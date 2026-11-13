#!/usr/bin/env python3
"""V9.2 historical factorial filter research ONLY. No orders, alerts, or book edits.
All variants use the previously source-verified closed-bar fork; the production
engine stays on disk and in Git untouched. Both periods previously inspected.
"""
import argparse
from bisect import bisect_right
from collections import Counter,defaultdict
from itertools import combinations
from datetime import datetime,timezone
from pathlib import Path
import json,math,random
from statistics import median,pstdev
import v92_filter_ablation_20261113 as old

RISK_GATES=frozenset(("risk_max_pct","risk_min_pct"))
SINGLE_GATES=tuple(old.ABLATIONS[k][0] for k in old.ONE_BY_ONE)
assert len(SINGLE_GATES)==14 and len(set(SINGLE_GATES))==14
SIGNAL_GATES=tuple(g for g in SINGLE_GATES if g not in RISK_GATES)
FROZEN_NAMES={tuple(sorted(v)):k for k,v in old.ABLATIONS.items()}
VARIANTS={"BASELINE":()}
for g in SINGLE_GATES:
    VARIANTS[FROZEN_NAMES[(g,)]]=(g,)
PAIRS=[]
for a,b in combinations(SINGLE_GATES,2):
    gates=tuple(sorted((a,b)))
    name=FROZEN_NAMES.get(gates,"PAIR__"+"__".join(gates))
    assert name not in VARIANTS
    VARIANTS[name]=gates
    PAIRS.append(name)
assert len(PAIRS)==91
assert sum(not RISK_GATES.intersection(VARIANTS[n]) for n in PAIRS)==66
PREDECLARED=(
    ("volume_burst","bos_rvol20","rsi_direction"),
    ("bos_break_atr","bos_ema_extension","rsi_direction"),
    ("volume_burst","bos_break_atr","bos_ema_extension"),
    ("rsi_direction","macd_direction","trend4h"),
    ("volume_burst","bos_rvol20","bos_break_atr","bos_ema_extension"),
    ("rsi_direction","macd_direction","bos_break_atr","bos_ema_extension"),
)
MULTI=[]
for gates in PREDECLARED:
    assert len(gates) in (3,4) and len(set(gates))==len(gates)
    assert set(gates).issubset(SIGNAL_GATES) and "trend1d" not in gates
    key=("TRIPLE__" if len(gates)==3 else "QUAD__")+"__".join(sorted(gates))
    VARIANTS[key]=tuple(sorted(gates))
    MULTI.append(key)
assert len(VARIANTS)==112 and len(MULTI)==6

def applicable(coin,mode):
    return coin=="SOLUSDT" or "sol_reversal" not in VARIANTS[mode]

def returns_for(trades,bps):
    return [t["netRIllustrative"]-2*(bps-9)/10000*t["entry"]/t["risk"]
            for t in trades]

def compact_metrics(trades,bps):
    rr=returns_for(trades,bps)
    equity=peak=dd=0.
    for r in rr:
        equity+=r
        peak=max(peak,equity)
        dd=max(dd,peak-equity)
    gain=sum(max(r,0) for r in rr)
    loss=-sum(min(r,0) for r in rr)
    return {"trades":len(rr),"wins":sum(r>0 for r in rr),
            "winPct":round(100*sum(r>0 for r in rr)/len(rr),3) if rr else None,
            "netR":round(sum(rr),6),
            "profitFactor":round(gain/loss,6) if loss else None,
            "maxDrawdownR":round(dd,6)}

def trend_asof(daily,cache,n):
    if n<55:
        return "insufficient"
    ind=cache["indicators"].get((daily[0]["t"],86400,n))
    if ind is None:
        raise ValueError("REGIME_DAILY_INDICATOR_GAP")
    c=daily[n-1]["c"]
    votes=sum((1 if c>ind["EMA20"] else -1 if c<ind["EMA20"] else 0,
               1 if c>ind["EMA50"] else -1 if c<ind["EMA50"] else 0,
               1 if ind["hist"]>0 else -1 if ind["hist"]<0 else 0,
               1 if ind["RSI14"]>50 else -1 if ind["RSI14"]<50 else 0))
    return "bull" if votes>=3 else "bear" if votes<=-3 else "range"

