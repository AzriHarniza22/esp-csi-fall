# RESEARCH REPORT — Wi-Fi CSI Fall Detection: Audit, Analisis Dataset, dan Rekomendasi

- Timestamp sesi riset: `20261104T180944Z` (UTC)
- Mode: **READ-ONLY** — tidak ada source code, firmware, dataset, label, maupun file model yang diubah. Skrip analisis dan seluruh output ada di folder ini (`scripts/`, `*.json`, `figures/`).
- Kategori bukti pada setiap pernyataan: `[CODE]` `[DATA]` `[PAPER]` `[MEASUREMENT]` `[HYPOTHESIS]` `[REKOMENDASI]`.
- Preflight: `docs/agent-preflight.md` dibaca; tidak ada edit runtime sehingga tidak ada entri changelog baru (mandat melarang perubahan kode).

---

## 1. Executive Summary

1. **Classifier yang ter-deploy di firmware saat ini tidak pernah berjalan pada data sekarang.** Header model in-tree mensyaratkan LLTF 104 byte (52 paritas), sedangkan perangkat menghasilkan 102 byte (51 paritas) sejak compaction `first_word_invalid`. Setiap frame ditolak `has_supported_lltf_layout()`; `classify_window()` tidak pernah terpanggil; web monitor tidak pernah menerima aktivitas. `[CODE]`+`[DATA]` — confidence HIGH untuk arah temuan (bukti statis lengkap), perlu satu sesi perangkat untuk konfirmasi runtime.
2. **Angka-angka lama saya tidak semuanya bertahan.** Re-count pada dataset kini (89 take): window fall 438 terkonfirmasi; "51 window sepenuhnya di fase aksi" menjadi **55**; "still ~634" **tidak dapat direproduksi** (kini 429 window take still + jangkar idle; dataset bertambah sejak klaim dibuat); uji simetris pasca-jatuh yang dulu saya kutip **86% kini 76%**, rasio magnitudo **6.3× kini ~2×**. Klaim lama dibuat pada dataset yang lebih kecil/sebelum take tambahan masuk. `[MEASUREMENT]`
3. **Hipotesis post-fall bertahan secara substansial tapi dengan koreksi penting:** kondisi setelah jatuh memang berbeda dari still normal (LOO simetris 76%; dalam-sesi absolut 78%; magnitudo perubahan ~2× kontrol), **tetapi** profil baseline-relative pasca-jatuh TIDAK bisa dibedakan dari pasca-aktivitas lain (3-kelas hanya 50%; fall-post salah diklabel other-action 22%, other-action salah diklabel fall 33%). Arti praktis: fitur profil pasca-jatuh adalah **konfirmasi bahwa "ada kejadian"**, bukan bukti bahwa kejadiannya jatuh. Deteksi jenis kejadian tetap harus dari fase transisi. `[MEASUREMENT]`
4. **Eksperimen fitur terkontrol (group holdout per take, 5 repeat):** untuk membedakan *falling vs rest*, motion-only balanced-acc 0.87 → kombinasi motion+baseline-relative 0.90 (logistik). Untuk *fallen_still vs normal_still*: motion-only 0.83, kombinasi 0.96 (logistik F1 0.91). H1 dan H2 **didukung**; H3 didukung untuk fallen_still, marginal untuk falling. Profil absolut mencetak skor tertinggi (0.98) justru karena mengencode identitas sesi — ini kontrol confound, bukan model yang sah. `[MEASUREMENT]`
5. **Labeling take-level adalah bug metodologis terbesar pelatihan** (semua window dari take `fall_*` berlabel `fall`, ~55% window fall sebenarnya berada pada level still), dan `to_feature_matrix()` di `dataset_io.py` **secara senyap menghasilkan 0 baris** pada data v3 (floor 52 paritas vs data 51) sehingga jalur adapter trainer-reader terputus tanpa error. `[CODE]`
6. Rekomendasi inti (§12/§14): **perbaiki gerbang layout firmware + regenerasi header** sebagai prasyarat apa pun; pindahkan labeling ke phase-aware (window lintas batas = ambiguous, dibuang); fitur = 16 band motion + 16 band baseline-relative (kausal); model utama linear (L2-friendly) dengan konfirmasi dua tahap k-of-N + state machine; subject/session-independent evaluation **belum mungkin** (subject_id kosong, satu orang, satu ruangan). `[REKOMENDASI]`

---

## 2. Current System Audit (C1/C2)

### 2.1 Alur data sesungguhnya di firmware `[CODE]`

`esp_wifi` promiscuous → esp-radar callback (`esp_radar.c: copy_subcarrier_data` L781, `esp_radar_rebuild_csi_data` L820–860 menghasilkan `valid_data`+`valid_lltf_len`; `esp_radar_get_ltf_data` L1031–1056) → `web_serial_monitor.c` csi_callback → `activity_classifier_enqueue()` (L739) → queue depth 4 → `activity_classifier_task` (L265–298) → `frame_to_amplitude()` → window 24 frame / stride 12 → `classify_window()` → `web_serial_monitor_publish_activity()` (L690–709). Tidak ada voting, debounce, atau state machine — keputusan per-window, log eksplisit `"DEMO only"` (L259).

### 2.2 Bug pemblokir (confirmed)

