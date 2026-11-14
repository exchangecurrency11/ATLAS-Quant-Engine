"""E4B negative controls on official funding archive parsing and trade accounting."""
from __future__ import annotations
from hashlib import sha256
from io import BytesIO
from unittest import TestCase
from unittest.mock import patch
from zipfile import ZipFile, ZIP_DEFLATED

from research.atlas_core_v4 import atlas_core_e4b as f
from research.atlas_core_v3.test_atlas_core_e4 import trade,candle

def fakefund(ts,rate,symbol="BTCUSDT",interval=8.):
    return {
        "symbol":symbol,"fundingTimeMs":ts*1000,
        "fundingEpoch":ts,"fundingIntervalHours":interval,
        "fundingRate":rate,
    }

def window_tp1_then_stop():
    t=trade(gross=-1/3,exit_ts=9*3600)
    bars=[candle(0,100,106,99,102)]
    bars.extend(candle(i*3600,100,102,99,100) for i in range(1,8))
    bars.append(candle(8*3600,100,102,94,95))
    return t,bars

class FundingArchiveContract(TestCase):

    def test_source_code_integrity_and_reference(self):
        a,b,pins=f.verify_frozen_e4a()
        self.assertEqual(a["archiveCountSHA256"],159)
        self.assertEqual(len(b),64)
        self.assertIn("E4A",pins)

    def test_reject_mutated_E4A_engine_pin(self):
        with patch.object(f,"E4A_PINNED_GIT_BLOB","0"*40):
            with self.assertRaisesRegex(ValueError,"E4B_E4A_EXECUTION_MODEL_CODE_DRIFT"):
                f.verify_frozen_e4a()

    def test_funding_archive_uses_observed_actual_intervals(self):
        csvb=b"calc_time,funding_interval_hours,last_funding_rate\n1704067200000,8,0.00037409\n1704096000000,4,-0.00010000\n"
        got=f.parse_official_csv(csvb,"BTCUSDT","2024-01")
        self.assertEqual(len(got),2)
        self.assertAlmostEqual(got[0]["fundingRate"],.00037409)
        self.assertEqual(got[1]["fundingIntervalHours"],4.)
        self.assertLess(got[1]["fundingRate"],0.)

    def test_schema_change_rejected(self):
        content=b"timestamp,rate\n1704067200000,.01\n"
        with self.assertRaisesRegex(ValueError,"E4B_UNEXPECTED_OFFICIAL_FUNDING_CSV_SCHEMA"):
            f.parse_official_csv(content,"BTCUSDT","2024-01")

    def test_non_hourly_settlement_rejected(self):
        content=b"calc_time,funding_interval_hours,last_funding_rate\n1704067800000,8,.001\n"
        with self.assertRaisesRegex(ValueError,"E4B_NON_HOURLY_SETTLEMENT_TIMESTAMP"):
            f.parse_official_csv(content,"BTCUSDT","2024-01")

    def test_duplicate_funding_timestamp_rejected(self):
        content=b"calc_time,funding_interval_hours,last_funding_rate\n1704067200000,8,.001\n1704067200000,8,.001\n"
        with self.assertRaisesRegex(ValueError,"E4B_DUPLICATE_OR_OUT_OF_ORDER_FUNDING_TIMESTAMP"):
            f.parse_official_csv(content,"BTCUSDT","2024-01")

    def test_nonfinite_or_extreme_rate_rejected(self):
        for rate in ("NaN","Infinity","0.5"):
            content=f"calc_time,funding_interval_hours,last_funding_rate\n1704067200000,8,{rate}\n".encode()
            with self.assertRaisesRegex(ValueError,"E4B_ABSURD_OR_INVALID_FUNDING_RATE"):
                f.parse_official_csv(content,"BTCUSDT","2024-01")

    def test_month_missing_funding_rejected(self):
        content=b"calc_time,funding_interval_hours,last_funding_rate\n1706745600000,8,.0001\n"
        with self.assertRaisesRegex(ValueError,"E4B_FUNDING_DATE_OUTSIDE_ARCHIVE_MONTH"):
            f.parse_official_csv(content,"BTCUSDT","2024-01")

    def test_manifest_checksum_verifies_zip_bytes(self):
        name="BTCUSDT-fundingRate-2024-01.zip"
        raw=b"calc_time,funding_interval_hours,last_funding_rate\n1704067200000,8,.0001\n"
        stream=BytesIO()
        with ZipFile(stream,"w",ZIP_DEFLATED) as z:
            z.writestr(name.replace(".zip",".csv"),raw)
        zipbytes=stream.getvalue()
        checksum=(sha256(zipbytes).hexdigest()+"  "+name+"\n").encode()
        with patch.object(f,"download_byte_source",side_effect=[checksum,zipbytes]):
            coin,month,events,proof=f.fetch_month("BTCUSDT","2024-01")
        self.assertEqual((coin,month),("BTCUSDT","2024-01"))
        self.assertEqual(len(events),1)
        self.assertEqual(proof["zipSHA256"],sha256(zipbytes).hexdigest())
        with patch.object(f,"download_byte_source",side_effect=[
             ("0"*64+"  "+name).encode(),zipbytes]):
            with self.assertRaisesRegex(ValueError,"E4B_OFFICIAL_FUNDING_ARCHIVE_SHA256_MISMATCH"):
                f.fetch_month("BTCUSDT","2024-01")

    def test_fail_closed_on_missing_declared_funding_events(self):
        rows=[fakefund(0,.0001),fakefund(8*3600,.0001),fakefund(24*3600,.0001)]
        with self.assertRaisesRegex(ValueError,"E4B_FUNDING_HOLE_NOT_COVERED_BY_INTERVAL"):
            f.check_timeline_coverage(rows,0,32*3600,"BTCUSDT")

    def test_changed_interval_allows_frequency_change_without_fabricating_event(self):
        rows=[fakefund(0,.0001,interval=8),
              fakefund(8*3600,.0001,interval=4),
              fakefund(12*3600,.0001,interval=4),
              fakefund(16*3600,.0001,interval=4)]
        result=f.check_timeline_coverage(rows,0,20*3600,"BTCUSDT")
        self.assertTrue(result["completeByDeclaredIntervals"])
        self.assertEqual(result["observedFundingIntervalsHours"],[4,8])

    def test_empty_truncated_period_rejected(self):
        with self.assertRaisesRegex(ValueError,"E4B_SYMBOL_FUNDING_TIMELINE_MISSING"):
            f.check_timeline_coverage([],0,86400,"BTCUSDT")
        with self.assertRaisesRegex(ValueError,"E4B_FUNDING_MISSING_PERIOD_BEGIN"):
            f.check_timeline_coverage([fakefund(16*3600,.0001)],0,86400,"BTCUSDT")

    def test_endpoint_does_not_accept_arbitrary_url(self):
        for url in ("https://evil.example/a","http://data.binance.vision/x",
                    f.BASE+"/BTCUSDT/../../bad.zip"):
            with self.assertRaisesRegex(ValueError,"E4B_UNAPPROVED_FUNDING_ARCHIVE_URL"):
                f.download_byte_source(url,max_bytes=50)

    def test_invalid_worker_count_no_download(self):
        for k in (0,7,-1):
            with self.assertRaisesRegex(ValueError,"E4B_WORKER_COUNT"):
                f.compute(k)