def volatility_asof(daily,n):
    if n<42:
        return "insufficient"
    closes=[d["c"] for d in daily[max(0,n-82):n]]
    if any(c<=0 for c in closes):
        raise ValueError("REGIME_NONPOSITIVE_CLOSE")
    ret=[math.log(closes[i]/closes[i-1]) for i in range(1,len(closes))]
    series=[pstdev(ret[i-20:i]) for i in range(20,len(ret)+1)]
    if len(series)<20:
        return "insufficient"
    return "high" if series[-1]>median(series[:-1]) else "low"

def trade_regime(trade,daily,cache,closes):
    t=int(trade["entryOpenUTC"])
    n=bisect_right(closes,t)
    if n>len(daily) or (n and daily[n-1]["t"]+86400>t):
        raise ValueError("LOOKAHEAD_REGIME_LEAK")
    return trend_asof(daily,cache,n),volatility_asof(daily,n)

def regime_slices(trades,daily,cache):
    close_times=[d["t"]+86400 for d in daily]
    groups=defaultdict(list)
    for trade in trades:
        trend,vol=trade_regime(trade,daily,cache,close_times)
        groups["trend:"+trend].append(trade)
        groups["volatility:"+vol].append(trade)
        groups["direction:"+trade["side"]].append(trade)
        groups["joint:"+trend+":"+vol+":"+trade["side"]].append(trade)
    return {k:{"at9bps":compact_metrics(v,9),
               "at25bps":compact_metrics(v,25)} for k,v in sorted(groups.items())}

def monthly_delta(old_trades,new_trades):
    delta=defaultdict(float)
    for sign,collection in ((-1,old_trades),(1,new_trades)):
        for t in collection:
            m=datetime.fromtimestamp(t["entryOpenUTC"],timezone.utc).strftime("%Y-%m")
            delta[m]+=sign*returns_for([t],25)[0]
    return delta

def bootstrap_delta_25(deltas,start_utc,seed):
    """Predeclared 600 reps, circular moving 3-month blocks. Descriptive ONLY.
    Not a family-wise corrected inferential or genuine out-of-sample test.
    """
    date=datetime.fromisoformat(start_utc.replace("Z","+00:00"))
    months=[f"{date.year+(date.month-1+i)//12:04d}-{(date.month-1+i)%12+1:02d}"
            for i in range(24)]
    values=[deltas.get(m,0.) for m in months]
    rng=random.Random(seed)
    sims=[]
    for _ in range(600):
        total=0.
        for _ in range(8):
            start=rng.randrange(24)
            total+=sum(values[(start+j)%24] for j in range(3))
        sims.append(total)
    sims.sort()
    return [round(sims[15],5),round(sims[584],5)]

def evaluate(coin,rows,pname,ref_data):
    p=old.PERIODS[pname]
    start,end=old.epoch(p["start"]),old.epoch(p["end"])
    four,daily=old.double_checked_candles(rows,end)
    cache={"indicators":{
        **old.exact_streaming_indicator_cache(rows),
        **old.exact_streaming_indicator_cache(four),
        **old.exact_streaming_indicator_cache(daily)},
        "bias":{},"structures":{}}
    scores,raw={},{}
    previous=ref_data["periods"][pname]["assets"][coin]["variants"]
    for mode,gates in VARIANTS.items():
        if not applicable(coin,mode):
            continue
        engine,quality=old.instrumentation(mode,symbol=coin,four=four,cache=cache)
        audit=Counter(examples=[])
        veto=(old.make_selective_gate(coin,four,"SELECTED_SOL_STRICT_SWEEP",audit)
              if coin=="SOLUSDT" and "sol_reversal" not in gates else None)
        report=engine(rows,four,daily,as_of=end,
                      retest_hours=6 if "retest_window" in gates else 4,
                      bos_quality_filter=quality,retest_quality_filter=veto)
        trades=old._trades(report,start,end)
        score=old.to_score(report,start,end)
        score["testedGates"]=list(gates)
        score["riskSensitivityOnly"]=bool(RISK_GATES.intersection(gates))
        score["at25bps"]=compact_metrics(trades,25)
        score["regimeSlices"]=regime_slices(trades,daily,cache)
        if mode in previous:
            frozen=previous[mode]
            for k in ("trades","netR9Bps","netR25Bps"):
                if abs(score[k]-frozen[k])>.000015:
                    raise ValueError(f"OLD_PARITY_DRIFT:{pname}:{coin}:{mode}:{k}")
            before=[(x["entryUTC"],x["side"]) for x in frozen["tradeEvidence"]]
            now=[(x["entryUTC"],x["side"]) for x in score["tradeEvidence"]]
            if before!=now:
                raise ValueError(f"OLD_ENTRY_TAPE_DRIFT:{pname}:{coin}:{mode}")
        raw[mode]=trades
        scores[mode]=score
        print("V92_INTERACTION",pname,coin,mode,score["trades"],
              score["netR25Bps"],flush=True)
    baseline=scores["BASELINE"]
    if not old.valid_baseline_period(pname,coin,baseline):
        raise ValueError("FROZEN_SIX_BASELINES_FAILED")
    for idx,(mode,score) in enumerate(scores.items()):
        score["deltaR9VsBaseline"]=round(score["netR9Bps"]-baseline["netR9Bps"],6)
        score["deltaR25VsBaseline"]=round(score["netR25Bps"]-baseline["netR25Bps"],6)
        score["pairedVsBaseline"]=old.paired(raw["BASELINE"],raw[mode])
        score["bootstrap3MoDeltaR25_95pctDescriptive"]=bootstrap_delta_25(
            monthly_delta(raw["BASELINE"],raw[mode]),p["start"],20261113+idx)
    return {"variants":scores,"cacheCounts":{
        "indicators":len(cache["indicators"]),
        "HTFBias":len(cache["bias"]),
        "structures":len(cache["structures"])}}

