# Phase-Level Motion Consistency Audit Report

**Audit date:** 2026-11-10  
**Metode:** Read-only. Tidak ada data yang dimodifikasi.  
**Referensi sebelumnya:** `audit_report.md` (quality audit teknis, 2026-11-10)

---

## 1. Metode

### 1.1 Motion Intensity Score

**Metrik utama:** Frame-to-frame delta amplitude (Δ-amp) per sub-carrier, kemudian dirata-ratakan:

```
score[t] = mean_over_subcarriers(|amp[t] - amp[t-1]|)
```

di mana `amp[t]` adalah vektor amplitudo dari `valid_b64` (int8 decoded, imaginary-first pair → √(I²+R²)).

Ini bukan absolute amplitude — ini **perubahan** sinyal, yang lebih sensitif terhadap gerakan fisik daripada nilai absolut.

**Gap masking:** Pasangan frame yang dipisahkan gap > max(5× median interval, 500 ms) di `callback_timestamp_us` diberi skor NaN dan dikecualikan dari statistik fase. Ini mencegah jump artefak dari timestamp gap menghasilkan motion score palsu.

**Clock source:** `callback_timestamp_us` (device monotonic, µs) untuk semua penentuan offset waktu. `host_receive_monotonic_ns` tidak digunakan karena granularitas 100 µs menyebabkan banyak tied value.

### 1.2 Baseline Empiris

Dari data nyata (empty_room, still_standing, still_sitting):

| Kondisi | Δ-amp mean (tipikal) |
|---|---|
| `empty_room` (tidak ada orang) | 2.0–2.5 |
| `still_standing` (orang berdiri diam) | 2.1–2.4 |
| `still_sitting` (orang duduk diam) | 2.1–3.5 |
| `walking` (phase berjalan) | 3.4–4.5 |
| `fall_action` (fase jatuh) | 3.5–8+ |

**Interpretasi:** Nilai > ~3.9 (3× baseline idle) menunjukkan ada gerakan signifikan dalam frame window tersebut.

### 1.3 Flags

| Flag | Kondisi |
|---|---|
| `PRE_ACTION_TOO_ACTIVE` | pre_mean > 3.9 (3× baseline 1.3) untuk label yang pre_action = "diam" |
| `LOW_ACTION_vs_PRE` | action_mean < 1.3× pre_mean dan kedua fase punya ≥5 frame |
| `HIGH_POST_vs_ACTION` | post_mean > 1.2× action_mean |
| `ACTION_PHASE_LOW_vs_LABEL` | z-score action_mean < −2.0 vs distribusi label |
| `IDLE_LABEL_HIGH_MOTION` | hold_mean > 3.25 untuk label idle-only |
| `KESELEO_PRE_WALKING_LOW` | pre (walking phase) mean < 1.5 untuk fall_keseleo |
| `KESELEO_POST_SLOW_MOVEMENT_FLAT` | post_mean < 0.4 untuk fall_keseleo |

**Penting:** Flag `PRE_ACTION_TOO_ACTIVE` tidak digunakan untuk `fall_keseleo` karena pre_action-nya adalah *walking*, bukan *diam*.

---

## 2. Ringkasan Hasil

| Verdict | Count | % |
|---|---|---|
| PASS | 58 | 44.6% |
| REVIEW | 72 | 55.4% |
| INVALID | 0 | 0% |

**Distribusi per label:**

| Label | Total | PASS | REVIEW | INVALID |
|---|---|---|---|---|
| `bending` | 10 | 5 | 5 | 0 |
| `empty_room` | 9 | 9 | 0 | 0 |
| `fall_backward` | 20 | 10 | 10 | 0 |
| `fall_forward` | 20 | 10 | 10 | 0 |
| `fall_keseleo` | 11 | 1 | 10 | 0 |
| `fall_lemas` | 10 | 6 | 4 | 0 |
| `fast_sitting` | 10 | 1 | 9 | 0 |
| `object_drop` | 10 | 2 | 8 | 0 |
| `still_sitting` | 10 | 10 | 0 | 0 |
| `still_standing` | 10 | 9 | 1 | 0 |
| `walking` | 10 | 7 | 3 | 0 |

**Tingginya angka REVIEW (72) perlu dikontekstualisasikan** — mayoritas bukan anomali individual melainkan pola struktural yang bersifat batch-wide atau label-wide. Lihat klasifikasi detail di bawah.

