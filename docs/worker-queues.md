# Worker, queue, timeout ve retry notları

## Bu adımda eklenenler

Redis broker ve result backend kullanan Celery uygulaması, Compose worker servisi,
üç açıkça tanımlanmış kuyruk, zaman sınırları ve sınırlı retry politikası eklendi.
Worker, Linux container içinde `prefork` process havuzuyla çalışır; Windows üzerinde
doğrudan worker çalıştırmak yerine Docker kullanılır. Varsayılan concurrency 2'dir.

Belge yükleme ve kaynak işleme endpoint'lerinin mevcut akışı değişmedi.
`documents` ve `analysis` kuyrukları sonraki iş görevleri için hazırdır; bu adımda
gerçek görev olarak yalnızca `intihal.healthcheck` kayıtlıdır. Kuyruk tanımlamak,
belge işleme kodunu kendiliğinden asenkron hale getirmez.

## ⭐ Not al: olay örgüsü

Çalışır durumdaki altyapı kontrolünün akışı:

1. Producer, `intihal.healthcheck` görevini Celery üzerinden gönderir.
2. Routing kuralı görevi `intihal.default` kuyruğuna yollar.
3. Redis broker mesajı saklar; worker mesajı alır.
4. Worker görevi çalıştırır ve `{"status": "ok"}` sonucunu üretir.
5. Result backend sonucu ayrı Redis veritabanında, varsayılan 24 saat tutar.
6. Producer, task ID ile sonucu okuyabilir.

İleride hedeflenen belge akışı: dosyayı MinIO'ya yaz → belge kaydını PostgreSQL'e
commit et → kuyruğa belge ID'sini gönder → worker dosyayı ID üzerinden oku → metni
çıkar → analiz görevini gönder → sonucu PostgreSQL'e kaydet. Dosya içeriğini ve
SQLAlchemy session nesnesini kuyruk mesajına koyma. İşin kalıcı sonucu PostgreSQL'de
olmalı; süresi dolan Celery sonucu raporun kendisi değildir.

## Kuyruklar ve routing

| Kuyruk | Görev adı kuralı | Amaç |
| --- | --- | --- |
| `intihal.default` | `intihal.healthcheck` ve yönlendirilmemiş görevler | Altyapı kontrolü ve genel işler |
| `intihal.documents` | `intihal.documents.*` | İleride belge/metin çıkarma işleri |
| `intihal.analysis` | `intihal.analysis.*` | İleride benzerlik hesaplama işleri |

⭐ **Routing:** Görev adından hangi kuyruğa gidileceğini belirleyen kuraldır.
Yanlış yazılan kuyruk isimleri otomatik oluşturulmaz; açık hata verir.
Tek worker üç kuyruğu da dinler. Ayrı isimler şu an CPU izolasyonu sağlamaz;
gerektiğinde her kuyruk için ayrı worker başlatılabilir. Bu kuyruklar arasında
katı öncelik veya tüm görevler için tamamlanma sırası garantisi verilmez.

⭐ **Concurrency:** Aynı anda çalışan görev sayısıdır. Varsayılan 2 process.
⭐ **Prefetch:** Worker'ın önceden ayırdığı mesaj sayısını etkiler. Çarpan 1 seçildi;
uzun işlerde bir worker'ın çok fazla mesajı önceden sahiplenmesini azaltır.

## Zaman sınırları

| Ayar | Varsayılan | Davranış |
| --- | --- | --- |
| Soft timeout | 240 saniye | `SoftTimeLimitExceeded` ile kontrollü kapanma fırsatı |
| Hard timeout | 300 saniye | Çalışan worker alt process'i zorla sonlandırılır |
| Redis bağlantı/okuma timeout | 5 saniye | Ağ işlemlerinin sınırsız beklemesini önler |
| Redis visibility timeout | 900 saniye | Onaylanmamış mesajın yeniden görünür olma süresi |
| Compose stop grace period | 330 saniye | Normal worker kapanışında çalışan işe süre tanır |

⭐ **Timeout:** İşin çalışma süresini sınırlar; kuyrukta bekleme süresi bu sınıra
dahil değildir. Soft limit hard limitten küçük olmalı. Timeout hataları bu
politikada otomatik retry edilmez. Soft timeout yakalanacaksa kaynak temizliği
sonrası yeniden yükseltilmeli; başarı olarak gizlenmemeli.

⭐ **Visibility timeout:** Görev timeout'uyla aynı şey değildir. Redis'in henüz
ACK almamış mesajı ne zaman yeniden dağıtabileceğini belirler. Hard timeout ve en
uzun retry beklemesinin toplamından büyük olması ayar doğrulamasında zorunludur.
Uzun ETA/countdown işleri eklenirse bu ilişki tekrar değerlendirilmelidir.

## Retry politikası

- Sadece `TransientJobError` otomatik retry edilir. Görev kodu, geçici olduğunu
  bildiği ve tekrarının güvenli olduğu hatayı bu tipe çevirmelidir.
