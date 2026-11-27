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


---

## 8. Session checkpoint — 2026-11-28

This checkpoint records the latest important developments discussed after Roadmap v1.0 was created. It is an evidence/status note, not a claim that the local machine was independently inspected during this update.

### 8.1 Roadmap persistence

- The user explicitly requested that every important ATLAS development, architecture decision, risk and next action be recorded here so a new chat can resume without relying on chat history.
- The roadmap was created on the isolated branch `docs/atlas-quant-engine-roadmap`.
- The repository README on that branch now links to this roadmap and states the multi-asset product vision.
- The documentation branch is separate from `main`; no roadmap merge to `main` has been performed.
- The latest remote `main` head was rechecked on 2026-11-28 and remained `e3f11234ec25ff5eafea33158e9652758b85cefa` (commit: `Update BTC SOL market structure data`).
- The roadmap/documentation branch latest commit after README update was `a4eee8e238eabf8ebac4b627b60cbcf98839d3e0`.

### 8.2 Latest reported P0 local worktree state

The following was supplied by the user from Windows PowerShell on 2026-11-27. It has not been re-inspected on the user's computer since that report:

- Main local clone: `C:/Users/HOME/atlas-quant-engine-ai-duo`
- P0 worktree: `C:/Users/HOME/.atlas-ai-duo/worktrees/atlas-quant-engine-ai-duo-20261123-211942-71d632`
- P0 branch: `ai/duo-20261123-211942-71d632`
- P0 worktree base: `2b641d007324a48bb39b9addb83f38f562594cfb`
- Reported working-tree paths:
  - Modified: `.github/workflows/publish-market-structure.yml`
  - Modified: `.github/workflows/test-market-structure.yml`
  - Added: `scripts/market_structure_publish.py`
  - Added: `tests/test_market_structure_publish.py`
- Reported patch summary: 715 insertions and 18 deletions across four paths.
- `git diff --check` showed no whitespace-error diagnostics; it emitted LF-to-CRLF line-ending warnings.
- The local P0 base `2b641d...` is behind the remote `main` head `e3f112...` observed on 2026-11-28. This discrepancy must be reconciled before any integration. Do not assume the worktree is based on current `main`.
- No completed P0 test-suite result, PR, merge or deployment was evidenced in the supplied logs.

### 8.3 Code review findings and open gaps

The user supplied the contents of `scripts/market_structure_publish.py` and `build_market_structure.py` for review.

Observed strengths in the proposed publisher:

- Pins the Git blobs for `market_data.json`, `build_market_structure.py` and `market_structure.py` to the build base.
- Checks that the working copies match the pinned blobs before and after calculation.
- Hashes the history input files before calculation and rejects changes during calculation.
- Builds a candidate commit intended to change only `market_structure_data.json`.
- Fetches remote `main` and stops if the base or pinned source blobs changed.
- Uses a pre-push check to verify the candidate's parent/destination and recheck closure consistency.

Important gaps to close before P0 acceptance:

1. The supplied builder currently expects all six BTC/SOL × 1H/4H/Daily groups together. This all-six requirement is incompatible with the agreed independent-lane failure isolation if retained as the only publication gate.
2. The supplied builder checks the latest close timestamp in the downloaded history against `market_data.json`, but does not prove candle-by-candle equality of OHLCV contents. Matching close timestamps alone are insufficient provenance.
3. The current builder and market-structure logic are BTC/SOL-specific. That is acceptable as a first P0 validation scope only if the data contract and publication design are not permanently hard-coded to those symbols.
4. The complete `tests/test_market_structure_publish.py` (reported as 515 lines) and full workflow diffs still require review.
5. Test execution and acceptance evidence are still outstanding in the supplied record.

### 8.4 Current agreed architecture clarification

The user confirmed the desired model:

- One logical canonical ATLAS data universe.
- Independent collection, validation, retry and health state for each instrument/timeframe lane.
- A fault in one lane must not block healthy BTC, ETH, SOL or future asset-class lanes.
- Last-known-good data may be retained only with an explicit stale marker and must not pass a freshness gate.
- A unified file or logical dataset must not become a global all-or-nothing refresh barrier.
- Canonical writes still need a controlled, race-safe publisher/transaction mechanism so independent lane updates cannot overwrite each other.
- This architecture must scale beyond crypto to FX, commodities, equities, indices and supported derivatives.

