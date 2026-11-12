#!/usr/bin/env python3
"""Download six months of SHA256-verified Binance USD-M daily warmup for BTC/SOL.

The official 1H monthly ZIPs are verified first; daily OHLCV is then aggregated
from complete 1H bars. These bars are ONLY indicator warmup before 2024-10-01;
they are not included in the 2-year performance scoring period.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
from pathlib import Path

from download_binance_um_history import (
    aggregate, download_month, month_end, month_start, months_inclusive
)

SYMBOLS=("BTCUSDT","SOLUSDT")


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--start",default="2024-04")
    p.add_argument("--end",default="2024-09")
    p.add_argument("--output-dir",default="v92_verified_warmup")
    p.add_argument("--workers",type=int,default=4)
    a=p.parse_args()
    months=months_inclusive(a.start,a.end)
    if len(months)!=6 or not 1<=a.workers<=6:
        p.error("Warmup requires exactly six complete months and 1-6 workers")
    result={}
    manifest=[]
    with ThreadPoolExecutor(max_workers=a.workers) as pool:
        tasks={pool.submit(download_month,s,m):(s,m)
               for s in SYMBOLS for m in months}
        for future in as_completed(tasks):
            symbol,month,rows,proof=future.result()
            result[(symbol,month)]=rows
            manifest.append({"symbol":symbol,"month":month,**proof})
            print("WARMUP_BINANCE_SHA256_VERIFIED",symbol,month,len(rows),flush=True)
    start,end=month_start(a.start),month_end(a.end)
    packed=[]
    counts={}
    for symbol in SYMBOLS:
        one=[bar for month in months for bar in result[(symbol,month)]]
        if len(one)!=(end-start)//3600 or any(
            bar["t"]!=start+i*3600 for i,bar in enumerate(one)):
            raise ValueError("WARMUP_1H_GAP_DUPLICATE_OR_BAD_BOUNDARY_"+symbol)
        daily=aggregate(one,86400)
        if len(daily)!=183:
            raise ValueError("WARMUP_DAILY_COUNT_MISMATCH_"+symbol)
        packed.append({"symbol":symbol+"_PERP.A","history":daily})
        counts[symbol]=len(daily)
    out=Path(a.output_dir);out.mkdir(parents=True,exist_ok=True)
    (out/"history_daily_warmup.json").write_text(
        json.dumps(packed,separators=(",",":"))+"\n")
    summary={
        "source":"Official Binance USD-M monthly 1H klines; monthly ZIP SHA256 verified; daily resampled from exact 1H UTC bars",
        "warmupOnlyNotPerformancePeriod":True,
        "firstUTC":datetime.fromtimestamp(start,timezone.utc).isoformat(),
        "endExclusiveUTC":datetime.fromtimestamp(end,timezone.utc).isoformat(),
        "dailyCounts":counts,
        "checksumsVerified":len(manifest),
        "inputFiles":sorted(manifest,key=lambda x:(x["symbol"],x["month"])),
    }
    (out/"source_manifest.json").write_text(json.dumps(summary,indent=2)+"\n")
    assert summary["checksumsVerified"]==12
    print("V92_BTC_SOL_WARMUP_COMPLETE",json.dumps(summary["dailyCounts"]),flush=True)


if __name__=="__main__":
    main()
