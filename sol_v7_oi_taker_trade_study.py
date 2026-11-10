#!/usr/bin/env python3
"""SOL historical V7 trades: point-in-time OI/taker context matched to frozen paper results.

Only research diagnostics; immutable V7 backtest artifact supplied as input.
No optimization/tuning/forward deployment, portfolio assumptions or orders.
"""
import argparse
import concurrent.futures
import json
import math
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import mean,median

from sol_derivatives_quality_audit import (
    SYMBOL, HOUR, FIVE,DAY,sha_archive,parse_metrics,parse_kline,
    parse_monthly_funding,unix,utc)

PAIR="SOLUSDT_PERP.A"

def day_for(t):
    return datetime.fromtimestamp(t,timezone.utc).strftime("%Y-%m-%d")

def month_for(t):
    return day_for(t)[:7]

def past_day(day):
    return (datetime.strptime(day,"%Y-%m-%d")-timedelta(days=1)).strftime("%Y-%m-%d")

def load_trades(source):
    data=json.loads(Path(source).read_text(encoding="utf-8"))
    if data.get("mode")!="V7_HISTORICAL_PAPER_DIAGNOSTIC_ONLY":
        raise ValueError("Must use original immutable V7 historical paper diagnostic")
    variants=data["results"][PAIR]["paperTradesByVariant"]
    required={"baseline_V4","V7_signal_gate","V7_signal_and_retest_gate"}
    if not required.issubset(variants):raise ValueError("Missing original research variants")
    return variants,data["asOfUTC"]


def source_paths(trades):
    # A prior date is needed for the first 4H OI change of early-day signals.
    timestamps={int(t["watchKnownUTC"]) for records in trades.values() for t in records}
    days={day_for(t) for t in timestamps}
    days.update(past_day(day_for(t)) for t in timestamps)
    monthset={month_for(t) for t in timestamps}
    paths=[]
    for day in sorted(days):
        paths.extend([
            ("metrics",day,f"daily/metrics/{SYMBOL}/{SYMBOL}-metrics-{day}.zip"),
            ("1h",day,f"daily/klines/{SYMBOL}/1h/{SYMBOL}-1h-{day}.zip")
        ])
    for month in sorted(monthset):
        paths.append(("funding",month,f"monthly/fundingRate/{SYMBOL}/{SYMBOL}-fundingRate-{month}.zip"))
    return paths


def gather(trades,workers=8):
    requests=source_paths(trades)
    oi={};hourly={};funding={};verified=[];failures=[]
    def one(req):
        typ,date,path=req
        try:
            rows,proof=sha_archive(path)
            if typ=="metrics":
                data,invalid,_=parse_metrics(rows,date)
            elif typ=="1h":
                data,invalid,_=parse_kline(rows,date,"1h")
            else:
                data,invalid=parse_monthly_funding(rows)
            if invalid and typ!="metrics":
                raise ValueError("Invalid archive rows for "+typ+":"+str(invalid))
            return (typ,date,data,invalid,proof,None)
        except (RuntimeError,ValueError,OSError,IndexError) as e:
            return (typ,date,None,{},None,type(e).__name__+":"+str(e)[:140])
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        for typ,date,data,invalid,proof,error in pool.map(one,requests):
            if error:
                failures.append({"type":typ,"dayOrMonth":date,"reason":error})
                continue
            verified.append({**proof,"rowWarnings":invalid})
            if typ=="metrics":
                for t,row in data.items():
                    if t in oi:raise ValueError("Duplicate OI across official archives")
                    oi[t]=row
            elif typ=="1h":
                for t,row in data.items():
                    if t in hourly:raise ValueError("Duplicate 1h across official archives")
                    hourly[t]=row
            else:
                funding[date]=data
    return oi,hourly,funding,verified,failures


