#!/usr/bin/env python3
"""ATLAS Core E3: official Binance SHA-256 1H OHLC -> exact V9.2 baseline.

Research-only, no orders, alerts, automation changes, scheduled runs or
production/paper writes. Historical 2022-2026 data previously examined:
this is source/replay *engineering parity*, NOT independently unseen OOS.
"""
from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha1, sha256
import json
from pathlib import Path

from research.atlas_core_v1 import atlas_core_e2 as e2
from research.atlas_core_v0 import atlas_core_v0 as core
import v92_filter_ablation_20261113 as v92

ROOT=Path("research/atlas_core_v2")
PINS={
    "backtest_retest_long_v4.py":"dae2d5edbec728612b820d59279f1ee06e7b287a",
    "v92_filter_ablation_20261113.py":"e2c453f8a0833c7f0deef44cfc200efd7b29c146",
    "v92_four_candle_models_20261113.py":"465c56cd1bc8e67766b99d9eb976a26b8058e75e",
    "signal_quality_v7.py":"77124c1563471c90226e68cc4cacc1312f81a9c1",
    "v92_selected_reversal_patterns.py":"75d827e1fcbbd48219d165bc49292bee26ae0a7c",
    "download_binance_um_history.py":"b706731a873a9c7da0aa2f0859c514b4117b55b9",
    "market_structure.py":"90d1c235e07f76efdb569620fe1928ddec389db9",
    "v92_bull_bear_candle_invalidation.py":"f01a190f2228be42123cd4803a0d23ec895dc3be",
    "v92_multi_candle_invalidation.py":"5a8a7376efbedabd2b36ba643593e965f34f390c",
}
COST_BPS=(9,25)
EXPECTED_PERIOD_FILES={"2022_2024":87,"2024_2026":72}
FREEZE_BTC_SOL="2026-11-15T00:00:00Z"
FREEZE_ETH="2026-11-14T00:00:00Z"

def blob_sha1(raw:bytes)->str:
    return sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()

def verify_code_pins()->dict:
    result={}
    for name,pin in PINS.items():
        raw=Path(name).read_bytes()
        if blob_sha1(raw)!=pin:
            raise ValueError("E3_REPLAY_SOURCE_CODE_MUTATED:"+name)
        result[name]=sha256(raw).hexdigest()
    if len(result)!=9:
        raise ValueError("E3_SOURCE_COVERAGE_CHANGED")
    # Historical source references already checked in E2; this check also
    # rejects drift in the original unmodified replay source string.
    v92.fork_source()
    return result

def checked_oracle():
    report, sha=e2.read_pinned(e2.SOURCE)
    if (report["status"]!="V92_FULL_FILTER_ONE_BY_ONE_AND_FOUR_PAIRS_RESEARCH_ONLY"
            or report["archiveCountSHA256"]!=159
            or not report["earlierAndLaterAlreadyHistoricallyInspectedNoTrueUnseenOOS"]):
        raise ValueError("E3_HISTORICAL_ORACLE_NOT_SEALED")
    return report, sha

def compare_archive_manifest(original:dict, verified:dict):
    """Re-downloaded Binance bytes are validated by official CHECKSUM first.

    Then compare each (symbol,month) digest and count to old sealed report.
    This independent re-download checks archived data did not silently change.
    """
    for period in e2.PERIODS:
        prior=original["periods"][period]["sourceManifest"]
        fresh=verified[period]
        if len(prior)!=EXPECTED_PERIOD_FILES[period] or len(fresh)!=EXPECTED_PERIOD_FILES[period]:
            raise ValueError("E3_ARCHIVE_TOTAL_MISMATCH:"+period)
        def keyed(items):
            result={}
            for x in items:
                key=(x["symbol"],x["month"])
                if key in result or len(x["sha256"])!=64:
                    raise ValueError("E3_DUPLICATE_OR_BAD_SHA256")
                result[key]=(x["sha256"],x["bars"])
            return result
        if keyed(prior)!=keyed(fresh):
            raise ValueError("E3_ARCHIVE_MONTH_SHA256_DRIFT:"+period)
    return sum(len(x) for x in verified.values())

