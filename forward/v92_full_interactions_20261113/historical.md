# V9.2 tüm ikili filtre etkileşimleri (13 Kasım 2026)

**Yalnızca tarihsel araştırma. V7, V9.2 üretim, sanal hesap ve bildirimler değiştirilmedi.**
159 Binance USD-M arşivi SHA256; altı baseline ve önceki örtüşen senaryolarla işlem/R eşleşmesi.
91 çift: 66 saf sinyal, 25 risk duyarlılığı; 4 önkayıtlı üçlü, 2 dörtlü.
2022–24 ve 2024–26 daha önce görülmüş veridir: bağımsız holdout değildir.

## Referans V9.2

| Dönem | Coin | N | Net R9 | Net R25 | DD25 R | PF25 |
|---|---|---:|---:|---:|---:|---:|
| 2022_2024 | BTC | 10 | -4.266 | -7.701 | 7.701 | 0.31704 |
| 2022_2024 | ETH | 10 | -0.979 | -4.497 | 6.199 | 0.469447 |
| 2022_2024 | SOL | 12 | +4.627 | +2.004 | 3.055 | 1.322837 |
| 2024_2026 | BTC | 5 | +4.101 | +2.815 | 1.639 | 2.433165 |
| 2024_2026 | ETH | 6 | -2.008 | -4.109 | 4.109 | 0.19785 |
| 2024_2026 | SOL | 8 | +4.261 | +2.410 | 1.353 | 1.627244 |

## Çiftlerin ve önkayıtlı kombinasyonların ilk döneme göre sıralaması

Yalnızca sıralama ilk dönemden. Sonraki dönem geçmişte incelenmiş olduğundan gerçek OOS sayılmaz.

| Coin | Kombinasyon | İlk ΔR25 | Son ΔR25 | Yeni işlem (ilk/son) | Kaçırılan kazanan (ilk/son) |
|---|---|---:|---:|---:|---:|
| BTC | PAIR__bos_ema_extension__macd_direction | +4.985 | -14.543 | 10/11 | 0/0 |
| BTC | PAIR_NO_RSI_AND_MACD | +4.928 | -11.263 | 4/7 | 0/0 |
| BTC | PAIR__macd_direction__retest_color | +4.928 | -11.263 | 4/7 | 0/0 |
| BTC | PAIR__macd_direction__retest_prev_close | +4.928 | -11.263 | 4/7 | 0/0 |
| BTC | PAIR__macd_direction__risk_max_pct | +4.928 | -11.263 | 4/7 | 0/0 |
| BTC | PAIR__macd_direction__volume_burst | +3.776 | -10.780 | 5/10 | 0/0 |
| BTC | PAIR__macd_direction__retest_window | +3.712 | -12.748 | 5/11 | 0/0 |
| BTC | QUAD__bos_break_atr__bos_ema_extension__macd_direction__rsi_direction | +2.663 | -20.358 | 14/17 | 0/0 |
| BTC | PAIR__bos_break_atr__macd_direction | +2.606 | -17.077 | 8/13 | 0/0 |
| BTC | PAIR__bos_ema_extension__risk_max_pct | +1.106 | -2.880 | 6/2 | 0/0 |
| BTC | PAIR__retest_color__retest_prev_close | +0.903 | -2.456 | 4/5 | 0/1 |
| BTC | PAIR__bos_ema_extension__retest_color | +0.547 | -2.880 | 5/2 | 0/0 |
| BTC | PAIR__bos_ema_extension__retest_prev_close | +0.547 | -2.880 | 5/2 | 0/0 |
| BTC | PAIR__bos_ema_extension__retest_window | +0.547 | -4.366 | 5/6 | 0/0 |
| BTC | PAIR__bos_ema_extension__rsi_direction | +0.547 | -2.880 | 5/2 | 0/0 |
| BTC | PAIR__retest_color__retest_window | +0.000 | -1.486 | 0/4 | 0/0 |
| BTC | PAIR__retest_color__risk_max_pct | +0.000 | +0.000 | 0/0 | 0/0 |
| BTC | PAIR__retest_color__rsi_direction | +0.000 | +0.000 | 0/0 | 0/0 |
| BTC | PAIR__retest_prev_close__retest_window | +0.000 | -1.486 | 0/4 | 0/0 |
| BTC | PAIR__retest_prev_close__risk_max_pct | +0.000 | +0.000 | 0/0 | 0/0 |
| BTC | PAIR__retest_prev_close__rsi_direction | +0.000 | +0.000 | 0/0 | 0/0 |
| BTC | PAIR__retest_window__risk_max_pct | +0.000 | -1.486 | 0/4 | 0/0 |
| BTC | PAIR__retest_window__rsi_direction | +0.000 | -1.486 | 0/4 | 0/0 |
| BTC | PAIR__risk_max_pct__rsi_direction | +0.000 | +0.000 | 0/0 | 0/0 |
| BTC | PAIR_NO_BREAK_ATR_AND_EMA_EXT | -0.379 | -5.640 | 8/6 | 0/0 |