def feature_at_known_close(t,side,oi,hourly,funding):
    if t%HOUR:raise ValueError("Signal time is not closed 1H UTC")
    row=hourly.get(t-HOUR)
    latest_oi=oi.get(t-FIVE)
    past1=oi.get(t-HOUR-FIVE)
    past4=oi.get(t-4*HOUR-FIVE)
    result={
        "signalCloseUTC":utc(t),
        "dataAvailability":"verified official archive, downloaded AFTER event; not contemporaneous feed",
        "OI5mAsOfLabelUTC":utc(t-FIVE),
        "OI5mAvailableAfterUTC":latest_oi["availableAfterUTC"] if latest_oi else None,
        "oi1hPct":round((latest_oi["oi"]/past1["oi"]-1)*100,5)
           if latest_oi and past1 else None,
        "oi4hPct":round((latest_oi["oi"]/past4["oi"]-1)*100,5)
           if latest_oi and past4 else None,
        "oiNotional1hPct":round((latest_oi["oiUSDT"]/past1["oiUSDT"]-1)*100,5)
           if latest_oi and past1 else None,
        "oiCoverageLast4h":sum(k in oi for k in (t-FIVE,t-HOUR-FIVE,t-4*HOUR-FIVE)),
        "takerBuyShare1h":round(row["takerBuyBase"]/row["v"],6)
           if row and row["v"]>0 else None,
        "takerSignedPressure1h":round(
             (1-2*row["takerBuyBase"]/row["v"]) if side=="bearish"
             else (2*row["takerBuyBase"]/row["v"]-1),6)
           if row and row["v"]>0 else None,
        "takerSellBase1h":row["takerSellBase"] if row else None,
        "takerBuyBase1h":row["takerBuyBase"] if row else None,
        "taker1hClosedAvailableAtUTC":utc(t) if row else None,
        "lastKnownFundingRate":None,
        "lastKnownFundingSettlementUTC":None,
        "fundingAgeHours":None,
    }
    # Funding settlement must have occurred at least one minute before BOS
    # for a conservative public-availability guard (not proof of actual publication).
    month=month_for(t)
    recs=funding.get(month,[])
    candidates=[f for f in recs if f["t"]+60<=t]
    if candidates:
        last=candidates[-1]
        age=(t-last["t"])/3600
        if age<=24:
            result["lastKnownFundingRate"]=last["rate"]
            result["lastKnownFundingSettlementUTC"]=last["closeUTC"]
            result["fundingAgeHours"]=round(age,3)
    return result


def label_trade(trade):
    r=float(trade["netRIllustrative"])
    if not math.isfinite(r):raise ValueError("Bad frozen paper R")
    return "POSITIVE_PAPER" if r>0 else "NEGATIVE_OR_FLAT_PAPER"


def summarize(rows):
    metrics=("oi1hPct","oi4hPct","oiNotional1hPct",
             "takerBuyShare1h","takerSignedPressure1h","lastKnownFundingRate")
    output={"trades":len(rows),"positive":sum(x["label"]=="POSITIVE_PAPER" for x in rows),
            "negativeOrFlat":sum(x["label"]=="NEGATIVE_OR_FLAT_PAPER" for x in rows)}
    for field in metrics:
        valid=[x["features"][field] for x in rows if x["features"][field] is not None]
        output[field]={
            "availableN":len(valid),
            "missingN":len(rows)-len(valid),
            "median":round(median(valid),6) if valid else None,
            "mean":round(mean(valid),6) if valid else None,
            "min":round(min(valid),6) if valid else None,
            "max":round(max(valid),6) if valid else None,
        }
    output["oiRisingAtSignal1hN"]=sum(x["features"]["oi1hPct"]>0
        for x in rows if x["features"]["oi1hPct"] is not None)
    output["takerPressureAlongSignalN"]=sum(x["features"]["takerSignedPressure1h"]>0
        for x in rows if x["features"]["takerSignedPressure1h"] is not None)
    return output


def matched_rows(variants,oi,hourly,funding):
    results={}
    for variant,records in variants.items():
        rows=[]
        for tr in records:
            t=int(tr["watchKnownUTC"])
            if int(tr["entryOpenUTC"])<t or int(tr["exitKnownUTC"])<int(tr["entryOpenUTC"]):
                raise ValueError("Original trade chronology invalid")
            rows.append({
                "watchKnownUTC":t,
                "watchUTC":utc(t),
                "entryUTC":utc(int(tr["entryOpenUTC"])),
                "exitUTC":utc(int(tr["exitKnownUTC"])),
                "side":tr["side"],
                "label":label_trade(tr),
                "netRIllustrative":round(tr["netRIllustrative"],6),
                "features":feature_at_known_close(t,tr["side"],oi,hourly,funding),
                "tradeIsOriginalFrozenBacktest":True,
            })
        results[variant]={
            "all":summarize(rows),
            "positive":summarize([r for r in rows if r["label"]=="POSITIVE_PAPER"]),
            "negativeOrFlat":summarize([r for r in rows if r["label"]!="POSITIVE_PAPER"]),
            "trades":rows
        }
    return results


