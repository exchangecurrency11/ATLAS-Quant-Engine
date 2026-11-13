#!/usr/bin/env python3
"""Frozen 2022-10..2024-09 ETH ATR / BTC 4H and SOL BTC-4H temporal check.

Research only. Uses 2022-05..2024-09 SHA256-verified Binance USD-M monthly
BTC/ETH/SOL 1H ZIPs. 2022-05..09 is indicator/replay warmup; results are scored
only in 2022-10..2024-09. Exact V7 BOS quality + V9.1 4H retest replay.
No live strategy, V7, V9.2 capped account, notification or broker modification.
The frozen ATR threshold 1.5 and SOL BTC 4H agreement were selected on the
later 2024-2026 period. This earlier temporal check is not prospective proof.
"""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
import math
from pathlib import Path

from backtest_retest_long_v4 import replay_pair
from download_binance_um_history import aggregate, download_month, months_inclusive
from signal_quality_v7 import evaluate_bos_quality
from v92_bull_bear_candle_invalidation import HOUR, FOUR, stamp, metrics
from v92_selected_reversal_patterns import make_selective_gate
from v92_three_asset_correlation_study import AsOfRegimes

SYMBOLS = ("BTCUSDT", "ETHUSDT", "SOLUSDT")
MONTHS = months_inclusive("2022-05", "2024-09")
WARMUP_START = int(datetime(2022, 5, 1, tzinfo=timezone.utc).timestamp())
START = int(datetime(2022, 10, 1, tzinfo=timezone.utc).timestamp())
END = int(datetime(2024, 10, 1, tzinfo=timezone.utc).timestamp())
EXPECTED_1H = (END - WARMUP_START) // HOUR
ETH_MODES = (
    "V91_V92_4H_BASELINE",
    "ETH_ATR_LE_1P5_BTC",
    "ETH_BTC_4H_AGREE",
    "ETH_BTC_4H_AGREE_AND_ATR_LE_1P5",
)
SOL_MODES = (
    "V91_4H_UNFILTERED",
    "V92_BASELINE_SOL_SELECTED",
    "V92_BTC_4H_AGREE",
)


def decision(symbol, mode, side, ctx):
    """Only CLOSED 4H facts known when the retest 1H candle closed."""
    if side not in ("bullish", "bearish"):
        raise ValueError("OLDER_REGIME_INVALID_SIDE")
    if not ctx.get("available") or not ctx.get("allPricesAlreadyClosed"):
        return False
    trends = ctx.get("trend4H") or {}
    ratio = ctx.get("ethAtrPercentVsBTC")
    if symbol == "ETHUSDT":
        if mode == "ETH_ATR_LE_1P5_BTC":
            return ratio is not None and math.isfinite(ratio) and ratio <= 1.5
        if mode == "ETH_BTC_4H_AGREE":
            return trends.get("BTCUSDT") == side
        if mode == "ETH_BTC_4H_AGREE_AND_ATR_LE_1P5":
            return (trends.get("BTCUSDT") == side
                    and ratio is not None and math.isfinite(ratio)
                    and ratio <= 1.5)
    if symbol == "SOLUSDT" and mode == "V92_BTC_4H_AGREE":
        # EXACT frozen 2024-2026 SOL rule: both BTC and SOL 4H direction
        # must agree with the original active SOL BOS direction.
        return trends.get("BTCUSDT") == side and trends.get("SOLUSDT") == side
    raise ValueError("OLDER_REGIME_UNREGISTERED_MODE_" + symbol + "_" + mode)


