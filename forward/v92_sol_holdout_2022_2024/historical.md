# V9.2 SOL earlier-period temporal validation

**Paper-only historical holdout. No orders, alerts, or production changes.**
Warmup: 2022-05-01T00:00:00Z to 2022-10-01T00:00:00Z.
Scored period: 2022-10-01T00:00:00Z to 2024-10-01T00:00:00Z (exclusive).
Source: 58 monthly SHA256-verified official Binance archives.
The selected rule is frozen; no thresholds were changed after opening this holdout.

| Coin | Baseline | Trades | Wins | Win % | Net R | Stress R | Filter trades | Filter Net R | Δ Net R | Vetoes |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| BTCUSDT | V7_ORIGINAL | 10 | 3 | 30.0 | -4.2658 | -7.7013 | 10 | -4.2658 | 0.0000 | 0 |
| BTCUSDT | V91_RETEST_MAX4H | 10 | 3 | 30.0 | -4.2658 | -7.7013 | 10 | -4.2658 | 0.0000 | 0 |
| SOLUSDT | V7_ORIGINAL | 13 | 6 | 46.15 | 3.4308 | 0.4578 | 13 | 3.4308 | 0.0000 | 0 |
| SOLUSDT | V91_RETEST_MAX4H | 12 | 6 | 50.0 | 4.6274 | 2.0039 | 12 | 4.6274 | 0.0000 | 0 |

Interpretation must consider trade counts and both base/stress costs; a small-sample improvement is not proof.
This is an earlier temporal window for the V9.2 rule, but not a wholly unseen market dataset because the repository contains other historical SOL research.
Funding, variable spread, market impact, liquidation, and executable next-open fills are not fully modeled.
No live strategy promotion from this report.

