#!/usr/bin/env python3
"""ATLAS Core E5-B: read-only, fail-closed frozen monthly prospective intake.

A completed-month V9.3 CLOSED-trade ledger is not a timely BOS/retest
entry notification. In particular it cannot populate an actionable
AL/SHORT card retroactively. This adapter audits provenance and complete
closed trades *only*; real-time opportunity feed is NOT connected.
"""
from __future__ import annotations

import argparse
from calendar import monthrange
from datetime import datetime,timezone
from hashlib import sha1,sha256
from math import isfinite
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request,urlopen
import json
import re

from research.atlas_core_v5 import shadow_decision_e5 as e5

ROOT="https://raw.githubusercontent.com/exchangecurrency11/ATLAS-Quant-Engine"
MAX_BYTES=12_000_000
CHANNELS={
    "ETH_V93_SIX_STREAM":{
        "branch":"research/eth-v93-prospective-paired-20261113",
        "folder":"forward/v93_shadow_prospective_20261113",
        "specPath":"forward/v93_shadow_prospective_20261113/frozen_spec.json",
        "preflightPath":"forward/v93_shadow_prospective_20261113/preflight.json",
        "freeze":"2026-11-14T00:00:00Z",
        "expectedStatus":"PROSPECTIVE_MONTHLY_SHADOW_ONLY",
        "closeOnly":True,
    },
    "BTC_SOL_V93_HIGH_VOL":{
        "branch":"research/btc-sol-event-regime-forward-20261114",
        "folder":"forward/btc_sol_v93_prospective_20261114",
        "specPath":"forward/btc_sol_v93_prospective_20261114/frozen_spec.json",
        "preflightPath":"forward/btc_sol_v93_prospective_20261114/preflight.json",
        "freeze":"2026-11-15T00:00:00Z",
        "expectedStatus":"BTC_SOL_MONTH_COMPLETE_FROZEN_PROSPECTIVE",
        "closeOnly":True,
    },
}
OUT=Path("research/atlas_core_v6/output")
STATUS="ATLAS_CORE_E5B_FROZEN_MONTHLY_FORWARD_INTAKE_NON_ACTIONABLE"
VALID_EXITS={"STOP_FIRST_OR_AFTER_TP","TP3_COMPLETE","TIME_EXIT_AT_CLOSE"}
VALID_SIDES={"bullish","bearish"}
ASSETS={"BTCUSDT","ETHUSDT","SOLUSDT"}
# These are outside the current 51 frozen historical E2/E3 research trades.
HISTORY_MAX_EXCLUSIVE_UTC="2026-10-01T00:00:00Z"

def blob_sha1(raw):
    return sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()

def utc(s):
    return e5.strict_utc(s)

def ensure_date_month_boundary(time_text):
    t=utc(time_text)
    d=datetime.fromtimestamp(t,timezone.utc)
    if not (d.day==1 and d.hour==d.minute==d.second==0):
        raise ValueError("E5B_NOT_COMPLETE_UTC_MONTH_BOUNDARY")
    return t

def prior_month(as_of):
    d=datetime.fromtimestamp(as_of,timezone.utc)
    year,month=(d.year-1,12) if d.month==1 else (d.year,d.month-1)
    return f"{year:04d}-{month:02d}"

def assert_json_bytes(raw,name):
    if raw is None or not 0<len(raw)<=MAX_BYTES:
        raise ValueError("E5B_REQUIRED_DOCUMENT_MISSING_OR_TOO_BIG:"+name)
    try: data=json.loads(raw)
    except (ValueError,UnicodeError) as exc:
        raise ValueError("E5B_BAD_JSON_SOURCE:"+name) from exc
    if not isinstance(data,dict):
        raise ValueError("E5B_SOURCE_JSON_NOT_OBJECT:"+name)
    return data

