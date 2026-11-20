#!/usr/bin/env python3
"""GitHub-only, forward-only ZQI V1 research logger.

Run on an external hourly scheduler (for example a NEW GitHub Actions workflow
after explicit approval). Reads market and structure commits from main, and
writes immutable observations/outcomes ONLY to the isolated research branch.
No ChatGPT tasks, Telegram, email, notifications, orders, or paper-account edits.
Uses Python standard library and the frozen V1 scorer.
"""
import base64
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

from zone_quality_forward_shadow_v1 import score_hour, settle_hour, seconds, stamp

REPO = "exchangecurrency11/ATLAS-Quant-Engine"
RESEARCH_BRANCH = "research/atlas-zone-quality-v1-forward-20261121"
SOURCE_REF = "main"
ROOT = "research/forward/zqi_v1"
CUTOFF_MINUTES = 5
FIRST_EVENT_UTC = "2026-11-20T22:00:00Z"


class SourceFailure(Exception):
    pass


def github(method, endpoint, data=None, *, missing_ok=False):
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        raise SourceFailure("GITHUB_TOKEN missing")
    url = "https://api.github.com/repos/" + REPO + endpoint
    headers = {"Authorization": "Bearer " + token,
               "Accept": "application/vnd.github+json",
               "X-GitHub-Api-Version": "2022-11-28",
               "User-Agent": "atlas-zqi-research-v1"}
    body = None
    if data is not None:
        body = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = "application/json"
    try:
        request = urllib.request.Request(url, data=body, headers=headers, method=method)
        with urllib.request.urlopen(request, timeout=25) as res:
            return json.loads(res.read().decode("utf-8"))
    except urllib.error.HTTPError as ex:
        if missing_ok and ex.code == 404:
            return None
        raise SourceFailure("GitHub API %s %s: HTTP %s" %
                            (method, endpoint.split("?")[0], ex.code)) from ex


def path_for(kind, at):
    d = datetime.fromtimestamp(seconds(at), timezone.utc)
    return "%s/%s/%04d/%02d/%02d/%02d00Z.json" % (
        ROOT, kind, d.year, d.month, d.day, d.hour)


def content_at(path, sha_or_branch):
    endpoint = "/contents/" + urllib.parse.quote(path, safe="/") + "?ref=" + urllib.parse.quote(sha_or_branch, safe="")
    item = github("GET", endpoint, missing_ok=True)
    if item is None:
        return None
    if not isinstance(item, dict) or item.get("encoding") != "base64":
        raise SourceFailure("GitHub content encoding not supported: " + path)
    return json.loads(base64.b64decode(item["content"]).decode("utf-8"))


def exists(path):
    return github("GET", "/contents/" + urllib.parse.quote(path, safe="/") +
                  "?ref=" + urllib.parse.quote(RESEARCH_BRANCH, safe=""),
                  missing_ok=True) is not None


def put_once(path, obj, message):
    # NO update (PUT with SHA) is permitted. GitHub will reject same-path races.
    if exists(path):
        return "ALREADY_EXISTS"
    data = json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    github("PUT", "/contents/" + urllib.parse.quote(path, safe="/"),
           {"message": message, "content": base64.b64encode(data.encode("utf-8")).decode("ascii"),
            "branch": RESEARCH_BRANCH})
    if not exists(path):
        raise SourceFailure("Write not confirmed: " + path)
    return "CREATED"


def commit_index(path, as_of_utc, count=40):
    args = urllib.parse.urlencode({"path": path, "until": as_of_utc,
                                  "per_page": min(count, 100)})
    raw = github("GET", "/commits?" + args)
    return [{"sha": v["sha"], "publishedUTC": v["commit"]["committer"]["date"]}
            for v in raw]


def valid_source(index, path, expected_close, cutoff):
    """Choose first commit that actually contains the required closed candle."""
    for item in index:
        publication = seconds(item["publishedUTC"])
        if publication > cutoff or publication < expected_close:
            continue
        doc = content_at(path, item["sha"])
        if not doc or not isinstance(doc.get("results"), list):
            continue
        rows = [x for x in doc["results"] if x.get("interval") == "1hour"
                and x.get("symbol") in ("BTCUSDT_PERP.A", "SOLUSDT_PERP.A")]
        if len(rows) != 2:
            continue
        key = "closeTimeUTC" if path == "market_data.json" else "lastCloseTimeUTC"
        if all(seconds(x[key]) == expected_close and x.get("status") == "READY"
               for x in rows):
            return item, doc
    raise SourceFailure("SOURCE_GAP: no as-of %s for %s" %
                        (path, stamp(expected_close)))


