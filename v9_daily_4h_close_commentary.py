#!/usr/bin/env python3
"""V9 Daily + 4H verified interpretation layer, separate from future-candle model.

Inputs: published main BTC/SOL Coinalyze OHLCV, RSI14, MACD hist and EMA
on 1H/4H/Daily; independently verified ETH V7 snapshot; BTC/SOL
OHLCV-derived chart structure. All source close timestamps must match
the EXACT SAME 4H close. Daily close must be <= 4H close.

Research display artifact, NOT a trading signal; no changes to the V9
green/red prestart forecast or paper journal. No guessed pivot/Fib/
SMA/orderbook/funding/values. Structures require confirmedAt<=4H close.
"""
import argparse,json,math
from datetime import datetime,timezone,timedelta
from pathlib import Path
from hashlib import sha256

ASSETS={"BTC":"BTCUSDT_PERP.A","ETH":"ETHUSDT_PERP.A","SOL":"SOLUSDT_PERP.A"}
TFS=("1hour","4hour","daily")
Istanbul=timezone(timedelta(hours=3))


def parse(t):
    return datetime.fromisoformat(t.replace("Z","+00:00")).astimezone(timezone.utc)


def ts(t):
    return int(parse(t).timestamp())


def tsi(t):
    return parse(t).astimezone(Istanbul).strftime("%Y-%m-%d %H:%M TSİ")


def source_digest(value):
    return sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,
                             separators=(",",":")).encode()).hexdigest()


def _checked(candle,ind):
    for k in ("open","high","low","close","volume"):
        v=candle.get(k)
        if type(v) not in (int,float) or not math.isfinite(v):
            raise ValueError("UNVERIFIED_CANDLE_"+k)
    o,h,l,c,v=(candle[z] for z in ("open","high","low","close","volume"))
    if not (0<l<=min(o,c)<=max(o,c)<=h and v>=0):
        raise ValueError("INVALID_CANDLE_BOUNDS")
    for k in ("RSI14","EMA20","EMA50","MACDHistogram"):
        if type(ind.get(k)) not in (int,float) or not math.isfinite(ind[k]):
            raise ValueError("MISSING_"+k)
    if not 0<=ind["RSI14"]<=100:
        raise ValueError("INVALID_RSI")
    return True


