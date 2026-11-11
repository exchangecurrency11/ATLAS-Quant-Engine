#!/usr/bin/env python3
"""V9.1 strictly timestamped prospective OBSERVATION, 4h retest shadow only.

Research paper simulation: true execution/next-open fills NOT verified.
Never emits trading alerts, broker orders or changes original V7 logic.
Replays identical complete AVAILABLE rolling 1H/4H/Daily histories for the
original V7 and max4h alternative, and refuses any original-V7 state mismatch.
Cannot create a missed-hour observation retroactively.
Only counts completed research paper trades whose retest had been separately
captured and committed to Git BEFORE the simulated exit candle finished.
All observations are append-only; missing source = skip, not an invented trade.
"""
import argparse
from datetime import datetime, timezone
import json
import math
import subprocess
import time
from pathlib import Path
from backtest_retest_long_v4 import replay_pair
from signal_quality_v7 import evaluate_bos_quality
from v7_forward_observer import epoch, iso, validate_inputs, latest_events
from v91_retest_full_replay import strong_retest

HOUR=3600
SYM={"BTCUSDT":"BTCUSDT_PERP.A","SOLUSDT":"SOLUSDT_PERP.A"}
STRATEGIES=("V7_ORIGINAL","V91_RETEST_MAX4H")
MODE="V91_PROSPECTIVE_4H_RETEST_IMMUTABLE_PAPER_SHADOW"
BASE_BPS_SIDE=9
STRESS_BPS_SIDE=25


def path_at(base, t):
    return Path(base) / (datetime.fromtimestamp(t,timezone.utc).strftime("%Y-%m-%dT%H-00Z")+".json")


def fetch_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def safe_trade(t, close):
    required=("entryOpenUTC","exitKnownUTC","retestKnownUTC","watchKnownUTC","netRIllustrative","entry","risk","stop","side")
    if not all(x in t for x in required):
        raise ValueError("V91_MISSING_ORIGINAL_PAPER_TRADE_FIELD")
    if not (0<int(t["watchKnownUTC"])<int(t["retestKnownUTC"])<=int(t["entryOpenUTC"])<int(t["exitKnownUTC"])==close):
        raise ValueError("V91_FUTURE_OR_STALE_EXIT")
    if (float(t["entry"])<=0 or float(t["risk"])<=0 or
        not math.isfinite(float(t["netRIllustrative"]))):
        raise ValueError("V91_INVALID_PAPER_RISK_OR_COST")
    return True


def require_exact_replay(reference, derived, *, symbol):
    for field in ("newWatchAtThisClose","paperTradeExitsObservedAtThisClose",
                  "currentPaperState","diagnosticTotalRollingWindowAlerts",
                  "diagnosticTotalRollingWindowClosedTrades"):
        if reference[field]!=derived[field]:
            raise ValueError("V91_ORIGINAL_V7_REPLAY_STATE_PARITY_FAILED_"+symbol+"_"+field)



def retest_diagnostics(row, bars, target):
    """Record V9.1 retest features as CONTEXT, never as an entry veto."""
    pending=row["currentPaperState"].get("pendingNextOpenPaperEntry")
    if pending is None:
        return None
    if pending.get("retestKnownUTC")!=target or bars[-1]["t"]+HOUR!=target:
        raise ValueError("V91_DIAGNOSTIC_RETEST_TIMELINE_INVALID")
    active={"side":pending["side"],"level":pending["level"],
            "knownUTC":pending["watchKnownUTC"]}
    diagnostic=strong_retest(bars[-250:],active,bars[-1])
    features=diagnostic.get("features",{})
    if features.get("retestClosedAtUTC")!=target:
        raise ValueError("V91_DIAGNOSTIC_MISSING_CURRENT_RETEST_FEATURES")
    return {"observationOnlyNoVeto":True,
            "strongGateWouldPassButIsNotActive":bool(diagnostic["passed"]),
            "hypotheticalGateRejectionReasons":diagnostic["reasons"],
            "closed1HRetraceFeatures":features}


