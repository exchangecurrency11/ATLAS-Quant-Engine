#!/usr/bin/env python3
"""Two frozen BTC SOL high-vol regime candidates versus actual V9.2.

Only official COMPLETE Binance USD-M SHA256 checked monthly 1H archives;
all BOS/retest/entry/exit known after research freeze 2026-11-15 00:00 UTC.
Archive snapshots immutable, reference parity against existing V9.3 6-stream
control. Not a live feed, actual fills, orders, alerts or real paper account.
Run only in independent research branch after monthly archive publication.
"""
import argparse
from datetime import datetime,timezone
from hashlib import sha256
import json
from pathlib import Path

import v93_shadow_monthly_20261113 as v93
import v92_filter_ablation_20261113 as old
import v92_full_interactions_20261113 as full
import btc_sol_v93_causal_regime_20261114 as e

OUT=Path("forward/btc_sol_v93_prospective_20261114")
FROZEN_FILES=(
  "btc_sol_v93_causal_regime_20261114.py",
  "btc_sol_v93_prospective_20261114.py",
  "v93_shadow_monthly_20261113.py",
  *e.SOURCE_FILES
)
STREAMS={"BTCUSDT":"BTC_V92_REFERENCE","SOLUSDT":"SOL_V92_REFERENCE"}

def frozen_spec():
    return {
      "freezeUTC":e.FREEZE,
      "freezeIsAfterHistoricalResearch":True,
      "frozenEngineHashesSHA256":{
        f:sha256(Path(f).read_bytes()).hexdigest() for f in FROZEN_FILES},
      "candidateNames":{"BTCUSDT":"BTC_LONG_HIGH_VOL_ONLY",
                        "SOLUSDT":"SOL_HIGH_VOL_ONLY"},
      "candidateSemantics":"BTC only longs high previous closed daily volatility; SOL both sides high previous closed daily volatility; baseline is exact V9.2",
      "source":"Official Binance USD-M 1h completed monthly SHA256 archives only",
      "perSideStressBps":[9,25,50],
      "notAutomaticallyPromoted":True,
      "noBrokerOrders":True,"noUserNotifications":True,
      "noProductionOrV7V92AccountEdits":True
    }

def after_freeze(trades,end):
    eligible=[]
    for t in trades:
        if (t["watchKnownUTC"]>=old.epoch(e.FREEZE)
            and t["retestKnownUTC"]>=old.epoch(e.FREEZE)
            and t["entryOpenUTC"]>=old.epoch(e.FREEZE)
            and t["exitKnownUTC"]<=end):
            if not (t["watchKnownUTC"]<t["retestKnownUTC"]<=t["entryOpenUTC"]<
                    t["exitKnownUTC"]<=end):
                raise ValueError("CANDIDATE_FORWARD_LOOKAHEAD")
            eligible.append(t)
    return eligible

def baseline_matches_existing_frozen_v93(ours,original,coin):
    # The V9.3 original reference freezes one day earlier. Compare only the
    # exact *newer* candidate registration window; original control unchanged.
    v=original[STREAMS[coin]]
    t=[r for r in v["closedProspectiveTrades"]
       if old.epoch(r["watchKnownUTC"])>=old.epoch(e.FREEZE)
       and old.epoch(r["retestKnownUTC"])>=old.epoch(e.FREEZE)
       and old.epoch(r["entryOpenUTC"])>=old.epoch(e.FREEZE)]
    x=[(r["entryOpenUTC"],r["side"],r["exitKnownUTC"],r["netR25Bps"]) for r in t]
    y=[(old.stamp(r["entryOpenUTC"]),r["side"],old.stamp(r["exitKnownUTC"]),
        round(full.returns_for([r],25)[0],7)) for r in ours]
    if len(x)!=len(y):
        raise ValueError("NEW_PROSPECTIVE_REFERENCE_TRADE_COUNT_DRIFT")
    for a,b in zip(x,y):
        if a[:3]!=b[:3] or abs(a[3]-b[3])>.000001:
            raise ValueError("NEW_PROSPECTIVE_ORIGINAL_SIX_STREAM_PARITY")
    return True

