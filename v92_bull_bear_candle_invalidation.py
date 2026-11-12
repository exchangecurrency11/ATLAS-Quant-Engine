#!/usr/bin/env python3
"""V9.2 research-only symmetric candle reversal / false-breakout invalidation.

Only *completed* OHLCV 1H and 4H candles. An Evening Star is a 3-candle
bearish reversal; a Morning Star is its bullish mirror. A star candle
itself is NOT an order block, and the model does not assign a profit
probability. 24/7 perpetual markets have no required overnight gaps.

This observational warning and retest-veto hypothesis is tested on the
SAME complete historical data as original V7 and V9.1. No V7 edits,
alerts, new orders or invented fills. No hyperparameter optimization.
"""
from bisect import bisect_right
from collections import Counter
import argparse
import json
import math
from pathlib import Path
from datetime import datetime,timezone

from backtest_retest_long_v4 import replay_pair
from market_structure import candles_from_history
from signal_quality_v7 import evaluate_bos_quality
from v7_paper_comparison import read_history

HOUR=3600
FOUR=4*HOUR
START=int(datetime(2024,10,1,tzinfo=timezone.utc).timestamp())
END=int(datetime(2026,10,1,tzinfo=timezone.utc).timestamp())
SYMBOLS={"BTCUSDT":"BTCUSDT_PERP.A","SOLUSDT":"SOLUSDT_PERP.A"}
BASE_COST_BPS_SIDE=9
STRESS_COST_BPS_SIDE=25
VARIANTS={
    "V7_ORIGINAL":(6,None),
    "V91_RETEST_MAX4H":(4,None),
    "V92_V7_OPPOSITE_STAR_WARNING_VETO":(6,False),
    "V92_V91_OPPOSITE_STAR_WARNING_VETO":(4,False),
    "V92_V7_STAR_PLUS_FAKE_BREAK_VETO":(6,True),
    "V92_V91_STAR_PLUS_FAKE_BREAK_VETO":(4,True),
}