def map_sources(main,eth,structure):
    if main.get("ok") is not True or main.get("provider")!="Coinalyze":
        raise ValueError("MAIN_MARKET_DATA_NOT_VERIFIED")
    if eth.get("status")!="VERIFIED_PAPER_OBSERVATION" or (
        eth.get("symbol")!=ASSETS["ETH"]):
        raise ValueError("ETH_PAPER_SOURCE_UNVERIFIED")
    proofs=eth.get("crossTimeframeOHLCVVerifiedLast5",{})
    if proofs.get("1H_matches_4H")!=5 or proofs.get("1H_matches_daily")!=5:
        raise ValueError("ETH_TIMEFRAME_5_OF_5_NOT_VERIFIED")
    if eth.get("brokerOrders") is not False:
        raise ValueError("ETH_SOURCE_MUST_HAVE_NO_ORDERS")
    mainmap={(r["symbol"],r["interval"]):r for r in main["results"]}
    if len(mainmap)!=len(main["results"]):
        raise ValueError("DUPLICATE_SOURCE_ROWS")
    smap={(r["symbol"],r["interval"]):r for r in structure["results"]}
    if len(smap)!=len(structure["results"]):
        raise ValueError("DUPLICATE_STRUCTURE_ROWS")
    if not structure.get("method","").startswith("Heuristic swing pivots"):
        raise ValueError("UNRECOGNIZED_STRUCTURE_METHOD")
    ethrows=eth["marketContext"][ASSETS["ETH"]]["timeframes"]
    results={}
    known_4h=set()
    known_daily=set()
    for asset,sym in ASSETS.items():
        timeframes={}
        for tf in TFS:
            if asset=="ETH":
                r=ethrows[tf]
                close=r["closeTimeUTC"]
                candle=r["candle"]
                ind=r["indicators"]
            else:
                r=mainmap.get((sym,tf))
                if not r or r.get("status")!="READY":
                    raise ValueError("MAIN_UNREADY_"+asset+"_"+tf)
                close=r["closeTimeUTC"]
                candle=r["candle"]
                ind=r["indicators"]
            _checked(candle,ind)
            timeframes[tf]={
                "closeUTC":parse(close).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "OHLCV":candle,"RSI14":ind["RSI14"],
                "EMA20":ind["EMA20"],"EMA50":ind["EMA50"],
                "EMA200":ind.get("EMA200"),
                "MACDHistogram":ind["MACDHistogram"],
            }
        if timeframes["1hour"]["closeUTC"]<timeframes["4hour"]["closeUTC"]:
            raise ValueError("LATEST_1H_OLDER_THAN_4H_"+asset)
        for tf in ("4hour","daily"):
            if asset!="ETH":
                z=smap.get((sym,tf))
                if not z or z.get("status")!="READY":
                    raise ValueError("STRUCTURE_UNREADY_"+asset+"_"+tf)
                if parse(z["lastCloseTimeUTC"])!=parse(timeframes[tf]["closeUTC"]):
                    raise ValueError("STRUCTURE_CLOSE_MISMATCH_"+asset+"_"+tf)
        known_4h.add(timeframes["4hour"]["closeUTC"])
        known_daily.add(timeframes["daily"]["closeUTC"])
        results[asset]={"timeframes":timeframes}
    if len(known_4h)!=1 or len(known_daily)!=1:
        raise ValueError("BTC_ETH_SOL_TIMESTAMPS_UNALIGNED")
    close4=next(iter(known_4h))
    daily=next(iter(known_daily))
    if parse(daily)>parse(close4):
        raise ValueError("FUTURE_DAILY_BAR_LEAK")
    for asset,sym in ASSETS.items():
        r=results[asset]
        r["source4HCloseUTC"]=close4
        r["lastDailyCloseUTC"]=daily
        for tf in ("daily","4hour"):
            x=r["timeframes"][tf]
            c=x["OHLCV"]
            body="GREEN" if c["close"]>c["open"] else "RED" if c["close"]<c["open"] else "DOJI"
            if c["close"]<x["EMA20"] and x["EMA20"]<x["EMA50"]:
                trend="BEARISH_CONTEXT"
            elif c["close"]>x["EMA20"] and x["EMA20"]>x["EMA50"]:
                trend="BULLISH_CONTEXT"
            else:
                trend="MIXED_CONTEXT"
            if x["RSI14"]<30:risk="RSI_OVERSOLD_BOUNCE_RISK"
            elif x["RSI14"]>70:risk="RSI_OVERBOUGHT_PULLBACK_RISK"
            else:risk="RSI_NOT_EXTREME"
            x["candleBody"]=body
            x["emaContext"]=trend
            x["oscillatorRisk"]=risk
            x["MACDHistogramSign"]="NEGATIVE" if x["MACDHistogram"]<0 else ("POSITIVE" if x["MACDHistogram"]>0 else "ZERO")
            x["volumeChangePct"]=c.get("volumeChangePct")
            x["volumeStatement"]="LOWER_THAN_PREVIOUS" if c.get("volumeChangePct",0)<0 else (
                "HIGHER_THAN_PREVIOUS" if c.get("volumeChangePct",0)>0 else "UNVERIFIED_CHANGE")
        r["combinedInterpretation"]=_combined(r)
        if asset=="ETH":
            r["structureCommentary"]={
               "available":False,
               "reason":"Independent ETH 4H/Daily BOS/CHoCH/OB/FVG levels not supplied in verified snapshot"}
        else:
            z=smap[(sym,"4hour")]
            cutoff=ts(close4)
            events=[p for p in z.get("structure",[]) if p["at"]<=cutoff]
            ob=[p for p in z.get("candidateOrderBlocks",[])
                if p.get("confirmedAt",cutoff+1)<=cutoff]
            fvg=[p for p in z.get("openFVG",[])
                 if p.get("formedAt",cutoff+1)<=cutoff]
            liquidity=z.get("liquidity",[])
            near=c["close"] # overwritten below
            near=r["timeframes"]["4hour"]["OHLCV"]["close"]
            closest_fvg=sorted(fvg,key=lambda v:abs((v["high"]+v["low"])/2-near))[:2]
            closest_ob=sorted(ob,key=lambda v:abs((v["body"]["high"]+v["body"]["low"])/2-near))[:2]
            closest_liq=sorted(liquidity,key=lambda v:abs(v["level"]-near))[:3]
            r["structureCommentary"]={
                "available":True,
                "mostRecentBOSorCHoCH":events[-1] if events else None,
                "nearestCandidateOB":[{"side":q["side"],"body":q["body"],"confirmedAt":q["confirmedAt"],
                                        "state":q["state"],"institutionalOrderProven":False} for q in closest_ob],
                "nearestOpenFVG":[{"side":q["side"],"low":q["low"],"high":q["high"],"formedAt":q["formedAt"]} for q in closest_fvg],
                "nearestChartLiquidity":[{"kind":q["kind"],"level":q["level"],
                                          "realRestingStopOrdersProven":False} for q in closest_liq],
                "dataAreChartStructureHeuristicsNotVerifiedOrderflow":True}
    return {
       "status":"V9_VERIFIED_DAILY_4H_INTERPRETATIONS_ONLY",
       "asOf4HCloseUTC":close4,
       "asOf4HCloseTSI":tsi(close4),
       "asOfDailyCloseUTC":daily,
       "asOfDailyCloseTSI":tsi(daily),
       "assets":results,
       "sourceSHA256":{"BTC_SOL_main":source_digest(main),
                       "ETH_independent":source_digest(eth),
                       "BTC_SOL_structure":source_digest(structure)},
       "preservePreviousFrozen4HPreStartPredictions":True,
       "commentaryNotAnEntrySignal":True,
       "fundingOIandExactPivotsNotAvailableInTheseSources":True,
       "user87_50_95_SOL_zoneIsUserSuppliedContextNotAutoDrawn":True,
       "noRealOrders":True,
       "productionModified":False}


