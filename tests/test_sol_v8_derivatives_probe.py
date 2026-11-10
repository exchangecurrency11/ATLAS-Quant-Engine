"""No-live-order regression tests for independent SOL V8 derivatives probe."""
import unittest

from sol_v8_derivatives_probe import (
    HOUR, SYMBOL, closed_hour_rows, observe, validate_funding, validate_oi,
    validate_volume,
)

TARGET = 1794326400  # 2026-11-10 16:00:00 UTC
NOW = TARGET + 21 * 60


def histories():
    oi = [{"t": TARGET - i * HOUR, "o": 100, "h": 110, "l": 90,
           "c": 100 + 0.5 * (7 - i)} for i in range(7, 0, -1)]
    volumes = [{"t": TARGET - i * HOUR, "v": 100, "bv": 40,
                "o": 100, "h": 101, "l": 99, "c": 100}
               for i in range(7, 0, -1)]
    # Unfinished future bar must never be used even if its values are absurd.
    oi.append({"t": TARGET, "o": 999999, "h": 999999, "l": 1, "c": 999999})
    volumes.append({"t": TARGET, "v": 999999, "bv": 999999})
    return [{"symbol": SYMBOL, "history": oi}], [
        {"symbol": SYMBOL, "history": volumes}
    ]


class DerivativesProbeTests(unittest.TestCase):
    def test_three_sources_pass_quality_only_no_orders(self):
        oi, volumes = histories()
        def fetch(endpoint, params, key):
            self.assertEqual(key, "SAFE_TEST_KEY")
            if endpoint == "open-interest-history":
                self.assertEqual(params["interval"], "1hour")
                self.assertEqual(params["symbols"], SYMBOL)
                return oi, "hash1"
            if endpoint == "ohlcv-history":
                return volumes, "hash2"
            if endpoint == "funding-rate":
                return [{"symbol": SYMBOL, "value": -0.0001, "update": NOW - 60}], "hash3"
            raise AssertionError("Unexpected endpoint")
        result = observe(NOW, "SAFE_TEST_KEY", fetch)
        self.assertEqual(result["status"], "DATA_VALIDATED_RESEARCH_ONLY")
        self.assertFalse(result["brokerOrders"])
        self.assertFalse(result["liveSignalEnabled"])
        self.assertFalse(result["productionSystemModified"])
        self.assertEqual(result["providerBuyVolume"]["providerBuyShare"], .4)
        self.assertFalse(result["providerBuyVolume"]["takerBuySellCrossSourceVerified"])
        self.assertEqual(result["openInterest"]["asOfClosedUTC"],
                         "2026-11-10T16:00:00Z")

    def test_wrong_symbol_never_accepted(self):
        oi, _ = histories()
        oi[0]["symbol"] = "SOLUSDT_SPOT"
        with self.assertRaisesRegex(ValueError, "WRONG_SOL"):
            validate_oi(oi, TARGET)

    def test_unclosed_excluded_and_gap_rejected(self):
        _, vols = histories()
        rows = closed_hour_rows(vols, TARGET)
        self.assertEqual(rows[-1]["t"], TARGET - HOUR)
        vols[0]["history"] = [x for x in vols[0]["history"]
                              if x["t"] != TARGET - 2 * HOUR]
        with self.assertRaisesRegex(ValueError, "GAPPED"):
            validate_volume(vols, TARGET)

    def test_oi_impossible_ohlc_rejected(self):
        oi, _ = histories()
        oi[0]["history"][-2]["h"] = 1
        with self.assertRaisesRegex(ValueError, "IMPOSSIBLE"):
            validate_oi(oi, TARGET)

    def test_buy_share_invalid_rejected(self):
        _, vols = histories()
        vols[0]["history"][-2]["bv"] = 101
        with self.assertRaisesRegex(ValueError, "EXCEEDS"):
            validate_volume(vols, TARGET)

    def test_funding_stale_rejected(self):
        with self.assertRaisesRegex(ValueError, "STALE"):
            validate_funding([{"symbol": SYMBOL, "value": 0.001,
                               "update": NOW - 13 * HOUR}], NOW)

    def test_missing_key_does_not_fetch(self):
        def fail(*args):
            raise AssertionError("Must not request without API key")
        result = observe(NOW, "", fail)
        self.assertEqual(result["status"], "SOURCE_UNAVAILABLE_NO_SIGNAL")
        self.assertNotIn("openInterest", result)

    def test_unauthorized_fails_closed(self):
        def deny(*args):
            raise RuntimeError("COINALYZE_HTTP_401")
        result = observe(NOW, "SECRET_NEVER_LOGGED", deny)
        self.assertEqual(result["status"], "SOURCE_UNAVAILABLE_NO_SIGNAL")
        self.assertEqual(result["rejectionReason"], "COINALYZE_HTTP_401")
        self.assertNotIn("SECRET_NEVER_LOGGED", str(result))

    def test_invalid_observation_time_fails_closed(self):
        r = observe(TARGET + 5 * 60, "KEY", lambda *a: None)
        self.assertEqual(r["status"], "SOURCE_UNAVAILABLE_NO_SIGNAL")
        self.assertIn("OUTSIDE", r["rejectionReason"])


if __name__ == "__main__":
    unittest.main()