def download_verified_history(workers):
    if len(MONTHS) != 29 or EXPECTED_1H != 21216:
        raise ValueError("OLDER_REGIME_FIXED_ARCHIVE_PERIOD_CHANGED")
    groups = {sym: {} for sym in SYMBOLS}
    source = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        tasks = {pool.submit(download_month, sym, month): (sym, month)
                 for sym in SYMBOLS for month in MONTHS}
        for future in as_completed(tasks):
            expected_sym, expected_month = tasks[future]
            sym, month, rows, proof = future.result()
            if (sym, month) != (expected_sym, expected_month):
                raise ValueError("OLDER_REGIME_SOURCE_SYMBOL_MONTH_MISMATCH")
            if len(proof["sha256"]) != 64 or not rows:
                raise ValueError("OLDER_REGIME_UNVERIFIED_SHA256")
            groups[sym][month] = rows
            source.append({"symbol": sym, "month": month, **proof})
            print("OLDER_REGIME_SHA256_OK", sym, month, len(rows), flush=True)
    if len(source) != 87:
        raise ValueError("OLDER_REGIME_NOT_87_VERIFIED_ARCHIVES")
    out = {}
    for sym in SYMBOLS:
        rows = [row for month in MONTHS for row in groups[sym][month]]
        if (len(rows) != EXPECTED_1H or rows[0]["t"] != WARMUP_START
                or rows[-1]["t"] + HOUR != END
                or any(row["t"] != WARMUP_START + i * HOUR
                       for i, row in enumerate(rows))):
            raise ValueError("OLDER_REGIME_GAP_DUPLICATE_BAD_BOUNDARY_" + sym)
        out[sym] = rows
    return out, sorted(source, key=lambda x: (x["symbol"], x["month"]))


def score_direction(trades, direction):
    chosen = [x for x in trades if x["side"] == direction]
    vals = [float(t["netRIllustrative"]) for t in chosen]
    stress = [v - 2 * (25 - 9) / 10000 * t["entry"] / t["risk"]
              for t, v in zip(chosen, vals)]
    win = sum(max(0, v) for v in vals)
    loss = -sum(min(0, v) for v in vals)
    return {
        "trades": len(chosen),
        "wins": sum(x > 0 for x in vals),
        "netR9Bps": round(sum(vals), 6),
        "netR25Bps": round(sum(stress), 6),
        "profitFactor9Bps": round(win / loss, 4) if loss else None,
    }


def evaluate(symbol, mode, hour, regimes):
    four = regimes.four[symbol]
    daily = aggregate(hour, 24 * HOUR)
    audit = Counter()
    candle_audit = Counter(examples=[])
    candle_gate = (make_selective_gate(symbol, four,
                                      "SELECTED_SOL_STRICT_SWEEP",
                                      candle_audit)
                   if symbol == "SOLUSDT"
                   and mode != "V91_4H_UNFILTERED" else None)
    baseline = mode in ("V91_V92_4H_BASELINE",
                        "V91_4H_UNFILTERED",
                        "V92_BASELINE_SOL_SELECTED")

    def gate(one, active, retest):
        at = int(retest["t"]) + HOUR
        if active["knownUTC"] >= at or at > END:
            raise ValueError("OLDER_REGIME_RETEST_CAUSALITY_BREACH")
        if candle_gate is not None:
            result = candle_gate(one, active, retest)
            if not result["passed"]:
                audit["originalV92CandleVetoes"] += 1
                return result
        if baseline:
            return {"passed": True, "reasons": []}
        ctx = regimes.at(at)
        audit["regimeRetestsChecked"] += 1
        if not ctx.get("available"):
            audit["regimeMissingClosedContext"] += 1
        else:
            if ctx["lastAll4HCloseUTC"] > stamp(at):
                raise ValueError("OLDER_REGIME_FUTURE_4H_CANDLE_USED")
        passed = decision(symbol, mode, active["side"], ctx)
        if not passed:
            audit["regimeVetoes"] += 1
        return {
            "passed": passed,
            "reasons": [] if passed else ["RESEARCH_ONLY_" + mode + "_VETO"],
        }

    result = replay_pair(hour, four, daily, as_of=END, retest_hours=4,
                         bos_quality_filter=evaluate_bos_quality,
                         retest_quality_filter=None if symbol == "ETHUSDT"
                         and baseline or symbol == "SOLUSDT"
                         and mode == "V91_4H_UNFILTERED" else gate)
    score = metrics(result, START, END)
    trades = sorted(
        [t for t in result["trades"]
         if START <= t["entryOpenUTC"] < END and t["exitKnownUTC"] <= END],
        key=lambda t: (t["exitKnownUTC"], t["entryOpenUTC"]),
    )
    if len(trades) != score["trades"]:
        raise ValueError("OLDER_REGIME_SCORE_TRADE_MISMATCH")
    evidence = []
    for tr in trades:
        if not (tr["watchKnownUTC"] < tr["retestKnownUTC"]
                <= tr["entryOpenUTC"] < tr["exitKnownUTC"]):
            raise ValueError("OLDER_REGIME_TRADE_LOOKAHEAD")
        if tr["risk"] <= 0 or tr["entry"] <= 0:
            raise ValueError("OLDER_REGIME_INVALID_RISK")
        stress = (tr["netRIllustrative"]
                  - 2 * (25 - 9) / 10000 * tr["entry"] / tr["risk"])
        evidence.append({
            "entryUTC": stamp(tr["entryOpenUTC"]),
            "exitUTC": stamp(tr["exitKnownUTC"]),
            "retestKnownUTC": stamp(tr["retestKnownUTC"]),
            "direction": tr["side"],
            "exitReason": tr["exitReason"],
            "netR9Bps": round(tr["netRIllustrative"], 6),
            "netR25Bps": round(stress, 6),
            "stopDistancePctOfEntry": round(
                100 * tr["risk"] / tr["entry"], 6),
        })
    score["byDirection"] = {
        side: score_direction(trades, side) for side in ("bullish", "bearish")
    }
    score["tradeEvidence"] = evidence
    score["gateAudit"] = {**dict(audit),
                          "originalV92CandleAudit": dict(candle_audit)}
    score["noHistoricalTradesEnteredIntoForwardAccount"] = True
    return score


