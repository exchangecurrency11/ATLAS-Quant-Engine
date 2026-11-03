"""Deterministic V7 gates: point-in-time inputs, failure cases and retest."""
import unittest
from signal_quality_v7 import evaluate_bos_quality, evaluate_retest_quality

HOUR = 3600
START = 1735689600


def bars(n=40):
    rows = []
    for i in range(n):
        rows.append({"t": START + i * HOUR, "o": 100., "h": 101.,
                     "l": 99., "c": 100., "v": 100.})
    rows[-1] = {"t": rows[-1]["t"], "o": 100., "h": 103.,
                "l": 99., "c": 102., "v": 250.}
    return rows


def bullish_event(rows, level=101.):
    return {"event": "BOS", "direction": "bullish",
            "at": rows[-1]["t"], "brokenLevel": level}


class QualityV7Tests(unittest.TestCase):
    def test_strong_relative_volume_and_atr_break(self):
        rows = bars()
        decision = evaluate_bos_quality(rows, bullish_event(rows),
                                        {"EMA20": 100., "RSI14": 55.})
        self.assertTrue(decision["passed"])
        self.assertGreater(decision["features"]["relativeVolume20"], 2)
        self.assertGreater(decision["features"]["breakATR"], .2)

    def test_weak_break_rejected(self):
        rows = bars()
        decision = evaluate_bos_quality(rows, bullish_event(rows, 101.95),
                                        {"EMA20": 100., "RSI14": 55.})
        self.assertIn("WEAK_BREAK_ATR", decision["reasons"])

    def test_low_relative_volume_rejected_even_if_prev_candle_low(self):
        rows = bars()
        rows[-1]["v"] = 90.
        decision = evaluate_bos_quality(rows, bullish_event(rows),
                                        {"EMA20": 100., "RSI14": 55.})
        self.assertIn("LOW_RELATIVE_VOLUME", decision["reasons"])

    def test_ema20_overextension_rejected(self):
        rows = bars()
        decision = evaluate_bos_quality(rows, bullish_event(rows),
                                        {"EMA20": 90., "RSI14": 55.})
        self.assertIn("EMA20_OVEREXTENDED", decision["reasons"])

    def test_future_event_not_accepted(self):
        rows = bars()
        bos = bullish_event(rows)
        bos["at"] += HOUR
        decision = evaluate_bos_quality(rows, bos,
                                        {"EMA20": 100., "RSI14": 55.})
        self.assertEqual(decision["reasons"], ["INVALID_OR_FUTURE_BOS"])

    def test_rsi_extreme_is_only_warning(self):
        rows = bars()
        decision = evaluate_bos_quality(rows, bullish_event(rows),
                                        {"EMA20": 100., "RSI14": 85.})
        self.assertTrue(decision["passed"])
        self.assertIn("RSI_EXTREME_NOT_A_HARD_REJECTION",
                      decision["warnings"])

    def test_retest_strength_is_measured_after_retest_close(self):
        rows = bars()
        rows[-1] = {"t": rows[-1]["t"], "o": 100.5, "h": 101.5,
                    "l": 98.5, "c": 99.4, "v": 100.}
        active = {"side": "bearish", "level": 100.}
        strong = evaluate_retest_quality(rows, active, rows[-1])
        self.assertTrue(strong["passed"])
        rows[-1]["c"] = 99.98
        weak = evaluate_retest_quality(rows, active, rows[-1])
        self.assertFalse(weak["passed"])
        self.assertIn("WEAK_RETEST_REJECTION", weak["reasons"])

    def test_retest_future_candle_rejected(self):
        rows = bars()
        later = dict(rows[-1])
        later["t"] += HOUR
        self.assertFalse(evaluate_retest_quality(
            rows, {"side": "bullish", "level": 101}, later)["passed"])


if __name__ == "__main__":
    unittest.main()
