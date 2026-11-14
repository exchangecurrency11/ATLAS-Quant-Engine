#!/usr/bin/env python3
"""ATLAS Core E5-D: durable append-only first-seen hourly observation journal.

The inputs are previously committed BTC/SOL & ETH V9.2 research paper
snapshots and V9 closed-market context, not executable exchange fills.
Only source-commit-pinned Git trees/blob SHA may supply observations.
NO live signals, notifications, paper-account edits, frozen candidates,
orders, or changes to existing strategies/automations.

The E5-D code is isolated on a research branch. A main-only scheduler
may checkout this branch, audit, and append ONLY to the E5-D journal.
"""
from __future__ import annotations

import argparse
from datetime import datetime,timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
from urllib.request import Request,urlopen
from unittest.mock import patch

from research.atlas_core_v7 import hourly_cold_observer_e5c as cold

ROOT=Path("forward/atlas_core_e5d_hourly")
OUT=Path("research/atlas_core_v8/output")
MODE="ATLAS_CORE_E5D_APPEND_ONLY_POST_START_HOURLY_OBSERVATION_NO_LIVE_ENTRY"
ACTIVATION_UTC="2026-11-14T22:00:00Z"
SOURCE_CLOSE_MAX_AGE_SEC=90*60
MAX_DIFF_RETRIES=3
SHA40=re.compile(r"^[0-9a-f]{40}$")
TIMESTAMPS=re.compile(r"^20\d\d-(0[1-9]|1[0-2])-[0-3]\dT[0-2]\d-00Z$")
RUN_KEY=re.compile(r"^[1-9][0-9]{0,17}$")
ATTEMPT_KEY=re.compile(r"^[1-9][0-9]{0,3}$")
STAGE="RESEARCH_ONLY"

def norm_epoch(when:str)->int:
    return cold.strict_utc(when)