| # | Temuan | Bukti |
|---|---|---|
| B1 | `activity_model_data.h`: `ACTIVITY_MODEL_LLTF_BYTES 104` / `SUBCARRIERS 52`; data perangkat 102/51 → `has_supported_lltf_layout()` false untuk **semua** frame → classifier mati total. `frame_to_amplitude` L106–112 dan gate L52–55 membandingkan `valid_lltf_len != 104`. | `[CODE]` grep header + `[DATA]` 89/89 take `lltf_len=102` (dataset_audit.json, kolom layouts) |
| B2 | Header model juga **stale secara label**: `{"kosong","duduk","berjalan"}` vs vocabulari recorder 11 label (`fall_*`, `still_*`, dsb.). | `[CODE]` |
| B3 | `dataset_io.to_feature_matrix()` menyaring `len(row) >= BASELINE_SUBCARRIERS (52)` → 0 baris tersisa pada v3 → adapter LR/SVM/RF senyap kosong; konstanta `BASELINE_LLTF_COMPLEX_PAIRS = 52` dengan komentar "must not drift" justru menjadi sumber drift. Test unit memakai fixture 104 byte/52 paritas sehingga bug tak pernah terlihat. | `[CODE]` dataset_io.py L658 + `[MEASUREMENT]` run fokus: X=0 rows, tensor/observation adapter OK |
| B4 | Trainer (`train_activity_model.py`) **sudah** toleran 51 paritas (`_lltf_pair_count` L139–160; `extract_window_features` memakai lebar dari data), tetapi **header yang di-export membekukan 52** (L410–411, konstanta modul L21–22). Jadi training berjalan; hasil export tetap ditolak firmware. | `[CODE]` |
| B5 | Perbedaan gerbang trainer vs firmware: trainer menerima `data_length in (X, X-2)` (kompaksi first_word_invalid, L85–93), firmware hanya panjang eksak 104 — satu-satunya alasan classifier iners. | `[CODE]` |

### 2.3 Fitur dan windowing

- Fitur = 16 band `log1p(mean |Δamplitude|)` antar frame berturut dalam window; **delta-only** — tidak ada komponen absolut/relatif-baseline. `[CODE]` L217–252.
- Window **frame-indexed** (24/12), bukan waktu. Pada data ini ~30 fps (median interval 21,9 ms) ⇒ window ≈ 0,5–0,8 s bervariasi; `EXPERIMENT_HISTORY.md` §7 sudah merekomendasikan jalur timestamp-aware sebagai turunan, terpisah dari baseline. `[CODE]`+`[DATA]`
- Kapasitas antrean 4 frame; overflow → reset `s_frames_processed` (history terbuang, klasifikasi restart). `[CODE]` L98–103.

### 2.4 Labeling pelatihan

`train_from_recordings` L292–313: setiap window dari sebuah take mendapat label take (`FeatureWindow(recording_id, class_name, feature)`); `timeline`/fase tidak dibaca sama sekali. Header hasil render bahkan mencetak peringatan "Experimental take-level labels; overlapping windows are correlated". `[CODE]`

---

## 3. Dataset Audit (C3)

Output lengkap: `dataset_audit.json` (skrip `01_audit_dataset.py`).

| Label | Takes | Frames-prod. windows | Batches |
|---|---:|---:|---:|
| fall_forward | 10 | 214 | 1 |
| fall_backward | 10 | 224 | 1 |
| walking | 10 | 234 | 1 |
| bending | 10 | 230 | 2 (+2 take tanpa batch_id) |
| fast_sitting | 10 | 233 | 1 (+1 tanpa batch_id) |
| object_drop | 10 | 231 | 1 |
| empty_room | 9 | 205 | 1 |
| still_standing | 10 | 212 | 1 |
| still_sitting | 10 | 217 | 1 |
| **Total** | **89** | **2000** | 9 batch + 3 take lepas |

Fakta penting `[MEASUREMENT]`:
- Semua 89 schema v3, status `complete`, eligible audit 89/89, lebar LLTF **51 paritas di semua take**, satu layout unik per take (HT/20MHz/non-STBC/secondary NONE/int8), `first_word_invalid=true` di seluruh frame.
- `subject_id` **null pada 89/89** ⇒ subject-independent split tidak mungkin hari ini.
- `annotations.fall_start/fall_impact = null` dan `annotation_complete=false` pada 20/20 take fall ⇒ tidak ada ground-truth onset fisik; onset harus diturunkan (FSM `motion_samples`, puncak motion, atau cue).
- `audio_cues.mode = visual_only` pada 89/89 (speech `synthesis-failed`, tone `interrupted`; operator mengonfirmasi lanjut) ⇒ patokan waktu instruksi = event visual dengan offset firing terdokumentasi per take.
- Missing take: `#005` di batch fast_sitting dan bending. Selain itu 3 take tanpa `batch_id` (`20261104T154653Z_bending_001`, `20261104T155021Z_bending_001`, `20261104T154615Z_fast_sitting_001`) adalah **nomor satu yang muncul lagi** setelah batch di-restart — inilah perwujudan nyata bug "nomor take restart per batch": tidak ada tabrakan nama file (timestamp berbeda), tetapi penomoran tidak lagi mengidentifikasi take secara unik secara manual. `[DATA]`
- Semua 89 take terekam pada satu hari (2026-11-04) pada satu perangkat/ruang ⇒ seluruh dataset = **satu environment**.

---

## 4. Fall Recording Analysis — `20261104T160401Z_fall_backward_010` (D1/D2)

### 4.1 Verifikasi metadata vs brief (D1) `[MEASUREMENT]`

Semua nilai brief terkonfirmasi dari file asli, dengan satu koreksi units: durasi 10,031 s; 299 frame; fase 0–4/4–6–10; `fall_start/impact=null`; `annotation_complete=false`; dropped 0; `mean_interval 33,531 ms`; median 21,859 ms; **maksimum 176,962 ms** (brief menulis "176,962" — dalam ms, ≈ 5 interval); `first_word_invalid` true 299/299; stimulus terdokumentasi `http_cloudflare` (target gateway; brief menyebut 64 KB — field `burst_bytes` tidak ada di node stimulus meta ini, jadi klaim "64 KB" **tidak terverifikasi dari file ini**).

### 4.2 Decode payload langsung `[MEASUREMENT]` (fokus_decode.json)

- `valid_b64` 214 byte = LLTF 102 (51 paritas) ‖ HT-LTF 112; `raw_b64` 256 byte buffer driver utuh; byte 0–3 tetap ada di raw, paritas invalid sudah di-clamp keluar dari valid (konsisten commit `3ac4a35`). Tidak ada paritas invalid yang ikut ter-decode; LLTF dibaca dari `lltf_len`, bukan 52.
- Gerbang firmware vs payload ini: `fw_would_accept = false` (102 ≠ 104) → take ini, dan seluruh dataset, tak pernah diklasifikasi firmware.

