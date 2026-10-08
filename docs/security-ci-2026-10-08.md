# CI güvenlik kontrolleri — 8 Ekim 2026

## Durum

`security.yml` workflow'u bağımlılık, container ve secret kontrolleriyle hazırlandı.
Komutlar yerelde Docker üzerinden çalıştırıldı; actionlint 1.7.12 hatasız geçti.
**GitHub Actions üzerinde yeni workflow henüz çalıştırılmadı:** dosya commit/push
edilmedi. Bu rapor uzak CI koşusunun başarılı olduğu anlamına gelmez.

Kaynak commit: `e55673e` (eşik değerlendirmesi sonrası). Tarama verileri
8 Ekim 2026 tarihine aittir; sonraki advisory güncellemeleri sayıları değiştirebilir.

## CI davranışı

- Python: uygulama + geliştirme bağımlılıkları ayrı ortamda çözülür; tam sürümler
  export edilir. Ayrı tool ortamında pip-audit 2.10.1 bütün bilinen bulgularda
  başarısız olur. Tool bağımlılıkları uygulama listesini değiştirmez.
- Node: `npm ci` ile lock dosyası kurulur; dev bağımlılıkları dahil
  `npm audit --audit-level=high` çalışır. HIGH/CRITICAL işin başarısız olmasına yol açar.
- Container: API ve web production target'ları, MinIO Dockerfile'ı build edilir.
  PostgreSQL/Redis sürümleri ve MinIO release'i Compose dosyasından okunur.
  Trivy 0.75.0 OS ve uygulama paketlerini HIGH/CRITICAL seviyesinde tarar.
  Düzeltmesi henüz olmayan açıklar da kapıyı başarısız yapar; ignore listesi yoktur.
- Secret: Gitleaks 8.30.1 hem bütün fetch edilmiş Git geçmişini hem checkout'taki
  Git tarafından izlenen dosyaları tarar. Yerel `.env` checkout kapsamına dahil değildir;
  Git geçmişine girmiş bir `.env` geçmiş taramasında yine incelenir.
- Scanner image'ları SHA-256 digest ile sabitlenmiştir. Checkout credential'ları
  kalıcı bırakılmaz; izin `contents: read` ile sınırlıdır.
- Her iş, başarısız olsa da JSON çıktısını 14 günlük artifact olarak saklar.
  Secret çıktısı `%100` maskelidir. Container matrisi ilk hatada diğer taramaları kesmez.
- Tetikleyiciler: main push, main'e PR ve manuel `workflow_dispatch`.
  Yeni workflow'un manuel seçilebilmesi için önce default branch'te bulunması gerekir.

## Yerel bağımlılık sonuçları

| Kontrol | Sonuç | Açıklama |
|---|---|---|
| API pip-audit | FAIL (exit 1) | pytest 8.4.2 için 1 benzersiz güvenlik kaydı |
| Web npm audit | FAIL (exit 1) | 8 HIGH sınıflandırılmış paket; 0 CRITICAL paket |
| Git geçmişi | PASS (exit 0) | 66 commit; 0 bulgu |
| İzlenen checkout + yeni workflow | PASS (exit 0) | 0 bulgu |

