# ATLAS Quant Engine — BTC / SOL Deep Research & Frozen New-Data Protocol

**Recorded 14 November 2026. Research only. No production, real orders, user alerts or existing paper-account edits.**

## Why study these two hypotheses?

The independently archived earlier investigation of V9.2 (159 official Binance USD-M monthly ZIPs, SHA256 checked) found that baseline BTC LONGs produced **−5.777 R25** over 6 trades, whereas BTC SHORTs produced **+0.891 R25** over 9; SOL in the high trailing-volatility regime produced **+5.899 R25** over 6 trades and low trailing-volatility produced **−1.486 R25** over 14. These historical differences are extremely sample-limited and influenced selection of today's hypotheses. They are **not unseen validation**, and high-vol conditions are not evidence of guaranteed profit.

**Exactly two candidates, frozen:**

1. `BTC_LONG_HIGH_VOL_ONLY`: preserve original V9.2 BTC short entries without a new veto. Reject only BTC bullish retests unless the already fully CLOSED prior Daily volatility regime is `high`.
2. `SOL_HIGH_VOL_ONLY`: preserve original SOL opposing-selected-reversal-veto and all V9.2 eligibility; reject both bullish/bearish retests in `low` or `insufficient` previous-closed-day volatility regimes.

Use exactly existing `v92_full_interactions_20261113.volatility_asof` (rolling 20-day realized log-return standard deviation vs historical past rolling median). Do not fit new thresholds. The 1H retest gets the last fully closed daily candle at its own close, not the still-open day or later observations. Original 1H BOS watch, retest validity, next 1H open entry, 1R/2R/3R exits, max 24h, 0.1–4% stop risk and stop-first assumptions are not changed.

## Historical external events — context only, not predictive inputs

| Window [UTC start, end-exclusive] | External source | Test purpose |
|---|---|---|
| 2022-11-07 — 2022-11-22 | [IMF 2023 return/volatility spillovers](https://www.elibrary.imf.org/view/journals/001/2023/213/article-A001-en.xml) | Crypto contagion around FTX, **not assumed causal PnL** |
| 2023-03-08 — 2023-03-23 | [IMF 2023 macrofinancial crypto risks](https://www.elibrary.imf.org/view/journals/001/2023/214/article-A001-en.xml) | US banking/crypto risk stress |
| 2024-01-03 — 2024-01-18 | [SEC 10 Jan 2024 spot Bitcoin ETP approval](https://www.sec.gov/newsroom/speeches-statements/gensler-statement-spot-bitcoin-011023) | Possible market-structure transition |
| 2024-02-05 — 2024-02-11 | [Solana 6 Feb 2024 outage incident report](https://solana.com/news/02-06-24-solana-mainnet-beta-outage-report) | Network incident is distinct from perpetual market volatility |
| 2025-10-08 — 2025-10-16 | [S&P Global 2026 Bitcoin volatility assessment](https://www.spglobal.com/en/research-insights/special-reports/bitcoin-volatility-trends-deep-dive) | Extreme volatility around 10 Oct 2025 |

Events serve only as retrospective labels. A historical trade inside an event window is **not** evidence the event caused that trade's profit/loss. An event may have no trades; report zero rather than fabricating statistical support.

## External science and methodology

- [Financial Research Letters 2025: crypto momentum profits are regime dependent](https://doi.org/10.1016/j.frl.2025.108356). It is a *cross-asset weekly momentum* study, **not validation** of ATLAS 1H BOS/retest.
- [Springer 2025: cryptocurrency momentum did not deliver significant payoff in examined sample and suffered crash risk](https://link.springer.com/article/10.1007/s11408-025-00474-9). Regime and tail sensitivity matter.
- [Frontiers in Blockchain 2026: weak crypto microstructure edges and realistic fees can erase backtest gains](https://www.frontiersin.org/journals/blockchain/articles/10.3389/fbloc.2026.1811716/full). Avoid predicting after-fee alpha from gross win rate.
- [Binance historical market data availability and monthly-release schedule](https://www.binance.com/en/academy/articles/how-to-get-trading-data-via-the-binance-api). Daily files arrive the following day; monthly files are compiled on the first Monday of the following month, possibly later.

## Validation boundaries

- Historical replays: 2022–24 and 2024–26 **both previously observed**. Four backtests, paired chronological trades, exact original V9.2 baseline parity, all prior SHA256 sources, event labels, 9/25/50 bps stress. No causal identification or fresh OOS claim.
- New independent eligibility freeze: **2026-11-15T00:00:00Z**, which is after this plan and after analysis of earlier historical outcomes. Watch, retest, entry, AND exit must all be completed in eligible post-freeze months.
- Paper-forward replays use the **complete official Binance USD-M monthly 1H SHA256** files, with an immutable snapshot per month and a separately pinned source hash list. The first prospective monthly record is **2026-11**, after the verified ZIP has become available (not guaranteed on Dec 1, expected first Monday Dec 7); preflight on October has zero qualified trades.
- Compare real strategy **sequences**, not simply delete historically losing trades. Report side, trend, volatility, 9/25/50 bps net R, profit factor, max drawdown, missed winners, added trade entries and adverse period persistence; no invented success with zero trades.
- Minimum initial review target: at least 180 days and 100 independent newly closed trades per asset, positive after-cost net R, conservative uncertainty band, exposure overlap and different market states. These are **minimum review gates**, not statistical proof. A strategy that suppresses nearly all trading fails the practicality gate even with high win%.
- No live promotion, no mutation of existing V9.2 or V7 accounts, automation schedules, alerts or BTC/SOL visual cards. Any rule change must begin a new clearly versioned forward evaluation and cannot rewrite sealed monthly results.
