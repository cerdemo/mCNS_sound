# Wiring üzerinden dönüş araştırması — 25 Eylül 2026

Doğal uçuş henüz doğrulanmadı. Bu çalışma canlı widget’ın hareketini değiştirmedi;
varsayılan `bilateral-v1` modeli ve OSC akışı korunuyor. Yeni deneysel model canlı
çalıştırıcıya bağlanmadı. Ek rastgele dönüşlerle eksik nöral yanıt örtülmedi.

## Saptanan eksikler

İlk seçilmiş devre, DNa02 hücrelerinin tam veri setindeki gelen sinaps ağırlığının
yalnızca yaklaşık %10,6–15,8’ini içeriyordu. DNg02 ailesinin 29 hücresi seçime dahil
değildi. DNa02’ye doğrudan tanısal akım verilince ateşleme oluşması, sessizliğin
yalnızca çıktı okuyucusundan kaynaklanmadığını gösterdi.

DNa02’yi tek bir genel uçuş yönü kanalı olarak yorumlamak yeterli değildir.
[DNg02 araştırması](https://pubmed.ncbi.nlm.nih.gov/35090590/) uçuşta kanat genliği
kontrolünü; [karşılaştırmalı DN çalışması](https://www.nature.com/articles/s41586-025-08925-z)
ise farklı motor bağlantılarını incelemek için dayanak sağlar. Bu bulgular mevcut
simülasyondaki parametreleri doğrulamaz.

`configs/flight-audit.json` ile hazırlanan genişletilmiş devre 14.206 gerçek hücre ve
609.432 anatomik bağlantı içerir; 606.414 bağlantı kullanılan nörotransmiter işaret
modelinde sıfır dışıdır. Her iki taraftaki DNg02 hücreleri ve daha geniş upstream
seçimi dahil edildi. DNa02 gelen ağırlık kapsamı yaklaşık %43,6–44,6’ya çıktı.
Bu hâlâ kesilmiş bir alt-devredir; tam CNS değildir, yeni veya aynalanmış nöron yoktur.

## Kontrollü deneyler

- Orijinal LIF fizyolojisiyle genişletilmiş devre, sabit beyaz sağ göz girdisine
  DNa02 yanıtı verdi. Ancak eşit ortalama parlaklıkta ters yönlü ızgaralarla DNa02
  ve DNg02 sessiz kaldı. Test edilen tekil T4/T5 hücrelerinde de 1 Hz yanıt eşiği
  aşılmadı.
- Global sinaptik kazancı artırmak bazı DN yanıtlarını açtı; yüksek kazanç bazı
  hücreleri modelin ateşleme tavanına taşıdı. Bu ayarlar canlı modele uygulanmadı.
- `mcns/hybrid.py` görsel hücreler için dereceli salım, merkezi hücreler için LIF
  kullanan ayrı bir hipotezdir. Bağlantı kimlikleri ve işaretleri korunur; görsel
  hedef satırları normalize edildiğinden mutlak etkin ağırlıklar orijinal LIF ile
  aynı değildir. Öğrenme veya yeni bağlantı yoktur.

Hibrit modelde DN yanıtı oluştu ve bağlantılar kapatılınca kayboldu. Buna rağmen
iki gözde ters hareket yönleri karşıt DNg02 sağ-sol farkı üretmedi; bazı merkezi
hücreler yaklaşık 333,5 Hz ile modelin tavanında kaldı. `eligible_for_runtime=false`.
300 Hz tarama sınırı bu model için bir doygunluk kontrolüdür, tüm biyolojik hücreler
için evrensel bir hız sınırı değildir. Testleri geçmek de tek başına biyolojik
geçerlilik anlamına gelmez.

[Flyvis çalışması](https://www.nature.com/articles/s41586-024-07939-3) dereceli görsel
dinamikler için yöntemsel bir referanstır. Burada Flyvis’in eğitilmiş parametreleri
kullanılmıyor. Hücre sınıfına göre dereceli/spiking ayrımı, zaman sabitleri, bazal
salım ve salım-akım dönüşümü kalibre edilmemiş varsayımlardır. Bu nedenle sonuç
“wiring doğal uçuş üretti” olarak sunulamaz. Sonraki bilimsel gereksinim, hücre tipi
fizyolojisi ve retinotopiyi doğrulayıp önce görsel yön seçiciliğini elde etmektir.

## Tekrar çalıştırma

Proje kökünde, mevcut veri dosyaları ve `.mcns` ortamıyla:

```sh
.mcns/bin/python -m mcns prepare --config configs/flight-audit.json --graph build/flight-audit-v1
.mcns/bin/python scripts/audit_steering.py --graph build/flight-audit-v1 --config configs/flight-audit.json --output build/flight-audit-v1/steering-audit.json
.mcns/bin/python scripts/probe_physiology.py
.mcns/bin/python scripts/validate_direction.py
.mcns/bin/python scripts/validate_hybrid.py
.mcns/bin/python -m unittest discover -s tests -v
node tests/test_widget.js
```

Sayısal raporlar `build/flight-audit-v1/` altında `steering-audit.json`,
`physiology-probes.json`, `direction-validation.json`, `hybrid-validation.json`
olarak bulunur. `build/` üretilmiş çıktı olarak Git dışında tutulur; deney kodları
ve config dosyaları sonuçları tekrar üretmek içindir. Hibrit rapor config, kod ve
grafik kimliklerini, ayrı salım/Hz ölçümlerini ve başarısız tarama kriterlerini içerir.

Doğrulama: 26 Python testi ve JavaScript widget testleri geçti. Bunlar yazılımın
işleyişini sınar; başarısız görsel yön seçiciliği deneyinin yerine geçmez.
