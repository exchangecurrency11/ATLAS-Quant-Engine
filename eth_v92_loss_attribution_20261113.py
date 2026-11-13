#!/usr/bin/env python3
"""ETH V9.2 trade-by-trade forensic report, from previously archived evidence ONLY.

Read-only historical post-mortem; no new backtest, no curve fitting, no orders,
no alerts, no edits to V7/V9.2 forward paper accounts or existing reports.
Both 2022-24 and 2024-26 have already been inspected; not a real holdout.
"""
import argparse
from collections import Counter,defaultdict
from datetime import datetime
from hashlib import sha256
import json
from math import sqrt
from pathlib import Path

INPUT=Path("forward/v92_full_interactions_20261113/historical.json")
OUTPUT=Path("forward/eth_v92_loss_attribution_20261113")
PERIODS=("2022_2024","2024_2026")
COIN="ETHUSDT"
CANDIDATES=(
    "BASELINE",
    "NO_BOS_MIN_BREAK_0P20ATR",
    "NO_BOS_EMA20_MAX_EXTENSION_2P50ATR",
    "PAIR_NO_BREAK_ATR_AND_EMA_EXT",
    "PAIR__bos_break_atr__retest_window",
)
# The candidate names and risk framework were frozen before this diagnostic.
# Do not choose more threshold combinations from this historical outcome.

def r25(trade):
    """Cost conversion 9->25 bps each side, riskPct in percentage points."""
    pct=float(trade["riskPct"])
    if not 0.1-0.00002<=pct<=4.0+0.00002:
        raise ValueError("ETH_RISK_PCT_OUTSIDE_FROZEN_LIMITS")
    return float(trade["netR9Bps"])-0.32/pct

def key(t):
    return (t["entryUTC"],t["side"])

def validate_trade(t):
    if not all(k in t for k in ("entryUTC","retestUTC","exitUTC","side","exitReason","riskPct","netR9Bps")):
        raise ValueError("MISSING_ETH_TRADE_EVIDENCE")
    ts=[datetime.fromisoformat(t[k].replace("Z","+00:00")).timestamp()
        for k in ("retestUTC","entryUTC","exitUTC")]
    if not ts[0]<=ts[1]<ts[2]:
        raise ValueError("NONCAUSAL_ETH_TRADE")
    if t["side"] not in ("bullish","bearish"):
        raise ValueError("INVALID_ETH_DIRECTION")
    return True

def evidence(score):
    tr=score["tradeEvidence"]
    if len(tr)!=score["trades"] or len({key(t) for t in tr})!=len(tr):
        raise ValueError("ETH_TAPE_MISSING_DUPLICATE_OR_INCONSISTENT")
    for t in tr:
        validate_trade(t)
    if any(a["entryUTC"]>b["entryUTC"] for a,b in zip(tr,tr[1:])):
        raise ValueError("ETH_TAPE_NOT_CHRONOLOGICAL")
    if abs(sum(r25(t) for t in tr)-score["netR25Bps"])>.0002:
        raise ValueError("ETH_25BPS_REPORT_PARITY_MISMATCH")
    expected=score["at25bps"]
    if (expected["trades"]!=len(tr) or
        expected["wins"]!=sum(r25(t)>0 for t in tr) or
        abs(expected["netR"]-score["netR25Bps"])>.0002):
        raise ValueError("ETH_SECOND_REPORT_METRIC_PARITY_MISMATCH")
    return tr

def wilson(w,n,z=1.96):
    """Descriptive 95% binomial Wilson interval; not model selection proof."""
    if not n:return None
    p=w/n
    denom=1+z*z/n
    center=(p+z*z/(2*n))/denom
    half=z*sqrt(p*(1-p)/n+z*z/(4*n*n))/denom
    return [round(100*(center-half),2),round(100*(center+half),2)]

