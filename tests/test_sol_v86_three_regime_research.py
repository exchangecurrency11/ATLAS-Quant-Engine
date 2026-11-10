"""SOL V8.6 invariant tests: no post-close leak, true 1H/4H, three-state risk."""
import copy
import unittest
from sol_v86_three_regime_research import (
    HOUR,FOUR,DAY,regime_at_close,last_four_1h,features,
    scan_daily_checkpoints,summarize,
)
from download_binance_um_history import aggregate

def bar(t,p=80.0):
    return {"t":t,"o":p,"h":p+.6,"l":p-.6,"c":p,"v":100.0}

def sample(n_days=230):
    one=[bar(i*HOUR,80.0-.005*(i//24)) for i in range(n_days*24)]
    four=aggregate(one,FOUR)
    daily=aggregate(one,DAY)
    return one,four,daily

def synthetic_prepared(four,daily,i,frsi=28,drsi=28,side="BEAR"):
    # Synthetic, closed-only indicators explicitly fed to classification
    p={"four":{"s100":[None]*len(four),"s200":[None]*len(four),
               "rsi":[None]*len(four)},
       "daily":{"s100":[None]*len(daily),"s200":[None]*len(daily),
                "rsi":[None]*len(daily)}}
    for k in range(len(four)):
        p["four"]["s100"][k]=(four[i]["c"]+5 if side=="BEAR" else four[i]["c"]-5)
        p["four"]["s200"][k]=(four[i]["c"]+10 if side=="BEAR" else four[i]["c"]-10)
        p["four"]["rsi"][k]=frsi
    for k in range(len(daily)):
        p["daily"]["s100"][k]=(daily[k]["c"]+5 if side=="BEAR" else daily[k]["c"]-5)
        p["daily"]["s200"][k]=(daily[k]["c"]+7 if side=="BEAR" else daily[k]["c"]-7)
        p["daily"]["rsi"][k]=drsi
    return p


class V86RegimeTests(unittest.TestCase):
    def test_exact_1h_four_bar_ohlcv(self):
        one,four,_=sample()
        i=1300
        self.assertEqual(len(last_four_1h(one,four[i])),4)
        wrong=copy.deepcopy(four[i])
        wrong["v"]+=1
        with self.assertRaisesRegex(ValueError,"CONSTITUENT_OHLCV"):
            last_four_1h(one,wrong)

    def test_oversold_not_blind_short(self):
        one,four,daily=sample()
        i=1295
        model=synthetic_prepared(four,daily,i,frsi=25,drsi=27)
        result=regime_at_close(one,four,daily,i,model)
        self.assertEqual(result["label"],"OVERSOLD_BOUNCE_RISK")
        self.assertIsNone(result["side"])

    def test_upward_closed_1h_rejection_creates_only_bounce_candidate(self):
        one,four,daily=sample()
        i=1295
        j=i*4+3
        prior=one[j-1]["h"]
        one[j]={"t":one[j]["t"],"o":prior-1.5,
                "h":prior+1.4,"l":prior-2.0,
                "c":prior+0.8,"v":150.0}
        four[i]=aggregate(one[i*4:i*4+4],FOUR)[0]
        # aggregate input time aligned with global 4H
        model=synthetic_prepared(four,daily,i,frsi=25,drsi=28)
        result=regime_at_close(one,four,daily,i,model)
        self.assertEqual(result["label"],"RELIEF_BOUNCE_LONG")
        self.assertEqual(result["side"],"LONG")
        self.assertTrue(result["micro"]["1HBullBOS"])

    def test_4h_close_today_does_not_use_undone_daily(self):
        one,four,daily=sample()
        i=1295
        before=regime_at_close(one,four,daily,i,synthetic_prepared(four,daily,i))
        newer=copy.deepcopy(daily)
        cutoff=four[i]["t"]+FOUR
        for b in newer:
            if b["t"]+DAY>cutoff:
                b["c"]=100000
        after=regime_at_close(one,four,newer,i,synthetic_prepared(four,newer,i))
        self.assertEqual(before["label"],after["label"])
        self.assertEqual(before["latestCompleteDailyUTC"],after["latestCompleteDailyUTC"])
        self.assertEqual(before["dailyClose"],after["dailyClose"])

    def test_future_1h_candles_cannot_repaint_decision(self):
        one,four,daily=sample()
        i=1295
        frozen=regime_at_close(one,four,daily,i,synthetic_prepared(four,daily,i))
        modified_one=copy.deepcopy(one)
        for candle in modified_one[(i+1)*4:]:
            candle["h"]*=100
            candle["c"]*=2
        observed=regime_at_close(modified_one,four,daily,i,synthetic_prepared(four,daily,i))
        self.assertEqual(frozen,observed)

    def test_one_anchor_per_day_and_disjoint_24h_outcomes(self):
        one,four,daily=sample()
        rows,_=scan_daily_checkpoints(one,four,daily)
        self.assertTrue(rows)
        from datetime import datetime,timezone
        for row in rows:
            stamp=datetime.fromisoformat(row["decisionKnownUTC"].replace("Z","+00:00"))
            self.assertEqual(stamp.hour,20)
        for before,after in zip(rows,rows[1:]):
            a=datetime.fromisoformat(before["decisionKnownUTC"].replace("Z","+00:00"))
            b=datetime.fromisoformat(after["decisionKnownUTC"].replace("Z","+00:00"))
            self.assertGreaterEqual((b-a).total_seconds(),86400)

    def test_no_events_and_tiny_75pct_no_success_claim(self):
        empty=summarize([])
        self.assertIsNone(empty["hitRate24hPct"])
        self.assertEqual(empty["abstentions"],0)
        mini=[{"side":"LONG","label":"TREND_CONTINUATION_LONG",
               "correct24hDirection":v,"correctNext4hDirection":v}
              for v in [True,True,True,False]]
        result=summarize(mini)
        self.assertEqual(result["hitRate24hPct"],75.0)
        self.assertFalse(result["min30Signals"])
        self.assertLess(result["wilson95LowerPct"],50)

if __name__=="__main__":
    unittest.main()
