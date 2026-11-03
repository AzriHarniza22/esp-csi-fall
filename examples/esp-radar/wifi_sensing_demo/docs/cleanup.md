# PROJECT CLEANUP & EXPERIMENTAL ARTIFACT CONSOLIDATION
## ESP32 Wi-Fi CSI Fall Detection — Repository Cleanup

### 1. TUJUAN UTAMA

Lakukan pembersihan menyeluruh terhadap repository proyek ESP32 Wi-Fi CSI Fall Detection setelah seluruh rangkaian eksperimen dan optimasi stimulus selesai.

Selama pengembangan, banyak eksperimen telah dilakukan, termasuk:
- HTTP stimulus.
- TCP stimulus.
- DNS UDP stimulus.
- ICMP Ping.
- NTP UDP.
- Optimasi parameter dan variasi konfigurasi stimulus.
- Benchmark FPS dan CSI acquisition.
- Pengujian serial, UART, HMS, dan Web Serial Monitor.
- Pengujian recording dan dataset.
- Pengujian firmware dan perubahan konfigurasi.
- Berbagai eksperimen pendukung lainnya.

Eksperimen tersebut menghasilkan banyak file sementara, recording, log, script, laporan Markdown, grafik, build, dan artefak lain.

Sekarang saya ingin repository dikembalikan menjadi struktur yang bersih, terorganisasi, dan berfokus pada program utama penelitian.

**Hasil akhir yang diinginkan:**
1. Program utama tetap berfungsi dan seluruh perbaikan penting dipertahankan.
2. File eksperimen yang tidak lagi diperlukan dibersihkan.
3. Recording hasil eksperimen yang tidak memiliki nilai untuk dataset penelitian dihapus.
4. Dokumentasi hasil seluruh eksperimen dikonsolidasikan menjadi satu file Markdown utama.
5. Dokumentasi lain yang masih benar-benar diperlukan tetap dipertahankan.
6. Tidak ada perubahan yang merusak fitur utama.
7. Repository mudah dipahami dan dilanjutkan untuk pengembangan serta pengumpulan dataset penelitian.

Ini adalah pekerjaan cleanup repository, bukan pekerjaan optimasi algoritma atau eksperimen baru.

---

# 2. ATURAN PALING PENTING: JANGAN MENGHAPUS PERBAIKAN PROGRAM UTAMA

Selama eksperimen, beberapa masalah ditemukan dan perbaikannya diterapkan langsung ke source code program utama.

**Semua perbaikan yang masih diperlukan oleh program utama wajib dipertahankan.**

Contoh area yang harus diperiksa secara khusus:

- Perbaikan UART/serial output agar tidak terjadi interleaving antara statistik dan CSI callback.
- Perbaikan lifecycle task stimulus.
- Perbaikan stop/start dan handoff task.
- Perbaikan sinkronisasi atau race condition.
- Perbaikan serial capture dan arm-verification protocol.
- Perbaikan HTTP stimulus.
- Perbaikan TCP stimulus.
- Perbaikan pacing DNS apabila modulnya masih menjadi bagian program utama.
- Perbaikan konfigurasi dan throttle CSI.
- Perbaikan parser command dan respons ACK.
- Perbaikan Web Serial Monitor.
- Perbaikan dataset recorder.
- Perbaikan timestamp, sequence number, dan integritas raw CSI.
- Perbaikan feature extraction.
- Perbaikan FSM fall detection.
- Perbaikan integrasi alarm dan Telegram.

Daftar ini merupakan contoh area audit, bukan asumsi bahwa seluruh modul tersebut harus dipertahankan tanpa pemeriksaan.

Untuk setiap perubahan yang ditemukan, tentukan:

1. Apakah perubahan tersebut memperbaiki masalah nyata?
2. Apakah perubahan tersebut masih digunakan oleh program utama?
3. Apakah perubahan tersebut menjadi dependensi fitur yang masih aktif?
4. Apakah menghapusnya akan mengembalikan bug?
5. Apakah perubahan tersebut hanya dibutuhkan oleh eksperimen sementara?

