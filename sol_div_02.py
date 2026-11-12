#!/usr/bin/env python3
"""SOL-DIV-02: matched CVD divergence + BOS retest / liquidity sweep / volume.

All arms use the same V9.2 strict-sweep gate, BOS/retest engine, next-open
hypothetical entry and exits. Only closed 1H bars are used. Historical paper
research only; no production, alert or broker actions.
"""
import argparse, json
from collections import Counter
from pathlib import Path

from signal_quality_v7 import evaluate_bos_quality
from v7_paper_comparison import read_history
from backtest_retest_long_v4 import replay_pair
from v92_bull_bear_candle_invalidation import START, END, HOUR, stamp
from v92_selected_reversal_patterns import make_selective_gate
from sol_flow_01 import FlowIndex, score
from sol_div_01 import DivergenceIndex, SYMBOL, BASE as V92_BASE

BASE = "V92_STRICT_SWEEP_CONTROL"
ARMS = (
    BASE,
    "CVD_1H_DIVERGENCE_PLUS_BOS_RETEST",
    "CVD_DIVERGENCE_PLUS_BOS_RETEST_PLUS_LIQUIDITY_SWEEP",
    "CVD_DIVERGENCE_PLUS_BOS_RETEST_PLUS_VOLUME_INCREASE",
    "CVD_DIVERGENCE_PLUS_BOS_RETEST_PLUS_SWEEP_AND_VOLUME",
)
VOLUME_MULTIPLE = 1.20
SWEEP_LOOKBACK = 20


def retest_sweep(bars, side, retest):
    """Prior 20 completed 1H candles, swept by retest wick and closed back in."""
    if len(bars) < SWEEP_LOOKBACK + 1 or bars[-1]["t"] != retest["t"]:
        raise ValueError("DIV02_RETEST_WINDOW_MISMATCH")
    prior = bars[-SWEEP_LOOKBACK-1:-1]
    prior_high = max(float(x["h"]) for x in prior)
    prior_low = min(float(x["l"]) for x in prior)
    close = float(retest["c"])
    if side == "bullish":
        return (float(retest["l"]) < prior_low and close > prior_low), {
            "prior20Low": prior_low, "retestLow": float(retest["l"]),
            "retestClose": close, "sweptAndReentered": bool(
                float(retest["l"]) < prior_low and close > prior_low)}
    return (float(retest["h"]) > prior_high and close < prior_high), {
        "prior20High": prior_high, "retestHigh": float(retest["h"]),
        "retestClose": close, "sweptAndReentered": bool(
            float(retest["h"]) > prior_high and close < prior_high)}


def make_gate(v92_gate, flow, div, arm, audit):
    def gate(bars, active, retest):
        v = v92_gate(bars, active, retest)
        audit["v92Retests"] += 1
        if not v["passed"]:
            audit["v92Vetoes"] += 1
            return v

        at = int(retest["t"]) + HOUR
        f = flow.at(at)
        d = div.at(at)
        side = active["side"]
        aligned = d["bullish"] if side == "bullish" else d["bearish"]
        audit["divergenceEligible"] += 1
        if not aligned:
            audit["divergenceVetoes"] += 1
            return {"passed": False, "reasons": ["NO_CONFIRMED_1H_CVD_DIVERGENCE"]}

        audit["divergencePassed"] += 1
        needs_sweep = arm in (ARMS[2], ARMS[4])
        needs_volume = arm in (ARMS[3], ARMS[4])
        evidence = {"knownAtUTC": stamp(at), "side": side,
                    "divergence": d, "relativeVolume20": f["relativeVolume20"]}
        if needs_sweep:
            ok, sweep_evidence = retest_sweep(bars, side, retest)
            evidence["liquiditySweep"] = sweep_evidence
            if not ok:
                audit["sweepVetoes"] += 1
                return {"passed": False, "reasons": ["NO_PRIOR20_LIQUIDITY_SWEEP_REENTRY"]}
            audit["sweepPassed"] += 1
        if needs_volume:
            ok = f["relativeVolume20"] >= VOLUME_MULTIPLE
            evidence["volumeThreshold"] = VOLUME_MULTIPLE
            evidence["volumePassed"] = bool(ok)
            if not ok:
                audit["volumeVetoes"] += 1
                return {"passed": False, "reasons": ["RETEST_VOLUME_BELOW_1_20X_PRIOR20_MEAN"]}
            audit["volumePassed"] += 1
        audit["finalPassed"] += 1
        if len(audit["examples"]) < 30:
            audit["examples"].append(evidence)
        return {"passed": True, "reasons": []}
    return gate


