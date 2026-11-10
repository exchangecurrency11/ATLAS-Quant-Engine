#!/usr/bin/env python3
"""Independent ETHUSDT Binance USD-M V7 HOURLY paper-forward observer.

Separate from BTC/SOL production and V7 files; public REST GET only.
Strict point-in-time data validation: closed 1H/4H/1D, 250 continuous
candles each, cross-timeframe OHLCV reconciliation and source hashes.
Never sends orders, modifies live systems or fabricates no-signal hours.
If venue API is blocked (e.g. HTTP 451), status is SOURCE_UNAVAILABLE.
"""
import argparse
import hashlib
import json
import math
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from backtest_retest_long_v4 import ema, indicators, bias, replay_pair
from market_structure import analyze, average_true_range
from signal_quality_v7 import evaluate_bos_quality, evaluate_retest_quality
from v7_forward_observer import latest_events

SYMBOL="ETHUSDT"
RESEARCH_PAIR="ETHUSDT_PERP.A"
URL="https://fapi.binance.com/fapi/v1/klines"
PERIODS={"1hour":("1h",3600,750),"4hour":("4h",14400,300),
         "daily":("1d",86400,300)}
HOUR=3600


def iso(seconds):
    return datetime.fromtimestamp(seconds,timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def epoch(value):
    value=datetime.fromisoformat(value.replace("Z","+00:00"))
    if value.tzinfo is None or value.utcoffset().total_seconds()!=0:
        raise ValueError("Must be UTC timestamp")
    return int(value.timestamp())


def check_time(target,now):
    if target%HOUR or not 10*60 <= now-target < HOUR:
        raise ValueError("Target must be latest closed 1H, observed between +10 and +59 minutes")


def public_klines(interval,limit):
    # No fallback to spot or another exchange. No credentials or trading.
    qs=urllib.parse.urlencode({"symbol":SYMBOL,"interval":interval,"limit":limit})
    req=urllib.request.Request(URL+"?"+qs,method="GET",
                                headers={"User-Agent":"ETH-V7-paper-only/1.0",
                                         "Accept":"application/json"})
    try:
        with urllib.request.urlopen(req,timeout=18) as result:
            if result.status!=200:
                raise ValueError("Non-200 ETH USD-M source HTTP response")
            blob=result.read(900000)
    except urllib.error.HTTPError as e:
        raise RuntimeError("BINANCE_USDM_HTTP_"+str(e.code)) from e
    except (urllib.error.URLError,TimeoutError) as e:
        raise RuntimeError("BINANCE_USDM_NETWORK_UNAVAILABLE_"+type(e).__name__) from e
    try:
        rows=json.loads(blob)
    except (TypeError,ValueError) as e:
        raise ValueError("Invalid ETH Binance Kline JSON") from e
    return rows,hashlib.sha256(blob).hexdigest()


def parse_closed_klines(raw,timeframe,target):
    if timeframe not in PERIODS:
        raise ValueError("Unsupported ETH timeframe")
    seconds=PERIODS[timeframe][1]
    target_close=(target//seconds)*seconds
    if not isinstance(raw,list):
        raise ValueError("Binance returned non-list OHLCV")
    rows=[]
    previous=None
    for item in raw:
        if not isinstance(item,list) or len(item)<7:
            raise ValueError("Malformed Binance Futures kline")
        open_ms,close_ms=int(item[0]),int(item[6])
        if open_ms%1000 or open_ms//1000%seconds or close_ms!=open_ms+seconds*1000-1:
            raise ValueError("Binance ETH candle timestamp/period invalid")
        t=open_ms//1000
        if previous is not None and t<=previous:
            raise ValueError("Unordered or duplicate ETH candles")
        previous=t
        o,h,l,c,v=(float(x) for x in item[1:6])
        if (not all(math.isfinite(x) for x in (o,h,l,c,v)) or
                l<=0 or v<0 or l>min(o,c) or h<max(o,c)):
            raise ValueError("ETH invalid OHLCV")
        if t+seconds<=target_close:
            rows.append({"t":t,"o":o,"h":h,"l":l,"c":c,"v":v})
    if len(rows)<250:
        raise ValueError("Insufficient ETH 250 closed "+timeframe+" bars")
    if rows[-1]["t"]+seconds!=target_close:
        raise ValueError("ETH "+timeframe+" stale or ahead of expected close")
    if any(rows[i]["t"]-rows[i-1]["t"]!=seconds for i in range(len(rows)-249,len(rows))):
        raise ValueError("ETH "+timeframe+" recent 250 candles not continuous")
    return rows


def same_price(a,b):
    return abs(a-b)<=max(0.000001,abs(a)*0.000002)


def reconcile(base,sub,seconds):
    """Compare last five 4H/1D bars with aggregated actual closed 1H bars."""
    by_hour={bar["t"]:bar for bar in base}
    checked=0
    for candle in sub[-5:]:
        t=candle["t"]
        hours=[by_hour.get(t+i*HOUR) for i in range(seconds//HOUR)]
        if any(bar is None for bar in hours):
            raise ValueError("No overlapping 1H history for ETH "+str(seconds))
        expected={
            "o":hours[0]["o"],"h":max(x["h"] for x in hours),
            "l":min(x["l"] for x in hours),"c":hours[-1]["c"],
            "v":sum(x["v"] for x in hours)
        }
        for k,v in expected.items():
            if not same_price(float(v),float(candle[k])):
                raise ValueError("Binance ETH timeframe OHLCV divergence "+str(seconds)+" "+k)
        checked+=1
    return checked


def validate_sources(raw_map,target,now):
    check_time(target,now)
    raw={}
    sha={}
    for tf in PERIODS:
        if tf not in raw_map:
            raise ValueError("ETH missing timeframe "+tf)
        data,signature=raw_map[tf]
        raw[tf]=parse_closed_klines(data,tf,target)
        sha[tf]=signature
    cross={"1H_matches_4H":reconcile(raw["1hour"],raw["4hour"],14400),
           "1H_matches_daily":reconcile(raw["1hour"],raw["daily"],86400)}
    return raw,sha,cross


def context_for_eth(h,f,d,target):
    bars=h[-250:]
    structural=analyze(bars,"1hour",as_of=target)
    events=[{**e,"knownAtUTC":iso(target)}
            for e in structural.get("structure",[]) if int(e["at"])+HOUR==target]
    bos=[e for e in events if e["event"]=="BOS"]
    bars_by_tf={"1hour":h,"4hour":f,"daily":d}
    rows={}
    votes={}
    for tf,candles in bars_by_tf.items():
        ind=indicators(candles)
        if not ind:
            raise ValueError("Missing ETH indicators "+tf)
        close=candles[-1]["c"]
        score=sum([1 if close>ind["EMA20"] else -1 if close<ind["EMA20"] else 0,
                   1 if close>ind["EMA50"] else -1 if close<ind["EMA50"] else 0,
                   1 if ind["hist"]>0 else -1 if ind["hist"]<0 else 0,
                   1 if ind["RSI14"]>50 else -1 if ind["RSI14"]<50 else 0])
        direction="bullish" if score>=3 else "bearish" if score<=-3 else "mixed"
        votes[tf]=direction
        prior=candles[-2]["v"]
        rows[tf]={
            "closeTimeUTC":iso(candles[-1]["t"]+PERIODS[tf][1]),
            "candle":{
                "open":close if False else candles[-1]["o"],
                "high":candles[-1]["h"],"low":candles[-1]["l"],
                "close":close,"volume":candles[-1]["v"],
                "volumeChangePct":(100*(candles[-1]["v"]/prior-1)
                                   if prior>0 else None)
            },
            "indicators":{
                "RSI14":round(ind["RSI14"],4),
                "EMA20":round(ind["EMA20"],4),
                "EMA50":round(ind["EMA50"],4),
                "EMA200":round(ema([b["c"] for b in candles],200),4),
                "MACDHistogram":round(ind["hist"],6),
            },
            "directionVotes":{"label":direction,"score":score},
        }
    direction_agree=votes["4hour"]==votes["daily"] and votes["daily"]!="mixed"
    ind=indicators(h)
    quality=[]
    vol20=[x["v"] for x in bars[-21:-1]]
    rvol=bars[-1]["v"]/(sum(vol20)/20) if sum(vol20)>0 else None
    for e in bos:
        side=e["direction"]
        quality.append({
            "direction":side,"level":e["brokenLevel"],
            "gate":evaluate_bos_quality(bars,e,ind),
            "higherTFalignedWithBOS":direction_agree and votes["daily"]==side,
            "momentumAlignedWithBOS":(
                (ind["RSI14"]>50 and ind["hist"]>0) if side=="bullish"
                else (ind["RSI14"]<50 and ind["hist"]<0)),
            "previousHourVolumeIncrease20Pct": (
                rows["1hour"]["candle"]["volumeChangePct"] is not None
                and rows["1hour"]["candle"]["volumeChangePct"]>=20),
        })
    explanation=(
        "NO_NEW_1H_BOS" if not bos else
        "HIGHER_TIMEFRAMES_NOT_ALIGNED" if any(not e["higherTFalignedWithBOS"] for e in quality) else
        "BOS_QUALITY_FILTER_REJECTED" if any(not e["gate"]["passed"] for e in quality) else
        "BOS_PRESENT_WAIT_FOR_SEPARATE_RETEST"
    )
    return {
        "checkedClosed1HUTC":iso(target),"timeframes":rows,
        "newStructureEventsAtClose":events,"newBOSCount":len(bos),
        "bosQualityBreakdown":quality,
        "higherTimeframesAgree":direction_agree,
        "atr14_1H":round(average_true_range(bars,len(bars)-1,14),8),
        "relativeVolume20_1H":round(rvol,5) if rvol is not None else None,
        "noSignalExplanation":explanation,
        "caution":"BOS is not an entry; retest and next-open are required.",
    }


def build_observation(raw_map,target,now):
    rows,hashes,cross=validate_sources(raw_map,target,now)
    h,f,d=(rows[tf] for tf in ("1hour","4hour","daily"))
    variants={
        "V4_baseline":{},
        "V7_signal_filter":{"bos_quality_filter":evaluate_bos_quality},
        "V7_signal_plus_retest":{
            "bos_quality_filter":evaluate_bos_quality,
            "retest_quality_filter":evaluate_retest_quality},
    }
    outcomes={}
    for name,opts in variants.items():
        simulation=replay_pair(h,f,d,as_of=target,**opts)
        outcomes[name]=latest_events(simulation,target)
    return {
        "status":"VERIFIED_PAPER_OBSERVATION",
        "marketContext":{RESEARCH_PAIR:context_for_eth(h,f,d,target)},
        "results":{RESEARCH_PAIR:outcomes},
        "dataSource":"Binance official USD-M futures public GET /fapi/v1/klines",
        "sourceSHA256":hashes,
        "crossTimeframeOHLCVVerifiedLast5":cross,
    }


def format_report(s):
    lines=[
        "# ETHUSDT — V7 Hourly Paper Forward (independent)",
        "",
        "**Hedef 1H kapanış (UTC):** "+s["targetClosed1HUTC"],
        "**Gözlem zamanı (UTC):** "+s["observedAtUTC"],
        "**Durum:** "+s["status"],
        "**Kaynak:** Binance official USD-M futures REST Klines (read-only)",
        "**Emir:** YOK. Gerçek fill veya getiri iddiası yok.",
        "",
    ]
    if s["status"]!="VERIFIED_PAPER_OBSERVATION":
        return "\n".join(lines+["**SİNYAL YOK:** "+s.get("rejectionReason","data unavailable"),""])
    context=s["marketContext"][RESEARCH_PAIR]
    lines+=["| TF | Kapanış UTC | Close | RSI14 | MACD Hist | EMA20 / EMA50 / EMA200 | Bias |",
             "|---|---|---:|---:|---:|---|---|"]
    for tf in ("1hour","4hour","daily"):
        z=context["timeframes"][tf]
        c=z["candle"];i=z["indicators"]
        lines.append(
            f"| {tf} | {z['closeTimeUTC']} | {c['close']:.4f} | "
            f"{i['RSI14']:.2f} | {i['MACDHistogram']:+.5f} | "
            f"{i['EMA20']:.4f} / {i['EMA50']:.4f} / {i['EMA200']:.4f} | "
            f"{z['directionVotes']['label']} |"
        )
    lines+=["","**RSI / ATR / RVOL:** "+str(context["atr14_1H"])+
             " ATR14; "+str(context["relativeVolume20_1H"])+" RVOL20",
             "**1H BOS:** "+str(context["newBOSCount"]),
             "**Sinyal açıklaması:** "+context["noSignalExplanation"],""]
    for q in context["bosQualityBreakdown"]:
        lines.append("- "+q["direction"]+" BOS "+str(q["level"])+
                     " | V7="+str(q["gate"]["passed"])+
                     " | neden="+",".join(q["gate"]["reasons"])+
                     " | 4H/Daily uyumu="+str(q["higherTFalignedWithBOS"]))
    lines+=["","| Paper varyant | Yeni uyarı | Çıkış | Açık pozisyon |",
            "|---|---:|---:|---|"]
    for name,out in s["results"][RESEARCH_PAIR].items():
        lines.append("| "+name+" | "+str(len(out["newWatchAtThisClose"]))+
                     " | "+str(len(out["paperTradeExitsObservedAtThisClose"]))+
                     " | "+("Var" if out["currentPaperState"].get("openHypotheticalPosition")
                             else "Yok")+" |")
    lines+=["","**Sınır:** Yalnız saatlik kapanıştan sonra veri doğrulanan ETH "
            "paper araştırması. Finansman, gerçek emir icrası, kayma ve likidasyon "
            "modellendiği iddia edilmez.",""]
    return "\n".join(lines)


def run(output,report,target,now):
    result={
        "mode":"ETH_V7_INDEPENDENT_PAPER_FORWARD_NO_ORDERS",
        "symbol":RESEARCH_PAIR,"exchange":"Binance",
        "observedAtUTC":iso(now),"targetClosed1HUTC":iso(target),
        "status":"SOURCE_UNAVAILABLE_NO_SIGNAL",
        "brokerOrders":False,"productionSystemModified":False,
        "paperForwardObservation":False,
    }
    try:
        check_time(target,now)
        raw={}
        for tf,(binance_interval,_,limit) in PERIODS.items():
            raw[tf]=public_klines(binance_interval,limit)
        result.update(build_observation(raw,target,now))
        result["paperForwardObservation"]=True
    except (RuntimeError,ValueError,TypeError,KeyError,IndexError,ZeroDivisionError) as e:
        result["status"]="SOURCE_UNAVAILABLE_NO_SIGNAL"
        result["rejectionReason"]=type(e).__name__+": "+str(e)[:220]
        result.pop("results",None)
        result.pop("marketContext",None)
    Path(output).parent.mkdir(parents=True,exist_ok=True)
    Path(report).parent.mkdir(parents=True,exist_ok=True)
    Path(output).write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    Path(report).write_text(format_report(result),encoding="utf-8")
    print("ETH V7",result["status"],result["targetClosed1HUTC"],
          result.get("rejectionReason",""))
    return result


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--output",required=True)
    p.add_argument("--report",required=True)
    p.add_argument("--now-utc",default=None,help="For deterministic tests only")
    p.add_argument("--target-utc",default=None,help="Latest completed 1H UTC")
    args=p.parse_args()
    now=epoch(args.now_utc) if args.now_utc else int(datetime.now(timezone.utc).timestamp())
    target=epoch(args.target_utc) if args.target_utc else now//HOUR*HOUR
    run(args.output,args.report,target,now)


if __name__=="__main__":
    main()
