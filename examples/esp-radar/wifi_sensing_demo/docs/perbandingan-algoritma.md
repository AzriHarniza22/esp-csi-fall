# MANDAT EKSPERIMEN: COMPREHENSIVE ACTIVITY MULTICLASS, BINARY, AND HARD-CASE CLASSIFIER BENCHMARK

## 1. Tujuan utama

Jalankan training dan perbandingan komprehensif terhadap kelima algoritma classifier yang tersedia di repository menggunakan dataset CSI aktual.

Kelima algoritma:

1. `nearest-centroid`
2. `logistic-regression`
3. `linear-svm`
4. `decision-tree`
5. `random-forest`

Benchmark wajib mencakup tiga eksperimen utama:

- **Experiment A:** multiclass classification — setiap activity label menjadi kelas tersendiri.
- **Experiment B:** binary classification — fall vs non-fall.
- **Experiment C:** hard-case classification — `fall_keseleo` vs `walking`.

Tujuan akhirnya adalah mengetahui:
- Kemampuan aktual setiap algoritma pada kelima belas? Tidak: seluruh 11 activity label yang tersedia.
- Kelas yang paling mudah dan paling sulit dikenali.
- Pola confusion antaraktivitas.
- Algoritma terbaik untuk multiclass dan binary.
- Apakah fitur snapshot 16-band mampu membedakan manner-fall.
- Apakah fitur sekarang mempunyai keterbatasan yang memerlukan temporal-shape dan settling.
- Algoritma paling realistis untuk implementasi ESP32-WROOM-32.

**Jalankan training dan evaluasi aktual. Jangan hanya menghasilkan rancangan penelitian.**

Semua hasil harus berasal dari eksperimen yang dapat direproduksi.

---

# BAGIAN I — KONTRAK DATA DAN IMPLEMENTASI

## 2. Gunakan hasil audit sebagai titik awal

Audit read-only sebelumnya mencatat:

- 130 take lengkap.
- 37.610 baris frame.
- 3.088 window berdasarkan window 24 frame, stride 12.
- 11 activity label.
- Seluruh frame mempunyai `lltf_len=102`.
- Tidak ada frame yang ditolak oleh filter layout pada audit sebelumnya.
- 41 take fall dan 89 take lainnya? Koreksi: 61 take fall dan 69 take non-fall.
- 41 take fall baru mempunyai observer `fall_start`.
- Seluruh 130 take memiliki timeline.

Hitung ulang angka tersebut saat membuat dataset snapshot. Apabila ada perbedaan, gunakan hasil pemeriksaan aktual dan jelaskan penyebabnya.

Jangan menggunakan hasil penelitian lama sebagai pengganti audit dataset.

## 3. Sumber label yang kanonik

Gunakan:

`meta.activity_label`

sebagai satu-satunya sumber label activity untuk eksperimen ini.

Trainer aktual juga menggunakan `activity_label` dengan fallback `meta.label`.

Jangan menurunkan label dari:
- `recording_id`.
- Nama folder.
- `events.segments[].label`.
- Teks instruksi timeline.

Field lain hanya digunakan untuk audit konsistensi dan metadata tambahan.

Perhatian:
- `fall_keseleo` masih mempunyai token legacy `fall_right` dalam recording ID, event segment, atau instruksi lama.
- `fall_lemas` masih mempunyai token legacy `fall_left`.

Hal tersebut tidak otomatis merupakan konflik training karena trainer menggunakan `activity_label`.

Laporkan konflik historis tersebut, tetapi jangan mengubah metadata atau raw CSI.

Untuk preprocessing layout, periksa kembali bahwa setiap frame yang digunakan memiliki kombinasi:
- `lltf_len=102`
- `first_word_invalid=true`

Jangan menganggap panjang payload yang benar otomatis menjamin decoding benar. Pertahankan decoder kanonik yang digunakan trainer dan laporkan inkonsistensi validasi layout yang ditemukan pada dua jalur reader.

## 4. Snapshot dataset dan reproduksibilitas

Sebelum training, buat manifest dataset:

- `recording_id`
- `activity_label`
- `subject_id`
- `session_id`
- `batch_id`
- tanggal recording
- jumlah frame
- jumlah window
- durasi aktual
- hash SHA-256 `.frames.csv`
- hash SHA-256 `.meta.json`

Simpan manifest dalam direktori benchmark.

Snapshot ini menjadi identitas dataset untuk seluruh eksperimen.

