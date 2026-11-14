"""Strict tests: ETH daily official SHA256 checks, no gaps, no fake forward."""
import csv
from datetime import datetime, timezone, timedelta, date
from hashlib import sha256
from io import BytesIO,TextIOWrapper,StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from zipfile import ZipFile, ZIP_DEFLATED
import json
import unittest
import eth_v93_daily_data_guard_20261114 as g

def make_day(day,missing=None,shuffle=False):
    start=g.utc_start(day)*1000
    rows=[]
    for h in range(24):
        if h==missing: continue
        ts=start+h*3600_000
        rows.append([ts,100,101,99,100,10,ts+3599_999,1000,20,5,500,0])
    if shuffle:
        rows[0],rows[1]=rows[1],rows[0]
    csvtext=StringIO()
    wr=csv.writer(csvtext)
    wr.writerows(rows)
    out=BytesIO()
    with ZipFile(out,"w",ZIP_DEFLATED) as z:
        z.writestr(f"ETHUSDT-1h-{day.isoformat()}.csv",csvtext.getvalue())
    return out.getvalue()

class DailyGuard(unittest.TestCase):
    def setUp(self):
        self.pre=date(2026,11,13)
        self.day=date(2026,11,14)
    def test_reject_missing_hour(self):
        with self.assertRaisesRegex(ValueError,"INCOMPLETE"):
            g.parse_daily(make_day(self.day,missing=4),self.day)
    def test_reject_reordered_hours(self):
        with self.assertRaisesRegex(ValueError,"GAPS"):
            g.parse_daily(make_day(self.day,shuffle=True),self.day)
    def test_completed_24h_with_timestamps(self):
        rows=g.parse_daily(make_day(self.day),self.day)
        self.assertEqual(len(rows),24)
        self.assertEqual(rows[0][0],g.utc_start(self.day))
        self.assertEqual(rows[-1][0],g.utc_start(self.day)+23*3600)
    def test_sha256_and_official_checks(self):
        body=make_day(self.pre)
        sh=sha256(body).hexdigest()
        def fake(url,max_size=0):
            return sh.encode() if url.endswith(".CHECKSUM") else body
        with patch.object(g,"get",side_effect=fake):
            v=g.verify(self.pre)
        self.assertEqual(v["zipSHA256"],sh)
        self.assertTrue(v["completeUTCday"])
        self.assertEqual(v["hourlyClosedCandles"],24)
    def test_checksum_tamper_fails_closed(self):
        body=make_day(self.pre)
        def bad(url,max_size=0):
            return b"0"*64 if url.endswith(".CHECKSUM") else body
        with patch.object(g,"get",side_effect=bad):
            with self.assertRaisesRegex(ValueError,"CHECKSUM_MISMATCH"):
                g.verify(self.pre)
    def test_preflight_does_not_claim_trades(self):
        with TemporaryDirectory() as tmp:
            with patch.object(g,"verify",return_value={
                "dateUTC":self.pre.isoformat(),"zipSHA256":"a"*64,
                "hourlyClosedCandles":24,"verifiedDirectWithOfficialChecksum":True}):
                s=g.run(Path(tmp),datetime(2026,11,14,17,tzinfo=timezone.utc),True)
                self.assertTrue(s["preflightOnly"])
                self.assertTrue(s["noProspectiveTradesClaimed"])
                self.assertEqual(s["checkedProspectiveDays"],0)
                self.assertTrue(s["monthlyStrategyReplayNotRun"])
    def test_daily_cumulative_ledger_persists(self):
        with TemporaryDirectory() as tmp:
            def fake(day):
                return {"dateUTC":day.isoformat(),"zipSHA256":"a"*64,
                        "hourlyClosedCandles":24,"verifiedDirectWithOfficialChecksum":True}
            with patch.object(g,"verify",side_effect=fake):
                first=g.run(Path(tmp),datetime(2026,11,15,17,tzinfo=timezone.utc))
                next=g.run(Path(tmp),datetime(2026,11,17,17,tzinfo=timezone.utc))
            self.assertEqual(first["checkedProspectiveDays"],1)
            self.assertEqual(next["checkedProspectiveDays"],3)
            ledger=json.loads((Path(tmp)/"daily_ledger.json").read_text())
            self.assertEqual(len(ledger["days"]),3)
    def test_existing_record_cannot_mutate(self):
        with TemporaryDirectory() as tmp:
            count=0
            def fake(day):
                nonlocal count
                count+=1
                return {"dateUTC":day.isoformat(),"zipSHA256":("a" if count==1 else "b")*64,
                        "hourlyClosedCandles":24,"verifiedDirectWithOfficialChecksum":True}
            with patch.object(g,"verify",side_effect=fake):
                g.run(Path(tmp),datetime(2026,11,15,17,tzinfo=timezone.utc))
                with self.assertRaisesRegex(ValueError,"PROOF_MUTATED"):
                    g.run(Path(tmp),datetime(2026,11,15,17,tzinfo=timezone.utc))
    def test_day_end_exclusive_and_no_future(self):
        self.assertEqual(g.day_span(self.day,self.day),[self.day])
        self.assertEqual(g.day_span(self.day,self.pre),[])
        with TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError,"NOT_COMPLETED"):
                g.run(Path(tmp),datetime(2026,11,14,17,tzinfo=timezone.utc),False)

if __name__=="__main__":
    unittest.main()
