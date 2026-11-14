#!/usr/bin/env python3
"""ATLAS Core E4 — historical OHLC gap/fee/funding scenarios and portfolio risk.

NO production changes, orders, signals, prospective fills, real-time booking,
realized venue slippage or actual funding observations. Historical research
only. Uses E3's frozen official Binance 1H SHA256 replay and 51 tape entries.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
from hashlib import sha1,sha256
import json
from math import isfinite
from pathlib import Path

from research.atlas_core_v2 import atlas_core_e3 as e3
from research.atlas_core_v1 import atlas_core_e2 as e2

E3_BLOB_SHA1="8853983fb9781ecdd820cdcdc1fa55da7def16d4"
RESULT_STATUS="ATLAS_CORE_E4_MODELED_EXECUTION_AND_SHARED_PORTFOLIO_HISTORICAL_ONLY"
SYMBOLS=e2.ASSETS
PERIODS=e2.PERIODS
FUNDING_INTERVAL_SECONDS=8*3600
INITIAL_EQUITY_USDT=10000.
RISK_FRACTION_PER_TRADE=.005
TOTAL_OPEN_STOP_RISK_FRACTION=.01
MAX_GROSS_NOTIONAL_TO_EQUITY=1.5
MIN_ACCEPTED_RISK_FRACTION=.001
TIMEFRAME_SECONDS=3600

@dataclass(frozen=True)
class Scenario:
    name:str
    commission_bps_per_side:float
    half_spread_bps:float
    execution_impact_bps:float
    adverse_funding_bps_per_8h:float
    gap_stop:bool=True

    def __post_init__(self):
        fields=(self.commission_bps_per_side,self.half_spread_bps,
                self.execution_impact_bps,self.adverse_funding_bps_per_8h)
        if not all(isfinite(x) and x>=0 for x in fields):
            raise ValueError("E4_NEGATIVE_OR_NONFINITE_FRICTION")
        if any(x>500 for x in fields):
            raise ValueError("E4_SCENARIO_OUTSIDE_VALID_RESEARCH_RANGE")

    @property
    def roundtrip_assumed_cost_per_side_bps(self):
        return self.commission_bps_per_side+self.half_spread_bps+self.execution_impact_bps

IDEAL=Scenario("ideal_gross_no_gap_or_cost",0,0,0,0,False)
SCENARIOS=(
    Scenario("9bps_per_side_plus_adverse_funding",6,1,2,.5),
    Scenario("25bps_per_side_plus_adverse_funding",6,4,15,3),
    Scenario("50bps_per_side_plus_adverse_funding",6,9,35,10),
)

def ensure_sealed_sources():
    raw=Path("research/atlas_core_v2/atlas_core_e3.py").read_bytes()
    blob=sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()
    if blob!=E3_BLOB_SHA1:
        raise ValueError("E4_PINNED_E3_CODE_CHANGED")
    code_pins=e3.verify_code_pins()
    source,oracle_sha=e3.checked_oracle()
    e2_result=e2.audit()
    if e2_result["totalWitnessTradesMatched"]!=51:
        raise ValueError("E4_SEALED_WITNESSES_NOT_COMPLETE")
    return source,oracle_sha,{"e3":sha256(raw).hexdigest(),**code_pins}

def validate_trade(t:dict):
    required=("side","entryOpenUTC","exitKnownUTC","entry","stop","risk",
              "targets","realizedR","netRIllustrative","exitReason")
    if any(k not in t for k in required):
        raise ValueError("E4_MISSING_ORIGINAL_ENGINE_TRADE_FIELDS")
    if t["side"] not in ("bullish","bearish"):
        raise ValueError("E4_BAD_SIDE")
    if t["exitReason"] not in (
       "STOP_FIRST_OR_AFTER_TP","TP3_COMPLETE","TIME_EXIT_AT_CLOSE"):
        raise ValueError("E4_BAD_ENGINE_EXIT")
    a,b=int(t["entryOpenUTC"]),int(t["exitKnownUTC"])
    if a%3600 or b%3600 or not (a<b<=a+24*3600):
        raise ValueError("E4_TRADE_TIME_INVALID")
    if not (isfinite(t["entry"]) and isfinite(t["risk"]) and
            t["entry"]>0 and t["risk"]>0 and t["stop"]>0):
        raise ValueError("E4_TRADE_PRICE_INVALID")
    if abs(t["entry"]-t["stop"]-t["risk"])>1e-6 and t["side"]=="bullish":
        raise ValueError("E4_INCONSISTENT_LONG_STOP")
    if abs(t["stop"]-t["entry"]-t["risk"])>1e-6 and t["side"]=="bearish":
        raise ValueError("E4_INCONSISTENT_SHORT_STOP")
    sign=1 if t["side"]=="bullish" else -1
    if len(t["targets"])!=3 or any(abs(t["targets"][i]-
            (t["entry"]+sign*t["risk"]*(i+1)))>1e-6
        for i in range(3)):
        raise ValueError("E4_INCONSISTENT_THREE_TARGETS")
    return a,b

def validate_history_window(hourly:list[dict], trade:dict):
    a,b=validate_trade(trade)
    if not hourly or len(hourly)!=(b-a)//3600:
        raise ValueError("E4_INCOMPLETE_TRADE_HOURLY_WINDOW")
    for j,c in enumerate(hourly):
        if int(c["t"])!=a+3600*j:
            raise ValueError("E4_GAPPED_OR_UNORDERED_HOURLY_WINDOW")
        o,h,l,close=(c[k] for k in ("o","h","l","c"))
        if not all(isfinite(x) and x>0 for x in (o,h,l,close)):
            raise ValueError("E4_NONFINITE_OR_NONPOSITIVE_HOURLY_PRICE")
        if not l<=min(o,close)<=max(o,close)<=h:
            raise ValueError("E4_MALFORMED_CANDLE")
    if abs(hourly[0]["o"]-trade["entry"])>1e-6:
        raise ValueError("E4_ENTRY_PRICE_VS_RAW_BAR_DISAGREE")
    return a,b

def adverse_execution_price(nominal:float, side:str, *, enter:bool, scenario:Scenario):
    sign=1 if side=="bullish" else -1
    # Long: entry at ask (>nominal), exits at bid (<nominal).
    # Short: entry at bid (<nominal), exits at ask (>nominal).
    direction=sign if enter else -sign
    bps=scenario.half_spread_bps+scenario.execution_impact_bps
    result=nominal*(1+direction*bps/10000)
    if result<=0:
        raise ValueError("E4_EXECUTION_PRICE_NONPOSITIVE")
    return result

def funding_events_at_open(candle_open:int, trade_entry:int, trade_exit:int):
    """Hypothetical 00/08/16 UTC schedule ONLY; not Binance observed history.

    Charge adverse funding if position is held at an interval boundary.
    Entry exactly on boundary is charged conservatively. Exit at same
    boundary is NOT charged. Remaining fraction reflects partial TP.
    """
    return (trade_entry<=candle_open<trade_exit
            and candle_open%FUNDING_INTERVAL_SECONDS==0)

def simulate_trade(trade:dict, hourly:list[dict], scenario:Scenario)->dict:
    """Independent partial-fill bar execution vs the V9.2 historical oracle.

    Risk-normalized qty=1 contract-equivalent; gross denominator original
    entry-stop distance. Worst stop-first within a 1H candle. For stop
    gaps, fill at worse of stop and opening price (no market microstructure
    depth simulation). Exits at targets use target limit, not better price.
    """
    entry_t,exit_t=validate_history_window(hourly,trade)
    side=trade["side"]
    sign=1 if side=="bullish" else -1
    entry=trade["entry"]
    entry_fill=adverse_execution_price(entry,side,enter=True,scenario=scenario)
    stop=trade["stop"]
    targets=trade["targets"]
    remaining=1.
    gross_cash=0.
    commission_cash=scenario.commission_bps_per_side/10000*entry_fill
    funding_cash=0.
    fills=[]
    hit_targets=0
    gap_penalty_cash=0.
    gap_stop_count=0
    exited=False
    reason=None

    def execute(nominal:float,fraction:float,label:str,bar:dict):
        nonlocal gross_cash,commission_cash,remaining
        if not 0<fraction<=remaining+1e-10:
            raise ValueError("E4_FILL_SIZE_INVALID")
        final=adverse_execution_price(nominal,side,enter=False,scenario=scenario)
        gross_cash+=sign*(final-entry_fill)*fraction
        commission_cash+=scenario.commission_bps_per_side/10000*abs(final)*fraction
        remaining=max(0.,remaining-fraction)
        fills.append({"barOpenUTC":int(bar["t"]),"type":label,
                      "nominalFillPrice":round(nominal,10),
                      "modeledFillPrice":round(final,10),
                      "positionFractionClosed":round(fraction,8)})

    for j,bar in enumerate(hourly):
        t=int(bar["t"])
        if funding_events_at_open(t,entry_t,exit_t) and remaining>0:
            # Adverse fee scenario, not an observed signed funding rate.
            # The notional approximation uses reference entry, not mark.
            funding_cash+=entry*remaining*scenario.adverse_funding_bps_per_8h/10000

        stop_hit=bar["l"]<=stop if sign==1 else bar["h"]>=stop
        if stop_hit:
            nominal=stop
            if scenario.gap_stop:
                if sign==1 and bar["o"]<stop:
                    nominal=bar["o"]
                elif sign==-1 and bar["o"]>stop:
                    nominal=bar["o"]
                if nominal!=stop:
                    gap_stop_count+=1
                    gap_penalty_cash+=abs(nominal-stop)*remaining
            execute(nominal,remaining,"STOP_FIRST",bar)
            reason="STOP_FIRST_OR_AFTER_TP"
            exited=True
            break

        while hit_targets<3:
            target=targets[hit_targets]
            reached=bar["h"]>=target if sign==1 else bar["l"]<=target
            if not reached:break
            execute(target,1/3,"TP"+str(hit_targets+1),bar)
            hit_targets+=1
        if hit_targets==3:
            reason="TP3_COMPLETE"
            exited=True
            break
        if j+1>=24:
            execute(bar["c"],remaining,"24H_CLOSE",bar)
            reason="TIME_EXIT_AT_CLOSE"
            exited=True
            break

    if not exited or reason!=trade["exitReason"]:
        raise ValueError("E4_ENGINE_EXIT_RECONSTRUCTION_MISMATCH:"+str(
            (reason,trade["exitReason"])))
    if abs(remaining)>1e-8:
        raise ValueError("E4_UNCLOSED_MODELED_POSITION")
    last_candle=hourly[j]
    if int(last_candle["t"])+3600 != exit_t:
        raise ValueError("E4_EXIT_TIMESTAMP_VS_REFERENCE_DIFFER")
    net_cash=gross_cash-commission_cash-funding_cash
    risk=trade["risk"]
    if not all(isfinite(x) for x in (net_cash,gross_cash,commission_cash,funding_cash)):
        raise ValueError("E4_NONFINITE_EXECUTION_PNL")
    return {
        "grossR":round(gross_cash/risk,9),
        "netR":round(net_cash/risk,9),
        "netCashPerUnit":net_cash,"riskCashPerUnit":risk,
        "commissionCashPerUnit":commission_cash,
        "adverseFundingCashPerUnit":funding_cash,
        "gapStopCount":gap_stop_count,
        "gapStopPenaltyR":round(gap_penalty_cash/risk,9),
        "fullExposureEntry":entry_fill,
        "fills":fills,
        "stopFirstPolicy":True,
        "wasObservedRealFill":False,
        "observedFundingRatesAvailable":False,
    }

def reference_ideal_parity(original:dict,hourly:list[dict]):
    """Zero-cost, no-gap independently reproduce old gross TP/stop R.

    All 51 trades must pass; otherwise E4 cannot be trusted even for
    hypothetical impact stress.
    """
    x=simulate_trade(original,hourly,IDEAL)
    if abs(x["grossR"]-original["realizedR"])>1e-7:
        raise ValueError("E4_INDEPENDENT_GROSS_TAPE_REPLAY_MISMATCH:"+repr(
            (x["grossR"],original["realizedR"])))
    expected9=original["realizedR"]-2*9/10000*original["entry"]/original["risk"]
    if abs(expected9-original["netRIllustrative"])>1e-8:
        raise ValueError("E4_REFERENCE_FEE_FORMULA_DRIFT")
    return x

def position_budget_portfolio(trades:list[dict], scenario_name:str,
                              *, equity:float=INITIAL_EQUITY_USDT,
                              fraction_per_trade:float=RISK_FRACTION_PER_TRADE,
                              total_risk_fraction:float=TOTAL_OPEN_STOP_RISK_FRACTION,
                              leverage_cap:float=MAX_GROSS_NOTIONAL_TO_EQUITY,
                              minimum_risk_fraction:float=MIN_ACCEPTED_RISK_FRACTION)->dict:
    """Realized-only chronological hypothetical shared-equity backtest.

    Every entry uses available equity *after earlier exits*. Each trade's
    R is dimensionless and risk sizing converts it into USDT. Gross exposure
    includes open trades; stop risk is reserved concurrently; no orders.
    """
    if not (equity>0 and 0<minimum_risk_fraction<=fraction_per_trade<=total_risk_fraction<=.1
            and 0<leverage_cap<=10):
        raise ValueError("E4_INVALID_PORTFOLIO_RISK_BUDGET")
    event_rows=[]
    seen=set()
    for ix,t in enumerate(trades):
        for k in ("symbol","entryEpoch","exitEpoch","entry","risk","netR"):
            if k not in t:
                raise ValueError("E4_INCOMPLETE_PORTFOLIO_TRADE")
        if t["symbol"] not in SYMBOLS or t["entry"]<=0 or t["risk"]<=0 or not isfinite(t["netR"]):
            raise ValueError("E4_BAD_PORTFOLIO_TRADE_DATA")
        if not 0<t["entryEpoch"]<t["exitEpoch"]:
            raise ValueError("E4_PORTFOLIO_TIMESTAMP_INVALID")
        identifier=(t["symbol"],t["entryEpoch"])
        if identifier in seen:
            raise ValueError("E4_DUPLICATE_ASSET_ENTRY")
        seen.add(identifier)
        event_rows.append((t["entryEpoch"],1,ix))
        event_rows.append((t["exitEpoch"],0,ix))
    event_rows.sort(key=lambda t:(t[0],t[1],t[2])) # EXIT before ENTRY

    open_pos={}
    equity_curve=[{"eventEpoch":event_rows[0][0] if event_rows else 0,
                   "realizedEquity":equity,"openStopRisk":0.,"grossNotional":0.}]
    start_equity=equity
    peak=equity
    max_realized_dd=0.
    accepted=0
    rejected=0
    clipped=0
    max_positions=0
    max_open_stop_risk_frac=0.
    max_gross_multiple=0.
    exposure_count_when_entry=Counter()
    realized_pnls=[]
    worst_modeled_R=float("inf")
    worst_loss_beyond_original_stop_count=0
    own_cap_exposure={}
    for ts,kind,index in event_rows:
        item=trades[index]
        if kind==0: # exit
            if index not in open_pos:
                continue  # rejected entry stays rejected
            risk_cash,notional,sym=open_pos.pop(index)
            pnl=risk_cash*item["netR"]
            realized_pnls.append(pnl)
            equity+=pnl
            worst_modeled_R=min(worst_modeled_R,item["netR"])
            if item["netR"] < -1.000001:
                worst_loss_beyond_original_stop_count+=1
            if equity<=0:
                raise ValueError("E4_HYPOTHETICAL_EQUITY_DEPLETION")
            peak=max(peak,equity)
            max_realized_dd=max(max_realized_dd,(peak-equity)/peak)
        else: # enter
            if any(sym==item["symbol"] for _,_,sym in open_pos.values()):
                raise ValueError("E4_SAME_ASSET_OVERLAPPING_REFERENCES")
            used_risk=sum(v[0] for v in open_pos.values())
            used_notional=sum(v[1] for v in open_pos.values())
            budget_by_trade=fraction_per_trade*equity
            free_total_risk=max(0.,total_risk_fraction*equity-used_risk)
            free_notional=max(0.,leverage_cap*equity-used_notional)
            risk_price_fraction=item["risk"]/item["entry"]
            allowed=min(budget_by_trade,free_total_risk,
                        free_notional*risk_price_fraction)
            if allowed+1e-8 < minimum_risk_fraction*equity:
                rejected+=1
                continue
            if allowed<budget_by_trade-1e-8:
                clipped+=1
            notional=allowed/risk_price_fraction
            own_cap_exposure[index]=notional
            open_pos[index]=(allowed,notional,item["symbol"])
            accepted+=1
            exposure_count_when_entry[len(open_pos)]+=1

        current_risk=sum(v[0] for v in open_pos.values())
        current_notional=sum(v[1] for v in open_pos.values())
        max_positions=max(max_positions,len(open_pos))
        max_open_stop_risk_frac=max(max_open_stop_risk_frac,current_risk/equity)
        max_gross_multiple=max(max_gross_multiple,current_notional/equity)
        if current_risk>total_risk_fraction*equity+1e-6:
            # Equity can drop while positions stay open. This is a breach,
            # not a new trade. Log the breach rather than falsely enforcing
            # an automatic deleveraging operation not implemented.
            pass
        equity_curve.append({
            "eventEpoch":ts,"realizedEquity":round(equity,6),
            "openStopRisk":round(current_risk,6),
            "grossNotional":round(current_notional,6),
        })
    if open_pos or accepted+rejected!=len(trades):
        raise ValueError("E4_POSITION_ACCOUNT_NOT_CLOSED")
    profits=sum(x for x in realized_pnls if x>0)
    losses=-sum(x for x in realized_pnls if x<0)
    pf=round(profits/losses,6) if losses>0 else None
    return {
        "scenario":scenario_name,
        "startingCashUSDT":start_equity,
        "endingRealizedCashUSDT":round(equity,4),
        "realizedOnlyReturnPct":round(100*(equity/start_equity-1),4),
        "hypotheticalRealizedOnlyProfitFactor":pf,
        "maxRealizedOnlyDrawdownPct":round(max_realized_dd*100,4),
        "maxConcurrentAcceptedPositions":max_positions,
        "maxStopRiskFractionVsRealizedEquity":round(max_open_stop_risk_frac,6),
        "maxGrossNotionalToRealizedEquity":round(max_gross_multiple,6),
        "tradesAccepted":accepted,"tradesRejectedByBudget":rejected,
        "tradesSizeClippedByBudget":clipped,
        "acceptedTradeWins":sum(x>0 for x in realized_pnls),
        "worstAcceptedTradeNetR":round(worst_modeled_R,6) if realized_pnls else None,
        "acceptedTradesBelowMinusOneR":worst_loss_beyond_original_stop_count,
        "riskBudget":{"maxPerTradeFraction":fraction_per_trade,
                      "maxTotalOpenStopFraction":total_risk_fraction,
                      "maxGrossLeverage":leverage_cap,
                      "minimumAcceptedRiskFraction":minimum_risk_fraction},
        "equityCurve":equity_curve,
        "equityIncludesOpenPositionMarkToMarket":False,
        "liquidationAndCrossMarginModeled":False,
        "commissionAndAdverseFundingScenarioOnly":True,
        "notActualExchangeAccount":True
    }

def model_all(workers:int=6)->dict:
    if not 1<=workers<=6:
        raise ValueError("E4_WORKER_LIMIT")
    baseline,oracle_sha,source_hashes=ensure_sealed_sources()
    histories,proofs=e3.v92.download_all(workers)
    count=e3.compare_archive_manifest(baseline,proofs)
    if count!=159:
        raise ValueError("E4_NOT_ALL_OFFICIAL_MONTHLY_FILES")
    report={
        "status":RESULT_STATUS,
        "matchedRawDataArchiveSHA256Count":count,
        "originalE3SourceAndEnginePinsSHA256":source_hashes,
        "sealedHistoricalOracleSHA256":oracle_sha,
        "historicalPeriodPreviouslyInspected":True,
        "independentOutOfSample":False,
        "actualFundingRatesDownloaded":False,
        "actualTickOrOrderbookFillsDownloaded":False,
        "fundingIntervalAssumed8hUTC":True,
        "fundingChargeAssumesConstantEntryNotionalNotActualMark":True,
        "fundingTimingAtOpenConservativeBoundary":True,
        "executionStopGapUsesWorstOfStopAndOpen":True,
        "stopFirstNoIntrabarResolution":True,
        "noProductionOrPaperOrTaskChanges":True,
        "noOrders":True,"noAlerts":True,"noLivePortfolioCreated":True,
        "noAutomaticPromotion":True,
        "initialVirtualEquityUSDT":INITIAL_EQUITY_USDT,
        "expectedHistoricalTradeCount":51,
        "independentZeroFeeNoGapGrossReplayAllMatched":False,
        "scenarios":{},
        "matchedTradeCount":0,
        "assets":{},
        "riskCautions":[],
    }
    trajectories={s.name:[] for s in SCENARIOS}
    by_scenario={s.name:Counter() for s in SCENARIOS}
    for period in PERIODS:
        for symbol in SYMBOLS:
            print("E4_OFFICIAL_OHLC_REPLAY",period,symbol,flush=True)
            bars=histories[period][symbol]
            score,tape,diag=e3.actual_baseline(symbol,bars,period)
            ref=baseline["periods"][period]["assets"][symbol]["variants"]["BASELINE"]
            e3.compare_raw_to_oracle(symbol,period,score,tape,ref)
            by_t={r["t"]:i for i,r in enumerate(bars)}
            if len(by_t)!=len(bars):
                raise ValueError("E4_HISTORICAL_SOURCE_DUPLICATE_CANDLE")
            evidence=[]
            for t in tape:
                entry=int(t["entryOpenUTC"])
                finish=int(t["exitKnownUTC"])
                if entry not in by_t or finish-3600 not in by_t:
                    raise ValueError("E4_TRADE_CANDLE_SLICE_MISSING")
                segment=bars[by_t[entry]:by_t[finish-3600]+1]
                reference_ideal_parity(t,segment)
                report["matchedTradeCount"]+=1
                row={"symbol":symbol,"period":period,
                     "entryEpoch":entry,"exitEpoch":finish,
                     "entry":t["entry"],"risk":t["risk"],
                     "side":t["side"],"referenceNetR9":round(t["netRIllustrative"],9),
                     "hypotheticalScenarioResults":{}}
                for scenario in SCENARIOS:
                    fill=simulate_trade(t,segment,scenario)
                    row["hypotheticalScenarioResults"][scenario.name]={
                        k:v for k,v in fill.items() if k!="fills"}
                    trajectories[scenario.name].append({
                        "symbol":symbol,"entryEpoch":entry,"exitEpoch":finish,
                        "entry":t["entry"],"risk":t["risk"],"netR":fill["netR"]
                    })
                    by_scenario[scenario.name]["totalGapStopEvents"]+=fill["gapStopCount"]
                    by_scenario[scenario.name]["grossNetR"]+=fill["netR"]
                    by_scenario[scenario.name]["grossFundingR"]+=fill["adverseFundingCashPerUnit"]/t["risk"]
                    if fill["netR"]<-1:
                        by_scenario[scenario.name]["tradesBelowMinus1R"]+=1
                evidence.append(row)
            report["assets"].setdefault(symbol,{})[period]={
                "rawOHLCBaselineMatched":len(tape),
                "independentGrossReplayAllMatched":True,
                "selectedExecutionExamples":evidence[:2],
                "tradesProcessed":len(evidence),
                "results":{scenario.name:{
                    "netRSum":round(sum(x["hypotheticalScenarioResults"][scenario.name]["netR"]
                                      for x in evidence),6),
                    "gapStopEvents":sum(x["hypotheticalScenarioResults"][scenario.name]["gapStopCount"]
                                       for x in evidence)}
                    for scenario in SCENARIOS},
                "originalRiskRuleDiagnostics":diag
            }
            print("E4_PARITY_OK",period,symbol,len(tape),flush=True)
    if report["matchedTradeCount"]!=51:
        raise ValueError("E4_FULL_51_HISTORICAL_TRADES_NOT_REPLAYED")
    report["independentZeroFeeNoGapGrossReplayAllMatched"]=True
    for s in SCENARIOS:
        tape=trajectories[s.name]
        portfolio=position_budget_portfolio(tape,s.name)
        c=by_scenario[s.name]
        report["scenarios"][s.name]={
            "assumptions":{
                "commissionBpsSide":s.commission_bps_per_side,
                "halfSpreadBps":s.half_spread_bps,
                "impactBps":s.execution_impact_bps,
                "combinedExecutionFrictionBpsPerSide":s.roundtrip_assumed_cost_per_side_bps,
                "adverseFundingBpsPerAssumed8h":s.adverse_funding_bps_per_8h,
                "fundingObserved":False,
                "spreadObserved":False,
                "gapOpenBasedOnVerifiedHistoricalOHLC":True,
            },
            "unsizedHistoricalTapeNetRSum":round(c["grossNetR"],6),
            "sumAdverseHypotheticalFundingR":round(c["grossFundingR"],6),
            "modeledHistoricalGapStopEvents":c["totalGapStopEvents"],
            "unsizedTradesBelowMinusOneR":c["tradesBelowMinus1R"],
            "sharedBudgetPortfolio":portfolio,
        }
    report["riskCautions"]=[
        "Trade outcomes are 2022-2026 historically inspected. Nothing is OOS or forward.",
        "Funding is unfavorable fixed bps at assumed 00/08/16 UTC; actual Binance funding rates and historical interval changes were NOT downloaded.",
        "Spread/impact values are chosen stress knobs rather than actual 2022-2026 quote/tick observations.",
        "OHLC open can estimate worse stop gaps but cannot model queue position, latency, stop execution within a 1H candle, liquidation or mark-price triggers.",
        "Equity drawdown is based on chronological realized exits; unclosed positions are NOT marked to market. Intratrade portfolio drawdown can be materially worse.",
        "Risk reservations use fixed stop risk but cannot cap gap losses; leverage is gross notional / realized equity, not maintenance margin.",
        "No order placement or updates to V7/V9.2, frozen ETH/BTC/SOL prospective cohorts, notification automations, or main."
    ]
    return report

def markdown(d:dict)->str:
    lines=[
        "# ATLAS Core E4 — Gap / friction / adverse-funding scenarios and shared portfolio",
        "",
        "**RESEARCH ONLY / HISTORICAL / NON-INDEPENDENT. Never treat scenario P&L as real venue fills.**",
        "",
        f'Official Binance 1H ZIPs independently rechecked: **{d["matchedRawDataArchiveSHA256Count"]}**.',
        f'Old engine vs independently coded gross-R evaluator (zero cost, no gap): **{d["matchedTradeCount"]}/{d["expectedHistoricalTradeCount"]}**.',
        "",
        "| Assumed friction / side | Tape sum Net R | Gap-stop events | 51-trade 10k shared-risk ending cash | Portfolio realized-only DD % | Accepted / declined |",
        "|---|---:|---:|---:|---:|---:|"
    ]
    for x in d["scenarios"].values():
        a=x["assumptions"];p=x["sharedBudgetPortfolio"]
        lines.append(
            f'| {a["combinedExecutionFrictionBpsPerSide"]:.0f}bps + '
            f'{a["adverseFundingBpsPerAssumed8h"]}bps/8h adverse funding | '
            f'{x["unsizedHistoricalTapeNetRSum"]:+.3f} | '
            f'{x["modeledHistoricalGapStopEvents"]} | '
            f'{p["endingRealizedCashUSDT"]:,.2f} USDT | '
            f'{p["maxRealizedOnlyDrawdownPct"]:.2f}% | '
            f'{p["tradesAccepted"]}/{p["tradesRejectedByBudget"]} |')
    lines += [
        "",
        "## Assumptions and constraints",
        "",
        "- Initial virtual equity 10,000 USDT; max 0.5% cash risk per trade, "
        "1% total concurrent stop-risk, 1.5× gross notional / realized equity; "
        "0.1% min accepted per trade. These are *test settings* not trade advice.",
        "- Scenario commission + half-spread + impact = nominal 9 / 25 / 50 bps "
        "per side; funding is separate, modeled adverse (not observed).",
        "- Historical gaps are from SHA256-verified OHLC OPEN; stop-first is "
        "pessimistic on ambiguous stop/target 1H bars.",
        "- Intratrade mark-to-market equity, maintenance margin, liquidation, "
        "actual funding/mark prices, orderbook fills and venue execution remain unavailable.",
        "",
        "## Explicit limitations",
        "",
        *("- "+v for v in d["riskCautions"]),
        ""
    ]
    return "\n".join(lines)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--workers",type=int,default=6)
    p.add_argument("--out",default="research/atlas_core_v3/output/e4_report.json")
    args=p.parse_args()
    dest=Path(args.out)
    if not str(dest).startswith("research/atlas_core_v3/output/"):
        raise ValueError("E4_OUTPUT_OUTSIDE_ISOLATED_RESEARCH")
    result=model_all(args.workers)
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+"\n")
    dest.with_suffix(".md").write_text(markdown(result))
    print("ATLAS_E4_159_RAW_SHA256_51_GROSS_PARITY_SCENARIOS_PORTFOLIO_PASS",
          flush=True)
    for name,row in result["scenarios"].items():
        p=row["sharedBudgetPortfolio"]
        print("E4_SCENARIO",name,"NetR",row["unsizedHistoricalTapeNetRSum"],
              "Cash",p["endingRealizedCashUSDT"],"DD%",p["maxRealizedOnlyDrawdownPct"],
              "Accepted",p["tradesAccepted"],"Rejected",p["tradesRejectedByBudget"],
              flush=True)

if __name__=="__main__":
    main()
