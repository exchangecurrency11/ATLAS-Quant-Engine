# V9.1 TradingView bağımsız piyasa yapısı araştırması

**Durum:** Pine Script v6 ve GitHub karşılaştırma/manuel alım kodu hazır; **TradingView hesabı veya otomatik webhook akışı henüz bağlanmadı ve gerçek TradingView alarmı henüz alınmadı.** V7 ve V9.1 paper sistemi değiştirilmedi.

## Kurulum

1. TradingView'de BINANCE:BTCUSDT.P grafiğinde **1H** ve normal mum grafiğini seç (Heikin Ashi ve Renko değil).
2. Pine Editor'a tradingview/v91_independent_1h_audit.pine dosyasının içeriğini tamamen yapıştır, kaydet ve grafiğe ekle. Pine uyarısı çıkarsa bize ilet: GitHub CI Pine'ı TradingView ortamında derlemez.
3. Bir alarm oluştur: **V9.1 TV Independent 1H Structure Audit → Any alert() function call**. Pine her **kapanmış 1H** için 1 JSON gönderir; sinyal olmasa da gönderir. Bir alım-satım emri oluşturma.
4. Aynısını **BINANCE:SOLUSDT.P** için başka bir grafikte yap.
5. Gerçek alarm JSON'unu GitHub Actions altında **V9.1 TradingView manual alert intake vs V7 → Run workflow → tradingview_alert_json** alanına yapıştır. Bu manuel kayıt yapar; TV'nin kendiliğinden GitHub'a veri gönderdiği anlamına gelmez.
6. Gerçek TV verileri geldikçe aynı kapanmış mumun orijinal V7 kaydıyla OHLC, BOS, CHoCH, FVG ve swing sweep işaretlerini karşılaştır.

## Denetim kuralları

- Yalnızca BINANCE:BTCUSDT.P ve BINANCE:SOLUSDT.P, normal 1H OHLC grafikleri.
- Pine sağdan teyit edilen pivotu 3 bar gecikmeyle tanır; V7'nin pivot algoritması birebir aynı değildir. Farklı BOS işaretleri otomatik olarak yanlış sinyal sayılmaz.
- JSON barOpenMs / barCloseMs UTC, 1 saat farkı, OHLCV, ATR, RSI, MACD histogramı, EMA20/50/200 ve yapı işaretlerini içerir.
- Python aynı UTC 1H kapanışında kaydedilmiş, gerçek V7 gözlemiyle eşleştirir; fiyat sapması 1 baz puanı aşarsa fiyat uyumu verilmez.
- El ile sunulan TV JSON'u **kimlik doğrulanmış / zamanında mühürlenmiş otomatik alarm değildir.** Geçmişe dönük yeni paper kazancı veya gerçek işlem kanıtı olarak yazılmaz.
- Canlı emir, V7 filtresi değişikliği veya kullanıcı V9 bildirimi **yoktur**.
- TradingView alarmı için plan sınırları geçerlidir. Webhook kullanmak isteyenlerin 2FA etkinleştirmesi ve güvenli HTTPS alıcısı kurması gerekir. Henüz webhook alıcısı aktif değildir. **API anahtarlarını, GitHub token'ını veya şifreleri alarm JSON'una ekleme.**

## Kaynaklar

TradingView alerts: https://www.tradingview.com/pine-script-docs/concepts/alerts/

TradingView closed candles: https://www.tradingview.com/pine-script-docs/concepts/bar-states/

TradingView webhook security: https://www.tradingview.com/support/solutions/43000529348-how-to-configure-webhook-alerts/

Pine kaynak: tradingview/v91_independent_1h_audit.pine

GitHub analiz kodu: v91_tradingview_compare.py

Manuel GitHub alımı: .github/workflows/v91-tradingview-manual-intake.yml (main dalında)

## Lokal karşılaştırma

Gerçek bir TradingView alarmı tv_alert.json olarak kaydedilmiş ve orijinal V7 gözlemleri v7_evidence/forward/snapshots altında olduğunda:

python3 v91_tradingview_compare.py --tv tv_alert.json --v7 v7_evidence/forward/snapshots --output forward/v91_tradingview_compare/local_manual.json

Bu komut TradingView hesabına bağlanmaz, veri indirmez; yalnızca elindeki gerçek JSON'u analiz eder. Otomatik webhook akışı ayrı araştırma entegrasyonu gerektirir.
