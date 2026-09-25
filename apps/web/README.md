# Web

Bu klasör projenin Next.js ve TypeScript tabanlı kullanıcı arayüzünü
barındıracaktır.

Web uygulamasının sorumlulukları:

- belge yükleme ekranını sunmak,
- analiz ilerlemesini göstermek,
- benzer bölümleri renkli ve kaynak bağlantılı biçimde göstermek,
- rapor filtreleme ve yazdırma deneyimini sağlamak.

Web uygulaması analiz yapmayacak; gerekli verileri API üzerinden alacaktır.

## Yerel çalıştırma

```powershell
cd apps/web
npm install
npm run dev
```

Ardından `http://localhost:3000` adresini açın.

## Komutlar

- `npm run dev`: geliştirme sunucusunu başlatır.
- `npm run build`: production paketini oluşturur.
- `npm run start`: production sunucusunu başlatır.
- `npm run lint`: ESLint kontrollerini çalıştırır.
- `npm run typecheck`: TypeScript tiplerini doğrular.

## App Router yapısı

- `src/app/layout.tsx`: bütün sayfaların ortak HTML iskeleti, üst menü ve alt bilgi.
- `src/app/page.tsx`: `/` adresinde gösterilen ana sayfa.
- `src/app/globals.css`: uygulamanın ortak tasarım değişkenleri ve responsive stilleri.
