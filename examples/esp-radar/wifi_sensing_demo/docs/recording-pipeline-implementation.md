

# ADDENDUM WAJIB — ESP-IDF CSI COMPLIANCE DAN VALIDASI AKUISISI

Bagian ini melengkapi spesifikasi recording pipeline sebelumnya. Ketentuan ini harus dipenuhi sebelum implementasi dinyatakan selesai.

## A. Target dan referensi resmi

Gunakan konfigurasi proyek yang sebenarnya:

- Target perangkat utama: ESP32-WROOM-32 / ESP32 klasik.
- Framework: ESP-IDF versi yang benar-benar digunakan proyek.
- Acuan dokumentasi: ESP-IDF Programming Guide 5.5.x, dengan penyesuaian terhadap patch version aktual.
- Referensi implementasi: repositori resmi `espressif/esp-csi`, khususnya `examples/get-started/csi_recv_router`.

Jangan menggunakan struktur atau perilaku API ESP32-C5, C6, C61, S3, atau chip lainnya sebagai asumsi untuk ESP32-WROOM-32.

Periksa versi ESP-IDF aktual dari environment dan build configuration. Jangan mengasumsikan versi hanya dari dokumentasi atau nama folder proyek.

## B. Pisahkan field native dan field buatan aplikasi

Audit setiap kolom `frames.csv` dan identifikasi sumber nilainya.

Kelompok native ESP-IDF meliputi informasi dari:

- `wifi_csi_info_t`
- `wifi_pkt_rx_ctrl_t`
- `info->buf`
- `info->len`
- `info->first_word_invalid`
- `info->mac`
- `info->dmac`
- `info->rx_seq`

Kelompok aplikasi atau hasil perhitungan meliputi:

- `recording_id`
- `frame_sequence`
- `seq`
- `raw_len`
- `valid_len`
- `lltf_len`
- `ht_ltf_len`
- `stbc_ht_ltf_len`
- `data_type`
- `callback_timestamp_us`
- `host_receive_monotonic_ns`
- `dropped`
- `payload_ok`
- `raw_b64`
- `valid_b64`
- `agc_gain`
- `fft_gain`
- `rx_gain_compensation`

Jangan mengklaim suatu field sebagai field native ESP-IDF apabila sebenarnya dihitung atau ditambahkan oleh firmware.

Dokumentasikan sumber, satuan, perhitungan, dan semantik setiap field yang bukan field native.

## C. Keamanan callback CSI dan pengelolaan buffer

Ikuti ketentuan resmi ESP-IDF:

1. Callback CSI berjalan di Wi-Fi task.
2. Memori yang ditunjuk oleh data callback tidak boleh digunakan setelah callback selesai.
3. Jangan melakukan file I/O, Base64 encoding, JSON serialization, atau pemrosesan berat di callback.
4. Salin buffer CSI ke memory yang dimiliki aplikasi sebelum callback kembali.
5. Gunakan bounded queue atau ring buffer untuk meneruskan frame ke task pengolah.
6. Pisahkan callback acquisition, pemrosesan frame, dan transmisi data ke host.
7. Jika queue penuh, jangan menimpa frame lain secara diam-diam.
8. Hitung dan catat queue overflow secara eksplisit.
9. Jangan memblokir Wi-Fi task ketika storage atau host sedang lambat.

Pastikan ukuran queue mempertimbangkan frekuensi frame, panjang payload, dan durasi gangguan sementara pada task pengolah.

## D. Semantik raw dan valid payload

Dokumentasikan bahwa API native ESP32 menyediakan satu CSI buffer, yaitu `info->buf` dengan panjang `info->len`.

`raw_data` dan `valid_data` adalah representasi yang dibentuk oleh aplikasi, bukan dua buffer native terpisah dari API ESP-IDF.

Ketentuan:

- `raw_b64` harus merupakan salinan byte sumber yang tidak dimodifikasi.
- `valid_b64` harus dibentuk berdasarkan aturan pemilihan byte yang eksplisit.
- Catat aturan pemilihan LTF dan rentang byte yang digunakan.
- Pastikan `valid_b64` dapat ditelusuri kembali ke sumber `raw_b64`.
- Jangan memotong, mengubah urutan, atau menggabungkan payload tanpa aturan yang terdokumentasi.
- Bila posisi rentang yang dipilih dapat berubah per frame, pastikan informasi yang diperlukan untuk merekonstruksi rentang tersebut ikut tersimpan.

Pertahankan `first_word_invalid` sebagai flag sumber.

ESP-IDF mendefinisikan kondisi ini sebagai empat byte pertama CSI yang tidak valid karena keterbatasan hardware.

Pertahankan payload raw secara utuh. Jika valid payload mengecualikan byte yang tidak valid, lakukan berdasarkan offset sumber yang benar sebelum penggabungan rentang, bukan dengan memangkas dua pasangan I/Q pertama secara membabi buta dari hasil akhir.

Buktikan aturan ini melalui pengujian byte-level menggunakan frame nyata.

## E. Format CSI ESP32 klasik

Untuk ESP32-WROOM-32, ikuti format native ESP-IDF:

- Buffer CSI bertipe signed int8.
- Setiap subcarrier terdiri dari dua byte.
- Urutan komponen adalah imaginary kemudian real.
- Urutan LTF adalah LLTF, HT-LTF, lalu STBC-HT-LTF apabila tersedia.

Jangan melakukan konversi ke int16 tanpa dasar dari format sumber.

Jika `data_type=1` digunakan, buktikan bahwa data memang merupakan representasi int16 hasil transformasi yang disengaja dan dokumentasikan cara konversinya.

Jangan mencampurkan decoding int8 ESP32 klasik dengan decoding 12-bit/int16 pada target ESP32 yang berbeda.

## F. Konfigurasi CSI driver harus eksplisit

Audit penggunaan `esp_wifi_set_csi_config()`.

Jangan mengandalkan default driver tanpa pemeriksaan.

Perhatikan khususnya:

- `lltf_en`
- `htltf_en`
- `stbc_htltf2_en`
- `ltf_merge_en`
- `channel_filter_en`
- `manu_scale`
- `shift`
- `dump_ack_en`

Jika target penelitian adalah mempertahankan data CSI tanpa channel smoothing dan tanpa penggabungan LTF, gunakan konfigurasi yang sesuai, termasuk:

```c
.channel_filter_en = false,
.ltf_merge_en = false,
```

Namun, verifikasi terlebih dahulu konfigurasi yang sesuai dengan target ESP32-WROOM-32 dan metode pengambilan CSI melalui router.

Jangan mengaktifkan atau menonaktifkan jenis LTF secara sembarangan.

Tetapkan pilihan LTF secara eksplisit dan konsisten antar-recording.

Simpan konfigurasi CSI aktual ke `meta.json`, termasuk jenis LTF yang diaktifkan, filter, merge, scaling, dan shift.

Jika ada perubahan konfigurasi, jangan mencampurkan take dengan konfigurasi yang berbeda tanpa mencatat perbedaannya.

## G. Timestamp dan sinkronisasi clock

Pertahankan clock sumber sebagai domain terpisah:

1. `callback_timestamp_us`: waktu ketika aplikasi mengambil timestamp dari `esp_timer_get_time()`.
2. `rx_ctrl_timestamp_us`: waktu lokal penerimaan paket dari `rx_ctrl.timestamp`.
3. `host_receive_monotonic_ns`: waktu penerimaan di host/browser, jika benar-benar dikonversi ke satuan nanodetik.

Perhatian:

- `esp_timer_get_time()` menghasilkan mikrodetik sejak inisialisasi ESP Timer.
- `rx_ctrl.timestamp` merupakan timestamp lokal driver dalam mikrodetik.
- `rx_ctrl.timestamp` memiliki batasan akurasi terkait modem sleep dan light sleep.
- `performance.now()` menghasilkan milidetik relatif terhadap `performance.timeOrigin`, bukan nanodetik.
- Jika `performance.now()` dikonversi menjadi nanodetik, dokumentasikan konversinya dan jangan mengklaim resolusi aktual nanodetik.
- Jangan melakukan pengurangan timestamp dari dua clock berbeda tanpa prosedur sinkronisasi.

Jika anotasi dilakukan dari GUI host, simpan waktu relatif terhadap awal recording pada clock host.

Jika diperlukan korelasi dengan timestamp ESP32, implementasikan mekanisme anchor/sinkronisasi yang jelas dan simpan pasangan timestamp sumbernya.

Jangan menganggap timestamp instruksi GUI, timestamp klik anotasi, dan timestamp penerimaan CSI otomatis memiliki referensi waktu yang sama.

