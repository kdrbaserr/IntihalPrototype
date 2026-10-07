# Analiz API'si: ne, nasıl, neden?

## Eklenen endpointler

Tüm yollar `/api/v1` önekiyle kullanılır. Kimlik doğrulama oturum cookie'siyle yapılır;
POST istekleri `X-CSRF-Protection: 1` başlığını gerektirir. [Giriş örneği](authentication.md)
ile önce `$authSession` oluşturun.

| İstek | Ne için? | Başarılı cevap |
| --- | --- | --- |
| `POST /api/v1/analyses` | Belge için analiz isteğini kabul etmek | `202`, analiz ID'si ve `Location` |
| `POST /api/v1/analyses/{analysis_id}/retry` | Son başarısız analizi kontrollü yeniden denemek | `202`, yeni/mevcut analiz ID'si |
| `GET /api/v1/analyses/{analysis_id}` | Belirli analiz kaydını ve durumunu okumak | `200`, analiz ayrıntıları |
| `GET /api/v1/analyses/{analysis_id}/matches?limit=20&offset=0` | Tamamlanmış analizin kanıtlarını okumak | `200`, sayfalı eşleşmeler |

Önceki `POST /documents/{document_id}/analysis` yolu aynı iş akışını kullanmaya
devam eder. İki yoldan tekrar istek göndermek ikinci bir aktif analiz açmaz.
Veritabanına yeni alan eklenmedi; bu değişiklik için yeni migration yoktur.

## Oluşturma: neyi, nasıl ve neden yaptık?

POST body yalnız `document_id` kabul eder. UUID biçimi doğrulanır; fazladan alanlar
reddedilir. İstemci kendi `status`, algoritma ayarı veya sahiplik alanını dayatamaz.

```json
{"document_id": "11111111-2222-3333-4444-555555555555"}
```

API belge sahipliğini kontrol edip satırı kilitler, mevcut `queue_document`
akışını çağırır. Analiz kaydı ve `QUEUED` durumu kalıcı olarak kaydedilir;
dispatcher/worker işi daha sonra yürütür. Dosya yeniden yüklenmez ve HTTP isteği
uzun karşılaştırmanın bitmesini beklemez.

Yanıtta `id` analiz UUID'si, `document_id` belge UUID'sidir. Ayrıca `status`,
`algorithm_version`, `started_at`, `completed_at`, `failure_reason` döner.
Yeni istekte durum `queued`, başlangıç/bitiş zamanları `null` olur.
`Location: /api/v1/analyses/{id}` header'ı takip adresini gösterir.

Tekrarlanan başlatma POST'u, başarısız analiz dahil mevcut son kaydı döndürür.
Başarısız belge yalnız ayrı retry endpointiyle yeni analiz ID'si açabilir;
önceki hata kaydı korunur. Yanıt kodu tekrar isteklerde de `202` olur; dönen `status`
analizin zaten tamamlanmış olup olmadığını gösterir.

⭐ **Not al — 202 Accepted:** İstek kabul edildi, analiz bitmiş olmak zorunda değil.
`201 Created` yeni kaynağın oluşturulmasını ifade eder; burada asenkron iş kabulü
API'nin ana davranışı olduğundan `202` kullanıldı.

Kontrollü retry ve çift tıklama davranışının ayrıntıları:
[⭐ Idempotency ve retry notları](analysis-retry.md).

⭐ **Not al — Idempotency:** Tekrarlanan aynı başlatma isteği ikinci aktif iş
üretmez. Belge satır kilidi iki eşzamanlı isteğin birlikte yeni kayıt açmasını
engeller. Bu mekanizma belge bazındadır; genel bir `Idempotency-Key` sistemi değildir.

## Durum sorgusu: nasıl takip edilir?

GET, analiz ile sahibi olan belgeyi tek JOIN ile bulur. Celery task durumunu
değil, işin kalıcı veritabanı durumunu döndürür. Analiz ayrıntılarında eşik,
konfigürasyon snapshot'ı ve oluşturma/güncelleme zamanları da bulunur.

- `status`: Bu analiz çalıştırmasının durumu (`queued`, `processing`, `completed`,
  `failed`, `cancelled`).
- `document_status`: Belgenin **şimdiki** yaşam döngüsü (`uploaded`, `queued`,
  `extracting`, `analyzing`, `completed`, `failed`).

Örneğin analiz `processing` iken belge `extracting` veya `analyzing` olabilir.
Eski başarısız analiz sorgulanırken belge yeni deneme için `queued` olabilir;
eski analizin `status=failed` değeri değişmez. İstemci bu iki alanı aynı anlamda
kullanmamalıdır.

⭐ **Not al — Resource identity:** Belge dosyanın kimliğidir; analiz belirli
çalıştırmanın kimliğidir. Sonucu okumak için POST cevabındaki analiz `id`'sini kullan.

⭐ **Not al — Polling:** İstemci durum endpoint'ini aralıklarla okur. Aktif işte
yaklaşık 2 saniyelik aralık uygundur; bitmiş/başarısız/iptal edilmiş analizde dur.
Bağlantı hatası işin başarısız olduğunu kanıtlamaz. HTTP 200, sorgunun başarılı
olduğunu söyler; analiz sonucu için ayrıca `status` okunmalıdır.

## Eşleşmeler: açıklanabilir sonuç

Eşleşmeler yalnız `status=completed` analizlerde okunur. Aktif, başarısız veya
iptal edilmiş analizde `409 / analysis_not_completed` döner. Böylece henüz sonuç
hazır değilken boş listeyi 'benzerlik yok' diye yorumlamak önlenir.

Her eşleşmede şu alanlar vardır:

