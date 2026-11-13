# BTC / ETH V9.2 historical failure forensics — hypotheses frozen 2026-11-13

**RESEARCH ONLY. No trading, no broker orders, no V7/V9.2 edits.**

The baseline was inspected prior to this research; therefore every result below is **selection-biased exploratory research**, not an independent holdout or performance forecast. All candidate rules were fixed in code in this branch before the new replay output.

## Fixed reference facts (2024-10-01 through 2026-10-01 UTC)

| Symbol | V9.1 retest <=4h | Wins | 9bps net R | 25bps net R |
|---|---:|---:|---:|---:|
| BTC | 5 trades | 3 | +4.101040 | +2.814628 |
| ETH | 6 trades | 2 | -2.008289 | -4.108804 |

BTC original 6h replay: 9 trades, +3.663602 R, stress +1.328976 R.
ETH original 6h replay: 7 trades, -2.447965 R, stress -4.737533 R.

The original 4h subsets consist of BTC 1 bullish and 4 bearish trades; ETH 3 bullish and 3 bearish. BTC direction breakdown approximately +5.330965 R short, -1.229924 R long; ETH +0.100865 R short, -2.109154 R long. **These are post-hoc diagnostics, NOT a defensible license to automatically disable long signals.**

BTC separate earlier period 2022-10 through 2024-09 generated 10 retest trades, -4.265784 R baseline, -7.701252 R under 25bps/side stress. A single 2024-2026 profitable BTC window is therefore not robust across regimes.

## Predeclared historical replay variants

Every variant uses the *same unchanged original* BOS quality and retest replay, stop and TP, chronological next-open fill assumption and pessimistic intrabar stop-first execution. BTC and ETH use the exact same 1H monthly Binance USD-M historical source as the old baseline. No crossover from later market observations.

BTC: unchanged 4h baseline, original 6h retest window, short-only retest confirmation, retest-close daily EMA20/50 trend alignment, 1H ATR14 as % price >=0.5%, and retest-close proposed stop distance <=2.0 ATR14.

ETH: unchanged 4h baseline, original 6h retest window, short-only retest confirmation, retest-close proposed stop distance <=2.0 ATR14, retest body >=0.2 ATR14, retest volume vs prior 20 hourly candles >=1.2x, and short-only combined with <=2.0 ATR14 stop.

The stop-distance experiments are admission vetoes; they **do not modify any existing stop price**. They may reduce opportunities and could give misleading wins with <=6 total original ETH trades. Regime classifiers use only already-closed candles at the retest close.

## Required research validation

- 48 complete verified official Binance BTC/ETH USD-M monthly archives, SHA256 checked by exchange source.
- Four fixed baseline references (BTC and ETH, 4h and 6h) must match original trade count, 9bps R, 25bps stress R.
- Every selected model reports trade count, wins, net R, stressed R, profit factor, max *realized* drawdown, retest rejections and individual trade inputs (entry/stop/ATR/volume).
- Negative, zero-trade and failed tests remain visible; no arbitrary rule is chosen for production from this data.
- Forward 1,000-USDT 10/20 risk-capped paper account remains separate; historical trades never satisfy the prospective 50-trade gate.

Source code: `v92_btc_eth_forensics_20261113.py` and `tests/test_v92_btc_eth_forensics_20261113.py`. New runner `.github/workflows/v92-btc-eth-forensics-20261113.yml` on main is research-only and writes exclusively to this branch.
