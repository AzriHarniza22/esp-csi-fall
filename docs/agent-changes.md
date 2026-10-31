# Log perubahan oleh AI agent

File ini **wajib** diperbarui setiap kali agent mengubah kode. Satu entri per
perubahan logis, ditulis sebelum commit. Tujuannya agar alasan keputusan tidak
hilang di riwayat chat dan bisa ditinjau tanpa membedah diff.

## Aturan

- Tambahkan entri baru di **paling bawah**, jangan menimpa entri lama.
- Satu entri boleh mencakup beberapa file bila perubahannya satu tujuan.
- Tulis alasan yang bisa diperiksa, bukan "memperbaiki bug". Sebutkan gejala,
  penyebab, dan bukti (log, angka pengukuran, dokumen).
- Cantumkan sumber dokumentasi. Bila tidak ada, tulis eksplisit
  `tidak ditemukan` beserta alasannya.
- Jangan menyalin seluruh diff. Ringkas keputusan dan konsekuensinya.
- Bila perubahan dibatalkan kemudian, tambahkan entri baru yang menyebut
  pembatalannya; jangan menghapus entri lama.

## Format entri

```markdown
## YYYY-MM-DD — <judul singkat>

- Agent/tool: <nama agent atau model>
- Branch/commit: <branch> / <hash atau "belum di-commit">
- File: <daftar file yang berubah>
- Perubahan: <apa yang berubah, secara perilaku>
- Alasan: <gejala/penyebab/bukti yang mendorong perubahan>
- Dokumen: <komponen> <versi> <path/URL> — "<kutipan singkat>"
- Verifikasi: <build/flash/log/uji yang benar-benar dijalankan>
```

## Entri

## 2026-10-20 — Gate dokumentasi dan log perubahan wajib

- Agent/tool: opencode (deepseek-v4.1-flash-free)
- Branch/commit: default / belum di-commit
- File: `AGENTS.md`, `docs/agent-preflight.md`, `docs/agent-changes.md`,
  `.githooks/commit-msg`, `.cursor/rules/espressif-docs.mdc`,
  `.github/copilot-instructions.md`, `CLAUDE.md`
- Perubahan: menambahkan preflight dokumentasi wajib dan log perubahan wajib.
  Hook `commit-msg` sekarang menolak commit yang mengubah kode tanpa entri di
  file ini, dan tetap menolak commit yang menyentuh perilaku runtime tanpa
  trailer `Docs:`.
- Alasan: instruksi di `AGENTS.md` saja tidak menjamin dokumen dibaca atau
  alasan perubahan tercatat. Gate yang bisa diperiksa membuat keduanya dapat
  diaudit dan berlaku untuk semua agent yang memakai hook repo ini.
- Dokumen: tidak berlaku (perubahan tooling repo, bukan perilaku runtime).
- Verifikasi: hook diuji dengan file sementara di `main/` — tanpa entri
  changelog `rc=1`, dengan entri `rc=0`, tanpa trailer `Docs:` `rc=1`.

## 2026-10-22 — Recorder CSI dataset di web serial monitor

- Agent/tool: Cursor Grok 4.6
- Branch/commit: default / belum di-commit
- File: `examples/esp-radar/wifi_sensing_demo/main/web_serial_monitor.c`,
  `examples/esp-radar/wifi_sensing_demo/tools/web_serial_monitor.html`,
  `examples/esp-radar/wifi_sensing_demo/tools/csi_recorder.js`,
  `examples/esp-radar/wifi_sensing_demo/tools/csi_recorder_server.py`,
  `examples/esp-radar/wifi_sensing_demo/tools/tests/csi_recorder.test.js`,
  `examples/esp-radar/wifi_sensing_demo/tools/tests/test_csi_recorder_server.py`,
  `examples/esp-radar/wifi_sensing_demo/recordings/README.md`,
  `examples/esp-radar/wifi_sensing_demo/README.md`, `.gitignore`
- Perubahan: stream CSI serial bisa `SET_CSI_PERIOD 0` (setiap callback),
  JSON CSI menambah `ts_us`, `valid` (`valid_data`), dan field `rx_ctrl`.
  Panel recorder (label, countdown, durasi, take) menyimpan CSI_DATA + I/Q +
  meta ke `recordings/` lewat server lokal; panel library daftar/hapus/heatmap/replay.
- Alasan: live chart membuang frame di antara Period 20–1000 ms, jadi tidak
  bisa jadi dataset. Collect resmi `console_test` memakai target/delay/duration
  dan baris `CSI_DATA`; demo ini hanya punya kalibrasi Train, bukan collect.
- Dokumen: esp-radar 0.3.4 `managed_components/espressif__esp-radar/include/esp_radar.h`
  — "`int8_t *raw_data` unfiltered"; "`valid_data` after filtering";
  `data_type` adalah lebar `valid_data`. ESP-IDF v5.5.3 `esp_timer.h` —
  "`esp_timer_get_time` Get time in microseconds since boot".
  `examples/esp-radar/console_test/README.md` §4.8 collect window.
  `SET_CSI_PERIOD 0` tidak ada di API Espressif (hanya throttle serial demo).
- Verifikasi: `node examples/esp-radar/wifi_sensing_demo/tools/tests/csi_recorder.test.js`
  16 PASS. `python3 .../tools/tests/test_csi_recorder_server.py` 4 tests OK
  (POST/GET/DELETE dan tolak id `../escape`). Firmware belum di-flash pada sesi ini.

## 2026-10-22 — Grafik rekaman CSI di panel library

- Agent/tool: Copilot SDK in VS Code
- Branch/commit: default / belum di-commit
- File: `examples/esp-radar/wifi_sensing_demo/tools/web_serial_monitor.html`,
  `docs/agent-changes.md`
- Perubahan: mengganti aksi Replay dengan CSI graph. Heatmap dan grafik CSI
  sekarang ditampilkan bergantian pada panel visualisasi di bawah tabel
  recordings. Grafik rekaman memakai renderer yang sama dengan Raw CSI live,
  dengan pilihan amplitude/real/imaginary dan step subcarrier, tetapi tidak
  menimpa data grafik live.
- Alasan: Replay sebelumnya memuat data rekaman ke grafik Raw CSI live, lalu
  menampilkan heatmap sekaligus. Permintaan UX adalah melihat tiap plot di
  panel recording yang sama tanpa mengubah chart live.
- Dokumen: esp-radar 0.3.4
  `examples/esp-radar/wifi_sensing_demo/managed_components/espressif__esp-radar/include/esp_radar.h`
  — `valid_bytes` adalah "Valid bytes of CSI data after filtering";
  `raw_data` adalah "unfiltered and contains invalid subcarriers".
- Verifikasi: tes helper Node 16 PASS; tes server Python 4 OK; `git diff --check`
  bersih. Uji browser pada rekaman tersimpan (`198` frame, `164` subcarrier):
  Heatmap dan CSI graph tampil bergantian dengan canvas terisi, kontrol grafik
  berfungsi, grafik live tidak berubah, dan label panel/tombol berubah sesuai
  bahasa UI.

## 2026-10-22 — Memperjelas skala heatmap CSI

- Agent/tool: Copilot SDK in VS Code
- Branch/commit: default / belum di-commit
- File: `examples/esp-radar/wifi_sensing_demo/tools/web_serial_monitor.html`,
  `examples/esp-radar/wifi_sensing_demo/README.md`, `docs/agent-changes.md`
- Perubahan: heatmap diperbesar dan diberi sumbu frame/subcarrier, colorbar
  magnitudo `|I+jQ|`, tick labels, dan palet perseptual bergradasi. Rentang warna
  menggunakan percentile 2–98 supaya puncak ekstrem tidak meratakan kontras
  sebagian besar sampel; nilai CSI tetap tidak diubah. Canvas tersembunyi
  sekarang benar-benar tidak mengambil ruang layout.
- Alasan: heatmap lama tidak memiliki axes atau skala warna dan memakai rentang
  linear dari nol sampai maksimum, sehingga sulit mengaitkan pola dengan frame
  atau subcarrier. Pada rekaman nyata 198×164, magnitudo terukur p02=3.16,
  median=18.79, p98=61.59, maksimum=126.78; puncak ekstrem menekan kontras
  variasi yang lebih umum.
- Dokumen: esp-radar 0.3.4
  `examples/esp-radar/console_test/README.md` §4 — "Raw data displays the
  original CSI sub-carrier data."; `examples/esp-radar/console_test/tools/esp_csi_tool.py`
  menghitung amplitudo sebagai `abs(complex(real, imag))`.
- Verifikasi: browser recorder server pada rekaman 198 frame/164 subcarrier
  menunjukkan plot berwarna, sumbu X 0–197 frame, sumbu Y 0–163 subcarrier,
  colorbar amplitudo, dan hint clipping. Kanvas grafik yang tersembunyi
  terkonfirmasi `display:none`; terjemahan heatmap English/Chinese diuji.

## 2026-10-22 — Audit offline dataset CSI untuk fall detection

- Agent/tool: Copilot SDK in VS Code
- Branch/commit: default / belum di-commit
- File: `fall_detection/__init__.py`, `fall_detection/audit_dataset.py`,
  `fall_detection/tests/test_audit_dataset.py`, `fall_detection/README.md`,
  `docs/agent-changes.md`
