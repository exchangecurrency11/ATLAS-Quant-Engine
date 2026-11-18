#!/usr/bin/env python3
"""E5J: fail-closed, first-writer-wins V9.2 hourly research source sealing.

This helper only creates immutable research Git commits. It never orders,
notifies, backfills a prior hour, rebases an overlapping writer, or merges
stale combined-account state over another writer's results.
"""
import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

BRANCH = "research/v92-bull-bear-candle-invalidation-20261112"
CONFIG = {
    "btc-sol": {
        "dir": "forward/v92_prospective_selected/hourly",
        "mode": "V92_SELECTED_CANDLE_IMMUTABLE_HOURLY_FORWARD_PAPER_ONLY",
        "parity": "sourceV7AndV91RecomputedExactMatch",
        "files": [
            "forward/v92_prospective_selected/third_paper_account.json",
            "forward/v92_prospective_selected/third_paper_account.md",
        ],
    },
    "eth": {
        "dir": "forward/v92_prospective_eth/hourly",
        "mode": "V92_ETH_VERIFIED_HOURLY_CANDLES_OBSERVATIONAL_PAPER",
        "parity": "verifiedSourceAndExactV7AndV91Replay",
        "files": [
            "forward/v92_prospective_eth/component.json",
            "forward/v92_prospective_eth/component.md",
        ],
    },
}
SHARED = [
    "forward/v92_prospective_selected/combined_three_asset_account.json",
    "forward/v92_prospective_selected/combined_three_asset_account.md",
]


class SealError(RuntimeError):
    """A safe refusal: no source file is modified or overwritten."""


def git(repo, *args, check=True):
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    if check and result.returncode:
        raise SealError("E5J_GIT_FAILED " + " ".join(args[:3]) +
                        " " + result.stderr.strip()[:300])
    return result


def _show(repo, commit, path):
    result = git(repo, "show", f"{commit}:{path}", check=False)
    return result.stdout if result.returncode == 0 else None


def _safe_snapshot(raw, asset, target):
    try:
        obj = json.loads(raw)
    except (ValueError, TypeError) as exc:
        raise SealError("E5J_SNAPSHOT_NOT_JSON") from exc
    conf = CONFIG[asset]
    expected_hour = datetime.strptime(target, "%Y-%m-%dT%H-00Z").strftime(
        "%Y-%m-%dT%H:00:00Z"
    )
    if not isinstance(obj, dict) or obj.get("mode") != conf["mode"]:
        raise SealError("E5J_SNAPSHOT_MODE_MISMATCH")
    if obj.get("targetClosed1HUTC") != expected_hour:
        raise SealError("E5J_TARGET_HOUR_MISMATCH")
    if obj.get(conf["parity"]) is not True:
        raise SealError("E5J_SOURCE_PARITY_UNVERIFIED")
    if obj.get("noBrokerOrders") is not True or obj.get("noUserNotifications") is not True:
        raise SealError("E5J_ORDERS_OR_ALERTS_NOT_PROVEN_DISABLED")
    return obj


def _comparable(obj):
    # The observation timestamp can differ on a legitimate same-hour retry.
    # All actual candle, parity, source and signal data MUST stay identical.
    return {k: v for k, v in obj.items() if k != "capturedAtUTC"}


def _output(output, committed):
    if output:
        with open(output, "a", encoding="utf-8") as f:
            f.write("committed=" + ("true" if committed else "false") + "\n")


