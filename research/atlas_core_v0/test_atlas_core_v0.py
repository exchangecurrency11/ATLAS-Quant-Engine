"""Standalone deterministic E0/E1 tests. No network, orders or account mutations."""
import unittest
from pathlib import Path
from unittest.mock import patch
from research.atlas_core_v0 import atlas_core_v0 as core

def bar(t, o=100, h=105, l=95, c=101):
    return {"t":t,"o":o,"h":h,"l":l,"c":c}

class CoreContractTests(unittest.TestCase):
    def test_one_hour_current_open_cannot_be_used(self):
        series=[bar(0),bar(3600),bar(7200),bar(10800)]
        self.assertEqual([x["t"] for x in core.closed_bars_asof(series,3600,7200,2)],[0,3600])
    def test_four_hour_closes_on_boundary_only(self):
        series=[bar(0),bar(14400),bar(28800)]
        self.assertEqual(core.closed_bars_asof(series,14400,14400,1)[0]["t"],0)
        with self.assertRaisesRegex(ValueError,"INSUFFICIENT"):
            core.closed_bars_asof(series,14400,14399,1)
    def test_daily_only_yesterday_during_current_day(self):
        series=[bar(0),bar(86400),bar(172800)]
        self.assertEqual(core.closed_bars_asof(series,86400,86400+3600,1)[0]["t"],0)
    def test_close_not_available_one_second_before(self):
        with self.assertRaisesRegex(ValueError,"INSUFFICIENT"):
            core.closed_bars_asof([bar(0)],3600,3599,1)
    def test_wrong_utc_alignment_rejected(self):
        with self.assertRaisesRegex(ValueError,"BAD_BAR"):
            core.closed_bars_asof([bar(1)],3600,3600,1)
    def test_out_of_order_and_duplicate_rejected(self):
        for series in ([bar(3600),bar(0)],[bar(0),bar(0)]):
            with self.assertRaisesRegex(ValueError,"BAD_BAR"):
                core.closed_bars_asof(series,3600,7200,1)
    def test_missing_hour_causes_fail_closed(self):
        with self.assertRaisesRegex(ValueError,"MISSING_TIMEFRAME"):
            core.closed_bars_asof([bar(0),bar(7200)],3600,10800,2)
    def test_bad_ohlc_rejected(self):
        with self.assertRaisesRegex(ValueError,"INVALID_OHLC"):
            core.closed_bars_asof([bar(0,h=99)],3600,3600,1)
    def test_future_partial_ohlc_not_read(self):
        chosen=core.closed_bars_asof([bar(0),bar(3600,h=50)],3600,3600,1)
        self.assertEqual(len(chosen),1)
    def test_long_stop_first_even_when_tp_hit_and_gap_worse(self):
        self.assertEqual(core.stop_first_with_gap("LONG",98,bar(0,o=100,h=110,l=90)),98)
        self.assertEqual(core.stop_first_with_gap("LONG",98,bar(0,o=95,h=110,l=90)),95)
    def test_short_stop_first_and_gap(self):
        self.assertEqual(core.stop_first_with_gap("SHORT",105,bar(0,o=100,h=110,l=90)),105)
        self.assertEqual(core.stop_first_with_gap("SHORT",105,bar(0,o=108,h=110,l=90)),108)
    def test_no_stop_and_side_check(self):
        self.assertIsNone(core.stop_first_with_gap("LONG",80,bar(0)))
        with self.assertRaisesRegex(ValueError,"INVALID_SIDE"):
            core.stop_first_with_gap("INVALID",98,bar(0))
    def test_cost_change_is_monotonic_and_two_leg(self):
        net=[core.cost_stress_r(1.,100.,1.,bps) for bps in (9,25,50)]
        self.assertAlmostEqual(net[0],1.)
        self.assertAlmostEqual(net[1],.68)
        self.assertAlmostEqual(net[2],.18)
        self.assertTrue(net[0]>net[1]>net[2])
    def test_funding_added_as_cost_not_assumed_observed(self):
        self.assertAlmostEqual(core.cost_stress_r(1.,100.,1.,9,.4),.6)
        with self.assertRaisesRegex(ValueError,"INVALID_COST_INPUT"):
            core.cost_stress_r(1.,100.,0.,9)
    def test_time_zone_rejection(self):
        self.assertEqual(core.utc_seconds("2026-11-15T00:00:00Z"),1794700800)
        with self.assertRaisesRegex(ValueError,"NON_UTC"):
            core.utc_seconds("2026-11-15T03:00:00+03:00")
    def test_sealed_historical_e0_n_cost_status(self):
        audit=core.audit()
        self.assertFalse(audit["independentOutOfSample"])
        self.assertFalse(audit["ethIncludedInE0"])
        self.assertFalse(audit["archivesRedownloadedThisRun"])
        btc=audit["assets"]["BTCUSDT"]["aggregate"]["candidate"]
        sol=audit["assets"]["SOLUSDT"]["aggregate"]["candidate"]
        self.assertEqual((btc["trades"],sol["trades"]),(10,7))
        self.assertAlmostEqual(btc["netR"]["25"],-0.498882,places=5)
        self.assertAlmostEqual(sol["netR"]["25"],7.232935,places=5)
        self.assertTrue(all(v["decision"].startswith("BLOCK") for v in audit["assets"].values()))
    def test_frozen_spec_guard_and_source_drift(self):
        with patch.dict(core.PINS,{str(core.HISTORY):"f"*40}):
            with self.assertRaisesRegex(ValueError,"SEALED_INPUT_DRIFT"):
                core.audit()
    def test_no_portfolio_pf_or_drawdown_from_summary(self):
        a=core.audit()
        self.assertIsNone(a["portfolioProfitFactor"])
        self.assertIsNone(a["portfolioMaxDrawdown"])

if __name__=="__main__":
    unittest.main()
