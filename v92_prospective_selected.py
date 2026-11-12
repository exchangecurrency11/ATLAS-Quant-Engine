#!/usr/bin/env python3
"""V9.2 BTC/SOL core capture for the shared third 1000 USDT paper portfolio.

- This module captures BTC and SOL; ETH is sealed by a separate source-specific
  V9.2 module and merged into the SAME shared 1000 USDT aggregate, not a second
  ETH deposit.
- BTC/SOL: 1H/4H candle watches plus closed 1D/derived-3D trend and pattern
  observations. Higher-timeframe observations are information-only.
- BTC: original V9.1 max4h signals unchanged; candle pattern *observed*.
- SOL: opposite closed Star/confirmed Harami + prior20 sweep invalidates
  retest in a completely separate full chronological replay.
- Source and V9.2 entry were PRECOMMITTED prior to hypothetical exit.
- No 4H candle before it closes; skip missing hours, no backfill.
- NO REAL ORDERS, NO USER ALERTS. Past V7/V9.1 ledgers unchanged.
- 1000 USDT initial and FIXED 100 USDT paper stop-risk per hypothetical
  trade. 10% is aggressive, not advisable live. May be $200 simultaneous
  exposure. Delayed publication means next-hour-open is NOT an executable
  fill, funding/variable spread/gaps/liquidation unmodeled.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import subprocess
import time

from backtest_retest_long_v4 import replay_pair
from signal_quality_v7 import evaluate_bos_quality
from v7_forward_observer import epoch, iso, latest_events, validate_inputs
from v91_prospective_retest import (
    HOUR, SYM, path_at, fetch_json, safe_trade, require_exact_replay,
    verify_candle_quality_against_v7
)
from v92_selected_reversal_patterns import (
    RESEARCH_QUALIFICATION, make_selective_gate,
    summarize_audit, soldier_crow
)
from v92_multi_candle_invalidation import all_patterns_at, warnings_at_retest
from v92_higher_timeframe_context import higher_timeframe_context

MODE="V92_SELECTED_CANDLE_IMMUTABLE_HOURLY_FORWARD_PAPER_ONLY"
BOOK="V92_INDEPENDENT_1000USDT_100USDT_RISK_PAPER_ACCOUNT"
FIRST=epoch("2026-11-12T11:00:00Z")
USER_REQUEST=epoch("2026-11-12T10:43:17Z")
INITIAL=1000.0
RISK=100.0
BASE_BPS=9
STRESS_BPS=25

def verified_first_commit(repo,path):
    """When reading another checked-out Git repository, first-add time only."""
    try:
        p=Path(repo).resolve()
        rel=Path(path).resolve().relative_to(p)
        x=subprocess.run(
          ["git","log","--diff-filter=A","--format=%ct","--",str(rel)],
          cwd=p,check=True,capture_output=True,text=True,timeout=15)
        ts=[int(t) for t in x.stdout.split() if t.isdecimal()]
        return min(ts) if ts else None
    except (subprocess.SubprocessError, OSError, ValueError):
        return None

def verify_source(source, v7, *, target, now, v91_source_file=None,
                  v91_repo=None):
    if target<FIRST or FIRST<=USER_REQUEST:
        raise ValueError("V92_FORWARD_RETROACTIVE_START_FORBIDDEN")
    if not 12*60<=now-target<=57*60 or target!=now//HOUR*HOUR:
        raise ValueError("V92_FORWARD_OUTSIDE_CURRENT_UNSEALED_CLOSE_WINDOW")
    if (source.get("mode")!="V91_PROSPECTIVE_4H_RETEST_IMMUTABLE_PAPER_SHADOW"
        or source.get("sourceVerifiedSameHour") is not True
        or source.get("V7SnapshotAndIndependentRecomputeExactMatch") is not True
        or source.get("priceAndVolumeValidatedAgainstOriginalV7For1H4HDaily") is not True
        or source.get("noBrokerOrders") is not True
        or source.get("noNotifications") is not True
        or epoch(source.get("targetClosed1HUTC"))!=target
        or set(source.get("assets",{}))!=set(SYM)):
        raise ValueError("V92_FORWARD_REQUIRED_SEALED_V91_SOURCE_MISSING")
    source_timestamp=epoch(source["capturedAtUTC"])
    if not target<=source_timestamp<=now+90 or source_timestamp>=target+HOUR:
        raise ValueError("V92_FORWARD_ORIGINAL_SOURCE_FUTURE_OR_STALE")
    if (v7.get("status")!="VERIFIED_PAPER_OBSERVATION"
        or v7.get("brokerOrders") is not False
        or epoch(v7.get("targetClosed1HUTC"))!=target
        or set(v7.get("results",{}))!=set(SYM.values())):
        raise ValueError("V92_FORWARD_INVALID_ORIGINAL_V7_SOURCE")
    if epoch(v7.get("observedAtUTC"))>source_timestamp+90:
        raise ValueError("V92_FORWARD_V7_CAPTURE_LATER_THAN_V91")
    if v91_source_file is not None:
        if v91_repo is None:
            raise ValueError("V92_FORWARD_MISSING_GIT_SOURCE")
        first_commit=verified_first_commit(v91_repo,v91_source_file)
        if first_commit is None or not (
           source_timestamp-90<=first_commit<=now+90
           and first_commit<target+HOUR):
            raise ValueError("V92_FORWARD_V91_SOURCE_NOT_SEALED_BEFORE_CAPTURE")
    return True

def current_close_retest_evaluation(symbol, one, four, target,
                                    baseline_state, selected_state):
    """Record only this newly closed hour's paired baseline/filter decision."""
    base=baseline_state.get("pendingNextOpenPaperEntry")
    selected=selected_state.get("pendingNextOpenPaperEntry")
    if base is None or int(base.get("retestKnownUTC",-1))!=target:
        selected_current=(selected is not None and
                          int(selected.get("retestKnownUTC",-1))==target)
        return {
          "candidateRetestAtThisClose":False,
          "baselineRetestPresent":False,
          "selectedRetestPresent":selected_current,
          "currentPatternWarnings":[],
          "directCurrentFilterVeto":False,
          "downstreamStateDivergence":selected_current,
          "interpretation":"No baseline V9.1 retest was created at this close",
        }
    warnings=warnings_at_retest(
        one,four,target,base["side"],
        {"STAR","HARAMI_CONFIRMED"},require_sweep=True)
    direct_veto=bool(symbol=="SOLUSDT" and warnings)
    selected_matches=(selected is not None and
        all(
          (math.isclose(float(selected[k]),float(base[k]),
                        rel_tol=1e-8,abs_tol=1e-7) if k=="stop"
           else selected.get(k)==base.get(k))
          for k in ("side","watchKnownUTC","retestKnownUTC","stop")
        ))
    if direct_veto and selected_matches:
        raise ValueError("V92_CURRENT_FILTER_FAILED_TO_VETO_MATCHED_SOL_RETTEST")
    return {
      "candidateRetestAtThisClose":True,
      "baselineRetestPresent":True,
      "activeBOSDirection":base["side"],
      "watchKnownUTC":base["watchKnownUTC"],
      "retestKnownUTC":base["retestKnownUTC"],
      "selectedRetestPresent":selected is not None and
          int(selected.get("retestKnownUTC",-1))==target,
      "selectedRetestMatchesBaseline":selected_matches,
      "currentPatternWarnings":warnings,
      "directCurrentFilterVeto":direct_veto,
      "downstreamStateDivergence":bool(not direct_veto and not selected_matches),
      "interpretation":(
        "Current SOL retest directly vetoed by predeclared opposing Star/Harami plus prior20 sweep"
        if direct_veto else
        "Baseline retest present without a qualifying current veto; compare state for prior-path divergence"
        if not selected_matches else
        "Baseline and filtered retest both retained"
      ),
      "onlyClosed1HAndCompleted4HUsed":True,
      "noFutureBarsUsed":True,
    }