def fetch_source(channel, relative, *, optional=False):
    """Only allow two exact frozen research branches and their folders.

    Missing optional latest.json means no data (not an error); 403, 451,
    network failures, or missing required snapshot fail closed.
    """
    if channel not in CHANNELS:
        raise ValueError("E5B_UNKNOWN_FROZEN_CHANNEL")
    conf=CHANNELS[channel]
    folder=conf["folder"]
    if not (relative==conf["specPath"] or relative==conf["preflightPath"]
            or relative==folder+"/latest.json"
            or (relative.startswith(folder+"/snapshots/") and
                re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])\.json",
                             relative[len(folder+"/snapshots/"):]))):
        raise ValueError("E5B_UNAUTHORIZED_REMOTE_PATH")
    url=f'{ROOT}/{conf["branch"]}/{relative}'
    with_req=Request(url,headers={"User-Agent":"ATLAS-E5B-ReadOnly-Prospective/1"})
    try:
        with urlopen(with_req,timeout=25) as response:
            raw=response.read(MAX_BYTES+1)
        if len(raw)>MAX_BYTES or not raw:
            raise ValueError("E5B_REMOTE_SOURCE_TOO_BIG_OR_EMPTY")
        return raw
    except HTTPError as exc:
        if optional and exc.code==404:
            return None
        raise ValueError("E5B_FROZEN_SOURCE_HTTP_FAILURE:"+str(exc.code)) from exc

def validate_origin(channel, fetcher):
    conf=CHANNELS[channel]
    pinned={}
    for path in (conf["specPath"],conf["preflightPath"]):
        fetched=fetcher(channel,path,optional=False)
        local=Path(path).read_bytes()
        if blob_sha1(local)!=e5.SOURCE_PINS[path] or fetched!=local:
            raise ValueError("E5B_REMOTE_FROZEN_SPEC_PREFLIGHT_DRIFT:"+path)
        pinned[path]=sha256(fetched).hexdigest()
    spec=assert_json_bytes(Path(conf["specPath"]).read_bytes(),"frozen_spec")
    preflight=assert_json_bytes(Path(conf["preflightPath"]).read_bytes(),"preflight")
    if spec["freezeUTC"]!=conf["freeze"]:
        raise ValueError("E5B_FROZEN_START_DRIFT")
    if channel=="ETH_V93_SIX_STREAM":
        if preflight["status"]!="PREFREEZE_PIPELINE_SMOKE_TEST":
            raise ValueError("E5B_WRONG_ETH_PREFLIGHT")
        if preflight["startProspectiveUTC"]!=conf["freeze"]:
            raise ValueError("E5B_ETH_START_DRIFT")
        if preflight["sourceHashSHA256"]!=spec["immutableEngineHashes"]:
            raise ValueError("E5B_ETH_PREFLIGHT_ENGINE_MISMATCH")
    else:
        if preflight["status"]!="BTC_SOL_PREFREEZE_PIPELINE_TEST_ONLY":
            raise ValueError("E5B_WRONG_BTC_SOL_PREFLIGHT")
        if preflight["frozenSpecHashes"]!=spec["frozenEngineHashesSHA256"]:
            raise ValueError("E5B_BTC_SOL_PREFLIGHT_ENGINE_MISMATCH")
    return spec,preflight,pinned

def validate_archive_manifest(latest,preflight,as_of,channel):
    """Continuity vs pre-registered prior months; checksum declarations only.

    Does NOT itself download/check Binance monthly ZIPs. Source producer
    does that; the adapter compares its claims to pinned preflight and
    immutable latest == month snapshot and records digest.
    """
    if channel=="ETH_V93_SIX_STREAM":
        proof=latest["archiveSHA256"]
        count=latest["verifiedArchives"]
        before=preflight["archiveSHA256"]
    else:
        proof=latest["officialArchiveSHA256"]
        count=latest["officialArchiveCount"]
        before=preflight["officialArchiveSHA256"]
    if not isinstance(proof,dict) or not proof or len(proof)!=count:
        raise ValueError("E5B_OFFICIAL_ARCHIVE_MANIFEST_COUNT")
    if any(not re.fullmatch(r"(BTCUSDT|ETHUSDT|SOLUSDT):20\d{2}-(0[1-9]|1[0-2])",k)
           or not isinstance(v,str) or not re.fullmatch("[a-f0-9]{64}",v)
           for k,v in proof.items()):
        raise ValueError("E5B_MANIFEST_BAD_KEY_OR_DIGEST")
    if any(proof.get(k)!=v for k,v in before.items()):
        raise ValueError("E5B_OLD_SHA256_ARCHIVE_REFERENCE_CHANGED")
    first=min(k.split(":")[1] for k in before)
    last=prior_month(as_of)
    if last<first:
        raise ValueError("E5B_ARCHIVE_LAST_MONTH_BEFORE_WARMUP")
    y,m=map(int,first.split("-"))
    needed=set()
    while f"{y:04d}-{m:02d}"<=last:
        month=f"{y:04d}-{m:02d}"
        for asset in ASSETS:
            needed.add(asset+":"+month)
        m+=1
        if m>12:y,m=y+1,1
    if set(proof)!=needed:
        raise ValueError("E5B_MISSING_OR_EXTRA_ARCHIVE_MONTHS")
    return {"reportedOfficialZipSHA256Count":count,
            "originalPreflightMonthlySHA256Unchanged":len(before),
            "latestMonth":last,
            "archiveDigestsReDownloadedByE5B":False}

