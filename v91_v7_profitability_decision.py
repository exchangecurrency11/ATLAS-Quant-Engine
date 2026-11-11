#!/usr/bin/env python3
"""V7 vs V9.1 trade-opportunity decision audit (PAPER, NO ORDERS).

Read immutable historical V7/V9.1 full chronological replay and real
prospective V7/V9.1 scoreboard. Compare only SAME trade identities; don't
mistake a cherry-picked subset for a fresh strategy. Separate historical
next-open fill assumptions from contemporaneously actionable publication.

Read-only inputs; produces research report, not a strategy promotion.
"""
import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path

SYMBOLS=("BTCUSDT","SOLUSDT")
VERSIONS=("V7_ORIGINAL","V91_RETEST_MAX4H")
MIN_CLOSED_FORWARD_PER_VARIANT_PER_ASSET=20
MIN_VERIFIED_HOURLY_OBSERVATIONS=168
HOUR=3600

def _number(value):
    val=float(value)
    if not math.isfinite(val): raise ValueError("NONFINITE_PAPER_R")
    return val

def key(trade):
    return tuple(trade[x] for x in ("watchUTC","retestUTC","entryUTC","side"))

def metrics(rows,field):
    vals=[_number(t[field]) for t in rows]
    return {"trades":len(vals),"wins":sum(x>0 for x in vals),
            "totalR":round(sum(vals),6),
            "avgR":round(sum(vals)/len(vals),6) if vals else None}

def compare_historical(hist):
    if hist.get("status")!="V91_FULL_CHRONOLOGICAL_RETEST_ABLATION_PAPER_ONLY":
        raise ValueError("UNVERIFIED_HISTORICAL_INPUT")
    if hist.get("NOTIndependentOutOfSampleOrProspective") is not True:
        raise ValueError("HISTORICAL_TRAINING_CONTAMINATION_FLAG_MISSING")
    trades=hist["tradesAudit"]
    result={}
    for symbol in SYMBOLS:
        versions={}
        for version in VERSIONS:
            rows=[x for x in trades if x["symbol"]==symbol and x["variant"]==version]
            identifiers=[key(x) for x in rows]
            if len(identifiers)!=len(set(identifiers)):
                raise ValueError("DUPLICATE_PAPER_ENTRY_KEY")
            reference=hist["results"][symbol][version]
            computed=metrics(rows,"netR9bps")
            if (computed["trades"]!=reference["trades"] or
                computed["wins"]!=reference["wins"] or
                abs(computed["totalR"]-float(reference["totalNetR9bpsSide"]))>0.0005):
                raise ValueError("HISTORICAL_TRADE_LEDGER_TOTAL_MISMATCH")
            stress=metrics(rows,"netR25bps")
            if abs(stress["totalR"]-float(reference["totalNetR25bpsSide"]))>0.0005:
                raise ValueError("HISTORICAL_STRESS_TOTAL_MISMATCH")
            versions[version]={key(t):t for t in rows}
        v7=versions["V7_ORIGINAL"];v91=versions["V91_RETEST_MAX4H"]
        shared=sorted(set(v7)&set(v91))
        v7only=sorted(set(v7)-set(v91))
        v91only=sorted(set(v91)-set(v7))
        # Fail closed if "shared" setup changed entries or outcomes.
        for ident in shared:
            for f in ("netR9bps","netR25bps","stop","entry"):
                if not math.isclose(_number(v7[ident][f]),_number(v91[ident][f]),
                                    rel_tol=1e-9,abs_tol=1e-6):
                    raise ValueError("MATCHED_V7_V91_TRADE_MISMATCH")
        result[symbol]={
            "V7Historical":metrics(list(v7.values()),"netR9bps"),
            "V91Historical":metrics(list(v91.values()),"netR9bps"),
            "retainedSameSetups":metrics([v91[k] for k in shared],"netR9bps"),
            "removedV7Setups":metrics([v7[k] for k in v7only],"netR9bps"),
            "newV91Setups":metrics([v91[k] for k in v91only],"netR9bps"),
            "removedV7Winners":sum(_number(v7[k]["netR9bps"])>0 for k in v7only),
            "removedV7Losers":sum(_number(v7[k]["netR9bps"])<0 for k in v7only),
            "newV91Winners":sum(_number(v91[k]["netR9bps"])>0 for k in v91only),
            "newV91Losers":sum(_number(v91[k]["netR9bps"])<0 for k in v91only),
            "historicalDeltaR":round(
                sum(_number(t["netR9bps"]) for t in v91.values())-
                sum(_number(t["netR9bps"]) for t in v7.values()),6),
            "historicalStressDeltaR":round(
                sum(_number(t["netR25bps"]) for t in v91.values())-
                sum(_number(t["netR25bps"]) for t in v7.values()),6),
            "auditRemoved":[{"retestUTC":v7[k]["retestUTC"],
                             "retestDelayHours":v7[k]["retestDelayHours"],
                             "netR9bps":v7[k]["netR9bps"]} for k in v7only],
            "auditNew":[{"retestUTC":v91[k]["retestUTC"],
                         "retestDelayHours":v91[k]["retestDelayHours"],
                         "netR9bps":v91[k]["netR9bps"]} for k in v91only],
            "historicalSelectionBiasNoOutOfSampleProof":True
        }
    return result