- `id`, `analysis_id`, `method`, `similarity_score`, `matched_token_count`,
  `explanation`.
- `document`: chunk ID'si, sayfa numarası, eşleşme başlangıç/bitişi ve metin kesiti.
- `source`: aynı kanıt alanlarına ek kaynak ID'si, başlık, yazar, yayıncı, URL,
  lisans adı/URL'si ve attribution bilgisi.

Skor `0–1` aralığındadır ve Decimal hassasiyetini korumak için JSON'da string
olarak gelir (`"0.8500"` gibi). Bu skor chunk çiftinin benzerlik skorudur;
belgenin toplam benzerlik yüzdesi veya bir intihal olasılığı değildir.
Kaynak metadata'sı okuma anındaki kayıt değerleridir; geçmiş metadata snapshot'ı
bu endpoint tarafından ayrıca tutulmaz.

Metin kesitini çıkarmak için eşleşmenin global karakter konumundan chunk'ın
başlangıcı çıkarılır. Tam dosya veya tam kaynak metni yerine eşleşen kesit verilir.
MinIO bucket/key bilgileri ve bağlantı kimlik bilgileri yanıtlanmaz.

⭐ **Not al — Evidence:** 'Skor yüksek' tek başına yeterli açıklama değildir.
Hangi metin, hangi kaynak, hangi konum sorularının cevabı incelenebilir kanıttır.

⭐ **Not al — Half-open interval:** Aralık `[char_start, char_end)` biçimindedir;
bitiş karakteri dahil değildir. Konumlar normalleştirilmiş metne aittir. PDF/DOCX
ham bayt konumu değildir. Sayfa bilgisi olmayan TXT/DOCX chunk'ında `page_number=null`
olabilir.

## Pagination ve sorgu davranışı

`limit` varsayılan 20, izinli aralık 1–100; `offset` en az 0'dır. Yanıt:

```json
{
  "analysis_id": "analiz-uuid",
  "total": 42,
  "limit": 20,
  "offset": 0,
  "items": []
}
```

Örnekte `items` yalnız yanıt yapısını göstermek için boştur. Gerçek yanıtta ilgili
sayfanın eşleşmeleri bulunur. Skor azalan, belge konumu artan, eşleşme ID'si artan
sıralama kullanılır. ID son eşitlik bozucudur; aynı skorlu kayıtlar sayfalar arasında
keyfî şekilde yer değiştirmez. Tamamlanmış sıfır eşleşmeli analiz `200`, `total=0`,
`items=[]` döner. Listenin sonundan sonraki offset de boş bir başarılı sayfadır.

⭐ **Not al — Pagination:** Tüm sonuçları tek yanıta doldurmak yerine parçalı
okuruz. Yanıt boyutunu ve istemcinin yükünü sınırlar. Çok yüksek offset maliyetli
olabilir; büyük ölçek için cursor pagination ayrı bir geliştirmedir.

⭐ **Not al — JOIN ve N+1:** Eşleşme, belge chunk'ı, kaynak chunk'ı ve kaynak
metadata'sı tek sayfa sorgusunda alınır. Her eşleşme için ek sorgu yapmak yerine
toplu okuma kullanılır. Toplam kayıt sayısı ayrıca `COUNT` ile hesaplanır.

## Yetkilendirme ve hata sözleşmesi

⭐ **Not al — Authentication vs authorization:** Kimlik kontrolü 'kim bu?',
sahiplik kontrolü 'bu analizi okuyabilir mi?' sorusudur. UUID'nin tahmin edilmesinin
zor olması erişim kontrolü değildir.

| Kod | Ne zaman? |
| --- | --- |
| `401` | Kullanıcı kimliği yok veya geçersiz |
| `403` | Kullanıcı hesabı devre dışı |
| `404` | Kayıt yok, başka kullanıcıya ait veya belge silinmiş |
| `409` | Sonuç henüz hazır değil / belge analiz için uygun değil |
| `422` | Geçersiz UUID, eksik/fazladan body alanı veya geçersiz pagination |

Başkasının kaydına `404` dönmek, kaydın varlığını ayrı bir cevapla açıklamamayı
sağlar. Sahiplik koşulu SQL sorgusunun içindedir; veri döndürüldükten sonra
istemcinin filtrelemesine güvenilmez.

## Örnek kullanım

Hata yanıtları `detail.code`, güvenli `detail.message` ve `detail.trace_id`
alanlarını içerir. `X-Request-ID` aynı takip kodunu taşır. Ayrıntılar ve ⭐ notlar
[güvenli hata ve trace belgesinde](error-handling.md) açıklanır.

```powershell
# Önce authentication.md giriş örneğiyle $authSession oluşturun.
$headers = @{ "X-CSRF-Protection" = "1" }
$payload = @{ document_id = "yuklenen-belgenin-uuid-degeri" } | ConvertTo-Json
$analysis = Invoke-RestMethod -WebSession $authSession -Method Post -Headers $headers -ContentType "application/json" -Body $payload -Uri "http://localhost:8000/api/v1/analyses"
$analysisId = $analysis.id
Invoke-RestMethod -WebSession $authSession -Headers $headers -Uri "http://localhost:8000/api/v1/analyses/$analysisId"
# status completed olduktan sonra:
Invoke-RestMethod -WebSession $authSession -Headers $headers -Uri "http://localhost:8000/api/v1/analyses/$analysisId/matches?limit=20&offset=0"
```

Olay örgüsü: belgeyi yükle → POST ile analiz ID'sini al → GET ile durumu takip et
→ completed olduğunda matches GET ile kanıtları sayfa sayfa oku. Swagger arayüzü
`http://localhost:8000/docs` altında yeni şemaları ve endpointleri gösterir.
