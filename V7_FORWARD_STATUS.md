# V7 Paper-Forward Test — Başlangıç ve İzleme

## 5 Kasım 2026 — V7 gözlem sürekliliği iyileştirmesi

- **Başlangıç verileri:** 3 Kasım 16:00 UTC ilk gözleminden sonra, 4 Kasım 22:00 UTC kapanışına kadar GitHub deney dalında toplam 9 doğrulanmış saatlik V7 snapshot'ı bulundu. Kontrol edilen son iki kapanış (4 Kasım 21:00 ve 22:00 UTC) doğrulandı; BTC/SOL için o anlarda yeni V7 uyarısı çıkmadı.
- **Yeni saatlik çalışma:** Sadece `main/.github/workflows/v7-hourly-trigger.yml` güncellendi: UTC dakika 17, 35 ve 50'de ayrı çalışma fırsatları var. GitHub'ın saatlik tetikleme gecikmeleri / atlanan çalışmaları tamamen ortadan kaldırmak garanti edilemez.
- **Eksik saat dökümü:** `v7_coverage.py` geçmiş her saatte `forward/snapshots/` altında gerçek zamanında kaydedilmiş snapshot var mı diye bakar. Eksikse **ayrı** `forward/coverage/YYYY-MM-DDTHH-00Z.json` dosyasına `MISSED_OBSERVATION` yazar. Bu durum **sıfır sinyal değildir, işlem değildir ve geçmişi yeniden analiz etmek değildir**. Nedenin kesin olarak bilinmediği açıkça yazılır.
- **Güncel özet:** `forward/coverage/latest.json` kaç saatin doğrulandığını, veri hatasıyla bittiğini ve kaçının kaçırıldığını sayar. Özetin kapsadığı dönem `upToExcludingUTC` alanıyla sınırlıdır; o anda devam eden saat hesaba katılmaz.
- **İdempotent kayıt:** Aynı saatin gerçek snapshot'ı korunur. GitHub'a kalıcı kayıt gönderimi arıza verirse en fazla üç kez denenir.
- **Canlı yatırım sistemi:** Değişmedi. V7 yalnız deneysel gözlem, analiz ve raporlama içindir. Eksik saatleri sahte forward sonuç olarak eklemek yasaktır.

**Doğrulama şartı:** İlk yeni zamanlanmış çalışmanın `forward/coverage/latest.json` dosyasını oluşturması ve aynı kapanışın `forward/snapshots/` ile `forward/reports/` dosyalarını yazması gerekir. Başarılı GitHub job tek başına yeterli değildir. Normal çalışma yoksa sistem eksik gözlem olarak raporlanır.

## 4 Kasım 2026 09:59 TSİ — Otomatik takip sorunu tespit edildi ve iş akışı düzeltildi

**Doğrulanmış durum:** İlk deneysel snapshot 3 Kasım 19:00 TSİ kapanışındadır. 4 Kasım 09:59 TSİ kontrolünde sonraki saatlerin snapshot veya raporu kaydedilmemişti. Saatlik GitHub Actions "tetikleyici" çalışmış, ancak onun `GITHUB_TOKEN` ile deneysel dala attığı commit, `push` temelli ikinci analizi tetiklememiştir. GitHub Actions'ın resmi çalışma kuralı gereği bu zincir kendiliğinden başlamaz.

**Kod düzeltmesi (ana sistemden bağımsız):** `main/.github/workflows/v7-hourly-trigger.yml` tek başına çalışan bir **doğrudan analiz zamanlayıcısı** olarak değiştirildi. Artık deneysel dalı checkout ederek V7 kodunu bizzat çalıştırır, yeni 1H/4H/Daily Coinalyze verilerini ve main fiyat snapshot zamanlarını doğrular, `forward/snapshots/` JSON ile `forward/reports/` Markdown dosyalarını **yalnız deneysel dala** kaydeder. Saatlik tetikleyici dosyası yazıp başka iş akışının başlayacağını varsaymaz. Değiştirilen ana dal dosyası sadece bu V7 iş akışıdır; `market_data.json`, Cloudflare, gerçek alım/satım, 1H/4H ChatGPT görevleri değiştirilmedi.

**Canlı çalışma teyidi henüz yok:** Bu kod güncellemesinin sonraki saatlik zamanlanmış çalışmada gerçekten bir snapshot ürettiğini ayrıca doğrulamak gerekir. `workflow completed/success` tek başına "sinyal analizi yapıldı" kanıtı değildir; `VERIFIED_PAPER_OBSERVATION` durumlu yeni JSON ve açıklamalı Markdown raporu kontrol edilmelidir. Veri hazır değilse DATA_REJECTED / DATA_FETCH_FAILED görünmelidir.

**Kaynak:** https://docs.github.com/en/actions/concepts/security/github_token