BTCUSDT: tamamı (84 kombinasyon) ve her işlem/regim JSON'da yer alır.

| ETH | PAIR__bos_break_atr__retest_window | +2.840 | +0.937 | 7/5 | 1/0 |
| ETH | TRIPLE__bos_break_atr__bos_ema_extension__volume_burst | +1.935 | +0.041 | 13/15 | 1/0 |
| ETH | PAIR__retest_window__volume_burst | +1.449 | -2.285 | 4/3 | 0/0 |
| ETH | PAIR_NO_BREAK_ATR_AND_EMA_EXT | +1.332 | +5.393 | 10/10 | 1/0 |
| ETH | TRIPLE__bos_break_atr__bos_ema_extension__rsi_direction | +1.332 | +5.393 | 10/10 | 1/0 |
| ETH | PAIR__retest_color__retest_window | +1.293 | -0.629 | 1/1 | 0/0 |
| ETH | PAIR__retest_prev_close__retest_window | +1.293 | -0.629 | 1/1 | 0/0 |
| ETH | PAIR__retest_window__risk_max_pct | +1.293 | -0.749 | 1/2 | 0/0 |
| ETH | PAIR__retest_window__risk_min_pct | +1.293 | -0.629 | 1/1 | 0/0 |
| ETH | PAIR__retest_window__rsi_direction | +1.293 | -0.629 | 1/1 | 0/0 |
| ETH | PAIR__bos_break_atr__volume_burst | +0.878 | -3.787 | 8/9 | 1/0 |
| ETH | PAIR__bos_break_atr__retest_color | +0.275 | +1.566 | 5/4 | 1/0 |
| ETH | PAIR__bos_break_atr__retest_prev_close | +0.275 | +1.566 | 5/4 | 1/0 |
| ETH | PAIR__bos_break_atr__risk_max_pct | +0.275 | +0.445 | 5/5 | 1/0 |
| ETH | PAIR__bos_break_atr__risk_min_pct | +0.275 | +1.566 | 5/4 | 1/0 |
| ETH | PAIR__bos_break_atr__rsi_direction | +0.275 | +1.566 | 5/4 | 1/0 |
| ETH | PAIR__retest_color__risk_max_pct | +0.000 | +0.000 | 0/0 | 0/0 |
| ETH | PAIR__retest_color__risk_min_pct | +0.000 | +0.000 | 0/0 | 0/0 |
| ETH | PAIR__retest_color__rsi_direction | +0.000 | +0.000 | 0/0 | 0/0 |
| ETH | PAIR__retest_prev_close__risk_max_pct | +0.000 | +0.000 | 0/0 | 0/0 |
| ETH | PAIR__retest_prev_close__risk_min_pct | +0.000 | +0.000 | 0/0 | 0/0 |
| ETH | PAIR__retest_prev_close__rsi_direction | +0.000 | +0.000 | 0/0 | 0/0 |
| ETH | PAIR__risk_max_pct__risk_min_pct | +0.000 | +0.000 | 0/0 | 0/0 |
| ETH | PAIR__risk_max_pct__rsi_direction | +0.000 | +0.000 | 0/0 | 0/0 |
| ETH | PAIR__risk_min_pct__rsi_direction | +0.000 | +0.000 | 0/0 | 0/0 |

