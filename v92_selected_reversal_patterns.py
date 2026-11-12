#!/usr/bin/env python3
"""V9.2 SELECTIVE reversal-warning research, old V7/V9.1 unaffected.

CAUTION: "High quality" means a transparent short-list for a *new trial*,
NOT statistically demonstrated hit rate. There was only ONE matched,
previously observed losing SOL trade eliminated by both Morning Star
and confirmed Harami. Do NOT extrapolate 61.5% to future wins.

Research policy frozen before this new replay:
 - SOL: ONLY confirmed 1H/4H Morning/Evening Star and Harami,
   AND prior-20 high/low sweep + close back inside, may VETO opposite
   V7 BOS -> retest hypothetical fills in a separately replayed trial.
 - BTC: OBSERVE ONLY; no form veto (existing Hikkake/Engulfing removed
   profitable BTC trades in inspected historical period).
 - Other patterns: OBSERVE ONLY (Hikkake/Engulfing), never automatic
   entries, never BTC vetoes, no alerts and no real orders.
 - Three White Soldiers/Three Black Crows (3-same-direction 1H/4H
   closed candles) are added as exploratory *watch* candidates only.
   Stock market reversal statistics MUST NOT be imported as crypto odds.

All thresholds are fixed and symmetric, source timestamps verified.
Full chronological replay; no posthoc deletion of losers.
"""
import argparse
from collections import Counter
from datetime import datetime,timezone
import json
from pathlib import Path

from backtest_retest_long_v4 import replay_pair
from market_structure import candles_from_history
from signal_quality_v7 import evaluate_bos_quality
from v7_paper_comparison import read_history
from v92_bull_bear_candle_invalidation import (
    START,END,HOUR,FOUR,SYMBOLS,stamp,metrics
)
from v92_multi_candle_invalidation import (
    all_patterns_at,warnings_at_retest,trend_before,validate_tail,sweep_before
)

STRATEGY="V92_SELECTED_STAR_HARAMI_PRIOR20_SWEEP_SHADOW_ONLY"
RESEARCH_QUALIFICATION={
  "selectedForTest":[
      "MORNING_STAR","EVENING_STAR",
      "BULLISH_HARAMI_CONFIRMED","BEARISH_HARAMI_CONFIRMED"],
  "selectedPatternFamilies":["STAR","HARAMI_CONFIRMED"],
  "eligibleOnlyOn":"SOLUSDT",
  "requirePrior20HighLowSweepAndReentry":True,
  "BTCUSDT":"OBSERVE_ONLY",
  "HIKKAKE_CONFIRMED":"OBSERVE_ONLY",
  "ENGULFING":"OBSERVE_ONLY",
  "THREE_WHITE_SOLDIERS":"OBSERVE_ONLY_NEW_CANDIDATE",
  "THREE_BLACK_CROWS":"OBSERVE_ONLY_NEW_CANDIDATE",
  "whyNotAllReversals":"Previously inspected historical BTC profitable trades were rejected by Hikkake/Engulfing",
  "isStatisticallyValidatedHighSuccessRate":False,
  "separateUnmodifiedV7AndV91":True,
  "requiresIndependentProspectiveClosedTradesBeforeDeployment":True,
}

def soldier_crow(bars,i,seconds):
    """Exploratory 3-candle reversal; no gaps required in perpetual market."""
    if i<27:return None
    cut=bars[max(0,i-34):i+1]
    if not validate_tail(cut,seconds):return None
    a,b,c=bars[i-2:i+1]
    def bullish(x):return x["c"]>x["o"]
    def bearish(x):return x["c"]<x["o"]
    if any(x["h"]<=x["l"] or
           abs(x["c"]-x["o"])/(x["h"]-x["l"])<.5 for x in (a,b,c)):
        return None
    if (all(bullish(x) for x in (a,b,c))
        and a["c"]<b["c"]<c["c"]
        and a["o"]<=b["o"]<=a["c"]
        and b["o"]<=c["o"]<=b["c"]
        and trend_before(bars,i-2,"bullish")):
        direction="bullish"
        name="THREE_WHITE_SOLDIERS"
    elif (all(bearish(x) for x in (a,b,c))
          and a["c"]>b["c"]>c["c"]
          and a["c"]<=b["o"]<=a["o"]
          and b["c"]<=c["o"]<=b["o"]
          and trend_before(bars,i-2,"bearish")):
        direction="bearish"
        name="THREE_BLACK_CROWS"
    else:return None
    return {
        "name":name,"direction":direction,
        "confirmedUTC":stamp(int(c["t"])+seconds),
        "prior20LiquiditySweepAndReentry":sweep_before(
            bars,i-2,i,direction),
        "researchWatchOnly":True,"noAutoVeto":True,"noStandaloneTrade":True,
        "fromFullyClosedCandles":True}

