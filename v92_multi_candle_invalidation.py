#!/usr/bin/env python3
"""V9.2 BTC/SOL symmetric Harami, Hikkake, Engulfing, and Star invalidation.

Each decision uses only *completed* 1H/4H bars and the ORIGINAL unchanged
V7 BOS -> later retest -> next-hour hypothetical fill engine. A Harami
requires third-bar confirmation (Three Inside Up/Down-like) to avoid
treating an unconfirmed small inside body as a reversal. A Hikkake
requires an inside bar, a false breakout, and a close across the opposite
inside-bar bound within the NEXT THREE CLOSED bars. No hindsight or
future 4H. Fixed predeclared parameters, no outcome optimization.

Retest filters are research-only; not independent prospective evidence.
Historical data previously inspected; no orders/alerts/strategy promotion.
"""
import argparse
from bisect import bisect_right
from collections import Counter
from datetime import datetime,timezone
import json
import math
from pathlib import Path

from backtest_retest_long_v4 import replay_pair
from market_structure import candles_from_history
from signal_quality_v7 import evaluate_bos_quality
from v7_paper_comparison import read_history
from v92_bull_bear_candle_invalidation import (
    START,END,HOUR,FOUR,SYMBOLS,
    stamp,candle_star,metrics
)

FAMILIES=("STAR","HARAMI_CONFIRMED","HIKKAKE_CONFIRMED","ENGULFING")
RETEST_MODES=("HARAMI_CONFIRMED","HIKKAKE_CONFIRMED","ENGULFING",
              "ALL_REVERSALS","ALL_REVERSALS_SWEEP_CONTEXT")
BASELINES={"V7_ORIGINAL":6,"V91_RETEST_MAX4H":4}
REFERENCE_STATUS="V91_FULL_CHRONOLOGICAL_RETEST_ABLATION_PAPER_ONLY"

def validate_tail(bars, seconds):
    if len(bars)<27:return False
    for a,b in zip(bars[-32:-1],bars[-31:]):
        if int(b["t"])-int(a["t"])!=seconds or int(a["t"])%seconds:
            raise ValueError("V92_EXT_GAPPED_OR_UNALIGNED_CANDLES")
    for bar in bars[-32:]:
        o,h,l,c,v=(float(bar[k]) for k in ("o","h","l","c","v"))
        if (not all(math.isfinite(x) for x in (o,h,l,c,v)) or
            l<=0 or l>min(o,c) or h<max(o,c) or v<0):
            raise ValueError("V92_EXT_MALFORMED_CANDLE")
    return True

def trend_before(bars, first_index, side, horizon=5):
    """Direction of the preceding 5 closed bars, BEFORE pattern begins."""
    if first_index<horizon:return False
    before=float(bars[first_index-horizon]["c"])
    last=float(bars[first_index-1]["c"])
    return (last<before if side=="bullish" else last>before)

def sweep_before(bars, first, last, side):
    """Prior-20 high/low sweep AND current close re-enters earlier range."""
    if first<20:return False
    prior=bars[first-20:first]
    hi=max(float(x["h"]) for x in prior)
    lo=min(float(x["l"]) for x in prior)
    observed=bars[first:last+1]
    close=float(bars[last]["c"])
    if side=="bullish":
        return min(float(x["l"]) for x in observed)<lo and close>lo
    return max(float(x["h"]) for x in observed)>hi and close<hi