Training harus membaca snapshot yang sama. Jangan biarkan recording baru atau perubahan metadata masuk diam-diam ketika eksperimen berlangsung.

## 5. Fitur yang digunakan

Gunakan feature extractor canonical yang sekarang ada:

- 16-band perubahan log-amplitudo.
- Window 24 frame.
- Stride 12 frame.
- LLTF 51 pasangan kompleks untuk layout data aktual.
- Formula dan preprocessing sesuai implementasi trainer.

Jangan menambahkan fitur baru.

Jangan mengubah:
- `classifier_models.py`
- `train_activity_model.py`
- `dataset_io.py`
- Canonical feature extractor
- Firmware
- `activity_model_data.h`

Audit aktual menyatakan fitur adalah snapshot perubahan log-amplitudo 16 band, bukan baseline-relative dan bukan temporal-shape.

Karena itu, jangan mengklaim eksperimen ini sudah menguji fitur settle atau dua-tahap.

### Timestamp dan durasi window

Untuk Experiment A dan B, pertahankan window generator indeks-frame kanonik trainer. Jangan mengubah windowing menjadi timestamp-aware karena itu akan mengubah baseline pipeline yang sedang diuji.

Tetap hitung dan laporkan durasi aktual serta inter-arrival time setiap window. Jangan mengasumsikan 24 frame selalu mempunyai durasi waktu yang identik.

Jangan menetapkan batas maximum gap baru dalam benchmark ini karena `MAX_FRAME_GAP_S` masih berstatus PENDING di DATA_CONTRACT.

Window dengan payload rusak atau struktur yang tidak valid harus ditolak dengan pencatatan eksplisit. Jangan membuat frame CSI palsu atau menginterpolasi data.

## 6. Karakteristik kelima algoritma yang harus dipertahankan

Gunakan implementasi dan hyperparameter default aktual dari `classifier_models.py`.

Audit sebelumnya menemukan:

| Algoritma | Konfigurasi aktual |
|---|---|
| Nearest Centroid | Euclidean squared distance, fitur terstandar |
| Logistic Regression | Softmax multiclass, lr 0,12, L2 0,001, 700 epoch |
| Linear SVM | One-vs-rest hinge SGD, lr 0,08, decay 0,002, 500 epoch |
| Decision Tree | Gini, max depth 4, min leaf 2 |
| Random Forest | 9 pohon, depth 4, min leaf 2, max features 4 |

Seluruh algoritma:
- Menggunakan 16 fitur.
- Mendukung multiclass dan binary.
- Tidak mempunyai class weighting.
- Memakai standardisasi yang di-fit dari training data.
- Mendukung export C.

Gunakan konfigurasi default tanpa hyperparameter tuning dalam benchmark utama.

Sebut hasilnya sebagai:

`Fixed-defaults algorithm comparison`

Jangan mengklaim bahwa pemenang adalah algoritma terbaik secara universal atau sudah mencapai konfigurasi optimal.

Random seed harus tetap menggunakan implementasi aktual. Jangan mengubah konstanta seed atau melakukan modifikasi produksi.

### Score dan probability

Jangan menganggap semua `predict_scores` adalah probability.

Dokumentasikan semantik:
- Nearest Centroid: negative distance.
- Logistic Regression: raw logits.
- Linear SVM: decision margins.
- Decision Tree: vote count/class decision.
- Random Forest: vote count.

Jangan membandingkan nilai score mentah antaralgoritma seolah-olah mempunyai skala yang sama.

Jangan membuat calibration metric tanpa probabilitas yang benar-benar terkalibrasi.

---

# BAGIAN II — VALIDASI DAN SPLIT

## 7. Gunakan Leave-One-Take-Out

LOTO merupakan split utama ketiga eksperimen.

Aturannya:

- Satu take menjadi test.
- Semua window dari take tersebut menjadi test.
- Semua window dari take tersebut dikeluarkan dari training.
- Seluruh take lainnya menjadi training.
- Setiap take menjadi test tepat satu kali.
- Kelima algoritma menggunakan fold identik.

Jumlah fold:

| Eksperimen | Take | Fold |
|---|---:|---:|
| A Multiclass | 130 | 130 |
| B Binary | 130 | 130 |
| C Hard-case | 21 | 21 |

Gunakan isolated benchmark harness dengan mengimpor implementasi classifier dan feature extractor canonical.

Jangan mengubah trainer produksi hanya untuk menyediakan LOTO.