## H. Definisi dropped frame

`dropped` merupakan instrumentation yang didefinisikan oleh aplikasi, bukan field native `wifi_csi_info_t`.

Definisikan counter secara terpisah apabila tersedia:

- Callback CSI yang diterima.
- Frame yang berhasil masuk queue.
- Frame yang hilang akibat queue overflow.
- Frame yang gagal dikirim ke host.
- Frame yang diterima host.
- Frame yang gagal ditulis atau divalidasi.

Jangan menggabungkan seluruh kehilangan menjadi satu angka tanpa mengetahui sumbernya.

`dropped_delta` harus berasal dari perbedaan counter kumulatif yang memiliki definisi sama.

Gap pada `rx_seq` harus dianalisis terpisah dan tidak boleh otomatis dianggap sebagai queue overflow.

Simpan jumlah dan sumber kehilangan frame di metadata.

## I. Validasi sampling rate melalui router

Karena arsitektur menggunakan satu ESP32 dan router, pastikan frekuensi CSI ditentukan oleh proses pengiriman paket yang sebenarnya.

Jangan menganggap konfigurasi interval ping 10 ms otomatis menjamin tepat 100 frame per detik.

Lakukan pengukuran aktual menggunakan timestamp frame.

Simpan:

- Target interval pengiriman.
- Jumlah frame yang diterima.
- Interval antar-frame aktual.
- Rata-rata interval.
- Median interval.
- Variasi interval atau jitter.
- Jumlah interval yang menyimpang.
- Jumlah frame yang hilang berdasarkan counter yang tersedia.

Jangan mengubah timestamp atau melakukan resampling untuk membuat data terlihat memiliki sampling rate 100 Hz.

`csi_period_ms` harus jelas apakah merupakan target konfigurasi atau interval aktual. Jangan menggunakan satu field untuk kedua makna tersebut.

## J. Persyaratan audio yang diperbaiki

Untuk instruksi suara recording:

- Prioritaskan file audio lokal berbahasa Indonesia yang telah dipersiapkan.
- Gunakan Web Audio API untuk tone cue dan penjadwalan audio.
- Gunakan `speechSynthesis` hanya sebagai alternatif jika voice `id-ID` benar-benar tersedia dan sudah diuji.
- Jangan mengandalkan speech synthesis untuk timing yang harus presisi.
- Catat waktu instruksi dijadwalkan dan waktu pemutaran aktual.
- Pastikan tone cue tetap menjadi penanda batas fase.
- Hindari antrean speech yang terlambat atau tumpang tindih.
- Lakukan preflight audio sebelum recording dimulai.
- Uji secara nyata pada browser dan sistem operasi yang digunakan.

Semua instruksi suara harus tetap berjalan terpisah dari proses akuisisi CSI agar keterlambatan audio tidak menghentikan atau menggeser recording.

## K. Pengujian berbasis dokumentasi

Tambahkan pengujian untuk membuktikan:

1. Buffer callback disalin sebelum callback kembali.
2. Tidak ada pointer callback yang digunakan setelah callback selesai.
3. Buffer raw identik dengan sumber native.
4. Valid payload dapat direkonstruksi dari aturan pemilihan yang terdokumentasi.
5. Byte order sesuai dokumentasi ESP-IDF.
6. Signedness int8 benar.
7. `first_word_invalid` ditangani berdasarkan offset sumber.
8. Konfigurasi CSI yang aktif sesuai metadata.
9. Perbedaan clock tidak disamakan.
10. Queue overflow tercatat secara benar.
11. Sampling rate dilaporkan berdasarkan hasil pengukuran aktual.
12. Output akhir tetap tepat dua file.

Gunakan source code ESP-IDF dan contoh resmi ESP-CSI sebagai referensi implementasi. Apabila terdapat perbedaan antara contoh dan kebutuhan penelitian, dokumentasikan alasan teknis pemilihan konfigurasi.

Jangan mengklaim semua hasil sudah sesuai dokumentasi apabila pemeriksaan hanya dilakukan pada kode tanpa pengujian terhadap frame CSI aktual.


# Implementasi Ulang Recording Pipeline Wi-Fi CSI untuk Dataset Fall Detection

## 1. Tujuan utama

Lakukan audit dan implementasi menyeluruh terhadap fitur recording Wi-Fi CSI pada proyek ini agar menghasilkan pipeline pengumpulan dataset yang konsisten, terstruktur, akurat, dan dapat digunakan untuk berbagai eksperimen machine learning maupun deep learning.

Implementasi harus mencakup:

1. Penyederhanaan hasil recording menjadi tepat dua file utama untuk setiap take.
2. Penggunaan `frames.csv` sebagai sumber data CSI utama tanpa kehilangan informasi payload.
3. Penyusunan ulang `meta.json` dan penggabungan informasi event dari `events.json`.
4. Penghapusan dataset recording lama sesuai permintaan.
5. Implementasi delapan kategori aktivitas beserta variasi fase aktivitas.
6. Recording otomatis dengan durasi per-take (diturunkan dari boundary terakhir timeline).
7. Instruksi visual dan audio berbahasa Indonesia selama recording.
8. Penandaan waktu kejadian aktual secara manual.
9. Validasi integritas payload CSI, timestamp, frame, dan hasil recording.
10. Pengujian menyeluruh terhadap seluruh aktivitas dan variasi recording.

**Jangan hanya memberikan analisis, rekomendasi, atau rencana implementasi. Lakukan audit kode terlebih dahulu, kemudian implementasikan perubahan secara langsung.**

Jangan mengubah algoritma deteksi jatuh, proses training, atau fitur lain di luar kebutuhan recording pipeline, kecuali perubahan tersebut benar-benar diperlukan agar integrasi tetap berfungsi.

---

## 2. Tahap pertama: audit implementasi yang sudah ada

Sebelum mengubah kode, periksa struktur proyek dan telusuri seluruh alur recording yang sebenarnya.

Identifikasi:

- Komponen GUI recording.
- `csi_recorder.js` dan modul terkait.
- Proses penerimaan CSI dari ESP32.
- Proses decoding atau encoding Base64.
- Proses penulisan seluruh file CSV dan JSON.
- Pengelolaan timestamp dan sequence number.
- Implementasi activity preset dan timeline.
- Penanganan event dan anotasi.
- Pengelolaan durasi serta penghentian recording.
- Proses batch atau multiple take, jika tersedia.
- Sistem validasi kualitas recording.
- Seluruh referensi ke format file lama.
- Modul ekspor atau konversi dataset.

Telusuri pula apakah terdapat kode lain yang membaca `raw_iq.csv`, `csi_data.csv`, `iq.csv`, atau `events.json`.

Jangan menghapus fungsi yang masih diperlukan oleh komponen lain hanya karena file keluarannya tidak lagi digunakan secara otomatis.

Pastikan setiap ketergantungan yang terdampak ditangani dengan benar.

### Struktur hasil recording saat ini

Enam file yang benar-benar dihasilkan pada take v2:

1. `frames.csv`
2. `raw_iq.csv`
3. `csi_data.csv`
4. `iq.csv`
5. `meta.json`
6. `events.json`

`quality_report.json` tidak pernah dihasilkan pada take nyata sehingga jangan menganggapnya sebagai file dataset yang tersedia.

Untuk take v1, terdapat tiga jenis file lama, yaitu `csi_data.csv`, `iq.csv`, dan `meta.json`. Metadata v1 tidak memiliki struktur bersarang `acquisition`, `files`, `payload_semantics`, `pipeline_versions`, dan `schema_version` sebagaimana v2.

Jangan menganggap format v1 dan v2 identik.

---

## 3. Struktur output final: tepat dua file

Setiap take harus menghasilkan tepat dua file:

```text
<recording_id>.frames.csv
<recording_id>.meta.json
```

Contoh:

```text
20261029T191238Z_tes_recording_001.frames.csv
20261029T191238Z_tes_recording_001.meta.json
```

### Keputusan terhadap keenam file lama

| File | Tindakan |
|---|---|
| `frames.csv` | Pertahankan sebagai sumber utama |
| `raw_iq.csv` | Hentikan pembuatan otomatis |
| `csi_data.csv` | Hentikan pembuatan otomatis |
| `iq.csv` | Hentikan pembuatan otomatis |
| `meta.json` | Pertahankan dan susun ulang |
| `events.json` | Gabungkan informasinya ke `meta.json` |

Ketentuan:

