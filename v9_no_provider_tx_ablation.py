#!/usr/bin/env python3
"""V9 source-motivated NO-TRANSACTION-COUNT ablation, training archives only.

Why: Independent official Binance SHA256 vs Coinalyze audits on 29 Oct and
08 Nov 2026 proved 'tx' not equal to Binance numberOfTrades for 48/48h
in BTC ETH SOL. The original model used two trade count features per
asset. Drop those six fixed indices (not hand-pick per outcome), REFIT
the exact same frozen baseline model architecture + 6 predeclared
chronological fold boundaries on the exact same Binance training data.
No re-tuning. Keep original V9 frozen model untouched; research only.

DO NOT treat improved historical results as independent predictive
validation. Coinalyze BTC/ETH and historical anomalous taker volumes
also have residual field gaps. No notifications or trades authorized.
"""
import json,math,argparse
from pathlib import Path
from datetime import datetime,timezone

from v9_next_4h_color_research import (
  SYMBOLS,download_three,prepare,observations,fit_and_predict,overall,
  freeze_future_shadow_models,iso,ts)

BASE_FEATURE_COUNT=94
PER_ASSET=30
DROP_IN_ASSET=(20,27)
DROP_INDICES=tuple(i*PER_ASSET+j for i in range(3) for j in DROP_IN_ASSET)
KEEP_INDICES=tuple(i for i in range(BASE_FEATURE_COUNT)
                   if i not in DROP_INDICES)
assert len(KEEP_INDICES)==88


def strip_transaction_count(x):
    if len(x)!=BASE_FEATURE_COUNT:
        raise ValueError("V9_EXPECTED_EXACT_94_BASE_FEATURES")
    z=tuple(x[i] for i in KEEP_INDICES)
    if len(z)!=88 or not all(math.isfinite(v) for v in z):
        raise ValueError("V9_NO_TX_FEATURE_PROJECTION_INVALID")
    return z


def transform_observations(obs):
    transformed={}
    for symbol,rows in obs.items():
        transformed[symbol]=[]
        for r in rows:
            y={**r,"x":strip_transaction_count(r["x"])}
            transformed[symbol].append(y)
    return transformed


def comparison(new,baseline):
    result={}
    for symbol in SYMBOLS:
        a=new[symbol]["logisticAll"]
        b=baseline[symbol]["logisticAll"]
        if a["predictions"]!=b["predictions"]:
            raise ValueError("V9_NO_TX_BASELINE_EVALUATED_DIFFERENT_FOLD_CANDLES")
        result[symbol]={
          "identicalChronologicalFoldTargetCount":a["predictions"],
          "originalFrozenV9ModelBacktest":b,
          "txFreeV9Backtest":a,
          "accuracyDeltaPercentagePoints":round(a["hitRatePct"]-b["hitRatePct"],2),
          "newModelNotProspectivelyValidated":True,
          "resultsSeenBeforeAnyPromotion":True,
          "cannotEnableNotificationsOrPromoteModelFromThisTest":True}
    return result


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--base-report",default="forward/v9_next_4h_color/latest.json")
    p.add_argument("--output",default="forward/v9_no_tx_ablation/report.json")
    p.add_argument("--models",default="forward/v9_no_tx_ablation/frozen_models_research_only.json")
    a=p.parse_args()
    base=json.loads(Path(a.base_report).read_text())
    if base["status"]!="HISTORICAL_CAUSAL_WALK_FORWARD_RESEARCH_ONLY":
        raise ValueError("ORIGINAL_FOLD_REPORT_NOT_VERIFIED")
    data,source=download_three()
    prepared=prepare(data)
    obs,doji=observations(prepared)
    o=transform_observations(obs)
    folds,fold_rows=fit_and_predict(o)
    agg=overall(fold_rows)
    frozen=freeze_future_shadow_models(o)
    if any(z["featureCount"]!=88 for z in frozen["symbols"].values()):
        raise ValueError("NO_TX_MODEL_NOT_88")
    # Include EXACT transformation in model metadata and explicit no-promotion.
    frozen["status"]="FROZEN_SHADOW_PAPER_MODELS_NOT_PRODUCTION"
    frozen["featureSpace"]="88_OF_ORIGINAL_94_NO_PROVIDER_TX"
    frozen["projectionRemovedFeatureIndices"]=list(DROP_INDICES)
    frozen["projectionOriginalFeatureCount"]=94
    frozen["allTrainingTargetsStillEndBy2026Sep"]=True
    frozen["sourcePortabilityPartiallyVerifiedButTakerBVCanStillDiffer"]=True
    frozen["originalFrozenV9ModelsUntouched"]=True
    frozen["noTradingSignalsOrNotificationsAuthorized"]=True
    frozen["onlyHistoricalAblationNotSelectedAsWinner"]=True
    for z in frozen["symbols"].values():
        z["version"]="V9_NO_PROVIDER_TX_88_FEATURE_ARCHIVE_RESEARCH_SHADOW"
        z["pointInTimeAndCrossAssetFeatureDefinition"]=(
            "v9_next_4h_color_research.py::features_at ->"
            " v9_no_provider_tx_ablation.py::strip_transaction_count")
        z["noActualCoinalyzeTXFeatureUsed"]=True
        z["featuresRemovedDueToObservedSourceMismatch"]=True
    report={
      "status":"V9_NO_TX_88_FEATURE_SOURCE_MISMATCH_MOTIVATED_ABLATION_HISTORICAL",
      "generatedUTC":iso(int(datetime.now(timezone.utc).timestamp())),
      "removedGlobalFeatureIndices":list(DROP_INDICES),
      "reason":"Coinalyze tx differs materially from official Binance numberOfTrades in all 48 audited hours in 3 assets",
      "sameHistoricalArchiveAsOriginalAndNotIndependentHoldout":True,
      "identicalSixChronologicalFoldsAndC0_2Fixed":True,
      "noPastPerformanceSelectionAllowed":True,
      "sameTargetCandlesAsOriginal":True,
      "modelsNeverReplaceOriginalUnlessIndependentlyProspectivelyValidated":True,
      "takerBuyFlowProviderParityNotGuaranteedEveryHour":True,
      "source":source,
      "dojiExcluded":doji,
      "folds":folds,
      "overall":agg,
      "matchedOriginalV9Historical":comparison(agg,base["overall"]),
      "noUserNotifications":True,"brokerOrders":False,"productionModified":False,
      "notActualForwardPaperPerformance":True}
    out=Path(a.output);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    models=Path(a.models);models.parent.mkdir(parents=True,exist_ok=True)
    models.write_text(json.dumps(frozen,ensure_ascii=False,indent=2)+"\n")
    print("V9_NO_TX_MOTIVATED_ABLATION_HISTORICAL_ONLY",json.dumps({
      s:z["accuracyDeltaPercentagePoints"] for s,z in
      report["matchedOriginalV9Historical"].items()}),flush=True)


if __name__=="__main__":
    main()
