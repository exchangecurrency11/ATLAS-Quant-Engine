#!/usr/bin/env python3
"""V9: FIVE MINUTES BEFORE next 4H starts, predict ITS OWN green/red body.

PREDECLARED outcome for future 4H Binance USD-M candle [T,T+4h):
   GREEN iff close(T+4h)>open(T); RED iff close<open; doji is excluded
   and separately counted. This is NOT close-versus-prior-close.

Prediction timestamp is T-300 seconds (5 minutes BEFORE next 4H starts).
At T-300, prior 4H candle [T-4h,T) is NOT CLOSED:
  - Last completed 4H is [T-8h,T-4h).
  - Last completed 1H is [T-2h,T-1h).
  - Three 1H bars of the currently forming 4H candle are usable,
    the fourth [T-1h,T) is NOT usable.
  - Daily indicators use ONLY days ending <=T-300.
  - Future T opening price is UNKNOWN at decision time.
All indicators at the point-in-time snapshot are causally computed.

Train six fixed expanding-window folds on verified Binance Futures 1H
SHA256 archives, three assets synchronized: BTC, ETH, SOL. No shuffled
cross-validation, no overfit threshold selection. Per-asset LogisticRegression
(StandardScaler, C=0.2). All test predictions made on unseen-at-training
future dates. Fold dates and confidence thresholds declared before results.
Caution: 2023-2026 historical data was already inspected in earlier
experiments; this is NOT prospective holdout. No live orders, alerts,
signal engine activation or production changes.
"""
import argparse
from bisect import bisect_right
from collections import Counter
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime,timezone
import json,math
from pathlib import Path

from download_binance_um_history import (
    download_month,months_inclusive,month_start,month_end,aggregate)

HOUR=3600
FOUR=4*HOUR
DAY=24*HOUR
LEAD_SECONDS=300
SYMBOLS=("BTCUSDT","ETHUSDT","SOLUSDT")
START_MONTH="2023-01"
END_MONTH="2026-09"
FOLDS=(
  ("2024-H1","2024-01-01T00:00:00Z","2024-07-01T00:00:00Z"),
  ("2024-H2","2024-07-01T00:00:00Z","2025-01-01T00:00:00Z"),
  ("2025-H1","2025-01-01T00:00:00Z","2025-07-01T00:00:00Z"),
  ("2025-H2","2025-07-01T00:00:00Z","2026-01-01T00:00:00Z"),
  ("2026-H1","2026-01-01T00:00:00Z","2026-07-01T00:00:00Z"),
  ("2026-Q3","2026-07-01T00:00:00Z","2026-10-01T00:00:00Z"),
)
CONFIDENCE_BANDS=(0.55,0.60,0.65)
MIN_TRAIN_SAMPLES=600
MAX_WORKERS=8


def ts(s):
    return int(datetime.fromisoformat(s.replace("Z","+00:00")).timestamp())


