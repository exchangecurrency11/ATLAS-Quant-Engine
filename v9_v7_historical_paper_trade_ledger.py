#!/usr/bin/env python3
"""Auditable, candle-by-candle V7 vs V9 historical PAPER trade ledger.

Consumes the ORIGINAL full chronological V7/V9 strategy replays returned
by v9_v7_full_profit_backtest.run(). No orders, no future data at entry,
no new trade signals, no aggressive leverage profit claims.

Keeps 100 USDT / 10x isolated / 0.5% equity risk assumptions separate
from evidence of actual fills. Margin constraints are applied to paper
account rather than pretending all overlapping trades are executable.
Funding, maintenance margin, liquidation, gaps and actual fill are NOT
modeled. Never mix filtered historical results with prospective profits.
"""
from datetime import datetime,timezone,timedelta
from hashlib import sha256
import csv,json,math
from pathlib import Path

INITIAL_EQUITY_USDT=100.
RISK_FRACTION=0.005
LEVERAGE=10.
MAX_SIMULTANEOUS_RISK_FRACTION=.01
COST_BPS_PER_SIDE=9.
STRESS_BPS_PER_SIDE=25.
TSI=timezone(timedelta(hours=3))


def at_utc(t):
    return datetime.fromtimestamp(int(t),timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def at_tsi(t):
    return datetime.fromtimestamp(int(t),TSI).strftime("%Y-%m-%d %H:%M TSİ")

def validate_trade(t,symbol,variant,hour_by_open):
    required=("watchKnownUTC","retestKnownUTC","entryOpenUTC",
              "exitKnownUTC","entry","stop","targets","risk",
              "side","realizedR","netRIllustrative","exitReason",
              "targetCount")
    if any(k not in t for k in required):
        raise ValueError("V7_TRADE_UNEXPECTED_MISSING_FIELD")
    for k in ("watchKnownUTC","retestKnownUTC","entryOpenUTC","exitKnownUTC"):
        if type(t[k]) is not int or t[k]%3600:
            raise ValueError("PAPER_TRADE_TIME_NOT_EXACT_CLOSED_1H")
    if not (t["watchKnownUTC"]<t["retestKnownUTC"]<=t["entryOpenUTC"]<
            t["exitKnownUTC"]):
        raise ValueError("PAPER_TRADE_CAUSAL_ORDER_INVALID")
    if t["side"] not in ("bullish","bearish") or t["targetCount"] not in (0,1,2,3):
        raise ValueError("PAPER_TRADE_INVALID_DIRECTION_OR_TPS")
    if t["entryOpenUTC"] not in hour_by_open or t["exitKnownUTC"]-3600 not in hour_by_open:
        raise ValueError("PAPER_TRADE_ENTRY_OR_EXIT_CANDLE_MISSING")
    e=hour_by_open[t["entryOpenUTC"]]
    exit_bar=hour_by_open[t["exitKnownUTC"]-3600]
    entry=float(t["entry"])
    stop=float(t["stop"])
    risk=float(t["risk"])
    if (not all(math.isfinite(float(t[k])) for k in
             ("entry","stop","risk","realizedR","netRIllustrative")) or
        not (entry>0 and stop>0 and risk>0) or
        abs(entry-e["o"])>max(1e-7,entry*1e-8)):
        raise ValueError("PAPER_TRADE_ENTRY_OR_RISK_NOT_FROM_CLOSED_CANDLES")
    if abs(abs(entry-stop)-risk)>max(1e-7,risk*1e-7):
        raise ValueError("PAPER_TRADE_STOP_RISK_INCONSISTENT")
    long=t["side"]=="bullish"
    if (long and stop>=entry) or (not long and stop<=entry):
        raise ValueError("PAPER_TRADE_STOP_WRONG_SIDE")
    sign=1 if long else -1
    expected_targets=[entry+sign*risk*n for n in (1,2,3)]
    if len(t["targets"])!=3 or any(
       abs(float(actual)-exp)>max(1e-7,abs(exp)*1e-8)
       for actual,exp in zip(t["targets"],expected_targets)):
        raise ValueError("PAPER_TRADE_TP_VALUES_NOT_1R_2R_3R")
    base_cost=2*COST_BPS_PER_SIDE/10000*entry/risk
    if abs((float(t["realizedR"])-base_cost)-float(t["netRIllustrative"]))>1e-7:
        raise ValueError("PAPER_TRADE_NETR_NOT_EQUAL_GROSS_MINUS_COSTS")
    if t["exitReason"]=="STOP_FIRST_OR_AFTER_TP":
        touched=exit_bar["l"]<=stop if long else exit_bar["h"]>=stop
        if not touched:raise ValueError("PAPER_TRADE_EXIT_STOP_NOT_TOUCHED_IN_EXIT_HOUR")
    elif t["exitReason"]=="TP3_COMPLETE":
        tp3=float(t["targets"][-1])
        touched=exit_bar["h"]>=tp3 if long else exit_bar["l"]<=tp3
        if not touched:raise ValueError("PAPER_TRADE_EXIT_TP3_NOT_TOUCHED_IN_EXIT_HOUR")
    elif t["exitReason"]=="TIME_EXIT_AT_CLOSE":
        pass
    else:
        raise ValueError("PAPER_TRADE_EXIT_REASON_UNKNOWN")
    h=sha256(f"{symbol}|{variant}|{t['entryOpenUTC']}|{t['exitKnownUTC']}".encode()).hexdigest()[:16]
    net=float(t["netRIllustrative"])
    cost_stress=2*(STRESS_BPS_PER_SIDE-COST_BPS_PER_SIDE)/10000*entry/risk
    return {
      "paperTradeId":h,
      "symbol":symbol,
      "variant":variant,
      "side":"LONG" if long else "SHORT",
      "watchConfirmedUTC":at_utc(t["watchKnownUTC"]),
      "retestConfirmedUTC":at_utc(t["retestKnownUTC"]),
      "entryOpenUTC":at_utc(t["entryOpenUTC"]),
      "entryTSI":at_tsi(t["entryOpenUTC"]),
      "exitKnownUTC":at_utc(t["exitKnownUTC"]),
      "exitTSI":at_tsi(t["exitKnownUTC"]),
      "entryEpoch":t["entryOpenUTC"],
      "exitEpoch":t["exitKnownUTC"],
      "entryPrice":round(entry,8),
      "stopPrice":round(stop,8),
      "tp1":round(float(t["targets"][0]),8),
      "tp2":round(float(t["targets"][1]),8),
      "tp3":round(float(t["targets"][2]),8),
      "entryStopDistancePct":round(100*risk/entry,5),
      "partialTargetsReached":t["targetCount"],
      "exitReason":t["exitReason"],
      "exitHourCandleOHLC":{k:exit_bar[k] for k in ("o","h","l","c")},
      "grossR":round(float(t["realizedR"]),7),
      "netR9BpsPerSide":round(net,7),
      "netR25BpsPerSideStress":round(net-cost_stress,7),
      "closedHourOHLCOnlyStopFirstAssumption":True,
      "noRealFill":True,
    }


def reconstruct(replays,histories):
    """Retain ALL completed paper trades for baseline + every V9 variant."""
    journal=[]
    for symbol,variants in replays.items():
        history=histories["1hour"][symbol+"_PERP.A"]
        hours={int(x["t"]):x for x in history}
        if len(hours)!=len(history):
            raise ValueError("V7_1H_HISTORY_DUPLICATE")
        for variant,report in variants.items():
            if report["status"]!="PAPER_BACKTEST_NOT_LIVE":
                raise ValueError("UNVERIFIED_PAPER_SIMULATION")
            for t in report["trades"]:
                journal.append(validate_trade(t,symbol,variant,hours))
    journal.sort(key=lambda x:(x["entryEpoch"],x["symbol"],x["variant"]))
    return journal


def paper_account(entries,*,equity=INITIAL_EQUITY_USDT,
                  risk_fraction=RISK_FRACTION,leverage=LEVERAGE):
    """Causal 1H entry/exit ordering; no post-hoc winner selection.

    Executed paper trades are entered at their already-simulated next
    candle open; stops/TP are priced by original paper engine.
    Margin/skipped statuses are separate from strategy trade count.
    """
    if equity<=0 or not 0<risk_fraction<=.02 or leverage<=0:
        raise ValueError("INVALID_PAPER_ACCOUNT_RISK")
    events=[]
    for row in entries:
        events.append((row["entryEpoch"],1,row))
        events.append((row["exitEpoch"],0,row))
    # Close known exits before any simultaneous new next-1H open.
    events.sort(key=lambda x:(x[0],x[1],x[2]["symbol"],x[2]["paperTradeId"]))
    initial=equity
    max_equity=equity
    max_drawdown_usdt=0.
    max_drawdown_pct=0.
    active={}
    seen={}
    records=[]
    skip=[]
    changes=[]
    for t,event,row in events:
        key=row["paperTradeId"]
        if event==0:
            pos=active.pop(key,None)
            if pos is None:
                if key not in skip:raise ValueError("PAPER_EXIT_WITHOUT_EXISTING_POSITION")
                continue
            pnl=pos["riskUSDT"]*row["netR9BpsPerSide"]
            equity+=pnl
            if equity<=0:raise ValueError("ILLUSTRATIVE_ACCOUNT_WIPED_OUT")
            max_equity=max(max_equity,equity)
            dd=max_equity-equity
            max_drawdown_usdt=max(max_drawdown_usdt,dd)
            max_drawdown_pct=max(max_drawdown_pct,100*dd/max_equity)
            pos.update({
                "paperNetPnlUSDT":round(pnl,6),
                "equityAfterExitUSDT":round(equity,6),
                "illustrativeMarginFreedAtExit":True,
                "onlyRealizedPnlEquityCurve":True})
            records.append(pos)
            changes.append({"timeUTC":at_utc(t),"equityUSDT":round(equity,6),
                            "paperTradeId":key})
        else:
            if key in active or key in seen:
                raise ValueError("DUPLICATE_ACCOUNT_PAPER_TRADE")
            if any(x["symbol"]==row["symbol"] for x in active.values()):
                raise ValueError("SAME_ASSET_OVERLAPPING_ORIGINAL_V7_PAPER_TRADES")
            risk_usd=equity*risk_fraction
            notional=risk_usd/(row["entryStopDistancePct"]/100)
            margin=notional/leverage
            sum_margin=sum(x["illustrativeIsolatedMarginUSDT"] for x in active.values())
            sum_risk=sum(x["riskUSDT"] for x in active.values())
            if (equity<=0 or sum_margin+margin>equity+1e-9 or
                sum_risk+risk_usd>equity*MAX_SIMULTANEOUS_RISK_FRACTION+1e-9):
                skip.append(key)
                seen[key]="SKIPPED_ILLUSTRATIVE_CAPITAL_OR_CONCURRENT_RISK"
                continue
            item={
              **row,
              "riskUSDT":risk_usd,
              "paperPositionNotionalUSDT":notional,
              "illustrativeIsolatedMarginUSDT":margin,
              "leverage":leverage,
              "riskFractionEquity":risk_fraction,
              "equityBeforeEntryUSDT":equity,
              "noFundingOrLiquidationModeled":True}
            active[key]=item
            seen[key]="OPENED_PAPER_ONLY"
    if active:raise ValueError("PAPER_ACCOUNT_CONTAINS_UNSCORED_OPEN_POSITION")
    if len(seen)!=len(entries):
        raise ValueError("PAPER_ACCOUNT_TRADE_NOT_PROCESSED")
    out={
      "initialEquityUSDT":initial,
      "finalEquityUSDT":round(equity,6),
      "totalPaperNetPnlUSDT":round(equity-initial,6),
      "realizedEquityReturnPct":round(100*(equity/initial-1),5),
      "maxRealizedEquityDrawdownUSDT":round(max_drawdown_usdt,6),
      "maxRealizedEquityDrawdownPct":round(max_drawdown_pct,4),
      "originalEligibleHistoricalPaperTrades":len(entries),
      "paperTradesNotBlockedByIllustrativeMargin":len(records),
      "paperTradesSkippedByIllustrativeMarginOrExposure":len(skip),
      "trades":sorted(records,key=lambda x:(x["entryEpoch"],x["symbol"])),
      "skippedPaperTradeIds":skip,
      "realizedEquityCurve":changes,
      "positionRiskAtEntryFraction":risk_fraction,
      "leverageAtEntry":leverage,
      "executableAtExchangeNotVerified":True,
      "feesAndSlippageAssumed9BpsPerSide":True,
      "initialMarginAt10xIsIllustrative":True,
      "noLiquidationMaintenanceMarginOrFundingModel":True,
      "noIntratradeMarkToMarketOrSpreadOrRealFills":True,
      "notAVerifiedUSDProfit":True,
    }
    if round(sum(x["paperNetPnlUSDT"] for x in records),5)!=round(out["totalPaperNetPnlUSDT"],5):
        raise ValueError("PAPER_ACCOUNT_CONSERVATION_MISMATCH")
    return out


def journal_report(journal):
    summary={}
    for symbol in ("BTCUSDT","SOLUSDT"):
        summary[symbol]={}
        for variant in ("V7_ORIGINAL","V9_94_DIRECTION_GATE",
                        "V9_88_NO_TX_DIRECTION_GATE",
                        "V9_94_AND_88_AGREEMENT_GATE"):
            subset=[row for row in journal
                    if row["symbol"]==symbol and row["variant"]==variant]
            acct=paper_account(subset)
            summary[symbol][variant]={
              "eligibleStrategyPaperTrades":len(subset),
              "executedIllustrativeAccountPaperTrades":acct["paperTradesNotBlockedByIllustrativeMargin"],
              "accountSkippedForMarginOrConcurrentRisk":acct["paperTradesSkippedByIllustrativeMarginOrExposure"],
              "from100USDTFinalEquity":acct["finalEquityUSDT"],
              "from100USDTNetPnl":acct["totalPaperNetPnlUSDT"],
              "from100USDTPct":acct["realizedEquityReturnPct"],
              "maxRealizedEquityDrawdownPct":acct["maxRealizedEquityDrawdownPct"]}
    portfolio={}
    for variant in ("V7_ORIGINAL","V9_94_DIRECTION_GATE",
                    "V9_88_NO_TX_DIRECTION_GATE",
                    "V9_94_AND_88_AGREEMENT_GATE"):
        subset=[row for row in journal if row["variant"]==variant]
        portfolio[variant]=paper_account(subset)
    return {
      "status":"V9_V7_HISTORICAL_CANDLE_BY_CANDLE_PAPER_LEDGER_AND_ILLUSTRATIVE_100USDT_10X",
      "symbols":["BTCUSDT","SOLUSDT"],
      "riskLimit":"0.5% of current realized equity at entry per position, max 1% combined",
      "initialCapitalUSDT":INITIAL_EQUITY_USDT,
      "leverageIsolated":LEVERAGE,
      "assumedFeeSlippagePerSideBps":COST_BPS_PER_SIDE,
      "assumedStressFeeSlippagePerSideBps":STRESS_BPS_PER_SIDE,
      "originalV7BOSRetestStopTPAndPaperFillsUnchanged":True,
      "allVariantsWereIndependentlyReplayedChronologically":True,
      "originalTradeEntriesMustMatchOfficial1HCandleOpens":True,
      "noHistoricalOutcomeUsedToSelectNewParams":True,
      "historicalStudyNotProspective":True,
      "retrospectiveTradesNotActualTrades":True,
      "portfolioPaperAccounts":portfolio,
      "perCoinPaperAccounts":summary,
      "allCompletedHistoricalPaperTradeLedger":journal,
      "realizedEquityCurveExcludesIntrabarLiquidation":True,
      "noBrokerOrders":True,
      "noUserNotifications":True,
      "productionModified":False,
      "noPromotionToLiveSignals":True,
    }


def csv_rows(report):
    names=("paperTradeId","symbol","variant","side","watchConfirmedUTC",
           "retestConfirmedUTC","entryOpenUTC","entryTSI","entryPrice",
           "stopPrice","tp1","tp2","tp3","partialTargetsReached",
           "exitKnownUTC","exitTSI","exitReason","grossR",
           "netR9BpsPerSide","netR25BpsPerSideStress",
           "entryStopDistancePct","fixed100USDT0_5pctRiskPnlUSDT",
           "fixed100USDT0_5pctRiskPositionNotionalUSDT",
           "fixed100USDT0_5pctRiskMarginAt10xUSDT")
    data=[]
    for x in report["allCompletedHistoricalPaperTradeLedger"]:
        a={k:x.get(k) for k in names}
        fixed=INITIAL_EQUITY_USDT*RISK_FRACTION
        a["fixed100USDT0_5pctRiskPnlUSDT"]=round(fixed*x["netR9BpsPerSide"],6)
        notional=fixed/(x["entryStopDistancePct"]/100)
        a["fixed100USDT0_5pctRiskPositionNotionalUSDT"]=round(notional,5)
        a["fixed100USDT0_5pctRiskMarginAt10xUSDT"]=round(notional/LEVERAGE,5)
        data.append(a)
    return names,data


def save_artifacts(report,outputdir):
    out=Path(outputdir);out.mkdir(parents=True,exist_ok=True)
    p=out/"trade_ledger.json"
    p.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    names,rows=csv_rows(report)
    with (out/"all_paper_trades.csv").open("w",newline="",encoding="utf-8-sig") as f:
        w=csv.DictWriter(f,fieldnames=names)
        w.writeheader()
        w.writerows(rows)
    md=[
      "# V7 and V9 — EACH historical paper LONG/SHORT from actual 1H candle opens",
      "",
      "Fixed chronological replay, already investigated historical data; NO live orders.",
      "Theoretical 100 USDT, 10x isolated, 0.5% risk per position; **costs** 9bps/side.",
      "No funding, actual fills, liquidation, maintenance margin or intra-hour equity path.",
      "Every original BOS watch, later retest, next-1H open, stop/TP and exit kept.",
      "",
      "| Asset | Strategy | Eligible paper trades | Margin constrained executed | 100 USDT final (illustrative) | USDT net | Realized max DD |",
      "|---|---|---:|---:|---:|---:|---:|"]
    for symbol,variants in report["perCoinPaperAccounts"].items():
        for variant,v in variants.items():
            md.append(f"| {symbol} | {variant} | {v['eligibleStrategyPaperTrades']} "
                      f"| {v['executedIllustrativeAccountPaperTrades']} "
                      f"| {v['from100USDTFinalEquity']:.4f} "
                      f"| {v['from100USDTNetPnl']:+.4f} "
                      f"| {v['maxRealizedEquityDrawdownPct']:.4f}% |")
    md+=["","## BTC+SOL in a single separate illustrative account",
         "One at a time per coin, maximum combined concurrent 1% risk, margin cap for isolated 10x.",
         "| Strategy | Eligible paper trades | Paper executions | 100 USDT final | USDT net | Realized max DD |",
         "|---|---:|---:|---:|---:|---:|"]
    for variant,v in report["portfolioPaperAccounts"].items():
        md.append(f"| {variant} | {v['originalEligibleHistoricalPaperTrades']} "
                  f"| {v['paperTradesNotBlockedByIllustrativeMargin']} "
                  f"| {v['finalEquityUSDT']:.4f} "
                  f"| {v['totalPaperNetPnlUSDT']:+.4f} "
                  f"| {v['maxRealizedEquityDrawdownPct']:.4f}% |")
    md+=["","## Original historical trades, exact entry/exit candles"]
    for sym in ("SOLUSDT","BTCUSDT"):
        md+=["",f"### {sym}",
             "| Strategy | Entry TSİ | Direction | Entry | Stop | TP1 / TP2 / TP3 | Exit TSİ | Reason | Net R |",
             "|---|---|---|---:|---:|---|---|---|---:|"]
        for x in [z for z in report["allCompletedHistoricalPaperTradeLedger"]
                  if z["symbol"]==sym]:
            md.append(f"| {x['variant']} | {x['entryTSI']} | {x['side']} "
                      f"| {x['entryPrice']} | {x['stopPrice']} "
                      f"| {x['tp1']} / {x['tp2']} / {x['tp3']} "
                      f"| {x['exitTSI']} | {x['exitReason']} "
                      f"| {x['netR9BpsPerSide']:+.4f} |")
    md+=["","**IMPORTANT:** This is a past-bar **paper** ledger, never real orders; "
         "USD values are illustrations conditioned on original simulator fills. "
         "Funding, liquidation, minimum lot, spreads and true executions can materially change results.",
         ""]
    (out/"trade_ledger.md").write_text("\n".join(md),encoding="utf-8")
    print("V9_V7_EACH_PAST_CANDLE_PAPER_TRADE_LEDGER",
          {s:{v:z["from100USDTNetPnl"] for v,z in vs.items()}
           for s,vs in report["perCoinPaperAccounts"].items()},
          flush=True)
