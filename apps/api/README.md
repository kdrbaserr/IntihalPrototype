# API

Bu klasör projenin FastAPI tabanlı backend uygulamasını barındıracaktır.

API'nin sorumlulukları:

- kullanıcı ve yetki kontrollerini yürütmek,
- belge yükleme ve analiz isteklerini kabul etmek,
- PostgreSQL ve MinIO ile iletişim kurmak,
- Celery görevlerini başlatmak,
- analiz durumu ve benzerlik sonuçlarını web uygulamasına sunmak.

Sonraki adımda burada temel FastAPI uygulaması ve `/health` endpoint'i
oluşturulacaktır.
