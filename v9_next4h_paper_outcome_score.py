#!/usr/bin/env python3
"""V9 after-close paper GREEN/RED outcome recorder, never trades.

Only score immutable pre-start files committed BEFORE the target 4H opened.
The exact result is the target 4H's OWN O/C built from four verified,
complete consecutive Coinalyze Binance USD-M perpetual 1H candles.
Never label based on previous 4H close, 1H partial, futures of another
symbol, manipulated timestamps or fabricated missing candles.
No backfilling missed predictions. Doji excluded from denominator.

Outputs separate paper_outcomes/<target>.json, never modifies a prediction.
Cumulative metrics are computed from completed forecast+outcome PAIRS,
with denominators and abstention rates; no unsupported 75% declaration.
These are research forecasts using 2026-09 frozen weights, not orders.
"""
from datetime import datetime,timezone
from hashlib import sha256
from pathlib import Path
import argparse,json,math,os

from v9_next4h_prestart_paper_capture import (
    get_group,EXCHANGE_SYMBOLS,FOUR,HOUR,SYMBOLS,
    EARLIEST_MINUTES_BEFORE,LATEST_MINUTES_BEFORE,PAPER_STATUS)
from v9_next_4h_color_research import iso,ts,wilson

PREDICTIONS="forward/v9_next_4h_color/paper_forecasts"
OUTCOMES="forward/v9_next_4h_color/paper_outcomes"


def stable_bytes(value):
    return json.dumps(value,sort_keys=True,ensure_ascii=False,
                      separators=(",",":")).encode("utf-8")


def verify_prior_forecast(forecast,models=None):
    if forecast.get("status")!=PAPER_STATUS:
        raise ValueError("NOT_A_VALID_BEFORE_START_PAPER_FORECAST")
    start=ts(forecast["target4HStartUTC"])
    end=ts(forecast["target4HEndUTC"])
    decided=ts(forecast["decisionCapturedUTC"])
    if start%FOUR or end-start!=FOUR:
        raise ValueError("TARGET_4H_NOT_ALIGNED")
    if not (LATEST_MINUTES_BEFORE*60<=start-decided<=EARLIEST_MINUTES_BEFORE*60):
        raise ValueError("FORECAST_WAS_NOT_CAPTURED_BEFORE_START")
    if forecast.get("noTargetOpenKnown") is not True:
        raise ValueError("FORECAST_CONTAINS_FUTURE_OPEN")
    if forecast.get("brokerOrders") is not False or forecast.get("productionModified") is not False:
        raise ValueError("PAPER_FORECAST_MAY_NOT_TRADE")
    if set(forecast.get("assetForecasts",{}))!=set(SYMBOLS):
        raise ValueError("INCORRECT_PAPER_FORECAST_ASSETS")
    for s,row in forecast["assetForecasts"].items():
        if row.get("direction") not in ("GREEN","RED"):
            raise ValueError("UNKNOWN_PROPOSED_COLOR")
        p=row.get("pGreenUNCALIBRATED")
        if type(p) not in (int,float) or not math.isfinite(p) or not 0<=p<=1:
            raise ValueError("FORECAST_PROBABILITY_UNUSABLE")
        if row["direction"]!=("GREEN" if p>=.5 else "RED"):
            raise ValueError("FORECAST_DIRECTION_MISMATCH_PROBABILITY")
        lagged=row.get("lastCompleted4HColorBaseline")
        if lagged is not None:
            if lagged not in ("GREEN","RED","DOJI"):
                raise ValueError("UNVERIFIED_COMPLETED_4H_COLOR_BASELINE")
            if (row.get("baselineClosedAtUTC")!=iso(start-FOUR) or
                row.get("baselineUsesOnlyCandleClosedBeforeTarget") is not True):
                raise ValueError("BASELINE_IS_NOT_CAUSALLY_AVAILABLE_BEFORE_TARGET")
        if models is not None:
            if row.get("modelTrainingLabelsSHA256")!=models["symbols"][s]["trainingLabelsSHA256"]:
                raise ValueError("FROZEN_MODEL_TRAIN_HASH_CHANGED")
    shadow=forecast.get("researchOnlyShadow88NoProviderTradeCount")
    if shadow is not None:
        if (shadow.get("status")!="FROZEN_88_NO_PROVIDER_TX_PARALLEL_PAPER_NOT_PROMOTED"
            or shadow.get("modelFeatureCount")!=88
            or shadow.get("sixTransactionCountFeaturePositionsDropped")!=[20,27,50,57,80,87]
            or shadow.get("sameOriginalDecisionAnd4HTarget") is not True
            or shadow.get("neverEnableNotificationsFromThisExperiment") is not True
            or set(shadow.get("shadowAssetForecasts",{}))!=set(SYMBOLS)):
            raise ValueError("FROZEN_88_PARALLEL_SHADOW_INVALID")
        for sym,row in shadow["shadowAssetForecasts"].items():
            p=row.get("pGreenUNCALIBRATED")
            if (type(p) not in (int,float) or not math.isfinite(p)
                or not 0<=p<=1 or row.get("direction") not in ("GREEN","RED")
                or row["direction"]!=("GREEN" if p>=.5 else "RED")
                or row.get("noCoinalyzeTXUsedInFeatureVector") is not True
                or row.get("notATradingSignal") is not True):
                raise ValueError("SHADOW_88_PAPER_DIRECTION_OR_SOURCE_INVALID")
            if models is not None and (
                row.get("modelTrainingLabelsSHA256")!=models["symbols"][sym]["trainingLabelsSHA256"]):
                raise ValueError("SHADOW_TRAIN_LABEL_HASH_CHANGED")
    return start,end