### 4.3 Tiga fase (D2) `[MEASUREMENT]` (d2_stats_focus.json, figures/focus_*)

| Fase | frames | mean amp | std | mean abs diff | temporal energy |
|---|---:|---:|---:|---:|---:|
| pre 0–4 s | 123 | 23.57 | 7.90 | 2.05 | 44 k |
| action 4–6 s | 56 | 23.38 | 8.89 | 3.75 | 83 k |
| post 6–10 s | 120 | 22.82 | 10.15 | 3.18 | 136 k |
| post-late 8–10 s | 62 | — | — | — | — |

- Mean amplitude **tidak** bergeser antar fase (23,6→22,8) — perubahan terjadi **per-subcarrier** (profil), dan deviasi profil mutlak rata-rata terhadap baseline pre justru **naik** di post-late (2,32 action → 5,88 post-early → **6,90 post-late**). std per frame dan antar-subcarrier ikut naik (7,9→10,1 / 2,2→6,1). `[DATA]`
- Motion ter-smooth (30 frame): pre 1,98 → action 3,61 → post 3,19 (ratio post/pre **1,61**); puncak di **5,99 s** (median lintas-take: forward 5,43 s, 10/10 dalam 4–6 s; backward **6,11 s**, hanya 2/10 dalam 4–6 s — puncak jatuh ke belakang konsisten melewati batas fase 6 s). `[MEASUREMENT]`
- Onset independen dari FSM perangkat (`motion_samples`): transisi `motion_status false→true` pada t=**5,615 s** (ts_ms 1614065 − anchor 1608456), kembali false 8,325 s. Cue visual fall_action firing 4,039 s. **[DATA]** Selisih cue→FSM ≈ 1,6 s: operator mulai bergerak setelah cue; batas fase 4 s bukan onset fisik. Konsisten dengan pernyataan pengguna bahwa gerakan dimulai saat laptop bersuara — bukan bug eksekusi.
- Persistensi: 32/120 frame post melampaui p95 motion fase pre ⇒ aktivitas tidak kembali ke level pre dalam 4 s pasca-jatuh, tapi juga tidak konstan (lihat §5.4 decay).

**Peringatan yang diminta mandat:** angka 4 s / 6 s adalah batas **instruksi**, bukan ground truth fisik. Onset fisik terbaik yang tersedia = transisi FSM (tersimpan untuk 20/20 take fall via `motion_samples`) atau puncak envelope; anotasi manual kosong.

---

## 5. Post-Fall CSI Analysis (D3)

### 5.1 Desain simetris pada dataset penuh `[MEASUREMENT]` (d3_results.json)

Baseline = window take sendiri berpusat < 4 s; kontrol "still→still" (378 window dari 29 take idle) vs "still→after-fall" (170 window dari 20 take fall); LOO nearest-centroid pada vektor perubahan 16-band:

- **Akurasi 75,9%** (confusion: fall→fall 108, fall→still 62; still→still 308, still→fall 70).
- Magnitudo perubahan: kontrol 0,64 vs after-fall 1,28 → **~1,98×** (bukan 6,3× yang saya kutip sebelumnya; lihat §5.5 retraction).
- Dalam-sesi absolut (pre vs post window take fall yang sama, tanpа baseline): LOO **77,9%** — arah berbeda terpisahkan tanpa mengenal sesi.

### 5.2 Confound identitas sesi `[MEASUREMENT]`

Profil absolut fall-pre vs still_standing (dua-duanya berdiri, batch berbeda) terpisah **79,3%** oleh nearest-centroid LOO — dua kelompok yang secara postur sama seharusnya TIDAK terpisahkan. Artinya sebagian daya pemisahan profil absolut adalah sidik jari sesi/posisi. Karena itu **profil absolut tidak dipakai sebagai bukti**; hanya dipakai sebagai kontrol.

### 5.3 Uji tiga kelas — batasan terpenting `[MEASUREMENT]` (d3_multiclass.json)

still (378) vs after-fall (170) vs after-other-action (255; walking/bending/fast_sitting/object_drop fase ≥7 s): **akurasi 49,9%**; fall-post → other-action 22,4% dan → still 22,4%; other-action → fall 32,9%. Magnitudo perubahan: still 0,64 < other 0,88 < fall 1,28 (rata-rata; median 0,57/0,82/0,96) — besaran berbeda, **arahnya tidak cukup terpisah**. Kesimpulan: fitur profil saat ini menangkap "telah terjadi perubahan keadaan" (deteksi + konfirmasi kejadian) tetapi bukan "perubahan itu adalah jatuh". Kelas pembanding wajib berikutnya: lying-down dan kneeling **tidak ada di dataset** sehingga kontras "Normal still → intentionally lying down / kneeling" dari mandat **tidak dapat diuji** (FallDar/PIF9D di §6 menangani kontras itu; kelas tersebut perlu direkam).

### 5.4 Dekay dan stabilitas `[MEASUREMENT]`

Magnitudo perubahan after-fall menurun terhadap waktu (Spearman ρ = −0,58, p = 8e−17; mean ‖Δ‖ 1,65 pada 6–8 s → 0,82 pada 8–10 s) — namun masih ~1,3× kontrol still, dan deviasi profil per-subcarrier pada take fokus justru naik di 8–10 s (6,90). Dua pengukuran tidak bertentangan: yang pertama menghitung delta-band (motion features), yang kedua profil amplitudo absolut. **Risiko metodologis:** drift kanal alami (AGC/termal) juga meningkatkan deviasi profil terhadap baseline seiring waktu; kontrol still→still kita (0,64) sudah memasukkan drift 0–10 s, jadi perbedaan fall masih berdiri, tapi baseline yang panjang (>10 s) belum teruji. `[HYPOTHESIS]` untuk diuji di sesi lebih panjang.

### 5.5 Koreksi terbuka atas klaim saya sebelumnya `[MEASUREMENT]`

