#!/usr/bin/env python3
"""SOL V8 Coinalyze derivatives data-health probe; NO SIGNALS, NO ORDERS.

Independent experiment only. Data must be observed after a genuinely closed
1H interval. Provider-reported 'bv' is not yet certified as Binance taker-buy
volume, and funding unit semantics are left as provider-reported.
"""
import argparse
import hashlib
import json
import math
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

SYMBOL = "SOLUSDT_PERP.A"
BASE = "https://api.coinalyze.net/v1/"
HOUR = 3600
MAX_FUNDING_AGE = 12 * HOUR


def iso(t):
    return datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def number(v, name, positive=False):
    if isinstance(v, bool):
        raise ValueError("BAD_" + name)
    try:
        x = float(v)
    except (ValueError, TypeError, OverflowError) as exc:
        raise ValueError("BAD_" + name) from exc
    if not math.isfinite(x) or (positive and x <= 0):
        raise ValueError("BAD_" + name)
    return x


def one_symbol(data, history=False):
    if (not isinstance(data, list) or len(data) != 1 or
            not isinstance(data[0], dict) or data[0].get("symbol") != SYMBOL):
        raise ValueError("WRONG_SOL_PERPETUAL_SYMBOL")
    row = data[0]
    if history and not isinstance(row.get("history"), list):
        raise ValueError("HISTORY_MISSING")
    return row["history"] if history else row


def closed_hour_rows(data, target, minimum=3):
    history = one_symbol(data, history=True)
    rows = []
    last_t = None
    for bar in history:
        if not isinstance(bar, dict):
            raise ValueError("BAD_HISTORY_BAR")
        t = bar.get("t")
        if type(t) is not int or t % HOUR:
            raise ValueError("BAD_HISTORY_TIME")
        if last_t is not None and t <= last_t:
            raise ValueError("DUPLICATE_OR_UNORDERED_TIME")
        last_t = t
        if t + HOUR <= target:
            rows.append(bar)
    if len(rows) < minimum or rows[-1]["t"] + HOUR != target:
        raise ValueError("MISSING_LATEST_CLOSED_HOUR")
    if any(rows[i]["t"] - rows[i - 1]["t"] != HOUR
           for i in range(len(rows) - minimum + 1, len(rows))):
        raise ValueError("GAPPED_HOURLY_HISTORY")
    return rows


def validate_oi(data, target):
    rows = closed_hour_rows(data, target)
    values = []
    for bar in rows[-3:]:
        o, h, low, c = [number(bar.get(k), "OI_" + k.upper(), positive=True)
                        for k in ("o", "h", "l", "c")]
        if not low <= min(o, c) <= max(o, c) <= h:
            raise ValueError("IMPOSSIBLE_OI_OHLC")
        values.append(c)
    previous, latest = values[-2:]
    return {"asOfClosedUTC": iso(target), "latest": latest,
            "previous": previous,
            "oneHourChangePct": round(100 * (latest / previous - 1), 6),
            "threeContinuousClosedHours": True,
            "units": "provider OI units (convert_to_usd=false)"}


def validate_volume(data, target):
    rows = closed_hour_rows(data, target)
    bar = rows[-1]
    volume = number(bar.get("v"), "VOLUME", positive=True)
    if "bv" not in bar:
        raise ValueError("COINALYZE_BV_NOT_AVAILABLE")
    buy = number(bar["bv"], "BUY_VOLUME")
    if buy < 0 or buy > volume * (1 + 1e-8):
        raise ValueError("BUY_VOLUME_EXCEEDS_TOTAL")
    buy = min(buy, volume)
    return {"closedHourUTC": iso(target), "totalVolume": volume,
            "providerBuyVolumeBV": buy, "derivedOtherVolume": volume - buy,
            "providerBuyShare": round(buy / volume, 6),
            "takerBuySellCrossSourceVerified": False,
            "caution": "Coinalyze bv not yet independently reconciled against Binance taker-buy archive"}


def validate_funding(data, now):
    record = one_symbol(data)
    rate = number(record.get("value"), "FUNDING")
    stamp = record.get("update")
    if type(stamp) is not int or stamp <= 0:
        raise ValueError("BAD_FUNDING_UPDATE")
    # Coinalyze documents a numeric update timestamp but its live endpoint
    # currently responds in epoch MILLISECONDS (13 digits). Support both
    # seconds and milliseconds explicitly, without accepting other units.
    if stamp >= 10**12:
        updated_at = stamp // 1000
        timestamp_unit = "milliseconds"
    else:
        updated_at = stamp
        timestamp_unit = "seconds"
    age = now - updated_at
    if age < -60 or age > MAX_FUNDING_AGE:
        raise ValueError("STALE_OR_FUTURE_FUNDING")
    return {"providerReportedValue": rate,
            "providerReportedUnitsUnverified": True,
            "providerUpdateUTC": iso(updated_at), "ageSeconds": age,
            "timestampUnit": timestamp_unit,
            "note": "Current funding observation, not a backfilled signal-time value"}


