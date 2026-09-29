# Kaynak lisansı ve veri toplama politikası

**Politika sürümü:** 1.0  
**Son güncelleme:** 29 Eylül 2026  
**Kapsam:** İzinli kaynak havuzuna dosya yükleyen admin işlemleri ile gelecekteki
otomatik indirme, tarama ve içe aktarma araçları.

Bu belge ürün politikasıdır; tek başına hukuki görüş değildir. Yeni bir lisans türü,
ülke, veri sağlayıcı veya kişisel veri işleme amacı eklenmeden önce hukuk ve gizlilik
incelemesi yapılmalıdır.

## Temel kabul kuralı

Bir kaynağın internette ücretsiz okunabilmesi, indirilebilmesi, “open access” olarak
etiketlenmesi veya `robots.txt` tarafından taramaya açık olması kaynak havuzuna alınması
için yeterli değildir. Her kaynakta aşağıdaki iki dayanak birlikte bulunmalıdır:

1. İçeriği saklama, normalleştirme, parçalara ayırma, karşılaştırma ve gerekli kısa
   alıntıları raporda gösterme yetkisini veren açık bir lisans veya yazılı izin.
2. Lisansın ilgili dosyaya ve hak sahibine ait olduğunu gösteren doğrulanabilir kanıt
   kaydı.

`robots.txt` otomatik istemciler için tarama tercihlerini bildirir; bir erişim yetkisi
veya telif lisansı değildir. Buna rağmen proje, daha kısıtlayıcı site kurallarını ve
`robots.txt` talimatlarını ayrıca uygular.

## Doğrudan kabul edilen lisans ve izinler

| Lisans veya dayanak | Karar | Zorunlu koşullar |
| --- | --- | --- |
| Proje tarafından üretilmiş sentetik içerik | Kabul | Üretim amacı, sürümü ve hak sahibi kaydedilir; gerçek kişisel veri içermez. |
| `CC0-1.0` | Kabul | Lisans işaretinin hak sahibi tarafından ilgili esere uygulandığı doğrulanır. Gizlilik, kişilik, marka ve patent haklarının ayrıca devam edebileceği unutulmaz. |
| Doğrulanmış kamu malı | Kabul | Kamu malı statüsünün ülke, eser ve tarih bakımından geçerli olduğuna ilişkin kaynak saklanır. Yalnızca “eski” olması yeterli sayılmaz. |
| `CC BY 4.0` | Kabul | Eser adı, üretici/hak sahibi, lisans adı ve bağlantısı, kaynak bağlantısı ile gerekiyorsa değişiklik bilgisi korunur. Atıf raporda ve ilgili ürün yüzeyinde gösterilebilir olmalıdır. |
| Kuruma verilmiş açık yazılı izin veya sözleşme | Kabul | İzin; saklama, teknik dönüşüm, indeksleme, benzerlik karşılaştırması ve raporda kısa alıntı gösterimini açıkça kapsar. Süre, bölge ve fesih koşulları kaydedilir. |

Creative Commons'a göre CC0, hak sahibinin mümkün olan ölçüde haklarından feragat ederek
ticari kullanım dâhil kopyalama ve değiştirmeye izin veren bir kamu malı aracıdır.
CC BY ise ticari kullanım ve uyarlamaya izin verir, fakat uygun atıf ister.

## Yalnızca manuel incelemeyle kabul edilebilecekler

Aşağıdaki kaynaklar otomatik olarak havuza alınmaz. Hukuk veya yetkili içerik yöneticisi
yazılı karar vermeli; karar `license_evidence_reference` ile izlenebilmelidir:

- `CC BY-SA 4.0`: Atıf şartına ek olarak uyarlamaların aynı koşullarla paylaşılması
  gerekebilir. Normalizasyon, chunk üretimi, indeks ve rapor çıktısı bakımından
  yükümlülüklerin nasıl uygulanacağı belirlenmeden kabul edilmez.
- Kuruma veya ülkeye özgü açık veri/açık yayın lisansları.
- Üniversite arşivi, yayınevi veya veri sağlayıcının özel kullanım koşulları.
- Kamu malı olduğu ileri sürülen fakat hak zinciri veya ülke kapsamı açık olmayan eserler.
- Bir istisna veya sınırlamaya dayanılarak kullanılmak istenen içerikler.
- Lisans metni ile platform kullanım şartları arasında çelişki bulunan kaynaklar.

