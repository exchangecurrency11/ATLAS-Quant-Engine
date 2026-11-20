import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from zone_quality_forward_shadow_v1 import score_hour, settle_hour, stamp, seconds

CLOSE = "2026-11-21T22:00:00Z"
SHA_A, SHA_B = "a" * 40, "b" * 40


def input_bundle(with_event=True):
    t = seconds(CLOSE)
    structure = {"results": []}
    market = {"results": []}
    for symbol in ("BTCUSDT_PERP.A", "SOLUSDT_PERP.A"):
        structure["results"].append({
            "symbol": symbol, "interval": "1hour", "status": "READY",
            "lastCloseTimeUTC": CLOSE, "candidateOrderBlocks": [],
            "openFVG": [], "liquidity": [],
            "structure": ([{"event": "BOS", "direction": "bullish", "at": t - 3600,
                           "brokenLevel": 99}] if with_event and symbol.startswith("BTC") else [])})
        market["results"].append({"symbol": symbol, "interval": "1hour", "status": "READY",
                                 "closeTimeUTC": CLOSE,
                                 "candle": {"open": 100, "high": 101, "low": 99, "close": 100}})
    history = []
    for i in range(15):
        close = t - (14 - i) * 3600
        row = {"symbol": "BTCUSDT_PERP.A", "interval": "1hour",
               "closeTimeUTC": stamp(close),
               "candle": {"open": 100, "high": 101, "low": 99, "close": 100}}
        history.append({"sha": SHA_A, "publishedUTC": stamp(close + 240),
                        "btc": row, "sol": {**row, "symbol": "SOLUSDT_PERP.A"}})
    params = dict(event_close_utc=CLOSE, observed_at_utc=stamp(t + 720),
                  start_utc="2026-11-21T00:00:00Z",
                  market_sha=SHA_A, market_published_utc=stamp(t + 240),
                  structure_sha=SHA_B, structure_published_utc=stamp(t + 250))
    return market, structure, history, params


class ShadowTest(unittest.TestCase):
    def test_no_event_does_not_invent_prediction(self):
        m, s, h, p = input_bundle(False)
        result = score_hour(m, s, [], **p)
        self.assertEqual(result["status"], "NO_NEW_STRUCTURE_EVENT")
        self.assertEqual(result["events"], [])

    def test_event_and_no_zone(self):
        m, s, h, p = input_bundle()
        result = score_hour(m, s, h, **p)
        self.assertEqual(len(result["events"]), 1)
        event = result["events"][0]
        self.assertEqual(event["eventKind"], "BOS")
        self.assertEqual(event["side"], "LONG")
        self.assertEqual(event["status"], "NO_ZONE")
        self.assertEqual(event["atr14"], 2)
        self.assertEqual(event["zoneCount"], 0)
        self.assertEqual(len(event["atrMarketCommitShas"]), 15)

    def test_reject_late_sources(self):
        m, s, h, p = input_bundle()
        with self.assertRaisesRegex(ValueError, "SOURCE_LATE"):
            score_hour(m, s, h, **{**p, "structure_published_utc": stamp(seconds(CLOSE) + 360)})

    def test_reject_late_observation(self):
        m, s, h, p = input_bundle()
        with self.assertRaisesRegex(ValueError, "LATE_OBSERVATION"):
            score_hour(m, s, h, **{**p, "observed_at_utc": stamp(seconds(CLOSE) + 3601)})

    def test_reject_past_event(self):
        m, s, h, p = input_bundle()
        with self.assertRaisesRegex(ValueError, "PRE_FREEZE"):
            score_hour(m, s, h, **{**p, "start_utc": "2026-11-22T00:00:00Z"})

    def test_reject_missing_atr_hour(self):
        m, s, h, p = input_bundle()
        with self.assertRaisesRegex(ValueError, "ATR_INPUT_GAP"):
            score_hour(m, s, h[:-1], **p)

    def test_reject_future_atr_publication(self):
        m, s, h, p = input_bundle()
        h[3]["publishedUTC"] = stamp(seconds(CLOSE) + 3600)
        with self.assertRaisesRegex(ValueError, "LOOKAHEAD"):
            score_hour(m, s, h, **p)

    def test_no_event_before_future_horizon(self):
        m, s, h, p = input_bundle()
        pred = score_hour(m, s, [], **p)
        with self.assertRaisesRegex(ValueError, "CENSORED"):
            settle_hour(pred, [], settled_at_utc=stamp(seconds(CLOSE) + 12 * 3600 + 900))

    def test_settlement_touch_reversal_and_break(self):
        t = seconds(CLOSE)
        forward = []
        for i in range(1, 13):
            close = t + i * 3600
            candle = {"open": 99, "high": 99.5, "low": 98.5, "close": 99}
            if i == 2:
                candle = {"open": 100, "high": 101.5, "low": 99.5, "close": 101}
            if i == 3:
                candle = {"open": 100, "high": 100, "low": 98.5, "close": 98.9}
            if i == 5:
                candle = {"open": 100, "high": 102.5, "low": 99.5, "close": 102}
            r = {"closeTimeUTC": stamp(close), "candle": candle}
            forward.append({"sha": SHA_A, "publishedUTC": stamp(close + 240),
                            "btc": r, "sol": r})
        prediction = {"recordKind": "PROSPECTIVE_SHADOW_HOURLY",
                      "scoreVersion": "ZQI-V1-PRECALIBRATION-20261120",
                      "eventCloseUTC": CLOSE,
                      "events": [{"symbol": "BTCUSDT_PERP.A", "eventKind": "CHoCH",
                                  "side": "LONG", "status": "CANDIDATES_UNVALIDATED",
                                  "atr14": 2, "topQualityZoneId": "Z001",
                                  "nearestZoneId": "Z001",
                                  "zones": [{"researchZoneId": "Z001",
                                             "range": [100, 101], "evidenceIndex": 70}]}]}
        outcome = settle_hour(prediction, forward,
                              settled_at_utc=stamp(t + 12 * 3600 + 600))
        case = outcome["events"][0]["zoneOutcomes"][0]
        self.assertTrue(case["visited"])
        self.assertEqual(case["firstTouchHour"], 2)
        self.assertTrue(case["reversedWithin3Closed1H"])
        self.assertTrue(case["closedBeyondFarEdge"])

    def test_settlement_censors_partial_series(self):
        m, s, h, p = input_bundle()
        pred = score_hour(m, s, h, **p)
        with self.assertRaisesRegex(ValueError, "CENSORED"):
            settle_hour(pred, [], settled_at_utc=stamp(seconds(CLOSE) + 12 * 3600 + 600))


if __name__ == "__main__":
    unittest.main()
