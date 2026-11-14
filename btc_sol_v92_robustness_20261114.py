#!/usr/bin/env python3
"""BTC/SOL V9.2 archived-history robustness. Research-only, not new forward.

Uses 159 previously SHA256 verified official Binance monthly USD-M archives'
frozen trade results, not current candles. No live strategy, orders, alerts,
forward books, notifications, ETH data guard or production changes.
All time periods here were previously inspected: NOT an independent holdout.
"""
import argparse
from collections import defaultdict
from datetime import datetime
from hashlib import sha256
from math import sqrt
import json
from pathlib import Path
import random

INPUT=Path("forward/v92_full_interactions_20261113/historical.json")
OUT=Path("forward/btc_sol_v92_robustness_20261114")
PERIODS=("2022_2024","2024_2026")
COINS=("BTCUSDT","SOLUSDT")
COSTS=(9,25,50)  # bps per SIDE, not verified funding/spread
FROZEN={
 ("2022_2024","BTCUSDT"):(10,-4.265784,-7.701252),
 ("2024_2026","BTCUSDT"):(5,4.101,2.8146),
 ("2022_2024","SOLUSDT"):(12,4.6274,2.0039),
 ("2024_2026","SOLUSDT"):(8,4.2607,2.4099),
}

def date(s):
    d=datetime.fromisoformat(s.replace("Z","+00:00"))
    if d.utcoffset() is None or d.utcoffset().total_seconds()!=0:
        raise ValueError("NOT_UTC")
    return d

def ret(tr,bps):
    pct=float(tr["riskPct"])
    if not .09999<=pct<=4.00001:
        raise ValueError("NON_FROZEN_RISK")
    return float(tr["netR9Bps"])-2*(bps-9)/(100*pct)

def metrics(tape,bps):
    r=[ret(t,bps) for t in tape]
    peak=equity=dd=0.
    for x in r:
        equity+=x
        peak=max(peak,equity)
        dd=max(dd,peak-equity)
    wins=sum(x>0 for x in r)
    pos=sum(x for x in r if x>0)
    neg=-sum(x for x in r if x<0)
    return {"trades":len(r),"wins":wins,"winPct":round(100*wins/len(r),3) if r else None,
            "netR":round(sum(r),6),"profitFactor":round(pos/neg,6) if neg else None,
            "maxDrawdownR":round(dd,6)}

def wilson(w,n):
    if n==0:return None
    z=1.96;p=w/n;d=1+z*z/n
    c=(p+z*z/(2*n))/d
    m=z*sqrt(p*(1-p)/n+z*z/(4*n*n))/d
    return [round(100*(c-m),2),round(100*(c+m),2)]

def guard_source(source):
    if (source["status"]!="V92_91_PAIRS_SIX_PREDECLARED_MULTI_RESEARCH_ONLY"
        or source["verifiedArchives"]!=159 or source["pairCount"]!=91
        or source["singleCount"]!=14 or source["multiCount"]!=6
        or not source["historicPeriodsAreNotIndependentHoldout"]
        or not source["noProductionChanges"] or source["orders"]
        or source["notifications"] or source["forwardAccountWrite"]):
        raise ValueError("WRONG_FROZEN_RESEARCH_SOURCE")
    proofs=[a for p in PERIODS for a in source["manifests"][p]]
    if len(proofs)!=159 or len({(x["symbol"],x["month"]) for x in proofs})!=159:
        raise ValueError("159_SOURCE_MANIFEST_COVERAGE_DRIFT")
    if any(len(x["sha256"])!=64 or
           any(c not in "0123456789abcdef" for c in x["sha256"])
           for x in proofs):
        raise ValueError("BINANCE_SHA256_INVALID")
    if set(source["periods"])!=set(PERIODS):
        raise ValueError("TWO_PERIODS_MISSING")

