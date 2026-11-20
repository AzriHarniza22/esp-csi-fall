# Plan Integrasi Linear SVM Experiment B ke ESP32

Tanggal riset: 2026-11-14
Status: integrasi kode selesai; build ESP-IDF v5.5.3 lulus; parity CSI-ke-fitur diverifikasi
Target: ESP32-WROOM-32 / NodeMCU-32S, ESP-IDF v5.5.3
Artifact kandidat: `final_model_experiment_B.json`

> Status lanjutan 2026-11-15: Experiment B di bawah ini adalah catatan
> integrasi historis. Source firmware kandidat sekarang menggunakan model
> full-fit berbasis anotasi fase dan stabilisasi label, bukan artifact
> Experiment B. Hasil OOF, provenance, build, dan batasan model fase dicatat di
> [PHASE_AWARE_TRAINING.md](./PHASE_AWARE_TRAINING.md). Model belum di-flash.

## 1. Keputusan dan rekomendasi

Untuk memakai artifact Experiment B yang ada, jalur firmware harus menghasilkan
16 fitur dari **representasi LLTF 51-pasangan yang sama dengan training**, bukan
memasukkan pasangan ke-52 dengan padding/interpolasi atau memakai pembagian band
52-pasangan.

Gate pemetaan Fase 0 telah lulus; kontrak implementasi yang dipakai:

1. Mekanisme yang dapat menghasilkan perbedaan lebar teridentifikasi:
   compaction `esp-radar` membuang satu pasangan int8 saat rentang LLTF
   menyentuh byte raw 0–3 dan `first_word_invalid` aktif. Hasilnya LLTF
   filtered 102 byte/51 pasangan. Snapshot/cache yang tersedia juga
   menunjukkan input benchmark berlebar 51; raw recording tidak ada di
   checkout ini, jadi hubungan setiap baris training ke payload sumber tidak
   dapat diperiksa ulang sekarang.
2. Artifact final dilatih dari feature cache yang semua take-nya memiliki lebar
   51, dengan band assignment `floor(index * 16 / 51)`.
3. Dokumentasi ESP-IDF v5.5.3 dan rentang byte `esp-radar` 0.3.4 memetakan
   urutan hasil filter: Layout A `-26..-1,+2..+26`. Training membaca
   `valid_data` yang sama dari `frames.csv`; audit snapshot mencatat seluruh
   130 take berlebar 51. Jadi gate representasi lulus. Raw recording tidak ada
   untuk membandingkan ulang setiap payload historis byte-per-byte, dan batas
   provenance ini tidak diubah menjadi klaim pengukuran hardware.

Jangan memakai model fold atau prediksi OOF sebagai model final. Jika kelak
berubah aturan compaction, indeks subcarrier, urutan fitur, atau format payload,
model ini tidak boleh dipakai tanpa audit kompatibilitas dan persetujuan untuk
refit final baru.

## 2. Bukti riset

### Dokumentasi resmi ESP-IDF

Sumber versi yang tepat untuk proyek:

- ESP-IDF v5.5.3 lokal:
  `/home/azri/.espressif/v5.5.3/esp-idf/docs/en/api-guides/wifi.rst`,
  bagian Wi-Fi Channel State Information, baris 2717–2745.
- URL versi eksplisit:
  <https://docs.espressif.com/projects/esp-idf/en/v5.5.3/esp32/api-guides/wifi.html#wi-fi-channel-state-information>
- Definisi field terpasang:
  `/home/azri/.espressif/v5.5.3/esp-idf/components/esp_wifi/include/local/esp_wifi_types_native.h`,
  `wifi_csi_info_t.first_word_invalid`.

Kutipan ESP-IDF v5.5.3:

> “If first_word_invalid field of wifi_csi_info_t is true, it means that the
> first four bytes of CSI data is invalid due to a hardware limitation”

Dokumen juga menyatakan tiap sampel subcarrier terdiri dari dua signed bytes,
imaginary lalu real; urutan item mengikuti tabel subcarrier; urutan LTF adalah
LLTF, HT-LTF, STBC-HT-LTF. Dokumentasi tersebut **tidak** menyatakan bahwa
`first_word_invalid` berarti semua frame berisi tepat 51 pasangan LLTF dan
tidak mendefinisikan pemetaan untuk hasil pemilihan/kompaksi rentang khusus
`esp-radar`.

