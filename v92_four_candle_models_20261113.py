#!/usr/bin/env python3
"""Independent BTC/ETH/SOL A/B/C/D confirmed-pattern ablation (historical ONLY).

A = prior V9.2 baseline (V7 BOS quality, max-4H retest; SOL retains the
    existing Star/confirmed Harami + prior-20 sweep/reentry veto).
B = same exact A trades, with additional observed pattern labels only.
C = A + opposing confirmed Star/Harami/Engulfing prior-20 sweep/reentry
    or independently confirmed Hikkake false-break veto at retest.
D = A + requires any matching-direction confirmed Star/Harami/
    Engulfing/Hikkake (without additional sweep requirement) at retest.

All patterns are based on fully CLOSED 1H and 4H bars by retest close.
The windows and detector thresholds are the existing frozen V9.2 research
definitions. We do not optimize outcomes or rewrite V7/V9.2 account.
No live orders, alerts, forward-ledger backfills or paper-account changes.
"""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
import math
from pathlib import Path

from backtest_retest_long_v4 import replay_pair
from download_binance_um_history import aggregate, download_month, months_inclusive
from signal_quality_v7 import evaluate_bos_quality
from v92_bull_bear_candle_invalidation import HOUR, FOUR, stamp, metrics
from v92_multi_candle_invalidation import warnings_at_retest

SYMBOLS = ("BTCUSDT", "ETHUSDT", "SOLUSDT")
PATTERNS = frozenset(("STAR", "HARAMI_CONFIRMED",
                      "ENGULFING", "HIKKAKE_CONFIRMED"))
MODES = ("A_BASELINE", "B_OBSERVATION_ONLY", "C_OPPOSING_CONTEXT_VETO",
         "D_SAME_DIRECTION_CONFIRM")
PERIODS = {
    "2022_2024": {
        "months": months_inclusive("2022-05", "2024-09"),
        "warmup": "2022-05-01T00:00:00Z",
        "start": "2022-10-01T00:00:00Z",
        "end": "2024-10-01T00:00:00Z",
        "count1H": 21216,
    },
    "2024_2026": {
        "months": months_inclusive("2024-10", "2026-09"),
        "warmup": "2024-10-01T00:00:00Z",
        "start": "2024-10-01T00:00:00Z",
        "end": "2026-10-01T00:00:00Z",
        "count1H": 17520,
    },
}

def epoch(t):
    return int(datetime.fromisoformat(t.replace("Z", "+00:00")).timestamp())

def validate_period_manifest(name, histories, files):
    p = PERIODS[name]
    if len(files) != 3 * len(p["months"]):
        raise ValueError("FOUR_MODE_MONTHLY_ARCHIVE_COUNT_" + name)
    expected = {(s,m) for s in SYMBOLS for m in p["months"]}
    if {(x["symbol"],x["month"]) for x in files} != expected:
        raise ValueError("FOUR_MODE_MONTHLY_ARCHIVE_COVERAGE_" + name)
    for s in SYMBOLS:
        bars = histories[s]
        if (len(bars) != p["count1H"] or
            bars[0]["t"] != epoch(p["warmup"]) or
            bars[-1]["t"] + HOUR != epoch(p["end"]) or
            any(row["t"] != bars[0]["t"] + i*HOUR
                for i,row in enumerate(bars))):
            raise ValueError("FOUR_MODE_GAPPED_1H_" + name + "_" + s)
    for x in files:
        if len(x["sha256"]) != 64:
            raise ValueError("FOUR_MODE_BAD_BINANCE_SHA256")
    return True

