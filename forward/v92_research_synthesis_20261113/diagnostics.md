# V9.2: etkileşim + eşik taramasının doğrulanmış sentezi

**Araştırma tarihi 13 Kasım 2026. Canlı sinyal, V7/V9.2 sanal hesap ve bildirimler aynı.**
Önceki 6 baseline ile iki yeni çalışma ve birbirleri arasında işlem teyidi; 159 SHA256 doğrulamalı Binance USD-M aylık arşiv.
Her iki dönem daha önce görülmüştür, gerçek unseen holdout değildir. Çoklu test: 91 çift + 32 eşik senaryosu + 6 önkayıtlı çoklu kombinasyon; yanıltıcı en iyi sonuçlara dikkat.

## Coin başına gözlenen koşullu filtre tekrarı

Yalnızca test edilen tekli ve ikili kombinasyonlarda; evrensel gereksizlik kanıtı değildir.

| Coin | Gate | Tekli iki dönemde etkisiz | Diğer 13 gate ile koşullu etkisizlik (uygun N) |
|---|---|---|---:|
| BTC | volume_burst | Hayır | 0/12 |
| BTC | rsi_direction | Evet | 12/12 |
| BTC | macd_direction | Hayır | 0/12 |
| BTC | trend4h | Hayır | 0/12 |
| BTC | trend1d | Hayır | 0/12 |
| BTC | bos_break_atr | Hayır | 0/12 |
| BTC | bos_rvol20 | Hayır | 0/12 |
| BTC | bos_ema_extension | Hayır | 0/12 |
| BTC | retest_window | Hayır | 0/12 |
| BTC | retest_color | Evet | 11/12 |
| BTC | retest_prev_close | Evet | 11/12 |
| BTC | risk_max_pct | Evet | 11/12 |
| BTC | risk_min_pct | Hayır | 0/12 |
| ETH | volume_burst | Hayır | 0/12 |
| ETH | rsi_direction | Evet | 12/12 |
| ETH | macd_direction | Hayır | 0/12 |
| ETH | trend4h | Hayır | 0/12 |
| ETH | trend1d | Hayır | 0/12 |
| ETH | bos_break_atr | Hayır | 0/12 |
| ETH | bos_rvol20 | Hayır | 0/12 |
| ETH | bos_ema_extension | Hayır | 0/12 |
| ETH | retest_window | Hayır | 0/12 |
| ETH | retest_color | Evet | 11/12 |
| ETH | retest_prev_close | Evet | 11/12 |
| ETH | risk_max_pct | Evet | 8/12 |
| ETH | risk_min_pct | Evet | 12/12 |
| SOL | volume_burst | Hayır | 0/13 |
| SOL | rsi_direction | Evet | 13/13 |
| SOL | macd_direction | Hayır | 0/13 |
| SOL | trend4h | Hayır | 0/13 |
| SOL | trend1d | Hayır | 0/13 |
| SOL | bos_break_atr | Hayır | 0/13 |
| SOL | bos_rvol20 | Hayır | 0/13 |
| SOL | bos_ema_extension | Hayır | 0/13 |
| SOL | sol_reversal | Hayır | 0/13 |
| SOL | retest_window | Hayır | 0/13 |
| SOL | retest_color | Evet | 12/13 |
| SOL | retest_prev_close | Evet | 12/13 |
| SOL | risk_max_pct | Hayır | 0/13 |
| SOL | risk_min_pct | Evet | 13/13 |

## İki dönemde de pozitif ΔR25 görünen saf sinyal kombinasyonları

Adayları bulmak için SONUÇLARA göre sıralama yapılır, ancak bu **ön kayıt / bağımsız doğrulama / yatırım tavsiyesi değildir**.

