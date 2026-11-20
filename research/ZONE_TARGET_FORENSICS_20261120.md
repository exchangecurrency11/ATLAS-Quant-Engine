# ATLAS Zone Target Intelligence — 2026-11-20 forensic baseline

**Mode:** isolated research, not live alerts or trading.  
**Status:** initial historical-source audit; NOT a strategy backtest, performance claim, or verified signal-timing match.

## Invariant: use only contemporaneous evidence

The 2026-11-15 BTC early-SHORT notice is user-reported at about **$64,738**. Its independent notification delivery timestamp has not yet been retrieved/verified. Do not mislabel an approximate price match as exact proof of the notification.

For reproducibility, this first baseline deliberately uses a **hypothetical as-of cutoff 2026-11-15 15:05:00 UTC** (18:05 TSİ), *not* a claim that the alert happened at that time:

- **Historical structure Git commit:** `380f108369e4037af0f0c97e2aa09bbdbe2b1d9e`, committed **2026-11-15 15:04:37 UTC**; file `market_structure_data.json`.
- **Historical market-data Git commit:** `492e91c260066a5e94550416b9fd503e9c1063c2`, committed **2026-11-15 15:04:25 UTC**; file `market_data.json`.
- **Recorded closed BTC 1H:** 2026-11-15 15:00 UTC, close **$64,740.60**.
- **Recorded 4H:** 2026-11-15 12:00 UTC; **Daily:** 2026-11-15 00:00 UTC.
- **V7 snapshot:** `experiment/v7-signal-quality-20261103/forward/snapshots/2026-11-15T15-00Z.json` (observed at 15:24:43 UTC), so this later V7 publication must NOT be represented as evidence accessible at 15:05. V7 shows no fresh BOS/watch at its own 15:00 observation; this is NOT the early-alert automation.

The source commit publication time must precede the candidate signal cutoff. For a real alert forensic replay, replace the hypothetical cutoff with the **verified notification time**, fetch the latest actually published source commit **at or before** that time, and apply the same gates. If provenance is missing, label status **UNVERIFIED**, not a predicted target.

## BTC/SHORT candidate zones at this illustrative cutoff

Candidates are output of existing `market_structure.py` heuristics and can be checked using `research/zone_target_intelligence_v0.py`. Ranking below is by distance from the recorded $64,740.60 close to the nearest edge, not predictive success.

| Rank | Type | Timeframe | Preexisting range/level (USD) | Distance to entry edge |
|---|---|---|---|---:|
| 1 | Open bullish FVG | 1H | 63,446.60–64,719.00 | 0.033% |
| 2 | Retested bullish candidate OB | Daily | 62,307.00–63,749.90 | 1.530% |
| 3 | Retested bullish candidate OB | Daily | 62,876.00–63,053.90 | 2.605% |
| 4 | Equal lows, chart liquidity proxy | Daily | 62,356.50 | 3.683% |
| 5 | Equal lows, chart liquidity proxy | Daily | 62,017.40 | 4.206% |
| 6 | Equal lows, chart liquidity proxy | Daily | 57,894.30 | 10.575% |

Note overlap: Daily OB #2 and #3 are not independent observations. The OBs are *candidates*, and equal lows are *not verified resting exchange orders*. The 1H FVG sits very close below the observed close and is not equivalent to a $58,700–59,000 demand prediction.

**Result:** no recorded bullish candidate OB at **$58,700–59,000**, and no exact preexisting demand-zone call at that range was established. A $57,894.30 equal-low proxy is a different level and must not be retroactively renamed. The price reaching or bouncing from a zone later is not proof that the system forecast the move.

## Symmetric LONG/SHORT coverage (research only)

This project is **bidirectional** and applies identically to **BTC and SOL**. The historical BTC SHORT is only the first forensic case; it does **not** limit the research to shorts.

| Early warning | Look ahead to | Candidate zones | Follow-up confirmation (not entry authorization) |
|---|---|---|---|
| **SHORT** | Lower prices | Prior bullish candidate OBs, open bullish FVG, confirmed equal lows / swing lows | 1H or 4H upward reaction; possible SHORT profit-taking hypothesis |
| **LONG** | Higher prices | Prior bearish candidate OBs, open bearish FVG, confirmed equal highs / swing highs | 1H or 4H downward reaction; possible LONG profit-taking hypothesis |

For each side, accept **only fully ahead-of-price zones** known at the hypothetical signal cutoff, never an already engulfing or behind-price zone; reject any candidate formed/confirmed in future candles, a future-published source commit, invalidated OBs and filled FVG. Chart liquidity is heuristic, not observed order-book liquidity. Symmetric code paths alone do **not** establish symmetric predictive performance: measure LONG and SHORT independently for each symbol, including null-signal and no-zone cases.

The initial synthetic unit-test suite includes SHORT time-leakage checks and additional LONG tests (BTC/SOL, opposing OB/FVG, filled/invalidated zones, pivot delay, future source/candle, and target ranking). **Test file presence is not evidence of CI execution**; run and record the exact suite results before claiming a pass. Historical LONG signal provenance, sample sizes, target hit rates and trading PnL have not yet been verified.

## Research-only method and next gates

1. Restore the verified 15-Nov early-alert timestamp and its true last-published market + structure commits. If unavailable, report only the *illustrative* cutoff above.
2. For every BTC/SOL LONG/SHORT signal, freeze signal timestamp, direction and price; require source commit publication before the signal, and closed 1H/4H/Daily before the signal.
3. For SHORT rank only **bullish** OB/FVG and confirmed equal lows **strictly below** the signal price; for LONG reverse directions. Verify OB confirmedAt, FVG candle close, and pivot confirmation lag (pivot_span + 1 candle opens to confirmation close). Exclude invalidated/filled features.
4. Pre-register target-touch definition, reversal threshold (e.g. ATR multiple), observation horizon, same-bar ambiguities and transaction costs **before** measuring outcomes. An OHLC bar with both stop and TP touched does not prove hit order.
5. Compare baseline fixed/existing exit versus nearest-zone staggered take-profit and confirmation-driven exits on the *same* signals. Report visit, meaningful bounce, failed/broken zone, PnL, drawdown, exposure, fees and confidence intervals. Keep BTC and SOL separate plus pooled.
6. Repeat prospective paper observation without backfill; do not promote to V7, ATLAS production, real broker orders or notification logic without separately approved evidence gates.

## Safety boundary

No changes to `main`, market publishers, existing workflows, alert tasks, strategy rules, or paper accounts. This research branch adds a standalone analyzer and synthetic tests only. Its CLI neither calls exchanges nor places orders. Confirm provenance independently on GitHub: the CLI accepts explicit commit SHA and time but cannot itself authenticate GitHub metadata offline.
