# API

Bu klasör projenin FastAPI tabanlı backend uygulamasını barındıracaktır.

API'nin sorumlulukları:

- kullanıcı ve yetki kontrollerini yürütmek,
- belge yükleme ve analiz isteklerini kabul etmek,
- PostgreSQL ve MinIO ile iletişim kurmak,
- Celery görevlerini başlatmak,
- analiz durumu ve benzerlik sonuçlarını web uygulamasına sunmak.

## Yerel çalıştırma

API klasöründe sanal ortamı oluşturup geliştirme bağımlılıklarını yükleyin:

```powershell
cd apps/api
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

Uygulamayı başlatın:

```powershell
uvicorn intihal_api.main:app --app-dir src --reload
```

Kullanılabilir adresler:

- `GET http://127.0.0.1:8000/health`
- `GET http://127.0.0.1:8000/api/v1/health`
- `http://127.0.0.1:8000/docs` (OpenAPI arayüzü)

Testleri çalıştırın:

```powershell
pytest
```

## Docker ile çalıştırma

Proje kökünden bütün servislerle birlikte çalıştırın:

```powershell
docker compose up -d --build
```

API kaynak kodu geliştirme container'ına bind volume olarak bağlanır. Uvicorn
değişiklikleri algılar ve uygulamayı otomatik olarak yeniden yükler.

## Ayarlar

Uygulama ayarları `INTIHAL_` önekli ortam değişkenlerinden okunur. Yerel
geliştirmede `.env.example` dosyasını `.env` adıyla kopyalayıp değerleri
değiştirebilirsiniz. `.env` Git tarafından takip edilmez.

## Veritabanı oturumu ve ortak model alanları

API, SQLAlchemy'nin async motorunu ve `asyncpg` PostgreSQL sürücüsünü kullanır.
Bu tercih `intihal_api.db.session` içinde merkezî olarak tanımlıdır; yeni kodda
ayrı bir senkron motor veya oturum oluşturulmamalıdır. `get_db_session`, her API
isteğine ayrı bir oturum verir ve hata halinde yarım kalan işlemi geri alır.

Kalıcı modeller `BaseModel` sınıfını miras alır. Bu soyut temel sınıf,
aşağıdaki iki mixin'i bütün modellere birlikte kazandırır:

- `UUIDPrimaryKeyMixin`: Uygulama tarafında üretilen benzersiz `id` alanını ekler.
- `TimestampMixin`: Saat dilimi bilgili `created_at` ve `updated_at` alanlarını ekler.

`Mixin`, birden fazla modele aynı alanları kopyala-yapıştır yapmadan kazandıran
küçük bir ortak sınıftır. Bağlantı adresi `INTIHAL_DATABASE_URL` ortam
değişkeninden okunur. Yerelde adres `localhost`, Docker Compose içinde ise PostgreSQL
servis adı olan `postgres` kullanılır.

## Kullanıcı ve belge tabloları

`users`, kullanıcı kimliğini (`email`, `display_name`) ve hesabın `active` veya
`disabled` durumunu tutar. `documents.owner_id`, belgeyi zorunlu olarak bir kullanıcıya
bağlar. Sahibi olan belge varken kullanıcının fiziksel olarak silinmesi `RESTRICT` ile
engellenir; hesap kapatma işlemi için kullanıcı durumu `disabled` yapılmalıdır.

Dosya içeriği PostgreSQL'e yazılmaz. `documents` tablosundaki `storage_bucket` ve
`storage_key` MinIO nesnesini gösterir; `storage_etag`, `sha256`, `content_type` ve
`size_bytes` bütünlük ve dosya metadatasını taşır. Aynı bucket/key çifti yalnızca bir
belgede kullanılabilir. Belge yaşam döngüsü `uploaded`, `processing`, `ready`, `failed`
ve `deleted` durumlarıyla izlenir. `deleted`, kaydın denetim izi için tutulduğu mantıksal
silme durumudur; MinIO nesnesini temizleyen iş ayrıca uygulanmalıdır.

## İzinli kaynak havuzu

Kullanıcının yüklediği belge ile karşılaştırma yaptığımız kaynaklar aynı şey değildir.
Kullanıcı yüklemeleri `documents` tablosunda, karşılaştırma için önceden sisteme alınan
eserler `source_documents` tablosunda tutulur. Böylece bir raporda bulunan eşleşmenin
hangi izinli kaynaktan geldiğini açıkça gösterebiliriz.

Kaynak dosyanın aslı yine MinIO'dadır. `source_documents`, dosyanın MinIO adresiyle
birlikte başlık, yazar, yayınevi ve geldiği internet adresini saklar. Lisans alanlarının
günlük dilde anlamı şöyledir:

| Alan | Neden tutuluyor? |
| --- | --- |
| `license_name` | Kullanım izninin adı; örneğin “CC BY 4.0” veya kurum sözleşmesi. |
| `rights_holder` | Eser üzerindeki hakların kimde olduğunu gösterir. |
| `license_url` | Varsa lisans koşullarının okunabildiği adres. |
| `attribution_text` | Kaynağı gösterirken yazılması gereken hazır atıf metni. |
| `license_evidence_reference` | Sözleşme numarası, izin e-postası kaydı veya kanıt dosyası gibi iç referans. |
| `license_valid_from` / `license_valid_until` | İznin geçerli olduğu tarih aralığı. |
| `license_verified_at` | Bir görevlinin izni en son ne zaman kontrol ettiği. |
| `license_status` | Kontrol sonucu: `pending`, `approved`, `rejected` veya `expired`. |

