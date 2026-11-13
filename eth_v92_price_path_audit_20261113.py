#!/usr/bin/env python3
"""ETH V9.2 retrospective trade PRICE PATH audit, independent from forward.

Download only the historical ETH Binance USD-M 1H monthly ZIPs touched by
previously archived trades and verify exact prior SHA256. Compute observed
hourly MFE/MAE, unresolved within-hour stop/TP ambiguity and the cost
contribution of tight stops. Do not optimize exits, claim forward edge,
change live V7/V9.2, send alerts or write existing virtual accounts.
"""
import argparse
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime,timezone,timedelta
from hashlib import sha256
import json
from pathlib import Path

from download_binance_um_history import download_month
import eth_v92_loss_attribution_20261113 as forensic

REF=Path("forward/v92_full_interactions_20261113/historical.json")
FORENSIC=Path("forward/eth_v92_loss_attribution_20261113/eth_loss_attribution.json")
OUT=Path("forward/eth_v92_price_path_audit_20261113")
CANDIDATES=("BASELINE","PAIR_NO_BREAK_ATR_AND_EMA_EXT","PAIR__bos_break_atr__retest_window")
PERIODS=("2022_2024","2024_2026")
ETH="ETHUSDT"
HOUR=3600

def epoch(stamp):
    d=datetime.fromisoformat(stamp.replace("Z","+00:00"))
    if d.tzinfo is None or d.utcoffset()!=timedelta(0):
        raise ValueError("NON_UTC_TRADE_STAMP")
    t=int(d.timestamp())
    if t%HOUR:
        raise ValueError("TRADE_HOURLY_TIMESTAMP_NOT_ALIGNED")
    return t

def touched_months(t):
    entry=epoch(t["entryUTC"])
    exit_time=epoch(t["exitUTC"])
    if not HOUR<=exit_time-entry<=24*HOUR:
        raise ValueError("TRADE_HOLD_OUTSIDE_24_HOURS")
    return {datetime.fromtimestamp(ts,timezone.utc).strftime("%Y-%m")
            for ts in range(entry,exit_time,HOUR)}

def archive_reference(full):
    if (full["status"]!="V92_91_PAIRS_SIX_PREDECLARED_MULTI_RESEARCH_ONLY" or
        full["verifiedArchives"]!=159 or full["pairCount"]!=91):
        raise ValueError("INVALID_FROZEN_159_ARCHIVE_STUDY")
    proofs={}
    for period in PERIODS:
        for entry in full["manifests"][period]:
            if entry["symbol"]!=ETH:
                continue
            month=entry["month"]
            if month in proofs and proofs[month]!=entry["sha256"]:
                raise ValueError("CONFLICTING_ETH_FROZEN_ARCHIVE_HASH")
            proofs[month]=entry["sha256"]
    if len(proofs)!=53:  # 2022-05..2024-09 (29) and 2024-10..2026-09 (24)
        raise ValueError("UNEXPECTED_FROZEN_ETH_MANIFEST_COVERAGE")
    return proofs

def source_trades(full,verified_forensic):
    if (verified_forensic["status"]!="HISTORICAL_ETH_TRADE_BY_TRADE_POST_MORTEM_ONLY"
        or not verified_forensic["bothTimeWindowsAlreadySeen"]
        or verified_forensic["sourceSHA256"]!=sha256(REF.read_bytes()).hexdigest()):
        raise ValueError("ETH_FORENSIC_CROSS_SOURCE_HASH_DRIFT")
    selected={};months=set()
    for p in PERIODS:
        variants=full["periods"][p]["assets"][ETH]["variants"]
        for mode in CANDIDATES:
            trades=variants[mode]["tradeEvidence"]
            if len(trades)!=variants[mode]["trades"]:
                raise ValueError("ETH_ARCHIVED_TRADE_COUNT_DRIFT")
            for tr in trades:
                forensic.validate_trade(tr)
                months.update(touched_months(tr))
            selected[(p,mode)]=trades
    return selected,months

