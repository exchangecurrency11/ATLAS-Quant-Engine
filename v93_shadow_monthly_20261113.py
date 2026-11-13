#!/usr/bin/env python3
"""Immutable prospective monthly shadow V9.2 vs frozen V9.3 hypotheses.
Research only: ZERO orders, notifications, current V7/V9.2 account writes.
Uses only COMPLETE SHA256-checked official Binance USD-M 1h monthly history.
Monthly reporting delay is deliberate: NOT intraday monitoring or fill proof.
"""
import argparse
import calendar
import hashlib
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime,timezone
import v92_filter_ablation_20261113 as old
from download_binance_um_history import months_inclusive,download_month,aggregate
import v92_full_interactions_20261113 as full

FREEZE="2026-11-14T00:00:00Z"
FREEZE_EPOCH=old.epoch(FREEZE)
WARMUP_FIRST="2026-04"
CANDIDATES={
    "BTC_V92_REFERENCE":("BTCUSDT","BASELINE",()),
    "ETH_V92_REFERENCE":("ETHUSDT","BASELINE",()),
    "SOL_V92_REFERENCE":("SOLUSDT","BASELINE",()),
    "ETH_BOS_EMA_RELAX":("ETHUSDT","PAIR_NO_BREAK_ATR_AND_EMA_EXT",
                         ("bos_break_atr","bos_ema_extension")),
    "ETH_BOS_RETEST6":("ETHUSDT","PAIR__bos_break_atr__retest_window",
                        ("bos_break_atr","retest_window")),
    "SOL_VOLUME_RELAX":("SOLUSDT","NO_1H_VOLUME_SURGE_20PCT",
                        ("volume_burst",)),
}
assert len(CANDIDATES)==6 and len({k for k in CANDIDATES})==6
assert all(tuple(old.ABLATIONS.get(mode,full.VARIANTS.get(mode,())))==gates
           for _,mode,gates in CANDIDATES.values())
OUTPUT=Path("forward/v93_shadow_prospective_20261113")
FROZEN_SOURCE=("v92_filter_ablation_20261113.py",
               "v92_full_interactions_20261113.py",
               "backtest_retest_long_v4.py",
               "signal_quality_v7.py",
               "v92_selected_reversal_patterns.py",
               "v92_four_candle_models_20261113.py",
               "market_structure.py")

def previous_complete_month(now):
    if now.tzinfo is None:
        raise ValueError("UTC_TIMEZONE_REQUIRED")
    year,month=now.astimezone(timezone.utc).year,now.astimezone(timezone.utc).month
    return f"{year-1:04d}-12" if month==1 else f"{year:04d}-{month-1:02d}"

def download_hist(end_month,workers):
    months=months_inclusive(WARMUP_FIRST,end_month)
    if not 1<=len(months)<=36:
        raise ValueError("PROSPECTIVE_MONTH_SPAN_NOT_SUPPORTED")
    source={}
    data={}
    tasks={}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for symbol in old.SYMBOLS:
            for month in months:
                tasks[pool.submit(download_month,symbol,month)]=(symbol,month)
        for task in as_completed(tasks):
            sym,mon,rows,proof=task.result()
            if (sym,mon)!=(symbol:=sym,month:=mon) or proof["bars"]!=len(rows):
                raise ValueError("SHA256_ARCHIVE_DATA_MISMATCH")
            data[(sym,mon)]=rows
            source[f"{sym}:{mon}"]=proof["sha256"]
            print("PROSPECTIVE_SHA256",sym,mon,len(rows),flush=True)
    histories={}
    start=old.epoch("2026-04-01T00:00:00Z")
    end=old.epoch((f"{int(end_month[:4])+1:04d}-01-01" if end_month.endswith("-12")
                   else f"{end_month[:4]}-{int(end_month[5:])+1:02d}-01")+"T00:00:00Z")
    for symbol in old.SYMBOLS:
        hour=[bar for month in months for bar in data[(symbol,month)]]
        if (len(hour)!=(end-start)//3600 or
            any(b["t"]!=start+i*3600 for i,b in enumerate(hour))):
            raise ValueError("PROSPECTIVE_HOURLY_GAP_DUPLICATE_OR_REORDER")
        histories[symbol]=hour
    return histories,source,end

