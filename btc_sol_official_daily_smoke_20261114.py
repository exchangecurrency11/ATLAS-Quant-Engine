#!/usr/bin/env python3
"""Read-only BTC/SOL V9.2 vs two regime candidates: official November daily smoke.

NOT PROSPECTIVE, NOT LIVE, NOT AN ALERT. Snapshot is intentionally pinned to
2026-11-14T00:00:00Z (Nov 13 fully closed): before 2026-11-15 candidate
freeze. Official Binance USD-M monthly Aug-Oct + 13 daily November archives,
each ZIP checked against Binance vendor SHA256, 1H 100% continuous.
Replays original engine full state, never makes orders, edits V7/V9.2 accounts,
changes any existing frozen candidate file or sends notifications.
"""
from concurrent.futures import ThreadPoolExecutor,as_completed
import csv
from datetime import date,datetime,timezone
from hashlib import sha256
from io import BytesIO,TextIOWrapper
import json
import math
from pathlib import Path
from zipfile import ZipFile

import download_binance_um_history as archive
import btc_sol_v93_causal_regime_20261114 as strategy
import v92_filter_ablation_20261113 as old
import v92_full_interactions_20261113 as full

OUT=Path("forward/btc_sol_official_daily_smoke_20261114")
FROZEN=Path("forward/btc_sol_v93_prospective_20261114/frozen_spec.json")
SOURCE=Path("forward/v92_full_interactions_20261113/historical.json")
CUTOFF=old.epoch("2026-11-14T00:00:00Z")
CANDIDATE_FREEZE=old.epoch("2026-11-15T00:00:00Z")
MONTHS=("2026-08","2026-09","2026-10")
DAYS=tuple(date(2026,11,d) for d in range(1,14))
SYMBOLS=("BTCUSDT","SOLUSDT")
TOTAL_HOURS=(31+30+31+13)*24
START=old.epoch("2026-08-01T00:00:00Z")

def check_sha_zip(url,archive_cap=7_000_000):
    blob=archive.get(url,max_size=archive_cap)
    tokens=archive.get(url+".CHECKSUM",max_size=2000).decode("utf-8-sig").strip().split()
    if not tokens or len(tokens[0])!=64 or any(c not in "0123456789abcdef" for c in tokens[0].lower()):
        raise ValueError("BTC_SOL_DAILY_VENDOR_SHA256_MISSING")
    digest=sha256(blob).hexdigest()
    if digest!=tokens[0].lower():
        raise ValueError("BTC_SOL_DAILY_VENDOR_SHA256_FAILED")
    return blob,digest

def decode_one_day(sym,day,blob):
    name=f"{sym}-1h-{day.isoformat()}.csv"
    rows=[]
    with ZipFile(BytesIO(blob)) as z:
        filenames=[i for i in z.namelist() if i.endswith(".csv")]
        if len(filenames)!=1 or filenames[0].split("/")[-1]!=name:
            raise ValueError("BTC_SOL_DAILY_ARCHIVE_CSV_NAME_INVALID")
        if z.getinfo(filenames[0]).file_size>1_000_000:
            raise ValueError("BTC_SOL_DAILY_UNCOMPRESSED_SIZE_LIMIT")
        with z.open(filenames[0]) as raw:
            for line in csv.reader(TextIOWrapper(raw,encoding="utf-8-sig")):
                if not line:continue
                if line[0].strip().lower() in ("open time","open_time"):continue
                if len(line)<11:
                    raise ValueError("BTC_SOL_DAILY_KLINE_FIELDS_MISSING")
                ts0=int(line[0])
                ts=ts0//1_000_000 if ts0>10**14 else ts0//1000 if ts0>10**11 else ts0
                o,h,l,c,v=[float(x) for x in line[1:6]]
                qv,tbv,tbq=(float(line[7]),float(line[9]),float(line[10]))
                trades=int(line[8])
                if not (all(math.isfinite(a) for a in (o,h,l,c,v,qv,tbv,tbq))
                    and 0<l<=min(o,c)<=max(o,c)<=h and v>=0
                    and trades>=0 and qv>=0 and tbv>=0 and tbq>=0):
                    raise ValueError("BTC_SOL_DAILY_KLINE_OHLCV_INVALID")
                if (tbv>v+max(1e-8,v*1e-7) or
                    tbq>qv+max(1e-6,qv*1e-7)):
                    raise ValueError("BTC_SOL_DAILY_TAKER_VOLUME_MISMATCH")
                if v and not l*.9999<=qv/v<=h*1.0001:
                    raise ValueError("BTC_SOL_DAILY_BASE_QUOTE_MISMATCH")
                rows.append({"t":ts,"o":o,"h":h,"l":l,"c":c,"v":v,
                            "qv":qv,"trades":trades,"tbv":tbv,"tbq":tbq})
    expected=int(datetime(day.year,day.month,day.day,tzinfo=timezone.utc).timestamp())
    if len(rows)!=24 or any(r["t"]!=expected+i*3600 for i,r in enumerate(rows)):
        raise ValueError("BTC_SOL_DAILY_ARCHIVE_GAP_DUPLICATE_OR_INCOMPLETE")
    return rows

