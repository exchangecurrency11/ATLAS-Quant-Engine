# V9.2 Stable — three-part hardening audit

**Research shadow: no modifications to original paper records or strategy, no real orders.**

## Risk policy for *new* capped shadow book

- Per-position budget: **10 USDT** inclusive of hypothetical stress fees/slippage.
- Combined concurrent budget: **20 USDT**; over-cap and missing data fail closed.
- Original V9.2 **100 USDT** per trade remains unchanged; not retroactively rewritten.

## Source completeness

| Source | Saved / expected | Missing UTC hours | Consecutive recent hours |
|---|---:|---|---:|
| BTC_SOL | 37/40 | 2026-11-12T14:00:00Z, 2026-11-13T02:00:00Z, 2026-11-13T14:00:00Z | 12 |
| ETH | 36/39 | 2026-11-12T13:00:00Z, 2026-11-12T14:00:00Z, 2026-11-12T15:00:00Z | 35 |

## Backtest / forward snapshot parity

- Matched 1H source hours: **34**.
- Coin-hour replay checks: **102**.
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
