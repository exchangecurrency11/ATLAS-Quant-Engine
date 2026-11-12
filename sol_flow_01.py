#!/usr/bin/env python3
"""SOL-FLOW-01: closed-only taker-flow ablation against unchanged V9.1.

Research-only, independently replayed V9.1 BOS -> 4H-expiring retest ->
next-1H-open paper fills. Not a forward test, signal, alert, or broker order.
Uses official Binance USD-M monthly 1H kline fields; the 1H full-field
archive and 4H/daily aggregates must originate from the SAME source manifest.
Thresholds are fixed *before* new outcomes; do not optimize using this output.
"""
import argparse
from bisect import bisect_right
from datetime import datetime, timezone
import json
import math
from pathlib import Path

from backtest_retest_long_v4 import replay_pair
from signal_quality_v7 import evaluate_bos_quality
from v7_paper_comparison import read_history

HOUR = 3600
END = int(datetime(2026, 10, 1, tzinfo=timezone.utc).timestamp())
START = int(datetime(2024, 10, 1, tzinfo=timezone.utc).timestamp())
PAIR = "SOLUSDT_PERP.A"
BASE_BPS = 9
STRESS_BPS = 25
ARMS = (
    "V91_UNFILTERED_CONTROL",
    "FLOW_1H_TAKER_AGREES",
    "FLOW_4H_CVD_AGREES",
    "FLOW_1H_4H_RVOL",
    "FLOW_1H_4H_RVOL_SIZE",
)
NEEDED = ("t", "o", "h", "l", "c", "v", "qv", "trades", "tbv", "tbq")


def iso(t):
    return datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def validate_source(rows):
    """Fail closed on missing flow, inconsistent volume or hourly gaps."""
    if not rows:
        raise ValueError("FLOW_EMPTY_ARCHIVE")
    times = []
    for b in rows:
        if not all(k in b for k in NEEDED):
            raise ValueError("FLOW_REQUIRED_FIELD_MISSING")
        if type(b["t"]) is not int or b["t"] % HOUR:
            raise ValueError("FLOW_UNALIGNED_TIMESTAMP")
        if type(b["trades"]) is not int or b["trades"] < 0:
            raise ValueError("FLOW_BAD_TRADE_COUNT")
        if not all(type(b[k]) in (int, float) and math.isfinite(b[k]) for k in NEEDED[1:] if k != "trades"):
            raise ValueError("FLOW_NONFINITE")
        o, h, l, c, v = (float(b[k]) for k in ("o", "h", "l", "c", "v"))
        if not (0 < l <= min(o, c) <= max(o, c) <= h and v >= 0):
            raise ValueError("FLOW_BAD_OHLCV")
        if not (0 <= b["tbv"] <= v + max(1e-8, v*1e-7) and
                0 <= b["tbq"] <= b["qv"] + max(1e-6, b["qv"]*1e-7) and b["qv"] >= 0):
            raise ValueError("FLOW_BAD_TAKER_VOLUME")
        if v > 0 and not l*.9999 <= b["qv"]/v <= h*1.0001:
            raise ValueError("FLOW_QUOTE_BASE_MISMATCH")
        if b["tbv"] > 0 and not l*.9999 <= b["tbq"]/b["tbv"] <= h*1.0001:
            raise ValueError("FLOW_TAKER_QUOTE_MISMATCH")
        times.append(b["t"])
    if any(t != times[0] + i*HOUR for i, t in enumerate(times)):
        raise ValueError("FLOW_HOURLY_GAP_DUPLICATE_OR_DISORDER")
    return True


def validate_aggregate(hour, aggregate, width):
    """Prove the replay's 4H and Daily OHLCV match the same exact 1H source."""
    if len(hour) % width or len(aggregate) != len(hour)//width:
        raise ValueError("FLOW_MISMATCH_AGGREGATE_LENGTH")
    for i, bar in enumerate(aggregate):
        part = hour[i*width:(i+1)*width]
        expected = {"t":part[0]["t"], "o":part[0]["o"],
                    "h":max(x["h"] for x in part), "l":min(x["l"] for x in part),
                    "c":part[-1]["c"], "v":sum(x["v"] for x in part)}
        if expected["t"] % (width*HOUR):
            raise ValueError("FLOW_MISALIGNED_AGGREGATE")
        for key,value in expected.items():
            if not math.isclose(float(value),float(bar[key]),rel_tol=1e-9,abs_tol=1e-6):
                raise ValueError("FLOW_MISMATCH_AGGREGATE_"+key)
    return True


