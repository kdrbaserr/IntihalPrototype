# Açık risk kaydı

Gözden geçirme: 8 Ekim 2026. Öncelikler prototip için mühendislik değerlendirmesidir;
otomatik scanner çıktısı istismar kanıtı değildir. Bu belge üretim onayı değildir.
Dağıtım ve risk kararlarının sorumlusu dağıtım operatörüdür.

| Öncelik / risk | Mevcut kanıt veya önlem | Açık iş / kapanış kanıtı |
|---|---|---|
| P0 — Container/bağımlılık açıkları | 8 Ekim taramasında MinIO 6, PostgreSQL image 1 kritik kayıt; API/web ve npm/Python bulguları var | İlgili sürüm/base image düzeltmeleri; yeniden build + tarama + regresyon. Bulgular kapatılmadı |
| P0 — Geliştirme dağıtımının dış erişimi | Compose HTTP, örnek parolalar, root MinIO kimliği ve host'a yayınlanan altyapı portları kullanır | Üretim ağı/kimliği/TLS/secret yönetimi ve en az yetki; erişim testi. Hazır production Compose yok |
| P1 — Sonucun yanlış yorumlanması | Kaynak, kesit ve açıklanabilir skor gösterilir; intihal kararı verilmez | İnsan incelemesi, geniş bağımsız etiketli set; genel doğruluk iddiası yok |
| P1 — Küçük sete uyum / eşik değişimi | v2 dört çiftte seçildi; v1 snapshot korunur | Gerçek dil/uzunluk/kaynak çeşitliliğinde yanlış pozitif/negatif ölçümü; v2 yük testi |
| P1 — Saklama süresinden geç silme | Saatlik 100 belgeli batch, tekrar edilebilir temizlik, tombstone ve cleaned_at | Geciken silme alarmı, süre tabanlı erişim kesme, birikim testi; son tarih SLA'sı yok |
| P1 — Kalan kişisel metadata/kopyalar | İçerik silinir; metadata/audit/hesap ve dış raporlar ayrı kalır | Metadata/log/audit/backup süreleri ve talep süreci; anonimleştirme yok |
| P1 — Kötücül/yoğun belgeyle kaynak tüketimi | 20 MiB dosya, 21 MiB body, kotalar, worker 240/300 s sınırları | Antivirüs, parser izolasyonu, açılmış arşiv/page/token/memory limitleri ve kötü belge yük testi |
| P1 — Büyük kaynak havuzunda ölçek | Her kullanıcı chunk'ı uygun kaynak chunk'larıyla karşılaştırılır | Aday bulma indeksi, büyük corpus/concurrency ölçümü; kapasite garantisi yok |
| P1 — Veri kaybı / geri yükleme | PostgreSQL/MinIO/Redis named volume'ları kalıcı; down veriyi kaldırmaz | Uyumlu DB+MinIO yedeği, retention ve restore provası; yerleşik backup yok |
| P1 — Kaynak izin hatası | Lisans alanları, kanıt referansı, approved/tarih/ready filtresi | Gerçek hak zinciri incelemesi ve iptal/kaldırma prosedürü; alanlar hukuki izin üretmez |
| P2 — İş kesintisi / broker gecikmesi | Kalıcı durum, dispatcher, bounded retry ve dayanıklılık testleri | İzleme/uyarı, backlog alarmı, çok worker/uzun kesinti testleri; exactly-once garantisi yok |
| P2 — Proxy/IP kotası | Uvicorn proxy başlığı yerelde kapalı, DB atomik sayaç ve CSRF | Gerçek reverse proxy trust/IP/CORS dağıtım testi; proxy IP'sinde kota paylaşımı olabilir |
| P2 — Admin/operatör gücü | API'de admin de sahiplik sınırına tabi; CLI oturum iptal eder | DB/MinIO/Docker operatör yetkileri, MFA/ayrı yönetim ağı; API dışı erişim ayrı sınır |
| P2 — Audit değiştirilebilirliği | Enum/UUID alanlar, uygulamada yalnız append; transaction ile kayıt | Doğrudan DB operatörüne karşı immutable/WORM kayıt; mevcut tablo bunu garanti etmez |
| P2 — CI yeşilinin kapsamı | Lint/test/build ve yeni güvenlik workflow'u var | Uzak run/required check sonucu ayrıca incelenir; yerel rapor GitHub koşusu kanıtı değildir |

## Güvenlik bulgularının yorumu

[Tarihli güvenlik raporu](security-ci-2026-10-08.md) hedef image kimliklerini ve
[ham özet JSON](measurements/2026-10-08-security-checks.json) paket/advisory sürümlerini
verir. Sayılar taranan **o image** içindir; sonraki build'lere otomatik taşınamaz.
HIGH/CRITICAL paket–advisory kayıtları aynı açığı birden fazla pakette sayabilir.

MinIO bulgularının bazıları OIDC/LDAP/AMQP/gRPC kullanım koşullarına bağlıdır;
PostgreSQL image'ının kritik kaydı Go stdlib TLS bileşenine aittir. Next Image
Optimization SSRF kaydı remotePatterns koşuluna bağlıdır; mevcut next.config'te
bu ayar yoktur. Bunlar risk değerlendirmesine girdidir; bütün scanner bulgularını
tek seferde dışlamaz. Ignore listesi veya zorla major downgrade uygulanmadı.

Yeni CI Python bulgularında, npm/container HIGH/CRITICAL'de ve secret bulgusunda
işi başarısız yapar; düzeltmesiz açıklar da container gate'ine dahildir. Secret
taramasında bulgu çıkmaması bütün olası sırların veya geçmiş dış kopyaların temiz
olduğu garantisi değildir. Güncel GitHub Actions sonuçları ayrıca kontrol edilir.

## Risk kapatma ve olay yanıtı

Her düzeltmede hedef sürüm/image ID, önce/sonra scanner çıktısı, ilgili fonksiyon
testi ve varsa kalan kabul kararı kaydedilir. Düzeltme yoksa etkilenen özelliği
kapatma/erişimi sınırlama kararı açıkça belgelenir; sessiz allowlist yapılmaz.

Sır ifşasında operatör erişimi sınırlar, ilgili kimliği iptal/rotate eder,
oturumları iptal eder ve log/audit kapsamını inceler. Commit'ten satır silmek
tek başına sızmış anahtarı geçersiz kılmaz. Veri kaybında temiz ortamda restore
denenmeden üretim verisi üzerine geri yükleme yapılmaz. Bu olay prosedürü henüz
tatbikatla doğrulanmış veya görevli/iletişim süreleri atanmış bir SLA değildir.

Veri kapsamı [veri politikasında](data-policy.md), ürün kapasitesi
[bilinen sınırlarda](known-limitations.md) açıklanır.
