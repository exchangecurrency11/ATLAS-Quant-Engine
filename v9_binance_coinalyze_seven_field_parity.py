#!/usr/bin/env python3
"""Independent 3-asset Binance 1H USD-M archive vs Coinalyze 1H field parity.

Proof uses SHA256-verified Binance OFFICIAL daily ZIP, not V7 Worker.
Coinalyze source is separate read-only API, same contract/hour. The fields
under examination: o,h,l,c,v, bv->Binance taker-buy base, tx->Binance
number of trades. No price or buy flow field is assumed equivalent.

Strict 24 closed 1H candles per UTC day and asset, exact timestamps.
A mismatch is recorded, NOT silently zero-filled or claimed verified.
Failures block promotion of *feature portability*, not paper observation;
never place orders, notifications or update frozen V9 model.
"""
import argparse,csv,json,io,math,os
from datetime import date,datetime,timezone
from hashlib import sha256
from zipfile import ZipFile
from pathlib import Path

from download_binance_um_history import get
from v9_next4h_prestart_paper_capture import (
    get_group,EXCHANGE_SYMBOLS,HOUR,SYMBOLS)
from v9_next_4h_color_research import iso

BASE="https://data.binance.vision/data/futures/um/daily/klines"
FIELDS=("o","h","l","c","v","tbv","trades")
PRICE_TOL_REL=1e-6
VOLUME_TOL_REL=0.002
TX_STRICT_EQUAL=True


def day_bound(day):
    d=date.fromisoformat(day)
    t=int(datetime(d.year,d.month,d.day,tzinfo=timezone.utc).timestamp())
    return t,t+86400


