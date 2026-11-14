#!/usr/bin/env python3
"""ATLAS Core E2: three-asset sealed trade-tape reconciliation (RESEARCH ONLY).

This checks previously saved V9.2 historical tapes against separate historical
research witnesses, with 9bps exact R and 25bps rounding-aware arithmetic.
This is NOT a new candle-by-candle engine replay, independent OOS, or proof of
future performance; it never interacts with exchange/production systems.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime
from hashlib import sha1, sha256
from pathlib import Path
import json

from research.atlas_core_v0 import atlas_core_v0 as core

SOURCE = Path("forward/v92_filter_ablation_20261113/historical.json")
OLDER = Path("forward/v92_older_eth_sol_regimes_20261113/historical.json")
LATER = Path("forward/v92_three_asset_correlation_20261113/historical.json")
GIT_BLOB_PINS = {
    str(SOURCE): "d09ac4830e9ef6ce635bce2e8ebde818242243cb",
    str(OLDER): "ea56be2efb022fe69ae48f9e8a1aefd8bffcc1e2",
    str(LATER): "cde7de239de86934273b791566d8a8d1ca4b85a9",
}
PERIODS = ("2022_2024", "2024_2026")
ASSETS = ("BTCUSDT", "ETHUSDT", "SOLUSDT")
COSTS = (9,25,50)
# Historical tape's riskPct/netR9Bps are rounded, so 25bps is approximate
# when independently repriced. Original source report contains exact 25bps.
PER_PERIOD_R25_ABS_TOL = 0.0001
R9_AGGREGATE_ABS_TOL = 0.00002

def read_pinned(path: Path):
    raw=path.read_bytes()
    blob=sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()
    if blob != GIT_BLOB_PINS[str(path)]:
        raise ValueError("E2_FROZEN_GIT_BLOB_DRIFT: "+str(path))
    return json.loads(raw),sha256(raw).hexdigest()

def witness_of(older: dict, later: dict, period: str, coin: str):
    if period == "2022_2024":
        asset=older["assets"][coin]
        if coin=="BTCUSDT":
            return asset["parityReferenceOnly"]
        if coin=="ETHUSDT":
            return asset["variants"]["V91_V92_4H_BASELINE"]
        return asset["variants"]["V91_4H_UNFILTERED"]
    return later["assets"][coin]["variants"]["V92_BASELINE"]

def audit_tape(primary: dict, witness: dict, *, coin: str, period: str):
    tape=primary["tradeEvidence"]
    independent=witness["tradeEntryExitEvidence"]
    if len(tape)!=primary["trades"] or len(tape)!=witness["trades"] or len(independent)!=len(tape):
        raise ValueError("E2_TRADE_COUNT_PARITY_FAIL_"+coin+"_"+period)
    if primary["noHistoricalTradesCreditedToForward"] is not True:
        raise ValueError("E2_FALSE_FORWARD_CLASSIFICATION")

    total9=0.
    total25=0.
    total50=0.
    wins9=wins25=0
    prev_key=None
    normalized=[]
    for a,b in zip(tape,independent):
        key_a=(a["entryUTC"],a["exitUTC"],a["side"],a["netR9Bps"])
        key_b=(b["entryUTC"],b["exitUTC"],b["side"],b["netR9bps"])
        if key_a!=key_b:
            raise ValueError("E2_ENTRY_EXIT_DIRECTION_OR_R9_MISMATCH_"+coin+"_"+period)
        if b["retestUTC"] != a["retestUTC"]:
            raise ValueError("E2_RETEST_WITNESS_MISMATCH")
        watch=core.utc_seconds(b["watchUTC"])
        retest=core.utc_seconds(b["retestUTC"])
        entry=core.utc_seconds(a["entryUTC"])
        exit_time=core.utc_seconds(a["exitUTC"])
        if not (watch<retest<=entry<exit_time):
            raise ValueError("E2_EVENT_CHRONOLOGY_BROKEN")
        if entry % 3600 or exit_time % 3600 or watch % 3600 or retest % 3600:
            raise ValueError("E2_EVENT_ALIGNMENT_BROKEN")
        if a["side"] not in ("bullish","bearish"):
            raise ValueError("E2_UNKNOWN_DIRECTION")
        if a["exitReason"] not in ("TP3_COMPLETE","STOP_FIRST_OR_AFTER_TP","TIME_EXIT_AT_CLOSE"):
            raise ValueError("E2_UNKNOWN_EXIT_REASON")
        if a["entry"]<=0 or not (0 < a["riskPct"] <= 4):
            raise ValueError("E2_INVALID_TRADE_RISK")
        if prev_key is not None and entry<=prev_key:
            raise ValueError("E2_TRADE_TAPE_UNSORTED")
        prev_key=entry

        risk=a["entry"]*a["riskPct"]/100
        r9=core.cost_stress_r(a["netR9Bps"],a["entry"],risk,9)
        r25=core.cost_stress_r(a["netR9Bps"],a["entry"],risk,25)
        r50=core.cost_stress_r(a["netR9Bps"],a["entry"],risk,50)
        if not r9 >= r25 >= r50:
            raise ValueError("E2_COST_STRESS_NONMONOTONIC")
        total9+=r9
        total25+=r25
        total50+=r50
        wins9+=r9>0
        wins25+=r25>0
        normalized.append({
            "symbol":coin, "period":period,
            "entryUTC":a["entryUTC"],"exitUTC":a["exitUTC"],
            "side":a["side"],"exitReason":a["exitReason"],
            "entryEpoch":entry,"exitEpoch":exit_time,
            "R9FromFrozenTape":round(r9,6),
            "approximateR25FromRoundedRiskPct":round(r25,6),
        })
    if abs(total9-primary["netR9Bps"])>R9_AGGREGATE_ABS_TOL:
        raise ValueError("E2_PRIMARY_R9_TOTAL_MISMATCH")
    if abs(total9-witness["totalNetR9BpsPerSide"])>R9_AGGREGATE_ABS_TOL:
        raise ValueError("E2_INDEPENDENT_WITNESS_R9_TOTAL_MISMATCH")
    if (primary["netR25Bps"] != witness["totalNetR25BpsPerSideStress"]
        or abs(total25-primary["netR25Bps"])>PER_PERIOD_R25_ABS_TOL):
        raise ValueError("E2_R25_TOTAL_OR_COST_FORMULA_MISMATCH")
    if wins9 != primary["wins"] or wins9 != witness["wins"]:
        raise ValueError("E2_WIN_DENOMINATOR_FAIL")
    return {
        "tradesMatched":len(tape),
        "sourceNetR9":primary["netR9Bps"],
        "sourceNetR25":primary["netR25Bps"],
        "computedR9FromRoundedEvidence":round(total9,6),
        "computedR25ApproxFromRoundedEvidence":round(total25,6),
        "computedR50ApproxFromRoundedEvidence":round(total50,6),
        "R25ApproxMinusOfficialReport":round(total25-primary["netR25Bps"],7),
        "winsAt9bps":wins9,"winsAt25bpsDerived":wins25,
        "witnessTradeKeysMatched":len(tape),
        "timeOrderingVerified":True,
        "fullCandleReplayPerformed":False,
    },normalized

def trade_overlap(tape: list[dict]):
    """Counts overlapping positions without inventing shared capital or PF."""
    events=[]
    for t in tape:
        events.append((t["entryEpoch"],+1,t["symbol"]))
        events.append((t["exitEpoch"],-1,t["symbol"]))
    # Exit before entry at exactly the same instant: half-open [entry,exit).
    events.sort(key=lambda x:(x[0],x[1]))
    live=Counter()
    max_live=0
    max_distinct=0
    same_time_cross_asset_pairs=set()
    for stamp,kind,symbol in events:
        if kind==1:
            if sum(live.values())>0:
                for other,count in live.items():
                    if other!=symbol and count>0:
                        same_time_cross_asset_pairs.add((stamp,tuple(sorted((symbol,other)))))
            live[symbol]+=1
        else:
            if live[symbol] <= 0:
                raise ValueError("E2_POSITION_EXIT_WITHOUT_ENTRY")
            live[symbol]-=1
        max_live=max(max_live,sum(live.values()))
        max_distinct=max(max_distinct,sum(v>0 for v in live.values()))
    if sum(live.values())!=0:
        raise ValueError("E2_UNCLOSED_POSITION")
    return {
        "maxConcurrentPositionsInHistoricalTape":max_live,
        "maxConcurrentDistinctAssets":max_distinct,
        "crossAssetOverlapEntryEvents":len(same_time_cross_asset_pairs),
        "fullCapitalAllocationRiskNotMeasured":True,
        "portfolioPFAndMaxDrawdownNotMeasured":True
    }

def audit():
    source,s_sha=read_pinned(SOURCE)
    old,o_sha=read_pinned(OLDER)
    new,n_sha=read_pinned(LATER)
    if (source["status"]!="V92_FULL_FILTER_ONE_BY_ONE_AND_FOUR_PAIRS_RESEARCH_ONLY"
        or old["status"]!="V92_OLDER_ETH_ATR_AND_SOL_BTC_4H_FIXED_RULE_TEMPORAL_CHECK"
        or new["status"]!="V92_THREE_ASSET_ASOF_4H_CORRELATION_AND_ETH_LOSS_HISTORICAL_RESEARCH"):
        raise ValueError("E2_UNEXPECTED_SOURCE_STATUS")
    if source["archiveCountSHA256"]!=159:
        raise ValueError("E2_WRONG_PRIOR_ARCHIVE_COUNT")
    if not (source["earlierAndLaterAlreadyHistoricallyInspectedNoTrueUnseenOOS"]
            and old["historicalOnlyNotIndependentLiveExecutionEvidence"]
            and new["alreadyInspectedHistoricalPeriodNotOutOfSample"]):
        raise ValueError("E2_FALSE_OOS_CLASSIFICATION")
    out={
        "status":"ATLAS_CORE_E2_THREE_ASSET_HISTORICAL_PARITY_ONLY",
        "independentOutOfSample":False,"freshForwardClosedTradesClaimed":0,
        "underlyingOfficialArchivesRedownloaded":False,
        "verifiesHistoricalReportsNotRawOHLCReplays":True,
        "noOrders":True,"noNotifications":True,"noProductionChanges":True,
        "noStrategyOrParameterEdits":True,"frozenForwardCandidateStartsUnchanged":True,
        "sourceSHA256":{"primary":s_sha,"earlyWitness":o_sha,"laterWitness":n_sha},
        "sourceGitBlobPins":dict(GIT_BLOB_PINS),
        "symbols":{},"totalTapeTradesMatched":0,"totalWitnessTradesMatched":0,
        "portfolioR":None,"portfolioPF":None,"portfolioMaxDrawdown":None,
        "overlap":{}
    }
    all_trades=[]
    for coin in ASSETS:
        out["symbols"][coin]={}
        for period in PERIODS:
            primary=source["periods"][period]["assets"][coin]["variants"]["BASELINE"]
            witness=witness_of(old,new,period,coin)
            summary,trades=audit_tape(primary,witness,coin=coin,period=period)
            out["symbols"][coin][period]=summary
            out["totalTapeTradesMatched"]+=summary["tradesMatched"]
            out["totalWitnessTradesMatched"]+=summary["witnessTradeKeysMatched"]
            all_trades.extend(trades)
    if out["totalTapeTradesMatched"]!=51 or out["totalWitnessTradesMatched"]!=51:
        raise ValueError("E2_UNEXPECTED_HISTORICAL_TRADE_COUNT")
    out["overlap"]=trade_overlap(all_trades)
    out["verificationLimits"]=[
        "Three files are separate historical reports, NOT independent raw-data implementations.",
        "All 51 trade keys, side and R9 matched across reports; no OHLC signal replay was run.",
        "Per-trade risk percentage is rounded; derived R25 and R50 are approximate.",
        "Portfolio risk and actual fills/funding/spread/slippage are unknown.",
        "Historical observations informed filter discovery; no new prospective edge shown."
    ]
    return out

def markdown(out):
    lines=[
        "# ATLAS Core E2 — three-asset V9.2 tape parity",
        "",
        "**Historical-only cross-report consistency; NOT prospective, independent OOS or raw-candle engine parity.**",
        "",
        "| Coin | 2022–24 trades | 2024–26 trades | Tape matches |",
        "|---|---:|---:|---:|",
    ]
    for coin,record in out["symbols"].items():
        a=record["2022_2024"]["tradesMatched"]
        b=record["2024_2026"]["tradesMatched"]
        lines.append(f"| {coin} | {a} | {b} | {a+b}/{a+b} |")
    lines += [
        "",
        f'Total reconciled trade keys: **{out["totalWitnessTradesMatched"]}**.',
        f'Max historical concurrent positions: **{out["overlap"]["maxConcurrentPositionsInHistoricalTape"]}**.',
        f'Max distinct assets concurrently open: **{out["overlap"]["maxConcurrentDistinctAssets"]}**.',
        "",
        "## Scientific limitations and next step",
        "",
        *("- "+point for point in out["verificationLimits"]),
        "- E3 must run a read-only reproducible raw-OHLC replay and compare every "
          "watch, retest, stop, TP, execution and trade to this sealed oracle.",
        "- All existing V7/V9.2 production, ETH/BTC/SOL prospective protocols "
          "and notification jobs stay unchanged.",
        ""
    ]
    return "\n".join(lines)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--out",default="research/atlas_core_v1/output/e2_report.json")
    args=parser.parse_args()
    path=Path(args.out)
    if not str(path).startswith("research/atlas_core_v1/output/"):
        raise ValueError("E2_OUTPUT_ESCAPES_SANDBOX")
    d=audit()
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(d,indent=2,ensure_ascii=False,sort_keys=True)+"\n")
    path.with_suffix(".md").write_text(markdown(d))
    print("ATLAS_CORE_E2_51_OF_51_SEALED_TAPE_KEYS_MATCH")
    for coin,periods in d["symbols"].items():
        print(coin,*(p+":"+str(x["tradesMatched"]) for p,x in periods.items()))
    print("CONCURRENT_POSITIONS",d["overlap"]["maxConcurrentPositionsInHistoricalTape"])
    print("INDEPENDENT_OOS",d["independentOutOfSample"])

if __name__=="__main__":
    main()