def frozen_tape(variant,p,coin):
    tape=variant["tradeEvidence"]
    count,r9,r25=FROZEN[(p,coin)]
    if (len(tape)!=count or variant["trades"]!=count
        or abs(variant["netR9Bps"]-r9)>.00016
        or abs(variant["netR25Bps"]-r25)>.00016):
        raise ValueError("BTC_SOL_BASELINE_PARITY_DRIFT")
    begin,end=(date(s) for s in (("2022-10-01T00:00:00Z","2024-10-01T00:00:00Z")
                 if p=="2022_2024" else
                 ("2024-10-01T00:00:00Z","2026-10-01T00:00:00Z")))
    prev=None;keys=set()
    for t in tape:
        if any(k not in t for k in ("entryUTC","retestUTC","exitUTC","side",
                                    "exitReason","riskPct","netR9Bps")):
            raise ValueError("TRADE_SOURCE_MISSING")
        a,b,c=(date(t[k]) for k in ("retestUTC","entryUTC","exitUTC"))
        if not (begin<=b<end and a<=b<c<=end and t["side"] in ("bullish","bearish")):
            raise ValueError("TRADE_CAUSAL_OR_PERIOD_DRIFT")
        key=(b,t["side"])
        if key in keys or (prev is not None and key<prev):
            raise ValueError("TRADE_DUPLICATE_OR_NOT_SORTED")
        keys.add(key);prev=key
    if (abs(sum(ret(t,9) for t in tape)-variant["netR9Bps"])>.00005
        or abs(sum(ret(t,25) for t in tape)-variant["netR25Bps"])>.006):
        raise ValueError("TRADE_9_25_BPS_PARITY_DRIFT")
    stored=variant["at25bps"]
    if (stored["trades"]!=count or stored["wins"]!=sum(ret(t,25)>0 for t in tape)
        or abs(stored["netR"]-variant["netR25Bps"])>.000016):
        raise ValueError("TRADE_WINS_AND_R_PARITY_DRIFT")
    return tape

def closed_daily_regimes(variant):
    source=variant["regimeSlices"]
    result={}
    for group in ("direction","trend","volatility"):
        entries={k.split(":")[1]:v["at25bps"] for k,v in source.items()
                 if k.startswith(group+":") and k.count(":")==1}
        if not entries or sum(x["trades"] for x in entries.values())!=variant["trades"]:
            raise ValueError("CLOSED_DAILY_REGIME_COVERAGE")
        if (sum(x["wins"] for x in entries.values())!=variant["at25bps"]["wins"]
            or abs(sum(x["netR"] for x in entries.values())-variant["netR25Bps"])>.00003):
            raise ValueError("CLOSED_DAILY_REGIME_METRIC_PARITY")
        result[group]={k:{"n":v["trades"],"wins":v["wins"],"r25":v["netR"]}
                       for k,v in entries.items()}
    return result

def merge_regimes(periods):
    out={}
    for group in ("direction","trend","volatility"):
        sums=defaultdict(lambda:{"n":0,"wins":0,"r25":0.})
        for p in PERIODS:
            for category,v in periods[p][group].items():
                s=sums[category]
                for k in ("n","wins","r25"):
                    s[k]+=v[k]
        out[group]={k:{"n":v["n"],"wins":v["wins"],
                       "winPct":round(100*v["wins"]/v["n"],3) if v["n"] else None,
                       "netR25":round(v["r25"],6)}
                    for k,v in sorted(sums.items())}
    return out

def fragility(tape):
    values=[ret(t,25) for t in tape]
    if not values:raise ValueError("EMPTY_SCORED_TAPE")
    total=sum(values)
    quarters=defaultdict(float);months=defaultdict(float)
    for t,r in zip(tape,values):
        dt=date(t["entryUTC"])
        quarters[f"{dt.year}-Q{(dt.month-1)//3+1}"]+=r
        months[t["entryUTC"][:7]]+=r
    positive=sorted((r for r in values if r>0),reverse=True)
    qbest=max(quarters,key=quarters.get)
    return {
        "tradedMonths":len(months),"tradedQuarters":len(quarters),
        "negativeQuarters":sum(x<0 for x in quarters.values()),
        "bestQuarter":qbest,"bestQuarterR25":round(quarters[qbest],6),
        "netR25WithoutBestTrade":round(total-max(values),6),
        "netR25WithoutTwoBestWinners":round(total-sum(positive[:2]),6),
        "netR25WithoutBestQuarter":round(total-quarters[qbest],6),
        "topWinnerShareOfGrossWinningsPct":
            round(100*positive[0]/sum(positive),2) if positive else None,
        "quarterNetR25":{k:round(v,6) for k,v in sorted(quarters.items())},
        "monthNetR25":{k:round(v,6) for k,v in sorted(months.items())}
    }

