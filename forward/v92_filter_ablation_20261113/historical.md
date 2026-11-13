# V9.2 filtre ablasyon testi — BTC / ETH / SOL, 2022–2026

**Sadece tarihsel araştırma. V7, V9.2 sanal hesap, bildirim ve emir değişmedi.**

159 resmî Binance 1H aylık USD-M arşivi SHA256 ile doğrulandı.
2022-10..2024-09 ve 2024-10..2026-09 iki ayrı inceleme dönemi.
Her varyantta aynı kronolojik BOS → daha sonra retest → sonraki 1H açılışı,
stop-first, TP1/2/3 üçte bir ve 24h maksimum tutma mekanizması geçerlidir.
Maliyet 9bps/yön; stres 25bps/yön, gerçek fonlama/dolum kanıtı değildir.
Önceden dondurulan 1×14 filtre ablasyonu + 4 çiftli etkileşim testi;
hiçbir kombinasyon sonuca bakılarak üretilmedi.
Altı baseline önceki SHA256 çalışmaları ile sonuç eşleşmesi zorunludur.

## Birer filtre kaldırma (BASELINE dahil)

| Dönem | Coin | Kural | İşlem | Win% | Net R 9bps | Net R 25bps | ΔR9 | ΔR25 | MaxDD R | Yeni işlem | Kaçırılan kârlı | Önlenen zararlı |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2022_2024 | BTC | BASELINE | 10 | 30.0 | -4.2658 | -7.7013 | +0.0000 | +0.0000 | 5.088 | 0 | 0 | 0 |
| 2022_2024 | BTC | NO_1H_VOLUME_SURGE_20PCT | 11 | 27.27 | -4.8939 | -8.8534 | -0.6281 | -1.1522 | 5.716 | 1 | 0 | 0 |
| 2022_2024 | BTC | NO_1H_RSI_DIRECTION | 10 | 30.0 | -4.2658 | -7.7013 | +0.0000 | +0.0000 | 5.088 | 0 | 0 | 0 |
| 2022_2024 | BTC | NO_1H_MACD_DIRECTION | 13 | 46.15 | +1.3482 | -2.7736 | +5.6140 | +4.9277 | 5.809 | 4 | 0 | 1 |
| 2022_2024 | BTC | NO_4H_TREND_ALIGNMENT | 20 | 35.0 | -5.8662 | -13.0131 | -1.6004 | -5.3119 | 7.733 | 10 | 0 | 0 |
| 2022_2024 | BTC | NO_DAILY_TREND_ALIGNMENT | 25 | 40.0 | -5.6422 | -14.7401 | -1.3764 | -7.0389 | 10.433 | 15 | 0 | 0 |
| 2022_2024 | BTC | NO_BOS_MIN_BREAK_0P20ATR | 13 | 38.46 | -4.3226 | -8.6267 | -0.0568 | -0.9254 | 4.692 | 3 | 0 | 0 |
| 2022_2024 | BTC | NO_BOS_RVOL20_1P20 | 13 | 23.08 | -7.6504 | -11.7695 | -3.3846 | -4.0682 | 7.952 | 3 | 0 | 0 |
| 2022_2024 | BTC | NO_BOS_EMA20_MAX_EXTENSION_2P50ATR | 15 | 33.33 | -2.1490 | -7.1547 | +2.1168 | +0.5466 | 3.373 | 5 | 0 | 0 |
| 2022_2024 | BTC | RETEST_WINDOW_6H_NOT_4H | 10 | 30.0 | -4.2658 | -7.7013 | +0.0000 | +0.0000 | 5.088 | 0 | 0 | 0 |
| 2022_2024 | BTC | NO_RETEST_CANDLE_COLOR | 10 | 30.0 | -4.2658 | -7.7013 | +0.0000 | +0.0000 | 5.088 | 0 | 0 | 0 |
| 2022_2024 | BTC | NO_RETEST_VS_PREVIOUS_CLOSE | 10 | 30.0 | -4.2658 | -7.7013 | +0.0000 | +0.0000 | 5.088 | 0 | 0 | 0 |
| 2022_2024 | BTC | RISK_STOP_MAX_6PCT_NOT_4PCT | 10 | 30.0 | -4.2658 | -7.7013 | +0.0000 | +0.0000 | 5.088 | 0 | 0 | 0 |
| 2022_2024 | BTC | RISK_STOP_MIN_0P05PCT_NOT_0P10 | 11 | 27.27 | -7.4627 | -14.8038 | -3.1969 | -7.1025 | 8.285 | 1 | 0 | 0 |
| 2022_2024 | ETH | BASELINE | 10 | 30.0 | -0.9789 | -4.4969 | +0.0000 | +0.0000 | 3.340 | 0 | 0 | 0 |
| 2022_2024 | ETH | NO_1H_VOLUME_SURGE_20PCT | 11 | 36.36 | -0.7407 | -4.5372 | +0.2382 | -0.0402 | 2.878 | 2 | 0 | 1 |
| 2022_2024 | ETH | NO_1H_RSI_DIRECTION | 10 | 30.0 | -0.9789 | -4.4969 | +0.0000 | +0.0000 | 3.340 | 0 | 0 | 0 |
| 2022_2024 | ETH | NO_1H_MACD_DIRECTION | 15 | 26.67 | -5.4451 | -10.4498 | -4.4662 | -5.9528 | 7.338 | 5 | 0 | 0 |
| 2022_2024 | ETH | NO_4H_TREND_ALIGNMENT | 20 | 25.0 | -4.7706 | -11.8925 | -3.7917 | -7.3955 | 8.525 | 10 | 0 | 0 |
| 2022_2024 | ETH | NO_DAILY_TREND_ALIGNMENT | 23 | 26.09 | -6.5074 | -13.0069 | -5.5285 | -8.5100 | 9.954 | 13 | 0 | 0 |
| 2022_2024 | ETH | NO_BOS_MIN_BREAK_0P20ATR | 14 | 35.71 | -0.0578 | -4.2216 | +0.9211 | +0.2754 | 3.107 | 5 | 1 | 0 |
| 2022_2024 | ETH | NO_BOS_RVOL20_1P20 | 12 | 25.0 | -2.8214 | -7.2448 | -1.8425 | -2.7478 | 5.183 | 2 | 0 | 0 |
| 2022_2024 | ETH | NO_BOS_EMA20_MAX_EXTENSION_2P50ATR | 15 | 40.0 | -0.0171 | -4.8227 | +0.9618 | -0.3257 | 2.273 | 5 | 0 | 0 |
| 2022_2024 | ETH | RETEST_WINDOW_6H_NOT_4H | 11 | 36.36 | +0.7667 | -3.2037 | +1.7456 | +1.2933 | 3.340 | 1 | 0 | 0 |
| 2022_2024 | ETH | NO_RETEST_CANDLE_COLOR | 10 | 30.0 | -0.9789 | -4.4969 | +0.0000 | +0.0000 | 3.340 | 0 | 0 | 0 |
| 2022_2024 | ETH | NO_RETEST_VS_PREVIOUS_CLOSE | 10 | 30.0 | -0.9789 | -4.4969 | +0.0000 | +0.0000 | 3.340 | 0 | 0 | 0 |
| 2022_2024 | ETH | RISK_STOP_MAX_6PCT_NOT_4PCT | 10 | 30.0 | -0.9789 | -4.4969 | +0.0000 | +0.0000 | 3.340 | 0 | 0 | 0 |
| 2022_2024 | ETH | RISK_STOP_MIN_0P05PCT_NOT_0P10 | 10 | 30.0 | -0.9789 | -4.4969 | +0.0000 | +0.0000 | 3.340 | 0 | 0 | 0 |
| 2022_2024 | SOL | BASELINE | 12 | 50.0 | +4.6274 | +2.0039 | +0.0000 | +0.0000 | 2.166 | 0 | 0 | 0 |
| 2022_2024 | SOL | NO_1H_VOLUME_SURGE_20PCT | 13 | 53.85 | +5.6833 | +2.9180 | +1.0559 | +0.9140 | 1.653 | 1 | 0 | 0 |
| 2022_2024 | SOL | NO_1H_RSI_DIRECTION | 12 | 50.0 | +4.6274 | +2.0039 | +0.0000 | +0.0000 | 2.166 | 0 | 0 | 0 |
| 2022_2024 | SOL | NO_1H_MACD_DIRECTION | 14 | 42.86 | +2.5017 | -0.3454 | -2.1257 | -2.3493 | 2.170 | 2 | 0 | 0 |
| 2022_2024 | SOL | NO_4H_TREND_ALIGNMENT | 21 | 57.14 | +7.5156 | +2.6623 | +2.8882 | +0.6583 | 2.221 | 9 | 0 | 0 |
| 2022_2024 | SOL | NO_DAILY_TREND_ALIGNMENT | 42 | 35.71 | -5.9825 | -15.5650 | -10.6099 | -17.5690 | 10.044 | 30 | 0 | 0 |
| 2022_2024 | SOL | NO_BOS_MIN_BREAK_0P20ATR | 14 | 57.14 | +7.9677 | +4.9089 | +3.3403 | +2.9049 | 1.721 | 3 | 0 | 1 |
| 2022_2024 | SOL | NO_BOS_RVOL20_1P20 | 15 | 53.33 | +7.2768 | +4.0299 | +2.6494 | +2.0260 | 2.270 | 3 | 0 | 0 |
| 2022_2024 | SOL | NO_BOS_EMA20_MAX_EXTENSION_2P50ATR | 13 | 46.15 | +4.2344 | +1.5049 | -0.3930 | -0.4990 | 2.166 | 1 | 0 | 0 |
| 2022_2024 | SOL | NO_SOL_SELECTED_REVERSAL_VETO | 12 | 50.0 | +4.6274 | +2.0039 | +0.0000 | +0.0000 | 2.166 | 0 | 0 | 0 |
| 2022_2024 | SOL | RETEST_WINDOW_6H_NOT_4H | 13 | 46.15 | +3.4308 | +0.4578 | -1.1966 | -1.5462 | 2.304 | 1 | 0 | 0 |
| 2022_2024 | SOL | NO_RETEST_CANDLE_COLOR | 12 | 50.0 | +4.6274 | +2.0039 | +0.0000 | +0.0000 | 2.166 | 0 | 0 | 0 |
| 2022_2024 | SOL | NO_RETEST_VS_PREVIOUS_CLOSE | 12 | 50.0 | +4.6274 | +2.0039 | +0.0000 | +0.0000 | 2.166 | 0 | 0 | 0 |
| 2022_2024 | SOL | RISK_STOP_MAX_6PCT_NOT_4PCT | 13 | 46.15 | +3.5895 | +0.8986 | -1.0379 | -1.1054 | 3.204 | 1 | 0 | 0 |
| 2022_2024 | SOL | RISK_STOP_MIN_0P05PCT_NOT_0P10 | 12 | 50.0 | +4.6274 | +2.0039 | +0.0000 | +0.0000 | 2.166 | 0 | 0 | 0 |
| 2024_2026 | BTC | BASELINE | 5 | 60.0 | +4.1010 | +2.8146 | +0.0000 | +0.0000 | 1.230 | 0 | 0 | 0 |
| 2024_2026 | BTC | NO_1H_VOLUME_SURGE_20PCT | 6 | 50.0 | +3.8572 | +2.4404 | -0.2439 | -0.3742 | 1.474 | 1 | 0 | 0 |
| 2024_2026 | BTC | NO_1H_RSI_DIRECTION | 5 | 60.0 | +4.1010 | +2.8146 | +0.0000 | +0.0000 | 1.230 | 0 | 0 | 0 |
| 2024_2026 | BTC | NO_1H_MACD_DIRECTION | 12 | 33.33 | -1.6601 | -8.4479 | -5.7612 | -11.2625 | 3.810 | 7 | 0 | 0 |
| 2024_2026 | BTC | NO_4H_TREND_ALIGNMENT | 17 | 47.06 | +2.7358 | -3.2877 | -1.3653 | -6.1024 | 5.760 | 12 | 0 | 0 |
| 2024_2026 | BTC | NO_DAILY_TREND_ALIGNMENT | 22 | 36.36 | -1.9101 | -10.4002 | -6.0111 | -13.2148 | 4.674 | 17 | 0 | 0 |
| 2024_2026 | BTC | NO_BOS_MIN_BREAK_0P20ATR | 9 | 55.56 | +3.1795 | +0.0549 | -0.9215 | -2.7597 | 1.707 | 4 | 0 | 0 |
| 2024_2026 | BTC | NO_BOS_RVOL20_1P20 | 5 | 60.0 | +4.1010 | +2.8146 | +0.0000 | +0.0000 | 1.230 | 0 | 0 | 0 |
| 2024_2026 | BTC | NO_BOS_EMA20_MAX_EXTENSION_2P50ATR | 7 | 42.86 | +1.7841 | -0.0657 | -2.3169 | -2.8804 | 3.547 | 2 | 0 | 0 |
| 2024_2026 | BTC | RETEST_WINDOW_6H_NOT_4H | 9 | 55.56 | +3.6636 | +1.3290 | -0.4374 | -1.4857 | 3.551 | 4 | 0 | 0 |
| 2024_2026 | BTC | NO_RETEST_CANDLE_COLOR | 5 | 60.0 | +4.1010 | +2.8146 | +0.0000 | +0.0000 | 1.230 | 0 | 0 | 0 |
| 2024_2026 | BTC | NO_RETEST_VS_PREVIOUS_CLOSE | 5 | 60.0 | +4.1010 | +2.8146 | +0.0000 | +0.0000 | 1.230 | 0 | 0 | 0 |
| 2024_2026 | BTC | RISK_STOP_MAX_6PCT_NOT_4PCT | 5 | 60.0 | +4.1010 | +2.8146 | +0.0000 | +0.0000 | 1.230 | 0 | 0 | 0 |
| 2024_2026 | BTC | RISK_STOP_MIN_0P05PCT_NOT_0P10 | 5 | 60.0 | +4.1010 | +2.8146 | +0.0000 | +0.0000 | 1.230 | 0 | 0 | 0 |
| 2024_2026 | ETH | BASELINE | 6 | 33.33 | -2.0083 | -4.1088 | +0.0000 | +0.0000 | 2.179 | 0 | 0 | 0 |
| 2024_2026 | ETH | NO_1H_VOLUME_SURGE_20PCT | 8 | 37.5 | -3.1478 | -5.7649 | -1.1395 | -1.6561 | 3.381 | 2 | 0 | 0 |
| 2024_2026 | ETH | NO_1H_RSI_DIRECTION | 6 | 33.33 | -2.0083 | -4.1088 | +0.0000 | +0.0000 | 2.179 | 0 | 0 | 0 |
| 2024_2026 | ETH | NO_1H_MACD_DIRECTION | 6 | 33.33 | -2.0083 | -4.1088 | +0.0000 | +0.0000 | 2.179 | 0 | 0 | 0 |
| 2024_2026 | ETH | NO_4H_TREND_ALIGNMENT | 15 | 40.0 | +0.0714 | -6.0356 | +2.0797 | -1.9268 | 4.955 | 9 | 0 | 0 |
| 2024_2026 | ETH | NO_DAILY_TREND_ALIGNMENT | 19 | 31.58 | -8.4051 | -14.5504 | -6.3969 | -10.4416 | 10.805 | 13 | 0 | 0 |
| 2024_2026 | ETH | NO_BOS_MIN_BREAK_0P20ATR | 10 | 50.0 | +0.2071 | -2.5431 | +2.2154 | +1.5657 | 3.285 | 4 | 0 | 0 |
| 2024_2026 | ETH | NO_BOS_RVOL20_1P20 | 7 | 28.57 | -3.1480 | -5.4968 | -1.1397 | -1.3880 | 3.319 | 1 | 0 | 0 |
| 2024_2026 | ETH | NO_BOS_EMA20_MAX_EXTENSION_2P50ATR | 13 | 53.85 | +5.5511 | +1.4822 | +7.5594 | +5.5910 | 2.179 | 7 | 0 | 0 |
| 2024_2026 | ETH | RETEST_WINDOW_6H_NOT_4H | 7 | 28.57 | -2.4480 | -4.7375 | -0.4397 | -0.6287 | 2.619 | 1 | 0 | 0 |
| 2024_2026 | ETH | NO_RETEST_CANDLE_COLOR | 6 | 33.33 | -2.0083 | -4.1088 | +0.0000 | +0.0000 | 2.179 | 0 | 0 | 0 |
| 2024_2026 | ETH | NO_RETEST_VS_PREVIOUS_CLOSE | 6 | 33.33 | -2.0083 | -4.1088 | +0.0000 | +0.0000 | 2.179 | 0 | 0 | 0 |
| 2024_2026 | ETH | RISK_STOP_MAX_6PCT_NOT_4PCT | 6 | 33.33 | -2.0083 | -4.1088 | +0.0000 | +0.0000 | 2.179 | 0 | 0 | 0 |
| 2024_2026 | ETH | RISK_STOP_MIN_0P05PCT_NOT_0P10 | 6 | 33.33 | -2.0083 | -4.1088 | +0.0000 | +0.0000 | 2.179 | 0 | 0 | 0 |
| 2024_2026 | SOL | BASELINE | 8 | 62.5 | +4.2607 | +2.4099 | +0.0000 | +0.0000 | 1.127 | 0 | 0 | 0 |
| 2024_2026 | SOL | NO_1H_VOLUME_SURGE_20PCT | 10 | 60.0 | +5.0975 | +2.8600 | +0.8369 | +0.4501 | 1.127 | 2 | 0 | 0 |
| 2024_2026 | SOL | NO_1H_RSI_DIRECTION | 8 | 62.5 | +4.2607 | +2.4099 | +0.0000 | +0.0000 | 1.127 | 0 | 0 | 0 |
| 2024_2026 | SOL | NO_1H_MACD_DIRECTION | 11 | 45.45 | +1.3881 | -1.3172 | -2.8725 | -3.7271 | 3.124 | 5 | 2 | 0 |
| 2024_2026 | SOL | NO_4H_TREND_ALIGNMENT | 15 | 53.33 | +4.8518 | +2.0070 | +0.5912 | -0.4029 | 3.264 | 7 | 0 | 0 |
| 2024_2026 | SOL | NO_DAILY_TREND_ALIGNMENT | 22 | 31.82 | -4.7070 | -10.6484 | -8.9676 | -13.0583 | 6.881 | 14 | 0 | 0 |
| 2024_2026 | SOL | NO_BOS_MIN_BREAK_0P20ATR | 18 | 44.44 | +3.5636 | -0.7376 | -0.6970 | -3.1476 | 3.158 | 10 | 0 | 0 |
| 2024_2026 | SOL | NO_BOS_RVOL20_1P20 | 8 | 62.5 | +4.2607 | +2.4099 | +0.0000 | +0.0000 | 1.127 | 0 | 0 | 0 |
| 2024_2026 | SOL | NO_BOS_EMA20_MAX_EXTENSION_2P50ATR | 11 | 54.55 | +3.1791 | +0.5292 | -1.0816 | -1.8807 | 2.211 | 3 | 0 | 0 |
| 2024_2026 | SOL | NO_SOL_SELECTED_REVERSAL_VETO | 9 | 55.56 | +3.1159 | +1.0080 | -1.1447 | -1.4020 | 2.272 | 1 | 0 | 0 |
| 2024_2026 | SOL | RETEST_WINDOW_6H_NOT_4H | 10 | 60.0 | +4.0057 | +2.0046 | -0.2550 | -0.4053 | 2.153 | 3 | 0 | 1 |
| 2024_2026 | SOL | NO_RETEST_CANDLE_COLOR | 8 | 62.5 | +4.2607 | +2.4099 | +0.0000 | +0.0000 | 1.127 | 0 | 0 | 0 |
| 2024_2026 | SOL | NO_RETEST_VS_PREVIOUS_CLOSE | 8 | 62.5 | +4.2607 | +2.4099 | +0.0000 | +0.0000 | 1.127 | 0 | 0 | 0 |
| 2024_2026 | SOL | RISK_STOP_MAX_6PCT_NOT_4PCT | 9 | 55.56 | +4.1093 | +2.1876 | -0.1513 | -0.2223 | 1.127 | 1 | 0 | 0 |
| 2024_2026 | SOL | RISK_STOP_MIN_0P05PCT_NOT_0P10 | 8 | 62.5 | +4.2607 | +2.4099 | +0.0000 | +0.0000 | 1.127 | 0 | 0 | 0 |