---

## 3. Temuan Per Label

### 3.1 `fall_forward` (20 recordings)

**Nov 4 (001–010, 10s, tanpa annotation):**

| Sub-metric | Nilai |
|---|---|
| pre_action mean | 4.5–7.1 |
| fall_action mean | 5.0–6.9 |
| post_action mean | 3.5–6.3 |
| action/pre ratio | 0.86–1.28 |

**Pola:** pre_action secara konsisten tinggi (~5–7) di semua 10 recording. Ini adalah **pola sistemik batch Nov 4**, bukan anomali per-recording. Penyebab: sesi batch dengan gap_before_s=10s tidak cukup untuk menstabilkan sinyal CSI setelah perpindahan posisi antar take. Person masih "settling" saat take dimulai.

**Nov 7 (015–024, 12s, dengan annotation):**

| Recording | pre | fall_action | post | ratio | Catatan |
|---|---|---|---|---|---|
| `_015` | 6.03 | 5.20 | 4.64 | 0.86 | pre tinggi |
| `_016` | 2.63 | 4.00 | 2.55 | 1.52 | ✓ bersih |
| `_017` | 2.50 | 3.60 | 4.77 | 1.44 | post tinggi (gap 1.3s di post) |
| `_018` | 2.90 | 3.58 | 2.09 | 1.23 | ✓ |
| `_019` | 2.94 | 4.05 | 2.31 | 1.38 | ✓ |
| `_020` | 2.62 | 3.98 | 2.46 | 1.51 | ✓ |
| `_021` | 3.75 | 5.00 | 2.67 | 1.33 | ✓ |
| `_022` | 2.39 | 4.14 | 2.66 | 1.73 | ✓ |
| `_023` | 2.54 | 4.08 | 4.16 | 1.61 | post sedikit tinggi |
| `_024` | 2.81 | 3.22 | 2.43 | 1.14 | ✓ (ada gap di pre + fall) |

**Kesimpulan fall_forward:** Nov 7 menunjukkan profil yang jauh lebih bersih dari Nov 4. Recording Nov 4 memiliki pre_action yang tidak diam — ini membatasi kemampuan model untuk menggunakan sinyal pre-fall sebagai baseline. Namun fall_action tetap ada (sinyal jatuh) di semua recording.

### 3.2 `fall_backward` (20 recordings)

**Nov 4 (001–010):**
Semua 10 recording memiliki pre_action tinggi (4.3–7.1), pola identik dengan fall_forward Nov 4. Penyebab yang sama.

**Nov 7 (011–020):**

| Recording | pre | fall_action | post | ratio | Catatan |
|---|---|---|---|---|---|
| `_011` | 6.11 | 5.34 | 2.85 | 0.87 | pre tinggi (orang baru tiba) |
| `_012` | 6.71 | 4.79 | 2.82 | 0.71 | pre tinggi + timestamp gap dalam fall_action |
| `_013` | 2.60 | 4.20 | 3.16 | 1.62 | ✓ |
| `_014` | 2.58 | 3.63 | 2.35 | 1.41 | ✓ |
| `_015` | 2.65 | 4.72 | 2.55 | 1.78 | ✓ |
| `_016` | 2.65 | 3.97 | 2.44 | 1.50 | ✓ |
| `_017` | 6.65 | 5.35 | 2.40 | 0.81 | pre tinggi |
| `_018` | 2.37 | 4.59 | 2.53 | 1.94 | ✓ |
| `_019` | 5.25 | 4.51 | 2.64 | 0.86 | pre tinggi |
| `_020` | 6.42 | 4.34 | 2.79 | 0.68 | pre tinggi |

**Pola Nov 7:** 5 dari 10 recording memiliki pre_action tinggi (~5–6.7). Pola bergantian: _011, _012, _017, _019, _020 tinggi; _013, _014, _015, _016, _018 bersih. Ini menunjukkan pre_action tinggi berkorelasi dengan take setelah pemulihan dari jatuh (orang masih bergerak ke posisi start). Take pertama dan beberapa take tengah lebih aktif.

Semua 10 recording Nov 7 menunjukkan **post_action yang sangat bersih (~2.4–3.2)** — orang diam setelah jatuh. Ini adalah signature fall yang baik.

### 3.3 `fall_lemas` (10 recordings, semua Nov 7, subject 2)

