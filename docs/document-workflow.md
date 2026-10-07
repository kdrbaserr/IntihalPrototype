# Belge durum zinciri ve mühendislik notları

## Olay örgüsü

`UPLOADED → QUEUED → EXTRACTING → ANALYZING → COMPLETED`

Python enum adları büyük harflidir; API ve PostgreSQL değerleri küçük harfle
(`uploaded`, `queued`, `extracting`, `analyzing`, `completed`) saklanır.

| Durum | Anlamı | Durumu değiştiren işlem |
| --- | --- | --- |
| UPLOADED | Dosya MinIO'da, belge kaydı PostgreSQL'de | Belge yükleme API'si |
| QUEUED | Analiz isteği kalıcı olarak kabul edildi, worker bekleniyor | Analizi başlat API'si |
| EXTRACTING | Dosya okunuyor, metin normalleştiriliyor ve parçalara ayrılıyor | Documents worker görevi |
| ANALYZING | Metin parçaları hazır, izinli kaynaklarla karşılaştırılıyor | Analysis worker görevi |
| COMPLETED | Eşleşmeler ve başarılı analiz sonucu kaydedildi | Analysis worker görevi |
| FAILED | Kalıcı hata, soft timeout veya denemelerin tükenmesi | Worker / kurtarma döngüsü |

1. Kullanıcı PDF, DOCX veya TXT yükler. Dosya doğrulanır, MinIO'ya yazılır;
   veritabanı kaydı `UPLOADED` olur. Yükleme yüzdesi analiz yüzdesi değildir.
2. Arayüzde **Analizi başlat** seçilir. `POST /api/v1/documents/{id}/analysis`
   belgeyi `QUEUED` yapar ve bir `Analysis` kaydı açar; `202 Accepted` döner.
3. Celery Beat 15 saniyede bir `intihal.dispatch_pending` görevini gönderir.
   Dispatcher veritabanındaki zamanı gelmiş işleri Redis kuyruklarına yollar.
   `QUEUED`, isteğin kalıcı kabulünü ifade eder; mesajın o anda Redis'e ulaşmış
   olduğunu veya worker'ın çalışmaya başladığını garanti etmez.
4. `intihal.documents.extract`, belgeyi `EXTRACTING` yapar. Worker dosyayı yeniden
   okur; boyut ve SHA-256 kontrolü yapar, metni çıkarır, normalleştirir ve chunk'lar
   oluşturur. Chunk'lar ile `ANALYZING` durumu birlikte commit edilir.
5. Dispatcher sonraki taramada `intihal.analysis.run` görevini analysis kuyruğuna
   yollar. Worker yalnız teknik durumu `ready`, lisansı `approved` ve lisans tarihi
   geçerli kaynakları karşılaştırmaya alır.
6. Hibrit skor eşiğini geçen chunk çiftlerinde ortak ardışık kelime aralıkları
   `Match` olarak saklanır. Tüm chunk'ın eşleştiği varsayılmaz. Metin konumları
   normalleştirilmiş metne aittir; ham PDF bayt konumları değildir.
7. Eşleşmeler, analiz bitiş zamanı ve `COMPLETED` tek transaction'da kaydedilir.
   Arayüz `GET /api/v1/documents/{id}` ile durumu yaklaşık 2 saniyede bir okur;
   `COMPLETED` veya `FAILED` olunca normal polling durur.

Kaynak havuzu boşsa analiz sıfır eşleşmeyle tamamlanabilir. Bu, karşılaştırmanın
yapılabildiği kapsamda sonuçtur; belgenin her olası kaynak karşısında özgün olduğunu
kanıtlamaz. Bu prototipte chunk çiftleri doğrudan karşılaştırılır; büyük kaynak
havuzları için aday seçimi/indeksleme ayrı bir geliştirmedir.

## ⭐ Not al: state machine ve geçiş kuralları

**State machine (durum makinesi)**, hangi durumdan hangi duruma geçilebileceğinin
tanımıdır. `jobs/states.py` mutlu yol adımlarının atlanmasını reddeder.

