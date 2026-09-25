# Scripts

Bu klasör geliştiricilerin tekrar tekrar çalıştıracağı yardımcı komutları
barındıracaktır.

Örnek kullanım alanları:

- geliştirme ortamını hazırlamak,
- demo verisi eklemek,
- izinli corpus'u indekslemek,
- test veya ölçüm süreçlerini başlatmak,
- bakım görevlerini güvenli ve tekrarlanabilir hale getirmek.

Uygulamanın asıl iş mantığı bu klasöre konulmayacaktır.

## Tek komutla yerel kurulum

- `setup.ps1`: Windows/PowerShell kurulumu
- `setup.sh`: Linux ve macOS kurulumu

İki script de aynı işi yapar: Docker'ı kontrol eder, eksikse `.env` oluşturur,
Compose yapılandırmasını doğrular, image'ları build eder ve servisleri başlatır.
Mevcut `.env` dosyası korunur.

Windows:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup.ps1
```

Linux/macOS:

```sh
sh scripts/setup.sh
```