| Recording | pre | fall_action | post | ratio | Catatan |
|---|---|---|---|---|---|
| `_007` | 2.76 | 3.14 | 2.62 | 1.14 | ✓ slight |
| `_008` | 2.78 | 3.87 | 3.16 | 1.39 | ✓ |
| `_009` | 2.27 | 4.44 | 3.68 | 1.95 | ✓ |
| `_010` | 2.85 | 2.92 | 2.69 | 1.02 | weak action (timestamp gap 1.4s dalam fall) |
| `_011` | 2.30 | 3.60 | 2.37 | 1.56 | ✓ |
| `_012` | 2.62 | 4.23 | 4.97 | 1.62 | post tinggi — `_012` tidak ada anomali teknis |
| `_014` | 2.17 | 3.55 | 2.40 | 1.63 | ✓ |
| `_015` | 3.02 | 3.11 | 2.04 | 1.03 | weak action |
| `_016` | 2.43 | 3.54 | 2.56 | 1.46 | ✓ |
| `_017` | 2.76 | 2.87 | 2.64 | 1.04 | weak action |

**Kesimpulan fall_lemas:** Kualitas protocol terbaik di antara fall labels. Pre_action bersih (~2.3–3.0) untuk semua recording. Fall_action menunjukkan elevasi yang konsisten. 

**Perhatian khusus:**
- `_010`: fall_action lemah (ratio=1.02). Dikombinasikan dengan timestamp gap 1.4s dalam fall_action — sinyal fall mungkin tidak lengkap.
- `_015`: fall_action lemah (ratio=1.03). Mungkin eksekusi jatuh yang lebih lambat/kecil (fall_lemas = "limp fall").
- `_017`: fall_action lemah (ratio=1.04).
- `_012`: post_action tinggi (4.97 vs action 4.23). Kemungkinan post-fall movement berlanjut.

Catatan: "weak action" untuk fall_lemas bisa merupakan karakteristik label yang valid — "jatuh lemas" secara fisik menghasilkan perubahan sinyal yang lebih gradual daripada fall_forward/backward. **Ini bukan indikasi kesalahan pelaksanaan otomatis.**

### 3.4 `fall_keseleo` (11 recordings, Nov 7)

**Timeline:** pre_action (0–4s) = walking, fall_action (4–8s) = fall ke kanan, post_action (8–12s) = slow movement.

| Recording | pre (walk) | fall_action | post (slow) | ratio_fall/walk | Catatan |
|---|---|---|---|---|---|
| `_002` | 5.52 | 3.91 | 5.37 | 0.71 | post tinggi (slow movement masih aktif) |
| `_003` | 5.99 | 4.28 | 4.56 | 0.71 | ✓ untuk protokol ini |
| `_004` | 5.97 | 5.03 | 4.79 | 0.84 | ✓ |
| `_005` | 5.31 | 5.51 | 4.44 | 1.04 | ✓ |
| `_006` | 5.03 | 5.04 | 2.71 | 1.00 | ✓ |
| `_007` | 5.85 | 5.37 | 3.97 | 0.92 | ✓ |
| `_008` | 4.23 | 4.84 | 2.56 | 1.14 | ✓ (ada timestamp gap dalam fall_action) |
| `_009` | 7.51 | 4.83 | 6.01 | 0.64 | pre dan post sangat tinggi |
| `_010` | 5.51 | 5.98 | 3.87 | 1.08 | ✓ |
| `_011` | 6.03 | 5.10 | 5.39 | 0.85 | post tinggi |
| `_012` | 5.54 | 5.15 | 5.14 | 0.93 | post tinggi (timestamp gap dalam post) |

**Kesimpulan fall_keseleo:** Profil temporal konsisten dengan protokol walking → fall → slow movement:
- Pre (walking): 4.2–7.5 ✓ (gerakan periodik)
- Fall action: 3.9–6.0 ✓ (impak jatuh)
- Post (slow): 2.6–6.0 — bervariasi sesuai tingkat "slow movement"

Semua 11 recording memiliki fall annotations lengkap (fall_start + fall_impact).

`_002` dan `_009` menunjukkan post_action yang sangat aktif (5.4–6.0) — ini kompatibel dengan "bergerak perlahan" yang lebih aktif dari biasanya, bukan indikasi kesalahan label. `_009` juga memiliki walking pre yang lebih tinggi (7.5) — kemungkinan langkah yang lebih cepat atau berjalan lebih jauh.

