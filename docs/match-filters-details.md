# Kaynak filtresi, minimum skor ve eşleşme ayrıntısı

Tamamlanmış analizde **Eşleşmeleri göster** ile açılan rapora üç özellik eklendi.

## Kaynak ve minimum skor

Kaynak seçiminde varsayılan **Tüm kaynaklar**dır. Filtre kaynak başlığına değil,
`source_document_id` değerine göre uygulanır. Aynı başlıklı kaynaklarda dosya adı
ve kısa kimlik eklenerek seçenekler ayrılır. Kaynak seçenekleri mevcut tüm
eşleşmelerden gelir; minimum skoru yükseltince liste kaybolmaz.

Minimum skor %0–100 arası, bir puanlık adımlarla seçilir. Sınır dahildir:
%80 seçildiğinde 0.80 ve üzerindeki eşleşmeler görünür. Kaynak ve minimum skor
birlikte uygulanır; iki koşulu da sağlayan eşleşmeler kalır.

Sıra: ham eşleşmeler → kaynak/minimum skor filtresi → aralık birleştirme →
en yüksek skora göre renk. Filtre, birleşmiş bölümün maksimum skoruna bakarak
uygulanmaz; aksi halde düşük skorlu bir eşleşme yüksek skorlu komşusu nedeniyle
görünümde kalabilirdi. Bir köprü eşleşme elenince birleşik bölüm ikiye ayrılabilir.

Filtreler tüm sayfalar yüklenmiş veri üzerinde tarayıcıda uygulanır; her slider
hareketinde HTTP isteği yapılmaz. API endpointi ve veritabanı kayıtları değişmez.
Görünümde kalan eşleşme/bölüm sayısı ve toplam sayı gösterilir. Sonuç boşsa
**Bu filtrelere uygun eşleşme bulunamadı** mesajı çıkar. **Filtreleri temizle**
tüm kaynakları ve %0 minimum skoru geri getirir.

Analiz oluşturulurken kullanılan skor eşiği, hangi eşleşmelerin kaydedildiğini
belirler. Rapor minimumunu azaltmak, bu eşiğin altında kalıp kaydedilmemiş
eşleşmeleri geri getirmez.

## Eşleşme ayrıntısı

Birleşik bölümde **Kaynakları incele**, ardından ilgili eşleşmede
**Eşleşme ayrıntısı** açılır. Ayrıntı her özgün eşleşmeye aittir; birleşik
bölümün maksimum skoruyla karıştırılmaz.

- Belge/kaynak aralıkları, kendi skor ve sayfa bilgileri kaynak satırında korunur.
- Belgedeki metin ve kaynaktaki metin ayrı başlıklarla sunulur.
- Kaynak dosya, yazar, yayıncı, lisans/atıf, yöntem ve eşleşen kelime sayısı gösterilir.
- Skor tablosu kelime TF-IDF, karakter TF-IDF ve kelime örtüşmesini; her bileşenin
  skorunu, ağırlığını ve ağırlıklı katkısını gösterir.
- Algoritma sürümü ve skorun iki tam chunk'ın karşılaştırmasına ait olduğu açıklanır.
- Eski eşleşmede bileşenler null ise **Skor bileşenleri kaydedilmemiş** yazılır;
  eksik bilgiler için sayı veya metadata uydurulmaz.

Kontroller label ile ilişkilidir; slider değeri ekran okuyucuya yüzde olarak
sunulur. Ayrıntı klavyeyle açılabilen native details/summary kullanır. Skor tablosu
dar ekranda kendi alanında yatay kaydırılabilir.

## ⭐ Not al

⭐ **Predicate ve AND:** Kaynak eşitliği ve skor sınırı iki filtre koşuludur;
birlikte uygulandığında ikisinin de doğru olması gerekir.

⭐ **Filter before aggregation:** Eşleşmeleri önce filtrelemek, ardından aralıkları
birleştirmek seçilmeyen kanıtın birleşik sonuca sızmasını önler.

⭐ **Stable identity:** Başlık kullanıcıya gösterilen metindir; benzersiz kimlik
değildir. Kaynak seçimi UUID üzerinden yapılır.

⭐ **Derived state:** Görünen eşleşmeler, birleşik aralıklar ve renkler ham veri
ile filtrelerden türetilir. Ham API verisi değiştirilmez; filtre temizlenince
özgün görünüm geri gelir.

⭐ **Analysis threshold / display threshold:** Analiz eşiği kayıt oluşturmayı,
minimum görünüm skoru raporda hangi kayıtların gösterileceğini kontrol eder.

Olay örgüsü: rapor yüklenir → kaynak seçilir → minimum skor belirlenir → kalan
aralıklar yeniden birleşip renklenir → eşleşme ayrıntısı açılır → özgün metinler
ve skor katkıları incelenir.

Testler iki filtrenin birleşimini, %80 sınırının dahil olmasını, elenen köprüyle
aralıkların ayrılmasını, renk güncellemesini, boş sonucu, reset'i, aynı başlıklı
kaynakları ve null/eski skor bileşenlerini doğrular.
