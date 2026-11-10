#!/usr/bin/env python3
"""V9 BTC ETH SOL synchronized OI, funding-history and taker-CVD research.

NO live orders, trading signals, or approval. Source Coinalyze read-only API
for Binance USD-M perpetual BTCUSDT_PERP.A ETHUSDT_PERP.A SOLUSDT_PERP.A.
Three synchronous sources at 1hour granularity:
  ohlcv-history with v and bv (BV->takerBuy only cross-checked for SOL
  on a separate 216-hour Binance test, NOT independently for BTC/ETH)
  open-interest-history in provider's native contract/base units
  funding-rate-history 1H candle of the provider funding series, NOT
  actual settlement cash flow or certified funding unit
Timestamp t is start of 1H interval: current bar is available only after
t+3600 UTC. For every observation at four-hour checkpoint C, read data
only from bars with t+3600<=C. Forward 4H close for evaluation ONLY.

No lookahead and no parameter-fitting. Tests evaluate predeclared rules:
  A: prior 4H price return sign (simple momentum baseline)
  B: A + prior 4H signed taker pressure agrees (4H CVD proxy)
  C: B + 4H OI close growth >0
  D: C + not-extreme 1H funding-history relative to previous 24 values
  E: 4H taker-flow sign only (simple flow baseline)
Predictions are only about next 4H closing price direction; they are NOT
actual profit/loss, optimized strategies, or forward trading tests.
Seven-day rolling historical window, 4H non-overlapping checkpoints.
BTC/ETH/SOL samples are correlated; 3x observations are not independent.
"""
import argparse
from bisect import bisect_right
from datetime import datetime,timezone
from hashlib import sha256
import json,math,os,urllib.request,urllib.parse,urllib.error
from pathlib import Path
from statistics import median

ROOT="https://api.coinalyze.net/v1/"
CONTRACTS=("BTCUSDT_PERP.A","ETHUSDT_PERP.A","SOLUSDT_PERP.A")
HOUR=3600
FOUR=4*HOUR
LOOKBACK_DAYS=10
MAX_RESPONSE_BYTES=8000000


