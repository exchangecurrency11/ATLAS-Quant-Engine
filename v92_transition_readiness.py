#!/usr/bin/env python3
"""V9.2 handover readiness gate (READ-ONLY, no trading or workflow toggles).

Consumes already-sealed V9.2 stable hourly source/replay audit and the live
three-asset paper ledger. A passing evaluation permits HUMAN REVIEW ONLY.
It never cancels V7, promotes V9.2, sends alerts, changes risk, or places orders.
"""
import argparse
import json
import math
from pathlib import Path

MIN_CONSECUTIVE_HOURS = 168  # 7 full days across BTC/SOL and ETH
MIN_FORWARD_CLOSED_TRADES = 50
MAX_PER_TRADE_RISK_USDT = 10.0
MAX_COMBINED_RISK_USDT = 20.0
REQUIRED_ASSETS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]

def evaluate(audit, paper):
    if not isinstance(audit, dict) or not isinstance(paper, dict):
        raise ValueError("HANDOVER_SOURCE_MUST_BE_JSON_OBJECT")
    if (audit.get("mode") != "V92_STABLE_SHADOW_HARDENING_ONLY"
        or paper.get("mode") != "V92_BTC_ETH_SOL_SINGLE_THIRD_1000USDT_PROSPECTIVE_PAPER_ACCOUNT"):
        raise ValueError("HANDOVER_UNRECOGNISED_RESEARCH_SOURCE")
    if paper.get("assets") != REQUIRED_ASSETS:
        raise ValueError("HANDOVER_WRONG_ASSETS_OR_ORDER")
    if (paper.get("virtualInitialUSDT") != 1000
        or paper.get("noBrokerOrders") is not True
        or paper.get("noUserNotifications") is not True
        or audit.get("newBrokerOrders") is not False
        or audit.get("noRetroactiveTradesOrRewrittenCandles") is not True):
        raise ValueError("HANDOVER_SOURCE_SAFETY_CONTRACT_FAILED")
    closed=paper.get("closedEligiblePaperTrades")
    if type(closed) is not int or closed < 0:
        raise ValueError("HANDOVER_CLOSED_COUNT_INVALID")
    ledger=paper.get("forwardOnlyPrecommittedPaperLedger")
    if not isinstance(ledger,list) or len(ledger)!=closed:
        raise ValueError("HANDOVER_LEDGER_COUNT_PARITY_FAILED")
    if not (type(paper.get("wins")) is int and type(paper.get("losses")) is int
            and paper["wins"]+paper["losses"]==closed):
        raise ValueError("HANDOVER_PAPER_WINS_LOSSES_INVALID")
    score=paper.get("netRealizedPaperR9BpsSide")
    stressed=paper.get("virtualPaperPnLStress25BpsUSDT")
    if not all(type(x) in (int,float) and math.isfinite(x) for x in (score,stressed)):
        raise ValueError("HANDOVER_PNL_INVALID")
    cover=audit.get("coverage",{})
    checks={}
    checks["sourceParityNoErrors"]=(
        audit.get("parityErrors")==[]
        and type(audit.get("matchedVerifiedHours")) is int
        and audit["matchedVerifiedHours"]>=1
        and audit.get("matchedAssetChecks")==3*audit["matchedVerifiedHours"])
    checks["sameLatestSealedHour"]=(
        isinstance(audit.get("latestCommonHourUTC"),str)
        and paper.get("lastCapturedBTCandSOLHourUTC")==audit["latestCommonHourUTC"]
        and paper.get("lastCapturedETHHourUTC")==audit["latestCommonHourUTC"])
    checks["sevenDayContinuousRecentCoverage"]=all(
        isinstance(cover.get(k),dict)
        and type(cover[k].get("consecutiveRecentHours")) is int
        and cover[k]["consecutiveRecentHours"]>=MIN_CONSECUTIVE_HOURS
        for k in ("BTC_SOL","ETH"))
    checks["forwardTradeSampleAtLeast50"]=closed>=MIN_FORWARD_CLOSED_TRADES
    checks["livePaperEntryStopTPParityVerified"]=(
        audit.get("tradeEntryStopTPParityOnLiveTradeProven") is True
        and audit.get("actualObservedExitEvents",0)>0)
    checks["riskPolicyUnitTestsDefined"]=(
        audit.get("policy",{}).get("maxRiskUSDTPerPosition")==MAX_PER_TRADE_RISK_USDT
        and audit.get("policy",{}).get("maxCombinedOpenRiskUSDT")==MAX_COMBINED_RISK_USDT)
    checks["riskCapAppliedToActualForwardPaperBook"]=(
        paper.get("simultaneousAssetsDoNotHaveTotalRiskCap") is False
        and type(paper.get("fixedVirtualStopRiskUSDTPerTrade")) in (int,float)
        and 0<paper["fixedVirtualStopRiskUSDTPerTrade"]<=MAX_PER_TRADE_RISK_USDT
        and paper.get("verifiedCombinedOpenRiskCapUSDT") is not None
        and type(paper.get("verifiedCombinedOpenRiskCapUSDT")) in (int,float)
        and 0<paper["verifiedCombinedOpenRiskCapUSDT"]<=MAX_COMBINED_RISK_USDT)
    checks["positiveRiskAndCostStressedPaperResults"]=(
        closed>=MIN_FORWARD_CLOSED_TRADES and score>0 and stressed>0)
    checks["existingV7V91EvidenceRequiredUnchanged"]=(
        audit.get("newCappedBookPolicyNotAppliedToLegacyV92") is True
        and audit.get("legacyV92RiskUSDTUnchanged")==100
        and paper.get("originalV7V91AndOtherV92BooksUnchanged") is True)
    checks["noHistoricalBackfillsOrUnverifiedFills"]=(
        paper.get("noHistorical836USDBackfilledIntoThisAccount") is True
        and paper.get("missingHistoryAndNoGitSealedRetestExcluded") is True
        and audit.get("missingHourNotBackfilled") is True)
    ready=all(checks.values())
    return {
        "status": "ELIGIBLE_FOR_MANUAL_HANDOVER_REVIEW" if ready else "CONTINUE_V7_V92_PARALLEL_PAPER",
        "approvedToChangeProduction":False,
        "autoPromotion":False,
        "autoDisableV7":False,
        "disableV7Data":False,
        "disableV7Notifications":False,
        "noBrokerOrders":True,
        "productionAndExistingPaperUnchanged":True,
        "migrationPhase":"PARALLEL_OBSERVATION" if not ready else "MANUAL_REVIEW_ONLY",
        "lastSealedCommonHourUTC":audit.get("latestCommonHourUTC"),
        "closedForwardTrades":closed,
        "netForwardR9BpsSide":score,
        "forwardStressPnL25BpsUSDT":stressed,
        "riskPolicyTarget":{"riskUSDTPerTrade":MAX_PER_TRADE_RISK_USDT,
                            "combinedRiskUSDT":MAX_COMBINED_RISK_USDT},
        "tests":checks,
        "blockingChecks":[name for name,ok in checks.items() if not ok],
        "rollback":"Keep V7 hourly source and independent reference running; revert any future V9.2 notification owner switch to last verified V7 path; never rewrite sealed paper evidence.",
        "nextAction":"Continue sealed, simultaneous V7+V9.1+V9.2 paper evidence; manual review only after all gates pass.",
        "notes":["Passing is not trading approval nor a guarantee of future profitability.",
                 "Historical initial gaps remain explicitly reported; require 7 days of recent continuous forward coverage.",
                 "Do not infer TP/SL execution parity until an observed prospective position and close exist.",
                 "The 10/20 USDT shadow risk policy is NOT applied to the current original 100 USDT per trade account."]
    }