def capture(source, original_v7, main_market, raw, *, now,
            dest, v91_source_file=None, v91_repo=None):
    target=now//HOUR*HOUR
    verify_source(source,original_v7,target=target,now=now,
                  v91_source_file=v91_source_file,v91_repo=v91_repo)
    parsed=validate_inputs(main_market,raw,target,now)
    parity=verify_candle_quality_against_v7(original_v7,parsed,target)
    assets={}
    for symbol,ref in SYM.items():
        h=parsed["1hour"][ref]
        four=parsed["4hour"][ref]
        daily=parsed["daily"][ref]
        replay7=replay_pair(
          h,four,daily,as_of=target,retest_hours=6,
          bos_quality_filter=evaluate_bos_quality)
        replay91=replay_pair(
          h,four,daily,as_of=target,retest_hours=4,
          bos_quality_filter=evaluate_bos_quality)
        base=latest_events(replay7,target)
        alt=latest_events(replay91,target)
        require_exact_replay(
           original_v7["results"][ref]["V7_signal_filter"],
           base,symbol=symbol)
        expected=source["assets"][symbol]
        require_exact_replay(
           expected["originalV7"],base,symbol=symbol)
        require_exact_replay(
           expected["max4hRetest"],alt,symbol=symbol)
        audit=Counter();audit["examples"]=[]
        selected_replay=replay_pair(
          h,four,daily,as_of=target,retest_hours=4,
          bos_quality_filter=evaluate_bos_quality,
          retest_quality_filter=make_selective_gate(
              symbol,four,"SELECTED_SOL_STRICT_SWEEP",audit))
        selected=latest_events(selected_replay,target)
        for x in selected["paperTradeExitsObservedAtThisClose"]:
            safe_trade(x,target)
        pending=selected["currentPaperState"]["pendingNextOpenPaperEntry"]
        if pending is not None and pending.get("retestKnownUTC")!=target:
            raise ValueError("V92_FORWARD_SELECTED_RETEST_NOT_CURRENT")
        current_retest=current_close_retest_evaluation(
            symbol,h,four,target,
            alt["currentPaperState"],selected["currentPaperState"])
        diagnostics={}
        # Only observe fully closed patterns THIS hour; 4H may be older.
        for tf,bars,length in (("1H",h,HOUR),("4H",four,4*HOUR)):
            index=len(bars)-1
            observations=[{**p,"tf":tf}
                          for p in all_patterns_at(bars,index,length)]
            extra=soldier_crow(bars,index,length)
            if extra:observations.append({**extra,"tf":tf})
            diagnostics[tf]={
              "lastClosedCandleUTC":iso(int(bars[-1]["t"])+length),
              "observedReversalsAtLastCompletedCandle":observations,
              "informationOnlyNotAutomaticNewTrade":True}
        # 1D and derived 3D use ONLY the already validated closed daily source.
        # Watch/context only: do NOT change original V7/V9.1 or selected retest logic.
        diagnostics.update(higher_timeframe_context(daily,target))
        assets[symbol]={
          "originalV7":base,
          "originalV91":alt,
          "selectedV92":selected,
          "selectedV92Audit":summarize_audit(audit),
          "currentCloseRetestEvaluation":current_retest,
          "recentPatternObservations":diagnostics,
          "modelPolicy":"SOL_STRICT_SELECTED_STAR_HARAMI_SWEEP_VETO"
             if symbol=="SOLUSDT" else "BTC_OBSERVATION_ONLY_NO_VETO",
          "noStandaloneCandleDrivenEntry":True,
        }
    return {
      "mode":MODE,
      "targetClosed1HUTC":iso(target),
      "capturedAtUTC":iso(now),
      "originalV91CapturedAtUTC":source["capturedAtUTC"],
      "originalV7ObservedAtUTC":original_v7["observedAtUTC"],
      "sourceVerifiedSameHour":True,
      "sourceV7AndV91RecomputedExactMatch":True,
      "originalV7_1H4HDailyCandleParity":parity,
      "liveBinanceExchangeParityNotIndependentlyProven":True,
      "noPastHourBackfill":True,
      "policyFrozenAfterInspectingOldHistory":True,
      "policy":RESEARCH_QUALIFICATION,
      "hypotheticalEntryAtPastNextOpenNotProvenExecutable":True,
      "userRequestedStartUTC":iso(USER_REQUEST),
      "firstEligibleHourUTC":iso(FIRST),
      "assets":assets,
      "noBrokerOrders":True,
      "noUserNotifications":True,
      "originalV7V91StrategyAndPortfolioUntouched":True,
      "ETHExcludedFromThisBTC_SOLCoreCapture":True,
      "ETHMustBeMergedFromSeparateSealedV92Component":True,
      "ETHUsesSameSharedThirdPaperPortfolioNotExtraCapital":True,
      "ETHSelectedPatternVetoNotEnabled":True,
      # Backward-compatible legacy flag: ETH is not part of this BTC/SOL
      # capture, but is integrated by the separate ETH component workflow.
      "ETHExcludedUntilSameSourceParityAndHistoricalRules":True,
    }

