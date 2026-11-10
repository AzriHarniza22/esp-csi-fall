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

## 2026-10-31 — Selector mode stimulus HTTP-vs-Ping + mutual exclusion + meta.stimulus

- Agent/tool: Qoder (AI agent)
- Branch/commit: default / belum di-commit
- File: `examples/esp-radar/wifi_sensing_demo/main/ht_stimulus.{h,c}`,
  `main/web_serial_monitor.{c,h}`, `main/app_main.c`,
  `tools/csi_recorder.js`, `tools/web_serial_monitor.html`,
  `tools/tests/csi_recorder.test.js`
- Perubahan: menambah selector stimulus dua mode yang saling eksklusif untuk
  eksperimen perbandingan HTTP-vs-Ping (`docs/perbandingan-http-vs-ping.md`).
  Mode (`off` / `http_cloudflare` / `icmp_ping`) disimpan di `web_serial_monitor`
  dan hanya diterapkan lewat satu choke point `apply_stimulus_mode()` yang selalu
  menghentikan kedua sumber sebelum menjalankan satu-satunya yang dipilih.
  `app_main.c` tidak lagi menyalakan ping FSM atau HTTP sendiri: `sensing_start()`,
  `sensing_rebind_ap()` memanggil `web_serial_monitor_link_up_apply_stimulus()`,
  dan jalur disconnect memanggil `web_serial_monitor_link_down_stop_stimulus()`.
  Mode default saat link up adalah `off` (bukan HTTP) sampai perintah
  `SET_STIMULUS_MODE` masuk. Ping memakai API FSM `esp_wifi_sensing_fsm_*` yang
  sudah ada (resolusi gateway otomatis, tanpa sesi esp_ping kedua). HTTP kini
  menghasilkan penghitung terukur (`ht_stimulus_stats_t`: requests, burst_success,
  burst_failed, bytes_requested/received, active/idle_ms, errors) yang di-reset
  tiap mode diterapkan agar cakupannya per-take; callback CSI menambah
  `csi_ap_frame_count` khusus peer AP. `send_stimulus_state()` mengirim field
  top-level lama (backward compatible) plus obyek bersarang `http{}`/`ping{}`;
  metrik ping yang tidak dis surface FSM (`ping_request_count`, `rtt_ms`, dll.)
  dikirim `null` disertai `metrics_reason`, bukan diisi dari konfigurasi.
  Recorder mengirim `SET_STIMULUS_MODE` di awal take dan `GET_STIMULUS` sebelum
  menulis meta, lalu menyimpan snapshot akhir ke blok `meta.stimulus` (v3).
- Alasan: audit Fase 1 menemukan `sensing_start()` menjalankan ping FSM
  (`esp_wifi_sensing_fsm_ping_router_start`) dan `ht_stimulus_start()` bersamaan,
  melanggar syarat mutual exclusion §4/§5/§16; eksperimen A/B butuh tepat satu
  sumber stimulus per take dengan counter terukur. Counter dibuat terukur (bukan
  turunan konfigurasi) karena §7 melarang nilai di-backfill dari config. Klaim
  lama di `ht_stimulus.h` bahwa "ping replies ... yield no CSI" justru jadi
  hipotesis yang diuji eksperimen, jadi jalur ping dihidupkan lewat API resmi
  alih-alih dipatok mati.
- Dokumen: esp_wifi_sensing 0.1.1
  `managed_components/espressif__esp_wifi_sensing/include/esp_wifi_sensing.h:495-508`
  — "Start internal router ping ... resolves the STA gateway automatically and
  starts an endless ping session" (+ `ESP_ERR_INVALID_STATE` bila gateway belum
  siap); `:383-396` — `esp_wifi_sensing_fsm_set_ping_frequency_hz()` "If
  ping-assisted sampling is already running, the ping session is restarted with
  the new frequency ... Must be greater than 0". ESP-IDF v5.5.3
  `examples/get-started/csi_recv_router/main/app_main.c:183` `wifi_ping_router_start()`
  — pola target gateway (hanya metode stimulusnya yang diadopsi; konfigurasi CSI
  LLTF-only contoh TIDAK dipakai, proyek tetap LLTF+HT+STBC).
