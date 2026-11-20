Laporan lengkap ditulis ke `/tmp/opencode/lit/REVIEW_DATASET_CONSTRUCTION.md`. Berikut versi lengkapnya.

---

# Dari Rekaman Mentah ke Sampel Berlabel
### Tinjauan literatur konstruksi dataset pada deteksi jatuh / HAR berbasis Wi-Fi CSI — 18 makalah

**[R]** = dilaporkan penulis · **[I]** = interpretasi saya · `UNKNOWN` = tidak dilaporkan · `NOT VERIFIED` = klaim sekunder, tidak terkonfirmasi ke teks asli

---

## 1. Ringkasan eksekutif

1. **Tidak ada satu pun makalah yang melaporkan pipeline secara lengkap.** Dari 18, tidak ada yang sekaligus melaporkan jumlah subjek, jumlah event, jumlah window, durasi window, aturan overlap, protokol split, dan definisi unit metrik. Celah paling sering: **protokol split** (8 × `UNKNOWN`) dan **normalisasi** (14 × `UNKNOWN`).
2. **Satu rekaman ≠ satu sampel latih.** StanWiFi = 6 subjek × 6 aktivitas × 20 repetisi = 720 rekaman, tetapi CSITime melaporkan 4.478 sampel dan dlmodels2022 melaporkan 8.959. Ekspansi 6,2× dan 12,4×.
3. **Anotasi manual dominan, medianya berbeda:** kamera + overlay timestamp (Chu, SiFall, CSI-Bench), tombol/log manual (CSI-Bench), atau asumsi "satu sesi = satu aktivitas" (Damodaran, GMM-HMM, WiFall, WmFall, HARNN, SmartAcc, ESP32 PoC).
4. **Window 5 detik adalah konvensi de facto** (Chu, RobustTrans, CSI-Bench, ESP32 PoC, "falling" Damodaran). 3 detik: Anti-Fall, SmartAcc. 6 detik: HARNN. 20 detik: WiFall.
5. **Fitur ≠ dimensi input.** Anti-Fall 112 = vektor fitur (7 × amp/fase × 4 SC × 2 link). Chu 3×625×30 = tensor mentah. Tidak sebanding.
6. **Metrik tingkat window mendominasi dan menyesatkan.** SiFall satu-satunya yang melaporkan segmen 5,1 s vs ground truth 2,6 s — TPR 100% dihitung per segmen.
7. **Kebocoran data adalah norma.** Split acak 80/20 pada data kontinu (Chu, RobustTrans) menempatkan window bersebelahan di train dan test. TransGNN split **berdasarkan durasi** pada rekaman 30 detik kontinu.
8. **Generalisasi lintas lingkungan titik terlemah.** WiFall 94% → 78% antar ruangan; WmFall → ~65% NLOS; FallDeFi ~80% lintas domain; SiFall mereproduksi RT-Fall hanya 64,9% TPR / 49,2% FPR.
9. **Subjek kecil dan tidak beragam.** Median 6. Hanya Chu (22), CSI-Bench (35/17), TransGNN (20), SiFall (16) yang >10. Tidak ada subjek lansia; usia tertinggi 56.
10. **Konsekuensi untuk kita:** simpan provenance window (recording_id, event_id, start/end sample), laporkan metrik event-level **dan** window-level terpisah, split subject-disjoint.

---

## 2. Ruang lingkup dan standar bukti

**Pertanyaan:** bukan "akurasi tertinggi", melainkan bagaimana data dibentuk — akuisisi, subjek/lingkungan, anotasi, segmentasi, preprocessing, representasi, split, evaluasi.

**Inklusi:** peer-reviewed atau preprint dengan teks lengkap terverifikasi; CSI Wi-Fi; kelas jatuh; melaporkan minimal satu dari jumlah subjek / jumlah sampel / durasi window / protokol split.

**Standar:** setiap angka dapat dilacak ke bagian/tabel/gambar. Klaim hanya-abstrak ditandai. Klaim sekunder ditandai `NOT VERIFIED`. Angka hilang tidak diisi inferensi; jika saya menghitung sendiri (mis. 720 = 6×6×20), saya tulis "dihitung dari".

**Keterbatasan:** RT-Fall & FallDeFi berbayar (abstrak + deskripsi sekunder); CSITime hanya preprint; DeFall DOI tidak tercantum di teks; CARM, E-eyes, Framework 2021, WiAR gagal diakses dan **tidak** dimasukkan.

---

## 3. Taksonomi pipeline