def bootstrap(tape,seed):
    month=defaultdict(float)
    for t in tape:month[t["entryUTC"][:7]]+=ret(t,25)
    values=[month.get(f"{2022+(9+i)//12:04d}-{(9+i)%12+1:02d}",0.)
            for i in range(48)]
    rng=random.Random(seed);out=[]
    for _ in range(1000):
        score=0.
        for _ in range(16):
            j=rng.randrange(48)
            score+=sum(values[(j+k)%48] for k in range(3))
        out.append(score)
    out.sort()
    return {"threeMonthBlock48ObservedMonthsDescriptive":True,
            "p2_5":round(out[25],5),"p97_5":round(out[974],5),
            "fractionPositiveDescriptive":round(sum(v>0 for v in out)/1000,3),
            "notIndependentOrMultipleTestCorrected":True}

def filter_fragility(doc,coin):
    prior=doc["rankings"][coin]["rankedByEarlyPeriodAlone"]
    rows=[x for x in prior if x["class"]=="signal_interaction"]
    early=[x for x in rows if x["earlyDeltaR25"]>0]
    both=[x for x in early if x["laterDeltaR25"]>0]
    high=[x for x in both if x["minSampleGate"]]
    if any(not x["twoPeriodPositive"] for x in high):
        raise ValueError("PREVIOUSLY_SELECTED_VARIANTS_DRIFT")
    return {"previouslyScannedSignalInteractions":len(rows),
            "earlyPeriodPositiveDelta":len(early),
            "alsoPositiveInAlreadySeenLaterPeriod":len(both),
            "twoPeriodAtLeastTenNewTradesEach":len(high),
            "bothPositiveExamples":[{
                "name":x["mode"],"earlyNew":x["earlyNew"],
                "laterNew":x["laterNew"],
                "deltaEarly":x["earlyDeltaR25"],
                "deltaLater":x["laterDeltaR25"]}
                for x in both[:5]],
            "notPromotedOrFittedHere":True}

def overlaps(btc,sol):
    intersect=[]
    for a in btc:
        for b in sol:
            left=max(date(a["entryUTC"]),date(b["entryUTC"]))
            right=min(date(a["exitUTC"]),date(b["exitUTC"]))
            if left<right:
                intersect.append({"BTCentryUTC":a["entryUTC"],"SOLentryUTC":b["entryUTC"],
                                  "overlapHours":round((right-left).total_seconds()/3600,2)})
    return {
        "simultaneousOpenTradePairs":len(intersect),
        "overlapExamples":intersect[:20],
        "sharedEntryMonths":len({t["entryUTC"][:7] for t in btc}&
                                {t["entryUTC"][:7] for t in sol}),
        "notAWeightedPortfolioOrCorrelation":True,
        "noAssumptionOfIndependentBTCSOLRisks":True}

