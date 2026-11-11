#!/usr/bin/env python3
"""V9 1H read-only paper STATUS, not a newly invented NEXT-4H forecast.

Every completed UTC hour, publish the three assets' actual CLOSED 1H
OHLC/RSI/MACD/EMA, last CLOSED 4H/Daily context, 24h taker delta proxy,
and only a previously persisted, pre-start V9 next-4H prediction when
one EXISTS. Never claim the 1H direction is a validated next4H signal.

Freeze one snapshot PER UNIQUE completed 1H (no backfills/repaints).
A separate V9 before-next-4H publication remains responsible for
official independently auditable green/red prestart 4H paper forecasts.
"""
import argparse,json,math,os
from datetime import datetime,timezone,timedelta
from pathlib import Path
from hashlib import sha256

from v9_next_4h_color_research import (
    DAY,FOUR,HOUR,SYMBOLS,iso,rsi14)
from v9_next4h_prestart_paper_capture import (
    get_group,aggregate_closed_four,verify_daily_vs_hours,HISTORY_1H,HISTORY_D)
from v9_next4h_paper_outcome_score import verify_prior_forecast

ISTANBUL=timezone(timedelta(hours=3))


def tsi(t):
    return datetime.fromtimestamp(t,ISTANBUL).strftime("%Y-%m-%d %H:%M TSİ")


def ema(v,n):
    if len(v)<n:
        raise ValueError("NOT_ENOUGH_FOR_EMA")
    start=sum(v[:n])/n
    alpha=2/(n+1)
    for x in v[n:]:
        start=alpha*x+(1-alpha)*start
    return start


def macd_hist(v):
    if len(v)<200:
        raise ValueError("INSUFFICIENT_HISTORY_MACD")
    def ema_trace(period):
        alpha=2/(period+1)
        initial=sum(v[:period])/period
        out=[None]*(period-1)+[initial]
        for x in v[period:]:
            out.append(alpha*x+(1-alpha)*out[-1])
        return out
    fast,slow=ema_trace(12),ema_trace(26)
    m=[fast[i]-slow[i] for i in range(25,len(v))]
    signal=ema_trace_on(m,9)
    return round(m[-1]-signal[-1],8)


def ema_trace_on(v,n):
    result=[None]*(n-1)+[sum(v[:n])/n]
    alpha=2/(n+1)
    for x in v[n:]:
        result.append(alpha*x+(1-alpha)*result[-1])
    return result


def close_indicators(bars):
    if len(bars)<200:
        raise ValueError("INDICATOR_HISTORY_LESS_THAN_200")
    closes=[b["c"] for b in bars]
    end=bars[-1]
    rsi=rsi14(closes)[-1]
    e20=ema(closes,20)
    e50=ema(closes,50)
    e200=ema(closes,200)
    hist=macd_hist(closes)
    return {
      "closedAtUTC":iso(end["t"]+{
          "1hour":HOUR,"4hour":FOUR,"daily":DAY
          }[{HOUR:"1hour",FOUR:"4hour",DAY:"daily"}[end["_seconds"]]]),
      "OHLCV":{"open":end["o"],"high":end["h"],
               "low":end["l"],"close":end["c"],"volume":end["v"]},
      "body":"GREEN" if end["c"]>end["o"] else (
           "RED" if end["c"]<end["o"] else "DOJI"),
      "RSI14":round(rsi,4),
      "EMA20":round(e20,8),
      "EMA50":round(e50,8),
      "EMA200":round(e200,8),
      "MACDHistogram":hist,
      "context":"BULLISH" if end["c"]>e20>e50 else
                "BEARISH" if end["c"]<e20<e50 else "MIXED",
      "RSIextreme":"OVERSOLD" if rsi<30 else (
                      "OVERBOUGHT" if rsi>70 else "NEUTRAL"),
      "technicalContextNotEvidenceOfNext4HColor":True}


