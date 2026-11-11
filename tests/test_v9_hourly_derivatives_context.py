"""V9 hourly OI funding CVD overlay, research-only with strict as-of barrier."""
import copy,unittest
from test_v9_three_asset_derivatives_ablation import make,source_fetch
from v9_hourly_derivatives_context import overlay_at,CONTRACTS,HOUR

CLOSE=10*24*HOUR


class V9HourlyDerivativeTests(unittest.TestCase):
    def test_three_asset_history_and_point_in_time_context(self):
        output=overlay_at(CLOSE,"mock",fetch=source_fetch(make()))
        self.assertEqual(output["status"],"V9_HOURLY_OI_FUNDING_TAKER_CONTEXT_NOT_SIGNAL")
        self.assertFalse(output["noTradingOrders"] is False)
        self.assertTrue(output["noUserNotifications"])
        self.assertEqual(set(output["contracts"]),set(CONTRACTS))
        for sym,obs in output["contracts"].items():
            self.assertEqual(obs["asOfClosed1HUTC"],output["asOfClosed1HUTC"])
            self.assertTrue(obs["featureSourceAligned28Closed1Hours"])
            self.assertFalse(obs["directionalSignalsFromThisOverlayAuthorized"])
            self.assertTrue(obs["takerBVNotIndependentlyVerifiedForBTCETH"])
            self.assertTrue(obs["notAnOwnCandleColorForecast"])
            self.assertIn("openInterest4HChangePct",obs)
            self.assertIn("fundingProviderHistoryLastClosed",obs)
        self.assertEqual(len(output["sourceSHA256"]),3)

    def test_change_in_future_incomplete_sources_does_not_change_closed_context(self):
        orig=make()
        first=overlay_at(CLOSE,"mock",fetch=source_fetch(orig))
        altered=copy.deepcopy(orig)
        for endpoint,series in altered.items():
            for row in series:
                if row["t"]>=CLOSE:
                    row["c"]*=100
                    if "bv" in row:row["bv"]=0
        other=overlay_at(CLOSE,"mock",fetch=source_fetch(altered))
        self.assertEqual(first["contracts"],other["contracts"])

    def test_missing_oi_bar_refuses_to_claim_verified_context(self):
        data=make()
        del data["open-interest-history"][-3]
        with self.assertRaisesRegex(ValueError,"OI_FUNDING_FLOW_LAST28H_NOT_ALIGNED"):
            overlay_at(CLOSE,"mock",fetch=source_fetch(data))

    def test_reject_unaligned_hour_timestamp(self):
        with self.assertRaisesRegex(ValueError,"OVERLAY_1H_CLOSE_NOT_ALIGNED"):
            overlay_at(CLOSE+1,"mock",fetch=source_fetch(make()))


if __name__=="__main__":
    unittest.main()
