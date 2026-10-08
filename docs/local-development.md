# Yerel geliştirme kurulumu

Bu proje API, web arayüzü ve bağımlı servisleri Docker Compose ile birlikte
çalıştırır. Yerel makineye PostgreSQL, Redis veya MinIO kurmak gerekmez.

## Gereksinimler

- Git
- Docker Desktop (Windows/macOS) veya Docker Engine + Compose eklentisi (Linux)

Docker Linux container modu ve Compose v2 (`docker compose`) gerekir; script
`up --wait` desteğini kullanır. İlk build paket/image/Go kaynaklarını indireceği
için internet ve boş Docker disk alanı gerekir. Minimum RAM/CPU belirlenmedi;
[ölçüm ortamı](document-performance-2026-10-08.md) minimum sistem gereksinimi değildir.
Yalnız Docker kurulumu için host Python/Node gerekmez. Host'ta geliştirme/test
isteğe bağlıdır: API için Python 3.13, web için Node 22; multipart API örneği için
PowerShell 7 kullanın. Windows kurulum scripti Windows PowerShell ile de çalışır.

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
4. API/worker/scheduler, web ve MinIO image'larını build eder.
5. PostgreSQL, Redis, MinIO, API, Celery worker, scheduler ve web servislerini başlatır.
6. Healthcheck'ler başarılı olana kadar en fazla 300 saniye bekler.
7. `alembic upgrade head` uygular; güncel head `20261008_12`.
8. TXT/PDF/DOCX biçiminde üç sentetik izinli kaynak oluşturur; tekrarında çoğaltmaz.
9. Web'den hesap açabileceğin adresleri gösterir; varsayılan admin/parola üretmez.

Varsayılan adresler web `http://localhost:3000`, API `http://localhost:8000`,
OpenAPI `http://localhost:8000/docs`, MinIO paneli `http://localhost:9001`.
Kayıt → giriş → yükleme (7/30 gün) → analiz → kaynak/kanıt inceleme → yazdırma
akışı kullanılabilir. Silme API'dedir. [API rehberi](api-reference.md).

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
Web origin değişirse `INTIHAL_CORS_ORIGINS` JSON listesi de güncellenmelidir.
Cookie davranışı için localhost ve 127.0.0.1 adreslerini bir oturumda karıştırmayın.

### Analiz ve worker ayarları

| Ayar | Varsayılan | Davranış |
|---|---|---|
| `INTIHAL_ALGORITHM_VERSION` | classical-hybrid-v2 | Yeni analiz sürümü |
| `INTIHAL_SIMILARITY_THRESHOLD` | 0.7500 | Ham chunk skoru bu değere eşit/büyükse değerlendirilir |
| `INTIHAL_WORD_TFIDF_WEIGHT` | 0.50 | Sözcük TF-IDF |
| `INTIHAL_CHARACTER_TFIDF_WEIGHT` | 0.25 | Karakter TF-IDF |
| `INTIHAL_WORD_OVERLAP_WEIGHT` | 0.25 | Sözcük kümesi örtüşmesi; toplam ağırlık tam 1 |
| `INTIHAL_SESSION_TTL_SECONDS` | 28800 | Sabit 8 saat oturum ömrü |
| `INTIHAL_WORKER_CONCURRENCY` | 2 | Paralel worker işi |
| `INTIHAL_TASK_SOFT_TIMEOUT_SECONDS` / `HARD_TIMEOUT_SECONDS` | 240 / 300 | Worker işlem sınırları |
| `INTIHAL_TASK_MAX_RETRIES` | 3 | Geçici iş hatasında otomatik retry |

Kök `.env` Compose tarafından okunur. Host API `apps/api/.env` veya process
ortamını okur; kökteki `.env` otomatik olarak aynı host API ayarı değildir.
Compose içinde database/Redis/MinIO adresleri servis adlarıdır; host API için
localhost ve yayınlanan portları kullanın. `.env` veya Compose environment
değişirse `restart` yeterli değildir; `docker compose up -d api worker scheduler`
ile container'lar yeni environment almalıdır. Script mevcut `.env`'yi koruduğu
için eski kurulumun v1 override değerleri otomatik v2'ye dönüşmez.

