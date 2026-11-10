# DATA CONTRACT — Kesepakatan format dan semantik data fall detection

- Versi: 1.0-draft (sesi riset `20261104T180944Z`, rev 2.2)
- Ruang lingkup: recorder host, firmware, trainer, evaluator, tool anotasi.
- Status: **dokumen acuan bersama**. Setiap komponen yang bertentangan dengan
  kontrak ini adalah bug di komponen tersebut, bukan sebaliknya.
- Angka yang ditandai **[PENDING]** menunggu pengukuran nyata dan akan diisi
  saat Fase 0 diresmikan (lihat §11).

## 1. Format payload CSI dan layout LLTF

| Layout | Panjang payload | Jumlah pasangan kompleks | `first_word_invalid` | Keterangan |
|--------|----------------|--------------------------|----------------------|------------|
| A (kompaksi) | 102 B | 51 | `true` | klamp-di-sumber (commit `3ac4a35`); 4 byte pertama hardware-corrupt sudah dibuang SEBELUM sampai ke ring buffer |
| B (legacy) | 104 B | 52 | `false` | frame tanpa kerusakan 4-byte pertama (jarang; hanya jika hardware lolos) |

**Kontrak**:

- Panjang ↔ flag **terikat 1-ke-1**. Kombinasi lain = error eksplisit dengan
  log diagnostik: `length`, `first_word_invalid`, `reason`.
- Layout B yang lolos gerbang panjang **tetap menghasilkan offset 52 pasangan**;
  decoding TIDAK menggeser indeks. Tool wajib menyimpan kedua fixture uji.
- Indeks subcarrier setelah klamp (layout A): pasangan-0 = LLTF indeks-2 fisik,
  dst. Ini dibakar dalam konstanta `CLAMP_OFFSET = 2` di decoder bersama
  assertion bahwa flag = true hanya bila panjang = 102.

## 2. Sumbu waktu kanonik dan anchor

- **Sumbu tunggal untuk seluruh pipeline**:
  `t = (host_receive_monotonic_ns − t₀) / 1e9` detik, di mana `t₀` =
  `host_receive_monotonic_ns` frame CSI **pertama** yang lolos validasi layout
  (§1) dalam satu take.
- Timestamp harus monoton non-decreasing. Frame dengan timestamp < sebelumnya
  ditolak dan dicatat di log.
- **Anchor lain disimpan di metadata** (`capture_plan_start_ms_browser`,
  `cue_offset_s`, `performance_now_ms`) sebagai offset terhadap sumbu kanonik;
  konversinya diekspos di tool dan tidak boleh dihitung ulang secara ad-hoc.
- Catatan dari pengukuran: perbedaan antara `t₀` (frame pertama) dan
  `capture_plan_start` = ±0,1–0,25 s — cukup kecil untuk tidak mengubah
  kesimpulan, tapi signifikan untuk window-level boundary assignment.

## 3. Taksonomi label (tiga lapisan)

| Lapisan | Nama | Domain | Dipakai di |
|---------|------|--------|-----------|
| 1 | Activity label | 11 preset recorder (`fall_forward`, `walking`, `idle`, …) | Recorder, metadata mentah, nama file |
| 2 | Temporal phase label | `normal_still` / `fall_transition` / `fallen_still` / `other_action` / `other_still` | Trainer (input labeling), dataset turunan |
| 3 | Binary target | `fall` / `non_fall` | Output eksternal firmware, evaluator event-level |

- Firmware **hanya** memuat kelas lapisan-2 yang diekspor trainer ke header.
  Jangan menulis 11 preset recorder ke `ACTIVITY_MODEL_LABELS` bila model tidak
  dilatih untuk memprediksi 11 kelas.
- Trainer menerima `--class-spec` yang memetakan lapisan-1 → lapisan-2;
  mapping default: semua `fall_*` action phase → `fall_transition`, `fall_*`
  post-phase → `fallen_still`, pre + idle → `normal_still`, non-fall action →
  `other_action`, non-fall post → `other_still`.

## 4. Skema anotasi kandidat

### 4.1 Status tangga verifikasi