class FlowIndex:
    def __init__(self, rows):
        validate_source(rows)
        self.rows = rows
        self.times = [r["t"] for r in rows]

    def at(self, closed_at):
        """Only use 21 completed hours ending exactly at closed_at."""
        if type(closed_at) is not int or closed_at % HOUR:
            raise ValueError("FLOW_NOT_A_CLOSED_HOUR")
        end = bisect_right(self.times, closed_at-HOUR)
        if end < 21 or self.rows[end-1]["t"] + HOUR != closed_at:
            raise ValueError("FLOW_STALE_OR_INSUFFICIENT_HISTORY")
        seq = self.rows[end-21:end]
        if any(b["t"] + HOUR > closed_at for b in seq):
            raise AssertionError("FLOW_FUTURE_CANDLE_LEAK")
        prior = seq[:-1]
        last = seq[-1]
        recent4 = seq[-4:]
        v4 = sum(b["v"] for b in recent4)
        prior_v = sum(b["v"] for b in prior)
        prior_trades = sum(b["trades"] for b in prior)
        if min(v4, prior_v, last["v"], prior_trades, last["trades"]) <= 0:
            raise ValueError("FLOW_ZERO_DENOMINATOR")
        delta4 = sum(2*b["tbv"] - b["v"] for b in recent4)
        last_avg_size = last["v"] / last["trades"]
        prior_avg_size = prior_v / prior_trades
        return {
            "knownAtUTC": iso(closed_at),
            "last1HBuyShare": last["tbv"] / last["v"],
            "last4HCvdProxyPct": 100*delta4/v4,
            "relativeVolume20": last["v"] / (prior_v/20),
            "relativeAvgTradeSize20": last_avg_size/prior_avg_size,
            "last1HRawOHLCV": {k: last[k] for k in ("t", "o", "h", "l", "c", "v")},
            "featureLastKnownAt": closed_at,
        }


def decision(features, side, arm):
    if side not in ("bullish", "bearish") or arm not in ARMS:
        raise ValueError("FLOW_UNREGISTERED_SIDE_OR_ARM")
    if arm == ARMS[0]:
        return True, []
    sign = 1 if side == "bullish" else -1
    one = sign*(features["last1HBuyShare"]-.5) > 0
    four = sign*features["last4HCvdProxyPct"] > 0
    rvol = features["relativeVolume20"] >= 1.0
    size = features["relativeAvgTradeSize20"] >= 1.0
    rules = {
        ARMS[1]: (("TAKER_1H_OPPOSITE", one),),
        ARMS[2]: (("CVD_4H_OPPOSITE", four),),
        ARMS[3]: (("TAKER_1H_OPPOSITE", one), ("CVD_4H_OPPOSITE", four),
                  ("RELATIVE_VOLUME_BELOW_ONE", rvol)),
        ARMS[4]: (("TAKER_1H_OPPOSITE", one), ("CVD_4H_OPPOSITE", four),
                  ("RELATIVE_VOLUME_BELOW_ONE", rvol),
                  ("MEAN_TRADE_SIZE_BELOW_ONE", size)),
    }
    reasons = [name for name, passed in rules[arm] if not passed]
    return not reasons, reasons


def gate_factory(index, arm, counts):
    def gate(closed_bars, active, retest_bar):
        at = int(retest_bar["t"]) + HOUR
        if not closed_bars or closed_bars[-1]["t"] != retest_bar["t"]:
            raise ValueError("FLOW_RETEST_NOT_LATEST_CLOSED_BAR")
        f = index.at(at)
        raw = f["last1HRawOHLCV"]
        for k in ("t", "o", "h", "l", "c", "v"):
            if not math.isclose(float(raw[k]), float(retest_bar[k]), rel_tol=1e-9, abs_tol=1e-6):
                raise ValueError("FLOW_MISMATCH_V91_RETEST_SOURCE_"+k)
        allowed, reasons = decision(f, active["side"], arm)
        counts["eligibleOriginalRetestsAssessed"] += 1
        if not allowed:
            counts["vetoedRetests"] += 1
            for reason in reasons:
                counts["reasonCounts"][reason] = counts["reasonCounts"].get(reason, 0)+1
        return {"passed": allowed, "reasons": reasons}
    return gate


