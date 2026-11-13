#!/usr/bin/env python3
"""Research-only V9.2 predeclared one-parameter threshold sensitivity.
Never mutates any source on disk, production system, account or notification.
Both historical periods previously seen, so comparisons are NOT unseen OOS.
"""
import argparse,json,math
from collections import Counter
from pathlib import Path
from itertools import chain
import v92_filter_ablation_20261113 as old
import v92_full_interactions_20261113 as full

# Frozen before running; all baseline thresholds are explicit and included.
GRID={
 "volume_surge_pct":(0,10,20,30,40,50),
 "rsi_long_cutoff":(46,48,50,52,54,56),
 "macd_hist_ema_bps":(0,0.5,1,2,3),
 "rvol20_min":(0.8,1.0,1.2,1.4,1.6),
 "bos_break_atr_min":(0,0.1,0.2,0.3,0.4),
 "ema_distance_atr_max":(1.5,2.0,2.5,3.0,4.0),
 "retest_hours":(2,3,4,5,6,8),
}
DEFAULT={
 "volume_surge_pct":20,
 "rsi_long_cutoff":50,
 "macd_hist_ema_bps":0,
 "rvol20_min":1.2,
 "bos_break_atr_min":0.2,
 "ema_distance_atr_max":2.5,
 "retest_hours":4,
}
assert set(GRID)==set(DEFAULT) and all(DEFAULT[k] in GRID[k] for k in GRID)
SCENARIOS={"BASELINE":(None,None)}
for family,values in GRID.items():
    for value in values:
        if value==DEFAULT[family]:
            continue
        SCENARIOS[f"{family}__{str(value).replace('.','p')}"]=(family,value)
assert len(SCENARIOS)==1+sum(len(v)-1 for v in GRID.values())

# Fail closed if source pattern changes; original old.replay_pair stays intact.
VOLUME_EXPECT="if vol_pct is None or (not _skip('volume_burst') and vol_pct < 20):"
VOLUME_PATCH="if vol_pct is None or vol_pct < _volume_threshold:"

def engine_for(family,value,symbol,four,cache):
    eng,q=old.instrumentation("BASELINE",symbol=symbol,four=four,cache=cache)
    ns=eng.__globals__
    if family=="volume_surge_pct":
        src=old.fork_source()
        if src.count(VOLUME_EXPECT)!=1:
            raise ValueError("V92_THRESHOLD_ORIGINAL_VOLUME_CODE_CHANGED")
        ns["_volume_threshold"]=value
        src=src.replace(VOLUME_EXPECT,VOLUME_PATCH,1)
        exec(compile(src,"<research-only-volume-threshold>","exec"),ns)
        eng=ns["replay_pair"]
    if family in ("rsi_long_cutoff","macd_hist_ema_bps"):
        rsi=value if family=="rsi_long_cutoff" else DEFAULT["rsi_long_cutoff"]
        macd=value if family=="macd_hist_ema_bps" else 0
        def momentum(ind,side):
            if side not in ("bullish","bearish"):
                raise ValueError("INVALID_THRESHOLD_SIDE")
            r,h,ema=ind["RSI14"],ind["hist"],ind["EMA20"]
            limit=macd/10000*ema
            return ((r>rsi and h>limit) if side=="bullish" else
                    (r<100-rsi and h<-limit))
        ns["_momentum_side"]=momentum
        ns["_momentum_possible"]=lambda ind: (
            momentum(ind,"bullish") or momentum(ind,"bearish"))
    if family in ("rvol20_min","bos_break_atr_min","ema_distance_atr_max"):
        br=value if family=="bos_break_atr_min" else .2
        rv=value if family=="rvol20_min" else 1.2
        ex=value if family=="ema_distance_atr_max" else 2.5
        def q(w,bos,ind):
            return old.evaluate_bos_quality(
                w,bos,ind,min_break_atr=br,
                min_rvol20=rv,max_extension_atr=ex)
    return eng,q

