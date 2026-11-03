#!/usr/bin/env python3
"""Hourly, point-in-time V7 forward observation — paper only, no orders.

Run from GitHub Actions on the isolated experimental branch. Inputs are freshly
downloaded closed 1H/4H/Daily Coinalyze futures OHLCV plus same-hour main
market_data.json. Refuse stale or mismatched inputs. Never backfill missed
observations, and never label historical paper fills as real executions.
"""
import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

from backtest_retest_long_v4 import replay_pair, indicators
from market_structure import analyze, average_true_range
from signal_quality_v7 import evaluate_bos_quality, evaluate_retest_quality

HOUR = 3600
TF_SECONDS = {"1hour": HOUR, "4hour": 4*HOUR, "daily": 24*HOUR}
PAIRS = ("BTCUSDT_PERP.A", "SOLUSDT_PERP.A")


def epoch(text):
    if not isinstance(text, str):
        raise ValueError("Timestamp must be UTC ISO string")
    stamp = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if stamp.tzinfo is None or stamp.utcoffset().total_seconds() != 0:
        raise ValueError("Expected offset-aware UTC timestamp")
    return int(stamp.timestamp())


def iso(t):
    return datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_and_hash(path):
    data = Path(path).read_bytes()
    return json.loads(data), hashlib.sha256(data).hexdigest()


def validate_inputs(main, histories, target, now):
    """Fail closed on time, completeness or provider-close mismatches."""
    if not 0 <= now - target < HOUR:
        raise ValueError("Requested target is not last completed 1H")
    if now - target < 10*60:
        raise ValueError("Run too close to hourly close for source publication")
    if main.get("ok") is not True or main.get("provider") != "Coinalyze" or main.get("market") != "Perpetual Futures":
        raise ValueError("Not the expected Coinalyze perpetual market snapshot")
    if epoch(main.get("checkedAtUTC")) < target:
        raise ValueError("Main source was checked before last 1H candle closed")
    # Provider source may refresh every ~hour; refuse time travel and stale checks.
    if epoch(main["checkedAtUTC"]) > now + 90:
        raise ValueError("Main source timestamp is in the future")
    groups = {}
    for row in main.get("results", []):
        key = (row.get("symbol"), row.get("interval"))
        if key in groups:
            raise ValueError("Duplicate market-data group")
        groups[key] = row
    if set(groups) != {(p, tf) for p in PAIRS for tf in TF_SECONDS}:
        raise ValueError("Missing or unexpected main market-data groups")
    parsed = {}
    for interval, seconds in TF_SECONDS.items():
        data = histories[interval]
        if not isinstance(data, list) or len(data) != 2:
            raise ValueError("Bad history provider array for " + interval)
        parsed[interval] = {}
        for item in data:
            symbol = item.get("symbol")
            if symbol not in PAIRS or symbol in parsed[interval]:
                raise ValueError("Missing/duplicate symbol in history " + interval)
            bars = item.get("history")
            if not isinstance(bars, list) or len(bars) < 250:
                raise ValueError("Insufficient closed history " + interval + " " + symbol)
            # Continuous 250 bars; worker endpoint already checks closedness,
            # but independently verify every input on the GitHub runner.
            tail = bars[-250:]
            for i, b in enumerate(tail):
                t = int(b["t"])
                if t % seconds != 0:
                    raise ValueError("Misaligned bar timestamp")
                if i and t - int(tail[i-1]["t"]) != seconds:
                    raise ValueError("History has missing or duplicate bars")
                o, h, lo, c, v = (float(b[x]) for x in ("o", "h", "l", "c", "v"))
                if (not all(map(math.isfinite, (o,h,lo,c,v))) or
                        lo <= 0 or v < 0 or lo > min(o,c) or h < max(o,c)):
                    raise ValueError("Invalid OHLCV in history")
            required_close = target // seconds * seconds
            observed_close = int(bars[-1]["t"]) + seconds
            if observed_close != required_close:
                raise ValueError("History stale or ahead: " + symbol + " " + interval +
                                 " got " + iso(observed_close) + " need " + iso(required_close))
            ref = groups[(symbol, interval)]
            if ref.get("status") != "READY" or epoch(ref.get("closeTimeUTC")) != required_close:
                raise ValueError("Main market snapshot stale: " + symbol + " " + interval)
            saved_close = float(ref["candle"]["close"])
            history_close = float(bars[-1]["c"])
            if abs(saved_close - history_close) > max(0.000001, abs(history_close)*0.000002):
                raise ValueError("Two closed-candle sources disagree on close: " + symbol + " " + interval)
            parsed[interval][symbol] = bars
        if set(parsed[interval]) != set(PAIRS):
            raise ValueError("Missing history pair")
    return parsed