```
A. Akuisisi     → perangkat, band, laju paket, geometri link
B. Penyimpanan  → format file, timestamp, metadata sesi
C. Anotasi      → ground truth, penyelarasan waktu
D. Segmentasi   → potong event vs windowing tetap
E. Pembersihan  → filter, koreksi fase, outlier
F. Representasi → fitur tangan | tensor mentah
G. Pelabelan    → per window | per event | per sesi
H. Split        → acak | subject-disjoint | environment-disjoint
I. Evaluasi     → window-level | event-level | sesi-level
```

Dua sumbu yang paling sering salah dilaporkan: **D vs G** (memotong lalu melabeli semua window sama ≠ menganotasi event lalu memotong di dalamnya) dan **H vs I** (split acak pada window bersebelahan membuat metrik mengukur hafalan).

---

## 4. Profil per makalah

**4.1 WiFall (INFOCOM 2014 / TMC 2017)** — `10.1109/INFOCOM.2014.6847948`. Intel 5300 3×3, link 5 GHz, beacon 100 paket/s = 100 Hz [R, §VI]. Sampel 20 detik [R]. 7 fitur × 9 stream = **63-d**; LOF + one-class SVM. Table I: chamber 94%/22%, lab-one 85%/17%, lab-two 91%/15%, dormitory 78%/21%, rata-rata **87%/18%** [R]. Split `UNKNOWN`. 4 subjek.

**4.2 Anti-Fall (Springer 2015)** — `10.1007/978-3-319-19312-0_15`. 6 mahasiswa (5M/1F), 2 ruangan, 2 minggu, ground truth kamera [R]. **230 jatuh** (70 meeting / 150 office) + **510 mirip-jatuh** [R]. Window **3.000 ms**. Fitur 7 × amp/fase × 4 SC × 2 link = **112-d**. One-class SVM. **89% presisi / 13% FA** [R]. Split `UNKNOWN`.

**4.3 RT-Fall (TMC 2017, 16(2):511–526)** — `10.1109/TMC.2016.2557795`. Phase difference antar antena + PDR; segmentasi real-time; one-class SVM RBF. Abstrak: **+14% sensitivitas, +10% spesifisitas vs WiFall** di 4 skenario [R]. Angka 91%/92%: `NOT VERIFIED` (dikutip Damodaran). Subjek/event/window/split: `UNKNOWN`. SiFall mereproduksi hanya **64,9% TPR / 49,2% FPR**.

**4.4 FallDeFi (IMWUT 2018)** — `10.1145/3161183`. STFT + PBC; matriks **10.000 × 60** per 10 s @1.000 Hz; **~80% lintas domain** [R]. Subjek/event/ruangan/split `UNKNOWN`. RobustTrans mengukur FallDeFi 80,8% agregat / 68,2% NLoS pada dataset Chu.

**4.5 WmFall (IJDSN 2018)** — `10.1177/1550147718805718`. 6 relawan, 5 aksi, 20 repetisi. 90 stream amplitudo, Butterworth 60 Hz, SVD window 10 @100 Hz [R]. Tahap 1 (SVM): jatuh+duduk TP **83%** / FP **31%**. Tahap 2 (DNN 3 hidden layer, 1.000 paket, 100 aksi berurutan): **91%**. Keseluruhan **89% presisi / 8% FA**; NLOS **~65%** [R]. Split `UNKNOWN`.

**4.6 Damodaran & Schäfer (CCF TPCCI 2020, 2:1–17)** — `10.1007/s42486-020-00027-1`. 1 TX + 3 RX; 2.500 paket @15 ms; 90 kolom amplitudo. 5 aktivitas × 200 sampel. Eksperimen jatuh: **700 aktivitas** (140/aktivitas; 60 diikuti berdiri → **80 `fall` + 60 `false alarm`**) [R, §6]. 500 paket @10 ms = 5 s; khusus fall 5 s "Falling" + 15 s "Post Fall". SVM (DWT+PCA+PSD+Haar) vs LSTM (90-d, 128 unit). **Recall 100%**, presisi **62%** (fall saja) / **74%** (semua fall) [R]. Split `UNKNOWN`. Catatan: definisi `false alarm` = jatuh lalu berdiri, bukan aktivitas non-jatuh — tidak sebanding dengan makalah lain.

**4.7 Chu et al. (IEEE Access 2023)** — `10.1109/ACCESS.2023.3300726`. 22 relawan (24–43, 7F/15M), 4 ruangan / 5 area. **321 jatuh + 436 non-jatuh**. Segmen 5 s, satu aktivitas per segmen. Input **3×625×30**, 1.000 → 125 Hz. Anotasi overlay timestamp GoPro. Split **80/20 acak**. Per ruangan (jatuh/non-jatuh): 91/157, 58/76, 40/45, 36/49, 96/109; ruangan tersulit 80% [R].