def load_all(folder, *, current=None):
    saved={}
    folder=Path(folder)
    for path in sorted(folder.glob("*.json")):
        o=fetch_json(path)
        t=epoch(o["targetClosed1HUTC"])
        if (path!=path_at(folder,t) or t in saved or t<FIRST
            or o.get("mode")!=MODE
            or o.get("sourceV7AndV91RecomputedExactMatch") is not True
            or o.get("noBrokerOrders") is not True):
            raise ValueError("V92_FORWARD_UNVERIFIED_SNAPSHOT_OR_DUPLICATE")
        saved[t]=o
    if current is not None:
        t=epoch(current["targetClosed1HUTC"])
        if t in saved:
            raise ValueError("V92_FORWARD_IMMUTABLE_SNAPSHOT_OVERWRITE_BLOCKED")
        if t<FIRST or current.get("mode")!=MODE:
            raise ValueError("V92_FORWARD_CURRENT_UNVERIFIED")
        saved[t]=current
    return saved

def evidence_for_entry(folder,symbol,t):
    ret=int(t["retestKnownUTC"])
    path=path_at(folder,ret)
    if not path.is_file():
        return "NO_PREVIOUSLY_CAPTURED_RETEST_HOUR"
    earlier=fetch_json(path)
    if (earlier.get("mode")!=MODE
        or earlier.get("sourceV7AndV91RecomputedExactMatch") is not True
        or epoch(earlier["targetClosed1HUTC"])!=ret):
        return "RETEST_SOURCE_UNVERIFIED"
    at=epoch(earlier["capturedAtUTC"])
    commit=verified_first_commit(".",path)
    exit_=int(t["exitKnownUTC"])
    if (commit is None or not ret<=at<ret+HOUR
        or not at-90<=commit<ret+HOUR
        or not commit<exit_ and at<exit_):
        return "RETEST_NOT_PROVEN_GIT_COMMITTED_PRE_EXIT"
    p=earlier["assets"][symbol]["selectedV92"]["currentPaperState"].get(
      "pendingNextOpenPaperEntry")
    if p is None:
        return "NOT_PRECOMMITTED_PENDING_V92_RETEST"
    for key in ("side","watchKnownUTC","retestKnownUTC","stop"):
        if key not in p or key not in t:
            return "RETEST_REQUIRED_FIELD_MISSING"
        if key=="stop":
            if not math.isclose(
               float(p[key]),float(t[key]),rel_tol=1e-8,abs_tol=1e-7):
                return "RETEST_STOP_MISMATCH"
        elif p[key]!=t[key]:
            return "RETEST_POLICY_OR_TRADE_MISMATCH"
    return "PRECOMMITTED_V92_RETEST_BEFORE_PAPER_EXIT"

