#!/usr/bin/env python3
"""V9.2 ETH historical 1D/3D + reversal-pattern paper ablation.

Uses independently downloaded official Binance USD-M ETHUSDT monthly 1H klines.
4H and 1D are derived from 1H. 3D is derived only from three complete daily bars.
Replays unchanged V7/V9.1 BOS->retest->next-open paper logic; all V9.2 filters
are research-only at retest close. This is not a parity claim to historical
Coinalyze/V7 live snapshots and not a live signal deployment.
"""
import argparse
from collections import Counter
import json
from pathlib import Path

from backtest_retest_long_v4 import replay_pair
from market_structure import candles_from_history
from signal_quality_v7 import evaluate_bos_quality
from v92_bull_bear_candle_invalidation import (
    START, END, HOUR, stamp, metrics
)
from v92_higher_timeframe_context import context_at, aggregate_3d_from_daily
from v92_multi_candle_invalidation import warnings_at_retest

MODES=(
    "BASELINE",
    "CANDLE_ONLY",
    "DAILY_RETEST_CONFIRM",
    "3D_RETEST_CONFIRM",
    "DAILY_AND_3D_RETEST_CONFIRM",
    "CANDLE_PLUS_3D",
)


def _candle_gate(four,audit):
    def gate(hour_bars,active,retest):
        at=int(retest["t"])+HOUR
        warnings=warnings_at_retest(
            hour_bars,four,at,active["side"],
            {"STAR","HARAMI_CONFIRMED"},require_sweep=True)
        audit["checkedRetests"]+=1
        if warnings:
            audit["candleVetoes"]+=1
            for w in warnings:
                audit["patterns"][w["name"]+"_"+w["tf"]]+=1
        return {
            "passed":not bool(warnings),
            "reasons":["V92_ETH_OPPOSING_STAR_HARAMI_PRIOR20_SWEEP"]
                if warnings else [],
        }
    return gate


def _gate(four,daily,*,candle_enabled,daily_enabled,three_enabled,audit):
    candle_audit=Counter()
    candle_audit["patterns"]=Counter()
    candle=_candle_gate(four,candle_audit) if candle_enabled else None
    def gate(hour_bars,active,retest):
        at=int(retest["t"])+HOUR
        ctx=context_at(daily,at)
        audit["checkedRetests"]+=1
        audit["dailyTrends"][ctx["1D"]]+=1
        audit["threeDayTrends"][ctx["3D"]]+=1
        passed=True
        reasons=[]
        if daily_enabled and ctx["1D"]!="insufficient":
            if ctx["1D"]!=active["side"]:
                passed=False
                reasons.append("DAILY_EMA20_50_NOT_ALIGNED_AT_RETEST")
                audit["dailyRejections"]+=1
        elif daily_enabled:
            audit["dailyWarmupPasses"]+=1
        if three_enabled and ctx["3D"]!="insufficient":
            if ctx["3D"]!=active["side"]:
                passed=False
                reasons.append("3D_EMA20_50_NOT_ALIGNED_AT_RETEST")
                audit["threeDayRejections"]+=1
        elif three_enabled:
            audit["threeDayWarmupPasses"]+=1
        if candle is not None:
            decision=candle(hour_bars,active,retest)
            if not decision["passed"]:
                passed=False
                reasons.extend(decision["reasons"])
        return {"passed":passed,"reasons":reasons}
    return gate,candle_audit


