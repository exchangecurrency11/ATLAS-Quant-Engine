# V7 Paper-Test Sonuçları — 3 Kasım 2026

**Çalışma:** [V7 GitHub Actions #41673983963](https://github.com/exchangecurrency11/BTC-SOL-ANALYS-S/actions/runs/41673983963) — success (unit tests + verified historical archive download + 3 full chronological replays).
**Arşiv:** [resmî Binance/USD-M geçmişi + 28 Ekim ham-trade rekonstrüksiyonu](https://github.com/exchangecurrency11/BTC-SOL-ANALYS-S/blob/experiment/early-signals-v1-20261022/DATA_ARCHIVE_STATUS_2026-11-03.md).
**Tam sonuç JSON artifact:** `v7-paper-quality-report` (#13248344084, Actions run içinden indirilebilir).
**İşlem yapılmadı, canlı sistem değişmedi.**

## Karşılaştırma — geçmiş varsayımsal işlemler

| Parite | Metot | Uyarı | Kapanmış paper işlem | Kazanan | Win rate | Ort. net R (9bp/yön) | R-kâr faktörü | Sıralı max DD (R) |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| BTC | V4 baseline | 62 | 18 | 7 | %38,89 | −0,0820 | 0,877 | 6,508 |
| BTC | V7 BOS kalitesi | 26 | 9 | 5 | %55,56 | +0,4071 | 1,969 | 3,551 |
| BTC | V7 BOS + güçlü retest | 26 | 8 | 3 | %37,50 | +0,0319 | 1,052 | 4,673 |
| SOL | V4 baseline | 80 | 34 | 14 | %41,18 | +0,0579 | 1,108 | 6,697 |
| SOL | V7 BOS kalitesi | 33 | 14 | 7 | %50,00 | +0,1610 | 1,291 | 2,576 |
| SOL | V7 BOS + güçlü retest | 34 | 14 | 6 | %42,86 | +0,0284 | 1,045 | 2,576 |

**Önemli:** V7 simülasyonu V4 ile **aynı emir/stop/kapanış varsayımlarını** kullanarak baştan oynatıldı. V7'de sinyal sayısı, bazı sinyallerin reddedilmesiyle fırsat sıralaması değiştiği için eski uyarı kümesinden geçen sayıya birebir eşit olmak zorunda değil. Eski uyarıların statik teşhisinde üç kalite filtresini birlikte geçenler BTC 25/62, SOL 33/80 idi; bu bir işlem backtesti değildir.

## Sıkı maliyet stresine duyarlılık — sadece yeniden fiyatlama

Mevcut kapanmış paper işlemleri değiştirmeden, yön başına 9bp yerine
**25bp** maliyet varsayılırsa yaklaşık net ortalama:

| Parite | V4 | V7 BOS kalitesi | V7 BOS + retest |
|---|---:|---:|---:|
| BTC | −0,419R | +0,148R | −0,199R |
| SOL | −0,175R | −0,077R | −0,213R |

Bu **yeni bir işlem yürütme simülasyonu değildir**; mevcut paper işlemlerin varsayımsal maliyetle yeniden fiyatlanmasıdır. Funding, gapping, gerçek fill, likidasyon ve order-book yoktur. Sıralı R-drawdown **hesap-sermaye drawdown'ı değildir**.

## Dönem dağılımı / istikrarsızlık

V7 BOS kalite filtresi:
- BTC 2025: 5 işlem, ort. −0,323R; 2026 Ocak–Haziran: 4 işlem, ort. +1,320R; 2026 Temmuz–Kasım: 0 işlem.
- SOL 2025: 8 işlem, ort. −0,132R; 2026 Ocak–Haziran: 3 işlem, ort. +1,306R; 2026 Temmuz–2 Kasım: 3 işlem, ort. −0,202R.

**Sonuç:** Örneklem dönemlere ayrıldığında iyileşme istikrarlı görünmüyor. Hem BTC hem SOL'da 30 bağımsız kapanmış V7 işlemi bile yok. Veriler eskiden de incelenmiş olduğundan bundan gerçek, untouched out-of-sample performansı çıkarılamaz. Önceden seçilmiş eşikleri bu geçmişe göre yeniden ayarlamak uygun olmaz.

## Karar — 3 Kasım

1. **Korunacak / araştırılacak:** ATR kırılım gücü + son 20 saate göre hacim + EMA20 aşırı uzama filtresi, yalnız ayrı V7 deneyinde. Eski sistemden ana sisteme veya canlı uyarılara geçirmeyeceğiz.
2. **Şimdilik reddedilen ilave kural:** Retest kapanışının 0,10 ATR öteye geçmesi. Bu örneklemde sonuçlar geriledi; mevcut V4'ün zaten ayrı kapanmış mum gerektiren retest mantığı korunuyor.
3. **Canlıya geçiş için engel:** küçük örneklem; SOL'un stres maliyetli net R değeri negatif; gelecekte hiç görülmemiş ileri dönem testleri yok; funding/gerçek fill modellenmedi.
4. **Sonraki teknik iş:** Filtreyi yalnız **paper-forward** modunda yeni kapanışlarla arşivleme ve yeni, bağımsız örneklerde tek tek analiz. Bu rapor kendi kendine zamanlanmış yeni görev oluşturmaz.
