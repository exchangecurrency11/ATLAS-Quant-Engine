# ATLAS Core E5-A — Silent opportunity-decision contract (research only)

**Goal.** Move from historical execution-cost experiments (E1–E4-B)
towards a useful **read-only shadow opportunity decision** for BTC/SOL,
and eventually ETH, without changing any current V7/V9.2 trades,
alerts, frozen prospective studies or user automations.

This first stage is an **honest integration boundary**, not a trade
recommendation or a live trading strategy. We must distinguish a
published chart structure region from a *closed-bar V9.2 BOS → retest
confirmed → next 1H OPEN* actionable entry. The current public
\`main/market_data.json\` and \`market_structure_data.json\` do NOT
contain such a validated full entry signal. The frozen monthly
prospective reports likewise only contain **pre-freeze preflight**
in the research branch; no completed-month post-freeze trade snapshot.

## What E5-A actually implements

- Read-only immutable source guards for frozen ETH and BTC/SOL
  prospective specifications, preflight evidence and existing E4-B
  research cost module. Exact Git blob SHA1 pre-registered in code.
  No existing file edited; entire E5-A stays on new branch.
- Read **51 prior historical V9.2 reference trades** against the
  independently matched original historical witness; create strictly
  **historical demonstration input packets** containing only
  watch/retest/entry, symbol/side/entry and rounded original stop
  risk%. No future exit outcomes, trade returns or stop-hits can
  enter decisions. A fake trade with a matching source label/hash but
  a changed price/risk/time is rejected unless it matches an exact
  sealed historical witness. These are old demonstration samples,
  not new trades.
- For each sample, show fixed **9/25/50 bps per side cost stress**
  and a 3-bps-per-8h × 24h maximum hold **unobserved FUTURE
  funding reserve**. Compute **2R only IF TP1/TP2/TP3 all fill**,
  minus stress. This is a risk/reward arithmetic scenario, *not*
  an expected return, opportunity hit probability or observed
  trading performance.
- Shared risk demonstration: hypothetical 10,000 USDT equity;
  0.5% stop-risk per new position, 1.0% maximum concurrent stop
  risk, 1.5x maximum gross exposure, 0.1% minimum accepted
  size. Position snapshot needed; stale, unknown/duplicate
  positions or occupied same-asset slots are rejected. The only
  demonstration position inventory is explicitly **synthetic-flat**.
  No claim to read your actual open positions.
- Status words: **WAIT**, **PASS_COST_STRESS**,
  **PASS_PORTFOLIO_RISK**, **HISTORICAL_REVIEW_ONLY**.
  None means "BUY"/"SELL"/"open a real trade"; every historical
  status remains non-actionable even if risk and cost arithmetic
  clears. No new notifications or automated strategies.
- Optionally fetch the public repo's **Coinalyze** published
  \`main/market_data.json\` read-only, retain source SHA256 and
  candle-freshness check. This public BTC/SOL market context
  cannot be promoted to a V9.2 entry. Any stale/unavailable
  data fails closed; ETH has no matching public main packet.

## Strong no-fabrication gates

E5-A explicitly records:

- \`actualNewForwardSignalCount=0\`
- \`actualNewForwardSignalCards=[]\`
- \`newTradeOrders=0\`, \`newUserAlerts=0\`,
  \`existingPaperTradesWritten=0\`
- \`existingAutomationsChanged=false\`,
  \`mainBranchChanged=false\`, \`candidatePromoted=false\`
- All cards \`realTradePermission=false\` and
  \`autoOrderAllowed=false\`.
- Frozen ETH freeze **2026-11-14T00:00:00Z**; BTC/SOL candidates
  **2026-11-15T00:00:00Z**. No retroactive promotion.

If a future monthly prospective \`latest.json\` appears, E5-A
deliberately **does not automatically ingest it**. A separate
validated E5-B prospective packet reader must pin the feed,
verify exact source signature/hash, causal known timestamps,
no-lookahead, closed data, true per-account position state,
and trace every reference to its original immutable snapshot.
That reader should first run *observation only*, publish
verification counts and non-actionable cards with timestamps.
Live entry notifications would need a separate explicit
user instruction and strong independent evidence.

## Run and evidence

From repo root:

    python3 -m unittest research.atlas_core_v5.test_shadow_decision_e5 -v
    python3 -m research.atlas_core_v5.shadow_decision_e5 --fetch-public-main-context

The Actions job on the E5 research branch only runs on push
or manual dispatch; **no schedule**, permissions \`contents:read\`,
checkout credentials not persisted and no git commits/pushes.
Outputs \`e5a_report.json\` / \`e5a_report.md\` are temporary
GitHub Actions artifacts, not added to production or
prospective ledgers.

## Next: E5-B genuine real-time proof adapter, not more fitting

Only when a close-confirmed V9.2 opportunity (complete watch,
retest and true next-hour open) and verified snapshot of
existing open positions are available, can we classify a
contemporaneous opportunity in a research-only shadow book.
Current market zones are insufficient, and historical 51
samples must never be credited to future signal performance.
Even then, all decisions remain unapproved for live capital
until prospectively calibrated, risk-reviewed and explicitly
authorized by the user.
