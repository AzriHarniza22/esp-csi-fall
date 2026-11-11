# ESP32 Wi-Fi CSI Fall Detection – Dataset Quality Audit Report

**Audit date:** 2026-11-10
**Dataset path:** `/home/azri/coding/wifi_sensing_demo/examples/esp-radar/wifi_sensing_demo/recordings`
**Total recordings audited:** 130

## 1. Metode Audit

Audit ini bersifat **read-only**. Tidak ada data yang dimodifikasi, dihapus, atau direkam ulang.

### Sumber data
- `frames.csv` sebagai sumber raw CSI utama (payload `valid_b64`, `raw_b64`, timestamp, sequence)
- `meta.json` untuk metadata, label, durasi, dan konfigurasi
- `index.csv` sebagai daftar registrasi recording

### Teknik audit
- **Technical CSI audit:** Parsing `frames.csv` secara streaming per-recording
  - Frame count, timestamp monotonicity, duplicate timestamps, inter-frame gaps
  - `payload_ok` flags, Base64 decode validation, `valid_len` byte-count check
  - `first_word_invalid` consistency per recording
  - `data_type` dan channel consistency
  - `rx_seq` gap analysis (16-bit rollover-aware)
  - `frame_sequence` monotonicity
- **Amplitude analysis:** Decode `valid_b64` → int8 → amplitude per subcarrier pair
  - Global mean, std, median, IQR, MAD per recording
  - Flatline detection (subcarrier std < 0.5)
  - Identical consecutive frame detection
  - Per-frame outlier detection (mean > 4σ dari global mean)
- **Statistical cross-recording analysis:**
  - Per-label amplitude distribution statistics
  - Z-score outlier detection: |z| > 3.0 dari rata-rata label
  - Low-variation detection untuk label aktif: z < −2.5 dalam distribusi amp_std per label
- **Metadata audit:** Konsistensi label, subject_id, session_id, schema_version, annotations

### Threshold
Semua threshold didasarkan pada distribusi aktual data, bukan nilai sembarang:
- Large gap: > max(5× median interval, 500 ms)
- Amplitude outlier (cross-recording): |z| > 3.0 dari mean per label
- Low variation (active labels): z < −2.5 dari distribusi amp_std per label
- Identical runs: > 5 frame berturutan identik
- Very low frame count: < 100 frame untuk recording ≥ 10s

## 2. Ringkasan Hasil

| Metrik | Nilai |
|---|---|
| Total recording | 130 |
| PASS | **118** |
| REVIEW | **12** |
| INVALID | **0** |
| ELIGIBLE | 118 |
| RESTRICTED | 12 |
| NOT_ELIGIBLE | 0 |

### Distribusi per label

| Label | Total | PASS | REVIEW | INVALID |
|---|---|---|---|---|
| `bending` | 10 | 9 | 1 | 0 |
| `empty_room` | 9 | 9 | 0 | 0 |
| `fall_backward` | 20 | 18 | 2 | 0 |
| `fall_forward` | 20 | 17 | 3 | 0 |
| `fall_keseleo` | 11 | 10 | 1 | 0 |
| `fall_lemas` | 10 | 7 | 3 | 0 |
| `fast_sitting` | 10 | 10 | 0 | 0 |
| `object_drop` | 10 | 10 | 0 | 0 |
| `still_sitting` | 10 | 10 | 0 | 0 |
| `still_standing` | 10 | 10 | 0 | 0 |
| `walking` | 10 | 8 | 2 | 0 |

## 3. Technical CSI Audit – Temuan Global

### 3.1 `first_word_invalid`

- Recording dengan 100% `first_word_invalid=true`: **130/130**
- Recording dengan inkonsistensi `first_word_invalid`: **0**

  Catatan: `first_word_invalid=true` pada 100% frame adalah kondisi **normal** untuk ESP32 secondary_channel=NONE. Ini bukan indikasi kerusakan.

### 3.2 Payload Integrity

- Total frame diaudit: **39,337**
- Frame `payload_ok=true`: **39,337** (100.0%)
- Frame `payload_ok=false`: **0**
- Frame `valid_len` mismatch (decode byte count ≠ valid_len): **0**
- Frame decode error: **0**

### 3.3 Timestamp dan Interval Frame

