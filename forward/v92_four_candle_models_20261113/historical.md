# BTC / ETH / SOL — A-B-C-D pattern experiment

**Research only; V7, V9.2 live paper account, alerts and orders unchanged.**

Models: **A** exact V9.2 baseline; **B** A plus observe-only patterns
(identical fills); **C** reject opposing prior-20 sweep/reentry
Star/confirmed Harami/Engulfing or confirmed Hikkake false break;
**D** require same-direction closed Star/Harami/Engulfing/Hikkake
within last 4×1H or 2×4H complete bars (no extra sweep condition).
Baseline SOL keeps its existing strict Star/Harami sweep veto in every model.
All use unchanged V7 BOS filter, 4H maximum retest, next-hour open,
original stop, TP1–TP3, 24-hour max hold and 9/25 bps/yön illustrative cost.
Data: official Binance USDT-M monthly 1H ZIPs SHA256 verified,
4H and daily aggregated exactly from 1H. No actual execution.

| Period | Symbol | Mode | Trades | Wins | Win% | Net R 9bps | Net R 25bps | Delta R vs A | PF | MaxDD R | Vetoes |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2022_2024 | BTCUSDT | A_BASELINE | 10 | 3 | 30.0 | -4.2658 | -7.7013 | +0.0000 | 0.5005 | 5.088 | 0 |
| 2022_2024 | BTCUSDT | B_OBSERVATION_ONLY | 10 | 3 | 30.0 | -4.2658 | -7.7013 | +0.0000 | 0.5005 | 5.088 | 0 |
| 2022_2024 | BTCUSDT | C_OPPOSING_CONTEXT_VETO | 10 | 3 | 30.0 | -4.2658 | -7.7013 | +0.0000 | 0.5005 | 5.088 | 0 |
| 2022_2024 | BTCUSDT | D_SAME_DIRECTION_CONFIRM | 3 | 1 | 33.33 | -1.8087 | -2.6539 | +2.4571 | 0.2233 | 2.329 | 11 |
| 2022_2024 | ETHUSDT | A_BASELINE | 10 | 3 | 30.0 | -0.9789 | -4.4969 | +0.0000 | 0.8434 | 3.340 | 0 |
| 2022_2024 | ETHUSDT | B_OBSERVATION_ONLY | 10 | 3 | 30.0 | -0.9789 | -4.4969 | +0.0000 | 0.8434 | 3.340 | 0 |
| 2022_2024 | ETHUSDT | C_OPPOSING_CONTEXT_VETO | 10 | 3 | 30.0 | -0.9789 | -4.4969 | +0.0000 | 0.8434 | 3.340 | 0 |
| 2022_2024 | ETHUSDT | D_SAME_DIRECTION_CONFIRM | 3 | 1 | 33.33 | -0.9565 | -2.6569 | +0.0224 | 0.6212 | 2.525 | 11 |
| 2022_2024 | SOLUSDT | A_BASELINE | 12 | 6 | 50.0 | +4.6274 | +2.0039 | +0.0000 | 1.9699 | 2.166 | 0 |
| 2022_2024 | SOLUSDT | B_OBSERVATION_ONLY | 12 | 6 | 50.0 | +4.6274 | +2.0039 | +0.0000 | 1.9699 | 2.166 | 0 |
| 2022_2024 | SOLUSDT | C_OPPOSING_CONTEXT_VETO | 11 | 6 | 54.55 | +5.1815 | +2.9506 | +0.5541 | 2.2288 | 1.612 | 2 |
| 2022_2024 | SOLUSDT | D_SAME_DIRECTION_CONFIRM | 1 | 1 | 100.0 | +0.0423 | -0.0658 | -4.5851 | — | 0.000 | 12 |
| 2024_2026 | BTCUSDT | A_BASELINE | 5 | 3 | 60.0 | +4.1010 | +2.8146 | +0.0000 | 3.8104 | 1.230 | 0 |
| 2024_2026 | BTCUSDT | B_OBSERVATION_ONLY | 5 | 3 | 60.0 | +4.1010 | +2.8146 | +0.0000 | 3.8104 | 1.230 | 0 |
| 2024_2026 | BTCUSDT | C_OPPOSING_CONTEXT_VETO | 4 | 2 | 50.0 | +2.1970 | +1.0812 | -1.9040 | 2.5056 | 1.230 | 1 |
| 2024_2026 | BTCUSDT | D_SAME_DIRECTION_CONFIRM | 1 | 1 | 100.0 | +1.9214 | +1.7817 | -2.1796 | — | 0.000 | 7 |
| 2024_2026 | ETHUSDT | A_BASELINE | 6 | 2 | 33.33 | -2.0083 | -4.1088 | +0.0000 | 0.4951 | 2.179 | 0 |
| 2024_2026 | ETHUSDT | B_OBSERVATION_ONLY | 6 | 2 | 33.33 | -2.0083 | -4.1088 | +0.0000 | 0.4951 | 2.179 | 0 |
| 2024_2026 | ETHUSDT | C_OPPOSING_CONTEXT_VETO | 6 | 2 | 33.33 | -2.0083 | -4.1088 | +0.0000 | 0.4951 | 2.179 | 0 |
| 2024_2026 | ETHUSDT | D_SAME_DIRECTION_CONFIRM | 3 | 1 | 33.33 | -2.0249 | -2.9698 | -0.0166 | 0.1736 | 2.025 | 3 |
| 2024_2026 | SOLUSDT | A_BASELINE | 8 | 5 | 62.5 | +4.2607 | +2.4099 | +0.0000 | 2.2899 | 1.127 | 0 |
| 2024_2026 | SOLUSDT | B_OBSERVATION_ONLY | 8 | 5 | 62.5 | +4.2607 | +2.4099 | +0.0000 | 2.2899 | 1.127 | 0 |
| 2024_2026 | SOLUSDT | C_OPPOSING_CONTEXT_VETO | 8 | 5 | 62.5 | +4.2607 | +2.4099 | +0.0000 | 2.2899 | 1.127 | 0 |
| 2024_2026 | SOLUSDT | D_SAME_DIRECTION_CONFIRM | 1 | 1 | 100.0 | +0.8272 | +0.6734 | -3.4335 | — | 0.000 | 10 |

