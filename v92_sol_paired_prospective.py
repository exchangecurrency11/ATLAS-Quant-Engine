#!/usr/bin/env python3
"""Paired, immutable prospective SOL comparison: V9.1 baseline vs V9.2 filter.

Only same-hour V7/V9.1 parity-sealed V92 snapshots are used. The baseline and
filtered arms replay the same source candles. A trade is eligible only when its
retest snapshot was committed before the hypothetical exit close. No backfill,
orders, alerts, or live-strategy changes. Next-open fills remain unverified.
"""
import argparse
from collections import Counter
import json
import math
from pathlib import Path

from v91_prospective_retest import safe_trade
from v92_prospective_selected import (
    FIRST, MODE, epoch, iso, load_all, path_at, verified_first_commit
)

SYMBOL="SOLUSDT"
ARMS={
    "V91_UNFILTERED_CONTROL":"originalV91",
    "V92_STAR_HARAMI_SWEEP_FILTER":"selectedV92",
}
MIN_CLOSED_CONTROL_TRADES=30
MIN_SEALED_VETO_EVENTS=5


def trade_evidence(folder, trade, arm_field):
    ret=int(trade["retestKnownUTC"])
    path=path_at(folder,ret)
    if not path.is_file():
        return "NO_PREVIOUSLY_CAPTURED_RETEST_HOUR"
    earlier=json.loads(path.read_text(encoding="utf-8"))
    if (earlier.get("mode")!=MODE
        or earlier.get("sourceV7AndV91RecomputedExactMatch") is not True
        or epoch(earlier.get("targetClosed1HUTC",""))!=ret):
        return "RETEST_SOURCE_UNVERIFIED"
    captured=epoch(earlier["capturedAtUTC"])
    commit=verified_first_commit(".",path)
    exit_close=int(trade["exitKnownUTC"])
    if (commit is None or not ret<=captured<ret+3600
        or not captured-90<=commit<ret+3600
        or commit>=exit_close):
        return "RETEST_NOT_GIT_SEALED_BEFORE_EXIT"
    pending=earlier["assets"][SYMBOL][arm_field]["currentPaperState"].get(
        "pendingNextOpenPaperEntry")
    if pending is None:
        return "NO_PRECOMMITTED_PENDING_RETEST_IN_"+arm_field
    for key in ("side","watchKnownUTC","retestKnownUTC","stop"):
        if key not in pending or key not in trade:
            return "RETEST_REQUIRED_FIELD_MISSING"
        if key=="stop":
            if not math.isclose(float(pending[key]),float(trade[key]),
                                rel_tol=1e-8,abs_tol=1e-7):
                return "RETEST_STOP_MISMATCH"
        elif pending[key]!=trade[key]:
            return "RETEST_FIELD_MISMATCH_"+key
    return "PRECOMMITTED_"+arm_field+"_RETEST_BEFORE_EXIT"


def key_of(trade):
    entry_value=trade.get("entryUTC",trade.get("entryOpenUTC"))
    entry_epoch=epoch(entry_value) if isinstance(entry_value,str) else int(entry_value)
    return (
        int(trade["watchKnownUTC"]),int(trade["retestKnownUTC"]),
        entry_epoch,trade["side"],round(float(trade["stop"]),8)
    )


def score(trades):
    ordered=sorted(trades,key=lambda x:(x["exitUTC"],x["entryUTC"]))
    rs=[float(x["netR9Bps"]) for x in ordered]
    wins=sum(x>0 for x in rs)
    losses=sum(x<=0 for x in rs)
    gross_win=sum(x for x in rs if x>0)
    gross_loss=sum(x for x in rs if x<0)
    equity=peak=drawdown=0.0
    for value in rs:
        equity+=value
        peak=max(peak,equity)
        drawdown=max(drawdown,peak-equity)
    return {
        "trades":len(rs),"wins":wins,"losses":losses,
        "winRatePct":round(100*wins/len(rs),2) if rs else None,
        "netR":round(sum(rs),6),
        "stressNetR":round(sum(float(x["netR25Bps"]) for x in ordered),6),
        "averageR":round(sum(rs)/len(rs),6) if rs else None,
        "profitFactor":round(gross_win/abs(gross_loss),4) if gross_loss<0 else None,
        "maxDrawdownR":round(drawdown,6),
        "tradeLedger":ordered,
    }