Seluruh preprocessing harus di-fit ulang pada training fold dan tidak boleh melihat test take.

### Penting: penggabungan OOF predictions

Untuk menghitung metrik keseluruhan, kumpulkan seluruh out-of-fold predictions.

Jangan menghitung macro-F1 atau balanced accuracy masing-masing LOTO fold lalu mengambil rata-ratanya secara naif.

Alasannya: test fold individual hanya berisi satu activity label pada eksperimen multiclass, atau satu kelas pada hard-case. Metrik kelas tidak dapat diinterpretasikan dengan benar pada satu fold semacam itu.

Lakukan:
- Pooled OOF window evaluation.
- OOF take-level evaluation.
- Per-class metrics dari gabungan seluruh OOF predictions.

### Dua jenis evaluasi take

Karena jumlah window setiap take berbeda, buat dua perspektif:

**Window-level**
- Setiap window menghasilkan satu prediksi.
- Laporkan pooled metrics.
- Berikan peringatan bahwa take dengan lebih banyak window mempunyai kontribusi lebih besar.

**Take-level**
- Gabungkan seluruh prediksi window dari take menggunakan majority vote.
- Satu take menghasilkan satu prediksi akhir.
- Jika terjadi seri, gunakan aturan tie-break deterministik berdasarkan urutan kelas yang ditentukan sebelumnya.
- Laporkan jumlah tie.

Jangan memperlakukan 3.088 window sebagai 3.088 kejadian independen.

## 8. Keterbatasan generalisasi

Audit menemukan:

- 89 take legacy tidak mempunyai `subject_id`.
- Hanya dua subject ID diketahui.
- Hanya satu `session_id` yang teridentifikasi.
- Walking, bending, dan kelas non-fall legacy tidak memiliki identitas subjek yang memadai.
- Fall lemas dan keseleo hanya mempunyai satu subjek masing-masing.

Konsekuensinya:

- LOTO adalah take-held-out evaluation, bukan subject-independent evaluation.
- Leave-One-Subject-Out tidak dapat dilakukan secara sah.
- Leave-One-Session-Out tidak dapat dilakukan secara sah.
- Jangan mengklaim generalisasi lintas subjek atau lintas sesi.

### Variasi recording date dan protokol

Fall forward/backward masing-masing mempunyai 20 take:
- 10 take lama dari 4 November 2026.
- 10 take baru dari 7 November 2026.

Fall forward/backward mencampur protokol 10 dan 12 detik.

Seluruh 69 take non-fall berasal dari dataset lama, sedangkan 41 take fall baru berasal dari 7 November.

Ini menciptakan potensi confounding antara label, hari recording, subjek, sesi, posisi, dan protokol.

Jangan menyembunyikan masalah ini.

Laporkan:
- Performa forward/backward pada kelompok recording lama.
- Performa forward/backward pada kelompok recording baru.
- Perbedaan performa menurut protokol.
- Hasil binary pada kelompok fall lama vs non-fall lama sebagai sensitivity analysis jika grouping aktual mendukungnya.

Jangan menyebut pemisahan berdasarkan tanggal sebagai leave-one-session-out kecuali metadata membuktikan sesi yang independen.

---

# BAGIAN III — EXPERIMENT A: MULTICLASS 11 ACTIVITY LABEL

## 9. Definisi kelas

Setiap `activity_label` menjadi kelas tersendiri.

Gunakan seluruh 11 kelas yang telah diverifikasi:

| Kelas | Jumlah take audit |
|---|---:|
| `fall_forward` | 20 |
| `fall_backward` | 20 |
| `fall_lemas` | 10 |
| `fall_keseleo` | 11 |
| `walking` | 10 |
| `bending` | 10 |
| `fast_sitting` | 10 |
| `object_drop` | 10 |
| `empty_room` | 9 |
| `still_standing` | 10 |
| `still_sitting` | 10 |

Verifikasi lagi jumlah aktual ketika membangun snapshot.

Urutan kelas harus ditetapkan sekali dan identik di semua fold dan algoritma:

```text
fall_forward
fall_backward
fall_lemas
fall_keseleo
walking
bending
fast_sitting
object_drop
empty_room
still_standing
still_sitting
```

### Labeling

Gunakan activity label per-take.

Seluruh window mewarisi label recording.

Contohnya, seluruh window dalam `fall_keseleo` menjadi kelas `fall_keseleo`, termasuk pre-action walking dan post-action slow movement.

