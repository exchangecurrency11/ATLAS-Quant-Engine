#!/usr/bin/env python3
"""V9.1 Coinbase spot independent hourly shadow (paper-only, no strategy changes).

Read-only three Coinbase Exchange BTC/ETH/SOL USD spot 1H candles, compare
same-hour RETURNS (not absolute prices or volumes) with previously sealed
Coinalyze-based V9 hourly context. NEVER modify signals or veto entries.
"""
import argparse
import datetime as dt
import json
import math
from pathlib import Path

from research.v91_coinbase_public_live_probe import (
    SPOT_HOST, SYMBOLS, ONE_HOUR, utc, read_public_json, inspect_spot_candles,
)

def fetch_closed_spot(asset, close, fetch=read_public_json):
    url=f"{SPOT_HOST}/products/{asset}-USD/candles"
    from urllib.parse import urlencode
    params=urlencode({"start":utc(close-4*ONE_HOUR),
                     "end":utc(close), "granularity":"3600"})
    return inspect_spot_candles(fetch(url+"?"+params),close)

def compare_venue_returns(coinbase, coinalyze):
    """Spot and perpetual are different instruments; this is *not* OHLC parity."""
    p=coinbase["candle"]
    other=coinalyze["1H"]["OHLCV"]
    def price(x):
        y=float(x)
        if not math.isfinite(y) or y<=0: raise ValueError("BAD_PRICE")
        return y
    spot_return=(price(p["close"])/price(p["open"])-1)*10000
    perp_return=(price(other["close"])/price(other["open"])-1)*10000
    def sign(v):
        return "UP" if v>0 else ("DOWN" if v<0 else "FLAT")
    return {"coinbaseSpot1HReturnBps":round(spot_return,4),
            "coinalyzePerpetual1HReturnBps":round(perp_return,4),
            "returnDifferenceBps":round(spot_return-perp_return,4),
            "sameHourlyCandleDirection":sign(spot_return)==sign(perp_return),
            "comparisonType":"DIRECTION_AND_RETURN_ONLY_DIFFERENT_MARKETS",
            "notDirectPriceOrVolumeParity":True,
            "notAnEntryFilterOrSignal":True}

def build_snapshot(target, observed, fresh_spot_by_asset, reference=None):
    result={
        "mode":"V91_COINBASE_HOURLY_SPOT_INDEPENDENT_SHADOW_READ_ONLY",
        "targetClosed1HUTC":utc(target),"observedAtUTC":utc(observed),
        "venue":"COINBASE_EXCHANGE_SPOT_USD_NOT_BINANCE_USDM_FUTURES",
        "assets":{},
        "coinalyzeComparisonStatus":"V9_REFERENCE_UNAVAILABLE",
        "successAllThreeCoinbaseSpotClosed1H":False,
        "allThreeSameHourV9Comparisons":False,
        "noIndependentLiveBinancePerpetualOHLCParity":True,
        "noCoinalyzeVolumeParityClaim":True,
        "noEntrySignalOrVeto":True,
        "originalV7Unmodified":True,
        "v91RulesUnmodified":True,
        "noBrokerOrders":True,
        "noNotifications":True,
        "noPaperTradesSynthesized":True,
    }
    valid_ref=(isinstance(reference,dict)
               and reference.get("status")=="V9_HOURLY_OBSERVATION_VERIFIED_PAPER_CONTEXT_ONLY"
               and reference.get("closed1HUTC")==utc(target)
               and isinstance(reference.get("assets"),dict))
    if valid_ref:
        result["coinalyzeComparisonStatus"]="V9_SAME_HOUR_AVAILABLE"
    all_comparable=True
    for asset in SYMBOLS:
        data=fresh_spot_by_asset.get(asset,{"status":"MISSING_COINBASE_SPOT"})
        row={"coinbaseSpotClosed1H":data}
        if data.get("status")=="VALID_COINBASE_SPOT_CLOSED_1H" and valid_ref:
            try:
                other=reference["assets"][asset+"USDT"]
                if other["1H"]["closedAtUTC"]!=utc(target):
                    raise ValueError("REFERENCE_CANDLE_NOT_SAME_HOUR")
                row["sameHourSpotVsPerpetualContext"]=compare_venue_returns(data,other)
            except (KeyError,TypeError,ValueError,OverflowError,ZeroDivisionError):
                row["comparisonStatus"]="DIFFERENT_OR_INVALID_REFERENCE_NO_COMPARISON"
                all_comparable=False
        else:
            all_comparable=False
            row["comparisonStatus"]="UNAVAILABLE_OR_NOT_SAME_HOUR"
        result["assets"][asset]=row
    result["successAllThreeCoinbaseSpotClosed1H"]=all(
        result["assets"][a]["coinbaseSpotClosed1H"].get("status")==
        "VALID_COINBASE_SPOT_CLOSED_1H" for a in SYMBOLS)
    result["allThreeSameHourV9Comparisons"]=bool(valid_ref and all_comparable)
    return result

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--out",default="forward/v91_coinbase_spot_shadow/hourly")
    parser.add_argument("--reference",default="forward/v9_next_4h_color/hourly/latest.json")
    args=parser.parse_args()
    observed=dt.datetime.now(dt.timezone.utc).timestamp()
    target=int(observed)//ONE_HOUR*ONE_HOUR
    minute=(observed-target)/60
    if not 12<=minute<=58:
        print("COINBASE_SPOT_SHADOW_SKIP_OUTSIDE_FRESH_CAPTURE_WINDOW",flush=True)
        return
    output=Path(args.out)/(
        dt.datetime.fromtimestamp(target,dt.timezone.utc).strftime("%Y-%m-%dT%H-00Z")+".json")
    if output.exists():
        print("COINBASE_SPOT_SHADOW_ALREADY_IMMUTABLY_RECORDED",output.name,flush=True)
        return
    source={a:fetch_closed_spot(a,target) for a in SYMBOLS}
    refpath=Path(args.reference)
    try:
        ref=json.loads(refpath.read_text()) if refpath.exists() else None
    except (OSError,ValueError):
        ref=None
    report=build_snapshot(target,observed,source,ref)
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open("x") as h:
        json.dump(report,h,ensure_ascii=False,indent=2)
        h.write("\n")
    print("COINBASE_SPOT_SHADOW_WRITTEN",output.name,
          "threeClosed",report["successAllThreeCoinbaseSpotClosed1H"],
          "sameHourCompared",report["allThreeSameHourV9Comparisons"],flush=True)

if __name__=="__main__":
    main()
