# ETH V9.2 — neden kaybediyor? İşlem bazlı teşhis

**Arşivden türetilmiş yeni tanısal rapor; yeni işlem, yeni backtest veya bağımsız holdout DEĞİLDİR.**
BTC/SOL/ETH V7 ve V9.2 canlı/forward hesaplarına, görevlerine, bildirimlerine hiç dokunulmadı.
159 önceki SHA256 onaylı Binance USD-M aylık dosyasından türetilen, SHA256 ile sabit 9.5 MB tarihsel JSON üzerinde işlem eşleşmesi yapıldı.
Aynı kapanmış 1H BOS → retest → sonraki 1H sanal giriş; 25bps/yön maliyet stresi.
Tüm iki yıllık dönemler önceden incelendi: kazanma yüzdeleri geleceği öngörmez. Wilson aralıkları yalnız tanımlayıcıdır.

## ETH baseline kazanan/kaybeden, maliyet, yön ve çıkış

| Dönem | N | Win% (25bps) | Wilson %95 | Net R25 | LONG N/W/NetR | SHORT N/W/NetR | 9→25bps kazançtan zarara dönüşen |
|---|---:|---:|---|---:|---|---|---:|
| 2022_2024 | 10 | 30.0 | [10.78, 60.32] | -4.497 | 4/1/-0.606 | 6/2/-3.891 | 0 |
| 2024_2026 | 6 | 33.333 | [9.68, 70.0] | -4.109 | 3/1/-3.204 | 3/1/-0.905 | 0 |

## Önceki adaylarla tek tek kronolojik işlem karşılaştırması

Eklenen yeni işlemlerin net sonucu **eksi** kronolojik olarak yer değiştiren referans işlemlerin net sonucu = adayın gerçek tarihsel delta R'si.
Kötü bir işlem atlanınca daha sonra başka işlem oluşabileceği için filtre başarısı yalnız tek işlemden çıkarılamaz.

| Dönem | Aday | Win % (25bps) | N | Net R25 | ΔR25 | Yeni N/W/L ve net R25 | Kaybolan N/W/L ve R25 |
|---|---|---:|---:|---:|---:|---|---|
| 2022_2024 | BASELINE | 30.0 | 10 | -4.497 | +0.000 | 0/0/0, +0.000 | 0/0/0, +0.000 |
| 2022_2024 | NO_BOS_MIN_BREAK_0P20ATR | 35.714 | 14 | -4.222 | +0.275 | 5/3/2, +1.078 | 1/1/0, +0.802 |
| 2022_2024 | NO_BOS_EMA20_MAX_EXTENSION_2P50ATR | 40.0 | 15 | -4.823 | -0.326 | 5/3/2, -0.326 | 0/0/0, +0.000 |
| 2022_2024 | PAIR_NO_BREAK_ATR_AND_EMA_EXT | 47.368 | 19 | -3.165 | +1.332 | 10/7/3, +2.135 | 1/1/0, +0.802 |
| 2022_2024 | PAIR__bos_break_atr__retest_window | 43.75 | 16 | -1.657 | +2.840 | 7/5/2, +3.642 | 1/1/0, +0.802 |
| 2024_2026 | BASELINE | 33.333 | 6 | -4.109 | +0.000 | 0/0/0, +0.000 | 0/0/0, +0.000 |
| 2024_2026 | NO_BOS_MIN_BREAK_0P20ATR | 50.0 | 10 | -2.543 | +1.566 | 4/3/1, +1.566 | 0/0/0, +0.000 |
| 2024_2026 | NO_BOS_EMA20_MAX_EXTENSION_2P50ATR | 53.846 | 13 | +1.482 | +5.591 | 7/5/2, +5.591 | 0/0/0, +0.000 |
| 2024_2026 | PAIR_NO_BREAK_ATR_AND_EMA_EXT | 56.25 | 16 | +1.284 | +5.393 | 10/7/3, +5.393 | 0/0/0, +0.000 |
| 2024_2026 | PAIR__bos_break_atr__retest_window | 45.455 | 11 | -3.172 | +0.937 | 5/3/2, +0.937 | 0/0/0, +0.000 |

## ETH baseline en ağır 5 maliyet-sonrası kayıp (periodik)