Jika suatu perbaikan sudah menjadi bagian dari implementasi utama dan masih dibutuhkan, pertahankan.

**Jangan melakukan revert berdasarkan alasan bahwa perubahan tersebut awalnya dibuat untuk eksperimen.** Asal-usul perubahan tidak menentukan apakah perubahan itu masih dibutuhkan.

Prinsipnya:

- Perbaikan yang berguna dan menjadi bagian program utama: PERTAHANKAN.
- Kode eksperimen yang tidak digunakan program utama: HAPUS jika aman.
- Kode yang masih dibutuhkan oleh fitur utama: PERTAHANKAN.
- Kode dengan status atau fungsi yang belum jelas: JANGAN HAPUS sebelum melakukan investigasi.

---

# 3. PHASE A — PREFLIGHT DAN AUDIT REPOSITORY

Sebelum mengubah atau menghapus file apa pun:

### A1. Baca dokumentasi wajib

Baca dan ikuti:

- `docs/agent-preflight.md`
- `docs/agent-changes.md`
- Dokumentasi arsitektur proyek yang masih berlaku.
- Dokumentasi pengembangan dan aturan repository lainnya.

Patuhi seluruh ketentuan preflight yang sudah berlaku.

### A2. Audit Git

Periksa:

```bash
git status --short
git branch --show-current
git diff --stat
git diff
git ls-files
```

Identifikasi:

- Tracked files.
- Untracked files.
- Modified files.
- Deleted files.
- File yang sudah ada sebelum pekerjaan cleanup.
- Perubahan yang belum di-commit.
- File yang kemungkinan merupakan hasil pekerjaan pengguna sebelumnya.

Jangan mengasumsikan semua untracked files merupakan file sampah.

Jangan menghapus atau menimpa perubahan pengguna yang sudah ada.

Jangan melakukan:
- `git reset --hard`
- `git clean -fd`
- Revert massal.
- Checkout massal.
- Penghapusan direktori berdasarkan nama saja.

### A3. Inventarisasi file

Audit seluruh repository, termasuk direktori:

- `main/`
- `examples/`
- `components/`
- `tools/`
- `fall_detection/`
- `docs/`
- `reports/`
- `recordings/`
- `dataset/` jika tersedia.
- `build/`
- Direktori firmware dan backup.
- Direktori eksperimen lain.

Jangan hanya memeriksa direktori yang sudah diketahui.

Cari semua jenis file berikut:

| Jenis | Contoh |
|---|---|
| Dokumentasi | `.md`, `.txt`, `.rst` |
| Recording | `.csv`, `.json`, `.bin`, `.dat` |
| Log | `.log`, `.txt`, `.tsv` |
| Grafik | `.png`, `.jpg`, `.svg` |
| Script eksperimen | `.py`, `.js`, `.sh` |
| Firmware sementara | `.bin`, `.elf`, `.map` |
| Data benchmark | `.csv`, `.json`, `.tsv` |
| Konfigurasi eksperimen | `.json`, `.yaml`, `.yml`, `.ini` |
| File sementara | `.tmp`, `.bak`, `.old`, salinan duplikat |

Buat inventaris dengan informasi:

- Path.
- Ukuran.
- Jenis.
- Status Git.
- Fungsi.
- Kategori.
- Keputusan cleanup.
- Alasan keputusan.

Simpan inventaris di direktori laporan cleanup.

Jangan membuat direktori kosong yang tidak diperlukan.

---

# 4. PHASE B — KLASIFIKASI FILE

Setiap file harus dimasukkan ke salah satu kategori berikut.

## Kategori 1 — CORE PROGRAM

File yang menjadi bagian dari implementasi utama.

Contoh:
- Source firmware.
- Header.
- CMakeLists.
- Kconfig.
- Konfigurasi utama.
- Web Serial Monitor.
- Dataset recorder yang masih digunakan.
- Feature extractor.
- Fall detection logic.
- Alarm.
- Telegram integration.
- Script operasional yang benar-benar digunakan.
- Test yang melindungi fitur utama.

Keputusan: PERTAHANKAN.

