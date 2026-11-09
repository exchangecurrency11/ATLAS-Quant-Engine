#!/usr/bin/env python3
"""V7 paper-only veto audit: frozen BOS observations vs later CLOSED 1H bars.

Never labels a price move alone as a missed trade. A counterfactual is CLOSED
only after the SAME V4 retest -> next-open -> stop/TP/max24h rules. Uses existing
verified hourly snapshot to freeze candidate, direction and rejection causes,
then future closed 1H history for retrospective outcome. No orders.
"""
import argparse
import hashlib
import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from backtest_retest_long_v4 import (reaction_confirmed, earliest_stop,
                                    init_position, assess_candle)
from market_structure import average_true_range

HOUR = 3600
PAIRS = ("BTCUSDT_PERP.A", "SOLUSDT_PERP.A")
START = "2026-11-03T16:00:00Z"


def stamp(ts):
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def ts_epoch(s):
    dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    if dt.tzinfo is None or dt.utcoffset().total_seconds() != 0:
        raise ValueError("UTC required")
    return int(dt.timestamp())


def load_provider(path):
    raw = Path(path).read_bytes()
    source_sha = hashlib.sha256(raw).hexdigest()
    listing = json.loads(raw)
    if not isinstance(listing, list) or len(listing) != 2:
        raise ValueError("Unexpected 1H provider response")
    data = {}
    for item in listing:
        symbol = item.get("symbol")
        if symbol not in PAIRS or symbol in data:
            raise ValueError("Unknown or duplicate symbol in provider data")
        bars = item.get("history")
        if not isinstance(bars, list) or len(bars) < 40:
            raise ValueError("Insufficient provider history")
        normalized = []
        prev = None
        for b in bars:
            t = int(b["t"])
            row = {"t": t}
            for k in ("o", "h", "l", "c", "v"):
                row[k] = float(b[k])
            if t % HOUR or (prev is not None and t - prev != HOUR):
                raise ValueError("History discontinuity/unaligned bar")
            if not all(math.isfinite(row[k]) for k in ("o", "h", "l", "c", "v")):
                raise ValueError("Nonfinite OHLCV")
            if (row["l"] <= 0 or row["v"] < 0 or row["l"] > min(row["o"],row["c"])
                    or row["h"] < max(row["o"],row["c"])):
                raise ValueError("Invalid OHLCV")
            normalized.append(row)
            prev = t
        data[symbol] = normalized
    if set(data) != set(PAIRS):
        raise ValueError("Missing pair")
    return data, source_sha


