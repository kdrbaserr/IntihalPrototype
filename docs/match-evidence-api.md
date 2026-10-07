# Eşleşme aralığı, kaynak, sayfa ve skor bileşenleri

`GET /api/v1/analyses/{analysis_id}/matches?limit=20&offset=0` tamamlanmış analizin
eşleşmelerini sunar. Belge sahipliği kontrolü, 409 hazır değil yanıtı ve pagination
korunur. Yanıt mevcut alanları korur; skor bileşenleri ve aralık sözleşmesi eklenir.

## Alanlar

| Alan | Ne için? |
| --- | --- |
| `document.char_start`, `char_end`, `text` | Kullanıcı belgesinde eşleşen metin aralığı ve metni |
| `source.char_start`, `char_end`, `text` | Kaynaktaki karşılık gelen aralık ve metin |
| `document.page_number`, `source.page_number` | PDF sayfası, 1'den başlar; güvenilir sayfa yoksa null |
| `source.source_document_id`, `chunk_id` | Kaynak belge ve kaynak parçasını tanımlamak |
| `source.title`, `original_filename`, `author`, `publisher`, `source_url` | Kaynağı kullanıcıya göstermek |
| `source.license_name`, `license_url`, `attribution_text` | Kaynağın lisans ve atıf bilgileri |
| `similarity_score` | 0–1 arasında toplam skor, dört ondalık basamak |
| `score_components` | Analiz sırasında saklanmış sinyaller, ağırlıkları ve katkıları |

Kaynak depolama anahtarı veya bucket kullanıcıya verilmez.

Aralıklar normalize edilmiş tam metindeki Unicode code point konumlarıdır;
chunk içindeki yerel konum değildir. Başlangıç dahil, bitiş hariçtir.
Yanıtın `offset_unit: "unicode_code_points"` ve
`range_convention: "start_inclusive_end_exclusive"` alanları bunu belirtir.
DOCX/TXT için fiziksel sayfa sayısı tahmin edilmez; sayfa null olur.

JavaScript string indeksleri UTF-16 code unit kullanır. Emoji gibi karakterlerde
API aralığıyla doğrudan `text.slice(start, end)` yapmak yanlış olabilir.
Code point aralığı için normalize edilmiş tam metni `Array.from(text)` ile ayırıp
`slice(start, end).join("")` uygulanabilir. API'nin `text` alanı eşleşen metni
zaten doğru aralıkla sunar; orijinal dosyanın ham byte konumları kullanılmaz.

## Skor sözleşmesi

Örnek skor alanları (eşleşmenin diğer alanları gösterilmedi):

```json
{
  "similarity_score": "0.7600",
  "score_components": {
    "scope": "chunk_pair",
    "algorithm_version": "classical-hybrid-v1",
    "word_tfidf": {"score": "0.8", "weight": "0.50", "contribution": "0.400"},
    "character_tfidf": {"score": "0.6", "weight": "0.30", "contribution": "0.180"},
    "word_overlap": {"score": "0.9", "weight": "0.20", "contribution": "0.180"}
  }
}
```

Her bileşende `contribution = score × weight`; toplam katkı dört ondalığa
yuvarlandığında `similarity_score` elde edilir. Decimal alanlar JSON'da string
olarak sunulur. Skor bileşenleri kelime TF-IDF, karakter TF-IDF ve kelime
örtüşmesidir. Ağırlıklar analizin snapshot'ından gelir.

`scope: chunk_pair`, skorun gösterilen kısa eşleşme aralığının değil iki tam
chunk'ın karşılaştırmasına ait olduğunu açıklar. Bir chunk çiftinde birden fazla
ardışık kelime eşleşmesi varsa her aralık aynı chunk skorunu taşır.
Bu değer intihal olasılığı veya belgenin genel intihal yüzdesi değildir.

Bileşenler GET sırasında hesaplanmaz. Analiz, skor ve bileşenleri aynı transaction
ile kalıcı kaydeder. Sonradan ayarlar değişse bile geçmiş sonuç değişmez.

## Migration ve eski kayıtlar

`20261006_08_match_score_components` migration'ı `matches.score_components`
nullable JSON alanını ekler. API/worker yeni kodla çalışmadan önce migration
uygulanmalıdır:

```powershell
# apps/api klasöründen
.venv/Scripts/python.exe -m alembic upgrade head
```

Mevcut eşleşmelerin bileşenleri bilinmediği için `score_components: null` döner;
geçmiş analiz için bugünün ayarlarıyla sahte bileşen üretilmez. Yeni analizler
bileşenleri saklar. Downgrade alanı ve içindeki bileşenleri kaldırır.

## ⭐ Not al

⭐ **Evidence:** Toplam skorun yanında hangi metnin hangi kaynak aralığıyla
eşleştiğini sunmak, sonucun kullanıcı tarafından incelenmesini sağlar.

⭐ **Half-open interval:** `[start, end)` aralığında uzunluk `end - start`'tır;
bitiş karakteri eşleşmeye dahil değildir.

⭐ **Explainability:** Sinyal skoru benzerlik ölçümünü, ağırlık önemini,
katkı toplam skora ne kadar eklendiğini gösterir.

⭐ **Snapshot ve reproducibility:** Analiz anındaki bileşenleri saklamak,
ayar değişikliklerinin geçmiş sonuçları değiştirmesini önler.

Olay örgüsü: iki chunk karşılaştırılır → alt skorlar ve ağırlıklı toplam
hesaplanır → eşik geçilirse ardışık eşleşme aralıkları bulunur → aralıklar,
toplam skor ve bileşenler birlikte saklanır → API kaynak/sayfa bilgileriyle sunar.