def validate_closed_trade(t,asset,freeze,end,*,with_prices):
    if not isinstance(t,dict):
        raise ValueError("E5B_TRADE_NOT_OBJECT")
    base={"watchKnownUTC","retestKnownUTC","entryOpenUTC",
          "exitKnownUTC","side","exitReason","netR25Bps"}
    extra={"entry","stop","targets","netR9Bps"} if with_prices else set()
    if set(t)!=base|extra:
        raise ValueError("E5B_CLOSED_TRADE_SCHEMA_CHANGED")
    if t["side"] not in VALID_SIDES or t["exitReason"] not in VALID_EXITS:
        raise ValueError("E5B_UNKNOWN_SIDE_OR_EXIT")
    watch,retest,entry,exit_at=(utc(t[k]) for k in
       ("watchKnownUTC","retestKnownUTC","entryOpenUTC","exitKnownUTC"))
    if not (freeze<=watch<retest<=entry<exit_at<=end):
        raise ValueError("E5B_LOOKAHEAD_OR_PREFREEZE_TRADE")
    if any(ts%3600 for ts in (watch,retest,entry,exit_at)):
        raise ValueError("E5B_NON_1H_EVENT_ALIGNMENT")
    if exit_at-entry>24*3600:
        raise ValueError("E5B_TRADE_OVER_MAX_24H")
    r25=t["netR25Bps"]
    if not isinstance(r25,(int,float)) or not isfinite(r25):
        raise ValueError("E5B_INVALID_RETURN")
    if with_prices:
        price,stop=t["entry"],t["stop"]
        if (not isinstance(price,(int,float)) or not isinstance(stop,(int,float))
            or not isfinite(price) or not isfinite(stop) or price<=0 or stop<=0):
            raise ValueError("E5B_INVALID_ENTRY_STOP")
        sign=1 if t["side"]=="bullish" else -1
        risk=abs(price-stop)
        if not .001<=risk/price<=.04:
            raise ValueError("E5B_INVALID_PRESPECIFIED_RISK_RANGE")
        if sign*(price-stop)<=0:
            raise ValueError("E5B_STOP_ON_WRONG_SIDE")
        targets=t["targets"]
        if (not isinstance(targets,list) or len(targets)!=3
            or any(not isinstance(v,(int,float)) or not isfinite(v)
                    or abs(v-(price+sign*risk*(i+1)))>1e-6
                    for i,v in enumerate(targets))):
            raise ValueError("E5B_TARGETS_NOT_FIXED_ONE_TWO_THREE_R")
        r9=t["netR9Bps"]
        if not isinstance(r9,(int,float)) or not isfinite(r9):
            raise ValueError("E5B_INVALID_R9")
        net25=r9-2*(25-9)/10000*price/risk
        if abs(net25-r25)>2e-6:
            raise ValueError("E5B_FUNDAMENTAL_COST_FORMULA_VIOLATION")
    return (entry,t["side"]),{
        "asset":asset,"side":t["side"],
        "watchKnownUTC":t["watchKnownUTC"],
        "retestKnownUTC":t["retestKnownUTC"],
        "entryOpenUTC":t["entryOpenUTC"],
        "exitKnownUTC":t["exitKnownUTC"],
        "exitReason":t["exitReason"],
        "netR25FromFrozenClosedTape":r25,
        "priceAndStopAvailable":with_prices,
        "signalCouldHaveBeenIssuedAtEntry":False,
        "retrospectiveOnly":True,
    }