| Coin | Kombinasyon | İlk ΔR25 | Son ΔR25 | İlk yeni işlem | Son yeni işlem | İlk/son kaçan kârlı | 3-ay bootstrap ilk [%95] |
|---|---|---:|---:|---:|---:|---:|---|
| ETH | PAIR_NO_BREAK_ATR_AND_EMA_EXT | +1.332 | +5.393 | 10 (W7/L3) | 10 (W7/L3) | 1/0 | [-6.99975, 9.14484] |
| ETH | TRIPLE__bos_break_atr__bos_ema_extension__rsi_direction | +1.332 | +5.393 | 10 (W7/L3) | 10 (W7/L3) | 1/0 | [-6.85039, 9.30748] |
| ETH | PAIR__bos_break_atr__retest_window | +2.840 | +0.937 | 7 (W5/L2) | 5 (W3/L2) | 1/0 | [-3.79549, 9.2647] |
| ETH | PAIR__bos_break_atr__retest_color | +0.275 | +1.566 | 5 (W3/L2) | 4 (W3/L1) | 1/0 | [-5.60546, 6.10083] |
| ETH | PAIR__bos_break_atr__retest_prev_close | +0.275 | +1.566 | 5 (W3/L2) | 4 (W3/L1) | 1/0 | [-6.3073, 5.81737] |
| ETH | PAIR__bos_break_atr__rsi_direction | +0.275 | +1.566 | 5 (W3/L2) | 4 (W3/L1) | 1/0 | [-5.81331, 5.99293] |
| ETH | TRIPLE__bos_break_atr__bos_ema_extension__volume_burst | +1.935 | +0.041 | 13 (W9/L4) | 15 (W8/L7) | 1/0 | [-5.18805, 9.52204] |
| SOL | PAIR__retest_color__volume_burst | +0.914 | +0.450 | 1 (W1/L0) | 2 (W1/L1) | 0/0 | [0.0, 2.74213] |
| SOL | PAIR__retest_prev_close__volume_burst | +0.914 | +0.450 | 1 (W1/L0) | 2 (W1/L1) | 0/0 | [0.0, 2.74213] |
| SOL | PAIR__rsi_direction__volume_burst | +0.914 | +0.450 | 1 (W1/L0) | 2 (W1/L1) | 0/0 | [0.0, 2.74213] |

İki dönemi de geçen pozitif ΔR25 kombinasyon adedi: BTC 0, ETH 7, SOL 3.
Bunların hiçbiri çoklu hipotez / örnek büyüklüğü engelini aşmış sayılmaz.

## Önemli iki dönemli filtre ablation etkileri

