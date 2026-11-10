"""V8 side-safe HTF EMA cache and V7 BOS-only ablation controls."""
import unittest
from backtest_retest_long_v4 import indicators
from v8_three_asset_confluence_backtest import make_gates, metrics, iso


def trending_bars(tf_seconds,count,up_per_bar):
    return [{"t":i*tf_seconds,"o":200+i*up_per_bar-0.5,
             "h":200+i*up_per_bar+1,"l":200+i*up_per_bar-1,
             "c":200+i*up_per_bar,"v":100} for i in range(count)]


class FilterAblationTests(unittest.TestCase):
    def test_higher_timeframe_ema_cache_must_be_direction_specific(self):
        day=trending_bars(86400,220,0.10)
        four=trending_bars(14400,1320,0.025)
        ts=219*86400+3600
        bars=[]
        for i in range(250):
            t=ts-250*3600+i*3600
            c=100+i*0.2
            bars.append({"t":t,"o":c-0.1,"h":c+0.5,"l":c-0.5,
                         "c":c,"v":100})
        ind=indicators(bars)
        self.assertIsNotNone(ind)
        gate,_,_=make_gates(four,day)
        bullish=gate(bars,{"event":"BOS","direction":"bullish",
                           "brokenLevel":bars[-1]["c"]-1,
                           "at":bars[-1]["t"]},ind)
        bearish=gate(bars,{"event":"BOS","direction":"bearish",
                           "brokenLevel":bars[-1]["c"]+1,
                           "at":bars[-1]["t"]},ind)
        self.assertEqual(bullish["features"]["emaTrendScore4Votes"],4)
        self.assertEqual(bearish["features"]["emaTrendScore4Votes"],0)
        bullish_again=gate(bars,{"event":"BOS","direction":"bullish",
                           "brokenLevel":bars[-1]["c"]-1,
                           "at":bars[-1]["t"]},ind)
        self.assertEqual(bullish_again["features"]["emaTrendScore4Votes"],4)

    def test_empty_ablation_has_no_winrate(self):
        sample=metrics([],0,3600)
        self.assertEqual(sample["trades"],0)
        self.assertIsNone(sample["winRatePct"])
        self.assertEqual(sample["netPnLUSDT"],0)

    def test_retrospective_trade_times_count_only_after_entry(self):
        start=10*3600
        trade={"entryOpenUTC":start+3600,
               "exitKnownUTC":start+7200,
               "entry":100,"stop":99,
               "side":"bullish","netRIllustrative":1.0,
               "exitReason":"TP"}
        earlier=metrics([trade],0,start+1)
        later=metrics([trade],start+1,start+10800)
        self.assertEqual(earlier["trades"],0)
        self.assertEqual(later["trades"],1)


if __name__=="__main__":
    unittest.main()
