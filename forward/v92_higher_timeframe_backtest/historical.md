# V9.2 1D / 3D retest context backtest

**Historical paper research only. Not live results.**
Period: 2024-10-01T00:00:00Z to 2026-10-01T00:00:00Z (exclusive).
The original strategy already uses 1D direction at BOS. This experiment separately re-checks 1D and derived 3D trend at the retest close.
3D candles are aggregated from three completed daily candles on a fixed UTC epoch grid; this is not proven exchange-native 3D parity.
EMA20/EMA50 alignment is the only new trend rule. Mixed direction blocks a confirmation variant; insufficient warmup passes and is separately counted.
Same source and unchanged V7/V9.1 BOS, retest, next-open fill, stop/TP and costs. Previously inspected history is not independent.

| Coin | Baseline | Variant | Trades | Wins | Win % | Net R | Stress R | Δ vs base | Δ vs candle |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| BTCUSDT | V7_ORIGINAL | BASELINE | 9 | 5 | 55.56 | 3.6636 | 1.3290 | 0.0000 | 0.0000 |
| BTCUSDT | V7_ORIGINAL | CANDLE_ONLY | 9 | 5 | 55.56 | 3.6636 | 1.3290 | 0.0000 | 0.0000 |
| BTCUSDT | V7_ORIGINAL | DAILY_RETEST_CONFIRM | 9 | 5 | 55.56 | 3.6636 | 1.3290 | 0.0000 | 0.0000 |
| BTCUSDT | V7_ORIGINAL | 3D_RETEST_CONFIRM | 6 | 3 | 50.0 | 1.2760 | 0.0301 | -2.3876 | -2.3876 |
| BTCUSDT | V7_ORIGINAL | DAILY_AND_3D_RETEST_CONFIRM | 6 | 3 | 50.0 | 1.2760 | 0.0301 | -2.3876 | -2.3876 |
| BTCUSDT | V7_ORIGINAL | CANDLE_PLUS_3D | 6 | 3 | 50.0 | 1.2760 | 0.0301 | -2.3876 | -2.3876 |
| BTCUSDT | V91_RETEST_MAX4H | BASELINE | 5 | 3 | 60.0 | 4.1010 | 2.8146 | 0.0000 | 0.0000 |
| BTCUSDT | V91_RETEST_MAX4H | CANDLE_ONLY | 5 | 3 | 60.0 | 4.1010 | 2.8146 | 0.0000 | 0.0000 |
| BTCUSDT | V91_RETEST_MAX4H | DAILY_RETEST_CONFIRM | 5 | 3 | 60.0 | 4.1010 | 2.8146 | 0.0000 | 0.0000 |
| BTCUSDT | V91_RETEST_MAX4H | 3D_RETEST_CONFIRM | 4 | 2 | 50.0 | 2.3721 | 1.5676 | -1.7289 | -1.7289 |
| BTCUSDT | V91_RETEST_MAX4H | DAILY_AND_3D_RETEST_CONFIRM | 4 | 2 | 50.0 | 2.3721 | 1.5676 | -1.7289 | -1.7289 |
| BTCUSDT | V91_RETEST_MAX4H | CANDLE_PLUS_3D | 4 | 2 | 50.0 | 2.3721 | 1.5676 | -1.7289 | -1.7289 |
| SOLUSDT | V7_ORIGINAL | BASELINE | 11 | 6 | 54.55 | 2.8610 | 0.6026 | 0.0000 | -1.1447 |
| SOLUSDT | V7_ORIGINAL | CANDLE_ONLY | 10 | 6 | 60.0 | 4.0057 | 2.0046 | 1.1447 | 0.0000 |
| SOLUSDT | V7_ORIGINAL | DAILY_RETEST_CONFIRM | 11 | 6 | 54.55 | 2.8610 | 0.6026 | 0.0000 | -1.1447 |
| SOLUSDT | V7_ORIGINAL | 3D_RETEST_CONFIRM | 9 | 5 | 55.56 | 2.0602 | 0.1559 | -0.8008 | -1.9455 |
| SOLUSDT | V7_ORIGINAL | DAILY_AND_3D_RETEST_CONFIRM | 9 | 5 | 55.56 | 2.0602 | 0.1559 | -0.8008 | -1.9455 |
| SOLUSDT | V7_ORIGINAL | CANDLE_PLUS_3D | 8 | 5 | 62.5 | 3.2049 | 1.5579 | 0.3439 | -0.8008 |
| SOLUSDT | V91_RETEST_MAX4H | BASELINE | 9 | 5 | 55.56 | 3.1159 | 1.0080 | 0.0000 | -1.1447 |
| SOLUSDT | V91_RETEST_MAX4H | CANDLE_ONLY | 8 | 5 | 62.5 | 4.2607 | 2.4099 | 1.1447 | 0.0000 |
| SOLUSDT | V91_RETEST_MAX4H | DAILY_RETEST_CONFIRM | 9 | 5 | 55.56 | 3.1159 | 1.0080 | 0.0000 | -1.1447 |
| SOLUSDT | V91_RETEST_MAX4H | 3D_RETEST_CONFIRM | 8 | 4 | 50.0 | 1.2671 | -0.5722 | -1.8488 | -2.9936 |
| SOLUSDT | V91_RETEST_MAX4H | DAILY_AND_3D_RETEST_CONFIRM | 8 | 4 | 50.0 | 1.2671 | -0.5722 | -1.8488 | -2.9936 |
| SOLUSDT | V91_RETEST_MAX4H | CANDLE_PLUS_3D | 7 | 4 | 57.14 | 2.4118 | 0.8298 | -0.7041 | -1.8488 |

No real orders, alerts, funding or executable fills. Fees/slippage are the existing illustrative assumptions.
No V7/V9.1 production changes. No filter promotion from this retrospective test.

