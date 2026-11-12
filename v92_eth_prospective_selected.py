#!/usr/bin/env python3
"""V9.2 ETHUSDT paper-only independent hourly source, joined to third virtual book.

ETH V7 and V9.1 original signals are recomputed exactly from the SAME
read-only Coinalyze Binance ETHUSDT_PERP.A source, as of a new CLOSED 1H bar.
No two-year ETH equivalence was established, so ALL ETH reversal patterns
are observational only; none vetoes or creates entry. ETH's hypothetical
trade logic is unchanged V9.1 max4h BOS -> retest -> next-open paper engine.

The third V9.2 portfolio is shared, NOT three separate 1,000-USDT accounts.
Historical paper is NOT forward execution; first ETH eligibility is
2026-11-12 12:00 UTC, after the user's request. The retest MUST have
been committed as a separate V9.2 snapshot BEFORE the retrospective exit.
Never backfill. No orders or notifications.
"""
import argparse
from collections import Counter
import json
import math
import os
from pathlib import Path
import time

from backtest_retest_long_v4 import replay_pair
from eth_v7_hourly_observer import (
    RESEARCH_PAIR, PERIODS, coinalyze_klines, validate_sources
)
from signal_quality_v7 import evaluate_bos_quality
from v7_forward_observer import iso, epoch, latest_events
from v91_eth_prospective_retest import verify_eth_source
from v91_prospective_retest import (
    HOUR,path_at,fetch_json,safe_trade,require_exact_replay
)
from v92_multi_candle_invalidation import all_patterns_at
from v92_selected_reversal_patterns import soldier_crow
from v92_prospective_selected import verified_first_commit

MODE="V92_ETH_VERIFIED_HOURLY_CANDLES_OBSERVATIONAL_PAPER"
BOOK="V92_ETH_COMPONENT_OF_SHARED_THIRD_FORWARD_PAPER"
FIRST_ETH=epoch("2026-11-12T12:00:00Z")
REQUESTED_ETH=epoch("2026-11-12T11:01:54Z")
BPS_SIDE=9
STRESS_BPS_SIDE=25

def verify_eth_v92_source(source, original, target, now,
                          source_path=None, source_repo=None):
    if FIRST_ETH<=REQUESTED_ETH or target<FIRST_ETH:
        raise ValueError("ETH_V92_RETROACTIVE_START_FORBIDDEN")
    if target!=now//HOUR*HOUR or not 12*60<=now-target<=57*60:
        raise ValueError("ETH_V92_NOT_CURRENT_VERIFIED_HOUR_WINDOW")
    if (source.get("mode")!="V91_ETH_PROSPECTIVE_4H_RETEST_IMMUTABLE_PAPER_SHADOW"
        or source.get("symbol")!="ETHUSDT"
        or source.get("originalV7Reference")!=RESEARCH_PAIR
        or source.get("verifiedSourceAndExactV7Replay") is not True
        or source.get("noBackfill") is not True
        or source.get("noBrokerOrders") is not True
        or source.get("noUserNotifications") is not True
        or source.get("independentBinanceMarketTruthEstablished") is not False
        or set(source.get("sourceIntegrity",{}))!=set(PERIODS)
        or not all(x.get("verified") is True
                   for x in source.get("sourceIntegrity",{}).values())
        or epoch(source.get("targetClosed1HUTC"))!=target):
        raise ValueError("ETH_V92_UNVERIFIED_OR_STALE_V91_ETH_SOURCE")
    timestamp=epoch(source["capturedAtUTC"])
    if not target<=timestamp<=now+90 or timestamp>=target+HOUR:
        raise ValueError("ETH_V92_V91_SOURCE_FUTURE_OR_STALE")
    if (original.get("status")!="VERIFIED_PAPER_OBSERVATION"
        or original.get("mode")!="ETH_V7_INDEPENDENT_PAPER_FORWARD_NO_ORDERS"
        or original.get("symbol")!=RESEARCH_PAIR
        or original.get("brokerOrders") is not False
        or original.get("paperForwardObservation") is not True
        or original.get("productionSystemModified") is not False
        or not original.get("dataSource","").startswith(
            "Coinalyze ETHUSDT_PERP.A / Binance perpetual")
        or epoch(original.get("targetClosed1HUTC"))!=target):
        raise ValueError("ETH_V92_MISSING_ORIGINAL_ETH_V7_SOURCE")
    v7_observed=epoch(original["observedAtUTC"])
    if not target<=v7_observed<=timestamp+90:
        raise ValueError("ETH_V92_UNVERIFIED_V7_TIMING")
    if source_path is not None:
        if not source_repo:
            raise ValueError("ETH_V92_GIT_REPO_REQUIRED")
        committed=verified_first_commit(source_repo,source_path)
        if committed is None or not (
           timestamp-90<=committed<=now+90
           and committed<target+HOUR):
            raise ValueError("ETH_V92_V91_PRIOR_GIT_COMMIT_MISSING")
    return True