def evaluate(coin,rows,pname,old_json):
    p=old.PERIODS[pname]
    start,end=old.epoch(p["start"]),old.epoch(p["end"])
    four,daily=old.double_checked_candles(rows,end)
    cache={"indicators":{
        **old.exact_streaming_indicator_cache(rows),
        **old.exact_streaming_indicator_cache(four),
        **old.exact_streaming_indicator_cache(daily)},
        "bias":{},"structures":{}}
    result,raw={},{}
    for mode,(family,value) in SCENARIOS.items():
        eng,quality=engine_for(family,value,coin,four,cache)
        audit=Counter(examples=[])
        veto=(old.make_selective_gate(coin,four,"SELECTED_SOL_STRICT_SWEEP",audit)
              if coin=="SOLUSDT" else None)
        report=eng(rows,four,daily,as_of=end,
                   retest_hours=value if family=="retest_hours" else 4,
                   bos_quality_filter=quality,
                   retest_quality_filter=veto)
        trades=old._trades(report,start,end)
        score=old.to_score(report,start,end)
        score["thresholdFamily"]=family
        score["thresholdValue"]=value
        score["at25bps"]=full.compact_metrics(trades,25)
        score["regimeSlices"]=full.regime_slices(trades,daily,cache)
        raw[mode]=trades
        result[mode]=score
        print("V92_THRESHOLD",pname,coin,mode,score["trades"],
              score["netR25Bps"],flush=True)
    base=result["BASELINE"]
    if not old.valid_baseline_period(pname,coin,base):
        raise ValueError("SIX_BASELINE_REPLAY_DRIFT")
    ref=old_json["periods"][pname]["assets"][coin]["variants"]["BASELINE"]
    if [(a["entryUTC"],a["side"]) for a in base["tradeEvidence"]] != [
        (a["entryUTC"],a["side"]) for a in ref["tradeEvidence"]]:
        raise ValueError("SIX_BASELINE_ENTRY_TAPE_DRIFT")
    for idx,(mode,score) in enumerate(result.items()):
        score["deltaR9VsBaseline"]=round(score["netR9Bps"]-base["netR9Bps"],6)
        score["deltaR25VsBaseline"]=round(score["netR25Bps"]-base["netR25Bps"],6)
        score["pairedVsBaseline"]=old.paired(raw["BASELINE"],raw[mode])
        score["bootstrap3MoDeltaR25_95pctDescriptive"]=full.bootstrap_delta_25(
            full.monthly_delta(raw["BASELINE"],raw[mode]),p["start"],20261113+idx)
    return {"scenarios":result,"cacheCounts":{
        "indicator":len(cache["indicators"]),
        "bias":len(cache["bias"]),
        "structures":len(cache["structures"])}}

def early_only_ranking(out):
    ranked={}
    for coin in old.SYMBOLS:
        early=out["periods"]["2022_2024"]["assets"][coin]["scenarios"]
        late=out["periods"]["2024_2026"]["assets"][coin]["scenarios"]
        families={}
        for family in GRID:
            keys=[k for k,(f,v) in SCENARIOS.items() if f==family]
            rows=[]
            for k in keys:
                a,b=early[k],late[k]
                rows.append({"scenario":k,"value":a["thresholdValue"],
                  "earlyDelta25":a["deltaR25VsBaseline"],
                  "laterDelta25":b["deltaR25VsBaseline"],
                  "earlyNew":a["pairedVsBaseline"]["newTrades"],
                  "laterNew":b["pairedVsBaseline"]["newTrades"],
                  "earlyWinnersLost":a["pairedVsBaseline"]["baselineWinnersLost"],
                  "laterWinnersLost":b["pairedVsBaseline"]["baselineWinnersLost"]})
            rows.sort(key=lambda x:(-x["earlyDelta25"],str(x["value"])))
            families[family]=rows
        ranked[coin]=families
    return ranked

