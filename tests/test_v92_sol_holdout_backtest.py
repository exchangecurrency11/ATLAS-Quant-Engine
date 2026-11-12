"""Earlier-period V9.2 SOL temporal-holdout safety tests."""
import unittest
from collections import Counter

from v92_sol_holdout_backtest import (
    WARMUP_START,START,END,MONTHS,EXPECTED,validate_manifest,make_gate
)
from v92_bull_bear_candle_invalidation import HOUR


def star_bars(base):
    bars=[{"t":base+i*HOUR,"o":100.,"h":102.,"l":98.,
           "c":100.,"v":1000.} for i in range(27)]
    bars.extend([
      {"t":base+27*HOUR,"o":99.,"h":100.,"l":94.,"c":95.,"v":1000.},
      {"t":base+28*HOUR,"o":95.,"h":96.,"l":88.,"c":94.8,"v":1000.},
      {"t":base+29*HOUR,"o":95.,"h":102.,"l":94.,"c":101.,"v":1000.},
    ])
    return bars


class V92SOLHoldoutTests(unittest.TestCase):
    def test_holdout_is_earlier_than_v92_selection_window(self):
        self.assertEqual(START,1664582400)
        self.assertEqual(END,1727740800)
        self.assertEqual(WARMUP_START,1651363200)
        self.assertLess(WARMUP_START,START)
        self.assertEqual(END,1727740800)
        self.assertEqual(len(MONTHS),29)
        self.assertEqual(MONTHS[0],"2022-05")
        self.assertEqual(MONTHS[-1],"2024-09")

    def test_archive_manifest_requires_all_60_monthly_checksums(self):
        manifest={
          "source":"Binance official data.binance.vision FUTURES/UM monthly 1h klines",
          "firstUTC":"2022-04-01T00:00:00+00:00",
          "endExclusiveUTC":"2024-10-01T00:00:00+00:00",
          "checksumsVerified":60,
          "pairCounts":{"BTCUSDT":dict(EXPECTED),"SOLUSDT":dict(EXPECTED)},
          "inputFiles":[
            {"symbol":sym,"month":month,"sha256":"a"*64}
            for sym in ("BTCUSDT","SOLUSDT") for month in MONTHS
          ],
        }
        self.assertTrue(validate_manifest(manifest))
        manifest["checksumsVerified"]=59
        with self.assertRaisesRegex(ValueError,"MANIFEST_INVALID"):
            validate_manifest(manifest)

    def test_sol_gate_vetoes_only_opposing_confirmed_star_with_prior20_sweep(self):
        bars=star_bars(START)
        at=bars[-1]["t"]+HOUR
        audit=Counter();audit["examples"]=[]
        gate=make_gate("SOLUSDT",[],audit,veto=True)
        decision=gate(bars,{"side":"bearish"},{"t":bars[-1]["t"]})
        self.assertFalse(decision["passed"])
        self.assertEqual(audit["rejectedRetests"],1)
        self.assertEqual(audit["MORNING_STAR_1H"],1)

    def test_btc_is_observation_only_under_same_rule(self):
        bars=star_bars(START)
        audit=Counter();audit["examples"]=[]
        gate=make_gate("BTCUSDT",[],audit,veto=True)
        decision=gate(bars,{"side":"bearish"},{"t":bars[-1]["t"]})
        self.assertTrue(decision["passed"])
        self.assertEqual(audit["rejectedRetests"],0)
        self.assertEqual(audit["opposingSelectedPatternsObserved"],1)


if __name__=="__main__":
    unittest.main()