class FundingAccountingContract(TestCase):

    def test_signed_real_rate_long_pays_short_receives(self):
        t,bars=window_tp1_then_stop()
        event=fakefund(8*3600,.01)
        x=f.estimate_with_actual_rates(t,bars,f.e4.SCENARIOS[0],[event])
        self.assertEqual(x["actualRateFunding"]["matchedActualFundingRateEvents"],1)
        self.assertGreater(x["actualRateFunding"]["signedFundingRProxy"],0)
        self.assertLess(x["netR"],x["netRWithoutFunding"])
        t2=dict(t,side="bearish",stop=105.,
                targets=[95.,90.,85.],realizedR=-1/3)
        bars2=[candle(0,100,101,94,98)]
        bars2.extend(candle(i*3600,100,101,98,100) for i in range(1,8))
        bars2.append(candle(8*3600,100,106,99,105))
        y=f.estimate_with_actual_rates(t2,bars2,f.e4.SCENARIOS[0],[event])
        self.assertLess(y["actualRateFunding"]["signedFundingRProxy"],0)
        self.assertGreater(y["netR"],y["netRWithoutFunding"])

    def test_negative_rate_long_receives_positive_cash_credit(self):
        t,bars=window_tp1_then_stop()
        x=f.estimate_with_actual_rates(t,bars,f.e4.SCENARIOS[0],
                                     [fakefund(8*3600,-.005)])
        self.assertLess(x["actualRateFunding"]["signedFundingCashCostPerUnitProxy"],0)
        self.assertGreater(x["netR"],x["netRWithoutFunding"])

    def test_after_tp1_funding_only_two_thirds_position(self):
        t,bars=window_tp1_then_stop()
        x=f.estimate_with_actual_rates(t,bars,f.e4.SCENARIOS[0],
                                     [fakefund(8*3600,.01)])
        self.assertEqual(x["actualRateFunding"]["events"][0]["positionFractionBeforeFunding"],.66666667)

    def test_exact_entry_and_exit_boundary_excluded(self):
        t,bars=window_tp1_then_stop()
        rows=[fakefund(0,.01),fakefund(8*3600,.01),
              fakefund(9*3600,.01)]
        x=f.estimate_with_actual_rates(t,bars,f.e4.SCENARIOS[0],rows)
        self.assertEqual(x["actualRateFunding"]["matchedActualFundingRateEvents"],1)
        self.assertTrue(x["actualRateFunding"]["fundingOnEntryAndExitBoundaryExcluded"])

    def test_no_funding_event_cannot_fabricate_cost(self):
        t,bars=window_tp1_then_stop()
        x=f.estimate_with_actual_rates(t,bars,f.e4.SCENARIOS[0],[])
        self.assertEqual(x["netR"],x["netRWithoutFunding"])
        self.assertEqual(x["actualRateFunding"]["matchedActualFundingRateEvents"],0)

    def test_source_events_must_be_sorted(self):
        t,bars=window_tp1_then_stop()
        r=f.e4.simulate_trade(t,bars,
            f.e4.Scenario("none",6,1,2,0))
        with self.assertRaisesRegex(ValueError,"E4B_UNORDERED_FUNDING_EVENTS"):
            f.calculate_observed_funding(
                t,bars,r,[fakefund(8*3600,.001),fakefund(0,.001)])

    def test_unchanged_spread_commission_impact_profiles(self):
        self.assertEqual([v.roundtrip_assumed_cost_per_side_bps
                          for v in f.SCENARIOS],[9,25,50])
        self.assertEqual(len(f.SCENARIOS),3)

    def test_mismatch_mark_open_requires_valid_hour(self):
        t,bars=window_tp1_then_stop()
        r=f.e4.simulate_trade(t,bars,
            f.e4.Scenario("none",6,1,2,0))
        with self.assertRaisesRegex(ValueError,"E4B_FUNDING_HOUR_CANNOT_BE_PRICED"):
            f.calculate_observed_funding(t,bars,r,[fakefund(8*3600+60,.001)])

    def test_funding_cash_not_claimed_as_account_settlement(self):
        t,bars=window_tp1_then_stop()
        x=f.estimate_with_actual_rates(t,bars,f.e4.SCENARIOS[0],
                                     [fakefund(8*3600,.001)])
        o=x["actualRateFunding"]
        self.assertFalse(o["actualAccountCashDebitOrCreditObserved"])
        self.assertTrue(o["cashIsModeledWithOHLCMarkProxy"])
        self.assertFalse(o["events"][0]["markPriceObserved"])

if __name__=="__main__":
    import unittest
    unittest.main()
