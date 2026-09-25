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

Bu ilk iskelet, uygulama bileşenlerini birbirinden ayırırken bütün projeyi
tek Git deposunda yönetebilmek için oluşturuldu.

## Hızlı başlangıç

Bilgisayarında Git ve çalışan bir Docker Desktop kurulumu olması yeterlidir.
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
- MinIO yönetim paneli: <http://localhost:9001>

Ortam değişkenleri, günlük Docker komutları ve sorun giderme notları için
[`docs/local-development.md`](docs/local-development.md) dosyasına bak.
