"""E3 negative controls; no network, no downloads, no orders."""
from __future__ import annotations
from copy import deepcopy
from unittest import TestCase
from unittest.mock import patch

from research.atlas_core_v2 import atlas_core_e3 as m

class E3RawReplayContract(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.oracle,_=m.checked_oracle()
        cls.older,_=m.e2.read_pinned(m.e2.OLDER)
        cls.later,_=m.e2.read_pinned(m.e2.LATER)

    def test_nine_replay_source_git_pins(self):
        source=m.verify_code_pins()
        self.assertEqual(len(source),9)
        self.assertTrue(all(len(x)==64 for x in source.values()))

    def test_mutated_original_engine_fails_before_download(self):
        with patch.dict(m.PINS,{"backtest_retest_long_v4.py":"0"*40}):
            with self.assertRaisesRegex(ValueError,"E3_REPLAY_SOURCE_CODE_MUTATED"):
                m.verify_code_pins()

    def test_159_months_in_sealed_oracle_without_network(self):
        oracle,_=m.checked_oracle()
        counts={p:len(x["sourceManifest"]) for p,x in oracle["periods"].items()}
        self.assertEqual(counts,{"2022_2024":87,"2024_2026":72})
        self.assertEqual(sum(counts.values()),159)

    def test_same_sealed_monthly_manifest_is_valid(self):
        original=self.oracle
        fresh={p:deepcopy(x["sourceManifest"]) for p,x in original["periods"].items()}
        self.assertEqual(m.compare_archive_manifest(original,fresh),159)

    def test_changed_monthly_checksum_is_rejected(self):
        fresh={p:deepcopy(x["sourceManifest"]) for p,x in self.oracle["periods"].items()}
        fresh["2024_2026"][0]["sha256"]="0"*64
        with self.assertRaisesRegex(ValueError,"E3_ARCHIVE_MONTH_SHA256_DRIFT"):
            m.compare_archive_manifest(self.oracle,fresh)

    def test_missing_archive_is_rejected(self):
        fresh={p:deepcopy(x["sourceManifest"]) for p,x in self.oracle["periods"].items()}
        fresh["2024_2026"].pop()
        with self.assertRaisesRegex(ValueError,"E3_ARCHIVE_TOTAL_MISMATCH"):
            m.compare_archive_manifest(self.oracle,fresh)

    def test_duplicate_month_archive_rejected(self):
        fresh={p:deepcopy(x["sourceManifest"]) for p,x in self.oracle["periods"].items()}
        fresh["2024_2026"][0]["month"]=fresh["2024_2026"][1]["month"]
        fresh["2024_2026"][0]["symbol"]=fresh["2024_2026"][1]["symbol"]
        with self.assertRaisesRegex(ValueError,"E3_DUPLICATE_OR_BAD_SHA256"):
            m.compare_archive_manifest(self.oracle,fresh)

    def test_expected_oracle_all_three_coins_six_partitions(self):
        counts={}
        for p in m.e2.PERIODS:
            for c in m.e2.ASSETS:
                x=self.oracle["periods"][p]["assets"][c]["variants"]["BASELINE"]
                counts[(p,c)]=x["trades"]
                self.assertEqual(len(x["tradeEvidence"]),x["trades"])
        self.assertEqual(counts,{
            ("2022_2024","BTCUSDT"):10,("2022_2024","ETHUSDT"):10,
            ("2022_2024","SOLUSDT"):12,("2024_2026","BTCUSDT"):5,
            ("2024_2026","ETHUSDT"):6,("2024_2026","SOLUSDT"):8
        })

    def test_exact_oracle_trade_keys_rejected_when_tampered(self):
        coin="BTCUSDT"
        p="2022_2024"
        primary=deepcopy(self.oracle["periods"][p]["assets"][coin]["variants"]["BASELINE"])
        score=deepcopy(primary)
        score["tradeEvidence"][0]["entryUTC"]="2024-10-10T00:00:00Z"
        with self.assertRaisesRegex(ValueError,"E3_RAW_BAR_TRADE_KEY_MISMATCH"):
            m.compare_raw_to_oracle(coin,p,score,[{}]*primary["trades"],primary)

    def test_misleading_r25_report_rejected(self):
        coin="BTCUSDT"
        p="2022_2024"
        primary=deepcopy(self.oracle["periods"][p]["assets"][coin]["variants"]["BASELINE"])
        score=deepcopy(primary)
        score["netR25Bps"]+=.1
        with self.assertRaisesRegex(ValueError,"E3_SOURCE_METRIC_DISAGREEMENT"):
            m.compare_raw_to_oracle(coin,p,score,[{}]*primary["trades"],primary)
        
    def test_future_start_cutoffs_preserved(self):
        self.assertEqual(m.FREEZE_ETH,"2026-11-14T00:00:00Z")
        self.assertEqual(m.FREEZE_BTC_SOL,"2026-11-15T00:00:00Z")
        self.assertLess(m.v92.epoch(m.v92.PERIODS["2024_2026"]["end"]),
                        m.v92.epoch(m.FREEZE_ETH))

    def test_replay_refuses_bad_worker_count(self):
        for n in (0,7,-2):
            with self.assertRaisesRegex(ValueError,"E3_WORKER_LIMIT"):
                m.run(n)

if __name__=="__main__":
    import unittest
    unittest.main()