**4.8 CSITime (preprint 2021)** — venue/DOI `NOT VERIFIED`. StanWiFi 6 subjek × 20 repetisi tetapi **4.478 sampel** (Lay 657, Fall 1.465, Walk 1.209, Run 400, Sit 304, Stand 443) [R, §4.1.2]. Input 90-d, datapoint `500 × 90`. ARIL 1.440; SignFi 8.280/276. Split: **10-fold StanWiFi**, 5-fold SignFi, bawaan ARIL. 98,20% / 98% / 95,42% [R].

**4.9 GMM-HMM (IEEE Access 2021)** — `10.1109/ACCESS.2021.3082627`. 1×3 MIMO, 5,320 GHz / 20 MHz, 100 Hz. **600 sampel** = 5 aksi × 30 × 4 relawan; tiap sampel **10 s dengan aksi hanya di detik 4–7** [R]. Split 2/3–1/3 acak, 20 eksperimen dirata-rata. **97,8%**; 100/100/100/98,2 di 4 kondisi; lintas lingkungan **≥95,9%** [R].

**4.10 HARNN (IEEE Access 2019)** — `10.1109/ACCESS.2019.2956952`. Intel 5300, 1.000 Hz, 5 GHz / 20 MHz. 10 orang × 6 aktivitas × 30 repetisi; 15 s per aktivitas; **sliding window 6 s** [R]. 95–98% (E-eyes 95%, CARM 96%). Proporsi split `UNKNOWN`.

**4.11 dlmodels2022 (NCAA 2022)** — `10.1007/s00521-021-06787-w`. StanWiFi publik; **8.959 sampel** (Lie 1.318, Fall 889, Walk 2.931, Run 2.408, Sit 812, Stand 601) [R, Table 2]. Input **1.000×30×3**, satu file = satu sampel, **tanpa windowing dilaporkan**. 10-fold CV + 70/30. **CNN-GRU 99,31%** (k-fold 99,14%).

**4.12 SiFall (SenSys 2022)** — `10.1145/3560905.3568517`. 16 relawan (11M/5F, 21–56 y, 42–100 kg, 155–186 cm); 92 jam data uji; 3 testbed; kamera 30 fps + NTP [R]. Pretrain 1.447 set STFT × 24 augmentasi = **34.728**. Uji: 12 subjek, 19,3 jam, **1.497 klip** → 523 disengaja (123 jatuh + 400 mirip-jatuh: 60 walk-fall, 33 slow-fall, 30 stop-fall). **TPR 100% / FPR 1,8%**. Segmen rata-rata **5,1 s** vs GT **2,6 s**. Reproduksi RT-Fall **64,9% / 49,2%**. Adopsi 3 hari: 204 klip, 12 FA; FAR 13,4% → 1,4% setelah pembaruan daring [R].

**4.13 DeFall / UMD (ICASSP 2020)** — DOI `NOT VERIFIED` (hlm. 1723). 5,808 GHz, 40 MHz, **1.500 Hz**. **846 jatuh + 814 non-jatuh**; 3 bulan; LOS/NLOS. Template 2-D + DTW, **tanpa training**. **DR 96% / FAR 1,47%** [R].

**4.14 ESP32 PoC (arXiv:2611.15532, 2026)** — 2× ESP32, 3,5 m, 1 peserta, window 5 s, **29 instance** (16 jatuh / 13 jalan). DWT Symlet-10 → z-score → wavelet scattering → LogitBoost. **93,10% / presisi 100% / recall 87,50% / F1 93,33%** [R]. Split `UNKNOWN`. Paling dekat dengan setup kita, paling lemah metodologinya.

**4.15 RobustTrans (arXiv:2605.00869, 2026)** — dataset Chu; 1.000 → 125 Hz; window 5 s → **625×90**. Split 80/20 acak **+ LOEO**. **99,5% agregat / 97,6% NLoS / 98,8% lingkungan tak terlihat** [R]. Baseline FallDeFi: 80,8% / 68,2%.

**4.16 CSI-Bench (arXiv:2505.21866, 2025)** — 26 lingkungan, 35 pengguna, **461 jam**. Tugas jatuh: **6,7k sampel / 17 pengguna / 6 lingkungan / 2 perangkat**; **2.770 event jatuh + 3.930 non-jatuh**; 14M/3F, 23–42 y, 156–182 cm, 46–90 kg [R, §A.5]. Window **5 s non-overlapping**, amplitudo saja, normalisasi mean/std **per sampel**, subcarrier pad/clip. Split **70/15/15** + OOD lintas pengguna/lingkungan/perangkat. Label easy/med/hard.

