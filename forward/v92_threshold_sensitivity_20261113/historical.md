# V9.2 eşik duyarlılığı — tarihsel araştırma

**Üretim, emirler, sanal hesaplar ve bildirimler değiştirilmedi.**
32 yapılandırma; 159 resmî Binance SHA256 doğrulamalı arşiv; iki dönem de önceden görülmüştür.
RSI LONG>eşik, SHORT<(100-eşik); MACD eşiği hist/EMA20 bps; diğer eşikler tek tek değiştirilir.
9 ve 25bps/yön maliyet; her coin, yön ve kapanmış-gün rejimi için JSON'da detay var.

| Coin | Eşik ailesi | İlk dönem en yüksek ΔR25 (sadece keşif) | Sonraki dönem ΔR25 | İlk/son yeni işlem |
|---|---|---:|---:|---:|
| BTC | volume_surge_pct=40 | +1.390 | +0.000 | 0/0 |
| BTC | rsi_long_cutoff=46 | +0.000 | +0.000 | 0/0 |
| BTC | macd_hist_ema_bps=3 | +3.739 | +0.392 | 0/0 |
| BTC | rvol20_min=1.4 | +0.000 | +0.000 | 0/0 |
| BTC | bos_break_atr_min=0.1 | -0.166 | +0.838 | 1/2 |
| BTC | ema_distance_atr_max=1.5 | +7.701 | -2.815 | 0/0 |
| BTC | retest_hours=2 | +5.211 | -1.342 | 0/0 |
| ETH | volume_surge_pct=50 | +0.477 | +0.000 | 0/0 |
| ETH | rsi_long_cutoff=46 | +0.000 | +0.000 | 0/0 |
| ETH | macd_hist_ema_bps=0.5 | +1.279 | +0.000 | 0/0 |
| ETH | rvol20_min=1.4 | +0.000 | +0.000 | 0/0 |
| ETH | bos_break_atr_min=0 | +0.275 | +1.566 | 5/4 |
| ETH | ema_distance_atr_max=1.5 | +2.839 | +4.109 | 0/0 |
| ETH | retest_hours=5 | +1.293 | +0.000 | 1/0 |
| SOL | volume_surge_pct=0 | +0.000 | -0.647 | 0/1 |
| SOL | rsi_long_cutoff=46 | +0.000 | +0.000 | 0/0 |
| SOL | macd_hist_ema_bps=0.5 | +1.775 | +0.000 | 0/0 |
| SOL | rvol20_min=1.0 | +3.477 | +0.000 | 2/0 |
| SOL | bos_break_atr_min=0.4 | +3.908 | -0.536 | 0/0 |
| SOL | ema_distance_atr_max=2.0 | +0.494 | -0.679 | 0/0 |
| SOL | retest_hours=3 | +0.947 | -2.859 | 0/0 |

**Uyarı:** Erken döneme göre 'en yüksek' geçmiş kâr, sağlam geleceğe dönük avantaj değildir.
Bootstrap tanımlayıcıdır; çoklu tarama düzeltmesi veya gerçek bağımsız test değildir.
Gelecekteki kağıt izleme olmadan V9.3'e otomatik geçiş yapılmaz.