def download_all(workers):
    records = {}
    files = {key: [] for key in PERIODS}
    tasks = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for key,period in PERIODS.items():
            for s in SYMBOLS:
                for month in period["months"]:
                    future = pool.submit(download_month,s,month)
                    tasks[future]=(key,s,month)
        for task in as_completed(tasks):
            key,s,m=tasks[task]
            symbol,month,bars,proof=task.result()
            if (symbol,month)!=(s,m) or not bars or len(proof["sha256"])!=64:
                raise ValueError("FOUR_MODE_ARCHIVE_PROOF_MISMATCH")
            records[(key,s,m)]=bars
            files[key].append({"symbol":symbol,"month":month,**proof})
            print("FOUR_MODE_ARCHIVE_SHA256_OK",key,s,m,len(bars),flush=True)
    hist = {}
    for key,period in PERIODS.items():
        by_symbol = {
            s:[bar for m in period["months"] for bar in records[(key,s,m)]]
            for s in SYMBOLS
        }
        validate_period_manifest(key,by_symbol,files[key])
        hist[key] = by_symbol
        files[key].sort(key=lambda x:(x["symbol"],x["month"]))
    return hist, files

def opposite(side):
    if side not in ("bullish","bearish"):
        raise ValueError("FOUR_MODE_INVALID_BOS_SIDE")
    return "bearish" if side=="bullish" else "bullish"

def matched_patterns(one, four, at, side, relation, *, strict_sweep=False):
    """Side means active BOS direction. Only PATTERN direction is reversed
    to reuse the original audited, causal V9.2 warning detector."""
    if relation not in ("opposing","same"):
        raise ValueError("FOUR_MODE_INVALID_RELATION")
    query_side = side if relation=="opposing" else opposite(side)
    out = warnings_at_retest(one,four,at,query_side,PATTERNS,
                             require_sweep=strict_sweep)
    if any(p["direction"] != (opposite(side) if relation=="opposing" else side)
           for p in out):
        raise ValueError("FOUR_MODE_PATTERN_SIDE_MISMATCH")
    if any(epoch(p["confirmedUTC"]) > at for p in out):
        raise ValueError("FOUR_MODE_FUTURE_PATTERN_LEAK")
    return out

def strict_sol_original(one,four,at,side):
    """Replicate EXACT existing V9.2 SOL-only veto before optional new gates."""
    return warnings_at_retest(
        one, four, at, side, {"STAR","HARAMI_CONFIRMED"},
        require_sweep=True)

def new_gate(symbol,mode,four,audit):
    if mode not in MODES or mode=="B_OBSERVATION_ONLY":
        raise ValueError("FOUR_MODE_GATE_UNKNOWN_MODE")
    def gate(one,active,retest):
        at=int(retest["t"])+HOUR
        if (active["knownUTC"]>=at or one[-1]["t"]+HOUR!=at or
            at != int(retest["t"])+HOUR):
            raise ValueError("FOUR_MODE_LOOKAHEAD_OR_STALE_RETEST")
        audit["retestsChecked"]+=1
        bos_side=active["side"]
        # B observes on every ORIGINAL baseline-eligible retest, with
        # both families and timeframes. A shares the exact same replay.
        if mode=="A_BASELINE":
            opp=matched_patterns(one,four,at,bos_side,"opposing")
            same=matched_patterns(one,four,at,bos_side,"same")
            audit["observedOpposingRetests"]+=bool(opp)
            audit["observedSameDirectionRetests"]+=bool(same)
            for p in opp:audit["opp_"+p["family"]+"_"+p["tf"]]+=1
            for p in same:audit["same_"+p["family"]+"_"+p["tf"]]+=1
            if len(audit["retetsEvidence"])<240:
                audit["retetsEvidence"].append({
                    "retestUTC":stamp(at),"bosSide":bos_side,
                    "opposing":opp,"sameDirection":same,
                })
        if symbol=="SOLUSDT":
            original=strict_sol_original(one,four,at,bos_side)
            if original:
                audit["originalV92SolVetoes"]+=1
                return {"passed":False,
                        "reasons":["ORIGINAL_V92_SOL_STRICT_SELECTED_VETO"]}
        if mode=="C_OPPOSING_CONTEXT_VETO":
            opp=matched_patterns(one,four,at,bos_side,
                                 "opposing",strict_sweep=True)
            if opp:
                audit["additionalCContextVetoes"]+=1
                for p in opp:audit["C_"+p["family"]+"_"+p["tf"]]+=1
                if len(audit["additionalVetoExamples"])<50:
                    audit["additionalVetoExamples"].append({
                        "atUTC":stamp(at),"side":bos_side,"patterns":opp})
                return {"passed":False,
                        "reasons":["RESEARCH_C_OPPOSING_CONFIRMED_CONTEXT"]}
        elif mode=="D_SAME_DIRECTION_CONFIRM":
            same=matched_patterns(one,four,at,bos_side,"same")
            if not same:
                audit["DNoConfirmRejected"]+=1
                return {"passed":False,
                        "reasons":["RESEARCH_D_NO_CLOSED_SAME_DIRECTION_PATTERN"]}
            audit["DConfirmationAccepted"]+=1
        return {"passed":True,"reasons":[]}
    return gate