| Klaim lama | Status kini pada dataset 89 take |
|---|---|
| LOO simetris 86% (n=20 vs 29 window) | **76%** dengan n=170 vs 378 — arah bertahan, besaran turun |
| Rasio magnitudo 6,3× (0,285 vs 0,045) | **~2×** (1,28 vs 0,64) — definisi magnitudo lama (delta-window ter-norm) tidak terproduksi ulang persis |
| fall-pre vs still_standing 100% | **79%** — confound sesi tetap nyata, tidak se-ekstrem dulu |
| post-fall elevated di 9/10 fwd & 10/10 bwd | **7/10 fwd, 9/10 bwd** (rasio mean-smooth post≥pre >1,0; take kini berbeda: 10 take fall per arah dari batch 16:00) |
| "51 window sepenuhnya 4–6 s; still ~634; rasio 1:8" | Lihat §10.2 — 51→55; 634 tidak terproduksi ulang |

Angka lama dihitung sebelum take tambahan (still/empty/bending fast_sitting susulan) masuk; tidak ada yang dipalsukan, tetapi tidak satu pun boleh dikutip lagi tanpa label "dataset pra-Nov 5".

---

## 6. Literature Review (E)

Verifikasi: setiap DOI diselesaikan via api.crossref.org pada sesi ini (metadata judul/penulis/tahun dikonfirmasi mesin). Ringkasan jujur — angka hasil hanya yang tercantum di abstrak/halaman resmi yang bisa diakses; yang tidak terverifikasi ditandai.

