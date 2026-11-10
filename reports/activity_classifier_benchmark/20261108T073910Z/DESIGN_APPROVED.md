# Approved Design Decisions (2026-11-08)

Status: desain arsitektur benchmark engine **disetujui dengan empat koreksi**.
Implementasi fase optimasi **belum diotorisasi** dan tidak boleh dimulai
sebelum run A → B → BSENS final selesai (prioritas saat ini). Dokumen ini
mencatat keputusan; tidak ada kode yang berubah karenanya sampai hari ini.

## 1. Split manifests (tiga file, dua lapisan)

- `splits_AB.json` — A dan B berbagi fold membership + window selection
  (terbukti identik secara struktural: 130 take ids sama, 3.088 window sama,
  grid kanonik penuh).
- `splits_BSENS.json` — populasi 89 take 2026-11-04 saja.
- `splits_C.json` — hard-case dengan window filtering berbasis interval
  (onset/action_end dari clock_anchor).

Setiap manifest memisahkan **fold membership + window selection** (bisa
di-shared) dari **class mapping + target definition** (per eksperimen:
A = 11 kelas, B/BSENS = biner native, C = biner hard-case).

## 2. Feature cache tervalidasi

```
feature_cache/
├── metadata.json    # provenance + skema
├── features.npz     # float64, np.load(allow_pickle=False)
└── checksums.json   # SHA-256 dihitung & disimpan EKSPLISIT per array
                     # (NPZ tidak menyediakan checksum otomatis)
```

Provenance `metadata.json` wajib mencakup SELURUH kode yang memengaruhi:
decoding (`dataset_io.decode_iq/amplitude`), frame filtering & layout CSI
(`train_activity_model._has_supported_lltf_layout/_lltf_pair_count/
CSI_SUBCARRIERS`), clock conversion (rumus `host_seconds` harness),
windowing (`WINDOW_FRAMES/WINDOW_STRIDE` + generator window harness),
feature extraction (`extract_window_features`, `FEATURE_COUNT`), plus hash
dataset snapshot, commit repo (+ dirty flag), dan versi python/numpy.

Protokol: parent process memverifikasi hash dataset + checksum payload
SEKALI sebelum worker dibuat (bukan per worker); cache yang tidak dapat
dibuktikan identitasnya **ditolak dan dibangun ulang**, tidak pernah dipakai
diam-diam. Label mentah `activity_label` tetap di cache; mapping biner/kelas
tinggal di konfigurasi eksperimen.

## 3. Equivalence gate v3 (rancangan)

Pemeriksaan per algoritma linear: seluruh weights, biases, standardization
parameters (means/scales), **full decision-score vectors** (bukan hanya
argmax), dan prediksi per kelas. Kategori bukti dicatat eksplisit dan berbeda:

- **bitwise equality** — delta tepat 0.0 (terbukti untuk linear-svm,
  semua skala; hanya klaim ini yang boleh dipakai untuk SVM);
- **numerical/tolerance equality** — LR ~1e-16 weights/biases; means/scales
  bitwise 0.0; **LR TIDAK boleh disebut bit-identical**;
- **prediction equality** — agreement argmax 100% holdout + ≥99,5% semua
  window (kedua algoritma lolos).

Deviasi yang harus diperbaiki di v3: holdout fallback ke take pertama karena
tid yang ditujukan tidak ada (holdout efektif 18 window), dan skor mentah
belum dibandingkan.

## 4. Provenance historis hasil run 0 (didokumentasikan, bukan direkayasa)

Tidak ada metadata per-baris yang di-backfill seolah direkam saat training.
Bukti berbasis kelompok hasil dari header stdout + timeline mtime log:

| Kelompok hasil | Fit mode yang TERBUKTI | Bukti |
|---|---|---|
| C — LR/SVM (105 task, ±15:01) | **kanonik penuh** | `run_C.log` header `linear_mode=canonical` (gate v1 baru selesai 15:16) |
| A chain-1 — 280 task (centroid+LR 130, SVM 20; ±15:17–15:46) | **vectorized, loop SVM versi sebelumnya** | `run_ABC.log` header `linear_mode=vectorized`; gate v1 di `equivalence_check.log` |
| A chain-2 — SVM task 21–130 + tree/RF | **vectorized, loop SVM teroptimasi (bit-identik, gate v2)** | `run_ABC2.log` header; `gate_svm_rerun.log` GATE PASSED 15:53, `max|Δw|=0.0` |
| B / BSENS (berjalan setelahnya) | vectorized per gate v2 yang sama — **bukti final dari header log run masing-masing saat selesai** | header `run_ABC2.log` bagian B/BSENS |
| Tree/RF di semua eksperimen | kanonik (mode linear tidak memengaruhinya) | `bench_common.fit_model_np` |

Angka lama **37.610 frame tetap dicatat sebagai tidak teratribusi** (0
kecocokan di transcript/repo); snapshot resmi run adalah **39.337 frame**
(0 hash mismatch terverifikasi ulang 2026-11-08).

## 5. Keputusan yang DITOLAK dengan pengukuran

- Cache standardisasi antar-algoritma: 0,325 s/fold-algoritma, hemat <2% →
  tidak dibangun.
- SQLite job-index untuk resume: scan CSV terukur 0,43 s (9.555 baris),
  ±7 s pada skala 20 algoritma → belum perlu; manifest JSONL fingerprint
  cukup.
- Batching fold×algoritma dalam satu pass: <2% hemat, memperburuk load
  balance di 2 core → pertahankan job = fold × algoritma.
- Numba: kompatibilitas 0.68.1 (py 3.10–<3.16, numpy <2.6 — termasuk
  3.11.2 & 2.3.5) terdokumentasi resmi, tetapi instalasi/kompilasi/speedup
  belum diuji; tetap Fase 5, di belakang gate v3.

## 6. Urutan implementasi setelah run 0 selesai (belum diotorisasi)

Fase 1 cache tervalidasi → Fase 2 job fingerprint + kolom provenance
per-baris (`linear_fit_mode`, `code_commit`, `env_hash`) → Fase 3 split
manifests → Fase 4 gate v3 → Fase 5 prototipe Numba di lingkungan terpisah →
Fase 6 Algorithm Registry hanya saat algoritma ke-6 riil masuk.
