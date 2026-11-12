#!/usr/bin/env python3
"""Two independent V7 vs V9.1 VIRTUAL portfolios, post-request and paper only.

ONLY V9.1 prospective hourly snapshots that independently matched immutable V7
are accepted. Reuse each strategy's evidence-gated trade ledger. No attempt to
invent past orders, trade when BOS/retest is absent, infer fills or send alerts.
No changes to source strategies or broker/production systems.
"""
import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path

from v7_forward_observer import epoch, iso
from v91_prospective_retest import MODE as BTC_SOL_MODE, path_at as source_path
from v91_eth_prospective_retest import MODE as ETH_MODE

STARTER="V7_VS_V91_PROSPECTIVE_SEPARATE_PAPER_ACCOUNTS"
NAMES=("V7_ORIGINAL","V91_RETEST_MAX4H")
BTC_SOL={"BTCUSDT":"originalV7","SOLUSDT":"originalV7"}
ETH_FIELD={"ETHUSDT":"originalV7"}

def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))

def latest_hour_records(path, expected_mode, *, first_utc, asset_refs):
    base=Path(path)
    result={}
    if not base.is_dir():
        return result
    for file in sorted(base.glob("*.json")):
        j=load_json(file)
        target=epoch(j["targetClosed1HUTC"])
        if file!=source_path(base,target):
            raise ValueError("PORTFOLIO_NONCANONICAL_SOURCE_FILENAME")
        if target<first_utc:
            continue
        if target in result:
            raise ValueError("PORTFOLIO_DUPLICATE_SOURCE_HOUR")
        captured=epoch(j["capturedAtUTC"])
        # The sealed BTC/SOL V9.1 schema calls this noNotifications; the
        # separate ETH V9.1 schema calls it noUserNotifications. Validate
        # the source-specific contract instead of rejecting valid BTC/SOL
        # snapshots or accepting a missing notification-safety assertion.
        if expected_mode==BTC_SOL_MODE:
            notifications_disabled=(j.get("noNotifications") is True)
        elif expected_mode==ETH_MODE:
            notifications_disabled=(j.get("noUserNotifications") is True)
        else:
            raise ValueError("PORTFOLIO_UNKNOWN_PROSPECTIVE_SOURCE_MODE")
        if (j.get("mode")!=expected_mode or
            captured<target or captured>=target+3600 or
            j.get("noBrokerOrders") is not True or
            not notifications_disabled):
            raise ValueError("PORTFOLIO_UNVERIFIED_PROSPECTIVE_SOURCE")
        if expected_mode==BTC_SOL_MODE:
            if (j.get("V7SnapshotAndIndependentRecomputeExactMatch") is not True or
                j.get("sourceVerifiedSameHour") is not True or
                set(j.get("assets",{}))!={"BTCUSDT","SOLUSDT"}):
                raise ValueError("PORTFOLIO_BTC_SOL_V7_PARITY_UNVERIFIED")
        else:
            if (j.get("verifiedSourceAndExactV7Replay") is not True or
                j.get("symbol")!="ETHUSDT"):
                raise ValueError("PORTFOLIO_ETH_V7_PARITY_UNVERIFIED")
        result[target]=j
    return result

def signal_state(records, coin, model):
    if not records:
        return {"status":"NO_ELIGIBLE_CAPTURE_AFTER_START","lastClosedUTC":None,
                "newBOSWatches":0,"retestsPending":0,
                "hypotheticalOpenPositions":0,"realOrders":0}
    last=max(records)
    doc=records[last]
    if coin=="ETHUSDT":
        value=doc["originalV7" if model=="V7_ORIGINAL" else "max4hRetest"]
    else:
        value=doc["assets"][coin]["originalV7" if model=="V7_ORIGINAL" else "max4hRetest"]
    state=value["currentPaperState"]
    if not set(("activeBOSWatch","pendingNextOpenPaperEntry","openHypotheticalPosition")).issubset(state):
        raise ValueError("PORTFOLIO_MISSING_ORIGINAL_SIGNAL_STATE")
    return {
      "status":("OPEN_PAPER_POSITION_NOT_PROVEN_EXECUTABLE"
                if state["openHypotheticalPosition"] is not None else
                "RETEST_PENDING_UNEXECUTED"
                if state["pendingNextOpenPaperEntry"] is not None else
                "BOS_WATCH_WAITING_RETEST"
                if state["activeBOSWatch"] is not None else "FLAT_NO_CONFIRMED_TRADE"),
      "lastClosedUTC":iso(last),
      "newBOSWatches":len(value["newWatchAtThisClose"]),
      "retestsPending":int(state["pendingNextOpenPaperEntry"] is not None),
      "hypotheticalOpenPositions":int(state["openHypotheticalPosition"] is not None),
      "realOrders":0
    }