TLS/HTTPS, Secure cookie, secret rotasyonu, backup ve açık scanner bulguları
çözülmeden bu geliştirme Compose dosyasını üretim kurulumu olarak kullanmayın.
API health yalnız canlılığı ölçer. [Riskler](risks.md), [veri politikası](data-policy.md).

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
- Yapılandırmayı secret değerlerini yazdırmadan doğrulamak için `docker compose config --quiet` kullan.
  Tam `docker compose config` çıktısı parolaları içerebilir; log/ticket'e kopyalama.
- `queued` durumunda API/worker/scheduler ve Redis'i kontrol et; scheduler dispatcher'ı
  15 saniyede bir çalıştırır. Beat yalnız bir instance olarak tutulmalıdır.
- Migration hatasında image'daki migration dosyalarını güncelle: build → up →
  `alembic upgrade head`; yalnız API kaynak reload'u yeterli değildir.
- Oturum 401/403 ise cookie, CSRF, origin ve hesap durumunu ayır; [API hata tablosuna](api-reference.md) bak.
- Varsayılan altyapı portları yalnız loopback'e sabitlenmemiştir; yerel ağ/firewall
  erişimini kontrol et. Named volume'lar yedek değildir; `down -v` veri siler.

## Kontroller

Proje kökünde, mevcut kaynak/image eşleşmesi sağlandıktan sonra:

```powershell
docker compose config --quiet
docker compose ps
docker compose exec -T api alembic current
docker compose exec -T api alembic heads
docker compose exec -T api ruff check .
docker compose exec -T api ruff format --check .
docker compose exec -T api pytest -o addopts= -q
docker compose exec -T web npm run lint
docker compose exec -T web npm run typecheck
docker compose exec -T web npm test
```

API testleri/migration'lar image'a kopyalanır; kaynak bind mount'u bunları yenilemez.
Host tarayıcı testinden önce `cd apps/web`, `npm ci`, `npm run test:e2e:install`
ile bağımlılık/Chromium hazırla; ardından `npm run test:e2e:live` çalıştır.
API/docs bağlantı, kaynak seed ve worker hazır olmalıdır. Gerçek PostgreSQL/MinIO
güvenlik kontrolleri ayrı [entegrasyon runner'ıdır](security-tests.md); genel pytest
skip sonuçları bu kontroller geçti anlamına gelmez.

Süre/bellek ve eşik komutları [scripts rehberinde](../scripts/README.md).
GitHub'da `.github/workflows/ci.yml` test/build; `security.yml` bağımlılık,
production container ve secret işleri içerir. Main push/PR ve manuel tetikleyici
vardır. [Yerel güvenlik raporu](security-ci-2026-10-08.md) uzak run kanıtı değildir.

## Güncelleme ve admin

Kaynak güncellemesinden sonra:

```powershell
docker compose up -d --build --wait --wait-timeout 300
docker compose exec -T api alembic upgrade head
docker compose exec -T api python -m intihal_api.corpus.sample_seed
docker compose exec -T api alembic current
```

Seed yalnız local/test içindir; mevcut pasif kaynakları tekrar etkinleştirmez.
DB migration veya dependency güncellemesi öncesinde kalıcı verinin uygun yedeği
ve rollback kararı olmalıdır; bu projede otomatik backup/restore aracı yoktur.
Veritabanı/default değişimi eski config snapshot'larını yeniden yazmaz.

Admin provisioning interaktif parola ister; `-T` kullanmayın:

```powershell
docker compose exec api python -m intihal_api.db.manage_user admin@example.test --name "Yönetici" --role admin
```

Mevcut e-postada parola/rol/adı günceller, eski oturumları iptal eder; disabled
kullanıcıyı otomatik etkinleştirmez. Parolayı komut argümanına koymayın.

## Giriş ve roller

Parola hashleme, cookie oturumu, user/admin rolleri ve admin oluşturma komutu için
[kimlik doğrulama ve mimari notlarını](authentication.md) okuyun. Normal hesap web ekranından açılır;
admin sunucu komutuyla atanır. Eski hesaplara parola atanması gerekir.
