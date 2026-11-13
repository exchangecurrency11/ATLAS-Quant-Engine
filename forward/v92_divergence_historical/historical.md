# V9.2 CVD / RSI / MACD divergence — historical 1H study

**RESEARCH ONLY — no live orders or V7/V9.2 strategy changes.**

Data: official Binance USD-M 1H kline archives, 72 SHA256 verified ZIPs,
BTC/ETH/SOL, 2024-10-01 through 2026-09-30. CVD is only an **hourly
taker-volume-derived approximation** (not tick-trade CVD).

Pivot confirmation needs 2 future-to-pivot but already CLOSED 1H bars;
at a retest decision only information already closed by that hour is read.

## Results (9 bps / 25 bps per side assumed cost)

| Asset | Scenario | Closed trades | Win % | Net R | Stress net R | PF | Max DD R | Retest rejections |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| BTCUSDT | V91_NO_CANDLE_VETO | 5 | 60.0 | +4.101 | +2.815 | 3.8104 | 1.230 | 0 |
| BTCUSDT | V92_SELECTED_BASELINE | 5 | 60.0 | +4.101 | +2.815 | 3.8104 | 1.230 | 0 |
| BTCUSDT | CVD_DIVERGENCE_BOS_RETEST | 1 | 100.0 | +1.729 | +1.247 | None | 0.000 | 6 |
| BTCUSDT | CVD_DIVERGENCE_LIQUIDITY_SWEEP | 0 | None | +0.000 | +0.000 | None | 0.000 | 8 |
| BTCUSDT | CVD_DIVERGENCE_VOLUME_SPIKE | 1 | 100.0 | +1.326 | +1.070 | None | 0.000 | 7 |
| BTCUSDT | RSI_DIVERGENCE_BOS_RETEST | 1 | 100.0 | +1.729 | +1.247 | None | 0.000 | 6 |
| BTCUSDT | MACD_DIVERGENCE_BOS_RETEST | 0 | None | +0.000 | +0.000 | None | 0.000 | 8 |
| BTCUSDT | RSI_AND_MACD_DIVERGENCE_RETEST | 0 | None | +0.000 | +0.000 | None | 0.000 | 8 |
| ETHUSDT | V91_NO_CANDLE_VETO | 6 | 33.33 | -2.008 | -4.109 | 0.4951 | 2.179 | 0 |
| ETHUSDT | V92_SELECTED_BASELINE | 6 | 33.33 | -2.008 | -4.109 | 0.4951 | 2.179 | 0 |
| ETHUSDT | CVD_DIVERGENCE_BOS_RETEST | 0 | None | +0.000 | +0.000 | None | 0.000 | 6 |
| ETHUSDT | CVD_DIVERGENCE_LIQUIDITY_SWEEP | 0 | None | +0.000 | +0.000 | None | 0.000 | 6 |
| ETHUSDT | CVD_DIVERGENCE_VOLUME_SPIKE | 0 | None | +0.000 | +0.000 | None | 0.000 | 6 |
| ETHUSDT | RSI_DIVERGENCE_BOS_RETEST | 0 | None | +0.000 | +0.000 | None | 0.000 | 6 |
| ETHUSDT | MACD_DIVERGENCE_BOS_RETEST | 0 | None | +0.000 | +0.000 | None | 0.000 | 6 |
| ETHUSDT | RSI_AND_MACD_DIVERGENCE_RETEST | 0 | None | +0.000 | +0.000 | None | 0.000 | 6 |
| SOLUSDT | V91_NO_CANDLE_VETO | 9 | 55.56 | +3.116 | +1.008 | 1.7006 | 2.272 | 0 |
| SOLUSDT | V92_SELECTED_BASELINE | 8 | 62.5 | +4.261 | +2.410 | 2.2899 | 1.127 | 1 |
| SOLUSDT | CVD_DIVERGENCE_BOS_RETEST | 1 | 100.0 | +1.326 | +1.215 | None | 0.000 | 13 |
| SOLUSDT | CVD_DIVERGENCE_LIQUIDITY_SWEEP | 0 | None | +0.000 | +0.000 | None | 0.000 | 16 |
| SOLUSDT | CVD_DIVERGENCE_VOLUME_SPIKE | 1 | 100.0 | +1.326 | +1.215 | None | 0.000 | 13 |
| SOLUSDT | RSI_DIVERGENCE_BOS_RETEST | 0 | None | +0.000 | +0.000 | None | 0.000 | 16 |
| SOLUSDT | MACD_DIVERGENCE_BOS_RETEST | 0 | None | +0.000 | +0.000 | None | 0.000 | 16 |
| SOLUSDT | RSI_AND_MACD_DIVERGENCE_RETEST | 0 | None | +0.000 | +0.000 | None | 0.000 | 16 |

## Limitations

- Models require baseline BOS/retest AND any stated divergence; not stand-alone entry signals.
- V9.2 SOL selected Star/Harami sweep veto remains in all V9.2/divergence arms.
- Data were previously inspected in earlier V9.2 work; filters are research candidates, not independently validated signals.
- Future *relative to pivot* bars are needed to confirm it, but these bars close before the retest decision.
- Simulator uses assumed next 1H open and stop/TP fills, not executable exchange quotes.
- No funding, market depth, real fill prices or liquidation risk modeled.
- Trades here cannot count toward the separate 10/20 USDT forward paper threshold.

