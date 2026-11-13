"""Point-in-time three-asset 30-day/4h correlation and filter regression."""
import copy
import math
import unittest

from v92_three_asset_correlation_study import (
    AsOfRegimes, FOUR, HOUR, SYMBOLS, WINDOW, PAIRS,
    pearson, gate_decision, HIGH_CORR, MAX_ETH_ATR_RATIO,
)

def make_hourly():
    """Uniform, valid contiguous synthetic 1H series, shared 4H log returns."""
    result={}
    for symbol in SYMBOLS:
        factor={"BTCUSDT":1.,"ETHUSDT":1.6,"SOLUSDT":2.}[symbol]
        rows=[]
        for i in range(224*4):
            q=i//4
            close=100*math.exp(0.0009*q*factor+0.004*factor*math.sin(q/3))
            rows.append({"t":i*HOUR,"o":close,"h":close*1.002,
                         "l":close*0.998,"c":close,"v":100.})
        result[symbol]=rows
    return result

class CorrelationTests(unittest.TestCase):
    def test_identical_returns_have_one_correlation(self):
        sample=[math.sin(i/5) for i in range(WINDOW)]
        self.assertAlmostEqual(pearson(sample,sample),1.,places=10)
        self.assertAlmostEqual(pearson(sample,[-x for x in sample]),-1.,places=10)

    def test_correlations_are_not_available_during_warmup(self):
        regimes=AsOfRegimes(make_hourly())
        self.assertFalse(regimes.at(10*FOUR)["available"])

    def test_future_4h_candles_never_enter_past_retest_features(self):
        original=make_hourly()
        at=200*FOUR+HOUR
        initial=AsOfRegimes(original).at(at)
        self.assertTrue(initial["available"])
        self.assertLessEqual(
            int(initial["lastAll4HCloseUTC"][11:13]),23)
        self.assertTrue(initial["noFutureCandles"])
        self.assertTrue(initial["highAllThreeCorrAtRetest"])
        bad=copy.deepcopy(original)
        for s in SYMBOLS:
            for i in range(200*4,len(bad[s])):
                bad[s][i]["o"]*=10
                bad[s][i]["h"]*=10
                bad[s][i]["l"]*=10
                bad[s][i]["c"]*=10
        updated=AsOfRegimes(bad).at(at)
        self.assertEqual(initial,updated)

    def test_pair_filter_and_risk_condition(self):
        good={
          "correlations":{"BTCUSDT_ETHUSDT":0.8,
                          "BTCUSDT_SOLUSDT":0.75,
                          "ETHUSDT_SOLUSDT":0.76},
          "minimumPairCorrelation":0.75,
          "trend4H":{s:"bullish" for s in SYMBOLS},
          "atrPercent4H":{"BTCUSDT":1.0,"ETHUSDT":1.3,"SOLUSDT":1.9}}
        self.assertTrue(gate_decision("THREE_CORR_AND_4H_ALIGNED","ETHUSDT","bullish",good))
        self.assertTrue(gate_decision("ETH_ATR_LE_1P5_BTC","ETHUSDT","bearish",good))
        self.assertFalse(gate_decision("THREE_CORR_AND_4H_ALIGNED","ETHUSDT","bearish",good))
        bad={**good,"atrPercent4H":{**good["atrPercent4H"],"ETHUSDT":2.1}}
        self.assertFalse(gate_decision("ETH_ATR_LE_1P5_BTC","ETHUSDT","bearish",bad))
        with self.assertRaisesRegex(ValueError,"MODE_NOT_AUTHORIZED"):
            gate_decision("BTC_SOL_4H_AGREE","ETHUSDT","bullish",good)

if __name__=="__main__":
    unittest.main()
