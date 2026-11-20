# ATLAS — pilot comparison: LONG/SHORT zone exits vs fixed 2-ATR target

**Audit date:** 2026-11-20. **Strict classification:** exploratory preselected seven-case diagnostic, NOT a full-sample backtest, proof of strategy superiority, an actual V7 exit comparison, a trade signal, a broker fill, or an assessment of users' exact historical alert-delivery timestamps.

## Selection, provenance, and outcomes

Seven already-discussed 1H BTC/SOL structural BOS examples selected before this pilot outcome calculation. Six have the full following 12 1H candles; SOL SHORT on Nov 20 has only six available hourly closes and is **right-censored**, not counted in the matched comparison. The closed-candle event prices and source publication times were independently checked against their historical `market_data.json` Git commits; the 1H, 4H and daily zone candidates are from the correspondingly time-pinned historical `market_structure_data.json` commits (listed below). The V7 observation snapshots were published **after** the ~04-minute live publisher; use them to retrospectively verify event/ATR, **not** to claim that their contents were already available at 05 minutes.

### Observed 12-hour zone quality (strictly structural, independent of trade exits)

| 1H event UTC | Side | Signal close | First previously-known, ahead-of-signal, signal-bar-untouched candidate | Touched within 12h? | Reverse at least 0.5 ATR in next 3 closed 1H candles? | Closed beyond zone far edge within 12h? |
|---|---|---:|---|---|---|---|
| 2026-11-08 15:00 BTC | LONG | 76,007 | 76,125.70 chart equal-high proxy | No | N/A | N/A |
| 2026-11-13 01:00 BTC | SHORT | 71,096.30 | 65,057.90–68,882.10 Daily bullish FVG | Yes, hour 3 | No | No |
| 2026-11-13 03:00 SOL | SHORT | 80.18 | 76.20–76.59 Daily bullish FVG | No | N/A | N/A |
| 2026-11-14 15:00 SOL | SHORT | 74.05 | 73.34 Daily equal-low chart proxy; 73.69 and 72.65–74.00 OB already touched in signal candle | Yes, hour 1 | No | Yes |
| **2026-11-14 21:00 BTC** | **SHORT** | **64,738** | **63,370–63,979.20 Daily bullish FVG** | **Yes, hour 1** | **No** | **Yes** |
| 2026-11-17 12:00 SOL | LONG | 73.46 | 73.91–75.02 4H bearish FVG | Yes, hour 2 | Yes | Yes, subsequently |
| 2026-11-20 13:00 SOL | SHORT | 71.06 | **No retained qualifying candidate** | N/A; only 6h observed | N/A | N/A |

**Raw descriptive counts:** 4 of 6 fully observed cases visited the nearest known level, **only 1 of those 4** met the predefined 0.5-ATR adverse-reversal-on-closes criterion within the next three closed 1H bars; **3 of the 4** later had a closed-candle breach beyond the zone far edge during the 12-hour horizon. These counts are **not predictive success rates**, because the examples were preselected, thresholds were explored after inspecting history, and the window and samples are small.

A zone's visit and a zone's reversal are independent attributes: the SOL 17-Nov FVG was touched, was followed by a qualified reversal, and was subsequently broken on the final observed candle. Same-direction price travel after touching a level is not proof of successful support/resistance.

### Hypothetical exit comparison: delayed entry (primary risk-controlled view)

**Frozen for this *diagnostic* comparison:** two theoretical approaches to the same structure event: nearest eligible zone edge as the entire hypothetical TP versus a fixed **2 × 1H ATR** entire hypothetical TP. Both use a **1 × 1H ATR** stop, no position scaling, and 12-hour total horizon measured from the BOS close (therefore ~11h after the delayed entry). To respect the ~04-minute Git publisher delay, hypothetical entry occurs at the **second following hourly candle's OPEN**, i.e. the first full-hour open *after* the 05-minute as-of source publication. Never claim fills at the signal close or at the earlier hour open. Any candidate zone already reached during the waiting candle is **SKIPPED**, rather than crediting an exit achieved before entry. OHLC cannot establish within-candle barrier order; in a simultaneous stop/TP touch, award **stop**. Example cost haircut **0.12% round trip of entry notional** (0.04% each direction taker + 0.02% each direction slippage), expressed in 1H ATR risk units; these are assumptions, not measured exchange fees. No funding, spread dynamics, partials, liquidation or order-book depth included. Entry or exit at exact levels still not proven executable.

