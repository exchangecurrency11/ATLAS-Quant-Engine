#!/usr/bin/env python3
"""Independent ETH Futures USD-M 1h DAILY archive integrity guard.

Research-only additive SHA256 evidence ledger; NO trading decisions, orders,
notifications, edits to frozen V9.3 specs, production code or accounts.
Daily archive is available *after* the UTC day finishes, subject to Binance
publication delays. Missing, invalid, reordered or revised data FAIL CLOSED.
This is separate from the canonical frozen six-stream monthly replay.
"""
import argparse
import csv
from datetime import date,datetime,timezone,timedelta
from hashlib import sha256
from io import BytesIO,TextIOWrapper
import json
import math
from pathlib import Path
from zipfile import ZipFile

from download_binance_um_history import get

SYMBOL="ETHUSDT"
FREEZE="2026-11-14T00:00:00Z"
FIRST=date(2026,11,14)
END=date(2026,11,30)
PREFLIGHT=date(2026,11,13)
HOUR=3600
BASE="https://data.binance.vision/data/futures/um/daily/klines"
OUT=Path("forward/eth_v93_daily_data_guard_20261114")

def iso(d):
    return d.isoformat()

def utc_start(d):
    return int(datetime(d.year,d.month,d.day,tzinfo=timezone.utc).timestamp())