def format_utc(epoch:int):
    return datetime.fromtimestamp(epoch,timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def date_part(epoch:int):
    return datetime.fromtimestamp(epoch,timezone.utc).strftime("%Y-%m-%d")

def hour_part(epoch:int):
    return datetime.fromtimestamp(epoch,timezone.utc).strftime("%H-00Z")

def secure_fetch(url:str):
    """Strict allowlisted GitHub URL and optionally runner-authenticated read.

    Auth via ephemeral Actions GITHUB_TOKEN increases GitHub API headroom.
    Never log or store it. No POST, no private API scope, no network
    destination outside the original E5-C URL allowlist.
    """
    if not cold._url_allowed(url):
        raise ValueError("E5D_UNAUTHORIZED_GITHUB_SOURCE_URL")
    token=os.environ.get("GITHUB_TOKEN","")
    if token and not re.fullmatch(r"[A-Za-z0-9_\\-]+",token):
        raise ValueError("E5D_UNSAFE_TOKEN_FORMAT")
    headers={"User-Agent":"ATLAS-E5D-ReadOnly-GitHub-Research/1.0",
             "Accept":"application/vnd.github+json" if url.startswith(cold.API) else "application/json",
             "X-GitHub-Api-Version":"2022-11-28"}
    if token:
        headers["Authorization"]="Bearer "+token
    with urlopen(Request(url,headers=headers),timeout=25) as response:
        data=response.read(cold.MAX_BYTES+1)
        if not data or len(data)>cold.MAX_BYTES:
            raise ValueError("E5D_EMPTY_OR_TOO_LARGE_REMOTE_SOURCE")
        return data

def validate_tree_entry(x):
    if not isinstance(x,dict):
        raise ValueError("E5D_GIT_TREE_NOT_AN_ENTRY")
    if not SHA40.fullmatch(x.get("sha","")):
        raise ValueError("E5D_GIT_TREE_MISSING_SHA")
    if not isinstance(x.get("path"),str):
        raise ValueError("E5D_GIT_TREE_NO_PATH")
    return x

def fetch_pinned_tree(ref_sha:str, folder:str, *, fetch=secure_fetch)->dict:
    """Read each Git tree by SHA, never a truncated GitHub contents page.

    GitHub contents/ API silently caps directory listings at ~1,000
    entries; hourly ledgers eventually exceed this. Nonrecursive Git
    trees by path preserve the exact recorded snapshot SHA.
    """
    if not SHA40.fullmatch(ref_sha):
        raise ValueError("E5D_UNPINNED_SOURCE_COMMIT")
    if folder not in (cold.BTC_SOL_DIR,cold.ETH_DIR):
        raise ValueError("E5D_UNAPPROVED_SOURCE_FOLDER")
    tree_sha=ref_sha
    for path_component in [*folder.split("/")]:
        manifest=cold.as_obj(fetch(cold.API+"/git/trees/"+tree_sha))
        if manifest.get("truncated") is True or not isinstance(manifest.get("tree"),list):
            raise ValueError("E5D_GIT_TREE_INCOMPLETE_OR_TRUNCATED")
        matches=[validate_tree_entry(e) for e in manifest["tree"]
                 if isinstance(e,dict) and e.get("path")==path_component]
        if len(matches)!=1 or matches[0].get("type")!="tree":
            raise ValueError("E5D_REQUIRED_SOURCE_TREE_NOT_FOUND")
        tree_sha=matches[0]["sha"]
    listing=cold.as_obj(fetch(cold.API+"/git/trees/"+tree_sha))
    if listing.get("truncated") is True or not isinstance(listing.get("tree"),list):
        raise ValueError("E5D_HOURLY_TREE_TRUNCATED")
    out={}
    for row in listing["tree"]:
        entry=validate_tree_entry(row)
        name=entry["path"]
        match=cold.STAMP_RE.fullmatch(name)
        if match is None:
            raise ValueError("E5D_UNKNOWN_HOURLY_TREE_MEMBER")
        if entry.get("type")!="blob" or entry.get("mode") not in ("100644","100664"):
            raise ValueError("E5D_HOURLY_MEMBER_NOT_A_FILE")
        key=match.group(1)
        expected=datetime.strptime(key,"%Y-%m-%dT%H-00Z").replace(tzinfo=timezone.utc)
        if expected.strftime("%Y-%m-%dT%H-00Z")!=key:
            raise ValueError("E5D_BAD_HOURLY_UTC_NAME")
        if key in out:
            raise ValueError("E5D_DUPLICATE_HOURLY_SOURCE")
        out[key]={"file":folder+"/"+name,"gitBlobSHA1":entry["sha"]}
    if not out:
        raise ValueError("E5D_EMPTY_HOURLY_GIT_TREE")
    return out

def observed_hourly_audit(*,fetch=secure_fetch, now_utc=None):
    # Purely adapt the source-directory listing to a pinned Git Tree.
    # All E5-C trade source, time and candle validators run unchanged.
    def tree_provider(sha,folder,fetch=fetch):
        return fetch_pinned_tree(sha,folder,fetch=fetch)
    with patch.object(cold,"list_hourly",side_effect=tree_provider):
        return cold.audit(fetch=fetch,now_utc=now_utc)

def journal_paths(now_epoch:int,run_id:str,run_attempt:str,source_epoch:int|None):
    if not RUN_KEY.fullmatch(run_id) or not ATTEMPT_KEY.fullmatch(run_attempt):
        raise ValueError("E5D_INVALID_GITHUB_RUN_ID_OR_ATTEMPT")
    attempt=ROOT/"attempts"/date_part(now_epoch)/(
        datetime.fromtimestamp(now_epoch,timezone.utc).strftime("%H-%M-%S")+
        "_run"+run_id+"_try"+run_attempt+".json")
    observation=None
    if source_epoch is not None:
        observation=ROOT/"observations"/date_part(source_epoch)/(hour_part(source_epoch)+".json")
    return attempt,observation

def require_research_json(path:Path):
    try:
        obj=json.loads(path.read_bytes())
    except (OSError,UnicodeError,ValueError) as exc:
        raise ValueError("E5D_EXISTING_JOURNAL_CANNOT_BE_READ") from exc
    if not isinstance(obj,dict) or obj.get("stage")!=STAGE:
        raise ValueError("E5D_EXISTING_JOURNAL_NOT_RESEARCH_ONLY")
    return obj

def strictly_append(path:Path,content:dict):
    """Never overwrite any existing journal file, including same-run retries."""
    if path.exists():
        old=require_research_json(path)
        if old!=content:
            raise ValueError("E5D_IMMUTABLE_JOURNAL_ENTRY_DRIFT:"+str(path))
        return False
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(content,sort_keys=True,ensure_ascii=False,indent=2)+"\n")
    return True