def score_one(now,forecast,key,models=None,fetch=None):
    start,end=verify_prior_forecast(forecast,models)
    if now<end+180:
        raise ValueError("TARGET_NOT_YET_CLOSED_PLUS_PUBLICATION_BUFFER")
    # Query the four 1H source bars of target interval only. Even if
    # scoring is days late, source data newer than target end is unavailable
    # to label creation and cannot bias outcome construction.
    grouped,source_sha=get_group("1hour",start,end,key,fetch)
    observed={}
    for symbol in SYMBOLS:
        bars=grouped[symbol]
        if len(bars)!=4 or any(b["t"]!=start+i*HOUR for i,b in enumerate(bars)):
            raise ValueError("TARGET_1H_NOT_FOUR_COMPLETE_BARS_"+symbol)
        op=bars[0]["o"]
        cl=bars[-1]["c"]
        actual=("GREEN" if cl>op else "RED" if cl<op else "DOJI")
        prior=forecast["assetForecasts"][symbol]
        predicted=prior["direction"]
        prior_baseline=prior.get("lastCompleted4HColorBaseline")
        shadow=forecast.get("researchOnlyShadow88NoProviderTradeCount")
        shadow_pred=shadow["shadowAssetForecasts"][symbol] if shadow is not None else None
        observed[symbol]={
            "noProviderTx88ShadowPrediction":(
                shadow_pred["direction"] if shadow_pred is not None else None),
            "noProviderTx88ShadowPgreenUncalibrated":(
                shadow_pred["pGreenUNCALIBRATED"] if shadow_pred is not None else None),
            "noProviderTx88ShadowCorrect":(
                shadow_pred["direction"]==actual
                if shadow_pred is not None and actual!="DOJI" else None),
            "lastCompleted4HColorBaseline":prior_baseline,
            "lastCompleted4HColorBaselineCorrect":(
                prior_baseline==actual if actual!="DOJI" and
                  prior_baseline in ("GREEN","RED") else None),
            "target4HOpen":op,
            "target4HClose":cl,
            "actual4HOwnOpenCloseColor":actual,
            "predicted4HColor":predicted,
            "correct":(predicted==actual) if actual!="DOJI" else None,
            "targetOwnOpenClosePct":round(100*(cl/op-1),6),
            "predictedPgreenUncalibrated":forecast["assetForecasts"][symbol]["pGreenUNCALIBRATED"],
            "sourceFourCompleteOneHourBars":True,
            "noPreviousCloseComparison":True}
    return {
        "status":"V9_REAL_PAPER_4H_OWN_COLOR_SCORED",
        "predictionMadeUTC":forecast["decisionCapturedUTC"],
        "target4HStartUTC":forecast["target4HStartUTC"],
        "target4HEndUTC":forecast["target4HEndUTC"],
        "scoredUTC":iso(now),
        "forecastCanonicalSHA256":sha256(stable_bytes(forecast)).hexdigest(),
        "targetOHLCVSourceSHA256":source_sha,
        "symbols":observed,
        "allThreeIndependentSourceBars":True,
        "dojiCount":sum(x["actual4HOwnOpenCloseColor"]=="DOJI" for x in observed.values()),
        "noTradingOrders":True,
        "productionEdited":False,
        "confidenceNotCalibrated":True,
        "historicalModelWasNotProspectivelyValidated":True}


