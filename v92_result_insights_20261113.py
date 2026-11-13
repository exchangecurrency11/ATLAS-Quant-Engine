#!/usr/bin/env python3
"""Read-only research synthesis of two SUCCESSFUL SHA256/6-parity CI reports.
No new optimization, trades, or account changes; all candidates exploratory.
"""
import json
from pathlib import Path
from itertools import combinations
from collections import Counter
import v92_full_interactions_20261113 as full
import v92_threshold_sensitivity_20261113 as thresh
import v92_filter_ablation_20261113 as old

ROOT=Path("forward")
A=ROOT/"v92_full_interactions_20261113"/"historical.json"
B=ROOT/"v92_threshold_sensitivity_20261113"/"historical.json"
OUT=ROOT/"v92_research_synthesis_20261113"
PERIODS=("2022_2024","2024_2026")
SYMBOLS=("BTCUSDT","ETHUSDT","SOLUSDT")
RISK=frozenset(("risk_max_pct","risk_min_pct"))

def tape(score):
    return tuple((x["entryUTC"],x["side"],x["exitUTC"],x["netR9Bps"])
                 for x in score["tradeEvidence"])

def same(a,b):
    return tape(a)==tape(b) and abs(a["netR25Bps"]-b["netR25Bps"])<0.00001

def record(d,p,c,mode):
    return d["periods"][p]["assets"][c]["variants"][mode]

def format_delta(score):
    return f"{score['deltaR25VsBaseline']:+.3f}"

def raw_risk_stats(sc):
    p=sc["pairedVsBaseline"]
    return f"{p['newTrades']} (W{p['newWinners']}/L{p['newLosers']})",f"{p['baselineWinnersLost']} / {p['baselineLosersAvoided']}"

def check_reports(a,b):
    assert a["status"]=="V92_91_PAIRS_SIX_PREDECLARED_MULTI_RESEARCH_ONLY"
    assert b["status"]=="RESEARCH_ONLY_V92_PREDECLARED_THRESHOLD_SENSITIVITY"
    assert a["verifiedArchives"]==b["verifiedArchives"]==159
    assert a["pairCount"]==91 and b["scenarioCount"]==32
    for period in PERIODS:
        for coin in SYMBOLS:
            x=record(a,period,coin,"BASELINE")
            y=b["periods"][period]["assets"][coin]["scenarios"]["BASELINE"]
            assert same(x,y),("CROSS_STUDY_BASELINE_TAPE_DRIFT",coin,period)
            assert old.valid_baseline_period(period,coin,x)

def all_gate_equivalence(a,coin):
    # Full single/two-gate conditional equivalence, not proof of necessity
    # outside tested 14 gates and observed historical markets.
    checks=[]
    for gate in full.SINGLE_GATES:
        this=next(n for n,g in full.VARIANTS.items() if g==(gate,))
        if not full.applicable(coin,this):
            continue
        baseline_equal=all(same(record(a,p,coin,"BASELINE"),
                               record(a,p,coin,this)) for p in PERIODS)
        conditional=[]
        for other in full.SINGLE_GATES:
            if other==gate:
                continue
            right=next(n for n,g in full.VARIANTS.items() if g==(other,))
            pair=next(n for n,g in full.VARIANTS.items()
                      if len(g)==2 and set(g)=={gate,other})
            if not full.applicable(coin,pair):
                continue
            conditional.append(all(same(record(a,p,coin,right),
                                        record(a,p,coin,pair)) for p in PERIODS))
        checks.append({"gate":gate,"singleDoesNothingBoth":baseline_equal,
                       "conditionalNoEffectCount":sum(conditional),
                       "conditionalPairsChecked":len(conditional),
                       "alwaysRedundantInPairScope":baseline_equal and all(conditional)})
    return checks

def regime_delta(a,coin,name,period):
    base=record(a,period,coin,"BASELINE")["regimeSlices"]
    var=record(a,period,coin,name)["regimeSlices"]
    out=[]
    for prefix in ("trend:","volatility:"):
        keys=sorted({k for k in set(base)|set(var) if k.startswith(prefix)})
        for k in keys:
            x=var.get(k,{}).get("at25bps",{"netR":0.,"trades":0})
            y=base.get(k,{}).get("at25bps",{"netR":0.,"trades":0})
            out.append((k,x["netR"]-y["netR"],x["trades"],y["trades"]))
    return out