def run():
    raw=INPUT.read_bytes()
    doc=json.loads(raw)
    guard_source(doc)
    d={"status":"BTC_SOL_FROZEN_HISTORICAL_ROBUSTNESS_RESEARCH_ONLY",
       "sourceSHA256":sha256(raw).hexdigest(),"verifiedOfficialBinanceMonthlyArchives":159,
       "allHistoryPreviouslySeen":True,"independentUnseenHoldout":False,
       "newForwardTradesCredited":0,"newPriceReplay":False,
       "tradingOrders":False,"userNotifications":False,"productionChanges":False,
       "existingPaperBooksChanged":False,"ETHDailyGuardChanged":False,
       "closedDailyRegimesReusedWithoutFutureLeak":True,
       "costPerSideBps":list(COSTS),
       "periods":{},"assets":{}}
    combined={}
    for p in PERIODS:
        d["periods"][p]={}
        for coin in COINS:
            variant=doc["periods"][p]["assets"][coin]["variants"]["BASELINE"]
            tape=frozen_tape(variant,p,coin)
            d["periods"][p][coin]={
                "frozenNetR25":variant["netR25Bps"],
                "stress":{str(b):metrics(tape,b) for b in COSTS},
                "regime":closed_daily_regimes(variant),
                "fragility":fragility(tape)}
            combined.setdefault(coin,[]).extend(tape)
    for coin in COINS:
        tape=combined[coin]
        combined25=sum(d["periods"][p][coin]["frozenNetR25"] for p in PERIODS)
        if abs(combined25-metrics(tape,25)["netR"])>.006:
            raise ValueError("TOTAL_FROZEN_NETR25_PARITY")
        d["assets"][coin]={
            "stress":{str(b):metrics(tape,b) for b in COSTS},
            "frozenNetR25Total":round(combined25,6),
            "wilson95WinPctDescriptive":wilson(sum(ret(t,25)>0 for t in tape),len(tape)),
            "regimes":merge_regimes({p:d["periods"][p][coin]["regime"] for p in PERIODS}),
            "fragility":fragility(tape),
            "blockBootstrap":bootstrap(tape,20261114+(1 if coin=="SOLUSDT" else 0)),
            "historicalFilterFragility":filter_fragility(doc,coin),
            "positiveBothPreviouslySeenPeriods":all(
                d["periods"][p][coin]["stress"]["25"]["netR"]>0 for p in PERIODS),
            "validatedForNewForwardTrading":False}
    d["btcSolOverlap"]=overlaps(combined["BTCUSDT"],combined["SOLUSDT"])
    return d

