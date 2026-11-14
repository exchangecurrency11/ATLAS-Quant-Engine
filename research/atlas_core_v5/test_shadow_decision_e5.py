"""E5-A negative controls: honest source provenance and non-actionable cards.

No network, no orders, no alerts, no repository writes in tests.
"""
from __future__ import annotations
from copy import deepcopy
from unittest import TestCase
from unittest.mock import patch
from research.atlas_core_v5 import shadow_decision_e5 as m

class E5SourceSafety(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows=m.historical_rows()

    def test_exact_frozen_source_pins_and_preflight(self):
        pins,stage=m.froze_sources()
        self.assertEqual(len(pins),5)
        self.assertEqual(stage["actualForwardTradesCredited"],0)
        self.assertTrue(stage["noLiveSignalReady"])
        self.assertEqual(stage["status"],
                         "NO_COMPLETED_POSTFREEZE_PROSPECTIVE_MONTHLY_SNAPSHOT_YET")

    def test_e4b_source_pinned(self):
        _,digest=m.get_pinned_source("research/atlas_core_v4/atlas_core_e4b.py")
        self.assertEqual(len(digest),64)

    def test_source_hash_tamper_fails_closed(self):
        with patch.dict(m.SOURCE_PINS,{"research/atlas_core_v4/atlas_core_e4b.py":"0"*40}):
            with self.assertRaisesRegex(ValueError,"E5A_FROZEN_SOURCE_GIT_BLOB_DRIFT"):
                m.froze_sources()

    def test_51_causal_historical_trade_inputs(self):
        self.assertEqual(len(self.rows),51)
        coins={}
        for r in self.rows:
            m.validate_packet(r)
            coins[r["asset"]]=coins.get(r["asset"],0)+1
            self.assertFalse(r["isProspective"])
            self.assertNotIn("exitKnownUTC",r)
            self.assertNotIn("netR",r)
        self.assertEqual(coins,{"BTCUSDT":15,"ETHUSDT":16,"SOLUSDT":20})

    def test_false_forward_claim_rejected(self):
        p={**self.rows[0],"isProspective":True}
        with self.assertRaisesRegex(ValueError,"E5A_FALSE_FORWARD_CLAIM"):
            m.validate_packet(p)

    def test_no_unknown_unverified_packet_fields(self):
        p={**self.rows[0],"futureReturn":5.0}
        with self.assertRaisesRegex(ValueError,"E5A_UNEXPECTED_OR_MISSING_PACKET_FIELDS"):
            m.validate_packet(p)

    def test_forged_historical_price_rejected(self):
        p={**self.rows[0],"entryPrice":self.rows[0]["entryPrice"]+5}
        with self.assertRaisesRegex(ValueError,"E5A_FABRICATED_HISTORICAL_TRADE"):
            m.validate_packet(p)

    def test_forged_historical_stop_distance_rejected(self):
        p={**self.rows[0],"referenceRiskPctRounded":self.rows[0]["referenceRiskPctRounded"]+.002}
        with self.assertRaisesRegex(ValueError,"E5A_FABRICATED_HISTORICAL_TRADE"):
            m.validate_packet(p)

    def test_forged_source_digest_rejected(self):
        p={**self.rows[0],"immutableSourceSHA256":"a"*64}
        with self.assertRaisesRegex(ValueError,"E5A_FABRICATED_HISTORICAL_TRADE"):
            m.validate_packet(p)

    def test_lookahead_entry_time_not_allowed(self):
        p={**self.rows[0],"asOfUTC":"2026-11-15T00:00:00Z"}
        with self.assertRaisesRegex(ValueError,"E5A_BAD_V92_CAUSAL_ENTRY_SEQUENCE"):
            m.validate_packet(p)

    def test_not_live_tradable_under_any_historical_packet(self):
        for p in self.rows:
            c=m.hypothetical_cost_card(p)
            self.assertFalse(c["realTradePermission"])
            self.assertFalse(c["autoOrderAllowed"])
            self.assertFalse(c["candidatePromotionAllowed"])
            self.assertFalse(c["userNotificationAllowed"])
            self.assertIn(c["decision"],("WAIT","PASS_COST_STRESS",
                                        "PASS_PORTFOLIO_RISK","HISTORICAL_REVIEW_ONLY"))

    def test_real_position_snapshot_missing_yields_wait_if_cost_not_rejected(self):
        possible=[p for p in self.rows if m.hypothetical_cost_card(p)["decision"]=="WAIT"]
        self.assertTrue(possible)
        result=m.hypothetical_cost_card(possible[0])
        self.assertEqual(result["decision"],"WAIT")
        self.assertIn("OPEN_POSITION_SNAPSHOT_NOT_AVAILABLE",result["reasons"])

    def test_not_an_expected_return_or_win_probability(self):
        out=m.hypothetical_cost_card(self.rows[0])
        self.assertIn("netRIfAllThreeTakeProfitsHitNotExpectedR",out)
        self.assertNotIn("winProbability",out)
        self.assertNotIn("expectedProfit",out)

    def test_cost_stress_monotonically_worse(self):
        for row in self.rows:
            result=m.hypothetical_cost_card(row)
            data=result["netRIfAllThreeTakeProfitsHitNotExpectedR"]
            self.assertGreater(data["9"],data["25"])
            self.assertGreater(data["25"],data["50"])

    def test_frozen_preflight_no_month_snapshot_is_not_forward_signal(self):
        with patch.object(m.Path,"exists",return_value=True):
            _,s=m.froze_sources()
        self.assertEqual(s["status"],"PROSPECTIVE_SNAPSHOTS_PRESENT_BUT_NO_E5A_VALIDATED_ADAPTER")
        self.assertTrue(s["noLiveSignalReady"])

class E5PortfolioAndContext(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows=m.historical_rows()
        cls.possible=next(x for x in cls.rows
                          if m.hypothetical_cost_card(x)["decision"]=="WAIT")

    def flat(self,packet):
        return {"kind":"SYNTHETIC_FLAT_DEMO",
                "asOfUTC":packet["entryOpenUTC"],
                "realizedEquityUSDT":10000,
                "openPositions":[]}

    def test_synthetic_flat_only_review_not_authorization(self):
        card=m.hypothetical_cost_card(self.possible,self.flat(self.possible))
        self.assertEqual(card["decision"],"HISTORICAL_REVIEW_ONLY")
        self.assertFalse(card["realTradePermission"])
        self.assertGreater(card["hypotheticalMaxPositionNotionalUSDT"],0)
        self.assertIn("POSITION_SNAPSHOT_IS_SYNTHETIC_NOT_REAL",card["reasons"])

    def test_shared_risk_account_already_at_cap(self):
        p=self.possible
        positions={"kind":"VERIFIED_READ_ONLY_PAPER_SNAPSHOT",
                   "asOfUTC":p["entryOpenUTC"],
                   "realizedEquityUSDT":10000,
                   "openPositions":[{"asset":next(x for x in m.e2.ASSETS if x!=p["asset"]),
                                     "reservedStopRiskUSDT":100,
                                     "grossNotionalUSDT":1000}]}
        card=m.hypothetical_cost_card(p,positions)
        self.assertEqual(card["decision"],"PASS_PORTFOLIO_RISK")
        self.assertIn("SHARED_PORTFOLIO_BUDGET_EXHAUSTED",card["reasons"])

    def test_overlapping_same_asset_is_rejected(self):
        p=self.possible
        positions={"kind":"VERIFIED_READ_ONLY_PAPER_SNAPSHOT",
                   "asOfUTC":p["entryOpenUTC"],
                   "realizedEquityUSDT":10000,
                   "openPositions":[{"asset":p["asset"],
                                     "reservedStopRiskUSDT":5,
                                     "grossNotionalUSDT":1000}]}
        self.assertEqual(m.hypothetical_cost_card(p,positions)["decision"],"PASS_PORTFOLIO_RISK")

    def test_stale_position_snapshot_rejected(self):
        pos=self.flat(self.possible)
        pos["asOfUTC"]="2026-11-15T00:00:00Z"
        with self.assertRaisesRegex(ValueError,"E5A_STALE_OR_FUTURE_POSITION_SNAPSHOT"):
            m.hypothetical_cost_card(self.possible,pos)

    def test_synthetic_flat_cannot_have_open_positions(self):
        pos=self.flat(self.possible)
        pos["openPositions"]=[{"asset":"BTCUSDT","reservedStopRiskUSDT":0,
                               "grossNotionalUSDT":0}]
        with self.assertRaisesRegex(ValueError,"E5A_FALSE_SYNTHETIC_FLAT_ACCOUNT"):
            m.hypothetical_cost_card(self.possible,pos)

    def test_duplicate_asset_in_position_snapshot_rejected(self):
        pos=self.flat(self.possible)
        pos["kind"]="VERIFIED_READ_ONLY_PAPER_SNAPSHOT"
        row={"asset":"ETHUSDT","reservedStopRiskUSDT":50,
             "grossNotionalUSDT":500}
        pos["openPositions"]=[row,row]
        with self.assertRaisesRegex(ValueError,"E5A_DUPLICATE_OR_UNKNOWN_ASSET_POS"):
            m.hypothetical_cost_card(self.possible,pos)

    def test_fresh_main_market_context_only_not_setup(self):
        now=m.strict_utc("2026-11-14T21:00:00Z")
        feed={"ok":True,"provider":"Coinalyze",
              "checkedAtUTC":"2026-11-14T20:45:00.000Z",
              "results":[]}
        for symbol in ("BTCUSDT_PERP.A","SOLUSDT_PERP.A"):
            for tf in ("1hour","4hour","daily"):
                feed["results"].append({
                    "symbol":symbol,"interval":tf,"status":"READY",
                    "closeTimeUTC":"2026-11-14T20:00:00.000Z",
                    "candle":{"close":100}
                })
        import json
        from io import BytesIO
        class FakeResponse:
            def __enter__(self):return self
            def __exit__(self,*a):return False
            def read(self,n):return json.dumps(feed).encode()
        with patch.object(m,"urlopen",return_value=FakeResponse()):
            x=m.get_main_context(now,network=True)
        self.assertEqual(x["status"],"CONTEXT_COMPLETE_NOT_A_SIGNAL")
        self.assertFalse(x["isVerifiedV92RetestEntry"])
        self.assertFalse(x["liveTradeSignalProduced"])

    def test_stale_public_main_data_not_tradable(self):
        now=m.strict_utc("2026-11-14T23:00:00Z")
        packet={"ok":True,"provider":"Coinalyze",
                "checkedAtUTC":"2026-11-14T20:00:00.000Z","results":[]}
        import json
        class FakeResponse:
            def __enter__(self):return self
            def __exit__(self,*a):return False
            def read(self,n):return json.dumps(packet).encode()
        with patch.object(m,"urlopen",return_value=FakeResponse()):
            result=m.get_main_context(now,network=True)
        self.assertEqual(result["status"],"STALE_OR_FUTURE_CONTEXT_SNAPSHOT")
        self.assertFalse(result["isVerifiedV92RetestEntry"])

    def test_public_main_unavailable_fail_closed(self):
        with patch.object(m,"urlopen",side_effect=OSError("no network")):
            out=m.get_main_context(m.strict_utc("2026-11-14T21:00:00Z"),network=True)
        self.assertEqual(out["status"],"CONTEXT_UNAVAILABLE_FAIL_CLOSED")
        self.assertFalse(out["liveTradeSignalProduced"])

    def test_offline_report_has_zero_prospective_cards_and_no_writes(self):
        out=m.audit(fetch_context=False,now_utc="2026-11-14T21:00:00Z")
        self.assertEqual(out["historical51InputsAudited"],51)
        self.assertEqual(out["actualNewForwardSignalCount"],0)
        self.assertEqual(out["actualNewForwardSignalCards"],[])
        self.assertTrue(out["allHistoricalCardsUntradeable"])
        self.assertEqual(out["newTradeOrders"],0)
        self.assertEqual(out["newUserAlerts"],0)
        self.assertEqual(out["existingPaperTradesWritten"],0)
        self.assertFalse(out["candidatePromoted"])
        self.assertFalse(out["existingAutomationsChanged"])
        self.assertFalse(out["mainBranchChanged"])
        self.assertTrue(out["pastReturnsWereNotInputsToDecision"])
        self.assertEqual(len(out["historicalExampleCards"]),6)

if __name__=="__main__":
    import unittest
    unittest.main()