- En fazla 3 retry: ilk çalıştırmayla beraber en fazla 4 deneme.
- Exponential backoff tabanı 10 saniye; bekleme tavanı 120 saniye.
- Jitter açık: ilk üç tekrar için bekleme 0–10, 0–20, 0–40 saniye aralığındadır.
- Geçersiz dosya, lisans hatası, kod hatası ve timeout otomatik tekrar edilmez.
- Denemeler tükendiğinde Celery sonucu `FAILURE` olur. Otomatik dead-letter queue
  veya PostgreSQL'deki iş durumunu güncelleyen iş mantığı henüz eklenmedi.

⭐ **Transient/permanent error:** Geçici bağlantı sorunu düzelebilir; bozuk dosya
bekleyerek düzelmez. `Exception` sınıfının tamamına retry uygulamak kod hatalarını
ve kalıcı sorunları tekrar tekrar çalıştırır.
⭐ **Backoff:** Her başarısızlıkta bekleme artar. **Jitter:** Beklemeye rastgelelik
ekler; çok sayıda görevin aynı anda servise tekrar yüklenmesini azaltır.

Broker'a ilk bağlanma en fazla 10 yeniden denemeyle sınırlıdır. Mesaj yayınlama
retry politikası ayrıca 3 tekrar kullanır. Bunlar görev çalıştırma retry'ından
ayrıdır; broker'a hiç yazılamayan iş worker'da çalışmış sayılmaz.

## ⭐ Not al: ACK ve idempotency

**ACK (acknowledgment)** mesajın alındığının broker'a onayıdır. Bu altyapıda early
ACK seçildi (`task_acks_late=False`). Worker çalışırken çökerse başlanmış işin
otomatik geri gelmesi garanti değildir. Bu tercih, henüz idempotent olmayan iş
kodunun kontrolsüz tekrarını önler; kayıp işleri toparlama mekanizması değildir.

**Idempotency:** Aynı iş tekrar çalışınca sonuç veya yan etki çoğalmamalı.
Örneğin aynı belge için ikinci kez chunk/rapor oluşturmamak. İş görevleri
eklenirken benzersiz anahtarlar, durum geçişleri ve transaction sınırlarıyla bu
özellik sağlanmalı. Sonra late ACK ve çöken worker sonrası kurtarma politikası
tasarlanabilir. Retry da işi yeniden çalıştırır; early ACK bu ihtiyacı ortadan
kaldırmaz. Mesaj sistemleriyle genel bir exactly-once garantisi varsayma.

**Transaction/outbox:** Veritabanına kayıt yazmak ve Redis'e görev göndermek iki
ayrı işlemdir. Aradaki çökme işi kaybettirebilir. Gerçek endpoint entegrasyonunda
transactional outbox veya bir telafi mekanizması bu boşluğu ele almalıdır.

## Çalıştırma ve kontrol

Proje kökünde:

```powershell
docker compose up -d --build --wait
docker compose logs -f worker
docker compose exec worker celery -A intihal_api.jobs.app:app inspect active_queues
docker compose exec api python -c "from intihal_api.jobs.tasks import healthcheck; job = healthcheck.delay(); print(job.id); print(job.get(timeout=15))"
```

Son komut API container'ından gerçek Redis mesajı gönderir ve worker sonucunu
bekler. Sağlıklı sonuç `{'status': 'ok'}` olmalıdır. Compose worker healthcheck'i
yalnız o container'ın Celery node'una `ping` gönderir; başka worker'ın cevabını
kendi sağlığı olarak kabul etmez. Ping görevlerin başarısını veya backlog'u ölçmez.

⭐ **Observability:** Kuyruk uzunluğu, en eski işin bekleme süresi, görev süresi,
retry sayısı ve hata oranı takip edilmeli. Task ID ile uygulamanın belge/analiz
ID'sini birlikte loglamak sorunu uçtan uca takip etmeyi sağlar.

Worker kaynak kodu bind mount ile görünür, fakat otomatik reload yoktur; Python
görevleri değişince `docker compose restart worker` gerekir. Bağımlılık değişince
`docker compose up -d --build --wait` kullanılır. Soft/hard limit doğrulaması
Linux prefork worker üzerinde yapılmalıdır; Celery eager testleri gerçek process
sonlandırmasını veya Redis redelivery davranışını doğrulamaz.

Tüm politika değerleri `.env.example` ve `apps/api/.env.example` içinde listelidir.
Compose Redis parolasını mevcut `REDIS_PASSWORD` değerinden alır; Docker dışında
API/producer çalıştırırken `INTIHAL_REDIS_PASSWORD` aynı parolaya ayarlanmalıdır.

Kaynaklar: [Celery görevler ve retry](https://docs.celeryq.dev/en/stable/userguide/tasks.html),
[Redis visibility timeout](https://docs.celeryq.dev/en/stable/getting-started/backends-and-brokers/redis.html).
