# SOL V8.5 — Trend-regime LONG+SHORT with abstention, wide zones and 1H confirmation

**Experimental historical research only**; not a trading system approval.
**2021–22** older-unseen-regime robustness; not time-forward; **2023–Sep2026** previously inspected development periods.

## Sources and validation
- **67** checksum-verified complete Binance USD-M SOLUSDT monthly 1H archives. 2022 incomplete months listed in JSON and entirely excluded, never stitched or padded.
- Daily + 4H SMA100 and SMA200 for regime; 4H RSI14, Daily RSI14; prior-day classic pivot.
- Broad Daily 28-day 8.5% width support/supply zone, Fib 38.2–61.8, Wyckoff SOS/SOW OHLCV proxy, 1H liquidity sweep, 4H volume.
- Either direction considered; mixed SMA regimes yield ABSTAIN. Next four closed 1H candles must provide BOS or sweep; next 1H open paper entry.
- Direction judged 24h after 1H confirmation. 24h global event cooldown fixed before looking at outcomes.
- Stop wick 1H+0.03 ATR, risk <= $0.50 planned; 10x notional; TP2R or 24h, worst-case stop first, 9bps/side fees/slippage.
- 4H chart structure BOS/FVG candidate proxies stored but not given votes; no institutionally verified orderbook or actual Wyckoff phase.

| Test | 2021–22 | 2023–24 | 2025–Sep26 | All |
|---|---:|---:|---:|---:|
| A_RegimePlus1H | 60/99 (60.61%) | 124/247 (50.2%) | 76/141 (53.9%) | 260/487 (53.39%) |
| B_AtLeast6of10 | 30/47 (63.83%) | 61/120 (50.83%) | 34/64 (53.12%) | 125/231 (54.11%) |
| C_AtLeast8of10 | 0/2 (0.0%) | 7/9 (77.78%) | 3/4 (75.0%) | 10/15 (66.67%) |
| D_Score6WithPastSweep | 18/27 (66.67%) | 32/63 (50.79%) | 17/26 (65.38%) | 67/116 (57.76%) |
| E_SMA_RSI_And6 | 22/36 (61.11%) | 43/87 (49.43%) | 18/41 (43.9%) | 83/164 (50.61%) |
| F_WideBox_Fib_Pivot | 6/10 (60.0%) | 11/22 (50.0%) | 16/28 (57.14%) | 33/60 (55.0%) |

## Cautions
- Historical observations are not live-forward; 2021–22 was selected as additional unseen market regime, but backward in calendar time.
- Technical proxies use OHLCV; true Wyckoff manipulation, stops and actual order-book liquidity cannot be validated.
- 75% goal never used to change filter thresholds after results.
- Six different predefined variants; selecting best in retrospect would bias accuracy.
- No funding, gaps in exchange API live execution, latency or liquidation model beyond OHLCV and rough fee/slippage.
- Score result is directional 24h hit, not probability that 10x futures trade would win.
- No production BTC/ETH/SOL branch modifications and no real orders.
