#!/usr/bin/env python3
"""BTC LONG / SOL prior-day high-vol causal replay, research-only.

Frozen after evaluating historical 2022-26. Not independent validation.
Re-download all 159 official Binance USD-M monthly ZIPs with SHA256, replay
complete V9.2 state chronologically; cannot cherry-pick losing trades.
Candidate future eligibility only >= 2026-11-15T00:00:00Z.
Never send alerts, trade or change main, existing V7/V9.2, ETH guard.
"""
import argparse
from bisect import bisect_right
from collections import Counter
from datetime import datetime,timezone
from hashlib import sha256
import json
from pathlib import Path
import v92_filter_ablation_20261113 as old
import v92_full_interactions_20261113 as full

OUT=Path("forward/btc_sol_v93_causal_regime_20261114")
SOURCE=Path("forward/v92_full_interactions_20261113/historical.json")
FREEZE="2026-11-15T00:00:00Z"
PERIODS=("2022_2024","2024_2026")
SYMBOLS=("BTCUSDT","SOLUSDT")
# External event windows are context only. Never used for trade decisions.
EVENTS=(
 ("FTX_2022","2022-11-07","2022-11-22",
  "https://www.elibrary.imf.org/view/journals/001/2023/213/article-A001-en.xml"),
 ("BANKING_2023","2023-03-08","2023-03-23",
  "https://www.elibrary.imf.org/view/journals/001/2023/214/article-A001-en.xml"),
 ("BTC_ETP_2024","2024-01-03","2024-01-18",
  "https://www.sec.gov/newsroom/speeches-statements/gensler-statement-spot-bitcoin-011023"),
 ("SOL_OUTAGE_2024","2024-02-05","2024-02-11",
  "https://solana.com/news/02-06-24-solana-mainnet-beta-outage-report"),
 ("BTC_VOL_SPIKE_2025","2025-10-08","2025-10-16",
  "https://www.spglobal.com/en/research-insights/special-reports/bitcoin-volatility-trends-deep-dive"),
)

def decision(daily,closes,retest):
    t=int(retest["t"])+3600
    n=bisect_right(closes,t)
    if n and daily[n-1]["t"]+86400>t:
        raise ValueError("VOL_REGIME_LOOKAHEAD")
    return full.volatility_asof(daily,n)

def gate(symbol,mode,daily,four):
    closes=[x["t"]+86400 for x in daily]
    if closes!=sorted(closes) or len(set(closes))!=len(closes):
        raise ValueError("INVALID_DAILY_CLOSED_CANDLE_TIMELINE")
    original=(old.make_selective_gate(symbol,four,"SELECTED_SOL_STRICT_SWEEP",Counter(examples=[]))
              if symbol=="SOLUSDT" else None)
    audit=Counter()
    def check(bars,active,retest):
        if original:
            r=original(bars,active,retest)
            if not r["passed"]:
                audit["originalSOLReversalVeto"]+=1
                return r
        if mode=="BASELINE":
            return {"passed":True,"reasons":[]}
        if symbol=="BTCUSDT" and active["side"]=="bearish":
            audit["BTCShortUnchanged"]+=1
            return {"passed":True,"reasons":[]}
        regime=decision(daily,closes,retest)
        audit["regime_"+regime]+=1
        passed=regime=="high"
        if not passed:audit["regimeVeto"]+=1
        return {"passed":passed,
                "reasons":[] if passed else ["FROZEN_PRIOR_CLOSED_DAILY_VOL_REGIME_VETO"]}
    return check,audit

def scored(report,start,end):
    return old._trades(report,start,end)

