# Yazdırılabilir analiz görünümü

Tamamlanmış analizde **Eşleşmeleri göster**, ardından **Yazdırılabilir görünüm**
açılır. Önizlemede **Yazdır / PDF olarak kaydet** tarayıcının yazdırma penceresini
açar. Kullanıcı yazıcı veya PDF hedefini bu pencereden seçer; uygulama doğrudan
yazıcıya iş göndermez ve sunucuda PDF üretmez.

## İçerik ve veri kaynağı

- Belge adı `GET /documents/{id}` yanıtından gelir.
- Analiz kimliği, algoritma sürümü, başlangıç/bitiş tarihi ve analiz eşiği
  `GET /analyses/{id}` yanıtından gelir. API çağrıları aynı kullanıcı kimliğiyle
  yapılır; tamamlanmış analiz kimliği doğrulanır.
- Yöntem mevcut hibrit iş akışıdır: kelime TF-IDF, karakter TF-IDF ve kelime
  örtüşmesi. Eşleşme bazındaki saklanmış bileşenler ayrıntı tablosunda yer alır.
- Analiz tarihi tamamlanma zamanıdır; Türkiye saatiyle gösterilir. Tarayıcının
  o anki saati analiz tarihi yerine kullanılmaz. Tarih yoksa “Tarih bilgisi yok” yazar.
- Seçili kaynak filtresi, minimum görünüm skoru, toplam/görünen eşleşme sayısı
  ve birleşik bölüm sayısı çıktı üzerinde belirtilir.
- Eşleşen metinler, aralıklar, sayfalar ve özgün eşleşme ayrıntıları açık olarak
  basılır. Ekrandaki kapalı details durumuna bağlı değildir.
- Kaynaklar UUID ile tekilleştirilir; başlık, yazar, yayıncı, dosya adı, lisans,
  atıf ve uygun http/https URL'si gösterilir. Yalnız seçili kapsamın kaynakları listelenir.

Önizleme hazırlanırken metadata alınamazsa çıktı açılmaz; güvenli hata ve yeniden
deneme imkânı gösterilir. Eşleşme bulunmayan veya filtreyle boş kalan rapor da
metadatası ve açıklamasıyla yazdırılabilir.

## Uyarı ve kapsam

Çıktı, benzerlik bulgularının tek başına intihal kararı olmadığını, karşılaştırmanın
izinli kaynak havuzuyla sınırlı olduğunu ve eşleşme yokluğunun özgünlüğü
kanıtlamadığını belirtir. Akademik kararın kullanıcıya/yetkili inceleyiciye ait
olduğu yazılır.

Çıktı mevcut ekran filtrelerini izler; tüm eşleşmeleri basmak için önce filtreler
temizlenir. Skorun belge geneli intihal yüzdesi olmadığı, birleşik bölümde en
yüksek eşleşme skorunun kullanıldığı ve aralıkların normalize edilmiş metin
konumları olduğu da açıklanır.

## Baskı düzeni

Önizleme React portal ile body altında ayrı alana yerleştirilir. `@media print`
bu alan dışındaki siteyi, araç çubuğunu, filtreleri ve yükleme kontrollerini gizler.
A4 boyut ve 16 mm kenar boşlukları tanımlıdır. Başlıkların sonraki içerikten
kopması sınırlandırılır, tablo başlıkları sonraki sayfada tekrarlanabilir.
Ekran için kaydırılan tablo baskıda görünür hale gelir. Renkli çıktı için
`print-color-adjust: exact` istenir; renk basılmasa bile seviye adı ve sayısal skor
korunur. Tarayıcı/yazıcı ayarları nihai renk ve kenar boşluklarını değiştirebilir.

Önizleme Escape veya kapat butonuyla kapanır. Klavye odağı önizleme içinde
tutulur ve kapatınca önceki kontrole döner.

## ⭐ Not al

⭐ **Print stylesheet:** `@media print` ekran kontrollerini kaldırıp içerik için
ayrı sayfa düzeni tanımlar. Ekran görünümünün birebir ekran görüntüsü alınmaz.

⭐ **Authoritative metadata:** Rapor tarihi ve yöntem sürümü kalıcı analiz
kaydından okunur; eksik tarih yerine bugünün tarihi uydurulmaz.

⭐ **Scope disclosure:** Filtreli çıktı, filtrelerini açıkça yazmalıdır. Aksi
halde okuyucu kısmi raporu bütün analiz sonucu sanabilir.

⭐ **Presentation reuse:** Eşleşme ayrıntısının aynı veri bileşeni baskıda açık
div olarak gösterilir; ikinci bir skor hesaplama akışı oluşturulmaz.

Olay örgüsü: rapor açılır → filtreler seçilir → analiz/belge metadata'sı alınır
→ yazdırılabilir önizleme açılır → kullanıcı tarayıcının yazdırma penceresini açar
→ yazıcı veya PDF olarak kaydet hedefini seçer.

Testler metadata sorgularını, filtreli kapsamı, Türkiye saatini, kaynak
tekilleştirmesini, uyarıyı, açık ayrıntıları, boş sonuçları ve yazdırma düğmesinin
`window.print()` çağrısını doğrular. DOM testleri fiziksel yazıcı veya tarayıcı PDF
çıktısının sayfa yerleşimini doğrulamaz.