def stats(tr):
    rs=[r25(t) for t in tr]
    wins=sum(r>0 for r in rs)
    byexit=defaultdict(lambda:{"count":0,"netR25":0.})
    for t,r in zip(tr,rs):
        x=byexit[t["exitReason"]]
        x["count"]+=1;x["netR25"]+=r
    pos=sum(x for x in rs if x>0)
    neg=sum(x for x in rs if x<0)
    out={"n":len(rs),"wins25bps":wins,
         "winPct25bps":round(100*wins/len(rs),3) if rs else None,
         "winPctWilson95Descriptive":wilson(wins,len(rs)),
         "netR25bps":round(sum(rs),6),
         "grossPositiveR":round(pos,6),
         "grossNegativeR":round(neg,6),
         "profitFactor25bps":round(pos/(-neg),4) if neg else None,
         "exitReasons":{name:{"count":v["count"],"netR25":round(v["netR25"],6)}
                        for name,v in sorted(byexit.items())},
         "costFlipWinners9ToLosers25":sum(t["netR9Bps"]>0 and r25(t)<=0 for t in tr),
         "side":{
             s: {"n":len(v),
                 "wins25bps":sum(r25(t)>0 for t in v),
                 "netR25bps":round(sum(r25(t) for t in v),6)}
             for s in ("bullish","bearish")
             for v in [[t for t in tr if t["side"]==s]]},
         "riskPctOfLosers":[round(t["riskPct"],5) for t in tr if r25(t)<=0]}
    return out

def companion(base,variant):
    b={key(t):t for t in base};v={key(t):t for t in variant}
    common=set(b)&set(v)
    for k in common:
        if abs(r25(b[k])-r25(v[k]))>.00002 or b[k]["exitUTC"]!=v[k]["exitUTC"]:
            raise ValueError("PAIRED_COMMON_ETH_TRADE_DRIFT")
    add=[v[k] for k in sorted(set(v)-set(b))]
    drop=[b[k] for k in sorted(set(b)-set(v))]
    a=stats(add);d=stats(drop)
    delta=sum(r25(t) for t in add)-sum(r25(t) for t in drop)
    return {
        "commonTrades":len(common),
        "added":a,"dropped":d,
        "addedTradeEvidence":[{
            "entryUTC":t["entryUTC"],"side":t["side"],
            "exitReason":t["exitReason"],"netR25bps":round(r25(t),6)}
            for t in add],
        "droppedTradeEvidence":[{
            "entryUTC":t["entryUTC"],"side":t["side"],
            "exitReason":t["exitReason"],"netR25bps":round(r25(t),6)}
            for t in drop],
        "incrementalNetR25bps":round(delta,6),
        "incrementalAttribution":"new sequence trades less displaced baseline trades, not independent signal effects"
    }

def evaluate(doc):
    if (doc["status"]!="V92_91_PAIRS_SIX_PREDECLARED_MULTI_RESEARCH_ONLY" or
        doc["verifiedArchives"]!=159 or doc["pairCount"]!=91 or
        not doc["historicPeriodsAreNotIndependentHoldout"]):
        raise ValueError("WRONG_ETH_VERIFIED_HISTORICAL_SOURCE")
    out={"status":"HISTORICAL_ETH_TRADE_BY_TRADE_POST_MORTEM_ONLY",
         "sourceFile":str(INPUT),"sourceSHA256":sha256(INPUT.read_bytes()).hexdigest(),
         "verifiedHistoricalBinanceArchiveCount":159,
         "bothTimeWindowsAlreadySeen":True,
         "noGenuineUnseenHoldout":True,
         "noOrders":True,"noNotifications":True,
         "noProductionWrites":True,"noForwardPaperCredits":True,
         "positiveNetRAfterCostsRequired":True,
         "candidateSelectionFromThisReportForbidden":True,
         "periods":{},
         "observationsNotGeneralizedAcrossAssets":True}
    for p in PERIODS:
        assets=doc["periods"][p]["assets"]
        if COIN not in assets:
            raise ValueError("ETH_NOT_IN_FULL_RESEARCH")
        av=assets[COIN]["variants"]
        ref=av["BASELINE"]
        base=evidence(ref)
        if (p=="2022_2024" and (len(base)!=10 or abs(ref["netR25Bps"]+4.4969)>.001)
            or p=="2024_2026" and (len(base)!=6 or abs(ref["netR25Bps"]+4.1088)>.001)):
            raise ValueError("ETH_PREVIOUSLY_FROZEN_BASELINE_DRIFT")
        result={"reference":stats(base),"referenceNetR25Report":ref["netR25Bps"],
                "watchCount":ref["BOSWatches"],"selected":{}}
        for mode in CANDIDATES:
            candidate=av[mode]
            tr=evidence(candidate)
            summary=stats(tr)
            pair=companion(base,tr)
            if abs(pair["incrementalNetR25bps"]-candidate["deltaR25VsBaseline"])>.00025:
                raise ValueError("ETH_PAIRED_NET_DELTA_DIVERGES")
            frozen=candidate["pairedVsBaseline"]
            if (len(pair["addedTradeEvidence"])!=frozen["newTrades"] or
                len(pair["droppedTradeEvidence"])!=
                 ref["trades"]-frozen["baselineTradesRetained"]):
                raise ValueError("ETH_PAIRED_EVIDENCE_TAPE_DISAGREEMENT")
            result["selected"][mode]={
                "outcome":summary,"pairedVsCurrentV92":pair,
                "retestVetoes":candidate["retestVetoes"],
                "BOSWatches":candidate["BOSWatches"],
                "riskRejected":candidate["riskRejected"],
                "replayDeltaR25":candidate["deltaR25VsBaseline"],
                "testedGates":candidate["testedGates"]}
        result["referenceWorstTrades"]=[
            {"entryUTC":t["entryUTC"],"side":t["side"],
             "exitReason":t["exitReason"],"riskPct":t["riskPct"],
             "netR9":t["netR9Bps"],"netR25":round(r25(t),6)}
            for t in sorted(base,key=r25)[:5]]
        out["periods"][p]=result
    return out

