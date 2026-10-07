# Analiz durumlarının arayüzde gösterimi

Belge yükleme tamamlandığında `DocumentWorkflow` durum kartı gösterilir.
Kart ilk GET yanıtını beklerken “Durum kontrol ediliyor…” yazar; durumu henüz
okunmamış belgeyi hazır kabul edip başlat butonu göstermez.

| API durumu | Görünüm | Kullanıcıya açıklama |
| --- | --- | --- |
| uploaded | Yüklendi | Belge hazır; analiz başlatılabilir |
| queued | Kuyrukta | İşlem sırası veya retry bekleme süresi bekleniyor |
| extracting | Metin çıkarılıyor | Metin okunup karşılaştırma için parçalara ayrılıyor |
| analyzing | Karşılaştırılıyor | İzinli kaynaklarla karşılaştırma yapılıyor |
| completed | Analiz tamamlandı | Sonuçlar kaydedildi; tüm adımlar tamamlandı |
| failed | Analiz başarısız | Güvenli hata açıklaması ve uygun sonraki işlem |

Aşama listesinde “Tamamlandı”, “Şu an” ve “Bekliyor” metinleri vardır; ayrım
yalnız renge bağlı değildir. Aktif adım `aria-current="step"` taşır. Durum
başlığı `role="status"`, hata alanları `role="alert"` ile duyurulur.

Timeout, retry tükenmesi ve genel işleme hatasında uygun analiz kimliği varsa
“Analizi yeniden dene” gösterilir. OCR veya bozuk dosya için düzeltme/yeni yükleme
açıklanır. Backend retry hakkının tükendiğini bildirirse güvenli mesaj gösterilir;
yanıttaki `trace_id` varsa destek takip kodu olarak eklenir.

Hata ilk okumada geldiyse hangi işlemde oluştuğu tahmin edilmez. İşlem sırasında
failed görülürse son gözlenen aşama yazılır; sonrasında kalan adımlar tamamlandı
işaretlenmez. Son gözlenen aşama, hatanın kesin oluştuğu aşama olarak sunulmaz.

Bağlantı kesintisinde son doğrulanmış durum korunur ve bağlantı uyarısı gösterilir.
Bu durum failed yerine geçmez. Bağlantı geri geldiğinde polling güncel durumu
okur. Aktif işler 2 saniyede, bağlantı hataları 5 saniyede kontrol edilir;
completed/failed durumunda normal polling durur.

## ⭐ Not al

⭐ **State-driven UI:** Ekranı API'nin durumu belirler. Geçen süreye göre sahte
ilerleme yüzdesi veya kuyruk sırası hesaplanmaz.

⭐ **Loading / error ayrımı:** Henüz okunmamış durum, bağlantı hatası ve işin
başarısızlığı farklıdır. Son bilinen durum yeni yanıt gelene kadar korunabilir.

⭐ **Accessibility:** Durum ve hata ekran okuyucuya bildirilir; aşamalar hem renk
hem metinle ayırt edilir. Düzen dar ekranlarda dikey kalır.

⭐ **Polling:** İstemci düzenli GET ile kalıcı durumu okur. Ekran worker sürecinin
canlı olup olmadığını veya kuyruğun gerçek sırasını ölçmez.

Olay örgüsü: belge yüklenir → durum doğrulanır → kullanıcı analizi başlatır →
kuyruk → metin çıkarma → karşılaştırma → tamamlandı. Hata olursa güvenli
açıklama ve uygun aksiyon gösterilir; bağlantı hatasında durum tekrar sorgulanır.
