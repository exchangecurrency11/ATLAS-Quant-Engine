#!/usr/bin/env python3
"""One-time earlier-period SOL reversal-filter temporal validation.

The Star/confirmed-Harami + prior-20 sweep/re-entry rule is frozen from the
separate 2024-10..2026-10 V9.2 research. This run uses official SHA256-verified
Binance USD-M monthly 1H archives from 2022-04..2024-09, with 2022-04..09 as
indicator warmup and 2022-10..2024-09 as the scored period. This is a temporal
holdout for this V9.2 rule, not proof of a wholly unseen market dataset.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path

from backtest_retest_long_v4 import replay_pair
from market_structure import candles_from_history
from signal_quality_v7 import evaluate_bos_quality
from v7_paper_comparison import read_history
from v92_bull_bear_candle_invalidation import (
    HOUR, FOUR, SYMBOLS, stamp, metrics
)
from v92_multi_candle_invalidation import warnings_at_retest
from download_binance_um_history import months_inclusive

WARMUP_START=int(datetime(2022,5,1,tzinfo=timezone.utc).timestamp())
START=int(datetime(2022,10,1,tzinfo=timezone.utc).timestamp())
END=int(datetime(2024,10,1,tzinfo=timezone.utc).timestamp())
MONTHS=months_inclusive("2022-05","2024-09")
EXPECTED={"1hour":21216,"4hour":5304,"daily":884}
SELECTED_FAMILIES={"STAR","HARAMI_CONFIRMED"}


def validate_manifest(m):
    if (m.get("source")!="Binance official data.binance.vision FUTURES/UM monthly 1h klines"
        or m.get("firstUTC")!="2022-05-01T00:00:00+00:00"
        or m.get("endExclusiveUTC")!="2024-10-01T00:00:00+00:00"
        or m.get("checksumsVerified")!=58):
        raise ValueError("V92_SOL_HOLDOUT_BINANCE_MANIFEST_INVALID")
    expected_pairs={(sym,month) for sym in ("BTCUSDT","SOLUSDT") for month in MONTHS}
    actual={(x.get("symbol"),x.get("month")) for x in m.get("inputFiles",[])}
    if (actual!=expected_pairs or len(m.get("inputFiles",[]))!=58
        or any(len(x.get("sha256",""))!=64 for x in m["inputFiles"])):
        raise ValueError("V92_SOL_HOLDOUT_MONTHLY_SHA256_COVERAGE_INVALID")
    for sym in ("BTCUSDT","SOLUSDT"):
        if m.get("pairCounts",{}).get(sym)!=EXPECTED:
            raise ValueError("V92_SOL_HOLDOUT_CANDLE_COUNT_INVALID_"+sym)
    return True


def make_gate(symbol,four,audit,*,veto):
    def gate(one,active,retest):
        at=int(retest["t"])+HOUR
        warnings=warnings_at_retest(
            one,four,at,active["side"],SELECTED_FAMILIES,
            require_sweep=True)
        if at>=START:
            audit["originalRetestsAssessed"]+=1
            if warnings:
                audit["opposingSelectedPatternsObserved"]+=1
                for item in warnings:
                    audit[item["name"]+"_"+item["tf"]]+=1
                if len(audit["examples"])<40:
                    audit["examples"].append({
                        "atUTC":stamp(at),"activeBOSDirection":active["side"],
                        "patterns":warnings})
        blocked=bool(symbol=="SOLUSDT" and veto and warnings)
        if blocked and at>=START:
            audit["rejectedRetests"]+=1
        return {
            "passed":not blocked,
            "reasons":["V92_SOL_STRICT_STAR_HARAMI_PRIOR20_SWEEP_VETO"]
                if blocked else [],
        }
    return gate


def audit_json(a):
    return {
        "originalRetestsAssessed":a["originalRetestsAssessed"],
        "opposingSelectedPatternsObserved":a["opposingSelectedPatternsObserved"],
        "rejectedRetests":a["rejectedRetests"],
        "patternCounts":{k:v for k,v in a.items()
                         if isinstance(v,int) and k not in (
                           "originalRetestsAssessed",
                           "opposingSelectedPatternsObserved",
                           "rejectedRetests")},
        "examples":a["examples"],
    }


def run(histories,manifest):
    validate_manifest(manifest)
    out={
      "status":"V92_SOL_EARLIER_PERIOD_TEMPORAL_HOLDOUT_PAPER_ONLY",
      "warmupPeriodUTC":[stamp(WARMUP_START),stamp(START)],
      "scoredPeriodUTC":[stamp(START),stamp(END)],
      "source":{
        "description":"Official Binance USD-M monthly 1H klines, each monthly ZIP SHA256 checked; 4H and Daily aggregated from continuous 1H UTC candles",
        "checksumsVerified":manifest["checksumsVerified"],
        "monthlyArchives":len(manifest["inputFiles"]),
        "pairCounts":manifest["pairCounts"],
      },
      "frozenPolicy":{
        "eligibleCoin":"SOLUSDT only",
        "families":["STAR","HARAMI_CONFIRMED"],
        "requireOppositeDirectionToActiveBOS":True,
        "requirePrior20HighLowSweepAndCloseBackInside":True,
        "BTC":"Observe only; never veto",
        "HikkakeAndEngulfing":"Observe only; never veto",
        "parametersChangedAfterOpeningHoldoutResults":False,
      },
      "temporalValidation":{
        "currentV92SelectionPeriodUTC":["2024-10-01T00:00:00Z","2026-10-01T00:00:00Z"],
        "holdoutEndsAtOrBeforeSelectionPeriodStart":END<=int(datetime(2024,10,1,tzinfo=timezone.utc).timestamp()),
        "sameV92RuleAppliedWithoutRetuning":True,
        "notProofOfEntirelyUnseenMarketData":True,
      },
      "timeframes":["1H","4H","1D"],
      "variants":{},
      "noBrokerOrders":True,"noUserNotifications":True,
      "noProductionChanges":True,"paperOnlyNotRealPnL":True,
      "nextOpenFillNotIndependentlyExecutable":True,
      "fundingVariableSpreadMarketImpactLiquidationNotFullyModeled":True,
    }
    for symbol,ref in SYMBOLS.items():
        h=histories["1hour"][ref]
        four=histories["4hour"][ref]
        daily=histories["daily"][ref]
        closedh=candles_from_history(h,"1hour",END)
        closedf=candles_from_history(four,"4hour",END)
        closedd=candles_from_history(daily,"daily",END)
        if (len(closedh)!=EXPECTED["1hour"]
            or len(closedf)!=EXPECTED["4hour"]
            or len(closedd)!=EXPECTED["daily"]):
            raise ValueError("V92_SOL_HOLDOUT_HISTORY_LENGTH_MISMATCH_"+symbol)
        variants={}
        for base_name,retest_hours in (("V7_ORIGINAL",6),("V91_RETEST_MAX4H",4)):
            baseline=replay_pair(
                h,four,daily,as_of=END,retest_hours=retest_hours,
                bos_quality_filter=evaluate_bos_quality)
            baseline_score=metrics(baseline,START,END)
            observe_audit=Counter();observe_audit["examples"]=[]
            observe=replay_pair(
                h,four,daily,as_of=END,retest_hours=retest_hours,
                bos_quality_filter=evaluate_bos_quality,
                retest_quality_filter=make_gate(
                    symbol,closedf,observe_audit,veto=False))
            observe_score=metrics(observe,START,END)
            for key in ("trades","wins","totalNetR9BpsPerSide",
                        "totalNetR25BpsPerSideStress"):
                if (observe_score[key]!=baseline_score[key]
                    if isinstance(baseline_score[key],int)
                    else abs(observe_score[key]-baseline_score[key])>.00001):
                    raise ValueError("V92_SOL_HOLDOUT_OBSERVE_ONLY_PARITY_FAILED_"+symbol+"_"+key)
            baseline_score["BOSWatches"]=sum(
                START<=e["knownUTC"]<END for e in baseline.get("alerts",[]))
            baseline_score["retestVetoes"]=0
            variants[base_name]=baseline_score

            filter_audit=Counter();filter_audit["examples"]=[]
            filtered=replay_pair(
                h,four,daily,as_of=END,retest_hours=retest_hours,
                bos_quality_filter=evaluate_bos_quality,
                retest_quality_filter=make_gate(
                    symbol,closedf,filter_audit,veto=True))
            filtered_score=metrics(filtered,START,END)
            filtered_score["BOSWatches"]=sum(
                START<=e["knownUTC"]<END for e in filtered.get("alerts",[]))
            filtered_score["retestVetoes"]=filter_audit["rejectedRetests"]
            filtered_score["filterAudit"]=audit_json(filter_audit)
            filtered_score["deltaNetRVsOwnBaseline"]=round(
                filtered_score["totalNetR9BpsPerSide"]-
                baseline_score["totalNetR9BpsPerSide"],6)
            filtered_score["deltaStressRVsOwnBaseline"]=round(
                filtered_score["totalNetR25BpsPerSideStress"]-
                baseline_score["totalNetR25BpsPerSideStress"],6)
            filtered_score["vetoEnabledForThisCoin"]=symbol=="SOLUSDT"
            variants[base_name+"__V92_STRICT_SWEEP_FILTER"]=filtered_score
        out["variants"][symbol]={
            "verifiedCandles":{"1H":len(closedh),"4H":len(closedf),"1D":len(closedd)},
            "scores":variants,
        }
    return out


def markdown(x):
    lines=[
      "# V9.2 SOL earlier-period temporal validation",
      "",
      "**Paper-only historical holdout. No orders, alerts, or production changes.**",
      "Warmup: {} to {}.".format(*x["warmupPeriodUTC"]),
      "Scored period: {} to {} (exclusive).".format(*x["scoredPeriodUTC"]),
      "Source: {} monthly SHA256-verified official Binance archives.".format(
        x["source"]["monthlyArchives"]),
      "The selected rule is frozen; no thresholds were changed after opening this holdout.",
      "",
      "| Coin | Baseline | Trades | Wins | Win % | Net R | Stress R | Filter trades | Filter Net R | Δ Net R | Vetoes |",
      "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for symbol,item in x["variants"].items():
        for base in ("V7_ORIGINAL","V91_RETEST_MAX4H"):
            a=item["scores"][base]
            f=item["scores"][base+"__V92_STRICT_SWEEP_FILTER"]
            lines.append("| {} | {} | {} | {} | {} | {:.4f} | {:.4f} | {} | {:.4f} | {:.4f} | {} |".format(
              symbol,base,a["trades"],a["wins"],a["winRatePct"],
              a["totalNetR9BpsPerSide"],a["totalNetR25BpsPerSideStress"],
              f["trades"],f["totalNetR9BpsPerSide"],
              f["deltaNetRVsOwnBaseline"],f["retestVetoes"]))
    lines += [
      "",
      "Interpretation must consider trade counts and both base/stress costs; a small-sample improvement is not proof.",
      "This is an earlier temporal window for the V9.2 rule, but not a wholly unseen market dataset because the repository contains other historical SOL research.",
      "Funding, variable spread, market impact, liquidation, and executable next-open fills are not fully modeled.",
      "No live strategy promotion from this report.",
      "",
    ]
    return "\n".join(lines)


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--archive",default="v92_sol_holdout_archive")
    p.add_argument("--out",default="forward/v92_sol_holdout_2022_2024")
    a=p.parse_args()
    root=Path(a.archive)
    manifest=json.loads((root/"source_manifest.json").read_text())
    validate_manifest(manifest)
    histories={
      tf:read_history(str(root/("history_"+tf+".json")))
      for tf in ("1hour","4hour","daily")
    }
    result=run(histories,manifest)
    out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    (out/"historical.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    (out/"historical.md").write_text(markdown(result)+"\n")
    print("V92_SOL_EARLIER_TEMPORAL_HOLDOUT_COMPLETE",json.dumps({
      symbol:{name:{
        "trades":score["trades"],
        "netR":score["totalNetR9BpsPerSide"],
        "filteredNetR":score.get("deltaNetRVsOwnBaseline")}
        for name,score in item["scores"].items()}
      for symbol,item in result["variants"].items()}),flush=True)


if __name__=="__main__":
    main()