def build(folder):
    folder=Path(folder)
    snapshots=load_all(folder)
    ledgers={name:[] for name in ARMS}
    excluded={name:Counter() for name in ARMS}
    for closed,snapshot in sorted(snapshots.items()):
        asset=snapshot["assets"][SYMBOL]
        for arm,field in ARMS.items():
            events=asset[field]["paperTradeExitsObservedAtThisClose"]
            for trade in events:
                safe_trade(trade,closed)
                if not (int(trade["retestKnownUTC"])>=FIRST
                        and int(trade["entryOpenUTC"])>=FIRST
                        and int(trade["exitKnownUTC"])>=FIRST+3600):
                    excluded[arm]["BEFORE_FORWARD_START"]+=1
                    continue
                reason=trade_evidence(folder,trade,field)
                if reason!="PRECOMMITTED_"+field+"_RETEST_BEFORE_EXIT":
                    excluded[arm][reason]+=1
                    continue
                net=float(trade["netRIllustrative"])
                stress=net-2*(25-9)/10000*float(trade["entry"])/float(trade["risk"])
                ledgers[arm].append({
                    "symbol":SYMBOL,"entryUTC":iso(int(trade["entryOpenUTC"])),
                    "exitUTC":iso(closed),"side":trade["side"],
                    "watchKnownUTC":int(trade["watchKnownUTC"]),
                    "retestKnownUTC":int(trade["retestKnownUTC"]),
                    "entry":float(trade["entry"]),"stop":float(trade["stop"]),
                    "exitReason":trade.get("exitReason"),
                    "netR9Bps":round(net,8),"netR25Bps":round(stress,8),
                    "notVerifiedExecutableRealFill":True,
                })
    summaries={name:score(rows) for name,rows in ledgers.items()}
    base_keys={key_of(x) for x in ledgers["V91_UNFILTERED_CONTROL"]}
    filtered_keys={key_of(x) for x in ledgers["V92_STAR_HARAMI_SWEEP_FILTER"]}
    matched=base_keys & filtered_keys
    baseline_only=base_keys-filtered_keys
    filtered_only=filtered_keys-base_keys

    retests=Counter()
    warning_counts=Counter()
    sealed_hours=0
    unsealed_hours=0
    for t,snapshot in sorted(snapshots.items()):
        path=path_at(folder,t)
        commit=verified_first_commit(".",path)
        captured=epoch(snapshot["capturedAtUTC"])
        if commit is None or not captured-90<=commit<t+3600:
            unsealed_hours+=1
            continue
        sealed_hours+=1
        ev=snapshot["assets"][SYMBOL].get("currentCloseRetestEvaluation")
        if not ev:
            continue
        if ev.get("candidateRetestAtThisClose"):
            retests["baselineRetestOpportunities"]+=1
        if ev.get("directCurrentFilterVeto"):
            retests["directFilterVetoes"]+=1
            for warning in ev.get("currentPatternWarnings",[]):
                warning_counts[warning.get("name","UNKNOWN")+"_"+warning.get("tf","UNKNOWN")]+=1
        if ev.get("downstreamStateDivergence"):
            retests["downstreamStateDivergences"]+=1

    times=sorted(snapshots)
    missing=[]
    if times:
        present=set(times)
        missing=[iso(t) for t in range(times[0],times[-1]+1,3600)
                 if t not in present]
    delta=summaries["V92_STAR_HARAMI_SWEEP_FILTER"]["netR"]-summaries["V91_UNFILTERED_CONTROL"]["netR"]
    stress_delta=summaries["V92_STAR_HARAMI_SWEEP_FILTER"]["stressNetR"]-summaries["V91_UNFILTERED_CONTROL"]["stressNetR"]
    enough=(summaries["V91_UNFILTERED_CONTROL"]["trades"]>=MIN_CLOSED_CONTROL_TRADES
            and retests["directFilterVetoes"]>=MIN_SEALED_VETO_EVENTS)
    if not enough:
        decision="INSUFFICIENT_PROSPECTIVE_SAMPLE"
    elif delta>0 and stress_delta>0 and not filtered_only:
        decision="PROMISING_BUT_NOT_APPROVED_FOR_LIVE"
    else:
        decision="NO_CLEAR_ROBUST_IMPROVEMENT_DO_NOT_PROMOTE"

    return {
        "status":"V92_SOL_PAIRED_PROSPECTIVE_PAPER_ONLY",
        "symbol":SYMBOL,"firstEligibleCloseUTC":iso(FIRST),
        "lastDistinctVerifiedCloseUTC":iso(max(times)) if times else None,
        "savedDistinctVerifiedHours":len(times),
        "sealedHoursWithGitTimestamp":sealed_hours,
        "unsealedHoursExcludedFromVetoAudit":unsealed_hours,
        "missingHoursNotBackfilled":missing,
        "frozenPolicy":{
            "baseline":"V9.1 max-4h retest, no additional candle veto",
            "candidate":"Only opposite fully closed 1H/4H Morning/Evening Star or third-candle-confirmed Harami AND prior-20 liquidity sweep plus close back inside may veto a SOL retest",
            "BTC":"Observation only; no veto",
            "HikkakeAndEngulfing":"Observation only; no veto",
            "parametersChangedDuringProspectiveStudy":False,
        },
        "source":{
            "sameHourV7V91RecomputeParityRequired":True,
            "sameClosedCandleSetForBothArms":True,
            "liveBinanceExchangeParityIndependentlyProven":False,
            "nextOpenFillExecutable":False,
        },
        "directRetestAudit":{
            **dict(retests),
            "warningCounts":dict(warning_counts),
        },
        "arms":summaries,
        "comparison":{
            "matchedTradeKeys":len(matched),
            "baselineOnlyTradeKeys":len(baseline_only),
            "filteredOnlyTradeKeys":len(filtered_only),
            "deltaNetR9Bps":round(delta,6),
            "deltaNetR25BpsStress":round(stress_delta,6),
            "baselineOnlyTradeKeyExamples":[list(x) for x in sorted(baseline_only)[:20]],
            "filteredOnlyTradeKeyExamples":[list(x) for x in sorted(filtered_only)[:20]],
        },
        "excludedUnsealedOrUnprovenExits":{
            name:dict(counter) for name,counter in excluded.items()
        },
        "minimumReviewThreshold":{
            "eligibleClosedBaselineTrades":MIN_CLOSED_CONTROL_TRADES,
            "sealedDirectFilterVetoEvents":MIN_SEALED_VETO_EVENTS,
        },
        "researchDecision":decision,
        "noBrokerOrders":True,"noUserNotifications":True,
        "noProductionOrV7V91Changes":True,
        "noRetrospectiveBackfill":True,
        "paperOnlyNotRealPnL":True,
        "fixedRiskDollarPnLNotRecommendedForLive":True,
    }