def risk_and_credit_guards(source:dict):
    if source.get("mode")!=cold.MODE or source.get("actualNewLiveOpportunityCount")!=0:
        raise ValueError("E5D_HOURLY_SOURCE_ALLEGES_LIVE_TRADE")
    if not isinstance(source.get("actionSafety"),dict) or source["actionSafety"]!=cold.REJECTED_LIVE_ACTIONS:
        raise ValueError("E5D_SOURCE_ACTION_SAFETY_GUARD_DRIFT")
    if source["status"] not in ("SOURCE_WITNESSES_CHECKED_OBSERVATION_ONLY",
                                "SOURCE_HOURS_DISAGREE_FAIL_CLOSED"):
        raise ValueError("E5D_UNAPPROVED_V92_SOURCE_STATUS")
    if source["status"]=="SOURCE_WITNESSES_CHECKED_OBSERVATION_ONLY":
        if (source.get("newForwardTradesAccrued")!=0
            or source.get("historical51TradesCreditedToForward")!=0
            or source.get("realAccountExposureAvailable") is not False
            or source.get("independentlyExchangeVerifiedSource") is not False
            or source.get("full3AssetLiveSourcePriceStopAndNextOpenValidated") is not False
            or source.get("separateFrozenForwardCandidateBranchesModified") is not False):
            raise ValueError("E5D_SOURCE_FALSE_READY_OR_CREDIT")
        if not isinstance(source.get("sourceFileSHA256"),dict) or set(source["sourceFileSHA256"])!={
            "BTC_SOL_V92","ETH_V92","V9_CONTEXT"}:
            raise ValueError("E5D_NOT_THREE_PUBLISHER_DOCUMENTS")
        if not isinstance(source.get("sourceAssetPaperObservations"),list) or {
            x["symbol"] for x in source["sourceAssetPaperObservations"]}!={"BTCUSDT","ETHUSDT","SOLUSDT"}:
            raise ValueError("E5D_MISSING_THREE_ASSETS")
        if (source["hourlyObservationTimeliness"]["liveEntryEligible"] is not False
            or source["hourlyObservationTimeliness"]["entryAtExactOpeningPriceVerified"] is not False):
            raise ValueError("E5D_FALSE_EXECUTION_PERMISSION")
    return True

def admission(source,when:int,activation:int):
    """Gate prospective journal by *first observed* time, not historical date."""
    risk_and_credit_guards(source)
    if source["status"]!="SOURCE_WITNESSES_CHECKED_OBSERVATION_ONLY":
        return "SOURCE_HOURS_MISMATCH_FAIL_CLOSED",None
    v=source["hourlyObservationTimeliness"]
    t=norm_epoch(v["latestClosedCandleUTC"])
    captured=norm_epoch(v["latestSourceCaptureUTC"])
    if t>when or captured>when:
        raise ValueError("E5D_FUTURE_SOURCE_STATE")
    if t<activation:
        return "SOURCE_HOUR_PRE_FIRST_SEEN_ACTIVATION_NOT_CREDITED",None
    if when-t>SOURCE_CLOSE_MAX_AGE_SEC:
        return "SOURCE_HOUR_STALE_OVER_90MIN_NOT_CREDITED",None
    if source["sourceIntegrityChecks"].get("independentExchangeNativeTruthEstablished") is not False:
        raise ValueError("E5D_INDEPENDENT_EXCHANGE_ASSERTION_CHANGED")
    if source["sourceIntegrityChecks"].get("BTC_SOL_1H_4H_Daily_OHLCVMatches") is not True:
        raise ValueError("E5D_CROSS_SOURCE_PARITY_MISSING")
    if source["consecutiveHourCoverage"]["matchedAcrossBothSources"] and (
       source["consecutiveHourCoverage"]["verifiedContentsWithGitBlobSHA1"]!=8):
        raise ValueError("E5D_CONSECUTIVE_HOURS_NOT_CONTENT_VERIFIED")
    return "NEW_POST_ACTIVATION_HOURLY_SOURCE_OBSERVED_NOT_ENTRY",t