def report():
    old.fork_source()
    spec=frozen_spec()
    e_source=OUT/"frozen_spec.json"
    e.write_immutable(e_source,spec)
    month=v93.previous_complete_month(datetime.now(timezone.utc))
    history,manifest,end=v93.download_hist(month,6)
    if end>old.epoch(datetime.now(timezone.utc).isoformat()):
        raise ValueError("CANNOT_USE_UNCOMPLETED_MONTH")
    # Exact original six-stream baseline must agree, but none of the original
    # six streams are modified, persisted, or credited to their accounts here.
    old.ABLATIONS.update({mode:gates for _,mode,gates in v93.CANDIDATES.values()})
    reference=v93.replay_all(history,end)
    result={
      "status":"BTC_SOL_MONTH_COMPLETE_FROZEN_PROSPECTIVE" if end>old.epoch(e.FREEZE)
               else "BTC_SOL_PREFREEZE_PIPELINE_TEST_ONLY",
      "freezeUTC":e.FREEZE,"asOfExclusiveUTC":old.stamp(end),
      "officialArchiveSHA256":dict(sorted(manifest.items())),
      "officialArchiveCount":len(manifest),
      "frozenSpecHashes":spec["frozenEngineHashesSHA256"],
      "independentNewFutureTradesOnly":True,
      "noHistoricalTradesCredited":True,
      "existingSixStreamV93ReferenceParity":True,
      "unresolvedPositionsNotCountedAsClosed":True,
      "realOrders":False,"notifications":False,
      "productionOrExistingPaperWrites":False,
      "candidatePromotionApproved":False,
      "streams":{}
    }
    for coin in e.SYMBOLS:
        replay=e.replay(history[coin],coin,end)
        orig=after_freeze(replay["BASELINE"]["raw"]["trades"],end)
        candidate=after_freeze(replay["CANDIDATE"]["raw"]["trades"],end)
        e.old.paired(orig,candidate)
        baseline_matches_existing_frozen_v93(orig,reference,coin)
        out={}
        for name,trades in (("V92_REFERENCE",orig),("HIGH_VOL_CANDIDATE",candidate)):
            out[name]={
                "metric":{str(b):full.compact_metrics(trades,b) for b in (9,25,50)},
                "closedTrades":[{
                    "watchKnownUTC":old.stamp(t["watchKnownUTC"]),
                    "retestKnownUTC":old.stamp(t["retestKnownUTC"]),
                    "entryOpenUTC":old.stamp(t["entryOpenUTC"]),
                    "exitKnownUTC":old.stamp(t["exitKnownUTC"]),
                    "side":t["side"],
                    "netR25Bps":round(full.returns_for([t],25)[0],7),
                    "exitReason":t["exitReason"]}
                    for t in trades],
                "sourceOnly":True}
        delta=(out["HIGH_VOL_CANDIDATE"]["metric"]["25"]["netR"]-
               out["V92_REFERENCE"]["metric"]["25"]["netR"])
        result["streams"][coin]={
            "versions":out,
            "paired":old.paired(orig,candidate),
            "deltaR25":round(delta,6) if (orig or candidate) else None,
            "noTradeDoesNotDemonstrateAdvantage":True,
            "candidateEntryGateDiagnostic":replay["CANDIDATE"]["audit"]
        }
    if end<=old.epoch(e.FREEZE):
        if any(x["versions"][m]["metric"]["25"]["trades"]>0
               for x in result["streams"].values() for m in x["versions"]):
            raise ValueError("PRE_FREEZE_FORWARD_DATA_FABRICATION")
        e.write_immutable(OUT/"preflight.json",result)
    else:
        d=datetime.fromtimestamp(end,timezone.utc)
        y,m=(d.year-1,12) if d.month==1 else (d.year,d.month-1)
        e.write_immutable(OUT/"snapshots"/f"{y:04d}-{m:02d}.json",result)
        (OUT/"latest.json").write_text(json.dumps(result,sort_keys=True,ensure_ascii=False,indent=2)+"\n")
    return result

def markdown(d):
    x=[
      "# BTC LONG / SOL volatilite — dondurulmuş yeni dönem",
      "",
      "**Bu, yalnızca resmî TAMAMLANMIŞ aylık arşiv ile oluşturulan araştırma özeti.**",
      f"Yeni adayı test başlangıcı: {d['freezeUTC']}; son resmî veri sınırı: {d['asOfExclusiveUTC']}.",
      "Mevcut V9.3 altı stream referanslarıyla işlem/çıkış/net R25 eşleşmesi kontrol edildi.",
      "Gerçek emir, borsa execution kanıtı, finansman veya dinamik spread ölçümü değildir.",
      "",
      "| Varlık | V9.2 işlem | V9.2 R25 | Aday işlem | Aday R25 | Aday−ref R25 |",
      "|---|---:|---:|---:|---:|---:|"]
    for coin,v in d["streams"].items():
        a=v["versions"]["V92_REFERENCE"]["metric"]["25"]
        b=v["versions"]["HIGH_VOL_CANDIDATE"]["metric"]["25"]
        diff=v["deltaR25"]
        x.append(f"| {coin[:3]} | {a['trades']} | {a['netR']:+.3f} | "
          f"{b['trades']} | {b['netR']:+.3f} | "
          f"{diff:+.3f} |" if diff is not None
          else f"| {coin[:3]} | 0 | — | 0 | — | Yetersiz veri |")
    x+=["","**Karar:** Yetersiz yeni işlemden strateji üstünlüğü çıkarma; hiçbir model canlıya geçmez.",
         "BTC/SOL/ETH ana V7/V9.2 ve kullanıcı bildirimleri değişmedi.", ""]
    return "\n".join(x)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out",default=str(OUT))
    a=p.parse_args()
    if Path(a.out)!=OUT:
        p.error("changing the frozen output folder is not allowed")
    d=report()
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/"comparison.md").write_text(markdown(d)+"\n")
    print("BTC_SOL_FORWARD_FROZEN_MONTHLY",d["status"],
          {c: (x["versions"]["V92_REFERENCE"]["metric"]["25"]["trades"],
               x["versions"]["HIGH_VOL_CANDIDATE"]["metric"]["25"]["trades"])
           for c,x in d["streams"].items()})

if __name__=="__main__":
    main()