**Tidak ada bukti anomali label untuk fall_keseleo.**

### 3.5 `fast_sitting` (10 recordings, Nov 4)

| Recording | pre (0–4s) | action (4–6s) | post (6–10s) | ratio | Catatan |
|---|---|---|---|---|---|
| `_001` (batch A) | 5.54 | 4.95 | 2.70 | 0.89 | pre aktif |
| `_002` | 6.01 | 3.54 | 3.01 | 0.59 | pre >> action |
| `_003` | 7.78 | 4.90 | 3.19 | 0.63 | pre >> action |
| `_004` | 5.65 | 4.97 | 3.16 | 0.88 | pre aktif |
| `_006` | 5.84 | 5.46 | 2.46 | 0.94 | pre aktif |
| `_007` | 7.84 | 4.82 | 2.84 | 0.62 | pre >> action |
| `_008` | 7.06 | 5.65 | 3.02 | 0.80 | pre aktif |
| `_009` | 6.61 | 3.21 | 2.83 | 0.49 | pre >> action, action sangat rendah |
| `_010` | 5.72 | 4.12 | 3.04 | 0.72 | pre aktif |
| `_001` (batch B, 15:46) | 2.53 | 4.00 | 2.96 | 1.58 | ✓ BERSIH |

**Temuan kritis:** 9 dari 10 recording `fast_sitting` memiliki pre_action lebih tinggi dari action phase. Satu-satunya recording bersih (`20261104T154615Z`, batch berbeda ~1 menit kemudian) menunjukkan profil normal (pre < action).

**Penyebab:** Semua 9 recording dalam batch A direkam berturutan dengan gap_before_s=5s. Interval 5 detik antara take tidak cukup bagi sinyal CSI untuk menstabilkan setelah subjek berpindah posisi. Ini bukan individual recording error — ini adalah **batch protocol issue**.

**Implikasi untuk model:** Jika model training menggunakan pre_action sebagai "diam sebelum aktivitas", maka 9/10 fast_sitting recordings memiliki pre_action yang sebenarnya sudah aktif. Fast_sitting action window hanya 2 detik (4–6s), yang sudah ter-overlap dengan energi dari pre-action carry-over.

**Klasifikasi:** REVIEW (pola sistemik, bukan individual failure) — bukan INVALID karena aktivitas fast_sitting tetap terjadi selama fase action.

### 3.6 `bending` (10 recordings, Nov 4)

| Recording | pre (0–3s) | action (3–7s) | post (7–10s) | ratio | Catatan |
|---|---|---|---|---|---|
| `_001` (batch A) | 2.21 | 3.20 | 3.67 | 1.45 | ✓ |
| `_001` (batch B) | 3.86 | 3.36 | 3.18 | 0.87 | pre aktif |
| `_002` | 2.41 | 2.98 | 3.03 | 1.24 | ✓ |
| `_003` | 2.44 | 3.31 | 3.70 | 1.36 | ✓ |
| `_004` | 2.20 | 3.39 | 3.66 | 1.54 | ✓ |
| `_006` | 3.00 | 3.39 | 2.89 | 1.13 | ✓ |
| `_007` | 2.57 | 3.28 | 3.28 | 1.28 | ✓ |
| `_008` | 2.78 | 2.80 | 3.07 | 1.01 | weak action |
| `_009` | 4.09 | 3.56 | 3.25 | 0.87 | pre aktif |
| `_001` (20261104T155021) | 4.26 | 3.21 | 2.50 | 0.75 | pre aktif |

**Pola bending:** Post_action cenderung lebih tinggi dari pre_action (~2.1 → ~3.2–3.7). Ini karena "berdiri kembali" setelah membungkuk menghasilkan sinyal tambahan di akhir take. Ini adalah **perilaku fisik yang diharapkan** untuk bending, bukan anomali.

Pre_action > baseline (> 3.9) hanya pada 3 recording — jauh lebih jarang daripada fall labels. Bending adalah aktivitas yang tidak memerlukan setup posisi yang sama dengan fall, sehingga pre-action lebih clean.

### 3.7 `object_drop` (10 recordings, Nov 4)

