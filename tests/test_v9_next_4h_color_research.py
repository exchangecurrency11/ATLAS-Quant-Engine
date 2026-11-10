"""V9 literal next-4H own open-close GREEN/RED, 5m pre-start, no leak."""
import copy
from datetime import datetime,timezone
import math
import unittest

from download_binance_um_history import aggregate,month_start
from v9_next_4h_color_research import (
    SYMBOLS,HOUR,FOUR,DAY,LEAD_SECONDS,label_next_candle,
    prepare,features_at,observations,results,FOLDS,ts
)


def mock_data(days=241):
    start=month_start("2023-01")
    out={}
    for symbol,k in (("BTCUSDT",1.),("ETHUSDT",.2),("SOLUSDT",.05)):
        one=[]
        for i in range(days*24):
            t=start+i*HOUR
            op=(100+i*.005+math.sin(i/6)*.5)*k
            c=(100+(i+1)*.005+math.sin((i+1)/6)*.5)*k
            h=max(op,c)+.2*k
            l=min(op,c)-.2*k
            v=100+i%7
            tbv=v*(.5+.1*math.sin(i/13))
            one.append({"t":t,"o":op,"h":h,"l":l,"c":c,"v":v,
                        "qv":v*(op+c)/2,"trades":10+i%7,
                        "tbv":tbv,"tbq":tbv*(op+c)/2})
        out[symbol]={"one":one,"four":aggregate(one,FOUR),
                     "daily":aggregate(one,DAY)}
    return out


class V9GreenRedStrictTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw=mock_data()
        cls.prepared=prepare(cls.raw)

    def test_target_is_OWN_OPEN_CLOSE_not_previous_close(self):
        self.assertEqual(label_next_candle({"o":100,"c":101}),1)
        self.assertEqual(label_next_candle({"o":100,"c":99}),0)
        self.assertIsNone(label_next_candle({"o":100,"c":100}))

    def test_real_prediction_is_5_minutes_BEFORE_target_start(self):
        i=6*225
        t=self.raw["SOLUSDT"]["four"][i]["t"]
        self.assertEqual(t%FOUR,0)
        self.assertEqual((t-(t-LEAD_SECONDS)),300)
        v=features_at("SOLUSDT",self.prepared,i)
        self.assertIsNotNone(v)
        self.assertTrue(all(math.isfinite(x) for x in v))
        self.assertGreater(len(v),20)

    def test_unfinished_4H_and_target_all_prices_cannot_leak(self):
        i=6*225
        baseline=features_at("SOLUSDT",self.prepared,i)
        future=copy.deepcopy(self.raw)
        t=future["SOLUSDT"]["four"][i]["t"]
        h_idx=(t-future["SOLUSDT"]["one"][0]["t"])//HOUR
        # At T-5min the final 1H bar of current 4H is NOT closed;
        # also all future 4H candle bars are UNKNOWN.
        for k in range(h_idx-1,len(future["SOLUSDT"]["one"])):
            one=future["SOLUSDT"]["one"][k]
            one["o"]=one["c"]=one["h"]=one["l"]=one["o"]*2
            one["v"]*=10
            one["qv"]*=20
            one["tbv"]=one["v"]*.9
            one["tbq"]=one["qv"]*.9
            one["trades"]*=9
        future["SOLUSDT"]["four"]=aggregate(future["SOLUSDT"]["one"],FOUR)
        future["SOLUSDT"]["daily"]=aggregate(future["SOLUSDT"]["one"],DAY)
        changed=features_at("SOLUSDT",prepare(future),i)
        self.assertEqual(baseline,changed)

    def test_last_completed_hour_can_change_snapshot(self):
        i=6*225
        baseline=features_at("SOLUSDT",self.prepared,i)
        fresh=copy.deepcopy(self.raw)
        t=fresh["SOLUSDT"]["four"][i]["t"]
        ix=(t-fresh["SOLUSDT"]["one"][0]["t"])//HOUR-2
        x=fresh["SOLUSDT"]["one"][ix]
        x["o"]=x["c"]=x["h"]=x["l"]=x["c"]*.9
        x["v"]*=1.2
        x["tbv"]*=1.2
        x["qv"]*=1.2
        x["tbq"]*=1.2
        fresh["SOLUSDT"]["four"]=aggregate(fresh["SOLUSDT"]["one"],FOUR)
        fresh["SOLUSDT"]["daily"]=aggregate(fresh["SOLUSDT"]["one"],DAY)
        affected=features_at("SOLUSDT",prepare(fresh),i)
        self.assertNotEqual(baseline,affected)

    def test_close_only_daily_even_at_00utc(self):
        i=6*225
        t=self.prepared["BTCUSDT"]["four"][i]["t"]
        self.assertEqual(t%DAY,0)
        d=self.prepared["BTCUSDT"]["daily"]
        last_full=max(j for j,z in enumerate(d) if z["t"]+DAY<=t-300)
        self.assertEqual(d[last_full]["t"]+DAY,t-DAY)

    def test_all_three_assets_same_4h_targets(self):
        obs,doji=observations(self.prepared)
        self.assertEqual(set(obs),set(SYMBOLS))
        self.assertTrue(obs["SOLUSDT"])
        for symbol in SYMBOLS:
            self.assertTrue(all(
                ts(o["decisionUTC"])+300==o["t"]
                and ts(o["targetStartUTC"])==o["t"]
                and ((o["actualClose"]>o["actualOpen"])==bool(o["y"]))
                for o in obs[symbol]))
            self.assertTrue(all(o["t"]%FOUR==0 for o in obs[symbol]))

    def test_zero_high_confidence_is_not_false_100pct(self):
        cases=[{"modelPgreen":.51,"y":1},{"modelPgreen":.49,"y":0}]
        z=results(cases,"modelPgreen",.65)
        self.assertEqual(z["predictions"],0)
        self.assertIsNone(z["hitRatePct"])
        self.assertFalse(z["userGoal75Observed"])

    def test_six_folds_are_chronological_and_not_randomized(self):
        folds=[(ts(a),ts(b)) for _,a,b in FOLDS]
        self.assertEqual(len(folds),6)
        self.assertTrue(all(a<b for a,b in folds))
        self.assertTrue(all(a1==b0 for (_,b0),(a1,_) in zip(folds,folds[1:])))


if __name__=="__main__":
    unittest.main()