- `UPLOADED → QUEUED`
- `QUEUED → EXTRACTING` veya `FAILED`
- `EXTRACTING → ANALYZING` veya `FAILED`
- `ANALYZING → COMPLETED` veya `FAILED`
- `FAILED → QUEUED`: Kullanıcının açık yeniden deneme isteği; yeni analiz kaydı.
- `COMPLETED`: Bu akışın sonudur. Tekrar başlat isteği mevcut analizi döndürür.

Geçiş kontrolü uygulama kodundadır; doğrudan SQL yazan başka bir uygulama bu
kuralları kendiliğinden uygulamaz. Kaynak havuzundaki `SourceDocumentStatus`
zinciri ayrı bir süreçtir; kullanıcı belgesinin durumlarıyla değiştirilmedi.

## ⭐ Not al: transaction ve atomicity

**Transaction**, birlikte başarılı olması gereken veritabanı değişikliklerini
tek işlemde toplar. **Atomicity**, hepsinin gerçekleşmesi veya hiçbirinin
gerçekleşmemesidir. Eşleşmeler yazılamadıysa `COMPLETED` de yazılmamalı.
Ara durumlar ayrı commit edildiğinden kullanıcı worker çalışırken aşamayı görebilir.

## ⭐ Not al: idempotency ve concurrency

**Idempotency:** Başlat isteğinin tekrarı ikinci bir aktif analiz oluşturmaz.
API, belge satırını `SELECT ... FOR UPDATE` ile kilitler. Aktif veya tamamlanmış
belgede aynı analiz kaydını döndürür. Başarısız analiz için de başlat isteği aynı
kaydı döndürür. `FAILED` sonrası yalnız kontrollü retry endpointi yeni analiz
açar; eski analizin hata kaydı korunur. Ayrıntılar: [retry notları](analysis-retry.md).

**Concurrency:** İki worker aynı belgeyi aynı anda alabilir. Her worker, belge
UUID'sinden türetilen PostgreSQL advisory lock alır; kilit doluysa işleme başlamaz.
Kilit aynı fiziksel bağlantıda tutulur ve ara commit'lerde bırakılmaz. Tamamlanmış
ya da artık o aşamada olmayan mesajlar yeniden gelse de işlenmez.

Bu, genel bir **exactly-once delivery** garantisi değildir. Mesaj tekrar gelebilir;
durum kontrolü, kilit ve atomic kayıt sayesinde aynı çalıştırmanın sonuçlarının
çoğalması önlenir. Advisory lock bağlantı kapanınca bırakılır.

## ⭐ Not al: durable dispatch, retry ve recovery

**Durable dispatch intent:** Kuyruğa gitmesi gereken iş PostgreSQL'de kalır.
Redis'e gönderme başarısızsa belge `QUEUED` kalır; sonraki dispatcher taramasında
tekrar denenir. Bu prototip ayrı bir outbox tablosu yerine belge durumu ve
`next_attempt_at` alanını kullanır. Tarama başına en eski 100 uygun belge gönderilir.
Bu sayı teslim hızı sınırıdır; yüksek yükte backlog takibi ve batch iyileştirmesi
gerekir. Tek Beat instance çalıştırılmalıdır.

**Retry:** Her aşamada ilk çalıştırma + en fazla 3 tekrar. `processing_attempts`
kalıcıdır; worker yeniden başlasa da sayacı sıfırlamaz. Extraction başarıyla bitince
analysis aşaması için sayaç sıfırlanır. Geçici bağlantı hatasında durum bulunduğu
aşamada kalır; jitter/backoff ile `next_attempt_at` ileri alınır. Tekrar zamanı
geldikten sonra bir dispatcher taraması beklenir; bekleme tam saniye garantisi
değildir. Belge işleri için Celery autoretry ile veritabanı retry sayacı birlikte
çalıştırılmaz. Genel altyapı görevlerinin `TransientJobError` politikası ayrı kalır.