Jelaskan bahwa ini merupakan:

`Whole-activity multiclass classification`

Bukan klasifikasi temporal phase dan bukan fall-event detection.

Jangan mengganti label berdasarkan perkiraan fase fisik.

### Evaluasi wajib

Untuk kelima algoritma:
- Accuracy.
- Balanced accuracy.
- Macro precision.
- Macro recall.
- Macro F1.
- Weighted F1.
- Per-class precision.
- Per-class recall.
- Per-class F1.
- Confusion matrix.
- Jumlah take benar dan salah per kelas.
- Window-level dan take-level results.

Analisis confusion secara rinci:

- `fall_keseleo` vs `walking`
- `fall_lemas` vs `fall_backward`
- `fall_forward` vs `fall_backward`
- `fast_sitting` vs `still_sitting`
- `object_drop` vs seluruh kelas fall
- `bending` vs `fall_forward`
- `fall_keseleo` vs seluruh kelas lain.

Laporkan kelas paling mudah dan paling sulit dikenali.

Jangan menyimpulkan kemampuan mengenali cara jatuh apabila model sebenarnya hanya membedakan konteks sesi atau baseline.

---

# BAGIAN IV — EXPERIMENT B: BINARY FALL VS NON-FALL

## 10. Definisi grouping

Latih ulang kelima algoritma dengan dua kelas native.

### FALL

```text
fall_forward
fall_backward
fall_lemas
fall_keseleo
```

Jumlah audit: 61 take, 1.526 window.

### NON_FALL

```text
walking
bending
fast_sitting
object_drop
empty_room
still_standing
still_sitting
```

Jumlah audit: 69 take, 1.562 window.

Gunakan `activity_label` yang telah diverifikasi.

Jangan hanya memetakan hasil prediksi multiclass menjadi binary. Model binary harus dilatih ulang menggunakan dua target tersebut.

### Evaluasi

Laporkan:

- Accuracy.
- Balanced accuracy.
- Precision.
- Fall recall/sensitivity.
- Specificity.
- Fall F1.
- Macro F1.
- False positive rate.
- False negative rate.
- Confusion matrix.
- Jumlah missed fall per manner.

Laporkan juga:
- Recall `fall_forward`.
- Recall `fall_backward`.
- Recall `fall_lemas`.
- Recall `fall_keseleo`.

Jalankan dua bentuk evaluasi:
1. Pooled OOF window-level.
2. OOF take-level majority vote.

### Pembanding binary hasil multiclass

Gunakan OOF predictions dari Experiment A yang dipetakan menjadi:

```text
fall_forward   → FALL
fall_backward  → FALL
fall_lemas     → FALL
fall_keseleo   → FALL

semua label non-fall → NON_FALL
```

Bandingkan dengan model native binary.

Tujuannya mengetahui apakah training langsung binary memberikan hasil berbeda dari multiclass kemudian dipetakan menjadi binary.

Kedua hasil harus menggunakan take dan fold yang sama.

### Keterbatasan yang wajib dilaporkan

Karena label diberikan pada level take, seluruh window dari take jatuh diberi target FALL, termasuk pre-action dan post-action.

Pada `fall_keseleo`, ini berarti window walking sebelum jatuh juga dilabeli FALL.

Pada `fall_forward`, `fall_backward`, dan `fall_lemas`, window diam sebelum jatuh juga dilabeli FALL.

Fitur snapshot absolut dapat membuat:
- Diam dalam take fall berlabel FALL.
- Diam dalam `still_sitting` atau `empty_room` berlabel NON_FALL.

Kondisi tersebut dapat membuat model mempelajari korelasi konteks protokol dan aktivitas, bukan kejadian jatuh.

Oleh sebab itu, sebut eksperimen ini:

`Legacy take-level binary classification baseline`

Bukan fall-event detector dan bukan klaim alarm runtime.

### Sensitivity analysis terhadap perbedaan tanggal

Karena semua non-fall merupakan take lama dan 41 fall merupakan take baru, lakukan analisis tambahan:

- Pisahkan hasil FALL lama dan FALL baru.
- Hitung false negative pada tiap kelompok.
- Laporkan apakah performa terutama ditopang kelompok fall yang direkam pada 7 November.
- Apabila 20 take fall forward/backward lama dapat diidentifikasi, buat sensitivity run khusus kelompok legacy tanggal 4 November dengan seluruh 69 take non-fall lama.

