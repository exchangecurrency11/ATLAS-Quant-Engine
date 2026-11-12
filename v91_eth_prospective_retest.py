#!/usr/bin/env python3
"""ETH V9.1 prospective MAX4H retest paper shadow, matched to immutable ETH V7.

No orders, user alerts, strategy edits, historical backfill or real execution
claims. Uses original ETH V7 Coinalyze Binance PERPETUAL sources. A missing
verified exact-hour original ETH capture refuses the hour entirely.
"""
import argparse
import json
import math
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from backtest_retest_long_v4 import replay_pair
from eth_v7_hourly_observer import (
    RESEARCH_PAIR, PERIODS, coinalyze_klines, validate_sources
)
from signal_quality_v7 import evaluate_bos_quality
from v7_forward_observer import iso, epoch, latest_events
from v91_prospective_retest import (
    HOUR, TIMEFRAME_SECONDS, OHLC_MAPPING,
    PRICE_REL_TOLERANCE, VOLUME_REL_TOLERANCE,
    path_at, fetch_json, safe_trade, require_exact_replay,
    retest_diagnostics, _first_commit_epoch, _statistics,
    current_hour_capture_window
)

MODE="V91_ETH_PROSPECTIVE_4H_RETEST_IMMUTABLE_PAPER_SHADOW"
VARIANTS=("V7_ORIGINAL","V91_RETEST_MAX4H")
BASE_BPS_SIDE=9
STRESS_BPS_SIDE=25

def verify_eth_source(original, rows, target):
    if (original.get("status")!="VERIFIED_PAPER_OBSERVATION"
        or original.get("mode")!="ETH_V7_INDEPENDENT_PAPER_FORWARD_NO_ORDERS"
        or original.get("paperForwardObservation") is not True
        or original.get("brokerOrders") is not False
        or original.get("productionSystemModified") is not False
        or original.get("symbol")!=RESEARCH_PAIR
        or not original.get("dataSource","").startswith("Coinalyze ETHUSDT_PERP.A / Binance perpetual")
        or epoch(original["targetClosed1HUTC"])!=target):
        raise ValueError("ETH_V91_MISSING_VERIFIED_EXACT_HOUR_V7_COINALYZE_PERP")
    reference=original["marketContext"][RESEARCH_PAIR]["timeframes"]
    audit={}
    for tf,period in TIMEFRAME_SECONDS.items():
        got=rows[tf][-1]
        src=reference[tf]
        required=target//period*period
        if epoch(src["closeTimeUTC"])!=required or got["t"]+period!=required:
            raise ValueError("ETH_V91_TIMEFRAME_CLOSE_MISMATCH_"+tf)
        diffs={}
        for name,k in OHLC_MAPPING.items():
            a=float(src["candle"][name]);v=float(got[k])
            if not (math.isfinite(a) and math.isfinite(v)) or a<=0 and name!="volume" or v<=0 and name!="volume" or a<0 or v<0:
                raise ValueError("ETH_V91_INVALID_OHLCV_"+tf+"_"+name)
            d=abs(a-v);rel=d/max(abs(a),1e-12)
            allowed=VOLUME_REL_TOLERANCE if name=="volume" else PRICE_REL_TOLERANCE
            if rel>allowed and d>1e-6:
                raise ValueError("ETH_V91_V7_COINALYZE_PARITY_FAILED_"+tf+"_"+name)
            diffs[name]=round(rel,10)
        audit[tf]={"closeUTC":iso(required),"verified":True,"relativeDifference":diffs,
                   "notIndependentBinanceExchangeTruth":True}
    return audit