def make_selective_gate(symbol,four,mode,audit):
    if mode not in ("OBSERVE_ONLY","SELECTED_SOL_STRICT_SWEEP",
                   "SELECTED_SOL_ANY_CLOSED_PATTERN"):
        raise ValueError("V92_SELECTIVE_UNKNOWN_MODE")
    def gate(bars,active,retest):
        at=int(retest["t"])+HOUR
        opposed=warnings_at_retest(
           bars,four,at,active["side"],{"STAR","HARAMI_CONFIRMED"},
           require_sweep=(mode=="SELECTED_SOL_STRICT_SWEEP"))
        audit["retests"]+=1
        if opposed:
            audit["opposingSelectedPatternsObserved"]+=1
            for x in opposed:audit[x["name"]+"_"+x["tf"]]+=1
        for x in opposed:
            if len(audit["examples"])<30:
                audit["examples"].append({"retestUTC":stamp(at),
                                          "activeBOSDirection":active["side"],
                                          "pattern":x,"mode":mode})
        # BTC receives warnings only, never a trade blocking filter.
        veto=bool(symbol=="SOLUSDT" and mode!="OBSERVE_ONLY" and opposed)
        if veto:
            audit["vetoes"]+=1
        return {"passed":not veto,
                "reasons":["V92_SOL_SELECTED_OPPOSING_CONFIRMED_REVERSAL"]
                if veto else []}
    return gate

def summarize_audit(a):
    return {"originalRetestsAssessed":a["retests"],
            "opposingSelectedWarningRetests":a["opposingSelectedPatternsObserved"],
            "rejectedRetests":a["vetoes"],
            "byPattern":{k:v for k,v in a.items()
                         if isinstance(v,int) and k not in (
                           "retests","opposingSelectedPatternsObserved","vetoes")},
            "examples":a["examples"]}

def run(hist,prior):
    if (prior.get("mode")!="V92_HARAMI_HIKKAKE_ENGULFING_STAR_RETEST_INVALIDATION_FULL_HISTORY_PAPER_ONLY"
        or not prior.get("sameConfirmedSourceForAllVariants")
        or prior.get("historicalFromUTC")!=stamp(START)
        or prior.get("historicalUntilExclusiveUTC")!=stamp(END)):
        raise ValueError("V92_SELECTED_BASELINE_UNVERIFIED")
    result={
        "status":"SELECTIVE_SOL_STAR_HARAMI_AND_OTHER_HIGH_PROFILE_CANDLE_WATCHES_HISTORICAL_ONLY",
        "preRegisteredStrategyId":STRATEGY,
        "fromUTC":stamp(START),"toUTCExclusive":stamp(END),
        "policy":RESEARCH_QUALIFICATION,
        "sameVerifiedBinanceBTCAndSOLSource":True,
        "originalSourceArchiveSHAValidatedPreviously":True,
        "requiresOnlyClosed1HAnd4HBars":True,
        "usesSameOriginal1H4HDailyV7QualityRetestNextOpenAndExits":True,
        "noV7V91ProductionChanges":True,
        "noNewTradeNotifications":True,
        "noBrokerOrders":True,
        "notRealProfit":True,
        "previouslyInspectedDataNotIndependent":True,
        "noClaimOfStatisticallyProvenHighWinRate":True,
        "symbols":{},
    }
    for sym,ref in SYMBOLS.items():
        h=hist["1hour"][ref]
        f=hist["4hour"][ref]
        d=hist["daily"][ref]
        closedh=candles_from_history(h,"1hour",END)
        closedf=candles_from_history(f,"4hour",END)
        closedd=candles_from_history(d,"daily",END)
        if (len(closedh)!=17520 or len(closedf)!=4380
                or len(closedd)!=730):
            raise ValueError("V92_SELECTED_SOURCE_ARCHIVE_MISMATCH_"+sym)
        exploratory={}
        for tf,bars,secs in (("1H",closedh,HOUR),("4H",closedf,FOUR)):
            c=Counter()
            for i in range(27,len(bars)):
                x=soldier_crow(bars,i,secs)
                if x:
                    c[x["name"]]+=1
                    if x["prior20LiquiditySweepAndReentry"]:
                        c[x["name"]+"_PRIOR20_SWEEP"]+=1
            exploratory[tf]=dict(c)
        variants={}
        baseline=prior["symbols"][sym]["variants"]
        for base_name,hours in (("V7_ORIGINAL",6),("V91_RETEST_MAX4H",4)):
            previous=baseline[base_name]
            # Baseline remains from previously PASSING exact same 2-year
            # artifact / original source; our newly replayed chosen variants
            # MUST NOT mutate those baseline entries.
            variants[base_name]={
                k:previous[k] for k in (
                    "trades","wins","winRatePct",
                    "totalNetR9BpsPerSide","totalNetR25BpsPerSideStress",
                    "maxDrawdownR","retestVetoes")}
            for mode in ("OBSERVE_ONLY","SELECTED_SOL_STRICT_SWEEP",
                         "SELECTED_SOL_ANY_CLOSED_PATTERN"):
                audit=Counter();audit["examples"]=[]
                replay=replay_pair(
                   h,f,d,as_of=END,retest_hours=hours,
                   bos_quality_filter=evaluate_bos_quality,
                   retest_quality_filter=make_selective_gate(sym,closedf,mode,audit))
                score=metrics(replay,START,END)
                key=base_name+"__"+mode
                # Only V7/V9.1 original source-matched snapshots are
                # eligible for causal comparisons.
                if mode=="OBSERVE_ONLY" and (
                    score["trades"]!=previous["trades"]
                    or score["wins"]!=previous["wins"]
                    or abs(score["totalNetR9BpsPerSide"]-
                           previous["totalNetR9BpsPerSide"])>.00001):
                    raise ValueError("V92_SELECTED_BASELINE_REPLAY_DIVERGENCE_"+sym)
                score["deltaTotalRVsOwnUnchangedBaseline"]=round(
                    score["totalNetR9BpsPerSide"]-
                    previous["totalNetR9BpsPerSide"],6)
                score["audit"]=summarize_audit(audit)
                score["symbolEligibleToVeto"]=sym=="SOLUSDT"
                score["requiresPrior20Sweep"]=mode=="SELECTED_SOL_STRICT_SWEEP"
                variants[key]=score
        result["symbols"][sym]={
            "verifiedCandles":{"1H":len(closedh),"4H":len(closedf),
                               "Daily":len(closedd)},
            "additionalSoldiersCrowsResearchOnlyCounts":exploratory,
            "variants":variants}
    return result

