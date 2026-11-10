# SOLUSDT Perpetual — OI / Funding / Taker veri kalitesi

**Dönem (UTC):** 2026-11-01 – 2026-11-09
**Sözleşme:** Binance USD-M SOLUSDT (spot değil)
**Kaynak:** Binance resmî arşivleri; ZIP SHA-256 doğrulaması
**Kullanım:** Yalnız veri kalitesi araştırması, işlem sinyali değil

| Veri | Beklenen | Doğrulanmış | Kapsam |
|---|---:|---:|---:|
| OI (5m) | 2592 | 2592 | %100.0 |
| Taker 5m OHLCV | 2592 | 2592 | %100.0 |
| Taker 1H OHLCV | 216 | 216 | %100.0 |

## OI kayıp veri ve zamanlama
- Boş 5m dilimleri: 0. Kayıp aralık grubu: 0.
- En büyük kesinti: 0 adet 5m dilimi.
- Son OI etiketi: 2026-11-09T23:55:00Z. En erken kullanılabilir kapanış: 2026-11-10T00:00:00Z.
- Kaynak satırları zaman sırasından sapma: 224 (içeriğin kayıp olduğu anlamına gelmez; zaman damgasına göre sıralanmalı).
- Geçersiz/uyarı kayıt türleri: {'UNSORTED_SOURCE_ROW_TRANSITIONS': 224}.
- Önemli: 2026-06-25 sonrası Binance metrics create_time başlangıç etiketlidir. T+5m öncesi stratejiye verilirse ileriye bakma hatası olur.

## Taker hacmi tutarlılığı
- 1H saatinin 12×5m toplamıyla doğrulandığı saat: 216.
- Hacim/toplam quote/taker alış uyuşmazlığı olan saat: 0.
- 5m verisi eksik olduğu için test edilemeyen 1H: 0.
- Metrikteki taker ratio ve resmî 5m mumlardan eşleşen örnek: 2592.
- Aynı pencere için median ratio mutlak farkı: 0.000181.
- 0,01 üzerinde ratio farkı: 158; 0,05 üzerinde: 32.

## Funding Rate
- En son bu çalışmada doğrulanan aylık paket: 2026-10.
- Kayıt sayısı: 93; son funding: 2026-10-31T16:00:00Z.
- Interval saat dağılımı: {8: 93}.
- Kasım 2026 güncel funding geçmişi bu kaynak üzerinden doğrulanamadı.

## Dosya kalitesi
- SHA256 ile doğrulanan Binance arşiv paketi: 28.
- Arşiv erişim veya içerik hata sayısı: 0.

## Canlı V7 için karar
Bu arşiv kalite değerlendirmesi **canlı taker/OI/funding filtrelerinin çalıştığını kanıtlamaz**.
Eksik OI için 0 atamak veya ileriye dönük doldurmak yasak.
Arşiv gecikmesi nedeniyle üç veri, yeni API akışı doğrulanana kadar V7'ye otomatik gating olarak eklenmez.
API key/alternatif salt-okunur akış ancak kendi kapanış zamanıyla ve örnek bazında doğrulanır.

## Sınırlar
- Binance REST for live OI/funding returns HTTP 451 from GitHub runner.
- Public daily OI metrics after 2026-06-25 use START labels; value cannot be known at create_time until period ends. Explicit +5min delay.
- Funding historical monthly October archive cannot be treated as latest November funding.
- Trading-significance or predictive efficacy not measured; only data integrity and coverage.
- Missing 5min OI samples must NEVER be forward-filled or interpreted as zero OI.
- Missing 2026-10-28 SOL klines ZIP is outside study period; prior trade-derived recovery is separate evidence.

### En büyük OI boşlukları

