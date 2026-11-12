"""SOL near-miss diagnostic is observation-only and cannot veto."""
import unittest
from collections import Counter

from v92_sol_near_miss_audit import make_diagnostic_gate
from v92_sol_holdout_backtest import START
from v92_bull_bear_candle_invalidation import HOUR


def star_bars(base, prior_low=98., prior_high=102.):
    bars=[{"t":base+i*HOUR,"o":100.,"h":prior_high,"l":prior_low,
           "c":100.,"v":1000.} for i in range(27)]
    bars.extend([
      {"t":base+27*HOUR,"o":99.,"h":100.,"l":94.,"c":95.,"v":1000.},
      {"t":base+28*HOUR,"o":95.,"h":96.,"l":88.,"c":94.8,"v":1000.},
      {"t":base+29*HOUR,"o":95.,"h":102.,"l":94.,"c":101.,"v":1000.},
    ])
    return bars


class V92SOLNearMissTests(unittest.TestCase):
    def test_sweep_pattern_is_counted_but_never_vetoed(self):
        bars=star_bars(START)
        audit=Counter();audit["examples"]=[]
        gate=make_diagnostic_gate([],audit)
        result=gate(bars,{"side":"bearish"},{"t":bars[-1]["t"]})
        self.assertTrue(result["passed"])
        self.assertEqual(audit["baselineRetests"],1)
        self.assertEqual(audit["retestsWithOpposingPattern"],1)
        self.assertEqual(audit["retestsWithQualifyingSweep"],1)
        self.assertEqual(audit["retestsWithPatternButNoSweep"],0)

    def test_pattern_without_prior20_sweep_is_logged_as_near_miss(self):
        bars=star_bars(START,prior_low=80.,prior_high=120.)
        audit=Counter();audit["examples"]=[]
        gate=make_diagnostic_gate([],audit)
        result=gate(bars,{"side":"bearish"},{"t":bars[-1]["t"]})
        self.assertTrue(result["passed"])
        self.assertEqual(audit["baselineRetests"],1)
        self.assertEqual(audit["retestsWithOpposingPattern"],1)
        self.assertEqual(audit["retestsWithQualifyingSweep"],0)
        self.assertEqual(audit["retestsWithPatternButNoSweep"],1)


if __name__=="__main__":
    unittest.main()