def verified_ledger(score, records, coin, *, first_utc, start_utc):
    if not records:
        return {k:[] for k in NAMES}
    if (score.get("noBrokerOrders") is not True or
        score.get("realTimeExecutableEntryCountProven")!=0 and
        score.get("realTimeExecutableEntryCountProven") is not None):
        raise ValueError("PORTFOLIO_SOURCE_LEDGER_NOT_PAPER")
    if coin=="ETHUSDT":
        if (score.get("mode")!="V91_ETH_PROSPECTIVE_PAPER_SCOREBOARD"
            or score.get("noNotifications") is not True
            or score.get("noHistoricalBackfill") is not True):
            raise ValueError("PORTFOLIO_UNVERIFIED_ETH_LEDGER")
        raw=score["tradeLedger"]
    else:
        if (score.get("mode")!="V91_PROSPECTIVE_CAUSAL_PAPER_SCOREBOARD"
            or score.get("noNotifications") is not True
            or score.get("noBackfilledOrPostSelectedTrades") is not True
            or score.get("V7SnapshotAndIndependentRecomputeExactMatch") is False):
            raise ValueError("PORTFOLIO_UNVERIFIED_BTC_SOL_LEDGER")
        raw=score["tradeLedger"][coin]
    result={}
    for model in NAMES:
        out=[];seen=set()
        for t in raw[model]:
            entry=epoch(t["entryUTC"]);end=epoch(t["exitUTC"])
            if entry<=start_utc or entry<first_utc or end<entry+3600:
                continue
            if end not in records:
                raise ValueError("PORTFOLIO_EXIT_WITHOUT_CONTEMPORANEOUS_HOURLY_SNAPSHOT")
            k=(t["entryUTC"],t["exitUTC"],t["side"])
            if k in seen:
                raise ValueError("PORTFOLIO_DUPLICATE_TRADE")
            seen.add(k)
            doc=records[end]
            item=(doc["originalV7" if model=="V7_ORIGINAL" else "max4hRetest"]
                  if coin=="ETHUSDT" else
                  doc["assets"][coin]["originalV7" if model=="V7_ORIGINAL" else "max4hRetest"])
            exits=item["paperTradeExitsObservedAtThisClose"]
            if not any(
                int(x.get("entryOpenUTC",-1))==entry and
                int(x.get("exitKnownUTC",-1))==end and
                x.get("side")==t["side"] and
                math.isclose(float(x.get("netRIllustrative",float("nan"))),
                             float(t["netR9Bps"]),rel_tol=1e-6,abs_tol=1e-6)
                for x in exits):
                raise ValueError("PORTFOLIO_LEDGER_EXIT_NOT_MATCHED_TO_SOURCE_REPLAY")
            if not math.isfinite(float(t["netR9Bps"])) or not math.isfinite(float(t["netR25Bps"])):
                raise ValueError("PORTFOLIO_NONFINITE_R")
            out.append({
                "asset":coin,"model":model,"entryUTC":t["entryUTC"],
                "exitUTC":t["exitUTC"],"side":t["side"],
                "paperNetR9BpsPerSide":t["netR9Bps"],
                "paperNetR25BpsPerSideStress":t["netR25Bps"],
                "notRealOrderOrProvenExecution":True
            })
        result[model]=out
    return result

