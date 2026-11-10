# V9: BEFORE next 4H starts — GREEN / RED of that candle

## Exact prediction contract
- Decision **T−5 minutes**, target Binance Futures 4H candle **[T,T+4h)**.
- GREEN iff next candle **close > its OWN open**. RED iff **close < own open**.
- Decision does **NOT** know next open, current 4H final hour, or future prices.
- Last fully closed 4H at T−5m ends **T−4h**. Last available full 1H ends **T−1h**.
- BTC/ETH/SOL same UTC 4H boundaries, official SHA-256 archives.
- Predeclared expanding-walk-forward folds; C=0.2 fixed logistic, no tuning, 55/60/65% confidence coverage disclosed.
- Historical 2023–2026 has already been investigated elsewhere; these results are NOT independent prospective evidence.
- No real orders, no stop/TP, no funding/cost claims, NO live signal enablement.

| Asset | Test candles | Majority | Last completed 4H color | Logistic all | >=60% confidence | >=65% confidence |
|---|---:|---:|---:|---:|---:|---:|
| BTCUSDT | 6024 | 3084/6024 (51.2%) | 2952/6024 (49.0%) | 3048/6024 (50.6%) | 1051/2099 (50.07%) | 571/1130 (50.53%) |
| ETHUSDT | 6024 | 3022/6024 (50.17%) | 2973/6024 (49.35%) | 3110/6024 (51.63%) | 1194/2291 (52.12%) | 609/1159 (52.55%) |
| SOLUSDT | 6006 | 3011/6006 (50.13%) | 2979/5988 (49.75%) | 3066/6006 (51.05%) | 1219/2378 (51.26%) | 669/1327 (50.41%) |

## Per 6 predeclared periods

### BTCUSDT
| Period | All predictions | 60% confidence | Coverage at 60% |
|---|---:|---:|---:|
| 2024-H1 | 519/1092 (47.53%) | 380/801 (47.44%) | 73.35% |
| 2024-H2 | 565/1104 (51.18%) | 241/493 (48.88%) | 44.66% |
| 2025-H1 | 579/1086 (53.31%) | 159/284 (55.99%) | 26.15% |
| 2025-H2 | 588/1104 (53.26%) | 104/189 (55.03%) | 17.12% |
| 2026-H1 | 522/1086 (48.07%) | 136/272 (50.0%) | 25.05% |
| 2026-Q3 | 275/552 (49.82%) | 31/60 (51.67%) | 10.87% |

### ETHUSDT
| Period | All predictions | 60% confidence | Coverage at 60% |
|---|---:|---:|---:|
| 2024-H1 | 571/1092 (52.29%) | 353/688 (51.31%) | 63.0% |
| 2024-H2 | 563/1104 (51.0%) | 259/474 (54.64%) | 42.93% |
| 2025-H1 | 593/1086 (54.6%) | 198/351 (56.41%) | 32.32% |
| 2025-H2 | 568/1104 (51.45%) | 229/451 (50.78%) | 40.85% |
| 2026-H1 | 531/1086 (48.9%) | 126/267 (47.19%) | 24.59% |
| 2026-Q3 | 284/552 (51.45%) | 29/60 (48.33%) | 10.87% |

### SOLUSDT
| Period | All predictions | 60% confidence | Coverage at 60% |
|---|---:|---:|---:|
| 2024-H1 | 568/1091 (52.06%) | 414/796 (52.01%) | 72.96% |
| 2024-H2 | 581/1104 (52.63%) | 285/536 (53.17%) | 48.55% |
| 2025-H1 | 555/1083 (51.25%) | 190/369 (51.49%) | 34.07% |
| 2025-H2 | 596/1099 (54.23%) | 149/288 (51.74%) | 26.21% |
| 2026-H1 | 496/1083 (45.8%) | 155/328 (47.26%) | 30.29% |
| 2026-Q3 | 270/546 (49.45%) | 26/61 (42.62%) | 11.17% |

**IMPORTANT:** A top historical percentage does not establish 75% prospective accuracy. No data from current/future 4H candle at T is in the features. Any model selection from these results is post-hoc.
