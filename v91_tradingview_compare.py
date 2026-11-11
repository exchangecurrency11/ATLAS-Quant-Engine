#!/usr/bin/env python3
"""TradingView 1H closed-candle independent BOS/CHoCH/FVG/sweep research parity.

SOURCE STATUS: TV user-provided alert JSON has NO authenticated webhook receipt.
Do not treat retrospective/manual imports as prospective time-locked evidence.
Never use TV heuristics as an executed order or a V7 BOS/retest veto.
Run on an original V7 observation at exact same closed 1H BTC/SOL timestamp.
"""
import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

HOUR=3600
HOUR_MS=3_600_000
VERSION="v91.tv.1h.v1"
TICKERS={"BTCUSDT.P":"BTCUSDT_PERP.A","SOLUSDT.P":"SOLUSDT_PERP.A"}
FLAG_NAMES=("bullBOS","bearBOS","chochBull","chochBear",
            "sweepHigh","sweepLow","fvgBull","fvgBear")
NUMBER_NAMES=("open","high","low","close","volume","atr14","rsi14",
              "macdHistogram","ema20","ema50","ema200")
OPTIONAL_NUMBERS=("confirmedSwingHigh","confirmedSwingLow","brokenLevel")
REL_PRICE_TOLERANCE=0.0001   # 1bp; source disagreement recorded, never auto-traded


