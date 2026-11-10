"""Verify no-look-ahead SOL V7/V8 paper shadow association."""
import unittest
from sol_v8_shadow_join import join,PAIR

T="2026-11-10T16:00:00Z"
def pair():
    a={"mode":"PAPER_FORWARD_OBSERVATION_NO_ORDERS",
       "targetClosed1HUTC":T,"observedAtUTC":"2026-11-10T16:24:53Z",
       "status":"VERIFIED_PAPER_OBSERVATION",
       "brokerOrders":False,"productionSystemModified":False,
       "marketContext":{PAIR:{"checkedClosed1HUTC":T,"newBOSCount":0,
                              "noSignalExplanation":"NO_NEW_1H_BOS"}},
       "results":{PAIR:{"V7_signal_filter":{
                            "newWatchAtThisClose":[],
                            "paperTradeExitsObservedAtThisClose":[]},
                         "V7_signal_plus_retest":{
                            "newWatchAtThisClose":[],
                            "paperTradeExitsObservedAtThisClose":[]}}}}
    b={"mode":"SOL_V8_DERIVATIVES_QUALITY_PROBE_NO_ORDERS",
       "targetClosed1HUTC":T,"observedAtUTC":"2026-11-10T16:53:13Z",
       "status":"DATA_VALIDATED_RESEARCH_ONLY","symbol":PAIR,
       "brokerOrders":False,"productionSystemModified":False,
       "liveSignalEnabled":False,
       "openInterest":{"asOfClosedUTC":T,"threeContinuousClosedHours":True,
                       "oneHourChangePct":-0.367768},
       "providerBuyVolume":{"closedHourUTC":T,"providerBuyShare":0.45366,
                            "takerBuySellCrossSourceVerified":False},
       "funding":{"ageSeconds":4,"providerReportedValue":-0.000171,
                  "providerUpdateUTC":"2026-11-10T16:53:09Z",
                  "providerReportedUnitsUnverified":True}}
    return a,b

class ShadowJoinTests(unittest.TestCase):
    def test_pair_is_research_only_and_preserves_late_availability(self):
        a,b=pair()
        s=join(a,b)
        self.assertEqual(s["status"],"PAIRED_RESEARCH_ONLY_NO_SIGNAL")
        self.assertEqual(s["earliestJointAvailabilityUTC"],b["observedAtUTC"])
        self.assertFalse(s["dataWasKnownToV7AtItsDecisionTime"])
        self.assertFalse(s["signalsEnabled"])
        self.assertFalse(s["brokerOrders"])

    def test_mismatched_target_rejected(self):
        a,b=pair()
        b["targetClosed1HUTC"]="2026-11-10T15:00:00Z"
        with self.assertRaisesRegex(ValueError,"TARGET_CLOSED_HOUR"):
            join(a,b)

    def test_stale_or_missing_v7_cannot_pair(self):
        a,b=pair()
        a["status"]="SOURCE_UNAVAILABLE_NO_SIGNAL"
        with self.assertRaisesRegex(ValueError,"V7_NOT_VERIFIED"):
            join(a,b)

    def test_post_hour_observation_disallowed(self):
        a,b=pair()
        b["observedAtUTC"]="2026-11-10T17:03:00Z"
        with self.assertRaisesRegex(ValueError,"OBSERVED_AFTER"):
            join(a,b)

    def test_invalid_oi_time_disallowed(self):
        a,b=pair()
        b["openInterest"]["asOfClosedUTC"]="2026-11-10T15:00:00Z"
        with self.assertRaisesRegex(ValueError,"V8_HOURLY"):
            join(a,b)

    def test_no_made_up_v7_watch(self):
        a,b=pair()
        a["results"][PAIR]["V7_signal_filter"]["newWatchAtThisClose"]=[{"side":"bearish"}]
        s=join(a,b)
        self.assertEqual(s["v7"]["V7_signal_filter_newWatches"],1)
        self.assertFalse(s["signalsEnabled"])

if __name__=="__main__":
    unittest.main()