- Jangan lagi membuat `raw_iq.csv`, `csi_data.csv`, `iq.csv`, dan `events.json` pada setiap recording.
- Jangan menyimpan file sementara atau file duplikat setelah recording selesai.
- Bersihkan file temporary apabila proses recording gagal atau dibatalkan.
- `meta.json` harus mencatat hanya dua file output utama yang memang tersedia.
- Jangan meninggalkan referensi ke file lama yang sudah tidak dibuat.
- Jangan menjalankan exporter legacy secara otomatis.
- Jika exporter legacy masih bermanfaat untuk kompatibilitas, boleh dipertahankan sebagai fungsi ekspor manual yang terpisah. Hasil ekspor tidak boleh masuk ke direktori utama take dan tidak boleh berjalan otomatis.

### Alasan

`frames.csv` sudah menyimpan raw dan valid payload dalam bentuk Base64. Informasi tersebut menjadi sumber untuk melakukan decoding dan preprocessing di kemudian hari.

Dengan demikian, representasi I/Q dan format kompatibilitas dapat dibuat kembali ketika diperlukan, tanpa perlu menyimpan seluruh duplikasi tersebut pada setiap recording.

---

## 4. Spesifikasi lengkap `frames.csv`

Gunakan `frames.csv` sebagai sumber data CSI utama dan otoritatif.

Header aktual yang diberikan memiliki **32 kolom**, bukan 31:

```csv
recording_id,frame_sequence,seq,rx_seq,mac,dmac,rssi,noise_floor,channel,secondary_channel,sig_mode,mcs,rate,bandwidth,stbc,data_type,raw_len,valid_len,lltf_len,ht_ltf_len,stbc_ht_ltf_len,first_word_invalid,agc_gain,fft_gain,rx_gain_compensation,callback_timestamp_us,rx_ctrl_timestamp_us,host_receive_monotonic_ns,dropped,payload_ok,raw_b64,valid_b64
```

Pertahankan seluruh kolom tersebut.

### 4.1 Identitas dan urutan frame

- `recording_id`
- `frame_sequence`
- `seq`
- `rx_seq`

Jangan menyamakan ketiga sequence number karena memiliki sumber dan makna berbeda.

`frame_sequence` harus menjadi indeks urutan frame dalam satu recording, dimulai dari 0 dan bertambah sesuai urutan frame yang diterima.

Jangan menganggap `seq` atau `rx_seq` harus selalu berurutan tanpa pengulangan.

### 4.2 Informasi paket dan Wi-Fi

Pertahankan:

- `mac`
- `dmac`
- `channel`
- `secondary_channel`
- `sig_mode`
- `mcs`
- `rate`
- `bandwidth`
- `stbc`

Informasi channel dan AP harus tetap tersedia baik pada level frame maupun metadata recording jika relevan.

### 4.3 Kualitas penerimaan

Pertahankan:

- `rssi`
- `noise_floor`
- `agc_gain`
- `fft_gain`
- `rx_gain_compensation`

Jangan membuang informasi penerimaan yang tersedia pada callback CSI.

### 4.4 Payload CSI

Pertahankan:

- `data_type`
- `raw_len`
- `valid_len`
- `lltf_len`
- `ht_ltf_len`
- `stbc_ht_ltf_len`
- `first_word_invalid`
- `raw_b64`
- `valid_b64`

`data_type`:
- `0`: int8.
- `1`: int16.

Pertahankan representasi raw dan valid secara terpisah.

Jangan melakukan operasi destruktif selama recording, termasuk:

- Pemotongan payload.
- Penghapusan subcarrier.
- Zero-padding.
- Smoothing.
- Normalisasi amplitudo.
- Filtering.
- Resampling.
- Transformasi FFT tambahan.
- Konversi ke representasi I/Q yang menggantikan payload asli.

Tujuannya adalah agar preprocessing dapat dilakukan kemudian sesuai kebutuhan masing-masing metode training.

**Perhatian khusus pada `first_word_invalid`:**

Jangan langsung menghapus dua pasangan I/Q pertama dari `valid_data` hanya karena flag `first_word_invalid` bernilai true.

Informasi first word pada raw driver buffer tidak otomatis berarti dua pasangan pertama dari buffer valid harus dihilangkan. Periksa implementasi firmware dan proses pembentukan valid payload sebelum melakukan transformasi apa pun.

### 4.5 Timestamp

Pertahankan tiga clock secara terpisah:

- `callback_timestamp_us`
- `rx_ctrl_timestamp_us`
- `host_receive_monotonic_ns`

Jangan menganggap ketiganya memiliki epoch, referensi waktu, atau satuan yang sama.

Gunakan clock monotonik untuk pengukuran durasi recording dan sinkronisasi timeline GUI.

Timestamp dari ketiga sumber harus disimpan sesuai nilai aslinya.

### 4.6 Integritas

Pertahankan:

- `dropped`
- `payload_ok`

Validasi `payload_ok` dengan membandingkan panjang byte hasil decoding Base64 dengan panjang payload yang sesuai:

- `raw_b64` terhadap `raw_len`.
- `valid_b64` terhadap `valid_len`.

Jangan membandingkan panjang string Base64 dengan `raw_len` atau `valid_len`, karena keduanya memiliki representasi dan satuan yang berbeda.

Catat anomali payload tanpa mengubah atau memperbaiki payload asli secara diam-diam.

---

## 5. Penyederhanaan file turunan

### 5.1 raw_iq.csv

Struktur lama:

```csv
frame_sequence,seq,source,data_type,subcarriers,iq
```

File ini mengandung dua baris per frame:

- `raw_data`
- `valid_data`

Data `iq` menggunakan urutan imaginary-first, dengan pasangan `imag|real`.

Hentikan pembuatan file ini secara otomatis karena datanya merupakan hasil decoding payload yang tersedia dalam `frames.csv`.

Pastikan proses decoding dapat dibuat kembali dari `raw_b64`, `valid_b64`, `data_type`, dan metadata panjang payload.

### 5.2 csi_data.csv

File ini merupakan format kompatibilitas v1 dengan 30 kolom.

Pada take v2, payload berisi payload terpilih, yaitu valid-diutamakan. Beberapa kolom legacy ditulis sebagai nilai 0 konstan, bukan hasil pengukuran.

Hentikan pembuatan otomatis file tersebut.

Jangan menjadikan `csi_data.csv` sumber utama untuk preprocessing maupun training dataset baru.

### 5.3 iq.csv

File ini memiliki 334 kolom:

- 6 kolom metadata.
- 164 subcarrier × 2 komponen I/Q.

Data menggunakan zero-padding jika frame lebih pendek dari maksimum take.

Nama kolom `_i` dan `_q` juga dipertahankan dengan konvensi yang berbeda dari byte-order dokumentasi.

Hentikan pembuatan otomatis file tersebut.

Jangan menerapkan zero-padding pada payload utama `frames.csv`.

### 5.4 Pengujian kesetaraan

Sebelum menghentikan generator file turunan, buat pengujian untuk memastikan informasi yang dibutuhkan dari `frames.csv` memang dapat di-decode kembali.

Bandingkan hasil decoding beberapa frame dengan hasil `raw_iq.csv` yang lama, memperhatikan:

- `data_type`.
- Byte order.
- Signedness.
- Urutan imaginary dan real.
- Jumlah pasangan I/Q.
- Perbedaan raw dan valid.
- Penanganan `first_word_invalid`.

Tujuannya bukan mempertahankan semua format lama, melainkan membuktikan bahwa payload sumber utama tidak kehilangan informasi yang dibutuhkan.

---

## 6. Struktur metadata baru: meta.json

Susun ulang metadata menjadi satu file yang konsisten, tidak redundan, dan mudah dibaca.

Gunakan `schema_version` sebagai versi skema metadata utama. Naikkan versi ketika perubahan struktur merupakan breaking change.

Jangan menghapus `schema_version` dengan alasan bahwa versi recorder atau pipeline tidak diperlukan lagi.

### 6.1 Informasi yang harus dipertahankan

- `schema_version`
- `recording_id`
- Waktu mulai dan selesai recording.
- Label aktivitas.
- Durasi target.
- Durasi aktual.
- Status recording.
- Informasi batch jika fitur batch masih digunakan.
- Jumlah frame.
- Informasi dropped frame.
- CSI period.
- Informasi Wi-Fi dan AP.
- Detail fase aktivitas yang dipilih.
- Timeline instruksi.
- Anotasi kejadian aktual.
- Informasi kualitas recording.
- Informasi audio cue.
- Informasi semantik payload yang diperlukan untuk decoding.

### 6.2 Field yang harus dihilangkan

Hapus field berikut sesuai kebutuhan desain sebelumnya:

- `trial_id`
- `firmware_target`

