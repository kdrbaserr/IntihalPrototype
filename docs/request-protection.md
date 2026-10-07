# İstek kotaları ve log redaction

| İşlem | Hesap/kullanıcı | IP | Pencere |
| --- | --- | --- | --- |
| Login | Normalize e-posta başına 10 | 50 | 5 dakika |
| Register | — | 20 | 5 dakika |
| Belge veya admin kaynak yükleme | Kullanıcı başına 10 | 20 | 5 dakika |

Başarılı ve servis doğrulamasında reddedilen denemeler kotaya dahildir. Kimlik,
CSRF ve zorunlu multipart alanları geçerli olmalıdır; ayrıştırılamayan istekler
uygulama kotasına ulaşmaz. Login kontrolü Argon2'den, yükleme kontrolü hashleme,
içerik doğrulaması ve MinIO yazımından önce yapılır. Multipart gövdesi framework
tarafından bağımlılıklar çalışmadan önce ayrıştırılır.

Sayaçlar mevcut `authentication_throttles` tablosunda PostgreSQL atomik upsert
ile tutulur. Reddedilen isteğin artırımı da commit edilir; rollback, uygulamanın
yeniden başlatılması veya API kopyası değiştirmek kotayı sıfırlamaz. Süresi dolan
sayaçlar temizlenir. Sabit pencere sınırında iki pencerenin kotası art arda
kullanılabilir; bu tam kayan pencere garantisi değildir.

Sayaç anahtarı HMAC-SHA256'dır. Ham IP/e-posta tutulmaz. Redis sunucu sırrı ve
`intihal-rate-limit` ayrımı kullanılır; API kopyaları aynı sırrı paylaşmalıdır.
Sırrı değiştirmek aktif kotaların yeni anahtarlardan başlamasına neden olur.

Limit aşımında `429`, güvenli mesaj ve `Retry-After` döner. CORS bu başlığın
tarayıcı tarafından okunmasına izin verir. Yerel Uvicorn `--no-proxy-headers`
kullanır; uygulama istemcinin X-Forwarded-For başlığını kabul etmez.

## HTTP gövde sınırı

Belge ve kaynak yükleme POST gövdeleri en fazla 21 MiB'dir: 20 MiB dosya ve
multipart metadata için 1 MiB pay. Dosyanın kendi 20 MiB kontrolü korunur.
Content-Length fazla ise gövde okunmadan `413` döner. Content-Length yoksa veya
yanlışsa gerçek byte sayısı akışta kontrol edilir. Sınır aşımında multipart
parser'ın açtığı geçici dosyalar kapatılır. Limit anonim isteklere de uygulanır.

## Redaction kapsamı

Redaction loglar, audit ve hata teşhis çıktılarındadır. Yetkili analiz akışı için
saklanan belge/chunk/eşleşme içeriği bu işlemle değiştirilmez.

`log_error` yalnız sabit olay/hata kodu, geçerli UUID, sabit aşama, HTTP yöntemi,
durum kodu ve sunucunun tanımladığı route şablonunu kabul eder. Hassas alanlar
`[REDACTED]` olur; bilinmeyen alan adları ve değerleri de aktarılmaz. Bu,
kişisel veriyi regex ile tahmin etmeye dayanmaz; tüm belge metni alanını maskeler.
Exception mesajı, SQL, locals, header, cookie ve body kaydedilmez. Trace yalnız
istisna türü, dosya basename'i, satır ve fonksiyon içerir; mutlak dizin yolu yoktur.

Python logging koruması uygulamanın serbest metin logları, httpx/httpcore,
urllib3/MinIO, PDF/DOCX/encoding kütüphaneleri ve SQLAlchemy mesajlarını, argümanlarını,
exception metinlerini ve extra alanlarını maskeler. Aynı koruma Celery'nin
logging kurulumu sonrasında worker'a da yüklenir. Güvenli yapılandırılmış
uygulama teşhis kayıtları korunur. Uvicorn ham access logu kapalıdır; URL query
ve IP bu kanaldan kaydedilmez. MuPDF'nin doğrudan stderr'e yazdığı hata/uyarılar
kapatılır; PyMuPDF mesajları filtrelenen Python logging'e yönlendirilir.
CLI kullanıcı yönetimi e-posta yerine UUID basar.

Audit kaydının sabit enum/UUID alanları korunur; belge veya PII payload alanı yoktur.
Bu koruma eski logları geriye dönük silmez; harici proxy/MinIO erişim logları kendi
dağıtım ayarlarıyla yönetilir.