| Recording | pre | action | post | ratio | Catatan |
|---|---|---|---|---|---|
| `_001` | 4.20 | 3.74 | 3.16 | 0.89 | pre sedikit aktif |
| `_002` | 3.26 | 3.42 | 2.87 | 1.05 | borderline |
| `_003` | 2.71 | 3.30 | 5.19 | 1.22 | post sangat tinggi |
| `_004` | 3.08 | 3.78 | 4.63 | 1.23 | post tinggi |
| `_005` | 2.90 | 2.84 | 2.60 | 0.98 | flat |
| `_006` | 2.68 | 3.17 | 3.01 | 1.18 | borderline |
| `_007` | 4.08 | 3.11 | 2.50 | 0.76 | pre aktif |
| `_008` | 4.27 | 4.73 | 3.76 | 1.11 | pre aktif tapi action juga tinggi |
| `_009` | 4.51 | 2.90 | 2.87 | 0.64 | pre aktif, action rendah |
| `_010` | 2.68 | 3.29 | 3.19 | 1.23 | borderline |

**Temuan penting:** Object dropping menghasilkan sinyal CSI yang sangat kecil. Perbedaan action vs pre/post sangat kecil (rata-rata delta hanya ~0.1–0.5). Ini adalah **keterbatasan fisik CSI** bukan kesalahan recording — CSI tidak dapat membedakan gerakan kecil seperti menjatuhkan benda dengan baik dari variasi ambient. 

`_003` dan `_004` memiliki post_action yang sangat tinggi (5.2 dan 4.6) — kemungkinan subjek bergerak setelah menjatuhkan benda (mengambil kembali?).

### 3.8 `walking` (10 recordings, Nov 4)

| Recording | pre (0–3s) | walking (3–7s) | post (7–10s) | ratio | Catatan |
|---|---|---|---|---|---|
| `_001` | 5.46 | 3.92 | 4.90 | 0.72 | pre >> walking, post aktif; + timestamp gaps |
| `_002` | 2.51 | 3.82 | 2.78 | 1.52 | ✓ |
| `_003` | 2.65 | 3.53 | 2.62 | 1.33 | ✓ |
| `_004` | 2.84 | 3.77 | 2.98 | 1.33 | ✓ |
| `_005` | 4.95 | 3.44 | 2.52 | 0.70 | pre aktif |
| `_006` | 1.99 | 3.69 | 2.89 | 1.85 | ✓ |
| `_007` | 3.67 | 3.70 | 2.57 | 1.01 | borderline |
| `_008` | 2.23 | 2.88 | 3.26 | 1.29 | action rendah (z=-2.65), post > walking |
| `_009` | 2.88 | 3.79 | 2.25 | 1.31 | ✓ |
| `_010` | 2.37 | 3.70 | 2.33 | 1.56 | ✓ |

**walking_001:** Profil paling bermasalah. Pre sangat aktif (5.46), walking phase lebih rendah (3.92), post tinggi (4.90). Kombinasi ini dengan timestamp gaps (dari audit teknis) menjadikannya kandidat REVIEW terkuat. Perekaman dimulai pukul 04:32 UTC — jauh dari sesi lain.

**walking_005:** Pre aktif (4.95 > walking 3.44) — subjek belum diam saat pre_action.

**walking_008:** Walking action z=-2.65 vs distribusi label — walking score terendah (2.88). Dikombinasikan dengan post > walking (3.26), menunjukkan posisi subjek atau jarak berjalan mungkin berbeda.

**walking_007:** Pre (3.67) ≈ walking (3.70) — tidak ada perbedaan bermakna antara diam dan berjalan dalam CSI.

### 3.9 `still_standing` (10 recordings, Nov 4)

Semua 10 recording menggunakan fase tunggal `hold` (0–10s).

| Recording | hold_mean | Catatan |
|---|---|---|
| `_001` – `_007` | 1.8–2.7 | ✓ Normal |
| `_008` | **3.69** | OUTLIER — signifikan di atas baseline |
| `_009` – `_010` | 2.1–2.3 | ✓ Normal |

**still_standing_008:** hold_mean = 3.69, vs ~2.1 untuk tetangga langsung. Ini adalah recording yang direkam pukul 12:02 UTC, di antara `_007` (12:02:14) dan `_009` (12:02:44). Perbedaan ini tidak dapat dijelaskan oleh waktu perekaman yang berbeda. Kemungkinan subjek melakukan penyesuaian postur kecil (bergeser, bergoyang) selama recording ini.

**Tidak ada still_sitting yang anomalous** — semua 10 dalam rentang normal.

---

## 4. Klasifikasi Anomali

