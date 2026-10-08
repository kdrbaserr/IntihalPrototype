# Dokümantasyon

Bu klasör projenin teknik ve operasyonel belgelerini barındıracaktır.

Burada zamanla şunlar tutulacaktır:

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

Kodun ne yaptığını yalnız koddan tahmin etmek yerine önemli kararları burada
açıkça kaydedeceğiz.

## Giriş ve roller

Parola hashleme, cookie oturumu, user/admin rolleri ve admin oluşturma komutu için
[kimlik doğrulama ve mimari notlarını](authentication.md) okuyun. Normal hesap web ekranından açılır;
admin sunucu komutuyla atanır. Eski hesaplara parola atanması gerekir.
