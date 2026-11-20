#!/usr/bin/env python3
"""ATLAS Zone Quality V1 forward-only shadow recorder.

Pure stdlib glue around the FROZEN research/zone_quality_intelligence_v1.py.
Receives source-pinned JSON from a separate observer. Never talks to GitHub,
an exchange, a broker, an alert or a portfolio. Creates output with mode x.
"""
import argparse
import json
import math
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from zone_quality_intelligence_v1 import assess, SCORE_VERSION

SYMBOLS = ("BTCUSDT_PERP.A", "SOLUSDT_PERP.A")
SHA = re.compile(r"^[0-9a-fA-F]{40}$")


def seconds(value):
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError("UTC ISO timestamp ending Z required")
    try:
        d = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ValueError("Bad ISO timestamp") from exc
    if d.utcoffset() != timedelta(0):
        raise ValueError("UTC required")
    return d.timestamp()


def stamp(value):
    return datetime.fromtimestamp(value, timezone.utc).isoformat().replace("+00:00", "Z")


def validate_sha(value):
    if not isinstance(value, str) or not SHA.fullmatch(value):
        raise ValueError("Require full 40-character SHA")


def valid_candle(c):
    if not isinstance(c, dict):
        return False
    o, h, l, cl = (c.get(k) for k in ("open", "high", "low", "close"))
    if any(not isinstance(x, (int, float)) or isinstance(x, bool) or
           not math.isfinite(x) or x <= 0 for x in (o, h, l, cl)):
        return False
    return l <= min(o, cl) <= max(o, cl) <= h


def get_market(market, symbol):
    rows = [x for x in market.get("results", []) if
            x.get("symbol") == symbol and x.get("interval") == "1hour"]
    if len(rows) != 1 or rows[0].get("status") != "READY":
        raise ValueError("Missing or duplicate READY market 1H symbol")
    return rows[0]


def get_structure(structure, symbol):
    rows = [x for x in structure.get("results", []) if
            x.get("symbol") == symbol and x.get("interval") == "1hour"]
    if len(rows) != 1 or rows[0].get("status") != "READY":
        raise ValueError("Missing or duplicate READY structure 1H symbol")
    return rows[0]


def atr_from_pinned_history(history, event_close, symbol, market_row, cutoff):
    """14 true ranges from 15 full hourly Git-published source snapshots."""
    records = history.get("rows") if isinstance(history, dict) else history
    if not isinstance(records, list) or len(records) != 15:
        raise ValueError("ATR_INPUT_GAP: require exactly 15 hourly source records")
    ordered = sorted(records, key=lambda x: seconds(
        (x.get("btc") if symbol.startswith("BTC") else x.get("sol") or {}).get("closeTimeUTC", "")))
    candles = []
    for i, record in enumerate(ordered):
        validate_sha(record.get("sha"))
        published = seconds(record.get("publishedUTC"))
        data = record.get("btc") if symbol.startswith("BTC") else record.get("sol")
        if not isinstance(data, dict) or data.get("symbol") != symbol or data.get("interval") != "1hour":
            raise ValueError("ATR_INPUT_GAP: missing symbol/hour")
        close = seconds(data.get("closeTimeUTC"))
        if abs(close - (event_close - (14 - i) * 3600)) > 0.01:
            raise ValueError("ATR_INPUT_GAP: missing or duplicate hour")
        if published < close or published > cutoff:
            raise ValueError("LOOKAHEAD: invalid historical market publication")
        candle = data.get("candle")
        if not valid_candle(candle):
            raise ValueError("ATR_INPUT_GAP: malformed candle")
        candles.append(candle)
    current = market_row["candle"]
    if any(not math.isclose(candles[-1][k], current[k], rel_tol=1e-10, abs_tol=1e-8)
           for k in ("open", "high", "low", "close")):
        raise ValueError("ATR_INPUT_GAP: final candle does not equal market snapshot")
    trs = []
    for i in range(1, 15):
        c, prev = candles[i], candles[i - 1]
        trs.append(max(c["high"] - c["low"], abs(c["high"] - prev["close"]),
                       abs(c["low"] - prev["close"])))
    atr = sum(trs) / 14
    if not math.isfinite(atr) or atr <= 0:
        raise ValueError("ATR_INPUT_GAP: unusable ATR")
    return atr, [r["sha"] for r in ordered]