def state_of(snapshot, coin):
    if snapshot is None:
        return {"state":"NO_NEW_V92_VERIFIED_HOUR","lastClosedUTC":None,
                "newBOSWatches":0,"retestPending":False,"openPaperPosition":False}
    x=snapshot["assets"][coin]["selectedV92"]
    state=x["currentPaperState"]
    return {
      "state":"OPEN_HYPOTHETICAL_PAPER_POSITION"
          if state.get("openHypotheticalPosition") is not None else
          "PENDING_HYPOTHETICAL_NEXT_OPEN"
          if state.get("pendingNextOpenPaperEntry") is not None else
          "BOS_WATCH_FOR_RETEST"
          if state.get("activeBOSWatch") is not None else "FLAT_NO_ENTRY",
      "lastClosedUTC":snapshot["targetClosed1HUTC"],
      "newBOSWatches":len(x["newWatchAtThisClose"]),
      "retestPending":state.get("pendingNextOpenPaperEntry") is not None,
      "openPaperPosition":state.get("openHypotheticalPosition") is not None,
      "patternWarnings":snapshot["assets"][coin]["recentPatternObservations"]
    }

def account(snapshots,folder,*,first=FIRST):
    if first!=FIRST:
        raise ValueError("V92_FORWARD_ACCOUNT_RESTRICTED_TO_ORIGINAL_START")
    eligible={sym:[] for sym in SYM}
    excluded={sym:[] for sym in SYM}
    for closed,snap in sorted(snapshots.items()):
        for coin in SYM:
            events=snap["assets"][coin]["selectedV92"]
            for t in events["paperTradeExitsObservedAtThisClose"]:
                safe_trade(t,closed)
                if not (int(t["retestKnownUTC"])>=first and
                        int(t["entryOpenUTC"])>=first and
                        int(t["exitKnownUTC"])>=first+HOUR):
                    excluded[coin].append({"exitUTC":iso(closed),
                                           "reason":"BEFORE_V92_FORWARD_START"})
                    continue
                reason=evidence_for_entry(folder,coin,t)
                if reason!="PRECOMMITTED_V92_RETEST_BEFORE_PAPER_EXIT":
                    excluded[coin].append({"exitUTC":iso(closed),
                                           "reason":reason})
                    continue
                r=float(t["netRIllustrative"])
                stress=r-2*(STRESS_BPS-BASE_BPS)/10000*float(t["entry"])/float(t["risk"])
                eligible[coin].append({
                  "symbol":coin,"entryUTC":iso(t["entryOpenUTC"]),
                  "exitUTC":iso(closed),"side":t["side"],
                  "exitReason":t.get("exitReason"),
                  "netR9Bps":round(r,8),"netR25Bps":round(stress,8),
                  "notVerifiedExecutableRealFill":True})
    alltrades=sorted(
       [v for coin in SYM for v in eligible[coin]],
       key=lambda x:(x["exitUTC"],x["entryUTC"],x["symbol"]))
    profit=sum(z["netR9Bps"] for z in alltrades)
    stress=sum(z["netR25Bps"] for z in alltrades)
    if not math.isfinite(profit) or not math.isfinite(stress):
        raise ValueError("V92_FORWARD_NONFINITE_ACCOUNT_PNL")
    latest=snapshots[max(snapshots)] if snapshots else None
    return {
        "mode":BOOK,
        "requestedAtUTC":iso(USER_REQUEST),
        "firstEligible1HCloseUTC":iso(first),
        "lastDistinctVerifiedClosed1HUTC":iso(max(snapshots)) if snapshots else None,
        "savedDistinctVerifiedHours":len(snapshots),
        "accountName":"V92_SELECTED_SOL_STRICT_CANDLES_BTC_WATCH",
        "virtualInitialUSDT":INITIAL,
        "targetVirtualRiskUSDTPerTrade":RISK,
        "riskPctOfInitialCapital":100*RISK/INITIAL,
        "riskIs10PctAggressivePaperOnlyNotLiveRecommendation":True,
        "virtualEquityUSDT":round(INITIAL+RISK*profit,6),
        "netRealizedPaperR9BpsPerSide":round(profit,6),
        "virtualRealizedPnLUSDT":round(RISK*profit,6),
        "virtualStressPnL25BpsUSDT":round(RISK*stress,6),
        "closedEligiblePaperTrades":len(alltrades),
        "wins":sum(t["netR9Bps"]>0 for t in alltrades),
        "losses":sum(t["netR9Bps"]<=0 for t in alltrades),
        "winRatePct":round(
            100*sum(t["netR9Bps"]>0 for t in alltrades)/len(alltrades),2)
            if alltrades else None,
        "stateBySymbol":{
            s:state_of(latest,s) for s in SYM
        },
        "validatedProspectivePaperLedger":alltrades,
        "excludedUnsealedOrUnprovenExits":excluded,
        "noBackfilledOlderHourObservation":True,
        "neverCountExitWithoutPrecommittedRetest":True,
        "noActualExchangeExecutionOrFill":True,
        "nextOpenPaperFillMayBeUnachievableDueToRunnerDelay":True,
        "assumedFeesSlippage9BpsPerSide":True,
        "fundingDynamicSpreadLiquidationExcluded":True,
        "perTradeTargetRiskNotGuaranteedWorstCase":True,
        "multipleCoinSimultaneousOpenRiskNotPortfolioCapped":True,
        "ETHExcludedWithoutVerifiedV7Parity":True,
        "V7V91CurrentPaperAccountsUnchanged":True,
        "noUserNotifications":True,
        "noBrokerOrders":True,
        "historicalPlus836USDNotTransferredHere":True,
    }

