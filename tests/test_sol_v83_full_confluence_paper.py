"""V8.3 SOL research: timestamp, Wyckoff proxy and risk regression."""
import copy
import unittest
from sol_v83_full_confluence_paper import (
    causal_indicators,wyckoff_proxy,last_hour_rejection,
    paper_short_next4h,segment_summary,all_filters,SECS4,DAY
)


def b(t,p=100,vol=100):
    return {"t":t,"o":p+0.1,"h":p+1,"l":p-1,"c":p,"v":vol}


def data():
    four=[b(i*SECS4,100-0.035*i,100) for i in range(480)]
    daily=[b(i*DAY,100-0.3*i,800) for i in range(90)]
    return four,daily


class V83FullConfluenceTest(unittest.TestCase):
    def test_daily_does_not_see_incomplete_or_future_day(self):
        f,d=data()
        i=430
        current=causal_indicators(f,d,i)
        edited=copy.deepcopy(d)
        cutoff=f[i]["t"]+SECS4
        for row in edited:
            if row["t"]+DAY>cutoff:
                row["c"]=500
                row["h"]=600
        self.assertEqual(current,causal_indicators(f,edited,i))
        self.assertTrue(current["MACDFreeEMABear"])
        self.assertLessEqual(current["dailyBarClosedUTC"],"1970-04-01T00:00:00Z")

    def test_wyckoff_proxy_break_volume_and_lpsy_no_future(self):
        f,_=data()
        br,rt=435,437
        f[br]={"t":br*SECS4,"o":91,"h":92,"l":87,"c":87.3,"v":250}
        f[br-1]["h"]=96
        f[rt]={"t":rt*SECS4,"o":89.5,"h":90.5,"l":86,"c":87.2,"v":110}
        first=wyckoff_proxy(f,br,rt)
        self.assertTrue(first["wyckoffSOWProxy"])
        self.assertTrue(first["wyckoffLPSYProxy"])
        self.assertTrue(first["wyckoffCombined"])
        newer=copy.deepcopy(f)
        for row in newer[rt+1:]:
            row["c"]*=100
            row["v"]*=100
        self.assertEqual(first,wyckoff_proxy(newer,br,rt))

    def test_last_1h_close_is_exact_end_of_4h_candle(self):
        f,_=data()
        i=435
        candle=f[i]
        start=candle["t"]
        hours=[
          {"t":start+j*3600,"o":candle["o"],"h":candle["h"],
           "l":candle["l"],"c":candle["c"]+(2-j)*.04,"v":100}
          for j in range(4)]
        hours[-2]["c"]=candle["c"]+.3
        hours[-1]["o"]=hours[-1]["c"]+.3
        hours[-1]["c"]=candle["c"]
        z=last_hour_rejection(hours,f,i)
        self.assertEqual(z["last1hClosedUTC"],"1970-03-14T16:00:00Z")
        self.assertTrue(z["hourlyBearishClose"])
        self.assertTrue(z["allFourConstituentsVerified"])
        with self.assertRaisesRegex(ValueError,"MISSING"):
            last_hour_rejection(hours[:3],f,i)

    def test_stop_and_target_same_4h_candle_resolves_stop_first(self):
        four,_=data()
        i=430
        four[i+1]={"t":four[i+1]["t"],"o":88,"h":110,
                   "l":50,"c":91,"v":100}
        event={"boxHigh":90}
        paper=paper_short_next4h(four,event,i,2)
        self.assertEqual(paper["status"],"ILLUSTRATIVE_PAPER_ONLY")
        self.assertEqual(paper["reason"],"STOP_FIRST")
        self.assertLess(paper["netPnLUSDT"],0)
        self.assertGreaterEqual(paper["netPnLUSDT"],-.500001)
        self.assertLessEqual(paper["marginUSDT"],100)

    def test_gap_stop_flag_does_not_fake_guaranteed_risk(self):
        four,_=data()
        i=430
        four[i+1]={"t":four[i+1]["t"],"o":88,"h":89,"l":85,"c":88,"v":100}
        four[i+2]={"t":four[i+2]["t"],"o":103,"h":105,"l":90,"c":95,"v":100}
        paper=paper_short_next4h(four,{"boxHigh":90},i,2)
        self.assertEqual(paper["reason"],"STOP_GAP_THROUGH")
        self.assertTrue(paper["gapsCanExceedPlannedRisk"])
        self.assertLess(paper["netPnLUSDT"],-.5)

    def test_all_eight_flags_are_included(self):
        inputs={key:True for key in [
            "Fibonacci","PreviousDayPivot","RSI14_Daily4H",
            "EMA20_50_Daily4H","WyckoffSOW_LPSYProxy",
            "OrderBlock_4H","BreakHighVolume","LastClosed1HRejection"]}
        row={"features":inputs,"confluenceScore8":8,
             "aux":{"FVG_4H":False},"future24hPct":-2.0,
             "paperNext4H":None}
        filters=all_filters()
        self.assertTrue(filters["11_AllEightMandatory"](row))
        self.assertTrue(filters["12_Score4of8"](row))
        self.assertTrue(filters["15_Trend_Wyckoff_Fib"](row))
        stats=segment_summary([row],filters["11_AllEightMandatory"])
        self.assertEqual(stats["directionHitPct"],100.0)
        self.assertEqual(stats["answered24h"],1)
        self.assertFalse(stats["meets75With30"])
        self.assertLess(stats["wilson95LowerPct"],50)


if __name__=="__main__":
    unittest.main()
