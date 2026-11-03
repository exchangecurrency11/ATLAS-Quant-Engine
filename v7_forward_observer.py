#!/usr/bin/env python3
"""Hourly, point-in-time V7 forward observation — paper only, no orders.

Run from GitHub Actions on the isolated experimental branch. Inputs are freshly
downloaded closed 1H/4H/Daily Coinalyze futures OHLCV plus same-hour main
market_data.json. Refuse stale or mismatched inputs. Never backfill missed
observations, and never label historical paper fills as real executions.
"""
import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

from backtest_retest_long_v4 import replay_pair
from signal_quality_v7 import evaluate_bos_quality, evaluate_retest_quality

HOUR = 3600
TF_SECONDS = {"1hour": HOUR, "4hour": 4*HOUR, "daily": 24*HOUR}
PAIRS = ("BTCUSDT_PERP.A", "SOLUSDT_PERP.A")


def epoch(text):
    if not isinstance(text, str):
        raise ValueError("Timestamp must be UTC ISO string")
    stamp = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if stamp.tzinfo is None or stamp.utcoffset().total_seconds() != 0:
        raise ValueError("Expected offset-aware UTC timestamp")
    return int(stamp.timestamp())


def iso(t):
    return datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_and_hash(path):
    data = Path(path).read_bytes()
    return json.loads(data), hashlib.sha256(data).hexdigest()


def validate_inputs(main, histories, target, now):
    """Fail closed on time, completeness or provider-close mismatches."""
    if not 0 <= now - target < HOUR:
        raise ValueError("Requested target is not last completed 1H")
    if now - target < 10*60:
        raise ValueError("Run too close to hourly close for source publication")
    if main.get("ok") is not True or main.get("provider") != "Coinalyze" or main.get("market") != "Perpetual Futures":
        raise ValueError("Not the expected Coinalyze perpetual market snapshot")
    if epoch(main.get("checkedAtUTC")) < target:
        raise ValueError("Main source was checked before last 1H candle closed")
    # Provider source may refresh every ~hour; refuse time travel and stale checks.
    if epoch(main["checkedAtUTC"]) > now + 90:
        raise ValueError("Main source timestamp is in the future")
    groups = {}
    for row in main.get("results", []):
        key = (row.get("symbol"), row.get("interval"))
        if key in groups:
            raise ValueError("Duplicate market-data group")
        groups[key] = row
    if set(groups) != {(p, tf) for p in PAIRS for tf in TF_SECONDS}:
        raise ValueError("Missing or unexpected main market-data groups")
    parsed = {}
    for interval, seconds in TF_SECONDS.items():
        data = histories[interval]
        if not isinstance(data, list) or len(data) != 2:
            raise ValueError("Bad history provider array for " + interval)
        parsed[interval] = {}
        for item in data:
            symbol = item.get("symbol")
            if symbol not in PAIRS or symbol in parsed[interval]:
                raise ValueError("Missing/duplicate symbol in history " + interval)
            bars = item.get("history")
            if not isinstance(bars, list) or len(bars) < 250:
                raise ValueError("Insufficient closed history " + interval + " " + symbol)
            # Continuous 250 bars; worker endpoint already checks closedness,
            # but independently verify every input on the GitHub runner.
            tail = bars[-250:]
            for i, b in enumerate(tail):
                t = int(b["t"])
                if t % seconds != 0:
                    raise ValueError("Misaligned bar timestamp")
                if i and t - int(tail[i-1]["t"]) != seconds:
                    raise ValueError("History has missing or duplicate bars")
                o, h, lo, c, v = (float(b[x]) for x in ("o", "h", "l", "c", "v"))
                if (not all(map(math.isfinite, (o,h,lo,c,v))) or
                        lo <= 0 or v < 0 or lo > min(o,c) or h < max(o,c)):
                    raise ValueError("Invalid OHLCV in history")
            required_close = target // seconds * seconds
            observed_close = int(bars[-1]["t"]) + seconds
            if observed_close != required_close:
                raise ValueError("History stale or ahead: " + symbol + " " + interval +
                                 " got " + iso(observed_close) + " need " + iso(required_close))
            ref = groups[(symbol, interval)]
            if ref.get("status") != "READY" or epoch(ref.get("closeTimeUTC")) != required_close:
                raise ValueError("Main market snapshot stale: " + symbol + " " + interval)
            saved_close = float(ref["candle"]["close"])
            history_close = float(bars[-1]["c"])
            if abs(saved_close - history_close) > max(0.000001, abs(history_close)*0.000002):
                raise ValueError("Two closed-candle sources disagree on close: " + symbol + " " + interval)
            parsed[interval][symbol] = bars
        if set(parsed[interval]) != set(PAIRS):
            raise ValueError("Missing history pair")
    return parsed


