# Changelog

Bu dosya kullanıcıya ve işletime yansıyan değişiklikleri sürüm bazında kaydeder.
Git etiketi veya yayımlanmış release kaydı oluşturulduğu anlamına gelmez.

## [Unreleased]

Henüz bu bölümde kayıtlı değişiklik yok.

## [0.1.0] — sürüm adayı, 8 Ekim 2026

İlk yerel prototip sürümünün kapsamı. Etiket/yayın henüz oluşturulmadı.

### Eklenenler

- Docker Compose ile API, web, PostgreSQL, Redis, MinIO, Celery worker ve scheduler kurulumu.
- Hesap kaydı/girişi, cookie oturumu, CSRF kontrolü, user/admin rolleri ve istek kotası.
- PDF/DOCX/TXT yükleme, metin çıkarma, chunk oluşturma ve izinli kaynak havuzuyla asenkron analiz.
- Kaynak/sayfa bilgisi, metin aralıkları ve skor bileşenleriyle eşleşme kanıtı;
  filtreler, ayrıntı görünümü ve tarayıcı üzerinden yazdırılabilir rapor.
- 7/30 günlük saklama seçimi, API ile silme ve süre dolumunda temizleme görevi.
- Kaynak lisans metadatası, admin kaynak ekleme/devre dışı bırakma/yeniden indeksleme.
- Üç kaynak ve dört kullanıcı belgesinden oluşan sentetik demo paketi;
  dosya manifesti, checksum ve yerel doğrulama çıktısı.
- Gerçek servislerle Playwright akışı, belge süre/bellek ölçümleri,
  sürümlü benzerlik fixture'ları, eşik ve ağırlık değerlendirmesi.
- CI test/build, bağımlılık/container/secret tarama işleri ve tarihli yerel tarama raporu.
- Kurulum, API, veri politikası, riskler ve bilinen sınırlar için kullanım belgeleri.

### Değiştirilenler

- Yeni analizler `classical-hybrid-v2`: eşik `0.7500`, sözcük TF-IDF / karakter
  TF-IDF / sözcük örtüşmesi ağırlıkları `0.50 / 0.25 / 0.25`.
- Veritabanı migration head `20261008_12`; eski analizler kendi snapshot'ını korur.

### Düzeltilenler

- Gerçek kullanıcı kimliğiyle analiz oluşturma ve raporun yazdırma stilleri.
- Merge sonrasında Alembic head birleşimi ve backend tip/format hataları.
- V2 worker altında eski v1 analiz snapshot'larının çalışabilmesi.

### Açık konular

Güvenlik taramasında açık HIGH/CRITICAL bulgular vardır. Bu sürüm üretime hazır
değildir. OCR, web'den kaynak toplama, genel benzerlik yüzdesi ve arayüzden silme
bu kapsamda bulunmaz. Ayrıntılar [sürüm notunda](docs/releases/v0.1.0.md),
[risklerde](docs/risks.md) ve [bilinen sınırlarda](docs/known-limitations.md).
