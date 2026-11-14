# ATLAS — BTC ve SOL V9.2 dayanıklılık testi

**Sadece daha önce incelenmiş tarihsel işlemlerin yeni denetimi; gerçek ileri/bağımsız holdout DEĞİL.**
159 Binance USD-M aylık ZIP dosyasının önceki SHA256 doğrulamalı arşiv raporundan birebir değişmez işlemler kullanıldı.
Girişte yalnız KAPANMIŞ Daily mumlara dayanan önceki trend/volatilite rejimlerine bakıldı.
Maliyet: 9, 25 ve araştırma amaçlı 50 bps/yön; gerçek fonlama, spread veya emir dolumu kanıtı yok.

## Tarihsel dönemler ve maliyet dayanıklılığı

| Dönem | Coin | N | Win %25 | R9 | R25 | R50 | DD25 | PF25 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 2022_2024 | BTC | 10 | 30.0 | -4.266 | -7.701 | -13.069 | 7.701 | 0.31704 |
| 2022_2024 | SOL | 12 | 41.667 | +4.627 | +2.004 | -2.095 | 3.055 | 1.322838 |
| 2024_2026 | BTC | 5 | 60.0 | +4.101 | +2.815 | +0.805 | 1.639 | 2.43317 |
| 2024_2026 | SOL | 8 | 62.5 | +4.261 | +2.410 | -0.482 | 1.353 | 1.627244 |

## İki dönem birleşimi — toplam risk ve kazanma oranı

| Coin | Yeni değil: N/W | Wilson %95 tanımlayıcı | Frozen toplam R25 | R50 | En iyi işlem çıkarılırsa R25 | En iyi iki kazanç çıkarılırsa R25 | En iyi çeyrek çıkarılırsa R25 |
|---|---:|---|---:|---:|---:|---:|---:|
| BTC | 15/6 | [19.82, 64.25] | -4.887 | -12.265 | -6.700 | -8.498 | -6.685 |
| SOL | 20/10 | [29.93, 70.07] | +4.414 | -2.577 | +2.605 | +0.808 | +1.308 |

## Girişte bilinen Daily rejim ve işlem yönü

| Coin | Boyut | Rejim | N | Kazanma % | R25 |
|---|---|---|---:|---:|---:|
| BTC | direction | bearish | 9 | 55.556 | +0.891 |
| BTC | direction | bullish | 6 | 16.667 | -5.777 |
| BTC | trend | bear | 9 | 55.556 | +0.891 |
| BTC | trend | bull | 6 | 16.667 | -5.777 |
| BTC | volatility | high | 5 | 40.0 | +0.457 |
| BTC | volatility | low | 10 | 40.0 | -5.344 |
| SOL | direction | bearish | 9 | 44.444 | +0.454 |
| SOL | direction | bullish | 11 | 54.545 | +3.960 |
| SOL | trend | bear | 9 | 44.444 | +0.454 |
| SOL | trend | bull | 11 | 54.545 | +3.960 |
| SOL | volatility | high | 6 | 83.333 | +5.899 |
| SOL | volatility | low | 14 | 35.714 | -1.486 |

## Çeyrek bazlı yoğunlaşma ve belirsizlik

| Coin | İşlem yapılan ay/çeyrek | Zarar eden çeyrek | En iyi çeyrek | Blok bootstrap R25 alt/üst %2.5–97.5 |
|---|---|---:|---|---|
| BTC | 12/10 | 5 | 2026-Q1 (+1.80R) | [-15.73,+5.54] |
| SOL | 12/10 | 4 | 2023-Q4 (+3.11R) | [-4.94,+14.56] |

3 aylık blok bootstrap zaten görülmüş 48 ay üzerinden tanımlayıcıdır; ileri dönem veya çoklu karşılaştırma düzeltmesi değildir.

## Geçmişte taranmış 91 çiftli araştırma: istikrar kontrolü

| Coin | Sinyal etkileşimi | İlk dönemi iyileştiren | Önceden görülmüş ikinci dönemi de iyileştiren | İki dönem ≥10 yeni işlem koşulu |
|---|---:|---:|---:|---:|
| BTC | 61 | 13 | 0 | 0 |
| SOL | 72 | 35 | 3 | 0 |

## BTC / SOL eşzamanlı risk

Örtüşen açık BTC/SOL tarihsel işlem çifti: 2; her iki coin'de giriş yapılan ortak ay: 4.
Bundan bağımsız risk sonucu çıkarılmadı; portföy PnL ve sermaye ağırlıklı korelasyon hesaplanmadı.

## Karar

- BTC 2022–24 negatif; 2024–26 tek başına son dönem artısıyla strateji kanıtlanmış sayılmaz.
- SOL iki geçmiş dönemde artı; bu küçük örnekle kalıcı %55 üstünlük, 50bps maliyet veya farklı rejim dayanıklılığı kesin değildir.
- Pozitif dönemler dahil hiçbir tarihsel işlem geleceğe dönük sanal hesaplara eklenmedi.
- Yeni parametre/filtre eklenmedi, eski 91 çiftlik taramadan üretime herhangi bir aday aktarılmadı.
- Gelecek araştırmada varlık başına ≥100 gerçekten yeni kapanmış işlem ve pozitif net R, DD, maliyet, rejim ve istatistiksel belirsizlik kontrolü gereklidir.
- GitHub main, V7/V9.2, ETH günlük veri güvenliği, kullanıcının bildirim saatleri ve görsel BTC/SOL kartları değişmedi.

Arşiv kaynak SHA256: 9b15781c293eaf38abfd62ea6e087bc9ec35b0df48b8b78fc6f851d971e3d5ab

