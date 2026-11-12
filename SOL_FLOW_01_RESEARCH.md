# SOL-FLOW-01 — BTC/SOL project SOL research-only 1H taker ablation

**Status: code + synthetic integrity tests only. Historical return figures have NOT been generated or validated.**
**Main/production, notifications, broker orders, V7/V9.1 and V9.2 code: unchanged.**

Created 2026-11-12 on independent research branch `research/sol-flow-01-20261112`.

## Question
Does pre-existing Binance USD-M 1H kline taker-buy volume and trade-count information improve SOL V9.1's **net costed paper expectancy**, rather than merely next-4H directional accuracy?

## Frozen test
- Market: Binance USD-M **SOLUSDT** perpetual, historical 2024-10-01 through 2026-09-30 inclusive.
- Source: `download_binance_um_history.py` generated **checksum-verified** paired BTC+SOL archive, 1H/4H/Daily, with retained `qv,tbv,tbq,trades`. Must include `source_manifest.json`.
- All five arms: identical original `backtest_retest_long_v4.replay_pair` engine, original V7 BOS gate, V9.1 **4-hour retest expiry**, next 1H open entry and stop-first OHLCV collision resolution.
- Only *completed* retest 1H and preceding 20H available to flow gate. 4H rolling taker CVD is a **candle approximation**, NOT tick delta or an order-book observable.
- A — `V91_UNFILTERED_CONTROL`
- B — 1H signed taker-buy share agrees with trade side (strictly >50% or <50%; ties fail).
- C — sum of signed taker volume over last 4 completed 1H bars agrees with side.
- D — B + C + retest 1H volume / prior20 mean volume >=1.
- E — D + mean base units per trade on retest 1H >= previous20 pooled mean.
- 9bps each side: baseline costs are already subtracted by original replay; 25bps each side: subtract incremental 32bps round-trip in price-risk units.
- Report completed net-R, win rate, max sequential R drawdown, profit factor, veto reasons, watches, rejected BOS and unresolved positions separately. No magic '75% win chance'.
- Results are exploratory because historical data and other candidate configurations were previously examined. Require *new* prospective sealed paper events before promotion.
- Source manifest and every individual 1H field must be present, contiguous and valid; 4H and Daily aggregate OHLCV must match **this exact 1H stream**.
- Optional external V9.1 baseline reference must reproduce original V9.1 MAX4H trade count, wins and total net-R within publication rounding.
- No live orders, new alerts, settings edits, auto-promotions or new historical 'fills'.

## Reproduce on a runner with Binance download access

```bash
python download_binance_um_history.py --start 2024-10 --end 2026-09 \
  --output-dir binance_history
python -m unittest discover -s tests -p 'test_sol_flow_01.py' -v
python sol_flow_01.py \
  --hour binance_history/history_1hour.json \
  --four binance_history/history_4hour.json \
  --daily binance_history/history_daily.json \
  --manifest binance_history/source_manifest.json \
  --output forward/sol_flow_01/latest.json
```

For external parity, append `--v91-reference /path/to/v91_full_replay_reference.json`. Do not describe a completed historical backtest until that command has actually succeeded on the complete source files and the output has been audited.

## Current verification
- Nine synthetic unit tests passed locally on authoring session.
- Historical archive not available in that local session; **no backtest was run**.
- No external full V9.1 parity result claimed.
- No new benchmark or performance improvement claimed.