### 8.5 Immediate next work — P0 remains active

Do these in order; do not jump to P1 yet:

1. Re-open and review the full P0 test file, both workflow diffs, `market_structure.py`, `build_market_structure.py` and `scripts/market_structure_publish.py` as one end-to-end data/provenance chain.
2. Add or confirm tests for exact candle OHLCV equality, stale/missing/invalid lane behavior, one-lane failure isolation, concurrent publication and safe recovery.
3. Decide the smallest compatible P0 implementation that preserves existing BTC/SOL consumers while removing the global six-group failure dependency.
4. Reconcile the P0 worktree against the current remote `main` SHA. Prefer a fresh isolated worktree from current `main` and selectively reapply/review the P0 patch if the old base cannot be safely reconciled. Never blindly rebase a candidate calculated from stale inputs.
5. Run the full relevant test suite and record exact commands/results.
6. Only after review and explicit approval, prepare a PR or controlled integration. Keep `main`, active research workflows and deployments untouched until then.

**Current phase:** P0 — publication integrity, exact provenance and independent-lane recovery.  
**Current state:** design agreed; isolated implementation under review; tests and safe base reconciliation pending.  
**Next checkpoint:** full P0 test/workflow review and fresh-base reconciliation.


### 8.6 Initial review of P0 publisher tests — first 180 lines received

On 2026-11-28, the user supplied lines 1–180 of the local `tests/test_market_structure_publish.py` from the P0 worktree. Only this excerpt has been reviewed so far; conclusions below are limited to the supplied lines.

**Coverage visible in lines 1–180:**

- Closure validation tests require JSON boolean `ok: true`, UTC closure formats, all six BTC/SOL × 1H/4H/Daily groups, unique/valid rows, READY statuses and matching latest close times.
- Negative cases cover malformed JSON, missing/duplicate/extra rows, invalid fields, non-UTC timestamps, stale/mismatched closes and invalid pre-push hook input.
- Workflow source tests assert use of `scripts/market_structure_publish.py`, absence of direct `git push` in the workflow, main-branch event restrictions and read-only `contents: read` permissions for the test workflow.

**Review observations / limitations:**

- The visible `snapshots()` fixtures model only the six hard-coded BTC/SOL groups.
- The visible closure tests compare the market and structure close timestamps; they do not compare individual OHLCV candle values.
- Independent instrument/timeframe lane failure isolation is not demonstrated in the supplied excerpt.
- The file continues with `PublicationTests` after line 180, so no claim is made that the complete test file lacks publication, concurrency or recovery tests until the remaining sections are reviewed.
- The complete test suite has not yet been reported as executed successfully.

**Next review action:** Obtain lines 181–360, then the remainder of `tests/test_market_structure_publish.py`. Review the rest of `scripts/market_structure_publish.py`, `build_market_structure.py`, `market_structure.py` and both workflow diffs as one chain before recommending implementation changes.


### 8.7 P0 publisher test review — second excerpt received (lines 181–360)

On 2026-11-28, the user supplied the next excerpt from `tests/test_market_structure_publish.py`. The same excerpt was pasted twice in the chat; it is treated as one review input. The received text starts at line 181 and is truncated partway through `test_publication_and_unchanged_output`; no conclusions are made about later lines.

**Coverage visible in this excerpt:**

- Builds a temporary local Git repository and bare remote for isolated publication tests.
- Creates fixture copies of the pinned builder and market-structure source files and a six-group market-data snapshot.
- Generates separate 1H, 4H and Daily history fixtures containing 250 candles per configured symbol/timeframe.
- Runs the CLI in a child Python process with socket connection/name-resolution audit events blocked.
- Tests a successful publication through the generated pre-push hook and verifies that the new remote commit is a direct child of the fixture base and changes only the structure output.
- Tests rejection when the snapshot becomes stale during the push hook.
- Tests rejection of invalid pinned market-data inputs, including false/missing `ok`, missing groups, non-UTC closure and duplicate groups.
- Begins a test for publication and unchanged-output behavior, but the excerpt ends before its assertions.

**Important provenance gap confirmed by the visible fixture:**

