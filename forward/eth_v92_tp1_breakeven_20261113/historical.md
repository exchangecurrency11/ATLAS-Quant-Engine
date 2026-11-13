# ETH V9.2 — TP1 sonrası bir sonraki 1H'de başa baş stop

**Ayrı, yalnızca tarihsel ve önceden tanımlı çıkış araştırması. GERÇEK İŞLEM/BAĞIMSIZ HOLDOUT DEĞİLDİR.**
53 Binance ETH resmi aylık SHA256 arşivi, daha önce dondurulmuş veriyle birebir eşleştirildi.
Her varyant tüm BOS/retest durumlarıyla yeniden oynatıldı: aynı girişleri alıp yalnız geçmiş PnL değiştirmek DEĞİL.
İlk TP1 yalnızca kapanmış önceki 1H mumda görüldüyse kalan pozisyon için başa baş koruması sonraki 1H'den itibaren geçerli; aynı mum stop önce.
Bara ters fiyat gap'iyle açılış varsa sanal stop girdi fiyatından değil, gerçekleşebilecek daha kötü AÇILIŞ fiyatından çözülür.
İki dönem de geçmişte incelendi; sonuçlar ileri döneme güvenilir kazanma oranı kanıtı değildir.

| Dönem | ETH giriş filtresi | Exit | N | Win%25 | NetR25 | PF25 | Max DD25 R | BE koruma çıkışı |
|---|---|---|---:|---:|---:|---:|---:|---:|
| 2022_2024 | BASELINE | ORIGINAL | 10 | 30.0 | -4.497 | 0.469447 | 6.199 | 0 |
| 2022_2024 | BASELINE | TP1_NEXT_1H_BREAK_EVEN | 10 | 40.0 | -3.497 | 0.470834 | 5.199 | 4 |
| 2022_2024 | PAIR_NO_BREAK_ATR_AND_EMA_EXT | ORIGINAL | 19 | 47.368 | -3.165 | 0.757307 | 6.512 | 0 |
| 2022_2024 | PAIR_NO_BREAK_ATR_AND_EMA_EXT | TP1_NEXT_1H_BREAK_EVEN | 19 | 47.368 | -3.541 | 0.683656 | 5.606 | 8 |
| 2022_2024 | PAIR__bos_break_atr__retest_window | ORIGINAL | 16 | 43.75 | -1.657 | 0.857187 | 4.961 | 0 |
| 2022_2024 | PAIR__bos_break_atr__retest_window | TP1_NEXT_1H_BREAK_EVEN | 16 | 37.5 | -3.275 | 0.676706 | 4.956 | 6 |
| 2024_2026 | BASELINE | ORIGINAL | 6 | 33.333 | -4.109 | 0.19785 | 4.109 | 0 |
| 2024_2026 | BASELINE | TP1_NEXT_1H_BREAK_EVEN | 6 | 50.0 | -3.442 | 0.254537 | 3.442 | 1 |
| 2024_2026 | PAIR_NO_BREAK_ATR_AND_EMA_EXT | ORIGINAL | 16 | 56.25 | +1.284 | 1.151065 | 3.793 | 0 |
| 2024_2026 | PAIR_NO_BREAK_ATR_AND_EMA_EXT | TP1_NEXT_1H_BREAK_EVEN | 17 | 52.941 | +0.442 | 1.058834 | 3.972 | 5 |
| 2024_2026 | PAIR__bos_break_atr__retest_window | ORIGINAL | 11 | 45.455 | -3.172 | 0.549771 | 4.307 | 0 |
| 2024_2026 | PAIR__bos_break_atr__retest_window | TP1_NEXT_1H_BREAK_EVEN | 11 | 63.636 | -2.300 | 0.610842 | 4.102 | 3 |

## Eşleştirilmiş kronolojik net R farkları

| Dönem | Giriş filtresi | ΔR25 | ΔR9 | Aynı entry | Farklı çıkış | Sonradan eklenen entry | Kaybolan entry |
|---|---|---:|---:|---:|---:|---:|---:|
| 2022_2024 | BASELINE | +1.000 | +1.000 | 10 | 3 | 0 | 0 |
| 2022_2024 | PAIR_NO_BREAK_ATR_AND_EMA_EXT | -0.376 | -0.376 | 19 | 6 | 0 | 0 |
| 2022_2024 | PAIR__bos_break_atr__retest_window | -1.618 | -1.618 | 16 | 5 | 0 | 0 |
| 2024_2026 | BASELINE | +0.667 | +0.667 | 6 | 1 | 0 | 0 |
| 2024_2026 | PAIR_NO_BREAK_ATR_AND_EMA_EXT | -0.842 | -0.599 | 16 | 5 | 1 | 0 |
| 2024_2026 | PAIR__bos_break_atr__retest_window | +0.871 | +0.871 | 11 | 3 | 0 | 0 |

## Nasıl yorumlanmalı?

- TP1 sonrası BE yeni bir **historical research-only** çıkış hipotezidir; geçmiş MFE sonuçlarına bakarak seçildiğinden optimizasyon yanlılığı taşır.
- Başabaş fiyatı, komisyon dahil net başa baş değildir. BE sonrası kalan pozisyon için ücret/slippage ile net zarar mümkün.
- Bir işlem erkenden kapandığında BOS/retest izlemesi ve sıradaki işlem sırası farklılaşabilir; paired ayrım bunu gösterir.
- 25 bps maliyet stresi gerçek borsa dolum, dinamik spread, funding ve stop gap zararlarının tam modeli değildir.
- Sıfır işlem ve birkaç kazanan değişiklik avantaj kanıtı değildir; forward test olmadan üretim/ileti değişmez.
- BTC ve SOL özel motorlarına, evrensel ATLAS Core'a, V7/V9.2 bildirim veya sanal hesaplarına dokunulmadı.

