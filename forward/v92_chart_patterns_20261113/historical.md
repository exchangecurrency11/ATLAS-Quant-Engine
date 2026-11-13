# V9.2 — 4H grafik formasyonları: tespit, başarı sıralaması, backtest

**Research only; V7, V9.2 paper account, main and notifications untouched.**

All 4H pivots confirmed by TWO additional CLOSED bars. Formations are recognized
only upon 4H CLOSING neckline/trendline/flag breakout, with no future candles.
Geometry is fixed, reproducible approximation, not subjective perfect shapes.
159 SHA256-verified Binance USD-M monthly BTC/ETH/SOL 1H files over
two scored periods: 2022-10..2024-09 and 2024-10..2026-09.
2022-05..09 indicator warmup; late period also has in-period warmup.

**Standalone success** = after next 4H open, +1R target reached BEFORE
1.5×ATR14 stop, within 6 closed 4H bars (24h); stop-first collision.
Timeouts count as unsuccessful for hit%, but mark-to-market contributes
to Net R. Costs 9bps per direction or 25bps stress, roundtrip.
These are *NOT* V9.2 trading outcomes.

## Ranking — EARLIER train period only (sort by hit%)

| Coin | Rank | Pattern | n | Target-first | Hit % | Wilson lower 95% | Net R 9bps | Net R 25bps |
|---|---:|---|---:|---:|---:|---:|---:|---:|
| BTC | 1 | DESC_TRIANGLE | 12 | 6 | 50.0 | 25.38 | +2.382 | -0.116 |
| BTC | 2 | HEAD_SHOULDERS | 9 | 4 | 44.44 | 18.88 | +2.586 | +1.146 |
| BTC | 3 | ASC_TRIANGLE | 17 | 7 | 41.18 | 21.61 | +0.592 | -2.588 |
| BTC | 4 | SYMM_TRIANGLE | 29 | 11 | 37.93 | 22.69 | -0.174 | -5.929 |
| BTC | 5 | DOUBLE_BOTTOM | 127 | 43 | 33.86 | 26.21 | -23.247 | -47.731 |
| BTC | 6 | INVERSE_HS | 18 | 6 | 33.33 | 16.28 | -1.593 | -6.261 |
| BTC | 7 | DOUBLE_TOP | 131 | 43 | 32.82 | 25.37 | -21.043 | -46.505 |
| BTC | 8 | BEAR_FLAG | 0 | 0 | — | — | +0.000 | +0.000 |
| BTC | 9 | BULL_FLAG | 0 | 0 | — | — | +0.000 | +0.000 |
| ETH | 1 | DESC_TRIANGLE | 11 | 5 | 45.45 | 21.27 | +0.954 | -1.112 |
| ETH | 2 | HEAD_SHOULDERS | 16 | 7 | 43.75 | 23.1 | +1.380 | -1.148 |
| ETH | 3 | SYMM_TRIANGLE | 28 | 12 | 42.86 | 26.51 | +4.368 | -0.283 |
| ETH | 4 | DOUBLE_BOTTOM | 114 | 42 | 36.84 | 28.55 | -3.478 | -20.905 |
| ETH | 5 | ASC_TRIANGLE | 22 | 8 | 36.36 | 19.73 | -2.952 | -6.282 |
| ETH | 6 | DOUBLE_TOP | 138 | 45 | 32.61 | 25.35 | -13.606 | -35.261 |
| ETH | 7 | INVERSE_HS | 18 | 4 | 22.22 | 9.0 | -4.254 | -7.253 |
| ETH | 8 | BEAR_FLAG | 0 | 0 | — | — | +0.000 | +0.000 |
| ETH | 9 | BULL_FLAG | 0 | 0 | — | — | +0.000 | +0.000 |
| SOL | 1 | ASC_TRIANGLE | 14 | 8 | 57.14 | 32.59 | +3.050 | +1.805 |
| SOL | 2 | INVERSE_HS | 28 | 10 | 35.71 | 20.71 | -1.397 | -3.593 |
| SOL | 3 | DOUBLE_BOTTOM | 111 | 39 | 35.14 | 26.89 | -2.004 | -12.052 |
| SOL | 4 | DESC_TRIANGLE | 15 | 5 | 33.33 | 15.18 | -0.918 | -2.163 |
| SOL | 5 | SYMM_TRIANGLE | 28 | 9 | 32.14 | 17.93 | +2.245 | +0.057 |
| SOL | 6 | DOUBLE_TOP | 122 | 31 | 25.41 | 18.52 | -20.890 | -31.496 |
| SOL | 7 | HEAD_SHOULDERS | 13 | 2 | 15.38 | 4.33 | -5.841 | -6.908 |
| SOL | 8 | BEAR_FLAG | 0 | 0 | — | — | +0.000 | +0.000 |
| SOL | 9 | BULL_FLAG | 0 | 0 | — | — | +0.000 | +0.000 |

