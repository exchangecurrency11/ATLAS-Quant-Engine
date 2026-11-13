#!/usr/bin/env python3
"""Fixed-rule isolated ETH/SOL older temporal check tests (no network)."""
import unittest

from v92_older_eth_sol_regimes_20261113 import (
    START, END, MONTHS, EXPECTED_1H, decision, check_existing_older_baselines
)


def ctx(btc="bullish", eth="bullish", sol="bullish", ratio=1.5,
        available=True):
    return {
        "available": available,
        "allPricesAlreadyClosed": available,
        "ethAtrPercentVsBTC": ratio,
        "trend4H": {"BTCUSDT": btc, "ETHUSDT": eth, "SOLUSDT": sol},
    }


class FrozenOlderRegimesTests(unittest.TestCase):
    def test_period_and_warmup_frozen(self):
        self.assertEqual(len(MONTHS), 29)
        self.assertEqual(EXPECTED_1H, 21216)
        self.assertEqual((END - START) // 3600, 17544)

    def test_eth_atr_threshold_boundary_and_null(self):
        self.assertTrue(decision("ETHUSDT", "ETH_ATR_LE_1P5_BTC",
                                 "bullish", ctx(ratio=1.5)))
        self.assertFalse(decision("ETHUSDT", "ETH_ATR_LE_1P5_BTC",
                                  "bullish", ctx(ratio=1.50001)))
        self.assertFalse(decision("ETHUSDT", "ETH_ATR_LE_1P5_BTC",
                                  "bullish", ctx(ratio=None)))

    def test_eth_btc_direction_only_and_combination(self):
        self.assertTrue(decision("ETHUSDT", "ETH_BTC_4H_AGREE", "bearish",
                                 ctx(btc="bearish", eth="bullish")))
        self.assertFalse(decision("ETHUSDT", "ETH_BTC_4H_AGREE", "bearish",
                                  ctx(btc="bullish")))
        self.assertTrue(decision(
            "ETHUSDT", "ETH_BTC_4H_AGREE_AND_ATR_LE_1P5", "bullish",
            ctx(ratio=1.5)))
        self.assertFalse(decision(
            "ETHUSDT", "ETH_BTC_4H_AGREE_AND_ATR_LE_1P5", "bullish",
            ctx(ratio=1.50001)))

    def test_sol_requires_both_btc_and_sol_trends(self):
        mode = "V92_BTC_4H_AGREE"
        self.assertTrue(decision("SOLUSDT", mode, "bullish", ctx()))
        self.assertFalse(decision("SOLUSDT", mode, "bullish",
                                  ctx(sol="bearish")))
        self.assertFalse(decision("SOLUSDT", mode, "bullish",
                                  ctx(btc="mixed")))

    def test_missing_causal_4h_context_fails_closed(self):
        for symbol, mode in (
            ("ETHUSDT", "ETH_ATR_LE_1P5_BTC"),
            ("ETHUSDT", "ETH_BTC_4H_AGREE"),
            ("SOLUSDT", "V92_BTC_4H_AGREE"),
        ):
            self.assertFalse(decision(symbol, mode, "bullish",
                                      ctx(available=False)))

    def test_unknown_mode_and_direction_cannot_pass(self):
        with self.assertRaises(ValueError):
            decision("ETHUSDT", "UNKNOWN", "bullish", ctx())
        with self.assertRaises(ValueError):
            decision("SOLUSDT", "V92_BTC_4H_AGREE", "sideways", ctx())

    def test_sealed_prior_baseline_parity_guard(self):
        def score(n, r, stress):
            return {"trades": n, "totalNetR9BpsPerSide": r,
                    "totalNetR25BpsPerSideStress": stress}
        btc = score(10, -4.265784, -7.701252)
        sol1 = score(12, 4.6274, 2.0039)
        sol2 = score(12, 4.6274, 2.0039)
        check_existing_older_baselines(btc, sol1, sol2)
        with self.assertRaises(ValueError):
            check_existing_older_baselines(btc, sol1, score(12, 0, 0))


if __name__ == "__main__":
    unittest.main()