## Kategori 2 — ESSENTIAL DOCUMENTATION

Dokumentasi yang dibutuhkan untuk memahami, membangun, menjalankan, atau mengembangkan program utama.

Contoh:
- README utama.
- Dokumentasi arsitektur.
- Dokumentasi setup ESP-IDF.
- Dokumentasi konfigurasi perangkat.
- Dokumentasi format dataset.
- Dokumentasi recording.
- Dokumentasi protocol komunikasi.
- Dokumentasi cara menjalankan program.
- Dokumentasi penggunaan Web Serial Monitor.

Keputusan: PERTAHANKAN, tetapi hindari duplikasi.

## Kategori 3 — EXPERIMENTAL EVIDENCE

File hasil eksperimen yang sudah selesai dan temuan pentingnya dapat dirangkum dalam dokumentasi utama.

Contoh:
- `reports/tcp_*`
- `reports/csi_stimulus_benchmark`
- Log HTTP.
- Log TCP.
- Log DNS.
- Log ICMP.
- Log NTP.
- Benchmark CSV.
- Grafik eksperimen.
- Recording eksperimen.
- Script benchmark yang hanya digunakan sekali.
- Laporan Phase A–J.
- Laporan optimasi sebelumnya.

Keputusan: RANGKUM, lalu HAPUS jika tidak lagi diperlukan.

Jangan menghapus sebelum seluruh temuan penting berhasil dipindahkan dan diverifikasi dalam dokumentasi konsolidasi.

## Kategori 4 — TEMPORARY / REDUNDANT

Contoh:
- File debug sementara.
- File hasil percobaan yang gagal dan tidak mengandung temuan unik.
- Salinan laporan yang sudah diperbaiki.
- Grafik duplikat.
- Build sementara.
- Log berulang yang tidak memberikan informasi tambahan.
- Script yang hanya digunakan untuk satu eksperimen dan tidak lagi dipakai.

Keputusan: HAPUS setelah dipastikan aman.

## Kategori 5 — PROTECTED / USER DATA

File yang tidak boleh dihapus hanya karena terlihat seperti artefak eksperimen.

Contoh:
- Dataset penelitian yang memang akan digunakan.
- Recording aktivitas yang berpotensi digunakan untuk training.
- Recording simulasi jatuh.
- Backup firmware P1.
- Recovery manifest.
- Data konfigurasi penting.
- Credential atau konfigurasi lokal.
- File yang belum jelas kepemilikannya.
- File yang merupakan satu-satunya bukti suatu temuan.

Keputusan: PERTAHANKAN.

Jika tidak jelas apakah recording merupakan data eksperimen atau dataset penelitian, jangan hapus. Masukkan ke daftar review.

---

# 5. PHASE C — KONSOLIDASI SELURUH TEMUAN EKSPERIMEN KE SATU FILE MARKDOWN

Ini merupakan bagian terpenting pekerjaan.

Buat satu dokumentasi utama:

`docs/EXPERIMENT_HISTORY.md`

Dokumentasi ini harus merangkum seluruh eksperimen yang pernah dilakukan dan temuan yang masih relevan.

Jangan sekadar menggabungkan isi seluruh file Markdown menggunakan concatenation.

Baca, evaluasi, deduplikasi, dan susun ulang informasi agar menjadi dokumentasi teknis yang koheren.

## C1. Sumber informasi

Cari dan audit seluruh file Markdown yang berhubungan dengan eksperimen.

Termasuk tetapi tidak terbatas pada:

- `reports/csi_stimulus_benchmark/**`
- `reports/tcp_integration_wifi_sensing_demo/**`
- `reports/tcp_csi_optimization/**`
- `reports/official_baseline/**` jika berisi temuan eksperimen yang relevan.
- Laporan eksperimen sebelumnya.
- Hypothesis ledger.
- Campaign plan.
- Final report.
- Benchmark report.
- Window assessment.
- Changelog eksperimen.
- Dokumentasi bug dan perbaikannya.
- Dokumentasi dataset dan recording.
- File Markdown lain yang ditemukan selama audit.

