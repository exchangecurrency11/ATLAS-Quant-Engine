#!/usr/bin/env python3
"""E5-C: cold, read-only audit of EXISTING precommitted V9.2 hourly paper.

NOT a Binance-native proof, new strategy, order execution, or timely
entry signal. A record received after its hour close never proves a
next-open fill. No changes to frozen V9.3 monthly forward studies.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha1, sha256
import json
from math import isfinite
from pathlib import Path
import re
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen

from research.atlas_core_v5 import shadow_decision_e5 as e5

REPO="exchangecurrency11/ATLAS-Quant-Engine"
API=f"https://api.github.com/repos/{REPO}"
RAW=f"https://raw.githubusercontent.com/{REPO}"
SOURCE_BRANCH_V92="research/v92-bull-bear-candle-invalidation-20261112"
SOURCE_BRANCH_V9="research/v9-prestart-live-data-compatibility-20261111"
BTC_SOL_DIR="forward/v92_prospective_selected/hourly"
ETH_DIR="forward/v92_prospective_eth/hourly"
V9_PATH="forward/v9_next_4h_color/hourly/latest.json"
OUTPUT=Path("research/atlas_core_v7/output")
MODE="ATLAS_E5C_HOURLY_EXISTING_V92_COLD_OBSERVER_NOT_TRADING"
STAMP_RE=re.compile(r"^(20\d\d-\d\d-\d\dT\d\d-00Z)\.json$")
SHA_RE=re.compile(r"[a-f0-9]{40}")
MAX_BYTES=4_000_000
MAX_HOUR_AGE_SEC=5400
MAX_CAPTURE_LAG_SEC=3600
REQUIRE_CONSECUTIVE=4
ALLOWED_V92_MODES={
    "BTC_SOL":"V92_SELECTED_CANDLE_IMMUTABLE_HOURLY_FORWARD_PAPER_ONLY",
    "ETH":"V92_ETH_VERIFIED_HOURLY_CANDLES_OBSERVATIONAL_PAPER",
}
REJECTED_LIVE_ACTIONS={
    "noNewTradingOrders":True,
    "noNotifications":True,
    "noChangesToExistingPaperJournals":True,
    "noExistingAutomationEdits":True,
    "noProductionOrMainWrites":True,
    "noProspectiveCandidateFreezeEdits":True,
    "noUserTradeAdvice":True,
    "noAutomaticStrategyPromotion":True,
}

def strict_utc(t):
    return e5.strict_utc(t)

def utc_stamp(epoch):
    return datetime.fromtimestamp(epoch,timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def sha_git_blob(raw:bytes):
    return sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()

def _url_allowed(url):
    x=urlparse(url)
    return (x.scheme=="https" and x.hostname in
            ("api.github.com","raw.githubusercontent.com")
            and (x.path.startswith("/repos/"+REPO+"/") if x.hostname=="api.github.com"
                 else x.path.startswith("/"+REPO+"/"))
            and (not x.query or
                 (x.hostname=="api.github.com" and
                  x.path.startswith("/repos/"+REPO+"/contents/") and
                  re.fullmatch(r"ref=[a-f0-9]{40}",x.query) is not None))
            and not x.fragment)

def _remote_bytes(url):
    if not _url_allowed(url):
        raise ValueError("E5C_UNAUTHORIZED_EXTERNAL_HOST")
    request=Request(url,headers={
        "User-Agent":"ATLAS-E5C-Research-ReadOnly-1.0",
        "Accept":"application/vnd.github+json" if url.startswith(API) else "application/json",
        "X-GitHub-Api-Version":"2022-11-28"})
    with urlopen(request,timeout=25) as response:
        content=response.read(MAX_BYTES+1)
        if len(content)>MAX_BYTES or not content:
            raise ValueError("E5C_EMPTY_OR_OVERSIZE_REMOTE_CONTENT")
        return content

def as_obj(raw):
    try: out=json.loads(raw)
    except (UnicodeError,ValueError) as exc:
        raise ValueError("E5C_MALFORMED_REMOTE_JSON") from exc
    if not isinstance(out,dict):
        raise ValueError("E5C_EXPECTED_JSON_OBJECT")
    return out

def commit_head(branch, fetch=_remote_bytes):
    if branch not in (SOURCE_BRANCH_V92,SOURCE_BRANCH_V9):
        raise ValueError("E5C_UNAPPROVED_SOURCE_BRANCH")
    # slash percent-encoded to ensure an unambiguous REST branch request.
    doc=as_obj(fetch(API+"/branches/"+quote(branch,safe="")))
    head=doc.get("commit",{}).get("sha")
    if not isinstance(head,str) or not SHA_RE.fullmatch(head):
        raise ValueError("E5C_UNTRUSTED_SOURCE_COMMIT")
    return head

def list_hourly(branch_sha, folder, fetch=_remote_bytes):
    if folder not in (BTC_SOL_DIR,ETH_DIR) or not SHA_RE.fullmatch(branch_sha):
        raise ValueError("E5C_UNAPPROVED_HOURLY_SOURCE_PATH")
    raw=fetch(API+"/contents/"+folder+"?ref="+branch_sha)
    # _url_allowed allows read-only '?ref=' API query only for this
    # exact commit-pinned metadata endpoint.
    try:listing=json.loads(raw)
    except (ValueError,UnicodeError) as exc:
        raise ValueError("E5C_BAD_REPOSITORY_DIRECTORY_JSON") from exc
    if not isinstance(listing,list):
        raise ValueError("E5C_NOT_A_DIRECTORY")
    by_stamp={}
    for f in listing:
        if not isinstance(f,dict):
            raise ValueError("E5C_UNRECOGNIZED_DIRECTORY_ENTRY")
        name=f.get("name")
        match=STAMP_RE.fullmatch(name) if isinstance(name,str) else None
        if not match:
            raise ValueError("E5C_UNEXPECTED_HOURLY_DIRECTORY_ENTRY")
        key=match.group(1)
        dt=datetime.strptime(key,"%Y-%m-%dT%H-00Z").replace(tzinfo=timezone.utc)
        if dt.minute or dt.second:
            raise ValueError("E5C_MISALIGNED_FILE_TIME")
        if key in by_stamp or f.get("type")!="file" or not SHA_RE.fullmatch(f.get("sha","")):
            raise ValueError("E5C_DUPLICATE_OR_UNPINNED_FILE")
        by_stamp[key]={"file":folder+"/"+name,"gitBlobSHA1":f["sha"]}
    if not by_stamp:
        raise ValueError("E5C_NO_VERIFIABLE_HOURLY_FILES")
    return by_stamp

def read_git_blob(commit,folder,filename_meta,fetch=_remote_bytes):
    if not SHA_RE.fullmatch(commit):
        raise ValueError("E5C_COMMIT_SHA_INVALID")
    path=filename_meta["file"]
    if not path.startswith(folder+"/") or not STAMP_RE.fullmatch(path[len(folder)+1:]):
        raise ValueError("E5C_HOURLY_FILE_PATH_TRAVERSAL")
    payload=fetch(RAW+"/"+commit+"/"+path)
    if sha_git_blob(payload)!=filename_meta["gitBlobSHA1"]:
        raise ValueError("E5C_GIT_SOURCE_BLOB_SHA1_MISMATCH")
    return as_obj(payload),sha256(payload).hexdigest()

def read_v9_context(commit,fetch=_remote_bytes):
    if not SHA_RE.fullmatch(commit):
        raise ValueError("E5C_V9_COMMIT_INVALID")
    b=fetch(RAW+"/"+commit+"/"+V9_PATH)
    return as_obj(b),sha256(b).hexdigest()

def timeline_stamps(entries):
    result={}
    for group,contents in entries.items():
        keys=sorted(contents)
        result[group]=keys
    return result

def latest_consecutive(maps, latest_epoch, count=REQUIRE_CONSECUTIVE):
    if not 1<=count<=12:
        raise ValueError("E5C_INVALID_CONSECUTIVE_REQUIREMENT")
    relevant={}
    for label,month in maps.items():
        relevant[label]=[utc_stamp(latest_epoch-n*3600).replace(":00Z","-00Z")
                         for n in range(count)]
        # Filename timezone format is 2026-..T21-00Z.
        # Ensure each consecutive clock-hour exists (not just last 4 stored).
        relevant[label]=all(x in month for x in relevant[label])
    return {
        "requiredConsecutiveHours":count,
        "allLastHoursPresentPerSource":relevant,
        "matchedAcrossBothSources":all(relevant.values()),
    }

def basic_time_safety(packet,kind,now):
    if packet.get("mode")!=ALLOWED_V92_MODES[kind]:
        raise ValueError("E5C_UNKNOWN_V92_HOURLY_MODE")
    target=strict_utc(packet["targetClosed1HUTC"])
    captured=strict_utc(packet["capturedAtUTC"])
    if target%3600 or not target<=captured<=now+60:
        raise ValueError("E5C_MALFORMED_OR_FUTURE_HOURLY_OBSERVATION")
    if not packet.get("noBrokerOrders") is True or not packet.get("noUserNotifications") is True:
        raise ValueError("E5C_V92_PAPER_ONLY_SOURCE_SAFETY_CHANGED")
    backfill_key="noRetroactiveBackfill" if kind=="ETH" else "noPastHourBackfill"
    if packet.get(backfill_key) is not True:
        raise ValueError("E5C_HOURLY_BACKFILL_CONTRACT_DRIFT")
    return target,captured

def validate_btc_sol(packet,now):
    ts,captured=basic_time_safety(packet,"BTC_SOL",now)
    if (packet.get("sourceVerifiedSameHour") is not True
        or packet.get("sourceV7AndV91RecomputedExactMatch") is not True
        or packet.get("liveBinanceExchangeParityNotIndependentlyProven") is not True
        or packet.get("hypotheticalEntryAtPastNextOpenNotProvenExecutable") is not True
        or packet.get("originalV7V91StrategyAndPortfolioUntouched") is not True
        or packet.get("policyFrozenAfterInspectingOldHistory") is not True):
        raise ValueError("E5C_BTC_SOL_VERIFICATION_OR_LIMITS_CHANGED")
    if packet.get("ETHExcludedFromThisBTC_SOLCoreCapture") is not True:
        raise ValueError("E5C_BTC_SOL_ETH_SOURCE_SEPARATION_CHANGED")
    assets=packet.get("assets")
    if not isinstance(assets,dict) or set(assets)!={"BTCUSDT","SOLUSDT"}:
        raise ValueError("E5C_BTC_SOL_MISSING_ASSET")
    for symbol,source in assets.items():
        for mode in ("originalV7","originalV91","selectedV92"):
            row=source.get(mode)
            if not isinstance(row,dict):
                raise ValueError("E5C_BTC_SOL_MISSING_V92_STREAM")
            if not isinstance(row.get("newWatchAtThisClose"),list):
                raise ValueError("E5C_BTC_SOL_BAD_WATCH_FIELD")
            if not isinstance(row.get("paperTradeExitsObservedAtThisClose"),list):
                raise ValueError("E5C_BTC_SOL_BAD_EXIT_FIELD")
            state=row.get("currentPaperState")
            if not isinstance(state,dict) or set(state)!={
                    "activeBOSWatch","pendingNextOpenPaperEntry","openHypotheticalPosition"}:
                raise ValueError("E5C_BTC_SOL_PAPER_STATE_CHANGED")
        audit=source.get("currentCloseRetestEvaluation")
        if not isinstance(audit,dict) or not all(k in audit for k in
            ("candidateRetestAtThisClose","baselineRetestPresent",
             "selectedRetestPresent","directCurrentFilterVeto")):
            raise ValueError("E5C_MISSING_CLOSED_RETEST_ATTESTATION")
        if audit["selectedRetestPresent"] and not audit["baselineRetestPresent"]:
            raise ValueError("E5C_SELECTED_RETEST_WITHOUT_BASELINE")
        if audit["directCurrentFilterVeto"] and audit["selectedRetestPresent"]:
            raise ValueError("E5C_SELECTED_RETEST_DESPITE_DIRECT_VETO")
        if source.get("noStandaloneCandleDrivenEntry") is not True:
            raise ValueError("E5C_CANDLE_OBSERVATION_AS_NEW_TRADE")
    parity=packet.get("originalV7_1H4HDailyCandleParity")
    if not isinstance(parity,dict) or set(parity)!=set(assets):
        raise ValueError("E5C_MISSING_BTC_SOL_CANDLE_PARITY")
    for coin in parity.values():
        if set(coin)!={"1hour","4hour","daily"}:
            raise ValueError("E5C_MISSING_TIMEFRAME_PARITY")
        for timeframe,row in coin.items():
            if row.get("allOHLCVFieldsWithinIntegrityTolerances") is not True or row.get("twoIndependentBinanceExchangeSourcesProven") is not False:
                raise ValueError("E5C_NOT_PROVEN_INDEPENDENT_EXCHANGE_SOURCE")
            close=strict_utc(row["closedCandleUTC"])
            if close>ts:
                raise ValueError("E5C_FUTURE_V92_CANDLE_USED")
            if timeframe=="1hour" and close!=ts:
                raise ValueError("E5C_1H_CLOSE_NOT_TARGET")
            fields=row.get("relativeDifferences",{})
            if set(fields)!={"open","high","low","close","volume"}:
                raise ValueError("E5C_MISSING_OR_CHANGED_SOURCE_OHLCV")
            for name,item in fields.items():
                if not isinstance(item,dict) or item.get("relativeDifference") is None:
                    raise ValueError("E5C_BAD_PARITY_DIFF")
                original=float(item["v7Reference"])
                fetched=float(item["reFetchedHistory"])
                rel=float(item["relativeDifference"])
                if not all(isfinite(x) for x in (original,fetched,rel)):
                    raise ValueError("E5C_NOT_FINITE_CANDLE_PARITY")
                if abs(original-fetched)>max(1e-7,abs(original)*.006):
                    raise ValueError("E5C_DISAGREED_V92_OHLCV")
                if abs(rel)>float(row.get("volumeToleranceRel" if name=="volume" else "priceToleranceRel",-1)):
                    raise ValueError("E5C_V92_PARITY_TOLERANCE_EXCEEDED")
    return {
        "targetClosed1HUTC":packet["targetClosed1HUTC"],
        "capturedAtUTC":packet["capturedAtUTC"],
        "hourlyCaptureLagMinutes":round((captured-ts)/60,3),
        "assets":{asset:mode_observation(packet["assets"][asset]["selectedV92"],
                                        packet["assets"][asset]["currentCloseRetestEvaluation"])
                  for asset in ("BTCUSDT","SOLUSDT")},
        "exchangeIndependentTruth":False,
    }

def validate_eth(packet,now):
    ts,captured=basic_time_safety(packet,"ETH",now)
    if (packet.get("symbol")!="ETHUSDT"
        or packet.get("verifiedSourceAndExactV7AndV91Replay") is not True
        or packet.get("independentBinanceTruthNotEstablished") is not True
        or packet.get("sameV91Max4hEntryStopTPAndExitLogic") is not True
        or packet.get("notNewETHTradeFromCandleAlone") is not True
        or packet.get("ethV92RetestVetoEnabled") is not False
        or packet.get("ethPatternObservationsOnly") is not True):
        raise ValueError("E5C_ETH_VERIFICATION_OR_TRADE_CLASSIFICATION_CHANGED")
    for field in ("originalV7","originalV91","selectedV92"):
        row=packet.get(field)
        if not isinstance(row,dict) or not isinstance(row.get("newWatchAtThisClose"),list):
            raise ValueError("E5C_ETH_MISSING_V92_ENGINE_STREAM")
        if not isinstance(row.get("paperTradeExitsObservedAtThisClose"),list):
            raise ValueError("E5C_ETH_MISSING_EXIT_STREAM")
        state=row.get("currentPaperState")
        if not isinstance(state,dict) or set(state)!={
            "activeBOSWatch","pendingNextOpenPaperEntry","openHypotheticalPosition"}:
            raise ValueError("E5C_ETH_MALFORMED_PAPER_STATE")
    si=packet.get("sourceIntegrity")
    if not isinstance(si,dict) or set(si)!={"1hour","4hour","daily"}:
        raise ValueError("E5C_ETH_MISSING_TIMEFRAME_INTEGRITY")
    for tf,x in si.items():
        if x.get("verified") is not True or x.get("notIndependentBinanceExchangeTruth") is not True:
            raise ValueError("E5C_ETH_INDEPENDENT_EXCHANGE_CLAIM")
        close=strict_utc(x["closeUTC"])
        if close>ts or (tf=="1hour" and close!=ts):
            raise ValueError("E5C_ETH_FUTURE_CANDLE")
        diffs=x.get("relativeDifference",{})
        if set(diffs)!={"open","high","low","close","volume"}:
            raise ValueError("E5C_ETH_INCOMPLETE_OHLCV_CHECKS")
        if not all(isinstance(v,(int,float)) and isfinite(v) and abs(v)<.006
                   for v in diffs.values()):
            raise ValueError("E5C_ETH_CANDLE_SOURCE_DISAGREES")
    return {
        "targetClosed1HUTC":packet["targetClosed1HUTC"],
        "capturedAtUTC":packet["capturedAtUTC"],
        "hourlyCaptureLagMinutes":round((captured-ts)/60,3),
        "assets":{"ETHUSDT":mode_observation(packet["selectedV92"],None)},
        "exchangeIndependentTruth":False,
    }

def mode_observation(v92, retest):
    """Retains counts and state identity; NEVER invents entry price/stop."""
    state=v92["currentPaperState"]
    return {
        "watchReportedAtThisHour":len(v92["newWatchAtThisClose"]),
        "exitReportedAtThisHour":len(v92["paperTradeExitsObservedAtThisClose"]),
        "bosWatchStillActive":state["activeBOSWatch"] is not None,
        "hypotheticalPaperEntryPending":state["pendingNextOpenPaperEntry"] is not None,
        "hypotheticalPaperPositionOpen":state["openHypotheticalPosition"] is not None,
        "retestPresentAtClose":retest["selectedRetestPresent"] if retest is not None else None,
        "paperSourceCannotProveExecutableFills":True,
        "orderAllowed":False,
        "newLiveTradingSignal":False,
        "stopAndPositionSizingProofAvailable":False,
    }

def verify_context(v9,btc_sol,eth):
    if (v9.get("status")!="V9_HOURLY_OBSERVATION_VERIFIED_PAPER_CONTEXT_ONLY"
        or v9.get("realOrders") is not False
        or v9.get("doesNotRepaintOrBackfillMissing4HForecasts") is not True
        or v9.get("officialNext4HColorRequiresBeforeStartRecord") is not True
        or set(v9.get("assets",{}))!={"BTCUSDT","ETHUSDT","SOLUSDT"}):
        raise ValueError("E5C_WRONG_V9_SOURCE_OR_MISCLASSIFIED_CONTEXT")
    target=btc_sol["targetClosed1HUTC"]
    if eth["targetClosed1HUTC"]!=target or v9["closed1HUTC"]!=target:
        raise ValueError("E5C_SOURCE_HOURS_NOT_ALIGNED")
    observed=strict_utc(v9["observedAtUTC"])
    if observed<strict_utc(target):
        raise ValueError("E5C_V9_CONTEXT_BEFORE_CANDLE_CLOSED")
    for symbol,data in v9["assets"].items():
        if data.get("contextOnlyNotANewPrestartDirectionForecast") is not True:
            raise ValueError("E5C_V9_CONTEXT_AS_ENTRY")
        for tf in ("1H","4H","Daily"):
            check=data[tf]
            if not isinstance(check,dict) or "OHLCV" not in check:
                raise ValueError("E5C_MISSING_V9_OHLCV")
            if strict_utc(check["closedAtUTC"])>strict_utc(target):
                raise ValueError("E5C_V9_LOOKAHEAD_CANDLE")
    return {"parityBTCAndSOL":True,"ETH4HAndDailyContextOnly":True}

def cross_prove_ohlcv(v9,original_btc_sol,original_eth):
    """Cross compare Coinalyze-derived V9 and V92 public paper OHLCV.

    This is source-system parity, NOT two independent Binance feeds.
    """
    result=verify_context(v9,original_btc_sol,original_eth)
    mapping={"1H":"1hour","4H":"4hour","Daily":"daily"}
    for asset in ("BTCUSDT","SOLUSDT"):
        parity=original_btc_sol["originalV7_1H4HDailyCandleParity"][asset]
        for frame,p in mapping.items():
            old=parity[p]
            current=v9["assets"][asset][frame]
            if old["closedCandleUTC"]!=current["closedAtUTC"]:
                raise ValueError("E5C_V92_V9_CANDLE_TIMESTAMP_MISMATCH")
            for attr in ("open","high","low","close","volume"):
                older=old["relativeDifferences"][attr]["v7Reference"]
                newer=current["OHLCV"][attr]
                if not all(isfinite(float(x)) for x in (older,newer)):
                    raise ValueError("E5C_NONFINITE_CROSS_FEED_OHLCV")
                if abs(float(older)-float(newer))>max(.000001,abs(float(older))*.000002):
                    raise ValueError("E5C_V92_V9_PUBLIC_CONTEXT_OHLCV_MISMATCH")
    eth_daily=original_eth["ethHigherTimeframeRecognition1D3D"]["1D"]
    if eth_daily["lastClosedCandleUTC"]!=v9["assets"]["ETHUSDT"]["Daily"]["closedAtUTC"]:
        raise ValueError("E5C_ETH_1D_CLOSED_TIMESTAMP_DRIFT")
    if abs(float(eth_daily["close"])-float(v9["assets"]["ETHUSDT"]["Daily"]["OHLCV"]["close"]))>1e-6:
        raise ValueError("E5C_ETH_DAILY_CLOSE_PARITY_DRIFT")
    return {
        **result,
        "BTC_SOL_1H_4H_Daily_OHLCVMatches":True,
        "ETH_1D_CloseMatches":True,
        "ETH_1H_4H_FullIndependentOHLCVAvailable":False,
        "independentExchangeNativeTruthEstablished":False,
    }

def classify_observation(btc,eth,coverage,now_epoch):
    target=strict_utc(btc["targetClosed1HUTC"])
    captured_max=max(strict_utc(btc["capturedAtUTC"]),strict_utc(eth["capturedAtUTC"]))
    if target>now_epoch:
        raise ValueError("E5C_CANNOT_REPLAY_FUTURE_HOUR")
    after_close_sec=now_epoch-target
    lag_sec=captured_max-target
    current=after_close_sec<=MAX_HOUR_AGE_SEC
    lagged=lag_sec>15*60
    if not current:
        classification="STALE_SOURCE_NO_ENTRY"
    elif lagged:
        classification="DELAYED_1H_OBSERVATION_NOT_AN_ENTRY"
    elif not coverage["matchedAcrossBothSources"]:
        classification="INCOMPLETE_HOURLY_COVERAGE_NOT_AN_ENTRY"
    else:
        classification="RECENT_PAPER_OBSERVATION_STILL_NOT_NEXT_OPEN_FILL_PROOF"
    return {
        "status":classification,
        "latestClosedCandleUTC":btc["targetClosed1HUTC"],
        "latestSourceCaptureUTC":utc_stamp(captured_max),
        "observerReadUTC":utc_stamp(now_epoch),
        "observedMinutesAfterClosedHour":round(after_close_sec/60,2),
        "lastSourceCaptureLagMinutes":round(lag_sec/60,2),
        "sourceHourAgeWithin90Minutes":current,
        "sourceCaptureWithinOneHour":lag_sec<=MAX_CAPTURE_LAG_SEC,
        "historicallyMissingHoursNeverFilled":True,
        "nextHourOpenAlreadyPassedByAnyPostCloseSnapshot":True,
        "entryAtExactOpeningPriceVerified":False,
        "actualBrokerOrPaperBookPositionInventoryVerified":False,
        "liveEntryEligible":False,
    }

def audit(*, fetch=_remote_bytes, now_utc=None):
    now_epoch=strict_utc(now_utc) if now_utc else int(datetime.now(timezone.utc).timestamp())
    old_pins,stage=e5.froze_sources()
    v92_sha=commit_head(SOURCE_BRANCH_V92,fetch=fetch)
    v9_sha=commit_head(SOURCE_BRANCH_V9,fetch=fetch)
    btc_meta=list_hourly(v92_sha,BTC_SOL_DIR,fetch=fetch)
    eth_meta=list_hourly(v92_sha,ETH_DIR,fetch=fetch)
    btc_latest=max(btc_meta)
    eth_latest=max(eth_meta)
    if btc_latest!=eth_latest:
        # No cross-asset same-hour semantics; require an exact current
        # triple-witness aligned observation, never silently use older pairs.
        return {
            "mode":MODE,"status":"SOURCE_HOURS_DISAGREE_FAIL_CLOSED",
            "sourceGitCommits":{"V92":v92_sha,"V9":v9_sha},
            "latestSourceHours":{"BTC_SOL":btc_latest,"ETH":eth_latest},
            "actualNewLiveOpportunityCount":0,
            "nonActionableObservations":[],
            "actionSafety":REJECTED_LIVE_ACTIONS,
            "limitations":["BTC/SOL and ETH latest hourly source timestamps disagree",
                           "No invented same-hour cross-source witness or entry signals."],
        }
    btc_data,btc_digest=read_git_blob(v92_sha,BTC_SOL_DIR,btc_meta[btc_latest],fetch=fetch)
    eth_data,eth_digest=read_git_blob(v92_sha,ETH_DIR,eth_meta[eth_latest],fetch=fetch)
    if (btc_latest!=btc_data["targetClosed1HUTC"].replace(":00Z","-00Z")
        or eth_latest!=eth_data["targetClosed1HUTC"].replace(":00Z","-00Z")):
        raise ValueError("E5C_FILENAME_TIMESTAMP_VS_SIGNED_CONTENT_DRIFT")
    b=validate_btc_sol(btc_data,now_epoch)
    e=validate_eth(eth_data,now_epoch)
    if b["targetClosed1HUTC"]!=e["targetClosed1HUTC"]:
        raise ValueError("E5C_V92_BTC_SOL_ETH_CLOSE_HOUR_DIFFER")
    v9,v9digest=read_v9_context(v9_sha,fetch=fetch)
    parity=cross_prove_ohlcv(v9,btc_data,eth_data)
    t=strict_utc(b["targetClosed1HUTC"])
    coverage=latest_consecutive(
        {"BTC_SOL":btc_meta,"ETH":eth_meta},t)
    classification=classify_observation(b,e,coverage,now_epoch)
    new_watches={**b["assets"],**e["assets"]}
    observations=[
        {"symbol":symbol,
         "sourceClosedHourUTC":b["targetClosed1HUTC"],
         "sourceCapturedUTC":b["capturedAtUTC"] if symbol!="ETHUSDT"
                                else e["capturedAtUTC"],
         "observerReadUTC":utc_stamp(now_epoch),
         "sourceAnalysis":entry,
         "notARealTimeTradingOpportunity":True,
         "noExecutableEntryOrStopClaim":True,
         "noRealTradingPermission":True}
        for symbol,entry in sorted(new_watches.items())]
    return {
        "mode":MODE,"status":"SOURCE_WITNESSES_CHECKED_OBSERVATION_ONLY",
        "sourceGitCommits":{"V92":v92_sha,"V9":v9_sha},
        "sourceFileSHA256":{"BTC_SOL_V92":btc_digest,
                           "ETH_V92":eth_digest,"V9_CONTEXT":v9digest},
        "latestSourceHours":{"BTC_SOL":btc_latest,"ETH":eth_latest,
                             "V9_CONTEXT":v9["closed1HUTC"]},
        "sourceIntegrityChecks":parity,
        "consecutiveHourCoverage":coverage,
        "hourlyObservationTimeliness":classification,
        "sourceAssetPaperObservations":observations,
        "newBOSWatchReports":sum(x["sourceAnalysis"]["watchReportedAtThisHour"]
                                 for x in observations),
        "newSelectedPaperRetestReports":sum(
            x["sourceAnalysis"]["retestPresentAtClose"] is True
            for x in observations),
        "pendingHypotheticalPaperEntryReports":sum(
            x["sourceAnalysis"]["hypotheticalPaperEntryPending"]
            for x in observations),
        "actualNewLiveOpportunityCount":0,
        "newForwardTradesAccrued":0,
        "historical51TradesCreditedToForward":0,
        "realAccountExposureAvailable":False,
        "independentlyExchangeVerifiedSource":False,
        "full3AssetLiveSourcePriceStopAndNextOpenValidated":False,
        "separateFrozenForwardCandidateBranchesModified":False,
        "sourceE5AValidationHashesSHA256":old_pins,
        "sourceForwardMonthlyStatus":stage["status"],
        "actionSafety":REJECTED_LIVE_ACTIONS,
        "limitations":[
            "Original V92 saved hourly paper observations exist and can be validated with source-commit-pinned SHA-1 Git file blobs.",
            "BTC/SOL + ETH + V9 readings are based on original Coinalyze/V7-derived OHLCV, not independent exchange-native Binance futures market data.",
            "BTC/SOL 1H/4H/daily OHLCV cross-replayed with V9; ETH daily close only cross-proven here, its 1H/4H source integrity remains reporter-asserted.",
            "Current original capture was made after the 1H closed and the hypothetical next-hour OPEN; a later read cannot claim a timely real entry or historical executable price.",
            "Missing hourly snapshots reject continuous-coverage readiness. No missing prior hour fabricated.",
            "Existing hypothetical pending/open positions are NOT real account exposure; portfolio risk gate cannot clear without independently verified timely position state.",
            "The research-only workflow runs on demand or on changes to this research branch; it is NOT a 24/7 automatically scheduled E5-C observer.",
            "Frozen V9.3 monthly ETH/BTC/SOL candidate studies are distinct and untouched; no new gains, forward trades, notifications or orders claimed.",
        ],
    }

def markdown(d):
    rows=["# ATLAS Core E5-C — observed hourly V9.2 research snapshots",
          "", "**NOT a live entry signal, no orders, no notifications.**","",
          f'**State:** {d["status"]}',"",
          f'Live tradable entry signals: **{d["actualNewLiveOpportunityCount"]}**.',
          f'V9.3 new paper forward trades credited: **{d.get("newForwardTradesAccrued",0)}**.',
          "",
    ]
    if d["status"]=="SOURCE_WITNESSES_CHECKED_OBSERVATION_ONLY":
        t=d["hourlyObservationTimeliness"]
        c=d["consecutiveHourCoverage"]
        rows+= [
          f'Saved last 1H close: {t["latestClosedCandleUTC"]}.',
          f'Last source captured after close: {t["lastSourceCaptureLagMinutes"]} minutes.',
          f'E5-C observed after close: {t["observedMinutesAfterClosedHour"]} minutes.',
          f'Timeliness: **{t["status"]}**.',
          f'4 contiguous hours all 3 assets (BTC/SOL + ETH): **{c["matchedAcrossBothSources"]}**.',
          "",
          "| Asset | New watch observations | Retest at close | Pending paper entry | Open paper position | Action |",
          "|---|---:|---|---|---|---|",
        ]
        for x in d["sourceAssetPaperObservations"]:
            s=x["sourceAnalysis"]
            rows.append(
                f'| {x["symbol"]} | {s["watchReportedAtThisHour"]} | '
                f'{s["retestPresentAtClose"]} | '
                f'{s["hypotheticalPaperEntryPending"]} | '
                f'{s["hypotheticalPaperPositionOpen"]} | '
                'OBSERVE ONLY |')
    rows+=["","## Important limits",*("- "+x for x in d["limitations"]),"",
           "Only GitHub Actions temporary artifact in a research branch; "
           "no production, legacy paper, user alerts, active automations or freezes changed.",""]
    return "\n".join(rows)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--output",default=str(OUTPUT/"e5c_report.json"))
    args=p.parse_args()
    target=Path(args.output)
    if not str(target).startswith(str(OUTPUT)+"/"):
        raise ValueError("E5C_OUTPUT_MUST_BE_ISOLATED")
    report=audit()
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(report,indent=2,sort_keys=True,ensure_ascii=False)+"\n")
    target.with_suffix(".md").write_text(markdown(report))
    print("ATLAS_E5C_SOURCE_COMMIT_PINNED_HOURLY_READ_ONLY_NO_LIVE_SIGNAL_PASS",flush=True)
    print("E5C_SOURCE_STATUS",report["status"],flush=True)
    if "hourlyObservationTimeliness" in report:
        print("E5C_HOURLY_TIMELINESS",report["hourlyObservationTimeliness"]["status"],flush=True)
        print("E5C_COVERAGE",report["consecutiveHourCoverage"]["matchedAcrossBothSources"],flush=True)
    print("E5C_NEW_LIVE_ENTRY_COUNT",report["actualNewLiveOpportunityCount"],flush=True)

if __name__=="__main__":
    main()
