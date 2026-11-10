#!/usr/bin/env python3
"""Retrospective Binance SHA-verified SOL taker buy vs Coinalyze bv comparison.
NO SIGNALS, NO ORDERS. Historical Binance archive was published AFTER the day.
"""
import argparse
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import median
from sol_derivatives_quality_audit import sha_archive, parse_kline
from sol_v8_derivatives_probe import request_json, one_symbol, number, SYMBOL, HOUR, iso

COIN="SOLUSDT"
TOL_TOTAL=0.02
TOL_BUY=0.02
TOL_SHARE=0.02
TOL_CLOSE=0.002


def provider_rows(data, begin, end):
    hist=one_symbol(data, history=True)
    rows={}
    previous=None
    for bar in hist:
        if not isinstance(bar,dict) or type(bar.get("t")) is not int:
            raise ValueError("BAD_PROVIDER_CANDLE_TIME")
        t=bar["t"]
        if t%HOUR or (previous is not None and t<=previous):
            raise ValueError("DUPLICATE_OR_UNALIGNED_PROVIDER_HOURS")
        previous=t
        if begin<=t<end:
            v=number(bar.get("v"),"PROVIDER_V",positive=True)
            bv=number(bar.get("bv"),"PROVIDER_BV")
            close=number(bar.get("c"),"PROVIDER_C",positive=True)
            if not 0<=bv<=v:
                raise ValueError("IMPOSSIBLE_PROVIDER_BV")
            rows[t]={"v":v,"bv":bv,"c":close}
    return rows


def compare(provider, reference, begin, hours):
    missing=[]
    measured=[]
    for i in range(hours):
        t=begin+i*HOUR
        a=provider.get(t)
        b=reference.get(t)
        if a is None or b is None:
            missing.append({"hourUTC":iso(t),"providerMissing":a is None,
                            "referenceMissing":b is None})
            continue
        if b["v"]<=0 or b["takerBuyBase"]<=0:
            raise ValueError("INVALID_REFERENCE_VOLUME")
        d_total=abs(a["v"]-b["v"])/b["v"]
        d_buy=abs(a["bv"]-b["takerBuyBase"])/b["takerBuyBase"]
        d_share=abs(a["bv"]/a["v"]-b["takerBuyBase"]/b["v"])
        d_close=abs(a["c"]-b["c"])/b["c"]
        passed=(d_total<=TOL_TOTAL and d_buy<=TOL_BUY
                and d_share<=TOL_SHARE and d_close<=TOL_CLOSE)
        measured.append({"utc":iso(t),"totalRel":round(d_total,8),
                         "buyRel":round(d_buy,8),"shareAbs":round(d_share,8),
                         "closeRel":round(d_close,8),
                         "binanceBuy":round(b["takerBuyBase"],4),
                         "coinalyzeBV":round(a["bv"],4),
                         "passed":passed})
    def summary(k):
        vals=[x[k] for x in measured]
        return {"median":round(median(vals),8) if vals else None,
                "max":round(max(vals),8) if vals else None}
    valid=sum(x["passed"] for x in measured)
    return {"expectedHours":hours,"pairedHours":len(measured),
            "matchedHours":valid,"mismatchedHours":len(measured)-valid,
            "missingHours":len(missing),
            "totalRel":summary("totalRel"),"buyRel":summary("buyRel"),
            "shareAbs":summary("shareAbs"),"closeRel":summary("closeRel"),
            "missingSamples":missing[:12],
            "discrepancies":sorted((x for x in measured if not x["passed"]),
                                   key=lambda x:x["buyRel"],reverse=True)[:12]}


