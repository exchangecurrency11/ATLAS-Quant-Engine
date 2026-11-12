# V9.2 — Morning Star / Evening Star & fake breakout invalidasyon

**YALNIZCA ESKİ KAPANIŞLARLA YAPILAN PAPER BACKTEST.** V7 ve V9.1 değişmedi.
Piyasa: BTC ve SOL USD-M perpetual. Dönem: 2024-10-01T00:00:00Z – 2026-10-01T00:00:00Z (son tarih hariç).
Tam kronolojik 1H/4H/Daily geçmişi; 4H kapanmadan sonraki bilgisi 1H kararında kullanılmaz.
Yıldız formasyonları üç mumdan oluşur; 24/7 piyasa için gap aranmaz. 
Geri dönük bakış: bu dönem daha önce incelendi, sonuçlar bağımsız doğrulama değildir.

| Coin | Sürüm | Paper işlem | Başarı % | Net R (9bp/yön) | 25bp/yön net R | Max DD R | Retest reddi |
|---|---|---:|---:|---:|---:|---:|---:|
| BTCUSDT | V7_ORIGINAL | 9 | 55.56 | 3.6636 | 1.3290 | 3.5506 | 0 |
| BTCUSDT | V91_RETEST_MAX4H | 5 | 60.0 | 4.1010 | 2.8146 | 1.2299 | 0 |
| BTCUSDT | V92_V7_OPPOSITE_STAR_WARNING_VETO | 9 | 55.56 | 3.6636 | 1.3290 | 3.5506 | 0 |
| BTCUSDT | V92_V91_OPPOSITE_STAR_WARNING_VETO | 5 | 60.0 | 4.1010 | 2.8146 | 1.2299 | 0 |
| BTCUSDT | V92_V7_STAR_PLUS_FAKE_BREAK_VETO | 9 | 55.56 | 3.6636 | 1.3290 | 3.5506 | 0 |
| BTCUSDT | V92_V91_STAR_PLUS_FAKE_BREAK_VETO | 5 | 60.0 | 4.1010 | 2.8146 | 1.2299 | 0 |
| SOLUSDT | V7_ORIGINAL | 11 | 54.55 | 2.8610 | 0.6026 | 2.5764 | 0 |
| SOLUSDT | V91_RETEST_MAX4H | 9 | 55.56 | 3.1159 | 1.0080 | 2.2718 | 0 |
| SOLUSDT | V92_V7_OPPOSITE_STAR_WARNING_VETO | 10 | 60.0 | 4.0057 | 2.0046 | 2.1534 | 1 |
| SOLUSDT | V92_V91_OPPOSITE_STAR_WARNING_VETO | 8 | 62.5 | 4.2607 | 2.4099 | 1.1271 | 1 |
| SOLUSDT | V92_V7_STAR_PLUS_FAKE_BREAK_VETO | 10 | 60.0 | 4.0057 | 2.0046 | 2.1534 | 1 |
| SOLUSDT | V92_V91_STAR_PLUS_FAKE_BREAK_VETO | 8 | 62.5 | 4.2607 | 2.4099 | 1.1271 | 1 |

Yıldız tersine dönüş uyarıları, karşı trendin teyidi değildir. Tam BOS ve retest kurallarıyla karşılaştırılmadan tek başına işlem açılmaz.
Ek filtrelerin trade fırsatlarını azaltması veya net R'yi düşürmesi mümkündür.
Maliyetler varsayımsaldır; gerçek emir, fundlama, slipaj ve likidasyon tam modellenmedi.
Hiçbir V9.2 bulgusu V7/V9.1 sistemini veya kullanıcı bildirimlerini otomatik değiştirmez.