Sensitivity run tersebut merupakan subset, bukan pengganti eksperimen binary utama.

Jangan menyatakan bahwa sensitivity run menghilangkan seluruh confounding.

---

# BAGIAN V — EXPERIMENT C: HARD-CASE FALL_KESELEO VS WALKING

## 11. Pertanyaan

Apakah fitur snapshot 16-band yang sekarang dapat membedakan window aktivitas jatuh-keseleo dari walking normal?

Audit sebelumnya menemukan:

- 11 take `fall_keseleo`.
- 10 take `walking`.
- 61 window positif berdasarkan observer onset.
- 80 window negatif pada interval walking normal.

Angka tersebut harus dihitung ulang menggunakan metode window yang benar-benar identik dengan trainer.

## 12. Definisi data positif

Positive:

`fall_keseleo`

Gunakan primary observer reference:
`annotations.fall_start.timestamp_utc`

Jangan menggunakan `offset_s` secara langsung apabila masih terdapat perbedaan anchor terhadap frame CSI pertama.

Rekonstruksi waktu observer ke host monotonic menggunakan `clock_anchor`:

```text
observer_host_monotonic_ms =
    performance_now_ms
    + (observer_timestamp_utc_ms - date_now_ms)
```

Kemudian:

```text
observer_onset_s =
    (observer_host_monotonic_ns - first_frame_host_monotonic_ns)
    / 1e9
```

Gunakan ketelitian timestamp aktual.

Jangan mengoreksi waktu dengan konstanta reaction time.

Observer mark merupakan `observer-referenced onset`, bukan physical ground truth.

### Interval positif

Pilih window yang seluruh rentang frame-nya memenuhi:

```text
window_start_timestamp >= observer_onset_timestamp

AND

window_end_timestamp <= action_end_timestamp
```

Untuk `fall_keseleo`, `action_end` berasal dari boundary detik ke-8 pada timeline rekaman.

Window harus sepenuhnya berada di dalam interval tersebut.

## 13. Definisi data negatif

Negative:

`walking`

Gunakan interval normal walking dari timeline:

```text
action_start = 3 s
action_end = 7 s
```

Pilih window yang seluruh rentang frame-nya berada dalam interval aktivitas berjalan tersebut.

Jangan menggunakan pre-action atau post-action walking dari kelompok lain tanpa menjelaskan perbedaan protokol.

## 14. Pembentukan window hard-case

Ini penting:

**Jangan memotong frame CSI menjadi potongan baru kemudian membuat ulang stride dari awal potongan.**

Buat seluruh window menggunakan canonical grid trainer:
- Window 24 frame.
- Stride 12.
- Grid dimulai dari frame CSI pertama setiap take.

Setelah window terbentuk, gunakan timestamp frame pertama dan terakhir untuk memilih window yang seluruhnya berada dalam interval positif atau negatif.

Dengan demikian:
- Definisi fitur sama dengan canonical trainer.
- Window alignment konsisten dengan grid aslinya.
- Hanya pemilihan window yang berbasis timestamp.

Gunakan feature extractor canonical yang sudah ada. Jangan menulis ulang formula fitur dalam isolated harness jika fungsi canonical bisa diimpor.

Jika jumlah window berbeda dari audit sebelumnya (61 positif/80 negatif), laporkan perbedaan dan metode perhitungannya.

## 15. Evaluasi hard-case

Gunakan Leave-One-Take-Out:

- 11 positive takes.
- 10 negative takes.
- 21 folds.
- Seluruh window dari satu take ditahan bersama.

Kelima algoritma menggunakan fold yang identik.

Laporkan:
- Accuracy.
- Balanced accuracy.
- Precision.
- Recall.
- F1.
- Confusion matrix.
- Per-take results.
- Take-level majority vote.
- Variasi false positive dan false negative antar-take.

### Batas interpretasi yang wajib

Experiment C hanya mengukur:

`Observer-referenced fall-transition-window vs normal-walking-window classification`

Experiment C TIDAK mengukur:
- Kemampuan deteksi onset secara online.
- Event-level fall recall.
- Latency alarm.
- Kemampuan dua tahap transition→settle.
- Konfirmasi fallen_still.
- Perbedaan jatuh dengan walking→berhenti atau walking→berjalan lambat.

Alasannya: window positif berhenti pada action-end detik ke-8. Periode post-action 8–12 tidak termasuk dalam klasifikasi utama.