def audit(start,end,key,fetch=request_json,load_archive=sha_archive):
    a=datetime.strptime(start,"%Y-%m-%d").replace(tzinfo=timezone.utc)
    b=datetime.strptime(end,"%Y-%m-%d").replace(tzinfo=timezone.utc)
    days=(b-a).days+1
    if not 1<=days<=10 or b.date()>=datetime.now(timezone.utc).date():
        raise ValueError("ONLY_COMPLETED_DAYS_1_TO_10")
    begin=int(a.timestamp())
    end_exclusive=int((b+timedelta(days=1)).timestamp())
    out={"status":"SOURCE_UNAVAILABLE_NO_SIGNAL",
         "mode":"SOL_V8_BV_TAKER_HISTORICAL_RECONCILIATION_NO_ORDERS",
         "symbol":SYMBOL,"exchange":"Binance",
         "periodUTC":{"start":start,"end":end},"isRetrospective":True,
         "noLiveTradingUse":True,"brokerOrders":False,
         "productionSystemModified":False,"liveSignalEnabled":False,
         "retrievedAtUTC":datetime.now(timezone.utc).isoformat()}
    try:
        if not key: raise ValueError("MISSING_COINALYZE_API_KEY")
        data,hash_=fetch("ohlcv-history",
            {"symbols":SYMBOL,"interval":"1hour",
             "from":begin,"to":end_exclusive},key)
        provider=provider_rows(data,begin,end_exclusive)
        reference={}
        proofs=[]
        for i in range(days):
            day=(a+timedelta(days=i)).strftime("%Y-%m-%d")
            path=f"daily/klines/{COIN}/1h/{COIN}-1h-{day}.zip"
            rows,proof=load_archive(path)
            bars,errors,n=parse_kline(rows,day,"1h")
            if errors or len(bars)!=n:
                raise ValueError("BINANCE_DAILY_ARCHIVE_INVALID_"+day)
            if set(reference)&set(bars):
                raise ValueError("DUPLICATE_REFERENCE_HOURS")
            reference.update(bars)
            proofs.append(proof)
        result=compare(provider,reference,begin,24*days)
        out.update({"comparison":result,
            "sourceSHA256":{"coinalyzeOHLCV":hash_,
                            "binanceVerifiedZIPs":proofs},
            "predeclaredTolerance":{"volumeRelative":TOL_TOTAL,
                                    "buyRelative":TOL_BUY,
                                    "buyShareAbsolute":TOL_SHARE,
                                    "closeRelative":TOL_CLOSE},
            "status":("RECONCILED_RESEARCH_ONLY"
                      if result["matchedHours"]==result["expectedHours"]
                      and result["missingHours"]==0
                      else "DATA_DISCREPANCY_NO_SIGNAL")})
    except (OSError,RuntimeError,ValueError,TypeError,KeyError,IndexError) as e:
        out["status"]="SOURCE_UNAVAILABLE_NO_SIGNAL"
        out["reason"]=str(e)[:180]
    return out


def render(result):
    lines=["# SOL V8 - Coinalyze buy volume vs Binance official taker buy",
           "", "Retrospective only. Not a live signal or trade validation.",
           "", "Status: "+result["status"],""]
    if "comparison" in result:
        c=result["comparison"]
        for k in ("expectedHours","pairedHours","matchedHours",
                  "mismatchedHours","missingHours","totalRel","buyRel",
                  "shareAbs","closeRel"):
            lines.append("- "+k+": "+str(c[k]))
        lines+=["","Largest mismatches:"]
        for row in c["discrepancies"][:8]:
            lines.append("- "+str(row))
    else:
        lines.append("Reason: "+result.get("reason","unavailable"))
    lines+=["","No changes to live filters, orders or BTC/SOL production."]
    return "\n".join(lines)+"\n"


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--start",default="2026-11-01")
    p.add_argument("--end",default="2026-11-09")
    p.add_argument("--output",required=True)
    p.add_argument("--markdown",required=True)
    args=p.parse_args()
    key=(os.environ.get("SOL_V8_COINALYZE_API_KEY")
         or os.environ.get("ETH_V7_COINALYZE_API_KEY")
         or os.environ.get("COINALYZE_API_KEY") or "").strip()
    res=audit(args.start,args.end,key)
    path=Path(args.output)
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(res,indent=2)+"\n",encoding="utf-8")
    text=Path(args.markdown)
    text.parent.mkdir(parents=True,exist_ok=True)
    text.write_text(render(res),encoding="utf-8")
    print("SOL_V8_BV_TAKER",res["status"],
          res.get("comparison",{}).get("matchedHours"),
          res.get("comparison",{}).get("expectedHours"),
          res.get("reason",""))
    if res["status"]!="RECONCILED_RESEARCH_ONLY":
        raise SystemExit(1)


if __name__=="__main__":
    main()