```
auto_pending  →  signal_reviewed  →  manual_corrected
```

Level `independently_verified` **TIDAK ADA** (keputusan user: tanpa video).

### 4.2 Field metadata turunan (tidak pernah menimpa data mentah)

| Field | Tipe | Isi |
|-------|------|-----|
| `annotation_method` | string | `"csi_envelope_p95"` (kanon algoritma) |
| `annotation_algorithm_version` | string | `"1.0"` |
| `annotation_parameters` | object | `{ grid_hz: 20, smooth_n: 20, search_offset: -0.5 }` |
| `annotation_status` | enum | salah satu tangga di atas |
| `candidate_onset_s` | float \| null | detik dari t₀ (§2) |
| `candidate_peak_s` | float \| null | |
| `candidate_settle_s` | float \| null | |
| `needs_manual_review` | bool | true → status `auto_pending`, alasan dicatat |

### 4.3 Parameter anotasi timeline-driven (kanon = metode skrip 08)

Skrip anotasi TIDAK meng-hardcode nilai tertentu untuk semua label. Setiap take
membaca parameternya sendiri dari `meta.timeline`:

```python
pre_end       = timeline[0].end_offset_s
action_start  = timeline[1].start_offset_s   # == pre_end secara desain
action_end    = timeline[1].end_offset_s
take_end      = timeline[2].end_offset_s     # boundary terakhir
```

Threshold = p95 dari `motion[offs < pre_end]`.
Onset search mulai `t ≥ pre_end − 0.5` — lihat §4.4 untuk kasusnya.

**Meta tanpa timeline → failed-fast, bukan fallback ke 4.0.**

### 4.4 Kandidat pra-aksi (`pre_action_candidate`)

Karena pencarian onset dimulai `pre_end − 0.5`:

- Jika `candidate_onset_s < action_start` → tandai `pre_action_candidate = true`.
- `pre_action_candidate` **TIDAK otomatis** dianggap onset aktivitas atau onset
  jatuh; status-nya tetap `auto_pending` dengan flag review.
- Alasannya: subjek mungkin menggeser berat badan sebelum cue, atau noise
  ambien kebetulan menembus p95 pada awal window pencarian.
- Review manual bisa mengonfirmasi → `signal_reviewed`, atau mengoreksi →
  `manual_corrected` dengan onset baru.

## 5. Kebijakan window dan frame gap

- Trainer: `WINDOW_FRAMES = 24`, `WINDOW_STRIDE = 12` (dikunci, bukan angka baru).
- Rentang waktu window `[ts_first, ts_last]` ditentukan dari timestamp
  kanonik (§2), **bukan dari indeks frame**.
- Durasi aktual window dilaporkan ke log/metrik (24 frame × interval rata-rata;
  bisa ≈ 0,6 s pada fps ideal, lebih panjang saat rate turun).
- **Validitas window**:
  - Timestamp monoton?
  - Tidak ada gap antar-frame > `MAX_FRAME_GAP_S` **[PENDING: lihat §11]**?
  - Jumlah frame dalam window == `WINDOW_FRAMES`?
  - Jika TIDAK → `window_status = "invalid"`. Window invalid **dibuang dari
    training** tapi tetap tercatat di dataset; evaluator tidak menghitungnya.
  - Jumlah window ditolak dilaporkan sebagai diagnostik pipeline.
- **Larangan**: membuat atau menginterpolasi frame CSI palsu.

## 6. Baseline: definisi dan ekuivalensi chronological replay

### 6.1 Aturan tunggal (SATU, bukan alternatif)

```
baseline[band] = cumulative_mean(log_amplitude[band])
                 atas SEMUA frame SEBELUM ts_first window ini
                 yang status episode = NORMAL.
```

- Window setelah `pre_end` secara otomatis mendapat baseline penuh dari fase
  pre-action (< pre_end), karena akumulasi sudah berjalan sejak t₀.
- Window sebelum baseline siap (jumlah frame < `MIN_BASELINE_FRAMES`
  **[PENDING]**) → fitur relatif **tidak dipakai** di window itu; hanya fitur
  absolut yang masuk model, atau window ini ditandai `NO_DECISION` (§7).
