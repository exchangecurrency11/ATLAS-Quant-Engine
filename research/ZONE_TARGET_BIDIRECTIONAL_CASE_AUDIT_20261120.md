# ATLAS LONG + SHORT — Seven historical zone case audit (20 Nov 2026)

**Research only.** This is not a full-sample backtest, successful live trade, brokerage fill, profit claim, confirmed alert-delivery replay, or promotion proposal.

## Critical chronology correction: the $64,738 BTC bearish BOS

The **exact** recorded BTC $64,738 close and bearish BOS occurred on **2026-11-14 21:00 UTC = 2026-11-15 00:00 TSİ** (not 2026-11-15 15:00 UTC). The bearish BOS broke **$64,969**; 1H RSI **24.9933**, MACD histogram **−86.3338**, prior-hour volume change **+294.2262%**. The V7 source snapshot `forward/snapshots/2026-11-14T21-00Z.json` was observed 21:31:55 UTC. Its **V4 baseline** detected a fresh watch but neither **V7_signal_filter** nor **V7_signal_plus_retest** did. Do not confuse the separately configured ChatGPT early-warning automation with V7's sealed paper strategy, or assert the precise delivered-alert time without an independent notification receipt.

The truly contemporaneous files were published much earlier:
- `market_data.json`, commit **81c18a112d785f837ccccb34520e83c7b5276871**, **2026-11-14 21:04:23 UTC**, BTC 1H O/H/L/C **65,694.4 / 65,857.3 / 64,469.5 / 64,738**.
- `market_structure_data.json`, commit **085c7d70147a0493bffc8a53de6109e08907101e**, **2026-11-14 21:04:36 UTC**, BTC 1H ended 21:00, 4H ended 20:00, Daily ended 00:00 UTC.
- The source-published-at **21:05 UTC** is therefore an **illustrative research cutoff**, not a user-notification timestamp. The previous 15-Nov 15:05 research slice is superseded for diagnosing the BTC $64,738 early warning.

**Known below BTC at that actual event:** Daily bullish FVG **$63,370–63,979.20** (1.17% away to upper edge), candidate Daily bullish OBs **$62,307–63,749.90** (1.53%) and **$62,876–63,053.90** (2.60%), confirmed Daily equal-low proxies **$62,356.50**, **$62,017.40**, **$57,894.30**. The later-reported **$58,700–59,000** band was **not present as a directly identified candidate Demand Zone** in these retained features. The $57,894.30 equal-low proxy is **not** the same range. The 1H bullish FVG $63,446.60–64,719 found in **15-Nov 15:05** records was **not present at the actual 14-Nov 21:05 cutoff** and must never be retroactively credited.

**Observed outcome only:** In the 2026-11-15 01:00 UTC BTC candle, low **$63,375.90** entered the earlier Daily FVG; the 02:00 UTC candle low **$61,956.30** went through that FVG and both candidate OB body ranges. Visiting a zone **does not** imply it gave effective support; an exit comparison needs a separately specified paper trade and costs.

## Bidirectional BTC/SOL selected event matrix

All cases use closed-candle event prices that **exactly match** their contemporaneously published `market_data.json` commits; 1H/4H/Daily known-at filters use the corresponding `market_structure_data.json` historical commit. Each cutoff below is approximately **5 minutes after closed 1H** solely for reproducible research; not a claim about the alert being delivered then.

