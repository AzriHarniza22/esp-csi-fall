# CLEANUP REPORT — Repository Cleanup & Experimental Artifact Consolidation

Mandat: `examples/esp-radar/wifi_sensing_demo/docs/cleanup.md`.
Eksekusi: 2026-11-03 (UTC). Agent/tool: Qoder. Branch: `default` (tidak ada commit — sesuai §10).
Purposes: **cleanup repository**, bukan optimasi/eksperimen baru.

## Ringkasan satu baris

Seluruh artefak eksperimen stimulus CSI (laporan mentah, fork harness, build, log) dibersihkan;
temuannya dikonsolidasikan ke satu dokumentasi; program utama (firmware + Web Serial Monitor +
recorder) **tidak tersentuh** dan tervalidasi rebuild bit-identik. Repo turun dari **≈5,2 GB → 1,1 GB**.

## 1. Kondisi repository sebelum cleanup

Area tak-terlacak (untracked) yang menjadi target:

| Area | Ukuran | Isi |
|---|---:|---|
| `reports/**` (12 subdireks) | 674 MB | laporan eksperimen, log capture, CSV, grafik, salinan build |
| `examples/esp-radar/wifi_sensing_demo/reports/**` | 208 MB | eksperimen_A, prioritas1_smoke, stimulus_comparison |
| `examples/get-started/csi_recv_router_promisc_on/` | 3,1 GB | fork harness (baseline + TCP campaign) + build |
| `examples/esp-radar/console_test_nulldata/` | 158 MB | fork harness null-data |
| `examples/esp-radar/wifi_sensing_demo/esp_wifi_sensing/` | 340 KB | komponen vendored (SALAH klasifikasi awal — lihat §10) |
| `.playwright-mcp/` | 472 KB | screenshot UI + log konsol (2 di antaranya git-tracked) |
| `hello_probe.txt` | 24 KB | output probe debug |
| Dokumen `.md` eksperimen (7) | ~260 KB | rencana/audit/hasil kampanye |

## 2–6. Angka hasil (definisi granularitas: per-unit pada `cleanup_inventory.csv`)

- **Unit diaudit:** 40 entri (lihat `cleanup_inventory.csv`) — mencakup direktori besar, tiap
  subdireksi `reports/*`, tiap fork, tiap dokumen eksperimen, tiap area terlindungi.
- **Unit dipertahankan (KEEP):** 14 (CORE program utama, dataset, backup, dokumen esensial,
  konsolidasi). **+1 RESTORED** (`esp_wifi_sensing`, lihat §10).
- **Unit dihapus (DELETE):** 18 direktori/file eksperimen (≈4,1 GB).
- **Recording dihapus:** **0** — seluruh `recordings/` dipertahankan (lihat §8 & §11; keputusan
  konservatif karena dataset & file ignore lokal saling bercampur dan manfaatnya hanya ~6 MB).
- **Dokumentasi dikonsolidasi:** 12 laporan `.md` + 7 dokumen `.md` eksperimen → **1** file
  `examples/esp-radar/wifi_sensing_demo/docs/EXPERIMENT_HISTORY.md` (13 §).

## 7. File utama yang dipertahankan (CORE — tak tersentuh oleh cleanup)

- `examples/esp-radar/wifi_sensing_demo/main/*.c/.h` — semua modul firmware, termasuk
  `ht_stimulus`, `tcp_stimulus`, `dns_stimulus`, `csi_phy_probe`, `web_serial_monitor` (di CMakeLists SRCS).
- `examples/esp-radar/wifi_sensing_demo/tools/` — `web_serial_monitor.html` (panel stimulus tunggal),
  `csi_recorder.js`, `csi_recorder_server.py`, `tests/`.
- `examples/esp-radar/wifi_sensing_demo/esp-radar/` (vendored, **git-tracked, LOCKED — status bersih, tak berubah**).
- `examples/esp-radar/wifi_sensing_demo/esp_wifi_sensing/` (vendored, dipulihkan — §10).
- `managed_components/espressif__esp_wifi_sensing` + komponen lain.
- `p1_flash_backup/` (dipindah dari dalam `reports/official_baseline/` ke top-level agar
  `reports/` dapat dibersihkan **tanpa** menyentuh backup — §12.4).
- `recordings/` penuh (`empty_room`, `walking` = dataset; `stim_*`, `tcp_*` = lihat §11).

## 8. Perbaikan program yang dipertahankan (bug fix — §2)

Tetap di source, diverifikasi lewat build + test: perbaikan profil ping (`profile 5`), TCP stop/start
race, `first_word_invalid` (clamp sumber), throttle emisi/`SET_CSI_PERIOD`, sinkron serial/diag_queue,
parser HMSCMD + ACK (panel Web). Ringkas lengkap di `EXPERIMENT_HISTORY.md` §9.

## 9. Hasil build & test (verifikasi pasca-cleanup)

- **Firmware:** `idf.py build` (ESP-IDF v5.5.3) → **exit 0**. `wifi_sensing_demo.bin`
  **0xf16a0 = 988832 B, sha256 `d3b3b0a73eb7…ed55967`** — **identik bit-for-bit** dengan end-state
  kampanye. Build deterministik; 0 error.