def summaries(result):
    out={}
    for coin in old.SYMBOLS:
        a=result["periods"]["2022_2024"]["assets"][coin]["variants"]
        b=result["periods"]["2024_2026"]["assets"][coin]["variants"]
        rows=[]
        for mode in PAIRS+MULTI:
            if mode not in a or mode not in b:
                continue
            x,y=a[mode],b[mode]
            rows.append({"mode":mode,
                "class":"risk_sensitivity" if RISK_GATES.intersection(VARIANTS[mode]) else "signal_interaction",
                "earlyDeltaR25":x["deltaR25VsBaseline"],
                "laterDeltaR25":y["deltaR25VsBaseline"],
                "earlyNew":x["pairedVsBaseline"]["newTrades"],
                "laterNew":y["pairedVsBaseline"]["newTrades"],
                "earlyWinnersLost":x["pairedVsBaseline"]["baselineWinnersLost"],
                "laterWinnersLost":y["pairedVsBaseline"]["baselineWinnersLost"],
                "twoPeriodPositive":x["deltaR25VsBaseline"]>0 and y["deltaR25VsBaseline"]>0,
                "minSampleGate":x["pairedVsBaseline"]["newTrades"]>=10 and
                                y["pairedVsBaseline"]["newTrades"]>=10,
            })
        rows.sort(key=lambda x:(-x["earlyDeltaR25"],x["mode"]))
        out[coin]={"rankedByEarlyPeriodAlone":rows,
                   "laterHasBeenPreviouslyInspected":True,
                   "promotedToLive":[]}
    return out

def run(workers):
    old.fork_source()
    old.ABLATIONS.clear()
    old.ABLATIONS.update(VARIANTS)  # process-local only; original Python file unchanged
    hist,proof=old.download_all(workers)
    if sum(map(len,proof.values()))!=159:
        raise ValueError("SHA256_BINANCE_ARCHIVE_COUNT_MISMATCH")
    reference=json.loads(Path("forward/v92_filter_ablation_20261113/historical.json").read_text())
    result={"status":"V92_91_PAIRS_SIX_PREDECLARED_MULTI_RESEARCH_ONLY",
            "noProductionChanges":True,"orders":False,"notifications":False,
            "forwardAccountWrite":False,"historicPeriodsAreNotIndependentHoldout":True,
            "sources":"Official Binance USD-M 1h monthly archives SHA256 verified",
            "verifiedArchives":159,"manifests":proof,
            "pairCount":91,"pureSignalPairs":66,"pairsContainingRiskSensitivity":25,
            "singleCount":14,"multiCount":6,"scenarioCount":112,
            "gates":{k:list(v) for k,v in VARIANTS.items()},
            "safetySpine":list(old.CONTROL_REQUIREMENTS),
            "regimeDefinition":"daily 4-vote trend & 20-day realized vol vs past-rolling median, at entry using closed days only",
            "multipleTesting":"All findings exploratory; descriptive moving-block bootstrap is not 91-test-adjusted confidence. Previous historical windows are not unseen.",
            "costBpsPerSide":[9,25],"periods":{}}
    for pname,p in old.PERIODS.items():
        period={"from":p["start"],"to":p["end"],
                "verifiedArchives":len(proof[pname]),"assets":{}}
        for coin in old.SYMBOLS:
            period["assets"][coin]=evaluate(coin,hist[pname][coin],pname,reference)
        result["periods"][pname]=period
    result["rankings"]=summaries(result)
    return result

