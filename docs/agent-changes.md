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