def read_forward(filepath,oi,hourly,funding):
    if not filepath:return None
    r=json.loads(Path(filepath).read_text(encoding="utf-8"))
    if r.get("mode")!="V7_REJECTED_BOS_PAPER_COUNTERFACTUAL_STUDY" and not r.get("candidates"):
        raise ValueError("Unexpected forensic source")
    rows=[]
    for c in r["candidates"]:
        if c["pair"]!=PAIR:continue
        t=int(c["bosCloseEpoch"])
        cf=c["counterfactual"]
        signal={
            "watchUTC":utc(t),"side":c["side"],
            "acceptedByV4":c["acceptedByV4"],
            "acceptedByV7":c["acceptedByV7"],
            "outcome":"CENSORED_NO_ACTIONABLE_ENTRY",
            "netRIllustrative":None,
            "features":feature_at_known_close(t,c["side"],oi,hourly,funding)
        }
        if cf.get("status")=="CLOSED_COUNTERFACTUAL_PAPER":
            signal["outcome"]="POSITIVE_PAPER" if cf["assumedNetR"]>0 else "NEGATIVE_OR_FLAT_PAPER"
            signal["netRIllustrative"]=cf["assumedNetR"]
        rows.append(signal)
    return {"mode":"FORWARD_BOS_DIAGNOSTIC_SEPARATE_NOT_HISTORICAL_REPLAY",
            "events":rows,"eventsCount":len(rows),
            "acceptedV7ClosedPaper":sum(x["acceptedByV7"] and x["netRIllustrative"] is not None for x in rows)}


def report_markdown(j):
    lines=[
        "# SOL — OI ve taker basıncı / V7 paper işlem sonuçları",
        "",
        "**Çalışma:** Tarihsel V7 paper trades + 1–9 Kasım contemporaneous forward BOS kayıtları ayrı.",
        "**Kaynak:** Geçmiş V7 işlem artifact'i sabit; Binance resmî Futures arşivleri SHA256 doğrulandı.",
        "**Uyarı:** Veriler SONRADAN arşivden edinildi. Sinyal kapanışını aşan OHLCV/OI kullanılmadı; bu canlı kanıt değildir.",
        "",
        "## Orijinal tarihsel V7 (BOS kalite filtresi)",
        "",
        "| Outcome | Paper trade | OI 1h medyan değişim | Taker sinyal yönü 1H medyan baskı | Funding elde |",
        "|---|---:|---:|---:|---:|",
    ]
    v7=j["historical"]["V7_signal_gate"]
    for name,grp in (("Kazanan",v7["positive"]),("Kayıplı/başa baş",v7["negativeOrFlat"])):
        oi=grp["oi1hPct"];tak=grp["takerSignedPressure1h"]
        o=f"{oi['median']:+.3f}%" if oi["median"] is not None else "N/A"
        t=f"{tak['median']:+.4f}" if tak["median"] is not None else "N/A"
        lines.append(f"| {name} | {grp['trades']} | {o} (n={oi['availableN']}) | {t} (n={tak['availableN']}) | {grp['lastKnownFundingRate']['availableN']} |")
    lines+=["",
            "**Veri tamlığı:** Tarihsel 14 V7 paper işleminin kaçında OI/taker/funding var?",
            "",
            "| Alan | Elde | Eksik |",
            "|---|---:|---:|",
        ]
    for field in ("oi1hPct","oi4hPct","takerSignedPressure1h","lastKnownFundingRate"):
        met=v7["all"][field]
        lines.append(f"| {field} | {met['availableN']} | {met['missingN']} |")
    lines+=["", "## Tüm V4 baseline (ayrı örnek, bağımsız ek işlem değil)",
            f"- V4 paper işlemler: {j['historical']['baseline_V4']['all']['trades']}; aynı arşivden, V7 ile çakışan işlemler ayrıca sayılmaz.",
            "",
            "## İleri gözlenen SOL BOS (sıfır/tek trade ayrımı)",
            "",
        ]
    forward=j.get("forward")
    if forward:
        for e in forward["events"]:
            x=e["features"]
            oi=x["oi1hPct"];tak=x["takerSignedPressure1h"]
            lines.append("- "+e["watchUTC"]+" "+e["side"]+
                         f" | V7 kabul={e['acceptedByV7']} | {e['outcome']} | "
                         f"netR={e['netRIllustrative']} | OI1H={oi} % | yönlü taker={tak}")
    lines+=["",
            "## Karar",
            "- Bu tablo *ilişki betimler*; sinyal kazancını artıran yeni OI/taker eşiği ispatlamaz.",
            "- 14 tarihsel SOL V7 paper işlem istatistiksel olarak çok küçük; aynı geçmiş üzerinde eşik seçilmez.",
            "- OI 5m gösterge etiketi T, ancak ancak T+5m itibarıyla erişilebilir sayıldı.",
            "- OI/funding/taker için aynı saat piyasada gerçekten erişilebilen veri kaynağı henüz yok; tarihsel ZIP ertesi gün oluşur.",
            "- Funding yayın zamanı ayrıca bilinmez; en az 1 dakika koruma kullanılır.",
            "- Gerçek emir, broker bağlantısı, ana V7 eşikleri ve BTC/SOL üretim sistemi değiştirilmedi.",
            "- Finansman ve gerçek fill maliyetleri historical paper işlem R sonucuna dahil değildir.",
            "",
            "## Doğrulama",
            f"- SHA256 verified paketler: {j['archivesVerified']}. Arşiv erişim hatası: {len(j['archiveErrors'])}.",
            "- Hatalar ve tüm işlem bazlı özellikler JSON raporunda. Sonuçlar yalnız deneysel araştırmadır.",
            ""
    ]
    return "\n".join(lines)