Semua recording menggunakan `csi_period_ms=0` (unthrottled). Frame rate ditentukan oleh HTTP stimulus ke Cloudflare dan kondisi jaringan.

| Statistik | Nilai |
|---|---|
| Mean interval rata-rata (semua recording) | 35.2 ms |
| Median interval rata-rata | 22.0 ms |
| Max gap tertinggi | 1393.6 ms |
| Max gap rata-rata | 226.5 ms |

- Recording dengan large timestamp gaps: **12**
  - `20261104T154805Z_bending_004`: LARGE_TIMESTAMP_GAPS:1 gaps >500ms (max_gap=660.072ms, label=bending)
  - `20261107T150949Z_fall_backward_012`: LARGE_TIMESTAMP_GAPS:1 gaps >500ms (max_gap=1335.735ms, label=fall_backward)
  - `20261107T151033Z_fall_backward_014`: LARGE_TIMESTAMP_GAPS:1 gaps >500ms (max_gap=753.474ms, label=fall_backward)
  - `20261104T160014Z_fall_forward_010`: LARGE_TIMESTAMP_GAPS:1 gaps >500ms (max_gap=628.266ms, label=fall_forward)
  - `20261107T150352Z_fall_forward_017`: LARGE_TIMESTAMP_GAPS:2 gaps >500ms (max_gap=1390.317ms, label=fall_forward)
  - `20261107T150628Z_fall_forward_024`: LARGE_TIMESTAMP_GAPS:2 gaps >500ms (max_gap=1097.984ms, label=fall_forward)
  - `20261107T153710Z_fall_right_008`: LARGE_TIMESTAMP_GAPS:1 gaps >500ms (max_gap=706.51ms, label=fall_keseleo)
  - `20261107T151834Z_fall_left_010`: LARGE_TIMESTAMP_GAPS:1 gaps >500ms (max_gap=1393.592ms, label=fall_lemas)
  - `20261107T151907Z_fall_left_011`: LARGE_TIMESTAMP_GAPS:1 gaps >500ms (max_gap=630.416ms, label=fall_lemas)
  - `20261107T152147Z_fall_left_016`: LARGE_TIMESTAMP_GAPS:2 gaps >500ms (max_gap=794.098ms, label=fall_lemas)
  - `20261104T043259Z_walking_001`: LARGE_TIMESTAMP_GAPS:2 gaps >500ms (max_gap=787.39ms, label=walking)
  - `20261104T043314Z_walking_002`: LARGE_TIMESTAMP_GAPS:1 gaps >500ms (max_gap=798.593ms, label=walking)

### 3.4 `rx_seq` Gap Analysis

- Total `rx_seq` gaps (seluruh dataset): **14,995**
- Recording dengan rx_seq gaps > 50: **130**

  Catatan: `rx_seq` gap dapat disebabkan oleh paket WiFi yang tidak sampai ke ESP32 atau frame yang tidak dilaporkan. Bukan otomatis indikasi kerusakan pipeline.

## 4. Amplitude Analysis

### 4.1 Per-label amplitude statistics (mean of per-recording mean amplitudes)

| Label | N | Mean | Std | Median | Min | Max | P05 | P95 |
|---|---|---|---|---|---|---|---|---|
| `bending` | 10 | 23.50 | 0.19 | 23.49 | 23.18 | 23.87 | 23.24 | 23.79 |
| `empty_room` | 9 | 23.47 | 0.13 | 23.41 | 23.32 | 23.77 | 23.34 | 23.71 |
| `fall_backward` | 20 | 25.23 | 1.17 | 25.14 | 23.32 | 27.68 | 23.33 | 27.54 |
| `fall_forward` | 20 | 25.54 | 0.91 | 25.32 | 24.12 | 27.42 | 24.45 | 27.20 |
| `fall_keseleo` | 11 | 26.82 | 0.54 | 26.93 | 25.62 | 27.50 | 25.84 | 27.45 |
| `fall_lemas` | 10 | 24.77 | 0.66 | 24.50 | 24.20 | 26.10 | 24.23 | 26.06 |
| `fast_sitting` | 10 | 27.11 | 1.42 | 27.35 | 23.46 | 28.87 | 24.76 | 28.62 |
| `object_drop` | 10 | 24.82 | 0.63 | 24.77 | 23.79 | 25.92 | 23.98 | 25.84 |
| `still_sitting` | 10 | 24.41 | 0.67 | 24.45 | 23.49 | 25.61 | 23.51 | 25.40 |
| `still_standing` | 10 | 24.85 | 0.61 | 25.11 | 23.85 | 25.63 | 23.90 | 25.62 |
| `walking` | 10 | 24.35 | 1.05 | 23.96 | 23.60 | 27.32 | 23.64 | 26.20 |

