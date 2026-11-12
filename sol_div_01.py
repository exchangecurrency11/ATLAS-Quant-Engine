#!/usr/bin/env python3
"""SOL-DIV-01: causal price/CVD divergence on top of V9.2 strict-sweep.

Pivots are confirmed only after two right-hand closed candles. At a retest,
both compared pivots and their confirmation bars must already be closed.
No orders, alerts, production writes or parameter fitting.
"""
import argparse, json, math
from pathlib import Path
from collections import Counter
from bisect import bisect_right

from market_structure import candles_from_history
from signal_quality_v7 import evaluate_bos_quality
from v7_paper_comparison import read_history
from backtest_retest_long_v4 import replay_pair
from v92_bull_bear_candle_invalidation import START, END, HOUR, FOUR, stamp
from v92_selected_reversal_patterns import make_selective_gate
from sol_flow_01 import score, validate_source

SYMBOL = "SOLUSDT_PERP.A"
BASE = "V92_STRICT_SWEEP_CONTROL"
ARMS = (
    BASE,
    "V92_PLUS_1H_CONFIRMED_CVD_DIVERGENCE",
    "V92_PLUS_4H_CONFIRMED_CVD_DIVERGENCE",
    "V92_PLUS_1H_OR_4H_CVD_DIVERGENCE",
)
PIVOT_LEFT = 2
PIVOT_RIGHT = 2
MAX_PIVOT_AGE = 48  # bars on the relevant timeframe


class DivergenceIndex:
    def __init__(self, rows, seconds):
        validate_source(rows)
        self.rows = rows
        self.seconds = seconds
        self.times = [int(x["t"]) for x in rows]
        self.cvd = []
        total = 0.0
        for x in rows:
            total += 2.0*float(x["tbv"])-float(x["v"])
            self.cvd.append(total)
        self.pivots = self._find_pivots()

    def _find_pivots(self):
        out = []
        n = len(self.rows)
        for i in range(PIVOT_LEFT, n-PIVOT_RIGHT):
            # A pivot at i becomes knowable only at i+2 close.
            left = self.rows[i-PIVOT_LEFT:i]
            right = self.rows[i+1:i+PIVOT_RIGHT+1]
            bar = self.rows[i]
            low = float(bar["l"])
            high = float(bar["h"])
            is_low = all(low < float(x["l"]) for x in left+right)
            is_high = all(high > float(x["h"]) for x in left+right)
            if is_low:
                out.append({"kind":"low","i":i,"price":low,
                            "cvd":self.cvd[i],
                            "knownAt":int(self.rows[i+PIVOT_RIGHT]["t"])+self.seconds})
            if is_high:
                out.append({"kind":"high","i":i,"price":high,
                            "cvd":self.cvd[i],
                            "knownAt":int(self.rows[i+PIVOT_RIGHT]["t"])+self.seconds})
        return out

    def at(self, closed_at):
        if type(closed_at) is not int or closed_at % self.seconds:
            raise ValueError("DIV_NOT_ALIGNED_CLOSED_TIME")
        end = bisect_right(self.times, closed_at-self.seconds)
        if end == 0 or self.times[end-1]+self.seconds != closed_at:
            raise ValueError("DIV_STALE_OR_MISSING_LAST_BAR")
        latest_i = end-1
        result = {"knownAtUTC":stamp(closed_at),"bullish":False,
                  "bearish":False,"bullishEvidence":None,
                  "bearishEvidence":None,"pivotRightBars":PIVOT_RIGHT}
        for kind in ("low","high"):
            eligible = [p for p in self.pivots
                        if p["kind"]==kind and p["knownAt"]<=closed_at
                        and p["i"]<=latest_i
                        and latest_i-p["i"]<=MAX_PIVOT_AGE]
            if len(eligible)<2:
                continue
            a,b=eligible[-2:]
            if b["i"]<=a["i"]:
                raise ValueError("DIV_PIVOT_ORDER")
            if kind=="low":
                # Lower price low, higher cumulative delta low.
                ok=b["price"]<a["price"] and b["cvd"]>a["cvd"]
                result["bullish"]=bool(ok)
                if ok:
                    result["bullishEvidence"]={
                        "priorPivotUTC":stamp(self.rows[a["i"]]["t"]),
                        "latestPivotUTC":stamp(self.rows[b["i"]]["t"]),
                        "priorPivotKnownUTC":stamp(a["knownAt"]),
                        "latestPivotKnownUTC":stamp(b["knownAt"]),
                        "priorPrice":a["price"],"latestPrice":b["price"],
                        "priorCVD":a["cvd"],"latestCVD":b["cvd"]}
            else:
                # Higher price high, lower cumulative delta high.
                ok=b["price"]>a["price"] and b["cvd"]<a["cvd"]
                result["bearish"]=bool(ok)
                if ok:
                    result["bearishEvidence"]={
                        "priorPivotUTC":stamp(self.rows[a["i"]]["t"]),
                        "latestPivotUTC":stamp(self.rows[b["i"]]["t"]),
                        "priorPivotKnownUTC":stamp(a["knownAt"]),
                        "latestPivotKnownUTC":stamp(b["knownAt"]),
                        "priorPrice":a["price"],"latestPrice":b["price"],
                        "priorCVD":a["cvd"],"latestCVD":b["cvd"]}
        return result


