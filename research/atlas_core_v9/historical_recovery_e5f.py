#!/usr/bin/env python3
"""ATLAS E5-F: independent, *historical* USD-M 1H candle recovery.

Never rewrites V7/V9.1/V9.2, E5-D, paper accounts, prospective candidate
cohorts, alerts, orders, timestamps or original live-signal evidence.
A late-pulled candle is NEVER first-seen live strategy history.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from io import BytesIO, StringIO, TextIOWrapper
import json
from pathlib import Path
import re
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from zipfile import ZipFile, BadZipFile

from research.atlas_core_v7 import hourly_cold_observer_e5c as cold
from research.atlas_core_v8.hourly_journal_e5d import secure_fetch

STAGE="RESEARCH_ONLY"
CLASSIFICATION="BINANCE_USDM_HISTORICAL_RECOVERY_NOT_LIVE"
START="2026-11-14T22:00:00Z"
END="2026-11-15T18:00:00Z"
HOUR_MS=3_600_000
ASSETS=("BTCUSDT","ETHUSDT","SOLUSDT")
API="https://fapi.binance.com/fapi/v1/klines"
ARCHIVE="https://data.binance.vision/data/futures/um/daily/klines"
MAX_RESPONSE_BYTES=12_000_000
SNAPSHOTS={
    "V92_BTC_SOL":(cold.SOURCE_BRANCH_V92,cold.BTC_SOL_DIR),
    "V92_ETH":(cold.SOURCE_BRANCH_V92,cold.ETH_DIR),
    "V91_BTC_SOL":(cold.SOURCE_BRANCH_V9,"forward/v91_prospective_retest/hourly"),
    "V91_ETH":(cold.SOURCE_BRANCH_V9,"forward/v91_eth_prospective_retest/hourly"),
    "V7_BTC_SOL":("experiment/v7-signal-quality-20261103","forward/snapshots"),
    "V7_ETH":("experiment/v7-signal-quality-20261103","forward/eth/snapshots"),
    "V9_THREE_ASSET":(cold.SOURCE_BRANCH_V9,"forward/v9_next_4h_color/hourly/snapshots"),
}
STAMP=re.compile(r"^20\d\d-\d\d-\d\dT\d\d-00Z\.json$")
SHA40=re.compile(r"^[0-9a-f]{40}$")
SHA64=re.compile(r"^[0-9a-f]{64}$")
RUN=re.compile(r"^[1-9]\d{0,17}$")
NO_REDIRECT=build_opener(type("DisallowRedirects",(HTTPRedirectHandler,),{
    "redirect_request":lambda self,req,fp,code,msg,headers,newurl: None
})())

def utc(s):
    if not isinstance(s,str) or not re.fullmatch(r"20\d\d-\d\d-\d\dT\d\d:00:00Z",s):
        raise ValueError("E5F_STRICT_COMPLETE_UTC_HOUR_REQUIRED")
    dt=datetime.strptime(s,"%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    if dt.strftime("%Y-%m-%dT%H:%M:%SZ")!=s:
        raise ValueError("E5F_BAD_UTC_TIMESTAMP")
    return dt

def stamp(dt):
    return dt.strftime("%Y-%m-%dT%H-00Z")

def isodt(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")

def hours(start,end,now):
    a=utc(start);b=utc(end)
    if a<utc(START) or b<a or (b-a).total_seconds()>72*3600:
        raise ValueError("E5F_INVALID_BOUNDED_HISTORICAL_SPAN")
    if b>now-timedelta(hours=1):
        raise ValueError("E5F_UNCLOSED_OR_NOT_MATURED_EXCHANGE_CANDLE")
    return [a+timedelta(hours=i) for i in range(int((b-a).total_seconds()//3600)+1)]

def pinned_commit(branch,fetch=secure_fetch):
    if branch not in {x[0] for x in SNAPSHOTS.values()}:
        raise ValueError("E5F_UNAPPROVED_SOURCE_BRANCH")
    data=cold.as_obj(fetch(cold.API+"/branches/"+quote(branch,safe="")))
    sha=data.get("commit",{}).get("sha")
    if not isinstance(sha,str) or not SHA40.fullmatch(sha):
        raise ValueError("E5F_NOT_COMMIT_PINNED")
    return sha

def pinned_directory(commit,folder,fetch=secure_fetch):
    if not SHA40.fullmatch(commit) or folder not in {x[1] for x in SNAPSHOTS.values()}:
        raise ValueError("E5F_UNAPPROVED_GIT_DIRECTORY")
    tree=commit
    for component in folder.split("/"):
        data=cold.as_obj(fetch(cold.API+"/git/trees/"+tree))
        if data.get("truncated") or not isinstance(data.get("tree"),list):
            raise ValueError("E5F_TRUNCATED_GIT_TREE")
        found=[x for x in data["tree"] if x.get("path")==component and x.get("type")=="tree"]
        if len(found)!=1 or not SHA40.fullmatch(found[0].get("sha","")):
            raise ValueError("E5F_REQUIRED_SOURCE_TREE_ABSENT")
        tree=found[0]["sha"]
    directory=cold.as_obj(fetch(cold.API+"/git/trees/"+tree))
    if directory.get("truncated") or not isinstance(directory.get("tree"),list):
        raise ValueError("E5F_SOURCE_FILE_LIST_TRUNCATED")
    out={}
    for entry in directory["tree"]:
        name=entry.get("path")
        if not isinstance(name,str): raise ValueError("E5F_BAD_SOURCE_MEMBER")
        if folder.endswith("/snapshots") and name.endswith(".md"):
            continue
        if not STAMP.fullmatch(name) or entry.get("type")!="blob" or entry.get("mode")!="100644":
            raise ValueError("E5F_SOURCE_FILE_LIST_UNEXPECTED")
        sha=entry.get("sha")
        if not isinstance(sha,str) or not SHA40.fullmatch(sha):
            raise ValueError("E5F_SOURCE_BLOB_SHA_UNAVAILABLE")
        dt=utc(name.replace("-00Z.json",":00:00Z").replace("T", "T"))
        # Filename closed hour is an *UTC candle close*, not API open time.
        out[isodt(dt)]=sha
    return {"treeSHA1":tree,"closedHourGitBlobSHA1":out}

def https_bytes(url):
    parsed=urlsplit(url)
    if parsed.scheme!="https" or parsed.port not in (None,443) or parsed.username or parsed.password or parsed.fragment:
        raise ValueError("E5F_UNAUTHORIZED_REMOTE_TRANSPORT")
    if parsed.hostname=="fapi.binance.com":
        if parsed.path!="/fapi/v1/klines":raise ValueError("E5F_UNAPPROVED_EXCHANGE_API_PATH")
    elif parsed.hostname=="data.binance.vision":
        if not re.fullmatch(
            r"/data/futures/um/daily/klines/(BTCUSDT|ETHUSDT|SOLUSDT)/1h/"
            r"(BTCUSDT|ETHUSDT|SOLUSDT)-1h-20\d\d-\d\d-\d\d\.zip(\.CHECKSUM)?",
            parsed.path) or parsed.query:
            raise ValueError("E5F_UNAPPROVED_EXCHANGE_ARCHIVE_PATH")
    else:raise ValueError("E5F_REMOTE_HOST_NOT_OFFICIAL_BINANCE")
    request=Request(url,headers={"User-Agent":"ATLAS-E5F-Historical-NoTrade/1.0"})
    with NO_REDIRECT.open(request,timeout=30) as response:
        content=response.read(MAX_RESPONSE_BYTES+1)
    if not content or len(content)>MAX_RESPONSE_BYTES:
        raise ValueError("E5F_EMPTY_OR_OVERSIZED_EXCHANGE_RESPONSE")
    return content

def checked_candle(row,expected_open_ms):
    if not isinstance(row,(list,tuple)) or len(row)!=12:
        raise ValueError("E5F_NOT_12_FIELD_USDM_FUTURES_KLINE")
    if type(row[0]) is not int or row[0]!=expected_open_ms:
        raise ValueError("E5F_EXCHANGE_1H_OPEN_TIMESTAMP_MISMATCH")
    if type(row[6]) is not int or row[6]!=expected_open_ms+HOUR_MS-1:
        raise ValueError("E5F_EXCHANGE_1H_CLOSE_TIMESTAMP_MISMATCH")
    try:
        vals=[Decimal(str(row[i])) for i in (1,2,3,4,5,7,9,10)]
    except (InvalidOperation,ValueError) as e:
        raise ValueError("E5F_INVALID_EXCHANGE_OHLCV") from e
    if not all(x.is_finite() for x in vals):
        raise ValueError("E5F_NONFINITE_EXCHANGE_OHLCV")
    o,h,l,c,v,q,taker,taker_quote=vals
    if (min(o,h,l,c)<=0 or min(v,q,taker,taker_quote)<0
        or h<max(o,l,c) or l>min(o,h,c) or taker>v or taker_quote>q):
        raise ValueError("E5F_OHLCV_ORDER_OR_VOLUME_INVALID")
    if type(row[8]) is not int or row[8]<0:
        raise ValueError("E5F_INVALID_EXCHANGE_TRADE_COUNT")
    return {"candleOpenUTC":isodt(datetime.fromtimestamp(expected_open_ms/1000,timezone.utc)),
            "candleCloseUTC":isodt(datetime.fromtimestamp((expected_open_ms+HOUR_MS)/1000,timezone.utc)),
            "open":str(o),"high":str(h),"low":str(l),"close":str(c),
            "volume":str(v),"quoteAssetVolume":str(q),"numberOfTrades":row[8],
            "takerBuyBaseVolume":str(taker),"takerBuyQuoteVolume":str(taker_quote)}

def fetch_api(symbol,target_hours,fetch=https_bytes):
    if symbol not in ASSETS or not target_hours or len(target_hours)>73:
        raise ValueError("E5F_BAD_API_REQUEST")
    start=int((target_hours[0]-timedelta(hours=1)).timestamp()*1000)
    end=int(target_hours[-1].timestamp()*1000)-1
    params=urlencode({"symbol":symbol,"interval":"1h","startTime":start,
                      "endTime":end,"limit":len(target_hours)})
    raw=fetch(API+"?"+params)
    doc=json.loads(raw)
    if not isinstance(doc,list) or len(doc)!=len(target_hours):
        raise ValueError("E5F_API_NOT_ALL_CLOSED_HOURS_RETURNED")
    checked={}
    for dt,item in zip(target_hours,doc):
        candle=checked_candle(item,int((dt-timedelta(hours=1)).timestamp()*1000))
        checked[isodt(dt)]=candle
    return checked,{"method":"BINANCE_USDM_FAPI_V1_KLINES",
                    "urlBase":API,
                    "transportResponseSHA256":sha256(raw).hexdigest(),
                    "independentlyPublishedChecksum":False}

def fetch_archive(symbol,day,fetch=https_bytes):
    if symbol not in ASSETS or not re.fullmatch(r"20\d\d-\d\d-\d\d",day):
        raise ValueError("E5F_UNAPPROVED_ARCHIVE_DAY")
    base=ARCHIVE+"/"+symbol+"/1h/"+symbol+"-1h-"+day+".zip"
    zip_bytes=fetch(base)
    checksum_bytes=fetch(base+".CHECKSUM")
    dig=sha256(zip_bytes).hexdigest()
    checksum_text=checksum_bytes.decode("ascii").strip()
    # Binance publishes <sha256> <archive file> (possibly preceding *).
    parts=checksum_text.split()
    if (len(parts)!=2 or parts[0].lower()!=dig
        or parts[1].lstrip("*")!=base.rsplit("/",1)[-1]):
        raise ValueError("E5F_OFFICIAL_ZIP_CHECKSUM_FAILED")
    try:
        with ZipFile(BytesIO(zip_bytes)) as z:
            names=z.namelist()
            expected=symbol+"-1h-"+day+".csv"
            if names!=[expected] or z.getinfo(expected).file_size>500_000:
                raise ValueError("E5F_UNEXPECTED_OR_OVERSIZED_ARCHIVE_CSV")
            csv_data=z.read(expected).decode("utf-8-sig")
    except (BadZipFile,UnicodeError) as exc:
        raise ValueError("E5F_INVALID_BINANCE_OFFICIAL_ZIP") from exc
    rows=list(csv.reader(StringIO(csv_data)))
    if rows and rows[0][0].lower() in ("open_time","open time","opentime"):
        rows=rows[1:]
    if len(rows)!=24:
        raise ValueError("E5F_OFFICIAL_DAILY_CSV_NOT_24_HOURS")
    base_dt=datetime.strptime(day,"%Y-%m-%d").replace(tzinfo=timezone.utc)
    results={}
    for i,row in enumerate(rows):
        try:
            vals=[int(row[j]) if j in (0,6,8) else row[j] for j in range(12)]
        except (IndexError,ValueError) as exc:
            raise ValueError("E5F_BAD_BINANCE_CSV_ROW") from exc
        candle=checked_candle(vals,int((base_dt+timedelta(hours=i)).timestamp()*1000))
        results[candle["candleCloseUTC"]]=candle
    return results,{"method":"BINANCE_USDM_DAILY_OFFICIAL_ZIP_WITH_PUBLISHED_SHA256",
                    "urlBase":base,"zipSHA256":dig,"checksumUrl":base+".CHECKSUM",
                    "independentlyPublishedChecksum":True}

def recover(*,start=START,end=END,now=None,fetch_github=secure_fetch,
            fetch_exchange=https_bytes,run_id="1"):
    if not RUN.fullmatch(str(run_id)):
        raise ValueError("E5F_INVALID_RUN_ID")
    moment=now or datetime.now(timezone.utc)
    cohort=hours(start,end,moment)
    commits={}
    evidence={}
    for key,(branch,folder) in SNAPSHOTS.items():
        if branch not in commits:
            commits[branch]=pinned_commit(branch,fetch=fetch_github)
        evidence[key]=pinned_directory(commits[branch],folder,fetch=fetch_github)
    missing={key:[isodt(dt) for dt in cohort if isodt(dt) not in obj["closedHourGitBlobSHA1"]]
             for key,obj in evidence.items()}
    all_missing=sorted(set().union(*(set(x) for x in missing.values())))
    if not all_missing:
        raise ValueError("E5F_NO_MISSING_HOURS_COHORT_ALREADY_FULL")
    obtained={}
    acquisition={}
    failures={}
    for symbol in ASSETS:
        try:
            candles,proof=fetch_api(symbol,cohort,fetch=fetch_exchange)
            obtained[symbol]=candles
            acquisition[symbol]=[proof]
        except (HTTPError,URLError,TimeoutError,OSError) as exc:
            # Official GitHub runner geo/IP restrictions can block fapi.
            # Fail CLOSED rather than silently switching to spot or fake data.
            failures[symbol]={"fapi":"OFFICIAL_FAPI_UNAVAILABLE_NO_LIVE_BACKFILL",
                              "exceptionType":type(exc).__name__}
            merged={}
            proofs=[]
            days=sorted({dt.date().isoformat() for dt in cohort if dt.date()<moment.date()})
            # An API candle closes at dt but OPEN belongs to prior UTC day.
            days=sorted({(dt-timedelta(hours=1)).date().isoformat()
                         for dt in cohort if (dt-timedelta(hours=1)).date()<moment.date()})
            for day in days:
                try:
                    daily,receipt=fetch_archive(symbol,day,fetch=fetch_exchange)
                except (HTTPError,URLError,TimeoutError,OSError):
                    continue
                merged.update(daily)
                proofs.append(receipt)
            obtained[symbol]={k:v for k,v in merged.items() if k in {isodt(x) for x in cohort}}
            acquisition[symbol]=proofs
    # Retain only 1H historical OHLCV whose original V92 or V9 witness is absent.
    repaired={}
    for symbol in ASSETS:
        relevant=sorted(set(missing["V9_THREE_ASSET"]) |
                        set(missing["V92_ETH"] if symbol=="ETHUSDT" else missing["V92_BTC_SOL"]))
        repaired[symbol]={k:obtained[symbol][k] for k in relevant if k in obtained[symbol]}
    counts={symbol:{"requiredMissingClosedHours":len(
                      sorted(set(missing["V9_THREE_ASSET"])|
                        set(missing["V92_ETH"] if symbol=="ETHUSDT" else missing["V92_BTC_SOL"]))),
                    "recoveredHours":len(repaired[symbol])}
            for symbol in ASSETS}
    full=all(x["requiredMissingClosedHours"]==x["recoveredHours"] for x in counts.values())
    return {"stage":STAGE,"classification":CLASSIFICATION,
            "status":"HISTORICAL_REPAIR_ALL_REQUESTED_HOURS_RETRIEVED" if full
                     else "PARTIAL_REPAIR_OFFICIAL_EXCHANGE_UNAVAILABLE_OR_NOT_PUBLISHED",
            "runId":str(run_id),"producedAtUTC":isodt(moment.replace(microsecond=0)),
            "requestedFirstClosedHourUTC":start,"requestedLastClosedHourUTC":end,
            "cohortClosedHourCount":len(cohort),
            "sourceCommitPins":commits,
            "sourceGitTrees":{k:v["treeSHA1"] for k,v in evidence.items()},
            "sourceMissingClosedHours":missing,
            "sourceMissingAtLeastOneCount":len(all_missing),
            "recoveryByAsset":repaired,"recoveryCounts":counts,
            "officialSourceAcquisition":acquisition,
            "officialSourceAvailabilityFailures":failures,
            "rawApiSHA256IsNotAnExchangeSignedChecksum":True,
            "archiveChecksumVerifiedOnlyWhenPublished":True,
            "originalPaperAndForwardJournalsModified":False,
            "ordersSubmitted":False,"notificationsSent":False,
            "historicalTradeFillsInvented":False,"pastRealTimeSignalRecreated":False,
            "historicalRecoveryNotProspectiveEvidence":True,
            "notIndependentOfBinanceOfficialMarketData":True,
            "explanation":"Archived/late-fetched exchange 1H OHLCV ONLY; immutable research evidence, never an original same-hour observer, trade, price fill or forward performance record."}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--start",default=START)
    p.add_argument("--end",default=END)
    p.add_argument("--output",default="e5f_payload/report.json")
    p.add_argument("--run-id",default=None)
    opts=p.parse_args()
    import os
    runid=opts.run_id or os.environ.get("GITHUB_RUN_ID")
    if not runid:raise ValueError("E5F_GITHUB_RUN_ID_REQUIRED")
    dest=Path(opts.output)
    if dest.as_posix()!="e5f_payload/report.json":
        raise ValueError("E5F_OUTPUT_PATH_NOT_RESEARCH_ISOLATED")
    result=recover(start=opts.start,end=opts.end,run_id=str(runid))
    dest.parent.mkdir(exist_ok=True,parents=True)
    with dest.open("x",encoding="utf-8") as fd:
        json.dump(result,fd,indent=2,sort_keys=True,ensure_ascii=False)
        fd.write("\n")
    print("ATLAS_E5F_RESEARCH_HISTORICAL_NOT_FORWARD",result["status"])
    print("ATLAS_E5F_SOURCE_MISSING_HOURS",result["sourceMissingAtLeastOneCount"])
    print("ATLAS_E5F_NATIVE_RECOVERY_COUNTS",json.dumps(result["recoveryCounts"]))
    print("ATLAS_E5F_BROKER_ORDERS",result["ordersSubmitted"])

if __name__=="__main__":
    main()
