# V9.2 ETH ATR and SOL BTC-4H older temporal check

**Only a historical paper study. No broker orders, live orders or V7/V9.2 edits.**
Scored UTC: 2022-10-01 to 2024-10-01 exclusive; warmup starts 2022-05-01.
87 official Binance USD-M monthly files verified against SHA256 checksums.
All 4H regime fields use candles closed by each retest-hour close.
Frozen ETH ATR threshold = 1.5; BTC/ETH 4H direction and SOL/BTC 4H
direction tests do not revise any threshold after viewing older results.

| Symbol | Mode | Trades | Wins | Net R 9bps | Net R 25bps | Profit factor | Max DD R | Regime vetoes |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| ETHUSDT | V91_V92_4H_BASELINE | 10 | 3 | -0.9789 | -4.4969 | 0.8434 | 3.3402 | 0 |
| ETHUSDT | ETH_ATR_LE_1P5_BTC | 8 | 2 | -1.6893 | -4.6926 | 0.672 | 5.1510 | 3 |
| ETHUSDT | ETH_BTC_4H_AGREE | 10 | 3 | -0.9789 | -4.4969 | 0.8434 | 3.3402 | 0 |
| ETHUSDT | ETH_BTC_4H_AGREE_AND_ATR_LE_1P5 | 8 | 2 | -1.6893 | -4.6926 | 0.672 | 5.1510 | 3 |
| SOLUSDT | V91_4H_UNFILTERED | 12 | 6 | +4.6274 | +2.0039 | 1.9699 | 2.1664 | 0 |
| SOLUSDT | V92_BASELINE_SOL_SELECTED | 12 | 6 | +4.6274 | +2.0039 | 1.9699 | 2.1664 | 0 |
| SOLUSDT | V92_BTC_4H_AGREE | 12 | 6 | +4.6274 | +2.0039 | 1.9699 | 2.1664 | 0 |

## LONG / SHORT breakdown

| Symbol | Mode | Side | Trades | Wins | Net R 9bps | Net R 25bps |
|---|---|---|---:|---:|---:|---:|
| ETHUSDT | V91_V92_4H_BASELINE | bullish | 4 | 1 | +0.4220 | -0.6057 |
| ETHUSDT | V91_V92_4H_BASELINE | bearish | 6 | 2 | -1.4009 | -3.8913 |
| ETHUSDT | ETH_ATR_LE_1P5_BTC | bullish | 3 | 0 | -1.3888 | -2.0801 |
| ETHUSDT | ETH_ATR_LE_1P5_BTC | bearish | 5 | 2 | -0.3005 | -2.6125 |
| ETHUSDT | ETH_BTC_4H_AGREE | bullish | 4 | 1 | +0.4220 | -0.6057 |
| ETHUSDT | ETH_BTC_4H_AGREE | bearish | 6 | 2 | -1.4009 | -3.8913 |
| ETHUSDT | ETH_BTC_4H_AGREE_AND_ATR_LE_1P5 | bullish | 3 | 0 | -1.3888 | -2.0801 |
| ETHUSDT | ETH_BTC_4H_AGREE_AND_ATR_LE_1P5 | bearish | 5 | 2 | -0.3005 | -2.6125 |
| SOLUSDT | V91_4H_UNFILTERED | bullish | 7 | 3 | +3.1635 | +1.6765 |
| SOLUSDT | V91_4H_UNFILTERED | bearish | 5 | 3 | +1.4639 | +0.3275 |
| SOLUSDT | V92_BASELINE_SOL_SELECTED | bullish | 7 | 3 | +3.1635 | +1.6765 |
| SOLUSDT | V92_BASELINE_SOL_SELECTED | bearish | 5 | 3 | +1.4639 | +0.3275 |
| SOLUSDT | V92_BTC_4H_AGREE | bullish | 7 | 3 | +3.1635 | +1.6765 |
| SOLUSDT | V92_BTC_4H_AGREE | bearish | 5 | 3 | +1.4639 | +0.3275 |

## Interpretation constraints

- Earlier temporal split is not prospective evidence, and this entire period may have been inspected by other repository studies.
- 9/25 bps per side are illustrative assumptions; funding, spread variation, market impact, liquidation and fill parity are not proven.
- Stop distance % (entry to fixed original stop) is recorded per trade in JSON; this is NOT a 10/20 USDT capped-account sizing simulation.
- 2022-2024 BTC and SOL V9.1/V9.2 prior backtest parity is a mandatory hard fail if it drifts.
- This backtest is not included among the 50 forward-recorded completed paper trades.
- V7 production, V9.2 prospective capped account and existing notifications remain untouched.

