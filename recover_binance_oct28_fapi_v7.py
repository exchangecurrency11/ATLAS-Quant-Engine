#!/usr/bin/env python3
"""Verify and repair *one* missing 2026-10-28 Binance USD-M 1H archive day.

Fetches genuine BTCUSDT/SOLUSDT perpetual OHLCV from official Binance USD-M
Futures /fapi/v1/klines APIs; never estimates, interpolates or uses spot candles.
UTC-only timestamps; reject gap/duplicate/partial bars/invalid kline geometry.
Read-only historical experiment. Never modifies main, runs orders, alerts, or
trading automations.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from download_binance_um_history import SYMBOLS, PERIODS, aggregate
from extend_binance_archive_october_v6 import (
    day_bound, days_inclusive, download_day, append_histories,
)

GAP_DAY = "2026-10-28"
FIRST_NEW_DAY = "2026-10-01"
LAST_DAY = "2026-11-02"
OFFICIAL_FUTURES_HOSTS = (
    "https://fapi.binance.com",
    "https://fapi1.binance.com",
    "https://fapi2.binance.com",
)
MAX_RESPONSE_BYTES = 80_000


def validate_fapi_klines(payload, symbol, day):
    """Require exactly 24 UTC OHLCV bars, with genuine close-time bounds."""
    begin, end = day_bound(day)
    if not isinstance(payload, list) or len(payload) != 24:
        raise ValueError(f"{symbol}: expected 24 hourly Futures candles, got {len(payload) if isinstance(payload, list) else 'non-list'}")
    result = []
    for idx, row in enumerate(payload):
        if not isinstance(row, list) or len(row) < 12:
            raise ValueError("Unexpected Binance Futures kline schema")
        open_time_ms = int(row[0])
        close_time_ms = int(row[6])
        target = (begin + idx * 3600) * 1000
        if open_time_ms != target or close_time_ms != target + 3_600_000 - 1:
            raise ValueError(f"{symbol}: gap/duplicate/misaligned close at hour {idx}")
        o, h, l, c, v = (float(row[i]) for i in range(1, 6))
        from math import isfinite
        if not all(isfinite(x) for x in (o, h, l, c, v)):
            raise ValueError("Nonfinite Futures OHLCV")
        if not (l > 0 and l <= min(o, c) <= max(o, c) <= h and v >= 0):
            raise ValueError("Invalid Futures OHLCV geometry")
        result.append({"t":begin + idx*3600, "o":o, "h":h, "l":l, "c":c, "v":v})
    if result[-1]["t"] + 3600 != end:
        raise ValueError("UTC day incomplete")
    return result


def get_gap_api(symbol, day=GAP_DAY, hosts=OFFICIAL_FUTURES_HOSTS):
    if symbol not in SYMBOLS or day != GAP_DAY:
        raise ValueError("Only approved symbols and missing date allowed")
    begin, end = day_bound(day)
    params = urlencode({
        "symbol":symbol, "interval":"1h",
        "startTime":begin*1000,
        "endTime":end*1000-1,
        "limit":24,
    })
    failures = []
    for host in hosts:
        url = host + "/fapi/v1/klines?" + params
        try:
            req = Request(url, headers={
                "User-Agent":"btc-sol-paper-gap-audit/1.0",
                "Accept":"application/json",
            })
            with urlopen(req, timeout=20) as resp:
                data = resp.read(MAX_RESPONSE_BYTES + 1)
                if len(data) > MAX_RESPONSE_BYTES:
                    raise ValueError("Futures API response size exceeds limit")
            bars = validate_fapi_klines(json.loads(data), symbol, day)
            # Integrity checksum of the exact HTTP payload, not a fabricated Binance CHECKSUM.
            proof = {
                "symbol":symbol, "date":day,
                "sourceType":"Binance USD-M Futures REST API OHLCV",
                "sourceUrl":url,
                "payloadSHA256":hashlib.sha256(data).hexdigest(),
                "confirmedClosedHours":len(bars),
                "warning":"SHA256 is local HTTP response digest, NOT Binance signed archive checksum",
            }
            return symbol, day, bars, proof
        except (HTTPError, URLError, TimeoutError, ValueError, OSError) as error:
            failures.append(f"{host}: {type(error).__name__}: {str(error)[:220]}")
    raise RuntimeError("All official USD-M Futures REST hosts inaccessible or invalid for "
                       + symbol + " " + day + "; " + "; ".join(failures))


def recover_series(base_records, extra_rows, days):
    if not days or days[0] != FIRST_NEW_DAY or days[-1] != LAST_DAY:
        raise ValueError("Expected contiguous Oct 1 through Nov 2")
    data=append_histories(base_records,extra_rows,days)
    first=(base_records[0]["history"])[0]["t"]
    _,end=day_bound(LAST_DAY)
    expected=(end-first)//3600
    for symbol in SYMBOLS:
        hour=data[(symbol,"1hour")]
        if len(hour)!=expected or any(row["t"]!=first+i*3600 for i,row in enumerate(hour)):
            raise ValueError(f"UTC continuity check failed for {symbol}")
    return data


def main():
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--probe-only",action="store_true")
    cli.add_argument("--base-dir",default="binance_2y")
    cli.add_argument("--output-dir",default="binance_through_nov2")
    cli.add_argument("--workers",type=int,default=4)
    args=cli.parse_args()
    if not 1<=args.workers<=6:
        cli.error("1–6 workers only")
    # Probe is fast, avoids unnecessary 48 ZIP monthly download if official
    # futures API is region-blocked or 28 Oct klines cannot be obtained.
    proofs=[]
    gap={}
    for symbol in SYMBOLS:
        s, day, bars, proof=get_gap_api(symbol)
        gap[(s,day)]=bars
        proofs.append(proof)
        print("GAP_VERIFIED",s,day,len(bars),proof["sourceUrl"],flush=True)
    if args.probe_only:
        print("GAP_PROBE_OK: 24 official Binance Futures 1H bars for each symbol",
              flush=True)
        return
    base_dir=Path(args.base_dir)
    records=json.loads((base_dir/"history_1hour.json").read_text())
    manifest=json.loads((base_dir/"source_manifest.json").read_text())
    if manifest.get("endExclusiveUTC")!="2026-10-01T00:00:00+00:00":
        raise ValueError("Base monthly archive does not end before Oct 1")
    days=days_inclusive(FIRST_NEW_DAY,LAST_DAY)
    other=[(s,day) for s in SYMBOLS for day in days if day!=GAP_DAY]
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        for s,day,bars,proof in executor.map(lambda pair:download_day(*pair),other):
            gap[(s,day)]=bars
            proofs.append(proof)
            print("DAILY_SHA256_VERIFIED",s,day,len(bars),flush=True)
    output=recover_series(records,gap,days)
    folder=Path(args.output_dir)
    folder.mkdir(parents=True,exist_ok=True)
    counts={}
    for interval in PERIODS:
        merged=[]
        for symbol in SYMBOLS:
            rows=output[(symbol,interval)]
            counts.setdefault(symbol,{})[interval]=len(rows)
            merged.append({"symbol":symbol+"_PERP.A","history":rows})
        (folder/("history_"+interval+".json")).write_text(
            json.dumps(merged,separators=(",",":"))+"\n")
    report={
        "mode":"PAPER_ONLY_READ_ONLY_ARCHIVE_RECONSTRUCTION",
        "originalSource":"Official Binance USD-M Futures monthly 1H ZIP SHA256",
        "baseMonths":"2024-10 through 2026-09",
        "appendDays":f"{FIRST_NEW_DAY} through {LAST_DAY}",
        "gapDay":GAP_DAY,
        "gapSource":"Official Binance USD-M Futures REST /fapi/v1/klines; not archive",
        "allOtherAdditionalDaysSource":"Official Binance USD-M Futures daily ZIP with SHA256 verification",
        "gapNotInterpolated":True,
        "noSpotData":True,
        "gapAPINotAnIndependentExchangeCrosscheck":True,
        "endExclusiveUTC":"2026-11-03T00:00:00+00:00",
        "counts":counts,
        "addedFileCount":len(proofs),
        "sourceProofs":sorted(proofs,key=lambda d:(d["symbol"],d["date"])),
        "limitations":"API-based 28 Oct 24h retrieval was authenticated only by HTTPS, not a Binance-signed archive checksum; no simulated missing hours; no funding, liquidity or real fills",
    }
    (folder/"provenance_manifest.json").write_text(
        json.dumps(report,indent=2,ensure_ascii=False)+"\n")
    print("RECONSTRUCTION_OK",json.dumps({
        "counts":counts,"gapSource":report["gapSource"],
        "endExclusiveUTC":report["endExclusiveUTC"],
        "addedFileCount":len(proofs)
    }),flush=True)


if __name__=="__main__":
    main()
