# ATLAS Quant Engine — Master Roadmap

**Document:** Master roadmap and architecture decisions  
**Version:** 1.0  
**Last updated:** 2026-11-28  
**Status:** Living design document; roadmap decisions recorded, implementation remains staged  
**Repository:** `exchangecurrency11/ATLAS-Quant-Engine`

> This document is the durable project reference for future ATLAS work sessions. Read it before proposing or making architectural changes. Update it when a decision is explicitly changed or a milestone is completed.

---

## 1. Product vision

ATLAS Quant Engine is intended to become a **multi-asset quantitative market-analysis engine**, not a BTC/SOL-only analysis script.

The current BTC/SOL pipeline is the initial engineering and validation environment. It is not the final product boundary.

Target asset classes include:

- **Cryptocurrency:** BTC, ETH, SOL and additional supported instruments.
- **FX / currencies:** major and minor currency pairs.
- **Commodities:** precious metals, energy, agricultural and industrial commodities.
- **Equities:** individual shares across supported exchanges.
- **Indices:** broad-market and sector indices.
- **Futures and other derivatives:** subject to contract metadata, expiry/roll rules, venue and data-provider support.

The long-term goal is one coherent platform that can collect, validate, analyze, compare and monitor instruments across these markets while respecting each market's data conventions.

## 2. Core architecture decisions

These are the currently agreed design principles. They are not permission to bypass the staged review and acceptance gates below.

### 2.1 One logical canonical data universe; independent data lanes

ATLAS should expose one logical canonical market-data layer, but it must **not** depend on one all-or-nothing global collection job.

- Each instrument has an independent ingestion and health state.
- Each instrument/timeframe is validated independently where the market and analysis semantics allow it.
- A BTC, ETH, SOL, commodity, FX pair or equity failure must not automatically block unrelated instruments.
- A failure in one timeframe must not automatically block other valid timeframes for the same instrument.
- Only the failed instrument/timeframe partition is retried or recovered.
- The latest known-good record may be retained, but it must be explicitly marked stale; it must never be presented as current.
- Analyses and signals that require several instruments may run only when all required inputs satisfy their freshness and integrity rules.

The canonical layer is logically unified. Its physical storage may later be partitioned by asset class, venue, instrument or timeframe for scale. A single large JSON file is not a permanent storage requirement.

### 2.2 One standard, market-aware adapters

Use a common internal data contract, with separate provider and market adapters.

The common contract should carry, at minimum:

- Stable instrument identifier and asset class.
- Venue/provider and source identity.
- Timeframe and candle open/close timestamps.
- OHLCV values with explicit units/semantics.
- Source retrieval time and source-data version/hash.
- Validation status and freshness status.
- Market-calendar / session context where applicable.
- Contract identity and expiry/roll metadata where applicable.

Do not assume every market is a 24/7 crypto market. Equities, FX, commodities, indices and futures have different sessions, holidays, time zones, contract definitions and adjustment requirements.

### 2.3 Controlled publication and provenance

- Use a controlled publisher for canonical outputs; avoid multiple uncontrolled writers to the same canonical files.
- Every published analysis result must be traceable to the exact immutable input snapshot, source metadata and calculation version used to create it.
- A timestamp match alone is not proof that two OHLCV datasets are identical.
- Where two outputs are derived from the same input snapshot, their provenance must point to the same snapshot/hash.
- A publication candidate must be validated before it can replace the last known-good publication.
- If validation or calculation fails, retain the previous valid publication.
- If the remote Git branch advances during calculation, do not blindly rebase or push a stale candidate. Fetch the new base, revalidate/recalculate against it, and retry only within a bounded policy.
- Identical inputs and calculation versions should be idempotent and should not create unnecessary commits.

### 2.4 Freshness and partial availability

The canonical dataset must distinguish at least:

- **READY / FRESH:** validated and current for the relevant market/timeframe.
- **STALE:** last known-good data retained, but not current.
- **MISSING:** no valid record exists.
- **INVALID:** data was received but failed validation.
- **DELAYED / UNAVAILABLE:** provider or transport has not supplied the expected data within the allowed window.

Exact enum names may be adapted to existing consumer contracts. The semantics must remain explicit.

Partial availability is allowed at the instrument/timeframe level. It must not be disguised as a fully synchronized snapshot. Cross-asset calculations must declare which inputs are required and enforce their own freshness gates.