def run_gate(index1h,index4h,arm,counts):
    def gate(bars,active,retest):
        at=int(retest["t"])+HOUR
        f1=index1h.at(at)
        f4=index4h.at((at//FOUR)*FOUR) if at%FOUR==0 else None
        # If the 1H retest close does not coincide with a 4H close,
        # the latest fully closed 4H bar ended at floor(at/4h)*4h.
        if f4 is None:
            four_close=(at//FOUR)*FOUR
            if four_close<=0:
                f4=None
            else:
                f4=index4h.at(four_close)
        bullish = f1["bullish"] or bool(f4 and f4["bullish"])
        bearish = f1["bearish"] or bool(f4 and f4["bearish"])
        if arm==ARMS[1]:
            aligned=f1["bullish"] if active["side"]=="bullish" else f1["bearish"]
        elif arm==ARMS[2]:
            aligned=bool(f4 and (f4["bullish"] if active["side"]=="bullish" else f4["bearish"]))
        else:
            aligned=bullish if active["side"]=="bullish" else bearish
        counts["eligible"]+=1
        if not aligned:
            counts["vetoes"]+=1
            counts["noAlignedDivergence"]+=1
        else:
            counts["aligned"]+=1
            counts["examples"].append({
                "knownAtUTC":stamp(at),"side":active["side"],
                "1H":f1,"4H":f4})
        return {"passed":bool(aligned),
                "reasons":[] if aligned else ["NO_CONFIRMED_PRICE_CVD_DIVERGENCE"]}
    return gate


def run(histories, v92_reference, manifest):
    if (v92_reference.get("status") !=
        "SELECTIVE_SOL_STAR_HARAMI_AND_OTHER_HIGH_PROFILE_CANDLE_WATCHES_HISTORICAL_ONLY"
        or v92_reference.get("sameVerifiedBinanceBTCAndSOLSource") is not True
        or v92_reference.get("fromUTC") != stamp(START)
        or v92_reference.get("toUTCExclusive") != stamp(END)
        or v92_reference.get("noV7V91ProductionChanges") is not True):
        raise ValueError("DIV_INVALID_V92_REFERENCE")
    proof=manifest.get("inputFiles",[])
    if not (manifest.get("source","").startswith("Binance official data.binance.vision")
            and manifest.get("checksumsVerified")==len(proof)==48
            and manifest.get("pairCounts",{}).get("SOLUSDT",{}).get("1hour")==17520):
        raise ValueError("DIV_INVALID_ARCHIVE_MANIFEST")
    hour=histories["1hour"][SYMBOL]
    four=histories["4hour"][SYMBOL]
    daily=histories["daily"][SYMBOL]
    if not hour or hour[0]["t"]!=START or hour[-1]["t"]+HOUR!=END:
        raise ValueError("DIV_WRONG_SOURCE_PERIOD")
    index1h=DivergenceIndex(hour,HOUR)
    index4h=DivergenceIndex(four,FOUR)
    four_closed=candles_from_history(four,"4hour",END)
    out={
      "status":"SOL_DIV_01_CAUSAL_PRICE_CVD_DIVERGENCE_HISTORICAL_PAPER_ONLY",
      "symbol":"SOLUSDT","startUTC":stamp(START),"endExclusiveUTC":stamp(END),
      "source":"Binance official USD-M monthly 1H klines with taker-buy base volume",
      "sameHistoryAllArms":True,"v92StrictSweepAppliedBeforeDivergence":True,
      "v92StrictSweepControlParityVerified":False,
      "pivotRule":{"leftClosedBars":PIVOT_LEFT,"rightClosedBars":PIVOT_RIGHT,
                   "maxPivotAgeBars":MAX_PIVOT_AGE,
                   "bullish":"lower price low + higher cumulative taker CVD low",
                   "bearish":"higher price high + lower cumulative taker CVD high"},
      "onlyClosedCandles":True,"pivotConfirmationWaited":True,
      "noFutureFeatures":True,"noOpenInterestUsed":True,
      "brokerOrders":False,"alerts":False,"productionModified":False,
      "promotionApproved":False,"historicalPeriodPreviouslyInspected":True,
      "notIndependentProspectiveEvidence":True,"results":{}}
    for arm in ARMS:
        audit=Counter();audit["examples"]=[]
        v92audit=Counter();v92audit["examples"]=[]
        v92gate=make_selective_gate("SOLUSDT",four_closed,
                                    "SELECTED_SOL_STRICT_SWEEP",v92audit)
        if arm==BASE:
            gate=v92gate
        else:
            divgate=run_gate(index1h,index4h,arm,audit)
            def gate(bars,active,retest,vg=v92gate,dg=divgate):
                v=vg(bars,active,retest)
                if not v["passed"]:
                    return v
                return dg(bars,active,retest)
        replay=replay_pair(hour,four,daily,as_of=END,retest_hours=4,
                           bos_quality_filter=evaluate_bos_quality,
                           retest_quality_filter=gate)
        summary=score(replay)
        out["results"][arm]={"summary":summary,
            "divergenceAudit":{"eligibleRetests":audit["eligible"],
              "alignedRetests":audit["aligned"],"vetoes":audit["vetoes"],
              "noAlignedDivergence":audit["noAlignedDivergence"],
              "examples":audit["examples"][:30]},
            "v92SelectedPatternAudit":{
              "retests":v92audit["retests"],
              "opposingPatternsObserved":v92audit["opposingSelectedPatternsObserved"],
              "vetoes":v92audit["vetoes"]}}
    base=out["results"][BASE]["summary"]
    expected=v92_reference["symbols"]["SOLUSDT"]["variants"]["V91_RETEST_MAX4H__SELECTED_SOL_STRICT_SWEEP"]
    if (base["trades"]!=expected["trades"] or base["winsNet"]!=expected["wins"]
        or abs(base["netR9BpsPerSide"]-expected["totalNetR9BpsPerSide"])>.00011
        or abs(base["netR25BpsPerSide"]-expected["totalNetR25BpsSideStress"])>.00011):
        raise ValueError("DIV_V92_CONTROL_PARITY_FAILED")
    out["v92StrictSweepControlParityVerified"]=True
    for arm,item in out["results"].items():
        item["summary"]["deltaNetR9VsV92"]=round(
            item["summary"]["netR9BpsPerSide"]-base["netR9BpsPerSide"],6)
    return out


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--hour",required=True);p.add_argument("--four",required=True)
    p.add_argument("--daily",required=True);p.add_argument("--manifest",required=True)
    p.add_argument("--v92-reference",required=True)
    p.add_argument("--output",default="forward/sol_div_01/latest.json")
    a=p.parse_args()
    hist={tf:read_history(path) for tf,path in (
      ("1hour",a.hour),("4hour",a.four),("daily",a.daily))}
    result=run(hist,json.loads(Path(a.v92_reference).read_text()),
               json.loads(Path(a.manifest).read_text()))
    dest=Path(a.output);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n")
    for name,item in result["results"].items():
        s=item["summary"]
        print(name,s["trades"],s["winsNet"],s["winRatePct"],
              s["netR9BpsPerSide"],s["netR25BpsPerSide"],flush=True)


if __name__=="__main__":
    main()