def md(x):
    text=[
      "# V9.2 seçici formasyon — üçüncü ayrı ileri paper hesap",
      "",
      "**GERÇEK EMİR, GERÇEK UYGULANABİLİR GİRİŞ VE KULLANICI BİLDİRİMİ YOK.**",
      "İleri paper başlangıç: "+x["firstEligible1HCloseUTC"],
      "En son doğrulanmış kapanış: "+str(x["lastDistinctVerifiedClosed1HUTC"]),
      "Doğrulanan saat: "+str(x["savedDistinctVerifiedHours"]),
      "",
      "| Hesap | İşlem | Kazanç | Net R | Sanal PnL | Sanal bakiye |",
      "|---|---:|---:|---:|---:|---:|",
      "| V9.2 bağımsız | {} | {} | {} | {} USDT | {} USDT |".format(
        x["closedEligiblePaperTrades"],x["winRatePct"],
        x["netRealizedPaperR9BpsPerSide"],
        x["virtualRealizedPnLUSDT"],x["virtualEquityUSDT"]),
      "",
      "BTC yalnız izleme; SOL 1H/4H kapanmış Morning/Evening Star veya "
      "3 mum teyitli Harami ve likidite geri dönüşüyle karşıt retest reddi.",
      "Hikkake, Engulfing, Three Soldiers/Crows yalnız gözlem.",
      "Eski iki 1000 USDT hesap değişmedi. Eski +8,36R geçmiş "
      "getiri yeni hesaba taşınmadı.",
      "Gecikmeli veri nedeniyle sonraki mum açılışında gerçek emir dolumu "
      "kanıtlanmadı; bu yalnız sanal referans. Maliyet 9bp/yön; "
      "funding, gerçek spread, kayma ve likidasyon eksik.",
      "10%/işlem riski çok yüksektir ve gerçek işlemler için tavsiye edilmez.",
      "Eksik saatler ve retest öncesi commit'i olmayan işlemler sayılmaz.",
      ""
    ]
    for coin,rows in x["excludedUnsealedOrUnprovenExits"].items():
        if rows:
            text.append("{} hariç tutulan varsayımsal çıkış: {}".format(coin,len(rows)))
    return "\n".join(text)

