#!/usr/bin/env python3
"""V9.2 observational 1D + derived 3D context from independently verified daily bars.

Only *fully closed* UTC daily OHLCV are accepted. Three-day candles are aligned
to a fixed Unix UTC 3-day grid for deterministic, reproducible aggregation; this
is NOT a claim of byte-for-byte parity with an exchange-native 3D feed.
Observations MUST NOT place orders, veto a retest or change existing V7/V9.1
signals without a separate prospective study and an audited backtest.
"""
import math

from v7_forward_observer import iso
from v92_multi_candle_invalidation import all_patterns_at
from v92_selected_reversal_patterns import soldier_crow

DAY = 86400
THREE_DAYS = 3 * DAY
FIELDS = ("o", "h", "l", "c", "v")


def _checked_closed_daily(daily, as_of):
    if not isinstance(as_of, int) or not isinstance(daily, list) or len(daily) < 155:
        raise ValueError("V92_HIGHER_TF_MISSING_VALIDATED_DAILY_HISTORY")
    closed = []
    previous = None
    for source in daily:
        t = int(source["t"])
        if t % DAY or (previous is not None and t - previous != DAY):
            raise ValueError("V92_HIGHER_TF_DAILY_GAP_OR_MISALIGNMENT")
        previous = t
        if t + DAY > as_of:
            raise ValueError("V92_HIGHER_TF_PARTIAL_OR_FUTURE_DAILY_CANDLE")
        b = {"t": t, **{k: float(source[k]) for k in FIELDS}}
        if (not all(math.isfinite(b[k]) for k in FIELDS)
            or b["l"] <= 0 or b["v"] < 0
            or b["l"] > min(b["o"], b["c"])
            or b["h"] < max(b["o"], b["c"])):
            raise ValueError("V92_HIGHER_TF_INVALID_DAILY_OHLCV")
        closed.append(b)
    # Each hourly capture must use the most recently finished UTC daily bar.
    if closed[-1]["t"] + DAY != as_of // DAY * DAY:
        raise ValueError("V92_HIGHER_TF_STALE_DAILY_CANDLE")
    return closed


def aggregate_3d_from_daily(daily):
    """Aggregate only complete, UTC epoch-aligned triplets of daily bars."""
    by_start = {bar["t"]: bar for bar in daily}
    result = []
    for start in sorted(t for t in by_start if t % THREE_DAYS == 0):
        bars = [by_start.get(start + i * DAY) for i in range(3)]
        if any(x is None for x in bars):
            continue
        result.append({
            "t": start,
            "o": bars[0]["o"],
            "h": max(x["h"] for x in bars),
            "l": min(x["l"] for x in bars),
            "c": bars[-1]["c"],
            "v": sum(x["v"] for x in bars),
        })
    if any(result[i]["t"] - result[i-1]["t"] != THREE_DAYS
           for i in range(1, len(result))):
        raise ValueError("V92_HIGHER_TF_3D_GAP")
    return result


def ema20_50_trend(bars):
    """Shared closed-bar EMA20/EMA50 direction rule for live and replay."""
    if len(bars) < 50:
        return "insufficient"
    closes = [z["c"] for z in bars]
    ema20 = _ema(closes, 20)
    ema50 = _ema(closes, 50)
    close = closes[-1]
    return ("bullish" if close > max(ema20, ema50)
            else "bearish" if close < min(ema20, ema50)
            else "mixed")


def context_at(daily, as_of):
    """Higher-timeframe trend at an intraday timestamp; future daily bars excluded."""
    closed_daily = [b for b in daily if b["t"] + DAY <= as_of]
    if not closed_daily:
        return {"1D": "insufficient", "3D": "insufficient",
                "closedDailyBars": 0, "closed3DBars": 0}
    three = aggregate_3d_from_daily(closed_daily)
    closed_three = [b for b in three if b["t"] + THREE_DAYS <= as_of]
    return {
        "1D": ema20_50_trend(closed_daily),
        "3D": ema20_50_trend(closed_three),
        "closedDailyBars": len(closed_daily),
        "closed3DBars": len(closed_three),
    }


def _ema(values, n):
    if len(values) < n:
        raise ValueError("V92_HIGHER_TF_EMA_NOT_ENOUGH_BARS")
    value = sum(values[:n]) / n
    alpha = 2.0 / (n + 1)
    for x in values[n:]:
        value = alpha * x + (1-alpha) * value
    return value


def _observation(tf, bars, seconds, as_of):
    last_close = bars[-1]["t"] + seconds
    if last_close > as_of:
        raise ValueError("V92_HIGHER_TF_FORBIDDEN_UNCLOSED_BAR")
    closes = [z["c"] for z in bars]
    ema20 = _ema(closes, 20)
    ema50 = _ema(closes, 50)
    close = closes[-1]
    trend = ema20_50_trend(bars)
    idx = len(bars)-1
    patterns = [{**p, "tf": tf}
                for p in all_patterns_at(bars, idx, seconds)]
    additional = soldier_crow(bars, idx, seconds)
    if additional:
        patterns.append({**additional, "tf": tf})
    return {
        "lastClosedCandleUTC": iso(last_close),
        "closedCandlesAvailable": len(bars),
        "close": close,
        "EMA20": round(ema20, 8),
        "EMA50": round(ema50, 8),
        "trendByCloseVsEMA20EMA50": trend,
        "observedReversalsAtLastCompletedCandle": patterns,
        "onlyFullyClosedCandlesUsed": True,
        "informationOnlyNotAutomaticNewTrade": True,
        "notVetoOrEntryFilter": True,
        "threeDaySource": (
            "DERIVED_UTC_UNIX_EPOCH_ALIGNED_3_COMPLETE_DAILY_OHLCV_BARS"
            if tf == "3D" else "VERIFIED_ORIGINAL_DAILY_CLOSED_OHLCV"
        ),
        "exchangeNative3DParityNotProven": tf == "3D",
    }


def higher_timeframe_context(daily, as_of):
    """Return reproducible 1D/3D WATCH data; fail closed on gaps/partials."""
    closed = _checked_closed_daily(daily, as_of)
    derived = aggregate_3d_from_daily(closed)
    return {
        "1D": _observation("1D", closed, DAY, as_of),
        "3D": _observation("3D", derived, THREE_DAYS, as_of),
    }