def run(workers):
    old.fork_source()
    if old.fork_source().count(VOLUME_EXPECT)!=1:
        raise ValueError("THRESHOLD_ABLATION_SOURCE_NO_LONGER_KNOWN")
    hist,proof=old.download_all(workers)
    if sum(map(len,proof.values()))!=159:
        raise ValueError("SHA256_MANIFEST_COUNT_WRONG")
    reference=json.loads(Path("forward/v92_filter_ablation_20261113/historical.json").read_text())
    data={"status":"RESEARCH_ONLY_V92_PREDECLARED_THRESHOLD_SENSITIVITY",
          "noOrders":True,"noLiveEdits":True,"noForwardBookChanges":True,
          "historicalPeriodsPreviouslyInspected":True,
          "fixedGrids":GRID,"baselineThresholds":DEFAULT,
          "scenarioCount":len(SCENARIOS),"periods":{},
          "verifiedArchives":159,"sha256Manifest":proof,
          "onlyOneParameterVariesPerReplay":True,
          "macd_hist_ema_bps_note":"MACD histogram magnitude threshold in bps of EMA20, sign retained",
          "rsi_long_cutoff_note":"LONG RSI > t; SHORT RSI < 100-t",
          "regimeDefinition":"entry-known closed daily 4-vote trend and trailing 20d vol-relative-to-past median",
          "costPerSideBps":[9,25],
          "multipleTesting":"Exploratory; multiple threshold scanning, historical windows both previously inspected; no statistical promotion.",
          "safetySpine":list(old.CONTROL_REQUIREMENTS)}
    for pname in old.PERIODS:
        d={"verifiedArchives":len(proof[pname]),"assets":{}}
        for coin in old.SYMBOLS:
            d["assets"][coin]=evaluate(coin,hist[pname][coin],pname,reference)
        data["periods"][pname]=d
    data["earlyOnlyRankings"]=early_only_ranking(data)
    return data

def markdown(d):
    lines=["# V9.2 eşik duyarlılığı — tarihsel araştırma","",
           "**Üretim, emirler, sanal hesaplar ve bildirimler değiştirilmedi.**",
           f"{d['scenarioCount']} yapılandırma; 159 resmî Binance SHA256 doğrulamalı arşiv; iki dönem de önceden görülmüştür.",
           "RSI LONG>eşik, SHORT<(100-eşik); MACD eşiği hist/EMA20 bps; diğer eşikler tek tek değiştirilir.",
           "9 ve 25bps/yön maliyet; her coin, yön ve kapanmış-gün rejimi için JSON'da detay var.","",
           "| Coin | Eşik ailesi | İlk dönem en yüksek ΔR25 (sadece keşif) | Sonraki dönem ΔR25 | İlk/son yeni işlem |",
           "|---|---|---:|---:|---:|"]
    for coin,families in d["earlyOnlyRankings"].items():
        for name,rows in families.items():
            best=rows[0]
            lines.append(f"| {coin[:3]} | {name}={best['value']} | {best['earlyDelta25']:+.3f} | {best['laterDelta25']:+.3f} | {best['earlyNew']}/{best['laterNew']} |")
    lines+=["","**Uyarı:** Erken döneme göre 'en yüksek' geçmiş kâr, sağlam geleceğe dönük avantaj değildir.",
            "Bootstrap tanımlayıcıdır; çoklu tarama düzeltmesi veya gerçek bağımsız test değildir.",
            "Gelecekteki kağıt izleme olmadan V9.3'e otomatik geçiş yapılmaz.",""]
    return "\n".join(lines)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--workers",type=int,default=6)
    p.add_argument("--out",default="forward/v92_threshold_sensitivity_20261113")
    a=p.parse_args()
    if not 1<=a.workers<=6:
        p.error("workers must be 1..6")
    outcome=run(a.workers)
    dest=Path(a.out);dest.mkdir(parents=True,exist_ok=True)
    (dest/"historical.json").write_text(json.dumps(outcome,ensure_ascii=False,indent=2)+"\n")
    (dest/"historical.md").write_text(markdown(outcome)+"\n")
    print("V92_FROZEN_7_THRESHOLD_FAMILIES_159_SHA256_SIX_PARITY_COMPLETE",flush=True)
if __name__=="__main__":
    main()
