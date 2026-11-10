# Feature Analysis — Benchmark Kelas CSI (2026-11-08)

Bukti mentah: `feature_probe_output.txt`, `window_duration_stats.csv`,
`feature_stats_by_label.csv`, `feature_standardizer_global.json`
(dibangun dari `features_cache.pkl`; angka di bawah berasal darinya).

## Ruang fitur (kanonik, tidak diubah harness)

16 fitur per window: `band = sc*16//51` atas 51 pasang subcarrier Layout A,
nilai = `log1p(mean |ΔAmp|)` di seluruh 23 transisi frame dalam window
24-frame. Fitur absolut — bukan baseline-relative. Standarisasi (mean/scale)
dilakukan ulang di dalam tiap fit fold.

## Cakupan waktu window (mandat §5: wajib dilaporkan)

- Grid 24/12 atas stream ~31 fps → span window **median 0,786 s**
  (p95 0,987 s; min 0,376 s karena clock recorder me-reset spasi antar frame;
  max 2,548 s pada segmen dengan gap besar). Ini bukan window durasi tetap:
  satu window bisa "melihat" rentang waktu berbeda antar take.
- Inter-arrival frame median per take: 8,3–39,7 ms (median global 31,7 ms).
  Protokol 2026-11-04 ≈ 32,2 ms; 2026-11-07 ≈ 30,0 ms — perbedaan rate
  kecil yang ikut jadi bagian confound tanggal.
- Jumlah window per take bervariasi 18–28 mengikuti durasi & rate stream.

## Band mana yang memisahkan fall vs non-fall?

Selisih mean terstandardisasi (Cohen-ish d) fall(1.526 window) vs
non-fall(1.562) per band 0..15:

`0.60, 1.01, 0.78, 0.33, 0.50, 0.24, 0.44, 0.35, 0.30, 0.14, 0.18, 0.10, 0.12, 0.28, -0.06, 0.44`

Sinyal terkonsentrasi di **band 0–4 (subcarrier bawah)** — konsisten dengan
cerita fisik: perubahan amplitudo low-tone paling kuat saat objek besar
(tubuh) bergerak cepat dekat jalur LOS. Band 9–12 praktis tidak informatif
(d < 0,2).

**Uji confound tanggal**: statistik yang sama dihitung HANYA dalam take
2026-11-04 (fall lama vs non-fall lama, tanggal identik):
`0.43, 0.83, 0.79, 0.12, 0.43, 0.52, 0.67, 0, 0.08, 0.24, 0.19, -0.18, -0.10, 0.05, -0.04, 0.30`
→ band 0–2 tetap memisahkan (d 0,43–0,83). Jadi sinyalnya nyata, bukan
murni artefak tanggal — tetapi lebih lemah dari angka campuran, dan band
5–7 justru terbalik peran antar kelompok tanggal. (Tidak mungkin uji dalam-
tanggal untuk 2026-11-07 karena tidak ada non-fall di tanggal itu.)

## Profil per label (mean terstandardisasi, ringkas)

- `empty_room`, `still_standing`, `still_sitting`, `fast_sitting`: band 0–2
  negatif (−0,4 s/d −1,2) — minim pergerakan amplitudo.
- `walking`: unik — band 3/6/7 NEGATIF tapi band 11/12/14/15 POSITIF
  (+0,34…+0,75): ritme langkah menaikkan subcarrier atas sambil rendah di
  bawah. Ini pembeda utama walking vs fall di band yang sama.
- `fall_backward`/`fall_lemas`: band 0–2 sangat positif (+0,21…+0,71).
- `fall_keseleo`: positif MERATA di band 5–10 (+0,24…+0,64) — profilnya
  lebih mirip "gegar lebar" daripada transisi tajam; sebagian alasan ia
  jadi hard-case terhadap walking (dua-duanya tinggi di band 11–12).
- `object_drop`: negatif kuat band 13 (−1,24) — sidik jari objek kecil.
- Fall lama vs baru (label sama, beda protokol): `fall_forward_old` vs
  `_new` berbeda paling jauh (band 5: +0,36 vs −0,22) — bukti langsung
  bahwa "tanggal" punya komponen bentuk fitur, bukan hanya durasi rekaman.

## Konsekuensi untuk model linear

Fitur paling diskriminatif (band 0–2) juga paling tumpang-tindih antar
kelas non-fall; profil band tinggi unik walking/keseleo berlawanan arah
dibanding asumsi "fall = lebih banyak movement di semua band". Model linear
akan bergantung pada band 0–2 dan akan terdorong memisahkan kelompok
tanggal; pohon bisa memotong di band 11–15 tapi dengan margin kecil
(n=10 take per kelas non-fall). Tidak ada normalisasi per-take (baseline-
relative) di fitur kanonik — ini pilihan desain produksi yang dipertahankan
benchmark; konsekuensinya (sensitif ke rate & offset perangkat) dilaporkan
di `algorithm_analysis.md`.