def capture(original, main, raw, *, now, folder):
    """Compute only CURRENT completed UTC hour; original V7 data must exist."""
    target=(now//HOUR)*HOUR
    if not (12*60<=now-target<=57*60):
        raise ValueError("V91_NOT_WITHIN_CONTEMPORANEOUS_12_TO_57_MIN_CLOSE_WINDOW")
    if original.get("status")!="VERIFIED_PAPER_OBSERVATION" or original.get("brokerOrders") is not False:
        raise ValueError("V91_ORIGINAL_V7_NOT_VERIFIED_PAPER_ONLY")
    if epoch(original["targetClosed1HUTC"])!=target:
        raise ValueError("V91_V7_NOT_MATCHED_TO_CURRENT_HOUR")
    recorded=epoch(original["observedAtUTC"])
    if not (target<=recorded<=now+90 and recorded<target+58*60):
        raise ValueError("V91_V7_SOURCE_NOT_SEALED_CONTEMPORANEOUSLY")
    parsed=validate_inputs(main,raw,target,now)
    if set(parsed)!={"1hour","4hour","daily"}:
        raise ValueError("V91_SOURCE_TIMELINES_MISSING")
    observed={}
    for symbol,ref in SYM.items():
        original_result=original["results"][ref]["V7_signal_filter"]
        h=parsed["1hour"][ref]
        h4=parsed["4hour"][ref]
        hd=parsed["daily"][ref]
        if h[-1]["t"]+HOUR !=target:
            raise ValueError("V91_LAST_CLOSED_HOUR_WRONG")
        c_v7=float(original["marketContext"][ref]["timeframes"]["1hour"]["candle"]["close"])
        if abs(c_v7-float(h[-1]["c"]))>max(1e-6,abs(c_v7)*2e-6):
            raise ValueError("V91_REPLAY_PRICE_PARITY_FAILED_"+symbol)
        base=replay_pair(h,h4,hd,as_of=target,
                         retest_hours=6,bos_quality_filter=evaluate_bos_quality)
        alt=replay_pair(h,h4,hd,as_of=target,
                        retest_hours=4,bos_quality_filter=evaluate_bos_quality)
        baseline=latest_events(base,target)
        candidate=latest_events(alt,target)
        require_exact_replay(original_result,baseline,symbol=symbol)
        if base["status"]!="PAPER_BACKTEST_NOT_LIVE" or alt["status"]!="PAPER_BACKTEST_NOT_LIVE":
            raise ValueError("V91_FULL_REPLAY_ENGINE_NOT_READY")
        for v in (baseline,candidate):
            for trade in v["paperTradeExitsObservedAtThisClose"]:
                safe_trade(trade,target)
            p=v["currentPaperState"].get("pendingNextOpenPaperEntry")
            if p is not None and p.get("retestKnownUTC")!=target:
                raise ValueError("V91_PENDING_RETEST_NOT_THIS_CLOSE")
        observed[symbol]={"sourceClose":float(h[-1]["c"]),
                          "originalV7":baseline,"max4hRetest":candidate,
                          "retestFeatureDiagnostics":{
                              "originalV7":retest_diagnostics(baseline,h,target),
                              "max4hRetest":retest_diagnostics(candidate,h,target)},
                          "featuresOnlyNoExtraRetestFilterApplied":True,
                          "separateFullSequentialReplay":True}
    snapshot={
        "mode":MODE,"targetClosed1HUTC":iso(target),
        "capturedAtUTC":iso(now),
        "originalV7ObservationAtUTC":original["observedAtUTC"],
        "mainSourceCheckedAtUTC":main["checkedAtUTC"],
        "retentionRuleHours":{"V7_ORIGINAL":6,"V91_RETEST_MAX4H":4},
        "sourceVerifiedSameHour":True,
        "V7SnapshotAndIndependentRecomputeExactMatch":True,
        "entryIsHistoricalNextOpenPaperAssumptionNotRealFill":True,
        "retrospectiveSnapshotBackfillForbidden":True,
        "noBrokerOrders":True,"noNotifications":True,
        "noV7ProductionOrNotificationChanges":True,
        "assets":observed}
    out=path_at(folder,target)
    if out.exists():
        raise ValueError("V91_IMMUTABLE_HOURLY_SNAPSHOT_EXISTS_DO_NOT_REWRITE")
    return snapshot,out


def _first_commit_epoch(path):
    """A prior snapshot is evidence only if its original Git commit predates exit."""
    try:
        run=subprocess.run(["git","log","--diff-filter=A","--format=%ct",
            "--",str(path)],check=True,capture_output=True,text=True,timeout=10)
    except (subprocess.SubprocessError,OSError):
        return None
    stamps=[int(x) for x in run.stdout.split() if x.isdecimal()]
    return min(stamps) if stamps else None


def _entry_evidence(snap,source_folder,variant,symbol,t):
    ret=int(t["retestKnownUTC"])
    before=path_at(source_folder,ret)
    if not before.is_file():
        return "RETEST_SNAPSHOT_NOT_CAPTURED_BEFORE_OUTCOME"
    earlier=fetch_json(before)
    if earlier.get("mode")!=MODE or not earlier.get("sourceVerifiedSameHour"):
        return "RETEST_ORIGINAL_SOURCE_UNVERIFIED"
    if epoch(earlier["targetClosed1HUTC"])!=ret:
        return "RETEST_SNAPSHOT_WRONG_TIME"
    captured=epoch(earlier["capturedAtUTC"])
    if not (ret<=captured<ret+HOUR and captured<int(t["exitKnownUTC"])):
        return "RETEST_CAPTURE_WAS_TOO_LATE"
    committed=_first_commit_epoch(before)
    if committed is None or not (captured-90<=committed<ret+HOUR and committed<int(t["exitKnownUTC"])):
        return "RETEST_NOT_PROVEN_FIRST_COMMITTED_BEFORE_PAPER_EXIT"
    field="originalV7" if variant=="V7_ORIGINAL" else "max4hRetest"
    pending=earlier["assets"][symbol][field]["currentPaperState"]["pendingNextOpenPaperEntry"]
    if pending is None:
        return "RETEST_WAS_NOT_SEALED_AS_PENDING"
    for key in ("retestKnownUTC","watchKnownUTC","side","stop"):
        if key not in pending:
            return "SEALED_RETEST_MISSING_REQUIRED_FIELD"
        a=pending[key];b=t[key]
        if key=="stop":
            if not math.isclose(float(a),float(b),rel_tol=1e-8,abs_tol=1e-7):
                return "SEALED_RETEST_STOP_CHANGED"
        elif a!=b:
            return "SEALED_RETEST_NOT_SAME_PAPER_TRADE"
    return "ELIGIBLE_PAPER_EXIT_EVIDENCED_BY_PRIOR_GIT_COMMIT"


def _statistics(rows):
    values=[x["netR9Bps"] for x in rows]
    stressed=[x["netR25Bps"] for x in rows]
    wins=sum(x>0 for x in values)
    gain=sum(max(0,x) for x in values)
    loss=-sum(min(0,x) for x in values)
    peak=eq=dd=0.
    for x in rows:
        eq+=x["netR9Bps"]
        peak=max(peak,eq);dd=max(dd,peak-eq)
    return {
        "eligibleClosedPaperTrades":len(values),
        "wins":wins,
        "winRatePct":round(100*wins/len(values),2) if values else None,
        "totalNetR9BpsPerSide":round(sum(values),4),
        "averageNetR9BpsPerSide":round(sum(values)/len(values),4) if values else None,
        "totalNetR25BpsPerSide":round(sum(stressed),4),
        "profitFactorR":round(gain/loss,3) if loss else None,
        "maxDrawdownR":round(dd,4)
    }


def scoreboard(folder, *, current=None, current_path=None):
    """Sealed contemporary hourly snapshots only; never count unmatched old exits."""
    saved={}
    root=Path(folder)
    for path in sorted(root.glob("*.json")):
        obj=fetch_json(path)
        t=epoch(obj["targetClosed1HUTC"])
        if path!=path_at(root,t):
            raise ValueError("V91_SNAPSHOT_NAME_MISMATCH")
        if t in saved:
            raise ValueError("V91_DUPLICATE_HOURLY_CAPTURE")
        if obj.get("mode")!=MODE or not obj.get("V7SnapshotAndIndependentRecomputeExactMatch"):
            raise ValueError("V91_UNVERIFIED_HOURLY_SNAPSHOT")
        saved[t]=obj
    if current is not None:
        target=epoch(current["targetClosed1HUTC"])
        if target in saved:
            raise ValueError("V91_WOULD_OVERWRITE_ALREADY_SEALED_HOUR")
        saved[target]=current
    counted={s:{v:[] for v in STRATEGIES} for s in SYM}
    skipped={s:{v:[] for v in STRATEGIES} for s in SYM}
    for end,snap in sorted(saved.items()):
        for sym in SYM:
            for name,field in (("V7_ORIGINAL","originalV7"),("V91_RETEST_MAX4H","max4hRetest")):
                for trade in snap["assets"][sym][field]["paperTradeExitsObservedAtThisClose"]:
                    safe_trade(trade,end)
                    reason=_entry_evidence(snap,root,name,sym,trade)
                    if reason!="ELIGIBLE_PAPER_EXIT_EVIDENCED_BY_PRIOR_GIT_COMMIT":
                        skipped[sym][name].append({"exitUTC":iso(end),"reason":reason})
                        continue
                    val=float(trade["netRIllustrative"])
                    stress=val-2*(STRESS_BPS_SIDE-BASE_BPS_SIDE)/10000*float(trade["entry"])/float(trade["risk"])
                    counted[sym][name].append({
                        "entryUTC":iso(trade["entryOpenUTC"]),"exitUTC":iso(end),
                        "side":trade["side"],"netR9Bps":round(val,8),
                        "netR25Bps":round(stress,8),
                        "paperOnlyNoRealExecution":True,
                        "diagnosticAtPreviouslySealedRetest":fetch_json(path_at(root,int(trade["retestKnownUTC"])))
                        ["assets"][sym].get("retestFeatureDiagnostics",{}).get(field)})
    result={
        "mode":"V91_PROSPECTIVE_CAUSAL_PAPER_SCOREBOARD",
        "sinceFirstActualSavedVerifiedCaptureUTC":iso(min(saved)) if saved else None,
        "savedDistinctVerifiedHours":len(saved),
        "results":{s:{v:_statistics(sorted(counted[s][v],key=lambda x:(x["exitUTC"],x["entryUTC"])))
                      for v in STRATEGIES} for s in SYM},
        "excludedUnsealedOrUnprovenPaperExits":{s:{v:skipped[s][v] for v in STRATEGIES} for s in SYM},
        "tradeLedger":counted,
        "originalV7Untouched":True,
        "noBackfilledOrPostSelectedTrades":True,
        "missingHourObservationsMustNotBeFilled":True,
        "prospectiveCaptureNotProspectiveActualOrderFill":True,
        "feesSlippage9BpsPerSideStress25BpsPerSide":True,
        "fundingVariableSpreadTrueFillsLiquidationNotModeled":True,
        "thresholdsNotReoptimizedFromNewObservations":True,
        "noNotifications":True,"noBrokerOrders":True,
        "notVerifiedProfitableStrategy":True}
    return result


def main():
    a=argparse.ArgumentParser()
    a.add_argument("--v7-dir",default="v7_evidence/forward/snapshots")
    a.add_argument("--market",default="forward/tmp/v91_main_market.json")
    a.add_argument("--history-dir",default="forward/tmp/v91_history")
    a.add_argument("--out",default="forward/v91_prospective_retest/hourly")
    a.add_argument("--scoreboard",default="forward/v91_prospective_retest/scoreboard.json")
    a.add_argument("--now-epoch",type=int,default=None)
    args=a.parse_args()
    now=args.now_epoch if args.now_epoch is not None else int(time.time())
    target=now//HOUR*HOUR
    root=Path(args.out)
    previous=path_at(root,target)
    if previous.exists():
        print("V91_SKIPPED_ALREADY_IMMUTABLY_RECORDED_HOUR",iso(target),flush=True)
        return
    original=path_at(args.v7_dir,target)
    if not original.is_file():
        print("V91_SKIPPED_MISSING_EXACT_CONTEMPORANEOUS_ORIGINAL_V7_SNAPSHOT",iso(target),flush=True)
        return
    main_data=fetch_json(args.market)
    history={}
    for tf in ("1hour","4hour","daily"):
        history[tf]=fetch_json(Path(args.history_dir)/("history_"+tf+".json"))
    snap,path=capture(fetch_json(original),main_data,history,now=now,folder=root)
    summary=scoreboard(root,current=snap,current_path=path)
    root.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(snap,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    score=Path(args.scoreboard);score.parent.mkdir(parents=True,exist_ok=True)
    score.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("V91_VERIFIED_CONTEMPORANEOUS_V7_PARITY_PAPER_ONLY_NO_ALERT",iso(target),
          json.dumps(summary["results"]),flush=True)


if __name__=="__main__":
    main()
