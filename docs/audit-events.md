# İşlem geçmişi (audit)

`audit_events` yalnızca şu alanları tutar: olay UUID'si, UTC zamanı, aktör türü,
aktör UUID'si, sabit işlem adı, hedef türü/UUID'si ve sabit sonuç adı.
İçerik, chunk, token sayısı, dosya adı, checksum, storage key, parola/hash,
session/cookie/token, HTTP gövdesi/header ve serbest metadata alanı içermez.

| İşlem | Kayıt anı |
| --- | --- |
| `document.upload` | Belge kaydıyla aynı transaction'da başarılı yükleme |
| `document.delete` | Silme niyeti kalıcılaşınca `started`, fiziksel temizlik tamamlanınca `succeeded` |
| `admin.source.create` | Kaynak kaydı oluşunca `started`, indeksleme bitince `succeeded` veya `failed` |
| `admin.source.list` | Yetkili listeleme |
| `admin.source.disable` | Pasifleştirmeyle aynı transaction'da |
| `admin.source.reindex` | İşleme başlangıcı ve başarı/başarısızlık durumuyla birlikte |
| `admin.user.provision` | CLI'nin (yerel demo admin seed dahil) parola/rol değişikliği ve session iptaliyle aynı transaction'da |

API aktörü doğrulanmış session'ın kullanıcı UUID'sidir. Otomatik temizlik aktörü
`system`, güvenilir CLI aktörü `operator` olarak kaydedilir; bunların kullanıcı
UUID'si yoktur. CLI uygulama kullanıcı kimliğiyle giriş yapmadığı için belirli
bir insan kullanıcıyı doğruladığını iddia etmez.

`record_audit` yalnızca enum ve UUID kabul eder; HTTP verisi veya hata mesajı
aktarılmaz. Veritabanındaki CHECK constraint'leri sabit değerleri ayrıca denetler.
İşlem ve audit yazımı aynı transaction'ı kullanır: audit yazımı başarısızsa ilgili
değişiklik commit edilmez. Upload servisinin MinIO telafi temizliği korunur.

Silme tekrarlarında tamamlanmış belge için yeni olay oluşturulmaz. Kullanıcının
başlattığı yarım temizliği sistem tamamladıysa başlangıç aktörü kullanıcı,
tamamlanma aktörü sistemdir. Kaynak veya kullanıcı silinmesinin geçmişi
silmemesi için audit UUID alanları foreign key/cascade kullanmaz.

Uygulama audit kayıtlarını yalnızca ekler. Düzenleme/silme/listeleme API'si veya
arayüzü eklenmedi. Veritabanına doğrudan yazabilen operatörlere karşı bu tablo
tek başına kurcalanamaz kayıt garantisi sağlamaz.