def markdown(result):
    lines=[
        "# V9.2 seçici dönüş mumları / güçlü aday havuzu",
        "",
        "**Yalnızca tarihi paper araştırması. Bu formasyonların gelecek başarı oranları kanıtlanmadı.**",
        "SOL: 1H/4H kapanmış Morning/Evening Star veya üçüncü mumla teyitli Harami;",
        "önceki 20 mumun tepe/dip likidite süpürmesi + bölgeye geri kapanış şartıyla",
        "**yalnız ayrı araştırma modelinde** aksi yönlü retest'i engeller.",
        "BTC: Tüm formasyonlar sadece uyarı (önceki testlerde bazı kârlı BTC işlemleri elenmişti).",
        "Hikkake, Engulfing, Three White Soldiers, Three Black Crows: sadece gözlem.",
        "",
        "Geçmiş: "+result["fromUTC"]+" – "+result["toUTCExclusive"]+" (hariç).",
        "1H/4H/Daily resmî, daha önce SHA256 ile doğrulanmış BTC/SOL arşivi.",
        "Maliyet 9 bps/yön, stres 25 bps/yön; fonlama, fiili dolum, zorunlu tasfiye tam modellenmiyor.",
        "",
        "| Coin | Sürüm | İşlem | Kazanan | Win % | Net R | Stres R | Baz göre fark R | Retest veto |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|"]
    for sym,item in result["symbols"].items():
        for mode,s in item["variants"].items():
            lines.append("| {} | {} | {} | {} | {} | {:.4f} | {:.4f} | {} | {} |".format(
                sym,mode,s["trades"],s["wins"],s["winRatePct"],
                s["totalNetR9BpsPerSide"],
                s["totalNetR25BpsPerSideStress"],
                s.get("deltaTotalRVsOwnUnchangedBaseline","—"),
                s["retestVetoes"]))
    lines+=["",
      "ÖNEMLİ: Hem Morning Star hem Harami aynı tek SOL kayıplı işlemi işaretledi;",
      "bu nedenle bunlar bağımsız iki başarı değildir. Tarihsel seçim yanlılığı yüksek.",
      "Canlıya almadan önce yeterince yeni, aynı anda kaydedilmiş ileri paper işlem",
      "ve farklı piyasa koşullarında kararlı net R üstünlüğü gerekir.",
      "V7/V9.1 orijinal hesapları, ana strateji ve bildirimler değiştirilmedi.",""]
    return "\n".join(lines)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--archive",default="v92_verified_archive")
    p.add_argument("--prior",default="forward/v92_multi_candle_invalidation/historical.json")
    p.add_argument("--out",default="forward/v92_selected_reversal_patterns")
    a=p.parse_args()
    historic={tf:read_history(str(Path(a.archive)/("history_"+tf+".json")))
              for tf in ("1hour","4hour","daily")}
    prior=json.loads(Path(a.prior).read_text())
    result=run(historic,prior)
    p=Path(a.out);p.mkdir(parents=True,exist_ok=True)
    (p/"historical.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    (p/"historical.md").write_text(markdown(result)+"\n")
    print("V92_SELECTIVE_REVERSE_1H4H_HISTORICAL_PAPER_DONE",
          json.dumps({sym:{key:{"R":v["totalNetR9BpsPerSide"],
                                "trades":v["trades"],
                                "veto":v["retestVetoes"]}
                          for key,v in data["variants"].items()}
                      for sym,data in result["symbols"].items()}),flush=True)
if __name__=="__main__":
    main()
