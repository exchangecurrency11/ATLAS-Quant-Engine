"""V7 safety tests: exact Futures 28 Oct UTC gap, never substitute spots or interpolation."""
from datetime import datetime, timezone
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from recover_binance_oct28_fapi_v7 import (
    GAP_DAY, get_gap_api, validate_fapi_klines,
    recover_series,
)
from extend_binance_archive_october_v6 import days_inclusive, day_bound


def kline_data(date=GAP_DAY):
    begin,_=day_bound(date)
    out=[]
    for hour in range(24):
        openms=(begin+hour*3600)*1000
        out.append([openms,"100","103","99","101","12",openms+3600000-1,
                    "1212",42,"5","505","0"])
    return out


class TestMissingBinanceDayRecovery(unittest.TestCase):
    def test_real_futures_api_response_only_24_closed_milliseconds(self):
        rows=validate_fapi_klines(kline_data(),"BTCUSDT",GAP_DAY)
        self.assertEqual(len(rows),24)
        self.assertEqual(rows[0]["t"],1793145600)
        self.assertEqual(rows[-1]["t"],1793228400)
        self.assertEqual(rows[0]["h"],103.0)

    def test_gap_is_fatal(self):
        data=kline_data()
        with self.assertRaises(ValueError):
            validate_fapi_klines(data[:12]+data[13:],"BTCUSDT",GAP_DAY)

    def test_duplicate_1h_is_fatal(self):
        data=kline_data()
        data[10]=data[9][:]
        with self.assertRaises(ValueError):
            validate_fapi_klines(data,"BTCUSDT",GAP_DAY)

    def test_close_time_must_be_exact(self):
        data=kline_data()
        data[13][6]+=100
        with self.assertRaises(ValueError):
            validate_fapi_klines(data,"BTCUSDT",GAP_DAY)

    def test_invalid_price_is_fatal(self):
        data=kline_data()
        data[0][2]="99"
        with self.assertRaises(ValueError):
            validate_fapi_klines(data,"BTCUSDT",GAP_DAY)

    def test_only_missing_day_and_futures_symbols(self):
        with self.assertRaises(ValueError):
            get_gap_api("ETHUSDT")
        with self.assertRaises(ValueError):
            get_gap_api("BTCUSDT","2026-10-29")

    def test_base_october_continuity_blocks_gaps(self):
        base_start=day_bound("2026-09-30")[0]
        originals=[{"symbol":sym+"_PERP.A",
                    "history":[{"t":base_start+i*3600,
                                "o":100,"h":101,"l":99,"c":100,"v":1}
                                for i in range(24)]}
                   for sym in ("BTCUSDT","SOLUSDT")]
        days=days_inclusive("2026-10-01","2026-11-02")
        extra={(sym,day):[{"t":day_bound(day)[0]+i*3600,
                           "o":100,"h":101,"l":99,"c":100,"v":1} for i in range(24)]
               for sym in ("BTCUSDT","SOLUSDT") for day in days}
        output=recover_series(originals,extra,days)
        self.assertEqual(len(output[("BTCUSDT","1hour")]),24+33*24)
        self.assertEqual(len(output[("SOLUSDT","daily")]),34)
        extra[("BTCUSDT","2026-10-28")][12]["t"]+=3600
        with self.assertRaises(ValueError):
            recover_series(originals,extra,days)


if __name__=="__main__":
    unittest.main()
