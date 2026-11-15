"""E5-G deterministic no-network safety and 8-stage diagnosis tests."""
from datetime import datetime, timedelta, timezone
import json
import unittest

from research.atlas_core_v9 import hourly_health_e5g as h

NOW=datetime(2026,11,15,21,40,tzinfo=timezone.utc)
COHORT=h.mature_window(NOW)
FOUND={s:{} for s in h.STAGES}
EMPTY_RUNS={s:{} for s in h.STAGES}
SHA="a"*40

def hour(index):
    return h.iso(COHORT[index])

def evidence():
    return ({s:dict(v) for s,v in FOUND.items()},
            {s:dict(v) for s,v in EMPTY_RUNS.items()})

def row_run(event="schedule",status="completed",conclusion="success"):
    return {"id":123456789,"createdAtUTC":hour(0),
            "event":event,"status":status,"conclusion":conclusion}

class E5GHealth(unittest.TestCase):
    def test_eight_only_source_stages_with_fixed_dependencies(self):
        self.assertEqual(len(h.SOURCE_CONFIG),7)
        self.assertEqual(len(h.STAGES),8)
        self.assertEqual(set(h.DEPENDENCIES),set(h.STAGES))
        self.assertEqual(set(h.DEPENDENCIES["E5D"]),
                         {"V92_BTC_SOL","V92_ETH","V9_THREE_ASSET"})

    def test_complete_window_strictly_after_grace(self):
        self.assertEqual(len(COHORT),12)
        self.assertEqual(h.iso(COHORT[-1]),"2026-11-15T20:00:00Z")
        # At 21:15 UTC, 20:00 close is exactly 75m old, not partial
        self.assertEqual(h.iso(h.mature_window(datetime(2026,11,15,21,14,tzinfo=timezone.utc))[-1]),
                         "2026-11-15T19:00:00Z")
        with self.assertRaisesRegex(ValueError,"E5G_INVALID_WINDOW"):
            h.mature_window(NOW,lookback=25)
        with self.assertRaisesRegex(ValueError,"E5G_INVALID_WINDOW"):
            h.mature_window(NOW,lookback=0)

    def test_strict_utc_and_no_naive_clock(self):
        with self.assertRaisesRegex(ValueError,"E5G_TIME_NOT_TZ_AWARE"):
            h.iso(datetime(2026,11,15,12))
        for bad in ("2026-11-15T12:30:00+03:00","2026-11-15 12:30:00",
                    "2026-11-31T00:00:00Z","2026-11-15T12:1:00Z"):
            with self.assertRaises(ValueError):
                h.parse_time(bad)
        self.assertEqual(h.parse_time("2026-11-15T19:30:00Z").hour,19)

    def test_green_workflow_does_not_imply_capture(self):
        files,runs=evidence()
        runs["V7_BTC_SOL"][hour(0)]=[row_run()]
        self.assertEqual(h.diagnosis("V7_BTC_SOL",COHORT[0],files,runs,files),
                         "GREEN_WORKFLOW_BUT_NO_SNAPSHOT")
        files["V7_BTC_SOL"][hour(0)]=SHA
        self.assertEqual(h.diagnosis("V7_BTC_SOL",COHORT[0],files,runs,files),
                         "SNAPSHOT_PRESENT_METADATA_ONLY")

    def test_downstream_upstream_dependency_overrides_green(self):
        files,runs=evidence()
        runs["V92_BTC_SOL"][hour(0)]=[row_run()]
        self.assertEqual(h.diagnosis("V92_BTC_SOL",COHORT[0],files,runs,files),
                         "UPSTREAM_SAME_HOUR_SOURCE_ABSENT")
        for k in ("V7_BTC_SOL","V91_BTC_SOL"):files[k][hour(0)]=SHA
        self.assertEqual(h.diagnosis("V92_BTC_SOL",COHORT[0],files,runs,files),
                         "GREEN_WORKFLOW_BUT_NO_SNAPSHOT")

    def test_failed_cancelled_or_pending_run_are_distinct(self):
        files,runs=evidence()
        for conclusion,want in (("failure","FAILED_WORKFLOW_NO_SNAPSHOT"),
                                ("cancelled","SKIPPED_CANCELLED_OR_NON_SUCCESS_NO_SNAPSHOT"),
                                ("skipped","SKIPPED_CANCELLED_OR_NON_SUCCESS_NO_SNAPSHOT")):
            runs["V7_BTC_SOL"][hour(0)]=[row_run(conclusion=conclusion)]
            self.assertEqual(h.diagnosis("V7_BTC_SOL",COHORT[0],files,runs,files),want)
        runs["V7_BTC_SOL"][hour(0)]=[row_run(status="in_progress",conclusion=None)]
        self.assertEqual(h.diagnosis("V7_BTC_SOL",COHORT[0],files,runs,files),
                         "RUN_NOT_FINISHED_NO_SNAPSHOT")

    def test_zero_run_does_not_claim_scheduler_certainly_skipped(self):
        files,runs=evidence()
        self.assertEqual(h.diagnosis("V7_ETH",COHORT[0],files,runs,files),
                         "NO_WORKFLOW_RUN_SEEN_IN_HOUR")
        self.assertEqual(h.diagnosis("V7_ETH",COHORT[0],files,runs,files,False),
                         "WORKFLOW_HISTORY_UNAVAILABLE")

    def test_e5d_journal_needs_all_three_upstream_sources(self):
        files,runs=evidence()
        for k in ("V92_BTC_SOL","V92_ETH","V9_THREE_ASSET"):
            files[k][hour(0)]=SHA
        runs["E5D"][hour(0)]=[row_run()]
        self.assertEqual(h.diagnosis("E5D",COHORT[0],files,runs,files),
                         "GREEN_WORKFLOW_BUT_NO_SNAPSHOT")
        files["V9_THREE_ASSET"].clear()
        self.assertEqual(h.diagnosis("E5D",COHORT[0],files,runs,files),
                         "UPSTREAM_SAME_HOUR_SOURCE_ABSENT")

    def test_summary_proves_no_trades_and_source_separate_from_journal(self):
        files,runs=evidence()
        for k in h.SOURCE_CONFIG:files[k][hour(0)]=SHA
        report=h.summarize(now=NOW,cohort=COHORT,files=files,run_by_hour=runs,
                           commit_pins={"branch":SHA},
                           tree_pins={x:SHA for x in h.STAGES},run_id="101")
        self.assertEqual(report["allSevenSourcesFilePresentHours"],1)
        self.assertEqual(report["e5dJournalPresentHours"],0)
        self.assertEqual(report["lookbackClosedHours"],12)
        self.assertEqual(report["hourlyMatrix"][0]["statuses"]["E5D"],
                         "NO_WORKFLOW_RUN_SEEN_IN_HOUR")
        self.assertFalse(report["sourceFilePayloadContentValidated"])
        self.assertFalse(report["independentlyExchangeVerifiedOHLCV"])
        self.assertFalse(report["liveEntrySignalValid"])
        self.assertFalse(report["historicalE5FRecoveryCountedAsTimely"])
        self.assertFalse(report["prospectivePerformanceOrTradeCredited"])
        self.assertFalse(report["existingProductionForwardSpecsOrAutomationsChanged"])
        self.assertFalse(report["realOrdersOrAlertsEmitted"])

    def test_fully_present_files_are_not_exchange_verified(self):
        files,runs=evidence()
        for k in h.STAGES:
            files[k]={hour(i):SHA for i in range(12)}
        d=h.summarize(now=NOW,cohort=COHORT,files=files,run_by_hour=runs,
                      commit_pins={},tree_pins={},run_id="200")
        self.assertEqual(d["allSevenSourcesFilePresentHours"],12)
        self.assertEqual(d["e5dJournalPresentHours"],12)
        self.assertEqual(d["status"],"ALL_12_SOURCE_HOURS_FILE_PRESENT_METADATA_ONLY")
        self.assertFalse(d["sourceFilePayloadContentValidated"])

    def test_unverified_run_id_disallowed(self):
        files,runs=evidence()
        with self.assertRaisesRegex(ValueError,"E5G_BAD_FIXED_WINDOW"):
            h.summarize(now=NOW,cohort=COHORT,files=files,run_by_hour=runs,
                        commit_pins={},tree_pins={},run_id="../false")

    def test_missing_source_in_summary_includes_dependency_list(self):
        files,runs=evidence()
        d=h.summarize(now=NOW,cohort=COHORT,files=files,run_by_hour=runs,
                      commit_pins={},tree_pins={},run_id="200")
        self.assertEqual(len(d["hourlyMatrix"]),12)
        self.assertEqual(d["sourceHealthStatusCounts"]["V92_BTC_SOL"]
                         ["UPSTREAM_SAME_HOUR_SOURCE_ABSENT"],12)
        self.assertEqual(d["hourlyMatrix"][0]["missingDependencies"]["V92_BTC_SOL"],
                         ["V7_BTC_SOL","V91_BTC_SOL"])

    def test_regular_git_hour_identifiers(self):
        def meta(name,sha=SHA,mode="100644",kind="blob"):
            return {"path":name,"sha":sha,"mode":mode,"type":kind}
        d={"entries":[meta("2026-11-15T17-00Z.json"),meta("2026-11-15T17-00Z.md")]}
        self.assertEqual(h.regular_entries(d,True),{"2026-11-15T17:00:00Z":SHA})
        with self.assertRaisesRegex(ValueError,"E5G_NON_HOURLY"):
            h.regular_entries(d,False)
        with self.assertRaisesRegex(ValueError,"E5G_NON_HOURLY"):
            h.regular_entries({"entries":[meta("2026-11-15T17-00Z.json",mode="100755")]})

    def test_malicious_remote_url_rejected_before_network(self):
        for url in ("http://api.github.com/repos/x","https://private.invalid/",
                    "https://api.github.com/repos/evil/other/branches/main",
                    "https://api.github.com/repos/"+h.REPO+"/issues",
                    "https://api.github.com:8443/repos/"+h.REPO+"/branches/main"):
            with self.assertRaisesRegex(ValueError,"E5G_"):
                h.fetch_github(url)

    def test_branch_and_tree_sha_not_invented(self):
        with self.assertRaisesRegex(ValueError,"E5G_UNAPPROVED"):
            h.branch_pin("main",fetch=lambda url:b"{}")
        with self.assertRaisesRegex(ValueError,"E5G_UNTRUSTED"):
            h.git_tree("wrong",fetch=lambda url:b"{}")
        with self.assertRaisesRegex(ValueError,"E5G_GIT_BRANCH_NOT_PINNED"):
            h.branch_pin(h.E5D_BRANCH,fetch=lambda url:b'{"commit":{"sha":"bad"}}')

    def test_git_tree_truncation_and_non_blob_sha_fail_closed(self):
        with self.assertRaisesRegex(ValueError,"TRUNCATED"):
            h.git_tree(SHA,fetch=lambda url:b'{"truncated":true,"tree":[]}')
        doc={"truncated":False,"tree":[{"path":"hack","type":"blob","sha":"nope"}]}
        with self.assertRaisesRegex(ValueError,"E5G_UNVERIFIED"):
            h.git_tree(SHA,fetch=lambda url:json.dumps(doc).encode())

    def test_workflow_list_url_filters_branch_and_time_and_does_not_count_green_as_snapshot(self):
        called=[]
        def fetch(url):
            called.append(url)
            return json.dumps({"total_count":1,"workflow_runs":[{
                "id":123,"created_at":"2026-11-15T20:10:00Z",
                "head_branch":"main","event":"schedule","status":"completed",
                "conclusion":"success"}]}).encode()
        d=h.workflow_runs("v7-hourly-trigger.yml",COHORT[0],NOW,fetch=fetch)
        self.assertIn("branch=main",called[0])
        self.assertIn("created=",called[0])
        self.assertIn("2026-11-15T20:00:00Z",d)
        self.assertEqual(d["2026-11-15T20:00:00Z"][0]["conclusion"],"success")

    def test_history_not_assumed_complete_if_over_100(self):
        with self.assertRaisesRegex(ValueError,"PAGINATION_TRUNCATED"):
            h.workflow_runs("v7-hourly-trigger.yml",COHORT[0],NOW,
                 fetch=lambda url:json.dumps({"total_count":101,"workflow_runs":[]}).encode())

    def test_workflow_branch_drift_fails_closed(self):
        def payload(url):
            return json.dumps({"total_count":1,"workflow_runs":[{
              "id":1,"created_at":"2026-11-15T20:10:00Z","head_branch":"research/other",
              "event":"schedule","status":"completed","conclusion":"success"}]}).encode()
        with self.assertRaisesRegex(ValueError,"BRANCH_NOT_MAIN"):
            h.workflow_runs("v7-hourly-trigger.yml",COHORT[0],NOW,fetch=payload)

if __name__=="__main__":unittest.main()
