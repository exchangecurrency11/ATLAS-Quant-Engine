#!/usr/bin/env python3
"""Download official SHA256-verified Binance USD-M ETHUSDT 1H monthly klines.

4H and 1D are resampled from exact 1H Binance Futures candles on UTC boundaries.
No API key, no orders. The resulting 3D candles are deliberately derived later
from three complete daily bars, not claimed as native Binance 3D klines.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
from pathlib import Path

from download_binance_um_history import (
    PERIODS, aggregate, download_month, month_end, month_start,
    months_inclusive,
)

SYMBOL = "ETHUSDT"


def build(month_data, first, last):
    months = months_inclusive(first, last)
    start, end = month_start(first), month_end(last)
    one = [bar for month in months for bar in month_data[(SYMBOL, month)]]
    expected = (end-start)//3600
    if len(one) != expected or any(
        bar["t"] != start+i*3600 for i,bar in enumerate(one)
    ):
        raise ValueError("ETH_BINANCE_1H_ARCHIVE_GAP_DUPLICATE_OR_BAD_BOUNDARY")
    if start % 86400 or end % 86400:
        raise ValueError("ETH_ARCHIVE_MUST_USE_UTC_DAY_BOUNDARIES")
    data = {tf: aggregate(one, seconds) for tf,seconds in PERIODS.items()}
    counts = {tf: len(rows) for tf,rows in data.items()}
    return data, counts, start, end


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start",default="2024-10")
    parser.add_argument("--end",default="2026-09")
    parser.add_argument("--output-dir",default="eth_verified_archive")
    parser.add_argument("--workers",type=int,default=4)
    args=parser.parse_args()
    months=months_inclusive(args.start,args.end)
    if len(months)!=24 or not 1<=args.workers<=6:
        parser.error("ETH archive requires exactly 24 complete months and 1-6 workers")
    month_data={}
    manifest=[]
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        tasks={pool.submit(download_month,SYMBOL,m):m for m in months}
        for future in as_completed(tasks):
            symbol,month,rows,proof=future.result()
            if symbol!=SYMBOL:
                raise ValueError("ETH_WRONG_BINANCE_SYMBOL")
            month_data[(symbol,month)]=rows
            manifest.append({"symbol":symbol,"month":month,**proof})
            print(f"ETH_BINANCE_SHA256_VERIFIED {month} {len(rows)} 1H candles",flush=True)
    data,counts,start,end=build(month_data,args.start,args.end)
    out=Path(args.output_dir);out.mkdir(parents=True,exist_ok=True)
    for tf,rows in data.items():
        packed=[{"symbol":"ETHUSDT_PERP.A","history":rows}]
        (out/f"history_{tf}.json").write_text(
            json.dumps(packed,separators=(",",":"))+"\n")
    summary={
        "source":"Binance official data.binance.vision FUTURES/UM monthly ETHUSDT 1h klines",
        "symbol":"ETHUSDT_PERP.A",
        "firstUTC":datetime.fromtimestamp(start,timezone.utc).isoformat(),
        "endExclusiveUTC":datetime.fromtimestamp(end,timezone.utc).isoformat(),
        "pairCounts":counts,
        "checksumsVerified":len(manifest),
        "inputFiles":sorted(manifest,key=lambda x:x["month"]),
        "4HAndDaily":"Aggregated from exactly continuous official 1H OHLCV on UTC boundaries",
        "limitations":"Historical closed bars only; no funding, execution, liquidation or native 3D feed",
    }
    (out/"source_manifest.json").write_text(json.dumps(summary,indent=2)+"\n")
    assert counts=={"1hour":17520,"4hour":4380,"daily":730}
    assert summary["checksumsVerified"]==24
    print("ETH_BINANCE_ARCHIVE_COMPLETE",json.dumps({
        "counts":counts,"checksumsVerified":summary["checksumsVerified"]}),flush=True)


if __name__=="__main__":
    main()
