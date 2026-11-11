"""V9 OI funding and CVD research must predict OWN candle body, never previous close."""
import copy,unittest
from test_v9_three_asset_derivatives_ablation import make,source_fetch
from v9_derivatives_own4h_color_study import (
    own_future_color,evaluate,run,CONTRACTS,HOUR,FOUR,DAY,EVAL_DAYS)

class V9OwnCandleDerivativeTests(unittest.TestCase):
    def test_actual_own_body_differs_from_last_close_direction(self):
        t=4*HOUR
        future=[
          {"t":t+i*HOUR,
           "o":100+i*.01,"h":101,"l":98,"c":99-i*.01,"v":10}
          for i in range(4)]
        first=own_future_color(future,t)
        self.assertEqual(first["color"],"RED")
        self.assertEqual(first["open"],100)
        self.assertLess(first["close"],100)
        # A previous 4H close at 80 would misleadingly imply GREEN,
        # but the OWN target candle body remains RED.
        self.assertGreater(first["close"],80)

    def test_21_days_three_assets_and_not_forward_performance(self):
        data=make(days=28)
        report=run(28*DAY,"key",fetch=source_fetch(data))
        self.assertEqual(set(report["assetResults"]),{
            "BTCUSDT","ETHUSDT","SOLUSDT"})
        self.assertTrue(report["noNotifications"])
        self.assertTrue(report["noActualNext4HModelTrainingOrPromotion"])
        self.assertFalse(report["trainingOrFeatureFitPerformed"])
        for s,x in report["assetResults"].items():
            self.assertEqual(x["intendedDistinct4HTargets"],126)
            self.assertEqual(len(x["rows"]),126)
            self.assertGreaterEqual(x["eligibleBothSourcesPlusFutureCandle"],100)
            self.assertTrue(x["postSelectionOfB_C_DNeverProvesDirectionalEdge"])
            self.assertEqual(x["results"]["A_priceMomentum"]["n"],
                             x["results"]["E_takerCVDOnly"]["n"])
            self.assertLessEqual(x["results"]["A_priceMomentum"]["correct"],126)

    def test_missing_oi_cannot_fabricate_causally_available_features(self):
        d=make(days=28)
        end=28*DAY
        start=end-EVAL_DAYS*DAY
        d["open-interest-history"]=[
            row for row in d["open-interest-history"]
            if row["t"]!=start-4*HOUR]
        row=evaluate(d["ohlcv-history"],
                     d["open-interest-history"],
                     d["funding-rate-history"],end)
        self.assertGreater(row["sourceMissingOrSkipped"],0)
        self.assertLess(row["eligibleBothSourcesPlusFutureCandle"],126)

    def test_future_unclosed_4h_cannot_be_labeled(self):
        d=make(days=28)
        start=28*DAY-FOUR
        d["ohlcv-history"]=[
            r for r in d["ohlcv-history"] if r["t"]!=start+2*HOUR]
        self.assertIsNone(own_future_color(d["ohlcv-history"],start))

if __name__=="__main__":
    unittest.main()
