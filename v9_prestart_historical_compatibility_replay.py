#!/usr/bin/env python3
"""V9 pre-start live-provider parser REPLAY, strictly NOT a forward prediction.

Runs a frozen model on historical as-of input limited to T-17min (Coinalyze
read-only API). Runs AFTER the target 4H has begun and therefore only
validates source/feature compatibility. No directions are ever published.
NO paper forecast or outcome files are written. Never count as success.
"""
from datetime import datetime,timezone
from pathlib import Path
import json,os
from v9_next4h_prestart_paper_capture import snapshot
from v9_next_4h_color_research import iso

REPLAY_ASOF_UTC="2026-11-11T07:43:00Z"


def main():
    actual=int(datetime.now(timezone.utc).timestamp())
    asof=int(datetime.fromisoformat(REPLAY_ASOF_UTC.replace("Z","+00:00")).timestamp())
    if actual<=asof:
        raise ValueError("REPLAY_TIME_MUST_ALREADY_BE_IN_PAST")
    models=json.loads(Path("forward/v9_next_4h_color/frozen_models.json").read_text())
    shadow_models=json.loads(Path(
        "forward/v9_no_tx_ablation/frozen_models_research_only.json").read_text())
    key=(os.getenv("ETH_V7_COINALYZE_API_KEY") or
         os.getenv("SOL_V8_COINALYZE_API_KEY") or
         os.getenv("COINALYZE_API_KEY") or "").strip()
    if not key:
        raise ValueError("READONLY_SOURCE_KEY_MISSING")
    value=snapshot(asof,models,key,shadow_models_no_tx=shadow_models)
    assert value["status"]=="BEFORE_START_PAPER_FORECAST_UNCALIBRATED_NOT_TRADE"
    assert value["target4HStartUTC"]=="2026-11-11T08:00:00Z"
    assert len(value["assetForecasts"])==3
    for row in value["assetForecasts"].values():
        assert row["featuresReplayed"]==94
        assert row["predictionOnlyNotAnOrder"] is True
    shadow=value["researchOnlyShadow88NoProviderTradeCount"]
    assert shadow["status"]=="FROZEN_88_NO_PROVIDER_TX_PARALLEL_PAPER_NOT_PROMOTED"
    assert shadow["modelFeatureCount"]==88
    assert set(shadow["shadowAssetForecasts"])==set(value["assetForecasts"])
    assert all(v["noCoinalyzeTXUsedInFeatureVector"]
               for v in shadow["shadowAssetForecasts"].values())
    assert value["noUserNotifications"] and not value["brokerOrders"]
    from v9_next4h_paper_outcome_score import verify_prior_forecast
    verify_prior_forecast(value,models)
    report={
       "status":"HISTORICAL_SOURCE_FEATURE_REPLAY_NOT_A_REAL_PAPER_PREDICTION",
       "asOfInputUTC":REPLAY_ASOF_UTC,
       "actualRunUTC":iso(actual),
       "target4HStartUTC":value["target4HStartUTC"],
       "historicalAsOfWasBeforeTargetOpenButExecutedAfterOpen":True,
       "sourcesLimitTheirToTimestamp":True,
       "frozenModelFeatureCountPerAsset":{s:r["featuresReplayed"]
                                          for s,r in value["assetForecasts"].items()},
       "allThreeCoinalyze1HAndDailyIntegrated":True,
       "original94PlusNoCoinalyzeTx88BothReplayedFromIdenticalAsOf":True,
       "experimental88FeatureCountPerAsset":{
           s:shadow["modelFeatureCount"] for s in shadow["shadowAssetForecasts"]},
       "notProspectiveAsBothWereExecutedAfterTargetOpen":True,
       "noUserNotifications":True,
       "sourceSHA256":{"oneHour":value["ohlcv1hResponseSHA256"],
                       "daily":value["dailyResponseSHA256"]},
       "noPaperForecastCreated":True,
       "mustNeverEnterProspectiveAccuracyDenominator":True,
       "noBrokerOrders":True}
    out=Path("forward/v9_next_4h_color/historical_compatibility_replay.json")
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("V9_HISTORICAL_ASOF_SOURCE_FEATURE_REPLAY_PASSED_NEVER_SCORE_AS_PAPER",report["target4HStartUTC"])


if __name__=="__main__":
    main()