def gap_watch(root:Path,stamp:int):
    """Detect explicitly missed source hours from immutable journal files."""
    parent=root/"observations"
    stamps=[]
    if parent.exists():
        for day in parent.iterdir():
            if not day.is_dir():continue
            for saved in day.glob("*-00Z.json"):
                old=require_research_json(saved)
                if old.get("classification")!="READ_ONLY_PAPER_OBSERVATION":
                    raise ValueError("E5D_PRIOR_OBSERVATION_CLASSIFICATION_DRIFT")
                ts=norm_epoch(old["sourceClosedHourUTC"])
                if saved!=parent/date_part(ts)/(hour_part(ts)+".json"):
                    raise ValueError("E5D_PRIOR_OBSERVATION_PATH_DATE_TAMPER")
                if ts>=stamp:
                    # Same-hour can already exist, but no future hour accepted.
                    if ts>stamp:
                        raise ValueError("E5D_JOURNAL_HAS_FUTURE_OBSERVATION")
                    continue
                stamps.append(ts)
    if len(stamps)!=len(set(stamps)):
        raise ValueError("E5D_DUPLICATE_PRIOR_HOURLY_JOURNAL")
    if not stamps:
        return {"previousObservedHourUTC":None,
                "missingClosedHoursSincePrevious":None,
                "historyMaturedEnoughForGapAssessment":False}
    last=max(stamps)
    delta=(stamp-last)//3600
    if delta<=0:
        raise ValueError("E5D_NONMONOTONIC_FIRST_SEEN_COHORT")
    return {"previousObservedHourUTC":format_utc(last),
            "missingClosedHoursSincePrevious":delta-1,
            "historyMaturedEnoughForGapAssessment":True}

