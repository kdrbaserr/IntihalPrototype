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
5. PostgreSQL, Redis, MinIO, API ve web servislerini başlatır.
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

# Kod veya Dockerfile değişiminden sonra yeniden build et
docker compose up -d --build --wait
```

`docker compose down` veritabanı verisini silmez; named volume'lar korunur.
`-v` seçeneği volume'ları ve yerel verileri de siler, bu nedenle bilinçli
kullanılmalıdır.

## Sorun giderme

- `docker info` hata veriyorsa Docker Desktop henüz çalışmıyordur.
- Bir port kullanımda hatası alırsan `.env` içindeki ilgili dış portu değiştir.
- Bir servis sağlıksız görünürse `docker compose logs servis-adi` ile logunu incele.
- Ayarların Compose'a nasıl işlendiğini görmek için `docker compose config` çalıştır.