## Önceden seçilmiş ikili etkileşim senaryoları

| Dönem | Coin | Kombinasyon | İşlem | Net R9 | Net R25 | ΔR9 | ΔR25 |
|---|---|---|---:|---:|---:|---:|---:|
| 2022_2024 | BTC | PAIR_NO_VOLUME_SURGE_AND_RVOL20 | 14 | -8.2785 | -12.9217 | -4.0127 | -5.2204 |
| 2022_2024 | BTC | PAIR_NO_RSI_AND_MACD | 13 | +1.3482 | -2.7736 | +5.6140 | +4.9277 |
| 2022_2024 | BTC | PAIR_NO_4H_AND_DAILY | 64 | -21.1543 | -49.9887 | -16.8886 | -42.2874 |
| 2022_2024 | BTC | PAIR_NO_BREAK_ATR_AND_EMA_EXT | 18 | -2.2058 | -8.0801 | +2.0600 | -0.3788 |
| 2022_2024 | ETH | PAIR_NO_VOLUME_SURGE_AND_RVOL20 | 16 | -6.2057 | -12.0138 | -5.2268 | -7.5169 |
| 2022_2024 | ETH | PAIR_NO_RSI_AND_MACD | 15 | -5.4451 | -10.4498 | -4.4662 | -5.9528 |
| 2022_2024 | ETH | PAIR_NO_4H_AND_DAILY | 54 | -24.6068 | -42.1611 | -23.6279 | -37.6641 |
| 2022_2024 | ETH | PAIR_NO_BREAK_ATR_AND_EMA_EXT | 19 | +2.3015 | -3.1647 | +3.2804 | +1.3323 |
| 2022_2024 | SOL | PAIR_NO_VOLUME_SURGE_AND_RVOL20 | 16 | +8.3326 | +4.9440 | +3.7052 | +2.9400 |
| 2022_2024 | SOL | PAIR_NO_RSI_AND_MACD | 14 | +2.5017 | -0.3454 | -2.1257 | -2.3493 |
| 2022_2024 | SOL | PAIR_NO_4H_AND_DAILY | 72 | +2.2511 | -14.8573 | -2.3763 | -16.8612 |
| 2022_2024 | SOL | PAIR_NO_BREAK_ATR_AND_EMA_EXT | 15 | +7.5747 | +4.4098 | +2.9473 | +2.4059 |
| 2024_2026 | BTC | PAIR_NO_VOLUME_SURGE_AND_RVOL20 | 8 | +2.7002 | +0.4119 | -1.4008 | -2.4027 |
| 2024_2026 | BTC | PAIR_NO_RSI_AND_MACD | 12 | -1.6601 | -8.4479 | -5.7612 | -11.2625 |
| 2024_2026 | BTC | PAIR_NO_4H_AND_DAILY | 51 | -7.3524 | -27.3138 | -11.4534 | -30.1284 |
| 2024_2026 | BTC | PAIR_NO_BREAK_ATR_AND_EMA_EXT | 11 | +0.8626 | -2.8255 | -3.2385 | -5.6401 |
| 2024_2026 | ETH | PAIR_NO_VOLUME_SURGE_AND_RVOL20 | 9 | -4.2875 | -7.1529 | -2.2792 | -3.0441 |
| 2024_2026 | ETH | PAIR_NO_RSI_AND_MACD | 6 | -2.0083 | -4.1088 | +0.0000 | +0.0000 |
| 2024_2026 | ETH | PAIR_NO_4H_AND_DAILY | 51 | -14.1268 | -31.8595 | -12.1185 | -27.7507 |
| 2024_2026 | ETH | PAIR_NO_BREAK_ATR_AND_EMA_EXT | 16 | +5.8516 | +1.2841 | +7.8599 | +5.3929 |
| 2024_2026 | SOL | PAIR_NO_VOLUME_SURGE_AND_RVOL20 | 13 | +3.3617 | +0.4085 | -0.8990 | -2.0014 |
| 2024_2026 | SOL | PAIR_NO_RSI_AND_MACD | 11 | +1.3881 | -1.3172 | -2.8725 | -3.7271 |
| 2024_2026 | SOL | PAIR_NO_4H_AND_DAILY | 45 | -3.6178 | -14.7678 | -7.8784 | -17.1777 |
| 2024_2026 | SOL | PAIR_NO_BREAK_ATR_AND_EMA_EXT | 23 | +5.6491 | +0.2981 | +1.3884 | -2.1118 |

