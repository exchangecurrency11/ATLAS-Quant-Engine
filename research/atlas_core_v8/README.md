# ATLAS Core E5-D: Hourly first-seen journal, read-only shadow observer

**Research-only continuation of E5-C. No broker orders, user notifications,
risk account mutations, active signal changes, or prospective rule promotion.**

## What this delivers

E5-C proved that our existing 1H BTC/SOL + ETH V9.2 paper
snapshots, together with V9 three-asset public market context,
are real saved sources. But those sources may be recorded 20–40+
minutes after the 1H close; they cannot prove an executable next-hour
OPEN or actual Binance orderbook execution.

E5-D adds:
- An **independent, low-privilege source reader** pinned to each source
  branch's exact Git commit SHA. It verifies Git blob SHA1 and records
  source SHA256 for every accepted hourly observation.
- Git **tree** walking rather than the GitHub contents API's 1,000-file
  directory cap. Reads source entries by SHA and independently
  checks the latest **four saved consecutive hours' file contents**.
- Two append-only, **day-partitioned research journals**:
  \`forward/atlas_core_e5d_hourly/attempts/YYYY-MM-DD/...\`
  and \`forward/atlas_core_e5d_hourly/observations/YYYY-MM-DD/HH-00Z.json\`.
  A successful source-first-seen observation for a closed UTC hour is
  written once and NEVER silently overwritten.
- UTC provenance: the observed source close, source capture time,
  first-seen observer UTC and the GitHub Actions run ID. Count
  missing hours between eligible source observations and flag source
  periods without all last four hours.
- A conservative **activation UTC** of
  **2026-11-14T22:00:00Z** (after E5-C development). Older closed hours
  can be inspected as previous context but are **never credited as
  new forward observations**. Source hours older than 90 minutes
  are also not newly credited.
- Retained source event counts: BOS watch notices, selected retest
  notices, pending hypothetical paper entries; NEVER infer missing
  entry price, stop, actual fills, true broker exposure or a trading
  opportunity where none is source verified.
- A **repeatable** same-hour run is idempotent with a new attempt ID:
  the old observation is reused. Re-running the identical run ID
  with changed facts, mutated existing ledger files, or a retroactive
  earlier hour fails closed.
- No requirements to know the user's capital, private positions or
  account API keys; this is **observation only**.

The research state machine always reports \`newLiveSignalCount = 0\`.
The original V9.2/ETH/BTC/SOL experiments are separate frozen cohorts.
Nothing about 51 historical V9.2 trades is called new prospective
trade performance.

## Running it, and honest scheduling limitation

Manual dry-run on research branch:

    GITHUB_RUN_ID=1234 GITHUB_RUN_ATTEMPT=1 \
      python3 -m research.atlas_core_v8.hourly_journal_e5d --no-write

Appending *only* to the dedicated research-only journal:

    GITHUB_RUN_ID=<real actions run id> GITHUB_RUN_ATTEMPT=1 \
      python3 -m research.atlas_core_v8.hourly_journal_e5d

Do not create fictitious source data. Source reading needs read-only
public GitHub API access.

**GitHub Actions scheduled workflows run exclusively on the DEFAULT
branch.** Therefore a cron schedule added to the E5-D research branch
would NOT activate the hourly agent. The intended production isolation
is a **single, narrowly scoped workflow definition on \`main\`** that
(1) checks out the research-only E5-D branch, (2) executes the
audited source-locked code at two off-hour slots, and (3) appends only
the research journal on its dedicated branch, never main or older
V7/V9.2 records. GitHub may delay or omit scheduled runs; this
is not a guaranteed minute-accurate service.

The main GitHub scheduling action is **not** a ChatGPT automation
and does not change any of the user's five existing tasks.
It creates no new signal notification. The isolated E5-D branch
runs its own fast regression on push, without a schedule, before
installation of any default-branch dispatcher.

## Risk and observability boundary

- A source event produced after the hour's exact OPEN can be
  prospectively recorded *only when first received*, not backdated
  to the original entry-open price. This can never certify fills.
- The existing live Coinalyze/V7 source parity is not independent
  native Binance futures bid/ask, per-position settlement mark,
  liquidation, or exchange-account exposure.
- The prior four hours being complete only improves data continuity;
  it does not establish a profitable trading system or fix source lag.
- GitHub Actions cron and source GitHub pushes have independent jitter.
  The report includes first-seen lags, missing source hours and
  source-branch commit pins. No "all hours always captured" claim.
- Existing ChatGPT BTC/SOL alerts stay exactly as they were.
  Even if a new BOS watch is observed, the journal is never a
  new trade recommendation or a notification trigger.

## Source validation

This E5-D project should pass all E1–E5-C regression and 30+
targeted E5-D negative tests in a read-only research-branch workflow.
The scheduled \`main\` dispatcher is a **separate, new workflow file**,
not an edit to any existing scheduled or trading workflow.
