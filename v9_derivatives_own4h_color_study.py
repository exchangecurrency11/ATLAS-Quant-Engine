#!/usr/bin/env python3
"""BTC/ETH/SOL Coinalyze OI funding taker CVD on EXACT NEXT 4H OWN BODY.

Research-only 21-day 4H nonoverlapping historical holdout comparison,
predeclared A (prior price momentum) E (taker CVD sign) and B/C/D subsets.
Target=GREEN if next [T,T+4H) candle close > ITS OWN OPEN; RED if <.
Only 28h closed OHLCV/Coinalyze OI/funding available at T (the target
OPEN is known only at T, NEVER a feature). Future four 1H bars used only
to score after all 4 have closed, not in features.

BV is a candle taker buy volume proxy, NOT individual trade CVD.
Coinalyze OI conversion / funding cash-flow not independently verified.
This does NOT create prospective forecasts, modify V9 models, or enable
notifications. A filtered subset that keeps same momentum direction as
baseline must not claim new directional edge from case selection.
"""
import argparse,math,os,json
from datetime import datetime,timezone
from pathlib import Path
from v9_three_asset_derivatives_ablation import (
   get_group,features,variants,metric,CONTRACTS,HOUR,FOUR,iso,wilson_lower)

DAY=24*HOUR
EVAL_DAYS=21
LOOKBACK_DAYS=28
ASSET_MAP={
   "BTCUSDT_PERP.A":"BTCUSDT",
   "ETHUSDT_PERP.A":"ETHUSDT",
   "SOLUSDT_PERP.A":"SOLUSDT"}


def own_future_color(ohlcv,checkpoint):
    lookup={x["t"]:x for x in ohlcv}
    bars=[lookup.get(checkpoint+j*HOUR) for j in range(4)]
    if any(x is None for x in bars):
        return None
    if any(x["t"]+HOUR>checkpoint+FOUR for x in bars):
        raise ValueError("PARTIAL_4H_CANNOT_BE_SCORE_LABEL")
    a,b=bars[0]["o"],bars[-1]["c"]
    return {"open":a,"close":b,"color":(
        "GREEN" if b>a else "RED" if b<a else "DOJI")}


def tally(observations):
    eligible=[x for x in observations
              if x["prediction"] is not None and x["color"]!="DOJI"]
    n=len(eligible)
    correct=sum(x["prediction"]==x["color"] for x in eligible)
    return {
      "n":n,
      "correct":correct,
      "hitRatePct":round(100*correct/n,2) if n else None,
      "wilson95LowerPct":wilson_lower(correct,n),
      "abstainedOrDoji":len(observations)-n,
      "notAForwardProspectiveTest":True}


def evaluate(klines,open_interest,funding,end):
    if end%FOUR:raise ValueError("EVALUATION_END_NOT_ALIGNED")
    t0=end-EVAL_DAYS*DAY
    observations={k:[] for k in ("A_priceMomentum","B_momentumAndCVD",
                                "C_BplusRisingOI","D_CplusFundingContext",
                                "E_takerCVDOnly")}
    rows=[]
    for start in range(t0,end,FOUR):
        f=features(klines,open_interest,funding,start)
        result=own_future_color(klines,start)
        if f is None or result is None:
            rows.append({"target4HStartUTC":iso(start),
                         "status":"SOURCE_MISSING_28H_OR_OUTCOME_NO_LABEL"})
            continue
        outcomes=variants(f)
        actual=result["color"]
        for name,side in outcomes.items():
            direction=("GREEN" if side=="LONG" else "RED" if side=="SHORT" else None)
            observations[name].append({"prediction":direction,"color":actual})
        rows.append({
           "target4HStartUTC":iso(start),
           "knownAtStartUTC":f["asOfUTC"],
           "outcomeKnownAfterUTC":iso(start+FOUR),
           "actualFutureOwnOpen":result["open"],
           "actualFutureOwnClose":result["close"],
           "actualOwnCandleColor":actual,
           "priceMomentumA":outcomes["A_priceMomentum"],
           "takerFlowE":outcomes["E_takerCVDOnly"],
           "oi4HchangePct":f["OI4hChangePct"],
           "takerCVD4HChangePct":f["CVD4hPctOfVolume"],
           "fundingHistoryVariationSufficient":f["fundingVariationSufficient"],
           "status":"HISTORICAL_CAUSAL_DERIVATIVE_FEATURES_NOT_FORWARD"})
    score={k:tally(v) for k,v in observations.items()}
    for other in ("B_momentumAndCVD","C_BplusRisingOI","D_CplusFundingContext"):
        # The direction of B/C/D is NEVER changed relative to A by their
        # filters. Recovered hit rates reflect case selection, not an
        # improvement in matched-direction accuracy.
        a=observations["A_priceMomentum"]; b=observations[other]
        retained=[(u,v) for u,v in zip(a,b)
                  if v["prediction"] is not None and v["color"]!="DOJI"]
        if any(u["prediction"]!=v["prediction"] for u,v in retained):
            raise ValueError("FILTERED_MOMENTUM_WAS_NOT_SAME_DIRECTION")
    # Compare A and E only on the IDENTICAL 4H target/symbol timestamps,
    # accounting for E abstentions when CVD delta is zero.
    a=observations["A_priceMomentum"]
    e=observations["E_takerCVDOnly"]
    pairs=[(u,v) for u,v in zip(a,e)
           if u["prediction"] is not None and v["prediction"] is not None
           and u["color"]!="DOJI" and v["color"]!="DOJI"]
    a_matched=tally([u for u,v in pairs])
    e_matched=tally([v for u,v in pairs])
    matched={
       "identicalTargetCandles":len(pairs),
       "priceMomentumA":a_matched,
       "takerCVDOnlyE":e_matched,
       "EminusAHitRatePercentagePoints":round(
           e_matched["hitRatePct"]-a_matched["hitRatePct"],2)
           if pairs else None,
       "noSelectedSubsetComparedAgainstUnmatchedBaseline":True,
       "notProspectiveOrTradingPerformance":True}
    if len(rows)!=EVAL_DAYS*6:
        raise ValueError("EXPECTED_NONOVERLAPPING_126_FOUR_HOUR_TARGETS")
    eligible=[r for r in rows if r["status"].startswith("HISTORICAL_CAUSAL")]
    return {
      "intendedDistinct4HTargets":len(rows),
      "eligibleBothSourcesPlusFutureCandle":len(eligible),
      "sourceMissingOrSkipped":len(rows)-len(eligible),
      "dojiExcluded":sum(r["actualOwnCandleColor"]=="DOJI" for r in eligible),
      "fundingHistoryWithUsableVariationCount":sum(
          r["fundingHistoryVariationSufficient"] for r in eligible),
      "results":score,
      "pairedPriceMomentumVsTakerCVDSameOwn4HColor":matched,
      "postSelectionOfB_C_DNeverProvesDirectionalEdge":True,
      "rows":rows,
    }


