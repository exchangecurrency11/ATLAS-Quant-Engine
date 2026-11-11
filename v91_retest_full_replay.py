#!/usr/bin/env python3
"""V9.1 full sequential V7 retest-ablation research, PAPER ONLY.

Uses the exact unmodified V7 BOS -> later retest -> next-hour-open simulator.
All outcomes are from the same previously inspected 2024-10 to 2026-09
historical archive; this is NOT prospective, independent, or a live edge.
The 4h expiry hypothesis arose from inspecting historical results.
The strong-retest criteria are research hypotheses, not optimized cutoffs.
Never changes V7/V9 signals, notifications, broker paths, or live filters.
"""
import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path

from backtest_retest_long_v4 import replay_pair
from market_structure import average_true_range
from signal_quality_v7 import evaluate_bos_quality, evaluate_retest_quality
from v7_paper_comparison import read_history

HOUR = 3600
START = int(datetime(2024,10,1,tzinfo=timezone.utc).timestamp())
AS_OF = int(datetime(2026,10,1,tzinfo=timezone.utc).timestamp())
SYMBOLS = {"BTCUSDT":"BTCUSDT_PERP.A", "SOLUSDT":"SOLUSDT_PERP.A"}
VARIANTS = {
    "V7_ORIGINAL": (6, False),
    "V91_RETEST_MAX4H": (4, False),
    "V91_STRONG_RETEST": (6, True),
    "V91_MAX4H_AND_STRONG": (4, True),
}
BASE_COST_BPS_SIDE = 9
STRESS_COST_BPS_SIDE = 25
STRONG_RETEST = {
    "minCloseBeyondBOS_ATR":0.20,
    "minDirectionalBody_ATR":0.20,
    "minDirectionalCloseLocation":0.60,
    "minRetestRelativeVolume20":1.00
}


def iso(t):
    return datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def strong_retest(bars, active, retest_bar):
    """Retest callback runs only AFTER later 1H bar closes; never uses entry bar."""
    no = lambda reason: {"passed":False, "reasons":[reason], "features":{}}
    if len(bars) < 21 or bars[-1]["t"] != retest_bar["t"]:
        return no("V91_RETEST_FUTURE_OR_INSUFFICIENT_BARS")
    if not all(bars[i+1]["t"]-bars[i]["t"]==HOUR for i in range(len(bars)-21,len(bars)-1)):
        return no("V91_RETEST_SOURCE_GAP")
    if int(active.get("knownUTC",-1)) > int(retest_bar["t"]):
        return no("V91_RETEST_NOT_AFTER_ORIGINAL_BOS")
    if active.get("side") not in ("bullish","bearish"):
        return no("V91_RETEST_INVALID_DIRECTION")
    atr=average_true_range(bars,len(bars)-1,count=14)
    if atr is None or atr<=0 or not math.isfinite(atr):
        return no("V91_RETEST_INVALID_ATR")
    b=bars[-1]
    try:
        o,h,l,c,v=(float(b[k]) for k in ("o","h","l","c","v"))
        level=float(active["level"])
        vols=[float(x["v"]) for x in bars[-21:-1]]
    except (TypeError,ValueError,KeyError):
        return no("V91_RETEST_MALFORMED")
    if (not all(map(math.isfinite,[o,h,l,c,v,level,*vols])) or
        l<=0 or h<max(o,c) or l>min(o,c) or v<0 or any(x<0 for x in vols)):
        return no("V91_RETEST_INVALID_OHLCV")
    mean_volume=sum(vols)/len(vols)
    if mean_volume<=0:return no("V91_RETEST_NO_REFERENCE_VOLUME")
    sign=1 if active["side"]=="bullish" else -1
    close_dist=sign*(c-level)/atr
    body=sign*(c-o)/atr
    loc=((c-l)/(h-l) if sign==1 else (h-c)/(h-l)) if h>l else 0.
    rvol=v/mean_volume
    reasons=[]
    # V7's own established rejection-strength function remains unchanged.
    v7=evaluate_retest_quality(bars,active,retest_bar)
    if not v7["passed"]:reasons+=v7["reasons"]
    if close_dist<STRONG_RETEST["minCloseBeyondBOS_ATR"]:
        reasons.append("V91_CLOSE_NOT_0_20_ATR_BEYOND_BOS")
    if body<STRONG_RETEST["minDirectionalBody_ATR"]:
        reasons.append("V91_DIRECTIONAL_BODY_WEAK")
    if loc<STRONG_RETEST["minDirectionalCloseLocation"]:
        reasons.append("V91_CLOSE_LOCATION_WEAK")
    if rvol<STRONG_RETEST["minRetestRelativeVolume20"]:
        reasons.append("V91_RETEST_VOLUME_BELOW_PRIOR20")
    return {"passed":not reasons,"reasons":reasons,"features":{
        "closeBeyondBOS_ATR":round(close_dist,5),
        "directionalBody_ATR":round(body,5),
        "directionalCloseLocation":round(loc,5),
        "retestRelativeVolume20":round(rvol,5),
        "retestClosedAtUTC":b["t"]+HOUR,
        "noFutureEntryCandleUsed":True}}


