#!/usr/bin/env python3
"""V9 prospective PAPER ONLY: BTC ETH SOL future 4H GREEN/RED snapshot.

Point-in-time capture in the PRE-START 25-to-3 minute window only.
At that time T, next 4H [T,T+4H) has NOT begun. At most three fully
CLOSED 1H bars from the current not-yet-closed 4H are used. No target
open/close prices, no partial last-hour information, no unsourced values.

The prospective model was frozen using Binance Futures official archives
through 2026-09-30. Coinalyze read-only OHLCV (Binance perpetuals)
has documented fields v/bv/tx; its BV matched archived SOL data in a
separate 216-hour check. BTC/ETH volume and all tx are NOT independently
reconciled yet: this is exploratory, not validated live prediction.
No broker API, no secrets in output, no trading orders, no alert activation.
"""
import argparse
from datetime import datetime,timezone
from hashlib import sha256
import json,math,os
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request,urlopen

from v9_next_4h_color_research import (
  FOUR,HOUR,DAY,SYMBOLS,features_at,prepare,iso,LEAD_SECONDS)
from v9_three_asset_derivatives_ablation import ROOT

PAPER_STATUS="BEFORE_START_PAPER_FORECAST_UNCALIBRATED_NOT_TRADE"
EXCHANGE_SYMBOLS={
    "BTCUSDT":"BTCUSDT_PERP.A",
    "ETHUSDT":"ETHUSDT_PERP.A",
    "SOLUSDT":"SOLUSDT_PERP.A"}
HISTORY_1H=1000
HISTORY_D=330
EARLIEST_MINUTES_BEFORE=25
LATEST_MINUTES_BEFORE=3
MAX_RESPONSE=6000000


