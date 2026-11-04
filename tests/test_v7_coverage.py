"""V7 coverage is a bookkeeping audit, never a made-up forward signal."""
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from v7_coverage import audit_coverage, file_stamp, parse_utc, utc_text

UTC = timezone.utc
T0 = datetime(2026, 11, 3, 16, tzinfo=UTC)


class CoverageTests(unittest.TestCase):
    def test_missing_hours_marked_once_and_never_counted_as_zero_signal(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            snapshots = root / "snapshots"
            coverage = root / "coverage"
            snapshots.mkdir()
            (snapshots / (file_stamp(T0) + ".json")).write_text(
                json.dumps({
                    "status": "VERIFIED_PAPER_OBSERVATION",
                    "targetClosed1HUTC": utc_text(T0),
                }), encoding="utf-8")
            target = T0 + timedelta(hours=4)
            first = audit_coverage(
                snapshots, coverage, target=target,
                discovered_at=target + timedelta(minutes=25),
                start=T0)
            self.assertEqual(first["expectedPriorHours"], 4)
            self.assertEqual(first["verifiedSnapshots"], 1)
            self.assertEqual(first["missingHourMarkers"], 3)
            self.assertEqual(first["newMissingMarkers"], 3)
            self.assertFalse((coverage / (file_stamp(target) + ".json")).exists())
            marker = json.loads(
                (coverage / (file_stamp(T0 + timedelta(hours=1)) + ".json")).read_text())
            self.assertEqual(marker["status"], "MISSED_OBSERVATION")
            self.assertFalse(marker["paperForwardObservation"])
            self.assertTrue(marker["notBackfilled"])
            second = audit_coverage(
                snapshots, coverage, target=target,
                discovered_at=target + timedelta(minutes=40), start=T0)
            self.assertEqual(second["newMissingMarkers"], 0)

    def test_explicit_source_failure_counts_as_recorded_not_missing(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            snapshots = root / "snapshots"
            snapshots.mkdir()
            (snapshots / (file_stamp(T0) + ".json")).write_text(
                json.dumps({
                    "status": "DATA_REJECTED",
                    "targetClosed1HUTC": utc_text(T0),
                }), encoding="utf-8")
            output = audit_coverage(
                snapshots, root / "coverage",
                target=T0+timedelta(hours=1),
                discovered_at=T0+timedelta(hours=1, minutes=20),
                start=T0)
            self.assertEqual(output["rejectedOrFetchFailedSnapshots"], 1)
            self.assertEqual(output["missingHourMarkers"], 0)

    def test_does_not_trust_invalid_snapshot_timestamp(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            snapshots = root / "snapshots"
            snapshots.mkdir()
            (snapshots / (file_stamp(T0) + ".json")).write_text(
                json.dumps({
                    "status": "VERIFIED_PAPER_OBSERVATION",
                    "targetClosed1HUTC": utc_text(T0 + timedelta(hours=1)),
                }), encoding="utf-8")
            output = audit_coverage(
                snapshots, root / "coverage",
                target=T0+timedelta(hours=1),
                discovered_at=T0+timedelta(hours=1, minutes=30),
                start=T0)
            self.assertEqual(output["invalidSnapshots"], 1)
            self.assertEqual(output["verifiedSnapshots"], 0)

    def test_no_future_target(self):
        with self.assertRaisesRegex(ValueError, "Hour target"):
            parse_utc("2026-11-04T23:15:00Z")
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError, "before experiment"):
                audit_coverage(Path(temp), Path(temp)/"x",
                               target=T0-timedelta(hours=1),
                               discovered_at=T0, start=T0)


if __name__ == "__main__":
    unittest.main()