| Asset / directional structure event (UTC close) | Close | Contemporaneous structure commit | Source-valid first levels ahead | Later evidence and strict classification |
|---|---:|---|---|---|
| BTC **LONG** bullish BOS, **Nov 08 15:00** | $76,007 | `ced7b11db75ac0f5f9ec9b4d4461e2356de0aa8f` (15:04:41) | Equal-high proxy **$76,125.70** (+0.16%); also $76,154.25 (+0.19%) | **Not visited in the next seven closed 1H candles** (16:00–22:00): maximum high $76,070; by 22:00 close $74,097.40. A structural BOS, **not** a V7 filtered watch or proven LONG entry. |
| BTC **SHORT** bearish BOS, **Nov 13 01:00** | $71,096.30 | `eae2fa0d908645527978c7c86010468c5f21112d` (01:04:37) | Daily bullish FVG **$65,057.90–68,882.10** | BTC later closed $64,738 on Nov 14 21:00, below the FVG: crossed/visited by then, but exact first-touch time and rejection quality not established. V7 filtered **new watch**, not executable fill. |
| BTC **SHORT** bearish BOS, **Nov 14 21:00** | $64,738 | `085c7d70147a0493bffc8a53de6109e08907101e` (21:04:36) | Daily bullish FVG **$63,370–63,979.20**, Daily bullish OBs **$62,307–63,749.90** and **$62,876–63,053.90** | FVG directly touched in Nov 15 01:00 low $63,375.90, subsequently traversed by Nov 15 02:00 low $61,956.30. V4 watch yes; **V7 filtered watch no**. |
| SOL **SHORT** bearish BOS, **Nov 13 03:00** | $80.18 | `2525571ba5cf360b751e598bc819f0b7986308de` (03:04:39) | Daily bullish FVG **$76.20–76.59**, candidate OB **$74.57–75.31** | Nov 14 15:00 close $74.05 was below both bands: crossed by then. Exact first-touch candle and eventual reaction not established. V7 filtered **new watch**, not proof of a completed trade. |
| SOL **SHORT** bearish BOS, **Nov 14 15:00** | $74.05 | `e0730e3c95f995a060fc645375b332005ddb2d36` (15:04:36) | OB **$72.65–74.00** and equal-low **$73.69** were **already touched by the SIGNAL candle low $73.68**; EXCLUDE as later targets. Next still-ahead equal-low **$73.34**, then candidate OB **$70.47–71.88**. | Nov 15 11:00 low $71.63 confirms later visit below $73.34 and into $70.47–71.88 body. V4 watch yes; V7 filtered watch no. |
| SOL **LONG** bullish BOS, **Nov 17 12:00** | $73.46 | `c5adb9f00d2fde3318b5776c2e3029f6d89ff25c` (12:04:39) | 4H bearish FVG **$73.91–75.02** (+0.61%) | Nov 18 00:00 high $75.74 / close $75.15: **FVG was visited and fully crossed**. Do **not** score as a successful supply-zone rejection. V7 filtered watch no. |
| SOL **SHORT** bearish BOS, **Nov 20 13:00** | $71.06 | `35a1b15e4bd5de2b63677da57b1f9836103c057c` (13:04:39) | **No qualifying below-price bullish OB/FVG/confirmed equal-low proxy among retained source features.** | Nov 20 18:00 close $69.24 is lower, but the research MUST return **NO_ZONE**, not invent a target after the fall. V7 filtered **new watch**, not proof of an entry. |

Contemporaneous 1H market-data commits, in matrix order:
1. BTC LONG Nov 08: `674737e6aebb53951555c846538094510b109b0f` (15:04:26 UTC).
2. BTC SHORT Nov 13: `8171c33075f03b8ed9fc9327570ebca630856163` (01:04:24 UTC).
3. BTC SHORT Nov 14: `81c18a112d785f837ccccb34520e83c7b5276871` (21:04:23 UTC).
4. SOL SHORT Nov 13: `e31083c472aaee581c101917589e7d49e75eaf46` (03:04:25 UTC).
5. SOL SHORT Nov 14: `22991a816461cab90ac579e187275de7804bd694` (15:04:25 UTC).
6. SOL LONG Nov 17: `99fc1d46a11eedac9a38fd7cefc9da6de78f7e36` (12:04:24 UTC).
7. SOL SHORT Nov 20: `6fca77eff6ba3442faed1c4e61c02e6aea2b0e43` (13:04:23 UTC).

## Method corrections from the first audit

- Distinguish **source exists before signal** vs **research snapshot created later**; the V7 source snapshots generally appeared ~13–32 minutes after each closed hour, so they are *after* the 05-minute hypothetical cutoff. Use the contemporaneous 04-minute market/structure commits for as-of detection and **use V7 snapshots only later to independently verify event candles / classify V7 watch state**.
- **Do not count zones already intersected by the signal candle wick** as a *future* target. On a SHORT signal, if signal-candle low <= zone upper edge, classify as `TOUCHED_DURING_SIGNAL_CANDLE`; on a LONG signal, if signal-candle high >= zone lower edge, likewise exclude.
- The research prototype `research/zone_target_intelligence_v0.py` now supports `--signal-candle-low` and `--signal-candle-high` (provide both). When omitted, output explicitly marks signal-bar eligibility as **NOT_CHECKED**; do not calculate valid future-hit ratios with unchecked inputs.
- Even after eliminating already-touched zones, distance ranking can count overlapping OBs/FVGs/levels multiple times. Group and score confluence separately before any claimed performance result.
- Open/filled FVG and OB states are **OHLCV heuristics**, not proof of exchange resting orders. The absence of a candidate in source's truncated/retained windows is **not** proof that no historical level exists outside that scope.
- Long and short performance require separate denominators and comparison to a frozen rule-based baseline. Measure eligible signals, no-zone cases, first untouched zone visits, reversal (predefined ATR and closed-candle rule), complete zone breaches, time to visit, fees/slippage and paper exits. Until full-sample, out-of-sample and prospective evaluation, do not promote to V7/production.
- The **19 Python unit test cases are defined** in the research branch as of this audit; their *GitHub CI execution has not been verified*, and no test pass claim should be made solely from file presence.

**Operational boundary:** No edits to `main`, workflows, alert automations, market publishers, production strategies or real/paper broker account balances. No orders or production notifications added.
