# SOL V8.2 — Fibonacci + previous Daily pivot on wide-zone 4H retests

**No real trading or independent forward validation.** User's objective of 75% is a *benchmark*, not a basis for after-the-fact threshold optimization.

**Source:** official Binance USD-M SOLUSDT 1H monthly ZIP + .CHECKSUM
**Verified months:** 21; **period:** 2025-01–2026-09

## Frozen test rules (no MACD)
- Wide Daily+4H boxes frozen at prior Daily closes; no user price anchor is used.
- After 4H support breakdown and confirmed retest candle closes bearish below zone:
  - Fibonacci anchors: highest high in the 18 4H candles BEFORE breakdown, lowest low from break through retest close. Wick high near 38.2–61.8% retracement (±0.35 times previous 4H ATR14).
  - Classical pivots: from the **previous completed UTC day** only (P, R1, R2, S1, S2). Retest high within 0.65 times the previous 4H ATR14 of a level at/above retest close.
- This is a retrospective diagnostic of 6 future 4H closing bars (24 hours); not a hypothetical entry PnL.
- Event sample is deduplicated as in V8.1; no threshold fitting to the 75% objective.

| Period | Filter | Retests | Down 24h | Direction hit | Wilson 95% lower bound |
|---|---|---:|---:|---:|---:|
| Full historical | baselineAllRetestRejections | 22 | 13 | 59.09% | 38.73% |
| Full historical | fib382To618 | 9 | 7 | 77.78% | 45.26% |
| Full historical | previousDailyPivot | 19 | 11 | 57.89% | 36.28% |
| Full historical | fibAndPivotBoth | 8 | 6 | 75.0% | 40.93% |
| Full historical | fibOrPivotEither | 20 | 12 | 60.0% | 38.66% |
| Full historical | neitherConfluence | 2 | 1 | 50.0% | 9.45% |
| Before July 2026 | baselineAllRetestRejections | 21 | 12 | 57.14% | 36.55% |
| Before July 2026 | fib382To618 | 8 | 6 | 75.0% | 40.93% |
| Before July 2026 | previousDailyPivot | 18 | 10 | 55.56% | 33.72% |
| Before July 2026 | fibAndPivotBoth | 7 | 5 | 71.43% | 35.89% |
| Before July 2026 | fibOrPivotEither | 19 | 11 | 57.89% | 36.28% |
| Before July 2026 | neitherConfluence | 2 | 1 | 50.0% | 9.45% |
| July–Sep 2026 (reused) | baselineAllRetestRejections | 1 | 1 | 100.0% | 20.65% |
| July–Sep 2026 (reused) | fib382To618 | 1 | 1 | 100.0% | 20.65% |
| July–Sep 2026 (reused) | previousDailyPivot | 1 | 1 | 100.0% | 20.65% |
| July–Sep 2026 (reused) | fibAndPivotBoth | 1 | 1 | 100.0% | 20.65% |
| July–Sep 2026 (reused) | fibOrPivotEither | 1 | 1 | 100.0% | 20.65% |
| July–Sep 2026 (reused) | neitherConfluence | 0 | 0 | N/A% | N/A% |

## Sample event examples
| Retest TSİ | Wide zone (USD) | Fib matched | Pivot matched | Nearest pivot | 24h direction return |
|---|---|---|---|---|---:|
| 2025-02-12 19:00 TSİ | 196.22–212.90 | Yes | Yes | P | -0.036% |
| 2025-03-19 11:00 TSİ | 126.01–136.72 | Yes | Yes | R1 | +6.581% |
| 2025-04-04 07:00 TSİ | 116.49–126.39 | No | Yes | P | +4.630% |
| 2025-06-02 15:00 TSİ | 154.00–167.10 | No | Yes | P | +4.642% |
| 2025-06-13 23:00 TSİ | 145.54–157.91 | No | Yes | S1 | -1.137% |
| 2025-06-17 19:00 TSİ | 149.95–162.69 | Yes | Yes | P | -1.267% |
| 2025-06-22 03:00 TSİ | 137.92–149.64 | Yes | No | P | -2.720% |
| 2025-10-08 07:00 TSİ | 220.58–239.33 | No | Yes | P | +3.620% |
| 2025-10-14 23:00 TSİ | 205.44–222.90 | No | Yes | P | -1.875% |
| 2025-10-22 03:00 TSİ | 186.79–202.66 | No | Yes | R1 | -2.981% |
| 2025-11-21 03:00 TSİ | 134.91–146.37 | Yes | Yes | P | -3.735% |
| 2025-12-17 19:00 TSİ | 131.60–142.78 | Yes | Yes | R2 | +0.529% |
| 2025-12-16 11:00 TSİ | 127.37–138.20 | No | Yes | P | +2.159% |
| 2026-01-19 19:00 TSİ | 133.74–145.11 | No | Yes | S2 | -4.263% |
| 2026-01-25 03:00 TSİ | 127.54–138.38 | No | Yes | P | -6.584% |
| 2026-01-30 19:00 TSİ | 116.98–126.92 | Yes | Yes | P | -6.990% |
| 2026-02-19 15:00 TSİ | 81.71–88.65 | No | Yes | P | +2.857% |
| 2026-02-24 11:00 TSİ | 77.12–83.67 | No | No | P | +6.954% |
| 2026-04-02 03:00 TSİ | 81.92–88.89 | No | No | P | -2.748% |
| 2026-06-02 07:00 TSİ | 81.14–88.04 | Yes | Yes | P | -10.163% |
| 2026-06-24 23:00 TSİ | 67.85–73.61 | No | Yes | S1 | +0.121% |
| 2026-07-28 03:00 TSİ | 74.69–81.04 | Yes | Yes | P | -0.526% |

## Limitations
- These filters were designed after earlier analysis of the same archive; results are exploratory, not a clean held-out experiment.
- A 75% hit rate from a small subset can be noise. Also test win/loss *money*, fees, spread, stop, and forward time-separated samples.
- No actual fills, OI, funding, taker or verified institutional OB modeled.
- A direction hit over 24 hours is not equal to a profitable SHORT position.
- No production or active BTC/SOL/ETH trading workflows were modified.