def check_existing_older_baselines(btc, sol_v91, sol_v92):
    # Independently sealed 2022-2024 BTC/SOL holdout report, before this
    # new ETH-regime comparison. Fail closed if the replay motor drifts.
    expected = ((btc, 10, -4.265784, -7.701252),
                (sol_v91, 12, 4.6274, 2.0039),
                (sol_v92, 12, 4.6274, 2.0039))
    for score, trades, normal, stress in expected:
        if score["trades"] != trades:
            raise ValueError("OLDER_REGIME_PREVIOUS_BASELINE_COUNT_MISMATCH")
        if (abs(score["totalNetR9BpsPerSide"] - normal) > 0.00012
                or abs(score["totalNetR25BpsPerSideStress"] - stress) > 0.00012):
            raise ValueError("OLDER_REGIME_PREVIOUS_BASELINE_PNL_MISMATCH")


def run(workers):
    hour, manifest = download_verified_history(workers)
    regimes = AsOfRegimes(hour)
    base_btc = evaluate("BTCUSDT", "V91_V92_4H_BASELINE", hour["BTCUSDT"], regimes)
    result = {
        "status": "V92_OLDER_ETH_ATR_AND_SOL_BTC_4H_FIXED_RULE_TEMPORAL_CHECK",
        "scoredPeriodUTC": [stamp(START), stamp(END)],
        "indicatorWarmupUTC": [stamp(WARMUP_START), stamp(START)],
        "data": {
            "source": "Official Binance USD-M monthly 1H ZIP archives and SHA256 .CHECKSUM",
            "monthlyVerifiedArchives": len(manifest),
            "sourceManifest": manifest,
            "verified1HCandlesEachSymbol": EXPECTED_1H,
            "verified1HCandlesAll": len(SYMBOLS) * EXPECTED_1H,
            "4HAnd1DDerivedFromContiguous1H": True,
        },
        "frozenRules": {
            "ETH_ATR_LE_1P5_BTC": "ETH 4H ATR14% / BTC 4H ATR14% <= 1.5",
            "ETH_BTC_4H_AGREE": "BTC last closed 4H EMA20/50 trend matches ETH BOS direction",
            "SOL_BTC_4H_AGREE": "BTC and SOL last closed 4H EMA20/50 trends both match SOL BOS direction",
            "V92_SOL_CANDLE": "Opposing confirmed Star/Harami + prior-20 liquidity sweep/reentry veto",
            "entryExit": "Original V7 BOS quality + V9.1 max 4H retest + next 1H open with unchanged stops/TP",
            "costPerSideBps": [9, 25],
            "parametersSelectedFromLaterPeriod": True,
            "noRetuningUsingEarlierOutcomes": True,
        },
        "assets": {"BTCUSDT": {"parityReferenceOnly": base_btc},
                   "ETHUSDT": {"variants": {}},
                   "SOLUSDT": {"variants": {}}},
        "noBrokerOrders": True,
        "noUserNotifications": True,
        "noProductionV7V91V92Changes": True,
        "noForwardBookBackfills": True,
        "historicalOnlyNotIndependentLiveExecutionEvidence": True,
        "notHistoricalLiveCoinalyzeParity": True,
    }
    for mode in ETH_MODES:
        score = evaluate("ETHUSDT", mode, hour["ETHUSDT"], regimes)
        result["assets"]["ETHUSDT"]["variants"][mode] = score
        print("OLDER_ETH", mode, score["trades"],
              score["totalNetR9BpsPerSide"],
              score["totalNetR25BpsPerSideStress"], flush=True)
    for mode in SOL_MODES:
        score = evaluate("SOLUSDT", mode, hour["SOLUSDT"], regimes)
        result["assets"]["SOLUSDT"]["variants"][mode] = score
        print("OLDER_SOL", mode, score["trades"],
              score["totalNetR9BpsPerSide"],
              score["totalNetR25BpsPerSideStress"], flush=True)
    check_existing_older_baselines(
        base_btc,
        result["assets"]["SOLUSDT"]["variants"]["V91_4H_UNFILTERED"],
        result["assets"]["SOLUSDT"]["variants"]["V92_BASELINE_SOL_SELECTED"],
    )
    return result