- **Tidak ada window yang baseline-nya memakai data SETELAH window itu.**
  (Ini adalah test kausalitas formal — 3.2 ACTION_PLAN.)

### 6.2 Chronological replay: ekuivalensi training ↔ firmware

**Prinsip**: training offline HARUS menyimulasikan urutan keputusan firmware,
bukan menggunakan label ground-truth untuk mengontrol baseline.

| Aspek | Firmware (runtime) | Trainer (offline) |
|-------|-------------------|-------------------|
| Akumulasi baseline | Frame diproses satu per satu; akumulator di-`update` selama state == `NORMAL` | Replay chronological: frame diproses urut timestamp; akumulator di-`update` selama **prediksi model** (bukan label) menyatakan state == NORMAL |
| Freeze | Saat state machine berpindah ke `CANDIDATE` atau lebih tinggi → akumulator di-freeze | Saat replay state machine (menggunakan prediksi, bukan label) berpindah → hentikan update |
| ALARM_LATCHED | Akumulator tetap frozen | Sama — replay tidak resume update saat latched |
| RECOVERED → NORMAL | Akumulator resume update | Replay: baru resume jika state machine memprediksi `RECOVERED`/`NORMAL` |
| Window invalid / NO_DECISION | Tidak menyentuh akumulator, tidak mengubah episode state | Replay: skip frame, tidak update akumulator |
| Reset episode (frame baru setelah long gap) | `data_gap` tercatat; akumulator TIDAK di-reset (baseline tetap kumulatif sejak t₀, tapi `window_status = invalid` selama belum penuh) | Replay identik |

**Konsekuensi kritis**: jika model keliru memprediksi `normal_still` padahal
sebenarnya `fall_transition`, baseline firmware akan continue updating saat
gerakan jatuh sedang terjadi. Ini adalah perilaku yang sah di firmware dan
**harus** terekam di training replay. Menggunakan label ground-truth untuk
membekukan baseline di training tapi membiarkan firmware mengandalkan prediksinya
sendiri → **train-inference mismatch** yang dilarang kontrak ini.

### 6.3 Statistik dan kriteria [PENDING]

- Statistik baseline: `mean(log1p(amplitude))` per band (16 band), dihitung
  incremental.
- Kriteria "baseline siap": minimal `MIN_BASELINE_FRAMES` frame valid dalam
  state NORMAL **[PENDING — ukur dari data]**.
- Update policy saat NORMAL: setiap frame baru ditambahkan ke akumulator Welford.
- Ekuivalensi diverifikasi dengan **unit test kausalitas**: untuk setiap window,
  assert bahwa baseline tidak memakai data dengan `t ≥ ts_first_window`.

## 7. NO_DECISION — kondisi runtime, bukan kelas model

**Definisi**: kondisi di mana sistem TIDAK menghasilkan prediksi kelas apa pun
(bukan `non_fall`, bukan `fall`).

### 7.1 Trigger

| Kondisi | Penjelasan |
|---------|-----------|
| Baseline belum siap | Jumlah frame NORMAL < `MIN_BASELINE_FRAMES` → fitur relatif tidak tersedia; classifier tidak dipanggil. |
| Window invalid | §5 — gap, non-monoton, jumlah frame kurang. |
| CSI quality di bawah ambang | Misalnya: semua frame dalam window adalah layout-reject (§1), rasio `first_word_invalid` > threshold tertentu **[PENDING]**. |
| Post-overflow, sebelum buffer penuh | Buffer baru di-reset tapi belum cukup untuk membentuk window baru yang valid (§5.4 ACTION_PLAN). |

### 7.2 Perilaku

- State episode (`NORMAL` / `CANDIDATE` / `ALARM_LATCHED` / `RECOVERED`) **tidak
  berubah** saat `NO_DECISION`. Satu window invalid tidak menghapus episode
  yang sedang berjalan.
- Output eksternal = tidak ada alarm, tidak ada status — **bukan** `NON_FALL`.
  Downstream consumer (UI, MQTT) menerima `status: "no_decision"` dan tidak
  menginterpretasikannya sebagai "aman".