def trades_within(result,start,end):
    if result.get("status")!="PAPER_BACKTEST_NOT_LIVE":
        raise ValueError("FOUR_MODE_UNEXPECTED_REPLAY_STATUS")
    trades=[t for t in result["trades"]
            if start<=t["entryOpenUTC"]<end and t["exitKnownUTC"]<=end]
    for t in trades:
        if not (t["watchKnownUTC"]<t["retestKnownUTC"]
                <=t["entryOpenUTC"]<t["exitKnownUTC"]
                and t["entry"]>0 and t["risk"]>0):
            raise ValueError("FOUR_MODE_TRADE_CAUSALITY")
    return sorted(trades,key=lambda t:(t["entryOpenUTC"],t["side"]))

def trade_key(t):
    return str(t["entryOpenUTC"])+"_"+t["side"]

def trade_summary(t):
    cost_stress=2*(25-9)/10000*t["entry"]/t["risk"]
    return {
        "key":trade_key(t),"side":t["side"],
        "watchUTC":stamp(t["watchKnownUTC"]),
        "retestUTC":stamp(t["retestKnownUTC"]),
        "entryUTC":stamp(t["entryOpenUTC"]),
        "exitUTC":stamp(t["exitKnownUTC"]),
        "exitReason":t["exitReason"],
        "netR9Bps":round(t["netRIllustrative"],6),
        "netR25Bps":round(t["netRIllustrative"]-cost_stress,6),
        "entry":round(t["entry"],7),
        "stop":round(t["stop"],7),
        "stopDistancePercent":round(100*t["risk"]/t["entry"],5),
    }

def paired_deltas(baseline,variant):
    bm={trade_key(t):t for t in baseline}
    vm={trade_key(t):t for t in variant}
    removed=[bm[k] for k in sorted(set(bm)-set(vm))]
    new=[vm[k] for k in sorted(set(vm)-set(bm))]
    retained=set(bm)&set(vm)
    for k in retained:
        # Replaying same engine with a gate must not change a retained
        # exact-entry trade's exit or netR in absence of concurrent sizing.
        a,b=bm[k],vm[k]
        if abs(a["netRIllustrative"]-b["netRIllustrative"])>1e-8:
            raise ValueError("FOUR_MODE_RETAINED_TRADE_OUTCOME_DRIFT")
    return {
        "baselineWinnersRemoved":sum(x["netRIllustrative"]>0 for x in removed),
        "baselineLosersRemoved":sum(x["netRIllustrative"]<=0 for x in removed),
        "baselineWinnersNetRRemoved":round(sum(x["netRIllustrative"] for x in removed
                                              if x["netRIllustrative"]>0),6),
        "baselineLosersNetRRemoved":round(sum(x["netRIllustrative"] for x in removed
                                             if x["netRIllustrative"]<=0),6),
        "additionalTradesVsBaseline":len(new),
        "additionalNetR9Bps":round(sum(x["netRIllustrative"] for x in new),6),
        "removedBaselineTradeKeys":[trade_key(x) for x in removed],
        "newVariantTradeKeys":[trade_key(x) for x in new],
    }