| Dönem | Entry UTC | LONG/SHORT | Stop-risk giriş yüzdesi | R9 | R25 | Çıkış nedeni |
|---|---|---|---:|---:|---:|---|
| 2022_2024 | 2024-06-30T05:00:00Z | SHORT | 0.46344% | -1.388 | -2.079 | STOP_FIRST_OR_AFTER_TP |
| 2022_2024 | 2023-05-22T02:00:00Z | SHORT | 0.75999% | -1.237 | -1.658 | STOP_FIRST_OR_AFTER_TP |
| 2022_2024 | 2024-02-01T04:00:00Z | SHORT | 1.31491% | -1.137 | -1.380 | STOP_FIRST_OR_AFTER_TP |
| 2022_2024 | 2022-11-21T20:00:00Z | SHORT | 1.79349% | -1.100 | -1.279 | STOP_FIRST_OR_AFTER_TP |
| 2022_2024 | 2023-06-30T08:00:00Z | LONG | 1.05164% | -0.504 | -0.809 | STOP_FIRST_OR_AFTER_TP |
| 2024_2026 | 2026-09-27T10:00:00Z | LONG | 0.44689% | -1.403 | -2.119 | STOP_FIRST_OR_AFTER_TP |
| 2024_2026 | 2025-05-20T05:00:00Z | LONG | 1.3651% | -1.132 | -1.366 | STOP_FIRST_OR_AFTER_TP |
| 2024_2026 | 2025-04-09T03:00:00Z | SHORT | 3.77866% | -1.048 | -1.132 | STOP_FIRST_OR_AFTER_TP |
| 2024_2026 | 2026-02-02T03:00:00Z | SHORT | 2.91616% | -0.395 | -0.505 | STOP_FIRST_OR_AFTER_TP |
| 2024_2026 | 2026-07-20T18:00:00Z | LONG | 2.21968% | +0.425 | +0.281 | TIME_EXIT_AT_CLOSE |

## Maliyet ve başarım yorumu

- 2022_2024: 10 referans işlem, 3 kazanmış; 25bps net -4.497R, 9bps'de kazançlıyken 25bps'de kayba dönen 0 işlem.
  - Kapanış nedenleri: STOP_FIRST_OR_AFTER_TP=7(-8.48R), TP3_COMPLETE=3(+3.98R).
- 2024_2026: 6 referans işlem, 2 kazanmış; 25bps net -4.109R, 9bps'de kazançlıyken 25bps'de kayba dönen 0 işlem.
  - Kapanış nedenleri: STOP_FIRST_OR_AFTER_TP=4(-5.12R), TIME_EXIT_AT_CLOSE=1(+0.28R), TP3_COMPLETE=1(+0.73R).

## Bulgulardan türeyen sağlam karar protokolü

1. Önceki sonuçlar ETH'deki bazı kaliteli fırsatların BOS/EMA kalite kapılarında kaybedilmiş olabileceğini işaret eder; bu **geriye dönük hipotez**, canlı filtre silme gerekçesi değildir.
2. %55 hedefini ETH için tarihsel en yüksek win-rate ile değil, **dondurulmuş** adayların sonraki gerçek bağımsız işlemlerindeki 25bps maliyet sonrası oranı ve pozitif net R ile ölç.
3. ETH retest/body veya hacim filtresini sonuca bakıp tekrar ayarlama; mevcut 91 çift ve 32 eşik denemesi çoklu test içerir.
4. BOS + EMA gevşetme ve BOS + 6H retest adayları zaten ayrı V9.3 shadow dalında dondurulmuştur. Yeni 6 varyant keşfi veya üretime terfi planlanmadı.
5. Eğer ileri ETH adayları da negatif kalırsa işlem yapmama/ABSTAIN kararı meşru; modelin %55 hedefini tutturmak için işlem sayısını sıfırlaması başarılı sonuç sayılmaz.
6. Üç ay trend/volatilite blok örneklemesi çoklu hipotez düzeltmesi değildir. ETH hatalarını kesin açıklamak için borsa emir/funding/gap/vol ve yeni prospektif işlemler gerekir.
7. BTC/SOL özel motorlarına dokunmadan ETH ayrı analiz edilir; evrensel V9 Core sonuçları ETH özelleştirilmiş filtresiyle karıştırılmaz.

**Kaynak rapor SHA256:** \`9b15781c293eaf38abfd62ea6e087bc9ec35b0df48b8b78fc6f851d971e3d5ab\`

