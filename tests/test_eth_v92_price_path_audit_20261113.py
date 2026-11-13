"""Strict ETH hourly price-path audit: verify direction, time, stop first, gaps."""
import unittest
from datetime import datetime,timezone
import eth_v92_price_path_audit_20261113 as x

class PathAuditTests(unittest.TestCase):
    def example(self,side="bullish",reason="STOP_FIRST_OR_AFTER_TP",
                entry="2026-06-05T17:00:00Z",exit_t="2026-06-05T18:00:00Z"):
        return {"side":side,"entryUTC":entry,"retestUTC":"2026-06-05T16:00:00Z",
                "exitUTC":exit_t,"entry":100.,"riskPct":1.,
                "netR9Bps":-1.,"exitReason":reason}
    def row(self,t,h,l):
        return {t:{"t":t,"o":100.,"h":h,"l":l,"c":100.,"v":10.}}
    def test_long_same_hour_stop_and_first_tp_uncertain(self):
        t=self.example()
        epoch=x.epoch(t["entryUTC"])
        d=x.excursion(t,self.row(epoch,102,98))
        self.assertEqual(d["holdingHourlyBars"],1)
        self.assertTrue(d["stopAndFirstTargetBothInFinalHourlyRange"])
        self.assertTrue(d["endHourStopTouched"])
        self.assertAlmostEqual(d["maximumFavorableExcursionR"],2)
        self.assertAlmostEqual(d["maximumAdverseExcursionR"],2)
        self.assertFalse(d["favorableAtLeast1RBeforeFinalHour"])
    def test_short_side_mfe_and_mae_swapped(self):
        t=self.example(side="bearish")
        i=x.epoch(t["entryUTC"])
        d=x.excursion(t,self.row(i,101.5,98.5))
        self.assertTrue(d["endHourStopTouched"])
        self.assertTrue(d["endHourTP1Touched"])
        self.assertAlmostEqual(d["maximumFavorableExcursionR"],1.5)
        self.assertAlmostEqual(d["maximumAdverseExcursionR"],1.5)
    def test_source_gap_fails(self):
        t=self.example()
        with self.assertRaisesRegex(ValueError,"MISSING_VERIFIED_ETH_HOUR"):
            x.excursion(t,{})
    def test_stop_wick_parity_fails_on_bad_archive(self):
        t=self.example()
        i=x.epoch(t["entryUTC"])
        with self.assertRaisesRegex(ValueError,"STOP_FIRST_ARCHIVED"):
            x.excursion(t,self.row(i,100.5,99.8))
    def test_tp3_parity_fails_on_bad_archive(self):
        t=self.example(reason="TP3_COMPLETE")
        i=x.epoch(t["entryUTC"])
        with self.assertRaisesRegex(ValueError,"TP3_ARCHIVED"):
            x.excursion(t,self.row(i,102.,99.5))
    def test_no_intrabar_order_fabrication(self):
        t=self.example()
        i=x.epoch(t["entryUTC"])
        d=x.excursion(t,self.row(i,101.5,98))
        self.assertTrue(d["stopFirstPricePathIntraHourUnknown"])
        self.assertTrue(d["marketFutureUnknownAtTradeEntry"])
    def test_only_24_closed_hours(self):
        t=self.example(exit_t="2026-06-06T19:00:00Z")
        with self.assertRaisesRegex(ValueError,"24_HOURS"):
            x.touched_months(t)
    def test_touched_months_cross_midnight(self):
        t=self.example(entry="2026-01-31T23:00:00Z",exit_t="2026-02-01T01:00:00Z")
        self.assertEqual(x.touched_months(t),{"2026-01","2026-02"})
    def test_summaries_explicit_losers(self):
        t=self.example()
        i=x.epoch(t["entryUTC"])
        d=x.excursion(t,self.row(i,101.5,98))
        v=x.summarize([d])
        self.assertEqual(v["losingTrades25bps"],1)
        self.assertEqual(v["stopAndTP1SameFinalHourCount"],1)
        self.assertEqual(v["losersThatReached1RBeforeFinalHour"],0)

if __name__=="__main__":
    unittest.main()