def replay(rows,symbol,end):
    four,daily=old.double_checked_candles(rows,end)
    cache={"indicators":{
      **old.exact_streaming_indicator_cache(rows),
      **old.exact_streaming_indicator_cache(four),
      **old.exact_streaming_indicator_cache(daily)},
      "bias":{},"structures":{}}
    result={}
    for mode in ("BASELINE","CANDIDATE"):
        engine,quality=old.instrumentation("BASELINE",symbol=symbol,four=four,cache=cache)
        veto,audit=gate(symbol,mode,daily,four)
        r=engine(rows,four,daily,as_of=end,retest_hours=4,
                 bos_quality_filter=quality,retest_quality_filter=veto)
        if r["status"]!="PAPER_BACKTEST_NOT_LIVE":
            raise ValueError("NOT_SAME_CHRONOLOGICAL_V92_ENGINE")
        result[mode]={"raw":r,"audit":dict(audit)}
    return result

def event_matches(tape):
    out=[]
    for name,begin,end,url in EVENTS:
        chosen=[t for t in tape if begin<=t["entryUTC"][:10]<end]
        out.append({"event":name,"startUTC":begin,"endExclusiveUTC":end,"source":url,
                    "n":len(chosen),
                    "netR25":round(sum(t["netR9Bps"]-.32/t["riskPct"] for t in chosen),6),
                    "entriesUTC":[t["entryUTC"] for t in chosen],
                    "onlyContextNotCausal":True})
    return out

def guard(reference):
    if (reference["status"]!="V92_91_PAIRS_SIX_PREDECLARED_MULTI_RESEARCH_ONLY"
        or reference["verifiedArchives"]!=159 or reference["pairCount"]!=91
        or not reference["historicPeriodsAreNotIndependentHoldout"]):
        raise ValueError("PRIOR_SHA256_RESEARCH_SOURCE_CHANGED")
    return True

def run():
    previous=json.loads(SOURCE.read_text())
    guard(previous)
    old.fork_source()
    history,proof=old.download_all(6)
    if sum(len(x) for x in proof.values())!=159:
        raise ValueError("MISSING_159_PRIOR_OFFICIAL_ARCHIVES")
    result={
      "status":"BTC_SOL_FULL_CHRONOLOGICAL_CAUSAL_REGIME_HISTORICAL_ONLY",
      "futureCandidateEligibilityFromUTC":FREEZE,
      "historicalStudiesPreviouslyInspected":True,
      "noIndependentHoldout":True,
      "archiveCountSHA256VerifiedAgain":159,
      "sourceSHA256":sha256(SOURCE.read_bytes()).hexdigest(),
      "noOrders":True,"noProductionOrV7V92PaperChanges":True,
      "noNotifications":True,"noAutomaticCandidatePromotion":True,
      "costPerSideBps":[9,25,50],
      "eventWindowsNotTradingSignals":True,"periods":{}}
    for period in PERIODS:
        config=old.PERIODS[period]
        start,end=old.epoch(config["start"]),old.epoch(config["end"])
        result["periods"][period]={}
        for symbol in SYMBOLS:
            pair=replay(history[period][symbol],symbol,end)
            base=scored(pair["BASELINE"]["raw"],start,end)
            alt=scored(pair["CANDIDATE"]["raw"],start,end)
            prev=previous["periods"][period]["assets"][symbol]["variants"]["BASELINE"]
            a=[(old.stamp(t["entryOpenUTC"]),t["side"],old.stamp(t["exitKnownUTC"])) for t in base]
            b=[(t["entryUTC"],t["side"],t["exitUTC"]) for t in prev["tradeEvidence"]]
            if a!=b or len(base)!=prev["trades"]:
                raise ValueError("BASELINE_FROZEN_ENTRY_EXIT_PARITY_MISMATCH")
            summary=full.compact_metrics(base,25)
            if abs(summary["netR"]-prev["netR25Bps"])>.000012:
                raise ValueError("BASELINE_FROZEN_R25_PARITY_MISMATCH")
            paired=old.paired(base,alt)
            metrics={
              k:{str(cost):full.compact_metrics(tape,cost) for cost in (9,25,50)}
              for k,tape in (("baseline",base),("candidate",alt))}
            result["periods"][period][symbol]={
              "metrics":metrics,"deltaR25":round(metrics["candidate"]["25"]["netR"]-
                                                metrics["baseline"]["25"]["netR"],6),
              "paired":paired,"gateAudit":pair["CANDIDATE"]["audit"],
              "baselineExactPreviousSourceParity":True,
              "events":event_matches(prev["tradeEvidence"])}
            print("BTC_SOL_CAUSAL_GATE",period,symbol,len(base),len(alt),
                  result["periods"][period][symbol]["deltaR25"],flush=True)
    return result

