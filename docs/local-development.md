# Yerel geliştirme kurulumu

Bu proje API, web arayüzü ve bağımlı servisleri Docker Compose ile birlikte
çalıştırır. Yerel makineye PostgreSQL, Redis veya MinIO kurmak gerekmez.

## Gereksinimler

- Git
- Docker Desktop (Windows/macOS) veya Docker Engine + Compose eklentisi (Linux)

Docker Desktop'ı açtıktan sonra proje kökünde aşağıdaki tek komuttan işletim
sistemine uygun olanı çalıştır.

Windows:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup.ps1
```

Linux/macOS:

```sh
sh scripts/setup.sh
```

Script şu sırayı izler:

1. Docker komutunun kurulu ve Docker motorunun çalışır olduğunu kontrol eder.
2. `.env` yoksa `.env.example` dosyasını kopyalar; varsa mevcut ayarları korur.
3. Compose dosyasını ve ortam değişkenlerini doğrular.
4. API ve web image'larını build eder.
5. PostgreSQL, Redis, MinIO, API, Celery worker, scheduler ve web servislerini başlatır.
6. Healthcheck'ler başarılı olana kadar en fazla 300 saniye bekler.

## `.env.example` ve `.env` farkı

`.env.example`, gereken değişkenlerin güvenli örneklerini gösteren ve Git'e
eklenen şablondur. `.env` ise kendi bilgisayarındaki gerçek ayarları içerir ve
`.gitignore` sayesinde Git'e gönderilmez. Yeni bir değişken eklendiğinde şablon
da güncellenmelidir.

## Ortam değişkenleri

| Değişken | Örnek değer | Görevi |
| --- | --- | --- |
| `API_PORT` | `8000` | FastAPI'nin bilgisayarda açıldığı port |
| `WEB_PORT` | `3000` | Next.js arayüzünün bilgisayarda açıldığı port |
| `INTIHAL_APP_NAME` | `Intihal Prototype API` | API'nin görünen adı |
| `INTIHAL_APP_VERSION` | `0.1.0` | API sürümü |
| `INTIHAL_ENVIRONMENT` | `local` | Çalışma ortamı adı |
| `INTIHAL_DEBUG` | `true` | Yerel hata ayıklama modu |
| `INTIHAL_API_V1_PREFIX` | `/api/v1` | Sürümlü API yollarının ön eki |
| `NEXT_PUBLIC_API_BASE_URL` | `http://localhost:8000/api/v1` | Tarayıcının API'ye eriştiği adres |
| `POSTGRES_DB` | `intihal` | PostgreSQL veritabanı adı |
| `POSTGRES_USER` | `intihal_app` | PostgreSQL kullanıcı adı |
| `POSTGRES_PASSWORD` | yerel örnek şifre | PostgreSQL parolası |
| `POSTGRES_PORT` | `5432` | PostgreSQL'in bilgisayara açılan portu |
| `REDIS_PASSWORD` | yerel örnek şifre | Redis parolası |
| `REDIS_PORT` | `6379` | Redis'in bilgisayara açılan portu |
| `MINIO_ROOT_USER` | `intihal_minio` | MinIO yönetici kullanıcı adı |
| `MINIO_ROOT_PASSWORD` | yerel örnek şifre | MinIO yönetici parolası |
| `MINIO_API_PORT` | `9000` | MinIO S3 API portu |
| `MINIO_CONSOLE_PORT` | `9001` | MinIO yönetim paneli portu |

Port değiştirirsen bağlantılı adresi de güncelle. Örneğin `API_PORT=8100`
yaparsan `NEXT_PUBLIC_API_BASE_URL=http://localhost:8100/api/v1` olmalıdır.

## Günlük Docker komutları

```powershell
# Servislerin durumunu göster
docker compose ps

# Tüm logları canlı izle
docker compose logs -f

# Sadece API logunu izle
docker compose logs -f api

# Servisleri durdur ve container'ları kaldır
docker compose down

# Dockerfile, bağımlılık veya migration dosyaları değiştiğinde image'ları güncelle
docker compose up -d --build --wait

# Yeni migration'ları uygula
docker compose exec -T api alembic upgrade head

# Kaynak kod değişiminden sonra worker ve scheduler'ı yenile
docker compose restart worker scheduler

# Container'ların anlık CPU ve bellek kullanımını göster
docker stats --no-stream
```

