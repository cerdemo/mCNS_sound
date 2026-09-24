# MaleCNS tabanlı interaktif ses enstalasyonu

## Fikir

Kameranın gördüğü hareketlerin, sineğin biyolojik bağlantı haritası (connectome) üzerinde çalışan bir nöral modelde oluşturduğu aktiviteyi seslendirmek istiyoruz. Ziyaretçi sesi duyup hareketini değiştirdiğinde yeni görsel girdi oluşacak; böylece insan ile sistem arasında kapalı bir etkileşim döngüsü kurulacak.

**Akış:** Kamera → görsel girdinin nöronlara aktarılması → sürekli nöral simülasyon → aktivitenin sonifikasyonu → ziyaretçinin yeni hareketi.

Amacımız belirli jestlere hazır tepkiler öğretmek değil. Biyolojik bağlantıları temel alıp, seçtiğimiz nöral dinamiklerle çevreye verilen yanıtı dinlemek istiyoruz. İlk sürümde model eğitimi veya bağlantıların öğrenmeyle değiştirilmesi planlanmıyor. Sabit bağlantılarda da ağın iç durumu zamanla değişebilir; kapalı döngü tek başına öğrenme demek değildir.

## İndireceğimiz üç dosya

Dosyalar [MaleCNS indirme sayfasında](https://male-cns.janelia.org/download/) bulunuyor; navis reposunun parçası değiller.

| Dosya | Ne için kullanacağız? |
| --- | --- |
| `body-annotations-male-cns-v1.0-minconf-0.5.feather` | Hücre tiplerini, sınıflarını ve taraf bilgilerini belirlemek. |
| `body-neurotransmitters-male-cns-v1.0.feather` | Nörotransmiter tahminlerini modele ilişkin varsayımlarda kullanmak. |
| `connectome-weights-male-cns-v1.0-minconf-0.5.feather` | Hangi segmentin hangisine ne ağırlıkta bağlandığını çıkarmak. |

Bu dosyalar anatomik başlangıç verileridir; hazır çalışan bir simülatör oluşturmazlar. Kamera ile görsel hücreler arasındaki eşleme için ek anotasyon veya kaynak gerekebilir.

## Dosyaları indirdikten sonra

### 1. Veriyi okuyup bağlantı ağını hazırlamak

Python'da `pandas` ve `pyarrow` ile dosyaları açacağız. Önce gerçek sütun adlarını ve kimlik alanlarını kontrol edeceğiz; ardından anotasyon, nörotransmiter ve bağlantı tablolarını nöron/segment kimlikleri üzerinden birleştireceğiz.

Bağlantı tablosu tüm segmentleri kapsadığından, simülasyona alınacak nöronları açık ölçütlerle seçeceğiz. Eksik anotasyonları ve belirsiz nörotransmiter tahminlerini raporlayacağız. Bağlantıları belleği verimli kullanan seyrek bir yapıda saklayacağız.

**Çıktı:** Sürümü sabitlenmiş nöron listesi, bağlantı listesi ve veri kontrol özeti.

### 2. Görsel giriş noktasını belirlemek

Hangi görsel hücrelerin mevcut olduğunu ve görüntü konumlarıyla nasıl ilişkilendirilebildiğini inceleyeceğiz. Gerektiğinde `neuprint-python` ile sorgu, `navis` ile morfoloji incelemesi yapacağız. Başlangıç için yerel neuPrintExplorer kurulumu gerekmiyor.

Tercihimiz, kameradaki parlaklık/kontrast bilgisini uygun duyusal girişlere vermek; hareket yanıtının mümkün olduğunca ağ içinde oluşmasını sağlamak. Hangi hücreye hangi sinyalin verileceği henüz çözülmüş değil ve projenin ilk kritik araştırma adımı bu.

**Çıktı:** Giriş hücrelerinin kimlikleri ve görüntüden nöral girdiye dönüşüm tanımı.

### 3. Bağlantılara nöral dinamik eklemek

İlk aday, Shiu ve arkadaşlarının çalışmasındaki gibi bir leaky integrate-and-fire (LIF) yaklaşımı. Bu modelde nöron girdileri biriktirir, aktivitesi zamanla sönümlenir ve eşik aşılınca spike üretir.

Zaman sabitleri, eşikler, gecikmeler ve bağlantı ağırlıklarının fizyolojik etkiye dönüşümü için parametreler belirlememiz gerekiyor. Nörotransmiter tahminleri tek başına sinaptik etkinin işaretini ve büyüklüğünü kesinleştirmez; kullandığımız varsayımları kaydedeceğiz. Shiu'nun FlyWire modelini MaleCNS'ye uyarlamak ayrıca çalışma gerektirir.

Önce küçük bir devrede veri ve simülasyon hattını doğrulayabiliriz. Ancak kesilen bağlantılar dinamiği değiştireceğinden bu testin sonuçlarını tüm sinir sisteminin davranışı olarak yorumlamayacağız.

**Çıktı:** Tanımlı girdiye yanıt veren, aktivitesi kaydedilebilen bir simülasyon.

### 4. Kontrollü uyaranlardan kameraya geçmek

Önce sabit görüntü ve hareket eden çubuk gibi tekrarlanabilir uyaranlar kullanacağız. Girdiyle aktivitenin değiştiğini kontrol ettikten sonra aynı hattı canlı kameraya bağlayacağız.

Ağın durumu her karede sıfırlanmayacak. Kamera kare hızı ile sayısal entegrasyon adımını ayrı tutacağız; eski karelerin birikmesini önleyip gerçek zaman performansını ölçeceğiz.

**Çıktı:** Görsel girdiye sürekli yanıt veren nöral aktivite akışı.

### 5. Aktiviteyi Max/MSP'de duyulur hâle getirmek

Seçilen popülasyonların spike sayısı veya kısa zaman pencerelerindeki aktivitesini OSC ile Max'e göndereceğiz. İlk patch, bu aktiviteyle kısa sesler veya rezonatörler üretebilir.

Sonifikasyon eşlemesi bizim tasarım kararımız olacak. Başlangıçta ayrıca “şaşırma”, “huzursuzluk” veya “alışma” kuralları eklemeyeceğiz; ağda gerçekten oluşan yanıtı dinleyeceğiz. Ses seviyesini güvenli ve tutarlı tutan ölçekleme/sınırlama uygulayacağız.

**Çıktı:** Ziyaretçinin hareketiyle değişen, nöral aktivite kaynaklı ses.

## İlk prototipin başarı ölçütü

Kameradaki değişimin nöral aktiviteyi değiştirdiği, bu değişimin duyulduğu ve sistemin en az 10 dakika kesintisiz çalıştığı bir prototip. Gecikmeyi, bellek kullanımını ve ağın sessizliğe ya da sürekli aşırı aktiviteye saplanıp saplanmadığını ölçeceğiz. Ardından ziyaretçinin sese göre hareketini değiştirdiği etkileşimi değerlendireceğiz.

Başlamak için bilgisayarın işletim sistemi, RAM ve GPU bilgileri ile Max'in hangi makinede çalışacağı gerekli. Simülasyon motoru ve ağ kapsamı bu donanımda yapılacak ölçümlere göre kesinleşecek.

## Görüşmede netleşenler — 24 Eylül 2026

- Makine: macOS 14.6.1, Apple M1 Pro, 32 GB RAM, 16 çekirdek entegre GPU. Max/MSP aynı Mac üzerinde çalışacak.
- Üç Feather dosyası `data/` klasöründe mevcut. `.mcns` sanal ortamı Python 3.9.17 ile oluşturulmuş.
- Etkileşime iki gestürel durum hâkim olacak: ziyaretçinin “sinek”ten kaçmaya çalışması ve “sinek”i yakalamaya çalışması.
- “Sinek” yalnızca sesle hissedilen bir varlık olacak. Ekranda görsel hedef planlanmıyor; uzamsal ses konumu henüz tanımlanmadı.
- Kamera için MediaPipe veya benzeri bir araçla el ve/veya kafa takibi değerlendirilecek; araç seçimi henüz kesinleşmedi.

**Tasarım önerisi, henüz kararlaştırılmadı:** Bu iki durumu başlangıçta hazır ses tetikleyen jest etiketleri yerine hareket senaryoları olarak ele almak. El/kafa konumu, hız ve el açıklığı gibi ölçümler etkileşimi incelemeye yardımcı olabilir. Bunların nöral girdiyi doğrudan mı belirleyeceği, yoksa kamera parlaklık/kontrast girdisi yanında yalnızca ölçüm için mi kullanılacağı açık bir tasarım kararıdır. Doğrudan özellik aktarımı seçilirse bu, biyolojik görsel girişten ayrı bir modelleme varsayımı olarak kaydedilmeli.

**Ölçüm sınırı:** “Sinek” için izlenen bir uzamsal hedef tanımlanmadığı sürece el/kafa hareketi “sineğe yaklaşma” veya “sinekten uzaklaşma” olarak ölçülemez. Kameraya göre hareket ve kişinin kendi bedenine göre el konumu ölçülebilir; kaçınma/yakalama niyeti bunlardan kesin olarak çıkarılamaz.

## Kaynaklar

- [MaleCNS veri indirme ve Python erişimi](https://male-cns.janelia.org/download/)
- [navis: neuPrint öğreticisi](https://navis-org.github.io/navis/generated/gallery/4_remote/tutorial_remote_00_neuprint/)
- [neuPrintExplorer: veri sorgulama arayüzü](https://github.com/connectome-neuprint/neuPrintExplorer)
- [Shiu ve arkadaşları, 2024: hesaplamalı sinek beyni modeli](https://www.nature.com/articles/s41586-024-07763-9)
- [Shiu modelinin kodu](https://github.com/philshiu/Drosophila_brain_model)

*Durum (24 Eylül 2026): `.mcns` ortamına pandas, pyarrow, numpy ve scipy kuruldu; bağımlılık kontrolü geçti ve sürümler `requirements-data.lock.txt` dosyasına kaydedildi. Üç Feather dosyasının şemaları açıldı: anotasyon kimliği `bodyId`, nörotransmiter kimliği `body`, bağlantı alanları `body_pre`, `body_post`, `weight`. Anotasyonlarda `assignedOlHex1` ve `assignedOlHex2` alanları mevcut; anlamları ve dolulukları henüz doğrulanmadı. Tam veri kalite kontrolü, kamera takibi ve simülasyon henüz yapılmadı.*
