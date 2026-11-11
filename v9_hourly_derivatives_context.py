#!/usr/bin/env python3
"""V9 optional verified derivatives context for each CLOSED 1H.

Only BTC ETH SOL Binance perpetual via Coinalyze, read-only:
- last 28 contiguous 1H price/taker volume, open interest and funding history
- 4H signed taker CVD proxy, 4H OI change, funding history variation
- no future bar and no extra GREEN/RED claim or trading recommendation

Research counterpart of v9_three_asset_derivatives_ablation.py using same
predeclared feature construction; NOT promoted to 4H predictor based on
any historical accuracy. If one source fails, explicit refusal rather than
making up levels. Called from the same hourly research job.
"""
import argparse,json,os,math
from pathlib import Path
from datetime import datetime,timezone
from v9_three_asset_derivatives_ablation import (
    get_group,features,iso,CONTRACTS,HOUR)

ENDPOINTS=("ohlcv-history","open-interest-history","funding-rate-history")
REQUIRED_BARS=28


def overlay_at(close_h,key,fetch=None):
    if close_h%HOUR:
        raise ValueError("OVERLAY_1H_CLOSE_NOT_ALIGNED")
    low=close_h-50*HOUR
    sources={}
    hashes={}
    for endpoint in ENDPOINTS:
        group,digest=get_group(endpoint,CONTRACTS,key,low,close_h,fetch=fetch)
        sources[endpoint]=group
        hashes[endpoint]=digest
    out={}
    for symbol in CONTRACTS:
        v=features(sources["ohlcv-history"][symbol],
                   sources["open-interest-history"][symbol],
                   sources["funding-rate-history"][symbol],
                   close_h)
        if v is None or not v.get("sourceAlignedComplete28Hours"):
            raise ValueError("OI_FUNDING_FLOW_LAST28H_NOT_ALIGNED_"+symbol)
        if v["asOfUTC"]!=iso(close_h):
            raise ValueError("OI_FUNDING_CONTEXT_TIME_MISMATCH_"+symbol)
        out[symbol]={
           "asOfClosed1HUTC":iso(close_h),
           "pricePrior4HChangePct":v["prev4HChangePct"],
           "takerBuy4HCVDBaseProxy":v["CVD4hBaseProxy"],
           "taker4HVolumeImbalancePct":v["CVD4hPctOfVolume"],
           "openInterest4HChangePct":v["OI4hChangePct"],
           "fundingProviderHistoryLastClosed":v["fundingHistoryLastClosed"],
           "fundingRelativePrior24Percentile":v["fundingPercentileRelativePrior24"],
           "fundingSourceVariationSufficient":v["fundingVariationSufficient"],
           "fundingUniquePrior24Values":v["fundingPrior24UniqueValues"],
           "providerFundingHistoryNotIndependentlySettlementVerified":True,
           "providerOpenInterestUnitsNotIndependentlyReconciled":True,
           "takerBVNotIndependentlyVerifiedForBTCETH":True,
           "CVDIsProxyNotTrueTradeByTradeDelta":True,
           "featureSourceAligned28Closed1Hours":True,
           "directionalSignalsFromThisOverlayAuthorized":False,
           "notAnOwnCandleColorForecast":True,
        }
    return {"status":"V9_HOURLY_OI_FUNDING_TAKER_CONTEXT_NOT_SIGNAL",
            "asOfClosed1HUTC":iso(close_h),
            "contracts":out,
            "sourceSHA256":hashes,
            "noTradingOrders":True,
            "doesNotChangeFrozenPrestart4HModel":True,
            "noUserNotifications":True}


def main():
    a=argparse.ArgumentParser()
    a.add_argument("--hourly",default="forward/v9_next_4h_color/hourly/latest.json")
    a.add_argument("--dir",default="forward/v9_next_4h_color/hourly/derivatives")
    args=a.parse_args()
    hourly=json.loads(Path(args.hourly).read_text())
    if hourly.get("status")!="V9_HOURLY_OBSERVATION_VERIFIED_PAPER_CONTEXT_ONLY":
        raise ValueError("HOURLY_SOURCE_NOT_VERIFIED")
    close=datetime.fromisoformat(hourly["closed1HUTC"].replace("Z","+00:00"))
    target=int(close.timestamp())
    now=int(datetime.now(timezone.utc).timestamp())
    if target>now or now-target>HOUR:
        raise ValueError("HOURLY_CONTEXT_STALE_NEVER_BACKFILL")
    key=(os.getenv("ETH_V7_COINALYZE_API_KEY") or
         os.getenv("SOL_V8_COINALYZE_API_KEY") or
         os.getenv("COINALYZE_API_KEY") or "").strip()
    if not key:raise ValueError("NO_READONLY_COINALYZE_KEY")
    out=overlay_at(target,key)
    d=Path(args.dir)
    d.mkdir(parents=True,exist_ok=True)
    name=close.strftime("%Y-%m-%dT%H-00Z")+".json"
    dest=d/name
    if dest.exists():
        raise ValueError("DERIVATIVE_SNAPSHOT_EXISTS_IMMUTABLE")
    dest.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
    (d/"latest.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
    print("V9_HOURLY_OI_CVD_FUNDING_CONTEXT_SAVED_NO_SIGNAL",
          out["asOfClosed1HUTC"],flush=True)


if __name__=="__main__":
    main()
