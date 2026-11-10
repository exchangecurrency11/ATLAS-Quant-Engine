#!/usr/bin/env python3
"""V9 SOL/BTC/ETH Binance 1H candle-based taker flow: RESEARCH ONLY.

NOT true tick-by-tick CVD: Binance aggregated taker BUY base volume is
known only at the 1H candle close. Delta=2*takerBuyBase-totalBaseVolume;
window sum is an hourly approximated cumulative delta (rolling CVD).
No actual orderbook imbalance, market-maker intent or liquidations.

Strictly as-of: use only CONTIGUOUS CLOSED hourly candles and reject
missing quote/trade/taker columns; never fill missing as 0 or with future data.
"""
from bisect import bisect_right
from datetime import datetime,timezone
import json, math

HOUR=3600
KEYS=("t","o","h","l","c","v","qv","trades","tbv","tbq")


def _valid_row(row):
    for key in KEYS:
        if key not in row:
            raise ValueError("FLOW_REQUIRED_FIELD_MISSING_"+key)
    nums=("o","h","l","c","v","qv","tbv","tbq")
    if not all(isinstance(row[k],(int,float)) and math.isfinite(row[k]) for k in nums):
        raise ValueError("FLOW_NONFINITE_OR_NONNUMERIC")
    if type(row["trades"]) is not int or row["trades"]<0:
        raise ValueError("FLOW_TRADES_INVALID")
    if type(row["t"]) is not int or row["t"]%HOUR:
        raise ValueError("FLOW_TIME_INVALID")
    if not (0<row["l"]<=min(row["o"],row["c"])<=max(row["o"],row["c"])<=row["h"]):
        raise ValueError("FLOW_PRICE_INVALID")
    if not (row["v"]>=0 and 0<=row["tbv"]<=row["v"]+1e-6
            and row["qv"]>=0 and 0<=row["tbq"]<=row["qv"]+1e-6):
        raise ValueError("FLOW_TAKER_OUTSIDE_TOTAL")
    if row["v"]>0 and not row["l"]*.9999<=row["qv"]/row["v"]<=row["h"]*1.0001:
        raise ValueError("FLOW_QUOTE_UNITS_DISAGREE")
    if row["tbv"]>0 and not row["l"]*.9999<=row["tbq"]/row["tbv"]<=row["h"]*1.0001:
        raise ValueError("FLOW_TAKER_QUOTE_UNITS_DISAGREE")


def closed_taker_features(rows, as_of_utc, hours=24, baseline_hours=24):
    """Produce a no-future, OHLCV volume-flow snapshot at a CLOSED 1H.

    Requires hours+baseline_hours consecutive data ending exactly at
    as_of_utc; all given rows may extend into the future but are never used.
    """
    if type(as_of_utc) is not int or as_of_utc%HOUR:
        raise ValueError("FLOW_AS_OF_MUST_BE_EXACT_HOURLY_CLOSE")
    if not 1<=hours<=168 or not 1<=baseline_hours<=168:
        raise ValueError("FLOW_WINDOW_OUT_OF_RANGE")
    # historical arrays have chronological unique 1H open timestamps
    times=[r.get("t") for r in rows]
    if any(type(t) is not int for t in times) or times!=sorted(times) or len(times)!=len(set(times)):
        raise ValueError("FLOW_HISTORY_UNSORTED_OR_DUPLICATE")
    end=bisect_right(times,as_of_utc-HOUR)
    required=hours+baseline_hours
    if end<required or rows[end-1]["t"]+HOUR!=as_of_utc:
        raise ValueError("FLOW_INSUFFICIENT_OR_STALE_CLOSED_HISTORY")
    chunk=rows[end-required:end]
    first=as_of_utc-required*HOUR
    if any(row["t"]!=first+i*HOUR for i,row in enumerate(chunk)):
        raise ValueError("FLOW_HOURLY_HISTORY_HAS_GAP")
    for row in chunk:
        _valid_row(row)
    base=chunk[:baseline_hours]
    now=chunk[baseline_hours:]
    total=sum(x["v"] for x in now)
    buys=sum(x["tbv"] for x in now)
    sells=total-buys
    qtotal=sum(x["qv"] for x in now)
    transactions=sum(x["trades"] for x in now)
    prev_base=sum(x["v"] for x in base)/len(base)
    this_avg=total/len(now)
    if total<=0 or prev_base<=0:
        raise ValueError("FLOW_ZERO_VOLUME_CANNOT_INFER_PRESSURE")
    if transactions<=0:
        raise ValueError("FLOW_NO_TRADES_CANNOT_INFER_MEAN_TRADE_SIZE")
    last=now[-1]
    last_share=last["tbv"]/last["v"] if last["v"] else None
    net=buys-sells
    result={
       "asOfClosedUTC":datetime.fromtimestamp(as_of_utc,timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
       "windowHours":hours,
       "baselineHours":baseline_hours,
       "source":"Binance official USD-M 1H kline taker buy base field; immutable monthly archives",
       "onlyClosedCandlesUsed":True,
       "firstWindow1HOpenUTC":datetime.fromtimestamp(now[0]["t"],timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
       "totalBaseVolume":round(total,8),
       "totalQuoteVolume":round(qtotal,8),
       "takerBuyBase":round(buys,8),
       "takerSellBaseDerived":round(sells,8),
       "buyShare":round(buys/total,6),
       "rollingCVDBaseApprox":round(net,8),
       "rollingCVDPctOfVolume":round(100*net/total,5),
       "averageHourlyVolumeRelativeToPreviousWindow":round(this_avg/prev_base,6),
       "completedTrades":transactions,
       "meanBaseVolumePerTrade":round(total/transactions,9),
       "last1HTakerBuyShare":round(last_share,6) if last_share is not None else None,
       "marketOrderBookKnown":False,
       "CVDIsCandleApproximationNotTickReconstruction":True,
       "realOrderIntentProven":False,
       "paperOnly":True,
    }
    if not -100.00001<=result["rollingCVDPctOfVolume"]<=100.00001:
        raise ValueError("FLOW_DELTA_OUTSIDE_POSSIBLE_RANGE")
    return result


def to_markdown(payload):
    rows=["# V9 closed-only Binance candle-derived taker flow",
          "","Research only, not a LONG/SHORT signal.",""]
    for sym,record in payload.items():
        rows.extend([f"## {sym}",
            f"- As-of: {record['asOfClosedUTC']}",
            f"- Taker buy share: {record['buyShare']:.2%}",
            f"- Rolling {record['windowHours']}H CVD proxy: {record['rollingCVDBaseApprox']:.3f} base units",
            f"- Signed delta as fraction of window volume: {record['rollingCVDPctOfVolume']:.2f}%",
            f"- Relative hourly volume: {record['averageHourlyVolumeRelativeToPreviousWindow']:.2f}x",
            "- Only historical already-closed data; no execution or predictive edge asserted.",
            ""])
    return "\n".join(rows)


if __name__=="__main__":
    raise SystemExit("Import as a read-only research module; no live trading")
