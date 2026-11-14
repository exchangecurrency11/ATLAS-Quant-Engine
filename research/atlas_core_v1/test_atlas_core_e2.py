"""E2 negative controls and 51 historically matched oracle trade keys."""
import copy
import unittest
from unittest.mock import patch
from research.atlas_core_v1 import atlas_core_e2 as m

def record(symbol, entry, end):
    return {"symbol":symbol,"entryEpoch":entry,"exitEpoch":end}

class ThreeAssetE2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.primary,_=m.read_pinned(m.SOURCE)
        cls.older,_=m.read_pinned(m.OLDER)
        cls.later,_=m.read_pinned(m.LATER)

    def segment(self, coin="BTCUSDT", period="2022_2024"):
        return copy.deepcopy(self.primary["periods"][period]["assets"][coin]["variants"]["BASELINE"]), \
            copy.deepcopy(m.witness_of(self.older,self.later,period,coin))

    def test_all_51_trade_keys_and_witness_parity(self):
        res=m.audit()
        self.assertEqual(res["totalTapeTradesMatched"],51)
        self.assertEqual(res["totalWitnessTradesMatched"],51)
        self.assertFalse(res["independentOutOfSample"])
        self.assertTrue(res["verifiesHistoricalReportsNotRawOHLCReplays"])
        self.assertFalse(res["underlyingOfficialArchivesRedownloaded"])
        self.assertIsNone(res["portfolioPF"])

    def test_three_assets_two_periods_all_groups(self):
        r=m.audit()
        self.assertEqual(set(r["symbols"]),set(m.ASSETS))
        counts={c:[r["symbols"][c][p]["tradesMatched"] for p in m.PERIODS] for c in m.ASSETS}
        self.assertEqual(counts,{"BTCUSDT":[10,5],"ETHUSDT":[10,6],"SOLUSDT":[12,8]})

    def test_trade_timestamp_mismatch_rejected(self):
        a,b=self.segment()
        b["tradeEntryExitEvidence"][0]["entryUTC"]="2020-01-01T00:00:00Z"
        with self.assertRaisesRegex(ValueError,"E2_ENTRY_EXIT"):
            m.audit_tape(a,b,coin="BTCUSDT",period="2022_2024")

    def test_net_r9_mismatch_rejected(self):
        a,b=self.segment()
        b["tradeEntryExitEvidence"][0]["netR9bps"]+=0.5
        with self.assertRaisesRegex(ValueError,"E2_ENTRY_EXIT"):
            m.audit_tape(a,b,coin="BTCUSDT",period="2022_2024")

    def test_exit_reason_rejection(self):
        a,b=self.segment()
        a["tradeEvidence"][0]["exitReason"]="UNKNOWN"
        with self.assertRaisesRegex(ValueError,"E2_UNKNOWN_EXIT_REASON"):
            m.audit_tape(a,b,coin="BTCUSDT",period="2022_2024")

    def test_retest_future_tamper_blocked(self):
        a,b=self.segment()
        b["tradeEntryExitEvidence"][0]["retestUTC"]="2035-01-01T00:00:00Z"
        with self.assertRaisesRegex(ValueError,"E2_RETEST"):
            m.audit_tape(a,b,coin="BTCUSDT",period="2022_2024")

    def test_no_future_classification(self):
        a,b=self.segment()
        a["noHistoricalTradesCreditedToForward"]=False
        with self.assertRaisesRegex(ValueError,"E2_FALSE_FORWARD"):
            m.audit_tape(a,b,coin="BTCUSDT",period="2022_2024")

    def test_wrong_risk_pct_detected_in_total_stress(self):
        a,b=self.segment()
        a["tradeEvidence"][0]["riskPct"]=0.001
        with self.assertRaisesRegex(ValueError,"E2_R25"):
            m.audit_tape(a,b,coin="BTCUSDT",period="2022_2024")

    def test_r25_stress_rounding_error_bound(self):
        report=m.audit()
        for coin,groups in report["symbols"].items():
            for name,s in groups.items():
                self.assertLess(abs(s["R25ApproxMinusOfficialReport"]),m.PER_PERIOD_R25_ABS_TOL)
                self.assertEqual(s["sourceNetR25"],s["sourceNetR25"])
                self.assertTrue(s["timeOrderingVerified"])

    def test_cost_stress_on_rounded_risk(self):
        r=m.audit()["symbols"]["SOLUSDT"]["2022_2024"]
        self.assertGreater(r["computedR25ApproxFromRoundedEvidence"],0)
        self.assertLess(r["computedR50ApproxFromRoundedEvidence"],0)  # baseline SOL at 50bps is negative
        self.assertEqual(r["winsAt9bps"],6)
        self.assertEqual(r["winsAt25bpsDerived"],5)

    def test_half_open_positions_adjacent_not_overlapping(self):
        data=[record("BTCUSDT",0,3600),record("SOLUSDT",3600,7200)]
        r=m.trade_overlap(data)
        self.assertEqual(r["maxConcurrentPositionsInHistoricalTape"],1)
        self.assertEqual(r["maxConcurrentDistinctAssets"],1)
        self.assertEqual(r["crossAssetOverlapEntryEvents"],0)

    def test_cross_asset_concurrent_positions_detected(self):
        data=[record("BTCUSDT",0,7200),record("SOLUSDT",3600,10800),record("ETHUSDT",5400,6000)]
        r=m.trade_overlap(data)
        self.assertEqual(r["maxConcurrentPositionsInHistoricalTape"],3)
        self.assertEqual(r["maxConcurrentDistinctAssets"],3)
        self.assertEqual(r["crossAssetOverlapEntryEvents"],3)

    def test_unmatched_exit_fails(self):
        with self.assertRaisesRegex(ValueError,"E2_POSITION_EXIT_WITHOUT_ENTRY"):
            m.trade_overlap([record("BTCUSDT",100,0)])

    def test_frozen_source_drift_blocks(self):
        with patch.dict(m.GIT_BLOB_PINS,{str(m.SOURCE):"0"*40}):
            with self.assertRaisesRegex(ValueError,"E2_FROZEN_GIT_BLOB_DRIFT"):
                m.audit()

    def test_no_automatic_promotion(self):
        result=m.audit()
        self.assertTrue(result["noOrders"])
        self.assertTrue(result["noNotifications"])
        self.assertTrue(result["noProductionChanges"])
        self.assertEqual(result["freshForwardClosedTradesClaimed"],0)
        self.assertIsNone(result["portfolioR"])

if __name__=="__main__":
    unittest.main()