> **Koreksi (ACTION_PLAN 2.8):** `session_id` TIDAK jadi dihapus. Ia kini menjadi
> field wajib hasil keputusan user karena pemuat dataset
> (`fall_detection/dataset_io.py`) mengelompokkan take lewat `meta.session_id`
> (fallback `meta.batch_id`) dan validator memperingatkan bila keduanya kosong.
> `session_id` adalah **pengelompokan sesi fisik yang ditentukan operator**
> (hari / posisi / subjek) dan **bukan proksi `batch_id`** — lihat §8.2.

> **Koreksi (keputusan user, 2026-11-07):** `subject_id` juga TIDAK jadi dihapus.
> ACTION_PLAN 4.2 dan 3.3 mensyaratkan `subject_id` **terisi** sebelum klaim
> apa pun yang bersifat subject-split atau subject-independent, dan
> `dataset_io.py` membacanya lewat `Recording.subject_id` (`str | None`).
> Field ini kini tersedia di GUI recorder; **bila operator membiarkannya kosong,
> nilainya menjadi `"1"`** (subjek tunggal), bukan `null` — kosong berarti
> "subjek 1", bukan "tidak diketahui". Simpan sebagai string. Lihat §8.3.
- ESP32 chip revision.
- Firmware version/build ID.
- ESP-IDF version.
- esp-radar version.
- Recorder version sebagai field tersendiri.
- Room.
- ESP32 position.
- Router position.
- Device distance.
- Subject orientation.
- Experimental condition notes.

Jangan menghapus informasi Wi-Fi channel dan AP.

Hilangkan field lain yang terbukti duplikat, misalnya `id` apabila isinya selalu identik dengan `recording_id`.

Field `label` sebaiknya dikonsolidasikan menjadi `activity_label` agar lebih jelas.

`binary_label` dapat diperoleh dari pemetaan `activity_label`, sehingga tidak perlu menyimpan data redundan jika tidak ada kebutuhan khusus.

### 6.3 Field yang harus diperiksa sebelum dihapus

Jangan langsung menghapus:

- `batch_id`
- `take`
- `take_count`
- `gap_s`
- `motion_peer`
- `motion_samples[]`
- `acquisition`
- `payload_semantics`

Telusuri penggunaannya terlebih dahulu.

Field batch tetap dipertahankan apabila fitur batch masih digunakan. `motion_peer` dan `motion_samples[]` tetap dipertahankan apabila masih merupakan bagian dari pipeline eksperimen. Apabila tidak lagi digunakan, hapus dengan alasan teknis yang jelas.

### 6.4 Payload semantics

Pertahankan informasi yang diperlukan untuk menjelaskan:

- Representasi raw dan valid.
- Data type.
- Byte order.
- Semantik payload.
- Arti `first_word_invalid`.
- Cara decoding yang benar.

Hapus metadata yang hanya mendeskripsikan file turunan yang sudah dihentikan, seperti referensi ke `legacy_iq_csv` dan `raw_iq_rows`, selama tidak ada fungsi lain yang memerlukannya.

### 6.5 Struktur metadata yang disarankan

Gunakan struktur logis seperti berikut. Sesuaikan dengan arsitektur kode yang sudah ada tanpa mempertahankan field redundan.

```json
{
  "schema_version": 2,
  "recording_id": "20261029T191238Z_tes_recording_001",
  "activity_label": "fall_forward",
  "created_at_utc": "...",
  "started_at_utc": "...",
  "ended_at_utc": "...",
  "target_duration_s": 10,
  "actual_duration_s": 10,
  "status": "complete",

  "wifi": {
    "channel": 6,
    "secondary_channel": 0,
    "ap_mac": "...",
    "ap_information": {}
  },

  "acquisition": {
    "csi_period_ms": 10,
    "csi_period_note": "..."
  },

  "recording": {
    "gap_before_s": 5,
    "frames": 0,
    "dropped_on_device": 0,
    "dropped_delta": 0,
    "complete": true
  },

  "activity": {
    "pre_action": "still",
    "post_action": "still"
  },

  "timeline": [],

  "annotations": {
    "fall_start": null,
    "fall_impact": null,
    "annotation_complete": false
  },

  "audio_cues": {
    "enabled": true,
    "mode": "voice_and_tone",
    "language": "id-ID",
    "events": []
  },

  "quality": {},

  "payload_semantics": {},

  "events": {
    "segments": [],
    "motion_samples": []
  },

  "files": {
    "frames_csv": "...frames.csv",
    "meta_json": "...meta.json"
  }
}
```

Struktur tersebut merupakan rancangan, bukan kewajiban untuk menyalin secara persis. Prioritaskan konsistensi dengan kode yang sudah ada dan hindari menyimpan nilai yang tidak benar-benar tersedia.

---

## 7. Label aktivitas utama + jangkar idle

Gunakan delapan label kejadian berikut, ditambah tiga label jangkar idle (§9.6):

| Label | Kategori biner |
|---|---|
| `fall_forward` | fall |
| `fall_backward` | fall |
| `fall_lemas` | fall |
| `fall_keseleo` | fall |
| `walking` | non_fall |
| `fast_sitting` | non_fall |
| `bending` | non_fall |
| `object_drop` | non_fall |
| `empty_room` | non_fall (jangkar idle, §9.6) |
| `still_standing` | non_fall (jangkar idle, §9.6) |
| `still_sitting` | non_fall (jangkar idle, §9.6) |

Label yang digunakan selama recording harus konsisten dengan label yang disimpan pada metadata.

Jangan mengubah empat arah jatuh menjadi satu label aktivitas yang sama. Arah tetap dibutuhkan untuk analisis dataset meskipun keluaran akhir sistem deteksi hanya berupa `jatuh` atau `tidak jatuh`.

---

## 8. Recording otomatis dengan durasi per-take (turunan timeline)

Durasi take **diturunkan dari boundary terakhir `timeline` label** (default
10 s; **fall = 12 s** per keputusan ACTION_PLAN rev 2.6), bukan konstanta global
tetap. `CsiRecorder.durationFromTimeline(timeline)` memakainya untuk deadline
capture, progress bar, dan status timer.

Gunakan satu clock monotonik sebagai sumber waktu untuk seluruh proses:

- Waktu mulai capture.
- Perubahan fase.
- Countdown.
- Progress bar.
- Audio cue.
- Penandaan event aktual.
- Waktu penghentian recording.

Jangan menggunakan akumulasi `setInterval` atau penghitungan waktu berdasarkan jumlah callback timer.

Gunakan deadline berdasarkan waktu monotonik agar tidak terjadi pergeseran fase akibat keterlambatan event loop.

Durasi pengambilan CSI tidak boleh berubah karena suara atau animasi GUI.

Setelah durasi take tercapai (boundary terakhir timeline):

1. Hentikan penerimaan frame untuk recording tersebut secara terkontrol.
2. Flush seluruh buffer.
3. Selesaikan penulisan CSV.
4. Selesaikan penulisan metadata.
5. Validasi kedua file.
6. Bersihkan temporary file.
7. Tampilkan hasil dan status recording.

Durasi target adalah boundary terakhir timeline label tersebut (default 10 detik; fall 12 detik), sedangkan durasi aktual dicatat berdasarkan hasil pengukuran waktu monotonik. Jangan memalsukan durasi aktual menjadi nilai target jika proses terhenti lebih awal.

### 8.1 Gap sebagai pre-roll sebelum setiap take

Gap yang dikonfigurasi adalah **pre-roll yang berjalan sebelum setiap take, termasuk take pertama**, bukan hanya jeda antar take berikutnya. Tujuannya memberi operator waktu masuk posisi (atau mengosongkan ruangan untuk label `empty_room`) sebelum capture dibuka; tanpa pre-roll ini, take pertama selalu mulai tepat sesudah stream CSI dinyalakan dan operator belum siap.

Ketentuan:

- Hitungan mundur memakai clock yang sama dengan fase lain dan tidak mengubah durasi take (tetap boundary terakhir timeline label).
- Frame yang tiba selama pre-roll **tidak** masuk ke take; buffer frame di-reset pada awal setiap take.
- `gap = 0` berarti tidak ada pre-roll dan take langsung mulai.
- Besar pre-roll yang benar-benar dijalankan dicatat di `meta.recording.gap_before_s` untuk setiap take (batch maupun single), agar kondisi warm-up perangkat dapat direproduksi.
- Cancel selama pre-roll atau saat take berjalan **tidak** lagi menghentikan seluruh batch (ACTION_PLAN 2.8). Slot take yang dibatalkan dicatat di `meta.abort.aborted_slots` pada take yang masih tersimpan, lalu jadwal berlanjut ke slot berikutnya. Lihat §8.2.

