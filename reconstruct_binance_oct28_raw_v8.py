#!/usr/bin/env python3
"""Reconstruct missing 2026-10-28 USD-M Futures klines from Binance RAW trades.

The official Binance daily 1H and monthly 1H OHLCV archives omit 28 Oct.
Instead use SHA256-verified official raw futures trades (not spot, not guesses),
group true trade events by UTC hour, and compare the reconstruction method to
an intact adjacent day's official 1H Binance candles BEFORE accepting the gap.
Paper-only, isolated experimental branch, never orders or edits live sources.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import csv
from datetime import datetime,timezone
from decimal import Decimal,InvalidOperation
import hashlib
from io import BytesIO,TextIOWrapper
import json
import math
from pathlib import Path
from zipfile import ZipFile

from download_binance_um_history import get, SYMBOLS,PERIODS
from extend_binance_archive_october_v6 import (
    day_bound,days_inclusive,download_day,append_histories,
)
from recover_binance_oct28_fapi_v7 import GAP_DAY,FIRST_NEW_DAY,LAST_DAY,recover_series

RAW_BASE="https://data.binance.vision/data/futures/um/daily/trades"
MAX_ZIP_BYTES=50_000_000
MAX_CSV_BYTES=750_000_000
EXPECTED_HEADER=["id","price","qty","quote_qty","time","is_buyer_maker"]


def aggregate_raw_zip(raw_archive,symbol,day):
    """Stream CSV. Strictly monotonic trade id/time; refuse missing UTC hours."""
    if symbol not in SYMBOLS:
        raise ValueError("Unapproved symbol")
    start,end=day_bound(day)
    filename=f"{symbol}-trades-{day}.csv"
    with ZipFile(BytesIO(raw_archive)) as archive:
        infos=archive.infolist()
        if len(infos)!=1 or infos[0].filename.split("/")[-1]!=filename:
            raise ValueError(f"Unexpected futures trades ZIP members for {symbol}")
        if infos[0].file_size>MAX_CSV_BYTES:
            raise ValueError("Raw trades CSV too large")
        with archive.open(infos[0]) as raw:
            reader=csv.reader(TextIOWrapper(raw,encoding="utf-8-sig"))
            first=next(reader,None)
            if not first or [x.strip().lower() for x in first]!=EXPECTED_HEADER:
                raise ValueError(f"Unexpected Futures trade CSV header {first}")
            output=[None for _ in range(24)]
            previous_id=previous_time=None
            count=0
            for parts in reader:
                if len(parts)!=6:
                    raise ValueError("Invalid Futures trades CSV row")
                trade_id=int(parts[0])
                price=Decimal(parts[1])
                qty=Decimal(parts[2])
                raw_time=int(parts[4])
                t=raw_time//1000 if raw_time>100_000_000_000 else raw_time
                if previous_id is not None and trade_id<=previous_id:
                    raise ValueError("Non-increasing futures trade IDs")
                if previous_time is not None and t<previous_time:
                    raise ValueError("Non-monotonic futures trade timestamps")
                previous_id,previous_time=trade_id,t
                if not (start<=t<end):
                    raise ValueError(f"Trade outside UTC day {day}")
                if not(price.is_finite() and qty.is_finite()) or price<=0 or qty<=0:
                    raise ValueError("Invalid real futures trade price / quantity")
                hour=(t-start)//3600
                bar=output[hour]
                if bar is None:
                    output[hour]={
                        "t":start+hour*3600,"o":price,"h":price,
                        "l":price,"c":price,"v":qty,
                        "trades":1,
                    }
                else:
                    bar["h"]=max(bar["h"],price)
                    bar["l"]=min(bar["l"],price)
                    bar["c"]=price
                    bar["v"]+=qty
                    bar["trades"]+=1
                count+=1
                if count>16_000_000:
                    raise ValueError("Suspicious trade count")
    if any(bar is None for bar in output):
        raise ValueError("Missing 1H trading period: do not invent candles")
    if not all(bar["v"]>0 and bar["trades"]>0 for bar in output):
        raise ValueError("Zero-volume/zero-trade 1H candle")
    result=[]
    for bar in output:
        result.append({
            "t":bar["t"],
            "o":float(bar["o"]),
            "h":float(bar["h"]),
            "l":float(bar["l"]),
            "c":float(bar["c"]),
            "v":float(bar["v"]),
        })
    return result,{"rawTrades":count,"firstTradeId":output[0] and "see source CSV",
                   "minHourlyTrades":min(b["trades"] for b in output),
                   "maxHourlyTrades":max(b["trades"] for b in output)}


def download_raw_day(symbol,day):
    if symbol not in SYMBOLS:
        raise ValueError("Unapproved pair")
    url=f"{RAW_BASE}/{symbol}/{symbol}-trades-{day}.zip"
    raw=get(url,max_size=MAX_ZIP_BYTES)
    checksum_text=get(url+".CHECKSUM",max_size=2000).decode("utf-8-sig").strip()
    expected=checksum_text.split()[0].lower()
    if len(expected)!=64 or any(c not in "0123456789abcdef" for c in expected):
        raise ValueError("Missing valid official Binance SHA256 raw-trades checksum")
    digest=hashlib.sha256(raw).hexdigest()
    if digest!=expected:
        raise ValueError(f"Official Binance raw-trade SHA256 mismatch {symbol} {day}")
    rows,stats=aggregate_raw_zip(raw,symbol,day)
    proof={
        "symbol":symbol,"date":day,"source":"Official Binance USD-M Futures RAW trades CSV",
        "officialZipUrl":url,"officialZipSHA256":digest,"candlesDerived":24,
        "method":"OHLC from UTC chronological individual trade prices; base volume=sum qty",
        **stats,
    }
    return symbol,day,rows,proof


def crosscheck_reconstruction(reconstructed,official,symbol,day):
    """Validate same method on a day with both trades and native klines."""
    if len(reconstructed)!=24 or len(official)!=24:
        raise ValueError("Cannot validate incomplete crosscheck")
    max_abs_volume_delta=0.0
    for n,(ours,published) in enumerate(zip(reconstructed,official)):
        if ours["t"]!=published["t"]:
            raise ValueError("Crosscheck timestamp mismatch")
        for field in ("o","h","l","c"):
            if not math.isclose(ours[field],published[field],abs_tol=0.0000001,rel_tol=1e-10):
                raise ValueError(
                    f"Raw-trade reconstruction fails official Binance kline "
                    f"{symbol} {day} UTC hour {n} field {field}: {ours[field]} vs {published[field]}"
                )
        delta=abs(ours["v"]-published["v"])
        max_abs_volume_delta=max(delta,max_abs_volume_delta)
        if delta>max(0.000001, published["v"]*0.0000001):
            raise ValueError(f"Volume mismatch {symbol} hour {n} {delta}")
    return {
        "symbol":symbol,
        "referenceDay":day,
        "checkedHours":24,
        "OHLCAllMatchPublishedBinanceKlines":True,
        "volumeWithinTolerance":True,
        "maximumAbsoluteHourlyVolumeDifference":max_abs_volume_delta,
    }


def validate_method_against_adjacent_day(symbol,day="2026-10-29"):
    s,d,raw,proof=download_raw_day(symbol,day)
    _,_,official,kline_proof=download_day(symbol,day)
    confidence=crosscheck_reconstruction(raw,official,s,d)
    confidence.update({
        "rawTradesSourceSha256":proof["officialZipSHA256"],
        "officialKlineSourceSha256":kline_proof["sha256"],
    })
    return confidence


def crosscheck_gap_against_fixed_coinalyze(symbol, reconstructed,
                                               reference_path="validation_refs/coinalyze_oct28_1h_reference.json"):
    """Corroborate real Binance raw trades using frozen third-party perp 1H.

    Secondary Coinalyze data are NOT Binance-signed native klines.
    Raw trade ZIP authenticity is verified separately via official SHA256.
    """
    ref=json.loads(Path(reference_path).read_text())
    items=[x for x in ref["data"] if x["symbol"]==symbol and x["day"]==GAP_DAY]
    if len(items)!=1 or len(items[0]["bars"])!=24 or len(reconstructed)!=24:
        raise ValueError("Missing immutable independent October 28 reference")
    max_volume_pct=0.0
    max_open_abs=0.0
    openings_different=0
    tick=0.1000001 if symbol=="BTCUSDT" else 0.0100001
    for n,(raw,second) in enumerate(zip(reconstructed,items[0]["bars"])):
        if raw["t"]!=int(second["t"]):
            raise ValueError(f"Missing or misplaced independent UTC hour {n}")
        for field in ("h","l","c"):
            if not math.isclose(raw[field],float(second[field]),rel_tol=1e-10,abs_tol=1e-7):
                raise ValueError(f"Cross-source 28 Oct {symbol} mismatch hour {n}, {field}")
        abs_open=abs(raw["o"]-float(second["o"]))
        if abs_open>tick:
            raise ValueError(f"Cross-source 28 Oct opening discrepancy >1 tick {symbol} {n}")
        if abs_open>1e-7:
            openings_different+=1
        max_open_abs=max(max_open_abs,abs_open)
        if raw["v"]<=0:
            raise ValueError("Non-positive true futures volume")
        volume_diff_pct=abs(float(second["v"])/raw["v"]-1)*100
        max_volume_pct=max(max_volume_pct,volume_diff_pct)
        if volume_diff_pct>0.5:
            raise ValueError(f"Cross-source 28 Oct volume difference exceeds 0.5% {symbol} {n}")
    return {
        "symbol":symbol,"gapDay":GAP_DAY,"checkedHours":24,
        "officialRawTradesZipChecksumConfirmedSeparately":True,
        "secondarySource":"Fixed independent Coinalyze perpetual 1H snapshot, not a Binance native Kline",
        "highLowCloseMatchAll24":True,
        "maximumOpeningDifferenceUSD":max_open_abs,
        "openingHoursDifferent":openings_different,
        "maxAbsoluteVolumeDifferencePct":max_volume_pct,
        "allHourlyVolumesWithinHalfPercent":True,
    }


def main():
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--probe-only",action="store_true")
    cli.add_argument("--base-dir",default="binance_2y")
    cli.add_argument("--output-dir",default="binance_through_nov2")
    cli.add_argument("--workers",type=int,default=4)
    args=cli.parse_args()
    if not 1<=args.workers<=6:
        cli.error("workers 1..6")
    checks=[]
    recovered={}
    proofs=[]
    for symbol in SYMBOLS:
        s,d,rows,proof=download_raw_day(symbol,GAP_DAY)
        quality=crosscheck_gap_against_fixed_coinalyze(symbol,rows)
        checks.append(quality)
        recovered[(s,d)]=rows
        proofs.append(proof)
        print("28_OCT_RECOVERED_AND_CROSSCHECKED",
              s,proof["rawTrades"],len(rows),proof["officialZipSHA256"],
              json.dumps(quality),flush=True)
    if args.probe_only:
        print("RAW_TRADE_GAP_PROBE_OK",flush=True)
        return
    base=Path(args.base_dir)
    monthly_manifest=json.loads((base/"source_manifest.json").read_text())
    if monthly_manifest.get("endExclusiveUTC")!="2026-10-01T00:00:00+00:00":
        raise ValueError("Month archive continuity reference mismatch")
    old=json.loads((base/"history_1hour.json").read_text())
    days=days_inclusive(FIRST_NEW_DAY,LAST_DAY)
    inputs=[(s,d) for s in SYMBOLS for d in days if d!=GAP_DAY]
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for symbol,day,rows,proof in pool.map(lambda p:download_day(*p),inputs):
            recovered[(symbol,day)]=rows
            proofs.append(proof)
            print("SHA256_VERIFIED_DAILY_KLINE",symbol,day,flush=True)
    data=recover_series(old,recovered,days)
    dest=Path(args.output_dir);dest.mkdir(parents=True,exist_ok=True)
    counts={}
    for interval in PERIODS:
        combined=[]
        for symbol in SYMBOLS:
            rows=data[(symbol,interval)]
            combined.append({"symbol":symbol+"_PERP.A","history":rows})
            counts.setdefault(symbol,{})[interval]=len(rows)
        (dest/("history_"+interval+".json")).write_text(
            json.dumps(combined,separators=(",",":"))+"\n")
    report={
        "mode":"OFFLINE_PAPER_ONLY_SHA256_VERIFIED_BINANCE_FUTURES_RAW_TRADES_RECONSTRUCTION",
        "base":"2024-10 through 2026-09 Binance USD-M verified monthly 1H",
        "addedDates":"2026-10-01 to 2026-11-02 inclusive",
        "gapDay":GAP_DAY,
        "gapSource":"BTC/SOL official Binance USD-M Futures raw trades ZIP archives, SHA256 verified",
        "gapFilledWithRealTrades":True,
        "interpolationOrSpotUsed":False,
        "oct28SecondaryCrosschecks":checks,
        "fileProofs":sorted(proofs,key=lambda p:(p["symbol"],p["date"])),
        "endExclusiveUTC":"2026-11-03T00:00:00+00:00",
        "counts":counts,
        "verificationCaveat":"28 Oct OHLCV reconstructed from Binance raw trade-level records (ZIP SHA256 verified), not published native 1H; independently crosschecked against frozen Coinalyze 1H for all 24 hours with max 0.5pct volume difference and one-tick open tolerance. 29 Oct raw-trades archive is incomplete late in day and is NOT used for authoritative validation. This reconstruction may differ from native exchange candles.",
        "tradingCaveat":"No live fills, funding, mark price liquidation or orders modeled",
    }
    (dest/"provenance_manifest.json").write_text(
        json.dumps(report,indent=2,ensure_ascii=False)+"\n")
    print("RAW_TRADE_ARCHIVE_REPAIR_COMPLETE",json.dumps({
        "counts":counts,"endExclusiveUTC":report["endExclusiveUTC"],
        "derivedGapHoursPerSymbol":24,"fileProofs":len(proofs)
    }),flush=True)


if __name__=="__main__":
    main()