def capture(source,original,raw,*,now,
            v91_source_path=None,v91_repo=None):
    target=now//HOUR*HOUR
    verify_eth_v92_source(source,original,target,now,
                          source_path=v91_source_path,source_repo=v91_repo)
    parsed,sha,cross=validate_sources(raw,target,now)
    integrity=verify_eth_source(original,parsed,target)
    h,f,d=(parsed[k] for k in ("1hour","4hour","daily"))
    base=replay_pair(h,f,d,as_of=target,retest_hours=6,
                     bos_quality_filter=evaluate_bos_quality)
    alt=replay_pair(h,f,d,as_of=target,retest_hours=4,
                    bos_quality_filter=evaluate_bos_quality)
    original_v7=latest_events(base,target)
    original_v91=latest_events(alt,target)
    require_exact_replay(
      original["results"][RESEARCH_PAIR]["V7_signal_filter"],
      original_v7,symbol="ETHUSDT")
    require_exact_replay(source["originalV7"],
                         original_v7,symbol="ETHUSDT")
    require_exact_replay(source["max4hRetest"],
                         original_v91,symbol="ETHUSDT")
    for trade in original_v91["paperTradeExitsObservedAtThisClose"]:
        safe_trade(trade,target)
    pending=original_v91["currentPaperState"].get("pendingNextOpenPaperEntry")
    if pending is not None and int(pending["retestKnownUTC"])!=target:
        raise ValueError("ETH_V92_RETEST_FUTURE_OR_OLD")
    obs={}
    for tf,bars,seconds in (("1H",h,HOUR),("4H",f,4*HOUR)):
        idx=len(bars)-1
        pats=[{**z,"tf":tf} for z in all_patterns_at(bars,idx,seconds)]
        extra=soldier_crow(bars,idx,seconds)
        if extra:pats.append({**extra,"tf":tf})
        obs[tf]={
          "lastCompletedCandleCloseUTC":iso(bars[-1]["t"]+seconds),
          "confirmedReversalPatterns":pats,
          "ethObservationalOnlyNoAutoVeto":True}
    return {
      "mode":MODE,"symbol":"ETHUSDT",
      "targetClosed1HUTC":iso(target),
      "capturedAtUTC":iso(now),
      "originalV91CapturedAtUTC":source["capturedAtUTC"],
      "originalV7ObservedAtUTC":original["observedAtUTC"],
      "verifiedSourceAndExactV7AndV91Replay":True,
      "sourceIntegrity":integrity,
      "sourceHashesIndependentRead":sha,
      "crossTimeframeOHLCV":cross,
      "independentBinanceTruthNotEstablished":True,
      "ethReversalPatternRecognition1H4H":obs,
      "originalV7":original_v7,
      "originalV91":original_v91,
      "selectedV92":original_v91,
      "ethV92RetestVetoEnabled":False,
      "ethPatternObservationsOnly":True,
      "sameV91Max4hEntryStopTPAndExitLogic":True,
      "notNewETHTradeFromCandleAlone":True,
      "noRetroactiveBackfill":True,
      "originalBTCAndSOLV92RulesUnchanged":True,
      "noBrokerOrders":True,
      "noUserNotifications":True}

def load_hours(folder,current=None):
    saved={}
    root=Path(folder)
    for path in sorted(root.glob("*.json")):
        z=fetch_json(path)
        t=epoch(z["targetClosed1HUTC"])
        if (t<FIRST_ETH or path!=path_at(root,t)
            or t in saved or z.get("mode")!=MODE
            or z.get("symbol")!="ETHUSDT"
            or z.get("verifiedSourceAndExactV7AndV91Replay") is not True
            or z.get("noBrokerOrders") is not True
            or z.get("noUserNotifications") is not True):
            raise ValueError("ETH_V92_STORED_HOUR_UNVERIFIED")
        saved[t]=z
    if current is not None:
        t=epoch(current["targetClosed1HUTC"])
        if t in saved or t<FIRST_ETH:
            raise ValueError("ETH_V92_IMMUTABLE_HOUR_OVERWRITE_OR_BACKFILL")
        saved[t]=current
    return saved