**4.17 TransGNN (arXiv:2504.16655, 2025)** — 20 subjek (7F/13M, ~29 y), 5 aksi × 5 repetisi, 114 subcarrier @300 Hz, buffer 10 → **(10,3,114) @30 Hz**; aksi statis 30 s kontinu. Split **80/20 berdasarkan durasi** [R] — kebocoran temporal. Jatuh: 5 s jalan/jongkok + 5 s jatuh; 4 repetisi train, ke-5 test. Label dari YOLOv11Pose.

**4.18 SmartAcc (arXiv:2412.09980, 2024)** — 10 aksi: fall 820, play 748, pickput 870, sit 876, squat 818, static 896, walk 759, up-down 832, toward-down 866, throwing 820. Window 3 s; CSI **30×212** (10 Hz, 106 SC I/Q); IMU 20 fitur; split 7:3; **99%** [R].

---

## 5. Akuisisi

| Makalah | Perangkat | Band/BW | Laju | Topologi |
|---|---|---|---|---|
| WiFall | i5300 3×3 | 5 GHz | 100 Hz | 1 TX, 1 RX |
| Anti-Fall | i5300 | UNKNOWN | UNKNOWN | 2 link |
| RT-Fall | i5300 | UNKNOWN | UNKNOWN | multi-antena |
| FallDeFi | i5300 | UNKNOWN | 1.000 Hz | UNKNOWN |
| WmFall | i5300 | UNKNOWN | 100 Hz | 1 TX, 3 antena |
| Damodaran | i5300 | UNKNOWN | 66,7 Hz | 1 TX, 3 RX |
| Chu | i5300 | 2,4/5 GHz | 1.000→125 Hz | 1 TX, 1 RX |
| GMM-HMM | i5300 1×3 | 5,320/20 MHz | 100 Hz | 1 TX, 3 RX |
| HARNN | i5300 | 5/20 MHz | 1.000 Hz | 1 TX, 1 RX |
| SiFall | 2 AP | UNKNOWN | UNKNOWN | 2 RX antena |
| DeFall | SDR | 5,808/40 MHz | 1.500 Hz | 1 TX, 1 RX |
| ESP32 PoC | 2× ESP32 | 2,4 GHz | UNKNOWN | 1 TX, 1 RX |
| TransGNN | 1 TX, 3 RX | 2,4 GHz | 300→30 Hz | 1 TX, 3 RX |
| SmartAcc | smartphone | UNKNOWN | 10 Hz | 1 link |

**Pola:** Intel 5300 mendominasi (9/18) → 30 grup subcarrier jadi default literatur; ESP32 tidak ekuivalen. Laju bervariasi **10–1.500 Hz** (150×) — "window 5 detik" = 50 sampel (SmartAcc) vs 7.500 (DeFall). Hanya 4 makalah melaporkan bandwidth eksplisit.

---

## 6. Subjek dan lingkungan

Median **6 subjek**. >10: Chu (22), CSI-Bench (35/17), TransGNN (20), SiFall (16). 5 dari 18 hanya satu ruangan. **Tidak ada subjek lansia**; usia tertinggi dilaporkan 56 (SiFall). [I] Seluruh literatur mengukur jatuh terkontrol oleh orang muda dan sehat — perbedaan distribusi kecepatan/massa/pola tidak dibahas sebagai ancaman validitas eksternal di makalah mana pun.

---

## 7. Anotasi

| Tingkat | Makalah | Konsekuensi |
|---|---|---|
| Event + timestamp eksternal | Chu (GoPro overlay), SiFall (kamera 30 fps + NTP), CSI-Bench (video + alat anotasi), TransGNN (YOLOv11Pose 30 Hz) | Dapat diverifikasi |
| Sesi (1 rekaman = 1 label) | WiFall, WmFall, Damodaran, HARNN, SmartAcc, ESP32 PoC, GMM-HMM | Rapuh: gerakan sebelum/sesudah aksi tetap berlabel |
| Otomatis oleh sistem sendiri | RT-Fall, DeFall | Ground truth = prediksi → konsistensi diri, bukan evaluasi independen |
| Turunan model lain | TransGNN (YOLO) | Error model jadi error label |

Tidak ada makalah tingkat "sesi" yang melaporkan berapa banyak window yang sebenarnya tidak mengandung aksi.

---

## 8. Segmentasi dan windowing