- The fixture's `market_data.json` is created by `snapshots(NOW)[0]`, whose visible schema contains symbol, interval, status and close time, but no candle-by-candle OHLCV history.
- Separate history fixtures are then generated with synthetic constant OHLCV values for the builder.
- Consequently, the tests visible so far do not establish that the history candles used by the builder are byte-for-byte or value-for-value identical to the candles represented by `market_data.json`. They mainly exercise closure checks and safe Git publication mechanics.
- The publisher's history digest check, as previously reviewed, detects changes to the local history files during calculation; it does not by itself prove those files are the same source content as the published market-data snapshot.
- This is an acceptance gap to resolve in P0 design. It may require an immutable canonical OHLCV snapshot or a source manifest/hash referenced by both outputs, rather than trying to infer OHLCV equality from a summary JSON that does not contain those candles.

**Review status:** Second excerpt partially reviewed; remainder of the test file is still outstanding. No test-suite execution result has been supplied.


### 8.8 P0 publisher test review — final excerpt received (lines 361–515)

On 2026-11-28, the user supplied the final excerpt of `tests/test_market_structure_publish.py`. Together with excerpts 1–180 and 181–360, the full test file (reported as 515 lines) has now been reviewed from pasted source. The tests have **not** yet been executed.

**Coverage visible in the final excerpt:**

- Verifies publication makes exactly one push, creates a direct child of the pinned base, changes only `market_structure_data.json`, and leaves the local HEAD and pre-existing Git index unchanged.
- Verifies unchanged output causes a fetch/revalidation but no new candidate commit or push.
- Verifies remote `main` movement during the builder causes publication to stop.
- Verifies a history input file changing during calculation stops publication before candidate creation.
- Verifies missing history stops before builder execution.
- Verifies remote ref movement/deletion after fetch leads to a rejected push.
- Includes a control test showing that a plain push, without the custom publisher guard, can accept a candidate that is a descendant of a rewound remote ref. This supports the need for the publisher's explicit expected-old-ref check; it is not evidence that the guarded publisher accepts such a rewind.
- Simulates a server-side ref change after the client pre-push hook and expects rejection.
- Verifies server rejection, stale-at-final-check, missing pinned blob and changed working-copy source all prevent publication.

**Overall test-file review conclusion:**

The test file has substantial coverage of the Git publication transaction, source pinning, stale-close rejection, idempotency, history-file mutation during calculation and several ref-race scenarios. This is a useful safety foundation for the current BTC/SOL publication mechanism.

However, these tests do not yet demonstrate the complete agreed P0 architecture:

1. The visible fixtures and publisher constants still assume exactly six BTC/SOL × 1H/4H/Daily groups.
2. No test shown so far proves candle-by-candle OHLCV equality between the history used by the structure builder and the market-data source.
3. No test shown so far proves independent instrument/timeframe failure isolation while healthy lanes continue to publish.
4. No test shown so far demonstrates explicit stale last-known-good retention and prevention of stale data entering fresh-data analyses.
5. No test execution result has been supplied. Source inspection is not equivalent to passing tests.

**Next step:** Do not edit or merge yet. Obtain the actual test-run result from the isolated P0 worktree, then review the full workflow diffs and the complete publisher → builder → market-structure data chain. The P0 implementation should be revised against the agreed independent-lane model before it can be accepted.


### 8.9 P0 publisher regression test run — passed

On 2026-11-28, the user ran the isolated-worktree command:

`python -m unittest discover -s tests -p "test_market_structure_publish.py" -v`

Observed result from the pasted PowerShell output:

- `Ran 23 tests in 39.449s`
- `OK`
- `TEST_EXIT_CODE=0`

All 23 tests in `test_market_structure_publish.py` passed in this local run. The Git initialization hints and deliberate remote-rejection/fatal messages shown during certain tests are fixture/test scenarios; they did not cause the suite to fail.

**Interpretation / boundary:** This establishes that the current 23-test publisher regression suite passes in the user's isolated P0 worktree. It does not establish that the code has been merged/pushed to production `main`, nor does it validate the broader independent-market-data-lane architecture, multi-asset expansion, source candle parity, or live production data freshness. Do not mark P0 architecture accepted solely on this result.

**Next step:** Continue static review of the complete P0 workflow and data path, then design/implement the agreed independent instrument/timeframe lanes and their failure-isolation tests. Keep the isolated worktree and current no-merge/no-production-publish posture until the full review and required tests are complete.