Jangan mengklaim bahwa Experiment C sudah memvalidasi temporal shape + settling.

### Analisis tambahan post-action

Boleh hitung statistik deskriptif fitur 16-band pada interval post-action 8–12 untuk 11 take keseleo.

Namun, jangan melakukan klasifikasi post-event terhadap walking normal seolah-olah tersedia kontrol walking→slow-movement yang setara.

Kontrol tersebut belum tersedia.

Laporkan sebagai analisis deskriptif terpisah.

---

# BAGIAN VI — ANALISIS PERFORMA DAN KOMPLEKSITAS

## 16. Perbandingan setiap algoritma

Buat analisis khusus untuk masing-masing algoritma.

### Nearest Centroid

Periksa:
- Jarak centroid antar kelas.
- Pasangan kelas dengan centroid paling dekat.
- Distribusi jarak test ke centroid.
- Kelas yang mempunyai overlap besar.
- Apakah rata-rata fitur cukup representatif untuk kelas tersebut.

### Logistic Regression

Periksa:
- Koefisien per kelas.
- Bias/intercept.
- Kontribusi fitur.
- Stabilitas koefisien antar-fold.
- Apakah 700 epoch mencapai konvergensi.
- Apakah terdapat indikasi underfitting.

Jangan menyebut nilai raw logits sebagai probability.

### Linear SVM

Periksa:
- Bobot model per kelas.
- Bias.
- Decision margin.
- Stabilitas bobot.
- Apakah 500 epoch dan learning-rate schedule memadai.
- Perbedaan hasil dengan Logistic Regression.

### Decision Tree

Periksa:
- Jumlah node.
- Jumlah leaf.
- Kedalaman aktual.
- Feature split.
- Struktur aturan keputusan.
- Konsistensi aturan antar-fold.
- Overfitting terhadap recording tertentu.

### Random Forest

Periksa:
- Jumlah pohon.
- Node dan leaf per pohon.
- Total node.
- Distribusi voting.
- Keragaman pohon.
- Feature importance hanya jika memang tersedia.
- Perbaikan dibandingkan Decision Tree.
- Stabilitas antar-fold.

Jangan mengarang informasi internal model apabila tidak tersedia dalam implementasi.

## 17. Feature analysis

Analisis distribusi 16 fitur untuk:
- Seluruh 11 kelas.
- Fall vs non-fall.
- Fall_keseleo vs walking.
- Still-to-fall vs walk-to-fall.

Laporkan:
- Mean.
- Standard deviation.
- Median.
- Minimum.
- Maximum.
- Distribusi per kelas.
- Korelasi antarfitur apabila relevan.

Identifikasi:
- Fitur dengan pemisahan paling jelas.
- Fitur dengan overlap terbesar.
- Fitur yang paling sering dipakai LR/SVM/tree/RF jika introspection tersedia.
- Perbedaan distribusi fitur antarsubjek atau protokol apabila data memungkinkan.

Jangan menyimpulkan kausalitas dari feature importance.

## 18. Deployment complexity

Gunakan model yang benar-benar dihasilkan pada setiap training fold.

Bandingkan:
- Parameter/bobot.
- Ukuran model.
- Node/leaf.
- Ukuran C header yang dihasilkan dalam direktori eksperimen.
- Operasi inference.
- Estimasi kebutuhan RAM/flash.
- Kompatibilitas exporter C.
- Kesesuaian dengan firmware ESP32 saat ini.

Laporkan median, p95, dan maksimum ukuran/kompleksitas antar-fold bila relevan.

Centroid dan model linear mungkin jauh lebih ringan daripada ensemble. Namun, jangan memilih pemenang deployment tanpa membandingkan ukuran aktual.

Jangan mengklaim latency inference di ESP32. Tidak ada flash atau benchmark perangkat dalam mandat ini.

Jangan overwrite:

`main/activity_model_data.h`

---

# BAGIAN VII — METRIK, INTERPRETASI, DAN PEMILIHAN

## 19. Metrik keseluruhan

Untuk A:
- Accuracy.
- Balanced accuracy.
- Macro precision.
- Macro recall.
- Macro F1.
- Weighted F1.
- Per-class F1.

Untuk B:
- Accuracy.
- Balanced accuracy.
- Fall precision.
- Fall recall.
- Specificity.
- Fall F1.
- Macro F1.
- FPR.
- FNR.
- Missed fall per manner.

Untuk C:
- Accuracy.
- Balanced accuracy.
- Precision.
- Recall.
- F1.
- False positive/negative per take.