def one_4h_history(one,closed_hour):
    complete_end=(closed_hour//FOUR)*FOUR
    start=next((j for j,x in enumerate(one) if x["t"]%FOUR==0),None)
    if start is None:
        raise ValueError("NO_4H_ALIGNMENT")
    complete=[x for x in one[start:] if x["t"]+HOUR<=complete_end]
    if not complete or len(complete)%4:
        raise ValueError("CANNOT_BUILD_COMPLETE_4H")
    return aggregate_closed_four(complete)


def read_locked(ledger_dir,start):
    p=Path(ledger_dir)/(iso(start).replace(":","-")+".json")
    if not p.exists():
        return {"status":"NO_PRESTART_FORECAST_RECORDED",
                "target4HStartUTC":iso(start),
                "noSignalFromPostStartAnalysis":True}
    item=json.loads(p.read_text())
    recorded,_=verify_prior_forecast(item)
    if recorded!=start:
        raise ValueError("FORECAST_OTHER_CANDLE")
    return {
      "status":"FROZEN_BEFORE_START_PAPER_FORECAST_RECORDED",
      "target4HStartUTC":item["target4HStartUTC"],
      "decisionCapturedUTC":item["decisionCapturedUTC"],
      "assetForecasts":{
          s:{"direction":item["assetForecasts"][s]["direction"],
             "pGreenUncalibrated":item["assetForecasts"][s]["pGreenUNCALIBRATED"]}
          for s in SYMBOLS},
      "noSignalFromPostStartAnalysis":True,
      "paperOnly":True}


def status_at(now,key,fetch=None,ledger_dir="forward/v9_next_4h_color/paper_forecasts"):
    close_h=(now//HOUR)*HOUR
    if now-close_h<10*60 or now-close_h>59*60:
        raise ValueError("OUTSIDE_10_TO_59_MINUTE_FRESH_1H_WINDOW")
    low1=close_h-HISTORY_1H*HOUR
    lowd=(close_h//DAY-HISTORY_D)*DAY
    one,hash1=get_group("1hour",low1,now,key,fetch)
    daily,hashd=get_group("daily",lowd,now,key,fetch)
    out={}
    for s in SYMBOLS:
        h=one[s]
        d=daily[s]
        if (len(h)!=HISTORY_1H or h[0]["t"]!=low1 or
            h[-1]["t"]+HOUR!=close_h or
            any(x["t"]!=low1+i*HOUR for i,x in enumerate(h))):
            raise ValueError("MISSING_OR_STALE_CLOSED_1H_"+s)
        if len(d)<205 or d[-1]["t"]+DAY!=(close_h//DAY)*DAY or any(
             b["t"]+DAY!=d[i+1]["t"] for i,b in enumerate(d[:-1])):
            raise ValueError("STALE_OR_MISSING_DAILY_"+s)
        if not verify_daily_vs_hours(h,d,now):
            raise ValueError("DAILY_1H_RECONCILIATION_UNAVAILABLE_"+s)
        four=one_4h_history(h,close_h)
        if len(four)<200 or four[-1]["t"]+FOUR!=(close_h//FOUR)*FOUR:
            raise ValueError("MISSING_COMPLETED_4H_"+s)
        for z,n in ((h,HOUR),(four,FOUR),(d,DAY)):
            for a in z:a["_seconds"]=n
        r1=close_indicators(h)
        r4=close_indicators(four)
        rd=close_indicators(d)
        delta=sum(2*x["tbv"]-x["v"] for x in h[-24:])
        volume=sum(x["v"] for x in h[-24:])
        out[s]={
           "1H":r1,"4H":r4,"Daily":rd,
           "last24HCoinalyzeTakerDeltaProxy":round(delta,6),
           "last24HTakerDeltaShare":round(delta/volume,6) if volume else None,
           "Daily4HAgreement":rd["context"]==r4["context"],
           "contextOnlyNotANewPrestartDirectionForecast":True}
    active=close_h//FOUR*FOUR
    pending=active+FOUR
    result={
      "status":"V9_HOURLY_OBSERVATION_VERIFIED_PAPER_CONTEXT_ONLY",
      "observedAtUTC":iso(now),
      "closed1HUTC":iso(close_h),"closed1HTSI":tsi(close_h),
      "active4HStartUTC":iso(active),
      "next4HStartUTC":iso(pending),
      "assets":out,
      "active4HPriorOfficialPrediction":read_locked(ledger_dir,active),
      "next4HPriorOfficialPrediction":read_locked(ledger_dir,pending),
      "sourceSHA256":{"oneHour":hash1,"daily":hashd},
      "officialNext4HColorRequiresBeforeStartRecord":True,
      "doesNotRepaintOrBackfillMissing4HForecasts":True,
      "modelConfidenceUncalibrated":True,
      "realOrders":False,
      "productionModified":False}
    return result


def readable(report):
    lines=[
      "# V9 SAATLİK BTC → ETH → SOL (paper gözlem)",
      "",
      f"**Doğrulanmış 1H kapanışı:** {report['closed1HTSI']}. "
      "Her satır gerçek tamamlanmış mumdur. **Resmî V9 4H tahmini yalnız mum açılmadan kaydedilmişse geçerlidir.**",
      "",
      "| Varlık | 1H kapanış | 1H rengi | 1H RSI | 4H yön bağlamı | Daily yön bağlamı |",
      "|---|---:|---|---:|---|---|"]
    for s,details in report["assets"].items():
        h=details["1H"]
        lines.append(f"| {s} | {h['OHLCV']['close']:,.4f} | {h['body']} | "
                     f"{h['RSI14']:.2f} | {details['4H']['context']} | "
                     f"{details['Daily']['context']} |")
    lines+=["","## Önceden kaydedilmiş 4H yön tahmini"]
    for label,key in (("Aktif 4H","active4HPriorOfficialPrediction"),
                      ("Sonraki 4H","next4HPriorOfficialPrediction")):
        k=report[key]
        lines.append(f"- **{label}** ({k['target4HStartUTC']}): "
                     +((", ".join(f"{s}: {v['direction']}" for s,v in k["assetForecasts"].items())
                         +f" — kayıt: {k['decisionCapturedUTC']}")
                        if k["status"]=="FROZEN_BEFORE_START_PAPER_FORECAST_RECORDED"
                        else "**ÖNCEDEN KAYIT YOK — sinyal yok.**"))
    lines+=["","**Uyarı:** Saatlik EMA/RSI/MACD, CVD vekili ve Daily/4H trend bağlamı "
            "bir sonraki 4H rengini kanıtlamaz. Yeşil/kırmızı doğruluk yalnız ayrı "
            "önceden kilitlenmiş 4H tahmin dosyaları için sayılır. İşlem yok.",""]
    return "\n".join(lines)


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--output-dir",default="forward/v9_next_4h_color/hourly")
    p.add_argument("--ledger-dir",default="forward/v9_next_4h_color/paper_forecasts")
    a=p.parse_args()
    key=(os.getenv("ETH_V7_COINALYZE_API_KEY") or
         os.getenv("SOL_V8_COINALYZE_API_KEY") or
         os.getenv("COINALYZE_API_KEY") or "").strip()
    if not key:raise ValueError("MISSING_COINALYZE_READONLY_KEY")
    now=int(datetime.now(timezone.utc).timestamp())
    end=(now//HOUR)*HOUR
    d=Path(a.output_dir)
    name=datetime.fromtimestamp(end,timezone.utc).strftime("%Y-%m-%dT%H-00Z")
    f=d/"snapshots"/(name+".json")
    if f.exists():
        print("V9_HOURLY_OBSERVATION_ALREADY_EXISTS_IMMUTABLE",f)
        return
    result=status_at(now,key,ledger_dir=a.ledger_dir)
    f.parent.mkdir(parents=True,exist_ok=True)
    f.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    (d/"latest.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    md=readable(result)
    (d/"latest.md").write_text(md)
    (d/"snapshots"/(name+".md")).write_text(md)
    print("V9_HOURLY_BTC_ETH_SOL_OBSERVATION_CAPTURED",result["closed1HUTC"],
          {s:z["1H"]["body"] for s,z in result["assets"].items()},flush=True)


if __name__=="__main__":
    main()
