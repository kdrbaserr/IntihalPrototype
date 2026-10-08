# API referansı

Gözden geçirme: 8 Ekim 2026. Varsayılan temel adres `http://localhost:8000/api/v1`.
`INTIHAL_API_V1_PREFIX` değiştirilirse yollar da değişir. Çalışan şema
`/openapi.json`, etkileşimli arayüz `/docs` altındadır. OpenAPI bütün çalışma
anındaki hata kodlarını ayrıca listelemeyebilir; aşağıdaki hata sözleşmesi de uygulanır.

## Oturum ve sahiplik

Kayıt normal `user` oluşturur; ardından giriş gerekir. Giriş cookie üretir.
Bearer token veya `X-User-ID` ile kimlik doğrulama yoktur. Tarayıcı isteğinde
`credentials: "include"` kullanılır. Veri değiştiren **POST/DELETE** isteklerinde,
kayıt ve giriş dahil, `X-CSRF-Protection: 1` zorunludur. `Origin` varsa izin
listesinde olmalıdır; tarayıcıda bu başlığı elle değiştirmeyin.

Cookie yerelde `intihal_session`, staging/production'da `__Host-intihal_session`
adını alır. Varsayılan oturum ömrü 8 saattir; kullanım süreyi uzatmaz. Çıkış,
parola/rol yönetimi veya hesabı devre dışı bırakma erişimi iptal eder/engeller.
Admin kaynak havuzunu yönetebilir; başka kullanıcının belgesini okuyamaz.
Başkasının veya silinen belgenin okunması `404` üretir.

## Endpoint envanteri

Aşağıdaki yollar `/api/v1` altındadır. `Açık` oturum gerektirmez; POST için CSRF
başlığı yine gerekir. UUID'ler belge ve analiz için farklı kimliklerdir.

| Yöntem | Yol | Erişim | Girdi / başarılı yanıt |
|---|---|---|---|
| GET | `/health` | Açık | 200, yalnız canlılık |
| POST | `/auth/register` | Açık | JSON email, display_name, password; 201 kullanıcı |
| POST | `/auth/login` | Açık | JSON email, password; 200 kullanıcı ve Set-Cookie |
| GET | `/auth/me` | Oturum | 200 kullanıcı/rol |
| POST | `/auth/logout` | Cookie varsa iptal | 204; tekrarlanabilir |
| POST | `/documents` | Kullanıcı | multipart file, retention_days; 201 belge |
| GET | `/documents` | Kullanıcı | limit/offset; 200 kendi belgelerinin listesi |
| GET | `/documents/{document_id}` | Sahibi | 200 belge ve latest_analysis_id |
| DELETE | `/documents/{document_id}` | Sahibi | 204; fiziksel temizlik, aynı sahibi tekrar çağırabilir |
| POST | `/documents/{document_id}/analysis` | Sahibi | body gerekmez; 202 analiz |
| POST | `/analyses` | Sahibi | JSON document_id; 202 analiz ve Location |
| GET | `/analyses/{analysis_id}` | Sahibi | 200 durum, eşik, config_snapshot |
| POST | `/analyses/{analysis_id}/retry` | Sahibi | uygun hatada 202 yeni/mevcut analiz |
| GET | `/analyses/{analysis_id}/matches` | Sahibi | completed ise 200 sayfalı kanıt |
| POST | `/admin/sources` | Admin | multipart dosya/lisans alanları; 201 indekslenen kaynak |
| GET | `/admin/sources` | Admin | status/license_status, limit/offset; 200 liste |
| POST | `/admin/sources/{source_id}/disable` | Admin | 200 pasif kaynak; dosya silinmez |
| POST | `/admin/sources/{source_id}/reindex` | Admin | 200 yeniden indekslenen kaynak |

Listeleme varsayılan `limit=20`, en fazla `100`, `offset≥0` kabul eder. Belge ve
admin kaynak listeleri JSON dizisidir; eşleşme yanıtı `total`, `limit`, `offset`,
`items` alanlarını içerir. Kaynak/minimum skor arayüz filtreleri sunucu filtreleri
değildir; matches API yalnız limit/offset kabul eder.

## Girdi ve sonuç kuralları

- Kayıt parolası 15–128 karakterdir. E-posta normalize edilir; kayıtla rol atanamaz.
- Dosya `file` alanında gönderilir; PDF/DOCX/TXT ve en fazla
  `20 * 1024 * 1024` byte. Multipart body sınırı ayrıca **21 MiB**'dir.
  Uzantı/MIME/içerik doğrulaması antivirüs taraması değildir.
- `retention_days` yalnız `7` veya `30`, varsayılan `7`. Yanıtta UTC `expires_at`
  verilir; otomatik silme aynı saniyede tamamlanma garantisi değildir.
- Admin kaynak için zorunlu: `file`, `title`, `license_name`, `rights_holder`,
  `license_evidence_reference`. İsteğe bağlı yazar, yayıncı, source_url,
  license_url, attribution_text ve izin tarihleri vardır. URL metadata'dır;
  URL'den belge indirilmez. Tarihler ISO `YYYY-MM-DD` biçimindedir.
- Yeni analiz body'si yalnız `document_id` kabul eder; sahip/durum/ağırlık/eşik
  istemci tarafından atanamaz. `202` tamamlandı anlamına gelmez.
- Başlatma tekrarları aynı son analizi döndürebilir; uygun başarısız analizde
  yeni çalıştırma için [retry](analysis-retry.md) gerekir.
