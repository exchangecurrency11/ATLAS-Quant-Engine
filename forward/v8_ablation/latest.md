# V8 signal-filter ablation — BTC / ETH / SOL

This is a **repeatedly inspected historical period**, not fresh out-of-sample.
No actual trades, no new threshold tuning, no authorization for live entry.

| Asset | Variant | Earlier paper trades | Earlier net USD | Reused Jul-Sep trades | Reused Jul-Sep net USD |
|---|---|---:|---:|---:|---:|
| BTCUSDT | V7_BOS_only_existing | 9 | +1.648 | 0 | +0.000 |
| BTCUSDT | V8_EMA_trend_only_context_shadow | 9 | +1.648 | 0 | +0.000 |

- BTCUSDT retest closed-candle feature readings: 9; completed trades with score below 2: 6; score >= 2: 3.
| ETHUSDT | V7_BOS_only_existing | 4 | -0.658 | 2 | -0.303 |
| ETHUSDT | V8_EMA_trend_only_context_shadow | 4 | -0.658 | 2 | -0.303 |

- ETHUSDT retest closed-candle feature readings: 7; completed trades with score below 2: 2; score >= 2: 4.
| SOLUSDT | V7_BOS_only_existing | 10 | +1.626 | 0 | +0.000 |
| SOLUSDT | V8_EMA_trend_only_context_shadow | 10 | +1.626 | 0 | +0.000 |

- SOLUSDT retest closed-candle feature readings: 11; completed trades with score below 2: 5; score >= 2: 5.

**Interpretation:** This can diagnose scarcity from rule confluence, not prove profitable future performance. Future paper-forward outcomes are the required next independent evaluation.

No OI/funding/cross-asset votes included in historical entries because their contemporary availability is not verified throughout the study.