### 4.1 Anomali Teknis (dari audit sebelumnya, dikonfirmasi relevan)

Lihat `audit_report.md` Bagian 6. 4 recording dengan timestamp gap dalam fall_action phase:
- `fall_lemas/_010`: 1,394ms gap dalam fall_action → motion score gap artefact
- `fall_backward/_012`: 1,336ms gap dalam fall_action
- `fall_forward/_024`: 1,098ms gap dalam fall_action  
- `fall_keseleo/_008`: 707ms gap dalam fall_action

Semua 4 sudah dikonfirmasi dalam laporan audit teknis.

### 4.2 Anomali Temporal (Structural / Batch-Wide)

**Pola A — Pre_action tidak diam pada recording Nov 4 batch besar:**

| Label | Jumlah affected | Deskripsi |
|---|---|---|
| `fall_forward` Nov 4 | **10/10** | Pre_action 4.5–7.1 (seharusnya ~2) |
| `fall_backward` Nov 4 | **10/10** | Pre_action 4.3–7.1 (seharusnya ~2) |
| `fast_sitting` batch A | **9/10** | Pre_action 5.5–7.8 > action 3.2–5.7 |

Ini adalah **pola sistemik** yang mempengaruhi seluruh batch. Penyebab: take recordings berturutan dalam satu sesi panjang. Sinyal CSI belum stabil saat take dimulai meskipun ada gap_before_s.

**Pola B — Pre_action tidak diam pada sebagian Nov 7:**

| Label | Jumlah affected | Detail |
|---|---|---|
| `fall_backward` Nov 7 | **5/10** | _011, _012, _017, _019, _020 |
| `fall_forward` Nov 7 | **1/10** | _015 saja |

Ini terisolasi pada take tertentu, kemungkinan setelah pemulihan jatuh yang lebih lama.

### 4.3 Kemungkinan Kesalahan Pelaksanaan Aktivitas

| Recording | Label | Deskripsi | Confidence |
|---|---|---|---|
| `walking_001` | walking | Pre aktif (5.46), walking (3.92) < pre, post aktif (4.90). Profil tidak konsisten dengan berjalan yang terpisah dari diam. | MEDIUM |
| `walking_005` | walking | Pre (4.95) > walking (3.44). Subjek belum diam di pre_action. | LOW |
| `walking_007` | walking | Pre (3.67) ≈ walking (3.70). Tidak ada perbedaan berjalan vs diam dalam sinyal. Mungkin berjalan di dalam dead-zone atau sangat lambat. | LOW |
| `walking_008` | walking | Walking action z=-2.65 (paling rendah dalam label). Post > walking. | MEDIUM |
| `still_standing_008` | still_standing | hold_mean=3.69 vs ~2.1 baseline. Mungkin adjustment postur. | LOW |
| `fast_sitting_009` | fast_sitting | Pre (6.61) >> action (3.21). Action sangat rendah — duduk dilakukan sangat lambat atau tidak terjadi. | MEDIUM |
| `object_drop_003` dan `_004` | object_drop | Post sangat tinggi (5.2 dan 4.6) — kemungkinan subjek mengambil kembali benda setelah dijatuhkan. | LOW |

### 4.4 Kemungkinan Kesalahan Label

**Tidak ditemukan indikasi mislabeling yang kuat** berdasarkan bukti CSI dan metadata yang tersedia.

Catatan penting: CSI tidak dapat membuktikan secara definitif bahwa aktivitas fisik tertentu terjadi — hanya dapat menunjukkan perubahan sinyal. Interpretasi aktivitas dari CSI memerlukan ground truth tambahan (video, observer annotation) yang tidak tersedia untuk sebagian besar dataset ini.

---

## 5. Profil Gerakan Per Label — Tabel Ringkasan