def markdown(d):
    lines=[
        "# ATLAS — BTC ve SOL V9.2 dayanıklılık testi",
        "",
        "**Sadece daha önce incelenmiş tarihsel işlemlerin yeni denetimi; gerçek ileri/bağımsız holdout DEĞİL.**",
        "159 Binance USD-M aylık ZIP dosyasının önceki SHA256 doğrulamalı arşiv raporundan birebir değişmez işlemler kullanıldı.",
        "Girişte yalnız KAPANMIŞ Daily mumlara dayanan önceki trend/volatilite rejimlerine bakıldı.",
        "Maliyet: 9, 25 ve araştırma amaçlı 50 bps/yön; gerçek fonlama, spread veya emir dolumu kanıtı yok.",
        "",
        "## Tarihsel dönemler ve maliyet dayanıklılığı",
        "",
        "| Dönem | Coin | N | Win %25 | R9 | R25 | R50 | DD25 | PF25 |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|"]
    for p in PERIODS:
        for coin in COINS:
            s=d["periods"][p][coin]["stress"]
            lines.append(f"| {p} | {coin[:3]} | {s['25']['trades']} | "
                         f"{s['25']['winPct']} | {s['9']['netR']:+.3f} | "
                         f"{s['25']['netR']:+.3f} | {s['50']['netR']:+.3f} | "
                         f"{s['25']['maxDrawdownR']:.3f} | {s['25']['profitFactor']} |")
    lines.extend(["","## İki dönem birleşimi — toplam risk ve kazanma oranı","",
        "| Coin | Yeni değil: N/W | Wilson %95 tanımlayıcı | Frozen toplam R25 | R50 | En iyi işlem çıkarılırsa R25 | En iyi iki kazanç çıkarılırsa R25 | En iyi çeyrek çıkarılırsa R25 |",
        "|---|---:|---|---:|---:|---:|---:|---:|"])
    for coin in COINS:
        s=d["assets"][coin];f=s["fragility"];z=s["stress"]
        lines.append(f"| {coin[:3]} | {z['25']['trades']}/{z['25']['wins']} | "
          f"{s['wilson95WinPctDescriptive']} | {s['frozenNetR25Total']:+.3f} | "
          f"{z['50']['netR']:+.3f} | {f['netR25WithoutBestTrade']:+.3f} | "
          f"{f['netR25WithoutTwoBestWinners']:+.3f} | "
          f"{f['netR25WithoutBestQuarter']:+.3f} |")
    lines.extend(["","## Girişte bilinen Daily rejim ve işlem yönü","",
        "| Coin | Boyut | Rejim | N | Kazanma % | R25 |",
        "|---|---|---|---:|---:|---:|"])
    for coin in COINS:
        for group,v in d["assets"][coin]["regimes"].items():
            for category,z in v.items():
                lines.append(f"| {coin[:3]} | {group} | {category} | "
                             f"{z['n']} | {z['winPct']} | {z['netR25']:+.3f} |")
    lines.extend(["","## Çeyrek bazlı yoğunlaşma ve belirsizlik","",
        "| Coin | İşlem yapılan ay/çeyrek | Zarar eden çeyrek | En iyi çeyrek | Blok bootstrap R25 alt/üst %2.5–97.5 |",
        "|---|---|---:|---|---|"])
    for coin in COINS:
        f=d["assets"][coin]["fragility"];b=d["assets"][coin]["blockBootstrap"]
        lines.append(f"| {coin[:3]} | {f['tradedMonths']}/{f['tradedQuarters']} | "
            f"{f['negativeQuarters']} | {f['bestQuarter']} ({f['bestQuarterR25']:+.2f}R) | "
            f"[{b['p2_5']:+.2f},{b['p97_5']:+.2f}] |")
    lines.extend(["",
        "3 aylık blok bootstrap zaten görülmüş 48 ay üzerinden tanımlayıcıdır; ileri dönem veya çoklu karşılaştırma düzeltmesi değildir.",
        "",
        "## Geçmişte taranmış 91 çiftli araştırma: istikrar kontrolü",
        "",
        "| Coin | Sinyal etkileşimi | İlk dönemi iyileştiren | Önceden görülmüş ikinci dönemi de iyileştiren | İki dönem ≥10 yeni işlem koşulu |",
        "|---|---:|---:|---:|---:|"])
    for coin in COINS:
        a=d["assets"][coin]["historicalFilterFragility"]
        lines.append(f"| {coin[:3]} | {a['previouslyScannedSignalInteractions']} | "
            f"{a['earlyPeriodPositiveDelta']} | "
            f"{a['alsoPositiveInAlreadySeenLaterPeriod']} | "
            f"{a['twoPeriodAtLeastTenNewTradesEach']} |")
    x=d["btcSolOverlap"]
    lines.extend(["","## BTC / SOL eşzamanlı risk","",
        f"Örtüşen açık BTC/SOL tarihsel işlem çifti: {x['simultaneousOpenTradePairs']}; "
        f"her iki coin'de giriş yapılan ortak ay: {x['sharedEntryMonths']}.",
        "Bundan bağımsız risk sonucu çıkarılmadı; portföy PnL ve sermaye ağırlıklı korelasyon hesaplanmadı.",
        "",
        "## Karar","",
        "- BTC 2022–24 negatif; 2024–26 tek başına son dönem artısıyla strateji kanıtlanmış sayılmaz.",
        "- SOL iki geçmiş dönemde artı; bu küçük örnekle kalıcı %55 üstünlük, 50bps maliyet veya farklı rejim dayanıklılığı kesin değildir.",
        "- Pozitif dönemler dahil hiçbir tarihsel işlem geleceğe dönük sanal hesaplara eklenmedi.",
        "- Yeni parametre/filtre eklenmedi, eski 91 çiftlik taramadan üretime herhangi bir aday aktarılmadı.",
        "- Gelecek araştırmada varlık başına ≥100 gerçekten yeni kapanmış işlem ve pozitif net R, DD, maliyet, rejim ve istatistiksel belirsizlik kontrolü gereklidir.",
        "- GitHub main, V7/V9.2, ETH günlük veri güvenliği, kullanıcının bildirim saatleri ve görsel BTC/SOL kartları değişmedi.",
        "",
        "Arşiv kaynak SHA256: "+d["sourceSHA256"],""])
    return "\n".join(lines)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out",default=str(OUT))
    args=p.parse_args()
    result=run()
    target=Path(args.out);target.mkdir(parents=True,exist_ok=True)
    (target/"robustness.json").write_text(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2)+"\n")
    (target/"robustness.md").write_text(markdown(result)+"\n")
    print("BTC_SOL_HISTORICAL_159_SHA256_FROZEN_ROBUSTNESS_PASSED",
          [(c,result["assets"][c]["frozenNetR25Total"]) for c in COINS])

if __name__=="__main__":
    main()