## Sadece ilk dönem verisine göre ön adaylar

- **BTCUSDT**: NO_1H_MACD_DIRECTION, NO_BOS_EMA20_MAX_EXTENSION_2P50ATR
- **ETHUSDT**: NO_BOS_MIN_BREAK_0P20ATR
- **SOLUSDT**: NO_BOS_MIN_BREAK_0P20ATR, NO_BOS_RVOL20_1P20, NO_4H_TREND_ALIGNMENT

## Önemli yorum ve güvenlik

- Bir filtreyi çıkarmak işlem dizisini değiştirebilir: yeni işlemler daha sonra gelecek başka işlemleri engelleyebilir. Çıkarılan/eklenen işlemler tarihle eşleştirildi, yalnızca kazanç yüzdesine bakılmadı.
- V9.2'de BOS yapısı, retest teması, retest kapanışının BOS seviyesinin doğru tarafında olması ve sonraki 1H açılışı hiçbir deneyde kaldırılmadı.
- Mevcut 1H BOS hacmi %20, RSI/MACD yön, 4H/Daily yön, BOS en az 0.2 ATR, RVOL20 1.2, EMA20 en fazla 2.5ATR, SOL seçici mum veto; risk aralığı %0.1-4 ve 4H retest limiti başlangıçtır.
- V7 ayrı 6H / 4H+retest-strength varyantları içerebilir. Bu ablation yalnızca mevcut V9.2 referansını değiştirir; V7 production için test edilmiş değildir.
- 9bps/25bps şeması fonlamayı, değişken spread ve stop kaymalarını tam yansıtmaz. 1000 USDT capped paper defterine tarihsel işlem eklenmedi.
- Filtre kombinasyonları aynı dönemlerde daha önce incelenmiş sinyaller üzerinde test edildi. Çoklu karşılaştırma ve sonradan seçim yanlılığı yüksektir; geleceğe dönük kârlılık kanıtı değildir.
- Daha az işlem yapan modelin 0R sonucu iyi performans değil işlem yapmamasıdır. Tekrarlanamayan veya az örnekli 'kazanan' parametre önerisi yoktur.