def load_frozen_candidates(snapshots_dir):
    """Only BOS that actually existed in verified forward snapshots."""
    snapshot_count = 0
    reasons_invalid = Counter()
    candidates = {}
    for file in sorted(Path(snapshots_dir).glob("*.json")):
        try:
            s = json.loads(file.read_text(encoding="utf-8"))
            if s.get("status") != "VERIFIED_PAPER_OBSERVATION":
                reasons_invalid["NOT_VERIFIED"] += 1
                continue
            close = ts_epoch(s["targetClosed1HUTC"])
            observed = ts_epoch(s["observedAtUTC"])
            checked = ts_epoch(s["marketDataCheckedAtUTC"])
            if observed < close or checked < close:
                reasons_invalid["TIMESTAMP_INVALID"] += 1
                continue
            snapshot_count += 1
            for pair in PAIRS:
                ctx = s.get("marketContext",{}).get(pair)
                if not ctx:
                    # First snapshot pre-dates explanatory marketContext; don't infer.
                    continue
                h = ctx["timeframes"]["1hour"]["candle"]
                quality = ctx.get("bosQualityBreakdown", [])
                for event in ctx.get("newStructureEventsAtClose", []):
                    if event.get("event") != "BOS":
                        continue
                    if event.get("confirmedAt", event.get("at", -HOUR) + HOUR) != close:
                        reasons_invalid["EVENT_TIMESTAMP_MISMATCH"] += 1
                        continue
                    side = event["direction"]
                    if side not in ("bullish", "bearish"):
                        reasons_invalid["EVENT_INVALID_DIRECTION"] += 1
                        continue
                    level = float(event["brokenLevel"])
                    same = [q for q in quality
                            if q.get("direction")==side and abs(q.get("level",0)-level)<1e-7]
                    if len(same) != 1:
                        reasons_invalid["MISSING_QUALITY_RECORD"] += 1
                        continue
                    q = same[0]
                    v7 = s["results"][pair]["V7_signal_filter"]["newWatchAtThisClose"]
                    v4 = s["results"][pair]["V4_baseline"]["newWatchAtThisClose"]
                    def matched(events):
                        return any(
                            x.get("knownUTC")==close and x.get("side")==side
                            and abs(float(x.get("BOSLevel",-1))-level)<1e-7
                            for x in events)
                    factors = []
                    if not q.get("higherTFalignedWithBOS"):
                        factors.append("4H_DAILY_ALIGNMENT_VETO")
                    if not q.get("momentumAlignedWithBOS"):
                        factors.append("1H_RSI_MACD_MOMENTUM_VETO")
                    if not q.get("previousHourVolumeIncrease20Pct"):
                        factors.append("PREVIOUS_HOUR_VOLUME_VETO")
                    if not q.get("gate",{}).get("passed"):
                        for cause in q.get("gate",{}).get("reasons",["UNKNOWN"]):
                            factors.append("V7_QUALITY_"+str(cause))
                    v7_accepted = matched(v7)
                    if not v7_accepted and not factors:
                        factors.append("SCANNER_OCCUPANCY_OR_OTHER_VETO")
                    key = (pair, close, side, level)
                    candidates[key] = {
                        "pair": pair, "bosClosedUTC": stamp(close),
                        "bosCloseEpoch": close, "side": side, "brokenLevel": level,
                        "acceptedByV4": matched(v4), "acceptedByV7": v7_accepted,
                        "rejectionFactors": factors,
                        "v7Quality": q.get("gate"),
                        "context": {
                            "higherTFaligned": q.get("higherTFalignedWithBOS"),
                            "momentumAligned": q.get("momentumAlignedWithBOS"),
                            "priorHourVolumeUp20Pct": q.get("previousHourVolumeIncrease20Pct"),
                        },
                        "frozenBosCandle": {k:float(h[k]) for k in ("open","high","low","close")},
                        "sourceSnapshot": file.name,
                    }
        except (KeyError, ValueError, TypeError, OSError):
            reasons_invalid["SNAPSHOT_PARSE_ERROR"] += 1
    return sorted(candidates.values(),key=lambda x:(x["bosCloseEpoch"],x["pair"],x["side"])), snapshot_count, dict(reasons_invalid)