Manuel onay verilene kadar `license_status=pending` kalır ve karşılaştırma havuzunda
kullanılmaz.

## Kabul edilmeyen kaynaklar

MVP kapsamında aşağıdaki lisanslar ve durumlar reddedilir:

- `CC BY-NC`, `CC BY-NC-SA` ve `CC BY-NC-ND`: “NonCommercial” koşulu ürünün mevcut veya
  gelecekteki kullanım modeliyle çatışabilir.
- `CC BY-ND` ve `CC BY-NC-ND`: “NoDerivatives” koşulu teknik dönüşüm ve türetilmiş
  çıktılar bakımından belirsizlik yaratır.
- “Tüm hakları saklıdır” içerik; ayrıca açık yazılı izin yoksa.
- Lisansı belirtilmeyen, lisans bağlantısı çalışmayan veya lisansın ilgili dosyaya ait
  olduğu kanıtlanamayan içerik.
- Yalnızca “ücretsiz”, “herkese açık”, “indirilebilir” veya “open access” açıklaması
  bulunan fakat yeniden kullanım izni verilmeyen içerik.
- Yetkisiz kopya, sızıntı, korsan arşiv, shadow library veya erişim anahtarı sızdırılarak
  elde edilmiş içerik.
- Yükleyenin lisans verme yetkisi olmadığı bilinen veya makul olarak şüphe edilen içerik.
- Lisans ile eser, ekler, görseller veya üçüncü taraf bölümler arasında kapsam farkı
  bulunan ve ayrıştırılamayan belgeler.

Bu ret listesi, lisansların genel olarak “kötü” olduğu anlamına gelmez. Proje, işleme
biçimi ve gelecekteki kullanım belirsizliği nedeniyle daha dar bir kabul politikası
uygular.

## Her kabul edilen kaynakta tutulacak kanıt

Kaynak havuzuna alınmadan önce en az şu bilgiler bulunmalıdır:

- kaynak başlığı ve hak sahibi;
- lisansın tam adı ve sürümü;
- lisans URL'si veya imzalı izin/sözleşme kaydının güvenli referansı;
- eserin bulunduğu kaynak URL ve erişim tarihi;
- zorunlu atıf metni;
- izin başlangıç/bitiş tarihleri ve doğrulama zamanı;
- indirilen özgün dosyanın SHA-256 checksum değeri;
- lisans sayfası değişebiliyorsa tarihli ekran görüntüsü, PDF veya denetim kaydı;
- incelemeyi yapan kişi ya da süreç ve karar sonucu.

Kanıt kaydı yoksa kaynak `approved` yapılamaz. Dosyanın checksum değeri daha sonra
değişirse yeniden indeksleme yapılmaz; yeni içerik ayrı bir inceleme ve kayıt gerektirir.

## Yasak veri toplama davranışları

Aşağıdaki davranışlar admin, geliştirici, worker, crawler ve üçüncü taraf entegrasyonları
için kesin olarak yasaktır:

### Erişim kontrollerini aşma

- Kullanıcı adı/parola, oturum çerezi veya API anahtarını yetki kapsamı dışında kullanmak.
- Paywall, CAPTCHA, MFA, bot koruması, indirme kotası veya erişim kontrolünü aşmak.
- Gizli ya da belgelenmemiş API uçlarını, imzalı URL'leri veya tahmin edilen nesne
  adreslerini yetkisiz içerik almak için kullanmak.
- IP değiştirme, proxy havuzu, kimlik veya `User-Agent` yanıltmasıyla engel ve hız
  sınırlarından kaçmak.
- Bir güvenlik açığını, yanlış yapılandırmayı veya herkese açık bırakılmış depolama
  anahtarını veri toplama amacıyla kullanmak.

### Site ve sağlayıcı kurallarını ihlal etme

- `robots.txt`, kullanım şartları, sözleşme, API politikası veya açık kaldırma talebini
  görmezden gelmek.
- `robots.txt` erişime izin veriyor diye telif veya veri işleme izni varmış gibi davranmak.
- Sağlayıcıya gereksiz yük bindirmek; hız sınırı olmadan paralel tarama yapmak.
- Onaylanan alan adı, dizin, belge türü veya tarih aralığının dışına çıkmak.
- Başlangıç URL'sinden kontrolsüz biçimde bağlantı takip ederek yeni siteler toplamak.

