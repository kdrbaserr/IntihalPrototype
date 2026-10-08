# Belge süre ve bellek ölçümleri — 8 Ekim 2026

Başlangıç: `2026-10-08T22:13:54.335685+03:00`. Çalışan kod: `c0c0aa4602c84a491d3ac199b4c4366fe9433a18`.

Gerçek API, PostgreSQL, MinIO, Redis, scheduler ve Celery worker kullanıldı. Her boyut üç kez, küçük → orta → büyük sırasıyla seri çalıştırıldı. Dokuz analizin tamamı başarılı oldu; test belgelerinin tamamı DELETE sonrası 404 ile doğrulandı. Hesap ve belge denetim metadatası korunur.

Ardından dokuz belgenin tamamı için doğrudan PostgreSQL/MinIO kontrolü yapıldı:
`cleaned_at` dolu, belge durumu `deleted`, bağlı metin parçası/analiz/eşleşme sayıları
sıfır ve dosya sorgusu `NoSuchKey` oldu.

| Boyut | Kelime | Medyan toplam (sn) | Min–maks (sn) | İşleme penceresi (sn) | Worker bellek tepe (MiB) | Başlangıca göre en büyük artış (MiB) | API bellek tepe (MiB) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Küçük — 10 KiB | 1153 | 20.706 | 20.373–30.721 | 16.294 | 404.49 | 54.94 | 171.91 |
| Orta — 100 KiB | 11773 | 41.531 | 40.326–41.556 | 27.347 | 402.02 | 55.15 | 171.37 |
| Büyük — 1 MiB | 120601 | 147.576 | 144.806–148.980 | 143.649 | 397.95 | 144.43 | 206.81 |

## Yöntem ve sınırlar

- Toplam süre yükleme isteğinin başlangıcından terminal durumun görülmesine kadardır. Kuyruk beklemesi dahildir; 250 ms polling küçük bir gözlem gecikmesi ekler.
- İşleme penceresi sunucunun analysis.started_at / completed_at farkıdır. Metin çıkarma başlangıcından itibaren ölçülür ve iki worker aşaması arasındaki kuyruk beklemesini de içerir; saf CPU süresi değildir.
- Bellek 100 ms aralıklarla /sys/fs/cgroup/memory.current üzerinden örneklenmiştir. Tabloda üç koşunun en yüksek gözlenen değeri vardır; kısa süreli daha yüksek bir tepe kaçabilir. Cache ve yaklaşık küçük bir sampler maliyeti dahildir.
- JSON ayrıca worker süreçlerinin toplam RSS değerlerini tutar. Paylaşılan sayfalar birden fazla kez sayılabildiği için bu sayı container belleğiyle aynı değildir. API RSS yalnız başlatıcı süreci kapsadı; karşılaştırmada API cgroup belleği kullanıldı.
- Worker yeniden başlatılmadığı için önceki büyük belgelerden kalan tahsisler küçük belge koşularının başlangıç belleğini yükseltebilir. Her koşunun başlangıcı ve tepe değeri ham JSON içinde ayrı saklanır.
- Sentetik TXT içerik, proje örnek havuzundaki Türkçe metnin tekrarıdır; gerçek PDF/DOCX sayfa düzeni, OCR, kaynak havuzu büyümesi veya çok kullanıcılı yük ölçülmedi.
- Rapor süresi yalnız ilk eşleşme sayfasının limit=1 isteğidir; tüm raporun tarayıcıda çizilmesi veya PDF çıktısı bu ölçümün dışında kalır.

## Ortam

- Docker VM: 16 mantıksal CPU, 7,609 GiB RAM; worker concurrency: 2.
- Kaynak havuzu: lisansı geçerli ve hazır 3 belge / 13 parça.
- Algoritma: classical-hybrid-v1, eşik: 0.8000; scheduler dispatch: 15 saniye.
- Worker soft/hard timeout: 240 / 300 saniye.
- Python: API ve worker 3.13.16; SQLAlchemy: API 2.1.4, worker 2.1.3.

## Dosyalar ve tekrar çalıştırma

- [Ham JSON](measurements/2026-10-08-document-performance.json): dokuz koşu, belge/analiz UUID, süre, başlangıç/tepe bellek ve silme sonucu.
- [Özet CSV](measurements/2026-10-08-document-performance.csv): boyut başına özet.

Proje kökünde:

```powershell
python scripts/measure-document-performance.py --output docs/measurements/YENI-KOSU.json
```

Çalışan Compose, uygulanmış migration ve sentetik örnek kaynak havuzu gerekir. Script yeni test hesabı açar ve yalnız kendi oluşturduğu belgeleri siler. Ölçüm sırasında kaynak kodu değiştirme veya worker/API yeniden başlatma yapma. Her koşuda 9 yükleme yapılır; hesabın 10 yükleme/saat kotası aşılmaz.

Bulgular: dosya büyüdükçe süre ve ek bellek artıyor. Küçük/orta belgelerde 15 saniyelik dispatcher periyodu toplam sürenin önemli bir kısmını oluşturabiliyor. Büyük belgenin 13.401 parçalık karşılaştırması worker CPU yükünü yaklaşık bir çekirdeğe çıkarıyor. Bu sonuçlar üç küçük kaynakla yapılan yerel ölçümlerdir; üretim kapasitesi olarak yorumlanmamalıdır.
