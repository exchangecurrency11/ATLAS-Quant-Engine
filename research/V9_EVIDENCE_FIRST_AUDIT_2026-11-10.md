# V9 Evidence-First Architecture — Binance BTC/ETH/SOL Perpetual
**Research audit:** 2026-11-10. **Scope:** paper-only, no orders, no production or alert changes. Main trading candidate: SOL; BTC/ETH synchronized market context.

## Executive decision
Do not add another stack of indicators or claim a 75% edge. Separate the *market-state classifier*, *zone/setup generator*, *entry confirmation*, *trade selection*, *execution simulator*, and *forward evidence collection*. The current V8.6 retrospective 24h SOL direction result is 37/72 (51.39%) with 893/965 no-signal checkpoints; V8.5 all-variant paper sample previously returned 451 simulated trades, 33.9% profitable and negative aggregate event PnL. These are exploratory, repeatedly examined samples, not validated prospective performance.

## Confirmed audit observations (repository-based)

1. **Primary archive drops valuable already-available columns.** `download_binance_um_history.py::parse_zip` reads 12-column official USD-M Binance kline CSV, but unpacks only `o,h,l,c,v` (`record[1:6]`). It discards quote asset volume, number of trades, taker buy base and quote volume. Preserve raw fields, align availability, and test against official CSV definitions. The source is already checksum-verified. Reference: https://github.com/binance/binance-public-data/blob/master/README.md
2. **Coinalyze responses have underused `bv`, `tx`, `btx`.** `market_structure.py::candles_from_history` retains only t/o/h/l/c/v. Data integration must preserve documented extra fields only when values and semantics are verified; don't assume all provider fields are same units. https://api.coinalyze.net/v1/doc/
3. **Existing derivative research must be REUSED, not rebuilt or overclaimed.** `forward/sol_v8_bv_audit/latest.json` (on `experiment/v8-sol-derivatives-probe-20261110`) retrospectively reconciled provider `bv` vs official Binance taker buy on 216/216 completed 1H SOL observations (2026-11-01..09), zero mismatches at the predefined tolerances. `forward/sol_derivatives_quality/latest.json` verifies 2,592/2,592 5m SOL OI and taker observations in that historical window, BUT these archives were obtained after the period; not contemporaneous live signals. `forward/sol_v7_oi_taker_study/latest.json` finds on 14 examined paper trades OI feature descriptive AUC ~0.633, unadjusted exact two-sided permutation p ~0.456; taker signed pressure AUC ~0.408, p ~0.620. Insufficient to enable either as a hard trade filter.
4. **OHLCV-only "Wyckoff", Order Block, FVG and liquidity levels are candidates, not proof.** `market_structure.py` pivot swing is only available after `pivot_span` following bars, and OB is an opposite-candle heuristic after BOS. Keep `confirmedAt` enforced at first *available time*, not origin time.
5. **Different experiments optimize incompatible targets.** Some report next-4H or next-24H direction, some event paper TP/SL. Need one comparable baseline: entry price at next executable bar after signal, first touch of executable TP/SL (or 24h time barrier), all costs and constraints. Direction accuracy is a secondary chart statistic.
6. **Exposure assumptions conflict if $100 × 10x is used as full notional.** $1000 notional and 9bps fee+slippage each side = $1.80 round trip, exceeding the $0.50 planned risk cap before the stop move. For a 1% stop and same 18bps round-trip assumption, conservative maximum notional ≈$42.37, or $4.24 isolated margin at 10x, **before funding**. Fee estimates are scenario assumptions; actual account fee tier, spreads and stops must be verified. Position sizing is risk-first, not margin-first.
7. **Incomplete archives fail closed.** Earlier V8 research identified incomplete SOL monthly 2022-02, 2022-04 and 2026-10. Preserve source manifests and independent unbroken periods; do not resample over missing gaps.
8. **Symbol/clock mismatch risk.** TradingView default spot symbol may differ from Binance USD-M perpetual. All three instruments need identical UTC contract type and synchronized closed 1H, 4H, Daily data with known publish/availability timestamps.
9. **Scheduled checks are not level-2 streaming.** GitHub Action cron snapshots and Coinalyze API periodic reads are not a historical order-book or tick-by-tick record and must not be represented as such.
10. **Data science selection bias is high.** Prior V8.1..V8.6 tested many post-hoc filters/thresholds on repeatedly inspected periods; choose future rules before test, maintain versioned trial ledger, show every negative result.