def pattern_at(bars,index, seconds, family):
    if family not in ("HARAMI_CONFIRMED","HIKKAKE_CONFIRMED","ENGULFING"):
        raise ValueError("V92_EXT_UNREGISTERED_PATTERN")
    if index<27:return None
    ctx=bars[max(index-35,0):index+1]
    # This safety check uses a *bounded* 32-bar window, not entire archive.
    if not validate_tail(ctx,seconds):return None
    def body(a):return abs(float(a["c"])-float(a["o"]))
    def bullish(a):return float(a["c"])>float(a["o"])
    def bearish(a):return float(a["c"])<float(a["o"])
    if family=="HARAMI_CONFIRMED":
        a,b,c=bars[index-2:index+1]
        first=index-2
        a_size=body(a)
        if (a_size<=0 or a_size/(a["h"]-a["l"])<.5 or
            body(b)>.50*a_size):
            return None
        upper=max(a["o"],a["c"]);lower=min(a["o"],a["c"])
        if min(b["o"],b["c"])<lower or max(b["o"],b["c"])>upper:
            return None
        if (bearish(a) and bullish(c) and
            c["c"]>max((a["o"]+a["c"])/2,b["h"]) and
            trend_before(bars,first,"bullish")):
            side="bullish"
        elif (bullish(a) and bearish(c) and
              c["c"]<min((a["o"]+a["c"])/2,b["l"]) and
              trend_before(bars,first,"bearish")):
            side="bearish"
        else:return None
    elif family=="ENGULFING":
        a,b=bars[index-1:index+1]
        first=index-1
        ar=float(a["h"]-a["l"]);br=float(b["h"]-b["l"])
        if (ar<=0 or br<=0 or body(a)<.25*ar or
            body(b)<1.05*body(a) or body(b)<.45*br):
            return None
        if (bearish(a) and bullish(b) and
            b["o"]<=a["c"] and b["c"]>=a["o"] and
            trend_before(bars,first,"bullish")):
            side="bullish"
        elif (bullish(a) and bearish(b) and
              b["o"]>=a["c"] and b["c"]<=a["o"] and
              trend_before(bars,first,"bearish")):
            side="bearish"
        else:return None
    else:
        # Confirmed Hikkake. On the breaking bar (b), strictly lower
        # high+low implies bullish setup; higher high+low implies bearish.
        # Only the first close across the opposite INSIDE-bar boundary
        # in the following 1,2,3 bars may confirm, never setup alone.
        matched=None
        for steps in (1,2,3):
            break_idx=index-steps
            inside_idx=break_idx-1
            mother_idx=break_idx-2
            if mother_idx<20:continue
            mother=bars[mother_idx]
            inside=bars[inside_idx]
            breaking=bars[break_idx]
            if not (inside["h"]<mother["h"] and inside["l"]>mother["l"]):
                continue
            if breaking["h"]<inside["h"] and breaking["l"]<inside["l"]:
                s="bullish"
                boundary=inside["h"]
                confirm=lambda x:x["c"]>boundary
            elif breaking["h"]>inside["h"] and breaking["l"]>inside["l"]:
                s="bearish"
                boundary=inside["l"]
                confirm=lambda x:x["c"]<boundary
            else:continue
            if (not confirm(bars[index]) or
                any(confirm(bars[j]) for j in range(break_idx+1,index))):
                continue
            # The false breakout is explicit; do not count unconfirmed
            # Hikkake setup signals as real reversals.
            matched=(s,mother_idx,break_idx)
            break
        if matched is None:return None
        side,first,_=matched
    fake=sweep_before(bars,first,index,side)
    return {
        "family":family,"name":side.upper()+"_"+family,
        "direction":side,
        "firstUTC":stamp(int(bars[first]["t"])),
        "confirmedUTC":stamp(int(bars[index]["t"])+seconds),
        "prior20LiquiditySweepAndReentry":bool(fake),
        "internalHikkakeFalseBreakConfirmed":family=="HIKKAKE_CONFIRMED",
        "crypto24hNoGapRequirement":True,
        "signalIsNotStandaloneTrade":True,
        "onlyClosedCandlesUsed":True
    }

def all_patterns_at(bars,index,seconds):
    result=[]
    x=candle_star(bars,index,seconds)
    if x:
        result.append({"family":"STAR","name":x["name"],
                       "direction":x["direction"],"firstUTC":x["startAtUTC"],
                       "confirmedUTC":x["closedAtUTC"],
                       "prior20LiquiditySweepAndReentry":x["fakeBreakoutPrior20SweepAndReentry"],
                       "internalHikkakeFalseBreakConfirmed":False,
                       "crypto24hNoGapRequirement":True,
                       "signalIsNotStandaloneTrade":True,"onlyClosedCandlesUsed":True})
    for family in FAMILIES[1:]:
        x=pattern_at(bars,index,seconds,family)
        if x:result.append(x)
    return result

def warnings_at_retest(one,four,at,active_side,allowed,require_sweep=False):
    if active_side not in ("bullish","bearish"):
        raise ValueError("V92_EXT_UNREGISTERED_BOS_DIRECTION")
    if (not one or one[-1]["t"]+HOUR!=at or any(
        one[i+1]["t"]-one[i]["t"]!=HOUR
        for i in range(max(0,len(one)-33),len(one)-1))):
        raise ValueError("V92_EXT_NO_MATCHED_CLOSED_HOUR")
    opposite="bearish" if active_side=="bullish" else "bullish"
    warns=[]
    # Only 1H patterns confirmed among the last FOUR completed hours.
    for i in range(max(27,len(one)-4),len(one)):
        for p in all_patterns_at(one,i,HOUR):
            if (p["family"] in allowed and p["direction"]==opposite and
                (not require_sweep or
                 p["prior20LiquiditySweepAndReentry"] or
                 p["internalHikkakeFalseBreakConfirmed"])):
                warns.append({**p,"tf":"1H"})
    # Include at most TWO most recent COMPLETED 4H pattern closes.
    n4=bisect_right([x["t"]+FOUR for x in four],at)
    for i in range(max(27,n4-2),n4):
        for p in all_patterns_at(four,i,FOUR):
            if (p["family"] in allowed and p["direction"]==opposite and
                (not require_sweep or
                 p["prior20LiquiditySweepAndReentry"] or
                 p["internalHikkakeFalseBreakConfirmed"])):
                warns.append({**p,"tf":"4H"})
    if any(datetime.fromisoformat(p["confirmedUTC"].replace("Z","+00:00")).timestamp()>at
           for p in warns):
        raise ValueError("V92_EXT_FUTURE_CONFIRMATION_LEAK")
    return warns

