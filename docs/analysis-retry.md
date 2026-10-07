# Çift tıklama ve kontrollü retry

## Neyi, nasıl, neden değiştirdik?

Başlat isteği artık belge için mevcut son analizi döndürür; analiz hızla başarısız
olmuş olsa bile gecikmiş ikinci başlatma isteği yeni çalışma açmaz. Her iki başlatma
yolu (`POST /analyses` ve `POST /documents/{id}/analysis`) aynı davranışı kullanır.

Arayüz, React render'ını beklemeden `useRef` ile gönderim kilidi koyar. İkinci
tıklama HTTP isteği göndermez; buton işlem boyunca devre dışıdır. Polling yanıtı
başlatma isteği sürerken ekrandaki durumu değiştirmez. Başlatma yanıtının durumu
okunur; zaten failed/completed olan analiz ekranda queued gösterilmez.

Backend belge satırını `SELECT ... FOR UPDATE` ile kilitler. Kilit alınınca ORM
nesnesi `populate_existing=True` ile güncellenir; daha önce okunmuş eski durum
üzerinden karar verilmez. PostgreSQL'de aynı belgeye gelen istekler sırayla karar
verir. Frontend kilidi kullanıcı deneyimi içindir; API kilidi ayrı istemcilerden
gelen eşzamanlı istekleri de korur.

## Manuel retry sözleşmesi

`POST /api/v1/analyses/{analysis_id}/retry` body gerektirmez; oturum cookie'si ve `X-CSRF-Protection: 1` gerekir. [Giriş örneği](authentication.md).
Başarılı cevap 202 ve `Location` header'ıyla takip edilecek analizi döndürür.

1. Analiz ve belge sahipliği kontrol edilir; başkasının analizi 404 döner.
2. Belge kilitlenir. Hedef analiz failed olmalıdır.
3. Aynı hedef için daha önce yeni analiz açılmış ve bu analiz queued/processing/
   completed durumundaysa mevcut analiz döner. İkinci retry yeni kayıt açmaz.
4. Son analiz de failed olmuşsa eski analiz ID'siyle retry reddedilir. Yeni retry
   ancak son başarısız analiz ID'siyle yapılır.
5. Yalnız `processing_failed`, `processing_timeout`, `retry_exhausted` yeniden
   denenebilir. OCR, bozuk dosya veya içerik değişikliği için dosya düzeltilip
   yeniden yüklenmelidir.
6. Belge başına varsayılan en fazla 3 manuel retry vardır. Analiz geçmişinin
   sayısı kullanılır; worker restart veya başlat endpointi bu limiti sıfırlamaz.
7. Yeni analiz oluşturulur, eski failed kaydı korunur. Belge queued olur;
   `next_attempt_at` varsayılan 30 saniye sonrasıdır. Dispatcher bu zaman gelince
   işi yayımlar; gerçek başlama zamanı dispatcher aralığı ve kuyruk yüküne bağlıdır.

`GET /documents/{id}` yanıtı `latest_analysis_id` içerir; arayüz retry hedefini
buradan alır. Bu alan list/upload yanıtlarında varsayılan null olabilir.

| Hata kodu | HTTP | Sebep |
| --- | --- | --- |
| `analysis_retry_conflict` | 409 | Hedef başarısız değil veya son failed çalışma değil |
| `analysis_retry_not_allowed` | 409 | Dosya düzeltilmeden retry fayda sağlamaz |
| `analysis_retry_limit` | 409 | Belgenin manuel retry hakkı tükendi |

Konfigürasyon `.env` / API `.env` / Compose üzerinden ayarlanabilir:

```dotenv
INTIHAL_ANALYSIS_MANUAL_RETRY_LIMIT=3
INTIHAL_ANALYSIS_MANUAL_RETRY_DELAY_SECONDS=30
```

Limit 0 manuel retry'ı kapatır. Otomatik worker retry ayrı politikadır: aşama
başına ilk çalıştırma + `INTIHAL_TASK_MAX_RETRIES` kadar tekrar; mevcut exponential
backoff ve jitter korunur. Manuel retry yeni çalışma açıp extraction'dan başlar.

## ⭐ Not al

⭐ **Idempotency:** Aynı isteği tekrar göndermek aynı sonucu verir. Başlatma belge
kimliği, retry ise başarısız analiz kimliği üzerinden tekrarları tanır.

⭐ **Race condition:** İki istek aynı eski durumu okuyup iki analiz açabilir.
Satır kilidi ve kilit sonrası taze okuma bu yarışmayı engeller.

⭐ **Automatic retry / manual retry:** Otomatik retry aynı işin geçici hata sonrası
tekrarıdır. Manuel retry kullanıcının açık isteğiyle yeni analiz kaydı açar;
geçmişteki hata kaydı inceleme için kalır.

⭐ **Retry budget ve delay:** Deneme sınırı sonsuz döngüyü, bekleme süresi servis
arıza sırasında hemen yeniden yük oluşmasını sınırlar. Limit veritabanındaki
geçmişten hesaplanır; yalnız buton gizleyerek uygulanmaz.

Olay örgüsü: çift tık → tek HTTP gönderimi → belge kilidi → tek analiz → worker
başarısızlığı → otomatik denemeler → failed → uygun hata için manuel retry →
30 saniyelik bekleme → yeni analiz. Manuel retry'a çift tıklanırsa yine tek yeni
analiz kullanılır.

SQLite tabanlı API testleri retry sınırını, gecikmeyi, sahipliği, eski ID reddini
ve geçmişi doğrular. Gerçek eşzamanlılık için PostgreSQL entegrasyon testi
`test_postgres_concurrent_start_and_retry_create_one_run` vardır; PostgreSQL test
veritabanı tanımlı değilse bu test atlanır. SQLite FOR UPDATE uygulamaz.