def next_boundary(now):
    return (now//FOUR+1)*FOUR


def check_clock(now):
    target=next_boundary(now)
    seconds=target-now
    if not LATEST_MINUTES_BEFORE*60<=seconds<=EARLIEST_MINUTES_BEFORE*60:
        raise ValueError("NOT_WITHIN_PRE_START_25_TO_3_MINUTES")
    if target%FOUR or now>=target:
        raise ValueError("PREDICTION_CANNOT_BE_AFTER_START")
    return target


def get_group(tf,low,now,key,fetch=None):
    params={"symbols":",".join(EXCHANGE_SYMBOLS.values()),
            "interval":tf,"from":low,"to":now}
    if fetch:
        raw=fetch(tf,params)
        if not isinstance(raw,bytes):
            raw=json.dumps(raw,separators=(",",":")).encode()
    else:
        qs=urlencode(params)
        req=Request(ROOT+"ohlcv-history?"+qs,headers={
           "api_key":key,"Accept":"application/json",
           "User-Agent":"V9-before-start-paper-readonly/1.0"})
        with urlopen(req,timeout=45) as resp:
            if resp.status!=200:raise ValueError("PROVIDER_NON200")
            raw=resp.read(MAX_RESPONSE)
    if len(raw)>MAX_RESPONSE:
        raise ValueError("SOURCE_TOO_LARGE")
    payload=json.loads(raw)
    if not isinstance(payload,list) or len(payload)!=3 or set(
      x.get("symbol") for x in payload)!=set(EXCHANGE_SYMBOLS.values()):
        raise ValueError("THREE_BINANCE_PERPETUAL_CONTRACTS_REQUIRED")
    result={}
    for block in payload:
        symbol=next(k for k,v in EXCHANGE_SYMBOLS.items()
                    if v==block["symbol"])
        history=block.get("history")
        if not isinstance(history,list) or not history:
            raise ValueError("EMPTY_OHLCV_HISTORY_"+symbol)
        rows=[]
        for item in history:
            t=item.get("t")
            if type(t) is not int or t%(HOUR if tf=="1hour" else DAY):
                raise ValueError("UNALIGNED_BAR_"+symbol)
            if t<low or t+(HOUR if tf=="1hour" else DAY)>now:
                continue  # never include an incomplete candle
            record={"t":t}
            for k in ("o","h","l","c","v"):
                v=item.get(k)
                if type(v) not in (int,float) or not math.isfinite(v):
                    raise ValueError("MISSING_INVALID_"+k+"_"+symbol)
                record[k]=float(v)
            if not (0<record["l"]<=min(record["o"],record["c"])
                    <=max(record["o"],record["c"])<=record["h"]
                    and record["v"]>=0):
                raise ValueError("IMPOSSIBLE_OHLCV_"+symbol)
            if tf=="1hour":
                bv=item.get("bv")
                tx=item.get("tx")
                if (type(bv) not in (int,float) or
                    type(tx) not in (int,float) or
                    not math.isfinite(bv) or not math.isfinite(tx) or
                    tx<0 or int(tx)!=tx or
                    not -1e-5<=bv<=record["v"]+max(1e-5,record["v"]*1e-6)):
                    raise ValueError("PROVIDER_TAKER_TRADES_UNVERIFIED_"+symbol)
                record["tbv"]=min(record["v"],max(0.,float(bv)))
                record["trades"]=int(tx)
            rows.append(record)
        if any(rows[i]["t"]>=rows[i+1]["t"] for i in range(len(rows)-1)):
            raise ValueError("UNSORTED_DUPLICATE_PROVIDER_CANDLES_"+symbol)
        result[symbol]=rows
    return result,sha256(raw).hexdigest()


def aggregate_closed_four(one):
    if len(one)%4:raise ValueError("4H_GROUP_NOT_COMPLETE")
    result=[]
    for j in range(0,len(one),4):
        b=one[j:j+4]
        if b[0]["t"]%FOUR or any(
            x["t"]!=b[0]["t"]+k*HOUR for k,x in enumerate(b)):
            raise ValueError("4H_NOT_CONTIGUOUS_OR_ALIGNED")
        result.append({
            "t":b[0]["t"],"o":b[0]["o"],
            "h":max(x["h"] for x in b),
            "l":min(x["l"] for x in b),
            "c":b[-1]["c"],
            "v":sum(x["v"] for x in b),
            "tbv":sum(x["tbv"] for x in b),
            "trades":sum(x["trades"] for x in b)})
    return result


def verify_daily_vs_hours(one,daily,now):
    d=daily[-1]
    hours=[b for b in one if d["t"]<=b["t"]<d["t"]+DAY]
    if len(hours)!=24:return False
    if not all(hours[j]["t"]==d["t"]+j*HOUR for j in range(24)):
        raise ValueError("DAILY_24H_CONTINUITY_MISSING")
    if abs(hours[-1]["c"]-d["c"])>max(.00001,abs(d["c"])*.00002):
        raise ValueError("DAILY_FROM_1H_LAST_CLOSE_MISMATCH")
    hvol=sum(b["v"] for b in hours)
    if abs(hvol-d["v"])>max(.00001,abs(d["v"])*.003):
        raise ValueError("DAILY_FROM_1H_VOLUME_MISMATCH")
    return True


def snapshot(now,models,key,fetch=None):
    target=check_clock(now)
    if models.get("status")!="FROZEN_SHADOW_PAPER_MODELS_NOT_PRODUCTION":
        raise ValueError("NOT_A_FROZEN_PAPER_MODEL")
    if models.get("noProspectiveTrackRecordYet") is not True:
        raise ValueError("MODEL_ORIGIN_UNEXPECTED")
    if set(models.get("symbols",{}))!=set(SYMBOLS):
        raise ValueError("FROZEN_WRONG_ASSET_SET")
    low1=target-HISTORY_1H*HOUR
    latest_expected_hour_end=target-HOUR
    one,source_hash1=get_group("1hour",low1,now,key,fetch)
    lowdaily=(target//DAY-HISTORY_D)*DAY
    daily,source_hashD=get_group("daily",lowdaily,now,key,fetch)
    source_data={}
    for symbol in SYMBOLS:
        hrs=one[symbol]
        if (len(hrs)!=HISTORY_1H-1 or
            hrs[0]["t"]!=low1 or
            hrs[-1]["t"]+HOUR!=latest_expected_hour_end):
            raise ValueError("1H_INCOMPLETE_STALE_OR_MISSING_"+symbol)
        if any(hrs[j]["t"]!=low1+j*HOUR for j in range(len(hrs))):
            raise ValueError("1H_HISTORY_HAS_GAPS_"+symbol)
        d=daily[symbol]
        if len(d)<205 or any(
            d[j+1]["t"]!=d[j]["t"]+DAY for j in range(len(d)-1)):
            raise ValueError("DAILY_SMA200_HISTORY_INCOMPLETE_"+symbol)
        expected_daily_close=((target-LEAD_SECONDS)//DAY)*DAY
        if d[-1]["t"]+DAY!=expected_daily_close:
            raise ValueError("MOST_RECENT_DAILY_CLOSE_UNAVAILABLE_"+symbol)
        verify_daily_vs_hours(hrs,d,now)
        # The [T-4H,T) candle has NOT yet closed. Use no 4H of it.
        old=hrs[:HISTORY_1H-4]
        four=aggregate_closed_four(old)
        if len(four)<210 or four[-1]["t"]+FOUR!=target-FOUR:
            raise ValueError("LAST_COMPLETE_FOUR_HOURS_NOT_VERIFIED_"+symbol)
        source_data[symbol]={"one":hrs,"four":four,"daily":d}
    prep=prepare(source_data)
    feats=[features_at(s,prep,len(prep[s]["four"])+1,target_start_t=target)
           for s in SYMBOLS]
    if any(v is None for v in feats):
        raise ValueError("INSUFFICIENT_FEATURE_HISTORY")
    dt=datetime.fromtimestamp(target,timezone.utc)
    theta=2*math.pi*(dt.hour/24)
    week=2*math.pi*(dt.weekday()/7)
    x=tuple(v for series in feats for v in series)+(
          math.sin(theta),math.cos(theta),math.sin(week),math.cos(week))
    forecasts={}
    for symbol in SYMBOLS:
        model=models["symbols"][symbol]
        n=model["featureCount"]
        if n!=len(x) or any(len(model[k])!=n for k in
                             ("scalerMean","scalerScale","logisticCoefficients")):
            raise ValueError("MODEL_SCHEMA_MISMATCH")
        logits=model["logisticIntercept"]+sum(
          c*((value-mean)/scale) for value,c,mean,scale in zip(
             x,model["logisticCoefficients"],
             model["scalerMean"],model["scalerScale"]))
        if not math.isfinite(logits):raise ValueError("NONFINITE_MODEL_OUTPUT")
        p=1/(1+math.exp(-max(-50,min(50,logits))))
        forecasts[symbol]={
           "direction":"GREEN" if p>=.5 else "RED",
           "pGreenUNCALIBRATED":round(p,6),
           "confidenceUNCALIBRATED":round(max(p,1-p),6),
           "predictionOnlyNotAnOrder":True,
           "lastFullyClosed1HEndUTC":iso(latest_expected_hour_end),
           "lastFullyClosed4HEndUTC":iso(target-FOUR),
           "latestCompletedDailyEndUTC":daily[symbol][-1]["t"]+DAY,
           "txFieldProviderParityNotIndependentlyVerified":True,
           "bvCrossVerifiedForBTCETH":False,
           "modelTrainingLabelsSHA256":model["trainingLabelsSHA256"],
           "featuresReplayed":n}
    return {
       "status":PAPER_STATUS,
       "mode":"NEXT_4H_OWN_OPEN_CLOSE_GREEN_RED_BEFORE_START",
       "decisionCapturedUTC":iso(now),
       "target4HStartUTC":iso(target),
       "target4HEndUTC":iso(target+FOUR),
       "minutesBeforeStart":round((target-now)/60,2),
       "allThreeAtSameTarget":True,
       "contract":"Binance USD-M perpetual via Coinalyze",
       "ohlcv1hResponseSHA256":source_hash1,
       "dailyResponseSHA256":source_hashD,
       "assetForecasts":forecasts,
       "noTargetOpenKnown":True,
       "forecastAlwaysRecordedEvenIfConfidenceLow":True,
       "notValidatedLiveDirection":True,
       "brokerOrders":False,"productionModified":False,
       "liveTradeOrAlertsActivated":False}


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--models",default="forward/v9_next_4h_color/frozen_models.json")
    p.add_argument("--dir",default="forward/v9_next_4h_color/paper_forecasts")
    a=p.parse_args()
    model=json.loads(Path(a.models).read_text())
    key=(os.getenv("ETH_V7_COINALYZE_API_KEY") or
         os.getenv("SOL_V8_COINALYZE_API_KEY") or
         os.getenv("COINALYZE_API_KEY") or "").strip()
    if not key:raise ValueError("MISSING_READONLY_COINALYZE_KEY")
    now=int(datetime.now(timezone.utc).timestamp())
    result=snapshot(now,model,key)
    target=result["target4HStartUTC"]
    path=Path(a.dir)/(target.replace(":","-")+".json")
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():
        raise ValueError("PREDICTION_ALREADY_EXISTS_IMMUTABLE_LEDGERS")
    path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print("V9_PAPER_BEFORE_START_PREDICTION_CAPTURED",str(path),
          json.dumps({k:v["direction"] for k,v in result["assetForecasts"].items()}),
          flush=True)


if __name__=="__main__":
    main()
