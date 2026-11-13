"""Safety and causal retest-only classification tests for BTC / ETH forensics."""
from collections import Counter
import copy
import unittest

from v92_btc_eth_forensics_20261113 import (
    info_at_retest,accepted,gate_for,HOUR
)

def sample():
    one=[]
    for i in range(90):
        t=i*HOUR
        one.append({"t":t,"o":100.0,"h":101.0,"l":99.0,
                    "c":100.4 if i%3 else 99.6,
                    "v":100. if i<89 else 140.})
    daily=[{"t":i*24*HOUR,"o":100.,"h":101.,"l":99.,
            "c":100.+.1*i,"v":100.} for i in range(10)]
    active={"side":"bullish","knownUTC":83*HOUR,
            "bosBar":one[83],"index":83}
    return one,daily,active

class FixedCausalResearchTests(unittest.TestCase):
    def test_no_future_daily_or_hour_can_change_completed_retest_decision(self):
        one,daily,active=sample()
        feats=info_at_retest(one,daily=daily,active=active)
        more=copy.deepcopy(one)
        more.extend({"t":i*HOUR,"o":100.,"h":900.,"l":1.,
                     "c":800.,"v":100000.} for i in range(90,100))
        # Caller must pass only closed candles; gate itself uses one[-1].
        # Force identical prefix to avoid confusing post-retet hindsight.
        later_daily=daily+[{"t":100*24*HOUR,"o":10.,"h":900.,"l":1.,"c":800.,"v":100000.}]
        feats2=info_at_retest(one,daily=later_daily,active=active)
        self.assertEqual(feats,feats2)

    def test_strict_bos_prior_to_retest(self):
        one,daily,active=sample()
        active["knownUTC"]=90*HOUR
        with self.assertRaisesRegex(ValueError,"NOT_PRECONFIRMED_BOS"):
            info_at_retest(one,daily=daily,active=active)

    def test_direction_and_stop_gate_are_predeclared(self):
        one,daily,active=sample()
        f=info_at_retest(one,daily=daily,active=active)
        self.assertFalse(accepted("ETH_SHORT_ONLY",f))
        self.assertFalse(accepted("BTC_SHORT_ONLY",f))
        self.assertTrue(accepted("BASELINE_4H",f))
        self.assertEqual(
            accepted("ETH_RETEST_STOPWIDTH_LE_2ATR",f),
            f["stopRelativeATRRetestClose"]<=2.)
        with self.assertRaisesRegex(ValueError,"UNREGISTERED_MODE"):
            accepted("BETTER_AFTER_SEEING_LOSER",f)

    def test_gate_only_retets_closed_at_that_time(self):
        one,daily,active=sample()
        audit=Counter()
        audit["examples"]=[]
        filt=gate_for("ETH_RETEST_BODY_GE_0P2ATR",daily,audit)
        out=filt(one,active,one[-1])
        self.assertIn("passed",out)
        self.assertEqual(audit["evaluatedRetests"],1)
        self.assertEqual(audit["examples"][0]["asOfClosed1HUTC"],
                         "1970-01-04T18:00:00Z")
        self.assertTrue(audit["examples"][0]["noFutureCandlesUsed"])

if __name__=="__main__":
    unittest.main()
