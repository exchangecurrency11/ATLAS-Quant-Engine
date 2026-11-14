# ATLAS Core — E2 three-asset V9.2 historical ledger parity

**Research-only; completed 2026-11-14.** This independent branch extends
research/atlas-core-v0-evidence-20261114 without editing any existing branch,
production V7/V9.2 virtual book, Ethereum/BTC/SOL candidate, automation,
GitHub main, notification, or 2026-11-14/15 prospective freeze.

## Research objective

Compare all saved V9.2 baseline trades across 3 assets and the previously
inspected 2022–2024 and 2024–2026 windows to separate historical witness
reports, identifying mismatched entry time, exit time, direction and net R9.
Audit metadata, chronological watch->retest->entry->exit constraints, and
rounding-aware transaction-cost stress; count simultaneous exposure across
assets without inventing portfolio monetary P&L.

This is a **cross-report trade-ledger identity test**, NOT a raw-OHLC replay,
independent external implementation, reliable trading win rate or newly
validated algorithm. Every input is previously known to the strategy designers.

### Pinned research inputs (Git object SHA1 and independently SHA256)

- primary: forward/v92_filter_ablation_20261113/historical.json
  blob d09ac4830e9ef6ce635bce2e8ebde818242243cb
- early witness: forward/v92_older_eth_sol_regimes_20261113/historical.json
  blob ea56be2efb022fe69ae48f9e8a1aefd8bffcc1e2
- late witness: forward/v92_three_asset_correlation_20261113/historical.json
  blob cde7de239de86934273b791566d8a8d1ca4b85a9

All are SHA-256-verified-source **historical report outputs** stored earlier
on the research branch; this task verifies their Git blob identity but does
not re-download all Binance monthly archive bytes.

### Exact acceptance criteria

1. Exactly 51 V9.2 *baseline* trades: BTC (10+5), ETH (10+6), SOL (12+8).
2. Every trade key in each of six partitions is identical across its primary
   and witness report: entry, exit, side, and net R9 (9bps/side).
3. Historical watch, retest, entry and exit timestamps are strictly ordered
   where the original specification permits equality at retest and entry.
   This only tests witness metadata; not full raw-signal known-at timing.
4. 9bps rounded-tape aggregate within 0.00002 R of sealed report; exact
   summary equality for original 25bps source reports; independent repricing
   using rounded riskPct within 0.0001 R per partition. Financial fills,
   funding, dynamic spread and execution are not independently verified.
5. All historical data continue to be marked non-independent and NOT forward.
6. Cross-asset concurrent positions computed from [entry, exit) time spans
   only; portfolio PF and maxDD deliberately null without a capital-normalized
   shared chronological position book.

### Commands from root

    python3 -m unittest research.atlas_core_v0.test_atlas_core_v0 -v
    python3 -m unittest research.atlas_core_v1.test_atlas_core_e2 -v
    python3 -m research.atlas_core_v1.atlas_core_e2

All generated reports under research/atlas_core_v1/output/.
No write privileges in CI; report is uploaded as temporary artifact.

## Next experiment E3, not yet implemented

Create a read-only signal-by-signal OHLC replay using a *separately pinned*
strategy engine with exact V9.2 stop and TP behavior, and verify source-closed
1H, 4H, Daily candles against the same 51 historical trade identities.
Separate engine parity from live independent validation. After E3:
- pre-register ATLAS Core hypotheses, validation folds, trial budget and
  survival thresholds;
- perform purge/embargo around overlapping outcomes, stress execution fees,
  preserve complete chronological multi-asset tape;
- wait for untouched post-freeze prospective source to qualify true out of
  sample. Historical matches can NEVER be labeled newly profitable.
