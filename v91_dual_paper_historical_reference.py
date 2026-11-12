#!/usr/bin/env python3
"""All available frozen V7 1H/4H/Daily historical candles: separate R-equity books.

Read the already completed FULL sequential replay from the frozen 2024-10
through 2026-09 archive. Do NOT call old outcomes forward/paper executions.
The V9.1 max4h rule was developed with knowledge of these historical trades.
Inputs exclude independent ETH two-year archive. No actual fills or orders.
"""
import argparse
import json
import math
from pathlib import Path

from v91_dual_paper_accounts import STARTER
from v7_forward_observer import epoch

MODE="V7_V91_ALL_AVAILABLE_HISTORICAL_CANDLE_REPLAY_VIRTUAL_R_EQUITY_NOT_FORWARD"
VARIANTS=("V7_ORIGINAL","V91_RETEST_MAX4H")
SYMBOLS=("BTCUSDT","SOLUSDT")
HOUR=3600

def history_paper_book(config, replay):
    if (config.get("mode")!=STARTER
        or config.get("noLiveOrders") is not True
        or config.get("noNewNotifications") is not True
        or config.get("noRetroactiveExecution") is not True
        or config.get("userExplicitlyRequested10PctRiskOnlyInVirtualPaper") is not True):
        raise ValueError("ARCHIVED_PAPER_UNSAFE_RISK_CONFIG")
    if (replay.get("status")!="V91_FULL_CHRONOLOGICAL_RETEST_ABLATION_PAPER_ONLY"
        or replay.get("source")!="original V7 Binance SHA-verified frozen archive"
        or replay.get("allVariantsReplayedIndependentlyChronologically") is not True
        or replay.get("originalV7BaselineVerifiedAgainstPublishedQualityBacktest") is not True
        or replay.get("historicalPeriodPreviouslyInspected") is not True
        or replay.get("max4hRuleSuggestedAfterSeeingPastOutcomes") is not True
        or replay.get("NOTIndependentOutOfSampleOrProspective") is not True
        or replay.get("noBrokerOrders") is not True
        or replay.get("noUserNotifications") is not True
        or replay.get("baseCostBpsPerSide")!=9
        or replay.get("stressCostBpsPerSide")!=25
        or replay.get("historyStartUTC")!=config.get("historicalReferenceStartUTC")
        or replay.get("historyEndExclusiveUTC")!=config.get("historicalReferenceEndExclusiveUTC")):
        raise ValueError("ARCHIVED_PAPER_REPLAY_NOT_VERIFIED_FROZEN_FULL_ARCHIVE")
    start=epoch(replay["historyStartUTC"]);end=epoch(replay["historyEndExclusiveUTC"])
    equity=float(config["initialVirtualCapitalUSDTPerAccount"])
    at_risk=float(config["fixedPaperRiskUSDTPerEligibleTrade"])
    if not (equity>0 and 0<at_risk<=equity*.10):
        raise ValueError("ARCHIVED_PAPER_CAPITAL_RISK_INVALID")
    items=replay["tradesAudit"]
    if not isinstance(items,list) or not items:
        raise ValueError("ARCHIVED_PAPER_NO_VERIFIED_TRADE_AUDIT")
    out={}
    for variant in VARIANTS:
        relevant=[]
        for row in items:
            if row["variant"]!=variant:
                continue
            if row["symbol"] not in SYMBOLS:
                raise ValueError("ARCHIVED_PAPER_UNEXPECTED_SYMBOL")
            a=epoch(row["watchUTC"]);ret=epoch(row["retestUTC"])
            ent=epoch(row["entryUTC"]);ext=epoch(row["exitUTC"])
            maxh=6 if variant=="V7_ORIGINAL" else 4
            if not (start<=ent<end and start<=ext<=end and a<ret<=ent<ext
                    and 1<=int(row["retestDelayHours"])<=maxh):
                raise ValueError("ARCHIVED_PAPER_TIME_OR_RETEST_RULE")
            if row["side"] not in ("bullish","bearish"):
                raise ValueError("ARCHIVED_PAPER_TRADE_SIDE_INVALID")
            pnl=float(row["netR9bps"]);pnl_stress=float(row["netR25bps"])
            entry=float(row["entry"]);stop=float(row["stop"])
            if (not all(map(math.isfinite,(pnl,pnl_stress,entry,stop)))
                or entry<=0 or stop<=0 or entry==stop):
                raise ValueError("ARCHIVED_PAPER_TRADE_R_OR_STOP_INVALID")
            if variant=="V7_ORIGINAL" and ret-a>6*HOUR:
                raise ValueError("ARCHIVED_PAPER_V7_RETEST_TOO_LATE")
            if variant=="V91_RETEST_MAX4H" and ret-a>4*HOUR:
                raise ValueError("ARCHIVED_PAPER_V91_RETEST_TOO_LATE")
            x=dict(row)
            x["paperRiskUSD"]=at_risk
            x["paperPnlUSDT"]=round(at_risk*pnl,6)
            x["paperStressPnlUSDT"]=round(at_risk*pnl_stress,6)
            x["illustrativeQuantityFor100USDTStopRisk"]=round(at_risk/abs(entry-stop),8)
            x["notionalRequiredUSDTNoLeverageOrMarginAssumed"]=round(
                entry*at_risk/abs(entry-stop),4)
            x["notAnExecutedTrade"]=True
            relevant.append(x)
        relevant.sort(key=lambda v:(v["exitUTC"],v["entryUTC"],v["symbol"]))
        if len({(z["symbol"],z["entryUTC"],z["exitUTC"],z["side"]) for z in relevant})!=len(relevant):
            raise ValueError("ARCHIVED_PAPER_DUPLICATE_TRADE")
        balance=equity;peak=equity;maxdd=0.0;curve=[]
        for t in relevant:
            balance+=t["paperPnlUSDT"]
            peak=max(peak,balance)
            maxdd=max(maxdd,peak-balance)
            curve.append({"exitUTC":t["exitUTC"],"asset":t["symbol"],
                          "netR":t["netR9bps"],"virtualBalanceUSDT":round(balance,6)})
        per={}
        for coin in SYMBOLS:
            m=[t for t in relevant if t["symbol"]==coin]
            reference=replay["results"][coin][variant]
            rn=sum(float(t["netR9bps"]) for t in m)
            sn=sum(float(t["netR25bps"]) for t in m)
            if (len(m)!=reference["trades"]
                or sum(float(t["netR9bps"])>0 for t in m)!=reference["wins"]
                or abs(rn-reference["totalNetR9bpsSide"])>0.0002
                or abs(sn-reference["totalNetR25bpsSide"])>0.0002):
                raise ValueError("ARCHIVED_PAPER_TRADE_LEDGER_SUM_DIVERGES_"+coin+"_"+variant)
            per[coin]={"trades":len(m),"wins":reference["wins"],
                       "netR9Bps":round(rn,6),
                       "netR25BpsStress":round(sn,6),
                       "simulatedPnlUSDT":round(at_risk*rn,4),
                       "simulatedPnlStressUSDT":round(at_risk*sn,4)}
        risk_events=[]
        for tr in relevant:
            risk_events.append((epoch(tr["entryUTC"]),1))
            risk_events.append((epoch(tr["exitUTC"]),-1))
        active=0;maxsim=0
        for _,change in sorted(risk_events,key=lambda a:(a[0],a[1])):
            active+=change;maxsim=max(active,maxsim)
            if active<0:
                raise ValueError("ARCHIVED_PAPER_CONCURRENT_RISK_TIMELINE_INVALID")
        if active!=0:raise ValueError("ARCHIVED_PAPER_UNRESOLVED_OPEN_TRADE")
        totalR=sum(t["netR9bps"] for t in relevant)
        stressedR=sum(t["netR25bps"] for t in relevant)
        if abs(balance-(equity+at_risk*totalR))>0.001:
            raise ValueError("ARCHIVED_PAPER_EQUITY_RECONCILIATION_FAILED")
        out[variant]={
            "initialVirtualUSDT":equity,"fixedTargetRiskPerTradeUSDT":at_risk,
            "riskPctOfInitialBalance":round(100*at_risk/equity,2),
            "assets":per,"totalClosedHistoricalReplayedTrades":len(relevant),
            "wins":sum(t["netR9bps"]>0 for t in relevant),
            "netR9Bps":round(totalR,6),"stressNetR25Bps":round(stressedR,6),
            "virtualPnLUSDT":round(at_risk*totalR,4),
            "virtualEndingBalanceUSDT":round(balance,4),
            "stressVirtualEndingBalanceUSDT":round(equity+at_risk*stressedR,4),
            "exitCloseToCloseMaxEquityDrawdownUSDT":round(maxdd,4),
            "maximumConcurrentHistoricalSimulatedTrades":maxsim,
            "maximumOpenTargetRiskUSDWithoutASeparateAccountWideCap":round(maxsim*at_risk,4),
            "replayedClosedTrades":relevant,"virtualEquityCurveAtExits":curve,
            "zeroRealOrders":True}
    return {
        "mode":MODE,"sourceArchiveStartUTC":replay["historyStartUTC"],
        "sourceArchiveEndExclusiveUTC":replay["historyEndExclusiveUTC"],
        "fullSequentialOriginalArchived1H4HDailyReplayAlreadyPerformed":True,
        "historicalTradesSelectedFromFullReplayNotJustNightCandleColors":True,
        "ETHHistoricalTwoYearArchiveNotAvailableForEqualComparison":True,
        "assetsWithComparableArchivedHistory":list(SYMBOLS),
        "accounts":out,
        "referenceResearchWasDesignedAfterViewingTheseHistoricalOutcomes":True,
        "resultsNOTIndependentlyValidatedProspectively":True,
        "executionAtInstantNextOpenUnprovenAndGenerallyNotAchievableFromDelayedGitPublication":True,
        "risk100USDIsTargetAtModeledStopNotGuaranteedWorstCase":True,
        "tenPercentRiskIsAggressiveAndCouldRapidlyDepleteCapital":True,
        "noAccountWideConcurrentRiskCapEnforcedInSourceTradeReplay":True,
        "fees9BpsPerSideStress25BpsPerSide":True,
        "fundingLiquidationsTrueBrokerFillsAndSpreadNotFullyModeled":True,
        "notForwardAccountBalances":True,
        "neverTreatRetrospectiveTradeAsOrderPlacedNow":True,
        "noBrokerOrders":True,"noNotifications":True,
        "V7V91SignalRulesUntouched":True}

