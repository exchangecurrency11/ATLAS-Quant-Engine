# Ayrı V7 ve V9.1 paper hesapları — yalnız ileriye dönük

**GERÇEK EMİR YOK.** 9 baz puan/yan maliyetli kaynak net-R sanal hesaba aktarılır. Girişler gerçek emir gerçekleşmesi değildir.
Başlangıç UTC: 2026-11-12T08:44:55Z
İlk uygun 1H kapanışı UTC: 2026-11-12T09:00:00Z

| Hesap | Kapanan paper işlem | Kazanma % | Net R | Sanal PnL USDT | Sanal bakiye USDT |
|---|---:|---:|---:|---:|---:|
| V7_ORIGINAL | 0 | None | 0 | 0.0 | 1000.0 |
| V91_RETEST_MAX4H | 0 | None | 0 | 0.0 | 1000.0 |

**Son giriş/sinyal durumları (BOS izleme, retest ve açık varsayımsal pozisyon eşiklerine göre):**

- V7_ORIGINAL BTCUSDT: NO_ELIGIBLE_CAPTURE_AFTER_START — en son doğrulanmış 1H yok.
- V7_ORIGINAL SOLUSDT: NO_ELIGIBLE_CAPTURE_AFTER_START — en son doğrulanmış 1H yok.
- V7_ORIGINAL ETHUSDT: NO_ELIGIBLE_CAPTURE_AFTER_START — en son doğrulanmış 1H yok.
- V91_RETEST_MAX4H BTCUSDT: NO_ELIGIBLE_CAPTURE_AFTER_START — en son doğrulanmış 1H yok.
- V91_RETEST_MAX4H SOLUSDT: NO_ELIGIBLE_CAPTURE_AFTER_START — en son doğrulanmış 1H yok.
- V91_RETEST_MAX4H ETHUSDT: NO_ELIGIBLE_CAPTURE_AFTER_START — en son doğrulanmış 1H yok.

V9 önceden dondurulan 4H renk tahminleri ayrıca değerlendirilir, V9.1 işleme giriş sinyali sayılmaz.
Önceki geceye sonradan emir yazılmaz; 1H eksikleri kapatılmaz.
ETH sadece V7 ile birebir doğrulanan gerçek ileriye dönük ETH V9.1 kayıtları geldikten sonra dahil edilir.
Sanal hesaplar her işlem için sabit 100.0 USDT hedef risk kullanır (başlangıç bakiyesinin %10.0'u). %10 çok yüksek risktir. Stop kayması ve kaldıraç nedeniyle gerçek zarar daha yüksek olabilir.
Fonlama, likidasyon, gerçek spread ve uygulanabilir fill garanti edilmez.