def create_first_seen(source:dict, *,now_epoch:int,run_id:str,run_attempt:str,
                      activation_epoch:int,root:Path=ROOT,write=True):
    """Returns current-run receipt. Every attempt recorded; only legitimate
    post-start hourly paper-source observations admitted (not signals).
    """
    stage_status,t=admission(source,now_epoch,activation_epoch)
    apath,opath=journal_paths(now_epoch,run_id,run_attempt,t)
    # Preserve caller-supplied target root for synthetic tests.
    attempt=root/apath.relative_to(ROOT)
    observed=root/opath.relative_to(ROOT) if opath else None
    new_observation=False
    duplicate=False
    metadata={}
    if t is not None:
        timeliness=source["hourlyObservationTimeliness"]
        proof=source["sourceIntegrityChecks"]
        meta=gap_watch(root,t)
        if source["consecutiveHourCoverage"]["matchedAcrossBothSources"]:
            sha_count=source["consecutiveHourCoverage"]["verifiedContentsWithGitBlobSHA1"]
        else:
            sha_count=source["consecutiveHourCoverage"]["verifiedContentsWithGitBlobSHA1"]
        obs={
            "stage":STAGE,
            "classification":"READ_ONLY_PAPER_OBSERVATION",
            "engine":"E5D",
            "firstSeenUTC":format_utc(now_epoch),
            "sourceClosedHourUTC":timeliness["latestClosedCandleUTC"],
            "sourceCapturedAtUTC":timeliness["latestSourceCaptureUTC"],
            "sourceCommits":source["sourceGitCommits"],
            "sourceSHA256":source["sourceFileSHA256"],
            "crossWitnesseOHLCVProof":proof,
            "sourceCaptureLagMinutes":timeliness["lastSourceCaptureLagMinutes"],
            "firstSeenLagMinutes":timeliness["observedMinutesAfterClosedHour"],
            "completeFourHourSourceChain":source["consecutiveHourCoverage"]["matchedAcrossBothSources"],
            "checkedRecentHourlyFileContents":sha_count,
            "newClosedBOSWatchReports":source["newBOSWatchReports"],
            "newSelectedRetestReports":source["newSelectedPaperRetestReports"],
            "pendingHypotheticalPaperEntryReports":source["pendingHypotheticalPaperEntryReports"],
            "assetObservations":source["sourceAssetPaperObservations"],
            "missingSourceHoursSincePreviousRecorded":meta["missingClosedHoursSincePrevious"],
            "historyMaturedEnoughForGapAssessment":meta["historyMaturedEnoughForGapAssessment"],
            "notAnExchangeFill":True,"notAnEntryTimeTradeAlert":True,
            "noBrokerOrders":True,"noUserAlerts":True,
            "noProductionOrAccountWrites":True,
            "noFrozenCandidatePromotion":True,
            "historical51NotForward":True,
            "noRealAccountExposure":True,
            "notIndependentBinanceTruth":True,
            "userMustNotTradeFromThisRecord":True,
            "evidenceRunId":run_id,
            "evidenceRunAttempt":run_attempt,
        }
        if observed.exists():
            prior=require_research_json(observed)
            if (prior.get("classification")!="READ_ONLY_PAPER_OBSERVATION"
                or prior.get("sourceClosedHourUTC")!=obs["sourceClosedHourUTC"]
                or prior.get("notAnExchangeFill") is not True
                or prior.get("noBrokerOrders") is not True
                or prior.get("notAnEntryTimeTradeAlert") is not True):
                raise ValueError("E5D_EXISTING_SOURCE_OBSERVATION_DRIFT")
            duplicate=True
            stage_status="EXISTING_IMMUTABLE_POST_ACTIVATION_OBSERVATION_NO_REWRITE"
        else:
            if write:
                strictly_append(observed,obs)
            new_observation=True
        metadata={
            "sourceClosedHourUTC":obs["sourceClosedHourUTC"],
            "sourceCapturedAtUTC":obs["sourceCapturedAtUTC"],
            "firstSeenUTC":obs["firstSeenUTC"],
            "verifiedRecentSourceFileCount":sha_count,
            "completeFourHourSourceChain":obs["completeFourHourSourceChain"],
            "sourceCaptureLagMinutes":obs["sourceCaptureLagMinutes"],
            "firstSeenLagMinutes":obs["firstSeenLagMinutes"],
            "missingSourceHoursSincePreviousRecorded":obs["missingSourceHoursSincePreviousRecorded"],
        }
    attempt_body={
        "stage":STAGE,
        "classification":"E5D_HOURLY_CHECKPOINT_ONLY",
        "runId":run_id,
        "runAttempt":run_attempt,
        "checkUTC":format_utc(now_epoch),
        "activationUTC":format_utc(activation_epoch),
        "sourceState":source["status"],
        "admission":stage_status,
        "observationFile":str(observed) if observed else None,
        "newObservationWritten":bool(new_observation),
        "existingObservationReused":bool(duplicate),
        "notARealTradingSignal":True,
        "noRealOrdersOrNotifications":True,
        "noSourceDataBackfilled":True,
        "inputSourceCommitPins":source["sourceGitCommits"],
        "whenAvailable":metadata,
    }
    if write:
        strictly_append(attempt,attempt_body)
    return {"status":stage_status,
            "checkpointPath":str(attempt),
            "observationPath":str(observed) if observed else None,
            "newObservation":new_observation,
            "reusedImmutableObservation":duplicate,
            "metadata":metadata}

