# SOL-FLOW-02 — V9.2 strict sweep + taker/CVD

**Exploratory historical paper replay only. No live orders, alerts, production changes or independent prospective evidence.**

Period: 2024-10-01T00:00:00Z to 2026-10-01T00:00:00Z (exclusive).
V9.2 strict-sweep control parity: True.
Every arm uses the same V9.2 selected Star/confirmed-Harami prior-20 sweep/re-entry veto before its flow filter.

| Arm | Trades | Wins | Win % | Net R 9 bps/side | Net R 25 bps/side | PF | Max DD R | Delta vs V9.2 | Flow veto |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| V92_STRICT_SWEEP_CONTROL | 8 | 5 | 62.5 | 4.2607 | 2.4099 | 2.28988 | 1.1271 | +0.0000 | 0 |
| V92_PLUS_1H_TAKER | 5 | 3 | 60.0 | 1.5372 | 0.6093 | 1.69449 | 1.1271 | -2.7235 | 6 |
| V92_PLUS_4H_CVD | 5 | 3 | 60.0 | 1.7611 | 0.8000 | 1.79567 | 1.1271 | -2.4996 | 5 |
| V92_PLUS_TAKER_AND_CVD | 1 | 1 | 100.0 | 1.3259 | 1.2154 | — | 0.0000 | -2.9347 | 12 |
| V92_PLUS_TAKER_CVD_RVOL | 1 | 1 | 100.0 | 1.3259 | 1.2154 | — | 0.0000 | -2.9347 | 12 |

## Audit

- V9.2 control must reproduce 8 trades, 5 wins, +4.260655 net R at 9 bps/side and +2.409915 at 25 bps/side.
- 1H taker buy share and 4H CVD proxy use only completed 1H candles.
- Flow gates are applied only after the original V9.2 selected reversal gate passes.
- CVD is a candle-volume proxy, not tick-level delta or order-book flow.
- All dates were previously examined; any best arm is exploratory and requires new prospective paper events.
- Do not promote a filter merely because it raises win rate while collapsing trade count.
- Funding, actual fills, spread, liquidation and account-specific fees are not fully modeled.