def _epoch(value):
    return int(datetime.fromisoformat(value.replace("Z","+00:00")).timestamp())

def publication_audit(folder):
    counts={s:{v:{"recordedEntryCandidates":0,
                  "assumedNextOpenBeforeResearchPublication":0,
                  "unprovenRealExecution":0,
                  "publicationLagMinutes":[]} for v in VERSIONS} for s in SYMBOLS}
    for path in sorted(Path(folder).glob("*.json")):
        obj=json.loads(path.read_text())
        if obj.get("mode")!="V91_PROSPECTIVE_4H_RETEST_IMMUTABLE_PAPER_SHADOW":
            raise ValueError("UNVERIFIED_PROSPECTIVE_CAPTURE")
        target=_epoch(obj["targetClosed1HUTC"])
        captured=_epoch(obj["capturedAtUTC"])
        if not target<captured<target+HOUR:
            raise ValueError("RESEARCH_PUBLICATION_OUTSIDE_CAPTURE_HOUR")
        for symbol in SYMBOLS:
            for variant,field in (("V7_ORIGINAL","originalV7"),
                                  ("V91_RETEST_MAX4H","max4hRetest")):
                pending=obj["assets"][symbol][field]["currentPaperState"].get(
                    "pendingNextOpenPaperEntry")
                if not pending:
                    continue
                if pending.get("retestKnownUTC")!=target:
                    raise ValueError("PROSPECTIVE_PENDING_ENTRY_NOT_THIS_HOUR")
                seen=counts[symbol][variant]
                seen["recordedEntryCandidates"]+=1
                # The historical simulator enters at the *immediate* next
                # candle open = retest close. Actual Git observation arrived
                # later and cannot prove that fill.
                lag=(captured-target)/60
                seen["publicationLagMinutes"].append(round(lag,2))
                seen["unprovenRealExecution"]+=1
                if captured>target:
                    seen["assumedNextOpenBeforeResearchPublication"]+=1
    return counts

def audit(historical,prospective,*,folder):
    history=compare_historical(historical)
    if (prospective.get("mode")!="V91_PROSPECTIVE_CAUSAL_PAPER_SCOREBOARD" or
        not prospective.get("noBrokerOrders") or
        not prospective.get("noNotifications") or
        not prospective.get("originalV7Untouched") or
        prospective.get("realTimeExecutableEntryCountProven")!=0):
        raise ValueError("BAD_PROSPECTIVE_PAPER_EVIDENCE")
    publication=publication_audit(folder)
    forward={}
    all_min_counts=True
    for sym in SYMBOLS:
        forward[sym]={}
        for ver in VERSIONS:
            row=prospective["results"][sym][ver]
            n=row["eligibleClosedPaperTrades"]
            if not isinstance(n,int) or n<0:raise ValueError("INVALID_FORWARD_TRADE_COUNT")
            all_min_counts=all_min_counts and n>=MIN_CLOSED_FORWARD_PER_VARIANT_PER_ASSET
            forward[sym][ver]={
                "sealedHistoricalNextOpenPaperExits":n,
                "netR9BpsPerSide":row["totalNetR9BpsPerSide"],
                "netR25BpsPerSide":row["totalNetR25BpsPerSide"],
                "notRealExecutableFills":True
            }
    enough_hours=(prospective["savedDistinctVerifiedHours"]>=MIN_VERIFIED_HOURLY_OBSERVATIONS)
    evidence_sufficient=bool(enough_hours and all_min_counts)
    return {
        "mode":"V91_V7_PROFITABILITY_DECISION_AUDIT_READ_ONLY",
        "sourceHistoricalReplayAlreadyInspectedNotIndependent":True,
        "sourceForwardProspectiveSealedOnly":True,
        "historical":history,
        "prospective":{
            "savedDistinctVerifiedHours":prospective["savedDistinctVerifiedHours"],
            "performance":forward,
            "publicationTiming":publication,
            "allAtLeast168ObservedHours":enough_hours,
            "allAtLeast20ClosedPaperTradesPerAssetPerVersion":all_min_counts,
            "minimumSampleScreenPassedNotStatisticalProof":evidence_sufficient,
            "realTimeExecutableEntryCountProven":0,
        },
        "decision":"KEEP_V91_SILENT_SHADOW_RESEARCH_NO_PROMOTION",
        "comparativeEdgeProven":False,
        "historicalStrategySelectedAfterLookingAtResults":True,
        "tradesAssumeUnexecutableInstantNextOpenFill":True,
        "newOrders":False,
        "notifications":False,
        "v7StrategyOrProductionModified":False,
        "v91StrategyModified":False,
        "neverAutoEnableSignalNotifications":True,
        "priority":"FAIR_EXECUTION_TIMING_AND_NEW_PROSPECTIVE_NET_R_NOT_MORE_INDICATORS"
    }