| Coin | Gate | İlk ΔR25 | Son ΔR25 | İlk/son yeni işlem | İlk/son kaçırılan kazanan |
|---|---|---:|---:|---:|---:|
| BTC | volume_burst | -1.152 | -0.374 | 1/1 | 0/0 |
| BTC | rsi_direction | +0.000 | +0.000 | 0/0 | 0/0 |
| BTC | macd_direction | +4.928 | -11.263 | 4/7 | 0/0 |
| BTC | trend4h | -5.312 | -6.102 | 10/12 | 0/0 |
| BTC | trend1d | -7.039 | -13.215 | 15/17 | 0/0 |
| BTC | bos_break_atr | -0.925 | -2.760 | 3/4 | 0/0 |
| BTC | bos_rvol20 | -4.068 | +0.000 | 3/0 | 0/0 |
| BTC | bos_ema_extension | +0.547 | -2.880 | 5/2 | 0/0 |
| BTC | retest_window | +0.000 | -1.486 | 0/4 | 0/0 |
| BTC | retest_color | +0.000 | +0.000 | 0/0 | 0/0 |
| BTC | retest_prev_close | +0.000 | +0.000 | 0/0 | 0/0 |
| ETH | volume_burst | -0.040 | -1.656 | 2/2 | 0/0 |
| ETH | rsi_direction | +0.000 | +0.000 | 0/0 | 0/0 |
| ETH | macd_direction | -5.953 | +0.000 | 5/0 | 0/0 |
| ETH | trend4h | -7.396 | -1.927 | 10/9 | 0/0 |
| ETH | trend1d | -8.510 | -10.442 | 13/13 | 0/0 |
| ETH | bos_break_atr | +0.275 | +1.566 | 5/4 | 1/0 |
| ETH | bos_rvol20 | -2.748 | -1.388 | 2/1 | 0/0 |
| ETH | bos_ema_extension | -0.326 | +5.591 | 5/7 | 0/0 |
| ETH | retest_window | +1.293 | -0.629 | 1/1 | 0/0 |
| ETH | retest_color | +0.000 | +0.000 | 0/0 | 0/0 |
| ETH | retest_prev_close | +0.000 | +0.000 | 0/0 | 0/0 |
| SOL | volume_burst | +0.914 | +0.450 | 1/2 | 0/0 |
| SOL | rsi_direction | +0.000 | +0.000 | 0/0 | 0/0 |
| SOL | macd_direction | -2.349 | -3.727 | 2/5 | 0/2 |
| SOL | trend4h | +0.658 | -0.403 | 9/7 | 0/0 |
| SOL | trend1d | -17.569 | -13.058 | 30/14 | 0/0 |
| SOL | bos_break_atr | +2.905 | -3.148 | 3/10 | 0/0 |
| SOL | bos_rvol20 | +2.026 | +0.000 | 3/0 | 0/0 |
| SOL | bos_ema_extension | -0.499 | -1.881 | 1/3 | 0/0 |
| SOL | sol_reversal | +0.000 | -1.402 | 0/1 | 0/0 |
| SOL | retest_window | -1.546 | -0.405 | 1/3 | 0/0 |
| SOL | retest_color | +0.000 | +0.000 | 0/0 | 0/0 |
| SOL | retest_prev_close | +0.000 | +0.000 | 0/0 | 0/0 |

## Ön araştırma için ETH seçilmiş kombinasyonların piyasa-rejim kırılımı

Rejim = giriş anında **kapanmış** Daily 4-oy trend sınıfı; yüksek/düşük volatilite geçmişteki rolling 20g dağılımına göre.

| ETH aday | Dönem | Rejim | Net ΔR25 | Varyant N | Baseline N |
|---|---|---|---:|---:|---:|
| PAIR_NO_BREAK_ATR_AND_EMA_EXT | 2022_2024 | trend:bear | +0.331 | 8 | 6 |
| PAIR_NO_BREAK_ATR_AND_EMA_EXT | 2022_2024 | trend:bull | +1.002 | 11 | 4 |
| PAIR_NO_BREAK_ATR_AND_EMA_EXT | 2022_2024 | volatility:high | +0.835 | 6 | 3 |
| PAIR_NO_BREAK_ATR_AND_EMA_EXT | 2022_2024 | volatility:low | +0.497 | 13 | 7 |
| PAIR_NO_BREAK_ATR_AND_EMA_EXT | 2024_2026 | trend:bear | +1.638 | 8 | 3 |
| PAIR_NO_BREAK_ATR_AND_EMA_EXT | 2024_2026 | trend:bull | +3.755 | 8 | 3 |
| PAIR_NO_BREAK_ATR_AND_EMA_EXT | 2024_2026 | volatility:high | +2.217 | 10 | 6 |
| PAIR_NO_BREAK_ATR_AND_EMA_EXT | 2024_2026 | volatility:low | +3.176 | 6 | 0 |
| PAIR__bos_break_atr__retest_window | 2022_2024 | trend:bear | +2.895 | 10 | 6 |
| PAIR__bos_break_atr__retest_window | 2022_2024 | trend:bull | -0.055 | 6 | 4 |
| PAIR__bos_break_atr__retest_window | 2022_2024 | volatility:high | -0.491 | 5 | 3 |
| PAIR__bos_break_atr__retest_window | 2022_2024 | volatility:low | +3.331 | 11 | 7 |
| PAIR__bos_break_atr__retest_window | 2024_2026 | trend:bear | +1.070 | 6 | 3 |
| PAIR__bos_break_atr__retest_window | 2024_2026 | trend:bull | -0.133 | 5 | 3 |
| PAIR__bos_break_atr__retest_window | 2024_2026 | volatility:high | -0.694 | 8 | 6 |
| PAIR__bos_break_atr__retest_window | 2024_2026 | volatility:low | +1.631 | 3 | 0 |