Jangan mengandalkan nama file saja.

Baca isi dan hubungan antarfile.

Perhatikan laporan yang berisi:
- Hasil awal.
- Hasil yang invalid.
- Koreksi hasil.
- Hipotesis yang disangkal.
- Perbaikan yang diterapkan.
- Kesimpulan final.

Jika ada beberapa versi kesimpulan, gunakan kesimpulan terakhir yang telah dikoreksi dan didukung bukti.

Jangan mempertahankan klaim lama yang sudah dicabut tanpa menjelaskan koreksinya.

## C2. Struktur dokumentasi yang diinginkan

Gunakan struktur berikut.

# Experiment History — ESP32 Wi-Fi CSI Fall Detection

## 1. Tujuan Eksperimen

Jelaskan tujuan seluruh rangkaian eksperimen dan hubungannya dengan penelitian deteksi jatuh berbasis Wi-Fi CSI.

## 2. Arsitektur Sistem dan Lingkungan Eksperimen

Catat:
- Board ESP32 yang digunakan.
- ESP-IDF.
- Firmware.
- Router dan karakteristik koneksi yang diketahui.
- Frekuensi Wi-Fi.
- Kanal.
- Arsitektur stimulus.
- Arsitektur CSI acquisition.
- Alur data ESP32 sampai host.
- Batasan perangkat dan lingkungan.

Jangan mencantumkan password, token, atau credential.

## 3. Riwayat Metode Stimulus

Rangkum seluruh metode yang pernah diuji:

- HTTP.
- TCP.
- DNS UDP.
- ICMP.
- NTP.
- Metode lain jika ditemukan dalam dokumentasi lama.

Untuk setiap metode, dokumentasikan:

- Tujuan.
- Mekanisme.
- Konfigurasi.
- Hasil pengujian.
- Jumlah recording atau sampel.
- Throughput CSI.
- Stabilitas.
- Kelebihan.
- Kekurangan.
- Masalah yang ditemukan.
- Status akhir.
- Alasan dipilih atau ditolak.

Sertakan tabel perbandingan.

Bedakan hasil yang benar-benar diukur dengan hipotesis atau estimasi.

Jangan membandingkan angka dari eksperimen yang berbeda seolah-olah berasal dari kondisi identik.

## 4. Hasil Optimasi Stimulus

Dokumentasikan hasil penting:

- HTTP 200 KB.
- HTTP 64 KB.
- HTTP keep-alive.
- TCP optimization.
- DNS pacing.
- Perbandingan A-B-A.
- Hasil yang dikoreksi akibat interferensi.
- Konfigurasi yang dipilih sebagai konfigurasi kerja.

Cantumkan konfigurasi final yang direkomendasikan berdasarkan bukti.

Jelaskan keterbatasan kesimpulannya.

## 5. Measurement Audit

Rangkum:

- CSI throttle default.
- `SET_CSI_PERIOD 0`.
- Definisi counter.
- Device callback FPS.
- Host received FPS.
- Dropped frames.
- Accounting identity.
- Serial capture.
- Arm-verification.
- Race condition.
- Masalah pengukuran yang berhasil ditemukan.

## 6. Wi-Fi Interference

Dokumentasikan:
- Perangkat asing yang teridentifikasi.
- Pengaruh frame foreign-source.
- Arti `no_peer`.
- Mengapa `no_peer` bukan indikator langsung kualitas stimulus.
- Dampak interferensi pada perbandingan eksperimen.
- Cara menginterpretasikan hasil benchmark berikutnya.

## 7. CSI Acquisition dan Temporal Characteristics

Rangkum:
- Frame rate.
- Inter-arrival time.
- P50/P95/P99.
- Gap.
- Bucket 0,5 detik.
- Durasi jendela 24 frame.
- Variasi timestamp.
- Device clock versus host clock.
- Keterbatasan akuisisi CSI.

## 8. Recording dan Dataset

