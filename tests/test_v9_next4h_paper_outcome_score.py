"""V9 only AFTER full target 4H closes: paper result integrity unit tests."""
import copy,json,unittest
from datetime import datetime,timezone

from v9_next4h_paper_outcome_score import (
    verify_prior_forecast,score_one,scoreboard,tally,PAPER_STATUS,
    SYMBOLS,HOUR,FOUR,iso)

T=int(datetime(2026,11,11,tzinfo=timezone.utc).timestamp())


def forecast():
    return {
       "status":PAPER_STATUS,
       "target4HStartUTC":iso(T),
       "target4HEndUTC":iso(T+FOUR),
       "decisionCapturedUTC":iso(T-600),
       "noTargetOpenKnown":True,
       "brokerOrders":False,"productionModified":False,
       "assetForecasts":{
           s:{"direction":"GREEN" if s!="ETHUSDT" else "RED",
              "pGreenUNCALIBRATED":.65 if s!="ETHUSDT" else .30,
              "modelTrainingLabelsSHA256":"x"*64}
           for s in SYMBOLS}
    }


def source(doji=False,missing=False):
    data={}
    for sym in SYMBOLS:
        v=[]
        for i in range(4):
            o=100+i
            c=(100+i+1 if sym=="BTCUSDT" else 100-(i+1)*.5 if sym=="ETHUSDT" else 100-(i+1)*.1)
            if doji and sym=="SOLUSDT":
                o=c=100
            v.append({"t":T+i*HOUR,"o":o,
                      "h":max(o,c)+1,"l":min(o,c)-1,
                      "c":c,"v":100,"bv":50,"tx":200})
        if missing and sym=="SOLUSDT":
            v.pop(2)
        data[sym]=v
    return data


def fetch(data):
    symbols={"BTCUSDT":"BTCUSDT_PERP.A","ETHUSDT":"ETHUSDT_PERP.A",
             "SOLUSDT":"SOLUSDT_PERP.A"}
    def fake(tf,params):
        return json.dumps([{"symbol":symbols[s],"history":data[s]}
                           for s in SYMBOLS]).encode()
    return fake


class V9PaperScorerTests(unittest.TestCase):
    def test_score_own_4h_oc_only_after_close(self):
        x=score_one(T+FOUR+180,forecast(),"key",fetch=fetch(source()))
        self.assertEqual(x["status"],"V9_REAL_PAPER_4H_OWN_COLOR_SCORED")
        self.assertTrue(x["symbols"]["BTCUSDT"]["correct"])
        self.assertTrue(x["symbols"]["ETHUSDT"]["correct"])
        self.assertFalse(x["symbols"]["SOLUSDT"]["correct"])
        self.assertTrue(x["noTradingOrders"])
        self.assertTrue(x["allThreeIndependentSourceBars"])
        self.assertEqual(len(x["forecastCanonicalSHA256"]),64)
        self.assertEqual(x["symbols"]["BTCUSDT"]["target4HOpen"],100)
        self.assertEqual(x["symbols"]["BTCUSDT"]["target4HClose"],104)

    def test_score_before_close_is_forbidden(self):
        with self.assertRaisesRegex(ValueError,"NOT_YET_CLOSED"):
            score_one(T+FOUR+179,forecast(),"key",fetch=fetch(source()))

    def test_missing_final_or_any_one_hour_never_inferred(self):
        with self.assertRaisesRegex(ValueError,"NOT_FOUR_COMPLETE"):
            score_one(T+FOUR+180,forecast(),"key",fetch=fetch(source(missing=True)))

    def test_doji_excluded_not_wrong(self):
        o=score_one(T+FOUR+180,forecast(),"key",fetch=fetch(source(doji=True)))
        self.assertEqual(o["symbols"]["SOLUSDT"]["actual4HOwnOpenCloseColor"],"DOJI")
        self.assertIsNone(o["symbols"]["SOLUSDT"]["correct"])
        score=scoreboard([forecast()],[o])
        self.assertEqual(score["allSymbols"]["SOLUSDT"]["all"]["evaluable"],0)
        self.assertEqual(score["allSymbols"]["SOLUSDT"]["all"]["dojiExcluded"],1)

    def test_rewrite_prior_forecast_fails_hash_audit(self):
        original=forecast()
        scored=score_one(T+FOUR+180,original,"key",fetch=fetch(source()))
        mutated=copy.deepcopy(original)
        mutated["assetForecasts"]["BTCUSDT"]["pGreenUNCALIBRATED"]=.9
        with self.assertRaisesRegex(ValueError,"ORIGINAL_FORECAST_CHANGED"):
            scoreboard([mutated],[scored])

    def test_no_retroactive_outcome_without_prior_forecast(self):
        scored=score_one(T+FOUR+180,forecast(),"key",fetch=fetch(source()))
        with self.assertRaisesRegex(ValueError,"RETROSPECTIVE_RESULT_WITHOUT_PRIOR"):
            scoreboard([],[scored])

    def test_prestart_window_rejects_after_start(self):
        bad=forecast()
        bad["decisionCapturedUTC"]=iso(T+10)
        with self.assertRaisesRegex(ValueError,"NOT_CAPTURED_BEFORE_START"):
            verify_prior_forecast(bad)

    def test_complete_and_pending_forecasts_show_denominators(self):
        p=forecast()
        scored=score_one(T+FOUR+180,p,"key",fetch=fetch(source()))
        later=copy.deepcopy(p)
        later["target4HStartUTC"]=iso(T+FOUR)
        later["target4HEndUTC"]=iso(T+2*FOUR)
        later["decisionCapturedUTC"]=iso(T+FOUR-600)
        score=scoreboard([p,later],[scored])
        self.assertEqual(score["totalPriorTargetForecasts"],2)
        self.assertEqual(score["completedTargetForecasts"],1)
        self.assertEqual(score["pendingOrMissingTargetResults"],1)
        self.assertEqual(score["allSymbols"]["BTCUSDT"]["all"]["evaluable"],1)
        self.assertTrue(score["mustKeepAllForecastsEvenIfWrong"])
        self.assertFalse(score["realOrders"])

    def test_missing_prestart_capture_is_counted_not_hidden(self):
        p=forecast()
        skip=copy.deepcopy(p)
        skip["target4HStartUTC"]=iso(T+2*FOUR)
        skip["target4HEndUTC"]=iso(T+3*FOUR)
        skip["decisionCapturedUTC"]=iso(T+2*FOUR-600)
        results=scoreboard([p,skip],[])
        self.assertEqual(results["expectedFourHourSlotsBetweenFirstAndLast"],3)
        self.assertEqual(results["missingScheduledForecastSlotsBetweenFirstAndLast"],1)
        self.assertEqual(results["captureCoveragePct"],66.67)
        self.assertEqual(results["completedTargetForecasts"],0)

    def test_no_forward_predictions_reports_none_not_100pct(self):
        x=scoreboard([],[])
        for s in SYMBOLS:
            self.assertIsNone(x["allSymbols"][s]["all"]["hitRatePct"])
            self.assertEqual(x["allSymbols"][s]["all"]["evaluable"],0)
            self.assertFalse(x["allSymbols"][s]["all"]["atLeast100NewForecasts"])


if __name__=="__main__":
    unittest.main()