## What to retain, demote or remove
| Item | V9 choice | Why |
|---|---|---|
| Daily+4H broad rectangles | RETAIN as context; ATR-normalized support/resistance/role flip and separately anchored volume/price areas | avoid a fixed 8.5% width for all regimes |
| Pivot Line, Fibonacci | RETAIN as distances and overlap with structure, not independent hard votes | correlated geometry |
| SMA100/200 + EMA20/50 | KEEP one slow-trend family (SMA100/200); use fast EMA only if proven incremental | correlated votes create fake confidence |
| RSI14 | RETAIN for overbought/oversold *risk* and trend weakening; no blanket RSI>50 gate | avoid late short after exhausting sells |
| Wyckoff | DEMOTE to measurable OHLCV event hypotheses (range/spring/UTAD/SOW/LPSY) with deterministic confirm times | cannot verify institutional behavior via candles |
| Liquidity sweep / BOS / CHoCH | RETAIN strict candidate-event lifecycle with closed 1H/15m/5m confirmation; chart sweep != actual stop order | separates setup from entry |
| OB/FVG | RETAIN as point-in-time candidate zone and retest context, not buy/sell execution signal | heuristic rules and repaint risk |
| MACD | OPTIONAL diagnostic only, not a required hard gate | duplicate momentum evidence |
| Universal 8/10 score and fixed %75 hit gate | RETIRE as entry rule; create net-expectancy calibrated selector | tiny n and high correlation |
| 4H-close directional win as "trade win" | REMOVE conflation; record separately | execution timing, TP/SL first touch matter |

## Data acquisition prioritized
**P0 no extra paid API:** Persist complete official USD-M klines (at least SOL 5m, 1h; BTC/ETH 1h), including buy base/quote volume, trade count, quote volume, plus verified SHA256 ZIP and immutable provenance. Preserve all Coinalyze OHLCV fields with reconciled names. Add funding-rate settlement history from Binance USD-M `/fapi/v1/fundingRate` or verified historical archive. Measure symbol-specific exchangeInfo tick size, lot size, min notional; user-specific commission rate remains unknown. Do not infer current fee tier.

**P0 live snapshot:** Poll already available Coinalyze `/v1/open-interest-history`, `/v1/funding-rate-history`, `/v1/liquidation-history`, `/v1/ohlcv-history` on BTC, ETH, SOL; capture synchronized closed 1H/4H and 5m if adequate retention. Its intraday history is limited to ~1500-2000 points (timeframe dependent); collect your own observations prospectively. Binance REST OI statistics and taker ratios are limited to around 30 days; some GitHub runner requests returned HTTP 451; no pretending that inaccessible endpoints were fetched. Every row must include `event_time`, `available_at`, `received_at`, `exchange`, `symbol`, `unit`, `quality`, `sourceHash`.

**P1 conditional paid:** Historical L2 orderbook, liquidation heatmaps, historical bid/ask spread if later proven incremental. Consider CoinGlass tiers ONLY if free OHLCV+OI+taker+funding pilot fails to cover a *specific* missing feature. Modelled liquidation heatmap != observed forced liquidation. Book walls can move and are not guaranteed resting fills.