def download_day(sym,day):
    base=f"https://data.binance.vision/data/futures/um/daily/klines/{sym}/1h/{sym}-1h-{day.isoformat()}.zip"
    payload,proof=check_sha_zip(base)
    return sym,day,decode_one_day(sym,day,payload),{"sha256":proof,"url":base}

def frozen_guards():
    spec=json.loads(FROZEN.read_text())
    if spec["freezeUTC"]!="2026-11-15T00:00:00Z":
        raise ValueError("PROSPECTIVE_FREEZE_DATE_CHANGED")
    for name,expected in spec["frozenEngineHashesSHA256"].items():
        if not Path(name).exists() or sha256(Path(name).read_bytes()).hexdigest()!=expected:
            raise ValueError("FROZEN_ENGINE_HASH_DRIFT "+name)
    j=json.loads(SOURCE.read_text())
    if j["status"]!="V92_91_PAIRS_SIX_PREDECLARED_MULTI_RESEARCH_ONLY":
        raise ValueError("PREVIOUS_FROZEN_SOURCE_MISSING")
    hashes={(p["symbol"],p["month"]):p["sha256"]
            for period in ("2022_2024","2024_2026")
            for p in j["manifests"][period]}
    if len(hashes)!=159:
        raise ValueError("FROZEN_159_SOURCE_MANIFEST_NOT_FOUND")
    return hashes

def execute():
    if not CUTOFF<CANDIDATE_FREEZE:
        raise ValueError("SMOKE_NOT_STRICTLY_PREFREEZE")
    known=frozen_guards()
    requested=[(sym,day) for sym in SYMBOLS for day in DAYS]
    archives={}
    proofs={}
    with ThreadPoolExecutor(max_workers=6) as pool:
        tasks={pool.submit(archive.download_month,sym,m):("monthly",sym,m)
               for sym in SYMBOLS for m in MONTHS}
        tasks.update({pool.submit(download_day,sym,d):("daily",sym,d)
                      for sym,d in requested})
        for job in as_completed(tasks):
            kind,sym,period=tasks[job]
            s,m,rows,proof=job.result()
            if s!=sym or m!=period:
                raise ValueError("SMOKE_WRONG_ARCHIVE_OR_SYMBOL")
            if kind=="monthly" and proof["sha256"]!=known[(sym,period)]:
                raise ValueError("SMOKE_FROZEN_MONTH_SHA256_MISMATCH")
            archives[(sym,str(period))]=rows
            proofs[(sym,str(period))]=proof["sha256"]
            print("BTC_SOL_VERIFIED_SOURCE",kind,sym,str(period),len(rows),flush=True)
    out={
      "status":"BTC_SOL_OFFICIAL_DAILY_PREFREEZE_SMOKE_NOT_FORWARD",
      "asOfExclusiveUTC":"2026-11-14T00:00:00Z",
      "prospectiveCandidateFreezeUTC":"2026-11-15T00:00:00Z",
      "monthlyBundlesVerified":len(SYMBOLS)*len(MONTHS),
      "dailyBundlesVerified":len(SYMBOLS)*len(DAYS),
      "officialSHA256ByBundle":{sym:{key:sha for (asset,key),sha in sorted(proofs.items()) if asset==sym}
                               for sym in SYMBOLS},
      "lastFullyClosedDailySource":"2026-11-13",
      "newProspectiveTradesCredited":0,
      "noOrders":True,"noSignalsSent":True,"noExistingAccountWrites":True,
      "notIndependentHoldout":True,"usedSameFrozenOriginalEngine":True,
      "latestChecks":{}
    }
    for sym in SYMBOLS:
        bars=[r for k in (*MONTHS,*(str(d) for d in DAYS))
              for r in archives[(sym,k)]]
        if len(bars)!=TOTAL_HOURS or any(r["t"]!=START+i*3600 for i,r in enumerate(bars)):
            raise ValueError("BTC_SOL_OFFICIAL_1H_CONTINUITY_FAILURE")
        if bars[-1]["t"]+3600!=CUTOFF:
            raise ValueError("BTC_SOL_SMOKE_ASOF_MISMATCH")
        daily=archive.aggregate(bars,86400)
        mode=full.volatility_asof(daily,len(daily))
        all_trials=strategy.replay(bars,sym,CUTOFF)
        month_start=old.epoch("2026-11-01T00:00:00Z")
        control=old._trades(all_trials["BASELINE"]["raw"],month_start,CUTOFF)
        experiment=old._trades(all_trials["CANDIDATE"]["raw"],month_start,CUTOFF)
        pair=old.paired(control,experiment)
        out["latestChecks"][sym]={
            "sourceCandleCount1H":len(bars),
            "latestClosed1HDailyBoundaryUTC":"2026-11-14T00:00:00Z",
            "lastCompletedUTCdayVolatilityClass":mode,
            "nov1To13ClosedReferenceTradesDiagnosticOnly":len(control),
            "nov1To13ClosedCandidateTradesDiagnosticOnly":len(experiment),
            "candidateVetoAudit":all_trials["CANDIDATE"]["audit"],
            "pairedDiagnostic":pair,
            "strictlyPrefreezeNotProspective":True,
            "noUserTradingSignal":True
        }
        print("SMOKE_REPLAY_MATCHED",sym,len(bars),mode,len(control),len(experiment),flush=True)
    return out

