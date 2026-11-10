# ETH V7 — Bağımsız saatlik paper-forward veri akışı

## 10 Kasım 2026 durum ve kapsam

ETHUSDT perpetual, BTC/SOL ana sistemi değiştirilmeden ayrı analiz motoruna bağlandı:

- Kod: eth_v7_hourly_observer.py
- Cron: main dalında .github/workflows/eth-v7-hourly-trigger.yml (UTC 18, 37, 52. dakikalarda deneme; GitHub cron gecikebilir/atlanabilir)
- Ayrı sonuçlar: forward/eth/snapshots/YYYY-MM-DDTHH-00Z.json ve forward/eth/reports/YYYY-MM-DDTHH-00Z.md
- Strateji: V4 baseline, V7 BOS filtresi, V7+güçlü retest. Kapanmış 1H BOS; 1–6 ayrı 1H retest; sonraki mumda varsayımsal giriş; stop/TP1/TP2/TP3/24h kuralı
- 1H, 4H ve günlük en az 250 kesintisiz kapanmış mum; ETH 4H ve 1D son 5 OHLCV'si 1H mum toplamlarıyla karşılaştırılır
- RSI14, MACD histogramı, EMA20/50/200, 1H ATR14, RVOL20, zaman dilimi yönü, yeni BOS ve reddetme gerekçeleri
- VERIFIED_PAPER_OBSERVATION yalnızca kaynak geçerli olduğunda; aksi halde SOURCE_UNAVAILABLE_NO_SIGNAL ve işlem/sinyal YOK
- Yalnız paper research; gerçek emir, Binance hesap erişimi, Cloudflare veya ana BTC/SOL yayın iş akışı değişikliği yok.

## Veri erişimi: gerçek engel

10 Kasım 2026 testinde GitHub runner'dan Binance resmi USD-M Futures REST GET /fapi/v1/klines 1H/4H/günlük için HTTP 451 verdi. Binance Futures WebSocket piyasa akışı el sıkışması 101 ile açıldı ancak geçmiş 250 kapanmış mumun güvenilir sorgulanması sağlanamadı. Spot ETH veya başka borsa verisi Binance ETH perpetual yerine konulmadı.

### ETH kaynak erişimini güvenli şekilde açmak

Mevcut deneysel kod isteğe bağlı Coinalyze ETHUSDT perpetual veri akışını destekler. GitHub repository -> Settings -> Secrets and variables -> Actions -> New repository secret:

- Secret name: ETH_V7_COINALYZE_API_KEY
- Secret value: Hesabın Coinalyze API anahtarı. **Bu sohbet içinde paylaşmayın.**

Alternatif olarak zaten COINALYZE_API_KEY adlı bir GitHub Actions secret varsa o da kullanılır. Secret Cloudflare'da bulunuyor olsa bile GitHub Actions'la otomatik paylaşılmaz. Yetkili hesap sahibinin GitHub Secrets bölümünde bu işlemi yapması gerekir.

Kaynak ETH-only Coinalyze perpetual candles: 1hour, 4hour ve daily. En az 250 tam kapanmış mum, zaman damgası/süreklilik ve 1H'e karşı 4H/1D OHLCV mutabakatı zorunludur. Kaynak reddederse sinyal çıkarılmaz. Binance REST erişimi gelecekte açılırsa anahtar olmasa da resmi API kullanılabilir.

### Nasıl teyit edilir?

1. Saatlik GitHub Runner'ın success olması yeterli değildir.
2. forward/eth/snapshots/ altında son saate ait JSON dosyasının status alanı VERIFIED_PAPER_OBSERVATION olmalıdır.
3. marketContext['ETHUSDT_PERP.A'] 1H/4H/Daily, BOS ve filtre nedenlerini içermelidir.
4. Yeni V7 uyarısı ancak results['ETHUSDT_PERP.A']['V7_signal_filter']['newWatchAtThisClose'] doluysa vardır.
5. SOURCE_UNAVAILABLE_NO_SIGNAL statüsü sıfır BOS değil, geçerli verinin bulunmaması demektir. Önceki saatler canlıymış gibi backfill yapılmaz.

## Maliyet/risk

ETH paper sinyalinin gerçek emir ya da gerçek fill olduğu iddia edilmez. R getirisi varsayımsal; fonlama ve emir defteri dahil değil. 100 USDT sermaye için 0,50 USDT planlanan işlem başı risk sınırı korunmuştur; observer gerçek pozisyon ve emir açmaz. İzleme sırası BTC, ETH, SOL; tercih edilen işlem odağı SOL.