def source_hashes():
    return {p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
            for p in FROZEN_SOURCE}

def frozen_spec():
    return {"freezeUTC":FREEZE,
            "warmupFirstUTC":"2026-04-01T00:00:00Z",
            "candidates":{k:{"symbol":s,"mode":mode,"disabledGates":list(gates)}
                          for k,(s,mode,gates) in CANDIDATES.items()},
            "immutableEngineHashes":source_hashes(),
            "costPerSideBps":[9,25],
            "entryEligibility":"watchKnownUTC >= freeze AND retestKnownUTC >= freeze AND entryOpenUTC >= freeze",
            "causalStructure":list(old.CONTROL_REQUIREMENTS),
            "realOrders":False,"currentV7V92AccountWrites":False,
            "notifications":False}

def replay_all(histories,end):
    reports={}
    for sym,hour in histories.items():
        four,daily=old.double_checked_candles(hour,end)
        cache={"indicators":{
            **old.exact_streaming_indicator_cache(hour),
            **old.exact_streaming_indicator_cache(four),
            **old.exact_streaming_indicator_cache(daily),
        },"bias":{},"structures":{}}
        for label,(symbol,mode,gates) in CANDIDATES.items():
            if symbol!=sym:
                continue
            engine,quality=old.instrumentation(
                mode,symbol=symbol,four=four,cache=cache)
            audit=old.Counter(examples=[])
            gate=(old.make_selective_gate(
                symbol,four,"SELECTED_SOL_STRICT_SWEEP",audit)
                if symbol=="SOLUSDT" and "sol_reversal" not in gates else None)
            output=engine(hour,four,daily,as_of=end,
                          retest_hours=6 if "retest_window" in gates else 4,
                          bos_quality_filter=quality,
                          retest_quality_filter=gate)
            if output["status"]!="PAPER_BACKTEST_NOT_LIVE":
                raise ValueError("PROSPECTIVE_INSUFFICIENT_REFERENCE_HISTORY")
            # A setup started before freeze is NOT a prospective observation.
            trades=[t for t in output["trades"]
                    if t["watchKnownUTC"]>=FREEZE_EPOCH and
                    t["retestKnownUTC"]>=FREEZE_EPOCH and
                    t["entryOpenUTC"]>=FREEZE_EPOCH and
                    t["exitKnownUTC"]<=end]
            # Incomplete positions stay observational; do not claim realized R.
            t25=full.compact_metrics(trades,25)
            t9=full.compact_metrics(trades,9)
            rows=[{
                "side":t["side"],"watchKnownUTC":old.stamp(t["watchKnownUTC"]),
                "retestKnownUTC":old.stamp(t["retestKnownUTC"]),
                "entryOpenUTC":old.stamp(t["entryOpenUTC"]),
                "exitKnownUTC":old.stamp(t["exitKnownUTC"]),
                "entry":t["entry"],"stop":t["stop"],
                "targets":t["targets"],"exitReason":t["exitReason"],
                "netR9Bps":round(t["netRIllustrative"],7),
                "netR25Bps":round(full.returns_for([t],25)[0],7)}
                for t in trades]
            reports[label]={
                "symbol":symbol,"mode":mode,"disabledGates":list(gates),
                "closedProspectiveTrades":rows,
                "metrics9Bps":t9,"metrics25Bps":t25,
                "openOrPendingAtLastClose":{
                    "position":output["forwardStateAtLastClose"]["openHypotheticalPosition"] is not None,
                    "pending":output["forwardStateAtLastClose"]["pendingNextOpenPaperEntry"] is not None},
                "unresolvedNotCredited":True,
                "noBackfilledHistoricalTrades":True,
                "isActualExecution":False}
    return reports

