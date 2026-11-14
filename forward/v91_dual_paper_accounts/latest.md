# Ayrı V7 ve V9.1 paper hesapları — yalnız ileriye dönük

**GERÇEK EMİR YOK.** 9 baz puan/yan maliyetli kaynak net-R sanal hesaba aktarılır. Girişler gerçek emir gerçekleşmesi değildir.
Başlangıç UTC: 2026-11-12T08:44:55Z
İlk uygun 1H kapanışı UTC: 2026-11-12T09:00:00Z

| Hesap | Kapanan paper işlem | Kazanma % | Net R | Sanal PnL USDT | Sanal bakiye USDT |
|---|---:|---:|---:|---:|---:|
| V7_ORIGINAL | 0 | None | 0 | 0.0 | 1000.0 |
| V91_RETEST_MAX4H | 0 | None | 0 | 0.0 | 1000.0 |

**Son giriş/sinyal durumları (BOS izleme, retest ve açık varsayımsal pozisyon eşiklerine göre):**

- V7_ORIGINAL BTCUSDT: FLAT_NO_CONFIRMED_TRADE — en son doğrulanmış 1H 2026-11-14T03:00:00Z.
- V7_ORIGINAL SOLUSDT: FLAT_NO_CONFIRMED_TRADE — en son doğrulanmış 1H 2026-11-14T03:00:00Z.
- V7_ORIGINAL ETHUSDT: FLAT_NO_CONFIRMED_TRADE — en son doğrulanmış 1H 2026-11-14T02:00:00Z.
- V91_RETEST_MAX4H BTCUSDT: FLAT_NO_CONFIRMED_TRADE — en son doğrulanmış 1H 2026-11-14T03:00:00Z.
- V91_RETEST_MAX4H SOLUSDT: FLAT_NO_CONFIRMED_TRADE — en son doğrulanmış 1H 2026-11-14T03:00:00Z.
- V91_RETEST_MAX4H ETHUSDT: FLAT_NO_CONFIRMED_TRADE — en son doğrulanmış 1H 2026-11-14T02:00:00Z.

**Kaynak saat kapsama denetimi (eksikler doldurulmaz):**

- BTC_SOL: 42/43 saat; eksik 1; son kayıt 2026-11-14T03:00:00Z; gecikme 0 saat.
- ETH: 39/43 saat; eksik 4; son kayıt 2026-11-14T02:00:00Z; gecikme 1 saat.

V9 önceden dondurulan 4H renk tahminleri ayrıca değerlendirilir, V9.1 işleme giriş sinyali sayılmaz.
Önceki geceye sonradan emir yazılmaz; 1H eksikleri kapatılmaz.
ETH sadece V7 ile birebir doğrulanan gerçek ileriye dönük ETH V9.1 kayıtları geldikten sonra dahil edilir.
Sanal hesaplar her işlem için sabit 100.0 USDT hedef risk kullanır (başlangıç bakiyesinin %10.0'u). %10 çok yüksek risktir. Stop kayması ve kaldıraç nedeniyle gerçek zarar daha yüksek olabilir.
Fonlama, likidasyon, gerçek spread ve uygulanabilir fill garanti edilmez.
