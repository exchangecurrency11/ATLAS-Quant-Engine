"""V9.2 independent capped paper ledger tests. Paper-only, no retrospective fill."""
import copy
import unittest

from v92_stable_hardening import seconds,stamp
from v92_capped_paper import (
    FIRST,MODE,ASSETS,original_intents,pending_retest,step,
    still_valid_original_position,BPS_BASE,BPS_STRESS,MAX_HOLD_BARS
)

T=seconds(FIRST)

def candle(price=100.,high=None,low=None):
    return {"o":price,"h":high if high is not None else price,
            "l":low if low is not None else price,"c":price,"v":100.}
def bars(price=100.,high=None,low=None):
    return {s:candle(price,high,low) for s in ASSETS}
def intent(sym,t=T,side="bullish",stop=99.):
    return {
        "symbol":sym,"side":side,"stop":stop,
        "watchKnownUTC":t-3600,"retestKnownUTC":t,
        "sourceV92SealedCloseUTC":stamp(t),
        "paperOnlyNoRealOrder":True,"notAnEntryOrActualFill":True
    }
def go(prev,t,b,si=None,commit=True,verified=True,ready=True,original_override=None):
    original={s:None for s in ASSETS}
    if prev is not None:
        for s,p in prev["intentNextObservation"].items():
            original[s]={"side":p["side"],"stop":p["stop"],
                         "watchKnownUTC":p["watchKnownUTC"],
                         "retestKnownUTC":p["retestKnownUTC"]}
    if original_override is not None:
        original.update(original_override)
    return step(prev,t,b,si if si is not None else {},
                original_open_positions=original,
                prior_committed_before_this_close=commit,
                verified=verified,stable_ready=ready,
                captured_at=t+1800)