- Perubahan: menambahkan auditor offline berbasis Python standard library
  untuk memvalidasi metadata take, kelengkapan, jumlah frame, kolom I/Q,
  jumlah subcarrier, dan nilai numerik; melaporkan take yang layak secara
  struktural tanpa menyimpulkan label atau kecukupan dataset.
- Alasan: pemeriksaan rekaman lokal menunjukkan hanya satu take lengkap
  (`kosong`, 198 frame/164 subcarrier); take `tes` tidak lengkap dan memiliki
  0 subcarrier. Belum ada kelas jatuh yang terverifikasi, sehingga training
  supervised belum dapat dijalankan secara sahih.
- Dokumen: format proyek `examples/esp-radar/wifi_sensing_demo/recordings/README.md`
  — "`*.iq.csv` — one row per frame, I/Q columns per subcarrier"; format dan
  metadata juga diperiksa di `examples/esp-radar/wifi_sensing_demo/tools/csi_recorder.js`.
  Tidak mengubah firmware, driver, radio, atau serial runtime protocol.
- Verifikasi: `python3 -m unittest discover -s fall_detection/tests -v`
  (4 PASS); `python3 fall_detection/audit_dataset.py` melaporkan 1 eligible
  take (`kosong`, 198 frame/164 subcarrier), 1 excluded (`tes`, incomplete/0
  subcarrier), dan training gate blocked karena baru satu label. Mode `--json`
  juga diuji; Pylance diagnostics kedua file Python: tidak ada temuan.

## 2026-10-23 — Terjemahkan status Wi-Fi GOT_IP di UI

- Agent/tool: Copilot SDK in VS Code
- Branch/commit: default / belum di-commit
- File: `examples/esp-radar/wifi_sensing_demo/tools/web_serial_monitor.html`,
  `docs/agent-changes.md`
- Perubahan: konversi state protokol seperti `GOT_IP` ke suffix key UI
  sekarang mengubah pemisah underscore menjadi camel-case (`GotIp`), agar
  status mendapat label “Connected” alih-alih menampilkan key mentah.
- Alasan: perangkat melaporkan `GOT_IP` bersama IP/BSSID/channel/RSSI, tetapi
  UI menghasilkan key `wifiStateGot_ip` yang tidak cocok dengan entri
  `wifiStateGotIp`; itu kegagalan pemetaan terjemahan, bukan status koneksi.
- Dokumen: ESP-IDF v5.5.3 Wi-Fi Guide,
  <https://docs.espressif.com/projects/esp-idf/en/v5.5.3/esp32/api-guides/wifi.html#ip-event-sta-got-ip>
  — “This event arises when the DHCP client successfully gets the IPV4 address
  from the DHCP server.”
- Verifikasi: evaluasi fungsi UI yang diekstrak dari file menghasilkan
  `GOT_IP -> Connected`, `CONNECTED -> Associated`, `FAILED -> Failed`, dan
  `DISCONNECTED -> Disconnected`; `git diff --check` bersih. Browser server
  lokal tidak sedang berjalan saat pemeriksaan, sehingga verifikasi visual live
  tidak dilakukan.

## 2026-10-23 — Model klasifikasi aktivitas CSI eksperimental di ESP32

- Agent/tool: Copilot SDK in VS Code
- Branch/commit: default / belum di-commit
- File: `fall_detection/train_activity_model.py`,
  `fall_detection/tests/test_train_activity_model.py`,
  `fall_detection/README.md`,
  `examples/esp-radar/wifi_sensing_demo/main/activity_classifier.c`,
  `examples/esp-radar/wifi_sensing_demo/main/activity_classifier.h`,
  `examples/esp-radar/wifi_sensing_demo/main/activity_model_data.h`,
  `examples/esp-radar/wifi_sensing_demo/main/app_main.c`,
  `examples/esp-radar/wifi_sensing_demo/main/web_serial_monitor.c`,
  `examples/esp-radar/wifi_sensing_demo/main/CMakeLists.txt`,
  `docs/agent-changes.md`
- Perubahan: menambah trainer standard-library yang membentuk 32 fitur log
  perubahan amplitudo untuk window 24 frame, menggabungkan label eksplisit
  `ayunkan tangan sekali/dua kali`, dan mengekspor centroid/skala ke header C.
  Firmware menyalin CSI INT8 108 sampel kompleks ke queue bounded dari callback;
  task FreeRTOS menghitung nearest-centroid tiap 12 frame dan mencatat kelas
  serta jarak di serial. Hasil diberi batas “DEMO only”; tidak ada klaim
  validasi atau fall detection.
- Alasan: pengguna meminta menguji alur training dan inferensi mandiri pada ESP.
  Data yang tersedia berisi satu take duduk dan dua take ayunan; tiap take
  menghasilkan window overlap (8 duduk, 19 ayunan) yang bukan sampel independen
  dan label seluruh take dapat menyertakan frame tanpa gerakan. Karena itu model
  hanya memverifikasi jalur ekspor/inferensi. `kosong` 164-bin tidak dicampur
  dengan take 108-bin.
- Dokumen: ESP-IDF v5.5.3
  `/home/azri/.espressif/v5.5.3/esp-idf/docs/en/api-guides/wifi.rst` §Wi-Fi CSI
  — “The CSI receiving callback function runs from Wi-Fi task. So, do not do
  lengthy operations in the callback function. Instead, post necessary data to
  a queue and handle it from a lower priority task.” esp-radar 0.3.4
  `managed_components/espressif__esp-radar/include/esp_radar.h` — `valid_len`
  adalah panjang data setelah filtering dan pointer callback hanya valid selama
  callback; `managed_components/espressif__esp-radar/src/esp_radar.c` membaca
  INT8 valid_data sebagai pasangan real/imaginary berurutan.
- Verifikasi: `python3 -m unittest discover -s fall_detection/tests -v`
  (8 PASS); trainer menghasilkan 8 window duduk dan 19 window ayunan dari 3
  take lengkap; dataset audit mengenali take lama `tes` sebagai tidak lengkap.
  Build `idf.py -C examples/esp-radar/wifi_sensing_demo build` dengan ESP-IDF
  v5.5.3 lulus; binary 0xec9b0 byte, app partition tersisa 0x13650 byte.
  Flash pertama gagal karena port sibuk (`code` PID 128152); setelah pengguna
  menutup pemegang serial, flash ke ESP32-D0WD-V3 pada `/dev/ttyUSB0` berhasil
  dan hash image terverifikasi. Verifikasi log runtime belum dilakukan:
  `idf.py monitor` non-interaktif berhenti karena stdin bukan TTY, lalu
  permintaan monitor interaktif ditolak pengguna. `git diff --check` bersih.

## 2026-10-23 — Tampilkan klasifikasi CSI live di Web Serial

- Agent/tool: Copilot SDK in VS Code
- Branch/commit: default / belum di-commit
- File: `examples/esp-radar/wifi_sensing_demo/main/activity_classifier.c`,
  `examples/esp-radar/wifi_sensing_demo/main/web_serial_monitor.c`,
  `examples/esp-radar/wifi_sensing_demo/main/web_serial_monitor.h`,
  `examples/esp-radar/wifi_sensing_demo/tools/web_serial_monitor.html`,
  `docs/agent-changes.md`
- Perubahan: menyiarkan hasil nearest-centroid sebagai pesan `HMS:` bertipe
  `activity` dan menampilkan kelas, jarak kelas terdekat, runner-up, serta
  status confidence pada panel web berbahasa Inggris/Tionghoa.
- Alasan: klasifier sebelumnya hanya mengirim hasil melalui log ESP, yang tidak
  diparse panel aplikasi. Model hanya menghasilkan jarak, bukan probabilitas
  atau confidence terkalibrasi, sehingga UI harus menyatakan confidence tidak
  tersedia dan tidak mengarang persentase.
- Dokumen: ESP-IDF v5.5.3
  `/home/azri/.espressif/v5.5.3/esp-idf/docs/en/api-guides/wifi.rst` §Wi-Fi CSI
  — “The CSI receiving callback function runs from Wi-Fi task. So, do not do
  lengthy operations in the callback function. Instead, post necessary data to
  a queue and handle it from a lower priority task.”
- Verifikasi: `python3 -m unittest discover -s fall_detection/tests -v`
  (8 PASS); ESP-IDF v5.5.3 `idf.py -C
  examples/esp-radar/wifi_sensing_demo build` lulus, image 0xecc00 byte dengan
  0x13400 byte tersisa di app partition.   Node mem-parsing inline JavaScript dan menguji payload `activity` sintetis
  (kelas/jarak tampil, confidence tidak tersedia, payload malformed ditolak);
  `git diff --check` bersih.
  Belum diuji pada perangkat/browser live, sehingga alur serial aktual belum
  terverifikasi.

## 2026-10-23 — Gunakan LLTF untuk prototipe 7 kelas CSI

- Agent/tool: Copilot SDK in VS Code
- Branch/commit: default / belum di-commit
- File: `fall_detection/train_activity_model.py`,
  `fall_detection/tests/test_train_activity_model.py`,
  `fall_detection/README.md`,
  `examples/esp-radar/wifi_sensing_demo/main/activity_classifier.c`,
  `examples/esp-radar/wifi_sensing_demo/main/activity_model_data.h`,
  `docs/agent-changes.md`