Rangkum:
- Perkembangan recorder.
- Format recording.
- Raw CSI.
- Base64 jika digunakan.
- Raw IQ.
- Timestamp.
- Sequence number.
- Metadata.
- First-word-invalid.
- Validasi recording.
- Kompatibilitas format lama.
- Kelebihan dan kekurangan format dataset.
- Masalah yang masih perlu diperbaiki.

Bedakan dataset penelitian yang masih digunakan dengan recording eksperimen sementara.

## 9. Bug dan Perbaikan yang Sudah Diterapkan

Buat tabel:

| Masalah | Penyebab | Perbaikan | File/modul | Status |
|---|---|---|---|---|

Masukkan hanya masalah yang memiliki bukti.

Prioritaskan perbaikan yang masih menjadi bagian program utama.

## 10. Eksperimen yang Gagal, Ditolak, atau Tidak Konklusif

Dokumentasikan:
- Eksperimen yang tidak menghasilkan CSI.
- Eksperimen yang gagal karena bug harness.
- Eksperimen yang tercemar race.
- Eksperimen yang terpengaruh interferensi.
- Hipotesis yang ditolak.
- Eksperimen yang belum memiliki bukti cukup.

Jelaskan mengapa hasilnya tidak boleh digunakan sebagai kesimpulan final.

## 11. Keputusan Teknis Saat Ini

Cantumkan:
- Metode stimulus standar.
- Konfigurasi HTTP.
- Status TCP.
- Status DNS.
- Status ICMP/NTP.
- Konfigurasi CSI period.
- Rekomendasi ekstraksi timestamp-aware.
- Status recorder.
- Status firmware.
- Hal yang sudah selesai.

Pastikan keputusan mencerminkan implementasi aktual dan bukan sekadar rencana.

## 12. Pekerjaan yang Masih Diperlukan

Pisahkan:
- Masalah yang belum selesai.
- Validasi yang belum dilakukan.
- Fitur yang belum diuji.
- Keterbatasan penelitian.
- Prioritas pengembangan berikutnya.

Jangan memasukkan pekerjaan yang sudah selesai sebagai TODO.

## 13. Referensi Implementasi

Cantumkan path source code yang masih relevan untuk menelusuri temuan.

Jangan membuat referensi ke file laporan eksperimen yang nantinya akan dihapus.

Gunakan path file program utama atau bagian dokumentasi yang tetap dipertahankan.

## C3. Standar kualitas dokumentasi

Dokumentasi harus:

- Menggunakan Bahasa Indonesia teknis yang konsisten.
- Mempertahankan istilah teknis penting dalam bahasa Inggris.
- Tidak mengandung klaim tanpa bukti.
- Tidak mengulang informasi yang sama.
- Membedakan fakta, hasil pengukuran, hipotesis, dan rekomendasi.
- Menyebutkan konfigurasi dan satuan dengan benar.
- Mempertahankan koreksi terhadap kesimpulan lama.
- Cukup detail untuk memahami riwayat eksperimen tanpa membuka puluhan laporan lama.

Gunakan label:

- **TERBUKTI** — didukung hasil eksperimen.
- **TERAMATI** — terlihat pada pengujian tetapi belum cukup untuk generalisasi.
- **TIDAK KONKLUSIF** — bukti tidak memadai.
- **DITOLAK** — tidak memenuhi kriteria atau terbukti tidak layak.
- **BELUM DIUJI** — belum ada validasi.
- **REKOMENDASI** — keputusan teknis berdasarkan bukti yang tersedia.

---

# 6. PHASE D — CLEANUP FILE MARKDOWN

Setelah `docs/EXPERIMENT_HISTORY.md` selesai dan diverifikasi:

Audit semua file `.md`.

Pertahankan dokumentasi yang masih diperlukan untuk menjalankan dan mengembangkan program utama.

Dokumentasi eksperimen yang isinya sudah dipindahkan secara lengkap ke `EXPERIMENT_HISTORY.md` dapat dihapus jika:

1. Tidak mengandung informasi unik yang belum dipindahkan.
2. Tidak digunakan sebagai referensi aktif oleh source code atau tool.
3. Tidak diperlukan oleh preflight.
4. Tidak diperlukan oleh proses build atau pengujian.
5. Tidak menjadi satu-satunya dokumentasi prosedur operasional yang masih dibutuhkan.

