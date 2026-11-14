"""E5-D append-only research runner: 30 negative and operational controls.

Only synthetic mocks and TemporaryDirectory used in tests.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime,timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
import json

from research.atlas_core_v7 import hourly_cold_observer_e5c as cold
from research.atlas_core_v7 import test_hourly_cold_observer_e5c as fixture
from research.atlas_core_v8 import hourly_journal_e5d as j

NOW="2026-11-14T21:35:00Z"
START="2026-11-14T20:00:00Z"

def clock(iso):
    return cold.strict_utc(iso)

def body(d):
    return (json.dumps(d,sort_keys=True,indent=2)+"\n").encode()

def tree_mock_fetch(*, continuous=True, missing_hour=False, truncated=False):
    source=fixture.fake_fetcher(continuous=continuous)
    SHA_A=fixture.SHA_V92
    SHA_B=fixture.SHA_V9
    # Non-recursive Git trees; avoids capped /contents directory listings.
    trees={
        SHA_A:[
            {"path":"forward","type":"tree","sha":"c"*40}
        ],
        "c"*40:[
            {"path":"v92_prospective_selected","type":"tree","sha":"d"*40},
            {"path":"v92_prospective_eth","type":"tree","sha":"e"*40}
        ],
        "d"*40:[{"path":"hourly","type":"tree","sha":"f"*40}],
        "e"*40:[{"path":"hourly","type":"tree","sha":"0"*40}],
    }
    for folder,key in ((cold.BTC_SOL_DIR,"f"*40),(cold.ETH_DIR,"0"*40)):
        files=json.loads(source(cold.API+"/contents/"+folder+"?ref="+SHA_A))
        entries=[]
        for v in files:
            if missing_hour and v["name"]=="2026-11-14T19-00Z.json":
                continue
            entries.append({"path":v["name"],"sha":v["sha"],
                            "mode":"100644","type":"blob","size":1234})
        trees[key]=entries
    def fetch(url):
        if url.startswith(cold.API+"/git/trees/"):
            sha=url[len(cold.API+"/git/trees/"):]
            if sha not in trees:
                raise AssertionError("E5D unexpected tree SHA: "+sha)
            return body({
                "sha":sha,"url":url,"tree":trees[sha],
                "truncated":bool(truncated and sha=="f"*40)})
        return source(url)
    return fetch

def real_synthetic_report():
    return cold.audit(fetch=fixture.fake_fetcher(),now_utc=NOW)

class TreeSourceSafety(TestCase):
    def test_multi_level_git_tree_yields_closed_hour(self):
        records=j.fetch_pinned_tree(fixture.SHA_V92,cold.BTC_SOL_DIR,
                                    fetch=tree_mock_fetch())
        self.assertIn("2026-11-14T21-00Z",records)
        self.assertEqual(len(records),4)
        self.assertEqual(records["2026-11-14T21-00Z"]["gitBlobSHA1"].__len__(),40)

    def test_e5c_original_source_validators_run_over_git_trees(self):
        audit=j.observed_hourly_audit(fetch=tree_mock_fetch(),now_utc=NOW)
        self.assertEqual(audit["status"],"SOURCE_WITNESSES_CHECKED_OBSERVATION_ONLY")
        self.assertEqual(audit["consecutiveHourCoverage"]["verifiedContentsWithGitBlobSHA1"],8)
        self.assertEqual(audit["actualNewLiveOpportunityCount"],0)

    def test_old_tree_with_hole_does_not_backfill(self):
        audit=j.observed_hourly_audit(
            fetch=tree_mock_fetch(missing_hour=True),now_utc=NOW)
        self.assertFalse(audit["consecutiveHourCoverage"]["matchedAcrossBothSources"])
        self.assertEqual(audit["actualNewLiveOpportunityCount"],0)

    def test_truncated_tree_fails(self):
        with self.assertRaisesRegex(ValueError,"E5D_HOURLY_TREE_TRUNCATED"):
            j.observed_hourly_audit(fetch=tree_mock_fetch(truncated=True),now_utc=NOW)

    def test_tree_cannot_fetch_unknown_folder(self):
        with self.assertRaisesRegex(ValueError,"E5D_UNAPPROVED_SOURCE_FOLDER"):
            j.fetch_pinned_tree(fixture.SHA_V92,"forward/private",fetch=tree_mock_fetch())

    def test_tree_cannot_use_moving_branch_name(self):
        with self.assertRaisesRegex(ValueError,"E5D_UNPINNED_SOURCE_COMMIT"):
            j.fetch_pinned_tree("main",cold.BTC_SOL_DIR,fetch=tree_mock_fetch())

    def test_tree_missing_source_folder_rejected(self):
        f=tree_mock_fetch()
        def no_folder(url):
            if url==cold.API+"/git/trees/"+fixture.SHA_V92:
                return body({"tree":[{"path":"other","type":"tree","sha":"c"*40}],
                             "truncated":False})
            return f(url)
        with self.assertRaisesRegex(ValueError,"E5D_REQUIRED_SOURCE_TREE_NOT_FOUND"):
            j.fetch_pinned_tree(fixture.SHA_V92,cold.BTC_SOL_DIR,fetch=no_folder)

    def test_tree_symlink_denied(self):
        f=tree_mock_fetch()
        def symlink(url):
            result=f(url)
            if url==cold.API+"/git/trees/"+"f"*40:
                obj=json.loads(result)
                obj["tree"][0]["mode"]="120000"
                return body(obj)
            return result
        with self.assertRaisesRegex(ValueError,"E5D_HOURLY_MEMBER_NOT_A_FILE"):
            j.fetch_pinned_tree(fixture.SHA_V92,cold.BTC_SOL_DIR,fetch=symlink)

    def test_tree_file_which_forges_source_blob_is_rejected(self):
        original=tree_mock_fetch()
        def tamper(url):
            b=original(url)
            if url.endswith("/2026-11-14T21-00Z.json") and cold.BTC_SOL_DIR in url:
                return b+b" "
            return b
        with self.assertRaisesRegex(ValueError,"E5C_GIT_SOURCE_BLOB_SHA1_MISMATCH"):
            j.observed_hourly_audit(fetch=tamper,now_utc=NOW)

class JournalContract(TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)/"forward/atlas_core_e5d_hourly"
        self.source=real_synthetic_report()

    def write(self,src=None,when=NOW,runid="123456",runattempt="1",
              activation=START,write=True):
        return j.create_first_seen(src or self.source,
                  now_epoch=clock(when),run_id=runid,run_attempt=runattempt,
                  activation_epoch=clock(activation),root=self.root,
                  write=write)

    def test_first_write_stores_attempt_and_observation_separately(self):
        result=self.write()
        self.assertTrue(result["newObservation"])
        self.assertFalse(result["reusedImmutableObservation"])
        self.assertTrue(Path(result["checkpointPath"]).exists())
        self.assertTrue(Path(result["observationPath"]).exists())
        receipt=json.loads(Path(result["observationPath"]).read_text())
        self.assertEqual(receipt["sourceClosedHourUTC"],fixture.CLOSE)
        self.assertEqual(receipt["evidenceRunId"],"123456")
        self.assertTrue(receipt["notAnExchangeFill"])
        self.assertTrue(receipt["noUserAlerts"])
        self.assertTrue(receipt["notAnEntryTimeTradeAlert"])
        self.assertEqual(receipt["checkedRecentHourlyFileContents"],8)

    def test_repeated_source_hour_immutable_snapshot_reused(self):
        first=self.write()
        original=Path(first["observationPath"]).read_bytes()
        newer=self.write(when="2026-11-14T21:40:00Z",runid="123457")
        self.assertFalse(newer["newObservation"])
        self.assertTrue(newer["reusedImmutableObservation"])
        self.assertEqual(Path(first["observationPath"]).read_bytes(),original)
        self.assertTrue(Path(newer["checkpointPath"]).exists())

    def test_same_run_replay_different_payload_is_rejected(self):
        self.write()
        with self.assertRaisesRegex(ValueError,"E5D_IMMUTABLE_JOURNAL_ENTRY_DRIFT"):
            self.write()

    def test_precise_same_result_under_no_write(self):
        out=self.write(write=False)
        self.assertTrue(out["newObservation"])
        self.assertFalse(Path(out["checkpointPath"]).exists())
        self.assertFalse(Path(out["observationPath"]).exists())

    def test_no_prewarmup_forward_credit(self):
        report=self.write(activation="2026-11-15T00:00:00Z")
        self.assertEqual(report["status"],"SOURCE_HOUR_PRE_FIRST_SEEN_ACTIVATION_NOT_CREDITED")
        self.assertFalse(report["newObservation"])
        self.assertIsNone(report["observationPath"])
        self.assertTrue(Path(report["checkpointPath"]).exists())

    def test_stale_hour_not_credited_after_new_activation(self):
        out=self.write(when="2026-11-15T05:00:00Z",activation=START)
        self.assertEqual(out["status"],"SOURCE_HOUR_STALE_OVER_90MIN_NOT_CREDITED")
        self.assertFalse(out["newObservation"])

    def test_source_hours_mismatch_records_only_attempt(self):
        src={"mode":cold.MODE,"status":"SOURCE_HOURS_DISAGREE_FAIL_CLOSED",
             "actualNewLiveOpportunityCount":0,
             "actionSafety":cold.REJECTED_LIVE_ACTIONS,
             "sourceGitCommits":{"V92":fixture.SHA_V92,"V9":fixture.SHA_V9}}
        got=self.write(src=src)
        self.assertEqual(got["status"],"SOURCE_HOURS_MISMATCH_FAIL_CLOSED")
        self.assertIsNone(got["observationPath"])
        self.assertTrue(Path(got["checkpointPath"]).exists())

    def test_false_actual_live_signal_rejected(self):
        src=deepcopy(self.source)
        src["actualNewLiveOpportunityCount"]=1
        with self.assertRaisesRegex(ValueError,"E5D_HOURLY_SOURCE_ALLEGES_LIVE_TRADE"):
            self.write(src=src)

    def test_trade_permission_flag_tamper_rejected(self):
        src=deepcopy(self.source)
        src["actionSafety"]["noNewTradingOrders"]=False
        with self.assertRaisesRegex(ValueError,"E5D_SOURCE_ACTION_SAFETY_GUARD_DRIFT"):
            self.write(src=src)

    def test_false_forward_trade_count_rejected(self):
        src=deepcopy(self.source)
        src["newForwardTradesAccrued"]=1
        with self.assertRaisesRegex(ValueError,"E5D_SOURCE_FALSE_READY_OR_CREDIT"):
            self.write(src=src)

    def test_true_real_account_access_claim_rejected(self):
        src=deepcopy(self.source)
        src["realAccountExposureAvailable"]=True
        with self.assertRaisesRegex(ValueError,"E5D_SOURCE_FALSE_READY_OR_CREDIT"):
            self.write(src=src)

    def test_source_future_capture_rejected(self):
        src=deepcopy(self.source)
        src["hourlyObservationTimeliness"]["latestSourceCaptureUTC"] = "2026-11-15T12:00:00Z"
        with self.assertRaisesRegex(ValueError,"E5D_FUTURE_SOURCE_STATE"):
            self.write(src=src)

    def test_bad_run_id_rejected(self):
        with self.assertRaisesRegex(ValueError,"E5D_INVALID_GITHUB_RUN_ID_OR_ATTEMPT"):
            self.write(runid="main")
        with self.assertRaisesRegex(ValueError,"E5D_INVALID_GITHUB_RUN_ID_OR_ATTEMPT"):
            self.write(runattempt="1_2")

    def test_existing_observation_tamper_not_overwritten(self):
        first=self.write()
        path=Path(first["observationPath"])
        obj=json.loads(path.read_text())
        obj["notAnExchangeFill"]=False
        path.write_bytes(body(obj))
        with self.assertRaisesRegex(ValueError,"E5D_EXISTING_SOURCE_OBSERVATION_DRIFT"):
            self.write(when="2026-11-14T21:40:00Z",runid="123457")

    def test_consecutive_four_hour_coverage_required_even_when_report_says_yes(self):
        src=deepcopy(self.source)
        src["consecutiveHourCoverage"]["verifiedContentsWithGitBlobSHA1"]=2
        with self.assertRaisesRegex(ValueError,"E5D_CONSECUTIVE_HOURS_NOT_CONTENT_VERIFIED"):
            self.write(src=src)

    def test_source_sha_missing_rejected(self):
        src=deepcopy(self.source)
        del src["sourceFileSHA256"]["ETH_V92"]
        with self.assertRaisesRegex(ValueError,"E5D_NOT_THREE_PUBLISHER_DOCUMENTS"):
            self.write(src=src)

    def test_gaps_count_from_previous_immutable_journal_only(self):
        first=self.write()
        src=deepcopy(self.source)
        new_t=clock("2026-11-14T23:00:00Z")
        src["hourlyObservationTimeliness"]["latestClosedCandleUTC"]="2026-11-14T23:00:00Z"
        src["hourlyObservationTimeliness"]["latestSourceCaptureUTC"]="2026-11-14T23:20:00Z"
        src["hourlyObservationTimeliness"]["lastSourceCaptureLagMinutes"]=20
        src["hourlyObservationTimeliness"]["observedMinutesAfterClosedHour"]=25
        src["sourceAssetPaperObservations"]=[
            {**x,"sourceClosedHourUTC":"2026-11-14T23:00:00Z"}
            for x in src["sourceAssetPaperObservations"]]
        gap=self.write(src=src,when="2026-11-14T23:25:00Z",runid="123458")
        self.assertTrue(gap["newObservation"])
        self.assertEqual(gap["metadata"]["missingSourceHoursSincePreviousRecorded"],1)

    def test_nonmonotonic_observation_hours_rejected(self):
        self.write()
        src=deepcopy(self.source)
        src["hourlyObservationTimeliness"]["latestClosedCandleUTC"]="2026-11-14T20:00:00Z"
        src["hourlyObservationTimeliness"]["latestSourceCaptureUTC"]="2026-11-14T20:20:00Z"
        src["hourlyObservationTimeliness"]["lastSourceCaptureLagMinutes"]=20
        src["hourlyObservationTimeliness"]["observedMinutesAfterClosedHour"]=25
        # Seen later but at a past source hour; no retroactive fill.
        with self.assertRaisesRegex(ValueError,"E5D_NONMONOTONIC_FIRST_SEEN_COHORT"):
            self.write(src=src,when="2026-11-14T20:25:00Z",runid="123459")

    def test_attempt_checkpoint_contains_run_id(self):
        out=self.write()
        doc=json.loads(Path(out["checkpointPath"]).read_text())
        self.assertEqual(doc["runId"],"123456")
        self.assertTrue(doc["notARealTradingSignal"])
        self.assertTrue(doc["noSourceDataBackfilled"])

    def test_no_standalone_user_trade_card_in_observation(self):
        out=self.write()
        result=json.loads(Path(out["observationPath"]).read_text())
        self.assertNotIn("BUY",json.dumps(result))
        self.assertNotIn("tradePermission",result)
        self.assertNotIn("realExchangeFill",result)
        self.assertTrue(result["userMustNotTradeFromThisRecord"])

    def test_archive_path_is_day_partitioned_not_1000_filenames_per_dir(self):
        r=self.write()
        self.assertIn("observations/2026-11-14/21-00Z.json",r["observationPath"])
        self.assertIn("attempts/2026-11-14/21-35-00_run123456_try1.json",r["checkpointPath"])

class RunnerContract(TestCase):

    def test_end_to_end_produce_testmode_does_not_write(self):
        with TemporaryDirectory() as temp:
            root=Path(temp)/"forward/atlas_core_e5d_hourly"
            doc=j.produce(now_utc=NOW,run_id="1234",run_attempt="1",
                root=root,fetch=tree_mock_fetch(),write=False,
                activation_utc=START)
            self.assertEqual(doc["mode"],j.MODE)
            self.assertEqual(doc["newLiveSignalCount"],0)
            self.assertTrue(doc["output"]["newObservation"])
            self.assertFalse(root.exists())

    def test_end_to_end_produce_writes_only_research_journal(self):
        with TemporaryDirectory() as temp:
            root=Path(temp)/"forward/atlas_core_e5d_hourly"
            doc=j.produce(now_utc=NOW,run_id="2345",run_attempt="1",
                root=root,fetch=tree_mock_fetch(),write=True,
                activation_utc=START)
            self.assertTrue(Path(doc["output"]["checkpointPath"]).exists())
            self.assertTrue(Path(doc["output"]["observationPath"]).exists())
            self.assertFalse(doc["automaticOrdersOrAlertsSent"])
            self.assertFalse(doc["originalCryptoAutomationsChanged"])

    def test_source_does_not_claim_funding_mark_as_observed(self):
        r=j.produce(now_utc=NOW,run_id="3456",
                    root=Path("/tmp/unwritten-research-e5d-never"),
                    fetch=tree_mock_fetch(),write=False,
                    activation_utc=START)
        self.assertIn("no orderbook or actual spread",r["limitations"][-1])

if __name__=="__main__":
    import unittest
    unittest.main()
