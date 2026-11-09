# V7 — Engellenen BOS sinyalleri karşıolgusal inceleme

**Analiz kapanış sınırı:** 2026-11-09T21:00:00Z (UTC)
**Sistem:** PAPER ONLY; canlı emir ve gerçek getiri yok
**Orijinal doğrulanmış V7 gözlemi:** 119

| Ölçüm | Sonuç |
|---|---:|
| Gerçek zamanında kaydedilmiş BOS | 4 |
| Eski V4 tarafından kabul edilen BOS | 1 |
| V7 tarafından kabul edilen BOS | 1 |
| V7 tarafından engellenen BOS | 3 |
| **Yalnız yeni V7 filtrelerinin ek reddi** | **0** |
| Yalnız yeni V7 filtreleri sayesinde kaçınılan zarar | 0 |
| Yalnız yeni V7 filtreleri nedeniyle kaçırılan kârlı paper | 0 |
| Engellenip karşıolgusal işlem kapanan | 1 |
| Bunlardan maliyet sonrası zarar/sıfır | 1 |
| Bunlardan maliyet sonrası kâr | 0 |
| Henüz kesin karşıolgusal işlem sonucu yok | 2 |

**Atıf uyarısı:** Engellenen BOS'lardan kaçınılan zarar, otomatik olarak yeni V7 filtrelerine atfedilemez. V4 de reddediyorsa bu eski filtrelerin etkisidir.

## BTC ve SOL ayrı sonuç

| Parite | BOS | V7 kabul | V7 red | Red → kapanmış işlem | Zarar/0 kaçınıldı | Olası kârlı fırsat kaçtı |
|---|---:|---:|---:|---:|---:|---:|
| BTCUSDT_PERP.A | 2 | 0 | 2 | 1 | 1 | 0 |
| SOLUSDT_PERP.A | 2 | 1 | 1 | 0 | 0 | 0 |

## Filtre gerekçeleri (bir BOS için birden fazla gerekçe olabilir)

- 4H_DAILY_ALIGNMENT_VETO: 3
- PREVIOUS_HOUR_VOLUME_VETO: 1
- V7_QUALITY_EMA20_OVEREXTENDED: 1

## Aday bazında sonuçlar

- **2026-11-05T13:00:00Z SOLUSDT_PERP.A bearish**, seviye 95.59; V7 RED; neden: 4H_DAILY_ALIGNMENT_VETO; sonuç: EXPIRED_WITHOUT_V4_RETEST; sınıf: UNRESOLVED_OR_NO_ACTIONABLE_ENTRY
- **2026-11-07T21:00:00Z SOLUSDT_PERP.A bearish**, seviye 89.13; V7 KABUL; neden: kabul; sonuç: CLOSED_COUNTERFACTUAL_PAPER, net -1.248236R; sınıf: ACCEPTED_BY_V7_NOT_A_REJECTED_SIGNAL
- **2026-11-08T15:00:00Z BTCUSDT_PERP.A bullish**, seviye 75966.0; V7 RED; neden: 4H_DAILY_ALIGNMENT_VETO, PREVIOUS_HOUR_VOLUME_VETO; sonuç: CLOSED_COUNTERFACTUAL_PAPER, net -1.680227R; sınıf: AVOIDED_NEGATIVE_OR_FLAT_PAPER
- **2026-11-08T22:00:00Z BTCUSDT_PERP.A bearish**, seviye 75634.0; V7 RED; neden: 4H_DAILY_ALIGNMENT_VETO, V7_QUALITY_EMA20_OVEREXTENDED; sonuç: EXPIRED_WITHOUT_V4_RETEST; sınıf: UNRESOLVED_OR_NO_ACTIONABLE_ENTRY

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
