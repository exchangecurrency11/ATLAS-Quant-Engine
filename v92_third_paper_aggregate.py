#!/usr/bin/env python3
"""Strict three-asset V9.2 single 1000 USDT virtual paper portfolio rollup.

The existing BTC/SOL 1000 USDT V9.2 book remains intact. The ETH
source is a separate verified component, not a second initial deposit.
Only prior-precommitted paper trade exits in either source may be counted.
This rollup can be called from either GitHub workflow, with the same
concurrency group. No orders or notifications.
"""
import argparse
from collections import Counter
import json
import math
from pathlib import Path

from v7_forward_observer import epoch
from v92_prospective_selected import BOOK as CORE_MODE, INITIAL, RISK, FIRST
from v92_eth_prospective_selected import (
    BOOK as ETH_MODE,FIRST_ETH
)

MODE="V92_BTC_ETH_SOL_SINGLE_THIRD_1000USDT_PROSPECTIVE_PAPER_ACCOUNT"
COINS=("BTCUSDT","ETHUSDT","SOLUSDT")
ETH_START="2026-11-12T12:00:00Z"

def _trade_key(x):
    return tuple(x[k] for k in ("symbol","entryUTC","exitUTC","side"))

def verified_trade(x,source):
    if (set(("symbol","entryUTC","exitUTC","side","netR9Bps",
             "netR25Bps","notVerifiedExecutableRealFill"))-set(x)
        or x["symbol"] not in COINS
        or x.get("notVerifiedExecutableRealFill") is not True):
        raise ValueError("V92_COMBINED_UNVERIFIED_SOURCE_TRADE_"+source)
    entry=epoch(x["entryUTC"]);end=epoch(x["exitUTC"])
    cutoff=FIRST_ETH if x["symbol"]=="ETHUSDT" else FIRST
    if (entry<cutoff or end<=entry
        or x["side"] not in ("bullish","bearish")
        or any(not math.isfinite(float(x[k]))
               for k in ("netR9Bps","netR25Bps"))):
        raise ValueError("V92_COMBINED_NONCAUSAL_OR_NONFINITE_TRADE")
    return x

