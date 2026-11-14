# BTC/SOL V9.3 independent forward monthly SHA256 refresh trigger

**Research branch only; no production changes.**

Updating this marker explicitly triggers the independent GitHub Actions
workflow `.github/workflows/btc-sol-v93-forward-20261114.yml`.
It replays the frozen BTC/SOL V9.2 baseline and only two high-volatility
candidates, and cross-checks against the unchanged original V9.3 six-stream
reference.

- **Freeze:** 2026-11-15T00:00:00Z. Older signal watch, retest, entry or
  exit records cannot be called a new prospective observation.
- **Data:** official Binance USD-M 1H monthly archives and vendor-provided
  SHA256. Do not count incomplete months or create fake fills.
- **Next possible month:** 2026-11, but do not assume its ZIP exists on Dec 1.
  Binance ordinarily publishes monthly source files on the first Monday
  of the next month (2026-12-07); check actual availability and checksum.
- If source, candidate script or original engine SHA256 differs from
  `frozen_spec.json`, fail closed. Do not alter frozen thresholds to fit
  results; version a separate prospective experiment instead.
- No live orders, BTC/SOL alerts, user reporting schedules or current
  V7/V9.2/ETH daily security writes. Nothing promotes automatically.

**Initial setup:** 2026-11-14 UTC; October preflight only, zero future trades.