def immutable_check_or_write(path,content):
    serialized=json.dumps(content,ensure_ascii=False,indent=2,sort_keys=True)+"\n"
    if path.exists():
        if path.read_text()!=serialized:
            raise ValueError("SHADOW_IMMUTABLE_SNAPSHOT_OR_FROZEN_SPEC_DRIFT:"+str(path))
    else:
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(serialized)

def validate_candidate_prospective(out):
    for label,v in out.items():
        prev=None
        for row in v["closedProspectiveTrades"]:
            stamps=[old.epoch(row[k]) for k in
                    ("watchKnownUTC","retestKnownUTC","entryOpenUTC","exitKnownUTC")]
            if not (FREEZE_EPOCH<=stamps[0]<stamps[1]<=stamps[2]<stamps[3]):
                raise ValueError("PROSPECTIVE_TRADE_CHRONOLOGY")
            if prev is not None and stamps[2]<=prev:
                raise ValueError("PROSPECTIVE_REPLAY_NONCHRONOLOGICAL")
            prev=stamps[2]
        if v["metrics9Bps"]["trades"]!=len(v["closedProspectiveTrades"]):
            raise ValueError("PROSPECTIVE_METRICS_DISAGREE")
        if v["metrics25Bps"]["trades"]!=len(v["closedProspectiveTrades"]):
            raise ValueError("PROSPECTIVE_STRESS_METRICS_DISAGREE")

def run(end_month,workers,dest):
    old.fork_source()  # prior baseline exact source pattern guard
    old.ABLATIONS.update({mode:gates for _,mode,gates in CANDIDATES.values()})
    spec=frozen_spec()
    immutable_check_or_write(dest/"frozen_spec.json",spec)
    hist,source,end=download_hist(end_month,workers)
    if end>old.epoch(datetime.now(timezone.utc).isoformat()):
        raise ValueError("PROSPECTIVE_INCOMPLETE_MONTH_NOT_ALLOWED")
    trials=replay_all(hist,end)
    validate_candidate_prospective(trials)
    day=datetime.fromtimestamp(end,timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    packet={
        "status":"PROSPECTIVE_MONTHLY_SHADOW_ONLY" if end>FREEZE_EPOCH else "PREFREEZE_PIPELINE_SMOKE_TEST",
        "asOfExclusiveUTC":day,"startProspectiveUTC":FREEZE,
        "verifiedArchives":len(source),"archiveSHA256":dict(sorted(source.items())),
        "sourceHashSHA256":spec["immutableEngineHashes"],
        "archiveMayArriveAfterMonthEnd":True,
        "notRealtimeAlerts":True,"neverRealOrders":True,
        "cannotCreditAnyPreFreezeTrade":True,
        "noExistingV7V92AccountWrites":True,
        "periodPreviouslyBacktestedForTraining":end<=FREEZE_EPOCH,
        "reportedStreams":trials}
    if end<=FREEZE_EPOCH:
        (dest/"preflight.json").write_text(json.dumps(packet,ensure_ascii=False,indent=2,sort_keys=True)+"\n")
    else:
        # Each month frozen once; replay for new month must not rewrite prior snapshot.
        immutable_check_or_write(dest/"snapshots"/f"{end_month}.json",packet)
        (dest/"latest.json").write_text(json.dumps(packet,ensure_ascii=False,indent=2,sort_keys=True)+"\n")
    return packet

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--last-complete-month",default=None)
    p.add_argument("--workers",type=int,default=6)
    p.add_argument("--out",default=str(OUTPUT))
    args=p.parse_args()
    if not 1<=args.workers<=6:
        p.error("workers 1..6")
    latest=previous_complete_month(datetime.now(timezone.utc))
    end_month=args.last_complete_month or latest
    if end_month>latest:
        p.error("cannot replay a future or incomplete monthly archive")
    if end_month<"2026-10":
        p.error("preflight requires >= 2026-10")
    report=run(end_month,args.workers,Path(args.out))
    print("V93_SHADOW",report["status"],report["asOfExclusiveUTC"],
          [(x,v["metrics25Bps"]["trades"]) for x,v in report["reportedStreams"].items()])
if __name__=="__main__":
    main()
