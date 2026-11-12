# V9.2 Harami + Hikkake + Engulfing + Star sahte kırılım/invalidasyon

**SADECE ESKİ MUM BACKTESTİ; GERÇEK/İLERİ DÖNÜK İŞLEM DEĞİL.**
Geçmiş dönem: 2024-10-01T00:00:00Z – 2026-10-01T00:00:00Z (son tarih hariç).
Harami üç mum teyitli; Hikkake ancak inside-bar sahte kırılımından sonra en geç üç bar içinde teyitli.
V7 ve V9.1 giriş–çıkış ve BOS kuralları korunmuştur.

| Sembol | Sistem | İşlem | Kazanan | Kazanma % | Net R | Stres net R | R farkı | Retest reddi |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| BTCUSDT | V7_ORIGINAL | 9 | 5 | 55.56 | 3.6636 | 1.3290 | — | 0 |
| BTCUSDT | V7_ORIGINAL__HARAMI_CONFIRMED | 9 | 5 | 55.56 | 3.6636 | 1.3290 | 0.0 | 0 |
| BTCUSDT | V7_ORIGINAL__HIKKAKE_CONFIRMED | 8 | 4 | 50.0 | 1.7596 | -0.4044 | -1.904023 | 1 |
| BTCUSDT | V7_ORIGINAL__ENGULFING | 8 | 4 | 50.0 | 1.8106 | -0.2627 | -1.852987 | 1 |
| BTCUSDT | V7_ORIGINAL__ALL_REVERSALS | 7 | 3 | 42.86 | -0.0934 | -1.9961 | -3.757011 | 2 |
| BTCUSDT | V7_ORIGINAL__ALL_REVERSALS_SWEEP_CONTEXT | 8 | 4 | 50.0 | 1.7596 | -0.4044 | -1.904023 | 1 |
| BTCUSDT | V91_RETEST_MAX4H | 5 | 3 | 60.0 | 4.1010 | 2.8146 | — | 0 |
| BTCUSDT | V91_RETEST_MAX4H__HARAMI_CONFIRMED | 5 | 3 | 60.0 | 4.1010 | 2.8146 | 0.0 | 0 |
| BTCUSDT | V91_RETEST_MAX4H__HIKKAKE_CONFIRMED | 4 | 2 | 50.0 | 2.1970 | 1.0812 | -1.904023 | 1 |
| BTCUSDT | V91_RETEST_MAX4H__ENGULFING | 5 | 3 | 60.0 | 4.1010 | 2.8146 | 0.0 | 0 |
| BTCUSDT | V91_RETEST_MAX4H__ALL_REVERSALS | 4 | 2 | 50.0 | 2.1970 | 1.0812 | -1.904023 | 1 |
| BTCUSDT | V91_RETEST_MAX4H__ALL_REVERSALS_SWEEP_CONTEXT | 4 | 2 | 50.0 | 2.1970 | 1.0812 | -1.904023 | 1 |
| SOLUSDT | V7_ORIGINAL | 11 | 6 | 54.55 | 2.8610 | 0.6026 | — | 0 |
| SOLUSDT | V7_ORIGINAL__HARAMI_CONFIRMED | 10 | 6 | 60.0 | 4.0057 | 2.0046 | 1.144706 | 1 |
| SOLUSDT | V7_ORIGINAL__HIKKAKE_CONFIRMED | 10 | 6 | 60.0 | 3.9246 | 1.7792 | 1.063586 | 1 |
| SOLUSDT | V7_ORIGINAL__ENGULFING | 11 | 6 | 54.55 | 2.8610 | 0.6026 | 0.0 | 0 |
| SOLUSDT | V7_ORIGINAL__ALL_REVERSALS | 9 | 6 | 66.67 | 5.0693 | 3.1812 | 2.208292 | 2 |
| SOLUSDT | V7_ORIGINAL__ALL_REVERSALS_SWEEP_CONTEXT | 9 | 6 | 66.67 | 5.0693 | 3.1812 | 2.208292 | 2 |
| SOLUSDT | V91_RETEST_MAX4H | 9 | 5 | 55.56 | 3.1159 | 1.0080 | — | 0 |
| SOLUSDT | V91_RETEST_MAX4H__HARAMI_CONFIRMED | 8 | 5 | 62.5 | 4.2607 | 2.4099 | 1.144707 | 1 |
| SOLUSDT | V91_RETEST_MAX4H__HIKKAKE_CONFIRMED | 9 | 5 | 55.56 | 3.1159 | 1.0080 | 0.0 | 0 |
| SOLUSDT | V91_RETEST_MAX4H__ENGULFING | 9 | 5 | 55.56 | 3.1159 | 1.0080 | 0.0 | 0 |
| SOLUSDT | V91_RETEST_MAX4H__ALL_REVERSALS | 8 | 5 | 62.5 | 4.2607 | 2.4099 | 1.144707 | 1 |
| SOLUSDT | V91_RETEST_MAX4H__ALL_REVERSALS_SWEEP_CONTEXT | 8 | 5 | 62.5 | 4.2607 | 2.4099 | 1.144707 | 1 |

Bu sonuçlar geçmişte incelenmiş dönemdedir; filtreler geçmişte şans eseri bir zarar işlemini elemiş olabilir. Komisyon baz 9bp/yön ve stres 25bp/yön. Gerçek emir dolumu, spread, funding, tasfiye ve gecikme tam modellenmez.
Kârlı işlemleri yanlış eleme riski ayrıca izlenmelidir.
V7, V9.1 ve mevcut 1.000 USDT sanal hesaplar değişmedi.