def build(config, btc_sol_snapshots, btc_sol_score, eth_snapshots=None, eth_score=None):
    if (config.get("mode")!=STARTER or
        config.get("noLiveOrders") is not True or
        config.get("noRetroactiveExecution") is not True or
        config.get("noNewNotifications") is not True or
        config.get("V7ProductionAndExistingV91TradingRulesUnchanged") is not True):
        raise ValueError("PORTFOLIO_CONFIG_UNSAFE")
    requested=epoch(config["requestedAtUTC"])
    first=epoch(config["firstEligible1HCloseUTC"])
    if first<=requested or first%3600:
        raise ValueError("PORTFOLIO_RETROACTIVE_OR_UNALIGNED_START")
    capital=float(config["initialVirtualCapitalUSDTPerAccount"])
    stake=float(config["fixedPaperRiskUSDTPerEligibleTrade"])
    if capital<=0 or not 0<stake<=capital*.10:
        raise ValueError("PORTFOLIO_INVALID_FIXED_RISK")
    if stake>capital*.01 and config.get("userExplicitlyRequested10PctRiskOnlyInVirtualPaper") is not True:
        raise ValueError("PORTFOLIO_HIGH_RISK_PAPER_SIMULATION_NOT_EXPLICITLY_REQUESTED")
    btc_sol=latest_hour_records(btc_sol_snapshots,BTC_SOL_MODE,first_utc=first,
                                asset_refs={"BTCUSDT","SOLUSDT"})
    eth=(latest_hour_records(eth_snapshots,ETH_MODE,first_utc=first,
                             asset_refs={"ETHUSDT"}) if eth_snapshots else {})
    if bool(eth) and eth_score is None:
        raise ValueError("PORTFOLIO_ETH_SCORE_MISSING_WHEN_ETH_SNAPSHOTS_EXIST")
    ledgers={}
    for coin,records,score in [
        ("BTCUSDT",btc_sol,btc_sol_score),
        ("SOLUSDT",btc_sol,btc_sol_score),
        ("ETHUSDT",eth,eth_score)]:
        ledgers[coin]=(verified_ledger(score,records,coin,first_utc=first,
                                     start_utc=requested)
                       if records else {k:[] for k in NAMES})
    accounts={}
    for model in NAMES:
        trades=sorted([item for c in ledgers for item in ledgers[c][model]],
                      key=lambda x:(x["exitUTC"],x["entryUTC"],x["asset"]))
        totalR=sum(float(t["paperNetR9BpsPerSide"]) for t in trades)
        stressR=sum(float(t["paperNetR25BpsPerSideStress"]) for t in trades)
        equity=capital+stake*totalR
        accounts[model]={
          "virtualInitialUSDT":capital,
          "virtualPaperRiskPerTradeUSDT":stake,
          "riskPctOfInitialCapital":round(100*stake/capital,4),
          "riskPerTradeIsHighAndNotRecommendedForLive":stake/capital>=.05,
          "virtualEquityUSDT":round(equity,6),
          "virtualRealizedPnlUSDT":round(stake*totalR,6),
          "virtualRealizedPnlStress25BpsUSDT":round(stake*stressR,6),
          "netRealizedPaperR9BpsPerSide":round(totalR,6),
          "closedEligiblePaperTrades":len(trades),
          "wins":sum(float(t["paperNetR9BpsPerSide"])>0 for t in trades),
          "losses":sum(float(t["paperNetR9BpsPerSide"])<=0 for t in trades),
          "winRatePct":round(100*sum(float(t["paperNetR9BpsPerSide"])>0 for t in trades)/len(trades),2)
                       if trades else None,
          "perAssetLatestState":{
              "BTCUSDT":signal_state(btc_sol,"BTCUSDT",model),
              "SOLUSDT":signal_state(btc_sol,"SOLUSDT",model),
              "ETHUSDT":signal_state(eth,"ETHUSDT",model)},
          "paperTradeLedger":trades,
          "brokerOrders":0,
          "realExecutableFillsVerified":0
        }
    return {
       "status":"TWO_SEPARATE_PROSPECTIVE_VIRTUAL_PAPER_ACCOUNTS",
       "requestedAtUTC":config["requestedAtUTC"],
       "firstEligible1HCloseUTC":config["firstEligible1HCloseUTC"],
       "lastCapturedEligibleBTCandSOLHourUTC":iso(max(btc_sol)) if btc_sol else None,
       "lastCapturedEligibleETHHourUTC":iso(max(eth)) if eth else None,
       "ETHAddedOnlyIfIndependentV7ParityVerified":bool(eth),
       "accounts":accounts,
       "nightBeforeRequestRetrospectiveOnlyNoOrders":True,
       "riskSizingIsFixedPaper100USDTPerRNotRealPositionFill":True,
       "noForcedEntriesFromMarketTrendOrV9ColorForecast":True,
       "forecastColorsAreV9NotV91EntrySignals":True,
       "noFabricatedMissingHours":True,
       "noActualOrders":True,
       "noUserAlerts":True,
       "unverifiedExecutionAndFundingExcluded":True,
       "BTC_SOL_V7_V91_StrategiesUnchanged":True
    }

