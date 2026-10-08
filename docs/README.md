# Dokümantasyon

Son gözden geçirme: **8 Ekim 2026**. Güncel profil v2; migration head `20261008_12`.

| Konu | Başlangıç belgesi |
|---|---|
| Kurulum ve işletim | [Yerel geliştirme](local-development.md) |
| API kullanımı | [API referansı](api-reference.md) |
| Veri saklama ve silme | [Veri politikası](data-policy.md) |
| Açık riskler | [Risk kaydı](risks.md) |
| Bilinen sınırlar | [Kapsam ve sınırlar](known-limitations.md) |

Bu klasör teknik ve operasyonel belgeleri, tarihli ölçümleri ve politika kararlarını içerir.

Ayrıntılı belgeler:

- sistem mimarisi ve veri akışı,
- yerel kurulum adımları,
- API kullanımı,
- veri saklama ve KVKK kararları,
- izinli kaynak havuzu kuralları,
- kabul edilen lisanslar ve yasak veri toplama davranışları
  (`source-acquisition-policy.md`),
- algoritmanın sınırları ve değerlendirme sonuçları,
- worker, kuyruklar, timeout/retry politikası ve mühendislik notları
  (`worker-queues.md`).
- belge durum zinciri, worker entegrasyonu ve ⭐ mühendislik notları
  (`document-workflow.md`).
- analiz oluşturma, durum sorgulama, eşleşme endpointleri ve ⭐ API notları
  (`analysis-api.md`).
- güvenli hata kodları, takip kodu, ayrıntılı log trace ve ⭐ mühendislik notları
  (`error-handling.md`).
- çift tıklama koruması, kontrollü manuel retry ve ⭐ notlar (`analysis-retry.md`).
- başarı, timeout, worker kesintisi ve retry senaryo testleri
  (`worker-resilience-tests.md`).
- kuyruk, metin çıkarma, analiz ve hata durumlarının kullanıcıya gösterimi
  (`analysis-status-ui.md`).
- eşleşme aralıkları, kaynak/sayfa bilgileri ve kalıcı skor bileşenleri
  (`match-evidence-api.md`).
- çakışan aralıkların birleştirilmesi ve skor renkleri (`match-highlighting.md`).
- kaynak/minimum skor filtreleri ve eşleşme ayrıntıları (`match-filters-details.md`).
- yöntem, tarih, kaynaklar ve uyarı içeren yazdırılabilir görünüm (`printable-report.md`).
- Playwright ile gerçek tarayıcı yükleme/bekleme/rapor akışı ve kapsam sınırları
  (`playwright-workflow.md`).
- Küçük/orta/büyük belge süre ve bellek ölçümleri
  ([8 Ekim 2026 sonuçları](document-performance-2026-10-08.md)).
- Merge geçmişi, conflict çözümü ve backend tip kontrolü
  ([8 Ekim 2026 incelemesi](merge-audit-2026-10-08.md)).
- Etiketli regresyon setinde eşiklerin precision/recall ve yanlış karar etkisi
  ([8 Ekim 2026 raporu](threshold-effects-2026-10-08.md)).
- Ölçüme dayalı v2 eşik/ağırlık ayarları ve eski snapshot uyumluluğu
  ([8 Ekim 2026 kalibrasyonu](similarity-calibration-2026-10-08.md)).
- CI bağımlılık, container ve secret kontrolleri
  ([8 Ekim 2026 tarama sonuçları](security-ci-2026-10-08.md)).

Tarihli v1 raporları tarihsel kanıttır; güncel ayarları v2 kalibrasyon belgesi
tanımlar. Yeni tarama ve ölçümler eski sonuçların üzerine yazılmadan kaydedilir.

## Dokümantasyon doğrulaması

8 Ekim 2026 gözden geçirmesinde kurulum scriptleri/Compose, API route ve şemaları,
temizlik/retention kodu, v2 ayarları ve tarihli risk ölçümleri karşılaştırıldı.
API tablosundaki 18 işlem üretilen OpenAPI ile eşleşir. README'ler ve docs içindeki
32 belgenin yerel Markdown bağlantıları kontrol edildi; kırık bağlantı bulunmadı.
PowerShell 7 API örneği sözdizimi kontrolünden geçti; örnek bu incelemede yeni
kullanıcı/veri oluşturarak ayrıca çalıştırılmadı. Çalışan API'de health, versioned
health, docs ve openapi.json adresleri 200 döndü; Compose config ve migration head
doğrulandı. Uygulama davranışı bu dokümantasyon çalışmasında değiştirilmedi.

## Giriş ve roller

Parola hashleme, cookie oturumu, user/admin rolleri ve admin oluşturma komutu için
[kimlik doğrulama ve mimari notlarını](authentication.md) okuyun. Normal hesap web ekranından açılır;
admin sunucu komutuyla atanır. Eski hesaplara parola atanması gerekir.
