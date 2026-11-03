"""V8 Binance real Futures trade aggregation tests. Completely offline."""
import unittest
from io import BytesIO
from zipfile import ZipFile
from reconstruct_binance_oct28_raw_v8 import (
    aggregate_raw_zip,crosscheck_reconstruction,
)
from extend_binance_archive_october_v6 import day_bound


def csv_zip(day="2026-10-28",symbol="BTCUSDT",skip_hour=None,swapped=False):
    start,_=day_bound(day)
    lines=["id,price,qty,quote_qty,time,is_buyer_maker"]
    tid=1000
    for hour in range(24):
        if hour==skip_hour:continue
        for sec,price,qty in ((10,"101.00","2.25"),(23,"102.00","1.75")):
            lines.append(f"{tid},{price},{qty},5,{(start+hour*3600+sec)*1000},true")
            tid+=1
    if swapped:
        lines[1],lines[2]=lines[2],lines[1]
    f=BytesIO()
    with ZipFile(f,"w") as z:
        z.writestr(f"{symbol}-trades-{day}.csv","\n".join(lines)+"\n")
    return f.getvalue()


class TestRealTradeDerivedKlines(unittest.TestCase):
    def test_all_24_hours_real_trades_not_assumed(self):
        result,info=aggregate_raw_zip(csv_zip(),"BTCUSDT","2026-10-28")
        self.assertEqual(len(result),24)
        self.assertEqual(info["rawTrades"],48)
        self.assertEqual(result[0]["o"],101.0)
        self.assertEqual(result[0]["h"],102.0)
        self.assertEqual(result[0]["l"],101.0)
        self.assertEqual(result[0]["c"],102.0)
        self.assertAlmostEqual(result[0]["v"],4.0)

    def test_missing_hour_rejected(self):
        with self.assertRaisesRegex(ValueError,"Missing 1H"):
            aggregate_raw_zip(csv_zip(skip_hour=8),"BTCUSDT","2026-10-28")

    def test_disordered_trade_ids_rejected(self):
        with self.assertRaisesRegex(ValueError,"Non-increasing futures trade IDs"):
            aggregate_raw_zip(csv_zip(swapped=True),"BTCUSDT","2026-10-28")

    def test_crosscheck_to_actual_neighbor_klines_required(self):
        rows,_=aggregate_raw_zip(csv_zip(),"BTCUSDT","2026-10-28")
        check=crosscheck_reconstruction(rows,[dict(r) for r in rows],"BTCUSDT","2026-10-28")
        self.assertTrue(check["OHLCAllMatchPublishedBinanceKlines"])
        altered=[dict(r) for r in rows]
        altered[0]["h"]+=1
        with self.assertRaises(ValueError):
            crosscheck_reconstruction(rows,altered,"BTCUSDT","2026-10-28")

    def test_wrong_csv_symbol_rejected(self):
        with self.assertRaises(ValueError):
            aggregate_raw_zip(csv_zip(symbol="SOLUSDT"),"BTCUSDT","2026-10-28")


if __name__=="__main__":
    unittest.main()