def entry_evidence(folder,trade):
    ret=int(trade["retestKnownUTC"])
    old=path_at(folder,ret)
    if not old.is_file():
        return "ETH_V92_MISSING_ORIGINALLY_GIT_SEALED_RETEST"
    prior=fetch_json(old)
    if (prior.get("mode")!=MODE
        or prior.get("verifiedSourceAndExactV7AndV91Replay") is not True
        or epoch(prior["targetClosed1HUTC"])!=ret):
        return "ETH_V92_INVALID_PRIOR_RETEST_SNAPSHOT"
    captured=epoch(prior["capturedAtUTC"])
    committed=verified_first_commit(".",old)
    last=int(trade["exitKnownUTC"])
    if (committed is None or not ret<=captured<ret+HOUR
        or not captured-90<=committed<ret+HOUR
        or not (captured<last and committed<last)):
        return "ETH_V92_RETEST_NOT_GIT_COMMITTED_BEFORE_EXIT"
    pending=prior["selectedV92"]["currentPaperState"].get(
       "pendingNextOpenPaperEntry")
    if pending is None:
        return "ETH_V92_RETEST_NOT_PRECOMMITTED_AS_PENDING"
    for key in ("side","watchKnownUTC","retestKnownUTC","stop"):
        if key not in pending or key not in trade:
            return "ETH_V92_RETEST_REQUIRED_FIELD_MISSING"
        if key=="stop":
            if not math.isclose(float(pending[key]),float(trade[key]),
                                rel_tol=1e-8,abs_tol=1e-7):
                return "ETH_V92_RETEST_ORIGINAL_STOP_MISMATCH"
        elif pending[key]!=trade[key]:
            return "ETH_V92_RETEST_TRADE_MISMATCH"
    return "ETH_V92_PRIOR_RETEST_COMMITTED_BEFORE_HYPOTHETICAL_EXIT"

def eth_component(snapshots,folder):
    eligible=[];excluded=[]
    for closed,doc in sorted(snapshots.items()):
        for trade in doc["selectedV92"]["paperTradeExitsObservedAtThisClose"]:
            safe_trade(trade,closed)
            if (trade["retestKnownUTC"]<FIRST_ETH
                or trade["entryOpenUTC"]<FIRST_ETH):
                excluded.append({"exitUTC":iso(closed),
                                 "reason":"ETH_V92_BEFORE_REQUESTED_START"})
                continue
            reason=entry_evidence(folder,trade)
            if reason!="ETH_V92_PRIOR_RETEST_COMMITTED_BEFORE_HYPOTHETICAL_EXIT":
                excluded.append({"exitUTC":iso(closed),"reason":reason})
                continue
            r=float(trade["netRIllustrative"])
            stress=r-2*(STRESS_BPS_SIDE-BPS_SIDE)/10000*float(trade["entry"])/float(trade["risk"])
            eligible.append({
                "symbol":"ETHUSDT","entryUTC":iso(trade["entryOpenUTC"]),
                "exitUTC":iso(closed),"side":trade["side"],
                "exitReason":trade.get("exitReason"),
                "netR9Bps":round(r,8),"netR25Bps":round(stress,8),
                "notVerifiedExecutableRealFill":True})
    last=snapshots[max(snapshots)] if snapshots else None
    if last is None:
        state={"state":"NO_NEW_V92_VERIFIED_ETH_HOUR",
               "lastClosedUTC":None,"retestPending":False,
               "openPaperPosition":False,"newBOSWatches":0}
    else:
        position=last["selectedV92"]["currentPaperState"]
        state={
          "state":"PAPER_OPEN" if position["openHypotheticalPosition"] else
                  "PAPER_RETEST_PENDING" if position["pendingNextOpenPaperEntry"] else
                  "BOS_WATCH" if position["activeBOSWatch"] else "FLAT",
          "lastClosedUTC":last["targetClosed1HUTC"],
          "retestPending":position["pendingNextOpenPaperEntry"] is not None,
          "openPaperPosition":position["openHypotheticalPosition"] is not None,
          "newBOSWatches":len(last["selectedV92"]["newWatchAtThisClose"]),
          "patternWarnings":last["ethReversalPatternRecognition1H4H"]}
    return {
      "mode":BOOK,"asset":"ETHUSDT",
      "requestedAtUTC":iso(REQUESTED_ETH),
      "firstEligible1HCloseUTC":iso(FIRST_ETH),
      "savedDistinctVerifiedETHHours":len(snapshots),
      "lastVerifiedETHCloseUTC":iso(max(snapshots)) if snapshots else None,
      "ETHselectedPatternStatus":"OBSERVATION_ONLY_PENDING_INDEPENDENT_ETH_BACKTEST",
      "ETHretentionHours":4,
      "ETHmax4hPaperEngineSameAsV91NoCandleVeto":True,
      "closedEligiblePaperTrades":len(eligible),
      "wins":sum(x["netR9Bps"]>0 for x in eligible),
      "netPaperR9BpsSide":round(sum(x["netR9Bps"] for x in eligible),8),
      "netPaperRStress25BpsSide":round(sum(x["netR25Bps"] for x in eligible),8),
      "verifiedProspectivePaperLedger":eligible,
      "excludedUnsealedETHExits":excluded,
      "stateETH":state,
      "isOneComponentOfCombined1000USDTThirdAccount":True,
      "separateETHStartingCapitalNotAllocated":True,
      "noHistoricalETHBackfill":True,
      "noRealExchangeOrProvenExecutableFills":True,
      "noBrokerOrders":True,"noUserNotifications":True,
      "originalV7V91AndBTCSOLV92Unchanged":True}

