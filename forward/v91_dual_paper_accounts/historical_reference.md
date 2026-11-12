# V7 vs V9.1 — bütün mevcut arşiv mumlarında ayrı 1.000 USDT sanal geçmiş test

**TARİHSEL SENARYO, GERÇEK VEYA İLERİ DÖNÜK PAPER İŞLEM DEĞİLDİR.**
Arşiv: 2024-10-01T00:00:00Z – 2026-10-01T00:00:00Z (son gün hariç).
V7 ve V9.1 tam kronolojik 1H/4H/Daily mum simülatörüyle aynı dönem üzerinden karşılaştırılmıştır.
V9.1'in 4H süresi, bu arşivdeki sonuçlar incelendikten sonra seçildiği için veriler bağımsız test değildir.
Her sanal hesap 1.000 USDT; stop mesafesine göre hedef risk 100 USDT/işlem, sabit, bileşik değil.

| Model | İşlem | Kazanç | Net R (9 bp/yan) | Sanal PnL | Bakiye | 25 bp/yan stres bakiyesi |
|---|---:|---:|---:|---:|---:|---:|
| V7_ORIGINAL | 20 | 11 | 6.5246 | 652.46 | 1652.46 | 1193.16 |
| V91_RETEST_MAX4H | 14 | 8 | 7.2170 | 721.70 | 1721.70 | 1382.26 |

**Sınırlamalar:** ETH'nin eşdeğer 2 yıllık bağımsız arşivi yok; arşiv sonucu BTC/SOL ile sınırlı. 
Aynı anda birden çok sembolde pozisyon olabiliyor; toplam hesap riski 100 USDT'yi aşabilir. Gerçekçi emir geçikmesi, fonlama, tasfiye, slipaj ve gerçek fill kanıtı yok. %10 risk agresiftir.
İleriye dönük gerçek paper hesapları **ayrı bir defterdedir**; bu bakiye onlara aktarılmaz.

