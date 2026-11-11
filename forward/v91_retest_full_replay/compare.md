# V9.1 retest expiry + strong retest: full sequential historical replay

**PAPER ONLY.** Historical bars were previously inspected. The 4h rule was proposed after examining past results. It is NOT an independent out-of-sample validation.

Original V7 BOS entry engine, 1H subsequent open, stops and three partial profit targets all retained. 9bps per side baseline; 25bps stress per side. Funding, fills and liquidation are excluded.

The strong-retet gate tests close >=0.20 ATR beyond BOS, directional body >=0.20 ATR, close location >=60% in the trade direction, retest volume >=1.0x preceding 20 closed hourly bars. V7 baseline has no extra retest gate in the published V9 full-profit replay.

| Asset | Variant | Trades | Win % | Total net R | Stress total R | PF | Max DD R | Watch | Retest rejected | Expired |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| BTCUSDT | V7_ORIGINAL | 9 | 55.56 | 3.6636 | 1.329 | 1.969 | 3.5506 | 26 | 0 | 17 |
| BTCUSDT | V91_RETEST_MAX4H | 5 | 60.0 | 4.101 | 2.8146 | 3.81 | 1.2299 | 26 | 0 | 21 |
| BTCUSDT | V91_STRONG_RETEST | 3 | 66.67 | 3.0177 | 2.5266 | 14.16 | 0.2293 | 27 | 9 | 24 |
| BTCUSDT | V91_MAX4H_AND_STRONG | 3 | 66.67 | 3.0177 | 2.5266 | 14.16 | 0.2293 | 27 | 4 | 24 |
| SOLUSDT | V7_ORIGINAL | 11 | 54.55 | 2.861 | 0.6026 | 1.523 | 2.5764 | 29 | 0 | 17 |
| SOLUSDT | V91_RETEST_MAX4H | 9 | 55.56 | 3.1159 | 1.008 | 1.701 | 2.2718 | 30 | 0 | 20 |
| SOLUSDT | V91_STRONG_RETEST | 4 | 25.0 | -1.9433 | -2.5324 | 0.406 | 3.2692 | 30 | 14 | 24 |
| SOLUSDT | V91_MAX4H_AND_STRONG | 2 | 50.0 | 0.2361 | -0.034 | 1.217 | 1.0898 | 30 | 11 | 27 |

**Do not select new thresholds based on this previously seen period.** Prospectively log fresh V7 opportunities with identical source and as-of checks before considering any activation.