def markdown(x):
    b=x["arms"]["V91_UNFILTERED_CONTROL"]
    f=x["arms"]["V92_STAR_HARAMI_SWEEP_FILTER"]
    c=x["comparison"]
    lines=[
      "# SOL V9.1 vs V9.2 paired prospective paper study","",
      "**Prospective paper only. No orders, alerts, or live strategy changes.**",
      "First eligible close: "+x["firstEligibleCloseUTC"],
      "Latest verified close: "+str(x["lastDistinctVerifiedCloseUTC"]),
      "Saved hours: "+str(x["savedDistinctVerifiedHours"])+"; sealed: "+str(x["sealedHoursWithGitTimestamp"]),
      "",
      "| Arm | Closed trades | Win % | Net R (9bp/side) | Stress R (25bp/side) | Max DD R |",
      "|---|---:|---:|---:|---:|---:|",
      "| V9.1 unfiltered control | {} | {} | {:.4f} | {:.4f} | {:.4f} |".format(
        b["trades"],b["winRatePct"],b["netR"],b["stressNetR"],b["maxDrawdownR"]),
      "| V9.2 Star/Harami + sweep | {} | {} | {:.4f} | {:.4f} | {:.4f} |".format(
        f["trades"],f["winRatePct"],f["netR"],f["stressNetR"],f["maxDrawdownR"]),
      "",
      "Baseline retest opportunities: "+str(x["directRetestAudit"].get("baselineRetestOpportunities",0)),
      "Direct, sealed filter vetoes: "+str(x["directRetestAudit"].get("directFilterVetoes",0)),
      "Matched trade keys: "+str(c["matchedTradeKeys"]),
      "Baseline-only / filtered-only trade keys: {}/{}".format(
        c["baselineOnlyTradeKeys"],c["filteredOnlyTradeKeys"]),
      "Delta net R: {:.4f}; stress delta: {:.4f}".format(
        c["deltaNetR9Bps"],c["deltaNetR25BpsStress"]),
      "",
      "Research decision: **"+x["researchDecision"]+"**",
      "Minimum review sample: {} closed baseline trades and {} sealed direct veto events.".format(
        x["minimumReviewThreshold"]["eligibleClosedBaselineTrades"],
        x["minimumReviewThreshold"]["sealedDirectFilterVetoEvents"]),
      "",
      "Missing hourly captures are listed, never backfilled. Only exits with a matching, pre-exit Git-committed retest snapshot are counted.",
      "The assumed next-hour-open fill is not proven executable; fees use 9 bp/side base and 25 bp/side stress. Funding, variable spread, market impact, and liquidation are not fully modeled.",
      "A positive paper result is not live approval.",
      "",
    ]
    if x["missingHoursNotBackfilled"]:
        lines += ["Missing hours not backfilled: "+", ".join(x["missingHoursNotBackfilled"][:30]),""]
    return "\n".join(lines)


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--hourly",default="forward/v92_prospective_selected/hourly")
    p.add_argument("--json",default="forward/v92_prospective_selected/paired_sol_account.json")
    p.add_argument("--markdown",default="forward/v92_prospective_selected/paired_sol_account.md")
    a=p.parse_args()
    result=build(a.hourly)
    out=Path(a.json);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    Path(a.markdown).write_text(markdown(result)+"\n")
    print("V92_SOL_PAIRED_PROSPECTIVE_RESULT",
          json.dumps({"hours":result["savedDistinctVerifiedHours"],
                      "controlTrades":result["arms"]["V91_UNFILTERED_CONTROL"]["trades"],
                      "filteredTrades":result["arms"]["V92_STAR_HARAMI_SWEEP_FILTER"]["trades"],
                      "vetoes":result["directRetestAudit"].get("directFilterVetoes",0),
                      "decision":result["researchDecision"]}),flush=True)


if __name__=="__main__":
    main()
