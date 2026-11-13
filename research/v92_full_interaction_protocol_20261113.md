# V9.2 -> V9.3: Araştırma ve ileri sanal izleme protokolü
Dondurma tarihi: 2026-11-13. **Üretime değişiklik YOK.**

## Değiştirilemez işlem mekanizması
- Yalnızca tamamen kapanmış 1H BOS; gözlenmiş, sonradan teyitli 1H retest.
- Retest mumunun BOS seviyesini test etmesi ve doğru yanda kapanması şart.
- Giriş retest kapanışından SONRAKİ 1H açılışında yalnızca varsayımsal.
- BOS/retest fitilinin dışında 0.1 ATR stop; 1R / 2R / 3R eşit parçalar.
- Aynı 1H stop+hedef çakışmasında stop önce; en fazla 24 saat elde tutma.
- HTF trend için yalnızca kapanmış 4H ve Daily barlar; lookahead yasak.
- Gerçek Binance emri ve geçmiş işlemleri üretim sanal hesabına ekleme YOK.

## Envanter: birbirine karıştırılmayacak sınıflar

| Sınıf | Gate | Sabit başlangıç |
|---|---|---|
| sinyal | volume_burst | BOS 1H önceki muma göre en az %20 hacim |
| sinyal | rsi_direction | LONG RSI14>50, SHORT RSI14<50 |
| sinyal | macd_direction | histogram LONG>0, SHORT<0 |
| sinyal | trend4h | 4H yön uyumu |
| sinyal | trend1d | Daily yön uyumu |
| sinyal | bos_break_atr | min 0.20 ATR |
| sinyal | bos_rvol20 | min 1.20 |
| sinyal | bos_ema_extension | max 2.50 ATR |
| SOL'a özel | sol_reversal | Star/Harami + prior20 liquidity sweep/reentry veto |
| retest kalitesi | retest_window | max 4 adet 1H retest saati (V7'nin 6 saati değil) |
| retest kalitesi | retest_color | doğru yöndeki retest mumu |
| retest kalitesi | retest_prev_close | önceki kapanışa göre yön teyidi |
| **risk duyarlılığı, canlıda değiştirme** | risk_min_pct | min %0.1 stop uzaklığı |
| **risk duyarlılığı, canlıda değiştirme** | risk_max_pct | max %4 stop uzaklığı |

14 gate, tam 91 çift = 66 yalnız sinyal/retest + 25 risk duyarlılığı içeren.
SOL dışındaki paritelerde SOL veto içeren kombinasyonlar geçersiz sayılır.
Önceden dondurulmuş üçlü/dörtlüler ayrı incelenir; geriye dönük en iyi kombinasyon "bulunarak" ön kayıt sayılmaz.

## Değişkenler, analizler ve kontrol kapıları

1. Altı orijinal baseline korunur (işlem sayısı + 9/25bps net R), önceki örtüşen varyantların işlem açılış zamanı/yön listesi ve R değerleri birebir eşleşmelidir.
2. Resmî Binance USD-M 1H arşivlerinin her aylık SHA256 toplamı doğrulanır; eksik/gap arşivde başarısız ol.
3. Coinler ve LONG/SHORT bağımsız hesaplanır; yalnızca 1H zamanına kadar kapanmış günlük barlarla boğa/ayı/yatay ve günlük trailing volatility high/low bölümlenir.
4. Referans ve varyant açılış saatleri/yönleri tek tek eşleştirilir: ortak, eklenen, kaybolan, kaçırılan kazanan ve engellenmiş zararlı işlemler; yeni sinyallerin sonraki olasılıkları değiştirerek kronolojik işlemleri engelleyebileceği açıkça not edilir.
5. Net R, PF, kazanma oranı, işlem sayısı ve max DD hem 9 hem 25bps/yön; gerçek fonlama ve değişken spread/slippage yok.
6. 91 çift + eşik gridleri çoklu hipotez taramasıdır. Renkli kazanan tablosu istatistiksel kanıt değil. 3-ay blok bootstrap tanımlayıcıdır, p değeri veya aile düzeyi düzeltilmiş kanıt sayılmaz.
7. İlk incelenen 2022–24 tarihleri ile sonraki 2024–26 tarihleri **ikisi de önceden görülmüştür**, sonraki dönemi gerçek bağımsız holdout diye isimlendirme. Adaylar dondurulmadan yeni dönem test edilmez.

## Karar kuralları (yeniden ayarlama yok)
- Günlük yön filtresi birincil güvenlik/bağlam adayıdır; tarihsel kazanan varyant da olsa tek başına 3/4 filtre kaldırmayla otomatik değiştirilmez.
- Değişim +0.1R/+0.5R gibi tek işlem kaynaklıysa "istatistiksel olarak güçlü" deme.
- Sadece tarihsel iki dönemde de (9bps ve 25bps) referansa karşı pozitif, makul yeni işlem sayılı, drawdown kötüleşmeyen ve ikisinde de yeni kazanan kaybetme maliyeti kabul edilebilir adaylar ileri izlemeye **aday** olabilir; bu bile onay değildir.
- Her aday için konfigürasyon, kod SHA, veri SHA, ilk izleme tarihi ve ölçüm tanımları önceden dondurulur.
- Takip başlangıcı 2026-11-13 sonrasındaki ilk **yeni** tam kapanmış mum; eski veriye geri doldurma ve geçmiş sanal işlem ekleme YOK.
- Aday ve V9.2 baseline aynı piyasa saatlerinde ayrı, korunmuş, yalnızca sanal günlüklerde ilerler. Giriş/stop/TP kuralları aynı; fonlama varsa ayrı tahmini kalem; gerçek emir yok.
- **Ön inceleme kapısı:** en az 180 takvim günü ve karşılaştırma başına en az 20 tamamlanmış yeni aday işlemi; her yönde en az 5, en az iki farklı trend/volatilite durumu. Mevcut strateji çok seyrek sinyal ürettiğinden bu eşiğe ulaşmak yıllar sürebilir; yetersiz veride karar ALMA.
- **Terfi için ek koşullar:** 25bps maliyette olumlu eşleştirilmiş fark, PF>1, max DD referansı anlamlı ölçüde aşmaması, farklı piyasa rejimlerinde tek bir şanslı işlemden ibaret olmayan katkı, ayrıca bootstrap/çoklu test belirsizliğinin dürüst raporu; yalnızca kullanıcının ayrı açık onayıyla V9.3 tasarımı tartışılır.
- Bu protokol izleme otomasyonunu veya canlı sinyal kodunu kurmaz; yalnızca gelecekte dondurulmuş adaylar için güvenli tasarımdır.

## İzlenecek nihai kayıt
Tarih/saat UTC, coin, LONG/SHORT, varyant, kod SHA, kullanılan kapanmış mum zamanları, BOS/retest kanıtı, entry-open UTC ve fiyatı, stop, hedefler, stop-first çözüm, 9/25bps net R, baseline ile ortak/eklenen/kaybolan işaretleri, kapanmış günlük trend/volatilite rejimi, gözlemlenen veri boşluğu ve fonlama/slippage belirsizliği.

**2026-11-13 itibarıyla yeni V9.3 adaylarının hiçbiri canlıya terfi etmemiştir.**
