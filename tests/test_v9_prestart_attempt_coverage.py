"""V9 prestart opportunity denominator remains accurate even with ZERO forecasts."""
import copy,unittest
from test_v9_next4h_paper_outcome_score import forecast,T
from v9_prestart_attempt_coverage import coverage,FOUR,iso


class V9CaptureCoverageTests(unittest.TestCase):
    def test_no_forecasts_does_not_mean_perfect_reliability(self):
        x=coverage([],T+3*FOUR+100,deploy=T)
        self.assertEqual(x["expectedAlreadyStarted4HTargets"],4)
        self.assertEqual(x["validForecastsCommittedBeforeOpenPerOriginalFile"],0)
        self.assertEqual(x["missed4HBeforeStartPredictionSlots"],4)
        self.assertEqual(x["captureCoveragePct"],0.)
        self.assertTrue(x["missingAreFailuresNotAbstentions"])

    def test_single_saved_forecast_preserves_all_unrecorded_opportunities(self):
        f=forecast()
        x=coverage([f],T+3*FOUR+100,deploy=T)
        self.assertEqual(x["expectedAlreadyStarted4HTargets"],4)
        self.assertEqual(x["validForecastsCommittedBeforeOpenPerOriginalFile"],1)
        self.assertEqual(x["missed4HBeforeStartPredictionSlots"],3)
        self.assertEqual(x["captureCoveragePct"],25.)
        self.assertEqual(x["capturedTargetStartUTC"],[iso(T)])

    def test_already_future_record_does_not_count_as_closed_opportunity(self):
        f=forecast()
        f["target4HStartUTC"]=iso(T+FOUR)
        f["target4HEndUTC"]=iso(T+2*FOUR)
        f["decisionCapturedUTC"]=iso(T+FOUR-600)
        x=coverage([f],T+100,deploy=T)
        self.assertEqual(x["validForecastsCommittedBeforeOpenPerOriginalFile"],0)
        self.assertEqual(x["forecastedTargetStartsNotYetBegunUTC"],[iso(T+FOUR)])
        self.assertEqual(x["missed4HBeforeStartPredictionSlots"],1)

    def test_invalid_late_snapshot_is_not_treated_as_prospective(self):
        f=forecast()
        f["decisionCapturedUTC"]=iso(T+1)
        with self.assertRaisesRegex(ValueError,"NOT_CAPTURED_BEFORE_START"):
            coverage([f],T+FOUR,deploy=T)

    def test_same_target_cannot_overcount(self):
        f=forecast()
        with self.assertRaisesRegex(ValueError,"DUPLICATE_FORECAST_FOR_4H"):
            coverage([f,copy.deepcopy(f)],T+FOUR,deploy=T)


if __name__=="__main__":
    unittest.main()
