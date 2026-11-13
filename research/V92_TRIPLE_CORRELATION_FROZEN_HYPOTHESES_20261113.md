# V9.2 triple correlation + ETH failure regime — frozen historical research setup

**Research only; not a forward trading system update.**

## Question and sample

We observed that BTC, ETH and SOL sometimes trend together, but a jointly moving market does not imply equal BOS/retest performance. Test only the same fully completed official Binance USD-M 1H history from 2024-10-01 through 2026-10-01, with 72 distinct monthly ZIPs verified against SHA256. **Selection risk:** we have already examined the ETH losing trades, so any apparent historical improvement is exploratory and must not be promoted without independent forward evidence.

At each retest that is confirmed at 1H close, calculate from the latest *already completed* 4H bars only:

- 30-day (180 closed 4H log-return) Pearson correlations: BTC/ETH, BTC/SOL, ETH/SOL. Strong triple correlation only if **all three pairs >=+0.65**.
- Each asset's 4H regime, by latest closed 4H close vs its EMA20 and EMA50. Require bullish/bearish alignment in the direction of the already qualified retest.
- Relative ETH/BTC 4H volatility = (ETH ATR14/ETH close)/(BTC ATR14/BTC close). Low-ETH-volatility hypothesis: **<=1.50**.
- No standalone new entry from a correlated candle. Only gate *already qualified* 4H-max BOS/retests with the original V7 BOS quality. The SOL strict Star/Harami + prior20 sweep veto remains in place.

## Frozen experimental arms

**BTC:** V9.2 selected baseline, all-pairs correlation>=0.65, all-pairs correlation>=0.65 & all three 4H regimes aligned, BTC/ETH 4H regimes aligned.

**ETH:** V9.2 baseline (original V9.1 4h BOS/retest, ETH candles observational only), all-pairs correlation>=0.65, all-pairs correlation>=0.65 & all three 4H regimes aligned, BTC/ETH pair correlation>=0.65 with BTC 4H regime aligned, ETH 4H normalized ATR<=1.5x BTC, BTC/ETH 4H regime agreement plus low normalized ETH ATR.

**SOL:** V9.2 selected strict reversal-veto baseline, all-pairs correlation>=0.65, all-pairs correlation>=0.65 & all three 4H regimes aligned, BTC/SOL 4H regimes aligned.

For EVERY qualifying original reference trade, store the three correlations, 4H regimes and relative ETH/BTC ATR as-of its retest close, labeled with the original net R and exit reason. Never use a candle closing after that retest.

## Required parity and validity

BTC baseline must equal 5 trades, +4.101040 R at 9bps/side, +2.814628 R at 25bps/side stress.
ETH baseline must equal 6 trades, -2.008289 R at 9bps/side, -4.108804 R at 25bps/side.
SOL baseline must equal 8 trades, +4.260655 R at 9bps/side, +2.409915 R at 25bps/side.

Include zero-trade models explicitly as **no evidence**, not as profitable variants. Stress fees and slippage are constant assumptions, not actual fills. No funding, actual orderbook impact or liquidation. No historical trade is forwarded into the independent 1,000 USDT risk-capped ledger; V7/production are unmodified. On observed overlap, correlated trades may have additional portfolio risk even if each trade's isolated Net R improves.

Source code: `v92_three_asset_correlation_study.py`.