### 8.2 Identitas batch, sesi, dan penomoran take monotonik

Tiga identitas yang berbeda disimpan pada metadata setiap take agar pemuat dataset
(`fall_detection/dataset_io.py`) dapat mengelompokkan take dengan benar.

**`batch_id` (wajib, otomatis per run).**
Dihasilkan setiap kali operator memulai satu run tangkap (batch maupun single) lewat
`CsiRecorder.makeBatchId()` dengan format `batch_<utcStamp>_<nonce6>`. Field ini selalu
ada, bahkan untuk satu take, sehingga setiap recording memiliki grup run yang eksplisit.
Disimpan di `meta.batch_id` (top-level) dan `meta.batch.batch_id`.

**`session_id` (kepunyaan operator, bukan proksi batch).**
Pengelompokan sesi fisik yang ditentukan operator — hari / posisi / subjek — dan
**bukan** sama dengan `batch_id`. Diambil dari input "Session ID" pada GUI; bila kosong
maka di-generate lewat `CsiRecorder.makeSessionId()` (`sess_<utcStamp>_<nonce6>`) dan
disimpan di `localStorage` (`csiRecorder.sessionId`) agar konsisten sepanjang sesi
perangkat. Disimpan di `meta.session_id` (top-level), yang dibaca duluan oleh properti
`Recording.session_id` (`meta.session_id` → fallback `meta.batch_id`).

**Nomor take monotonik lintas-restart.**
Suffix `_NNN` pada `recording_id` tidak dimulai ulang setiap reload halaman.
`computeNextTakeNumber` mengambil nilai awal dari dua sumber dan memakai maksimumnya:

- `CsiRecorder.nextTakeNumber(libraryEntries, label)` — maksimum nomor take yang ada di
  library untuk label itu (via `parseTakeNumber`), ditambah satu; dan
- penghitung di `localStorage` (`csiRecorder.takeCount.<label>`) untuk take yang belum
  tersimpan ke server.

`buildBatchSchedule({ takes, gapS, startTake })` menerima `startTake` ini sehingga slot
berikutnya bernomor `startTake, startTake+1, …`. `rememberTakeNumber` menulis balik
nomor tertinggi ke `localStorage` hanya bila lebih besar dari yang tersimpan.

**Jejak abort.**
Jika sebuah slot dibatalkan (cancel saat pre-roll atau saat take berjalan) atau
`take_begin` ditolak, loop batch memakai `continue` (bukan `break`) agar slot sisa tetap
dijadwalkan. Slot yang gagal dicatat di `csiRecorder.batchAborts` lalu ditulis ke
`meta.abort.aborted_slots` pada take berikutnya yang tersimpan. Take dengan nol frame
tidak dibuat (server menolaknya, dan §5 melarang memfabrikasi frame), sehingga jejak abort
hidup di metadata take yang tersisa, bukan sebagai file kosong.

### 8.3 Identitas subjek (`subject_id`)

`subject_id` menamai **orang yang melakukan take**, bukan hari/posisi (itu `session_id`)
dan bukan run tangkap (itu `batch_id`). ACTION_PLAN 4.2 menuntut **≥2 subjek × ≥2 sesi**
dan 3.3 menunda klaim subject-independent sampai `subject_id` terisi, sehingga field ini
**tidak boleh `null` pada rekaman baru**.

Ketentuan:

- Tersedia sebagai input terpisah di panel recorder ("Subject ID"), di samping Session ID.
- **Bila dibiarkan kosong, nilainya menjadi `"1"`** (`CsiRecorder.DEFAULT_SUBJECT_ID`),
  bukan `null`. Kosong berarti "subjek tunggal", bukan "tidak diketahui".
- Nilai disimpan sebagai **string** (`"1"`, `"2"`, `"S2"` boleh) karena
  `dataset_io.Recording.subject_id` bertipe `str | None`; spasi di tepi dipangkas.
- Nilai yang pernah diisi dipertahankan di `localStorage` (`csiRecorder.subjectId`)
  sehingga tidak perlu diketik ulang tiap reload. Bila field kosong, default efektif
  ditampilkan sebagai *placeholder* — kolomnya tetap kosong secara jujur sementara
  take yang dihasilkan tetap mendapat `"1"`.
- Rekaman lama yang tidak punya field ini tetap sah; `dataset_io` mengembalikannya
  sebagai `None` dan pemuat dataset memperlakukannya sebagai subjek tak dikenal
  (tidak dipakai untuk split per-subjek), bukan sebagai subjek `"1"`.

---

## 9. Timeline aktivitas dan instruksi visual

Peserta harus mengetahui tindakan yang perlu dilakukan pada setiap fase melalui GUI.

Variasi fase yang dapat dipilih harus ditentukan sebelum recording dimulai agar timeline tidak berubah secara acak saat proses berlangsung.

### 9.1 Fall detection

Durasi 12 detik (fall; boundary [0, 4, 8, 12]).

| Waktu | Fase | Instruksi |
|---|---|---|
| 0–4 detik | Pre-action | Diam atau berjalan, sesuai pilihan |
| 4–8 detik | Fall action | Jatuh (arah atau cara, sesuai label) |
| 8–12 detik | Post-action | Diam, merangkak, atau bergerak perlahan |

Empat kelas jatuh — dua berdasar arah, dua berdasar cara (manner):

- `fall_forward` — Jatuh ke depan (arah; pre-action diam).
- `fall_backward` — Jatuh ke belakang (arah; pre-action diam).
- `fall_lemas` — Jatuh lemas, collapse lunglai (manner; **pre-action diam**).
- `fall_keseleo` — Jatuh keseleo, collapse lateral terkontrol (manner;
  **pre-action berjalan** + post-action bergerak perlahan).

Pilihan sebelum recording:

`Pre-action`
- Diam.
- Berjalan.

`Post-action`
- Diam.
- Merangkak.
- Bergerak perlahan.

Arah jatuh juga harus dipilih sebelum recording.

### 9.2 Walking

| Waktu | Fase | Instruksi |
|---|---|---|
| 0–2 detik | Pre-action | Diam |
| 2–8 detik | Walking | Berjalan |
| 8–10 detik | Post-action | Berhenti dan diam |

### 9.3 Fast sitting

| Waktu | Fase | Instruksi |
|---|---|---|
| 0–4 detik | Pre-action | Diam atau berjalan |
| 4–6 detik | Action | Jongkok atau duduk cepat |
| 6–10 detik | Post-action | Diam |

Pilihan pre-action harus dibuat sebelum recording.

### 9.4 Bending

| Waktu | Fase | Instruksi |
|---|---|---|
| 0–3 detik | Pre-action | Diam atau berjalan |
| 3–7 detik | Action | Membungkuk lalu berdiri |
| 7–10 detik | Post-action | Diam atau berjalan |

Pilihan pre-action dan post-action dibuat sebelum recording.

### 9.5 Object drop

| Waktu | Fase | Instruksi |
|---|---|---|
| 0–4 detik | Pre-action | Diam atau berjalan |
| 4–6 detik | Action | Menjatuhkan benda |
| 6–10 detik | Post-action | Diam atau berjalan |

Pilihan pre-action dan post-action dibuat sebelum recording.

### 9.6 Label jangkar idle (empty_room, still_standing, still_sitting)

Label jangkar merekam kondisi tanpa kejadian: satu fase `hold` memanjang sepanjang
rekaman (batas `[0, 10]`), tanpa pilihan pre/post-action (UI menyembunyikannya), dan
tanpa cue di tengah take — hanya cue mulai dan cue selesai.

| Label | Instruksi seluruh take |
|---|---|
| `empty_room` | Ruangan kosong — tidak ada orang |
| `still_standing` | Berdiri diam sepanjang rekaman |
| `still_sitting` | Duduk diam sepanjang rekaman |

Fungsinya adalah lantai noise, normalisasi antar-sesi, dan referensi level
"manusia ada tetapi diam" untuk logika konfirmasi stillness. Kategori binernya
`non_fall`, tetapi saat training keduanya sebaiknya dipetakan ke kelas sendiri
(mis. `--class idle=still_standing,still_sitting`) agar tidak menjadi jalur pintas
klasifikasi fall/non_fall.

---

## 10. Implementasi instruksi suara selama recording

**Ini merupakan fitur penting dan wajib diimplementasikan, bukan fitur opsional yang boleh dilewatkan.**

Tujuannya adalah agar peserta dapat melakukan aktivitas berdasarkan instruksi yang didengar tanpa harus terus melihat layar laptop.

GUI harus memberikan instruksi visual dan audio yang tersinkronisasi.

