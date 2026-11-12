#!/usr/bin/env python3
"""SOL-FLOW-02: add closed-candle taker/CVD gates ON TOP of V9.2 strict-sweep.

Same Binance USD-M history, unchanged V9.1 BOS/retest/exit engine, same
V9.2 selected SOL star/harami prior-20 sweep/reentry veto, then optional
flow gates. Exploratory historical paper only; never production.
"""
import argparse, json, math
from pathlib import Path
from market_structure import candles_from_history
from signal_quality_v7 import evaluate_bos_quality
from v7_paper_comparison import read_history
from backtest_retest_long_v4 import replay_pair
from v92_bull_bear_candle_invalidation import gated_retest_factory, START, END, stamp
from sol_flow_01 import FlowIndex, score, decision, ARMS as FLOW_ARMS

SYMBOL = "SOLUSDT_PERP.A"
BASE = "V92_STRICT_SWEEP_CONTROL"
ARMS = (
    BASE,
    "V92_PLUS_1H_TAKER",
    "V92_PLUS_4H_CVD",
    "V92_PLUS_TAKER_AND_CVD",
    "V92_PLUS_TAKER_CVD_RVOL",
)
EXPECTED_BASE_TRADES = 8
EXPECTED_BASE_WINS = 5
EXPECTED_BASE_NET_R9 = 4.260655
EXPECTED_BASE_NET_R25 = 2.409915


def compose_gate(v92_gate, flow_index, arm, audit):
    flow_map = {
        BASE: None,
        ARMS[1]: "FLOW_1H_TAKER_AGREES",
        ARMS[2]: "FLOW_4H_CVD_AGREES",
        ARMS[3]: "FLOW_1H_4H_RVOL",
        ARMS[4]: "FLOW_1H_4H_RVOL",
    }
    def check(bars, active, retest):
        # V9.2 selected star/harami prior-20 sweep/reentry gate is always first.
        v92 = v92_gate(bars, active, retest)
        audit["v92EligibleRetests"] += 1
        if not v92["passed"]:
            audit["v92Vetoes"] += 1
            return v92
        flow_arm = flow_map[arm]
        if flow_arm is None:
            return {"passed": True, "reasons": []}
        at = int(retest["t"]) + 3600
        f = flow_index.at(at)
        # Guard against any difference between the flow source's final 1H
        # candle and the V9.1 replay engine's exact retest candle.
        for k in ("t", "o", "h", "l", "c", "v"):
            if not math.isclose(float(f["last1HRawOHLCV"][k]),
                                float(retest[k]), rel_tol=1e-9, abs_tol=1e-6):
                raise ValueError("FLOW02_V92_RETEST_SOURCE_MISMATCH_" + k)
        allowed, reasons = decision(f, active["side"], flow_arm)
        audit["flowEligibleRetests"] += 1
        if not allowed:
            audit["flowVetoes"] += 1
            for reason in reasons:
                audit["flowReasonCounts"][reason] = audit["flowReasonCounts"].get(reason, 0) + 1
            return {"passed": False, "reasons": reasons}
        return {"passed": True, "reasons": []}
    return check