### 2.5 Preserve existing research and safety boundaries

- V7, V9.1 and V9.2 research/paper strategy logic is outside the initial P0 publication-integrity scope.
- Existing paper-only restrictions, no-broker-order safeguards, notification boundaries and immutable research-record rules must be preserved.
- Do not modify strategy semantics, paper-account logic, production alerts or trading behavior as an incidental part of data-platform work.
- No live order execution is part of this roadmap unless explicitly approved as a separate future project.

---

## 3. Current baseline (as inspected on 2026-11-28)

This section records the known starting point, not a claim that every live service or workflow has been independently audited.

- The current initial market-data / market-structure implementation is centered on Binance perpetual BTC and SOL data sourced through the existing Coinalyze / Cloudflare Worker path.
- The inspected BTC/SOL structure builder processes 1H, 4H and Daily history and expects six symbol/timeframe groups.
- The current structure builder checks the latest close timestamp against the published market snapshot, but the inspected code does not yet prove full candle-by-candle OHLCV equality between the history inputs and the published market-data records.
- The inspected market-structure module is currently BTC/SOL-oriented. ETH and the wider asset universe are future expansion, not assumed to be implemented by the current P0 code.
- Separate V7, V9.1 and V9.2 research workflows/branches exist. They must remain outside P0 strategy changes.
- E5G, E5H and E5I provide health/recovery/dispatch functions. Their existing bounded retries, workflow allowlists, concurrency and paper-only safeguards must be preserved unless a separately reviewed change is approved.
- V9.2 BTC/SOL and ETH workflows were observed using a shared concurrency group for their combined paper-account outputs. Preserve this protection.
- V9.1 BTC/SOL and ETH workflows use separate concurrency groups while writing to the same research branch but separate output folders. Keep this as a monitored Git race/rebase risk; do not change the groups without a specific concurrency analysis.
- A V9.1 ETH scoreboard path was rechecked and found consistent between its read and `git add` operations.

### 3.1 Repository and working-state snapshot

At the time this document was written:

- Repository: `exchangecurrency11/ATLAS-Quant-Engine`
- Default branch: `main`
- Remote `main` observed at: `e3f11234ec25ff5eafea33158e9652758b85cefa` (2026-11-27 23:04:33 UTC)
- A local P0 worktree was reported at: `C:/Users/HOME/.atlas-ai-duo/worktrees/atlas-quant-engine-ai-duo-20261123-211942-71d632`
- That local worktree was based on: `2b641d007324a48bb39b9addb83f38f562594cfb`
- Its reported uncommitted files were:
  - Modified: `.github/workflows/publish-market-structure.yml`
  - Modified: `.github/workflows/test-market-structure.yml`
  - Added: `scripts/market_structure_publish.py`
  - Added: `tests/test_market_structure_publish.py`

**Important:** The local P0 worktree base is behind the remote `main` SHA recorded above. Before integrating or publishing any P0 work, inspect the current remote branch, compare the worktree and its base, and reconcile safely. Do not assume the local worktree is current.

At the time of this snapshot, the P0 publisher and builder had been inspected, but the full 515-line P0 test file had not yet been reviewed and the complete P0 test suite had not yet been reported as passing. No P0 merge or production deployment is implied by this roadmap.

---

## 4. Phased roadmap

## P0 — Publication integrity and safe recovery foundation

**Goal:** Make the existing BTC/SOL publication path reproducible, provenance-aware and safe before expanding its scope.

### P0-A — One immutable input per publication unit

- Define the canonical immutable OHLCV input snapshot used for a publication.
- Bind each instrument/timeframe result to its exact input content hash, source identity, close time and calculation version.
- Ensure Market Data and Market Structure results that claim to describe the same candles are calculated from the same exact OHLCV content, not merely matching close timestamps.
- Compare OHLCV values candle by candle where both paths currently exist.
- Validate numeric types, finite values, OHLC relationships, non-negative volume, timestamps, duplicates and missing-candle continuity.
- Keep the publication unit independent enough that an unrelated instrument/timeframe failure does not block healthy lanes.

### P0-B — Atomic and guarded publication

