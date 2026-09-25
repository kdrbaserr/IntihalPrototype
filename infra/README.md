# Infrastructure

Bu klasör uygulamanın yerel altyapı yapılandırmalarını barındıracaktır.

Planlanan servisler:

- PostgreSQL: kullanıcı, belge metadata'sı ve analiz sonuçları,
- Redis: Celery görev kuyruğu ve geçici durum bilgisi,
- MinIO: yüklenen belge dosyalarının nesne depolaması,
- API ve Web container'ları: uygulamaların tutarlı ortamda çalışması.

Sonraki altyapı adımında `compose.yaml`, Dockerfile'lar, healthcheck'ler ve
kalıcı volume tanımları eklenecektir.