| Paper | DOI/URL terverifikasi | Inti metode | Hasil yang dilaporkan | Relevansi proyek ini |
|---|---|---|---|---|
| **WmFall: WiFi-based multistage fall detection with CSI** — Yang, Xiong, Shao, Niu, *Int. J. Distributed Sensor Networks* 14(10), 2018 (open access CC-BY) | [10.1177/1550147718805718](https://doi.org/10.1177/1550147718805718) (Crossref: judul+penulis+tahun terverifikasi) | Deteksi **multi-tahap**: amplitudo CSI → segmentasi aksi jatuh per fase (falling / after-fall), model sequential | Angka akurasi **tidak saya verifikasi dari teks lengkap** pada sesi ini (halaman SAGE diblokir bot); jangan dikutip dari ingatan | kerangka "fase" (pre/falling/post) yang mandat B usulkan persis arsitektur WmFall; bukti bahwa pendekatan satu-window-biner bukan state of the art |
| **Deep Learning-Based Fall Detection Using WiFi CSI** — Chu, Cumanan, Sankarpandi, Smith, Dobre, *IEEE Access*, 2023 | [10.1109/access.2023.3300726](https://doi.org/10.1109/access.2023.3300726) | Dataset multi-lingkungan (>700 sampel CSI), CNN/GRU dsb. | **>96%** akurasi lintas 4 lingkungan, hingga 99% di lingkungan tertentu (per abstrak halaman York pure + IEEE) | pembanding akurasi; catatan: jumlah subjek kecil seperti kita; transfer antar-ruangan tetap masalah terbuka |
| **TCS-Fall: Cross-individual fall detection system based on CSI and time-continuous stack method** — Zhou dkk., *Digital Health* 10, 2024 | [10.1177/20552076241259047](https://doi.org/10.1177/20552076241259047) | Time-continuous stacking untuk **cross-individual**; real-time | **AUC 0,999** pada test set (per abstrak PubMed: [PMID 38840661](https://pubmed.ncbi.nlm.nih.gov/38840661/)) | menjawab langsung kelemahan terbesar kita (generalisasi antar subjek) — tetapi butuh data multi-subjek yang belum ada |
| **Device free human activity and fall recognition using WiFi CSI** — Damodaran, Haruni, Kokhkharova, Schäfer, *CCF Trans. Pervasive Computing & Interaction* 2, 2020 | [10.1007/s42486-020-00027-1](https://doi.org/10.1007/s42486-020-00027-1) | Recognisi aktivitas + fall device-free pada CSI amplitudo | Hasil kuantitatif **tidak terverifikasi** pada sesi ini (Springer menolak akses otomatis); jangan mengutip angka "96%" untuk paper ini — angka 96% adalah milik Chu 2023 | fondasi fitur amplitudo-only yang sepadan dengan hardware satu-antena kita |

Tambahan terverifikasi sebagian (untuk penelusuran lanjutan, angka belum diverifikasi): dataset **FallDar** (606 fall / 1049 non-fall instances, 3 relawan — registrasi sdp8.net) dan **PIF9D** (tidak ditemukan lewat Crossref pada sesi ini — status referensinya: belum terverifikasi). Pelajaran lintas-paper `[PAPER]`: (1) evaluasi per-**event** dengan ambang k-of-n adalah norma, bukan per-window; (2) post-fall/after-fall diperlakukan sebagai fase terpisah (WmFall); (3) claim produksi selalu multi-subjek; satu-subjek hanya sah untuk studi kelayakan.

---

## 7. Labeling Strategy Comparison (F)

Jumlah window aktual (dataset_audit + skrip 06; waktu riil berbasis centre window):

| Skema | Distribusi |
|---|---|
| Take-level (status kini) | fall 438 / non_fall 1562 — **~55% window fall berada pada fase still** (pre 156 + post 243 dari 438 window fall take, berbasis centre) ⇒ label noise struktural |
| Phase-aware centre-based | fall_transition **94**; fallen_still **138**; normal_still **1316−…+** ; other_action 165; other_still ~500 (lihat g3h_results.json class_counts) |
| Phase-aware konservatif (window sepenuhnya dalam satu fase) | fall_transition **55** (27 fwd + 28 bwd); fully-pre 156; fully-post 143; **mixed 84** dibuang sebagai ambiguous |

**Jawaban 7 pertanyaan mandat:**
1. *Apakah post-fall tetap berlabel fall?* Untuk keluaran biner event: ya — pasca-jatuh adalah **bagian dari episode jatuh** (status "butir pertolongan"), dan §5.1 membuktikan sinyalnya nyata. Tapi untuk **training**, gabungkan sebagai kelas internal sendiri (`fallen_still`), jangan di-biner dengan transisi: ciri keduanya beda total (delta-motion vs profil).
2. *Bagian kejadian atau aktivitas baru?* Keduanya benar di dimensi berbeda: ontologically aktivitas baru (orang diam di lantai), epistemically bagian kejadian (bukti konfirmasi). Karena itu state machine (§11) — bukan label tunggal — yang berhak memegang status.
3. *Label menggambarkan aktivitas saat ini atau riwayat kejadian?* Fitur window-only hanya bisa menggambarkan **aktivitas saat ini**; "riwayat kejadian" adalah properti state, dan melabeli window post-fall sebagai "fall" dengan fitur still hanya mengajarkan model mengidentifikasi sesi (§5.2). Pisahkan: label window = kondisi; status sistem = riwayat.
4. *Classifier satu window cukup untuk event?* Tidak. 55–94 window transisi per dataset dan puncak jatuh sering di luar window aksi (backward: 8/10 lewat 6 s); satu window ≈ 0,5–0,8 s dengan jitter. Event butuh agregasi temporal (k-of-N ≥ 2, atau model sequence).
5. *Perlu state machine?* Ya — normal → candidate (skor transisi melewati θ) → **confirmed** (k-of-n) → fallen_still (profil-relatif mengunci + alarm latch) → recovered (baseline kembali + tidak ada motion ≥ T). Bukti pendukung: persistensi post-fall §5.1/5.4; penolakan: fallen_still ≠ other_still belum terpisah (§5.3) sehingga konfirmasi "ini jatuh" tetap harus dari fase transisi.
6. *Bagaimana mencegah post-fall satu take mengacaukan normal_still take lain?* Label per fase (bukan per take) + split per-take/per-sesi (GroupSplit) + baseline kausal per take; window ambiguous di batas dibuang. Selama post-fall berlabel `fall`, model linear akan menolak setiap post-state di mana pun — persis kegagalan yang sekarang.
7. *Jatuh lalu bangkit?* Belum teramati di dataset (tidak ada take get-up; post-fall semua ≤ 4 s). State machine butuh state `recovered` dengan timeout + bukti kembali-ke-baseline; desain **BELUM DAPAT DIPUTUSKAN** penuh sampai data get-up ada.

Perbandingan: **F1 take-level** = status kini, salah dua arah (noise label + memaksa firmware biner). **F2 phase-aware** = minimal yang benar; biaya: kelas transisi menyusut ke 55–94 window (imbalance, §10). **F3 three-state + event** = paling sesuai literatur (WmFall) dan bukti kita (deteksi ≠ konfirmasi); kompleksitasnya di runtime, bukan dataset. `[REKOMENDASI]` F2 sebagai basis training + F3 sebagai struktur runtime; output eksternal tetap fall/non_fall.

---

## 8. Feature Engineering Comparison (G)

Eksperimen §5 (skrip 06; group holdout utuh-per-take, 5 repeat; class-balanced linear models; metrik balanced-acc):

| Feature set | falling_vs_rest | fallen_still_vs_normal_still | Catatan |
|---|---:|---:|---|
| A. Motion-only (16 band delta — fitur deployed) | 0.87 (lin-SVM) / RF F1 0.66 | 0.83 | Recall tinggi, presisi buruk pada model linear |
| B. Profil absolut (16 band) — **kontrol confound** | 0.93 | **0.98** | Tinggi karena sidik jari sesi (§5.2) — TIDAK direkomendasikan |
| C. Motion + baseline-relative (16+16, kausal) | **0.90** (logistik, bal) | **0.96** (logistik F1 0.91; RF F1 0.93) | Kombinasi sah terbaik dua tugas |
| D. Motion + relative (subset 8) | 0.89 | 0.97 (bal) | Sedikit lebih baik di bal, F1 setara — varian ringkas untuk ESP32 |

H1 (**motion saja tak cukup untuk pasca-jatuh**): didukung — set A 0.83 vs C 0.96 pada fallen_still. H2 (baseline-relative meningkatkan): didukung langsung (Δ +13 poin balanced-acc). H3 (kombinasi terbaik untuk kedua tugas sekaligus): didukung; manfaat kombinasi terbesar datang dari komponen relatif, bukan lebih banyak fitur. `[MEASUREMENT]`

Strategi baseline (G2): yang divalidasi di sini = **startup/awal-sesi** (mean window < 4 s, kausal). Rolling baseline **berbahaya**: menyerap post-fall ke "normal" tepat pada saat kita butuh deviasinya (risiko yang mandat minta jelaskan — nyata, dan ρ=−0,58 decay di §5.4 menunjukkan window post-fall sendiri berubah-ubah; rolling dengan konstanta waktu pendek akan menghapus bukti). Varian freeze-on-candidate layak diuji (E5 di §13). Percentile rolling (median 30 s) plausibel untuk drift AGC tapi belum teruji pada data 10 s.

Phase CSI (G4): payload int8 51 paritas + `first_word_invalid` per-hardware + satu antena + tidak ada kalibrasi → phase tidak andal lintas-sesi `[PAPER: ESP-IDF docs + pengetahuan umum bahwa phase-offset bersifat acak per pasangan radio]`. **REKOMENDASI: jangan menjadikan phase fitur** sampai ada bukti sanitization yang bekerja pada hardware ini; dataset saat ini bahkan tidak menyimpan phase secara terpisah dari IQ mentah (tersimpan, tapi belum diaudit).

---

## 9. Algorithm Comparison (H)

Dari matriks lengkap `g3h_results.json` (11 model × 4 feature set × 2 tugas), pola: linear (logistik/SVM/lda) ≈ ensemble pada set C; tree ensembles unggul F1 di tugas falling yang sangat imbang (RF F1 0.66 vs logistic 0.47 pada set A); RBF-SVM tidak stabil antar tugas (0.84–0.94) ⇒ sensitivitas skala fitur. Ranking praktis untuk dataset 2000 window/89 take:

| Peran | Pilihan | Alasan |
|---|---|---|
| Baseline | Nearest-centroid / logistic 16-band | sudah ada di firmware (setelah bug B1 diperbaiki); titik-tolak ukur |
| **Model utama** | **Logistic regression 32 fitur (C) atau linear-SVM** | performa tertinggi sah (0.90/0.96), Inferensi = dot-product — trivial di ESP32, interpretable via bobot per band |
| Pembanding | RandomForest set C | F1 tinggi di tugas imbang; cek apakah non-linear menambah sesuatu yang nyata; deployment berat (100–200 tree) |
| Layak diuji kemudian | 1D-CNN/GRU pada tensor `[51,24]` (adapter `to_time_series_tensor` sudah berfungsi) | fase transisi backward melewati batas window — model sequence menangani onset/peak lintas-window; tapi butuh >20 take fall sebelum dicoba, dan tidak akan ter-deploy di MCU |
| Two-stage (H5) | Stage-1 transisi (falling_vs_rest) + stage-2 konfirmasi (fallen_still_vs_normal_still) | kedua tugas terpisah memiliki akurasi tinggi sendiri (0.90; 0.96) dan jawaban §5.3 (stage-2 tidak bisa identifikasi jenis kejadian, hanya konfirmasi "ada sesuatu") — karena itu stage-2 **hanya boleh mengonfirmasi kandidat dari stage-1**, bukan memicu alarm sendiri | `[REKOMENDASI]` |

Per-window classifier tunggal tidak memadai (see §7 Q4); deep learning belum terdukung ukur dataset (94–138 window positif, satu subjek).

---

## 10. Dataset Split and Evaluation (I)

### 10.1 Kebocoran split saat ini `[CODE]`
- Trainer hanya mendukung `--test-take` (whole-take holdout eksplisit) — baik; **tetapi** tanpa flag itu semua window masuk train dan report hanya menyebut "these training results are not evaluation" (peringkatan ada, proteksi tidak). 
- Window yang berdekatan (stride 12, overlap 50%) selalu tetangga satu take ⇒ **jangan pernah** split per-window; GroupSplit per-take minimum, idealnya per-batch (sesi) karena satu batch = satu setting posisi.

### 10.2 Re-count angka klaim (I2) `[MEASUREMENT]`
- "438 window fall" — **terkonfirmasi** (224 bwd + 214 fwd).
- "51 window sepenuhnya di 4–6 s (24 fwd + 27 bwd)" — **tidak lagi 51**: konservatif fully-action = **55** (27 fwd + 28 bwd) dengan konvensi indeks-frame yang sama; jika pakai waktu riil centre, 94 window. Definisi lama kemungkinan ambang berbeda + dataset lama.
- "still ~634; rasio ~1:8" — **tidak terproduksi ulang**: take still_standing+still_sitting kini 429 window (+ empty_room 205 → 634 total jangkar still — angka 634 lama kemungkinan dihitung saat dataset sudah berisi ini; tidak dapat direkonstruksi presisi; rasio aktual fully-action 55 : 634 = **1:11,5**; centre-based 94:634 = 1:6,7).
- "24+27" terbagi arah — kini **27+28**. Semua kutipan lama harus dianggap historis (lihat tabel §5.5).

### 10.3 Imbalance dan metrik (I3)
Strategi yang sah di sini: **class weighting** (sudah dipakai eksperimen), **cap window per-take-per-kelas**, dan undersampling kontrol still. Yang **dilarang metodologis**: duplikasi/SMOTE pada window overlap dari 20 kejadian fall — jumlah bukti independen tetap 20 take; bootstrap window bukan subjek baru.
Metrik wajib dua tingkat: per-window (precision/recall/F1 fall, specificity, balanced-acc, confusion) **dan** per-event: event-recall (≥1 deteksi benar dalam [onset, onset+3 s] dari 20 event), latency sejak **onset tersimpulkan** (FSM transisi, bukan cue 4 s — §4.3), false-alarm/jam dari idle takes (empty_room 9 take = 90 s; still 20 take = 200 s → laporkan FA/menit-detik-terpasang, dengan catatan basisnya kecil), flicker-rate (transisi status per menit). Status `fallen_still` yang dipertahankan setelah event benar **tidak dihitung** sebagai false alarm (definisi masa toleransi latched-alarm, §11). Anotasi onset manual (`annotation_complete`) harus diisi dulu agar latency jadi ground-truth; untuk kini gunakan FSM sebagai onset proxy `[DATA]`.

---

## 11. Firmware Runtime Implications (J) — tanpa implementasi

Status kini: classifier iners (B1); jika bug diperbaiki, yang tersisa adalah klasifikasi per-window tanpa memori apa pun (`classify_window` → publish; "DEMO only"). Yang dibutuhkan runtime, berjenjang `[REKOMENDASI]`:

1. **K-of-N voting** (mis. 2 dari 3 window transisi berturut): menekan flicker; latency tambah ≤ 1 window (≈0,5 s); murah (uint8 counter).
2. **State machine** `NORMAL → CANDIDATE → ALARM_LATCHED(fallen_still) → RECOVERED`: butuh (a) skor transisi stage-1, (b) deviasi profil-relatif stage-2 sebagai pengunci persistensi (bukti §5.1), (c) timeout reset; alarm latch agar status "butuh pertolongan" bertahan walau orang diam. Reset-on-queue-overflow sekarang (`s_reset_on_next_frame`) akan menghapus jejak CANDIDATE — perlu ditinjau saat implementasi.
3. **Baseline kausal on-device**: jalankan hanya saat state NORMAL; freeze saat CANDIDATE+ (mencegah post-fall menjadi baseline diri sendiri).
4. Trade-off: k↑ → FA↓ tapi latency↑; state machine dengan stage-2 ↓ FA pasca-kejadian tapi **tidak bisa** membedakan jatuh-vs-duduk-pascakegiatan (§5.3) — konfirmasi jenis tetap 100% bergantung fase transisi; satu orang-per-ruangan membatasi klaim FA lintas lingkungan sampai ada rekaman multi-sesi.
5. Semua item di atas = perubahan `main/` → tunduk preflight + changelog + trailer `Docs:` (AGENTS.md) dan **dilarang dalam mandat ini**; catatan kepatuhan: item 1–3 belum diuji di perangkat ⇒ `BELUM DIUJI`.

---

## 12. Recommended Architecture

```text
ESP32 (per frame)                       Host/training                          Runtime (usulan, belum diimplementasi)
csi_data ──esp-radar compaction──▶ valid 102B LLTF(51)‖HT112   ──▶ amplitude[51] ─┐
   windows 24fr/stride12 (frame-indexed; turunan ts-aware terpisah)               │
   motion[16] = log1p mean|Δ| per band  ◀── (fitur deployed)                      │
   profile[16]= log1p mean amp per band ◀── BARU                                  ▼
   baseline[16]= mean profile (window pusat<4s, kausal, freeze-on-candidate)      stage1: linear (motion+rel) → falling?
   relative[16]= profile − baseline  ────────────────────────────────────────────▶ stage2: rel-magnitude → konfirmasi persisten
                                                            state machine NORMAL→CANDIDATE→LATCHED→RECOVERED (k-of-N, timeout)
                                                            output tetap fall|non_fall
```
Prasyarat keras sebelum apa pun: perbaiki gerbang layout (104→102/51 atau terima kedua panjang seperti trainer) + regenerasi `activity_model_data.h` + sinkronkan `BASELINE_LLTF_COMPLEX_PAIRS`/`to_feature_matrix` — semuanya implementasi, **di luar mandat ini**.

---

## 13. Prioritized Experiment Plan (K)

| # | Hipotesis | Eksperimen | Dataset | Status hari ini |
|---|---|---|---|---|
| E1 | H1 | fallen_still vs normal_still dengan set A saja, group-split | dataset kini | **TERJALAN** (0.83) — H1 didukung, confidence MEDIUM (satu subjek) |
| E2 | H2 | uji hal yang sama dengan set C (tambah profil-relatif) | dataset kini | **TERJALAN** (0.96) — H2 didukung, MEDIUM; valid penuh butuh sesi baru yang tidak pernah dilihat |
| E3 | H3 | falling_vs_rest A vs C; ablation bobot rel | dataset kini | **TERJALAN** (0.87→0.90) — didukung MARGINAL (Δ kecil, satu subjek) |
| E4 | H4 | three-state (normal/falling/fallen) vs biner; ukur efek pada fallen_still & FA idle | dataset kini + label phase-aware | **BELUM DIUJI** — bisa dengan data sekarang; kendala: fallen_still≠other_still belum terpisahkan (§5.3) |
| E5 | H5 | two-stage + k-of-N di replay offline; latency & FA/ jam | dataset kini + `motion_samples` sebagai onset | **BELUM DIUJI** — butuh simulator runtime host-side |
| E6 | — | **Rekam kelas baru**: lying-down intentional, kneeling, get-up-after-fall; ≥3 sesi; ≥2 subjek; subject_id diisi | baru, wajib | **DATA BARU** — tanpa ini §5.3 & klaim "jatuh vs bukan-jatuh pascakejadian" mentok |
| E7 | — | Sesi panjang (>60 s) dengan jatuh di tengah: uji rolling vs frozen baseline, dekay post-fall (§5.4) | baru | **DATA BARU** |
| E8 | — | Konfirmasi runtime B1 di perangkat (log `Skipping CSI frame` per frame) | perangkat saat ini | Diperbolehkan begitu mandat berakhir; sekarang tetap `BELUM DIUJI (runtime)` |

Kriteria keberhasilan E2/E3: balanced-acc set C − set A ≥ +5 poin pada group-split per-batch (bukan hanya per-take) dengan CI non-overlapping (bootstrap per-take). Risiko bias terbesar di semua eksperimen kini: 1 subjek, 1 ruangan, 1 hari, 1 posisi perangkat.

---

## 14. Final Technical Recommendations (Tabel Keputusan M)

| Komponen | Opsi | Rekomendasi | Bukti | Confidence | Alasan singkat |
|---|---|---|---|---|---|
| Target labeling | take-level / phase-aware / three-state event | **phase-aware untuk training + three-state untuk state runtime**; keluaran tetap fall/non_fall | §5, §7, `[CODE]` B-blocker | HIGH (keburukan take-level), MEDIUM (rincian tiga-state) | take-level = label noise struktural; bukti post-fall nyata tapi tak bisa pisahkan jenis kejadian |
| Penanganan pre-fall | label non_fall / drop | **label `normal_still`** (fase pre window sepenuhnya <4s) | §10 counts | HIGH | pre-fall = berdiri diam, identik kelas still lain |
| Fall transition | window utuh dalam fase / centre-based | **fully-in-phase + mixed dibuang (ambiguous)** | konservatif 55 window | MEDIUM | boundary 4/6 s bukan onset fisik (§4.3); hindari mencampur transisi dengan still |
| Post-fall | relabel still / label fall / kelas sendiri | **kelas internal `fallen_still`, dipetakan ke status episode fall di runtime** | §5.1, §5.3 | MEDIUM | sinyalnya nyata (76%) tapi tidak event-specific (50%) |
| Baseline | startup / rolling / percentile / freeze-on-candidate | **startup (kausal) + freeze-on-candidate**; rolling ditunda | §8 risiko absorbsi; §5.4 | MEDIUM | rolling berisiko menyerap post-fall; belum ada data >10 s |
| Fitur CSI | motion-16 / +relative-16 / +absolut / phase | **motion[16] + relative[16]**; tanpa absolut, tanpa phase | §8 (0.90/0.96); §5.2; §8 G4 | HIGH untuk dua komponen; HIGH menolak phase/absolut | absolut = bocor identitas sesi; phase tak tepercaya di hardware ini |
| Window/stride | frame-indexed vs time-aware | **pertahankan frame-indexed sbg baseline; turunan time-aware terpisah** | `[CODE]` EXPERIMENT_HISTORY §7 | HIGH | mandate preflight repo: jangan ubah extractor sebelum akuisisi selesai |
| Missing frame | zero-fill / skip | **skip (drop frame, reset history)**; jangan invent | `[CODE]` B3/dataset_io design rule | HIGH | nilai buatan = sampel hantu |
| Model utama | logreg / linSVM / RF / RBF / DL | **logistic regression (set C)** | §9 | MEDIUM | linear = deployable, terbaik sah dua-dua tugas; RF sebagai challenger |
| Model pembanding | RF / RBF-SVM / nearest-centroid | **RF (set C)** + baseline centroid | §9 | MEDIUM | mengukur nilai non-linearitas pada data kecil |
| Balancing | class weight / cap / SMOTE | **class_weight + per-take cap**; **no SMOTE** | §10.3 | HIGH | bukti independen = take, bukan window |
| Split | window / take / batch | **GroupSplit per-take; minimal satu uji per-batch (LOSO sesi)** | §10.1 | HIGH | overlap window + sidik jari sesi (§5.2) |
| Metrik | accuracy / dua-tingkat | **event-level (recall, latency dari onset proxy FSM, FA/menit) + window-level (bal-acc, F1, confusion)** | §10.3 | HIGH | accuracy pada rasio 1:11 tidak informatif |
| Runtime confirmation | per-window / k-of-N / state machine | **k-of-N (2/3) + state machine + alarm latch** | §7 Q4–5, §11 | MEDIUM — `BELUM DIUJI` di perangkat | satu window ~0,5–0,8 s dengan jitter & peak melintas batas |
| Alarm behavior | latch persist / timeout reset | **latch sampai `recovered` (baseline kembali + no-motion ≥T)**, T **BELUM DAPAT DIPUTUSKAN** (butuh data get-up E6) | §5.4 decay; belum ada bangkit | LOW | risiko: latch palsu bertahan lama |
| Deployment ESP32 | regenerate header + gate fix dulu | **perbaiki B1–B4 (implementasi, Wewenang user setelah laporan ini)**; model 32-float linear ≈ 0,5 KB | §2.2 | HIGH untuk diagnosis | classifier kini tidak menghasilkan apa-apa |

Yang **tidak boleh diimplementasikan karena kurang bukti**: (a) relabel post-fall→still (retracted §5.5), (b) fitur profil absolut mentah sebagai fitur produksi (confound §5.2), (c) phase features (G4), (d) SMOTE antar window (I2), (e) CNN/LSTM sebelum data berlipat (H), (f) rolling baseline sebelum E7.

---

## 15. Unresolved Questions

1. **Onset fisik tanpa anotasi** — `fall_start/impact` kosong 20/20; FSM proxy onset ≈ +1,6 s setelah cue (satu take terverifikasi; perlu distribusi lintas take). Tindakan: isi anotasi (proses recorder, bukan analisis).
2. **Apakah deviasi profil post-fall bertahan > 10 s / vs drift AGC-termal** — data 10 s tidak menjawab; butuh E7.
3. **fallen_still vs other_still** — 50% pada 3-kelas; tanpa lying-down/kneeling/get-up (E6) kontras wajib mandat tidak dapat diuji.
4. **Generalisasi lintas sesi/subjek** — mustahil diukur hari ini (`subject_id` null, 1 sesi/hari); semua angka §5/§8 = bukti kelayakan dalam-satu-lingkungan, confidence MEDIUM per M-rule.
5. **Status runtime classifier iners** — bukti statis lengkap (`[CODE]`+`[DATA]`), konfirmasi log perangkat (`Skipping CSI frame …`) belum dilakukan (dilarang dalam mandat).
6. **Burst stimulus sebenarnya 64 KB?** — node `stimulus` take fokus tidak memuat `burst_bytes`; klaim brief "64 KB" tidak terverifikasi dari file ini.
7. **Angka hasil WmFall/Damodaran** — DOI+metadata terverifikasi Crossref; angka akurasi belum (akses penuh diblokir); jangan dikutip sebelum teks lengkap dibaca.
8. **Take `#005` yang hilang & 3 take tanpa batch** — pola sesuai bug numbering/restart yang sudah didokumentasikan sebelumnya; server `rewrite_index` tetap tanpa jejak take abortif (perbaikan = pekerjaan implementasi terpisah).

---

### Lampiran — artefak reproduksi
- `scripts/01_audit_dataset.py` → `dataset_audit.json` (C3)
- `scripts/02_focus_take.py` → `focus_decode.json`, `window_phase_counts.json`, `motion_series_focus.csv`, `figures/focus_motion_phases.png` (D1/D2/I2)
- `scripts/03_d3_symmetric.py` → `d3_results.json`, `figures/d3_symmetric_separation.png` (D3)
- `scripts/04_d2_stats.py` → `d2_stats_focus.json`, `figures/focus_phase_profiles.png`, `figures/focus_subcarrier_heatmap.png` (D2)
- `scripts/05_d3_multiclass.py` → `d3_multiclass.json`, `figures/d3_change_magnitude_by_class.png` (D3)
- `scripts/06_g3h_experiment.py` → `g3h_results.json` (G3/H)
- `scripts/07_settle_times.py` → `settle_analysis.json`, `settle_summary.json`, `figures/fall_settle_times.png` (tindak lanjut pertanyaan batas akhir jatuh: settle terukur 20/20 take fall)
- `scripts/08_label_durations.py` → `label_durations.json` (analisis durasi label non-fall: settle/ekor-still per label + stabilitas idle; ambang p95 pre tidak sensitif aksi halus, dilengkapi diagnostik energy-after-action-end dan last-1s/pre-median)
- Sitasi preflight: ESP-IDF v5.5.3 `esp_wifi_types_native.h:123` (`first_word_invalid`); enum `WIFI_SIGNAL_MODE_*`/`WIFI_CSI_DATA_TYPE_*` **bukan** milik ESP-IDF — lokal di esp-radar vendored `esp_radar/include/esp_radar.h:93-97,185-188`; `Dokumen: docs/agent-preflight.md`, `docs/EXPERIMENT_HISTORY.md`.
