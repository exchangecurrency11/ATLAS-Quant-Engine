#!/usr/bin/env python3
"""Predeclared ETH TP1->breakeven exit study; research-only, no live changes.

Replay all ETH 1H bar decisions from independently SHA256-verified Binance
USD-M historical ZIPs. Original V9.2 and two frozen ETH candidates, each
with ORIGINAL exit and a single TP1-then-next-bar-BE exit, same sources.
Stop first if concurrent TP/stop in a 1H candle; adverse gap executes at
OPEN (not a fabricated break-even fill). No entry filtering from future MFE.
Historical periods already inspected: entirely exploratory, NOT holdout.
"""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime,timezone
from hashlib import sha256
import json
from pathlib import Path

import backtest_retest_long_v4 as orig
import v92_filter_ablation_20261113 as old
import v92_full_interactions_20261113 as full
import eth_v92_price_path_audit_20261113 as path

FROZEN_INPUT=Path("forward/v92_full_interactions_20261113/historical.json")
OUT=Path("forward/eth_v92_tp1_breakeven_20261113")
PERIODS=("2022_2024","2024_2026")
MODES=("BASELINE","PAIR_NO_BREAK_ATR_AND_EMA_EXT",
       "PAIR__bos_break_atr__retest_window")
EXITS=("ORIGINAL","TP1_NEXT_1H_BREAK_EVEN")
SYMBOL="ETHUSDT"
ORIG_ASSESS=orig.assess_candle

def be_after_prior_tp1(pos,bar):
    """Fresh 1H after prior closed candle hit TP1; stop-entry is a paper hypothesis.

    This NEVER moves stop intra-candle: original TP1 and its candle obey
    original stop-first. Same-hour protective stop beats any new profit target.
    Prior-candle protective stop gap through entry executes at adverse bar OPEN.
    """
    if pos.get("_be_armed",False):
        if not 1<=pos["targetCount"]<=2:
            raise ValueError("ETH_TP1_BE_INVALID_ARMED_POSITION")
        if not (pos["entry"]>0 and pos["risk"]>0):
            raise ValueError("ETH_TP1_BE_BAD_RISK")
        is_long=pos["side"]=="bullish"
        if pos["side"] not in ("bullish","bearish"):
            raise ValueError("ETH_TP1_BE_UNKNOWN_SIDE")
        hit = (bar["l"]<=pos["entry"]) if is_long else (bar["h"]>=pos["entry"])
        if hit:
            # If the next 1H bar opened beyond the planned entry-level stop,
            # the gap's adverse OPEN is used; never assume a free BE fill.
            px=(min(pos["entry"],bar["o"]) if is_long
                else max(pos["entry"],bar["o"]))
            sign=1 if is_long else -1
            pos["realizedR"] += sign*(px-pos["entry"])/pos["risk"]*(
                3-pos["targetCount"])/3
            return True,"TP1_PRIOR_CLOSE_BE_PROTECT"
        return ORIG_ASSESS(pos,bar)
    was=pos["targetCount"]
    closed,reason=ORIG_ASSESS(pos,bar)
    if not closed and was==0 and pos["targetCount"]>=1:
        pos["_be_armed"]=True
    return closed,reason

def verified_eth_data(full_doc,workers):
    hashes=path.archive_reference(full_doc)
    if set(hashes)!=set(m for p in PERIODS for m in old.PERIODS[p]["months"]):
        raise ValueError("ETH_FULL_WARMUP_MANIFEST_COVERAGE_DRIFT")
    data={}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        fut={pool.submit(path.download_month,SYMBOL,m):m for m in sorted(hashes)}
        for task in as_completed(fut):
            want=fut[task]
            symbol,month,rows,proof=task.result()
            if (symbol,month)!=(SYMBOL,want) or proof["sha256"]!=hashes[month]:
                raise ValueError("ETH_BREAKEVEN_PRIOR_BINANCE_SHA256_MISMATCH")
            data[month]=rows
            print("ETH_TP1_BE_VERIFIED_SHA256",month,len(rows),flush=True)
    if len(data)!=53:
        raise ValueError("ETH_TP1_BE_NOT_ALL_53_VERIFIED_MONTHS")
    return {p:[bar for m in old.PERIODS[p]["months"] for bar in data[m]]
            for p in PERIODS}, hashes