def run(now,key,fetch=None):
    if not key and fetch is None:raise ValueError("MISSING_READONLY_CO INALYZE_KEY".replace(" ",""))
    end=now//FOUR*FOUR
    low=end-LOOKBACK_DAYS*DAY
    data={};digests={}
    for endpoint in ("ohlcv-history","open-interest-history",
                     "funding-rate-history"):
        payload,digest=get_group(endpoint,CONTRACTS,key,low,end,fetch=fetch)
        data[endpoint]=payload;digests[endpoint]=digest
    contracts={}
    for contract in CONTRACTS:
        contracts[ASSET_MAP[contract]]=evaluate(
            data["ohlcv-history"][contract],
            data["open-interest-history"][contract],
            data["funding-rate-history"][contract],end)
    return {
       "status":"V9_CO INALYZE_DERIVATIVES_OWN_NEXT_4H_COLOR_CAUSAL_HISTORICAL_ONLY".replace(" ",""),
       "evaluatedAtUTC":iso(now),
       "featuresOnlyThroughAsOfUTC":iso(end),
       "windowStartTargetUTC":iso(end-EVAL_DAYS*DAY),
       "windowEndExcludedUTC":iso(end),
       "targetDefinition":"NEXT 4H GREEN iff close > its OWN open, RED iff close < its OWN open",
       "trainingOrFeatureFitPerformed":False,
       "variantThresholdsSameAsPriorPredeclaredA_E_and_B_C_D":True,
       "noActualNext4HModelTrainingOrPromotion":True,
       "coinalyzeBvProviderNotIndependentlyReconciledAllHours":True,
       "coinalyzeFundingDoesNotMeanRealSettlementRate":True,
       "OIUnitsHaveNotBeenIndependentlyNormalizedAgainstBinance":True,
       "assetResults":contracts,
       "sourceSHA256":digests,
       "noRealOrders":True,"noNotifications":True,"productionModified":False}


def report_md(r):
    lines=["# V9 OI, funding and taker-CVD on the future 4H candle's OWN body",
           "",
           "Historical **not prospective** BTC ETH SOL comparison. "
           "Do not confuse next 4H close vs PREVIOUS close with next 4H own O/C color.",
           "",
           "| Asset | Eligible / 126 | Price momentum A | Taker CVD E | OI+funding filters B/C/D |",
           "|---|---:|---:|---:|---|"]
    for s,x in r["assetResults"].items():
        def f(v):
            return f"{v['correct']}/{v['n']} ({v['hitRatePct']}%)" if v["n"] else "N/A"
        matched=x["pairedPriceMomentumVsTakerCVDSameOwn4HColor"]
        lines.append(f"| {s} | {x['eligibleBothSourcesPlusFutureCandle']}/126 | "
                     f"{f(matched['priceMomentumA'])} | "
                     f"{f(matched['takerCVDOnlyE'])} | "
                     "B/C/D only filter same A direction (no extra directional edge) |")
    lines+=["",(
          "**Limits:** OI and funding field semantics have not been "
          "independently verified with Binance settlement/position books, "
          "and market shares are not profits or fills. These rules do not "
          "replace the frozen V9 model or prove next-4H predictive edge."
          ),""]
    return "\n".join(lines)


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--json",default="forward/v9_derivatives_own4h_color/report.json")
    p.add_argument("--md",default="forward/v9_derivatives_own4h_color/report.md")
    a=p.parse_args()
    key=(os.getenv("ETH_V7_COINALYZE_API_KEY") or
         os.getenv("SOL_V8_COINALYZE_API_KEY") or
         os.getenv("COINALYZE_API_KEY") or "").strip()
    if not key:raise ValueError("READONLY_API_KEY_MISSING")
    now=int(datetime.now(timezone.utc).timestamp())
    result=run(now,key)
    for path,content in ((a.json,json.dumps(result,ensure_ascii=False,indent=2)+"\n"),
                         (a.md,report_md(result))):
        out=Path(path);out.parent.mkdir(parents=True,exist_ok=True)
        out.write_text(content)
    print("V9_21D_DERIVATIVES_OWN_CANDLE_COLOR_HISTORICAL_ONLY",
          {s:{k:v["results"][k]["hitRatePct"] for k in
               ("A_priceMomentum","E_takerCVDOnly")}
             for s,v in result["assetResults"].items()},flush=True)


if __name__=="__main__":
    main()
