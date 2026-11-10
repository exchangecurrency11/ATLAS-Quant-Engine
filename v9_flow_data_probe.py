#!/usr/bin/env python3
"""V9 read-only Binance UM historical flow integrity smoke test for BTC ETH SOL.

Only one completed archive month per pair; SHA256 authenticated .CHECKSUM.
No entry/exit signals, no orders, no live conclusions, no user secrets.
"""
import argparse,json
from datetime import datetime,timezone
from pathlib import Path

from download_binance_um_history import download_month,aggregate
from v9_binance_taker_flow import closed_taker_features

SYMBOLS=("BTCUSDT","ETHUSDT","SOLUSDT")


def run(month):
    result={}
    for symbol in SYMBOLS:
        s,m,one,proof=download_month(symbol,month)
        if s!=symbol or m!=month:raise ValueError("ARCHIVE_CONTRACT_MISMATCH")
        if not all(set(("qv","tbv","tbq","trades")).issubset(r) for r in one):
            raise ValueError("SOURCE_FIELDS_MISSING")
        if len(one)<48:raise ValueError("INSUFFICIENT_CLOSED_FLOW_DATA")
        four=aggregate(one,14400)
        daily=aggregate(one,86400)
        for arr,batch in ((four,4),(daily,24)):
            # Check point-in-time aggregation exactly matches source sum
            for j,c in enumerate(arr):
                window=one[j*batch:(j+1)*batch]
                for key in ("v","qv","tbv","tbq","trades"):
                    got=c[key];expected=sum(x[key] for x in window)
                    if abs(got-expected)>max(1e-8,abs(expected)*1e-12):
                        raise ValueError("BINANCE_FLOW_AGGREGATION_MISMATCH_"+key)
        as_of=one[-1]["t"]+3600
        flow=closed_taker_features(one,as_of)
        result[symbol]={
            "month":m,"archiveSHA256":proof["sha256"],
            "archiveSource":proof["url"],
            "1hourCandles":len(one),"4hourCandles":len(four),"dailyCandles":len(daily),
            "allFiveFlowMeasuresAggregatedExactly":True,
            "asOfUTC":flow["asOfClosedUTC"],
            "rollingLast24hTakerResearchSnapshot":flow,
            "sourcePublicationNotContemporaneous":True}
        print("V9_BINANCE_FULL_KLINE_FLOW_SHA256_VERIFIED",symbol,m,len(one),flush=True)
    return {
        "mode":"V9_COMPLETED_ARCHIVE_FLOW_INTEGRITY_NO_ORDERS",
        "status":"HISTORICAL_DATA_FIELDS_VERIFIED_NO_PREDICTIVE_INFERENCE",
        "runUTC":datetime.now(timezone.utc).isoformat(),
        "monthsVerified":len(result),
        "contracts":result,
        "historicalNotRealTime":True,
        "paperOnly":True,"liveSignalEnabled":False,
        "brokerOrders":False,"productionModified":False}


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--month",default="2026-09")
    p.add_argument("--json",default="forward/v9_taker_flow/latest.json")
    args=p.parse_args()
    r=run(args.month)
    out=Path(args.json);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(r,indent=2,ensure_ascii=False)+"\n")
    print("V9_FLOW_ARCHIVE_3_ASSETS_VERIFIED",r["monthsVerified"],flush=True)


if __name__=="__main__":
    main()