- Perubahan: trainer dan inferensi memakai 52 pasangan kompleks pertama dari
  LLTF untuk layout ESP32 20 MHz yang diverifikasi (non-HT 104 byte, HT non-STBC
  216 byte, HT STBC 328 byte); model memakai 16 band dan tujuh kelas aktivitas
  yang dipilih pengguna, termasuk label transisi berdiri→duduk dan
  berdiri→jongkok. Frame dengan metadata/layout lain ditolak.
- Alasan: audit tujuh take lengkap menunjukkan mayoritas CSI 328 byte
  (HT/STBC), sementara model lama hanya menerima 216 byte dan seluruh CSI
  concatenated bukan satu spektrum. Source tabel esp-radar memisahkan LLTF,
  HT-LTF, dan STBC-HT-LTF; LLTF 104 byte hadir di tiga layout yang diterima.
  Dataset masih satu take untuk sebagian besar kelas dan label mencakup frame
  sebelum/sesudah aksi, sehingga model hanya untuk uji jalur end-to-end.
- Dokumen: ESP-IDF v5.5.3
  `/home/azri/.espressif/v5.5.3/esp-idf/docs/en/api-guides/wifi.rst` §CSI —
  “post necessary data to a queue and handle it from a lower priority task”;
  esp-radar 0.3.4
  `managed_components/espressif__esp-radar/src/csi_sub_carrier_table.c` —
  LLTF ranges/byte lengths untuk layout HT20/non-STBC dan HT20/STBC.
- Verifikasi: `python3 fall_detection/audit_dataset.py` menemukan 7/7 take
  eligible; seluruhnya 164 pasangan hasil CSI dengan mayoritas HT/STBC,
  20 MHz, `valid_len=328`. Trainer ekspor 7 kelas dari 105 window overlap
  (38 `kosong`, 10–12 untuk setiap kelas aktivitas); setiap kelas hanya
  memiliki 1 take, bukan evaluasi independen. `python3 -m unittest discover
  -s fall_detection/tests -v` (9 PASS); build ESP-IDF v5.5.3 lulus, image
  0xecde0 byte dengan 0x13220 byte tersisa di app partition; `git diff --check`
  bersih. Firmware belum di-flash dan belum ada verifikasi runtime setelah
  perubahan ini.

## 2026-10-26 — Membandingkan classifier CSI yang dapat diekspor ke ESP32

- Agent/tool: Copilot SDK in VS Code
- Branch/commit: default / belum di-commit
- File: `fall_detection/classifier_models.py`,
  `fall_detection/train_activity_model.py`,
  `fall_detection/tests/test_train_activity_model.py`,
  `fall_detection/README.md`,
  `examples/esp-radar/wifi_sensing_demo/main/activity_classifier.c`,
  `examples/esp-radar/wifi_sensing_demo/main/activity_model_data.h`,
  `examples/esp-radar/wifi_sensing_demo/main/web_serial_monitor.c`,
  `examples/esp-radar/wifi_sensing_demo/main/web_serial_monitor.h`,
  `examples/esp-radar/wifi_sensing_demo/tools/web_serial_monitor.html`,
  `docs/agent-changes.md`
- Perubahan: trainer mendukung nearest centroid, Logistic Regression,
  linear SVM, decision tree kedalaman terbatas, dan random forest kecil;
  classifier terpilih diekspor sebagai header C yang berbeda bentuknya sesuai
  model untuk inferensi standalone pada task ESP32. `--test-take` memisahkan
  rekaman penuh untuk evaluasi dan `--algorithm all` membandingkan semua model
  hanya jika kelas uji lengkap serta masih ada take training tiap kelas.
  Panel serial kini menyebut score model (bukan jarak nearest-centroid) dan
  tetap tidak mengklaim probabilitas/confidence.
- Alasan: pengguna meminta alur untuk membandingkan algoritma dengan training
  di laptop dan klasifikasi standalone di ESP32. Pipeline CSI/LLTF dan fitur
  yang sama dipakai agar perbandingan hanya mengubah classifier. Audit data
  saat perubahan menunjukkan tujuh kelas dengan satu take per kelas; ini
  cukup untuk mencoba ekspor/inferensi, tetapi tidak cukup untuk holdout take
  penuh sekaligus melatih setiap kelas, dan belum ada take jatuh terverifikasi.
- Dokumen: ESP-IDF v5.5.3
  `/home/azri/.espressif/v5.5.3/esp-idf/docs/en/api-guides/wifi.rst` §CSI —
  “do not do lengthy operations in the callback function. Instead, post
  necessary data to a queue and handle it from a lower priority task”;
  esp-radar 0.3.4
  `examples/esp-radar/wifi_sensing_demo/managed_components/espressif__esp-radar/include/esp_radar.h`
  — `valid_data` adalah CSI hasil filtering dan `valid_lltf_len` adalah
  panjang data LLTF hasil filtering.
- Verifikasi: `python3 -m unittest discover -s fall_detection/tests -v`
  (11 PASS); `python3 fall_detection/train_activity_model.py --help`
  menampilkan lima algoritma dan pilihan `all`; header C untuk kelima algoritma
  dilatih dari data lokal lalu dikompilasi dengan GCC host `-std=c11 -Wall
  -Werror -fsyntax-only`; dua script inline web berhasil diparse oleh Node;
  model default nearest-centroid diekspor kembali dari tujuh take (satu take
  per kelas, tanpa klaim validasi); audit JSON mengonfirmasi satu take eligible
  per kelas; `git diff --check` bersih. Build ESP-IDF tidak dijalankan karena
  permintaan build sebelumnya ditolak; firmware belum di-flash atau
  diverifikasi pada perangkat.

## 2026-10-26 — Batch recording CSI tanpa jeda antar-take

- Agent/tool: Copilot SDK in VS Code
- Branch/commit: default / belum di-commit
- File: `examples/esp-radar/wifi_sensing_demo/tools/web_serial_monitor.html`,
  `examples/esp-radar/wifi_sensing_demo/tools/csi_recorder.js`,
  `examples/esp-radar/wifi_sensing_demo/tools/tests/csi_recorder.test.js`,
  `examples/esp-radar/wifi_sensing_demo/recordings/README.md`,
  `docs/agent-changes.md`
- Perubahan: panel recorder membatasi batch ke 1–100 take dan menambahkan gap
  0–60 detik (default 0). Countdown hanya berlaku sebelum take pertama; take
  berikutnya dimulai langsung jika gap 0. Setiap take dipisah dan disimpan
  sendiri, metadata mendapat `batch_id` dan `gap_s`, upload berjalan saat
  pengambilan CSI berlanjut, dan daftar rekaman diperbarui setelah batch.
  Batch multi-take memeriksa ketersediaan server sebelum memulai. README
  recordings menjelaskan label transisi, prosedur awal, dan keterbatasan
  repetisi yang saling berkorelasi.
- Alasan: UI sebelumnya sudah mempunyai jumlah take tetapi menambah countdown
  satu detik bila countdown nol dan menunggu upload serta refresh library
  sebelum merekam take berikutnya. Itu tidak memenuhi kebutuhan akuisisi
  kontigu dan menimbulkan lubang antarsegmen. Sumber `esp-radar` menyatakan
  buffer CSI hasil callback dibebaskan setelah callback kembali, maka tiap
  frame harus tetap disalin segera oleh jalur serial/browser yang ada.
- Dokumen: esp-radar 0.3.4
  `examples/esp-radar/wifi_sensing_demo/managed_components/espressif__esp-radar/include/esp_radar.h`
  — “The memory that it points to will be deallocated after callback function
  returns”; ESP-IDF v5.5.3
  `/home/azri/.espressif/v5.5.3/esp-idf/docs/en/api-guides/wifi.rst` §CSI —
  “do not do lengthy operations in the callback function. Instead, post
  necessary data to a queue and handle it from a lower priority task.”
- Verifikasi: Node recorder tests 19 PASS; Python recorder-server tests 4
  PASS; inline JavaScript berhasil diparse; browser lokal menampilkan field
  batch dan mengonfirmasi `Takes max=100`, default gap `0`, konfigurasi
  `100 × 8s × gap 0` diterima serta 101 take ditolak; `git diff --check`
  bersih. Tidak ada board yang direkam live pada verifikasi ini.

## 2026-10-27 — Membatasi tinggi daftar rekaman di UI

- Agent/tool: Copilot SDK in VS Code
- Branch/commit: default / belum di-commit
- File: `examples/esp-radar/wifi_sensing_demo/tools/web_serial_monitor.html`,
  `docs/agent-changes.md`
- Perubahan: daftar rekaman kini berada dalam viewport dengan tinggi maksimum
  320 px dan scroll internal; header tabel tetap terlihat saat menggulir.
  Hitungan hasil filter dibanding total rekaman ditampilkan di atas daftar,
  sehingga visualisasi yang dipilih tetap dekat dan tidak terdorong jauh oleh
  daftar panjang.
- Alasan: seluruh rekaman sebelumnya dirender dalam tabel setinggi jumlah
  baris, sedangkan grafik visualisasi berada sesudah tabel. Makin banyak take,
  makin jauh posisi visualisasi dari kontrol utama.
- Dokumen: esp-radar 0.3.4
  `examples/esp-radar/wifi_sensing_demo/managed_components/espressif__esp-radar/include/esp_radar.h`
  — “The memory that it points to will be deallocated after callback function
  returns.” Perubahan hanya menyentuh tata letak DOM/CSS daftar dan tidak
  mengubah pengambilan atau pemrosesan CSI.
