#!/usr/bin/env python3
"""V9 live-source COMPATIBILITY ONLY: BTC/ETH/SOL Coinalyze 1H + Daily.

Does not generate predictions. Run at ANY time, not just before 4H.
Reports source quality and exact availability of v/bv/tx and 1000-hour
continuity needed by the pre-start frozen model, independent of signals.
Never touches trading endpoints or production.
"""
from datetime import datetime,timezone
from pathlib import Path
from hashlib import sha256
import json,os

from v9_next4h_prestart_paper_capture import (
    HOUR,DAY,HISTORY_1H,HISTORY_D,get_group,verify_daily_vs_hours)
from v9_next_4h_color_research import SYMBOLS,iso


def audit(now,key,fetch=None):
    target=now//HOUR*HOUR
    start=target-HISTORY_1H*HOUR
    first_day=((now//DAY)-HISTORY_D)*DAY
    hour,h_sha=get_group("1hour",start,now,key,fetch)
    daily,d_sha=get_group("daily",first_day,now,key,fetch)
    report={}
    for symbol in SYMBOLS:
        hours=hour[symbol]
        days=daily[symbol]
        expected=HISTORY_1H
        contig=(len(hours)==expected and hours[0]["t"]==start and
                hours[-1]["t"]+HOUR==target and all(
                    hours[i]["t"]==start+i*HOUR for i in range(len(hours))))
        d_contig=(len(days)>=205 and all(
                    days[i+1]["t"]==days[i]["t"]+DAY
                    for i in range(len(days)-1)))
        last_d=(now//DAY)*DAY
        day_fresh=(days[-1]["t"]+DAY==last_d)
        try:
            daily_parity=verify_daily_vs_hours(hours,days,now)
        except ValueError:
            daily_parity=False
        count_1h=sum(int(h["trades"]) for h in hours[-24:])
        report[symbol]={
           "history1hBars":len(hours),"historyDailyBars":len(days),
           "oneHourContiguousComplete":contig,
           "dailyContiguousSMA200Ready":d_contig,
           "dailyLatestAsExpected":day_fresh,
           "lastDailyVsOneHourPriceVolumeWithinTolerance":daily_parity,
           "latest1hClosedUTC":iso(hours[-1]["t"]+HOUR),
           "latestDailyClosedUTC":iso(days[-1]["t"]+DAY),
           "last24HTradeCountFromProviderTX":count_1h,
           "takerBuyBaseAvailable":all("tbv" in x for x in hours),
           "tradeCountAvailable":all("trades" in x for x in hours),
           "coinalyzeProviderTransactionCountNotProvenBinanceEquivalent":True,
           "flowCrossSourceVerifiedForBTCETH":False,
           "eligibleForStrictPaperPrestartInput":contig and d_contig and day_fresh and daily_parity,
        }
    return {
       "status":"LIVE_SOURCE_ONLY_READONLY_NO_PREDICTIONS",
       "observedUTC":iso(now),
       "latestExpectedClosed1HUTC":iso(target),
       "provider":"Coinalyze Binance USD-M perpetual",
       "sourceSHA256":{"1hour":h_sha,"daily":d_sha},
       "assets":report,
       "allThreeReadyForInput":all(z["eligibleForStrictPaperPrestartInput"]
                                   for z in report.values()),
       "fundingAndOIMandatoryForFrozenModel":False,
       "noOrders":True,"noProductionEdits":True}


def main():
    now=int(datetime.now(timezone.utc).timestamp())
    key=(os.getenv("ETH_V7_COINALYZE_API_KEY") or
         os.getenv("SOL_V8_COINALYZE_API_KEY") or
         os.getenv("COINALYZE_API_KEY") or "").strip()
    if not key:
        raise ValueError("MISSING_COINALYZE_READONLY_KEY")
    result=audit(now,key)
    path=Path("forward/v9_next_4h_color/live_source_compatibility.json")
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print("V9_1H_DAILY_SOURCE_COMPATIBILITY",json.dumps({
        k:{"ready":z["eligibleForStrictPaperPrestartInput"],
           "1h":z["history1hBars"],"daily":z["historyDailyBars"],
           "tx24":z["last24HTradeCountFromProviderTX"]}
        for k,z in result["assets"].items()}),flush=True)


if __name__=="__main__":
    main()
