# V9: V7+ PROFIT-ORIENTED OPPORTUNITY DETECTION FIRST

## User objective (2026-11-11)
**Primary:** Preserve original V7 BTC/SOL 1H BOS -> later retest -> subsequent
1H hypothetical next-open strategy; improve its ability to distinguish
profitable LONG and SHORT opportunities **after fees, slippage, funding,
and risk**. SOL is first priority. Paper-only until superiority proven.

**Secondary:** Predict next 4H candle's *OWN OPEN-vs-CLOSE GREEN/RED* color
as independent market context, recorded before candle begins. A green
4H prediction is **NOT** a LONG trade or positive-P&L prediction. V9
must never create an entry solely from candle color, OI, CVD, funding,
or 4H/Daily trend vote.

Do not edit or disable original V7. Do not enable V9 notifications or
execute orders without **explicit user approval** after genuine paired
prospective evidence.

## Read-only research streams
1. **Original V7:** `experiment/v7-signal-quality-20261103/forward/snapshots`.
   `V7_signal_filter.newWatchAtThisClose` is a newly confirmed BOS WATCH.
   `pendingNextOpenPaperEntry` is a later retest confirmation.
   `paperTradeExitsObservedAtThisClose` contains hypothetical paper
   fills, partial TP and stops. `marketContext` trends are not signals.
2. **V9 closed 1H:** `forward/v9_next_4h_color/hourly/snapshots` BTC ETH SOL
   source timestamps, technical context and optional derivative overlays.
3. **V9 sealed future 4H colors:** `forward/v9_next_4h_color/paper_forecasts`
   exists only if original prediction **and a Git commit before the target
   4H open** are independently evidenced. No backfill. Their directional
   agreement is advisory/research-only and cannot veto the original
   V7 strategy automatically.
4. **New trade-first research bridge:**
   `v9_v7_trade_opportunity_bridge.py` checks identical closed 1H
   timestamps, BTC/SOL close parity and original V7 state, then creates a
   separate V9 shadow record and tracks original paper exit net R. Runs
   from `main/.github/workflows/v9-v7-paper-trade-opportunity-shadow.yml`
   into the research branch. Missing matched sources => skip rather
   than manufacture observations.

ETH V7 BOS/retest has NOT been established as an identical original
BTC/SOL V7 strategy. ETH can remain a market-context asset; no ETH
paper-P&L comparisons until the same entry/risk/exit semantics exist.

## Profit and safety scorecard: PRIMARY metric is net expectancy, NOT color %
- Original V7 vs shadow V9 on the **same eligible chronological signal
  opportunities**. True candidate assessment needs *full strategy replays*
  with a pre-committed V9 filter, since blocking a trade can change later
  opportunity timing. The current subset report is descriptive only.
- Average **net R per closed hypothetical trade**, **total net R**, win %
  with count, **profit factor**, max peak-to-trough R drawdown, trade
  coverage, # WATCH signals, # retests, rejected setups, and missed
  source/time slots.
- Cost sensitivity: baseline 6bp fees + 3bp slippage per side; separately
  25bp per side stress. Funding, variable spreads, actual order fills,
  stop gaps, liquidation and market impact require separate modeling.
  No risk-adjusted annual return or verified true profit is implied.
- Research target: positive net expectancy **and** improvement vs original
  V7 at same costs/period, without sacrificing sample coverage or
  worsening drawdown materially; prefer independent new prospective
  signals and at least 100 closed trades per symbol before any confident
  claim. Insufficient samples => UNPROVEN.
- The original V7 2026-11-03 paper simulation had BTC 5/9 winners
  (mean +0.4071R at 9bp/side) and SOL 7/14 winners
  (mean +0.1610R at 9bp/side), but SOL stress at 25bp per side was
  **-0.077R**. These are small historical hypothetical samples, not
  forecasts of income or live results.
- 4H own-body color hit rate, Brier, coverage and confidence calibration
  are **SECONDARY** diagnostics only. A correct 4H forecast can coincide
  with a losing retest trade (entry timing, stop distance, fees).
- Independent Binance archive SHA256 parity audit found Coinalyze
  `tx` does **not** equal Binance official count on the 48 audited
  hours for any of BTC/ETH/SOL. Binance live REST access from GitHub
  was HTTP 451. Frozen 94-feature research model remains historical;
  source-motivated 88-feature no-tx model was **not superior** and remains
  independent shadow only. Neither has proven live trade edge.

## Near-term no-alert milestones
1. Verify first *real* 4H GREEN/RED GitHub commit **before** target 4H
   start; do not confuse a successful-but-skipped workflow with capture.
2. Preserve every V7 BOS WATCH and subsequent retest paper result with
   timestamp and all costs. Compare both original V7 and extra research
   on identical signals. Never rewrite original signals.
3. Score only actual sealed pre-start forecasts vs subsequent target and
   V7 outcomes; if no sealed model, record MISSING, not directional edge.
4. Investigate additional signal-quality features (OI, funding,
   candle-taker CVD), with causal as-of verification and ablation.
   A higher win rate after rejecting 95% of opportunities need not mean
   higher net return; reject candidate rules with unstable cost stress.
5. Require enough **new, independent, prospectively captured** paper
   opportunities with better net R than V7, then ask user whether
   notifications should be changed. No silent activation.

**Current gate:** V9 notifications BLOCKED, no broker orders.
