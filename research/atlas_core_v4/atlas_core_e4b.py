#!/usr/bin/env python3
"""E4-B: real archived Binance USD-M funding RATE events vs modeled E4-A.

159 official monthly fundingRate CSV ZIPs with publisher CHECKSUM verification,
combined with the 159 official 1H OHLC SHA256 ZIPs and E4-A's 51-trade
historical replay. No live changes, no orders, no external account data.

Actual funding rates/times/intervals are observed; cash fee is an ESTIMATE
because the settlement mark price and venue position notional are unavailable.
Use official 1H OHLC opening price as explicitly labeled mark-price PROXY.
"""
from __future__ import annotations

import argparse
import calendar
import csv
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha1, sha256
from io import StringIO
import json
from math import isfinite
from pathlib import Path
import re
from urllib.error import URLError, HTTPError
from urllib.request import Request, urlopen
from zipfile import ZipFile
from io import BytesIO

from research.atlas_core_v3 import atlas_core_e4 as e4
from research.atlas_core_v2 import atlas_core_e3 as e3
from research.atlas_core_v1 import atlas_core_e2 as e2

E4A_PINNED_GIT_BLOB="865e30925ecef323c54659a9720f89568c29d0ec"
STATUS="ATLAS_CORE_E4B_OBSERVED_FUNDING_RATES_PROXY_SETTLEMENT_HISTORICAL_ONLY"
BASE="https://data.binance.vision/data/futures/um/monthly/fundingRate"
EXPECTED_MONTH_COUNTS={"2022_2024":87,"2024_2026":72}
CSV_HEADER=("calc_time","funding_interval_hours","last_funding_rate")
EXPECTED_ASSETS=e2.ASSETS
EXPECTED_PERIODS=e2.PERIODS
SCENARIOS=e4.SCENARIOS
MAX_ARCHIVE_SIZE=2_000_000

def git_blob_sha1(raw:bytes):
    return sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()

def verify_frozen_e4a():
    raw=Path("research/atlas_core_v3/atlas_core_e4.py").read_bytes()
    if git_blob_sha1(raw)!=E4A_PINNED_GIT_BLOB:
        raise ValueError("E4B_E4A_EXECUTION_MODEL_CODE_DRIFT")
    oracle,oracle_sha,engines=e4.ensure_sealed_sources()
    return oracle,oracle_sha,{
        "E4A":sha256(raw).hexdigest(), **engines
    }

def epoch_month_bounds(month:str):
    if not re.fullmatch(r"20\d{2}-(0[1-9]|1[0-2])",month):
        raise ValueError("E4B_INVALID_FUNDING_MONTH")
    year,m=(int(x) for x in month.split("-"))
    start=int(datetime(year,m,1,tzinfo=timezone.utc).timestamp())
    if m==12:
        end=int(datetime(year+1,1,1,tzinfo=timezone.utc).timestamp())
    else:
        end=int(datetime(year,m+1,1,tzinfo=timezone.utc).timestamp())
    return start,end

