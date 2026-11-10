# V8.6 SOL — Trend continuation vs countertrend relief vs reversal

**Experimental classification of SOL Daily+4H+1H, no trading orders.**

## Fixed pretest rules
- One daily observation at exactly 20:00 UTC / 23:00 TSİ; ensuing 6x4H close (24h) outcomes don't overlap.
- SMA100/200 actual simple averages on Daily and 4H, RSI14 Wilder, last 4 true 1H candles, 4H prior8 swing references, relative volume20.
- Bear continuation: 4H below SMA100 with SMA100<SMA200; latest closed Daily below SMA100 and RSI<50; 4H RSI 35..50 and bearish 1H BOS/sweep.
- Oversold: current 4H or Daily RSI <=30 in bear context. If bullish 1H rejection then relief bounce candidate LONG; else ABSTAIN.
- Symmetric bull continuation, overbought pullback and reversal-candidate conditions. Reversal candidates require closed multi-timeframe price reclaim/loss and 1H plus 4H microstructure.
- Daily SMA100/SMA200 CROSS is not a mandatory hard gate for existing trend: daily SMA lags 4H and price context; current daily order still reported.
- Assesses next 4h and 24h close direction only. No simulated fills, fee-adjusted PnL or false win rate claim.
- This reuses previously investigated 2023–26 data; no untouched holdout and no claim of forecast calibration.

| Segment | Checkpoints | Signals | Coverage | 24h hit | Next 4h hit |
|---|---:|---:|---:|---:|---:|
| 2023–24 | 529 | 42 | 7.94% | 22/42 (52.38%) | 15/42 (35.71%) |
| 2025–Sep2026 | 436 | 30 | 6.88% | 15/30 (50.0%) | 11/30 (36.67%) |
| Combined | 965 | 72 | 7.46% | 37/72 (51.39%) | 26/72 (36.11%) |

## Breakdown by actual frozen label (combined)
| Label | Signals | Direction right | 24h accuracy |
|---|---:|---:|---:|
| RELIEF_BOUNCE_LONG | 4 | 1 | 25.0% |
| RELIEF_BOUNCE_SHORT | 19 | 9 | 47.37% |
| REVERSAL_DOWN_CANDIDATE | 3 | 2 | 66.67% |
| REVERSAL_UP_CANDIDATE | 1 | 1 | 100.0% |
| TREND_CONTINUATION_LONG | 25 | 13 | 52.0% |
| TREND_CONTINUATION_SHORT | 20 | 11 | 55.0% |

## Constraints
- Daily checkpoint outcome windows are disjoint; historical bars reused for SMA warmup are not independent training data.
- SOW/LPSY and liquidity sweeps are chart inferences; no proof of actual institutional order placement.
- No BTC/ETH extrapolation from SOL backtest; no claim that 75% goal was reached.
- The user-drawn 87.50–95 rectangle is not force-fitted into historical detection.
- All results historical, not prospective; source archive completeness is enforced, missing months fail.
