#!/usr/bin/env python3
"""ATLAS Core E5-A — read-only decision research, NOT trading recommendations.

Historical 51 V9.2 records demonstrate a predeclared risk/cost gate.
Live public market_data / structure snapshots are informational context,
never a verified V9.2 entry. Frozen prospective branches are unchanged
and do not contain qualifying completed-month evidence yet.

No broker calls, push, accounts, alerts, schedules, or production edits.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
from functools import lru_cache
from hashlib import sha1, sha256
import json
from math import isfinite
from pathlib import Path
from urllib.request import Request, urlopen

from research.atlas_core_v1 import atlas_core_e2 as e2

STATUS="ATLAS_CORE_E5A_READ_ONLY_SHADOW_CONTRACT_HISTORICAL_DEMO_NO_LIVE_SIGNAL"
SOURCE_PINS={
    "research/atlas_core_v4/atlas_core_e4b.py":"29bea883db085a9ed9591f411a20698b45a8caa0",
    "forward/btc_sol_v93_prospective_20261114/frozen_spec.json":"3086de7b9a2835a10baf778693899b68cc6a400d",
    "forward/btc_sol_v93_prospective_20261114/preflight.json":"8f3e187bf031ac1f7ee9517c21919c07da9de692",
    "forward/v93_shadow_prospective_20261113/frozen_spec.json":"44cdd8a04e83dbd003efbfa40c5e5ac795bb310a",
    "forward/v93_shadow_prospective_20261113/preflight.json":"d736fac5a26cce81831ae55b52a9fdae191135d1",
}
FUTURE_FREEZE={"ETHUSDT":"2026-11-14T00:00:00Z",
               "BTCUSDT":"2026-11-15T00:00:00Z",
               "SOLUSDT":"2026-11-15T00:00:00Z"}
OUT=Path("research/atlas_core_v5/output")
START_EQUITY=10000.0
MAX_RISK_PER_TRADE=.005
MAX_TOTAL_OPEN_RISK=.01
MAX_NOTIONAL_MULTIPLE=1.5
MIN_ACCEPTED_RISK=.001
FULL_TP3_GROSS_R=2.0
# No historical fitting of thresholds. Cautionary hypothetical costs.
SCENARIOS_BPS=(9,25,50)
FUNDING_RESERVE_BPS_PER_8H=3.0
MAX_HOLD_HOURS=24
MIN_AFTER_25BPS_FULL_TP3_NET_R=1.0

def git_sha(raw:bytes):
    return sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()

def get_pinned_source(path:str):
    raw=Path(path).read_bytes()
    expected=SOURCE_PINS[path]
    if git_sha(raw)!=expected:
        raise ValueError("E5A_FROZEN_SOURCE_GIT_BLOB_DRIFT:"+path)
    obj=json.loads(raw) if path.endswith(".json") else None
    return obj,sha256(raw).hexdigest()

def strict_utc(s:str)->int:
    if not isinstance(s,str) or not s.endswith("Z"):
        raise ValueError("E5A_TIMESTAMP_MUST_BE_UTC_Z")
    try: d=datetime.fromisoformat(s.replace("Z","+00:00"))
    except ValueError as e: raise ValueError("E5A_INVALID_TIMESTAMP") from e
    if d.utcoffset().total_seconds()!=0:
        raise ValueError("E5A_TIMESTAMP_NOT_UTC")
    return int(d.timestamp())

def froze_sources():
    hashes={}
    snapshots={}
    for path in SOURCE_PINS:
        data,digest=get_pinned_source(path)
        hashes[path]=digest
        if data is not None:snapshots[path]=data
    btc=snapshots["forward/btc_sol_v93_prospective_20261114/frozen_spec.json"]
    bpre=snapshots["forward/btc_sol_v93_prospective_20261114/preflight.json"]
    eth=snapshots["forward/v93_shadow_prospective_20261113/frozen_spec.json"]
    epre=snapshots["forward/v93_shadow_prospective_20261113/preflight.json"]
    if (btc["freezeUTC"]!=FUTURE_FREEZE["BTCUSDT"]
        or eth["freezeUTC"]!=FUTURE_FREEZE["ETHUSDT"]
        or bpre["freezeUTC"]!=btc["freezeUTC"]
        or epre["startProspectiveUTC"]!=eth["freezeUTC"]):
        raise ValueError("E5A_PROSPECTIVE_FREEZE_SOURCE_CHANGED")
    if (bpre["status"]!="BTC_SOL_PREFREEZE_PIPELINE_TEST_ONLY"
        or epre["status"]!="PREFREEZE_PIPELINE_SMOKE_TEST"
        or bpre["realOrders"] or bpre["notifications"]
        or not epre["neverRealOrders"] or not epre["cannotCreditAnyPreFreezeTrade"]):
        raise ValueError("E5A_PREFREEZE_SOURCE_MISCLASSIFIED")
    b_latest=Path("forward/btc_sol_v93_prospective_20261114/latest.json")
    e_latest=Path("forward/v93_shadow_prospective_20261113/latest.json")
    if b_latest.exists() or e_latest.exists():
        # E5-A is not a monthly candidate reader. A separate verified
        # E5-B adapter is required before any prospective rows can be
        # turned into cards.
        return hashes,{
            "status":"PROSPECTIVE_SNAPSHOTS_PRESENT_BUT_NO_E5A_VALIDATED_ADAPTER",
            "actualForwardTradesCredited":0,"noLiveSignalReady":True
        }
    return hashes,{
        "status":"NO_COMPLETED_POSTFREEZE_PROSPECTIVE_MONTHLY_SNAPSHOT_YET",
        "actualForwardTradesCredited":0,"noLiveSignalReady":True
    }

@lru_cache(maxsize=1)
def historical_rows():
    """Immutable historical oracle; exit/returns are NOT fed to decision."""
    p,hashp=e2.read_pinned(e2.SOURCE)
    older,_=e2.read_pinned(e2.OLDER)
    later,_=e2.read_pinned(e2.LATER)
    normalized=[]
    for period in e2.PERIODS:
        for symbol in e2.ASSETS:
            ref=p["periods"][period]["assets"][symbol]["variants"]["BASELINE"]
            witness=e2.witness_of(older,later,period,symbol)
            evidence=ref["tradeEvidence"]
            other=witness["tradeEntryExitEvidence"]
            if len(evidence)!=len(other) or len(evidence)!=ref["trades"]:
                raise ValueError("E5A_FROZEN_HISTORICAL_TRADE_COUNT_DRIFT")
            for a,b in zip(evidence,other):
                if (a["entryUTC"],a["exitUTC"],a["side"],a["netR9Bps"])!=(
                    b["entryUTC"],b["exitUTC"],b["side"],b["netR9bps"]):
                    raise ValueError("E5A_ORACLE_INDEPENDENT_WITNESS_MISMATCH")
                if a["retestUTC"]!=b["retestUTC"]:
                    raise ValueError("E5A_RETEST_REFERENCE_MISMATCH")
                packet={
                    "sourceKind":"SEALED_HISTORICAL_V92_REFERENCE_DEMO",
                    "asset":symbol,"period":period,
                    "watchKnownUTC":b["watchUTC"],
                    "retestKnownUTC":a["retestUTC"],
                    "entryOpenUTC":a["entryUTC"],
                    "asOfUTC":a["entryUTC"],
                    "side":a["side"],
                    "entryPrice":a["entry"],
                    "referenceRiskPctRounded":a["riskPct"],
                    "immutableSourceSHA256":hashp,
                    "isProspective":False,
                }
                # Do not pass exit, netR or any future-outcome field.
                normalized.append(packet)
    if len(normalized)!=51:
        raise ValueError("E5A_HISTORICAL_REFERENCE_NOT_51")
    return normalized

def validate_packet(pkt:dict):
    required={"sourceKind","asset","watchKnownUTC","retestKnownUTC",
              "entryOpenUTC","asOfUTC","side","entryPrice",
              "referenceRiskPctRounded","immutableSourceSHA256"}
    if set(pkt)!=required|{"period","isProspective"}:
        raise ValueError("E5A_UNEXPECTED_OR_MISSING_PACKET_FIELDS")
    if pkt["sourceKind"]!="SEALED_HISTORICAL_V92_REFERENCE_DEMO":
        raise ValueError("E5A_UNATTESTED_SIGNAL_KIND")
    if pkt["isProspective"] is not False:
        raise ValueError("E5A_FALSE_FORWARD_CLAIM")
    if pkt["asset"] not in e2.ASSETS or pkt["side"] not in ("bullish","bearish"):
        raise ValueError("E5A_INVALID_ASSET_OR_DIRECTION")
    if pkt["period"] not in e2.PERIODS:
        raise ValueError("E5A_UNSEALED_PERIOD")
    watch,retest,entry,asof=(strict_utc(pkt[x]) for x in
                             ("watchKnownUTC","retestKnownUTC","entryOpenUTC","asOfUTC"))
    if not (watch<retest==entry==asof):
        raise ValueError("E5A_BAD_V92_CAUSAL_ENTRY_SEQUENCE")
    if any(t%3600 for t in (watch,retest,entry)):
        raise ValueError("E5A_NON_HOURLY_TRADE_EVENT")
    price,risk_pct=pkt["entryPrice"],pkt["referenceRiskPctRounded"]
    if not isinstance(price,(int,float)) or not isinstance(risk_pct,(int,float)):
        raise ValueError("E5A_BAD_PRICE_OR_RISK")
    if not all(isfinite(x) for x in (price,risk_pct)) or price<=0 or not .1<=risk_pct<=4:
        raise ValueError("E5A_BAD_PRICE_OR_STOP_PERCENTAGE")
    if not isinstance(pkt["immutableSourceSHA256"],str) or len(pkt["immutableSourceSHA256"])!=64:
        raise ValueError("E5A_BAD_SOURCE_DIGEST")
    # Self-assertion of a historic label is NOT a verified signal.
    # Every field must match a frozen, source-hashed historical record.
    if not any(pkt==canonical for canonical in historical_rows()):
        raise ValueError("E5A_FABRICATED_HISTORICAL_TRADE_NOT_IN_PINNED_TAPE")
    return entry,risk_pct/100

def validate_positions(snapshot:dict|None, *, as_of:int):
    """No portfolio risk PASS without explicit verified account read-only data.

    For historical demonstrations the caller may request a labeled
    synthetic flat account. This does not represent real account state.
    """
    if snapshot is None:
        return None
    if snapshot.get("kind") not in ("SYNTHETIC_FLAT_DEMO","VERIFIED_READ_ONLY_PAPER_SNAPSHOT"):
        raise ValueError("E5A_UNSUPPORTED_OPEN_POSITION_SOURCE")
    if strict_utc(snapshot["asOfUTC"])!=as_of:
        raise ValueError("E5A_STALE_OR_FUTURE_POSITION_SNAPSHOT")
    equity=float(snapshot["realizedEquityUSDT"])
    if not isfinite(equity) or equity<=0:
        raise ValueError("E5A_INVALID_EQUITY")
    positions=snapshot["openPositions"]
    if not isinstance(positions,list):
        raise ValueError("E5A_OPEN_POSITIONS_REQUIRED")
    if snapshot["kind"]=="SYNTHETIC_FLAT_DEMO" and positions:
        raise ValueError("E5A_FALSE_SYNTHETIC_FLAT_ACCOUNT")
    seen=set()
    risk=notional=0.0
    for p in positions:
        if set(p)!={"asset","reservedStopRiskUSDT","grossNotionalUSDT"}:
            raise ValueError("E5A_BAD_POSITION_FIELDS")
        if p["asset"] not in e2.ASSETS or p["asset"] in seen:
            raise ValueError("E5A_DUPLICATE_OR_UNKNOWN_ASSET_POS")
        seen.add(p["asset"])
        a=float(p["reservedStopRiskUSDT"]);b=float(p["grossNotionalUSDT"])
        if not all(isfinite(x) and x>=0 for x in (a,b)):
            raise ValueError("E5A_BAD_OPEN_POSITION_RISK")
        risk+=a;notional+=b
    return equity,risk,notional,seen,snapshot["kind"]

def hypothetical_cost_card(pkt:dict, positions:dict|None=None):
    entry,dist=validate_packet(pkt)
    # At full 1R/2R/3R targets (gross arithmetic 2R), not a probabilistic
    # expected profit or actual expected trade outcome.
    reserve=(FUNDING_RESERVE_BPS_PER_8H*
             (MAX_HOLD_HOURS//8))/10000
    projected={
        str(b):round(FULL_TP3_GROSS_R-(2*b/10000+reserve)/dist,5)
        for b in SCENARIOS_BPS
    }
    result={
        "asset":pkt["asset"],"direction":pkt["side"],
        "referenceEntryUTC":pkt["entryOpenUTC"],
        "sourceKind":pkt["sourceKind"],
        "historicalReferenceOnly":True,
        "realTradePermission":False,
        "autoOrderAllowed":False,
        "userNotificationAllowed":False,
        "candidatePromotionAllowed":False,
        "setupEntryPrice":round(pkt["entryPrice"],8),
        "approxStopDistancePctFromRoundedHistoricalOracle":round(dist*100,5),
        "exampleStopPriceEstimatedOnly":round(
            pkt["entryPrice"]*(1-dist if pkt["side"]=="bullish" else 1+dist),8),
        "netRIfAllThreeTakeProfitsHitNotExpectedR":projected,
        "costStressBpsPerSide":list(SCENARIOS_BPS),
        "fundingIsConservativeUnobservedFutureReserveBps":
            round(reserve*10000,4),
        "declaredRiskBudget":{
            "maxTradeFraction":MAX_RISK_PER_TRADE,
            "maxOpenStopFraction":MAX_TOTAL_OPEN_RISK,
            "maxGrossNotionalMultiple":MAX_NOTIONAL_MULTIPLE,
            "minimumTradeRiskFraction":MIN_ACCEPTED_RISK,
        },
        "openPositionStateWasRealAccount":False,
        "hypotheticalMaxPositionNotionalUSDT":None,
        "decision":"WAIT",
        "reasons":[],
    }
    if projected["25"]<MIN_AFTER_25BPS_FULL_TP3_NET_R:
        result["decision"]="PASS_COST_STRESS"
        result["reasons"].append("25BPS_PLUS_FUNDING_RESERVE_ERODES_FULL_TP3_BELOW_1R")
        return result
    if positions is None:
        result["reasons"].append("OPEN_POSITION_SNAPSHOT_NOT_AVAILABLE")
        return result
    equity,used_risk,used_notional,assets,kind=validate_positions(positions,as_of=entry)
    if pkt["asset"] in assets:
        result["decision"]="PASS_PORTFOLIO_RISK"
        result["reasons"].append("SAME_ASSET_POSITION_ALREADY_OPEN")
        return result
    available_risk=max(0.,MAX_TOTAL_OPEN_RISK*equity-used_risk)
    free_notional=max(0.,MAX_NOTIONAL_MULTIPLE*equity-used_notional)
    permitted=min(MAX_RISK_PER_TRADE*equity,available_risk,free_notional*dist)
    if permitted<MIN_ACCEPTED_RISK*equity:
        result["decision"]="PASS_PORTFOLIO_RISK"
        result["reasons"].append("SHARED_PORTFOLIO_BUDGET_EXHAUSTED")
        return result
    result["hypotheticalMaxPositionNotionalUSDT"]=round(permitted/dist,2)
    # All E5-A input is historical, including any synthetic paper account.
    # Even valid verified PAPER account state could not license live orders.
    result["decision"]="HISTORICAL_REVIEW_ONLY"
    result["reasons"].append("PAST_KNOWN_V92_TRADE_NOT_AN_ELIGIBLE_LIVE_SIGNAL")
    if kind=="SYNTHETIC_FLAT_DEMO":
        result["reasons"].append("POSITION_SNAPSHOT_IS_SYNTHETIC_NOT_REAL")
    return result

def get_main_context(now_epoch:int,*,network:bool):
    """Main's public OHLC indicators contextual ONLY: never a V9.2 signal."""
    result={"source":"public_main_market_data.json",
            "isVerifiedV92RetestEntry":False,
            "liveTradeSignalProduced":False,
            "status":"NOT_REQUESTED","observedSymbols":[]}
    if not network:return result
    url="https://raw.githubusercontent.com/exchangecurrency11/ATLAS-Quant-Engine/main/market_data.json"
    try:
        with urlopen(Request(url,headers={"User-Agent":"ATLAS-E5-ReadOnly-Context/1.0"}),timeout=15) as response:
            raw=response.read(400000+1)
        if len(raw)>400000:
            raise ValueError("E5A_MAIN_CONTEXT_TOO_LARGE")
        packet=json.loads(raw)
        if packet.get("ok") is not True or packet.get("provider")!="Coinalyze":
            raise ValueError("E5A_UNEXPECTED_MAIN_CONTEXT_DATA_SOURCE")
        checked=strict_utc(packet["checkedAtUTC"])
        if checked>now_epoch+60 or now_epoch-checked>7200:
            result.update(status="STALE_OR_FUTURE_CONTEXT_SNAPSHOT",
                          sourceSHA256=sha256(raw).hexdigest())
            return result
        observations={}
        for item in packet["results"]:
            symbol=item["symbol"].removesuffix("_PERP.A")
            tf=item["interval"]
            if symbol not in ("BTCUSDT","SOLUSDT") or tf not in ("1hour","4hour","daily"):
                raise ValueError("E5A_UNEXPECTED_CONTEXT_INSTRUMENT")
            if item["status"]!="READY":
                continue
            closed=strict_utc(item["closeTimeUTC"].replace(".000Z","Z"))
            if closed>checked+60:
                raise ValueError("E5A_FUTURE_CANDLE_CONTEXT")
            if not (0<float(item["candle"]["close"])<1e9):
                raise ValueError("E5A_BAD_CANDLE_CONTEXT_PRICE")
            observations.setdefault(symbol,set()).add(tf)
        missing=[s for s in ("BTCUSDT","SOLUSDT")
                 if observations.get(s)!={"1hour","4hour","daily"}]
        result.update(status="CONTEXT_COMPLETE_NOT_A_SIGNAL" if not missing
                      else "CONTEXT_INCOMPLETE_NOT_A_SIGNAL",
                      sourceSHA256=sha256(raw).hexdigest(),
                      checkedAtUTC=packet["checkedAtUTC"],
                      observedSymbols=sorted(observations),
                      missingFullTimeframesFor=missing)
    except Exception as err:
        result.update(status="CONTEXT_UNAVAILABLE_FAIL_CLOSED",
                      fetchErrorType=type(err).__name__)
    return result