- Verifikasi: `node examples/esp-radar/wifi_sensing_demo/tools/tests/csi_recorder.test.js`
  (19 PASS); inline JavaScript diparse dengan Node; `git diff --check` bersih.
  Browser lokal diuji dengan 80 baris sintetik tambahan: viewport tetap
  320 px (318 px area isi), scrollHeight tabel 4764 px, header sticky; setelah
  memilih heatmap rekaman tersimpan, visualisasi tampil langsung setelah
  viewport (jarak 0 px). Perangkat CSI tidak diperlukan untuk perubahan
  presentasi ini.

## 2026-10-27 — Mencegah visualisasi rekaman tertukar saat klik cepat

- Agent/tool: Copilot SDK in VS Code
- Branch/commit: default / belum di-commit
- File: `examples/esp-radar/wifi_sensing_demo/tools/web_serial_monitor.html`,
  `docs/agent-changes.md`
- Perubahan: hasil visualisasi hanya diterapkan jika permintaan masih cocok
  dengan pilihan terakhir. Panel juga menampilkan label, waktu, dan jumlah
  frame rekaman yang sedang divisualisasikan; teks tersebut mengikuti bahasa
  UI.
- Alasan: alur sebelumnya menunggu `fetchRecording()` tanpa memeriksa apakah
  ID yang diminta masih merupakan pilihan terbaru. Jika respons rekaman
  pertama terlambat setelah pilihan berubah, respons tersebut dapat menimpa
  visualisasi. Judul grafik sebelumnya generik, sehingga tidak menunjukkan
  identitas rekaman aktif.
- Dokumen: Web serial monitor UI (versi proyek tidak dipisahkan)
  `docs/agent-changes.md`, entri “Grafik rekaman CSI di panel library” —
  “Heatmap dan grafik CSI sekarang ditampilkan bergantian pada panel
  visualisasi di bawah tabel recordings.” Tidak ada dokumentasi Espressif
  yang relevan; perubahan hanya menangani permintaan UI asynchronous dan
  identitas visualisasi.
- Verifikasi: browser lokal menguji urutan respons tak berurutan (`duduk`
  mulai dahulu, `kosong` selesai dahulu), lalu memastikan ID, frame, dan label
  yang aktif tetap `kosong` setelah respons `duduk` selesai; panel juga
  menampilkan label/waktu/frame serta berganti ke mode CSI graph. Tes
  JavaScript inline diparse oleh Node dan `git diff --check` bersih. Nilai
  hash dari pembacaan canvas pertama tidak digunakan sebagai bukti karena
  pembacaan pertama `getImageData()` mengubah hasil readback canvas.

## 2026-10-27 — Mengganti tombol unduh rekaman dengan Motion graph

- Agent/tool: Copilot SDK in VS Code
- Branch/commit: default / belum di-commit
- File: `examples/esp-radar/wifi_sensing_demo/tools/web_serial_monitor.html`,
  `examples/esp-radar/wifi_sensing_demo/tools/csi_recorder.js`,
  `examples/esp-radar/wifi_sensing_demo/tools/tests/csi_recorder.test.js`,
  `examples/esp-radar/wifi_sensing_demo/recordings/README.md`,
  `docs/agent-changes.md`
- Perubahan: action `CSI_DATA` dan `I/Q` dihapus, diganti tombol `Motion graph`.
  Saat merekam, browser kini menyimpan telemetri motion ESP (`motion_status`,
  `smooth_scaled`, `enter_level_scaled`, dan `exit_level_scaled`) per take
  dalam metadata JSON. Grafik menampilkan tiga kurva nilai detektor dan strip
  status ACTIVE/INACTIVE. Rekaman lama tanpa telemetri menampilkan instruksi
  untuk merekam ulang, bukan menggambar nilai turunan CSI seolah-olah output
  detektor.
- Alasan: pengguna memilih grafik output motion detector ESP. Rekaman CSI yang
  ada sebelumnya tidak menyimpan output detector per sampel, sehingga tidak
  cukup untuk membangun kembali grafik aktual dari rekaman lama.
- Dokumen: Web serial monitor firmware (proyek ESP-IDF v5.5.3)
  `examples/esp-radar/wifi_sensing_demo/main/web_serial_monitor.c` — sample
  JSON memuat `"motion_status"`, `"smooth_scaled"`, `"enter_level_scaled"`,
  dan `"exit_level_scaled"`; `docs/agent-preflight.md` menyatakan proyek
  dibangun dengan ESP-IDF v5.5.3.
- Verifikasi: Node helper tests 21 PASS; recorder-server tests 4 PASS; seluruh
  fall-detection Python tests 11 PASS; inline JavaScript diparse oleh Node;
  browser memverifikasi label tombol, pesan yang tepat untuk rekaman lama,
  grafik/legend/state strip dengan sampel telemetri sintetis, dan penangkapan
  sample serial yang hanya memasukkan peer terpilih. Tes server juga memastikan
  `motion_samples` tersimpan dan dikembalikan pada GET rekaman. Build firmware
  ESP-IDF v5.5.3 berhasil; image 0xecea0 byte dengan 0x13160 byte tersedia pada
  app partition. `git diff --check` bersih. Tidak ada board direkam live pada
  sesi ini, jadi penyimpanan telemetri lewat sesi Web Serial nyata belum
  diverifikasi di perangkat.

## 2026-10-27 — Memasang Logistic Regression tanggal 27 untuk uji ESP32

- Agent/tool: Copilot SDK in VS Code
- Branch/commit: default / belum di-commit
- File: `examples/esp-radar/wifi_sensing_demo/main/activity_model_data.h`,
  `docs/agent-changes.md`
- Perubahan: mengganti model embedded dari nearest-centroid 7 kelas menjadi
  Logistic Regression 3 kelas (`kosong`, `duduk`, `berjalan`), dilatih ulang
  dari take eligible tanggal 27 Oktober saja. Linear SVM tidak dipasang pada
  tahap ini agar pengguna dapat menguji algoritma di ESP satu per satu.
- Alasan: perbandingan holdout tanggal 27 menempatkan Logistic Regression dan
  Linear SVM seri pada skor teratas. Pengguna meminta menguji masing-masing
  model secara berurutan di perangkat, dimulai dari salah satu model seri.
- Dokumen: esp-radar 0.3.4
  `examples/esp-radar/wifi_sensing_demo/managed_components/espressif__esp-radar/include/esp_radar.h`
  — `valid_lltf_len` adalah “Length of the LL-LTF data after filtering”.
  ESP-IDF v5.5.3
  `/home/azri/.espressif/v5.5.3/esp-idf/docs/en/api-guides/tools/idf-py.rst`
  — `idf.py flash` otomatis membangun proyek bila perlu, lalu melakukan flash.
- Verifikasi: trainer Logistic Regression memakai tepat 44 take eligible
  tanggal 27 (24 `kosong`, 10 `duduk`, 10 `berjalan`) dan header hasil
  menyebut hanya ID take tanggal 27. Build ESP-IDF v5.5.3 berhasil; image
  `0xecd40` byte dan sisa app partition `0x132c0` byte. Flash UART ke ESP32
  `/dev/ttyUSB0` berhasil dan hash seluruh image terverifikasi. `git diff
  --check` bersih. Monitor boot tidak dapat dijalankan karena tool monitor
  membutuhkan TTY interaktif; klasifikasi CSI live belum diuji dengan target
  Wi-Fi/CSI aktif.

## 2026-10-27 — Memasang Linear SVM tanggal 27 untuk uji ESP32

- Agent/tool: Copilot SDK in VS Code
- Branch/commit: default / belum di-commit
- File: `examples/esp-radar/wifi_sensing_demo/main/activity_model_data.h`,
  `docs/agent-changes.md`
- Perubahan: mengganti Logistic Regression dengan Linear SVM 3 kelas
  (`kosong`, `duduk`, `berjalan`), dilatih ulang dari 44 take eligible tanggal
  27 Oktober saja. Dataset, fitur, dan label tidak diubah agar tes perangkat
  membandingkan algoritma satu per satu.
- Alasan: pengguna melaporkan Logistic Regression hampir selalu mengeluarkan
  `kosong` saat berjalan dan meminta mencoba Linear SVM berikutnya.
- Dokumen: esp-radar 0.3.4
  `examples/esp-radar/wifi_sensing_demo/managed_components/espressif__esp-radar/include/esp_radar.h`
  — `valid_lltf_len` adalah “Length of the LL-LTF data after filtering”.
  ESP-IDF v5.5.3
  `/home/azri/.espressif/v5.5.3/esp-idf/docs/en/api-guides/tools/idf-py.rst`
  — `idf.py flash` otomatis membangun proyek bila perlu, lalu melakukan flash.
- Verifikasi: trainer menghasilkan Linear SVM dari 44 take tanggal 27 saja
  (24 `kosong`, 10 `duduk`, 10 `berjalan`); header memilih
  `ACTIVITY_MODEL_NAME "linear-svm"` dengan tiga kelas. Fall-detection tests
  11 PASS; recorder tests 21 PASS; build ESP-IDF v5.5.3 berhasil (image
  `0xecd40` byte, sisa partisi `0x132c0` byte). Flash ke ESP32
  `/dev/ttyUSB0` berhasil dan hash image terverifikasi. `git diff --check`
  bersih. Uji klasifikasi dengan CSI live belum dikonfirmasi melalui monitor.