def main():
    a=argparse.ArgumentParser()
    a.add_argument("--source-dir",default="v91_evidence")
    a.add_argument("--v7-dir",default="v7_evidence/forward/snapshots")
    a.add_argument("--market",default="forward/tmp/v92_main_market.json")
    a.add_argument("--history",default="forward/tmp/v92_history")
    a.add_argument("--hourly",default="forward/v92_prospective_selected/hourly")
    a.add_argument("--account",default="forward/v92_prospective_selected/third_paper_account.json")
    a.add_argument("--report",default="forward/v92_prospective_selected/third_paper_account.md")
    a.add_argument("--now-epoch",type=int)
    args=a.parse_args()
    now=args.now_epoch or int(time.time())
    target=now//HOUR*HOUR
    if target<FIRST:
        print("V92_PRE_FIRST_ELIGIBLE_HOUR_SAFE_SKIP",iso(target),flush=True)
        return
    folder=Path(args.hourly)
    path=path_at(folder,target)
    if path.exists():
        print("V92_ALREADY_IMMUTABLE_HOUR_SAFE_SKIP",iso(target),flush=True)
        return
    srcpath=path_at(
      Path(args.source_dir)/"forward/v91_prospective_retest/hourly",target)
    v7path=path_at(args.v7_dir,target)
    if not srcpath.is_file() or not v7path.is_file():
        print("V92_REQUIRE_MATCHED_SEALED_V91_AND_V7_HOUR_SAFE_SKIP",
              iso(target),flush=True)
        return
    market=fetch_json(args.market)
    raw={tf:fetch_json(Path(args.history)/("history_"+tf+".json"))
         for tf in ("1hour","4hour","daily")}
    snap=capture(
      fetch_json(srcpath),fetch_json(v7path),market,raw,now=now,
      dest=folder,v91_source_file=srcpath,v91_repo=args.source_dir)
    all_s=load_all(folder,current=snap)
    book=account(all_s,folder)
    folder.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(snap,ensure_ascii=False,indent=2)+"\n")
    outfile=Path(args.account)
    outfile.parent.mkdir(parents=True,exist_ok=True)
    outfile.write_text(json.dumps(book,ensure_ascii=False,indent=2)+"\n")
    Path(args.report).write_text(md(book)+"\n")
    print("V92_NEW_HOUR_PREPARED_REQUIRES_GIT_COMMIT_TO_SEAL",
          iso(target),"paperTrades",book["closedEligiblePaperTrades"],
          "equity",book["virtualEquityUSDT"],flush=True)

if __name__=="__main__":
    main()
