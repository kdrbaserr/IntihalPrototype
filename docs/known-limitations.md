# Bilinen sınırlar ve doğrulama kapsamı

Gözden geçirme: 8 Ekim 2026. Bu sürüm açıklanabilir klasik metin benzerliği
prototipidir; genel internet taraması veya akademik intihal hükmü üretmez.

## Belge ve metin çıkarma

PDF, DOCX ve TXT; en fazla 20 MiB dosya ve 21 MiB multipart body kabul edilir.
Şifreli PDF ve metin çıkarılamayan belge analiz edilemez. OCR yoktur: yalnız
görüntü içeren PDF'de OCR gereksinimi hata olarak bildirilir. Karma metin/görüntü
PDF'de çıkarılan metin analiz edilir; görüntüdeki yazı için tam kapsam garanti edilmez.

PDF okuma sırası, çok sütun, tablo, dipnot, DOCX paragraf/yapı ve TXT encoding
çıkarımı sonucu etkileyebilir. Özgün düzen, sayfa koordinatları veya DOCX'in Word
render'ı korunmaz. TXT/DOCX için güvenilir sayfa numarası yoktur. Metin normalize
edilir; kanıt aralığı orijinal dosyanın byte/ekran koordinatı değildir.

Dosya doğrulaması güvenli dosya sertifikası değildir. Antivirüs/sandbox yoktur;
yükleme boyutu, açılmış DOCX arşivi veya PDF'den çıkarılan metnin boyutunu sınırlamaz.

## Algoritma ve kaynak kapsamı

- TF-IDF sözcük/karakter n-gramları ve sözcük kümesi örtüşmesi vardır; embedding,
  çeviri, anlamsal paraphrase, görsel veya formül karşılaştırması uygulanmadı.
- Türkçe karakter normalizasyonu desteklenir; bütün dillerde kalite ölçülmedi.
  Ortak kalıplar yanlış pozitif; çeviri, yoğun yeniden yazım ve kısa kesitler
  yanlış negatif üretebilir.
- Yalnız sisteme alınmış ready/approved ve geçerli lisans tarihli kaynaklar
  karşılaştırılır. Havuzda olmayan eserin kullanımı bulunamaz. source_url yalnız
  metadata'dır; internet crawling/URL indirme yoktur.
- Mevcut demo havuzu üç sentetik kaynaktır. Büyük yayınevi/tez/internet corpus'u
  kapsamına sahip olduğu iddia edilmez.
- v2 eşik 0,75 ve ağırlıklar 0,50/0,25/0,25. Dört sabit regresyon örneği üzerinde
  yedi ağırlık ve 101 eşik tarandı; bağımsız kalibrasyon/test ayrımı yoktur.
  İki sınıfta yüzde 100 sonuç yalnız bu dört çift içindir; genel doğruluk değildir.
- Eşik chunk çiftine uygulanır. Ardından ortak ardışık token kanıtı çıkarılır;
  skorun geçmesi tek başına belge geneli veya bir intihal olasılığı değildir.
- Eşik altındaki çiftler kaydedilmez. Sonradan UI skor filtresini azaltmak bu
  atılmış çiftleri geri getirmez; yeniden analiz için ürün akışı ayrıca gerekir.

## Rapor ve arayüz

Kodda genel oran için hesaplama yardımcısı vardır; mevcut analiz API yanıtı ve
web/PDF raporu belge geneli bir oran alanı sunmaz. Bu yardımcının tanımladığı oran,
normalize belge üzerindeki birleşmiş eşleşme aralıklarının
benzersiz karakter sayısı / belge uzunluğudur; skorların ortalaması veya intihal
olasılığı değildir. Kaynak ve skor filtreleri görüntülenen kanıtı değiştirir;
filtrelenmiş görünümü bütün kaynakların kesin özeti olarak yorumlamayın.

PDF çıktısı tarayıcıdan alınır; bağımsız sunucu PDF endpointi, imzalı rapor veya
çıktının sonradan değişmediğine ilişkin doğrulama yoktur. Çıktı orijinal PDF/DOCX
sayfa düzenini kopyalamaz. Kaynak metadata'sı okuma anındaki değerlerdir; tarihsel
lisans/başlık snapshot'ı ayrıca tutulmaz. Eski eşleşme bileşenleri null olabilir.

Belge silme düğmesi, hesap silme/export, parola sıfırlama/e-posta doğrulama,
admin kaynak arayüzü ve kullanıcıların istediği ayarla serbest yeniden analiz
akışları tamamlanmadı. Mevcut API'lerin kapsamı [API referansındadır](api-reference.md).

## Performans ve dayanıklılık

Uygun kaynak chunk'ları belleğe alınır ve kullanıcı chunk'larıyla karşılaştırılır;
büyük corpus için aday bulma indeksi yoktur. Çok uzun tek cümle, fazla sayfa/chunk
ve eşzamanlı yük için kapasite sınırı ölçülmedi. Worker varsayılan concurrency 2,
soft/hard timeout 240/300 saniye; dispatcher 15 saniyede bir çalışır. Kuyruk
beklemesi bu task süresinin dışında ek gecikme oluşturabilir.

[Süre/bellek raporu](document-performance-2026-10-08.md) v1, üç kaynak/13 chunk,
ısınmış worker ve seri sentetik TXT koşularıdır: 10 KiB/100 KiB/1 MiB için üçer
tekrar. PDF/DOCX, cold-start, eşzamanlılık, production yükü veya v2 süresi olarak
genellenemez. Cgroup belleği cache içerir; toplam process RSS paylaşılan sayfaları
birden fazla sayabilir. Minimum donanım veya production SLA'sı belirlenmedi.

Kalıcı durum/retry/satır kilitleri vardır; broker, API, DB ve MinIO tek atomik
transaction değildir. Polling bağlantı hatası işin başarısızlığını kanıtlamaz.
Exactly-once veya sürekli erişilebilirlik garantisi yoktur.

## Test kanıtı ve eksik doğrulama

[v2 doğrulaması](similarity-calibration-2026-10-08.md): 284 backend test geçti,
26 ayrı entegrasyon ortamı gerektiren test atlandı; bir gerçek Playwright
kayıt/giriş/TXT yükleme/analiz/PDF/API silme akışı geçti. Skip başarı sayılmaz.
[Gerçek altyapı güvenlik runner'ı](security-tests.md) ayrı çalıştırılır.

Bu kanıt, bütün dosya türlerinin canlı tarayıcı akışında, bütün tarayıcıların,
geniş gerçek belge havuzunun veya saldırgan yükün doğrulandığı anlamına gelmez.
Health endpointi canlılığı gösterir; migration, corpus, worker veya tam iş akışının
hazır olduğunu tek başına kanıtlamaz. Yerel tarama uzak CI koşusu değildir.
Kapalı kabul edilmeyen güvenlik/işletim işleri [risk kaydındadır](risks.md).
