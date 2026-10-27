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