def score_hour(market, structure, history, *, event_close_utc, observed_at_utc,
               start_utc, market_sha, market_published_utc,
               structure_sha, structure_published_utc):
    for value in (market_sha, structure_sha):
        validate_sha(value)
    close, observed, begin = seconds(event_close_utc), seconds(observed_at_utc), seconds(start_utc)
    cutoff = close + 300
    if close < begin:
        raise ValueError("PRE_FREEZE_EVENT: cannot score earlier events as forward")
    if close % 3600:
        raise ValueError("Signal event must be a full 1H UTC close")
    mp, sp = seconds(market_published_utc), seconds(structure_published_utc)
    if not (close <= mp <= cutoff and close <= sp <= cutoff):
        raise ValueError("SOURCE_LATE_OR_LOOKAHEAD: not published by five-minute cutoff")
    if not (max(mp, sp, cutoff) <= observed < close + 3600):
        raise ValueError("LATE_OBSERVATION: record must precede next 1H close")
    events = []
    for symbol in SYMBOLS:
        m, s = get_market(market, symbol), get_structure(structure, symbol)
        if seconds(m.get("closeTimeUTC")) != close or seconds(s.get("lastCloseTimeUTC")) != close:
            raise ValueError("SOURCE_CANDLE_MISMATCH: market/structure not at event close")
        candle = m.get("candle")
        if not valid_candle(candle):
            raise ValueError("SOURCE_CANDLE_MISMATCH: invalid OHLC")
        matching = [e for e in s.get("structure", [])
                    if isinstance(e, dict) and e.get("event") in ("BOS", "CHoCH")
                    and e.get("direction") in ("bullish", "bearish")
                    and e.get("at") == close - 3600]
        for ev in matching:
            side = "LONG" if ev["direction"] == "bullish" else "SHORT"
            atr, atr_shas = atr_from_pinned_history(history, close, symbol, m, cutoff)
            result = assess(structure, symbol=symbol, side=side,
                            signal_at=stamp(cutoff), signal_price=candle["close"],
                            pinned_commit=structure_sha,
                            commit_published_at=structure_published_utc, atr=atr,
                            signal_candle_low=candle["low"],
                            signal_candle_high=candle["high"])
            zones = result["zones"]
            near = min(zones, key=lambda z: (z["distanceATR"], -z["evidenceIndex"])) if zones else None
            events.append({
                "symbol": symbol, "eventKind": ev["event"], "side": side,
                "eventCloseUTC": stamp(close), "signalPrice": candle["close"],
                "signalCandle": candle, "brokenLevel": ev.get("brokenLevel"),
                "atr14": atr, "atrMarketCommitShas": atr_shas,
                "status": result["status"],
                "zoneCount": len(zones), "zones": zones,
                "topQualityZoneId": zones[0]["researchZoneId"] if zones else None,
                "nearestZoneId": near["researchZoneId"] if near else None,
                "modelVersion": SCORE_VERSION,
                "note": "Forward research zone ranking, NOT a probability or trade instruction"})
    return {
        "schemaVersion": 1, "recordKind": "PROSPECTIVE_SHADOW_HOURLY",
        "scoreVersion": SCORE_VERSION, "eventCloseUTC": stamp(close),
        "cutoffUTC": stamp(cutoff), "observedAtUTC": observed_at_utc,
        "startedNoEarlierThanUTC": start_utc,
        "status": "EVENTS_CAPTURED" if events else "NO_NEW_STRUCTURE_EVENT",
        "sources": {"marketSha": market_sha, "marketPublishedUTC": market_published_utc,
                    "structureSha": structure_sha,
                    "structurePublishedUTC": structure_published_utc,
                    "publicationProvenanceVerifiedByCaller": False},
        "events": events, "noActualOrders": True,
        "warning": "Commit-time of the immutable GitHub observation file must also precede the next 1H close to qualify for prospective evaluation."}