def actual_baseline(symbol:str, candles:list[dict], period:str):
    """Chronological raw-OHLC baseline using research fork of frozen V9.2.

    The original function's source is copied in-memory with exactly matched
    guard clauses; mode BASELINE disables NO quality gates. SOL keeps its
    original retrospective Star/Harami sweep veto.
    """
    p=v92.PERIODS[period]
    start,end=v92.epoch(p["start"]),v92.epoch(p["end"])
    four,daily=v92.double_checked_candles(candles,end)
    cache={
        "indicators":{
            **v92.exact_streaming_indicator_cache(candles),
            **v92.exact_streaming_indicator_cache(four),
            **v92.exact_streaming_indicator_cache(daily),
        },
        "bias":{},"structures":{}
    }
    engine,bos_quality=v92.instrumentation("BASELINE",symbol=symbol,four=four,cache=cache)
    audit=Counter(examples=[])
    sol_veto=(v92.make_selective_gate(
        symbol,four,"SELECTED_SOL_STRICT_SWEEP",audit)
        if symbol=="SOLUSDT" else None)
    replay=engine(candles,four,daily,as_of=end,retest_hours=4,
                  bos_quality_filter=bos_quality,retest_quality_filter=sol_veto)
    if replay.get("status")!="PAPER_BACKTEST_NOT_LIVE":
        raise ValueError("E3_UNEXPECTED_REPLAY_STATUS")
    trades=v92._trades(replay,start,end)
    score=v92.to_score(replay,start,end)
    if not v92.valid_baseline_period(period,symbol,score):
        raise ValueError("E3_FIXED_SIX_BASELINE_NUMERIC_PARITY")
    return score,trades,{
        "hourly":len(candles),"fourHour":len(four),"daily":len(daily),
        "verifiedCandleEndExclusiveUTC":v92.stamp(end),
        "BOSWatches":score["BOSWatches"],
        "retestVetoes":score["retestVetoes"],
        "riskRejected":score["riskRejected"],
        "SOLOriginalReversalVetoAudit":{k:v for k,v in audit.items() if k!="examples"},
        "indicatorPrefixDecisions":len(cache["indicators"]),
        "structureComputationDecisions":len(cache["structures"]),
    }

def compare_raw_to_oracle(symbol:str,period:str,score:dict,trades:list[dict],reference:dict):
    """Compare full tape fields & exact 9/25bps rounded report values."""
    if (len(trades)!=reference["trades"] or score["trades"]!=reference["trades"]
        or score["wins"]!=reference["wins"]):
        raise ValueError("E3_TRADE_COUNTS_OR_WINS_DIVERGED")
    if len(score["tradeEvidence"])!=len(reference["tradeEvidence"]):
        raise ValueError("E3_TRADE_EVIDENCE_COUNT_DIVERGED")
    keys=("entryUTC","retestUTC","side","exitUTC","exitReason","entry","riskPct","netR9Bps")
    for i,(got,want) in enumerate(zip(score["tradeEvidence"],reference["tradeEvidence"])):
        if any(got[k]!=want[k] for k in keys):
            wrong=[k for k in keys if got[k]!=want[k]]
            raise ValueError("E3_RAW_BAR_TRADE_KEY_MISMATCH:"+symbol+":"+period+":"+str(i)+":"+repr(wrong))
        raw=trades[i]
        expected_r25=core.cost_stress_r(raw["netRIllustrative"],raw["entry"],raw["risk"],25)
        if (abs(expected_r25-core.cost_stress_r(raw["netRIllustrative"],raw["entry"],raw["risk"],9))<=0):
            raise ValueError("E3_COST_STRESS_DID_NOT_APPLY")
        if (v92.stamp(raw["watchKnownUTC"])>=v92.stamp(raw["retestKnownUTC"])
            or not raw["retestKnownUTC"]<=raw["entryOpenUTC"]<raw["exitKnownUTC"]):
            raise ValueError("E3_CAUSAL_EVENT_ORDER_FAILED")
    for field in ("netR9Bps","netR25Bps","BOSWatches","retestVetoes","riskRejected"):
        if score[field]!=reference[field]:
            raise ValueError("E3_SOURCE_METRIC_DISAGREEMENT:"+field)
    if score["direction"]!=reference["direction"]:
        raise ValueError("E3_DIRECTION_RETURN_PARITY")
    return {
        "matched":len(trades),"exactTradeKeysAndR9":True,
        "exactHistoricalTotalR25":True,"exactDirectionR9R25":True,
        "sameBOSWatchCount":True,"sameRetestVetoCount":True,
    }