### 8.10 Market-structure engine review — scale-out and fault-isolation gap

Reviewed the user's 2026-11-27/28 PowerShell output for `market_structure.py` (232 lines), alongside the previously shared `build_market_structure.py` and `market_structure_publish.py` implementations.

**Confirmed current scope**
- `market_structure.py` hard-codes `ALLOWED = {"BTCUSDT_PERP.A", "SOLUSDT_PERP.A"}`.
- Its supported intervals are hard-coded to `1hour`, `4hour`, and `daily`.
- It calculates BOS/CHoCH, heuristic candidate order blocks, three-candle FVGs, and equal-high/equal-low chart-liquidity candidates from closed OHLCV candles.
- The code explicitly does not claim that candidate OBs or chart-liquidity levels prove institutional orders or live order-book liquidity.
- The CLI rejects symbols outside the BTC/SOL allow-list.

**Confirmed fault-isolation gap across the shared implementation**
- The previously shared builder expects BTC and SOL across all three intervals (six groups), and raises if any expected group is missing, stale, insufficient, or not READY.
- The publisher's closure validator also requires all six groups to be READY and their closures to match the current interval boundaries.
- Therefore, one failed/stale symbol-timeframe lane can stop publication of the combined market-structure artifact, even when other lanes have valid data. This is not the intended independent-lane architecture.

**Required architectural direction (agreed product goal)**
Keep one canonical, unified ATLAS dataset for consumers, but make collection, validation, calculation, and recovery independent per instrument × venue/source × timeframe lane. A lane failure must not block healthy lanes. Preserve the last known-good lane output and explicitly mark its freshness/status (e.g. READY, STALE, UNAVAILABLE, ERROR); never present retained stale data as fresh. An aggregation/publication stage can assemble the lane outputs into the single canonical dataset. Avoid concurrent workers racing to overwrite the same monolithic file; use lane-scoped artifacts or an equivalent serialized/compare-and-swap aggregation design.

**Expansion boundary**
Do not treat the current BTC/SOL Binance-perpetual implementation as a universal market engine. Equities, FX, commodities, indices, spot, and futures require instrument/venue metadata and source adapters that understand their sessions, calendars, contracts/rolls, timestamp conventions, and volume semantics. The current three timeframes and Coinalyze perpetual symbol format are not a sufficient global abstraction.

**Next review**
Inspect the two workflow files (`.github/workflows/publish-market-structure.yml` and `.github/workflows/test-market-structure.yml`) before approving changes. Then design lane-level failure-isolation tests, including one failed lane while other lanes successfully refresh, stale last-known-good retention, recovery after source restoration, and concurrent publication safety. Keep the current P0 work isolated; do not merge or enable production publishing until the review and tests are complete.


### 8.11 P0 GitHub Actions workflow review — both workflow files received

Reviewed the complete user-pasted contents of:
- `.github/workflows/publish-market-structure.yml`
- `.github/workflows/test-market-structure.yml`

**Publisher workflow findings**
- Triggers on successful completion of `Publish BTC SOL Market Data` on `main`, manual dispatch, and a push changing the publisher workflow file on `main`.
- Uses one concurrency group for structure publication with `cancel-in-progress: false`.
- Checks out `main`, then downloads `1hour`, `4hour`, and `daily` history sequentially from the Cloudflare Worker, then runs `scripts/market_structure_publish.py`.
- Global workflow permission is `contents: write`; consider least-privilege scoping at job level with read-only workflow default and write only for the publishing job.
- A failure in any one sequential history download fails the shell step and therefore blocks the entire structure run. This is consistent with current all-six-groups builder/publisher behavior, but conflicts with the agreed future independent-lane fault-isolation goal.
- The workflow fetches three history responses independently. Matching last-close timestamps does not prove candle-by-candle OHLCV identity between history and the OHLCV source used to publish `market_data.json`. The builder currently checks group readiness, candle count and closure alignment, not full OHLCV parity.
- The one combined `market_structure_data.json` output and six-group all-or-nothing validator mean one bad lane can prevent healthy lanes from updating.
- The workflow has no explicit artifact/source-manifest handoff tying the structure calculation to the exact immutable OHLCV package used by the market-data publisher.
- Its name and endpoint/symbol scope remain BTC/SOL-specific; this is not yet the multi-asset/multi-market engine architecture.

