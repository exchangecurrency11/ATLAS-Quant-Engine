"""Offline SOL derivative-data audit regression; no private market data or broker orders."""
import unittest
from datetime import datetime,timezone
from sol_derivatives_quality_audit import (parse_metrics,parse_kline,
                                           verify_granularity,summarize_holes,unix,FIVE)

DAY="2026-11-09"
T=unix(DAY+"T00:00:00Z")
HEAD=["create_time","symbol","sum_open_interest","sum_open_interest_value",
      "count_toptrader_long_short_ratio","sum_toptrader_long_short_ratio",
      "count_long_short_ratio","sum_taker_long_short_vol_ratio"]


class DerivativeQualityTests(unittest.TestCase):
    def test_oi_is_sparse_without_fake_ffill(self):
        rows=[HEAD,
              ["2026-11-09 00:00:00","SOLUSDT","123","1300","1","1","1","0.8"],
              ["2026-11-09 00:10:00","SOLUSDT","124","1301","1","1","1","0.9"]]
        data,invalid,expected=parse_metrics(rows,DAY)
        self.assertEqual(expected,288)
        self.assertEqual(len(data),2)
        self.assertEqual(data[T]["availableAfterUTC"],"2026-11-09T00:05:00Z")
        self.assertNotIn(T+FIVE,data)
        holes=summarize_holes(data,T,FIVE,expected)
        self.assertEqual(holes["missingCount"],286)

    def test_bad_symbols_and_zero_oi_fail_closed(self):
        rows=[HEAD,["2026-11-09 00:00:00","ETHUSDT","123","1300","1","1","1","1"],
              ["2026-11-09 00:05:00","SOLUSDT","0","0","1","1","1","1"]]
        data,errors,_=parse_metrics(rows,DAY)
        self.assertEqual(len(data),0)
        self.assertEqual(errors["NONPOSITIVE_OI"],1)
        self.assertEqual(errors["MALFORMED_ROW"],1)

    def test_5min_taker_buy_plus_sell_equals_total_and_hourly_match(self):
        hour=[["open_time","open","high","low","close","volume","close_time",
               "quote_volume","count","taker_buy_volume","taker_buy_quote_volume","ignore"],
              [str(T*1000),"100","102","98","100","1200",str((T+3600)*1000-1),
               "120000","120","600","60000","0"]]
        five=[hour[0]]
        for i in range(12):
            t=T+i*FIVE
            five.append([str(t*1000),"100","102","98","100","100",
                         str((t+FIVE)*1000-1),"10000","10","50","5000","0"])
        h,invalid,_=parse_kline(hour,DAY,"1h")
        f,invalid2,_=parse_kline(five,DAY,"5m")
        self.assertEqual(invalid,{})
        self.assertEqual(invalid2,{})
        report=verify_granularity(h,f)
        self.assertEqual(report["testedHours"],1)
        self.assertEqual(report["mismatchHours"],0)
        f.pop(T+FIVE)
        self.assertEqual(verify_granularity(h,f)["hourlyBarsMissing5mInput"],1)

    def test_taker_buy_gt_volume_is_rejected(self):
        rows=[["open_time","open","high","low","close","volume","close_time",
               "quote_volume","count","taker_buy_volume","taker_buy_quote_volume","ignore"],
              [str(T*1000),"100","101","99","100","200",str((T+3600)*1000-1),
               "20000","10","220","20000","0"]]
        bars,bad,_=parse_kline(rows,DAY,"1h")
        self.assertEqual(len(bars),0)
        self.assertEqual(bad["MALFORMED_ROW"],1)


if __name__=="__main__":
    unittest.main()
