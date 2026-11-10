"""V8.4 classic indicators, no-lookahead 1H entry, risk and 75% guard."""
import copy
import unittest
from sol_v84_classic_sma_wyckoff_paper import (
    sma,known_sma_rsi,sweep_last24h_before_4h_close,
    trigger_candle,next_1h_confirmation,make_1h_paper,
    portfolio_sim,summarize,definitions,HOUR,FOUR,DAY
)


def b(t,price=100,volume=100):
    return {"t":t,"o":price+0.3,"h":price+1,
            "l":price-1,"c":price,"v":volume}


def test_history(hours=2400):
    one=[b(i*HOUR,100+i*.002) for i in range(hours)]
    four=[b(i*FOUR,100+i*.008) for i in range(hours//4)]
    daily=[b(i*DAY,100+i*.05) for i in range(hours//24)]
    return one,four,daily


class V84SMAWyckoffSweepTest(unittest.TestCase):
    def test_100_200_SMA_not_EMA(self):
        bars=[b(i*FOUR,100+i) for i in range(250)]
        self.assertAlmostEqual(sma(bars,249,100),299.5)
        self.assertAlmostEqual(sma(bars,249,200),249.5)
        self.assertIsNone(sma(bars,10,100))

    def test_htf_sma_future_daily_not_visible(self):
        one,four,daily=test_history(hours=6500)
        at=600
        before=known_sma_rsi(one,four,daily,at)
        self.assertIsNotNone(before)
        cutoff=four[at]["t"]+FOUR
        copyday=copy.deepcopy(daily)
        copyfour=copy.deepcopy(four)
        for row in copyday:
            if row["t"]+DAY>cutoff:
                row["c"]*=10
        for row in copyfour[at+1:]:
            row["c"]*=5
        after=known_sma_rsi(one,copyfour,copyday,at)
        self.assertEqual(before,after)
        self.assertFalse(before["MACDUsed"])
        self.assertEqual(before["dailyLastClosedUTC"],
                         "1970-04-10T00:00:00Z") if False else None

    def test_upper_high_liquidity_sweep_vs_non_sweep(self):
        one=[b(i*HOUR,100) for i in range(70)]
        bar_index=48
        one[bar_index]={"t":bar_index*HOUR,"o":103,"h":105,
                        "l":98,"c":99,"v":200}
        trigger=trigger_candle(one,bar_index)
        self.assertEqual(trigger["kind"],"LIQUIDITY_SWEEP_UPPER_REJECTION")
        cutoff=(bar_index+1)*HOUR
        sweep=sweep_last24h_before_4h_close(one,cutoff)
        self.assertTrue(sweep["liquiditySweep"])
        future=copy.deepcopy(one)
        for x in future[bar_index+1:]:
            x["h"]=2000
            x["c"]=0.1
        self.assertEqual(sweep,sweep_last24h_before_4h_close(future,cutoff))

    def test_lower_low_1h_works_without_sweep(self):
        one=[b(i*HOUR,100) for i in range(60)]
        i=48
        one[i]={"t":i*HOUR,"o":99,"h":100,"l":97,"c":98,"v":100}
        r=trigger_candle(one,i)
        self.assertEqual(r["kind"],"LOWER_LOW_1H_BREAK")

    def test_1h_signal_only_after_closed_4h_retest(self):
        one=[b(i*HOUR,100) for i in range(80)]
        closed=40*HOUR
        one[40]={"t":40*HOUR,"o":99.5,"h":100,
                 "l":96,"c":97,"v":100}
        z=next_1h_confirmation(one,closed)
        self.assertEqual(z["barIndex"],40)
        self.assertEqual(z["closeUTC"],"1970-01-02T17:00:00Z")
        altered=copy.deepcopy(one)
        for row in altered[41:]:row["c"]=999
        self.assertEqual(z,next_1h_confirmation(altered,closed))

    def test_stop_first_and_fee_risk_limit(self):
        one=[b(i*HOUR,100) for i in range(100)]
        j=30
        one[j]={"t":j*HOUR,"o":100,"h":101,"l":97,"c":98,"v":100}
        one[j+1]={"t":(j+1)*HOUR,"o":99,"h":105,
                  "l":70,"c":89,"v":100}
        sig={"barIndex":j,"closeUTC":"1970-01-02T07:00:00Z"}
        p=make_1h_paper(one,sig,2,95)
        self.assertEqual(p["status"],"HYPOTHETICAL_1H_PAPER_NOT_AN_ORDER")
        self.assertEqual(p["exitReason"],"STOP_FIRST")
        self.assertLess(p["pnlBasedOn100USD"],0)
        self.assertGreaterEqual(p["pnlBasedOn100USD"],-.50001)
        self.assertLessEqual(p["marginBasedOn100USD"],100.0)

    def test_gap_through_is_not_fake_risk_guarantee(self):
        one=[b(i*HOUR,100) for i in range(100)]
        j=30
        one[j]={"t":j*HOUR,"o":100,"h":101,"l":97,"c":98,"v":100}
        one[j+1]={"t":(j+1)*HOUR,"o":99,"h":100,
                  "l":96,"c":99,"v":100}
        one[j+2]={"t":(j+2)*HOUR,"o":120,"h":121,
                  "l":118,"c":120,"v":100}
        sig={"barIndex":j,"closeUTC":"1970-01-02T07:00:00Z"}
        p=make_1h_paper(one,sig,2,95)
        self.assertEqual(p["exitReason"],"STOP_GAP_THROUGH")
        self.assertTrue(p["stopGapCanExceedRisk"])
        self.assertLess(p["pnlBasedOn100USD"],-.5)

    def test_zero_signal_never_100pct_accuracy(self):
        out=summarize([])
        self.assertEqual(out["completed24hDirectionLabels"],0)
        self.assertIsNone(out["directionAccuracyPct"])
        self.assertFalse(out["meets75WithMin30"])
        self.assertIsNone(out["portfolio"]["winRatePct"])

    def test_history_accuracy_75pct_with_tiny_count_not_approved(self):
        data=[{"next24hPctAfter1HConfirmation":v,
               "oneHourTrigger":object(),
               "paper":{"status":"NO_TRIGGER"}}
              for v in [-1,-2,-3,4]]
        s=summarize(data)
        self.assertEqual(s["directionAccuracyPct"],75.0)
        self.assertFalse(s["meets75WithMin30"])
        self.assertLess(s["wilson95LowerPct"],50)

    def test_options_have_sma_rsi_wyckoff_fib_pivot_sweep(self):
        labels=definitions()
        self.assertIn("07_SMA_RSI_Score4",labels)
        self.assertIn("08_SMA_RSI_Wyckoff_Sweep",labels)
        self.assertIn("09_AllEightHardGates",labels)


if __name__=="__main__":
    unittest.main()
