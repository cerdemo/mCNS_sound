# MaleCNS browser widget → ses + OSC

Kamera veya kontrollü görüntü → MaleCNS bağlantıları üzerinde sürekli LIF simülasyonu → OSC.
Max/MSP patch'i bu projenin kapsamı dışında. Varsayılan hedef `127.0.0.1:9000`.

## İki gözlü browser widget (varsayılan)

```sh
source .mcns/bin/activate
python -m mcns serve
```

[Widget’ı açın](http://127.0.0.1:8765), **Başlat**, ardından **Sesi aç** düğmelerini kullanın.
Varsayılan grafik `build/bilateral-v1`, config `configs/bilateral.json`.
Kamera numarası ve kontrollü görüntü kaynağı tarayıcıdan seçilir. Durdur kamerayı ve
simülasyonu kapatır; sunucu açık kalır. Terminalde Ctrl-C sunucuyu kapatır.
OSC `127.0.0.1:9000` hedefine devam eder. Kamera görüntüleri dışarı gönderilmez/diske kaydedilmez.

### Gerçek devre ile simülasyon varsayımları

**8.440 gerçek hücre, 278.080 anatomik bağlantı** (277.784 etkin işaretli bağlantı).
Sol ve sağ optik kolonlar, T4/T5 örneklemi, LC4/LPLC2, seçili DN hücreleri ve bunların
iki katman gerçek upstream ortakları birlikte simüle edilir. Aynalanmış/sentetik nöron eklenmez.
Devre tam CNS değildir; grafik seçimi ve kesilen bağlantılar `manifest.json` içindedir.

- Sineğin tarayıcıdaki konum/yönü Python’a geri gelir. Kamera görüntüsü bu poza göre
  iki **yerel, düzlemsel sanal göz** görüntüsüne örneklenir. Ortada yapay kör boşluk yoktur;
  ön görüşte örtüşme vardır. Tek kamera stereo/360° görüntü sağlayamaz. Yön, ölçek ve
  göz projeksiyonu kalibre edilmemiştir; gerçek bileşik göz optiği iddiası taşımaz.
- Giriş yalnızca gerçek sol/sağ **L1/L2** hücrelerine verilir. Fotoreseptör ve
  reseptör/fizyoloji ayrıntıları henüz modellenmez. Sol tarafta bazı hücre tiplerinin
  kolon anotasyonları eksiktir; sağ tarafın haritası sol diye kopyalanmaz.
- DNp01/02/04/11 hücrelerinin yumuşatılmış, bazal düzey üzerindeki aktivitesi hızlanma/kalkış
  okumasına; DNa02 sağ-sol aktivite farkı dönüşe bağlanır. DNp07/10 aktivitesi ölçülür,
  henüz konma kontrolünde kullanılmaz. Bu çıkış eşlemesi biyolojik motor kas simülasyonu değildir.
- **İnsan hareket etti → kaç**, **üç saniye bekle → geri çık** kuralları bu sürümde yoktur.
  Küçük temel keşif hızı/yön gürültüsü, ekran sınırı ve nesne teması hâlâ modellenmiş fizik
  varsayımlarıdır. `escaping` widget OSC modu deneysel DN hızlanmasını ifade eder; doğrulanmış korku değildir.
- Konma, algılanan nesnenin kutusunun üst kenarıyla geometrik karşılaşmadır. Sinek kutuyla
  birlikte taşınır ve yürür. Kutu bir 3B yüzey/segmentasyon maskesi değildir; hatalı algılama
  ve perspektif yüzünden havada konma görülebilir. Nesne kaybolunca uçuşa geçilir.
- Ortalama giriş dışı kolon aktivitesi hız ve tınıyı etkiler; yürürken uçuş sesi susar.
  Ses tarayıcıda harmonikli osilatör, filtre, frekans modülasyonu ve stereo pan ile üretilir.
- **A/B: bağlantıları kapat** gerçek sinaptik matrisi sıfırlar; aynı kamera girdisi ve
  L1/L2 sürüşü kalır. Sinaptik durum doğal olarak sönümlenir. Temel keşif fiziği sürer.

### Nesneler ve birden fazla insan

Yerel **MediaPipe EfficientDet-Lite0** nesne algılar (COCO sınıfları, eşik 0.4, en çok 20 kutu,
hedef 8 Hz). Her kişi ayrı `person #id` olarak izlenir. Sınıf ve hareket kestirimli konum
ataması kullanılır; bu kimlik tanıma değildir. Kapanma/kesişme veya 0.8 saniyelik kayıpta
ID değişebilir. MediaPipe aynı zamanda en çok 4 yüz/6 el çıkarır; eski OSC el/yüz kanalları
uyumluluk için birer özet tutar, `tracking.jsonl` ek yüz/el listesini içerir.

**Nesneleri ve yönü göster** kutuları açar; iki gözün gerçek girdisi hemen altta görünür.
Nesne sınıfları ve kişi etiketleri nöral ağa enjekte edilmez. Nesne kutuları temas fiziğine,
pikseller görsel nöral girdiye gider. Yoğun optik akış ayrıca ölçülür, korku tetikleyicisi değildir.
Tek etkin widget sekmesi kullanın. Tarayıcı telemetrisi 1 saniye eskirse widget OSC sesi sıfırlanır.
Arka plandaki sekmede yerel ses susar; ses düğmesi/seviyesi OSC davranış kazancını değiştirmez.

### Doğrulama sonucu ve açık sınır

`python scripts/validate_bilateral.py` sabit, yaklaşan, uzaklaşan ve yatay hareket eden
kontrollü uyaranları aynı pozdan karşılaştırır; bağlantısız kontrol de çalışır.
Sonuç `build/bilateral-v1/validation.json` dosyasındadır. Mevcut tek tip LIF ile **yaklaşma
seçiciliği doğrulanmadı**: uzaklaşan uyaranın DN yanıtı yaklaşandan daha büyüktü.
Bağlantısız ağda DN yanıtı sıfırdır. Bu, bağlantısal nedenselliği destekler; doğal kaçış
veya biyolojik doğruluk kanıtı değildir. UI bu sınırı görünür tutar.

Sonraki bilimsel gereksinimler: hücre tipine özgü zamansal/graded dinamikler, giriş
polaritesi ve adaptasyon, retinotopik kalibrasyon, eksik upstream yolların denetimi ve
sabit/çeviri/yaklaşma/uzaklaşma uyaranlarında seçicilik doğrulaması. Bunları gerçek bağlantı
sayısını artırmanın otomatik olarak çözdüğü varsayılmaz.

Yeni kurulumda:

```sh
python scripts/download_models.py
python -m mcns prepare --config configs/bilateral.json --graph build/bilateral-v1
```

Mevcut grafik klasörü doluysa üzerine yazılmaz; başka `--graph` yolu seçin.
Eski davranışlı prototipi karşılaştırmak için:
`python -m mcns serve --graph build/visual-v1 --config configs/default.json`.

Widget OSC: `/mcns/widget/flight sequence:int mode:string gain:float wing_hz:float speed:float x:float y:float activity:float`.
DN OSC: `/mcns/descending sequence:int escape_drive:float turn_drive:float landing_drive:float`.
`escape_drive/landing_drive` 0..1, `turn_drive` −1..1; bunlar açık decoder parametreleridir.
Eski `/mcns/flight` yalnızca eski `--behavior` sürümünde gönderilir. Popülasyon sayısı artık
682’dir; Max eşlemesi `/mcns/population` metadata’sını izlemelidir.

## Komut satırı ile süreli koşular

Komutları proje klasöründe çalıştırın. Mevcut `.mcns` ortamı hazırlanmıştır.

```sh
source .mcns/bin/activate
python -m mcns run --source bar --duration 60
```

Kamera, el ve kafa takibiyle:

```sh
python -m mcns run --source camera --track --duration 600
```

Canlı nöral aktivite haritasını da açmak için:

```sh
python -m mcns run --source camera --behavior --dashboard --duration 600
```

Tarayıcıda [127.0.0.1:8765](http://127.0.0.1:8765) açın. Sayfa yerel bilgisayara
bağlıdır; dışarıya yayın yapılmaz. Portu `--dashboard-port 8766` ile değiştirebilirsiniz.
Kamera olmadan denemek için `--source bar --dashboard` kullanın.

Aşağıdaki sabit sayılar eski `visual-v1` grafiğine aittir; yeni grafikte UI metadata’yı kullanır.

- **Anatomik soma konumları:** anotasyonda konumu olan 862 hücrenin XY/XZ/YZ izdüşümü.
- **Görsel kolonlar:** koordinatı atanmış 915 hücrenin 61 kolondaki ortalama aktivitesi.
- **Popülasyon çubukları:** tüm 1.107 hücre, konum anotasyonu olmayanlar dahil.
- **Zaman grafiği:** giriş ve diğer hücrelerin ayrı ortalama ateşleme hızları.

Hücre tipi filtresi, Hz renk ölçeği ve hücre ayrıntıları bulunur. Renk son OSC
penceresindeki spike/nöron/saniye değeridir. Tek hücre için 50 ms pencerede bir spike
20 Hz demektir; görüntüde yanıp sönme normaldir. Kolon görünümünde üst üste gelen
hücreler ortalanır. T4/T5 için eksik kolon konumu uydurulmaz.
Bu görünüm, tüm beynin neuropil/ROI aktivite haritası değildir. Soma bir hücrenin
gövdesidir; sinapslarının bulunduğu bölgeyi göstermez. Bölgesel sinaps aktivitesini
göstermek için ek ROI/sinaps konum verisi gerekir.

Görünümü dondurmak yalnızca tarayıcıyı etkiler. `run --dashboard` kapanınca sayfa
"Bağlantı kesildi" diyerek son görüntüyü tutar. `serve` sunucusu ise açık kalır ve yeniden başlatılabilir.
Sunucu en yeni ölçümü, tarayıcı yalnızca son 20 saniyeyi saklar. Kamera önizlemesi
ve 128×128 nöral giriş görüntüsü yalnızca localhost üzerinden tarayıcıya aktarılır.
Önizlemedeki el/yüz işaretleri çıkarım yapılan kareye çizilir; yaşları UI'de gösterilir.
Görüntüler diske kaydedilmez.

## Eski prototip: uçuş / kaçış / saklanma davranışı (iki gözlü sürümde kapalı)

`--behavior` el/yüz takibini de açar. Bu, kullanıcının sonradan istediği sahne
davranışıdır; nöral ağın öğrenilmiş veya ortaya çıkmış korku yanıtı değildir.
Nöral bağlantılar ve nöral OSC değerleri bu katmandan etkilenmez.

- **flying:** sakinlikte sanal 2B ses konumu dolaşır, uçuş ses kazancı 1'dir.
- **escaping:** el veya yüz hareketi eşik üzerinde en az 0.1 s kalırsa, konum
  izlenen kişinin yatay konumunun tersindeki kenara 0.6 s'de çekilir; kazanç söner.
- **hidden:** uçuş kazancı ve kanat parametresi 0 olur. Yeni hareket sakinlik sayacını sıfırlar.
- **recovering:** hareket 3 s boyunca düşükse, konum ve kazanç 1.5 s'de geri döner.
  Bu sırada tekrar hareket olursa yeniden kaçış başlar.

Hareket skoru, takip edilen el/yüz merkezlerinin 2B hızından hesaplanır; sabit insan
varlığı hareket değildir. Kamera/başka nesne hareketi için ham piksel farkı kullanılmaz.
Hızlarda 0.025 görüntü birimi/s deadband ve 0.12 s yumuşatma vardır. Başlatma eşiği
0.22, sakinlik eşiği 0.10'dur; tüm parametreler `configs/default.json → behavior` içindedir.
Hız eşlemesi kamera görüş alanına bağlı olduğundan kurulum sırasında ayarlanmalıdır.
Bu sürüm yaklaşmayı, elin kapanmasını veya yakalama niyetini ayrıca sınıflandırmaz.

0.5 s'den eski takip verisi sessizlik üretir ve saklanmadan dönüşü bekletir.
Güncel çıkarımda insan bulunmaması ise boş sahne kabul edilir; sakinlik sonrası uçuş
geri gelebilir. Yani **algılama yokluğu** ve **eski/kesilmiş veri** ayrı durumlardır.

Sanal konum bir akustik tasarım parametresidir; gerçek 3B sinek fiziği, kamera bakış
açısı veya insan-sinek mesafesi değildir. `wing_hz` 190–230 Hz arasında seçilmiş ses
sentez parametresidir; ölçülmüş biyolojik kanat frekansı olarak yorumlanmamalıdır.

Max'e ek mesajlar:

- `/mcns/behavior`: `sequence:int state:string motion:float human_present:int tracking_valid:int`.
- `/mcns/flight`: `sequence:int gain:float wing_hz:float speed:float x:float y:float`.

`gain`, `speed`, `x`, `y` 0–1 aralığındadır; `gain=0` uçuş sesini susturmalıdır.
Max tarafında bir başlangıç eşlemesi: uçuş sesinin amplitüdünü `gain` ile çarp,
`wing_hz` ile vızıltı/periyodik modülasyon hızını sür, `x/y` ile ses konumunu kontrol et.
Ham nöral `/mcns/activity` değerleri tını/rezonansları modüle etmeyi sürdürür.
Nöral hızlar saklanma sırasında sıfırlanmaz; davranış sesi kısmak için ayrı kapı sağlar.

İlk kamera kullanımında macOS kamera izni gerekebilir. Erişim olmazsa Sistem Ayarları →
Gizlilik ve Güvenlik → Kamera bölümünden komutu çalıştıran uygulamayı kontrol edin.
`--device 1` başka kamerayı seçer; `--mirror` görüntüyü yatay çevirir (varsayılan kapalı).
Görüntü kaydedilmez; yerel model çıkarımı yapılır. Diskte yalnızca nöral aktivite,
performans, davranış ve takip özellikleri tutulur. Kamera önizlemesi dashboard'dadır.

`--track` olmadan da kamera nöral simülasyonu sürer. Takip kanalı nöral girdiyi değiştirmez.
`--behavior` kapalıyken kaçış/saklanma kuralı çalışmaz. Hiçbir modda ses sentezi yapılmaz.

Max olmadan OSC paketlerini görmek için **ayrı terminalde**:

```sh
source .mcns/bin/activate
python scripts/osc_monitor.py
```

Bu alıcı ile Max aynı UDP portunu eşzamanlı kullanmamalı. Alıcıyı kapatıp Max'i açın.
Birden çok simülasyonu aynı hedef porta eşzamanlı göndermeyin.
Farklı hedef: `--host 127.0.0.1 --port 9001`. Ctrl-C durdurur.

## Kurulumu yeniden oluşturma

Python 3.9 / Apple Silicon ortamında doğrulanan tam bağımlılıklar `requirements.lock.txt` içinde.
Doğrudan bağımlılıklar `requirements.txt` içinde. `opencv-python` ile
`opencv-contrib-python` birlikte kurulmaz; bu ortam yalnızca contrib paketini kullanır.

```sh
python3 -m venv .mcns
.mcns/bin/python -m pip install -r requirements.lock.txt
.mcns/bin/python scripts/download_models.py
.mcns/bin/python -m mcns prepare
```

`data/` altında proje özetindeki üç Feather dosyası bulunmalı. Hazır devre
`build/visual-v1/` altında oluşturulmuştur. `prepare`, dolu çıktı klasörünün üstüne yazmaz.
Seçimi değiştirirken config dosyasını kopyalayıp yeni bir çıktı adı kullanın:

```sh
python -m mcns prepare --config configs/default.json --graph build/visual-v2
python -m mcns run --graph build/visual-v2 --source bar
```

## Görsel devre ve açık varsayımlar

Varsayılan devre sağ optik lobda, `status=Traced`, `superclass=ol_intrinsic` hücrelerinden
seçilir. Kolon merkezi `(18,19)`, yarıçapı 4'tür. Kolon bölgesi
`max(abs(dq), abs(dr), abs(dq-dr)) <= 4` ile tanımlanır.
Bu bölgedeki koordinat atanmış tüm tipler ve buradan en çok sinaps alan her T4/T5
alt tipinden en fazla 24 hücre alınır. Eşitlikte küçük bodyId önce gelir.
Seçilen hücreler arasındaki tüm anatomik bağlantılar korunur; eşikleme/öğrenme yoktur.

Mevcut veride 61 kolon, 1.107 nöron, 183 giriş hücresi, 16.700 bağlantı ve 23 popülasyon var.
Kapsam dışına çıkan bağlantılar kesilir; sayıları ve sinaps toplamları manifestte bulunur.
Bu kesim dinamiği değiştirir; sonuçlar tüm sineğin davranışı olarak yorumlanamaz.

L1/L2/L3 hücrelerine gri görüntü parlaklığı enjekte edilir. Fotoreseptörler atlanır;
bu bir fizyolojik retina modeli değildir. L1 ve L2 için ayrıca ON/OFF, hareket algılama
veya kaçınma/yakalama kuralı eklenmez. Sabit parlaklık da aktivite üretir.
Hareket seçiciliği biyolojik olarak doğrulanmış değildir.

Kolon koordinatları `x=q-r/2`, `y=sqrt(3)*r/2` ile düzleme taşınıp seçilen bölgenin
ekran aralığına ölçeklenir. Bu dönüşümün yönü ve kamera görüş alanı bir tasarım
varsayımıdır; sineğin göz geometrisine kalibre edilmemiştir. Görüntü 128×128 griye
indirilir ve giriş hücrelerine bilineer örneklenir.

Nörotransmiter **consensus_nt** alanından asetilkolin +1; GABA, glutamat ve histamin -1
kabul edilir. Diğer/belirsiz etiketler 0 etkili çıkış üretir. Bu kaba bir varsayımdır;
reseptöre bağlı işaretler ve nöromodülasyon modellenmez. Bireysel tahmin güveni,
eksiklikler ve consensus ile anlaşmazlıklar ayrıca raporlanır; düşük güvenli hücrelerin
sessizce elendiği varsayılmamalı.

`neurons.feather`: nöron kimliği, popülasyon, anotasyon/NT alanları, giriş bayrağı.
`edges.feather`: body_pre/body_post, matris indisleri ve ham sinaps sayısı.
`weights.npz`: seyrek matris, **satır=hedef, sütun=kaynak**, NT işaretli sinaps sayısı.
`manifest.json`: seçim, eksik veri, kesilen bağlantılar, kaynak ve çıktı SHA-256 değerleri.
Tam bağlantı tablosu partiler halinde taranır; belleğe bir bütün olarak yüklenmez.

## Dinamik ve zamanlama

Boyutsuz LIF: dinlenme/reset=0, eşik=1.

```text
dv/dt = (-v + I_görüntü + g) / tau_m
dg/dt = -g / tau_s
gecikmiş spike geldiğinde: g_hedef += sinaps_sayısı × NT_işareti × synapse_gain
I_görüntü = 0.15 + 2.0 × parlaklık  (yalnızca giriş hücrelerinde)
```

Varsayılan `dt=1 ms`, `tau_m=20 ms`, `tau_s=5 ms`, refrakter süre 2 ms,
gecikme 2 ms, sinaps kazancı 0.04. Adım içinde sabit dış girdi ve üstel sinaptik akım
için analitik entegrasyon kullanılır. Refrakter durumda voltaj reset seviyesinde
tutulur; sinaptik akım sönmeye devam eder ve spike sonrası sıfırlanmaz.
Gecikme/refrakter süre en yakın adım sayısına yuvarlanır; etkili değerler run.json'a yazılır.
Bu, Shiu modelinin birebir portu veya MaleCNS için fizyolojik olarak fit edilmiş model değildir.

Kamera tek bir en yeni kareyi saklar. Model her karede sıfırlanmaz.
Görüntü güncelleme hedefi 30 Hz, OSC 20 Hz; adım yuvarlamasıyla gerçekleşen hızlar run.json'dadır.
Takip ayrı iş parçacığında çalışır ve en yeni kareyi kullanır. Bir saniyeden eski kamera
karesi hata ile durdurur. 250 ms'den fazla hesaplama gecikmesinde simülasyon saati
yavaşlatılır ve kayıp duvar saati raporlanır; eski kareler sıraya alınmaz.

## Max'e OSC sözleşmesi — sürüm 1

OSC 1.0 UDP, varsayılan `127.0.0.1:9000`. Adresler ve argüman sırası:

- `/mcns/schema`: `version:int` (=1).
- `/mcns/population`: `index:int name:string neuron_count:int`.
- `/mcns/rates`: `sequence:int simulation_seconds:float rate0:float rate1:float ...`.
- `/mcns/activity`: `sequence:int simulation_seconds:float value0:float value1:float ...`.
- `/mcns/health`: `sequence:int simulation_seconds:float wall_seconds:float frame_age_ms:float rss_mb:float clock_slip_seconds:float overwritten_camera_frames:int`.
- `/mcns/state`: `completed`, `stopped`, `interrupted` veya `error` metni; kapanışta gönderilir.

`rate`: son OSC penceresindeki spike sayısı / nöron sayısı / pencere süresi, Hz/nöron.
`activity`: `clip(rate / 100, 0, 1)`; 100 Hz config içindeki `normalization_hz` ile değişir.
Ham `rates` kırpılmaz. Popülasyon sırası alfabetiktir; her koşunun `run.json` dosyasında
ve saniyede bir tekrarlanan `/mcns/population` mesajlarında verilir.
Metadata tekrarları geç açılan bir Max alıcısının eşlemeyi öğrenmesini sağlar.

Örnek: `/mcns/activity 42 2.15 0.0 0.03 ...`; ilk iki sayı kanal aktivitesi değildir.
Normal kapanışta son bir sıfır aktivite paketi gönderilir. UDP teslim garantisi taşımaz;
Max tarafında paket kesildiğinde, örneğin 500 ms sonra sesi söndüren watchdog önerilir.
Grafik/config değiştirildiğinde popülasyon sayısı değişebilir; sabit 23 kanalı varsaymayın.

`--track` açıksa ek ölçüm mesajları:

- `/mcns/tracking/hand`: `frame:int side:string present:int x:float y:float vx:float vy:float openness:float handedness_score:float age_ms:float`.
- `/mcns/tracking/face`: `frame:int present:int x:float y:float vx:float vy:float width:float age_ms:float`.

`x/y` görüntü koordinatlarıdır (sol/üst 0); `vx/vy` görüntü birimi/saniye.
El açıklığı, parmak uçlarının bileğe ortalama 2B uzaklığı / avuç uzunluğu oranıdır;
kalibre edilmiş kavrama ölçüsü değildir. Yüz genişliği görüntü genişliği oranıdır,
metrik derinlik değildir. `side`, modelin Left/Right etiketidir; ayna seçimiyle birlikte
kurulumda kontrol edin. İki aynı taraf etiketi gelirse daha yüksek skorlu olan tutulur.
Takip kaybolduğunda `present=0` ve özellikler sıfır olur; tekrar görünmede hız sıfırdan
başlar. Bir saniyeden eski takip sonucu da geçersizdir. Bu kanal ayrı bir gözlem
kanalıdır; nöral aktivite kaynaklı ses istendiğinde `/mcns/activity` kullanılmalıdır.

## Kayıt ve test

Her koşu ayrı `runs/<timestamp>/` klasörü üretir:

- `run.json`: tam config, kullanılan grafiğin kimliği, popülasyon sırası, etkili zamanlama.
- `activity.csv`: her OSC penceresinde ham popülasyon hızları, bellek ve zamanlama ölçümleri.
- `tracking.jsonl`: takip açıksa işlenen karelerin hareket özellikleri; görüntü içermez.
- `behavior.jsonl`: davranış açıksa her OSC penceresinde durum, hareket, kazanç ve uçuş parametreleri.
- `scene.jsonl`: nesne/kişi kutuları, geçici ID’ler ve ölçüm yaşı; görüntü içermez.
- `widget.jsonl`: widget/harita açıkken OSC pencerelerinde tarayıcı uçuş durumu ve sonraki pencereye uygulanacak bağlantı A/B bayrağı.
- `summary.json`: tamamlanma/hata durumu, spike toplamları, sessiz hücre oranı ve performans.

```sh
python -m unittest discover -s tests -v
node tests/test_widget.js
python -m mcns run --source black --duration 5 --fast
python -m mcns run --source white --duration 5 --fast
python -m mcns run --source static --duration 5 --fast
python -m mcns run --source bar --duration 600
```

`--fast` yalnızca kontrollü uyaranlarda kullanılır; gerçek zaman testi sayılmaz.
Bellek RSS örnekleri tüm Python sürecini kapsar. `frame_age_ms`, OpenCV'nin kareyi
teslim ettiği andan OSC yayınına kadar yaşı ölçer; sensör, Max ve ses kartı dahil
uçtan uca gecikme değildir. Max patch’inin işitsel doğrulaması kullanıcıya aittir; tarayıcı sentezi widget içinde dinlenebilir.

## Kaynaklar

25 Eylül dönüş araştırması: [devre kapsamı, deneysel fizyoloji ve test sonuçları](STEERING_AUDIT.md).
14.206 hücreli araştırma devresi ve hibrit model eklendi; yön seçiciliği testleri
başarısız olduğu için canlı widget’ın varsayılan modeline geçirilmedi.

- [MaleCNS verisi ve lisansı (CC-BY)](https://male-cns.janelia.org/download/).
- [Optik kolon koordinatlarının tanımı](https://github.com/reiserlab/male-drosophila-visual-system-connectome-code/blob/main/docs/coordinate-systems.md).
- [Shiu modelinin referans kodu](https://github.com/philshiu/Drosophila_brain_model/blob/main/model.py).
- [MediaPipe el takibi](https://developers.google.com/edge/mediapipe/solutions/vision/hand_landmarker/python) ve [yüz takibi](https://developers.google.com/edge/mediapipe/solutions/vision/face_landmarker/python).

### İki gözlü devre ve algılama kaynakları

- [LC4/DN kaçış yönü araştırması](https://www.nature.com/articles/s41586-022-05562-8).
- [LPLC2 yaklaşma seçiciliği](https://www.nature.com/articles/nature24626).
- [Göz geometrisi ve görüş örtüşmesi](https://www.nature.com/articles/s41586-025-09276-5).
- [DN işlevleri: karşılaştırmalı connectomics](https://www.nature.com/articles/s41586-025-08925-z).
- [MediaPipe nesne algılama](https://developers.google.com/edge/mediapipe/solutions/vision/object_detector).
