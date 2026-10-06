# Worker senaryo testleri

`apps/api/tests/test_worker_resilience.py` gerçek `run_stage`, dispatcher,
extraction/analysis ve kalıcı veritabanı kayıtlarını birlikte test eder.
Hatalar aşama sınırında kontrollü olarak enjekte edilir. Üretim kodu değişmedi.

| Senaryo | Doğrulanan sonuç |
| --- | --- |
| Başarı | Belge ve analiz completed; zaman alanları ve tek eşleşme kaydedilir |
| Yinelenen mesaj | Bitmiş aşama yeniden çalışmaz; ikinci sonuç üretilmez |
| Extraction soft timeout | Failed + `processing_timeout`; otomatik dispatch durur |
| Analysis soft timeout | Aynı güvenli hata sözleşmesi; manuel retry yeni analizle tamamlanır |
| Extraction sırasında worker kaybı | Extracting durumu ve sayaç kalır; süre dolunca extract tekrar yayımlanır |
| Analysis sırasında worker kaybı | Analyzing durumu kalır; süre dolunca analyze tekrar yayımlanır |
| Tekrarlayan worker kaybı | İlk çalışma + 3 tekrar sonrası `retry_exhausted`; sayaç sıfırlanmaz |
| Geçici servis arızası ve düzelme | Retry zamanından önce çalışma yok; servis düzelince başarı |
| Kalıcılaşan servis arızası | 4 deneme sonrası failed; terminal iş yeniden yayımlanmaz |

Soft timeout `SoftTimeLimitExceeded` ile enjekte edilir. Worker kesintisi,
normal `Exception` handler'ını atlayan `WorkerStopped(BaseException)` ile
simüle edilir. Böylece işin başarısız diye kaydedilemediği durumdaki kalıcı
sayaç, bekleme zamanı ve dispatcher kurtarma davranışı kontrol edilir.
Gerçek Celery prefork süreci öldürülmez; OS sinyali, SIGKILL/TerminateProcess,
Redis kesintisi ve hard timeout'un süreç sonlandırması bu testlerin kapsamı
dışındadır. Hard timeout sonrası kurtarmada kullanılan kalıcı bekleme mekanizması
worker kesintisi senaryosuyla sınanır.

## Çalıştırma

Repo kökünden:

```powershell
apps/api/.venv/Scripts/python.exe -m pytest apps/api/tests/test_worker_resilience.py -v
apps/api/.venv/Scripts/python.exe -m pytest apps/api/tests --tb=short
```

Her senaryo SQLite ve PostgreSQL için parametrelidir. SQLite testlerinde yalnız
PostgreSQL advisory-lock SQL fonksiyonları uyumluluk stub'ıyla değiştirilir;
SQLite'ın timezone kaybı test fixture'ında düzeltilir. Gerçek PostgreSQL kilitleri
bu SQLite koşularıyla doğrulanmış sayılmaz.

PostgreSQL koşuları mevcut test altyapısını kullanır: `INTIHAL_TEST_DATABASE_URL`
ayrı bir test veritabanını göstermeli, veritabanı adında `test` bulunmalıdır.
Fixture migration'ları baştan kurup test sonunda geri alır. Bu nedenle yalnız
test verisi içeren ayrı veritabanıyla çalıştırılır. URL tanımlı değilse PostgreSQL
senaryoları açıkça skip olur. Dokuz SQLite senaryosu dış servis gerektirmez.

## ⭐ Not al

⭐ **Fault injection:** Gerçek iş akışında belirli bir noktaya kontrollü hata
yerleştirerek beklenen davranışı ölçmektir. Test hem hata cevabını hem kalıcı
veritabanı durumunu doğrulamalıdır.

⭐ **Soft / hard timeout:** Soft timeout kodun yakalayabileceği istisnadır.
Hard timeout süreç kaybına yol açabilir; kodun cleanup yapmasına güvenilemez.

⭐ **Durable recovery:** İş alınırken deneme sayısı ve yeniden alınabilecek
zaman veritabanına yazılır. Worker kaybolsa da yeni worker kaldığı yerden karar
verebilir. Her `run_stage` çağrısı yeni engine/bağlantı açtığı için test, yalnız
aynı Python nesnesindeki sayaç üzerinden geçmez.

⭐ **Retry budget:** Yeniden başlatma deneme hakkını sıfırlamamalıdır.
Kesinti art arda yaşanırsa sonsuz kurtarma döngüsü yerine güvenli failed durumu
oluşur.

⭐ **Deterministic test:** Uzun süre uyumak yerine kalıcı `next_attempt_at`
testte geçmişe alınır. Öncesinde çalışmanın beklediği, sonrasında dispatcher'ın
doğru kuyruğa yayımladığı kontrol edilir. Backoff/jitter algoritmasının kendisi
ayrı `test_jobs.py` testlerinde sınanır.

Olay örgüsü: iş alınır → deneme ve kurtarma zamanı commit edilir → worker
kesilir → erken mesaj bekletilir → süre dolunca dispatcher işi tekrar yayımlar
→ yeni worker tamamlar; kesinti sürerse deneme bütçesi tükenir.
