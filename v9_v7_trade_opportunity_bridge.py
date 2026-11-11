#!/usr/bin/env python3
"""V9 objective correction: V7 BOS/retest paper trading is PRIMARY.

This is a READ-ONLY prospective shadow join of:
  1) V7 *actually saved* and verified closed-1H paper observation (BTC/SOL),
  2) V9 *actually saved* hourly market-context snapshot at same 1H close,
  3) optional V9 green/red next 4H forecast committed BEFORE that 4H began.

The forecast's own 4H candle color is only a trade-context overlay. It is
not an entry, guarantee of profit, price target, trailing stop or a V7
strategy win. We NEVER promote generic 4H trend votes to BOS signals,
and NEVER fabricate a missing sealed V9 prediction. At any step a failed
timestamp, branch-commit proof, or price parity returns an ineligible
research overlay, with V7's own original signals left UNCHANGED.

Separate after-close journal tracks original V7 paper exits in net R at
9bp per side and a 25bp stress case; samples with a correctly archived V9
prestart forecast can be compared as a hypothetical pre-committed gate.
Never infer that rejecting old trades would yield the same V7 opportunities
without a full chronological replay; gated trade subsets are only
descriptive, not a simulated counterfactual strategy.
"""
import argparse,json,math,subprocess,os
from datetime import datetime,timezone
from pathlib import Path
from v9_next4h_paper_outcome_score import verify_prior_forecast
from v9_next_4h_color_research import HOUR,FOUR,SYMBOLS,iso,ts
from v9_trade_opportunity_quality import quality_profile

CANDIDATES=("BTCUSDT","SOLUSDT")
CONTRACTS={s:s+"_PERP.A" for s in CANDIDATES}
STATUS="V9_V7_ORIGINAL_TRADE_OPPORTUNITY_READONLY_SHADOW"
DEFAULT_V7="v7_evidence/forward/snapshots"
DEFAULT_V9="forward/v9_next_4h_color/hourly/snapshots"
DEFAULT_PRESTART="forward/v9_next_4h_color/paper_forecasts"


def verify_saved_forecast(forecast,*,git_first_commit_time=None):
    """Trust ORIGINAL Git commit time, not an arbitrary JSON decision clock."""
    start,_=verify_prior_forecast(forecast)
    if git_first_commit_time is None:
        return {"status":"NO_PROVEN_GIT_PRESTART_COMMIT"}
    if type(git_first_commit_time) is not int:
        raise ValueError("INVALID_FIRST_ORIGINAL_GIT_COMMIT_TIME")
    if git_first_commit_time>=start:
        return {"status":"FORECAST_GIT_COMMIT_NOT_BEFORE_4H_START"}
    if ts(forecast["decisionCapturedUTC"])>git_first_commit_time+120:
        # Commit must be created after forecast, allow small clock drift.
        return {"status":"FORECAST_CAPTURE_AFTER_EVIDENCED_COMMIT"}
    return {"status":"ORIGINAL_LOCKED_BEFORE_START_FORECAST",
            "targetUTC":iso(start),
            "firstGitCommitUTC":iso(git_first_commit_time)}


def _side_to_color(side):
    if side=="bullish":return "GREEN"
    if side=="bearish":return "RED"
    raise ValueError("INVALID_V7_SIDE")


