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

Sonifikasyon eşlemesi bizim tasarım kararımız olacak. İlk tasarımda ayrıca “şaşırma”, “huzursuzluk” veya “alışma” kuralları eklemeden ağda oluşan yanıtı dinlemek planlandı. 24 Eylül görüşmesindeki ek istek doğrultusunda, nöral modelden ayrı ve isteğe bağlı bir uçuş/kaçış/saklanma katmanı eklendi (aşağıya bakınız). Max/MSP tarafındaki ses tasarımını kullanıcı devralacak.

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

## Uygulama kararları — 24 Eylül 2026

- Uygulama kapsamı kamera → simülasyon → OSC. Max patch'i kullanıcıya ait.
- Sağ optik lobdan 61 kolon ve bunların seçilmiş T4/T5 hedefleriyle 1.107 nöron, 16.700 bağlantılı ilk devre çıkarıldı. Kaynak kimlikleri, SHA-256 değerleri, NT belirsizlikleri ve kesilen bağlantılar manifestte kayıtlı.
- Kamera parlaklığı L1/L2/L3 girişlerine yaklaşık bir kolon eşlemesiyle aktarılıyor. Fotoreseptörler atlanıyor; bu bir kalibre edilmiş retina modeli değil.
- Nöral model boyutsuz, sürekli durumlu bir LIF prototipi. NT işaretleri ve dinamik parametreleri açık varsayımlar olarak kaydediliyor.
- Yerel UI'de canlı kamera, el/yüz işaretleri, gri nöral giriş, soma/kolon haritaları ve popülasyon aktivitesi bulunuyor. Haritalar seçilmiş devreyi gösterir; soma haritası neuropil/ROI haritası değildir.
- Kullanıcının yeni isteğiyle `--behavior` seçeneği eklendi: sakinlikte uçuş; el/yüz hareketinde kaçış ve saklanma; sakinlik sonrası geri dönüş. Bu yazılmış sahne davranışıdır, nöral modelin korku duygusu ürettiği iddiası değildir. Hareket ölçümü bu katmanı, kamera parlaklığı ise nöral modeli sürer.
- OSC'de ham nöral aktivite ile davranış/uçuş ses kontrolü ayrı adreslerde gönderilir. Ses burada sentezlenmez. Ayrıntılı sözleşme ve başlatma komutları `README.md` içindedir.

## Kaynaklar

- [MaleCNS veri indirme ve Python erişimi](https://male-cns.janelia.org/download/)
- [navis: neuPrint öğreticisi](https://navis-org.github.io/navis/generated/gallery/4_remote/tutorial_remote_00_neuprint/)
- [neuPrintExplorer: veri sorgulama arayüzü](https://github.com/connectome-neuprint/neuPrintExplorer)
- [Shiu ve arkadaşları, 2024: hesaplamalı sinek beyni modeli](https://www.nature.com/articles/s41586-024-07763-9)
- [Shiu modelinin kodu](https://github.com/philshiu/Drosophila_brain_model)

*Durum (24 Eylül 2026): Veri hazırlama, kamera, MediaPipe el/yüz takibi, LIF simülasyonu, canlı UI ve OSC çıkışı uygulandı. 17 otomatik test geçti; gerçek kamerada algılama ve dört sahne durumu gözlendi. Uzun koşuların gerçek tamamlanma/hata sonuçları `runs/*/summary.json` dosyalarındadır. Tam ortam `requirements.lock.txt` ile sabitlendi; MediaPipe 0.10.21 kullanılıyor. Biyolojik hareket seçiciliği ve tüm-CNS davranışı doğrulanmış değildir.*

## Tarayıcı widget uygulaması — 24 Eylül 2026

`python -m mcns serve` ile kalıcı yerel sunucu başlar. Kamera/simülasyon/OSC Python’da;
başlat/durdur, sahne üzerindeki sinek ve Web Audio sentezi tarayıcıdadır. Gerçek görsel
alt-devrenin giriş dışı kolon aktivitesi yön/hız/tınıya bağlandı. Bağlantı A/B kontrolü
sinaptik matrisi gerçekten devreden çıkarır; keşif ve korku kuralları ayrıca tasarlanmıştır.
Kenarlar ve el/yüz merkezleri 2B konma adaylarıdır; semantik nesne/3B yüzey algılama değildir.
`/mcns/widget/flight` tarayıcı sineğinin hareketini OSC’ye taşır. Eski OSC adresleri korunur.
Kamera görüntüleri diske kaydedilmez. Detaylar ve çalıştırma yönergesi README.md içindedir.

## İki gözlü, DN okumasına dayalı revizyon — 24 Eylül 2026

Önceki genel insan hareketi → kaç/saklan kuralı varsayılan widget’tan çıkarıldı.
`configs/bilateral.json` ve `build/bilateral-v1`: 8.440 gerçek hücre / 278.080 anatomik bağlantı,
iki gözün kolonları + LC4/LPLC2 + seçili DN’ler + iki upstream katman. Tarayıcı pozundan
ikili yerel retina görüntüsü üretilir. EfficientDet-Lite0 çoklu kişi/nesne kutuları ve geçici
ID’ler verir. Sinek temas ettiği kutuyla taşınır; nesne etiketi nöral girdi değildir.

Kontrollü testte DN aktivitesi bağlantılara bağlıydı ancak yaklaşma seçiciliği başarısızdı:
uzaklaşma yaklaşmadan güçlü yanıt üretti. Bu sürüm gerçek wiring kullanan deneysel devredir;
doğal biyolojik kaçışın başarıyla yeniden üretildiği iddia edilmez. Fizyoloji ve retinotopi
kalibrasyonu açık bilimsel gereksinimdir. Test raporu: build/bilateral-v1/validation.json.

## Dönüş devresi araştırması — 25 Eylül 2026

DNa02 giriş kapsamının düşük olduğu ve DNg02 ailesinin seçilmiş devrede bulunmadığı
saptandı. Araştırma için 14.206 hücreli gerçek alt-devre, bağlantı kapsamı denetimi,
eşit parlaklıkta yön testleri ve ayrı bir dereceli görsel/LIF hibrit model eklendi.
Hibrit model bağlantılara bağlı motor yanıt üretse de yön seçiciliği ve doygunluk
kontrollerini geçmedi; canlı modele alınmadı. Doğal uçuş henüz elde edilmedi.
26 Python testi ve widget testleri geçti. Bulgular, bilimsel sınırlar ve tekrar
çalıştırma komutları [STEERING_AUDIT.md](STEERING_AUDIT.md) içindedir.
