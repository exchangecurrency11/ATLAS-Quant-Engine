"""Actual past candle paper LONG/SHORT ledger and 100USDT 10x account constraints."""
import copy,math,unittest
from v9_v7_historical_paper_trade_ledger import (
 validate_trade,paper_account,reconstruct,journal_report,csv_rows,
 RISK_FRACTION,LEVERAGE)
from v9_next_4h_color_research import HOUR,ts

T=ts("2026-03-12T12:00:00Z")


def fake_trade(side="bullish",price=100,stop=98,grossR=2,
               reason="TP3_COMPLETE",count=3):
    risk=abs(price-stop)
    direction=1 if side=="bullish" else -1
    return {
       "watchKnownUTC":T-2*HOUR,"retestKnownUTC":T-HOUR,
       "entryOpenUTC":T,"exitKnownUTC":T+HOUR,
       "entry":price,"stop":stop,
       "targets":[price+direction*risk*n for n in (1,2,3)],
       "risk":risk,"side":side,"realizedR":grossR,
       "netRIllustrative":grossR-.0018*price/risk,
       "exitReason":reason,"targetCount":count}


def source(entry=100,stop=98):
    return {T:{"t":T,"o":entry,"h":108.,"l":97.,"c":104.},
            T+HOUR:{"t":T+HOUR,"o":104,"h":104,"l":99,"c":100}}


def row_from_trade(t=None,symbol="SOLUSDT",variant="V7_ORIGINAL"):
    return validate_trade(t or fake_trade(),symbol,variant,source())


class PaperBacktestTradeLedger(unittest.TestCase):
    def test_long_original_paper_next_open_tp3_and_costs(self):
        r=row_from_trade()
        self.assertEqual(r["entryPrice"],100)
        self.assertEqual(r["stopPrice"],98)
        self.assertEqual([r["tp1"],r["tp2"],r["tp3"]],[102,104,106])
        self.assertEqual(r["side"],"LONG")
        self.assertEqual(r["netR9BpsPerSide"],1.91)
        self.assertEqual(r["netR25BpsPerSideStress"],1.75)
        self.assertIn("TSİ",r["entryTSI"])
        self.assertTrue(r["noRealFill"])
        self.assertEqual(r["exitHourCandleOHLC"]["h"],108)

    def test_same_hour_stop_first_not_optimistic_target_credit(self):
        t=fake_trade(side="bearish",stop=102,grossR=-1,
                     reason="STOP_FIRST_OR_AFTER_TP",count=0)
        s={T:{"t":T,"o":100,"h":103,"l":93,"c":94}}
        r=validate_trade(t,"BTCUSDT","V9_94_DIRECTION_GATE",s)
        self.assertEqual(r["netR9BpsPerSide"],-1.09)
        self.assertEqual(r["partialTargetsReached"],0)

    def test_entry_must_be_official_closed_1h_open_no_future_leak(self):
        t=fake_trade()
        prices=source()
        prices[T]["o"]=99.5
        with self.assertRaisesRegex(ValueError,"ENTRY_OR_RISK_NOT_FROM_CLOSED"):
            validate_trade(t,"SOLUSDT","V7_ORIGINAL",prices)

    def test_profit_simulation_risk_half_usdt_10x_and_margins(self):
        r=row_from_trade()
        v=paper_account([r])
        self.assertEqual(v["originalEligibleHistoricalPaperTrades"],1)
        self.assertEqual(v["paperTradesNotBlockedByIllustrativeMargin"],1)
        self.assertEqual(v["totalPaperNetPnlUSDT"],.955)
        self.assertEqual(v["finalEquityUSDT"],100.955)
        self.assertAlmostEqual(v["trades"][0]["riskUSDT"],.5)
        self.assertAlmostEqual(v["trades"][0]["paperPositionNotionalUSDT"],25)
        self.assertAlmostEqual(v["trades"][0]["illustrativeIsolatedMarginUSDT"],2.5)
        self.assertTrue(v["notAVerifiedUSDProfit"])

    def test_loss_cost_does_not_ensure_exact_half_percent_equity_loss(self):
        t=fake_trade(side="bearish",stop=102,grossR=-1,
                     reason="STOP_FIRST_OR_AFTER_TP",count=0)
        row=validate_trade(t,"BTCUSDT","V7_ORIGINAL",
                   {T:{"t":T,"o":100,"h":103,"l":93,"c":94}})
        v=paper_account([row])
        self.assertEqual(v["totalPaperNetPnlUSDT"],-.545)
        self.assertEqual(v["finalEquityUSDT"],99.455)
        self.assertGreater(v["maxRealizedEquityDrawdownPct"],.5)

    def test_two_simultaneous_collateral_hungry_positions_skips_second(self):
        a=row_from_trade()
        b=copy.deepcopy(a)
        a["entryStopDistancePct"]=.09
        b["entryStopDistancePct"]=.09
        b["symbol"]="BTCUSDT";b["paperTradeId"]="other"
        v=paper_account([a,b])
        self.assertEqual(v["originalEligibleHistoricalPaperTrades"],2)
        self.assertEqual(v["paperTradesNotBlockedByIllustrativeMargin"],1)
        self.assertEqual(v["paperTradesSkippedByIllustrativeMarginOrExposure"],1)
        self.assertAlmostEqual(v["totalPaperNetPnlUSDT"],.955)

    def test_no_trade_no_fake_100pct(self):
        x=paper_account([])
        self.assertEqual(x["totalPaperNetPnlUSDT"],0)
        self.assertEqual(x["paperTradesNotBlockedByIllustrativeMargin"],0)

    def test_ledger_reconciles_individual_paper_simulator_trades(self):
        t=fake_trade()
        replays={"SOLUSDT":{"V7_ORIGINAL":{
          "status":"PAPER_BACKTEST_NOT_LIVE","trades":[t]}}}
        histories={"1hour":{"SOLUSDT_PERP.A":list(source().values())}}
        journal=reconstruct(replays,histories)
        self.assertEqual(len(journal),1)
        r=journal_report(journal)
        self.assertEqual(len(r["allCompletedHistoricalPaperTradeLedger"]),1)
        self.assertEqual(r["perCoinPaperAccounts"]["SOLUSDT"][
                         "V7_ORIGINAL"]["from100USDTNetPnl"],.955)
        self.assertEqual(r["perCoinPaperAccounts"]["BTCUSDT"][
                         "V7_ORIGINAL"]["eligibleStrategyPaperTrades"],0)
        fields,csv=csv_rows(r)
        self.assertEqual(len(csv),1)
        self.assertEqual(csv[0]["fixed100USDT0_5pctRiskPnlUSDT"],.955)
        self.assertIn("exitReason",fields)


if __name__=="__main__":
    unittest.main()