- Durasi kumulatif `NO_DECISION` dilaporkan ke log; jika >
  `NO_DECISION_ESCALATION_S` **[PENDING]** → trigger diagnostik peringatan
  (bukan alarm jatuh).

### 7.3 Mengapa bukan kelas keenam

Model 5-kelas dilatih dengan data berlabel phase temporal. Menambah `NO_DECISION`
sebagai kelas akan memaksa trainer melabeli frame-frame "sampah" yang tidak
mempunyai bentuk temporal yang konsisten — sinyal noise bukan kelas aktivitas.
`NO_DECISION` adalah **keputusan di level pipeline sebelum classifier**, bukan
di dalam classifier.

## 8. Mapping lima kelas → output biner + state machine

```
  Model output (5 kelas)
        ↓
  Pemetaan runtime state:
    normal_still   → episode: NORMAL
    fall_transition → episode: memicu CANDIDATE (setelah k-of-N §5.1)
    fallen_still   → episode: mengonfirmasi/mempertahankan CANDIDATE atau LATCHED
    other_action   → episode: tidak memicu; jika sudah CANDIDATE → counter-evidence (flicker check)
    other_still    → episode: mengonfirmasi NORMAL
        ↓
  Output eksternal:
    NORMAL → NON_FALL
    CANDIDATE / ALARM_LATCHED / RECOVERED → FALL (alarm aktif, latched, atau cooldown)
    NO_DECISION → (tidak ada output — §7)
```

- **Indeks kelas di header C** (`ACTIVITY_MODEL_LABELS[]`) **harus sama persis**
  dengan urutan `class_order` yang diekspor trainer. Assert di build-time.
- Model biner tunggal TIDAK bisa mendukung pemisahan pemicu (`fall_transition`)
  vs pengonfirmasi (`fallen_still`) — oleh karena itu 5 kelas.

## 9. Timeline protokol per label (recorder)

| Label | Boundaries | Durasi take | Keterangan |
|-------|-----------|-------------|-----------|
| `fall_forward/backward/lemas/keseleo` | [0, 4, 8, 12] | 12 s | cue=4 s, action window 4–8 s, tail 8–12 s |
| `walking` | [0, 3, 7, 10] | 10 s | |
| `bending` | [0, 3, 7, 10] | 10 s | |
| `fast_sitting` | [0, 4, 6, 10] | 10 s | |
| `object_drop` | [0, 4, 6, 10] | 10 s | |
| `empty_room / still_standing / still_sitting` | [0, 10] | 10 s | single hold phase |

**Batas protokol = scaffolding sesi (instruksi ke subjek), BUKAN batas label fisik.**
Label fisik dari anotasi kandidat (§4) yang timeline-driven.

### 9.1 Kelas jatuh: arah vs cara (manner)

Empat label jatuh (`kind=fall`) berbagi timeline [0, 4, 8, 12] tetapi beda
semantik dan cara penentuan onset-nya:

| Label | Semantik | Pre-action | Onset ground-truth |
|-------|----------|-----------|--------------------|
| `fall_forward` / `fall_backward` | arah jatuh | diam | p95 §4.1 andal (baseline diam) |
| `fall_lemas` | jatuh lemas (collapse lunglai) | **diam** | p95 §4.1 andal — sama seperti arah |
| `fall_keseleo` | jatuh keseleo (collapse lateral terkontrol) | **berjalan** | mark observer `fall_start` (lihat catatan) |

**Catatan onset (terukur, 41 take 2026-11-07):** ambang §4.1 = p95 motion
pre-action. Hanya `fall_keseleo` yang memakai pre-action **berjalan**; tiga
kelas lain (forward/backward/lemas) **diam** sehingga p95 onset-nya andal
(lemas `peak/baseline ≈ 1,1`, onset bersih). Pada keseleo, baseline berjalan
terangkat DI ATAS puncak jatuh yang halus (`peak/baseline ≈ 0,56`) → **0/11**
onset p95, dan change-point level pun gagal (pulih 3/11, meleset s.d. +2,9 s):
**tidak ada ambang level yang bisa mengambil onset-nya** karena jatuh
sebenarnya lebih lemah daripada berjalan. Menurunkan persentil (mis. p50)
bukan solusi — onset hanya berpindah ke tepi window (`pre_end − 0,5`) dan
menyalakan `pre_action_candidate` (deteksi palsu). **Maka onset `fall_keseleo`
= `annotations.fall_start` (mark observer/spasi), level `manual_corrected`
§4.1**; p95 hanya konfirmasi sekunder (dan absen saat berjalan). Mark spasi
tervalidasi memotret fisik: `fall_start` mendahului rise p95 ~0,2–0,6 s, motion
pasca-`fall_impact` runtuh ke ~⅔ level jatuh.