def iso(t):
    return datetime.fromtimestamp(t,timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def download_three():
    months=months_inclusive(START_MONTH,END_MONTH)
    expected_len=(month_end(END_MONTH)-month_start(START_MONTH))//HOUR
    work={}
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures={pool.submit(download_month,s,m):(s,m)
                 for s in SYMBOLS for m in months}
        for f in as_completed(futures):
            s,m=futures[f]
            rs,rm,one,proof=f.result()
            if (rs,rm)!=(s,m) or len(proof.get("sha256",""))!=64:
                raise ValueError("UNVERIFIED_ARCHIVE")
            if len(one)!=(month_end(m)-month_start(m))//HOUR:
                raise ValueError("INCOMPLETE_MONTH_"+s+"_"+m)
            work[(s,m)]=(one,proof["sha256"])
            print("V9_NEXT4H_SHA256",s,m,len(one),flush=True)
    result={}
    source={}
    for s in SYMBOLS:
        one=[row for m in months for row in work[(s,m)][0]]
        if len(one)!=expected_len or any(
            x["t"]!=month_start(START_MONTH)+i*HOUR for i,x in enumerate(one)):
            raise ValueError("MISSING_OR_DUPLICATE_1H_"+s)
        for row in one:
            if not all(key in row for key in ("tbv","tbq","qv","trades")):
                raise ValueError("MISSING_REQUIRED_FLOW_"+s)
        four=aggregate(one,FOUR)
        daily=aggregate(one,DAY)
        result[s]={"one":one,"four":four,"daily":daily}
        source[s]={"1H":len(one),"4H":len(four),"Daily":len(daily),
                   "verifiedMonthlyZIPs":len(months),
                   "archiveSHA256ByMonth":{m:work[(s,m)][1] for m in months}}
    return result,source


def sma(values,length):
    result=[None]*len(values);total=0.
    for i,x in enumerate(values):
        total+=x
        if i>=length:total-=values[i-length]
        if i>=length-1:result[i]=total/length
    return result


def rsi14(values):
    out=[None]*len(values)
    if len(values)<15:return out
    gain=sum(max(values[i]-values[i-1],0) for i in range(1,15))/14
    loss=sum(max(values[i-1]-values[i],0) for i in range(1,15))/14
    def ratio(g,l):
        if g==0 and l==0:return 50.0
        return 100.0 if l==0 else 100-100/(1+g/l)
    out[14]=ratio(gain,loss)
    for i in range(15,len(values)):
        delta=values[i]-values[i-1]
        gain=(13*gain+max(delta,0))/14
        loss=(13*loss+max(-delta,0))/14
        out[i]=ratio(gain,loss)
    return out


def prepare(raw):
    prepared={}
    for symbol,bars in raw.items():
        four=bars["four"]
        daily=bars["daily"]
        fc=[b["c"] for b in four]
        dc=[b["c"] for b in daily]
        # SMA only on CLOSED candle indices; caller chooses lagged index.
        prepared[symbol]={
          **bars,
          "fc":fc,"dc":dc,
          "f_sma100":sma(fc,100),"f_sma200":sma(fc,200),
          "d_sma100":sma(dc,100),"d_sma200":sma(dc,200),
          "f_rsi14":rsi14(fc),"d_rsi14":rsi14(dc),
          "daily_ends":[b["t"]+DAY for b in daily]}
    return prepared


def safe_log(ratio):
    return math.log(max(1e-12,ratio))


def features_at(symbol,prepared,target_index):
    """Features for T-300 seconds, absolutely no future or last 1H input.

    All symbols are aligned; i is index of the candle that does not yet
    exist at prediction time. Using only four[i-2] and one[4*i-2].
    """
    data=prepared[symbol]
    future_bar=data["four"][target_index]
    t=future_bar["t"]
    if t%FOUR or t<month_start(START_MONTH)+215*DAY:
        return None
    last_complete_4h=target_index-2  # i-1 four-hour candle still open at T-5m
    if last_complete_4h<205:
        return None
    start_1h=(t-data["one"][0]["t"])//HOUR
    last_hour=start_1h-2  # (T-2h,T-1h) last fully CLOSED hour
    if last_hour<50:
        return None
    # End time is 1 hour before T, safely earlier than decision at T-5m.
    if data["one"][last_hour]["t"]+HOUR!=t-HOUR:
        raise ValueError("ONE_HOUR_TIME_ALIGNMENT_BROKEN")
    day_i=bisect_right(data["daily_ends"],t-LEAD_SECONDS)-1
    if day_i<200:
        return None
    four=data["four"]
    daily=data["daily"]
    one=data["one"]
    q=four[last_complete_4h]
    last_days=daily[day_i]
    if last_days["t"]+DAY>t-LEAD_SECONDS:
        raise ValueError("DAILY_FUTURE_LEAK")
    prices=data["fc"]
    dclose=data["dc"]
    d100=data["d_sma100"][day_i]
    d200=data["d_sma200"][day_i]
    f100=data["f_sma100"][last_complete_4h]
    f200=data["f_sma200"][last_complete_4h]
    drsi=data["d_rsi14"][day_i]
    frsi=data["f_rsi14"][last_complete_4h]
    if any(z is None for z in (d100,d200,f100,f200,drsi,frsi)):
        return None
    # All 4H bars below end at T-4h or earlier.
    hist4=four[last_complete_4h-30:last_complete_4h+1]
    if len(hist4)!=31 or hist4[-1]["t"]+FOUR>t-LEAD_SECONDS:
        raise ValueError("UNFINISHED_4H_LEAK")
    recent=hist4[-14:]
    true_ranges=[]
    for j,b in enumerate(recent):
        prev=hist4[-15+j]["c"]
        true_ranges.append(max(b["h"]-b["l"],
                               abs(b["h"]-prev),abs(b["l"]-prev)))
    atr14=sum(true_ranges)/14
    low20=min(z["l"] for z in hist4[-20:])
    high20=max(z["h"] for z in hist4[-20:])
    avgvol20=sum(z["v"] for z in hist4[-21:-1])/20
    avgtrades20=sum(z["trades"] for z in hist4[-21:-1])/20
    prev_daily=[b for b in daily[day_i-1:day_i+1]]
    prev_day=prev_daily[-1]
    pivot=(prev_day["h"]+prev_day["l"]+prev_day["c"])/3
    r=max(q["h"]-q["l"],1e-9)
    recent_prev=four[last_complete_4h-1]
    bias_short_sweep=(q["h"]>max(x["h"] for x in hist4[-21:-1])
                      and q["c"]<max(x["h"] for x in hist4[-21:-1]))
    bias_long_sweep=(q["l"]<min(x["l"] for x in hist4[-21:-1])
                     and q["c"]>min(x["l"] for x in hist4[-21:-1]))
    # The 3 ALREADY CLOSED 1H bars within currently INCOMPLETE [T-4,T)
    partial=one[start_1h-4:start_1h-1]
    if len(partial)!=3 or any(
        b["t"]!=t-FOUR+j*HOUR for j,b in enumerate(partial)):
        raise ValueError("PARTIAL_4H_CONTAINS_FUTURE_HOURLY_CANDLE")
    if any(b["t"]+HOUR>t-LEAD_SECONDS for b in partial):
        raise ValueError("FUTURE_HOURLY_CANDLE")
    prev_3=one[start_1h-7:start_1h-4]
    partial_vol=sum(x["v"] for x in partial)
    prev3vol=sum(x["v"] for x in prev_3)
    partial_delta=sum(2*x["tbv"]-x["v"] for x in partial)
    partial_count=sum(x["trades"] for x in partial)
    prior3count=sum(x["trades"] for x in prev_3)
    # All denominators use price or volume ALREADY KNOWN at T-5m.
    v=[
       safe_log(q["c"]/q["o"]),                          # lagged 4H body
       safe_log(q["c"]/recent_prev["c"]),                # lagged 4H close change
       safe_log(q["c"]/four[last_complete_4h-3]["c"]),   # 12h move
       safe_log(q["c"]/four[last_complete_4h-6]["c"]),   # 24h move
       safe_log(q["c"]/four[last_complete_4h-12]["c"]),  # 48h move
       safe_log(q["v"]/avgvol20) if avgvol20>0 and q["v"]>0 else 0.,
       atr14/max(q["c"],1e-9),
       (q["c"]-q["l"])/r,
       (q["h"]-max(q["o"],q["c"]))/r,
       (min(q["o"],q["c"])-q["l"])/r,
       frsi/100.,
       safe_log(q["c"]/f100),
       safe_log(q["c"]/f200),
       drsi/100.,
       safe_log(last_days["c"]/d100),
       safe_log(last_days["c"]/d200),
       (q["c"]-low20)/max(1e-9,high20-low20),
       (q["c"]-pivot)/max(atr14,1e-9),
       (2*q["tbv"]/q["v"]-1) if q["v"]>0 else 0.,
       (2*sum(x["tbv"] for x in hist4[-6:]) /
            sum(x["v"] for x in hist4[-6:])-1)
            if sum(x["v"] for x in hist4[-6:])>0 else 0.,
       safe_log(q["trades"]/avgtrades20)
         if avgtrades20>0 and q["trades"]>0 else 0.,
       float(bias_short_sweep),
       float(bias_long_sweep),
       safe_log(partial[-1]["c"]/q["c"]),             # partial 3h progress
       safe_log(partial[-1]["c"]/partial[0]["o"]),    # completed partial 3h body
       partial_delta/max(1e-9,partial_vol),
       safe_log(partial_vol/prev3vol) if prev3vol>0 and partial_vol>0 else 0.,
       safe_log(partial_count/prior3count)
          if prior3count>0 and partial_count>0 else 0.,
       (partial[-1]["c"]-partial[-1]["o"])/max(partial[-1]["o"],1e-9),
       float(partial[-1]["c"]>partial[-1]["o"]),
    ]
    if not all(math.isfinite(x) for x in v):
        raise ValueError("NONFINITE_FEATURE")
    return v


def label_next_candle(bar):
    if bar["c"]>bar["o"]:return 1
    if bar["c"]<bar["o"]:return 0
    return None


def observations(prepared):
    assert set(prepared)==set(SYMBOLS)
    base=prepared[SYMBOLS[0]]["four"]
    for symbol in SYMBOLS[1:]:
        other=prepared[symbol]["four"]
        if len(other)!=len(base) or any(
                b["t"]!=a["t"] for a,b in zip(base,other)):
            raise ValueError("CROSS_ASSET_4H_UNALIGNED")
    obs={s:[] for s in SYMBOLS}
    doji=Counter()
    for i in range(1260,len(base)):
        t=base[i]["t"]
        per={symbol:features_at(symbol,prepared,i) for symbol in SYMBOLS}
        if any(v is None for v in per.values()):
            continue
        combined=tuple(x for s in SYMBOLS for x in per[s])
        # UTC hour, weekday are known at the decision time T-5m.
        stamp=datetime.fromtimestamp(t,timezone.utc)
        theta=2*math.pi*(stamp.hour/24)
        weekday=2*math.pi*(stamp.weekday()/7)
        context=(math.sin(theta),math.cos(theta),
                 math.sin(weekday),math.cos(weekday))
        x=combined+context
        for s in SYMBOLS:
            y=label_next_candle(prepared[s]["four"][i])
            if y is None:
                doji[s]+=1
                continue
            obs[s].append({"targetStartUTC":iso(t),
                           "decisionUTC":iso(t-LEAD_SECONDS),
                           "t":t,"x":x,"y":y,
                           "actualOpen":prepared[s]["four"][i]["o"],
                           "actualClose":prepared[s]["four"][i]["c"],
                           "previousComplete4HColor":
                               label_next_candle(prepared[s]["four"][i-2])})
    return obs,dict(doji)


def wilson(w,n):
    if n==0:return None
    p=w/n
    z=1.95996398454
    den=1+z*z/n
    return round(100*((p+z*z/(2*n))
         -z*math.sqrt(p*(1-p)/n+z*z/(4*n*n)))/den,2)


def results(rows,prob_col,threshold=None):
    eligible=[row for row in rows if row.get(prob_col) is not None]
    if threshold is not None:
        selected=[r for r in eligible if max(r[prob_col],1-r[prob_col])>=threshold]
    else:
        selected=eligible
    n=len(selected)
    correct=sum((r[prob_col]>=.5)==(r["y"]==1) for r in selected)
    return {"eligible":len(eligible),
            "predictions":n,
            "noPredictions":len(rows)-n,
            "coveragePct":round(100*n/len(rows),2) if rows else None,
            "correct":correct,
            "hitRatePct":round(100*correct/n,2) if n else None,
            "wilson95LowerPct":wilson(correct,n),
            "userGoal75Observed":n>0 and correct/n>=.75,
            "confidenceThreshold":threshold,
            "notForwardValidated":True}


def fit_and_predict(obs):
    # scikit-learn is used as a transparent baseline model, not a hyperparameter
    # search. C=0.2 and thresholds were predeclared for ALL SIX folds.
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    from sklearn.pipeline import make_pipeline
    report={}
    records={}
    for symbol,all_rows in obs.items():
        records[symbol]=[]
        report[symbol]={}
        all_rows=sorted(all_rows,key=lambda r:r["t"])
        for fold_name,lo,hi in FOLDS:
            start,end=ts(lo),ts(hi)
            training=[r for r in all_rows if r["t"]+FOUR<=start]
            testing=[r for r in all_rows if start<=r["t"]<end]
            if len(training)<MIN_TRAIN_SAMPLES or not testing:
                raise ValueError("FOLD_MIN_TRAIN_OR_TEST_INVALID_"+symbol+"_"+fold_name)
            model=make_pipeline(
                StandardScaler(),
                LogisticRegression(C=0.2,max_iter=600,solver="lbfgs"))
            model.fit([r["x"] for r in training],[r["y"] for r in training])
            probs=model.predict_proba([r["x"] for r in testing])[:,1]
            major=int(sum(r["y"] for r in training)/len(training)>=.5)
            annotated=[]
            for j,(row,prob) in enumerate(zip(testing,probs)):
                d={"targetStartUTC":row["targetStartUTC"],
                   "decisionUTC":row["decisionUTC"],
                   "y":row["y"],
                   "actualOpen":row["actualOpen"],
                   "actualClose":row["actualClose"],
                   "modelPgreen":float(prob),
                   "majorityPgreen":float(major),
                   "laggedCandlePgreen":float(row["previousComplete4HColor"])
                        if row["previousComplete4HColor"] is not None else None}
                if d["decisionUTC"]>=d["targetStartUTC"]:
                    raise ValueError("DECISION_WAS_NOT_BEFORE_CANDLE_OPEN")
                annotated.append(d)
            brier=sum((a["modelPgreen"]-a["y"])**2 for a in annotated)/len(annotated)
            score={
              "trainingExamples":len(training),
              "testCandles":len(annotated),
              "trainLastLabelKnownBeforeFold":True,
              "majorityTrainGreenRatePct":round(100*sum(x["y"] for x in training)/len(training),2),
              "greenActualPct":round(100*sum(x["y"] for x in annotated)/len(annotated),2),
              "alwaysTrainMajority":results(annotated,"majorityPgreen"),
              "lastClosed4HColor":results(annotated,"laggedCandlePgreen"),
              "fixedLogisticAll":results(annotated,"modelPgreen"),
              "fixedLogisticConfidence55":results(annotated,"modelPgreen",.55),
              "fixedLogisticConfidence60":results(annotated,"modelPgreen",.60),
              "fixedLogisticConfidence65":results(annotated,"modelPgreen",.65),
              "brierModel":round(brier,5),
              "brierTrainMajority":round(
                  sum((a["majorityPgreen"]-a["y"])**2 for a in annotated)/len(annotated),5),
              "modelType":"StandardScaler LogisticRegression C0.2 fixed",
              "futureCandleOpenUsedAsFeature":False}
            report[symbol][fold_name]=score
            records[symbol].extend({**r,"fold":fold_name} for r in annotated)
            print("V9_NEXT4H_FOLD",symbol,fold_name,score["fixedLogisticAll"],
                  score["fixedLogisticConfidence60"],flush=True)
    return report,records


def overall(records):
    aggregated={}
    for symbol,rows in records.items():
        aggregated[symbol]={
           "samples":len(rows),
           "greenActualCount":sum(x["y"] for x in rows),
           "majorityBaseline":results(rows,"majorityPgreen"),
           "lastClosed4HColorBaseline":results(rows,"laggedCandlePgreen"),
           "logisticAll":results(rows,"modelPgreen"),
           "logistic55":results(rows,"modelPgreen",.55),
           "logistic60":results(rows,"modelPgreen",.60),
           "logistic65":results(rows,"modelPgreen",.65),
           "brier":round(sum((x["modelPgreen"]-x["y"])**2 for x in rows)/len(rows),5),
           "last20Predictions":[
              {"T":r["targetStartUTC"],"decisionUTC":r["decisionUTC"],
               "predicted":"GREEN" if r["modelPgreen"]>=.5 else "RED",
               "pGreen":round(r["modelPgreen"],5),
               "actual":"GREEN" if r["y"] else "RED",
               "open":r["actualOpen"],"close":r["actualClose"]}
              for r in rows[-20:]],
        }
    return aggregated


def markdown(report):
    lines=["# V9: BEFORE next 4H starts — GREEN / RED of that candle",
           "",
           "## Exact prediction contract",
           "- Decision **T−5 minutes**, target Binance Futures 4H candle **[T,T+4h)**.",
           "- GREEN iff next candle **close > its OWN open**. RED iff **close < own open**.",
           "- Decision does **NOT** know next open, current 4H final hour, or future prices.",
           "- Last fully closed 4H at T−5m ends **T−4h**. Last available full 1H ends **T−1h**.",
           "- BTC/ETH/SOL same UTC 4H boundaries, official SHA-256 archives.",
           "- Predeclared expanding-walk-forward folds; C=0.2 fixed logistic, no tuning, 55/60/65% confidence coverage disclosed.",
           "- Historical 2023–2026 has already been investigated elsewhere; these results are NOT independent prospective evidence.",
           "- No real orders, no stop/TP, no funding/cost claims, NO live signal enablement.",
           "",
           "| Asset | Test candles | Majority | Last completed 4H color | Logistic all | >=60% confidence | >=65% confidence |",
           "|---|---:|---:|---:|---:|---:|---:|"]
    for s,v in report["overall"].items():
        def f(z):
            if z["hitRatePct"] is None:return "no signals"
            return f"{z['correct']}/{z['predictions']} ({z['hitRatePct']}%)"
        lines.append(f"| {s} | {v['samples']} | {f(v['majorityBaseline'])} | "
                     f"{f(v['lastClosed4HColorBaseline'])} | {f(v['logisticAll'])} | "
                     f"{f(v['logistic60'])} | {f(v['logistic65'])} |")
    lines+=["","## Per 6 predeclared periods",]
    for s,folds in report["folds"].items():
        lines+=["",f"### {s}","| Period | All predictions | 60% confidence | Coverage at 60% |",
                "|---|---:|---:|---:|"]
        for name,x in folds.items():
            a=x["fixedLogisticAll"];c=x["fixedLogisticConfidence60"]
            lines.append(f"| {name} | {a['correct']}/{a['predictions']} ({a['hitRatePct']}%) | "
                         f"{c['correct']}/{c['predictions']} ({c['hitRatePct']}%)"
                         f" | {c['coveragePct']}% |")
    lines+=["","**IMPORTANT:** A top historical percentage does not establish 75% prospective accuracy. "
            "No data from current/future 4H candle at T is in the features. "
            "Any model selection from these results is post-hoc.",
            ""]
    return "\n".join(lines)


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--json",default="forward/v9_next_4h_color/latest.json")
    p.add_argument("--markdown",default="forward/v9_next_4h_color/latest.md")
    a=p.parse_args()
    data,sources=download_three()
    prepared=prepare(data)
    obs,doji=observations(prepared)
    folded,records=fit_and_predict(obs)
    report={
       "mode":"V9_NEXT_4H_OWN_OPEN_CLOSE_COLOR_PREDICT_T_MINUS_5M",
       "status":"HISTORICAL_CAUSAL_WALK_FORWARD_RESEARCH_ONLY",
       "generatedUTC":iso(int(datetime.now(timezone.utc).timestamp())),
       "targetDefinition":"GREEN iff future4H.close>future4H.open; RED iff future4H.close<future4H.open",
       "decisionLeadMinutes":5,
       "latestFullyClosed4HAtDecisionEndsHoursBeforeTargetStart":4,
       "latestFullyClosed1HAtDecisionEndsHoursBeforeTargetStart":1,
       "noTarget4HOpenAvailableAtDecision":True,
       "sixPredeclaredWalkForwardFolds":[x[0] for x in FOLDS],
       "fixedConfidenceThresholds":list(CONFIDENCE_BANDS),
       "fixedRegularizationC":0.2,
       "sources":sources,
       "dojiExcluded":doji,
       "folds":folded,
       "overall":overall(records),
       "previouslyInspectedHistoricalDataNotProspective":True,
       "futureLookaheadTestRequired":True,
       "liveTradingApproved":False,
       "brokerOrders":False,
       "productionModified":False,
       "liveSignalNotificationsModified":False,
       "userTargetAccuracyPct":75,
    }
    out=Path(a.json);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    md=Path(a.markdown);md.parent.mkdir(parents=True,exist_ok=True)
    md.write_text(markdown(report),encoding="utf-8")
    print("V9_NEXT4H_COLOR_BACKTEST_DONE",
          json.dumps({s:{k:v[k] for k in ("samples","logisticAll","logistic60","logistic65")}
                      for s,v in report["overall"].items()}),flush=True)


if __name__=="__main__":
    main()