def scan_trades(rows,asset,freeze,end,metric,*,with_prices):
    if not isinstance(rows,list) or not isinstance(metric,dict):
        raise ValueError("E5B_TRADE_LIST_OR_METRIC_MISSING")
    if metric["trades"]!=len(rows) or not isinstance(metric["netR"],(int,float)):
        raise ValueError("E5B_SOURCE_METRIC_COUNT_MISMATCH")
    found=[]
    last=None
    keys=set()
    for t in rows:
        k,row=validate_closed_trade(t,asset,freeze,end,with_prices=with_prices)
        if k in keys or (last is not None and k<last):
            raise ValueError("E5B_DUPLICATE_OR_UNSORTED_ENTRIES")
        keys.add(k);last=k
        found.append(row)
    if abs(sum(t["netR25FromFrozenClosedTape"] for t in found)-metric["netR"])>2e-5:
        raise ValueError("E5B_REPORTED_NET_R25_NOT_RECONCILED")
    return found

def validate_eth(data,spec,preflight,end):
    if (data["startProspectiveUTC"]!=spec["freezeUTC"]
        or data["sourceHashSHA256"]!=spec["immutableEngineHashes"]
        or not data["neverRealOrders"] or not data["cannotCreditAnyPreFreezeTrade"]
        or not data["noExistingV7V92AccountWrites"]
        or data["notRealtimeAlerts"] is not True
        or data["periodPreviouslyBacktestedForTraining"] is not False):
        raise ValueError("E5B_ETH_FROZEN_SOURCE_OR_SAFETY_MISMATCH")
    streams=data["reportedStreams"]
    if set(streams)!=set(spec["candidates"]) or len(streams)!=6:
        raise ValueError("E5B_ETH_SIX_STREAM_IDENTITY_DRIFT")
    out={}
    for name,want in spec["candidates"].items():
        s=streams[name]
        if (s["symbol"]!=want["symbol"] or s["mode"]!=want["mode"]
            or s["disabledGates"]!=want["disabledGates"]
            or s["isActualExecution"] or not s["noBackfilledHistoricalTrades"]
            or not s["unresolvedNotCredited"]):
            raise ValueError("E5B_ETH_CANDIDATE_MISMATCH")
        if not (isinstance(s["openOrPendingAtLastClose"],dict)
                and set(s["openOrPendingAtLastClose"])=={"position","pending"}):
            raise ValueError("E5B_ETH_OPEN_POSITION_AUDIT_MISSING")
        arr=scan_trades(s["closedProspectiveTrades"],want["symbol"],
              utc(spec["freezeUTC"]),end,s["metrics25Bps"],with_prices=True)
        if s["metrics9Bps"]["trades"]!=len(arr) or (
            abs(sum(x["netR9Bps"] for x in s["closedProspectiveTrades"])
                 -s["metrics9Bps"]["netR"])>2e-5):
            raise ValueError("E5B_ETH_R9_METRICS_DISAGREE")
        out[name]=arr
    return out

def validate_btc_sol(data,spec,preflight,end):
    if (data["freezeUTC"]!=spec["freezeUTC"]
        or data["frozenSpecHashes"]!=spec["frozenEngineHashesSHA256"]
        or data["independentNewFutureTradesOnly"] is not True
        or data["noHistoricalTradesCredited"] is not True
        or data["unresolvedPositionsNotCountedAsClosed"] is not True
        or data["existingSixStreamV93ReferenceParity"] is not True
        or data["realOrders"] or data["notifications"]
        or data["productionOrExistingPaperWrites"]
        or data["candidatePromotionApproved"]):
        raise ValueError("E5B_BTC_SOL_FROZEN_SOURCE_OR_SAFETY_MISMATCH")
    streams=data["streams"]
    if set(streams)!={"BTCUSDT","SOLUSDT"}:
        raise ValueError("E5B_BTC_SOL_ASSET_STREAM_DRIFT")
    out={}
    for asset,record in streams.items():
        versions=record["versions"]
        if set(versions)!={"V92_REFERENCE","HIGH_VOL_CANDIDATE"}:
            raise ValueError("E5B_BTC_SOL_VERSION_DRIFT")
        for name,v in versions.items():
            if v["sourceOnly"] is not True or set(v["metric"])!={"9","25","50"}:
                raise ValueError("E5B_BTC_SOL_SOURCE_VERSION_DRIFT")
            arr=scan_trades(v["closedTrades"],asset,utc(spec["freezeUTC"]),
                  end,v["metric"]["25"],with_prices=False)
            if any(v["metric"][x]["trades"]!=len(arr) for x in ("9","50")):
                raise ValueError("E5B_BTC_SOL_COST_SCENARIO_COUNT_DRIFT")
            out[asset+":"+name]=arr
    return out

