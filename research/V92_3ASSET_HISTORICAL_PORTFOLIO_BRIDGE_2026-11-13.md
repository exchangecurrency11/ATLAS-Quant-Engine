# V9.2 historical BTC/ETH/SOL portfolio sensitivity — 13 November 2026

**RESEARCH ONLY. NOT the forward 10/20 USDT capped-paper ledger, not a fresh OHLCV replay, and not proven executable fills.**

## Methods

- Period: 2024-10-01T00:00:00Z to 2026-10-01T00:00:00Z, using previously committed OHLCV-based historical replay trade-entry/exit evidence.
- BTC: V9.1 max4h BOS/retest + V9.2 SOL-specific selective filter (BTC observe-only; 5 trades).
- SOL: V9.1 max4h BOS/retest + V9.2 opposing Star/confirmed Harami prior-20 liquidity sweep filter (8 trades).
- ETH: V9.1 max4h BOS/retest + V9.2 exploratory candle-only shadow variant (no vetoes, 6 trades). ETH history independently sourced and not exact Coinalyze parity.
- Trade records sorted by historical *entryUTC*. A 10 USDT-per-1R constant-stake **illustration** applies each precomputed after-cost net R to a nominal 1,000 USDT starting value. Existing positions must exit *strictly before* another entry to free a slot. Maximum 2 concurrent slots as proxy for 20 USDT target combined risk; one open trade per symbol. No resizing, reinvestment, mark-to-market or funding.
- Trade-source historical engines assume next-open fills after retest; they **do not** reproduce the live prospective capped engine's later observed close, risk-gate stop width checks, 25-bps reserved-cost position sizing or late Git-sealed intent chronology. Therefore outputs below **cannot** be represented as an exact 10/20 USDT capped-account backtest, return forecast or promotion evidence.
- Baseline trading cost is 9 bps per side; stress costs 25 bps per side from the *original* historical replay reports. Stress sums assume no slot-based skipped trade (confirmed here).

## Two-year historical comparison (BTC + SOL + ETH)

| Historical variant | Trades | Wins | Win rate | Aggregate net R (9 bps/side) | Stress net R (25 bps/side) | Illustration at fixed 10 USDT/1R: final balance (9 bps) | Stress final balance (25 bps) | Realized-only peak-to-trough drawdown in 10 USDT/1R units |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| V7 original | 27 | 13 | 48.15% | +4.076623 | -2.805944 | 1040.77 USDT | 971.94 USDT | 87.46 USDT |
| V9.1 max4h | 20 | 10 | 50.00% | +5.208700 | -0.286224 | 1052.09 USDT | 997.14 USDT | 56.81 USDT |
| V9.2 selected-shadow | 19 | 10 | 52.63% | +6.353407 | +1.115739 | 1063.53 USDT | 1011.16 USDT | 45.37 USDT |

All three variant portfolios had <=2 simultaneous trades; none was rejected by the **two-slot approximation**. That does **not** prove none would be rejected by the actual 10/20 risk-plus-cost and notional gate.

## V9.2 per asset (two-year simulation)

| Symbol | Historical trades | Wins | Net R at 9 bps/side | Net R at 25 bps/side |
|---|---:|---:|---:|---:|
| BTC | 5 | 3 | +4.101040 | +2.814628 |
| SOL | 8 | 5 | +4.260655 | +2.409915 |
| ETH | 6 | 2 | -2.008289 | -4.108804 |
| Total | 19 | 10 | +6.353406 (rounding) | +1.115739 |

Profit factor from 19 individual historical 9-bps net-R observations is approximately 1.727. Drawdown above uses only the realized balance at each exit, **not** intratrade/margin drawdown. 25-bps stress report's combined R positive by only +1.115739, implying little robustness margin.

## Earlier-period holdout, no ETH (2022-10-01 to 2024-10-01)

Frozen V9.2 strict SOL sweep filter: BTC 10 trades, -4.265784 R at 9 bps / -7.701252 R at 25 bps. SOL 12 trades, +4.627398 R at 9 bps / +2.003940 R at 25 bps. Combined 22 trades, **+0.361614 R** at 9 bps and **-5.697312 R** at 25 bps; no vetoes in this earlier sample. This illustrates instability of whole-portfolio cost-stressed profitability across periods. ETH was not included.

## Decision

**DO NOT PROMOTE V9.2 OR DISABLE V7.** These historical reports may include already-researched historical selection. Forward prospective 10/20 USDT paper account remains separate with its actual immutable signals, risk reservations and observations. It still needs 7 days continuous validated data and >=50 truly prospective closed trades, entry/exit integrity and positive cost stress with manual authorization. Historical backtest does not count toward the 50-trade gate.

## Reproducible data lineage (read-only originals)

- `forward/v92_higher_timeframe_backtest_warmup/historical.json` — BTC/SOL existing V7/V9.1 and V9.2 candle-only entry/exit evidence
- `forward/v92_selected_reversal_patterns/historical.json` — SOL selected strict sweep rule and filter results
- `forward/v92_eth_historical_backtest_warmup/historical.json` — ETH historical entry/exit evidence, 183-day warmup
- `forward/v92_sol_holdout_2022_2024/historical.json` — separate earlier BTC/SOL holdout
- `v92_capped_paper.py` and `v92_stable_hardening.py` — prospective, separate 10/20 USDT policy, not used for these exact fills

No V7, original V9.2 paper snapshot, live notification, production workflow or financial order is changed by this research report.