def market_history(candle_closes, *, as_of_utc):
    """Fetch 1H source records, never interpolate a missing hour."""
    commits = commit_index("market_data.json", as_of_utc, 100)
    final_cutoff = seconds(as_of_utc)
    out = []
    for close in candle_closes:
        c, m = valid_source(commits, "market_data.json", close,
                            min(close + CUTOFF_MINUTES * 60, final_cutoff))
        out.append({"sha": c["sha"], "publishedUTC": c["publishedUTC"],
                    "checkedAtUTC": m.get("checkedAtUTC"),
                    "btc": next(x for x in m["results"]
                                if x.get("symbol") == "BTCUSDT_PERP.A" and x.get("interval") == "1hour"),
                    "sol": next(x for x in m["results"]
                                if x.get("symbol") == "SOLUSDT_PERP.A" and x.get("interval") == "1hour")})
    return out


def create_observation(now):
    close = now.replace(minute=0, second=0, microsecond=0).timestamp()
    start = seconds(FIRST_EVENT_UTC)
    if close < start:
        print("NOT_STARTED", stamp(close))
        return
    if not close + 5 * 60 <= now.timestamp() < close + 3600:
        raise SourceFailure("LATE_OBSERVATION: outside recording window")

    when = stamp(close)
    dst = path_for("observations", when)
    err = path_for("errors", when)
    if exists(dst) or exists(err):
        print("OBSERVATION_ALREADY_ACCOUNTED", when)
        return

    cutoff = stamp(close + 5 * 60)
    try:
        mi = commit_index("market_data.json", cutoff, 8)
        si = commit_index("market_structure_data.json", cutoff, 8)
        m_ref, market = valid_source(mi, "market_data.json", close, close + 300)
        s_ref, structure = valid_source(si, "market_structure_data.json", close, close + 300)
        history = []  # do not require ATR source if no BOS/CHoCH in either asset
        for s in structure.get("results", []):
            if s.get("interval") != "1hour" or s.get("symbol") not in ("BTCUSDT_PERP.A","SOLUSDT_PERP.A"):
                continue
            if any(e.get("at") == close - 3600 and e.get("event") in ("BOS", "CHoCH")
                   for e in s.get("structure", [])):
                history = market_history([close - (14 - i) * 3600 for i in range(15)],
                                         as_of_utc=cutoff)
                break
        record = score_hour(
            market, structure, history,
            event_close_utc=when, observed_at_utc=stamp(now.timestamp()),
            start_utc=FIRST_EVENT_UTC, market_sha=m_ref["sha"],
            market_published_utc=m_ref["publishedUTC"], structure_sha=s_ref["sha"],
            structure_published_utc=s_ref["publishedUTC"])
        record["sources"]["publicationProvenanceVerifiedByCaller"] = True
        status = put_once(dst, record, "research(zqi): freeze forward 1H source-pinned observation "+when)
        print(status, dst, record["status"], len(record["events"]))
    except (SourceFailure, ValueError, KeyError, TypeError) as e:
        # Immutable first-error record; cannot substitute for a valid prediction.
        err_record = {"schemaVersion": 1, "recordKind": "FORWARD_SOURCE_ERROR",
                      "eventCloseUTC": when, "observedAtUTC": stamp(now.timestamp()),
                      "reason": str(e), "prospectiveEligible": False}
        print(put_once(err, err_record, "research(zqi): record source failure "+when), err)
        raise


def settle_due(now):
    current_close = now.replace(minute=0, second=0, microsecond=0).timestamp()
    due_close = current_close - 12 * 3600
    if due_close < seconds(FIRST_EVENT_UTC):
        return
    when = stamp(due_close)
    p = path_for("observations", when)
    q = path_for("outcomes", when)
    if exists(q):
        return
    prediction = content_at(p, RESEARCH_BRANCH)
    if not prediction or not prediction.get("events"):
        return
    try:
        closes = [due_close + (i + 1) * 3600 for i in range(12)]
        history = market_history(closes, as_of_utc=stamp(current_close + 300))
        obj = settle_hour(prediction, history, settled_at_utc=stamp(now.timestamp()))
        print(put_once(q, obj, "research(zqi): freeze forward 12h outcome "+when), q)
    except (SourceFailure, ValueError, KeyError, TypeError) as exc:
        path = path_for("errors", when).replace(".json", ".settlement.json")
        err = {"recordKind": "OUTCOME_CENSORED_OR_SOURCE_ERROR", "eventCloseUTC": when,
               "observedAtUTC": stamp(now.timestamp()), "reason": str(exc)}
        print(put_once(path, err, "research(zqi): record censored 12h outcome "+when), path)
        raise


def main():
    now = datetime.now(timezone.utc)
    try:
        create_observation(now)
        settle_due(now)
    except Exception as exc:
        print("FAILED:", str(exc), file=sys.stderr)
        raise


if __name__ == "__main__":
    main()