Dokumentasi yang harus dipertahankan meliputi:

- `README.md`.
- `docs/agent-preflight.md`.
- `docs/agent-changes.md`.
- Dokumentasi arsitektur aktif.
- Dokumentasi setup dan penggunaan.
- Dokumentasi dataset/recording yang masih berlaku.
- Dokumentasi lain yang benar-benar dibutuhkan.

Jangan menghapus `docs/agent-changes.md` meskipun sebagian riwayat perubahan sudah dirangkum.

`docs/agent-changes.md` tetap menjadi changelog resmi repository.

Sebelum menghapus Markdown, pastikan seluruh informasi penting sudah dipindahkan ke file konsolidasi.

Periksa juga broken links dan referensi ke file yang dihapus.

---

# 7. PHASE E — CLEANUP RECORDINGS DAN DATA EKSPERIMEN

Lakukan audit menyeluruh terhadap seluruh recording dan data hasil eksperimen.

Pisahkan dengan tegas:

### E1. Recording eksperimen stimulus

Contoh:
- HTTP benchmark.
- TCP benchmark.
- DNS benchmark.
- ICMP benchmark.
- NTP benchmark.
- Recording A-B-A.
- Capture untuk menguji FPS.
- Capture untuk menguji UART.
- Capture debugging.
- Recording sementara untuk memvalidasi harness.

Jika recording tersebut hanya berfungsi sebagai bukti eksperimen yang telah selesai, dan seluruh hasil penting sudah tercatat dalam `EXPERIMENT_HISTORY.md`, recording dapat dihapus.

### E2. Dataset penelitian

Jangan menghapus:
- Recording aktivitas manusia yang memang disiapkan untuk dataset.
- Recording simulasi jatuh.
- Recording non-fall.
- Dataset yang sudah dianotasi.
- Recording yang berpotensi digunakan untuk training atau evaluasi.
- Metadata yang dibutuhkan untuk memahami dataset.

Jika status recording tidak jelas, pertahankan.

### E3. Data eksperimen yang masih memiliki nilai unik

Jika suatu recording merupakan satu-satunya bukti untuk temuan penting yang belum dapat dirangkum secara memadai:

- Pertahankan sementara.
- Catat alasannya dalam inventory.
- Jangan menghapus hanya karena ukurannya besar.

### E4. Cleanup direktori

Setelah klasifikasi selesai:

- Hapus recording eksperimen yang tidak lagi diperlukan.
- Hapus log sementara.
- Hapus file capture duplikat.
- Hapus hasil benchmark sementara.
- Hapus file data yang tidak digunakan.
- Hapus direktori kosong yang tersisa.

Jangan menghapus direktori dataset utama.

Jangan menghapus backup firmware P1.

Jangan menghapus recovery manifest.

Jangan menghapus konfigurasi lokal yang masih diperlukan.

Jangan menghapus data pengguna.

---

# 8. PHASE F — CLEANUP SCRIPT DAN KODE EKSPERIMEN

Audit semua script eksperimen.

Contoh:
- Script benchmark HTTP.
- Script benchmark TCP.
- Script DNS.
- Script ICMP.
- Script NTP.
- Script plotting khusus kampanye.
- Script pengolahan log.
- Script analisis satu kali.
- Script pengujian sementara.

Untuk setiap script, tentukan:

1. Apakah masih digunakan program utama?
2. Apakah masih dibutuhkan untuk pengumpulan dataset?
3. Apakah masih dibutuhkan untuk validasi recording?
4. Apakah masih dibutuhkan untuk training?
5. Apakah hanya digunakan untuk kampanye eksperimen yang telah selesai?

Keputusan:

- Script operasional program utama: PERTAHANKAN.
- Script recorder/validator dataset yang masih digunakan: PERTAHANKAN.
- Script training dan evaluasi yang masih digunakan: PERTAHANKAN.
- Script benchmark yang tidak lagi digunakan: HAPUS jika hasilnya sudah terdokumentasi.
- Script debug sementara: HAPUS jika tidak memiliki fungsi lain.