def parse_official_csv(raw:bytes,symbol:str,month:str)->list[dict]:
    """Strict schema, signed decimal rates, UTC settlement times, no time fill."""
    if symbol not in EXPECTED_ASSETS:
        raise ValueError("E4B_UNKNOWN_SYMBOL")
    start,end=epoch_month_bounds(month)
    try:
        decoded=raw.decode("utf-8-sig")
        reader=csv.DictReader(StringIO(decoded))
        if tuple(reader.fieldnames or ())!=CSV_HEADER:
            raise ValueError("E4B_UNEXPECTED_OFFICIAL_FUNDING_CSV_SCHEMA")
        rows=[]
        prev=None
        for line,row in enumerate(reader,2):
            if set(row)!=set(CSV_HEADER) or any(v is None for v in row.values()):
                raise ValueError("E4B_MALFORMED_FUNDING_CSV_LINE:"+str(line))
            millis=int(row["calc_time"])
            # The public archive usually has exact settlement ms; tolerate
            # <= 999ms positive publisher jitter but never round a whole hour.
            secs=millis//1000
            if millis%1000>999 or secs%3600:
                raise ValueError("E4B_NON_HOURLY_SETTLEMENT_TIMESTAMP")
            if not start<=secs<end:
                raise ValueError("E4B_FUNDING_DATE_OUTSIDE_ARCHIVE_MONTH")
            interval=Decimal(row["funding_interval_hours"])
            if not interval.is_finite() or not Decimal("1")<=interval<=Decimal("24"):
                raise ValueError("E4B_INVALID_DECLARED_FUNDING_INTERVAL")
            rate=Decimal(row["last_funding_rate"])
            if not rate.is_finite() or abs(rate)>Decimal(".1"):
                raise ValueError("E4B_ABSURD_OR_INVALID_FUNDING_RATE")
            if prev is not None and millis<=prev:
                raise ValueError("E4B_DUPLICATE_OR_OUT_OF_ORDER_FUNDING_TIMESTAMP")
            prev=millis
            rows.append({
                "symbol":symbol,
                "fundingTimeMs":millis,
                "fundingEpoch":secs,
                "fundingIntervalHours":float(interval),
                "fundingRate":float(rate),
            })
    except (UnicodeError,InvalidOperation,KeyError,OverflowError) as exc:
        raise ValueError("E4B_CORRUPT_OFFICIAL_FUNDING_CSV") from exc
    if not rows:
        raise ValueError("E4B_EMPTY_OFFICIAL_FUNDING_MONTH")
    return rows

def download_byte_source(url:str, *, max_bytes:int)->bytes:
    """No secrets, no arbitrary host, no hidden network fallback."""
    if not url.startswith(BASE+"/") or "?" in url or ".." in url:
        raise ValueError("E4B_UNAPPROVED_FUNDING_ARCHIVE_URL")
    with urlopen(Request(url,headers={
        "User-Agent":"ATLAS-Quant-Engine-Research-FundingArchive/1.0"
    }),timeout=30) as response:
        raw=response.read(max_bytes+1)
        if len(raw)>max_bytes or not raw:
            raise ValueError("E4B_SOURCE_BYTES_TOO_BIG_OR_EMPTY")
        return raw

def fetch_month(symbol:str,month:str):
    if symbol not in EXPECTED_ASSETS:
        raise ValueError("E4B_UNKNOWN_SYMBOL")
    epoch_month_bounds(month)
    name=f"{symbol}-fundingRate-{month}.zip"
    url=f"{BASE}/{symbol}/{name}"
    checksum=download_byte_source(url+".CHECKSUM",max_bytes=500)
    try:
        line=checksum.decode("utf-8-sig").strip()
    except UnicodeError as exc:
        raise ValueError("E4B_OFFICIAL_CHECKSUM_BAD_ENCODING") from exc
    tokens=line.split()
    if (len(tokens)!=2 or not re.fullmatch("[a-fA-F0-9]{64}",tokens[0])
        or tokens[1]!=name):
        raise ValueError("E4B_MALFORMED_OFFICIAL_SHA256_CHECKSUM")
    zip_data=download_byte_source(url,max_bytes=MAX_ARCHIVE_SIZE)
    actual=sha256(zip_data).hexdigest()
    if actual.lower()!=tokens[0].lower():
        raise ValueError("E4B_OFFICIAL_FUNDING_ARCHIVE_SHA256_MISMATCH")
    with ZipFile(BytesIO(zip_data)) as z:
        if z.namelist()!=[name.replace(".zip",".csv")]:
            raise ValueError("E4B_FUNDING_ZIP_UNEXPECTED_MEMBERS")
        meta=z.getinfo(z.namelist()[0])
        if meta.file_size>MAX_ARCHIVE_SIZE:
            raise ValueError("E4B_UNZIPPED_CSV_TOO_LARGE")
        payload=z.read(meta)
    events=parse_official_csv(payload,symbol,month)
    proof={
        "symbol":symbol,"month":month,"archiveURL":url,
        "checksumURL":url+".CHECKSUM",
        "zipSHA256":actual,
        "csvSHA256":sha256(payload).hexdigest(),
        "events":len(events),
        "firstFundingEpoch":events[0]["fundingEpoch"],
        "lastFundingEpoch":events[-1]["fundingEpoch"],
    }
    return symbol,month,events,proof

