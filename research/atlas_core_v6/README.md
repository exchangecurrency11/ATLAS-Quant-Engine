# ATLAS Core E5-B — Verified monthly prospective source adapter (read-only)

**Purpose:** Connect the existing frozen ETH six-stream and BTC/SOL
two-candidate *monthly prospective ledgers* to a guarded read-only
**audit intake**. This is the first half of enabling future ATLAS
shadow decisions, **not** a new live order or notification pipeline.

## Why we cannot announce new live AL/SHORT decisions yet

The two original prospective sources are independently frozen on:

- ETH: \`research/eth-v93-prospective-paired-20261113\`,
  2026-11-14T00:00:00Z start, six V9.3 streams.
- BTC/SOL: \`research/btc-sol-event-regime-forward-20261114\`,
  2026-11-15T00:00:00Z start, BTC LONG high-volume-volatility and
  SOL high-volatility research candidates and exact V9.2 controls.

On Nov 14 2026 they have only PRE-FREEZE \`preflight.json\` and
\`frozen_spec.json\` files, not post-freeze monthly \`latest.json\`
with newly closed positions. These original scripts only publish
**complete previous calendar month** Binance USD-M SHA-256 history,
meaning outcomes arrive after trades close and after the relevant
monthly archive is published. Those results **cannot** establish
that an entry signal was delivered at entry time.

The active main branch exposes public BTC/SOL indicators and
structural chart context, **not** sufficient 1H BOS/retest/next-open
V9.2 candidate proof. Treating market context as a "buy/sell"
signal would fabricate a new trading strategy.

E5-B therefore:

1. Reads source branches over pinned, approved \`raw.githubusercontent.com\`
   paths; **never writes to either source**.
2. Requires the live branch's frozen \`frozen_spec.json\` and
   \`preflight.json\` to equal byte-for-byte the **Git-blob-pinned**
   reference copies in this E5-B branch.
3. If \`latest.json\` does not exist, reports **NO COMPLETED
   POST-FREEZE SNAPSHOT** and **0** eligible timely opportunities.
4. If it exists, enforces its claimed status, post-freeze and
   before-now month boundary, exact \`latest.json\` bytes matching
   \`snapshots/YYYY-MM.json\`, original source-engine frozen hashes,
   publisher archive SHA declarations including all preflight months,
   complete per-symbol monthly digest keys, all reference/candidate
   stream names and the original account / no-alert guards.
5. Enforces each completed trade's timestamp order:
   \`freeze <= watch < retest <= entry < exit <= month_end\`,
   UTC hour alignment, max 24h hold, no duplicate entries,
   allowed side / original exit reason, metric count and netR25 parity.
   ETH source also supplies original entry/stop/targets and R9/R25,
   which are verified (stop side, 0.1–4% stop distance,
   exact TP1/TP2/TP3 spacing, and 9→25 bps formula).
   BTC/SOL monthly report **does not include entry price/stop**.
6. Writes only a temporary GitHub Actions research artifact with
   counts, source hash and disclosure, not a live opportunity card
   or retroactive "AL/SHORT" notification. No existing frozen
   prospective streams, account books, or notification schedules
   change.

**Source-provenance limitation:** E5-B checks producer-declared
month SHA256 against the immutable preflight for old months,
and checks the source snapshot's latest==immutable-month bytes.
E5-B **does NOT re-download publisher ZIPs** and is therefore not
independent Binance candle parity. A mutable GitHub source branch
is not a cryptographically signed broker feed.

## Deliberately strict absence and falsification tests

- Fake, future or pre-freeze watch/retest/entry records: reject.
- Preflight, frozen engine configuration or source drift: reject.
- Latest not identical to official research \`snapshots/YYYY-MM\`: reject.
- Changing an old SHA256, missing monthly archive, duplicate trade: reject.
- ETH fake stop, targets or incorrectly calculated 25bps return: reject.
- Unavailable latest: **no signal**. HTTP 403 or other source errors
  are not silently converted into "no trades."
- Closed outcomes are retrospective only; no outcome-derived
  trade entry decisions or claims of realtime forecasting.

## How to reproduce

From repository root on the isolated E5-B branch:

    python3 -m unittest research.atlas_core_v6.test_prospective_intake_e5b -v
    python3 -m research.atlas_core_v6.prospective_intake_e5b

The GitHub Actions workflow is **manual or research-branch push only**,
\`contents:read\`, no checkout credentials, **no schedule**,
no file modifications to sources, and no Git commit of reports.

## What is genuinely next after E5-B

**E5-C — timely source producer / independent cold observation:**
a read-only feed must supply complete *closed* 1H BOS and retest
timestamps, true next-hour OPEN entry proof, required 4H and daily
closed-candle evidence, verified exchange provenance and a timely
risk/position snapshot **at that entry time**. New prospectively
timestamped "WAIT/PASS/RESEARCH-ELIGIBLE" shadow evaluations can
then be accumulated in immutable snapshots and compared against
subsequently observed outcomes.

E5-C does not automatically promote any strategy, send alerts,
or change V7/V9.2/ETH/BTC/SOL frozen prospective studies.
Live capital approval would need independent prospective results,
observed costs, risk review and explicit user authorization.