def metrics(report):
    if report.get("status")!="PAPER_BACKTEST_NOT_LIVE":
        raise ValueError("V91_NOT_VERIFIED_PAPER_REPLAY")
    trades=[t for t in report["trades"] if START<=t["entryOpenUTC"]<AS_OF and t["exitKnownUTC"]<=AS_OF]
    trades.sort(key=lambda t:(t["exitKnownUTC"],t["entryOpenUTC"]))
    vals=[float(t["netRIllustrative"]) for t in trades]
    stress=[r - 2*(STRESS_COST_BPS_SIDE-BASE_COST_BPS_SIDE)/10000*
            float(t["entry"])/float(t["risk"]) for t,r in zip(trades,vals)]
    total=0.;peak=0.;dd=0.
    for n in vals:
        total+=n; peak=max(peak,total); dd=max(dd,peak-total)
    gain=sum(max(0,n) for n in vals)
    loss=-sum(min(0,n) for n in vals)
    result={
        "trades":len(vals),"wins":sum(x>0 for x in vals),
        "winRatePct":round(100*sum(x>0 for x in vals)/len(vals),2) if vals else None,
        "totalNetR9bpsSide":round(sum(vals),4),
        "averageNetR9bpsSide":round(sum(vals)/len(vals),4) if vals else None,
        "totalNetR25bpsSide":round(sum(stress),4),
        "profitFactorR":round(gain/loss,3) if loss else None,
        "maxDrawdownR":round(dd,4),
        "BOSWatches":report["alertsCount"],
        "BOSRejected":report["qualityGateRejectedBOS"],
        "retestsRejected":report["qualityGateRejectedRetest"],
        "retestsExpired":report["retestExpiredCount"],
        "riskRejected":report["riskRuleRejected"],
        "unresolvedPositionExcluded":report["unresolvedPositionExcluded"],
        "originalV7StopTPAndNextOpenEngineUntouched":True}
    return result,trades


def analyze(histories,baseline_reference):
    result={"status":"V91_FULL_CHRONOLOGICAL_RETEST_ABLATION_PAPER_ONLY",
        "historyStartUTC":iso(START),"historyEndExclusiveUTC":iso(AS_OF),
        "source":"original V7 Binance SHA-verified frozen archive",
        "historicalPeriodPreviouslyInspected":True,
        "max4hRuleSuggestedAfterSeeingPastOutcomes":True,
        "NOTIndependentOutOfSampleOrProspective":True,
        "strongRetestCriteriaNotOutcomeOptimized":STRONG_RETEST,
        "baseCostBpsPerSide":BASE_COST_BPS_SIDE,
        "stressCostBpsPerSide":STRESS_COST_BPS_SIDE,
        "fundingTrueFillsGapsLiquidationNOTSimulated":True,
        "noBrokerOrders":True,"noUserNotifications":True,
        "originalV7AndV9Unmodified":True,"promotionToLiveSignalsBlocked":True,
        "results":{},"tradesAudit":[]}
    for symbol,ref in SYMBOLS.items():
        res={}
        h=histories["1hour"][ref]
        four=histories["4hour"][ref]
        day=histories["daily"][ref]
        for name,(hours,strong) in VARIANTS.items():
            out=replay_pair(h,four,day,as_of=AS_OF,
                retest_hours=hours,bos_quality_filter=evaluate_bos_quality,
                retest_quality_filter=strong_retest if strong else None)
            summary,trades=metrics(out)
            res[name]=summary
            for t in trades:
                if not (t["watchKnownUTC"] < t["retestKnownUTC"] <=
                        t["entryOpenUTC"] < t["exitKnownUTC"]):
                    raise AssertionError("V91_TRADE_FUTURE_TIMELINE_OR_ORDER_VIOLATION")
                delay=(t["retestKnownUTC"]-t["watchKnownUTC"])//HOUR
                if delay>hours:
                    raise AssertionError("V91_LATE_RETEST_ACCEPTED")
                result["tradesAudit"].append({
                    "symbol":symbol,"variant":name,
                    "watchUTC":iso(t["watchKnownUTC"]),
                    "retestUTC":iso(t["retestKnownUTC"]),
                    "entryUTC":iso(t["entryOpenUTC"]),
                    "exitUTC":iso(t["exitKnownUTC"]),
                    "retestDelayHours":delay,
                    "side":t["side"],"entry":round(t["entry"],6),
                    "stop":round(t["stop"],6),
                    "TP":[round(x,6) for x in t["targets"]],
                    "exitReason":t["exitReason"],
                    "netR9bps":round(t["netRIllustrative"],6),
                    "netR25bps":round(t["netRIllustrative"]-
                        2*(STRESS_COST_BPS_SIDE-BASE_COST_BPS_SIDE)/10000*
                        t["entry"]/t["risk"],6)})
        baseline=res["V7_ORIGINAL"]
        expected=baseline_reference["candidateHistorical"][symbol]["V7_ORIGINAL"]
        if (baseline["trades"]!=expected["V7paperClosedTrades"] or
            baseline["wins"]!=expected["winningTrades9BpsPerSide"] or
            abs(baseline["totalNetR9bpsSide"]-expected["totalNetR9BpsPerSide"])>0.00011 or
            abs(baseline["totalNetR25bpsSide"]-expected["totalNetR25BpsPerSideStress"])>0.00011):
            raise AssertionError("V91_BASELINE_DOES_NOT_MATCH_PUBLISHED_V7_"+symbol)
        for name in VARIANTS:
            e=res[name]
            e["deltaTotalNetRvsV7"]=round(e["totalNetR9bpsSide"]-baseline["totalNetR9bpsSide"],4)
            e["deltaWinRatePctPointsVsV7"]=(
                round(e["winRatePct"]-baseline["winRatePct"],2)
                if e["winRatePct"] is not None else None)
        result["results"][symbol]=res
    result["allVariantsReplayedIndependentlyChronologically"]=True
    result["originalV7BaselineVerifiedAgainstPublishedQualityBacktest"]=True
    return result