| Makalah | Durasi | Overlap | Unit label | Jumlah window dilaporkan |
|---|---|---|---|---|
| WiFall | 20 s | — | sampel | Tidak |
| Anti-Fall | 3.000 ms | UNKNOWN | event | Ya (740) |
| FallDeFi | 10 s | UNKNOWN | segmen | Tidak |
| WmFall | SVD 10 (0,1 s) | — | frame | Tidak |
| Damodaran | 5 s (+15 s post) | Tidak | sampel | Ya (700) |
| Chu | 5 s | Tidak | event | Ya (757) |
| CSITime | 500 sampel | UNKNOWN | window | Ya (4.478) |
| GMM-HMM | 10 s (aksi 3 s) | — | sampel | Ya (600) |
| HARNN | 6 s | Ya | window | Tidak |
| dlmodels2022 | 1.000 sampel | Tidak | file | Ya (8.959) |
| SiFall | variabel ~5,1 s | — | segmen | Ya (1.497) |
| DeFall | variabel | — | sampel | Ya (1.660) |
| ESP32 PoC | 5 s | UNKNOWN | instance | Ya (29) |
| RobustTrans | 5 s | Tidak | window | Tidak |
| CSI-Bench | 5 s | **Tidak** | window | Ya (6,7k) |
| TransGNN | 0,33 s | Ya (buffer) | frame | Tidak |
| SmartAcc | 3 s | UNKNOWN | window | Ya (per kelas) |

**Hanya 8 dari 18** melaporkan jumlah window/sampel latih eksplisit. [I] "Akurasi 98%" dari 29 sampel berbeda secara statistik dari 98% dari 6.700 sampel, tetapi literatur memperlakukannya setara.

**Window variabel:** SiFall segmen 5,1 s vs GT 2,6 s → model bisa belajar dari pasca-jatuh, bukan dinamika jatuh.
**Window dengan padding:** GMM-HMM 10 s dengan aksi 3 s di tengah → efektif window 3 s + 7 s padding; akurasi bisa berarti "ada aksi di suatu tempat".

---

## 9. Preprocessing

| Makalah | Filter | Normalisasi | Subcarrier | Fase |
|---|---|---|---|---|
| WiFall | UNKNOWN | UNKNOWN | 30×9 | tidak |
| Anti-Fall | UNKNOWN | UNKNOWN | **4 dipilih** | **ya** |
| RT-Fall | interpolasi + band-pass | UNKNOWN | UNKNOWN | **phase diff** |
| FallDeFi | STFT | UNKNOWN | 60 | UNKNOWN |
| WmFall | Butterworth 60 Hz + DWT | UNKNOWN | 90 | tidak |
| Damodaran | DWT (heursure, soft) | UNKNOWN | 90 | tidak |
| Chu | downsample 1.000→125 | UNKNOWN | 30 | tidak |
| CSITime | — | batch-level | 30 | tidak |
| GMM-HMM | koreksi linear + Savitzky-Golay | UNKNOWN | 30 | **phase diff** |
| dlmodels2022 | UNKNOWN | UNKNOWN | 30 | tidak |
| SiFall | cleaning + STFT | UNKNOWN | UNKNOWN | **ya** |
| ESP32 PoC | DWT Symlet-10 | **z-score** | UNKNOWN | UNKNOWN |
| RobustTrans | augmentasi fisik | UNKNOWN | 30 | tidak |
| CSI-Bench | — | **mean/std per sampel** | pad/clip | tidak |
| TransGNN | — | /256 | 114 | UNKNOWN |
| SmartAcc | normalisasi | UNKNOWN | 106 I/Q | UNKNOWN |

Fase diabaikan mayoritas (10/18) karena instabilitas; yang memakainya semuanya melakukan koreksi eksplisit. **Normalisasi hampir tidak pernah dilaporkan** — celah reproduksibilitas serius karena amplitudo CSI bergantung pada AGC, jarak, dan daya TX.

---

## 10. Representasi: fitur vs tensor

| Makalah | Jenis | Dimensi input aktual |
|---|---|---|
| WiFall | 7 statistik × 9 stream | **63** |
| Anti-Fall | 7 × amp/fase × 4 SC × 2 link | **112** |
| FallDeFi | STFT + PBC | **10.000 × 60** |
| WmFall | singular value ke-2 | 1 nilai/window |
| Damodaran | amplitudo mentah | **90** (LSTM) |
| Chu | amplitudo mentah | **3 × 625 × 30** |
| CSITime | amplitudo mentah | **500 × 90** |
| dlmodels2022 | amplitudo mentah | **1.000 × 30 × 3** |
| SiFall | STFT | variabel |
| RobustTrans | amplitudo mentah | **625 × 90** |
| CSI-Bench | amplitudo mentah | 5 s × subcarrier |
| TransGNN | amplitudo mentah | **10 × 3 × 114** |
| SmartAcc | 20 fitur IMU + CSI | 30 × 212 |

