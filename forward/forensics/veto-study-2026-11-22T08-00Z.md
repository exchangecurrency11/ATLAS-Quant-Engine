# V7 — Engellenen BOS sinyalleri karşıolgusal inceleme

**Analiz kapanış sınırı:** 2026-11-22T08:00:00Z (UTC)
**Sistem:** PAPER ONLY; canlı emir ve gerçek getiri yok
**Orijinal doğrulanmış V7 gözlemi:** 383

| Ölçüm | Sonuç |
|---|---:|
| Gerçek zamanında kaydedilmiş BOS | 23 |
| Eski V4 tarafından kabul edilen BOS | 11 |
| V7 tarafından kabul edilen BOS | 5 |
| V7 tarafından engellenen BOS | 18 |
| **Yalnız yeni V7 filtrelerinin ek reddi** | **6** |
| Yalnız yeni V7 filtreleri sayesinde kaçınılan zarar | 0 |
| Yalnız yeni V7 filtreleri nedeniyle kaçırılan kârlı paper | 0 |
| Engellenip karşıolgusal işlem kapanan | 5 |
| Bunlardan maliyet sonrası zarar/sıfır | 4 |
| Bunlardan maliyet sonrası kâr | 1 |
| Henüz kesin karşıolgusal işlem sonucu yok | 13 |

**Atıf uyarısı:** Engellenen BOS'lardan kaçınılan zarar, otomatik olarak yeni V7 filtrelerine atfedilemez. V4 de reddediyorsa bu eski filtrelerin etkisidir.

## BTC ve SOL ayrı sonuç

| Parite | BOS | V7 kabul | V7 red | Red → kapanmış işlem | Zarar/0 kaçınıldı | Olası kârlı fırsat kaçtı |
|---|---:|---:|---:|---:|---:|---:|
| BTCUSDT_PERP.A | 13 | 1 | 12 | 3 | 2 | 1 |
| SOLUSDT_PERP.A | 10 | 4 | 6 | 2 | 2 | 0 |

## Filtre gerekçeleri (bir BOS için birden fazla gerekçe olabilir)

- 4H_DAILY_ALIGNMENT_VETO: 11
- V7_QUALITY_EMA20_OVEREXTENDED: 7
- V7_QUALITY_LOW_RELATIVE_VOLUME: 5
- V7_QUALITY_WEAK_BREAK_ATR: 4
- PREVIOUS_HOUR_VOLUME_VETO: 3
- 1H_RSI_MACD_MOMENTUM_VETO: 2

## Aday bazında sonuçlar