def channel_snapshot(channel,*,fetcher,now_epoch):
    spec,preflight,pins=validate_origin(channel,fetcher)
    conf=CHANNELS[channel]
    latest_path=conf["folder"]+"/latest.json"
    latest=fetcher(channel,latest_path,optional=True)
    if latest is None:
        return {
            "channel":channel,"status":"NO_COMPLETED_POSTFREEZE_MONTHLY_SNAPSHOT",
            "pinnedFrozenSpecPreflightSHA256":pins,
            "closedTrades":0,"streamCounts":{},
            "noTimelyOpportunityProof":True,
            "immutableMonthlySnapshotExactMatch":None,
            "reportedOfficialArchiveHashesAreNotIndependentlyRedownloaded":True,
            "snapshotGitBlobSHA1":None,
            "snapshotSHA256":None,
            "asOfExclusiveUTC":None,
        },{}
    data=assert_json_bytes(latest,"latest.json")
    if data.get("status")!=conf["expectedStatus"]:
        raise ValueError("E5B_LATEST_IS_NOT_ELIGIBLE_MONTHLY_PROSPECTIVE")
    asof=ensure_date_month_boundary(data["asOfExclusiveUTC"])
    freeze=utc(conf["freeze"])
    if asof<=freeze or asof>now_epoch:
        raise ValueError("E5B_SOURCE_FROM_FUTURE_OR_PREFREEZE")
    label=prior_month(asof)
    snapshot_path=conf["folder"]+"/snapshots/"+label+".json"
    immutable=fetcher(channel,snapshot_path,optional=False)
    if immutable!=latest:
        raise ValueError("E5B_LATEST_DIFFERS_FROM_IMMUTABLE_MONTH_SNAPSHOT")
    manifest=validate_archive_manifest(data,preflight,asof,channel)
    if channel=="ETH_V93_SIX_STREAM":
        streams=validate_eth(data,spec,preflight,asof)
    else:
        streams=validate_btc_sol(data,spec,preflight,asof)
    counts={key:len(rows) for key,rows in streams.items()}
    return {
        "channel":channel,
        "status":"VERIFIED_SOURCE_MONTHLY_CLOSED_TRADE_TAPE_NOT_TIMELY_ENTRY",
        "asOfExclusiveUTC":data["asOfExclusiveUTC"],
        "immutableMonthlySnapshotExactMatch":True,
        "snapshotGitBlobSHA1":blob_sha1(latest),
        "snapshotSHA256":sha256(latest).hexdigest(),
        "pinnedFrozenSpecPreflightSHA256":pins,
        "manifestProvenance":manifest,
        "closedTrades":sum(counts.values()),
        "streamCounts":counts,
        "noTimelyOpportunityProof":True,
        "reportedOfficialArchiveHashesAreNotIndependentlyRedownloaded":True,
    },streams

def cross_check_common_references(eth,btc_sol):
    """If the two source cohorts are from the same completed month,
    compare BTC/SOL baseline trades after the *later* 2026-11-15 freeze.
    """
    if not eth or not btc_sol:
        return {"performed":False,"matched":0,"why":"ONE_SOURCE_NOT_AVAILABLE"}
    if (eth["asOfExclusiveUTC"]!=btc_sol["asOfExclusiveUTC"]):
        return {"performed":False,"matched":0,"why":"DIFFERENT_MONTHS"}
    return {"performed":False,"matched":0,
            "why":"SIX_STREAM_PERIOD_BASELINE_COMPARISON_REQUIRES_RAW_REPORTS_AND_IS_NOT_ASSUMED"}