"112 dimensi" (vektor fitur) dan "3×625×30" (56.250 nilai mentah) tidak dapat dibandingkan. Dua makalah dengan akurasi ~98–99% memakai **dataset yang sama** (StanWiFi) dengan input berbeda — perbedaan performa lebih mencerminkan windowing dan split daripada arsitektur. Hanya 6/18 memakai tensor mentah end-to-end.

---

## 11. Matriks perbandingan

| # | Makalah | Tahun | Perangkat | Subjek | Event/sampel | Window | Input | Model | Split | Hasil |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | WiFall | 2014 | i5300 3×3 | 4 | 4 aksi, 1 minggu | 20 s | 63 | LOF + 1-class SVM | UNKNOWN | 87%/18%; dorm 78%/21% |
| 2 | Anti-Fall | 2015 | i5300 | 6 | 230 + 510 | 3.000 ms | 112 | 1-class SVM | UNKNOWN | 89% / 13% FA |
| 3 | RT-Fall | 2017 | i5300 | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | 1-class SVM RBF | UNKNOWN | +14% sens, +10% spec |
| 4 | FallDeFi | 2018 | i5300 | UNKNOWN | UNKNOWN | 10 s | 10.000×60 | STFT + PBC | UNKNOWN | ~80% lintas domain |
| 5 | WmFall | 2018 | i5300 | 6 | 5 aksi × 20 | SVD 10 | 90 | SVM + DNN | UNKNOWN | 89% / 8%; NLOS 65% |
| 6 | Damodaran | 2020 | i5300 1×3 | UNKNOWN | 700 (80+60) | 5 s + 15 s | 90 | SVM / LSTM | UNKNOWN | recall 100%; presisi 62/74% |
| 7 | Chu | 2023 | i5300 | 22 | 321 + 436 | 5 s | 3×625×30 | CNN | 80/20 acak | terendah 80% |
| 8 | CSITime | 2021 | publik | 6 | 4.478 | 500 sampel | 500×90 | InceptionTime | 10-fold | 98% |
| 9 | GMM-HMM | 2021 | i5300 1×3 | 4 | 600 | 10 s (aksi 3 s) | fitur fase | GMM-HMM | 2/3–1/3 | 97,8% |
| 10 | HARNN | 2019 | i5300 | 10 | 1.800 rekaman | 6 s | UNKNOWN | RNN | proporsi UNKNOWN | 95–98% |
| 11 | dlmodels2022 | 2022 | StanWiFi | 6 | 8.959 | 1.000 sampel | 1.000×30×3 | CNN-GRU | 10-fold + 70/30 | 99,31% |
| 12 | SiFall | 2022 | 2 AP | 16 | 1.497 | ~5,1 s | STFT | FallNet | UNKNOWN | TPR 100% / FPR 1,8% |
| 13 | DeFall | 2020 | 40 MHz SDR | UNKNOWN | 846 + 814 | template | variabel | DTW | tanpa training | DR 96% / FAR 1,47% |
| 14 | ESP32 PoC | 2026 | 2× ESP32 | 1 | 29 | 5 s | scattering | LogitBoost | UNKNOWN | 93,10% |
| 15 | RobustTrans | 2026 | Chu | 22 | mewarisi | 5 s | 625×90 | Transformer | 80/20 + LOEO | 99,5% / 97,6% NLoS |
| 16 | CSI-Bench | 2025 | 2 device | 35 (17) | 6,7k | 5 s | amplitudo | beberapa | 70/15/15 + OOD | lihat §13 |
| 17 | TransGNN | 2025 | 1×3 | 20 | 5 aksi × 5 | 10 sampel | 10×3×114 | Transformer+GNN | 80/20 per durasi | pose + fall |
| 18 | SmartAcc | 2024 | smartphone | UNKNOWN | 8.307 | 3 s | 30×212 | ensemble | 7:3 | 99% |

---

## 12. Protokol training dan validasi

**Dilaporkan:** split acak (Chu 80/20, GMM-HMM 2/3, SmartAcc 7:3, RobustTrans 80/20); k-fold (CSITime 10-fold, dlmodels2022 10-fold); 70/15/15 (CSI-Bench); LOEO (RobustTrans); per durasi (TransGNN); tanpa training (DeFall). **Tidak dilaporkan (8):** WiFall, Anti-Fall, RT-Fall, FallDeFi, WmFall, Damodaran, SiFall, ESP32 PoC.

**Tiga kebocoran:**

1. **Window bertetangga.** Window 5 s berbagi sampel batas dan korelasi tinggi; split acak menempatkan window dari event yang sama di kedua sisi. [I] 99,5% RobustTrans pada split acak = batas atas; 98,8% LOEO = estimasi jujur.
2. **Split per durasi (TransGNN).** 30 detik kontinu dipotong 80/20 secara temporal — bukan split independen.
3. **Normalisasi global.** Hanya CSI-Bench yang menyatakan per sampel; sisanya tidak dapat dipastikan.