## 2026-10-29 — Recording CSI model-agnostic (payload mentah lengkap + skema v2)

- Agent/tool: Qoder
- Branch/commit: default / belum di-commit
- File:
  - `examples/esp-radar/wifi_sensing_demo/main/web_serial_monitor.c`
  - `examples/esp-radar/wifi_sensing_demo/main/activity_model_data.h`
  - `examples/esp-radar/wifi_sensing_demo/tools/csi_recorder.js`
  - `examples/esp-radar/wifi_sensing_demo/tools/web_serial_monitor.html`
  - `examples/esp-radar/wifi_sensing_demo/tools/csi_recorder_server.py`
  - `examples/esp-radar/wifi_sensing_demo/tools/tests/csi_recorder.test.js`
  - `examples/esp-radar/wifi_sensing_demo/tools/tests/test_csi_recorder_server.py`
  - `fall_detection/dataset_io.py` (baru)
  - `fall_detection/validate_recording.py` (baru)
  - `fall_detection/tests/test_dataset_io.py` (baru)
  - `fall_detection/tests/test_validate_recording.py` (baru)
  - `docs/agent-changes.md`
- Perubahan:
  - **Firmware (`web_serial_monitor.c`):** menaikkan batas payload CSI
    (`WEB_SERIAL_CSI_MAX_RAW_LEN` 512 → 612 sesuai maksimum byte mentah CSI
    ESP32; `WEB_SERIAL_TX_BUF_SIZE` 3072 → 4096) agar seluruh payload yang
    diterima driver terkirim tanpa pemotongan; mengambil timestamp monotonic
    di awal callback (`cb_ts_us = esp_timer_get_time()`) bukan setelah enqueue;
    menambah field JSON lossless per frame: `dmac`, `first_word_invalid`,
    `rx_seq`, `lltf_len`, `ht_ltf_len`, `stbc_ht_ltf_len`,
    `rx_gain_compensation`. Field HE-LTF sengaja tidak dikirim karena target
    `esp32` tidak menghasilkannya.
  - **Perekam (`csi_recorder.js`, `web_serial_monitor.html`,
    `csi_recorder_server.py`):** menambah skema v2 lossless di atas output v1
    yang tetap tidak berubah. `frames.csv` menyimpan kedua payload
    (`raw_b64` dari `raw_data` dan `valid_b64` dari `valid_data`) plus seluruh
    metadata per frame dengan `na` untuk field tak tersedia; `raw_iq.csv`
    menyimpan pasangan I/Q panjang-variatif (imajiner dulu, lalu real) dengan
    kolom `source` eksplisit tanpa zero-padding; `events.json` menyimpan
    segmen aktivitas + telemetri motion; `meta.json` v2 menambah
    `schema_version`, `recording_id`, `session_id`, `trial_id`, `subject_id`,
    `recording_started_at_utc`/`ended_at_utc`, `payload_semantics`
    (mengandung `iq_byte_order` dan catatan bahwa kolom `iq.csv` v1 lama
    tertukar), dan `pipeline_versions` (baseline classifier: 52 pasangan
    kompleks LLTF, 16 band log-amplitude-change, window 24, stride 12).
    Browser menambah `host_receive_monotonic_ns` via `performance.now()`;
    ketiga clock (callback `ts_us`, rx_ctrl `local_timestamp`, host ns)
    disimpan terpisah. Server mempersisten dan mengembalikan file v2.
  - **Reader model-agnostic (`fall_detection/dataset_io.py`):** stdlib-only,
    membaca skema v2 maupun v1 (fallback `csi_data.csv`), mendekode I/Q
    (imaginer-first), memotong komponen LTF dari panjang yang dilaporkan, dan
    menyediakan adapter terpisah: `to_feature_matrix` (LR/SVM/DT/RF),
    `to_time_series_tensor` (ROCKET/Hydra/TCN/CNN-LSTM), `to_observation_sequence`
    (HMM/DTW/shapelet). `baseline_band_features` mereproduksi pipeline 16-band
    yang terpasang tanpa mengubah classifier.
  - **Validasi (`fall_detection/validate_recording.py`):** verdict
    `VALID`/`WARNING`/`INVALID` dengan alasan; memeriksa integritas payload,
    konsistensi jumlah frame, timestamp duplikat/mundur/gap (ambang gap relatif
    8x median, bukan angka arbitrer), gap sequence, distribusi MAC/layout LTF,
    dan status finalisasi. Menulis `<id>.quality_report.json`.
  - **Perbaikan blocker build:** memulihkan
    `activity_model_data.h` baris 19 yang terkorupsi di working tree
    (`#define ACTIVITY_MODELNDOW_FRAMES` tanpa nilai) menjadi
    `#define ACTIVITY_MODEL_WINDOW_FRAMES 24`, sesuai template generator
    `train_activity_model.py` baris 291. Korupsi ini bukan dari pekerjaan
    recording tetapi mematahkan build baseline classifier.
- Alasan: fitur recording lama hanya menyimpan payload `valid_data` lewat
  `csi_data.csv`/`iq.csv` v1 (langkah `framePayloadBytes` memilih valid di atas
  raw), sehingga byte mentah driver dan metadata LTF hilang dan dataset tidak
  bisa dipakai ulang untuk keluarga model lain tanpa merekam ulang. Task
  meminta data mentah lengkap + timestamp terstandar + label/anotasi +
  validasi kualitas tanpa mengubah baseline classifier atau merusak dataset lama.
- Dokumen:
  - ESP-IDF v5.5.3
    `/home/azri/.espressif/v5.5.3/esp-idf/docs/en/api-guides/wifi.rst`
    — “The first one is imaginary part and the second one is real part”; urutan
    LTF “LLTF, HT-LTF, STBC-HT-LTF”; total byte CSI hingga 612 untuk
    HT/40MHz/STBC; arti `first_word_invalid`.
  - esp-radar 0.3.4
    `examples/esp-radar/wifi_sensing_demo/managed_components/espressif__esp-radar/include/esp_radar.h`
    — struct `wifi_csi_filtered_info_t` menyediakan `raw_len`/`raw_data`,
    `valid_len`, `valid_lltf_len`, `valid_ht_ltf_len`, `valid_stbc_ht_ltf_len`,
    `rx_gain_compensation`, `data_type`, `dmac`, dan pointer `info` ke
    `wifi_csi_info_t` driver (sumber `first_word_invalid` dan `rx_seq`).
  - `fall_detection/train_activity_model.py` baris 291 —
    `#define ACTIVITY_MODEL_WINDOW_FRAMES {WINDOW_FRAMES}` dengan
    `WINDOW_FRAMES = 24` (baris 17), dipakai untuk memulihkan header terkorupsi.
- Verifikasi:
  - `idf.py build` (ESP-IDF v5.5.3, target esp32) berhasil; image
    `0xeced0` byte, sisa partisi app `0x13130` byte (7%). `web_serial_monitor.c`
    dan `activity_classifier.c` terkompilasi tanpa error.
  - `python3 -m unittest discover -s fall_detection/tests` → 35 test OK
    (termasuk test audit_dataset dan train_activity_model lama → kompatibilitas
    mundur terjaga).
  - `node tests/csi_recorder.test.js` → semua PASS, exit 0 (termasuk test v2:
    base64 roundtrip, urutan imaginer-first, header/kolom frames, kedua payload
    raw+valid, tiga clock terpisah, payload_ok true/false, `na` untuk field tak
    tersedia, raw_iq source/panjang-variatif, events, metaV2).
  - `python3 tests/test_csi_recorder_server.py` → 5 test OK (termasuk
    `test_post_v2_files_roundtrip`).
  - `python3 -m fall_detection.validate_recording examples/esp-radar/wifi_sensing_demo/recordings`
    → 53 recording: VALID=0 WARNING=53 INVALID=0, exit 0. Semua WARNING karena
    file lama v1 tidak punya payload mentah driver dan sebagian tanpa
    `session_id` — diharapkan dan tidak merusak arti dataset lama.
  - **Sudah dijalankan (recording nyata):** pengguna merekam ulang dengan label
    `tes recording` (target `20261029T154556Z_tes_recording_001`, 162 frame).
    `dataset_io.load_recording` membacanya sebagai `schema_version=2` dari
    `frames_csv`; tiap frame menyimpan `raw_payload` 384 byte **dan**
    `valid_payload` 328 byte utuh (raw > valid → payload mentah driver tidak
    dipotong). Ketiga clock (`callback_timestamp_us`, `rx_ctrl_timestamp_us`,
    `host_receive_monotonic_ns`) tercatat terpisah. `validate_recording` →
    status **VALID** (tanpa alasan); adapter menghasilkan input nyata:
    `feature_matrix` 12×16, `time_series_tensor` 12×[164,24],
    `observation_sequence` 162×164.
  - **CATATAN (aktif after flash):** field metadata yang ditambahkan di
    `web_serial_monitor.c` (`lltf_len`, `ht_ltf_len`, `stbc_ht_ltf_len`,
    `first_word_invalid`, `rx_seq`, `dmac`, `rx_gain_compensation`) muncul
    sebagai `na` pada recording pertama karena perangkat masih memakai
    firmware lama (build v5.5.3 belum di-flash). Setelah `idf.py -p
    /dev/ttyUSB0 flash` (image app 970448 byte, hash terverifikasi) dan
    rekam ulang (`20261029T155155Z_tes_recording_001`, 148 frame), field itu
    terisi dari perangkat: `lltf_len=104`, `ht_ltf_len=112`,
    `stbc_ht_ltf_len=112` (jumlah = 328 = `valid_len`), `first_word_invalid=true`,
    `rx_seq` dan `dmac` terisi. `dataset_io.ltf_sections` memotong LLTF
    (0,104)/HT-LTF (104,216)/STBC-HT-LTF (216,328); `component_pairs` memberi
    LLTF 52 pasangan kompleks (persis baseline), HT-LTF 56, STBC-HT-LTF 56.
    `validate_recording` → **VALID** tanpa alasan/peringatan. Perangkat nyata
    terbukti menghasilkan komponen HT-LTF/STBC-HT-LTF yang dulu dibuang.
  - **NOT RUN (sisa):** uji variasi panjang/layout payload antar tipe paket
    (recording ini hanya satu layout HT); perilaku pada pesan serial parsial
    dan disconnect.