- Verifikasi: `idf.py build` exit 0, "Project build complete",
  `wifi_sensing_demo.bin` 0xed810 (7% free), `ht_stimulus.c` +
  `web_serial_monitor.c` tercompilasi ulang bersih. `python3 -m unittest discover
  -s fall_detection/tests` → 66 OK. `node tools/tests/csi_recorder.test.js` →
  99 PASS 0 FAIL (3 uji baru blok `meta.stimulus`: default null, nilai terukur
  dipertahankan, counter ping tetap null ber-alasan). `test_csi_recorder_server.py`
  → 11 OK. Inline `<script>` `web_serial_monitor.html` lolos `node --check`.
  **Diuji di perangkat:** `idf.py -p /dev/ttyUSB0 flash` exit 0 ("Hash of data
  verified"), konsol UART berjalan pada 921600 baud
  (`CONFIG_ESP_CONSOLE_UART_BAUDRATE`). Smoke test serial membuktikan: boot bersih
  tanpa panic, AP connected (gateway 192.168.1.1), default `GET_STIMULUS` =
  `mode=off, running=false` (tidak ada co-run saat boot),
  `SET_STIMULUS_MODE icmp_ping 100` -> `mode=icmp_ping_gateway, running=true,
  configured_frequency_hz=100, configured_interval_ms=10.0, target_ip=192.168.1.1`
  dengan counter ping `null` + `metrics_reason` (bukan diisi dari config), ack
  `off -> icmp_ping_gateway`, lalu `SET_STIMULUS_MODE off` -> ack
  `icmp_ping_gateway -> off`. Fase 4 (rekaman penuh HTTP vs Ping 50/100 Hz,
  >=5 repetisi) masih dijalankan pengguna.

## 2026-10-31 — Rekaman HTTP + probe A/B + laporan komparasi stimulus (Fase 4-6)

- Agent/tool: Qoder
- Branch/commit: default / belum di-commit
- File: `examples/esp-radar/wifi_sensing_demo/recordings/empty_room/*`
  (5 take HTTP via server recorder),
  `examples/esp-radar/wifi_sensing_demo/reports/stimulus_comparison/experiment_20261031/`
  (`probe_ab.py`, `analyze.py`, `report.md`, `summary.csv`,
  `detailed_metrics.csv`, `experiment_manifest.json`, `plots/` 15 grafik,
  `raw/probe_*.json|log`).
- Perubahan: Tidak ada perubahan kode runtime. Menjalankan Fase 4-6 spec
  `docs/perbandingan-http-vs-ping.md`: (1) merekam 5 take HTTP lewat harness
  serial sementara yang memakai protokol HMSCMD/HMS: asli lalu membangun
  frames.csv+meta.json lewat modul `tools/csi_recorder.js` asli dan POST ke
  `tools/csi_recorder_server.py` (harness sementara sudah dihapus); (2) probe
  A/B `off -> icmp_ping 50 -> icmp_ping 100 -> http -> off` yang menyimpan
  transkrip mentah sebagai bukti lengan Ping; (3) analyzer yang menghitung
  metrik timing/PHY/amplitudo/fase/repeatability dan 15 plot wajib dari file
  recording saja.
- Alasan: Spec §8 mengasumsikan Ping menghasilkan CSI. Pengamatan menyanggah:
  pada ESP32 classic + AP `f8:73:1a:59:23:f4`, `ping_reply_hz` terukur 50,50/100,00
  (ping terkirim & dibalas gateway) TETAPI `csi_ap_frame_count` delta = 0 dan
  `esp_radar_csi_rx_cb` tidak melihat event RX dari AP kita selama fase Ping.
  HTTP menghasilkan ~31 fps usable (5 take: 303-308 frame, payload 100% utuh,
  0 drop; korelasi profil amplitudo antar-take r=0,963-0,998). Diskriminator
  terukur = ukuran/jenis frame data HT (802.11n) dari AP, bukan ada/tidaknya
  trafik; frame kecil ICMP dan beacons latar tidak memicu tap CSI. Temuan
  robustness baru: re-apply `SET_STIMULUS_MODE http_cloudflare` saat burst lama
  masih berjalan kalah-balik -> task mati (`burst_failed=1, running=False,
  requests=0`), 2 dari 7 apply; dicatat sebagai kandidat perbaikan
  `apply_stimulus_mode()` (di luar scope, tidak diubah).
- Dokumen: `espressif__esp_wifi_sensing` 0.1.1
  `managed_components/espressif__esp_wifi_sensing/include/esp_wifi_sensing.h`
  — "resolves the STA gateway automatically and starts an endless ping session"
  (API ping FSM); ESP-IDF v5.5.3 `wifi_csi` (urutan komponen I/Q imajiner lalu
  real, `first_word_invalid`). Spec internal `docs/perbandingan-http-vs-ping.md`
  §9-§17 untuk daftar metrik & struktur laporan. Tidak ada dokumen eksternal
  yang menyatakan Ping wajib menghasilkan CSI pada hardware ini.
- Verifikasi: `probe_ab.py` (pyserial idf5.5 env, /dev/ttyUSB0 @921600) ->
  `ap_frames_delta`: off=0, icmp_ping_50=0, icmp_ping_100=0, http=476, off_after=0;
  transkrip tersimpan di `raw/`. `analyze.py` (numpy 2.3.5 + matplotlib 3.10.8)
  exit 0 -> 15 plot + summary.csv + detailed_metrics.csv + manifest. Audit
  `python3 fall_detection/audit_dataset.py recordings/empty_room` -> 5/5 eligible,
  163 subcarrier/take. 5 take HTTP POST ke server -> HTTP 200 (2 take 0-frame
  dari race apply ditolak server dengan benar: "frames.csv has no data rows").
  Device ditinggalkan `mode=off`, CSI stream berhenti.

## 2026-10-31 — Audit forensik read-only: penyebab ping router tak menghasilkan CSI

- Agent/tool: Qoder
- Branch/commit: default / belum di-commit
- File: `examples/esp-radar/wifi_sensing_demo/docs/investigasi-wifi-sensing-demo-ping-csi.md` (baru). Tidak ada file kode yang disentuh.
- Perubahan: Tidak ada perubahan runtime. Menambahkan laporan investigasi
  14 bagian yang menelusuri jalur ping & CSI dan membandingkan
  `wifi_sensing_demo` vs `csi_recv_router` vs `console_test` pada tingkat
  konfigurasi + lifecycle.
- Alasan: `analisis-metode-ping.md` meminta audit read-only atas gejala
  terukur (ping `ping_reply_hz=50,50/100,00` tetapi `rx=` callback = 0 selama
  fase ping). Temuan: jalur ping identik (`esp_ping data_size=1`) sehingga
  H2 ditolak; `rx++` ada di entry callback driver (`esp_radar.c:949`) sehingga
  H3/H5/H8 ditolak; pembeda sesungguhnya adalah konfigurasi
  `wifi_csi_config_t` — `csi_recv_router` LLTF-only (komentar resmi
  "compatibility of routers") vs default esp-radar HT-LTF+STBC. Klasifikasi
  H1/H6 = INDIKASI KUAT (belum TERBUKTI; butuh eksperimen satu-variabel).
- Dokumen: `espressif__esp_wifi_sensing` 0.1.1~3
  `managed_components/.../src/esp_wifi_sensing.c:847-869` — `esp_ping` FSM
  (`data_size=1`, `count=0`, `interval_ms=1000/hz`) identik dengan
  `csi_recv_router/main/app_main.c:183-204`; `esp-radar` 0.3.4
  `esp-radar/include/esp_radar.h:398-404` — default `htltf_en=true,
  ltf_merge_en=false, channel_filter_en=false`; `csi_recv_router` komentar
  `app_main.c:130-132` — "In order to ensure the compatibility of routers,
  only LLTF sub-carriers are selected." MCP espressif-docs/context7 tidak
  tersedia; thread `unknown csi bug` (esp32.com t=20005) gagal dibuka
  (bot-check) sehingga hanya jadi indikasi lemah.
- Verifikasi: audit statis read-only (grep/Read) + tabel A/B dari
  `experiment_20261031`. Tidak ada flash, recording, atau perubahan
  `main/`/`tools/`/`sdkconfig*`/`managed_components/`/patch esp-radar.

## 2026-11-01 — Eksperimen A: flash `csi_recv_router` unmodified + capture serial

- Agent/tool: Qoder
- Branch/commit: default / belum di-commit
- File: artefak eksperimen baru di
  `examples/esp-radar/wifi_sensing_demo/reports/eksperimen_A/`
  (`README.md`, `source_hashes.txt`, `expA.defaults`, `expA_capture.py`,
  `expA_analyze.py`, `parsed_csi_rows.csv`, log mentah `raw_expA_run*.log` +
  `raw_hashes.txt`, `main_firmware_restore_hashes.txt`, build out-of-tree di
  `build/`). Addendum §15 ditambahkan ke
  `examples/esp-radar/wifi_sensing_demo/docs/investigasi-wifi-sensing-demo-ping-csi.md`.
  **Tidak ada file kode yang dimodifikasi**: pohon
  `examples/get-started/csi_recv_router` bersih (`git status --porcelain`
  kosong; sha256 tercatat), `main/` firmware utama, patch `esp-radar` LOCKED,
  dan HTTP Cloudflare tidak disentuh.
- Perubahan: tidak ada perubahan runtime firmware utama. Flash firmware
  `csi_recv_router` standalone (build ESP-IDF v5.5.3, out-of-tree, kredensial
  via `expA.defaults` eksternal — hanya
  `CONFIG_EXAMPLE_CONNECT_WIFI/SSID/PASSWORD`) ke ESP32-WROOM-32 yang sama,
  lalu capture log serial Diagnostic (tanpa dataset recording). Eksperimen B
  tidak diizinkan dan tidak dijalankan.
- Alasan: menguji hipotesis H1 (perbedaan `wifi_csi_config_t` LLTF-only vs
  default esp-radar sebagai penyebab ping→0CSI) pada rig yang sama. Hasil:
  contoh resmi LLTF-only pun hanya menghasilkan ≈10 frame `CSI_DATA` selama
  ~145 s aktif (≈0,07 Hz) vs beban ping 100 Hz — jeda antar callback skala
  detik, bukan ~10 ms, campuran sig_mode legacy+HT, semua dari BSSID AP
  `f8:73:1a:59:23:f4`. Kesimpulan: H1 **bukan penyebab tunggal**; konfig
  paling "router-compatible" versi Espressif pun tidak mengubah balasan ping
  menjadi CSI pada rig ini. Penjelasan dominan bergeser ke H6 (balasan ping
  tidak masuk jalur ekstraksi CSI). Power save aktif (`pm type=1`) dicatat
  sebagai confound kandidat untuk eksperimen berikutnya.
- Dokumen: `csi_recv_router/main/app_main.c` (commit `3ac4a35`) `:166-174` —
  konfigurasi LLTF-only `lltf_en=true, htltf_en=false`; `:178-180` — urutan
  `set_csi_config`→`set_csi_rx_cb`→`set_csi(true)` semua `ESP_ERROR_CHECK`;
  `:183-204` — `esp_ping count=0, interval_ms=1000/100, data_size=1`, target
  gateway; `:217-220` — connect→csi_init→ping; contoh **tidak** memakai
  promiscuous (grep bersih). Kredensial SSID diverifikasi via `HMSCMD
  WIFI_INFO` pada perangkat hidup sebelum dipakai (SSID `"kos mutiara "`
  dengan trailing space, bssid cocok eksperimen) — bukan tebakan dari NVS.
- Verifikasi: build OK v5.5.3 target esp32; flash + boot bersih →
  `got ip:192.168.1.56 gw:192.168.1.1` + header `CSI RECV` tercetak ⇒
  ketiga API CSI mengembalikan `ESP_OK` (ESP_ERROR_CHECK tidak panic).
  10 baris `CSI_DATA` termuat parser (`parsed_csi_rows.csv`): len=128,
  first_word_invalid=1, RSSI −58…−63 dBm. Kehidupan STA dibuktikan terpisah:
  ping host → 192.168.1.56 membalik (seq s/d ~393, RTT ≈ 6 ms). Prosedur
  pemulihan firmware utama **didokumentasikan, belum dieksekusi** — perangkat
  masih menjalankan `csi_recv_router`; hash artefak utama tersimpan di
  `main_firmware_restore_hashes.txt` (`wifi_sensing_demo.bin b17fd292…`).

## 2026-11-01 — Restore firmware utama ke ESP32 setelah Eksperimen A

- Agent/tool: Qoder
- Branch/commit: default / belum di-commit
- File: artefak log baru di
  `examples/esp-radar/wifi_sensing_demo/reports/eksperimen_A/`
  (`restore_verify.py`, `raw_restore_boot.log`, `raw_restore_hmscmd.log`,
  `raw_restore_wifi_info.log`, `restore_flash_hashes.txt`); §6 README file itu
  diperbarui dari "belum dieksekusi" menjadi "dieksekusi + hasil". Tidak ada
  file kode/sumber/konfigurasi yang berubah: flash hanya menulis ulang binari
  yang sudah ada di `build/`.
- Perubahan: memulihkan ESP32-WROOM-32 dari `csi_recv_router` (Eksperimen A)
  ke firmware utama `wifi_sensing_demo`. Flash dengan `idf.py -n` (NO-BUILD —
  varian dari prosedur README §6, sengaja supaya binari yang di-hash pasti
  yang di-flash; tidak ada compile ulang), ESP-IDF v5.5.3, `/dev/ttyUSB0`,
  baud 921600, offset persis `build/flash_args` (0x1000 bootloader, 0x20000
  app, 0xa000 partition-table).
- Alasan: user menyetujui restore (ketentuan 1–10). Pra-check: SHA-256 tiga
  artefak `build/` dicocokkan dengan `main_firmware_restore_hashes.txt` —
  cocok 3/3 (`wifi_sensing_demo.bin b17fd292…`), mtime Oct 31 22:43 lebih
  tua dari eksperimen ⇒ binari identik dengan sebelum Eksperimen A, bukan
  hasil build ulang dengan source/konfigurasi berbeda.
- Dokumen: prosedur restore §6
  `examples/esp-radar/wifi_sensing_demo/reports/eksperimen_A/README.md` —
  "idf.py -C examples/esp-radar/wifi_sensing_demo -p /dev/ttyUSB0 -b 921600
  flash" + "kirim HMSCMD GET_STIMULUS dan pastikan mode=off"; prefix
  perintah `HMSCMD ` dari `main/web_serial_monitor.c:39,1241-1246`
  percobaan pertama tanpa prefix tidak direspons (bukti parsing, bukan
  tebakan).
- Verifikasi: esptool `Hash of data verified.` (3/3 region). Boot log:
  `Project name: wifi_sensing_demo`; `connected with kos mutiara , aid=3,
  channel 11, BW20, bssid=f8:73:1a:59:23:f4`; `got ip 192.168.1.56
  rssi=-59`; `HMSCMD WIFI_INFO` → state GOT_IP + `ack ok=true`; `HMSCMD
  GET_STIMULUS` → `mode=off` + `ack ok=true`. Boot tunggal (0 reboot
  tambahan selama observasi 12 s; uptime ts_ms 128105→140091 terus naik);
  0 marker Guru Meditation/abort/Backtrace. Smoke recording tidak dijalankan
  (tidak disetujui). Perangkat kembali ke keadaan pra-Eksperimen A.

## 2026-11-01 — Rencana instrumentasi korelasi ping↔CSI (audit read-only)

- Agent/tool: Qoder
- Branch/commit: default / belum di-commit
- File: `examples/esp-radar/wifi_sensing_demo/docs/rencana-instrumentasi-ping-csi-correlation.md`
  (baru). Tidak ada file kode/`sdkconfig`/`dependencies.lock`/patch esp-radar/
  HTTP yang disentuh. Tidak ada build, flash, reset, recording, atau Eksperimen B.
- Perubahan: dokumen perancangan 16 bagian untuk mengaudit apakah callback CSI
  terkait ICMP Echo Reply, dan mengapa laju callback ≈0,07 Hz vs ping 100 Hz.
  Tidak mengubah perilaku runtime — hanya memetakan API & merancang instrumen.
- Alasan: instruksi user (fase audit + perencanaan, DILARANG implementasi).
  Temuan audit: (1) `wifi_csi_info_t` IDF 5.5.3 sudah menyimpan `dmac`,`rx_seq`,
  `payload`,`payload_len`,`hdr`; firmware utama **sudah** meneruskan
  `dmac`/`rx_seq`/`ts_us`/`local_timestamp` (web_serial_monitor.c:609-625) sehingga
  sisi CSI siap, gap sesungguhnya di sisi ping (`hms_ping_on_success` hanya
  count++, esp_wifi_sensing.c:804-811, tanpa timestamp/seqno per-reply). (2)
  `ESP_PING_PROF_REQUEST` = hitungan `sendto()` lolos stack IP, **bukan** bukti
  transmisi radio (ping_sock.c:74-85). (3) Loop `esp_ping` sekuensial & blokir
  `recvfrom` sampai `timeout_ms=1000` default (ping_sock.c:170-188) → laju
  efektif dibatasi RTT/timeout. (4) `rx_ctrl.timestamp` 32-bit µs, wrap ~71,6
  menit, dan "precise only if modem/light sleep tidak aktif" (native header :64)
  → gabungkan pakai `esp_timer_get_time()`. (5) Atap korelasi on-device =
  Level 2 (statistik) + kandidat Level 3; Level 4 butuh capture 802.11 eksternal
  + dekripsi. Power save (`pm type=1`) & throttle `csi_stream_period_ms` dicatat
  sebagai confound utama 0,07 Hz.
- Dokumen: `lwip` v5.5.3 `ping/ping_sock.h` — `on_ping_success` "Invoked by
  internal ping thread when received ICMP echo reply packet" (:38), profil
  SEQNO/REQUEST/REPLY (:94-104); `esp_wifi` v5.5.3
  `include/local/esp_wifi_types_native.h` — `wifi_csi_info_t` dmac/rx_seq/payload
  (:119-130), `timestamp ... precise only if modem sleep or light sleep is not
  enabled` (:64). Semua nomor baris diverifikasi via grep/Read, bukan tebakan.
- Verifikasi: audit statis (Read/Grep header IDF 5.5.3 + source repo). Tidak ada
  flash/uji perangkat baru; angka eksperimen (0,07 Hz; 1,7–11,6 s; pm type=1;
  rx=0 selama ping) diambil dari `reports/eksperimen_A/` & hasil A/B firmware
  utama yang sudah ada. Tidak ada klaim one-to-one; payload tidak diasumsikan
  plaintext (tidak terverifikasi — di blob).

## 2026-11-01 — Revisi desain rencana instrumentasi ping↔CSI (dokumentasi saja)

- Agent/tool: Qoder
- Branch/commit: default / belum di-commit
- File: `examples/esp-radar/wifi_sensing_demo/docs/rencana-instrumentasi-ping-csi-correlation.md`
  (koreksi internal §1/§3/§4/§7/§9/§10/§14/§15 + bagian baru **§17** dengan 8
  sub-bagian). Tidak ada file sumber/`sdkconfig`/`managed_components` yang diubah.
- Perubahan: merevisi **perancangan** sebelum persetujuan Prioritas 1, menjawab
  11 poin tinjauan user. Tidak mengubah perilaku runtime.
- Alasan (keputusan desain, bukan kode):
  (1) **Producer-consumer:** ada **dua** produser (callback CSI di task RX Wi-Fi +
  callback ping di task "ping"), jadi buffer bersama **salah** dilabeli SPSC →
  dipilih **satu FreeRTOS queue** multi-producer (`xQueueSend(...,0)`, konsumen
  `xQueueReceive`); dua ring SPSC terpisah didokumentasikan sebagai alternatif.
  (2) **Sinkronisasi statistik:** `esp_ping_get_profile` tak ber-lock
  (ping_sock.c:363-414) → profil per-probe **hanya** dibaca **di dalam** callback
  (task ping); statistik periodik dari **counter aplikasi** di bawah
  `portENTER_CRITICAL`, **bukan** baca profil lintas-task dari task diagnostik;
  implementasi IDF tak diubah. (3) **Counter:** API publik **tidak** menyediakan
  `scheduled` → dipakai definisi `configured_interval_ms`,
  `request_accepted_by_stack` (=PROF_REQUEST, bukan OTA), `echo_reply_received`,
  `success_callback_count`, `timeout_callback_count`, `in_flight`,
  `unresolved_or_unaccounted`. (4) **Timeline CSI:** karena `csi_stream_period_ms`
  membuat stream ter-*log* hanya **subset** callback
  (web_serial_monitor.c:555-560), dipilih **Pilihan B** — event metadata ringkas
  di-**entry** callback **sebelum throttle**; laju pakai `csi_frame_count`.
  (5) **Power save:** dipisah menjadi dua pertanyaan (efek ke presisi timestamp
  terdokumentasi vs efek ke jumlah callback **belum terbukti**); diuji sebagai
  kondisi **terpisah**, tak digabung Prioritas 1. (6) **Beacon/legacy:** `sig_mode`
  hanya menandakan mode PHY, bukan tipe frame MAC; klasifikasi mgmt/data/control
  butuh type/subtype header yang belum tervalidasi; tak berasumsi beacon 10 Hz.
  (7) **Level 3/4:** `dmac==me`+`rx_seq` = **kandidat**, payload **tidak**
  diasumsikan plaintext; Level 4 **belum dibuktikan**, bukan dinyatakan mustahil;
  bukti penentu = verifikasi semantik runtime `payload`. (8) **Buffer:** ukuran
  dihitung dari struktur (csi 32 B / ping 24 B → item queue 32 B), N awal 256
  (8 KB), throughput serial (92.160 B/s @921600, ±85 B/event → ±1.084 ev/s);
  buffer penuh → drop-newest + counter overflow, callback tak pernah blok/IO/heap.
  (9) **Source-of-truth:** diverifikasi `esp_wifi_sensing` = registry
  (dependencies.lock:78-103) & `managed_components/**` **di-git-ignore**
  (`git check-ignore` positif) → salinan itu hasil resolusi Component Manager,
  edit in-place akan tertimpa; strategi tahan-lama = **vendor `override_path`**
  mengikuti pola esp-radar (main/idf_component.yml). (10) **Kontrak recording:**
  dipertahankan (hanya frames.csv + meta.json, kolom tetap, tanpa events.csv,
  HTTP tak berubah, esp-radar LOCKED); event diagnostik = aliran log serial, bukan
  dataset; meta.json simpan counter skalar → pertumbuhan O(1).
- Dokumen: `lwip` v5.5.3 `apps/ping/ping_sock.c` — `transmitted++` hanya saat
  `sendto` penuh (:74-85), pencocokan reply id+seqno (:123), `get_profile` memcpy
  tanpa lock (:363-414); `esp_wifi` v5.5.3 `esp_wifi_types_native.h` — `rx_seq`
  uint16 (:129), `payload_len` uint16 (:128), `timestamp` 32-bit "precise only if
  modem/light sleep tidak aktif" (:64). Verifikasi sumber: `git check-ignore`
  pada `managed_components/espressif__esp_wifi_sensing/src/esp_wifi_sensing.c`
  = IGNORED; `dependencies.lock` esp-radar `type: local` vs esp_wifi_sensing
  `registry_url`. Semua nomor baris diverifikasi via Read/grep, bukan tebakan.
- Verifikasi: **dokumentasi saja** — tidak ada build/flash/reset/recording/
  eksperimen; perubahan diverifikasi dengan Read ulang blok target + grep
  konsistensi (tak ada lagi klaim "SPSC untuk buffer bersama", "Level 4 mustahil",
  "scheduled tersedia", atau power-save sebagai penyebab dominan).

## 2026-11-01 — Persistensi event Ping & CSI ke meta.json (dokumentasi saja)

- Agent/tool: Qoder
- Branch/commit: default / belum di-commit
- File: `examples/esp-radar/wifi_sensing_demo/docs/rencana-instrumentasi-ping-csi-correlation.md`
  (bagian baru **§18** dengan 9 sub-bagian; koreksi §9 intro/CSI_CALLBACK/
  DIAGNOSTIC_STATUS, §15, §16, §17.4-ujung, §17.5-consumer, §17.6). Tidak ada
  source/`sdkconfig`/`managed_components`/kode recorder yang diubah.
- Perubahan: merevisi **perancangan penyimpanan event** sebelum persetujuan
  Prioritas 1; tidak mengubah perilaku runtime.
- Alasan: draf §17.6 sebelumnya hanya menyimpan **counter skalar O(1)** di
  meta.json dan mengirim event sebagai log serial sementara. Ini **tidak
  memenuhi** tujuan akhir (korelasi temporal Ping↔CSI **setelah** recording)
  karena agregat tidak dapat menggantikan **timestamp tiap event**. Direvisi agar
  **event individual dipersistenkan ke `meta.json`** sambil **mempertahankan
  kontrak tepat dua file** (frames.csv + meta.json, tanpa events.csv/sidecar,
  kolom frames.csv tetap). Keputusan & bukti (semuanya dari kode nyata):
  (1) `meta.events` sudah ada sebagai slot (csi_recorder.js:535) → `ping` +
  `csi_diag` + `meta.session_stats` ditanam di sana tanpa file baru.
  (2) Rekonsiliasi via `callback_timestamp_us` (kolom #26 FRAMES_HEADER,
  csi_recorder.js:575-583) = clock `esp_timer` perangkat; himpunan **disjoint**:
  callback masuk **salah satu** frames.csv (lolos throttle) ATAU csi_diag
  (dropped), tidak diduplikasi.
  (3) Format ringkas = kolom + delta timestamp µs + enum numerik + MAC 12-hex;
  rekonstruksi absolut = base + Σdelta (presisi valid, delta < 10⁷ µs < 2⁵³).
  (4) Ukuran per-event: ping ~28 B (kolom) vs ~80 B (objek), csi_diag ~64 vs ~150;
  take 10 s @100 Hz worst ~73 KB; 300 s ~2,2 MB — di bawah **plafon POST server
  32 MiB** (csi_recorder_server.py:301); TARGET_DURATION_S=10 (js:51) sebagai
  panjang standar; soft-cap MAX_EVENTS_PER_TAKE + `truncated`/loss counter.
  (5) UART 921600 **8N1** = 10 bit/byte → 92.160 B/s mentah; **bukan** jatah
  event penuh: frames CSI ±14,4 KB/s → residual ±77,7 KB/s → ±860–900 event/s.
  (6) Queue MPSC 256×32 B (8 KB); backlog 256/R (2,33 s @110 Hz … 0,256 s @1 kHz);
  risiko throttle tab latar (web_serial_monitor.html:641).
  (7) **Persistensi Ping per-event bergantung Prioritas 1** — saat ini FSM ping tak
  memancarkan result callback (recorder `stimulus.ping.metrics_reason` js:486;
  `hms_ping_on_success` count-only esp_wifi_sensing.c:804-811) → butuh vendoring
  `override_path` (§17.7); tanpa itu `seqno_valid=false`/null (prinsip
  buildMetaV3:415 "tak tersedia = null, bukan tebak").
  (8) Router recorder memisah tegas: **hanya** `msg.type==="csi"` menyentuh
  `csiRecorder.frames` (html:4247,4265, gate phase==="recording" :4259) → tipe
  `"diag"` baru tak dianggap frame; akumulator event di-gate & di-reset per take.
  File/fungsi yang kelak diubah didaftar §18.9 (web_serial_monitor.c emit; esp_wifi_sensing
  callbacks; web_serial_monitor.html handleMessage:4228 + finalize:3127/3179;
  csi_recorder.js events:535; server toleransi ukuran). Keputusan §17 (MPSC,
  profil-di-callback, counter aplikasi, power-save belum terbukti, dmac/rx_seq
  kandidat, override_path, esp-radar LOCKED, HTTP tetap) **dipertahankan**.
- Dokumen: tidak ada dokumen eksternal baru; dasar = kode repo terverifikasi
  (baris di atas dibaca via Read/grep hari ini). Prinsip dua-file & clock
  perangkat mengikuti komentar spesifikasi recorder (csi_recorder.js:6-8,410-411).
- Verifikasi: **dokumentasi saja** — tidak ada build/flash/reset/recording/
  eksperimen; cek konsistensi grep (tak ada lagi "metadata O(1)" sebagai
  keputusan final; §17.5 diarahkan ke §18.6 agar tak memakai seluruh baud).

## 2026-11-01 — Final design review §18: boundary sesi, loss per-tahap, validasi memori/UART (dokumentasi saja)

- Agent/tool: Qoder
- Branch/commit: default / belum di-commit
- File: `examples/esp-radar/wifi_sensing_demo/docs/rencana-instrumentasi-ping-csi-correlation.md`
  (sub-bagian baru **§18.10–§18.17**; koreksi §9 pointer, §17.5
  nama counter + struktur ber-`diag_seq`, §18.1 kolom `ds`+`epoch`, §18.6,
  §18.7, §18.8, §18.9, diagram §18.9, §16 jalur device). Tidak ada
  source/`sdkconfig`/`managed_components`/kode recorder yang diubah.
- Perubahan: memfinalisasi **perancangan boundary recording, akuntansi
  kehilangan event, dan validasi estimasi** sebelum persetujuan Prioritas 1;
  tidak mengubah perilaku runtime.
- Alasan: review menemukan batas take saat ini ditentukan **host**
  (`captureStartMono = performance.now()`, web_serial_monitor.html:2554; gate
  `phase==="recording"` :4259 — waktu **kedatangan**, bukan **generate**),
  sehingga lima race terbuka (event pra-start tiba pasca-gate; stop saat queue
  terisi; event di serial saat finalisasi; straggler take lama; latensi
  ping≠CSI). Audit jalur aktual (html:1603-1629,2538-2609,4228-4345,4527-4570;
  web_serial_monitor.c:38,51,123,430-465,543,555-575,700,1239; csi_recorder.js
  :51,419,535; server :301) menghasilkan keputusan:
  (1) **Boundary device-side**: `epoch` per take di-echo device, ditempel ke
  tiap record hanya setelah `HMSCMD TAKE_BEGIN`; jendela `start_ts_us ≤
  ts_us ≤ end_ts_us` (esp_timer) — `phase` saja eksplisit **tidak cukup**
  (§18.10).
  (2) **Barrier start/stop** via `send_ack`/`handle_command` yang sudah ada:
  `TAKE_BEGIN`/`TAKE_END` (drain queue → ack + `queue_pending`); timeout
  ±2000 ms / disconnect → `boundary_unconfirmed`, dua file tetap ditulis
  (§18.11).
  (3) **Loss per-tahap terpisah** (bukan satu `event_overflow_count`): A
  `diag_queue_overflow_count`, B1 `truncated_msg_count` (sudah ada, .c:449),
  B2 `serial_short_write_count`, C1 `browser_parse_error_count` (kini
  parse-fail hanya di-log, html:4566), D `browser_event_truncated_count`; C2
  (bytes hilang saat host stalled) **tidak langsung terukur** — hanya via gap
  `diag_seq`, dilaporkan `unaccounted` (§18.12).
  (4) **`diag_seq` uint32** assign-before-enqueue + tiga high-water
  (assigned/enqueued/emitted) untuk bucketing gap; wrap 2^32 (~86 hari @550/s,
  mustahil per-take); reboot di-scope per `epoch` (§18.13).
  (5) **Identitas rekonsiliasi CSI — enam counter**:
  (`csi_callback_count = frame_callback_count + csi_diag_event_count +
  csi_diag_queue_overflow_count + csi_transport_loss_count +
  browser_event_loss_count + unaccounted`); `csi_dropped_count` device kini
  menggabungkan throttle+oversize (.c:555-575) → **harus dipecah** agar
  terukur (§18.14).
  (6) **Memori dihitung ulang dari struktur**: dengan `diag_seq` item queue
  ≈36–40 B (align4/align8), **bukan 32 B** ⇒ N=256 ≈ ±10,4 KB heap;
  stack task diagnostik 2048–4096 B [estimate, ukur via
  `uxTaskGetStackHighWaterMark` pasca-kode] (§17.5, §18.15).
  (7) **UART dari serialisasi aktual**: 921600 8N1 = 92.160 B/s; baris
  ping ≈114 B / csi_diag ≈164 B (`HMS:` + newline, TX_BUF 4096 sudah cukup
  per baris); frames CSI ±14,4 KB/s lebih dulu → residual ±77,7 KB/s →
  **±550–575 event/s aman**, bukan seluruh baud jadi jatah diagnostik; kongesti
  terdeteksi via growth `queue_pending`/`diag_seq_enqueued_max`
  −`diag_seq_emitted_max` (§18.6, §18.16).
  (8) **Meta vs plafon 32 MiB** (server:301): baris kolom+delta+`ds` ping
  ≈34 B / csi_diag ≈72 B; 10 s ≈≤90 KB; 300 s worst events ≈±2,5 MB + frames
  ≈4,3 MB ≈ **±7 MB** < 32 MiB; `MAX_EVENTS_PER_TAKE=100.000` berdasar target
  ≤±6 MB ÷ 72 B; truncation tercatat, finalisasi tak gagal diam, tepat dua
  output (§18.17).
- Dokumen: tidak ada dokumen eksternal baru; semua angka dari konstanta kode
  nyata (TX_BUF 4096 .c:51, prefix `HMS:` .c:38, 32 MiB server:301,
  TARGET_DURATION_S=10 js:51) — bukan asumsi; angka `sizeof`/stack ditandai
  **[estimate]** sampai diukur pasca-implementasi sesuai aturan "jangan
  menebak angka".
- Verifikasi: **dokumentasi saja** — tidak ada build/flash/reset/recording/
  Eksperimen B; grep konsistensi final (tak ada lagi `ev_dropped`/`queue_overflows`
  lama, diagram "256×32B" sudah "256×≈40B", §18.8 merujuk §18.12–§18.14,
  §18.1 memuat `ds`+`epoch`).

## 2026-11-01 — Konsistensi teknis final §18: barrier dua jalur, epoch universal, diag_seq out-of-order, UART per kelas (dokumentasi saja)

- Agent/tool: Qoder
- Branch/commit: default / belum di-commit
- File: `examples/esp-radar/wifi_sensing_demo/docs/rencana-instrumentasi-ping-csi-correlation.md`
  (rewrite §18.10–§18.11, §18.13, §18.16; tambahan §18.12 titik B0/F, §18.14
  `frame_tx_drop_count`, sub-bagian baru **§18.18**; koreksi §17.5, §18.1,
  §18.6, §18.7, §18.9 diagram, §18.17, Status). Tidak ada
  source/`sdkconfig`/`managed_components`/kode recorder yang diubah.
- Perubahan: memfinalisasi barrier STOP, cakupan epoch, semantik `diag_seq`,
  dan kapasitas UART sebelum persetujuan Prioritas 1; tidak mengubah perilaku
  runtime.
- Alasan: review menemukan empat inkonsistensi desain: (1) barrier lama hanya
  menguras MPSC queue, padahal **jalur kedua sudah ada di firmware** — frame
  lolos throttle ditulis inline dari callback dengan `s_tx_lock` sendiri
  (web_serial_monitor.c:565-567 ambil lock 50 ms, :599-625 susun baris,
  :630-640 fwrite+give) sehingga drain queue tidak menjamin quiescence jalur
  itu. (2) epoch lama hanya menempel record `csi`/`diag` dengan gate `phase`
  browser — frame dan state transisi tak terdefinisi. (3) `diag_seq` lama
  mengimplisitkan urutan datang = urutan nomor, salah untuk MPSC dua producer.
  (4) angka "±550–575 ev/s aman" memakai ukuran baris lama (114/164 B,
  MAC colon-format) dan mencampur kelas. Keputusan final:
  (a) **Barrier 7 langkah** (§18.11): closing flag + `end_ts_us` atomik
  (portMUX), `s_inflight` per-producer, quiescence `s_inflight==0` (±500 ms
  [estimate]), drain MPSC, **ambil `s_tx_lock`+fflush** (bukti tak ada penulis
  aktif di kedua jalur), STOP ACK di bawah lock yang sama dengan
  `barrier_ok`/`queue_pending`/`inflight_at_close`; gagal ⇒
  `boundary_unconfirmed`, bukan klaim nol-loss. Delapan jaminan review
  terpenuhi tercatat per langkah.
  (b) **Epoch numerik uint32 di semua record** termasuk frame CSI lewat field
  JSON `"eq":N` — tidak dipetakan ke `frames.csv` (32 kolom tetap; server
  validasi kolom tak tersentuh); mesin state browser
  `idle→starting→recording→stopping→finalized`: buffer mulai dibuka sebelum
  `TAKE_BEGIN`, pesan epoch-cocok ditampung pra-ACK, akumulator tidak ditutup
  sampai STOP ACK; jendela `start_ts_us≤ts_us≤end_ts_us` clock perangkat;
  timeout ±2000 ms/putus ⇒ `boundary_unconfirmed` + dua file tetap ditulis.
  (c) **`diag_seq`**: increment aman-konkurensi (critical section), assign
  tetap sebelum enqueue; **urutan datang ≠ urutan seq bukan loss** — browser
  buffer by ID `(boot_id, epoch, ds)` lalu sort; **gap hanya dihitung setelah
  STOP ACK** dengan watermark `diag_seq_assigned_max` (3 high-water
  assigned/enqueued/emitted untuk bucketing A/B/C); **cakupan hanya stream
  MPSC** — frame jalur langsung tidak bernomor urut (rekonsiliasi via
  counter §18.14, bukan sequence); reset **per boot** + `boot_id` acak saat
  init (reboot ≠ gap; gap di-scope per `(boot_id, epoch)`); wrap 2^32 ≈146
  hari @340/s — mustahil per-take, aritmetika selisih uint32 cukup.
  (d) **UART per kelas dengan margin operasional 25%** (§18.16): ukuran baris
  penuh dihitung ulang dari template literal (`HMS:` 4 B + newline + `eq` +
  `ds` + MAC 12-hex): ping ±112 B tipikal/±135 worst; csi_diag ±171/±185.
  Residual operasional 0,75×77,7 ≈ **58,3 kB/s** ⇒ **ping-saja ±520/s,
  csi_diag-saja ±340/s**, campuran @50 Hz ping ±308 ev/s csi_diag tambahan; klaim tunggal
  550–575 **ditarik** di semua bagian (§17.5/§18.6/§18.7/§18.17 ikut
  direvisi). csi_diag = maks(0, R−forwarded); observasi R≈0,07 Hz ⇒ beban
  aktual jauh di bawah plafon.
  (e) **Temuan kode baru saat audit barrier**: `write_line` gagal ambil lock
  return 0 **tanpa pencacatan** (:426-428) → counter baru
  `serial_tx_lock_timeout_count` (titik B0); `csi_dropped_count` ternyata
  menampung **empat** alasan (throttle :560, oversize :563, lock-timeout
  :566, base64 :575/:590) → pecahan `frame_tx_drop_count` masuk identitas
  §18.14 (titik F). Semua kehilangan kini terbedakan A/B0/B1/B2/F/C1/D atau
  dilabeli tidak-terukur (C2 inferens gap; ekor unconfirmed → `unaccounted`).
- Dokumen: tanpa dokumen eksternal baru; semua nomor baris diverifikasi via
  Read/sed hari ini (web_serial_monitor.c :426-428, :430-465, :558-590,
  :600-640); angka UART = aritmetika 8N1 + template baris, seluruhnya
  **[estimate]** sampai `strlen` aktual diukur — bukan angka terukur.
- Verifikasi: **dokumentasi saja** — tidak ada build/flash/reset/recording/
  Eksperimen B; grep final: nol karakter CJK tersisa, tidak ada lagi angka
  550–575 sebagai klaim (hanya kutipan penarikan), `frame_tx_drop_count`/
  `serial_tx_lock_timeout_count`/`boot_id` konsisten; daftar verifikasi
  §18.18 + keterbatasan tersisa (quiescence bounded, overhead critical
  section, `"eq"` +6–11 B/baris frame, pemecahan `csi_dropped_count` sebagai
  prasyarat implementasi).




## 2026-11-01 — Verifikasi final ronde 3 §18: race drain-vs-ACK, semantik fsync UART, ukuran frame aktual (dokumentasi saja)

- Agent/tool: Qoder
- Branch/commit: default / belum di-commit
- File: `examples/esp-radar/wifi_sensing_demo/docs/rencana-instrumentasi-ping-csi-correlation.md`
  (§18.11 langkah 4–6 + paragraf gagal; §18.12 catatan B0; §18.13 semantik
  high-water + wraparound; §18.18 rewrite daftar ronde 3 + keterbatasan (a)–(f);
  koreksi angka di §17.5, §18.6, §18.7, §18.9 diagram, §18.17, Status). Tidak
  ada source/`sdkconfig`/`managed_components`/kode recorder yang diubah.
- Perubahan: memverifikasi tiga klaim desain terhadap source dan data recording
  sebelum persetujuan Prioritas 1; tidak mengubah perilaku runtime.
- Alasan: tiga temuan verifikasi:
  (1) **Race drain-vs-ACK dikonfirmasi mungkin** — queue kosong tepat setelah
  drain task dequeue item terakhir (belum memegang `s_tx_lock`), STOP task
  mendapat lock lebih dulu dan mengirim ACK, lalu drain menulis event lama
  setelahnya ⇒ `queue_pending == 0` **tidak cukup**. §18.11 langkah 4 kini
  menuntut `uxQueueMessagesWaiting() == 0` **DAN** `drain_inflight == 0`
  (counter consumer-side, naik saat dequeue, turun setelah transmit selesai),
  dan langkah 6 mengirim ACK di bawah `s_tx_lock` yang sama dengan langkah 5 —
  event in-flight hanya bisa menyusup sebelum ACK bila ia memegang lock, dan
  lock itu sudah dipegang prosedur STOP.
  (2) **Semantik UART diverifikasi dari source IDF v5.5.3**
  (`components/esp_driver_uart/src/uart_vfs.c`), bukan asumsi: proyek ini
  non-driver mode (`CONFIG_ESP_CONSOLE_UART_CUSTOM=y` UART0, `sdkconfig:1183`–
  :1192; `esp_vfs_dev_uart_use_driver()` tidak ada di `main/`). `uart_tx_char`
  (:185-194) busy-wait mendorong byte ke FIFO TX HW (≤128 B ≈ ±1,4 ms tail
  @921600) ⇒ **`fflush()` hanya membuktikan byte masuk FIFO, bukan keluar ke
  wire**. Mekanisme tunggu fisik yang benar di mode ini adalah `uart_fsync`
  (:405-411) → `esp_rom_output_tx_wait_idle`, terjangkau via
  `fsync(fileno(stdout))` — dipakai di langkah 5. `tcdrain`→`uart_wait_tx_done`
  (:1001-1013) hanya valid mode driver; `tcflush(TCOFLUSH)` output tidak
  didukung (:1028). ACK di bawah lock+fsync yang sama ⇒ ACK record terakhir
  epoch; jaminan gagal ⇒ `boundary_unconfirmed`.
  (3) **Ukuran pesan CSI aktual membantah estimasi lama** — audit emitter
  (`web_serial_monitor.c:600-640`) + recording terukur
  (`recordings/empty_room/20261031T162727Z_…_007.frames.csv`: `raw_len` 384 dan
  `valid_len` 326 **konstan** min/med/max — base64 512+436 = 948 char/frame;
  308 frame/10,0 s = **30,8 FPS**; baris CSV avg=P95=max=**1.130 B**): klaim
  lama ±14,4 kB/s (480 B/frame) **ditarik**; baris wire frame ±1,44 kB
  [estimate strlen, dijangkar CSV 1.130 B] ⇒ ±44,5 kB/s pada 30,8 FPS.
  Kapasitas dihitung ulang: residual 92,16−44,5 = ±47,7 kB/s; operasional
  0,75× ≈ ±35,8 kB/s ⇒ **ping-saja ±320/s, csi_diag-saja ±210/s, campuran
  @50 Hz ping ±177/s & @100 Hz ±144/s csi_diag tambahan**; gabungan terburuk
  ±67,7 kB/s ≈ 73% duty. Skenario A (throttle 100 ms ≤10 FPS, frames 14,4 kB/s)
  tetap dicantumkan bersyarat (±520/±340). §18.7 backlog ±1,2 s; §18.17 worst
  300 s ≈ ±10,4 MB CSV + ±2,5 MB events ≈ ±13 MB < 32 MiB (headroom ±2,4×).
  (4) **Semantik high-water `diag_seq` diluruskan** (§18.13): assigned-high-water
  **bukan** bukti ter-enqueue; enqueued-high-water **bukan** bukti semua di
  bawahnya berhasil; emitted-high-water **bukan** bukti browser menerima.
  Atribusi lokasi kehilangan **hanya** dari counter per-tahap (A
  `diag_queue_overflow_count`, B0 `serial_tx_lock_timeout_count`, B1
  `truncated_msg_count`, B2 `serial_short_write_count`, F `frame_tx_drop_count`,
  C1 `browser_parse_error_count`, D `browser_event_truncated_count`) +
  watermark final + himpunan ID diterima; `unaccounted = (assigned_max −
  rentang epoch) − diterima − A − B − C − D` dan **tidak diklaim
  terlokalisasi**. Cakupan tetap hanya stream MPSC. Wraparound diperbarui ke
  kelas ±210/s ⇒ ±229 hari.
- Dokumen: source lokal ESP-IDF **v5.5.3**
  `/home/azri/.espressif/v5.5.3/esp-idf/components/esp_driver_uart/src/uart_vfs.c`
  (:185-194, :405-411, :1001-1013, :1028 — dibaca langsung, bukan dokumentasi
  v6.0); tidak ada dokumen eksternal baru.
- Verifikasi: **dokumentasi saja** — tidak ada build/flash/reset/recording/
  Eksperimen B/perubahan source. Angka terukur dari file recording yang sudah
  ada di repo (bukan eksperimen baru): FPS, raw_len/valid_len, ukuran baris
  CSV. Semua ukuran baris wire tetap **[estimate]** sampai `strlen` aktual
  direkam. Grep final: nol karakter CJK, tidak ada lagi klaim 14,4 kB/s tanpa
  konteks bantahan; daftar ronde 3 + keterbatasan (a)–(f) tercatat di §18.18.



## 2026-11-01 — Verifikasi final ronde 4 §18.11: admission atomik, reserve-before-dequeue, deadlock ACK (dokumentasi saja)

- Agent/tool: Qoder
- Branch/commit: default / belum di-commit
- File: `examples/esp-radar/wifi_sensing_demo/docs/rencana-instrumentasi-ping-csi-correlation.md`
  (§18.11 ditulis ulang menjadi dua bagian — I protokol admission + II urutan
  STOP 7 langkah + blok `drain_inflight` + choreografi lock + makna
  `boundary_confirmed`; §18.18 judul→"ronde 3–4" + baris 7/8/9 + paragraf
  `boundary_confirmed` + keterbatasan (g); paragraf Kompatibilitas §18.11;
  Status). Tidak ada source/`sdkconfig`/`managed_components`/kode recorder yang
  diubah.
- Perubahan: menutup dua race konkurensi + satu deadlock sebelum implementasi;
  tidak mengubah perilaku runtime.
- Alasan: dua race + satu bug yang dikonfirmasi terhadap source:
  (1) **Admission tidak atomik** — ronde-3 memecah "baca closing/epoch" dan
  "naikkan `s_inflight`" menjadi dua langkah terpisah, meninggalkan jendela
  TOCTOU (baca aktif → STOP lihat `s_inflight==0` → callback naikkan → enqueue
  pasca-barrier). §18.11 bagian I memformalkan SATU critical section
  `s_epoch_mux` yang mengerjakan check-closing + snapshot-epoch + `++s_inflight`
  atomik terhadap set `s_closing` STOP ⇒ hanya dua interleaving (diterima &
  terhitung, atau `epoch=0` ditolak); **tak ada titik antara pemeriksaan epoch
  dan registrasi in-flight**.
  (2) **`drain_inflight` dinaikkan SETELAH dequeue** — ronde-3 ("increment saat
  drain MENGAMBIL item") masih ber-jendela: `xQueueReceive` kembali, queue
  kosong, konter belum naik, STOP lihat `drain_inflight==0` → ACK → item lama
  terbit. §18.11 kini **reserve SEBELUM dequeue** (`++drain_inflight` di bawah
  `s_epoch_mux` yang sama dengan uji STOP `queue==0 && drain_inflight==0`);
  valid karena drain **konsumen tunggal** MPSC. Barrier-watermark 8-langkah
  (usulan review) **dibandingkan & ditolak** untuk saat ini: setara jaminannya
  tapi butuh state bersama ekstra; dipilih `drain_inflight` sebagai yang paling
  sederhana yang bebas-race menurut konkurensi aktual; watermark jadi opsi bila
  muncul konsumen kedua.
  (3) **Deadlock ACK (bug nyata di source)** — `send_ack()` (:698-704) memanggil
  `write_line()` yang mengambil `s_tx_lock` (:426); langkah "ACK di bawah lock
  yang sama" ronde-3 = take rekursif semaphore biner non-rekursif ⇒ deadlock /
  timeout 50 ms hilang ACK. Solusi terdokumentasi: refactor `write_line_locked()`
  (inti tanpa take/give) + `send_ack_locked()`; ACK ditulis via jalur itu saat
  lock dipegang, give **sekali**.
  (4) **Choreografi lock diverifikasi:** semua penulis `stdout` (drain, frame
  langsung :565-640, ACK) memakai satu `s_tx_lock`; `s_epoch_mux` (spinlock)
  selalu dilepas sebelum `s_tx_lock` diambil ⇒ tak ada lock-order inversion;
  `fwrite` (buffer stdio) ≠ `fflush` (→ FIFO HW) ≠ `fsync` (→ TX idle) dibedakan;
  `boundary_confirmed` dipersempit ke "lengkap dari **device**", bukan "browser
  punya" (bukan kerugian pasca-UART-RX §18.13 C/D).
  (5) **Throughput ronde-3 dipertahankan** — 44,5 kB/s & 320/210 ev/s ditegaskan
  sebagai **estimasi** (panjang pesan × FPS terukur), panjang wire **belum**
  diukur `strlen()`, kapasitas pakai worst-case; **14,4 kB/s tetap ditarik**.
- Dokumen: source ESP-IDF **v5.5.3** `/home/azri/.espressif/v5.5.3/esp-idf`
  (uart_vfs.c, sudah diverifikasi ronde-3); `main/web_serial_monitor.c`
  (:414, :420-465, :565-640, :698-704) — dikonfirmasi **tidak ada**
  `portENTER_CRITICAL`/`portMUX` di file ⇒ `s_epoch_mux` primitive BARU;
  konteks task (bukan ISR) disimpulkan dari `s_tx_lock` timeout :565-567.
- Verifikasi: **dokumentasi saja** — tidak ada source/build/flash/reset/
  recording/Eksperimen B. Grep final: nol karakter CJK; nol kebocoran kata
  Inggris; rujukan langkah silang (§18.9 diagram, §18.13 "langkah 6") konsisten
  dengan penomoran baru; daftar ronde 3–4 + keterbatasan (a)–(g) tercatat di
  §18.18. Keterbatasan baru (g): bebas-race bergantung asumsi konsumen-tunggal
  & konteks-task, dan `s_epoch_mux`/`write_line_locked()`/`send_ack_locked()`
  belum ada — argumen desain, divalidasi hanya saat konkurensi diuji di
  perangkat (belum dilakukan).



## 2026-11-01 — Klarifikasi final ronde 5 §18.11/§18.16: consumer-ack drain + nested-spinlock FreeRTOS + safety margin atas TOTAL (dokumentasi saja)

- Agent/tool: Qoder
- Branch/commit: default / belum di-commit
- File: `examples/esp-radar/wifi_sensing_demo/docs/rencana-instrumentasi-ping-csi-correlation.md`
  (§18.11 langkah-3 + blok drain ditulis ulang jadi consumer-ack + catatan
  verifikasi ronde-5 + choreografi + boundary_confirmed + payload ACK +
  Kompatibilitas; §18.16 tabel kapasitas + definisi margin; koreksi angka di
  §17.5, §18.6, §18.7, §18.17, §18.13 wraparound, §18.18 baris 1/4/9/10 +
  keterbatasan (h), §18.9 diagram, Status). Tidak ada
  source/`sdkconfig`/`managed_components`/kode recorder yang diubah.
- Perubahan: memverifikasi mekanisme drain terhadap FreeRTOS sebenarnya dan
  mengoreksi definisi safety margin UART; tidak mengubah perilaku runtime.
- Alasan: dua klarifikasi yang diminta:
  (1) **`uxQueueMessagesWaiting()` TIDAK aman di dalam `s_epoch_mux`** —
  [SRC] `freertos/FreeRTOS-Kernel/queue.c:2306-2319`: fungsi ini sendiri memanggil
  `taskENTER_CRITICAL(&xQueue->xQueueLock)`, jadi memanggilnya sambil memegang
  `s_epoch_mux` = nested dua spinlock `portMUX` berbeda; dan
  `xQueueReceive(...,portMAX_DELAY)` di dalam critical section ilegal (bisa
  block/yield). Draf ronde-4 (call `uxQueueMessagesWaiting` di dalam
  `portENTER_CRITICAL`) **dibatalkan**. Final = **consumer-ack**: task drain
  mengobservasi queue di context normalnya, me-**reserve `drain_inflight` sebelum
  `xQueueReceive(...,0)` non-blocking** (aman karena drain = konsumen tunggal:
  item hanya bertambah, jadi receive pasca-observasi dijamin sukses), melepas
  reserve setelah transmit; STOP men-set `flush_requested` + `xTaskNotifyGive`
  lalu menunggu ack `drain_inflight==0 && drain_saw_empty` via
  `s_drain_idle_sem`. Enam poin tinjauan (no-block-after-reserve, lepas saat
  kosong, in-flight tetap aktif s.d. transmit selesai, STOP tak bisa mengaku
  selesai saat item di tangan, STOP bisa membangunkan pemeriksaan akhir) terpenuhi.
  Barrier-watermark tetap ditolak (lebih kompleks; hanya perlu bila konsumen kedua
  muncul).
  (2) **Safety margin 25% dihitung dari KAPASITAS TOTAL, bukan residual** —
  plafon operasional = 0,75 × 92.160 = **69.120 B/s**; dengan trafik frames
  terukur-estimasi **44.500 B/s** (30,8 FPS, fakta FPS/panjang frame TIDAK diubah)
  ⇒ **budget diagnostik = 69.120 − 44.500 = 24.620 B/s**. Dibagi ukuran
  **worst-case** (ping 135 B, csi_diag 185 B): **ping-saja ±182/s** (24.620/135),
  **csi_diag-saja ±133/s** (24.620/185), **campuran @50 Hz ping ±96/s** csi_diag
  ((24.620−6.750)/185), **@100 Hz ±60/s** ((24.620−13.500)/185). Beban gabungan
  terburuk = 44.500 + 24.620 = **69.120 B/s = tepat 75% duty**. Angka lama
  margin-pada-residual (35,8 KB/s) & ukuran tipikal (112/171) ⇒ ±320/±210, dan
  skenario throttle (520/340) **digantikan/dihitung ulang** (A: budget 54.720 B/s ⇒
  ping ±405, csi_diag ±295). Semua ditegaskan **estimasi aritmetika**, bukan
  `strlen()` runtime maupun uji throughput. §18.13 wraparound ikut (±210→±133 ⇒
  ±374 hari); §18.7 backlog 256 @±133/s ≈ ±1,9 s.
- Dokumen: source FreeRTOS **IDF v5.5.3**
  `/home/azri/.espressif/v5.5.3/esp-idf/components/freertos/FreeRTOS-Kernel/queue.c`
  (:2306-2319, dibaca langsung — bukan asumsi); `esp_driver_uart/src/uart_vfs.c`
  (ronde-3). Tidak ada dokumen eksternal baru.
- Verifikasi: **dokumentasi saja** — tidak ada source/build/flash/reset/recording/
  Eksperimen B. Grep final: nol CJK; nol kebocoran kata Inggris (sisa hanya istilah
  teknis `assign-before-enqueue`); fence markdown balanced (14); tidak ada lagi
  angka kapasitas ±320/±210/±520/±340 sebagai klaim hidup (hanya kutipan
  "digantikan"/"bukan"); §18.18 baris 1/4/9/10 + keterbatasan (a)–(h) tercatat.
  Keterbatasan baru (h): angka kapasitas tetap estimasi; primitive ack
  (`drain_saw_empty`/`flush_requested`/`s_drain_idle_sem`/`xTaskNotifyGive`) belum
  ada; konsumen kedua memaksa revisi ke barrier-watermark.

## 2026-11-01 — Implementasi Prioritas 1: instrumentasi diagnostik Ping–CSI

- Agent/tool: Qoder
- Branch/commit: default / belum di-commit
- File:
  - `examples/esp-radar/wifi_sensing_demo/esp_wifi_sensing/**` (vendor baru,
    salinan `managed_components/espressif__esp_wifi_sensing`) +
    `include/esp_wifi_sensing.h` + `src/esp_wifi_sensing.c` (hook callback
    per-reply ping).
  - `examples/esp-radar/wifi_sensing_demo/main/idf_component.yml`
    (esp_wifi_sensing → `override_path: ../esp_wifi_sensing`).
  - `examples/esp-radar/wifi_sensing_demo/main/web_serial_monitor.c`
    (mesin diagnostik: MPSC queue, admission, epoch, diag_seq, STOP barrier,
    event `type:"diag"`, refactor `write_line_core`/`write_line_locked`/
    `send_ack_locked`, TAKE_BEGIN/TAKE_END).
  - `examples/esp-radar/wifi_sensing_demo/tools/csi_recorder.js`
    (`createDiagSession`/`diagNoteStartAck`/`diagNoteStopAck`/`diagAcceptEvent`/
    `diagFinalize` + `session_stats`/`boundary` di `buildMetaV3`;
    `metrics_reason` diperbarui).
  - `examples/esp-radar/wifi_sensing_demo/tools/web_serial_monitor.html`
    (routing `type:"diag"`, korelasi ACK `pendingAcks`/`waitForAck`,
    state machine epoch di `runTake`, gating frame by `eq`).
  - `examples/esp-radar/wifi_sensing_demo/tools/tests/diag_session.test.js`
    (baru) + `csi_recorder.test.js` + `test_csi_recorder_server.py` (regresi).
- Perubahan: Menambahkan kemampuan diagnostik tanpa mengubah jalur data yang
  ada. (1) `esp_wifi_sensing` di-vendor via `override_path` mengikuti pola
  `esp-radar`; callback `hms_ping_on_success`/`on_timeout` kini membaca profile
  `esp_ping` (seqno/ttl/size/timegap/ip/request/reply) **di dalam** callback dan
  memanggil hook opsional `esp_wifi_sensing_fsm_register_ping_event_cb`.
  (2) Firmware menjalankan satu queue MPSC `xQueueCreate(256, diag_item_t)`
  dengan satu task drain (`diag_drain`, stack 4096, prio 5) sebagai konsumen
  tunggal; producer ping & csi_diag admission atomik di bawah `s_epoch_mux`
  (portMUX), assign-before-enqueue, lalu `xQueueSend(...,0)` **di luar** mux.
  (3) Event `HMS:{"type":"diag",...}` membawa `bid/e/ds/ts`. (4) Frame CSI
  (jalur direct-write) kini membawa `"eq"`+`"bid"` (bukan `ds`), `csi_dropped_count`
  tetap di-increment agar kolom `dropped` frames.csv tak berubah. (5) STOP
  barrier 7 langkah mengquiescent kedua jalur (inflight==0, consumer-ack
  terikat `flush_generation`, `fflush`+`fsync(fileno(stdout))`), ACK final via
  `send_ack_locked`. (6) Host memodelkan sesi (epoch/boot_id/window/gap/
  out-of-order/soft-cap/stale-ack) dan mempersist event ke `meta.events.ping`/
  `csi_diag` (kolom+delta+enum) + `meta.session_stats` + `meta.boundary`.
- Alasan: Ronde 5 menyimpulkan FSM `esp_wifi_sensing` registry **tidak**
  memancarkan callback hasil per-reply (hanya `count++`), sehingga korelasi
  Ping–CSI per-event mustahil tanpa menyentuh komponen; komponen registry
  di-git-ignore jadi vendoring `override_path` satu-satunya jalur bertahan.
  Barrier + consumer-ack + `flush_generation` dibutuhkan karena device punya
  **dua** jalur keluar (queue + direct-write) dan stop lama adalah gerbang
  host-arrival yang race (§18.10 lima race). Stale acknowledgement eksplisit
  dilarang user (§2) — diikat ke (epoch, gen) di device maupun host.
- Dokumen: source FreeRTOS **v5.5.3**
  `components/freertos/FreeRTOS-Kernel/queue.c:2312` — `uxQueueMessagesWaiting`
  memanggil `taskENTER_CRITICAL(&xQueue->xQueueLock)`, jadi API queue tidak
  boleh dipanggil di dalam `s_epoch_mux` (dibaca langsung). `esp_random.h`
  (`components/esp_hw_support/include/esp_random.h`) kini wajib di-include
  terpisah — pesan build v5.5.3: "esp_random.h header file is not included by
  esp_system.h anymore." `esp_ping` profile `ping_sock.h:94-104`; README
  `esp_wifi_sensing 0.1.1~3`. Kontrak `fsync` non-driver UART dari ronde-3.
- Verifikasi: **build + automated tests saja** — TIDAK ada flash/reset/
  `/dev/ttyUSB0`/command firmware/recording/Eksperimen B.
  `idf.py build` (ESP-IDF v5.5.3, target esp32): **exit 0, nol warning/error**
  pada `web_serial_monitor.c`, biner `0xee900` B, partisi app 7% free.
  `sizeof(diag_item_t)=56` B diukur dengan toolchain xtensa (objdump .data),
  penyimpanan queue `56×256=14336` B (~14 KB) heap + overhead StaticQueue_t.
  Uji host: `node csi_recorder.test.js` 99 PASS, `node diag_session.test.js`
  37 PASS, `python test_csi_recorder_server.py` 12 OK (exit 0). Kontrak dua
  file & 32 kolom frames.csv tetap (test). Bukti `esp-radar` LOCKED tak
  berubah: `git status --short examples/esp-radar/esp-radar` kosong.

## 2026-11-01 — Focused review pasca-implementasi: gate lifecycle TAKE_BEGIN, fallback csi_diag, alokasi diagnostik non-fatal

- Agent/tool: Qoder (review round)
- Branch/commit: default / belum di-commit
- File: `examples/esp-radar/wifi_sensing_demo/main/web_serial_monitor.c`,
  `examples/esp-radar/wifi_sensing_demo/tools/csi_recorder.js`,
  `examples/esp-radar/wifi_sensing_demo/tools/web_serial_monitor.html`,
  `examples/esp-radar/wifi_sensing_demo/tools/tests/diag_session.test.js`,
  `examples/esp-radar/wifi_sensing_demo/tools/tests/test_csi_recorder_server.py`,
  `examples/esp-radar/wifi_sensing_demo/docs/rencana-instrumentasi-ping-csi-correlation.md`
- Perubahan:
  1. **Gate lifecycle TAKE_BEGIN** (`handle_take_begin`): TAKE_BEGIN menolak
     bila take sebelumnya masih terbuka (`take_open:...`, tanpa TAKE_END), dan
     melakukan recovery bounded (poll ≤500 ms, budget sama dengan barrier)
     sampai `queue_pending==0 && s_inflight==0 && s_drain_inflight==0`; bila
     tetap sibuk → ACK `ok:false` dengan reason + snapshot
     (`prev_not_quiescent:queue_pending=N;inflight=N;drain_inflight=N`) TANPA
     mengubah state. `xQueueReset()` kini hanya berjalan SETELAH quiescence
     terbukti (sebelumnya unconditional — bisa memusnahkan event sesi
     `boundary_unconfirmed`). `handle_take_end` menolak TAKE_END tanpa take
     terbuka (`no_open_take`), selalu menutup `s_diag_take_open` di akhir
     (ACK STOP kini membawa `diagnostics_enabled`). Browser (`runTake`):
     START ACK `ok:false`/timeout ⇒ take dilewati dengan pesan reason perangkat
     (`return null` + loop batch `continue`), bukan merekam sesi tanpa atribusi
     perangkat.
  2. **Fallback metadata direct-write failure** (`emit_csi_frame_fallback` +
     `drop_reason`): kegagalan pengiriman frame CSI (tx-lock timeout 50 ms,
     oversized, base64 raw gagal, fwrite short) kini dicerminkan sebagai event
     `csi_diag` minimal TANPA payload raw, dengan `drop_reason`
     (0=throttle,1=tx_lock_timeout,2=oversized,3=base64_fail,4=uart_write_fail)
     dan `seq_id` firmware (`sid`/`dr` di wire; kolom `firmware_seq`/
     `drop_reason` + `drop_reason_enum` di meta). Enqueue selalu DI LUAR
     `s_tx_lock`, non-blocking (timeout 0); kuota fallback ≤160 B vs ±1,44 kB
     frame yang digantikan, dan queue penuh hanya menaikkan
     `diag_queue_overflow` — tidak bisa memicu overload berantai. Struktur
     `diag_item_t` bertambah `seq_id`(u32)+`drop_reason`(u8) tetapi tetap
     **56 B** (mengisi padding; diukur ulang objdump xtensa). Counter lama
     (`csi_dropped_count`, `frame_tx_drop`) tidak berubah; jalur write kini
     mengecek hasil `fwrite` (sebelumnya `(void)`) sehingga short-write CSI
     ikut terhitung. Catatan: di mode non-driver UART, FIFO penuh diam-diam
     menjatuhkan byte dan `fwrite` tetap mengembalikan count penuh — fallback
     `uart_write_fail` hanya terdeteksi bila write benar-benar short; kehilangan
     akibat stall host tetap tidak terdeteksi device (dibatasi §18.13, loss
     dihitung host).
  3. **Alokasi diagnostik non-fatal** (`web_serial_monitor_init`): kegagalan
     `xQueueCreate`/semaphore/`xTaskCreate(drain_task)` tidak lagi membatalkan
     init monitor (sebelumnya mengembalikan `ESP_ERR_NO_MEM`/`ESP_FAIL` dan
     `app_main.c:401` membuang return value → serial monitor mati diam-diam).
     Kini degrasi ke "diagnostics disabled" (`s_diag_queue`/`s_drain_task`
     NULL, semua producer no-op, barrier melewati langkah MPSC,
     `diagnostics_enabled:false` di STOP ACK) dengan `ESP_LOGE` + free heap;
     jalur CSI utama tetap hidup. Stack drain task 4096 B (compile-time,
     `DIAG_DRAIN_TASK_STACK`).
- Alasan: review user pasca-implementasi menemukan tiga cacat: (a) TAKE_BEGIN
  lama memakai `xQueueReset()` buta yang memusnahkan event sesi yang belum
  quiescent (STOP timeout / browser putus saat STOP) dan bisa mencemari sesi
  baru bila drain masih memegang item; (b) frame CSI yang gagal direct-write
  hilang tanpa representasi individual di timeline (hanya counter agregat);
  (c) kegagalan alokasi 14 KB queue membunuh seluruh monitor tanpa ACK — dan
  build lulus tidak membuktikan alokasi runtime lulus.
- Dokumen: `queue.c:2306-2319` v5.5.3 (`uxQueueMessagesWaiting` mengambil
  `xQueueLock` internal — tetap dipanggil hanya di luar `s_epoch_mux`; poll
  recovery TAKE_BEGIN juga memanggilnya di luar mux). `uart_vfs.c:405-411`
  (fsync non-driver, tak berubah). Tidak ada dokumen baru yang diperlukan untuk
  gate lifecycle — ini kontrak protokol internal proyek sendiri.
- Verifikasi: **build + automated tests saja** — TIDAK ada flash/reset/
  `/dev/ttyUSB0`/command firmware/recording/eksperimen Ping/HTTP/Eksperimen B.
  `idf.py build` (v5.5.3, esp32): exit 0, nol warning, biner `0xeec90` B
  (0xee900 → 0xeec90, +912 B), app 7% free. `sizeof(diag_item_t)=56` B
  diukur ulang. Uji host: `csi_recorder.test.js` 99 PASS,
  `diag_session.test.js` **49** PASS (+12: enam matriks gate lifecycle,
  rejection START ACK, round-trip `sid`/`dr` throttle/oversized/
  uart_write_fail, enum drop_reason, wire fallback, loss counter),
  `test_csi_recorder_server.py` 12 OK (test meta round-trip kini membawa
  kolom `firmware_seq`/`drop_reason`). Skrip inline HTML tervalidasi
  `node --check`. Kontrak tetap: dua file, 32 kolom, `esp-radar` LOCKED
  (`git status` kosong), HTTP stimulus tak berubah (diff `ht_stimulus.c`
  tanpa baris URL/HTTP).
## 2026-11-01 — Audit final: rekonsiliasi loss berjenjang, degraded diagnostics, verifikasi STOP ACK

- Agent/tool: Qoder (agent session, ESP-IDF v5.5.3)
- Branch/commit: default / belum di-commit (setelah `3ac4a35`)
- File: `examples/esp-radar/wifi_sensing_demo/main/web_serial_monitor.c`,
  `examples/esp-radar/wifi_sensing_demo/tools/csi_recorder.js`,
  `examples/esp-radar/wifi_sensing_demo/tools/web_serial_monitor.html`,
  `examples/esp-radar/wifi_sensing_demo/tools/tests/diag_session.test.js`,
  `examples/esp-radar/wifi_sensing_demo/tools/tests/test_csi_recorder_server.py`,
  `examples/esp-radar/wifi_sensing_demo/docs/rencana-instrumentasi-ping-csi-correlation.md`
- Perubahan:
  1. **Rumus loss diganti menjadi rekonsiliasi 4 tahap dengan suku saling lepas.**
     Rumus lama `deviceOverflow + max(0, deviceAdmitted - hostReceived) + eventOverflow`
     punya dua cacat: suku tengah tidak bisa membedakan kegagalan TX, item masih
     di antrean, dan kehilangan transport; dan event yang ditolak filter jendela
     dihitung dua kali (sekali di `boundary_ts_rejected`, sekali lagi di dalam
     `deviceAdmitted - hostReceived` karena `hostReceived` memakai baris hasil
     filter). Identitas baru: tahap 1 `assigned = enqueued + queue_overflow`,
     tahap 2 `enqueued = tx_success + tx_failure + pending_at_close`, tahap 3
     `tx_success = browser_received + transport_unaccounted`, tahap 4
     `browser_received = persisted + window_rejected + truncated`, dan
     `diagnostic_event_loss_count = queue_overflow + tx_failure + pending_at_close
     + transport_unaccounted + browser_truncated` (window-rejected bukan loss).
     Counter device baru `diag_emit_failed` (item sudah-enqueued yang gagal tulis
     serial — satu-satunya sumber `diag_tx_failure_count`), field `loss_accounting`
     dengan nama kanonik (`diag_assigned_count`, `diag_queue_enqueued_count`,
     `diag_queue_overflow_count`, `diag_tx_success_count`, `diag_tx_failure_count`,
     `diag_pending_at_close_count`, `transport_unaccounted_count`,
     `browser_received_count`, `browser_received_unique_count`,
     `browser_parse_error_count`, `browser_event_truncated_count`,
     `browser_persisted_count`, `diag_unaccounted_stage1_count`) dan bendera
     `counter_inconsistent` bila counter saling bertentangan — selisih negatif
     ditandai, tidak diam-diam menaikkan loss. Loss yang tidak bisa diidentifikasi
     penyebabnya dilaporkan sebagai `unaccounted`, bukan nol.
  2. **Degraded diagnostics untuk tiga kegagalan alokasi** (`xQueueCreate`,
     semaphore, `xTaskCreate(drain_task)`): `s_diag_disable_reason`
     (`queue_alloc_failed`/`sem_alloc_failed`/`drain_task_create_failed`) kini
     mengalir START ACK → session → `meta.json`
     (`session_stats.diagnostics_unavailable[_reason]`,
     `boundary.diagnostics_enabled:false, diagnostics_unavailable_reason`), dan
     stream `events.ping`/`events.csi_diag` serta metrik turunan device bernilai
     **null, bukan 0**. **Bug ditemukan dan diperbaiki:** di mode degraded,
     `diag_admit_and_enqueue()` tetap mengonsumsi `diag_seq` dan menaikkan
     `diag_queue_overflow` untuk setiap callback CSI saat `s_diag_queue == NULL`
     → loss hantu seukuran seluruh frame CSI + celah sequencer. Diperbaiki dengan
     early-return sebelum `s_epoch_mux`. Browser tidak lagi mengorbankan take:
     START ACK degraded hanya memicu `WARN ... CSI recording continues`.
  3. **STOP ACK memverifikasi transmit secara nyata.** `send_ack_locked()`
     mengembalikan jumlah byte; barrier STOP memeriksa `fflush()` dan
     `fsync(fileno(stdout))` secara terpisah dan melaporkan `fflush_ok`,
     `fsync_ok`, `tx_drained` di ACK; `stop_ack_drained` hanya dihitung bila body
     ACK tertulis lengkap. `write_line_core()` kini menganggap `fflush` EOF sebagai
     write gagal (sebelumnya `fwrite` penuh dianggap sukses meski buffer tidak
     sampai ke wire). Host mewajibkan `ok === true && barrier_ok === true &&
     tx_drained === true` — tanpa satupun flag eksplisit tidak ada konfirmasi, dan
     `boundary.unconfirmed_reason` menyebutkan sebab spesifik
     (`serial_tx_not_drained(fflush_ok=..,fsync_ok=..)`, `mpsc_barrier_incomplete(..)`,
     `stop_ack_missing_drain_flags`, `stop_ack_timeout`, `device_reported_failure`).
     UART TX idle tidak lagi dipakai sebagai bukti browser menerima event — hanya
     bukti wire kosong; penerimaan event diukur host dari counter tahap 3/4.
- Alasan: instruksi audit user §1–§3. Poin (1) dibutuhkan karena laporan loss
  sebelumnya menjumlahkan counter dari tahap berbeda dan tidak bisa menjelaskan
  dari tahap mana kehilangan datang. Poin (2) diuji lewat pembacaan jalur gagal
  alokasi — sebelumnya flag "diagnostics disabled" ada di STOP ACK tetapi tidak
  pernah sampai ke browser/meta, dan jalur admission masih menghitung loss untuk
  queue yang tidak ada. Poin (3) menuntut pemeriksaan return value, dan
  pemeriksaan sumber IDF v5.5.3 menunjukkan `fsync()` pada konsol UART **tidak
  bisa gagal** hari ini (lihat Dokumen), sehingga sinyal kegagalan yang sebenarnya
  adalah short-write `fwrite` dan EOF `fflush` — keduanya kini dihitung.
- Dokumen: `esp_driver_uart` v5.5.3
  `/home/azri/.espressif/v5.5.3/esp-idf/components/esp_driver_uart/src/uart_vfs.c:404-411`
  — "`uart_fsync()` … `esp_rom_output_tx_wait_idle(uart_num); … return 0;`"
  dan `:1146-1152` — "`ESP_SYSTEM_INIT_FN(init_vfs_uart)` (di bawah
  `#if CONFIG_ESP_CONSOLE_UART`) memanggil `uart_vfs_dev_register()`";
  `components/vfs/vfs.c:1118-1130` — "`esp_vfs_fsync` mengembalikan `-1`/`EBADF`
  bila tidak ada VFS yang memiliki fd", `:1861` "`fsync` alias `esp_vfs_fsync`".
  Proyek ini `CONFIG_ESP_CONSOLE_UART=y` + `CONFIG_ESP_CONSOLE_UART_CUSTOM=y`
  (sdkconfig), jadi `fsync()` selalu `0` hari ini; field `fsync_ok` tetap
  dilaporkan agar kegagalan terdeteksi bila VFS berubah. Untuk FreeRTOS:
  `components/freertos/.../task.h` (`xTaskCreate` mengembalikan `pdPASS`/0) dan
  `queue.c` v5.5.3 (`xQueueCreate` → NULL saat OOM). Tidak ada dokumen Espressif
  yang mengatur kontrak ACK internal proyek — tidak ditemukan.
- Verifikasi: **audit fokus + automated tests + build saja** — TIDAK ada
  flash, reset, `/dev/ttyUSB0`, recording, Ping, HTTP experiment, atau
  Eksperimen B. `idf.py build` (v5.5.3, target esp32 klasik): exit 0, biner
  `0xeeff0` B = 978.928 B (0xeec90 → 0xeeff0, +16 B statis; app partition 7%
  free, bootloader 29% free). `main/web_serial_monitor.c` di-touch lalu
  di-compile ulang: 0 baris `warning:` dan 0 `error:`. `sizeof(diag_item_t)=56` B
  diukur ulang dari DWARF ELF. Uji host: `diag_session.test.js` **91 PASS** / 0 FAIL
  (+42: disjointness per tahap, satu event gagal-di-dua-tahap dihitung sekali,
  pending-at-close sekali, `counter_inconsistent`, partisi tahap 4 di semua
  sesi ter-finalize, matriks degraded 3 alasan × assert, lima `unconfirmed_reason`
  spesifik, ACK short-write, 12 pin kontrak sumber firmware),
  `csi_recorder.test.js` 99 PASS / 0 FAIL, `test_csi_recorder_server.py` 13 OK
  (test baru: meta degraded + staged round-trip). `node --check` lulus untuk
  `csi_recorder.js` dan skrip inline HTML (170.405 B). Area terkunci tidak
  berubah: `examples/esp-crab`, `examples/esp-radar/console_test`,
  `examples/get-started`, `fall_detection` → `git status` kosong (0 file);
  vendored `esp_wifi_sensing/` tetap hanya dua file berbeda dari upstream
  (`include/esp_wifi_sensing.h`, `src/esp_wifi_sensing.c` — hook ping dari sesi
  sebelumnya, tidak disentuh audit ini; 21 entri `CHECKSUMS.json`, deviasi 2);
  diff `ht_stimulus.c` tidak memuat baris URL/HTTP.
## 2026-11-01 — Eksekusi hardware: flash P1, smoke test tunggal, A/B regresi image

- Agent/tool: Qoder (agent session, ESP-IDF v5.5.3, `/dev/ttyUSB0` @921600)
- Branch/commit: default / belum di-commit (setelah `3ac4a35`)
- File: `examples/esp-radar/wifi_sensing_demo/docs/rencana-instrumentasi-ping-csi-correlation.md`
  (§22 baru), `docs/agent-changes.md` (entri ini), dan artefak di
  `examples/esp-radar/wifi_sensing_demo/reports/prioritas1_smoke/`
  (`ab_capture.py`, `ab_capture2.py`, `boot_capture.py`, `gui_drive.mjs`,
  5 log `ab_*.log`, 3 log `boot_p1_*.log`, `failed_take_1/`).
  **Tidak ada satu byte pun perubahan di `main/`, `tools/`, `sdkconfig*`,
  `managed_components/`, atau `esp_wifi_sensing/` pada ronde ini** — `git status`
  untuk path itu identik dengan kondisi sebelum eksekusi hardware dimulai.
- Perubahan:
  1. **Flash P1 + rollback teruji.** Image rollback lebih dulu dipulihkan dari
     flash (`read_flash` @0x20000 → 972.816 B, sha256 `b17fd292…6a3`) sebelum
     P1 di-flash, supaya path undo terverifikasi, bukan diasumsikan. P1 =
     978.928 B, sha256 `2679aec7…f88`, `write_flash` + "Hash of data verified".
  2. **Satu smoke recording dijalankan, dan hanya satu.** Take
     `20261101T150906Z_object_drop_001`: `TAKE_BEGIN OK` → `TAKE_END OK` → dua
     file dihasilkan → server **menolak HTTP 400** (`validate_frames_csv`:
     `frames.csv has no data rows`) → fallback unduhan GUI. Artefak diamankan di
     `reports/prioritas1_smoke/failed_take_1/`; `recordings/` tetap 8 entri.
     Boundary-nya **lulus lengkap**: `confirmed=true`, `barrier_ok=true`,
     `tx_drained=true`, epoch 1 / `flush_generation` 1 / `boot_id` 4233061905,
     `queue_pending=0`, `inflight_at_close=0`, 15 counter `loss_accounting.stages`
     = 0, `counter_inconsistent=false`, `diagnostics_enabled=true`. Frames = 0.
  3. **A/B regresi image vs lingkungan.** Flash ulang rollback → 4 capture dengan
     kondisi divariasikan (stream off/on via `SET_CSI_PERIOD 0`+`START_CSI_STREAM`,
     stimulus off vs `icmp_ping 10`, trafik AP→device ~240 ping dari host) →
     flash ulang P1 → capture identik. Hasil: **0 jendela `csi_cb` dengan
     `f8:73:1a:59:23:f4` sebagai sumber di kedua image**; angka terukur
     A1 rx=41/10j, A2 rx=485/21j, A3 rx=99/17j, A4 rx=24/4j, B(P1) rx=126/12j,
     sedangkan referensi lama pada image yang sama di 14:34 UTC rx=354/16j dengan
     **4** jendela ber-AP (`queued=2..5`, `sel ok>0`). P1 bersih dari tuduhan
     regresi; device dibiarkan menjalankan P1 (tanpa restore otomatis, sesuai brief).
  4. **Boot P1 diverifikasi ulang dari log bersih** (reset via pulse RTS, dengan
     `dtr=False, rts=False` sebelum `open()` — membuka port dengan DTR/RTS default
     membuat chip tertahan dan capture menghasilkan 0 baris):
     `diag_queue=256 items x 56 B (diagnostics enabled)`, 0 baris `E (`, 0 `Guru`,
     0 loop, heap 144.140–144.840, Wi-Fi `GOT_IP` bssid `f8:73:1a:59:23:f4`
     channel **1** rssi −56 ip 192.168.1.10. Stack HWM drain task **tidak
     tersedia** (tidak ada yang mem-log `uxTaskGetStackHighWaterMark`) — dilaporkan
     sebagai tidak tersedia, bukan 0.
  5. **Web Serial di view IDE tidak bisa dipakai**: `navigator.serial.requestPort()`
     reject dalam ~1 ms (`elapsed_ms: 1`) tanpa pernah menampilkan chooser
     (Electron `Qoder/1.38.0`). GUI recorder dijalankan di Chrome-for-Testing
     headed via CDP (`gui_drive.mjs`), hanya mengisi form + mengirim klik
     terpercaya; FSM take tetap seluruhnya milik halaman.
  6. Diperbaiki di dokumentasi: satu tabel A/B sempat memuat placeholder `rx=…`
     dan label kondisi A4 (`stream on`) yang tidak cocok dengan skrip yang benar
     dijalankan (`stream off`); keduanya diganti angka/label terukur.
- Alasan: instruksi user §1–§8 (eksekusi hardware) + §6 (berhenti dan laporkan
  saat gagal, tanpa mengulang smoke test). Setelah take pertama menghasilkan 0
  frame, pertanyaan yang tersisa hanyalah "regresi P1 atau lingkungan radio?"
  dan itu hanya bisa dijawab dengan A/B di hardware, bukan dengan membaca source
  lagi. `okmac=` sempat hampir saya baca sebagai "AP match di jendela ini";
  source `esp-radar/src/esp_radar.c:593,718,751` menunjukkan `s_ok_mac` adalah
  global yang **tidak di-reset** per jendela, sehingga nilai itu sisa dari
  jendela sebelumnya — keberatan terhadap interpretasi itu tercatat di §22.3.
- Dokumen: source vendored lokal `esp-radar/src/esp_radar.c` pada build v5.5.3
  ini — `:703` `esp_radar_select_peer()` (exact→wildcard, `s_sel_nopeer++` saat
  tidak ada peer), `:966` `esp_radar_src_count(info->mac)` dipanggil **sebelum**
  seleksi peer (karena itu `srcs{}` = semua MAC yang diserahkan driver, termasuk
  yang ditolak), `:990` `stat_filtered++` hanya setelah peer match. Tidak ada
  dokumen Espressif yang saya buka untuk ronde ini, dan tidak ada klaim perilaku
  driver yang saya ambil di luar log perangkat; untuk pertanyaan "mengapa frame
  AP tidak diserahkan ke callback CSI" jawabannya **tidak ditemukan** — penyebab
  sengaja dibiarkan tidak diketahui, bukan diisi penalaran.
- Verifikasi: semua angka di §22 dan entri ini berasal dari log yang tersimpan di
  `reports/prioritas1_smoke/` (`ab_*.log`, `boot_p1_*.log`, `raw_*.log`) atau dari
  artefak take di `failed_take_1/` (sha256 frames.csv `2fc45ea4…`, meta.json
  `39caba16…`). Tidak ada test suite yang dijalankan ulang (tidak ada perubahan
  kode untuk diuji). Build tidak diulang — biner yang dipakai adalah hasil build
  Prioritas 1 yang seluruh suite-nya lulus (91/99/13) dan hash-nya cocok dengan
  artefak `0xeeff0` = 978.928 B. Yang **gagal** dan dilaporkan apa adanya: syarat
  §3 "CSI callback berjalan" terpenuhi di level callback (`rx>0` dari MAC lain)
  tetapi **tidak** di level frame sensor (`queued=0`, `csi_ap_frame_count=0`), dan
  syarat §5 "tepat dua file di `recordings/`" tidak terpenuhi karena server
  menolak take 0 frame by design. Smoke test kedua, eksperimen Ping 50/100 Hz,
  HTTP Cloudflare, power-save, promiscuous, dan Eksperimen B **tidak** dijalankan.

## 2026-11-02 — Investigasi kompatibilitas AP vs CSI ESP32 classic

- Agent/tool: Qoder (agent session; ESP-IDF v5.5.3; read-only pada perangkat)
- Branch/commit: default / belum di-commit (setelah `3ac4a35`)
- File: **baru** `docs/investigasi-kompatibilitas-ap-csi.md`. `docs/agent-changes.md`
  (entri ini). **Tidak ada perubahan kode** di `main/`, `tools/`,
  `esp_wifi_sensing/`, `esp-radar/`, `sdkconfig*`, atau `managed_components/`;
  tidak ada flash/reset/recording/ubah-router. Perbaikan ping-profile (§4.4) dan
  instrumentasi arah-downlink (§3.5 Opsi B) **dirancang, belum diterapkan** —
  menunggu persetujuan.
- Perubahan: dokumen investigasi yang memisahkan empat lapisan (stack terima →
  promiscuous amati → callback CSI → filter esp-radar) dan menyimpulkan kegagalan
  berpindah ke batas lapisan 2→3 **khusus sumber=AP**; memetakan error
  `unmatched data size for profile 5` ke satu pemanggil; menyusun eksperimen E1.
- Alasan (bukti):
  1. Baseline `recordings/walking/20261031T012305Z_walking_001.meta.json`:
     AP `f8:73:1a:59:23:f4` di **channel 11**, 304 frame, `complete=true`.
     Kondisi starved (A/B 2026-11-01): AP pindah **channel 1**, `srcs{}` hanya
     STA uplink (`48:45:20:ee:be:b1`, `d4:53:2a:61:a2:c1`, `dmac=`AP), `okmac`
     tak pernah AP, `queued=0` — pada **rollback dan P1 identik** (bukan regresi).
  2. Lapisan 1 & 2 hidup: ICMP reply 95/110 @5Hz, `promisc=1`, `promis=52–83`/2s.
     Lapisan 3 mati utk AP: `esp_radar_csi_rx_cb` tak pernah menerima src=AP.
  3. Kelayakan PHY dari source: `sig_mode` (native L41) + `lltf_en`/`stbc_htltf2_en`
     → CSI hanya dari PPDU OFDM (LLTF/HT-LTF); CCK 802.11b tak punya → cocok
     hipotesis watchdog `web_serial_monitor.c:72–81`. Tidak mengklaim satu tipe
     frame sebagai penyebab (downlink-AP `sig_mode` tak terukur; `DL(fromAP)`=0 di
     semua log, termasuk baseline, jadi counter itu tak terhubung ke jalur RX).
  4. Error ping: **671/671** baris `ping_sock` = "profile 5" (IPADDR). Pemanggil
     `esp_wifi_sensing.c:833` kirim `sizeof(ev.ip4_addr)=4` (`uint32_t`,
     `esp_wifi_sensing.h:174`) padahal `ping_sock.c` minta `sizeof(ip_addr_t)`
     (=20 dgn `CONFIG_LWIP_IPV4=y`&`IPV6=y`, sdkconfig:1568–1569) → `size>=copy_size`
     gagal → `ESP_ERR_INVALID_SIZE`. Hanya IPADDR; SIZE/TIMEGAP (uint32_t) benar.
- Dokumen: ESP-IDF v5.5.3 `components/esp_wifi/include/local/esp_wifi_types_native.h`
  L41 "sig_mode … 0: non HT(11bg); 1: HT(11n); 3: VHT(11ac)", L39 "rate … Only valid
  for non HT(11bg)", L97 `lltf_en`, L123 `first_word_invalid … hardware limitation`;
  `components/lwip/include/apps/ping/ping_sock.h` L94–104 (enum IPADDR=5),
  `components/lwip/apps/ping/ping_sock.c` (`copy_size=sizeof(ep->recv_addr)`,
  recv_addr = `ip_addr_t`). Tidak memakai MCP `esp-idf` v6.0 (salah versi).
- Verifikasi: inspeksi source on-disk v5.5.3; ekstrak window `csi_cb`/`csi_preproc`
  dari `reports/prioritas1_smoke/ab_*.log` & `raw_pre_flash_*.log`; baca meta
  baseline; `nmcli`/`iw` read-only (scan aktif butuh root → ditolak, `kos mutiara`
  tak terlihat host hari ini karena host di AP lain — dicatat sebagai keterbatasan,
  §1.3). Tidak ada build/test dijalankan (tak ada perubahan kode).


## 2026-11-02 — Perbaikan Ping IPADDR + instrumentasi PHY downlink (Ronde 2)

- Agent/tool: Qoder
- Branch/commit: default / belum di-commit
- File:
  `esp_wifi_sensing/src/esp_wifi_sensing.c`,
  `main/phy_probe.c` (baru), `main/phy_probe.h` (baru),
  `main/CMakeLists.txt`, `main/web_serial_monitor.c`,
  `docs/investigasi-kompatibilitas-ap-csi.md`, `docs/agent-changes.md`.
- Perubahan:
  1. **Bug IPADDR** (`esp_wifi_sensing.c`): tambah helper
     `hms_ping_read_reply_ip4()` yang membaca `ESP_PING_PROF_IPADDR` ke buffer
     `ip_addr_t` sungguhan (`sizeof` = kontrak), cek `IP_IS_V4_VAL()` sebelum
     `ip4_addr_get_u32(ip_2_ip4(&..))`, dan `static_assert(sizeof(buffer) >=
     sizeof(ip_addr_t))`. Pemanggil lama (`&ev.ip4_addr`, 4 B) diganti helper.
     `#include <assert.h>` + `lwip/ip_addr.h` ditambahkan. Tidak mengubah
     interval/timeout/payload/FSM ping, tidak mengubah CSI config.
  2. **Instrumentasi PHY** (`main/phy_probe.[ch]` + wiring di
     `web_serial_monitor.c`): modul berbatas-tetap yang menempel di hook CSI
     yang sudah ada (`web_serial_monitor_csi_callback`), bukan callback
     promiscuous kedua. Menghitung histogram per kategori arah (from_ap/to_self/
     other), frame-type (best-effort dari `info->info->hdr`), sig_mode/rx_format/
     bandwidth/stbc/aggregation/secondary/rate/mcs/channel/rssi/payload_len, dan
     tabel per-source-MAC × mode. Default **OFF**; diaktifkan via
     `HMSCMD PHYPROBE on|off|get`. Laporan periodik (window 1 s) dari
     `web_serial_monitor_task` lewat `ESP_LOGW` (tag `phy_probe`), bukan stream
     JSON. Snapshot+reset di bawah `portMUX`; callback tetap hanya increment.
  3. **Dok**: §8 Ronde 2 (perbaikan, rancangan, ownership, identifikasi PHY vs
     frame-type, hasil test/build, protokol E1, keterbatasan); flip penanda
     §3.5/§4.4/§7 jadi "DITERAPKAN".
- Alasan:
  - (1) `[TERUKUR]` 671/671 `ping_sock: unmatched data size for profile 5`.
    `[FAKTA-DOK]` `ping_sock.c` menetapkan `copy_size = sizeof(ep->recv_addr)`
    (`recv_addr` = `ip_addr_t`) dan menolak `size < copy_size`. `[FAKTA-SRC]`
    dual-stack (`CONFIG_LWIP_IPV4=y` & `IPV6=y`) ⇒ `sizeof(ip_addr_t)`=20 > 4.
    Field IPADDR redundan (target selalu = gateway; tak ada kolomnya di stream)
    tetapi dibaca dengan benar, bukan dihapus, agar kontrak komponen tak berubah.
  - (2) Menutup celah karakterisasi PHY downlink AP tanpa menyentuh `esp-radar`
    LOCKED. Pemetaan ownership (`esp_radar.c:2023`/`:572`, `esp_radar_promis_cb`)
    menunjukkan slot promiscuous tunggal milik esp-radar → callback kedua DITOLAK
    (mencacatkan akuntansi `csi_preproc` yang dipakai E1). Yang dipasang = varian
    Opsi A pada hook CSI `main/`.
- Dokumen:
  - lwip ping_sock.c ESP-IDF v5.5.3
    `components/lwip/apps/ping/ping_sock.c` —
    "case ESP_PING_PROF_IPADDR: copy_size = sizeof(ep->recv_addr);" +
    "ESP_GOTO_ON_FALSE(size >= copy_size, ESP_ERR_INVALID_SIZE, ..., unmatched
    data size for profile %d)"; `recv_addr` = `ip_addr_t` (baris 46).
  - lwip ip_addr.h v5.5.3 — `IP_IS_V4_VAL`, `ip_2_ip4`; ip4_addr.h —
    `ip4_addr_get_u32`.
  - esp_wifi_types_native.h v5.5.3 — `sig_mode` 0=11bg/1=11n/3=11ac, `rate`
    "Only valid for non HT", `cwb` 0/1, `aggregation` 1-bit, `secondary_channel`
    0/1/2, `rx_seq`, `payload_len`, `first_word_invalid`, `hdr`.
  - docs/en/api-guides/wifi.rst v5.5.3 — ":2717 LLTF/HT-LTF/STBC-HT-LTF",
    ":2768 Except for 802.11g all modes have LLTF + HT/VHT/HE-LTF",
    ":2804 rx_channel_estimate_info_vld", ":2853 callback di Wi-Fi task; STA
    terhubung hanya terima paket dari AP → sarankan sniffer/promiscuous".
  - `esp_wifi_sensing` 0.1.1 (vendored, tidak LOCKED) — sumber edit helper.
  - Tidak memakai MCP `esp-idf` v6.0 (salah versi untuk proyek ini).
