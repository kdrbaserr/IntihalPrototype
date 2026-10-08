# Veri saklama, erişim ve silme politikası

Sürüm 1.0 — 8 Ekim 2026. Kapsam: mevcut yerel prototip. Bu belge uygulanmış
teknik davranışı ve operatörün tamamlaması gereken süreçleri ayırır; hukuki
uygunluk veya anonimleştirme sertifikası değildir.

## Amaç ve veri akışı

Kullanıcı dosyası, izinli kaynak havuzuyla açıklanabilir metin benzerliği için
işlenir. Kullanıcı yüklemeleri otomatik olarak kaynak havuzuna eklenmez.
Bu sürümün analiz hattında dış LLM/embedding servisine belge gönderimi veya
model eğitimi işi yoktur. Bağımlılık/güvenlik araçları ayrı geliştirme işlemleridir;
paket metadatası için dış registry/advisory servislerine erişebilirler.

Dosya → MinIO aslı + PostgreSQL metadata → worker'da çıkarma/normalizasyon →
PostgreSQL metin parçaları → izinli kaynaklarla karşılaştırma → eşleşme kanıtı →
oturum sahibi için web/JSON ve tarayıcıda PDF. Geçici multipart/extraction verileri
process belleğinde veya çalışma ortamının geçici dosya alanında bulunabilir.

## Veri envanteri ve süreler

| Veri | Yer | Süre / silme davranışı |
|---|---|---|
| Kullanıcının PDF/DOCX/TXT aslı | MinIO, Docker minio_data volume | Yüklemeden itibaren 7/30 gün; manuel silme veya süre temizliği |
| Normalize metin parçaları, konumlar, hash'ler | PostgreSQL document_chunks | Belge fiziksel temizliğiyle silinir |
| Analiz, config snapshot, skor/kanıt | PostgreSQL analyses/matches | Belge fiziksel temizliğiyle silinir |
| Belge metadata/tombstone | PostgreSQL documents | İçerik silinse de kalır; otomatik metadata purge yok |
| Hesap: e-posta/ad/rol/durum, Argon2id parola hash'i | PostgreSQL users | Otomatik hesap silme/süre politikası uygulanmadı |
| Oturum token özeti ve zamanları | PostgreSQL user_sessions | Erişim varsayılan 8 saatte biter; logout/yönetim işlemleri iptal eder |
| HMAC kota anahtarı/sayaç/expiry | PostgreSQL authentication_throttles | Süresi geçen kayıtlar yeni kota kontrollerinde temizlenir; anlık purge garantisi yok |
| İşlem/aktör/hedef UUID ve UTC zamanları | PostgreSQL audit_events | Otomatik saklama süresi/purge yok; düzenleme/silme API'si yok |
| Lisanslı kaynak aslı, metni ve lisans kanıt referansı | MinIO + source_documents/source_chunks | Kullanıcı belge süresine tabi değil; disable fiziksel silmez |
| Görev mesajı/sonuç metadatası | Redis redis_data volume | Celery result TTL varsayılan 86400 saniye; kuyruk mesajı için aynı süre garantisi yok |
| Log, test trace, screenshot, PDF ve ölçüm dosyası | Docker logları / yerel test-output klasörleri | Bu uygulamada ortak otomatik saklama/temizleme politikası yok |
| Yedekler ve dışa aktarılan raporlar | Operatör/kullanıcı ortamı | Uygulama silmesi bunları geri çağıramaz; ayrı süre ve temizlik gerekir |

PostgreSQL'de yalnız metadata değil, **çıkarılmış metin içeriği de** vardır.
Tombstone kaydı owner UUID, dosya adı, boyut, checksum, storage konumu ve tarih
alanlarını korur. Bunlar anonim veri olarak kabul edilmemelidir. Dosyanın gömülü
metadatası veya metin içindeki kişisel bilgiler otomatik anonimleştirilmez.

Oturumun erişim süresinin bitmesi, satırın aynı anda fiziksel silinmesi demek
değildir. Hesap, metadata, audit, log ve yedekler için süreler dağıtım operatörü
tarafından ayrıca belirlenip uygulanmalıdır; şu anda bu eksik işlerdir.

## Belge silmenin gerçek kapsamı

1. Sahiplik ve belge satır kilidi doğrulanır. Admin sahiplik kontrolünü atlayamaz.
2. queued/extracting/analyzing belge `409 document_processing` ile korunur;
   iş sürerken dosya silinmez.
3. `deleted` tombstone kalıcılaştırılır; okuma/liste/rapor yolları 404 üretir.
4. MinIO aslı kaldırılır; analiz, eşleşme ve kullanıcı metin parçaları silinir.
5. `cleaned_at` ve başarılı audit olayı kaydedilir; tombstone kalır.