def latest_events(report, target):
    if report.get("status") != "PAPER_BACKTEST_NOT_LIVE":
        raise ValueError("Historical replay not READY")
    events = report.get("alerts", [])
    exits = report.get("trades", [])
    return {
        "newWatchAtThisClose": [e for e in events if e["knownUTC"] == target],
        "paperTradeExitsObservedAtThisClose": [
            t for t in exits if t["exitKnownUTC"] == target],
        "currentPaperState": report.get("forwardStateAtLastClose", {}),
        "diagnosticTotalRollingWindowAlerts": len(events),
        "diagnosticTotalRollingWindowClosedTrades": len(exits),
    }


def observe(main, data, *, target, now):
    parsed = validate_inputs(main, data, target, now)
    results = {}
    for pair in PAIRS:
        h, four, daily = (parsed[tf][pair] for tf in TF_SECONDS)
        variants = (
            ("V4_baseline", {}),
            ("V7_signal_filter", {"bos_quality_filter": evaluate_bos_quality}),
            ("V7_signal_plus_retest", {
                "bos_quality_filter": evaluate_bos_quality,
                "retest_quality_filter": evaluate_retest_quality,
            }),
        )
        results[pair] = {}
        for name, opts in variants:
            result = replay_pair(h, four, daily, as_of=target, **opts)
            results[pair][name] = latest_events(result, target)
    return results


def _vote_bias(row):
    """Explicit 4-vote directional context; NOT a winning probability."""
    ind = row["indicators"]
    c = row["candle"]["close"]
    def vote(x, y):
        return 1 if x > y else -1 if x < y else 0
    score = (vote(c, ind["EMA20"]) + vote(c, ind["EMA50"]) +
             vote(ind["MACDHistogram"], 0) + vote(ind["RSI14"], 50))
    return {
        "score": score,
        "label": "bullish" if score >= 3 else "bearish" if score <= -3 else "mixed",
        "votesFrom": "close vs EMA20/EMA50, MACD histogram sign, RSI50",
        "notProbability": True,
    }


def build_market_context(main, histories, target):
    """Provide explainable context for EVERY checked hour, including zero signals.

    Source closes/indicators are checked against 1H/4H/D history in validate_inputs.
    Do not convert a structural observation into an actionable trade signal.
    """
    groups = {(x["symbol"], x["interval"]): x for x in main["results"]}
    result = {}
    for symbol in PAIRS:
        h = next(x["history"] for x in histories["1hour"] if x["symbol"] == symbol)
        # Last 250 closed bars are the same lookback used by V4 BOS detection.
        window = h[-250:]
        structure = analyze(window, "1hour", as_of=target)
        events = [
            {**e, "knownAtUTC": iso(target)}
            for e in structure.get("structure", [])
            if int(e["at"]) + HOUR == target
        ]
        bos = [e for e in events if e["event"] == "BOS"]
        rows = {tf: groups[(symbol, tf)] for tf in TF_SECONDS}
        h1, h4, d1 = (rows[tf] for tf in ("1hour", "4hour", "daily"))
        bias = {tf: _vote_bias(rows[tf]) for tf in TF_SECONDS}
        direction_aligned = (
            bias["4hour"]["label"] == bias["daily"]["label"] and
            bias["4hour"]["label"] in ("bullish", "bearish"))
        atr = average_true_range(window, len(window)-1, 14)
        prev20 = [float(b["v"]) for b in window[-21:-1]]
        rvol = float(window[-1]["v"]) / (sum(prev20)/len(prev20)) if sum(prev20)>0 else None
        quality = []
        if bos:
            ind = indicators(h)
            for e in bos:
                quality.append({
                    "direction": e["direction"],
                    "level": e["brokenLevel"],
                    "gate": evaluate_bos_quality(window, e, ind),
                    "higherTFalignedWithBOS":
                        direction_aligned and bias["daily"]["label"] == e["direction"],
                    "momentumAlignedWithBOS":
                        ((h1["indicators"]["RSI14"]>50 and
                          h1["indicators"]["MACDHistogram"]>0)
                         if e["direction"] == "bullish" else
                         (h1["indicators"]["RSI14"]<50 and
                          h1["indicators"]["MACDHistogram"]<0)),
                    "previousHourVolumeIncrease20Pct":
                        h1["candle"]["volumeChangePct"] is not None and
                        h1["candle"]["volumeChangePct"] >= 20,
                })
        if not bos:
            explanation = (
                "NO_NEW_1H_BOS: BOS/retest entry engine did not receive a fresh BOS "
                "at this close. This is a valid no-trigger observation, not a missed analysis.")
        elif not direction_aligned:
            explanation = "HIGHER_TIMEFRAMES_NOT_ALIGNED: 4H and Daily directional votes differ or are mixed."
        elif not all(e["gate"]["passed"] for e in quality):
            explanation = "BOS_QUALITY_FILTER_REJECTED: see specific quality gate reasons."
        else:
            explanation = "BOS_PRESENT: follow V4/V7 newWatch and retest state; no same-candle entry."
        result[symbol] = {
            "checkedClosed1HUTC": iso(target),
            "timeframes": {
                tf: {
                    "closeTimeUTC": rows[tf]["closeTimeUTC"],
                    "candle": rows[tf]["candle"],
                    "indicators": rows[tf]["indicators"],
                    "directionVotes": bias[tf],
                } for tf in TF_SECONDS
            },
            "atr14_1H": round(atr, 8) if atr is not None else None,
            "relativeVolume20_1H": round(rvol, 5) if rvol is not None else None,
            "higherTimeframesAgree": direction_aligned,
            "newStructureEventsAtClose": events,
            "newBOSCount": len(bos),
            "bosQualityBreakdown": quality,
            "noSignalExplanation": explanation,
            "caution": (
                "Trend votes and quality filters are descriptive; no live fill or entry "
                "confirmation follows from them. BOS analysis uses only closed hourly candles."
            ),
        }
    return result