def markdown(result):
    lines=[
        "# V7 vs V9.1 — işlem fırsatı ve uygulanabilir kârlılık kontrolü",
        "",
        "**Karar: V9.1 sadece sessiz paper araştırmasında kalsın. Canlı emir/bildirim yok.**",
        "",
        "## Önceden incelenmiş geçmiş 2024-10 → 2026-09",
        "",
        "| Coin | V7 işlem | V7 net R | V9.1 işlem | V9.1 net R | Fark R | Ortak | Çıkarılan V7 | Eklenen V9.1 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for sym,x in result["historical"].items():
        lines.append(f'| {sym} | {x["V7Historical"]["trades"]} | {x["V7Historical"]["totalR"]} | '
                     f'{x["V91Historical"]["trades"]} | {x["V91Historical"]["totalR"]} | '
                     f'{x["historicalDeltaR"]} | {x["retainedSameSetups"]["trades"]} | '
                     f'{x["removedV7Setups"]["trades"]} '
                     f'({x["removedV7Winners"]} kazanç, {x["removedV7Losers"]} zarar) | '
                     f'{x["newV91Setups"]["trades"]} |')
    prospective=result["prospective"]
    lines+=[
        "",
        "**Bu, hipotez üretilirken incelenmiş geçmiş veridir; yeni kâr kanıtı değildir.**",
        "9bps/yan ücret+slippage varsayılmıştır. 25bps/yan stres hesabı da rapor JSON'undadır.",
        "",
        "## Gerçek zamanda kaydedilmiş sessiz paper",
        "",
        f'Gerçekten saklanmış karşılaştırılabilir saat: **{prospective["savedDistinctVerifiedHours"]}**',
        "",
        "| Coin | V7 kapanmış paper | V9.1 kapanmış paper |",
        "|---|---:|---:|",
    ]
    for sym,v in prospective["performance"].items():
        lines.append(f'| {sym} | {v["V7_ORIGINAL"]["sealedHistoricalNextOpenPaperExits"]} | '
                     f'{v["V91_RETEST_MAX4H"]["sealedHistoricalNextOpenPaperExits"]} |')
    lines+=[
        "",
        "Gerçek icra fiyatı doğrulanmış işlem: **0**.",
        "Retest kapanışı anındaki geçmiş mum açılışı, GitHub'a sinyal yazıldığında çoğu zaman geçmiştedir.",
        "Kapanış sonrası emir gerçekleştiği veya aynı fiyattan işlem yapılabildiği varsayılamaz.",
        "",
        "### Karar kapıları (asgari tanısal örnek eşiği; tek başına istatistiksel kanıt değil)",
        "",
        f'- 168 doğrulanmış saat: **{prospective["allAtLeast168ObservedHours"]}**',
        f'- Her coin × iki sistem için en az 20 kapanmış paper işlem: **{prospective["allAtLeast20ClosedPaperTradesPerAssetPerVersion"]}**',
        "- İşlem maliyeti stresini, maksimum düşüşü ve geç yayımlanmış sinyalleri ayrıca ölç.",
        "- Bu eşikler geçse bile **otomatik gerçek işleme/bildirime geçiş yok**.",
        "",
        "## Sonraki en önemli iş",
        "",
        "Aynı saatte sinyal veren iki sistem için, gerçekten sinyalin görülebildiği zamandaki yürütülebilir giriş koşullarını tasarlayıp yeni forward sonuçlarda karşılaştırmak. Geçmişteki anlık next-open fiyatlarıyla kârlılık iddiası üretmemek.",
        ""
    ]
    return "\n".join(lines)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--historical",default="forward/v91_retest_full_replay/compare.json")
    ap.add_argument("--prospective",default="forward/v91_prospective_retest/scoreboard.json")
    ap.add_argument("--hours",default="forward/v91_prospective_retest/hourly")
    ap.add_argument("--output",default="forward/v91_prospective_retest/profitability_decision.json")
    ap.add_argument("--markdown",default="forward/v91_prospective_retest/profitability_decision.md")
    args=ap.parse_args()
    source=json.loads(Path(args.historical).read_text())
    forward=json.loads(Path(args.prospective).read_text())
    report=audit(source,forward,folder=args.hours)
    for path,content in ((args.output,json.dumps(report,indent=2,ensure_ascii=False)+"\n"),
                         (args.markdown,markdown(report))):
        dest=Path(path);dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_text(content,encoding="utf-8")
    print("V91_V7_PROFITABILITY_DECISION",report["decision"],
          "verifiedHours",report["prospective"]["savedDistinctVerifiedHours"],
          "noOrders",not report["newOrders"],flush=True)

if __name__=="__main__":
    main()