def request_json(endpoint, params, key):
    qs = urllib.parse.urlencode(params)
    request = urllib.request.Request(
        BASE + endpoint + ("?" + qs if qs else ""),
        headers={"api_key": key, "Accept": "application/json",
                 "User-Agent": "SOL-V8-research-readonly/1.0"},
        method="GET")
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            if response.status != 200:
                raise RuntimeError("COINALYZE_NON_200")
            blob = response.read(1500000)
    except urllib.error.HTTPError as exc:
        raise RuntimeError("COINALYZE_HTTP_" + str(exc.code)) from None
    except (urllib.error.URLError, TimeoutError) as exc:
        raise RuntimeError("COINALYZE_NETWORK_" + type(exc).__name__) from None
    try:
        data = json.loads(blob)
    except (ValueError, TypeError):
        raise ValueError("COINALYZE_INVALID_JSON") from None
    return data, hashlib.sha256(blob).hexdigest()


def observe(now, key, fetch=request_json):
    target = now // HOUR * HOUR
    result = {
        "mode": "SOL_V8_DERIVATIVES_QUALITY_PROBE_NO_ORDERS",
        "symbol": SYMBOL, "exchange": "Binance", "perpetual": True,
        "observedAtUTC": iso(now), "targetClosed1HUTC": iso(target),
        "status": "SOURCE_UNAVAILABLE_NO_SIGNAL", "brokerOrders": False,
        "productionSystemModified": False, "liveSignalEnabled": False,
        "dataSource": "Coinalyze API (read-only) for Binance SOL perpetual",
    }
    try:
        if not 10 * 60 <= now - target < HOUR:
            raise ValueError("OUTSIDE_CLOSED_HOUR_OBSERVATION_WINDOW")
        if not key:
            raise ValueError("MISSING_COINALYZE_SECRET")
        start = target - 6 * HOUR
        common = {"symbols": SYMBOL, "interval": "1hour",
                  "from": start, "to": now}
        oi, oi_hash = fetch("open-interest-history",
                            {**common, "convert_to_usd": "false"}, key)
        volumes, volume_hash = fetch("ohlcv-history", common, key)
        funding, funding_hash = fetch("funding-rate", {"symbols": SYMBOL}, key)
        # Preserve independently valid OI and volume data even when funding
        # is stale. Partial data is NEVER promoted to a signal or "healthy".
        result.update({
            "openInterest": validate_oi(oi, target),
            "providerBuyVolume": validate_volume(volumes, target),
            "sourceSHA256": {"openInterest": oi_hash, "ohlcv": volume_hash,
                            "funding": funding_hash},
            "researchCaution": "No taker source reconciliation, funding unit certification, "
                               "or historical prospective predictive efficacy; no trading signals.",
        })
        try:
            result["funding"] = validate_funding(funding, now)
            result["status"] = "DATA_VALIDATED_RESEARCH_ONLY"
        except ValueError:
            raw = one_symbol(funding)
            stamp = raw.get("update")
            valid_stamp = type(stamp) is int and 0 < stamp < now + 86400
            result["funding"] = {
                "status": "STALE_OR_INVALID_TIMESTAMP_NO_SIGNAL",
                "providerUpdateUTC": iso(stamp) if valid_stamp else None,
                "ageSeconds": (now - stamp) if valid_stamp else None,
                "providerUpdateRaw": (str(stamp)[:32] if isinstance(stamp, (int, float, str))
                                      else type(stamp).__name__),
            }
            result["status"] = "DATA_PARTIAL_RESEARCH_ONLY_NO_SIGNAL"
            result["rejectionReason"] = "FUNDING_TIMESTAMP_NOT_FRESH"
    except (ValueError, RuntimeError, KeyError, TypeError, OverflowError) as exc:
        result["status"] = "SOURCE_UNAVAILABLE_NO_SIGNAL"
        result["rejectionReason"] = str(exc)[:120] if str(exc) else type(exc).__name__
        for name in ("openInterest", "providerBuyVolume", "funding", "sourceSHA256"):
            result.pop(name, None)
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--output", required=True)
    p.add_argument("--strict", action="store_true")
    args = p.parse_args()
    now = int(datetime.now(timezone.utc).timestamp())
    key = (os.environ.get("SOL_V8_COINALYZE_API_KEY") or "").strip()
    result = observe(now, key)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print("SOL_V8_DATA_HEALTH", result["status"], result["targetClosed1HUTC"],
          result.get("rejectionReason", ""))
    if args.strict and result["status"] != "DATA_VALIDATED_RESEARCH_ONLY":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