def utc(epoch):
    return datetime.fromtimestamp(epoch,timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def stamp(value):
    if not isinstance(value,str):
        raise ValueError("V91_UNTIMESTAMPED_ORIGINAL_V7_SNAPSHOT")
    d=datetime.fromisoformat(value.replace("Z","+00:00"))
    if d.tzinfo is None or d.utcoffset().total_seconds()!=0:
        raise ValueError("V91_V7_TIME_NOT_UTC")
    return int(d.timestamp())


def finite(value,name,*,nullable=False):
    if nullable and value is None:
        return None
    if type(value) not in (int,float) or not math.isfinite(value):
        raise ValueError("V91_TV_NOT_FINITE_"+name)
    return float(value)


def validate_alert(payload):
    if not isinstance(payload,dict):
        raise ValueError("V91_TV_JSON_OBJECT_REQUIRED")
    if (payload.get("schema")!=VERSION or
        payload.get("source")!="TradingViewPineV6" or
        payload.get("exchange")!="BINANCE" or
        payload.get("ticker") not in TICKERS or
        payload.get("timeframe")!="60" or
        payload.get("confirmed") is not True or
        payload.get("researchOnly") is not True or
        payload.get("noTradeAction") is not True):
        raise ValueError("V91_TV_WRONG_SCHEMA_EXCHANGE_FUTURES_OR_CLOSED_BAR")
    if type(payload.get("barOpenMs")) is not int or type(payload.get("barCloseMs")) is not int:
        raise ValueError("V91_TV_INVALID_MILLISECOND_TIMESTAMP")
    opened=payload["barOpenMs"]
    closed=payload["barCloseMs"]
    if opened%HOUR_MS or closed-opened != HOUR_MS or closed%HOUR_MS:
        raise ValueError("V91_TV_NOT_A_COMPLETE_UTC_HOUR")
    for k in NUMBER_NAMES:
        finite(payload.get(k),k)
    for k in OPTIONAL_NUMBERS:
        finite(payload.get(k),k,nullable=True)
    o,h,l,c=(payload[k] for k in ("open","high","low","close"))
    if l<=0 or h<max(o,c) or l>min(o,c) or payload["volume"]<0 or payload["atr14"]<=0:
        raise ValueError("V91_TV_INVALID_OHLCV")
    if not 0<=payload["rsi14"]<=100:
        raise ValueError("V91_TV_BAD_RSI")
    if type(payload.get("pivotRightBars")) is not int or not 2<=payload["pivotRightBars"]<=10:
        raise ValueError("V91_TV_BAD_PIVOT_CONFIGURATION")
    for k in FLAG_NAMES:
        if type(payload.get(k)) is not bool:
            raise ValueError("V91_TV_FLAG_IS_NOT_BOOLEAN_"+k)
    if payload["bullBOS"] and payload["bearBOS"]:
        raise ValueError("V91_TV_IMPOSSIBLE_DOUBLE_BOS")
    if payload["chochBull"] and not payload["bullBOS"]:
        raise ValueError("V91_TV_CHOCH_WITHOUT_BULL_BOS")
    if payload["chochBear"] and not payload["bearBOS"]:
        raise ValueError("V91_TV_CHOCH_WITHOUT_BEAR_BOS")
    if (payload["bullBOS"] or payload["bearBOS"]) and payload["brokenLevel"] is None:
        raise ValueError("V91_TV_MISSING_BROKEN_LEVEL")
    return payload


def compare_snapshot(tv,v7):
    validate_alert(tv)
    if not isinstance(v7,dict) or v7.get("status")!="VERIFIED_PAPER_OBSERVATION" or v7.get("brokerOrders") is not False:
        raise ValueError("V91_ORIGINAL_V7_OBSERVATION_UNVERIFIED")
    target=tv["barCloseMs"]//1000
    if stamp(v7.get("targetClosed1HUTC"))!=target:
        raise ValueError("V91_TV_V7_DIFFERENT_CLOSED_1H_CANDLE")
    observed=stamp(v7.get("observedAtUTC"))
    if not target<=observed<target+HOUR:
        raise ValueError("V91_ORIGINAL_V7_NOT_CAPTURED_IN_HOUR")
    sym=TICKERS[tv["ticker"]]
    v7row=v7["marketContext"][sym]
    if stamp(v7row["checkedClosed1HUTC"])!=target:
        raise ValueError("V91_V7_COINALYZE_CONTEXT_TIME_MISMATCH")
    v7one=v7row["timeframes"]["1hour"]["candle"]
    deviations={}
    for key in ("open","high","low","close"):
        original=finite(v7one[key],key)
        independent=finite(tv[key],key)
        deviations[key]=round(10_000*abs(independent-original)/original,4)
    same_ohlc=all(value<=REL_PRICE_TOLERANCE*10000 for value in deviations.values())
    original_events=v7row["newStructureEventsAtClose"]
    v7bos=[event for event in original_events
           if event.get("event")=="BOS" and
           event.get("direction") in ("bullish","bearish")]
    v7dirs=sorted({event["direction"] for event in v7bos})
    tvdirs=(["bullish"] if tv["bullBOS"] else [])+(
            ["bearish"] if tv["bearBOS"] else [])
    v7watch=v7["results"][sym]["V7_signal_filter"]["newWatchAtThisClose"]
    if any(x.get("knownUTC")!=target for x in v7watch):
        raise ValueError("V91_V7_WATCH_NOT_THIS_HOUR")
    flags={k:tv[k] for k in FLAG_NAMES}
    return {
        "status":"V91_TV_INDEPENDENT_CLOSED_1H_CONTEXT_COMPARISON",
        "symbol":tv["ticker"].replace(".P",""),
        "v7Contract":sym,
        "closed1HUTC":utc(target),
        "v7CapturedUTC":v7["observedAtUTC"],
        "tvProvider":"TradingView",
        "tvFromActualLiveAlertProven":False,
        "manualAlertInputNotAuthenticatedOrTimeSealed":True,
        "tvSource":"BINANCE:"+tv["ticker"],
        "tvAlertSHA256":hashlib.sha256(json.dumps(tv,sort_keys=True,separators=(",",":")).encode()).hexdigest(),
        "v7InputSnapshotSHA256":v7.get("inputSHA256"),
        "priceParityWithin1bpEachOHLC":same_ohlc,
        "priceDeviationBasisPoints":deviations,
        "tvOHLC":{"open":tv["open"],"high":tv["high"],"low":tv["low"],"close":tv["close"]},
        "v7OHLC":{key:v7one[key] for key in ("open","high","low","close")},
        "tvIndependentPivotRightBars":tv["pivotRightBars"],
        "tvIndependentStructure":flags,
        "tvLastConfirmedSwingHigh":tv["confirmedSwingHigh"],
        "tvLastConfirmedSwingLow":tv["confirmedSwingLow"],
        "tvBrokenLevel":tv["brokenLevel"],
        "tvBOSDirections":tvdirs,
        "v7RawBOSDirections":v7dirs,
        "v7NewQualifyingBOSWatches":len(v7watch),
        "v7RawNewBOSCount":len(v7bos),
        "tvVsV7RawBOSDirectionAgreementAtExactClose":same_ohlc and tvdirs==v7dirs,
        "differenceIsNotAnErrorBecausePivotsAndConfirmationDiffer":True,
        "automaticLiveEntryFilteringAllowed":False,
        "outcomeOrWinningProbabilityInferred":False,
        "noBrokerOrders":True,"noNotifications":True,
        "originalV7AndV9Unmodified":True,
    }


def summarize(comparisons):
    if len(comparisons)!=len(set((x["symbol"],x["closed1HUTC"]) for x in comparisons)):
        raise ValueError("V91_DUPLICATE_TV_SYMBOL_HOUR")
    report={
        "status":"V91_TV_MANUAL_OR_UNVERIFIED_RESEARCH_ONLY",
        "comparisons":sorted(comparisons,key=lambda x:(x["closed1HUTC"],x["symbol"])),
        "count":len(comparisons),
        "OHLCParityPass":sum(x["priceParityWithin1bpEachOHLC"] for x in comparisons),
        "bosDirectionSameOnComparableHours":sum(x["tvVsV7RawBOSDirectionAgreementAtExactClose"] for x in comparisons),
        "missingHoursAreNeverCountedAsAgreement":True,
        "PinePivotIsDeliberatelyNotV7ExactBOSAlgorithm":True,
        "retrospectiveUserProvidedAlertsNotProspective":True,
        "noConfirmedTradingViewWebhookConnection":True,
        "noPaperPnLEdgeEstablished":True,
        "notAnOrderOrProductionSignal":True,
        "noBrokerOrders":True,"noNotifications":True,
        "promotionBlocked":True}
    return report


def run(alerts,v7_directory):
    if isinstance(alerts,dict): alerts=[alerts]
    if not isinstance(alerts,list) or not 1<=len(alerts)<=500:
        raise ValueError("V91_TV_INPUT_ONE_TO_500_JSON_SNAPSHOTS")
    compared=[]
    for tv in alerts:
        validate_alert(tv)
        target=tv["barCloseMs"]//1000
        path=Path(v7_directory)/(datetime.fromtimestamp(
            target,timezone.utc).strftime("%Y-%m-%dT%H-00Z")+".json")
        if not path.is_file():
            raise ValueError("V91_V7_MISSING_IDENTICAL_TIME_SNAPSHOT_NO_BACKFILL_"+utc(target))
        compared.append(compare_snapshot(tv,json.loads(path.read_text())))
    return summarize(compared)


def main():
    a=argparse.ArgumentParser()
    a.add_argument("--tv",required=True,help="Actual TradingView Pine v6 alert JSON file (no invented events)")
    a.add_argument("--v7",default="v7_evidence/forward/snapshots")
    a.add_argument("--output",default="forward/v91_tradingview_compare/latest_manual.json")
    args=a.parse_args()
    result=run(json.loads(Path(args.tv).read_text(encoding="utf-8")),args.v7)
    path=Path(args.output)
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print("V91_TV_CONTEXT_ONLY_MANUAL_NOT_AUTHENTICATED",
          result["count"],"identicalCloseOHLC",result["OHLCParityPass"],
          "BOSdirectionAgreement",result["bosDirectionSameOnComparableHours"],flush=True)


if __name__=="__main__":
    main()
