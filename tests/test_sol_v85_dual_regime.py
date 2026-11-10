"""V8.5: causality, abstain, symmetric LONG/SHORT 1H confirmation and risk."""
import copy
import unittest
from sol_v85_dual_regime_research import (
    rolling_sma,rolling_rsi14,trigger,first_1h_confirm_index,
    simulate_trade,broad_box,features_at_4h_close,
    scan,score,HOUR,FOUR,DAY)


def bar(t,o=100,h=102,l=98,c=100,v=100):
    return {"t":t,"o":o,"h":h,"l":l,"c":c,"v":v}


def history(days=225,trend="UP"):
    one=[]
    four=[]
    daily=[]
    for d in range(days):
        for j in range(24):
            i=d*24+j
            price=100+.20*d if trend=="UP" else 160-.20*d
            one.append(bar(i*HOUR,price,price+1,price-1,price,100))
        for j in range(6):
            i=d*6+j
            price=100+.20*d if trend=="UP" else 160-.20*d
            four.append(bar(i*FOUR,price,price+1,price-1,price,100))
        p=100+.20*d if trend=="UP" else 160-.20*d
        daily.append(bar(d*DAY,p,p+1,p-1,p,600))
    return one,four,daily


class V85Tests(unittest.TestCase):
    def test_sma_is_simple_not_exponential(self):
        v=list(range(1,300))
        m=rolling_sma(v,200)
        self.assertIsNone(m[198])
        self.assertAlmostEqual(m[199],100.5)
        self.assertAlmostEqual(m[-1],199.5)

    def test_rsi_wilder_has_no_future_access(self):
        a=[100+i for i in range(60)]
        b=a[:20]+[500]*40
        orig=rolling_rsi14(a)
        altered=rolling_rsi14(b)
        self.assertEqual(orig[:20],altered[:20])
        self.assertGreater(orig[18],99)

    def test_bear_and_bull_1h_bos(self):
        rows=[bar(i*HOUR) for i in range(60)]
        k=35
        rows[k]=bar(k*HOUR,99.5,100,90,91)
        short=trigger(rows,k,"SHORT")
        self.assertIsNotNone(short)
        self.assertEqual(short["kind"],"BOS")
        rows[k]=bar(k*HOUR,101,110,100,109)
        long=trigger(rows,k,"LONG")
        self.assertIsNotNone(long)
        self.assertEqual(long["kind"],"BOS")

    def test_reversal_sweep_1h_symmetry(self):
        rows=[bar(i*HOUR) for i in range(60)]
        k=35
        rows[k]=bar(k*HOUR,98,100,95,99.8)
        up=trigger(rows,k,"LONG")
        self.assertEqual(up["kind"],"SWEEP")
        rows[k]=bar(k*HOUR,102,105,99,99.5)
        down=trigger(rows,k,"SHORT")
        self.assertEqual(down["kind"],"SWEEP")

    def test_signal_is_only_after_4h_close_and_from_next1h(self):
        rows=[bar(i*HOUR) for i in range(80)]
        rows[40]=bar(40*HOUR,100,103,100,102.5)
        sig=first_1h_confirm_index(rows,40,"LONG")
        self.assertEqual(sig["index"],40)
        self.assertEqual(sig["closedUTC"],"1970-01-02T17:00:00Z")
        perturbed=copy.deepcopy(rows)
        for v in perturbed[41:]:
            v["o"]=500
            v["c"]=1000
        self.assertEqual(sig,first_1h_confirm_index(perturbed,40,"LONG"))

    def test_risk_stop_first_short_and_long(self):
        one=[bar(i*HOUR) for i in range(80)]
        j=30
        one[j]=bar(j*HOUR,99.9,100.5,97,98)
        one[j+1]=bar((j+1)*HOUR,99,104,60,70)
        signal={"index":j,"closedUTC":"1970-01-02T07:00:00Z"}
        result=simulate_trade(one,signal,"SHORT",2)
        self.assertEqual(result["status"],"COMPLETE_PAPER_NOT_FILLED")
        self.assertEqual(result["exitReason"],"STOP_FIRST")
        self.assertGreaterEqual(result["paperNetUSDT"],-.50001)
        one[j]=bar(j*HOUR,99.9,103,98,102)
        one[j+1]=bar((j+1)*HOUR,101,145,70,100)
        result=simulate_trade(one,signal,"LONG",2)
        self.assertEqual(result["exitReason"],"STOP_FIRST")
        self.assertGreaterEqual(result["paperNetUSDT"],-.50001)

    def test_stop_gap_may_exceed_planned_risk(self):
        one=[bar(i*HOUR) for i in range(80)]
        j=30
        one[j]=bar(j*HOUR,99.9,100.5,97,98)
        one[j+1]=bar((j+1)*HOUR,99,100,98,99)
        one[j+2]=bar((j+2)*HOUR,120,122,119,120)
        signal={"index":j,"closedUTC":"1970-01-02T07:00:00Z"}
        x=simulate_trade(one,signal,"SHORT",2)
        self.assertEqual(x["exitReason"],"STOP_GAP")
        self.assertTrue(x["gapThroughStopCanLoseMoreThanPlannedRisk"])
        self.assertLess(x["paperNetUSDT"],-.5)

    def test_higher_timeframe_data_future_invariant(self):
        one,four,daily=history(240,trend="UP")
        i=221*6
        fprices=[x["c"] for x in four]
        dprices=[x["c"] for x in daily]
        args=[rolling_sma(fprices,100),rolling_sma(fprices,200),
              rolling_rsi14(fprices),
              rolling_sma(dprices,100),rolling_sma(dprices,200),
              rolling_rsi14(dprices)]
        baseline=features_at_4h_close(one,four,daily,i,*args)
        newer=copy.deepcopy(daily)
        current_close=four[i]["t"]+FOUR
        for b in newer:
            if b["t"]+DAY>current_close:b["c"]*=10
        dailyclose=[x["c"] for x in newer]
        newer_args=args[:3]+[rolling_sma(dailyclose,100),
                              rolling_sma(dailyclose,200),
                              rolling_rsi14(dailyclose)]
        updated=features_at_4h_close(one,four,newer,i,*newer_args)
        self.assertEqual(baseline,updated)
        self.assertIn(baseline["status"],("CANDIDATE","ABSTAIN_MIXED_SMA_REGIME"))
        if baseline["status"]=="CANDIDATE":
            self.assertLessEqual(baseline["previousDayPivotClosedUTC"],baseline["asOfUTC"])

    def test_empty_events_no_fabricated_75pct(self):
        x=score([])
        self.assertIsNone(x["directionHitRatePct"])
        self.assertFalse(x["observedTarget75"])
        self.assertFalse(x["atLeast30Events"])

    def test_75pct_from_4_not_validated(self):
        rows=[{"side":"LONG","directional24HHit":i<3,
               "paper":{"status":"SKIP_STOP_INVALID"}} for i in range(4)]
        x=score(rows)
        self.assertEqual(x["directionHitRatePct"],75)
        self.assertTrue(x["observedTarget75"])
        self.assertFalse(x["atLeast30Events"])
        self.assertLess(x["wilson95LowerPct"],50)


if __name__=="__main__":
    unittest.main()