def download_touched(months,expected_hashes,workers):
    data={}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        jobs={pool.submit(download_month,ETH,m):m for m in sorted(months)}
        for fut in as_completed(jobs):
            wanted=jobs[fut]
            symbol,month,bars,proof=fut.result()
            if (symbol,month)!=(ETH,wanted) or proof["sha256"]!=expected_hashes[month]:
                raise ValueError("ETH_OFFICIAL_ARCHIVE_SHA256_CHANGED_OR_WRONG_MONTH")
            for b in bars:
                if b["t"] in data:
                    raise ValueError("DUPLICATED_ETH_HOURLY_CANDLE")
                data[b["t"]]=b
            print("ETH_CLOSED_1H_PRIOR_SHA256_MATCH",month,len(bars),flush=True)
    return data

def excursion(tr,rows):
    forensic.validate_trade(tr)
    entry_ts=epoch(tr["entryUTC"])
    exit_ts=epoch(tr["exitUTC"])
    times=range(entry_ts,exit_ts,HOUR)
    try:
        bars=[rows[ts] for ts in times]
    except KeyError as e:
        raise ValueError("MISSING_VERIFIED_ETH_HOUR_AT_TRADE") from e
    if len(bars)!=len(times) or not bars:
        raise ValueError("NONCONTINUOUS_ETH_TRADE")
    entry=float(tr["entry"])
    pct=float(tr["riskPct"])
    risk=entry*pct/100
    if risk<=0:
        raise ValueError("INVALID_ETH_RISK")
    if abs(bars[0]["o"]-entry)>max(.0000001,entry*1e-8):
        raise ValueError("ETH_ENTRY_BAR_OPEN_PARITY_FAIL")
    is_long=tr["side"]=="bullish"
    def f(b):
        return max(0.,((b["h"]-entry) if is_long else (entry-b["l"]))/risk)
    def a(b):
        return max(0.,((entry-b["l"]) if is_long else (b["h"]-entry))/risk)
    fe=max(map(f,bars))
    ae=max(map(a,bars))
    pre=max(map(f,bars[:-1]),default=0.)
    terminal=bars[-1]
    # The price tolerances absorb the round-off of archived riskPct (5 decimals).
    tolerance=max(0.00001,entry*.0000002)
    stop=(entry-risk) if is_long else (entry+risk)
    target1=(entry+risk) if is_long else (entry-risk)
    target3=(entry+3*risk) if is_long else (entry-3*risk)
    stop_hit=(terminal["l"]<=stop+tolerance if is_long
              else terminal["h"]>=stop-tolerance)
    tp1_hit=(terminal["h"]>=target1-tolerance if is_long
             else terminal["l"]<=target1+tolerance)
    tp3_hit=(terminal["h"]>=target3-tolerance if is_long
             else terminal["l"]<=target3+tolerance)
    reason=tr["exitReason"]
    if reason=="STOP_FIRST_OR_AFTER_TP" and not stop_hit:
        raise ValueError("STOP_FIRST_ARCHIVED_1H_WICK_PARITY_FAIL")
    if reason=="TP3_COMPLETE" and not tp3_hit:
        raise ValueError("TP3_ARCHIVED_1H_WICK_PARITY_FAIL")
    if reason=="TIME_EXIT_AT_CLOSE" and len(bars)!=24:
        raise ValueError("24H_TIME_EXIT_PARITY_FAIL")
    if reason not in ("STOP_FIRST_OR_AFTER_TP","TP3_COMPLETE","TIME_EXIT_AT_CLOSE"):
        raise ValueError("ETH_EXIT_REASON_NOT_FROZEN")
    win=forensic.r25(tr)>0
    return {
        "entryUTC":tr["entryUTC"],"exitUTC":tr["exitUTC"],
        "side":tr["side"],"exitReason":reason,
        "netR25":round(forensic.r25(tr),6),"winningAt25bps":win,
        "entry":entry,"riskPct":pct,
        "holdingHourlyBars":len(bars),
        "maximumFavorableExcursionR":round(fe,5),
        "maximumAdverseExcursionR":round(ae,5),
        "favorableBeforeFinalHourR":round(pre,5),
        "favorableAtLeast1RBeforeFinalHour":pre>=1,
        "stopAndFirstTargetBothInFinalHourlyRange":bool(stop_hit and tp1_hit),
        "endHourStopTouched":bool(stop_hit),
        "endHourTP1Touched":bool(tp1_hit),
        "endHourTP3Touched":bool(tp3_hit),
        "stopFirstPricePathIntraHourUnknown":True,
        "marketFutureUnknownAtTradeEntry":True,
    }