Laporkan metrik window-level dan take-level secara terpisah.

Pooled window metric menggambarkan prediksi window. Take-level metric memberi bobot lebih merata kepada unit recording.

Jika membuat confidence interval:
- Bootstrap harus dilakukan pada unit take.
- Jangan bootstrap overlapping windows secara independen.
- Tegaskan bahwa CI tetap terbatas oleh jumlah take, subjek, dan sesi.

Jangan menggunakan AUC atau raw model score sebagai satu-satunya dasar ranking. Jika menghitung ROC-AUC, hitung secara terpisah per algoritma dan hanya apabila orientasi score serta maknanya benar-benar sesuai. Decision-tree vote yang diskrit harus dicatat sebagai score bertie tinggi.

## 20. Fixed defaults dan fairness

Kelima model memiliki hyperparameter default hardcoded dan tidak ada class weighting.

Karena itu:
- Tidak ada hyperparameter tuning.
- Tidak ada perubahan default antar fold.
- Tidak ada SMOTE.
- Tidak ada duplikasi overlapping windows.
- Tidak ada penyeimbangan test set.
- Tidak ada perubahan random seed.

Sebut perbandingan sebagai fixed-defaults benchmark.

Jangan mengklaim pemenang sebagai algoritma terbaik setelah optimasi.

Perbedaan jumlah window per take juga harus dilaporkan. Algoritma dilatih dengan jumlah window aktual; tidak ada sample weighting per take pada baseline ini.

## 21. Pemilihan model

Berikan dua rekomendasi terpisah:

**Predictive performance winner**
- Macro F1.
- Balanced accuracy.
- Per-class recall.
- Stabilitas antar-take.
- False positive dan false negative.

**ESP32 deployment candidate**
- Ukuran model.
- Kompleksitas inference.
- Interpretabilitas.
- Ketersediaan exporter.
- Kesesuaian dengan resource ESP32.

Keduanya tidak harus sama.

Jangan menetapkan model produksi dari benchmark ini.

Karena lima algoritma dibandingkan pada OOF yang sama, pemilihan pemenang berdasarkan skor tersebut merupakan model selection. Nyatakan bahwa skor pemenang tetap merupakan estimasi eksploratif dan perlu validasi independen pada dataset baru sebelum klaim performa final.

---

# BAGIAN VIII — ARTEFAK

## 22. Lokasi hasil

Buat direktori baru:

`reports/activity_classifier_benchmark/<timestamp>/`

Jangan menggunakan direktori eksperimen sebelumnya.

Struktur minimal:

```text
reports/activity_classifier_benchmark/<timestamp>/
├── DATASET_AUDIT.md
├── EXPERIMENT_DESIGN.md
├── dataset_manifest.csv
├── dataset_snapshot_hashes.csv
├── multiclass_results.csv
├── binary_results.csv
├── hardcase_results.csv
├── per_class_metrics.csv
├── fold_results.csv
├── predictions_oof.csv
├── confusion_matrices/
│   ├── multiclass/
│   ├── binary/
│   └── hardcase/
├── feature_analysis.md
├── algorithm_analysis.md
├── model_complexity.csv
├── RESULTS.md
├── configs/
└── scripts/
```

Tambahkan file tambahan jika diperlukan, tetapi jangan mengubah file produksi.

### Isi CSV OOF

Minimal:
- experiment_id
- algorithm
- fold_id
- recording_id
- activity_label
- true_class
- predicted_class
- window_index
- timestamp_start
- timestamp_end
- feature_validity
- per-class raw scores jika tersedia beserta score semantics

Jangan menyebut raw score sebagai probability.

Simpan fold metadata agar hasil bisa direproduksi.

## 23. Command reproduksi

Tuliskan:
- Command audit dataset.
- Command menjalankan multiclass.
- Command menjalankan binary.
- Command menjalankan hard-case.
- Command menghasilkan seluruh OOF predictions.
- Command menghasilkan confusion matrix.
- Command menghasilkan model complexity report.

Seluruh command harus dapat dijalankan ulang dari repository yang sama menggunakan dataset snapshot yang dicatat.

Jangan hanya menyimpan output terminal.

---

# BAGIAN IX — KESIMPULAN YANG WAJIB DIJAWAB

## 24. Pertanyaan hasil benchmark

