#!/usr/bin/env python3
"""SOLUSDT USD-M perpetual OI, funding, taker BUY/SELL data quality audit.

Sources: Binance Vision official ZIP and .CHECKSUM only. Research-only.
Never mix next-day archives into contemporaneous forward V7 signals.
Metrics post 2026-06-25 START-LABELED: measured interval is [T,T+5m);
the value cannot be used as known at T (look-ahead protection).
"""
import argparse
import csv
import hashlib
import io
import json
import math
from collections import Counter
from datetime import datetime,timedelta,timezone
from pathlib import Path
from statistics import median
from zipfile import ZipFile

from download_binance_um_history import get

ROOT="https://data.binance.vision/data/futures/um"
SYMBOL="SOLUSDT"
FIVE=300
HOUR=3600
DAY=86400

def utc(epoch):
    return datetime.fromtimestamp(epoch,timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def unix(s):
    return int(datetime.fromisoformat(s.replace("Z","+00:00")).timestamp())

def sha_archive(path,max_bytes=14_000_000):
    url=ROOT+"/"+path
    data=get(url,max_size=max_bytes)
    sha=hashlib.sha256(data).hexdigest()
    checksum=get(url+".CHECKSUM",max_size=1000).decode("utf-8-sig").strip()
    wanted=checksum.split()[0].lower()
    if len(wanted)!=64 or any(c not in "0123456789abcdef" for c in wanted) or sha!=wanted:
        raise ValueError("OFFICIAL_SHA256_CHECKSUM_MISMATCH:"+path)
    with ZipFile(io.BytesIO(data)) as archive:
        names=[n for n in archive.namelist() if n.endswith(".csv")]
        if len(names)!=1 or names[0].split("/")[-1] != path.split("/")[-1].replace(".zip",".csv"):
            raise ValueError("UNEXPECTED_ARCHIVE_MEMBER:"+path)
        if archive.getinfo(names[0]).file_size>55_000_000:
            raise ValueError("DECOMPRESSED_ARCHIVE_TOO_LARGE")
        with archive.open(names[0]) as fp:
            rows=list(csv.reader(io.TextIOWrapper(fp,encoding="utf-8-sig")))
    return rows,{"archive":path,"sha256":sha,"csvRows":len(rows)}

def valid_float(val):
    x=float(val)
    if not math.isfinite(x):raise ValueError("Nonfinite data")
    return x

def parse_kline(rows,day,tf):
    secs={"1h":HOUR,"5m":FIVE}[tf]
    start=unix(day+"T00:00:00Z")
    data={}
    bad=Counter()
    seen=set()
    for line in rows:
        if line and line[0].strip().lower().replace("_"," ") in ("open time","opentime"):
            continue
        if len(line)<11:bad["INVALID_COLUMNS"]+=1;continue
        try:
            t=int(line[0])
            t=t//1000000 if t>=10**15 else t//1000
            values=[valid_float(line[j]) for j in (1,2,3,4,5,7,9,10)]
            o,h,l,c,volume,quote,buy,buy_quote=values
            close_raw=int(line[6])
            close_ts=(close_raw//1000000 if close_raw>=10**15 else close_raw//1000)
            if not (start<=t<start+DAY and t%secs==0 and
                    close_ts==t+secs-1 and volume>=0 and quote>=0 and
                    0<=buy<=volume+0.0000001 and buy_quote>=0 and
                    l>0 and l<=min(o,c) and h>=max(o,c)):
                raise ValueError("bad candle")
            if t in seen:bad["DUPLICATE"]+=1;continue
            seen.add(t)
            data[t]={"o":o,"h":h,"l":l,"c":c,"v":volume,"quote":quote,
                     "takerBuyBase":buy,"takerSellBase":volume-buy,
                     "takerBuyQuote":buy_quote,"takerSellQuote":quote-buy_quote}
            if quote-buy_quote<-0.001: bad["TAKER_BUY_QUOTE_EXCEEDS_QUOTE"]+=1
        except (ValueError,TypeError,IndexError):
            bad["MALFORMED_ROW"]+=1
    expected=DAY//secs
    return data,dict(bad),expected

def parse_metrics(rows,day):
    start=unix(day+"T00:00:00Z")
    if not rows or rows[0][:4]!=["create_time","symbol","sum_open_interest","sum_open_interest_value"]:
        raise ValueError("Unexpected metrics column names")
    data={}
    bad=Counter()
    for fields in rows[1:]:
        try:
            if len(fields)<8 or fields[1]!=SYMBOL:raise ValueError("symbol/schema")
            t=unix(fields[0].strip().replace(" ","T")+"Z")
            if not start<=t<start+DAY or t%FIVE:raise ValueError("not on 5-min boundary")
            if t in data:bad["DUPLICATE"]+=1;continue
            oi=valid_float(fields[2]);oi_usdt=valid_float(fields[3])
            if oi<=0 or oi_usdt<=0:bad["NONPOSITIVE_OI"]+=1;continue
            try:
                ratio=valid_float(fields[7]) if fields[7].strip() else None
                if ratio is not None and ratio<0:raise ValueError("invalid ratio")
            except ValueError:
                ratio=None;bad["UNUSABLE_TAKER_RATIO"]+=1
            data[t]={"oi":oi,"oiUSDT":oi_usdt,"takerRatio":ratio,
                     # Binance archive metrics switched to START labels 2026-06-25.
                     # Current value/flow cannot be known at label T.
                     "availableAfterUTC":utc(t+FIVE)}
        except (ValueError,TypeError,IndexError):
            bad["MALFORMED_ROW"]+=1
    return data,dict(bad),DAY//FIVE

def summarize_holes(series,start,secs,count):
    missing=[start+i*secs for i in range(count) if start+i*secs not in series]
    segments=[]
    for t in missing:
        if segments and segments[-1]["toExclusiveEpoch"]==t:
            segments[-1]["toExclusiveEpoch"]+=secs
            segments[-1]["count"]+=1
        else:
            segments.append({"startEpoch":t,"toExclusiveEpoch":t+secs,"count":1})
    return {
        "missingCount":len(missing),"missingGroups":len(segments),
        "largestGapCandles":max((a["count"] for a in segments),default=0),
        "gaps": [{"startUTC":utc(x["startEpoch"]),
                  "endExclusiveUTC":utc(x["toExclusiveEpoch"]),"missing":x["count"]}
                 for x in sorted(segments,key=lambda x:-x["count"])[:8]],
    }

def verify_granularity(h1,m5):
    errors=[]
    missing_sources=0
    for t,h in sorted(h1.items()):
        seq=[m5.get(t+i*FIVE) for i in range(12)]
        if any(row is None for row in seq):
            missing_sources+=1;continue
        sums={field:sum(x[field] for x in seq)
              for field in ("v","quote","takerBuyBase","takerBuyQuote")}
        # Binance archives round 2 decimal places; 12 summed rows may have
        # <=0.12 units/USDT differences in quote volume.
        tolerance={"v":0.15,"quote":0.2,"takerBuyBase":0.15,"takerBuyQuote":0.2}
        max_error=max(abs(sums[key]-h[key])/max(abs(h[key]),1) for key in sums)
        errors.append({"hour":t,"maxRelativeError":max_error,
                       "failedFields":[key for key in sums
                                       if abs(sums[key]-h[key])>tolerance[key]]})
    return {"testedHours":len(errors),
            "hourlyBarsMissing5mInput":missing_sources,
            "mismatchHours":sum(bool(e["failedFields"]) for e in errors),
            "largestRelativeDifference":max((x["maxRelativeError"] for x in errors),default=None),
            "examples":[{"timeUTC":utc(x["hour"]),"fields":x["failedFields"]}
                        for x in errors if x["failedFields"]][:8]}

def parse_monthly_funding(rows):
    if not rows or rows[0][:3]!=["calc_time","funding_interval_hours","last_funding_rate"]:
        raise ValueError("Unexpected Binance monthly funding schema")
    data=[]
    bad=Counter()
    for line in rows[1:]:
        try:
            if len(line)<3:raise ValueError("length")
            milliseconds=int(line[0])
            t=milliseconds//1000
            interval=int(line[1])
            r=valid_float(line[2])
            if not 0<interval<=24 or abs(r)>0.05:
                raise ValueError("implausible funding entry")
            if data and t<=data[-1]["t"]:raise ValueError("unordered or duplicated funding")
            data.append({"t":t,"intervalHours":interval,"rate":r,
                         "closeUTC":utc(t)})
        except (TypeError,ValueError,IndexError):
            bad["INVALID_FUNDING_ROW"]+=1
    return data,dict(bad)

def pct(num,den):
    return round(100*num/den,3) if den else None

def audit(start_date,end_date):
    start=datetime.strptime(start_date,"%Y-%m-%d").replace(tzinfo=timezone.utc)
    end=datetime.strptime(end_date,"%Y-%m-%d").replace(tzinfo=timezone.utc)
    if start>end or (end-start).days>31:
        raise ValueError("Choose 1-32 full UTC days")
    days=[(start+timedelta(days=i)).strftime("%Y-%m-%d") for i in range((end-start).days+1)]
    manifest=[];errors=[];oi={};klines_1h={};klines_5m={}
    invalid_oi=Counter();invalid_1h=Counter();invalid_5m=Counter()
    for day in days:
        for group,label in (("metrics",None),("klines","1h"),("klines","5m")):
            sub="/"+label if label else ""
            suffix="-"+label if label else "-metrics"
            path=f"daily/{group}/{SYMBOL}{sub}/{SYMBOL}{suffix}-{day}.zip"
            try:
                rows,proof=sha_archive(path)
                manifest.append(proof)
                if group=="metrics":
                    parsed,invalid,_=parse_metrics(rows,day)
                    oi.update(parsed);invalid_oi.update(invalid)
                elif label=="1h":
                    parsed,invalid,_=parse_kline(rows,day,label)
                    klines_1h.update(parsed);invalid_1h.update(invalid)
                else:
                    parsed,invalid,_=parse_kline(rows,day,label)
                    klines_5m.update(parsed);invalid_5m.update(invalid)
            except (OSError,RuntimeError,ValueError,IndexError) as e:
                errors.append({"file":path,"error":type(e).__name__+":"+str(e)[:100]})
    funding=None
    funding_source_month=(start-timedelta(days=1)).strftime("%Y-%m")
    # Most recent complete monthly funding archive as of Nov 10, 2026
    prev_month=f"{start.year-1}-12" if start.month==1 else f"{start.year}-{start.month-1:02d}"
    funding_month=prev_month if start.day==1 else (start.replace(day=1)-timedelta(days=1)).strftime("%Y-%m")
    funding_path=f"monthly/fundingRate/{SYMBOL}/{SYMBOL}-fundingRate-{funding_month}.zip"
    try:
        rows,proof=sha_archive(funding_path)
        manifest.append(proof)
        funding,invalid_funding=parse_monthly_funding(rows)
    except (OSError,RuntimeError,ValueError,IndexError) as e:
        errors.append({"file":funding_path,"error":type(e).__name__+":"+str(e)[:100]})
        invalid_funding={}
    begin=int(start.timestamp())
    expected_days=len(days)
    expected_oi=expected_days*288
    expected_h1=expected_days*24
    expected_5m=expected_days*288
    holes_oi=summarize_holes(oi,begin,FIVE,expected_oi)
    holes_1h=summarize_holes(klines_1h,begin,HOUR,expected_h1)
    holes_5m=summarize_holes(klines_5m,begin,FIVE,expected_5m)
    taker_recon=verify_granularity(klines_1h,klines_5m)
    ratios=[]
    for t,r in oi.items():
        candle=klines_5m.get(t)
        if candle and r["takerRatio"] is not None and candle["takerSellBase"]>0:
            calculated=candle["takerBuyBase"]/candle["takerSellBase"]
            ratios.append(abs(calculated-r["takerRatio"]))
    monthly={
        "lastAvailableMonthlyArchive":funding_month if funding else None,
        "records":len(funding) if funding else 0,
        "firstRecordUTC":funding[0]["closeUTC"] if funding else None,
        "lastRecordUTC":funding[-1]["closeUTC"] if funding else None,
        "fundingIntervalsHours":dict(Counter(a["intervalHours"] for a in funding)) if funding else {},
        "invalidRows":invalid_funding,
        "usableForCurrentForwardV7":False,
        "reason":"Completed monthly archive only; no contemporaneous November funding history. Binance REST 451 from GitHub runner.",
    }
    last_oi=max(oi) if oi else None
    return {
        "status":"SOL_USDM_DERIVATIVES_DATA_QUALITY_RESEARCH_ONLY",
        "exchange":"Binance","symbol":SYMBOL,"contract":"USD-M perpetual",
        "dataWindowUTC":{"firstIncluded":start_date,"lastIncluded":end_date,"completeUTCDays":expected_days},
        "source": "official data.binance.vision daily/monthly ZIP and SHA-256 CHECKSUM",
        "sourcePublication":"Daily archives published after UTC day ends; downloaded retrospectively. NOT live market observations.",
        "historyRisks":[
            "Binance REST for live OI/funding returns HTTP 451 from GitHub runner.",
            "Public daily OI metrics after 2026-06-25 use START labels; value cannot be known at create_time until period ends. Explicit +5min delay.",
            "Funding historical monthly October archive cannot be treated as latest November funding.",
            "Trading-significance or predictive efficacy not measured; only data integrity and coverage.",
            "Missing 5min OI samples must NEVER be forward-filled or interpreted as zero OI.",
            "Missing 2026-10-28 SOL klines ZIP is outside study period; prior trade-derived recovery is separate evidence.",
        ],
        "openInterest5m":{
            "expected":expected_oi,"validRecords":len(oi),"coveragePct":pct(len(oi),expected_oi),
            "latestRecordedLabelUTC":utc(last_oi) if last_oi else None,
            "latestSafeAvailabilityUTC":utc(last_oi+FIVE) if last_oi else None,
            "invalid":dict(invalid_oi),"holes":holes_oi,
            "usableAsCurrentV7SignalFilter":False,
        },
        "taker":{
            "hourly":{"expected":expected_h1,"validRecords":len(klines_1h),
                      "coveragePct":pct(len(klines_1h),expected_h1),"invalid":dict(invalid_1h),
                      "holes":holes_1h},
            "fiveMinute":{"expected":expected_5m,"validRecords":len(klines_5m),
                          "coveragePct":pct(len(klines_5m),expected_5m),"invalid":dict(invalid_5m),
                          "holes":holes_5m},
            "hourlyVsTwelve5mConsistency":taker_recon,
            "directTakerBuySell":True,
            "usableAsCurrentV7SignalFilter":False,
            "reason":"Values historical: same-day REST currently blocked; daily archive arrives next day.",
        },
        "metricVs5mTakerRatioValidation":{
            "pairedSamples":len(ratios),
            "medianAbsoluteRatioDifference":round(median(ratios),7) if ratios else None,
            "maxAbsoluteRatioDifference":round(max(ratios),7) if ratios else None,
            "note":"Post-June2026 metric start label T compared to same-period [T,T+5m) Binance taker_buy/(total-taker_buy); evaluation only retrospective.",
        },
        "fundingRate":monthly,
        "archiveErrors":errors,
        "checksumVerifiedPackages":len(manifest),
        "archives":manifest
    }

def render(d):
    oi=d["openInterest5m"];tk=d["taker"];f=d["fundingRate"];r=d["metricVs5mTakerRatioValidation"]
    m=tk["hourlyVsTwelve5mConsistency"]
    lines=[
        "# SOLUSDT Perpetual — OI / Funding / Taker veri kalitesi",
        "",
        "**Dönem (UTC):** "+d["dataWindowUTC"]["firstIncluded"]+" – "+d["dataWindowUTC"]["lastIncluded"],
        "**Sözleşme:** Binance USD-M SOLUSDT (spot değil)",
        "**Kaynak:** Binance resmî arşivleri; ZIP SHA-256 doğrulaması",
        "**Kullanım:** Yalnız veri kalitesi araştırması, işlem sinyali değil",
        "",
        "| Veri | Beklenen | Doğrulanmış | Kapsam |",
        "|---|---:|---:|---:|",
        f"| OI (5m) | {oi['expected']} | {oi['validRecords']} | %{oi['coveragePct']} |",
        f"| Taker 5m OHLCV | {tk['fiveMinute']['expected']} | {tk['fiveMinute']['validRecords']} | %{tk['fiveMinute']['coveragePct']} |",
        f"| Taker 1H OHLCV | {tk['hourly']['expected']} | {tk['hourly']['validRecords']} | %{tk['hourly']['coveragePct']} |",
        "",
        "## OI kayıp veri ve zamanlama",
        f"- Boş 5m dilimleri: {oi['holes']['missingCount']}. Kayıp aralık grubu: {oi['holes']['missingGroups']}.",
        f"- En büyük kesinti: {oi['holes']['largestGapCandles']} adet 5m dilimi.",
        f"- Son OI etiketi: {oi['latestRecordedLabelUTC']}. En erken kullanılabilir kapanış: {oi['latestSafeAvailabilityUTC']}.",
        f"- Geçersiz kayıt türleri: {oi['invalid']}.",
        "- Önemli: 2026-06-25 sonrası Binance metrics create_time başlangıç etiketlidir. T+5m öncesi stratejiye verilirse ileriye bakma hatası olur.",
        "",
        "## Taker hacmi tutarlılığı",
        f"- 1H saatinin 12×5m toplamıyla doğrulandığı saat: {m['testedHours']}.",
        f"- Hacim/toplam quote/taker alış uyuşmazlığı olan saat: {m['mismatchHours']}.",
        f"- 5m verisi eksik olduğu için test edilemeyen 1H: {m['hourlyBarsMissing5mInput']}.",
        f"- Metrikteki taker ratio ve resmî 5m mumlardan eşleşen örnek: {r['pairedSamples']}.",
        f"- Aynı pencere için median ratio mutlak farkı: {r['medianAbsoluteRatioDifference']}.",
        "",
        "## Funding Rate",
        f"- En son bu çalışmada doğrulanan aylık paket: {f['lastAvailableMonthlyArchive']}.",
        f"- Kayıt sayısı: {f['records']}; son funding: {f['lastRecordUTC']}.",
        f"- Interval saat dağılımı: {f['fundingIntervalsHours']}.",
        "- Kasım 2026 güncel funding geçmişi bu kaynak üzerinden doğrulanamadı.",
        "",
        "## Dosya kalitesi",
        f"- SHA256 ile doğrulanan Binance arşiv paketi: {d['checksumVerifiedPackages']}.",
        f"- Arşiv erişim veya içerik hata sayısı: {len(d['archiveErrors'])}.",
        "",
        "## Canlı V7 için karar",
        "Bu arşiv kalite değerlendirmesi **canlı taker/OI/funding filtrelerinin çalıştığını kanıtlamaz**.",
        "Eksik OI için 0 atamak veya ileriye dönük doldurmak yasak.",
        "Arşiv gecikmesi nedeniyle üç veri, yeni API akışı doğrulanana kadar V7'ye otomatik gating olarak eklenmez.",
        "API key/alternatif salt-okunur akış ancak kendi kapanış zamanıyla ve örnek bazında doğrulanır.",
        "",
        "## Sınırlar",
    ]
    lines+=["- "+x for x in d["historyRisks"]]
    lines+=["","### En büyük OI boşlukları",""]
    for gap in oi["holes"]["gaps"]:
        lines.append(f"- {gap['startUTC']} – {gap['endExclusiveUTC']}: {gap['missing']}×5m")
    lines+=[""]
    return "\n".join(lines)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--start",default="2026-11-01")
    p.add_argument("--end",default="2026-11-09")
    p.add_argument("--json-output",required=True)
    p.add_argument("--report-output",required=True)
    args=p.parse_args()
    report=audit(args.start,args.end)
    for output in (args.json_output,args.report_output):
        Path(output).parent.mkdir(parents=True,exist_ok=True)
    Path(args.json_output).write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    Path(args.report_output).write_text(render(report),encoding="utf-8")
    print(json.dumps({
        "OI":{k:v for k,v in report["openInterest5m"].items() if k!="holes"},
        "taker":{k:{"coveragePct":v["coveragePct"],"validRecords":v["validRecords"]}
                 for k,v in report["taker"].items() if k in ("hourly","fiveMinute")},
        "consistency":report["taker"]["hourlyVsTwelve5mConsistency"],
        "ratio":report["metricVs5mTakerRatioValidation"],
        "funding":report["fundingRate"],
        "verifiedArchivePackages":report["checksumVerifiedPackages"],
        "errors":report["archiveErrors"]
    },ensure_ascii=False,indent=2),flush=True)

if __name__=="__main__":
    main()