### 4.2 Flatline / Low-variation Signal

- Recording dengan >30% flat frames (subcarrier std < 0.5): **0**

  Catatan: `empty_room`, `still_standing`, `still_sitting` secara inheren memiliki sinyal stabil — ini **bukan** anomali.

### 4.3 Frame Identik Berurutan

- Recording dengan >5 consecutive identical amplitude frames: **0**

### 4.4 Cross-recording Outliers

- Recording dengan amplitude z-score > 3.0 vs label group: **0**

- Recording dengan amp variation rendah (active label, z < -2.5): **1**
  - `20261104T154615Z_fast_sitting_001` (fast_sitting): LOW_AMP_VARIATION:amp_std=2.083,group_std_mean=5.460,z=-2.89

## 5. Metadata dan Protokol

- Recording tanpa `subject_id`: **89**
- Recording tanpa `session_id`: **89**

  Catatan: 89 recording lama diketahui tidak memiliki subject_id/session_id. Ini adalah **metadata incompleteness**, bukan kerusakan teknis.

- Recording dengan `annotation_complete=true`: **41/130**
- Fall recordings tanpa annotation complete: **20**

### 5.1 Label Consistency

- Recording dengan mismatch label (folder vs meta): **0**

### 5.2 Activity Consistency – `fall_keseleo`

- Total `fall_keseleo` recordings: **11**

  File dalam folder `fall_keseleo` menggunakan prefix `fall_right_*` pada filename (bukan `fall_keseleo_*`).
  Ini merupakan inkonsistensi penamaan file vs label. Namun `meta.json` semua recording ini mencantumkan `activity_label=fall_keseleo` (sesuai index.csv).

  - Recording dengan annotation complete: **11/11**

## 6. Daftar Recording REVIEW dan INVALID

### 6.1 INVALID (0)

_Tidak ada recording INVALID._

### 6.2 REVIEW (12)

| Recording ID | Label | Frames | Reason | Confidence |
|---|---|---|---|---|
| `20261104T154805Z_bending_004` | `bending` | 273 | LARGE_TIMESTAMP_GAPS:1 gaps >500ms | MEDIUM |
| `20261107T150949Z_fall_backward_012` | `fall_backward` | 314 | LARGE_TIMESTAMP_GAPS:1 gaps >500ms | MEDIUM |
| `20261107T151033Z_fall_backward_014` | `fall_backward` | 324 | LARGE_TIMESTAMP_GAPS:1 gaps >500ms | MEDIUM |
| `20261104T160014Z_fall_forward_010` | `fall_forward` | 265 | LARGE_TIMESTAMP_GAPS:1 gaps >500ms | MEDIUM |
| `20261107T150352Z_fall_forward_017` | `fall_forward` | 266 | LARGE_TIMESTAMP_GAPS:2 gaps >500ms | MEDIUM |
| `20261107T150628Z_fall_forward_024` | `fall_forward` | 301 | LARGE_TIMESTAMP_GAPS:2 gaps >500ms | MEDIUM |
| `20261107T153710Z_fall_right_008` | `fall_keseleo` | 330 | LARGE_TIMESTAMP_GAPS:1 gaps >500ms | MEDIUM |
| `20261107T151834Z_fall_left_010` | `fall_lemas` | 298 | LARGE_TIMESTAMP_GAPS:1 gaps >500ms | MEDIUM |
| `20261107T151907Z_fall_left_011` | `fall_lemas` | 323 | LARGE_TIMESTAMP_GAPS:1 gaps >500ms | MEDIUM |
| `20261107T152147Z_fall_left_016` | `fall_lemas` | 303 | LARGE_TIMESTAMP_GAPS:2 gaps >500ms | MEDIUM |
| `20261104T043259Z_walking_001` | `walking` | 228 | LARGE_TIMESTAMP_GAPS:2 gaps >500ms | MEDIUM |
| `20261104T043314Z_walking_002` | `walking` | 276 | LARGE_TIMESTAMP_GAPS:1 gaps >500ms | MEDIUM |