class CappedPaperTests(unittest.TestCase):
    def test_three_simultaneous_retsets_only_two_allowed_by_20_usdt(self):
        s0=go(None,T,bars(),{a:intent(a) for a in ASSETS})
        self.assertEqual(len(s0["intentNextObservation"]),3)
        self.assertEqual(s0["closedPaperTrades"],0)
        self.assertEqual(s0["openRiskReservationUSDT"],0)
        s1=go(s0,T+3600,bars())
        self.assertEqual(set(s1["openPositions"]),{"BTCUSDT","ETHUSDT"})
        self.assertEqual(s1["openRiskReservationUSDT"],20)
        rejects=[e for e in s1["observedEvents"] if
                 e["type"]=="CAPPED_INTENT_REJECTED"]
        self.assertEqual(len(rejects),1)
        self.assertEqual(rejects[0]["symbol"],"SOLUSDT")
        self.assertEqual(rejects[0]["reason"],"COMBINED_RISK_CAP_EXCEEDED")
        self.assertTrue(all(p["reservedStopAndCostUSDT"]==10
                            for p in s1["openPositions"].values()))
        self.assertEqual(s1["realizedPaperPnL9BpsUSDT"],0)

    def test_stop_first_tp_collision_only_after_entry_hour(self):
        s0=go(None,T,bars(),{"BTCUSDT":intent("BTCUSDT")})
        s1=go(s0,T+3600,bars())
        self.assertEqual(s1["closedPaperTrades"],0)
        # same next-hour bar has all three TPs AND the stop -> stop first
        s2=go(s1,T+7200,bars(high=104,low=98))
        self.assertEqual(s2["closedPaperTrades"],1)
        r=s2["closedTrades"][0]
        self.assertEqual(r["exitReason"],"STOP_FIRST_OR_AFTER_TP")
        self.assertEqual(r["realizedGrossR"],-1)
        self.assertEqual(r["targetCount"],0)
        self.assertGreaterEqual(r["netPaperPnL25BpsUSDT"],-10.000001)
        self.assertAlmostEqual(s2["paperRealizedEquity9BpsUSDT"],
                               1000+r["netPaperPnL9BpsUSDT"],places=5)
        self.assertGreater(s2["paperRealizedEquityStress25BpsUSDT"],
                           989.999999)

    def test_gated_intent_cannot_be_backdated(self):
        s0=go(None,T,bars(),{"SOLUSDT":intent("SOLUSDT")})
        s1=go(s0,T+3600,bars(),commit=False)
        self.assertEqual(len(s1["openPositions"]),0)
        self.assertTrue(any("NO_PRIOR_COMMIT" in e.get("reason","")
                            for e in s1["observedEvents"]))
        self.assertEqual(s1["paperRealizedEquity9BpsUSDT"],1000)
        with self.assertRaisesRegex(ValueError,"DUPLICATE_OR_RETROACTIVE"):
            go(s1,T+3600,bars())

    def test_source_gap_with_open_position_freezes_without_fake_pnl(self):
        s0=go(None,T,bars(),{"SOLUSDT":intent("SOLUSDT")})
        s1=go(s0,T+3600,bars())
        s3=go(s1,T+10800,bars(high=104,low=98))
        self.assertTrue(s3["historyFrozenByMissingHour"])
        self.assertEqual(len(s3["openPositions"]),1)
        self.assertEqual(s3["closedPaperTrades"],0)
        self.assertEqual(s3["realizedPaperPnL9BpsUSDT"],0)
        s4=go(s3,T+14400,bars(high=104,low=98))
        self.assertTrue(s4["historyFrozenByMissingHour"])
        self.assertEqual(s4["closedPaperTrades"],0)

    def test_stale_audit_prevents_entry_and_drops_stale_intent(self):
        s0=go(None,T,bars(),{"ETHUSDT":intent("ETHUSDT")})
        s1=go(s0,T+3600,bars(),ready=False)
        self.assertEqual(len(s1["openPositions"]),0)
        self.assertEqual(s1["intentNextObservation"],{})
        s2=go(s1,T+7200,bars(),ready=True)
        self.assertEqual(s2["closedPaperTrades"],0)

    def test_original_v92_early_stop_prevents_new_delayed_entry(self):
        s0=go(None,T,bars(),{"SOLUSDT":intent("SOLUSDT")})
        s1=go(s0,T+3600,bars(),
              original_override={"SOLUSDT":None})
        self.assertEqual(len(s1["openPositions"]),0)
        reasons=[x.get("reason") for x in s1["observedEvents"]]
        self.assertIn("ORIGINAL_V92_POSITION_ALREADY_EXITED_OR_CHANGED",reasons)

    def test_original_v92_stop_or_retest_change_blocks(self):
        s0=go(None,T,bars(),{"BTCUSDT":intent("BTCUSDT")})
        s1=go(s0,T+3600,bars(),
              original_override={"BTCUSDT":{"side":"bullish",
                "watchKnownUTC":T-3600,"retestKnownUTC":T,
                "stop":97.}})
        self.assertEqual(s1["closedPaperTrades"],0)
        self.assertEqual(len(s1["openPositions"]),0)

    def test_eligible_future_price_drift_invalidates_wrong_stop(self):
        s0=go(None,T,bars(),{"BTCUSDT":intent("BTCUSDT",stop=99.)})
        s1=go(s0,T+3600,bars(price=98.))
        self.assertEqual(len(s1["openPositions"]),0)
        e=[e for e in s1["observedEvents"] if e["type"]=="CAPPED_INTENT_REJECTED"]
        self.assertEqual(e[0]["reason"],"STOP_WRONG_SIDE")

    def test_partial_tp_one_then_time_exit_and_fee_stress(self):
        s0=go(None,T,bars(),{"BTCUSDT":intent("BTCUSDT")})
        s1=go(s0,T+3600,bars())
        s2=go(s1,T+7200,bars(high=101.5,low=99.4))
        self.assertEqual(s2["openPositions"]["BTCUSDT"]["targetCount"],1)
        self.assertEqual(s2["closedPaperTrades"],0)
        current=s2
        for j in range(2,MAX_HOLD_BARS+1):
            current=go(current,T+(j+1)*3600,bars(100.))
        self.assertEqual(current["closedPaperTrades"],1)
        trade=current["closedTrades"][0]
        self.assertEqual(trade["exitReason"],"TIME_EXIT_AT_CLOSE")
        self.assertEqual(trade["targetCount"],1)
        self.assertGreater(trade["netPaperPnL9BpsUSDT"],
                           trade["netPaperPnL25BpsUSDT"])

    def test_retest_provenance_not_inferred_from_bos_only(self):
        state={"currentPaperState":{"pendingNextOpenPaperEntry":None,
                                    "activeBOSWatch":{"side":"bullish"}}}
        self.assertIsNone(pending_retest(state,T))
        state["currentPaperState"]["pendingNextOpenPaperEntry"]={
            "side":"bearish","stop":103.,"watchKnownUTC":T-3600,
            "retestKnownUTC":T}
        self.assertEqual(pending_retest(state,T)["side"],"bearish")
        state["currentPaperState"]["pendingNextOpenPaperEntry"]["retestKnownUTC"]=T-3600
        with self.assertRaisesRegex(ValueError,"RETROACTIVE"):
            pending_retest(state,T)

    def test_missing_or_malformed_ohlcv_fail_closed(self):
        with self.assertRaisesRegex(ValueError,"CANDLE_FIELDS"):
            go(None,T,{"BTCUSDT":{"o":100},**{s:candle() for s in ASSETS if s!="BTCUSDT"}})
        bad=bars();bad["ETHUSDT"]["h"]=90
        with self.assertRaisesRegex(ValueError,"UNVERIFIED_BAR"):
            go(None,T,bad)
    
    def test_no_change_original_books_and_no_real_orders(self):
        s=go(None,T,bars())
        self.assertEqual(s["mode"],MODE)
        self.assertTrue(s["noLegacyV7V91OrV92Modification"])
        self.assertTrue(s["noHistoricalBackfill"])
        self.assertTrue(s["noBrokerOrders"])
        self.assertTrue(s["noUserNotifications"])
        self.assertTrue(s["entryPriceIsLaterObservedCloseNotExecutableFill"])
        self.assertEqual(s["paperInitialUSDT"],1000)
        self.assertEqual(s["riskPolicy"]["maxRiskUSDTPerPosition"],10)
        self.assertEqual(s["riskPolicy"]["maxCombinedOpenRiskUSDT"],20)

if __name__=="__main__":
    unittest.main()