def parse_daily(data,day):
    label=iso(day)
    filename=f"{SYMBOL}-1h-{label}.csv"
    with ZipFile(BytesIO(data)) as archive:
        entries=[n for n in archive.namelist() if n.endswith(".csv")]
        if len(entries)!=1 or entries[0].split("/")[-1]!=filename:
            raise ValueError("ETH_DAY_ZIP_CSV_NAME_MISMATCH")
        if archive.getinfo(entries[0]).file_size>1_000_000:
            raise ValueError("ETH_DAY_TOO_LARGE_UNCOMPRESSED")
        with archive.open(entries[0]) as raw:
            reader=csv.reader(TextIOWrapper(raw,encoding="utf-8-sig"))
            bars=[]
            for record in reader:
                if not record:continue
                if record[0].strip().lower() in ("open time","open_time"):
                    continue
                if len(record)<6 or 6<len(record)<11:
                    raise ValueError("ETH_DAY_MALFORMED_KLINE_FIELDS")
                value=int(record[0])
                ts=(value//1_000_000 if value>100_000_000_000_000
                    else value//1000 if value>100_000_000_000 else value)
                o,h,l,c,v=map(float,record[1:6])
                if not (all(math.isfinite(q) for q in (o,h,l,c,v))
                        and l>0 and l<=min(o,c)<=max(o,c)<=h and v>=0):
                    raise ValueError("ETH_DAY_OHLCV_MALFORMED")
                if len(record)>=11:
                    qv=float(record[7]); count=int(record[8])
                    tbv=float(record[9]);tbq=float(record[10])
                    if not (all(math.isfinite(q) for q in (qv,tbv,tbq))
                        and count>=0 and qv>=0
                        and 0<=tbv<=v+max(1e-8,v*1e-7)
                        and 0<=tbq<=qv+max(1e-6,qv*1e-7)):
                        raise ValueError("ETH_DAY_TAKER_FLOW_MALFORMED")
                bars.append((ts,o,h,l,c,v))
    start=utc_start(day)
    if len(bars)!=24:
        raise ValueError(f"ETH_DAY_INCOMPLETE_{label}_{len(bars)}_BARS")
    if any(b[0]!=start+i*HOUR for i,b in enumerate(bars)):
        raise ValueError(f"ETH_DAY_HOURLY_GAPS_DUPLICATES_{label}")
    return bars

def verify(day):
    label=iso(day)
    url=f"{BASE}/{SYMBOL}/1h/{SYMBOL}-1h-{label}.zip"
    blob=get(url,max_size=7_000_000)
    proof=get(url+".CHECKSUM",max_size=2000).decode("utf-8-sig").strip().split()
    if not proof or len(proof[0])!=64 or any(c not in "0123456789abcdef" for c in proof[0].lower()):
        raise ValueError("ETH_DAY_MISSING_OR_MALFORMED_SHA256_PROOF")
    digest=sha256(blob).hexdigest()
    if digest!=proof[0].lower():
        raise ValueError("ETH_DAY_CHECKSUM_MISMATCH")
    bars=parse_daily(blob,day)
    return {
        "dateUTC":label,
        "officialSource":url,
        "zipSHA256":digest,
        "hourlyClosedCandles":len(bars),
        "firstCandleOpenUTC":datetime.fromtimestamp(bars[0][0],timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "lastCandleCloseUTC":datetime.fromtimestamp(bars[-1][0]+HOUR,timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "completeUTCday":True,
        "verifiedDirectWithOfficialChecksum":True
    }

def day_span(start,end):
    if start>end:return []
    return [start+timedelta(days=i) for i in range((end-start).days+1)]

def valid_ledger(existing):
    if (existing.get("schema")!="ETH_DAILY_V93_SOURCE_CHECKSUM_LEDGER"
        or existing.get("freezeUTC")!=FREEZE
        or existing.get("symbol")!=SYMBOL):
        raise ValueError("ETH_EXISTING_LEDGER_WRONG_IDENTITY")
    for key,v in existing.get("days",{}).items():
        d=date.fromisoformat(key)
        if not (FIRST<=d<=END or d==PREFLIGHT) or v["dateUTC"]!=key:
            raise ValueError("ETH_EXISTING_LEDGER_BAD_DATE")
        if not (v["hourlyClosedCandles"]==24 and len(v["zipSHA256"])==64
                and v["verifiedDirectWithOfficialChecksum"]):
            raise ValueError("ETH_EXISTING_LEDGER_UNVERIFIED_ENTRY")
    return True

def run(dest,now,preflight=False):
    today=now.astimezone(timezone.utc).date()
    previous=today-timedelta(days=1)
    last=min(previous,END)
    dates=([PREFLIGHT] if preflight else day_span(FIRST,last))
    # Only safe known historical date is permitted for one-time preflight.
    if preflight and previous<PREFLIGHT:
        raise ValueError("ETH_PREFLIGHT_DATE_NOT_YET_COMPLETED")
    if not preflight and previous<FIRST:
        raise ValueError("ETH_FIRST_PROSPECTIVE_UTC_DAY_NOT_COMPLETED_YET")
    ledgerfile=dest/"daily_ledger.json"
    ledger=(json.loads(ledgerfile.read_text()) if ledgerfile.exists()
            else {"schema":"ETH_DAILY_V93_SOURCE_CHECKSUM_LEDGER","symbol":SYMBOL,
                  "freezeUTC":FREEZE,"sourceType":"Binance official USD-M futures ETHUSDT 1h DAILY ZIPs",
                  "noTradeResultsOrRetroactivePaperCredits":True,
                  "noOrders":True,"noNotifications":True,"noProductionChanges":True,
                  "days":{}})
    valid_ledger(ledger)
    for day in dates:
        entry=verify(day)
        key=iso(day)
        if key in ledger["days"] and ledger["days"][key]!=entry:
            raise ValueError("ETH_EXISTING_DAILY_PROOF_MUTATED_REQUIRES_MANUAL_INVESTIGATION")
        ledger["days"][key]=entry
        print("VERIFIED_ETH_24_HOURLY_BARS_SHA256",key,entry["zipSHA256"],flush=True)
    expected=[iso(d) for d in day_span(FIRST,last)]
    observed=sorted(k for k in ledger["days"] if k in expected)
    if not preflight and observed!=expected:
        raise ValueError("ETH_DAILY_COVERAGE_GAP")
    result={
        "schema":ledger["schema"],"freezeUTC":FREEZE,"symbol":SYMBOL,
        "preflightOnly":preflight,"checkedAtUTC":now.astimezone(timezone.utc).isoformat(),
        "lastCompletedDayExpectedUTC":iso(last) if not preflight else None,
        "checkedProspectiveDays":len(observed),"eligibleCompleteDaysExpected":len(expected),
        "completeSinceFirstProspectiveUTC":observed==expected,
        "dailySourceSHA256Verified":len(dates),
        "monthlyStrategyReplayNotRun":True,
        "noProspectiveTradesClaimed":True,
        "noOrders":True,"noNotifications":True,"noProductionChanges":True,
        "noAutomaticDailySchedulerInThisWorkflow":True
    }
    dest.mkdir(parents=True,exist_ok=True)
    ledgerfile.write_text(json.dumps(ledger,ensure_ascii=False,sort_keys=True,indent=2)+"\n")
    (dest/"coverage_status.json").write_text(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2)+"\n")
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out",default=str(OUT))
    p.add_argument("--preflight",action="store_true",
                   help="verify last fully-completed Nov 13 day; never claim forward evidence")
    args=p.parse_args()
    result=run(Path(args.out),datetime.now(timezone.utc),args.preflight)
    print("ETH_DAILY_1H_SHA256_COVERAGE_GUARD",json.dumps(result,sort_keys=True))
if __name__=="__main__":
    main()
