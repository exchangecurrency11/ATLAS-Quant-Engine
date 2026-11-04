#!/usr/bin/env python3
"""Point-in-time V7 observation coverage ledger (NO market data, NO orders).

A missing GitHub snapshot is NOT a valid no-trade observation. This script writes
explicit MISSED_OBSERVATION markers for PAST hours only, never manufactures
a forward observation, prices, technical signals, fills or trading results.
"""
import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

UTC = timezone.utc
START_UTC = datetime(2026, 11, 3, 16, tzinfo=UTC)
HOUR = timedelta(hours=1)
CLOSED_STATUS = ("VERIFIED_PAPER_OBSERVATION", "DATA_REJECTED", "DATA_FETCH_FAILED")


def parse_utc(value):
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None or dt.utcoffset() != timedelta(0):
        raise ValueError("Expected UTC timestamp")
    if (dt.minute, dt.second, dt.microsecond) != (0, 0, 0):
        raise ValueError("Hour target must be on the hour")
    return dt


def file_stamp(target):
    return target.strftime("%Y-%m-%dT%H-00Z")


def utc_text(value):
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


def audit_coverage(snapshots_path, missed_path, *, target,
                   discovered_at, start=START_UTC):
    """Mark missing prior hours; never mark the currently targeted hour early."""
    if start.utcoffset() != timedelta(0) or target.utcoffset() != timedelta(0):
        raise ValueError("UTC required")
    if start > target:
        raise ValueError("Target before experiment began")
    if discovered_at < target:
        raise ValueError("Cannot discover future-hour status")
    snapshots_path = Path(snapshots_path)
    missed_path = Path(missed_path)
    missed_path.mkdir(parents=True, exist_ok=True)
    summary = {
        "mode": "V7_PAPER_FORWARD_COVERAGE_NOT_TRADE_PERFORMANCE",
        "checkedAtUTC": utc_text(discovered_at),
        "startClosedHourUTC": utc_text(start),
        "upToExcludingUTC": utc_text(target),
        "expectedPriorHours": 0,
        "verifiedSnapshots": 0,
        "rejectedOrFetchFailedSnapshots": 0,
        "missingHourMarkers": 0,
        "invalidSnapshots": 0,
        "newMissingMarkers": 0,
        "snapshotStatusCounts": {},
        "note": "A missing-hour marker is NOT a market analysis or 0-signal observation.",
    }
    time = start
    while time < target:
        summary["expectedPriorHours"] += 1
        key = file_stamp(time)
        snap = snapshots_path / (key + ".json")
        marker = missed_path / (key + ".json")
        if snap.exists():
            try:
                obj = json.loads(snap.read_text(encoding="utf-8"))
                status = obj.get("status", "UNKNOWN")
                if obj.get("targetClosed1HUTC") != utc_text(time):
                    status = "INVALID_SNAPSHOT_TIME"
            except (ValueError, TypeError, OSError):
                status = "UNREADABLE_SNAPSHOT"
            summary["snapshotStatusCounts"][status] = (
                summary["snapshotStatusCounts"].get(status, 0) + 1)
            if status == "VERIFIED_PAPER_OBSERVATION":
                summary["verifiedSnapshots"] += 1
            elif status in ("DATA_REJECTED", "DATA_FETCH_FAILED"):
                summary["rejectedOrFetchFailedSnapshots"] += 1
            else:
                summary["invalidSnapshots"] += 1
        else:
            summary["missingHourMarkers"] += 1
            if not marker.exists():
                message = {
                    "mode": "V7_PAPER_FORWARD_COVERAGE_ONLY",
                    "status": "MISSED_OBSERVATION",
                    "targetClosed1HUTC": utc_text(time),
                    "discoveredAtUTC": utc_text(discovered_at),
                    "reason": (
                        "No persisted snapshot for this past hour: scheduled job may have "
                        "been skipped/delayed, tests/source fetch may have failed, "
                        "or GitHub commit may not have persisted. Exact cause not inferred."
                    ),
                    "paperForwardObservation": False,
                    "liveOrPaperTrade": False,
                    "notBackfilled": True,
                    "noSignalInferred": True,
                }
                marker.write_text(
                    json.dumps(message, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")
                summary["newMissingMarkers"] += 1
        time += HOUR
    if (summary["verifiedSnapshots"] +
            summary["rejectedOrFetchFailedSnapshots"] +
            summary["invalidSnapshots"] +
            summary["missingHourMarkers"] != summary["expectedPriorHours"]):
        raise AssertionError("Coverage ledger count mismatch")
    return summary


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--snapshots", default="forward/snapshots")
    p.add_argument("--coverage", default="forward/coverage")
    p.add_argument("--target", required=True, help="Current UTC hour, e.g. 2026-11-04T23:00:00Z")
    p.add_argument("--now", default=None)
    args = p.parse_args()
    now = (datetime.fromisoformat(args.now.replace("Z", "+00:00"))
           if args.now else datetime.now(UTC))
    target = parse_utc(args.target)
    summary = audit_coverage(
        args.snapshots, args.coverage, target=target, discovered_at=now)
    # summary is derived only from PAST hours, not current potentially running hour.
    Path(args.coverage, "latest.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("V7 FORWARD COVERAGE", json.dumps({
        key: summary[key] for key in (
            "expectedPriorHours", "verifiedSnapshots",
            "rejectedOrFetchFailedSnapshots", "missingHourMarkers",
            "newMissingMarkers")
    }))


if __name__ == "__main__":
    main()