def evaluate_counterfactual(candidate, bars, *, fee_bps=6, slippage_bps=3):
    """Single hypothetical setup, not sequential/portfolio P&L; no lookahead.

    Need contiguous closed bars covering BOS, retest (1..6h) and later exit
    (up to 24h), with ATR computed only from candles known at retest close.
    """
    close = candidate["bosCloseEpoch"]
    by_t = {b["t"]:i for i,b in enumerate(bars)}
    bos_open = close-HOUR
    if bos_open not in by_t:
        return {"status":"HISTORY_COVERAGE_MISSING_BOS"}
    base = by_t[bos_open]
    observed = bars[base]
    reference = candidate["frozenBosCandle"]
    for k,src in (("o","open"),("h","high"),("l","low"),("c","close")):
        if abs(observed[k]-reference[src]) > max(0.00001,abs(observed[k])*0.000005):
            return {"status":"SOURCE_MISMATCH", "field":k,
                    "original":reference[src],"current":observed[k]}
    if base < 20:
        return {"status":"INSUFFICIENT_ATR_LOOKBACK"}
    side,level=candidate["side"],candidate["brokenLevel"]
    retest_index = None
    for j in range(1,7):
        index=base+j
        if index>=len(bars):
            return {"status":"PENDING_RETEST_UNCLOSED"}
        bar=bars[index]
        if reaction_confirmed(side,bar,bars[index-1],level):
            retest_index=index
            break
    if retest_index is None:
        return {"status":"EXPIRED_WITHOUT_V4_RETEST",
                "note":"No eligible entry; subsequent directional price move does NOT count as missed trade"}
    reaction=bars[retest_index]
    atr=average_true_range(bars,retest_index,14)
    if atr is None or atr<=0:
        return {"status":"INVALID_ATR_AT_RETEST"}
    pending={
        "side":side, "watchKnownUTC":close,
        "retestKnownUTC":reaction["t"]+HOUR,"level":level,
        "stop":earliest_stop(side,observed,reaction,atr)
    }
    entry_index=retest_index+1
    if entry_index>=len(bars):
        return {"status":"AWAITING_CLOSED_ENTRY_BAR",
                "retestClosedUTC":stamp(reaction["t"]+HOUR)}
    pos=init_position(pending,bars[entry_index]["o"],bars[entry_index]["t"])
    if pos is None:
        return {"status":"REJECTED_BY_V4_ENTRY_RISK_RULE",
                "retestClosedUTC":stamp(reaction["t"]+HOUR)}
    for idx in range(entry_index,len(bars)):
        complete,reason=assess_candle(pos,bars[idx])
        if complete:
            cost_r=2*(fee_bps+slippage_bps)/10000*pos["entry"]/pos["risk"]
            net=pos["realizedR"]-cost_r
            return {
                "status":"CLOSED_COUNTERFACTUAL_PAPER",
                "retestClosedUTC":stamp(reaction["t"]+HOUR),
                "entryOpenUTC":stamp(pos["entryOpenUTC"]),
                "entry":round(pos["entry"],8), "stop":round(pos["stop"],8),
                "targets":[round(v,8) for v in pos["targets"]],
                "exitClosedUTC":stamp(bars[idx]["t"]+HOUR),
                "exitReason":reason, "targetCount":pos["targetCount"],
                "grossR":round(pos["realizedR"],6),
                "assumedNetR":round(net,6), "perSideCostBps":fee_bps+slippage_bps,
                "outcome":("PAPER_POSITIVE" if net>0 else "PAPER_NEGATIVE_OR_FLAT"),
                "notExecuted":True,
            }
    return {"status":"OPEN_COUNTERFACTUAL_NO_CLOSED_EXIT",
            "entryOpenUTC":stamp(pos["entryOpenUTC"]),
            "entry":round(pos["entry"],8),"stop":round(pos["stop"],8),
            "noOutcomeAssigned":True}


