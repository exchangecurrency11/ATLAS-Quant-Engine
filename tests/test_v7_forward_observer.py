"""V7 forward observer regression: reject stale, incomplete or future data."""
import unittest
from datetime import datetime, timezone
from v7_forward_observer import validate_inputs, latest_events, iso, HOUR, PAIRS, TF_SECONDS

TARGET = int(datetime(2026, 11, 3, 16, tzinfo=timezone.utc).timestamp())
NOW = TARGET + 35*60


def good_data():
    all_history = {}
    results = []
    for tf, step in TF_SECONDS.items():
        close = TARGET // step * step
        all_history[tf] = []
        for symbol in PAIRS:
            history = []
            for i in range(255):
                t = close - (255-i)*step
                history.append({"t": t, "o": 100.0, "h": 101.0,
                                "l": 99.0, "c": 100.0, "v": 200.0})
            all_history[tf].append({"symbol": symbol, "history": history})
            results.append({"symbol": symbol, "interval": tf, "status":"READY",
                            "closeTimeUTC": iso(close),
                            "candle": {"close": 100.0}})
    return {
        "ok": True, "provider": "Coinalyze", "market":"Perpetual Futures",
        "checkedAtUTC": iso(TARGET+5*60), "results": results,
    }, all_history


class ForwardObserverTests(unittest.TestCase):
    def test_fresh_closed_data_verifies(self):
        main, histories = good_data()
        parsed = validate_inputs(main, histories, TARGET, NOW)
        self.assertEqual(len(parsed["1hour"]["BTCUSDT_PERP.A"]),255)

    def test_stale_main_snapshot_never_signals(self):
        main, histories = good_data()
        main["checkedAtUTC"] = iso(TARGET-HOUR)
        with self.assertRaisesRegex(ValueError,"before last 1H"):
            validate_inputs(main, histories, TARGET, NOW)

    def test_future_or_stale_close_never_signals(self):
        main, histories = good_data()
        main["results"][0]["closeTimeUTC"] = iso(TARGET-HOUR)
        with self.assertRaisesRegex(ValueError, "snapshot stale"):
            validate_inputs(main, histories, TARGET, NOW)

    def test_divergent_price_fails_closed(self):
        main, histories = good_data()
        histories["daily"][0]["history"][-1]["c"] = 100.5
        with self.assertRaisesRegex(ValueError, "disagree"):
            validate_inputs(main, histories, TARGET, NOW)

    def test_gapped_history_rejected(self):
        main, histories = good_data()
        histories["1hour"][0]["history"][-2]["t"] -= HOUR
        with self.assertRaisesRegex(ValueError, "missing or duplicate"):
            validate_inputs(main, histories, TARGET, NOW)

    def test_only_current_close_events_recorded(self):
        report={"status":"PAPER_BACKTEST_NOT_LIVE",
                "alerts":[{"knownUTC": TARGET-HOUR},{"knownUTC":TARGET}],
                "trades":[{"exitKnownUTC": TARGET-HOUR},
                          {"exitKnownUTC": TARGET}],
                "forwardStateAtLastClose":{"pendingNextOpenPaperEntry":None}}
        fresh=latest_events(report,TARGET)
        self.assertEqual(len(fresh["newWatchAtThisClose"]),1)
        self.assertEqual(len(fresh["paperTradeExitsObservedAtThisClose"]),1)


if __name__ == "__main__":
    unittest.main()