pip-audit aynı `PYSEC-2026-1845` kaydını iki kez döndürdü; iki ayrı açık olarak
sayılmadı. [pytest advisory](https://github.com/advisories/GHSA-6w46-j5rx-g56g)
UNIX geçici dizin kullanımını kapsar; scanner düzeltme sürümü olarak 9.0.3 verir.
Bu paket development grubundadır; mevcut `<9.0` kısıtı ayrıca ele alınmalıdır.

npm'nin sekiz paket sayısı, sekiz bağımsız açık demek değildir. Geçişli bağımlılık
zincirleri üst paketin de HIGH sınıflandırılmasına neden olur. Çıktıda dokuz
benzersiz doğrudan advisory vardır; bunların bazıları LOW/MODERATE seviyesindedir.
HIGH sınıflandırılan paketler: `@next/eslint-plugin-next`, `braces`,
`eslint-config-next`, `fast-glob`, `micromatch`, `next`, `sharp`, `source-map-js`.

Next 16.3.6 scanner tarafından etkilenmiş sürüm olarak listelenir.
[Image Optimization SSRF advisory'si](https://github.com/advisories/GHSA-cjq9-62q9-8jv4)
16.3.8 sürümünü düzeltme olarak belirtir; bu spesifik açık `images.remotePatterns`
kullanımına bağlıdır. Paket sürümü bulgusu, her açığın bu uygulamada istismar
edilebildiği kanıtı değildir. Mevcut `next.config.ts` içinde `images.remotePatterns`
yoktur; advisory'ye göre bu spesifik SSRF koşulu mevcut yapılandırmada sağlanmaz.
Diğer Next bulguları bu değerlendirmeyle dışlanmış değildir.
`npm audit fix --force` uygulanmadı: çıktı bazı
ESLint bağımlılıkları için Next 14'e geri dönüş önermektedir.

## Container sonuçları

HIGH/CRITICAL sayıları **paket–advisory kayıtlarıdır**. Aynı açık birden fazla
pakette yer alabildiğinden benzersiz advisory sayısı ayrı gösterilmiştir.

| Taranan hedef | HIGH kayıt | CRITICAL kayıt | Benzersiz advisory | Sonuç |
|---|---:|---:|---:|---|
| Yeni API production image | 48 | 0 | 12 | FAIL |
| Yeni web production image | 13 | 0 | 12 | FAIL |
| CI komutuyla yeni MinIO image | 58 | 6 | 62 | FAIL |
| PostgreSQL 17.11-alpine3.23 | 21 | 1 | 22 | FAIL |
| Redis 8.10.2-alpine | 0 | 0 | 0 | PASS |
| Çalışan API development image | 48 | 0 | 12 | FAIL |
| Çalışan web development image | 15 | 0 | 14 | FAIL |
| Çalışan worker image | 48 | 0 | 12 | FAIL |
| Çalışan scheduler image | 48 | 0 | 12 | FAIL |
| Çalışan MinIO dosya sistemi | 58 | 6 | 62 | FAIL |

API production image'ında 44 Debian, 4 Python paket kaydı bulunur.
PostgreSQL'in kritik bulgusu `CVE-2025-68121`, image içindeki Go `stdlib v1.24.6`
TLS koduna aittir; PostgreSQL SQL motorunun açığı olarak yorumlanmamalıdır.

MinIO kritik kayıtları: `CVE-2026-33322`, `CVE-2026-33419`, `CVE-2026-77405`,
`CVE-2026-77408`, `CVE-2026-77411`, `CVE-2026-33186`. Paketler MinIO, AMQP client
ve gRPC'yi kapsar. OIDC/LDAP gibi özelliklere bağlı kullanım koşulları ayrıca
incelenmelidir; otomatik tarama bu özelliklerin etkinliğini veya istismarı doğrulamaz.

Çalışan MinIO eski image ID'si Docker image deposundan kaldırılmıştır. İlk image
tarama denemesi bu nedenle araç hatası verdi; temiz kabul edilmedi. `docker export`
ile **volume içeriği alınmadan** çalışan container dosya sistemi tarandı.
Ayrıca mevcut MinIO tag'i ve CI build komutuyla yeni image ayrı ayrı tarandı.

API, web ve MinIO production build'leri exit 0 ile tamamlandı. Tarama exit 1'leri
tamamlanmış taramadaki bulgulara aittir. Servisler yeniden başlatılmadı;
son kontrolde yedi servis running, sağlık kontrolü olan altısı healthy idi.

## Kontrolün gerçekten hata üretmesi

Gitleaks'e geçersiz, sentetik bir token verildi. İki kural bunu yakaladı ve
istenen exit 42 üretildi; JSON çıktısı maskelendi. Bu pozitif kontrol gerçek
secret sayısına eklenmedi. npm/pip-audit/Trivy gerçek bulgularda exit 1 üretti.
Workflow'da bulguları gizleyen `continue-on-error` veya `|| true` yoktur.

## Çıktılar ve tekrar çalıştırma

Özet makine çıktısı: [security-checks JSON](measurements/2026-10-08-security-checks.json).
Ham taramalar, build log'ları ve requirements snapshot'ı yerel
`output/security/2026-10-08/` klasöründedir; bu klasör Git'ten hariç tutulmuştur.
Ham secret raporları da maskelidir. Container export tar'ı ve sentetik token
dosyası kontrolden sonra kaldırılır.

GitHub'a aktarım sonrası Security workflow'u PR'da otomatik çalışır. Default
branch'e ulaştığında Actions → Security → Run workflow ile manuel koşu da başlatılır.
Bu sonuçlarla güvenlik işleri yeşil beklenmez; bağımlılık ve image düzeltmeleri
ayrı değişiklikler olarak doğrulanmalıdır. Bu çalışma sürümleri değiştirmedi.

Araç kaynakları: [Trivy 0.75.0](https://github.com/aquasecurity/trivy/releases/tag/v0.75.0),
[Gitleaks kullanımı](https://github.com/gitleaks/gitleaks),
[pip-audit kullanımı](https://github.com/pypa/pip-audit).