### 10.1 Konsep sistem suara

Gunakan kombinasi dua jenis audio:

1. **Speech cue:** instruksi suara berbahasa Indonesia yang menyebutkan tindakan peserta.
2. **Tone cue:** bunyi pendek sebagai penanda pergantian fase, peringatan, dan akhir recording.

Contohnya:

- Nada pendek: fase baru dimulai.
- Instruksi suara: "Mulai berjalan."
- Nada khusus: fase tindakan jatuh dimulai.
- Instruksi suara: "Jatuh ke depan sekarang!"

Nada dan suara harus mempunyai pola yang konsisten agar mudah dikenali.

Jangan hanya membuat semua fase menggunakan beep yang sama tanpa instruksi suara. Peserta harus mengetahui tindakan apa yang harus dilakukan.

### 10.2 Teknologi audio

Periksa terlebih dahulu apakah proyek sudah memiliki sistem audio atau asset suara yang bisa digunakan.

Apabila belum ada, implementasikan dengan teknologi browser yang sesuai:

- Web Audio API untuk tone cue.
- Web Speech API `speechSynthesis` untuk instruksi suara berbahasa Indonesia, apabila tersedia dan kompatibel dengan browser.
- Preferensikan voice `id-ID`.
- Jangan mengandalkan layanan TTS eksternal atau API berbayar.
- Jangan membutuhkan koneksi internet untuk menghasilkan instruksi suara.
- Jangan menambahkan dependensi besar tanpa alasan teknis.

Jika proyek menggunakan mekanisme audio lokal yang lebih andal, utamakan mekanisme tersebut.

Tone harus menjadi penanda waktu yang cepat dan konsisten, sementara speech menjelaskan tindakan.

### 10.3 Ketepatan timing audio

Audio harus mengikuti clock monotonik dan timeline recording yang sama.

Ketentuan:

- Persiapkan AudioContext dan voice sebelum recording dimulai.
- Aktifkan audio melalui interaksi pengguna, misalnya tombol `Uji Suara`.
- Preload atau inisialisasi audio sebelum tombol mulai recording digunakan.
- Jangan menunggu speech selesai untuk berpindah fase.
- Jangan menunggu speech selesai untuk menghentikan capture.
- Jangan membiarkan antrean instruksi lama terus diputar setelah fase berikutnya dimulai.
- Jangan mengakumulasikan keterlambatan audio sebagai pergeseran timeline.
- Jika speech terlambat atau gagal, fase dan durasi recording tetap mengikuti clock utama.
- Gunakan penjadwalan Web Audio API untuk tone agar penanda waktu dapat dijadwalkan dengan lebih presisi.
- Trigger speech berdasarkan deadline fase yang sama.
- Batalkan atau tandai instruksi yang sudah kedaluwarsa agar peserta tidak mendengar perintah yang salah pada fase berikutnya.

Catat status setiap cue, termasuk apakah berhasil dipanggil, mulai diputar, selesai, gagal, atau terinterupsi.

### 10.4 Instruksi suara untuk setiap aktivitas

Gunakan kalimat singkat, jelas, dan mudah dipahami.

Implementasikan instruksi berikut sebagai default. Kalimat boleh disesuaikan sedikit untuk menghasilkan ucapan yang alami, tetapi makna dan waktunya harus dipertahankan.

#### A. Fall detection

Contoh untuk `fall_forward`, dengan pre-action diam dan post-action diam:

| Waktu | Instruksi suara |
|---|---|
| 0 detik | "Mulai. Tetap diam." |
| 4 detik | "Jatuh ke depan sekarang!" |
| 8 detik | "Selesai jatuh. Tetap diam." (post-action diam) |
| 12 detik | "Rekaman selesai." |

Kelas manner tidak memakai arah; cue-nya menyebut cara, didefinisikan penuh
di `FALL_ACTION_CUES`:

- "Jatuh ke belakang sekarang!"  (arah)
- "Jatuh lemas sekarang!"  (manner, `fall_lemas`)
- "Jatuh keseleo sekarang!"  (manner, `fall_keseleo`)

Jika pre-action adalah berjalan:

"Mulai. Berjalan seperti biasa."

Jika post-action adalah merangkak:

"Selesai jatuh. Mulai merangkak perlahan."

Jika post-action adalah bergerak perlahan:

"Selesai jatuh. Bergerak perlahan."

Jika post-action adalah diam:

"Selesai jatuh. Tetap diam."

#### B. Walking

| Waktu | Instruksi suara |
|---|---|
| 0 detik | "Mulai. Tetap diam." |
| 2 detik | "Mulai berjalan sekarang!" |
| 8 detik | "Berhenti berjalan. Tetap diam." |
| 10 detik | "Rekaman selesai." |

#### C. Fast sitting

Jika pre-action diam:

| Waktu | Instruksi suara |
|---|---|
| 0 detik | "Mulai. Tetap diam." |
| 4 detik | "Jongkok atau duduk cepat sekarang!" |
| 6 detik | "Selesai. Tetap diam." |
| 10 detik | "Rekaman selesai." |

Sesuaikan instruksi pre-action jika pilihan awal adalah berjalan.

#### D. Bending

| Waktu | Instruksi suara |
|---|---|
| 0 detik | "Mulai. [Instruksi pre-action]." |
| 3 detik | "Mulai membungkuk, lalu berdiri!" |
| 7 detik | "Kembali ke posisi awal." |
| 10 detik | "Rekaman selesai." |

#### E. Object drop

| Waktu | Instruksi suara |
|---|---|
| 0 detik | "Mulai. [Instruksi pre-action]." |
| 4 detik | "Jatuhkan benda sekarang!" |
| 6 detik | "Selesai. [Instruksi post-action]." |
| 10 detik | "Rekaman selesai." |

### 10.5 Antarmuka pengaturan suara

Sediakan kontrol suara pada halaman recording:

- Tombol `Uji Suara`.
- Kontrol volume.
- Indikator status audio.
- Status voice yang digunakan.
- Status audio cue aktif/nonaktif.
- Pilihan pengaktifan instruksi suara.

Default:

- Audio cue aktif.
- Speech dan tone aktif.
- Bahasa Indonesia.
- Voice `id-ID` apabila tersedia.

Saat pengguna membuka halaman recording, tampilkan cara menguji speaker sebelum memulai.

Jangan memulai recording dengan menganggap suara pasti berfungsi.

Jika browser tidak mendukung speech atau audio gagal dipersiapkan:

- Tampilkan peringatan yang jelas.
- Berikan informasi penyebab yang tersedia.
- Jangan diam-diam mengganti instruksi suara dengan beep.
- Sediakan pilihan mode visual-only dengan konfirmasi eksplisit jika diperlukan.
- Tandai kondisi tersebut sebagai deviasi protokol pada metadata.

Jangan memulai recording dalam mode audio wajib apabila audio belum berhasil diuji.

Pastikan pengguna mengetahui bahwa halaman recording harus tetap aktif di foreground agar timer dan pemutaran suara tidak terganggu oleh throttling browser.

### 10.6 Integrasi audio dengan metadata

Catat rencana instruksi dan hasil pemutaran dalam metadata.

Contoh:

```json
{
  "audio_cues": {
    "enabled": true,
    "mode": "voice_and_tone",
    "language": "id-ID",
    "voice": "...",
    "events": [
      {
        "cue_id": "start",
        "scheduled_offset_s": 0,
        "text": "Mulai. Tetap diam.",
        "status": "completed"
      },
      {
        "cue_id": "fall_forward",
        "scheduled_offset_s": 4,
        "text": "Jatuh ke depan sekarang!",
        "status": "completed"
      }
    ]
  }
}
```

Struktur tersebut adalah contoh. Gunakan nilai status yang benar berdasarkan event pemutaran aktual.

Bedakan dengan jelas:

- Waktu instruksi dijadwalkan.
- Waktu instruksi mulai diputar.
- Waktu instruksi selesai.
- Status pemutaran.

Jangan menganggap waktu instruksi sama dengan waktu kejadian aktivitas yang sebenarnya.

### 10.7 Instruksi suara tidak boleh menggantikan anotasi aktual

Instruksi:

"Jatuh ke depan sekarang!"

hanyalah perintah yang dijadwalkan pada detik ke-4.

Itu bukan bukti bahwa peserta benar-benar mulai jatuh pada detik ke-4.

Waktu kejadian aktual tetap harus diperoleh melalui tombol penandaan manual.

Simpan timeline instruksi dan anotasi kejadian aktual secara terpisah.

---

## 11. Penandaan kejadian aktual

