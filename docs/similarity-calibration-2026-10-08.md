# Eşik ve ağırlık güncellemesi — 8 Ekim 2026

Yeni varsayılanlar: **classical-hybrid-v2**, eşik **0,7500**; sözcük TF-IDF
**0,50**, karakter TF-IDF **0,25**, sözcük örtüşmesi **0,25**.

## Ölçüm ve seçim

Önceki eşik taraması ağırlıkları sabit tutuyordu. Bu güncelleme için aynı dört
metin çiftinin sabit regresyon etiketleriyle yedi ağırlık kombinasyonu yeniden
skorlandı; her biri 0–1 arasında 0,01 adımla değerlendirildi: **707 kombinasyon**.
Metinler ve etiketler değiştirilmedi.

Ağırlık değişimi her sinyal için en fazla ±0,05 ile sınırlandı; toplam tam 1,
her sinyal pozitif kaldı. Bu, küçük sete aşırı uyumu sınırlamak için kullanılan
bir mühendislik kısıtıdır; istatistiksel güven garantisi değildir.

Seçim sırası: F1, ardından en düşük pozitif skor ile en yüksek negatif skor
arasındaki fark, ardından mevcut ağırlıklara en küçük L1 uzaklığı. Eşik için
iki sınıftan da en az 0,05 skor marjı arandı; bu koşuldaki eşikler arasında eski
0,80'e en yakın değer seçildi. **0,05 marjı veriden öğrenilmiş optimum değil,
açıkça belirlenmiş bir tasarım tercihidir.** Bu nedenle 0,75 seçildi.

| Sözcük TF-IDF | Karakter TF-IDF | Örtüşme | Sınıf farkı |
|---:|---:|---:|---:|
| 0,45 | 0,30 | 0,25 | 0,507727 |
| 0,45 | 0,35 | 0,20 | 0,503422 |
| **0,50** | **0,25** | **0,25** | **0,510206** |
| 0,50 | 0,30 | 0,20 | 0,505901 |
| 0,50 | 0,35 | 0,15 | 0,501595 |
| 0,55 | 0,25 | 0,20 | 0,508379 |
| 0,55 | 0,30 | 0,15 | 0,504074 |

## Önce / sonra

| Örnek | Sabit etiket | v1 skor | v2 skor |
|---|---|---:|---:|
| Tam kopya | match | 1,000000 | 1,000000 |
| Küçük değişiklik | match | 0,800889 | 0,801247 |
| Ortak kalıp | no_match | 0,294988 | 0,291041 |
| İlgisiz metin | no_match | 0,004381 | 0,003651 |

| Gösterge | v1 (eşik 0,80) | v2 (eşik 0,75) |
|---|---:|---:|
| TP / FP / FN / TN | 2 / 0 / 0 / 2 | 2 / 0 / 0 / 2 |
| Precision / recall / F1 | %100 / %100 / %100 | %100 / %100 / %100 |
| Pozitif örneğin eşiğe en küçük marjı | 0,000889 | 0,051247 |
| Negatif örneğin eşiğe en küçük marjı | 0,505012 | 0,458959 |
| Sınıf farkı | 0,505901 | 0,510206 |

Eşik düşürme pozitif örnek için toleransı artırırken negatif sınıfın eşiğe
uzaklığını azaltır. Ağırlık değişimi bu sette ayrımı küçük miktarda artırır;
**F1 veya doğru karar sayısında artış yoktur**. Gerçek belgelerde yanlış
eşleşme oranının artmadığı bu dört örnekten çıkarılamaz. Bu ayarlar küçük
regresyon setine dayanan geçici prototip ayarlarıdır; bağımsız doğrulama gerekir.

## Uygulama ve geçmiş analizler

Settings, Compose fallback değerleri, `.env.example` ve yerel `.env` aynı
değerlere getirildi. Yeni analizler v2 etiketiyle bu ağırlıkları snapshot'a alır.
`20261008_12` migration'ı yalnız yeni kayıtlar için veritabanı varsayılan eşiğini
değiştirir; eski analizlere UPDATE uygulanmaz.

Worker v1/v2'nin ortak hesaplama kodunu, analizin kendi snapshot ağırlıklarıyla
çalıştırır. Önceki sürüm kontrolü yalnız aktif sürümü kabul ediyordu; v1
analizlerinin v2 worker altında devam edebilmesi için bu kontrol güncellendi.
Bilinmeyen snapshot sürümleri reddedilir. v1 fixture ve eski ölçüm çıktıları
korundu; v2 için ayrı `benchmark-v2.json` eklendi.

Regresyon testi, v1 ağırlıklarında reddedilen fakat v2 ağırlıklarında geçecek
bir çiftin eski snapshot ile hâlâ reddedildiğini doğrular. Ayrıca ortak fixture
örneklerinin metin ve etiketlerinin sürümler arasında aynı kaldığı kontrol edilir.

## Tekrar çalıştırma ve çıktılar

```powershell
& apps/api/.venv/Scripts/python.exe scripts/calibrate-similarity.py `
  --output docs/measurements/YENI-KALIBRASYON.json
```

Script ayar dosyalarını değiştirmez; v1 fixture'dan adayları hesaplar ve seçim
gerekçesini kaydeder. Tam skorlar, 707 eşikte bütün kararlar, politika ve
çalıştırma metadatası [kalibrasyon JSON'unda](measurements/2026-10-08-similarity-calibration.json).
Yerel hesaplama Python 3.14 ortamında yapıldı; golden skorlar gerçek API'nin
Python 3.13 ortamında da tolerans içinde doğrulandı.

Önceki [v1 eşik raporu](threshold-effects-2026-10-08.md) tarihsel karşılaştırmadır;
yeni varsayılan ayarları bu belge tanımlar. Süre/bellek ölçümleri yeniden
çalıştırılmadı; yeni eşik daha fazla eşleşme üretebileceğinden önceki süreler
v2 performans kanıtı sayılmaz.

## Doğrulama

- Docker backend: **284 passed, 26 skipped**. Atlananlar ayrı entegrasyon ortamı gerektiren testlerdir.
- Gerçek Playwright akışı: kayıt, giriş, yükleme, worker analizi, PDF raporu ve
  API ile silme **1 passed**.
- Ruff lint/format temiz; Pyright **0 hata, 0 uyarı**. Genel format kontrolündeki
  iki mevcut test dosyasının biçimi düzeltildi; davranışları değiştirilmedi.
- API ve worker'dan okunan aktif değerler: v2 / 0,7500 / 0,50–0,25–0,25.
  Veritabanı migration head: `20261008_12`.
- Docker'da yedi servis running; sağlık kontrolü olan altısı healthy.
- Commit veya push yapılmadı.
