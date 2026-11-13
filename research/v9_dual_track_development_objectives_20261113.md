# V9 — Çift Hatlı Geliştirme Kararı (13 Kasım 2026)

**Durum:** Stratejik hedef ve araştırma protokolü. Canlı emir, bildirim, V7/V9.2 hesap veya çalışan görev değişikliği değildir.

## A) İşlem motorları — BTC, SOL, ETH (kullanıcının birincil işlem odağı)

- **Amaç:** Her bir sembolün perps sanal işlem stratejisinde, komisyon/slippage/funding ve riski dikkate alarak **gerçek, tekrarlanabilir pozitif net beklenti**; makul bir kazanma oranı ve istikrarlı risk kontrolü.
- **BTC / SOL:** Var olan V9.2 ayrı referans hesapları ve V7 korunur; geçmiş deneylerde işe yarar görünen değişiklikler yalnız yeni yan strateji olarak karşılaştırılır.
- **ETH:** BTC ve SOL için kullanılan aynı ölçüm yöntemleri (tüm filtre ablasyonları, çiftler, eşik duyarlılığı, trend/rejim/volatilite, geçmiş ve ileri çiftli işlem analizi) ETH'ye de uygulanır. ETH özel değişiklikleri evrensel motorun başarısı diye sunulmaz.
- **Birincil performans göstergesi:** Net R beklentisi (9 bp/yön ve 25 bp/yön maliyet stresi), drawdown, profit factor, işlem kapsaması; kazanma oranı ayrıca raporlanır. Yüksek win-rate ama negatif net R başarılı değildir.
- **Değişiklik kuralı:** Her yeni filtre/parametre kombinasyonu testten **önce** kaydedilmeli, bağımsız ileri örneklemle sınanmalı; kazandıran tarihsel sonuçlar kendiliğinden mevcut çalışan hesaba geçirilmez.
- **Hedef:** Uzun dönemde hem daha yüksek hem de tutarlı kazanç oranı / risk-ayarlı net kârlılık. Her iterasyonda oranın artacağına dair bir garanti veya beklenti kurulmaz.

## B) V9 Core — varlık bağımsız genel motor

- **Amaç:** Parametreler sabitken BTC/ETH/SOL dışındaki coinlere, **emtialara** (ör. altın/gümüş) ve **hisselere** taşınabilen bir analiz / sinyal motoru.
- **Hedef eşik:** Gerçekten yeni, kronolojik, maliyetleri dahil edilmiş ve tamamlanmış **paper işlemlerde %55 üzeri kazanma oranı**. Bu eşik araştırma hedefidir; bugün kanıtlanmış başarı veya gelecek için olasılık tahmini **değildir**.
- **Çapraz-varlık genelleme:** Önceden kaydedilmiş eşik ve özellikler her varlığa *aynı şekilde* uygulanır. Bir varlığa bakıp eşik ayarlayıp o varlıktaki sonucu “genel başarı” diye saymak yasaktır. Varlığa özel ayarlar A hattına yazılır.
- **Sınıflar:** (1) coin perpetual; (2) altın/gümüş ve diğer emtia enstrümanları; (3) hisse. Borsaya, işlem seansına, tatil ve açılış gaplerine, temettü/bölünme düzeltmelerine, futures roll/continuous kontrat metoduna, perp funding'e ve sözleşme spesifikasyonlarına uygun veri doğrulama **zorunludur**.
- **Ölçüm:** Her varlık ve sınıf için işlem sayısı, uzun/kısa ayrımı (short izni varsa), win-rate, net R, PF, max DD, rejected signals, maliyet stresi ve veri kapsaması ayrıca gösterilir; yalnız genel toplulaştırılmış oran raporlamak yeterli değildir.
- **Kanıt eşiği:** İlk inceleme için varlık başına en az 100 gerçek yeni kapanmış *bağımsız sanal* işlem ve farklı piyasa rejimleri hedeflenir; istatistiksel belirsizlik aralıkları raporlanır. Az işlemli >%55 oran geçici/kanıtsız diye etiketlenir. Sınıflar arası aktarılabilirlik için her sınıfta bağımsız, hiçbir şekilde eğitimde kullanılmamış dönemler gerekir.
- **Sinyal isabeti ile işlem kazanma oranı ayrımı:** Bir 4H mumunun rengini doğru bilmek, bir işlemden kâr elde etmekle aynı değildir. Her ikisi ayrı metriklerle ölçülür; yalnız trading win-rate >=%55 şartı bir işlem motoru hedefidir.

## Değiştirilmeyecek korumalar

- V7 çalışan görev, bildirim, canlı analiz ve geçmiş sanal kayıtları korunur.
- V9.2 sanal hesap, bildirim, görev ve canlıya bağlı kod korunur.
- V9 Core ve sembole özel geliştirmeler yalnız bağımsız research branch/workflow içinde yürütülür; prod'a merge veya aktivasyon ancak sonradan açık yetkiyle olur.
- Sahte geleceğe-dönük test, daha önce incelenen veriyi "holdout" diye sunma, aynı mumdan geleceği kullanma, işlem kapatılmadan kazanç yazma, geriye dönük paper işlem yaratma yoktur.
- Gerçek borsa emri veya canlı hesap riskine yönelik otomatik eylem yoktur.

## Bir sonraki teknik aşama

1. A hattında BTC/ETH/SOL'un birbiriyle karışmayan ileri sanal işlem defterlerini izlemek ve ETH alternatiflerini ölçmek.
2. B hattında **değişmeden kalan** V9 Core kurallarını ve varlık-bağımsız veri sözleşmesini dondurmak; her enstrümanın veri sınırlarını ve saat dilimlerini doğrulamak.
3. Hem sınıf bazlı hem sembol bazlı net R/başarı kıyas raporu üretmek. >%55 hedefe **gerçek veriyle** ulaşılıp ulaşılmadığını göstermek; ulaşılamıyorsa açıkça kaydetmek.

**Ana ilke:** Gelir odağındaki BTC/SOL/ETH özelleştirmesinin başarısını varlıklar arası V9 Core başarısıyla karıştırma.