Sediakan dua tombol besar selama recording untuk aktivitas jatuh:

1. `TANDAI AWAL JATUH`
2. `TANDAI BENTURAN`

Saat ditekan, simpan waktu aktual berdasarkan clock monotonik relatif terhadap waktu mulai capture.

Simpan juga timestamp UTC jika diperlukan untuk audit.

Ketentuannya:

- Tombol hanya aktif selama recording berlangsung.
- Simpan waktu klik pertama yang valid untuk masing-masing event.
- Hindari pengisian timestamp secara otomatis berdasarkan jadwal instruksi.
- Jangan membuat waktu kejadian palsu apabila peserta tidak menekan tombol.
- Cegah penandaan ganda yang tidak disengaja atau sediakan mekanisme koreksi yang jelas.
- Simpan status kelengkapan anotasi.

Contoh:

```json
{
  "annotations": {
    "fall_start": {
      "offset_s": 4.37,
      "timestamp_utc": "..."
    },
    "fall_impact": {
      "offset_s": 5.12,
      "timestamp_utc": "..."
    },
    "annotation_complete": true
  }
}
```

Jika tombol tidak ditekan:

```json
{
  "annotations": {
    "fall_start": null,
    "fall_impact": null,
    "annotation_complete": false
  }
}
```

Untuk aktivitas non-fall, tombol penandaan jatuh tidak perlu diaktifkan.

---

## 12. Desain GUI recording

Buat antarmuka yang jelas, fokus pada instruksi aktivitas, serta mudah dipahami peserta.

Minimal tampilkan:

### Sebelum recording

- Pilihan delapan aktivitas.
- Pilihan arah jatuh jika aktivitas fall.
- Pilihan pre-action dan post-action.
- Informasi durasi 10 detik.
- Status koneksi ESP32.
- Status penerimaan CSI.
- Status audio.
- Tombol uji suara.
- Tombol mulai recording.

### Selama recording

Elemen penting yang harus terlihat:

- Label aktivitas.
- Instruksi fase saat ini dalam ukuran besar.
- Countdown.
- Progress bar 10 detik.
- Indikator `REC`.
- Status penerimaan CSI.
- Indikator koneksi ESP32.
- Indikator audio cue.
- Tombol penandaan awal jatuh dan benturan ketika aktivitas fall.
- Informasi perubahan fase.

Instruksi visual harus berubah bersamaan dengan perubahan fase audio.

Contoh:

<pre>
REC                         00:04 / 00:10

        JATUH KE DEPAN SEKARANG!

        FASE: FALL ACTION

        [==========----------]

CSI RECEIVING: ACTIVE
ESP32: CONNECTED
AUDIO: ACTIVE

[TANDAI AWAL JATUH] [TANDAI BENTURAN]
</pre>

### Setelah recording

Tampilkan:

- Recording berhasil atau tidak.
- Durasi aktual.
- Jumlah frame diterima.
- Jumlah dropped frame.
- Status integritas payload.
- Status anotasi.
- Status audio cue.
- Nama dua file hasil recording.
- Informasi kualitas atau peringatan jika ada.

Jangan menampilkan recording yang tidak lengkap sebagai recording berhasil.

---

## 13. Alur recording lengkap

Implementasikan lifecycle berikut:

```text
PILIH AKTIVITAS
       |
PILIH VARIASI FASE
       |
PERIKSA KONEKSI ESP32
       |
UJI DAN PERSIAPKAN AUDIO
       |
VALIDASI KONFIGURASI
       |
MULAI RECORDING
       |
MULAI CLOCK MONOTONIK
       |
RECORD CSI + TIMELINE GUI + AUDIO CUE
       |
PENANDAAN EVENT AKTUAL
       |
DURASI 10 DETIK TERCAPAI
       |
HENTIKAN CAPTURE
       |
FLUSH SELURUH BUFFER
       |
TULIS FRAMES.CSV
       |
TULIS META.JSON
       |
VALIDASI KEDUA FILE
       |
BERSIHKAN TEMPORARY FILE
       |
TAMPILKAN HASIL RECORDING
```

Tangani kondisi berikut:

- ESP32 terputus.
- Penerimaan CSI berhenti.
- Tidak ada frame yang diterima.
- Payload rusak.
- Terjadi dropped frame.
- Browser kehilangan koneksi.
- Audio gagal.
- Recording dihentikan pengguna.
- Penulisan file gagal.
- Halaman ditutup atau reload saat recording.
- Buffer tidak berhasil di-flush.

Setiap kondisi tersebut harus menghasilkan status dan metadata yang akurat. Jangan menganggap file berhasil hanya karena file sudah terbentuk.

### 13.1 Jalur penyimpanan dan fallback unduhan

Sasaran utama selalu `POST /api/recordings` ke `csi_recorder_server.py`. Server
memeriksa kontrak dua file sebelum menulis apa pun dan menolak take tanpa baris
frame (`frames.csv has no data rows`, HTTP 400) supaya tidak ada artefak parsial.

- POST gagal dan take berisi frame: browser mengunduh file yang sama
  (`*.frames.csv` + `*.meta.json`) agar tidak ada take yang hilang diam-diam.
  Unduhan ganda memicu izin "automatic downloads" di browser; itu konsekuensi
  yang diterima demi menyelamatkan data.
- POST gagal dan frame nol: fallback unduhan **dilewati**. CSV header-only tidak
  menyelamatkan apa pun, hanya meninggalkan sampah di folder unduhan, dan tetap
  memicu prompt tanpa manfaat. Yang dicatat hanya kegagalan beserta alasan dari
  server (`saved: "failed"`), sehingga operator tahu take itu harus diulang.

Pesan kegagalan harus menyertakan alasan validasi dari body respons server; HTTP
status saja ("HTTP 400") menyembunyikan penyebab sebenarnya.

---

## 14. Penghapusan dataset recording lama

Dataset recording lama harus dihapus seluruhnya, tanpa migrasi dan tanpa backup, sesuai kebutuhan proyek.

Dataset lama yang dimaksud mencakup recording v1 dan v2 beserta file turunan yang menjadi bagian dari dataset tersebut.

Ketentuan penting:

1. Identifikasi direktori dataset dari konfigurasi dan implementasi aktual.
2. Pastikan lokasi yang dihapus benar-benar merupakan direktori data recording.
3. Hapus seluruh take lama dan file turunannya.
4. Jangan menghapus source code, konfigurasi, firmware, test, dokumentasi, atau aset aplikasi.
5. Jangan menggunakan wildcard global seperti menghapus seluruh file `.csv` atau `.json` dalam proyek.
6. Jangan menghapus direktori lain yang kebetulan memiliki nama serupa.
7. Jangan membuat salinan atau migrasi dataset lama.
8. Setelah penghapusan, laporkan jumlah recording dan file yang dihapus serta lokasi yang dibersihkan.

Jangan mengasumsikan jumlah aktual berdasarkan perkiraan. Temukan jumlahnya dari filesystem.

---

## 15. Kompatibilitas dan kebersihan implementasi

Pastikan perubahan tidak meninggalkan dependensi yang rusak.

Periksa:

- Seluruh referensi GUI ke format lama.
- Modul pembaca metadata.
- Modul visualisasi CSI.
- Sistem batch recording.
- Sistem penamaan file.
- API atau event handler.
- Fungsi ekspor.
- Proses pembersihan temporary file.
- Pengelolaan status recording.

Jika ada komponen internal yang sebelumnya membaca `events.json`, ubah agar membaca data event dari `meta.json`.

Jangan mempertahankan dua sumber metadata terpisah.

Gunakan satu sumber metadata utama.

---

## 16. Pengujian wajib

Implementasikan automated test atau pengujian yang sesuai dengan arsitektur proyek.

### A. Pengujian file output

- Recording berhasil menghasilkan tepat dua file.
- Nama file sesuai `recording_id`.
- Tidak ada file `.raw_iq.csv`.
- Tidak ada file `.csi_data.csv`.
- Tidak ada file `.iq.csv`.
- Tidak ada file `.events.json`.
- Tidak ada temporary file yang tertinggal.
- `meta.json` merujuk ke dua file yang benar-benar ada.

### B. Pengujian header dan payload CSI

- Header `frames.csv` memiliki tepat 32 kolom.
- Semua kolom wajib tersedia.
- Base64 dapat di-decode.
- Panjang byte raw sesuai `raw_len`.
- Panjang byte valid sesuai `valid_len`.
- `data_type` diproses dengan benar.
- Byte order benar.
- Raw dan valid tetap terpisah.
- `frame_sequence` dimulai dari 0.
- Tidak ada perubahan payload yang tidak diminta.
- Field timestamp tetap terpisah.
- Informasi dropped frame tercatat dengan benar.