def evaluate(snapshots_path, hourly_path, *, as_of):
    history,hash_value=load_provider(hourly_path)
    all_candidates,count,bad=load_frozen_candidates(snapshots_path)
    results=[]
    for c in all_candidates:
        bars=[b for b in history[c["pair"]] if b["t"]+HOUR<=as_of]
        row=dict(c)
        row["counterfactual"] = evaluate_counterfactual(row,bars)
        out=row["counterfactual"]
        if c["acceptedByV7"]:
            row["classification"]="ACCEPTED_BY_V7_NOT_A_REJECTED_SIGNAL"
        elif out["status"]=="CLOSED_COUNTERFACTUAL_PAPER":
            row["classification"]=(
                "POTENTIALLY_MISSED_POSITIVE_PAPER" if out["assumedNetR"]>0
                else "AVOIDED_NEGATIVE_OR_FLAT_PAPER")
        else:
            row["classification"]="UNRESOLVED_OR_NO_ACTIONABLE_ENTRY"
        results.append(row)
    rejection=[r for r in results if not r["acceptedByV7"]]
    closed=[r for r in rejection if r["counterfactual"]["status"]=="CLOSED_COUNTERFACTUAL_PAPER"]
    positive=[r for r in closed if r["counterfactual"]["assumedNetR"]>0]
    negative=[r for r in closed if r["counterfactual"]["assumedNetR"]<=0]
    status_counts=Counter(r["counterfactual"]["status"] for r in rejection)
    factor_counts=Counter(f for r in rejection for f in r["rejectionFactors"])
    by_pair={}
    for pair in PAIRS:
        a=[r for r in rejection if r["pair"]==pair]
        b=[r for r in a if r["counterfactual"]["status"]=="CLOSED_COUNTERFACTUAL_PAPER"]
        by_pair[pair] = {
            "observedBOS":sum(r["pair"]==pair for r in results),
            "acceptedByV7":sum(r["pair"]==pair and r["acceptedByV7"] for r in results),
            "rejectedBOS":len(a),
            "rejectedWithClosedCounterfactualPaperTrade":len(b),
            "avoidedNegativeOrFlatPaper":sum(r["counterfactual"].get("assumedNetR",1)<=0 for r in b),
            "potentiallyMissedPositivePaper":sum(r["counterfactual"].get("assumedNetR",-1)>0 for r in b),
            "notActionableOrUnresolved":len(a)-len(b),
        }
    out={
        "mode":"V7_RETROSPECTIVE_REJECTED_BOS_PAPER_STUDY_NO_ORDERS",
        "asOfClosed1HUTC":stamp(as_of),
        "forwardSnapshotsVerified":count,
        "historicalRawCandlesSourceSHA256":hash_value,
        "historicalRawSourceNote":"Current Coinalyze historical 1H feed, checked against original BOS OHLC values",
        "method":("Frozen forward-observed BOS and filters at original close; later fully "
                  "closed 1H candles for 1..6h retest, next-open simulated entry, "
                  "24h maximum hold, stop-first collision, TP1/TP2/TP3 thirds, "
                  "6bps fees + 3bps slippage per side. Diagnostic independent "
                  "counterfactuals (not mutually exclusive positions)."),
        "limitations":[
            "A missed positive is a counterfactual PAPER trade, not a proven realizable winning live trade.",
            "Not selected from unobserved/missed-hour BOS; those hours remain MISSED_OBSERVATION.",
            "Never interpret a price change without retest/entry as a missed win.",
            "A gate can have MULTIPLE rejection causes; factor counts are overlapping.",
            "Incomplete future 1H data = pending, not a winner or a loser.",
            "Historical feed acquired later cannot make the observation a contemporaneous live signal.",
            "No funding, orderbook, actual fills, variable slippage, liquidation, portfolio overlap.",
            "No V7 threshold tuning on this inspected sample; tiny samples are not efficacy proof."
        ],
        "summary":{
            "forwardObservedBOS":len(results),
            "v7AcceptedBOS":sum(r["acceptedByV7"] for r in results),
            "v7RejectedBOS":len(rejection),
            "rejectedWithClosedCounterfactualPaperTrade":len(closed),
            "avoidedNegativeOrFlatPaper":len(negative),
            "potentiallyMissedPositivePaper":len(positive),
            "rejectedWithoutCompletedActionableCounterfactual":len(rejection)-len(closed),
            "rejectedCounterfactualStatuses":dict(status_counts),
            "overlappingRejectionFactors":dict(factor_counts),
            "snapshotIssues":bad,
            "byPair":by_pair,
            "sumNetROfRejectedIndependentSetupsNotPortfolio":
                round(sum(r["counterfactual"]["assumedNetR"] for r in closed),6),
        },
        "candidates":results,
    }
    return out