def capture(original, raw, *, now, folder):
    target=now//HOUR*HOUR
    if not current_hour_capture_window(target,now):
        raise ValueError("ETH_V91_NOT_CURRENT_CLOSED_HOUR_WINDOW")
    if epoch(original["targetClosed1HUTC"])!=target:
        raise ValueError("ETH_V91_ORIGINAL_HOUR_MISMATCH")
    observed=epoch(original["observedAtUTC"])
    if not (target<=observed<=now+90 and observed<target+HOUR):
        raise ValueError("ETH_V91_NOT_CONTEMPORANEOUS_ORIGINAL_V7")
    parsed,signatures,cross=validate_sources(raw,target,now)
    integrity=verify_eth_source(original,parsed,target)
    history=(parsed["1hour"],parsed["4hour"],parsed["daily"])
    base=replay_pair(*history,as_of=target,retest_hours=6,bos_quality_filter=evaluate_bos_quality)
    alt=replay_pair(*history,as_of=target,retest_hours=4,bos_quality_filter=evaluate_bos_quality)
    if base["status"]!="PAPER_BACKTEST_NOT_LIVE" or alt["status"]!="PAPER_BACKTEST_NOT_LIVE":
        raise ValueError("ETH_V91_FULL_CAUSAL_PAPER_REPLAY_UNAVAILABLE")
    original_state=original["results"][RESEARCH_PAIR]["V7_signal_filter"]
    b=latest_events(base,target);a=latest_events(alt,target)
    require_exact_replay(original_state,b,symbol="ETHUSDT")
    for item in (b,a):
        for exit_trade in item["paperTradeExitsObservedAtThisClose"]:
            safe_trade(exit_trade,target)
        pending=item["currentPaperState"].get("pendingNextOpenPaperEntry")
        if pending is not None and pending.get("retestKnownUTC")!=target:
            raise ValueError("ETH_V91_PENDING_RETEST_NOT_NOW")
    snap={
       "mode":MODE,"symbol":"ETHUSDT","originalV7Reference":"ETHUSDT_PERP.A",
       "targetClosed1HUTC":iso(target),"capturedAtUTC":iso(now),
       "originalV7CapturedAtUTC":original["observedAtUTC"],
       "source":"Coinalyze Binance ETHUSDT perpetual; exact same instrument",
       "sourceIntegrity":integrity,
       "sourceSHA256NewFetch":signatures,
       "crossTimeframeOHLCV":cross,
       "verifiedSourceAndExactV7Replay":True,
       "independentBinanceMarketTruthEstablished":False,
       "BTCandSOLV91ScoreboardUnaffected":True,
       "retentionRuleHours":{"V7_ORIGINAL":6,"V91_RETEST_MAX4H":4},
       "sourceClose1H":parsed["1hour"][-1]["c"],
       "originalV7":b,"max4hRetest":a,
       "retestDiagnosticsOnlyNoEntryVeto":{
           "originalV7":retest_diagnostics(b,parsed["1hour"],target),
           "max4hRetest":retest_diagnostics(a,parsed["1hour"],target)},
       "noBackfill":True,
       "entryAtNextOpenIsHistoricalUnverifiedFill":True,
       "realTimeExecutableOrderCountVerified":0,
       "noUserNotifications":True,"noBrokerOrders":True,
       "V7AndV9ProductionAndSignalsUnchanged":True
    }
    output=path_at(folder,target)
    if output.exists():
        raise ValueError("ETH_V91_IMMUTABLE_HOUR_EXISTS")
    return snap,output

def prior_commit_evidence(trade, variant, folder):
    old_path=path_at(folder,int(trade["retestKnownUTC"]))
    if not old_path.is_file():
        return "NO_PRIOR_ETH_V91_RETEST_SNAPSHOT"
    prior=fetch_json(old_path)
    ret=int(trade["retestKnownUTC"]);exit_=int(trade["exitKnownUTC"])
    if (prior.get("mode")!=MODE or not prior.get("verifiedSourceAndExactV7Replay")
        or epoch(prior["targetClosed1HUTC"])!=ret):
        return "INVALID_PRIOR_ETH_V91_SNAPSHOT"
    captured=epoch(prior["capturedAtUTC"])
    comm=_first_commit_epoch(old_path)
    if (not(ret<=captured<ret+HOUR and captured<exit_)
        or comm is None or not(captured-90<=comm<ret+HOUR and comm<exit_)):
        return "PRIOR_ETH_V91_SNAPSHOT_NOT_EARLY_GIT_COMMITTED"
    field="originalV7" if variant=="V7_ORIGINAL" else "max4hRetest"
    pending=prior[field]["currentPaperState"].get("pendingNextOpenPaperEntry")
    if not pending:return "ETH_V91_RETEST_NOT_PRECOMMITTED_AS_PENDING"
    for k in ("retestKnownUTC","watchKnownUTC","side","stop"):
        if k not in pending or k not in trade:
            return "ETH_V91_ORIGINAL_TRADE_MISSING_KEY"
        if k=="stop":
            if not math.isclose(float(pending[k]),float(trade[k]),abs_tol=1e-7,rel_tol=1e-8):
                return "ETH_V91_SEALED_STOP_CHANGED"
        elif pending[k]!=trade[k]:
            return "ETH_V91_SEALED_RETEST_ID_CHANGED"
    return "EVIDENCED_PRIOR_SEALED_PAPER_RETEST"

