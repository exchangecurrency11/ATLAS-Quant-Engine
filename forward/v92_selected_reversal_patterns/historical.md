# V9.2 seçici dönüş mumları / güçlü aday havuzu

**Yalnızca tarihi paper araştırması. Bu formasyonların gelecek başarı oranları kanıtlanmadı.**
SOL: 1H/4H kapanmış Morning/Evening Star veya üçüncü mumla teyitli Harami;
önceki 20 mumun tepe/dip likidite süpürmesi + bölgeye geri kapanış şartıyla
**yalnız ayrı araştırma modelinde** aksi yönlü retest'i engeller.
BTC: Tüm formasyonlar sadece uyarı (önceki testlerde bazı kârlı BTC işlemleri elenmişti).
Hikkake, Engulfing, Three White Soldiers, Three Black Crows: sadece gözlem.

Geçmiş: 2024-10-01T00:00:00Z – 2026-10-01T00:00:00Z (hariç).
1H/4H/Daily resmî, daha önce SHA256 ile doğrulanmış BTC/SOL arşivi.
Maliyet 9 bps/yön, stres 25 bps/yön; fonlama, fiili dolum, zorunlu tasfiye tam modellenmiyor.

| Coin | Sürüm | İşlem | Kazanan | Win % | Net R | Stres R | Baz göre fark R | Retest veto |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| BTCUSDT | V7_ORIGINAL | 9 | 5 | 55.56 | 3.6636 | 1.3290 | — | 0 |
| BTCUSDT | V7_ORIGINAL__OBSERVE_ONLY | 9 | 5 | 55.56 | 3.6636 | 1.3290 | 0.0 | 0 |
| BTCUSDT | V7_ORIGINAL__SELECTED_SOL_STRICT_SWEEP | 9 | 5 | 55.56 | 3.6636 | 1.3290 | 0.0 | 0 |
| BTCUSDT | V7_ORIGINAL__SELECTED_SOL_ANY_CLOSED_PATTERN | 9 | 5 | 55.56 | 3.6636 | 1.3290 | 0.0 | 0 |
| BTCUSDT | V91_RETEST_MAX4H | 5 | 3 | 60.0 | 4.1010 | 2.8146 | — | 0 |
| BTCUSDT | V91_RETEST_MAX4H__OBSERVE_ONLY | 5 | 3 | 60.0 | 4.1010 | 2.8146 | 0.0 | 0 |
| BTCUSDT | V91_RETEST_MAX4H__SELECTED_SOL_STRICT_SWEEP | 5 | 3 | 60.0 | 4.1010 | 2.8146 | 0.0 | 0 |
| BTCUSDT | V91_RETEST_MAX4H__SELECTED_SOL_ANY_CLOSED_PATTERN | 5 | 3 | 60.0 | 4.1010 | 2.8146 | 0.0 | 0 |
| SOLUSDT | V7_ORIGINAL | 11 | 6 | 54.55 | 2.8610 | 0.6026 | — | 0 |
| SOLUSDT | V7_ORIGINAL__OBSERVE_ONLY | 11 | 6 | 54.55 | 2.8610 | 0.6026 | 0.0 | 0 |
| SOLUSDT | V7_ORIGINAL__SELECTED_SOL_STRICT_SWEEP | 10 | 6 | 60.0 | 4.0057 | 2.0046 | 1.144706 | 1 |
| SOLUSDT | V7_ORIGINAL__SELECTED_SOL_ANY_CLOSED_PATTERN | 10 | 6 | 60.0 | 4.0057 | 2.0046 | 1.144706 | 1 |
| SOLUSDT | V91_RETEST_MAX4H | 9 | 5 | 55.56 | 3.1159 | 1.0080 | — | 0 |
| SOLUSDT | V91_RETEST_MAX4H__OBSERVE_ONLY | 9 | 5 | 55.56 | 3.1159 | 1.0080 | 0.0 | 0 |
| SOLUSDT | V91_RETEST_MAX4H__SELECTED_SOL_STRICT_SWEEP | 8 | 5 | 62.5 | 4.2607 | 2.4099 | 1.144707 | 1 |
| SOLUSDT | V91_RETEST_MAX4H__SELECTED_SOL_ANY_CLOSED_PATTERN | 8 | 5 | 62.5 | 4.2607 | 2.4099 | 1.144707 | 1 |

ÖNEMLİ: Hem Morning Star hem Harami aynı tek SOL kayıplı işlemi işaretledi;
bu nedenle bunlar bağımsız iki başarı değildir. Tarihsel seçim yanlılığı yüksek.
Canlıya almadan önce yeterince yeni, aynı anda kaydedilmiş ileri paper işlem
ve farklı piyasa koşullarında kararlı net R üstünlüğü gerekir.
V7/V9.1 orijinal hesapları, ana strateji ve bildirimler değiştirilmedi.

