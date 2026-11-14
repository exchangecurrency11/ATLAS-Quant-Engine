# ATLAS Core E4 — execution-model sensitivity and shared BTC/ETH/SOL risk

**Research-only historical stress test, 2026-11-14.**
No account, order, auto-promoted trading candidate, production V7/V9.2
configuration, branch main, alert, freeze, or reminder is modified.

## Research question

Do 51 *previously observed* V9.2 baseline trades remain viable when
accounting for pessimistic 1H stop gaps, price-affected entry/exit,
assumed commission, half-spread, impact and adverse funding, **and**
a common account where simultaneous BTC/ETH/SOL exposure competes for
one risk and gross-notional limit?

E4 is an execution and sizing *sensitivity experiment*, not a search for
a more profitable rule and NOT a forecast.

## Mandatory raw-data and engine parity

E4 re-downloads all 159 BTC/ETH/SOL official Binance USD-M 1H monthly
ZIPs for 2022-05 through 2026-09, verifies the official .CHECKSUM and
matches their SHA256 with the previously sealed V9.2 manifest.

Nine original engine-related source files and E3's own module are pinned
to historical Git blobs; any modified input aborts. Re-run the frozen
V9.2 BASELINE signal engine on all six full-period histories; every
entry, exit, Net R9 and R25, veto count and watch count must match the
sealed 51-trade historical oracle.

Additionally, E4 implements independent *gross position accounting*
with partial 1/3 targets, stop-first intrabar priority and 24H exit.
With 0 fees, 0 half-spread, 0 impact, 0 funding and no gap adjustment,
this separate implementation MUST reproduce each of the original 51
trades' realized gross R within 1e-7.

## Prespecified hypothetical frictions — not actual venue observations

| Scenario | Commission / side | Half-spread / side | Impact / side | Total friction / side | Adverse funding at assumed UTC 8H marks |
|---|---:|---:|---:|---:|---:|
| Calm | 6 bps | 1 bps | 2 bps | 9 bps | 0.5 bps/event |
| Stress | 6 bps | 4 bps | 15 bps | 25 bps | 3 bps/event |
| Shock | 6 bps | 9 bps | 35 bps | 50 bps | 10 bps/event |

Rates **are assumptions**, not exchange-specific commission tiers,
observed bid/ask, historical market impact or real historical funding.
No Binance historical funding or orderbook data is downloaded by E4.
The 00:00/08:00/16:00 UTC interval is assumed, may not match actual
past funding schedules, and is charged as adverse even on shorts where
observed signed funding may have benefited the strategy.

The model executes at price +/- the assumed half-spread and impact,
and charges commission on position entry and each partial exit notional.
Funding uses the reference entry notional times open fraction, never an
observed mark price. Stop-first order is preserved when an hour touches
both TP and stop. A stop gapped through at OPEN is filled at the worse of
nominal stop and that actual bar OPEN, then charged modeled exit friction.
The model does not know within-hour tick sequence or queue depth.

Even the 9-bps scenario should not be mistaken for the old V9.2 R9:
the latter charges a flat 9-bps-per-side entry-notional approximation.
E4 uses price-adjusted fills, fees on exit notional, and adverse funding.

## Prespecified shared portfolio for descriptive sensitivity ONLY

- Hypothetical opening equity: **10,000 USDT**.
- Initial stop-distance budget: **0.5% realized equity per position**.
- Concurrent total open stop-distance budget: **1.0% realized equity**.
- Concurrent gross notional limit: **1.5x realized equity**.
- If available budget is below 0.1% equity, reject the hypothetical
  position; otherwise clip it and count the clip.
- Exit cash settles before entry at the same timestamp. A rejected trade
  never earns hypothetical P&L. Only one position in each asset at once.
- Cash changes are computed in chronological event order: allocated
  risk USDT * independently modeled E4 scenario net R.
- Realized-only max drawdown and profit factor are **not** true
  mark-to-market portfolio risk metrics; no liquidation or margin
  maintenance model. Reserved stop risk does not cap larger gap losses.

These risk caps are experiment parameters, **not** live deployment advice,
paper trading modifications or user-specific investment recommendations.

## How to reproduce

From repository root with public internet access:

    python3 -m unittest research.atlas_core_v0.test_atlas_core_v0
    python3 -m unittest research.atlas_core_v1.test_atlas_core_e2
    python3 -m unittest research.atlas_core_v2.test_atlas_core_e3
    python3 -m unittest research.atlas_core_v3.test_atlas_core_e4
    python3 -u -m research.atlas_core_v3.atlas_core_e4 --workers 6

Artifacts are generated under research/atlas_core_v3/output/ and
temporarily uploaded by the isolated read-only CI job. No commit or git
push after execution. Actions job runs on this research branch only,
no time schedule and no permission to write repository contents.

## Exit criteria and next E4 follow-ups

E4-A: Full 159 official archive SHA256, 51/51 frozen trade parity,
51/51 independent gross zero-cost replay, all negative controls, three
scenario outcomes and budgeted chronological portfolio metrics.

E4-B (not part of E4-A): Attach separately SHA256-pinned real historical
Binance funding **events** including timing, sign and mark, plus
time-specific actual maker/taker fees if available; verify missing-event
coverage rather than filling with assumptions. To estimate actual
spread, impact, marketable-stop latency and liquidation mechanics,
need tick/orderbook and exchange account fee data. Re-evaluate the
portability of these risk profiles beyond cryptocurrencies separately.
