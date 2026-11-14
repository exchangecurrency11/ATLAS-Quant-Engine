#!/usr/bin/env python3
"""ATLAS Core v0 — isolated research contracts and frozen BTC/SOL evidence.

E0 uses ALREADY-INSPECTED historical reports (NOT independent OOS).
E1 tests close-time semantics, stop-first gap execution and cost stress.
No orders, alerts, portfolio writes, model promotion or main changes.
"""
from __future__ import annotations
import argparse
from bisect import bisect_right
from datetime import datetime
from hashlib import sha1, sha256
import json
from pathlib import Path

HISTORY = Path("forward/btc_sol_v93_causal_regime_20261114/historical.json")
SPEC = Path("forward/btc_sol_v93_prospective_20261114/frozen_spec.json")
PINS = {
    str(HISTORY): "f0eff2f48c530f4ad9902fa09c6e395187541002",
    str(SPEC): "3086de7b9a2835a10baf778693899b68cc6a400d",
}
FREEZE = "2026-11-15T00:00:00Z"
COST_BPS = (9, 25, 50)
PERIODS = ("2022_2024", "2024_2026")
SYMBOLS = ("BTCUSDT", "SOLUSDT")

def pinned_json(path: Path):
    raw = path.read_bytes()
    git_sha = sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
    if git_sha != PINS[str(path)]:
        raise ValueError("SEALED_INPUT_DRIFT: " + str(path))
    return json.loads(raw), sha256(raw).hexdigest()

def utc_seconds(value: str):
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.utcoffset() is None or dt.utcoffset().total_seconds() != 0:
        raise ValueError("NON_UTC_TIME")
    return int(dt.timestamp())

def closed_bars_asof(bars: list[dict], interval: int, decision_utc: int, n: int):
    """Only candles whose entire timeframe has closed by decision_utc.

    Example: 4H candle opening 04:00 cannot be read until 08:00 UTC.
    """
    if interval not in (3600, 14400, 86400) or n < 1:
        raise ValueError("INVALID_INTERVAL_OR_WARMUP")
    times = [b["t"] for b in bars]
    if (any(not isinstance(t, int) or t % interval for t in times)
        or times != sorted(set(times))):
        raise ValueError("BAD_BAR_TIMELINE")
    last = bisect_right(times, decision_utc - interval)
    observed = bars[:last]
    if len(observed) < n:
        raise ValueError("INSUFFICIENT_CLOSED_HISTORY")
    for i, b in enumerate(observed):
        if i and b["t"]-observed[i-1]["t"] != interval:
            raise ValueError("MISSING_TIMEFRAME_BAR")
        o,h,l,c = (float(b[k]) for k in ("o","h","l","c"))
        if min(o,h,l,c) <= 0 or not l <= min(o,c) <= max(o,c) <= h:
            raise ValueError("INVALID_OHLC")
    return observed[-n:]

def stop_first_with_gap(side: str, stop: float, bar: dict):
    """On simultaneous stop/TP, stop wins; gap beyond stop fills worse."""
    if side == "LONG":
        return min(stop, float(bar["o"])) if float(bar["l"]) <= stop else None
    if side == "SHORT":
        return max(stop, float(bar["o"])) if float(bar["h"]) >= stop else None
    raise ValueError("INVALID_SIDE")

def cost_stress_r(net_r_9: float, entry: float, risk: float,
                  cost_per_side_bps: float, extra_funding_cost_r: float = 0.0):
    """Net R9 from original engine, not gross R. Two-leg incremental stress.

    Funding zero is only an unknown-data placeholder, not a validation.
    """
    if entry <= 0 or risk <= 0 or cost_per_side_bps < 0:
        raise ValueError("INVALID_COST_INPUT")
    return (net_r_9 - 2*(cost_per_side_bps-9)/10000*entry/risk
            - extra_funding_cost_r)