def settle_hour(prediction, forward_rows, *, settled_at_utc):
    if prediction.get("scoreVersion") != SCORE_VERSION or prediction.get("recordKind") != "PROSPECTIVE_SHADOW_HOURLY":
        raise ValueError("Wrong prediction version/type")
    t = seconds(prediction["eventCloseUTC"])
    records = forward_rows.get("rows") if isinstance(forward_rows, dict) else forward_rows
    if not isinstance(records, list) or len(records) != 12:
        raise ValueError("CENSORED: require 12 independently sourced future hours")
    if seconds(settled_at_utc) < t + 12 * 3600 + 300:
        raise ValueError("CENSORED: full observation horizon not available")
    ordered = sorted(records, key=lambda r: seconds(r["btc"]["closeTimeUTC"]))
    for i, record in enumerate(ordered):
        validate_sha(record.get("sha"))
        publication = seconds(record.get("publishedUTC"))
        expected = t + (i + 1) * 3600
        for s in ("btc", "sol"):
            row = record.get(s)
            if (not isinstance(row, dict) or seconds(row.get("closeTimeUTC")) != expected
                or not valid_candle(row.get("candle"))):
                raise ValueError("CENSORED: future bar is missing or malformed")
        if not expected <= publication <= seconds(settled_at_utc):
            raise ValueError("CENSORED: future source publication unavailable")
    outcomes = []
    for event in prediction.get("events", []):
        symbol = event["symbol"]
        side = event["side"]
        atr = event["atr14"]
        candles = [(r["btc"] if symbol.startswith("BTC") else r["sol"])["candle"] for r in ordered]
        diagnostics = []
        for zone in event["zones"]:
            lo, hi = zone["range"]
            hit_index = next((i for i, candle in enumerate(candles)
                              if candle["high"] >= lo if side == "LONG"), None) if side == "LONG" else next(
                                  (i for i, candle in enumerate(candles) if candle["low"] <= hi), None)
            if hit_index is None:
                diagnostics.append({"researchZoneId": zone["researchZoneId"],
                    "score": zone["evidenceIndex"], "visited": False,
                    "firstTouchHour": None, "reversedWithin3Closed1H": None,
                    "closedBeyondFarEdge": None})
                continue
            opposing = any((c["close"] <= lo - 0.5 * atr if side == "LONG"
                             else c["close"] >= hi + 0.5 * atr)
                            for c in candles[hit_index + 1: min(12, hit_index + 4)])
            breached = any((c["close"] > hi if side == "LONG" else c["close"] < lo)
                           for c in candles[hit_index:])
            diagnostics.append({"researchZoneId": zone["researchZoneId"],
                "score": zone["evidenceIndex"], "visited": True,
                "firstTouchHour": hit_index + 1, "reversedWithin3Closed1H": opposing,
                "closedBeyondFarEdge": breached})
        outcomes.append({"symbol": symbol, "eventKind": event["eventKind"],
                         "side": side, "status": event["status"],
                         "topQualityZoneId": event["topQualityZoneId"],
                         "nearestZoneId": event["nearestZoneId"],
                         "zoneOutcomes": diagnostics})
    return {"schemaVersion": 1, "recordKind": "PROSPECTIVE_SHADOW_OUTCOME",
            "scoreVersion": SCORE_VERSION, "eventCloseUTC": prediction["eventCloseUTC"],
            "settledAtUTC": settled_at_utc, "full12h": True,
            "futureMarketCommits": [r["sha"] for r in ordered],
            "events": outcomes, "warning": "12h OHLC observation only, no simulated execution or actual trading"}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    q = sub.add_parser("score-hour")
    for key in ("market", "structure", "history", "event-close-utc", "observed-at-utc",
                "start-utc", "market-sha", "market-published-utc",
                "structure-sha", "structure-published-utc"):
        q.add_argument("--" + key, required=True)
    s = sub.add_parser("settle-hour")
    for key in ("prediction", "future-rows", "settled-at-utc"):
        s.add_argument("--" + key, required=True)
    for subp in (q, s):
        subp.add_argument("--output", required=True)
    a = p.parse_args()
    if a.cmd == "score-hour":
        result = score_hour(
            json.loads(Path(a.market).read_text()),
            json.loads(Path(a.structure).read_text()),
            json.loads(Path(a.history).read_text()),
            event_close_utc=a.event_close_utc, observed_at_utc=a.observed_at_utc,
            start_utc=a.start_utc, market_sha=a.market_sha,
            market_published_utc=a.market_published_utc,
            structure_sha=a.structure_sha, structure_published_utc=a.structure_published_utc)
    else:
        result = settle_hour(json.loads(Path(a.prediction).read_text()),
                            json.loads(Path(a.future_rows).read_text()),
                            settled_at_utc=a.settled_at_utc)
    with Path(a.output).open("x", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(json.dumps({"status": result.get("status", result.get("recordKind")),
                      "events": len(result["events"]), "output": a.output}))


if __name__ == "__main__":
    main()
