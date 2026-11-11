#!/usr/bin/env python3
"""RETROSPECTIVE V7 4H DIRECTION-VOTE PROXY vs FROZEN V9 next 4H COLOR.

A V7 4H+Daily market-context vote is NOT a V7 BOS/retest trading signal.
This comparison is only SAME TARGET future 4H own-open/close color, with
V7 vote actually recorded before T and frozen V9 computed historically
from the strictly causal <=T-1H Coinalyze bars. Never claim V9 was
prospectively time-locked, nor that a GitHub snapshot proves a ChatGPT
notification was delivered. No order, no alert, no changes to V7.

V9 source model fitted through Sep-2026. Nov-2026 is out-of-training,
but replay occurs after outcomes, NOT genuine prospective validation.
"""
import argparse,hashlib,json,math,os
from pathlib import Path
from datetime import datetime,timezone
from v9_next_4h_color_research import (
   DAY,FOUR,HOUR,SYMBOLS,features_at,prepare,iso,ts,wilson,LEAD_SECONDS)
from v9_next4h_prestart_paper_capture import (
   get_group,aggregate_closed_four,verify_daily_vs_hours,EXCHANGE_SYMBOLS)

START=ts("2026-11-03T20:00:00Z")
START_SOURCE_V7=ts("2026-11-03T16:00:00Z")
FEATURE_1H=1000
FEATURE_DAILY=330
V7_KEY={"BTCUSDT":"BTCUSDT_PERP.A","SOLUSDT":"SOLUSDT_PERP.A",
        "ETHUSDT":"ETHUSDT_PERP.A"}
REPLAY_STATUS="RETROSPECTIVE_V7_4H_CONTEXT_VOTE_PROXY_VS_FROZEN_V9_NOT_PROSPECTIVE"


