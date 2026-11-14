# ATLAS Core — E3 full raw-OHLC replay / V9.2 baseline parity

**Purpose:** Re-download the previously studied 159 official Binance USD-M
monthly 1H ZIP files, verify each by the publisher's SHA256 CHECKSUM and
prior sealed monthly manifest, replay V9.2's 1H BOS / up-to-4H retest / next
1H opening entry / stop-first / TP1-3 historical strategy for BTC, ETH,
SOL, and demand exact matches to 51 historical trade records across two
periods (2022–24, 2024–26).

**Strict scope:** historical engineering parity, NOT forward performance,
independent code implementation, new alpha, actual execution, or order
placement. Existing main, all V7/V9.2 paper journals, candidate branches,
ETH guard, BTC/SOL alerts, cards, and automations untouched. This branch is
a descendant of the separate ATLAS Core E2 research branch.

## Frozen six-partition data and evidence

- Early: May 2022 – Sep 2024 monthly archives for BTC/ETH/SOL (87 ZIPs);
  scored Oct 2022 – Sep 2024.
- Later: Oct 2024 – Sep 2026 for BTC/ETH/SOL (72 ZIPs);
  scored Oct 2024 – Sep 2026.
- Prior E2 and historical oracle: 51 trades (BTC 10+5, ETH 10+6,
  SOL 12+8), already inspected for strategy design.
- Every ZIP SHA-256 must agree both with Binance's currently downloadable
  .CHECKSUM and *the prior immutable archived manifest*. Missing or changed
  source fails closed, rather than silently changing a dataset.
- Nine source modules are pinned to exact Git blob hashes before download.
  Candidate parameters, time windows, frozen cutoffs, and control references
  are not changed.
- Replay uses the original V9.2 source text compiled in memory using the
  earlier reviewed BASELINE-only research fork and O(N) exact-prefix
  indicator caches, preserving the original source file on disk. It is not
  an independently coded/validated trade simulator.
- The output compares all 51 trade rows (entry UTC, retest UTC, side,
  exit UTC, exit reason, entry, riskPct, R9) and exact V9.2 per-partition
  aggregate R9/R25, BOS-watch counts, retest veto counts, risk rejects.
- No net-new trading hypothesis, selection or model promotion.

### Pass conditions

All nine source pins, all 159 SHA256 files and old manifest hashes,
all six complete period-asset bar counts, all 51 rows, 9/25bps aggregate
metrics and source safety flags pass. Any mismatch fails CI. E1 and E2
tests must pass again. No summary is written to existing ledgers.

### Reproduction

Run from repository root, with Python 3 and internet access to the official
Binance public archive:

    python3 -m unittest research.atlas_core_v2.test_atlas_core_e3 -v
    python3 -m research.atlas_core_v2.atlas_core_e3 --workers 6

On Actions the job is **manual/push only**, never scheduled, has
**contents: read** only, and checks out this branch with credentials
persistence disabled. It uploads its report under research/atlas_core_v2/output/
as a temporary artifact; no report is committed to GitHub.

If publisher website access fails, the E3 process must remain **unverified**,
not be relabeled successful using previously existing reports.

### After E3

If parity succeeds, next stages should:
1. Derive a separately implemented order-execution accounting engine,
   compare against the frozen historical reference, and test edge cases
   such as gaps, simultaneous stop/TP, realistic varying spreads/funding.
2. Build an asset-shared portfolio time tape with a declared total risk
   budget; prevent concurrent trade overlap from hiding true exposures.
3. Register (before looking at new prices) an ATLAS Core neutral-candidate
   specification and independent prospective start; do not use 2022–26
   again as forward evidence.