def markdown(d):
    lines=["# V9.2 tüm ikili filtre etkileşimleri (13 Kasım 2026)","",
           "**Yalnızca tarihsel araştırma. V7, V9.2 üretim, sanal hesap ve bildirimler değiştirilmedi.**",
           "159 Binance USD-M arşivi SHA256; altı baseline ve önceki örtüşen senaryolarla işlem/R eşleşmesi.",
           "91 çift: 66 saf sinyal, 25 risk duyarlılığı; 4 önkayıtlı üçlü, 2 dörtlü.",
           "2022–24 ve 2024–26 daha önce görülmüş veridir: bağımsız holdout değildir.","",
           "## Referans V9.2","",
           "| Dönem | Coin | N | Net R9 | Net R25 | DD25 R | PF25 |",
           "|---|---|---:|---:|---:|---:|---:|"]
    for p,period in d["periods"].items():
        for coin,data in period["assets"].items():
            sc=data["variants"]["BASELINE"]; t=sc["at25bps"]
            lines.append(f"| {p} | {coin[:3]} | {sc['trades']} | {sc['netR9Bps']:+.3f} | {sc['netR25Bps']:+.3f} | {t['maxDrawdownR']:.3f} | {t['profitFactor']} |")
    lines.extend(["","## Çiftlerin ve önkayıtlı kombinasyonların ilk döneme göre sıralaması","",
        "Yalnızca sıralama ilk dönemden. Sonraki dönem geçmişte incelenmiş olduğundan gerçek OOS sayılmaz.","",
        "| Coin | Kombinasyon | İlk ΔR25 | Son ΔR25 | Yeni işlem (ilk/son) | Kaçırılan kazanan (ilk/son) |",
        "|---|---|---:|---:|---:|---:|"])
    for coin,r in d["rankings"].items():
        rows=r["rankedByEarlyPeriodAlone"]
        for a in rows[:25]:
            lines.append(f"| {coin[:3]} | {a['mode']} | {a['earlyDeltaR25']:+.3f} | {a['laterDeltaR25']:+.3f} | {a['earlyNew']}/{a['laterNew']} | {a['earlyWinnersLost']}/{a['laterWinnersLost']} |")
        lines.append(f"\n{coin}: tamamı ({len(rows)} kombinasyon) ve her işlem/regim JSON'da yer alır.\n")
    lines.extend(["## İstatistiksel ve işlem sınırları","",
        "- 3-ay blok bootstrap tanımlayıcıdır; çoklu karşılaştırma düzeltmesi değildir.",
        "- Rejimler yalnızca girişte kapanmış günlük mumlarla hesaplandı.",
        "- 9bps/25bps yön başı maliyet fonlama veya gerçek emir dolumunu ispatlamaz.",
        "- Risk sınırı gevşetmeleri araştırmadır; canlı sistem önerisi değildir.",
        "- Değerli görünen düşük örnekli sonuçlar V9.3'e otomatik terfi ettirilmez.",
        "- Geleceğe yönelik yeni kağıt izleme ve önkayıtlı holdout gereklidir.",""])
    return "\n".join(lines)

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--workers",type=int,default=6)
    ap.add_argument("--out",default="forward/v92_full_interactions_20261113")
    args=ap.parse_args()
    if not 1<=args.workers<=6:
        ap.error("workers must be 1..6")
    data=run(args.workers)
    p=Path(args.out);p.mkdir(parents=True,exist_ok=True)
    (p/"historical.json").write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n")
    (p/"historical.md").write_text(markdown(data)+"\n")
    print("V92_91_PAIRS_6_MULTIS_159_SHA256_SIX_BASELINE_PRIOR_PARITY_COMPLETE",flush=True)

if __name__=="__main__":
    main()
