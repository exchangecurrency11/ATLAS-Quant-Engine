# ETH: Dondurulmuş V9.2 vs BOS+EMA — yeni veri kıyası

**Henüz dondurma sonrası tamamlanmış resmi aylık veri yok. Bu sonuç performans iddiası değildir.**

Ön kayıt: **2026-11-14T00:00:00Z**; en son incelenen veri bitişi: **2026-11-01T00:00:00Z**.
Her iki motor aynı dondurulmuş BOS → retest → sonraki 1H giriş, 1R/2R/3R çıkışlarını ve 9/25 bps/yön maliyet varsayımını kullanır.
Yalnızca watch, retest, giriş ve kapanış saatleri dondurmadan sonra olan işlemler sayılır.

| Metrik | ETH V9.2 referans | ETH BOS+EMA gevşetme |
|---|---:|---:|
| Tamamlanan yeni işlem | 0 | 0 |
| Kazanan | 0 | 0 |
| Win % (25bps) | Yetersiz veri | Yetersiz veri |
| Net R 9bps | +0.000 | +0.000 |
| Net R 25bps | +0.000 | +0.000 |
| PF 25bps | None | None |
| Max DD R25 | 0.000 | 0.000 |

**Eşleştirilen işlemler:** 0 ortak, 0 yalnız aday, 0 yalnız referans.
**Net R25 farkı:** Hesaplanamaz (yeni işlem yok; sıfır gerçek üstünlük sayılmaz).

**Karar:** İleri veri, farklı piyasa rejimleri ve yeterli işlem örneği olmadan canlıya aktarım yok.
İlk inceleme protokolü: en az 180 gün, karşılaştırmada her iki kolda en az 20 yeni kapanmış işlem, her yönde en az 5 ve iki rejim; bu sayılar yeterli istatistiksel kanıt garantisi değildir.
Yüksek win-rate ancak negatif net R başarısız sayılır. Gerçek funding, spread değişkenliği, fill kalitesi ve likidasyon doğrulanmamıştır.

GitHub varsayılan dal, mevcut V7/V9.2 sanal defterleri, otomasyonlar ve bildirimler değiştirilmemiştir.
