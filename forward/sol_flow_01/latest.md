# SOL-FLOW-01 historical taker-flow ablation

**Exploratory historical paper replay only. Not live PnL, not independent forward evidence, no orders or alerts.**

Period: 2024-10-01T00:00:00Z to 2026-10-01T00:00:00Z (exclusive).
Source: Binance official USD-M 1H kline (full taker columns); checksum-verified monthly files: 48.
V9.1 control parity: True.

| Arm | Trades | Wins | Win rate | Net R (9 bps/side) | Net R (25 bps/side) | PF | Max DD R | Retest vetoes |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| V91_UNFILTERED_CONTROL | 9 | 5 | 55.56% | 3.1159 | 1.0080 | 1.70055 | 2.2718 | 0 |
| FLOW_1H_TAKER_AGREES | 6 | 3 | 50.0% | 0.3924 | -0.7927 | 1.11687 | 2.2718 | 6 |
| FLOW_4H_CVD_AGREES | 6 | 3 | 50.0% | 0.6164 | -0.6019 | 1.18356 | 2.2718 | 5 |
| FLOW_1H_4H_RVOL | 1 | 1 | 100.0% | 1.3259 | 1.2154 | — | 0.0000 | 13 |
| FLOW_1H_4H_RVOL_SIZE | 1 | 1 | 100.0% | 1.3259 | 1.2154 | — | 0.0000 | 13 |

## Interpretation guardrails

- No funding, real spread, real fills or liquidation effects
- Repeated past comparisons; do not treat best arm as new validated edge
- No trading fees tier verification or ex-ante slippage verification
- The best arm is exploratory only: these historical periods and candidate filters have already been inspected.
- No live deployment, alert, broker order, paper account mutation, or production strategy change.
- V9.1 control was checked against the previously published SOL historical reference before interpreting any filter delta.