## 2026-10-30 — Perbaikan tinjauan: raw I/Q dua payload, csi_period_ms, lintas-clock, first_word

- Agent/tool: Qoder
- Branch/commit: default / belum di-commit
- File:
  - `examples/esp-radar/wifi_sensing_demo/tools/csi_recorder.js`
  - `examples/esp-radar/wifi_sensing_demo/tools/web_serial_monitor.html`
  - `examples/esp-radar/wifi_sensing_demo/tools/tests/csi_recorder.test.js`
  - `fall_detection/dataset_io.py`
  - `fall_detection/validate_recording.py`
  - `fall_detection/tests/test_dataset_io.py`
  - `fall_detection/tests/test_validate_recording.py`
  - `docs/agent-changes.md`
- Perubahan:
  - **A — raw_iq.csv kini dua baris per frame.** `buildRawIqCsv` sebelumnya
    memilih SATU payload (valid bila ada) sehingga I/Q raw_data (384 B = 192
    pasangan) tidak pernah tersimpan. Sekarang tiap frame menulis satu baris per
    payload yang tersedia (`source=raw_data` dan/atau `valid_data`) dengan
    jumlah pasangan = panjang aktual tiap payload (tanpa zero-padding), urutan
    imaginer-dulu sesuai dokumentasi.
  - **csi_period_ms diisi dari konfigurasi nyata.** meta lama men-hardcode
    `csi_period_ms: 0`. Sekarang `saveTake` membaca `appInfo.csi_stream_period_ms`
    dari pesan `hello` firmware dan menuliskannya ke field top-level dan
    `acquisition.csi_period_ms`, plus `acquisition.csi_period_note` yang
    menjelaskan `0 = unthrottled (emit tiap callback)`, `>0 = throttle ms`.
  - **C — selisih timestamp diberi label benar.** `_timestamp_report` menambah
    `cross_clock_delta` (min/median/max `callback - rx_ctrl`) dengan
    `interpretation` eksplisit bahwa itu offset antar-basis-clock, BUKAN latensi
    pemrosesan. Analisis interval/gap tetap hanya memakai satu clock
    (`callback_timestamp_us`).
  - **D — first_word_invalid ditangani, tidak diam-diam.** dataset_io menambah
    `leading_invalid_pairs(first_word_invalid, data_type)` (int8 → 2 pasangan,
    int16 → 1, sesuai "empat byte pertama" ESP-IDF). Representation factories dan
    ketiga adapter menerima `drop_first_word` (default **False** agar baseline 52
    LLTF tak berubah). Validator menambahkan WARNING bila ada frame
    `first_word_invalid` agar preprocessing tahu harus membuang pasangan awal.
  - `payload_semantics` meta menambah kunci `raw_iq_rows` dan
    `first_word_invalid`.
- Alasan: tinjauan pengguna menemukan tiga gap pasca-implementasi v2: I/Q masih
  hanya valid_data, `csi_period_ms` tidak informatif, selisih ~161 ms berisiko
  disalahartikan sebagai latensi, dan `first_word_invalid` belum dipertimbangkan
  saat memakai pasangan untuk training. Ini kebutuhan model-agnostic prioritas
  tinggi karena konsumen I/Q belum mendapat kedua payload.
- Dokumen:
  - ESP-IDF v5.5.3
    `/home/azri/.espressif/v5.5.3/esp-idf/components/esp_wifi/include/local/esp_wifi_types_native.h:64`
    — `rx_ctrl.timestamp`: "The local time when this packet is received. It is
    precise only if modem sleep or light sleep is not enabled. unit: microsecond"
    (field 32-bit; beda basis dengan `esp_timer_get_time()`).
  - ESP-IDF v5.5.3
    `/home/azri/.espressif/v5.5.3/esp-idf/components/esp_wifi/include/local/esp_wifi_types_native.h:123`
    dan `docs/en/api-guides/wifi.rst:2745` — `first_word_invalid` true berarti
    "the first four bytes of CSI data is invalid due to a hardware limitation".
  - `main/web_serial_monitor.c` hello — melaporkan `csi_stream_period_ms` sehingga
    browser bisa membacanya; firmware throttle `csi_stream_period_ms > 0` di
    callback berarti emit per periode, `0` = tanpa throttle.
- Verifikasi:
  - `python3 -m unittest discover -s fall_detection/tests` → **41 test OK**
    (+6 test baru: `leading_invalid_pairs`, 3 test `FirstWordInvalid` termasuk
    baseline tetap utuh saat default, `cross_clock_delta` non-latency, warning
    `first_word_invalid`).
  - `node tests/csi_recorder.test.js` → semua PASS, exit 0 (test raw_iq diperbarui
    ke dua baris raw+valid, plus test metaV2 semantics/csi_period).
  - `python3 tests/test_csi_recorder_server.py` → 5 test OK.
  - Validator pada recording nyata `20261029T155155Z_tes_recording_001`: status
    **WARNING**, `cross_clock_delta` median 161.533 ms (rentang 152.127–220.241)
    berlabel non-latency, `first_word_invalid_frames=148` → warning. Sesuai
    angka yang dilaporkan pengguna.
  - **NOT RUN:** flash firmware + rekam ulang untuk mengisi `acquisition.csi_period_ms`
    nyata dan `raw_iq.csv` dua-baris di file baru (perubahan format berlaku pada
    rekaman berikutnya; rekaman lama di disk masih berformat raw_iq satu-baris,
    dapat diregenerasi dari `frames.csv` karena `raw_b64` tersimpan utuh).

## 2026-10-30 — Audit first_word_invalid: koreksi pemotongan ditunda, helper dibatasi

- Agent/tool: Qoder
- Branch/commit: default / belum di-commit
- File:
  - `fall_detection/dataset_io.py`
  - `fall_detection/validate_recording.py`
  - `examples/esp-radar/wifi_sensing_demo/tools/csi_recorder.js`
  - `fall_detection/tests/test_dataset_io.py`
  - `docs/agent-changes.md`
- Perubahan:
  - **Tidak ada bagian recording v2 yang di-revert.** Raw+valid di `frames.csv`,
    `raw_iq.csv` dua baris/frame, `csi_period_ms` dari firmware, label
    cross-clock offset, dan flag `first_word_invalid` per frame + warning
    validator semuanya dipertahankan.
  - `drop_first_word` **dihapus** dari `amplitude_representation`,
    `iq_representation`, `to_feature_matrix`, `to_time_series_tensor`, dan
    `to_observation_sequence`. Ketiga fungsi itu membaca `valid_data` hasil
    kompresi esp-radar, jadi satu-satunya jalur masuk pemotongan yang belum
    terbukti kini menolak `TypeError`; `config` adapter mencatat
    `first_word_invalid_handling: "metadata only; trimming deferred..."`.
  - `leading_invalid_pairs()` dipertahankan sebagai utilitas hitung byte
    (int8 → 2 pasangan, int16 → 1) **khusus buffer asli** (`raw_payload` /
    `raw_data` = `wifi_csi_info_t.buf`); docstring kini memuat AUDIT LIMIT:
    tidak boleh diterapkan ke `valid_data`/segmen LTF sebelum pemetaan per
    layout terbukti.
  - Teks warning validator dan `meta.json payload_semantics.first_word_invalid`
    dipersempit: flag merusak empat byte pertama **buffer driver**, bukan
    empat byte terdepan setiap payload turunan; larangan auto-trim dinyatakan
    eksplisit.
  - Tes: `test_adapters_reject_unverified_first_word_trim` (TypeError di tiga
    adapter), `test_flagged_frames_are_not_trimmed` (output = daftar pasangan
    utuh, 52 lebar), regression `test_baseline_feature_matrix_is_unchanged_by_default`
    dipertahankan; tes counting helper tetap.