Jangan menghapus utility hanya berdasarkan nama atau lokasi file.

Periksa seluruh pemanggilan dan dependensinya sebelum menghapus.

Periksa juga:
- CMake references.
- Python imports.
- JavaScript imports.
- Shell scripts.
- Build scripts.
- Test references.
- README references.
- CI configuration jika ada.

---

# 9. PHASE G — BUILD, TEST, DAN VALIDASI PROGRAM UTAMA

Setelah cleanup, lakukan validasi untuk memastikan tidak ada fitur utama yang rusak.

Prioritaskan:

### G1. Firmware

- Build firmware utama.
- Pastikan tidak ada missing source atau header.
- Pastikan CMakeLists tetap benar.
- Pastikan konfigurasi ESP-IDF tetap benar.
- Pastikan modul stimulus yang digunakan program utama tetap tersedia.
- Pastikan UART dan CSI callback tidak rusak.

### G2. Web Serial Monitor

Pastikan:

- HTML valid.
- JavaScript valid.
- Serial communication tetap bekerja.
- Kontrol stimulus yang sudah ada tetap bekerja.
- Selector stimulus yang sudah diperbaiki tetap memiliki tiga metode sesuai implementasi saat ini.
- Jangan mengubah atau menghapus pekerjaan selector tersebut sebagai bagian cleanup.
- Fitur recording tidak rusak.

**Penting:** Jangan mengembalikan selector ke implementasi lama atau mengubahnya menjadi konfigurasi lain. Pertahankan kondisi UI terkini yang sudah selesai diperbaiki.

### G3. Dataset

Pastikan:
- Recorder masih dapat dijalankan.
- Validator masih dapat dijalankan.
- Format raw CSI tidak berubah.
- Timestamp tetap tersedia.
- Sequence number tetap benar.
- Metadata tetap lengkap sesuai implementasi.
- File recording baru dapat dibuat dan dibaca.

Jika perlu melakukan hardware capture, setiap recording maksimal 60 detik. Tidak boleh ada recording individual lebih dari 60 detik.

### G4. Pengujian lainnya

Jalankan automated tests yang relevan.

Jangan mengulang kampanye benchmark stimulus.

Jangan melakukan eksperimen baru hanya untuk membuktikan hasil lama.

Jika hardware testing tidak diperlukan untuk memvalidasi cleanup, cukup gunakan build dan automated tests.

---

# 10. PHASE H — CLEANUP GIT DAN STRUKTUR AKHIR

Setelah seluruh perubahan selesai:

1. Periksa `git status`.
2. Periksa seluruh file yang dihapus.
3. Periksa seluruh file yang dimodifikasi.
4. Pastikan tidak ada file utama yang hilang.
5. Pastikan tidak ada referensi rusak.
6. Pastikan tidak ada dokumentasi yang terhapus sebelum dikonsolidasikan.
7. Pastikan tidak ada data penelitian yang ikut terhapus.
8. Pastikan tidak ada backup penting yang berubah.

Jangan melakukan commit kecuali diminta.

Jangan melakukan push.

Jangan mengubah branch.

Jangan menghapus file yang statusnya masih meragukan.

---

# 11. PHASE I — LAPORAN CLEANUP

Simpan laporan akhir di:

`reports/repository_cleanup/<timestamp>/`

Minimal berisi:

### `CLEANUP_REPORT.md`

Memuat:

1. Kondisi repository sebelum cleanup.
2. Jumlah file yang diaudit.
3. Jumlah file yang dipertahankan.
4. Jumlah file yang dihapus.
5. Jumlah recording yang dihapus.
6. Jumlah dokumentasi yang dikonsolidasikan.
7. File utama yang dipertahankan.
8. Perbaikan program yang dipertahankan.
9. Hasil build dan test.
10. Masalah yang ditemukan.
11. File yang tidak dihapus karena statusnya belum jelas.
12. Kondisi akhir repository.

### `cleanup_inventory.csv`

Minimal kolom:

