#!/usr/bin/env python3
"""V9.2 STABLE *shadow* hardening: source coverage, exact replay parity, risk gate.

Does NOT alter the existing V9.2 immutable 100-USDT-risk ledger or V7/V9.1.
Risk policy here applies to a NEW prospective capped paper admission gate.
No historical paper fill can be invented from these read-only observations.
"""
import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path

HOUR = 3600
BTC_SOL_FIRST = "2026-11-12T11:00:00Z"
ETH_FIRST = "2026-11-12T12:00:00Z"
ASSETS = ("BTCUSDT", "ETHUSDT", "SOLUSDT")
EVENT_FIELDS = ("newWatchAtThisClose","paperTradeExitsObservedAtThisClose",
                "currentPaperState","diagnosticTotalRollingWindowAlerts",
                "diagnosticTotalRollingWindowClosedTrades")
POLICY = {
    "paperInitialUSDT":1000.0,
    "maxRiskUSDTPerPosition":10.0,
    "maxCombinedOpenRiskUSDT":20.0,
    "stressCostBpsPerSide":25.0,
    "maxLeverageForNotionalCeiling":10.0,
    "requireMostRecentConsecutiveHours":4,
    "noRealOrders":True,
}
def seconds(s):
    if not isinstance(s,str) or not s.endswith("Z"):
        raise ValueError("STABLE_INVALID_UTC")
    dt=datetime.strptime(s,"%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    t=int(dt.timestamp())
    if t%HOUR:
        raise ValueError("STABLE_HOUR_MISALIGNED")
    return t

def stamp(t):
    return datetime.fromtimestamp(t,timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def hour_file(t):
    return datetime.fromtimestamp(t,timezone.utc).strftime("%Y-%m-%dT%H-00Z.json")

def finite_positive(x):
    return type(x) in (int,float) and math.isfinite(x) and x>0

def exact_events(a,b,where):
    if not isinstance(a,dict) or not isinstance(b,dict):
        raise ValueError("STABLE_MISSING_PARITY_OBJECT_"+where)
    for k in EVENT_FIELDS:
        if k not in a or k not in b or a[k]!=b[k]:
            raise ValueError("STABLE_BACKTEST_PAPER_REPLAY_MISMATCH_"+where+"_"+k)
    return True

def valid_position(position,symbol):
    if not isinstance(position,dict):
        raise ValueError("STABLE_POSITION_NOT_DICT_"+symbol)
    for k in ("entry","stop","risk","side","targets","entryOpenUTC",
              "watchKnownUTC","retestKnownUTC"):
        if k not in position:
            raise ValueError("STABLE_POSITION_REQUIRED_FIELD_"+symbol+"_"+k)
    entry,stop,risk = (position[k] for k in ("entry","stop","risk"))
    if not all(finite_positive(x) for x in (entry,stop,risk)):
        raise ValueError("STABLE_POSITION_UNCERTAIN_STOP_"+symbol)
    side=position["side"]
    if side not in ("bullish","bearish"):
        raise ValueError("STABLE_POSITION_BAD_SIDE_"+symbol)
    if ((side=="bullish" and stop>=entry)
        or (side=="bearish" and stop<=entry)
        or not math.isclose(abs(entry-stop),risk,rel_tol=1e-8,abs_tol=1e-7)
        or not .001<=risk/entry<=.04):
        raise ValueError("STABLE_POSITION_BAD_RISK_OR_STOP_"+symbol)
    expected=[entry+(1 if side=="bullish" else -1)*risk*x for x in (1,2,3)]
    targets=position["targets"]
    if (not isinstance(targets,list) or len(targets)!=3
        or any(not finite_positive(x) or not math.isclose(x,y,rel_tol=1e-8,abs_tol=1e-7)
               for x,y in zip(targets,expected))):
        raise ValueError("STABLE_POSITION_BACKTEST_TP_MISMATCH_"+symbol)
    if not (position["watchKnownUTC"]<position["retestKnownUTC"]
            <=position["entryOpenUTC"]):
        raise ValueError("STABLE_POSITION_FUTURE_CAUSALITY_"+symbol)
    return True

def risk_gate(symbol,side,entry,stop,already_reserved=0.0,
              already_notional=0.0,*,verified=False,precommitted=False,
              hour_synchronized=False,policy=POLICY):
    """New shadow admission sizing, NOT legacy 100 USDT accounting.

    Stop risk + worst-case round-trip assumed trading costs must fit both caps.
    Stop/slippage can still gap in real markets: NOT a loss guarantee.
    """
    def blocked(reason):
        return {"allowed":False,"reason":reason,"symbol":symbol,
                "notExecutableOrder":True}
    if symbol not in ASSETS or side not in ("bullish","bearish"):
        return blocked("INVALID_ASSET_OR_SIDE")
    if not (verified and precommitted and hour_synchronized):
        return blocked("UNVERIFIED_OR_NOT_PRECOMMITTED_OR_UNSYNCED")
    if not all(finite_positive(x) for x in (entry,stop)):
        return blocked("ENTRY_OR_STOP_UNAVAILABLE")
    if (side=="bullish" and stop>=entry) or (side=="bearish" and stop<=entry):
        return blocked("STOP_WRONG_SIDE")
    fraction=abs(entry-stop)/entry
    if not .001<=fraction<=.04:
        return blocked("STOP_WIDTH_OUTSIDE_REPLAY_RULE")
    if not (type(already_reserved) in (int,float) and
            type(already_notional) in (int,float) and
            math.isfinite(already_reserved) and math.isfinite(already_notional)
            and already_reserved>=0 and already_notional>=0):
        return blocked("UNKNOWN_PRIOR_PORTFOLIO_EXPOSURE")
    cap=policy["maxCombinedOpenRiskUSDT"]
    per=policy["maxRiskUSDTPerPosition"]
    initial=policy["paperInitialUSDT"]
    if not (0<per<=cap<=initial and
            policy["stressCostBpsPerSide"]>=0 and
            policy["maxLeverageForNotionalCeiling"]>=1):
        return blocked("INVALID_RISK_POLICY")
    if already_reserved+per>cap+1e-9:
        return blocked("COMBINED_RISK_CAP_EXCEEDED")
    per_unit=abs(entry-stop)+2*policy["stressCostBpsPerSide"]/10000*entry
    qty=per/per_unit
    notional=qty*entry
    ceiling=initial*policy["maxLeverageForNotionalCeiling"]
    if already_notional+notional>ceiling+1e-8:
        return blocked("NOTIONAL_LEVERAGE_CEILING_EXCEEDED")
    return {
        "allowed":True,"reason":"CAPPED_SHADOW_ADMISSION_ELIGIBLE",
        "symbol":symbol,"side":side,
        "entryAssumed":entry,"stop":stop,
        "quantityHypothetical":round(qty,10),
        "notionalUSDT":round(notional,6),
        "reservedStopAndCostUSDT":per,
        "combinedRiskAfterUSDT":round(already_reserved+per,6),
        "maxCombinedRiskUSDT":cap,
        "stressCostBpsPerSide":policy["stressCostBpsPerSide"],
        "notExecutableOrder":True,
    }

def read_hourly(folder,first,expected_mode,kind):
    base=Path(folder)
    if not base.is_dir():
        raise ValueError("STABLE_MISSING_SOURCE_DIRECTORY_"+kind)
    docs={}
    for path in sorted(base.glob("*.json")):
        x=json.loads(path.read_text(encoding="utf-8"))
        t=seconds(x.get("targetClosed1HUTC"))
        if (t<seconds(first) or path.name!=hour_file(t) or t in docs
            or x.get("mode")!=expected_mode
            or x.get("noBrokerOrders") is not True
            or x.get("noUserNotifications") is not True):
            raise ValueError("STABLE_UNVERIFIED_STORED_HOUR_"+kind+"_"+path.name)
        if kind=="CORE":
            valid=x.get("sourceVerifiedSameHour") is True and x.get("sourceV7AndV91RecomputedExactMatch") is True
        elif kind=="ETH":
            valid=x.get("verifiedSourceAndExactV7AndV91Replay") is True
        else:
            valid=False
        captured=x.get("capturedAtUTC")
        if not valid or not isinstance(captured,str):
            raise ValueError("STABLE_UNVERIFIED_PARITY_"+kind)
        captured_ts=int(datetime.strptime(captured,"%Y-%m-%dT%H:%M:%SZ")
                        .replace(tzinfo=timezone.utc).timestamp())
        if not t<=captured_ts<t+HOUR:
            raise ValueError("STABLE_RETROACTIVE_OR_FUTURE_CAPTURE_"+kind)
        docs[t]=x
    return docs

def read_reference_hour(root,t,relative):
    p=Path(root)/relative/hour_file(t)
    if not p.is_file():
        raise ValueError("STABLE_MISSING_PRIOR_SOURCE_"+str(p))
    x=json.loads(p.read_text(encoding="utf-8"))
    if seconds(x.get("targetClosed1HUTC"))!=t:
        raise ValueError("STABLE_MISMATCH_PRIOR_HOUR_"+str(p))
    return x

def parity_one_hour(t,core,eth,v91,v7):
    token=stamp(t)
    rows=[]
    for sym in ("BTCUSDT","SOLUSDT"):
        live=core["assets"][sym]
        old=read_reference_hour(v91,t,"forward/v91_prospective_retest/hourly")
        original=read_reference_hour(v7,t,"forward/snapshots")
        if (old.get("sourceVerifiedSameHour") is not True or
            old.get("V7SnapshotAndIndependentRecomputeExactMatch") is not True or
            original.get("status")!="VERIFIED_PAPER_OBSERVATION"):
            raise ValueError("STABLE_UNVERIFIED_ORIGINAL_BTC_SOL")
        exact_events(live["originalV91"],old["assets"][sym]["max4hRetest"],sym+"_V91")
        exact_events(live["originalV7"],original["results"][sym+"_PERP.A"]["V7_signal_filter"],sym+"_V7")
        # BTC has no V9.2 candle veto. Must equal unchanged baseline fields.
        if sym=="BTCUSDT":
            exact_events(live["selectedV92"],live["originalV91"],"BTC_SELECTED_EQUALS_V91")
        else:
            e=live["currentCloseRetestEvaluation"]
            if e.get("directCurrentFilterVeto"):
                if (not e.get("baselineRetestPresent")
                    or e.get("selectedRetestPresent")
                    or not e.get("currentPatternWarnings")):
                    raise ValueError("STABLE_SOL_INVALID_DIRECT_VETO")
            if (e.get("selectedRetestPresent") and
                not e.get("baselineRetestPresent") and
                not e.get("downstreamStateDivergence")):
                raise ValueError("STABLE_SOL_UNEXPLAINED_NEW_RETEST")
        parity=core["originalV7_1H4HDailyCandleParity"][sym]
        for tf in ("1hour","4hour","daily"):
            p=parity[tf]
            if p.get("allOHLCVFieldsWithinIntegrityTolerances") is not True:
                raise ValueError("STABLE_BTC_SOL_SOURCE_NOT_OHLCV_VERIFIED")
        rows.append({"symbol":sym,"timeUTC":token,"storedBacktestParity":True,
                     "selectedPolicy":"BTC_V91_EQUAL" if sym=="BTCUSDT" else "SOL_V92_STRICT_VETO"})
    prior_e=read_reference_hour(v91,t,"forward/v91_eth_prospective_retest/hourly")
    first_e=read_reference_hour(v7,t,"forward/eth/snapshots")
    if (prior_e.get("verifiedSourceAndExactV7Replay") is not True
        or first_e.get("status")!="VERIFIED_PAPER_OBSERVATION"):
        raise ValueError("STABLE_UNVERIFIED_ORIGINAL_ETH")
    exact_events(eth["originalV91"],prior_e["max4hRetest"],"ETH_V91")
    exact_events(eth["originalV7"],first_e["results"]["ETHUSDT_PERP.A"]["V7_signal_filter"],"ETH_V7")
    exact_events(eth["selectedV92"],eth["originalV91"],"ETH_SELECTED_EQUALS_V91")
    for tf in ("1hour","4hour","daily"):
        p=eth["sourceIntegrity"][tf]
        if p.get("verified") is not True:
            raise ValueError("STABLE_ETH_SOURCE_NOT_OHLCV_VERIFIED")
        for sym in ("BTCUSDT","SOLUSDT"):
            target_tf=core["originalV7_1H4HDailyCandleParity"][sym][tf]["closedCandleUTC"]
            if target_tf!=p["closeUTC"]:
                raise ValueError("STABLE_THREE_ASSET_TIMEFRAME_ALIGNMENT_"+tf)
    for sym in ("BTCUSDT","SOLUSDT"):
        for tf in ("1H","4H"):
            z=core["assets"][sym]["recentPatternObservations"][tf]["lastClosedCandleUTC"]
            if z != eth["ethReversalPatternRecognition1H4H"][tf]["lastCompletedCandleCloseUTC"]:
                raise ValueError("STABLE_CLOSED_REPLAY_TIMEFRAME_MISMATCH_"+tf)
    rows.append({"symbol":"ETHUSDT","timeUTC":token,"storedBacktestParity":True,
                 "selectedPolicy":"ETH_V91_EQUAL"})
    return rows

def coverage(docs,first,last):
    start=seconds(first)
    if last is None:
        return {"expected":0,"saved":len(docs),"missingHoursUTC":[],
                "latestUTC":None,"consecutiveRecentHours":0}
    keys=set(docs)
    missing=[stamp(t) for t in range(start,last+HOUR,HOUR) if t not in keys]
    streak=0
    t=last
    while t in keys and t>=start:
        streak+=1
        t-=HOUR
    return {"expected":(last-start)//HOUR+1,"saved":len(docs),
            "missingHoursUTC":missing,"latestUTC":stamp(max(keys)) if keys else None,
            "consecutiveRecentHours":streak}

def audit(core_docs,eth_docs,v91_root,v7_root,policy=POLICY):
    latests=[max(d) for d in (core_docs,eth_docs) if d]
    last=max(latests) if latests else None
    c=coverage(core_docs,BTC_SOL_FIRST,last)
    e=coverage(eth_docs,ETH_FIRST,last)
    common=sorted(set(core_docs)&set(eth_docs))
    matched=[]
    errors=[]
    for t in common:
        try:
            matched.extend(parity_one_hour(t,core_docs[t],eth_docs[t],v91_root,v7_root))
        except (ValueError,KeyError,TypeError,IndexError) as ex:
            errors.append({"hourUTC":stamp(t),"reason":str(ex)})
    common_latest=bool(last is not None and
                       last in core_docs and last in eth_docs)
    recent_ok=(common_latest and
               c["consecutiveRecentHours"]>=policy["requireMostRecentConsecutiveHours"] and
               e["consecutiveRecentHours"]>=policy["requireMostRecentConsecutiveHours"])
    latest_parity_ok=(not errors and common_latest and
                      any(x["timeUTC"]==stamp(last) for x in matched))
    # Existing 100 USDT V9.2 ledger NEVER gets downsized or rewritten here.
    # Shadow only admits NEW, previously-precommitted next-open entries.
    current_state={}
    current_new_entry_decisions=[]
    for symbol in ASSETS:
        if last is None or not common_latest:
            state={"status":"MISSING_MATCHED_THREE_ASSET_HOUR"}
        else:
            z=(eth_docs[last]["selectedV92"] if symbol=="ETHUSDT"
               else core_docs[last]["assets"][symbol]["selectedV92"])
            state=z["currentPaperState"]
            pos=state.get("openHypotheticalPosition")
            pending=state.get("pendingNextOpenPaperEntry")
            if pos is not None:
                try:
                    valid_position(pos,symbol)
                    detail="LEGACY_OPEN_POSITION_NOT_RETROACTIVELY_ADMITTED"
                except (ValueError,TypeError) as ex:
                    errors.append({"hourUTC":stamp(last),
                                   "reason":str(ex)})
                    detail="INVALID_LEGACY_OPEN_POSITION"
                current_new_entry_decisions.append({"symbol":symbol,
                        "status":detail,"allowed":False,"legacyUnchanged":True})
            elif pending is not None:
                current_new_entry_decisions.append({"symbol":symbol,
                    "status":"WAIT_FOR_NEXT_REAL_CLOSED_CANDLE_ENTRY_PRICE_AND_PRECOMMIT",
                    "allowed":False,"legacyUnchanged":True})
            else:
                current_new_entry_decisions.append({"symbol":symbol,
                    "status":"NO_NEW_ENTRY_CANDIDATE","allowed":False,
                    "legacyUnchanged":True})
    strict_safe=(recent_ok and latest_parity_ok and not errors)
    return {
        "status":"V92_STABLE_SHADOW_AUDIT_"+("READY_FOR_NEW_ADMISSION_REVIEW" if strict_safe else "FAIL_CLOSED"),
        "mode":"V92_STABLE_SHADOW_HARDENING_ONLY",
        "sharedVirtualInitialUSDT":1000,
        "policy":policy,
        "newCappedBookPolicyNotAppliedToLegacyV92":True,
        "legacyV92RiskUSDTUnchanged":100,
        "legacyV92OrdersSent":False,
        "newBrokerOrders":False,"newUserNotifications":False,
        "noRetroactiveTradesOrRewrittenCandles":True,
        "coverage":{"BTC_SOL":c,"ETH":e},
        "latestCommonHourUTC":stamp(last) if common_latest else None,
        "matchedVerifiedHours":len(matched)//3,
        "matchedAssetChecks":len(matched),
        "exactStoredReplayParities":{"BTC":"V91+V7 and V92 selected equals V91",
                                     "SOL":"V91+V7; V92 filter veto audited",
                                     "ETH":"V91+V7 and V92 selected equals V91"},
        "crossAssetLastClosed1H4HDailyAlignmentChecked":True,
        "missingHourNotBackfilled":True,
        "parityErrors":errors,
        "newEntryAdmissionReadiness":bool(strict_safe),
        "latestShadowEntryDecisions":current_new_entry_decisions,
        "limitsCannotGuaranteeExecutionOrStopFill":True,
        "fundingVariableSlippageAndLiquidationNotFullyModeled":True,
    }

def markdown(x):
    out=["# V9.2 Stable — three-part hardening audit","",
         "**Research shadow: no modifications to original paper records or strategy, no real orders.**","",
         "## Risk policy for *new* capped shadow book","",
         "- Per-position budget: **10 USDT** inclusive of hypothetical stress fees/slippage.",
         "- Combined concurrent budget: **20 USDT**; over-cap and missing data fail closed.",
         "- Original V9.2 **100 USDT** per trade remains unchanged; not retroactively rewritten.","",
         "## Source completeness","",
         "| Source | Saved / expected | Missing UTC hours | Consecutive recent hours |",
         "|---|---:|---|---:|"]
    for key,z in x["coverage"].items():
        out.append(f"| {key} | {z['saved']}/{z['expected']} | "
                   f"{', '.join(z['missingHoursUTC']) or 'None'} | {z['consecutiveRecentHours']} |")
    out += ["",
            "## Backtest / forward snapshot parity",
            "",
            f"- Matched 1H source hours: **{x['matchedVerifiedHours']}**.",
            f"- Coin-hour replay checks: **{x['matchedAssetChecks']}**.",
            "- Comparison is based on independently stored forward 1H snapshots and their prior V7/V9.1 reference records, not a claim of executable live fills.",
            "- Original V9.2 already replays the same closed OHLCV as of each hour; audit double-checks serialized strategy state, BOS/retest, stop/TP fields when open, and timeframe stamps.",
            f"- Latest strict paper admission gate: **{'READY FOR REVIEW' if x['newEntryAdmissionReadiness'] else 'FAIL CLOSED'}**."]
    if x["parityErrors"]:
        out += ["","**Errors:**"]+[f"- {e['hourUTC']}: {e['reason']}" for e in x["parityErrors"]]
    out += ["","## New-entry review",""]
    for d in x["latestShadowEntryDecisions"]:
        out.append(f"- {d['symbol']}: {d['status']}.")
    out+=["","**Limits:** Data gaps are not backfilled; risk limits cannot prevent stop gaps, funding/variable spreads/slippage are not fully modeled; no strategy promotion."] 
    return "\n".join(out)+"\n"

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--v92-btcsol",required=True)
    p.add_argument("--v92-eth",required=True)
    p.add_argument("--v91-root",required=True)
    p.add_argument("--v7-root",required=True)
    p.add_argument("--out",default="forward/v92_stable_hardening/latest.json")
    p.add_argument("--md",default="forward/v92_stable_hardening/latest.md")
    a=p.parse_args()
    core=read_hourly(a.v92_btcsol,BTC_SOL_FIRST,
                    "V92_SELECTED_CANDLE_IMMUTABLE_HOURLY_FORWARD_PAPER_ONLY","CORE")
    eth=read_hourly(a.v92_eth,ETH_FIRST,
                   "V92_ETH_VERIFIED_HOURLY_CANDLES_OBSERVATIONAL_PAPER","ETH")
    result=audit(core,eth,a.v91_root,a.v7_root)
    dest=Path(a.out);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    Path(a.md).write_text(markdown(result),encoding="utf-8")
    print(result["status"],"matchedHours",result["matchedVerifiedHours"],
          "parityErrors",len(result["parityErrors"]),
          "coverage",json.dumps(result["coverage"]),flush=True)

if __name__=="__main__":
    main()
