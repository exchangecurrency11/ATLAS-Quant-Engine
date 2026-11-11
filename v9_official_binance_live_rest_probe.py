#!/usr/bin/env python3
"""Read-only official Binance USD-M REST 1H trades/taker field access probe.

Do NOT use API keys, send orders, score new V9 predictions, or fabricate
source-parity if geo-blocked. Public GET /fapi/v1/klines only.
"""
import argparse,json,os,urllib.parse,urllib.request,urllib.error
from pathlib import Path
from datetime import datetime,timezone
from v9_next_4h_color_research import SYMBOLS,iso,HOUR
from v9_next4h_prestart_paper_capture import get_group

BASE="https://fapi.binance.com/fapi/v1/klines"


def official_hours(symbol,close,limit=8,fetch=None):
    if close%HOUR or not 1<=limit<=1000:
        raise ValueError("INVALID_CLOSED_HOURLY_RANGE")
    query=urllib.parse.urlencode({
      "symbol":symbol,"interval":"1h",
      "startTime":(close-limit*HOUR)*1000,
      "endTime":close*1000-1,"limit":limit})
    if fetch:
        raw=fetch(BASE+"?"+query)
    else:
        req=urllib.request.Request(BASE+"?"+query,headers={
            "Accept":"application/json",
            "User-Agent":"V9-Official-Binance-USD-M-ReadOnly-Data-Audit/1.0"})
        with urllib.request.urlopen(req,timeout=25) as response:
            if response.status!=200:raise ValueError("BINANCE_REST_NON_200")
            raw=response.read(6_000_000)
    if isinstance(raw,bytes):records=json.loads(raw)
    elif isinstance(raw,str):records=json.loads(raw)
    else:records=raw
    if not isinstance(records,list) or len(records)!=limit:
        raise ValueError("BINANCE_REST_MISSING_OR_INCOMPLETE_1H")
    result=[]
    for i,row in enumerate(records):
        if not isinstance(row,list) or len(row)<11:
            raise ValueError("BINANCE_REST_MALFORMED")
        t=int(row[0])//1000
        if t!=close-(limit-i)*HOUR or int(row[6])//1000<t+HOUR-1:
            raise ValueError("BINANCE_REST_INCONSISTENT_OPEN_CLOSE")
        obj={"t":t,"o":float(row[1]),"h":float(row[2]),
             "l":float(row[3]),"c":float(row[4]),"v":float(row[5]),
             "trades":int(row[8]),"tbv":float(row[9])}
        if not (0<obj["l"]<=min(obj["o"],obj["c"])<=max(obj["o"],obj["c"])<=obj["h"]
                and obj["v"]>=obj["tbv"]>=0 and obj["trades"]>=0):
            raise ValueError("BINANCE_REST_BAD_PRICE_OR_FLOW")
        result.append(obj)
    return result


def run(close,fetch=None,provider_fetch=None):
    report={"status":"V9_OFFICIAL_BINANCE_LIVE_REST_ACCESS_PROBE_NO_ORDERS",
            "asOfClosedHourUTC":iso(close),"assets":{},
            "allThreeOfficialRESTSourceAvailable":False,
            "sourceUnavailableDoesNotAuthorizeUnverifiedTX":True,
            "alertsEnabled":False,"orders":False,"productionModified":False}
    try:
        for symbol in SYMBOLS:
            try:
                records=official_hours(symbol,close,fetch=fetch)
                report["assets"][symbol]={
                  "status":"OFFICIAL_BINANCE_8_COMPLETE_1H_CANDLES",
                  "bars":len(records),"lastClosed1HUTC":iso(records[-1]["t"]+HOUR),
                  "sumTradeCountLast8H":sum(x["trades"] for x in records),
                  "lastHourTakerBuyVolume":records[-1]["tbv"],
                  "lastHourVolume":records[-1]["v"]}
            except (ValueError,OSError,urllib.error.HTTPError,urllib.error.URLError,
                    TimeoutError,KeyError,IndexError,json.JSONDecodeError) as e:
                report["assets"][symbol]={
                   "status":"OFFICIAL_BINANCE_REST_UNAVAILABLE_DO_NOT_REPLACE_TRADE_COUNT",
                   "errorType":type(e).__name__,
                   "httpCode":getattr(e,"code",None)}
        report["allThreeOfficialRESTSourceAvailable"]=all(
            x["status"]=="OFFICIAL_BINANCE_8_COMPLETE_1H_CANDLES"
            for x in report["assets"].values())
    except Exception:
        # no unconstrained network fallbacks and never infer parity
        raise
    return report


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--output",default="forward/v9_source_parity/binance_live_rest_access.json")
    a=p.parse_args()
    now=int(datetime.now(timezone.utc).timestamp())
    report=run(now//HOUR*HOUR)
    out=Path(a.output);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("V9_OFFICIAL_BINANCE_PUBLIC_LIVE_REST_ONLY",
          report["allThreeOfficialRESTSourceAvailable"],
          {s:v["status"] for s,v in report["assets"].items()},flush=True)


if __name__=="__main__":
    main()