**Test workflow findings**
- Runs the full `tests/test_*.py` unittest discovery on configured pushes, pull requests targeting `main`, and manual dispatch.
- Uses Python 3.12, `actions/checkout@v5`, `actions/setup-python@v6`, and workflow-level `contents: read`.
- Pull requests targeting `main` are tested without granting write permissions.
- The push path filters include the engine, builder, publisher, both relevant test files, and the workflows themselves.
- Consider adding a timeout and a concurrency policy for redundant CI runs; these are maintainability improvements, not the central P0 correctness gap.
- Manual dispatch is not explicitly restricted to `main`; the job is read-only, so this is not a production-write exposure, but branch/ref behavior should be intentional and tested.
- The workflow's BTC/SOL naming reflects the current limited scope.

**Review conclusion**
The current workflows are internally consistent with a single combined BTC/SOL structure publication, and the 23 publisher tests passed in the user's isolated worktree. However, they do not implement independent instrument/timeframe collection, validation, recovery, or publishing. A single failed history request currently blocks the complete Structure job. Same-close validation is weaker than exact OHLCV input identity.

**Required P0 architecture before acceptance**
1. Produce or identify one immutable, validated OHLCV source package/manifest per instrument × venue/source × timeframe lane. Include source identity, interval, close timestamp, candle count/range, and deterministic content hash.
2. Ensure downstream analysis consumes that exact package or verifies exact candle-by-candle OHLCV equality—not just matching close timestamps.
3. Validate lane completeness and continuity (missing/duplicate/misaligned candles, invalid OHLCV, stale closes) independently.
4. Permit healthy lanes to refresh when another lane fails. Retain last-known-good output for a failed lane with explicit freshness/status metadata; never label stale retained data as fresh.
5. Aggregate lane outputs into one canonical dataset using serialized or compare-and-swap publication so concurrent lane updates cannot overwrite one another.
6. Add tests for partial provider failure, exact OHLCV mismatch with identical close time, missing candles, stale lane retention, successful lane recovery, and concurrent aggregate writes.
7. Keep write permissions least-privilege: read-only workflow default and write only in the minimal publication job.

**Current status:** Static workflow review complete. No repository application code, production workflow, or main branch was changed by this review. P0 remains isolated and not approved for merge/production deployment.


### 8.12 AI Duo operating model — use the integrated agents for engineering tasks

The user correctly reminded us that ATLAS AI Duo Control Center was built specifically to coordinate the real Codex CLI and Claude Code CLI in the same project environment.

The 2026-11-24 handover record confirms:
- Current panel path: `C:\Users\HOME\atlas-ai-duo-control\atlas-ai-duo`.
- Launch script: `ATLAS_Panel_Ac.bat`.
- The panel manages real Codex CLI + Claude Code CLI workflows in an approved, isolated worktree arrangement.
- The P0 repository worktree is separate from the actual `main` clone.
- At the time of that handover, no new task had been started and the panel's last observed state was idle / 0%; real live Codex↔Claude progress-state transitions had not yet been independently validated.

**Operating correction:** For future ATLAS engineering tasks, use the integrated AI Duo as the primary execution/review environment rather than routinely asking the user to manually inspect and paste large source files. Assign one agent a bounded implementation or architecture task and the other an independent review/challenge task, with explicit scope, acceptance tests, and stop conditions. Keep all work in the isolated P0 worktree or a fresh task-specific worktree. Do not allow either agent to write to production `main`, push, open PRs, merge, rebase, or trigger production workflows without the user's separate explicit approval.

The ChatGPT conversation remains the coordinator: clarify architecture, prepare task briefs, assess evidence/results, challenge unsupported conclusions, and record decisions. It should not imply that the two CLI agents are automatically running merely because the panel is installed; a task must be explicitly launched/approved in the panel.

**Immediate next action:** Route the P0.2 independent-lane architecture design through AI Duo. First request a read-only design/review (no file modifications), with Codex and Claude independently assessing lane identity, immutable OHLCV package/manifest, exact candle parity, per-lane failure recovery, stale last-known-good retention, and safe aggregation. Reconcile disagreements before authorizing any implementation.
