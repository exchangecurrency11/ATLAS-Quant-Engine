# V9 trade-first full chronological historical backtest vs original V7

**History:** 2024-10-01T00:00:00Z through 2026-10-01T00:00:00Z (exclusive).

**Primary:** same actual V7 BOS -> later confirmed retest -> next 1H open -> stop / 1R,2R,3R TP. V9 GREEN/RED is only a precomputed 4H context FILTER on qualifying BOS, never an independent trade.

**Strict:** V9 same 6 fixed chronological expanding folds and same official Binance history, 4H target prediction T−5m, then BOS at time >=T. All variants rerun V7 full sequentially. NO past-trade winner filtering. Historical periods were already inspected, and must NOT be reused for parameter selection or claimed as truly unseen.

| Asset | Variant | Trades | Win% | Avg net R | Total net R | Avg R 25bp/side | PF | Max DD(R) |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| BTCUSDT | V7_ORIGINAL | 9 | 55.56 | 0.4071 | 3.6636 | 0.1477 | 1.969 | 3.5506 |
| BTCUSDT | V9_94_DIRECTION_GATE | 2 | 50.0 | 0.3115 | 0.6231 | -0.0235 | 1.507 | 1.2299 |
| BTCUSDT | V9_88_NO_TX_DIRECTION_GATE | 2 | 50.0 | 0.3115 | 0.6231 | -0.0235 | 1.507 | 1.2299 |
| BTCUSDT | V9_94_AND_88_AGREEMENT_GATE | 2 | 50.0 | 0.3115 | 0.6231 | -0.0235 | 1.507 | 1.2299 |
| SOLUSDT | V7_ORIGINAL | 11 | 54.55 | 0.2601 | 2.861 | 0.0548 | 1.523 | 2.5764 |
| SOLUSDT | V9_94_DIRECTION_GATE | 1 | 100.0 | 0.7704 | 0.7704 | 0.6652 | N/A | 0 |
| SOLUSDT | V9_88_NO_TX_DIRECTION_GATE | 2 | 100.0 | 1.2555 | 2.5109 | 0.9722 | N/A | 0 |
| SOLUSDT | V9_94_AND_88_AGREEMENT_GATE | 1 | 100.0 | 0.7704 | 0.7704 | 0.6652 | N/A | 0 |

## Known limits
Small sample of original V7 retest paper trades; no orders or fills. Funding, real execution gaps, spread, liquidation and leverage not simulated. A green 4H candle does not imply a profitable LONG.
No 2026-10 or 2026-11 targets in the V9 evaluation because the 6-fold historical 4H records end 2026-09. Original V7 Oct-Nov observations remain untouched and separate.
A strategy improvement requires independent new paper trade P&L and price-source parity, not this backtest alone.
