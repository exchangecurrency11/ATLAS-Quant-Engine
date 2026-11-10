# SOL — Historical Daily + 4H wide support-box role-flip study

**Important:** This tests automatically frozen broad rectangles, not the exact manually drawn 87.50–95.00 zone in November 2026.

## Method
- Binance USD-M SOL perpetual official monthly 1H ZIPs with SHA256: **21**.
- 2025-01 to 2026-09 (inclusive complete months).
- Each day a band width of 8.5% of its lower edge is evaluated with **only the preceding 28 closed Daily and 168 closed 4H candles**.
- Require at least 6 Daily and 28 4H closes inside the band, price at or above the lower boundary at formation.
- Freeze box BEFORE searching for subsequent breaks; close below floor with 0.15 prior ATR14 margin within 7 days qualifies a break.
- Next 5 days: a 4H bar touching the box but closing red below its lower edge is a qualified bearish retest rejection. Reclaim above upper edge is tracked separately.
- Compare next 6 fully closed 4H returns after a break or retest; no simulated fills, no funding/slippage profit claims.
- Only one representative episode per near-overlapping band / break time is included in summary to reduce repeated counting.

## General background rate (control, not a trading strategy)
- All eligible 4H closes: **1745 / 3517** closed lower 24 hours later.
- When BOTH Daily+4H prices were below EMA20 and EMA50 (MACD excluded): **534 / 1170** closed lower 24 hours later.
- Baseline windows overlap and do not represent independent trades. Historical event results should be interpreted relative to these background rates.

## Outcomes (overlapping break episodes deduplicated)
| Segment | Frozen boxes | Breaks | Retest rejections | 6x4H down after break | 6x4H down after retest |
|---|---:|---:|---:|---:|---:|
| Entire complete archive | 66 | 31 | 22 | 13/31 | 13/22 |
| Before Jul 2026 | 58 | 29 | 21 | 13/29 | 12/21 |
| Jul–Sep 2026 (previously examined) | 8 | 2 | 1 | 0/2 | 1/1 |

## Selected strictly historical examples
| Frozen date TSİ | Zone (USDT) | Break date TSİ | Result | 6x4H after break |
|---|---|---|---|---|
| 2026-09-10 03:00 TSİ | 98.43–106.80 | 2026-09-15 23:00 TSİ | RECLAIMED_ABOVE_ZONE | +0.21% |
| 2026-07-24 03:00 TSİ | 74.69–81.04 | 2026-07-24 19:00 TSİ | BEARISH_RETEST_REJECTION | +0.20% |
| 2026-06-23 03:00 TSİ | 67.85–73.61 | 2026-06-24 19:00 TSİ | BEARISH_RETEST_REJECTION | -1.52% |
| 2026-05-29 03:00 TSİ | 81.14–88.04 | 2026-06-01 11:00 TSİ | BEARISH_RETEST_REJECTION | -1.29% |
| 2026-03-29 03:00 TSİ | 81.92–88.89 | 2026-03-31 15:00 TSİ | BEARISH_RETEST_REJECTION | +3.13% |
| 2026-03-26 03:00 TSİ | 84.54–91.73 | 2026-03-27 15:00 TSİ | BROKEN_NO_CONFIRMED_RETEST | -0.49% |
| 2026-02-24 03:00 TSİ | 77.12–83.67 | 2026-02-24 07:00 TSİ | BEARISH_RETEST_REJECTION | +6.35% |
| 2026-02-14 03:00 TSİ | 81.71–88.65 | 2026-02-18 23:00 TSİ | BEARISH_RETEST_REJECTION | +1.27% |
| 2026-01-26 03:00 TSİ | 116.98–126.92 | 2026-01-30 07:00 TSİ | BEARISH_RETEST_REJECTION | +3.45% |
| 2026-01-22 03:00 TSİ | 127.54–138.38 | 2026-01-24 11:00 TSİ | BEARISH_RETEST_REJECTION | -0.50% |
| 2026-01-19 03:00 TSİ | 133.74–145.11 | 2026-01-19 11:00 TSİ | BEARISH_RETEST_REJECTION | -2.12% |
| 2025-12-18 03:00 TSİ | 121.32–131.63 | 2025-12-18 23:00 TSİ | BROKEN_NO_CONFIRMED_RETEST | +7.45% |

## Limitations
- The supplied manual 87.50–95.00 region does not prove an ICT breaker, only support/resistance flip hypothesis.
- The band size and density rules are exploratory, not independently validated or fit on a completely unseen test set.
- Downward 4H follow-through is not the same as a profitable SHORT after costs, stops and fills.
- This historical archive is previously inspected; no statistical significance or live efficacy claim.
- The daily close and 4H close boundaries both use UTC; TSİ is rendered only for convenience.
- No live orders and no changes to BTC/ETH/SOL production.