def baseline_exact_parity(got,frozen,period,mode):
    if not old.valid_baseline_period(period,SYMBOL,frozen if mode=="BASELINE" else
                                     frozen):
        # only BASELINE uses the old 6-asset frozen requirement.
        if mode=="BASELINE":
            raise ValueError("ETH_TP1_BASELINE_HISTORICAL_REF_INVALID")
    if (got["trades"]!=frozen["trades"]
        or abs(got["netR9Bps"]-frozen["netR9Bps"])>.000012
        or abs(got["netR25Bps"]-frozen["netR25Bps"])>.000012
        or got["tradeEvidence"]!=frozen["tradeEvidence"]):
        raise ValueError("ETH_TP1_UNMODIFIED_REFERENCE_ENTRY_AND_PNL_DRIFT")

def paired_replay(original,alt):
    def key(t):
        return (int(t["entryOpenUTC"]),t["side"])
    a={key(t):t for t in original}
    b={key(t):t for t in alt}
    if len(a)!=len(original) or len(b)!=len(alt):
        raise ValueError("ETH_TP1_DUPLICATE_ENTRY")
    shared=sorted(set(a)&set(b))
    added=sorted(set(b)-set(a))
    dropped=sorted(set(a)-set(b))
    def ret(t,bps):
        return full.returns_for([t],bps)[0]
    return {
        "sameEntryCount":len(shared),
        "sameEntryModifiedExitCount":sum(
            a[k]["exitKnownUTC"]!=b[k]["exitKnownUTC"] for k in shared),
        "sameEntryNetR25Delta":round(sum(ret(b[k],25)-ret(a[k],25)
                                      for k in shared),6),
        "addedEntryCount":len(added),
        "removedEntryCount":len(dropped),
        "addedEntriesNetR25":round(sum(ret(b[k],25) for k in added),6),
        "removedEntriesNetR25":round(sum(ret(a[k],25) for k in dropped),6),
        "earliestAddedEntriesUTC":[old.stamp(k[0]) for k in added[:10]],
        "earliestDroppedEntriesUTC":[old.stamp(k[0]) for k in dropped[:10]],
        "sequenceSensitive":True,
    }

