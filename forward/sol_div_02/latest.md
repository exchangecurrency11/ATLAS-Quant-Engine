# SOL-DIV-02 — CVD divergence combinations

**Exploratory historical paper comparison only. No live orders, alerts or production changes.**

Period: 2024-10-01T00:00:00Z to 2026-10-01T00:00:00Z (exclusive).
Source: checksum-verified Binance USD-M monthly 1H klines. Same historical source and BOS/retest engine across all arms.

- V9.2 strict-sweep control parity: verified.
- DIV-01 divergence-only parity: verified.
- Pivot confirmation: 2 left + 2 right closed 1H candles; no future candles.
- BOS/retest: existing engine unchanged; hypothetical entry at next 1H open.
- Liquidity sweep: retest wick beyond prior 20 completed 1H high/low and close back inside.
- Volume increase: retest 1H base volume >= 1.20x preceding 20 completed 1H candle mean.
- All candidate arms retain V9.2 strict-sweep gate.
- No broker orders, alerts, production changes or model promotion.

## Results

| Model | Trades | Wins | Win % | Net R 9 bps/side | Net R 25 bps/side | Profit factor | Max DD R | Δ Net R vs V9.2 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| V9.2 control | 8 | 5 | 62.5% | +4.2607 | +2.4099 | 2.2899 | 1.1271 | 0.0000 |
| CVD divergence + BOS retest | 1 | 1 | 100% | +1.3259 | +1.2155 | N/A (one trade) | 0.0000 | -2.9347 |
| CVD + BOS retest + liquidity sweep | 0 | 0 | N/A | 0.0000 | 0.0000 | N/A | 0.0000 | -4.2607 |
| CVD + BOS retest + volume increase | 1 | 1 | 100% | +1.3259 | +1.2155 | N/A (one trade) | 0.0000 | -2.9347 |
| CVD + BOS + liquidity sweep + volume | 0 | 0 | N/A | 0.0000 | 0.0000 | N/A | 0.0000 | -4.2607 |

## Gate audit

- **CVD + BOS retest:** 13 divergence-eligible retests; 1 confirmed divergence passed; 12 divergence vetoes; 1 final pass.
- **CVD + BOS + liquidity sweep:** 15 divergence-eligible retests; 3 confirmed divergences passed; all 3 failed the added prior-20 sweep/re-entry condition; 3 sweep vetoes; 0 final passes.
- **CVD + BOS + volume:** 13 divergence-eligible retests; 1 confirmed divergence passed; the one retest passed the 1.20x volume threshold; 1 final pass.
- **CVD + BOS + sweep + volume:** 15 divergence-eligible retests; 3 confirmed divergences passed; all 3 failed the sweep/re-entry condition before volume could add a trade; 0 final passes.

The sole divergence trade occurred on 2026-06-03 21:00 UTC and had 1.9197x relative volume. Thus the 1.20x volume condition did not change the divergence-only result.

## Interpretation and limits

1. None of the divergence combinations improved on the V9.2 control in this historical sample.
2. A 100% win rate here means one winning trade, not a reliable estimate of future win probability.
3. The prior-20 liquidity sweep condition was too restrictive for the three divergence-qualified retests observed in this run.
4. Volume confirmation did not add discrimination: the sole divergence-qualified trade already exceeded the threshold.
5. The 2024–2026 historical period has been inspected previously; this is not independent prospective evidence.
6. CVD is Binance 1H kline taker-buy minus taker-sell base volume, not tick-level order flow.
7. Funding, actual fills, spread, liquidation and account-specific fees are not fully modeled.
8. No arm is promoted. Keep V9.2 unchanged pending sealed forward paper observations and a larger sample.
