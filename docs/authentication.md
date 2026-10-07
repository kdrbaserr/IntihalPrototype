# Parola, oturum ve roller: ne, nasıl, neden?

| İşlem | Nasıl yaptık? | Ne için? |
| --- | --- | --- |
| Parola saklama | Argon2id; her parola için ayrı rastgele salt, 64 MiB bellek ve 3 tur | Veritabanı sızarsa parola tahminini pahalılaştırmak |
| Oturum | 32 rastgele byte içeren anahtar; veritabanında yalnız SHA-256 özeti | Kullanıcı kimliğinin taklit edilmesini önlemek, çıkışta erişimi iptal etmek |
| Cookie | HttpOnly, SameSite=Lax, Path=/; staging/production ortamında Secure ve __Host- öneki | JavaScript erişimini ve uygunsuz cookie aktarımını sınırlamak |
| CSRF | Veri değiştiren her istekte X-CSRF-Protection: 1; varsa Origin için izin listesi | Başka sitenin kullanıcının oturumuyla işlem başlatmasını engellemek |
| Roller | Kayıt user üretir; admin yalnız güvenilir sunucu komutuyla atanır | Kullanıcının kendi yetkisini yükseltmesini engellemek |
| Deneme sınırı | Veritabanında atomik sayaç; girişte e-posta ve IP, kayıtta IP | Parola tahmini ve kayıt saldırılarını sınırlamak |

## Öğrenmen gereken mimari noktalar

- **Authentication / authorization:** Oturum “kimsin?” sorusunu yanıtlar; rol ve belge sahipliği “bu işlemi yapabilir misin?” sorusunu yanıtlar. Kontroller API'de uygulanır; arayüzde buton gizlemek güvenlik kontrolü değildir.
- **Hash / şifreleme:** Parolayı geri çözmeye ihtiyacımız yoktur. Girilen parolayı Argon2id ile doğrularız. Salt hash içinde saklanır. SHA-256 parolaya uygun değildir; yüksek entropili rastgele oturum anahtarına uygundur.
- **Stateful session:** Sunucu oturum kaydını tutar. JWT yerine bu yaklaşımı seçtik; çıkışta kayıt silinince eski cookie anında geçersiz olur. Bunun bedeli her korumalı istekte veritabanı sorgusudur.
- **Oturum yenileme:** Başarılı her giriş yeni anahtar üretir ve tarayıcının önceki oturumunu siler. Böylece session fixation önlenir. Oturum en fazla 8 saat geçerlidir; kullanım süreyi uzatmaz.
- **Güncel yetki:** Kullanıcının rolü ve aktiflik durumu her istekte veritabanından okunur. Rol değişikliği ve hesabın devre dışı bırakılması mevcut oturumlara da uygulanır. Admin belge sahipliği kontrolünü atlayamaz.
- **CORS / CSRF:** CORS tek başına CSRF koruması değildir. Özel başlık tarayıcıda preflight gerektirir; API yalnız açıkça izin verilen origin'lere credential erişimi verir. Cookie kullanılan POST isteklerinde başlık zorunludur. CLI istemcileri de başlığı gönderir.
- **Async / CPU işi:** Argon2id bilerek pahalıdır. Hashleme/doğrulama thread pool'da çalışır; API'nin event loop'u bloke edilmez. Thread kullanmak hesaplama maliyetini ortadan kaldırmaz.
- **Migration:** Eski kullanıcıya tahmin edilebilir varsayılan parola atamadık. password_hash NULL kalır, hesap giriş yapamaz; belgeleri korunur. Parolayı yönetim komutuyla atamak gerekir.
- **Ortak rate limit:** Process belleğinde sayaç kullanmak birden fazla API instance'ında tutarsız olur. PostgreSQL upsert sayacı atomik artırır. Beş dakikalık sabit pencere kullanıyoruz; pencere sınırında iki dönemin kotası art arda kullanılabilir.
- **HTTP hata kodları:** 401 oturum/giriş sorunu, 403 yetersiz yetki veya CSRF, 409 kayıt çakışması, 422 geçersiz alan, 429 fazla deneme anlamına gelir. Yanıt ve loglarda parola veya cookie yer almaz.

## API sözleşmesi

Tüm yollar `/api/v1/auth` altındadır.

| Yöntem / yol | Girdi | Sonuç |
| --- | --- | --- |
| POST /register | email, display_name, password | 201, user; ardından giriş gerekir |
| POST /login | email, password | 200, user ve Set-Cookie |
| GET /me | Oturum cookie'si | 200, kullanıcı ve rolü |
| POST /logout | Cookie ve CSRF başlığı | 204; oturumu siler, cookie'yi temizler; tekrar çağrılabilir |

