# SOL-DIV-01 — causal price/CVD divergence

**Exploratory historical paper only. No live orders, alerts, production changes or prospective validation.**

Period: 2024-10-01T00:00:00Z to 2026-10-01T00:00:00Z (exclusive).
V9.2 strict-sweep baseline parity: True
Pivot: 2 left + 2 right closed candles; pivot becomes available only after the second right candle closes.
Bullish: lower price low + higher cumulative taker CVD low. Bearish: higher price high + lower cumulative taker CVD high.
Maximum pivot age: 48 bars on the tested timeframe. No OI data is used in this experiment.

| Arm | Trades | Wins | Win % | Net R 9 bps/side | Net R 25 bps/side | PF | Max DD R | Delta vs V9.2 | Divergence vetoes |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| V92_STRICT_SWEEP_CONTROL | 8 | 5 | 62.5 | 4.2607 | 2.4099 | 2.28988 | 1.1271 | +0.0000 | 0 |
| V92_PLUS_1H_CONFIRMED_CVD_DIVERGENCE | 1 | 1 | 100.0 | 1.3259 | 1.2154 | — | 0.0000 | -2.9347 | 12 |
| V92_PLUS_4H_CONFIRMED_CVD_DIVERGENCE | 0 | 0 | None | 0.0000 | 0.0000 | — | 0.0000 | -4.2607 | 15 |
| V92_PLUS_1H_OR_4H_CVD_DIVERGENCE | 1 | 1 | 100.0 | 1.3259 | 1.2154 | — | 0.0000 | -2.9347 | 12 |

## Interpretation guardrails

- CVD is cumulative taker-buy minus taker-sell base volume derived from Binance 1H kline aggregates; it is not tick-level aggressor flow or order-book delta.
- Divergence requires two confirmed pivots; no pivot is used before both right-hand confirmation candles close.
- The same V9.2 strict Star/confirmed-Harami prior-20 sweep/re-entry gate is applied before divergence in every arm.
- All tested dates have been examined before; this is not independent prospective evidence.
- A higher win rate with fewer trades is not sufficient; compare net R, stress costs, drawdown and sample size.
- Funding, actual fills, spread, liquidation and account-specific fees are not fully modeled.
- Open Interest is deliberately excluded until a complete, checksum-auditable historical source is available.
