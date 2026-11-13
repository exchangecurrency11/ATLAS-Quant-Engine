#!/usr/bin/env python3
"""V9.2 six-dataset causal research-only ablation: one filter removed at a
time, plus FOUR predeclared two-factor interactions.

This script does NOT edit the original replay engine: its EXACT function
source is copied in-memory, with explicit, counted substitutions for a few
eligibility statements. Every original baseline is parity-checked against
the six previously SHA256-verified V9.2 reports. Reference-engine fills
must also match the generated fork on the frozen periods; any drift fails.

Rules held fixed: confirmed closed 1H BOS structure, CLOSED retest touch
and close beyond BOS level, next-hour OPEN simulated fill, 0.1 ATR BOS /
retest wick stop, 1R/2R/3R thirds, stop-first on 1H collision, 24h
maximum hold, no future 4H/daily candles, 9/25bps per side illustration.
Do not conflate V9.2's 4H maximum *retest horizon* with its daily/4H bias.
"NO" tests disable one historical quality criterion, not live safeguards.
No broker orders, live signal edits, notifications, or forward book writes.
The 2022-2024 and 2024-2026 periods were previously studied elsewhere:
time-separated robustness, NOT fully unseen validation.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
from functools import wraps
import inspect
import json
import math
from pathlib import Path

import backtest_retest_long_v4 as original
from download_binance_um_history import aggregate
from signal_quality_v7 import evaluate_bos_quality
from v92_bull_bear_candle_invalidation import HOUR, FOUR, metrics, stamp
from v92_four_candle_models_20261113 import (
    SYMBOLS, PERIODS, download_all, parity_check, epoch)
from v92_selected_reversal_patterns import make_selective_gate

# Every named criterion corresponds to one exact existing V7/V9.2
# decision. Mandatory causal structure and stop-first are NOT optional.
ABLATIONS = {
    "BASELINE": (),
    "NO_1H_VOLUME_SURGE_20PCT": ("volume_burst",),
    "NO_1H_RSI_DIRECTION": ("rsi_direction",),
    "NO_1H_MACD_DIRECTION": ("macd_direction",),
    "NO_4H_TREND_ALIGNMENT": ("trend4h",),
    "NO_DAILY_TREND_ALIGNMENT": ("trend1d",),
    "NO_BOS_MIN_BREAK_0P20ATR": ("bos_break_atr",),
    "NO_BOS_RVOL20_1P20": ("bos_rvol20",),
    "NO_BOS_EMA20_MAX_EXTENSION_2P50ATR": ("bos_ema_extension",),
    "NO_SOL_SELECTED_REVERSAL_VETO": ("sol_reversal",),
    "RETEST_WINDOW_6H_NOT_4H": ("retest_window",),
    "NO_RETEST_CANDLE_COLOR": ("retest_color",),
    "NO_RETEST_VS_PREVIOUS_CLOSE": ("retest_prev_close",),
    "RISK_STOP_MAX_6PCT_NOT_4PCT": ("risk_max_pct",),
    "RISK_STOP_MIN_0P05PCT_NOT_0P10": ("risk_min_pct",),
    # Predeclared interaction checks; NOT a post-result combinatorial search
    "PAIR_NO_VOLUME_SURGE_AND_RVOL20": ("volume_burst","bos_rvol20"),
    "PAIR_NO_RSI_AND_MACD": ("rsi_direction","macd_direction"),
    "PAIR_NO_4H_AND_DAILY": ("trend4h","trend1d"),
    "PAIR_NO_BREAK_ATR_AND_EMA_EXT": ("bos_break_atr","bos_ema_extension"),
}
ONE_BY_ONE = tuple(k for k,v in ABLATIONS.items()
                   if k!="BASELINE" and len(v)==1)
PAIRS = tuple(k for k,v in ABLATIONS.items() if len(v)==2)
CONTROL_REQUIREMENTS = (
    "causal_1h_confirmed_BOS",
    "retest_touches_and_closes_beyond_structure",
    "entry_next_1h_open_only",
    "stop_wick_plus_0.1_ATR",
    "take_profit_1R_2R_3R_one_third_each",
    "same_hour_stop_first",
    "max_24_1h_bars_held",
    "closed_4h_and_daily_context_only",
)
EXPECTED_PREVIOUS = {
    ("2022_2024","BTCUSDT"):(10,-4.265784,-7.701252),
    ("2022_2024","ETHUSDT"):(10,-0.9789,-4.496945),
    ("2022_2024","SOLUSDT"):(12,4.6274,2.0039),
    ("2024_2026","BTCUSDT"):(5,4.1010,2.8146),
    ("2024_2026","ETHUSDT"):(6,-2.0083,-4.1088),
    ("2024_2026","SOLUSDT"):(8,4.2607,2.4099),
}

# The original script is not modified on disk. Each replaced AST line
# must exactly match known version, else fail before any data download.
SOURCE_REWRITES = (
    (
        "if vol_pct is None or vol_pct < 20:",
        "if vol_pct is None or (not _skip('volume_burst') and vol_pct < 20):",
    ),
    (
        'if not ((ind["RSI14"] < 50 and ind["hist"] < 0)\n'
        '                or (ind["RSI14"] > 50 and ind["hist"] > 0)):',
        "if not _momentum_possible(ind):",
    ),
    (
        'if tf_bias[0] != tf_bias[1] or tf_bias[0] not in ("bullish","bearish"):',
        "if not _htf_any(tf_bias):",
    ),
    (
        "if tf_bias != [side, side]:",
        "if not _htf_side(tf_bias,side):",
    ),
    (
        'if side == "bearish" and not (ind["RSI14"] < 50 and ind["hist"] < 0):',
        'if side == "bearish" and not _momentum_side(ind,side):',
    ),
    (
        'if side == "bullish" and not (ind["RSI14"] > 50 and ind["hist"] > 0):',
        'if side == "bullish" and not _momentum_side(ind,side):',
    ),
)


def fork_source():
    source=inspect.getsource(original.replay_pair)
    for expected,replacement in SOURCE_REWRITES:
        if source.count(expected)!=1:
            raise ValueError("ABLATION_ORIGINAL_ENGINE_CHANGED_NO_SAFE_PATCH:"+expected)
        source=source.replace(expected,replacement,1)
    if source.count("def replay_pair(")!=1:
        raise ValueError("ABLATION_ENGINE_GENERATION_UNTRUSTWORTHY")
    return source


def instrumentation(variant, *, symbol, four, cache):
    """Construct a fork with original state transitions unchanged.
    Only the chosen criterion's decision changes, via globals local
    to THIS compiled fork. No mutations to imported original module."""
    disabled=frozenset(ABLATIONS[variant])
    if variant not in ABLATIONS:
        raise ValueError("ABLATION_UNKNOWN_VARIANT")
    if symbol!="SOLUSDT" and "sol_reversal" in disabled:
        raise ValueError("ABLATION_SOL_ONLY_VARIANT_IN_OTHER_COIN")

    def _skip(x):
        return x in disabled

    def _momentum_side(ind,side):
        if side not in ("bullish","bearish"):
            raise ValueError("ABLATION_UNKNOWN_SIDE")
        r=ind["RSI14"]
        h=ind["hist"]
        return (
            (_skip("rsi_direction") or (r>50 if side=="bullish" else r<50))
            and
            (_skip("macd_direction") or (h>0 if side=="bullish" else h<0))
        )

    def _momentum_possible(ind):
        return _momentum_side(ind,"bullish") or _momentum_side(ind,"bearish")

    def _htf_side(tf_bias,side):
        return ((_skip("trend4h") or tf_bias[0]==side)
                and (_skip("trend1d") or tf_bias[1]==side))

    def _htf_any(tf_bias):
        return _htf_side(tf_bias,"bullish") or _htf_side(tf_bias,"bearish")

    def _bos_quality(window,bos,ind):
        return evaluate_bos_quality(
            window,bos,ind,
            min_break_atr=(-1.e12 if _skip("bos_break_atr") else .20),
            min_rvol20=(0. if _skip("bos_rvol20") else 1.20),
            max_extension_atr=(1.e12 if _skip("bos_ema_extension") else 2.50),
        )

    def _reaction_confirmed(side,bar,prev,level):
        if not(bar["l"]<=level<=bar["h"]):
            return False
        if side=="bullish":
            return (bar["c"]>level
                    and (_skip("retest_color") or bar["c"]>bar["o"])
                    and (_skip("retest_prev_close") or bar["c"]>prev["c"]))
        if side=="bearish":
            return (bar["c"]<level
                    and (_skip("retest_color") or bar["c"]<bar["o"])
                    and (_skip("retest_prev_close") or bar["c"]<prev["c"]))
        raise ValueError("ABLATION_UNKNOWN_RETEST_SIDE")

    def _init_position(pending,entry,ts):
        if not (_skip("risk_min_pct") or _skip("risk_max_pct")):
            return original.init_position(pending,entry,ts)
        stop=pending["stop"]
        risk=abs(entry-stop)
        if (risk<=0 or entry<=0
            or (pending["side"]=="bearish" and stop<=entry)
            or (pending["side"]=="bullish" and stop>=entry)):
            return None
        r=risk/entry
        minimum=(.0005 if _skip("risk_min_pct") else .001)
        maximum=(.06 if _skip("risk_max_pct") else .04)
        if not minimum<=r<=maximum:
            return None
        sign=1 if pending["side"]=="bullish" else -1
        return {**pending,"entry":entry,"entryOpenUTC":ts,"risk":risk,
                "targets":[entry+sign*risk*n for n in (1,2,3)],
                "targetCount":0,"realizedR":0.}

    def _indicators(bars):
        key=(bars[0]["t"],bars[1]["t"]-bars[0]["t"],len(bars))
        if key not in cache["indicators"]:
            cache["indicators"][key]=original.indicators(bars)
        return cache["indicators"][key]

    def _bias(bars):
        key=(bars[0]["t"],bars[1]["t"]-bars[0]["t"],len(bars))
        if key not in cache["bias"]:
            cache["bias"][key]=original.bias(bars)
        return cache["bias"][key]

    def _analyze(window,interval,as_of):
        if interval!="1hour" or len(window)!=250:
            raise ValueError("ABLATION_UNEXPECTED_STRUCTURE_INPUT")
        key=as_of
        if key not in cache["structures"]:
            cache["structures"][key]=original.analyze(
                window,interval,as_of=as_of)
        return cache["structures"][key]

    # Same engine code, original helper names except the single
    # selected gate's substitutions and research-only wrappers.
    namespace=dict(vars(original))
    namespace.update({
        "_skip":_skip,
        "_momentum_possible":_momentum_possible,
        "_momentum_side":_momentum_side,
        "_htf_side":_htf_side,
        "_htf_any":_htf_any,
        "indicators":_indicators,
        "bias":_bias,
        "analyze":_analyze,
        "reaction_confirmed":_reaction_confirmed,
        "init_position":_init_position,
    })
    exec(compile(fork_source(),"<research-only-v92-fork>","exec"),namespace)
    return namespace["replay_pair"],_bos_quality


def double_checked_candles(rows,end):
    if rows[0]["t"]%3600 or rows[-1]["t"]+HOUR!=end:
        raise ValueError("ABLATION_SOURCE_TIME_BOUNDARY")
    return aggregate(rows,FOUR),aggregate(rows,24*HOUR)


def _key(t):
    return (int(t["entryOpenUTC"]),t["side"])

def _trades(report,start,end):
    if report.get("status")!="PAPER_BACKTEST_NOT_LIVE":
        raise ValueError("ABLATION_INVALID_REPLAY")
    return sorted(
        (t for t in report["trades"]
         if start<=t["entryOpenUTC"]<end and t["exitKnownUTC"]<=end),
        key=lambda t:(t["entryOpenUTC"],t["side"]))


def paired(baseline,variant):
    b={_key(x):x for x in baseline}
    v={_key(x):x for x in variant}
    if len(b)!=len(baseline) or len(v)!=len(variant):
        raise ValueError("ABLATION_DUPLICATE_TRADE_KEY")
    shared=set(b)&set(v)
    for key in shared:
        a,c=b[key],v[key]
        if (abs(a["netRIllustrative"]-c["netRIllustrative"])>1e-9
            or a["exitKnownUTC"]!=c["exitKnownUTC"]):
            raise ValueError("ABLATION_SHARED_ENTRY_PNL_DRIFT")
    dropped=[b[k] for k in sorted(set(b)-set(v))]
    added=[v[k] for k in sorted(set(v)-set(b))]
    return {
        "baselineWinnersLost":sum(t["netRIllustrative"]>0 for t in dropped),
        "baselineLosersAvoided":sum(t["netRIllustrative"]<=0 for t in dropped),
        "baselineWinnersRLost":round(sum(t["netRIllustrative"] for t in dropped
                                          if t["netRIllustrative"]>0),6),
        "baselineLosersRAvoided":round(sum(t["netRIllustrative"] for t in dropped
                                              if t["netRIllustrative"]<=0),6),
        "newTrades":len(added),
        "newWinners":sum(t["netRIllustrative"]>0 for t in added),
        "newLosers":sum(t["netRIllustrative"]<=0 for t in added),
        "newTradesNetR9Bps":round(sum(t["netRIllustrative"] for t in added),6),
        "baselineTradesRetained":len(shared),
        "droppedEntryUTC":[stamp(t["entryOpenUTC"]) for t in dropped],
        "addedEntryUTC":[stamp(t["entryOpenUTC"]) for t in added],
        "tradeKeyCollisionChecked":True,
    }


def to_score(report,start,end):
    score=metrics(report,start,end)
    tr=_trades(report,start,end)
    if len(tr)!=score["trades"]:
        raise ValueError("ABLATION_METRIC_TRADE_COUNT_DIFFERENCE")
    normal=[float(t["netRIllustrative"]) for t in tr]
    stres=[r-2*(25-9)/10000*t["entry"]/t["risk"]
           for t,r in zip(tr,normal)]
    byside={}
    for side in ("bullish","bearish"):
        subset=[(a,b) for t,a,b in zip(tr,normal,stres) if t["side"]==side]
        byside[side]={
            "trades":len(subset),
            "wins":sum(a>0 for a,b in subset),
            "netR9Bps":round(sum(a for a,b in subset),6),
            "netR25Bps":round(sum(b for a,b in subset),6),
        }
    losses=-sum(min(0,r) for r in normal)
    wins=sum(max(0,r) for r in normal)
    return {
        "trades":score["trades"],"wins":score["wins"],
        "winRatePct":score["winRatePct"],
        "netR9Bps":score["totalNetR9BpsPerSide"],
        "netR25Bps":score["totalNetR25BpsPerSideStress"],
        "meanR9Bps":score["netRMean"],
        "profitFactor9Bps":round(wins/losses,4) if losses else None,
        "maxDrawdownR9Bps":score["maxDrawdownR"],
        "BOSWatches":score["BOSWatches"],
        "retestVetoes":score["retestVetoes"],
        "riskRejected":report["riskRuleRejected"],
        "direction":byside,
        "tradeEvidence":[{
            "entryUTC":stamp(t["entryOpenUTC"]),
            "retestUTC":stamp(t["retestKnownUTC"]),
            "side":t["side"],
            "exitUTC":stamp(t["exitKnownUTC"]),
            "exitReason":t["exitReason"],
            "entry":round(t["entry"],8),
            "riskPct":round(100*t["risk"]/t["entry"],5),
            "netR9Bps":round(t["netRIllustrative"],6),
        } for t in tr],
        "noHistoricalTradesCreditedToForward":True,
    }


def evaluate(symbol,rows,start,end):
    four,daily=double_checked_candles(rows,end)
    cache={"indicators":{},"bias":{},"structures":{}}
    all_scores={}
    raw={}
    for mode in ABLATIONS:
        if mode=="NO_SOL_SELECTED_REVERSAL_VETO" and symbol!="SOLUSDT":
            continue
        engine,quality=instrumentation(mode,symbol=symbol,four=four,cache=cache)
        audit=Counter(examples=[])
        selected_veto=(make_selective_gate(
            symbol,four,"SELECTED_SOL_STRICT_SWEEP",audit)
            if symbol=="SOLUSDT" and
            "sol_reversal" not in ABLATIONS[mode] else None)
        result=engine(
            rows,four,daily,as_of=end,
            retest_hours=(6 if "retest_window" in ABLATIONS[mode] else 4),
            bos_quality_filter=quality,
            retest_quality_filter=selected_veto,
        )
        score=to_score(result,start,end)
        score["solReversalGateAudit"]={
            k:v for k,v in audit.items()}
        score["disabledGates"]=list(ABLATIONS[mode])
        raw[mode]=_trades(result,start,end)
        all_scores[mode]=score
        if mode=="BASELINE":
            parity_check(
                "2022_2024" if start==epoch(PERIODS["2022_2024"]["start"])
                else "2024_2026",symbol,{
                    "trades":score["trades"],
                    "totalNetR9BpsPerSide":score["netR9Bps"],
                    "totalNetR25BpsPerSideStress":score["netR25Bps"],
                })
        print("V92_ABLATION",symbol,mode,score["trades"],
              score["netR9Bps"],score["netR25Bps"],flush=True)
    baseline=all_scores["BASELINE"]
    for mode,score in all_scores.items():
        score["deltaR9BpsVsBaseline"]=round(
            score["netR9Bps"]-baseline["netR9Bps"],6)
        score["deltaR25BpsVsBaseline"]=round(
            score["netR25Bps"]-baseline["netR25Bps"],6)
        score["pairedVsBaseline"]=paired(raw["BASELINE"],raw[mode])
    return {"variants":all_scores,
            "engineCaches":{
                "distinctIndicatorDecisionPoints":len(cache["indicators"]),
                "distinctHTFTrendDecisionPoints":len(cache["bias"]),
                "distinctCausalStructureComputations":len(cache["structures"]),
            }}


def valid_baseline_period(period,asset,score):
    n,r,stress=EXPECTED_PREVIOUS[(period,asset)]
    return (score["trades"]==n
            and abs(score["netR9Bps"]-r)<.00016
            and abs(score["netR25Bps"]-stress)<.00016)


def followup_shortlist(report):
    """Strictly score preliminary one-gate removals using FIRST period
    alone. Later-period values are only reported, NEVER used to
    refine selection. For exploratory consideration require positive
    delta under both 9bps and 25bps, not merely zero trades."""
    choices={}
    earlier=report["periods"]["2022_2024"]["assets"]
    later=report["periods"]["2024_2026"]["assets"]
    for coin in SYMBOLS:
        base=earlier[coin]["variants"]["BASELINE"]
        eligible=[]
        for mode in ONE_BY_ONE:
            if mode not in earlier[coin]["variants"]:
                continue
            sc=earlier[coin]["variants"][mode]
            new=sc["pairedVsBaseline"]["newTrades"]
            if (new>=2
                and sc["trades"]>=max(5,base["trades"]-2)
                and sc["deltaR9BpsVsBaseline"]>0
                and sc["deltaR25BpsVsBaseline"]>0
                and sc["maxDrawdownR9Bps"]<=base["maxDrawdownR9Bps"]+1):
                eligible.append(mode)
        eligible=sorted(eligible,key=lambda m:(
            -earlier[coin]["variants"][m]["deltaR25BpsVsBaseline"],m))
        choices[coin]={
            "earlyEligibleExploratory":eligible,
            "doNotPromoteWithoutForwardValidation":True,
            "laterPeriodUsedToSelect":False,
            "laterObserved":{name:{
                "deltaR9Bps":later[coin]["variants"][name]["deltaR9BpsVsBaseline"],
                "deltaR25Bps":later[coin]["variants"][name]["deltaR25BpsVsBaseline"],
                "trades":later[coin]["variants"][name]["trades"],
            } for name in eligible}
        }
    return choices


def run(workers):
    fork_source()  # verify original unchanged BEFORE downloading data
    hist,proof=download_all(workers)
    result={
        "status":"V92_FULL_FILTER_ONE_BY_ONE_AND_FOUR_PAIRS_RESEARCH_ONLY",
        "baseline":"Current V7-quality + V9.1 max 4H retest, with original V9.2 SOL-only Star/Harami prior20 sweep/reentry veto; ETH/BTC no candle veto",
        "variants":{k:list(v) for k,v in ABLATIONS.items()},
        "oneAtATime":list(ONE_BY_ONE),
        "predeclaredPairs":list(PAIRS),
        "safetyBackboneNeverDisabled":list(CONTROL_REQUIREMENTS),
        "riskStopsAreResearchSensitivityNotRiskRecommendations":True,
        "data":"Binance official USD-M monthly 1H ZIP archives SHA256 verified",
        "archiveCountSHA256":sum(len(x) for x in proof.values()),
        "costPerSideBps":[9,25],
        "periods":{},
        "onlyEarlierPeriodMayDetermineExploratorySelection":True,
        "earlierAndLaterAlreadyHistoricallyInspectedNoTrueUnseenOOS":True,
        "noNewLiveSignalConfiguration":True,
        "noProductionV7V92Changes":True,
        "noOrders":True,"noNotifications":True,
        "noForwardCappedAccountEdits":True,
        "noFundingRealSlippageOrLiquidationVerification":True,
    }
    for pname,period in PERIODS.items():
        p={
            "scoredUTC":[period["start"],period["end"]],
            "warmupUTC":period["warmup"],
            "verifiedArchives":len(proof[pname]),
            "sourceManifest":proof[pname],
            "assets":{},
        }
        for asset in SYMBOLS:
            scored=evaluate(asset,hist[pname][asset],
                            epoch(period["start"]),epoch(period["end"]))
            if not valid_baseline_period(pname,asset,
                                         scored["variants"]["BASELINE"]):
                raise ValueError("ABLATION_PREVIOUS_SIX_BASELINES_DIVERGED")
            p["assets"][asset]=scored
        result["periods"][pname]=p
    result["earlierOnlyCandidateSelection"]=followup_shortlist(result)
    return result


def markdown(data):
    names=list(ABLATIONS)
    lines=[
        "# V9.2 filtre ablasyon testi — BTC / ETH / SOL, 2022–2026",
        "",
        "**Sadece tarihsel araştırma. V7, V9.2 sanal hesap, bildirim ve emir değişmedi.**",
        "",
        "159 resmî Binance 1H aylık USD-M arşivi SHA256 ile doğrulandı.",
        "2022-10..2024-09 ve 2024-10..2026-09 iki ayrı inceleme dönemi.",
        "Her varyantta aynı kronolojik BOS → daha sonra retest → sonraki 1H açılışı,",
        "stop-first, TP1/2/3 üçte bir ve 24h maksimum tutma mekanizması geçerlidir.",
        "Maliyet 9bps/yön; stres 25bps/yön, gerçek fonlama/dolum kanıtı değildir.",
        "Önceden dondurulan 1×14 filtre ablasyonu + 4 çiftli etkileşim testi;",
        "hiçbir kombinasyon sonuca bakılarak üretilmedi.",
        "Altı baseline önceki SHA256 çalışmaları ile sonuç eşleşmesi zorunludur.",
        "",
        "## Birer filtre kaldırma (BASELINE dahil)",
        "",
        "| Dönem | Coin | Kural | İşlem | Win% | Net R 9bps | Net R 25bps | ΔR9 | ΔR25 | MaxDD R | Yeni işlem | Kaçırılan kârlı | Önlenen zararlı |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for pname,p in data["periods"].items():
        for asset,a in p["assets"].items():
            for mode in ("BASELINE",)+ONE_BY_ONE:
                if mode not in a["variants"]:
                    continue
                s=a["variants"][mode]
                p2=s["pairedVsBaseline"]
                lines.append(
                    f"| {pname} | {asset[:3]} | {mode} | {s['trades']} | "
                    f"{s['winRatePct'] if s['winRatePct'] is not None else '—'} | "
                    f"{s['netR9Bps']:+.4f} | {s['netR25Bps']:+.4f} | "
                    f"{s['deltaR9BpsVsBaseline']:+.4f} | "
                    f"{s['deltaR25BpsVsBaseline']:+.4f} | "
                    f"{s['maxDrawdownR9Bps']:.3f} | "
                    f"{p2['newTrades']} | {p2['baselineWinnersLost']} | "
                    f"{p2['baselineLosersAvoided']} |")
    lines += [
        "", "## Önceden seçilmiş ikili etkileşim senaryoları", "",
        "| Dönem | Coin | Kombinasyon | İşlem | Net R9 | Net R25 | ΔR9 | ΔR25 |",
        "|---|---|---|---:|---:|---:|---:|---:|",
    ]
    for pname,p in data["periods"].items():
        for asset,a in p["assets"].items():
            for mode in PAIRS:
                s=a["variants"][mode]
                lines.append(
                    f"| {pname} | {asset[:3]} | {mode} | {s['trades']} | "
                    f"{s['netR9Bps']:+.4f} | {s['netR25Bps']:+.4f} | "
                    f"{s['deltaR9BpsVsBaseline']:+.4f} | "
                    f"{s['deltaR25BpsVsBaseline']:+.4f} |")
    lines += ["", "## Sadece ilk dönem verisine göre ön adaylar", ""]
    for asset,v in data["earlierOnlyCandidateSelection"].items():
        choices=", ".join(v["earlyEligibleExploratory"]) or "YOK"
        lines.append(f"- **{asset}**: {choices}")
    lines += [
        "", "## Önemli yorum ve güvenlik", "",
        "- Bir filtreyi çıkarmak işlem dizisini değiştirebilir: yeni işlemler daha sonra gelecek başka işlemleri engelleyebilir. Çıkarılan/eklenen işlemler tarihle eşleştirildi, yalnızca kazanç yüzdesine bakılmadı.",
        "- V9.2'de BOS yapısı, retest teması, retest kapanışının BOS seviyesinin doğru tarafında olması ve sonraki 1H açılışı hiçbir deneyde kaldırılmadı.",
        "- Mevcut 1H BOS hacmi %20, RSI/MACD yön, 4H/Daily yön, BOS en az 0.2 ATR, RVOL20 1.2, EMA20 en fazla 2.5ATR, SOL seçici mum veto; risk aralığı %0.1-4 ve 4H retest limiti başlangıçtır.",
        "- V7 ayrı 6H / 4H+retest-strength varyantları içerebilir. Bu ablation yalnızca mevcut V9.2 referansını değiştirir; V7 production için test edilmiş değildir.",
        "- 9bps/25bps şeması fonlamayı, değişken spread ve stop kaymalarını tam yansıtmaz. 1000 USDT capped paper defterine tarihsel işlem eklenmedi.",
        "- Filtre kombinasyonları aynı dönemlerde daha önce incelenmiş sinyaller üzerinde test edildi. Çoklu karşılaştırma ve sonradan seçim yanlılığı yüksektir; geleceğe dönük kârlılık kanıtı değildir.",
        "- Daha az işlem yapan modelin 0R sonucu iyi performans değil işlem yapmamasıdır. Tekrarlanamayan veya az örnekli 'kazanan' parametre önerisi yoktur.",
        "",
    ]
    return "\n".join(lines)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--workers",type=int,default=6)
    ap.add_argument("--out",default="forward/v92_filter_ablation_20261113")
    args=ap.parse_args()
    if not 1<=args.workers<=6:
        ap.error("workers must be 1..6")
    result=run(args.workers)
    folder=Path(args.out);folder.mkdir(parents=True,exist_ok=True)
    (folder/"historical.json").write_text(
        json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    (folder/"historical.md").write_text(markdown(result)+"\n")
    print("V92_159_SHA256_SIX_BASELINE_PARITY_FULL_FILTER_ABLATION_DONE",flush=True)


if __name__=="__main__":
    main()