- Verifikasi:
  - Node: `csi_recorder.test.js` + `diag_session.test.js` semua PASS (exit 0);
    mencakup serial-protocol parse, frames.csv 32 kolom, meta tepat dua file.
  - Python: `python -m unittest test_csi_recorder_server` → 13 OK.
  - Build ESP32 classic (`idf.py build`, IDF v5.5.3): `BUILD_EXIT=0`, 0 warning
    (satu `-Wtype-limits` pada `aggregation<2` (field 1-bit) diperbaiki jadi
    ternary).
  - `esp-radar` LOCKED: `git status esp-radar/` bersih (nol edit sesi ini).
    Catatan: hash on-disk `esp_radar.c` (5a4aaabc…) ≠ `CHECKSUMS.json`
    (4d414bf2…) = divergensi pre-existing ter-commit, bukan perubahan ronde ini.
  - HTTP Cloudflare tidak disentuh. Skema rekaman tetap 32 kolom/2 file.
  - **Belum** diverifikasi runtime (0 "unmatched data size", efek `phy_probe`) —
    butuh flash, ditunda ke persetujuan terpisah. E1 belum dijalankan.

## 2026-11-02 — Koreksi Ronde 2: `phy_probe` → `csi_phy_probe` (batas observasi)

- Agent/tool: Qoder agent
- Branch/commit: default / belum di-commit
- File: `examples/esp-radar/wifi_sensing_demo/main/phy_probe.c` (dihapus),
  `main/phy_probe.h` (dihapus), `main/csi_phy_probe.c` (baru),
  `main/csi_phy_probe.h` (baru), `main/CMakeLists.txt`,
  `main/web_serial_monitor.c`, `docs/investigasi-kompatibilitas-ap-csi.md`
  (§3.5, §6, §8.2, §8.4, §8.5, §8.6, §8.7)