## 7. Rekomendasi

### 7.1 Tindakan segera (sebelum training)

1. **INVALID recordings** (jika ada): Jangan digunakan untuk training. Lakukan verifikasi manual dan rekam ulang jika diperlukan.
2. **REVIEW recordings**: Lakukan inspeksi manual sebelum diputuskan PASS atau dikeluarkan dari dataset.
3. **Fall recordings tanpa annotation**: Semua fall recordings sebaiknya memiliki `annotation_complete=true` dengan `fall_start` dan `fall_impact` timestamp sebelum digunakan untuk model yang memerlukan temporal precision.

### 7.2 Metadata incompleteness

- Recording tanpa `subject_id`/`session_id` dapat digunakan untuk training binary classification, tetapi **tidak dapat digunakan untuk subject-independent evaluation** tanpa risiko data leakage.
- Pisahkan recording ini ke split terpisah atau anotasikan subject secara manual jika memungkinkan.

### 7.3 `fall_keseleo` filename inconsistency

- File dalam folder `fall_keseleo` menggunakan prefix `fall_right_*`. Ini hanya inkonsistensi penamaan, bukan kesalahan label karena `meta.json` sudah benar.
- Pertimbangkan rename file untuk konsistensi, tetapi ini bukan prioritas audit teknis.

### 7.4 `fall_lemas` filename inconsistency

- File dalam folder `fall_lemas` menggunakan prefix `fall_left_*`. Sama seperti fall_keseleo, ini inkonsistensi penamaan.

### 7.5 Walking recordings – waktu pengambilan

- 10 walking recordings diambil pada jam 04:32-04:35 UTC (sekitar pukul 11-12 siang WIB).
  Ini berbeda session dari recordings lain di hari yang sama yang diambil siang-sore UTC.
  Perbedaan session ini perlu diperhitungkan saat train/test split untuk menghindari data leakage.

### 7.6 Annotation completeness untuk fall recordings

- 20 dari 61 fall recordings tidak memiliki annotation complete.
  `fall_start` dan `fall_impact` diperlukan untuk temporal fall detection models.
  Tanpa anotasi, hanya binary classification (fall/non-fall) yang dapat dilakukan dengan data ini.

## 8. Duplikat dan Near-duplicate

Exact duplicate check dilakukan berdasarkan `recording_id` (semua unique). Near-duplicate check berbasis amplitude signature:

- Recording pairs dengan amplitude mean dalam 0.5% satu sama lain (potential near-duplicate signal): **90**
  - `20261104T154719Z_bending_001` vs `20261104T154851Z_bending_007` (bending): diff=0.0620
  - `20261104T154719Z_bending_001` vs `20261104T154921Z_bending_009` (bending): diff=0.0380
  - `20261104T154750Z_bending_003` vs `20261104T154906Z_bending_008` (bending): diff=0.0220
  - `20261104T154750Z_bending_003` vs `20261104T155021Z_bending_001` (bending): diff=0.0630
  - `20261104T154805Z_bending_004` vs `20261104T154835Z_bending_006` (bending): diff=0.0650
  - `20261104T154805Z_bending_004` vs `20261104T154851Z_bending_007` (bending): diff=0.0610
  - `20261104T154835Z_bending_006` vs `20261104T155021Z_bending_001` (bending): diff=0.0540
  - `20261104T154851Z_bending_007` vs `20261104T154921Z_bending_009` (bending): diff=0.1000
  - `20261104T154906Z_bending_008` vs `20261104T155021Z_bending_001` (bending): diff=0.0850
  - `20261104T121450Z_empty_room_001` vs `20261104T121506Z_empty_room_002` (empty_room): diff=0.1070

  Catatan: Amplitude proximity bukan bukti near-duplicate recording — CSI bervariasi bahkan untuk gerakan identical. Ini hanya indikator untuk inspeksi lebih lanjut jika diperlukan.

---
*Laporan dihasilkan oleh run_audit.py — read-only analysis*
*Output files:*
- `recording_status.csv`: status per recording
- `anomaly_details.csv`: seluruh temuan anomali per recording
- `audit_report.md`: laporan ini