def check_timeline_coverage(rows:list[dict],start:int,end:int,symbol:str):
    """Ensure no silent truncation, missing middle events or duplicate times.

    Interval can change historically. A gap must be explainable by the
    adjacent publisher-declared settlement intervals (1–24h). If it is
    longer, treat source as incomplete rather than interpolating.
    """
    if not rows or any(x["symbol"]!=symbol for x in rows):
        raise ValueError("E4B_SYMBOL_FUNDING_TIMELINE_MISSING")
    if rows[0]["fundingEpoch"]>start+rows[0]["fundingIntervalHours"]*3600:
        raise ValueError("E4B_FUNDING_MISSING_PERIOD_BEGIN")
    if rows[-1]["fundingEpoch"]<end-rows[-1]["fundingIntervalHours"]*3600:
        raise ValueError("E4B_FUNDING_MISSING_PERIOD_END")
    prev=None
    observed_intervals=set()
    for row in rows:
        ts=row["fundingEpoch"]
        if ts<start or ts>=end:
            raise ValueError("E4B_FUNDING_EVENT_OUT_OF_PERIOD")
        interval=row["fundingIntervalHours"]
        observed_intervals.add(interval)
        if prev:
            delta=(ts-prev["fundingEpoch"])/3600
            if delta<=0:
                raise ValueError("E4B_FUNDING_DUPLICATE_OR_UNSORTED")
            max_plausible=max(interval,prev["fundingIntervalHours"])
            if delta>max_plausible+0.0003:
                raise ValueError("E4B_FUNDING_HOLE_NOT_COVERED_BY_INTERVAL")
        prev=row
    return {"fundingEvents":len(rows),
            "observedFundingIntervalsHours":sorted(observed_intervals),
            "firstFundingEpoch":rows[0]["fundingEpoch"],
            "lastFundingEpoch":rows[-1]["fundingEpoch"],
            "completeByDeclaredIntervals":True}

def download_all_funding(workers:int=6):
    if not 1<=workers<=6:
        raise ValueError("E4B_DOWNLOAD_WORKER_LIMIT")
    raw={}
    proofs={p:[] for p in EXPECTED_PERIODS}
    periods=e3.v92.PERIODS
    futures={}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for period in EXPECTED_PERIODS:
            for symbol in EXPECTED_ASSETS:
                for month in periods[period]["months"]:
                    future=pool.submit(fetch_month,symbol,month)
                    futures[future]=(period,symbol,month)
        for future in as_completed(futures):
            period,symbol,month=futures[future]
            got_symbol,got_month,events,proof=future.result()
            if got_symbol!=symbol or got_month!=month:
                raise ValueError("E4B_FUNDING_DOWNLOAD_RETURNED_WRONG_PAIR")
            raw[(period,symbol,month)]=events
            proofs[period].append(proof)
    timeline={}
    coverage={}
    for period in EXPECTED_PERIODS:
        if len(proofs[period])!=EXPECTED_MONTH_COUNTS[period]:
            raise ValueError("E4B_FUNDING_ARCHIVE_COUNT_MISMATCH")
        if len({(x["symbol"],x["month"]) for x in proofs[period]})!=len(proofs[period]):
            raise ValueError("E4B_DUPLICATE_MONTH_IN_ARCHIVE_PROOF")
        p=periods[period]
        start=e3.v92.epoch(p["warmup"])
        end=e3.v92.epoch(p["end"])
        for symbol in EXPECTED_ASSETS:
            rows=[event for month in p["months"]
                  for event in raw[(period,symbol,month)]]
            coverage[(period,symbol)]=check_timeline_coverage(rows,start,end,symbol)
            timeline[(period,symbol)]=rows
        proofs[period].sort(key=lambda x:(x["symbol"],x["month"]))
    return timeline,proofs,coverage