- Preserve the existing JSON consumer contract during the first migration.
- Validate all outputs for a publication unit before replacing its last known-good state.
- Publish related canonical outputs from the same input snapshot in one controlled Git transaction/commit where the existing deployment design permits it.
- A failed validation or incomplete calculation must not publish a half-updated output pair.
- Preserve unchanged-content/no-unnecessary-commit behavior.
- Pin the calculation base and relevant source blobs.
- If remote `main` advances, stop the stale candidate; fetch and recalculate against the new base rather than blindly rebasing old calculations.
- Keep the change scope restricted to intended output paths.

### P0-C — Independent recovery without cross-asset blockage

- Retain the single logical canonical dataset.
- Retry the failed instrument/timeframe lane independently with bounded attempts and time windows.
- Preserve last known-good data with an explicit stale state when a refresh fails.
- Do not allow stale or invalid inputs into analyses that require fresh data.
- Keep unrelated healthy lanes publishable.
- Maintain one controlled publisher to serialize canonical writes and avoid lost updates.

### P0-D — Tests and acceptance gates

Required tests include:

1. Identical input and calculation version produce no unnecessary new commit.
2. A single-candle OHLCV mismatch is rejected even when close timestamps match.
3. Missing, duplicate, malformed, non-finite, negative-volume and invalid-OHLC records are rejected.
4. Missing candle continuity is detected according to the relevant market calendar.
5. A failure in one instrument/timeframe does not overwrite or block unrelated healthy records.
6. A stale last-known-good record remains clearly stale and cannot be used as fresh input.
7. Failure while building any related output preserves the previous valid publication.
8. A remote branch advance causes a fresh-base validation/recalculation, not a stale rebase/push.
9. Concurrent publication attempts cannot silently lose a valid update.
10. Existing consumers and workflow contracts remain compatible.

**P0 completion gate:** Reproducible outputs tied to exact input hashes; safe failure behavior; no partial/corrupt publication; tests passing; no change to V7–V9.2 strategy or paper-account semantics.

## P1 — Canonical multi-asset data contract and instrument registry

**Goal:** Generalize the data model beyond the current BTC/SOL implementation.

- Define stable instrument IDs, asset classes, venues, quote/base currencies, contract specifications and provider mappings.
- Add per-instrument and per-timeframe freshness/health state.
- Version the canonical schema and provide a compatibility/migration plan for existing JSON consumers.
- Introduce market calendars, sessions, holidays, time zones and asset-specific candle-close rules.
- Add ETH as an explicit expansion target after the shared contract and compatibility tests are approved.
- Support partial updates without implying that the entire universe was refreshed at one instant.
- Define data-quality and source-precedence policies.

**P1 completion gate:** A new supported instrument can be registered and validated without changing unrelated instrument pipelines or hard-coding its identity into shared analysis logic.

## P2 — Provider adapters and resilient ingestion

**Goal:** Add asset-class-aware data acquisition and recovery.

- Separate provider adapters from canonical normalization and analysis.
- Add provider health, latency, quota/rate-limit and error observability.
- Implement bounded retries, backoff, caching and recovery windows.
- Define primary/fallback provider policy; fallback data must pass the same canonical validation and carry its own provenance.
- Support instrument-specific and timeframe-specific recovery.
- Handle exchange sessions, market holidays, futures expiry/roll and adjusted/unadjusted series as explicit domain rules.
- Avoid unnecessary repeated provider calls; measure quota use and latency before selecting cache windows.

**P2 completion gate:** A provider outage or bad response affects only the dependent instruments/lanes, and a fallback is never silently treated as identical to the primary source.

## P3 — Shared quantitative analysis and asset-specific modules

**Goal:** Reuse common analysis capabilities without assuming every market behaves like crypto.

- Shared OHLCV indicators and time-series primitives.
- Market structure: swings, BOS/CHoCH, FVG, candidate order blocks and liquidity estimates, with clear heuristic labeling.
- Supply/demand mapping and multi-timeframe context.
- Trend, momentum, volatility and regime analysis.
- Asset-class-specific rules for sessions, contract rolls, corporate actions and market microstructure where supported.
- Cross-asset relationships and relative-strength analysis.
- Explicit freshness/provenance requirements for every analysis and signal.
- Research/paper evaluation separated from production analysis outputs.

**P3 completion gate:** The same analysis framework can operate on different asset classes through explicit adapters/rules, with tests that prevent crypto-specific assumptions from leaking into other markets.

