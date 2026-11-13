# V9.2 — Bağımsız 10/20 USDT risk limitli ileriye dönük paper hesabı

**Yalnız sanal/araştırma hesabı. Gerçek emir, kullanıcı bildirimi, otomatik V7 iptali veya strateji değiştirme YOK.**

- **Başlangıç sanal sermaye:** 1.000 USDT (BTC, ETH, SOL için ortak)
- **Risk sınırı:** işlem başına toplam 10 USDT; eşzamanlı toplam 20 USDT. Hesaplanan rezerv, stop mesafesine ek olarak 25 bps/yön toplam varsayımsal giriş+çıkış maliyetini içerir.
- **İşleme giriş:** yalnızca V9.2'nin onaylı kapanmış 1H BOS/retest bekleyen girişinden hareketle, o sinyalin ayrı Git commit'inde önceden kaydedilmesi ve sonraki doğrulanmış saatte özgün V9.2 pozisyonunun halen açık olduğunun kontrolü sonrasında yapılır.
- **Paper fiyatı:** sinyalin mühürlendiği saatten sonraki doğrulanmış 1H mumunun **kapanış fiyatı**. Bu fiyatı iş akışı geç görür; gerçek zamanda uygulanabilir işlem fiyatı veya gerçekleşmiş emir değildir. Pozisyonun stop/TP sonuçları ancak **daha sonraki** kapanmış 1H mumlarıyla hesaplanır.
- **Çıkış:** 1H OHLCV; aynı mumda stop ve hedef görüldüğünde **önce stop**; TP1/TP2/TP3, 24 bar zaman aşımı. 9 ve 25 bps/yön sonuçları ayrı takip edilir.
- **Koruma:** 0.1%-4% dışında stop genişliği; yanlış tarafta/eksik stop; eski veya kayıp mum; V7/V9.1/V9.2 eşleşmesi olmaması; önceki Git commit'inin eksik olması; V9.2 kaynak pozisyonunun sonradan kapanması/değişmesi; eşzamanlı risk veya notional üst sınırı = **işlem reddi**.
- **Eksik saat / açık pozisyon:** ara mum eksikse olası stop ve TP sıralaması bilinemez. Açık paper işlem **dondurulur** ve sonuç uydurulmaz; otomatik hesap düzeltmesi yoktur.
- **Başlangıç sınırı:** **2026-11-13 03:00 UTC** (06:00 Türkiye saati) kapanışı veya bundan sonraki ilk üçlü doğrulanmış saat. **Daha eski hiçbir kapanışa giriş ya da PnL yazılmaz.**
- **Geçmiş hesap:** eski V9.2 100 USDT/işlem hesabı ve V7, V9.1 arşiv/sinyalleri aynen devam eder. Bu yeni defter ayrı ve bağımsızdır.
- **Kalan sınırlar:** hesaplanan 10/20 USDT hedef rezerv gerçek stop kayması veya likidasyon riskine üst sınır garantisi vermez; değişken spread, funding ve gerçek emir gerçekleşmeleri doğrulanmamıştır.

Zamanlanmış çalışmanın adı: `V9.2 capped 10-20 USDT independent forward paper (NO ORDERS NO ALERTS)`.

İlk doğrulanmış yeni saat işlendiğinde `forward/v92_capped_paper/latest.md`, `latest.json` ve `hourly/<hour>.json` oluşur. Bir GitHub Actions çalışmasının **başarılı bitmesi tek başına yeni fiyat verisinin ya da sanal işlemin oluştuğu anlamına gelmez**: `CAPPED_NEW_HOUR_PERSISTED_ON_RESEARCH_ONLY` veya yeni snapshot dosyası kontrol edilmelidir.
