# MaleCNS → OSC prototipi

Kamera veya kontrollü görüntü → MaleCNS bağlantıları üzerinde sürekli LIF simülasyonu → OSC.
Max/MSP patch'i bu projenin kapsamı dışında. Varsayılan hedef `127.0.0.1:9000`.

## Çalıştırma

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
python -m mcns run --source camera --track --dashboard --duration 600
```

Tarayıcıda [127.0.0.1:8765](http://127.0.0.1:8765) açın. Sayfa yerel bilgisayara
bağlıdır; dışarıya yayın yapılmaz. Portu `--dashboard-port 8766` ile değiştirebilirsiniz.
Kamera olmadan denemek için `--source bar --dashboard` kullanın.

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

Görünümü dondurmak yalnızca tarayıcıyı etkiler. Simülasyon kapanınca sayfa
"Bağlantı kesildi" diyerek son görüntüyü tutar; yeniden çalıştırınca sayfayı yenileyin.
Sunucu en yeni ölçümü, tarayıcı yalnızca son 20 saniyeyi saklar. Kamera kareleri
tarayıcıya aktarılmaz.

İlk kamera kullanımında macOS kamera izni gerekebilir. Erişim olmazsa Sistem Ayarları →
Gizlilik ve Güvenlik → Kamera bölümünden komutu çalıştıran uygulamayı kontrol edin.
`--device 1` başka kamerayı seçer; `--mirror` görüntüyü yatay çevirir (varsayılan kapalı).
Görüntü kaydedilmez; yerel model çıkarımı yapılır. Diskte yalnızca nöral aktivite,
performans ve takip özellikleri tutulur. Kamera önizleme penceresi açılmaz.

`--track` olmadan da kamera nöral simülasyonu sürer. Takip kanalı nöral girdiyi değiştirmez.
Kaçınma/yakalama etiketi veya hazır ses tetikleyicisi yoktur.

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
- `/mcns/state`: `completed`, `interrupted` veya `error` metni; kapanışta gönderilir.

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
- `summary.json`: tamamlanma/hata durumu, spike toplamları, sessiz hücre oranı ve performans.

```sh
python -m unittest discover -s tests -v
python -m mcns run --source black --duration 5 --fast
python -m mcns run --source white --duration 5 --fast
python -m mcns run --source static --duration 5 --fast
python -m mcns run --source bar --duration 600
```

`--fast` yalnızca kontrollü uyaranlarda kullanılır; gerçek zaman testi sayılmaz.
Bellek RSS örnekleri tüm Python sürecini kapsar. `frame_age_ms`, OpenCV'nin kareyi
teslim ettiği andan OSC yayınına kadar yaşı ölçer; sensör, Max ve ses kartı dahil
uçtan uca gecikme değildir. Max'te işitsel doğrulama kullanıcıya aittir.

## Kaynaklar

- [MaleCNS verisi ve lisansı (CC-BY)](https://male-cns.janelia.org/download/).
- [Optik kolon koordinatlarının tanımı](https://github.com/reiserlab/male-drosophila-visual-system-connectome-code/blob/main/docs/coordinate-systems.md).
- [Shiu modelinin referans kodu](https://github.com/philshiu/Drosophila_brain_model/blob/main/model.py).
- [MediaPipe el takibi](https://developers.google.com/edge/mediapipe/solutions/vision/hand_landmarker/python) ve [yüz takibi](https://developers.google.com/edge/mediapipe/solutions/vision/face_landmarker/python).