def make_retest_gate(four,mode,evidence):
    if mode not in RETEST_MODES:
        raise ValueError("V92_EXT_UNREGISTERED_RETEST_VARIANT")
    allowed=(set(FAMILIES) if mode.startswith("ALL") else {mode})
    require_sweep=(mode=="ALL_REVERSALS_SWEEP_CONTEXT")
    def gate(bars,active,retest):
        t=int(retest["t"])+HOUR
        warnings=warnings_at_retest(
            bars,four,t,active["side"],allowed,require_sweep)
        evidence["originalRetestsAssessed"]+=1
        if warnings:
            evidence["vetoedOriginalRetests"]+=1
            for warning in warnings:
                evidence[warning["name"]+"_"+warning["tf"]]+=1
            if len(evidence["vetoExamples"])<40:
                evidence["vetoExamples"].append({
                    "atUTC":stamp(t),"side":active["side"],"patterns":warnings})
            return {"passed":False,
                    "reasons":["V92_EXT_OPPOSITE_"+warnings[-1]["name"]]}
        return {"passed":True,"reasons":[]}
    return gate

def summarize_audit(e):
    return {"originalRetestsAssessed":e["originalRetestsAssessed"],
            "vetoedOriginalRetests":e["vetoedOriginalRetests"],
            "vetoPatternCounts":{k:v for k,v in e.items()
                                 if isinstance(v,int) and k not in
                                 ("originalRetestsAssessed","vetoedOriginalRetests")},
            "vetoExamples":e["vetoExamples"]}

def run(histories,baseline):
    if (baseline.get("status")!=REFERENCE_STATUS or
        baseline.get("originalV7BaselineVerifiedAgainstPublishedQualityBacktest") is not True or
        baseline.get("NOTIndependentOutOfSampleOrProspective") is not True):
        raise ValueError("V92_EXT_ORIGINAL_REPLAY_NOT_VERIFIED")
    result={
        "mode":"V92_HARAMI_HIKKAKE_ENGULFING_STAR_RETEST_INVALIDATION_FULL_HISTORY_PAPER_ONLY",
        "historicalFromUTC":stamp(START),"historicalUntilExclusiveUTC":stamp(END),
        "originalBacktestAlreadyInspectedAndOptimismRisk":True,
        "sameConfirmedSourceForAllVariants":True,
        "candleSets":["1H","4H","Daily"],
        "rulesFrozenBeforeReadingNewResults":True,
        "HikkakeMustBeConfirmedWithinNextThreeClosedBars":True,
        "HaramiRequiresThirdCandleConfirmation":True,
        "noIncomplete4HCandleUsed":True,
        "invalidationsOnlyAtRetestNotStandaloneTradeSignals":True,
        "sourcePerp":"Original SHA-verified Binance BTC SOL USD-M Futures archive",
        "patterns":list(FAMILIES),
        "symbols":{},
        "noBrokerOrders":True,"noUserNotifications":True,
        "BTC_SOL_V7_V91Unchanged":True,
        "ETHNotComparableWithoutSameCompleteLongArchive":True,
        "tradeFillsNotIndependentlyExecutable":True,
        "fundingVariableSlippageLiquidationNotFullyModeled":True,
    }
    for symbol,ref in SYMBOLS.items():
        h=histories["1hour"][ref]
        f=histories["4hour"][ref]
        d=histories["daily"][ref]
        closedh=candles_from_history(h,"1hour",END)
        closedf=candles_from_history(f,"4hour",END)
        closedd=candles_from_history(d,"daily",END)
        if min(len(closedh)/17000,len(closedf)/4000,len(closedd)/600)<1:
            raise ValueError("V92_EXT_INCOMPLETE_OR_UNVERIFIED_LONG_HISTORY_"+symbol)
        population={}
        for tf,bars,sec in [("1H",closedh,HOUR),("4H",closedf,FOUR)]:
            ctr=Counter()
            for i in range(27,len(bars)):
                for p in all_patterns_at(bars,i,sec):
                    ctr[p["name"]]+=1
                    if p["prior20LiquiditySweepAndReentry"]:
                        ctr[p["name"]+"_PRIOR20_SWEEP"]+=1
            population[tf]=dict(ctr)
        variants={}
        for base_name,hours in BASELINES.items():
            reference=baseline["results"][symbol][base_name]
            model=replay_pair(h,f,d,as_of=END,retest_hours=hours,
                              bos_quality_filter=evaluate_bos_quality)
            scored=metrics(model,START,END)
            if (scored["trades"]!=reference["trades"] or
                scored["wins"]!=reference["wins"] or
                abs(scored["totalNetR9BpsPerSide"]-
                    reference["totalNetR9bpsSide"])>.0001 or
                abs(scored["totalNetR25BpsPerSideStress"]-
                    reference["totalNetR25bpsSide"])>.0001):
                raise ValueError("V92_EXT_ORIGINAL_V7_V91_BASELINE_MISMATCH_"+symbol)
            variants[base_name]=scored
            for mode in RETEST_MODES:
                evidence=Counter()
                evidence["vetoExamples"]=[]
                cand=replay_pair(h,f,d,as_of=END,retest_hours=hours,
                    bos_quality_filter=evaluate_bos_quality,
                    retest_quality_filter=make_retest_gate(closedf,mode,evidence))
                entry=metrics(cand,START,END)
                entry["baseline"]=base_name
                entry["filterMode"]=mode
                entry["deltaTotalRVsOwnBaseline"]=round(
                    entry["totalNetR9BpsPerSide"]-
                    scored["totalNetR9BpsPerSide"],6)
                entry["audit"]=summarize_audit(evidence)
                variants[base_name+"__"+mode]=entry
        result["symbols"][symbol]={
            "verifiedCandleCounts":{"1H":len(closedh),
                                    "4H":len(closedf),"Daily":len(closedd)},
            "allHistoricalConfirmedPatternCounts":population,
            "variants":variants}
    return result