## Başladı
**İlk doğrulanmış gözlem:** 2026-11-03 16:00:00 UTC (3 Kasım 19:00 TSİ kapanışı).
**Snapshot:** `forward/snapshots/2026-11-03T16-00Z.json`
**Sistem:** BTCUSDT_PERP.A + SOLUSDT_PERP.A; V4 baseline, V7 BOS filtresi, V7 BOS+güçlü retest varyantları.
**İlk gözlem:** kaynak status `VERIFIED_PAPER_OBSERVATION`; BTC/SOL'da üç varyantın hiçbirinde yeni BOS uyarısı veya yeni sonuçlanan paper işlem yok.

## Zamanlayıcı
ChatGPT planındaki etkin görev limiti (5) nedeniyle yeni ChatGPT görevi oluşturulmadı. Alternatif olarak **yalnız bağımsız saatlik tetikleyici** olan yeni `main/.github/workflows/v7-hourly-trigger.yml` dosyası eklendi. Var olan main kodu, fiyat verisi, Cloudflare ve 1H/4H/Daily analiz iş akışları **değiştirilmedi**. GitHub Actions `schedule: 35 * * * *` UTC (TSİ saat xx:35); saatlik tetikleyici yalnız `experiment/v7-signal-quality-20261103` dalında tekil `forward/triggers/YYYY/MM/DD/HH.json` dosyası oluşturur.

Bu commit, deney dalındaki `.github/workflows/v7-forward-paper.yml` çalışmasını başlatır:
1. Güncel `main/market_data.json` ve Cloudflare `/history?interval=1hour|4hour|daily` (yalnız kapanmış Coinalyze Binance perpetual) verisini yeniden indirir.
2. BTC/SOL 1H + 4H + Daily zamanları, 250 mum bütünlüğü, checkedAt ve fiyat eşleşmesi doğrulanmazsa `DATA_REJECTED` veya `DATA_FETCH_FAILED` kaydeder; **sinyal üretmez**.
3. Doğrulanmış veriyle **önceden sabitlenen** V4 + V7 + V7-retetst metotlarını aynı anlık mumlarda yeniden yürütür. Uyarıyı yalnız o yeni kapanışla teyit edilmişse loglar.
4. Gözlem dosyasını **yalnız deney dalına** `forward/snapshots/YYYY-MM-DDTHH-00Z.json` olarak yazar. Eski snapshot üzerine yazmaya gerek yoktur; her saat ayrı bir dosya.
5. Kullanılan girdileri ve son gözlemi kısa süreli Actions artifact'inde saklar (14 gün).

**GitHub Actions schedule zamanında teslim garantisi vermez.** Gecikmiş yürütmeler xx:25–55 penceresi dışında kalıyorsa tetikleyici o saati atlar; geçmişi sanki canlı takip edilmiş gibi doldurmaz.

## Yorum sınırları
- Bu bir **kağıt üstü gözlem ve simülasyon**; canlı emir, kullanıcıya otomatik işlem tavsiyesi veya gerçekleşmiş getiri değildir.
- Retest mum kapanışı anında izlenir, varsayımsal **sonraki mum açılış fiyatı** ise kapanmış geçmiş bar erişilebilir olduktan sonra kayda girer. Bu nedenle varsayımsal fill daha sonra doğrulanır, gerçek emir verilmiş gibi gösterilmez.
- Funding, emir defteri, değişken spread, gerçek slipaj, gerçekleşme gecikmesi ve likidasyon modellenmez.
- Yeni veriyle yeterli sayıda bağımsız paper işlem görmeden kazanç ihtimali, başarı vaadi veya canlı kullanım kararı yok.
- Değerlendirmede veri kalitesi/atlanan saat sayısı da sayılmalı; yalnız olumlu sinyal saatlerini seçmek yanlılık yaratır.

## İzleme bağlantıları
- [V7 deneysel dalı](https://github.com/exchangecurrency11/BTC-SOL-ANALYS-S/tree/experiment/v7-signal-quality-20261103)
- [İlk snapshot](https://github.com/exchangecurrency11/BTC-SOL-ANALYS-S/blob/experiment/v7-signal-quality-20261103/forward/snapshots/2026-11-03T16-00Z.json)
- [GitHub Actions](https://github.com/exchangecurrency11/BTC-SOL-ANALYS-S/actions)
- [Saatlik tetikleyici (main, bağımsız tek dosya)](https://github.com/exchangecurrency11/BTC-SOL-ANALYS-S/blob/main/.github/workflows/v7-hourly-trigger.yml)

## Devam
Her yeni saat için kayıt ve sinyal sonuçlarını biriktir. Yeni tarihlerde minimum örneklem oluşunca BTC/SOL ayrı ayrı win-rate, net R, maliyet stresi, max sıralı R-drawdown, missing-hour veri kalitesi ve veri dağılımı ile kıyas yap. V7 parametrelerini sonuçlara bakarak değiştirme. Ana sinyal/bildirim metodu bu deneyden otomatik olarak etkilenmez.