def markdown(result):
    p=["# Ayrı V7 ve V9.1 paper hesapları — yalnız ileriye dönük",
       "",
       "**GERÇEK EMİR YOK.** 9 baz puan/yan maliyetli kaynak net-R sanal hesaba aktarılır. Girişler gerçek emir gerçekleşmesi değildir.",
       "Başlangıç UTC: "+result["requestedAtUTC"],
       "İlk uygun 1H kapanışı UTC: "+result["firstEligible1HCloseUTC"],"",
       "| Hesap | Kapanan paper işlem | Kazanma % | Net R | Sanal PnL USDT | Sanal bakiye USDT |",
       "|---|---:|---:|---:|---:|---:|"]
    for name,a in result["accounts"].items():
        p.append("| {} | {} | {} | {} | {} | {} |".format(
            name,a["closedEligiblePaperTrades"],a["winRatePct"],
            a["netRealizedPaperR9BpsPerSide"],
            a["virtualRealizedPnlUSDT"],a["virtualEquityUSDT"]))
    p+=["","**Son giriş/sinyal durumları (BOS izleme, retest ve açık varsayımsal pozisyon eşiklerine göre):**",""]
    for name,a in result["accounts"].items():
        for sym,row in a["perAssetLatestState"].items():
            p.append("- {} {}: {} — en son doğrulanmış 1H {}.".format(
                name,sym,row["status"],row["lastClosedUTC"] or "yok"))
    p+=["",
         "V9 önceden dondurulan 4H renk tahminleri ayrıca değerlendirilir, V9.1 işleme giriş sinyali sayılmaz.",
         "Önceki geceye sonradan emir yazılmaz; 1H eksikleri kapatılmaz.",
         "ETH sadece V7 ile birebir doğrulanan gerçek ileriye dönük ETH V9.1 kayıtları geldikten sonra dahil edilir.",
         "Sanal hesaplar her işlem için sabit {} USDT hedef risk kullanır (başlangıç bakiyesinin %{}'u). %10 çok yüksek risktir. Stop kayması ve kaldıraç nedeniyle gerçek zarar daha yüksek olabilir.".format(next(iter(result["accounts"].values()))["virtualPaperRiskPerTradeUSDT"], next(iter(result["accounts"].values()))["riskPctOfInitialCapital"]),
         "Fonlama, likidasyon, gerçek spread ve uygulanabilir fill garanti edilmez.",""]
    return "\n".join(p)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--config",default="forward/v91_dual_paper_accounts/config.json")
    p.add_argument("--btc-sol-hours",default="forward/v91_prospective_retest/hourly")
    p.add_argument("--btc-sol-score",default="forward/v91_prospective_retest/scoreboard.json")
    p.add_argument("--eth-hours",default="forward/v91_eth_prospective_retest/hourly")
    p.add_argument("--eth-score",default="forward/v91_eth_prospective_retest/scoreboard.json")
    p.add_argument("--out",default="forward/v91_dual_paper_accounts/latest.json")
    p.add_argument("--md",default="forward/v91_dual_paper_accounts/latest.md")
    a=p.parse_args()
    out=build(load_json(a.config),a.btc_sol_hours,load_json(a.btc_sol_score),
              a.eth_hours,load_json(a.eth_score)
              if Path(a.eth_score).is_file() else None)
    Path(a.out).parent.mkdir(parents=True,exist_ok=True)
    Path(a.out).write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
    Path(a.md).write_text(markdown(out))
    print("V7_V91_DUAL_PAPER_ACCOUNTS",
          json.dumps({x:{"closed":y["closedEligiblePaperTrades"],
                         "pnl":y["virtualRealizedPnlUSDT"]}
                      for x,y in out["accounts"].items()}),
          "firstEligible",out["firstEligible1HCloseUTC"],"noOrders",out["noActualOrders"])

if __name__=="__main__":
    main()