def run(hist, reference, manifest):
    if (reference.get("status") !=
        "SELECTIVE_SOL_STAR_HARAMI_AND_OTHER_HIGH_PROFILE_CANDLE_WATCHES_HISTORICAL_ONLY"
        or reference.get("sameVerifiedBinanceBTCAndSOLSource") is not True
        or reference.get("fromUTC") != stamp(START)
        or reference.get("toUTCExclusive") != stamp(END)
        or reference.get("noV7V91ProductionChanges") is not True):
        raise ValueError("DIV02_INVALID_V92_REFERENCE")
    proof = manifest.get("inputFiles", [])
    if not (manifest.get("source", "").startswith("Binance official data.binance.vision")
            and manifest.get("checksumsVerified") == len(proof) == 48
            and manifest.get("pairCounts", {}).get("SOLUSDT", {}).get("1hour") == 17520):
        raise ValueError("DIV02_INVALID_SOURCE_MANIFEST")

    hour = hist["1hour"][SYMBOL]
    four = hist["4hour"][SYMBOL]
    daily = hist["daily"][SYMBOL]
    if not hour or hour[0]["t"] != START or hour[-1]["t"] + HOUR != END:
        raise ValueError("DIV02_WRONG_SOURCE_INTERVAL")
    flow = FlowIndex(hour)
    div = DivergenceIndex(hour, HOUR)
    out = {
        "status": "SOL_DIV_02_CVD_BOS_SWEEP_VOLUME_MATCHED_HISTORICAL_PAPER_ONLY",
        "symbol": "SOLUSDT", "startUTC": stamp(START),
        "endExclusiveUTC": stamp(END),
        "source": "Binance official USD-M monthly 1H klines, checksum verified",
        "sameHistoryAllArms": True, "v92StrictSweepBeforeEveryArm": True,
        "pivotConfirmationWaited": True, "onlyClosedCandles": True,
        "noFutureFeatures": True, "CVDTimeframe": "1H",
        "BOSRetestEngine": "unchanged V9.1/V9.2, next 1H open hypothetical entry",
        "liquiditySweepRule": "retest wick beyond prior 20 completed 1H high/low and close back inside",
        "volumeRule": "retest 1H base volume >= 1.20x preceding 20 completed 1H candle mean",
        "volumeThresholdMultiple": VOLUME_MULTIPLE,
        "brokerOrders": False, "alerts": False, "productionModified": False,
        "promotionApproved": False, "historicalPeriodPreviouslyInspected": True,
        "notIndependentProspectiveEvidence": True, "results": {}
    }

    for arm in ARMS:
        audit = Counter()
        audit["examples"] = []
        v92_audit = Counter()
        v92_audit["examples"] = []
        v92_gate = make_selective_gate(
            "SOLUSDT", __import__("market_structure").candles_from_history(
                four, "4hour", END), "SELECTED_SOL_STRICT_SWEEP", v92_audit)
        if arm == BASE:
            gate = v92_gate
        else:
            gate = make_gate(v92_gate, flow, div, arm, audit)
        replay = replay_pair(hour, four, daily, as_of=END, retest_hours=4,
                             bos_quality_filter=evaluate_bos_quality,
                             retest_quality_filter=gate)
        summary = score(replay)
        out["results"][arm] = {
            "summary": summary,
            "audit": {k: v for k, v in audit.items()},
            "v92SelectedPatternAudit": {
                "retests": v92_audit["retests"],
                "opposingPatternsObserved": v92_audit["opposingSelectedPatternsObserved"],
                "vetoes": v92_audit["vetoes"]}}

    base = out["results"][BASE]["summary"]
    expected = reference["symbols"]["SOLUSDT"]["variants"]["V91_RETEST_MAX4H__SELECTED_SOL_STRICT_SWEEP"]
    if (base["trades"] != expected["trades"] or base["winsNet"] != expected["wins"]
        or abs(base["netR9BpsPerSide"] - expected["totalNetR9BpsPerSide"]) > .00011
        or abs(base["netR25BpsPerSide"] - expected["totalNetR25BpsPerSideStress"]) > .00011):
        raise ValueError("DIV02_V92_CONTROL_PARITY_FAILED")
    out["v92StrictSweepControlParityVerified"] = True

    # Arm 1 must reproduce DIV-01's 1H divergence-only result exactly.
    expected_div = 1
    a = out["results"][ARMS[1]]["summary"]
    if a["trades"] != expected_div or abs(a["netR9BpsPerSide"] - 1.325925) > .00011:
        raise ValueError("DIV02_DIVERGENCE_ONLY_PARITY_FAILED")
    out["divergenceOnlyParityVerifiedAgainstDIV01"] = True
    for arm, item in out["results"].items():
        item["summary"]["deltaNetR9VsV92"] = round(
            item["summary"]["netR9BpsPerSide"] - base["netR9BpsPerSide"], 6)
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--hour", required=True); p.add_argument("--four", required=True)
    p.add_argument("--daily", required=True); p.add_argument("--manifest", required=True)
    p.add_argument("--v92-reference", required=True)
    p.add_argument("--output", default="forward/sol_div_02/latest.json")
    a = p.parse_args()
    hist = {tf: read_history(path) for tf, path in (
        ("1hour", a.hour), ("4hour", a.four), ("daily", a.daily))}
    result = run(hist, json.loads(Path(a.v92_reference).read_text()),
                 json.loads(Path(a.manifest).read_text()))
    dest = Path(a.output); dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    for name, item in result["results"].items():
        s = item["summary"]
        print(name, s["trades"], s["winsNet"], s["winRatePct"],
              s["netR9BpsPerSide"], s["netR25BpsPerSide"],
              s["deltaNetR9VsV92"], flush=True)


if __name__ == "__main__":
    main()
