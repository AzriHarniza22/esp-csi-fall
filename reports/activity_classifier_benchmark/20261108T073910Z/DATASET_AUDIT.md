# Dataset Audit — Benchmark Klasifikasi Aktivitas (2026-11-08)

Semua angka di file ini diukur ulang langsung dari dataset pada saat run
(manifest + SHA-256: `dataset_manifest.csv`, `dataset_snapshot_hashes.csv`,
`dataset_snapshot_summary.json`), bukan disalin dari audit lisan sesi
sebelumnya.

## Snapshot

- Sumber: `examples/esp-radar/wifi_sensing_demo/recordings/` (v3:
  `{tid}.meta.json` + `{tid}.frames.csv`).
- **130 take, 39.337 frame CSV, 39.337 frame disimpan reader kanonik,
  0 frame diskip** (0 payload-invalid, 0 layout-unsupported; seluruh frame
  Layout A 51 pasang subcarrier → `subcarrier_width = 51` di semua take).
- **3.088 window** pada grid kanonik `WINDOW_FRAMES=24`, `WINDOW_STRIDE=12`
  (ekstraksi via `extract_window_features` produksi; harness memverifikasi
  amplitudo per-frame bit-eksak terhadap reader kanonik untuk 130/130 take).
- Label kanonik = `meta.activity_label` saja. Tidak ada label yang diambil
  dari recording_id / folder / segments / instruction (§3 mandat).
- Durasi rekaman: take 2026-11-04 median 9,96 s (protokol 10 s), take
  2026-11-07 median 11,97 s (protokol 12 s).

## Komposisi per label

| activity_label | takes | windows | subjek | sesi | tanggal |
|---|---|---|---|---|---|
| fall_forward | 20 | 470 | 1 (baru) + None (lama) | 1 baru + None | 10 lama / 10 baru |
| fall_backward | 20 | 495 | 1 (baru) + None (lama) | 1 baru + None | 10 lama / 10 baru |
| fall_lemas | 10 | 264 | 2 | sess_20261107T100226Z_luxlof | 11-07 semua |
| fall_keseleo | 11 | 297 | 1 | sess_20261107T100226Z_luxlof | 11-07 semua |
| walking | 10 | 234 | None | None | 11-04 |
| bending | 10 | 230 | None | None | 11-04 |
| fast_sitting | 10 | 233 | None | None | 11-04 |
| object_drop | 10 | 231 | None | None | 11-04 |
| empty_room | 9 | 205 | None | None | 11-04 |
| still_standing | 10 | 212 | None | None | 11-04 |
| still_sitting | 10 | 217 | None | None | 11-04 |

Grup fall: 61 take / 1.526 window. Non-fall: 69 take / 1.562 window.

## Batasan generalisasi yang WAJIB dibaca bersama hasil

1. **Confound tanggal/protokol**: seluruh non-fall (69 take) + 20 fall lama
   direkam 2026-11-04 dengan protokol 10 s; 41 take fall (fwd/bwd baru,
   lemas, keseleo) direkam 2026-11-07 dengan protokol 12 s. Model bisa
   belajar "tanggal/protokol", bukan "jatuh".
2. **Subjek tunggal per label baru**: `fall_lemas` hanya subjek 2;
   `fall_keseleo` hanya subjek 1. Dua label fall ini punya confound
   subjek-sesi penuh.
3. **89 take lama tidak punya `subject_id`/`session_id`** → LOTO adalah
   satu-satunya unit generalisasi yang tersedia; LOTO ≠ cross-subject.
4. **Token legacy di recording_id**: take `fall_keseleo` bernama
   `..._fall_right_00X`, `fall_lemas` bernama `..._fall_left_00X`. Tidak
   ada dampak karena label dibaca dari `activity_label`, tapi siapa pun
   yang meng-audit dengan grep nama file akan salah kelompok.
5. Nomor take duplikat dalam satu label: `bending_001` ×3,
   `fast_sitting_001` ×2 (waktu rekaman berbeda; bukan duplikat berkas).
   Tidak memengaruhi LOTO (unit = take utuh, keyed oleh tid penuh).

## Catatan timestamp

- `clock_anchor` + `started_at_utc` ada di seluruh 130 take; rekonstruksi
  onset observer-berbasis-anchor untuk Experiment C berhasil di 11/11 take
  keseleo (onset relatif frame pertama: 4,12–5,26 s).
- Stempel `host_receive_monotonic_ns` clock recorder TIDAK naik murni:
  ada pasangan berurutan dengan nilai identik (3.987 pasangan di 130 take;
  granularitas clock). Tidak ada satu pun backstep (0 reversal di 130 take)
  → deret waktu non-decreasing, sah. Harness awal menuntut monotonic
  strict dan itu salah ekspektasi; sudah dikoreksi di `bench_common.py`
  (reversal tetap stop-condition §26).

## Ulang hard-case (mandat §11–13, metode identik trainer)

Window harus UTUH di dalam interval, dipilih pada grid kanonik (bukan
re-grid dari irisan):

- Positif (`fall_keseleo`, window ⊆ [onset_anchor, action_end timeline 8 s]):
  **57 window** di 11 take (4–6/take). Audit lisan awal melaporkan 61
  karena memakai batas kasar 8,0 s relatif frame pertama; dengan
  konversi anchor yang benar (`plan_host + 8 s`, bervariasi 7,51–7,97 s
  relatif frame pertama) jumlahnya 57. Angka 57 yang dipakai.
- Negatif (`walking`, window ⊆ [action_start, action_end] timeline 3–7 s):
  **80 window** di 10 take (5–9/take). Cocok dengan audit awal.
- Interval `onset` C TIDAK mengoreksi reaction-time observer (§12), dan
  onset adalah `observer-referenced`, bukan ground-truth fisik.

## Verifikasi snapshot

- SHA-256 per berkas meta+frames tersimpan (`dataset_snapshot_hashes.csv`).
- Ekstraksi fitur sekali ke `features_cache.pkl` dipakai semua eksperimen
  → semua fold melihat snapshot identik.
- 0 frame diskip, 0 inkonsistensi reader-vs-harness, 0 fold kehilangan
  kelas training (semua 130+89+21 fold lolos pre-check §26).
