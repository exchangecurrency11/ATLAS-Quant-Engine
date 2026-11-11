# V7 original 4H market-bias votes vs frozen V9 retrospective 4H own-candle color

**Test window:** 2026-11-03T20:00:00Z to 2026-11-11T12:00:00Z.

**CRITICAL:** V7 is a real prior-hour GitHub paper snapshot, but its **4H trend vote is NOT a V7 BOS/retest trading signal**. The V9 frozen model colors below were **replayed after outcomes had already occurred**. Therefore this study does not establish prospective accuracy or justify notifications.

| Asset | V9 all 4H (hits/N) | Paired N | V9 paired | V7 prior 4H vote PROXY | Difference pp |
|---|---:|---:|---:|---:|---:|
| BTCUSDT | 17/46 (36.96%) | 30 | 11/30 (36.67%) | 14/30 (46.67%) | -10.0 |
| ETHUSDT | 24/45 (53.33%) | 3 | 0/3 (0.0%) | 0/3 (0.0%) | 0.0 |
| SOLUSDT | 22/46 (47.83%) | 30 | 12/30 (40.0%) | 14/30 (46.67%) | -6.67 |

## Why this does not compare V7 strategy trade win rates
V7's original BOS/retest trade performance measures hypothetical entry, stop, and TP outcomes across multiple 1H candles, not the own-body color of next 4H. The V7 4H vote is only a direction-context baseline. Missing V7 forward snapshots, mixed votes and post-target observations are excluded rather than backfilled. Official V9 forward locked paper journal remains separate and unaffected.

Source: BTC/SOL V7 GitHub experiment branch forward/snapshots and ETH independent V7 forward/eth/snapshots; read-only Coinalyze BTC/ETH/SOL Binance perpetual 1H and Daily; frozen V9 model, no training or fitted thresholds.

## Last six paired evidence rows (per asset)

**BTCUSDT**
- 2026-11-10T12:00:00Z V9(replayed)=GREEN V7(4H vote proxy)=None Actual=RED
- 2026-11-10T16:00:00Z V9(replayed)=RED V7(4H vote proxy)=None Actual=GREEN
- 2026-11-10T20:00:00Z V9(replayed)=GREEN V7(4H vote proxy)=RED Actual=GREEN
- 2026-11-11T00:00:00Z V9(replayed)=GREEN V7(4H vote proxy)=RED Actual=RED
- 2026-11-11T04:00:00Z V9(replayed)=RED V7(4H vote proxy)=RED Actual=GREEN
- 2026-11-11T08:00:00Z V9(replayed)=GREEN V7(4H vote proxy)=RED Actual=RED

**ETHUSDT**
- 2026-11-10T20:00:00Z V9(replayed)=RED V7(4H vote proxy)=RED Actual=GREEN
- 2026-11-11T00:00:00Z V9(replayed)=RED V7(4H vote proxy)=RED Actual=GREEN
- 2026-11-11T04:00:00Z V9(replayed)=RED V7(4H vote proxy)=RED Actual=GREEN

**SOLUSDT**
- 2026-11-10T12:00:00Z V9(replayed)=RED V7(4H vote proxy)=RED Actual=RED
- 2026-11-10T16:00:00Z V9(replayed)=RED V7(4H vote proxy)=RED Actual=GREEN
- 2026-11-10T20:00:00Z V9(replayed)=RED V7(4H vote proxy)=RED Actual=GREEN
- 2026-11-11T00:00:00Z V9(replayed)=RED V7(4H vote proxy)=RED Actual=GREEN
- 2026-11-11T04:00:00Z V9(replayed)=RED V7(4H vote proxy)=RED Actual=GREEN
- 2026-11-11T08:00:00Z V9(replayed)=GREEN V7(4H vote proxy)=RED Actual=GREEN
