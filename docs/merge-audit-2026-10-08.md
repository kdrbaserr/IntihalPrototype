# Merge ve backend kod kontrolü — 8 Ekim 2026

İncelenen merge: `e8c73c77e825a500c1f71d3737944cd976894593`
(`main` → `feat/auth-retention-security`), ardından `2925480` ile `main`'e alınmış.
Bu inceleme `codex/live-workflow-verification` çalışma dalında yapıldı.

## Merge bulguları

Kaynak dosyaları, testler, migration'lar, dokümanlar ve scriptlerde açık conflict
işareti bulunmadı. `git show --remerge-diff e8c73c7` ile yeniden karşılaştırıldığında
gerçek conflict dosyası `apps/web/src/app/globals.css` olarak doğrulandı. Conflict
çözümünde giriş stilleri korunmuş, yazdırılabilir rapor stilleri düşmüş.
Önceki turdaki `5024d04` bu stilleri geri getirdi.

Birleştirilen rapor arayüzünde eski `userId` kullanımı kalmış ve cookie oturumuyla
rapor okunamıyordu; `9991c45` bunu giderdi. Rapor ve kimlik doğrulama migration'ları
iki ayrı kola ayrılmıştı; `1029ea1` geçmiş revision'ları değiştirmeden merge
revision'ı ekledi. Çalışan veritabanına `score_components` sütunu eklendi ve güncel
tek head `20261008_11` oldu.

## Kod ve tip kontrolü

`main.py` için Ruff, sözdizimi ve Pyright kontrollerinde hata bulunmadı. Pyright
hem yerel API sanal ortamıyla hem varsayılan Python seçimiyle 0 hata verdi.
Bu nedenle `main.py` üzerinde gereksiz bir değişiklik yapılmadı.

Backend'in tüm 61 Python dosyasında ilk Pyright taraması 41 hata buldu.
Bunlar çalışma zamanında görülmeyen tip sözleşmesi sorunlarını da içeriyordu:

- SQLAlchemy 2.1 sorgu sonuçlarının tuple/variadic tipleri yanlış belirtilmişti.
- Oturum protokolleri SQLAlchemy'nin `execute` ve `add_all` imzalarıyla uyuşmuyordu.
- Dondurulmuş metin dataclass'ları yazılabilir alan isteyen protokole veriliyordu.
- Parola hash'i, cleanup sorgusu, exception zinciri ve sayım sonucundaki `None`
  olasılıkları doğru daraltılmıyordu.
- MinIO ETag'i isteğe bağlı olduğu hâlde zorunlu `str` olarak tanımlanmıştı.
- PDF SDK'sının çok biçimli dönüşü ve JSON skor bileşenleri açıkça doğrulanmıyordu.
- ASGI scope, log factory özelliği ve HTTPException tipi hatalı tanımlanmıştı.

Tip denetimini tekrar etmek için proje kökünde `npx --yes pyright --project
pyrightconfig.json` çalıştırılabilir. Yapılandırma API'nin `.venv` ortamını ve
`apps/api/src` import kökünü kullanır.

Tam backend test taramasında ayrıca Redis URL testinin Docker ortamındaki `redis`
host değerinden etkilenerek başarısız olduğu görüldü. Bu testin sabit URL sözleşmesi
için host, port ve veritabanı numaraları açıkça tanımlandı.

Yeni değişiklikler commit veya push edilmedi.

## Son doğrulama

- Ruff: tüm backend kaynakları/testleri ve ölçüm scripti başarılı.
- Pyright 1.1.414: 61 backend dosyası, 0 hata / 0 uyarı.
- Backend testleri: 278 başarılı, 26 atlandı.
- Gerçek Docker servisleriyle tarayıcı testi: kayıt, giriş, TXT yükleme, worker
  analizi, pozitif eşleşme, PDF raporu, silme ve çıkış başarılı.
- Çalışan API, web, PostgreSQL, Redis, MinIO ve worker sağlıklı; scheduler çalışıyor.
- Ölçüm için oluşturulan dokuz belgenin MinIO dosyası ve bağlı metin/analiz/eşleşme
  kayıtları salt okunur kontrolde tamamen temizlenmiş olarak doğrulandı.