def latest_events(report, target):
    if report.get("status") != "PAPER_BACKTEST_NOT_LIVE":
        raise ValueError("Historical replay not READY")
    events = report.get("alerts", [])
    exits = report.get("trades", [])
    return {
        "newWatchAtThisClose": [e for e in events if e["knownUTC"] == target],
        "paperTradeExitsObservedAtThisClose": [
            t for t in exits if t["exitKnownUTC"] == target],
        "currentPaperState": report.get("forwardStateAtLastClose", {}),
        "diagnosticTotalRollingWindowAlerts": len(events),
        "diagnosticTotalRollingWindowClosedTrades": len(exits),
    }


def observe(main, data, *, target, now):
    parsed = validate_inputs(main, data, target, now)
    results = {}
    for pair in PAIRS:
        h, four, daily = (parsed[tf][pair] for tf in TF_SECONDS)
        variants = (
            ("V4_baseline", {}),
            ("V7_signal_filter", {"bos_quality_filter": evaluate_bos_quality}),
            ("V7_signal_plus_retest", {
                "bos_quality_filter": evaluate_bos_quality,
                "retest_quality_filter": evaluate_retest_quality,
            }),
        )
        results[pair] = {}
        for name, opts in variants:
            result = replay_pair(h, four, daily, as_of=target, **opts)
            results[pair][name] = latest_events(result, target)
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--main-data", required=True)
    parser.add_argument("--hour", required=True)
    parser.add_argument("--four", required=True)
    parser.add_argument("--daily", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--artifact-output", default=None)
    parser.add_argument("--now-utc", default=None, help="ONLY for deterministic tests")
    args = parser.parse_args()
    now = epoch(args.now_utc) if args.now_utc else int(datetime.now(timezone.utc).timestamp())
    target = now // HOUR * HOUR
    snapshot = {
        "mode": "PAPER_FORWARD_OBSERVATION_NO_ORDERS",
        "observedAtUTC": iso(now),
        "targetClosed1HUTC": iso(target),
        "status": "DATA_REJECTED",
        "productionSystemModified": False,
        "brokerOrders": False,
        "caution": (
            "Retest is observed at close. Hypothetical next-open fills and "
            "subsequent outcomes are reconstructed from later CLOSED candles; "
            "not actual orders, funding or orderbook fills. No missed-hour backfill."
        ),
    }
    try:
        main_data, main_sha = load_and_hash(args.main_data)
        histories = {}
        source_hashes = {"main": main_sha}
        for tf, path in (("1hour", args.hour), ("4hour", args.four), ("daily", args.daily)):
            histories[tf], source_hashes[tf] = load_and_hash(path)
        snapshot["inputSHA256"] = source_hashes
        snapshot["marketDataCheckedAtUTC"] = main_data.get("checkedAtUTC")
        snapshot["results"] = observe(main_data, histories, target=target, now=now)
        snapshot["status"] = "VERIFIED_PAPER_OBSERVATION"
        print("VALIDATED:", snapshot["targetClosed1HUTC"])
        for symbol, variants in snapshot["results"].items():
            print(symbol, " ".join(
                name + ":alerts=" + str(len(report["newWatchAtThisClose"])) +
                ",exits=" + str(len(report["paperTradeExitsObservedAtThisClose"]))
                for name,report in variants.items()))
    except (ValueError, KeyError, TypeError, ZeroDivisionError) as e:
        snapshot["rejectionReason"] = str(e)
        print("DATA_REJECTED; NO SIGNALS:", str(e))
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.artifact_output:
        Path(args.artifact_output).write_text(
            json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