def iso(ts):
    return datetime.fromtimestamp(ts,timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def finite(v,name):
    if type(v) not in (int,float) or not math.isfinite(v):
        raise ValueError("NONFINITE_"+name)
    return float(v)


def get_group(endpoint,symbols,key,low,high,fetch=None):
    params={"symbols":",".join(symbols),"interval":"1hour","from":low,"to":high}
    if endpoint=="open-interest-history":
        params["convert_to_usd"]="false"
    if fetch is None:
        qs=urllib.parse.urlencode(params)
        req=urllib.request.Request(ROOT+endpoint+"?"+qs,
            headers={"api_key":key,"Accept":"application/json",
                     "User-Agent":"V9-BTC-ETH-SOL-deriv-no-orders/1.0"})
        try:
            with urllib.request.urlopen(req,timeout=45) as r:
                if r.status!=200:raise ValueError("COINALYZE_HTTP_NOT200")
                raw=r.read(MAX_RESPONSE_BYTES)
        except urllib.error.HTTPError as e:
            raise ValueError("COINALYZE_HTTP_"+str(e.code)) from None
    else:
        raw=fetch(endpoint,params)
        if isinstance(raw,str):raw=raw.encode()
    if isinstance(raw,bytes):data=json.loads(raw)
    else:
        data=raw
        raw=json.dumps(data,sort_keys=True).encode()
    if not isinstance(data,list) or len(data)!=len(symbols):
        raise ValueError("WRONG_SYMBOL_GROUP_LENGTH_"+endpoint)
    if set(x.get("symbol") for x in data)!=set(symbols):
        raise ValueError("WRONG_SYMBOL_GROUP_"+endpoint)
    result={}
    for obj in data:
        name=obj["symbol"]
        rows=obj.get("history")
        if not isinstance(rows,list) or not rows:
            raise ValueError("EMPTY_HISTORY_"+endpoint+"_"+name)
        seen=set()
        ordered=[]
        for b in rows:
            t=b.get("t")
            if type(t) is not int or t%HOUR:
                raise ValueError("MISALIGNED_HOUR_"+endpoint+"_"+name)
            if t in seen:raise ValueError("DUPLICATE_"+endpoint+"_"+name)
            seen.add(t)
            if t+HOUR>high:
                # Discard incomplete current hour explicitly.
                continue
            if t<low:continue
            record={"t":t}
            if endpoint=="ohlcv-history":
                for field in ("o","h","l","c","v","bv"):
                    if field not in b:raise ValueError("MISSING_"+field+"_"+name)
                    record[field]=finite(b[field],field)
                if not (0<record["l"]<=min(record["o"],record["c"])
                        <=max(record["o"],record["c"])<=record["h"]
                        and record["v"]>=0 and
                        -1e-6<=record["bv"]<=record["v"]+max(1e-5,record["v"]*1e-6)):
                    raise ValueError("BAD_VOLUME_OHLCV_"+name)
            else:
                for field in ("o","h","l","c"):
                    if field not in b:raise ValueError("MISSING_"+field+"_"+name)
                    record[field]=finite(b[field],field)
                # funding-rate candles may cross zero and be negative, OI not
                if endpoint=="open-interest-history" and not (
                    record["l"]>0 and record["l"]<=min(record["o"],record["c"])
                    <=max(record["o"],record["c"])<=record["h"]):
                    raise ValueError("BAD_OI_VALUE_"+name)
                if endpoint=="funding-rate-history" and not (
                    record["l"]<=min(record["o"],record["c"])
                    <=max(record["o"],record["c"])<=record["h"]):
                    raise ValueError("BAD_FUNDING_OHLC_"+name)
            ordered.append(record)
        ordered.sort(key=lambda x:x["t"])
        if not ordered:raise ValueError("NO_CLOSED_"+endpoint+"_"+name)
        result[name]=ordered
    return result,sha256(raw).hexdigest()


def aligned_bars(ohlcv,oi,funding,checkpoint):
    """Return a strictly contiguous prior 28h universe ending at checkpoint.

    The 28h span supports 24 prior funding history and 4h lookbacks.
    """
    start=checkpoint-28*HOUR
    series={}
    for label,data in (("kline",ohlcv),("oi",oi),("funding",funding)):
        rows={x["t"]:x for x in data}
        selected=[rows.get(start+j*HOUR) for j in range(28)]
        if any(x is None for x in selected):
            return None
        if any(x["t"]+HOUR>checkpoint for x in selected):
            raise ValueError("FUTURE_USED_IN_FEATURE")
        series[label]=selected
    return series


def features(kline,oi,funding,checkpoint):
    data=aligned_bars(kline,oi,funding,checkpoint)
    if data is None:return None
    a,b,c=data["kline"],data["oi"],data["funding"]
    last4=a[-4:]
    vol=sum(x["v"] for x in last4)
    delta=sum(2*x["bv"]-x["v"] for x in last4)
    if vol<=0:return None
    price=a[-1]["c"]
    price4=a[-5]["c"]
    oi_prev=b[-5]["c"]
    oi_last=b[-1]["c"]
    if min(price,price4,oi_prev,oi_last)<=0:return None
    funding_history=[x["c"] for x in c[-25:-1]]
    funding_now=c[-1]["c"]
    if len(funding_history)!=24 or not all(math.isfinite(v) for v in funding_history):
        return None
    price_move=price/price4-1
    oi_change=oi_last/oi_prev-1
    # Funding percentile from PAST 24 complete readings only. This is a
    # context-based risk filter, not a funding settlement/cashflow model.
    percentile=sum(v<=funding_now for v in funding_history)/24.
    momentum="LONG" if price_move>0 else "SHORT" if price_move<0 else None
    pressure="LONG" if delta>0 else "SHORT" if delta<0 else None
    return {"asOfUTC":iso(checkpoint),"4HClose":price,
            "prev4HChangePct":round(price_move*100,6),
            "CVD4hBaseProxy":round(delta,6),
            "CVD4hPctOfVolume":round(delta/vol*100,5),
            "buyShare4H":round((vol+delta)/(2*vol),6),
            "OI4hChangePct":round(oi_change*100,6),
            "fundingHistoryLastClosed":funding_now,
            "fundingPercentileRelativePrior24":round(percentile,6),
            "momentumSide":momentum,"takerPressureSide":pressure,
            "OIAdded":oi_change>0,
            "fundingNotExtremeAgainstSide":(percentile<=.75 if momentum=="LONG"
                   else percentile>=.25 if momentum=="SHORT" else False),
            "sourceAlignedComplete28Hours":True}


def variants(row):
    m=row["momentumSide"]
    p=row["takerPressureSide"]
    agrees=m is not None and m==p
    add=agrees and row["OIAdded"]
    return {
       "A_priceMomentum":m,
       "B_momentumAndCVD":m if agrees else None,
       "C_BplusRisingOI":m if add else None,
       "D_CplusFundingContext":m if add and row["fundingNotExtremeAgainstSide"] else None,
       "E_takerCVDOnly":p}


def label_observation(kline,checkpoint):
    ks={x["t"]:x for x in kline}
    next_hour=checkpoint+3*HOUR # final hour of next 4H block
    if next_hour not in ks:return None
    last=ks[next_hour]
    if last["t"]+HOUR!=checkpoint+FOUR:
        raise ValueError("OUTCOME_INVALID_TIMESTAMP")
    # Strict no missing forward 1H future to make a 4H candle
    if not all(checkpoint+j*HOUR in ks for j in range(4)):
        return None
    return last["c"]


def wilson_lower(w,n):
    if n==0:return None
    z=1.95996398454
    p=w/n;den=1+z*z/n
    return round(100*((p+z*z/(2*n))-z*math.sqrt((p*(1-p)+z*z/(4*n))/n))/den,2)


def metric(outcomes):
    x=[y for y in outcomes if y["prediction"] is not None]
    n=len(x)
    wins=sum(y["correct"] for y in x)
    return {"predictions":n,"correct":wins,
            "hitRatePct":round(100*wins/n,2) if n else None,
            "wilson95LowerBoundPct":wilson_lower(wins,n),
            "noSignal":len(outcomes)-n,
            "directionalOnlyNoPnL":True,
            "notIndependentAcrossAssets":True}


def evaluate_one(kline,oi,funding,days=7):
    ks={x["t"]:x for x in kline}
    common_ends={x["t"]+HOUR for x in kline}.intersection(
        x["t"]+HOUR for x in oi).intersection(x["t"]+HOUR for x in funding)
    latest_end=max(common_ends)
    # Anchor checkpoints to exchange standard UTC 4H closes.
    end=latest_end//FOUR*FOUR
    start=end-days*24*HOUR
    checkpoints=range(start,end,FOUR)
    per={key:[] for key in ("A_priceMomentum","B_momentumAndCVD",
                           "C_BplusRisingOI","D_CplusFundingContext",
                           "E_takerCVDOnly")}
    examples=[]
    eligible=0
    skipped=0
    for t in checkpoints:
        row=features(kline,oi,funding,t)
        future=label_observation(kline,t)
        if row is None or future is None:
            skipped+=1
            continue
        eligible+=1
        pred=variants(row)
        for key,side in pred.items():
            correct=(future>row["4HClose"]) if side=="LONG" else (
                future<row["4HClose"] if side=="SHORT" else None)
            per[key].append({"prediction":side,"correct":correct})
        if len(examples)<3:
            examples.append({"features":row,
                             "forward4HPrice":future,
                             "prediction":pred,
                             "outcomeKnownUTC":iso(t+FOUR)})
    return {"windowStartUTC":iso(start),"windowEndUTC":iso(end),
            "intended4HCheckpoints":len(checkpoints),
            "fullyAlignedEvaluable":eligible,
            "rejectedMissingOrIncomplete":skipped,
            "results":{k:metric(x) for k,x in per.items()},
            "earliestExamples":examples,
            "noOptimizationFromResults":True,
            "notActualTrades":True}


def one_source_quality(group,expected_target):
    results={}
    for symbol,items in group.items():
        end=items[-1]["t"]+HOUR
        data={x["t"] for x in items}
        recent=range(end-24*HOUR,end,HOUR)
        results[symbol]={
           "barsReceived":len(items),
           "latestClosedUTC":iso(end),
           "lagFromTargetHours":round((expected_target-end)/HOUR,2),
           "last24HoursPresent":sum(t in data for t in recent),
           "latestAgeTooOld":(expected_target-end)>4*HOUR}
    return results


def run(now,key,fetch=None):
    if not key and fetch is None:raise ValueError("NO_READ_ONLY_COINALYZE_KEY")
    expected=now//HOUR*HOUR
    low=expected-LOOKBACK_DAYS*24*HOUR
    groups={}
    proofs={}
    for endpoint in ("ohlcv-history","open-interest-history","funding-rate-history"):
        data,proof=get_group(endpoint,CONTRACTS,key,low,expected,fetch=fetch)
        groups[endpoint]=data
        proofs[endpoint]=proof
    quality={endpoint:one_source_quality(data,expected)
             for endpoint,data in groups.items()}
    per={}
    for symbol in CONTRACTS:
        p=groups["ohlcv-history"][symbol]
        oi=groups["open-interest-history"][symbol]
        f=groups["funding-rate-history"][symbol]
        per[symbol]=evaluate_one(p,oi,f)
        per[symbol]["inputQuality"]={k:v[symbol] for k,v in quality.items()}
        # Report late data and refuse to turn it into a current signal.
        per[symbol]["sourceFreshEnoughForCurrentHourlySnapshot"]=all(
            not quality[k][symbol]["latestAgeTooOld"] for k in quality)
    response={
      "mode":"V9_BTC_ETH_SOL_CVD_OI_FUNDING_HISTORICAL_ABLATION",
      "status":"HISTORICAL_DIRECTION_ONLY_NO_SIGNAL",
      "generatedUTC":iso(now),
      "expectedLastClosed1HUTC":iso(expected),
      "source":"Coinalyze read-only Binance USD-M perpetual OHLCV, OI, funding-rate histories",
      "contracts":per,"sourceSHA256":proofs,
      "fundingFieldSemantics":"1H provider funding-rate-history series; not certified exchange paid funding settlement or fee",
      "OIFieldSemantics":"1H provider open interest c (convert_to_usd=false); point-in-time after bar close",
      "takerFieldSemantics":"Coinalyze bv; independently reconciled with Binance on limited historical SOL sample only",
      "noFutureFeatures":True,"fourHourOutcomesNonOverlappingWithinEachAsset":True,
      "samplesAcrossBTCETHSOLCorrelated":True,
      "previousHistoricalAnalysesMakeThisExploratoryNotProspective":True,
      "brokerOrders":False,"productionEdited":False,
      "liveTradingApproved":False}
    return response


def main():
    args=argparse.ArgumentParser()
    args.add_argument("--out",default="forward/v9_three_derivatives/latest.json")
    c=args.parse_args()
    key=(os.getenv("ETH_V7_COINALYZE_API_KEY")
         or os.getenv("SOL_V8_COINALYZE_API_KEY")
         or os.getenv("COINALYZE_API_KEY") or "").strip()
    now=int(datetime.now(timezone.utc).timestamp())
    report=run(now,key)
    output=Path(c.out);output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("V9_THREE_ASSET_DATA_ABLATION",json.dumps({
       k:{"eligible":v["fullyAlignedEvaluable"],
          "rejected":v["rejectedMissingOrIncomplete"],
          "results":v["results"]}
       for k,v in report["contracts"].items()}),flush=True)


if __name__=="__main__":
    main()
