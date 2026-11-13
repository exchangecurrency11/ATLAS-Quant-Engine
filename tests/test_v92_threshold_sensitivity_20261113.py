"""Frozen threshold sensitivity: source parity, momentum direction and grids."""
import unittest
import v92_threshold_sensitivity_20261113 as v
import v92_filter_ablation_20261113 as old

class TestThresholds(unittest.TestCase):
    def test_prespecified_grid_and_defaults(self):
        self.assertEqual(len(v.GRID),7)
        self.assertEqual(len(v.SCENARIOS),32)
        self.assertTrue(all(v.DEFAULT[k] in values for k,values in v.GRID.items()))
        self.assertEqual(v.SCENARIOS["BASELINE"],(None,None))
    def test_original_fork_source_tether(self):
        self.assertEqual(old.fork_source().count(v.VOLUME_EXPECT),1)
        self.assertNotIn("_volume_threshold",old.original.replay_pair.__code__.co_names)
    def test_volume_threshold_patch_preserves_closed_retest_engine(self):
        cache={"indicators":{},"bias":{},"structures":{}}
        engine,q=v.engine_for("volume_surge_pct",10,"BTCUSDT",[],cache)
        self.assertEqual(engine.__globals__["_volume_threshold"],10)
        self.assertIn("_volume_threshold",engine.__code__.co_names)
        self.assertTrue(callable(q))
    def test_symmetric_rsi_thresholds_long_short(self):
        cache={"indicators":{},"bias":{},"structures":{}}
        engine,q=v.engine_for("rsi_long_cutoff",56,"ETHUSDT",[],cache)
        f=engine.__globals__["_momentum_side"]
        self.assertFalse(f({"RSI14":55,"hist":2,"EMA20":100},"bullish"))
        self.assertTrue(f({"RSI14":57,"hist":2,"EMA20":100},"bullish"))
        self.assertTrue(f({"RSI14":43,"hist":-2,"EMA20":100},"bearish"))
        self.assertFalse(f({"RSI14":45,"hist":-2,"EMA20":100},"bearish"))
    def test_macd_histogram_scale_direction(self):
        cache={"indicators":{},"bias":{},"structures":{}}
        engine,q=v.engine_for("macd_hist_ema_bps",2,"SOLUSDT",[],cache)
        f=engine.__globals__["_momentum_side"]
        self.assertFalse(f({"RSI14":60,"hist":.01,"EMA20":100},"bullish"))
        self.assertTrue(f({"RSI14":60,"hist":.03,"EMA20":100},"bullish"))
        self.assertTrue(f({"RSI14":40,"hist":-.03,"EMA20":100},"bearish"))
    def test_baseline_original_function_preserved(self):
        self.assertEqual(len(old.CONTROL_REQUIREMENTS),8)
        self.assertNotIn("_momentum_possible",old.original.replay_pair.__code__.co_names)

if __name__=="__main__":
    unittest.main()