def stamp(epoch):
    return datetime.fromtimestamp(epoch,timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def _valid(bars, seconds):
    if len(bars)<26: return False
    recent=bars[-35:]
    for i,b in enumerate(recent):
        if (int(b["t"])%seconds or
            (i and int(b["t"])-int(recent[i-1]["t"])!=seconds)):
            raise ValueError("V92_GAPPED_OR_UNALIGNED_CANDLE_SERIES")
        o,h,l,c,v=(float(b[k]) for k in ("o","h","l","c","v"))
        if (not all(math.isfinite(x) for x in (o,h,l,c,v)) or
            l<=0 or l>min(o,c) or h<max(o,c) or v<0):
            raise ValueError("V92_INVALID_OHLCV")
    return True

def candle_star(bars, end_index, seconds):
    """Completed third star candle at end_index; first at end_index-2.

    Crypto adaptation: no gap requirement. Geometry, trend and
    prior-20 high/low re-entry are strictly prior/closed data.
    """
    if end_index<23:return None
    ctx=bars[:end_index+1]
    if not _valid(ctx,seconds):return None
    a,b,c=ctx[-3:]
    body=lambda x:abs(float(x["c"])-float(x["o"]))
    first=body(a);middle=body(b);third=body(c)
    if first<=0 or third<=0:return None
    ar=float(a["h"])-float(a["l"])
    cr=float(c["h"])-float(c["l"])
    if ar<=0 or cr<=0:return None
    # Predeclared crypto-friendly star thresholds, not fitted to outcomes.
    if not (first/ar>=.5 and middle<=.45*first
            and third>=.65*first and third/cr>=.45):
        return None
    prior=ctx[-23:-3]
    if len(prior)!=20:return None
    upper=max(float(z["h"]) for z in prior)
    lower=min(float(z["l"]) for z in prior)
    midpoint=(float(a["o"])+float(a["c"]))/2
    # 3 closed candles + trend measured BEFORE first pattern candle.
    bearish=(a["c"]>a["o"] and c["c"]<c["o"] and
             c["c"]<midpoint and a["c"]>prior[-5]["c"])
    bullish=(a["c"]<a["o"] and c["c"]>c["o"] and
             c["c"]>midpoint and a["c"]<prior[-5]["c"])
    if not (bearish or bullish):return None
    side="bearish" if bearish else "bullish"
    if side=="bearish":
        sweep=max(float(x["h"]) for x in (a,b,c))>upper and float(c["c"])<upper
        invalidationLevel=upper
        name="EVENING_STAR"
    else:
        sweep=min(float(x["l"]) for x in (a,b,c))<lower and float(c["c"])>lower
        invalidationLevel=lower
        name="MORNING_STAR"
    return {"name":name,"direction":side,
            "closedAtUTC":stamp(int(c["t"])+seconds),
            "startAtUTC":stamp(int(a["t"])),
            "fakeBreakoutPrior20SweepAndReentry":bool(sweep),
            "levelBeforePattern":float(invalidationLevel),
            "cryptoNoGapRequired":True,
            "notAnEntrySignal":True}

def opposite_warning(h1, h4, at, active_side, *, require_fake_break=False):
    """Only pattern closes already known at retest 1H end can veto."""
    if active_side not in ("bullish","bearish"):
        raise ValueError("V92_INVALID_ACTIVE_SIDE")
    if not h1 or h1[-1]["t"]+HOUR!=at:
        raise ValueError("V92_1H_BAR_NOT_CLOSED_AT_RETEST")
    opponent="bearish" if active_side=="bullish" else "bullish"
    warnings=[]
    # Last four completed 1H star finishes, including retest bar.
    for i in range(max(23,len(h1)-4),len(h1)):
        match=candle_star(h1,i,HOUR)
        if match and match["direction"]==opponent and (not require_fake_break or match["fakeBreakoutPrior20SweepAndReentry"]):
            warnings.append({**match,"timeframe":"1H"})
    # Last two COMPLETED 4H candles; a 4H currently forming cannot count.
    four_closes=[z["t"]+FOUR for z in h4]
    last=bisect_right(four_closes,at)-1
    for i in range(max(23,last-1),last+1):
        if i>=len(h4):continue
        match=candle_star(h4,i,FOUR)
        if match and match["direction"]==opponent and (not require_fake_break or match["fakeBreakoutPrior20SweepAndReentry"]):
            warnings.append({**match,"timeframe":"4H"})
    if any(int(datetime.fromisoformat(x["closedAtUTC"].replace("Z","+00:00")).timestamp())>at for x in warnings):
        raise ValueError("V92_FUTURE_PATTERN_LEAK")
    return warnings

def gated_retest_factory(h4, veto_fake_break, tally):
    """V7's previous BOS quality and stop/TP engine remain unchanged."""
    def check(bars, active, retest):
        at=int(retest["t"])+HOUR
        warnings=opposite_warning(bars,h4,at,active["side"],
                                  require_fake_break=veto_fake_break)
        tally["eligibleOriginalRetestsChecked"]+=1
        if warnings:
            tally["oppositePatternVetoCount"]+=1
            for w in warnings:
                tally[w["name"]+"_"+w["timeframe"]]+=1
            tally["examples"].append({
                "atUTC":stamp(at),"activeSide":active["side"],
                "patterns":warnings})
            return {"passed":False,
                    "reasons":["V92_OPPOSITE_CLOSED_"+warnings[-1]["name"]+
                               ("_FAKE_BREAKOUT_REENTRY" if veto_fake_break else "_EARLY_WARNING")]}
        return {"passed":True,"reasons":[]}
    return check

def metrics(res, start, end):
    if res.get("status")!="PAPER_BACKTEST_NOT_LIVE":
        raise ValueError("V92_INVALID_SEQUENTIAL_REPLAY")
    trades=sorted([t for t in res["trades"]
                   if start<=t["entryOpenUTC"]<end and t["exitKnownUTC"]<=end],
                  key=lambda x:(x["exitKnownUTC"],x["entryOpenUTC"]))
    vals=[float(t["netRIllustrative"]) for t in trades]
    stress=[r-2*(STRESS_COST_BPS_SIDE-BASE_COST_BPS_SIDE)/10000*
             float(t["entry"])/float(t["risk"]) for t,r in zip(trades,vals)]
    for t in trades:
        if not (t["watchKnownUTC"]<t["retestKnownUTC"]<=t["entryOpenUTC"]<t["exitKnownUTC"]):
            raise ValueError("V92_LOOKAHEAD_TRADE_TIME")
    cum=peak=dd=0.
    for v in vals:
        cum+=v;peak=max(cum,peak);dd=max(dd,peak-cum)
    grosswins=sum(max(x,0) for x in vals)
    grossloss=-sum(min(x,0) for x in vals)
    return {
        "trades":len(trades),
        "wins":sum(x>0 for x in vals),
        "winRatePct":round(100*sum(x>0 for x in vals)/len(vals),2) if vals else None,
        "totalNetR9BpsPerSide":round(sum(vals),6),
        "totalNetR25BpsPerSideStress":round(sum(stress),6),
        "netRMean":round(sum(vals)/len(vals),6) if vals else None,
        "profitFactor":round(grosswins/grossloss,4) if grossloss else None,
        "maxDrawdownR":round(dd,6),
        "BOSWatches":res["alertsCount"],
        "retestVetoes":res["qualityGateRejectedRetest"],
        "retestExpires":res["retestExpiredCount"],
        "unresolvedExcluded":res["unresolvedPositionExcluded"],
        "tradeEntryExitEvidence":[{
             "entryUTC":stamp(t["entryOpenUTC"]),
             "exitUTC":stamp(t["exitKnownUTC"]),
             "watchUTC":stamp(t["watchKnownUTC"]),
             "retestUTC":stamp(t["retestKnownUTC"]),
             "side":t["side"],"netR9bps":round(t["netRIllustrative"],6)}
            for t in trades],
    }

def run(histories, base_reference, *, as_of=END):
    if (base_reference.get("status")!="V91_FULL_CHRONOLOGICAL_RETEST_ABLATION_PAPER_ONLY"
        or base_reference.get("originalV7BaselineVerifiedAgainstPublishedQualityBacktest") is not True):
        raise ValueError("V92_ORIGINAL_V7_V91_BASELINE_NOT_VERIFIED")
    if as_of!=END:
        raise ValueError("V92_MUST_USE_SAME_FROZEN_MATCHED_PERIOD_FIRST")
    out={"status":"V92_MORNING_EVENING_STAR_FAKE_BREAKOUT_RETEST_INVALIDATION_HISTORICAL_PAPER_ONLY",
         "startUTC":stamp(START),"endExclusiveUTC":stamp(END),
         "sameExactSourceHistoryForAllVariants":True,
         "timeframeInputs":["1H","4H","Daily"],
         "retestCandlePatternsMayBeObservedAfterActualCloseNotAtNextOpen":True,
         "patterns": ["EVENING_STAR","MORNING_STAR"],
         "gapRequirementRemovedFor24x7Perpetual":True,
         "preDeclaredNoOutcomeTuning":True,
         "fourHourUnclosedCandleNeverUsed":True,
         "fakeBreakoutPrior20HighLowSweepReentry":True,
         "symbols":{},"noBrokerOrders":True,"noNotifications":True,
         "notIndependentNewHistory":True,
         "noGuaranteedProfitImprovement":True}
    for symbol,ref in SYMBOLS.items():
        hour=histories["1hour"][ref]
        four=histories["4hour"][ref]
        daily=histories["daily"][ref]
        closedhour=candles_from_history(hour,"1hour",END)
        closedfour=candles_from_history(four,"4hour",END)
        cld=candles_from_history(daily,"daily",END)
        if len(closedhour)<17000 or len(closedfour)<4000 or len(cld)<600:
            raise ValueError("V92_2Y_VERIFIED_FULL_ARCHIVE_INCOMPLETE_"+symbol)
        # Observations across all candles, not only at profitable V7 trades.
        scan={"1H":Counter(),"4H":Counter()}
        for tf,bars,seconds in (("1H",closedhour,HOUR),("4H",closedfour,FOUR)):
            for i in range(23,len(bars)):
                pattern=candle_star(bars,i,seconds)
                if pattern:
                    scan[tf][pattern["name"]]+=1
                    if pattern["fakeBreakoutPrior20SweepAndReentry"]:
                        scan[tf][pattern["name"]+"_FAKE_BREAKOUT"]+=1
        readings={}
        for name,(retest_hours,strict) in VARIANTS.items():
            count=Counter()
            count["examples"]=[]
            filt=(gated_retest_factory(closedfour,strict,count)
                  if strict is not None else None)
            rep=replay_pair(hour,four,daily,as_of=END,
                            retest_hours=retest_hours,
                            bos_quality_filter=evaluate_bos_quality,
                            retest_quality_filter=filt)
            m=metrics(rep,START,END)
            if strict is not None:
                m["opposingCandlestickWarningAudit"]={
                    "checkedRetests":count["eligibleOriginalRetestsChecked"],
                    "vetoes":count["oppositePatternVetoCount"],
                    "morningStar1H":count["MORNING_STAR_1H"],
                    "eveningStar1H":count["EVENING_STAR_1H"],
                    "morningStar4H":count["MORNING_STAR_4H"],
                    "eveningStar4H":count["EVENING_STAR_4H"],
                    "examples":count["examples"][:30]}
            else:m["opposingCandlestickWarningAudit"]={"baselineUnchanged":True}
            readings[name]=m
        for name in ("V7_ORIGINAL","V91_RETEST_MAX4H"):
            expected=base_reference["results"][symbol][name]
            actual=readings[name]
            if (actual["trades"]!=expected["trades"] or
                actual["wins"]!=expected["wins"] or
                abs(actual["totalNetR9BpsPerSide"]-expected["totalNetR9bpsSide"])>.0001 or
                abs(actual["totalNetR25BpsPerSideStress"]-expected["totalNetR25bpsSide"])>.0001):
                raise ValueError("V92_BASELINE_REPLAY_DID_NOT_MATCH_ORIGINAL_"+symbol+"_"+name)
        for name,_,base in (
            ("V92_V7_OPPOSITE_STAR_WARNING_VETO",False,"V7_ORIGINAL"),
            ("V92_V91_OPPOSITE_STAR_WARNING_VETO",False,"V91_RETEST_MAX4H"),
            ("V92_V7_STAR_PLUS_FAKE_BREAK_VETO",True,"V7_ORIGINAL"),
            ("V92_V91_STAR_PLUS_FAKE_BREAK_VETO",True,"V91_RETEST_MAX4H")):
            readings[name]["deltaTotalRVsOwnBaseline"]=round(
                readings[name]["totalNetR9BpsPerSide"]-
                readings[base]["totalNetR9BpsPerSide"],6)
            readings[name]["baseline"]=base
        out["symbols"][symbol]={
            "verifiedCandleCount":{"1H":len(closedhour),
                                  "4H":len(closedfour),
                                  "Daily":len(cld)},
            "allHistoryPatternCounts":{tf:dict(c) for tf,c in scan.items()},
            "variants":readings}
    return out

def markdown(d):
    lines=["# V9.2 — Morning Star / Evening Star & fake breakout invalidasyon",
           "","**YALNIZCA ESKİ KAPANIŞLARLA YAPILAN PAPER BACKTEST.** V7 ve V9.1 değişmedi.",
           "Piyasa: BTC ve SOL USD-M perpetual. Dönem: "+d["startUTC"]+
           " – "+d["endExclusiveUTC"]+" (son tarih hariç).",
           "Tam kronolojik 1H/4H/Daily geçmişi; 4H kapanmadan sonraki bilgisi 1H kararında kullanılmaz.",
           "Yıldız formasyonları üç mumdan oluşur; 24/7 piyasa için gap aranmaz. ",
           "Geri dönük bakış: bu dönem daha önce incelendi, sonuçlar bağımsız doğrulama değildir.",
           "","| Coin | Sürüm | Paper işlem | Başarı % | Net R (9bp/yön) | 25bp/yön net R | Max DD R | Retest reddi |",
           "|---|---|---:|---:|---:|---:|---:|---:|"]
    for symbol,dct in d["symbols"].items():
        for name,z in dct["variants"].items():
            lines.append("| {} | {} | {} | {} | {:.4f} | {:.4f} | {:.4f} | {} |".format(
                symbol,name,z["trades"],z["winRatePct"],
                z["totalNetR9BpsPerSide"],z["totalNetR25BpsPerSideStress"],
                z["maxDrawdownR"],z["retestVetoes"]))
    lines+=["",
            "Yıldız tersine dönüş uyarıları, karşı trendin teyidi değildir. "
            "Tam BOS ve retest kurallarıyla karşılaştırılmadan tek başına işlem açılmaz.",
            "Ek filtrelerin trade fırsatlarını azaltması veya net R'yi düşürmesi mümkündür.",
            "Maliyetler varsayımsaldır; gerçek emir, fundlama, slipaj ve likidasyon tam modellenmedi.",
            "Hiçbir V9.2 bulgusu V7/V9.1 sistemini veya kullanıcı bildirimlerini otomatik değiştirmez.",""]
    return "\n".join(lines)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--archive",default="v92_verified_archive")
    p.add_argument("--reference",default="forward/v91_retest_full_replay/compare.json")
    p.add_argument("--out",default="forward/v92_candle_invalidation")
    a=p.parse_args()
    hist={tf:read_history(str(Path(a.archive)/("history_"+tf+".json")))
          for tf in ("1hour","4hour","daily")}
    ref=json.loads(Path(a.reference).read_text())
    d=run(hist,ref)
    dest=Path(a.out);dest.mkdir(exist_ok=True,parents=True)
    (dest/"historical.json").write_text(json.dumps(d,indent=2,ensure_ascii=False)+"\n")
    (dest/"historical.md").write_text(markdown(d))
    print("V92_BULL_BEAR_STAR_FAKE_BREAK_FULL_ARCHIVE_HISTORICAL_PAPER_COMPLETE",
          json.dumps({sym:{v:{"trades":q["trades"],"R":q["totalNetR9BpsPerSide"]}
                            for v,q in o["variants"].items()}
                      for sym,o in d["symbols"].items()}),
          flush=True)

if __name__=="__main__":main()
