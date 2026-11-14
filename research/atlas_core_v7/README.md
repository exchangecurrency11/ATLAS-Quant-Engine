# ATLAS Core E5-C — Cold observational stream: existing V9.2 hourly paper

This is the first real **hourly-source pilot** after E5-B monthly
intake. It **does not** alter current V7/V9.2 production paper
accounts, Telegram/ChatGPT notifications, ETH/BTC/SOL frozen
prospective candidate rules, schedules, \`main\` or prior E1–E5-B.

## Source evidence, as it actually exists

The official futures REST source may be unavailable to GitHub runners.
Instead of falsely claiming a Binance-native live execution price, we
read three **pre-existing** research streams:

1. \`research/v92-bull-bear-candle-invalidation-20261112\`:
   \`forward/v92_prospective_selected/hourly/YYYY-MM-DDTHH-00Z.json\`
   (BTC and SOL, original V7/V9.1 and selected V9.2 sources).
2. **Same research branch, independent ETH component**:
   \`forward/v92_prospective_eth/hourly/YYYY-MM-DDTHH-00Z.json\`
   (original V7/V9.1 and separate ETH V9.2 selected paper).
3. \`research/v9-prestart-live-data-compatibility-20261111\`:
   \`forward/v9_next_4h_color/hourly/latest.json\` (BTC/ETH/SOL
   closed 1H, 4H and daily context). **This is not a V9.2 entry
   event, nor does it prove independent Binance exchange truth.**

Sources 1 and 2 inherit existing Coinalyze-derived V7 data. E5-C
refuses to report the datasets as independently matched Binance USD-M
public exchange order book or as real exchange executions.

## What is implemented

- Read only three sources from their exact allowlisted research
  branches and paths; snapshot each source branch's Git commit SHA
  before fetching. Never fetch moving branch raw URLs.
- Compare raw document **Git blob SHA1** to GitHub file-list metadata,
  and include SHA256 in each audit report. File names must match
  actual UTC closed 1H stamps; disallow modified, forged or
  intentionally future-dated files and capture timestamps.
- Require same latest closed 1H for BTC/SOL and ETH; align that with
  the third-party V9 market context.
- Verify BTC/SOL original exact V7/V9.1 source checks and V9 context
  OHLCV of 1H/4H/daily for all 5 fields, not only indicator labels.
  ETH verified source flags and daily close are cross-checked.
  ETH full independent 1H/4H OHLCV is **not** proven by this
  integration; source limitation is explicitly preserved.
- Inspect latest **four consecutive hourly source files** for BOTH
  branches and verify all eight file bodies against their Git blobs
  to avoid counting an absent/forged hour as complete. Any missing
  hour stays missing — NEVER fill gaps retroactively.
- Preserve each stream's separate original watches, current
  confirmed retest indicators, pending hypothetical next-open
  entries, open paper hypothetical positions and exit notices;
  use counts/state labels **only**. Does not invent stop, entry
  prices or predicted outcomes absent in the source.
- Distinguish closed-hour UTC, producer capture UTC and observer
  read UTC. If a 1H-close observation was produced at 21:32 UTC,
  the 21:00 exact next-hour OPEN is already past. A later capture
  cannot be converted into a fair prospective entry signal.
- No trading notifications, no broker calls, no read/write to a
  user's exchange positions, no virtual account allocations, no
  overriding the five existing ChatGPT automations.

## Statuses, not signals

- \`SOURCE_WITNESSES_CHECKED_OBSERVATION_ONLY\`: matching hourly
  cross-stream evidence checked, but *still* never a proven
  executable at-boundary entry.
- \`SOURCE_HOURS_DISAGREE_FAIL_CLOSED\`: BTC/SOL and ETH saved
  sources do not have the same most recent 1H close; do not
  combine unlike hours.
- \`DELAYED_1H_OBSERVATION_NOT_AN_ENTRY\`: source capture happened
  more than 15 minutes after the already-closed hour.
- \`STALE_SOURCE_NO_ENTRY\`: last closed hour is older than
  the 90-minute observation window.
- \`INCOMPLETE_HOURLY_COVERAGE_NOT_AN_ENTRY\`: mandatory
  four consecutive saved hours missing from at least one source.

Everything is an **observational research status**, not a
personally actionable LONG/SHORT order. The original BTC/SOL
hourly sources and their ETH counterpart were not produced by
our E5-A/E5-B candidates and cannot be repackaged as new
performance results.

## Verification and reproducibility

From the E5-C research branch:

    python3 -m unittest research.atlas_core_v7.test_hourly_cold_observer_e5c -v
    python3 -u -m research.atlas_core_v7.hourly_cold_observer_e5c

The branch-only workflow repeats E1–E5-B regression tests and
E5-C synthetic negative controls. It then **reads the actual
original research branches** and creates temporary JSON and Markdown
evidence as a GitHub Actions artifact (30 days), without Git commits.

**Important operational limitation:** The original V9.2 observation
branches already publish their own hourly snapshots; E5-C verifies
them **only when its workflow is manually dispatched or this
research branch is changed**. GitHub Actions schedules run from
the default branch, not isolated research branches. We have
**not** added a new \`main\` schedule or altered production alerts.
Consequently E5-C cannot claim 24/7 independent automatic
observation or timely entry detection yet.

## What comes after the E5-C pilot

For genuinely new *timely*, autonomous shadow opportunity checks:

- An explicitly authorized **separate recurring runner** must
  observe closed 1H market history quickly enough for a prospective
  next-hour decision and lock all its data/time hashes.
- Reconstruct V9.2 **closed BOS → closed retest → next-hour open**
  from closed exchange-specific OHLCV and its pinned exact
  engine code. Today's V92 source may publish 12–50+ minutes
  after the next-hour opening; this is too late to claim that
  opening as a real fill.
- Verify independent actual portfolio exposure and account fees
  or classify the risk gate as \`UNKNOWN/WAIT\`. Treat monthly
  results as delayed evidence, never as entry-time observations.
- Record all first-seen, no-lookahead events prospectively,
  track capture gaps and compare later observed performance.
  No strategy is promoted on previously studied history.

No source or candidate is silently modified by this step.