- Perubahan: **koreksi atas-klaim cakupan**, bukan perubahan perilaku runtime.
  1. Modul diagnostik diganti nama dari `phy_probe` → `csi_phy_probe` (file,
     seluruh simbol, `TAG`, makro `CSI_PHY_PROBE_*`, tipe `csi_phy_probe_*`,
     statis `s_*`), sehingga **nama itu sendiri** menyatakan batas observasinya:
     ia hanya mengamati frame yang **mencapai CSI callback**. Deskripsi di header
     dan komentar sumber sekarang menyatakan hal itu secara eksplisit, termasuk
     bahwa ia **bukan** sniffer promiscuous dan **tidak** melihat frame yang
     ditolak sebelum callback. Token perintah `HMSCMD PHYPROBE` **dipertahankan**
     sebagai alias agar antarmuka serial tidak berubah.
  2. Dokumentasi: statistik **Promiscuous RX** (milik `esp-radar` LOCKED, log
     `[csi_preproc]`, window 2 s) dipisah dari statistik **CSI callback** (milik
     `main/`, log `csi_phy_probe`, window 1 s) dalam tabel dua-domain di §8.2;
     ditambah pernyataan tegas di §8.4/§8.7 bahwa **absennya AP pada counter probe
     bukan bukti tentang PHY AP** (CCK/OFDM/HT) — hanya bukti tidak ada frame AP
     yang sampai ke callback. §3.5 Opsi B ditandai DITOLAK dengan alasannya.
  3. §8.6 (protokol E1) disusun ulang menjadi **Domain A** (promiscuous:
     `promist{m/c/d}`, `psig{}`, tabel src-MAC esp-radar, histogram PHY sebelum
     gerbang CSI; `DL(fromAP)` dicatat dengan peringatan heuristik
     `addr1 == my_mac` yang terbaca 0 bahkan pada baseline) dan **Domain B**
     (CSI callback: `cat_from_ap`, `csi_ap_frame_count`, `queued`, distribusi PHY
     frame layak-CSI). Analisis ditentukan **dua tahap dan tidak dicampur**,
     dengan normalisasi window 2 s vs 1 s sebelum membandingkan, dan aturan
     "bukti H1 harus berasal dari Domain A". §6 (rekomendasi ronde 1) diselaraskan
     agar tidak lagi merujuk histogram Opsi B. Probe **tidak** disebut sebagai
     instrumentasi downlink lengkap.
  4. §8.5 mencatat ketidakcocokan hash apa adanya: on-disk
     `esp-radar/src/esp_radar.c` = `5a4aaabc…` **≠** `CHECKSUMS.json`
     = `4d414bf2…`; ditandai sebagai **kondisi pre-existing yang belum
     direkonsiliasi** (sudah ter-commit sebelum sesi ini) dan **tidak diklaim
     cocok**. Rekonsiliasi (regenerate checksum atau pulihkan sumber upstream)
     adalah keputusan terpisah, belum dilakukan.
  5. **Koreksi fakta tambahan yang ditemukan saat memeriksa klaim Domain A**
     (hanya re-analisis artefak log, tanpa perangkat): klaim ronde 2
     "`DL(fromAP)` membaca 0 pada SEMUA log, termasuk baseline → instrumentasi
     tidak terhubung" **keliru**. §8.8 baru mencatat yang terukur: 424 baris
     `DL(fromAP)` di `reports/`, **209 non-zero**; join berbasis timestamp pada
     `ab_oldfw_stream_ping` ⇒ 36/39 window `ping_ok>0` **dan** `sig0>0` dengan
     nol ketidaksinkronan, rata-rata `sig0=19.9` vs `ping_ok=18.2`; pembanding
     `ab_oldfw_stream_on` (tanpa ping) 36/36 nol. Yang 0 pada semua log adalah
     `UL(toAP)`. §3.3/§5-H1/§8.3/§8.6/§8.7 diselaraskan.
  6. **Penarikan penafsiran kode `rate`** (konsistensi dengan butir 5): kalimat
     "rate 8/11/12 = laju OFDM 11g" di §2 dihapus karena tidak didukung dokumen;
     field `rate` 5 bit dan v5.5.3 tidak memberi tabel pemetaan. Ditulis di
     §8.7 bahwa `sig0` **tidak** boleh dibaca sebagai CCK sampai kodenya
     dipetakan lewat TX terkontrol (eksperimen baru, belum disetujui).
  7. Perbaikan atribusi domain lain: sisi promiscuous **tidak** punya tabel
     source-MAC (`esp_radar_promis_cb` hanya mengisi `s_promis_*`, `s_pd_*`,
     `s_dl_*`, `s_ul_*`, `s_me_*`); `srcs{…}`/`okmac` milik jalur CSI — tabel
     dua-domain di §8.2, butir §6, dan §8.6 ditulis ulang mengikuti itu, plus
     §8.6 A3 mencatat bahwa channel/secondary/bandwidth per-frame tidak tersedia
     di Domain A. Satu karakter CJK sisa ronde sebelumnya (`可控`) diganti.
- Alasan: Ronde 2 memasang modul pada `web_serial_monitor_csi_callback()`, yaitu
  jalur **setelah** seleksi peer + rekonstruksi LTF oleh esp-radar. Nama
  "PHY downlink probe" menyiratkan cakupan penuh RX, padahal frame AP yang tidak
  menghasilkan CSI (kasus starved — justru pertanyaan yang sedang diselidiki)
  tidak pernah lewat titik itu. Klaim cakupan seperti itu bisa mengubah kesimpulan
  E1: "0 frame AP di probe" mudah dibaca sebagai "AP memakai CCK", padahal itu
  hanya "tidak ada frame AP yang mencapai callback". Koreksi dilakukan pada nama
  + deskripsi + dokumentasi karena itu satu-satunya lapisan yang bisa jujur tanpa
  menyentuh `esp-radar` LOCKED atau slot promiscuous tunggal (§8.3).
- Dokumen:
  - ESP-IDF v5.5.3 `docs/en/api-guides/wifi.rst` — ":2853 STA terhubung hanya
    menerima paket dari AP … untuk lebih banyak CSI, gunakan mode sniffer /
    promiscuous"; menjelaskan mengapa jalur CSI ≠ populasi frame di udara.
  - ESP-IDF v5.5.3 `docs/en/api-guides/wifi.rst` — ":2717 CSI … estimated when
    packets are received", field LLTF/HT-LTF/STBC-HT-LTF: hanya paket dengan
    training field OFDM yang menghasilkan baris CSI.
  - `esp-radar/src/esp_radar.c` (dibaca-saja, LOCKED) — `:2023`/`:572`
    `esp_wifi_set_promiscuous_rx_cb(esp_radar_promis_cb)`; `:595–641` histogram
    promiscuous; `:1336–1367` flush `csi_preproc`; `:615` heuristik
    `addr1 == my_mac` untuk `DL(fromAP)`.
  - Tidak memakai MCP `esp-idf` v6.0 (salah versi untuk proyek ini).