def render_markdown(r):
    lines=["# V9.2 controlled handover readiness",
           "",
           f"**Decision: {r['status']}**",
           "",
           "V7 continues unchanged; no automated notifications, orders or strategy cutover.",
           f"Latest common sealed UTC hour: {r['lastSealedCommonHourUTC'] or 'not available'}.",
           f"Forward closed paper trades: {r['closedForwardTrades']}.",
           f"Forward net R (9 bps each side): {r['netForwardR9BpsSide']}.",
           f"Forward stress paper PnL USDT (25 bps each side): {r['forwardStressPnL25BpsUSDT']}.",
           "",
           "| Mandatory gate | Result |","|---|---|"]
    for key,ok in r["tests"].items():
        lines.append(f"| {key} | {'PASS' if ok else 'BLOCKED'} |")
    lines.extend(["","**No automatic handover or V7 deactivation.**",
                  "",
                  "Rollback design: "+r["rollback"],
                  "",
                  "The original 100 USDT-risk paper ledger remains unchanged and cannot be represented as the 10/20 USDT capped book.",
                  "A future cutover would require a separately tested notification-only switch, independent data collection, 1H/4H/Daily report parity and explicit human approval."])
    return "\n".join(lines)+"\n"

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--audit",required=True)
    p.add_argument("--paper",required=True)
    p.add_argument("--out",default="forward/v92_transition_readiness/latest.json")
    p.add_argument("--md",default="forward/v92_transition_readiness/latest.md")
    a=p.parse_args()
    result=evaluate(json.loads(Path(a.audit).read_text()),
                    json.loads(Path(a.paper).read_text()))
    out=Path(a.out); out.parent.mkdir(parents=True,exist_ok=True)
    md=Path(a.md);md.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,indent=2)+"\n")
    md.write_text(render_markdown(result))
    print(result["status"],"blocking=",result["blockingChecks"],flush=True)

if __name__=="__main__":
    main()