def checked_official_zip(symbol,day,download=get):
    start,end=day_bound(day)
    url=f"{BASE}/{symbol}/1h/{symbol}-1h-{day}.zip"
    content=download(url,max_size=600000)
    expected=download(url+".CHECKSUM",max_size=2048).decode("utf-8-sig").strip().split()[0].lower()
    digest=sha256(content).hexdigest()
    if expected!=digest or len(expected)!=64:
        raise ValueError("BINANCE_OFFICIAL_DAILY_SHA256_MISMATCH")
    with ZipFile(io.BytesIO(content)) as f:
        names=[n for n in f.namelist() if n.endswith(".csv")]
        if len(names)!=1 or names[0].split("/")[-1]!=f"{symbol}-1h-{day}.csv":
            raise ValueError("BINANCE_OFFICIAL_DAILY_CSV_UNEXPECTED")
        if f.getinfo(names[0]).file_size>500000:
            raise ValueError("BINANCE_OFFICIAL_DAILY_CSV_TOO_LARGE")
        with f.open(names[0]) as b:
            rows=[]
            for line in csv.reader(io.TextIOWrapper(b,encoding="utf-8-sig")):
                if not line or line[0].strip().lower() in ("open time","open_time"):
                    continue
                if len(line)<11:
                    raise ValueError("BINANCE_OFFICIAL_FLOW_FIELDS_MISSING")
                raw_t=int(line[0])
                t=(raw_t//1000000 if raw_t>10**14
                   else raw_t//1000 if raw_t>10**11 else raw_t)
                vals={k:float(line[pos]) for k,pos in
                      (("o",1),("h",2),("l",3),("c",4),("v",5),("tbv",9))}
                vals["trades"]=int(line[8])
                if not all(math.isfinite(x) for x in vals.values()):
                    raise ValueError("BINANCE_OFFICIAL_NONFINITE_CANDLE")
                if not (0<vals["l"]<=min(vals["o"],vals["c"])
                        <=max(vals["o"],vals["c"])<=vals["h"]):
                    raise ValueError("BINANCE_OFFICIAL_IMPOSSIBLE_OHLC")
                rows.append({"t":t,**vals})
    if len(rows)!=24 or any(x["t"]!=start+i*HOUR for i,x in enumerate(rows)):
        raise ValueError("BINANCE_OFFICIAL_DAILY_NOT_24_CONTIGUOUS")
    return rows,{"source":url,"sha256Verified":digest,
                 "24ClosedHours":True,"endUTC":iso(end)}


def close_enough(a,b,field):
    if field=="trades":
        return type(a) is int and type(b) is int and a==b
    if field in ("o","h","l","c"):
        return abs(a-b)<=max(1e-7,abs(a)*PRICE_TOL_REL)
    return abs(a-b)<=max(1e-7,abs(a)*VOLUME_TOL_REL)


def compare_pair(official,coinalyze):
    if len(official)!=24 or len(coinalyze)!=24:
        raise ValueError("SAME_24_HOURS_REQUIRED")
    mismatches={k:[] for k in FIELDS}
    maxima={k:0. for k in FIELDS}
    for i,(a,b) in enumerate(zip(official,coinalyze)):
        if a["t"]!=b["t"] or (i and a["t"]!=official[0]["t"]+i*HOUR):
            raise ValueError("PROVIDER_TIMESTAMPS_NOT_THE_SAME_HOUR")
        for field in FIELDS:
            if not close_enough(a[field],b[field],field):
                mismatches[field].append({
                   "atUTC":iso(a["t"]),"official":a[field],
                   "coinalyze":b[field],
                   "relativeDifferencePct":round(
                     abs(b[field]-a[field])/abs(a[field])*100,4)
                      if a[field]!=0 else None})
            if a[field]:
                maxima[field]=max(maxima[field],
                                  100*abs(b[field]-a[field])/abs(a[field]))
    return {"barsCompared":24,
            "mismatchesByField":{k:len(v) for k,v in mismatches.items()},
            "firstMismatchByField":{k:v[:2] for k,v in mismatches.items() if v},
            "maximumAbsoluteRelativeDifferencePct":{
                k:round(v,5) for k,v in maxima.items()},
            "priceOHLCParity":all(not mismatches[f] for f in ("o","h","l","c")),
            "totalVolumeParity":not bool(mismatches["v"]),
            "takerBuyBaseParity":not bool(mismatches["tbv"]),
            "coinalyzeTxEqualsOfficialNumberOfTrades":not bool(mismatches["trades"]),
            "allSevenFieldsParity":all(not v for v in mismatches.values())}


def audit(dates,key,source_fetch=None,official_fetch=None):
    all_results={}
    for day in dates:
        start,end=day_bound(day)
        # Existing Coinalyze read-only get_group enforces closed 1H,
        # source consistency and valid trade-count and taker-buy bounds.
        try:
            provider,hash_coinalyze=get_group("1hour",start,end,key,source_fetch)
            entry={"status":"COINALYZE_1H_AVAILABLE","coinalyzeSHA256":hash_coinalyze,
                   "symbols":{}}
            for sym in SYMBOLS:
                try:
                    orig,proof=checked_official_zip(sym,day,
                        download=official_fetch or get)
                    result=compare_pair(orig,provider[sym])
                    entry["symbols"][sym]={"status":
                         "SEVEN_FIELDS_MATCH" if result["allSevenFieldsParity"]
                         else "CROSS_SOURCE_FIELD_MISMATCH",
                         "official":proof,**result}
                except (ValueError,OSError,RuntimeError,KeyError,IndexError) as e:
                    entry["symbols"][sym]={
                       "status":"OFFICIAL_OR_PARITY_CHECK_UNAVAILABLE_NO_VERIFICATION",
                       "errorType":type(e).__name__,
                       "errorCategory":"SOURCE_UNAVAILABLE_OR_MALFORMED"}
        except (ValueError,OSError,RuntimeError,KeyError,IndexError) as e:
            entry={"status":"COINALYZE_1H_UNAVAILABLE_NO_VERIFICATION",
                   "errorType":type(e).__name__,
                   "errorCategory":"SOURCE_UNAVAILABLE_OR_MALFORMED",
                   "symbols":{}}
        all_results[day]=entry
    usable=[
      r for day in all_results.values()
      for r in day["symbols"].values()
      if "barsCompared" in r]
    per={}
    for symbol in SYMBOLS:
        checks=[
           day["symbols"][symbol]
           for day in all_results.values()
           if symbol in day["symbols"] and
              "barsCompared" in day["symbols"][symbol]]
        per[symbol]={
          "daysCompared":len(checks),
          "hourlyCandlesCompared":24*len(checks),
          "OHLCVMatchedEveryComparedHour":(
             all(z["priceOHLCParity"] and z["totalVolumeParity"]
                 for z in checks) if checks else False),
          "takerBuyBaseMatchedEveryComparedHour":(
             all(z["takerBuyBaseParity"] for z in checks) if checks else False),
          "CoinalyzeTXequalsOfficialTradeCount":(
             all(z["coinalyzeTxEqualsOfficialNumberOfTrades"]
                 for z in checks) if checks else False),
          "allSevenFieldsMatched":(
             all(z["allSevenFieldsParity"] for z in checks)
             if checks else False),
          "noSourceMatchConclusionsIfZeroSamples":True}
    return {
      "status":"V9_CROSS_SOURCE_1H_CANDLE_FLOW_PARITY_AUDIT_NOT_SIGNAL",
      "testedUTC":iso(int(datetime.now(timezone.utc).timestamp())),
      "dates":all_results,
      "perAsset":per,
      "priceToleranceRel":PRICE_TOL_REL,
      "volumeAndTakerBuyToleranceRel":VOLUME_TOL_REL,
      "tradeCountStrictIntegerEquality":True,
      "officialBinanceArchiveSHA256IndependentlyVerified":True,
      "allAssetsPriceVolumeFlowParityProven":(
        all(z["allSevenFieldsMatched"] and z["daysCompared"]>=1
            for z in per.values())),
      "noModelTrainingOrWeightUpdates":True,
      "mustNotPretendUnverifiedFieldsAreVerified":True,
      "researchOnly":True,"notificationsEnabled":False,
      "brokerOrders":False,"productionModified":False}


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--dates",default="2026-10-29,2026-11-08")
    p.add_argument("--output",default="forward/v9_source_parity/compare.json")
    a=p.parse_args()
    ds=[s.strip() for s in a.dates.split(",") if s.strip()]
    if not 1<=len(ds)<=5 or len(set(ds))!=len(ds):
        raise ValueError("EXPECTED_1_TO_5_UNIQUE_UTC_DAYS")
    today=datetime.now(timezone.utc).date()
    if any(date.fromisoformat(d)>=today for d in ds):
        raise ValueError("NEVER_VALIDATE_INCOMPLETE_DAY")
    key=(os.getenv("ETH_V7_COINALYZE_API_KEY") or
         os.getenv("SOL_V8_COINALYZE_API_KEY") or
         os.getenv("COINALYZE_API_KEY") or "").strip()
    if not key:raise ValueError("READ_ONLY_COINALYZE_KEY_MISSING")
    result=audit(ds,key)
    path=Path(a.output);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print("V9_BINANCE_COINALYZE_INDEPENDENT_1H_FIELD_PARITY_AUDIT",
          json.dumps({s:z for s,z in result["perAsset"].items()},
                     ensure_ascii=False),flush=True)


if __name__=="__main__":
    main()
