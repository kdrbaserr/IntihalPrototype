# v0.1.0 sentetik demo verisi

Paket kişisel veri veya dışarıdan alınmış yayın içermez. Metinler mevcut
`build_sample_sources()` üreticisinden ve sentetik ilgisiz metinden oluşur;
demo içerik lisansı **CC0-1.0** olarak kaydedilir. Bu içerik lisansı uygulamanın
kod lisansını tanımlamaz. Kaynakların izin kayıtları [manifestte](manifest.json).

## Dosyalar ve beklenen davranış

| Kullanıcı belgesi | Kaynak | Beklenen sonuç |
|---|---|---|
| [Birebir TXT](documents/exact-akademik-kaynak-gosterme.txt) | [Kaynak TXT](sources/akademik-kaynak-gosterme.txt) | Eşleşme |
| [Birebir PDF](documents/exact-veri-butunlugu.pdf) | [Kaynak PDF](sources/veri-butunlugu.pdf) | Eşleşme; iki sayfa |
| [Birebir DOCX](documents/exact-tekrarlanabilir-arastirma.docx) | [Kaynak DOCX](sources/tekrarlanabilir-arastirma.docx) | Eşleşme; paragraf/tablo |
| [İlgisiz TXT](documents/unrelated.txt) | Paket içindeki üç kaynak | Eşleşme yok |

Kaynak havuzu sürümü **v1**, aktif algoritma **classical-hybrid-v2**'dir;
bu iki sürüm farklı şeyleri tanımlar. Beklentiler yalnız bu üç kaynak ve
`0.7500 / 0.50–0.25–0.25` ayarları için geçerlidir. Başka kaynaklar veya
farklı ayarlar sonucu değiştirebilir. Pozitif örnekler intihal kararı değil,
birebir eşleşme gösterimidir. Paket genel doğruluk değerlendirme seti değildir.

## Demo akışı

1. Proje kökünde [kurulumu](../../docs/local-development.md) tamamla.
   Kurulum üç kaynağı otomatik seed eder. Tekrar gerekirse:

   ```powershell
   docker compose exec -T api python -m intihal_api.corpus.sample_seed
   ```

   Bu komut yalnız local/test içindir. Mevcut kaynakları çoğaltmaz ve daha önce
   devre dışı bırakılanları tekrar etkinleştirmez. Beklenen sonuç için üç
   kaynağın da hazır, onaylı ve etkin olması gerekir. `sources/` dosyalarını
   ayrıca admin API ile eklemek aynı örneklerin tekrarını oluşturabilir.

2. `http://localhost:3000` adresinde yeni hesap aç ve giriş yap.
   Paket hesap, sabit parola veya oturum tokenı içermez; admin olmak gerekmez.
3. `documents/` klasöründen bir belgeyi **7 gün** saklama ile yükle.
   Analizi başlat, terminal durumunu bekle ve kaynak/kanıt ayrıntılarını incele.
4. Üç birebir örnekte eşleşme bekle. PDF'te sayfa kanıtını, DOCX'te metin/table
   içeriğini kontrol et; DOCX için özgün sayfa numarası bekleme.
5. Yazdırılabilir görünümü aç ve tarayıcıdan PDF kaydet. Ardından ilgisiz TXT'yi
   ayrı yükleyip tamamlanmış analizde boş eşleşme listesini kontrol et.
6. Oluşturduğun belgeleri [oturumlu API örneği](../../docs/api-reference.md)
   üzerinden sil. Analiz aktifken silme 409 dönebilir; tamamlandıktan sonra dene.
   Belge içerikleri temizlenir; hesap, belge metadatası ve audit kayıtları kalır.
   Tarayıcıda kaydettiğin PDF'i ayrıca sen silmelisin.

Bu rehber manuel demo akışıdır; bu paketin dört belgesi için yeni bir canlı
API/worker/tarayıcı koşusu yapılmış olduğu iddiasını taşımaz.

## Yeniden üretme ve doğrulama

API sanal ortamı/bağımlılıkları hazırken proje kökünde:

```powershell
& apps/api/.venv/Scripts/python.exe scripts/export-demo-data.py
```

Script yedi içerik dosyasını ve manifest/doğrulama JSON'larını yeniden yazar;
veritabanına, MinIO'ya veya hesaplara dokunmaz. Farklı çıktı klasörü için
`--output output/demo` kullan. PDF/DOCX container metadatası nedeniyle tekrar
üretimde binary checksum değişebilir; manifest her koşuda güncellenir.

Script gerçek yükleme doğrulaması, metin çıkarma ve chunk skorlamasını çalıştırır;
beklenen karar çıkmazsa hata verir. [Kaydedilen doğrulamada](verification.json)
yedi dosya okunabildi; birebir örneklerin en yüksek chunk skoru **1.0**,
ilgisiz örneğin skoru yaklaşık **0.009813**. Bunlar genel belge benzerlik yüzdesi
veya canlı uçtan uca test sonucu değildir.

Güvenlik ve saklama sınırları: [riskler](../../docs/risks.md),
[veri politikası](../../docs/data-policy.md), [sürüm notu](../../docs/releases/v0.1.0.md).
