# Etiketli sette eşik etkisi — 8 Ekim 2026

Bu rapor v1 ayarlarının tarihsel ölçümüdür. Güncel v2 eşik/ağırlıkları için
[kalibrasyon raporunu](similarity-calibration-2026-10-08.md) okuyun.

Set: `classical-similarity-benchmark-v1`; algoritma: `classical-hybrid-v1`.
Çalıştırma (UTC): `2026-10-08T19:37:59.637523+00:00`; kaynak commit: `5bed47a750f75b0c9e0e0d0104571ff7e87e2895`.
Python: `3.13.16`; ortam: `Docker Compose API Python runtime`.

## Yöntem ve kapsam

Mevcut 4 sentetik metin çifti yeniden skorlandı. Etiketler fixture içindeki
`expected.threshold_decision` alanından sabit alındı; taranan eşikten türetilmedi.
Bunlar bağımsız uzmanların intihal kararları değil, regresyon beklentileridir.
İki pozitif (kopya/küçük değişiklik), iki negatif (kalıp/ilgisiz) örnek vardır.
Ağırlıklar: sözcük TF-IDF 0,50; karakter TF-IDF 0,30; sözcük örtüşmesi 0,20.
Karar üretimdeki gibi ham skor ≥ eşik karşılaştırmasıyla verildi. Veritabanına
yazılan dört basamaklı yuvarlanmış skor karar için kullanılmadı.
0–1 arasında 0,01 adımlı tarama ve kritik sınırlar: 113 eşik.
Her örneğin tam skorunda; 1,0 dışındakilerin 0,000000000001 üzerinde de karar kontrol edildi.
JSON bütün skorları/kararları; CSV her eşikte metrikleri içerir.

## Yeniden hesaplanan skorlar

| Örnek | Sabit etiket | Ham skor |
|---|---|---:|
| exact-copy-v1 | match | 1.000000000000 |
| minor-edit-v1 | match | 0.800888539505 |
| shared-template-v1 | no_match | 0.294987972419 |
| unrelated-topics-v1 | no_match | 0.004381461071 |

Bütün skorlar fixture toleransı (0,000001) içinde kaldı.

## Eşik karşılaştırması

TP: doğru eşleşme; FP: yanlış eşleşme; FN: kaçırılan eşleşme; TN: doğru ret.
Precision = TP/(TP+FP); recall = TP/(TP+FN); F1 = 2TP/(2TP+FP+FN).
Accuracy = (TP+TN)/N; specificity = TN/(TN+FP). Sıfır payda JSON/CSV'de boş/null.

| Eşik | TP | FP | FN | TN | Precision | Recall | F1 | Accuracy |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 2 | 2 | 0 | 0 | 50.0% | 100.0% | 66.7% | 50.0% |
| 0.005 | 2 | 1 | 0 | 1 | 66.7% | 100.0% | 80.0% | 75.0% |
| 0.25 | 2 | 1 | 0 | 1 | 66.7% | 100.0% | 80.0% | 75.0% |
| 0.2949 | 2 | 1 | 0 | 1 | 66.7% | 100.0% | 80.0% | 75.0% |
| 0.2950 | 2 | 0 | 0 | 2 | 100.0% | 100.0% | 100.0% | 100.0% |
| 0.3 | 2 | 0 | 0 | 2 | 100.0% | 100.0% | 100.0% | 100.0% |
| 0.5 | 2 | 0 | 0 | 2 | 100.0% | 100.0% | 100.0% | 100.0% |
| 0.75 | 2 | 0 | 0 | 2 | 100.0% | 100.0% | 100.0% | 100.0% |
| 0.8 | 2 | 0 | 0 | 2 | 100.0% | 100.0% | 100.0% | 100.0% |
| 0.8008 | 2 | 0 | 0 | 2 | 100.0% | 100.0% | 100.0% | 100.0% |
| 0.8009 | 1 | 0 | 1 | 2 | 100.0% | 50.0% | 66.7% | 75.0% |
| 0.801 | 1 | 0 | 1 | 2 | 100.0% | 50.0% | 66.7% | 75.0% |
| 0.85 | 1 | 0 | 1 | 2 | 100.0% | 50.0% | 66.7% | 75.0% |
| 1 | 1 | 0 | 1 | 2 | 100.0% | 50.0% | 66.7% | 75.0% |

## Bulgular ve sınırlar

- Bu sette hatasız aralık: **0.29498797241906877 < eşik ≤ 0.8008885395053242**.
  Alt sınır dahil değildir: kalıp skoru eşik ile eşitse yanlış eşleşme olur.
- Mevcut eşik `0.8000` bu aralıkta; 2/2 pozitif yakalanır, 2/2 negatif reddedilir.
- Küçük değişiklik örneğinin mevcut eşiğe marjı yalnızca 0.000888539505.
  0,8008 geçerken 0,8009 ve 0,801 bu örneği kaçırır; recall %50'ye iner.
- 0,2949 ortak kalıbı yanlış eşleşme kabul eder; 0,2950 reddeder.
- 1,0 tam kopyayı kabul eder; karşılaştırma ≥ olduğu için sınırdaki skor elenmez.
- Tek bir hata accuracy'yi 25 puan değiştirir. Test/kalibrasyon ayrımı, bağımsız
  doğrulama seti, gerçek belge/uzunluk/dil çeşitliliği veya güvenilir saha tahmini yoktur.
  Bu setten üretim için optimum eşik ya da genel başarı oranı çıkarılamaz.
- Çalışma bir skor/karar deneyi; aday kaynak bulma, parçalama ve belge geneli
  benzerlik yüzdesinin doğruluğunu ölçmez. Eşik veya ağırlık ayarı değiştirilmedi.

## Tekrar çalıştırma

Proje kökünde (API bağımlılıkları kurulu ortam):

```powershell
& apps/api/.venv/Scripts/python.exe scripts/evaluate-similarity-thresholds.py `
  --revision (git rev-parse HEAD) --output docs/measurements/2026-10-08-threshold-effects `
  --report docs/threshold-effects-2026-10-08.md
```

Fixture SHA-256: `e53de452c2d5b432654e01538ecdaeee81fb57336fa9f88f9504072d6304618c`.
