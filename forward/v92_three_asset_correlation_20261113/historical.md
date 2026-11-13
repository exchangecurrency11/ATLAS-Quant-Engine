# BTC / ETH / SOL — triple 30D correlation and 4H regime historical research

**Historical research, not forward evidence or a trading instruction.**

**Data:** 72 official Binance USD-M monthly 1H ZIPs SHA256 verified,
October 2024 to September 2026; all 4H bars are already CLOSED at the
original later 1H retest decision.

Pearson correlation over 180 fully closed 4H log returns per pair;
high correlation means all three pair correlations >=0.65.

| Symbol | Mode | Trades | Wins | Net R 9bps | Net R 25bps | Max DD R | Retest veto |
|---|---|---:|---:|---:|---:|---:|---:|
| BTCUSDT | V92_BASELINE | 5 | 3 | +4.1010 | +2.8146 | 1.2299 | 0 |
| BTCUSDT | THREE_CORR_GE_0P65 | 5 | 3 | +4.1010 | +2.8146 | 1.2299 | 0 |
| BTCUSDT | THREE_CORR_AND_4H_ALIGNED | 5 | 3 | +4.1010 | +2.8146 | 1.2299 | 0 |
| BTCUSDT | BTC_ETH_4H_AGREE | 5 | 3 | +4.1010 | +2.8146 | 1.2299 | 0 |
| ETHUSDT | V92_BASELINE | 6 | 2 | -2.0083 | -4.1088 | 2.1795 | 0 |
| ETHUSDT | THREE_CORR_GE_0P65 | 6 | 2 | -2.0083 | -4.1088 | 2.1795 | 0 |
| ETHUSDT | THREE_CORR_AND_4H_ALIGNED | 6 | 2 | -2.0083 | -4.1088 | 2.1795 | 0 |
| ETHUSDT | ETH_BTC_CORR_AND_BTC_4H_AGREE | 6 | 2 | -2.0083 | -4.1088 | 2.1795 | 0 |
| ETHUSDT | ETH_ATR_LE_1P5_BTC | 3 | 2 | +0.5663 | -1.1054 | 1.4028 | 3 |
| ETHUSDT | ETH_BTC_4H_AGREE_AND_ATR_LE_1P5 | 3 | 2 | +0.5663 | -1.1054 | 1.4028 | 3 |
| SOLUSDT | V92_BASELINE | 8 | 5 | +4.2607 | +2.4099 | 1.1271 | 1 |
| SOLUSDT | THREE_CORR_GE_0P65 | 8 | 5 | +4.2607 | +2.4099 | 1.1271 | 1 |
| SOLUSDT | THREE_CORR_AND_4H_ALIGNED | 5 | 4 | +4.8003 | +3.7546 | 1.0862 | 6 |
| SOLUSDT | BTC_SOL_4H_AGREE | 7 | 5 | +5.3504 | +3.6593 | 1.1271 | 2 |

## ETH baseline trades classified by information known at retest

| Entry UTC | Direction | Net R | BTC/ETH 30D corr | All3 corr >=0.65 | BTC 4H aligned | ETH ATR% / BTC ATR% |
|---|---|---:|---:|---|---|---:|
| 2025-04-09T03:00:00Z | bearish | -1.0476 | 0.8320761 | True | True | 1.7601566 |
| 2025-05-20T05:00:00Z | bullish | -1.1319 | 0.7899097 | True | True | 2.2205358 |
| 2026-01-29T14:00:00Z | bearish | +1.5436 | 0.8553992 | True | True | 1.3475035 |
| 2026-02-02T03:00:00Z | bearish | -0.3951 | 0.8881876 | True | True | 1.91144 |
| 2026-07-20T18:00:00Z | bullish | +0.4255 | 0.8898337 | True | True | 1.318532 |
| 2026-09-27T10:00:00Z | bullish | -1.4028 | 0.8632948 | True | True | 1.3440234 |

## Limitations

- Same historical period had already been studied, so selecting any winner is post-selection and not independent validation.
- A 4H candle closing *after* a retest cannot contribute to its signal.
- All three correlation is not three independent risks; shared positions may amplify joint market drawdown.
- ETH historical Binance/CoinAlyze live-source parity is not guaranteed.
- Brokerage costs assumed; no funding, exchange book slippage, real executions or liquidations.
- Tiny historical trade samples; a 0-trade filter has 0 R because it does not trade, not because profitable.
- V7 and V9.2 production and capped paper risk settings are untouched; no historical trades backfilled.