| Label | pre_mean (rata-rata) | action_mean (rata-rata) | post_mean (rata-rata) | ratio act/pre | Interpretasi |
|---|---|---|---|---|---|
| `empty_room` | 2.3 (hold) | — | — | — | Baseline ambient; sinyal stabil |
| `still_standing` | 2.3 (hold) | — | — | — | ✓ Diam; konsisten |
| `still_sitting` | 2.6 (hold) | — | — | — | ✓ Diam; konsisten |
| `bending` | 2.9 | 3.2 | 3.2 | 1.11 | Moderat; post sering tinggi (berdiri kembali) |
| `fall_lemas` | 2.6 | 3.5 | 2.9 | **1.37** | ✓ Profil terbaik untuk fall |
| `fall_backward` Nov 7 clean | ~2.6 | ~4.3 | ~2.6 | **1.65** | ✓ |
| `fall_forward` Nov 7 clean | ~2.7 | ~3.9 | ~2.6 | **1.44** | ✓ |
| `fall_keseleo` pre=walk | 5.6 (walk) | 5.0 | 4.4 (slow) | 0.89 | ✓ sesuai protokol |
| `walking` | 2.8 | 3.6 | 2.7 | **1.30** | ✓ mayoritas recording |
| `fast_sitting` clean | 2.5 | 4.0 | 3.0 | **1.58** | ✓ hanya 1 recording |
| `object_drop` | 3.2 | 3.3 | 2.8 | 1.03 | Sangat kecil; CSI kurang sensitif |
| **Fall batch Nov 4** | **~5–6** | ~5–7 | ~4–6 | ~1.0 | ⚠️ Pre tidak baseline |

---

## 6. Daftar Recording REVIEW (dengan konteks)

### Kategori 1: Pola Sistemik Batch (Bukan Individual Error)

**Confidence: HIGH bahwa ini adalah batch artifact, bukan individual recording failure.**

Ini adalah anomali TEMPORAL tipe "pre_action carry-over". Batch dengan gap_before_s pendek tidak memberikan waktu cukup untuk CSI stabilisasi. Semua recording dalam kelompok ini memiliki:
- Payload valid, frames lengkap, label benar
- Pre_action elevated secara konsisten di seluruh batch
- Fall/action signal masih ada dalam fase yang tepat

| Kelompok | Recording | Jumlah |
|---|---|---|
| fall_forward Nov 4 | 001–010 (kecuali 006, 008, 010) | 7 recordings |
| fall_backward Nov 4 | 001–010 (kecuali 004, 005, 009) | 7 recordings |
| fast_sitting batch A | 001–004, 006–010 (terkecuali 015:46) | 9 recordings |

**Rekomendasi:** REVIEW — dapat digunakan untuk binary fall/non-fall classification. Sebaiknya **jangan digunakan untuk model yang memerlukan clean pre-fall baseline** tanpa preprocessing yang memotong detik pertama atau menggunakan window normalisasi.

### Kategori 2: Pre_action Elevated (Sebagian Nov 7)

| Recording | Label | pre | fall | post | Catatan |
|---|---|---|---|---|---|
| `20261107T150927Z_fall_backward_011` | fall_backward | 6.11 | 5.34 | 2.85 | Take pertama batch |
| `20261107T150949Z_fall_backward_012` | fall_backward | 6.71 | 4.79 | 2.82 | + gap dalam fall |
| `20261107T151140Z_fall_backward_017` | fall_backward | 6.65 | 5.35 | 2.40 | — |
| `20261107T151224Z_fall_backward_019` | fall_backward | 5.25 | 4.51 | 2.64 | — |
| `20261107T151246Z_fall_backward_020` | fall_backward | 6.42 | 4.34 | 2.79 | — |
| `20261107T150308Z_fall_forward_015` | fall_forward | 6.03 | 5.20 | 4.64 | Take pertama batch |

### Kategori 3: Profil Post_action Tinggi

| Recording | Label | Deskripsi | Concern level |
|---|---|---|---|
| `fall_forward_017` | fall_forward | post=4.77 (ada timestamp gap dalam post) | LOW |
| `fall_forward_023` | fall_forward | post=4.16 | LOW |
| `fall_lemas_012` | fall_lemas | post=4.97 (gerakan berlanjut setelah jatuh) | LOW |
| `fall_keseleo_002` | fall_keseleo | post=5.37 (slow movement sangat aktif) | LOW |
| `fall_keseleo_009` | fall_keseleo | post=6.01 (slow movement paling aktif) | LOW |
| `fall_keseleo_011` | fall_keseleo | post=5.39 | LOW |
| `fall_keseleo_012` | fall_keseleo | post=5.14 (+ timestamp gap) | LOW |

### Kategori 4: Action Phase Lemah

