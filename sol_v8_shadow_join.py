#!/usr/bin/env python3
"""Strict point-in-time audit join: V7 SOL paper vs V8 read-only derivatives.
No signals are generated, no entries or fills inferred, no order API.
"""
import argparse
import json
from datetime import datetime,timezone
from pathlib import Path

PAIR="SOLUSDT_PERP.A"
V7_MODE="PAPER_FORWARD_OBSERVATION_NO_ORDERS"
V8_MODE="SOL_V8_DERIVATIVES_QUALITY_PROBE_NO_ORDERS"


def timestamp(iso):
    if type(iso) is not str:
        raise ValueError("INVALID_TIME")
    dt=datetime.fromisoformat(iso.replace("Z","+00:00"))
    if dt.tzinfo is None or dt.utcoffset().total_seconds()!=0:
        raise ValueError("TIMESTAMP_NOT_UTC")
    return int(dt.timestamp())


def join(v7,v8):
    a=v7.get("targetClosed1HUTC")
    b=v8.get("targetClosed1HUTC")
    target=timestamp(a)
    if target%3600 or a!=b:
        raise ValueError("TARGET_CLOSED_HOUR_MISMATCH")
    if v7.get("status")!="VERIFIED_PAPER_OBSERVATION":
        raise ValueError("V7_NOT_VERIFIED")
    if v8.get("status")!="DATA_VALIDATED_RESEARCH_ONLY":
        raise ValueError("V8_NOT_VERIFIED")
    if v7.get("mode")!=V7_MODE or v8.get("mode")!=V8_MODE:
        raise ValueError("UNEXPECTED_OBSERVER_MODES")
    if (v7.get("brokerOrders") is not False or
        v8.get("brokerOrders") is not False or
        v7.get("productionSystemModified") is not False or
        v8.get("productionSystemModified") is not False or
        v8.get("liveSignalEnabled") is not False):
        raise ValueError("PAPER_ONLY_SAFETY_VIOLATION")
    t7=timestamp(v7["observedAtUTC"])
    t8=timestamp(v8["observedAtUTC"])
    if not (target < t7 < target+3600 and target < t8 < target+3600):
        raise ValueError("OBSERVED_AFTER_VALID_CLOSED_HOUR_WINDOW")
    if v8.get("symbol")!=PAIR:
        raise ValueError("WRONG_V8_SYMBOL")
    c=v7["marketContext"][PAIR]
    if c.get("checkedClosed1HUTC")!=a:
        raise ValueError("V7_SOL_CONTEXT_WRONG_HOUR")
    oi=v8["openInterest"]
    buy=v8["providerBuyVolume"]
    funding=v8["funding"]
    if oi.get("asOfClosedUTC")!=a or buy.get("closedHourUTC")!=a:
        raise ValueError("V8_HOURLY_DATA_WRONG_HOUR")
    if oi.get("threeContinuousClosedHours") is not True:
        raise ValueError("OI_NOT_CONTIGUOUS")
    if buy.get("takerBuySellCrossSourceVerified") is not False:
        raise ValueError("UNEXPECTED_TAKER_ATTESTATION")
    if not 0<=buy["providerBuyShare"]<=1:
        raise ValueError("INVALID_BUY_SHARE")
    if funding.get("ageSeconds",999999)>43200:
        raise ValueError("STALE_FUNDING")
    variants=v7["results"][PAIR]
    if not {"V7_signal_filter","V7_signal_plus_retest"}.issubset(variants):
        raise ValueError("MISSING_V7_VARIANTS")
    def count(variant,field):
        arr=variants[variant].get(field)
        if not isinstance(arr,list):
            raise ValueError("MISSING_V7_EVENT_LIST")
        return len(arr)
    return {
        "status":"PAIRED_RESEARCH_ONLY_NO_SIGNAL",
        "mode":"SOL_V8_SHADOW_AUDIT_JOIN_NO_ORDERS",
        "symbol":PAIR,"targetClosed1HUTC":a,
        "v7ObservedAtUTC":v7["observedAtUTC"],
        "v8ObservedAtUTC":v8["observedAtUTC"],
        "earliestJointAvailabilityUTC":max(v7["observedAtUTC"],v8["observedAtUTC"]),
        "dataWasKnownToV7AtItsDecisionTime":t8<=t7,
        "v7":{
            "newBOSCount":c["newBOSCount"],
            "V7_signal_filter_newWatches":count("V7_signal_filter","newWatchAtThisClose"),
            "V7_retest_newWatches":count("V7_signal_plus_retest","newWatchAtThisClose"),
            "V7_signal_filter_newPaperExits":count("V7_signal_filter","paperTradeExitsObservedAtThisClose"),
            "noSignalExplanation":c.get("noSignalExplanation"),
        },
        "v8":{
            "oi1hChangePct":oi["oneHourChangePct"],
            "providerBuyShare":buy["providerBuyShare"],
            "fundingProviderValueAtObservation":funding["providerReportedValue"],
            "fundingProviderUpdateUTC":funding["providerUpdateUTC"],
            "fundingProviderUnitsUnverified":funding["providerReportedUnitsUnverified"],
        },
        "historicalBVIndependentBenchmark":"216/216 Binance hourly periods aligned (2026-11-01 through 09)",
        "causalityCaution":"V8 observed later than V7 when applicable. Do not treat post-decision funding or OI as known at V7 close; no retrospective gate or fill.",
        "signalsEnabled":False,"brokerOrders":False,"productionSystemModified":False,
        "realTrades":0,
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--v7",required=True)
    p.add_argument("--v8",required=True)
    p.add_argument("--output",required=True)
    args=p.parse_args()
    obj=join(json.loads(Path(args.v7).read_text()),
             json.loads(Path(args.v8).read_text()))
    path=Path(args.output)
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,indent=2)+"\n",encoding="utf-8")
    print("SOL_V8_SHADOW_JOIN",obj["status"],obj["targetClosed1HUTC"],
          "newV7Watches",obj["v7"]["V7_signal_filter_newWatches"])

if __name__=="__main__":
    main()