Pencarian dokumentasi Espressif semantik mengembalikan beberapa versi (termasuk
v5.5.4/current); hasil versi yang tidak sama dengan proyek tidak dipakai
sebagai dasar. Pencarian issue `espressif/esp-idf` tidak menemukan bukti yang
menyelesaikan pemetaan ESP32 klasik ini; temuan CSI yang tampak relevan
menyangkut ESP32-C5/C61, bukan target ini, sehingga tidak dapat diterapkan.

### Sumber 51/52 pada pipeline proyek

- Tabel subcarrier ESP32 memilih LLTF dari rentang raw `{76,128}` lalu
  `{2,54}` (104 byte sebelum compaction):
  [`csi_sub_carrier_table.c:24`](../../../examples/esp-radar/wifi_sensing_demo/esp-radar/src/csi_sub_carrier_table.c#L24).
- `copy_subcarrier_data` mengubah `start < 4` menjadi byte 4 ketika
  `first_word_invalid` aktif:
  [`esp_radar.c:787`](../../../examples/esp-radar/wifi_sensing_demo/esp-radar/src/esp_radar.c#L787)–[`esp_radar.c:798`](../../../examples/esp-radar/wifi_sensing_demo/esp-radar/src/esp_radar.c#L798).
  Rentang kedua karena itu kehilangan 2 byte (satu int8 I/Q pair), LLTF menjadi
  102 byte/51 pasangan.
- Tes fixture byte-level menunjukkan hasil terkompaksi 102 byte dan bahwa
  pasangan yang hilang berasal dari raw bytes 2–3:
  [`test_csi_compaction.py:138`](../../../fall_detection/tests/test_csi_compaction.py#L138)–[`test_csi_compaction.py:145`](../../../fall_detection/tests/test_csi_compaction.py#L145),
  [`test_csi_compaction.py:199`](../../../fall_detection/tests/test_csi_compaction.py#L199).
- Reader training menghitung pasangan LLTF dari `lltf_len`, mendekode payload
  secara berurutan, lalu menghitung magnitudo hanya dari pasangan LLTF:
  [`train_activity_model.py:144`](../../../fall_detection/train_activity_model.py#L144),
  [`train_activity_model.py:207`](../../../fall_detection/train_activity_model.py#L207)–[`train_activity_model.py:214`](../../../fall_detection/train_activity_model.py#L214).
- Feature extractor menggunakan lebar aktual frame dan
  `band = floor(subcarrier_index * 16 / width)`:
  [`train_activity_model.py:222`](../../../fall_detection/train_activity_model.py#L222)–[`train_activity_model.py:254`](../../../fall_detection/train_activity_model.py#L254).
- Snapshot audit mencatat 130/130 take memiliki 51 pasangan:
  [`DATASET_AUDIT.md:10`](./DATASET_AUDIT.md#L10)–[`DATASET_AUDIT.md:18`](./DATASET_AUDIT.md#L18).
  Artifact menyimpan `subcarrier_width=51`, formula band `/51`, 16 means,
  16 scales, dan matriks bobot 2×16:
  [`final_model_experiment_B.json`](./final_model_experiment_B.json).
- Firmware saat ini mengenali 51 dan 52, tetapi hanya menerima frame jika
  lebarnya sama dengan `ACTIVITY_MODEL_SUBCARRIERS`:
  [`activity_classifier.c:102`](../../../examples/esp-radar/wifi_sensing_demo/main/activity_classifier.c#L102)–[`activity_classifier.c:152`](../../../examples/esp-radar/wifi_sensing_demo/main/activity_classifier.c#L152).
  Header yang sekarang terpasang menyatakan 52 pasangan/104 byte dan model
  lama 3-kelas:
  [`activity_model_data.h:17`](../../../examples/esp-radar/wifi_sensing_demo/main/activity_model_data.h#L17)–[`activity_model_data.h:22`](../../../examples/esp-radar/wifi_sensing_demo/main/activity_model_data.h#L22).
- Kedua feature extractor memakai magnitudo I/Q (simetris terhadap pertukaran
  I/Q), adjacent-frame absolute difference, band mean, dan `log1p`. Tetapi
  batas band berubah antara lebar 51 dan 52; karena itu feature vector 51 tidak
  dapat diperlakukan sebagai vector 52.

### Pemetaan fisik dan hasil gate Fase 0

ESP-IDF v5.5.3 mendefinisikan urutan LLTF `0..31, -32..-1` dan menyatakan
urutan item CSI mengikuti urutan subcarrier pada tabel. Untuk ESP32 20 MHz /
secondary NONE, rentang `esp-radar` adalah `[76,128)` lalu `[2,54)`. Dengan
dua byte per pasangan, posisi raw-nya `[38,64)` lalu `[1,27)`, sehingga urutan
52 sampel hasil pemilihan adalah `-26..-1, +1..+26`.

Ketika `first_word_invalid=true`, kode `copy_subcarrier_data` menjepit awal
rentang kedua dari byte 2 ke byte 4. Itu membuang pasangan raw 1 (`+1`), bukan
pasangan pertama hasil pemilihan. Fixture byte-level membuktikan raw bytes 2–3
berada pada pasangan keluaran ke-26 sebelum clamp. Hasil setelah clamp adalah
51 pasangan dengan urutan `-26..-1, +2..+26`; pasangan-0 adalah `-26`.
Klaim lama dalam `DATA_CONTRACT.md` bahwa pasangan-0 adalah LLTF indeks fisik
`-2` sudah dikoreksi.

Training membaca tepat `lltf_len` byte pertama dari `valid_b64` dan
mempertahankan urutan pasangannya. Firmware merekam `info->valid_data` dan
`valid_lltf_len`; keduanya berasal dari hasil filter `esp-radar`. Audit snapshot
Experiment B melaporkan 130/130 take memiliki lebar 51. Jadi transformasi
indeks dan representasi input training cocok dengan jalur firmware untuk
Layout A dan gate firmware harus menerima hanya 102-byte LLTF int8 dengan
`first_word_invalid=true`, 20 MHz, secondary NONE. Rekaman mentah tidak ada
untuk membandingkan ulang setiap payload historis byte-per-byte; batas ini
dicatat sebagai keterbatasan provenance, bukan alasan untuk menggeser atau
membangun ulang fitur.

Hasil gate Fase 0: **(a), cocok pada tingkat urutan dan transformasi sumber**.
Capture hardware tidak diperlukan untuk memetakan rentang tersebut dan tidak
dilakukan.

## 3. Sasaran perilaku integrasi (setelah gate riset lulus)

- Aktivitas Linear SVM FALL/NON_FALL berjalan berdampingan dengan detector
  Motion Graph/FSM yang sudah ada.
- Output classifier tidak dipetakan menjadi status gerak FSM dan tidak
  mengubah threshold, baseline, smoothing, sensitivity, debounce, atau
  perilaku detector.
- Hanya layout input yang terbukti cocok dengan artifact diproses.
  Kombinasi flag/panjang yang tidak cocok ditolak eksplisit; layout 52 tidak
  boleh dinormalisasi diam-diam menjadi 51.
- Urutan label artifact tetap `fall`, `non_fall`; skor tetap
  one-vs-rest hinge margin dan keputusan tetap argmax sesuai class order.
- Tidak mengedit `managed_components/`.

## 4. Non-goals dan batasan

- Tidak menyatakan metrik OOF sebagai validasi independen atau klaim performa
  final. Dataset memiliki confound tanggal/protokol dan validasi LOTO bukan
  validasi lintas-subjek.
- Tidak mengubah feature extractor/model/hyperparameter untuk mengejar
  kecocokan firmware tanpa persetujuan.
- Tidak memakai sklearn sebagai refit pengganti; trainer kanonik benchmark
  adalah `fall_detection.classifier_models.fit_classifier`.
- Tidak flash, capture hardware, atau commit tanpa persetujuan.
- Tidak menyatakan RAM, flash, atau waktu inference perangkat sebelum diukur.

## 5. TODO dan acceptance criteria

### Fase 0 — Selesaikan pemetaan CSI (blocker)

- [x] Buat peta byte-ke-subcarrier untuk target ESP32 klasik dan layout tabel
      `secondary NONE`, mengikuti tabel CSI ESP-IDF v5.5.3 serta rentang
      `csi_sub_carrier_table.c`.
- [x] Gunakan fixture byte-level yang ada dan, bila perlu, satu capture raw
      baru yang disetujui untuk menguji peta itu. Jangan menganggap komentar
      DATA_CONTRACT sebagai bukti jika bertentangan dengan bytes/source.
- [x] Tentukan apakah clamp membuang sampel berindeks fisik tertentu dan
      bagaimana indeks sampel 0–50 dalam training berkorespondensi dengan
      output firmware.
- [x] Putuskan secara tertulis salah satu hasil:
      (a) representasi training 51 identik dengan hasil firmware dan model
      dapat dipakai; atau
      (b) representasi tidak identik/tidak dapat dibuktikan, sehingga cache
      fitur/model final perlu dibangun ulang dari transformasi yang disepakati.
- [x] Koreksi klaim pemetaan di [`DATA_CONTRACT.md`](../../../docs/DATA_CONTRACT.md)
      hanya setelah pemetaan didukung dokumentasi/observasi; simpan aturan
      panjang↔flag dan contoh indeks dengan jelas.

**Gate:** jangan mengedit jalur runtime atau mengekspor model ke header sebelum
semua TODO Fase 0 selesai dan hasil (a) terbukti. Jika hasil (b), minta
persetujuan eksplisit untuk refit final baru sebelum training.

### Fase 1 — Bekukan kontrak artifact dan ekspor

- [x] Verifikasi ulang hash artifact, input cache, urutan kelas, jumlah fitur,
      mean/scale, koefisien/intercept, source trainer, serta rule feature band.
- [x] Tambah/ubah exporter deterministik yang mengubah artifact final menjadi
      file C/header. Output memuat provenance/hash, class order, lebar 51,
      panjang LLTF 102 byte untuk int8, feature count 16, window 24/stride 12,
      feature order, means/scales, weights, dan biases.
- [x] Pastikan regenerasi header tidak melatih ulang model dan gagal eksplisit
      bila dimensi, class order, formula, atau hash tidak sesuai artifact.
- [x] Catat perubahan kode di bagian paling bawah `docs/agent-changes.md`
      sebelum commit.

**Gate:** nilai header yang dihasilkan harus sama dengan nilai artifact setelah
formatting float C yang ditentukan; tidak ada parameter yang diambil dari
header lama.

### Fase 2 — Input dan fitur firmware

- [x] Selaraskan buffer amplitude/history dan feature extractor dengan 51
      pasangan sesuai hasil Fase 0.
- [x] Gate input pada jenis data int8, bandwidth, secondary channel, signal
      mode, `first_word_invalid`, dan `valid_lltf_len` yang benar; pastikan
      `valid_len`/segmen LLTF tidak mencampur HT-LTF.
- [x] Buat layout 52 ditolak eksplisit untuk model 51; jangan truncate,
      pad, interpolate, atau menerima layout melalui kesamaan panjang saja.
- [x] Pastikan panjang/flag yang salah tidak dapat dianggap cocok setelah
      konstanta model berubah.
- [x] Pertahankan jalur classifier sebagai output aktivitas tersendiri;
      jangan ubah FSM/Motion Graph atau threshold.

### Fase 3 — Tes host dan parity

- [x] Tambahkan host test untuk byte compaction dan urutan pasangan LLTF pada
      semua layout yang akan diterima/ditolak.
- [x] Uji ekstraksi 24 frame, stride 12, semua 16 indeks band, pembagi 51,
      mean absolute adjacent-frame amplitude delta, pembagian band, dan
      `log1p`.
- [x] Jalankan Python kanonik dan implementasi C pada input fixture identik;
      bandingkan amplitudo, fitur mentah, fitur terstandardisasi, kedua score,
      serta prediksi.
- [x] Tetapkan toleransi numerik C/Python berdasarkan representasi float yang
      benar-benar diuji; cek juga tie-break class order dan input non-finite.
- [x] Uji rejection frame 52-pasangan, flag/panjang mismatch, HT-LTF
      concatenation leak, dan queue/history reset jika frame ditolak.
- [x] Jalankan regression test classifier/CSI yang relevan dan
      `git diff --check`.

**Gate:** skor parity penuh harus lulus, bukan hanya kesamaan argmax.

Hasil host: 89 regression tests lulus. Skor C vs Python pada 3.088 window
memiliki galat absolut maksimum terukur `1.71700898e-6`, dengan 0 prediksi
berbeda. Untuk parity CSI-ke-fitur, 137 rekaman yang tersedia memberi 40.722
frame LLTF dan 3.192 window. Setiap frame memakai `valid_b64` yang sama,
`lltf_len=102`, int8, dan `first_word_invalid=true`; maksimum galat amplitudo
absolut `3.70076764e-6`, maksimum galat fitur `4.61979598e-7`. Batasan: ini
membandingkan payload LLTF hasil filter yang direkam, bukan merekonstruksi byte
driver sebelum compaction.

### Fase 4 — Build dan ukuran statis

- [x] Baca `docs/agent-preflight.md` sebelum perubahan runtime; catat bukti
      `Dokumen:` dan `Kutipan:` sebelum edit pertama.
- [x] Build dengan ESP-IDF **v5.5.3** untuk target `esp32`; jangan memakai MCP
      ESP-IDF v6.0.
      Setelah referensi ke ping-event callback privat dihapus dari aplikasi,
      `idf.py -C examples/esp-radar/wifi_sensing_demo build` selesai.
- [x] Rekam ukuran binary dan bandingkan dengan partition aplikasi aktual dari
      partition table build (bukan asumsi ukuran partisi). Partition table
      aktual memiliki partisi app terkecil `0x100000`; image `0xf1850` byte,
      tersisa `0xe7b0` byte (6%).
- [ ] Rekam penggunaan static RAM/stack yang dapat dibuktikan dari map/build
      dan periksa buffer history/queue classifier. Object target menunjukkan
      buffer amplitude history 4.896 B; inference stack/runtime target belum
      diukur dan image tidak tertaut.
- [x] Tidak flash.

### Fase 5 — Pengukuran target (perlu persetujuan hardware)

- [ ] Minta persetujuan sebelum flash atau capture hardware.
- [ ] Pada ESP32-WROOM-32/NodeMCU-32S, ukur waktu ekstraksi fitur dan inference
      dengan timer monotonic target; laporkan min/median/p95 dan metode ukur.
- [ ] Ukur dampak RAM/stack serta flash dari image yang benar-benar dibangun.
- [ ] Uji output classifier terpisah dari event/status FSM; verifikasi tidak
      mengubah jalur detector.
- [ ] Bandingkan input dan prediksi perangkat dengan fixture host bila
      prosedur capture yang disetujui tersedia.

### Fase 6 — Pelaporan dan evaluasi

- [x] Dokumentasikan konvensi sampel, unit, class order, scoring, layout yang
      diterima, batasan pemetaan, serta provenance artifact.
- [x] Pertahankan OOF sebagai evaluasi terpisah; jangan mengganti atau
      menulis ulang hasil OOF dengan prediksi full-fit.
- [x] Laporkan batasan dataset (confound tanggal/protokol, subjek/session
      terbatas, LOTO per take bukan lintas-subjek).
- [ ] Laporkan build/test/parity, ukuran firmware, RAM/flash, dan waktu target
      hanya jika hasilnya benar-benar diukur.
- [ ] Review seluruh diff dan dokumentasi; commit hanya atas persetujuan.

## 6. Status setelah implementasi

- Ekspor final tidak melatih ulang model. Artifact SHA-256:
  `0b5662acf36c72d1c502c6f0e9169eacfc4dd3a73b33899eb239c5e25590b5cb`.
- Cache SHA-256: `e4fcbf79bcaf43685bcf4077b34ad50549a684f821786b8d042593480101495e`;
  manifest SHA-256: `e9842d6fd961199e29b7cd7825a160ca409e35127ab3e6e4d2027c272bbe2269`.
- Header/sumber model C dihasilkan deterministik dan diverifikasi dengan
  `export_activity_model.py --check`; class order `fall, non_fall`, fitur 16,
  LLTF 51 pasang / 102 byte, window 24 frame / stride 12.
- Model menyimpan 66 nilai float32 parameter = 264 B; object target memiliki
  264 B parameter `.rodata` dan 25 B label/string/pointer. Buffer history
  amplitude `.bss` = 4.896 B. Ini ukuran object, bukan ukuran final firmware.
- Pemetaan fisik pasangan yang dihapus: selesai secara dokumenter; raw pair 1
  (`+1`) dihapus, output berurutan `-26..-1,+2..+26`.
- Kesetaraan input dan fitur diukur pada 137 rekaman yang tersedia: firmware
  menyalin 102 byte pertama `valid_data` setelah gate LLTF 51-pasangan;
  Python mengambil 102 byte pertama dari `valid_b64` sesuai `lltf_len=102`.
  Pada 40.722 frame dan 3.192 window (24 frame/stride 12), galat maksimum
  amplitudo `3.70076764e-6`; galat maksimum fitur `4.61979598e-7`.
- Build ESP-IDF v5.5.3 lulus. `wifi_sensing_demo.bin` berukuran `0xf1850`
  terhadap partisi app terkecil `0x100000` (sisa `0xe7b0`, 6%).
- `esp_wifi_sensing` 0.1.1~3 tidak menyediakan API publik untuk menerima
  ping reply per-paket. Hook aplikasi yang tak didukung dihapus; ping router
  start/stop tetap memakai API publik. Event ping per-paket tidak tersedia.
- RAM/flash dan waktu inference pada hardware belum diukur; tidak flash dan
  tidak capture hardware.
- Perubahan classifier tetap paralel dan terpisah dari Motion Graph/FSM;
  tidak mengubah threshold, baseline, smoothing, sensitivity, atau debounce.
- Keterbatasan dataset tetap berlaku: confound tanggal/protokol, metadata
  subject/session terbatas, dan LOTO per take bukan validasi lintas-subjek.