def asof_overlay(v7,hourly,forecast=None,git_first_commit_time=None,
                 quality_hour_by_symbol=None):
    if v7.get("status")!="VERIFIED_PAPER_OBSERVATION":
        raise ValueError("V7_NOT_VERIFIED_ORIGINAL_SNAPSHOT")
    if hourly.get("status")!="V9_HOURLY_OBSERVATION_VERIFIED_PAPER_CONTEXT_ONLY":
        raise ValueError("V9_HOURLY_NOT_VERIFIED_ORIGINAL_SNAPSHOT")
    end=ts(v7["targetClosed1HUTC"])
    if end%HOUR or hourly.get("closed1HUTC")!=v7["targetClosed1HUTC"]:
        raise ValueError("V7_V9_NOT_IDENTICAL_CLOSED_HOURLY_TARGET")
    if ts(v7["observedAtUTC"])<end or ts(hourly["observedAtUTC"])<end:
        raise ValueError("ANALYSIS_CREATED_BEFORE_HOUR_WAS_CLOSED")
    if set(hourly["assets"])!=set(SYMBOLS):
        raise ValueError("V9_SOURCE_NOT_ALL_THREE_ASSETS")
    if any(c not in v7.get("results",{}) or c not in v7.get("marketContext",{})
           for c in CONTRACTS.values()):
        raise ValueError("V7_PAIR_OR_MARKET_CONTEXT_MISSING")
    if v7.get("brokerOrders") is not False or hourly.get("realOrders") is not False:
        raise ValueError("TRADING_ORDER_NOT_RESEARCH")
    target=(end//FOUR)*FOUR
    eligible_forecast=None
    lock_status="NO_ORIGINAL_GIT_SEALED_V9_4H_FORECAST"
    if forecast is not None:
        if ts(forecast["target4HStartUTC"])!=target:
            raise ValueError("V9_FORECAST_TARGET_NOT_CURRENT_ACTIVE_4H")
        proof=verify_saved_forecast(forecast,
                  git_first_commit_time=git_first_commit_time)
        lock_status=proof["status"]
        if lock_status=="ORIGINAL_LOCKED_BEFORE_START_FORECAST":
            eligible_forecast=forecast
    derived={}
    for s in CANDIDATES:
        ref=CONTRACTS[s]
        v7row=v7["results"][ref]["V7_signal_filter"]
        v7context=v7["marketContext"][ref]
        observations=[]
        new_watches=v7row["newWatchAtThisClose"]
        quality_profiles=[]
        if quality_hour_by_symbol is not None and new_watches:
            bars=quality_hour_by_symbol.get(s)
            if not bars or len(bars)!=250 or (
                bars[0]["t"]!=end-250*HOUR or
                bars[-1]["t"]+HOUR!=end):
                raise ValueError("V9_QUALITY_NOT_EXACT_PRIOR_250_CLOSED_HOURS_"+s)
            for watch in new_watches:
                if watch.get("side") not in ("bullish","bearish") or (
                    type(watch.get("BOSLevel")) not in (int,float)):
                    raise ValueError("V7_WATCH_LEVEL_INVALID_FOR_V9_SCORE")
                signal={"event":"BOS","direction":watch["side"],
                        "at":end-HOUR,"confirmedAt":end,
                        "brokenLevel":watch["BOSLevel"]}
                quality_profiles.append(quality_profile(
                    bars,signal,v7context["timeframes"]["1hour"]["indicators"]))
        for w in new_watches:
            if w.get("knownUTC")!=end and (
                type(w.get("knownUTC")) is not int or w["knownUTC"]!=end):
                raise ValueError("V7_WATCH_TIMESTAMP_NOT_THIS_HOUR")
            observations.append({"kind":"V7_NEW_BOS_WATCH",
                                 "side":w["side"],
                                 "notAnEntry":True,
                                 "recordedAtClosedUTC":iso(end)})
        p=v7row["currentPaperState"].get("pendingNextOpenPaperEntry")
        pending_now=p is not None and p.get("retestKnownUTC")==end
        if pending_now:
            observations.append({"kind":"V7_RETEST_CONFIRMED_NEXT_OPEN_PAPER_ONLY",
                                 "side":p["side"],
                                 "notAPreExecutedEntry":True})
        live=v7row["currentPaperState"].get("openHypotheticalPosition")
        v9_asset=hourly["assets"][s]
        provider_close=float(v9_asset["1H"]["OHLCV"]["close"])
        v7close=float(v7context["timeframes"]["1hour"]["candle"]["close"])
        if abs(v7close-provider_close)>max(1e-6,abs(v7close)*2e-5):
            raise ValueError("V7_V9_CLOSED_1H_PRICE_SOURCE_MISMATCH_"+s)
        if quality_profiles and (
            abs(float(quality_hour_by_symbol[s][-1]["c"])-v7close)>
            max(1e-6,abs(v7close)*2e-5)):
            raise ValueError("V9_QUALITY_COINALYZE_V7_LAST_HOUR_PRICE_PARITY_FAILED_"+s)
        suggestion=None
        if eligible_forecast is not None:
            row=eligible_forecast["assetForecasts"][s]
            primary={
              "direction":row["direction"],
              "pGreenUncalibrated":row["pGreenUNCALIBRATED"],
              "predictsOwn4HBodyNotTradePnL":True,
              "notApprovedAsEntryOrExitSignal":True,
              "locked4HStartUTC":eligible_forecast["target4HStartUTC"]}
            shadow=eligible_forecast.get("researchOnlyShadow88NoProviderTradeCount")
            shadow88=(shadow["shadowAssetForecasts"][s]
                if shadow is not None else None)
            suggestion={
              "primary94":primary,
              "shadow88NoProviderTX":({
                "direction":shadow88["direction"],
                "pGreenUncalibrated":shadow88["pGreenUNCALIBRATED"],
                "sameCurrent4HTarget":True,
                "notTradingSignal":True,
              } if shadow88 is not None else None)}
        statuses=[]
        for i,event in enumerate(observations):
            score=(quality_profiles[i] if i<len(quality_profiles)
                   and event["kind"]=="V7_NEW_BOS_WATCH" else None)
            aligned=(suggestion["primary94"]["direction"]==
                _side_to_color(event["side"])) if suggestion else None
            statuses.append({
               "v7Event":event,
               "v9BOSQualityScoreFromExact250ClosedHours":score,
               "v9Primary94DirectionalAgreement":aligned,
               "v9SignalFilterWouldBeHypotheticalNotExecuted":True,
               "doNotTurnDirectionIntoProfitProbability":True})
        derived[s]={
          "originalV7NewWatchesAtThisClose":len(new_watches),
          "v9QualityScoredOriginalV7NewWatches":len(quality_profiles),
          "v9QualityScoreIsOnlyResearchContextNotAProfitableTradeProbability":True,
          "originalV7RetestConfirmedAtThisClose":bool(pending_now),
          "originalV7PaperPositionAlreadyOpen":live is not None,
          "originalV7NewPaperTradeExitsAtThisClose":len(
              v7row["paperTradeExitsObservedAtThisClose"]),
          "v7VotesOnlyNotActionable":{
             "4H":v7context["timeframes"]["4hour"]["directionVotes"]["label"],
             "Daily":v7context["timeframes"]["daily"]["directionVotes"]["label"]},
          "v9IndependentHourContext":v9_asset["1H"]["context"],
          "v9OriginalSealed4HColorContext":suggestion,
          "eventOverlayOnly":statuses,
          "noOriginalV7WatchOrRetestRewritten":True}
    return {
      "status":STATUS,
      "sameClosed1HUTC":iso(end),
      "joinedAfterBothOriginalSnapshotsUTC":iso(max(
          ts(v7["observedAtUTC"]),ts(hourly["observedAtUTC"]))),
      "current4HTargetStartUTC":iso(target),
      "original4HForecastLockStatus":lock_status,
      "4HOwnColorIsSecondaryNotProfitTarget":True,
      "V7BOSRetestStrategyIsPrimary":True,
      "V9CannotInventBOSWatchOrProfitableTrade":True,
      "v7PositionsAndSignalsLeftUnchanged":True,
      "contracts":derived,
      "noOrders":True,"noNotifications":True,
      "noProductionModified":True}


def first_commit_epoch(path):
    # GitHub runner uses fetch-depth 0; reject missing, truncated or
    # rewritten history rather than fabricating a first commit date.
    cmd=["git","log","--diff-filter=A","--follow",
         "--format=%ct","--",str(path)]
    r=subprocess.run(cmd,text=True,capture_output=True,check=True,timeout=10)
    xs=[x.strip() for x in r.stdout.splitlines() if x.strip()]
    if not xs or not all(x.isdecimal() for x in xs):
        return None
    return min(int(x) for x in xs)


def score_trade_subset(v7_snapshot_dir,forecast_dir,commit_lookup):
    """DESCRIPTIVE only; original V7 strategy is NOT re-simulated after filter."""
    files=sorted(Path(v7_snapshot_dir).glob("*.json"))
    ledger={}
    for path in files:
        x=json.loads(path.read_text())
        if x.get("status")!="VERIFIED_PAPER_OBSERVATION":continue
        ended=ts(x["targetClosed1HUTC"])
        if ts(x["observedAtUTC"])<ended:continue
        for symbol in CANDIDATES:
            for t in x.get("results",{}).get(CONTRACTS[symbol],{}).get(
                     "V7_signal_filter",{}).get(
                     "paperTradeExitsObservedAtThisClose",[]):
                if t.get("exitKnownUTC")!=ended:
                    raise ValueError("V7_TRADE_EXIT_IS_NOT_THIS_CLOSED_HOUR")
                key=(symbol,t["entryOpenUTC"],t["exitKnownUTC"])
                if key in ledger:
                    if ledger[key]["trade"]!=t:
                        raise ValueError("ORIGINAL_V7_TRADE_REWRITTEN")
                else:
                    ledger[key]={"symbol":symbol,"trade":t}
    forecast_cache={}
    for path in sorted(Path(forecast_dir).glob("*.json")):
        j=json.loads(path.read_text())
        start,_=verify_prior_forecast(j)
        if start in forecast_cache:raise ValueError("TWO_V9_FORECASTS_SAME_TARGET")
        p=verify_saved_forecast(j,git_first_commit_time=commit_lookup(path))
        if p["status"]=="ORIGINAL_LOCKED_BEFORE_START_FORECAST":
            forecast_cache[start]=j
    def cost_stress(t,bps):
        base=float(t["netRIllustrative"])
        return base-2*(bps-9)/10000*float(t["entry"])/float(t["risk"])
    full={s:[] for s in CANDIDATES}
    gated={s:[] for s in CANDIDATES}
    for item in ledger.values():
        symbol,t=item["symbol"],item["trade"]
        if (type(t.get("entryOpenUTC")) is not int or
            type(t.get("retestKnownUTC")) is not int or
            t["retestKnownUTC"]>t["entryOpenUTC"] or
            t["entryOpenUTC"]>=t["exitKnownUTC"] or
            float(t["risk"])<=0):
            raise ValueError("V7_ORIGINAL_TRADE_CHRONOLOGY_OR_RISK_INVALID")
        full[symbol].append(t)
        decision=t["retestKnownUTC"]
        start=decision//FOUR*FOUR
        if decision==start:
            # At exact T, sealed 4H forecast is valid, but we require
            # original Git prestart proof; trade entry is next 1H open.
            pass
        forecast=forecast_cache.get(start)
        if forecast is None:continue
        if (ts(forecast["decisionCapturedUTC"])>decision or
            not start<=decision<start+FOUR):
            continue
        if forecast["assetForecasts"][symbol]["direction"]==_side_to_color(t["side"]):
            gated[symbol].append(t)
    def metrics(items):
        r=[float(t["netRIllustrative"]) for t in items]
        r25=[cost_stress(t,25) for t in items]
        pos=sum(x for x in r if x>0)
        neg=-sum(x for x in r if x<0)
        eq=0.;peak=0.;dd=0.
        for n in sorted(items,key=lambda x:x["exitKnownUTC"]):
            eq+=float(n["netRIllustrative"])
            peak=max(peak,eq);dd=max(dd,peak-eq)
        return {
          "completedV7OriginalPaperTrades":len(r),
          "winnerCountAt9bpsPerSide":sum(x>0 for x in r),
          "winRatePct":round(100*sum(x>0 for x in r)/len(r),2) if r else None,
          "totalNetRIllustrativeAt9bpsPerSide":round(sum(r),4) if r else None,
          "meanNetRAt9bpsPerSide":round(sum(r)/len(r),4) if r else None,
          "meanNetRStressAt25bpsPerSide":round(sum(r25)/len(r25),4) if r25 else None,
          "profitFactorR":round(pos/neg,3) if neg else None,
          "maximumPeakToTroughDrawdownInR":round(dd,4) if r else None,
          "fundingOrderbookTrueFillAndLiquidationNotModeled":True}
    return {
      "status":"V9_V7_PAPER_TRADE_RETROSPECTIVE_SUBSET_REPORT_NOT_CAUSAL_COUNTERFACTUAL",
      "baselineFromOriginalProspectivelyRecordedV7PaperExits":True,
      "target":"Positive mean net R, reasonable trade count and drawdown after costs",
      "originalV7PaperTradeMetrics":{s:metrics(full[s]) for s in CANDIDATES},
      "hypotheticalOnlySealedV9AlignedTradeSubset":{
          s:metrics(gated[s]) for s in CANDIDATES},
      "originalV7TradeCount":sum(map(len,full.values())),
      "gatedSubsetCount":sum(map(len,gated.values())),
      "gatingWithoutFullStrategyReplayCannotProveHigherProfit":True,
      "unobservedCounterfactualTradesMustNotBeFilledIn":True,
      "requiresFreshOutOfSampleProspectiveSignals":True,
      "fundingAndActualExecutionNotModeled":True,
      "cannotAutoEnableNotifications":True,
      "noOrders":True,"noNotifications":True,"noProductionModified":True}


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--v7",default=DEFAULT_V7)
    p.add_argument("--v9",default=DEFAULT_V9)
    p.add_argument("--sealed",default=DEFAULT_PRESTART)
    p.add_argument("--latest",default="forward/v9_v7_trade_overlay/latest.json")
    p.add_argument("--snapshot-dir",default="forward/v9_v7_trade_overlay/hourly")
    p.add_argument("--score",default="forward/v9_v7_trade_overlay/paper_trade_scoreboard.json")
    a=p.parse_args()
    v7=Path(a.v7);v9=Path(a.v9)
    if not v7.is_dir() or not v9.is_dir():
        raise ValueError("V7_V9_ORIGINAL_HOURLY_ARCHIVE_MISSING")
    matches={p.name:p for p in v7.glob("*.json")}
    hourly={p.name:p for p in v9.glob("*.json")}
    current=int(datetime.now(timezone.utc).timestamp())
    # Latest matching exact 1H records; MAX 58m after hourly close to avoid
    # retrospective generation falsely treated as a live overlay.
    names=sorted(set(matches)&set(hourly),reverse=True)
    matched=None
    for n in names:
        end=ts(n.replace("Z.json","Z").replace("T", "T").replace("-00Z",":00:00Z")) if False else None
        # Actual Git filenames: YYYY-MM-DDTHH-00Z.json
        stamp=n.replace("-00Z.json",":00:00Z")
        try:
            close=ts(stamp)
        except (ValueError,OverflowError):
            continue
        if 0<=current-close<=58*60:
            matched=(n,close)
            break
    if matched is None:
        print("V9_V7_NO_CONTEMPORANEOUS_MATCHED_ORIGINAL_HOURLY_RECORD",flush=True)
        return
    name,end=matched
    s7=json.loads(matches[name].read_text())
    s9=json.loads(hourly[name].read_text())
    target=end//FOUR*FOUR
    chosen=None;commit_time=None
    for path in sorted(Path(a.sealed).glob("*.json")):
        f=json.loads(path.read_text())
        if ts(f["target4HStartUTC"])==target:
            if chosen is not None:raise ValueError("DUPLICATE_V9_TARGET")
            chosen=f
            commit_time=first_commit_epoch(path)
    # Price and chart-signal quality are computed only when ORIGINAL V7
    # has actually saved a fresh BOS watch. Coinalyze tx/bv are never
    # used in quality scoring: independently audited cross-source gaps.
    needs_quality=any(
      s7["results"].get(CONTRACTS[s],{}).get(
          "V7_signal_filter",{}).get("newWatchAtThisClose",[])
      for s in CANDIDATES)
    quality_history=None
    quality_source={
       "status":"NO_ORIGINAL_V7_NEW_WATCH_TO_SCORE"
                if not needs_quality else "SOURCE_NOT_VERIFIED",
       "qualityScoreNotAnOrderOrTradeSignal":True}
    if needs_quality:
        key=(os.getenv("ETH_V7_COINALYZE_API_KEY") or
             os.getenv("SOL_V8_COINALYZE_API_KEY") or
             os.getenv("COINALYZE_API_KEY") or "").strip()
        if not key:
            quality_source["status"]="COINALYZE_READ_ONLY_KEY_UNAVAILABLE_NO_QUALITY_SCORE"
        else:
            from v9_next4h_prestart_paper_capture import get_group
            from urllib.error import HTTPError,URLError
            try:
                quality_history,digest=get_group(
                    "1hour",end-250*HOUR,end,key)
                quality_source.update(
                    status="COINALYZE_THREE_ASSET_250_CLOSED_HOURS_RETRIEVED",
                    sourceSHA256=digest,
                    noProviderTradeCountUsed=True)
            except (ValueError,OSError,HTTPError,URLError,TimeoutError,
                    KeyError,IndexError) as error:
                quality_history=None
                quality_source["status"]="QUALITY_HISTORY_SOURCE_UNAVAILABLE_NO_SCORE"
                quality_source["errorType"]=type(error).__name__
    report=asof_overlay(s7,s9,chosen,commit_time,
                        quality_hour_by_symbol=quality_history)
    report["v9QualitySourceAudit"]=quality_source
    paper=score_trade_subset(a.v7,a.sealed,first_commit_epoch)
    for name,content in ((a.latest,report),(a.score,paper)):
        out=Path(name);out.parent.mkdir(parents=True,exist_ok=True)
        out.write_text(json.dumps(content,ensure_ascii=False,indent=2)+"\n")
    path=Path(a.snapshot_dir)/(matched[0])
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():
        previous=json.loads(path.read_text())
        if previous!=report:raise ValueError("IMMUTABLE_HOURLY_TRADE_OVERLAY_REWRITE_REFUSED")
    else:
        path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("V9_V7_PRIMARY_TRADE_OPPORTUNITY_BRIDGE_RECORDED",
          iso(end),report["original4HForecastLockStatus"],
          "originalV7exits",paper["originalV7TradeCount"],
          "hypotheticalV9gatedExits",paper["gatedSubsetCount"],flush=True)


if __name__=="__main__":
    main()
