#!/usr/bin/env python3
"""Download six months of official SHA256-verified Binance USD-M ETH daily warmup."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
from pathlib import Path

from download_binance_um_history import (
    aggregate, download_month, month_end, month_start, months_inclusive
)

SYMBOL="ETHUSDT"


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--start",default="2024-04")
    p.add_argument("--end",default="2024-09")
    p.add_argument("--output-dir",default="eth_verified_warmup")
    p.add_argument("--workers",type=int,default=4)
    a=p.parse_args()
    months=months_inclusive(a.start,a.end)
    if len(months)!=6 or not 1<=a.workers<=6:
        p.error("ETH warmup requires six complete months and 1-6 workers")
    downloaded={}
    manifest=[]
    with ThreadPoolExecutor(max_workers=a.workers) as pool:
        tasks={pool.submit(download_month,SYMBOL,m):m for m in months}
        for future in as_completed(tasks):
            symbol,month,rows,proof=future.result()
            if symbol!=SYMBOL:
                raise ValueError("ETH_WARMUP_WRONG_SYMBOL")
            downloaded[month]=rows
            manifest.append({"symbol":symbol,"month":month,**proof})
            print("ETH_WARMUP_BINANCE_SHA256_VERIFIED",month,len(rows),flush=True)
    start,end=month_start(a.start),month_end(a.end)
    one=[bar for month in months for bar in downloaded[month]]
    if len(one)!=(end-start)//3600 or any(
        bar["t"]!=start+i*3600 for i,bar in enumerate(one)):
        raise ValueError("ETH_WARMUP_1H_GAP_DUPLICATE_OR_BAD_BOUNDARY")
    daily=aggregate(one,86400)
    if len(daily)!=183:
        raise ValueError("ETH_WARMUP_DAILY_COUNT_MISMATCH")
    out=Path(a.output_dir);out.mkdir(parents=True,exist_ok=True)
    packed=[{"symbol":"ETHUSDT_PERP.A","history":daily}]
    (out/"history_daily_warmup.json").write_text(
        json.dumps(packed,separators=(",",":"))+"\n")
    summary={
        "source":"Official Binance USD-M monthly ETHUSDT 1H klines; monthly ZIP SHA256 verified; daily resampled from full 1H bars",
        "symbol":"ETHUSDT_PERP.A",
        "warmupOnlyNotPerformancePeriod":True,
        "firstUTC":datetime.fromtimestamp(start,timezone.utc).isoformat(),
        "endExclusiveUTC":datetime.fromtimestamp(end,timezone.utc).isoformat(),
        "dailyBars":len(daily),
        "checksumsVerified":len(manifest),
        "inputFiles":sorted(manifest,key=lambda x:x["month"]),
    }
    (out/"source_manifest.json").write_text(json.dumps(summary,indent=2)+"\n")
    assert summary["checksumsVerified"]==6
    print("ETH_3D_EMA_WARMUP_COMPLETE",len(daily),flush=True)


if __name__=="__main__":
    main()