def _combined(r):
    daily=r["timeframes"]["daily"]
    four=r["timeframes"]["4hour"]
    return {
       "contextAgreement":daily["emaContext"]==four["emaContext"],
       "dailyContext":daily["emaContext"],
       "fourHourContext":four["emaContext"],
       "caution":"Oversold bounce" if (
             daily["oscillatorRisk"]=="RSI_OVERSOLD_BOUNCE_RISK" or
             four["oscillatorRisk"]=="RSI_OVERSOLD_BOUNCE_RISK") else (
             "Overbought pullback" if (
                daily["oscillatorRisk"]=="RSI_OVERBOUGHT_PULLBACK_RISK" or
                four["oscillatorRisk"]=="RSI_OVERBOUGHT_PULLBACK_RISK")
             else "No RSI extreme"),
       "notPredictiveEvidenceForNextCandle":True}


def markdown(report):
    parts=["# BTC → ETH → SOL — Verified Daily + 4H close interpretation",
           "",
           f"4H closed: **{report['asOf4HCloseTSI']}**. Daily closed: **{report['asOfDailyCloseTSI']}**.",
           "",
           "**This is context and technical commentary, NOT a prediction of the next 4H candle.** "
           "V9 pre-start forecast remains immutable and must be evaluated separately.",
           ""]
    for a in ("BTC","ETH","SOL"):
        x=report["assets"][a]
        parts+=["",f"## {a}"]
        for tf,cap in (("daily","Daily"),("4hour","4H")):
            v=x["timeframes"][tf]
            c=v["OHLCV"]
            parts += [f"**{cap}:** {v['candleBody']} | O {c['open']:,.2f} H {c['high']:,.2f} "
                      f"L {c['low']:,.2f} C {c['close']:,.2f} | RSI14 {v['RSI14']:.2f} "
                      f"| MACD hist {v['MACDHistogram']:+.4f} | "
                      f"EMA20/50 {v['EMA20']:,.2f}/{v['EMA50']:,.2f} "
                      f"| {v['emaContext']} | {v['oscillatorRisk']}"]
        k=x["combinedInterpretation"]
        parts+=[f"**Daily+4H interpretation:** trend agreement={k['contextAgreement']}; "
                f"Daily={k['dailyContext']}; 4H={k['fourHourContext']}; "
                f"risk={k['caution']}."]
        z=x["structureCommentary"]
        if not z["available"]:
            parts+=["**BOS/OB/FVG/liquidity:** Not verified for ETH at this timestamp."]
        else:
            ev=z["mostRecentBOSorCHoCH"]
            parts+=[f"**Latest chart structure:** {ev['event']} {ev['direction']} "
                    f"at level {ev['brokenLevel']:,.2f} (heuristic, not guaranteed)"
                    if ev else "**Latest chart structure:** none confirmed."]
            for q in z["nearestCandidateOB"]:
                parts+=[f"- Candidate {q['side']} OB body {q['body']['low']:,.2f}–{q['body']['high']:,.2f}; "
                        "not proven institutional orders."]
            for q in z["nearestOpenFVG"]:
                parts+=[f"- Open {q['side']} FVG {q['low']:,.2f}–{q['high']:,.2f}."]
            for q in z["nearestChartLiquidity"]:
                parts+=[f"- Chart {q['kind']} near {q['level']:,.2f}; actual resting orders unverified."]
        if a=="SOL":
            parts+=["User 87.50–95.00 USD broad zone is manual context; no automatic retest is inferred."]
    parts+=["", "## Separate V9 next 4H prediction",
             "The green/red prediction is captured **before** the next 4H opens and published separately. "
             "Post-close chart comments must never overwrite, re-label, or delete that forecast.",
             "",
             "**Unsupported in this snapshot:** exact Pivot/Fibonacci anchors, SMA100/200, funding, OI, BTC/ETH OB/FVG where absent. Do not infer them.",
             ""]
    return "\n".join(parts)


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--main",required=True)
    p.add_argument("--eth",required=True)
    p.add_argument("--structure",required=True)
    p.add_argument("--json",default="forward/v9_close_commentary/latest.json")
    p.add_argument("--markdown",default="forward/v9_close_commentary/latest.md")
    a=p.parse_args()
    load=lambda f:json.loads(Path(f).read_text())
    result=map_sources(load(a.main),load(a.eth),load(a.structure))
    for path,data in ((a.json,json.dumps(result,indent=2,ensure_ascii=False)+"\n"),
                      (a.markdown,markdown(result))):
        out=Path(path);out.parent.mkdir(parents=True,exist_ok=True)
        out.write_text(data)
    print("V9_DAILY_4H_CONTEXT_VERIFIED_NO_PREDICTION_OVERRIDE",
          result["asOf4HCloseUTC"],
          {s:z["combinedInterpretation"]["dailyContext"] for s,z in result["assets"].items()})


if __name__=="__main__":
    main()
