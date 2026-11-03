#!/usr/bin/env python3
"""V7 offline paper comparison on identical historical closed BTC/SOL candles.

No orders, no live alerts, no connection to the production pipeline.
Runs the FULL chronological V4 simulator with optional V7 gates, rather than
falsely treating a post-hoc winning subset as a newly simulated strategy.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from statistics import mean
import math

from backtest_retest_long_v4 import replay_pair, indicators
from market_structure import candles_from_history
from signal_quality_v7 import evaluate_bos_quality, evaluate_retest_quality

PAIRS = ("BTCUSDT_PERP.A", "SOLUSDT_PERP.A")
COST_ASSUMPTION = "6bps fee + 3bps slippage per side; funding and real fills excluded"


def read_history(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, list) or len(data) != 2:
        raise ValueError("Expected exactly two perpetual symbols in " + path)
    groups = {}
    for item in data:
        if item.get("symbol") not in PAIRS or item["symbol"] in groups:
            raise ValueError("Wrong or duplicate perpetual symbol in " + path)
        groups[item["symbol"]] = item["history"]
    if set(groups) != set(PAIRS):
        raise ValueError("Missing perpetual symbol in " + path)
    return groups


def compute_metrics(report):
    trades = report.get("trades", [])
    values = [t["netRIllustrative"] for t in trades]
    count = len(values)
    cumulative = peak = drawdown = 0.
    for r in values:
        cumulative += r
        peak = max(peak, cumulative)
        drawdown = max(drawdown, peak - cumulative)
    gains = sum(max(0, r) for r in values)
    losses = sum(max(0, -r) for r in values)
    return {
        "alerts": report.get("alertsCount"),
        "completedPaperTrades": count,
        "positiveNetR": sum(r > 0 for r in values),
        "winRate": sum(r > 0 for r in values) / count if count else None,
        "meanNetR": mean(values) if count else None,
        "profitFactorInR": gains / losses if losses else (None if gains == 0 else "NO_LOSSES"),
        "maxSequentialDrawdownR_NotEquity": drawdown if count else None,
        "qualityRejectedBOS": report.get("qualityGateRejectedBOS", 0),
        "qualityRejectedRetest": report.get("qualityGateRejectedRetest", 0),
        "qualityRejectionReasons": report.get("qualityGateRejectionReasons", {}),
        "unresolvedExcluded": report.get("unresolvedPositionExcluded", False),
    }


def describe_baseline_alerts(bars, baseline, as_of):
    """A DIAGNOSTIC of baseline watches; NOT a strategy replay."""
    closed = candles_from_history(bars, "1hour", as_of)
    index = {b["t"] + 3600: i for i, b in enumerate(closed)}
    descriptions = []
    for a in baseline.get("alerts", []):
        i = index[a["knownUTC"]]
        bos = {"event": "BOS", "at": closed[i]["t"],
               "direction": a["side"], "brokenLevel": a["BOSLevel"]}
        decisions = {}
        for name, settings in (
            ("breakOnly", {"min_rvol20": 0., "max_extension_atr": 1e9}),
            ("rvolOnly", {"min_break_atr": 0., "max_extension_atr": 1e9}),
            ("extensionOnly", {"min_break_atr": 0., "min_rvol20": 0.}),
            ("combined", {}),
        ):
            ind = indicators(closed[:i+1])
            decisions[name] = evaluate_bos_quality(
                closed[max(0, i-249):i+1], bos, ind, **settings)
        descriptions.append({
            "knownUTC": a["knownUTC"], "side": a["side"],
            "BOSLevel": a["BOSLevel"], "diagnostic": decisions,
        })
    matched_trades = {t["watchKnownUTC"] for t in baseline.get("trades", [])}
    return {
        "baselineWarnings": len(descriptions),
        "baselinePaperTradesWithMatchedWarning": sum(
            r["knownUTC"] in matched_trades for r in descriptions),
        "isolatedSignalPassCounts": {
            key: sum(r["diagnostic"][key]["passed"] for r in descriptions)
            for key in ("breakOnly", "rvolOnly", "extensionOnly", "combined")
        },
        "warningAudit": descriptions,
        "IMPORTANT": "Descriptive baseline warning subsets only; NOT filtered win rates or a full counterfactual backtest.",
    }


def compare(histories, *, as_of):
    reports = {}
    for symbol in PAIRS:
        h = histories["1hour"][symbol]
        four = histories["4hour"][symbol]
        day = histories["daily"][symbol]
        # The underlying V4 simulator is identical for all 3 scenarios.
        baseline = replay_pair(h, four, day, as_of=as_of)
        signal_gate = replay_pair(
            h, four, day, as_of=as_of,
            bos_quality_filter=evaluate_bos_quality)
        signal_and_retest_gate = replay_pair(
            h, four, day, as_of=as_of,
            bos_quality_filter=evaluate_bos_quality,
            retest_quality_filter=evaluate_retest_quality)
        for name, report in (
            ("baseline_V4", baseline),
            ("V7_signal_gate", signal_gate),
            ("V7_signal_and_retest_gate", signal_and_retest_gate),
        ):
            if report.get("status") != "PAPER_BACKTEST_NOT_LIVE":
                raise ValueError(symbol + " " + name + " history not ready")
        reports[symbol] = {
            "metrics": {
                "baseline_V4": compute_metrics(baseline),
                "V7_signal_gate": compute_metrics(signal_gate),
                "V7_signal_and_retest_gate": compute_metrics(signal_and_retest_gate),
            },
            "baselineWarningDiagnostics": describe_baseline_alerts(h, baseline, as_of),
            "paperTradesByVariant": {
                key: report["trades"] for key, report in (
                    ("baseline_V4", baseline),
                    ("V7_signal_gate", signal_gate),
                    ("V7_signal_and_retest_gate", signal_and_retest_gate),
                )
            },
        }
    return {
        "mode": "V7_HISTORICAL_PAPER_DIAGNOSTIC_ONLY",
        "asOfUTC": datetime.fromtimestamp(as_of, timezone.utc).isoformat(),
        "variants": {
            "baseline_V4": "Identical existing chronological BOS + later retest + next-open V4 paper simulator",
            "V7_signal_gate": "ATR break >=0.20, trailing previous-20 relative volume >=1.20, EMA20 extension <=2.50 ATR",
            "V7_signal_and_retest_gate": "Signal gate + subsequent retest close >=0.10 ATR beyond BOS level",
        },
        "costAssumptions": COST_ASSUMPTION,
        "restrictions": [
            "Same already-inspected historical period; no untouched out-of-sample evaluation.",
            "Thresholds are hypotheses, not optimized or predictive confidence levels.",
            "Filter effects on new signals/trade scheduling require FULL replay (done for 3 variants).",
            "Real fills, funding, spread, order book, partial executions and liquidation excluded.",
            "No live deployment or production code modification.",
        ],
        "results": reports,
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--hour", required=True)
    p.add_argument("--four", required=True)
    p.add_argument("--daily", required=True)
    p.add_argument("--output", default="v7-paper-comparison.json")
    p.add_argument("--as-of-utc", default="2026-11-03T00:00:00+00:00",
                   help="Exclusive end of completed-candle history")
    a = p.parse_args()
    as_of = int(datetime.fromisoformat(
        a.as_of_utc.replace("Z", "+00:00")).timestamp())
    histories = {
        "1hour": read_history(a.hour),
        "4hour": read_history(a.four),
        "daily": read_history(a.daily),
    }
    result = compare(histories, as_of=as_of)
    Path(a.output).write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for symbol, item in result["results"].items():
        print(symbol)
        for variant, met in item["metrics"].items():
            print(" ", variant, "alerts", met["alerts"],
                  "trades", met["completedPaperTrades"],
                  "wins", met["positiveNetR"],
                  "meanNetR", met["meanNetR"],
                  "drawdownInR", met["maxSequentialDrawdownR_NotEquity"],
                  "qualityRejects", met["qualityRejectedBOS"],
                  met["qualityRejectedRetest"])
    print("PAPER-ONLY. Do not infer live profitability from this report.")


if __name__ == "__main__":
    main()
