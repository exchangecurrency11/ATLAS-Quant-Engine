# BTC LONG / SOL volatilite — tam kronolojik tarihsel araştırma

**TÜM TARİHLER ÖNCEDEN GÖRÜLMÜŞTÜR: yeni ileri test, bağımsız holdout veya kârlılık kanıtı değil.**
Daha önce dondurulmuş V9.2 engine ile aynı giriş/çıkış, Binance 159 aylık resmî SHA256 kaynağı yeniden kontrol edildi.
Olası LONG BTC ve SOL giriş veto kararı yalnız retest kapanışından önce TAMAMLANMIŞ Daily volatilite sınıfıyla verilir.
BTC SHORT hiç engellenmez. SOL eski seçici ters mum vetosu korunur.
Yeni, gerçekten ileri değerlendirme için tasarlanan başlangıç: 2026-11-15T00:00:00Z.

| Dönem | Coin | Yöntem | N | W%25 | R25 | R50 | DD25 | ΔR25 aday-ref |
|---|---|---|---:|---:|---:|---:|---:|---:|
| 2022_2024 | BTC | baseline | 10 | 30.0 | -7.701 | -13.069 | 7.701 | +2.749 |
| 2022_2024 | BTC | candidate | 6 | 33.333 | -4.952 | -8.571 | 4.952 | +2.749 |
| 2022_2024 | SOL | baseline | 12 | 41.667 | +2.004 | -2.095 | 3.055 | +1.602 |
| 2022_2024 | SOL | candidate | 2 | 100.0 | +3.606 | +3.212 | 0.000 | +1.602 |
| 2024_2026 | BTC | baseline | 5 | 60.0 | +2.815 | +0.805 | 1.639 | +1.639 |
| 2024_2026 | BTC | candidate | 4 | 75.0 | +4.453 | +3.082 | 0.325 | +1.639 |
| 2024_2026 | SOL | baseline | 8 | 62.5 | +2.410 | -0.482 | 1.353 | +1.217 |
| 2024_2026 | SOL | candidate | 5 | 80.0 | +3.627 | +1.793 | 1.239 | +1.217 |

## Dış kaynaklı tarihsel olaylarla işlemlerin eşleştirilmesi

| Olay | BTC işlem / R25 | SOL işlem / R25 |
|---|---:|---:|
| [FTX_2022](https://www.elibrary.imf.org/view/journals/001/2023/213/article-A001-en.xml) (2022-11-07–2022-11-22) | 0 / +0.000 | 0 / +0.000 |
| [BANKING_2023](https://www.elibrary.imf.org/view/journals/001/2023/214/article-A001-en.xml) (2023-03-08–2023-03-23) | 1 / +1.502 | 1 / -1.300 |
| [BTC_ETP_2024](https://www.sec.gov/newsroom/speeches-statements/gensler-statement-spot-bitcoin-011023) (2024-01-03–2024-01-18) | 0 / +0.000 | 0 / +0.000 |
| [SOL_OUTAGE_2024](https://solana.com/news/02-06-24-solana-mainnet-beta-outage-report) (2024-02-05–2024-02-11) | 1 / -1.720 | 1 / +1.625 |
| [BTC_VOL_SPIKE_2025](https://www.spglobal.com/en/research-insights/special-reports/bitcoin-volatility-trends-deep-dive) (2025-10-08–2025-10-16) | 0 / +0.000 | 0 / +0.000 |

Olay pencereleri dış kaynaktan sabitlendi. Eşleşme korelasyon değil; olayın işlemi meydana getirdiğine dair kanıt değildir.
Yanlılık: geçmiş LONG ve volatilite sonuçları görüldükten sonra bu iki aday tasarlandı.
Başka fırsatları engelleme etkisini görmek için her adayın TÜM 1H strateji sırası yeniden oynatıldı; yalnızca kaybeden eski işlemler silinmedi.
25/50 bps ücret-stres modelleri gerçek emir dolumunu, dinamik spread, funding ve pozisyon likidasyonunu doğrulamaz.
V7/V9.2, ETH günlük veri güvenliği, tüm sanal hesaplar, otomasyonlar ve bildirimler değiştirilmedi.