def evaluate_symbol(symbol,hour,start,end):
    four=aggregate(hour,FOUR)
    daily=aggregate(hour,24*HOUR)
    variants={}
    raw={}
    obs=None
    for mode in ("A_BASELINE","C_OPPOSING_CONTEXT_VETO",
                 "D_SAME_DIRECTION_CONFIRM"):
        audit=Counter()
        audit["retetsEvidence"]=[]
        audit["additionalVetoExamples"]=[]
        report=replay_pair(
            hour,four,daily,as_of=end,retest_hours=4,
            bos_quality_filter=evaluate_bos_quality,
            retest_quality_filter=(
                new_gate(symbol,mode,four,audit)
                if symbol=="SOLUSDT" or mode!="A_BASELINE"
                else new_gate(symbol,mode,four,audit)
            ),
        )
        score=metrics(report,start,end)
        trades=trades_within(report,start,end)
        if len(trades)!=score["trades"]:
            raise ValueError("FOUR_MODE_SCORE_COUNT_MISMATCH")
        score["fullTradeEvidence"]=[trade_summary(t) for t in trades]
        score["audit"]={k:v for k,v in audit.items()}
        score["noForwardTradesCredited"]=True
        raw[mode]=trades
        variants[mode]=score
        if mode=="A_BASELINE":
            obs={"retestsChecked":audit["retestsChecked"],
                 "opposingPatternRetests":audit["observedOpposingRetests"],
                 "sameDirectionPatternRetests":audit["observedSameDirectionRetests"],
                 "familyAndTimeframeCounts":{
                     k:v for k,v in audit.items()
                     if k.startswith(("opp_","same_"))},
                 "retetsEvidence":audit["retetsEvidence"]}
        print("FOUR_MODE",symbol,mode,score["trades"],
              score["totalNetR9BpsPerSide"],
              score["totalNetR25BpsPerSideStress"],flush=True)
    # B must not produce different fills; it is only feature annotation.
    variants["B_OBSERVATION_ONLY"]={
        **{k:v for k,v in variants["A_BASELINE"].items() if k!="audit"},
        "audit":{"observationOnly":obs,
                 "allSignalsIdenticalToA":True},
    }
    for mode in ("B_OBSERVATION_ONLY","C_OPPOSING_CONTEXT_VETO",
                 "D_SAME_DIRECTION_CONFIRM"):
        variants[mode]["pairedVsA"]=paired_deltas(
            raw["A_BASELINE"],
            raw["A_BASELINE"] if mode=="B_OBSERVATION_ONLY" else raw[mode])
        variants[mode]["deltaR9BpsVsA"]=round(
            variants[mode]["totalNetR9BpsPerSide"]-
            variants["A_BASELINE"]["totalNetR9BpsPerSide"],6)
        variants[mode]["deltaR25BpsVsA"]=round(
            variants[mode]["totalNetR25BpsPerSideStress"]-
            variants["A_BASELINE"]["totalNetR25BpsPerSideStress"],6)
    variants["A_BASELINE"]["pairedVsA"]=paired_deltas(
        raw["A_BASELINE"],raw["A_BASELINE"])
    variants["A_BASELINE"]["deltaR9BpsVsA"]=0.
    variants["A_BASELINE"]["deltaR25BpsVsA"]=0.
    return {m:variants[m] for m in MODES}

