# ATLAS Core E4-B — Official historical funding rates (BTC/ETH/SOL)

**Research-only, already inspected historical trades, no new alpha or live execution.**

## Why this exists

E4-A simulated constant *adverse* funding bps alongside 9,25,50bps
commission + half-spread + impact scenarios. E4-B replaces that
constant assumption with the **historical signed rates and exact event
timestamps** published in official Binance USD-M Futures monthly
\`fundingRate\` ZIP archives, then recomputes the same 51 previously
sealed V9.2 baseline trades and shared portfolio. This is NOT a new
candidate rule, independently unseen OOS, real fill, or accurate
reconstruction of an actual account's realized funding debit/credit.

Binance official dataset path:

\`https://data.binance.vision/data/futures/um/monthly/fundingRate/<SYMBOL>/<SYMBOL>-fundingRate-<YYYY-MM>.zip\`

Every ZIP must match Binance's sibling \`.zip.CHECKSUM\` SHA-256.
For all three assets and both historical periods the 159 1H OHLC archives
and **another 159 fundingRate archives** are freshly downloaded,
validated and accounted. No missing month, duplicated settlement
timestamp or unexplained gap is silently filled. Official funding CSV
schema, confirmed via read-only CI probe:

\`calc_time,funding_interval_hours,last_funding_rate\`

E4-B preserves the **publisher's actual variable funding interval**
rather than assuming 8 hours. If event intervals are unexplainable by
adjacent published interval values, the run must fail closed.

## Data provenance limitations

- The public official fundingRate monthly CSV archives have the
  settlement time and **signed historical funding rate** but **do not
  contain a settlement mark price**. The official REST endpoint can
  sometimes provide a mark price, but the read-only GitHub runner
  returned HTTP **451**, so this study does NOT claim that an official
  settlement mark was obtained.
- To estimate USDT funding per hypothetical unit, E4-B uses the
  **verified Binance 1H OHLC OPEN at the funding event timestamp as a
  mark-price proxy**. This differs from exchange settlement mark price.
- Positive funding rate: simulated LONG pays / SHORT receives. Negative
  rate: simulated LONG receives / SHORT pays. Real accounts may have
  special rules and undisclosed market state.
- Fractional remaining position is reconstructed from previous hourly
  stop/TP fills before each funding boundary. 1H intrabar execution
  remains ambiguous; funding exactly at entry or exit is excluded and
  disclosed as boundary uncertainty. No funding payment can be
  reconstructed from an account because no user income data is used.
- OHLC open != mark and the difference is unquantified in E4-B. Do not
  report modeled funding USDT as a verified Binance account balance.

Binance docs for REST funding with optional markPrice:
https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Get-Funding-Rate-History

## Preserved E4-A conditions

- Original E4-A code pinned to git blob:
  \`865e30925ecef323c54659a9720f89568c29d0ec\`.
- E4-A engine and earlier E3/E2 source pins and 51 trades revalidated
  from 159 separately verified OHLC ZIPs.
- Three original 9/25/50bps-per-side hypothetical execution frictions
  completely unchanged. Only fixed adverse funding is replaced by
  actual signed observed rates and a proxy mark.
- Shared virtual realized-only portfolio unchanged: 10k USDT initial
  balance, 0.5% per entry stop-risk, 1% concurrent risk cap, 1.5×
  gross notional, 0.1% minimum acceptance size. These are sensitivity
  parameters, not deployment recommendations.
- Internal side-by-side replay must reproduce E4-A reported results
  (10,271.8196 / 9,503.8182 / 8,376.7766 USDT) within 2 cents.
- A trade missing an expected funding interval or missing 1H OHLC
  mark proxy aborts rather than silently charging zero.
- Funding receipts are strictly timestamped in the trade's OPEN
  interval, excluding exact entry/exit; no prospective records touched.

## Run from repository root

    python3 -m unittest research.atlas_core_v0.test_atlas_core_v0 -v
    python3 -m unittest research.atlas_core_v1.test_atlas_core_e2 -v
    python3 -m unittest research.atlas_core_v2.test_atlas_core_e3 -v
    python3 -m unittest research.atlas_core_v3.test_atlas_core_e4 -v
    python3 -m unittest research.atlas_core_v4.test_atlas_core_e4b -v
    python3 -u -m research.atlas_core_v4.atlas_core_e4b --workers 6

Expected GitHub read-only workflow: manually or research-branch push
triggered; permissions \`contents:read\`, no checkout credentials,
no schedule, no commits/pushes, and temporary report JSON/MD artifacts
only, retained for 30 days.

## What E4-B cannot solve

Actual per-second orderbook spreads or trade execution, maker/taker
account-specific fees, realized funding without settlement mark,
liquidation and mark-to-market intratrade drawdown. These demand
additional official datasets or separately measured venue/account
records and **another dedicated research phase**. E4-B cannot by
itself approve production strategies. Keep all ETH, BTC and SOL
prospective research frozen and entirely separate.
