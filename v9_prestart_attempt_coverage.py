#!/usr/bin/env python3
"""V9 4H attempt coverage accounting since live paper research started.

An absent forecast is MISSED, never treated as a predicted RED/GREEN,
a successful no-signal, or removed from the coverage denominator.
Only committed strict lead-time files (validated using original scorer)
count as prospective capture. Never backfill a missed capture. No orders.
"""
from datetime import datetime,timezone
from pathlib import Path
import argparse,json

from v9_next4h_paper_outcome_score import verify_prior_forecast
from v9_next_4h_color_research import FOUR,iso,ts

DEPLOY_START=ts("2026-11-11T00:00:00Z")


def coverage(forecasts,now,deploy=DEPLOY_START):
    if deploy%FOUR:
        raise ValueError("COVERAGE_DEPLOY_MUST_ALIGN_4H")
    if now<deploy:raise ValueError("BEFORE_COVERAGE_DEPLOY")
    starts={}
    for file in forecasts:
        rec=file if isinstance(file,dict) else json.loads(Path(file).read_text())
        start,_=verify_prior_forecast(rec)
        if start in starts:raise ValueError("DUPLICATE_FORECAST_FOR_4H")
        if start<deploy:
            raise ValueError("FORECAST_TARGET_BEFORE_COVERAGE_DEPLOY")
        starts[start]=rec
    # Every 4H candle which ALREADY STARTED is accounted for. Skip active
    # latest boundary only if T is exactly NOW, since target has just begun.
    last=(now-1)//FOUR*FOUR
    if last<deploy:
        slots=[]
    else:
        slots=list(range(deploy,last+1,FOUR))
    captured=[t for t in slots if t in starts]
    missed=[t for t in slots if t not in starts]
    pending_future=[t for t in starts if t>last]
    return {
      "status":"V9_PRESTART_4H_PAPER_CAPTURE_COVERAGE_NO_BACKFILL",
      "asOfUTC":iso(now),
      "deploymentStart4HUTC":iso(deploy),
      "expectedAlreadyStarted4HTargets":len(slots),
      "validForecastsCommittedBeforeOpenPerOriginalFile":len(captured),
      "missed4HBeforeStartPredictionSlots":len(missed),
      "captureCoveragePct":round(100*len(captured)/len(slots),2)
                           if slots else None,
      "missedTargetStartUTC":[iso(t) for t in missed],
      "capturedTargetStartUTC":[iso(t) for t in captured],
      "forecastedTargetStartsNotYetBegunUTC":[iso(t) for t in sorted(pending_future)],
      "missingAreFailuresNotAbstentions":True,
      "noRetrospectiveImputation":True,
      "notAProfitOrDirectionalAccuracy":True,
      "noUserNotifications":True,"brokerOrders":False,"productionModified":False
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--ledger",default="forward/v9_next_4h_color/paper_forecasts")
    p.add_argument("--output",default="forward/v9_next_4h_color/attempt_coverage.json")
    a=p.parse_args()
    now=int(datetime.now(timezone.utc).timestamp())
    src=Path(a.ledger)
    forecasts=[json.loads(f.read_text()) for f in sorted(src.glob("*.json"))]
    result=coverage(forecasts,now)
    out=Path(a.output);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print("V9_4H_MISSED_PREDICTION_SLOTS_NOT_BACKFILLED",result[
          "missed4HBeforeStartPredictionSlots"],"CAPTURED",result[
          "validForecastsCommittedBeforeOpenPerOriginalFile"],flush=True)


if __name__=="__main__":
    main()