def markdown(result):
    lines = [
        "# V9.2 ETH ATR and SOL BTC-4H older temporal check",
        "",
        "**Only a historical paper study. No broker orders, live orders or V7/V9.2 edits.**",
        "Scored UTC: 2022-10-01 to 2024-10-01 exclusive; warmup starts 2022-05-01.",
        "87 official Binance USD-M monthly files verified against SHA256 checksums.",
        "All 4H regime fields use candles closed by each retest-hour close.",
        "Frozen ETH ATR threshold = 1.5; BTC/ETH 4H direction and SOL/BTC 4H",
        "direction tests do not revise any threshold after viewing older results.",
        "",
        "| Symbol | Mode | Trades | Wins | Net R 9bps | Net R 25bps | Profit factor | Max DD R | Regime vetoes |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for sym in ("ETHUSDT", "SOLUSDT"):
        for mode, score in result["assets"][sym]["variants"].items():
            pf = score["profitFactor"]
            lines.append(
                f"| {sym} | {mode} | {score['trades']} | {score['wins']} | "
                f"{score['totalNetR9BpsPerSide']:+.4f} | "
                f"{score['totalNetR25BpsPerSideStress']:+.4f} | "
                f"{pf if pf is not None else 'N/A'} | "
                f"{score['maxDrawdownR']:.4f} | "
                f"{score['gateAudit'].get('regimeVetoes', 0)} |"
            )
    lines += [
        "", "## LONG / SHORT breakdown",
        "",
        "| Symbol | Mode | Side | Trades | Wins | Net R 9bps | Net R 25bps |",
        "|---|---|---|---:|---:|---:|---:|",
    ]
    for sym in ("ETHUSDT", "SOLUSDT"):
        for mode, score in result["assets"][sym]["variants"].items():
            for side, item in score["byDirection"].items():
                lines.append(
                    f"| {sym} | {mode} | {side} | {item['trades']} | "
                    f"{item['wins']} | {item['netR9Bps']:+.4f} | "
                    f"{item['netR25Bps']:+.4f} |"
                )
    lines += [
        "",
        "## Interpretation constraints",
        "",
        "- Earlier temporal split is not prospective evidence, and this entire period may have been inspected by other repository studies.",
        "- 9/25 bps per side are illustrative assumptions; funding, spread variation, market impact, liquidation and fill parity are not proven.",
        "- Stop distance % (entry to fixed original stop) is recorded per trade in JSON; this is NOT a 10/20 USDT capped-account sizing simulation.",
        "- 2022-2024 BTC and SOL V9.1/V9.2 prior backtest parity is a mandatory hard fail if it drifts.",
        "- This backtest is not included among the 50 forward-recorded completed paper trades.",
        "- V7 production, V9.2 prospective capped account and existing notifications remain untouched.",
        "",
    ]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--out", default="forward/v92_older_eth_sol_regimes_20261113")
    args = parser.parse_args()
    if not 1 <= args.workers <= 6:
        parser.error("workers must be 1..6")
    result = run(args.workers)
    directory = Path(args.out)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "historical.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    (directory / "historical.md").write_text(markdown(result) + "\n")
    print("OLDER_ETH_SOL_REGIMES_SHA256_AND_PARITY_COMPLETE", flush=True)


if __name__ == "__main__":
    main()