## Test protocol — freeze before looking at results
1. Select candidate events using only closed point-in-time data: zone touch/sweep + 1H or 15m confirmation. Keep all rejected candidates with codes.
2. Generate *triple barrier labels*: TP (e.g. 1.5R/2R), stop (1R), max holding 24h; use next tradable open, 5m/1m whenever possible to order intrabar stop-vs-target; otherwise pessimistic stop-first.
3. Account simulation at $100 starting equity, 10x isolated upper bound, 0.50 USDT *maximum planned risk including expected entry/exit costs*, actual lot/min notional, mark/last differences, funding, adverse gap, overlapping positions and daily stop rule.
4. Segment regimes using observable, minimal inputs: trend-follow, range/mean-reversion, compression/breakout, and high-volatility/uncertain; no forced directional trade in ambiguous regime.
5. Baselines: no trade; simple SMA trend + 1H BOS; ATR-band bounce; previous V8.5; V9 with OI/taker ablations. Compare same opportunities and same entry/exit simulator.
6. If simple strategies do not pass, evaluate interpretable logistic regression then LightGBM/CatBoost/gradient-boosted trees. Feature importance, calibration/Brier, time-ordered walk-forward with purging/embargo, and confidence abstention. Never let an LLM auto-pick side or TP/SL from hallucinated charts.
7. Keep trial registry of all parameter variations, data versions and failures. Predeclare a final untouched FUTURE-forward sample; historical 2021–2026 already inspected and do not call any slice from it "clean untouched".
8. Report per asset, side, regime and month: trade count, no-trade rate, realized/hypothetical net R, P&L, max drawdown, profit factor, median holding time, slippage, funding, risk breaches, confidence intervals and sampling caveats. Validate realistic capacity/min-order constraints.
9. Only promote to next research gate after *positive costed net expectancy*, stable results across market regimes, data freshness, trade quality, and a prospective paper sample with independent checkpoints. A 75% direction rate is a monitored aspiration, never a profitability guarantee or sufficient release criterion.

## Third-party frameworks — evaluate, not mandatory rewrites
- **Freqtrade/FreqAI:** open-source strategy research, dry-run, lookahead-analysis, recursive-analysis; FreqAI offers feature engineering/outlier controls. Strong first external parity check.
- **Jesse:** crypto futures candle backtests, transaction costs, visual chart and Monte Carlo/significance tests; candidate second engine cross-validation.
- **NautilusTrader:** event-driven bid/ask/order-book replay and simulation/live parity; consider later only if fine-grained data and event-driven exchange connectivity are justified.
- **Hummingbot:** controller/executor/market-making framework; not automatically ideal for a directional SOL 1H strategy, unless strategy shifts to providing liquidity.
- **vectorbt:** fast feature ablation/scenario backtest, but speed makes overfitting easier without independent tests.
- **TradingView Pine:** visualization, confirmations and user manual review; non-repainting `request.security`/closed bars, standard candles and broker-emulator costs are mandatory if comparing backtests.

## Verified external references
- Binance public Futures Klines data shape: https://github.com/binance/binance-public-data/blob/master/README.md
- Binance USD-M market-data endpoints (historical OI 1 month, taker ratio 30 days): https://developers.binance.info/en/docs/catalog/core-trading-derivatives-trading-usd-s-m-futures/api/rest-api/market-data
- Coinalyze API fields, 40calls/min and 1500–2000 intraday retention: https://api.coinalyze.net/v1/doc/
- CoinGlass coverage and tier restrictions: https://docs.coinglass.com/reference/getting-started-with-your-api
- Freqtrade lookahead audit: https://www.freqtrade.io/en/stable/lookahead-analysis/
- Freqtrade recursive warmup audit: https://docs.freqtrade.io/en/stable/recursive-analysis/
- TradingView repainting: https://www.tradingview.com/pine-script-docs/concepts/repainting/
- Hummingbot execution/controller architecture: https://hummingbot.org/strategies/
- Jesse testing: https://docs.jesse.trade/docs/backtest/
- NautilusTrader event-driven parity: https://nautilustrader.io/docs/
- Selection bias and multiple trials: https://escholarship.org/uc/item/4w1110bb
- Deflated Sharpe Ratio: https://doi.org/10.3905/jpm.2014.40.5.094
- Triple barrier and meta-labeling: https://random-docs.readthedocs.io/en/latest/implementations/tb_meta_labeling.html
- Current Coinalyze OI & Binance source quality artifacts: https://github.com/exchangecurrency11/BTC-SOL-ANALYS-S/tree/experiment/v8-sol-derivatives-probe-20261110

**Safety:** This file is research only. No account credentials, no trade instructions, no actual orders, no deployment to main and no implied guarantee of 75% success.
