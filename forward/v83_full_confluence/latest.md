# SOL V8.3 — Wyckoff proxies + RSI + EMA + Fib + Daily pivot + Order Block + volume

THIS IS EXPLORATORY HISTORICAL RESEARCH, NOT REAL TIME SUCCESS OR AN EXECUTABLE SIGNAL.
All eight indicators are evaluated on already closed bars; all-eight, score and individual filters compared.
75% target is a user benchmark; thresholds were frozen before the study, not tuned for the best result.

## Immutable research rules
- SOL Binance USD-M Futures official SOLUSDT 1H monthly .zip plus .CHECKSUM verification; 45 months total across 2023-24 and 2025-Sep2026.
- V8.1 wide Daily+4H support zone frozen before the break, red retest below the band.
- V8.2 Fib 38.2–61.8 retracement and Classic prior completed UTC Daily P/R1/R2/S1/S2.
- RSI14 4H and Daily under 50 but 4H >=30; EMA20/50 trend below BOTH timeframes. EMA200 is context only. First 55 Daily candles lack sufficient RSI/EMA50 warmup and are excluded for all filters.
- Wyckoff SOW proxy = broken support with RVOL>=1.2 and bearish close in bottom 40% of the range.
- Wyckoff LPSY proxy = after break, failed upper retest below previous 12-bar high and volume contraction or upper wick.
- Bearish Order Block = CHoCH/BOS previous opposite candle from OHLCV structure, known BEFORE the 4H retest opens; FVG also recorded.
- Last closed 1H rejection and prior 20-bar 4H break relative-volume recorded.
- Score = sum of 8 binary votes (FVG is extra, no score); no MACD.
- Paper SHORT (separate metric): next 4H OPEN, stop beyond retest/box +0.15ATR, TP2R or 24h exit, stop-first, 9bps one-way, 100 USD 10x, <=0.5 USD planned risk. Gap-through stops can exceed planned risk.
- Alternative local retest-wick stop +0.15 ATR is post-hoc sensitivity introduced after finding no full-box eligible fills; not a tested production choice.
- No proof of genuine Wyckoff phases, UTAD, springs or institutional orders; chart-only proxies.

| Filter | 2023–24 hit | 2025–Sep2026 hit | Combined hit | Combined count | Full-box paper trades | Local-wick paper trades / net USDT (post-hoc) |
|---|---:|---:|---:|---:|---:|---:|
| 00_BaseWideZoneRetest | 11/26 (42.31%) | 12/21 (57.14%) | 23/47 (48.94%) | 47 | 0 | 39 / -1.7269 |
| 01_RSI14Daily4H | 8/20 (40.0%) | 11/18 (61.11%) | 19/38 (50.0%) | 38 | 0 | 32 / +0.3445 |
| 02_EMA20_50Daily4H | 6/18 (33.33%) | 11/19 (57.89%) | 17/37 (45.95%) | 37 | 0 | 31 / -1.7697 |
| 03_WyckoffSOW_LPSYProxy | 2/10 (20.0%) | 7/10 (70.0%) | 9/20 (45.0%) | 20 | 0 | 18 / +0.4228 |
| 04_Fibonacci | 8/20 (40.0%) | 6/8 (75.0%) | 14/28 (50.0%) | 28 | 0 | 24 / +1.7997 |
| 05_PreviousDayPivot | 11/23 (47.83%) | 10/18 (55.56%) | 21/41 (51.22%) | 41 | 0 | 33 / -2.3332 |
| 06_ChartOrderBlock | 2/4 (50.0%) | 2/5 (40.0%) | 4/9 (44.44%) | 9 | 0 | 6 / -0.8078 |
| 07_BreakHighVolume | 9/20 (45.0%) | 8/13 (61.54%) | 17/33 (51.52%) | 33 | 0 | 28 / -1.1430 |
| 08_1HRejection | 5/13 (38.46%) | 6/13 (46.15%) | 11/26 (42.31%) | 26 | 0 | 21 / -2.1047 |
| 09_FibonacciAndPivot | 8/18 (44.44%) | 5/7 (71.43%) | 13/25 (52.0%) | 25 | 0 | 21 / +0.5240 |
| 10_Trend_RSI_EMA_Wyckoff | 0/6 (0.0%) | 6/8 (75.0%) | 6/14 (42.86%) | 14 | 0 | 13 / +0.1903 |
| 11_AllEightMandatory | No signal | 0/1 (0.0%) | 0/1 (0.0%) | 1 | 0 | 1 / -0.5000 |
| 12_Score4of8 | 8/21 (38.1%) | 10/17 (58.82%) | 18/38 (47.37%) | 38 | 0 | 31 / -0.4513 |
| 13_Score5of8 | 8/19 (42.11%) | 9/13 (69.23%) | 17/32 (53.12%) | 32 | 0 | 27 / +0.3808 |
| 14_FibAndScore4of8 | 7/18 (38.89%) | 5/7 (71.43%) | 12/25 (48.0%) | 25 | 0 | 21 / +1.8856 |
| 15_Trend_Wyckoff_Fib | 0/5 (0.0%) | 4/5 (80.0%) | 4/10 (40.0%) | 10 | 0 | 9 / +0.6951 |
| 16_FVGextra | 1/6 (16.67%) | 3/7 (42.86%) | 4/13 (30.77%) | 13 | 0 | 10 / -2.3185 |

## Caveats
- Both periods are previously examined; they are NOT a new independent validation cohort.
- Multiple filters were compared; selecting the highest percentage is data snooping.
- The count of signals is low; Wilson 95% lower bounds must be reported.
- Paper net USD sums are per independent event, not an executable one-position-at-a-time account.
- Funding, maker/taker actual fees, realized fill quality, changing spreads, OI and market impact not reconciled.
- Consecutive 24-hour outcomes can overlap; these are not automatically independent observations.
- No real orders and no BTC/ETH/SOL production branch edits.