## Missed winners / avoided losers vs baseline

| Period | Symbol | Mode | Baseline winners missed | Baseline losers avoided | New variant trades | Delta R 9bps | Delta R 25bps |
|---|---|---|---:|---:|---:|---:|---:|
| 2022_2024 | BTCUSDT | C_OPPOSING_CONTEXT_VETO | 0 | 0 | 0 | +0.0000 | +0.0000 |
| 2022_2024 | BTCUSDT | D_SAME_DIRECTION_CONFIRM | 2 | 5 | 0 | +2.4571 | +5.0474 |
| 2022_2024 | ETHUSDT | C_OPPOSING_CONTEXT_VETO | 0 | 0 | 0 | +0.0000 | +0.0000 |
| 2022_2024 | ETHUSDT | D_SAME_DIRECTION_CONFIRM | 2 | 5 | 0 | +0.0224 | +1.8401 |
| 2022_2024 | SOLUSDT | C_OPPOSING_CONTEXT_VETO | 0 | 1 | 0 | +0.5541 | +0.9466 |
| 2022_2024 | SOLUSDT | D_SAME_DIRECTION_CONFIRM | 5 | 6 | 0 | -4.5851 | -2.0697 |
| 2024_2026 | BTCUSDT | C_OPPOSING_CONTEXT_VETO | 1 | 0 | 0 | -1.9040 | -1.7334 |
| 2024_2026 | BTCUSDT | D_SAME_DIRECTION_CONFIRM | 3 | 2 | 1 | -2.1796 | -1.0330 |
| 2024_2026 | ETHUSDT | C_OPPOSING_CONTEXT_VETO | 0 | 0 | 0 | +0.0000 | +0.0000 |
| 2024_2026 | ETHUSDT | D_SAME_DIRECTION_CONFIRM | 1 | 2 | 0 | -0.0166 | +1.1390 |
| 2024_2026 | SOLUSDT | C_OPPOSING_CONTEXT_VETO | 0 | 0 | 0 | +0.0000 | +0.0000 |
| 2024_2026 | SOLUSDT | D_SAME_DIRECTION_CONFIRM | 4 | 3 | 0 | -3.4335 | -1.7365 |

## Constraints and interpretation

- Veto audit counts may exceed excluded *executed* trades because later risk validation and overlapping BOS watches can change the sequence.
- Missed winners/avoided losers are paired by exact original entry UTC and side. Newly available trades are reported separately; changes in opportunity sequence matter.
- B cannot improve PnL by construction; its value is observational data to analyze during genuinely forward tests.
- 2022–2024 vs 2024–2026 is a temporal comparison, not fully unseen information: previous research has inspected parts of both datasets.
- Every baseline is checked against the preceding SHA256 historical studies; mismatch aborts the report.
- This is NOT the $1,000 capped-account historical sizing simulation. $10/$20 risk and max 10x remain prospective account rules.
- Funding, order book, variable execution costs, liquidations, quote timing and live Binance/Coinalyze parity are not verified.
- A tiny trade sample or a zero-trade variant does not prove a profitable edge. Historical trades do not count toward the 50 forward completed trades.

