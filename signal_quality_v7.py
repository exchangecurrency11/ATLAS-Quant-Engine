#!/usr/bin/env python3
"""V7 pre-registered PAPER-ONLY filters. Never publishes or sends trade orders.

All input is already-closed 1H OHLCV. BOS features are measured when the BOS
candle closes; retest features are measured only when a later retest candle
closes. Default thresholds are research hypotheses, NOT optimized or validated.
"""
from math import isfinite
from statistics import mean

from market_structure import average_true_range

DEFAULT_MIN_BREAK_ATR = 0.20
DEFAULT_MIN_RVOL20 = 1.20
DEFAULT_MAX_EMA20_EXTENSION_ATR = 2.50
DEFAULT_MIN_RETEST_CLOSE_ATR = 0.10


def _finite(value):
    try:
        number = float(value)
    except (ValueError, TypeError):
        return None
    return number if isfinite(number) else None


def evaluate_bos_quality(bars, bos, indicators, *,
                         min_break_atr=DEFAULT_MIN_BREAK_ATR,
                         min_rvol20=DEFAULT_MIN_RVOL20,
                         max_extension_atr=DEFAULT_MAX_EMA20_EXTENSION_ATR):
    """Return reasons and *point-in-time* features; no future bar allowed."""
    if len(bars) < 21:
        return {"passed": False, "reasons": ["INSUFFICIENT_CANDLES"], "features": {}}
    bar = bars[-1]
    if bos.get("event") != "BOS" or bos.get("at") != bar["t"] or bos.get("direction") not in ("bullish", "bearish"):
        return {"passed": False, "reasons": ["INVALID_OR_FUTURE_BOS"], "features": {}}

    side = bos["direction"]
    sign = 1 if side == "bullish" else -1
    atr = average_true_range(bars, len(bars) - 1, count=14)
    close = _finite(bar["c"])
    level = _finite(bos.get("brokenLevel"))
    ema20 = _finite(indicators.get("EMA20"))
    prior_volumes = [_finite(x["v"]) for x in bars[-21:-1]]
    volume = _finite(bar["v"])
    if (atr is None or not isfinite(atr) or atr <= 0 or close is None or
            level is None or ema20 is None or volume is None or
            any(x is None or x < 0 for x in prior_volumes)):
        return {"passed": False, "reasons": ["INVALID_MARKET_DATA"], "features": {}}
    average_volume = mean(prior_volumes)
    if average_volume <= 0:
        return {"passed": False, "reasons": ["NO_REFERENCE_VOLUME"], "features": {}}
    break_atr = sign * (close - level) / atr
    rvol20 = volume / average_volume
    extension_atr = sign * (close - ema20) / atr
    reasons = []
    if break_atr < min_break_atr:
        reasons.append("WEAK_BREAK_ATR")
    if rvol20 < min_rvol20:
        reasons.append("LOW_RELATIVE_VOLUME")
    if extension_atr > max_extension_atr:
        reasons.append("EMA20_OVEREXTENDED")
    rsi = _finite(indicators.get("RSI14"))
    warnings = []
    if rsi is not None and ((side == "bearish" and rsi <= 30) or
                            (side == "bullish" and rsi >= 70)):
        warnings.append("RSI_EXTREME_NOT_A_HARD_REJECTION")
    return {"passed": not reasons, "reasons": reasons, "warnings": warnings,
            "features": {"breakATR": round(break_atr, 6),
                         "relativeVolume20": round(rvol20, 6),
                         "ema20ExtensionATR": round(extension_atr, 6)}}


def evaluate_retest_quality(bars, active, retest_bar, *,
                            min_close_atr=DEFAULT_MIN_RETEST_CLOSE_ATR):
    """An extra rejection-strength check AFTER the existing V4 retest rule.

    Caller already verified level touch, directional candle and close vs prior.
    Requiring distance beyond broken BOS level aims to avoid weak rejections.
    """
    if not bars or bars[-1]["t"] != retest_bar["t"]:
        return {"passed": False, "reasons": ["FUTURE_OR_MISSING_RETEST"]}
    atr = average_true_range(bars, len(bars) - 1, count=14)
    if atr is None or not isfinite(atr) or atr <= 0:
        return {"passed": False, "reasons": ["INVALID_RETEST_ATR"]}
    side = active["side"]
    if side not in ("bullish", "bearish"):
        return {"passed": False, "reasons": ["INVALID_DIRECTION"]}
    sign = 1 if side == "bullish" else -1
    close_strength = sign * (retest_bar["c"] - active["level"]) / atr
    passed = close_strength >= min_close_atr
    return {"passed": passed,
            "reasons": [] if passed else ["WEAK_RETEST_REJECTION"],
            "features": {"retestCloseDistanceATR": round(close_strength, 6)}}