### Multiclass
1. Algoritma mana yang memperoleh Macro F1 tertinggi?
2. Algoritma mana yang memperoleh balanced accuracy tertinggi?
3. Kelas mana yang paling mudah dikenali?
4. Kelas mana yang paling sulit?
5. Pasangan kelas mana yang paling sering tertukar?
6. Apakah manner-fall dapat dibedakan?

### Binary
1. Algoritma mana yang mempunyai fall recall tertinggi?
2. Apakah recall tinggi dibayar dengan false positive lebih tinggi?
3. Apakah `fall_keseleo` terdeteksi?
4. Apakah `fall_lemas` terdeteksi?
5. Apakah performa berubah antara fall lama dan fall baru?
6. Berapa perbedaan native binary dengan multiclass-to-binary?

### Hard-case
1. Apakah 16-band dapat membedakan transisi fall-keseleo dari walking?
2. Apakah kelima algoritma memberikan hasil yang konsisten?
3. Apakah model hanya memanfaatkan perbedaan intensitas atau ada fitur yang lebih diskriminatif?
4. Seberapa kuat hasilnya pada 11 take dan satu subjek?
5. Apakah hasil ini cukup untuk melanjutkan ke pengembangan fitur temporal?

### Still-to-fall vs walk-to-fall
Bandingkan:
- `fall_forward`
- `fall_backward`
- `fall_lemas`
- `fall_keseleo`

Jelaskan apakah fitur snapshot mampu mengenali variasi konteks pre-action atau hanya karakteristik aktivitas keseluruhan.

### Rekomendasi akhir
Nyatakan:
- Model terbaik predictive performance untuk A.
- Model terbaik predictive performance untuk B.
- Model terbaik untuk C.
- Kandidat paling ringan untuk ESP32.
- Kelas dengan bukti yang masih terlalu lemah.
- Apakah fitur 16-band snapshot layak dipertahankan sebagai baseline.
- Fitur temporal apa yang perlu diteliti pada Fase 3.

---

# BAGIAN X — TATA KELOLA DAN BATAS PEKERJAAN

## 25. Batas eksperimen

Baca dan patuhi:
- `AGENTS.md`.
- `docs/agent-preflight.md`.
- Instruksi repository lainnya.

Ini adalah mandat training dan benchmarking host-side.

Yang diperbolehkan:
- Membaca seluruh dataset.
- Menjalankan training kelima algoritma.
- Membuat isolated benchmark harness.
- Membuat script dan artefak dalam direktori laporan eksperimen baru.
- Menghasilkan model dan header percobaan hanya di direktori laporan.
- Menambahkan catatan changelog sesuai konvensi repository.

Yang dilarang:
- Mengubah `classifier_models.py`.
- Mengubah `train_activity_model.py`.
- Mengubah `dataset_io.py`.
- Mengubah canonical feature extractor.
- Mengubah firmware.
- Mengubah recorder atau test produksi.
- Mengubah folder recording.
- Mengubah `.frames.csv`.
- Mengubah `.meta.json`.
- Mengubah index dataset.
- Mengubah `activity_model_data.h` aktif.
- Flash atau erase flash/NVS.
- Commit atau push.
- Git reset atau clean.
- Mengubah project memory.
- Menjalankan implementasi Fase 3 atau Fase 5.

Semua script tambahan harus berada di:

`reports/activity_classifier_benchmark/<timestamp>/scripts/`

Jangan menaruh helper eksperimen di `tools/` atau `fall_detection/`.

Jika ada modifikasi tidak sengaja pada file produksi, hentikan pekerjaan dan laporkan. Jangan mencoba memulihkan dengan reset/checkout/clean otomatis.

## 26. Aturan penghentian

Apabila:
- Dataset snapshot tidak konsisten.
- Label tidak dapat ditetapkan.
- Ada fold yang kehilangan kelas training.
- Feature extractor canonical tidak dapat dipanggil dengan aman.
- Ada kesalahan timestamp.
- Model gagal fit.
- Prediksi tidak lengkap.

Hentikan bagian eksperimen yang terdampak dan dokumentasikan bukti kegagalannya.

Eksperimen lain yang masih valid boleh tetap dijalankan.

Jangan menyembunyikan fold gagal atau mengurangi persyaratan evaluasi secara diam-diam.

**Jalankan seluruh eksperimen yang valid sekarang. Setelah hasil, laporan, dan artefak reproducible tersedia, berhenti dan laporkan. Jangan melanjutkan otomatis ke implementasi Fase 3 atau Fase 5.**