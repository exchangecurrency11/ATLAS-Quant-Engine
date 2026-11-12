#!/usr/bin/env python3
"""V9.2 causal 1D/3D retest-context ablation, historical paper only.

Daily trend is EMA20/EMA50 alignment at the retest close. 3D is built only
from three fully closed consecutive daily candles aligned to UTC epoch
3-day boundaries. Existing V7 BOS/4H/Daily rules and exits are unchanged.
New filters are applied at the retest close only; no incomplete bar is read.
"""
import argparse
from collections import Counter
import json
from pathlib import Path

from backtest_retest_long_v4 import replay_pair
from market_structure import candles_from_history
from signal_quality_v7 import evaluate_bos_quality
from v7_paper_comparison import read_history
from v92_bull_bear_candle_invalidation import (
    START, END, HOUR, FOUR, SYMBOLS, stamp, metrics
)
from v92_higher_timeframe_context import context_at, aggregate_3d_from_daily
from v92_selected_reversal_patterns import make_selective_gate, summarize_audit

MODES = (
    "BASELINE",
    "CANDLE_ONLY",
    "DAILY_RETEST_CONFIRM",
    "3D_RETEST_CONFIRM",
    "DAILY_AND_3D_RETEST_CONFIRM",
    "CANDLE_PLUS_3D",
)


def make_gate(symbol, four, daily, *, candle_enabled, daily_enabled,
              three_enabled, audit):
    candle_audit = Counter()
    candle_audit["examples"] = []
    candle_gate = (make_selective_gate(
        symbol, four, "SELECTED_SOL_STRICT_SWEEP", candle_audit)
        if candle_enabled else None)

    def gate(hour_bars, active, retest):
        at = int(retest["t"]) + HOUR
        context = context_at(daily, at)
        audit["checkedRetests"] += 1
        audit["lastContextUTC"] = stamp(at)
        audit["dailyTrendCounts"][context["1D"]] += 1
        audit["threeDayTrendCounts"][context["3D"]] += 1
        passed = True
        reasons = []
        if daily_enabled and context["1D"] != "insufficient":
            if context["1D"] != active["side"]:
                passed = False
                reasons.append("DAILY_EMA20_50_NOT_ALIGNED_AT_RETEST")
                audit["dailyRejections"] += 1
        elif daily_enabled:
            audit["dailyWarmupPasses"] += 1
        if three_enabled and context["3D"] != "insufficient":
            if context["3D"] != active["side"]:
                passed = False
                reasons.append("3D_EMA20_50_NOT_ALIGNED_AT_RETEST")
                audit["threeDayRejections"] += 1
        elif three_enabled:
            audit["threeDayWarmupPasses"] += 1
        if candle_gate is not None:
            candle_decision = candle_gate(hour_bars, active, retest)
            if not candle_decision["passed"]:
                passed = False
                reasons.extend(candle_decision.get("reasons", []))
        return {"passed": passed, "reasons": reasons}

    return gate, candle_audit


def _same(a, b, label):
    for key in ("trades", "wins"):
        if a[key] != b[key]:
            raise ValueError("V92_HTF_BASELINE_MISMATCH_" + label + "_" + key)
    for key in ("totalNetR9BpsPerSide", "totalNetR25BpsPerSideStress"):
        if abs(a[key] - b[key]) > 0.0001:
            raise ValueError("V92_HTF_BASELINE_MISMATCH_" + label + "_" + key)