MinIO ve DB tek transaction paylaşmaz. Depolama/DB arızasında belge gizlenmiş
olabilir fakat fiziksel temizlik bitmemiş olabilir. Aynı sahip DELETE'i tekrar
çağırabilir; arka plan işi de yarım silmeyi tamamlamayı dener. `204` başarılı
temizliği ifade eder; tamamlanmış silmede tekrar DELETE de 204'tür. Kaydı olmayan
veya başka kişiye ait UUID 404 döner. Bir 404 okuma sonucu tek başına fiziksel
temizliğin kanıtı değildir; [temizlik doğrulaması](local-development.md) kullanılabilir.

Süre temizliği scheduler tarafından **saatlik**, bir batch'te en fazla **100**
belgeyle yürütülür. Aktif işler, kilitli satırlar, servis kesintisi ve backlog
silme zamanını geciktirebilir. Süresi dolan belge, temizlik tamamlanana kadar
yalnız expires_at nedeniyle otomatik gizlenmez; bu sürümde süre tabanlı erişim
kesme garantisi yoktur. Operatör geciken/yarım temizliği izlemelidir.

Kaynak havuzu, hesap, audit, rapor/PDF kopyası, backup ve storage medyasının
forensik/sanitizasyonu bu silme işleminin kapsamı değildir. Uygulama yalnız
çalışan DB/MinIO içeriğinin kaldırılmasını doğrular.

## Erişim ve koruma

- USER kendi belgelerini; ADMIN ayrıca kaynak havuzunu yönetir. Doğrudan DB,
  MinIO veya Docker yetkisi olan operatör API sahiplik sınırının dışındadır.
- Parola Argon2id; yüksek entropili oturum anahtarının yalnız SHA-256 özeti DB'de
  saklanır. Bu, belge içeriğinin şifrelenmesi değildir.
- Cookie HttpOnly/SameSite=Lax; staging/production Secure. Yerel Compose HTTP
  kullanır; uygulama düzeyinde belge şifreleme veya KMS/at-rest politikası yoktur.
- Audit içerik/filename/checksum/token/header/gövde tutmaz; sabit işlem ve UUID
  alanları kullanır. UUID'ler hesapla ilişkilendirilebilir; audit anonim değildir.
- Log redaction, erişim kontrolleri ve kotalar uygulanır. Playwright PDF/trace
  gibi geliştirme çıktıları belge metni ve oturum bilgisi içerebilir; kontrollü
  erişimle tutulmalı, paylaşılmadan önce gözden geçirilmelidir.

## Kaynak havuzu ve kaldırma talepleri

Yalnız ready + approved ve geçerli izin tarihine sahip kaynaklar yeni analizde
kullanılır. Lisans kanıtının gerçek içeriği dış güvenli kayıtta, referansı DB'de
tutulur. [Kaynak edinme politikası](source-acquisition-policy.md) karar matrisidir;
admin alanlara değer girdi diye kullanım hakkı otomatik doğrulanmış sayılmaz.

İzin iptali/kaldırma talebinde operatör kaynağı disable eder, yeni analizleri
kontrol eder; eski rapor kanıtları, dosya/chunk bağımlılıkları ve yedekler için
ayrı temizlik kararı uygular. Disable geçmiş kanıtı fiziksel kaldırmaz. Kaynak
silme/lisans güncelleme için genel API henüz yoktur.

## Operatör süreçleri ve mevcut açıklar

Demo/CI/ölçümde yalnız sentetik veya açıkça izinli test verisi kullanılır. Gerçek
kişisel belge kabulünden önce sorumlu kurum; amaç, erişim yetkisi, bilgilendirme,
işleme dayanağı, süreler ve talep/olay yanıt sürecini belirlemelidir. Uygulama
bu kararları veya kişisel veri taramasını otomatik yapmaz.

Hesap silme/export/şifre sıfırlama self-service akışı, audit/log/backup purge,
yerleşik yedek/geri yükleme ve doğrulanmış kriz prosedürü yoktur. Parola/rol CLI
işlemi oturumları iptal eder; disabled hesabı otomatik etkinleştirmez. Kaldırma
veya veri erişim talebi operatöre iletilir; kimlik ve sahiplik doğrulanır, kapsam
(canlı veri + metadata + yedek + dış çıktı) kaydedilir. Teknik silme testi tek
başına bütün veri yükümlülüklerinin tamamlandığı anlamına gelmez.

İlgili kanıt: [audit sözleşmesi](audit-events.md), [güvenlik/silme testleri](security-tests.md),
[riskler](risks.md), [bilinen sınırlar](known-limitations.md).