def score(replay):
    if replay["status"] != "PAPER_BACKTEST_NOT_LIVE":
        raise ValueError("FLOW_INVALID_REPLAY")
    trades = sorted((t for t in replay["trades"] if START <= t["entryOpenUTC"] < END
                     and t["exitKnownUTC"] <= END),
                    key=lambda x: (x["exitKnownUTC"], x["entryOpenUTC"]))
    vals, stress = [], []
    for t in trades:
        if not (t["watchKnownUTC"] < t["retestKnownUTC"] <= t["entryOpenUTC"] < t["exitKnownUTC"]):
            raise ValueError("FLOW_TRADE_TIME_LEAK")
        risk = float(t["risk"])
        if risk <= 0:
            raise ValueError("FLOW_INVALID_RISK")
        r = float(t["netRIllustrative"])
        vals.append(r)
        stress.append(r-2*(STRESS_BPS-BASE_BPS)/10000*float(t["entry"])/risk)
    cumulative = peak = max_dd = 0.0
    for r in vals:
        cumulative += r
        peak = max(peak, cumulative)
        max_dd = max(max_dd, peak-cumulative)
    gains = sum(r for r in vals if r > 0)
    losses = -sum(r for r in vals if r < 0)
    return {
        "trades":len(vals), "winsNet":sum(r > 0 for r in vals),
        "winRatePct":round(100*sum(r > 0 for r in vals)/len(vals),2) if vals else None,
        "netR9BpsPerSide":round(sum(vals),6),
        "netR25BpsPerSide":round(sum(stress),6),
        "meanNetR":round(sum(vals)/len(vals),6) if vals else None,
        "profitFactorR":round(gains/losses,5) if losses else None,
        "maxSequentialDrawdownR":round(max_dd,6),
        "BOSWatches":replay["alertsCount"],
        "rejectedBOS":replay["qualityGateRejectedBOS"],
        "retestVetoes":replay["qualityGateRejectedRetest"],
        "expiredRetests":replay["retestExpiredCount"],
        "unresolvedPositionExcluded":replay["unresolvedPositionExcluded"],
        "pendingEntryExcluded":replay["pendingEntryExcluded"],
    }