def audit(*,fetcher=fetch_source,now_utc=None):
    now_epoch=utc(now_utc) if now_utc else int(datetime.now(timezone.utc).timestamp())
    e5_source_hashes,preflight=e5.froze_sources()
    if preflight["actualForwardTradesCredited"]!=0:
        raise ValueError("E5B_E5A_FUTURE_CREDIT_DRIFT")
    channels={}
    all_streams={}
    for channel in CHANNELS:
        c,s=channel_snapshot(channel,fetcher=fetcher,now_epoch=now_epoch)
        channels[channel]=c;all_streams[channel]=s
    counted=sum(c["closedTrades"] for c in channels.values())
    if any(c["status"].startswith("NO_COMPLETED") for c in channels.values()):
        status="NO_COMPLETE_PROSPECTIVE_SOURCE_FOR_SOME_OR_ALL_CHANNELS"
    else:
        status="MONTHLY_FROZEN_SOURCE_AUDIT_AVAILABLE_BUT_NO_TIMELY_ENTRY"
    # Closed trades are known only after exit and monthly archive release.
    # NO after-the-fact decision labels are assigned to these entries.
    return {
        "status":STATUS,
        "readiness":status,
        "dataOriginSources":list(CHANNELS),
        "channels":channels,
        "cohortRowsReadAcrossAllVersions":counted,
        "uniqueRealTimeEntryOpportunitiesValidated":0,
        "liveOrContemporaneousEntryCards":[],
        "forwardProfitClaimMade":False,
        "historical51TradesCreditedAsProspective":0,
        "prospectiveClosedTapesAuditedNotPredictions":True,
        "prospectiveSourceScriptsWereReexecuted":False,
        "officialMonthlyZIPsRedownloadedByE5B":False,
        "snapshotSourcePinVerified":True,
        "noOrders":True,"noAlerts":True,"noNotifications":True,
        "noProductionOrMainOrPaperWrites":True,
        "noAutomationChanges":True,
        "noCandidatePromotion":True,
        "noRealAccountPositionsAvailable":True,
        "E5AFrozenGateHashesSHA256":e5_source_hashes,
        "limitations":[
            "Monthly archive may appear days after month end; a completed trade cannot be an entry-time notification.",
            "Snapshot byte-for-byte agreement with its immutable month witness is checked; remote branch itself is writable by permitted repository actors, not an independently signed exchange attestation.",
            "Monthly archive SHA256 entries are verified as original producer's declarations and pinned preflight consistency only; E5B does not re-download all raw publisher ZIP bytes.",
            "BTC/SOL monthly report has direction and final netR but omits actual entry price/stop, so E5B cannot compute a genuine stop risk or a real-time cost/risk card.",
            "ETH monthly report has prices and stops but includes post-exit results. Those fields are never fed into live decision cards retroactively.",
            "No 1H entry-time V9.2 BOS/retest witness feed, no verified position inventory or timely funding and spread feed is connected.",
            "No trade recommendation, user notification, broker order, source-branch writes, existing frozen experiment reset or schedule.",
        ],
        "nextTechnicalDependency":"Independent near-entry-time closed 1H BOS/retest producer with reproducible known-at UTC and read-only portfolio exposure; integrate only as a separate frozen E5-C stream",
    }

def markdown(d):
    rows=[
        "# ATLAS Core E5-B — verified frozen forward monthly source intake",
        "",
        "**Research only. Source verification does not mean live tradable signal.**",
        "",
        "| Frozen source channel | Evidence status | Verified monthly closed rows across variants | As-of UTC |",
        "|---|---|---:|---|",
    ]
    for c in d["channels"].values():
        rows.append("| "+c["channel"]+" | "+c["status"]+
           " | "+str(c["closedTrades"])+" | "+str(c["asOfExclusiveUTC"] or "—")+" |")
    rows+=["",f'**Timely verified entry signals: {d["uniqueRealTimeEntryOpportunitiesValidated"]}**.',
         "No historical 51 treated as fresh. No live position, orders or notifications.",
         "", "## Limitations", "",*("- "+x for x in d["limitations"]),""]
    return "\n".join(rows)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--out",default=str(OUT/"e5b_report.json"))
    a=p.parse_args()
    dest=Path(a.out)
    if not str(dest).startswith(str(OUT)+"/"):
        raise ValueError("E5B_OUTPUT_NOT_ISOLATED")
    result=audit()
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(result,sort_keys=True,indent=2,ensure_ascii=False)+"\n")
    dest.with_suffix(".md").write_text(markdown(result))
    print("ATLAS_E5B_FROZEN_PROSPECTIVE_INTAKE_FAIL_CLOSED_NO_FAKE_LIVE_SIGNAL",flush=True)
    for channel,c in result["channels"].items():
        print("E5B_SOURCE",channel,c["status"],"rows",c["closedTrades"],flush=True)
    print("E5B_TIMELY_ENTRIES",result["uniqueRealTimeEntryOpportunitiesValidated"],flush=True)

if __name__=="__main__":
    main()