Parola 15–128 karakterdir; boşluk ve Unicode kabul edilir, parola trim edilmez.
E-posta trim edilip küçük harfe dönüştürülür. role/status gibi ek kayıt alanları reddedilir.
Tarayıcı fetch için credentials: include, XMLHttpRequest için withCredentials: true kullanır.
Parola ve oturum anahtarı localStorage'a yazılmaz. Kimlik yanıtları Cache-Control: no-store taşır.

Giriş kotası e-posta başına 10, IP başına 50 deneme / 5 dakika; kayıt kotası IP başına 20'dir.
Başarılı girişler de kotaya dahildir. Kota dolduğunda Retry-After döner.
IP, doğrudan bağlantı bilgisidir; uygulama X-Forwarded-For başlığını kendisi kabul etmez.
Proxy arkasında Uvicorn'un güvenilir proxy ayarlarını açıkça yap; aksi halde tüm kullanıcılar
proxy IP'sinin kotasını paylaşabilir. Key'ler kimliklerin hash'idir, düz e-posta/IP değildir.

## Çalıştırma ve admin oluşturma

Docker motoru açıkken proje kökünde:

```powershell
docker compose up -d --build
docker compose exec api alembic upgrade head
# Yeni admin oluşturur veya mevcut kullanıcının parolasını/rolünü günceller:
docker compose exec api python -m intihal_api.db.manage_user admin@example.com --name "Yönetici" --role admin
```

Komut parolayı iki kez gizli olarak sorar; komut satırına parola koyma. Mevcut kullanıcı
parolası/rolü güncellenirken tüm oturumları iptal edilir. Hesap disabled ise komut onu
otomatik etkinleştirmez. Eski bir hesabın belgelerini korumak için aynı e-posta adresini kullan.
Normal kullanıcı web ekranından kayıt olabilir. Kurulum artık otomatik varsayılan admin üretmez.

Yerel demo seed isteğe bağlıdır: yalnız local ortamında açıkça verilen
INTIHAL_DEMO_PASSWORD ile çalışır. Docker içinde gerekirse yönetim komutunu kullan;
demo parolası Compose ortamına otomatik aktarılmaz.

PowerShell ile API girişi:

```powershell
$headers = @{ "X-CSRF-Protection" = "1" }
$credential = Get-Credential -UserName "user@example.com" -Message "Uygulama girişi"
$payload = @{ email = $credential.UserName; password = $credential.GetNetworkCredential().Password } | ConvertTo-Json
Invoke-RestMethod -Method Post -Headers $headers -ContentType "application/json" -Body $payload -SessionVariable authSession -Uri "http://localhost:8000/api/v1/auth/login"
$payload = $null
$credential = $null
Invoke-RestMethod -WebSession $authSession -Uri "http://localhost:8000/api/v1/auth/me"
Invoke-RestMethod -Method Post -Headers $headers -WebSession $authSession -Uri "http://localhost:8000/api/v1/auth/logout"
```

## Ortam ve doğrulama

INTIHAL_SESSION_TTL_SECONDS varsayılan 28800'dür. INTIHAL_ENVIRONMENT staging veya
production olduğunda cookie Secure olur ve __Host-intihal_session adını alır;
CORS origin'leri HTTPS olmalıdır. Local HTTP'de intihal_session kullanılır.
API ve web'i aynı site altında barındır; farklı sitelerde SameSite=Lax cookie gönderilmez.
localhost ile 127.0.0.1 adreslerini karıştırma. Üretimde HTTPS/TLS sonlandırmasını kur.

20261007_08 migration'ı users.password_hash, user_sessions ve authentication_throttles
şemasını ekler. Downgrade oturumları ve parola hash'lerini siler; yeniden upgrade parola
hash'lerini geri getirmez. Süresi dolan kayıtlar yeni giriş/deneme sırasında temizlenir.

SQLite üzerinde gerçek kayıt/giriş/çıkış, cookie rotasyonu ve iptali, süre aşımı,
CSRF, rol değişimi, disabled hesap, hash saklama, kota ve sırların loga sızmaması test edilir.
PostgreSQL migration/ownership testleri INTIHAL_TEST_DATABASE_URL ile ayrı test veritabanında
çalışır. Web testleri kayıt, cookie ile giriş, çıkış, oturumun geri yüklenmesi ve süre
sonunda giriş ekranına dönüşü doğrular. Bu adım e-posta doğrulama, MFA ve self-service
parola sıfırlama akışlarını kapsamaz.

Kaynaklar: [OWASP Password Storage](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html),
[OWASP Session Management](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html),
[OWASP CSRF Prevention](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html).
