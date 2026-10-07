# Güvenlik ve kalıcı silme testleri

`tests/test_security_regressions.py` HTTP API üzerinden şu senaryoları doğrular:

- USER ve ADMIN rollerindeki başka kullanıcı, sahte `X-User-ID` gönderse bile
  belge/analiz/eşleşme okuyamaz, analiz başlatamaz, retry yapamaz veya silemez.
- Süresi dolmuş, iptal edilmiş, değiştirilmiş, bilinmeyen ve uzun token;
  session digest'inin cookie olarak kullanılması ve yalnız Bearer başlığı
  tüm korumalı belge/analiz işlemlerinde 401 üretir. Veri ve MinIO durumu değişmez.
- Parola/rol yönetimi iki ayrı tarayıcı oturumunu da iptal eder; yeni parola gerekir.
- Başka kullanıcı, sahibinin yarım kalmış silmesini devam ettiremez.
- Token ve parola tanı loglarına/yanıtlara yazılmaz.

`tests/test_security_integration.py` gerçek PostgreSQL ve MinIO kullanır:

- Gerçek session/owner sorguları USER ve ADMIN için aynı sahiplik sınırını uygular.
  MinIO nesnesine anonim doğrudan HTTP erişimi 403 üretir.
- Gerçek session digest replay, değiştirilmiş cookie, logout sonrası replay ve
  sona ermiş oturum engellenir; diğer kullanıcının oturumu logout'tan etkilenmez.
- İki silme isteği MinIO adımında aynı anda bekletilir. PostgreSQL satır kilitleri
  yalnız bir `started` ve bir `succeeded` audit kaydı bırakmalıdır.
- Silme sonrası gerçek MinIO `stat_object` çağrısı `NoSuchKey` döndürür; chunk,
  analiz ve eşleşme satırları yoktur. Kaynak dosyası ve kaynak chunk'ı korunur.
  Belgenin `deleted` metadata kaydı ve audit geçmişi kalır.
- Önceden kuyruklanmış worker görevleri silme sonrası `skipped` döner; dispatcher
  belgeyi yeniden kuyruklamaz ve silinen içerik geri oluşmaz.
- MinIO arızası veya nesne silindikten sonraki DB commit arızası enjekte edilir.
  API belgeyi gizler; aynı sahibin tekrar isteği kalıcı temizliği tamamlar.

## Çalıştırma

Proje kökünden, yerel Docker servisleri açıkken:

```powershell
docker compose cp apps/api/tests/. api:/app/tests
docker compose exec -T api python tests/run_security_integration.py
```

Runner her çalışmada yeni `intihal_security_test_<uuid>` veritabanı ve
`intihal-security-test-<uuid>` bucket oluşturur. Yalnız sentetik dosyalar kullanılır.
Test fixture'ı bu namespace dışında bir hedefi reddeder. Test başarılı veya
başarısız olsa da runner yalnız kendi oluşturduğu kaynakları `finally` içinde
temizler ve kaldırıldıklarını doğrular. Normal uygulama veritabanına/bucket'ına
test verisi yazılmaz. Runner için yerel DB rolünün CREATE DATABASE ve MinIO
kimliğinin bucket oluşturma/silme yetkisi gerekir.

Genel pytest çalışmasında entegrasyon ortamı sağlanmadıysa gerçek altyapı testleri
skip olur. SQLite testleri gerçek PostgreSQL satır kilitlerini veya MinIO'nun
fiziksel silmesini doğrulamaz; ayrı runner bu farkı kapatır.