def to_markdown(out):
    lines=[
       "# V7 vs V9.1 — bütün mevcut arşiv mumlarında ayrı 1.000 USDT sanal geçmiş test",
       "",
       "**TARİHSEL SENARYO, GERÇEK VEYA İLERİ DÖNÜK PAPER İŞLEM DEĞİLDİR.**",
       "Arşiv: "+out["sourceArchiveStartUTC"]+" – "+out["sourceArchiveEndExclusiveUTC"]+" (son gün hariç).",
       "V7 ve V9.1 tam kronolojik 1H/4H/Daily mum simülatörüyle aynı dönem üzerinden karşılaştırılmıştır.",
       "V9.1'in 4H süresi, bu arşivdeki sonuçlar incelendikten sonra seçildiği için veriler bağımsız test değildir.",
       "Her sanal hesap 1.000 USDT; stop mesafesine göre hedef risk 100 USDT/işlem, sabit, bileşik değil.",
       "",
       "| Model | İşlem | Kazanç | Net R (9 bp/yan) | Sanal PnL | Bakiye | 25 bp/yan stres bakiyesi |",
       "|---|---:|---:|---:|---:|---:|---:|"]
    for v in VARIANTS:
        a=out["accounts"][v]
        lines.append("| {} | {} | {} | {:.4f} | {:.2f} | {:.2f} | {:.2f} |".format(
            v,a["totalClosedHistoricalReplayedTrades"],a["wins"],
            a["netR9Bps"],a["virtualPnLUSDT"],
            a["virtualEndingBalanceUSDT"],a["stressVirtualEndingBalanceUSDT"]))
    lines+=["","**Sınırlamalar:** ETH'nin eşdeğer 2 yıllık bağımsız arşivi yok; arşiv sonucu BTC/SOL ile sınırlı. ",
        "Aynı anda birden çok sembolde pozisyon olabiliyor; toplam hesap riski 100 USDT'yi aşabilir. " +
        "Gerçekçi emir geçikmesi, fonlama, tasfiye, slipaj ve gerçek fill kanıtı yok. %10 risk agresiftir.",
        "İleriye dönük gerçek paper hesapları **ayrı bir defterdedir**; bu bakiye onlara aktarılmaz.",
        ""]
    return "\n".join(lines)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--config",default="forward/v91_dual_paper_accounts/config.json")
    p.add_argument("--replay",default="forward/v91_retest_full_replay/compare.json")
    p.add_argument("--out",default="forward/v91_dual_paper_accounts/historical_reference.json")
    p.add_argument("--md",default="forward/v91_dual_paper_accounts/historical_reference.md")
    a=p.parse_args()
    c=json.loads(Path(a.config).read_text())
    d=json.loads(Path(a.replay).read_text())
    output=history_paper_book(c,d)
    Path(a.out).parent.mkdir(parents=True,exist_ok=True)
    Path(a.out).write_text(json.dumps(output,indent=2,ensure_ascii=False)+"\n")
    Path(a.md).write_text(to_markdown(output)+"\n")
    print("V7_V91_ARCHIVED_ALL_CANDLES_PAPER_SIMULATION_NOT_FORWARD",
          json.dumps({v:{"trades":o["totalClosedHistoricalReplayedTrades"],
                         "balance":o["virtualEndingBalanceUSDT"]}
                      for v,o in output["accounts"].items()}),
          flush=True)

if __name__=="__main__":main()
