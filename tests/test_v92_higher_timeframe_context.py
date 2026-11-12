#!/usr/bin/env python3
"""V9.2 higher-timeframe watches: never look ahead or turn into orders."""
import unittest

from v92_higher_timeframe_context import (
    DAY, THREE_DAYS, higher_timeframe_context,
)

class HigherContextTests(unittest.TestCase):
    def bars(self, count=255, start=0):
        return [{
            "t": start + i*DAY,
            "o": 100+i*0.1,
            "h": 101+i*0.1,
            "l": 99+i*0.1,
            "c": 100.5+i*0.1,
            "v": 10+i
        } for i in range(count)]

    def test_all_three_coins_use_identical_daily_schema(self):
        d=self.bars()
        as_of=d[-1]["t"]+DAY
        for name in ("BTCUSDT","ETHUSDT","SOLUSDT"):
            with self.subTest(symbol=name):
                z=higher_timeframe_context(d,as_of)
                self.assertEqual(set(z),{"1D","3D"})
                self.assertEqual(z["1D"]["lastClosedCandleUTC"],
                                 "1970-09-13T00:00:00Z")
                self.assertTrue(z["3D"]["notVetoOrEntryFilter"])
                self.assertTrue(z["3D"]["exchangeNative3DParityNotProven"])
                self.assertLessEqual(
                    z["3D"]["closedCandlesAvailable"],len(d)//3+1)

    def test_partial_daily_rejected(self):
        d=self.bars()
        with self.assertRaisesRegex(ValueError,"PARTIAL_OR_FUTURE"):
            higher_timeframe_context(d,d[-1]["t"]+DAY-1)

    def test_gap_rejected(self):
        d=self.bars()
        d.pop(100)
        with self.assertRaisesRegex(ValueError,"DAILY_GAP"):
            higher_timeframe_context(d,d[-1]["t"]+DAY)

    def test_3day_only_completed_triplets_and_prior_close(self):
        d=self.bars(256)
        z=higher_timeframe_context(d,d[-1]["t"]+DAY)
        self.assertEqual(z["3D"]["closedCandlesAvailable"],85)
        self.assertEqual(z["3D"]["close"],d[254]["c"])
        self.assertEqual(z["3D"]["EMA50"]>0,True)
        self.assertTrue(z["3D"]["onlyFullyClosedCandlesUsed"])

if __name__=="__main__":
    unittest.main()
