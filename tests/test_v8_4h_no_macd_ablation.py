"""Guard MACD-free 15:00/19:00 retrospective freeze and no-trade conclusions."""
import copy
import json
import unittest
from pathlib import Path

from v8_4h_no_macd_ablation import run


class NoMacdFrozenTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source=json.loads(Path(
            "forward/v8_blind4h/2026-11-10_15-to-19-TSI.json").read_text())

    def test_reconstruction_covers_three_assets(self):
        j=run(self.source)
        self.assertEqual(j["directionHits"],3)
        self.assertEqual(j["assessedAssets"],3)
        for x in j["coins"].values():
            self.assertEqual(x["primaryTrendMACDFree"],"BEARISH")
            self.assertTrue(x["oneHourAgrees"])
            self.assertFalse(x["MACDUsed"])
            self.assertFalse(x["V7PaperEntryAt15"])
            self.assertEqual(x["V7New1HBOSAt15"],0)

    def test_macd_values_have_zero_influence_on_output(self):
        original=run(self.source)
        transformed=copy.deepcopy(self.source)
        for c in transformed["coins"].values():
            for tf in ("1hour","4hour","daily"):
                c["asOf15TSI"]["timeframes"][tf]["indicators"]["MACDHistogram"]=999999
        retest=run(transformed)
        self.assertEqual(original,retest)

    def test_future_candle_does_not_change_frozen_prediction(self):
        x=copy.deepcopy(self.source)
        before=run(x)
        for c in x["coins"].values():
            c["asOf19TSI"]["timeframes"]["4hour"]["OHLCV"]["c"]=999999
        after=run(x)
        for coin in before["coins"]:
            self.assertEqual(
                before["coins"][coin]["primaryTrendMACDFree"],
                after["coins"][coin]["primaryTrendMACDFree"])

    def test_earlier_data_inconsistency_rejected(self):
        bad=copy.deepcopy(self.source)
        bad["coins"]["ETHUSDT_PERP.A"]["asOf15TSI"]["timeframes"]["4hour"]["lastClosedUTC"]="2026-11-10T16:00:00Z"
        with self.assertRaisesRegex(ValueError,"FUTURE_OR_STALE_BAR"):
            run(bad)

    def test_eth_not_fake_as_live(self):
        j=run(self.source)
        self.assertFalse(j["coins"]["ETHUSDT_PERP.A"]["asOf15ActualVerifiedSnapshot"])
        self.assertFalse(j["realtimePrediction"])


if __name__=="__main__":
    unittest.main()
