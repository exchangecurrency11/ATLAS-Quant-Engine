# ATLAS Core v0 — audited, research-only architecture (2026-11-14)

## Scope and immutable boundaries

This branch descends from research/btc-sol-event-regime-forward-20261114. It is NOT
main, does NOT update BTC/SOL or ETH frozen engines or their markers, does not
affect V7/V9.2 virtual books, alerts, notification cards, schedules or live feeds.
No broker keys, network requests, orders or automation mutations. This is a
research prototype and evidence-qualification harness, not a trading strategy.

## Architecture contract (planned modularity)

1. **Source ledger:** immutable symbol/exchange/instrument ID, archive path,
   archive SHA-256, known-at timestamp, time zone and original availability.
   Separate the 159 *previously reviewed* archived ZIPs from untouched future.
2. **Market adapters:** asset calendar (24/7 vs sessions/holidays), tick size,
   contract multiplier, margin mechanics, currency, availability of a short
   instrument, fee/funding, spread/slippage, auction/gap rules. Refuse missing
   specifications rather than silently importing crypto assumptions to gold,
   equities or ETFs.
3. **Causal feature layer:** 1H decisions can use ONLY fully closed 1H, 4H
   and Daily bars; a daily feature becomes eligible only after UTC daily close.
   All joins must record feature calculation timestamp AND known-at timestamp.
   No centered moving averages, current unclosed candles or revised macro data
   treated as known in the past.
4. **Proposal layer:** *predeclared* families: BOS-retest momentum/trend, a
   basic trend-following benchmark, a no-trade benchmark. Asset-neutral
   normalized features first; no coin-specific fitted thresholds in universal
   core. Candidate feature sets are to be decided BEFORE their OOS test.
5. **Execution layer:** next-open hypothetical entry; stop-first on
   intrabar ambiguity, and adverse opening gap for stops. Transaction cost
   scenarios at 9/25/50 bps per side are illustrative stress tests for
   existing crypto-perp research; not a transfer to equity/metal brokers.
   Add exchange- and epoch-specific spread/slippage, funding and market impact
   only when supported by timestamped data, with missing inputs reported.
6. **Portfolio layer:** chronological cross-asset shared-capital tape,
   concurrent risk and exposure caps, correlation/sector clustering, trades
   overlapping in time, drawdown and drawdown duration. Do NOT sum per-asset
   maximum drawdown or average their PF to invent portfolio metrics.
7. **Evidence registry:** immutable frozen spec, code/data hashes, all tested
   variants and discarded trials, parameters, data windows, trial budget,
   time-aware cross-validation folds, unmodified live shadows and the decisions
   that preceded each test. No automatic promotion.

## Validation protocol, fixed before new development

- **Tier 0 (E0)**: frozen historical BTC/SOL evidence audit. Git-blob pins,
  source invariants, costs, counts, lack of independent OOS. Its purpose is to
  uncover unjustified confidence, not optimize or claim positive future alpha.
- **Tier 1 (E1)**: deterministic generated-data unit tests for closed-bar
  multi-timeframe as-of, gap/stop-first and two-sided cost arithmetic.
  Synthetic tests prove code properties, NOT profitability.
- **Tier 2 (pending)**: parity test on a fixed set of recorded V9.2
  reference trades for all 3 assets with identical entries, stop/TP and cost
  math, making the frozen V7/V9.2 engine a read-only oracle.
- **Tier 3 (pending)**: preregistered expanding walk-forward, purged/embargoed
  overlapping outcome windows, regime and per-direction slicing, fixed
  search budget, negative controls, multiple-testing corrections and block
  bootstrap uncertainty ranges. Purged CV is NOT automatically independent
  validation when the dataset informed candidate selection.
- **Tier 4 (pending)**: independent prospective monthly SHA-256 source
  snapshots from the preexisting ETH freeze 2026-11-14 00:00 UTC and BTC/SOL
  freeze 2026-11-15 00:00 UTC. Core must have its *own* prospective freeze
  later, and cannot relabel older data as fresh.
- **Tier 5 (pending)**: asset-class portability (gold/silver, equity index,
  individual stocks), including session gaps and adapted cost engines; assess
  each class separately. Cross-asset "universal" claims require independent
  evidence for each class and combined portfolio simulation.

### Promotion and uncertainty policy

We aim for sustainable net-positive R, manageable maxDD and PF after real
frictions, NOT an optimized 55% win-rate claim. 30 historical transactions is
a *provisional administrative minimum* for review; it is NOT a statistical
sample-size proof. All candidate directions, minimum live exposure period,
family-wise/multiplicity control and acceptance hurdles must be registered
before new independent data accrues. A 7-trade SOL 85.7% sample is not a
forecast. When funding, market impact, portfolio tape, ETH parity or a complete
dataset is absent, say UNKNOWN and block promotion.

## Current E0: no fresh performance claim

Inputs:
- forward/btc_sol_v93_causal_regime_20261114/historical.json
- forward/btc_sol_v93_prospective_20261114/frozen_spec.json

Existing 2022–2026 history had already informed candidate choice. Existing
report says 159 SHA256-verified Binance monthly archives; E0 **checks the report
and file identities**, not the original 159 archive bytes again. E0 aggregate
PF and maxDD are intentionally null, because chronological interleaving of
trade data across assets is needed. ETH evidence is outside E0, not silently
imputed from BTC/SOL.

Run from repository root:

    python3 -m unittest research.atlas_core_v0.test_atlas_core_v0 -v
    python3 research/atlas_core_v0/atlas_core_v0.py

Outputs confined to research/atlas_core_v0/output/ and uploaded as CI
artifacts only. Workflow has contents: read and no scheduled triggers.

## Scientific and documentation references

- Bailey et al. (2017), Probability of Backtest Overfitting:
  https://escholarship.org/uc/item/4w1110bb
- Bailey and López de Prado (2014), Deflated Sharpe Ratio:
  https://davidhbailey.com/dhbpapers/deflated-sharpe.pdf
- Harvey, Liu, Zhu (2016), multiple testing:
  https://academic.oup.com/rfs/article-abstract/29/1/5/1843824
- Moskowitz, Ooi, Pedersen (2012), time-series momentum across futures:
  https://www.sciencedirect.com/science/article/pii/S0304405X11002613
- Nefedov (2026, preprint, provisional evidence), crypto factor backtest
  overfitting and explicit friction costs:
  https://papers.ssrn.com/sol3/papers.cfm?abstract_id=7350238
- Crypto order execution / failed fills (2025):
  https://www.tandfonline.com/doi/full/10.1080/14697688.2025.2515933
- Binance public market data official documentation and CHECKSUM:
  https://github.com/binance/binance-public-data

These sources motivate research controls; none validates ATLAS alpha.