## 7 aile eşik duyarlılığı: geçmişin tuzakları

İlk dönemde en iyi puan veren eşikler ikinci dönemde aynı sonucu vermeyebilir; **işlem sıfırlayan** varyantlar avantaj sayılmaz.

| Coin | Aile | İlk-dönem en iyi eşik | İlk ΔR25 | Son ΔR25 | İlk/son işlem adedi |
|---|---|---:|---:|---:|---:|
| BTC | volume_surge_pct | 40 | +1.390 | +0.000 | 9/5  |
| BTC | rsi_long_cutoff | 46 | +0.000 | +0.000 | 10/5  |
| BTC | macd_hist_ema_bps | 3 | +3.739 | +0.392 | 6/3  |
| BTC | rvol20_min | 1.4 | +0.000 | +0.000 | 10/5  |
| BTC | bos_break_atr_min | 0.1 | -0.166 | +0.838 | 11/7  |
| BTC | ema_distance_atr_max | 1.5 | +7.701 | -2.815 | 0/0 (SIFIR İŞLEM) |
| BTC | retest_hours | 2 | +5.211 | -1.342 | 7/2  |
| ETH | volume_surge_pct | 50 | +0.477 | +0.000 | 8/6  |
| ETH | rsi_long_cutoff | 46 | +0.000 | +0.000 | 10/6  |
| ETH | macd_hist_ema_bps | 0.5 | +1.279 | +0.000 | 9/6  |
| ETH | rvol20_min | 1.4 | +0.000 | +0.000 | 10/6  |
| ETH | bos_break_atr_min | 0 | +0.275 | +1.566 | 14/10  |
| ETH | ema_distance_atr_max | 1.5 | +2.839 | +4.109 | 1/0 (SIFIR İŞLEM) |
| ETH | retest_hours | 5 | +1.293 | +0.000 | 11/6  |
| SOL | volume_surge_pct | 0 | +0.000 | -0.647 | 12/9  |
| SOL | rsi_long_cutoff | 46 | +0.000 | +0.000 | 12/8  |
| SOL | macd_hist_ema_bps | 0.5 | +1.775 | +0.000 | 10/8  |
| SOL | rvol20_min | 1.0 | +3.477 | +0.000 | 14/8  |
| SOL | bos_break_atr_min | 0.4 | +3.908 | -0.536 | 8/5  |
| SOL | ema_distance_atr_max | 2.0 | +0.494 | -0.679 | 9/3  |
| SOL | retest_hours | 3 | +0.947 | -2.859 | 11/6  |

## Net karar

- Daily yön teyidinin kaldırılması iki dönem/üç coinde tekrar tekrar zarar verdi; **henüz gevşetme gerekçesi yok**.
- RSI çiftlerin tamamında bilgi tekrarı gibi görünüyorsa dahi gerçek bağımsız piyasa verisi ve yeni aday izlemesi olmadan canlıdan çıkarılmaz.
- ETH BOS/retest ve BOS/EMA sinyalleri yalnızca ölçülebilir ileri sanal izleme hipotezidir, V9.3 kuralı değildir.
- Pozitif delta, kaçırılan kârlı işlem, stop risk sınırı, komisyon ve yetersiz yeni işlem birlikte değerlendirilir.
- 3 aylık blok bootstrap tanımlayıcıdır, çoklu test düzeltmesi değildir; hiçbir model üstünlüğü kanıtlanmadı.
- Geleceğe dönük plan research/v92_full_interaction_protocol_20261113.md dosyasında sabitlenmiştir.

