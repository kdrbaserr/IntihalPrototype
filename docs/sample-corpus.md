# Sentetik örnek kaynak havuzu

Yerel geliştirme ve test ortamı üç küçük, tamamen sentetik kaynakla hazırlanır. Metinler
haricî bir eserden alınmamış, bu projenin dosya işleme davranışını sınamak için özgün
olarak yazılmıştır. Örneklerin lisans kaydı `CC0-1.0`, kanıt referansı sürümü ise
`SYNTHETIC-CORPUS-v1` değerini kullanır.

| Kaynak | Format | Özellikle sınadığı davranış |
| --- | --- | --- |
| Akademik Yazımda Kaynak Gösterme | TXT | Türkçe Unicode, paragraf ve cümle parçalama |
| Veri Bütünlüğü ve Denetim İzleri | PDF | İki sayfanın ayrı sayfa numaralarıyla indekslenmesi |
| Araştırmada Tekrarlanabilirlik | DOCX | Başlık, paragraf ve tablo hücrelerinin belge sırasıyla çıkarılması |

Seed komutu dosyaları bellekte üretir, gerçek yükleme doğrulamasından geçirir, MinIO'ya
yazar ve ortak normalizasyon/chunk hattıyla indeksler. Kayıtlar sentetik lisansları
bilindiği için `license_status=approved` ve başarılı indeksleme sonrasında `status=ready`
olur.

Her örneğin sabit bir `license_evidence_reference` değeri vardır. Komut tekrar
çalıştırıldığında bu referanslar aranır; mevcut kayıtlar değiştirilmez veya yeniden
etkinleştirilmez ve yalnızca eksik örnekler eklenir.

Komut güvenlik amacıyla yalnızca `local` ve `test` ortamlarında çalışır:

```powershell
docker compose --env-file .env exec --no-TTY api `
  python -m intihal_api.corpus.sample_seed
```

Başarılı çıktı oluşturulan ve atlanan kayıt sayılarını gösterir:

```text
Synthetic corpus ready: created=3, skipped=0
```

İkinci çalıştırmada beklenen sonuç:

```text
Synthetic corpus ready: created=0, skipped=3
```