def study_period(p,rows,full_doc):
    expect=old.PERIODS[p]
    start,end=old.epoch(expect["start"]),old.epoch(expect["end"])
    if (len(rows)!=expect["count1H"] or rows[0]["t"]!=old.epoch(expect["warmup"])
        or rows[-1]["t"]+3600!=end
        or any(r["t"]!=rows[0]["t"]+i*3600 for i,r in enumerate(rows))):
        raise ValueError("ETH_TP1_BE_HISTORY_GAP")
    four,daily=old.double_checked_candles(rows,end)
    cache={"indicators":{
        **old.exact_streaming_indicator_cache(rows),
        **old.exact_streaming_indicator_cache(four),
        **old.exact_streaming_indicator_cache(daily)
    },"bias":{},"structures":{}}
    data={}
    historical=full_doc["periods"][p]["assets"][SYMBOL]["variants"]
    for mode in MODES:
        vals={};raw={}
        for exit_method in EXITS:
            engine,quality=old.instrumentation(mode,symbol=SYMBOL,four=four,cache=cache)
            if exit_method=="TP1_NEXT_1H_BREAK_EVEN":
                # Only forked function's PRIVATE globals, not production module.
                assert engine.__globals__ is not orig.__dict__
                assert engine.__globals__["assess_candle"] is ORIG_ASSESS
                engine.__globals__["assess_candle"]=be_after_prior_tp1
                assert orig.assess_candle is ORIG_ASSESS
            retest_hours=6 if "retest_window" in old.ABLATIONS[mode] else 4
            report=engine(rows,four,daily,as_of=end,retest_hours=retest_hours,
                          bos_quality_filter=quality,
                          retest_quality_filter=None)
            score=old.to_score(report,start,end)
            trades=old._trades(report,start,end)
            if exit_method=="ORIGINAL":
                baseline_exact_parity(score,historical[mode],p,mode)
            if orig.assess_candle is not ORIG_ASSESS:
                raise ValueError("ORIGINAL_V7_ASSESS_GLOBAL_WAS_MODIFIED")
            raw[exit_method]=trades
            vals[exit_method]={
                "metrics9Bps":full.compact_metrics(trades,9),
                "metrics25Bps":full.compact_metrics(trades,25),
                "exitReasonCounts":dict(sorted(Counter(t["exitReason"] for t in trades).items())),
                "BOSWatches":score["BOSWatches"],
                "tradeEvidence":[{
                    "entryUTC":old.stamp(t["entryOpenUTC"]),
                    "exitUTC":old.stamp(t["exitKnownUTC"]),
                    "side":t["side"],"exit":t["exitReason"],
                    "R25":round(full.returns_for([t],25)[0],5)}
                    for t in trades],
                "orders":False}
            print("ETH_TP1_STUDY",p,mode,exit_method,
                  len(trades),vals[exit_method]["metrics25Bps"]["netR"],flush=True)
        delta=paired_replay(raw["ORIGINAL"],raw["TP1_NEXT_1H_BREAK_EVEN"])
        m0=vals["ORIGINAL"]["metrics25Bps"]
        m1=vals["TP1_NEXT_1H_BREAK_EVEN"]["metrics25Bps"]
        if abs((m1["netR"]-m0["netR"])-
               (delta["sameEntryNetR25Delta"]+delta["addedEntriesNetR25"]-
                delta["removedEntriesNetR25"]))>.00005:
            raise ValueError("ETH_TP1_PAIRED_SEQUENCE_DELTA_PARITY_FAIL")
        data[mode]={"variants":vals,"paired":delta,
                    "deltaR25":round(m1["netR"]-m0["netR"],6),
                    "deltaR9":round(vals["TP1_NEXT_1H_BREAK_EVEN"]["metrics9Bps"]["netR"]-
                                    vals["ORIGINAL"]["metrics9Bps"]["netR"],6)}
    return data

def run(workers):
    old.fork_source()
    source=json.loads(FROZEN_INPUT.read_text())
    if source["status"]!="V92_91_PAIRS_SIX_PREDECLARED_MULTI_RESEARCH_ONLY":
        raise ValueError("NO_VERIFIED_FROZEN_ARCHIVE_SOURCE")
    history,proof=verified_eth_data(source,workers)
    result={
        "status":"ETH_V92_FROZEN_PREDECLARED_TP1_NEXT_BAR_BE_HISTORICAL_REPLAY",
        "sourceHistoricalSHA256":sha256(FROZEN_INPUT.read_bytes()).hexdigest(),
        "archiveCountSHA256":53,"manifest":dict(sorted(proof.items())),
        "frozenVariantNames":list(MODES),
        "frozenExitMethods":list(EXITS),
        "stopFirstWithinSame1H":True,
        "protectionOnlyFromNextHourlyCandleAfterPriorTP1":True,
        "adverseGapOpenNotAssumedBreakEven":True,
        "unchangedEnginesParityCheckedAgainstAllSixFrozenETHTapes":True,
        "usesPreviouslyInspectedPeriods":True,"independentHoldout":False,
        "noOrders":True,"noNotifications":True,
        "noProductionV7V92Changes":True,"noLiveForwardPaperWrites":True,
        "noAutomaticCandidatePromotion":True,
        "notActualExchangeExecution":True,
        "costPerSideBps":[9,25],
        "periods":{}
    }
    for p in PERIODS:
        result["periods"][p]=study_period(p,history[p],source)
    return result

