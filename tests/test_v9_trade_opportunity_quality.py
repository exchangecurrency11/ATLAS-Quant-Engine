"""V9+ point-in-time BOS risk/quality, no hindsight or price projection."""
import unittest,copy,math
from unittest.mock import patch
from v9_trade_opportunity_quality import (
    SCORE_CANDIDATES,quality_profile,gate_v7_with_quality,HOUR)
T=1760000000//HOUR*HOUR


def candles():
    out=[]
    for i in range(250):
        level=100+i*.025
        out.append({
            "t":T-250*HOUR+i*HOUR,
            "o":level,"h":level+.4,"l":level-.4,
            "c":level+.05,"v":1000.+((i%5)*70)})
    return out


def bos(b,side="bullish"):
    return {"event":"BOS","direction":side,"at":b[-1]["t"],
            "confirmedAt":b[-1]["t"]+HOUR,"brokenLevel":b[-1]["c"]-.3}


class QualityScoringTests(unittest.TestCase):
    def test_all_features_from_only_closed_250_hours_bounded_nonprobabilistic(self):
        bars=candles();signal=bos(bars)
        r=quality_profile(bars,signal,{"EMA20":100,"EMA50":100})
        self.assertEqual(r["status"],"V9_TRADE_QUALITY_SNAPSHOT_FROM_CLOSED_V7_BOS_ONLY")
        self.assertEqual(r["observedClosed1HUTC"],bars[-1]["t"]+HOUR)
        self.assertTrue(0<=r["qualityScoreNotProfitProbability"]<=100)
        self.assertLessEqual(r["qualityScoreNotProfitProbability"],100)
        self.assertIn("relativeVolume",r["components"])
        self.assertIn("volatilityRegime",r["components"])
        self.assertTrue(r["noFutureRetestOrTPUsed"])
        self.assertTrue(r["liquidityFVGAndOrderBlocksNotActualOrders"])
        self.assertTrue(r["noProviderOIOrFundingOrUnverifiedTradeCount"])
        self.assertEqual(set(SCORE_CANDIDATES),{"V9_QUALITY_SCORE_60","V9_QUALITY_SCORE_75"})
        self.assertEqual(r["features"]["atrRegime"] in ("CALM","NORMAL","EXPANSION","CHAOTIC"),True)

    def test_cannot_score_bos_from_future_or_wrong_time(self):
        bars=candles();x=bos(bars)
        x["confirmedAt"]+=1
        with self.assertRaisesRegex(ValueError,"FUTURE_BOS"):
            quality_profile(bars,x,{})
        x=bos(bars);x["at"]+=HOUR
        with self.assertRaisesRegex(ValueError,"NOT_LAST_CLOSED"):
            quality_profile(bars,x,{})

    def test_missing_historical_bar_causes_fail_closed(self):
        b=candles();b[-8]["t"]+=HOUR
        with self.assertRaisesRegex(ValueError,"HAS_GAP"):
            quality_profile(b,bos(b),{})

    def test_future_bar_cannot_enter_existing_confirmed_bos(self):
        b=candles()
        current=quality_profile(b,bos(b),{})["qualityScoreNotProfitProbability"]
        appended=copy.deepcopy(b)
        last=copy.deepcopy(appended[-1])
        last["t"]+=HOUR
        last["c"]+=30
        last["h"]+=30
        appended.append(last)
        with self.assertRaisesRegex(ValueError,"NOT_LAST_CLOSED"):
            quality_profile(appended,bos(b),{})
        self.assertTrue(math.isfinite(current))

    def test_scoring_never_turns_failed_v7_bos_into_entry(self):
        b=candles();ev={}
        original={"passed":False,"reasons":["V7_RELATIVE_VOLUME_LOW"]}
        with patch("v9_trade_opportunity_quality.quality_profile") as p:
            out=gate_v7_with_quality(b,bos(b),{},original,60,ev)
        p.assert_not_called()
        self.assertEqual(out,original)
        self.assertEqual(ev,{})

    def test_thresholds_different_and_are_not_selected_by_outcomes(self):
        b=candles();signal=bos(b)
        original={"passed":True,"reasons":[]}
        ev={}
        with patch("v9_trade_opportunity_quality.quality_profile",
             return_value={
               "qualityScoreNotProfitProbability":67,
               "qualityBand":"MEDIUM",
               "features":{"atrRegime":"NORMAL",
                           "nearFVGCount":0,"nearOrderBlockCount":1,
                           "prior20HighLowSweepAgainstOpposingSide":False},
               "observedClosed1HUTC":b[-1]["t"]+HOUR,
               "direction":"bullish"}) as p:
            accept=gate_v7_with_quality(b,signal,{},original,60,ev)
            reject=gate_v7_with_quality(b,signal,{},original,75,ev)
        self.assertTrue(accept["passed"])
        self.assertFalse(reject["passed"])
        self.assertEqual(ev["v7QualifyingBOSScored"],2)
        self.assertEqual(ev["v9QualityRejected"],1)
        self.assertEqual(ev["v9QualityAccepted"],1)
        self.assertEqual(len(ev["scoresAtV7BOS"]),2)
        self.assertIn("75",reject["reasons"][-1])

    def test_never_accept_unregistered_score_threshold(self):
        with self.assertRaisesRegex(ValueError,"UNREGISTERED"):
            gate_v7_with_quality([],{}, {},{},70,{})

if __name__=="__main__":
    unittest.main()