def seal(repo, asset, target, *, now=None, output=None):
    repo = Path(repo).resolve()
    if asset not in CONFIG or not re.fullmatch(r"20\d{2}-\d\d-\d\dT\d\d-00Z", target):
        raise SealError("E5J_ASSET_OR_TARGET_REJECTED")
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset().total_seconds() != 0:
        raise SealError("E5J_TIME_MUST_BE_UTC")
    if target != now.strftime("%Y-%m-%dT%H-00Z") or now.minute < 12:
        raise SealError("E5J_OLD_OR_PREMATURE_HOUR_REJECTED")
    if git(repo, "branch", "--show-current").stdout.strip() != BRANCH:
        raise SealError("E5J_WRONG_RESEARCH_BRANCH")
    conf = CONFIG[asset]
    target_path = f"{conf['dir']}/{target}.json"
    local_path = repo / target_path
    if not local_path.is_file():
        raise SealError("E5J_CANDIDATE_SOURCE_ABSENT")
    local_obj = _safe_snapshot(local_path.read_text(encoding="utf-8"), asset, target)
    shared_obj = json.loads((repo / SHARED[0]).read_text(encoding="utf-8"))
    if not (
        shared_obj.get("mode") == "V92_BTC_ETH_SOL_SINGLE_THIRD_1000USDT_PROSPECTIVE_PAPER_ACCOUNT"
        and shared_obj.get("assets") == ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
        and shared_obj.get("virtualInitialUSDT") == 1000
        and shared_obj.get("sharedSingleVirtualPortfolioNotThreeTimes1000") is True
        and shared_obj.get("noBrokerOrders") is True
        and shared_obj.get("noUserNotifications") is True
    ):
        raise SealError("E5J_SHARED_PAPER_ACCOUNT_SAFETY_REJECTED")
    expected_files = [target_path, *conf["files"], *SHARED]
    if not all((repo / p).is_file() for p in expected_files):
        raise SealError("E5J_EXPECTED_RESEARCH_OUTPUT_ABSENT")

    # Re-check immutable remote Git tree after potentially slow worker reads.
    initial_head = git(repo, "rev-parse", "HEAD").stdout.strip()
    git(repo, "fetch", "--quiet", "origin", BRANCH)
    remote_head = git(repo, "rev-parse", "FETCH_HEAD").stdout.strip()

    def remote_sealed(commit):
        existing = _show(repo, commit, target_path)
        if existing is None:
            return False
        remote_obj = _safe_snapshot(existing, asset, target)
        if _comparable(remote_obj) != _comparable(local_obj):
            raise SealError("E5J_IMMUTABLE_HOUR_CONTENT_CONFLICT_FAIL_CLOSED")
        _output(output, False)
        print("E5J_IDENTICAL_HOUR_ALREADY_SEALED_NO_REWRITE")
        return True

    if remote_sealed(remote_head):
        return False
    if remote_head != initial_head:
        # Never rebase stale shared-account totals over another writer's commit.
        # A later exact-current-hour run can recompute from fresh Git state.
        raise SealError("E5J_REMOTE_ADVANCED_RECOMPUTE_REQUIRED")

    git(repo, "config", "user.name", "github-actions[bot]")
    git(repo, "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com")
    git(repo, "add", "--", *expected_files)
    changed = set(git(repo, "diff", "--cached", "--name-only").stdout.splitlines())
    if target_path not in changed or not changed.issubset(set(expected_files)):
        raise SealError("E5J_UNEXPECTED_STAGED_PATHS")
    git(repo, "commit", "-m",
        "E5J first-writer-wins immutable V9.2 " + asset + " source NO ORDERS")
    if target != datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-00Z") and now is None:
        raise SealError("E5J_HOUR_ROLLOVER_BEFORE_PUSH")
    result = git(repo, "push", "origin", "HEAD:" + BRANCH, check=False)
    if result.returncode == 0:
        _output(output, True)
        print("E5J_NEW_HOUR_COMMITTED_NO_ORDERS")
        return True

    # Another writer may have sealed the same hour during the push race.
    # Never attempt an add/add rebase or force-push, even when account totals differ.
    git(repo, "fetch", "--quiet", "origin", BRANCH)
    remote_head = git(repo, "rev-parse", "FETCH_HEAD").stdout.strip()
    if remote_sealed(remote_head):
        return False
    raise SealError("E5J_PUSH_REJECTED_NO_SAFE_REBASE")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--asset", required=True, choices=sorted(CONFIG))
    parser.add_argument("--target", required=True)
    parser.add_argument("--repo", default=".")
    parser.add_argument("--github-output")
    args = parser.parse_args()
    try:
        seal(args.repo, args.asset, args.target, output=args.github_output)
    except (SealError, OSError, ValueError) as exc:
        print("E5J_FAIL_CLOSED " + str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