## P4 — Quant intelligence, monitoring and application experience

**Goal:** Turn the engine into an observable, usable multi-asset platform.

- Unified market and instrument dashboards.
- Data-health, source-latency, publication and recovery monitoring.
- Explainable analysis cards and signal/alert history.
- Cross-asset watchlists, scans and comparative views.
- Configurable alerts with explicit freshness and confidence gates.
- Research/paper performance reporting and audit trails.
- Application/API packaging after core data and analysis contracts stabilize.
- Operational controls, permissions and deployment safeguards.

**P4 completion gate:** Users can monitor supported markets from one application while every displayed value and analysis remains traceable to source, timestamp, validation and calculation version.

---

## 5. Non-negotiable engineering guardrails

1. **No silent stale data:** old data must be visibly stale and excluded from fresh-data decisions.
2. **No false synchronization:** matching timestamps alone do not prove matching candle content.
3. **No global failure coupling:** one instrument/timeframe outage must not stop unrelated healthy lanes.
4. **No blind stale rebase:** a candidate calculated from an old base must be recalculated against the new base.
5. **No partial publication:** related outputs must pass validation before the publication transaction is accepted.
6. **No uncontrolled writers:** canonical writes must be serialized or use an equivalent race-safe compare-and-swap protocol.
7. **No hidden strategy changes:** P0 data work must not alter V7–V9.2 strategy or paper-account logic.
8. **No live orders:** paper-only and no-broker-order safeguards remain in force.
9. **No provider assumptions:** market calendars, contract metadata and source semantics must be explicit.
10. **No premature scale claims:** performance and provider capacity must be measured before broad universe expansion.

## 6. Working protocol for future ChatGPT sessions

At the start of a new ATLAS conversation:

1. Read this document first: `docs/ATLAS_QUANT_ENGINE_MASTER_ROADMAP.md`.
2. Read the current repository state and the latest remote `main` SHA; do not rely on the historical SHA in this document.
3. Inspect the current P0 worktree/branch and its uncommitted changes before suggesting commands.
4. Confirm which roadmap phase and acceptance gate is active.
5. Keep implementation isolated from `main` until tests and review pass.
6. Update this document when a decision changes, a risk is resolved or a milestone is completed.
7. Record actual evidence (commit SHA, test command/results, workflow run or review) when marking a task complete. Do not mark a task complete based only on intention or a successful dispatch request.

### Current next actions

- Finish reviewing `scripts/market_structure_publish.py`, `build_market_structure.py` and `market_structure.py` together as one provenance chain.
- Review all of `tests/test_market_structure_publish.py` and identify missing acceptance tests.
- Reconcile the local P0 worktree with the current remote `main` before any integration attempt.
- Revise the P0 design around independent instrument/timeframe lanes inside one logical canonical data universe.
- Implement and test only within the isolated P0 worktree; do not push to `main` or deploy until explicitly reviewed and approved.

---

## 7. Decision log

| ID | Decision | Rationale |
|---|---|---|
| ADR-001 | ATLAS is a multi-asset quant engine, not a BTC/SOL-only tool. | BTC/SOL is the initial validation scope; the product target includes crypto, FX, commodities, equities, indices and derivatives. |
| ADR-002 | One logical canonical data universe with independent instrument/timeframe lanes. | Keep a unified view without allowing one failed instrument or timeframe to block unrelated data. |
| ADR-003 | Retain last known-good data only with explicit stale status. | Preserve continuity without presenting old data as current. |
| ADR-004 | Cross-asset analysis has stricter freshness gates than independent single-instrument analysis. | Prevent incomplete or asynchronous inputs from producing misleading combined signals. |
| ADR-005 | Use one controlled canonical publisher and provenance-linked publication transactions. | Prevent races, mixed-source outputs and partial publication. |
| ADR-006 | P0 improves current BTC/SOL integrity while keeping the design reusable for more asset classes. | Avoid premature expansion and avoid rebuilding the architecture later. |
| ADR-007 | Existing V7–V9.2 strategy/paper logic and no-order safeguards remain out of P0 scope. | Keep data-platform hardening separate from research-strategy changes. |
| ADR-008 | Keep `main` untouched during isolated P0 development until review and acceptance gates pass. | Protect the active data and research system. |

---

**End of roadmap — update this file as the project evolves.**
