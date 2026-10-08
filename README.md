# İntihal Prototype

PDF, DOCX ve TXT belgelerini izinli bir kaynak havuzuyla karşılaştırarak
açıklanabilir metin benzerlikleri üreten monorepo projesi.

> Sistem benzerlik bulgusu üretir; tek başına intihal kararı vermez.

## Monorepo yapısı

```text
apps/
  api/      FastAPI tabanlı backend ve analiz API'si
  web/      Next.js tabanlı kullanıcı arayüzü
docs/       Mimari, kurulum ve proje kararları
scripts/    Tekrarlanan geliştirme ve bakım komutları
infra/      Docker Compose ve yerel servis yapılandırmaları
```

API, Celery worker/scheduler ve web arayüzü aynı depoda sürümlenir.

## Hızlı başlangıç

Git ve çalışan Docker Desktop (Linux container modu) veya Docker Engine + Compose v2 gerekir.
PostgreSQL, Redis veya MinIO'yu ayrıca kurman gerekmez; bu servisler Docker
container'ları olarak çalışır.

Repoyu klonladıktan sonra proje kökünde Windows için tek komut çalıştır:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup.ps1
```

Linux veya macOS için:

```sh
sh scripts/setup.sh
```

Kurulum komutu, yoksa `.env.example` dosyasından yerel `.env` dosyasını
oluşturur; Compose ayarlarını doğrular, image'ları build eder ve bütün
servislerin sağlıklı duruma gelmesini bekler. Var olan `.env` dosyanı silmez
veya üzerine yazmaz.

Servis adresleri:

- Web: <http://localhost:3000>
- API sağlık kontrolü: <http://localhost:8000/health>
- OpenAPI arayüzü: <http://localhost:8000/docs>
- MinIO yönetim paneli: <http://localhost:9001>

Ortam değişkenleri, günlük Docker komutları ve sorun giderme notları için
[`docs/local-development.md`](docs/local-development.md) dosyasına bak.

## Giriş ve roller

Parola hashleme, cookie oturumu, user/admin rolleri ve admin oluşturma komutu için
[kimlik doğrulama ve mimari notlarını](docs/authentication.md) okuyun. Normal hesap web ekranından açılır;
admin sunucu komutuyla atanır. Eski hesaplara parola atanması gerekir.

## Kullanım ve kapsam

Web'de giriş yapıp en fazla **20 MiB** PDF/DOCX/TXT yükleyin; saklama süresi
**7 veya 30 gün** seçilir. Analizi başlatıp tamamlandığında kanıtları ve kaynakları
inceleyin. PDF raporu yazdırılabilir görünümden tarayıcıda üretilir. Belge silme
şu anda API üzerinden yapılır; arayüzde silme düğmesi yoktur.

Yeni profil `classical-hybrid-v2`, eşik `0.7500`, ağırlıklar `0.50 / 0.25 / 0.25`.
Dört sentetik çift üzerindeki ölçüm genel başarı oranı kanıtı değildir. Eski
analizler kendi konfigürasyon snapshot'ını kullanır.

Varsayılan Compose geliştirme içindir: HTTP, örnek parolalar, dışarı açılan
altyapı portları ve açık güvenlik bulguları vardır. Üretime hazır dağıtım değildir.

## Kullanım belgeleri

| Konu | Rehber |
|---|---|
| Kurulum, güncelleme ve Docker kontrolleri | [Yerel geliştirme](docs/local-development.md) |
| Bütün endpointler ve örnek akış | [API referansı](docs/api-reference.md) |
| Saklanan veriler, süreler ve silme kapsamı | [Veri politikası](docs/data-policy.md) |
| Açık güvenlik ve operasyon riskleri | [Risk kaydı](docs/risks.md) |
| Algoritma, belge ve ölçüm sınırları | [Bilinen sınırlar](docs/known-limitations.md) |
| Lisans ve izin kararları | [Kaynak edinme politikası](docs/source-acquisition-policy.md) |
| Ölçümler ve ayrıntılı teknik notlar | [Dokümantasyon dizini](docs/README.md) |