- Yeni profil v2 / `0.7500` / `0.50–0.25–0.25`; snapshot analiz anındaki ayarları
  korur. Analiz `queued → processing → completed` veya `failed/cancelled`;
  belge ayrıca `extracting/analyzing` aşamalarını gösterir.
- Eşleşmeler yalnız completed analizde okunur; aksi halde `409 analysis_not_completed`.
  Decimal skor string (`"0.8012"`) olarak gelir. Ham skor ≥ eşik ile seçim yapılır;
  sonra kayıt skoru dört basamağa yuvarlanır.
- Kanıtlar normalize metindeki `[char_start, char_end)` Unicode karakter aralığıdır;
  UTF-8 byte veya JavaScript UTF-16 indeksi değildir. PDF sayfası 1 tabanlıdır;
  DOCX/TXT sayfası güvenilir değilse `null`. Eski bileşen kaydı `null` olabilir.
- PDF indirme/rapor endpointi yoktur; PDF tarayıcıda yazdırılabilir görünümden üretilir.

## Örnek akış — PowerShell 7

İlk kullanımda yeni hesap oluşturur; var olan hesapta register satırını atlayın.
`sample.txt` yerine izinli test dosyanızı seçin. Parola prompt ile alınır;
komut satırı argümanına veya cookie dosyasına yazılmaz.

```powershell
$api = 'http://localhost:8000/api/v1'
$headers = @{ 'X-CSRF-Protection' = '1' }
$credential = Get-Credential -UserName 'demo@example.test' -Message 'En az 15 karakter parola'
$login = @{ email = $credential.UserName; password = $credential.GetNetworkCredential().Password }
$registration = $login.Clone()
$registration.display_name = 'API örnek kullanıcısı'
Invoke-RestMethod -Method Post -Uri "$api/auth/register" -Headers $headers `
  -ContentType 'application/json' -Body ($registration | ConvertTo-Json)
Invoke-RestMethod -Method Post -Uri "$api/auth/login" -Headers $headers `
  -ContentType 'application/json' -Body ($login | ConvertTo-Json) -SessionVariable authSession
Invoke-RestMethod -Uri "$api/auth/me" -WebSession $authSession
$form = @{ file = Get-Item -LiteralPath './sample.txt'; retention_days = '7' }
$document = Invoke-RestMethod -Method Post -Uri "$api/documents" `
  -WebSession $authSession -Headers $headers -Form $form
$analysis = Invoke-RestMethod -Method Post -Uri "$api/analyses" `
  -WebSession $authSession -Headers $headers -ContentType 'application/json' `
  -Body (@{ document_id = $document.id } | ConvertTo-Json)

$finished = $false
for ($attempt = 0; $attempt -lt 180; $attempt++) {
  $detail = Invoke-RestMethod -Uri "$api/analyses/$($analysis.id)" -WebSession $authSession
  if ($detail.status -eq 'completed') { $finished = $true; break }
  if ($detail.status -in @('failed', 'cancelled')) {
    throw "Analiz tamamlanamadı: $($detail.failure_reason)"
  }
  Start-Sleep -Seconds 2
}
if (-not $finished) { throw 'Bekleme süresi doldu; iş sürüyor olabilir. Durumu tekrar sorgulayın.' }
$matches = Invoke-RestMethod -Uri "$api/analyses/$($analysis.id)/matches?limit=20&offset=0" `
  -WebSession $authSession
$matches.items
# Yalnız bu örnekte yüklenen belgeyi siler; önce sonucu inceleyin.
Invoke-RestMethod -Method Delete -Uri "$api/documents/$($document.id)" `
  -WebSession $authSession -Headers $headers
Invoke-RestMethod -Method Post -Uri "$api/auth/logout" -WebSession $authSession -Headers $headers
```

İstemci bekleme sınırı işi iptal etmez. Başarısız/yarım örnekte belgeyi ve oturumu
ayrıca temizleyin. Aktif analizde silme `409` dönebilir. Kullanıcı/audit/tombstone
metadata'sı örnek silmesiyle kaldırılmaz.

## Hata ve kota sözleşmesi

| Kod | Anlam / sonraki adım |
|---|---|
| 400 | Boş/bozuk/türü tutarsız veya geçersiz upload |
| 401 | Oturum eksik/geçersiz/süresi dolmuş veya hatalı giriş |
| 403 | CSRF/Origin, disabled kullanıcı veya admin yetkisi |
| 404 | Yok, silinmiş veya sahip olunmayan kaynak |
| 409 | Aktif işte silme, hazır olmayan analiz, retry/reindex çakışması |
| 413 | Dosya veya raw body boyut sınırı |
| 422 | Alan/UUID/saklama süresi/pagination veya admin kaynak doğrulaması |
| 429 | Kota doldu; Retry-After süresini bekleyin |
| 503 | Depolama/servis yok; document_cleanup_pending silmesi tekrar denenebilir |
| 500 | Beklenmeyen hata; takip kodunu operatöre iletin |

Hatalar `detail.code`, güvenli `detail.message`, `detail.trace_id` ve
`X-Request-ID` ile izlenir. Dışarı traceback/secret gönderilmez. Giriş kotası
e-posta başına 10/IP başına 50; kayıt IP başına 20; yükleme kullanıcı başına
10/IP başına 20 deneme / 5 dakika. [Kota ayrıntıları](request-protection.md).

Fiziksel temizlik [veri politikasında](data-policy.md), kanıt alanları
[eşleşme API belgesinde](match-evidence-api.md) açıklanır.