def audit():
    history, history_sha = pinned_json(HISTORY)
    spec, spec_sha = pinned_json(SPEC)
    if (history["status"] != "BTC_SOL_FULL_CHRONOLOGICAL_CAUSAL_REGIME_HISTORICAL_ONLY"
        or history["archiveCountSHA256VerifiedAgain"] != 159
        or not history["noIndependentHoldout"]
        or not history["historicalStudiesPreviouslyInspected"]
        or not history["noOrders"] or not history["noAutomaticCandidatePromotion"]):
        raise ValueError("UNSAFE_HISTORICAL_SOURCE")
    if (spec["freezeUTC"] != FREEZE or spec["perSideStressBps"] != list(COST_BPS)
        or not spec["noBrokerOrders"] or not spec["notAutomaticallyPromoted"]):
        raise ValueError("FROZEN_SPEC_CHANGED")
    output = {
        "status": "ATLAS_CORE_RESEARCH_ONLY", "experiment": "E0_HISTORICAL_TRANSFER_AUDIT",
        "independentOutOfSample": False, "forwardTrades": None,
        "frozenCandidateStartUTC": FREEZE,
        "reportSHA256": history_sha, "frozenSpecSHA256": spec_sha,
        "priorWorkflowReportedVerifiedArchives": 159,
        "archivesRedownloadedThisRun": False,
        "sourceProofLevel": "pinned Git blobs and existing report invariants",
        "productionTouched": False, "orders": False, "notifications": False,
        "portfolioProfitFactor": None, "portfolioMaxDrawdown": None,
        "ethIncludedInE0": False,
        "assets": {}
    }
    for symbol in SYMBOLS:
        periods = {}
        for period in PERIODS:
            row = history["periods"][period][symbol]
            if not row["baselineExactPreviousSourceParity"]:
                raise ValueError("BASELINE_PARITY_MISSING")
            for variant in ("baseline","candidate"):
                metrics = row["metrics"][variant]
                cost_rows = [metrics[str(x)] for x in COST_BPS]
                if len({m["trades"] for m in cost_rows}) != 1:
                    raise ValueError("COST_CHANGED_TRADE_COUNT")
                if not all(cost_rows[i]["netR"] >= cost_rows[i+1]["netR"] for i in (0,1)):
                    raise ValueError("NONMONOTONIC_COST_NET_R")
                for m in cost_rows:
                    if m["wins"] > m["trades"] or (m["trades"] > 0 and
                        abs(m["winPct"] - 100*m["wins"]/m["trades"]) > .001):
                        raise ValueError("WIN_DENOMINATOR_ERROR")
            periods[period] = row["metrics"]
        aggregates = {}
        for variant in ("baseline","candidate"):
            count = sum(periods[p][variant]["25"]["trades"] for p in PERIODS)
            wins = sum(periods[p][variant]["25"]["wins"] for p in PERIODS)
            aggregates[variant] = {
                "trades": count,
                "wins25": wins,
                "winPct25Descriptive": round(100*wins/count,3) if count else None,
                "netR": {str(cost): round(sum(periods[p][variant][str(cost)]["netR"]
                             for p in PERIODS),6) for cost in COST_BPS},
                "periodNetR25": {p:periods[p][variant]["25"]["netR"] for p in PERIODS}
            }
        c = aggregates["candidate"]
        output["assets"][symbol] = {
            "aggregate": aggregates,
            "historicalPeriodNetR25": c["periodNetR25"],
            "provisionalRiskGates": {
                "atLeast30HistoricalTrades": c["trades"]>=30,
                "positiveR25EachHistoricalPeriod": all(v>0 for v in c["periodNetR25"].values()),
                "combinedR50Positive": c["netR"]["50"]>0,
                "independentOOSConfirmed": False,
                "executionAndFundingVerified": False,
                "crossAssetPortfolioRiskVerified": False,
            },
            "decision": "BLOCK_PRODUCTION_NOT_INDEPENDENTLY_VALIDATED"
        }
    return output

def as_markdown(result):
    rows = [
        "# ATLAS Core v0 — E0 sealed history audit",
        "",
        "**Past observations reused. Not forward testing or a predictive win rate.**",
        "",
        "| Asset | N | Win% (25bps) | R25 | R50 | Status |",
        "|---|---:|---:|---:|---:|---|"
    ]
    for coin,v in result["assets"].items():
        m = v["aggregate"]["candidate"]
        rows.append("| {} | {} | {:.2f} | {:+.3f} | {:+.3f} | BLOCKED |".format(
            coin, m["trades"], m["winPct25Descriptive"], m["netR"]["25"], m["netR"]["50"]))
    rows += [
        "", "## Known missing evidence", "",
        "- ETH historical candidate is out of scope for E0.",
        "- No independently unseen 2026-11-15+ BTC/SOL signals are measured.",
        "- Portfolio covariance, trade overlap and true aggregate PF/DD are unknown.",
        "- Realized funding, bid-ask, slippage and market impact are NOT verified.",
        "- Source identities and aggregates are checked; 159 archives were NOT re-downloaded.",
        "- 30 transactions is a tentative administrative evidence floor, not statistical significance.",
        "- Do not promote or modify any pre-existing engine or notification.",
        "", "Source SHA256: "+result["reportSHA256"], ""
    ]
    return "\n".join(rows)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--out",default="research/atlas_core_v0/output/e0_report.json")
    args=parser.parse_args()
    output=Path(args.out)
    if not str(output).startswith("research/atlas_core_v0/output/"):
        raise ValueError("OUTPUT_OUTSIDE_RESEARCH")
    result=audit()
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n")
    output.with_suffix(".md").write_text(as_markdown(result))
    print("ATLAS_CORE_E0_SEALED_HISTORY_GUARDS_PASS")
    for coin,v in result["assets"].items():
        m=v["aggregate"]["candidate"]
        print(coin,"N",m["trades"],"R25",m["netR"]["25"],"R50",m["netR"]["50"])

if __name__=="__main__":
    main()