def synthesize(a,b):
    check_reports(a,b)
    lines=[
      "# V9.2: etkileşim + eşik taramasının doğrulanmış sentezi",
      "",
      "**Araştırma tarihi 13 Kasım 2026. Canlı sinyal, V7/V9.2 sanal hesap ve bildirimler aynı.**",
      "Önceki 6 baseline ile iki yeni çalışma ve birbirleri arasında işlem teyidi; 159 SHA256 doğrulamalı Binance USD-M aylık arşiv.",
      "Her iki dönem daha önce görülmüştür, gerçek unseen holdout değildir. Çoklu test: 91 çift + 32 eşik senaryosu + 6 önkayıtlı çoklu kombinasyon; yanıltıcı en iyi sonuçlara dikkat.",
      "",
      "## Coin başına gözlenen koşullu filtre tekrarı",
      "",
      "Yalnızca test edilen tekli ve ikili kombinasyonlarda; evrensel gereksizlik kanıtı değildir.",
      "",
      "| Coin | Gate | Tekli iki dönemde etkisiz | Diğer 13 gate ile koşullu etkisizlik (uygun N) |",
      "|---|---|---|---:|",
    ]
    for coin in SYMBOLS:
        for r in all_gate_equivalence(a,coin):
            lines.append(f"| {coin[:3]} | {r['gate']} | {'Evet' if r['singleDoesNothingBoth'] else 'Hayır'} | {r['conditionalNoEffectCount']}/{r['conditionalPairsChecked']} |")
    lines.extend(["","## İki dönemde de pozitif ΔR25 görünen saf sinyal kombinasyonları","",
       "Adayları bulmak için SONUÇLARA göre sıralama yapılır, ancak bu **ön kayıt / bağımsız doğrulama / yatırım tavsiyesi değildir**.",
       "",
       "| Coin | Kombinasyon | İlk ΔR25 | Son ΔR25 | İlk yeni işlem | Son yeni işlem | İlk/son kaçan kârlı | 3-ay bootstrap ilk [%95] |",
       "|---|---|---:|---:|---:|---:|---:|---|"])
    counts={}
    for coin in SYMBOLS:
        modes=[]
        for name in full.PAIRS+full.MULTI:
            if RISK.intersection(full.VARIANTS[name]) or not full.applicable(coin,name):
                continue
            early=record(a,PERIODS[0],coin,name)
            later=record(a,PERIODS[1],coin,name)
            if early["deltaR25VsBaseline"]>0 and later["deltaR25VsBaseline"]>0:
                modes.append((name,early,later))
        modes.sort(key=lambda item:(-min(item[1]["deltaR25VsBaseline"],
                                        item[2]["deltaR25VsBaseline"]),item[0]))
        counts[coin]=len(modes)
        for name,x,y in modes:
            xn,_=raw_risk_stats(x);yn,_=raw_risk_stats(y)
            lines.append(f"| {coin[:3]} | {name} | {format_delta(x)} | {format_delta(y)} | {xn} | {yn} | {x['pairedVsBaseline']['baselineWinnersLost']}/{y['pairedVsBaseline']['baselineWinnersLost']} | {x['bootstrap3MoDeltaR25_95pctDescriptive']} |")
    if not sum(counts.values()):
        lines.append("| — | İki dönemde tutarlı çift bulunamadı | — | — | — | — | — | — |")
    lines.extend(["",f"İki dönemi de geçen pozitif ΔR25 kombinasyon adedi: BTC {counts['BTCUSDT']}, ETH {counts['ETHUSDT']}, SOL {counts['SOLUSDT']}.",
       "Bunların hiçbiri çoklu hipotez / örnek büyüklüğü engelini aşmış sayılmaz.","",
       "## Önemli iki dönemli filtre ablation etkileri","",
       "| Coin | Gate | İlk ΔR25 | Son ΔR25 | İlk/son yeni işlem | İlk/son kaçırılan kazanan |",
       "|---|---|---:|---:|---:|---:|"])
    for coin in SYMBOLS:
        for gate in full.SINGLE_GATES:
            name=next(n for n,g in full.VARIANTS.items() if g==(gate,))
            if not full.applicable(coin,name) or gate in RISK:
                continue
            x=record(a,PERIODS[0],coin,name)
            y=record(a,PERIODS[1],coin,name)
            lines.append(f"| {coin[:3]} | {gate} | {format_delta(x)} | {format_delta(y)} | {x['pairedVsBaseline']['newTrades']}/{y['pairedVsBaseline']['newTrades']} | {x['pairedVsBaseline']['baselineWinnersLost']}/{y['pairedVsBaseline']['baselineWinnersLost']} |")
    lines.extend(["","## Ön araştırma için ETH seçilmiş kombinasyonların piyasa-rejim kırılımı","",
                  "Rejim = giriş anında **kapanmış** Daily 4-oy trend sınıfı; yüksek/düşük volatilite geçmişteki rolling 20g dağılımına göre.",
                  "",
                  "| ETH aday | Dönem | Rejim | Net ΔR25 | Varyant N | Baseline N |",
                  "|---|---|---|---:|---:|---:|"])
    examples=("PAIR_NO_BREAK_ATR_AND_EMA_EXT","PAIR__bos_break_atr__retest_window")
    for mode in examples:
        for p in PERIODS:
            for label,delta,nv,nb in regime_delta(a,"ETHUSDT",mode,p):
                lines.append(f"| {mode} | {p} | {label} | {delta:+.3f} | {nv} | {nb} |")
    lines.extend(["","## 7 aile eşik duyarlılığı: geçmişin tuzakları","",
       "İlk dönemde en iyi puan veren eşikler ikinci dönemde aynı sonucu vermeyebilir; **işlem sıfırlayan** varyantlar avantaj sayılmaz.",
       "",
       "| Coin | Aile | İlk-dönem en iyi eşik | İlk ΔR25 | Son ΔR25 | İlk/son işlem adedi |",
       "|---|---|---:|---:|---:|---:|"])
    for coin in SYMBOLS:
        for family,rows in b["earlyOnlyRankings"][coin].items():
            best=rows[0]
            n1=b["periods"][PERIODS[0]]["assets"][coin]["scenarios"][best["scenario"]]["trades"]
            n2=b["periods"][PERIODS[1]]["assets"][coin]["scenarios"][best["scenario"]]["trades"]
            lines.append(f"| {coin[:3]} | {family} | {best['value']} | {best['earlyDelta25']:+.3f} | {best['laterDelta25']:+.3f} | {n1}/{n2} {'(SIFIR İŞLEM)' if n1==0 or n2==0 else ''} |")
    lines.extend(["","## Net karar","",
       "- Daily yön teyidinin kaldırılması iki dönem/üç coinde tekrar tekrar zarar verdi; **henüz gevşetme gerekçesi yok**.",
       "- RSI çiftlerin tamamında bilgi tekrarı gibi görünüyorsa dahi gerçek bağımsız piyasa verisi ve yeni aday izlemesi olmadan canlıdan çıkarılmaz.",
       "- ETH BOS/retest ve BOS/EMA sinyalleri yalnızca ölçülebilir ileri sanal izleme hipotezidir, V9.3 kuralı değildir.",
       "- Pozitif delta, kaçırılan kârlı işlem, stop risk sınırı, komisyon ve yetersiz yeni işlem birlikte değerlendirilir.",
       "- 3 aylık blok bootstrap tanımlayıcıdır, çoklu test düzeltmesi değildir; hiçbir model üstünlüğü kanıtlanmadı.",
       "- Geleceğe dönük plan research/v92_full_interaction_protocol_20261113.md dosyasında sabitlenmiştir.",""])
    return "\n".join(lines),counts

def main():
    a=json.loads(A.read_text())
    b=json.loads(B.read_text())
    md,counts=synthesize(a,b)
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/"diagnostics.md").write_text(md+"\n")
    (OUT/"metadata.json").write_text(json.dumps({
        "status":"CROSS_RESEARCH_BASELINE_PARITY_AND_REGIME_SYNTHESIS",
        "totalPairCount":a["pairCount"],"thresholdScenarios":b["scenarioCount"],
        "archiveCount":a["verifiedArchives"],"positiveTwoPeriodPairCounts":counts,
        "noProductionChanges":True,"noIndependentHoldoutClaim":True
    },ensure_ascii=False,indent=2)+"\n")
    print("RESEARCH_SYNTHESIS_CROSS_PARITY_91_PAIRS_32_THRESHOLDS_COMPLETED")
if __name__=="__main__":
    main()
