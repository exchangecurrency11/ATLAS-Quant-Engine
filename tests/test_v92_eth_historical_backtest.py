#!/usr/bin/env python3
"""Offline integrity tests for official ETH Binance archive and V9.2 gates."""
import unittest
from collections import Counter

from download_binance_um_eth_history import build, month_start
from v92_eth_historical_backtest import _gate
from v92_higher_timeframe_context import DAY


class ETHArchiveTests(unittest.TestCase):
    def one_month(self):
        start=month_start("2024-10")
        return [{
            "t":start+i*3600,"o":100.0+i*.01,"h":101.0+i*.01,
            "l":99.0+i*.01,"c":100.5+i*.01,"v":10.0
        } for i in range(31*24)]

    def test_month_aggregates_exactly_to_4h_and_daily(self):
        data,counts,start,end=build(
            {("ETHUSDT","2024-10"):self.one_month()},
            "2024-10","2024-10")
        self.assertEqual(counts,{"1hour":744,"4hour":186,"daily":31})
        self.assertEqual(data["4hour"][0]["o"],data["1hour"][0]["o"])
        self.assertEqual(data["4hour"][0]["c"],data["1hour"][3]["c"])
        self.assertEqual(data["daily"][0]["c"],data["1hour"][23]["c"])
        self.assertEqual(end-start,31*DAY)

    def test_missing_hour_is_rejected(self):
        bars=self.one_month()
        bars.pop(400)
        with self.assertRaisesRegex(ValueError,"GAP_DUPLICATE"):
            build({("ETHUSDT","2024-10"):bars},"2024-10","2024-10")

    def test_duplicate_hour_is_rejected(self):
        bars=self.one_month()
        bars[400]=dict(bars[399])
        with self.assertRaisesRegex(ValueError,"GAP_DUPLICATE"):
            build({("ETHUSDT","2024-10"):bars},"2024-10","2024-10")


if __name__=="__main__":
    unittest.main()