def run(hist, selected_reference, warmup_daily):
    if (selected_reference.get("status") !=
        "SELECTIVE_SOL_STAR_HARAMI_AND_OTHER_HIGH_PROFILE_CANDLE_WATCHES_HISTORICAL_ONLY"
        or selected_reference.get("fromUTC") != stamp(START)
        or selected_reference.get("toUTCExclusive") != stamp(END)
        or not selected_reference.get("sameVerifiedBinanceBTCAndSOLSource")):
        raise ValueError("V92_HTF_SELECTED_REFERENCE_UNVERIFIED")

    result = {
        "status": "V92_1D_3D_RETEST_CONTEXT_ABLATION_HISTORICAL_PAPER_ONLY",
        "fromUTC": stamp(START),
        "toUTCExclusive": stamp(END),
        "source": "Same previously SHA256-verified official Binance USD-M BTC/SOL archive",
        "verifiedTimeframes": ["1H", "4H", "1D"],
        "derived3D": "Three consecutive fully closed daily candles, UTC epoch 3-day alignment",
        "3DExchangeNativeParityProven": False,
        "trendRule": "At retest close, last closed bar close above both EMA20/EMA50 = bullish; below both = bearish; otherwise mixed",
        "insufficientWarmup": "Pass without new veto and counted separately; no future bars",
        "existingV7V91BOS4HDailyAndExitRulesUnchanged": True,
        "selectedCandleRule": "SOL only; opposing closed Star/confirmed Harami plus prior20 sweep and re-entry",
        "noBrokerOrders": True,
        "noUserNotifications": True,
        "notRealProfit": True,
        "previouslyInspectedHistoryNotIndependent": True,
        "noPromotionWithoutProspectiveValidation": True,
        "modes": list(MODES),
        "symbols": {},
    }

    for symbol, ref in SYMBOLS.items():
        hour = hist["1hour"][ref]
        four = hist["4hour"][ref]
        daily = hist["daily"][ref]
        h = candles_from_history(hour, "1hour", END)
        f = candles_from_history(four, "4hour", END)
        d = candles_from_history(daily, "daily", END)
        warm = candles_from_history(warmup_daily[ref], "daily", END)
        d_context = candles_from_history(warmup_daily[ref] + daily, "daily", END)
        if (len(h) != 17520 or len(f) != 4380 or len(d) != 730
            or len(warm) != 183 or len(d_context) != 913):
            raise ValueError("V92_HTF_ARCHIVE_COUNT_MISMATCH_" + symbol)
        if context_at(d_context, START)["3D"] == "insufficient":
            raise ValueError("V92_HTF_3D_EMA50_WARMUP_INCOMPLETE_" + symbol)
        if len(aggregate_3d_from_daily(d_context)) < 300:
            raise ValueError("V92_HTF_EXPECTED_FULL_3D_CONTEXT_MISSING_" + symbol)

        prior = selected_reference["symbols"][symbol]["variants"]
        symbol_result = {
            "verifiedCandles": {"1H": len(h), "4H": len(f), "1D": len(d)},
            "contextWarmupDailyBars": len(warm),
            "contextWarmupPeriodUTC": ["2024-04-01T00:00:00Z", "2024-10-01T00:00:00Z"],
            "derived3DContextCandlesWithWarmup": len(aggregate_3d_from_daily(d_context)),
            "variants": {},
        }
        for base_name, retest_hours in (
            ("V7_ORIGINAL", 6), ("V91_RETEST_MAX4H", 4)
        ):
            baseline = replay_pair(
                hour, four, daily, as_of=END,
                retest_hours=retest_hours,
                bos_quality_filter=evaluate_bos_quality,
            )
            baseline_metrics = metrics(baseline, START, END)
            _same(baseline_metrics, prior[base_name],
                  symbol + "_" + base_name)
            symbol_result["variants"][base_name] = baseline_metrics

            for mode in MODES[1:]:
                candle_enabled = mode in ("CANDLE_ONLY", "CANDLE_PLUS_3D")
                daily_enabled = mode in (
                    "DAILY_RETEST_CONFIRM", "DAILY_AND_3D_RETEST_CONFIRM")
                three_enabled = mode in (
                    "3D_RETEST_CONFIRM", "DAILY_AND_3D_RETEST_CONFIRM",
                    "CANDLE_PLUS_3D")
                audit = Counter()
                audit["dailyTrendCounts"] = Counter()
                audit["threeDayTrendCounts"] = Counter()
                gate, candle_audit = make_gate(
                    symbol, f, d_context,
                    candle_enabled=candle_enabled,
                    daily_enabled=daily_enabled,
                    three_enabled=three_enabled,
                    audit=audit)
                rep = replay_pair(
                    hour, four, daily, as_of=END,
                    retest_hours=retest_hours,
                    bos_quality_filter=evaluate_bos_quality,
                    retest_quality_filter=gate,
                )
                score = metrics(rep, START, END)
                score["deltaNetRVsOwnBaseline"] = round(
                    score["totalNetR9BpsPerSide"] -
                    baseline_metrics["totalNetR9BpsPerSide"], 6)
                score["deltaNetRVsCandleOnly"] = None
                score["contextAudit"] = {
                    "checkedRetests": audit["checkedRetests"],
                    "dailyTrendCounts": dict(audit["dailyTrendCounts"]),
                    "threeDayTrendCounts": dict(audit["threeDayTrendCounts"]),
                    "dailyRejections": audit["dailyRejections"],
                    "threeDayRejections": audit["threeDayRejections"],
                    "dailyWarmupPasses": audit["dailyWarmupPasses"],
                    "threeDayWarmupPasses": audit["threeDayWarmupPasses"],
                    "candleAudit": summarize_audit(candle_audit)
                        if candle_enabled else None,
                }
                symbol_result["variants"][base_name + "__" + mode] = score

            candle = symbol_result["variants"][base_name + "__CANDLE_ONLY"]
            for mode in MODES:
                key = (base_name if mode == "BASELINE"
                       else base_name + "__" + mode)
                symbol_result["variants"][key]["deltaNetRVsCandleOnly"] = round(
                    symbol_result["variants"][key]["totalNetR9BpsPerSide"] -
                    candle["totalNetR9BpsPerSide"], 6)

            # Existing selective-candle result is the exact control arm.
            expected = prior[base_name + "__SELECTED_SOL_STRICT_SWEEP"]
            _same(candle, expected, symbol + "_" + base_name + "_CANDLE")
        result["symbols"][symbol] = symbol_result
    return result