def parity_check(period,symbol,base):
    # Previously sealed exact historical source/motor parity: FAIL CLOSED.
    refs={
        ("2022_2024","BTCUSDT"):(10,-4.265784,-7.701252),
        ("2022_2024","ETHUSDT"):(10,-0.9789,-4.4969),
        ("2022_2024","SOLUSDT"):(12,4.6274,2.0039),
        ("2024_2026","BTCUSDT"):(5,4.1010,2.8146),
        ("2024_2026","ETHUSDT"):(6,-2.0083,-4.1088),
        ("2024_2026","SOLUSDT"):(8,4.2607,2.4099),
    }
    n,r,stress=refs[(period,symbol)]
    if (base["trades"]!=n or
        abs(base["totalNetR9BpsPerSide"]-r)>.00016 or
        abs(base["totalNetR25BpsPerSideStress"]-stress)>.00016):
        raise ValueError("FOUR_MODE_PREVIOUS_SEALED_BASELINE_PARITY_FAILED_"+
                         period+"_"+symbol+":"+repr((
            base["trades"],base["totalNetR9BpsPerSide"],
            base["totalNetR25BpsPerSideStress"])))
    return True

def run(workers):
    history,proofs=download_all(workers)
    result={
        "status":"FOUR_MODEL_CLOSED_CANDLE_PATTERN_ABLATION_HISTORICAL_ONLY",
        "modes":{
            "A_BASELINE":"Existing V9.2: V7 BOS + max4h retest, existing SOL-only opposing Star/Harami with prior20 sweep veto",
            "B_OBSERVATION_ONLY":"Exactly A trades; label same/opposing confirmed 1H/4H patterns at baseline retest",
            "C_OPPOSING_CONTEXT_VETO":"A plus veto opposing confirmed Star/Harami/Engulfing with prior20 sweep OR confirmed Hikkake false breakout at retest",
            "D_SAME_DIRECTION_CONFIRM":"A plus require any same-direction confirmed Star/Harami/Engulfing/Hikkake at retest; no sweep requirement",
        },
        "fixedDetector":"Existing v92_multi_candle_invalidation.py and v92_bull_bear_candle_invalidation.py; no parameter refitting",
        "patternFamilies":sorted(PATTERNS),
        "lastFourClosed1HCandlesAndLastTwoClosed4HCandlesOnly":True,
        "BIdenticalTradesToA":True,
        "sweepRequiredForCOtherThanHikkakeInternalFalseBreak":True,
        "costBpsPerSide":[9,25],
        "periods":{},
        "noProductionV7V92Edits":True,
        "noPaperAccountEditsOrBackfills":True,
        "noOrdersOrUserAlerts":True,
        "historicalDataAlreadyResearchedNotIndependentProspectiveEvidence":True,
        "noFundingOrRealOrderbookFillParity":True,
        "noCappedAccountDollarSizingInThisStudy":True,
    }
    for pname,p in PERIODS.items():
        start,end=epoch(p["start"]),epoch(p["end"])
        period={
            "scoredUTC":[p["start"],p["end"]],
            "warmupFromUTC":p["warmup"],
            "verifiedMonthlyArchives":len(proofs[pname]),
            "1HCandlesPerSymbol":p["count1H"],
            "sourceManifest":proofs[pname],
            "symbols":{},
        }
        for sym in SYMBOLS:
            score=evaluate_symbol(sym,history[pname][sym],start,end)
            parity_check(pname,sym,score["A_BASELINE"])
            period["symbols"][sym]=score
        result["periods"][pname]=period
    return result

