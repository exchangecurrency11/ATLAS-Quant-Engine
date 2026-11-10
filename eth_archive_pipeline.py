#!/usr/bin/env python3
"""Read-only ETHUSDT Binance USD-M Futures closed klines archive.

Daily/monthly ZIP + SHA256 CHECKSUM from Binance public data archive.
Exports full available 1h since 2019-11 (partial first month permitted),
then 4h/1d derived from validated 1h. Also 5m/15m for recent
entry-analysis history. No live prices, orders, credentials or production changes.
"""
import argparse
import calendar
import csv
import hashlib
import io
import json
import math
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zipfile import ZipFile

from download_binance_um_history import get, months_inclusive

ROOT="https://data.binance.vision/data/futures/um"
SYMBOL="ETHUSDT"
STEP={"1m":60,"5m":300,"15m":900,"1h":3600,"4h":14400,"1d":86400}
START_YEAR_MONTH="2019-12"


def month_after(ym):
    y,m=map(int,ym.split("-"))
    return f"{y+1:04d}-01" if m==12 else f"{y:04d}-{m+1:02d}"


def month_start(ym):
    return int(datetime.strptime(ym+"-01","%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp())


def iso(seconds):
    return datetime.fromtimestamp(seconds,timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def verify_chunk(entry, step):
    """Byte checksum, exact member, strict timestamp spacing, closed OHLCV."""
    package, interval, date = entry
    period="monthly" if package=="monthly" else "daily"
    url=f"{ROOT}/{period}/klines/{SYMBOL}/{interval}/{SYMBOL}-{interval}-{date}.zip"
    blob=get(url,max_size=12_000_000)
    checksum=get(url+".CHECKSUM",max_size=2000).decode("utf-8-sig").strip()
    declared=checksum.split()[0].lower()
    actual=hashlib.sha256(blob).hexdigest()
    if len(declared)!=64 or actual!=declared:
        raise ValueError(f"CHECKSUM mismatch: {entry}")
    with ZipFile(io.BytesIO(blob)) as archive:
        names=[x for x in archive.namelist() if x.endswith(".csv")]
        expected=f"{SYMBOL}-{interval}-{date}.csv"
        if len(names)!=1 or names[0].split("/")[-1]!=expected:
            raise ValueError(f"Wrong CSV member: {entry} {names}")
        if archive.getinfo(names[0]).file_size>65_000_000:
            raise ValueError("CSV too large")
        rows=[]
        with archive.open(names[0]) as raw:
            for fields in csv.reader(io.TextIOWrapper(raw,encoding="utf-8-sig")):
                if not fields or fields[0].lower().replace("_"," ") in ("open time","opentime"):
                    continue
                if len(fields)<6:
                    raise ValueError(f"Bad row: {entry}")
                raw_t=int(fields[0])
                t=(raw_t//1000000 if raw_t>=10**15 else raw_t//1000)
                row={"t":t,"o":float(fields[1]),"h":float(fields[2]),
                     "l":float(fields[3]),"c":float(fields[4]),"v":float(fields[5])}
                if not all(math.isfinite(row[k]) for k in ("o","h","l","c","v")):
                    raise ValueError("Nonfinite candle")
                if row["l"]<=0 or row["v"]<0 or row["l"]>min(row["o"],row["c"]) or row["h"]<max(row["o"],row["c"]):
                    raise ValueError("Broken OHLCV")
                rows.append(row)
    start=month_start(date) if package=="monthly" else int(
        datetime.strptime(date,"%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp())
    end=(month_start(month_after(date)) if package=="monthly" else start+86400)
    if not rows or rows[0]["t"]<start or rows[-1]["t"]>=end:
        raise ValueError(f"Out-of-period or empty: {entry}")
    if any(row["t"]%step or (i and row["t"]-rows[i-1]["t"]!=step)
           for i,row in enumerate(rows)):
        raise ValueError(f"Gaps or misaligned candles: {entry}")
    # Contract launch month 2019-11 is partial, but every subsequent
    # interval and month MUST be complete. Last finished day must be complete.
    launch_partial=(date=="2019-11" and interval=="1h")
    if not launch_partial and (rows[0]["t"]!=start or rows[-1]["t"]+step!=end):
        raise ValueError(f"Incomplete package: {entry}, rows={len(rows)}")
    return entry,rows,{"url":url,"zipSha256":actual,"bars":len(rows),
                       "firstUTC":iso(rows[0]["t"]),"lastCloseUTC":iso(rows[-1]["t"]+step)}


def full_month_before(today):
    first=today.replace(day=1)
    return (first-timedelta(days=1)).strftime("%Y-%m")


def list_entries(now_utc,*,start="2019-11",include_recent=True):
    day=now_utc.date()
    last_month=full_month_before(now_utc)
    first_months=months_inclusive(start,last_month)
    daily_start=datetime(int(last_month[:4]),int(last_month[5:]),1,tzinfo=timezone.utc)
    daily_start=datetime.strptime(month_after(last_month)+"-01","%Y-%m-%d").date()
    daily_dates=[(daily_start+timedelta(days=i)).strftime("%Y-%m-%d")
                 for i in range(max(0,(day-daily_start).days))]
    # Full 1h history, with 5m and 15m covering the last complete month
    # plus current month so that recent lower-timeframe entries can be studied.
    entries=[("monthly","1h",ym) for ym in first_months]
    entries += [("daily","1h",ymd) for ymd in daily_dates]
    if include_recent:
        entries += [("monthly",tf,last_month) for tf in ("5m","15m")]
        entries += [("daily",tf,d) for d in daily_dates for tf in ("5m","15m")]
    return entries


def concatenate(files, interval):
    rows=[]
    for entry,chunk,proof in sorted(files,key=lambda x:x[1][0]["t"]):
        if entry[1]!=interval:
            continue
        if rows and chunk[0]["t"]-rows[-1]["t"]!=STEP[interval]:
            raise ValueError(f"Cross-package gap in {interval} at {iso(chunk[0]['t'])}")
        rows+=chunk
    return rows


def aggregate(bars, tf):
    secs=STEP[tf];parts=secs//3600
    if tf=="1h":
        return bars
    if not bars:
        raise ValueError("Missing 1h data")
    # Start from first aligned COMPLETE 4H or 1D UTC group.
    first=next((i for i,b in enumerate(bars) if b["t"]%secs==0),None)
    if first is None:
        raise ValueError("No aligned timeframe start")
    output=[]
    for i in range(first,len(bars)-parts+1,parts):
        block=bars[i:i+parts]
        if any(x["t"]!=block[0]["t"]+j*3600 for j,x in enumerate(block)):
            raise ValueError("Gap in source 1h aggregation")
        output.append({"t":block[0]["t"],"o":block[0]["o"],
                       "h":max(x["h"] for x in block),
                       "l":min(x["l"] for x in block),
                       "c":block[-1]["c"],"v":sum(x["v"] for x in block)})
    return output


def produce(entries, results, dest):
    dest=Path(dest);dest.mkdir(parents=True,exist_ok=True)
    by_interval={}
    for tf in ("1h","5m","15m"):
        chunks=[v for v in results if v[0][1]==tf]
        data=concatenate(chunks,tf)
        if not data:
            raise ValueError(f"Missing {tf}")
        by_interval[tf]=data
    by_interval["4h"]=aggregate(by_interval["1h"],"4h")
    by_interval["1d"]=aggregate(by_interval["1h"],"1d")
    counts={}
    for tf,bars in by_interval.items():
        # Only CLOSED candles; first/last source package excludes current date.
        path=dest/f"ETHUSDT_{tf}.json"
        path.write_text(json.dumps({"symbol":"ETHUSDT","market":"Binance USDT-M perpetual",
                                    "interval":tf,"history":bars},
                                   separators=(",",":"))+"\n",encoding="utf-8")
        counts[tf]={"candles":len(bars),"firstOpenUTC":iso(bars[0]["t"]),
                    "lastCloseUTC":iso(bars[-1]["t"]+STEP[tf]),
                    "file":path.name}
    manifest={
        "status":"BINANCE_OFFICIAL_ARCHIVE_SHA256_VERIFIED",
        "market":"USD-M perpetual","symbol":"ETHUSDT",
        "inputPackages":len(results),
        "firstPartialLaunchMonth":"ETHUSDT launched Nov 2019, but monthly 2019-11 1h ZIP returned HTTP 404; historical archive starts from first available complete month",
        "intervals":counts,
        "sourceFiles":sorted([dict(package=e[0],interval=e[1],date=e[2],**proof)
                              for e,_,proof in results],
                             key=lambda x:(x["interval"],x["date"])),
        "restrictions":"Historical only. Latest complete UTC day; no intraday today. No live trading or forward V7 signal.",
    }
    (dest/"manifest.json").write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    (dest/"STATUS.md").write_text(
        "# ETHUSDT Binance USD-M perpetual — verified historical candles\n\n"
        "Data: Binance official monthly/daily kline ZIP files; SHA256 checksums verified.\n\n"
        "| Interval | Candles | First open UTC | Last close UTC |\n|---|---:|---|---|\n"+
        "\n".join(f"| {tf} | {row['candles']} | {row['firstOpenUTC']} | {row['lastCloseUTC']} |"
                  for tf,row in counts.items())+
        "\n\nNo same-day live candle, funding or real order information is claimed. "
        "The 4H and Daily candles are resampled from exact continuous Binance 1H data. "
        "Shorter timeframes (5m,15m) cover the last complete month plus "
        "the current month's fully published days only.\n",
        encoding="utf-8")
    return manifest


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--output-dir",default="eth-history")
    p.add_argument("--workers",type=int,default=8)
    p.add_argument("--start-month",default=START_YEAR_MONTH)
    p.add_argument("--now-utc",default=None,help="Override for reproducible archive run")
    p.add_argument("--no-recent",action="store_true")
    args=p.parse_args()
    if not 1<=args.workers<=10:
        p.error("Choose 1..10 concurrent download workers")
    now=(datetime.fromisoformat(args.now_utc.replace("Z","+00:00"))
         if args.now_utc else datetime.now(timezone.utc))
    if now.utcoffset()!=timedelta(0):
        p.error("UTC required")
    entries=list_entries(now,start=args.start_month,include_recent=not args.no_recent)
    out=[]
    print(f"Downloading ETH perpetual archives: {len(entries)} ZIPs with official SHA256",flush=True)
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        jobs={pool.submit(verify_chunk,e,STEP[e[1]]):e for e in entries}
        for task in as_completed(jobs):
            row=task.result()
            out.append(row)
            print("VERIFIED",row[0],row[2]["bars"],flush=True)
    manifest=produce(entries,out,args.output_dir)
    print(json.dumps({"symbol":"ETHUSDT","archivesVerified":len(out),
                      "intervals":manifest["intervals"]},indent=2))


if __name__=="__main__":
    main()