ETHUSDT: tamamı (84 kombinasyon) ve her işlem/regim JSON'da yer alır.

| SOL | PAIR__bos_break_atr__trend4h | +4.428 | -5.346 | 16/19 | 1/0 |
| SOL | PAIR__bos_rvol20__trend4h | +4.071 | -0.403 | 18/7 | 0/0 |
| SOL | PAIR_NO_VOLUME_SURGE_AND_RVOL20 | +2.940 | -2.001 | 4/5 | 0/0 |
| SOL | TRIPLE__bos_rvol20__rsi_direction__volume_burst | +2.940 | -2.001 | 4/5 | 0/0 |
| SOL | PAIR__bos_break_atr__retest_color | +2.905 | -3.148 | 3/10 | 0/0 |
| SOL | PAIR__bos_break_atr__retest_prev_close | +2.905 | -3.148 | 3/10 | 0/0 |
| SOL | PAIR__bos_break_atr__risk_min_pct | +2.905 | -3.148 | 3/10 | 0/0 |
| SOL | PAIR__bos_break_atr__rsi_direction | +2.905 | -3.148 | 3/10 | 0/0 |
| SOL | PAIR__bos_break_atr__sol_reversal | +2.905 | -4.550 | 3/11 | 0/0 |
| SOL | PAIR_NO_BREAK_ATR_AND_EMA_EXT | +2.406 | -2.112 | 4/15 | 0/0 |
| SOL | TRIPLE__bos_break_atr__bos_ema_extension__rsi_direction | +2.406 | -2.112 | 4/15 | 0/0 |
| SOL | PAIR__bos_break_atr__bos_rvol20 | +2.398 | -3.517 | 9/11 | 0/0 |
| SOL | PAIR__bos_rvol20__retest_color | +2.026 | +0.000 | 3/0 | 0/0 |
| SOL | PAIR__bos_rvol20__retest_prev_close | +2.026 | +0.000 | 3/0 | 0/0 |
| SOL | PAIR__bos_rvol20__risk_min_pct | +2.026 | +0.000 | 3/0 | 0/0 |
| SOL | PAIR__bos_rvol20__rsi_direction | +2.026 | +0.000 | 3/0 | 0/0 |
| SOL | PAIR__bos_rvol20__sol_reversal | +2.026 | -1.402 | 3/1 | 0/0 |
| SOL | QUAD__bos_break_atr__bos_ema_extension__macd_direction__rsi_direction | +1.831 | -0.675 | 7/25 | 0/2 |
| SOL | PAIR__bos_break_atr__risk_max_pct | +1.800 | -4.460 | 4/12 | 0/0 |
| SOL | PAIR__bos_break_atr__volume_burst | +1.669 | -2.537 | 6/12 | 0/0 |
| SOL | PAIR__trend4h__volume_burst | +1.572 | -0.799 | 10/10 | 0/0 |
| SOL | PAIR__bos_break_atr__retest_window | +1.359 | -3.553 | 4/13 | 0/0 |
| SOL | PAIR__bos_rvol20__macd_direction | +1.314 | -4.671 | 6/8 | 0/2 |
| SOL | TRIPLE__bos_break_atr__bos_ema_extension__volume_burst | +1.170 | -1.501 | 7/17 | 0/0 |
| SOL | PAIR__bos_rvol20__risk_max_pct | +0.921 | -0.222 | 4/1 | 0/0 |

SOLUSDT: tamamı (97 kombinasyon) ve her işlem/regim JSON'da yer alır.

## İstatistiksel ve işlem sınırları

- 3-ay blok bootstrap tanımlayıcıdır; çoklu karşılaştırma düzeltmesi değildir.
- Rejimler yalnızca girişte kapanmış günlük mumlarla hesaplandı.
- 9bps/25bps yön başı maliyet fonlama veya gerçek emir dolumunu ispatlamaz.
- Risk sınırı gevşetmeleri araştırmadır; canlı sistem önerisi değildir.
- Değerli görünen düşük örnekli sonuçlar V9.3'e otomatik terfi ettirilmez.
- Geleceğe yönelik yeni kağıt izleme ve önkayıtlı holdout gereklidir.