## Later validation — SAME detector and earlier-only selection

| Coin | Pattern | Earlier n / hit% | Later n / hit% | Earlier Net R25 | Later Net R25 |
|---|---|---:|---:|---:|---:|
| BTC | DESC_TRIANGLE | 12 / 50.0 | 14 / 42.86 | -0.116 | -3.639 |
| BTC | HEAD_SHOULDERS | 9 / 44.44 | 8 / 50.0 | +1.146 | +1.117 |
| BTC | ASC_TRIANGLE | 17 / 41.18 | 23 / 43.48 | -2.588 | -5.010 |
| BTC | SYMM_TRIANGLE | 29 / 37.93 | 23 / 34.78 | -5.929 | -5.239 |
| BTC | DOUBLE_BOTTOM | 127 / 33.86 | 124 / 31.45 | -47.731 | -35.696 |
| BTC | INVERSE_HS | 18 / 33.33 | 13 / 23.08 | -6.261 | -1.704 |
| BTC | DOUBLE_TOP | 131 / 32.82 | 125 / 40.0 | -46.505 | -29.464 |
| BTC | BEAR_FLAG | 0 / None | 1 / 0.0 | +0.000 | -1.401 |
| BTC | BULL_FLAG | 0 / None | 0 / None | +0.000 | +0.000 |
| ETH | DESC_TRIANGLE | 11 / 45.45 | 17 / 47.06 | -1.112 | +1.605 |
| ETH | HEAD_SHOULDERS | 16 / 43.75 | 15 / 40.0 | -1.148 | -0.014 |
| ETH | SYMM_TRIANGLE | 28 / 42.86 | 17 / 52.94 | -0.283 | +1.710 |
| ETH | DOUBLE_BOTTOM | 114 / 36.84 | 121 / 36.36 | -20.905 | -19.017 |
| ETH | ASC_TRIANGLE | 22 / 36.36 | 17 / 35.29 | -6.282 | -3.006 |
| ETH | DOUBLE_TOP | 138 / 32.61 | 121 / 33.88 | -35.261 | -22.899 |
| ETH | INVERSE_HS | 18 / 22.22 | 18 / 33.33 | -7.253 | -2.004 |
| ETH | BEAR_FLAG | 0 / None | 1 / 100.0 | +0.000 | +0.830 |
| ETH | BULL_FLAG | 0 / None | 0 / None | +0.000 | +0.000 |
| SOL | ASC_TRIANGLE | 14 / 57.14 | 17 / 35.29 | +1.805 | -3.379 |
| SOL | INVERSE_HS | 28 / 35.71 | 13 / 38.46 | -3.593 | +0.588 |
| SOL | DOUBLE_BOTTOM | 111 / 35.14 | 120 / 27.5 | -12.052 | -24.424 |
| SOL | DESC_TRIANGLE | 15 / 33.33 | 10 / 40.0 | -2.163 | -1.754 |
| SOL | SYMM_TRIANGLE | 28 / 32.14 | 27 / 29.63 | +0.057 | -8.818 |
| SOL | DOUBLE_TOP | 122 / 25.41 | 123 / 37.4 | -31.496 | -14.211 |
| SOL | HEAD_SHOULDERS | 13 / 15.38 | 15 / 40.0 | -6.908 | -0.950 |
| SOL | BEAR_FLAG | 0 / None | 1 / 100.0 | +0.000 | +0.850 |
| SOL | BULL_FLAG | 0 / None | 0 / None | +0.000 | +0.000 |

## Locked prior-period selection and V9.2 overlay backtest

Selection uses **only 2022-2024**: >=8 independent completed pattern
events, >=45% 1R target-first, positive 25bps stressed net R;
rank eligible by Wilson lower 95%, select at most top two per symbol.
A >=30 prior-period events is merely a conservative sample gate,
not formal statistical significance; NONE is promoted live.
A = V9.2 original, B = require same-direction selected prior breakout
within 12 closed 4H bars, C = veto opposite selected breakout
within 12 closed 4H bars. Original SOL Star/Harami strict veto retained.
No selected family means B may be zero trades, NOT a profitable result.