def markdown(d):
    out=[
        "# ETH V9.2 — TP1 sonrası bir sonraki 1H'de başa baş stop",
        "",
        "**Ayrı, yalnızca tarihsel ve önceden tanımlı çıkış araştırması. GERÇEK İŞLEM/BAĞIMSIZ HOLDOUT DEĞİLDİR.**",
        "53 Binance ETH resmi aylık SHA256 arşivi, daha önce dondurulmuş veriyle birebir eşleştirildi.",
        "Her varyant tüm BOS/retest durumlarıyla yeniden oynatıldı: aynı girişleri alıp yalnız geçmiş PnL değiştirmek DEĞİL.",
        "İlk TP1 yalnızca kapanmış önceki 1H mumda görüldüyse kalan pozisyon için başa baş koruması sonraki 1H'den itibaren geçerli; aynı mum stop önce.",
        "Bara ters fiyat gap'iyle açılış varsa sanal stop girdi fiyatından değil, gerçekleşebilecek daha kötü AÇILIŞ fiyatından çözülür.",
        "İki dönem de geçmişte incelendi; sonuçlar ileri döneme güvenilir kazanma oranı kanıtı değildir.",
        "",
        "| Dönem | ETH giriş filtresi | Exit | N | Win%25 | NetR25 | PF25 | Max DD25 R | BE koruma çıkışı |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|"
    ]
    for p in PERIODS:
        for mode in MODES:
            for e in EXITS:
                row=d["periods"][p][mode]["variants"][e]
                r=row["metrics25Bps"]
                out.append(f"| {p} | {mode} | {e} | {r['trades']} | {r['winPct']} | {r['netR']:+.3f} | "
                           f"{r['profitFactor']} | {r['maxDrawdownR']:.3f} | "
                           f"{row['exitReasonCounts'].get('TP1_PRIOR_CLOSE_BE_PROTECT',0)} |")
    out.extend(["","## Eşleştirilmiş kronolojik net R farkları","",
                "| Dönem | Giriş filtresi | ΔR25 | ΔR9 | Aynı entry | Farklı çıkış | Sonradan eklenen entry | Kaybolan entry |",
                "|---|---|---:|---:|---:|---:|---:|---:|"])
    for p in PERIODS:
        for mode in MODES:
            r=d["periods"][p][mode]
            x=r["paired"]
            out.append(f"| {p} | {mode} | {r['deltaR25']:+.3f} | {r['deltaR9']:+.3f} | "
                       f"{x['sameEntryCount']} | {x['sameEntryModifiedExitCount']} | "
                       f"{x['addedEntryCount']} | {x['removedEntryCount']} |")
    out.extend(["","## Nasıl yorumlanmalı?","",
                "- TP1 sonrası BE yeni bir **historical research-only** çıkış hipotezidir; geçmiş MFE sonuçlarına bakarak seçildiğinden optimizasyon yanlılığı taşır.",
                "- Başabaş fiyatı, komisyon dahil net başa baş değildir. BE sonrası kalan pozisyon için ücret/slippage ile net zarar mümkün.",
                "- Bir işlem erkenden kapandığında BOS/retest izlemesi ve sıradaki işlem sırası farklılaşabilir; paired ayrım bunu gösterir.",
                "- 25 bps maliyet stresi gerçek borsa dolum, dinamik spread, funding ve stop gap zararlarının tam modeli değildir.",
                "- Sıfır işlem ve birkaç kazanan değişiklik avantaj kanıtı değildir; forward test olmadan üretim/ileti değişmez.",
                "- BTC ve SOL özel motorlarına, evrensel ATLAS Core'a, V7/V9.2 bildirim veya sanal hesaplarına dokunulmadı.",
                ""])
    return "\n".join(out)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--workers",type=int,default=6)
    p.add_argument("--out",default=str(OUT))
    a=p.parse_args()
    if not 1<=a.workers<=6:
        p.error("workers must be 1..6")
    d=run(a.workers)
    out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    (out/"historical.json").write_text(json.dumps(d,ensure_ascii=False,indent=2)+"\n")
    (out/"historical.md").write_text(markdown(d)+"\n")
    print("ETH_TP1_PRIOR_CLOSE_NEXT_BAR_BE_REPLAY_AND_SIX_BASELINE_PARITY_OK")
if __name__=="__main__":
    main()
