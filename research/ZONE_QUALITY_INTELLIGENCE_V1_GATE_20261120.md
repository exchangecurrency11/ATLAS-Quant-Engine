# ATLAS — Zone Quality Intelligence V1 research gate (20 Nov 2026)

**Scope:** isolated research branch only. No changes to main, V7/V9 paper books, market publishers, alerts, Actions, portfolio accounting or real orders.

## Verified baseline and audit limits

- GitHub research branch already contained four prior zone reports, the V0 selector and V0 unit-test definitions.
- The widened report lists **21 BOS events**: **19** completed 12-hour outcomes, **2** censored. Recomputed from the published **rounded report rows**: average net R per completed opportunity **−0.2555789** (zone method, three SKIPs = zero deployed R) and **−0.2015789** (fixed 2 ATR). Same 16 zone-tradable opportunities: **−0.3035** and **−0.4010**. This is a report arithmetic audit, **not** an independent candle-by-candle backtest.
- BTC $64,738 1H bearish BOS: historical market commit 81c18a112d785f837ccccb34520e83c7b5276871 published **2026-11-14 21:04:23 UTC**; structure commit 085c7d70147a0493bffc8a53de6109e08907101e published **21:04:36 UTC**. The 21:05 UTC as-of cutoff is only research illustration; exact user notification delivery was not independently verified.
- Widened-audit per-event JSON/CSV and replay scripts mentioned in the conversation ZIP were **not found in GitHub's research directory**. Fully independent event-by-event reproduction requires these data, source publication times and each candle chain.
- Branch-filtered GitHub Actions query yielded **zero workflow runs** at this check. **11 new local isolated V1 synthetic tests passed**. No branch CI or entire V0-suite passing claim.

## Frozen V1 hypothesis (not optimized for previous outcomes)

Implementation: research/zone_quality_intelligence_v1.py. Tests: research/tests/test_zone_quality_intelligence_v1.py. Version: ZQI-V1-PRECALIBRATION-20261120.

1. Reuse V0 as-of filtering unchanged: correct BTC/SOL side, only source-pinned known-before-cutoff and ahead-of-close OB/open-FVG/chart-liquidity features. Both signal wick extremes are mandatory. The signal candle must not have touched the target.
2. Require explicitly supplied positive 1H ATR for geometry. Reject invalid/wrong-time inputs or future-published sources. Source commit publication metadata and ATR's own historical data source still require independent upstream attestation.
3. Group regions using geometric gap tolerance **0.10 × ATR**. A candidate enters a group only if close to **each existing member**; avoid transitive bridging. Grouping does not imply independent evidence or actual institutional orders.
4. Index = sum of the following components, clamped 0 to 100:

| Pre-specified feature | Index points |
|---|---:|
| V0 as-of eligible candidate/group | +35 |
| At least two distinct feature kinds | +12 |
| Three distinct feature kinds | +6 additionally |
| At least two distinct timeframes | +12 |
| Three distinct timeframes | +6 additionally |
| Eligible OB volumeRatio >= 2.0 | +10 |
| Otherwise volumeRatio >= 1.3 | +5 |
| Eligible fresh OB | +6 |
| Only retested OB, no fresh OB | -5 |
| Eligible BOS-backed OB | +5 |
| Eligible OB with fvgConfluence true | +5 |
| Group envelope wider than 2 ATR | -12 |
| Group envelope wider than 4 ATR | -12 additionally |

5. Distances are tie-breakers only, **not** part of zone quality. Eligible OB source metadata are joined using timeframe, price body, state and confirmed time; never reselect an invalid or future OB. Outputs expose price envelopes, timeframes, contributing features, component points, wick exclusions and provenance. Absent features produce **NO_ZONE**, not a fabricated target.
6. The numerical index is an **uncalibrated structural-evidence score**, not the estimated probability of a reversal, profitability, trading signal or execution recommendation. Example: 79 index points does **not** mean 79% chance. Feature correlation and truncated retained source windows remain material limitations.

## Reproducibility and test result

From research directory: python -m unittest discover -v -s tests -p 'test_zone_quality_intelligence_v1.py'

**11 synthetic unit tests passed locally**, covering SHORT, LONG symmetry, source/confirmation leakage, invalid ATR, missing wick data, signal-wick exclusions, NO_ZONE, clustering, anti-transitive grouping, broad-zone penalty and distance versus evidence separation.

**Not claimed:** full repository test pass, GitHub CI run, complete 21-case OHLC rerun, full CHoCH history, source ATR attestation, external notification receipt timestamp, holdout validation or PnL advantage.

## Next research-only gates

1. Persist exact BOS JSON/CSV/replay scripts with per-event and per-candle SHA/publication metadata; independently audit completeness, overlaps, duplicates, two censored events and all 21 source snapshots.
2. Expand to all historical eligible BOS; audit an independent CHoCH cohort. Preserve NO_ZONE, skipped, losing and failed-reversal cases. Stratify BTC LONG, BTC SHORT, SOL LONG, SOL SHORT and keep CHoCH separate.
3. Freeze V1 coefficients and grouping tolerance **before** matching future reactions, first touches, >=0.5 ATR within three subsequent closed 1H candles, later breaches and exit performance. Audit delayed entry, stop-first same-bar tie and actual trading-cost assumptions.
4. Use chronological disjoint train/holdout periods and then prospective paper observations. Any weight/tolerance revisions must create a **new model version** and fresh holdout. Compare with the 2-ATR research benchmark and, only with proper paper-trade provenance, real V7 exits.
5. Retain research-only isolation and never merge to main or change signals, live brokers or sealed paper books without separate explicit approval.
