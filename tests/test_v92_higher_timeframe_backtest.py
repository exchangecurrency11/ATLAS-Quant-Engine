#!/usr/bin/env python3
"""Tests for causal 1D/3D higher-timeframe context and retest gate."""
import unittest
from collections import Counter

from v92_higher_timeframe_context import (
    DAY, context_at, higher_timeframe_context
)
from v92_higher_timeframe_backtest import make_gate


def daily_bars(count=255):
    return [{
        "t": i*DAY,
        "o": 100+i*.1,
        "h": 101+i*.1,
        "l": 99+i*.1,
        "c": 100.5+i*.1,
        "v": 100+i,
    } for i in range(count)]


class HigherTimeframeBacktestTests(unittest.TestCase):
    def test_intraday_context_excludes_unclosed_daily_and_3d(self):
        d=daily_bars(255)
        as_of=d[-1]["t"]+DAY-1
        c=context_at(d,as_of)
        self.assertEqual(c["closedDailyBars"],254)
        self.assertLessEqual(c["closed3DBars"],254//3)
        c2=context_at(d,d[-1]["t"]+DAY)
        self.assertEqual(c2["closedDailyBars"],255)
        self.assertGreaterEqual(c2["closed3DBars"],c["closed3DBars"])

    def test_mixed_or_opposing_daily_and_3d_rejects(self):
        # Gate is causal; use a deterministic monkey-free fake context by
        # constructing real daily candles whose recent trend is bearish.
        d=daily_bars(255)
        # Reverse the last 90 daily closes to force a downward EMA regime.
        for i in range(165,255):
            x=i-165
            d[i]={"t":i*DAY,"o":130-x*.2,"h":131-x*.2,
                  "l":129-x*.2,"c":129.5-x*.2,"v":200}
        audit=Counter()
        audit["dailyTrendCounts"]=Counter()
        audit["threeDayTrendCounts"]=Counter()
        gate,_=make_gate("SOLUSDT",[],d,candle_enabled=False,
                         daily_enabled=True,three_enabled=True,audit=audit)
        passed=gate([],{"side":"bullish"},{"t":254*DAY})
        self.assertFalse(passed["passed"])
        self.assertTrue(any("NOT_ALIGNED" in x for x in passed["reasons"]))

    def test_warmup_does_not_read_future_bars(self):
        d=daily_bars(100)
        c=context_at(d,99*DAY+DAY-1)
        self.assertEqual(c["closedDailyBars"],99)
        self.assertEqual(c["3D"],"insufficient")

if __name__=="__main__":
    unittest.main()
