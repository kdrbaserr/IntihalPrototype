# Playwright: yükleme, bekleme ve rapor akışı

Testler gerçek Chromium Headless Shell tarayıcısında Next.js uygulamasını açar.
Playwright, dosya input'una örnek TXT verir; kullanıcı gibi butonlara tıklar ve
arayüzün polling ile güncellenmesini bekler. Vitest/jsdom yerine gerçek tarayıcı
DOM'u, XMLHttpRequest, klavye etkileşimi ve print CSS çalışır.

## Senaryolar

1. **Başarı:** Dosya seçimi → multipart yükleme → kuyruğa alma → extracting →
   analyzing → completed → rapor. İki API sayfasındaki çakışma tek bölümde
   birleşir. Minimum skor/kaynak filtreleri uygulanır; eşleşme ayrıntısı ve skor
   tablosu açılır. Yazdırma önizlemesinde tarih, uyarı ve filtreli kapsam kontrol
   edilir; print media'da ekran kontrolleri gizlenir, PDF ve ekran görüntüsü üretilir.
2. **Timeout ve retry:** Failed/processing_timeout açıklaması görülür; manuel
   retry ile yeni analiz kimliği kullanılır, süreç tamamlanır ve rapor açılır.
3. **Rapor bağlantı hatası:** İlk rapor isteği 503 döner. Yeniden yükle ile rapor
   alınır; yeni analiz başlatılmaz.
4. **Yükleme hatası:** Depolama 503 yanıtında güvenli hata görünür; analiz butonu
   açılmaz ve analiz isteği gönderilmez.

Her testin API durumu, sayaçları ve route fixture'ı ayrı kurulur. Sabit sleep
kullanılmaz; görünür durumlar `expect(locator)` ile beklenir. Başarı testinde
tarayıcı `pageerror` kayıtlarının boş olduğu da kontrol edilir. Hata locator'ları
ilgili region ile sınırlıdır; Next.js'in route-announcer alert'iyle karışmaz.

## Kapsam sınırı

API yanıtları `page.route` ile kontrollü fixture'dan gelir. Gerçek dosya seçimi
ve tarayıcı multipart gönderimi çalışır, ancak dosya MinIO'ya yazılmaz; Redis,
PostgreSQL ve Celery worker kullanılmaz. Bu koşu **gerçek servislerle uçtan uca
backend testi değildir**. Gerçek worker işlemleri ayrı backend senaryo testleriyle
ele alınır; servislerin birlikte çalıştığı canlı E2E kapsamı ayrıca gerekir.

Bu çalışmada localhost:8000 API ve Docker engine erişilebilir değildi; bu nedenle
tarayıcı akışı kontrollü API ile doğrulandı. Fixture timeout'un gerçek worker
tarafından üretildiğini veya kuyruk teslimini kanıtlamaz.

## Çalıştırma

`apps/web` klasöründen:

```powershell
npm ci
npm run test:e2e:install
npm run test:e2e
npm run test:e2e:report
```

Chromium önbelleği proje içinde `node_modules/.cache/ms-playwright` altındadır.
`PLAYWRIGHT_BROWSERS_PATH` verilirse o yol kullanılır. Playwright kendi Next dev
sunucusunu `127.0.0.1:3100` üzerinde başlatır; aynı portta başka sunucu olmamalıdır.
API base URL yalnız bu test sunucusunda `/api/v1` route fixture'larına ayarlanır.
Üretim/local API ayarları değiştirilmez. Tarayıcı indirme için internet gerekir.

`npm test` yalnız `src/**/*.test.ts(x)` Vitest testlerini çalıştırır; E2E spec'leri
ayrı komutla çalışır. Lint ve typecheck E2E dosyalarını da kapsar.

Sonuçlar:

- HTML raporu: `apps/web/playwright-report/index.html`.
- Başarılı baskı örneği: `apps/web/test-results/.../analysis-report.pdf`.
- Baskı görünümü ekran görüntüsü: `apps/web/test-results/.../print-preview.png`.
- Hatalı testte screenshot ve Playwright trace otomatik saklanır.

Bu çıktılar `.gitignore` kapsamındadır; yeni koşu test-results içeriğini yeniler.

## ⭐ Not al

⭐ **Browser E2E:** Gerçek tarayıcıdaki kullanıcı akışını sınar. API mock'landığında
backend servisleri yerine yalnız tarayıcı davranışı uçtan uca doğrulanır.

⭐ **Route interception:** Test, HTTP isteğine kontrollü yanıt verir. Başarı ve
hata koşullarını tekrarlanabilir yapar; canlı entegrasyonun yerini tutmaz.

⭐ **Auto-waiting:** UI koşulu gerçekleşene kadar beklenir; makine hızına bağlı
keyfî süreler testin doğru çalışmasını belirlemez.

⭐ **Trace:** Hatalı testin adımlarını, DOM ve istek bilgilerini incelemek için
kullanılır. Test fixture'ında yalnız sentetik belge ve kaynaklar bulunur.

Olay örgüsü: test sunucusu başlar → Chromium açılır → route fixture kurulur →
dosya yüklenir → polling aşamaları beklenir → rapor/filtre/ayrıntı doğrulanır →
baskı/PDF örneği alınır → test sonuçları raporlanır.