def _coverage_audit(first_utc,last_utc,saved_count,through_utc):
    """Summarize source freshness and gaps; never infer missing observations."""
    saved=int(saved_count)
    if saved<0:
        raise ValueError("V92_COMBINED_NEGATIVE_SOURCE_HOUR_COUNT")
    if through_utc is None:
        if saved!=0 or last_utc is not None:
            raise ValueError("V92_COMBINED_SOURCE_HOURS_WITHOUT_COMMON_HORIZON")
        return {"firstExpectedHourUTC":None,"expectedThroughUTC":None,
                "expectedHours":0,"savedVerifiedHours":0,
                "missingHourCount":0,"lastVerifiedHourUTC":None,
                "lagHours":None,"noBackfill":True}
    if first_utc%3600 or through_utc%3600 or through_utc<first_utc:
        raise ValueError("V92_COMBINED_COVERAGE_WINDOW_NOT_ALIGNED")
    expected=((through_utc-first_utc)//3600)+1
    last=epoch(last_utc) if last_utc is not None else None
    if ((last is None and saved!=0) or
        (last is not None and (last<first_utc or last>through_utc or saved==0)) or
        saved>expected):
        raise ValueError("V92_COMBINED_SOURCE_COVERAGE_INCONSISTENT")
    return {
        "firstExpectedHourUTC":iso(first_utc),
        "expectedThroughUTC":iso(through_utc),
        "expectedHours":expected,
        "savedVerifiedHours":saved,
        "missingHourCount":expected-saved,
        "lastVerifiedHourUTC":iso(last) if last is not None else None,
        "lagHours":((through_utc-last)//3600 if last is not None else expected),
        "noBackfill":True
    }


def build(core,eth=None):
    if (core.get("mode")!=CORE_MODE
        or core.get("virtualInitialUSDT")!=INITIAL
        or core.get("targetVirtualRiskUSDTPerTrade")!=RISK
        or core.get("firstEligible1HCloseUTC")!="2026-11-12T11:00:00Z"
        or core.get("noBrokerOrders") is not True
        or core.get("noUserNotifications") is not True
        or core.get("noActualExchangeExecutionOrFill") is not True
        or core.get("historicalPlus836USDNotTransferredHere") is not True
        or core.get("V7V91CurrentPaperAccountsUnchanged") is not True
        or set(core.get("stateBySymbol",{}))!={"BTCUSDT","SOLUSDT"}):
        raise ValueError("V92_COMBINED_BTC_SOL_CORE_UNVERIFIED")
    if eth is not None and (
        eth.get("mode")!=ETH_MODE
        or eth.get("asset")!="ETHUSDT"
        or eth.get("firstEligible1HCloseUTC")!=ETH_START
        or eth.get("noBrokerOrders") is not True
        or eth.get("noUserNotifications") is not True
        or eth.get("separateETHStartingCapitalNotAllocated") is not True
        or eth.get("ETHmax4hPaperEngineSameAsV91NoCandleVeto") is not True
        or eth.get("noRealExchangeOrProvenExecutableFills") is not True
        or eth.get("originalV7V91AndBTCSOLV92Unchanged") is not True):
        raise ValueError("V92_COMBINED_ETH_COMPONENT_UNVERIFIED")
    c=list(core.get("validatedProspectivePaperLedger",[]))
    e=list(eth.get("verifiedProspectivePaperLedger",[])) if eth else []
    if any(t.get("symbol") not in ("BTCUSDT","SOLUSDT") for t in c):
        raise ValueError("V92_COMBINED_CORE_COINS_INVALID")
    if any(t.get("symbol")!="ETHUSDT" for t in e):
        raise ValueError("V92_COMBINED_ETH_COIN_INVALID")
    for t in c:verified_trade(t,"CORE")
    for t in e:verified_trade(t,"ETH")
    if (len(c)!=core.get("closedEligiblePaperTrades")
        or len(e)!=(eth.get("closedEligiblePaperTrades") if eth else 0)
        or not math.isclose(
            sum(float(x["netR9Bps"]) for x in c),
            float(core["netRealizedPaperR9BpsPerSide"]),abs_tol=1e-5)
        or eth and not math.isclose(
            sum(float(x["netR9Bps"]) for x in e),
            float(eth["netPaperR9BpsSide"]),abs_tol=1e-5)):
        raise ValueError("V92_COMBINED_LEDGER_AGGREGATE_MISMATCH")
    rows=sorted(c+e,key=lambda x:(x["exitUTC"],x["entryUTC"],x["symbol"]))
    keys=[_trade_key(x) for x in rows]
    if len(keys)!=len(set(keys)):
        raise ValueError("V92_COMBINED_DUPLICATE_FORWARD_TRADE")
    total=sum(float(x["netR9Bps"]) for x in rows)
    stress=sum(float(x["netR25Bps"]) for x in rows)
    counts=Counter(x["symbol"] for x in rows)
    core_first=epoch(core["firstEligible1HCloseUTC"])
    core_last=core.get("lastDistinctVerifiedClosed1HUTC")
    eth_first=epoch(eth["firstEligible1HCloseUTC"]) if eth else epoch(ETH_START)
    eth_last=eth.get("lastVerifiedETHCloseUTC") if eth else None
    latest_candidates=[epoch(x) for x in (core_last,eth_last) if x is not None]
    common_latest=max(latest_candidates) if latest_candidates else None
    coverage={
        "BTC_SOL":_coverage_audit(
            core_first,core_last,core["savedDistinctVerifiedHours"],common_latest),
        "ETH":_coverage_audit(
            eth_first,eth_last,eth["savedDistinctVerifiedETHHours"] if eth else 0,
            common_latest)
    }
    by_asset={
        x:{"closedEligiblePaperTrades":counts[x],
           "wins":sum(t["netR9Bps"]>0 for t in rows if t["symbol"]==x),
           "netR":round(sum(t["netR9Bps"] for t in rows if t["symbol"]==x),6)}
        for x in COINS}
    return {
      "mode":MODE,
      "assets":list(COINS),
      "virtualInitialUSDT":INITIAL,
      "fixedVirtualStopRiskUSDTPerTrade":RISK,
      "virtualRiskPercentPerTradeOfInitialCapital":10,
      "risk10PctVeryAggressiveNotAdvisedLive":True,
      "firstEligibleBTCandSOLUTC":"2026-11-12T11:00:00Z",
      "firstEligibleETHUTC":ETH_START,
      "sourceBTCandSOLVerifiedClosedHours":core["savedDistinctVerifiedHours"],
      "sourceETHVerifiedClosedHours":
          eth["savedDistinctVerifiedETHHours"] if eth else 0,
      "sourceCoverageAudit":coverage,
      "lastCapturedBTCandSOLHourUTC":core["lastDistinctVerifiedClosed1HUTC"],
      "lastCapturedETHHourUTC":eth["lastVerifiedETHCloseUTC"] if eth else None,
      "sharedSingleVirtualPortfolioNotThreeTimes1000":True,
      "virtualPaperEquityUSDT":round(INITIAL+RISK*total,6),
      "virtualPaperPnLUSDT":round(RISK*total,6),
      "netRealizedPaperR9BpsSide":round(total,6),
      "virtualPaperPnLStress25BpsUSDT":round(RISK*stress,6),
      "closedEligiblePaperTrades":len(rows),
      "wins":sum(t["netR9Bps"]>0 for t in rows),
      "losses":sum(t["netR9Bps"]<=0 for t in rows),
      "winRatePct":round(
          100*sum(t["netR9Bps"]>0 for t in rows)/len(rows),2) if rows else None,
      "perAssetScores":by_asset,
      "perAssetLatestState":{
         "BTCUSDT":core["stateBySymbol"]["BTCUSDT"],
         "ETHUSDT":eth["stateETH"] if eth else {
             "state":"ETH_V92_AWAITING_FIRST_SAME_HOUR_SEALED_SOURCE",
             "lastClosedUTC":None,"newBOSWatches":0,
             "retestPending":False,"openPaperPosition":False},
         "SOLUSDT":core["stateBySymbol"]["SOLUSDT"]},
      "forwardOnlyPrecommittedPaperLedger":rows,
      "ethPatternsObservedButNotAutomaticTradeFilter":True,
      "solStrictSelectedStarHaramiSweepOnly":True,
      "btcPatternVetoDisabled":True,
      "originalV7V91AndOtherV92BooksUnchanged":True,
      "missingHistoryAndNoGitSealedRetestExcluded":True,
      "noHistorical836USDBackfilledIntoThisAccount":True,
      "noRealExecutableFillsProven":True,
      "fundingVariableSpreadSlippageLiquidationNotFullyModeled":True,
      "simultaneousAssetsDoNotHaveTotalRiskCap":True,
      "noBrokerOrders":True,"noUserNotifications":True
    }

def markdown(z):
    text=[
       "# V9.2 — BTC / ETH / SOL, tek üçüncü bağımsız paper hesap",
       "",
       "**1.000 USDT toplam başlangıç, coin başına ayrı 1.000 USDT değil.**",
       "**Gerçek emir / kullanıcı bildirimi / uygulanabilir gerçek fiyat garantisi yok.**",
       "",
       "| Coin | Kapanmış işlem | Kazanan | Net R |",
       "|---|---:|---:|---:|"]
    for coin,x in z["perAssetScores"].items():
        text.append("| {} | {} | {} | {} |".format(
            coin,x["closedEligiblePaperTrades"],x["wins"],x["netR"]))
    coverage=z.get("sourceCoverageAudit",{})
    text += [
       "",
       "**Saatlik kaynak kapsama denetimi (eksik saatler doldurulmaz):**",
       "",
       "| Kaynak | Kaydedilen / beklenen | Eksik saat | Son doğrulanmış saat | Gecikme |",
       "|---|---:|---:|---|---:|"]
    for label,row in coverage.items():
        text.append("| {} | {}/{} | {} | {} | {} saat |".format(
            label,row["savedVerifiedHours"],row["expectedHours"],
            row["missingHourCount"],row["lastVerifiedHourUTC"] or "yok",
            row["lagHours"] if row["lagHours"] is not None else "—"))
    text += [
       "",
       "| Toplam | İşlem | Win % | Net R | Sanal PnL | Sanal bakiye |",
       "|---|---:|---:|---:|---:|---:|",
       "| V9.2 BTC+ETH+SOL | {} | {} | {} | {} USDT | {} USDT |".format(
           z["closedEligiblePaperTrades"],z["winRatePct"],
           z["netRealizedPaperR9BpsSide"],
           z["virtualPaperPnLUSDT"],z["virtualPaperEquityUSDT"]),
       "",
       "ETH ilk uygun saat (TSİ): 12 Kasım 2026 15.00; yeni saatlik ETH V7 + V9.1",
       " kaynakları Git'te doğrulanmışsa gözlem yapılır.",
       "ETH tüm dönüş mumları şimdilik gözlem, BTC otomatik veto yok; "
       "SOL teyitli Star/Harami + 20 mum likidite geri dönüşü filtresi ayrı test.",
       "Geçmişteki +8,36R bu hesaba eklenmedi.",
       "İşlem başına 100 USDT sanal risk (%10 agresif); BTC/ETH/SOL",
       " eşzamanlı risk için henüz birleşik portföy tavanı yok.",
       "Stop kayması, ücretler ve likidasyon nedeniyle gerçek zarar bu riskin üzerine çıkabilir.",
       "Eksik saatler, geç yazılan retestler ve doğrulanmamış giriş/çıkışlar reddedilir.",
       ""
    ]
    return "\n".join(text)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--core",default="forward/v92_prospective_selected/third_paper_account.json")
    p.add_argument("--eth",default="forward/v92_prospective_eth/component.json")
    p.add_argument("--out",default="forward/v92_prospective_selected/combined_three_asset_account.json")
    p.add_argument("--md",default="forward/v92_prospective_selected/combined_three_asset_account.md")
    a=p.parse_args()
    core=json.loads(Path(a.core).read_text())
    eth=json.loads(Path(a.eth).read_text()) if Path(a.eth).exists() else None
    o=build(core,eth)
    f=Path(a.out);f.parent.mkdir(parents=True,exist_ok=True)
    f.write_text(json.dumps(o,ensure_ascii=False,indent=2)+"\n")
    Path(a.md).write_text(markdown(o)+"\n")
    print("V92_THIRD_SHARED_1K_PAPER_ACCOUNT_THREE_COINS",json.dumps({
        "closed":o["closedEligiblePaperTrades"],
        "equity":o["virtualPaperEquityUSDT"],
        "hoursETH":o["sourceETHVerifiedClosedHours"],
        "hoursBTCSOL":o["sourceBTCandSOLVerifiedClosedHours"]}),flush=True)

if __name__=="__main__":
    main()
