#!/usr/bin/env python3
"""E5-G: GitHub source-hour health observability, NOT market data or trading.

Run-time Git commit pins + Git tree metadata prove that a filename existed
at check time; they DO NOT prove OHLCV payload, source-native exchange parity,
executable fills, an original live warning, or strategy profitability.
Read-only audit; standalone writer handles append-only research journal.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

REPO="exchangecurrency11/ATLAS-Quant-Engine"
API="https://api.github.com/repos/"+REPO
MODE="ATLAS_E5G_SOURCE_HEALTH_GITHUB_METADATA_ONLY_RESEARCH"
STAGE="RESEARCH_ONLY_NO_LIVE_OR_FORWARD_CREDIT"
SOURCE_CONFIG={
 "V7_BTC_SOL":("experiment/v7-signal-quality-20261103","forward/snapshots","v7-hourly-trigger.yml"),
 "V7_ETH":("experiment/v7-signal-quality-20261103","forward/eth/snapshots","eth-v7-hourly-trigger.yml"),
 "V91_BTC_SOL":("research/v9-prestart-live-data-compatibility-20261111","forward/v91_prospective_retest/hourly","v91-prospective-hourly-shadow.yml"),
 "V91_ETH":("research/v9-prestart-live-data-compatibility-20261111","forward/v91_eth_prospective_retest/hourly","v91-eth-prospective-hourly-shadow.yml"),
 "V92_BTC_SOL":("research/v92-bull-bear-candle-invalidation-20261112","forward/v92_prospective_selected/hourly","v92-selected-prospective-third-paper.yml"),
 "V92_ETH":("research/v92-bull-bear-candle-invalidation-20261112","forward/v92_prospective_eth/hourly","v92-eth-prospective-third-paper.yml"),
 "V9_THREE_ASSET":("research/v9-prestart-live-data-compatibility-20261111","forward/v9_next_4h_color/hourly/snapshots","v9-hourly-three-asset-context.yml"),
}
E5D_BRANCH="research/atlas-core-v8b-journal-audit-20261115"
E5D_PATH="forward/atlas_core_e5d_hourly/observations"
E5D_WORKFLOW="atlas-e5d-silent-hourly-observer.yml"
DEPENDENCIES={
 "V7_BTC_SOL":(),"V7_ETH":(),"V9_THREE_ASSET":(),
 "V91_BTC_SOL":("V7_BTC_SOL",),
 "V91_ETH":("V7_ETH",),
 "V92_BTC_SOL":("V7_BTC_SOL","V91_BTC_SOL"),
 "V92_ETH":("V7_ETH","V91_ETH"),
 "E5D":("V92_BTC_SOL","V92_ETH","V9_THREE_ASSET"),
}
STAGES=tuple(SOURCE_CONFIG)+("E5D",)
SHA40=re.compile(r"^[a-f0-9]{40}$")
STAMP=re.compile(r"^20\d\d-\d\d-\d\dT\d\d-00Z\.json$")
DATE=re.compile(r"^20\d\d-\d\d-\d\d$")
HOUR=re.compile(r"^\d\d-00Z\.json$")
RUNID=re.compile(r"^[1-9]\d{0,17}$")
MAX_BYTES=5_000_000
WINDOW_HOURS=12
GRACE_MINUTES=75
MAX_HOUR_AGE_DAYS=5
NO_REDIRECT=build_opener(type("BlockRedirect",(HTTPRedirectHandler,),{
 "redirect_request":lambda self,req,fp,code,msg,headers,newurl:None
})())

def iso(dt):
    if dt.tzinfo is None:raise ValueError("E5G_TIME_NOT_TZ_AWARE")
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def parse_time(value):
    if not isinstance(value,str) or not re.fullmatch(r"20\d\d-\d\d-\d\dT\d\d:\d\d:\d\dZ",value):
        raise ValueError("E5G_NOT_UTC_TIMESTAMP")
    parsed=datetime.strptime(value,"%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    if iso(parsed)!=value:raise ValueError("E5G_NOT_CANONICAL_UTC_TIMESTAMP")
    return parsed

def fetch_github(url):
    parsed=urlsplit(url)
    if (parsed.scheme!="https" or parsed.hostname!="api.github.com" or
        parsed.port is not None or parsed.username or parsed.password or parsed.fragment or
        not parsed.path.startswith("/repos/"+REPO+"/")):
        raise ValueError("E5G_UNAUTHORIZED_REMOTE_URL")
    # No remote host except GitHub API, read-only GET only. Restrict path family.
    suffix=parsed.path[len("/repos/"+REPO+"/"):]
    if not (suffix.startswith("branches/") or suffix.startswith("git/trees/") or
            suffix.startswith("actions/workflows/")):
        raise ValueError("E5G_UNAPPROVED_GITHUB_API_PATH")
    token=os.environ.get("GITHUB_TOKEN","")
    if token and (len(token)>4096 or not all(33<=ord(c)<=126 for c in token)):
        raise ValueError("E5G_UNSAFE_GITHUB_TOKEN_FORMAT")
    headers={"Accept":"application/vnd.github+json",
             "User-Agent":"ATLAS-E5G-Hourly-Health-Read-Only",
             "X-GitHub-Api-Version":"2022-11-28"}
    if token:headers["Authorization"]="Bearer "+token
    with NO_REDIRECT.open(Request(url,headers=headers,method="GET"),timeout=30) as response:
        raw=response.read(MAX_BYTES+1)
    if not raw or len(raw)>MAX_BYTES:
        raise ValueError("E5G_GITHUB_API_RESPONSE_EMPTY_OR_OVERSIZE")
    return raw

def obj(raw):
    try:d=json.loads(raw)
    except (ValueError,UnicodeError) as exc:raise ValueError("E5G_BAD_GITHUB_JSON") from exc
    if not isinstance(d,dict):raise ValueError("E5G_NOT_OBJECT")
    return d

def branch_pin(branch,fetch=fetch_github):
    if branch not in {x[0] for x in SOURCE_CONFIG.values()}|{E5D_BRANCH}:
        raise ValueError("E5G_UNAPPROVED_SOURCE_BRANCH")
    r=obj(fetch(API+"/branches/"+quote(branch,safe="")))
    sha=r.get("commit",{}).get("sha")
    if not isinstance(sha,str) or not SHA40.fullmatch(sha):
        raise ValueError("E5G_GIT_BRANCH_NOT_PINNED")
    return sha

def git_tree(sha,fetch=fetch_github,cache=None):
    if not isinstance(sha,str) or not SHA40.fullmatch(sha):
        raise ValueError("E5G_UNTRUSTED_GIT_TREE_SHA")
    if cache is not None and sha in cache:return cache[sha]
    t=obj(fetch(API+"/git/trees/"+sha))
    if t.get("truncated") is not False or not isinstance(t.get("tree"),list):
        raise ValueError("E5G_TRUNCATED_OR_UNREADABLE_GIT_TREE")
    result=t["tree"]
    for member in result:
        if (not isinstance(member,dict) or not isinstance(member.get("path"),str)
            or not isinstance(member.get("sha"),str) or
            not SHA40.fullmatch(member["sha"]) or
            member.get("type") not in ("blob","tree")):
            raise ValueError("E5G_UNVERIFIED_GIT_TREE_MEMBER")
    if cache is not None:cache[sha]=result
    return result

def walk_tree(commit,folder,fetch=fetch_github,cache=None,optional=False):
    if (folder not in {x[1] for x in SOURCE_CONFIG.values()}|{E5D_PATH} and
        not (folder.startswith(E5D_PATH+"/") and DATE.fullmatch(folder.split("/")[-1]))):
        raise ValueError("E5G_UNAPPROVED_SOURCE_FOLDER")
    sha=commit
    for part in folder.split("/"):
        matches=[e for e in git_tree(sha,fetch,cache)
                 if e["path"]==part and e["type"]=="tree"]
        if len(matches)!=1:
            if optional and not matches:return None
            raise ValueError("E5G_REQUIRED_GIT_TREE_MISSING:"+part)
        sha=matches[0]["sha"]
    return {"treeSHA1":sha,"entries":git_tree(sha,fetch,cache)}

def regular_entries(bundle,allow_markdown=False):
    out={}
    for item in bundle["entries"]:
        path=item["path"]
        if allow_markdown and path.endswith(".md") and STAMP.fullmatch(path[:-3]+".json"):
            continue
        if (not STAMP.fullmatch(path) or item["type"]!="blob"
            or item.get("mode")!="100644"):
            raise ValueError("E5G_NON_HOURLY_OR_NON_BLOB_SOURCE_MEMBER")
        time=parse_time(path.replace("-00Z.json",":00:00Z"))
        out[iso(time)]=item["sha"]
    return out

def e5d_entries(commit,cohort,fetch=fetch_github,cache=None):
    root=walk_tree(commit,E5D_PATH,fetch,cache,optional=True)
    if root is None:return {"treeSHA1":None,"files":{}}
    dates={d.date().isoformat() for d in cohort}
    entries={}
    for date in dates:
        found=[x for x in root["entries"] if x["path"]==date and x["type"]=="tree"]
        if not found:continue
        if len(found)!=1:raise ValueError("E5G_DUPLICATE_E5D_DAY_TREE")
        files=git_tree(found[0]["sha"],fetch,cache)
        for item in files:
            if item["type"]!="blob" or item.get("mode")!="100644" or not HOUR.fullmatch(item["path"]):
                raise ValueError("E5G_BAD_E5D_OBSERVATION_MEMBER")
            t=parse_time(date+"T"+item["path"].replace("-00Z.json",":00:00Z"))
            entries[iso(t)]=item["sha"]
    return {"treeSHA1":root["treeSHA1"],"files":entries}

def workflow_runs(workflow,start,now,fetch=fetch_github):
    if workflow not in {x[2] for x in SOURCE_CONFIG.values()}|{E5D_WORKFLOW}:
        raise ValueError("E5G_UNAPPROVED_WORKFLOW")
    # GitHub's official workflow-specific run endpoint supports created range.
    # Include +1 hour after evaluated close so queued jobs may finish later.
    earliest=start
    query=urlencode({"branch":"main","per_page":100,
                     "created":iso(earliest)+".."+iso(now)})
    url=API+"/actions/workflows/"+workflow+"/runs?"+query
    data=obj(fetch(url))
    arr=data.get("workflow_runs")
    if not isinstance(arr,list) or not isinstance(data.get("total_count"),int):
        raise ValueError("E5G_UNVERIFIABLE_WORKFLOW_RUN_HISTORY")
    if data["total_count"]>100:
        raise ValueError("E5G_WORKFLOW_RUN_HISTORY_PAGINATION_TRUNCATED")
    out={}
    for item in arr:
        rid=item.get("id")
        if not isinstance(rid,int) or rid<=0:
            raise ValueError("E5G_BAD_WORKFLOW_RUN_ID")
        at=parse_time(item.get("created_at"))
        if at<earliest or at>now+timedelta(minutes=5):
            raise ValueError("E5G_OUT_OF_FILTER_TIME_WORKFLOW_RUN")
        if item.get("head_branch")!="main":
            raise ValueError("E5G_WORKFLOW_RUN_BRANCH_NOT_MAIN")
        event=item.get("event")
        if event not in ("schedule","workflow_run","workflow_dispatch","push"):
            raise ValueError("E5G_UNEXPECTED_GITHUB_EVENT")
        if item.get("status") not in ("queued","in_progress","completed","waiting","requested","pending"):
            raise ValueError("E5G_UNEXPECTED_RUN_STATUS")
        result=item.get("conclusion")
        if result not in (None,"success","failure","cancelled","skipped","timed_out",
                          "action_required","neutral","stale","startup_failure"):
            raise ValueError("E5G_UNEXPECTED_GITHUB_RESULT")
        hour=at.replace(minute=0,second=0,microsecond=0)
        out.setdefault(iso(hour),[]).append({
            "id":rid,"createdAtUTC":iso(at),"event":event,
            "status":item["status"],"conclusion":result,
        })
    return out

def mature_window(now,lookback=WINDOW_HOURS):
    if now.tzinfo is None or not 1<=lookback<=24:
        raise ValueError("E5G_INVALID_WINDOW")
    now=now.astimezone(timezone.utc)
    last=(now-timedelta(minutes=GRACE_MINUTES)).replace(minute=0,second=0,microsecond=0)
    if (now-last)>timedelta(days=MAX_HOUR_AGE_DAYS):
        raise ValueError("E5G_STALE_WINDOW")
    return [last-timedelta(hours=i) for i in range(lookback-1,-1,-1)]

def diagnosis(stage,when,files,run_by_hour,existing,run_history_known=True):
    at=iso(when)
    if at in files[stage]:
        return "SNAPSHOT_PRESENT_METADATA_ONLY"
    absent=[d for d in DEPENDENCIES[stage] if at not in files[d]]
    if absent:return "UPSTREAM_SAME_HOUR_SOURCE_ABSENT"
    if not run_history_known:return "WORKFLOW_HISTORY_UNAVAILABLE"
    runs=run_by_hour.get(stage,{}).get(at,[])
    if not runs:return "NO_WORKFLOW_RUN_SEEN_IN_HOUR"
    if any(x["status"] in ("queued","in_progress","waiting","requested","pending") for x in runs):
        return "RUN_NOT_FINISHED_NO_SNAPSHOT"
    if any(x["conclusion"]=="success" for x in runs):
        return "GREEN_WORKFLOW_BUT_NO_SNAPSHOT"
    if any(x["conclusion"] in ("failure","timed_out","startup_failure") for x in runs):
        return "FAILED_WORKFLOW_NO_SNAPSHOT"
    return "SKIPPED_CANCELLED_OR_NON_SUCCESS_NO_SNAPSHOT"

def summarize(*,now,cohort,files,run_by_hour,commit_pins,tree_pins,run_id):
    if not RUNID.fullmatch(str(run_id)) or len(cohort)!=WINDOW_HOURS:
        raise ValueError("E5G_BAD_FIXED_WINDOW_OR_RUN")
    for stage in STAGES:
        if stage not in files or stage not in run_by_hour:
            raise ValueError("E5G_UNVERIFIED_STAGE_INPUT")
    expected_keys=[iso(dt) for dt in cohort]
    rows=[]
    for dt in cohort:
        at=iso(dt)
        statuses={stage:diagnosis(stage,dt,files,run_by_hour,files) for stage in STAGES}
        runs={stage:run_by_hour[stage].get(at,[])[:8] for stage in STAGES}
        missing_upstream={stage:[d for d in DEPENDENCIES[stage] if at not in files[d]]
                          for stage in STAGES if at not in files[stage]}
        complete=all(at in files[stage] for stage in SOURCE_CONFIG)
        rows.append({
            "closedHourUTC":at,"statuses":statuses,
            "sameHourWorkflowRuns":runs,"missingDependencies":missing_upstream,
            "allSevenSourceFilesPresent":complete,
            "e5dJournalFilePresent":at in files["E5D"],
        })
    latest={stage:max(files[stage]) if files[stage] else None for stage in STAGES}
    missing={stage:sum(iso(x) not in files[stage] for x in cohort) for stage in STAGES}
    status_counts={stage:{name:sum(row["statuses"][stage]==name for row in rows)
                           for name in sorted({row["statuses"][stage] for row in rows})}
                   for stage in STAGES}
    complete=sum(row["allSevenSourceFilesPresent"] for row in rows)
    entries=sum(row["e5dJournalFilePresent"] for row in rows)
    green=sum(sum(status=="GREEN_WORKFLOW_BUT_NO_SNAPSHOT"
                  for status in row["statuses"].values()) for row in rows)
    observed_sources=complete==len(cohort)
    state="ALL_12_SOURCE_HOURS_FILE_PRESENT_METADATA_ONLY" if observed_sources else "INCOMPLETE_12_HOUR_SOURCE_PRESENCE"
    return {
        "mode":MODE,"stage":STAGE,"status":state,
        "auditedAtUTC":iso(now),"githubRunId":str(run_id),
        "lookbackClosedHours":len(cohort),"graceMinutesAfterClose":GRACE_MINUTES,
        "windowFirstClosedHourUTC":expected_keys[0],
        "windowLastClosedHourUTC":expected_keys[-1],
        "sourceCommitPins":commit_pins,
        "sourceTreeSHA1":tree_pins,
        "latestSourceClosedHourUTCByStage":latest,
        "missingSourceHoursByStage":missing,
        "sourceHealthStatusCounts":status_counts,
        "allSevenSourcesFilePresentHours":complete,
        "e5dJournalPresentHours":entries,
        "greenWorkflowWithoutSourceFileCount":green,
        "hourlyMatrix":rows,
        "interpretation":"GitHub immutable tree file-presence + workflow metadata only; a successful Actions run may skip source capture. Missing runs are not proof Github scheduled a trigger then dropped it.",
        "sourceFilePayloadContentValidated":False,
        "independentlyExchangeVerifiedOHLCV":False,
        "liveEntrySignalValid":False,
        "prospectivePerformanceOrTradeCredited":False,
        "historicalE5FRecoveryCountedAsTimely":False,
        "realOrdersOrAlertsEmitted":False,
        "existingProductionForwardSpecsOrAutomationsChanged":False,
    }

def audit(*,now=None,fetch=fetch_github,run_id=None):
    now=now or datetime.now(timezone.utc)
    cohort=mature_window(now)
    pins={}
    cache={}
    for branch,*_ in SOURCE_CONFIG.values():
        if branch not in pins:pins[branch]=branch_pin(branch,fetch)
    pins[E5D_BRANCH]=branch_pin(E5D_BRANCH,fetch)
    files={};trees={}
    for stage,(branch,folder,workflow) in SOURCE_CONFIG.items():
        listing=walk_tree(pins[branch],folder,fetch,cache)
        files[stage]=regular_entries(listing,allow_markdown=(stage=="V9_THREE_ASSET"))
        trees[stage]=listing["treeSHA1"]
    journal=e5d_entries(pins[E5D_BRANCH],cohort,fetch,cache)
    files["E5D"]=journal["files"];trees["E5D"]=journal["treeSHA1"]
    runs={}
    for stage,(_,_,workflow) in SOURCE_CONFIG.items():
        runs[stage]=workflow_runs(workflow,cohort[0],now,fetch)
    runs["E5D"]=workflow_runs(E5D_WORKFLOW,cohort[0],now,fetch)
    return summarize(now=now,cohort=cohort,files=files,run_by_hour=runs,
                     commit_pins=pins,tree_pins=trees,run_id=run_id)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--run-id",required=True)
    p.add_argument("--output",default="e5g_payload/health.json")
    options=p.parse_args()
    if options.output!="e5g_payload/health.json":
        raise ValueError("E5G_REPORT_MUST_STAY_RESEARCH_PAYLOAD_ONLY")
    doc=audit(run_id=options.run_id)
    target=Path(options.output)
    target.parent.mkdir(parents=True,exist_ok=True)
    with target.open("x",encoding="utf-8") as f:
        json.dump(doc,f,ensure_ascii=False,sort_keys=True,indent=2)
        f.write("\n")
    print("ATLAS_E5G_METADATA_ONLY_HEALTH_NO_TRADES",doc["status"])
    print("ATLAS_E5G_WINDOW",doc["windowFirstClosedHourUTC"],doc["windowLastClosedHourUTC"])
    print("ATLAS_E5G_SEVEN_SOURCE_COMPLETE",doc["allSevenSourcesFilePresentHours"],"of",doc["lookbackClosedHours"])
    print("ATLAS_E5G_JOURNAL_PRESENT",doc["e5dJournalPresentHours"],"of",doc["lookbackClosedHours"])
    print("ATLAS_E5G_GREEN_BUT_NO_FILE",doc["greenWorkflowWithoutSourceFileCount"])
    print("ATLAS_E5G_NO_LIVE_ALERT_OR_ORDER",doc["realOrdersOrAlertsEmitted"])

if __name__=="__main__":main()