| Period | Coin | Earlier selected | Overlay | Trades | Wins | Net R9 | Net R25 | DeltaR9 vs A | DeltaR25 vs A |
|---|---|---|---|---:|---:|---:|---:|---:|---:|
| 2022_2024 | BTC | NONE | A_V92_BASELINE | 10 | 3 | -4.266 | -7.701 | +0.000 | +0.000 |
| 2022_2024 | BTC | NONE | B_SELECTED_SAME_SIDE_ONLY | 0 | 0 | +0.000 | +0.000 | +4.266 | +7.701 |
| 2022_2024 | BTC | NONE | C_SELECTED_OPPOSITE_VETO | 10 | 3 | -4.266 | -7.701 | +0.000 | +0.000 |
| 2022_2024 | ETH | NONE | A_V92_BASELINE | 10 | 3 | -0.979 | -4.497 | +0.000 | +0.000 |
| 2022_2024 | ETH | NONE | B_SELECTED_SAME_SIDE_ONLY | 0 | 0 | +0.000 | +0.000 | +0.979 | +4.497 |
| 2022_2024 | ETH | NONE | C_SELECTED_OPPOSITE_VETO | 10 | 3 | -0.979 | -4.497 | +0.000 | +0.000 |
| 2022_2024 | SOL | ASC_TRIANGLE | A_V92_BASELINE | 12 | 6 | +4.627 | +2.004 | +0.000 | +0.000 |
| 2022_2024 | SOL | ASC_TRIANGLE | B_SELECTED_SAME_SIDE_ONLY | 1 | 0 | -1.099 | -1.275 | -5.726 | -3.279 |
| 2022_2024 | SOL | ASC_TRIANGLE | C_SELECTED_OPPOSITE_VETO | 12 | 6 | +4.627 | +2.004 | +0.000 | +0.000 |
| 2024_2026 | BTC | NONE | A_V92_BASELINE | 5 | 3 | +4.101 | +2.815 | +0.000 | +0.000 |
| 2024_2026 | BTC | NONE | B_SELECTED_SAME_SIDE_ONLY | 0 | 0 | +0.000 | +0.000 | -4.101 | -2.815 |
| 2024_2026 | BTC | NONE | C_SELECTED_OPPOSITE_VETO | 5 | 3 | +4.101 | +2.815 | +0.000 | +0.000 |
| 2024_2026 | ETH | NONE | A_V92_BASELINE | 6 | 2 | -2.008 | -4.109 | +0.000 | +0.000 |
| 2024_2026 | ETH | NONE | B_SELECTED_SAME_SIDE_ONLY | 0 | 0 | +0.000 | +0.000 | +2.008 | +4.109 |
| 2024_2026 | ETH | NONE | C_SELECTED_OPPOSITE_VETO | 6 | 2 | -2.008 | -4.109 | +0.000 | +0.000 |
| 2024_2026 | SOL | ASC_TRIANGLE | A_V92_BASELINE | 8 | 5 | +4.261 | +2.410 | +0.000 | +0.000 |
| 2024_2026 | SOL | ASC_TRIANGLE | B_SELECTED_SAME_SIDE_ONLY | 1 | 1 | +1.849 | +1.580 | -2.412 | -0.830 |
| 2024_2026 | SOL | ASC_TRIANGLE | C_SELECTED_OPPOSITE_VETO | 8 | 5 | +4.261 | +2.410 | +0.000 | +0.000 |

## Methodological constraints

- Raw target hit% must never be read without n; 1/1 is not a reliable edge. Wilson lower 95% is shown for sample-size context, NOT multiple-testing-adjusted confidence.
- Multiple families and same-date signals can overlap; 6-bar same-family cooldown reduces but does not make outcomes independent.
- The earlier split and later period have both been studied in past work. The later test is time-separated but NOT truly unseen independent data.
- V9.2 baseline must match all 6 earlier sealed references or the run fails; overlapping/cancelled trades can affect later opportunities in overlay.
- BTC/ETH/SOL 4H breakout-only standalones have different entry/stop/horizon from V9.2 BOS + retest. Do NOT equate two win percentages.
- None of the chart-family candidates are live validated; previous 50-forward-trade gate and $1000 paper caps remain intact.
- Execution price, funding, variable spread, liquidity, exchange stop fills and broker leverage are not proven by historical OHLCV.

