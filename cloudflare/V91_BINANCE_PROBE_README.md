# V9.1 Binance Futures bağımsız canlı veri bağlantı testi

**Şu anki durum (11 Kasım 2026):** Salt-okunur Cloudflare Worker kaynağı hazırlanmıştır; henüz Cloudflare'a dağıtılmamış ve gerçek bağlantı testi yapılmamıştır. Mevcut Cloudflare `btc-sol-futures-test` Worker'ı, V7/V9.1 sinyalleri, borsa emirleri ve kullanıcı bildirimleri değiştirilmedi.

## Neyi test eder?

Yeni Worker yalnızca `GET /probe` isteğinde resmî Binance **USD-M perpetual** herkese açık REST `https://fapi.binance.com/fapi/v1/klines` kaynağına BTCUSDT, ETHUSDT ve SOLUSDT için `1h` sorgusu gönderir. İşlem açma, Binance API anahtarı, hesap verisi veya emir API'si yoktur.

Son **tamamlanmış UTC 1H** mumunu, OHLCV, resmî işlem sayısı `n`, taker alış hacmi ve zaman damgasını denetler. Oluşmakta olan mumu reddeder.

- `successAllThree=true`: Cloudflare dağıtılmış Worker'ının üç sembol için resmî *kapanmış 1H* mumuna eriştiği kanıtı. **Coinalyze eşleşmesi henüz kanıtlanmış olmaz.**
- `PUBLIC_BINANCE_RESTRICTED_HTTP_451`: erişim engeli; tekrardan farklı aracıyla erişimin hukuken mümkün olduğunu varsaymayın.
- `PUBLIC_BINANCE_TRANSPORT_OR_VALIDATION_FAILED`: ağ/veri uyumu/zamanlama sorunu; bu veriyle sinyal üretmeyin.

## Kurulum (manuel kullanıcı onayı gerekir)

1. Cloudflare Dashboard → **Workers & Pages → Create Worker** içinde **yeni ve ayrı** bir araştırma Worker'ı oluşturun; mevcut çalışan Worker'ı değiştirmeyin.
2. GitHub'daki [v91-binance-official-probe.js](v91-binance-official-probe.js) kaynak kodunu bu ayrı Worker'a ekleyip yayımlayın.
3. Worker'a **Cloudflare Access veya rate limiting** koruması koyun; kamuya açık, sınırsız çağrılan bir Binance proxy'si olarak bırakmayın.
4. Korunmuş yeni endpoint'in `/probe` yolunu açın ve yalnızca dönen JSON durumlarını inceleyin. API anahtarı/şifre mesaj veya query string içine koymayın.
5. Gözlenen HTTP durumuna göre yeni, tamamen ayrı bir Binance kapanmış mum karşılaştırma akışı kurulabilir. Resmî Binance ile Coinalyze aynı sözleşme ve UTC saatinde gerçekten uyuşmadan canlı doğrulama iddiası yapılmaz.

**Neden GitHub Actions üzerinde doğrudan değil?** Ayrı yapılan GitHub runner resmî Binance REST denemesinde BTC/ETH/SOL için 451 alınmıştır. Bu nedenle Cloudflare'ın kendi çalışma ortamının erişimi ayrıca doğrulanmalıdır. Coğrafi/politika kısıtlamaları varsa bunları aşan alternatif yol otomatik olarak önerilmez.

**WebSocket:** Resmî 2026 USD-M market stream URL'si `wss://fstream.binance.com/market/stream?streams=btcusdt@kline_1h/ethusdt@kline_1h/solusdt@kline_1h` gibi market path mimarisi kullanır. REST'e erişim başarısızsa WebSocket'in çalıştığı varsayılmaz. Kalıcı WebSocket ve 1H/4H/Daily kayıt altyapısı ancak erişim ve gerçek kaynak doğrulaması başarılı olunca ayrı kurulur.

Kod testleri: `node --test tests/test-v91-binance-official-probe.mjs`

**Kritik sınırlar:** Bu bir veri bağlantısı testidir; canlı veri toplama, sabit zamanlı kalıcı saklama veya V9.1'in kârlılığını artırdığı henüz kanıtlanmış değildir.