def run(workers:int=6):
    if not 1<=workers<=6:
        raise ValueError("E3_WORKER_LIMIT")
    sha_sources=verify_code_pins()
    baseline,oracle_sha=checked_oracle()
    # Import side effects of v92 are computational only. Downloaded bytes
    # used exclusively in this local CI process and are NOT committed.
    all_candles,archives=v92.download_all(workers)
    count=compare_archive_manifest(baseline,archives)
    result={
        "status":"ATLAS_CORE_E3_OFFICIAL_RAW_OHLC_BASELINE_PARITY_HISTORICAL_ONLY",
        "referenceHistoricalSourceSHA256":oracle_sha,
        "replaySourceHashesSHA256":sha_sources,
        "historicArchivesDownloadedAndSHA256Verified":count,
        "newForwardTrades":0,"independentOutOfSample":False,
        "futureFreezeBTC_SOL_UTC":FREEZE_BTC_SOL,
        "futureFreezeETH_UTC":FREEZE_ETH,
        "realOrders":False,"notifications":False,"productionOrExistingPaperChanged":False,
        "noAutomaticPromotion":True,"wasOriginalUnmodifiedReplayExecuted":False,
        "replayMethod":"In-memory compiled V9.2 original function SOURCE with frozen BASELINE gates and cached exact-prefix indicators; original source on disk unchanged",
        "replayedFromOfficialRaw1H":True,
        "realExecutionFillFundingProof":False,
        "symbols":{},"all6PartitionsMatched":False,"all51TradesMatched":False,
    }
    matched=0
    for period in e2.PERIODS:
        for symbol in e2.ASSETS:
            print("ATLAS_E3_REPLAY_BEGIN",period,symbol,flush=True)
            score,tape,diagnostics=actual_baseline(symbol,all_candles[period][symbol],period)
            expected=baseline["periods"][period]["assets"][symbol]["variants"]["BASELINE"]
            same=compare_raw_to_oracle(symbol,period,score,tape,expected)
            matched+=same["matched"]
            result["symbols"].setdefault(symbol,{})[period]={
                "evidence":same,
                "metrics":{"trades":score["trades"],"wins":score["wins"],
                           "netR9":score["netR9Bps"],"netR25":score["netR25Bps"]},
                "diagnostics":diagnostics,
            }
            print("ATLAS_E3_RAW_PARITY_OK",period,symbol,score["trades"],
                  "R25",score["netR25Bps"],flush=True)
    if count!=159 or matched!=51:
        raise ValueError("E3_FINAL_COVERAGE_FAIL")
    result["all6PartitionsMatched"]=True
    result["all51TradesMatched"]=True
    result["matchedTradeCount"]=matched
    return result

def to_markdown(result):
    rows=[
        "# ATLAS Core E3 — raw Binance historical 1H vs V9.2 baseline",
        "",
        "**Engineering parity ONLY. Already known history; NOT independent forward profit proof.**",
        "",
        "| Asset | 2022–24 trades | 2024–26 trades | Raw-bar replay match |",
        "|---|---:|---:|---:|"
    ]
    for coin,periods in result["symbols"].items():
        a=periods["2022_2024"]["metrics"]["trades"]
        b=periods["2024_2026"]["metrics"]["trades"]
        rows.append(f"| {coin} | {a} | {b} | {a+b}/{a+b} |")
    rows += [
        "",f'**SHA256 verified official Binance monthly archives:** {result["historicArchivesDownloadedAndSHA256Verified"]}',
        f'**Matched exact historical trades:** {result["matchedTradeCount"]}',
        "",
        "## Constraints",
        "- 9/25 bps per-side assumptions are NOT exchange-reconciled fills; funding remains unknown.",
        "- The fast exact-prefix research fork executes the frozen baseline original SOURCE; no "
          "separate independently coded engine implementation was proven.",
        "- 2022–26 had already been inspected; results cannot establish new trading alpha.",
        "- Existing frozen forward starts, paper ledgers, main, orders, alerts and schedules "
          "were not modified.",
        "- Output is a temporary CI artifact; no commit of generated outputs into Git.",
        ""
    ]
    return "\n".join(rows)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--workers",type=int,default=6)
    parser.add_argument("--out",default="research/atlas_core_v2/output/e3_report.json")
    args=parser.parse_args()
    path=Path(args.out)
    if not str(path).startswith("research/atlas_core_v2/output/"):
        raise ValueError("E3_OUTPUT_NOT_ISOLATED")
    d=run(args.workers)
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(d,indent=2,ensure_ascii=False,sort_keys=True)+"\n")
    path.with_suffix(".md").write_text(to_markdown(d))
    print("ATLAS_E3_159_SHA256_ARCHIVES_SIX_RAW_REPLAYS_51_TRADES_EXACT_MATCH",flush=True)

if __name__=="__main__":
    main()