def run(histories, source_manifest, reference=None):
    proof = source_manifest.get("inputFiles", [])
    source_months = {(x.get("symbol"),x.get("month")) for x in proof}
    expected_months = {(sym,f"{year}-{month:02d}")
                       for sym in ("SOLUSDT","BTCUSDT")
                       for year, first, last in ((2024,10,12),(2025,1,12),(2026,1,9))
                       for month in range(first,last+1)}
    if not ("Binance official" in source_manifest.get("source", "")
            and source_manifest.get("checksumsVerified") == len(proof) == 48
            and source_months == expected_months
            and all(len(p.get("sha256", "")) == 64 and
                    all(c in "0123456789abcdef" for c in p["sha256"])
                    for p in proof)
            and source_manifest.get("firstUTC", "").startswith("2024-10-01")
            and source_manifest.get("endExclusiveUTC", "").startswith("2026-10-01")
            and source_manifest.get("pairCounts", {}).get("SOLUSDT", {}).get("1hour") == (END-START)//HOUR):
        raise ValueError("FLOW_MANIFEST_NOT_FROZEN_SHA_VERIFIED_SOURCE")
    hour = histories["1hour"][PAIR]
    four = histories["4hour"][PAIR]
    day = histories["daily"][PAIR]
    if not hour or hour[0]["t"] != START or hour[-1]["t"] + HOUR != END:
        raise ValueError("FLOW_FROZEN_HISTORY_BOUNDARY_MISMATCH")
    index = FlowIndex(hour)
    validate_aggregate(hour, four, 4)
    validate_aggregate(hour, day, 24)
    result = {"status":"SOL_FLOW_01_EXPLORATORY_HISTORICAL_PAPER_ONLY",
        "source":"Binance official USD-M 1H kline (full taker columns)",
        "symbol":"SOLUSDT", "startUTC":iso(START), "endExclusiveUTC":iso(END),
        "archiveChecksumEntriesReported":source_manifest["checksumsVerified"],
        "sameHistoryEveryArm":True, "retestExpiryHours":4,
        "4HAndDailyVerifiedAgainst1H":True,
        "externalV91ReferenceParityVerified":False,
        "next1HOpenHypotheticalFill":True,"sameCandleStopFirst":True,
        "thresholdsPredeclared":{"takerBuyShare":0.5,"4hCvdSignedPct":0,
                                  "relativeVolume20Min":1.0,"relativeAvgTradeSize20Min":1.0},
        "allHistoricalPeriodsPreviouslyExamined":True,
        "notIndependentForwardEvidence":True,"brokerOrders":False,
        "alerts":False,"productionModified":False,"promotionApproved":False,
        "limitations":["No funding, real spread, real fills or liquidation effects",
                       "Repeated past comparisons; do not treat best arm as new validated edge",
                       "No trading fees tier verification or ex-ante slippage verification"],
        "results":{}}
    for arm in ARMS:
        counts = {"eligibleOriginalRetestsAssessed":0,"vetoedRetests":0,"reasonCounts":{}}
        filter_fn = None if arm == ARMS[0] else gate_factory(index, arm, counts)
        replay = replay_pair(hour, four, day, as_of=END,
                             retest_hours=4, bos_quality_filter=evaluate_bos_quality,
                             retest_quality_filter=filter_fn)
        result["results"][arm] = {"summary":score(replay), "gateEvidence":counts}
    if reference is not None:
        # Accept either the complete V9.1 replay report or the published
        # V9.2 historical report that embeds the unchanged V9.1 baseline.
        if reference.get("status") == "V91_FULL_CHRONOLOGICAL_RETEST_ABLATION_PAPER_ONLY":
            if reference.get("originalV7BaselineVerifiedAgainstPublishedQualityBacktest") is not True:
                raise ValueError("FLOW_INVALID_V91_REFERENCE")
            expected = reference["results"]["SOLUSDT"]["V91_RETEST_MAX4H"]
            expected_net = expected["totalNetR9bpsSide"]
            expected_stress = expected["totalNetR25BpsSide"]
        elif reference.get("status") == "SELECTIVE_SOL_STAR_HARAMI_AND_OTHER_HIGH_PROFILE_CANDLE_WATCHES_HISTORICAL_ONLY":
            if (reference.get("noV7V91ProductionChanges") is not True or
                    reference.get("sameVerifiedBinanceBTCAndSOLSource") is not True or
                    reference.get("fromUTC") != iso(START) or
                    reference.get("toUTCExclusive") != iso(END)):
                raise ValueError("FLOW_INVALID_V92_EMBEDDED_V91_REFERENCE")
            expected = reference["symbols"]["SOLUSDT"]["variants"]["V91_RETEST_MAX4H"]
            expected_net = expected["totalNetR9BpsPerSide"]
            expected_stress = expected["totalNetR25BpsPerSideStress"]
        else:
            raise ValueError("FLOW_INVALID_V91_REFERENCE")
        actual = result["results"][ARMS[0]]["summary"]
        if (actual["trades"] != expected["trades"] or
                actual["winsNet"] != expected["wins"] or
                abs(actual["netR9BpsPerSide"]-expected_net) > .00011 or
                abs(actual["netR25BpsPerSide"]-expected_stress) > .00011):
            raise ValueError("FLOW_V91_BASELINE_REPLAY_PARITY_FAILED")
        result["externalV91ReferenceParityVerified"] = True
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--hour", required=True)
    p.add_argument("--four", required=True)
    p.add_argument("--daily", required=True)
    p.add_argument("--manifest", required=True)
    p.add_argument("--v91-reference", default=None,
                   help="Published V9.2 historical report or original V9.1 replay for baseline parity")
    p.add_argument("--output", default="forward/sol_flow_01/latest.json")
    a = p.parse_args()
    histories = {tf:read_history(file) for tf,file in
                 (("1hour",a.hour),("4hour",a.four),("daily",a.daily))}
    manifest = json.loads(Path(a.manifest).read_text(encoding="utf-8"))
    reference = (json.loads(Path(a.v91_reference).read_text(encoding="utf-8"))
                 if a.v91_reference else None)
    result = run(histories, manifest, reference)
    dest = Path(a.output)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(result, indent=2, ensure_ascii=False)+"\n",encoding="utf-8")
    for name,row in result["results"].items():
        print(name, row["summary"]["trades"],
              row["summary"]["netR9BpsPerSide"],
              row["summary"]["netR25BpsPerSide"], flush=True)


if __name__ == "__main__":
    main()