**Recovery:** Worker process'i hard timeout veya çökme ile kesilirse aşama ve
deneme sayısı veritabanında kalır. Çalışmaya başlarken sonraki uygun zaman
`hard timeout + 30 saniye` olarak kaydedilir. Süre dolunca dispatcher işi yeniden
yollar; hâlâ çalışan bir worker varsa belge kilidi ikinci çalışmayı engeller.
Denemeler tükenince `FAILED / retry_exhausted` olur. Soft timeout yakalanabildiğinde
`FAILED / processing_timeout` kaydedilir. Scheduler/worker kapalı kaldığı sürece
ilerleme olmaz; yeniden açılınca kalıcı iş kayıtları taranır.

**Hata sınıflandırması:** Depolama bağlantısı ve geçici DB bağlantı hataları tekrar
edilebilir. Bozuk dosya, OCR gereksinimi, checksum uyuşmazlığı, yetki hatası veya
kod hatası başarı gibi gösterilmez. API'ye güvenli hata kodu verilir; kimlik
bilgileri ve ham exception içeriği belgeye yazılmaz.

**Celery task state ≠ belge state:** Bir task, iş hatasını veritabanına kaydedip
teknik olarak başarıyla dönebilir. Kullanıcıya sonucu gösterirken Celery `SUCCESS`
yerine PostgreSQL'deki belge/analiz durumu esas alınır.

## ⭐ Not al: configuration snapshot

Analiz başlatılırken algoritma sürümü, eşik ve üç skor ağırlığı analize kaydedilir.
Worker sonradan değiştirilmiş eşik/ağırlıkları sessizce kullanmaz. Desteklenmeyen
algoritma sürümü geldiğinde iş başarısız olur. Snapshot olmayan eski analizlere
kendiliğinden yeni ayarlarla sonuç üretilmez.

## API ve yerel deneme

Tüm belge endpoint'leri sahiplik kontrolü yapar. Başkasının veya silinmiş belgesinin
durumu/analizi `404` döner. Kimlik yoksa `401` döner.

```powershell
# Yeni şema gerekir. Scheduler/worker'ı yeni şema hazır olmadan çalıştırma.
docker compose stop scheduler worker
docker compose build api worker scheduler
docker compose run --rm api python -m alembic upgrade head
docker compose up -d --wait
docker compose logs -f worker scheduler
```

Web arayüzünden dosya yükleyip **Analizi başlat** seç. API üzerinden denemek için:

```powershell
$documentId = "yuklenen-belgenin-uuid-degeri"
# Önce authentication.md giriş örneğiyle $authSession oluşturun.
$headers = @{ "X-CSRF-Protection" = "1" }
Invoke-RestMethod -WebSession $authSession -Method Post -Headers $headers -Uri "http://localhost:8000/api/v1/documents/$documentId/analysis"
Invoke-RestMethod -WebSession $authSession -Headers $headers -Uri "http://localhost:8000/api/v1/documents/$documentId"
```

## Migration ve test sınırları

`20261006_07` migration'ı eski belge enum'unu değiştirir. Eski `ready` belgesi,
analiz tamamlandı anlamına gelmediğinden `uploaded` olur. Eski `processing` belgesi
`failed` olur; kullanıcı yeniden analiz başlatabilir. Downgrade yeni aşamaları eski
enum'a eşler, workflow alanlarını kaldırır; yeni durum ayrıntısı kaybolur.

SQLite testleri iş akışını, sahiplik kontrollerini, eşleşme kaydını ve rollback'i
gerçek veritabanı işlemleriyle doğrular. PostgreSQL testleri gerçek advisory lock,
dispatcher ve sınırlı retry davranışını doğrulamak için
`INTIHAL_TEST_DATABASE_URL` gerektirir. Celery process timeout'u ve gerçek Redis
teslimatı ayrıca çalışan Docker ortamında doğrulanmalıdır.

Kaynaklar: [PostgreSQL kilitler](https://www.postgresql.org/docs/17/explicit-locking.html),
[Celery periyodik görevler](https://docs.celeryq.dev/en/stable/userguide/periodic-tasks.html).