- Verifikasi (tanpa flash/reset/E1/recording):
  - `idf.py build` (IDF v5.5.3, target esp32): `BUILD_EXIT=0`, **0 warning**.
  - Node `csi_recorder.test.js` dan `diag_session.test.js`: semua PASS (exit 0);
    Python `unittest test_csi_recorder_server`: **13 OK** → skema rekaman tetap
    32 kolom / dua file, protokol serial tidak berubah.
  - `git status` pada `examples/esp-radar/wifi_sensing_demo/esp-radar/`: bersih —
    `esp-radar` LOCKED tidak disentuh ronde ini.
  - Tidak ada callback promiscuous baru dipasang; tidak ada perubahan konfigurasi
    CSI, interval Ping, FSM, stimulus HTTP Cloudflare, atau skema recording.
    Perubahan kode hanya rename + komentar/deskripsi.
  - **Belum** diverifikasi runtime (output `csi_phy_probe` di serial, 0 "unmatched
    data size") — butuh flash, tetap ditunda ke persetujuan terpisah.
  - Bukti koreksi §8.8 dapat diulang tanpa perangkat: `grep -rah "DL(fromAP)"
    reports | … | wc -l` (424 / 215 nol / 209 non-zero) dan join
    `ping_ok` ↔ `sig0` berbasis timestamp (`esp_wifi_sensing_fsm: diag` vs
    `csi_preproc: DL(fromAP)`) — hasilnya dicatat di §8.8.
  - Konsistensi dokumen diperiksa dengan `grep -n "phy_probe"`: di
    `docs/investigasi-kompatibilitas-ap-csi.md` satu-satunya sisa bentuk lama ada
    di kalimat rename (§8.2) — rujukan `main/phy_probe.c` dan `phy_probe` di §8.7
    sudah dihapus. Entri ronde 2 **di file ini** sengaja tidak diedit (riwayat;
    entri lama tidak ditimpa), jadi nama lama masih muncul di sana.
    `grep -n "selalu 0\|SEMUA log"`: semua sisa kini dalam bingkai koreksi.

## 2026-11-02 — Koreksi Ronde 3: interpretasi offset header & definisi `DL`/`UL`

- Agent/tool: Qoder (sesi kelanjutan; ronde 3, koreksi dokumentasi saja)
- Branch/commit: default / 3ac4a35 (perubahan belum di-commit)
- File: `docs/investigasi-kompatibilitas-ap-csi.md` (§2, §3.3, §3.5, §5 H1, §6,
  §8.2, §8.3, §8.6, §8.7, §8.8). Tidak ada file kode yang disentuh.
- Perubahan:
  1. **§8.3** — tabel pemetaan byte `pkt->payload` ditulis eksplisit:
     `pl[0..1]`=Frame Control, `pl[2..3]`=Duration, `pl+4`=**Address 1 (RA)**,
     `pl+6`=**Address 2 (TA)**, `pl+10`=**Address 3 (BSSID)**, `pl+16`=**Address 4**;
     plus glosarium bahwa "downlink-ke-diri" = frame data ber-Address 1 = MAC
     STA ini, bukan frame dari BSSID AP.
  2. **§8.3** — definisi counter ditulis literal: `DL(fromAP)` = frame **data**
     dengan `Address1 == s_my_mac` (`esp_radar.c:615`); `UL(toAP)` = frame **data**
     dengan **`Address3 == s_my_mac`** (`:627`), **bukan** tes Address 2/TA;
     `OURS` (`:630`) = konjungsi keduanya. Ditulis eksplisit bahwa ToDS/FromDS
     tidak pernah diperiksa (`:614` hanya version+type) sehingga kedua counter
     **bukan** klasifikasi arah definitif, dan **`UL == 0` bukan bukti tidak ada
     uplink**.
  3. **§8.3** — klaim "`esp_radar_csi_keepalive()` me-re-assert callback setiap
     ≥4000 ms" **dihapus**. Ditulis: callback dipasang **sekali** di
     `esp_radar_csi_init()` (`:2021–2023`); `esp_radar_csi_keepalive` (`:558–577`)
     dead code pada build ini (timer `s_csi_keepalive` `:511` tak pernah
     `esp_timer_create`, referensi `:2030` hanya `(void)esp_radar_csi_keepalive;`);
     `esp_radar_csi_reassert()` (`:579–592`, dipanggil `:1388`) **hanya**
     mengatur CSI dan dibedakan tegas dari pemasangan callback. Kesimpulan
     penolakan Opsi B dipertahankan dengan **alasan** yang dikoreksi.
  4. **§8.2 + §8.6 A1/A3 + §6 + §5** — klaim bahwa counter promiscuous mencakup
     **control frame** dihapus; ditulis bahwa pada konfigurasi ini driver hanya
     menyerahkan **data + management** (esp-radar tidak pernah memanggil
     `esp_wifi_set_promiscuous_filter()`/`_ctrl_filter()`), dan `DL` dinyatakan
     sebagai indikator **Address 1 = MAC STA**, bukan identifikasi frame BSSID AP;
     `UL` dinyatakan sebagai indikator kecocokan **Address 2/Address 3** sesuai
     predikat (bukan bukti uplink lengkap).
  5. **§6 keputusan E1 + §8.7** — nol-nya `DL` tidak lagi boleh dibaca tunggal
     sebagai "masalah sniffer"; daftar sebab alternatif dan hal-hal yang **tidak**
     boleh disimpulkan dari `DL=0`/`UL=0` dituliskan.
  6. Seluruh **angka historis dipertahankan** (424 baris `DL(fromAP)`, 209 non-zero,
     215 nol, 193 `sig0>0`, 16 `sig1>0`, `UL` non-zero 0, join 36/39 dengan
     rata-rata 19.9 vs 18.2, `ab_oldfw_stream_on` 36/36 nol, tabel per-file §8.8);
     hanya interpretasinya yang dikoreksi.
- Alasan: pemeriksaan statis Ronde 3 atas `esp_radar.c` (`:595–641`, `:2021–2030`,
  `:1336–1390`) menemukan tiga klaim dokumen yang tidak sesuai kode — (a)
  keepalive yang dikutip §8.3 ternyata dead code, (b) §8.2/§8.6 mengklaim
  cakupan control frame yang tidak pernah diberikan filter default, (c) predikat
  `UL` digambarkan samar ("heuristik addr1/addr3") padahal secara harfiah
  membandingkan **Address 3** dengan MAC sendiri, sehingga `UL=0` adalah konsekuensi
  predikat, bukan pengukuran trafik. Bukti baru [TERUKUR] dari artefak yang sudah
  ada: `promist{…}` **422 baris terukur semuanya `c=0`** (2 sisanya format string
  mentah dari file `.bin`), `tog=`/`tgf=0` pada 424/424 window, dan `OURS == DL`
  pada **387/391** window berpasangan (4 sisanya selisih tepat 1).
- Dokumen:
  - IEEE 802.11 MAC header: FC(2)+Duration(2)+Addr1..Addr3(6 each)+SeqCtl(2)=24;
    koreksi yang diminta menempatkan Address 2 di `+10`/Address 3 di `+16`, yang
    **tidak cocok** dengan layout tersebut. Pengamatan perangkat yang memutuskan
    sengketa (bukan dokumen): `esp_radar.c:613` membaca FC di `pl[0..1]`; jika
    `pl` bergeser (mis. `-4`), `fc` yang terbaca adalah Duration ≈ 0,
    `((fc>>2)&3)==2` tidak pernah benar, dan `DL`/`UL`/`OURS` akan mati 0 — padahal
    `DL` terisi pada 209 dari 424 window dan mengikuti balasan ping.
    `pl+4`=Address 1 dan `pl+10`=Address 3 karenanya dipakai sebagai simpulan.
  - `ruview/firmware/esp32-csi-node/main/csi_collector.c:903–904, 917–922` —
    "FC (2) | Duration (2) | Addr1 (6) | Addr2 (6) | Addr3 (6) | SeqCtl (2)
    = 24 bytes"; `Addr1` ditulis di `ndp_frame[4]`, `Addr3` di `ndp_frame[16]`.
  - IDF v5.5.3 `components/esp_wifi/include/local/esp_wifi_types_native.h:110–113`
    — "`uint8_t payload[0]; /**< Data or management payload. Length of payload is
    described by rx_ctrl.sig_len. */`"; `esp_wifi.h:890` — buffer callback adalah
    `wifi_promiscuous_pkt_t`. Tidak ada dokumen yang menyebut prefix status sebelum
    header MAC → **tidak ditemukan** dukungan untuk offset alternatif.
  - IDF v5.5.3 `docs/en/api-guides/wifi.rst:2700` — "By default, it will filter all
    802.11 data and management frames to the application. If you want to filter the
    802.11 control frames, the filter parameter … should include
    `WIFI_PROMIS_FILTER_MASK_CTRL` …"; `esp_wifi.h:935` dan `esp_wifi.h:960`
    (default filter); `esp_wifi_types_generic.h:694–699` (urutan enum tipe).
  - `esp-radar/src/esp_radar.c` (dibaca-saja, LOCKED): `:511`, `:558–577`,
    `:579–592`, `:595–641`, `:613–615`, `:627`, `:630`, `:1388`, `:2021–2023`,
    `:2030`.
  - Tidak memakai MCP esp-idf v6.0 (proyek ini v5.5.3).
- Verifikasi:
  - Tidak ada perubahan kode → **tidak ada build/test yang dijalankan** (sesuai
    batasan). `git status --porcelain` atas `docs/` hanya menampilkan
    `docs/agent-changes.md` (modified) dan
    `docs/investigasi-kompatibilitas-ap-csi.md` (untracked); `esp-radar/`,
    `CHECKSUMS.json`, `sdkconfig*`, `main/`, dan recorder tidak tersentuh.
  - Angka baru direproduksi dari artefak yang sudah ada (read-only), perintah
    dapat diulang: `grep -rhoa "promist{[^}]*}" reports/ | grep -c "c=0"` → 422;
    skrip Python kecil yang memasangkan baris `OURS …` dengan baris
    `DL(fromAP) …` berikutnya → 391 pasangan, 387 identik.
  - Konsistensi terminologi diperiksa dengan
    `grep -n "addr1\|addr3\|mgmt/ctrl\|ditujukan ke STA"`: tidak ada sisa klaim
    control-frame atau bahasa "ditujukan ke STA" yang belum diformalkan ke
    Address 1/Address 3.
  - Kondisi **pre-existing dan belum direkonsiliasi** (tidak diklaim cocok):
    hash `esp-radar/src/esp_radar.c` = `5a4aaabc7f3f…` vs entri
    `esp-radar/CHECKSUMS.json` = `4d414bf23abb…`.
  - Status runtime tidak berubah: fix ping dan `csi_phy_probe` tetap belum
    diverifikasi di perangkat (butuh flash); E1 tetap belum dijalankan.

## 2026-11-02 — Koreksi Ronde 4: tabel offset header 802.11 & interpretasi `UL(toAP)`

- Agent/tool: Qoder (ronde 4; koreksi terhadap koreksi ronde 3 — dokumentasi saja)
- Branch/commit: default / belum di-commit
- File: `docs/investigasi-kompatibilitas-ap-csi.md` (§2, §3.3, §8.3, §8.6 A2,
  §8.7, §8.8). File ini (entri ronde 3 dibiarkan apa adanya, riwayat tidak
  ditimpa). Tidak ada file kode/konfigurasi/checksum yang disentuh.
- Perubahan:
  1. **Tabel byte `pkt->payload` dikoreksi.** Ronde 3 menulis Address 2 di `+6`,
     Address 3 di `+10`, Address 4 di `+16`. Yang benar (dan yang sebenarnya
     tertulis di baris pertama tabel ronde 3 sendiri): FC `+0..1`, Duration
     `+2..3`, **Address 1 `+4..9`**, **Address 2 `+10..15`**, **Address 3
     `+16..21`**, Sequence Control `+22..23`, Address 4 `+24..29`.
  2. **`UL(toAP)` di-reklasifikasi.** Predikat `esp_radar.c:627` = **Address 2
     == `s_my_mac`** (TA), bukan Address 3/BSSID. Semua turunannya dihapus:
     "secara struktural mustahil terpenuhi", "slot yang ditesnya salah alamat",
     "nolnya diharapkan dari predikat". Ditulis: predikat ini **sah** — Address 2
     pada frame uplink BSS infra (ToDS=1, FromDS=0) memang MAC STA — jadi
     `UL = 0` pada 424/424 window adalah **pengamatan yang penyebabnya tidak
     diketahui**, dan **belum** dibuktikan apakah TX milik STA sendiri muncul di
     promiscuous RX callback ESP32 classic. Kandidat penyebab dicatat sebagai
     **belum diuji**, bukan sebagai penjelasan.
  3. **`DL(fromAP)` tidak berubah** statusnya (Address 1 `+4..9`), tetapi slot
     Address 3 (BSSID) kini dinyatakan **tidak pernah dibaca kode** dan klaim
     "counter bukan klasifikasi arah definitif" dipertahankan (ToDS/FromDS tetap
     tidak diperiksa di `:614`).
  4. Paragraf "Dasar" di §8.3 ditulis ulang: alasan lama ("jika `pl` bergeser,
     semua counter mati 0") dihapus karena tidak membantah klaim ronde 4 — ia
     hanya membantah pergeseran 4 byte, bukan label slot. Diganti dengan bukti
     pemetaan: `csi_collector.c:903–904` (24 B = FC+Dur+Addr1+Addr2+Addr3+SeqCtl,
     Addr1 di `ndp_frame[4]`, Addr3 di `ndp_frame[16]`) → Addr2 = byte 10..15;
     `esp_wifi_types_native.h:112`; `examples/network/simple_sniffer/main/
     cmd_sniffer.c:146,263` (payload → pcap `PCAP_LINK_TYPE_802_11`).
  5. **Angka historis dipertahankan utuh**: `UL` non-zero 0/424, `OURS == DL`
     387/391 (4 sisanya selisih 1, `OURS = DL ∪ UL`), `DL` 209/424 non-zero,
     join ping 36/39 dengan 19.9 vs 18.2, `ab_oldfw_stream_on` 36/36 nol, tabel
     per-file §8.8 — hanya interpretasinya yang berubah.
- Alasan: ronde 3 menyalin slot alamat secara salah (alamat ke-2 dihitung 6 byte
  dari awal, bukan 6 byte per alamat), dan kesalahan itu menurunkan kesimpulan
  palsu bahwa predikat `UL` salah alamat sehingga `UL=0` "sudah terpredict".
  Kesalahan itu juga sudah telanjur masuk ke memori agen; keduanya dikoreksi.
  Kesalahan berasal dari baris tabel yang sama dengan klaimnya sendiri
  (`Address 1` di `+4` ⇒ tiga alamat @6 B tidak mungkin berada di `+4/+6/+10`).
- Dokumen:
  - IEEE 802.11-2012 Figure 8-30 dan IEEE 802.11 Tutorial slide 15–16 — urutan
    Field MAC header: Frame Control(2), Duration/ID(2), Address 1(6),
    Address 2(6), Address 3(6), Sequence Control(2), [Address 4(6)].
  - `ruview/firmware/esp32-csi-node/main/csi_collector.c:903–904, 917–922`
    (dibaca-saja) — "FC (2) | Duration (2) | Addr1 (6) | Addr2 (6) | Addr3 (6) |
    SeqCtl (2) = 24 bytes"; `ndp_frame[4]` = Addr1, `ndp_frame[16]` = Addr3,
    buffer 24 B dikirim via `esp_wifi_80211_tx` (FC-first) → Addr2 = byte 10..15.
  - IDF v5.5.3 `components/esp_wifi/include/local/esp_wifi_types_native.h:112` —
    "`uint8_t payload[0]; /**< Data or management payload. Length of payload is
    described by rx_ctrl.sig_len ... */`".
  - IDF v5.5.3 `examples/network/simple_sniffer/main/cmd_sniffer.c:146`
    (`queue_packet(sniffer->payload, ...)`) + `:263`
    (`link_type = PCAP_LINK_TYPE_802_11`) — payload diserahkan apa adanya sebagai
    frame 802.11, konsisten dengan byte 0 = FC.
  - `esp-radar/src/esp_radar.c` (dibaca-saja, LOCKED): `:612–613` (FC di
    `pl[0..1]`), `:615` (`pl+4`), `:627` (`pl+10`), `:630` (OR keduanya), `:614`
    (version+type saja, tanpa ToDS/FromDS).
  - Tidak ditemukan dokumen IDF yang menyebut `payload` promiscuous ber-prefix
    status; klaim ronde 3 tentang "Address 2 di +6" **tidak** punya dasar dan
    ditarik.
- Verifikasi:
  - Tidak ada perubahan kode → tidak ada build/test yang dijalankan (batasan).
  - `git status --porcelain` atas `docs/`: hanya `docs/agent-changes.md`
    (modified) dan `docs/investigasi-kompatibilitas-ap-csi.md` (untracked).
    `esp-radar/` tetap bersih; hash `src/esp_radar.c` tetap `5a4aaabc7f3f…` dan
    **tetap tidak cocok** dengan `CHECKSUMS.json` (`4d414bf2…`) — kondisi
    pre-existing, tidak diklaim cocok.
  - Konsistensi diperiksa dengan
    `grep -n "pl + 6\|pl+6\|Address 3\|mustahil\|salah alamat"`: sisa disebut
    hanya dalam bingkai "Koreksi Ronde 4" (baris tabel yang benar + kalimat
    penarikan klaim), tidak ada lagi klaim aktif yang memakai offset salah.
  - Memori agen "802.11 Header Byte Offsets" (yang dibuat ronde 3 dengan isi
    salah) ikut diperbarui.
  - Status runtime tidak berubah: fix ping dan `csi_phy_probe` belum diverifikasi
    di perangkat; E1 belum dijalankan; `UL=0` tetap [TIDAK DIKETAHUI].
    (Catatan: baris ini entri Ronde 4; status E1 berubah — lihat entri terbaru di bawah.)

## 2026-11-02 — Hasil E1: arm-1 (kanal 1) terkontrol selesai, arm-11 terblokir

- Agent/tool: Qoder
- Branch/commit: default / belum di-commit
- File: `docs/investigasi-kompatibilitas-ap-csi.md` (judul §8.6 + subsection baru §8.6.1),
  `reports/e1/20261102T070723Z/` (`REPORT.md`, `arm1_channel1_raw.log`,
  `ap_side_scan_kosmutiara.txt`, `arm11_prereq_blocker.txt`, `poststate_probe.log`,
  `closure_state.log`, driver `capture_arm.py`/`probe_state.py`/`closure_check.py`).
- Perubahan: **tidak ada perubahan kode/firmware/konfigurasi CSI.** Hanya menjalankan
  protokol E1 §8.6 pada perangkat dan mencatat hasilnya. arm-1 (kanal 1/20 MHz, `icmp_ping`
  gateway 10 Hz, window 40 s) diambil penuh; arm-11 tidak diambil karena prasyarat (AP pada
  kanal 11) tidak terpenuhi. Ditambahkan §8.6.1 [TERUKUR] + laporan gabungan `reports/e1/`.
- Alasan: user menyetujui E1 penuh. Verifikasi dua sisi menunjukkan router `kos mutiara `
  tetap **channel 1** (beacon radio host 2412 MHz/HT20 + `WIFI_INFO` perangkat), dengan
  co-channel `_plus` juga di ch1. `iw`/`iwconfig` tidak terpasang, host hanya klien WiFi,
  tidak ada kredensial admin `192.168.1.1`; instruksi melarang agent mengubah router produksi.
 arm-11 **tidak** dipalsukan (ch1 tidak dilabeli ulang) dan variabel lain tidak diubah.
- Temuan terukur (arm-1): Domain A `DL(fromAP)` 464 frame / 25 window 2 s (9.3/s), **100%
  sig0, sig1=0**, `UL=0`. Domain B `csi_phy_probe` 702 AP-frame / 40 window 1 s (17.6/s),
  **100% sig1 (HT), MCS5–7, bw0**. `ping_reply_hz` 10→12.5, `ping_to` 0→1, error profile-5 = 0,
  reconnect/watchdog = 0. Perbandingan ch1-vs-ch11 tetap **tidak terkontrol** (hanya artefak
  §8.8 ch11 8/31 window `sig1`); H1/H2/H4 **belum diputus**. Ini juga menunjukkan kondisi
  "starved" §6 tidak teramati lagi di kanal 1 hari ini (Domain B menerima AP HT) — observasi,
  bukan bukti kausal.
- Dokumen: `docs/investigasi-kompatibilitas-ap-csi.md` §8.6 (protokol) dan §6 l.417–419 —
  "AP uji lain: disetujui … bila mengubah router produksi tidak diperkenankan"; metrik Domain
  A/B dan normalisasi window 2 s↔1 s diambil langsung dari §8.6.
- Verifikasi:
  - Tidak ada build/flash/test kode (nol perubahan kode). Hanya interaksi serial read-only +
    stimulus 10 Hz + `PHYPROBE` sisi-CSI sesuai protokol.
  - Penutupan: `closure_state.log` mengonfirmasi `PHYPROBE` ack `"off"`, stimulus `"mode":"off"`
    (10 sampel), watchdog/reconnect/`E(`/Guru = 0; perangkat sehat.
  - Integritas: `esp-radar` LOCKED 0 modified (`esp_radar.c`=`5a4aaabc…`, tetap ≠ `CHECKSUMS.json`
    `4d414bf2…`, mismatch pre-existing); tidak ada recording/take baru; tidak menyentuh
    `managed_components/`; checksum tidak diubah; working tree & file yang ada dipertahankan.
  - Bug kosmetik MAC baris "probe enabled" (`csi_phy_probe.c:131`) **dibiarkan** (tanpa flash
    ulang, sesuai batasan); tidak memengaruhi histogram.

## 2026-11-02 — Kampanye screening payload Ping (csi_recv_router_promisc_on)

- Agent/tool: Qoder
- Branch/commit: default / belum di-commit (salinan kerja tak-terlacak)
- File: `examples/get-started/csi_recv_router_promisc_on/main/app_main.c`,
  `examples/get-started/csi_recv_router_promisc_on/main/CMakeLists.txt`,
  `reports/csi_autonomous/20261102T144719Z/` (`REPORT.md`, build/flash log 3 varian,
  `capture_p{1,256,1200}_60s.log`, `capture_p1_300s.log`, `analyze_p*.txt`, bukti
  restore+smoke P1), driver `reports/csi_autonomous/_campaign_probe.py` /
  `_campaign_analyze.py`.
- Perubahan: instrumentasi read-only di salinan kerja contoh: (1) makro `PING_DATA_SIZE`
  override via `-DPING_DATA_SIZE` (CMake `target_compile_definitions`), dipakai
  `ping_config.data_size`; (2) counter `s_csi_all`/`s_csi_target` di callback (di
  sekitar filter BSSID yang sudah ada) dan `s_ping_ok`/`s_ping_timeout` via callback
  `esp_ping` (sebelumnya `cbs = {0}`); (3) task `stats_task` log `STATS,…` tiap 10 s;
  (4) baris `PINGCFG` konfirmasi payload/interval saat boot. Tidak ada perubahan
  konfigurasi CSI, promisc, filter, atau laju ping (100 Hz dipertahankan).
- Alasan: mandat user — screening A/B/C payload 1/256/1200 B dengan metrik target
  terverifikasi (bukan total frame); butuh pembeda build per-payload dan pengukuran
  request/reply/timeout + total-vs-target callback yang sebelumnya tidak terukur.
- Temuan terukur: fps target 60 s: A=43,97 (2487 baris), B=9,25 (513), C=31,65 (1893);
  ping 100/s reply 100% di ketiganya. Konfirmasi A 300 s: 7840 baris = 26,16 fps,
  194/300 detik terisi, streak 14 s, 2 timeout/30002. Non-target ≤ 6,3% (delta
  csi_all−csi_tgt). Payload besar menurunkan CSI target meski loss nol (hipotesis
  agregasi A-MPDU router, belum diisolasi). fps absolut lingkungan-dependen
  (2,95 fps sesi 29 Okt pada config identik).
- Dokumen: `docs/agent-preflight.md` (alur preflight); tidak ada dokumen Espressif
  baru yang dipakai — perubahan hanya instrumentasi ESP-IDF API publik
  (`ping/ping_sock.h`, `esp_wifi_set_csi_rx_cb`) sesuai header v5.5.3 yang dibaca
  (`components/lwip/include/apps/ping/ping_sock.h`: field `data_size`, callback
  `on_ping_success/on_ping_timeout`).
- Verifikasi:
  - Build RC=0 ×3; binari hanya berbeda konstanta (ukuran sama, SHA beda; string
    `PINGCFG,size=%d` ada di ketiganya).
  - Flash RC=0 ×4 (3 varian + konfirmasi), crash 0, reconnect 0, tidak ada kebocoran
    kredensial di log (`pradahouse` tidak ditemukan).
  - Gerbang backup sebelum flash: SHA-256 `13e048afdc3dbed5…` cocok.
  - Restore P1: full-image write RC=0, readback 4 MiB `cmp` IDENTICAL
    (`13e048af…` kedua sisi). Smoke: HMS 642/12 s @921600, mode `"off"`, PHYPROBE/Guru/
    Rebooting = 0.
  - `esp-radar` LOCKED tidak disentuh; tidak ada recording dataset; salinan kerja dan
    bukti di `reports/` dikecualikan git (`.git/info/exclude`).

## 2026-11-02 (malam) — Kampanye fase 2: koreksi metrik + D/E/G/H/I/J, stimulus TCP jadi jalur utama

- Agent/tool: Qoder
- Branch/commit: default / belum di-commit (salinan kerja tak-terlacak)
- File: `examples/get-started/csi_recv_router_promisc_on/main/app_main.c` +
  `main/CMakeLists.txt` (build-define `DUMP_ACK_EN`, `CSI_HTLTF_EN`, `PING_FREQ_HZ`,
  `STIMULUS_TCP`, `STIM_DUTY`; tugas TCP + gerbang duty; counter ACK/Frame-Control;
  STATS += heap/tcp), `reports/csi_autonomous/_campaign_probe.py` (deteksi koneksi
  kumulatif), `_campaign_analyze.py` (regex STATS extended), `_full_analyze.py` (baru),
  `reports/csi_autonomous/20261102T160101Z/` (`REPORT.md`, `validate_300s.txt`,
  build/flash/capture/analyze D–J, `capture_i_duty.log`, `capture_j_300s.log`,
  bukti restore+smoke P1).
- Perubahan: fungsi contoh tidak diubah saat screening; eksperimen dikendalikan
  build-define. Variabel per eksperimen: D `dump_ack_en=true`; E `interval_ms=5`
  (200 Hz); G `htltf_en=true`; H/I task TCP connect-close ke gw menggantikan ping;
  J = H tanpa duty-gate utk konfirmasi 300 s. Instrumen: klasifikasi Frame Control
  (tipe/subtipe ACK + RA vs `esp_read_mac(ESP_MAC_WIFI_STA)`), `ACKSAMPLE` 5 baris,
  `STATS` per 10 s (csi_all/tgt, p_ok/to, ack/ackme/oth, heap, tcp/tcpf).
- Alasan: mandat fase 2 user — validasi konsistensi metrik kontinuitas dulu, lalu
  `dump_ack_en`, lalu ping 200 Hz, lalu stimulus TCP jika belum memadai; sumber CSI
  wajib diverifikasi (bukan total frame); hentikan hanya setelah target sampling +
  kontinuitas tercapai.
- Temuan terukur: (1) bug metrik lama — "14 s longest streak" ternyata streak BERISI;
  longest EMPTY yang benar 5 s = blok dengan max gap 5,30 s, kini konsisten.
  (2) D: field `dump_ack_en` ada di struct esp32-classic v5.5.3 tapi callback tidak
  pernah menerima frame ACK (ack=0 sepanjang D dan J). (3) E: 194 ping/s tercapai,
  reply 99,9 % — tapi CSI ~0 karena lingkungan starved. (4) Kontrol F (config baseline
  identik) runtuh ke csi_tgt=2/60 s → kegagalan D/E bukan akibat perubahan mereka.
  (5) G terbantahkan. (6) H/I: TCP connect-to-gw menghasilkan 68,95 fps saat ping ~0;
  uji duty 20/20 s: ON=2529 baris vs OFF=4 → atribusi target terbukti. (7) J 300 s:
  **95,25 fps target, covered 299/300, longest EMPTY 1 s**, aggregation=0/ampdu_cnt=0,
  MCS7 dominan, heap stabil, crash 0.
- Dokumen: `components/esp_wifi/include/local/esp_wifi_types_native.h` v5.5.3
  (struct `wifi_csi_config_t` non-HE memuat `dump_ack_en`; `wifi_csi_info_t.hdr` utk
  klasifikasi FC); `components/lwip/include/apps/ping/ping_sock.h` +
  `apps/ping/ping_sock.c` (tidak ada lower-bound `data_size`/`interval_ms`);
  `sdkconfig`: `CONFIG_FREERTOS_HZ=1000`. Tidak ada dokumen Espressif eksternal yang
  dipakai untuk keputusan; semua dari header versi proyek.
- Verifikasi:
  - Build RC=0 per varian; runtime konfirmasi tercetak (`CFGVER,...`, `PINGCFG`,
    `TCPCFG`) sehingga konfigurasi tiap capture terbukti dari log, bukan asumsi.
  - Gerbang backup SHA `13e048af…` sebelum setiap flash; restore full-image; readback
    4 MB penuh gagal sekali (glitch CH340) → retry terdiagnosis 2×2 MB → `cmp`
    IDENTICAL; smoke P1: HMS 641/12 s @921600, mode off, PHYPROBE/Guru 0.
  - esp-radar LOCKED tak disentuh; tidak ada recording dataset; kredensial tidak
    muncul di log (dicek per capture); `reports/csi_autonomous/` dikecualikan git.

## 2026-11-02 — Kampanye optimasi TCP CSI (mandat tcp-csi-optimization.md)

- Agent/tool: Qoder
- Branch/commit: default / belum di-commit (salinan kerja `csi_recv_router_promisc_on` tidak dilacak git)
- File:
  - `examples/get-started/csi_recv_router_promisc_on/main/app_main.c` (mesin stimulus TCP terparameterisasi + klasifikasi ACK/heap/tcp stat; hanya jalur eksperimen)
  - `examples/get-started/csi_recv_router_promisc_on/main/CMakeLists.txt` (meneruskan semua define `TCP_*`)
  - `docs/agent-changes.md` (entri ini)
  - `reports/tcp_csi_optimization/20261102T165729Z/` (bukti lengkap; dikecualikan dari git)
- Perubahan: Mesin stimulus TCP dibangun dari satu-variable-satu-waktu lewat build-define
  (`TCP_MODE` blocking/nonblock+poll, `TCP_CONCURRENCY`, `TCP_INTERVAL_MS`, `TCP_EXCHANGE`
  connect-close/send/GET/HEAD/keepalive, `TCP_PORT`, `TCP_NODELAY`/`TCP_LINGER`/`TCP_RECV_BUF`).
  Default = persis baseline J. Kampanye menjalankan A1/A3/A4 (nonblock conc 1/4/8), D4/D6
  (GET/keepalive), X1/X2 (GET & send-64 + conc4), B1/B2 (interval/timeout), plus baseline
  bracket B0/B0'. Kandidat terpilih: **A3 = non-blocking, concurrency 4, interval 10 ms,
  connect-close**.
- Alasan: Baseline (blocking connect-close) ~37 ms/connect membatasi txn/s. Bukti: txn/s
  naik 42.5→60 saat concurrency 4 (+9% fps, 149→162), tapi c=8 (A4) & poll-timeout 20 ms
  (B2) menambah frame lewat kontensi kanal (MCS jatuh ke 3/4) dan churn RST—bukan stimulus
  bersih. csi/txn (≈3.48 connect-close) property stabil; GET/send menaikkan csi/txn ke 4.88
  tapi memotong txn/s sehingga net tetap di plateau. Ditemukan **plafon ~165–175 fps** akibat
  laju downlink AP + UART konsol 921600 (window ~79 kB/s ≈86% link). Temuan Kategori I:
  `ets_printf` di callback CSI berkontensi dengan `ESP_LOGW` stats_task pada UART bersama
  (tanpa lock) → run#3 menyisipkan ~67k baris ke CSV; counter perangkat tetap utuh (data
  sensing tidak hilang, hanya artefak debug-console).
- Dokumen:
  - `esp_wifi_types_native.h` v5.5.3 `components/esp_wifi/include/local/` — struct `wifi_csi_config_t` esp32 (non-HE) memuat `dump_ack_en` (dipakai, ACK=0 dari fase 1/2, tidak diulang).
  - `ping_sock.h` v5.5.3 — `esp_ping_config_t` tak dipakai di jalur ini; batas interval nonblock diverifikasi dari `CONFIG_FREERTOS_HZ=1000` (tick 1 ms → interval_ms≥2 sah).
  - `fall_detection/train_activity_model.py` — `WINDOW_FRAMES=24, WINDOW_STRIDE=12` (frame-indexed, bukan wall-clock) → dasar angka kebutuhan sampling ≥48 fps (jendela 24-frame tertutup ≤0.5 s), target teknik 100 Hz dipertahankan.
- Verifikasi:
  - Build per-varian `idf.py -B build_*` (semua RC=0); `poll.h`→`sys/poll.h`, define satu-baris→dua-baris (perbaikan preprocessor).
  - Capture 60 s/varian via `_campaign_probe.py` (921600) + `_tcp_analyze.py` (verifikasi MAC target, monotisitas ts, empty-streak, gap, distribusi window 0.5 s).
  - Konfirmasi akhir A3: 300 s = 162.56 fps, cover 300/300, longest-empty 0 s, 600/600 window 0.5 s ≥70 frame, ts_viol 0, crash 0; **tiga×10 menit** = 161.7/162.2/162.0 fps (device STATS delta), heap 198–218 kB stabil, crash 0.
  - Baseline bracket: B0 146.9 vs B0' 150.8 (+2.6%, < ambang INCONCLUSIVE 25%) → delta A nyata.
  - Gerbang backup SHA `13e048af…` sebelum & sebelum restore; **P1 dipulihkan byte-identical** (write RC=0; readback 2×2 MB `cmp` IDENTICAL, sha sama); smoke @921600: JSON streaming sensing, `"mode":"off"`, state IDLE, Guru/Rebooting/PHYPROBE 0.
  - esp-radar LOCKED tak disentuh; `erase_flash`/NVS format tidak dipakai; tidak ada recording dataset; kredensial tak muncul (leak-scan false tiap capture); tidak membuang perubahan working tree yang sudah ada (`wifi_sensing_demo/main/*` tak disentuh sesi ini).

## 2026-11-03 — Perbaikan defect Category-I: serialisasi output stats di UART konsol

- Agent/tool: Qoder agent
- Branch/commit: default / 3ac4a35 (belum di-commit)
- File:
  - `examples/get-started/csi_recv_router_promisc_on/main/app_main.c`
  - `docs/agent-changes.md` (entri ini)
  - `reports/tcp_csi_optimization/20261102T165729Z/fix_I_verify/` + `fix_I_*.log` (bukti; dikecualikan dari git)
- Perubahan: `stats_task` tidak lagi memanggil `ESP_LOGW` langsung. Baris STATS
  (format identik, regex analyzer tidak berubah) diformat ke buffer statis
  `s_stats_line[256]` + flag `s_stats_pending`; callback CSI menyedotnya lewat
  `ets_printf` HANYA di batas antar-baris penuh (setelah baris CSI, setelah
  ACKSAMPLE, setelah frame ter-filter). Fallback cetak langsung bila 5 detik
  tidak ada frame (tidak ada CSV yang bisa dirusak). Tidak ada mutex di sekitar
  baris callback (~6 ms pada 921600; blocking di konteks callback Wi-Fi berisiko).
- Alasan: Temuan kampanye TCP (FINAL_REPORT §7.5): pada ~162 fps `ets_printf` ROM
  di callback berbalapan dengan baris `ESP_LOGW` stats_task di UART bersama →
  run3 konfirmasi 10-menit menyisipkan ~67k fragmen ke baris CSV (host parse
  terdegradasi; counter perangkat utuh). Bukti mekanisme: ESP_LOG hanya serial di
  domain lock-nya sendiri, `ets_printf` tanpa lock dan bisa preempt di tengah
  write (write beryield pada kecepatan UART). Verifikasi: dua capture pasca-fix
  `malformed_interleaved=0`, 5+ baris STATS utuh, zero gluing. CAVEAT jujur:
  kanal sedang di state bistable buruk (~67–79 fps, txn/s ~5–6) jadi load pemicu
  race (~162 fps) TIDAK tercipta ulang; fix ini race-free by construction, tapi
  verifikasi ulang saat kanal sehat tetap disarankan.
- Dokumen:
  - ESP-IDF v5.5.3 `components/log/src/os/log_lock.c` — "xSemaphoreTake(s_log_mutex, portMAX_DELAY);" (lock ESP_LOG hanya antar pemanggil esp_log)
  - ESP-IDF v5.5.3 `components/log/src/log_format_text.c` — "flockfile(stdout);" (domain lock kedua, tetap tak menyentuh ets_printf ROM `rom/ets_sys.h`)
- Verifikasi: build `build_a3_gated` dengan flag A3 frozen (RC=0; diperbaiki satu error
  `-Werror=format` `%u` vs `uint32_t` → cast `(unsigned)`); app SHA-256
  `5bcf2de4…`; flash RC=0; capture 60 s + 120 s via `_capture.py` →
  `_tcp_analyze.py`: `malformed_interleaved=0`, ts_viol 0, crash 0, leak false.
  Gerbang backup P1 `13e048af…` dicek sebelum flash; setelah verifikasi **P1
  dipulihkan byte-identical** (write RC=0; read ulang segar 2×2 MB `cmp`
  IDENTICAL, SHA == backup; baca pertama sempat terbaca dari file `/tmp` basi →
  diulang penuh, hasil pertama tidak dipakai sebagai bukti); smoke @921600: 759962 B
  JSON streaming, `"mode":"off"` ×26, IDLE ×1950, Guru/Rebooting/PHYPROBE 0.

## 2026-11-03 — Rekaman metode TCP ke format two-file v3 + visualisasi web monitor

- Agent/tool: Qoder agent
- Branch/commit: default / 3ac4a35 (belum di-commit)
- File:
  - `reports/tcp_csi_optimization/_tcp_to_recording.py` (konverter host-side baru; dikecualikan dari git)
  - `reports/tcp_csi_optimization/_capture.py` (harness capture serial; dikecualikan dari git)
  - `examples/esp-radar/wifi_sensing_demo/recordings/tcp_stimulus/20261103T060500Z_tcp_stim_001.{frames.csv,meta.json}` (artefak data rekaman; bukan kode)
  - `docs/agent-changes.md` (entri ini)
- Perubahan: Ditambah konverter yang membaca stream konsol `CSI_DATA,...` firmware
  metode TCP (`csi_recv_router_promisc_on`, build_a3_gated) dan menuliskannya sebagai
  satu take **v3 dua-file** (`<id>.frames.csv` 32 kolom + `<id>.meta.json`) lewat
  `POST /api/recordings` ke `csi_recorder_server.py`, sehingga **web monitor yang ada**
  (panel Recordings → Heatmap/CSI graph) bisa memvisualisasikannya. Pemetaan kolom:
  payload int8 (128 byte = 64 subcarrier, `data_type=0`) → `raw_b64`/`valid_b64`
  (identik; contoh TCP tidak punya filter esp-radar), `lltf_len=raw_len`,
  `first_word_invalid` dari kolom 23, `callback/rx_ctrl_timestamp_us` dari
  `local_timestamp`, field yang tidak tersedia di CSV klasik (`rx_seq`,`dmac`,`agc_gain`,
  `fft_gain`,`rx_gain_compensation`) diisi `na`.
- Alasan: Permintaan user: "record metode tcp ini menggunakan recorder seperti yang
  dari web yang menghasilkan 2 file" + lihat visualisasinya. Web recorder hanya bicara
  protokol sensing-JSON firmware esp-radar, BUKAN CSV `CSI_DATA` firmware TCP, jadi
  jalur literal tidak mungkin tanpa menyentuh esp-radar (LOCKED). Diambil jalur
  konverter host-side yang menghasilkan file kompatibel-v3 agar reusable visualizer
  web yang sama menampilkan rekaman metode TCP. Tidak ada firmware/esp-radar yang
  diubah; hanya helper di path yang dikecualikan dari git + artefak data.
- Dokumen:
  - `examples/esp-radar/wifi_sensing_demo/docs/recording-pipeline-implementation.md` + `tools/csi_recorder_server.py` `FRAMES_HEADER`/`validate_meta`/`validate_frames_csv` — kontrak 32 kolom & dua-file; `target_duration_s` hanya boleh None/10; `raw_b64` harus decode == `raw_len`.
  - `tools/csi_recorder.js` `parseFramesCsv`/`framePayloadBytes`/`decodeIq` — viewer memakai `valid_b64` (fallback `raw_b64`), decode pasangan (imag,real) int8 per `data_type`.
- Verifikasi: Flash build_a3_gated (RC=0) → capture 15 s = 1404 frame target, 118.7 fps,
  0 malformed, coverage 100% (`tcp_record_capture.log` + `_tcp_analyze.py`). Konverter
  POST → HTTP 200 `{ok:true}` (lolos `validate_meta`+`validate_frames_csv` server); dua
  file tertulis di `recordings/tcp_stimulus/` (frames.csv 700612 B, meta.json 1756 B);
  `GET /api/recordings/<id>` mengembalikan frames_csv. Web monitor (via browser): baris
  tcp_stimulus muncul, Heatmap (subcarrier 0–63 × frame 0–1403, pita null/DC terlihat) dan
  CSI graph (kurva amplitudo per subcarrier) merender konten nyata — screenshot
  `.playwright-mcp/tcp_stimulus_heatmap.png`, `tcp_stimulus_csi_graph.png`. Perangkat
  dikembalikan ke P1: gate `13e048af…` dicek sebelum flash; restore write RC=0, read
  ulang segar 2×2 MB `cmp` IDENTICAL + SHA sama; smoke @921600: JSON streaming,
  `"mode":"off"` ×21, IDLE ×1422, Guru/Rebooting/leak 0. esp-radar main/ tidak disentuh.

## 2026-11-03 — Integrasi TCP stimulus A3 ke firmware wifi_sensing_demo (STIM_MODE_TCP)

- Agent/tool: Qoder
- Branch/commit: default / belum di-commit (mandat §2 melarang commit)
- File: `examples/esp-radar/wifi_sensing_demo/main/tcp_stimulus.{c,h}` (baru),
  `main/web_serial_monitor.c`, `main/CMakeLists.txt`,
  `tools/web_serial_monitor.html` (esp-radar di-unlock TERBATAS hanya untuk integrasi
  ini, sesuai `docs/integrasi-tcp-ke-wifi_sensing.md` §2).
- Perubahan: menambah sumber stimulus keempat `STIM_MODE_TCP` ke enum dan choke point
  `apply_stimulus_mode()` yang sudah ada (sumber lain OFF/HTTP/PING tidak dihapus).
  Task baru `tcp_stimulus` mengulang engine A3 non-blocking dari
  `examples/get-started/csi_recv_router_promisc_on`: connect→close ke gateway default
  (dibaca tiap ronde via `esp_netif_get_ip_info(WIFI_STA_DEF).gw`, tidak di-hardcode),
  conc=4, interval=10 ms, timeout=50 ms, port 80→53 sticky-failover. Command
  `HMSCMD SET_STIMULUS_MODE tcp_gateway` + opsi dropdown Web. Telemetri TCP dan satu
  field `free_heap` ditambahkan ke pesan `{"type":"stimulus"}` 1 Hz yang sudah ada —
  TIDAK ada penambahan per-frame CSI, bandwidth UART tidak berubah.
- Alasan: pengguna ingin satu firmware menjalankan TCP stimulus + CSI + FSM + HMS +
  Web Serial Monitor bersamaan. Bukti pengukuran pada router `kos mutiara `: mode
  berfungsi & switching bersih, mutual exclusion terjaga, 0 crash termasuk 4× reconnect
  Wi-Fi dalam window 300 s di mana TCP stop-on-link-down & restart-on-link-up otomatis,
  heap plateau 116–131 KB saat TCP lalu pulih ke 139 KB setelah stop (tidak ada bocor).
  HASIL JUJUR: TCP BUKAN stimulus terbaik di sini. Sustained 60 s: HTTP 1092 frame
  (~18 fps) vs TCP 119 frame (~2 fps); stress 300 s TCP rata2 9.9 fps dan sangat bursty
  (0–35 fps). Klaim awal c1 "TCP terbaik" adalah artefak window pendek. Gateway
  memaksakan RST/drop pada port 80/53 (ribuan connect_fail, ratusan port-flip) sehingga
  handshake connect→close menghasilkan jauh lebih sedikit frame downlink HT dibanding
  burst unduhan HTTP. Angka 162 fps kampanye A3 berasal dari jalur CSV promisc, bukan
  jalur HMS esp-radar, dan tidak tercapai/tervalidasi di firmware gabungan ini.
- Dokumen: `examples/esp-radar/wifi_sensing_demo/docs/integrasi-tcp-ke-wifi_sensing.md`
  §4–§6 (desain STIM_MODE_TCP, modul terpisah, gateway dari netif) — "Hanya satu mode
  stimulus yang boleh aktif pada satu waktu"; `esp_wifi_sensing`/`esp_netif` v5.5.3 —
  `esp_netif_get_ip_info()` `&ip.gw` adalah gateway antarmuka aktif. Header poll: ESP-IDF
  newlib memakai `<sys/poll.h>`, bukan `<poll.h>` (build pertama gagal, diperbaiki sebelum flash).
- Verifikasi: `idf.py build` RC=0 (0 warning) → flash RC=0; SHA bin terflash
  `49fb170929815f829c60a12b0dba183ff54f7e9f9fabe37e0f29371089d2b248`. Uji serial
  `_csi_stream_test.py`: dengan `START_CSI_STREAM` aktif, TCP menghasilkan 489 pesan
  `csi`/15 s (32.6 fps) & `free_heap` pulih 140812 setelah stop, 0 crash. Recording v3
  via `csi_recorder.js` (host reconstruct) POST → HTTP 200: stim_http (1092 frame),
  stim_tcp (119), stim_off (3); stim_ping 0 frame → ditolak server (valid, ping = legacy,
  tanpa CSI). Stress `_tcp_stress.py` 300 s: crashes=0, heap tanpa drift. Artefak di
  `reports/tcp_integration_wifi_sensing_demo/20261103T063000Z/`. Backup P1
  (`13e048afdc3dbed5…`, 4 MiB) terverifikasi; perangkat DITINGGAL pada firmware
  integrasi atas permintaan pengguna (ingin membuka web monitor sendiri); belum restore.

## 2026-11-03 — Koreksi: paired A/B denominator fps, TCP > HTTP (supersedes klaim "TCP bukan terbaik")

- Agent/tool: Qoder
- Branch/commit: default / belum di-commit
- File: `reports/tcp_integration_wifi_sensing_demo/20261103T063000Z/tests/paired_ab/_paired_ab.py`,
  `.../paired_ab/_plot_paired_ab.py`, `.../paired_ab/run1/{paired_ab.log,paired_ab.csv,paired_ab_results.json,paired_ab_fps.png}`,
  `.../FINAL_REPORT.md` (seksi Supersedendum + pointer pada "Honest performance finding"
  dan "Recommendation"). Tidak ada perubahan kode firmware; SHA bin tetap
  `49fb1709…` dan tidak di-flash ulang.
- Perubahan: pengukuran ulang HTTP vs TCP dengan **tiga denominator sekaligus** per blok
  60 s, selang-seling 3 ronde: (a) callback device (`csi_hz_x10/10`, angka yang dibaca
  browser), (b) AP-attributed (`csi_ap_frame_count/detik`, di-reset di
  `apply_stimulus_mode`), (c) delivered ke host (pesan `{"type":"csi"}` yang benar-benar
  diparsing) plus delta `dropped`. Harness memverifikasi `ack` tiap perintah
  (`send_checked`) alih-alih tidur tetap, dan mengembalikan `ap_window_s` agar
  denominator AP memakai rentang sejak reset, bukan sejak jendela.
- Alasan: gejala dari pengguna — web menunjukkan HTTP 60–90 fps, TCP 50–160 fps, padahal
  entri kampanye 2026-11-03 (sesi ini) mencatat HTTP 1092 vs TCP 119 frame/60 s dan
  menyimpulkan "TCP BUKAN stimulus terbaik". Penyebab konflik: dua metrik berbeda,
  `csi_frame_count` di-increment di ENTRY callback (`web_serial_monitor.c` L724) sebelum
  gate `csi_stream_enabled` (L739) dan sebelum antrean tulis UART, sedangkan tabel §D
  menghitung frame yang datang ke host. Hasil pengukuran baru: **TCP 35.8 Hz vs
  HTTP 25.2 Hz**, TCP unggul di ketiga ronde (per-1s TCP 26–48 Hz; HTTP 2–32 Hz), dan
  `delivered ≈ device` dengan `dropped Δ = 0` di semua blok → serial BUKAN limiter pada
  rate ini, sehingga selisih 1092-vs-119 dulu adalah perbedaan GENERASI frame pada
  window tersebut (saat itu juga ada churn reconnect Wi-Fi; rounds 6.7/s vs 16/s
  sekarang), bukan kehilangan di UART. Hipotesis lama "gateway RST port 80/53 → lebih
  sedikit frame downlink" gugur: handshake gagal tetap menghasilkan radio (~2.2 frame AP
  per round; 2 114–2 420 frame / ~968 round) dengan `connect_ok` 1–5 dari ~3 870 attempt.
  HTTP di lingkungan ini dibatasi WAN: 11–12 request 200 KB/60 s ≈ 37 kB/s dan sempat
  jatuh ke 2 Hz saat unduhan macet. Yang TIDAK terjelaskan: puncak 160 Hz yang dilihat
  pengguna melampaui maksimum per-1s yang harness catat (48.5 Hz) pada counter yang sama;
  dibiarkan sebagai belum terukur, tidak diklaim.
- Dokumen: `esp_wifi_sensing` (vendored, `managed_components/espressif__esp_wifi_sensing`) +
  `esp-radar` (`esp-radar/src/esp_radar.c` L1828) — `jitter`/`waveform_jitter` dihitung per
  jendela deteksi, dan README `espressif__esp_radar_motion_dec`: "Returns `0.0` when data is
  insufficient"; untuk arti readout fps web, sumbernya kode proyek ini sendiri
  (`web_serial_monitor.html` L4052, `web_serial_monitor.c` L2390–L2397, L1601) — tidak
  ditemukan dokumen ESP-IDF yang mendefinisikan metrik HMS ini (milik proyek).
- Verifikasi: read-only atas `/dev/ttyUSB0` @921600 (browser diputus lebih dulu; port eksklusif).
  Smoke 8 s x1 ronde: run pertama GAGAL (`delivered=0`) karena pulsa RTS me-reset board dan
  perintah START_CSI_STREAM hilang — artefak harness, diperbaiki dengan ack-check; run
  berikutnya sehat. Penuh 3 ronde x 2 mode x 60 s selesai, 0 crash, heap akhir 122–130 KB.
  Artefak: `tests/paired_ab/run1/paired_ab_fps.png`. Tidak ada commit; firmware tidak
  diubah sehingga hasil ini adalah pengukuran lingkungan, bukan perubahan perilaku.

## 2026-11-03 — SET_TCP_STIMULUS live + sweep parameter TCP: laju offer bukan limiter CSI

- Agent/tool: Qoder
- Branch/commit: default / belum di-commit
- File: `examples/esp-radar/wifi_sensing_demo/main/tcp_stimulus.c`,
  `main/tcp_stimulus.h`, `main/web_serial_monitor.c`,
  `tools/web_serial_monitor.html`,
  `reports/tcp_integration_wifi_sensing_demo/20261103T063000Z/tests/tcp_param_sweep/`
  (`preflight.md`, `_tcp_sweep.py`, `_plot_tcp_sweep.py`, `_reconstruct_from_log.py`,
  `_sweep_stats.py`, `_probe.py`, `_raw_capture.py`, `build/`, `run1/`, `run2/`, `run3/`,
  `_smoke*/`, `REPORT.md`), dan `.../FINAL_REPORT.md` (seksi Supersedendum II + pointer
  di Verdict dan header firmware).
- Perubahan:
  1. Perintah HMSCMD baru `SET_TCP_STIMULUS <conc> <interval_ms> <timeout_ms>`; semua
     token opsional sehingga bentuk tanpa arg = readback. Parameter diaplikasikan
     **in-place** ke task yang sedang jalan — sengaja TIDAK lewat `apply_stimulus_mode()`
     karena fungsi itu me-reset counter per-take, dan dispatch-nya dipasang sebelum gate
     `sensing_ready` (hanya butuh netif, sama seperti perintah stimulus lain). Satu boot
     kini mencakup seluruh grid, bukan satu sel per rebuild+flash.
  2. Validasi `timeout_ms` dilonggarkan dari `1..5000` ke `0..5000`; 0 adalah mode
     non-blocking yang nyata, bukan nilai dummy.
  3. **Bug race stop/start diperbaiki** dengan `portMUX_TYPE s_mux`: `tcp_stimulus_stop()`
     hanya menandai flag, sedangkan `tcp_stimulus_start()` return lebih awal selama task
     lama masih hidup — jadi penerapan ulang tcp→tcp (tombol "Apply mode" di browser,
     atau `SET_STIMULUS_MODE` yang diulang) diam-diam meninggalkan stimulus **OFF**.
     Task kini loop `for(;;)` dan memeriksa ulang `s_stop_requested` di dalam critical
     section sebelum melepas `s_running`; `start()` membatalkan stop yang tertunda.
  4. JSON `stimulus` objek `tcp` menambah `configured_timeout_ms`, `port`, `port_alt`.
  5. Panel web: tiga input (connections/interval/timeout) + hint + i18n EN&ZH; untuk mode
     tcp tombol apply mengirim `SET_TCP_STIMULUS` **saja** tanpa re-apply mode, sehingga
     counter tidak ter-reset; status pill menampilkan `4×/10ms/to 50ms · ok N/R r`.
- Alasan: pertanyaan pengguna apakah TCP masih bisa dioptimalkan. Preflight justru
  **membatalkan grid yang diusulkan** sebelum dijalankan: dengan `CONFIG_FREERTOS_HZ=100`
  (tick 10 ms) dan pembulatan ke atas di `sys_arch_sem_wait()`, timeout 25/10/5/1 ms
  jatuh ke kuantum tick yang sama dan interval 5 ms tidak bisa terwujud — grid yang sah
  adalah 50/20/10/0. Bug race di butir 3 ditemukan **dari membaca sumber**, bukan dari
  pengujian. Hasil pengukuran (`run2`, 9 sel x 60 s; `run3`, 8 sel berpasangan):
  **laju offer bukan pembatas** — rounds/s 16.0→141.9 (8,9x) dan SYNs/s 48→568 (11,8x)
  sementara CSI device hanya 35,33→40,67 Hz (1,15x), `delivered ≈ device` dengan
  `dropped Δ = 0` di semua sel. Satu-satunya sel kandidat (`timeout 0`, +10% di run2) TIDAK
  tereplikasi saat dipasangkan dengan control selang-seling: Δ +3,18 Hz, sd 6,75,
  t = 0,94, df = 3, tanda tidak konsisten 4/4 pasangan; sel control yang identik sendiri
  menyebar 1,27 Hz (run2) dan 28,96→38,02 Hz (dalam run3), jadi noise lingkungan lebih
  besar daripada beda antar sel. `connect_ok` 98 dan 7 per 60 s dari ~3 900 attempt di
  control, 0 di sel lain → jalur gateway praktis SYN→RST di semua timeout, dan `connect_ok`
  terlalu tidak stabil untuk dipakai sebagai fungsi objektif. Keputusan: **default A3
  4x/10 ms/50 ms dipertahankan** (memberi ~36 Hz yang sama dengan 1/9 churn paket, dan
  satu-satunya setting yang masih menuntaskan handshake); tidak ada perubahan perilaku
  firmware dari sweep ini. Hipotesis saya sendiri — "fps mengikuti rounds/s" — digugurkan
  oleh data smoke dan dikonfirmasi oleh run2/run3.
- Dokumen: ESP-IDF **v5.5.3** (salinan lokal
  `/home/azri/.espressif/v5.5.3/esp-idf`; MCP v6.0 tidak dipakai):
  `docs/en/api-guides/lwip.rst` L91 — "on ESP-IDF, `poll()` is implemented by calling
  `select()` internally"; L149/L228 — kesalahan berbasis select dibaca lewat
  `getsockopt(SO_ERROR)`, bukan `errno`; L394 — "not possible to delete a task while it
  is actively waiting on `select()` or `poll()` APIs"; `components/lwip/port/freertos/sys_arch.c`
  L159-184 — `timeout_ticks = ((timeout + portTICK_PERIOD_MS - 1) / portTICK_PERIOD_MS) + 1`,
  "shall wait for AT LEAST timeout"; `components/lwip/lwip/src/api/sockets.c` ~L2403 —
  `if (timeout == 0) { … "lwip_poll: no timeout, returning 0" }`; `components/freertos/Kconfig`
  + `sdkconfig` L1371 (`CONFIG_FREERTOS_HZ=100`); `components/esp_common/include/projdefs.h`
  L46 (`pdMS_TO_TICKS`); `sdkconfig` `CONFIG_LWIP_MAX_SOCKETS=10` (batas concurrency 8).
  Tidak ditemukan dokumen ESP-IDF yang mendefinisikan metrik fps HMS proyek ini —
  sumbernya kode proyek sendiri.
- Verifikasi: build inkremental bersih (tidak ada warning), gerbang SHA backup P1
  `13e048afdc3dbed5…` dicek ulang sebelum flash, flash selesai "Hash of data verified"
  saat itu; **catatan artefak**: log flash untuk build ini tidak tersimpan
  (`tests/tcp_param_sweep/build/` baru dibuat setelahnya), jadi identitas image dibuktikan
  ulang pada 11:42–11:43: `idf.py build` pada tree saat ini menghasilkan ulang app SHA
  `6231e0ab…` persis (0 warning, `build/build.log`) dan perangkat menjawab round-trip
  `SET_TCP_STIMULUS 2 30 15` → readback `c=2 i=30 t=15` → restore `4 10 50`
  (`build/device_livecmd_evidence.txt`) — perintah yang hanya ada di build ini.
  `node --check` pada script HTML yang diekstrak OK; `tools/tests/csi_recorder.test.js`
  dan `diag_session.test.js` lulus. `run1` **GAGAL di tengah** (sel 1 valid 29,57 Hz, lalu
  `SerialException … readiness to read but returned no data` / `OSError: [Errno 5]`; node
  by-id dibuat ulang pukul 10:10 dan device lalu melapor `mode:"off"`, counter 0,
  `switched_at_us` 6,16 s → board reboot + adapter re-enumeration, peristiwa level
  daya/kabel; sisi host tidak bisa membuktikan sebaliknya, artefak disimpan). Harness
  kemudian diperkeras (reopen by-id, simpan parsial per sel, retry 3x, deteksi reboot dari
  counter kumulatif yang mundur) dan `run2`/`run3` selesai 0 reopen / 0 reboot / 0
  disconnect. **Catatan insiden alat**: `_tcp_sweep.py` sempat menyimpan blok lama yang
  dobel (edit SearchReplace memulihkan salinan cache basi, 419→574 baris) sehingga `run3`
  mencetak dua ringkasan dan JSON-nya tertimpa 0 baris; 8 sel selamat di log dan dibangun
  ulang oleh `_reconstruct_from_log.py` (ditandai `reconstructed: true`; `ap_window_s`,
  `delivered_hz_min/max`, daftar kejadian Wi-Fi tidak bisa dipulihkan dan dibiarkan null),
  file rusak disimpan sebagai bukti. State device akhir: `mode=off`, parameter kembali ke
  4/10/50, heap 140 864, tidak ada reboot baru. Tidak ada commit.

## 2026-11-03 — Phase A audit pengukuran: harness HMS + pemulihan kredensial NVS

- Agent/tool: Qoder agent (sesi kampanye `protocol-benchmark.md`)
- Branch/commit: default / belum di-commit
- File:
  - **baru** `reports/csi_stimulus_benchmark/20261103T074916Z/tools/hms_capture.py` (v2),
    `tools/meta_audit.py`, `tools/csv_audit.py`, `tools/residual_audit.py`,
    `tools/diag_arm.py`, `tools/connect_ap.py`, `tools/run_ladder_a.sh`,
    `tools/_archive_hms_capture_v1_windowbug.py` (arsip bug)
  - **baru** `reports/csi_stimulus_benchmark/20261103T074916Z/campaign_plan.md`,
    `measurement_audit.md`, `measurement/_quarantine_serial_race/README.md`
  - **tidak ada** file firmware (`main/**`), UI (`tools/web_serial_monitor.html`),
    `sdkconfig*`, atau `managed_components/**` yang diubah sesi ini.
- Perubahan:
  1. Harness pengukuran baru untuk jalur HMS serial: satu lintasan serial menghasilkan
     enam definisi FPS terpisah, delta counter dalam-jendela, utilisasi baud, RTT perintah,
     dan gerbang validitas (capture ditandai INVALID, bukan "dipakai", bila state perangkat
     tidak terverifikasi). Tidak ada perubahan perangkat.
  2. Harness menangkap baris `ESP_LOGW … csi_cb window: rx=… no_peer=… filtered=… queued=…
     dropped=…` dari esp-radar, karena itu **satu-satunya** counter yang ada sebelum seleksi
     peer dan tidak pernah masuk telemetri HMS.
  3. `ht_stimulus_start()`/stop race (defect perangkat, **belum diperbaiki**): harness kini
     menunggu perangkat "hening", mengirim mode, lalu menuntut progres (`http.requests>=1`,
     `tcp.rounds>=1`) — bukan hanya flag `running` — dan menandai capture invalid bila gagal.
  4. **Perubahan state perangkat**: kredensial Wi-Fi di NVS ditulis ulang lewat perintah resmi
     `HMSCMD WIFI_CONFIG_HEX <hex ssid> <hex pass>` oleh `tools/connect_ap.py`. Penyebab:
     boot log memperlihatkan NVS berisi SSID `"SMEAPREMIUMKUPIWARUNG@WIFI.ID"`, bukan AP
     kampanye, sehingga device gagal koneksi (`WIFI_INFO` FAILED, reason 201 NO_AP_FOUND) dan
     semua capture kosong. Passphrase diambil dari backup flash P1 milik user sendiri, tidak
     pernah dicetak, dan dibersihkan dari byte yang ditangkap log. **Tidak** ada `erase_flash`,
     tidak ada penghapusan NVS, tidak ada penghapusan rekaman lama.
  5. Kuarantin data: delapan leg `run_ladder_a.sh` dipindahkan ke
     `measurement/_quarantine_serial_race/` (tidak dihapus) karena runner pernah terluncurkan
     dua proses sekaligus dan berebut port serial; README menyimpan buktinya dan menegaskan
     tidak ada kesimpulan defect yang boleh diambil dari data itu.
  6. `run_ladder_a.sh` dan `hms_capture.py` sekarang memegang `flock` pada port serial.
- Alasan (bukti pengukuran, semua jendela 20–30 s, kap 60 s dipatuhi):
  - Lima angka historis (32.6 / 1.98 / 9.86 / 35–47 / ~160) ternyata tidak pernah mengukur
    hal yang sama: 32.6 = jumlah **pesan**/15 s; 35–47 = `csi_hz_x10` yang dihitung dari
    `csi_frame_count` di `web_serial_monitor.c:724` (**sebelum** gerbang emisi dan sebelum
    semua drop); 1.98 dan 9.86 = rata-rata pesan/jendela panjang dari take yang mengandung
    stall 10.5 s; ~160 **mustahil** sebagai angka host — satu baris `csi` rata-rata 1446 B
    terukur, sehingga plafon 921600 baud 8N1 adalah ≈63 fps (`csi` saja) dan ≈45 fps bila
    stream `sample` HUD ikut (283 kbps terukur).
  - Kata `fps` tidak ada di UI sama sekali; satu-satunya angka laju adalah pill
    `stimulusRate: "CSI {hz} frame/s"` (`web_serial_monitor.html:1161,4086`) yang menampilkan
    counter sisi perangkat. Jadi "FPS browser" selama ini adalah laju callback perangkat.
  - Temuan baru yang mengubah desain benchmark: **biaya emisi menekan laju callback**.
    Hanya mengubah throttle 0→100 ms, `rx` di entry callback esp-radar naik 34.89→88.73 Hz
    (`H1` vs `H2`). Tidak ada counter di bawah `esp_radar_csi_rx_cb`, jadi kehilangan di
    tahap itu tidak terlihat oleh siapa pun.
  - Identitas `emitted−1 + dropped_delta == Δseq` berlaku **tepat (selisih 0) di 10/10 leg
    valid**, termasuk leg throttle (265+2931=3196). Karena itu keputusan Phase A5: **tidak**
    menambah sequence ID ke payload; `seq` (diberikan per callback, `esp_radar.c:992`) +
    `csi_dropped_count` (diincrement di `:754,760,768,778,848,860`) + `rx_seq` (`uint16_t`,
    diteruskan di `:841`) sudah menutup kebutuhan akuntansi. Yang tetap terbuka: kehilangan
    pra-callback, dan `dropped` yang menggabungkan throttle dengan kegagalan transport.
  - Repetabilitas A-B-A kondisi identik: 34.16 / 38.31 / 35.52 fps (±6 %). Perbedaan kandidat
    < ±12 % tidak resolusi dengan satu leg 30 s.
  - Defect lain yang terbukti: ICMP tidak punya counter apa pun di telemetri
    (`ping_request_count` dkk. `null` dengan `metrics_reason`, `web_serial_monitor.c:1523`),
    dan nama mode telemetry `icmp_ping_gateway` berbeda dari token perintah `icmp_ping`
    (`stim_mode_name()` di `:1546`) — jebakan yang sempat membuat harness menandai leg sehat
    sebagai invalid. `recording.dropped_on_device` di `.meta.json` adalah counter kumulatif
    perangkat (`web_serial_monitor.html:4539`), bukan dalam-take; yang dalam-take adalah
    `dropped_delta`.
- Dokumen: ESP-IDF v5.5.3 `components/esp_wifi/include/local/esp_wifi_types_native.h` —
  "uint16_t rx_seq"; esp-radar 0.3.4 `esp-radar/src/esp_radar.c:949,971,990,992,944` —
  "stat_rx++ … filtered_info->seq_id = peer->csi_seq++"; proyek
  `main/web_serial_monitor.c:59,72,724,739,754–778,841,1268–1269,1523,1603,1901,2183,2459`
  dan `main/ht_stimulus.c:190–198` — "s_enabled = true; if (s_running) { return ESP_OK; }".
  MCP `esp-idf` (v6.0) tidak dipakai; versi tidak cocok dengan build proyek ini.
- Verifikasi: `python3 -m py_compile` pada harness; leg live A/B1/B2/B3/C/E/F/G/G1/G2/H1/H2
  dengan hasil tercetak VALID/INVALID + alasan-nya di `measurement/*.summary.json`;
  identitas akuntansi dihitung ulang dari file itu; koneksi AP dikonfirmasi
  (`GOT_IP`, ch1, rssi −53, ip 192.168.1.10, bssid f8:73:1a:59:23:f4); build/flash **tidak**
  dijalankan karena tidak ada file firmware yang berubah. Tidak ada commit.
- Catatan ketidakpastian yang jujur: RSSI hari ini −53 (pagi tadi −60) dan satu GOT_IP
  sempat muncul selama percobaan passphrase salah; keduanya dicatat sebagai observasi, bukan
  bukti kausal. Angka "160 Hz" tidak pernah saya ukur — hanya dibuktikan tidak mungkin sebagai
  angka host.

## 2026-11-03 — Phase B baseline HTTP + PHY watch di harness

- Agent/tool: Qoder agent (sesi kampanye `protocol-benchmark.md`)
- Branch/commit: default / belum di-commit
- File:
  - `reports/csi_stimulus_benchmark/20261103T074916Z/tools/hms_capture.py` (ubah)
  - `reports/csi_stimulus_benchmark/20261103T074916Z/tools/run_baseline_b.sh` (baru)
  - `reports/csi_stimulus_benchmark/20261103T074916Z/baseline_http.md`,
    `hypothesis_ledger.md` (baru), `campaign_plan.md` (§7b + status, ubah)
  - `experiments/http_baseline/BL0..BL3.*` (data) + `measurement/smoke_phy_off_10s.*`
  - **tidak ada** file firmware/UI/sdkconfig yang berubah.
- Perubahan:
  1. Harness menambah PHY watch: tiap probe RTT dalam jendela kini mengirim
     `WIFI_INFO`; balasan `wifi` (state/bssid/channel/rssi/ip,
     `web_serial_monitor.c:1819–1832`) dirangkum jadi `phy_watch` dan **gerbang
     invalid baru** menolak leg yang device-nya asosiasi ke BSSID selain
     `f8:73:1a:59:23:f4` (mandat §2.1). Alasan: RSSI/channel adalah metrik §11E
     dan empat leg BL0–BL3 terlanjur jalan tanpa bukti kondisi radio per-leg.
  2. Ladder Phase B: empat leg @60 s tepat (BL0 off, BL1–BL3 http
     `burst=200000 pause=100`, p0, hud off) dengan flock serial; semua VALID.
- Alasan (bukti pengukuran di `baseline_http.md`):
  - Baseline HTTP kanonik = **31,85 fps device_cb** (30,94/33,16/31,46; spread
    ±3,5 %, di bawah floor resolusi ±6 % Phase A). Kontrol off 1,27 Hz —
    lingkungan radio hari ini lebih ramai dari pagi (0,22 Hz), jadi bracket
    A-B-A wajib, bukan formalitas.
  - Audit `ht_stimulus.c` (333 baris, dibaca utuh): `keep_alive_enable=true`
    (`:110`) tidak pernah berpengaruh karena client di-`cleanup()` tiap burst
    (`:158`) → handshake TCP+HTTP terulang per request; `active_ms` 55,4–58,2 s
    dari 60 s = duty radio 92–97 %, `pause=100` ms praktis hilang; dependensi
    internet **terbukti** (34/38 burst sukses, 6 834 944 B, `errors=0`) —
    HTTP bukan LAN-only. Literal `?bytes=2000000` di sdkconfig tidak pernah
    dipakai karena `build_url()` membangun ulang query dari burst runtime
    (`:69–77`).
  - Heap turun selama stimulus (140k→44k di BL3) dan pulih ke 140,2 k saat off
    (smoke) — dicatat sebagai observasi, bukan klaim leak.
- Dokumen: `main/ht_stimulus.c:106–158,196–200`, `main/web_serial_monitor.c:1513–1537,
  1819–1832`, `sdkconfig:446–450`, `main/Kconfig.projbuild:57–120` — kutipan:
  "esp_http_client_cleanup(client); … keep_alive_enable = true";
  "s_running … if (s_running) { return ESP_OK; }". Tidak ada dokumen eksternal
  yang dipakai sesi ini (tidak ada perubahan firmware).
- Verifikasi: `py_compile` harness; smoke 10 s membuktikan `phy_watch` terisi
  (rssi −53, ch 1, bssid target) dan leg tetap VALID; empat ringkasan
  `*.summary.json` BL0–BL3 VALID dengan identitas akuntansi exact (47/1886/1986/1855);
  angka agregat (38 req / 34 succ / 1 fail / 0 err / 6 834 944 B) dihitung ulang
  dari file dengan skrip, bukan diketik manual. Build/flash tidak dijalankan.

## 2026-11-03 — Phase C2: modul stimulus DNS (`dns_stimulus.c`) + integrasi HMS + fix pacing tick

- Prioritas: tinggi (membuka Phase C3 screening).
- File:
  - `examples/esp-radar/wifi_sensing_demo/main/dns_stimulus.c` (baru, 337 baris; lalu diperbaiki)
  - `examples/esp-radar/wifi_sensing_demo/main/dns_stimulus.h` (baru)
  - `examples/esp-radar/wifi_sensing_demo/main/web_serial_monitor.c` (ubah: mode `dns_query`, parser `SET_STIMULUS_MODE dns_query [interval timeout]`, blok telemetri JSON `"dns":{...}`, reset/stop link-down)
  - `examples/esp-radar/wifi_sensing_demo/main/CMakeLists.txt` (ubah: +`"dns_stimulus.c"`)
  - `reports/csi_stimulus_benchmark/20261103T074916Z/tools/hms_capture.py` (ubah: whitelist `dns_query`, arm gate `running && queries_sent>=1`, blok `dns` + delta di `stimulus_in_window`)
  - Data: `measurement/preflight_dns_p100_20s.*` (pre-fix), `measurement/preflight_dns_pacingfix_p100_20s.*` (post-fix), `firmware/{build_logs,flash_logs,source_hashes}/20261103T0940_dns_c2_pacingfix_*`
- Perubahan:
  1. Stimulus DNS baru: query RFC1035 dibangun manual (satu nama tetap `speed.cloudflare.com`, tanpa spraying domain), server diambil dari `esp_netif_get_dns_info` STA (MAIN→BACKUP, bukan hardcode), validasi respons = id + QR + opcode 0 + rcode 0 + ANCOUNT≥1 + **alamat sumber == server yang ditanya**; metrik per transaksi (queries/ok/bad/timeouts/errors/bytes/latency µs min-max-last). Lifecycle task meniru pola `tcp_stimulus.c` (handshake `portMUX` start/stop), bukan `ht_stimulus.c` yang cacat early-return.
  2. **Bug pacing ditemukan dan diperbaiki**: preflight pertama (interval terkofnfigurasi 100 ms) menghasilkan 748 query/20 s ≈ 37 qps. Akar: `CONFIG_FREERTOS_HZ=100` (`sdkconfig:1371`, tick 10 ms) membuat `pdMS_TO_TICKS(5)` = 0 tick → `vTaskDelay(0)` tidak tidur → loop slice habis seketika. Fix: slice clamp ≥1 tick dan `remaining` dikurangi waktu tidur sesungguhnya. Pola identik masih ada di `tcp_stimulus.c` (komentar `:177–179` mengakui); TIDAK diubah di tengah kampanye — angka 49,5 Hz TCP lama harus dibaca dengan pemahaman ini (catatan untuk Phase D/E).
- Alasan: mandat §6.2 meminta mode DNS terukur sebelum screening; verifikasi pasca-fix: 157 query/20 s window (steady-state 182 rounds ≈ 8,2 qps ≈ 1/(100 ms + latency 23 ms)), 0 bad/0 timeout/0 error, latensi min 22,3 ms — pacing 100 ms kini diberlakukan nyata, ceiling 100 qps aman untuk tangga 10 ms (siklus ≈33 ms ≈ 30 qps).
- Dokumen: `docs/agent-preflight.md` (dibaca ulang gerbang absolut); sumber otoritatif = pohon IDF v5.5.3 terpasang (MCP espressif-docs/context7 tidak tersedia sesi ini; MCP esp-idf terdaftar menunjuk v6.0 — tidak dipakai). Kutipan `esp_netif.h:704,740`: "The default Main DNS server is typically the IP of the DHCP server itself." / `esp_err_t esp_netif_get_dns_info(esp_netif_t *esp_netif, esp_netif_dns_type_t dns_type, esp_netif_dns_info_t *dns);`; `lwip/prot/dns.h:103–116`: `DNS_SERVER_PORT 53`, `DNS_RRTYPE_A 1`; tick `sdkconfig:1371` `CONFIG_FREERTOS_HZ=100`. Tidak ada dokumen eksternal yang menyatakan pacing slice-loop — itu bug kami sendiri.
- Verifikasi: build sukses (bin `0xf1490`, 6 % partisi free), flash `Hash of data verified` (exit 0); preflight 20 s VALID pasca-fix dengan telemetri `server=192.168.1.1` (cocok dengan audit host C1 `dns_audit.md`); identitas akuntansi exact (163+0=163/cb=163). Catatan integritas: log build/flash C2 pra-fix (`20261103T0840_*`) ditemukan **hilang** dari `firmware/` saat langkah ini — di regenerate untuk bin pasca-fix; bin pra-fix tidak dapat direkonstruksi (sha lama `53893f38…` hanya tersimpan di catatan sesi).

## 2026-11-03 — Phase C3: screening tangga pacing DNS + defect gerbang BSSID harness

- File:
  - `reports/csi_stimulus_benchmark/20261103T074916Z/tools/run_screening_c.sh` (baru)
  - `…/experiments/dns_udp/{CL0_off,C1_dns_p100,C2_dns_p50,C3_dns_p20,C4_dns_p10,CL5_off}_60s.*` (data)
  - `…/dns_screening.md` (baru, deliverable), `…/hypothesis_ledger.md` (H-C3 diisi),
    `…/campaign_plan.md` (§7c + status)
  - Tidak ada perubahan firmware/sdkconfig pada langkah ini.
- Perubahan: ladder enam leg (off-bracket, 100/50/20/10 ms, off-bracket), tiap
  capture tepat 60 s, flock serial, `timeout=500`, `p0`, `hud off`.
- Alasan (angka dari `*.summary.json`, dihitung skrip): qps jendela
  8,15/13,75/24,38/31,87 ≈ 1/(interval+latensi 22 ms); device_cb
  8,236/14,980/24,642/32,252 mengikuti 1:1; 0 responses_bad/timeouts/errors di
  keempat rung; identitas exact (493/897/1477/1934 + dropped 0); ceiling 100
  qps mandat tidak tersentuh. Mode DNS dinyatakan terbukti → §6.2 membuka
  jalan integrasi dropdown web; diputuhkan setelah Phase G agar opsi UI ikut
  hasil akhir, dicatat eksplisit.
- Insiden: CL0/CL5 invalid — gerbang BSSID (ditambahkan Phase B) menghitung
  probe `00:00:00:00:00:00` (device fasa transisi tidak terasosiasi setelah
  stimulus→off) sebagai asosiasi asing, dan window off penuh tanpa baris csi
  membuat `device_cb=None`. Defect gerbang di harness, bukan firmware;
  diperbaiki sebelum A-B-A Phase G dengan entri changelog sendiri. Observasi
  terpisah yang jujur: dua-duanya terjadi tepat setelah transisi mode, jadi
  fasa reconnect nyata bisa terjadi di ujung tangga — tidak diklaim, hanya
  dicatat.
- Dokumen: `docs/agent-preflight.md` (gerbang); mandat
  `examples/esp-radar/wifi_sensing_demo/docs/protocol-benchmark.md` §6.2
  (dibaca ulang baris 404–481): "Batas awal maksimum 100 query per detik",
  "Pacing awal 100 ms / 50 ms / 20 ms / 10 ms", "Integrasikan ke dropdown web
  hanya setelah mode DNS terbukti bekerja." Tidak ada perubahan perilaku
  runtime → tidak perlu dokumen eksternal baru.
- Verifikasi: keempat rung VALID oleh gerbang §5; agregat dihitung dari file
  dengan skrip (bukan diketik); log ladder `experiments_screening_c.log`
  menyimpan kedua INVALID apa adanya; device dikembalikan ke `off` di ujung
  ladder dan kesehatan link diverifikasi smoke setelahnya.

## 2026-11-03 — Phase D: audit ICMP + harness `--take` (observasi diag per-transaksi)

- File:
  - `reports/csi_stimulus_benchmark/20261103T074916Z/tools/hms_capture.py` (ubah)
  - `…/icmp_audit.md` (baru, deliverable §7 mandat), `…/hypothesis_ledger.md`
    (H-D1/H-D2), `…/campaign_plan.md` (status)
  - Data: `measurement/smoke_take_{dns_p100_15s,icmp_p10_20s,icmp_p10_20s_b}.*`,
    `experiments/icmp_phaseD/D_icmp_p100_60s.*` (termasuk sidecar `.esplog.txt`)
  - **Tidak ada perubahan firmware/sdkconfig/main pada langkah ini.**
- Perubahan harness:
  1. Flag `--take <epoch>`: kirim `HMSCMD TAKE_BEGIN/END` mengapit jendela
     dwell; gerbang valid baru menolak TAKE ack gagal dan (untuk `icmp_ping`)
     nOL event ping dalam take. Retry sekali bila take lama masih terbuka.
  2. Parsing counter `sel: ok/legacy/dmac/null/nopeer` dari baris window
     esp-radar (sebelumnya hilang karena token `"sel:"` bukan identifier) +
     sidecar `.esplog.txt` berisi baris mentah (rej:/peers[]/srcs{}),
     truncation 400→1200 karakter.
- Alasan (hasil terukur, `icmp_audit.md` §6): tahap 1–2 ICMP **lolos** pada
  10 Hz dan 100 Hz official-parity (tx==rx==2531, tg median 2 ms), tapi
  callback CSI menerima **nol** frame AP (f8:73) maupun device (00:c3) selama
  60 s penuh — hanya STA tetangga yang lewat; `device_cb=None`, 0 baris csi.
  Identifikasi tahap mandat = 3/4. Sub-sebab (AP tidak transmit vs driver
  buang pra-callback) TIDAK terbedakan oleh telemetri ada dan dihentikan di
  sana (aturan "katakan tidak ditemukan"). Koreksi dokumentasi lama: alasan
  "FSM ping tidak memanggil callback esp_ping" di telemetri salah di level
  komponen — callback ada; main yang tidak membaca counter, dan diag et=ping
  hanya terekam dalam take.
- Dokumen: `docs/agent-preflight.md` (gerbang, blok Dokumen/Kutipan sesi ini
  sudah ditulis sebelum edit `main/**` pertama di C2). Sumber baca Phase D:
  `examples/get-started/csi_recv_router/main/app_main.c:183–204` (kutipan:
  `ping_config.count = 0; ping_config.interval_ms = 1000 / CONFIG_SEND_FREQUENCY;`
  dengan `#define CONFIG_SEND_FREQUENCY 100` — mandat §7 menulis "count = 100";
  itu frekuensi, bukan count: koreksi pembacaan didokumentasikan),
  `esp_wifi_sensing/src/esp_wifi_sensing.c:919–956` (`hms_ping_start`,
  `interval_ms = 1000/frequency_hz`, `data_size=1`), `sdkconfig:2097`
  (`CONFIG_ESP_WIFI_SENSING_PING_FREQUENCY_HZ=10`), `web_serial_monitor.c:970–1000`
  (admission diag hanya saat take terbuka), `esp-radar/src/esp_radar.c:703–760`
  (`esp_radar_select_peer`, jalur legacy filter_mac).
- Verifikasi: `py_compile` OK; smoke `--take` di DNS membuktikan TAKE_BEGIN/END
  di-ack (`diagnostics_enabled=true`, counter barrier nol semua); leg ICMP
  menghasilkan 143/170/5059 event dengan tx/rx yang menutup (rx==tx); take
  yatim dari run yang crash (directory belum dibuat — FileNotFoundError,
  exit sebelum tulis artefak) ditutup manual via TAKE_END dan diverifikasi
  TAKE_BEGIN/END baru sukses; satu INVALID jujur tersimpan di
  `experiments/icmp_phaseD/` ( nol csi + gerbang BSSID fasa transisi).

## Phase E — HTTP variants screening (2026-11-03)

**File yang berubah:**
- `examples/esp-radar/wifi_sensing_demo/main/ht_stimulus.c`
- `examples/esp-radar/wifi_sensing_demo/main/ht_stimulus.h`
- `examples/esp-radar/wifi_sensing_demo/main/web_serial_monitor.c`
- `examples/esp-radar/wifi_sensing_demo/main/Kconfig.projbuild`

**Apa yang berubah:**
- `ht_stimulus.c`: `HT_STIMULUS_BURST_MIN` diturunkan 100 000→4 000;
  tambah `s_keep_alive` volatile;重构 task loop menjadi dua jalur (ka=on: init
  sekali di luar loop, reuse client handle; ka=off: init→cleanup per burst
  seperti sebelumnya); pause loop memakai tick-clamp ≥1 sama seperti
  `dns_stimulus.c`; error path ka=on melakukan re-init koneksi.
- `ht_stimulus.h`: field `bool keep_alive` di `ht_stimulus_config_t`.
- `web_serial_monitor.c`: argumen ke-3 opsional di `SET_STIMULUS_MODE
  http_cloudflare` (on/off); absent → **false secara eksplisit** (fix bug
  inheritance); telemetri JSON `http.keep_alive` ditambahkan.
- `Kconfig.projbuild`: range minimum burst diturunkan ke 4000.

**Alasan:** Mandat §8 menguji 10 variasi HTTP termasuk response kecil (4/16/64 KB),
keep-alive sejati, dan interval variation. Tidak ada satu pun yang bisa diukur
tanpa perubahan parameter minimum dan mekanisme lifecycle koneksi.

**Dokumen yang dipakai:** `protocol-benchmark.md` §8; `baseline_http.md` §1
(audit ht_stimulus lifecycle, H-B3 confirmed); ESP-IDF v5.5.3 `esp_http_client`
API (init/open/read/close/cleanup lifecycle and keep_alive_enable semantics).

**Verifikasi:**
- Build sukses: `0xf16a0` sha `64a8...` (hash fix flash kedua).
- Preflight 20 s: 4KB ka=off VALID (12.35 fps); 4KB ka=on VALID (13.04 fps).
- Screening 9 leg × 60 s: semua VALID di firmware fix (dua retry untuk E5 dan E9
  karena BSSID transient gate).
- Deliverable: `http_variants.md`; ledger H-E1/E2/E3 confirmed.
- Defect ditemukan & diperbaiki dalam sesi: ka-inheritance (ka_tok absent →
  s_keep_alive diwarisi dari mode sebelumnya); fix = explicit false when NULL.
## 2026-11-03 — Phase G (A-B-A finalists) + Phase H (window 24-frame)

- Agent/tool: Qoder
- Branch/commit: default / belum di-commit
- File: `reports/csi_stimulus_benchmark/20261103T074916Z/aba_benchmark.md`,
  `window_assessment.md`, `comparison.csv`, `comparison_legs.csv`,
  `tools/aggregate_phase_g.py`, `tools/phase_h_window.py`,
  `hypothesis_ledger.md` (H-G1/G2/G3 + H-H1), `campaign_plan.md`. Data mentah di
  `experiments/aba_benchmark/` (14 leg ×60 s, `.summary.json`/`.lines.tsv`/`.esplog.txt`).
- Perubahan: **tidak ada kode runtime yang diubah.** Fase ini hanya mengukur,
  mengagregasi, dan memutuskan. 14 leg A-B-A dijalankan pada firmware build
  `0xf16a0` (perbaikan inheritansi keep-alive dari sesi Phase E). Runner:
  `run_g.sh` (A-B-A-B-A-C-A-D-A-B) + `run_g64.sh` (konfirmasi 64 KB: A6-C2-A7-C3)
  karena §10.3 menuntut ≥3 recording independen untuk kandidat terpilih.
- Alasan: kandidat screening Phase E (keep-alive E6=38,1 dan 64 KB E3=34,6) wajib
  diverifikasi ulang dengan bracket baseline karena lingkungan radio tidak stasioner
  (H-B/D). Hasil: **keep-alive REJECTED** — di bawah bracket device_cb 25,6/5,6/34,9
  (mean 22,1, worst gap 10,5 s, satu bucket 0,5 s kosong, no_peer 19,6) vs baseline
  mean 34,6. Angka E6 adalah artefak momen radio, bukan sifat protokol.
  **64 KB CONFIRMED menang** — device_cb 36,0–36,5 (spread 1,4 %), no_peer 0,16
  (vs baseline 8,56), 0 empty-bucket. **Pemenang §12 = `http_cloudflare 65536 0 off`.**
  Phase H: extractor frame-indexed 24/12 ⇒ window 24-frame = ~0,62 s (CV 10 %),
  jam host≈device (jitter dari sumber radio), tak ada kandidat capai ≥50 frame/0,5 s
  ⇒ rekomendasi timestamp-aware (jalur turunan terpisah, extractor utama tak diubah).
- Dokumen: `protocol-benchmark.md` §10.2/§10.3/§12/§13/§15; `fall_detection/dataset_io.py`
  (BASELINE_WINDOW_FRAMES=24, STRIDE=12, loop frame-indexed).
- Verifikasi:
  - 14/14 leg VALID (gerbang §5: mode terbukti + `csi` terdistribusi + BSSID target).
  - Bracket valid: 7 baseline device_cb 32,1–36,2 (spread 11,7 % < ambang 25 % §10.2).
  - Akuntansi tertutup di 14/14 (emitted−1+dropped == Δseq, seq_gap=0, dropped=0).
  - comparison.csv/legs.csv diregenerasi dari summary JSON (`aggregate_phase_g.py`).

## 2026-11-03 — KOREKSI Phase G: no_peer = interferensi AP asing, klaim "64 KB unggul" dicabut

- Agent/tool: Qoder
- Branch/commit: default / belum di-commit
- File: `aba_benchmark.md` (ditulis ulang), `hypothesis_ledger.md` (H-G2/G3 → INCONCLUSIVE),
  `comparison.csv` (kolom winner diluruskan), `tools/check_no_peer_source.py` (baru).
- Perubahan: tidak ada kode runtime. Ini **pembatalan sebagian** dari entri Phase G
  sebelumnya yang menyatakan "64 KB menang di konsistensi peer (no_peer 0,16)".
- Alasan: audit esplog `check_no_peer_source.py` atas 14 leg membuktikan `no_peer` HANYA
  berasal dari sumber co-channel asing `d4:53:2a:61:a2:c1` (no_peer≈0 di window target-only;
  melonjak saat asing hadir). `foreign%` berubah sepanjang waktu nyata dan menjelaskan
  device_cb antar-leg. Pada **blok tenang terkontrol** (A6-C2-A7-C3, radio sama, back-to-back):
  baseline 200KB 36,2/36,1 ≡ 64KB 36,0/36,5 (selisih <1,5%) → **tidak ada keunggulan
  throughput/konsistensi 64KB atas baseline.** Sesuai mandat §10.2/§15 ("jangan nyatakan
  unggul bila perubahan kondisi radio dapat menjelaskan hasil"), klaim semula dicabut.
  keep-alive TETAP ditolak karena kegagalan tingkat-aplikasi (G_B2 gap 10 475 ms,
  fw_reported=0, counter requests stall) yang tidak dapat dijelaskan interferensi.
- Dokumen: `protocol-benchmark.md` §10.2, §12, §15; esplog `esp_radar_csi_rx_cb` (srcs/rej).
- Verifikasi:
  - 14 esplog di-parse; korelasi no_peer↔foreign% tegas (lihat tabel §0 `aba_benchmark.md`).
  - Blok tenang: 3 leg (A6/C2/C3) + A7 semuanya 36,0–36,5 → baseline==64KB.
  - comparison.csv diregenerasi: label winner = "http-class-tie-recommended ... NOT-faster-in-quiet-block".

## 2026-11-03 — Phase I (laporan akhir + grafik) & Phase J (kondisi akhir)

- Agent/tool: Qoder
- Branch/commit: default / belum di-commit
- File: `reports/csi_stimulus_benchmark/20261103T074916Z/FINAL_REPORT.md`,
  `end_state.md`, `visualizations/**` (9 PNG), `tools/phase_i_charts.py`,
  `firmware/source_hashes/20261103T_phase_J_endstate.sha256`,
  `experiments/final_state/J_*`, `campaign_plan.md` (status). Tidak ada kode runtime diubah.
- Perubahan: menyusun laporan final 14 pertanyaan + klasifikasi (terbukti/gagal/inconclusive/
  belum diuji/keterbatasan); menghasilkan grafik dari data yang benar-benar ada; memverifikasi
  kondisi akhir perangkat.
- Alasan: menyelesaikan kampanye §14/§16/§17. Grafik yang TIDAK dibuat secara eksplisit dicatat
  (browser parsed/rendered FPS: recorder tidak dalam loop leg A-B-A; heatmap magnitude:
  amplitudo 52 subcarrier tidak dikirim HMS — hanya metadata). Keadaan akhir diverifikasi:
  stimulus OFF (J_off_final VALID, heap 138708, tanpa crash), HMS streaming bekerja
  (J_hms_check @64KB device_cb 36,72, akuntansi 439+0=439).
- Verifikasi SHA firmware (non-destruktif): `esptool read_flash 0x20000 len 988832` → sha256
  `d3b3b0a7…` == `build/wifi_sensing_demo.bin` (0xf16a0). Ditemukan & dicatat: log flash build
  fix (0xf16a0) tidak pernah disimpan in-band (hanya build#1 0xf16b0 yang ter-log), sehingga
  end-state diverifikasi lewat read-back, bukan asumsi. P1 backup `p1_flash_backup/` utuh
  (p1_full_flash_4MB.bin sha `13e048af…`) dan TIDAK dipulihkan.
- Dokumen: `protocol-benchmark.md` §14, §16, §17.

## 2026-11-03 — Panel "Wi-Fi Stimulus Control" di Web Serial Monitor (host-only)

- Agent/tool: Qoder
- Branch/commit: default / belum di-commit
- File: `examples/esp-radar/wifi_sensing_demo/tools/web_serial_monitor.html` (tambah panel +
  i18n EN/ZH + JS); `reports/web_stimulus_control/20261103T145232Z/REPORT.md`. TIDAK ada file
  firmware C yang berubah; TIDAK ada re-flash.
- Perubahan: menambah panel pilihan stimulus (dropdown 4 preset: OFF / HTTP 200 KB / HTTP 64 KB /
  TCP) dengan tombol Apply/Start dan STOP/OFF, plus Selected vs Active Mode, mesin status
  (OFF/STARTING/ACTIVE/STOPPING/ERROR/UNKNOWN), Last Command/Response, indikator akuisisi CSI
  (device-cb fps, host-received fps, frames, dropped, RSSI, heap, serial), transition-lock,
  Retry, dan penanganan putus-koneksi→UNKNOWN. Memilih preset tidak langsung men-stimulus;
  aktivasi lewat Apply. Panel lama "Traffic Stimulus" dipertahankan.
- Alasan: mandat user — mengendalikan stimulus lewat browser tanpa terminal. Audit source
  (Phase A) menemukan bahwa command + telemetri yang dibutuhkan SUDAH ada dan build aktif sudah
  memuat TCP/DNS, sehingga solusi benar = UI-only reuse, bukan implementasi stimulus baru. Ini
  juga pekerjaan kontrol manual, bukan kampanye optimasi (dilarang mengulang eksperimen A-J).
  Angka TCP 4/10/50 diverifikasi dari source (bukan tebakan): urutan command =
  `SET_TCP_STIMULUS <concurrency> <interval_ms> <timeout_ms>`, default kompilasi conc=4/int=10/
  to=50/port 80→53. `SET_STIMULUS_MODE` ack tidak ber-epoch → panel pakai waiter ACK sendiri.
- Dokumen: `wifi_sensing_demo` source `main/web_serial_monitor.c` (handle_set_stimulus_mode
  :1669-1735; apply_stimulus_mode :1597-1638 mutual-exclusion; send_stimulus_state :1521-1570
  telemetry mode/running/csi_hz_x10/free_heap/http.keep_alive/tcp.configured_*; send_ack
  :935-941 no-epoch), `main/tcp_stimulus.c:32-37` + `main/tcp_stimulus.h:33-34` (default
  conc=4 interval=10ms timeout=50ms port 80->53). Tidak mengubah driver/radio/protokol.
- Verifikasi:
  - `node --check` JS inline (baris 879-5571) → SYNTAX_OK; tidak ada id duplikat (16 id baru 1x).
  - Suite existing lolos: csi_recorder.test.js exit 0, diag_session.test.js exit 0.
  - Build aktif `0xf16a0` (988832 B) dipindai: memuat tcp_stimulus_start, dns_stimulus_start,
    handle_set_tcp_stimulus, STIM_MODE_TCP → TCP preset didukung tanpa re-flash.
  - E2 (ESP32 nyata) & E3 (Brave nyata) BELUM dilakukan: tidak ada perangkat di /dev/ttyUSB* /
    /dev/serial/by-id/. Tidak diklaim lulus; prosedur manual ditulis di REPORT.md.

## 2026-11-03 — Merge panel stimulus jadi satu kotak di Web Serial Monitor (host-only)

- Agent/tool: Qoder
- Branch/commit: default / belum di-commit
- File: `examples/esp-radar/wifi_sensing_demo/tools/web_serial_monitor.html`;
  `reports/web_stimulus_control/20261103T145232Z/REPORT.md` (koreksi). TIDAK ada file firmware C
  yang berubah; TIDAK ada re-flash.
- Perubahan: menghapus section standalone "Traffic Stimulus (HTTP vs Ping)" dan memindahkan
  SELURUH kontrolnya (stimulusModeSelect incl. icmp_ping, burst/pause, TCP conc/int/timeout,
  stimulusBadge/stimulusStateText/refreshStimulusBtn/stimulusDetailText, stimulusTcpHint,
  applyStimulusModeBtn/toggleStimulusBtn/applyStimulusBtn) ke dalam blok collapsible
  "Advanced (manual tuning)" (`webStimAdvancedToggle` + `webStimAdvancedWrap`, default
  tersembunyi) di dalam satu panel "Wi-Fi Stimulus Control". Kunci i18n EN/ZH
  `webStimAdvancedBtn` ditambahkan; dua baris `applyLanguage` yang mereferensi id
  `stimulusPanelTitle`/`stimulusPanelDesc` (section terhapus) ikut dihapus agar tidak
  `null.textContent`. Entri changelog sebelumnya yang menyatakan "Panel lama Traffic Stimulus
  dipertahankan" menjadi tidak akurat — entri ini yang berlaku (file append-only).
- Alasan: umpan balik user — dua kotak stimulus tumpang tindih membingungkan; diminta satu kotak
  lengkap. Kontrol tuner tidak dihapus (memuat ICMP ping + tuning TCP live + dependensi JS
  `startRecorderStimulus` → `readStimulusInputs`, `renderStimulusWarn`, `applyStimulusValues`)
  sehingga semua id lama dipertahankan persis, hanya dipindah behind-the-fold.
- Dokumen: audit sebelumnya `main/web_serial_monitor.c` (sumber command/telemetri, tidak diubah);
  tidak mengubah driver/radio/protokol.
- Verifikasi:
  - Tidak ada id duplikat di seluruh file; 16 id yang dipindah masing-masing muncul tepat 1x di
    markup.
  - `node --check` JS inline (baris 880-5584) → SYNTAX_OK.
  - Suite existing lolos: csi_recorder.test.js exit 0, diag_session.test.js exit 0.
  - Server `127.0.0.1:8000` masih melayani halaman terupdate (curl HTTP 200).
  - E2 (ESP32 nyata) & E3 (Brave nyata) tetap BELUM dilakukan: tidak ada perangkat terpasang.

## 2026-11-03 — Cleanup repository + konsolidasi temuan eksperimen (host-only, tanpa perubahan runtime)

- Agent/tool: Qoder
- Branch/commit: default / TIDAK di-commit (mandat §10: jangan commit/push)
- File:
  - TAMBAH `examples/esp-radar/wifi_sensing_demo/docs/EXPERIMENT_HISTORY.md` (konsolidasi 13 §).
  - TAMBAH `reports/repository_cleanup/20261103T230000Z/{CLEANUP_REPORT.md,cleanup_inventory.csv}`.
  - PINDAH `reports/official_baseline/20261102T085330Z/p1_flash_backup/` -> top-level `p1_flash_backup/`
    (agar `reports/` bisa dibersihkan tanpa menyentuh backup P1).
  - HAPUS artefak eksperimen untracked: `reports/{csi_stimulus_benchmark,tcp_csi_optimization,
    tcp_integration_wifi_sensing_demo,console_test,csi_autonomous,official_baseline,
    official_baseline_promiscuous_on,e1,e2,p1_runtime_smoke,ap_csi_compat,web_stimulus_control}`,
    `examples/esp-radar/wifi_sensing_demo/reports/`, fork `examples/esp-radar/console_test_nulldata/` &
    `examples/get-started/csi_recv_router_promisc_on/`, `.playwright-mcp/*.png` (untracked), `hello_probe.txt`,
    `tools/__pycache__`, dan 7 dokumen `.md` eksperimen (`protocol-benchmark`, `tcp-csi-optimization`,
    `analisis-metode-ping`, `integrasi-tcp-ke-wifi_sensing`, `investigasi-wifi-sensing-demo-ping-csi`,
    `perbandingan-http-vs-ping`, `rencana-instrumentasi-ping-csi-correlation`). ±4,1 GB.
  - TIDAK mengubah source `main/`, `tools/` (kode), `sdkconfig*`, `esp-radar` (LOCKED), format CSI, FSM.
- Perubahan: mengembalikan repo ke struktur bersih; seluruh temuan eksperimen stimulus dipindahkan ke
  satu dokumen koheren; program utama + bug fix + dataset + backup dipertahankan utuh.
- Alasan: mandat `examples/esp-radar/wifi_sensing_demo/docs/cleanup.md` — setelah kampanye A-J + panel
  Web selesai, rapikan artefak, konsolidasi dokumentasi, jaga keselamatan source & data penelitian.
- INSIDEN & penanganan (transparan):
  1. `esp_wifi_sensing/` SALAH diklasifikasi sebagai duplikat stray dan terhapus -> `idf.py build` gagal
     karena `main/idf_component.yml` memakai `espressif/esp_wifi_sensing: override_path: ../esp_wifi_sensing`
     (komponen vendored dibutuhkan). Dipulihkan dari `managed_components/espressif__esp_wifi_sensing`
     (berisi instrumentasi ping yang sama); rebuild -> `wifi_sensing_demo.bin` **0xf16a0 sha `d3b3b0a7…`
     identik bit-for-bit** dengan end-state. Tidak ada regresi. Pelajaran: direktori tak jelas = REVIEW,
     jangan hapus (sudah dilanggar; kini dicatat).
  2. 2 file git-TRACKED `.playwright-mcp/console-*.log` ikut terhapus -> dipulihkan via `git checkout`;
     0 penghapusan file terkomit tersisa.
- Dokumen: `examples/esp-radar/wifi_sensing_demo/docs/cleanup.md` (mandat); `main/idf_component.yml`
  (override_path vendored esp_wifi_sensing + esp-radar); `agent-preflight.md` (esp_wifi_sensing 0.1.1~3,
  ESP-IDF v5.5.3). Tidak menyentuh driver/radio/keamanan/protokol -> build re-verifikasi membuktikan
  biner tak berubah.
- Verifikasi:
  - `idf.py build` exit 0; `wifi_sensing_demo.bin` 988832 B (0xf16a0), sha256 `d3b3b0a73eb7…ed55967`.
  - `node --check` JS inline (880-5584) SYNTAX_OK; `csi_recorder.test.js` exit 0; `diag_session.test.js`
    exit 0; `test_csi_recorder_server.py` 13 OK.
  - `esp-radar/` git-status bersih (LOCKED tak berubah); `p1_flash_backup/` sha `13e048af…` == manifest.
  - `recordings/` utuh (empty_room, walking = dataset dipertahankan; stim_*/tcp_* direview, tidak dihapus).

## 2026-11-03 — Purge seluruh recording (permintaan user; dataset akan direkam ulang)

- Agent/tool: Qoder
- Branch/commit: default / tidak di-commit
- File: `examples/esp-radar/wifi_sensing_demo/recordings/` — hapus 7 take (`empty_room`, `walking`,
  `stim_http`, `stim_off`, `stim_tcp`, `tcp_motion`, `tcp_stimulus`) + `index.csv`.
  `README.md` dan `.gitkeep` DIPERTAHANKAN (dokumen format + penjaga direktori untuk rekaman ulang).
- Perubahan: melanjutkan cleanup — recording yang pada entri sebelumnya saya pertahankan konservatif
  kini dihapus atas instruksi eksplisit user.
- Alasan: user akan mengumpulkan dataset baru dari nol; semua take merupakan artefak pra-cleanup.
- Dokumen: mandat `docs/cleanup.md` §E; `.gitignore` (file take `*.csv`/`*.meta.json` memang untracked).
  Tidak menyentuh firmware/tools/config; hanya data rekaman.
- Verifikasi: `git status --short` pada `recordings/` = kosong (tidak ada file terkomit yang hilang);
  direktori tersisa berisi `README.md` + `.gitkeep`. `recordings/README.md` & `.gitkeep` tetap.

## 2026-11-03 — Batas fase walking diubah ke pre=3 / action=4 / post=3

- Agent/tool: Qoder
- Branch/commit: default / tidak di-commit
- File: `tools/csi_recorder.js` (`TIMELINE_DEFS.walking.boundaries`),
  `tools/tests/csi_recorder.test.js` (asersi batas + offset cue `walk_begin`),
  `docs/recording-pipeline-implementation.md` (§E daftar batas fase walking).
- Perubahan: batas fase recording `walking` `[0, 2, 8, 10]` -> `[0, 3, 7, 10]`. Durasi total tetap
  10 s; pre-action (diam) 3 s, action (berjalan) 4 s, post-action (diam) 3 s. Cue audio
  `walk_begin` ikut bergeser dari offset 2 s ke 3 s. Hanya label `walking` yang berubah; fall,
  fast_sitting, bending, object_drop tidak disentuh.
- Alasan: permintaan eksplisit user ("ubah untuk walking, pre 3 detik, action 4, post 3") untuk
  keseimbangan jendela diam/aksi/ diam pada akuisisi dataset. Tidak ada perubahan perilaku
  runtime firmware (bukan driver/radio/keamanan/protokol); ini parameter anotasi recorder.
- Dokumen: `docs/recording-pipeline-implementation.md` §E — kutipan asal sebelum edit:
  "Walking: 0, 2, 8, 10 detik." (baris 1378). Dokumen spesifikasi ikut diperbarui agar tetap cocok
  dengan implementasi; penyimpangan dari nilai lama dicatat di sini.
- Verifikasi: `node tools/tests/csi_recorder.test.js` exit 0 — 99 PASS, 0 GAGAL
  (`timeline boundaries walking` dan `walking action cue at 3s` kini PASS). Teks sumber
  `csi_recorder.js:75` dan mirror test `:77` konsisten `[0, 3, 7, 10]`.

## 2026-11-03 — .gitignore: kecualikan p1_flash_backup/ dan .qoder/ sebelum commit

- Agent/tool: Qoder
- Branch/commit: default / commit pertama pasca-cleanup (belum ada hash saat entri ditulis)
- File: `.gitignore`
- Perubahan: tambah pola `p1_flash_backup/` dan `.qoder/` agar artefak lokal tidak ikut ter-commit.
  Sumber firmware `esp_wifi_sensing/` (diperlukan `override_path` di `main/idf_component.yml`),
  modul `main/{tcp,dns}_stimulus`, `csi_phy_probe`, `tools/`, `docs/EXPERIMENT_HISTORY.md`,
  `docs/cleanup.md`, dan `reports/repository_cleanup/` tetap di-commit.
- Alasan: backup flash P1 (15 MB bin/elf) dan cache IDE bukan bagian kode sumber; `.bin`/`.elf`/`sdkconfig`
  sudah di-ignore per-file tapi direktorinya belum. User meminta commit + push seluruh codebase pasca-cleanup.
- Dokumen: `docs/agent-preflight.md` (trailer `Docs:` wajib untuk commit yang menyentuh `main/`/`tools/`);
  `.githooks/commit-msg` (regex SENSITIVE + CHANGELOG). Entri perubahan besar (cleanup, walking) sudah ada
  di entri sebelumnya.
- Verifikasi: `git check-ignore` mengonfirmasi `p1_flash_backup/` dan `.qoder/` ter-ignore; hasil commit
  dicatat di pesan commit / log hook.

## 2026-11-04 — Tiga label jangkar idle: empty_room, still_standing, still_sitting

- Agent/tool: Qoder
- Branch/commit: default / belum di-commit
- File: `tools/csi_recorder.js`, `tools/web_serial_monitor.html`,
  `tools/csi_recorder_server.py`, `tools/tests/csi_recorder.test.js`,
  `fall_detection/dataset_io.py`, `docs/recording-pipeline-implementation.md`.
- Perubahan: menambah tiga label aktivitas baru dengan `kind: "idle"` — timeline satu fase
  `hold` (boundaries `[0, 10]`), binary `non_fall`, opsi pre/post dipaksa still/still, cue hanya
  start+end (tanpa cue tengah), instruksi GUI per label (IDLE_INSTRUCTION). UI menyembunyikan
  dropdown pre/post untuk kind idle (sejalan dengan walking). `buildActivityCues` kini memakai
  `b[b.length-1]` untuk offset cue akhir karena indeks tetap `b[3]` undefined pada boundaries
  2-elemen. Spec §7/§9.6/§16-E diperbarui (heading §10 sempat terserap replace, sudah dipulihkan).
- Alasan: kebutuhan akuisisi dataset pasca-purge — lantai noise per sesi, normalisasi antar-sesi,
  dan referensi "manusia ada tetapi diam" untuk logika konfirmasi stillness (diskusi analisis take
  walking 2026-11-04: energi pre 21–33% tidak bisa dinilai tanpa empty_room). Data lama label
  `empty_room` (purge 2026-11-03) sebelumnya terekam sebagai label kustom; kini jadi preset resmi.
  Pemetaan biner tetap dua nilai (fall|non_fall) agar konsumer index.csv/meta tidak berubah semantik.
- Dokumen: `docs/recording-pipeline-implementation.md` §7/§9 — kutipan sebelum edit:
  "Gunakan delapan label utama berikut"; bukan pertanyaan API ESP-IDF (perubahan host/UI saja,
  firmware tidak disentuh).
- Verifikasi: `node --check csi_recorder.js` SYNTAX_OK; JS inline HTML SYNTAX_OK;
  `csi_recorder.test.js` exit 0 — 109 PASS, 0 GAGAL (10 assertion baru: idle mapping, opsi,
  boundaries 1 fase, cue start/end only, instruksi hold); `test_csi_recorder_server.py` exit 0 (OK);
  `python3 -m unittest discover -s fall_detection/tests` exit 0 (OK). Recording yang sudah ada
  tidak berubah formatnya; label baru hanya preset tambahan (label kustom tetap didukung).

## 2026-11-04 — Perbaikan kontras dropdown gelap di Web Serial Monitor

- Agent/tool: Qoder
- Branch/commit: default / belum di-commit
- File: `examples/esp-radar/wifi_sensing_demo/tools/web_serial_monitor.html`
- Perubahan: aturan `select` memakai latar solid `var(--panel-soft)` (sebelumnya
  `rgba(255,255,255,0.04)`), ditambah aturan `option` (latar `var(--panel)`, teks
  `var(--text)`) dan `option:checked` (latar aksen, teks gelap). Berlaku untuk semua
  dropdown: Activity, Pre/Post-action, stimulus preset/mode, CSI view, subcarrier step.
- Alasan: laporan pengguna — saat dropdown Activity dibuka, daftar opsi tampil
  tulisan putih di atas latar putih sehingga tidak terbaca. Penyebab: `select`
  mengeset `color: var(--text)` (#edf2ff, nyaris putih); popup opsi native dirender
  dengan latar terang, dan `option` tanpa warna eksplisit mewarisi color tersebut.
  Latar translusen pada `select` juga membuat tampilan tertutup tidak solid.
- Dokumen: tidak ditemukan dokumen resmi yang mengatur warna popup `option` native;
  ini perilaku rendering browser (Chrome/Android menyetarakan `background` option
  terhadap color swatch). Bukti: pengamatan langsung pengguna, bukan tebakan.
- Verifikasi: perubahan hanya CSS, tidak ada perubahan perilaku recorder maupun
  JS inline (tidak ada test yang sentuh gaya). Verifikasi visual dilakukan
  pengguna di browser.

## 2026-11-04 — Fallback unduhan dilewati untuk take kosong + alasan 400 ditampilkan

- Agent/tool: Qoder
- Branch/commit: default / belum di-commit
- File: `examples/esp-radar/wifi_sensing_demo/tools/web_serial_monitor.html`,
  `examples/esp-radar/wifi_sensing_demo/tools/tests/test_csi_recorder_server.py`,
  `examples/esp-radar/wifi_sensing_demo/docs/recording-pipeline-implementation.md`.
- Perubahan: `saveTakeV3` kini (a) menyisipkan pesan error dari body respons server
  ke log (`HTTP 400: frames.csv has no data rows`, bukan `HTTP 400` saja), dan
  (b) melewati fallback unduhan ketika `frames.length === 0` — hanya log
  `recSaveFailedEmpty` dan mengembalikan `saved: "failed"`. Fallback dua file tetap
  aktif untuk take yang berisi frame. Strings baru di tabel I18N `en` dan `zh_CN`.
  Test baru `test_rejects_header_only_frames_csv` mengunci perilaku tolak-server.
  Spec §13.1 menambahkan kontrak jalur penyimpanan/fallback.
- Alasan: laporan pengguna — browser menanyakan izin unduh banyak file. Bukti:
  `~/Downloads/20261104T042249Z_walking_001.frames.csv` (352 byte, header saja,
  0 baris data) tanpa `meta.json` — pola cocok dengan satu download lolos dan satu
  diblokir. `recordings/` tidak memuat recId itu, dan validasi server menolak
  nol-frame (`csi_recorder_server.py` baris 254-255). Jadi fallback berjalan untuk
  take kosong yang tidak ada isinya, menghasilkan sampah + prompt. Pengambilan
  `result.saved` hanya satu (baris tampilan 2759), jadi nilai `"failed"` aman.
- Dokumen: `docs/recording-pipeline-implementation.md` §13 (kondisi "Tidak ada frame
  yang diterima" dan "Penulisan file gagal" harus menghasilkan status akurat) —
  sebelum edit bagian ini tidak mendokumentasikan fallback unduhan sama sekali.
  Perilaku prompt "this site is trying to download multiple files" adalah kebijakan
  izin browser (Chromium: Settings > Privacy and security > Site settings >
  Automatic downloads), terverifikasi lewat pencarian web, bukan tebakan.
- Verifikasi: `node --check csi_recorder.js` SYNTAX_OK; JS inline HTML (2 blok,
  196622 char) lolos `node --check`; `csi_recorder.test.js` exit 0 — 109 PASS,
  0 GAGAL; `python3 tests/test_csi_recorder_server.py` exit 0 — Ran 14 tests OK
  (termasuk test baru); `fall_detection/tests` Ran 66 tests OK. Server port 8000
  masih hidup (pid 25841) — probing POST tanpa label menghasilkan 400 JSON yang
  benar.

## 2026-11-04 — Gap menjadi pre-roll sebelum setiap take, termasuk take pertama

- Agent/tool: Qoder
- Branch/commit: default / belum di-commit
- File: `examples/esp-radar/wifi_sensing_demo/tools/csi_recorder.js`,
  `examples/esp-radar/wifi_sensing_demo/tools/web_serial_monitor.html`,
  `examples/esp-radar/wifi_sensing_demo/tools/tests/csi_recorder.test.js`,
  `examples/esp-radar/wifi_sensing_demo/docs/recording-pipeline-implementation.md`.
- Perubahan: fungsi baru `CsiRecorder.buildBatchSchedule({takes, gapS})` menghasilkan
  satu slot per take dengan `pre_roll_s` = gap; loop sesi memakai jadwal itu sehingga
  countdown dijalankan sebelum SETIAP take (sebelumnya `if (take > 1 && gapS > 0)`
  — take pertama mulai segera). `plan` membawa `pre_roll_s` dan disimpan sebagai
  `meta.recording.gap_before_s` (0 bila gap mati). Label UI diubah menjadi "Gap before
  each take (s)" (en) / "每次采集前的间隔（秒）" (zh_CN) plus span statis dan pesan
  `recInvalidBatch` keduanya. `waitRecorderPhase` dan display countdown dipindah dari
  `Date.now()` ke `performance.now()`. Spec: §8.1 baru, contoh node `recording` di §6.5
  menambah `gap_before_s`, §16.I daftar uji batch/gap.
- Alasan: permintaan eksplisit operator — gap harus berlaku juga untuk recording pertama.
  Secara praktis: take pertama sebelumnya mulai tepat sesudah START_CSI_STREAM, jadi
  operator belum berada di posisi (jalan dari garis start, atau keluar ruangan untuk
  `empty_room`), dan warm-up AGC perangkat ikut terekam dalam fase pre. Reset buffer
  per-take di `runTake` (baris 2775) sudah menjamin frame selama pre-roll tidak masuk
  ke take, jadi pre-roll aman ditambahkan tanpa mengubah durasi 10 detik.
- Dokumen: `docs/recording-pipeline-implementation.md` §8 — "Gunakan satu clock monotonik
  sebagai sumber waktu untuk seluruh proses: ... Countdown." dan "Semua aktivitas
  menggunakan durasi recording tepat 10 detik." Catatan: kode lama countdown memakai
  `Date.now()` (wall-clock), yang melanggar aturan ini; deviation tersebut sudah ada sebelum
  perubahan ini dan sekarang diperbaiki, bukan hanya dicatat.
- Verifikasi: `node --check csi_recorder.js` SYNTAX_OK; JS inline HTML (2 blok) lolos
  `node --check`; `csi_recorder.test.js` exit 0 — 113 PASS, 0 GAGAL (4 assertion baru:
  pre-roll semua take, single take tetap pre-roll, gap 0 tanpa pre-roll, settings tidak
  valid → null); `diag_session.test.js` exit 0 — 91 PASS, 0 GAGAL; server tests Ran 14 OK;
  `fall_detection/tests` Ran 66 OK. `validate_meta` diuji langsung dengan meta berisi
  `gap_before_s` → tanpa error (field tambahan di node `recording` aman; buildMetaV3
  memakai Object.assign sehingga menurunkan kunci tanpa whitelist). Perilaku runtime
  belum diuji di perangkat — butuh sesi recording sungguhan.

## 2026-11-06 — Fase 1A.1: gerbang LLTF terikat-flag + log diagnostik (firmware, tanpa flash)

- Agent/tool: Qoder
- Branch/commit: default / belum di-commit
- File: `examples/esp-radar/wifi_sensing_demo/main/activity_classifier.c`
- Perubahan: gerbang layout `has_supported_lltf_layout` (yang lama) diganti
  `classify_csi_layout` yang mengembalikan vonis terstruktur (valid, model_compat,
  pairs, reason). Panjang LLTF kini **terikat flag** sesuai kontrak:
  `first_word_invalid=true` hanya sah bila `valid_lltf_len==102` (51 paritas),
  `flag=false` hanya sah bila panjang cocok model (kini 104/52); kombinasi lain
  ditolak. Sum HT/STBC dihitung eksplisit (`valid_len == lltf+ht+stbc_ht`) karena
  percabangan lama memakai `valid_len == valid_lltf_len + ...` yang hanya benar
  untuk NON_HT. Layout yang ditolak (kontrak salah ATAU valid tapi lebar ≠ model)
  kini menghasilkan **log diagnostik ter-throttle** berisi panjang, flag, dan
  alasan, langsung di gerbang enqueue (bukan lagi per-frame di task konsumen).
  `activity_frame_t` menambah `lltf_pairs` + `model_compat`; `frame_to_amplitude`
  memakai `lltf_pairs` alih-alih `ACTIVITY_MODEL_SUBCARRIERS` agar decoding tidak
  terikat satu lebar; salinan `samples` dibatasi `pairs*2` byte. Log skip per-frame
  di task konsumen dihapus (diagnostik sudah di gerbang).
- Alasan: bug B1 — classifier iners terhadap frame 51-paritas karena gerbang
  lama hanya menerima panjang persis `ACTIVITY_MODEL_LLTF_BYTES` (104) dan
  tidak pernah membaca `first_word_invalid`; data perangkat nyata ber-layout A
  (102 B, flag true hasil klamp-di-sumber commit `3ac4a35`) sehingga ditolak
  diam-diam tanpa jejak. ACTION_PLAN rev 2.6 1A.1 menuntut gerbang terikat-flag
  + log diagnostik, BUKAN toleransi `X atau X-2` bebas.
- Dokumen:
  - esp-radar 0.3.4 `esp-radar/include/esp_radar.h` — "`wifi_csi_filtered_info_t`
    memuat `wifi_csi_info_t *info`; field `first_word_invalid` TIDAK ada di struct
    filtered, diakses lewat `info->info`."
  - ESP-IDF v5.5.3 `components/esp_wifi/include/local/esp_wifi_types_native.h:123`
    — "bool first_word_invalid; first four bytes of the CSI data is invalid ...
    due to hardware limitation."
  - `docs/DATA_CONTRACT.md` §1 — "Layout A 102 B/51 ⟺ true, Layout B 104 B/52 ⟺
    false; panjang↔flag terikat 1-ke-1; kombinasi lain = error eksplisit dengan
    log diagnostik (length, first_word_invalid, reason)."
- Verifikasi: `idf.py build` sukses (exit 0), `activity_classifier.c.obj`
  tercompile, `wifi_sensing_demo.bin` tergenerasi. **Tidak di-flash** sesuai
  kebijakan rev 2.6 (bukti run device digabung ke Fase V). GetProblems hanya
  menampilkan noise toolchain clangd (`-mlongcalls`, `machine/endian.h`), bukan
  error dari perubahan ini. Semantik decode 51 vs 52 dan log penolakan akan
  dibuktikan di fixture host (1A.2/1A.4) dan run device Fase V #1.

## 2026-11-06 — Fase 1A.4: lantai dinamis terikat-flag di `dataset_io` + fixture per-layout (host, tanpa flash)

- Agent/tool: Qoder
- Branch/commit: default / belum di-commit
- File: `fall_detection/dataset_io.py`, `fall_detection/tests/test_dataset_io.py`
- Perubahan: `to_feature_matrix` tidak lagi memotong ke lantai tetap
  `BASELINE_SUBCARRIERS` (52). Lebar kini **terikat flag** dan dipisahkan menjadi
  dua konsep: `frame_layout_pairs` (legalitas layout intrinsik — 102 B ⟺ flag
  true → 51 paritas, 104 B ⟺ flag false → 52, lain → 0) dan `frame_lltf_pairs`
  (kecocokan model — layout hanya dipakai bila sama dengan lebar model).
  konstanta `LLTF_PAIRS_FLAGGED=51` / `LLTF_PAIRS_UNFLAGGED=52` ditambahkan. Tiga
  kelas error baru diperkenalkan (`DatasetError`, `EmptyFeatureMatrixError`,
  `MixedLayoutError`): baris kosong → `EmptyFeatureMatrixError` (bukan hasil hening),
  dua layout sah bercampur dalam satu run → `MixedLayoutError`. Config keluaran
  kini melaporkan `subcarriers`, `model_pairs`, `layout_matches_model`,
  `frames_total`, `frames_kept`, `contract_rejects`, `distinct_layouts`. Test
  lama `FirstWordInvalidTests` (yang memakai `len(row) >= 52` salah konsep)
  diganti mixin `_LayoutFixtureMixin` plus `LayoutAFlaggedTests` (102/51/true),
  `LayoutBUnflaggedTests` (104/52/false), dan `FeatureMatrixContractTests`
  (flag/panjang tidak konsisten → ditolak; layout A/B bergantian → MixedLayoutError).
- Alasan: jalur trainer sudah menurunkan lebar dari frame (`_lltf_pair_count`),
  tetapi `dataset_io` masih memaksa 52 sehingga recording Layout A (51 paritas,
  data perangkat nyata) terpotong/dibuang diam-diam — sama seperti bug B1 di
  firmware. ACTION_PLAN rev 2.6 1A.4 menuntut lantai dinamis terikat-flag,
  0-baris = raise eksplisit, dan fixture uji per layout sah.
- Dokumen:
  - `docs/DATA_CONTRACT.md` §1 — "Layout A 102 B/51 ⟺ true, Layout B 104 B/52 ⟺
    false; panjang↔flag terikat 1-ke-1; kombinasi lain = error eksplisit."
  - esp-radar 0.3.4 `esp-radar/include/esp_radar.h` — sumber klamp `first_word_invalid`
    yang memangkas pasangan leading saat flag true (commit `3ac4a35`).
- Verifikasi: `python -m unittest` modul `test_dataset_io` → 27 OK; satu suite
  lengkap `fall_detection/tests` → 76 OK. Tidak ada perubahan firmware, tidak
  di-flash.

## 2026-11-06 — Fase 1A.2: header renderer menulis lebar terukur + assertion layout campur (host, tanpa flash)

- Agent/tool: Qoder
- Branch/commit: default / belum di-commit
- File: `fall_detection/train_activity_model.py`, `fall_detection/tests/test_train_activity_model.py`
- Perubahan: `render_c_header` kini menerima parameter wajib `subcarriers: int`
  dan menulis `ACTIVITY_MODEL_SUBCARRIERS {subcarriers}` serta
  `ACTIVITY_MODEL_LLTF_BYTES {subcarriers*2}` dari nilai terukur, bukan konstanta
  52 yang di-hardcode. Validasi `isinstance(int) and > 0` menolak lebar non-positif.
  `train_from_recordings` mengumpulkan `measured_widths: set[int]` dari setiap
  recording; bila `len(measured_widths) > 1` → `ValueError` (satu model tidak boleh
  dibangun dari dua lebar LLTF), lalu mengembalikan lebar tunggal. Panggilan `main()`
  membuka 6-tuple dan meneruskan `measured_subcarriers`. Test: pemanggilan
  `render_c_header` lama diperbarui (+`CSI_SUBCARRIERS`), dan kelas
  `HeaderRendererFixtureTests` baru menguji lewat fixture sintetis 5-kelas — lebar
  terukur 51 dan 52, `LLTF_BYTES == 2*subcarriers`, penolakan lebar non-positif,
  konsistensi dimensi bobot/urutan kelas/indeks, dan roundtrip encode↔decode.
- Alasan: renderer lama selalu menulis 52/104 tanpa mempedulikan lebar data
  training, sehingga model yang diekspor dari Layout A (51) tidak cocok dengan
  buffer firmware dan gerbang 1A.1 membuang semua frame. ACTION_PLAN rev 2.6 1A.2
  menuntut renderer menulis lebar terukur + assertion layout campur, dan pengujian
  lewat fixture sintetis (BUKAN model lama sebagai pengganti).
- Dokumen:
  - `docs/DATA_CONTRACT.md` §1 — kontrak lebar↔flag 1-ke-1; header wajib
    menyatakan lebar yang benar-benar diukur.
  - `ACTION_PLAN.md` rev 2.6 1A.2 — "header renderer menulis lebar terukur +
    assertion layout campur + uji fixture sintetis."
- Verifikasi: `python -m unittest` modul `test_train_activity_model` → 16 OK;
  satu suite lengkap `fall_detection/tests` → 76 OK; `idf.py build` ulang
  (ESP-IDF v5.5.3, esp32) → exit 0, `wifi_sensing_demo.bin` 0xf1900 (6% free).
  Tidak di-flash (kebijakan rev 2.6; run device digabung ke Fase V).

## 2026-11-06 — Shortcut Spasi menjalankan dua mark anotasi jatuh berurutan (web tool, tanpa flash)

- Agent/tool: Qoder
- Branch/commit: default / belum di-commit
- File: `examples/esp-radar/wifi_sensing_demo/tools/web_serial_monitor.html`
- Perubahan: handler `keydown` Spasi diubah dari "selalu `fall_start`" menjadi
  **menelusuri urutan dua mark**: tekan pertama → `fall_start` (mulai jatuh),
  kedua → `fall_impact` (menyentuh lantai), selanjutnya no-op bila keduanya
  sudah terisi. Ditambah helper `nextPendingAnnotation()` yang mengembalikan mark
  belum-terisi berikutnya (order tetap `fall_start` → `fall_impact`), selaras
  aturan first-press-wins `makeAnnotator`. Kondisi gerbang diperlonggar: Spasi aktif
  selama take jatuh berjalan (`phase==="recording"` + `recAnnotRow` terlihat),
  tidak lagi bergantung pada `recMarkFallStartBtn.disabled`. Status live
  (`renderAnnotStatus`) kini menampilkan petunjuk "Next (Space): <mark>" agar
  operator tahu tombol berikutnya; label tombol diberi penanda urutan + hint
  "(Spasi)". Tambahan i18n `recAnnotNext` (en "Next (Space)" / zh "下一个（空格）").
- Alasan: user ingin operator cukup menekan satu tombol saat subjek jatuh, tanpa
  membidik tombol di layar. MARK "diam" TIDAK ditambahkan ke jalur live —
  keputusan user: "diam" sudah tersedia sebagai opsi `post_action` (Still/diam,
  sudah ada di `POST_ACTION_KEYS`), jadi anotasi live tetap dua mark. Tidak ada
  perubahan `csi_recorder.js`, skema meta, maupun spec §11 karena kedua mark
  (`fall_start`/`fall_impact`) dan field meta-nya sudah ada.
- Dokumen:
  - `docs/recording-pipeline-implementation.md` §11 (annotations) —
    "`annotations.fall_start` / `fall_impact` = `{offset_s, timestamp_utc}`;
    first valid click wins; duplicates ignored."
  - `docs/DATA_CONTRACT.md` §4 — anotasi kandidat signal-derived
    (`candidate_*`, `annotation_method="csi_envelope_p95"`) terpisah dari mark
    live-observer; "Physical fall latency ... TIDAK DAPAT diverifikasi tanpa video".
  - `docs/agent-preflight.md` — path `tools/**` wajib preflight + entri changelog.
- Verifikasi: `node --check` blok `<script>` inline (baris 893–5665) → SYNTAX OK;
  `node tools/tests/csi_recorder.test.js` → exit 0 (PASS). Handler keydown Spasi
  **diverifikasi di browser nyata** (Chromium via browser-use, halaman diserve
  statis): dispatch `KeyboardEvent{code:"Space"}` ke listener sungguhan pada state
  `phase="recording"` + `recAnnotRow` terlihat + annotator fall → (1) tekan#1
  mengisi `fall_start` lalu `nextPendingAnnotation()`→`fall_impact`; (2) tekan#2
  mengisi `fall_impact`, `annotation_complete=true`, `next=null`; (3) tekan#3 =
  no-op (offset `fall_start` tak berubah); (4) klik tombol `fall_impact` tetap
  menandai jenisnya sendiri (next→`fall_start`); (5) saat `phase="idle"` Spasi
  TIDAK menandai. Teks status menampilkan "Next (Space): Fall start/Impact" sesuai
  urutan. CJK-check: hanya string terjemahan zh yang sah (`recAnnotNext`).

## 2026-11-06 — Fase 2.1/2.2: timeline fall jadi 12 s [0,4,8,12]; durasi per-take turunan boundary (web tool, tanpa flash)

- Agent/tool: Qoder
- Branch/commit: default / belum di-commit
- File: `examples/esp-radar/wifi_sensing_demo/tools/csi_recorder.js`,
  `examples/esp-radar/wifi_sensing_demo/tools/web_serial_monitor.html`,
  `examples/esp-radar/wifi_sensing_demo/tools/tests/csi_recorder.test.js`,
  `examples/esp-radar/wifi_sensing_demo/docs/recording-pipeline-implementation.md`
- Perubahan (2.1): `TIMELINE_DEFS.fall_*` boundaries `[0,4,6,10]` → `[0,4,8,12]`;
  empat label fall kini ber-take 12 s. Semua label lain tetap (walking/bending
  [0,3,7,10]; fast_sitting/object_drop [0,4,6,10]; idle [0,10]).
- Perubahan (2.2): durasi take TIDAK lagi dari konstanta global
  `TARGET_DURATION_S` (tetap 10 sebagai default non-fall). Ditambah
  `durationFromTimeline(timeline)` = `end_offset_s` boundary terakhir (fallback 10).
  `buildActivityCues` sudah boundary-driven (`lastOffset = b[last]`), jadi cue akhir
  ikut geser ke 12 tanpa perubahan. `buildMetaV3.target_duration_s` kini
  `durationFromTimeline(fields.timeline)`. Di HTML, `plan.durationS`
  (via `durationFromTimeline`) dipakai untuk: deadline loop `runTake`
  (`totalMs = plan.durationS*1000`), progress bar (`renderRecorderLive`), dan
  status timer (`renderRecorderStatus`) — keempat situs `TARGET_DURATION_S` diganti.
  Teks i18n `recDurationInfo` en/zh tak lagi menyebut "fixed 10 s". Spec
  `recording-pipeline-implementation.md` §C (target_duration_s) dan §E (Fall)
  disinkronkan. Test: boundary map fall → [0,4,8,12], assertion "spans 0..10"
  jadi generik per-label, probe `phaseAtOffset` post 7s→10s, offset cue
  [0,4,6,10]→[0,4,8,12], `target_duration_s` "fixed at 10"→"derived = 12", plus
  assertion baru `durationFromTimeline(timeline) === lastBoundary` untuk tiap label.
- Alasan: keputusan user yang mengikat (ACTION_PLAN rev 2.6 baris 4): "fall 12 s
  [0,4,8,12]; semua label lain tetap 10 s". B1/1A sudah menegakkan gerbang layout;
  2.1 adalah prasyarat timeline-driven untuk 2.3 (anotasi kandidat membaca parameter
  dari `meta.timeline`) dan 2.2 (capture-end/cue turunan boundary terakhir). Angka
  12 dan batas [0,4,8,12] bukan tebakan — dari keputusan eksplisit user + bukti
  settle 20/20 ≤ 8 s (report 07/08) yang memberi ekor 8–12 s.
- Dokumen:
  - `ACTION_PLAN.md` rev 2.6 (baris 4) — "keputusan user yang mengikat: fall 12 s
    [0,4,8,12]; semua label lain tetap 10 s; TANPA video".
  - `docs/recording-pipeline-implementation.md` §8/§9/§E — timeline & batas fase
    per aktivitas; sebelumnya menyebut "fixed 10 s" (kini dikoreksi utk fall).
  - `docs/DATA_CONTRACT.md` §4.3 — anotasi "membaca parameter sendiri dari
    `meta.timeline`" (`pre_end/action_start/action_end/take_end = timeline[i]...`);
    sudah timeline-driven, jadi tidak perlu angka 12 di kontrak.
  - Catatan: sumber driver ESP-IDF/esp-radar TIDAK relevan — perubahan ini murni
    perilaku UI/protokol rekaman host, bukan radio/driver.
- Verifikasi: `node --check tools/csi_recorder.js` OK; `node --check` blok `<script>`
  inline HTML (baris 893–5668) → SYNTAX OK; `node tools/tests/csi_recorder.test.js`
  → exit 0, **0 FAIL** (termasuk assertion durasi per-take baru);
  `python3 tools/tests/test_csi_recorder_server.py` → 14 OK. `recordingCompleteness`
  dan audit/validate tidak mengecek durasi, jadi take 12 s lolos eligibility.
  **Capture 12 s nyata di perangkat belum diuji** — butuh sesi Web Serial (Fase V);
  yang dibuktikan di host adalah logika timeline/durasi, bukan akuisisi CSI nyata.

## 2026-11-06 — Fase 2.3: tool anotasi kandidat signal-driven, timeline-driven (host tool, tanpa flash, read-only default)

- Agent/tool: Qoder
- Branch/commit: default / belum di-commit
- File: `examples/esp-radar/wifi_sensing_demo/tools/annotate_candidates.py` (baru),
  `examples/esp-radar/wifi_sensing_demo/tools/tests/test_annotate_candidates.py` (baru)
- Perubahan: Tool host standalone yang menghasilkan **anotasi kandidat** per-take
  (`candidate_onset/peak/settle`) dari envelope gerakan CSI, sebagai kanon
  algoritma + `ALGORITHM_VERSION` yang dirujuk ACTION_PLAN 2.3/2.5. Alur:
  `load_series` + `smooth_on_grid` dipindah apa adanya dari skrip kanon
  (`07_settle_times.py`, dipakai `08_label_durations.py`) — motion = `mean|Δamp|`,
  grid 20 Hz, moving-average 20 sampel (=1 s), edge di-hold. Bedanya dari skrip 07:
  **SELURUH parameter dibaca dari `meta.timeline` per kelas**, bukan konstanta
  fall (`PRE_END=4.0`, onset `t≥3.5`). `extract_timeline_params`:
  `pre_end=timeline[0].end_offset_s`, `action_start=timeline[1].start_offset_s`,
  `action_end=timeline[1].end_offset_s`, `take_end=timeline[2].end_offset_s`;
  threshold = p95 `motions[offs<pre_end]`; onset = grid pertama `t≥pre_end−0.5`
  dengan envelope>threshold; peak=argmax setelah onset; settle=titik pertama
  setelah peak yang bertahan <threshold sampai akhir. Timeline 1-fase (idle/hold)
  → `kind=hold`, laporkan stabilitas (Spearman rho + rasio late/early p95), BUKAN
  onset. **Timeline hilang/kosong/jumlah fase tak sah/boundary non-numerik →
  `TimelineError` → failed-fast**, TIDAK ada fallback diam-diam ke 4.0. Kandidat
  dengan `onset<action_start` → `pre_action_candidate=true` + `needs_manual_review`
  (kontrak §4.4); tak ada crossing / tak settle / tak ada frame pre → `needs_manual_review`.
  `annotation_status` yang dihasilkan tool SELALU `auto_pending` (promosi
  `signal_reviewed`/`manual_corrected` = hak panel review manusia, bukan tool).
  Output = blok turunan `candidate_annotation` (field persis §4.2: method,
  algorithm_version, parameters, status, `candidate_*_s`, `needs_manual_review`,
  `pre_action_candidate`, `timeline_parameters`, threshold, notes) yang **tidak
  pernah menimpa data mentah maupun `annotations` observer**. Default **read-only
  (preview)**; `--write` (mutasi dataset) dan `--plot` (PNG kurva) opsional;
  `--strict` exit≠0 bila ada failed-fast.
- Alasan: ACTION_PLAN 2.3 menuntut wujud tool kanon (bukan reimplementasi di panel
  review) dengan metode skrip 08 (timeline-driven), BUKAN skrip 07 (fall-hardcoded).
  Putaran-2 review #2 mengoreksi fakta: skrip 08 sudah timeline-driven; yang nyata
  dibutuhkan = fallback `4.0` → failed-fast + flag `pre_action_candidate` +
  parameter terdokumentasi. Review grafik memvalidasi BENTUK sinyal, bukan waktu
  fisik (keputusan tanpa video → level `independently_verified` tidak ada).
- Dokumen:
  - `docs/DATA_CONTRACT.md` §4.2/§4.3/§4.4 — "field `annotation_method=
    csi_envelope_p95`, `annotation_algorithm_version`, `annotation_parameters
    {grid_hz:20, smooth_n:20, search_offset:-0.5}`, `candidate_onset/peak/settle_s`,
    `needs_manual_review`"; "`pre_end=timeline[0].end_offset_s; action_start=
    timeline[1].start_offset_s; action_end=timeline[1].end_offset_s; take_end=
    timeline[2].end_offset_s`"; "**Meta tanpa timeline → failed-fast, bukan
    fallback ke 4.0**"; "`candidate_onset_s < action_start` → `pre_action_candidate
    = true` ... TIDAK otomatis dianggap onset ... wajib review".
  - `ACTION_PLAN.md` rev 2.6 2.3 — "kanon = metode skrip 08 yang timeline-driven,
    BUKAN skrip 07 yang fall-hardcoded ... `tools/annotate_candidates.py` (kanon
    algoritma + `ALGORITHM_VERSION` dipelihara di sana)".
  - `fall_detection/dataset_io.py` (repo) `decode_iq`/`amplitude` — decoder yang
    dipakai `load_series`, sama seperti skrip 07.
  - Catatan: sumber driver ESP-IDF/esp-radar TIDAK relevan — tool host murni di atas
    CSV rekaman, tidak menyentuh radio/firmware.
- Verifikasi: `python -m py_compile` tool → OK; unit test baru
  `tools/tests/test_annotate_candidates.py` → **13 OK** (failed-fast missing/
  empty/2-fase/non-numerik timeline; onset bersih >action_start; kandidat
  pra-aksi ter-flag; no-crossing & never-settled → needs_review; hold→stability;
  identity fields §4.2). Suite regressi: `fall_detection/tests` → **76 OK**;
  `tools/tests` python → **27 OK**. **Preview read-only di data nyata** (89 take,
  tanpa `--write`): fall_forward onset 4,35–5,2 s & settle 5,95–7,25 s (selaras
  report 07 median ≤8 s); walking **6/10 onset + 4 None** (persis crossing 6/10
  yang dilaporkan skrip 08); idle `kind=hold` tanpa kandidat. JSON blok terbit
  cocok field §4.2. **Belum ada penulisan metadata** — backfill dataset (2.5)
  adalah mandat terpisah yang menyentuh data dan butuh persetujuan eksplisit user.

## 2026-11-06 — Fase 2.4: karakterisasi lintas kelas segmentasi kandidat (host tool, read-only, tanpa flash)

- Agent/tool: Qoder
- Branch/commit: default / belum di-commit
- File: `examples/esp-radar/wifi_sensing_demo/tools/annotate_candidates.py`
  (tambah `characterize()` + flag `--characterize`),
  `reports/fall_detection_research/20261104T180944Z/candidate_characterization.json` (baru, artefak)
- Perubahan: Menambah mode agregasi **read-only** di tool kanon 2.3 — merangkum
  output anotasi kandidat per label aktivitas (BUKAN reimplementasi; hanya
  konsumen hasil `compute_candidate`). Metrik per kelas action: jumlah kandidat
  terbit vs no-onset, `needs_manual_review`, jumlah `pre_action_candidate`,
  median/rentang onset, **deviasi onset terhadap `action_start` milik kelas itu
  sendiri** (bukan angka tetap), median/max settle, median/min tail. Kelas hold
  (idle): median Spearman rho + rasio late/early p95. Artefak JSON disimpan di
  folder snapshot riset (bukan dataset). Tidak ada perubahan jalur anotasi per-take.
- Alasan: ACTION_PLAN 2.4 meminta "karakterisasi segmentasi kandidat gerakan CSI
  lintas kelas aktivitas" (bukan "uji spesifisitas deteksi jatuh") dengan
  **parameter per aktivitas sesuai timeline masing-masing**, mencakup (i) jumlah
  kandidat per kelas, (ii) deviasi onset vs batas fase protokol per kelas,
  (iii) dampak tumpang tindih 0,5 s baseline. Membuatnya sebagai mode di tool
  kanon menjaga satu sumber kebenaran algoritma + reproduksibel, sesuai 2.3
  ("kanon algoritma dipelihara di sana").
- Dokumen:
  - `ACTION_PLAN.md` rev 2.6 2.4 — "Karakterisasi segmentasi kandidat gerakan CSI
    lintas kelas aktivitas ... Dengan parameter per aktivitas sesuai timeline
    masing-masing, bukan parameter fall universal ... (iii) dampak tumpang tindih
    0,5 s baseline".
  - `docs/DATA_CONTRACT.md` §10 — "istilah untuk §2.4: karakterisasi segmentasi
    kandidat gerakan CSI lintas kelas aktivitas — bukan uji spesifisitas".
  - `reports/fall_detection_research/20261104T180944Z/label_durations.json` —
    angka awal skrip 08 (crossing p95 fall 20/20, walking 6/10, sisanya 1–2/10,
    idle ≈ 0) yang jadi pembanding.
- Verifikasi: `py_compile` OK; `test_annotate_candidates.py` tetap **13 OK**
  (perubahan hanya menambah fungsi agregasi, tidak menyentuh jalur anotasi).
  Jalan penuh `--characterize` atas **89 take (0 failed-fast)**, hasil disimpan di
  `candidate_characterization.json`. Angka terukur mereproduksi dasar laporan 08
  **persis**: fall_forward kandidat **10/10** (onset median 4,875 s, settle median
  6,3 s / maks 7,25 s; tail min 2,75 s), fall_backward **10/10** (settle median
  7,525 s / maks 7,9 s) → **20/20 ≤ 8 s**; walking **6/10** onset; bending **1/10**,
  fast_sitting **2/10**, object_drop **2/10**; idle (empty_room/still_sitting/
  still_standing) semua `hold`, **0 kandidat**, late/early p95 ≈ 1,0. Temuan
  penting 2.4(iii): **`pre_action_candidate` = 0 di SEMUA kelas** dan
  `onset_minus_action_start` selalu positif (fall 0,875–1,275 s) → tumpang tindih
  window pencarian `pre_end−0,5` ke baseline **tidak** menyeret kandidat ke
  wilayah pra-aksi pada data ini (dampak empiris nol). Catatan jujur: take fall di
  dataset ini masih memakai protokol lama [0,4,6,10] (action_start=4), jadi
  karakterisasi ini memvalidasi metode pada data yang ada — distribusi onset
  protokol baru 12 s menunggu pilot 4.1 (soft check, bukan gate), dan emisi
  kandidat rendah pada bending/fast_sitting/object_drop adalah **sifat metode**,
  BUKAN kegagalan (gerakan kelas itu memang tak menembus p95 baseline-nya sendiri).

## 2026-11-06 — Fase 2.7: keputusan protokol audio cue (rekaman keputusan, tanpa kode baru)

- Agent/tool: Qoder
- Branch/commit: default / belum di-commit
- File: tidak ada perubahan kode — ini entri keputusan. Field yang relevan sudah
  ada di `csi_recorder.js` (`buildMetaV3.audio_cues`: `enabled`, `mode`,
  `language`, `events[]`) dan `buildActivityCues()` sudah mencatat status playback
  per cue ke `meta.audio_cues.events`.
- Perubahan: menetapkan **satu protokol audio cue yang bisa diikuti** sebagai
  resmi, dengan **mode dicatat per take** di metadata. `mode` default
  `voice_and_tone` (bahasa `id-ID`); operator dapat memilih visual-only sebagai
  opsi murah, tetapi pilihan itu **wajib tercatat** agar konsistensi antar take
  dapat diaudit, bukan diasumsikan seragam.
- Alasan: review eksternal §2 + temuan C3 (89/89 take berdeviasi dari jadwal cue).
  Yang penting bukan akurasi cue — onset kandidat CSI (2.3) toh tidak bergantung
  pada cue akurat — melainkan **konsistensi + pencatatan** supaya deviasi dapat
  direkonstruksi pasca-hoc. Karena mekanisme pencatatan per-take (`audio_cues.mode`
  + `.events`) sudah ada, 2.7 menjadi rekaman keputusan, bukan perubahan perilaku.
- Dokumen:
  - `ACTION_PLAN.md` rev 2.6 2.7 — "Audio cue: tetapkan SATU protokol yang bisa
    diikuti dan catat mode per take (visual-only resmi = opsi murah; onset
    kandidat toh tidak butuh cue akurat)" (dasar: "C3 89/89 deviasi; review §2:
    yang penting konsistensi + pencatatan").
  - `csi_recorder.js` `buildMetaV3`/`buildActivityCues` — field `audio_cues`
    `{enabled, mode, language, events}` sudah menyimpan mode & status per cue.
  - Catatan: dokumentasi driver ESP-IDF/esp-radar TIDAK relevan — ini keputusan
    protokol operasi host/GUI, bukan perilaku radio.
- Verifikasi: konfirmasi kode bahwa `meta.audio_cues.mode` terisi per take (grep
  `audio_cues` di `csi_recorder.js`: blok default + dokumentasi `events`); tidak
  ada perubahan runtime sehingga tidak ada build/flash baru. Suite regressi tetap
  hijau (lihat entri 2.8).

## 2026-11-06 — Fase 2.8: identitas batch/sesi, penomoran take monoton, jejak abort (host tool, tanpa flash)

- Agent/tool: Qoder
- Branch/commit: default / belum di-commit
- File: `examples/esp-radar/wifi_sensing_demo/tools/csi_recorder.js`
  (`makeBatchId`/`makeSessionId`/`parseTakeNumber`/`nextTakeNumber` +
  `buildBatchSchedule({startTake})` + `buildMetaV3` menaikkan
  `session_id`/`batch_id`/`batch`/`abort` ke top-level + ekspor baru),
  `tools/web_serial_monitor.html` (state `sessionId`/`batchAborts`, helper
  `resolveRecorderSessionId`/`computeNextTakeNumber`/`rememberTakeNumber`, loop
  batch `break`→`continue`+trace, input Session ID, i18n en/zh),
  `tools/csi_recorder_server.py` (`validate_meta`: `target_duration_s` dilonggarkan
  dari `not in (None, 10)` menjadi "angka positif atau null"),
  `tools/tests/csi_recorder.test.js` (+14 assert), `tools/tests/test_csi_recorder_server.py`
  (+2 test), `docs/recording-pipeline-implementation.md` (§6.2 koreksi session_id,
  §8 durasi per-take, §8.1 jejak abort, §8.2 baru, rujukan silang §8.1→§8.2).
- Perubahan:
  1. **`batch_id` wajib & otomatis per run** (`batch_<utcStamp>_<nonce6>`),
     disimpan top-level + `meta.batch.batch_id`, bahkan untuk satu take.
  2. **`session_id` kepunyaan operator** (input GUI, di-generate & dipersist via
     `localStorage` bila kosong) — jelas **berbeda** dari `batch_id`, disimpan
     top-level sehingga dibaca `dataset_io.Recording.session_id`.
  3. **Nomor take monoton lintas-restart**: `startTake = max(nomor di library untuk
     label itu, penghitung localStorage) + 1`; `buildBatchSchedule` menerima
     `startTake` sehingga suffix `_NNN` tak mengulang nomor lama.
  4. **Jejak abort**: cancel/`take_begin` ditolak → `continue` (bukan `break`) +
     push ke `batchAborts`, ditulis ke `meta.abort.aborted_slots` pada take sisa.
  5. **Perbaikan bug laten**: server menolak `target_duration_s != 10`, padahal
     durasi kini diturunkan dari timeline (fall = 12 s) → take fall 12 s akan
     ditolak saat POST.
- Alasan: review §2 eksternal & ACTION_PLAN 2.8 menuntut batch≠session (jangan
  pakai batch sebagai proksi sesi) + penomoran monoton + jejak abort. Bug durasi
  dan celah sesi ditemukan dengan **membaca kode**, bukan menebak:
  `dataset_io.Recording.session_id` membaca `meta.session_id`/`meta.batch_id` di
  TOP-LEVEL yang tak pernah diisi (validator selalu warn), dan `validate_meta`
  hardcoded `!= 10` bertentangan dengan `durationFromTimeline` dari 2.1/2.2.
- Dokumen:
  - `ACTION_PLAN.md` rev 2.6 2.8 — "Penomoran take monoton lintas-restart,
    `batch_id` wajib, jejak take abort; **`batch_id` ≠ `session_id`** — sesi
    independen didefinisikan terpisah (beda hari/posisi/subjek), jangan pakai
    batch sebagai proksi sesi."
  - `fall_detection/dataset_io.py` — properti `Recording.session_id` membaca
    `meta.get("session_id") or meta.get("batch_id")` (top-level).
  - Catatan: sumber driver ESP-IDF/esp-radar TIDAK relevan — perubahan murni
    bookkeeping recording di host/GUI + validasi server penyimpanan, tidak
    menyentuh radio/firmware.
- Verifikasi: `csi_recorder.test.js` **semua lulus** (100+ assert, termasuk 14
  baru 2.8: startTake offset [7,8,9], default 1, parseTakeNumber, nextTakeNumber
  per-label/unseen/string polos, batchId≠sessionId, meta mengekspos
  session_id+batch_id top-level, batch untuk single-take, abort terisi/null);
  inline `<script>` HTML lolos cek sintaks; `test_csi_recorder_server.py` **16
  lulus** (termasuk `test_accepts_12s_fall_take` membuktikan bug 12 s teratasi &
  `test_rejects_nonpositive_target_duration` membuktikan 0/"ten" ditolak);
  `test_annotate_candidates.py` tetap **13 lulus**; `fall_detection/tests` **76
  lulus**. Belum flash ke perangkat (no-flash policy host-side); smoke test
  browser atas wiring input sesi + penomoran take menyusul (item g).

## 2026-11-07 — Fase 2.8 lanjutan: `subject_id` dipulihkan + default "1" bila kosong (host tool, tanpa flash)

- Agent/tool: Qoder
- Branch/commit: default / belum di-commit
- File: `examples/esp-radar/wifi_sensing_demo/tools/csi_recorder.js`
  (`DEFAULT_SUBJECT_ID` + `normalizeSubjectId()` + `subject_id` di `buildMetaV3`
  top-level + ekspor baru),
  `tools/web_serial_monitor.html` (state `subjectId`, input "Subject ID" +
  `resolveRecorderSubjectId()` dengan persist `localStorage`, pemanggilan di
  batch-start, field `subject_id` ke `buildMetaV3`, i18n en/zh, render label,
  teks fallback `recDurationInfo` diluruskan),
  `tools/tests/csi_recorder.test.js` (+4 assert),
  `docs/recording-pipeline-implementation.md` (§6.2 `subject_id` keluar dari
  daftar hapus + koreksi, §8.3 baru).
- Perubahan: `subject_id` kini **selalu terisi pada rekaman baru**. GUI punya
  input terpisah di samping Session ID; bila operator **membiarkannya kosong**,
  nilainya menjadi string `"1"` (subjek tunggal), **bukan `null`**. Nilai
  eksplisit dipangkas spasi tepinya dan dipertahankan di `localStorage`
  (`csiRecorder.subjectId`) lintas reload; saat kosong, default efektif tampil
  sebagai *placeholder* sehingga kolom tetap jujur kosong sementara take tetap
  mendapat `"1"`. Rekaman lama tanpa field ini tetap sah (`dataset_io`
  mengembalikan `None`, tidak ditafsirkan ulang sebagai subjek `"1"`).
- Alasan: user memutuskan "jika subject id di web kosong, masukkan nomor 1 saja".
  Konflik dokumen ditemukan **dengan membaca, bukan menebak**: spec §6.2
  memasukkan `subject_id` ke daftar "Field yang harus dihilangkan", padahal
  ACTION_PLAN 4.2 mewajibkan `subject_id` terisi (≥2 subjek × ≥2 sesi) dan 3.3
  menunda klaim subject-independent sampai field itu ada. Bukti lapangan:
  take uji `20261107T100345Z_fall_left_004` tidak punya key `subject_id` sama
  sekali — `buildMetaV3` tidak pernah memancarnya; satu-satunya penyebutan
  `subject_id` di `csi_recorder.js` ada di **`buildMetaV2`** (skema legacy), dan
  tidak ada input web untuk itu, sehingga nilainya selalu `null`. Tanpa field
  ini, split per-subjek di Fase 3.3 dan E6 di Fase 4 tidak dapat dijalankan.
- Dokumen:
  - `fall_detection/dataset_io.py` (repo) — `def subject_id(self) -> str | None:
    return self.meta.get("subject_id")` (alasan nilai disimpan sebagai string).
  - `ACTION_PLAN.md` rev 2.6 4.2 / 3.3 — "`subject_id` terisi"; "klaim
    subject/session-independent menunggu E6 dengan `subject_id` terisi dan split
    per-subjek".
  - `docs/recording-pipeline-implementation.md` §6.2 — teks lama "Field yang
    harus dihilangkan … `subject_id`" yang kini dikoreksi (konflik, bukan
    fakta final).
  - Catatan: dokumentasi driver ESP-IDF v5.5.3 / esp-radar 0.3.4 **tidak
    ditemukan dan tidak relevan** — ini field metadata host/GUI, tidak
    menyentuh radio, firmware, atau protokol payload.
- Verifikasi: `node tests/csi_recorder.test.js` → **rc=0**, termasuk 4 assert
  baru (default blank/null/whitespace → `"1"`; trim & lestarikan nilai eksplisit
  sebagai string; `buildMetaV3` kosong → `subject_id==="1"`; nilai operator
  `" 2 "` → `"2"`). Inline `<script>` HTML lolos `node --check`; suite python
  `tools/tests` → **29 lulus**; `fall_detection/tests` → **76 lulus**.
  Cek artefak CJK pada wilayah spec + changelog baru: bersih (entri kamus i18n
  zh `受试者 ID` memang Chinese, bukan artefak). Tidak ada flash perangkat.

## 2026-11-08 — Rename taksonomi manner-fall: `fall_left`→`fall_lemas`, `fall_right`→`fall_keseleo` (host tool, tanpa flash)

- Agent/tool: Qoder
- Branch/commit: default / belum di-commit
- File: `examples/esp-radar/wifi_sensing_demo/tools/csi_recorder.js`
  (`ACTIVITY_LABELS`, `BINARY_LABELS`, `TIMELINE_DEFS`, `PHASE_IDS`; `FALL_DIRECTIONS`
  → `FALL_ACTION_CUES` berupa frasa lengkap; dua call-site cue `phaseInstruction`
  + `buildActivityCues`; ekspor), `tools/csi_recorder_server.py` (`BINARY_LABELS`),
  `fall_detection/dataset_io.py` (`BINARY_LABELS`),
  `tools/tests/csi_recorder.test.js` (assert label + boundary + cue manner baru),
  `docs/DATA_CONTRACT.md` (§9 tabel + §9.1 baru arah-vs-manner + catatan onset),
  `examples/esp-radar/wifi_sensing_demo/docs/recording-pipeline-implementation.md`
  (tabel label, daftar uji, §9.1 arah→manner, koreksi timeline 10s→12s, contoh
  cue), `tools/annotate_candidates.py` (tidak berubah — kanon tetap), dan
  **migrasi dataset**: `recordings/fall_left/`→`fall_lemas/` (10 take),
  `recordings/fall_right/`→`fall_keseleo/` (11 take), `activity_label` ditulis
  ulang di 21 `*.meta.json` sementara `recording_id`/nama file DIPERTAHANKAN.
- Perubahan: Dua kelas jatuh berbasis arah (`fall_left`/`fall_right`) diganti
  menjadi kelas berbasis **cara**: `fall_lemas` (collapse lunglai, **pre-action
  diam** — sama seperti forward/backward) dan `fall_keseleo` (collapse lateral
  terkontrol, pre-action berjalan + post-action bergerak perlahan).
  `FALL_ACTION_CUES` kini memetakan tiap label ke frasa cue
  penuh ("Jatuh lemas sekarang!" / "Jatuh keseleo sekarang!") alih-alih
  menyisipkan kata arah ke template `Jatuh ke {arah} sekarang!`. Onset untuk
  manner-fall dengan pre-action berjalan ditetapkan **berasal dari mark observer
  (`annotations.fall_start`, level `manual_corrected`)**, bukan p95 auto.
- Alasan: user merekam 41 take (2026-11-07) dan meminta rename + analisis.
  Analisis atas 4 kelas: gerbang teknis 4.1 LULUS semua; `subject_id` terisi
  (lemas=`'2'`, sisanya `'1'`). Temuan utama — **`fall_right` 0/11 kandidat**
  karena ambang kanon `p95(motion[pre_action])` (§4.3) terangkat oleh pre-action
  **berjalan** di atas puncak gerak jatuh yang halus (`peak/baseline ≈ 0,56`; vs
  lemas-diam `≈ 1,1`). Riset menunjukkan menurunkan persentil ke p50 adalah
  jebakan: onset melompat ke tepi window (`pre_end−0,5`, 3,5 s) →
  `pre_action_candidate` menyala 7–9/10, yaitu **deteksi palsu**. Verifikasi mark
  spasi: `fall_start` mendahului rise p95 ~0,2–0,6 s dan motion pasca-`fall_impact`
  runtuh ke ~⅔ level jatuh → mark observer memotret fisik, sah jadi onset primer.
  Rekomendasi user: rename kunci folder penuh; pengolahan baseline: riset dulu.
- Dokumen:
  - `docs/DATA_CONTRACT.md` §4.3 — "Threshold = p95 dari `motion[offs < pre_end]`"
    (asumsi pre-action diam; sumber kegagalan manner-fall berjalan).
  - `docs/DATA_CONTRACT.md` §4.1 — tangga `auto_pending → signal_reviewed →
    manual_corrected`; `independently_verified` TIDAK ADA (tanpa video).
  - `fall_detection/dataset_io.py:598` — `label = str(meta.get("activity_label")
    or meta.get("label") or folder.name)` → `activity_label` otoritatif, folder
    hanya fallback; `recording_id` identitas terpisah → migrasi aman.
  - Catatan: dokumentasi ESP-IDF v5.5.3 / esp-radar 0.3.4 **tidak relevan** —
    ini taksonomi label + metadata host, tidak menyentuh radio/firmware/protokol.
- Verifikasi: `node tests/csi_recorder.test.js` → rc=0 (assert label 11, boundary
  `[0,4,8,12]` utk lemas/keseleo, cue manner baru); `tools/tests` python lulus;
  `fall_detection/tests` lulus. `git grep fall_left|fall_right` pada kode →
  nol (hanya tersisa di entri changelog historis). Dataset: 21 meta terverifikasi
  `activity_label` baru + `recording_id` tak berubah; `annotate_candidates.py`
  membaca folder baru tanpa failed-fast. Belum flash; belum ada `--write` ke
  dataset anotasi (2.5 tetap mandat terpisah).
- Klarifikasi (user, 2026-11-08): `fall_lemas` **memang pre-action diam**, jadi
  10 take lemas yang sudah ada sudah benar (7/10 onset p95 valid) — TIDAK perlu
  rekam ulang. Hanya `fall_keseleo` yang pre-action berjalan. Untuk pertanyaan
  "bagaimana agar jatuh-dari-berjalan terdeteksi": diukur pada 11 take keseleo —
  p95 (0/11) dan change-point level (k=2: 3/11, meleset s.d. +2,9 s; k=3: 0/11)
  keduanya gagal karena puncak jatuh (<5,4) berada di bawah pita berjalan
  (p95 ~6–8). Diskriminator yang bekerja = **settling ke diam pasca-puncak
  (11/11)**, yaitu ciri bentuk dua-tahap `fall_transition`→`fallen_still` (§6/§7),
  wilayah Fase 3/5 (model + state machine), bukan alat anotasi. Onset waktu
  keseleo tetap memakai mark observer `fall_start`. DATA_CONTRACT §9.1 +
  recording-pipeline-implementation §9.1 + test cue diluruskan (lemas=diam).

## 2026-11-08 — Uji kelayakan dua-domain "berjalan biasa" vs "jatuh dari berjalan" (probe host, read-only, tanpa flash)

- Agent/tool: Qoder
- Branch/commit: default / belum di-commit
- File: `examples/esp-radar/wifi_sensing_demo/tools/probe_keseleo_separability.py`
  (baru; konsumen `annotate_candidates.load_series`/`smooth_on_grid`, tidak
  mengubah dataset maupun jalur anotasi per-take).
- Perubahan: Probe read-only yang memisahkan dua domain — `fall_keseleo`
  (11 take, berjalan→tersandung→jatuh) vs `walking` (10 take, berjalan biasa)
  — memakai ciri **bentuk + settle** pada envelope gerak kanon, SELURUHNYA
  dibatasi di dalam action window (0–4/4–8 utk keseleo; 3–7 utk walking) agar
  berhenti-protokol tidak disalahartikan sebagai jatuh. Ciri: `drop_ratio`
  (penurunan pasca-puncak), `still_confirm` (minimum pasca-puncak ÷ floor diam
  pre-action), `peak_pos_frac`, dan komposit `fall_shape`. Melapor AUC
  Mann-Whitney + tabel TP/FP pada ambang eksplisit.
- Alasan: user menanyakan apakah "jatuh dari berjalan" (kasus riil) bisa
  terdeteksi meski onset-nya tak terambil ambang level (terukur sebelumnya: p95 0/11,
  change-point k=2 3/11 meleset s.d. +2,9 s, k=3 0/11 — puncak jatuh < pita
  berjalan). Hipotesis: yang memisahkan bukan level, tapi bentuk dua-tahap
  (naik-tajam → settle ke diam) ala `fall_transition`→`fallen_still` §6/§7.
  Hasil terukur mengonfirmasi: `still_confirm` AUC 0,99 (keseleo 0,61–1,00 =
  kembali ke diam; walking 0,97–1,50 = tidak pernah diam di tengah window),
  `fall_shape` AUC 0,89. Aturan `fall_shape>0,18 AND still_confirm<1,0` =
  **9/11 keseleo terdeteksi, 0/10 walking false-alarm**. Kesimpulan: LAYAK
  secara prinsip; onset waktu tetap butuh mark observer (fallback level gagal).
- Dokumen:
  - `docs/DATA_CONTRACT.md` §6/§7 — dua tahap `fall_transition`→`fallen_still`;
    statistik baseline `mean(log1p(amplitude))` per band (fitur relatif, bukan
    ambang level global). §9.1 — hanya keseleo yang pre-action berjalan.
  - `annotate_candidates.py` (kanon motion envelope, dipakai ulang probe).
  - Catatan: ESP-IDF v5.5.3 / esp-radar 0.3.4 **tidak relevan** — analisis host
    murni di atas CSV rekaman, tidak menyentuh radio/firmware.
- Batasan jujur (dinyatakan di jawaban): n kecil (11 vs 10), 2 subjek
  (keseleo='1', walking='1'), satu ruang; ambang dipilih pada data yang sama
  (belum LOO/cross-validated); `fall_shape` = proxy envelope 1-ciri, BUKAN fitur
  16-band kanon model. Ini bukti **kelayakan**, bukan akurasi siap-deploy.
- Verifikasi: `py_compile` OK; `python probe_keseleo_separability.py` → AUC
  (`fall_shape`=0,89, `still_confirm`=0,01 arah terbalik) + tabel threshold
  direproduksi stabil. Tidak ada mutasi dataset; tidak ada flash; `--write` tidak
  pernah disentuh.
