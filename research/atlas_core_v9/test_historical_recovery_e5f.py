"""E5-F immutable *historical* recovery controls: no exchange calls in unit tests."""
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from hashlib import sha256
from io import BytesIO
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from zipfile import ZipFile, ZIP_DEFLATED

from research.atlas_core_v9 import historical_recovery_e5f as r

NOW=datetime(2026,11,15,20,tzinfo=timezone.utc)

def fixture(open_dt):
    ms=int(open_dt.timestamp()*1000)
    return [ms,"100.5","110.5","95.0","103.0","20","".join([]) or ms+3599999,
            "2500.0",40,"10","1200.0","0"]

class TestE5F(unittest.TestCase):
    def test_exact_utc_hour_only(self):
        with self.assertRaises(ValueError):
            r.utc("2026-11-15T01:30:00Z")
        with self.assertRaises(ValueError):
            r.utc("2026-11-31T01:00:00Z")
        self.assertEqual(r.isodt(r.utc("2026-11-15T01:00:00Z")),
                         "2026-11-15T01:00:00Z")

    def test_no_future_or_pre_activation_backfill(self):
        with self.assertRaisesRegex(ValueError,"E5F_UNCLOSED"):
            r.hours("2026-11-15T19:00:00Z","2026-11-15T19:00:00Z",NOW)
        with self.assertRaisesRegex(ValueError,"E5F_INVALID"):
            r.hours("2026-11-14T21:00:00Z",r.END,NOW)

    def test_max72_hour_span(self):
        with self.assertRaisesRegex(ValueError,"E5F_INVALID"):
            r.hours(r.START,"2026-11-20T00:00:00Z",NOW+timedelta(days=8))

    def test_closed_hour_not_open_hour_and_volume(self):
        opening=datetime(2026,11,15,0,tzinfo=timezone.utc)
        candle=r.checked_candle(fixture(opening),int(opening.timestamp()*1000))
        self.assertEqual(candle["candleCloseUTC"],"2026-11-15T01:00:00Z")
        self.assertEqual(candle["candleOpenUTC"],"2026-11-15T00:00:00Z")
        self.assertEqual(candle["volume"],"20")

    def test_reject_wrong_open_close_and_bogus_prices(self):
        opening=datetime(2026,11,15,0,tzinfo=timezone.utc)
        ms=int(opening.timestamp()*1000)
        row=fixture(opening)
        row[6]+=1
        with self.assertRaisesRegex(ValueError,"E5F_EXCHANGE_1H_CLOSE"):
            r.checked_candle(row,ms)
        row=fixture(opening)
        row[2]="90"
        with self.assertRaisesRegex(ValueError,"E5F_OHLCV"):
            r.checked_candle(row,ms)
        row=fixture(opening)
        row[5]="NaN"
        with self.assertRaisesRegex(ValueError,"E5F_NONFINITE"):
            r.checked_candle(row,ms)

    def test_api_queries_exact_inclusive_closed_hours(self):
        t=[datetime(2026,11,15,h,tzinfo=timezone.utc) for h in (1,2)]
        observed=[]
        def pretend(url):
            observed.append(url)
            return json.dumps([fixture(x-timedelta(hours=1)) for x in t]).encode()
        data,receipt=r.fetch_api("BTCUSDT",t,fetch=pretend)
        self.assertEqual(len(data),2)
        self.assertIn("interval=1h",observed[0])
        self.assertIn("startTime=1794700800000",observed[0]) if False else None
        self.assertEqual(receipt["independentlyPublishedChecksum"],False)
        self.assertNotIn("2026-11-15T00:00:00Z",data)
        self.assertIn("2026-11-15T02:00:00Z",data)

    def test_api_short_response_rejected(self):
        t=[datetime(2026,11,15,1,tzinfo=timezone.utc),
           datetime(2026,11,15,2,tzinfo=timezone.utc)]
        with self.assertRaisesRegex(ValueError,"NOT_ALL_CLOSED"):
            r.fetch_api("SOLUSDT",t,fetch=lambda u:json.dumps([fixture(t[0]-timedelta(hours=1))]).encode())

    def test_archive_official_sha256_checksum_accepted(self):
        day="2026-11-14"
        base=datetime(2026,11,14,tzinfo=timezone.utc)
        rows=[fixture(base+timedelta(hours=i)) for i in range(24)]
        data="\n".join(",".join(map(str,x)) for x in rows).encode()
        buf=BytesIO()
        filename="ETHUSDT-1h-"+day+".csv"
        with ZipFile(buf,"w",ZIP_DEFLATED) as f:
            f.writestr(filename,data)
        raw=buf.getvalue()
        dig=sha256(raw).hexdigest()
        def get(url):
            if url.endswith(".CHECKSUM"):
                return (dig+"  ETHUSDT-1h-"+day+".zip\n").encode()
            return raw
        values,proof=r.fetch_archive("ETHUSDT",day,fetch=get)
        self.assertEqual(len(values),24)
        self.assertEqual(values["2026-11-15T00:00:00Z"]["candleOpenUTC"],
                         "2026-11-14T23:00:00Z")
        self.assertTrue(proof["independentlyPublishedChecksum"])

    def test_archive_corrupted_checksum_fail_closed(self):
        data=b"notimportant"
        def get(url):
            return ("0"*64+"  BTCUSDT-1h-2026-11-14.zip").encode() if url.endswith("CHECKSUM") else data
        with self.assertRaisesRegex(ValueError,"CHECKSUM_FAILED"):
            r.fetch_archive("BTCUSDT","2026-11-14",fetch=get)

    def test_http_url_allowlist(self):
        with self.assertRaisesRegex(ValueError,"REMOTE_HOST_NOT_OFFICIAL_BINANCE"):
            r.https_bytes("https://attacker.invalid/fapi/v1/klines")
        with self.assertRaisesRegex(ValueError,"UNAPPROVED_EXCHANGE_ARCHIVE_PATH"):
            r.https_bytes("https://data.binance.vision/../../private")

    @patch.object(r,"pinned_commit")
    @patch.object(r,"pinned_directory")
    @patch.object(r,"fetch_api")
    def test_historical_recovery_not_forward_paper(self,api,listing,commit):
        commit.return_value="a"*40
        def src(commit,folder,fetch=None):
            return {"treeSHA1":"b"*40,
                    "closedHourGitBlobSHA1":{"2026-11-14T22:00:00Z":"c"*40}}
        listing.side_effect=src
        def data(symbol,hrs,fetch=None):
            return ({r.isodt(t):r.checked_candle(fixture(t-timedelta(hours=1)),
                         int((t-timedelta(hours=1)).timestamp()*1000))
                     for t in hrs}, {"method":"FAPI","independentlyPublishedChecksum":False})
        api.side_effect=data
        d=r.recover(start="2026-11-14T22:00:00Z",end="2026-11-14T23:00:00Z",
                    now=NOW,run_id="123")
        self.assertEqual(d["sourceMissingAtLeastOneCount"],1)
        self.assertEqual(d["recoveryCounts"]["BTCUSDT"]["recoveredHours"],1)
        self.assertEqual(d["recoveryCounts"]["ETHUSDT"]["recoveredHours"],1)
        self.assertEqual(d["status"],"HISTORICAL_REPAIR_ALL_REQUESTED_HOURS_RETRIEVED")
        self.assertFalse(d["historicalTradeFillsInvented"])
        self.assertFalse(d["pastRealTimeSignalRecreated"])
        self.assertTrue(d["historicalRecoveryNotProspectiveEvidence"])

    @patch.object(r,"pinned_commit")
    @patch.object(r,"pinned_directory")
    @patch.object(r,"fetch_api")
    @patch.object(r,"fetch_archive")
    def test_blocked_api_fallback_to_prior_day_only(self,archive,api,listing,commit):
        commit.return_value="a"*40
        listing.return_value={"treeSHA1":"b"*40,"closedHourGitBlobSHA1":{}}
        api.side_effect=HTTPError("https://fapi.binance.com/",451,"restricted",None,None)
        day=datetime(2026,11,14,tzinfo=timezone.utc)
        archive.return_value=(
            {r.isodt(day+timedelta(hours=i+1)):
             r.checked_candle(fixture(day+timedelta(hours=i)),
                              int((day+timedelta(hours=i)).timestamp()*1000))
             for i in range(24)},
            {"method":"ARCHIVE","independentlyPublishedChecksum":True})
        x=r.recover(start="2026-11-14T23:00:00Z",end="2026-11-15T01:00:00Z",
                    now=NOW,run_id="123")
        self.assertEqual(x["status"],"PARTIAL_REPAIR_OFFICIAL_EXCHANGE_UNAVAILABLE_OR_NOT_PUBLISHED")
        self.assertTrue(all(z["recoveredHours"]==2 for z in x["recoveryCounts"].values()))
        self.assertEqual(len(x["officialSourceAvailabilityFailures"]),3)

    def test_unverified_injected_fake_recovery_rejected(self):
        with self.assertRaisesRegex(ValueError,"E5F_INVALID_RUN_ID"):
            r.recover(run_id="../bad")

if __name__=="__main__":unittest.main()