### Kişisel ve hassas veri toplama

- Belirli, açık ve belgelenmiş bir hukuki sebep ve amaç olmadan kişisel veri toplamak.
- İntihal/benzerlik analizi için gerekli olmayan e-posta, telefon, adres, öğrenci numarası,
  hesap kimliği, cihaz kimliği veya konum bilgisini toplamak.
- Sağlık, biyometrik/genetik veri, siyasi düşünce, din/inanç, etnik köken, sendika/dernek
  üyeliği, cinsel hayat veya ceza mahkûmiyeti gibi özel nitelikli verileri hukuk ve
  gizlilik incelemesi olmadan toplamak.
- Çocuklara ait kişisel verileri veya özel yazışmaları kaynak havuzuna almak.
- Kamuya açık kişisel verileri sınırsızca profil oluşturmak, kişileri puanlamak veya
  farklı kaynaklar arasında kimlik eşleştirmek amacıyla birleştirmek.
- Silinmiş, erişimi sınırlandırılmış veya veri sahibinin kaldırılmasını istediği içeriği
  yeniden toplamaya çalışmak.

KVKK ilkeleri gereği kişisel veri işleme hukuka ve dürüstlük kurallarına uygun, belirli
ve meşru amaçlarla bağlantılı, sınırlı, ölçülü ve gerekli saklama süresiyle kısıtlı
olmalıdır. Kaynağın açık lisanslı olması kişisel veri koruma yükümlülüklerini ortadan
kaldırmaz.

### İçerik ve kullanım sınırlarını aşma

- İzin verilen kısa kanıt alıntısı yerine eserin tamamını raporda veya kullanıcıya açık
  başka bir yüzeyde yeniden yayımlamak.
- Toplanan içeriği belirtilen benzerlik analizi amacı dışında model eğitimi, reklam,
  kişi profilleme veya veri satışı için kullanmak.
- Lisans/atıf bilgisini, kaynak URL'sini, hak sahibini ya da değişiklik bilgisini silmek.
- İzin süresi dolmuş, reddedilmiş veya pasifleştirilmiş kaynağı yeni analizlerde kullanmak.
- Kaynak dosyayı checksum kontrolü olmadan değiştirmek veya değişmiş dosyayı eski izin
  kaydına bağlamak.

## Toplama öncesi zorunlu kontrol

Yeni bir veri kaynağı için aşağıdaki soruların tamamına olumlu ve kanıtlı cevap
verilmeden otomatik toplama başlatılamaz:

1. İçeriği toplama ve bu projedeki amaçlarla işleme yetkisi açık mı?
2. Lisans veya yazılı izin ilgili dosyanın tamamını kapsıyor mu?
3. Hak sahibi ve lisans kanıtı doğrulanıp kaydedildi mi?
4. Kişisel veri varsa hukuki sebep, amaç, minimizasyon ve saklama süresi belirlendi mi?
5. Site şartları, API politikası ve `robots.txt` incelendi mi?
6. Alan adı/yol kapsamı, hız sınırı, tekrar deneme ve durdurma mekanizması tanımlandı mı?
7. Kaldırma talebi, lisans değişikliği ve incident durumunda kaynağı hızla pasifleştirme
   süreci var mı?

Bir cevap belirsizse varsayılan karar **toplamamak** ve kaydı manuel incelemeye
göndermektir.

## Dayanak ve başvuru kaynakları

- [Creative Commons lisans türleri ve koşulları](https://creativecommons.org/share-your-work/use-remix/cc-licenses/)
- [CC0 1.0 açıklaması](https://creativecommons.org/publicdomain/zero/1.0/)
- [RFC 9309 — Robots Exclusion Protocol](https://www.rfc-editor.org/rfc/rfc9309.html)
- [KVKK — Kişisel verilerin işlenmesindeki temel ilkeler](https://www.kvkk.gov.tr/SharedFolderServer/CMSFiles/a3b2290a-a61b-4faa-b6dc-5202630a0fd3.pdf)
- [KVKK — Özel nitelikli kişisel verilerin işlenmesine ilişkin rehber](https://www.kvkk.gov.tr/Icerik/8184/Ozel-Nitelikli-Kisisel-Verilerin-Islenmesine-Iliskin-Rehber)