def md(x):
    return "\n".join([
      "# V9.2 ETH doğrulanmış 1H/4H dönüş mumları — ayrı veri akışı",
      "",
      "**Yalnız araştırma: gerçek emir, bildirim veya kanıtlanmış fill yok.**",
      "İlk uygun ETH kapanışı UTC: "+x["firstEligible1HCloseUTC"],
      "ETH kapanmış doğrulanmış saat: "+str(x["savedDistinctVerifiedETHHours"]),
      "ETH uygun varsayımsal kapanmış işlem: "+str(x["closedEligiblePaperTrades"]),
      "ETH simülasyon net R: "+str(x["netPaperR9BpsSide"]),
      "ETH aynı 1.000 USDT V9.2 ortak hesabının bir bileşenidir; ayrı 1.000 USDT eklenmedi.",
      "Kapanmış 1H/4H Harami, Star, Hikkake, Engulfing, Soldiers/Crows:",
      "gözlem. ETH için geçmiş bağımsız başarı kanıtlanmadığından retest veto YOK.",
      "Saat kaydı ancak Git'e önce işlenmiş V7 ve V9.1 ETH kaynağıyla oluşturulur.",
      "Önceden sabitlenen retest olmadan sonradan PnL yazılmaz.",
      ""
    ])

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source-dir",default="v91_evidence")
    p.add_argument("--eth-v7-dir",default="v7_evidence/forward/eth/snapshots")
    p.add_argument("--hours",default="forward/v92_prospective_eth/hourly")
    p.add_argument("--component",default="forward/v92_prospective_eth/component.json")
    p.add_argument("--md",default="forward/v92_prospective_eth/component.md")
    p.add_argument("--now",type=int,default=None)
    a=p.parse_args()
    now=int(a.now) if a.now is not None else int(time.time())
    target=now//HOUR*HOUR
    if target<FIRST_ETH:
        print("ETH_V92_SKIP_BEFORE_FIRST_ELIGIBLE_CLOSE",iso(target),flush=True)
        return
    output=path_at(a.hours,target)
    if output.is_file():
        print("ETH_V92_SKIP_IMMUTABLE_CLOSED_HOUR",iso(target),flush=True)
        return
    srcpath=path_at(Path(a.source_dir)/"forward/v91_eth_prospective_retest/hourly",target)
    origpath=path_at(a.eth_v7_dir,target)
    if not srcpath.is_file() or not origpath.is_file():
        print("ETH_V92_SKIP_MISSING_SAME_HOUR_SEALED_ETH_V7_V91",iso(target),flush=True)
        return
    key=os.environ.get("ETH_V7_COINALYZE_API_KEY","").strip()
    if not key:
        print("ETH_V92_SKIP_NO_READONLY_PROVIDER_KEY",flush=True)
        return
    raw={tf:coinalyze_klines(tf,now,key) for tf in PERIODS}
    snapshot=capture(fetch_json(srcpath),fetch_json(origpath),raw,
         now=now,v91_source_path=srcpath,v91_repo=a.source_dir)
    path=Path(a.hours)
    book=eth_component(load_hours(path,current=snapshot),path)
    path.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(snapshot,ensure_ascii=False,indent=2)+"\n")
    component=Path(a.component)
    component.parent.mkdir(parents=True,exist_ok=True)
    component.write_text(json.dumps(book,ensure_ascii=False,indent=2)+"\n")
    Path(a.md).write_text(md(book)+"\n")
    print("ETH_V92_PAPER_PREPARED_REQUIRES_GIT_COMMIT",
          iso(target),"ETHsavedHours",book["savedDistinctVerifiedETHHours"],
          "eligibleTrades",book["closedEligiblePaperTrades"],flush=True)

if __name__=="__main__":
    main()
