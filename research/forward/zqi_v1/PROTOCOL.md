# ATLAS ZQI V1 — Prospective Shadow Observation Protocol

**This is an append-only forward research experiment, not a trading system.** Data read from main is allowed; writes ONLY to research/atlas-zone-quality-v1-forward-20261121 under research/forward/zqi_v1/. Do not edit V7/V9, alerts, live paper accounts, any GitHub Actions, or main.

## Frozen start and source timing

- Manifest: research/forward/zqi_v1/FROZEN_MANIFEST.json.
- First eligible UTC 1H close: **2026-11-20 22:00 UTC** (21 November 01:00 Europe/Istanbul). Discard any earlier event from prospective results.
- Run source check near **12 minutes after each complete 1H close**. For that event choose Git-committed market_data.json and market_structure_data.json source commits published **after close and no later than close + 5 minutes**. Verify exact 40-character commit SHAs and GitHub committer publication timestamps. Source publication is not the observation time.
- The prediction itself must be saved as a NEW GitHub file **before the next 1H candle closes**. Use GitHub commit time as evidence. An event recorded late is LATE_CAPTURE, must never be counted as prospective, even if an older SHA could be fetched later.
- Process every BTC/SOL 1H BOS and CHoCH closed-hour event, independent of direction or score. The structure event 'at' is candle start: require event at = close - 3600 seconds.
- If as-of publisher data are not available or have timestamps out of order, write a unique SOURCE_GAP/ERROR check, not a fabricated NO_EVENT or NO_ZONE.

## Hourly write procedure

1. Read GitHub current or historical (as-of) source commits and ensure both 1H BTC/SOL market and structure close timestamps match the selected completed hour. Check if observation file already exists; if present, DO NOT overwrite.
2. If neither asset has a new BOS/CHoCH, record one immutable NO_NEW_STRUCTURE_EVENT check for the hour; skip ATR retrieval.
3. If at least one event is present, fetch all **15 consecutive hourly market_data.json source commits**, ending at that same hour, with exact per-hour close and published timestamps. Compute ATR14 from fourteen true ranges, including signal candle. No substitutes, guessed ATR or future hours.
4. Use the frozen engine research/zone_quality_intelligence_v1.py via research/zone_quality_forward_shadow_v1.py score-hour. Freeze the raw list and structural evidence index for EVERY zone, best-quality-zone ID, nearest-distance-zone ID, wick exclusions and NO_ZONE.
5. Save immutable event-hour JSON to research/forward/zqi_v1/observations/YYYY/MM/DD/HH00Z.json using GitHub create_file; avoid updates and same-path retries. Capture status should be EVENTS_CAPTURED or NO_NEW_STRUCTURE_EVENT. Verify the resulting commit time precedes the next hourly close; otherwise append an invalidity note and exclude it from prospective counts.
6. On source errors write research/forward/zqi_v1/errors/YYYY/MM/DD/HH00Z.json with reasons and provenance. Do NOT silently backfill successes.

## 12h settlement

- Each hourly check also scans previously captured EVENT files whose next 12 closed 1H bars are now observable and for which no settlement file exists.
- Fetch 12 **newer source-pinned** consecutive Git market snapshots, one per hour, always after the captured event. Require publication at or after corresponding close and before settlement time.
- Run research/zone_quality_forward_shadow_v1.py settle-hour. The output records each scored zone's visited-in-12h, first-touch hour, opposing 0.5 ATR close reaction within next three closed 1H candles after touch, and subsequent close beyond far edge.
- Save once to research/forward/zqi_v1/outcomes/YYYY/MM/DD/HH00Z.json. Never rewrite the prior prediction, even if later price action contradicts it.
- Missing hours or otherwise unresolved outcomes are CENSORED with explicit data gaps and are excluded from full-horizon success denominators.

## Evaluation principles

- No threshold tuning, no ranking change and no score calibration with knowledge of the future before 30 matured events **AND** 30 elapsed days. That is a first descriptive review, not proof of superiority.
- Keep all zones, NO_ZONE, no-event checks, source gaps and failures. Compare top-quality vs nearest-distance regions on visit, conditional adverse reaction, far-edge break and distance-ATR strata.
- Report BTC LONG, BTC SHORT, SOL LONG, SOL SHORT separately; BOS vs CHoCH separately. Correlated hours and shared price action cannot be summed as actual trades.
- A score of 80 is not an 80% reversal probability. No orders, hypothetical positions, profit transfers or ledger balance changes are authorized.
- The task may notify the user when a fresh scored event is captured, a 12h settlement materializes, or a source failure blocks coverage; otherwise stay quiet.

## CLI shape (research only)

From the research directory run the Python stdlib-only script with pinned input files:

python zone_quality_forward_shadow_v1.py score-hour --market market.json --structure structure.json --history last15.json --event-close-utc 2026-11-20T22:00:00Z --observed-at-utc 2026-11-20T22:12:00Z --start-utc 2026-11-20T22:00:00Z --market-sha FULL_SHA --market-published-utc ISO_Z --structure-sha FULL_SHA --structure-published-utc ISO_Z --output unique-prediction.json

python zone_quality_forward_shadow_v1.py settle-hour --prediction frozen-prediction.json --future-rows next12.json --settled-at-utc ISO_Z --output unique-outcome.json

Input hour records use the archived schema from research/data/atlas_hourly_ohlcv_part_*.json: each record includes sha, publishedUTC, btc (market result row) and sol (market result row).

**Execution note:** This research branch has no new workflow. Recurring observation requires the newly created ChatGPT automation; an existing price/alert automation is not modified. Before claiming any run succeeded, inspect that run's GitHub files and timestamps.