- **2026-11-05T13:00:00Z SOLUSDT_PERP.A bearish**, seviye 95.59; V7 RED; neden: 4H_DAILY_ALIGNMENT_VETO; sonuç: HISTORY_COVERAGE_MISSING_BOS; sınıf: UNRESOLVED_OR_NO_ACTIONABLE_ENTRY
- **2026-11-07T21:00:00Z SOLUSDT_PERP.A bearish**, seviye 89.13; V7 KABUL; neden: kabul; sonuç: HISTORY_COVERAGE_MISSING_BOS; sınıf: ACCEPTED_BY_V7_NOT_A_REJECTED_SIGNAL
- **2026-11-08T15:00:00Z BTCUSDT_PERP.A bullish**, seviye 75966.0; V7 RED; neden: 4H_DAILY_ALIGNMENT_VETO, PREVIOUS_HOUR_VOLUME_VETO; sonuç: HISTORY_COVERAGE_MISSING_BOS; sınıf: UNRESOLVED_OR_NO_ACTIONABLE_ENTRY
- **2026-11-08T22:00:00Z BTCUSDT_PERP.A bearish**, seviye 75634.0; V7 RED; neden: 4H_DAILY_ALIGNMENT_VETO, V7_QUALITY_EMA20_OVEREXTENDED; sonuç: HISTORY_COVERAGE_MISSING_BOS; sınıf: UNRESOLVED_OR_NO_ACTIONABLE_ENTRY
- **2026-11-10T11:00:00Z BTCUSDT_PERP.A bearish**, seviye 74343.0; V7 RED; neden: 4H_DAILY_ALIGNMENT_VETO, PREVIOUS_HOUR_VOLUME_VETO, V7_QUALITY_LOW_RELATIVE_VOLUME; sonuç: INSUFFICIENT_ATR_LOOKBACK; sınıf: UNRESOLVED_OR_NO_ACTIONABLE_ENTRY
- **2026-11-10T11:00:00Z SOLUSDT_PERP.A bearish**, seviye 85.47; V7 RED; neden: V7_QUALITY_EMA20_OVEREXTENDED; sonuç: INSUFFICIENT_ATR_LOOKBACK; sınıf: UNRESOLVED_OR_NO_ACTIONABLE_ENTRY
- **2026-11-11T17:00:00Z BTCUSDT_PERP.A bullish**, seviye 74156.6; V7 RED; neden: 4H_DAILY_ALIGNMENT_VETO, PREVIOUS_HOUR_VOLUME_VETO, V7_QUALITY_WEAK_BREAK_ATR; sonuç: CLOSED_COUNTERFACTUAL_PAPER, net -1.207688R; sınıf: AVOIDED_NEGATIVE_OR_FLAT_PAPER
- **2026-11-13T01:00:00Z BTCUSDT_PERP.A bearish**, seviye 71218.1; V7 KABUL; neden: kabul; sonuç: EXPIRED_WITHOUT_V4_RETEST; sınıf: ACCEPTED_BY_V7_NOT_A_REJECTED_SIGNAL
- **2026-11-13T03:00:00Z SOLUSDT_PERP.A bearish**, seviye 80.42; V7 KABUL; neden: kabul; sonuç: CLOSED_COUNTERFACTUAL_PAPER, net -1.084417R; sınıf: ACCEPTED_BY_V7_NOT_A_REJECTED_SIGNAL
- **2026-11-14T03:00:00Z BTCUSDT_PERP.A bearish**, seviye 68073.5; V7 RED; neden: 1H_RSI_MACD_MOMENTUM_VETO; sonuç: EXPIRED_WITHOUT_V4_RETEST; sınıf: UNRESOLVED_OR_NO_ACTIONABLE_ENTRY
- **2026-11-14T15:00:00Z BTCUSDT_PERP.A bearish**, seviye 66427.5; V7 RED; neden: V7_QUALITY_EMA20_OVEREXTENDED; sonuç: EXPIRED_WITHOUT_V4_RETEST; sınıf: UNRESOLVED_OR_NO_ACTIONABLE_ENTRY
- **2026-11-14T15:00:00Z SOLUSDT_PERP.A bearish**, seviye 74.77; V7 RED; neden: V7_QUALITY_EMA20_OVEREXTENDED; sonuç: EXPIRED_WITHOUT_V4_RETEST; sınıf: UNRESOLVED_OR_NO_ACTIONABLE_ENTRY
- **2026-11-14T21:00:00Z BTCUSDT_PERP.A bearish**, seviye 64969.0; V7 RED; neden: V7_QUALITY_EMA20_OVEREXTENDED; sonuç: EXPIRED_WITHOUT_V4_RETEST; sınıf: UNRESOLVED_OR_NO_ACTIONABLE_ENTRY
- **2026-11-17T09:00:00Z BTCUSDT_PERP.A bearish**, seviye 64351.0; V7 RED; neden: 4H_DAILY_ALIGNMENT_VETO, V7_QUALITY_WEAK_BREAK_ATR, V7_QUALITY_LOW_RELATIVE_VOLUME; sonuç: CLOSED_COUNTERFACTUAL_PAPER, net -1.171388R; sınıf: AVOIDED_NEGATIVE_OR_FLAT_PAPER
- **2026-11-17T12:00:00Z SOLUSDT_PERP.A bullish**, seviye 73.27; V7 RED; neden: 4H_DAILY_ALIGNMENT_VETO; sonuç: CLOSED_COUNTERFACTUAL_PAPER, net -1.077753R; sınıf: AVOIDED_NEGATIVE_OR_FLAT_PAPER
- **2026-11-18T00:00:00Z SOLUSDT_PERP.A bullish**, seviye 74.29; V7 RED; neden: 4H_DAILY_ALIGNMENT_VETO; sonuç: CLOSED_COUNTERFACTUAL_PAPER, net -0.530451R; sınıf: AVOIDED_NEGATIVE_OR_FLAT_PAPER
- **2026-11-18T13:00:00Z BTCUSDT_PERP.A bearish**, seviye 64100.0; V7 RED; neden: 4H_DAILY_ALIGNMENT_VETO, V7_QUALITY_WEAK_BREAK_ATR, V7_QUALITY_LOW_RELATIVE_VOLUME; sonuç: CLOSED_COUNTERFACTUAL_PAPER, net 1.76362R; sınıf: POTENTIALLY_MISSED_POSITIVE_PAPER
- **2026-11-18T23:00:00Z BTCUSDT_PERP.A bearish**, seviye 62250.2; V7 RED; neden: 4H_DAILY_ALIGNMENT_VETO, V7_QUALITY_WEAK_BREAK_ATR, V7_QUALITY_LOW_RELATIVE_VOLUME; sonuç: EXPIRED_WITHOUT_V4_RETEST; sınıf: UNRESOLVED_OR_NO_ACTIONABLE_ENTRY
- **2026-11-19T04:00:00Z SOLUSDT_PERP.A bullish**, seviye 73.94; V7 RED; neden: 4H_DAILY_ALIGNMENT_VETO, 1H_RSI_MACD_MOMENTUM_VETO, V7_QUALITY_LOW_RELATIVE_VOLUME; sonuç: EXPIRED_WITHOUT_V4_RETEST; sınıf: UNRESOLVED_OR_NO_ACTIONABLE_ENTRY
- **2026-11-20T13:00:00Z SOLUSDT_PERP.A bearish**, seviye 71.55; V7 KABUL; neden: kabul; sonuç: CLOSED_COUNTERFACTUAL_PAPER, net 1.852432R; sınıf: ACCEPTED_BY_V7_NOT_A_REJECTED_SIGNAL
- **2026-11-20T16:00:00Z BTCUSDT_PERP.A bearish**, seviye 61255.6; V7 RED; neden: V7_QUALITY_EMA20_OVEREXTENDED; sonuç: EXPIRED_WITHOUT_V4_RETEST; sınıf: UNRESOLVED_OR_NO_ACTIONABLE_ENTRY
- **2026-11-21T04:00:00Z BTCUSDT_PERP.A bearish**, seviye 57700.1; V7 RED; neden: V7_QUALITY_EMA20_OVEREXTENDED; sonuç: EXPIRED_WITHOUT_V4_RETEST; sınıf: UNRESOLVED_OR_NO_ACTIONABLE_ENTRY
- **2026-11-21T04:00:00Z SOLUSDT_PERP.A bearish**, seviye 67.08; V7 KABUL; neden: kabul; sonuç: EXPIRED_WITHOUT_V4_RETEST; sınıf: ACCEPTED_BY_V7_NOT_A_REJECTED_SIGNAL

## Yorum ve sınırlamalar

- A missed positive is a counterfactual PAPER trade, not a proven realizable winning live trade.
- Not selected from unobserved/missed-hour BOS; those hours remain MISSED_OBSERVATION.
- Never interpret a price change without retest/entry as a missed win.
- A gate can have MULTIPLE rejection causes; factor counts are overlapping.
- Incomplete future 1H data = pending, not a winner or a loser.
- Historical feed acquired later cannot make the observation a contemporaneous live signal.
- No funding, orderbook, actual fills, variable slippage, liquidation, portfolio overlap.
- No V7 threshold tuning on this inspected sample; tiny samples are not efficacy proof.

Bu sonuçlar yeni V7 parametrelerini ayarlamak için değil, kaçırılan fırsatlar ile kötü işlemlerden korunmayı karşılaştırmak içindir.