def markdown(data):
    lines=[
        "# BTC / ETH / SOL — A-B-C-D pattern experiment",
        "",
        "**Research only; V7, V9.2 live paper account, alerts and orders unchanged.**",
        "",
        "Models: **A** exact V9.2 baseline; **B** A plus observe-only patterns",
        "(identical fills); **C** reject opposing prior-20 sweep/reentry",
        "Star/confirmed Harami/Engulfing or confirmed Hikkake false break;",
        "**D** require same-direction closed Star/Harami/Engulfing/Hikkake",
        "within last 4×1H or 2×4H complete bars (no extra sweep condition).",
        "Baseline SOL keeps its existing strict Star/Harami sweep veto in every model.",
        "All use unchanged V7 BOS filter, 4H maximum retest, next-hour open,",
        "original stop, TP1–TP3, 24-hour max hold and 9/25 bps/yön illustrative cost.",
        "Data: official Binance USDT-M monthly 1H ZIPs SHA256 verified,",
        "4H and daily aggregated exactly from 1H. No actual execution.",
        "",
        "| Period | Symbol | Mode | Trades | Wins | Win% | Net R 9bps | Net R 25bps | Delta R vs A | PF | MaxDD R | Vetoes |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for pname,p in data["periods"].items():
        for s,variants in p["symbols"].items():
            for mode in MODES:
                d=variants[mode]
                veto=d["audit"].get("additionalCContextVetoes",0)+d["audit"].get("DNoConfirmRejected",0)
                lines.append(
                    f"| {pname} | {s} | {mode} | {d['trades']} | {d['wins']} | "
                    f"{d['winRatePct'] if d['winRatePct'] is not None else '—'} | "
                    f"{d['totalNetR9BpsPerSide']:+.4f} | "
                    f"{d['totalNetR25BpsPerSideStress']:+.4f} | "
                    f"{d['deltaR9BpsVsA']:+.4f} | "
                    f"{d['profitFactor'] if d['profitFactor'] is not None else '—'} | "
                    f"{d['maxDrawdownR']:.3f} | {veto} |")
    lines += [
        "", "## Missed winners / avoided losers vs baseline",
        "",
        "| Period | Symbol | Mode | Baseline winners missed | Baseline losers avoided | New variant trades | Delta R 9bps | Delta R 25bps |",
        "|---|---|---|---:|---:|---:|---:|---:|",
    ]
    for pname,p in data["periods"].items():
        for s,variants in p["symbols"].items():
            for mode in ("C_OPPOSING_CONTEXT_VETO","D_SAME_DIRECTION_CONFIRM"):
                d=variants[mode]; x=d["pairedVsA"]
                lines.append(
                    f"| {pname} | {s} | {mode} | "
                    f"{x['baselineWinnersRemoved']} | "
                    f"{x['baselineLosersRemoved']} | "
                    f"{x['additionalTradesVsBaseline']} | "
                    f"{d['deltaR9BpsVsA']:+.4f} | "
                    f"{d['deltaR25BpsVsA']:+.4f} |")
    lines += [
        "", "## Constraints and interpretation",
        "",
        "- Veto audit counts may exceed excluded *executed* trades because later risk validation and overlapping BOS watches can change the sequence.",
        "- Missed winners/avoided losers are paired by exact original entry UTC and side. Newly available trades are reported separately; changes in opportunity sequence matter.",
        "- B cannot improve PnL by construction; its value is observational data to analyze during genuinely forward tests.",
        "- 2022–2024 vs 2024–2026 is a temporal comparison, not fully unseen information: previous research has inspected parts of both datasets.",
        "- Every baseline is checked against the preceding SHA256 historical studies; mismatch aborts the report.",
        "- This is NOT the $1,000 capped-account historical sizing simulation. $10/$20 risk and max 10x remain prospective account rules.",
        "- Funding, order book, variable execution costs, liquidations, quote timing and live Binance/Coinalyze parity are not verified.",
        "- A tiny trade sample or a zero-trade variant does not prove a profitable edge. Historical trades do not count toward the 50 forward completed trades.",
        "",
    ]
    return "\n".join(lines)

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--workers",type=int,default=6)
    ap.add_argument("--out",default="forward/v92_four_candle_models_20261113")
    args=ap.parse_args()
    if not 1<=args.workers<=6:
        ap.error("workers must be 1..6")
    res=run(args.workers)
    path=Path(args.out)
    path.mkdir(parents=True,exist_ok=True)
    (path/"historical.json").write_text(
        json.dumps(res,ensure_ascii=False,indent=2)+"\n")
    (path/"historical.md").write_text(markdown(res)+"\n")
    print("FOUR_MODEL_ALL_159_MONTHLY_SHA256_BASELINES_PARITY_OK",flush=True)

if __name__=="__main__":
    main()
