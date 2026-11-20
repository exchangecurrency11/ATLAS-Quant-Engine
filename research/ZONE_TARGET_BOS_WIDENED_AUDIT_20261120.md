# ATLAS BTC/SOL — widened 1H BOS zone comparison (20 Nov 2026)

**Scope:** 2026-11-08 00:00 UTC through 2026-11-20 20:00 UTC, all identified **1H BOS** for BTC/SOL in the contemporaneous market-structure snapshots. **21 BOS**: 19 have complete next-12h Coinalyze/GitHub recorded candles; 2 late signals are right-censored and **not** given 12h outcomes. Of the full sample: **13 BTC**, **6 SOL**; **5 LONG**, **14 SHORT**. This is a widened **retrospective structural-event exercise**, *not* a prospective test of filtered V7 signals, executable fills, or the actual V7 exit policy. CHoCH must not be pooled with these BOS counts.

## Frozen comparison rules (applied symmetrically to both assets and directions)

- As-of time: hypothetical **event-close + five minutes**; contemporaneously published Git SHA of \`market_structure_data.json\`, approximately four minutes after the last 1H close. Never use later model/snapshot state for a candidate.
- Eligible zone: nearest **ahead-of-close**, **signal-candle-untouched** opposite-side candidate OB, open FVG or chart equal-low/high proxy, from fully closed 1H/4H/Daily data. Require OB confirmation, FVG third-bar close, equal-high/low pivot confirmation; already-invalidated/filled zones excluded. For a SHORT, search lower bullish demand; LONG searches higher bearish supply. All are heuristic OHLCV constructs, **not** verified institutional orders.
- Twelve closed 1H bars **after** the event (no hidden longer horizon). Modelled trade entry only at the **second bar OPEN** (one full waiting hour), so the market data publisher's four-minute posting delay is respected. This is still *not* proof that the fill was executable.
- Model A: full take profit at first eligible zone edge; if zone was visited during the waiting hour, skip instead of claiming profit already taken; no zone = **NO_ZONE_SKIP**. Model B: full take profit at fixed **2× ATR14(1H)**. Both: stop 1× ATR14, same initial sizing, same 12h event cutoff, time-close if no barrier hit, **stop-first** when OHLC hits both barrier levels in the same bar.
- **Illustrative friction 0.12% round trip** (fees + slippage); no funding, real order-book spread, liquidation, collateral or portfolio exposure included. \`R\` = net hypothetical directional price outcome / signal-hour 1H ATR. An unused zone event scores **0 deployed R** for the all-opportunities summary, but is **NOT** a winning trade. Overlapping opportunities can imply simultaneous positions and are correlated; never add R values as actual portfolio equity returns.
- ATR at missing V7 observations (BTC Nov 16 06, BTC Nov 17 17) reconstructed from 15 preceding per-hour Git-committed OHLC candles using 14 true ranges; their source BOS was independently confirmed in 1H \`market_structure_data.json\`.

## Results: 19 completed BOS opportunities, including losses and skipped zones

| Metric | Nearest preexisting zone | Fixed 2-ATR |
|---|---:|---:|
| Eligible structural opportunities | 19 | 19 |
| Hypothetical trades | 16 | 19 |
| Skipped opportunities | 3 (pre-entry zone touch) | 0 |
| Positive hypothetical trades | 5 | 6 |
| Mean net R **per all 19 events**, skip = 0 | **−0.2556 R** | **−0.2016 R** |
| Mean net R, **same 16 zone-tradable opportunities only** | −0.3035 R | −0.4010 R |

The conditional 16-case result is **selection-biased** because the zone model can skip events; the 19-case result is the apples-to-apples **opportunity-set** comparison under these artificial assumptions. There is **no robust evidence of a zone-based exit advantage**; both methods average negative outcomes in this small, dependent sample.

### Zone reaction diagnostic

- A pre-identified, valid first target exists in **all 19 completed BOS examples** from these retained snapshots. This does **not** mean all potential historical events have such zones.
- **10/19** earliest candidate zones were touched within the following 12h (visit, not guaranteed stop/reversal).
- **3/10** visited zones had a predefined **≥0.5 ATR opposing reaction on one of the next three closed 1H candles**.
- **5/10** visited zones subsequently had at least one 1H CLOSE beyond their far edge within the 12h horizon. Reaction and later breakdown can both be true.
- **3/19** zone plans were skipped because price touched the zone during the waiting hour before the earliest modelled full-hour entry.

Separate mean net R per event; extremely small subgroup sizes:

| Subgroup | n | Zone | Fixed 2-ATR |
|---|---:|---:|---:|
| BTC LONG | 2 | −0.8367 | −1.4390 |
| BTC SHORT | 11 | −0.1481 | −0.0767 |
| SOL LONG | 3 | −0.4613 | −0.9175 |
| SOL SHORT | 3 | −0.0565 | +0.8815 |

### All event outcomes (dates and times UTC, R rounded to 3 decimals)

\`SKIP\` = zone plan had no hypothetical entry; \`CENSORED\` = no 12h result. Values in rows are not actual trades.

| Event close UTC | Signal | First eligible zone | Reached within following 12h | Zone net R | Fixed net R |
|---|---|---|---|---:|---:|
| 11-08 15:00 | BTC LONG 76,007 | 76,125.70 liquidity | No | −1.673 | −1.673 |
| 11-08 22:00 | BTC SHORT 74,097.40 | 70,450–72,992.40 FVG | No | −1.268 | −1.268 |
| 11-10 11:00 | BTC SHORT 74,200.30 | 70,450–72,992.40 FVG | Yes | −1.236 | −1.236 |
| 11-10 11:00 | SOL SHORT 84.43 | 77.39–83.97 FVG | Yes | +0.936 | +1.844 |
| 11-11 17:00 | BTC LONG 74,224.70 | 74,537.40–74,805.40 OB | Yes | SKIP | −1.205 |
| 11-13 01:00 | BTC SHORT 71,096.30 | 65,057.90–68,882.10 FVG | Yes | +3.557 | +1.845 |
| 11-13 03:00 | SOL SHORT 80.18 | 76.20–76.59 FVG | No | −1.106 | −1.106 |
| 11-14 03:00 | BTC SHORT 67,654.50 | 63,370–63,979.20 FVG | No | −1.131 | −1.131 |
| 11-14 15:00 | BTC SHORT 65,889.70 | 63,370–63,979.20 FVG | Yes | +2.840 | +1.865 |
| 11-14 15:00 | SOL SHORT 74.05 | 73.34 equal-lows | Yes | SKIP | +1.907 |
| 11-14 21:00 | BTC SHORT **64,738** | 63,370–63,979.20 FVG | Yes | SKIP | +1.884 |
| 11-16 06:00 | BTC SHORT 64,444.70 | 62,307–63,749.90 OB | No | −1.146 | −1.146 |
| 11-17 09:00 | BTC SHORT 64,304.60 | 62,307–63,749.90 OB | Yes | −1.189 | −1.189 |
| 11-17 12:00 | SOL LONG 73.46 | 73.91–75.02 FVG | Yes | +0.248 | −1.121 |
| 11-17 17:00 | BTC SHORT 63,714.90 | 62,876–63,053.90 OB | No | −1.131 | −1.131 |
| 11-18 00:00 | SOL LONG 75.15 | 76.10–77.13 FVG | No | −0.541 | −0.541 |
| 11-18 13:00 | BTC SHORT 64,056.30 | 62,307–63,749.90 OB | Yes | +0.216 | +1.804 |
| 11-18 23:00 | BTC SHORT 62,220 | 62,017.40 equal-lows | No | −1.141 | −1.141 |
| 11-19 04:00 | SOL LONG 74.20 | 75.67–75.92 OB | No | −1.091 | −1.091 |
| 11-20 13:00 | SOL SHORT 71.06 | **NO_ZONE** in retained records | 12h unavailable | CENSORED | CENSORED |
| 11-20 16:00 | BTC SHORT 59,445.10 | 57,894.30 equal-lows proxy | 12h unavailable | CENSORED | CENSORED |

**Crucial original BTC alert chronology:** The BTC bearish BOS at **$64,738** occurred at the **2026-11-14 21:00 UTC close (15-Nov 00:00 TSİ)**. The source-pinned 14-Nov structure snapshot \`085c7d70147a0493bffc8a53de6109e08907101e\` supplies its actual pre-existing zone; the later 15-Nov 15:00 UTC reconstruction should not be credited as early evidence. Exact external notification receipt/delivery time is **still not independently proven**. V4 reported a watch; V7 filtered variants did not.

## NO_ZONE control: an additional complete 12h CHoCH (not part of BOS denominator)

The 1H **SOL bearish CHoCH, 2026-11-16 09:00 UTC**, close **$70.82**, from time-pinned \`market_structure_data.json\` commit \`6f6617958358d283bf52d7b229d7b0f0a204036f\`, had **zero qualifying retained lower-price bullish OB/open-FVG/equal-low candidates** after as-of, confirmation and signal-candle-wick guards. This is a genuine research **NO_ZONE** result (not a claim that no support existed anywhere). Its 12 following hourly market commits were inspected: zone model **SKIP / no trade**, fixed 2-ATR model **STOP / −1.0938 net R** using the same illustrative delayed-entry, 1 ATR stop and 0.12% friction rules. This control belongs to the **CHoCH group** and is **NOT** pooled with the 19 BOS mean R. Four additional recent CHoCH source records inspected had qualifying opposite-side regions; a separate full CHoCH backtest remains necessary.

## Interpretation, limitations, and next research gates

1. The pilot near-zone target is not a reliable take-profit replacement. The strongest improvement candidates are **zone confluence/quality, delayed entry and exit confirmation**, not enabling aggressive profit-taking just because a chart label exists.
2. Do not optimize a score on these same 19 outcomes and then claim backtest validity. Explicitly freeze any score and the benchmark rules before a **disjoint out-of-sample period** and subsequent forward paper observation. BTC/SOL and LONG/SHORT need stratified minimum sample sizes.
3. These signals are **1H BOS structural events**; they are not automatically the strict V7-approved watches. Many did not pass strict V7 filters. **No brokerage fills, portfolio equity or V7 actual exit-rule comparison** was established.
4. The 19 events are highly overlapping and trend-correlated. The averages are **descriptive opportunity averages, not causal effects or portfolio return**, and the research deliberately includes no confidence/p-value claim. The five-group CHoCH source audit is also not exhaustive.
5. Exact reproducibility: each event in the accompanying research JSON carries the **full 40-character structure source SHA**, time, side, price, ATR and zone; the every-hour OHLC data used for the case is from per-hour **\`market_data.json\` commits** on the same GitHub repository. Two missing V7 observation hours were reconstructed from 15 timestamped source candles. Additional script and JSON/CSV are delivered in the accompanying conversation files; this report is a compact GitHub research record.
6. Keep **main, V7/V9 production/paper paths, existing notification automations, source collectors, GitHub workflows and real broker operations unchanged**. No deployment recommendation. Existing stabilization windows and user permission gates remain in force.

**Local verification:** 13 standalone audit assertions passed against the enlarged research dataset, including censored-event separation, source SHAs, direction/wick-valid zones, delayed entry, stop-first treatment, and no-zone skip. These are **local validation checks**, not GitHub Actions CI or an independent financial backtest.