def main():
    a=argparse.ArgumentParser()
    a.add_argument("--v7-report",required=True)
    a.add_argument("--forward-forensic",default=None)
    a.add_argument("--output",required=True)
    a.add_argument("--markdown",required=True)
    a.add_argument("--workers",type=int,default=8)
    args=a.parse_args()
    if not 1<=args.workers<=10:raise ValueError("Workers must be <=10")
    variants,asof=load_trades(args.v7_report)
    oi,hourly,funding,verified,errors=gather(variants,workers=args.workers)
    historical=matched_rows(variants,oi,hourly,funding)
    forward=None
    if args.forward_forensic:
        forward=read_forward(args.forward_forensic,oi,hourly,funding)
    # Forward Nov7 is not in earlier historical paper artifact. Fetch its
    # corresponding OI/taker archive as separate addition when needed.
    result={
        "mode":"SOL_V7_OI_TAKER_HISTORICAL_PAPER_ASSOCIATION_NOT_TRADING_SYSTEM",
        "historicalArtifactAsOf":asof,
        "sourceDescription":"Binance USD-M SOLUSDT official ZIP and checksum (downloaded after signal)",
        "timestampMethod":"OI at T uses label T-5m (period ends T); 1H taker at [T-1h,T); 1H OI change against label T-65m",
        "historical":historical,
        "forward":forward,
        "archivesVerified":len(verified),
        "archiveErrors":errors,
        "sourceProofs":verified,
        "noBrokerOrders":True,
        "dataNotRealtime":True,
        "limitation":"Descriptive on inspected tiny sample. No fixed OI or taker strategy gates implemented; no claim of predictive edge.",
    }
    for path,body in ((args.output,json.dumps(result,ensure_ascii=False,indent=2)+"\n"),
                      (args.markdown,report_markdown(result))):
        Path(path).parent.mkdir(parents=True,exist_ok=True)
        Path(path).write_text(body,encoding="utf-8")
    report=historical["V7_signal_gate"]
    print(json.dumps({
        "historicalV7Trades":report["all"]["trades"],
        "positive":report["positive"]["trades"],
        "negative":report["negativeOrFlat"]["trades"],
        "oi":{n:report[n]["oi1hPct"] for n in ("positive","negativeOrFlat")},
        "taker":{n:report[n]["takerSignedPressure1h"] for n in ("positive","negativeOrFlat")},
        "fundingN":report["all"]["lastKnownFundingRate"]["availableN"],
        "forward":forward,
        "archiveFilesVerified":len(verified),
        "archiveErrorCount":len(errors),
    },ensure_ascii=False,indent=2),flush=True)


if __name__=="__main__":
    main()