def scoreboard(folder, current=None):
    seen={}
    root=Path(folder)
    for f in sorted(root.glob("*.json")):
        record=fetch_json(f)
        t=epoch(record["targetClosed1HUTC"])
        if (f!=path_at(root,t) or t in seen or
            record.get("mode")!=MODE or
            not record.get("verifiedSourceAndExactV7Replay") or
            record.get("noBrokerOrders") is not True or
            record.get("noUserNotifications") is not True):
            raise ValueError("ETH_V91_BAD_SAVED_IMMUTABLE_HOUR")
        seen[t]=record
    if current is not None:
        t=epoch(current["targetClosed1HUTC"])
        if t in seen:raise ValueError("ETH_V91_DUPLICATE_IMMUTABLE_HOUR")
        seen[t]=current
    ledger={v:[] for v in VARIANTS}
    excluded={v:[] for v in VARIANTS}
    for end,obj in sorted(seen.items()):
        for v,field in (("V7_ORIGINAL","originalV7"),
                        ("V91_RETEST_MAX4H","max4hRetest")):
            for trade in obj[field]["paperTradeExitsObservedAtThisClose"]:
                safe_trade(trade,end)
                reason=prior_commit_evidence(trade,v,root)
                if reason!="EVIDENCED_PRIOR_SEALED_PAPER_RETEST":
                    excluded[v].append({"exitUTC":iso(end),"reason":reason})
                    continue
                risk=float(trade["risk"]);entry=float(trade["entry"])
                net=float(trade["netRIllustrative"])
                stressed=net-2*(STRESS_BPS_SIDE-BASE_BPS_SIDE)/10000*entry/risk
                ledger[v].append({
                    "entryUTC":iso(trade["entryOpenUTC"]),"exitUTC":iso(end),
                    "side":trade["side"],
                    "netR9Bps":round(net,8),"netR25Bps":round(stressed,8),
                    "notExecutableFillProof":True})
    return {
       "mode":"V91_ETH_PROSPECTIVE_PAPER_SCOREBOARD",
       "asset":"ETHUSDT","savedDistinctVerifiedHours":len(seen),
       "firstActualSavedHourUTC":iso(min(seen)) if seen else None,
       "results":{k:_statistics(sorted(ledger[k],key=lambda x:(x["exitUTC"],x["entryUTC"])))
                  for k in VARIANTS},
       "tradeLedger":ledger,"excludedUnprovenExits":excluded,
       "noHistoricalBackfill":True,
       "realTimeExecutableEntryCountProven":0,
       "hypotheticalNextOpenExecutionNotProven":True,
       "notVerifiedProfitableStrategy":True,
       "BTCandSOLOriginalV91Undisturbed":True,
       "noBrokerOrders":True,"noNotifications":True,
       "noV7Modification":True
    }

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--v7-dir",default="v7_evidence/forward/eth/snapshots")
    p.add_argument("--out",default="forward/v91_eth_prospective_retest/hourly")
    p.add_argument("--score",default="forward/v91_eth_prospective_retest/scoreboard.json")
    p.add_argument("--now",type=int,default=None)
    args=p.parse_args()
    now=args.now if args.now is not None else int(time.time())
    target=(now//HOUR)*HOUR
    if not(12*60<=now-target<=57*60):
        print("ETH_V91_SKIP_OUTSIDE_CURRENT_HOUR",iso(target),flush=True)
        return
    folder=Path(args.out);destination=path_at(folder,target)
    if destination.exists():
        print("ETH_V91_SKIP_IMMUTABLE_ALREADY_CAPTURED",iso(target),flush=True)
        return
    original=path_at(args.v7_dir,target)
    if not original.is_file():
        print("ETH_V91_SKIP_NO_EXACT_V7_ETH_HOUR_NO_BACKFILL",iso(target),flush=True)
        return
    saved=fetch_json(original)
    if saved.get("status")!="VERIFIED_PAPER_OBSERVATION":
        print("ETH_V91_SKIP_UNVERIFIED_ORIGINAL_NO_SIGNAL",iso(target),flush=True)
        return
    key=os.environ.get("ETH_V7_COINALYZE_API_KEY","").strip()
    if not key:
        print("ETH_V91_SKIP_MISSING_READONLY_ETH_PROVIDER_CREDENTIAL_NO_SIGNAL",flush=True)
        return
    raw={tf:coinalyze_klines(tf,now,key) for tf in PERIODS}
    sample,path=capture(saved,raw,now=now,folder=folder)
    record=scoreboard(folder,current=sample)
    folder.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(sample,indent=2,ensure_ascii=False)+"\n")
    targetscore=Path(args.score)
    targetscore.parent.mkdir(parents=True,exist_ok=True)
    targetscore.write_text(json.dumps(record,indent=2,ensure_ascii=False)+"\n")
    print("ETH_V91_EXACT_V7_PAPER_PARITY_VERIFIED",iso(target),
          "scoreboardHours",record["savedDistinctVerifiedHours"],
          "noOrders",record["noBrokerOrders"],flush=True)

if __name__=="__main__":
    main()