def markdown(doc):
    lines=[
        "# ETH V9.2 — neden kaybediyor? İşlem bazlı teşhis",
        "",
        "**Arşivden türetilmiş yeni tanısal rapor; yeni işlem, yeni backtest veya bağımsız holdout DEĞİLDİR.**",
        "BTC/SOL/ETH V7 ve V9.2 canlı/forward hesaplarına, görevlerine, bildirimlerine hiç dokunulmadı.",
        "159 önceki SHA256 onaylı Binance USD-M aylık dosyasından türetilen, SHA256 ile sabit 9.5 MB tarihsel JSON üzerinde işlem eşleşmesi yapıldı.",
        "Aynı kapanmış 1H BOS → retest → sonraki 1H sanal giriş; 25bps/yön maliyet stresi.",
        "Tüm iki yıllık dönemler önceden incelendi: kazanma yüzdeleri geleceği öngörmez. Wilson aralıkları yalnız tanımlayıcıdır.",
        "",
        "## ETH baseline kazanan/kaybeden, maliyet, yön ve çıkış",
        "",
        "| Dönem | N | Win% (25bps) | Wilson %95 | Net R25 | LONG N/W/NetR | SHORT N/W/NetR | 9→25bps kazançtan zarara dönüşen |",
        "|---|---:|---:|---|---:|---|---|---:|"
    ]
    for p in PERIODS:
        a=doc["periods"][p]["reference"]
        x=a["side"]["bullish"];y=a["side"]["bearish"]
        lines.append(f"| {p} | {a['n']} | {a['winPct25bps']} | {a['winPctWilson95Descriptive']} | "
          f"{a['netR25bps']:+.3f} | {x['n']}/{x['wins25bps']}/{x['netR25bps']:+.3f} | "
          f"{y['n']}/{y['wins25bps']}/{y['netR25bps']:+.3f} | {a['costFlipWinners9ToLosers25']} |")
    lines.extend(["","## Önceki adaylarla tek tek kronolojik işlem karşılaştırması","",
      "Eklenen yeni işlemlerin net sonucu **eksi** kronolojik olarak yer değiştiren referans işlemlerin net sonucu = adayın gerçek tarihsel delta R'si.",
      "Kötü bir işlem atlanınca daha sonra başka işlem oluşabileceği için filtre başarısı yalnız tek işlemden çıkarılamaz.",
      "",
      "| Dönem | Aday | Win % (25bps) | N | Net R25 | ΔR25 | Yeni N/W/L ve net R25 | Kaybolan N/W/L ve R25 |",
      "|---|---|---:|---:|---:|---:|---|---|"])
    for p in PERIODS:
        for mode in CANDIDATES:
            row=doc["periods"][p]["selected"][mode]
            a=row["outcome"];j=row["pairedVsCurrentV92"];add=j["added"];drop=j["dropped"]
            lines.append(f"| {p} | {mode} | {a['winPct25bps']} | {a['n']} | {a['netR25bps']:+.3f} | "
             f"{j['incrementalNetR25bps']:+.3f} | {add['n']}/{add['wins25bps']}/{add['n']-add['wins25bps']}, {add['netR25bps']:+.3f} | "
             f"{drop['n']}/{drop['wins25bps']}/{drop['n']-drop['wins25bps']}, {drop['netR25bps']:+.3f} |")
    lines.extend(["","## ETH baseline en ağır 5 maliyet-sonrası kayıp (periodik)","",
       "| Dönem | Entry UTC | LONG/SHORT | Stop-risk giriş yüzdesi | R9 | R25 | Çıkış nedeni |",
       "|---|---|---|---:|---:|---:|---|"])
    for p in PERIODS:
        for t in doc["periods"][p]["referenceWorstTrades"]:
            lines.append(f"| {p} | {t['entryUTC']} | {'LONG' if t['side']=='bullish' else 'SHORT'} | "
                         f"{t['riskPct']}% | {t['netR9']:+.3f} | {t['netR25']:+.3f} | {t['exitReason']} |")
    lines.extend(["","## Maliyet ve başarım yorumu",""])
    for p in PERIODS:
        base=doc["periods"][p]["reference"]
        lines.append(f"- {p}: {base['n']} referans işlem, "
           f"{base['wins25bps']} kazanmış; 25bps net {base['netR25bps']:+.3f}R, "
           f"9bps'de kazançlıyken 25bps'de kayba dönen {base['costFlipWinners9ToLosers25']} işlem.")
        reasons=", ".join(f"{k}={v['count']}({v['netR25']:+.2f}R)"
                        for k,v in base["exitReasons"].items())
        lines.append(f"  - Kapanış nedenleri: {reasons}.")
    lines.extend(["","## Bulgulardan türeyen sağlam karar protokolü","",
      "1. Önceki sonuçlar ETH'deki bazı kaliteli fırsatların BOS/EMA kalite kapılarında kaybedilmiş olabileceğini işaret eder; bu **geriye dönük hipotez**, canlı filtre silme gerekçesi değildir.",
      "2. %55 hedefini ETH için tarihsel en yüksek win-rate ile değil, **dondurulmuş** adayların sonraki gerçek bağımsız işlemlerindeki 25bps maliyet sonrası oranı ve pozitif net R ile ölç.",
      "3. ETH retest/body veya hacim filtresini sonuca bakıp tekrar ayarlama; mevcut 91 çift ve 32 eşik denemesi çoklu test içerir.",
      "4. BOS + EMA gevşetme ve BOS + 6H retest adayları zaten ayrı V9.3 shadow dalında dondurulmuştur. Yeni 6 varyant keşfi veya üretime terfi planlanmadı.",
      "5. Eğer ileri ETH adayları da negatif kalırsa işlem yapmama/ABSTAIN kararı meşru; modelin %55 hedefini tutturmak için işlem sayısını sıfırlaması başarılı sonuç sayılmaz.",
      "6. Üç ay trend/volatilite blok örneklemesi çoklu hipotez düzeltmesi değildir. ETH hatalarını kesin açıklamak için borsa emir/funding/gap/vol ve yeni prospektif işlemler gerekir.",
      "7. BTC/SOL özel motorlarına dokunmadan ETH ayrı analiz edilir; evrensel V9 Core sonuçları ETH özelleştirilmiş filtresiyle karıştırılmaz.",
      "",
      f"**Kaynak rapor SHA256:** \`{doc['sourceSHA256']}\`",
      ""])
    return "\n".join(lines)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--infile",default=str(INPUT))
    p.add_argument("--output",default=str(OUTPUT))
    a=p.parse_args()
    # default source file intentionally fixed: do not allow arbitrary rescored snapshots
    if a.infile!=str(INPUT):
        p.error("Only previous sealed history input is accepted")
    result=evaluate(json.loads(INPUT.read_text()))
    target=Path(a.output);target.mkdir(parents=True,exist_ok=True)
    (target/"eth_loss_attribution.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    (target/"eth_loss_attribution.md").write_text(markdown(result)+"\n")
    print("ETH_V92_TRADE_BY_TRADE_LOSS_ATTRIBUTION_VERIFIED",flush=True)

if __name__=="__main__":
    main()