**Tidak dilaporkan siapa pun:** jumlah subjek di train vs test (kecuali TransGNN repetisi ke-5, CSI-Bench split per pengguna); jumlah event di train vs test; apakah window dari event yang sama muncul di kedua split.

---

## 13. Metrik dan apa yang diukur

| Makalah | Metrik | Unit |
|---|---|---|
| WiFall | precision, FP | sampel 20 s |
| Anti-Fall | precision, FA | event |
| RT-Fall | sens, spec | event (asumsi) |
| FallDeFi | accuracy | segmen 10 s |
| WmFall | TP/FP, accuracy | frame & aksi (dua tahap) |
| Damodaran | recall, precision | sampel |
| Chu | accuracy per ruangan | segmen 5 s |
| CSITime / dlmodels2022 | accuracy | window / file |
| SiFall | TPR, FPR | **segmen** |
| DeFall | DR, FAR | sampel |
| ESP32 PoC | acc, P, R, F1 | instance |
| CSI-Bench | accuracy, F1 | window (easy/med/hard) |
| SmartAcc | accuracy | window (gabungan IMU+CSI) |

**Tiga distorsi sistematis:**

1. **Unit ≠ kejadian.** SiFall satu event 2,6 s → segmen 5,1 s; TPR 100% = "semua segmen", bukan "semua jatuh".
2. **Definisi FA berbeda.** Damodaran: FA = jatuh lalu berdiri. WmFall: FA = non-jatuh diklasifikasi jatuh. Presisi 62% vs 89% mengukur hal berbeda.
3. **Ketidakseimbangan kelas.** dlmodels2022 Walk 2.931 vs Stand 601 (4,9:1); 99,31% sebagian dari kelas mayoritas.

**Tidak diukur siapa pun:** latency deteksi eksplisit; false alarm per hari (hanya SiFall: 12 FA/3 hari/204 klip); performa pada subjek yang tak pernah dilatih (hanya CSI-Bench, RobustTrans); performa pada lansia.

---

## 14. Mode kegagalan dan ancaman validitas

**Terdokumentasi:**

1. **Jatuh vs duduk** — WmFall tahap 1 TP 83% / FP 31%; Damodaran Sit akurasi 0,60–0,80. [I] Ini batas kelas sebenarnya; akurasi agregat menyembunyikannya.
2. **NLOS** — WmFall ~65%; RobustTrans 97,6% (dengan augmentasi); WiFall dorm 78%.
3. **Perubahan lingkungan** — WiFall 94% → 78%. GMM-HMM ≥95,9% tetapi hanya 30 sampel/aktivitas/relawan.
4. **Pergeseran temporal** — SiFall FAR 13,4% → 1,4% setelah pembaruan; distribusi berubah dalam hitungan hari.
5. **Perangkat berbeda** — FallDeFi 80,8% → 68,2% NLoS pada dataset Chu (~12 poin hilang).

**Ancaman per makalah:** subjek 1–4 (WiFall, GMM-HMM, ESP32 PoC); satu lingkungan (WmFall, Damodaran, TransGNN, SmartAcc, ESP32 PoC); split tak dilaporkan (8); kebocoran window (Chu, RobustTrans acak, TransGNN durasi); ground truth = prediksi sendiri (RT-Fall, DeFall); metrik window dilaporkan sebagai event (hampir semua); tanpa metrik per kelas (10); tanpa baseline eksternal (8).

---

## 15. Implikasi untuk proyek ini

**Tiru:**

1. **Provenance window wajib** — `recording_id`, `event_id`, `start_sample`, `end_sample`, `label`, `annotator`, `label_source`. Tanpa ini metrik event-level dan deteksi kebocoran tidak mungkin.
2. **Pisahkan metrik event dan window**, dengan definisi eksplisit; sebutkan durasi segmen vs durasi ground truth (model: SiFall).
3. **Split subject-disjoint sejak awal** (template: CSI-Bench 70/15/15 + OOD).
4. **Laporkan normalisasi eksplisit** (per sampel atau global).
5. **Catat laju paket efektif dan jumlah subcarrier yang benar-benar dipakai** — ESP32 ≠ Intel 5300.

**Hindari:**

1. Mengutip akurasi literatur sebagai target — 99%/100% diukur pada unit dan split berbeda.
2. Menganggap satu rekaman = satu aktivitas; data kita sudah multi-aksi per rekaman (audit temporal: 55/127 take), jangan disederhanakan.
3. Window 5 detik karena konvensi; window harus diturunkan dari distribusi onset terukur.
4. Akurasi tanpa support per kelas — jatuh vs duduk adalah batas nyata.

