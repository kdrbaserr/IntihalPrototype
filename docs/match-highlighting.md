# Çakışan aralıklar ve skor renkleri

Tamamlanmış analizin durum kartında **Eşleşmeleri göster** butonu vardır.
Rapor `GET /analyses/{id}/matches` endpointinin bütün sayfalarını okuyup belge
aralıklarını birleştirir. Tam belgenin eşleşmeyen kısımları bu görünümde yoktur;
rapor eşleşen bölümleri gösterir.

Aralıklar başlangıca, eşitse bitişe göre sıralanır. Son grubun bitişinden önce
başlayan aralık aynı gruba eklenir. Grubun bitişi iki bitişin büyüğüdür.
Örneğin `[10, 30)` ve `[20, 40)` → `[10, 40)`. Zincirleme çakışma ve tamamen
içeride kalan aralıklar da tek bölüm olur. `[10, 20)` ile `[20, 30)` çakışmaz;
iki ayrı bölüm kalır.

Metin API'nin Unicode code point aralıklarıyla birleştirilir. Çakışan metin bir
kez gösterilir; emoji nedeniyle UTF-16 indeksi kayması oluşmaz. İki eşleşmenin
ortak aralıkta farklı metin taşıması durumunda rapor hata gösterir; metin
uydurulmaz. Başka bir API sayfasındaki çakışmayı kaçırmamak için bütün sayfalar
tamamlanmadan rapor gösterilmez. Ağ hatasında kullanıcı raporu tekrar yükleyebilir.

| Skor | Seviye | Renk |
| --- | --- | --- |
| `0 ≤ skor < 0.50` | Düşük | Sarı |
| `0.50 ≤ skor < 0.80` | Orta | Turuncu |
| `0.80 ≤ skor ≤ 1` | Yüksek | Kırmızı |

Birleşik bölümün rengi en yüksek eşleşme skoruna göre seçilir. Bu kural görünüm
kuralıdır; API'deki skorlar ve eşleşmeler değişmez. Birleşik bölümdeki bazı
karakterler yalnız daha düşük skorlu bir eşleşmeye ait olabilir; rengin tüm
bölüm için maksimum skor olduğu ekranda açıklanır. Bu değer belge geneli
intihal yüzdesi veya her karakterin ayrı skoru değildir.

**Kaynakları incele** bölümünde her eşleşmenin kaynak başlığı, kendi skoru,
belge/kaynak aralıkları, kaynak sayfası ve kaynak metni korunur. Kaynak URL'si
yalnız http/https ise bağlantı olur. Sayfa bilinmiyorsa “Sayfa bilgisi yok”
yazılır. Renk yanında seviye metni ve skor gösterilir; kullanıcı yalnız renge
bağımlı değildir. React metni escape eder; ham HTML yerleştirilmez.

## ⭐ Not al

⭐ **Interval union:** Çakışan konumları tek aralıkta toplar. Önce sıralama,
sonra birikmiş bitişi takip ederek tarama yapılır.

⭐ **Presentation / evidence ayrımı:** Görünümde aralıklar birleşir; kaynak
kanıtları ve bireysel skorlar silinmez. Veritabanındaki eşleşmeler değiştirilmez.

⭐ **Pagination boundary:** Bir sayfanın sonunda kalan aralık sonraki sayfayla
çakışabilir. Eksik sayfa yüklenmişken tam rapor sunmak yanlış sonuç verebilir.

⭐ **Unicode offsets:** API code point kullanır, JavaScript string indeksleri
UTF-16 kullanır. `Array.from(text)` bu görünümde doğru sınırlarla işlem yapar.

Olay örgüsü: analiz tamamlanır → kullanıcı raporu açar → tüm eşleşmeler okunur →
aralıklar sıralanıp birleşir → en yüksek skor renk seviyesini belirler → kullanıcı
kaynakları açıp özgün aralık ve skorları inceler.

Testler zincirleme çakışma, kapsanan/aynı aralık, bitişik aralık, emoji, renk
sınırları, sayfalar arasında çakışma, kaynakların korunması, boş sonuç, güvenli
linkler ve hata sonrası yeniden yüklemeyi kapsar. Birleştirme taraması doğrulanır;
gerçek tarayıcıdaki görünüm ayrıca gözle kontrol edilebilir.
