# V9.2 Stable — three-part hardening audit

**Research shadow: no modifications to original paper records or strategy, no real orders.**

## Risk policy for *new* capped shadow book

- Per-position budget: **10 USDT** inclusive of hypothetical stress fees/slippage.
- Combined concurrent budget: **20 USDT**; over-cap and missing data fail closed.
- Original V9.2 **100 USDT** per trade remains unchanged; not retroactively rewritten.

## Source completeness

| Source | Saved / expected | Missing UTC hours | Consecutive recent hours |
|---|---:|---|---:|
| BTC_SOL | 110/179 | 2026-11-12T14:00:00Z, 2026-11-13T02:00:00Z, 2026-11-13T14:00:00Z, 2026-11-14T18:00:00Z, 2026-11-14T19:00:00Z, 2026-11-14T20:00:00Z, 2026-11-14T23:00:00Z, 2026-11-15T00:00:00Z, 2026-11-15T03:00:00Z, 2026-11-15T04:00:00Z, 2026-11-15T05:00:00Z, 2026-11-15T06:00:00Z, 2026-11-15T07:00:00Z, 2026-11-15T10:00:00Z, 2026-11-15T12:00:00Z, 2026-11-15T13:00:00Z, 2026-11-15T14:00:00Z, 2026-11-15T16:00:00Z, 2026-11-15T18:00:00Z, 2026-11-15T19:00:00Z, 2026-11-15T20:00:00Z, 2026-11-15T22:00:00Z, 2026-11-15T23:00:00Z, 2026-11-16T00:00:00Z, 2026-11-16T03:00:00Z, 2026-11-16T04:00:00Z, 2026-11-16T05:00:00Z, 2026-11-16T06:00:00Z, 2026-11-16T07:00:00Z, 2026-11-16T10:00:00Z, 2026-11-16T12:00:00Z, 2026-11-16T13:00:00Z, 2026-11-16T14:00:00Z, 2026-11-16T15:00:00Z, 2026-11-16T16:00:00Z, 2026-11-16T17:00:00Z, 2026-11-16T19:00:00Z, 2026-11-16T21:00:00Z, 2026-11-16T23:00:00Z, 2026-11-17T00:00:00Z, 2026-11-17T01:00:00Z, 2026-11-17T05:00:00Z, 2026-11-17T06:00:00Z, 2026-11-17T07:00:00Z, 2026-11-17T08:00:00Z, 2026-11-17T09:00:00Z, 2026-11-17T10:00:00Z, 2026-11-17T12:00:00Z, 2026-11-17T15:00:00Z, 2026-11-17T16:00:00Z, 2026-11-17T17:00:00Z, 2026-11-17T18:00:00Z, 2026-11-17T20:00:00Z, 2026-11-17T23:00:00Z, 2026-11-18T00:00:00Z, 2026-11-18T05:00:00Z, 2026-11-18T06:00:00Z, 2026-11-18T07:00:00Z, 2026-11-18T08:00:00Z, 2026-11-18T11:00:00Z, 2026-11-18T15:00:00Z, 2026-11-18T16:00:00Z, 2026-11-18T17:00:00Z, 2026-11-18T23:00:00Z, 2026-11-19T00:00:00Z, 2026-11-19T04:00:00Z, 2026-11-19T05:00:00Z, 2026-11-19T06:00:00Z, 2026-11-19T07:00:00Z | 14 |
| ETH | 116/178 | 2026-11-12T13:00:00Z, 2026-11-12T14:00:00Z, 2026-11-12T15:00:00Z, 2026-11-14T19:00:00Z, 2026-11-14T20:00:00Z, 2026-11-14T23:00:00Z, 2026-11-15T00:00:00Z, 2026-11-15T03:00:00Z, 2026-11-15T04:00:00Z, 2026-11-15T05:00:00Z, 2026-11-15T06:00:00Z, 2026-11-15T10:00:00Z, 2026-11-15T12:00:00Z, 2026-11-15T13:00:00Z, 2026-11-15T14:00:00Z, 2026-11-15T18:00:00Z, 2026-11-15T19:00:00Z, 2026-11-15T20:00:00Z, 2026-11-15T22:00:00Z, 2026-11-15T23:00:00Z, 2026-11-16T00:00:00Z, 2026-11-16T03:00:00Z, 2026-11-16T04:00:00Z, 2026-11-16T05:00:00Z, 2026-11-16T06:00:00Z, 2026-11-16T07:00:00Z, 2026-11-16T10:00:00Z, 2026-11-16T12:00:00Z, 2026-11-16T13:00:00Z, 2026-11-16T14:00:00Z, 2026-11-16T15:00:00Z, 2026-11-16T17:00:00Z, 2026-11-16T19:00:00Z, 2026-11-16T21:00:00Z, 2026-11-16T23:00:00Z, 2026-11-17T01:00:00Z, 2026-11-17T02:00:00Z, 2026-11-17T03:00:00Z, 2026-11-17T05:00:00Z, 2026-11-17T06:00:00Z, 2026-11-17T07:00:00Z, 2026-11-17T09:00:00Z, 2026-11-17T12:00:00Z, 2026-11-17T15:00:00Z, 2026-11-17T16:00:00Z, 2026-11-17T18:00:00Z, 2026-11-17T20:00:00Z, 2026-11-17T21:00:00Z, 2026-11-17T23:00:00Z, 2026-11-18T00:00:00Z, 2026-11-18T05:00:00Z, 2026-11-18T06:00:00Z, 2026-11-18T08:00:00Z, 2026-11-18T11:00:00Z, 2026-11-18T12:00:00Z, 2026-11-18T15:00:00Z, 2026-11-18T17:00:00Z, 2026-11-18T20:00:00Z, 2026-11-18T23:00:00Z, 2026-11-19T01:00:00Z, 2026-11-19T05:00:00Z, 2026-11-19T13:00:00Z | 8 |

## Backtest / forward snapshot parity

- Matched 1H source hours: **100**.
- Coin-hour replay checks: **300**.
- Actually observed open-position snapshots: **0**; pending-retest snapshots: **0**; closed-exit events: **0**.
- Older immutable hours with reduced direct-veto diagnostics: **1**; accepted only when unchanged V9.1/V9.2 parity and zero veto were independently confirmed.
- Stored BOS/retest state parity is checked, but when no real paper trades exist, trade-specific entry/stop/TP parity remains UNPROVEN outside synthetic unit tests.
- Comparison is based on independently stored forward 1H snapshots and their prior V7/V9.1 reference records, not a claim of executable live fills.
- Original V9.2 already replays the same closed OHLCV as of each hour; audit double-checks serialized strategy state, BOS/retest, stop/TP fields when open, and timeframe stamps.
- Latest strict paper admission gate: **READY FOR REVIEW**.

## New-entry review

- BTCUSDT: NO_NEW_ENTRY_CANDIDATE.
- ETHUSDT: NO_NEW_ENTRY_CANDIDATE.
- SOLUSDT: NO_NEW_ENTRY_CANDIDATE.

**Limits:** Data gaps are not backfilled; risk limits cannot prevent stop gaps, funding/variable spreads/slippage are not fully modeled; no strategy promotion.