`R` = price PnL divided by 1H ATR (before friction), or net after illustrative roundtrip friction. No actual V7 trade is implied.

| Event | Nearest-zone method, net R | Fixed 2-ATR method, net R | Reason |
|---|---:|---:|---|
| BTC LONG Nov 8 | −1.673 | −1.673 | Both stop in first eligible bar |
| BTC SHORT Nov 13 | **+3.557** | +1.845 | Zone target farther away; both reached |
| SOL SHORT Nov 13 | −1.106 | −1.106 | Both stop; initial move before modeled delayed entry is not credited |
| SOL SHORT Nov 14 | **SKIP (0 allocated)** | +1.907 | First zone touched *before* delayed entry |
| BTC SHORT Nov 14 | **SKIP (0 allocated)** | +1.884 | First zone touched *before* delayed entry |
| SOL LONG Nov 17 | **+0.248** | −1.121 | First supply-FVG edge reached before stop; fixed 2-ATR target not reached first |
| SOL SHORT Nov 20 | **NO_ZONE**, right-censored 6h | +1.904 (observed 3rd bar) | Not in six-case 12h comparison |

Among the **four eligible paired scenarios where a zone model could enter**, mean theoretical **zone +0.2565 net R vs fixed −0.5137 net R**; this is a selected conditional subset, NOT a complete strategy comparison. Across **all six complete structural events**, if an avoided zone trade scores zero deployed R and the fixed model acts in all six, mean theoretical outcome **zone +0.171 net R per event vs fixed +0.289 net R per event**. The gross model and these absolute R sums are not portfolio equity returns. The two strategies have different participation rates and exposure; no risk-adjusted superiority can be inferred. Sensitivity to different entry delays, 1H-ATR stop sizing, costs and target definitions has not been analyzed.

**Contrasting unrealistic diagnostic:** If a backtest assumes a fill at the next-hour OPEN immediately at the BOS close **before** contemporaneous source-commit publication, it obtains zone +0.547 net R/event vs fixed +0.789 net R/event for these six. This variant **violates executable source timing** and is provided only as a warning: do not report or promote it as achievable PnL.

### Underlying contemporaneous source citations for each scenario

| Scenario | Structure snapshot Git commit (published approx 04 minutes after event close) | Current-hour `market_data.json` commit |
|---|---|---|
| BTC LONG Nov 8 15 UTC | `ced7b11db75ac0f5f9ec9b4d4461e2356de0aa8f` | `674737e6aebb53951555c846538094510b109b0f` |
| BTC SHORT Nov 13 01 UTC | `eae2fa0d908645527978c7c86010468c5f21112d` | `8171c33075f03b8ed9fc9327570ebca630856163` |
| SOL SHORT Nov 13 03 UTC | `2525571ba5cf360b751e598bc819f0b7986308de` | `e31083c472aaee581c101917589e7d49e75eaf46` |
| SOL SHORT Nov 14 15 UTC | `e0730e3c95f995a060fc645375b332005ddb2d36` | `22991a816461cab90ac579e187275de7804bd694` |
| BTC SHORT Nov 14 21 UTC | `085c7d70147a0493bffc8a53de6109e08907101e` | `81c18a112d785f837ccccb34520e83c7b5276871` |
| SOL LONG Nov 17 12 UTC | `c5adb9f00d2fde3318b5776c2e3029f6d89ff25c` | `99fc1d46a11eedac9a38fd7cefc9da6de78f7e36` |
| SOL SHORT Nov 20 13 UTC | `35a1b15e4bd5de2b63677da57b1f9836103c057c` | `6fca77eff6ba3442faed1c4e61c02e6aea2b0e43` |

All forward 1H OHLC samples were inspected in the hourly **`market_data.json` history**, with GitHub commit metadata per hour; the local reproducibility calculation includes each individual bar, the source window and the conservative stop-first rule. No gaps in the 12-hour **market publisher** hour sequence for these six cases, despite gaps in the separate V7 paper snapshot folders.

**Next:** execute the full retained set of BTC/SOL structure events (not only handpicked cases), group overlapping zones, verify persisted alert times (do not infer from matching price), freeze exit parameters **before** out-of-sample/prospective paper evaluation, and audit trading costs. Use actual V7 exit rules for an *explicit* V7 baseline only if contemporaneous eligible paper trade/exit records are available. Do not alter V7, main, GitHub workflows, market publishers, ChatGPT alert tasks or real/paper order books without explicit approval.