Kaynağın teknik hazırlanma durumu ayrıca tutulur: `pending`, `processing`, `ready`,
`failed` veya `disabled`. Bu iki ayrı durum önemlidir. Bir dosyanın metni işlenmiş olsa
bile lisansı onaylanmamış olabilir. Karşılaştırma işi yalnızca teknik durumu `ready`,
lisans durumu `approved` olan ve lisans süresi dolmamış kaynakları kullanmalıdır.

Uzun bir kitabı veya makaleyi her aramada baştan sona karşılaştırmak yerine metni küçük
parçalara ayırıyoruz. Her parça `source_chunks` tablosunda tutulur. `chunk_index`
parçanın sırasını; `page_number` sayfasını; `char_start` ve `char_end` metin içindeki
yerini gösterir. `content_sha256`, parça sonradan değişti mi kontrol etmeye yarar.
Kaynak belge fiziksel olarak silinirse ona ait parçalar da otomatik silinir; tek başına
ve hangi kaynağa ait olduğu bilinmeyen parçalar bırakılmaz.

Buradaki lisans alanları bir iznin kaydını ve kontrol sürecini destekler; kendi başına
hukuki izin oluşturmaz. Gerçek sözleşme veya izin belgesi güvenli bir yerde ayrıca
saklanmalı, `license_evidence_reference` ile o kayda işaret edilmelidir.

## Analiz, belge parçaları ve eşleşmeler

Yüklenen bir belgeyi kaynak havuzuyla karşılaştırırken üç ayrı tür kayıt oluşur:

1. `document_chunks`, kullanıcının yüklediği uzun belgeyi küçük ve aranabilir metin
   parçalarına böler. Sayfa, sıra ve karakter konumları tutulduğu için bulunan bir
   cümlenin belgenin neresinde olduğu daha sonra tekrar gösterilebilir.
2. `analyses`, yapılan her karşılaştırma çalışmasının fişidir. Hangi belgenin hangi
   algoritma sürümü ve hangi puan sınırıyla incelendiğini, işlemin ne zaman başlayıp
   bittiğini ve hata varsa nedenini saklar.
3. `matches`, kullanıcı belgesindeki bir parça ile izinli kaynak havuzundaki bir parça
   arasında bulunan eşleşmedir. Puanla birlikte her iki taraftaki tam metin konumunu da
   saklar; rapor bu bilgilerle eşleşen bölümleri işaretleyebilir.

Analiz durumları sırayla `queued` (kuyrukta), `processing` (çalışıyor), `completed`
(tamamlandı), `failed` (hata oluştu) ve `cancelled` (iptal edildi) olabilir. Analiz
başladığında `started_at`, bittiğinde `completed_at` doldurulmalıdır. Hata durumunda
teknik kayıtların içine bakmadan anlaşılabilecek kısa bir açıklama `failure_reason`
alanına yazılmalıdır.

`similarity_threshold`, hangi puanın rapora alınmaya değer sayıldığını 0 ile 1 arasında
saklar. Varsayılan değer `0.8000`, yani yüzde 80'dir. `algorithm_version` da mutlaka
kaydedilir; böylece yöntem ileride değişse bile eski sonucun hangi sürümle üretildiği
bilinir.

Bir eşleşmenin `method` alanı nasıl bulunduğunu belirtir: `exact` birebir metin,
`lexical` kelime benzerliği, `semantic` anlam benzerliği, `hybrid` ise birden fazla
yöntemin birlikte kullanılmasıdır. `similarity_score` 0 ile 1 arasındadır. Bu puan
tek başına “intihal var” kararı değildir; raporda incelenmesi gereken benzerliği gösterir.

Bir analiz silinirse ona ait eşleşmeler de silinir. Buna karşılık sonuçta kullanılmış
belge ve kaynak parçaları doğrudan silinemez; önce bağlı analiz kaydı kaldırılmalıdır.
Bu tercih, rapor dururken raporun dayandığı kanıtın kaybolmasını önler. Normal kullanımda
belgeleri fiziksel olarak silmek yerine mevcut `deleted` veya `disabled` durumları
kullanılmalıdır.

## Migration yönetimi

`20260927_03_initial_schema.py`, B02 kapsamındaki bütün enum, tablo, foreign key,
constraint ve indeksleri kuran başlangıç migration'ıdır. Tablolar foreign key
bağımlılık sırasıyla oluşturulur; `downgrade()` ise aynı nesneleri ters sırada kaldırır.
Bu başlangıç revision'ı yayımlandıktan sonra değiştirilmemeli, her şema değişikliği yeni
bir Alembic revision'ı olarak eklenmelidir.

Kök dizindeki tek komutluk kurulum migration'ı otomatik uygular. Şemayı Docker dışında
çalışan yerel veritabanına elle uygulamak için API klasöründe çalıştırın:

```powershell
alembic upgrade head
```

Mevcut revision'ı görmek için:

```powershell
alembic current
```

Başlangıç migration'ını tamamen geri almak için:

```powershell
alembic downgrade base
```

> **Dikkat:** `downgrade base`, bu ilk migration'ın oluşturduğu bütün uygulama
> tablolarını ve içlerindeki verileri siler. Yalnızca geliştirme/test veritabanında veya
> doğrulanmış bir yedek alındıktan sonra kullanılmalıdır.

Geri alma sonrasında şemayı tekrar kurmak için yeniden `alembic upgrade head`
çalıştırılabilir.
