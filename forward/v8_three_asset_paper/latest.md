# BTC / ETH / SOL — V8 multi-timeframe paper-only historical test

**Official source:** Binance USD-M Futures 1H monthly ZIP + SHA256 CHECKSUM.
**Timeframes:** 1H archive; 4H and Daily aggregated from exact closed 1H.
**Strategy:** V4 BOS → later retest → next 1H open; V7 ATR/RVOL quality; V8 EMA20/50/200, RSI14, MACD, OB, FVG, Fibonacci 0.382/0.618, equal-high/low liquidity, 24H sweep, pin/engulfing form.

**Data:** 2025-01 through 2026-09; **untuned holdout entry dates:** 2026-07-01T00:00:00Z onward.

| Coin | Variant | Holdout trades | Win rate | Avg net R | Profit factor | Simulated net PnL ($100 independent account) |
|---|---|---:|---:|---:|---:|---:|
| BTCUSDT | V4_baseline | 1 | 0.0 | -1.4772 | 0.0 | -0.5000 |
| BTCUSDT | V7_quality_retest | 0 | N/A | N/A | N/A | +0.0000 |
| BTCUSDT | V8_all_OHLCV_confluence | 0 | N/A | N/A | N/A | +0.0000 |
| ETHUSDT | V4_baseline | 4 | 75.0 | 0.65762 | 2.8752 | +1.2067 |
| ETHUSDT | V7_quality_retest | 2 | 50.0 | -0.48865 | 0.3033 | -0.3032 |
| ETHUSDT | V8_all_OHLCV_confluence | 2 | 50.0 | -0.48865 | 0.3033 | -0.3032 |
| SOLUSDT | V4_baseline | 3 | 66.67 | 1.12036 | 9.3535 | +1.4950 |
| SOLUSDT | V7_quality_retest | 0 | N/A | N/A | N/A | +0.0000 |
| SOLUSDT | V8_all_OHLCV_confluence | 0 | N/A | N/A | N/A | +0.0000 |

## Important rules / limitations
- ALL 4H/1D features refer only to already closed candles at the BOS hour.
- 1H BOS requires a later closed retest; paper entry is NEXT open.
- If stop and target share a candle, stop is hit first.
- Cost assumption: 6 bps fee + 3 bps slippage per side, illustrative.
- 100 USDT START per coin; <=0.50 USDT risk including modeled entry/exit costs per trade, 10x isolated notional cap.
- USD report is a **standalone account per asset**, not a joint portfolio and not observed fills.
- Funding, OI/taker, live spread, partial fills, liquidations, gap-through-stop and changing exchange rules are NOT included in PnL.
- No model fitting on holdout in this run. Historical sample and tests do not establish forward profitability.
- OHLCV OB/liquidity zones are heuristic; they are not verified institutional orders.
- Strategy intentionally uses scored confluence; all filters are evaluated, NOT all must be simultaneously true.
- No live broker orders or production changes; do NOT activate live trades from this report alone.
