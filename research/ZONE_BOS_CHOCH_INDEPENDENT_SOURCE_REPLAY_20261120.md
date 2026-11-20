# ATLAS — Independent BOS/CHoCH Source Replay (20 November 2026)

**RESEARCH ONLY.** Does not represent live trades, portfolio equity, confirmed user notifications, filtered V7 watches or production actions.

## Source audit

Historical period: 8–20 November 2026, BTC/SOL 1H.

- Indexed **333 market-data commits** and **333 structure-data commits**; archived **317 consecutive source-pinned 1H BTC/SOL hourly snapshots** from Nov 7 at 16:00 UTC to Nov 20 at 20:00 UTC. First 162 and final 155 snapshots independently checked for no missing/duplicate hours, matching BTC/SOL timestamps and valid publication chronology.
- Scanned 13 daily evening and 13 additional morning historical structure snapshots. Combined sources yielded **39 distinct 1H structural events: 21 BOS (14 BTC, 7 SOL) plus 18 CHoCH (6 BTC, 12 SOL)**. Morning snapshots yielded no extra previously missed events.
- All **39/39** historical event candles were checked against source-pinned market and structure records present by the hypothetical event-close + 5 minute cutoff. Source event and OHLC closed-candle timestamps matched; zero source mismatches.
- **Chronology correction:** source structure event's at field is **the 1H candle start**; event close is one hour later. The recorded Git commit time must precede the research cutoff. This is **not** verification of delivery of a push notification.
- Candidate OB/open FVG/confirmed equal-high or equal-low had to be known at cutoff, on fully closed source timeframe data, ahead of signal-close price, and unvisited by the signal candle wick. No future levels were retroactively credited.

## Archived reproducibility inputs

| Path within isolated research branch | Contents |
|---|---|
| research/data/atlas_source_commit_index_20261108_20.json | all 333 market and 333 structure SHA/timestamp pairs |
| research/data/atlas_bos_choch_event_inventory_20261108_20.json | 39 events, exact event close UTC and five-minute as-of source refs |
| research/data/atlas_asof_events_part_01.json to _05.json | 39 historical full market candle and structural feature sets |
| research/data/atlas_hourly_ohlcv_part_01.json to _18.json | source-SHA-pinned contiguous 317 BTC/SOL hourly candle snapshots |
| research/data/atlas_replayed_12h_part_01.json and _02.json | newly recomputed 39 case diagnostics and paper exit models |

## Frozen historical replay assumptions

Event-close after 1H candle. ATR14 = simple arithmetic mean of 14 true ranges (15 consecutive 1H candles ending at event). First eligible ahead-of-price source-known opposite-side OB, open FVG or chart equal-high/low pivot. Exclude features touched by signal bar wick. For reaction: at least 0.5 ATR opposite-direction **closed** 1H price relative to nearest-zone entry edge, in one of the next 3 candles *after* first-touch candle. Later far-edge close breach counted separately.

Hypothetical trade: skip zone method if NO_ZONE or first waiting candle already visited zone or entry crossed target. Both strategies enter at **second following 1H bar OPEN**, after one waiting full hour. Stop at 1 ATR, TP at eligible nearest zone edge or fixed 2 ATR; stop-first when OHLC touches both; final close exit within 12 following hourly candles. Assumed 0.12% round-trip cost normalized to R. R is risk-normalized **hypothetical price outcome, not portfolio return**. Fees, funding, real liquidity, slippage variation, correlated exposure and broker fills unverified.

**Right-censored:** SOL SHORT BOS of Nov 20 13:00 UTC has only 7 hours; BTC SHORT BOS of Nov 20 16:00 UTC only 4 hours. Neither given a full 12h outcome. Completed sample therefore **37 cases: 19 BOS + 18 CHoCH**.

## Independently reproduced BOS (19 complete)

| Metric | Source-replayed zone model | Fixed 2 ATR |
|---|---:|---:|
| Full 12h events | 19 | 19 |
| Net R/event, including zero deployed R on SKIPs | **-0.255548** | **-0.201576** |
| Zone method pre-entry SKIPs | 3 | 0 |
| First zone visited | 10/19 | — |
| Qualified reversal after visit | 3/10 | — |
| Subsequent far-edge breach | 5/10 | — |

Each independently replayed BOS case agrees with the previous widened audit's event-level 3-decimal result within rounding tolerance. This **confirms the original negative opportunity-set results**, not a zone-method advantage.

## Newly expanded CHoCH (18 complete)

| Measure | Finding |
|---|---:|
| Full 12h CHoCH events | 18 |
| Candidate eligible source-known zone | 17/18 |
| First zone visited within 12h | 11/18 |
| Qualified reversal after first visit | 4/11 |
| Subsequent far-edge closing breach | 4/11 |
| Zone non-entries | 5/18: 4 waiting-hour touches and 1 NO_ZONE |
| Zone-method net R/event (SKIPs = 0 allocated) | **+0.039964** |
| Fixed 2 ATR net R/event | **+0.022379** |

The SOL bearish CHoCH at **2026-11-16 09:00 UTC** retained **NO_ZONE** on source data; any later fall is not an invented target. The +0.017585 R/event difference between the two hypothetical CHoCH methods is **far too small and sample-dependent to infer statistically significant advantage**.

### Separate asset/side/event aggregates

| Event | Asset | Side | n completed | Zone mean R | Fixed mean R |
|---|---|---|---:|---:|---:|
| BOS | BTC | LONG | 2 | -0.8367 | -1.4390 |
| BOS | BTC | SHORT | 11 | -0.1481 | -0.0767 |
| BOS | SOL | LONG | 3 | -0.4613 | -0.9175 |
| BOS | SOL | SHORT | 3 | -0.0565 | +0.8815 |
| CHoCH | BTC | LONG | 3 | +0.5622 | +0.6638 |
| CHoCH | BTC | SHORT | 3 | -0.5315 | +0.1784 |
| CHoCH | SOL | LONG | 6 | -0.3340 | -0.6243 |
| CHoCH | SOL | SHORT | 6 | +0.4385 | +0.2703 |

**Important:** historical event observations overlap heavily and cannot be combined as portfolio trades, independent successes or stable profits. No held-out independent sample has validated these differences.

## Conclusions and research gates

The earlier 19-case BOS results have been corroborated with per-hour historic Git-published price data, without changing them. An additional 18 CHoCH cases are now separately assessed. This is a **historical source-audit and outcome replay**, not proof of reliable market prediction or superior exits. Chart OB/FVG/liquidity are OHLCV heuristics, not verified resting institutional orders.

**Next:** pre-register Zone Quality Intelligence V1 weights without tuning to these 37 outcomes; test on a separate chronological holdout and then forward-only paper observation. Preserve BTC/SOL LONG/SHORT stratification, censored events, NO_ZONE, non-entries and losses. Perform no new real orders, changes to paper portfolios, V7/V9, GitHub Actions or alert automations. Keep main entirely unchanged; research branch only.