def summarize(path):
    losers=[v for v in path if not v["winningAt25bps"]]
    winners=[v for v in path if v["winningAt25bps"]]
    stop=[v for v in path if v["exitReason"]=="STOP_FIRST_OR_AFTER_TP"]
    def mean(key,seq):
        return round(sum(v[key] for v in seq)/len(seq),5) if seq else None
    return {
        "trades":len(path),"winningTrades25bps":len(winners),"losingTrades25bps":len(losers),
        "stopExitTrades":len(stop),
        "losersThatReached1RBeforeFinalHour":sum(v["favorableAtLeast1RBeforeFinalHour"]
                                                  for v in losers),
        "loserAvgMfeR":mean("maximumFavorableExcursionR",losers),
        "loserAvgMaeR":mean("maximumAdverseExcursionR",losers),
        "winnerAvgMfeR":mean("maximumFavorableExcursionR",winners),
        "winnerAvgMaeR":mean("maximumAdverseExcursionR",winners),
        "stopAndTP1SameFinalHourCount":sum(v["stopAndFirstTargetBothInFinalHourlyRange"] for v in stop),
        "stopAndTP1SameFinalHourShareOfStopExits":
            round(sum(v["stopAndFirstTargetBothInFinalHourlyRange"] for v in stop)/len(stop),4)
            if stop else None,
        "medianHoldHours":sorted(v["holdingHourlyBars"] for v in path)[len(path)//2]
            if path else None,
    }

def run(workers):
    full=json.loads(REF.read_text())
    prior=json.loads(FORENSIC.read_text())
    expected=archive_reference(full)
    chosen,months=source_trades(full,prior)
    if not months or not set(months)<=set(expected):
        raise ValueError("TRADE_MONTH_OUTSIDE_FROZEN_MANIFEST")
    bars=download_touched(months,expected,workers)
    result={
        "status":"RESEARCH_ONLY_HISTORICAL_ETH_OHLCV_EXCURSION_AUDIT",
        "archiveSource":"Binance official USD-M ETHUSDT 1H monthly ZIP SHA256 exact prior study",
        "frozenTradeSourceSHA256":sha256(REF.read_bytes()).hexdigest(),
        "verifiedTouchedETHMonths":len(months),
        "proofSHA256":{m:expected[m] for m in sorted(months)},
        "pathsComputedOnlyFromTradeEntryUntilReportedExit":True,
        "pricePathCannotDetermineIntrabarOrder":True,
        "doesNotReplayOrOptimizeEntriesOrStops":True,
        "bothResearchPeriodsAlreadySeen":True,
        "outOfSampleValidation":False,"noProfitForecast":True,
        "noOrders":True,"noNotifications":True,"noProductionEdits":True,
        "noForwardPaperAccountChanges":True,
        "periods":{}
    }
    for p in PERIODS:
        result["periods"][p]={}
        for mode in CANDIDATES:
            evid=chosen[(p,mode)]
            path=[excursion(t,bars) for t in evid]
            summ=summarize(path)
            if summ["trades"]!=len(evid):
                raise ValueError("ETH_EXCURSION_REPORT_MISSING_TRADES")
            result["periods"][p][mode]={"summary":summ,"trades":path}
    return result

def markdown(result):
    out=[
        "# ETH V9.2 — 1H fiyat yolu: MFE / MAE ve dar stop riski",
        "",
        "**Geçmiş işlemlerin yeni OHLCV incelemesi; yeni backtest/forward sinyal veya gerçek fill değildir.**",
        "Her ETH saatlik Binance USD-M ZIP SHA256 değeri geçmişteki 159 arşivli raporla birebir eşleştirildi.",
        "Yalnız arşivde var olan işlem girişinden çıkışına kadar 1H maksimum lehine/aleyhine hareket ölçüldü.",
        "MFE/MAE işlem girişinde bilinmiyordu; geçmişten filtre seçmek için kullanılamaz.",
        "",
        "## Mevcut referans ile önceden belirlenmiş iki ETH adayının fiyat yolu",
        "",
        "| Dönem | Motor | İşlem | Zarar eden | Zarar eden ort. MFE R | Zarar eden ort. MAE R | Zarar ettiği halde çıkıştan önce 1R görmüş | Stop ile TP1 aynı son mumda |",
        "|---|---|---:|---:|---:|---:|---:|---:|"
    ]
    for p in PERIODS:
        for mode in CANDIDATES:
            s=result["periods"][p][mode]["summary"]
            out.append(f"| {p} | {mode} | {s['trades']} | {s['losingTrades25bps']} | "
                       f"{s['loserAvgMfeR']} | {s['loserAvgMaeR']} | "
                       f"{s['losersThatReached1RBeforeFinalHour']} | "
                       f"{s['stopAndTP1SameFinalHourCount']} |")
    out +=[
        "", "## Mevcut V9.2 başarısız işlemler: ileri bilgiyi işlem sinyali olarak kullanmadan geriye dönük inceleme",
        "",
        "| Dönem | Entry UTC | Yön | Net R25 | Hold 1H | Max lehine R | Max aleyhine R | Son 1H stop ve TP1 aynı mumda? |",
        "|---|---|---|---:|---:|---:|---:|---|"]
    for p in PERIODS:
        for x in result["periods"][p]["BASELINE"]["trades"]:
            if not x["winningAt25bps"]:
                out.append(f"| {p} | {x['entryUTC']} | {'LONG' if x['side']=='bullish' else 'SHORT'} | "
                           f"{x['netR25']:+.3f} | {x['holdingHourlyBars']} | "
                           f"{x['maximumFavorableExcursionR']:.3f} | {x['maximumAdverseExcursionR']:.3f} | "
                           f"{'EVET' if x['stopAndFirstTargetBothInFinalHourlyRange'] else 'Hayır'} |")
    out += [
        "", "## Disiplin ve yorum sınırları",
        "",
        "- Maksimum lehine hareket, alım-satım motorunun o kârı gerçekleştirdiği anlamına gelmez: fiyat hareketi bir mum içinde stop ile aynı anda gerçekleşmiş olabilir.",
        "- Stop ve hedefin aynı 1H mumunda dokunulması durumunda **önce stop** varsayımı korunur. Mum içindeki gerçek sıra resmi 1H OHLCV'den bilinemez.",
        "- 9 bps ve 25 bps maliyetler simülasyondur; gerçek fonlama/spread/gap/emir dolumu kanıtlanmaz.",
        "- Kaybeden işlemde geçmişte görülen MFE veya başka özellik, giriş zamanında bilinmediği için yeni filtreye sızdırılmamalı.",
        "- 2022–24 ve 2024–26 her ikisi de daha önce incelenmiştir, bağımsız unseen dönem değildir.",
        "- V7/V9.2 üretime, mevcut sanal defterlere veya kullanıcının bildirimlerine hiç dokunulmadı.",
        "",
        f"**SHA256 ile eşleşen ETH aylık dosya adedi:** {result['verifiedTouchedETHMonths']}.",
        ""
    ]
    return "\n".join(out)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--workers",type=int,default=6)
    p.add_argument("--out",default=str(OUT))
    args=p.parse_args()
    if not 1<=args.workers<=6:
        p.error("workers must be 1..6")
    r=run(args.workers)
    out=Path(args.out)
    out.mkdir(parents=True,exist_ok=True)
    (out/"price_path.json").write_text(json.dumps(r,ensure_ascii=False,indent=2)+"\n")
    (out/"price_path.md").write_text(markdown(r)+"\n")
    print("ETH_V92_PRIOR_SHA256_PRICE_PATH_AUDIT_PASSED")
if __name__=="__main__":
    main()