def run(histories, v92_reference, manifest):
    # Reuse the independently archived V9.2 historical report as a frozen
    # benchmark. Require exact source interval and the known strict-sweep row.
    if (v92_reference.get("status") !=
        "SELECTIVE_SOL_STAR_HARAMI_AND_OTHER_HIGH_PROFILE_CANDLE_WATCHES_HISTORICAL_ONLY"
        or v92_reference.get("sameVerifiedBinanceBTCAndSOLSource") is not True
        or v92_reference.get("fromUTC") != stamp(START)
        or v92_reference.get("toUTCExclusive") != stamp(END)
        or v92_reference.get("noV7V91ProductionChanges") is not True):
        raise ValueError("FLOW02_INVALID_V92_REFERENCE")
    source_files = manifest.get("inputFiles", [])
    if not (manifest.get("source", "").startswith("Binance official data.binance.vision")
            and manifest.get("checksumsVerified") == len(source_files) == 48
            and manifest.get("pairCounts", {}).get("SOLUSDT", {}).get("1hour") == 17520):
        raise ValueError("FLOW02_INVALID_BINANCE_SOURCE_MANIFEST")
    hour = histories["1hour"][SYMBOL]
    four = histories["4hour"][SYMBOL]
    daily = histories["daily"][SYMBOL]
    if not hour or hour[0]["t"] != START or hour[-1]["t"] + 3600 != END:
        raise ValueError("FLOW02_WRONG_HISTORICAL_INTERVAL")
    flow = FlowIndex(hour)
    four_closed = candles_from_history(four, "4hour", END)
    expected = v92_reference["symbols"]["SOLUSDT"]["variants"]["V91_RETEST_MAX4H__SELECTED_SOL_STRICT_SWEEP"]
    out = {
        "status": "SOL_FLOW_02_V92_STRICT_SWEEP_PLUS_FLOW_EXPLORATORY_HISTORICAL_PAPER_ONLY",
        "symbol": "SOLUSDT", "startUTC": stamp(START), "endExclusiveUTC": stamp(END),
        "source": "Binance official USD-M monthly 1H klines, checksum verified",
        "sameHistoryAllArms": True, "baseV92StrictSweepParityVerified": False,
        "V92StrictSweepAppliedBeforeEveryFlowFilter": True,
        "V9_1BOSRetestStopTargetEngineUnchanged": True,
        "next1HOpenHypotheticalEntry": True, "sameCandleStopFirst": True,
        "flowOnlyUsesCompleted1HCandles": True,
        "noFutureFlowFeatures": True, "brokerOrders": False, "alerts": False,
        "productionModified": False, "promotionApproved": False,
        "historicalPeriodPreviouslyInspected": True,
        "notIndependentProspectiveEvidence": True,
        "results": {},
    }
    for arm in ARMS:
        audit = {"v92EligibleRetests": 0, "v92Vetoes": 0,
                 "flowEligibleRetests": 0, "flowVetoes": 0,
                 "flowReasonCounts": {}}
        v92_gate = gated_retest_factory(four_closed, True, {
            "examples": [], "eligibleOriginalRetestsChecked": 0,
            "oppositePatternVetoCount": 0, "MORNING_STAR_1H": 0,
            "EVENING_STAR_1H": 0, "MORNING_STAR_4H": 0,
            "EVENING_STAR_4H": 0})
        gate = compose_gate(v92_gate, flow, arm, audit)
        replay = replay_pair(hour, four, daily, as_of=END,
                             retest_hours=4,
                             bos_quality_filter=evaluate_bos_quality,
                             retest_quality_filter=gate)
        summary = score(replay)
        out["results"][arm] = {"summary": summary, "audit": audit}
    base = out["results"][BASE]["summary"]
    if (base["trades"] != EXPECTED_BASE_TRADES or
        base["winsNet"] != EXPECTED_BASE_WINS or
        abs(base["netR9BpsPerSide"] - EXPECTED_BASE_NET_R9) > .00011 or
        abs(base["netR25BpsPerSide"] - EXPECTED_BASE_NET_R25) > .00011 or
        base["trades"] != expected["trades"] or
        base["winsNet"] != expected["wins"] or
        abs(base["netR9BpsPerSide"] - expected["totalNetR9BpsPerSide"]) > .00011 or
        abs(base["netR25BpsPerSide"] - expected["totalNetR25BpsPerSideStress"]) > .00011):
        raise ValueError("FLOW02_V92_STRICT_SWEEP_CONTROL_PARITY_FAILED")
    out["baseV92StrictSweepParityVerified"] = True
    for arm, item in out["results"].items():
        s = item["summary"]
        s["deltaNetR9VsV92StrictSweep"] = round(s["netR9BpsPerSide"] - base["netR9BpsPerSide"], 6)
        s["deltaNetR25VsV92StrictSweep"] = round(s["netR25BpsPerSide"] - base["netR25BpsPerSide"], 6)
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--hour", required=True); p.add_argument("--four", required=True)
    p.add_argument("--daily", required=True); p.add_argument("--manifest", required=True)
    p.add_argument("--v92-reference", required=True)
    p.add_argument("--output", default="forward/sol_flow_02/latest.json")
    a = p.parse_args()
    hist = {tf: read_history(file) for tf, file in (
        ("1hour", a.hour), ("4hour", a.four), ("daily", a.daily))}
    result = run(hist, json.loads(Path(a.v92_reference).read_text()),
                 json.loads(Path(a.manifest).read_text()))
    dest = Path(a.output); dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    for name, item in result["results"].items():
        s = item["summary"]
        print(name, s["trades"], s["winRatePct"],
              s["netR9BpsPerSide"], s["netR25BpsPerSide"],
              s["deltaNetR9VsV92StrictSweep"], flush=True)


if __name__ == "__main__":
    main()