def tally(events):
    qualified=[x for x in events if x["correct"] is not None]
    wins=sum(x["correct"] for x in qualified)
    n=len(qualified)
    total=len(events)
    brier=(sum((x["p"]-(x["actual"]=="GREEN"))**2 for x in qualified)/n
           if n else None)
    return {
      "forecastsCaptured":total,
      "dojiExcluded":total-n,
      "evaluable":n,
      "correct":wins,
      "hitRatePct":round(100*wins/n,2) if n else None,
      "wilson95LowerPct":wilson(wins,n),
      "brierScore":round(brier,5) if brier is not None else None,
      "atLeast100NewForecasts":n>=100,
      "notAProfitOrTradingResult":True,
    }


def scoreboard(predictions,outcomes):
    """No doubles or unmatched scored cases. Missing future outcomes remain pending."""
    mapping={}
    for prediction in predictions:
        start,_=verify_prior_forecast(prediction)
        if start in mapping:raise ValueError("DUPLICATE_TARGET_FORECAST")
        mapping[start]=prediction
    completed={}
    for outcome in outcomes:
        if outcome.get("status")!="V9_REAL_PAPER_4H_OWN_COLOR_SCORED":
            raise ValueError("NOT_A_REAL_PAPER_RESULT")
        start=ts(outcome["target4HStartUTC"])
        if start in completed:raise ValueError("DUPLICATE_TARGET_OUTCOME")
        pred=mapping.get(start)
        if pred is None:raise ValueError("RETROSPECTIVE_RESULT_WITHOUT_PRIOR_FORECAST")
        if sha256(stable_bytes(pred)).hexdigest()!=outcome["forecastCanonicalSHA256"]:
            raise ValueError("ORIGINAL_FORECAST_CHANGED_AFTER_RESULT")
        if set(outcome.get("symbols",{}))!=set(SYMBOLS):
            raise ValueError("SCORE_RESULT_MISSING_ASSETS")
        completed[start]=outcome
    per={}
    for symbol in SYMBOLS:
        entries=[]
        for start,outcome in sorted(completed.items()):
            row=outcome["symbols"][symbol]
            pred=mapping[start]["assetForecasts"][symbol]
            if (row["predicted4HColor"]!=pred["direction"] or
                row["predictedPgreenUncalibrated"]!=pred["pGreenUNCALIBRATED"]):
                raise ValueError("SCORED_PREDICTION_CHANGED_"+symbol)
            prior_baseline=pred.get("lastCompleted4HColorBaseline")
            prior_shadow=mapping[start].get("researchOnlyShadow88NoProviderTradeCount")
            if prior_shadow is not None:
                immutable_shadow=prior_shadow["shadowAssetForecasts"][symbol]
                if (row.get("noProviderTx88ShadowPrediction")!=immutable_shadow["direction"]
                    or row.get("noProviderTx88ShadowPgreenUncalibrated")!=immutable_shadow["pGreenUNCALIBRATED"]):
                    raise ValueError("FROZEN_88_SHADOW_CHANGED_AFTER_FORECAST")
            elif row.get("noProviderTx88ShadowPrediction") is not None:
                raise ValueError("SHADOW_SCORE_WITHOUT_PRESTART_FORECAST")
            if (prior_baseline is not None and
                row.get("lastCompleted4HColorBaseline")!=prior_baseline):
                raise ValueError("BASELINE_WAS_MODIFIED_AFTER_FORECAST")
            entries.append({
                "correct":row["correct"],
                "actual":row["actual4HOwnOpenCloseColor"],
                "p":row["predictedPgreenUncalibrated"],
                "baselineCorrect":row.get("lastCompleted4HColorBaselineCorrect")
                    if prior_baseline is not None else None,
                "shadowNoTx88Correct":row.get("noProviderTx88ShadowCorrect")
                    if prior_shadow is not None else None})
        matched=[z for z in entries if
                 z["correct"] is not None and z["baselineCorrect"] is not None]
        n_matched=len(matched)
        model_wins=sum(z["correct"] for z in matched)
        lagged_wins=sum(z["baselineCorrect"] for z in matched)
        model_only=sum(z["correct"] and not z["baselineCorrect"] for z in matched)
        baseline_only=sum(z["baselineCorrect"] and not z["correct"] for z in matched)
        paired_comparison={
           "matchedSameTarget4HColorEvents":n_matched,
           "modelCorrect":model_wins,
           "laggedClosed4HColorCorrect":lagged_wins,
           "modelHitRatePct":round(100*model_wins/n_matched,2)
                             if n_matched else None,
           "laggedBaselineHitRatePct":round(100*lagged_wins/n_matched,2)
                                      if n_matched else None,
           "modelMinusBaselinePercentagePoints":round(
              100*(model_wins-lagged_wins)/n_matched,2)
              if n_matched else None,
           "modelOnlyCorrect":model_only,
           "baselineOnlyCorrect":baseline_only,
           "atLeast200PairedProspectiveCandles":n_matched>=200,
           "doesNotDemonstrateV7SuperiorityBecauseV7UsesDifferentTarget":True,
           "notEnoughAloneToEnableNotifications":True,
        }
        paired_shadows=[z for z in entries if
            z["correct"] is not None and z["shadowNoTx88Correct"] is not None]
        n_shadow=len(paired_shadows)
        base_correct=sum(z["correct"] for z in paired_shadows)
        shadow_correct=sum(z["shadowNoTx88Correct"] for z in paired_shadows)
        paired_shadow={
            "matchedSameFuture4HOwnCandle":n_shadow,
            "frozenOriginal94Correct":base_correct,
            "sourceMotivatedNoTx88Correct":shadow_correct,
            "frozenOriginal94HitRatePct":round(100*base_correct/n_shadow,2)
               if n_shadow else None,
            "noTx88HitRatePct":round(100*shadow_correct/n_shadow,2)
               if n_shadow else None,
            "noTx88MinusOriginal94PercentagePoints":round(
                 100*(shadow_correct-base_correct)/n_shadow,2)
                if n_shadow else None,
            "noTx88OnlyCorrect":sum(z["shadowNoTx88Correct"] and not z["correct"]
                                   for z in paired_shadows),
            "original94OnlyCorrect":sum(z["correct"] and not z["shadowNoTx88Correct"]
                                        for z in paired_shadows),
            "minimum200ProspectivePairsForInterpretation":n_shadow>=200,
            "cannotChangeNotificationsBasedOnThisResearch":True,
        }
        per[symbol]={
            "matchedNoProviderTX88ShadowVsOriginal94":paired_shadow,
            "matchedNext4HOwnColorBaselineComparison":paired_comparison,
            "all":tally(entries),
            "atLeast55pctConfidence":tally([z for z in entries if max(z["p"],1-z["p"])>=.55]),
            "atLeast60pctConfidence":tally([z for z in entries if max(z["p"],1-z["p"])>=.60]),
            "atLeast65pctConfidence":tally([z for z in entries if max(z["p"],1-z["p"])>=.65]),
        }
    # A missing scheduled paper capture must NEVER disappear silently.
    # Within the span of the FIRST to LAST captured forecasts count every
    # four-hour slot, including those with no forecast, as missing.
    # This is comparable with the per-prediction hit rate only alongside
    # a coverage denominator, not as a guaranteed six-per-day count.
    starts=sorted(mapping)
    expected_slots=(starts[-1]-starts[0])//FOUR+1 if starts else 0
    if expected_slots<len(mapping):
        raise ValueError("NON_FOUR_HOUR_ALIGNED_PAPER_SERIES")
    missing_slots=expected_slots-len(mapping)
    return {
       "status":"V9_FORWARD_PAPER_SCOREBOARD_RESEARCH_ONLY",
       "firstForecastTargetUTC":iso(starts[0]) if starts else None,
       "lastForecastTargetUTC":iso(starts[-1]) if starts else None,
       "expectedFourHourSlotsBetweenFirstAndLast":expected_slots,
       "missingScheduledForecastSlotsBetweenFirstAndLast":missing_slots,
       "captureCoveragePct":round(100*len(mapping)/expected_slots,2)
           if expected_slots else None,
       "totalPriorTargetForecasts":len(mapping),
       "completedTargetForecasts":len(completed),
       "pendingOrMissingTargetResults":len(mapping)-len(completed),
       "allSymbols":per,
       "mustKeepAllForecastsEvenIfWrong":True,
       "confidenceUncalibrated":True,
       "no75PercentClaimUntilProspectiveEfficacy":True,
       "notificationPromotionEligibility":"BLOCKED_PENDING_MATCHED_V7_OR_OTHER_EQUIVALENT_4H_TARGET_AND_PROSPECTIVE_RESULTS",
       "notificationActivationRequested":False,
       "noUserNotifications":True,
       "realOrders":False,
       "productionModified":False}


