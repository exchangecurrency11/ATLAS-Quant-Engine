# SOL V8.4 — Pivot Line, RSI, SMA100/200, Wyckoff, liquidity sweep, Fibonacci, Daily+4H wide zones

**Only research.** Short-direction study on SOL perpetual; no real orders, no BTC/ETH production edits.

## Mechanical rules
- Daily + 4H broad 8.5% OHLCV support boxes frozen BEFORE breakdown, then bearish 4H retest.
- Next eight 1H CLOSED candles: either close below prior four 1H lows or bearish upper liquidity sweep above prior 12 1H highs. Entry is only NEXT 1H OPEN.
- RSI14 Daily+4H <50, with 4H >=30 to flag oversold shorts; SMA 100/200 on 4H plus SMA100 Daily, optional Daily SMA200 where warmed.
- Wyckoff SOW and LPSY are volume-price heuristic proxies, NOT verified institutional distribution/spring/UTAD.
- Fibonacci 38.2–61.8 and classical P/R1/R2/S1/S2 previous fully completed Daily pivot.
- Bearish OB/FVG chart-derived candidate only; look for 1H preceding 24h upper-high liquidity sweep; MACD excluded.
- Each vote fixed before historical execution; score>=4 or >=5 variants shown; ALL eight hard mandatory is a diagnostic only.
- Paper SHORT stop: 1H confirmation high or preceding high + 0.03 of 4H ATR buffer. TP2R / 24h close, pessimistic stop-first, 9 bps one-way. Planned risk <=0.5 USD per trade and 10x notional cap.
- Independent per-strategy account starts at 100 USD. Any overlap is excluded (not double-counted). Stop-gap losses may exceed the planned risk.

## Comparison — 24-hour direction accuracy AFTER 1H confirmation
| Version | 2023–24 | 2025–Sep2026 | Combined | Non-overlap paper trades | Account net USD |
|---|---:|---:|---:|---:|---:|
| 00_1H_Confirmed_PriceOnly | 6/16 (37.5%) | 7/12 (58.33%) | 13/28 (46.43%) | 27 | -1.9017 |
| 01_SMA100200_RSI | 4/8 (50.0%) | 4/8 (50.0%) | 8/16 (50.0%) | 15 | +0.2055 |
| 02_Wyckoff_SMA | 0/3 (0.0%) | 3/5 (60.0%) | 3/8 (37.5%) | 8 | -0.8373 |
| 03_LiquiditySweep | 4/11 (36.36%) | 6/8 (75.0%) | 10/19 (52.63%) | 18 | -1.3489 |
| 04_Fibonacci_Pivot | 5/13 (38.46%) | 3/5 (60.0%) | 8/18 (44.44%) | 17 | -2.5160 |
| 05_Score4of8 | 6/13 (46.15%) | 6/11 (54.55%) | 12/24 (50.0%) | 23 | -2.5183 |
| 06_Score5of8 | 5/12 (41.67%) | 5/9 (55.56%) | 10/21 (47.62%) | 20 | -2.2864 |
| 07_SMA_RSI_Score4 | 4/8 (50.0%) | 4/8 (50.0%) | 8/16 (50.0%) | 15 | +0.2055 |
| 08_SMA_RSI_Wyckoff_Sweep | 0/2 (0.0%) | 3/3 (100.0%) | 3/5 (60.0%) | 5 | +0.6652 |
| 09_AllEightHardGates | No cases | No cases | No cases | 0 | +0.0000 |

## Important limitations
- All historical periods were already examined; no honest out-of-sample validation yet.
- Multiple versions measured; selecting whichever is 75% with low n is not evidence of an edge.
- OHLCV can indicate possible Wyckoff or liquidity sweep, but not confirmed market-maker intent.
- Fixed fee+slippage and no liquidation/funding/partial fill model. No claim of net profit.
- Previous candle analysis restricts feature creation; labels after entries are NEVER used for gating.
- This pipeline is standalone SOL SHORT only, not BTC/ETH or LONG live deployment.
