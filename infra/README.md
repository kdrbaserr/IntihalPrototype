# Infrastructure

Bu klasör uygulamanın yerel altyapı yapılandırmalarını barındıracaktır.

Planlanan servisler:

- PostgreSQL: kullanıcı, belge metadata'sı ve analiz sonuçları,
- Redis: Celery görev kuyruğu ve geçici durum bilgisi,
- MinIO: yüklenen belge dosyalarının nesne depolaması,
- API ve Web container'ları: uygulamaların tutarlı ortamda çalışması.

Sonraki altyapı adımında `compose.yaml`, Dockerfile'lar, healthcheck'ler ve
kalıcı volume tanımları eklenecektir.

## Yerel servisleri çalıştırma

Proje kökünde örnek ortam dosyasını yerel `.env` dosyasına kopyalayın:

```powershell
Copy-Item .env.example .env
```

Ardından servisleri oluşturup arka planda başlatın:

```powershell
docker compose up -d --build
```

Durumu kontrol edin:

```powershell
docker compose ps
```

Servis adresleri:

- PostgreSQL: `localhost:5432`
- Redis: `localhost:6379`
- MinIO S3 API: `http://localhost:9000`
- MinIO yönetim ekranı: `http://localhost:9001`

Logları canlı izlemek için:

```powershell
docker compose logs -f
```

Servisleri durdurmak için:

```powershell
docker compose down
```

`docker compose down` verileri silmez. Yerel verileri de tamamen silmek için
ayrıca `--volumes` kullanılması gerekir; bu işlem geri alınamaz.

## MinIO topluluk sürümü notu

MinIO'nun eski topluluk container imajı artık herkese açık kayıt defterinde
dağıtılmadığı için son açık kaynak sürüm resmi GitHub etiketinden
`infra/minio/Dockerfile` ile derlenir. Bu kurulum yerel geliştirme içindir;
production dağıtımı olarak kullanılmamalıdır.