def load_models(path):
    x=json.loads(Path(path).read_text())
    if x.get("status")!="FROZEN_SHADOW_PAPER_MODELS_NOT_PRODUCTION":
        raise ValueError("MODEL_STATUS_NOT_FROZEN")
    return x


def main():
    a=argparse.ArgumentParser()
    a.add_argument("--prediction-dir",default=PREDICTIONS)
    a.add_argument("--outcome-dir",default=OUTCOMES)
    a.add_argument("--models",default="forward/v9_next_4h_color/frozen_models.json")
    a.add_argument("--scoreboard",default="forward/v9_next_4h_color/paper_scoreboard.json")
    args=a.parse_args()
    forecasts=[json.loads(f.read_text()) for f in sorted(Path(args.prediction_dir).glob("*.json"))]
    outcomes=[json.loads(f.read_text()) for f in sorted(Path(args.outcome_dir).glob("*.json"))]
    models=load_models(args.models)
    now=int(datetime.now(timezone.utc).timestamp())
    key=(os.getenv("ETH_V7_COINALYZE_API_KEY") or
         os.getenv("SOL_V8_COINALYZE_API_KEY") or
         os.getenv("COINALYZE_API_KEY") or "").strip()
    for p in forecasts:
        start,end=verify_prior_forecast(p,models)
        if now<end+180:continue
        result_name=p["target4HStartUTC"].replace(":","-")+".json"
        dest=Path(args.outcome_dir)/result_name
        if dest.exists():continue
        if not key:raise ValueError("MISSING_READONLY_KEY_FOR_AFTER_CLOSE_SCORING")
        result=score_one(now,p,key,models)
        dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
        outcomes.append(result)
        print("V9_PAPER_RESULT_POST_CLOSE",p["target4HStartUTC"],
              {s:z["correct"] for s,z in result["symbols"].items()},flush=True)
    table=scoreboard(forecasts,outcomes)
    path=Path(args.scoreboard);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(table,ensure_ascii=False,indent=2)+"\n")
    print("V9_PROSPECTIVE_PAPER_SCOREBOARD",json.dumps({
        s:x["all"] for s,x in table["allSymbols"].items()}),flush=True)


if __name__=="__main__":
    main()
