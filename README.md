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
