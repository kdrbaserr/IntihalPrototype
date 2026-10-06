# Güvenli hatalar ve teknik izler

API hataları merkezi handler üzerinden aşağıdaki sözleşmeyle döner:

```json
{
  "detail": {
    "code": "internal_error",
    "message": "İşlem tamamlanamadı. Takip koduyla destek isteyebilirsiniz.",
    "trace_id": "sunucunun-urettigi-takip-kodu"
  }
}
```

HTTP durum kodu korunur. `code` makine tarafından okunabilen sabit hata
kodudur; `message` kontrollü Türkçe katalogdan gelir. İstisnanın kendi mesajı
istemciye gönderilmez. Örneğin `validation_error` 422, `document_not_found` 404,
`analysis_not_completed` 409 ve beklenmedik `internal_error` 500 döner.
Doğrulama yanıtları hatalı alanın ham değerini içermez.

Her HTTP isteğinde sunucu yeni bir takip kodu üretir. Yanıtın `X-Request-ID`
header'ı, hata yanıtındaki `trace_id` ve ilgili API hata logu aynı değeri taşır.
İstemcinin gönderdiği takip koduna güvenilmez. CORS bu yanıt header'ının tarayıcı
tarafından okunmasına izin verir; beklenmedik 500 yanıtlarında da CORS uygulanır.
Uygulama debug ayarı açık olsa bile istemciye traceback sayfası gönderilmez.

## Log sözleşmesi

Uygulama hataları standart Python logging üzerinden JSON mesajları olarak
yazılır. HTTP 4xx kayıtları WARNING, 5xx ve worker hataları ERROR seviyesindedir.
Logger adı `intihal_api.core.diagnostics`'tir. Çalıştırıcı log satırına kendi
tarih/seviye önekini ekleyebilir.

- API: `event`, `code`, `trace_id`, `http_status`, `method`, `route`, `trace`.
- Worker aşaması: ek olarak `document_id`, `analysis_id`, `task_id`, `stage`,
  `attempt`; olay adı `workflow_stage_error`.
- Worker dış hatası: `worker_unhandled_error`, task/stage ve varsa belge kimliği.
- Yükleme sonrası dosya temizliği hatası: `document_cleanup_failed` veya
  `source_cleanup_failed`, depolama anahtarı.

`trace`, istisna türünü ve çağrı yığınının tüm dosya/satır/fonksiyon konumlarını
tutar; neden zincirindeki istisnalar da kaydedilir. Ham istisna mesajı, SQL,
parametreler, yerel değişkenler, belge metni, istek gövdesi ve query değerleri
kaydedilmez. Bu nedenle trace bir traceback konum kaydıdır; ham Python hata
metninin kopyası değildir. Celery'ye iletilen dış hata da güvenli mesaj ve takip
kodu taşır; geçici hata sınıfı korunarak mevcut retry politikası çalışır.

```powershell
docker compose logs --follow api worker
```

Olay örgüsü: kullanıcı hata kodu ve takip kodunu görür → API logunda `trace_id`
aranır → dosya/satır/fonksiyon ve neden zinciri incelenir. Arka plan analizi
başarısız olmuşsa belge/analiz kimliğiyle worker kaydı bulunur. Worker kendi
takip kodunu üretir; API ve worker arasında dağıtık trace aktarımı yoktur.
`failure_reason` alanında yalnız katalogdaki güvenli kodlar gösterilir;
eski kayıtlardaki bilinmeyen hata metinleri `processing_failed` olarak okunur.

## ⭐ Mühendislik notları

⭐ **Not al — Error contract:** HTTP durum kodu sonucun sınıfını, uygulama hata
kodu özel sebebi anlatır. İstemci mesaj metnini karşılaştırmak yerine `code`
alanını kullanır.

⭐ **Not al — Correlation ID:** Kullanıcıdaki hatayı log kaydıyla eşleştiren
kimliktir. Kullanıcı bu kodu ilettiğinde hangi isteğin hata verdiği bulunur.

⭐ **Not al — Traceback ve exception chaining:** Çağrı yığını hataya giden
fonksiyonları gösterir. `raise ... from ...` neden zincirini korur; örneğin
depolama hatasının altındaki bağlantı hatasının türü ve konumu da incelenebilir.

⭐ **Not al — ContextVar:** Eşzamanlı async isteklerin takip kodlarının birbirine
karışmasını önler. İstek bitince context sıfırlanır.

⭐ **Not al — Sanitization:** Teknik tanı için gerekli konumları tutarken ham
veriyi dışarıda bırakmaktır. SQL hatası parola veya belge içeriği taşıyabilir;
bu yüzden doğrudan `str(exception)` veya `logger.exception` kullanılmaz.

⭐ **Not al — Observability:** API isteği `trace_id` ile, worker işi task/belge/
analiz kimlikleriyle izlenir. Retry kararını loglamak, hatanın kalıcı mı geçici
mi olduğunu araştırmayı kolaylaştırır.