def markdown(data):
    lines = [
        "# V9.2 1D / 3D retest context backtest",
        "",
        "**Historical paper research only. Not live results.**",
        "Period: " + data["fromUTC"] + " to " + data["toUTCExclusive"] + " (exclusive).",
        "The original strategy already uses 1D direction at BOS. This experiment separately re-checks 1D and derived 3D trend at the retest close.",
        "3D candles are aggregated from three completed daily candles on a fixed UTC epoch grid; this is not proven exchange-native 3D parity.",
        "EMA20/EMA50 alignment is the only new trend rule. Mixed direction blocks a confirmation variant; insufficient warmup passes and is separately counted.",
        "Same source and unchanged V7/V9.1 BOS, retest, next-open fill, stop/TP and costs. Previously inspected history is not independent.",
        "",
        "| Coin | Baseline | Variant | Trades | Wins | Win % | Net R | Stress R | Δ vs base | Δ vs candle |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for symbol, item in data["symbols"].items():
        for name, score in item["variants"].items():
            base = name.split("__", 1)[0]
            variant = name.split("__", 1)[1] if "__" in name else "BASELINE"
            lines.append(
                f"| {symbol} | {base} | {variant} | {score['trades']} | {score['wins']} | "
                f"{score['winRatePct']} | {score['totalNetR9BpsPerSide']:.4f} | "
                f"{score['totalNetR25BpsPerSideStress']:.4f} | "
                f"{score.get('deltaNetRVsOwnBaseline', 0):.4f} | "
                f"{score.get('deltaNetRVsCandleOnly', 0):.4f} |"
            )
    lines += [
        "",
        "No real orders, alerts, funding or executable fills. Fees/slippage are the existing illustrative assumptions.",
        "No V7/V9.1 production changes. No filter promotion from this retrospective test.",
        "",
    ]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", default="v92_verified_archive")
    parser.add_argument("--selected", default="forward/v92_selected_reversal_patterns/historical.json")
    parser.add_argument("--warmup-daily", default="v92_verified_warmup/history_daily_warmup.json")
    parser.add_argument("--out", default="forward/v92_higher_timeframe_backtest_warmup")
    args = parser.parse_args()
    histories = {
        tf: read_history(str(Path(args.archive) / ("history_" + tf + ".json")))
        for tf in ("1hour", "4hour", "daily")
    }
    selected = json.loads(Path(args.selected).read_text())
    warmup_daily = read_history(args.warmup_daily)
    data = run(histories, selected, warmup_daily)
    data["contextWarmupSource"] = "Official Binance USD-M monthly 1H ZIPs; 12 SHA256-verified files; 1D derived from complete 1H bars"
    data["contextWarmupExcludedFromPerformancePeriod"] = True
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "historical.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    (out / "historical.md").write_text(markdown(data) + "\n")
    print("V92_1D_3D_HTF_BACKTEST_COMPLETE",
          json.dumps({sym: {
              k: {"trades": v["trades"], "wins": v["wins"],
                  "netR": v["totalNetR9BpsPerSide"],
                  "delta": v.get("deltaNetRVsOwnBaseline")}
              for k, v in item["variants"].items()}
              for sym, item in data["symbols"].items()}), flush=True)


if __name__ == "__main__":
    main()
