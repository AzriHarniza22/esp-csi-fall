# Experiment Design — Benchmark Algoritma Kelas CSI (2026-11-08)

Mandat: `examples/esp-radar/wifi_sensing_demo/docs/perbandingan-algoritma.md`.
Harness sepenuhnya terisolasi di direktori ini; tidak ada berkas produksi
(`fall_detection/`, `main/`, recorder, recordings) yang disentuh.

## Eksperimen

| ID | Unit data | Kelas | Folds | Catatan |
|---|---|---|---|---|
| A | semua window grid kanonik, 130 take | 11 label `activity_label` | LOTO 130 | multiclass penuh |
| B | semua window grid kanonik, 130 take | `fall`/`non_fall` (label fall = 4 label `fall_*`) | LOTO 130 | binary dilatih native, folds identik A |
| B (comparator) | OOF A dipetakan biner | `fall`/`non_fall` | — | tanpa fit baru; mayoritas-vote take-level |
| BSENS | 89 take 2026-11-04 saja (20 fall lama + 69 non-fall) | biner | LOTO 89 | sensitivitas confound tanggal/protokol |
| C | window UTUH dalam interval (57 pos / 80 neg, lihat DATASET_AUDIT) | `fall` (keseleo) / `non_fall` (walking) | LOTO 21 | klasifikasi window transisi-jatuh vs window-jalan normal; BUKAN deteksi onset, BUKAN recall event |

Label sumber: `meta.activity_label` saja (§3). Onset C: rekonstruksi
`clock_anchor` (§12), tanpa koreksi reaction-time; observer mark =
`observer-referenced onset`.

## Algoritma & hyperparameter tetap (§6)

Lima algoritma produksi (`fall_detection/classifier_models.py`) dengan default
baku — tanpa tuning, tanpa SMOTE, tanpa class weighting, tanpa ganti seed:
lihat `configs/algorithm_defaults.json`. Skor antar-algoritma TIDAK
sebanding (jarak vs logit vs margin vs indikator daun vs suara). Logit
softmax dilaporkan sebagai skor, bukan probabilitas terkalibrasi.

## Prosedur evaluasi

- **LOTO**: satu take penuh dipegang keluar (semua window-nya jadi test);
  standardisasi fitted ulang di dalam tiap fold oleh kode fit kanonik →
  tidak ada kebocongan statistik antar-fold.
- Pre-check wajib sebelum run: tiap fold harus menyisakan semua kelas di
  training (stop-condition §26). Jumlah window per label per fold didaftar.
- Fitur diekstraksi SEKALI ke `features_cache.pkl` (grid kanonik 24/12;
  window duration dilaporkan di `window_duration_stats.csv`).
- **Pooled OOF**: metrik dihitung dari gabungan semua prediksi out-of-fold
  (bukan rata-rata metrik per-fold), dua level: per-window dan per-take
  (majority vote, tie-break deterministik theo urutan kelas tetap; jumlah
  tie dilaporkan).
- **Bootstrap CI** hanya pada unit take (1.000 resample, seed 20261108) —
  window dalam satu take tidak independen (§19).
- Confusion per algoritma per eksperimen → `confusion_matrices/…`.

## Strategi linear solver + gerbang ekivalensi

Fit kanonik LR/SVM adalah Python murni dan terlalu lambat untuk 130×2 fold.
`bench_common.py` menyediakan mirror numpy dari matematika update yang sama:

- LR full-batch softmax SGD 700 epoch — identik term-for-term; perbedaan
  hanya urutan akumulasi floating-point (bln `err.T @ X`).
- SVM OvR hinge SGD 500 epoch dengan urutan shuffle yang direplikur persis
  (`random.Random(RANDOM_SEED)` stream yang sama). Dalam satu sampel,
  update tiap kelas saling independen (margin kelas c hanya membaca baris
  W[c]) → vektorisasi simultan == loop sekuensial kanonik.
- Prediksi SEMUA algoritma selalu lewat `predict_scores` kanonik.

Gate (`equivalence_check.py`, hasil di `equivalence_check.json`): untuk LR
dan SVM pada 3 ukuran training (subset 191 / 714 / penuh ±2.850 window),
dibandingkan max|Δweights| dan agreement argmax pada seluruh 3.088 window.
Kriteria lolos: agreement holdout 100% dan agreement semua window ≥ 99,5%.
Jika gate gagal, LR/SVM dijalankan mode kanonik (lebih lambat) — runner
membaca file gate secara otomatis; tidak ada jalur diam-diam.

Catatan eksekusi aktual: Experiment C dijalankan lebih dulu (training hanya
137–173 window/fold) saat `equivalence_check.json` belum ada → LR/SVM C
memakai fit KANONIK penuh. A/B/BSENS jalan setelah gate lolos (mode
vectorized). Karena gate menunjukkan agreement argmax 100% (SVM bahkan
bobot bit-identik, max|Δw| = 0.0), kedua mode menghasilkan model yang sama
secara fungsional.

## Stop-conditions (§26) dan status

| Kondisi | Mekanisme | Status |
|---|---|---|
| Snapshot tidak konsisten | verifikasi bit-eksak harness-vs-kanonik per take di `load_take` | 130/130 cocok, 0 frame skip |
| Fold kehilangan kelas training | pre-check sebelum dispatch di `run_loto.main` | lihat log per eksperimen |
| Kesalahan timestamp | reversal = raise; duplikat stempel diizinkan (didokumentasi) | 0 reversal |
| Fit gagal | fold masuk `failed_folds.csv`, tidak pernah dihapus diam-diam | lihat CSV / log |

## Kompleksitas model

Per fold dicatat: jumlah parameter (bobot/centroid), jumlah node pohon,
dan ukuran header C hasil `render_c_header` kanonik (byte) → agregat
median/p95/max di `model_complexity.csv`. Ini biaya host-side; klaim
RAM/flash perangkat hanya dibahas deskriptif di RESULTS (header aktif
saat ini masih 3-kelas 52-pair dan belum selaras dengan dataset —
registrasi ulang adalah Fase 1B/4B, di luar mandat ini).

## Reproduksi

```
cd reports/activity_classifier_benchmark/20261108T073910Z/scripts
python3 make_manifest.py
python3 extract_features.py
python3 equivalence_check.py
python3 run_loto.py --experiment A
python3 run_loto.py --experiment B
python3 run_loto.py --experiment BSENS
python3 run_loto.py --experiment C
python3 analyze.py
```

Python 3.11.2 + numpy 2.3.5 (lihat `configs/environment.json` termasuk
commit repo). Semua seed tetap: `RANDOM_SEED=20261026` (kanonik) dan
bootstrap 20261108.