def markdown(d):
    items=[
        "# BTC/SOL — gerçek Binance verisiyle son kapanmış gün PROVA",
        "",
        "**Önemli: Dondurma ÖNCESİ veri, ileri kâr testi ve işlem önerisi değildir.**",
        "2026-11-14T00:00:00Z'ye kadar bütün 1H BTC/SOL mumu; resmî Binance USD-M "
        "3 aylık + 13 günlük ZIP dosyalarından SHA256 ile doğrulanmıştır.",
        "Orijinal V9.2 ile iki aday, sabit 2026-11-01–14 UTC aralığındaki "
        "tamamlanmış eski işlemlerde aynı şekilde kronolojik oynatılmıştır.",
        "Karar verirken yalnız kapanmış mumlar kullanılır. "
        "2026-11-15T00:00:00Z öncesi hiçbir işlem ileri test hanesine eklenmez.",
        "",
        "| Varlık | Doğrulanmış 1H mum | Son kapanmış UTC günün volatilitesi | 1–13 Kasım referans eski kapanmış işlem | Aday eski kapanmış işlem |",
        "|---|---:|---|---:|---:|"
    ]
    for sym,x in d["latestChecks"].items():
        items.append(f"| {sym[:3]} | {x['sourceCandleCount1H']} | "
                     f"{x['lastCompletedUTCdayVolatilityClass']} | "
                     f"{x['nov1To13ClosedReferenceTradesDiagnosticOnly']} | "
                     f"{x['nov1To13ClosedCandidateTradesDiagnosticOnly']} |")
    items.extend([
        "",
        f"**Doğrulanmış dosya:** {d['monthlyBundlesVerified']} aylık, {d['dailyBundlesVerified']} günlük.",
        "**Gerçek yeni ileri işlem:** 0 (henüz başlamadı).",
        "Bu yalnızca bağlantı, kaynak bütünlüğü, 1H kesintisizlik ve referansla eşit koşulda kıyas çalışmasının kanıtıdır.",
        "V7/V9.2, mevcut sanal hesaplar, bildirimler, ETH günlük denetimi ve ileri freeze değişmedi.",
        ""
    ])
    return "\n".join(items)

def main():
    result=execute()
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/"smoke.json").write_text(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2)+"\n")
    (OUT/"smoke.md").write_text(markdown(result)+"\n")
    print("BTC_SOL_OFFICIAL_DAILY_PREFREEZE_SOURCE_AND_ENGINE_PROVA_PASSED")
if __name__=="__main__":
    main()
