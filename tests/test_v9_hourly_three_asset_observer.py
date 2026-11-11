"""V9 hourly observation research safety tests, independent of official 4H predictions."""
import copy,math,tempfile,json,unittest
from pathlib import Path
from test_v9_next4h_prestart_paper_capture import (
    synthetic_sources,fake_fetch,TARGET)
from test_v9_next4h_paper_outcome_score import forecast
from v9_hourly_three_asset_observer import (
    status_at,close_indicators,ema,macd_hist,read_locked,readable,HOUR,DAY,FOUR,iso)

NOW=TARGET+17*60


class HourlyV9Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sources=synthetic_sources()
        cls.fetch=fake_fetch(cls.sources)

    def test_hourly_observation_all_three_strict_status_only(self):
        with tempfile.TemporaryDirectory() as directory:
            r=status_at(NOW,"mock",fetch=self.fetch,ledger_dir=directory)
            self.assertEqual(r["status"],"V9_HOURLY_OBSERVATION_VERIFIED_PAPER_CONTEXT_ONLY")
            self.assertEqual(r["closed1HUTC"],iso(TARGET))
            self.assertEqual(r["active4HStartUTC"],iso(TARGET))
            self.assertEqual(r["active4HPriorOfficialPrediction"]["status"],
                             "NO_PRESTART_FORECAST_RECORDED")
            self.assertEqual(r["next4HPriorOfficialPrediction"]["status"],
                             "NO_PRESTART_FORECAST_RECORDED")
            self.assertTrue(r["doesNotRepaintOrBackfillMissing4HForecasts"])
            self.assertFalse(r["realOrders"])
            for s in ("BTCUSDT","ETHUSDT","SOLUSDT"):
                a=r["assets"][s]
                self.assertEqual(a["1H"]["closedAtUTC"],iso(TARGET))
                self.assertEqual(a["4H"]["closedAtUTC"],iso(TARGET))
                self.assertEqual(a["Daily"]["closedAtUTC"],iso(TARGET))
                for tf in ("1H","4H","Daily"):
                    self.assertTrue(0<=a[tf]["RSI14"]<=100)
                    self.assertTrue(math.isfinite(a[tf]["MACDHistogram"]))
                    self.assertTrue(math.isfinite(a[tf]["EMA200"]))
            self.assertIn("ÖNCEDEN KAYIT YOK",readable(r))

    def test_frozen_prestart_file_visible_but_not_recreated(self):
        with tempfile.TemporaryDirectory() as directory:
            p=forecast()
            path=Path(directory)/(iso(TARGET).replace(":","-")+".json")
            path.write_text(json.dumps(p))
            r=status_at(NOW,"mock",fetch=self.fetch,ledger_dir=directory)
            locked=r["active4HPriorOfficialPrediction"]
            self.assertEqual(locked["status"],"FROZEN_BEFORE_START_PAPER_FORECAST_RECORDED")
            self.assertEqual(locked["assetForecasts"]["BTCUSDT"]["direction"],"GREEN")
            self.assertEqual(locked["assetForecasts"]["ETHUSDT"]["direction"],"RED")
            self.assertEqual(locked["decisionCapturedUTC"],p["decisionCapturedUTC"])
            self.assertEqual(json.loads(path.read_text()),p)
            self.assertTrue(r["assets"]["BTCUSDT"]["contextOnlyNotANewPrestartDirectionForecast"])

    def test_stale_hour_is_rejected_not_backfilled(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError,"OUTSIDE_10_TO_59"):
                status_at(TARGET+6*60,"mock",fetch=self.fetch,ledger_dir=directory)

    def test_missing_hour_rejected_not_interpolated(self):
        records=copy.deepcopy(self.sources)
        del records["1hour"]["SOLUSDT"][-40]
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError,"MISSING_OR_STALE_CLOSED_1H"):
                status_at(NOW,"mock",fetch=fake_fetch(records),ledger_dir=directory)

    def test_indicator_basics(self):
        self.assertAlmostEqual(ema([10.]*220,200),10.)
        self.assertAlmostEqual(macd_hist([10.]*230),0.,places=6)

    def test_forged_forecast_cannot_enter_hourly_card(self):
        with tempfile.TemporaryDirectory() as directory:
            p=forecast()
            p["decisionCapturedUTC"]=iso(TARGET+60)
            (Path(directory)/(iso(TARGET).replace(":","-")+".json")).write_text(json.dumps(p))
            with self.assertRaisesRegex(ValueError,"NOT_CAPTURED_BEFORE_START"):
                status_at(NOW,"mock",fetch=self.fetch,ledger_dir=directory)


if __name__=="__main__":
    unittest.main()