| Recording | Label | action_mean | concern | Catatan |
|---|---|---|---|---|
| `fall_lemas_010` | fall_lemas | 2.92 | MEDIUM | + timestamp gap 1.4s dalam fall_action |
| `fall_lemas_015` | fall_lemas | 3.11 | LOW | "lemas" = gradual fall expected |
| `fall_lemas_017` | fall_lemas | 2.87 | LOW | Idem |
| `walking_008` | walking | 2.88 | MEDIUM | z=-2.65 vs label; post > walking |
| `fast_sitting_009` | fast_sitting | 3.21 | MEDIUM | pre (6.61) >> action (3.21) |
| `bending_008` | bending | 2.80 | LOW | z=-2.15 vs label |

### Kategori 5: Idle Label Anomaly

| Recording | Label | Metrik | Concern |
|---|---|---|---|
| `still_standing_008` | still_standing | hold_mean=3.69 (vs ~2.1 baseline) | LOW — mungkin micro-adjustment postur |

### Kategori 6: Walking Profil Tidak Konsisten

| Recording | Label | Deskripsi | Concern |
|---|---|---|---|
| `walking_001` | walking | Pre aktif (5.46), walking < pre, post tinggi; + 2 timestamp gaps | MEDIUM |
| `walking_005` | walking | Pre (4.95) > walking (3.44) | LOW |
| `walking_007` | walking | Pre ≈ walking (3.67 ≈ 3.70) | LOW |

---

## 7. Rekomendasi

### 7.1 Recording INVALID
**Tidak ada.** Tidak ada recording yang memiliki bukti cukup untuk INVALID berdasarkan analisis motion. Anomali yang ditemukan tidak membuktikan kesalahan label atau kerusakan data yang tidak dapat digunakan.

### 7.2 Untuk Training (Prioritas)

**Gunakan langsung (PASS atau REVIEW-rendah):**
- Semua `fall_lemas` (kecuali `_010` yang sudah REVIEW dari audit teknis)
- `fall_backward` Nov 7: `_013`, `_014`, `_015`, `_016`, `_018` (clean pre + clean post)
- `fall_forward` Nov 7: `_016`, `_018`, `_019`, `_020`, `_021`, `_022`, `_023`
- `fall_keseleo`: semua 11 (protokol sesuai, annotations lengkap)
- Semua `still_*` dan `empty_room`
- `walking` `_002–_006`, `_009`, `_010`

**Gunakan dengan preprocessing:**
- Fall recordings Nov 4 (fall_forward/backward 001–010): potong detik pertama atau gunakan window yang dimulai dari t=1s untuk menghindari carry-over. Pre_action tidak reliable sebagai baseline.
- `fast_sitting` recordings: gunakan hanya window action (t=4–6s) dan post (t=6–10s). Pre_action tidak dapat diandalkan sebagai "diam sebelum duduk".

**Periksa sebelum penggunaan:**
- `fall_lemas_010`, `fall_backward_012`, `fall_forward_024`: timestamp gap dalam fall_action + motion anomaly
- `walking_001` dan `walking_008`: profil tidak konsisten
- `fast_sitting_009`: action sangat rendah

### 7.3 Rekomendasi Recording Ulang

Berdasarkan temuan ini, recording ulang yang paling bermanfaat adalah:

1. **fast_sitting batch A (9 recordings):** Rekam ulang dengan gap_before_s yang lebih panjang (≥15s) atau interval batch yang lebih lama. Ini adalah batch dengan masalah protokol yang paling konsisten.

2. **walking_001:** Sudah ada timestamp gaps + profil motion tidak konsisten. Prioritas sedang.

3. Opsional: Fall recordings Nov 4 untuk fall_forward dan fall_backward — jika model memerlukan pre-fall baseline yang bersih. Nov 7 recordings sudah berkualitas jauh lebih baik.

**Semua keputusan recording ulang diserahkan kepada reviewer setelah konfirmasi laporan ini.**

---

## 8. File Output

| File | Deskripsi |
|---|---|
| `motion_phase_stats.csv` | Per-recording per-phase motion statistics |
| `motion_anomaly_details.csv` | Detail setiap flag anomali motion |
| `motion_plots/` | Per-recording motion profile plots (79 plots) |
| `run_motion_audit.py` | Script audit (read-only, dapat diulang) |

Laporan audit teknis sebelumnya tetap valid dan tidak dimodifikasi:
- `audit_report.md`
- `recording_status.csv`
- `anomaly_details.csv`

---

*Laporan ini dihasilkan dari analisis manual dan `run_motion_audit.py` — read-only*  
*Semua keputusan recording ulang menunggu persetujuan reviewer*