**Eksperimen minimum yang dapat dipertahankan:** (a) baseline window-level split per subjek; (b) baseline event-level (satu prediksi per event, TPR/FPR per event); (c) confusion matrix penuh termasuk kelas mirip-jatuh; (d) perbandingan window 3/5/8 s dengan split sama; (e) analisis kebocoran — berapa banyak window bersebelahan yang jatuh ke split berbeda.

---

## 16. Bibliografi

1. C. Han, K. Wu, Y. Wang, L. M. Ni. *WiFall: Device-Free Fall Detection by Wireless Networks.* IEEE INFOCOM 2014. DOI `10.1109/INFOCOM.2014.6847948`; jurnal: IEEE TMC, DOI `10.1109/TMC.2016.2557792`.
2. *Anti-Fall: A Non-intrusive and Real-time Fall Detector Leveraging CSI from Commodity WiFi Devices.* Springer 2015. DOI `10.1007/978-3-319-19312-0_15`.
3. H. Wang, D. Zhang, Y. Wang, J. Ma, Y. Wang, S. Li. *RT-Fall: A Real-time and Contactless Fall Detection System with Commodity WiFi Devices.* IEEE TMC 16(2):511–526, 2017. DOI `10.1109/TMC.2016.2557795`.
4. S. Palipana, D. Rojas, P. Agrawal, D. Pesch. *FallDeFi: Ubiquitous Fall Detection using Commodity Wi-Fi Devices.* IMWUT 1(4), 2018. DOI `10.1145/3161183`.
5. *WmFall: WiFi-based multistage fall detection with channel state information.* IJDSN 2018. DOI `10.1177/1550147718805718`.
6. S. Damodaran, E. Schäfer. *Device free human activity and fall recognition using WiFi channel state information (CSI).* CCF TPCCI 2:1–17, 2020. DOI `10.1007/s42486-020-00027-1`.
7. G. Chu et al. *Fall Detection Based on Wi-Fi CSI.* IEEE Access 11, 2023. DOI `10.1109/ACCESS.2023.3300726`.
8. S. K. Yadav et al. *CSITime: Privacy-Preserving Human Activity Recognition Using WiFi Channel State Information.* Preprint 2021. Venue/DOI `NOT VERIFIED`.
9. *Device-Free Human Activity Recognition Based on GMM-HMM Using Channel State Information.* IEEE Access 9, 2021. DOI `10.1109/ACCESS.2021.3082627`.
10. *Human Activity Recognition Using Deep Recurrent Neural Network (HARNN).* IEEE Access 7, 2019. DOI `10.1109/ACCESS.2019.2956952`.
11. *Deep learning models for WiFi CSI-based human activity recognition.* NCAA 2022. DOI `10.1007/s00521-021-06787-w`.
12. S. Ji, Y. Xie, M. Li. *SiFall: Practical Online Fall Detection with RF Sensing.* ACM SenSys 2022. DOI `10.1145/3560905.3568517`.
13. Y. Hu, F. Zhang, C. Wu, B. Wang, K. J. R. Liu. *A WiFi-based Passive Fall Detection System.* IEEE ICASSP 2020, 1723–1727. DOI `NOT VERIFIED`.
14. A. S. S. et al. *A Proof-of-Concept Study of Wi-Fi CSI-Based Fall Detection Using ESP32 Devices.* arXiv:2611.15532, 2026.
15. Y. Wang et al. *Robust Cross-Domain WiFi Fall Detection via Physics-Driven Attention-Enhanced Transformers.* arXiv:2605.00869, 2026.
16. G. Zhu et al. *CSI-Bench: A Large-Scale In-the-Wild Dataset for Multi-task WiFi Sensing.* arXiv:2505.21866, 2025.
17. Y. Cho et al. *Wi-Fi based Human Fall and Activity Recognition using Transformer-based Encoder–Decoder and Graph Neural Networks.* arXiv:2504.16655, 2025.
18. L. Wang et al. *Real-Time Fall Detection Using Smartphone Accelerometers and WiFi Channel State Information.* arXiv:2412.09980, 2024.

---

**Catatan kejujuran bukti.** Tiga hal yang tidak dapat saya klaim: (a) RT-Fall dan FallDeFi tidak saya baca penuh, jadi semua field selain abstrak adalah `UNKNOWN`, bukan "tidak ada"; (b) CSITime hanya preprint — DOI `10.1145/3494991` yang beredar **tidak** cocok dengan teks ini dan saya tidak memakainya; (c) DeFall DOI tidak tercantum di teks ICASSP yang saya miliki. Repo tidak disentuh; semua keluaran ada di `/tmp/opencode/lit/`.