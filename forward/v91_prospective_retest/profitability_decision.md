# V7 vs V9.1 — işlem fırsatı ve uygulanabilir kârlılık kontrolü

**Karar: V9.1 sadece sessiz paper araştırmasında kalsın. Canlı emir/bildirim yok.**

## Önceden incelenmiş geçmiş 2024-10 → 2026-09

| Coin | V7 işlem | V7 net R | V9.1 işlem | V9.1 net R | Fark R | Ortak | Çıkarılan V7 | Eklenen V9.1 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| BTCUSDT | 9 | 3.663603 | 5 | 4.101041 | 0.437438 | 5 | 4 (2 kazanç, 2 zarar) | 0 |
| SOLUSDT | 11 | 2.860985 | 9 | 3.115948 | 0.254963 | 8 | 3 (1 kazanç, 2 zarar) | 1 |

**Bu, hipotez üretilirken incelenmiş geçmiş veridir; yeni kâr kanıtı değildir.**
9bps/yan ücret+slippage varsayılmıştır. 25bps/yan stres hesabı da rapor JSON'undadır.

## Gerçek zamanda kaydedilmiş sessiz paper

Gerçekten saklanmış karşılaştırılabilir saat: **59**

| Coin | V7 kapanmış paper | V9.1 kapanmış paper |
|---|---:|---:|
| BTCUSDT | 0 | 0 |
| SOLUSDT | 0 | 0 |

Gerçek icra fiyatı doğrulanmış işlem: **0**.
Retest kapanışı anındaki geçmiş mum açılışı, GitHub'a sinyal yazıldığında çoğu zaman geçmiştedir.
Kapanış sonrası emir gerçekleştiği veya aynı fiyattan işlem yapılabildiği varsayılamaz.

### Karar kapıları (asgari tanısal örnek eşiği; tek başına istatistiksel kanıt değil)

- 168 doğrulanmış saat: **False**
- Her coin × iki sistem için en az 20 kapanmış paper işlem: **False**
- İşlem maliyeti stresini, maksimum düşüşü ve geç yayımlanmış sinyalleri ayrıca ölç.
- Bu eşikler geçse bile **otomatik gerçek işleme/bildirime geçiş yok**.

## Sonraki en önemli iş

Aynı saatte sinyal veren iki sistem için, gerçekten sinyalin görülebildiği zamandaki yürütülebilir giriş koşullarını tasarlayıp yeni forward sonuçlarda karşılaştırmak. Geçmişteki anlık next-open fiyatlarıyla kârlılık iddiası üretmemek.