```text
path,size,type,git_status,category,decision,reason
```

### `CLEANUP_REPORT.md` harus mencantumkan:

- Path dokumentasi konsolidasi.
- Path file yang dihapus.
- Path file yang dipertahankan.
- Hasil verifikasi firmware.
- Hasil verifikasi Web Serial Monitor.
- Hasil verifikasi dataset recorder.
- Daftar masalah yang belum selesai.

Jangan membuat laporan yang hanya menyatakan "cleanup berhasil". Berikan bukti dan rincian perubahan.

---

# 12. KETENTUAN WAJIB

1. Jangan menghapus perbaikan yang sudah menjadi bagian program utama.
2. Jangan melakukan revert terhadap bug fix yang masih diperlukan.
3. Jangan menghapus dataset penelitian.
4. Jangan menghapus backup P1.
5. Jangan menghapus recovery manifest.
6. Jangan menghapus konfigurasi lokal yang masih dibutuhkan.
7. Jangan melakukan erase flash atau NVS.
8. Jangan melakukan factory reset.
9. Jangan melakukan eksperimen stimulus baru.
10. Jangan menjalankan recording lebih dari 60 detik.
11. Jangan mengubah algoritma fall detection.
12. Jangan mengubah format raw CSI.
13. Jangan merusak Web Serial Monitor.
14. Jangan merusak fitur recording.
15. Jangan menghapus file yang belum dipahami fungsinya.
16. Jangan menghapus dokumentasi sebelum seluruh informasi pentingnya dipindahkan.
17. Jangan melakukan Git reset, clean, atau revert massal.
18. Jangan commit atau push.
19. Jangan mengklaim pengujian berhasil jika hanya dilakukan secara statis.
20. Semua perubahan harus dicatat dalam `docs/agent-changes.md`.

Jika menemukan file yang tidak jelas statusnya, pertahankan dan masukkan ke daftar review. Jangan mengambil risiko menghapusnya.

---

# 13. KRITERIA SELESAI

Pekerjaan baru dinyatakan selesai jika:

- [ ] Seluruh repository sudah diaudit.
- [ ] Seluruh file diklasifikasikan.
- [ ] Semua temuan eksperimen penting sudah dikonsolidasikan ke `docs/EXPERIMENT_HISTORY.md`.
- [ ] Kesimpulan lama yang sudah dikoreksi tidak lagi disajikan sebagai hasil final.
- [ ] Dokumentasi eksperimen yang redundant sudah dibersihkan.
- [ ] Recording eksperimen yang tidak berguna sudah dibersihkan.
- [ ] Dataset penelitian tetap utuh.
- [ ] Script eksperimen yang tidak digunakan sudah dibersihkan.
- [ ] Seluruh bug fix penting pada program utama tetap dipertahankan.
- [ ] Selector stimulus Web Serial Monitor tetap dalam kondisi terkini.
- [ ] Firmware berhasil dibangun.
- [ ] Test yang relevan berhasil.
- [ ] Tidak ada broken references yang diketahui.
- [ ] Backup P1 tetap utuh.
- [ ] Changelog diperbarui.
- [ ] Cleanup report dan inventory tersedia.

## 14. INSTRUKSI PELAKSANAAN

Kerjakan seluruh proses secara sistematis dan mandiri.

Jangan langsung menghapus banyak file sebelum audit.

Jangan hanya membersihkan direktori `reports/`. Cari seluruh artefak eksperimen yang tersebar di repository.

Prioritaskan keselamatan source code dan data penelitian daripada agresivitas cleanup.

Jika menemukan masalah pada program utama selama audit, jangan memperbaikinya secara sembarangan sebagai bagian dari cleanup. Catat masalahnya, telusuri dampaknya, dan hanya lakukan perubahan jika memang diperlukan untuk menjaga fungsi yang sudah ada.

**Target akhir: repository yang bersih, dokumentasi yang ringkas tetapi lengkap, tidak ada eksperimen lama yang mengotori struktur program utama, dan seluruh hasil penelitian terdahulu tetap dapat dipahami melalui satu file Markdown konsolidasi.**