def markdown(d):
    lines=[
      "# BTC LONG / SOL volatilite — tam kronolojik tarihsel araştırma",
      "",
      "**TÜM TARİHLER ÖNCEDEN GÖRÜLMÜŞTÜR: yeni ileri test, bağımsız holdout veya kârlılık kanıtı değil.**",
      "Daha önce dondurulmuş V9.2 engine ile aynı giriş/çıkış, Binance 159 aylık resmî SHA256 kaynağı yeniden kontrol edildi.",
      "Olası LONG BTC ve SOL giriş veto kararı yalnız retest kapanışından önce TAMAMLANMIŞ Daily volatilite sınıfıyla verilir.",
      "BTC SHORT hiç engellenmez. SOL eski seçici ters mum vetosu korunur.",
      "Yeni, gerçekten ileri değerlendirme için tasarlanan başlangıç: 2026-11-15T00:00:00Z.",
      "",
      "| Dönem | Coin | Yöntem | N | W%25 | R25 | R50 | DD25 | ΔR25 aday-ref |",
      "|---|---|---|---:|---:|---:|---:|---:|---:|"]
    for period,coins in d["periods"].items():
        for coin,v in coins.items():
            for mode,score in v["metrics"].items():
                lines.append(f"| {period} | {coin[:3]} | {mode} | {score['25']['trades']} | "
                  f"{score['25']['winPct']} | {score['25']['netR']:+.3f} | "
                  f"{score['50']['netR']:+.3f} | {score['25']['maxDrawdownR']:.3f} | "
                  f"{v['deltaR25']:+.3f} |")
    lines+=["","## Dış kaynaklı tarihsel olaylarla işlemlerin eşleştirilmesi","",
            "| Olay | BTC işlem / R25 | SOL işlem / R25 |","|---|---:|---:|"]
    for idx,(name,start,end,url) in enumerate(EVENTS):
        rows={}
        for coin in SYMBOLS:
            ev=[row for period in PERIODS
                for row in d["periods"][period][coin]["events"]
                if row["event"]==name]
            rows[coin]=(sum(x["n"] for x in ev),sum(x["netR25"] for x in ev))
        lines.append(f"| [{name}]({url}) ({start}–{end}) | "
                    f"{rows['BTCUSDT'][0]} / {rows['BTCUSDT'][1]:+.3f} | "
                    f"{rows['SOLUSDT'][0]} / {rows['SOLUSDT'][1]:+.3f} |")
    lines+=["","Olay pencereleri dış kaynaktan sabitlendi. Eşleşme korelasyon değil; olayın işlemi meydana getirdiğine dair kanıt değildir.",
       "Yanlılık: geçmiş LONG ve volatilite sonuçları görüldükten sonra bu iki aday tasarlandı.",
       "Başka fırsatları engelleme etkisini görmek için her adayın TÜM 1H strateji sırası yeniden oynatıldı; yalnızca kaybeden eski işlemler silinmedi.",
       "25/50 bps ücret-stres modelleri gerçek emir dolumunu, dinamik spread, funding ve pozisyon likidasyonunu doğrulamaz.",
       "V7/V9.2, ETH günlük veri güvenliği, tüm sanal hesaplar, otomasyonlar ve bildirimler değiştirilmedi.",
       ""]
    return "\n".join(lines)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out",default=str(OUT))
    a=p.parse_args()
    d=run()
    out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    (out/"historical.json").write_text(json.dumps(d,sort_keys=True,ensure_ascii=False,indent=2)+"\n")
    (out/"historical.md").write_text(markdown(d)+"\n")
    print("BTC_SOL_ALL_159_OFFICIAL_SHA256_CAUSAL_GATES_PARITY_PASS",flush=True)

if __name__=="__main__":
    main()