### C. Pengujian metadata

- `schema_version` tersedia.
- `recording_id` konsisten.
- `activity_label` benar.
- `target_duration_s` diturunkan dari boundary terakhir `timeline` (10 s untuk
  mayoritas label; **12 s untuk fall**), bukan konstanta global tetap.
- `actual_duration_s` berasal dari pengukuran aktual.
- Status recording akurat.
- Informasi Wi-Fi dan AP tetap tersedia.
- `payload_semantics` tersedia.
- Tidak ada referensi file legacy yang tidak dibuat.
- Tidak ada field redundan yang sengaja dihapus.
- Event terintegrasi dalam `meta.json`.

### D. Pengujian aktivitas

Uji seluruh delapan label:

- `fall_forward`
- `fall_backward`
- `fall_lemas`
- `fall_keseleo`
- `walking`
- `fast_sitting`
- `bending`
- `object_drop`

Uji seluruh pilihan pre-action dan post-action.

Pastikan instruksi fase, label, dan metadata selalu konsisten.

### E. Pengujian timeline

Periksa setiap batas fase:

- Fall: 0, 4, 8, 12 detik (take 12 s per keputusan ACTION_PLAN rev 2.6).
- Walking: 0, 3, 7, 10 detik.
- Fast sitting: 0, 4, 6, 10 detik.
- Bending: 0, 3, 7, 10 detik.
- Object drop: 0, 4, 6, 10 detik.
- Jangkar idle (empty_room, still_standing, still_sitting): 0, 10 detik (satu fase).

Pastikan durasi take mengikuti boundary terakhir timeline label (fall 12 s, lainnya 10 s) dan keterlambatan callback GUI tidak menyebabkan akumulasi pergeseran waktu.

### F. Pengujian audio

Ini wajib diuji, bukan hanya memastikan kode audio tersedia.

- Tombol `Uji Suara` berfungsi.
- Voice bahasa Indonesia digunakan apabila tersedia.
- Tone cue terdengar.
- Instruksi speech sesuai aktivitas.
- Instruksi sesuai fase dan pilihan variasi.
- Suara mulai pada batas fase yang benar.
- Suara tidak saling bertumpuk atau tertinggal.
- Audio gagal menghasilkan peringatan.
- Mode tanpa audio harus dicatat sebagai deviasi.
- Penghentian recording tidak menunggu speech selesai.
- Penyelesaian audio tidak mengubah durasi capture.
- Status cue terekam dalam metadata.

Uji setidaknya satu recording untuk setiap jenis aktivitas dan setiap variasi arah jatuh.

### G. Pengujian anotasi

- Tombol awal jatuh mencatat offset aktual.
- Tombol benturan mencatat offset aktual.
- Kedua tombol tidak mengisi timestamp secara otomatis.
- Timestamp tidak dibuat jika pengguna tidak menekan tombol.
- Anotasi tidak lengkap ditandai dengan benar.
- Event aktual tidak tertukar dengan jadwal instruksi suara.

### H. Pengujian kegagalan

- ESP32 terputus.
- Frame tidak diterima.
- Payload tidak valid.
- Audio tidak tersedia.
- Penyimpanan gagal.
- Recording dihentikan sebelum 10 detik.
- Browser mengalami gangguan.

Pastikan tidak ada recording gagal yang dilabeli `complete`.

### I. Pengujian batch dan gap

- Jumlah slot jadwal sama dengan jumlah take yang diminta.
- Setiap slot membawa pre-roll sebesar gap yang dikonfigurasi, **termasuk slot
  pertama** (`takes=3, gap=5` → tiga slot, semuanya `pre_roll_s=5`).
- Batch satu take tetap mendapat pre-roll (`takes=1, gap=8` → `pre_roll_s=8`).
- `gap=0` menghasilkan `pre_roll_s=0` pada semua slot.
- Konfigurasi tidak valid (take > 100, gap < 0 atau > 60) menghasilkan `null`
  dan sesi tidak dimulai.
- `meta.recording.gap_before_s` terisi untuk take batch maupun single.
- Pre-roll tidak menambah durasi take: tetap tepat 10 detik.
- Hitungan mundur memakai clock monotonik yang sama dengan fase lain, bukan
  `Date.now()`.

---

## 17. Kriteria penerimaan akhir

Implementasi dinyatakan selesai apabila seluruh kriteria berikut terpenuhi:

1. Setiap take menghasilkan tepat dua file utama.
2. `frames.csv` menyimpan seluruh informasi CSI yang diperlukan.
3. Raw dan valid payload tidak mengalami transformasi destruktif.
4. Metadata tersusun ulang dengan benar.
5. Informasi event sudah tergabung dalam `meta.json`.
6. Field yang redundan atau tidak diperlukan sudah dihilangkan sesuai spesifikasi.
7. Dataset recording lama sudah dihapus dengan aman.
8. Seluruh delapan aktivitas tersedia.
9. Seluruh variasi fase dapat dipilih sebelum recording.
10. Durasi setiap recording sesuai boundary terakhir timeline label (fall 12 s, lainnya 10 s).
11. Instruksi visual berubah sesuai timeline.
12. Instruksi suara berbahasa Indonesia berjalan pada pergantian fase.
13. Tone cue dan speech cue tersinkronisasi dengan timeline.
14. Penandaan awal jatuh dan benturan merekam waktu aktual.
15. Kegagalan recording dan audio ditangani secara eksplisit.
16. Hanya recording yang valid yang ditampilkan sebagai berhasil.
17. Tidak ada file sementara atau file legacy yang dibuat otomatis.
18. Seluruh pengujian wajib berhasil atau kegagalannya dijelaskan secara spesifik.

---

## 18. Prioritas implementasi

Kerjakan berdasarkan urutan berikut:

**Prioritas 1 — Data integrity**
- Audit alur CSI.
- Pertahankan seluruh informasi `frames.csv`.
- Pastikan raw dan valid payload dapat di-decode.
- Hentikan ketergantungan terhadap file turunan.

**Prioritas 2 — Metadata dan output**
- Susun ulang `meta.json`.
- Gabungkan event.
- Terapkan dua file output.
- Hapus dataset lama dengan aman.

**Prioritas 3 — Recording lifecycle**
- Terapkan durasi per-take dari boundary terakhir timeline (fall 12 s, lainnya 10 s).
- Sinkronkan timeline dengan clock monotonik.
- Tangani buffer dan kondisi kegagalan.

**Prioritas 4 — GUI dan instruksi aktivitas**
- Implementasikan delapan label.
- Implementasikan variasi fase.
- Implementasikan visual instruction.

**Prioritas 5 — Audio cue**
- Implementasikan instruksi speech berbahasa Indonesia.
- Implementasikan tone cue.
- Tambahkan uji audio dan indikator status.
- Sinkronkan audio dengan timeline.
- Simpan riwayat cue dalam metadata.

**Prioritas 6 — Anotasi dan validasi**
- Implementasikan penandaan awal jatuh dan benturan.
- Jalankan seluruh pengujian.
- Periksa hasil recording aktual.

Semua prioritas merupakan bagian dari implementasi akhir. Jangan menghentikan pekerjaan setelah menyelesaikan audit atau prioritas pertama.

---

## 19. Laporan hasil implementasi

Setelah selesai, berikan laporan teknis yang mencakup:

1. Ringkasan perubahan.
2. File source code yang diubah, ditambahkan, dan dihapus.
3. Penjelasan alur recording baru.
4. Struktur dua file output.
5. Struktur metadata baru.
6. Penjelasan sistem audio cue dan sinkronisasinya.
7. Daftar variasi aktivitas yang sudah diuji.
8. Dataset lama yang dihapus dan jumlah file/take.
9. Hasil pengujian integritas CSI.
10. Hasil pengujian audio.
11. Hasil seluruh automated test.
12. Masalah yang belum terselesaikan, jika ada.

Jangan mengklaim pengujian berhasil apabila hanya memeriksa kode tanpa menjalankannya.

Jangan mengklaim audio berfungsi hanya karena API berhasil dipanggil. Lakukan pengujian playback pada lingkungan yang tersedia dan laporkan keterbatasannya.

**Target akhir:** fitur recording yang menghasilkan dataset Wi-Fi CSI berkualitas tinggi, mempertahankan payload mentah secara utuh, memiliki anotasi aktivitas yang jelas, memberikan instruksi visual dan suara secara terkoordinasi, serta menghasilkan tepat dua file per recording yang siap digunakan untuk berbagai proses preprocessing dan training selanjutnya.