def render_report(snapshot):
    """Human-readable audit, even when there are zero signals or stale inputs."""
    lines = [
        "# BTC/SOL V7 Saatlik Paper-Forward Teknik Durum",
        "",
        "**Hedef kapanış (UTC):** " + snapshot["targetClosed1HUTC"],
        "**Gözlem (UTC):** " + snapshot["observedAtUTC"],
        "**Veri durumu:** " + snapshot["status"],
        "",
        "Bu rapor yatırım işlemi değildir. Canlı emir, gerçekleşmiş fill veya "
        "doğrulanmış getiri iddiası içermez.",
        "",
    ]
    if snapshot["status"] != "VERIFIED_PAPER_OBSERVATION":
        lines += ["**Sinyal üretilmedi.** Kaynak reddedildi: " +
                  str(snapshot.get("rejectionReason", snapshot["status"])), ""]
        return "\n".join(lines) + "\n"
    lines += [
        "**Piyasa verisi kontrolü (UTC):** " + str(snapshot["marketDataCheckedAtUTC"]),
        "**Kaynak:** Coinalyze / Binance USDT perpetual, KAPANMIŞ mumlar.",
        "",
    ]
    for pair in PAIRS:
        context = snapshot["marketContext"][pair]
        lines += ["## " + ("BTC" if pair.startswith("BTC") else "SOL") +
                  " — " + pair, ""]
        lines += [
            "| Süre | Kapanış (UTC) | Fiyat | RSI14 | MACD hist | EMA20 / EMA50 / EMA200 | Hacim değişimi | Yön oyu |",
            "|---|---|---:|---:|---:|---|---:|---|",
        ]
        for tf in ("1hour", "4hour", "daily"):
            row = context["timeframes"][tf]
            c,ind = row["candle"],row["indicators"]
            pct = c.get("volumeChangePct")
            pct_text = "N/A" if pct is None else f"{pct:+.2f}%"
            lines.append(
                "| " + tf + " | " + row["closeTimeUTC"] +
                f" | {c['close']:.4f} | {ind['RSI14']:.2f} | "
                f"{ind['MACDHistogram']:+.4f} | "
                f"{ind['EMA20']:.4f} / {ind['EMA50']:.4f} / {ind['EMA200']:.4f} | "
                + pct_text + " | " +
                row["directionVotes"]["label"] +
                " (" + str(row["directionVotes"]["score"]) + ") |"
            )
        lines += [
            "",
            f"**1H ATR14:** {context['atr14_1H']}; "
            f"**1H göreli hacim (önceki 20 mum):** {context['relativeVolume20_1H']}.",
            "**4H / Daily aynı yönde mi?** " +
            ("Evet" if context["higherTimeframesAgree"] else "Hayır"),
            "**Bu kapanışta yeni 1H BOS:** " + str(context["newBOSCount"]),
            "**Sinyal açıklaması:** " + context["noSignalExplanation"],
            "",
        ]
        if context["newStructureEventsAtClose"]:
            lines.append("**Yeni yapı olayları (işlem teyidi değil):**")
            for event in context["newStructureEventsAtClose"]:
                lines.append(
                    "- " + event["event"] + " " + event["direction"] +
                    " | seviye " + str(event["brokenLevel"]) +
                    " | ilk doğrulanabilir kapanış " + event["knownAtUTC"])
        if context["bosQualityBreakdown"]:
            lines.append("**BOS kalite filtresi:**")
            for event in context["bosQualityBreakdown"]:
                q = event["gate"]
                lines.append("- " + event["direction"] +
                             " | passed=" + str(q["passed"]) +
                             " | reasons=" + str(q["reasons"]) +
                             " | features=" + str(q.get("features", {})) +
                             " | 4H/Daily uyumu=" +
                             str(event["higherTFalignedWithBOS"]) +
                             " | hacim>=+20%=" +
                             str(event["previousHourVolumeIncrease20Pct"]))
        lines += [
            "",
            "| Deneysel varyant | Bu kapanışta yeni erken uyarı | Bu kapanışta paper çıkış | Açık paper pozisyon |",
            "|---|---:|---:|---|",
        ]
        for name, info in snapshot["results"][pair].items():
            state = info["currentPaperState"]
            lines.append(
                "| " + name + " | " +
                str(len(info["newWatchAtThisClose"])) + " | " +
                str(len(info["paperTradeExitsObservedAtThisClose"])) + " | " +
                ("Var" if state.get("openHypotheticalPosition") else "Yok") + " |"
            )
        lines += [
            "",
            "**Yorum:** 0 yeni uyarı, 0 analiz demek değildir. Bu saatte yeni BOS-"
            "retest olayının strateji koşullarına dönüşmediği anlamına gelir.",
            "",
        ]
    lines += [
        "## Sınırlar",
        "4H/Daily yön oyu yalnızca kural bazlı piyasa bağlamıdır, kazanç olasılığı değildir. "
        "BOS–retest stratejisi giriş açmak için retest ve sonraki mum açılışını bekler. "
        "Fonlama, gerçek fill, likidasyon, order-book ve değişken maliyetler modellenmez.",
        "",
    ]
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--main-data", required=True)
    parser.add_argument("--hour", required=True)
    parser.add_argument("--four", required=True)
    parser.add_argument("--daily", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--artifact-output", default=None)
    parser.add_argument("--report-output", default=None)
    parser.add_argument("--now-utc", default=None, help="ONLY for deterministic tests")
    args = parser.parse_args()
    now = epoch(args.now_utc) if args.now_utc else int(datetime.now(timezone.utc).timestamp())
    target = now // HOUR * HOUR
    snapshot = {
        "mode": "PAPER_FORWARD_OBSERVATION_NO_ORDERS",
        "observedAtUTC": iso(now),
        "targetClosed1HUTC": iso(target),
        "status": "DATA_REJECTED",
        "productionSystemModified": False,
        "brokerOrders": False,
        "caution": (
            "Retest is observed at close. Hypothetical next-open fills and "
            "subsequent outcomes are reconstructed from later CLOSED candles; "
            "not actual orders, funding or orderbook fills. No missed-hour backfill."
        ),
    }
    try:
        main_data, main_sha = load_and_hash(args.main_data)
        histories = {}
        source_hashes = {"main": main_sha}
        for tf, path in (("1hour", args.hour), ("4hour", args.four), ("daily", args.daily)):
            histories[tf], source_hashes[tf] = load_and_hash(path)
        snapshot["inputSHA256"] = source_hashes
        snapshot["marketDataCheckedAtUTC"] = main_data.get("checkedAtUTC")
        snapshot["results"] = observe(main_data, histories, target=target, now=now)
        snapshot["marketContext"] = build_market_context(main_data, histories, target)
        snapshot["status"] = "VERIFIED_PAPER_OBSERVATION"
        print("VALIDATED:", snapshot["targetClosed1HUTC"])
        for symbol, variants in snapshot["results"].items():
            print(symbol, " ".join(
                name + ":alerts=" + str(len(report["newWatchAtThisClose"])) +
                ",exits=" + str(len(report["paperTradeExitsObservedAtThisClose"]))
                for name,report in variants.items()))
    except (ValueError, KeyError, TypeError, ZeroDivisionError) as e:
        snapshot["rejectionReason"] = str(e)
        print("DATA_REJECTED; NO SIGNALS:", str(e))
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.report_output:
        Path(args.report_output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.report_output).write_text(render_report(snapshot), encoding="utf-8")
    if args.artifact_output:
        Path(args.artifact_output).write_text(
            json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