def calculate_observed_funding(
        trade:dict, bars:list[dict], no_funding_exec:dict,
        funding_events:list[dict])->dict:
    """Signed real funding rate * historical OHLC open-price mark PROXY.

    Position fraction at settlement comes from TP/stop fills strictly in
    earlier hours. Settlement at exact entry or exit excluded as ambiguous
    ownership. This is not actual account funding cash or official mark.
    """
    start,end=e4.validate_history_window(bars,trade)
    if no_funding_exec["adverseFundingCashPerUnit"]!=0:
        raise ValueError("E4B_BASE_FUNDING_NOT_DISABLED")
    if no_funding_exec["wasObservedRealFill"]:
        raise ValueError("E4B_FALSE_EXECUTION_OBSERVATION")
    if any(int(bar["t"])!=start+i*3600 for i,bar in enumerate(bars)):
        raise ValueError("E4B_GAPPED_OR_MALFORMED_OHLC")
    side=trade["side"]
    sign=1 if side=="bullish" else -1
    out=[]
    total_signed_cost=0.0
    prev=-1
    for event in funding_events:
        if event["symbol"] not in EXPECTED_ASSETS:
            raise ValueError("E4B_BAD_FUNDING_EVENT_SYMBOL")
        ts=event["fundingEpoch"]
        if ts<=prev:
            raise ValueError("E4B_UNORDERED_FUNDING_EVENTS")
        prev=ts
        if not start<ts<end:
            continue
        if ts%3600 or ts not in {int(x["t"]) for x in bars}:
            raise ValueError("E4B_FUNDING_HOUR_CANNOT_BE_PRICED")
        # At the boundary, fills in older candles are already completed;
        # no fill from the funding hour is assumed to happen first.
        fraction_closed=sum(float(x["positionFractionClosed"])
             for x in no_funding_exec["fills"] if x["barOpenUTC"]<ts)
        position_remaining=1-fraction_closed
        if not -1e-8<=position_remaining<=1+1e-8:
            raise ValueError("E4B_IMPOSSIBLE_REMAINING_POSITION")
        position_remaining=max(0.,min(1.,position_remaining))
        price=bars[(ts-start)//3600]["o"]
        if not isfinite(price) or price<=0:
            raise ValueError("E4B_BAD_SETTLEMENT_MARK_PROXY")
        rate=event["fundingRate"]
        if not isfinite(rate) or abs(rate)>.1:
            raise ValueError("E4B_INVALID_OBSERVED_FUNDING_RATE")
        signed_cash_cost=sign*position_remaining*rate*price
        total_signed_cost+=signed_cash_cost
        out.append({
            "fundingTimeEpoch":ts,
            "fundingRateObserved":rate,
            "publisherDeclaredIntervalHours":event["fundingIntervalHours"],
            "positionFractionBeforeFunding":round(position_remaining,8),
            "hourlyOHLCOpenAsMarkProxy":round(price,8),
            "signedCashCostPerOneUnitProxy":round(signed_cash_cost,10),
            "markPriceObserved":False,
        })
    return {
        "matchedActualFundingRateEvents":len(out),
        "signedFundingCashCostPerUnitProxy":round(total_signed_cost,10),
        "signedFundingRProxy":round(total_signed_cost/trade["risk"],9),
        "events":out,
        "cashIsModeledWithOHLCMarkProxy":True,
        "actualFundingRateAndTimestampObserved":True,
        "actualAccountCashDebitOrCreditObserved":False,
        "fundingOnEntryAndExitBoundaryExcluded":True,
    }

def estimate_with_actual_rates(
        trade:dict,bars:list[dict],scenario:e4.Scenario,
        funding_events:list[dict])->dict:
    zero_funding=e4.Scenario(
       name="same-execution-friction_without_assumed_funding",
       commission_bps_per_side=scenario.commission_bps_per_side,
       half_spread_bps=scenario.half_spread_bps,
       execution_impact_bps=scenario.execution_impact_bps,
       adverse_funding_bps_per_8h=0,
       gap_stop=scenario.gap_stop,
    )
    no_funding=e4.simulate_trade(trade,bars,zero_funding)
    actual=calculate_observed_funding(trade,bars,no_funding,funding_events)
    r=(no_funding["netCashPerUnit"]-actual["signedFundingCashCostPerUnitProxy"])/trade["risk"]
    if not isfinite(r):
        raise ValueError("E4B_NONFINITE_NET_R")
    return {
        "netR":round(r,9),
        "netRWithoutFunding":no_funding["netR"],
        "netRDeltaDueToObservedRateWithProxy":round(-actual["signedFundingRProxy"],9),
        "actualRateFunding":actual,
        "modeledSpreadImpactAndCommissionUnchanged":True,
        "modeledStopsAndTPsUnchanged":True,
    }

def compute(workers:int=6)->dict:
    if not 1<=workers<=6:
        raise ValueError("E4B_WORKER_COUNT")
    frozen,oracle_sha,sources=verify_frozen_e4a()
    # Both official sources re-downloaded and SHA-256 verified; nothing
    # is written into Git or any paper/live forward journal.
    bars_by_period,bar_proofs=e3.v92.download_all(workers)
    bar_count=e3.compare_archive_manifest(frozen,bar_proofs)
    if bar_count!=159:
        raise ValueError("E4B_SEALED_OHLC_ARCHIVES_MISSING")
    funding,fp,coverage=download_all_funding(workers)
    funding_count=sum(len(x) for x in fp.values())
    if funding_count!=159:
        raise ValueError("E4B_NOT_159_FUNDING_ZIPS")
    result={
        "status":STATUS,
        "researchOnly":True,"historicallyInspected":True,
        "independentOutOfSample":False,
        "newForwardTrades":0,
        "mainOrProductionOrPaperOrAutomationChanged":False,
        "ordersPlaced":False,"notificationsSent":False,
        "tradingCandidateAutomaticallyPromoted":False,
        "sealedOracleSHA256":oracle_sha,
        "sourceCodeHashesSHA256":sources,
        "officialOHLCZipSHA256Verified":bar_count,
        "officialFundingZipSHA256Verified":funding_count,
        "officialFundingArchiveManifests":fp,
        "fundingTimelineCoveredByDeclaredIntervals":True,
        "actualFundingRatesObserved":True,
        "actualFundingEventTimesObserved":True,
        "actualFundingIntervalsObserved":True,
        "actualVenueSettlementMarkPriceObserved":False,
        "hourlyOHLCOpenUsedAsSettlementMarkProxy":True,
        "actualAccountFundingPaymentsObserved":False,
        "actualSpreadOrOrderbookOrFillObserved":False,
        "fundingAtExactEntryExitExcluded":True,
        "riskBudgetIsOriginalE4AUnchanged":True,
        "matchedHistoricalTrades":0,
        "observedFundingEventsInDataset":0,
        "observedFundingEventsWhilePositionOpen":0,
        "assets":{},"scenarios":{},
        "riskCautions":[
            "Original 51 V9.2 trades are known, selected historical data, not unseen OOS.",
            "Rates and settlement timestamps are real official monthly Binance funding archive records with SHA256 publisher checksums.",
            "Funding cash is an estimate: official settlement mark prices are not present in the monthly funding ZIP; 1H trade OHLC open serves only as a marked proxy.",
            "This is NOT actual exchange account funding credit/debit: there are no user positions or account income entries.",
            "Funding events exactly at hypothetical trade entry or exit excluded as ambiguous execution/settlement order.",
            "The fee/spread/impact knobs are preserved hypothetical E4A 9,25,50 bps-per-side scenarios. No historical orderbook was fetched.",
            "Gap stop and stop-first remain 1H candle approximations; no intrabar tick, exchange queue, partial-market fill or liquidation.",
            "Shared portfolio equity and DD are REALIZED ONLY: open trade mark-to-market and maintenance margin not implemented.",
            "Any archive checksum or unexplained interval hole aborts rather than fabricating an event.",
            "No changes to V7, V9.2, paper accounts, ETH/BTC/SOL prospective frozen cohorts, scheduled reports, alerts or main."
        ]
    }
    trajectories_actual={s.name:[] for s in SCENARIOS}
    trajectories_e4a={s.name:[] for s in SCENARIOS}
    scenarios_tape={s.name:{"totalNetRObservedRateProxy":0.0,
                            "totalNetRE4AAdverseFunding":0.0,
                            "fundingNetRProxy":0.0,
                            "fundingEventMatches":0,
                            "longEventMatches":0,
                            "shortEventMatches":0,
                            "fundingPositiveCashCostEvents":0,
                            "fundingNegativeCashCreditEvents":0}
                    for s in SCENARIOS}
    for period in EXPECTED_PERIODS:
        for symbol in EXPECTED_ASSETS:
            print("E4B_VERIFY_1H_BARS_AND_FUNDING",period,symbol,flush=True)
            rows=bars_by_period[period][symbol]
            score,tape,diag=e3.actual_baseline(symbol,rows,period)
            ref=frozen["periods"][period]["assets"][symbol]["variants"]["BASELINE"]
            e3.compare_raw_to_oracle(symbol,period,score,tape,ref)
            if len(tape)!=ref["trades"]:
                raise ValueError("E4B_SEALED_BASELINE_COUNT_DRIFT")
            times={bar["t"]:i for i,bar in enumerate(rows)}
            frows=funding[(period,symbol)]
            result["observedFundingEventsInDataset"]+=len(frows)
            stats=coverage[(period,symbol)]
            position_evidence=[]
            for t in tape:
                start,end=e4.validate_trade(t)
                if start not in times or end-3600 not in times:
                    raise ValueError("E4B_MISSING_1H_POSITION_BARS")
                bar_slice=rows[times[start]:times[end-3600]+1]
                e4.reference_ideal_parity(t,bar_slice)
                result["matchedHistoricalTrades"]+=1
                bounded=[x for x in frows if start<=x["fundingEpoch"]<=end]
                info={
                    "symbol":symbol,
                    "entryEpoch":start,"exitEpoch":end,
                    "side":t["side"],
                    "entry":t["entry"],"risk":t["risk"],
                    "period":period,
                    "e4aVersusActualFunding":{},
                }
                for s in SCENARIOS:
                    historical=e4.simulate_trade(t,bar_slice,s)
                    observed=estimate_with_actual_rates(t,bar_slice,s,bounded)
                    base={
                        "symbol":symbol,"entryEpoch":start,"exitEpoch":end,
                        "entry":t["entry"],"risk":t["risk"]
                    }
                    trajectories_e4a[s.name].append({**base,"netR":historical["netR"]})
                    trajectories_actual[s.name].append({**base,"netR":observed["netR"]})
                    data=scenarios_tape[s.name]
                    data["totalNetRObservedRateProxy"]+=observed["netR"]
                    data["totalNetRE4AAdverseFunding"]+=historical["netR"]
                    data["fundingNetRProxy"]+=observed["actualRateFunding"]["signedFundingRProxy"]
                    receipts=observed["actualRateFunding"]["events"]
                    data["fundingEventMatches"]+=len(receipts)
                    data["longEventMatches"]+=len(receipts) if t["side"]=="bullish" else 0
                    data["shortEventMatches"]+=len(receipts) if t["side"]=="bearish" else 0
                    data["fundingPositiveCashCostEvents"]+=sum(
                        x["signedCashCostPerOneUnitProxy"]>0 for x in receipts)
                    data["fundingNegativeCashCreditEvents"]+=sum(
                        x["signedCashCostPerOneUnitProxy"]<0 for x in receipts)
                    info["e4aVersusActualFunding"][s.name]={
                        "netRE4AAdverseFunding":historical["netR"],
                        "netRObservedRateWithMarkProxy":observed["netR"],
                        "fundingEventCount":len(receipts),
                        "actualFundingRateEventsWithProxyMark":receipts,
                    }
                position_evidence.append(info)
            result["assets"].setdefault(symbol,{})[period]={
                "historicalTradesMatched":len(tape),
                "officialFundingTimeline":stats,
                "firstTwoTradeEvidenceExamples":position_evidence[:2],
                "observedTradeFundingEvents":sum(
                    len(x["e4aVersusActualFunding"][SCENARIOS[0].name]
                        ["actualFundingRateEventsWithProxyMark"])
                    for x in position_evidence),
                "allThreeE4ACostScenariosPreserved":True,
            }
            print("E4B_PERIOD_PARITY",period,symbol,len(tape),
                  "FUNDING_EVENTS",stats["fundingEvents"],flush=True)

    if result["matchedHistoricalTrades"]!=51:
        raise ValueError("E4B_NOT_ALL_51_TAPES")
    for scenario in SCENARIOS:
        name=scenario.name
        c=scenarios_tape[name]
        p_actual=e4.position_budget_portfolio(trajectories_actual[name],name)
        p_e4a=e4.position_budget_portfolio(trajectories_e4a[name],name)
        if p_actual["tradesAccepted"]+p_actual["tradesRejectedByBudget"]!=51:
            raise ValueError("E4B_PORTFOLIO_COHORT_LOST")
        if p_e4a["tradesAccepted"]+p_e4a["tradesRejectedByBudget"]!=51:
            raise ValueError("E4B_A_COMPARISON_COHORT_LOST")
        result["scenarios"][name]={
            "executionAssumptionsUnchanged":{
                "commissionBpsPerSide":scenario.commission_bps_per_side,
                "halfSpreadBpsPerSide":scenario.half_spread_bps,
                "impactBpsPerSide":scenario.execution_impact_bps,
                "frictionTotalBpsPerSide":scenario.roundtrip_assumed_cost_per_side_bps,
                "oldE4AAssumedAdverseFundingBpsPer8h":scenario.adverse_funding_bps_per_8h,
                "fundingRateSource":"Official USD-M fundingRate monthly CSV ZIPs",
                "markPriceSource":"OHLC_1H_OPEN_PROXY_NOT_SETTLEMENT_MARK",
            },
            "aggregatePriorE4ANetR":round(c["totalNetRE4AAdverseFunding"],6),
            "aggregateActualRateProxyMarkNetR":round(c["totalNetRObservedRateProxy"],6),
            "aggregateSignedFundingCostRProxy":round(c["fundingNetRProxy"],6),
            "fundingEventMatches":c["fundingEventMatches"],
            "longFundingEventMatches":c["longEventMatches"],
            "shortFundingEventMatches":c["shortEventMatches"],
            "rateEventsPayingFundingCost":c["fundingPositiveCashCostEvents"],
            "rateEventsReceivingFundingCredit":c["fundingNegativeCashCreditEvents"],
            "priorE4AAdverseAssumptionPortfolio":p_e4a,
            "actualRateProxyMarkPortfolio":p_actual,
            "endingCashDeltaUSDT":round(p_actual["endingRealizedCashUSDT"]-
                                        p_e4a["endingRealizedCashUSDT"],4),
        }
        print("E4B_SCENARIO_REAL_RATE",name,"events",c["fundingEventMatches"],
              "E4A_USDT",p_e4a["endingRealizedCashUSDT"],
              "E4B_USDT",p_actual["endingRealizedCashUSDT"],
              "Delta_USDT",result["scenarios"][name]["endingCashDeltaUSDT"],
              flush=True)
    first_name=SCENARIOS[0].name
    result["observedFundingEventsWhilePositionOpen"]=result["scenarios"][first_name]["fundingEventMatches"]
    if result["observedFundingEventsWhilePositionOpen"]==0:
        raise ValueError("E4B_NO_OPEN_TRADE_FUNDING_EVENTS_SUSPICIOUS")
    # Published E4-A comparison numbers pinned from successful original
    # CI (43638440671). Same original code and official source must
    # reproduce these within rounding, preventing comparison drift.
    expected_a={"9bps_per_side_plus_adverse_funding":10271.8196,
                "25bps_per_side_plus_adverse_funding":9503.8182,
                "50bps_per_side_plus_adverse_funding":8376.7766}
    for name,want in expected_a.items():
        got=result["scenarios"][name]["priorE4AAdverseAssumptionPortfolio"]["endingRealizedCashUSDT"]
        if abs(got-want)>.02:
            raise ValueError("E4B_PRIOR_E4A_RECALCULATION_DRIFT:"+name+":"+str(got))
    result["originalE4AOutputsExactReproduced"]=True
    return result

def markdown(d:dict)->str:
    lines=[
        "# ATLAS Core E4-B — observed Binance funding RATE vs E4-A adverse assumptions",
        "",
        "**HISTORICAL RESEARCH ONLY / no new forward or paper trade. Funding cash uses mark-price PROXY, not real exchange settlement cash.**",
        "",
        "Fundamental distinction: The **rates, times, intervals and data archive hashes** are observed officially;",
        "funding USDT is a **modeled estimate** (the archive contains no exact settlement mark price).",
        "",
        f'Official 1H OHLC ZIPs SHA256: {d["officialOHLCZipSHA256Verified"]}; '
        f'official fundingRate ZIPs SHA256: {d["officialFundingZipSHA256Verified"]}.',
        f'Original historic 1H engine trades matched: {d["matchedHistoricalTrades"]}.',
        f'Historical recorded funding events (entire 6 period-asset raw datasets): {d["observedFundingEventsInDataset"]}.',
        f'Observed funding rate events overlapping a trade: {d["observedFundingEventsWhilePositionOpen"]}.',
        "",
        "| Unchanged modeled fee/spread/impact side | E4-A adverse funding ending cash | E4-B official rate + proxy mark ending cash | Difference | Signed historical funding R cost / credit (proxy) |",
        "|---|---:|---:|---:|---:|",
    ]
    for name,s in d["scenarios"].items():
        p=s["priorE4AAdverseAssumptionPortfolio"]
        q=s["actualRateProxyMarkPortfolio"]
        side=s["executionAssumptionsUnchanged"]["frictionTotalBpsPerSide"]
        lines.append(
            f'| {side:.0f} bps | {p["endingRealizedCashUSDT"]:,.2f} USDT | '
            f'{q["endingRealizedCashUSDT"]:,.2f} USDT | '
            f'{s["endingCashDeltaUSDT"]:+,.2f} USDT | '
            f'{s["aggregateSignedFundingCostRProxy"]:+.6f} R |')
    lines += [
        "",
        "## Explicit limitations",
        *("- "+v for v in d["riskCautions"]),
        "",
        "Research output in temporary GitHub Actions artifact only. No production, paper account, "
        "prospective candidate, automation or main repo writes.",
        ""
    ]
    return "\n".join(lines)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--workers",type=int,default=6)
    p.add_argument("--out",default="research/atlas_core_v4/output/e4b_report.json")
    args=p.parse_args()
    path=Path(args.out)
    if not str(path).startswith("research/atlas_core_v4/output/"):
        raise ValueError("E4B_OUTPUT_MUST_BE_ISOLATED")
    report=compute(args.workers)
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True)+"\n")
    path.with_suffix(".md").write_text(markdown(report))
    print("ATLAS_E4B_OFFICIAL_159_FUNDING_SHA256_AND_159_CANDLES_51_MATCHED_REAL_RATE_PROXY_PORTFOLIO_PASS",flush=True)

if __name__=="__main__":
    main()