- Alasan: tinjauan pengguna menunda penerapan otomatis koreksi
  `first_word_invalid` sampai pemetaan byte/subcarrier terbukti. Audit jalur
  data menemukan pemotongan depan `valid_data` **terbukti salah** untuk layout
  nyata terekam: `esp_radar.c` menyusun `valid_data` dengan menempelkan
  rentang sub-carrier dari `buf` (`csi_sub_carrier_table.c`), dan untuk layout
  none/HT/20MHz/STBC (cocok dengan rekaman: raw 384, valid 104+112+112=328)
  segmen LLTF dimulai dari `buf[76]`, bukan `buf[0]`. Verified pada frame 0
  rekaman `20261029T155155Z`: `lltf[0:26] == raw[38:64]` (True) dan paruh
  invalid `buf[2:4]` muncul di `lltf[26] == (93, 0)` — tengah segmen. Membuang
  2 pasangan terdepan `valid_data` berarti membuang data sah `buf[76:80]`
  sementara byte invalid justru ditinggal tetap.
- Dokumen:
  - ESP-IDF v5.5.3 `docs/en/api-guides/wifi.rst:2745` — "the first four bytes
    of CSI data is invalid due to a hardware limitation"; dan bullet yang sama
    menyatakan data CSI "stored in a buffer starting from the buf field" dengan
    urutan LLTF → HT-LTF → STBC-HT-LTF (flag merujuk awal buffer, bukan awal
    setiap LTF — sesuai penegasan collaborator Espressif di issue esp-faq #4).
  - esp-radar 0.3.4 `src/esp_radar.c:836-837` — `filtered_info->raw_data =
    info->buf; filtered_info->raw_len = info->len;` (raw = identitas buffer).
  - esp-radar 0.3.4 `src/csi_sub_carrier_table.c:40-53` — entri none/HT/20
    MHz/STBC: `.lltf = {{76, 128}, {2, 54}}`, `.ht_ltf = {{200, 256},
    {130, 186}}`, `.stbc_ht_ltf = {{258, 314}, {328, 384}}`; `copy_subcarrier_data`
    menyalin rentang itu berurutan ke `valid_data`.
  - Status pemetaan: **terbukti** untuk layout satu ini (dok + data nyata);
    **belum terverifikasi** untuk layout lain (non-HT, 40 MHz, STBC variants,
    int16/lltf_bit_mode) — karena itu koreksi tidak diterapkan otomatis.
- Verifikasi: `python3 -m unittest discover -s fall_detection/tests` → 42 OK.
  `node tests/csi_recorder.test.js` → exit 0 semua PASS. `python3
  tests/test_csi_recorder_server.py` → 5 OK. Validator pada rekaman nyata
  `20261029T155155Z_tes_recording_001` → WARNING dengan teks baru (empat byte
  pertama buffer driver; jangan auto-trim). Bukti empiris mapping dicetak dari
  data rekaman (lihat Alasan). Rekaman baru untuk menguji `raw_iq.csv`
  dua-baris belum dijalankan; tidak perlu flash karena perubahannya di sisi
  browser/Python, bukan firmware.

## 2026-10-30 — Verifikasi rekaman "tes record": raw_iq dua baris terbukti; csi_period_ms null diperbaiki di flow Start

- Agent/tool: Qoder
- Branch/commit: default / belum di-commit
- File:
  - `examples/esp-radar/wifi_sensing_demo/tools/web_serial_monitor.html`
  - `docs/agent-changes.md`
- Perubahan: flow Start recording kini mengirim ulang `HMSCMD HELLO` setelah
  `START_CSI_STREAM` supaya `appInfo` (dan `csi_period_ms` meta) terisi nilai
  throttle live dari firmware sebelum `saveTake` berjalan.
- Alasan: verifikasi rekaman nyata pengguna (`recordings/tes_record`, tiga
  take 2026-10-29 18:52-18:53 UTC):
  - **A TERBUKTI:** `raw_iq.csv` dua baris per frame — 138/138, 129/129,
    146/146 frame menghasilkan pasangan 192 (`raw_data`) + 164
    (`valid_data`); jumlah baris = 2x frame, `frame_sequence` unik per frame,
    dan penghitungan frame validator memakai `frames.csv` sehingga dua baris
    tidak pernah dihitung dua frame. Tidak ada zero-padding (panjang tetap
    192/164 untuk semua frame).
  - **csi_period_ms GAGAL:** meta menulis `null`, bukan `0`. Akar masalah:
    `appInfo` hanya terisi dari pesan `hello`; respons `HELLO` firmware
    digate `sensing_ready` (`web_serial_monitor.c:1086-1091`) sehingga
    handshake saat connect bisa hanya membalas ack "sensing not ready" dan
    field `csi_stream_period_ms` tidak pernah sampai ke halaman. Kejadian
    persis (gate vs waktu connect) belum bisa direplikasi karena perangkat
    tidak tercolok saat pemeriksaan; perbaikan di sisi browser aman untuk
    kedua kemungkinan karena saat recording `sensing_ready` pasti benar
    (frame mengalir). Nilai `SET_CSI_PERIOD 0` disimpan ke
    `s_ctx.csi_stream_period_ms` (`web_serial_monitor.c:1133`) sehingga
    `HELLO` setelah Start mengembalikan angka live; `0` berarti unthrottled
    sesuai note meta, bukan 100 Hz.
  - Warning `first_word_invalid` dan `cross_clock_delta` muncul dengan teks
    audit baru pada ketiga take; tidak ada masalah integritas payload.
- Dokumen: `main/web_serial_monitor.c` — gate `if (!s_ctx.sensing_ready)
  { send_ack(cmd, false, "sensing not ready"); return; }` sebelum `HELLO`
  (baris 1086-1096); `SET_CSI_PERIOD` menyimpan ke
  `s_ctx.csi_stream_period_ms` (baris 1133); handler `HELLO` membalas
  `send_hello()` berisi `csi_stream_period_ms` (baris 1091-1096, 871-876).
- Verifikasi: `validate_recording` pada `recordings/` → ketiga take
  `tes_record` WARNING hanya karena `first_word_invalid` (sesuai desain),
  struktur `raw_iq.csv` diverifikasi dengan script counting sumber/pasangan.
  Suite Node/Python/server tidak terpengaruh perubahan HTML.
  **NOT RUN:** re-record singkat untuk mengonfirmasi `csi_period_ms: 0`
  tertulis di meta setelah perbaikan flow Start (butuh perangkat + browser
  reload; tanpa flash).
  **TERVERIFIKASI 2026-10-30:** setelah hard refresh, take
  `20261029T191238Z_tes_recording_001` (154 frame) menulis
  `csi_period_ms: 0` di top-level dan `acquisition`; validator PASS dengan
  dua WARNING jujur by-design (`first_word_invalid` seluruh frame, dan
  1 gap `seq_id` yang memang 1 frame `dropped` di perangkat).
- Verifikasi rekaman kedua 2026-10-30: `20261029T190253Z_tes_record_001`
  (147 frame) mengonfirmasi raw_iq dua baris/frame (147×192 raw_data +
  147×164 valid_data, tanpa padding) tetapi `csi_period_ms` masih `null`
  — halaman masih berjalan dari HTML pra-fix (belum di-reload).
- Probe serial langsung (perangkat dicolok ulang, port bebas; baud 921600
  terbukti — 115200 menghasilkan byte sampah, 921600 100% ASCII line
  `HMS:`): `HMSCMD HELLO` dijawab hello dengan
  `"csi_stream_period_ms":100`. Jalur respons HELLO terbukti berfungsi
  saat stream aktif; 100 adalah default firmware sesudah cold boot.
  Implikasi jujur: take 18:52/19:02 ber-~25 fps ≈ throttle 100 ms, jadi
  nilai keras `0` di v1 memang salah (poin B review) — nilai yang harus
  tertulis di meta adalah sebesar yang dikembalikan hello saat itu, dan
  baru bisa dibuktikan 0 sesudah browser menjalankan flow Start terbaru.

## 2026-10-31 — Pipeline recording v3: dua file per take, 8 label aktivitas, audio cue, hapus dataset lama

- Agent/tool: Qoder (Claude)
- Branch/commit: default / belum di-commit
- File: `examples/esp-radar/wifi_sensing_demo/tools/csi_recorder.js`,
  `tools/csi_recorder_server.py`, `tools/web_serial_monitor.html`,
  `tools/tests/csi_recorder.test.js`, `tools/tests/test_csi_recorder_server.py`,
  `fall_detection/dataset_io.py`, `fall_detection/validate_recording.py`,
  `fall_detection/audit_dataset.py`, `fall_detection/train_activity_model.py`,
  `fall_detection/tests/*` (baru: `test_dataset_io.py`,
  `test_validate_recording.py`),
  `examples/esp-radar/wifi_sensing_demo/docs/recording-pipeline-implementation.md`
  (subjuk spesifikasi; entri ini mengacu padanya, bukan mengubahnya)
- Perubahan: implementasi penuh spesifikasi `recording-pipeline-implementation.md`.
  1) Kontrak output berubah dari empat file turunan per take
     (`csi_data.csv`, `iq.csv`, `raw_iq.csv`, `events.json`) menjadi tepat dua
     file: `<id>.frames.csv` (32 kolom, payload base64 `raw_b64`/`valid_b64`)
     dan `<id>.meta.json` (`schema_version: 3`, events disatukan di node
     `events.segments` + `timeline`). Builder lama (`buildCsiDataCsv`,
     `buildIqCsv`, `buildRawIqCsv`, `buildEvents`, `buildMetaV2`) tetap ada
     sebagai fungsi manual legacy tetapi tidak dipanggil di jalur recording.
  2) 8 label aktivitas (`fall_forward/backward/left/right`, `walking`,
     `fast_sitting`, `bending`, `object_drop`) dengan pemetaan biner
     fall/non_fall, timeline fase tetap untuk durasi 10 s
     (`TARGET_DURATION_S`), dan batch `parseBatchSettings` mengabaikan
     `durationS` input (dipatok 10 s).
  3) Perintah audio berbahasa Indonesia + tone cue di browser, dengan
     preflight gating dan fallback visual-only yang dicatat ke meta sebagai
     deviasi protokol saat `AudioContext` tidak `running`.
  4) Tombol anotasi (`fall_start`, `fall_impact`) mencatat offset
     monotonik `offset_s` + `timestamp_utc`; tidak ada auto-fill.
  5) Server memvalidasi SEBELUM menulis (schema meta v3, header/jumlah baris
     frames.csv, base64 harus valid), menulis frames.csv lalu meta.json
     sebagai commit point; menolak field legacy (`csi_data_csv`, `iq_csv`,
     `raw_iq_csv`, `events`, `label`) dengan 400 tanpa partial write;
     `index.csv` adalah turunan dan ikut dibersihkan saat DELETE.
  6) Pembaca Python (`dataset_io`, `validate_recording`, `audit_dataset`,
     `train_activity_model`) mendapat cabang v3 (baca `frames.csv`, node
     `recording`, `activity_label`) dengan fallback v1/v2 dipertahankan.
     amplitude dihitung via `hypot(decode_iq(valid_b64))` — identik dengan
     jalur lama karena `hypot` invarian terhadap ordo i/q dan tanda.
  7) Dataset lama dihapus seluruhnya sesuai §14 spesifikasi (tanpa migrasi/
     backup): 60 take v1/v2, 204 file, 13 direktori label, `index.csv`;
     `README.md` dan `.gitkeep` dipertahankan. Penghapusan dieksekusi oleh
     user setelah cakupan diverifikasi dari filesystem (0 file `schema_version: 3`).
