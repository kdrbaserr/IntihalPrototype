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
Migration'lardan sonra üç belgeli sentetik kaynak havuzunu hazırlar. Kullanıcı
hesabı web ekranından açılır; admin için `intihal_api.db.manage_user` komutu kullanılır. Mevcut `.env` dosyası ve daha önce seed edilmiş kaynaklar korunur.

Windows:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup.ps1
```

Linux/macOS:

```sh
sh scripts/setup.sh
```

## Belge süre ve bellek ölçümü

Compose servisleri çalışırken proje kökünde:

```powershell
python scripts/measure-document-performance.py --output docs/measurements/YENI-KOSU.json
```

Script küçük (10 KiB), orta (100 KiB) ve büyük (1 MiB) sentetik TXT belgelerini
üçer kez gerçek API/worker üzerinden analiz eder. Süreleri ve 100 ms aralıklarla
API/worker belleğini JSON/CSV'ye yazar, kendi test belgelerini siler ve çıkış yapar.
Hesap ve denetim metadatası kalır. `--repeats 1` kısa koşu içindir. Bellekte
başlangıç, gözlenen tepe ve örnek sayısı saklanır; cgroup değeri cache'i içerir.
Kod değişikliği/restart yapmadan çalıştırılmalıdır. Mevcut örnek kaynak havuzuyla
elde edilen sonuçlar [ölçüm raporunda](../docs/document-performance-2026-10-08.md).
