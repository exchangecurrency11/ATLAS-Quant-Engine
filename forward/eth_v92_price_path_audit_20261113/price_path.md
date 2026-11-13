# ETH V9.2 — 1H fiyat yolu: MFE / MAE ve dar stop riski

**Geçmiş işlemlerin yeni OHLCV incelemesi; yeni backtest/forward sinyal veya gerçek fill değildir.**
Her ETH saatlik Binance USD-M ZIP SHA256 değeri geçmişteki 159 arşivli raporla birebir eşleştirildi.
Yalnız arşivde var olan işlem girişinden çıkışına kadar 1H maksimum lehine/aleyhine hareket ölçüldü.
MFE/MAE işlem girişinde bilinmiyordu; geçmişten filtre seçmek için kullanılamaz.

## Mevcut referans ile önceden belirlenmiş iki ETH adayının fiyat yolu

| Dönem | Motor | İşlem | Zarar eden | Zarar eden ort. MFE R | Zarar eden ort. MAE R | Zarar ettiği halde çıkıştan önce 1R görmüş | Stop ile TP1 aynı son mumda |
|---|---|---:|---:|---:|---:|---:|---:|
| 2022_2024 | BASELINE | 10 | 7 | 0.79118 | 1.89849 | 3 | 1 |
| 2022_2024 | PAIR_NO_BREAK_ATR_AND_EMA_EXT | 19 | 10 | 0.671 | 1.77285 | 3 | 1 |
| 2022_2024 | PAIR__bos_break_atr__retest_window | 16 | 9 | 0.6852 | 1.81879 | 3 | 1 |
| 2024_2026 | BASELINE | 6 | 4 | 0.55102 | 1.19018 | 1 | 0 |
| 2024_2026 | PAIR_NO_BREAK_ATR_AND_EMA_EXT | 16 | 7 | 0.55874 | 1.16978 | 2 | 0 |
| 2024_2026 | PAIR__bos_break_atr__retest_window | 11 | 6 | 0.66063 | 1.16676 | 2 | 0 |

## Mevcut V9.2 başarısız işlemler: ileri bilgiyi işlem sinyali olarak kullanmadan geriye dönük inceleme

| Dönem | Entry UTC | Yön | Net R25 | Hold 1H | Max lehine R | Max aleyhine R | Son 1H stop ve TP1 aynı mumda? |
|---|---|---|---:|---:|---:|---:|---|
| 2022_2024 | 2022-11-21T20:00:00Z | SHORT | -1.279 | 1 | 0.088 | 1.229 | Hayır |
| 2022_2024 | 2023-05-22T02:00:00Z | SHORT | -1.658 | 5 | 0.191 | 1.574 | Hayır |
| 2022_2024 | 2023-06-30T08:00:00Z | LONG | -0.809 | 6 | 1.364 | 3.369 | EVET |
| 2022_2024 | 2024-02-01T04:00:00Z | SHORT | -1.380 | 11 | 0.184 | 1.542 | Hayır |
| 2022_2024 | 2024-03-05T04:00:00Z | LONG | -0.534 | 14 | 1.436 | 1.472 | Hayır |
| 2022_2024 | 2024-03-08T01:00:00Z | LONG | -0.737 | 16 | 1.934 | 1.727 | Hayır |
| 2022_2024 | 2024-06-30T05:00:00Z | SHORT | -2.079 | 3 | 0.341 | 2.377 | Hayır |
| 2024_2026 | 2025-04-09T03:00:00Z | SHORT | -1.132 | 4 | 0.218 | 1.077 | Hayır |
| 2024_2026 | 2025-05-20T05:00:00Z | LONG | -1.366 | 2 | 0.152 | 1.045 | Hayır |
| 2024_2026 | 2026-02-02T03:00:00Z | SHORT | -0.505 | 11 | 1.586 | 1.125 | Hayır |
| 2024_2026 | 2026-09-27T10:00:00Z | LONG | -2.119 | 4 | 0.248 | 1.514 | Hayır |

## Disiplin ve yorum sınırları

- Maksimum lehine hareket, alım-satım motorunun o kârı gerçekleştirdiği anlamına gelmez: fiyat hareketi bir mum içinde stop ile aynı anda gerçekleşmiş olabilir.
- Stop ve hedefin aynı 1H mumunda dokunulması durumunda **önce stop** varsayımı korunur. Mum içindeki gerçek sıra resmi 1H OHLCV'den bilinemez.
- 9 bps ve 25 bps maliyetler simülasyondur; gerçek fonlama/spread/gap/emir dolumu kanıtlanmaz.
- Kaybeden işlemde geçmişte görülen MFE veya başka özellik, giriş zamanında bilinmediği için yeni filtreye sızdırılmamalı.
- 2022–24 ve 2024–26 her ikisi de daha önce incelenmiştir, bağımsız unseen dönem değildir.
- V7/V9.2 üretime, mevcut sanal defterlere veya kullanıcının bildirimlerine hiç dokunulmadı.

**SHA256 ile eşleşen ETH aylık dosya adedi:** 26.

