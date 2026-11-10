# SOL — OI ve taker basıncı / V7 paper işlem sonuçları

**Çalışma:** Tarihsel V7 paper trades + 1–9 Kasım contemporaneous forward BOS kayıtları ayrı.
**Kaynak:** Geçmiş V7 işlem artifact'i sabit; Binance resmî Futures arşivleri SHA256 doğrulandı.
**Uyarı:** Veriler SONRADAN arşivden edinildi. Sinyal kapanışını aşan OHLCV/OI kullanılmadı; bu canlı kanıt değildir.

## Orijinal tarihsel V7 (BOS kalite filtresi)

| Outcome | Paper trade | OI 1h medyan değişim | Taker sinyal yönü 1H medyan baskı | Funding elde |
|---|---:|---:|---:|---:|
| Kazanan | 7 | +1.006% (n=7) | +0.0838 (n=7) | 7 |
| Kayıplı/başa baş | 7 | +0.354% (n=7) | +0.1024 (n=7) | 6 |

**Veri tamlığı:** Tarihsel 14 V7 paper işleminin kaçında OI/taker/funding var?

| Alan | Elde | Eksik |
|---|---:|---:|
| oi1hPct | 14 | 0 |
| oi4hPct | 14 | 0 |
| takerSignedPressure1h | 14 | 0 |
| lastKnownFundingRate | 13 | 1 |

## Tüm V4 baseline (ayrı örnek, bağımsız ek işlem değil)
- V4 paper işlemler: 34; aynı arşivden, V7 ile çakışan işlemler ayrıca sayılmaz.

## İleri gözlenen SOL BOS (sıfır/tek trade ayrımı)

- 2026-11-05T13:00:00Z bearish | V7 kabul=False | CENSORED_NO_ACTIONABLE_ENTRY | netR=None | OI1H=-0.49783 % | yönlü taker=0.127607
- 2026-11-07T21:00:00Z bearish | V7 kabul=True | NEGATIVE_OR_FLAT_PAPER | netR=-1.248236 | OI1H=-0.24486 % | yönlü taker=0.172595

## Karar
- Bu tablo *ilişki betimler*; sinyal kazancını artıran yeni OI/taker eşiği ispatlamaz.
- 14 tarihsel SOL V7 paper işlem istatistiksel olarak çok küçük; aynı geçmiş üzerinde eşik seçilmez.
- OI 5m gösterge etiketi T, ancak ancak T+5m itibarıyla erişilebilir sayıldı.
- OI/funding/taker için aynı saat piyasada gerçekten erişilebilen veri kaynağı henüz yok; tarihsel ZIP ertesi gün oluşur.
- Funding yayın zamanı ayrıca bilinmez; en az 1 dakika koruma kullanılır.
- Gerçek emir, broker bağlantısı, ana V7 eşikleri ve BTC/SOL üretim sistemi değiştirilmedi.
- Finansman ve gerçek fill maliyetleri historical paper işlem R sonucuna dahil değildir.

## Doğrulama
- SHA256 verified paketler: 150. Arşiv erişim hatası: 1.
- Hatalar ve tüm işlem bazlı özellikler JSON raporunda. Sonuçlar yalnız deneysel araştırmadır.