def run(histories, warmup_daily):
    hour=histories["1hour"]
    four=histories["4hour"]
    daily=histories["daily"]
    h=candles_from_history(hour,"1hour",END)
    f=candles_from_history(four,"4hour",END)
    d=candles_from_history(daily,"daily",END)
    warm=candles_from_history(warmup_daily,"daily",END)
    d_context=candles_from_history(warmup_daily+daily,"daily",END)
    if (len(h)!=17520 or len(f)!=4380 or len(d)!=730
        or len(warm)!=183 or len(d_context)!=913):
        raise ValueError("V92_ETH_OFFICIAL_BINANCE_ARCHIVE_COUNT_MISMATCH")
    if context_at(d_context,START)["3D"]=="insufficient":
        raise ValueError("V92_ETH_3D_EMA50_WARMUP_INCOMPLETE")
    if len(aggregate_3d_from_daily(d_context))<300:
        raise ValueError("V92_ETH_EXPECTED_3D_CONTEXT_MISSING")
    result={
        "status":"V92_ETH_OFFICIAL_BINANCE_1D_3D_HISTORICAL_PAPER_ABLATION",
        "symbol":"ETHUSDT",
        "fromUTC":stamp(START),
        "toUTCExclusive":stamp(END),
        "verifiedCandles":{"1H":len(h),"4H":len(f),"1D":len(d)},
        "contextWarmupDailyBars":len(warm),
        "contextWarmupPeriodUTC":["2024-04-01T00:00:00Z","2024-10-01T00:00:00Z"],
        "derived3DContextCandlesWithWarmup":len(aggregate_3d_from_daily(d_context)),
        "source":"Official Binance USD-M Futures monthly 1H klines; each monthly ZIP SHA256 verified; 4H and 1D derived from 1H",
        "3D":"Derived from three consecutive fully closed UTC daily bars on epoch-aligned 3-day boundaries",
        "nativeExchange3DParityProven":False,
        "trendRule":"At retest close, close above EMA20 and EMA50 = bullish; below both = bearish; otherwise mixed",
        "baselineRule":"Same replay_pair V7 6h and V9.1 4h BOS->retest->next-open engine with existing BOS quality and existing 4H/1D BOS context",
        "candleRule":"Exploratory ETH shadow only: opposing closed 1H/4H Star or confirmed Harami plus prior-20 sweep/re-entry veto at retest",
        "dailyAnd3dRules":"Optional EMA20/EMA50 retest-close confirmation using only bars already closed at that time",
        "notExactHistoricalLiveV7SnapshotParity":True,
        "noBrokerOrders":True,
        "noUserNotifications":True,
        "notRealProfit":True,
        "noFilterPromotionWithoutProspectiveEvidence":True,
        "variants":{},
    }
    for base_name,retest_hours in (("V7_ORIGINAL",6),("V91_RETEST_MAX4H",4)):
        base=replay_pair(hour,four,daily,as_of=END,retest_hours=retest_hours,
                         bos_quality_filter=evaluate_bos_quality)
        base_score=metrics(base,START,END)
        result["variants"][base_name]=base_score
        for mode in MODES[1:]:
            candle_enabled=mode in ("CANDLE_ONLY","CANDLE_PLUS_3D")
            daily_enabled=mode in ("DAILY_RETEST_CONFIRM","DAILY_AND_3D_RETEST_CONFIRM")
            three_enabled=mode in ("3D_RETEST_CONFIRM","DAILY_AND_3D_RETEST_CONFIRM","CANDLE_PLUS_3D")
            audit=Counter()
            audit["dailyTrends"]=Counter()
            audit["threeDayTrends"]=Counter()
            gate,candle_audit=_gate(
                f,d_context,candle_enabled=candle_enabled,
                daily_enabled=daily_enabled,three_enabled=three_enabled,
                audit=audit)
            rep=replay_pair(hour,four,daily,as_of=END,
                            retest_hours=retest_hours,
                            bos_quality_filter=evaluate_bos_quality,
                            retest_quality_filter=gate)
            score=metrics(rep,START,END)
            score["deltaNetRVsOwnBaseline"]=round(
                score["totalNetR9BpsPerSide"]-
                base_score["totalNetR9BpsPerSide"],6)
            score["contextAudit"]={
                "checkedRetests":audit["checkedRetests"],
                "dailyTrends":dict(audit["dailyTrends"]),
                "threeDayTrends":dict(audit["threeDayTrends"]),
                "dailyRejections":audit["dailyRejections"],
                "threeDayRejections":audit["threeDayRejections"],
                "dailyWarmupPasses":audit["dailyWarmupPasses"],
                "threeDayWarmupPasses":audit["threeDayWarmupPasses"],
                "candleCheckedRetests":candle_audit["checkedRetests"],
                "candleVetoes":candle_audit["candleVetoes"],
                "candlePatternCounts":dict(candle_audit["patterns"]),
            }
            result["variants"][base_name+"__"+mode]=score
    return result