def audit(*,fetch_context=False, now_utc:str|None=None):
    now= strict_utc(now_utc) if now_utc else int(datetime.now(timezone.utc).timestamp())
    sources,forward=froze_sources()
    history=historical_rows()
    # All examples are explicitly historical and tested with a synthetic
    # FLAT paper account at each original historical entry.
    sample=[]
    tallies=Counter()
    by_coin=Counter()
    for p in history:
        synthetic={
          "kind":"SYNTHETIC_FLAT_DEMO","asOfUTC":p["entryOpenUTC"],
          "realizedEquityUSDT":START_EQUITY,"openPositions":[]
        }
        card=hypothetical_cost_card(p,synthetic)
        tallies[card["decision"]]+=1
        by_coin[p["asset"]]+=1
        if len([x for x in sample if x["asset"]==p["asset"]])<2:
            sample.append(card)
    if dict(by_coin)!={"BTCUSDT":15,"ETHUSDT":16,"SOLUSDT":20}:
        raise ValueError("E5A_HISTORICAL_COUNTS_CHANGED")
    assert len(history)==51
    context=get_main_context(now,network=fetch_context)
    return {
        "status":STATUS,
        "historical51InputsAudited":len(history),
        "historicalAssetCounts":dict(by_coin),
        "historicalDecisionTallies":dict(tallies),
        "historicalExampleCards":sample,
        "frozenSourceSHA256":sources,
        "frozenProspectivePipeline":forward,
        "mainPublicContext":context,
        "actualNewForwardSignalCards":[],
        "actualNewForwardSignalCount":0,
        "newTradeOrders":0,"newUserAlerts":0,"newNotifications":0,
        "existingPaperTradesWritten":0,"existingAutomationsChanged":False,
        "mainBranchChanged":False,"candidatePromoted":False,
        "sourceContainsNoLiveBrokerPositions":True,
        "allHistoricalCardsUntradeable":True,
        "pastReturnsWereNotInputsToDecision":True,
        "proposedNextDependency":"Read-only live V9.2 watch+confirmed-retest proof and timely signed exposure snapshot, separately freeze and verify before current opportunity decisions",
        "limitation":[
            "51 historical entries previously studied: strictly engineering demonstrations, never true forward trade evidence",
            "No monthly prospective post-freeze snapshot yet; current hourly alerts are distinct from V9.2 candidate fills",
            "Public main market indicators or structure regions do not establish a V9.2 BOS+closed retest+next 1H entry",
            "No account-specific open positions observed; synthetic flat account only for explanatory hypothetical sizing",
            "Round historical riskPct to 5 decimals means estimated example stop is not original exact stop",
            "Full TP3 = gross 2R is a mechanical best-case IF all three targets hit, NOT expected R or win probability",
            "9/25/50bps friction and 3bps/8h reserve are assumed future stress knobs, not live observed spreads, fees, funding or execution",
            "E5-A does not emit actionable AL or SHORT signals, send notifications, alter schedules, or place orders"
        ]
    }

