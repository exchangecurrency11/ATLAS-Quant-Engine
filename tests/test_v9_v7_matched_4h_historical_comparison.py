"""V7 4H context vote vs V9 4H next-candle own O/C: no fake trade comparison."""
import copy
import unittest
from v9_v7_matched_4h_historical_comparison import (
    _check_vote,compare,freeze_probability,ts,HOUR,FOUR,DAY,iso)

T=ts("2026-11-11T12:00:00Z")
SYM="BTCUSDT_PERP.A"


def fake_v7():
    return {
     "status":"VERIFIED_PAPER_OBSERVATION",
     "observedAtUTC":iso(T-45*60),
     "targetClosed1HUTC":iso(T-HOUR),
     "marketContext":{SYM:{"timeframes":{
         "1hour":{"closeTimeUTC":iso(T-HOUR),"candle":{"close":100}},
         "4hour":{"closeTimeUTC":iso(T-FOUR),"candle":{"close":95},
                  "directionVotes":{"label":"bearish","score":-4}},
         "daily":{"closeTimeUTC":iso(T//DAY*DAY),"candle":{"close":96},
                  "directionVotes":{"label":"bearish","score":-4}}}}},
     "results":{SYM:{"V7_signal_filter":{"newWatchAtThisClose":[]}}}
    }


def src():
    return ({T-2*HOUR:{"c":100}},
            {T-2*FOUR:{"c":95}},
            {T//DAY*DAY:{"c":96}})


class V9V7MatchedTests(unittest.TestCase):
    def test_v7_prior_4h_vote_does_not_become_a_trade_signal(self):
        x=_check_vote(fake_v7(),"BTCUSDT",T,*src())
        self.assertEqual(x["status"],"VERIFIED_V7_MARKET_CONTEXT_VOTE_NOT_SIGNAL")
        self.assertEqual(x["mapped4HColorVoteProxy"],"RED")
        self.assertTrue(x["notAV7TradeSignal"])
        self.assertTrue(x["chatGPTNotificationDeliveryNotProvenByGithubSnapshot"])

    def test_v7_poststart_snapshot_not_accepted(self):
        x=fake_v7()
        x["observedAtUTC"]=iso(T+1)
        self.assertEqual(_check_vote(x,"BTCUSDT",T,*src())["status"],
                         "V7_SNAPSHOT_CREATED_AFTER_TARGET_START_EXCLUDED")

    def test_v7_incorrect_closed_candle_price_not_accepted(self):
        x=fake_v7()
        x["marketContext"][SYM]["timeframes"]["4hour"]["candle"]["close"]=101
        self.assertEqual(_check_vote(x,"BTCUSDT",T,*src())["status"],
                         "V7_COINALYZE_PRICE_PARITY_MISMATCH")

    def test_v7_mixed_has_no_direction(self):
        x=fake_v7()
        x["marketContext"][SYM]["timeframes"]["4hour"]["directionVotes"]["label"]="mixed"
        v=_check_vote(x,"BTCUSDT",T,*src())
        self.assertIsNone(v["mapped4HColorVoteProxy"])

    def test_paired_comparison_uses_same_target_and_preserves_abstentions(self):
        row=lambda s,pred,v7,actual: {
          "symbol":s,"target4HStartUTC":iso(T),
          "actual4HOwnColor":actual,"v9FrozenModelColor":pred,"v7":v7}
        valid=_check_vote(fake_v7(),"BTCUSDT",T,*src())
        mixed=copy.deepcopy(valid)
        mixed["mapped4HColorVoteProxy"]=None
        z=compare([
          row("BTCUSDT","GREEN",valid,"GREEN"),
          row("BTCUSDT","RED",mixed,"RED"),
          row("BTCUSDT","GREEN",{"status":"MISSING_OR_UNVERIFIED_V7_SOURCE"},"RED"),
          row("ETHUSDT","GREEN",{"status":"MISSING_OR_UNVERIFIED_V7_SOURCE"},"GREEN"),
        ])
        btc=z["BTCUSDT"]
        self.assertEqual(btc["frozenV9AllCompleted"]["n"],3)
        self.assertEqual(btc["pairedSameTarget"]["n"],1)
        self.assertEqual(btc["pairedSameTarget"]["frozenV9"]["correct"],1)
        self.assertEqual(btc["pairedSameTarget"]["v7Prior4HTrendVotePROXY"]["correct"],0)
        self.assertEqual(btc["v7VoteProxyAbstentionsMixed"],1)
        self.assertEqual(btc["v7MissingRejectedLateOrPriceMismatch"],1)

    def test_static_model_formula(self):
        m={"featureCount":2,"scalerMean":[0,0],"scalerScale":[1,1],
           "logisticCoefficients":[0,0],"logisticIntercept":0}
        self.assertEqual(freeze_probability((1.,-1.),m),.5)
        with self.assertRaisesRegex(ValueError,"FEATURE_LENGTH"):
            freeze_probability((1.,),m)


if __name__=="__main__":
    unittest.main()