- **Web Serial Monitor:** `node --check` JS inline (baris 880–5584) → **SYNTAX_OK**. Selector
  stimulus tetap 4 preset + blok Advanced (kondisi terkini dipertahankan, §G2).
- **Tests:** `csi_recorder.test.js` exit 0; `diag_session.test.js` exit 0;
  `test_csi_recorder_server.py` **13 OK**.
- **esp-radar LOCKED:** `git status` pada `esp-radar/` = bersih (tak berubah).

## 10. Masalah yang ditemukan & ditangani (jujur)

1. **Salah klasifikasi `esp_wifi_sensing/`.** Awal saya tandai "duplikat stray" (TEMP-REDUNDANT) dan
   saya hapus. **`idf.py build` langsung gagal**: `main/idf_component.yml` menetapkan
   `espressif/esp_wifi_sensing: override_path: ../esp_wifi_sensing` (komponen vendored yang
   **dibutuhkan** build, agar instrumentasi ping bertahan dari re-resolusi). **Penanganan:** dipulihkan
   dari `managed_components/espressif__esp_wifi_sensing` (yang memuat instrumentasi yang sama),
   rebuild → biner **kembali ke 0xf16a0, sha `d3b3b0a7…` identik**. Jadi tidak ada regresi; insiden
   tertangkap oleh gerbang §G persis seperti yang mandat inginkan. **Pelajaran:** direktori yang
   belum jelas harus masuk review, tidak dihapus (melanggar §12.15 — dicatat).
2. **2 file git-tracked ikut terhapus** di `.playwright-mcp/` (`console-*.log`). **Dipulihkan** via
   `git checkout`; 0 deletion terkomit tersisa. 3 screenshot untracked memang layak hapus.
3. **Backup P1 berada di dalam `reports/official_baseline/…/p1_flash_backup/`** — akan ikut
   terhapus. **Dipindahkan** ke top-level `p1_flash_backup/` sebelum `reports/` dibersihkan; SHA
   `13e048af…` dicocokkan dengan `RECOVERY_MANIFEST.sha256` (9 file, mode 600) **sebelum & sesudah**.

## 11. File yang TIDAK dihapus karena status belum jelas (REVIEW)

- `recordings/tcp_motion/` (1755 frame, label "motion") — ambigu dataset-vs-eksperimen → **kept**.
- `recordings/stim_http/`, `stim_off/`, `stim_tcp/`, `tcp_stimulus/` — validasi stimulus; **kept**
  (manfaat hapus hanya ~3 MB, risiko menyentuh tree dataset; dapat dihapus atas permintaan eksplisit).
- `docs/investigasi-kompatibilitas-ap-csi.md` — **kept**: direferensikan aktif oleh
  `main/csi_phy_probe.h:29` (jangan hapus doc dengan referensi source, §D.2).
- `examples/.../docs/recording-pipeline-implementation.md` — **kept**: dokumentasi format aktif (Kategori 2).
- `examples/.../docs/cleanup.md` — **kept**: berkas mandat/task itu sendiri.
- `.qoder/` — **kept**: cache/pengetahuan IDE, bukan artefak eksperimen.

## 12. Kondisi akhir repository

Struktur `examples/` kembali bersih (fork `console_test_nulldata` & `csi_recv_router_promisc_on` hilang;
hanya example resmi + `wifi_sensing_demo` + `esp-radar`/`esp_wifi_sensing` vendored yang tersisa).
Seluruh temuan eksperimen kini hidup di **satu** file:
`examples/esp-radar/wifi_sensing_demo/docs/EXPERIMENT_HISTORY.md`.
`reports/` kini hanya berisi laporan cleanup ini. Tidak ada commit/push; tidak ada branch yang berubah;
tidak ada flash/erase/NVS; tidak ada eksperimen baru; format raw CSI & FSM tak disentuh.

## Path referensi

- **Dokumentasi konsolidasi:** `examples/esp-radar/wifi_sensing_demo/docs/EXPERIMENT_HISTORY.md`
- **Inventory:** `reports/repository_cleanup/20261103T230000Z/cleanup_inventory.csv`
- **Backup terlindungi:** `p1_flash_backup/` (sha `13e048af…`)
- **Dihapus (unit):** lihat baris ber-`DELETE` pada inventory (≈4,1 GB).
- **Dipertahankan (unit):** lihat baris ber-`KEEP`/`REVIEW`/`RESTORED`.

## Daftar masalah yang belum selesai (untuk pengembangan berikutnya)

- Validasi end-to-end panel Web (E2/E3) di ESP32 + Brave nyata masih **BELUM DIUJI** (perangkat tak
  terpasang saat panel dibuat; lihat `EXPERIMENT_HISTORY.md` §12).
- Jalur ekstraksi fitur timestamp-aware (`ts_us`) masih rekomendasi, belum diimplementasi.
- Pengumpulan dataset jatuh/non-jatuh terkontrol pada HTTP 64 KB belum dilakukan.
- Interferensi AP asing `d4:53:2a:61:a2:c1` tak dapat dihilangkan (one-router) — pantau per sesi.