def fmt_report(obj):
    s=obj["summary"]
    lines=[
        "# V7 — Engellenen BOS sinyalleri karşıolgusal inceleme",
        "",
        "**Analiz kapanış sınırı:** "+obj["asOfClosed1HUTC"]+" (UTC)",
        "**Sistem:** PAPER ONLY; canlı emir ve gerçek getiri yok",
        "**Orijinal doğrulanmış V7 gözlemi:** "+str(obj["forwardSnapshotsVerified"]),
        "",
        "| Ölçüm | Sonuç |","|---|---:|",
        "| Gerçek zamanında kaydedilmiş BOS | "+str(s["forwardObservedBOS"])+" |",
        "| V7 tarafından kabul edilen BOS | "+str(s["v7AcceptedBOS"])+" |",
        "| V7 tarafından engellenen BOS | "+str(s["v7RejectedBOS"])+" |",
        "| Engellenip karşıolgusal işlem kapanan | "+str(s["rejectedWithClosedCounterfactualPaperTrade"])+" |",
        "| Bunlardan maliyet sonrası zarar/sıfır | "+str(s["avoidedNegativeOrFlatPaper"])+" |",
        "| Bunlardan maliyet sonrası kâr | "+str(s["potentiallyMissedPositivePaper"])+" |",
        "| Henüz kesin karşıolgusal işlem sonucu yok | "+str(s["rejectedWithoutCompletedActionableCounterfactual"])+" |",
        "",
        "## BTC ve SOL ayrı sonuç",
        "",
        "| Parite | BOS | V7 kabul | V7 red | Red → kapanmış işlem | Zarar/0 kaçınıldı | Olası kârlı fırsat kaçtı |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for pair,d in s["byPair"].items():
        lines.append("| "+pair+" | "+" | ".join(str(d[k]) for k in (
            "observedBOS","acceptedByV7","rejectedBOS",
            "rejectedWithClosedCounterfactualPaperTrade","avoidedNegativeOrFlatPaper",
            "potentiallyMissedPositivePaper"))+" |")
    lines+=["","## Filtre gerekçeleri (bir BOS için birden fazla gerekçe olabilir)",""]
    for k,v in sorted(s["overlappingRejectionFactors"].items(),key=lambda kv:(-kv[1],kv[0])):
        lines.append("- "+k+": "+str(v))
    lines+=["","## Aday bazında sonuçlar",""]
    for a in obj["candidates"]:
        c=a["counterfactual"]
        lines.append(
            "- **"+a["bosClosedUTC"]+" "+a["pair"]+" "+a["side"]+
            "**, seviye "+str(a["brokenLevel"])+
            "; V7 "+("KABUL" if a["acceptedByV7"] else "RED")+
            "; neden: "+(", ".join(a["rejectionFactors"]) or "kabul")+
            "; sonuç: "+c["status"]+
            (", net "+str(c["assumedNetR"])+"R" if "assumedNetR" in c else "")+
            "; sınıf: "+a["classification"])
    lines+=["","## Yorum ve sınırlamalar",""]
    lines+=["- "+w for w in obj["limitations"]]
    lines+=["","Bu sonuçlar yeni V7 parametrelerini ayarlamak için değil, kaçırılan fırsatlar ile kötü işlemlerden korunmayı karşılaştırmak içindir.",""]
    return "\n".join(lines)


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--hour",required=True)
    p.add_argument("--snapshots",default="forward/snapshots")
    p.add_argument("--json-output",required=True)
    p.add_argument("--report-output",required=True)
    p.add_argument("--as-of-utc",required=True)
    a=p.parse_args()
    cutoff=ts_epoch(a.as_of_utc)
    res=evaluate(a.snapshots,a.hour,as_of=cutoff)
    for path in (a.json_output,a.report_output):
        Path(path).parent.mkdir(parents=True,exist_ok=True)
    Path(a.json_output).write_text(
        json.dumps(res,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    Path(a.report_output).write_text(fmt_report(res),encoding="utf-8")
    print(json.dumps(res["summary"],ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