- Alasan: spesifikasi menuntut target tepat dua file utama per recording,
  konsistensi timestamp satu jam monotonic, dan annotation yang siap-latih;
  jalur empat-file lama redundan (semua turunan dapat direkonstruksi dari
  frames.csv — dibuktikan oleh tes kesetaraan decode P1b sebelum penghapusan).
  Dataset lama berisi label preset/usang (`kosong`, `tes record`) yang tidak
  sesuai taksonomi 8-label dan spesifikasi eksplisit melarang migrasi.
- Dokumen: `examples/esp-radar/wifi_sensing_demo/docs/recording-pipeline-implementation.md` —
  "tepat dua file per recording"; §14 "Dataset recording lama harus dihapus
  seluruhnya, tanpa migrasi dan tanpa backup". ESP-IDF v5.5.3
  `/home/azri/.espressif/v5.5.3/esp-idf` `wifi_csi.h` — "The CSI data is
  stored in `csi_data`... imaginary part comes before real part per
  subcarrier" (sumber urutan decode `decode_iq`; tidak ada dokumen eksternal
  baru yang diperlukan — perubahan murni host-side, firmware tidak disentuh
  dan jalur wire frame CSI tidak berubah sehingga firmware lama tetap kompatibel).
- Verifikasi: `python3 -m unittest discover fall_detection/tests` → 54 OK
  (12 di antaranya tes v3 baru); `test_csi_recorder_server.py` → 11 OK
  (rewrite untuk kontrak dua-file, termasuk test penolakan field v2 dan
  no-partial-write); `node tools/tests/csi_recorder.test.js` → 96 PASS exit 0;
  blok script HTML lolos parse (`new Function`, 0 error); smoke test browser
  sungguhan (subagent playwright, port 8777): 0 console error, 8 opsi
  aktivitas benar, pre/post-action `fall_forward` dan collapse `walking`
  benar, audio status `ACTIVE · AudioContext: running`
  (`.playwright-mcp/recorder_panel.png`). State pasca-hapus diverifikasi:
  `find recordings/ -type f | wc -l` → 2 (`.gitkeep`, `README.md`).
  **NOT RUN:** recording end-to-end dengan perangkat nyata (ESP32 tidak
  tercolok saat sesi); validasi meta `csi_period_ms` pada take v3 pertama
  masih butuh perangkat.

## 2026-10-31 — Kompaksi CSI valid_data dibuat first_word_invalid-aware (patch esp-radar)

- Agent/tool: Qoder
- Branch/commit: default / belum di-commit
- File: `examples/esp-radar/wifi_sensing_demo/esp-radar/` (salinan vendored
  esp-radar 0.3.4 yang kini di-track git; `src/esp_radar.c` di-patch),
  `examples/esp-radar/wifi_sensing_demo/main/idf_component.yml`,
  `examples/esp-radar/wifi_sensing_demo/managed_components/espressif__esp-radar`
  (dihapus agar tidak duplikat komponen), `tools/csi_recorder.js`,
  `fall_detection/train_activity_model.py`,
  `fall_detection/tests/test_csi_compaction.py` (baru).
- Perubahan: `copy_subcarrier_data()` sekarang menerima `range_count` dan
  `bool first_word_invalid`. Ketika flag true, rentang byte yang menyentuh
  offset 0..3 di-clamp agar mulai dari byte 4 (`start = (stop<=4)?stop:4`);
  rentang yang sudah mulai ≥4 tak tersentuh, dan entri padding nol
  menyempit jadi panjang 0 lalu di-skip. Semua call-site (lltf count 2; ht_ltf,
  stbc_ht_ltf, he_ltf, stbc_he_ltf count 4) meneruskan
  `info->first_word_invalid`. Akibatnya payload `valid_b64` untuk layout
  ESP32 secondary NONE (`.lltf={{76,128},{2,54}}`, int8) kehilangan satu
  pasangan terdepan: `lltf_len` 104→102 dan `valid_len` 328→326. JS hanya
  meneruskan byte firmware apa adanya (tidak ada pemotongan di browser);
  metadata `PAYLOAD_SEMANTICS` diperbarui dengan `lltf_source_ranges` +
  aturan clamp. Reader ML memotong LLTF berdasar `lltf_len` (bukan tetap
  52), menerima layout nominal dan nominal−2, dan `extract_window_features`
  menurunkan lebar dari frame (tetap 16 band fitur). `raw_b64` tidak diubah.
- Alasan: reproduksi pada recording nyata `20261031T012305Z_walking_001`
  (304 frame): seluruhnya `first_word_invalid=true`, `data_type=0`,
  `raw_len=384`, `valid_len=328`, dan `valid[52:54]==raw[2:4]` pada 304/304
  frame. Karena int8 menyimpan imajiner+real 2 byte/pasangan, byte 2-3
  (raw pair 1) masih di dalam empat byte pertama yang didokumentasikan
  invalid — jadi `valid_b64` lama menyisipkan data invalid dan memunculkan
  garis artefak pada heatmap di posisi subcarrier tersebut. Perbaikan harus
  di sumber pembentukan (tabel esp-radar), bukan menghapus indeks 26 di
  viewer; tidak ada zero-padding atau nilai pengganti yang dibuat.
- Dokumen: ESP-IDF v5.5.3
  `/home/azri/.espressif/v5.5.3/esp-idf/components/esp_wifi/include/local/esp_wifi_types_native.h:123`
  — "first four bytes of the CSI data is invalid or not, true indicates the
  first four bytes is invalid due to hardware limitation". esp-radar 0.3.4
  `src/csi_sub_carrier_table.c:50` — `.lltf = {{76, 128}, {2, 54}}` (sumber
  kebocoran hanya pada baris secondary NONE; BELOW/ABOVE mulai dari byte 12).
- Verifikasi: `idf.py build` exit 0, "Project build complete", bin 0xecf00
  (7% free); `compile_commands.json` mengompilasi
  `esp-radar/src/esp_radar.c` (vendored, override `override_path: ../esp-radar`
  resolve benar) dan `copy_subcarrier_data` ada di `libesp-radar.a`. Suite:
  `python3 -m unittest discover fall_detection/tests` → 66 OK (12 di antaranya
  `test_csi_compaction.py`: clamp true mengeksklusi byte 0-3, dropping hanya
  pasangan invalid, pasangan lain cocok mapping sumber, `valid_len` actual 326,
  raw tak berubah, jalur false tetap 328, layout BELOW tak terpengaruh);
  `test_csi_recorder_server.py` → 11 OK; `node tools/tests/csi_recorder.test.js`
  → 96 PASS 0 FAIL exit 0. Fixture hex diturunkan langsung dari frame 0
  recording nyata. **Diverifikasi di perangkat:** `idf.py -p /dev/ttyUSB0 flash`
  exit 0 ("Hash of data verified"), lalu re-record walking
  `20261031T143755Z_walking_001` (224 frame): seluruhnya `lltf_len=102`,
  `valid_len=326`, kebocoran `val[52:54]==raw[2:4]` = 0/224, raw pair 0/1 tidak
  ada di LLTF, mapping LLTF/HT/STBC cocok byte-exak, `raw_b64` tetap 384 B, tetap
  dua file. `audit_dataset.py` melaporkan 163 subcarrier untuk take ini (vs 164
  pada take firmware lama). Reader ML: 224 frame lebar 51 → 17 baris × 16 fitur.