def markdown(out):
    lines=["# V9.2 Harami + Hikkake + Engulfing + Star sahte kırılım/invalidasyon",
           "",
           "**SADECE ESKİ MUM BACKTESTİ; GERÇEK/İLERİ DÖNÜK İŞLEM DEĞİL.**",
           "Geçmiş dönem: "+out["historicalFromUTC"]+" – "+
           out["historicalUntilExclusiveUTC"]+" (son tarih hariç).",
           "Harami üç mum teyitli; Hikkake ancak inside-bar sahte kırılımından sonra en geç üç bar içinde teyitli.",
           "V7 ve V9.1 giriş–çıkış ve BOS kuralları korunmuştur.",
           "",
           "| Sembol | Sistem | İşlem | Kazanan | Kazanma % | Net R | Stres net R | R farkı | Retest reddi |",
           "|---|---|---:|---:|---:|---:|---:|---:|---:|"]
    for sym,group in out["symbols"].items():
        for variant,r in group["variants"].items():
            lines.append("| {} | {} | {} | {} | {} | {:.4f} | {:.4f} | {} | {} |".format(
                sym,variant,r["trades"],r["wins"],r["winRatePct"],
                r["totalNetR9BpsPerSide"],
                r["totalNetR25BpsPerSideStress"],
                r.get("deltaTotalRVsOwnBaseline","—"),
                r["retestVetoes"]))
    lines+=["","Bu sonuçlar geçmişte incelenmiş dönemdedir; filtreler geçmişte şans eseri "
            "bir zarar işlemini elemiş olabilir. Komisyon baz 9bp/yön ve stres 25bp/yön. "
            "Gerçek emir dolumu, spread, funding, tasfiye ve gecikme tam modellenmez.",
            "Kârlı işlemleri yanlış eleme riski ayrıca izlenmelidir.",
            "V7, V9.1 ve mevcut 1.000 USDT sanal hesaplar değişmedi.",
            ""]
    return "\n".join(lines)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--archive",default="v92_verified_archive")
    p.add_argument("--reference",default="forward/v91_retest_full_replay/compare.json")
    p.add_argument("--out",default="forward/v92_multi_candle_invalidation")
    args=p.parse_args()
    histories={tf:read_history(str(Path(args.archive)/("history_"+tf+".json")))
               for tf in ("1hour","4hour","daily")}
    baseline=json.loads(Path(args.reference).read_text())
    report=run(histories,baseline)
    destination=Path(args.out);destination.mkdir(parents=True,exist_ok=True)
    (destination/"historical.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    (destination/"historical.md").write_text(markdown(report)+"\n")
    print("V92_MULTIPATTERN_FULL_HISTORY_PAPER_ONLY_COMPLETE",
          json.dumps({s:{name:{"trades":v["trades"],
                              "R":v["totalNetR9BpsPerSide"],
                              "vetoes":v["retestVetoes"]}
                          for name,v in group["variants"].items()}
                      for s,group in report["symbols"].items()}),
          flush=True)

if __name__=="__main__":
    main()
