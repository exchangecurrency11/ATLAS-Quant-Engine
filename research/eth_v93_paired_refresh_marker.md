# ATLAS ETH V9.2 vs BOS+EMA — isolated prospective monthly refresh marker

**Research only.** This file is a safe push trigger for the independent GitHub Actions
workflow on `research/eth-v93-prospective-paired-20261113`.

### Frozen source and date

- First genuinely prospective setup may start at **2026-11-14T00:00:00Z** (03:00 Turkey).
- No historical trades before that UTC instant may enter either forward account.
- The first *complete monthly official Binance 1H archive* containing any new
  observations is **2026-11**, and it is not complete until **2026-12-01T00:00:00Z**.
  Publication of the validated SHA256 zip can be later than month end.
- If published and SHA256 verified, update only this file in this research branch
  with an actual UTC refresh date to trigger the monthly 6-stream frozen replay
  and read-only ETH V9.2 vs BOS+EMA comparator.
- Replaying in a research branch does not make GitHub Actions run itself on a timer.
  There is **no scheduled job or notification**; the trigger is an explicit commit.
- V7, V9.2 production, existing paper accounting, all user alerts and analysis
  schedules remain untouched. Never merge research output without separate approval.

Initial setup: 2026-11-13T22:32:56Z. No eligible post-freeze closed trades.