def markdown(d):
    lines=[
      "# V9.1 retest expiry + strong retest: full sequential historical replay",
      "",
      "**PAPER ONLY.** Historical bars were previously inspected. The 4h rule was proposed after examining past results. It is NOT an independent out-of-sample validation.",
      "",
      "Original V7 BOS entry engine, 1H subsequent open, stops and three partial profit targets all retained. 9bps per side baseline; 25bps stress per side. Funding, fills and liquidation are excluded.",
      "",
      "The strong-retet gate tests close >=0.20 ATR beyond BOS, directional body >=0.20 ATR, close location >=60% in the trade direction, retest volume >=1.0x preceding 20 closed hourly bars. V7 baseline has no extra retest gate in the published V9 full-profit replay.",
      "",
      "| Asset | Variant | Trades | Win % | Total net R | Stress total R | PF | Max DD R | Watch | Retest rejected | Expired |",
      "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for symbol,variants in d["results"].items():
        for name,v in variants.items():
            lines.append("| {} | {} | {} | {} | {} | {} | {} | {} | {} | {} | {} |".format(
                symbol,name,v["trades"],v["winRatePct"],
                v["totalNetR9bpsSide"],v["totalNetR25bpsSide"],
                v["profitFactorR"],v["maxDrawdownR"],v["BOSWatches"],
                v["retestsRejected"],v["retestsExpired"]))
    lines+=["","**Do not select new thresholds based on this previously seen period.** Prospectively log fresh V7 opportunities with identical source and as-of checks before considering any activation.",""]
    return "\n".join(lines)


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--archive",default="v7_archived")
    ap.add_argument("--reference",default="forward/v9_v7_quality_upgraded_backtest/compare.json")
    ap.add_argument("--out",default="forward/v91_retest_full_replay")
    args=ap.parse_args()
    history={kind:read_history(str(Path(args.archive)/("history_"+kind+".json")))
             for kind in ("1hour","4hour","daily")}
    base=json.loads(Path(args.reference).read_text(encoding="utf-8"))
    if base.get("status")!="V9_V7_PLUS_BOS_RETEST_FULL_CHRONOLOGICAL_PROFIT_BACKTEST_HISTORICAL":
        raise ValueError("V91_ORIGINAL_REFERENCE_UNVERIFIED")
    d=analyze(history,base)
    path=Path(args.out);path.mkdir(parents=True,exist_ok=True)
    (path/"compare.json").write_text(json.dumps(d,indent=2,ensure_ascii=False)+"\n")
    (path/"compare.md").write_text(markdown(d),encoding="utf-8")
    print("V91_FULL_SEQUENTIAL_V7_RETEST_STRENGTH_PAPER_ONLY",
          json.dumps(d["results"]),flush=True)

if __name__=="__main__":
    main()