def markdown(x):
    lines=[
        "# V9.2 ETH official Binance historical 1D/3D backtest",
        "",
        "**Research-only paper simulation. Not live PnL.**",
        "Period: "+x["fromUTC"]+" – "+x["toUTCExclusive"]+" (exclusive).",
        "Source: "+x["source"]+".",
        "3D: "+x["3D"]+". Native 3D parity is not proven.",
        "The existing engine already applies 4H/1D context at BOS; this experiment optionally re-checks 1D and derived 3D EMA20/50 at retest close.",
        "ETH candle veto is an exploratory shadow using the same strict Star/Harami + prior20 sweep/re-entry rule. It is not enabled in the live ETH paper engine.",
        "",
        "| Baseline | Variant | Trades | Wins | Win % | Net R | Stress R | Δ Net R |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for name,z in x["variants"].items():
        base,_,variant=name.partition("__")
        lines.append(
            f"| {base} | {variant or 'BASELINE'} | {z['trades']} | {z['wins']} | "
            f"{z['winRatePct']} | {z['totalNetR9BpsPerSide']:.4f} | "
            f"{z['totalNetR25BpsPerSideStress']:.4f} | "
            f"{z.get('deltaNetRVsOwnBaseline',0):.4f} |")
    lines += [
        "",
        "Costs are the existing illustrative 9 bps/side base and 25 bps/side stress. Funding, true fills, dynamic spread and liquidation are not fully modeled.",
        "No live orders, alerts, or V7/V9.1 changes. No strategy promotion from this retrospective sample.",
        "",
    ]
    return "\n".join(lines)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--archive",default="eth_verified_archive")
    parser.add_argument("--warmup-daily",default="eth_verified_warmup/history_daily_warmup.json")
    parser.add_argument("--warmup-manifest",default="eth_verified_warmup/source_manifest.json")
    parser.add_argument("--out",default="forward/v92_eth_historical_backtest_warmup")
    args=parser.parse_args()
    root=Path(args.archive)
    manifest=json.loads((root/"source_manifest.json").read_text())
    if (manifest.get("symbol")!="ETHUSDT_PERP.A"
        or manifest.get("checksumsVerified")!=24
        or manifest.get("pairCounts")!={"1hour":17520,"4hour":4380,"daily":730}):
        raise ValueError("V92_ETH_BINANCE_SHA256_MANIFEST_INVALID")
    histories={}
    for tf in ("1hour","4hour","daily"):
        rows=json.loads((root/f"history_{tf}.json").read_text())
        if len(rows)!=1 or rows[0].get("symbol")!="ETHUSDT_PERP.A":
            raise ValueError("V92_ETH_WRONG_ARCHIVE_SYMBOL")
        histories[tf]=rows[0]["history"]
    warm_path=Path(args.warmup_daily)
    warm_rows=json.loads(warm_path.read_text())
    if len(warm_rows)!=1 or warm_rows[0].get("symbol")!="ETHUSDT_PERP.A":
        raise ValueError("V92_ETH_WARMUP_WRONG_SYMBOL")
    warm_history=warm_rows[0]["history"]
    warm_manifest=json.loads(Path(args.warmup_manifest).read_text())
    if (warm_manifest.get("checksumsVerified")!=6
        or warm_manifest.get("dailyBars")!=183
        or warm_manifest.get("warmupOnlyNotPerformancePeriod") is not True):
        raise ValueError("V92_ETH_WARMUP_MANIFEST_INVALID")
    data=run(histories,warm_history)
    data["contextWarmupSource"]="Official Binance USD-M ETH monthly 1H ZIPs; six additional SHA256-verified files; 1D derived from complete 1H bars"
    data["contextWarmupExcludedFromPerformancePeriod"]=True
    data["sourceManifest"]={
        "checksumsVerified":manifest["checksumsVerified"],
        "firstUTC":manifest["firstUTC"],
        "endExclusiveUTC":manifest["endExclusiveUTC"],
        "monthlyFiles":[{"month":x["month"],"sha256":x["sha256"]} for x in manifest["inputFiles"]],
        "warmupChecksumsVerified":warm_manifest["checksumsVerified"],
        "warmupFiles":[{"month":x["month"],"sha256":x["sha256"]} for x in warm_manifest["inputFiles"]],
    }
    out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
    (out/"historical.json").write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n")
    (out/"historical.md").write_text(markdown(data)+"\n")
    print("V92_ETH_OFFICIAL_BINANCE_BACKTEST_COMPLETE",json.dumps({
        name:{"trades":score["trades"],"wins":score["wins"],
              "netR":score["totalNetR9BpsPerSide"],
              "delta":score.get("deltaNetRVsOwnBaseline")}
        for name,score in data["variants"].items()}),flush=True)


if __name__=="__main__":
    main()
