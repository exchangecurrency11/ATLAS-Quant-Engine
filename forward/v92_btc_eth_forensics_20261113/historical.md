# V9.2 BTC/ETH losses, stop-ATR and regime test

**RESEARCH ONLY. NO BROKER ORDERS. No live V7/V9.2 modifications.**

Period: 2024-10 through 2026-09; official Binance USD-M archives, 48 verified SHA256 ZIPs.
These experiments were selected after seeing earlier performance: results are
exploratory and not out-of-sample evidence. Baseline uses the original
V7 BOS quality and V9.1 four-hour retest chronological next-open simulation.

## Comparative results

| Asset | Variant | Trades | Wins | Net R (9bps) | Stress R (25bps) | PF | Max DD R | Veto |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| BTCUSDT | BASELINE_4H | 5 | 3 | +4.101 | +2.815 | 3.8104 | 1.230 | 0 |
| BTCUSDT | BASELINE_6H | 9 | 5 | +3.664 | +1.329 | 1.9692 | 3.551 | 0 |
| BTCUSDT | BTC_SHORT_ONLY | 4 | 3 | +5.331 | +4.453 | 24.2474 | 0.229 | 1 |
| BTCUSDT | BTC_DAILY_TREND_ALIGNED | 5 | 3 | +4.101 | +2.815 | 3.8104 | 1.230 | 0 |
| BTCUSDT | BTC_1H_ATR_VOL_GE_0P5PCT | 5 | 3 | +4.101 | +2.815 | 3.8104 | 1.230 | 0 |
| BTCUSDT | BTC_RETEST_STOPWIDTH_LE_2ATR | 5 | 3 | +4.101 | +2.815 | 3.8104 | 1.230 | 0 |
| ETHUSDT | BASELINE_4H | 6 | 2 | -2.008 | -4.109 | 0.4951 | 2.179 | 0 |
| ETHUSDT | BASELINE_6H | 7 | 2 | -2.448 | -4.738 | 0.4458 | 2.619 | 0 |
| ETHUSDT | ETH_SHORT_ONLY | 3 | 1 | +0.101 | -0.905 | 1.0699 | 1.048 | 3 |
| ETHUSDT | ETH_RETEST_STOPWIDTH_LE_2ATR | 5 | 1 | -2.434 | -4.390 | 0.3881 | 2.434 | 1 |
| ETHUSDT | ETH_RETEST_BODY_GE_0P2ATR | 4 | 1 | -2.149 | -2.722 | 0.1653 | 2.575 | 2 |
| ETHUSDT | ETH_RETEST_RVOL20_GE_1P2 | 1 | 0 | -1.403 | -2.119 | 0.0 | 1.403 | 5 |
| ETHUSDT | ETH_SHORT_AND_STOPWIDTH_LE_2ATR | 3 | 1 | +0.101 | -0.905 | 1.0699 | 1.048 | 3 |

## Baseline trade diagnostics

| Asset | Entry UTC | Direction | Net R | Stop / ATR14 | Retest RVOL20 | Daily regime | Exit |
|---|---|---|---:|---:|---:|---|---|
| BTCUSDT | 2025-05-02T18:00:00Z | bullish | -1.230 | 1.52 | 0.833698 | bullish | STOP_FIRST_OR_AFTER_TP |
| BTCUSDT | 2025-11-21T07:00:00Z | bearish | +1.904 | 1.49 | 0.465112 | bearish | TP3_COMPLETE |
| BTCUSDT | 2026-02-05T04:00:00Z | bearish | +1.927 | 1.35 | 1.097454 | bearish | TP3_COMPLETE |
| BTCUSDT | 2026-05-27T17:00:00Z | bearish | +1.729 | 1.31 | 1.097778 | bearish | TP3_COMPLETE |
| BTCUSDT | 2026-06-05T16:00:00Z | bearish | -0.229 | 1.91 | 2.158181 | bearish | TIME_EXIT_AT_CLOSE |
| ETHUSDT | 2025-04-09T03:00:00Z | bearish | -1.048 | 1.53 | 1.115693 | bearish | STOP_FIRST_OR_AFTER_TP |
| ETHUSDT | 2025-05-20T05:00:00Z | bullish | -1.132 | 0.89 | 0.580039 | bullish | STOP_FIRST_OR_AFTER_TP |
| ETHUSDT | 2026-01-29T14:00:00Z | bearish | +1.544 | 0.59 | 0.391768 | bearish | TP3_COMPLETE |
| ETHUSDT | 2026-02-02T03:00:00Z | bearish | -0.395 | 1.12 | 0.798817 | bearish | STOP_FIRST_OR_AFTER_TP |
| ETHUSDT | 2026-07-20T18:00:00Z | bullish | +0.425 | 2.28 | 0.860132 | bullish | TIME_EXIT_AT_CLOSE |
| ETHUSDT | 2026-09-27T10:00:00Z | bullish | -1.403 | 1.00 | 1.434894 | bullish | STOP_FIRST_OR_AFTER_TP |

## Important limitations

- The 2-year period had previously been analyzed, so differences are selection-biased hypotheses.
- Gate decisions are known at retest close; original entry remains next 1H *open*, not live executable fill.
- ATR stop-width scenario vetoes trades; it never edits historical stop/TP prices.
- All costs are assumed; no full funding, spread variation, liquidation, orderbook or slippage proof.
- Too few trades to conclude statistical significance, especially one-direction subsets.
- Historical completed trades cannot count toward the 50 genuinely prospective completed trades gate.
- Source data do not establish historical Coinalyze/Binance parity for ETH; official Binance only.