def _check_vote(snap,sym,target,one_by_t,four_by_t,daily_by_end):
    """Only use V7 evidence actually saved before future target opened."""
    if not snap or snap.get("status")!="VERIFIED_PAPER_OBSERVATION":
        return {"status":"MISSING_OR_UNVERIFIED_V7_SOURCE"}
    if ts(snap["observedAtUTC"])>=target:
        return {"status":"V7_SNAPSHOT_CREATED_AFTER_TARGET_START_EXCLUDED"}
    if ts(snap["targetClosed1HUTC"])!=target-HOUR:
        return {"status":"V7_1H_CLOSE_NOT_EXACTLY_PRETARGET"}
    key=V7_KEY[sym]
    try:
        ctx=snap["marketContext"][key]["timeframes"]
        actual1=ctx["1hour"]
        actual4=ctx["4hour"]
        d=ctx["daily"]
        if (ts(actual1["closeTimeUTC"])!=target-HOUR or
            ts(actual4["closeTimeUTC"])!=target-FOUR or
            ts(d["closeTimeUTC"])!=((target-1)//DAY)*DAY):
            return {"status":"V7_TIMEFRAME_TIMESTAMP_MISMATCH"}
        last1=one_by_t[target-2*HOUR]
        last4=four_by_t[target-2*FOUR]
        lastD=daily_by_end[((target-1)//DAY)*DAY]
        comparators=((actual1["candle"],last1),(actual4["candle"],last4),(d["candle"],lastD))
        for a,b in comparators:
            # Independently sourced Coinalyze OHLCV close comparison,
            # tolerate tiny provider rounding, never compare unrelated bars.
            tolerance=max(1e-6,abs(b["c"])*2e-5)
            if abs(float(a["close"])-b["c"])>tolerance:
                return {"status":"V7_COINALYZE_PRICE_PARITY_MISMATCH"}
        vote=actual4["directionVotes"]
        if vote.get("label") not in ("bullish","bearish","mixed"):
            return {"status":"V7_VOTE_UNKNOWN_OR_NOT_SUPPORTED"}
        # A market bias cannot be silently promoted to an actual alert.
        return {
           "status":"VERIFIED_V7_MARKET_CONTEXT_VOTE_NOT_SIGNAL",
           "v7SnapshotObservedUTC":snap["observedAtUTC"],
           "v7Snapshot1HCloseUTC":snap["targetClosed1HUTC"],
           "v7Prior4HCloseUTC":actual4["closeTimeUTC"],
           "v7DailyCloseUTC":d["closeTimeUTC"],
           "v7Prior4HVote":vote["label"],
           "v7DailyVote":d["directionVotes"]["label"],
           "v7CombinedDailyAnd4HAgree":(
              vote["label"]==d["directionVotes"]["label"] and
              vote["label"] in ("bullish","bearish")),
           "mapped4HColorVoteProxy":(
              "GREEN" if vote["label"]=="bullish" else
              "RED" if vote["label"]=="bearish" else None),
           "notAV7TradeSignal":True,
           "chatGPTNotificationDeliveryNotProvenByGithubSnapshot":True,
           "v7ActualFreshBOSWatchCount":sum(
              len(v.get("newWatchAtThisClose",[]))
              for name,v in snap.get("results",{}).get(key,{}).items()
              if name=="V7_signal_filter"),
        }
    except (KeyError,IndexError,TypeError,ValueError):
        return {"status":"V7_CONTEXT_UNREADABLE_OR_INCOMPLETE"}


def freeze_probability(x,model):
    n=model["featureCount"]
    if len(x)!=n:
        raise ValueError("V9_FROZEN_MODEL_FEATURE_LENGTH_MISMATCH")
    if not all(len(model[k])==n for k in
               ("scalerMean","scalerScale","logisticCoefficients")):
        raise ValueError("V9_FROZEN_MODEL_SCHEMA_INVALID")
    z=model["logisticIntercept"]+sum(
        c*(v-mean)/scale for v,c,mean,scale in zip(
            x,model["logisticCoefficients"],model["scalerMean"],
            model["scalerScale"]))
    if not math.isfinite(z):raise ValueError("NON_FINITE_V9_SCORE")
    return 1/(1+math.exp(-max(-50,min(50,z))))


def metrics(items):
    n=len(items)
    wins=sum(x for x in items)
    return {"n":n,"correct":wins,
            "hitRatePct":round(100*wins/n,2) if n else None,
            "wilson95LowerPct":wilson(wins,n),
            "notAnIndependentSampleAcrossCorrelatedAssets":True}


def compare(rows):
    """V9 vs V7 vote on exactly same target/symbol and completed future candle."""
    per={}
    for symbol in SYMBOLS:
        xs=[r for r in rows if r["symbol"]==symbol]
        eligible=[r for r in xs if r["actual4HOwnColor"]!="DOJI"]
        withv=[r for r in eligible if r["v7"]["status"]=="VERIFIED_V7_MARKET_CONTEXT_VOTE_NOT_SIGNAL"]
        matched=[r for r in withv if r["v7"]["mapped4HColorVoteProxy"] is not None]
        winsModel=[r["v9FrozenModelColor"]==r["actual4HOwnColor"] for r in eligible]
        winsV9=[r["v9FrozenModelColor"]==r["actual4HOwnColor"] for r in matched]
        winsV7=[r["v7"]["mapped4HColorVoteProxy"]==r["actual4HOwnColor"] for r in matched]
        same=len(matched)
        modelCorrect=sum(winsV9)
        voteCorrect=sum(winsV7)
        per[symbol]={
           "completed4HTargetsInTest":len(xs),
           "dojiExcluded":len(xs)-len(eligible),
           "frozenV9AllCompleted":metrics(winsModel),
           "v7VerifiedBeforeTarget4HContextAvailable":len(withv),
           "v7VoteProxyAbstentionsMixed":len(withv)-len(matched),
           "v7MissingRejectedLateOrPriceMismatch":len(eligible)-len(withv),
           "pairedSameTarget": {
              "n":same,
              "frozenV9":metrics(winsV9),
              "v7Prior4HTrendVotePROXY":metrics(winsV7),
              "v9MinusV7PercentagePoints":round(100*(modelCorrect-voteCorrect)/same,2) if same else None,
              "v9OnlyCorrect":sum(a and not b for a,b in zip(winsV9,winsV7)),
              "v7OnlyCorrect":sum(b and not a for a,b in zip(winsV9,winsV7)),
              "notAV7StrategyTradeWinRate":True,
              "notForwardProspectiveV9":True,
           },
           "sameTargetOnlyNoCherryPickedV9HighConfidenceFiltering":True,
        }
    return per


def load_v7(v7_dir):
    return {p.name:json.loads(p.read_text()) for p in Path(v7_dir).glob("*.json")}


def replay(asof,key,model_file,v7BTC_SOL,v7ETH,fetch=None):
    if asof<ts("2026-11-11T12:00:00Z"):
        raise ValueError("REPLAY_MUST_RUN_AFTER_FROZEN_MODELS_EXIST_AND_TEST_WINDOW")
    if not key and fetch is None:
        raise ValueError("READ_ONLY_COINALYZE_KEY_REQUIRED")
    if not Path(v7BTC_SOL).is_dir():
        raise ValueError("V7_GITHUB_ORIGINAL_SNAPSHOTS_NOT_CHECKED_OUT")
    model=json.loads(Path(model_file).read_text())
    if model["status"]!="FROZEN_SHADOW_PAPER_MODELS_NOT_PRODUCTION":
        raise ValueError("V9_MODELS_NOT_FROZEN_RESEARCH_ONLY")
    if set(model["symbols"])!=set(SYMBOLS):
        raise ValueError("V9_DIFFERENT_ASSET_SET")
    end=(asof//FOUR)*FOUR
    lo1=end-FEATURE_1H*HOUR
    lowD=(end//DAY-FEATURE_DAILY)*DAY
    one,h1=get_group("1hour",lo1,end,key,fetch)
    daily,hD=get_group("daily",lowD,end,key,fetch)
    raw={}
    for s in SYMBOLS:
        h=one[s];d=daily[s]
        if len(h)!=FEATURE_1H or any(
            x["t"]!=lo1+i*HOUR for i,x in enumerate(h)):
            raise ValueError("V9_1000H_CONTIGUOUS_REQUIRED_"+s)
        if (len(d)!=FEATURE_DAILY or any(
                x["t"]!=lowD+i*DAY for i,x in enumerate(d))):
            raise ValueError("V9_330D_CONTIGUOUS_REQUIRED_"+s)
        if not verify_daily_vs_hours(h,d,end):
            raise ValueError("V9_DAILY_HOURLY_PARITY_UNVERIFIED_"+s)
        raw[s]={"one":h,"four":aggregate_closed_four(h),"daily":d}
        if len(raw[s]["four"])!=FEATURE_1H//4:
            raise ValueError("V9_4H_HISTORY_LENGTH_INVALID")
    prepared=prepare(raw)
    v7_s=load_v7(v7BTC_SOL)
    v7_e=load_v7(v7ETH) if Path(v7ETH).is_dir() else {}
    four_base=raw["BTCUSDT"]["four"]
    if any(raw[s]["four"][i]["t"]!=b["t"] for s in SYMBOLS for i,b in enumerate(four_base)):
        raise ValueError("BTC_ETH_SOL_4H_UNALIGNED")
    byone={s:{b["t"]:b for b in raw[s]["one"]} for s in SYMBOLS}
    byfour={s:{b["t"]:b for b in raw[s]["four"]} for s in SYMBOLS}
    bydaily={s:{b["t"]+DAY:b for b in raw[s]["daily"]} for s in SYMBOLS}
    results=[]
    for i,b in enumerate(four_base):
        target=b["t"]
        if not (START<=target and target+FOUR<=end):
            continue
        features={s:features_at(s,prepared,i) for s in SYMBOLS}
        if any(z is None for z in features.values()):
            raise ValueError("FROZEN_REPLAY_FEATURES_MISSING")
        combined=tuple(v for s in SYMBOLS for v in features[s])
        date=datetime.fromtimestamp(target,timezone.utc)
        th=2*math.pi*date.hour/24; week=2*math.pi*date.weekday()/7
        x=combined+(math.sin(th),math.cos(th),math.sin(week),math.cos(week))
        if len(x)!=94:
            raise ValueError("FROZEN_FEATURES_NOT_94")
        snapname=datetime.fromtimestamp(target-HOUR,timezone.utc).strftime("%Y-%m-%dT%H-00Z.json")
        for s in SYMBOLS:
            candle=raw[s]["four"][i]
            if candle["t"]+FOUR>end:
                raise ValueError("FUTURE_TARGET_NOT_CLOSED")
            actual=("GREEN" if candle["c"]>candle["o"] else
                    "RED" if candle["c"]<candle["o"] else "DOJI")
            p=freeze_probability(x,model["symbols"][s])
            prediction="GREEN" if p>=.5 else "RED"
            v7file=(v7_e if s=="ETHUSDT" else v7_s).get(snapname)
            v7row=_check_vote(v7file,s,target,byone[s],byfour[s],bydaily[s])
            results.append({
              "symbol":s,
              "target4HStartUTC":iso(target),
              "target4HEndUTC":iso(target+FOUR),
              "hypotheticalV9AsOfBeforeStartUTC":iso(target-LEAD_SECONDS),
              "v9PredictionActuallyGeneratedAtHistoricalReplay":True,
              "v9FrozenModelColor":prediction,
              "v9PgreenUncalibrated":round(p,6),
              "v9TrainingCutoffUTC":model["cutoffUTC"],
              "v7":v7row,
              "actual4HOwnColor":actual,
              "actualOpen":candle["o"],
              "actualClose":candle["c"],
              "v9Correct":prediction==actual if actual!="DOJI" else None,
              "notTrueProspectiveForecast":True,
            })
    if not results:
        raise ValueError("NO_TEST_TARGETS_AVAILABLE")
    per=compare(results)
    return {
      "status":REPLAY_STATUS,
      "generatedAtUTC":iso(asof),
      "periodStartUTC":iso(START),
      "lastEvaluable4HClosesAtUTC":iso(end),
      "targetDefinition":"GREEN iff target own close > own open, RED iff <, DOJI excluded",
      "V7ProxyDefinition":"V7 PRIOR fully closed 4H trend vote as recorded in GitHub verified 1H snapshot T-1H",
      "V7ActualTradingSignalDifferentTarget":True,
      "V7GitHubSnapshotNotProofOfChatGPTNotificationDelivery":True,
      "V9PredictionsReplayedOnlyAfterOutcomesAlreadyKnown":True,
      "notGenuineProspectiveV9":True,
      "frozenModelWeightsNotRetuned":True,
      "exactlySame4HTargetsForPairedComparisons":True,
      "historicalAfterTrainingCutoffButAlreadyInspectedByProject":True,
      "source4HResampledFrom1H":True,
      "sourceHashes":{"Coinalyze1Hour":h1,"CoinalyzeDaily":hD},
      "v7OriginalSnapshotsBTC_SOL":len(v7_s),
      "v7OriginalSnapshotsETH":len(v7_e),
      "perAsset":per,
      "rows":results,
      "noTradingOrders":True,
      "noUserNotifications":True,
      "noPromotionToLiveSignals":True,
    }


def report_md(r):
    out=["# V7 original 4H market-bias votes vs frozen V9 retrospective 4H own-candle color",
         "",
         f"**Test window:** {r['periodStartUTC']} to {r['lastEvaluable4HClosesAtUTC']}.",
         "",
         "**CRITICAL:** V7 is a real prior-hour GitHub paper snapshot, but its **4H trend vote is NOT a V7 BOS/retest trading signal**. "
         "The V9 frozen model colors below were **replayed after outcomes had already occurred**. "
         "Therefore this study does not establish prospective accuracy or justify notifications.",
         "",
         "| Asset | V9 all 4H (hits/N) | Paired N | V9 paired | V7 prior 4H vote PROXY | Difference pp |",
         "|---|---:|---:|---:|---:|---:|"]
    for s,x in r["perAsset"].items():
        a=x["frozenV9AllCompleted"]
        p=x["pairedSameTarget"]
        f=lambda d: f"{d['correct']}/{d['n']} ({d['hitRatePct']}%)" if d["n"] else "N/A"
        out.append(f"| {s} | {f(a)} | {p['n']} | {f(p['frozenV9'])} "
                   f"| {f(p['v7Prior4HTrendVotePROXY'])} | "
                   f"{p['v9MinusV7PercentagePoints']} |")
    out+=["","## Why this does not compare V7 strategy trade win rates",
          "V7's original BOS/retest trade performance measures hypothetical entry, stop, and TP outcomes across multiple 1H candles, "
          "not the own-body color of next 4H. The V7 4H vote is only a direction-context baseline. "
          "Missing V7 forward snapshots, mixed votes and post-target observations are excluded rather than backfilled. "
          "Official V9 forward locked paper journal remains separate and unaffected.",
          "",
          "Source: BTC/SOL V7 GitHub experiment branch forward/snapshots and ETH independent V7 forward/eth/snapshots; "
          "read-only Coinalyze BTC/ETH/SOL Binance perpetual 1H and Daily; frozen V9 model, no training or fitted thresholds.",
          "",
          "## Last six paired evidence rows (per asset)"]
    for s in SYMBOLS:
        rows=[x for x in r["rows"] if x["symbol"]==s and
              x["v7"]["status"]=="VERIFIED_V7_MARKET_CONTEXT_VOTE_NOT_SIGNAL"]
        out+=["",f"**{s}**"]
        for x in rows[-6:]:
            v=x["v7"]
            out.append("- "+x["target4HStartUTC"]+
                       " V9(replayed)="+x["v9FrozenModelColor"]+
                       " V7(4H vote proxy)="+str(v["mapped4HColorVoteProxy"])+
                       " Actual="+x["actual4HOwnColor"])
    return "\n".join(out)+"\n"


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--v7",default="v7_evidence/forward/snapshots")
    p.add_argument("--eth",default="v7_evidence/forward/eth/snapshots")
    p.add_argument("--models",default="forward/v9_next_4h_color/frozen_models.json")
    p.add_argument("--output",default="forward/v9_v7_matched_historical_4h/compare.json")
    p.add_argument("--markdown",default="forward/v9_v7_matched_historical_4h/compare.md")
    a=p.parse_args()
    key=(os.getenv("ETH_V7_COINALYZE_API_KEY") or
         os.getenv("SOL_V8_COINALYZE_API_KEY") or
         os.getenv("COINALYZE_API_KEY") or "").strip()
    now=int(datetime.now(timezone.utc).timestamp())
    r=replay(now,key,a.models,a.v7,a.eth)
    for path,content in ((a.output,json.dumps(r,ensure_ascii=False,indent=2)+"\n"),
                         (a.markdown,report_md(r))):
        dest=Path(path);dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_text(content)
    print("V7_V9_SAME_NEXT4H_OWN_COLOR_HISTORICAL_REPLAY_NO_ALERTS",
          json.dumps({s:v["pairedSameTarget"] for s,v in r["perAsset"].items()},sort_keys=True),flush=True)


if __name__=="__main__":
    main()
