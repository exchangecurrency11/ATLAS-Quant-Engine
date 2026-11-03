# BTC/SOL Geçmiş Veri Envanteri — 3 Kasım 2026

**Durum: tarihsel veri 2 Kasım 2026 UTC gün sonuna kadar kesintisiz yeniden üretildi.**

[Başarılı GitHub Actions run #41638329887](https://github.com/exchangecurrency11/BTC-SOL-ANALYS-S/actions/runs/41638329887)

## Kaynaklar ve doğrulama

- 1 Ekim 2024 – 30 Eylül 2026: Binance resmî USD-M Futures aylık 1H ZIP; her dosyanın Binance SHA-256 dosyası doğrulandı.
- 1–27 Ekim 2026 ve 29 Ekim – 2 Kasım 2026: Binance resmî USD-M Futures günlük 1H ZIP; SHA-256 doğrulandı.
- **28 Ekim 2026:** Binance resmî günlük ve aylık 1H arşivlerinde bu günün 24 mumu **yok**. Resmî `/fapi/v1/klines` API'ye GitHub runner IP'lerinden erişim 451/yanıtsız oldu.
- **28 Ekim için geçerli telafi:** Binance resmî USD-M Futures **ham trade** ZIP dosyaları; BTCUSDT için 2.568.252, SOLUSDT için 1.553.139 gerçek trade satırı kullanıldı. Her iki ZIP Binance tarafından yayımlanan **SHA-256 dosyası ile doğrulandı**; trade zaman damgasına göre UTC 24 1H OHLCV mumuna indirgenerek hesaplandı. **Aradeğer doldurma, spot fiyatı ve uydurma mum kullanılmadı.**
- 28 Ekim rekonstrüksiyonu, bağımsız ikinci kaynak olarak sabitlenmiş Coinalyze Binance perpetual 1H OHLCV kayıtlarıyla tüm 24 saat için karşılaştırıldı. Her iki varlıkta **yüksek, düşük ve kapanış 24/24 aynı**; BTC'de sadece 1 adet saatlik açılışta 0,1 USD fark, SOL'da açılışlar tamamen aynı. En yüksek saatlik mutlak hacim farkı BTC'de **%0,1552**, SOL'da **%0,2985**; ikisi de %0,5 kalite eşiğinin altında.
- Coinalyze doğrulama referansı: `validation_refs/coinalyze_oct28_1h_reference.json`. Bu kaynak **Binance'in yayımladığı orijinal 1H kline dosyası değildir**; 28 Ekim mumlarını doğrudan Binance native 1H ZIP'i olarak iddia etmiyoruz.
- 29 Ekim ham trade ZIP dosyasının son saatlerindeki hacim eksikliğinden dolayı onu 28 Ekim'i doğrulamak için kullanmadık; 29 Ekim mumları resmî günlük **1H kline** ZIP dosyasından geldi.

## Bütünlük

| Periyot | BTCUSDT | SOLUSDT |
|---|---:|---:|
| 1H | 18.312 | 18.312 |
| 4H (1H'den UTC toplama) | 4.578 | 4.578 |
| 1D (1H'den UTC toplama) | 763 | 763 |

Veri başlangıcı **2024-10-01 00:00 UTC**. Son tamamlanmış gün **2026-11-02**, veri bitişi özel olarak **2026-11-03 00:00 UTC (exclusive)**.

Her saatlik mum zaman damgası ve tam günlük bağ kontrol edildi; bir saatlik boşluk / çakışma kabul edilmedi.

**61/61 otomatik regresyon testi geçti.** V6'nın geçmiş sinyal/işlem kayıtları V8 yeniden oynatıldığında birebir korunmuştur:
- BTC: ilk 62 BOS erken uyarı ve 18 tarihsel paper işlem değişmedi.
- SOL: ilk 79 uyarı ve 33 paper işlem değişmedi.

## Güncel ama hâlâ sadece deneysel olan metodun sonuçları

V4 kurallarında değişiklik yapmadan yeni arşivle yapılan paper replay:
- BTC: 62 erken uyarı, 18 sonuçlanmış varsayımsal işlem, 11 kayıplı; ortalama net **−0,082R**.
- SOL: 80 erken uyarı, 34 sonuçlanmış varsayımsal işlem, 20 kayıplı; ortalama net **+0,058R**.

Bu getiriler **gerçek emir sonucu veya kanıtlanmış strateji kârlılığı değildir**. 9 bps/yön varsayımsal maliyet uygulanır, funding, piyasa derinliği, likidasyon, gerçek gecikme ve emir dolum kalitesi eksiktir. 28 Ekim rekonstrüksiyonu Binance'in resmî kline dosyasının yerine geçen işlem bazlı türetmedir; orijinal günlük kline yayımlanırsa iki veri mutlaka karşılaştırılmalıdır.

## Dosyaları yeniden kullanma

Başarılı run içindeki **`btc-sol-official-binance-verified-through-2026-11-02`** GitHub artifact'inde 1H, 4H, 1D JSON geçmişleri, `provenance_manifest.json`, paper backtest ve hata sınıflama raporları bulunuyor. Artifact saklama süresi **90 gün**, kalıcı olarak büyük veri dosyaları GitHub main dalına yazılmadı. Kurtarma/validasyon kodu ve sabit Coinalyze doğrulama referansı deneysel dalda tutuluyor.

**Canlı main dalı, Cloudflare Worker, 1H önemli olay bildirimleri, 4H/Daily analiz görevleri ve canlı analiz metodu değiştirilmedi.**

Geleceğe dönük arşiv artımı veya otomatik günlük backfill burada kurulmadı; bu geçiş 2 Kasım 2026 UTC gün sonuna kadar yapılan tek seferlik verifikasyondur.
