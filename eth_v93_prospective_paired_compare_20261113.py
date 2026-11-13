#!/usr/bin/env python3
"""Frozen, no-lookahead ETH V9.2 vs BOS+EMA month-complete prospective comparison.

This reads ONLY the pre-registered, SHA256-source-verified V9.3 SHADOW packet
and never reinterprets previously studied 2022-2026 trades as prospective.
A prefreeze packet creates a truthful NO_DATA status, not a mock backtest.
Sources/results are immutable and execution is research-only; no alerts,
orders, live V7/V9.2 paper bookkeeping or default-branch writes.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import v93_shadow_monthly_20261113 as frozen

SHADOW=Path("forward/v93_shadow_prospective_20261113")
OUTPUT=Path("forward/eth_v93_paired_prospective_20261113")
ETH_REF="ETH_V92_REFERENCE"
ETH_CAND="ETH_BOS_EMA_RELAX"
FREEZE=frozen.FREEZE
MIN_DAYS=180
MIN_EACH_STREAM=20
MIN_EACH_SIDE=5

def dt(s):
    x=datetime.fromisoformat(s.replace("Z","+00:00"))
    if x.tzinfo is None or x.utcoffset().total_seconds()!=0:
        raise ValueError("UTC_TIMESTAMP_REQUIRED")
    return x

def spec_guard(spec):
    expected=frozen.frozen_spec()
    if spec!=expected:
        raise ValueError("ETH_FROZEN_RESEARCH_SPEC_OR_SOURCE_DRIFT")
    assert FREEZE=="2026-11-14T00:00:00Z"
    a=spec["candidates"]
    if (a[ETH_REF] != {"symbol":"ETHUSDT","mode":"BASELINE","disabledGates":[]}
        or a[ETH_CAND] != {
        "symbol":"ETHUSDT","mode":"PAIR_NO_BREAK_ATR_AND_EMA_EXT",
        "disabledGates":["bos_break_atr","bos_ema_extension"]}):
        raise ValueError("ETH_PROSPECTIVE_DIFFERENT_CANDIDATE")
    if spec["realOrders"] or spec["notifications"] or spec["currentV7V92AccountWrites"]:
        raise ValueError("ETH_BAD_FROZEN_SAFETY_SPEC")
    return True

def load_packet():
    spec=json.loads((SHADOW/"frozen_spec.json").read_text())
    spec_guard(spec)
    latest=SHADOW/"latest.json"
    if latest.exists():
        data=json.loads(latest.read_text())
        if data["status"]!="PROSPECTIVE_MONTHLY_SHADOW_ONLY":
            raise ValueError("ETH_LATEST_NOT_PROSPECTIVE")
        asof=dt(data["asOfExclusiveUTC"])
        if asof<=dt(FREEZE):
            raise ValueError("ETH_LATEST_NOT_AFTER_FREEZE")
        if asof>datetime.now(timezone.utc):
            raise ValueError("ETH_FUTURE_ARCHIVE_SNAPSHOT")
        month=(asof.year-1,12) if asof.month==1 else (asof.year,asof.month-1)
        label=f"{month[0]:04d}-{month[1]:02d}"
        immutable_file=SHADOW/"snapshots"/f"{label}.json"
        if (not immutable_file.exists()
            or immutable_file.read_bytes()!=latest.read_bytes()):
            raise ValueError("ETH_LATEST_NOT_EXACT_IMMUTABLE_MONTH_SNAPSHOT")
        return data,"COMPLETED_MONTHLY_PROSPECTIVE",label
    pf=json.loads((SHADOW/"preflight.json").read_text())
    if (pf["status"]!="PREFREEZE_PIPELINE_SMOKE_TEST" or
        dt(pf["asOfExclusiveUTC"])>dt(FREEZE)):
        raise ValueError("ETH_PREFLIGHT_NOT_PREFREEZE")
    return pf,"PREFREEZE_NO_ELIGIBLE_TRADES",None

def guard_packet(data,spec):
    if (data["startProspectiveUTC"]!=FREEZE
        or data["sourceHashSHA256"]!=spec["immutableEngineHashes"]
        or not data["neverRealOrders"] or not data["cannotCreditAnyPreFreezeTrade"]
        or not data["noExistingV7V92AccountWrites"]
        or data["verifiedArchives"]!=len(data["archiveSHA256"])
        or len(data["reportedStreams"])!=6):
        raise ValueError("ETH_PROSPECTIVE_SOURCE_MISMATCH")
    if any(len(v)!=64 for v in data["archiveSHA256"].values()):
        raise ValueError("ETH_ARCHIVE_SHA256_NOT_VERIFIED")
    if not all(label in data["reportedStreams"] for label in (ETH_REF,ETH_CAND)):
        raise ValueError("ETH_COMPARISON_NOT_IN_FROZEN_SIX_STREAMS")
    for k in (ETH_REF,ETH_CAND):
        row=data["reportedStreams"][k]
        expected=spec["candidates"][k]
        if (row["symbol"]!=expected["symbol"] or row["mode"]!=expected["mode"]
            or row["disabledGates"]!=expected["disabledGates"]
            or not row["noBackfilledHistoricalTrades"]
            or row["isActualExecution"] or not row["unresolvedNotCredited"]):
            raise ValueError("ETH_FROZEN_STREAM_IDENTITY_OR_COST_DRIFT")
    return True

def score(t):
    return float(t["netR25Bps"])

def key(t):
    return (t["entryOpenUTC"],t["side"])

def validate_tape(stream,asof):
    trades=stream["closedProspectiveTrades"]
    if len(trades)!=stream["metrics25Bps"]["trades"] or len(trades)!=stream["metrics9Bps"]["trades"]:
        raise ValueError("ETH_PROSPECTIVE_CLOSED_TRADE_COUNT")
    keys=set()
    previous=None
    for tr in trades:
        moments=[dt(tr[k]) for k in ("watchKnownUTC","retestKnownUTC","entryOpenUTC","exitKnownUTC")]
        if not(dt(FREEZE)<=moments[0]<moments[1]<=moments[2]<moments[3]<=asof):
            raise ValueError("ETH_PROSPECTIVE_CLOSED_TRADE_LOOKAHEAD")
        k=key(tr)
        if k in keys or (previous is not None and k<=previous):
            raise ValueError("ETH_PROSPECTIVE_DUPLICATE_OR_UNSORTED_ENTRY")
        keys.add(k)
        previous=k
        if tr["side"] not in ("bullish","bearish"):
            raise ValueError("ETH_PROSPECTIVE_BAD_SIDE")
        if not (float(tr["entry"])>0 and float(tr["stop"])>0):
            raise ValueError("ETH_PROSPECTIVE_BAD_PRICE")
        if (len(tr["targets"])!=3 or
            any(float(z)<=0 for z in tr["targets"])):
            raise ValueError("ETH_PROSPECTIVE_INVALID_TP")
    for bps in (9,25):
        metric=stream[f"metrics{bps}Bps"]
        values=[float(t[f"netR{bps}Bps"]) for t in trades]
        if (abs(sum(values)-float(metric["netR"]))>0.00002
            or metric["wins"]!=sum(v>0 for v in values)):
            raise ValueError("ETH_PROSPECTIVE_METRIC_RECONCILIATION")
    return trades

def paired(a,b):
    amap={key(x):x for x in a}
    bmap={key(x):x for x in b}
    common=sorted(set(amap)&set(bmap))
    for k in common:
        x,y=amap[k],bmap[k]
        if (x["exitKnownUTC"]!=y["exitKnownUTC"]
            or abs(x["netR25Bps"]-y["netR25Bps"])>0.000001
            or abs(x["netR9Bps"]-y["netR9Bps"])>0.000001
            or x["entry"]!=y["entry"] or x["stop"]!=y["stop"]):
            raise ValueError("ETH_SHARED_PROSPECTIVE_TRADE_DRIFT")
    added=[bmap[k] for k in sorted(set(bmap)-set(amap))]
    dropped=[amap[k] for k in sorted(set(amap)-set(bmap))]
    return {
        "common":len(common),
        "candidateOnly":len(added),
        "baselineOnly":len(dropped),
        "candidateOnlyWins25":sum(score(t)>0 for t in added),
        "baselineOnlyWins25":sum(score(t)>0 for t in dropped),
        "candidateOnlyNetR25":round(sum(score(t) for t in added),6),
        "baselineOnlyNetR25":round(sum(score(t) for t in dropped),6),
        "candidateOnlyEntriesUTC":[t["entryOpenUTC"] for t in added],
        "baselineOnlyEntriesUTC":[t["entryOpenUTC"] for t in dropped],
        "sharedIdenticalRAndExitVerified":True,
        "deltaFromIncrementalEntriesR25":round(sum(score(t) for t in added)-
                                                sum(score(t) for t in dropped),6)
    }

def verdict(reference,candidate,asof):
    days=(asof-dt(FREEZE)).total_seconds()/86400
    rs=reference["closedProspectiveTrades"]
    cs=candidate["closedProspectiveTrades"]
    ref=reference["metrics25Bps"]
    cand=candidate["metrics25Bps"]
    side=lambda trades,side:sum(t["side"]==side for t in trades)
    directions={
        label:{"long":side(trades,"bullish"),"short":side(trades,"bearish")}
        for label,trades in ((ETH_REF,rs),(ETH_CAND,cs))
    }
    checks={
        "atLeast180CalendarDays":days>=MIN_DAYS,
        "eachStreamAtLeast20ClosedTrades":min(len(rs),len(cs))>=MIN_EACH_STREAM,
        "bothDirectionsAtLeast5PerStream":all(
            z["long"]>=MIN_EACH_SIDE and z["short"]>=MIN_EACH_SIDE
            for z in directions.values()),
        "differentRegimesVerified":False, # current snapshot does not store causal regime tags
        "positiveCandidateNetR25":len(cs)>0 and cand["netR"]>0,
        "positiveMatchedR25Gain":len(cs)>0 and len(rs)>0 and cand["netR"]>ref["netR"],
        "candidateProfitFactorAboveOne":cand["profitFactor"] is not None and cand["profitFactor"]>1,
        "candidateDrawdownNotWorse":cand["maxDrawdownR"]<=ref["maxDrawdownR"],
        "independentFundingSlippageFillProof":False,
    }
    return {
        "calendarDaysObserved":round(days,3),
        "directionCounts":directions,
        "preliminaryCoverageGates":checks,
        "candidateApprovedForPromotion":False,
        "decision":"INSUFFICIENT_NEW_INDEPENDENT_EVIDENCE_NO_PRODUCTION_PROMOTION"
    }

def compare(data,context,label):
    spec=json.loads((SHADOW/"frozen_spec.json").read_text())
    guard_packet(data,spec)
    asof=dt(data["asOfExclusiveUTC"])
    ref=data["reportedStreams"][ETH_REF]
    cand=data["reportedStreams"][ETH_CAND]
    ra=validate_tape(ref,asof)
    ca=validate_tape(cand,asof)
    if context=="PREFREEZE_NO_ELIGIBLE_TRADES" and (ra or ca):
        raise ValueError("ETH_PREFREEZE_CANNOT_HAVE_PROSPECTIVE_TRADES")
    match=paired(ra,ca)
    deltaR25=round(cand["metrics25Bps"]["netR"]-ref["metrics25Bps"]["netR"],6)
    deltaR9=round(cand["metrics9Bps"]["netR"]-ref["metrics9Bps"]["netR"],6)
    if abs(deltaR25-match["deltaFromIncrementalEntriesR25"])>0.00003:
        raise ValueError("ETH_PROSPECTIVE_PAIRED_R_NOT_RECONCILED")
    if not ra and not ca:
        deltaR25=None
        deltaR9=None
    return {
        "status":"ETH_BOS_EMA_PAIRED_PROSPECTIVE_OBSERVATION" if context=="COMPLETED_MONTHLY_PROSPECTIVE"
                 else "ETH_NO_NEW_DATA_BEFORE_FROZEN_START",
        "sourcePacketSHA256":hashlib.sha256(
            json.dumps(data,ensure_ascii=False,indent=2,sort_keys=True).encode()+b"\n").hexdigest(),
        "freezeUTC":FREEZE,"asOfExclusiveUTC":data["asOfExclusiveUTC"],
        "sourceMonth":label,"provenance":context,
        "verifiedOfficialMonthlyArchives":data["verifiedArchives"],
        "comparison":{"reference":{
            "label":ETH_REF,"metrics9Bps":ref["metrics9Bps"],
            "metrics25Bps":ref["metrics25Bps"],
            "unresolved":ref["openOrPendingAtLastClose"]},
            "candidate":{
            "label":ETH_CAND,"metrics9Bps":cand["metrics9Bps"],
            "metrics25Bps":cand["metrics25Bps"],
            "unresolved":cand["openOrPendingAtLastClose"]},
            "paired":match,"deltaR25Bps":deltaR25,"deltaR9Bps":deltaR9},
        "review":verdict(ref,cand,asof),
        "researchOnly":True,"realOrders":False,"notifications":False,
        "originalV7V92AccountsTouched":False,
        "historyCreditedToProspective":False,
        "monthlyCompletedArchiveOnly":True,
        "doesNotAutomaticallyRun":True,
        "noRealtimeTradingSignal":True
    }

def markdown(x):
    a=x["comparison"]["reference"]
    b=x["comparison"]["candidate"]
    paired=x["comparison"]["paired"]
    status=x["status"]
    evidence= x["provenance"]=="COMPLETED_MONTHLY_PROSPECTIVE"
    lines=[
        "# ETH: Dondurulmuş V9.2 vs BOS+EMA — yeni veri kıyası",
        "",
        "**"+("Tamamlanmış aylık Binance arşivine dayalı ileri sanal karşılaştırma." if evidence
              else "Henüz dondurma sonrası tamamlanmış resmi aylık veri yok. Bu sonuç performans iddiası değildir.")+"**",
        "",
        f"Ön kayıt: **{x['freezeUTC']}**; en son incelenen veri bitişi: **{x['asOfExclusiveUTC']}**.",
        "Her iki motor aynı dondurulmuş BOS → retest → sonraki 1H giriş, 1R/2R/3R çıkışlarını ve 9/25 bps/yön maliyet varsayımını kullanır.",
        "Yalnızca watch, retest, giriş ve kapanış saatleri dondurmadan sonra olan işlemler sayılır.",
        "",
        "| Metrik | ETH V9.2 referans | ETH BOS+EMA gevşetme |",
        "|---|---:|---:|",
        f"| Tamamlanan yeni işlem | {a['metrics25Bps']['trades']} | {b['metrics25Bps']['trades']} |",
        f"| Kazanan | {a['metrics25Bps']['wins']} | {b['metrics25Bps']['wins']} |",
        f"| Win % (25bps) | {a['metrics25Bps']['winPct'] if a['metrics25Bps']['winPct'] is not None else 'Yetersiz veri'} | {b['metrics25Bps']['winPct'] if b['metrics25Bps']['winPct'] is not None else 'Yetersiz veri'} |",
        f"| Net R 9bps | {a['metrics9Bps']['netR']:+.3f} | {b['metrics9Bps']['netR']:+.3f} |",
        f"| Net R 25bps | {a['metrics25Bps']['netR']:+.3f} | {b['metrics25Bps']['netR']:+.3f} |",
        f"| PF 25bps | {a['metrics25Bps']['profitFactor']} | {b['metrics25Bps']['profitFactor']} |",
        f"| Max DD R25 | {a['metrics25Bps']['maxDrawdownR']:.3f} | {b['metrics25Bps']['maxDrawdownR']:.3f} |",
        "",
        f"**Eşleştirilen işlemler:** {paired['common']} ortak, {paired['candidateOnly']} yalnız aday, {paired['baselineOnly']} yalnız referans.",
        f"**Net R25 farkı:** {x['comparison']['deltaR25Bps']:+.3f} R" if x["comparison"]["deltaR25Bps"] is not None
             else "**Net R25 farkı:** Hesaplanamaz (yeni işlem yok; sıfır gerçek üstünlük sayılmaz).",
        "",
        "**Karar:** İleri veri, farklı piyasa rejimleri ve yeterli işlem örneği olmadan canlıya aktarım yok.",
        "İlk inceleme protokolü: en az 180 gün, karşılaştırmada her iki kolda en az 20 yeni kapanmış işlem, her yönde en az 5 ve iki rejim; bu sayılar yeterli istatistiksel kanıt garantisi değildir.",
        "Yüksek win-rate ancak negatif net R başarısız sayılır. Gerçek funding, spread değişkenliği, fill kalitesi ve likidasyon doğrulanmamıştır.",
        "",
        "GitHub varsayılan dal, mevcut V7/V9.2 sanal defterleri, otomasyonlar ve bildirimler değiştirilmemiştir.",
        ""
    ]
    return "\n".join(lines)

def write_immutable(path,text):
    if path.exists() and path.read_text()!=text:
        raise ValueError("ETH_PAIRED_SNAPSHOT_IMMUTABILITY_FAILURE")
    path.parent.mkdir(parents=True,exist_ok=True)
    if not path.exists():
        path.write_text(text)

def run(out):
    packet,context,label=load_packet()
    data=compare(packet,context,label)
    serialized=json.dumps(data,ensure_ascii=False,sort_keys=True,indent=2)+"\n"
    written=markdown(data)
    out.mkdir(parents=True,exist_ok=True)
    if label:
        immutable_path=out/"snapshots"/f"{label}.json"
        write_immutable(immutable_path,serialized)
    (out/"latest_status.json").write_text(serialized)
    (out/"comparison.md").write_text(written)
    return data

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out",default=str(OUTPUT))
    args=ap.parse_args()
    result=run(Path(args.out))
    print("ETH_BOS_EMA_FROZEN_COMPARE",result["status"],
          result["asOfExclusiveUTC"],result["comparison"]["reference"]["metrics25Bps"]["trades"],
          result["comparison"]["candidate"]["metrics25Bps"]["trades"])

if __name__=="__main__":
    main()