def produce(*,now_utc=None,run_id=None,run_attempt=None,root=ROOT,fetch=secure_fetch,
            write=True,activation_utc=ACTIVATION_UTC):
    current=norm_epoch(now_utc) if now_utc else int(datetime.now(timezone.utc).timestamp())
    run_id=run_id or os.environ.get("GITHUB_RUN_ID")
    run_attempt=run_attempt or os.environ.get("GITHUB_RUN_ATTEMPT","1")
    if not run_id:
        raise ValueError("E5D_RUN_ID_REQUIRED_FOR_APPEND_ONLY_AUDIT")
    activation=norm_epoch(activation_utc)
    source=observed_hourly_audit(fetch=fetch,now_utc=format_utc(current))
    outcome=create_first_seen(source,now_epoch=current,
                               activation_epoch=activation,
                               run_id=run_id,run_attempt=run_attempt,
                               root=root,write=write)
    return {
        "mode":MODE,
        "runUTC":format_utc(current),
        "activatedUTC":activation_utc,
        "onlyResearchDataWritten":True,
        "readOnlyFrozenSource":True,
        "automaticOrdersOrAlertsSent":False,
        "newLiveSignalCount":0,
        "originalCryptoAutomationsChanged":False,
        "paperAccountStateReadOrModified":False,
        "userPositionsAccessed":False,
        "output":outcome,
        "source":source,
        "sourceGitHubWorkflowIsCronOnMainOnly":True,
        "limitations":[
            "Only a time-stamped audit of previously saved V92 paper snapshots; not independently native Binance futures market data.",
            "GitHub scheduler may delay or skip runs; attempts are journaled only if a runner executes.",
            "Signals captured after exact 1H OPEN can never be backdated as executable entries.",
            "A completed source candle is already in the past by the observation capture time; no historical-fill approximation is certified.",
            "A source-branch ref can move; source Git commit and file blobs are pinned for each run, not a signed independent oracle.",
            "No connected user account position inventory, no orderbook or actual spread or mark price.",
        ]
    }

def markdown(result):
    out=result["output"]
    src=result["source"]
    lines=["# ATLAS E5-D — isolated appended hourly cold observation",
           "",
           "**No signal, order, user alert or automatic trading action.**",
           "",f'Run observed at: {result["runUTC"]}',
           f'Start boundary: {result["activatedUTC"]}',
           f'Journal status: **{out["status"]}**.',
           f'New immutable observation: **{out["newObservation"]}**.',
           f'Original source status: {src["status"]}.',
           f'Live signals validated: **{result["newLiveSignalCount"]}**.',
           "",
           "## Data quality", ""]
    if "hourlyObservationTimeliness" in src:
        st=src["hourlyObservationTimeliness"]
        lines.extend([
            f'Original hourly close: {st["latestClosedCandleUTC"]}',
            f'Original source capture lag: {st["lastSourceCaptureLagMinutes"]} minutes',
            f'Observer read lag: {st["observedMinutesAfterClosedHour"]} minutes',
            f'Four previous hours backed by verified file bytes: {src["consecutiveHourCoverage"]["matchedAcrossBothSources"]}',
            f'Original clock-late classification: {st["status"]}',
        ])
    lines+=["", "## Limits", *("- "+a for a in result["limitations"]),""]
    return "\n".join(lines)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--report-out",default=str(OUT/"e5d_report.json"))
    parser.add_argument("--no-write",action="store_true")
    options=parser.parse_args()
    output=Path(options.report_out)
    if not str(output).startswith(str(OUT)+"/"):
        raise ValueError("E5D_REPORT_OUTSIDE_RESEARCH")
    doc=produce(write=not options.no_write)
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(doc,sort_keys=True,ensure_ascii=False,indent=2)+"\n")
    output.with_suffix(".md").write_text(markdown(doc))
    print("ATLAS_E5D_PERMANENT_RESEARCH_JOURNAL_NO_LIVE_SIGNAL_OR_ORDER_PASS",flush=True)
    print("E5D_FIRST_SEEN_RESULT",doc["output"]["status"],flush=True)
    print("E5D_SOURCE_STATUS",doc["source"]["status"],flush=True)
    print("E5D_STORED_NEW_OBSERVATION",doc["output"]["newObservation"],flush=True)
    print("E5D_LIVE_SIGNALS",doc["newLiveSignalCount"],flush=True)

if __name__=="__main__":
    main()