def markdown(d):
    lines=[
        "# ATLAS Core E5-A — Shadow Decision CONTRACT, no live order signals",
        "",
        "**Source-limited conclusion:** The read-only historical risk/cost evaluator works. "
        "The frozen prospective feeds have no verified eligible trade packet. "
        "No live entry decision is authorized.",
        "",
        f'Previously sealed historical rows read for demonstration: **{d["historical51InputsAudited"]}**.',
        "Counts by coin: "+", ".join(k+" "+str(v) for k,v in d["historicalAssetCounts"].items()),
        "Historical risk/cost-gate outcomes: "+
        ", ".join(k+" "+str(v) for k,v in d["historicalDecisionTallies"].items()),
        "",
        f'Prospective status: **{d["frozenProspectivePipeline"]["status"]}**.',
        f'Public main market context: **{d["mainPublicContext"]["status"]}** '
        "(context, NOT V9.2 entry proof).",
        "",
        "| Asset | Side | Historical UTC entry | 25bps full-TP3 hypothetical Net R | 50bps full-TP3 hypothetical Net R | Research status |",
        "|---|---|---|---:|---:|---|"
    ]
    for card in d["historicalExampleCards"]:
        lines.append(
            f'| {card["asset"]} | {card["direction"]} | {card["referenceEntryUTC"]} | '
            f'{card["netRIfAllThreeTakeProfitsHitNotExpectedR"]["25"]:+.3f} | '
            f'{card["netRIfAllThreeTakeProfitsHitNotExpectedR"]["50"]:+.3f} | '
            f'{card["decision"]} |')
    lines+=["","## Limits","",*("- "+v for v in d["limitation"]),
            "","No production modifications, no strategy promotion, no prospective freeze edits.",""]
    return "\n".join(lines)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--fetch-public-main-context",action="store_true")
    parser.add_argument("--out",default=str(OUT/"e5a_report.json"))
    args=parser.parse_args()
    target=Path(args.out)
    if not str(target).startswith(str(OUT)+"/"):
        raise ValueError("E5A_OUTPUT_MUST_STAY_IN_RESEARCH")
    report=audit(fetch_context=args.fetch_public_main_context)
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(report,sort_keys=True,ensure_ascii=False,indent=2)+"\n")
    target.with_suffix(".md").write_text(markdown(report))
    print("ATLAS_E5A_HISTORICAL_51_SOURCE_PINNED_SHADOW_GUARDS_PASS",flush=True)
    print("E5A_HISTORICAL_GATE_TALLIES",report["historicalDecisionTallies"],flush=True)
    print("E5A_NO_LIVE_ENTRY_PROOF",report["frozenProspectivePipeline"]["status"],flush=True)
    print("E5A_PUBLIC_CONTEXT_NOT_SIGNAL",report["mainPublicContext"]["status"],flush=True)

if __name__=="__main__":
    main()
