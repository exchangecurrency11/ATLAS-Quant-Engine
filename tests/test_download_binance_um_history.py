"""Offline tests for Binance UM monthly archive + 4H/1D UTC resampling."""
from datetime import datetime, timezone
from io import BytesIO
from zipfile import ZipFile, ZIP_DEFLATED
import unittest

from download_binance_um_history import (
    aggregate, build, months_inclusive, month_start, month_end, parse_zip,
    SYMBOLS,
)


def utc(t):
    return int(datetime.fromisoformat(t).replace(tzinfo=timezone.utc).timestamp())


def synthetic(symbol, month, *, skip_index=None, shift_end=False):
    start,end=month_start(month),month_end(month)
    buf=BytesIO()
    with ZipFile(buf,"w",compression=ZIP_DEFLATED) as z:
        text=[]
        for i,t in enumerate(range(start,end,3600)):
            if i==skip_index: continue
            o,c=100+i/1000,100.05+i/1000
            h,l=c+0.1,o-0.1
            qv=123*(o+c)/2
            tbv=60.
            tbq=tbv*(o+c)/2
            text.append(f"{t*1000},{o},{h},{l},{c},123,{(t+3600)*1000-1},{qv},11,{tbv},{tbq},0")
        z.writestr(f"{symbol}-1h-{month}.csv","\n".join(text)+"\n")
    return buf.getvalue()


class ArchiveTests(unittest.TestCase):
    def test_monthly_contract_and_1h_continuity(self):
        b=synthetic("BTCUSDT","2025-02")
        candles=parse_zip(b,symbol="BTCUSDT",month="2025-02")
        self.assertEqual(len(candles),672)
        self.assertEqual(candles[0]["t"],utc("2025-02-01T00:00:00"))
        self.assertEqual(candles[-1]["t"],utc("2025-02-28T23:00:00"))

    def test_quote_taker_and_number_trades_retained(self):
        b=synthetic("SOLUSDT","2025-02")
        result=parse_zip(b,symbol="SOLUSDT",month="2025-02")
        a=result[0]
        self.assertEqual(a["trades"],11)
        self.assertAlmostEqual(a["tbv"],60)
        self.assertAlmostEqual(a["tbq"]/a["tbv"],(a["o"]+a["c"])/2)
        self.assertAlmostEqual(a["qv"]/a["v"],(a["o"]+a["c"])/2)
        agg4=aggregate(result[:4],14400)[0]
        self.assertEqual(agg4["trades"],44)
        self.assertAlmostEqual(agg4["tbv"],240)
        self.assertAlmostEqual(agg4["qv"],sum(x["qv"] for x in result[:4]))
        aggD=aggregate(result[:24],86400)[0]
        self.assertEqual(aggD["trades"],264)

    def test_reject_taker_field_greater_than_total_volume(self):
        month="2025-02"
        b=synthetic("SOLUSDT",month)
        from zipfile import ZipFile,ZIP_DEFLATED
        from io import BytesIO
        with ZipFile(BytesIO(b)) as archive:
            rows=archive.read("SOLUSDT-1h-"+month+".csv").decode().splitlines()
        parts=rows[0].split(",")
        parts[9]="999"
        rows[0]=",".join(parts)
        out=BytesIO()
        with ZipFile(out,"w",compression=ZIP_DEFLATED) as z:
            z.writestr("SOLUSDT-1h-"+month+".csv","\\n".join(rows)+"\\n")
        with self.assertRaisesRegex(ValueError,"Malformed Binance taker"):
            parse_zip(out.getvalue(),symbol="SOLUSDT",month=month)

    def test_mix_old_and_new_hourly_flow_fails_closed(self):
        bars=[
            {"t":i*3600,"o":100,"h":102,"l":99,"c":100,"v":50,
             **({"qv":5000,"trades":4,"tbv":25,"tbq":2500} if i!=2 else {})}
            for i in range(4)]
        with self.assertRaisesRegex(ValueError,"Partial Binance taker"):
            aggregate(bars,14400)

    def test_legacy_bare_ohlcv_still_aggregates(self):
        bars=[{"t":i*3600,"o":100,"h":102,"l":99,"c":100,"v":50}
              for i in range(4)]
        r=aggregate(bars,14400)
        self.assertEqual(r[0]["v"],200)
        self.assertNotIn("tbv",r[0])

    def test_missing_hour_fails_closed(self):
        b=synthetic("SOLUSDT","2025-02",skip_index=11)
        with self.assertRaisesRegex(ValueError,"Missing/extra"):
            parse_zip(b,symbol="SOLUSDT",month="2025-02")

    def test_wrong_asset_fails_closed(self):
        b=synthetic("SOLUSDT","2025-02")
        with self.assertRaises(ValueError):
            parse_zip(b,symbol="BTCUSDT",month="2025-02")

    def test_4h_and_1d_aggregates_from_same_exact_hourly_source(self):
        bars=[{"t":i*3600,"o":10+i,"h":14+i,"l":9+i,"c":11+i,"v":1+i}
              for i in range(24)]
        f=aggregate(bars,14400)
        d=aggregate(bars,86400)
        self.assertEqual(len(f),6)
        self.assertEqual(len(d),1)
        self.assertEqual(f[0]["o"],10)
        self.assertEqual(f[0]["c"],14)
        self.assertEqual(f[0]["h"],17)
        self.assertEqual(f[0]["l"],9)
        self.assertEqual(f[0]["v"],10)
        self.assertEqual(d[0]["v"],300)
        self.assertEqual(d[0]["c"],34)

    def test_invalid_time_alignment_fails_closed(self):
        bars=[{"t":i*3600+3600,"o":100,"h":101,"l":99,"c":100,"v":1}
              for i in range(4)]
        with self.assertRaises(ValueError):
            aggregate(bars,14400)

    def test_build_all_symbol_tf_counts(self):
        m="2025-02"
        content={(s,m):parse_zip(synthetic(s,m),symbol=s,month=m) for s in SYMBOLS}
        data,counts,st,en=build(content,m,m)
        self.assertEqual((counts["BTCUSDT"]["1hour"],counts["BTCUSDT"]["4hour"],counts["BTCUSDT"]["daily"]),(672,168,28))
        self.assertEqual(len(data[("SOLUSDT","daily")]),28)
        self.assertEqual(en-st,28*86400)

    def test_range_and_boundary(self):
        self.assertEqual(months_inclusive("2024-12","2025-02"),["2024-12","2025-01","2025-02"])
        with self.assertRaises(ValueError):
            months_inclusive("2025-10","2025-01")


if __name__=="__main__":
    unittest.main()