**Deteksi (runtime, bukan anotasi) "berjalan→tersandung→jatuh":** tidak bisa
lewat ambang level; harus **bentuk + dua tahap** ala §6/§7 (`fall_transition` →
`fallen_still`). Diskriminator terkuat = **settling ke diam pasca-puncak
(11/11 keseleo)**, yang tidak dimiliki berjalan biasa. Ini wilayah Fase 3/5
(model fitur relatif per-band + state machine), BUKAN alat anotasi.

Capture-end, progress bar, dan cue akhir **diturunkan dari boundary terakhir**
(bukan hardcoded 10 s).

## 10. Metrik: penamaan dan interpretasi

| Nama metrik | Titik referensi | Interpretasi |
|-------------|----------------|--------------|
| `CSI-proxy event recall` | `candidate_onset` (signal-derived) | ≥1 deteksi dalam `[candidate_onset, +3 s]` per event-take |
| `CSI-proxy latency` | `candidate_onset` | Waktu deteksi minus onset kandidat |
| `Cue-to-detection latency` | Timestamp cue protokol | **Metrik protokol**; = reaksi manusia + eksekusi gerakan + latency CSI; BUKAN latency fisik murni |
| `Physical fall latency` | Onset jatuh fisik (tanpa referensi) | **TIDAK DAPAT diverifikasi** tanpa video/referensi fisik independen; **tidak akan diklaim** |
| `Physical event recall` | Event fisik | **TIDAK DAPAT diverifikasi**; **tidak akan diklaim** |
| Window-level (bal-acc, F1, confusion matrix) | Label fase (§3) | Diambil pada window valid saja |
| False alarm | Episode `NORMAL` yang memicu alarm | Laporkan **jumlah mentah + total menit observasi** (bukan rate, sampai N cukup) |

- `fallen_still` pasca-event-benar = masa toleransi latch, **bukan** FA.
- Istilah untuk §2.4 ACTION_PLAN: **"karakterisasi segmentasi kandidat gerakan
  CSI lintas kelas aktivitas"** — bukan "uji spesifisitas deteksi jatuh".

## 11. Angka yang masih menunggu pengukuran

| # | Parameter | Sumber pengukuran | Perkiraan awal |
|---|-----------|-------------------|----------------|
| P1 | `MAX_FRAME_GAP_S` (window invalid threshold) | Distribusi inter-arrival 89 take yang ada (belum dihitung — perlu skrip) | aturan kandidat: k× median inter-arrival take itu sendiri; nilai k ditentukan dari data |
| P2 | `MIN_BASELINE_FRAMES` (baseline siap) | Konvergensi incremental mean per band atas recording idle yang ada | aturan kandidat: jumlah frame sampai delta mean < ε; ε dari data |
| P3 | `guard_s` pasca-settle (window `fallen_still` mulai) | Fit dari distribusi settle data 07/08; dilaporkan bukan diasumsikan | ~1–2 s? |
| P4 | Durasi take `get_up_after_fall` | Pilot take E6 | mungkin >10 s |
| P5 | Distribusi onset-kandidat protokol baru 12 s | Pilot 4.1 | soft check, bukan gate |

Angka-angka ini **TIDAK boleh diisi dari tebakan**. Masing-masing menunggu
pengukuran dan akan membaku di versi kontrak berikutnya.

---

*Dokumen ini adalah deliverable Fase 0. Perubahan selanjutnya memerlukan
entri di `docs/agent-changes.md` dan review internal sebelum menjadi acuan.*
