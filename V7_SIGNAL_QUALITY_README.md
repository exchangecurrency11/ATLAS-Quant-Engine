# V7 — BTC/SOL Yanlış Sinyal Filtresi ve Retest Teyidi (paper-only)

## Kapsam
Bu geliştirme **yalnızca** `experiment/v7-signal-quality-20261103` dalındadır.
`main`, mevcut Cloudflare veri toplayıcısı, 1H/4H/Daily bildirimleri,
borsa hesapları ve emir yolları değiştirilmez. **Canlı LONG/SHORT teyidi değildir.**

Deney dalının tabanı: `experiment/early-signals-v1-20261022`.

## Neyi düzeltmeyi deniyoruz?
Eski V4, 4H+Daily yön uyumu, RSI+MACD, önceki saat hacmine göre
%20 artış ve yeni 1H BOS ile `WATCH` üretir; sonraki 1–6 kapanmış mumda
BOS seviyesi retest + yönlü reaksiyon arar; hipotetik işlem **sonraki
1H mumunun açılışında** başlar.

V7, V4'ün tüm kurallarını koruyarak iki **isteğe bağlı** katman ekler.
Aşağıdaki sayılar tahmin edilen başarı olasılığı değil, test edilecek
başlangıç hipotezleridir. Sonuçlara bakarak eşikleri optimize etmiyoruz.

1. **1H BOS sinyal filtresi** (yalnızca BOS mumu kapandıktan sonra):
   - Yönlü kapanış mesafesi / ATR14 en az **0,20**.
   - BOS mumunun hacmi / **önceki 20 kapanmış 1H** hacminin ortalaması
     en az **1,20**. Önceki tek saate göre artış şartı V4'te hâlâ var.
   - Yönlü fiyat–EMA20 uzaklığı / ATR14 en fazla **2,50**;
     çok uzamış fiyatı kovalamayı azaltma hipotezi.
   - RSI aşırı satım/alım **uyarı**; sert ret kuralı değil.
   - Veri eksik/uyumsuzsa filtre başarısız; gelecek mum kullanılamaz.
2. **Retest teyidi** (BOS'tan sonra ayrı kapanan mumda):
   - V4'ün dokunma + yönlü gövde + önceki kapanışa göre iyileşme şartları.
   - Ek olarak retest kapanışı BOS seviyesinin doğru tarafında en az
     **0,10×ATR14** olmalı; zayıf fitil temaslarını eleme hipotezi.
   - Sonraki açık mumun açılışından önce giriş sayılmaz.

## Adil kıyas: aynı kronolojik simulator
`backtest_retest_long_v4.py` yalnızca **opsiyonel callback** alacak
şekilde bu dalda değiştirildi. Callback verilmezse V4 mantığı
aynı kalır. `v7_paper_comparison.py` aynı arşivle 3 kez FULL
sequential replay çalıştırır:

- `baseline_V4`: geçmiş V4 kuralları
- `V7_signal_gate`: yalnız yeni BOS sinyal filtresi
- `V7_signal_and_retest_gate`: BOS + güçlü retest filtresi

Bu yöntem, engellenen bir sinyal sonrası oluşabilecek sonraki fırsatları
da kronolojik olarak tekrar simüle eder; eski işlemlerden sadece
kazananları seçerek sahte iyileşme hesabı yapmaz.

Eski uyarıların her filtreye takılıp takılmadığını ayıran
`baselineWarningDiagnostics` ise **yalnızca tanımlayıcı analizdir**
ve yeni stratejinin kazanma oranı değildir.

## Veri ve maliyet
Arşiv: 1 Ekim 2024–2 Kasım 2026, sembol başına 18.312 adet kapalı 1H
mumu, Binance resmî USD-M Futures 1H arşivi + 28 Ekim ham-trade
rekonstrüksiyonu. Arşiv ayrı deneyde doğrulandı. 4H ve 1D aynı 1H
mumlarından türetildi. 28 Ekim'in orijinal resmî 1H ZIP'i mevcut değil;
rekonstrüksiyonun provenance bilgisi arşiv artifact'inde bulunur.

Backtestte 1R/2R/3R hedeflere üç eşit kısım, stop öncelikli
belirsiz mum işlemi, en fazla 24 mum taşıma; 6 baz puan ücret
ve 3 baz puan kayma **her yön için varsayımsal**. Funding, emir defteri,
gerçek spread, gerçekleşen fill, gap-through-stop ve likidasyon modellenmez.

Yalnız aynı geçmiş dönemi tekrar test ettiğimiz için bunlar bağımsız
out-of-sample sonuçlar **değil**. Önceki testlerin görüldüğü dönemleri
kalibrasyon sonrası tarafsız holdout diye adlandırmayız. Pozitif sonuç
gelse bile canlıya aktarım için yeni bağımsız dönem / paper forward test
ve maliyet stres testi gerekir.

## Çalıştırma
```bash
python3 -m unittest discover -s tests -p 'test_*.py' -v
python3 v7_paper_comparison.py \
  --hour history/history_1hour.json \
  --four history/history_4hour.json \
  --daily history/history_daily.json \
  --as-of-utc 2026-11-03T00:00:00Z \
  --output v7-paper-comparison.json
```

İzole GitHub Actions CI iş akışı
`.github/workflows/v7-paper-quality.yml`, önceden SHA doğrulanmış
GitHub Actions arşivini indirip test + kıyas yapar. Sonuçları ayrı
`v7-paper-quality-report` artifact'i olarak saklar. **Üretim
otomasyonlarına bağlı değildir.**
