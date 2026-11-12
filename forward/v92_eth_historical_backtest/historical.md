# V9.2 ETH official Binance historical 1D/3D backtest

**Research-only paper simulation. Not live PnL.**
Period: 2024-10-01T00:00:00Z – 2026-10-01T00:00:00Z (exclusive).
Source: Official Binance USD-M Futures monthly 1H klines; each monthly ZIP SHA256 verified; 4H and 1D derived from 1H.
3D: Derived from three consecutive fully closed UTC daily bars on epoch-aligned 3-day boundaries. Native 3D parity is not proven.
The existing engine already applies 4H/1D context at BOS; this experiment optionally re-checks 1D and derived 3D EMA20/50 at retest close.
ETH candle veto is an exploratory shadow using the same strict Star/Harami + prior20 sweep/re-entry rule. It is not enabled in the live ETH paper engine.

| Baseline | Variant | Trades | Wins | Win % | Net R | Stress R | Δ Net R |
|---|---|---:|---:|---:|---:|---:|---:|
| V7_ORIGINAL | BASELINE | 7 | 2 | 28.57 | -2.4480 | -4.7375 | 0.0000 |
| V7_ORIGINAL | CANDLE_ONLY | 7 | 2 | 28.57 | -2.4480 | -4.7375 | 0.0000 |
| V7_ORIGINAL | DAILY_RETEST_CONFIRM | 7 | 2 | 28.57 | -2.4480 | -4.7375 | 0.0000 |
| V7_ORIGINAL | 3D_RETEST_CONFIRM | 6 | 1 | 16.67 | -2.8735 | -5.0189 | -0.4255 |
| V7_ORIGINAL | DAILY_AND_3D_RETEST_CONFIRM | 6 | 1 | 16.67 | -2.8735 | -5.0189 | -0.4255 |
| V7_ORIGINAL | CANDLE_PLUS_3D | 6 | 1 | 16.67 | -2.8735 | -5.0189 | -0.4255 |
| V91_RETEST_MAX4H | BASELINE | 6 | 2 | 33.33 | -2.0083 | -4.1088 | 0.0000 |
| V91_RETEST_MAX4H | CANDLE_ONLY | 6 | 2 | 33.33 | -2.0083 | -4.1088 | 0.0000 |
| V91_RETEST_MAX4H | DAILY_RETEST_CONFIRM | 6 | 2 | 33.33 | -2.0083 | -4.1088 | 0.0000 |
| V91_RETEST_MAX4H | 3D_RETEST_CONFIRM | 5 | 1 | 20.0 | -2.4338 | -4.3901 | -0.4255 |
| V91_RETEST_MAX4H | DAILY_AND_3D_RETEST_CONFIRM | 5 | 1 | 20.0 | -2.4338 | -4.3901 | -0.4255 |
| V91_RETEST_MAX4H | CANDLE_PLUS_3D | 5 | 1 | 20.0 | -2.4338 | -4.3901 | -0.4255 |

Costs are the existing illustrative 9 bps/side base and 25 bps/side stress. Funding, true fills, dynamic spread and liquidation are not fully modeled.
No live orders, alerts, or V7/V9.1 changes. No strategy promotion from this retrospective sample.