`docker compose down` veritabanı verisini silmez; named volume'lar korunur.
`-v` seçeneği volume'ları ve yerel verileri de siler, bu nedenle bilinçli
kullanılmalıdır.

Web ve API kaynak kodu bind mount üzerinden container'a bağlanır; bu servisler
kod değişikliklerini otomatik yükler. Dockerfile çalışma ortamının tarifidir ve
her özellik eklendiğinde değişmesi gerekmez. Migration dosyaları image'a kopyalandığı
için kaynak kodun güncel olması, container'daki migration'ların da güncel olduğu
anlamına gelmez. `healthy` sonucu da yalnızca servis sağlık kontrolünü doğrular;
kayıt, analiz, rapor ve silme akışları ayrıca sınanmalıdır.

## Gerçek servislerle uçtan uca test

Compose servisleri çalışır, migration'lar uygulanmış ve sentetik örnek kaynak havuzu
hazır olmalıdır. Ardından:

```powershell
cd apps/web
npm run test:e2e:live
```

Bu test API isteklerini taklit etmez. Tarayıcıdan yeni bir test hesabı açar, giriş
yapar, sayfa yenilenince oturumu doğrular, 7 gün saklama ile TXT yükler, Celery
analizini bekler, pozitif eşleşme ve yazdırılabilir PDF raporunu kontrol eder.
Silme düğmesi henüz arayüzde olmadığı için silmeyi aynı oturumla gerçek API
üzerinden sınar; belge ve raporun 404 dönmesini, listeden çıkmasını ve tekrarlanan
silmenin 204 dönmesini doğrular. Çıkış sonrası oturumun 401 döndüğünü de kontrol eder.

Test dosyasını siler; test hesabı ve denetim için tutulan belge metadatası kalır.
Başarılı koşunun PDF'i `apps/web/test-results/live/` altında, HTML raporu
`apps/web/playwright-report/live/` altında oluşur. Başarısız koşularda ekran
görüntüsü ve Playwright trace kaydedilir. Varsayılan adresler localhost:3000 ve
localhost:8000/api/v1; gerektiğinde `E2E_WEB_URL` ve `E2E_API_URL` ile değiştirilebilir.

`npm run test:e2e` ise ayrı geliştirme sunucusunda, taklit API ile arayüzün
hata/yeniden deneme senaryolarını kontrol eder.

Fiziksel temizliği ayrıca okumak için test raporundaki `live-identifiers`
ekinden belge ve analiz UUID'lerini alıp proje kökünde çalıştır:

```powershell
Get-Content -Raw scripts/verify-document-cleanup.py | docker compose exec -T api python - BELGE_UUID ANALIZ_UUID
```

Bu salt okunur kontrol belge metadatasının `deleted`/`cleaned_at` durumunu,
analiz/eşleşme/metin parçalarının sıfır kaldığını ve MinIO'nun `NoSuchKey`
döndüğünü doğrular.

## Sorun giderme

Worker komutları, kuyruk isimleri ve timeout/retry politikası için
[worker notlarına](worker-queues.md) bak. Worker kod değişikliklerinde otomatik
reload yapmaz; `docker compose restart worker` gerekir.

- `docker info` hata veriyorsa Docker Desktop henüz çalışmıyordur.
- Bir port kullanımda hatası alırsan `.env` içindeki ilgili dış portu değiştir.
- Bir servis sağlıksız görünürse `docker compose logs servis-adi` ile logunu incele.
- Ayarların Compose'a nasıl işlendiğini görmek için `docker compose config` çalıştır.

## Giriş ve roller

Parola hashleme, cookie oturumu, user/admin rolleri ve admin oluşturma komutu için
[kimlik doğrulama ve mimari notlarını](authentication.md) okuyun. Normal hesap web ekranından açılır;
admin sunucu komutuyla atanır. Eski hesaplara parola atanması gerekir.
