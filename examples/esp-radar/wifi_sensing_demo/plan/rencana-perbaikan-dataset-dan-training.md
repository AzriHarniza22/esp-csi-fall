# Rencana Perbaikan Dataset, Label, dan Training — Fall Detection ESP32-WROOM-32

Dokumen hidup. Setiap kali satu tabel di
[`docs/tabel_riset_dataset_dan_fitur_training.md`](../docs/tabel_riset_dataset_dan_fitur_training.md)
selesai dibandingkan, tambahkan bagian baru di §5 dan perbarui §6–§9.

| Tabel | Topik | Status |
|---|---|---|
| 1 | Karakteristik dataset | Selesai dianalisis |
| 2 | Perekaman, ground truth, segmentasi | Selesai dianalisis |
| 3 | Preprocessing | Selesai dianalisis |
| 4 | Representasi / fitur | Comparison complete; feature experiments pending |
| 5 | Models / training | Comparison complete; model/training/combination experiments NOT_RUN |
| 6 | Dataset splitting / leakage | Comparison complete; split implementation and validation experiments NOT_RUN |
| 7 | Evaluation / ESP-realistic streaming tests | Comparison and protocol complete; replay implementation, hardware tests and live confirmation NOT_RUN |
| PF | Post-fall confirmation / incident and alarm lifecycle | Research synthesized; specification in §5.8/D17/A12/B8/C8 with shared B9 truth contract; all implementation and experiments NOT_RUN |

Sumber literatur: `docs/chatgpt_research.md`, `docs/riset_perplexity.md`,
`docs/riset_opencode.md`, dan tabel ringkasan di atas.

### Current authorization and decision status — 2026-11-20

The user's six unified-dataset decisions supersede older HTTP-only acquisition,
missing-identity eligibility and historical split-feasibility assumptions below.
HTTP and TCP belong to ONE dataset/model-development pipeline. Original takes are
the base unit; acquisition profile is retained for stratified evaluation, not a
reason to create transport-specific models. Unknown identities stay unknown.

| Stage | Status in this update |
|---|---|
| Read-only inventory, structural validation and count-level feasibility of 232 takes | COMPLETE; §2.1/§2.6/§5.6.7; not an executed split or model result |
| Annotation-alignment methods and verification assessment | Development-only implementation and masked-observer validation COMPLETE (§5.2.2/A14); confidence calibration and independent verification NOT_RUN |
| Incorporate six user decisions into this existing plan | DOCUMENTATION_UPDATED; historical measurements remain historical |
| Development-only automatic annotation proposals | COMPLETE:22 sidecars,20 AUTO_PROPOSED /2 ABSTAINED; originals unchanged; not training labels (§5.2.2) |
| Split manifests/assignments or original recording edits | AWAITING_USER_APPROVAL; NOT_CREATED/NOT_RUN |
| Training, calibration fits, ablations, build, flash or deployment | AWAITING_USER_APPROVAL; NOT_RUN in this update |

The subsequent automatic-annotation request authorizes only an offline development
study and quarantined proposals. No detector split/training or original recording
edits are authorized. Fold-local donor ownership, numeric acceptance tolerances and
independent verification remain unresolved; regenerate any future training proposals
inside approved training folds. Earlier diagnostic CSVs/replays and this study do not
constitute split manifests, independent physical truth or completed A10/A11 gates.

---

## 1. Aturan kerja

- One-variable ablations lock labels, windows, preprocessing, representation,
  model, training and splits except the named factor. Predeclared interaction/
  combination stages include single-component and matched-context controls;
  they do not attribute a joint improvement to one component.
- Angka yang ditulis di dokumen ini harus berasal dari output script, log
  perangkat, atau dokumen. Perkiraan ditulis eksplisit sebagai **perkiraan**.
- Perubahan kode dicatat di `docs/agent-changes.md` (sesuai `AGENTS.md`).
- Perubahan firmware (`main/`, `sdkconfig*`, `tools/`) wajib melewati
  preflight `docs/agent-preflight.md` dan memakai trailer `Docs:` di commit.
- Phase A contains offline implementation/evaluation only. Phase C distinguishes
  an explicitly authorized replay/profiling harness from candidate behavior changes;
  hardware verification does not authorize deployment or replacing the active model.
  The six-decision documentation update authorized no execution; the subsequent
  automatic-annotation request authorizes only the offline study described above.

---

## 2. Kondisi sekarang (terverifikasi dari data)

### 2.1 Dataset

| Item | Nilai |
|---|---|
| Complete original takes | 232 unique IDs; 231 outside the existing `TEST01`/`SMOKE01` smoke-control exclusion |
| FALL take labels | 101: forward 28, backward 32, keseleo 21, lemas 20 |
| NON_FALL take labels | 131: bending 20, empty_room 20, fast_sitting 20, object_drop 10, still_sitting 20, still_standing 21, walking 20 |
| Complete observer start/impact annotations | 79 FALL takes; 22 incomplete (21 missing both, 1 missing impact only) |
| CSI | Canonical LLTF target: 51 I/Q pairs (102 bytes), single antenna; per-frame layout validation remains required |
| Stimulus families in the unified dataset | 183 `http_cloudflare` (historical HTTP 65536/pause0) + 49 `tcp_gateway`; no split into separate transport models |
| AP/channel metadata | Same recorded AP; channel1 for225 takes, channel11 for7 walking takes on11-04; AP identity is not proof of unchanged placement/environment |
| Structural validator | 232 WARNING, 0 INVALID; 78,452 parsed frames, 0 payload length/flag mismatches; WARNING is not a timing/ground-truth quality pass |
| Historical cadence evidence | Previous HTTP audit: median29.32fps, W24/12 span about0.78s; these are NOT unified-dataset measurements |
| Latest TCP cadence evidence | Median per-take saved-CSI rate39.80fps from `(N−1)/(last_callback−first_callback)`; different acquisition day, not a controlled causal comparison |

Counts were recomputed read-only from `recordings/*/*.meta.json` and matching frame
files through `dataset_io.load_recording`/`validate_recording`; no split allocation,
feature/model fit or raw-metadata modification. The prior183-take snapshot remains
the basis of historical §3 measurements, not the current inventory.

### 2.2 Subjek dan sesi

| Tanggal | Isi | subject_id | session_id |
|---|---|---|---|
| 2026-11-04 | 20 fall (forward/backward, **tanpa anotasi**) + 65 non-fall | kosong (85 take) | kosong |
| 2026-11-07 | 40 fall (semua beranotasi) | 1 = 31, 2 = 9 (semua `fall_lemas`) | `sess_20261107T100226Z_luxlof` |
| 2026-11-11 | 1 non-fall smoke/control take | TEST01 | SMOKE01 |
| 2026-11-14 | 57 non-fall | 1 | `sess_20261114T145643Z_3tu71w` |
| 2026-11-19 | 41 fall (39 complete annotations) + 8 non-fall, TCP | 1 | `sess_20261107T100226Z_luxlof` (reused raw value) |

85 takes lack both subject/session IDs. They remain in the inventory and are not
excluded from take-level eligibility for that reason. The raw November7 session ID
appears on89 takes across November7/19; preserve it and flag the provenance conflict,
not replace it with invented sessions. Recorded identities are not independently
verified identities. `fall_lemas` now includes subject1 TCP takes and subject2 HTTP
takes; the previous subject2-only observation was historical.

### 2.3 Timeline take

| Kelas | Timeline cue (detik) |
|---|---|
| Fall 12 s (11-07 and11-19) | pre 0–4, aksi 4–8, post 8–12 |
| Fall forward/backward 10 s (11-04) | pre 0–4, aksi 4–6, post 6–10 |
| bending, walking | 0–3 / 3–7 / 7–10 |
| fast_sitting, object_drop | 0–4 / 4–6 / 6–10 |
| still_*, empty_room | hold 0–10 |

`fall_keseleo`: pre = berjalan, post = `walk_slow`. Fall lainnya: pre dan
post diam.

### 2.4 Historical observer annotation measurements (40 FALL takes)

The statistics below describe the earlier40 annotated takes only. The current
inventory has79 complete observer annotations (§2.1/§2.6); do not reuse these
historical distributions as newly measured uncertainty or timing accuracy.

Tanda ditekan teman yang melihat langsung (Spasi: `fall_start` lalu
`fall_impact`).

| Ukuran | Median | Min | Max |
|---|---|---|---|
| Offset `fall_start` | 4,87 s | 4,34 s | 5,64 s |
| Offset `fall_impact` | 6,70 s | 6,28 s | 7,70 s |
| Durasi start→impact | 1,90 s | 1,27 s | 2,78 s |

### 2.5 Current policy, generated source model, and proposed target

- `fall_detection/phase_label_policy.json`: NON_FALL pre-action; FALL from cue
  4.0 s to recording end (`recording_tail_labels`). Non-fall takes are NON_FALL;
  strict source-support containment excludes boundary-crossing windows.
- Generated source model: binary Linear SVM, 16 F0 features, trained under the
  older observer start-to-impact policy WITHOUT D1 margins. Its artifact hash is
  `90dc0302d747fd6f2d9cf1109ded47ccefcfec46a246621463a90f36d2bd2318`.
  Source inspection does not verify which image is currently flashed.
- Proposed A2/D1 policy: start-0.3 s to impact+1.0 s; post-fall excluded;
  unannotated fall takes excluded entirely from training. This is a third policy,
  not the current source model's label contract.
- Existing stabilizer immediately adopts the first raw class after startup/reset,
  including FALL; subsequent entry requires 2 FALL votes among3, release requires
  3 consecutive NON_FALL. Scores are margins, ties choose FALL, not probabilities.
- Separate Motion gate: matching peer and <=250ms age required; missing telemetry
  suppresses output, below3850000 vetoes FALL, above5000000 marks an existing FALL
  confident and cannot create FALL from NON_FALL. These are source thresholds,
  not newly measured model features. Replay each stage separately.

---

### 2.6 Unified inventory, evidence levels and pending eligibility

| Recording UTC day | HTTP/TCP takes | FALL / NON_FALL take labels | Complete / incomplete FALL annotations |
|---|---|---|---|
| 2026-11-04 | 85 / 0 | 20 / 65 | 0 / 20 |
| 2026-11-07 | 40 / 0 | 40 / 0 | 40 / 0 |
| 2026-11-11 | 1 / 0 | 0 / 1 (smoke control) | 0 / 0 |
| 2026-11-14 | 57 / 0 | 0 / 57 | 0 / 0 |
| 2026-11-19 | 0 / 49 | 41 / 8 | 39 / 2 |
| Total | 183 / 49 | 101 / 131 | 79 / 22 |

Keep all232 original takes. Under the unchanged proposed manual-first D1 policy
and existing smoke exclusion, the candidate training pool is209 takes:79 annotated
FALL +130 NON_FALL. This is take-level eligibility, not a verified window count or
an executed split.65 of these candidates have unknown subject/session IDs and stay
eligible. The other20 unknown-ID takes lack fall boundaries: their primary-D1
restriction is missing labels, NOT missing identity.22 incomplete FALL takes remain
available for A3 take-level diagnostics and proposed A14 annotation research; no
pre/post frames silently enter primary-D1 fitting. The smoke take remains visible,
with the existing exclusion separately identified for user confirmation (§8.1).

New incomplete annotations (exact source evidence):
- `recordings/fall_backward/20261119T161206Z_fall_backward_021.meta.json`: both marks null.
- `recordings/fall_backward/20261119T161424Z_fall_backward_027.meta.json`: manual
  start5.229s retained; impact null. Never replace this observed mark with a template.
-20 earlier unannotated FALL takes are10 forward +10 backward on November4.

No existing take has a top-level `acquisition_profile`; all232 also have null
`acquisition.csi_config` and no recorded `stimulus.tcp` block. Preserve the existing
`stimulus`, `acquisition`, `wifi`, clock and identity metadata verbatim. B6 will
retain/add a normalized acquisition-profile record only after approval, with
field-level provenance and UNKNOWN values, never invented TCP port/concurrency/
timeout or current source defaults substituted for historical applied settings.
For now, stimulus-family and known-channel strata are descriptive metadata, NOT
complete verified acquisition profiles. Dormant HTTP fields in TCP metadata are
not evidence that HTTP was active or that two TCP profiles existed.

## 3. Historical findings from the earlier snapshot

The measurements in T1–T11 are preserved with their original cohorts. Current
counts, identities, stimulus decisions and feasibility are §2.6/§5.6.7; statements
such as one annotated-fall day or subject2-only `fall_lemas` are no longer current.

### T1 — Konfounding hari/sesi dengan kelas (kritis)

97 dari 183 take berada di hari yang hanya berisi satu kelas. Tanggal tidak
masuk fitur, tapi kondisi radio per hari ikut terekam di 16 fitur.

Uji: Linear SVM dengan 16 fitur yang sama dilatih menebak **tanggal** hanya
dari window diam (pre_action/hold), split per take.

| Aktivitas yang sama, beda hari | Akurasi menebak hari | Acak |
|---|---|---|
| empty_room | 100% | 50% |
| fast_sitting | 100% | 50% |
| bending | 97,6% | 50% |
| still_sitting | 97,2% | 50% |
| still_standing | 96,1% | 50% |
| fall_forward | 94,7% | 50% |
| fall_backward | 82,4% | 50% |
| walking | 88,7% | 50% |
| Semua take, 3 hari | 69,2% | 33,3% |

Contoh: median |ΔA| ruangan kosong 2,37 (11-04) vs 1,80 (11-14).

Kesimpulan: model **bisa** mendapat skor tinggi dengan mengenali hari. Seberapa
besar model sekarang memanfaatkannya belum diukur → tugas A1.

Konfounding sekunder: `fall_lemas` hanya dari subjek 2.

### T2 — Cue-to-tail FALL labels are contaminated (not the generated model policy)

- Cue 4,0 s lebih awal 0,3–1,6 s dari `fall_start` sebenarnya → diam sebelum
  jatuh ikut berlabel FALL.
- Label sampai akhir take → sekitar 4 s diam setelah jatuh ikut FALL.
- Post `fall_keseleo` = `walk_slow` berlabel FALL, padahal kelas `walking`
  berlabel NON_FALL → label saling bertentangan.

### T3 — Energi gerak per segmen take fall

Median |ΔA| (dihaluskan 5 frame) relatif terhadap diam pre-action take itu
sendiri:

| Segmen | Fall (post diam, n=29) | Fall keseleo (n=11) |
|---|---|---|
| Pre 0,5–3 s | 1,00 | 1,00 |
| fall_start → impact | **1,51** | 1,08 |
| impact → +1 s | **1,16** | 0,83 |
| impact +1 → +2 s | 1,00 | 0,69 |
| impact +2 → +3 s | 1,04 | 0,69 |
| impact +3 s → akhir | 1,00 | 0,69 |

- Gerakan lanjutan setelah impact (kaki membal, dll.) terlihat sekitar 1 s,
  lalu kembali ke level diam.
- Level absolut post-fall (2,36) berada di dalam rentang still_* dan
  empty_room (1,80–2,40) → tidak bisa dibedakan dengan fitur delta sekarang.
- Keseleo hanya 1,08× baseline karena pre-nya berjalan → jatuh paling sulit.

### T4 — Deteksi onset dari CSI tidak andal untuk label

Detektor ambang (median + 6·MAD baseline, 3 frame berturut-turut):

| Kelas | Onset terdeteksi |
|---|---|
| Fall beranotasi | 17 / 40 |
| bending | 5 / 20 |
| fast_sitting | 9 / 20 |
| object_drop | 4 / 10 |
| walking | 10 / 17 |

Rasio energi bending saat aksi hanya 1,02× baseline. Label dari CSI juga
melingkar: hanya contoh yang "terlihat jelas" berlabel benar.

Puncak energi CSI berada median 0,75 s **sebelum** `fall_impact` (masih di dalam
interval anotasi). Tidak ditemukan bukti tanda observer meleset jauh; delay
reaksi observer belum terukur.

### T5 — Window lebih pendek dari kejadian jatuh

Window 0,78 s (P95 0,974 s) lebih pendek dari transisi jatuh terpendek
(1,27 s). Tidak ada satu window yang memuat satu jatuh utuh. Ini window
terpendek dibanding semua studi di Tabel 2.

### T6 — Pipeline preprocessing sekarang (terverifikasi dari kode)

| Tahap | Firmware (`main/activity_classifier.c`, `activity_model_inference.c`) | Training (`fall_detection/`) |
|---|---|---|
| Validasi frame | Gate layout: INT8, HT20, tanpa secondary channel, `first_word_invalid` ↔ 102 byte/51 pasangan, segmen LTF konsisten | `_has_supported_lltf_layout`, lebar 51 wajib |
| Amplitudo | `hypotf(I, Q)` per subcarrier | `amplitude(decode_iq(...))` |
| Filter/smoothing | Tidak ada | Tidak ada |
| Normalisasi gain/skala | Tidak ada | Tidak ada |
| Penanganan gap waktu | Tidak ada; history di-reset hanya saat queue drop atau frame tidak valid | Tidak ada; window berbasis jumlah frame |
| Standardisasi fitur | `means`/`scales` dari artifact | Di-fit di dalam `fit_classifier` per fold (tidak bocor) |

Konfigurasi CSI (`ESP_RADAR_CSI_CONFIG_DEFAULT` untuk ESP32):
`channel_filter_en = false` (subcarrier tetap independen), `manu_scale = false`
(skala otomatis driver), `csi_compensate_en = true`.

**Kompensasi gain tidak bekerja di ESP32 klasik.** `esp_radar_extract_rx_ctrl_info`
mengisi `agc_gain = 0` dan `fft_gain = 0` secara hard-code untuk
`CONFIG_IDF_TARGET_ESP32`. Data rekaman konsisten: `agc_gain`, `fft_gain`, dan
`rx_gain_compensation` bernilai 0 di semua frame yang diperiksa. Jadi tidak ada
padanan RSS/AGC scaling ala TCS-Fall dari driver.

### T7 — Kualitas waktu dan sinyal mentah

| Ukuran | Nilai |
|---|---|
| Interval antar-frame | median 29,0 ms, P95 85,2 ms, P99 146,5 ms, maks 1.375,8 ms |
| Gap > 0,2 s | 456 (0,82% interval), di 102/182 take |
| Gap > 0,5 s | 19 (0,03% interval), di 16/182 take |
| Window 24 frame dengan gap > 0,2 s | 18,68% |
| Window 24 frame dengan gap > 0,5 s | 0,78% |
| CV skala amplitudo per frame (take diam) | median 0,054, P90 0,080 |
| Subcarrier amplitudo terendah | indeks 46–50 (15,4–17,2), puncak indeks 25–27 (30,7–32,4) |
| Subcarrier paling bising (ruang kosong, \|ΔA\|/mean) | indeks 45–50 (0,134–0,177), median semua 0,087 |
| Hampel (w=5, 3σ) menandai | 6,4–7,7% sampel, termasuk di take diam |

Hampel menandai ~7% sampel bahkan saat diam: pada data int8 terkuantisasi, ia
bekerja sebagai smoother, bukan pembuang outlier.

### T8 — Ablasi preprocessing (offline, satu variabel)

Pengaturan: window 24/12 dan 16 fitur delta yang sama; label berbasis anotasi
(D1/D2, 227 window FALL); sklearn `LinearSVC(class_weight="balanced")`, bukan
implementasi proyek, jadi angkanya **perbandingan relatif**, bukan pengganti
metrik resmi.

- **A** — OOF 5-fold dikelompokkan per take.
- **B** — akurasi menebak hari dari window diam (lebih rendah = jejak hari
  lebih sedikit; acak 0,333).
- **C** — uji lintas hari: latih 11-07 + 11-14, uji take 11-04 (20 fall tanpa
  anotasi, 65 non-fall); alarm = 2 dari 3 window FALL.

Historical measurements below are preserved. The old B interpretation (lower raw
accuracy and0.333 as a universal chance target) is superseded by §5.4.4/§7.3's
imbalance-aware, diagnostic-only E3 contract; it never selects a feature or breaks ties.
C counts any-alarm fall takes, not annotated event recall or delivered notifications.

| Varian | A macro-F1 | A FALL P / R | B hari | C fall alarm | C non-fall alarm |
|---|---|---|---|---|---|
| V0 amplitudo mentah (sekarang) | 0,682 | 0,30 / 0,84 | 0,717 | 20/20 | 52/65 |
| V1 Hampel w=5 | 0,730 | 0,37 / 0,86 | 0,704 | 20/20 | 44/65 |
| V2 rata-rata kausal 3 frame | 0,757 | 0,42 / 0,85 | 0,739 | 20/20 | 39/65 |
| V3 normalisasi per frame (A / mean subcarrier) | **0,777** | **0,45 / 0,90** | 0,850 | 20/20 | 33/65 |
| V4 baseline per take (0,5–2,5 s) | 0,694 | 0,32 / 0,87 | 0,844 | 15/20 | 30/65 |
| V5 baseline EMA kausal | 0,689 | 0,31 / 0,89 | 0,838 | 6/20 | 30/65 |
| V6 V3 + Hampel | 0,749 | 0,40 / 0,87 | 0,758 | 20/20 | 31/65 |
| V7 V3 − lantai noise per take | 0,680 | 0,31 / 0,68 | 0,362 | 20/20 | 37/65 |
| V8 V3 − lantai noise kausal (P20, 30 window) | 0,716 | 0,37 / 0,73 | 0,395 | 20/20 | 34/65 |
| V9 V2 + V3 − lantai noise kausal | 0,736 | 0,40 / 0,74 | 0,424 | 20/20 | 33/65 |

Alarm palsu uji C per aktivitas (11-04):

| Varian | still_sitting | still_standing | empty_room | object_drop | bending | fast_sitting | walking |
|---|---|---|---|---|---|---|---|
| V0 | 9/9 | 10/10 | 4/9 | 3/10 | 9/10 | 10/10 | 7/7 |
| V3 | 3/9 | 7/10 | 0/9 | 0/10 | 10/10 | 7/10 | 6/7 |
| V2 | 4/9 | 6/10 | 0/9 | 2/10 | 10/10 | 10/10 | 7/7 |
| V9 | 4/9 | 4/10 | 0/9 | 7/10 | 9/10 | 10/10 | 7/7 |

Pembacaan:

- Model mentah yang dilatih pada data terkonfounding membunyikan alarm di
  **semua** take diam hari lain (still_sitting 9/9, still_standing 10/10).
  This is evidence of cross-day false alarms, not proof of their sole cause.
  Session, radio conditions, labels, features, and timing remain confounded.
- Normalisasi per frame (V3) dan smoothing ringan (V2) menurunkan alarm palsu
  di take diam dan menaikkan presisi tanpa menurunkan recall.
- Pengurangan lantai noise (V7–V9) menghapus jejak hari (B mendekati acak),
  tapi menurunkan recall di data take pendek. Take hanya 10–12 s, sehingga
  estimasi lantai kausal ikut tercemar aksi; perlu diuji ulang di rekaman
  kontinu (B5).
- Bending, fast_sitting, dan walking hampir selalu memicu alarm di hari lain
  pada semua varian. This motivates feature/window experiments (Table 4,
  D4), but does not establish that preprocessing is irrelevant.
- V3 menaikkan jejak hari di uji B (0,717 → 0,850) walau alarm palsu lintas
  hari turun. Belum dijelaskan; harus diperiksa ulang di data sesi campuran.

Batasan: satu seed, data training uji C terkonfounding penuh (fall hanya
11-07, non-fall hanya 11-14), take pendek, dan bukan implementasi classifier
proyek.

### T9 — Table 4: one feature type, 16 output dimensions

Verified in `main/activity_model_inference.c` (`activity_model_extract_features`)
and `fall_detection/train_activity_model.py` (`extract_window_features`):

```text
A[t,k] = hypot(I[t,k], Q[t,k])
B_b = {k: floor(16*k/51) = b}, k = 0..50
f[b] = log1p(sum(t=1..23, k in B_b, abs(A[t,k]-A[t-1,k])) / (23*|B_b|))
```

- One receiver link, 51 complex LLTF pairs per frame, 24 frames per window,
  23 adjacent differences, 16 output scalars. These are different counts.
- Bands 0, 5, 10 contain 4 pairs; the other bands contain 3. Indices 45–50
  occupy the last two bands. These are array indices, not verified physical
  OFDM frequency labels.
- Absolute per-subcarrier differences are calculated **before** band pooling.
  Averaging amplitudes into bands before differencing is a different feature.
- The artifact's "phase-aware" name refers to recording/event phases, not
  CSI phase as a classifier input; the current representation is amplitude-only.
- Delta is already present: adding another mean absolute delta is not a new
  feature. It is displacement per adjacent frame, not velocity per second;
  timestamps do not enter this formula.
- The vector retains average fluctuation strength by band, but discards phase,
  change direction, absolute level, peak timing, and within-band detail.
  Exact reversal of frame order leaves the vector unchanged: a mathematical
  property of this formula, not a newly executed experiment.
- A short spike and sustained activity can have similar mean delta. This is
  a reason to test richer representations, not proof of a dataset failure.

Calculated storage (float32, excluding queue, stack, strings, and other state):
24*51 = 1,224 amplitude values = 4,896 bytes of history; 16 output features =
64 bytes. The binary linear artifact stores 16 means + 16 scales + 32 weights
+ 2 biases = 66 floats = 264 bytes. These are arithmetic counts, not a new
hardware measurement. Small model input does not eliminate window history.

The separate Motion gate is not a seventeenth classifier feature and is not
CSI peak extraction. It acts on a recent external motion diagnostic after
classification/stabilization; model, voting, and gate must be evaluated separately.

### T10 — Evidence boundaries for richer features

- Table 4 and the research files describe candidates, not project benchmarks.
- `chatgpt_research.md` §15.2 reports an earlier 89-take analysis favoring
  motion + baseline-relative features. Its snapshot/protocol differs from
  the current data, and referenced pasted analysis is not a fresh controlled
  comparison. Treat it as motivation only.
- Existing saved metrics use differing snapshots/policies; active firmware
  and current training policy must not be assumed identical (§2.5).
- No completed current-snapshot comparison of the feature sets below was
  located. T8 is a preprocessing proxy with the same delta representation;
  its scores do not rank peak, range, PCA, phase, or spectral features.

### T11 — Table 5: model capacity does not resolve experimental confounding

Canonical host implementations include five compact classifiers, but current phase
export/C inference accepts only Linear SVM. New model families need tested schema,
solver/export and replay support. Historic window metrics and static build figures
are not event-level or live hardware evidence. A2 labels, source artifact labels
and the current cue-tail policy differ; reproduce/hash each control separately.
Models, representation and training can interact, so §5.5 specifies isolated tests,
bounded combinations, nested ownership and untouched-session confirmation.

---

## 4. Keputusan desain

### D1 — Label FALL dari anotasi observer

- FALL = `[fall_start − 0,3 s, fall_impact + 1,0 s)` (half-open, consistent with §5.5/§5.7).
- The −0.3s/+1.0s margins are initial estimates, not measured optima. Freeze them
  as the primary A2 policy. A13 owns predeclared, training-only margin sensitivity;
  A4 changes windows only and A5 reports results without selecting from outer tests.
- In the manual-first primary branch, FALL takes with incomplete annotations supply
  no training frames/windows, including pre/post phases. Missing subject/session IDs
  are a separate issue and never an automatic exclusion. A14 investigates assisted labels; automatic or
  signal-reviewed proposals are not manual ground truth and need separate approval.

### D2 — Perlakuan fase pada take fall

| Fase | Label |
|---|---|
| Pre | NON_FALL |
| `fall_start − 0,3 s` → `fall_impact + 1,0 s` | FALL |
| Setelah `fall_impact + 1,0 s` | `post_fall` → dikeluarkan dari model biner |
| Post `fall_keseleo` (`walk_slow`) | dikeluarkan (bukan FALL) |
| Window yang memotong batas | dibuang (strict containment tetap) |

Preserve `post_fall` for the separate aftermath/assistance study in §5.8/D17.
Label observed movement, recovery, user response and evidence availability independently
of impact labels. Neither the current delta features nor a proposed relative-level
feature establishes lying posture, unconsciousness or safety. Learn and validate any
additional representation separately; do not relabel stationary aftermath as FALL.

### D3 — Label aksi non-fall

Tetap memakai cue (bending/walking 3–7, fast_sitting/object_drop 4–6). Untuk
model biner semua fase NON_FALL, jadi batas aksi tidak memengaruhi label.
Tidak memakai deteksi onset CSI (T4).

### D4 — Window berbasis waktu

Definisikan window dalam detik dari `host_receive_monotonic_ns`, bukan jumlah
frame. Kandidat: 1, 2, 3 s dengan stride 0,4–0,5 s. Kandidat utama 2 s
(median transisi 1,90 s), latensi diukur, bukan diasumsikan.

### D5 — Preserve metadata; identity availability is not take eligibility

Original recording/take is the base unit for storage, eligibility and diagnostic
splits. Keep unknown `subject_id`, `session_id`, `environment_id` unchanged; do not
invent IDs, default to subject1/room1, or use a date/take ID as a replacement person
or session. An unknown identity is not itself a data-quality failure or an automatic
training exclusion. Signal, label, clock and smoke-control eligibility are separate.

| Field | Preservation and evaluation use |
|---|---|
| `recording_id` | Original take and all windows/copies remain together; verified parent/copy lineage can require grouping several takes together |
| `subject_id`, `session_id` | Preserve raw values and verification/conflict status; optional exclusive evaluation only when provenance supports membership |
| `environment_id` | UNKNOWN remains UNKNOWN; AP identity alone cannot recover room/placement |
| `recording_day` | Derived UTC-day audit stratum, not a recovered session identity |
| `acquisition_profile` | Preserve known stimulus/radio/capture fields and their provenance; retain UNKNOWN fields; evaluate strata within one unified pipeline |

Unknown-ID takes remain in the base evaluation. For an optional identity-exclusive
claim, report unresolved membership explicitly; do not silently place unknown takes
in training where they might belong to the held-out person/session. A verified-subset
analysis is separately denominated and does not revoke global take eligibility.

### D6 — Yang tidak diadopsi dari literatur

- Konfigurasi Intel 5300 (90 stream, ~1 kHz).
- Phase difference antar-antena (WROOM-32 single antenna).
- Window berbasis jumlah paket (STFT 512, 512/128, 625 step).
- Window 8 s ala TCS-Fall (take kita 10–12 s → pasti mencampur fase).

### D7 — Yang dipertahankan

- Take terisolasi dengan timeline cue.
- Anotasi Spasi `fall_start`/`fall_impact` saat perekaman.
- Strict containment.
- Split dikelompokkan, bukan acak per window.
- Cakupan hard negative yang ada (bending, fast_sitting, object_drop, dll.).
- Gate layout CSI di firmware, `channel_filter_en = false`, dan
  standardisasi fitur yang di-fit per fold.

### D8 — Kandidat preprocessing utama

Urutan kausal per frame, murah untuk ESP32:

1. Gate layout (sudah ada).
2. Amplitudo `hypot(I, Q)` (sudah ada).
3. **Normalisasi per frame**: `A[k] / mean(A)` atas 51 subcarrier
   (V3). Pengganti kompensasi AGC yang tidak tersedia di ESP32 klasik (T6).
4. **Smoothing kausal ringan**: rata-rata 3 frame (V2). Tambahan latensi
   sekitar 1 frame (~30 ms, perkiraan dari median interval).

Kombinasi V3 + V2 belum diuji tanpa pengurangan lantai noise → diuji di A6.

Status: **hipotesis**, belum keputusan. Hasil T8 berasal dari proxy sklearn,
satu seed, satu arah lintas hari. Pilihan final ditentukan lewat katalog dan
protokol di §7.

### D9 — Penanganan gap waktu

- Kandidat awal: tanpa interpolasi ke grid teratur (interpolasi bisa
  menciptakan gerakan buatan). Interpolasi linear/ZOH tetap diuji sebagai
  P9.3–P9.4 di §7.
- Window berbasis waktu (D4) + window ditandai tidak valid jika gap
  terbesar di dalamnya > 0,5 s. Ambang 0,5 s adalah **perkiraan**; saat ini
  memengaruhi 0,78% window 24 frame.
- Firmware perlu aturan yang sama (Fase C).

### D10 — Lantai noise / baseline relatif

Ditunda sampai ada rekaman kontinu (B5). Hasil V7–V9 menunjukkan cara ini
menghapus jejak hari, tapi tidak bisa dinilai adil di take 10–12 s.

### D11 — Methods not directly transferable or outside preprocessing scope

Distinguish hardware constraints from parameter choices and feature branches:

| Metode | Alasan |
|---|---|
| Phase-difference / conjugate multiplication antar-antena | Single antenna |
| Original TCS-Fall grouped-CV configuration | Its high-rate group/window parameters cannot be copied unchanged; adapted CV features remain testable |
| Downsampling | Technically possible; low measured packet rate makes it low priority, not impossible |
| STFT / CWT / spektrogram | Ini representasi fitur → Tabel 4, bukan preprocessing |

Revisi 2026-11-18: versi sebelumnya juga menolak interpolasi, Butterworth,
Savitzky–Golay, DWT, PCA, dan Hampel. Alasan itu berupa penalaran, bukan hasil
uji. Metode tersebut kini masuk katalog §7: versi kausalnya diuji sebagai
kandidat, versi non-kausal sebagai pembanding offline. Koreksi: proyeksi PCA
yang di-fit offline hanya butuh 51 × k perkalian per frame di firmware, jadi
alasan "biaya matriks per frame" tidak tepat.

### D12 — Feature selection remains open

Keep the exact 16-delta baseline. First test adding peak, range, dispersion,
and temporal order separately, then a small combination. Test per-subcarrier,
PCA, relative-profile, spectral, and phase branches without assuming that more
input dimensions improve performance. Priorities in §5.4 are proposed, not
measured rankings; costs and deployment feasibility require verification.

### D13 — Separate feature extraction from preprocessing and event state

P3/P5/P10 in §7 overlap representation choices. Give each experiment one
configuration identity; do not count it again as a new independent result.
Changing LTF, band count, phase streams, or PCA also changes feature schema.
Baseline-relative profiles need causal, deployment-available calibration.
Post-fall stillness may support an already detected event but must not generate
an alarm on its own. Ground-truth start/impact markers may label and evaluate
windows; they must never become classifier inputs or inference-time boundaries.

### D14 — Model/training candidates require independent ablations and deployment proof

Use the bounded M0–M24/T0–T14/S/C catalog and A9 (§5.5). Preserve canonical
unweighted controls, natural-prevalence tests, original-take lineage and fold-local
learned state. Thresholds/calibration/model/feature choices belong inside training
folds. Historical shortlist selection remains exploratory; neither a nested rerun
on already-inspected data nor more training windows proves cross-session validity.
Do not name a hardware winner without actual C parity, complete-state replay,
resource profiling and untouched new-session confirmation. Fitting/installation/
firmware/flash/commit are not authorized by this documentation task.

### D15 — Match split independence to the intended claim

Use original takes as the base unit and keep all derived data together. Use day
holdouts as secondary robustness diagnostics; session/subject grouping is optional
and requires verified provenance, not merely a populated metadata string. Verified
subject/environment holdouts support only their explicitly scoped generalization claims. Keep all selection and
learned transforms inside training groups; freeze manifests and untouched final
groups before fitting. Choose fold counts from group/class support, not a desired
percentage. Unsupported folds stay blocked; §5.6/A10 supplies shared safeguards
without changing Table4's fixed ablation or labeling contract.

### D16 — Fidelity is demonstrated at a named boundary, not assumed from replay

Use §5.7/A11/C7: complete causal Python replay, production-C reference, paced replay
on the physical ESP32-WROOM-32, then untouched live-radio confirmation. Preserve
production state/queue/clock semantics in a versioned legacy control; proposed
boundary/gap resets are a separate pipeline change. Captured CSI is not RF reception,
virtual time is not measured real-time performance, and replayed Motion is not FSM
checkpoint restoration. Require acquisition/transport coverage, actual timing,
build identity and stage-specific traces before claiming firmware equivalence.

### D17 — Separate fall evidence, assistance assessment, sensor health and alarm delivery

Use §5.8/A12/B8/C8. A classifier episode starts a candidate, not an emergency call.
Confirm the suspected physical event from a frozen causal evidence policy; assess
post-event movement and human response separately. Low CSI motion cannot establish
unconsciousness; recovery does not make a real fall false. Keep confirmed unresolved
incidents through classifier resets/dropout, use independent monotonic deadlines,
and distinguish alarm intent, delivery, acknowledgment and explicit resolution.
The recommended first prototype is multi-observation confirmation plus a bounded
user-response workflow, initially SHADOW_ONLY with a fake notification sink. All
numeric lifecycle settings below are proposed experimental parameters, not measured
optima or production safety limits. Preserve HTTP and TCP acquisition provenance
under unified D18/B6; matched lifecycle comparisons hold the acquisition profile
constant, and resource results name the tested profile. No firmware, experiment
or external notification is authorized.

### D18 — One unified HTTP/TCP dataset and profile-aware evaluation

Pool all original HTTP/TCP takes under one dataset schema, label policy and shared
candidate-model pipeline. Do not create transport-specific models, routing heads,
scalers, decision thresholds or deployment artifacts solely because stimulus differs.
Keep profile/day/channel as audit strata, not classifier inputs in the primary
comparison. Report pooled and per-profile coverage, recall, negative-take alarms
and timing with their own denominators. Any profile-held-out diagnostic uses the
same candidate specification and is not a proposal for separate deployed models.

HTTP downloads also use TCP; the recorded distinction here is `http_cloudflare`
download-burst stimulus versus `tcp_gateway` connect/close stimulus, not mutually
exclusive network-layer protocols. The user's latest TCP choice is retained; the
previous HTTP65536 choice remains historical evidence. Missing profile fields do
not force exclusion from unified take-level analysis; exact-profile claims remain
unverified. §5.6.7 separates feasibility from confounding and executable readiness.

---

## 5. Hasil perbandingan per tabel

### 5.1 Tabel 1 — Karakteristik dataset

| Aspek | Literatur | Proyek | Keputusan |
|---|---|---|---|
| Perangkat | Mayoritas Intel 5300 3×30 stream; sebagian Nexmon/ESP32-S3 | ESP32-WROOM-32, 51 subcarrier, 1 antena | Tidak meniru konfigurasi multi-antena |
| Packet rate | ~100–1000Hz | Historical HTTP median29.32fps; latest TCP median39.80fps, different days | Time windows and actual per-take cadence; no causal transport ranking from unmatched days |
| Jumlah subjek | median ~6; TCS-Fall 20; CSI-Bench 17 | 1–2 | Tambah subjek; tiap jenis jatuh dari >1 subjek |
| Sessions/environments | Multiple rooms/sessions in stronger studies | Five UTC days including smoke, four primary candidate days; reused/unknown session IDs and unverified placement | Mixed collection (B2), preserve unknown provenance; day is not session identity |
| Hard negative | Lying down, duduk ke lantai, jongkok, fall-like | bending, fast_sitting, object_drop, walking | Tambah (B4) |
| Rekaman kontinu | TCS-Fall 150 s; FallAware naturalistik | Tidak ada | Sesi negatif kontinu (B5) |

### 5.2 Tabel 2 — Perekaman, ground truth, segmentasi

| Aspek | Literatur | Proyek | Keputusan |
|---|---|---|---|
| Ground truth | Video+timestamp (Chu, SiFall), key-press (TCS-Fall), protokol | Key-press observer (setara TCS-Fall) | Pertahankan; video untuk subset (B3) |
| Lingkup label | Per take / per window / berbasis anotasi | Tail dari cue 4 s | Berbasis anotasi (D1, D2) |
| Window | 2,9–8 s; konvensi de facto ~5 s | 0,78 s | Uji 1/2/3 s (D4) |
| Overlap | 50–98% | 50% | Stride 0,4–0,5 s; jangan inflate jumlah fall |
| Batas fase | Jarang dijelaskan | Strict containment | Pertahankan |

Inkonsistensi sumber (catat, jangan dipakai sebagai dasar keputusan):
- Overlap Chu 2023: Tabel 2 menyebut overlap; `riset_opencode.md` §8 menyebut
  tanpa overlap.
- WiFall 2014: Tabel 1 "laptop, NR"; `riset_opencode.md` "Intel 5300 3×3,
  4 subjek".
- `riset_perplexity.md` tidak punya akses kode → kolom proyek semuanya
  "TIDAK DIKETAHUI".
- Header tabel ringkasan merujuk `riset_chatgpt.md`; berkas yang dipakai
  `chatgpt_research.md` (keduanya ada di `docs/`).

#### 5.2.1 Assisted annotation: feasibility assessment, not generated ground truth

Status: inventory/method assessment and the subsequently authorized development-only
alignment study COMPLETE (§5.2.2). Confidence calibration, reviewer decisions,
independent verification and training-ready labels remain NOT_RUN. A14 is an optional
research track; primary manual-first A2 need not wait for it.

Targets:22 incomplete FALL takes (21 missing both boundaries,1 missing impact).
Available complete observer-annotated donor candidates, before quality/ownership checks:

| Subtype | HTTP donors | TCP donors | Incomplete targets |
|---|---|---|---|
| forward | 10 | 8 | 10 HTTP |
| backward | 10 | 10 | 10 HTTP +2 TCP |
| keseleo | 11 | 10 | 0 |
| lemas | 9 | 11 | 0 |

Similar activity alone does not establish identical motion or trustworthy boundaries.
Prefer same-subtype, compatible observed placement/profile and reliable-clock donors;
unknown provenance stays visible. Evaluate same-family and cross-family transfer
separately inside the unified dataset, without separate transport classifiers.

| Candidate method | Potential use | Limitation / required control |
|---|---|---|
| Normalized cross-correlation | Rigid-lag baseline on time-indexed amplitude-change envelopes | Cannot model variable execution speed; competing peaks/flat traces require abstention |
| Constrained multivariate DTW | Map donor phase boundaries through a monotonic time-alignment path using band-level signal trajectories | Constrain band, slope and path length; unconstrained warping can force unrelated noise to match |
| Multiple-donor consensus | Aggregate independently mapped start/impact proposals and boundary spread | Donors can share day/person bias; agreement is not independent truth or a calibrated probability |

Training-ready procedure AFTER separate approval (not completed by the quarantined
§5.2.2 study):
1. A10 freezes original-take/verified-lineage ownership for all232 takes before
   donor selection, including currently label-incomplete takes. Keep manual-first
   eligibility separate from group ownership; successful completion cannot reshuffle folds.
2. A11 R0 audits clock mapping, source support, gaps and quality. Use physical-time
   axes with explicit interpolation/support limits, not equal frame indices across
   HTTP/TCP rates. Fit preprocessing, donor selection and alignment constraints only
   in training-owned groups; no whole-test normalization learned from other takes.
3. Align observable trajectories without using target truth. Map donor-relative
   boundaries through the fitted path into the target's own clock; never copy absolute
   UTC, fixed offsets, cue4s or another take's timestamps. Full-take offline alignment
   is label assistance only, never an inference-time classifier input or causal detector.
4. Preserve every existing manual mark. For
   `20261119T161424Z_fall_backward_027`, retain start5.229s and propose ONLY impact,
   constrained to follow the observed start. A path inconsistent with that mark is
   rejected, not used to overwrite it. Keep all raw annotations immutable.
5. Confidence records include normalized cost/correlation, second-best ambiguity,
   donor count/disagreement, mapped-boundary spread, path distortion, clock uncertainty,
   gap/coverage and profile mismatch. DTW cost is not a probability; never invent a
   numerical confidence guarantee. Abstain on ambiguous, implausible or low-quality cases.
6. Validate by hiding known boundaries on complete held-out takes, separately for
   missing-both and impact-only tasks. Select donors/parameters and calibrate confidence
   within inner training only; score against held-out observer marks without exposing
   them to alignment. Report start/impact signed error, MAE, P95 absolute error,
   interval agreement, coverage-versus-error and abstention by subtype/profile/day.
   Compare rigid lag with constrained DTW and consensus only after approval. Take-only
   validation does not establish new-session accuracy; observer error remains unknown.
7. Review proposed overlays, donor paths and uncertainty. CSI-only human review yields
   SIGNAL_REVIEWED_AUTO, not manual ground truth. Independent synchronized video or
   contemporaneous observer evidence, with B9 review and timing bounds, is required
   for an independently verified physical boundary. Unavailable evidence stays unavailable.

Future sidecar provenance: source take/hash, boundary name, original manual value,
proposal/value/uncertainty, AUTO_PROPOSED / SIGNAL_REVIEWED_AUTO /
INDEPENDENTLY_VERIFIED / REJECTED / ABSTAINED status, donor IDs/hashes/fold ownership,
method/version/config, confidence components/calibration identity, evidence links,
reviewer/time and verification reason. Record provenance per boundary: a manual start
plus automatic impact is not a fully manual annotation. No changes to current metadata.

Primary training/evaluation remains manual-first. Automatic/signal-reviewed proposals
may enter only a separately approved weak-label training branch using training-owned
recipients/donors; they never become held-out physical truth. Any later independently
verified additions require a new dataset/policy version, preserved original ownership
and disclosed change of eligibility. An annotation study's held-out truth cannot
subsequently be called untouched detector confirmation data.

Method sources consulted: [SciPy correlation](https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.correlate.html)
(defines cross-correlation and lag behavior) and [tslearn DTW](https://tslearn.readthedocs.io/en/stable/user_guide/dtw.html)
(monotonic paths; Sakoe-Chiba band, Itakura slope and path-length constraints).
These sources establish available methods, not transfer accuracy for this dataset.
Error tolerances, acceptance thresholds and permitted label use await §8.1 approval.

#### 5.2.2 Executed automatic-annotation development study — 2026-11-20

Scope: the subsequent user request authorized automatic annotation assistance only.
No A10 detector ownership exists, so this is DEVELOPMENT_ONLY, not completed fold-local
A14 calibration or permission to fit a classifier. Existing D1 eligibility is unchanged.

Artifacts (repository-relative):
- Code: `fall_detection/automatic_annotations.py`; tests:
  `fall_detection/tests/test_automatic_annotations.py`.
- Run: `reports/automatic_annotations/20261120_development_run01/`.
- `summary.json`: frozen configuration, observer-agreement metrics, versions, code hashes,
  and limitations; `validation.csv`:632 target/task/method/protocol rows with donor IDs.
- `proposal_index.json` and `proposals/*.auto.json`:22 sidecars with per-boundary provenance,
  donor hashes, alignment paths/physical-time grid axes, disagreement and abstention reasons.
- `source_hashes.json` and `input_audit.json`: immutable input checks and FALL quality audit.

Fixed before observing outcomes:10Hz grid; duplicate host timestamps coalesced;
no interpolation across host gaps >0.5s;4 LLTF level +4 motion bands; per-take offline
normalization; constrained DTW time band2.5s/local moves(1,1)/(1,2)/(2,1);3 source-disjoint
same-subtype donors with coarse stimulus-family preference and median boundary consensus.
NCC is a diagnostic baseline; DTW remained primary regardless of validation ranking.
These are untuned research settings, not accepted label-error limits or safety thresholds.
Unknown subject/session values and original acquisition metadata are preserved.

Measured outcomes:
- 232 metadata records /101 FALL;79 complete observer references /22 incomplete targets.
- 20 AUTO_PROPOSED takes (19 from November4,1 from November19),40 proposed missing
  boundaries;2 ABSTAINED. All22 sidecars require review and have training_eligible=false.
- `20261104T160014Z_fall_forward_010`: observed host gap0.6335s, so no boundary proposed.
- `20261119T161424Z_fall_backward_027`: host gap0.7379s, so impact remains missing;
  original start5.229s and its UTC mark are preserved exactly. Limits were not relaxed.
- 79 targets ×2 masking tasks ×2 donor protocols ×2 methods =632 diagnostic rows.
  Each variant produced60 predictions and19 abstentions; MAE/P95 below are conditional
  on those60 predictions, not all79 takes. Complete references remain in coverage denominators.

| Method / donor protocol | Masked task | Predicted/targets | Start MAE / P95 (s) | Impact MAE / P95 (s) |
|---|---|---|---|---|
| DTW / profile-preferred | Both boundaries | 60/79 | 0.245 /0.711 | 0.350 /0.880 |
| DTW / other-day | Both boundaries | 60/79 | 0.348 /0.855 | 0.452 /1.037 |
| NCC / profile-preferred | Both boundaries | 60/79 | 0.415 /1.522 | 0.481 /1.313 |
| NCC / other-day | Both boundaries | 60/79 | 0.374 /1.314 | 0.535 /1.521 |
| DTW / profile-preferred | Impact only | 60/79 | Manual start retained | 0.316 /0.760 |
| DTW / other-day | Impact only | 60/79 | Manual start retained | 0.426 /0.827 |
| NCC / profile-preferred | Impact only | 60/79 | Manual start retained | 0.296 /0.750 |
| NCC / other-day | Impact only | 60/79 | Manual start retained | 0.355 /0.787 |

Interpretation/recommendation: retain these as review proposals, not accepted labels.
Errors measure agreement with observer marks; observer reaction and host delivery delay
are not independently bounded. Other-day also changes stimulus family; November4 has
no complete reference boundaries, so the error of its19 proposals is not directly known.
Low donor spread does not guarantee low error: other-day DTW impact spread <=0.25s
retains only4/79 targets with MAE0.561s (both-missing task). Confidence remains UNCALIBRATED;
no numeric acceptance threshold was selected from these results. CSI-only review cannot
establish independent physical truth. Future model use requires approved fold-owned donors,
regeneration and a separately authorized weak-label policy; no primary-pool promotion.

Verification:63 focused tests passed, including saved-output donor/hash/path checks,
manual preservation, metric recomputation and rehash of all467 source files; unchanged.
Run metadata records Python3.11.2 /NumPy2.4.6 (the execution environment, distinct from
an earlier system-Python package probe). No package install, split manifest, classifier
training, detector ablation, firmware edit, build, flash or commit occurred in this study.

### 5.3 Tabel 3 — Preprocessing

| Metode literatur | Studi | Proyek sekarang | Relevansi ESP32-WROOM-32 | Keputusan |
|---|---|---|---|---|
| Validasi / buang frame rusak | Perplexity (umum) | Ada: gate layout ketat di firmware dan training | Tinggi | Pertahankan |
| Interpolasi ke grid teratur | Anti-Fall, RT-Fall, FallDeFi | Tidak ada; window per jumlah frame | Rendah; gap > 0,2 s ada di 18,7% window | Kandidat awal: window waktu + invalidasi gap (D9); interpolasi diuji P9.3–P9.4 |
| Ekstraksi amplitudo | Damodaran, Chu, STC-NLSTMNet, TCS-Fall | Ada (`hypot`) | Tinggi | Pertahankan |
| Phase-difference | Anti-Fall, RT-Fall | Tidak ada | Tidak mungkin (1 antena) | Tidak |
| Low-pass / band-pass | Anti-Fall, RT-Fall, STC-NLSTMNet | Tidak ada | Sedang, hanya versi kausal | Rata-rata kausal 3 frame (D8); diuji P7.1–P7.6 |
| DWT denoising | Damodaran, FallDeFi, ESP32 PoC | Tidak ada | Rendah (biaya, Chu: tanpa denoising setara/lebih baik) | Pembanding offline P7.9 |
| PCA | Damodaran, FallDeFi, IntechOpen | Tidak ada; 16 band rata-rata | Sedang (proyeksi tetap murah) | Diuji P10.1–P10.2 |
| Gaussian / Savitzky–Golay smoothing | STC-NLSTMNet, IntechOpen | Tidak ada | Sedang; meredam transient | Pembanding offline P7.7–P7.8 |
| Grouped coefficient of variation | TCS-Fall | Tidak ada | Original high-rate parameters do not transfer | Adapted CV is testable as F17; D11 |
| Downsampling | Chu | Tidak ada | Technically possible, low priority at current rate | Conditional lower-rate control, not impossible; D11 |
| Hampel outlier removal | IntechOpen | Tidak ada | Rendah; menandai ~7% sampel diam | Diuji P6.1–P6.2 (versi kausal) |
| CWT / scalogram | AmFall | Tidak ada | Rendah | Riset offline saja |
| Normalisasi skala sinyal (RSS/AGC) | TCS-Fall, Chu, IntechOpen | Tidak ada; AGC tidak tersedia di ESP32 | Tinggi | Normalisasi per frame (D8); diuji P4.1–P4.6 |
| Normalisasi fitur (z-score) | Hampir semua; CSI-Bench per sampel | Ada; di-fit per fold, dipakai di firmware | Tinggi | Pertahankan |
| Baseline subtraction | Perplexity (umum), ChatGPT (baseline-relative) | Tidak ada | Tinggi, tapi butuh data kontinu | Skrining P8.1–P8.3; final ditunda (D10) |
| Pemilihan subcarrier | Anti-Fall (4 dari 30), IntechOpen | Semua 51 dipakai | Sedang; indeks 45–50 paling bising | Diuji P5.1–P5.3 dan Tabel 4 |

Inkonsistensi sumber:
- Tabel 3 ringkasan menyebut "Normalization" untuk Chu, TCS-Fall, IntechOpen;
  `riset_opencode.md` §9 menyebut normalisasi Chu dan TCS-Fall UNKNOWN.
- `riset_opencode.md` menyebut Chu downsample 1.000 → 125; tabel ringkasan
  menyebut 5.000 → 625 titik (5 s × 1 kHz ÷ 8). Keduanya konsisten jika 125 =
  laju per detik, tapi tidak dinyatakan eksplisit.
- `riset_perplexity.md` tidak punya akses kode; kolom proyeknya tidak bisa
  dipakai.

### 5.4 Table 4 — CSI representation and feature dimensions

Sources: `docs/tabel_riset_dataset_dan_fitur_training.md` §4/§9/§10,
`riset_chatgpt.md` §7, `riset_opencode.md` §10,
`riset_perplexity.md` feature section, and `chatgpt_research.md` §15.2.
Paper descriptions below are claims in these research documents; primary
papers were not independently revalidated during this comparison.

| Literature approach | Studies / reported shape | Our project | Practical comparison |
|---|---|---|---|
| Handcrafted activity statistics | WiFall; Anti-Fall: 7 types × 4 SC × amplitude/phase = 56 per link | One mean-absolute-delta type × 16 bands | Keep baseline; add distinct statistics rather than duplicating delta |
| Amplitude + relative phase | RT-Fall: 8 named feature types, final dimension NR | Amplitude only, one antenna | Inter-antenna phase unavailable; single-antenna sanitized phase is a separate unproven branch |
| Compact temporal/spectral descriptors | FallDeFi: spectral entropy, fractal dimension, event duration | No peak timing, duration, or spectral descriptor | Test compact causal statistics before full scalograms |
| Statistics plus PSD / PCA | Damodaran classical ML: 90 streams, final vector NR | 51 streams pooled into 16 | Transfer feature ideas, not antenna/stream counts |
| Raw amplitude sequences | Damodaran LSTM / El-Sayed: 90 values per timestep | 51 amplitudes per timestep before extraction | Raw sequence is possible offline, but requires a different feature/model contract |
| Large amplitude tensors | Chu: 56,250 values; STC-NLSTMNet: 46,080 | 1,224 amplitude values become 16 features | Tensor values are not feature types, model parameters, or proof of superiority |
| Grouped CV | TCS-Fall: 36,000 values | No grouped CV input | Test adapted dispersion/CV; do not copy high-rate grouping unchanged |
| Doppler tensor | Construction-worker study: 16,240 values conditionally | No calibrated Doppler representation | Frequency features from amplitude are not automatically physical Doppler |
| Reduced temporal matrix | IntechOpen: 100 × 10 PCs = 1,000 | Fixed band pooling, no learned projection | Compare PCA fitted within training folds; component count is not final feature count |
| Distribution profile / image | DapFall DAPD / AmFall CWT, shape NR | No distribution image or scalogram | Separate offline challengers; define exact shape, timing, and cost first |

Source reconciliation:

- `riset_opencode.md` assigns WiFall 63 dimensions and Anti-Fall 112. The
  synthesis/`riset_chatgpt.md` retain WiFall NR and make Anti-Fall 112 conditional
  on concatenating two 56-dimensional links. Do not present either disputed
  flattened size as independently verified.
- FallDeFi's `10,000 × 60` intermediate representation in OpenCode is not the
  dimension of its final selected three-feature descriptor set.
- PCA components, subcarrier streams, statistic types, and flattened tensors
  describe different pipeline stages. Always record all relevant shapes.

#### 5.4.1 Scope, status, and fixed experiment contract

This is the execution specification for A8, not an experiment report. All new
runs start as NOT_RUN. Numerical settings below are predeclared design choices,
not measured optima. This section governs Table 4 if older A6 instructions differ.
F0–F15 are retained; F16–F27 explicitly add the previously discussed families.
The catalog is bounded; it does not claim to enumerate every conceivable feature.

| Item | Frozen setting |
|---|---|
| Data | Unified232 original takes; provisional primary pool209 under D1/manual-first +existing smoke exclusion (§2.6). Unknown identities/profiles do not automatically exclude takes; hash/revalidate after approval, do not allocate folds now |
| Identity | Hash every metadata/frame input, policy, configuration, source file used, and fold manifest; record Git HEAD plus dirty-file hashes; preserve originals |
| Training labels | Frozen primary A2: FALL in `[start-0.3 s, impact+1.0 s)`; valid pre-action outside this interval NON_FALL; post-fall excluded; unannotated fall takes excluded entirely from training. A13 sensitivity has separate policy hashes, not implicit changes to this contract |
| Non-falls | All valid phases NON_FALL; never turn CSI onset or peak into ground truth |
| Input | Canonical supported 51-pair LLTF layout; decode stored imaginary/real order correctly; never include HT-LTF in the LLTF slice |
| Primary preprocessing | Raw amplitude `hypot(I,Q)`; no smoothing, normalization, learned mask, or PCA unless the named branch explicitly changes it |
| Classifier | Project `linear-svm`, class order `[fall,non_fall]`; canonical SGD settings: 500 epochs, initial rate 0.08, regularization 0.002, rate decay `1/(1+0.01*epoch)`; no new class weighting/tuning |
| Scaling | Preserve canonical training-only `_standardize`; infer dimension from the schema; persist means/scales and existing constant-column convention |
| Seeds | `[17,29,43,71,101]`; same seed and frozen recording-level fold assignment for paired configurations |
| Windows | W24: 24 frames/stride 12; W1/W2/W3: trailing 1/2/3 s with stride 0.5 s; logical end times anchored to recording start, never fall annotations |
| Gap policy | Reject/reset on nonfinite data, nonpositive dt, unsupported layout, peer/channel change, or gap >0.5 s; threshold is proposed, not optimized |
| Clock | Host receive monotonic ns, converted with existing clock-anchor helpers for labels; log device clock separately; do not subtract UTC directly from monotonic time |

Reproduce F0 without the new gap rule once as a legacy control. Use F0 with the
same gap rule as every screened candidate; label/window changes are not feature
improvements. Keep frame order; never silently sort/deduplicate malformed input.
Reject a bad frame/segment and account for its lost coverage. Independent historical
takes start fresh. For a genuinely continuous session, only an acknowledged START
epoch or declared peer/channel/invalid-segment reset changes histories/calibration/votes;
activity, annotation and file-chunk boundaries do not. Incident state resets separately
under §5.8, never merely because classifier evidence resets.
A time window needs >=8 frames and complete duration coverage; F5 also needs
three nonempty transition blocks. Interpolation cannot bridge an invalid segment.
Labels require the entire raw source-support interval to fit one phase, including
frames bracketing a resampled point. A prediction is available only when its last
required source frame arrives. Record both logical end and actual availability.

#### 5.4.2 Exact definitions and feature ordering

Use `X[t,k]` after the declared preprocessing, T frames, L=T-1 transitions,
`dt[t]` in seconds, 16 bands `floor(16*k/51)`, and four groups `floor(4*k/51)`.
Let `d_b[t]=mean(k in band b, abs(X[t,k]-X[t-1,k]))` and
`g[t]=mean(k=0..50, abs(X[t,k]-X[t-1,k]))`. Group series `u_j[t]` are group means.
A statistic of each subcarrier is computed over time, then averaged inside its
band, unless explicitly defined otherwise. `p(x)=log1p(x)` for nonnegative
amplitude/rate/energy statistics; signed values, correlations, probabilities,
normalized positions, and fractal dimensions remain unlogged unless specified.
All feature arrays use block-major then band/group-major order, zero-based.
For PCA/tensors, use the component/axis orders explicitly stated below.

Population moments: `mu=mean(x)`, `m_r=mean((x-mu)^r)`, `sd=sqrt(max(m_2,0))`.
Quantiles use sorted linear interpolation at index `(n-1)*q`; IQR=P75-P25;
MAD=`median(abs(x-median(x)))`, without the 1.4826 multiplier. Use epsilon=1e-6
for amplitude/numerical guards, not as evidence of sensor precision. For sd<=epsilon,
set skew/excess-kurtosis/CV to zero; if either correlation input's centered norm
is<=epsilon, return zero. Constant series occupy one entropy bin. Reject nonfinite final features;
do not replace NaN/Inf with plausible zero measurements. Persist guard behavior.

| ID | Exact block definition | Final D | Primary grid / deployment condition |
|---|---|---|---|
| F0 | `p(mean_t d_b[t])`, b=0..15 | 16 | W24; exact baseline |
| F1 | F0 + `p(max_t d_b[t])` | 32 | W24; peak CSI delta, not Motion |
| F2 | F0 + `p(mean_k(max_t X-min_t X))` per band | 32 | W24 |
| F3 | F0 + `p(mean_k sd_t(X))` per band | 32 | W24; variance not an extra duplicate block |
| F4 | F0 + `p(mean_k IQR_t(X))` per band | 32 | W24 |
| F5 | Replace F0 by mean delta in 3 ordered blocks; boundaries `floor(j*L/3)`, j=0..3; apply p | 48 | W24; order block 0/1/2 then band; blocks are frame-order, not equal-time |
| F6 | F0 + `mean_k(X[last,k]-X[first,k])` per band | 32 | W24; signed |
| F7 | Replace F0 by `p(mean_t,k(abs(delta X)/dt))` per band | 16 | W24; additionally reject dt<0.001 s; deployment clock audit required |
| F8 | F0 + `[p(max g),peak_position,active_time_fraction]` | 19 | W24; threshold rules below |
| F9 | F0 + `mean_t,k(X[t,k]/max(c[k],epsilon)-1)` per band | 32 | Conditional causal calibration below |
| F10 | F0 + `p(mean_t,k X)` per band | 32 | W24; absolute-level confound control |
| F11 | Replace F0 by `p(mean_t abs(delta X[t,k]))`, k=0..50 | 51 | W24; no pooling/mask |
| F12 | Fold-fixed PCA: p(mean absolute delta) alone, or append p(sd) per PC | k / 2k | W24; k=3/5/8, six distinct configurations |
| F13 | Phase-only p(mean absolute circular delta) per band, or F0 + that block | 16 / 32 | W24; two configurations; phase gate below |
| F14 | Four groups × `[normalized spectral entropy,dominant frequency/10,p(low/high energy)]` | 12 | W2/R30; spectrum contract below |
| F15 | Raw / STFT / CWT / local-density tensor flattened in declared order | 3060 / 384 / 1920 / 1472 | W2/R30; four offline linear challengers below |
| F16 | F0 + `p(mean_k MAD_t(X))` per band | 32 | W24; robust dispersion |
| F17 | F0 + `p(mean_k(sd/max(abs(mu),epsilon)))` per band | 32 | W24; zero mean+sd =>0; adapted CV, not original TCS grouping |
| F18 | F0 + band mean of `m3/sd^3` OR `m4/sd^4-3` | 32 each | W24; skew/excess-kurtosis are two separate configurations |
| F19 | F0 + band mean of normalized 8-bin amplitude entropy | 32 | W24; training-fitted bins below |
| F20 | F0 + correlations at lags 3/6/12 for each of four groups | 28 | W2/R30; group-major then lag; normalized centered dot product |
| F21 | F0 + `[p(burst_count),longest_burst_fraction,first_active_position]` | 19 | W24; threshold/duration rules below |
| F22 | F0 + four signed OLS slopes, then four p(RMS second derivatives) | 24 | W2/R30; time in seconds; second derivative `(u[n+1]-2u[n]+u[n-1])*30^2` |
| F23 | F0 + `[rise_fraction,decay_fraction,p((rise_s+1/30)/(decay_s+1/30))]` | 19 | W24; global g peak between first/last threshold crossings; inactive =>all0 |
| F24 | F0 + six Pearson correlations of four group series | 22 | W24; pairs `(0,1),(0,2),(0,3),(1,2),(1,3),(2,3)` |
| F25 | F0 + p(mean squared Haar coefficients) for A2,D2,D1 per group | 28 | W2/R30; compact wavelet challenger below |
| F26 | F0 + four ordered singular-energy fractions | 20 | W2/R30; descending singular values of time-centered N×4 group matrix |
| F27 | F0 + Higuchi dimension for each group | 20 | W2/R30; kmax=5; algorithm below |

Thresholds and bursts (F8/F21/F23): fit theta on training quiet transitions only
(empty/still hold; annotated fall pre-action excluding walking pre-keseleo).
Use `theta=max(median(g)+3*1.4826*MAD(g),epsilon)`; no test-label calibration.
Active interval t is `(time[t-1],time[t]]` when g[t]>theta. Active fraction is
active dt / total dt. A burst is contiguous active intervals lasting >=0.1 s;
count bursts, longest duration / window duration. No activity =>all appended
position/shape/burst values zero. Peak ties select earliest index; positions are
relative to first window frame, divided by window duration. Rise/decay use
first/last active boundaries and peak time, clipped to nonnegative durations.
F8's active fraction includes short active intervals; F21 counts only qualifying
bursts. These are proposed detection settings, not measured physiological values.

F9 state machine: startup waits for 2.0 s of uninterrupted g<=theta and >=30
frames, using only arriving data. A g>theta transition discards the pending segment;
restart at its ending frame. At the first qualifying frame, set c[k] to the
per-carrier median of the shortest suffix satisfying duration/frame requirements;
freeze c until boundary/gap reset. No labels/cues are consulted during inference.
Do not output relative features until calibrated, do not backfill earlier frames,
and record time-to-calibrate/unavailable events. Train c through the same replay
procedure. A walking startup may never qualify; mark conditional coverage rather
than force calibration. Static-calibration drift is measured in continuous B5;
no untested adaptive update is part of this experiment.

F12: fit mean/covariance on unique source frames in training windows, not repeated
overlap copies. Eigenvectors sorted by descending eigenvalue; fix sign so the
largest-absolute loading is positive (lowest index breaks ties). Store the basis;
C projects with that basis and does not fit PCA. Log tied eigenvalues/library
versions; use covariance denominator n-1 (n>=2) and `Y=(X-training_mean)*basis`.
Feature order is all component deltas then all component stds for delta+std.
Six configs: k=3/5/8 × delta or delta+std; never use test explained
variance to choose k. Treat P10.1 as the same experiment, not independent evidence.

F13: before enabling, verify signed I/Q and active physical subcarrier ordering
against canonical decoder and official CSI ESP-IDF v5.5.3 documentation. If the
mapping cannot be established, status BLOCKED_MAPPING, not guessed indices.
Compute phi=atan2(imag,real); unwrap in verified frequency order (increments in
[-pi,pi), exact pi chooses -pi). Remove per-frame OLS offset+slope against verified
frequency offsets. Use `abs(atan2(sin(residual_delta),cos(residual_delta)))` for
temporal differences. Frames with an active pair amplitude<epsilon are invalid.
Persist the verified mask and band map; if width changes, define a distinct
schema/control rather than silently call it the 51-pair F13. Record quiet phase
variance, valid coverage, and day dependence; neither residual existence nor a
paper's phase gains prove ESP32 repeatability. Synthetic offset/slope-removal,
wrap/tie, future-data invariance and C-parity tests are mandatory.

R30 resampling: linear interpolation at 30 Hz within valid source segments.
For W2 use q[j]=logical_end-2+j/30, j=0..59 (N=60); W1/W3 N=30/90.
Wait for each point's right bracket, never extrapolate or fill a gap>0.5 s.
Declare the full bracket support for labels and charge delay to alarm latency.
Use matched F0 native and F0 resampled controls to separate resampling from
representation gains. No spectral/Doppler claim is made from the 30 Hz design.

F14: demean u; Hann `0.5-0.5*cos(2*pi*n/(N-1))`; one-sided rFFT of length N,
no zero-padding. Retain bins 0.15<=f<=10 Hz; probabilities from squared magnitude.
Entropy is `-sum(p*ln p)/ln(number_of_retained_bins)`; 0 ln0=0. Dominant-frequency
ties choose lowest bin. Low energy is 0.15<=f<3; high is 3<=f<=10;
ratio denominator=max(high,epsilon). Zero total power =>three zeros.
Report true support duration and bin spacing 30/N; short windows limit resolution.

F15 contracts (all use the same canonical linear classifier initially, not new
CNN/LSTM architectures; classify the representation, not a paper reproduction):
- Raw: N×51 amplitude, time-major then carrier; N=60 =>3060 scalars.
- STFT: four demeaned groups, Hann length16, hop4, rFFT length16, no padding,
  drop DC; p(power), order group×frequency×time =4×8×12 =>384 scalars.
- CWT: four demeaned groups, PyWavelets `cmor1.5-1.0`, frequencies
  `[1,2,3,4,5,6,8,10]` Hz, scales=30/f, convolution method, zero extension;
  p(abs(coefficient)^2), group×frequency×time =4×8×60 =>1920 scalars.
- Local-density surrogate: window15/hop1 on each group; training-fitted 8 bins,
  probabilities per local window, no log; group×bin×time=4×8×46 =>1472.
  This is not claimed to implement original DapFall DAPD; primary-method
  replication is outside this run. Compare the explicitly defined surrogate.
Persist original tensor shape as well as flattened D; fit scaling on training
only. Transforms may see the whole trailing window, never samples after its
availability. Report boundary-extension artifacts and measured CPU/RAM; initially
OFFLINE_ONLY means no export promised, not that an ESP32 implementation is impossible.

F19/F15 density bins: fit P1/P99 bounds on unique training frames for each carrier
(F19) or group (density); eight equal-width bins, clip to end bins, last bin includes
upper bound. Degenerate bounds produce zero entropy and a single occupied bin;
normalized entropy divides by ln8. Save edges, never refit on validation/test.
F20 correlations use centered lagged vectors with denominator sqrt(sum(x^2)*sum(y^2));
zero denominator=>0, clip rounding to [-1,1]; same zero-variance rule for F24.
F22 slopes use OLS centered time; zero time variance is invalid, not slope zero.
F25: demean each group, orthonormal Haar using `(x_even+x_odd)/sqrt(2)` and
`(x_even-x_odd)/sqrt(2)`; pad N to next power of2 by repeating its last value
(W2:60 to64; W1:30 to32; W3:90 to128). Two levels; coefficient order A2,D2,D1
per group; evaluate energy per coefficient count. No external future data is used.
F26: singular energy fractions `s_i^2/sum(s^2)`; all zero=>four zeros; no PCA fit
is needed for this per-window four-column statistic. Measure cost before export.
F27: for k=1..5 and m=0..k-1 use n=floor((N-1-m)/k),
`L_m(k)=(N-1)/(n*k*k)*sum(i=1..n,abs(u[m+i*k]-u[m+(i-1)*k]))`.
Average valid L_m over m; regress ln(L(k)) on ln(1/k); slope is the descriptor.
All-flat=>0; otherwise omit zero L(k), require >=2 positive k values or invalidate.

#### 5.4.3 Implementation prerequisites and software tests

These are future implementation tasks, not changes made by this plan update:
1. Extend A2 policy semantics with margins and schema-based preprocessing checks;
   retain legacy policies. D1 and this feature schema must never silently clash.
2. Add a feature registry (planned `fall_detection/feature_representations.py`)
   with fit/transform/reset contracts, ordered names, D, config hash, and availability
   metadata. Legacy F0 remains callable and numerically unchanged.
3. Generalize `classifier_models.py`, phase trainer, and artifact validation from
   hard-coded 16 to declared D; inject local seeds without global RNG side effects.
   Keep the canonical loss/optimizer. If accelerated, verify against its original
   implementation on toy and real fixtures; a sklearn substitute cannot decide winners.
4. Add explicit folds, second windows, source-support/gap handling, and a runner
   (planned `fall_detection/feature_ablation.py`) reusing dataset audit/validation,
   canonical parsing, phase conversion, and existing prediction outputs.
5. Extend exporter/firmware only for finalists: schema dispatch, generated D/names,
   masks/calibration/PCA state, and timing contract. Export a full-data final fit,
   never an OOF model; do not overwrite the active model during experiments.
6. Pin actual Python/NumPy/PyWavelets versions and numerical backend in the run
   manifest before numerical branches. Existing core is standard-library Python;
   no dedicated feature dependency lock currently exists. Missing packages are
   BLOCKED_DEPENDENCY; do not silently use a different interpreter/algorithm.

Required fixture/test groups:
- F0 old/new parity; constant/ramp/reversed/spike/plateau signals; pooling-before-
  difference counterexample; dimension/order checks for every F/config combination.
- Quantile/MAD/zero moments, bins/entropy, threshold ties, minimum burst durations,
  first/last activity, calibration warmup/reset/drift, PCA sign/ties and saved-basis use.
- Phase I/Q orientation/unwrap/linear-trend removal; FFT sinusoid bin/ties/DC/zero
  power; STFT/CWT/density shapes; Haar constant/impulse; SVD rank0/1; Higuchi flat/ramp.
- Timestamp duplicates, short/long gaps, missing brackets, clock conversion,
  no future/annotation access, no cross-take state, no PCA/scaler fit on test frames.
- Label boundary endpoints, no contained FALL at W3, per-configuration support
  differences, missing train class, empty folds, skipped dependency/host-C checks.

Currently valid software test command (repository root; not run in this update):
`python3 -m unittest discover -s fall_detection/tests -v`.
Host parity tests need gcc and may otherwise skip; skipped C tests are not a pass.
New registry tests must cover all enabled configs. Nonfinite outputs or changed F0
behavior stop the campaign. Fixture references are float64; C deployment is float32.

#### 5.4.4 Splits, inference replay, and metrics

AFTER approval, prepare per-seed E1 five-fold original-take/verified-lineage
assignments using A10's audited allocator; freeze all-take ownership and the F0
eligibility view separately. Verify both classes in fit/selection folds from actual
strict windows, not take labels alone. Reuse assignments when feature coverage changes.
E1 is count-level plausible, not an executed or certified split (§5.6.7).
Proposed unified E2 uses all eligible OTHER days for training: E2a=test11-04,
E2b=test11-14, E2c=test11-07, E2d=test11-19. Smoke stays excluded provisionally.
Incomplete FALL contributes no D1 fitting frames; replay it only as separately
identified held-out take diagnostics. E2c now has39 annotated training falls and
is no longer automatically blocked. Day-independent nested selection is a different,
currently unsupported claim. Subject/session schemes require proven membership;
unknown identities retain E1 eligibility. No manifests are created in this update.

Training uses strict labeled windows only. Inference replays each complete held-out
take, including pre/post/unlabeled windows, through all causal states; do not reset
at annotation boundaries or replay only FALL windows. Emit raw class, score margin,
stabilized class, and separate Motion-gated result. Voting immediately adopts the first raw class after startup/reset (including
FALL); subsequent entry uses 2-of-3 and release 3 consecutive NON_FALL. Fresh state
per independent historical take; continuous sessions retain state across activities and
file chunks, using only acknowledged START/declared evidence resets. Invalid segments
clear window/vote state and are logged, not NON_FALL; incidents follow §5.8.
These are proposed experiment reset rules; §5.7 separately reproduces current
production behavior before comparing any new peer/channel/time-gap reset policy.
A FALL rising edge is one prediction episode; count a new episode only after release.
Historical tables may call these "alarms": they are not confirmed incidents or delivered
notifications. §5.8 adds separate lifecycle metrics without redefining these controls.
Motion requires synchronized matching-peer diagnostics and current freshness/threshold
logic; if absent, gated metrics are UNAVAILABLE, never simulated from CSI peaks.

| Output | Definition / denominator |
|---|---|
| Window metrics | Confusion matrix and class P/R/F1 on held-out strict windows; macro-F1 ranking uses E1 only; undefined class denominators are NA, not invented zero recall; raw/voted separate |
| Annotated event recall | OOF E1 annotated falls with a new alarm in D1 interval / all eligible held-out annotated falls; missing valid event coverage is a miss |
| Unannotated recall | E2a fall takes with any alarm / held-out unannotated fall takes; no timing claim |
| False alarms | Non-fall takes with >=1 alarm / all held-out non-fall takes; episode counts by activity/day/channel/acquisition profile; report sparse/UNKNOWN strata and NA denominators |
| Latency | Alarm availability minus observer start for matched annotated events; median/P95/range, count misses separately; early margin alarms may be negative |
| Pre-event/post-event alarms | Report outside D1 separately; an already-active pre-event alarm does not become a detected fall merely by crossing the annotation |
| Coverage | Valid/attempted decisions, labeled windows retained per class, event coverage, calibration delay and resets; paired F0 on same eligible subset plus original-set denominators |
| Day probe | E3 grouped by take on quiet windows: raw/balanced accuracy, training-fold majority-day baseline, confusion matrix and per-day/activity support; diagnostic only, never feature selection or a ranking tie-breaker |
| Cost | Extraction and classification separately, peak RAM/state/stack, artifact bytes, CPU time per decision and amortized per frame; host timing is not hardware measurement |
| Continuous false alarms | B5 episode count / monitored negative hours; also valid-output hours; never derive deployment FA/hour from concatenated short takes |

E3 runs for F0 plus at most3 shortlisted compact configurations, with the same
5-seed/5-fold take-group manifests made from quiet data and class-presence checks.
It cannot select fall features by day accuracy. Unsupported day-probe folds are
reported as blocked; do not compare raw accuracy to a balanced chance baseline.
Use seeds above for all schemes; persist every per-seed result plus median/min/max.
For exploratory uncertainty, paired bootstrap whole takes within activity/day,
1000 resamples, RNG seed20261118; paired 2.5/97.5 percentiles of differences.
Keep all windows of a sampled take together. Report resampling unit and limited
session count; these intervals are not cross-session guarantees. Exact McNemar
is optional descriptive output, not a multiple-comparison proof of a winner.

#### 5.4.5 Campaign order, selection, and stopping rules

| Stage | Explicit run set | Exit condition |
|---|---|---|
| T4-0 Prepare/pilot | Prepare without fitting: snapshot, environment lock, source-support/label audit, seeded folds and fixtures; then pilot full-size fits on E1 fold0/seed17 for F0 and largest enabled D | Tests/contracts pass; both train classes present; pilot times/projected workload saved without held-out ranking |
| T4-1 Core screen | W24/raw/gap0.5: F0–F8,F10,F11,F16,F17,F18.skew,F18.kurt,F19,F21,F23,F24 (19 configurations) | Proposed E1/E2a–E2d ×5 seeds after approval/support checks; pooled and per-profile counts/coverage |
| T4-2 Branches | F12 six,F13 two,F14 one,F15 four,F20/F22/F25/F26/F27 one each (18); W2 for R30 branches, W24 for PCA/phase; matched controls for each support/grid | Status/result for every branch; phase/dependency/support blockers explicitly recorded; F9 separately screened only with valid causal calibration |
| T4-3 Combine | Best two eligible distinct core appended blocks under the ranking below; test F0+blockA+blockB once; skip if fewer than2 pass; ties resolve by smaller D then lexical ID | Matched controls, redundancy/coverage reported; no unconstrained feature-subset search or concatenating replacements without a new schema |
| T4-4 Interactions | At most 3 provisional compact finalists +F0 ×W1/W2/W3 ×raw/one A6-selected causal preprocessing; stride0.5 fixed | All same window/preprocessing controls present; reject empty-class grids, do not alter label margins to save them |
| T4-5 Deployment | At most 2 finalists: host-C parity, full-data export into report directory, firmware resource/replay tests after preflight | Numerical/timing/state parity and resource targets pass; no automatic flash/replacement of active model |
| T4-6 Confirmation | Frozen baseline+finalists; at least3 new mixed annotated sessions across days, each containing both classes; B5 >=1 monitored negative hour across sessions, a proposed data target; F9 warmup/drift tests | Train only remaining groups; valid class-preserving session/day holdouts; reserve latest session as untouched final test; no threshold/model tuning on it |

If all four unified E2 diagnostics are approved/supported, each config requires
(5 E1 +4 E2)×5=45 fits. Core19 =>855 fits;18 branches plus two W2 F0 controls
=>900 more; F9 adds45. These are conditional planning estimates, not scheduled
or completed work, excluding E3, nested selection, support-matched extra fits,
interactions and deployment fits. Runner emits exact scheduled/completed counts.
No launch before a full-size fit pilot projects workload; if >48 CPU-hours,
pause for user scheduling/optimization approval rather than silently reduce seeds,
epochs, folds, or replace the classifier. Completed runs can resume only when all
input/config/source hashes match; otherwise use a new run directory.

Eligibility: finite/schema-valid, causal availability, supported folds, and no
coverage trick. For provisional ranking protect E2a recall (median loses at most
1/20 take vs matched F0) and E1 annotated event recall (at most 0.05 absolute drop,
a proposed guard). Report per-subtype losses. A drop in false alarms alone is not
an improvement if windows/events were hidden. Overall event coverage must be>=95%
for unconditional deployment candidacy; F9 below this stays CONDITIONAL.
For explicitly exploratory reports, order remaining candidates by pooled negative-
take alarm rate across E2a/E2b/E2d, then event recall, macro-F1, median latency,
measured cost and smaller D. Also report each day/profile and annotated E2c/E2d
misses; require non-worsening negative-take results in each supported day to call
it consistently improved. These outer results cannot select a confirmatory model;
that requires training-owned inner selection and untouched new confirmation.
Use paired differences/seed ranges to describe uncertainty; overlapping evidence
means retain baseline/simpler candidate provisionally, not assert equivalence.
All old-day selection is exploratory: final confirmation uses new untouched data.

Deployment targets (proposed, not measured): additional RAM state<=4KiB relative
to matched F0 window, total incremental extraction+inference CPU<=2.9ms per frame
amortized, decision-time P99<=50ms at stride0.5s, no incremental queue loss. Report
absolute baseline/candidate RAM and cold/warm worst cases too. Numerical gate:
`abs(C-Python)<=1e-5+1e-4*abs(Python)` for each feature and score; class disagreement
is acceptable only within that score-margin tolerance, counted explicitly.
An offline-only branch cannot win a firmware recommendation without an actual
causal implementation and measured targets; it can win a research comparison.

#### 5.4.6 Planned runner interface, result files, and completion

The following interface is to be IMPLEMENTED; no such runner/options exist now.
The current phase CLI only has recordings/policy/algorithm/group-by(take/session/
subject)/folds/output/fit-final. Do not pretend it already supports feature IDs,
seed manifests, time windows, calibration, day holdout, or these commands.
Proposed runner defaults come from the frozen table above; `prepare` requires A2
policy to exist and creates config/inventory/manifests, without training.
`pilot` records fit timings only; screen/branches check the workload gate before
starting. `report` includes incomplete/blocked configurations, not just successes.

```sh
python3 -m fall_detection.feature_ablation --stage prepare --run-dir <RUN_DIR>
python3 -m fall_detection.feature_ablation --stage pilot --run-dir <RUN_DIR>
python3 -m fall_detection.feature_ablation --stage screen --run-dir <RUN_DIR>
python3 -m fall_detection.feature_ablation --stage branches --run-dir <RUN_DIR>
python3 -m fall_detection.feature_ablation --stage combine --run-dir <RUN_DIR>
python3 -m fall_detection.feature_ablation --stage interactions --run-dir <RUN_DIR>
python3 -m fall_detection.feature_ablation --stage parity --run-dir <RUN_DIR>
python3 -m fall_detection.feature_ablation --stage report --run-dir <RUN_DIR>
```

RUN_DIR is a new `reports/feature_ablation/<UTC_run_id>/` only at execution;
commands are specification examples, not executed here. Add `--resume` with hash
verification. Confirmation requires a separately frozen new-data manifest and
explicit confirmation stage; it must not reuse development data as an untouched test.
Proposed call: `python3 -m fall_detection.feature_ablation --stage confirm
--run-dir <RUN_DIR> --confirmation-manifest <NEW_DATA_MANIFEST>` (one shell line).
It writes to a separate confirmation subdirectory with new-data hashes and frozen
shortlist; reject any overlap with the reserved final-test session during fitting.

| Required file | Required contents |
|---|---|
| `config.json`, `environment.lock.json` | Seeds, all numeric/clock/label/coverage/resource rules, package/backend versions, source hashes; freeze before fitting |
| `dataset_manifest.csv`, `folds.json` | Original take IDs/files/hashes, activity/day/IDs/annotation eligibility, exclusions, source windows, per-seed group split and class counts |
| `feature_inventory.csv`, `feature_schema.json` | Every variant, block order/formula/D/shape, transform parameters, fitted-state ownership, causality/status/blocker; actual fitted schema stored per fold |
| `results.csv` | Config×scheme×seed×fold rows plus fold=ALL aggregates: run_status/feasibility, train/test windows/events, coverage, P/R/F1/confusion, alarm denominators, latency/misses, runtime; blank/NA for unrun/undefined, never fake0 |
| `predictions.csv`, `alarms_per_take.csv` | Window/support/availability times, label, scores, raw/voted/gated decisions, invalid reason, annotation match, episode times, calibration/reset metadata |
| `paired_differences.csv`, `costs.csv` | Matched F0 deltas, per-activity/day/seed statistics, bootstrap intervals, host vs device provenance, absolute/incremental RAM/CPU |
| `tests.json`, `summary.md`, `decision.json` | Passed/failed/skipped fixtures, ranked evidence, rejected/blocked reasons, provisional vs confirmed choice, freeze date and next required data |

Separate fields: run_status = NOT_RUN/RUNNING/COMPLETE/BLOCKED_DEPENDENCY/
BLOCKED_MAPPING/BLOCKED_NO_TRAIN_FALL/BLOCKED_COVERAGE/FAILED_TEST;
feasibility = UNVERIFIED/CONDITIONAL/OFFLINE_ONLY/DEPLOYABLE/REJECTED_RESOURCE.
An offline or conditional run can be COMPLETE without being adopted. Mark hardware
DEPLOYABLE only after actual C/resource checks, not from a Python runtime estimate.
Results template (all values remain pending until an actual reproducible run):

| Variant | Status | D | Coverage | Event recall | False-alarm takes | Macro-F1 | Latency | RAM/CPU | Decision |
|---|---|---|---|---|---|---|---|---|---|
| F0–F27 and parameter variants | NOT_RUN | Per inventory | Pending | Pending | Pending | Pending | Pending | Pending | None |

A8 complete only when every scheduled variant has a result or explicit blocker,
paired controls and artifact/test files exist, failed coverage/folds are reported,
and the decision distinguishes provisional offline evidence from deployment/new-
session confirmation. Do not overwrite T8 historical proxy results: append Table4
results with their own hashes and provenance. No new training was run in this update.

### 5.5 Table 5 — Models, training, and combined pipelines (A9)

#### 5.5.1 Scope and evidence boundary

This is an experimental specification, not completed training or a deployment
recommendation. All stages below are NOT_RUN. Settings are proposed defaults,
not measured optima. Only this living plan is updated; no packages, runners,
models, firmware, builds, flashes, or new experiment results are produced here.
Table 4 remains its frozen, unweighted Linear SVM feature comparison. Table 5
adds separately identified model/training experiments, never retrospectively
relabels a Table 4 run as a controlled model comparison.

The bounded catalog covers the practical compact statistical, discriminative,
tree, prototype, anomaly, and temporal families discussed for this receiver.
It cannot enumerate every conceivable architecture or parameter combination.
Training occurs on the host. Inference feasibility depends on the complete
pipeline, including acquisition/history, transforms, state, and concurrent Wi-Fi
work; host training epochs do not consume ESP32 inference time.

| Evidence / constraint | Consequence |
|---|---|
| One ESP32-WROOM-32 receiver/antenna; supported LLTF has 51 complex int8 pairs | No inter-antenna features, invented streams, or assumption of ESP32-S3 acceleration/PSRAM |
| Current amplitude representation is F0, not CSI phase | A more complex model cannot restore discarded temporal order or phase |
| Canonical host supports centroid, logistic regression, Linear SVM, tree, RF | Other entries require new, tested host implementations; existing phase exporter/inference supports only linear SVM |
| Generated source model uses start-to-impact; default policy uses cue-to-tail; A2 uses annotated margins | Preserve three identities; export/source inspection does not prove the currently flashed model |
| Old source build reported app 0xf1a20 in 0x100000 partition, 264-byte model, 4896-byte history | Historical/static evidence only; fresh build, live memory, and timing must determine current capacity |
| Unified annotated falls occur on11-07 and11-19; raw session ID is reused | Take CV remains diagnostic; both fall-day holdouts retain training FALL, but three day-independent inner folds are unsupported (§5.6.7) |

Literature anchors checked during the preceding Table 5 analysis:
- [TCS-Fall](https://pmc.ncbi.nlm.nih.gov/articles/PMC11151769/): subject-exclusive
  testing and continuous evaluation motivate stronger splits/events, not copying
  its 400×90 CNN input or 8-second context to this hardware.
- [STC-NLSTMNet](https://pmc.ncbi.nlm.nih.gov/articles/PMC9823549/): reported random
  ten-fold evaluation does not establish recording-group separation; do not claim
  proven leakage or transfer its large architecture without a compact test.
- WiFall 2014 (DOI 10.1109/INFOCOM.2014.6847948) and its 2017 journal work
  (DOI 10.1109/TMC.2016.2557792) are distinct; the latter includes OC-SVM/RF.
- FallDeFi conference paper (DOI 10.1145/3161183) exists independently of the
  dissertation. Exact RT-Fall kernel/stage details remain unresolved here.
- Table 5 also motivates SVM/LSTM, CNN/GRU, transfer, and anomaly families.
  Published learning rates, SVM C, custom lambda, and accuracy are not mutually
  interchangeable project settings or evidence of MCU feasibility.

#### 5.5.2 Candidate model catalog and bounded defaults

All D below denotes the declared input dimension. Binary class order remains
[fall,non_fall]. Nonlinear/sequence scores get explicit semantics; do not label
hinge margins, tree votes, novelty distances, or uncalibrated logits as probability.
The default vector grid uses training-only canonical z-score, T0 training,
W24/raw amplitude/gap0.5 and argmax/zero margin. Tree scaling is retained as a
matched control; omitting scaling is a separately named later optimization.

C = compact implementation candidate; K = conditional bounded implementation;
O = initially offline-only benchmark/teacher. None of these labels means measured
DEPLOYABLE. A configured member can fail even if its family has feasible members.
Parameters in braces are bounded tuning neighbors, not exhaustive Cartesian grids.

| ID | Family / reference configuration | Bounded neighbors / constraints | Tier |
|---|---|---|---|
| M0 | Canonical standardized nearest centroid, squared Euclidean distance, empirical mean per class | One centroid/class; T1 has no effect on a class mean when weights are constant within class | C |
| M1 | Canonical softmax logistic regression, 700 full-batch epochs, LR0.12, L2=0.001 | LR {0.04,0.12}; L2 {0.0001,0.001,0.01}; epochs fixed outside T6 | C |
| M2 | Canonical one-vs-rest Linear SVM, 500 epochs, LR0.08, lambda0.002, decay 1/(1+0.01*epoch) | LR {0.02,0.08}; lambda {0.0002,0.002,0.02}; preserve hinge/bias/tie semantics | C |
| M3 | Canonical Gini tree, max depth4, minimum leaf2 | depth {2,3,4}; leaf {2,5}; persist comparator and node ordering | C |
| M4 | Canonical RF: 9 bootstrapped trees, depth4, leaf2, floor(sqrt(D)) features/split | trees {5,9,15}; depth {3,4}; <=31 nodes/tree | C |
| M5 | Shrinkage LDA, pooled covariance, shrink0.1, equal priors | shrink {0.01,0.1,0.5}; export affine discriminants, covariance inversion is host-only | C |
| M6 | Diagonal QDA, equal priors, variance floor1e-4 in standardized units | floor {1e-5,1e-4,1e-3}; full shrinkage QDA only for D<=16, shrink0.1, named separate branch | C/K |
| M7 | Gaussian Naive Bayes, equal priors, variance floor1e-4 | floor {1e-5,1e-4,1e-3}; log likelihood; constant-column fixtures | C |
| M8 | Class-conditional diagonal GMM, 2 components/class, equal class priors | components {1,2,4}; EM max100, tolerance1e-4, floor1e-4, seeded k-means init | K |
| M9 | RBF SVM, C=1, gamma=1/D | C {0.1,1,10}; gamma {0.1/D,1/D,10/D}; reference must retain <=128 SVs, otherwise resource-blocked | K |
| M10 | Degree2 polynomial SVM, C=1, gamma=1/D, coef0=1 | C {0.1,1,10}; SV<=128; no unbounded kernel-degree search | K |
| M11 | Bounded kNN, k=3, Euclidean, inverse-distance vote, <=128 exemplars | k {1,3,5}; 64/128 exemplars; deterministic training-only class/take-balanced farthest-first selection | K |
| M12 | Prototype-distance classifier, 4 k-means centroids/class, nearest-prototype label | prototypes {1,4,8}/class; max100 iterations, tolerance1e-4; prototypes fitted on training only | C |
| M13 | Binary gradient-boosted trees, logistic loss, 16 trees, depth2, LR0.1, leaf5 | trees {8,16,32}; depth {1,2,3}; LR {0.05,0.1}; <=15 nodes/tree | K |
| M14 | Tiny MLP D→16 ReLU→2 logits, Adam LR0.001, L2=1e-4, batch32, max200 epochs | hidden {8,16,32}; one/two hidden layers (16→8); LR {0.0003,0.001}; D<=64 | K |
| M15 | NON_FALL-only diagonal Mahalanobis distance (standardized negative mean/variance, floor1e-4) | Full shrink0.1 covariance for D<=16 as named branch; high distance=novelty, not FALL identity | C/K |
| M16 | NON_FALL-only RBF One-Class SVM, nu0.05, gamma1/D | nu {0.01,0.05,0.1}; gamma {0.1/D,1/D}; SV<=128; anomaly threshold fitted separately | K |
| M17 | NON_FALL-only isolation forest, 16 trees, subsample64, depth<=6 | trees {8,16}; subsample {32,64}; explicit path-length score, max127 nodes/tree | K |
| M18 | NON_FALL-only tiny AE D→8 ReLU→D linear, reconstruction MSE | bottleneck {4,8,16}; D<=64; Adam0.001, batch32, 200 epochs; novelty is not proof of fall | K |
| M19 | Two class-conditional left-to-right Gaussian HMMs, 3 states each, diagonal emissions on S1/S2 | states {2,3,4}; self/next transitions, final self-loop; floor1e-4, max100 EM iterations, tolerance1e-4 | K |
| M20 | DTW template classifier, 4 templates/class, band width6 at N=60 | templates {1,4}/class, width {3,6}; two-row DP; training medoid templates, duration-normalized squared distance | K |
| M21 | Tiny 1D CNN: conv8/kernel5→ReLU→conv8/kernel3→ReLU→global average→2 logits | channels {4,8,16}; stride1, valid padding; Adam0.001, batch16, max200 epochs | K |
| M22 | Tiny causal TCN: two conv8/kernel3 blocks, dilations1/2, ReLU, global average→2 | channels {4,8,16}; left zero-padding within window only, no residual branches by default | K |
| M23 | Tiny GRU, 8 hidden units→2 logits at final timestep | hidden {4,8,16}; Adam0.001, batch16, max200 epochs; explicit gate/reset convention | K |
| M24 | Tiny LSTM, 8 hidden units→2 logits at final timestep | hidden {4,8,16}; same optimizer; persist gate order, cell/hidden initialization | K |

M8/M19 EM nonconvergence, singular fits, neural nonfinite loss, and kernel
support-vector overflow must be reported, not silently replaced by another model.
M6 diagonal QDA and M7 Gaussian NB can be algebraically identical under equal priors
and matching variance estimates; implement a parity check and mark duplicate cells,
not independent model evidence. Never claim different family names prove diversity.
M9/M10/M16 may be distilled to a small student or evaluated with a separately
identified compressed approximation; never prune SVs and call it the exact model.
M11 has a bounded training dictionary, not kNN over all overlapping windows.
M17's large leaf/node footprint may fail flash even though working RAM is small.
Flash-resident const tables need their access/timing tested, not counted as free.

Analytical preflight for each configured model (arithmetic/complexity, NOT profiling):
- Binary canonical linear storage including scaler: 4*(4D+2) bytes; M14 with one
  hidden layer H: 4*(D*H+3H+2) model bytes plus scaler. At D16/H16 this is1224
  model bytes, not the whole RAM footprint. Linear scoring is O(D), MLP O(D*H).
- Diagonal likelihood models are O(D) per component; dense QDA is O(D^2).
  LDA folds training covariance into affine inference weights. Density models need
  log/exp implementation timing and stability checks, not just parameter counts.
- Binary kernel tables require roughly4*S*(D+1) bytes for SVs/coefficients plus
  scaler/kernel scalars, O(S*D) scoring and S exp calls for RBF. S<=128 bounds
  tables; it does not establish that the application image fits its partition.
- kNN stores4*K*D bytes plus labels/scaler; prototype scoring O(K*D). Trees store
  every node/leaf record in the declared serializer; traversal O(trees*depth).
- M21 default convolution model has40*C+226 float parameters (C input channels);
  C4 gives386 floats=1544 model bytes, excluding scaler/input/activations/code.
  CNN/TCN MACs and simultaneously live activation tensors follow actual layer shapes.
- PyTorch-default GRU with two bias vectors has3H*(C+H)+6H+2H+2 parameters;
  LSTM has4H*(C+H)+8H+2H+2, including final binary layer. Both perform O(N*H*(C+H))
  work per complete-window decision. State reset does not eliminate input/history.
- HMM forward costs O(N*states^2) plus diagonal emission work; DTW costs
  O(templates*N*band_width*C), uses two DP rows but still retains templates/input.
Emit concrete parameter/node/SV/buffer counts, const vs RAM placement, and estimated
MACs per configured cell before pilot. No prediction of MCU latency is called measured.

Reference libraries are permitted for genuinely new families, with pinned versions
and exact solver/loss/config recorded. They must not replace M0–M4 and claim
canonical-baseline equivalence. Proposed dependencies: NumPy/SciPy/scikit-learn for
statistical/kernel references, PyTorch for compact neural training, PyWavelets for
existing spectral branches. A neural C exporter/operator backend must be selected
and version-pinned before neural parity; unavailable backend = BLOCKED_OPERATOR.
Large published CNN-LSTM/ResNet/R(2+1)D, GNN, Transformer, full-resolution
scalograms, and bidirectional/full-recording models stay O benchmarks/teachers.
Tiny versions are not excluded by name alone: admitting a new architecture needs
a new frozen operator/shape/budget specification and user-approved scope extension.

#### 5.5.3 Representation and model compatibility

Reuse the exact F0–F27 and P1–P11 definitions; do not create duplicate evidence
for renamed PCA/phase/preprocessing branches. Hash feature order, units, shape,
clock, fitted state, support, and reset behavior along with the model.

| Representation | Available information / model pairing | Initial experiment policy |
|---|---|---|
| F0 D16 | Mean delta; all compact vector classifiers/anomaly detectors | Mandatory baseline for every vector family |
| F1/F3 D32, F5 D48, F11 D51, F12.k5.delta D5 | Peak, dispersion, coarse order, carrier detail, learned projection | Structural sentinels; fixed before model results, not merely Table4 linear winners |
| Other F0–F27 compact variants | Relative/absolute profile, range/robust stats, signed/time derivatives, entropy/correlation/bursts/Haar/SVD/fractal descriptors | Individual Table4 tests preserved; Table5 interaction pool adds at most2 exploratory Table4 shortlists |
| F13 phase D16/32; HT-LTF-derived schemas | Additional stream/layout information | Mapping, valid coverage, and schema gates first; never guess hardware ordering |
| F14 D12 and F15 tensors D3060/384/1920/1472 | Spectral/tensor alternatives | Initially offline benchmarks; compact deployment only after complete transform/profile parity |
| S1 N×4 group-amplitude sequence | Four group means from §5.4, W2/R30, N60; time-major | M19–M24 initial sequence input; 240 floats=960 bytes of input, arithmetic only |
| S2 N×5 PCA sequence | Training-frame PCA k5 using F12 basis rules, W2/R30 | M19–M24 second input; 300 floats=1200 bytes, plus basis/state costs |
| S3 N×16 band-amplitude sequence | Means across each band before model, not F0 delta extraction | Conditional extension for at most2 temporal finalists; 960 floats=3840 bytes |
| S4 N×51 raw amplitude / F15 raw | Original carrier sequence | Offline teacher/control first; 3060 floats=12240 bytes, not a claim that it fits live RAM |

Sequence scaling uses unique training frames per channel, not duplicated overlapping
windows. Train and infer on complete trailing windows; label strict full raw support.
HMM starts in state0 with probability1; nonfinal states initialize self/next at
0.5/0.5, final state self at1; training-only EM, log-domain forward likelihood/N;
transition zeros stay impossible. DTW templates share N/channels and scaling.
CNN/TCN/GRU/LSTM initially reset hidden/filter state at each window; streaming
state carry is a new variant requiring its own chronological training/replay/parity.
Neural classifiers use unweighted cross-entropy at T0, no dropout/data shuffle
across splits; epoch batches shuffle only training windows with the local seed.
Use PyTorch module-default initialization with its pinned version/local seed,
Adam betas(0.9,0.999)/epsilon1e-8; L2 is an explicit loss penalty, not silently
decoupled AdamW. M18 uses MSE. Loss reduction is mean over examples (AE first
mean over input dimensions); weighted variants mean-normalize weights. Biases are
unpenalized; M14 L2=1e-4, M18/M21–M24 L2=0 at reference. Log batch weights.
LDA/full covariance shrink toward trace(cov)/D times identity,
with diagonal floor1e-4; class likelihood priors stay equal unless a named variant.
No per-take full-record normalization, annotation-triggered crop, future context,
or hidden state imported from a different take. All S grids include matched W2/R30
F0 controls to separate model, context length, and resampling effects.
Define storage reuse explicitly; do not add full S buffers to amplitude history
without counting both. A float32 buffer is not a quantized buffer by assumption.

#### 5.5.4 Data preparation and implementation prerequisites

Complete these in order before fitting a campaign:
1. Re-audit complete metadata/frame pairs, TEST01/smoke/incomplete exclusions,
   annotations and timestamps; recount class, subtype, day, subject, session,
   channel, duration, gap, and supported-layout distributions. Preserve raw files.
   Historical 182/189/130-take inventories are different snapshots, not defaults.
2. Freeze SHA-256 inputs, Git HEAD+dirty hashes, A2 label policy and a membership
   manifest. Mark unannotated fall takes TEST_ONLY; no pre/post windows from them
   enter supervised, self-supervised, PCA, calibration, or negative-only training.
3. Implement A1/A2/A4/A7 and the §5.4 feature registry/support tests. Validate
   observer clocks, half-open label endpoints, full-support containment, no label
   overlap and class retention. Interval notation elsewhere lists bounds; actual
   training/event inclusion uses [start-0.3,impact+1.0), preserving the canonical
   half-open convention. Empty positive W3 grids are blocked, not relabeled.
4. Generalize classifier configuration/dimension/local seed; preserve old M0–M4
   default outputs. Add immutable algorithm/optimizer/hyperparameter/sample-weight
   contracts, score semantics, class order, serializers, and per-family limits.
5. Implement fold manifests, nested fitting, frame deduplication for learned
   transforms, training-only caches, negative-only fits, group-aware validation,
   convergence/failure logging, full-record replay and one-to-one event matching.
6. Add planned `fall_detection/model_experiments.py` and model/export dispatch;
   this module/options do not exist now. Keep phase/legacy CLI working. Final
   artifacts must reject OOF/fold models, invalid D/state, missing provenance,
   nonfinite values, inconsistent class order and unsupported operators.
7. Pin interpreter, packages, CPU threads/BLAS, framework/solver/exporter versions,
   deterministic flags and seeds [17,29,43,71,101]. No automatic package install or
   alternate interpreter. Record nondeterministic kernels; use deterministic CPU
   reference for parity. Cache only with transform, training-group and source hashes.
8. Test fixtures: F0/canonical regression; weighted loss/gradient/tree impurity;
   constant/rank-deficient/imbalanced data; kernel distances/support caps; prototype
   ties; likelihood/logsumexp; HMM/DTW sequences; neural operators/gate conventions;
   split leakage sentinels; all availability/reset/gap/calibration/gating paths.
9. Pilot full-size fold0/seed17 F0-M2, largest enabled vector, and enabled temporal
   model. Measure fit/memory/export estimates without examining outer-test rankings.
   Save exact projected scheduled fits and host resource requirements before launch.

Existing test command: `python3 -m unittest discover -s fall_detection/tests -v`.
No tests are run by this plan edit. Add registry/family/nesting/replay/export tests
when implementing. Skipped gcc/backend/parity tests mean BLOCKED, not passed.
If workload exceeds 48 CPU-hours, pause for scheduling/optimization approval;
never silently reduce folds, seeds, epochs, or swap baseline algorithms.

#### 5.5.5 Training strategies, imbalance, and calibration

All variants retain all natural-prevalence validation/test windows/events. Count
positive windows, positive events and original takes separately. Accuracy includes
an always-NON_FALL baseline and cannot drive selection. More overlapping windows
or augmented copies do not increase the number of independent fall events.

| ID | Isolated strategy / proposed default | Rules and deployment implications |
|---|---|---|
| T0 | Canonical unweighted training | Mandatory paired control; M0–M4 exact defaults |
| T1 | Class-balanced loss: w_i=N/(2*N_class(i)) | Training counts only; normalize mean weight1; weighted impurity/loss, not arbitrary score multiplication |
| T2 | Equal-take weights: w_i=1/n_take(i), mean-normalized | Prevent long recordings dominating; priors unchanged unless named |
| T3 | Equal total weight per class and per contributing take within class: w_i=1/(G_class(i)*n_take,class(i)), mean-normalized | Not naive multiplication of T1/T2; inspect max/min weight and subtype/day contributions |
| T4 | Negative-window sampling to at most3 negatives/positive | Training only; round-robin by negative activity then take, chronological spread, seeded tie-breaking; never drop positives |
| T5 | Causal source augmentation, one additional copy per training take/epoch | Seeded amplitude gain U[0.9,1.1] and independent carrier noise SD0.02*training quiet SD; apply on amplitude then full pipeline, clamp>=0; same copy provenance/split as parent |
| T6 | Grouped early stopping | MLP/AE/sequences: check every5 epochs, patience20, min delta1e-4, max200; validation loss only; M1/M2 early stopping requires explicit separate implementation/fixtures |
| T7 | Operating-threshold selection | Grouped inner-OOF margin/novelty predictions and full replay only; freeze threshold before outer prediction |
| T8 | Probability calibration | Binary Platt logistic fit on cross-fitted inner scores, L2=0.001; ECE/Brier/log loss evaluated held out; calibrated probabilities are optional, never infer them from margins |
| T9 | Post-training int8 quantization | Training-only representative data; explicit tensor scales/zero points/rounding/saturation; separate quantized-reference parity and resource tests |
| T10 | Quantization-aware training | Only after measured PTQ degradation; same training groups, up to50 extra epochs LR0.0001; validation-controlled, no test rescue |
| T11 | Distillation to M1/M14 | Teacher trained only current fit groups (inner or outer), excluding every held-out fold; cross-fitted targets for student training examples; temperature2, loss 0.5 hard-label+0.5 soft-target KL |
| T12 | Pretraining/transfer | External compatible CSI or training-group self-supervision only; exact provenance/channel mapping; freeze encoder then training-only fine-tune; no target-test exposure |
| T13 | Causal personalization/domain adaptation | Separate future protocol, not pooled as subject-independent; only designated earlier calibration segments, no labels/full-test-record normalization |
| T14 | Auxiliary multiclass/pre-action/action/post objectives | Offline conditional study with explicit annotation policy; no automatic firmware class/schema change or post-fall training contamination |

T1/T2/T3 must reach loss gradients/centroids/impurity/priors according to each
family's declared objective. Algebraically identical variants are marked
NOT_APPLICABLE and not counted as independent improvements. For M9/M10 map
weights to effective per-example C; never equate their C with custom M2 lambda.
Use T0 scaling for initial weighting ablations; weighted scaling is a distinct,
not automatically enabled, experiment. T4 does not replace T1 silently.
T5 is a robustness hypothesis, not physically validated channel simulation.
For T5, closed-form/tree/kernel fits use one fixed augmented take copy; iterative
fits generate one copy per epoch with recorded seeds, never augment validation/test.
For T11, non-neural teachers require training-cross-fitted Platt probabilities,
converted to clipped log probabilities before temperature softmax; clip to
[1e-6,1-1e-6]. Neural teachers use logits. Save all teacher/student ownership.
No frame reversal (destroys causal order), temporal warp/cue jitter, cross-take
mixing or SMOTE by default. Add them only with new predeclared validity tests.
Focal loss, balanced neural batches and subtype weights can be added as bounded
neighbors only when class-count/gradient checks justify them, not a hidden optimizer.

T6 uses a class-preserving grouped validation split from the fit partition;
outer validation/test never selects epochs. If insufficient groups, T6 is blocked
and fixed epochs remain the reference. Save best epoch; final training length
uses median chosen inner epoch, not performance on the final test session.
For named M1/M2-T6 use their canonical700/500 maximum epochs, validation checks
and patience as above; do not apply the neural200-epoch cap to linear controls.
AE validation fits/checks NON_FALL only; supervised threshold selection may use
inner training FALL but is explicitly a supervised operating-point step.
Novelty detections are compared against both majority and supervised baselines.

T7: supervised positive margin = score_fall-score_non_fall; novelty models use
higher=more anomalous. Candidate thresholds are distinct inner-OOF scores plus
all-positive/all-negative endpoints, with a frozen empirical-quantile subset of
at most101 values if more exist. Replay each threshold; choose minimum negative
alarm-take rate subject to event recall >= max(0, paired inner M2 recall-0.05).
Break ties by event recall, latency, then higher threshold; margin/probability
threshold ties use FALL (>=threshold), and undefined matched latency sorts last.
Record attained recall and alarm rates. No feasible point = BLOCKED_OPERATING_POINT,
not a test-tuned threshold. Anomaly default threshold is training-negative P99; compare it with T7.
For M15–M18, fit ALL learned preprocessing/PCA/scaling/bins on eligible NON_FALL
training frames/windows only; FALL may enter T7/T8 inner operating-point selection,
not density/AE/prototype fitting. This ownership difference is part of the model
contract and saved artifact, not an unreported change to shared feature formulas.
Continuous-negative calibration can target <=1 FA/monitored hour (proposed research
target) only after such training/validation exposure exists; do not derive it from
short takes. T8 uses cross-fitted base scores and grouped calibration ownership;
never calibrate and evaluate on the same rows. Report 10 equal-width ECE bins and
uncalibrated controls; calibrated scores still require event replay.

#### 5.5.6 Leakage-resistant evaluation and selection ownership

Use the approved unified §5.4 E1/E2a–E2d assignments and five seeds for paired
diagnosis; all allocation/fitting is pending. §5.6.7 replaces the old E2c blocker.
Incomplete FALL in E2a/E2d supports any-alarm take diagnostics only, not onset
latency. No synthetic subject/session IDs. A test without FALL can report negative
metrics; supervised fit/selection requires actual window-class support. Missing
NON_FALL-labeled takes does not imply no pre-action NON_FALL windows. Never average
NA recall as zero; pooled and profile-specific denominators remain separate.

Nested procedure for each supported outer partition and seed:
1. Hold out its entire test takes/days/sessions/subjects before any fit, tuning,
   augmentation, feature selection or cache creation. Use original take lineage
   for all copies. For a continuous recording, assign the complete recording/session,
   not adjacent overlapping fragments. No raw-source support crosses a split.
2. Build three class-preserving inner grouped folds inside outer training only.
   Use the outer grouping unit where enough mixed groups exist; historical E1/E2
   uses take grouping inside training and is explicitly not session-independent.
   Insufficient groups/classes = BLOCKED_INNER_FOLDS; no random-window fallback.
   Check §5.6.5/A10 after reserving final-test groups: three development days or
   subjects do not support three same-axis inner folds after holding one out.
3. Fit scaler, PCA, masks, bins, quiet thresholds, prototypes, calibration, priors,
   class weights and models on each inner fit partition only. Causal unlabeled
   startup calibration may use arriving validation frames identically to deployment,
   never validation labels/future frames. Freeze fitted state before replay.
4. Select representation, model, hyperparameters, T variants, threshold and optional
   combination from inner OOF/replay results. Inner eligibility requires valid
   coverage and event recall >=max(0, paired inner F0-M2 recall-0.05); rank by
   negative alarm-take rate, event recall, macro-F1, median matched latency,
   estimated deployment footprint, then lexical config ID. Do not read outer E2
   outcomes for this ranking; save a failure if no candidate qualifies. For
   calibrated pipelines use grouped cross-fitting within inner fit data, never
   the inner held-out fold. Save all candidate results and the exact deterministic tie-break rule.
5. Refit selected learned components on all outer training, with training-group
   cross-fitted scores for final threshold/calibration; then evaluate once on the
   outer test. No changes after inspecting that test. Retain standalone default
   scores separately from the selected-pipeline procedure's OOF predictions.
6. Repeat across outer folds/seeds; aggregate original-window/event denominators,
   per-fold and pooled results, selection frequency and paired baseline differences.
   Never export a fold model as the final deployment artifact.

Important: globally selecting a Table4 shortlist, top models, or an operating
point using old outer scores makes subsequent old-data results exploratory even
if another nested run follows. The fixed six structural sentinels in §5.5.3 reduce
linear-selection bias; they do not undo prior knowledge of this dataset.
For an unbiased confirmation, freeze the entire development procedure before
opening independently reserved new sessions. Model-selection uncertainty belongs
inside CV; do not report the maximum historical OOF score as expected performance.

On new data, use class-preserving session/day outer folds first, subject holdout
where multiple subjects each have both classes, and environment holdout only when
several annotated environments exist. Inner folds preserve the same independence
unit. Class balance never overrides the held-out group boundary. For forward-in-time
adaptation tests, all calibration/training precedes evaluation chronologically;
no update from future outcomes. Missing metadata/supported folds is a reported
limitation, not evidence of generalization.

#### 5.5.7 Execution stages and controlled combinations

Every stage produces a manifest before fitting. Defaults below bound workload;
blocked/not-applicable cells remain visible. A selected global shortlist yields
exploratory comparisons only. The final nested selection pool must be fixed without
using its outer outcomes, and final confirmation uses untouched data.

| Stage | Predeclared run set / changing variable | Exit / status |
|---|---|---|
| T5-0 Prepare/pilot | §5.5.4 prerequisites; reproduce legacy F0-M2/seed20261026 separately, then gap-matched F0-M2 across five seeds | Audit/fixtures pass, exact workload approved; NOT_RUN |
| T5-1 Vector defaults | M0–M14 × [F0,F1,F3,F5,F11,F12.k5.delta], W24/raw/T0; each representation held fixed for model comparisons | 90 cells, proposed E1/E2a–E2d ×5 seeds; pooled/profile outcomes; approval/support pending, NOT_RUN |
| T5-2 Anomaly defaults | M15–M18 × same six reps; fit NON_FALL only, negative-P99 threshold; paired F0-M2 and T7 controls | 24 cells, same outer assignments; novelty vs fall identity and coverage separated; NOT_RUN |
| T5-3 Sequence defaults | M19–M24 ×S1/S2 at W2/R30/T0; HMM/DTW/neural contracts as specified; W2 F0 native/resampled controls | 12 cells plus controls; gaps, timing and full support audited; NOT_RUN |
| T5-4 Isolated training | M2/M5/M14 on F0: T1–T6 vs T0; only applicable strategies, same labels/split/scaler/window | <=18 new cells, same outer schemes/seeds; not-applicable T6 or weight cases listed; NOT_RUN |
| T5-5 Nested tuning | First inner-screen predeclared eligible M0–M14 ×six reps/T0; inner top3 family winners get <=9 configurations each, including default, bounded hyperparameter neighbors and applicable T1–T6 | All selection inside outer training; one selected-pipeline outer prediction; extensions to anomaly/sequence pool require a frozen manifest; NOT_RUN |
| T5-6 Operating point | Compare T7 and T8 against default decisions for inner-selected top3 pipelines; exact stabilizer/gate unchanged | Calibration/threshold OOF ownership and event trade-off curves logged; NOT_RUN |
| T5-7 Interactions | Predeclared combinations below; up to2 representations and2 causal A6 preprocessors chosen inside inner training, W24/W1/W2/W3 with matched controls | No outer-driven searches; blocked label/support grids retained; NOT_RUN |
| T5-8 Compression/teacher | <=2 neural/vector finalists: float32 vs T9; T10 only if PTQ fails accuracy guards; T11 student if teacher is too large; T12–T14 remain conditional | Separate algorithm/representation/quantization effects; no invented equivalence; NOT_RUN |
| T5-9 Deployment profile | <=2 finalists plus matched baseline: host-C fixtures/replay, fresh ESP-IDF build, measured resource/timing tests after preflight | Full artifact/numerical/state/resource checks; hardware/flash needs separate authorization; NOT_RUN |
| T5-10 New-data confirmation | Frozen baseline, nested selected procedure and <=2 finalists; B2–B7 plus §5.5.11 | Untouched final session; no tuning/automatic deployment; NOT_RUN |

Conditional unified E1 plus four E2 workload: T5-1=90×45=4050 outer fits;
T5-2=1080; T5-3=540; T5-4<=810, excluding controls/threshold fits/inner CV.
These are estimates, not approved schedules or results. T5-5 inner screen uses
90×3=270 fits per supported outer/seed, plus3×9×3=81 refinements and1 outer refit:
up to352×45=15840 only if every row has an approved/supported inner protocol.
Three day-exclusive inner folds are NOT supported; an approved take-inner diagnostic
has a narrower claim. Calibration/early-stop subfits/baselines/pools add further work.
Prepare must enumerate those extra fits and cap the actual schedule explicitly.
No full family×feature×training×window Cartesian campaign; no hidden random search.
Inner refinement order: default, one-axis hyperparameter neighbors in catalog order,
then applicable T1–T6 in ID order; retain at most9 unique configs/family, log omitted
neighbors. T5-4 still tests all applicable isolated T variants independently.
Resume only with matching data/source/environment/config hashes.

Controlled combination catalog (not all combinations are necessarily beneficial):
- C0 single-model baseline: preserve scores, votes and current Motion gate separately.
- C1 feature concatenation: F0 plus two nonduplicate appended blocks; select from
  F1/F3/F16 inside training, maxD48. Compare F0, each added block, and union with the
  same classifier. Correlations/redundancy are fitted/measured in training only.
- C2 score ensemble: mean of calibrated FALL probabilities of the two inner-best
  distinct compact families, weights0.5/0.5; compare each calibrated member. If
  calibration is blocked, do not average incomparable margins/novelty distances.
- C3 cascade: M15 novelty candidate →M2 or M14 verifier. Both run on all validation
  windows for audit; deployed verifier runs only at frozen candidate threshold.
  Threshold chosen from inner replay to preserve the recall guard. Measure candidate
  rate, gate misses, conditional latency and average/worst-case CPU; no oracle crops.
- C4 two-timescale detector: same compact family W1 plus W2, each available every0.5s;
  average cross-fitted calibrated probabilities at shared actual availability,
  stale/missing branch means unavailable, never fabricated zero. Compare each scale.
- C5 classifier plus temporal decoder: existing voter vs binary online HMM forward
  smoothing of calibrated raw classifier probabilities. Train transitions from
  adjacent strict-labeled windows in the same training take, add1 to each transition
  count, row-normalize; never count across unlabeled/support gaps. Initial prior
  [0.5,0.5]; emission likelihoods [p_fall,1-p_fall] clipped to [1e-6,1-1e-6], online
  posterior argmax in canonical class order. Reset only at real segment boundaries;
  no future Viterbi/backward pass. Report raw/voted/HMM and delays, calibrate inside
  folds. This is a decoder hypothesis, not Motion FSM equivalence.
- C6 teacher→small student: T11, comparing teacher/student/hard-label-only student
  with identical raw input availability; privileged future/annotation features
  cannot be inputs or targets at deployment. Report information/compression loss.

Use at most3 inner-selected eligible single pipelines for C2/C3/C5 pair formation,
with deterministic ranking and lexical tie-breaks; never ensemble all25 families.
C1/C4/C6 have their declared separate controls. Initially each combination changes
one component. Only an inner-selected combination may join one selected causal
preprocessor and representation; freeze the candidate schedule before outer test.
Post-fall confirmation is a future C7 research branch requiring independent posture
labels/features. Stillness by itself must never create FALL. Motion gate tuning or
adding Motion as an input changes the task and needs a separate telemetry contract.

#### 5.5.8 Window, event, coverage, and robustness evaluation

Replay all held-out frames/windows chronologically, including unlabeled pre/post.
The proposed reset policy uses acknowledged START epochs for independent takes/sessions
and declared peer/channel/invalid-segment boundaries, not labels or continuous file chunks.
Keep a separate current-production control per §5.7: extra gap/peer/channel
resets are not already implemented. Record raw score/class, default voter, optional decoder and
Motion-gated published result separately. Existing voter immediately adopts its
first raw class at startup/reset; subsequent entry needs2/3, release3 consecutive
NON_FALL. A missing/stale/wrong-peer Motion diagnostic suppresses output; it is not
a correct NON_FALL. Apply actual <=250ms freshness and unchanged gate thresholds
only with synchronized recorded telemetry; otherwise gated metrics=UNAVAILABLE.

| Metric | Exact interpretation |
|---|---|
| Window quality | Natural-prevalence confusion matrix, FALL/NON_FALL P/R/F1, macro-F1, balanced accuracy, MCC, PR-AUC (positive=FALL), ROC-AUC secondary; raw and stabilized separately |
| Window ownership | Strict held-out source-support labels only; report retained/attempted windows per class and take; undefined denominators/AUC classes=NA |
| Annotated event recall | Chronological new FALL onsets in [reviewed_start−0.3s,impact+1.0s); one-to-one nearest eligible unmatched event by absolute distance to start, then earliest start/event ID (§5.7.7); divide by all held-out annotated events; unavailable events remain misses; B9 timing uncertainty/bounds reported |
| Episode precision | Matched episodes /episodes in fully annotated monitored intervals; excluded/ambiguous post-fall episodes listed separately, not assigned invented negative truth |
| Unannotated fall takes | Any-alarm take recall for E2a only; no annotation-window accuracy, onset latency or timing-based event matching |
| Negative take alarms | Takes with>=1 alarm /all held-out non-fall takes; episode count/length and activity/day/channel/subject breakdown |
| Continuous false alarms | Unmatched episodes /monitored verified-negative hours; also rate per valid-output hour; never concatenate short takes to manufacture deployment exposure |
| Alarm latency | Actual alarm availability-start and availability-impact for matched events; median/P95/P99/range and counts; early alarms may be negative, misses are not deleted from recall |
| Processing latency | Arrival→features→scores→vote→gate→publish, with logical window end/bracket wait separated; cannot substitute host inference time for event onset latency |
| Coverage | Valid decisions/attempted, event-time valid coverage, output/calibration-unavailable time, gap/reset causes, class-specific loss; publish unconditional and coverage-conditioned recall |
| Stability | Startup alarms, pre-event active alarms, post-event persistence, episode duplicates, transitions per monitored minute, release delay |
| Calibration | Held-out Brier/log loss/ECE for actual probabilities; reliability plots and threshold precision/recall/FA-rate curves, prevalence stated |
| Robustness | Day/subject/subtype/channel/environment strata, quiet day-predictability probe for <=3 finalists, missing-frame/gap/noise perturbation sensitivity using training-defined stress levels |

Compute PR/ROC-AUC from continuous raw margin/novelty score or calibrated
probability, not voted hard labels; hard-label stages report confusion/event metrics
unless their own continuous decoder score is explicitly defined. Use average
precision for PR-AUC and the standard trapezoidal ROC-AUC, persist conventions.
Attempted decisions include scheduled source slots before validity/calibration/gate
filtering, not only emitted predictions. Event coverage is events with >=1 valid
available decision in the allowed interval /all held-out annotated events, per stage;
report valid-time fraction separately. Missing gated output fails gated coverage,
not raw coverage. Small-sample latency quantiles always show matched-event count.

An alarm active before the allowed event interval cannot become a true detection
by remaining active into it. Multiple onsets for one event produce one match;
extra episodes are duplicates and counted where negative truth is known. Excluded
post-fall training windows still enter replay and persistence/coverage reports.
Never improve recall/false alarms by hiding an invalid window/event. Compare paired
controls on shared valid support AND retain original-set all-event denominators.
Maintain full inference history; if the deployment gate cannot be replayed, say so.

Aggregate per-fold/per-seed and pooled original-event predictions; report median,
min/max across five seeds. Paired uncertainty: 1000 whole-take bootstrap resamples
within activity/day, seed20261118, 95% paired percentile differences; preserve all
windows/episodes of each sampled take. On new mixed sessions bootstrap sessions
(and subjects where supported), not windows. Report unit/count and wide intervals;
scarce sessions cannot establish population guarantees. Seed variation is not five
independent datasets. Multiple comparisons and outer-selected maxima remain
exploratory; McNemar is descriptive, not proof of clinical superiority.

#### 5.5.9 Python training → C inference parity

Pass these layers for each deployment finalist; keep golden fixtures/artifact hashes:
1. Raw decoder/layout/imaginary-real order, timestamps and supported frame decisions.
2. Per-frame transforms, reset/calibration state, trailing support/resampling and
   ordered vector/tensor values. Future-frame edits must not change earlier outputs.
3. Saved training scaler/PCA/bins/thresholds and every family score before argmax:
   linear coefficients, tree comparators/leaves, kernels/prototypes, GMM log scores,
   HMM forward steps, DTW distances, neural operators and recurrent gate/state order.
4. Class order/ties, selected threshold/calibration, voter startup/reset/release,
   optional decoder, synchronized Motion eligibility and published episode times.
5. End-to-end held-out full-record replay: same availability, invalid/reset reasons,
   coverage, decisions/episodes and event metrics; mismatches get frame/score traces.

Use float64 Python fixtures, an explicit float32 reference and actual C float32.
Float gate per feature/score: abs(C-Python)<=1e-5+1e-4*abs(Python). If individual
score error is bounded by e for each class, margin sign can differ within2e;
count all near-tie disagreements and event effects, never silently call them equal.
Outside the derived bound = FAILED_PARITY. Float numeric tolerance alone is not
sufficient if an alarm episode changes; report and resolve before recommendation.
For statistical/kernel extremes test overflow/logsumexp and safe finite guards.
For trees test values exactly at split thresholds. For sequences test startup,
all-zero/constant/impulse signals, long/gapped windows, recurrent saturation/reset.

For T9/T10, compare C integer tensors against the same Python quantized reference,
not float64 within the float gate. Freeze int8 signedness, accumulation width,
scale/zero point, requantization rounding/saturation/operator implementation.
Demand bit-identical intermediate/output integers for the selected backend reference;
otherwise BLOCKED_OPERATOR/FAILED_PARITY until an explicitly documented backend
contract is verified. Compare quantized vs float event/window metrics separately
with the same recall/coverage guards. Representative quantization data is training
only. GCC or exporter skips do not satisfy parity. C tests run on host AND device;
host C success is necessary, not proof of ESP32 timing or math-library behavior.
Export full-data development refits into the run directory; never overwrite the
active generated artifact as a side effect. Record exporter/framework/IDF/compiler
versions, numeric flags, checksums, D/shape/operator list and class mapping.

#### 5.5.10 On-device RAM, flash, CPU, and latency profiling

Before any runtime code/radio change, read `docs/agent-preflight.md`, open official
version-matched ESP-IDF v5.5.3 documentation and record Document + Quotation evidence.
Future code changes require `docs/agent-changes.md`; commits require applicable
Docs: trailers. No profiling firmware or flashing is authorized by this plan edit.

Profile baseline and finalists with identical compiler/sdkconfig/partition table,
CSI layout/stimulus/queue/radio settings and workload. First fresh-build baseline,
check actual application-partition headroom and linker map. Do not assume extra
flash partitions, PSRAM, lower Wi-Fi load, or an empty MCU from nominal chip RAM.
Use documented capability-heap/stack/timer APIs; freeze instrumentation and quantify
its overhead on a baseline build. Logs store device/artifact/build identities.

| Resource | Required profile |
|---|---|
| Flash/IRAM | App image vs configured partition, model const data/operators/tables/code, .text/.rodata/.data/.bss/IRAM deltas; report absolute and remaining bytes |
| RAM | Static history/input/features/model state; peak simultaneous live buffers; internal-capability heap minimum/largest block; classifier/all affected task stack high-water; neural arena/intermediate tensors; queues and fragmentation |
| CPU | Per-frame preprocessing, per-window extraction/inference/calibration/decoder/gate separately; cold and warm P50/P95/P99/max; total and incremental amortized cost/frame; no generic operation count presented as measurement |
| Latency | Decision processing P99, source-bracket wait, startup/time-to-first-output, end-to-end publish and annotated alarm delay; record device→host clock alignment uncertainty |
| Acquisition impact | RX/valid/enqueue/drop/reset/publish counters, queue high-water, CSI rate/gaps, watchdog/reboot, Wi-Fi/web/telemetry coexistence; compute rates over equal wall-time runs |

Proposed profile protocol: three paired 10-minute baseline/candidate runs in
alternating order under the same approved stimulus, including quiet/normal-motion
and hard-negative loads; record actual durations/frame counts. Add cold boot,
calibration, longest supported window, full cascade firing and neural worst-case
inputs. Recorded-event replay is separate from live CSI: measure harness overhead,
use the same injection path and do not claim a replay-only result proves live
acquisition performance. Any serial/replay injection prerequisites remain tasks.

Proposed deployment gates, not measured results: additional peak live RAM<=4KiB
relative to a matched F0 same-window build; incremental extraction+inference+state
CPU<=2.9ms/frame amortized; decision processing P99<=50ms; event coverage>=95%;
no incremental queue loss, allocation failure, watchdog or reset. Count arena,
stacks and temporary peaks, not only weights. Also report absolute total CPU/RAM
and available heap/stack/flash headroom. All app images must fit the actual partition;
if neither finalist fits, keep baseline or revise budgets with new explicit approval.
The <=4KiB gate may exclude viable larger models under this project's conservative
budget; label REJECTED_RESOURCE for this budget, not universally impossible on ESP32.

#### 5.5.11 Final selection, confirmation, and completion

First reject unsupported labels/splits, leakage, nonfinite fits, missing parity,
unavailable inference inputs, and hidden coverage. Then apply the provisional
recall guards: annotated E1 event recall drop<=0.05 absolute and E2a loses at most
one fall take vs matched baseline, median seeds; show subtype losses. These are
comparison guards, not adequate safety performance claims. Require >=95% event
coverage for unconditional deployment candidacy, and every resource/parity gate.

Among eligible pipelines choose a Pareto shortlist of at most2 by negative alarm
rate, annotated event recall, latency and measured cost. Historical ranking:
non-worsening E2a AND E2b negative-take alarm rate, then event recall, macro-F1,
latency, RAM/CPU/flash, smaller model/pipeline. If evidence is inconclusive retain
baseline/simpler candidate; do not claim statistical equivalence. On continuous
new data prioritize monitored FA/hour and annotated event recall before window F1.
Threshold/representation/model/ensemble selection must use development inner folds,
not the final-test FA rate. A teacher/offline winner is not a firmware winner.

Confirmation data target (proposed minimum, not power analysis): at least6 new
mixed annotated sessions across>=3 days, >=3 subjects with both classes where safe,
each fall subtype represented by>=2 subjects, and>=1 hour of continuous verified
negative exposure across sessions. Follow the existing approved recording/safety
protocol; do not induce unsafe falls. This minimum supports a diagnostic campaign,
not clinical certification or a tight low-FA guarantee. Keep existing historical
sessions as development-only. Reserve latest new mixed session before modeling as
untouched final test; use the remaining new groups for nested development, verify
class-preserving outer/inner session/subject folds before launch. If grouping is
insufficient, collect more data or mark blocked, never dilute independence.
This minimum does not guarantee nested day/subject support (§5.6.5). A reserved
session supports a new-session claim only; reserve whole days/subjects/environments
when claiming independence on those axes, and exclude all their data from fitting.
Allocate continuous-negative sessions to development/calibration/final test by
whole session before threshold fitting; report separate exposure per partition.
Zero alarms in H final-test hours gives an approximate one-sided95% Poisson upper
rate -ln(0.05)/H (~3/H), with stated assumptions, not proof of zero risk.

Freeze candidate/threshold/feature/training/quantization settings and hashes before
final replay; run baseline+finalists once on reserved data and report all outcomes.
No final-test tuning; a failed confirmation returns to development and requires a
new untouched test. Choose final model from development evidence and fit all
allowed development data (not reserved final test), using cross-fitted calibration
and fixed epochs/hyperparameters. Export/test again; no automatic deployment.
Decision states distinguish PROVISIONAL_OFFLINE, CONFIRMED_RESEARCH,
DEPLOYMENT_ELIGIBLE and NOT_RECOMMENDED; none means certified safety alarm.

Planned runner interface (IMPLEMENTATION REQUIRED, example only, not runnable now):
`python3 -m fall_detection.model_experiments --stage <STAGE> --run-dir <RUN_DIR>`.
STAGE values: prepare, pilot, vectors, anomaly, sequences, training, nested,
operating, combinations, compression, parity, profile, confirm, report.
Confirm also needs frozen `--confirmation-manifest <MANIFEST>`. Run directory at execution:
`reports/model_experiments/<UTC_run_id>/`; resume requires exact hashes.

| Required artifacts | Contents |
|---|---|
| config/environment/source locks; dataset manifest | All policies/seeds/backend/compiler versions/input hashes/exclusions, proposed gates and exact scheduled workload |
| model/training/representation inventories | M0–M24, T0–T14, F/P/S/C IDs, hyperparameter neighbors, shape/D/operator/causality/state/score semantics, status and blocker |
| outer/inner/calibration folds and selection log | Original group lineage, train/validation/test class/event counts, fitted-state ownership, every evaluated choice and omitted/refused branch |
| fit logs and fold artifacts | Timing/convergence/epochs/weights/SV/node counts, training membership, learned transforms/threshold/calibration, artifact hash |
| window predictions and full replay traces | Source/support/availability clocks, raw/voted/decoded/gated scores and labels, invalid/reset/calibration reasons, annotation matching |
| event/take/exposure tables and paired metrics | All-event/coverage denominators, alarm episodes/misses/latency, subtype/day/subject breakdown, continuous monitored/valid hours, uncertainty |
| parity/profile manifests and traces | Golden fixtures, passed/failed/skipped checks, C/backend/IDF identity, absolute/incremental peak resources, counters and cold/warm measurements |
| results.csv, summary.md, decision.json | Every scheduled cell including blockers; standalone vs selected-procedure scores, exploratory vs untouched-test status, accepted/rejected reasons and next action |

Separate run_status (NOT_RUN/RUNNING/COMPLETE/FAILED_TEST/FAILED_PARITY/
BLOCKED_DEPENDENCY/BLOCKED_MAPPING/BLOCKED_OPERATOR/BLOCKED_INNER_FOLDS/
BLOCKED_NO_TRAIN_FALL/BLOCKED_OPERATING_POINT/BLOCKED_COVERAGE/NOT_APPLICABLE)
from feasibility (UNVERIFIED/CONDITIONAL/OFFLINE_ONLY/DEPLOYABLE/REJECTED_RESOURCE).
No missing measurement is written as0. A completed Python run can be OFFLINE_ONLY.

| Candidate group | Run status | Window/event metrics | RAM/CPU/parity | Selection |
|---|---|---|---|---|
| M0–M24 defaults, T variants, S inputs and C combinations | NOT_RUN | Pending | Pending | None |

A9 is complete when every scheduled individual/combination has a result or explicit
blocker, ownership/leakage and parity tests are documented, all event/window/resource
comparisons have paired controls and provenance, and final choice clearly separates
historical diagnosis, nested development, untouched confirmation and hardware
eligibility. Record conditional unexecuted future branches instead of inventing
results. Preserve T8/Table4/historical artifacts; append new evidence with hashes.

### 5.6 Table 6 — Dataset splitting, independence, and leakage (A10)

#### 5.6.1 Comparison and current implementation

Comparison and read-only232-take/count-feasibility audit complete (§5.6.7).
Split implementation, allocations, tests and experiments remain NOT_RUN. Splits and
training run on the host; ESP32 RAM does not determine which CV scheme is valid.
The limiting factors are independent groups, annotation coverage, class support
and ownership of learned state. An 80/20 ratio is not intrinsically better than
70/30 or grouped CV; choose the question and independent unit first.

Source: `docs/tabel_riset_dataset_dan_fitur_training.md` §6 and its research
summaries. These are literature descriptions, not reproduced paper experiments.

| Literature | Reported split / limitation | Recommendation |
|---|---|---|
| TCS-Fall | Group by volunteer ID; subject-independent evaluation stated | Use subject-exclusive tests when claiming new-user generalization |
| RT-Fall | Progressive personalization | Separate adaptation performance from unseen-user performance without adaptation |
| FallDeFi | Within-environment70/30 and transfer tests reported; summaries disagree on verifiable grouping | Preserve uncertainty; original-take grouping needs verification |
| Chu | 80/20 plus room/participant tests; main recording/subject exclusivity unclear | Do not infer independence from the ratio or extra tests alone |
| El-Sayed | Random70/30 and sample-level k-fold | Check original-recording lineage before interpreting sample counts |
| STC-NLSTMNet | Ten-fold after sliding segmentation | Potential overlapping-window risk, not demonstrated leakage without actual fold lineage |
| Construction-worker study | Pooled6:2:2; take/window unit uncertain | High overlap makes the independent split unit especially important |
| IntechOpen | Stratified80/20 at sample level | Class balance alone does not preserve groups |
| DapFall | Cross-environment testing reported; subject/group details uncertain | Do not equate environment transfer with subject-exclusive validation |
| WiFall/Anti-Fall/Damodaran/AmFall | Insufficient split details | Keep unknowns; do not invent a split or declare demonstrated leakage |

Verified current phase path in `fall_detection/train_phase_activity_model.py`:
- Default five-fold OOF by take; all windows of a take remain together.
- Deterministic, class-aware allocation using group window counts; not randomized
  StratifiedGroupKFold. There is no exposed split seed or frozen-manifest input.
- `take`, `session`, `subject` grouping supported; `day` and nested selection are
  not implemented. `_take_group` returns recording_id immediately for `take`.
  Missing IDs raise only for the requested session/subject axis; the collector
  catches/skips those errors. This is NOT a missing-ID exclusion for take grouping.
- Empty test folds and missing training classes are rejected. A test fold lacking
  FALL is not explicitly rejected, and `_metrics` currently returns0 for an
  undefined recall denominator. Planned negative-only diagnostics must report NA.
- Canonical scaling is fitted on training rows only. Current F0 is deterministic
  within each take; producing these windows before fold assignment is not itself
  leakage while lineage is kept intact and no learned test statistics are used.
- Random model fitting uses fixed seed20261026 where applicable; changing a model
  seed alone would not create repeated randomized split assignments.
- The older take-label trainer supports explicit held-out recording IDs, otherwise
  a full-data fit; it is not the current phase OOF or the proposed nested protocol.

Current strengths: take integrity and fold-local scaling. Current gaps: credible
independent session/day/user data, explicit manifests, nested selection, metadata
coverage reports and missing-test-class metric semantics. A2's annotation margins
and whole-unannotated-fall exclusion remain prerequisites, not current behavior.

#### 5.6.2 What constitutes leakage versus a limited claim

| Situation | Treatment |
|---|---|
| Shared CSI source packets/augmented copies from one take across train/test | Direct source-lineage leakage; forbid crossing and test disjointness |
| Scaler/PCA/mask/bin/feature or threshold fitted using held-out data | Learned-state leakage; fit only within the current training partition |
| Selecting a model/feature/operating point from outer-test scores | Selection bias; select in inner groups and confirm on untouched data |
| Same session/day/person/room represented on both sides | Not automatically invalid for known-condition testing, but does not establish independence on that axis |
| Group allocator uses labels for balancing | Legitimate stratification; cannot justify breaking group boundaries |
| Thousands of correlated windows from few takes | More windows, not more independent fall events; uncertainty resamples groups |

Do not assert that every random-split paper leaked or that its reported effect size
applies to our model. Distinguish demonstrated contamination, plausible risk and
an evaluation answering a narrower question than the intended deployment claim.

#### 5.6.3 Layered evaluation recommendations

| Scheme | Question / planned use | Unified-snapshot limitation |
|---|---|---|
| Take-grouped E1 | Base evaluation: held-out original takes under represented conditions | Unknown IDs eligible; shared person/day/session and unresolved copy lineage limit independence |
| Session-exclusive | Optional new-session diagnostic only with verified provenance | Raw session ID reused across11-07/11-19;85 unknown; no verified independent session partition |
| Day-exclusive | Secondary robustness: whole UTC days | E2c now retains training FALL; only two annotated-FALL days prevent three same-axis inner folds |
| Subject-exclusive | Optional verified-subset new-user diagnostic | Two recorded study subjects, uncertain provenance/unknown membership; subject2 has9 HTTP lemas takes only |
| Environment-exclusive | New room/link geometry/configuration | No verified multiple environments; AP identity cannot establish placement |
| Profile-held-out | Secondary stimulus/profile-shift diagnostic of the same candidate pipeline | TCP occurs only11-19; no causal separation of stimulus/day; exact profiles incomplete |
| Forward-time personalization | Adaptation using earlier designated calibration | Separate future protocol; no future labels/full-record normalization |

Retain old E2 results as historical, and version proposed unified E2a–E2d separately.
Under primary A2, all22 incomplete FALL takes contribute no fitting/PCA/calibration
frames. E2a may report20 incomplete fall takes separately as any-alarm diagnostics;
E2d similarly reports its2 incomplete falls separately from39 annotated events.
E2b has negative-only take labels, so FALL recall is NA. E2c supports annotated
fall-event diagnostics but has no NON_FALL-labeled test takes; negative-take alarms
are NA while valid pre-action negative windows remain separately assessable.

No scheme isolates a causal percentage of the old score attributable to day.
Cross-day performance and a quiet day probe reveal robustness/confounding concerns,
not a causal decomposition. Recount each frozen snapshot instead of pooling the
historical182/189/130-take inventories or silently shrinking denominators.

#### 5.6.4 Manifest, metadata, and ownership safeguards

Before any future fitting:
1. Freeze original recording IDs, parent lineage, SHA-256 metadata/frame hashes,
   annotation-policy identity, status/exclusion reason and eligibility per scheme.
   Keep every take and all derived windows/copies in one group. Detect duplicate
   recordings/renamed copies; resolve provenance or exclude as unresolved rather
   than treating copies as independent events.
2. Store raw/resolved subject/session/environment IDs, recording UTC day, channel,
   annotations, subtype, source/support times and clock anchor. For new B9 data also
   include raw/reviewed truth hashes, schema/reviewer/adjudication/QC versions, timing
   uncertainty, censored/UNKNOWN exposure and the complete B6 acquisition-profile hash.
   Historical absent fields stay UNKNOWN; exact identity/verified-truth claims remain
   blocked, not backfilled by assumption. Never guess missing identities. Use only
   verified existing metadata fallbacks, logging conflicts.
   Derive day from `started_at_utc` without calling it a recovered session ID.
   Flag recordings spanning dates; keep them whole and do not claim day exclusivity
   if their actual source support touches both training and held-out dates.
3. Freeze outer/inner/calibration/final-test assignments before model results.
   Record grouping axis, allocator/version, seed, fold count, class/window/event
   counts and independence limitations. Use the same original group assignments
   for paired candidates even when feature eligibility changes.
4. Fit scaler/PCA/masks/bins/quiet statistics/augmentation/weights/prototypes and
   every model only on its training partition. Perform feature/model/hyperparameter/
   epoch/threshold/calibration selection inside grouped inner folds (§5.5.6).
   Negative-only models retain their NON_FALL-only fitted-state contract.
5. Keep causal startup calibration distinct from fitting on an entire test session:
   arriving unlabeled calibration frames are allowed only under the declared
   deployment procedure, with warmup/coverage recorded and no backfilling.
6. Record the exact training membership for each learned cache/artifact. Cache keys
   include training-group, input, transform, source and environment hashes. Never
   export an OOF/fold model or include reserved final-test data in the final refit.

Default diagnostic E1 retains Table4/5's five take folds and declared seeds. New
split-seed support is a future implementation task; record split and model seeds
separately and keep paired assignments identical. Existing deterministic repetitions
must not be described as five independent partitions or independent datasets.

#### 5.6.5 Fold feasibility, blocked cases, and new data

Choose/freeze fold counts and grouping before inspecting scores. For proposed new
data use leave-one-session/day/subject/environment-out where supported; for a large
session pool, five grouped outer folds are permitted when every fit/selection fold
has the required classes and enough remaining groups. Keep the Table5 default of
three grouped inner folds; check calibration and early-stopping subfolds too.

Necessary, not sufficient, checks:
- Every supervised fit contains FALL and NON_FALL; missing train class = BLOCKED.
- Every inner selection/calibration fold has the support required by its objective.
- A negative-only outer test is useful, but cannot produce measured FALL recall,
  balanced accuracy or two-class AUC; undefined metrics stay NA.
- Table4 E1's existing both-test-classes requirement remains unchanged. Its E2
  negative-only diagnostics and Table5 supported outer schemes stay separate.
- K folds need at leastK independent eligible groups. Three days cannot support
  leave-one-day-out with three day-grouped inner folds: only two days remain.
  At leastfour development days are necessary for that structure, after reserved
  final-test days are removed; class/calibration support may demand more.
- Likewise three identified development subjects do not by themselves support
  leave-one-subject-out with three subject-grouped inner folds. Check actual group
  support instead of substituting take folds and retaining a subject-independent label.
- Do not silently reduce folds, drop a difficult group, invent labels/IDs or switch
  to random-window splits. An alternative inner-fold count/grouping requires a
  separately frozen protocol, justified before results, with its narrower claim.

Collect mixed annotated sessions/days and subjects using B2–B8 only after the B9
reviewed-truth/consent/clock pilot and B6 acquisition-identity gates pass.
Distribute fall subtypes/hard negatives across groups;
class weighting cannot repair a class absent from a day or unknown identity.
The §5.5.11 minimum6 sessions/3 days/3 subjects is a proposed collection starting
point, NOT sufficient proof that every nested day/subject protocol can execute.
For new-session confirmation, reserve the latest new complete mixed session before
selection. For new-day/user/environment confirmation, reserve the ENTIRE relevant
day/subject/environment and all its recordings; a reserved session alone does not
establish those stronger axes. Reserve continuous-negative exposure by whole session
and the same claimed axis; no final-test exposure for calibration/threshold fitting.

#### 5.6.6 Future tests, outputs, and completion

Implement shared split/metric support through A10 before A6/A8/A9 campaigns. Reuse
their planned prepare/manifests rather than create a parallel incompatible trainer.
These are future tasks; no runner/options or new tests are implemented here.

Required tests: parent/packet/group disjointness; copies stay with their take;
no raw source support crosses a partition; deterministic assignment replay;
separate split/model RNG; unknown-ID take eligibility and scoped identity-claim limits;
verified metadata fallbacks/conflicts; annotation donor/recipient ownership;
boundary-spanning records; missing training/test classes; too few groups; nested
calibration/early-stop support; scaler/PCA fit spies; augmentation provenance;
cache ownership; final-test isolation; full-refit membership; paired eligibility.

Required outputs in each execution report directory:
- `dataset_manifest.csv`: full original inventory, raw/resolved IDs, hashes,
  per-scheme eligibility and all exclusion reasons, not only surviving takes.
- `folds.json`: outer/inner/calibration/reserved groups, allocator/seeds/versions,
  label policy, class/window/event counts and hash-linked artifact/cache ownership.
- `split_audit.json`, `tests.json`: overlap/disjointness checks, supported/blocked
  folds, metadata loss by class/subtype/day, passed/failed/skipped tests.
- `results.csv`/decision report: raw/voted/gated window and event diagnostics per
  fold/seed, original/retained denominators, NA/blocked metrics, paired differences,
  group-level uncertainty and the exact generalization claim. No fabricated0.

A10 complete when manifests/tests enforce the intended grouping and learned-state
ownership, every scheduled split has reproducible results or explicit blockers,
and conclusions distinguish take diagnostics, new-group validation, personalization
and untouched confirmation. Host/C parity and device deployment gates remain
required under A8/A9; a better split is not a new hardware measurement.
No implementation, training, build, flash or commit is part of this plan update.

#### 5.6.7 Recalculated unified feasibility — 232 takes, no allocation

Read-only audit COMPLETE. The232 inventory is101 FALL/131 NON_FALL and183 HTTP/49 TCP.
Primary manual-first D1 plus the existing smoke exclusion gives209 candidate takes:
79 complete-annotation FALL and130 NON_FALL.22 incomplete FALL and1 smoke take remain
in inventory with separate eligibility reasons. No manifest, window extraction for
new D1, fold allocation, model fit or alignment experiment was performed here.

| Policy / purpose | FALL / NON_FALL takes | Status |
|---|---|---|
| Full unified inventory | 101 /131 | Inventory only; includes smoke and incomplete annotations |
| All non-smoke take-level diagnostics | 101 /130 | Count-level possible; timing truth unavailable for22 falls |
| Primary manual-first D1 candidate fitting pool | 79 /130 |209; final signal/clock/window eligibility not yet audited under new policy |
| Hypothetical all22 annotations recovered +smoke excluded | 101 /130 |231 upper bound, NOT approved/verified primary eligibility; automatic labels are not manual truth |

Proposed leave-one-day-out arithmetic on the209 pool (F/N are TAKE labels):

| Scheme / test UTC day | Test F/N | Train F/N from all other eligible days | Interpretation |
|---|---|---|---|
| E2a /2026-11-04 | 0 /65 | 79 /65 | Negative-take test;20 additional incomplete falls may be separate any-alarm diagnostics |
| E2c /2026-11-07 | 40 /0 | 39 /130 | Annotated-event test; old no-training-FALL blocker is obsolete |
| E2b /2026-11-14 | 0 /57 | 79 /73 | Negative-only test; no FALL recall |
| E2d /2026-11-19 | 39 /8 | 40 /122 | Joint day/TCP shift;2 additional incomplete falls separately reported |

Every row has both training TAKE classes; strict window-class/support checks remain
necessary. Conversely, fall takes can yield pre-action NON_FALL windows: absence
of negative takes in a partition is not proof that it lacks negative windows.
Smoke day11-11 has no primary eligible takes and is not an extra CV day.

| Grouping / protocol | Count-level assessment | What remains unresolved |
|---|---|---|
| Five-fold outer /three-fold inner by take | Plausible with209 candidates; not allocated or certified | Duplicate/parent lineage, actual phase-window coverage, allocator/test/calibration support and approval |
| Whole-day outer diagnostic | All four rows above retain annotated training falls | Fixed-pipeline or approved take-inner selection only; the latter is NOT day-independent nested selection |
| Three-fold same-day-axis inner selection | Unsupported for this snapshot | Only11-07/11-19 have annotated FALL; holding out either leaves one FALL day, so some inner fits lose FALL |
| Raw session grouping | Not a verified independence protocol | Reused raw ID spans89 takes/two days; do not repair by inventing sessions or exclude unknowns globally |
| Subject grouping | No justified population/three-inner-subject claim |137 subject1,9 subject2,85 unknown,1 smoke; actual membership verification and class/subtype support required |
| Stimulus-family holdout | HTTP test40F/122N versus TCP train39F/8N, or reverse, after other gates | Joint profile/day domain shift, not a transport effect or separate deployed model |

Leakage/confounding audit and mitigation:
- Keep each original take and all windows/augmentations together; hash/inspect shared
  packets, renamed copies, contiguous source fragments and verified parent lineage
  before claiming direct-source disjointness.232 unique IDs alone do not prove it.
- Unknown IDs do not justify invented people/sessions or automatic exclusion. E1 may
  share latent subject/session across partitions; disclose that limit. Optional
  exclusive claims require resolved membership or an explicitly denominated verified
  subset, not unknown takes silently assigned to the opposing training side.
- Primary HTTP mix is40F/122N; TCP is39F/8N. TCP exists ONLY on11-19. Day, stimulus and
  profile-related signal shifts cannot be causally disentangled by this snapshot.
  Pooled performance can hide profile imbalance; report pooled/per-family/per-known-
  profile/subtype/day/channel coverage and counts, including UNKNOWN strata.
- TCP negatives cover only empty_room2, still_sitting3 and walking3. Do not require
  every profile×activity cell in every five-fold test: even TCP empty_room has only2
  takes. Sparse/absent cells stay NA; no duplication or synthetic balancing of tests.
- Seven HTTP walking takes use channel11; all other225 use channel1. Channel/activity/
  day effects are confounded. Preserve them and report the stratum; exclusion or a
  sensitivity study requires a predeclared, approved decision, not favorable results.
- No complete normalized acquisition profiles exist yet (§2.6/B6). Preserve inactive
  HTTP fields on TCP takes as inactive/unverified metadata, not active TCP settings.
- Donor selection, confidence calibration, learned preprocessing and weak-label use
  follow current training ownership. Never fit annotation templates on held-out
  labels and then report detector success against their own generated boundaries.
- All232 takes are already inspected development data. Freezing them later does not
  create an untouched confirmation set. New approved crossed/mixed-day collection
  with both stimulus families and activities is needed to address confounding;
  profile randomization alone cannot recover unknown historical subject identities.

Recommendation pending §8.1: unified take-based E1 as the primary development
protocol, E2a–E2d as secondary diagnostics, pooled and per-profile reporting,
manual-first labels, and an optional A14 study. No transport-specific model or
mandatory identity exclusion. Approval is needed before allocating any takes.

### 5.7 Table 7 — Evaluation, metrics, and ESP-realistic streaming fidelity (A11/C7)

Status: comparison and detailed protocol complete; every new implementation, replay,
parity run, device profile and live acceptance experiment is NOT_RUN. This section
operationalizes §5.4.4/§5.5.8–11 and uses A10's manifests; it does not launch them.

#### 5.7.1 Literature, verified implementation, and limits of existing evidence

| Study group | Reported evaluation | Transferable lesson / limitation |
|---|---|---|
| WiFall, Anti-Fall, RT-Fall | Precision/false-alarm rate, detection ratio/FPR, sensitivity/specificity | Preserve each sample/event denominator; a reported FPR is not an episode/hour rate |
| FallDeFi, Damodaran | Segmented-event/activity accuracy or precision/recall/sensitivity/specificity/F1 | Event crops and transfer tests do not establish continuous alarm burden |
| Chu, El-Sayed, STC-NLSTMNet, construction-worker study | Extracted/sliding-window classification metrics | Window quality is diagnostic; overlapping windows are not independent physical falls |
| DapFall | Fall-classification TPR/FPR | Do not rank against this project's different labels, subjects and monitoring exposure |
| TCS-Fall | ROC-AUC and continuous-recording NEWR/CWR | Useful recording-level warning tests, but not this plan's timed event/episode metrics |
| IntechOpen | Offline classification plus live-event trials | Live outcomes help; standardized onset latency/exposure still needs explicit definitions |

Use `docs/tabel_riset_dataset_dan_fitur_training.md` Table7 and the research documents
as secondary synthesis; mark unavailable primary-paper details NR, not guessed facts.
TCS-Fall's [primary Methods](https://pmc.ncbi.nlm.nih.gov/articles/PMC11151769/) defines
NEWR = 1 − (TCS recordings with any erroneous NON_FALL-slice warning / all TCS recordings),
and CWR = TCS recordings with any correctly warned FALL slice / all TCS recordings.
Its slices cover 8 s and TCS recordings 150 s. Multiple warnings in a recording collapse
to one flagged record. The discussion's per-hour extrapolation is not a measured
alarm-episode/exposure rate; reported 100 ms computer parsing/prediction is not ESP32
or physical fall-onset latency. Retain original definitions only as optional diagnostics.

Verified canonical evaluation currently loads complete recordings, extracts W24/12
feature rows, retains strict labeled windows and predicts each row independently.
The SVM receives 16 features, not the whole recording. Each row uses only its 24 frames;
loading the file into memory is not by itself future leakage. The voter subsequently
processes retained rows and resets at omitted-window gaps. This is NOT full-stream
replay or Motion-gated event evaluation. `_metrics` currently substitutes 0 for some
undefined denominators; A10/A11 must implement the explicit NA contract below.

Historical source-model run: 3261 windows/189 takes, 101 FALL/3160 NON_FALL; raw accuracy
97.55% and FALL recall 54.46%, stabilized accuracy 97.12% and recall 51.49%. Its 61→17
transitions concern retained labeled rows only. The cue4-to-tail run uses different
labels/support and must not be pooled with it. Source artifact, current policy and
proposed A2/D1 remain three separate contracts. These are saved report results, not
new measurements. Existing host C fixtures and isolated gate/voter tests do not prove
full-state replay, device timing or the active flashed model.

Source evidence: `fall_detection/train_phase_activity_model.py` extraction/OOF/voter;
`main/activity_classifier.c`, `main/activity_prediction_stability.c`,
`main/activity_motion_gate.c`, `main/web_serial_monitor.c`; `docs/DATA_CONTRACT.md`;
`reports/activity_classifier_benchmark/20261108T073910Z/PHASE_AWARE_TRAINING.md`.
`reports/HARDWARE_SMOKE_TEST_REPORT.md` contains historical acquisition/FSM diagnostic
smokes, including incomplete/overflowing telemetry; it is not classifier replay or
model acceptance evidence. `tools/replay/` has no canonical runner at this inspection.

#### 5.7.2 Fidelity tiers and permitted claims

| Tier | Input/execution | Required proof | Claim boundary |
|---|---|---|---|
| R0 Prepare | Frozen data/build/label/split/clock inventory; no fitting | Capture, state and metadata audit; eligible/blocked records retained | Feasibility only |
| R1 Python causal replay | Every available CSI/Motion item in original order; frozen held-out model; virtual recorded time | No future access; complete histories; window/event/coverage traces | Algorithmic captured-stream behavior, not ESP timing |
| R2 Production-C host replay | Actual C decoder/features/scoring/voter/gate with explicit clock and finite-queue adapters | Python/float32/C parity; admission/service/reset traces | Firmware algorithm equivalence on declared inputs, not RF/FreeRTOS performance |
| R3-V Device virtual-clock replay | Same C on actual ESP with an explicitly instrumented clock/order seam | Device numeric/state fixtures and deterministic trace comparison | Device arithmetic/state proof; no real-time or live-acquisition claim |
| R3-P Device paced replay | Recorded filtered CSI enters the production enqueue boundary at 1× cadence; actual ESP monotonic time | Delivery/jitter/queue/state/Motion/resource traces | Closest repeatable recorded-input test of the physical classifier |
| R4 Live acceptance | Frozen firmware receives actual Wi-Fi CSI under normal concurrent workload | Untouched mixed events and continuous negative exposure; identity, timing and loss audit | End-to-end evidence for tested subjects/environment/workload only |

R3-P is the preferred device test for existing recordings; R4 is the closest test
of the deployed system. R1 screens scheduled candidates; R2/R3-V/R3-P/R4 verify
matched F0 plus at most 2 deployment finalists with implemented C backends. A missing
C exporter/operator is BLOCKED_OPERATOR, not a Python surrogate passing firmware
verification. Reuse fitted artifacts; these tiers are not new training strategies
or independent datasets. A recording replay cannot
recreate missing frames, RF propagation, driver filtering or the original scheduler.

#### 5.7.3 Capture boundary, eligibility, and causality

Define the classifier replay boundary as post-ESP-Radar filtered CSI immediately
before `activity_classifier_enqueue`, not RF reception, raw-feature FSM input or
precomputed vectors. Preserve valid I/Q payloads, INT8 signedness and imaginary-real
order; radio flags, peer MAC, signal mode, bandwidth, secondary channel, first-word
flag and valid/LLTF/HT/STBC lengths must reproduce the actual enqueue verdict.
Retain sequence IDs, device callback/driver timestamps and host receive timestamps
as separate provenance. The first-word flag requires a correctly reconstructed
`info->info`; a NULL pointer would silently change its meaning. Do not coerce a
52-pair record into the active 51-pair model or fabricate absent flag/length metadata.

Classifier enqueue precedes CSI serial throttling in `web_serial_monitor_csi_callback`.
Thus `frames.csv` may omit inputs seen by the original classifier. Audit throttle,
direct-write failure, fallback-only records, recorder gaps and diagnostic overflow.
Period 0 is an all-callback capture request, not proof of lossless capture. Fresh
recording changes require preflight and overhead measurement; existing records are
not retroactively repaired. Metadata-only fallbacks identify loss, not recoverable CSI.
Do not equate 802.11 RX sequence gaps with callback, recording or classifier drops;
only counters with verified scope/order can establish the corresponding loss denominator.

Retain every inventoried held-out event with valid truth/group ownership in the
unconditional event denominator, even if its stream has no usable input. New recordings
require B9 reviewed event/interval/action records; physical-truth QC is independent of
sensor/capture QC. List UNKNOWN event truth, missing event timing and censored outcomes
explicitly beside the all-event inventory; never use detector silence as verification.
Missing annotations permit only any-alarm take diagnostics. An unreadable/partial capture
gets explicit coverage/eligibility status, never silently disappears from the report.
Transport-invalid records never reach unsafe pointer/length operations; semantic
unsupported-layout frames with intact payload/metadata enter the normal rejection
path. Keep missing-payload slots as loss records, not zeros/interpolated observations.

All inference uses trailing support available at the decision time. Replay pre/post,
unlabeled and quiet regions through every causal state; annotations control scoring
only. Freeze training scalers/PCA/calibration/thresholds; no test-record refitting,
future quiet-period selection, event-cropped windows or backward sequence pass.
Future-frame mutation must leave all earlier feature/score/state outputs unchanged.
Preserve original order; reject/account for reversed timestamps rather than sort them.
Independent historical takes start fresh. Genuinely continuous sessions retain histories
across activities, annotations and file chunks; reset only at acknowledged START or the
explicit source/invalidity boundaries of the declared replay policy. Session end censors
outcomes; it does not retrospectively reset an unresolved incident.

#### 5.7.4 Production state versus proposed state changes

| State | Current source behavior to reproduce | Proposed experiment policy / required trace |
|---|---|---|
| Frame queue | Depth4, zero-wait send; failure counts drop and marks next accepted frame for reset | Keep capacity/failure semantics; log enqueue/dequeue IDs, occupancy and reset marker |
| Window | Latest24 processed frames, stride12; first decision after24 | W1/W2/W3 require separately versioned timestamp/window implementation; no frame-to-second conversion assumed |
| Feature/model |51 LLTF amplitudes→16 F0 deltas/log1p; saved scaler/OVR margins; canonical class order/ties | Freeze schema/artifact; candidate preprocessing, PCA/sequence/calibration state separately named |
| Voter | First raw class adopted immediately, including FALL; later enter2/3, release3 consecutive NON_FALL | Record initialized/history/index/stable class/release streak; test startup/reset alarms |
| Classifier reset | Queue-loss marker or invalid frame clears processed history and voter | Extra peer/channel/time-gap resets are proposed, not present current behavior |
| Motion cache |16 peer slots; matching peer and age0…250000µs at actual classification time | Reproduce update/eviction order, sample timestamp/value and selected peer; do not substitute CSI peaks |
| Motion gate | Below3850000 vetoes FALL; above5000000 confidence marker only; missing/stale suppresses publication | Exact boundary tests; unavailable output is not NON_FALL or calibrated confidence |
| FSM/radio | Independently running sensing state, baseline, AP/channel lifecycle and stimulus | Log baseline/peer/radio status; classifier reset is not FSM baseline reset |

Freeze `PROD_LEGACY` as the current-source state/reset control. `PLAN_GAP05` uses
D9's proposed gap>0.5s plus verified peer/channel/invalid-segment resets, applied
identically to baseline/candidates. Reset candidate preprocessing, rolling/PCA,
calibration, recurrent/decoder and voter state at declared segment boundaries;
clear the replay Motion cache on independent replay start. Neither mode resets at
labels. A peer/channel/gap policy change gets its own configuration and firmware
implementation/parity requirement; it must not be attributed to a better model.

Cold-start replay uses a verified empty classifier state and Motion cache. Warm
replay supplies a continuous preceding prefix and processes it causally, without
scoring the prefix or warming from future/test-fitted data. F9's quiet calibration
uses its existing 2 s/>=30-frame contract and reports unavailable warmup. Recurrent
reference models remain reset-per-trailing-window as specified in Table5; carrying
state across windows is a separate model protocol, not a fidelity improvement.

Public sensing start/stop/reset-baseline does not establish checkpoint restore.
Do not claim to restore production FSM/pending rings from write-only checkpoints.
Classifier gate replay uses audited recorded Motion; rebuilding Motion from CSI
requires a separately supported upstream/FSM injection and restore design. Cold
boot with documented baseline establishment can test live FSM state, not restore it.

#### 5.7.5 Build, hardware and workload identity

Before R3/R4, require separate implementation/build/flash/test authorization and
`docs/agent-preflight.md` evidence; log future code changes in `docs/agent-changes.md`.
Use ESP-IDF v5.5.3, not the registered v6.0 documentation service. Archive board/chip
revision, source commit plus dirty-source hashes, compiler/toolchain and numeric flags,
component locks, sdkconfig, partition table, ELF/bin and generated model/transform
hashes. Boot telemetry must identify the executing app/partition and model; verify
against the authorized flash record/readback where available. Source hashes alone
are not proof of active firmware. Preserve recovery artifacts before authorized flash.

Keep actual CPU frequency/power-management settings, core affinity, classifier task
priority 3/4096-byte stack, queue depths, Wi-Fi/BT state, channel/AP/stimulus, sensing
FSM, web/serial and active HTTP/TCP stimulus workload with B6 profile provenance,
and watchdog configuration in the manifest. Do not
assume nominal RAM, PSRAM or additional partitions, or silently pin tasks, raise
priority, enlarge queues, disable watchdogs/radio/stimulus, or quiet the application.
Measure cold/warm states and realistic concurrency; a quiet-MCU microbenchmark is
secondary. Every changed build/load setting gets a separate paired experiment.

A replay source selector excludes live CSI and live Motion from classifier state
while existing approved radio/FSM activity can remain concurrent load. Count rejected
cross-feed attempts; zero admitted cross-feed is mandatory. Do not stop the radio
as an undocumented shortcut. R4 uses live inputs with the replay adapter inactive.
Harness buffers/stacks/logging remain bounded and are measured in both matched
baseline/candidate builds; include absolute total costs as well as incremental model
cost. Matched harness overhead cannot be described as zero deployment overhead.

Official v5.5.3 sources: [ESP Timer](https://docs.espressif.com/projects/esp-idf/en/v5.5.3/esp32/api-reference/system/esp_timer.html)
explains that higher-priority tasks delay callback dispatch and `esp_timer_get_time`
reports time since timer initialization. [IDF FreeRTOS](https://docs.espressif.com/projects/esp-idf/en/v5.5.3/esp32/api-reference/system/freertos_idf.html)
specifies task stack sizes in bytes and zero-wait queue sends. Timer resolution is
not a measured replay-delivery guarantee. Future implementation must quote relevant
local/version-matched APIs before changing runtime behavior.

#### 5.7.6 Streaming adapter, clocks, and timing acceptance

Implement a bounded versioned binary adapter, not whole-record storage on the ESP.
Proposed v1 envelope: little-endian fixed-width integers, record type, run/generation/
source sequence IDs, relative due time in signed 64-bit microseconds, payload length,
intact classifier layout/peer fields and payload; CRC32/IEEE covers header and payload.
Record types CSI, MOTION, LOSS and START/END; no native C-struct memory serialization.
Maximum 512 bytes/envelope, ingress 8 records (4 KiB slot storage, plus explicitly
measured metadata/parser/task costs). MOTION preserves uint32 `smooth_scaled` and
sample timestamp; payload fields/version/CRC have decoder fixtures and a schema lock.
Payload includes the complete filtered segment needed to validate layout; original
raw bytes remain archived on the host. Oversize/corrupt records are rejected and
counted, not truncated. This is a proposed protocol, not an installed command/API.
START is accepted only at a new epoch after prior input is quiescent and classifier/
voter/cache state is reset and acknowledged; begin the timeline after prefetch READY.
END stops new inputs at recorded end, then permits a proposed bounded 5 s queue drain.
Log actual drain/timeout and late post-end decisions separately; do not reset queued
work away, extend monitored exposure or backdate late alarms. No generation may mix
with the next run. Time-window variants additionally require a versioned queued
arrival timestamp; the current packet-count queue does not already provide one.

The PC streams chunks; an on-device scheduler releases prefetched items at due times
without waiting for previous classification. Receiver/scheduler work stays outside
classifier/timer callbacks; use documented timing/task APIs and bounded critical
sections. Preserve the production depth4/zero-wait classifier queue. Adapter full:
drop incoming envelope and report its ID; never overwrite queued records. Prefetch
may be flow-controlled before due time, but must not stretch the 1× input timeline.
Late items are attempted immediately, with original due time and actual lateness
logged; ingress underrun/overflow remains fidelity failure, not erased by blocking.
Freeze the tested serial port/baud, receiver/scheduler priority and message framing;
measure sustainable wire throughput including telemetry and acknowledgments in the
pilot. Nominal baud alone is not proof that ingress8 can sustain bursty1× traffic.

Use device callback monotonic deltas for cadence when complete and consistent;
otherwise use host receive monotonic deltas and label HOST_TIMING_PROXY. Map labels
and Motion onto that axis through audited clock pairs/anchors. Driver-local 32-bit
clock wrap and reboot epochs are explicit; never subtract UTC directly from device
monotonic time. Audit Motion timeline status/smoothed values/peer/time provenance
in `.meta.json`; absence of an alignable timeline blocks gated replay, not raw replay.
For example, `events.motion_samples` stores `ts_ms`, `peer`, `smooth_scaled` and FSM
levels. Preserve the scaled integer; FSM enter/exit levels are not classifier-gate
thresholds. Resolve an AP alias only through verified per-segment AP MAC metadata.
Millisecond timestamps have quantization uncertainty; graph samples do not prove
that every original cache update was captured. Audit sample-time versus cache-update
provenance and missing updates. Exact historical gating is blocked when timestamp/
ordering uncertainty can change a freshness verdict; retain explicitly approximate
recorded-Motion diagnostics separately. Clock alignment cannot restore lost updates.
Equal timestamps require a recorded source order; unknown cross-stream ordering
is BLOCKED_CLOCK_ALIGNMENT for exact gating near freshness boundaries.

R3-P uses `t_due = device_start + recorded_relative_time` at 1× and actual device
monotonic time for enqueue, dequeue, gate and publication. Map each recorded Motion
sample timestamp onto the same device epoch, with its cache update attempted at the
recorded update time where available. Never replace an old sample timestamp with its
late transport arrival time to make it fresh. Record intended/actual update times,
the exact sample timestamp/value used by the gate and all provenance uncertainty;
no unrelated live value or future sample enters replay state.
R1/R2/R3-V use a declared virtual clock for all modeled timing/state operations.
Default functional mode is FUNCTIONAL_NO_DELAY: immediate service, explicitly ideal
algorithmic source-time latency, not measured processing. H8 uses a frozen synthetic
admission/service-order fixture to exercise finite-queue overflow, not a CPU estimate.
OBSERVED_SCHEDULE mode later consumes R3's actual admission/service/Motion traces;
other delay/load simulations require a named trace and cannot masquerade as measurements.
No virtual-time run supports wall-clock throughput, real queue contention or RF claims.

Proposed R3-P fidelity targets: P99 absolute CSI/Motion delivery error<=5ms,
maximum<=20ms, and clock-alignment uncertainty<=5ms; these are unmeasured protocol
choices, not device specifications. Report early/late distributions, interarrival
errors, backlog and gate-boundary effects. Any transport/ingress/diagnostic loss or
target violation marks timing fidelity FAILED_TIMING/INCOMPLETE_CAPTURE; retain
observed outputs as stress evidence, not exact-original-timing proof. Classifier
queue loss remains measured production behavior and subject to the matched cost gate.

Compare device C against a reference replay conditioned on actual admission/service,
reset and selected-Motion traces; compare nominal versus delivered timing separately.
This isolates arithmetic/state bugs from timing/load effects. Scheduling uncertainty
cannot be hidden by backdating an available alarm. Capture arrival, logical/support
window end, bracket availability, dequeue, features, scores, vote, gate, publish and
host receipt separately; event latency is availability time, not nominal window end.

#### 5.7.7 Metrics, episodes, abstention and uncertainty

Use §5.5.8's definitions at raw, stabilized/decoded and gated-published stages separately.
Episodes here are derived prediction episodes, not verified notifications from an
unspecified downstream UI/buzzer. Initial valid FALL starts a startup episode;
a subsequent new onset requires an observed NON_FALL release. Missing output is
neither release nor NON_FALL: keep the prediction-episode latch and mark its unavailable duration.
An internal history reset alone cannot turn an already-active pre-event prediction episode into
a new matched detection. Incident and notification lifecycles are the separate §5.8 extension. Session end censors an active episode; report its duration,
resets and censoring, rather than inventing a release or joining independent takes.

| Metric | Frozen computation and denominator |
|---|---|
| Annotated recall | Chronological new onsets in [reviewed_start−0.3s,impact+1.0s); match one-to-one to nearest eligible unmatched event by absolute distance to start, then earliest start/event ID; divide by all held-out annotated events |
| Misses/duplicates | Unavailable events remain misses; each event matches once; extra episodes are duplicates, not additional detected falls; report subtype losses |
| Episode precision | Matched episodes /episodes whose onsets have fully annotated truth; unmatched episodes in defined FALL/NON_FALL truth count in the denominator; ambiguous/post-fall onsets separately listed |
| Continuous FA/hour | Unmatched episode onsets inside verified continuous NON_FALL monitoring /that monitoring's hours; also per valid-output hour; report session count, activities, gaps and exposure |
| Take diagnostics | Unannotated FALL takes with any alarm /all such held-out takes; NON_FALL takes with any alarm /all held-out negative takes; no timing or clinical event claim |
| Alarm latency | Available matched alarm−reviewed start and−impact; matched count, median/P95/P99/min/max and clock/observer uncertainty; negative early values retained; misses remain in recall |
| Window diagnostics | Strict-source-support confusion matrix, FALL P/R/F1, specificity, macro-F1, balanced accuracy, MCC, average precision and secondary trapezoidal ROC-AUC; natural test prevalence |
| Probability quality | Brier/log loss,10 equal-width-bin ECE and reliability plots only for held-out calibrated probabilities; no confidence interpretation of hinge margins/Motion flags |
| Stability/cost | Startup alarms, pre-event active alarms, persistence/release delay, duplicates, transitions/minute; processing stages and absolute/incremental RAM/flash/CPU |

Do not concatenate independent short takes to claim continuous deployment FA/hour.
Unknown post-fall truth stays outside negative exposure; known negative subperiods
may have separately labeled diagnostic rates. Capture loss does not imply the
physical activity ceased: retain total verified-negative monitoring exposure and
report unavailable time, plus valid-output exposure. If observation/annotation itself
is incomplete, report UNKNOWN exposure separately. A silent/dead detector with 0
alarms must fail recall/coverage, not win the comparison. Undefined denominators,
single-class AUC, missing truth or missing timing yield NA/UNAVAILABLE, never invented 0.

Shared metric implementation contract (FALL positive; apply independently per stage):
- P=TP/(TP+FP), recall=TP/(TP+FN), specificity=TN/(TN+FP),
  F1=2TP/(2TP+FP+FN), balanced accuracy=(recall+specificity)/2, and
  MCC=(TP*TN−FP*FN)/sqrt((TP+FP)(TP+FN)(TN+FP)(TN+FN)). Zero denominators
  are NA. Macro-F1 requires defined scores for all declared classes; do not quietly
  average only the supported class. Preserve TP/FP/TN/FN and truth/validity counts.
- Strict-window quality is conditional on valid labeled support; report unavailable
  windows separately with fixed nominal coverage/all-event denominators. Abstentions
  are neither TN nor accepted FALL; confirmation metrics add an explicit abstention
  column and unconditional positive recall, as specified in §5.8.13.
- Historical "alarms" and E2a any-alarm take recall mean prediction episodes, not
  confirmed incidents/notifications. Take recall has no onset timing; continuous
  FA/hour needs complete reviewed B9 negative exposure, never independent concatenated takes.
- Use B9's versioned event/interval/action truth and clock uncertainty for new sessions;
  nominal fixed-D1 matching, uncertain-boundary flags and definite/possible match bounds
  share one implementation. No label-margin branch, confirmation delay or missing data
  can widen the event-matching interval or shrink its original event denominator.
- Small-sample quantiles use sorted linear interpolation at(n−1)*q (same convention
  as §5.4.2); show endpoint counts, censoring and min/max. Missing endpoint times are
  NA, not zero latency. No later receipt/ACK time is imputed as the original intent.

Calculate AP/ROC-AUC per eligible held-out fold and report defined-fold counts and
macro means. Concatenated raw margins from different fitted folds need not share a
scale: pooled score AUC is diagnostic only, unless a common cross-fitted probability
contract is established inside training. Do not fit a pooled calibration on OOF test
labels. Confusion/event counts may pool original held-out predictions within a seed.

Persist nominal pre-validity source slots, actual engine attempts, valid raw/voter
outputs and gated publications separately. W24 nominal slots derive from known
source ordinals24,36,48… before filtering; actual reset-induced schedules are logged
separately. Time windows use their frozen anchored grid. If lost-source counts are
unknown, nominal capture coverage is NA; emit observed counts without a lossless claim.
Report engine-stage validity per actual attempt separately from nominal opportunity
coverage. For W24 opportunity coverage, credit at most one valid decision whose source
end ordinal lies in [nominal_end, nominal_end+12), per known nominal slot; log reset-
shifted/nonaligned support rather than claiming identical windows. Time-window slots
retain their logical-end identity. Late availability is separate from input-support
coverage. Retained labeled windows and event denominators never shrink with validity.
Event coverage = events with at least 1 valid available decision in the allowed
interval /all annotated events, per stage; coverage-conditioned recall is secondary.

For valid-time coverage, use proposed evaluation-only freshness horizon 0.5 s, not an invented
firmware release rule. Each valid publication/decision covers until the next attempt,
reset/unavailable indication, session end or availability+0.5s, whichever comes first;
a next valid decision begins the next interval. Warmup, missing Motion and expired
output remain unavailable. Archive this horizon and interdecision distributions;
current firmware's persistent stored class is reported separately. Never use old
held labels to manufacture coverage through long acquisition gaps.

Thresholds/operating points and calibration fit inside A10's grouped inner training.
Report per-fold/seed and per-stratum counts before pooled metrics; do not multiply
event/exposure counts by five seeds. Use §5.5.8's 1000 paired whole-take bootstrap
resamples/seed20261118 for historical diagnostics, session/subject clustering where
supported for new data, 95% intervals and actual independent-group counts. Latency
quantiles include the matched count; matched-only latency cannot hide recall loss.
Zero alarms over H hours has the stated-assumption approximate 95% upper Poisson rate
−ln(0.05)/H, not zero risk. Six sessions/three days/three subjects and 1 h are starting
targets, not power or low-FA guarantees; obey §5.6.5's nested-group feasibility checks.

#### 5.7.8 Required functional and hardware scenario matrix

Run deterministic fixtures in R1/R2/R3-V; run paced traces at R3-P with the same
artifact/policy and actual timestamps. All scenarios below are proposed, NOT_RUN.
Stress-modified traces are derivatives owned by their original split, never new takes.

| ID | Scenario | Required observation / assertion |
|---|---|---|
| H0 | Cold boot, empty state,23/24/36 frames | No premature window; first raw FALL adopted; startup alarm and time-to-first-output recorded |
| H1 | Warm prefix, constant/zero, impulse, near ties and tree split boundaries | C features/scores/state parity; finite guards; no oracle warmup |
| H2 | Complete pre/action/post/unlabeled stream; edit only future frames | Earlier outputs unchanged; no annotation-controlled reset; persistence/duplicate accounting |
| H3 | Invalid flags/lengths,52-pair model mismatch, INT16, HT/STBC/layout/secondary-channel changes | Exact production accept/reject/reset verdict; no unsafe reads, padding or coercion |
| H4 | Missing payload, corrupted CRC, duplicate/out-of-order transport ID, truncated end | Explicit loss/rejection/censoring; exclude unsafe transport data; do not deduplicate legitimate repeated CSI |
| H5 | Gaps0.49/0.50/0.51s; peer/channel change; reconnect/reboot | PROD_LEGACY vs PLAN_GAP05 differences explicit; actual epoch/cache/history lifecycle recorded |
| H6 | Matching/stale/wrong-peer/absent Motion; age249999/250000/250001µs | Exact inclusive freshness in virtual fixtures; real-device actual-time effects logged; unavailable never NON_FALL |
| H7 | Motion3850000/5000000 thresholds and±1 scaled unit;16-peer cache eviction | Veto/confidence boundaries and lookup order; confidence cannot create FALL |
| H8 | Queue fills, overflow then next accepted frame; ingress starvation/overflow | Capacity4/zero-wait semantics, reset marker, separate loss counters and admission/service ordering |
| H9 | Original irregular cadence1×; speed factors0.5×/2× and four-frame zero-spacing bursts |1× is fidelity test; altered timing is labeled stress, not equivalent real-time data |
| H10 | Approved B6 HTTP/TCP stimulus profile plus web/telemetry traffic, cold/warm cache and worst-case supported candidate | Concurrent resource/latency/queue profiles per workload; no silent workload removal |
| H11 | Continuous hard negatives, deliberate lying down, sitting-to-floor, recovery/stillness | False episodes/exposure and persistence; stillness alone must not manufacture FALL |
| H12 | Source selector switches, same-peer live/replayed Motion coexistence, session restart | No cross-feed; switch only at a documented new run/epoch, cache/reset acknowledgment required |

Numeric noise/drop-rate sweeps beyond this matrix need a frozen training-only stress
manifest. Do not select favorable stress levels after outer/final results. R4 physical
activities follow the approved safe recording protocol; do not induce unsafe falls,
change radio/security behavior or conduct unsolicited flash/network operations.

#### 5.7.9 Execution order, telemetry, outputs and completion gates

A11 offline preparation: audit source/capture/clock/Motion state and A10 ownership;
implement common replay/episode/coverage metrics and tests; reproduce saved legacy
window results separately. R0/R1 readiness precedes A6/A8/A9 campaigns; consume their
frozen artifacts for recorded replay. R2 parity is for matched F0 and at most2 C-supported
finalists after screening, not a circular prerequisite to create every candidate.
Reuse A6/A8/A9 outputs, not a competing trainer. A skipped GCC/parity check does not pass.

C7 device preparation after separate authorization: minimal selector/clock/adapter
and bounded telemetry, version-matched preflight, fresh matched builds, partition/
heap/stack check, recovery/identity proof, then synthetic R3-V fixtures and R3-P pilot.
Pilot capacity/timing is established on development data before reserved test access.
Baseline and each finalist use identical instrumentation/load and three repeated 1×
recorded-stream runs; alternate baseline/candidate order. Candidate effects are paired
on identical recordings, but repeated replay is not additional independent evidence.
R3-P timing/trace failure returns to harness investigation, not threshold tuning.

Profile the three paired 10-minute load runs and cold/worst-case cases in §5.5.10.
Proposed gates remain additional peak live RAM<=4KiB, incremental complete-pipeline
CPU<=2.9ms/frame amortized, decision processing P99<=50ms, event coverage>=95%, no
incremental classifier queue loss/allocation failure/watchdog/reboot, and actual app
partition fit. These are research budgets, not measured results; 50 ms processing is
not a 50 ms physical-onset alarm requirement. Record instrumentation-disabled baseline
cost controls; do not test two full models simultaneously for primary cost claims.

R4 final acceptance: freeze baseline/finalists, labels/thresholds/decoder and hardware
settings before untouched whole-axis groups; mixed annotated falls and representative
continuous-negative monitoring are independently reserved per §5.5.11/§5.6.5.
B6 complete acquisition identity and B9 reviewed/hashed truth, clock uncertainty,
independent adjudication and full exposure QC must pass before LIVE_CONFIRMED claims.
Sensor-invalid time remains in physically verified exposure; UNKNOWN truth and censored
endpoints are explicit. Missing truth/prompt/clock evidence blocks the affected claim.
Use predeclared alternating/randomized live blocks for matched conditions, with one
active production pipeline at a time. Replay gives paired identical-input comparisons;
live blocks are different physical events and must not be falsely called paired takes.
Report all planned conditions once without test-driven tuning; a revision needs new
untouched confirmation. Unknown observer reaction delay remains measurement uncertainty.

Each decision trace requires run/build/model IDs; source/generation/peer IDs; actual
input/admission/service clocks; support bounds; full-precision features/all scores;
raw/voted/decoded/gated labels; reset/drop reasons; Motion timestamp/value/age/eligibility;
processing/publish/host receipt clocks; unavailable state and stage episode IDs.
Use binary float32 or >=9 significant decimal digits for parity traces, not current
three-decimal activity JSON. Existing `class` is gated and `model_class` stabilized;
its score is not a probability or necessarily the gated class's winning margin.
Count capture/throttle/write losses, transport errors, adapter losses, classifier
drops and diagnostic export overflow separately; overflow invalidates trace completeness.

| Planned artifact in existing run directories | Required contents |
|---|---|
| `evaluation_protocol.json`, `capture_audit.json` | R tier, boundary, reset/clock modes, timing/coverage horizon, eligible events, source completeness and blockers |
| `build_manifest.json`, `replay_manifest.json` | Board/build/active artifact/flash identity, source/data/fold hashes, resource settings, envelope/capacity/order and stress lineage |
| `state_trace.jsonl`, `decisions.csv`, `episodes.csv` | Complete causal state and actual timing; source/admission/reset/Motion traces; all matched/unmatched/censored episodes |
| `events.csv`, `exposure.csv`, `metrics.json` | B9 raw/reviewed/schema/QC hashes and reviewer/adjudication provenance; original event/take/class denominators, fully partitioned physical exposure and separate sensor health, matches/misses/uncertain bounds/latency/censoring |
| `parity.json`, `timing.csv`, `resources.json`, `tests.json` | Golden fixtures, errors/skips, delivery/service jitter, hardware costs/overhead, queue/acquisition accounting and scenario results |
| Existing `results.csv`, `summary.md`, `decision.json` | Every scheduled test/result/blocker, matched-control trade-offs and exact permitted claim; no fabricated measurements |

Share run directories/manifests with A6/A8/A9/A10; a standalone evaluation run may
use `reports/evaluation/<UTC_run_id>/` at execution. Runner/adapter interfaces require
implementation; no runnable command is advertised here. Keep immutable raw traces;
resume only matching source/build/data/protocol hashes. Append results to §9 later.

Keep run status (NOT_RUN/COMPLETE/FAILED_TEST/FAILED_PARITY/FAILED_TIMING/
INCOMPLETE_CAPTURE/BLOCKED_CLOCK_ALIGNMENT/BLOCKED_MOTION/BLOCKED_STATE_RESTORE/
BLOCKED_DEPENDENCY) separate from evidence level (CAPTURED_STREAM_ONLY/
HOST_C_VERIFIED/DEVICE_STATE_VERIFIED/DEVICE_PACED_VERIFIED/LIVE_CONFIRMED).
A successful upstream FSM restore is not required for recorded-Motion classifier
replay, but absent restore cannot be presented as FSM equivalence. Do not call an
incomplete gated run a failed raw classifier or an offline winner device-eligible.

Select under §5.5.11's provisional recall/resource/coverage guards; rank continuous
FA burden and annotated recall before window accuracy. Retain baseline when evidence
is inconclusive; report near-tie numerical class/episode differences and resolve them
before recommendation. No absolute clinical FA/recall requirement is established by
this plan; safety-alarm deployment remains outside research acceptance.
A11 completes only with audited full-stream R1/R2 and scheduled tests/results/blockers.
C7 hardware/live acceptance completes only with authorized identity-verified R3
timing/state/cost evidence and reserved R4 confirmation. If a required tier is blocked,
report the available narrower evidence and keep acceptance incomplete; do not waive it.
All scheduled rows currently remain NOT_RUN; no training/build/flash/measurement
or change to production firmware is performed by this documentation update.

### 5.8 Post-fall confirmation and the complete incident/alarm lifecycle (D17/A12/B8/B9/C8)

This section extends, rather than replaces, §5.4–§5.7. It specifies a research prototype
for ESP32-WROOM-32: detection → candidate → event confirmation → aftermath assessment
→ local alarm intent → bounded response/countdown → notification attempts → human
acknowledgment → explicit resolution/re-arm. Source inspection and earlier research
are evidence; the policy, APIs, modules, durations and tests below are NOT_IMPLEMENTED/
NOT_RUN. "Confirmed" means accepted by this versioned algorithm, not clinically verified.
Only this existing plan is edited; retain unrelated working-tree changes.

#### 5.8.1 Evidence, transfer limits and terminology

References PF-R1–PF-R13 are listed in §5.8.16. Earlier inspected research is carried
forward; csi-pose source, Apple workflow, smartphone IMU+CSI methods and ESP-IDF v5.5.3
Timer/NVS documentation were additionally checked for this extension. Mutable GitHub
main branches are not immutable dependencies: freeze commit/content hashes at execution.
Do not invent a complete timer recipe when an older paper's methods were inaccessible.

| Evidence | Observed architecture / setting | Transferable lesson and limitation |
|---|---|---|
| SiFall [PF-R1] | Motion/pause-driven candidate segmentation; preceding search context and 1s endpoint refinement; FallNet then alarm; human review for adaptation | Separate segmentation, decision and later feedback. Its refinement interval is not an alarm countdown or proof of post-fall injury. |
| Smartphone IMU+CSI [PF-R2] | IMU candidate; 3s/30-sample CSI assessment at 10Hz, two receiving antennas; focuses non-self-recoverable falls | Useful two-stage pattern, but its IMU, antenna count and task differ. Still/activity classification does not demonstrate unconsciousness on WROOM. |
| TCS-Fall [PF-R3] | 8s window/1s stride, displayed predictions and sample-level warning metrics | Window length and warning metrics are not incident persistence, response grace, delivery or acknowledgment policies. Do not copy 8s into these short takes. |
| csi-pose [PF-R4] | IDLE→IMPACT→ALARM; config: confirmation2s, lying/stillness fraction0.7, absence grace1.5s, refractory10s, standing-release1s/absence-release5s | Explicit FSM and evaluable-frame denominator are useful. Pose cues are additional model outputs, not available WROOM measurements. CSI stillness is disabled in inspected config; fractions alone need minimum coverage. Timeouts require update calls. |
| ElderCare two-stage checker [PF-R5] | Advertised confidence0.85/confirmation3s; inspected `confirmation_windows` is computed but unused by `check()` | Do not copy documentation as behavior: next low-variance call can confirm; high variance can leave pending indefinitely. Implement absolute deadlines and tests. Its model confidence is not our SVM margin. |
| ElderCare aftermath/pipeline [PF-R6] | Separate default30s inactivity check; new candidate can replace timestamp; initial fall and aftermath may both send emergency-level alerts | Keep first incident time immutable; deduplicate by incident/stage. Check advertised delays and duplicate integration behavior end-to-end. |
| ElderCare alert manager [PF-R7] | Level+zone cooldown, webhook retries/timeouts/circuit breaker; API success is not proof of successful delivery | Separate attempt, remote receipt and caregiver acknowledgment. Retry, cooldown, incident dedup and escalation are different state machines. |
| Wearable/RSSI/robot/vision [PF-R8] | Wearable candidate; robot navigation and visual confirmation before decision | Orthogonal evidence can disambiguate, but navigation/occlusion add delay and hardware/privacy requirements. Not an ESP32 CSI-only baseline. |
| Apple Watch [PF-R9] | Immediate hard-fall local alert; about1min immobility then30s countdown; explicit cancel/help; movement changes automatic-call workflow | Accessible user response and staged urgency are useful patterns, not validated CSI settings. Wrist detection, connectivity and identity differ. |
| Pixel Watch 2023 workflow [PF-R10] | About30s immobility before alert, then about1min without response before attempted call | A comparable dated product policy, not a recommendation to wait these durations or evidence of current WROOM behavior. |
| FDA human-factors guidance [PF-R11] | Intended users, use environments, critical tasks and foreseeable use errors | Validate alarm perception and help/cancel interaction; citation confers neither regulatory approval nor a clinical operating point. |
| ESP-IDF v5.5.3 [PF-R12/R13] | Timer callbacks serialized/short/nonblocking; monotonic timer restarts after deep sleep; NVS interrupted newest write can be lost | Independent owner task, explicit clock epochs, checked persistence and power-fault tests. No assumed hard real-time or exactly-once guarantee. |

Required distinctions:
- A window class is not an event. Multiple overlapping windows are correlated observations,
  not independent votes whose probabilities can be multiplied.
- Event confirmation asks whether the suspected fall is supported. Aftermath assessment
  asks what activity is observed. Assistance need asks whether help is requested/verified.
  None is a synonym for notification dispatch or caregiver arrival.
- A real fall followed by recovery remains a real fall. A user saying "I'm OK" ends the
  assistance workflow, not necessarily the physical-event label. "I did not fall" is
  user-reported denial, not an automatic ground-truth relabel for training.
- Low motion, limited movement, sustained movement and unavailable evidence are distinct.
  Never emit "unconscious", "breathing normally", "safe" or victim-specific posture from
  the present single-link CSI/Motion pipeline. Multiple occupants/pets/fans are confounders.

#### 5.8.2 Architecture comparison and controlled experiment catalog

A "single-frame" comparator here means one raw classification decision from a complete
24-frame window, NOT classification of one CSI packet. Preserve F0/labels/model/voter/
Motion/radio configuration for the primary lifecycle comparison. Additional feature,
threshold or sensor changes use a separate identity and matched controls (§5.5/A10).

| ID / approach | Benefit on WROOM-32 | Main risk / cost | Planned comparison and permitted claim |
|---|---|---|---|
| AL0: PROD_LEGACY detector, no new lifecycle | Reproduces current classifier/voter/gate and counts; minimal control cost | No actual alarm service, no independent expiry; startup FALL adopted immediately | A11 control; report prediction episodes only, not successful alarm handling. |
| AL1: one raw-window candidate | Earliest available decision; small state | Spikes/near-falls/startup ambiguity; cannot infer clinical confidence | SHADOW_ONLY stage comparator; same fake sink/grace as AL2/AL3; raw evidence intervention named explicitly. |
| AL2: current gated/stabilized edge confirms immediately | Uses existing two-of-three logic with almost no extra history | First-after-reset FALL bypasses votes; stable class may outlast impact or use stale support | Virtual lifecycle wrapper control with the common fixed response schedule; do not modify legacy classifier. |
| AL3: evidence-qualified multi-observation confirmation + fixed response grace | Recommended first candidate: validates startup/support freshness; compact integer state; no obligatory stationary aftermath | Extra rejection/latency; correlated votes remain; gap may cause indeterminate candidate | Default prototype in §5.8.4–§5.8.6; compare AL2 with identical response policy. |
| AL4: multi-observation AND mandatory stillness | May reject some ordinary high-motion false candidates | Rejects genuine falls with recovery/micro-movement; stationary negatives can pass; missing data can fake stillness | Research-only false-rejection comparator; use matched AL3_DELAY3 to isolate the predicate and AL3 to measure extra delay (§5.8.2). Never assume safer. |
| AL5: AL3 + evidence-dependent response deadlines | Earlier notification intent for no-motion/unknown evidence; bounded longer response for movement | Scene movement is not victim recovery; premature/late alerts and unvalidated thresholds | Compare to fixed-grace AL3 with unchanged event confirmation. Freeze rules and all limits before outer tests. |
| AL6: bounded grace/countdown variants | Directly measures user-response/latency/burden trade-off | Delays assistance; more user-error exposure; cannot choose on window accuracy | Fixed one-factor sweeps in §5.8.5; reuse AL3 and untouched response traces. |
| AL7: orthogonal pose/IMU/button/human verification | Can add information absent from single-antenna CSI | New hardware/model, memory, identity, privacy and availability dependencies | Human commands are planned; pose/IMU/robot fusion is BLOCKED_EXTRA_SENSOR and not a dependency of AL3. |
| AL8: lifecycle resilience/fault campaign | Establishes bounded time, dedup and observable failure | Stress traces are not new independent recordings or measured clinical reliability | Same selected policy; dropout/overload/persistence/notification fixtures in §5.8.12. |

Recommended order: AL0 reproduction → AL2 wrapper → AL3 one-factor confirmation test
→ AL4 diagnostic rejection test → AL6 fixed-grace sensitivity → AL5 optional adaptive
schedule → AL8 fault campaign → authorized device/live confirmation. Do not run a full
Cartesian product or simultaneously retrain the detector. AL1 is diagnostic, never a
preferred emergency policy merely because its matched-only latency is smallest.
For AL4, first require impact qualification within the same3s candidate deadline,
then assess3s after available impact qualification, with a6s candidate-to-terminal cap.
A matched `AL3_DELAY3` control waits the same extra3s with the same6s cap but no stillness
predicate; AL4 vs AL3_DELAY3 isolates rejection by stillness, while AL3 vs AL3_DELAY3
measures added delay. Do not attribute the joint predicate/delay change to one factor.
AL4's human HELP path remains immediate; unknown/insufficient aftermath is indeterminate.

#### 5.8.3 Independent state axes and invariants

The requested top-level path is `IDLE → FALL_SUSPECTED → CONFIRMED_FALL → ALARM_ACTIVE
→ RESOLVED → IDLE`. `CONFIRMED_FALL` records evidence acceptance; `ALARM_ACTIVE` records
an unresolved logical local alarm, not proven actuator delivery. They may be entered
in successive transitions during one owner-task service pass. Use the axes below to
avoid conflating event truth, assistance and external communications.

| Axis | States / fields | Owner and meaning |
|---|---|---|
| Incident | IDLE, FALL_SUSPECTED, CONFIRMED_FALL, ALARM_ACTIVE, RESOLVED; terminal UNCONFIRMED/USER_DENIED records | Lifecycle owner; immutable candidate/confirmation times and identity; separate kind=DETECTED_FALL/MANUAL_HELP/SUSPECTED_FALL_WITH_HELP and event disposition=PENDING/ACCEPTED/INDETERMINATE/USER_DENIED. Accepted is algorithmic, not independently verified truth |
| Aftermath / assistance | UNKNOWN, LOW_MOTION_OBSERVED, MOVEMENT_OBSERVED, MIXED; human NONE, HELP_REQUESTED, SELF_REPORTED_OK, CAREGIVER_VERIFIED; separate NO_RESPONSE_TO_DELIVERED_PROMPT | Evidence summaries are scene/link observations. Human response is an independent input; no unconsciousness state. |
| Sensor/evidence health | VALID, DEGRADED, UNAVAILABLE with reasons, coverage, age, clock/source epoch | Changes evidence eligibility, never sets NON_FALL, recovery or resolution. Motion freshness and CSI validity remain separately reported. |
| Notification | Per-stage NONE, DISPATCH_PENDING, IN_FLIGHT, BACKOFF, RECEIVED, FAILED, DELIVERY_UNKNOWN, CANCELLED_BEFORE_SEND; separate local LOCAL_PENDING/LOCAL_ACTIVE/FAILED/UNKNOWN and response RESPONSE_WAIT/COUNTDOWN; caregiver ACKNOWLEDGED independent | Owner stores stage0/1/2 status separately: a received stage1 can coexist with pending stage2 and active local alarm. ACK does not overwrite receipt/failure history or resolve the incident |

Invariants (assert in Python and C):
1. Only impact/candidate evidence or an explicitly typed human-help incident can create
   an incident. Stationarity alone never enters FALL_SUSPECTED/CONFIRMED_FALL.
2. A HELP request without fall evidence creates `kind=MANUAL_HELP`, not a confirmed fall;
   allow it from any state, including IDLE or unavailable sensor, with distinct metrics.
3. First candidate time, first-stage cap and separate stage2 anchor never restart on
   duplicate FALL, movement, reconnect, overflow, calibration update or UI refresh.
   Explicit HELP may advance an uncreated stage1, but cannot restart an existing anchor.
4. Missing evidence advances wall-clock deadlines but contributes zero valid duration.
   Valid-time counters never substitute for the bounded absolute pending deadline.
5. Accepted-fall and explicit-help incident state survives classifier/voter/Motion-cache
   resets and `esp_wifi_sensing` INACTIVE. Absence and generic inactivity are not automatic release.
6. `ALARM_ACTIVE` remains until explicit authorized resolution. External receipt/ACK,
   a NON_FALL class, recovered movement or session end cannot silently resolve it.
7. No backdating: preserve support timestamps, decision availability and actual transition
   time separately. Slow processing cannot rewrite dispatch or confirmation into the past.
8. At most one unresolved zone-level incident is operational in this single-link prototype;
   subsequent independently qualified falls are subevents, not ignored or new victims.
9. One INITIAL notification intent per incident/escalation stage; retries keep its ID.
   Explicit bounded UPDATE intents are separately keyed (§5.8.7), not new falls/stages.
   Exactly-once external delivery is not claimed; the gateway must deduplicate idempotently.
10. `first_remote_intent_cap` bounds scheduled STAGE1 intent only, relative to confirmation;
    `stage2_due` is separately anchored to the immutable ACTUAL first stage1 intent+60s.
    Failed attempts, updates, re-falls, reconnects and reboot never reset either anchor.
    Actual service/delivery lateness and durability failures remain explicit; the cap
    is not a bound on stage2, network receipt, ACK or physical assistance.

#### 5.8.4 Explicit transition and cancellation contract

UNCONFIRMED/USER_DENIED are terminal record dispositions, not extra persistent FSM
states. Algorithmic event acceptance and later denial/disposition are both retained;
DENY_FALL never overwrites an accepted event as ground-truth NON_FALL. Runtime human
caregiver verification is assistance disposition, distinct from independent B9 labels.
Unsupported commands/inputs are reasoned rejections or self-transitions, never guessed
paths. RESOLVED retains the episode latch and history until qualified re-arm.

`entry_evidence_ok` for recommended AL3: the current candidate is an eligible gated
FALL; among the last three DISTINCT chronological decision observations, at least two
have raw FALL, compatible complete support, the same selected link/source epoch,
matching-peer Motion age in [0,250000]µs and Motion>=3850000 at their ORIGINAL decision
availability. Counted observations lie in a trailing1.5s availability span at service;
require the latest observation's callback-support end to be at most0.5s old at service.
Earlier votes may be older than0.5s within the1.5s evidence span; that is evidence memory,
not held-output coverage. Duplicates, stale latest backlog, invalid support and unavailable
Motion do not count. Use source decision IDs, not retransmitted
JSON. The last3 slots include distinct unavailable/non-FALL decisions in the current
source epoch; such slots do not count as eligible FALL votes and may not be skipped to
find an arbitrarily older bundle. A discontinuity invalidates the bundle. Preserve the
exact existing high-Motion marker (>5000000); it is NOT a probability
and is not sufficient confirmation. This extra qualified-evidence policy is a named
AL3 intervention, not a claim that the legacy voter already performs these checks.

On a normal qualified edge, accept the two already observed votes; do not require
FALL to continue throughout stationary aftermath. A first-after-reset gated FALL with
only one eligible observation starts FALL_SUSPECTED and waits for qualifying evidence.
A later raw/gated FALL can complete the bundle while suspected without a second rising
edge. A later NON_FALL may simply mean impact ended: it does not negate accepted evidence.
No impact annotation/ground-truth peak is available to the runtime transition logic.
After an expired/denied/resolved candidate, preserve its episode-consumption latch:
sustained old FALL cannot create a fresh3s pending loop. A new impact episode requires
observed release (three consecutive distinct valid raw NON_FALL decisions) followed
by a new qualified bundle. After resolution this new bundle may bypass the additional
2s re-arm monitoring hold, but NEVER bypass the observed-release requirement. HELP can
always bypass detector re-arm. Very close falls with no observable release remain
unresolved possible-re-fall evidence; report this detector limitation, not separate hits.

| Current → next | Entry / exit predicate | Time/action rule | Cancellation / missing-evidence behavior |
|---|---|---|---|
| IDLE → FALL_SUSPECTED | New eligible gated FALL episode; fresh source/decision ID; no unresolved incident | Allocate incident ID; record `t_candidate_available`; freeze selected policy/baseline; start3s confirmation deadline | A lone invalid/stale/missing-Motion result does not create a fall candidate; report unavailable opportunity. |
| FALL_SUSPECTED → CONFIRMED_FALL | `entry_evidence_ok`; policy fixed before replay | Immediate upon available qualifying evidence, including already qualified entry votes; store acceptance bundle/time/reason | No requirement to remain FALL or still. Do not promote from high Motion or low-variance CSI alone. |
| FALL_SUSPECTED → terminal UNCONFIRMED → IDLE with episode latch | Deadline reached without sufficient qualifying evidence and no active HELP workflow | At3s from first candidate close as INSUFFICIENT_EVENT_EVIDENCE/QUALITY_INDETERMINATE; retain terminal record; consume old episode until observed release | Indeterminate is not a verified false fall. Source reset invalidates bundle, not deadline. No automatic remote fall alert in AL3. After HELP, expiry marks event indeterminate but leaves assistance ALARM_ACTIVE |
| FALL_SUSPECTED → RESOLVED with USER_DENIED or UNCONFIRMED disposition | Authorized incident-scoped DENY_FALL or caregiver RESOLVE | Record actor/disposition, cancel unsent work and retain event/terminal history; normal resolution re-arm applies | IM_OK alone stores assistance response while event confirmation may finish before3s; it does not deny a fall. Same-time HELP takes precedence over cancellation |
| CONFIRMED_FALL → ALARM_ACTIVE | Accepted event and unresolved assistance workflow | Same service pass: create local alarm intent, initialize aftermath and response/countdown deadlines | If prior incident-scoped OK/verified resolution exists, record CONFIRMED_FALL→RESOLVED without notification; retain event. Local delivery failure is explicit, not cancellation. |
| ALARM_ACTIVE / RESPONSE_WAIT → COUNTDOWN | Fixed-grace deadline reached without resolution/help, or selected AL5 condition | Deadline based on confirmation time, never latest motion/candidate; visible countdown and immediate help/cancel controls | Quality failure never pauses the countdown indefinitely. A countdown already started cannot be extended by later movement. |
| ALARM_ACTIVE / stage1 NONE → stage1 DISPATCH_PENDING | HELP, countdown expiry or FIRST remote-intent cap reached | Freeze actual first stage1 intent time/ID; HELP bypasses grace; record nominal due/actual service/uncertainty | Incident stays ALARM_ACTIVE; fake sink in SHADOW_ONLY. Cap applies only to stage1, never stage2/delivery |
| Each stage DISPATCH_PENDING → IN_FLIGHT → RECEIVED or BACKOFF → DISPATCH_PENDING | Valid worker admission/result with intent/attempt/version IDs |5s attempt timeout; at most3 admitted attempts with1s/2s backoff; exhaustion → FAILED/DELIVERY_UNKNOWN | Queue full remains pending only until5s admission limit, then FAILED with reason=FAILED_ADMISSION; no fictitious attempt. Partial/late delivery stays UNKNOWN until verified receipt; same intent ID |
| ALARM_ACTIVE → RESOLVED | Incident-scoped SELF_REPORTED_OK, verified caregiver resolution, or user denial with explicit recorded disposition | Store actor, receipt time and resolution reason; cancel unsent work; send resolution update if already dispatched | Human ACK alone means "message seen", not "person safe". Recovery/no CSI/timeout do not resolve. |
| RESOLVED → IDLE | Resolution recorded; qualified observed release/re-arm |3 fresh distinct raw NON_FALL decisions plus2s valid link monitoring after resolution; enable only NEW episodes, never old held FALL | No-input never fabricates release. New qualified bundle after observed release may bypass2s hold via RESOLVED→IDLE→FALL_SUSPECTED in one service pass; HELP always bypasses it |
| Any unresolved state + new candidate | Same consumed episode → duplicate; observed release then new qualified bundle → subevent; first fall in a MANUAL_HELP incident needs no prior fall release | Append evidence/acceptance/subtype/timestamps, initialize new aftermath if applicable; existing first-intent/stage2 anchors unchanged | Possible re-fall without release is not a separate hit; no blind refractory suppression or new victim count |
| Reboot / deep sleep with durable unresolved record | Valid journal with unresolved accepted fall or explicit-help incident | Restore same ID/kind as ALARM_ACTIVE, evidence UNKNOWN; preserve stage IDs/first-intent anchor; conservative due actions under §5.8.10 | No healthy-IDLE reset, fresh grace/stage2 delay or subtraction of old monotonic clocks; reconcile unknown delivery |
| IDLE/RESOLVED → ALARM_ACTIVE with MANUAL_HELP | Authorized HELP; no current unresolved incident | Allocate a new linked manual-help ID if prior resolved; local/stage1 urgent intent immediately, no fictitious CONFIRMED_FALL transition | Works with no CSI and bypasses detector re-arm; manual-help metrics separate |
| FALL_SUSPECTED → ALARM_ACTIVE with SUSPECTED_FALL_WITH_HELP | Incident-scoped HELP | Keep same ID and pending event-evidence deadline; dispatch assistance immediately; later qualification marks accepted event without restarting alarm/grace | At3s insufficiency leaves HELP workflow active with indeterminate event, not an invented confirmed fall |
| ALARM_ACTIVE / stage2 NONE → stage2 DISPATCH_PENDING | stage2_due reached without prior authorized ACK/resolution | Create one stage2 intent at actual service; independent of stage1 receipt/retry/failure | ACK at/before deadline suppresses creation; later ACK cancels only unsent work; stage2 is not clipped by first-intent cap |
| Each stage / unresolved incident → ACKNOWLEDGED assistance-message flag | Authorized incident-scoped caregiver ACK | Record actor/time/version; suppress next unstarted stage, cancel unsent escalation work; keep receipt/failure states | Local status remains active; ACK alone cannot set RESOLVED |
| Local LOCAL_PENDING → LOCAL_ACTIVE/FAILED/UNKNOWN | Observable actuator/mock result | Record intent/delivery/perception separately; local failure does not pause fixed deadlines | No observed prompt means PROMPT_UNDELIVERED/UNKNOWN, not delivered-prompt nonresponse |
| Any state → same incident state | Quality/reset/tick/STATUS/duplicate result not satisfying a transition predicate | Update health/deadline/counter/result fields only; reject stale/unauthorized inputs | Evidence reset never resolves; after RESOLVED late receipt results are archived, not incident resurrection |

Ordering: before a due action, inspect admitted pending commands (including HELP
mailbox) by captured receipt time. Service deadlines BEFORE inputs received later than
that deadline; no retroactive cancellation of attempted sends. At the SAME timestamp,
HELP precedes RESOLVE/DENY_FALL/IM_OK, then caregiver ACK, then qualifying observation,
then deadline expiry; within each priority use monotonic receipt/source sequence.
An exact-deadline qualified observation may confirm; an exact-stage2-deadline ACK
suppresses stage2. Simultaneous HELP/cancel conflict records cancel rejection as
CONFLICT_HELP_PRIORITY, not immediate last-writer-wins resolution. Invalid/unauthorized
commands have no priority effects. Later commands/results follow recorded receipt order.
Log actual service/queue delay and late_command; evidence-age checks use actual service,
not backdated receipt. Freeze/test this arbitration across queues and bounded batches.

#### 5.8.5 Proposed clocks, durations and experimental sweeps

All new numbers in this subsection are DESIGN PROPOSALS for testing, NOT observations,
clinical limits or copied optimal settings. Exact legacy thresholds above remain source
facts. Use int64 monotonic microseconds and `now>=deadline` boundaries; persist policy
version/hash independently of model hash. The default research profile is
`PF_AL3_FIXED_V1`, `mode=SHADOW_ONLY`, with fake notification delivery.

| Parameter | Proposed initial value | Bounded sensitivity / purpose |
|---|---|---|
| Candidate evidence span |1.5s for the last3 decisions;2 eligible raw FALL | Span1.0/1.5/2.0s with fixed votes; then votes1-of1/2-of3/3-of5 at common2s span as separate experiments. Count missing opportunities and overlap, not independent likelihoods. |
| Suspected hard deadline |3s from first available candidate |2/3/5s one-factor sweep; never unbounded or reset by new input. |
| Source evidence-age horizon |0.5s for latest callback-support age / decision coverage; Motion expires at250ms | Different from the1.5s retained vote-evidence span and legacy held class. Use the stricter actual source/Motion freshness for scene evidence; archive cadence and expire on reset/source change. Not a classifier reset modification. |
| Aftermath bins / minimum coverage |0.5s non-overlapping wall-time bins;>=80% valid-time coverage in assessment interval; no unsupported gap>0.5s | Coverage0.7/0.8/0.9 one-factor study. Frame fractions alone can give100% from a single sample; bins must retain unknown duration. |
| Aftermath observation interval |Trailing3s after confirmation, once the interval is full; low/movement fraction>=0.7 of valid duration |2/3/5s with fixed coverage; fraction0.6/0.7/0.8 separately. Unknown bins cannot enter numerator. AL4 anchors at impact qualification instead; AL3 has no requisite stillness. |
| Post-movement hold, AL5 only |>=2s supported movement; no claim of standing/recovery |1/2/3s separately; continued unknown/mixed evidence does not count. |
| Fixed response grace, AL3 |30s from confirmation, with local intent immediately |10/30/60s one-factor AL6; changes notification timing only, not detector labels/recall. |
| Visible countdown |10s after grace |5/10/20s separately; not copied Apple's30s. HELP bypasses; cancel control remains available. |
| FIRST remote-intent cap (`first_remote_intent_cap`) |60s from available confirmation, STAGE1 only | Clip adaptive first-intent deadlines; keep nominal/effective schedules. Not a stage2, network-delivery or safety bound; actual service lateness is measured separately |
| AL5 response branch |At+10s inspect the trailing3s; supported movement with2s hold retains30s grace, otherwise begin10s countdown | LOW_MOTION/MIXED/UNKNOWN take the earlier branch; unknown text says "evidence unavailable", not immobility. After branch selection, later evidence cannot postpone an earlier started countdown. |
| Local reminder / dedup |At most once per10s while unresolved; new HELP/stage may interrupt | This limits repeated prompt emission, NOT new-fall detection. No automatic incident expiry. |
| Worker admission / attempt / retries |Admission wait<=5s; attempt timeout5s; at most3 admitted attempts/stage, backoff1s/2s | Proposed profile; admission failure reason separate from network failure; persisted budget, no unbounded wait or alarm-task networking |
| Human ACK escalation (`stage2_delay`) |60s after immutable actual first STAGE1 intent → stage2 if no ACK/resolution | Separate deadline, NOT clipped to confirmation+60s; independent of receipt/retries/failure. Normal stage1+40s gives stage2+100s after confirmation. Two stages only; then unresolved/failed for manual intervention |
| Owner service target |Wake on input or next deadline; maximum planned idle wait50ms | Tick conversion rounds safely; timer/service lateness measured. It is a research target, not hard real-time guarantee. |
| Re-arm / retention |3 valid NON_FALL decisions plus2s valid monitoring; no unresolved-incident TTL | Expiry may archive bounded terminal records, never erase unresolved incident. Retention policy in §5.8.14. |

For AL6 grace/countdown sensitivity only, use named `AL3_CAP80` with a proposed80s
FIRST stage1 intent cap for ALL sweep rows, so60s grace/20s countdown does not silently
clip. Keep stage2_delay=60s unchanged; isolate any future stage2-delay sweep under a
new protocol. Compare first-cap80 vs first-cap60 separately and log nominal/effective
values. Reject fixed profiles whose grace+countdown exceeds first cap; adaptive earlier
branches are explicitly clipped. Require nonnegative/overflow-safe separate deadlines.
Vote-count sensitivity uses a COMMON2s evidence span for1-of1/2-of3/3-of5 controls;
span sensitivity with fixed2-of3 remains separate. Do not compare an impossible5-decision
span at the measured irregular cadence as if it were a supported optimum.

Source-arrival times, decision-availability times and owner times are different. Use callback
arrival for source age only when known/alignable; if only host-clock proxies exist,
record their evidence tier and uncertainty. Ground-truth impact must never set runtime
assessment windows. Anchor the first prototype at available confirmation time, record
support-end offset and any overlap with descent/impact as contamination, and test the
sensitivity without claiming an exact physical post-impact boundary. Confirmation at
one normal qualified edge may be immediate; the3s bound is not an obligatory delay.

Deadline formulas (proposed): `t_first_due=min(t_confirm+grace+countdown,
t_confirm+first_remote_intent_cap)`; eligible HELP makes an uncreated stage1 due
immediately at actual command service. Store `t_first_remote_intent` once when the
stage1 logical intent is actually created. Then `t_stage2_due=t_first_remote_intent+
stage2_delay`, unless ACK/resolution suppresses it. Intent creation, durable outbox
commit, worker attempt, endpoint receipt and caregiver ACK are distinct endpoints.

Illustrative on-time schedules, NOT measured latency: AL3 local intent+0, stage1+40,
stage2+100 seconds after confirmation without ACK. AL5 earlier branch gives stage1+20
and stage2+80; supported movement gives+40/+100. HELP at confirmation gives+0/+60.
AL6 first-cap80 extreme gives+80/+140. Only stage1's SCHEDULED intent is capped at+60
(default); stage2 is later by its separate rule. Queue/service/storage/network delays
are separately reported, not hidden by backdating. Restored anchors follow §5.8.10,
never a new grace or restarted60s stage2 delay. Clinical limits require intended-use
risk review and new confirmation, not this proposed arithmetic.

#### 5.8.6 Aftermath evidence, grace and cancellation policy

For the first prototype use the existing synchronized matching-link Motion diagnostic
as an OBSERVATION, not a new classifier feature. Preserve3850000/5000000 only for
legacy gate/marker; they do NOT define stillness or recovery thresholds. A separate
quiet/movement threshold contract belongs to the aftermath policy and requires B8 data.
Until that contract is validated, set `aftermath=UNKNOWN`; AL3 fixed-grace still works.
AL5 and AL4 real-evidence rankings are BLOCKED_AFTERMATH_CALIBRATION, though their
mechanics can run on explicitly synthetic fixtures.

Planned compact estimator: accumulate distinct fresh Motion summaries into disjoint
0.5s bins; include only intervals until next update, source invalidation or freshness
expiry. Do not reuse a250ms sample for3s or interpolate dropout as zero. Per bin retain
valid duration, time-weighted motion mean/range and quality flags. Define two separately
frozen thresholds `theta_quiet<theta_move` in the same scaled Motion units; values are
fit on only training/development verified quiet/activity intervals, with held-out
operating-point selection inside A10, never by labeling "unconscious" participants.
Use a threshold dead band: <=quiet is low-motion, >=move is movement, intermediate is
MIXED; nonfinite/unsupported/insufficient coverage is UNKNOWN. Over the trailing full
assessment interval, LOW_MOTION_OBSERVED requires low-duration/valid-duration>=0.7;
MOVEMENT_OBSERVED requires movement-duration/valid-duration>=0.7, plus the2s supported
movement hold for AL5's longer grace. Otherwise report MIXED if coverage is sufficient,
UNKNOWN if not. Apply exact inclusive threshold/fraction boundaries in fixtures.
If development data cannot separate these states across sessions, stop AL4/AL5 and
keep UNKNOWN/fixed grace.

An optional amplitude-relative feature branch may reuse A8/D10 causal calibration,
without silently replacing Motion or F0. Compare separately; fit noise floors and
quiet references inside training/calibration ownership. Freeze only the NEW aftermath
estimator's baseline/adaptation from first candidate through resolution/re-arm; do not
pause or alter the existing generic Motion FSM in legacy controls. Any upstream adaptation
intervention is separately named and tested. Do not adapt a collapsed/quiet scene
into "normal". Resume only after qualified release and a documented calibration check.
Neither smooth Motion nor single-antenna delta amplitude proves victim-specific motion,
posture, breathing, injury or consciousness; add those only under a separately validated
orthogonal-sensor protocol (AL7).

| Observation / action | Event interpretation | Response / escalation recommendation |
|---|---|---|
| Supported low scene motion after accepted impact | Event retained; assistance UNKNOWN | Local response prompt; optional AL5 earlier bounded countdown; text "fall detected; little scene movement; response unknown". |
| Limited/intermittent or sustained movement | Possible movement/recovery attempt, not proof of safety | Retain event; allow normal bounded response window, never automatic cancellation or indefinite movement extension. |
| SELF_REPORTED_OK / verified caregiver resolution | Real event may have occurred; human disposition recorded | Resolve assistance workflow; cancel only unsent intent; keep event and update any notified recipient. |
| "I did not fall" | User denial; algorithm result and denial both retained | Close with USER_DENIED; use independently reviewed feedback for later learning, never immediate automatic retraining. |
| HELP / inability to respond via validated interface | Explicit HELP is strong assistance input; no response alone is ambiguous | HELP dispatches immediately; nonresponse uses bounded schedule with prompt-delivery/quality context, not diagnosis. |
| Missing CSI/Motion or unobservable local prompt | Evidence and/or interaction unavailable | Suspected-only closes indeterminate at hard deadline; confirmed event persists and advances schedule. Record PROMPT_UNDELIVERED/UNKNOWN rather than NO_RESPONSE_TO_DELIVERED_PROMPT. |

Cancellation after a notification attempt cannot unsend it. Send a separate disposition
update referencing the same incident if a real authorized gateway was used. A remote
caregiver ACK suspends the next unstarted escalation stage but does not resolve the
incident; explicit RESOLVE is required. Keep local status visible and allow HELP to
reopen assistance on the same unresolved incident. If a genuinely resolved incident
has a new HELP request, allocate a new manual-help incident with a link to prior history.

#### 5.8.7 Notification delivery, escalation and human commands

Initial sinks are deterministic fake workers and diagnostic logs. The current activity
panel/serial line is not a validated safety alarm; LED/log output is not assumed
perceivable by a fallen user. A real local audible/tactile/display interface, accessible
help/OK controls, gateway and approved recipients are later separately authorized work.
A browser-tab close, USB disconnect or JSON publication success does not acknowledge,
resolve or reliably deliver a local prompt.

Each intent has `{incident_id, stage_id, notification_id, policy_hash, urgency,
created_available_us, evidence_summary, disposition}`. Attempts add `attempt_id`,
worker start/end, result, receipt ID and timeout/uncertainty. Use stage0 local, stage1
primary test caregiver/gateway, stage2 secondary test recipient; no emergency-service
number, unsolicited external contact or default public endpoint in this plan.

For stage1/2: at most3 admitted attempts per stage, stable notification idempotency key,
5s attempt timeout and1s/2s backoff. Start attempt time on worker admission, not intent
creation; bound a full/unavailable worker admission wait to a proposed5s, then mark
FAILED with reason=FAILED_ADMISSION without pretending a network attempt occurred. Exhaustion sets FAILED
for definite rejection or DELIVERY_UNKNOWN for possible partial send; local incident
persists. Counters/remaining attempts survive committed restore; reboot is not a new
3-attempt allowance. Late verified receipt updates the same stage, never resurrects a
resolved incident or creates a new fall. A disconnected gateway is not delivery.

Create `t_stage2_due` ONCE when the actual first stage1 intent is created, not when
stage1 exhausts retries or is received. At first-intent+60s, absent authorized ACK/
resolution, create stage2 even without stage1 receipt; reason=DELIVERY_FAILED or NO_ACK.
Do NOT clip it to confirmation+60s: the default on-time schedule is stage1+40/stage2+100.
ACK received at/before that due time suppresses creation (§5.8.4 arbitration); later
ACK cancels only unsent work. Failed stage1 admission cannot postpone stage2. No extra stages/retry loop by default; unresolved status and failure remain
visible for manual intervention. HELP after ACK creates an explicitly deduplicated
urgent update, not a new physical fall count. Initial stage intents and UPDATE intents
are distinct record types: update key=incident/stage/update-sequence, coalesce repeated
unchanged subevent information, at most one non-HELP update per10s and one pending update
slot. New qualified subevents update evidence but do not restart/shorten fixed first
response deadlines; HELP alone bypasses grace. Saturated update slots retain pending
intent and expose loss/saturation, not silently overwrite an in-flight send.

Command contract: incident-scoped `HELP`, `IM_OK`, `DENY_FALL`, `ACK`, `RESOLVE`, `STATUS`;
include command ID, incident ID, actor/role, source, captured receipt time and expected
incident version. Only HELP/STATUS may use `incident_id=null` in IDLE; HELP then allocates
a manual-help incident and returns its ID. All cancel/ACK/resolution actions require
an existing incident ID. The parser submits to the owner, never directly mutates FSM state.
Duplicate IDs return the prior result; stale incident/version, wrong role, oversized
payload, replayed old-boot commands or malformed IDs return reasoned rejection. ACK
means caregiver message receipt; RESOLVE requires explicit disposition. Local user
IM_OK is self-reported, not verified safety. Raw serial/debug commands are development
controls, not authenticated production user input; remote operations require gateway
authentication, authorization and audit. No security-parameter changes are implemented.

Freeze the role matrix: participant/local-user HELP/IM_OK/DENY_FALL; designated caregiver
HELP/ACK/RESOLVE; authorized supervisor may exercise these in labeled lab simulations;
STATUS is read-only for permitted viewers. ACK must reference an existing incident and
stage notification ID (the caregiver has seen that message); it is not an arbitrary
IDLE command or proof of physical safety. RESOLVE includes explicit disposition. Command
receipt, admission, validation and application have separate statuses/times. Store the
idempotent result for duplicate command IDs; stale/new-ID commands after resolution
cannot resurrect the incident, except a fresh HELP allocating the linked new manual case.

#### 5.8.8 Edge cases and failure-mode protocol

| Scenario | Required behavior | Diagnostic / validation consequence |
|---|---|---|
| Near-fall without accepted impact | Candidate may expire without sufficient event evidence; reviewed recovery/denial logged | Include catching balance/support, stumble, fast sitting and kneeling hard negatives. No retrospective safe/false label from movement alone. |
| Real fall with immediate self-recovery | Preserve accepted event; human OK may resolve; movement alone does not | Report event recall and assistance escalation separately. Mandatory-stillness AL4 false rejection is a primary risk. |
| Prolonged quiet sitting/standing/sleep/empty room | No candidate/incident from quiet evidence alone | Stationary-negative FA/hour plus quality coverage; force synthetic stillness-only sequence to keep IDLE. |
| CSI dropout during suspected confirmation | Valid-time coverage stops; no extrapolated zero;3s hard deadline closes indeterminate if insufficient | Availability-conditioned result secondary; indeterminate actual falls remain end-to-end misses, not excluded. |
| Dropout after confirmation / during countdown | Keep incident/intent and independent deadlines; unknown assessment; do not clear on reconnect | R1/R2/R3 tick-only fixtures must dispatch scheduled fake intent without further CSI. |
| Stale/wrong-peer Motion; invalid CSI; source/channel epoch change | Invalidate new evidence/support; mark health and boundary; keep confirmed incident | Test exact250ms inclusive Motion age; keep PROD_LEGACY vs PLAN_GAP05 classifier differences independent. |
| Candidate burst from same sustained FALL | Same episode/incident; dedup; fixed candidate/first-intent anchors | Count duplicates; never restart3s confirmation, first-stage cap or stage2 first-intent+60s deadline; no per-window sends |
| Genuine repeated fall after observed release while active | Append independently qualified subevent to same incident, retain initial times; urgent update if warranted | Match physical subevents separately from incident/notification counts; avoid blind10s refractory detection suppression. |
| More pending subevents than storage | Fixed four compact subevent descriptors; append saturation counter/last ID; do not overwrite active incident | Detailed ordered telemetry remains required; overflow invalidates exact subevent-trace completeness, not silently a pass. |
| Classifier/owner/command/worker/telemetry queue overload | Separate counters, nonblocking ingress, latched health failure; owner deadlines still serviced | Lost evidence is UNKNOWN; rejected commands get negative acknowledgment; notification/trace loss never labeled successful. |
| User response at countdown expiry; delayed duplicate cancel | Receipt-time/sequence arbitration in §5.8.4; no retroactive undo; idempotent response | Test deadline−1µs/equal/+1µs, admission failure, backlog and send-start races. |
| Network timeout, retry, ACK after failure | Same intent ID; separate unknown/failed/received/ACK; explicit next-stage policy | Fake endpoint script exercises partial sends/late receipts/idempotent replay. Cooldown is not caregiver ACK. |
| Reboot/brownout/sleep; interrupted durable write | Restore committed unresolved incident; fresh clock epoch; disclose uncommitted loss risk | Power-fault tests; no arbitrary new boot-based fall count, silent IDLE or claim of crash-proof delivery. |
| Multiple people/pet/fan/environment movement | Scene motion cannot identify victim recovery or absence | UNKNOWN/scene-only assessment, no victim-specific cancel; stratified mixed-occupant tests and intended-use limitation. |
| Confirmed fall before recording end | Censor evidence/latency/ACK; retain incident as unresolved in live service | Isolated short take cannot validate30–60s workflow. Synthetic extension is functional evidence only. |
| Prompt not perceivable; tab/host absent; sensor dead at IDLE | Show interaction/coverage fault, not NO_RESPONSE or NON_FALL | Accessible-interface acceptance blocked; sensor-fault advisory is a separate health channel, not a fall/manual-help incident in this FSM |

#### 5.8.9 Technical integration: isolated C core, observations and queues

Implement only after separately authorized A12/C8 execution. Keep the generated model,
16-delta extractor, source classifier queue depth4/zero-wait, existing voter and Motion
gate unchanged for AL0–AL3 controls. New lifecycle qualification is downstream, not a
silent alteration of `activity_prediction_stability_update()` or a seventeenth feature.
Do not feed generic `esp_wifi_sensing` ACTIVE/INACTIVE directly into incident transitions.

Planned pure-C core: `main/fall_alarm_fsm.c/.h` exposes
`fall_alarm_init(policy, boot_epoch)`, `fall_alarm_step(state, event, now_us, effects)`,
`fall_alarm_next_deadline(state)` and explicit checked restore/serialize operations.
These names/interfaces are proposals, not existing APIs. Core has no ESP-IDF/clock/
network/JSON/flash calls, dynamic allocation or ground-truth access. Use a bounded typed
union for OBSERVATION, MOTION_SAMPLE, QUALITY_CHANGE, USER_COMMAND, TICK, STORAGE_RESULT and
DELIVERY_RESULT; callers provide monotonic time. `effects` is a bounded list of state
transitions, local/remote intents, journal requests and command results. Host-C and
Python use the same policy schema, ordering, timestamp bounds and saturation rules.

A planned `main/fall_alarm_manager.c/.h` owns this core in ONE independent task. It
services absolute deadlines on input and timed wake even when the classifier remains
blocked on `xQueueReceive(..., portMAX_DELAY)`. Wait at most the smaller of next deadline
and proposed50ms; safely round FreeRTOS ticks and measure actual lateness. Timers, if
used, only notify the task; no classifier/FSM/network/flash/printf work in timer callbacks.
Do not rely on timer events queued behind CSI to service an urgent countdown.

Observation provenance must include run/build/model/policy IDs; boot/source generation;
selected link/peer; source support start/end ordinals/timestamps; raw/voted/gated class;
decision availability/service time; Motion timestamp/value/age/verdict; validity/reset/
queue-loss reason. Carry callback sequence and monotonic callback-arrival timestamp in
`activity_frame_t` through the classifier depth4 queue; capture enqueue attempt/dequeue
and support bounds in existing traces. Hardware RX timestamps are a distinct domain,
not blindly interchangeable with callback time. Emit internal observation before UI
throttle, including abstention/invalid/reset outcomes, so missing publication does not
masquerade as missing classification or NON_FALL.
Feed aftermath bins from distinct source-timestamped `activity_classifier_note_motion_sample()`
inputs, not only Motion values repeated on classifier predictions. Otherwise sparse
24/12 prediction cadence may fail the80%/250ms coverage contract by construction.
Use a bounded per-link bin accumulator with compact snapshot/sequence/loss reporting;
no raw Motion flood into the decision queue. Its timestamps and discontinuities remain
replayable, and unknown sample cadence stays BLOCKED_MOTION/UNKNOWN, not assumed coverage.

| Integration surface | Planned minimal change | Regression / separation requirement |
|---|---|---|
| `main/activity_classifier.c/.h`: enqueue/frame/task | Propagate callback sequence/time, support boundaries, source generation and reset reason; emit compact lifecycle observations | Existing depth4/zero-wait admissions and next-accepted reset semantics unchanged; measure timestamp overhead and possible queue-loss changes. |
| `classify_window()` / Motion lookup | Supply raw/stable/gated stages, selected Motion age and unavailable reasons before serial publication | AL0 feature/score/voter/gate parity; no new thresholds in generated artifact. |
| `main/activity_prediction_stability.c/.h`, `activity_motion_gate.c/.h` | Preserve as controls; add downstream evidence-bundle tests rather than edit them for AL3 | First-reset FALL and exact gate boundaries remain reproducible. |
| Planned `fall_alarm_fsm` / `fall_alarm_manager` | Single owner, policy validation, deadline service, bounded records, independent reset scopes | Pure core deterministic; no direct cross-task state mutation or annotation input. |
| `main/web_serial_monitor.c/.h` callback / publish / `handle_command` | Pass ingress metadata; separate versioned incident/notification publication; parse incident-scoped commands/results | Preserve existing activity JSON compatibility; command receipt != applied/ACK/resolution; no callback blocking. |
| `tools/web_serial_monitor.html` | Separate experimental detection, incident, quality and delivery panels; explicit HELP/OK/denial/ACK/resolve controls and countdown | Feature-gated research mode; never imply current classification panel is a safety alarm. Browser verification required when UI implementation is authorized. |
| `tools/csi_recorder.js`, diagnostic recorder/protocol/archive modules | Preserve ordered lifecycle events and command/receipt clocks alongside CSI/Motion; version/hash schema | Keep raw CSI and recording compatibility; source losses and diagnostic losses separate. Audit actual interfaces before changing them. |
| `main/app_main.c`, `main/CMakeLists.txt`, `main/Kconfig.projbuild` | Initialize lifecycle after identity/policy/storage checks; register new modules; feature flag default OFF, mode SHADOW_ONLY | No radio/security/model change, no accidental alarm activation on existing builds. |
| `fall_detection/tests`, shared A11/tools replay adapters | Add Python policy/core fixtures, host-C parity, full-stream deadline/command/delivery replay | Reuse A10 ownership and A11 transport/clock contract; do not create a competing training runner. |

Proposed bounded storage: observation queue8, command queue4, two remote stage1/2 intent
slots, one coalesced local-intent state, one active zone incident, four compact subevent
descriptors, six aftermath bins, one pending update slot and one reserved HELP mailbox.
Stage deadline creation is a logical owner-state effect, independent of worker admission;
full sink queues expose admission fault/lateness and never hide or overwrite a due stage. Confirmation evidence ring holds at most five decision
records for the3-of5 sensitivity variant; default AL3 reads the last three. Fixed-size messages
carry compact IDs/classes/time/flags; full features and verbose strings stay in the
existing deferred diagnostic path. Target observation<=64 bytes, command<=48 bytes and
intent<=96 bytes as STRUCT DESIGN LIMITS, not measured `sizeof` values. Carry additional
provenance through a versioned trace/config dictionary if it does not fit; never truncate
identity/timestamp to force parity. Add compile-time size assertions at implementation.

On observation overflow: increment separate loss counter, latch discontinuity/quality
UNKNOWN, invalidate confirmation/aftermath support across the gap; nonblocking callback
continues. Keep confirmed incident. Health is stage-specific: VALID needs coherent source epoch,
compatible layout and fresh required inputs; DEGRADED means partially observed support
with losses/insufficient coverage; UNAVAILABLE means expired/missing required input or
unknown clock/source identity. Raw classifier validity can remain VALID while gated/
aftermath validity is UNAVAILABLE. Health faults cannot mutate event disposition.
Prioritize commands/results and deadline service;
bounded batches with clock/deadline checks prevent continuous observations starving
countdowns. Failed command enqueue returns BUSY/rejected with command ID; never display
"cancelled" or "help sent" before owner acceptance. Provide a reserved/coalescing HELP
mailbox for the active incident, preserving earliest receipt and count; owner validates
scope before application. Full notification slots retain active pending intent and raise
an explicit saturation fault; retries/new stages cannot overwrite it. All saturation,
ordering and mailbox races require AL8 fixtures, including four subevent descriptors.

#### 5.8.10 Persistence, reboot, clock epochs and calibration lifecycle

For the prototype journal only semantically important changes: accepted fall or explicit-
help incident, outbox/stage and attempt-budget changes, delivery/ACK and resolution. Never write each CSI frame,
Motion bin or timer tick to flash. Use one versioned compact NVS blob containing
schema, journal sequence, incident/kind/policy IDs, immutable event acceptance plus human
unresolved/disposition state, notification idempotency keys, stage status/remaining attempt
budget, confirmation and first-stage-intent clock-epoch anchors, separate first/stage2
scheduled deadlines and their trusted-time mapping status, recipient stage and CRC. ID format is device-pseudonym /
committed boot-generation / monotonic incident counter; boot-generation is advanced and
committed before new durable incidents, so reboot cannot reuse IDs. If that commit fails,
restrict to visibly NON_DURABLE shadow scope and report an acceptance blocker.
Check set/commit/read errors and schema/CRC; this is not a multi-key atomic transaction
or tamper-proof journal.

A deferred storage adapter returns committed version to the owner; coalesce only with
version/ordering checks so a late confirmed snapshot cannot overwrite RESOLVED. Local
alarm intent is not blocked by flash; gateway dispatch of a persisted outbox requires
commit acknowledgment. Commit failure leaves DURABILITY_FAILED/local unresolved status
and explicit unsent remote intent, not pretend delivery. This can prevent remote sending
and is an acceptance blocker; do not silently waive it to claim scheduled cap compliance.
Measure storage task/heap/flash-operation impact under each declared B6 workload;
report HTTP/TCP profile results separately. Any extra adapter task
counts toward the same shared budget. Power loss before confirmation/outbox commit can
lose the newest incident: document this unavoidable uncommitted window and test it;
continuous safety during loss of power requires separate power/hardware design.

Restore the same committed incident/notification IDs after reboot; do not create a
second fall merely from boot. Reset source/clock epochs and evidence to UNKNOWN; do not
subtract pre-reboot `esp_timer_get_time()` values from new boot time. With trusted elapsed
mapping, preserve remaining deadlines from ORIGINAL anchors, not fresh boot timers. With
unknown downtime, pending stage1 is due immediately; if stage1 already exists and no
committed ACK/resolution exists, its uncreated stage2 is also conservatively due immediately,
not another60s after reboot/retry. Preserve ordering/IDs and record RESTORE_TIME_UNKNOWN.
Only when no stage1 ever existed does newly created restored stage1 establish a new actual
first-intent anchor; do not replace an existing anchor. Committed ACK suppresses unstarted
stage2; committed RESOLVED suppresses all new dispatch. Reconcile possibly sent intents
using gateway idempotency/status within the bounded worker timeout; inability to reconcile
marks DELIVERY_UNKNOWN with the persisted remaining-attempt budget. Never reset it on
reboot or claim exactly-once delivery. Storage/clock faults remain acceptance blockers.
A committed RESOLVED record restores as resolved/re-arm, not ALARM_ACTIVE. Suspected-only
volatile candidates are reported as lost/unknown after reboot, not confirmed retrospectively.

No automatic NVS erase/reformat or partition/security change on initialization error;
retain recoverable journal and expose storage fault. Disable deep-sleep entry while
monitoring/unresolved for the planned prototype; this is a separately authorized power
policy change, not current behavior. Espressif documents timer restart after deep sleep.
Follow D10/§5.5 calibration ownership: frozen candidate-to-resolution baseline, explicit
warmup/quality check on re-arm and recalibration after environment changes. Classifier
history, motion-cache, calibration, incident and notification resets have separate APIs.

#### 5.8.11 Diagnostic schema and auditable alarm trace

Add `schema_version`, `record_type` (OBSERVATION/CANDIDATE/TRANSITION/QUALITY/COMMAND/
INTENT/ATTEMPT/RECEIPT/ACK/RESOLUTION/PERSISTENCE/OVERFLOW/HEARTBEAT) and monotonic
`event_seq`. Required correlation: run/build/active-flash/model/policy/source hashes,
boot/source epochs, selected link, candidate/episode/incident/subevent/stage/notification/
attempt/command IDs. Source identity still does not prove flashed identity.

For transitions store from/to axes, trigger/reason, evidence IDs, threshold/config
version, valid/unknown duration, first candidate/confirmation/actual transition time,
named first-stage scheduled/actual-intent and stage2-anchor/deadline fields, suppression
reason and observed service lateness. Reference B6/B9 acquisition/truth/clock/QC hashes in
the run manifest, not runtime label input. For communications store local intent and
observable prompt delivery, user receipt/application, worker admit/start/end, endpoint
receipt, human ACK/resolution times and failures. Keep host receipt separately from
device availability; common clock/uncertainty is mandatory for cross-device latency.

Counters: CSI callback/capture/throttle/parser/admission/classifier/lifecycle/command/
intent/worker/telemetry losses; candidate accepted/expired/indeterminate/denied; confirmed
incidents/subevents/duplicates; prompt undelivered; attempts/timeouts/unknown/ACK; queue
high-water; clock regression, epoch change, persistence failures; tick/service lateness.
A proposed1Hz heartbeat reports current incident, health, pending deadlines and counts
even without CSI. Heartbeat loss marks monitor availability UNKNOWN, not incident resolved.

Full-fidelity diagnostic capture is deferred/bounded; transition/command records take
priority over optional high-rate observations, but counters disclose every omission.
Event trace overflow makes exact lifecycle reconstruction INCOMPLETE_TRACE; no "all
alarms handled" claim from a partial log. AL0/AL3 instrumentation/load controls must be
matched. Use existing §5.7 full-precision classifier trace for parity, not rounded UI scores.

#### 5.8.12 Validation scenarios, causal replay and fault injection

Extend A11 R0–R4, not production FSM checkpoint restoration. R1 runs complete chronological
streams plus explicit ticks/commands/mock results; R2 executes the identical pure-C core
and policy; R3-V verifies state/time boundaries, not CPU or RF; R3-P verifies1× real-device
service/queue/time with actual admission-conditioned references; R4 uses untouched live
mixed sessions. No synthetic pause extension proves observed180s real aftermath or user
perception. Keep derived faults owned by the original recording's split.

| Fixture ID | Required scenario | Exact assertion |
|---|---|---|
| H13 | Startup single gated FALL vs qualified2-of3 bundle; non-FALL at aftermath | AL2/AL3 difference named; AL3 single vote suspected only; complete bundle confirms without requiring continued FALL. |
| H14 | Stillness-only, near-fall/self-recovery, true impact then movement | Stillness never starts incident; real recovered fall retained; event/assistance metrics separate. |
| H15 | Tick-only dropout suspected, confirmed, grace, countdown and no ACK |3s suspected expiry and default stage1+40/stage2+100s occur without CSI; first cap applies stage1 only; unresolved incident/UNKNOWN duration retained |
| H16 | Time span/coverage/deadline boundaries, duplicate/old/out-of-order observations |−1µs/equal/+1µs; no double vote, time reversal or held-value coverage;0.7 fraction plus80% coverage tested independently. |
| H17 | HELP at IDLE/suspected/active/resolved; OK/denial/ACK/resolve; full queues; equal/late/replayed commands | Manual-help vs accepted-fall disposition preserved; role/scope/idempotency exact; HELP beats simultaneous cancel, ACK at stage2 due suppresses it, no retroactive unsend |
| H18 | Sustained FALL, release/re-fall, bursts/>4 subevents and AL6 first-cap80 | Candidate/first-intent/stage2 anchors immutable across re-fall/reconnect/update; default+40/+100 and extreme+80/+140 schedules; stage2_delay unchanged; bounded saturation/no blind refractory miss |
| H19 | Lifecycle queue/worker/telemetry flood, timer starvation, callback loss | Independent deadline service, exact separate loss counts, unknown support and INCOMPLETE_TRACE; no callback/network block. |
| H20 | Worker admission full, rejection/partial send/timeout/late receipt; ACK at deadline−1/equal/+1µs | Admission failure!=network attempt; at most3 admitted attempts/stage, unchanged intent ID; stage2 first-intent+60 even after stage1 failure, no first-cap clipping; exact ACK suppression/cancel race |
| H21 | Power cut around incident/stage/attempt/ACK/resolution commit; old/corrupt schema; known/unknown downtime | Restore same fall/help IDs, persisted attempt budgets and separate anchors; unknown-age pending stages due without fresh grace/stage2 delay; ACK/resolution preserved, uncommitted-loss window disclosed |
| H22 | Source/peer/channel/reconnect/calibration changes mid-incident | Evidence reset separate from incident; no adaptation contamination; PROD_LEGACY classifier control preserved. |
| H23 | Local prompt invisible/disconnected, caregiver absent, multi-occupant movement | UNKNOWN/PROMPT_UNDELIVERED instead of unconsciousness/no-response claim; no scene-motion automatic resolution. |
| H24 | Session end before confirmation/dispatch/ACK; annotation and future-data perturbations | Censor endpoints, retain event denominator; no invented response, long monitoring or inference access to future/truth. |

Run thresholds/durations exactly from frozen policy; add property tests for invariants,
random event sequences, integer overflow/saturation, empty/constant evidence and policy
validation. Changing only future CSI/commands must leave earlier outputs unchanged.
Invalid policy (negative/overflowing timeout, quiet>=move, impossible deadline order,
unknown schema) fails initialization with feature disabled and explicit fault, not guessed
defaults. Compare Python/C state, reason, intent IDs/deadlines/counters exactly; preserve
§5.5 float32 tolerance only for numerical feature/summary calculations. Skipped gcc or
missing Motion/persistence clock support does not pass the corresponding tier.

#### 5.8.13 Metrics, matching, denominators and selection gates

Keep §5.7 detector matching window [reviewed_start−0.3s,impact+1.0s) and raw/voted/gated
episode metrics unchanged. Link each confirmed incident to its candidate onset and
recorded evidence bundle, THEN to the original annotated event; confirmation/notification
may occur after the D1 detection interval. Do not search an enlarged alarm window until
a false late episode becomes a hit. A candidate matches one physical event once;
independent subevents have separate physical-event matches, but one operational incident
or three sends are not three detected falls. Post-fall unknown truth stays separately
listed, not silently converted to negative exposure.

| Metric | Computation / denominator |
|---|---|
| Candidate/detector recall | Matched eligible candidate onsets / ALL held-out annotated physical events; retain misses from invalid data/startup/loss. |
| Confirmation precision | Confirmed physical-event records matched to reviewed falls / all confirmed physical-event records with fully annotated truth; user denial and unknown truth separate. |
| Conditional confirmation sensitivity | Matched fall candidates confirmed / all matched fall candidates, including indeterminate/expired cases; report both cases and reasons. |
| End-to-end confirmed recall | Annotated events whose matched candidate becomes accepted / ALL held-out events; immediate recovery remains a fall. Censored confirmations listed, no denominator shrink. |
| Negative-candidate nonconfirmation / false confirmation | Reviewed negative candidates not accepted /all reviewed negative candidates; split explicit predicate rejection, indeterminate/expiry, denial and censoring. Accepted negatives/all reviewed negatives is false-confirmation rate; missing evidence is not verified rejection; zero denominator NA |
| Confirmation confusion / accuracy | Candidate truth FALL/NON_FALL crossed with ACCEPTED/EXPLICITLY_REJECTED/INDETERMINATE/USER_DENIED/CENSORED; abstention separately. Reviewed FALL not accepted remains an unconditional FN; denial/quality insufficiency is not verified rejection. Binary accuracy/P/R/F1/specificity/balanced/MCC on explicitly decided subset is conditional, with subset coverage and all-candidate recall |
| Aftermath assessment | Per reviewed bin/episode LOW_MOTION/MOVEMENT/MIXED/UNKNOWN confusion and valid-time coverage; observed scene motion vs victim recovery labels separate. No unconsciousness-accuracy claim. |
| Assistance / escalation | HELP intent fulfillment: accepted HELP commands producing same-incident urgent stage1/update /all authorized admitted HELP commands; also receipt-to-intent delay and admission failures. Simulated-need coverage: B9 preassigned help-required scenarios with first remote intent by their frozen policy due time /all such scenarios, including unavailable detector cases; stage2 due fulfillment separately. Not measured clinical need |
| Local/remote FA/hour | Reviewed false detected-fall incidents with local/stage1 intent /B9 H_negative, separately. Attribute by the originating candidate onset in reviewed NON_FALL exposure, even if delayed intent occurs later/in a censored follow-up; delayed receipt never changes truth attribution. Count once per incident/endpoint; manual HELP, UNKNOWN incidents, updates/stages/retries and user overrides are separate burden; also H_negative_valid and censored endpoint counts |
| Latency decomposition | Available candidate−start/impact; confirmation−candidate; local intent and observable delivery−confirmation; remote intent−confirmation/candidate; receipt−intent; ACK−receipt; resolution−candidate. Report median/P95/P99/max, matched count, early negative offsets, clock/observer uncertainty and censored failures. |
| Deadline / availability | Stage1 actual-intent−first_due and stage2 actual-intent−stage2_due reported separately with cap/ACK-suppressed/failed/censored counts; no-input expiry lateness, confirmation coverage, UNKNOWN time/warmup/re-arm delay; a dead detector cannot win with0 FA |
| Delivery reliability / burden | Per stage: attempts/created intents, verified receipts/created intents and authenticated ACK/created intents; count terminal received/failed/unknown/cancelled/censored separately. No denominator shrink from unsent/durability failure. Conditional fully-followed rates labeled; stages/updates/prompts/cancel races/unresolved duration separate. Receipt!=ACK |
| Resources / resilience | Additional AND absolute live RAM/stack/heap/flash, CPU per frame/decision/tick, queue high-water/loss, watchdog/reboots, acquisition-rate drift, storage overhead and trace completeness. |

Censored confirmation/follow-up is not an observed permanent miss: unconditional
observed-success recall keeps its full denominator, with censored unresolved cases and
best/worst outcome bounds separately. No exclusion can improve it. EXPLICITLY_REJECTED
means a named policy predicate failed on sufficient evidence (e.g. AL4 stillness), not
AL3's insufficient/expired evidence. Denial of an already accepted event is a separate
human-disposition field, never a second mutually exclusive classifier outcome.
Freeze simulated assistance endpoints and due-time expectations from the policy and
preassigned script actions before replay. A scenario where the detector never accepts
has unmet end-to-end assistance intent, not an omitted case with no deadline. Scripted
expectations are not clinical safety limits; confirmation/intent/receipt/ACK success
and failures are reported independently. All binary formulas follow §5.7.7.

Ground truth: B8 collection uses B9 versioned physical event/interval/action labels,
independent two-reviewer/third-adjudicator QC, clock bounds and full exposure partitioning.
Scene motion and victim recovery/position, prompt availability/perception, human actions
and SIMULATED assistance truth remain separate. Runtime sees none of these annotations.
Existing post-fall4s and cue labels cannot establish30–60s
response outcomes or clinical incapacitation; those results remain BLOCKED_POSTFALL_TRUTH.

Freeze policy/threshold/grace selection in grouped inner DEVELOPMENT data under A10;
report all predeclared outer results and reserve new complete sessions/users as supported.
Use natural prevalence and per-subtype/day/subject/quality/occupancy strata. Paired replay
uses the SAME input/exogenous commands/mock-delivery traces; replay repetitions/seeds are
not new people or exposure. Fixed-timestamp human-response replay is an open-loop mechanical
comparison, not proof that the same person responds identically to different prompts.
Prompt-relative scripted responses need separately named causal scenarios; actual user
perception/response comparisons need B8/B9 supervised observations and untouched groups.
Bootstrap whole sessions/subjects where supported (§5.7), report independent
cluster counts and uncertainty; short-take diagnostics cannot establish deployment FA/hour.
For zero false alarms use the stated-assumption rate bound−ln(0.05)/H, not zero risk.

Provisional engineering acceptance: all invariants/fixtures pass; exact state/intent
Python-C parity; no unbounded suspected/response/worker state; confirmed incidents survive
no-input/reset/committed restore; complete stage telemetry and explicit failures; shared
§5.7 budgets (additional peak live RAM<=4KiB, incremental complete-pipeline CPU<=2.9ms/frame,
decision P99<=50ms, event coverage>=95%, no incremental classifier queue loss) hold under
matched B6 acquisition-profile loads, reporting HTTP/TCP separately. These ceilings
are aggregate across selected features/model/lifecycle,
NOT4KiB extra for each subsystem. Include owner stack/queues/journal/deferred adapters/
instrumentation and timestamp overhead; propose a compact owner stack budget<=1536 bytes
but measure stack high-water and margin before enabling. If the aggregate does not fit,
reduce optional diagnostics or stop at host prototype; do not silently waive the gate.

Event selection safeguard (PROPOSED): on each fully annotated reserved evaluation set,
AL3 must not discard any true fall AL2 accepted merely because aftermath is moving;
report every new qualification miss and abstention. No ranking based only on fewer alerts:
compare confirmed recall, false confirmations/FA burden, response latency and availability
jointly. A clinically tolerable miss/FA/latency requirement is NOT established here;
research gates and source literature are insufficient for a safety deployment claim.

#### 5.8.14 Human factors, privacy, operational boundaries and rollout

B8 uses witnessed safe simulations with consent; never induce unconsciousness, prolonged
unsafe lying, unsafe falls or withhold real assistance to evaluate an alarm timer. Use
scenario instructions as simulated-assistance labels, not medical diagnosis. Choose an
intended population/use environment and validate hearing/visibility/reachability, HELP/
OK/denial wording, confusion with ACK/RESOLVE, countdown comprehension and accidental
cancel. Real responders and emergency escalation require separately reviewed procedures.
An LED or host browser is not automatically reachable by an injured person.

Minimize exported CSI/person-linked data and recipient details; use pseudonymous run/
incident/link IDs. Proposed research trace retention30days on consented host storage,
terminal device record retention until next incident or operator archive, and unresolved-
record retention without expiry until explicit disposition. Device storage is bounded:
one current journal/last disposition, not unlimited history; host archive retains ordered
terminal records. If host/trace export is unavailable, expose older terminal-history loss
before replacing the bounded record; never block detection or discard an unresolved record.
Retention values are proposed; confirm consent/access/backup/deletion policy before
collection. Do not log credentials,
medical claims, raw remote secrets or personally identifying notification content.
Raw serial controls are lab-only; gateway authentication/authorization/idempotency and
privacy review are gates for external service, not changes performed by this plan.

Rollout stages: feature OFF → host-only core/fake sink → authorized on-device SHADOW_ONLY
under matched load → supervised local experimental prompt → separately authorized test
gateway/recipient pilot. No automatic production/emergency-service release. Rollback
selects the verified prior model/pipeline and disables NEW candidate generation, while
showing/preserving unresolved incident and pending gateway reconciliation; turning the
feature off must not silently dismiss an existing alert. Recovery/build/flash identity
and backups follow project preflight; no installation/flash/commit is done here.

#### 5.8.15 Step-by-step implementation milestones, artifacts and completion

| Milestone / owner track | Concrete planned output | Dependency / exit condition |
|---|---|---|
| PF0: A12 contract audit | Frozen AL0/AL2 identity, state/command/policy schema, separate first/stage2 anchors, observation/loss/literature hashes | Contract freeze enables PF1 synthetic mechanics; A10/A11 R0 source/split audit gates recorded input, not a fictitious prerequisite to write a pure synthetic core |
| PF1: A12 host core | Python reference, pure-C FSM and host binding, fake clock/sink/storage/user-command adapters | H13–H24/invariants and exact state/intent/deadline parity; no fitting/device build/runtime integration needed for synthetic mechanics. Any added firmware-source code still obeys project preflight. |
| PF2: A12 replay / ablations | AL2/AL3 full-stream replay, conditional AL4/AL5, AL6 one-factor table | PF1 parity + A10/A11 R0/R1/frozen model/labels; real aftermath/response requires PF3 B8/B9 truth and training-owned calibration. Synthetic tests do not wait for main collection |
| PF3: B8/B9 acquisition/truth | Complete long aftermath/response and hard-negative sessions; immutable raw/reviewed/adjudicated truth/QC/clock artifacts | B9 protocol/safe pilot and B6 verified mode-specific acquisition profile; whole groups reserved before tuning. Collection may overlap PF1; real PF2 rankings wait for reviewed truth |
| PF4: C8 firmware observation integration | Timestamped observations; bounded owner/core, default-OFF SHADOW_ONLY; build/schema identity | PF1 parity + C7 adapter/identity/R3 readiness, separate approval/v5.5.3 preflight/change log; AL0 regression intact; C7 R4 not required before integration |
| PF5: C8 resilience / diagnostic integration | Independent deadline service, journal/restore, command/results, versioned incident UI/recorder, fake gateway | H13–H24 at R3-V/R3-P; full losses/latency/storage/ACK/restore trace; browser test of implemented UI. |
| PF6: C8 resource / live confirmation | Matched B6 HTTP/TCP workload profiles, same unified model, authorized R4 reserved groups, lifecycle report | PF5/C7 device gates and B8/B9 signed truth/clock/exposure QC; frozen development artifact/policy before test access, shared budgets/full trace; live events not falsely paired |
| PF7: separate operational approval | Usability/risk/privacy/security review, supervised local/test-recipient protocol, rollback exercise | Not an automatic consequence of research success; emergency service integration/deployment remains out of scope. |

At any firmware milestone read `docs/agent-preflight.md`, open version-matched official
Timer/FreeRTOS/NVS and any affected API documentation BEFORE runtime edits, provide
Document + Quotation evidence, update `docs/agent-changes.md`, and include applicable
`Docs:` commit trailers if a commit is separately requested. Existing unrelated changes
are not baseline evidence to overwrite. Existing valid unit command is §5.4.3's
`python3 -m unittest discover -s fall_detection/tests -v`; new runners do not exist yet,
so no fabricated runnable CLI/campaign command is provided. Do not install dependencies,
train, build, flash, send alerts, alter the radio or commit during this documentation task.

Store planned outputs alongside A11 runs, e.g. `reports/evaluation/<UTC_run_id>/`:
`alarm_policy.json`, `alarm_manifest.json`, `observations.jsonl`, `incidents.csv`,
`subevents.csv`, `aftermath_bins.csv`, `commands.jsonl`, `notifications.csv`,
`persistence_trace.jsonl`, `alarm_metrics.json`, `alarm_parity.json`, `alarm_resources.json`
and `alarm_tests.json`; reuse existing build/capture/split/clock/exposure manifests.
Each result lists policy/control/data/code/source hashes, R tier, actual executing image,
truth denominators, missed/censored events, all scheduled tests and blockers. Resume only
matching manifests. Append decisions/evidence to §9, not a second plan.

| Track / planned row | Present status | Required future evidence |
|---|---|---|
| AL0/AL2 lifecycle-wrapper control | NOT_RUN | Reproduced detector/episode control and fake-sink trace; AL0 itself has no real notification service. |
| AL3 recommended fixed-grace prototype | NOT_IMPLEMENTED / NOT_RUN | Pure-C/Python mechanics, qualified evidence, bounded timers, stage metrics and authorized resource/live tests. |
| AL4/AL5 real aftermath confirmation/scheduling | BLOCKED_AFTERMATH_CALIBRATION / BLOCKED_POSTFALL_TRUTH | B8/B9 reviewed continuous truth/clock/exposure QC and training-owned thresholds; synthetic FSM tests possible after authorization |
| AL6 sensitivity / AL8 resilience | NOT_RUN | Frozen one-factor protocol, all faults/results and explicit unresolved/failed outcomes. |
| AL7 additional sensor fusion | BLOCKED_EXTRA_SENSOR | Separate scoped design, hardware/model validation, resources/privacy/identity; not required for AL3. |
| C8 device/UI/gateway pilot | NOT_RUN / NOT_AUTHORIZED | Preflight/identity, R3 timing/parity/queues, browser usability and separately authorized reserved R4. |
| Clinical unconsciousness detection / emergency release | OUT_OF_SCOPE / NOT_VALIDATED | Current CSI cannot support this claim; no medical or external-call deployment approval. |

A12 completes with contract/core/replay/fixture/parity outputs or itemized blockers, not
with synthetic mechanics mislabeled as validated aftermath. C8 completes only with
separately authorized instrumented device tests and reserved live evidence for every
claimed boundary; required blocked tests keep acceptance incomplete. Retain AL2/legacy
control if AL3 evidence is inconclusive, and keep all notification sinks non-emergency.

#### 5.8.16 References and exact provenance boundaries

- PF-R1: [SiFall, primary text](https://arxiv.org/html/2301.03773v2): segmentation/classification/human review; not a WROOM confirmation timer benchmark.
- PF-R2: [IMU and smartphone Wi-Fi CSI two-stage fall detection](https://arxiv.org/html/2412.09980v1), §II-D:3s/30 samples at10Hz, two antennas; task focuses non-self-recoverable falls.
- PF-R3: [TCS-Fall](https://pmc.ncbi.nlm.nih.gov/articles/PMC11151769/):8s/1s windows and warning evaluation; no inferred acknowledgment lifecycle.
- PF-R4: csi-pose [FSM source](https://github.com/sel00000/csi-pose/blob/main/rt/csi_rt/fall.py), [config](https://github.com/sel00000/csi-pose/blob/main/configs/rt.yaml), [project limitations](https://github.com/sel00000/csi-pose): pose+CSI demo, CSI stillness disabled in inspected configuration; supplied durations belong to that demo.
- PF-R5: ElderCare [two-stage checker](https://github.com/dungnotnull/wifi-sensing-based-elderlycare-deeplearning/blob/main/models/fall_detection/model.py): inspected code does not enforce the advertised3s interval.
- PF-R6: ElderCare [post-fall checker](https://github.com/dungnotnull/wifi-sensing-based-elderlycare-deeplearning/blob/main/models/activity/detector.py) and [pipeline integration](https://github.com/dungnotnull/wifi-sensing-based-elderlycare-deeplearning/blob/main/pipeline/inference_engine.py): distinguish30s check and initial/post-event alerts.
- PF-R7: ElderCare [alert manager](https://github.com/dungnotnull/wifi-sensing-based-elderlycare-deeplearning/blob/main/alerts/alert_manager.py): cooldown/retry/API-return behavior, not end-to-end caregiver acknowledgment.
- PF-R8: [Wearable/robot/vision assisted confirmation](https://arxiv.org/html/2507.10474v1): heterogeneous verification, not CSI-only or same-hardware comparison.
- PF-R9: [Apple Fall Detection support](https://support.apple.com/en-us/108896): immediate prompt, about1min immobility and30s countdown, cancellation/connectivity limits; not proposed profile timings.
- PF-R10: [Google Pixel Watch fall-detection workflow,2023](https://blog.google/products-and-platforms/devices/pixel/fall-detection-on-pixel-watch/): dated comparable product behavior, not current WROOM evidence.
- PF-R11: [FDA: Applying Human Factors and Usability Engineering to Medical Devices](https://www.fda.gov/regulatory-information/search-fda-guidance-documents/applying-human-factors-and-usability-engineering-medical-devices): intended-use interaction/risk principles; no medical approval claim.
- PF-R12: [ESP Timer, ESP-IDF v5.5.3/ESP32](https://docs.espressif.com/projects/esp-idf/en/v5.5.3/esp32/api-reference/system/esp_timer.html): "The execution of callbacks in the ESP Timer task is serialized"; "it is recommended to keep the callbacks short"; deep-sleep timer restart. [FreeRTOS reference for the same version/target](https://docs.espressif.com/projects/esp-idf/en/v5.5.3/esp32/api-reference/system/freertos_idf.html) remains the required implementation reference for queues/tasks/tick conversion.
- PF-R13: [NVS, ESP-IDF v5.5.3/ESP32](https://docs.espressif.com/projects/esp-idf/en/v5.5.3/esp32/api-reference/storage/nvs_flash.html), security/robustness discussion: power-off recovery excludes a new key-value pair being written at power-off; therefore no promise that an uncommitted newest incident survives.

---

## 6. Rencana kerja

### Execution dependencies (task IDs are not chronological order)

Preserve the A/B/C identifiers below; this readiness order governs execution. Apart from
the subsequently authorized, completed development-only annotation study (§5.2.2), new
implementation/campaigns remain NOT_RUN and require separate authorization. Contract
writing and collection preparation may proceed in parallel AFTER approval; blocked
outcomes are not passes. §8.1 still blocks detector splits/manifests, training, ablations
and promotion of annotation proposals; this study does not complete the gates below.

| Gate | Required order / exit evidence | Work enabled |
|---|---|---|
| APPROVAL: present stop | User accepts §2.6/§5.6.7 audit and resolves §8.1 execution choices | Only the explicitly approved next scope; this update creates no manifests/experiments |
| RDEP0: contracts | Unified D18/take-based D5, primary manual-first A2/D1 eligibility, optional A13/A14 scope, B6 profile provenance, B9 truth/uncertainty, §5.7 metrics and §5.8 deadlines | Approved audit/tooling preparation, not fitting or unreviewed collection |
| RDEP1: ownership | A2 eligibility tests → A10 immutable all-take/verified-lineage ownership and separate label eligibility, approved outer/inner/reserved manifests and class-feasibility audit | Prepare A1/A13/A11 and optional A14 donor ownership; no identity-based global exclusion; fits wait for RDEP2 |
| RDEP2: causal evaluation | A11 R0 capture/clock/loss audit and tested R1 full-stream/stage/episode/coverage metrics; synchronized Motion required only for gated claims | A1 diagnostic fits, A13 inner sensitivity, A3 and primary-label A6/A8 branches with tested operators |
| RDEP3: conditional operators | A7 tested PLAN_GAP05 invalidation before any gap-policy branch; A4 timestamp/support/grid tests before time-window branches; required A8 schema/tests before corresponding A9 representation branch | Supported A6/A8 screens and A9 models/training; unsupported branches stay blocked |
| RDEP4: lifecycle core | A12/PF0 frozen state/deadline/command contracts → PF1 synthetic Python/C core/fake-sink parity; recorded PF2 needs A10/A11 R0/R1 | Synthetic mechanics may precede B8; real aftermath/response rankings wait for B8/B9 and training-owned calibration |
| RDEP5: new collection | B9 reviewed protocol, consent/safe supervision and B6 identity verified; B1/B3 clock/metadata pilot passes; reserve whole groups before any tuning | B2–B8 mixed/long-aftermath/continuous-negative development and sealed confirmation collection |
| RDEP6: offline decision | Supported A6/A8/A9/A12 results; A5 interim report with blockers; select/refit on DEVELOPMENT only, retaining old controls; R2 parity for matched F0 and at most2 C-supported finalists | Authorized C7 device replay/resource verification, not deployment |
| RDEP7: device lifecycle | C7 adapter/identity/R3-V/R3-P timing and resource readiness + A12 core parity → authorized C8/PF4–PF5 integration | Matched lifecycle device/fault tests; not a claim that all of C7 R4 must precede C8 |
| RDEP8: untouched acceptance | Freeze final build/model/policy before opening reserved groups; complete B8/B9 truth/QC and C7/C8 device gates → reserved offline confirmation and authorized untouched R4/PF6 | Final A5 report; no tuning on confirmation failures; PF7 operational approval remains separate |

A13 or A14 completion is not a prerequisite for frozen-primary A6/A8 screening.
Their alternate/assisted labels never silently replace A2. A14 parameter/confidence
experiments require A10 donor/recipient ownership and A11 R0 clock/quality evidence;
A11 R1 is additionally required for any approved downstream detector comparison. A9 depends on required operator/schema readiness, not
on completing every catalog experiment. Collection can overlap offline tooling once its
own safety/truth/identity gates pass. Interim A5 may precede device tests but cannot claim
measured device acceptance; append that evidence only after C7/C8 and reserved confirmation.

### Fase A — Data yang sudah ada (tanpa rekam ulang, offline)

#### A1 — Baseline lintas hari

- **Goal:** diagnose cross-day robustness and confounding, not estimate a causal
  percentage of the score attributable to day rather than motion.
- **Current behavior:** default take grouping does not require subject/session IDs;
  only requested identity grouping raises missing-ID errors. Current audit:85 unknown-ID
  takes,65 primary D1 candidates;20 FALL restricted by missing labels, not identity.
  Preserve the raw reused session ID and report A10 provenance/independence limits.
- **Langkah:**
  1. Tambah opsi grup `day` (turunan `started_at_utc[:10]`) tanpa mengisi ID
     palsu.
  2. After A2/A10 ownership and A11 R0/R1 readiness, run separate primary-A2
     and identified legacy-policy take/day diagnostics using frozen manifests.
     Do not call an unsupported future group/manifest interface already installed.
  3. Use §5.6.7's unified E2a–E2d arithmetic: holding out11-07 now leaves39
     annotated FALL candidates. Check actual windows before fitting; same-axis
     three-inner-day selection remains unsupported. Legacy results stay separate.
- **Limitations:** four primary days, two annotated-FALL days and TCP only on11-19;
  profile/day/class confounding remains. Take-inner selection cannot claim session
  independence. No new split or fit is authorized by this audit.
- **Completion:** take/day diagnostics and class/exclusion support are reported;
  negative-only metrics use NA for FALL recall, blocked folds retain reasons.
  Record A2 vs legacy policy separately; use A10 manifests, not inferred identities.

#### A2 — Kebijakan label baru

- **Langkah:**
  1. Buat policy baru (file terpisah, policy lama tidak dihapus), misalnya
     `fall_detection/phase_label_policy_annotated.json`.
  2. FALL = `annotation_intervals` `fall_start − 0,3 s` →
     `fall_impact + 1,0 s` (D1).
  3. Setelah `fall_impact + 1,0 s` → `post_fall`, dikeluarkan dari training
     biner (D2).
  4. Post `fall_keseleo` dikeluarkan.
  5. Primary manual-first training excludes whole FALL takes with incomplete
     boundaries, not unknown identities. Keep all232 in inventory; A14 proposals
     remain separate with per-boundary provenance, never silently promoted to manual truth.
  6. Cek dukungan margin di `_annotation_intervals`; tambah jika belum ada,
     beserta test di `fall_detection/tests/`.
- Completion: freeze/hash the half-open primary policy and eligibility tests; report
  window counts, exclusions, boundary support and annotation uncertainty. Never clip
  or pad unsupported training windows. A13 variants remain separately identified.

#### A3 — Any-alarm take diagnostics for unannotated falls

- Replay complete held-out takes through A11; ask whether any stabilized alarm
  occurred. Report raw and gated stages separately where inputs are available.
- Count negative takes with alarms and episode counts, without joining short takes.
- Completion: any-alarm FALL-take recall and NON_FALL-take alarm proportion, with
  coverage and actual snapshot counts. These are not annotated timed event recall,
  onset latency or continuous deployment FA/hour (§5.7).

#### A4 — Window berbasis waktu

- Implement time windows only after A2 labels, A10 splits and A11 R0/R1 support/clock
  contracts; coordinate with A7 gap tests. Label margins stay fixed here (A13 owns them).
- Grid: durasi 1 / 2 / 3 s × stride 0,4 / 0,5 s.
- Keep the exact 16-delta baseline fixed here; feature changes are isolated in A8.
- First validate trailing support, logical grid, minimum frames, gap invalidation
  and actual decision availability. Then compare durations/strides with frozen labels,
  choosing only inside training-owned folds; outer scores are reports, not selectors.
- Completion: causal/window tests and per-configuration coverage, latency and results
  or explicit blockers. Host/source-time latency is not measured device latency.

#### A6 — Ablasi preprocessing lengkap di pipeline resmi

- Katalog kandidat, prasyarat, tahapan, dan kriteria penilaian ada di §7.
- Mandatory before fitting: frozen A2 labels, A10 ownership/manifests, A1 scheme
  feasibility and A11 R0/R1 common causal metrics. Start W24/12; A4 gates time branches,
  A7 gates PLAN_GAP05 branches. Missing Motion blocks gated claims only.
- Completion: supported offline stages and identified project-classifier results,
  nested training-owned choices or explicitly exploratory historical shortlists.
  R2 parity gates C-supported finalists; C7 supplies authorized measured device costs.
  Final confirmation waits for untouched Fase B groups, not outer-test optimization.

#### A7 — Invalidasi window dengan gap

- Audit gaps under A10/A11; implement/test gap>0.5s and declared source/invalidity
  resets before PLAN_GAP05 W24 or time-window comparisons. Keep PROD_LEGACY distinct.
- Report invalidated support per class, all-event denominators, coverage and metrics.
  A7 tooling may run alongside A4; A4 is not required for a W24 gap-policy branch.

#### A8 — Controlled representation and feature ablation

- Follow §5.4.1–§5.4.6 after A2/A10 ownership, A1 feasibility and A11 R0/R1 metrics;
  A7 must support the catalog's PLAN_GAP05 control, A4 the W1/W2/W3 branches. This is a specification,
  not authorization to start training or deploy during the documentation update.
- Freeze preprocessing/model first; compare feature blocks separately, then
  check finalist interactions with A6. No new firmware or training run yet.
- Version feature dimensions/semantics across trainer, artifact, exporter,
  Python/C extractor, and tests. Reuse overlapping P3/P5/P10 experiments.
- Completion: a current-snapshot comparison with coverage, per-activity alarms,
  event recall, latency, uncertainty, and measured finalist deployment costs.

#### A9 — Model, training, representation interactions and combinations

- Follow §5.5.1–§5.5.11 after A2/A10 ownership, A1 feasibility, A11 R0/R1 metrics
  and branch-specific A4/A7/A8 operator/schema tests. A8's entire campaign need not
  finish first; its frozen feature contract remains distinct from A9 model/training.
- Compare M0–M24, T strategies, structural representation sentinels and bounded
  S/C combinations with natural-prevalence tests and fold-local learned state.
- Implement/pilot only after separate execution authorization; this update writes
  the plan only. No dependency installation, campaign, build or flash now.
- Complete only with explicit statuses, nested ownership, full event replay,
  window/event/coverage metrics, Python/C parity, peak device costs and a decision
  distinguishing exploratory evidence, confirmation and hardware eligibility.

#### A10 — Shared split manifests and leakage-resistant evaluation

- Implement §5.6 safeguards after A2 eligibility is defined; use the audit to plan
  A1 day diagnostics. Complete shared split support before A6/A8/A9 fitting, without
  retroactively changing Table4's frozen feature/model contract.
- Preserve raw unknown/conflicting IDs; add provenance-qualified resolution, day
  audit grouping, original-take/verified-lineage ownership and separate eligibility
  views. Include acquisition-profile provenance, pooled/stratified support and
  independent split/model seeds; preserve canonical default regression tests.
- Freeze ownership for all232 takes before optional A14 donor selection; labels
  becoming available cannot trigger favorable reassignment or hidden fold changes.
- Enforce fold-owned transforms/caches, nested selection and reserved-test isolation;
  correct undefined-test-class metrics to NA and report per-scheme exclusions.
- Audit available groups/classes before choosing K; unsupported day/subject inner
  folds remain blocked. Collect more mixed groups rather than dilute independence.
- Completion per §5.6.6: reproducible manifests/tests, results or explicit blockers
  and conclusions scoped to actual independent axes. All work NOT_RUN; this edit
  authorizes documentation only, not implementation or experiment execution.

#### A11 — Complete causal replay and shared evaluation contracts

- Implement §5.7 R0/R1 after A2/A10 policies/ownership are audited; tested common
  metrics precede A3/A6/A8/A9 fitting/replay. Supply R2 production-C parity later for
  matched F0 and at most2 C-supported deployment finalists, not every Python screen.
  Preserve PROD_LEGACY and PLAN_GAP05 and existing Table4/5 candidate contracts.
- Supply full-stream state/Motion/clock/episode/coverage tests to A3/A6/A8/A9; no
  future input, label-controlled reset, hidden capture loss or undefined-metric0.
- Completion: shared manifests, scenario fixtures, host C numerical/state parity,
  full-record traces and rigorous metrics or named blockers (§5.7.9).
- Report pooled and per-acquisition-profile/day/subtype coverage and stage metrics.
  Manual observer truth, independently verified boundaries and assisted-label diagnostics
  have separate provenance/denominators. Missing profile fields do not erase the take.
- All implementation work NOT_RUN. A11 is offline; device adapter/build/flash/live execution is
  the separate C7 task and needs authorization/preflight, not this document edit.

#### A12 — Post-fall incident/alarm core and causal validation

- Implement §5.8 PF0–PF2 offline after separate authorization; reuse A10/A11 ownership,
  clocks, replay and detector controls. Pure-C/Python mechanics can precede new recordings;
  real long-afterevent/response assessment requires B8/B9 reviewed truth and cannot
  be invented from4s POST. PF1 synthetic tests start after PF0 contracts; PF2 recorded
  comparisons require A10/A11 R0/R1, while real AL4/AL5 wait for calibration as well.
- Freeze event qualification separately from aftermath thresholds/response grace; AL2/AL3
  primary comparison does not retrain or alter the selected acquisition/model/voter/gate.
- Supply bounded no-input timers, human command/sink/storage mocks, H13–H24 invariants,
  exact state/intent parity and separate event/assistance/delivery/exposure metrics.
- Completion per §5.8.15: identifiable outputs/tests and explicit blockers; all new work
  NOT_IMPLEMENTED/NOT_RUN. Firmware/real UI/notification/device execution is separate C8.

#### A13 — Training-owned annotation-margin sensitivity

- `lead` is seconds subtracted from reviewed start; `tail` is seconds added to impact.
  Every policy is [start−lead,impact+tail), with strict source-support containment.
- Freeze the primary A2 lead/tail at0.3s/1.0s. Proposed one-factor grid (seconds):
  lead0/0.3/0.5 with tail1.0; tail0.5/1.0/1.5 with lead0.3 (5 unique policies).
  These are estimates to test, not optima. Hash every policy and derived-label manifest.
- Prerequisites: A2 interval/boundary tests, A10 ownership/feasibility and A11 R0/R1
  causal metrics. Use eligible annotated FALL and NON_FALL TRAINING groups for fits/inner
  selection; no unannotated-fall pre/post frames, outer/reserved truth or test-fitted
  calibration enters fitting/selection. Original group assignments are identical across policies.
- Hold F0, W24/12, preprocessing/reset mode, model/training settings, seeds and original
  group assignments fixed. Strict raw-support containment applies to each policy;
  report changed class/window counts, lost support and ambiguity rather than padding.
- Score all variants with the SAME frozen primary-D1 event-matching interval and reviewed
  physical truth; do not enlarge the matching window to make a wider label policy win.
  Window metrics depend on label eligibility and are secondary, not directly comparable
  accuracy evidence for a better detector. Include common-support window diagnostics.
- Predeclare inner selection as highest annotated event recall, then fewer negative-take
  alarms, then primary-policy preference; remaining ties use smallest absolute lead/tail
  distance to primary, then lower lead, then lower tail. Unsupported inner objectives
  are BLOCKED, not replaced by outer-test choices. Real continuous FA/hour is used only with B5/B9 truth.
- Outer results may report all predeclared policies as sensitivity, never select the final
  margins. Keep A2 primary for Table4/5/7 controls; promoting an alternative requires an
  explicitly versioned development-only decision and new untouched confirmation groups.
- Completion: policy/grid/ownership hashes, boundary tests, paired inner/outer tables,
  per-event misses/coverage/latency and blocked folds. A5 summarizes A13; A4 is not its owner.
  All work NOT_RUN; historical observer/source and cue policies remain separate controls.

#### A14 — Optional assisted-annotation investigation

- Design assessment COMPLETE in §5.2.1. The user subsequently authorized automatic
  annotations: offline implementation, masked-observer diagnostics,20 proposals and
  2 abstention sidecars COMPLETE; artifacts and measured errors in §5.2.2.
  This scoped development study does not complete the training-ready A14 gates below.
  Proposals remain DEVELOPMENT_ONLY, UNCALIBRATED, NOT_REVIEWED and training-ineligible;
  original recordings/manual marks stay unchanged. No detector split is created.
  Full fold-owned validation, numeric acceptance and independent verification remain
  PENDING; this authorization does not waive their dependencies.
- Investigate22 incomplete FALL takes using same-subtype complete candidates; compare
  rigid lag, constrained multivariate DTW and multiple-donor consensus. Use time-aware
  support, quality/ambiguity rejection and per-profile diagnostics; never copy timestamps.
- Dependencies: approved tolerances/label use (§8.1), A10 original-take/lineage donor
  ownership, A11 R0 clock/capture checks and synthetic alignment fixtures. No test-owned
  donors or target hidden truth in fitting/calibration; keep existing manual marks.
- Run masked-boundary validation only after approval, reporting boundary errors,
  coverage/error trade-off, abstention and donor bias by subtype/profile/day.
  Independent verification follows B9; CSI-only review is not independent ground truth.
- Future outputs: immutable proposal sidecars, per-boundary provenance, donor/path and
  calibration identities, validation/review/rejection tables and explicit evidence limits.
  No original metadata overwrite, automatic primary-eligibility promotion or fold reshuffle.
- Completion means an evidence-backed accept/reject/abstain recommendation, not a
  requirement to fill every missing label. Primary manual-first work can proceed
  independently after its own approval/gates; weak-label training needs separate approval.

#### A5 — Laporan keputusan

Compare legacy policy/source controls, A2, A2+A4, +A6, +A8 and separate +A9
model/training/combination results. Use supported take/day schemes, nested selection
and new session/subject holdouts where valid; blocked folds remain visible.
A10 supplies split/exclusion manifests and independence claims for each row;
A11 supplies §5.7's complete-stream, stage/clock/fidelity and metric contracts.
A12 supplies §5.8's separate candidate/confirmed-event/assistance/notification lifecycle
report; detector ranking is not alarm-service success, and human OK does not erase a fall.
A13 supplies separately hashed, training-owned label sensitivity, not an A4/A5 margin
search. B9 supplies reviewed truth/uncertainty and complete exposure disposition for new
recordings. Publish interim offline and final device/untouched-confirmation A5 reports
separately; unresolved prerequisites remain blockers, never implicit completion.
Changing the split answers a different question, not an automatic model improvement.
Never attribute multiple changed factors to one model or pool distinct label policies.

| Metrik | Keterangan |
|---|---|
| Macro-F1 window | OOF |
| Recall / presisi FALL window | OOF |
| Annotated event recall | One-to-one new onsets inside the allowed interval /all held-out annotated falls |
| Take alarm diagnostics | Any-alarm recall for unannotated falls; negative-take alarm proportion, not FA/hour |
| Continuous false alarms | Episode onsets /verified continuous negative hours; available/unknown exposure separate |
| Latency / coverage | Actual availability−observer start/impact; misses and stage-specific unavailable decisions retained |

Include raw/voted/gated window and event results, retained/attempted coverage,
continuous monitored-negative hours where available, absolute/incremental RAM,
CPU/processing vs alarm latency, parity, class imbalance and uncertainty. Save
reports with timestamps/hashes in `reports/`; append evidence and decision to §9.
Report unified pooled and per-acquisition-profile/day/subtype outcomes, unknown provenance
and actual support. A14 annotation error/review results remain separate from detector
accuracy; no transport-specific models and no automatic-label held-out ground truth.

### Fase B — Protokol perekaman baru

| # | Tugas | Detail |
|---|---|---|
| B1 | Provenance-preserving recorder metadata | For new captures, record operator-verified subject/session/environment values when known; subject IDs may recur across sessions, a session ID recurs only within its actual session. Unknowns stay unknown and do not automatically block take eligibility. Preserve historical reused/conflicting IDs; audit clocks/truth/B6 profile with field-level provenance and claim-specific limitations |
| B2 | Sesi campuran | Setiap sesi berisi fall dan non-fall dalam urutan acak (recorder membuat urutan) |
| B3 | Independent physical ground truth | Annotate every staged event and full monitored intervals under B9; synchronize observer/video/device clocks. Video subset supports reaction-delay study only; non-video truth still needs independent review and declared timing uncertainty. Script/cue alone is not observed truth |
| B4 | Reviewed hard negatives | Deliberate lying, controlled floor sitting, jumping and stumble-without-landing/recovery; classify by B9 observed taxonomy. An actual lateral fall is FALL, not a negative merely because listed here; ambiguous/unwitnessed contact is UNKNOWN |
| B5 | Continuous reviewed-negative sessions | B9 review covers every monitored interval, not just alarm timestamps; physically verified NON_FALL duration includes sensor dropout, with sensor health separate. Preserve complete CSI/Motion/clock/loss timelines; reserve exposure by whole group before tuning. UNKNOWN truth/censoring explicit; §5.5.11 targets are proposals, not low-FA guarantees |
| B6 | Unified acquisition-profile metadata | Preserve HTTP and TCP in one pipeline; retain latest TCP choice and historical HTTP65536 evidence. Freeze mode-specific applied settings/radio/CSI/build/recorder identity with explicit UNKNOWN/provenance. Profile-stratified evaluation is required, not separate models; no acquisition experiment or metadata rewrite now |
| B7 | Subject variation | Collect each fall subtype and negatives across verified subjects and days. Unified lemas includes subject2 HTTP and subject1 TCP, but subject/profile/day confounding persists; do not infer population coverage from this |
| B8 | Reviewed long aftermath / alarm-response protocol | Proposed>=180s observation after the latest safely staged event to cover grace/countdown/ACK/second-stage and censoring; physical start/contact, observed recovery/movement, prompt perception, human actions and assistance simulation labels with synchronized clocks. Add near-fall, recovered fall, deliberate lying/quiet negatives, dropout and multi-occupant confounders. Allocate whole development/reserved sessions before tuning; consented safe supervision, no induced unconsciousness or withheld real help. Reuse B5/B9 full reviewed exposure/clock/reviewer contracts and §5.8 thresholds/interaction limits; no collection performed now |
| B9 | Shared operational truth and adjudication | Freeze the protocol below BEFORE B1–B8 collection; schema/clock/taxonomy/independent review/uncertainty/censoring/whole-exposure checks gate A10/A11 metrics and R4/PF6 truth claims. Versioned pilot and signed QC required; all work NOT_RUN |

#### B6 acquisition identity contract

After approval, attach/reference a normalized `acquisition_profile` in per-take
metadata through a versioned sidecar/overlay, preserving raw recording files. New
captures record it directly. Use one canonical schema/hash for both stimulus families,
not separate datasets/models. Retain raw values, effective/UNKNOWN status and the
source evidence for each field; a schema-complete record may still contain unknowns.

| Field group | Required provenance / handling |
|---|---|
| Common | Active stimulus mode, applied CSI stream throttle, capture/serial settings, AP/link pseudonym, actual channel/secondary/BW and changes, board/antenna/environment placement, radio/CSI/layout/invalid-word policy, firmware/build/source/model and recorder/schema identities |
| HTTP active settings | Full generated URL/query, GET/method/scheme/endpoint, requested burst bytes, pause/read chunk, connection reuse, timeout/retry; historical selected request is `http://speed.cloudflare.com/__down?bytes=65536`, pause0/reuse OFF, but missing historical applied values remain UNKNOWN |
| TCP active settings | Gateway target type/address, port, connect/close behavior, concurrency, timeout, pacing/retry and applied mode settings when actually captured; never backfill from current firmware defaults |
| Evidence status | OBSERVED_APPLIED, RECORDED_UNVERIFIED, INACTIVE, UNKNOWN or CONFLICT with source references; inferred stimulus-family stratum is distinct from a verified complete profile |
| Per-run quality | Actual FPS/dt/gaps, CSI and stimulus counters, clock/loss/coverage; retained alongside profile, excluded from configuration hash |

All232 historical takes currently lack top-level acquisition_profile, have null
acquisition.csi_config and no stimulus.tcp block. TCP metadata retains HTTP values
(fall burst200000/pause100; negatives65536/pause0), but HTTP request/received-byte
counters are zero. Preserve those as inactive settings, not two proven TCP profiles.
Configured target/frequency labels alone do not establish the actual TCP worker schedule.
HTTP uses TCP too; do not conflate stimulus mode with the CSI serial recording transport.
Body/read-chunk sizes do not establish MAC/TCP packet sizes; AP is the downlink transmitter.

Hash deterministic sorted-key configuration JSON with explicit units/null semantics;
keep field evidence/status and schema version hash-linked. Exclude per-run timestamps/
counters from configuration identity. Keep raw identity maps protected and never include
credentials. A changed applied configuration gets a new profile/source segment while
retaining its original take ownership. Unknown settings limit exact-profile claims,
NOT global take eligibility. A10 keeps day/known-family/known-channel/UNKNOWN strata;
A11 reports pooled and per-profile outcomes for the same shared candidate model.

Matched future detector/lifecycle comparisons hold the profile constant; resource
reports identify the actual HTTP/TCP workload tested. More collection to cross both
families with day/activity is a proposed way to reduce confounding, not an authorized
acquisition campaign. No historical metadata edits or profile files are created here.

#### B9 versioned truth, synchronization and review contract

This is a proposed operational protocol, not collected/validated evidence. Freeze it
with the consented safety procedure, taxonomy, schema and assignment manifest before
collection; its artifacts extend A10/A11/A12 rather than creating another plan.

1. Physical taxonomy and observation:
   - FALL: witnessed staged loss of support/balance with uncontrolled body descent and
     landing on a lower supporting surface; annotate subtype and all relevant contacts.
     A recovered fall remains FALL. A cue or model output alone cannot establish it.
   - NON_FALL: witnessed controlled action/no fall, including deliberate lying or a
     stumble with regained support and no uncontrolled landing. Conflicting intent,
     occlusion or insufficient observation yields UNKNOWN, not an assumed negative.
   - `reviewed_start`: first visible loss of support initiating the fall descent;
     `reviewed_impact`: first landing contact terminating that descent. Log preliminary
     hand/support contacts separately. If the primary contact is ambiguous, retain
     bounds/UNKNOWN timing and adjudicate; do not choose a CSI peak to resolve it.
   - Scene movement, victim movement/recovery attempt, independently observed posture,
     ability to perceive/reach the prompt, self-report and caregiver disposition are
     separate labels. No medical consciousness/injury truth is induced or inferred.
     Freeze a visual codebook for elementary intervals: LOW=no displacement discernible
     above measured video/observer resolution; MOVEMENT=discernible displacement;
     occluded/unobserved time=UNKNOWN. Record spatial/temporal resolution from the
     independent pilot. Derive0.5s truth bins from reviewed durations: observer coverage
     <80% → UNKNOWN; otherwise LOW or MOVEMENT if its fraction of observed duration>=0.7,
     else MIXED. These proposed label-aggregation settings match the declared assessment
     granularity, not CSI thresholds; scene/victim labels and observation coverage remain
     independent of sensor validity. Never derive physical truth from CSI/Motion outputs.
2. Clock mapping and proposed pilot targets:
   - Preserve native device callback/driver, observer/video, host monotonic and UTC
     clock domains/epochs. Capture shared observable start/end markers and periodic
     anchors at most60s apart for long sessions; estimate drift between anchors and
     record mapping/residual/quantization uncertainty. Never equate display UTC to
     callback time or subtract clocks without mapping. Each reboot starts a new epoch.
   - Proposed alignment target<=5ms for exact replay (per §5.7.6); proposed physical
     boundary annotation half-width<=100ms. Neither is measured accuracy. Reviewers
     mark earliest/latest plausible boundary, not fake precision from a button press.
     Larger uncertainty is retained and blocks precise latency/freshness claims, not
     event-existence recall or all-event inventory. Missing mapping gives timing NA.
   - Pilot synchronized visible markers, reaction-delay pairs and boundary fixtures
     before main collection. A video subset can estimate observer delay only for that
     subset; never apply an unmeasured universal delay correction to other events.
3. Versioned records (all include session/source epoch, provenance and schema hash):
   - Event: event ID, subject/session/environment/group IDs, staged instruction,
     independently observed FALL/NON_FALL/UNKNOWN disposition/subtype, nominal start/
     impact and earliest/latest bounds, contact list, source evidence/observer IDs,
     completeness, reviewer certainty/disagreement and adjudication status.
   - Interval: half-open [start,end), physical FALL/NON_FALL/UNKNOWN, scene/victim
     motion/posture where observable, observer/video coverage, prompt availability,
     independent sensor-health/loss flags and end-censoring reason. Partition EVERY
     monitored second without overlap/unaccounted gaps; planned quiet is not verified quiet.
   - Action: action/incident/command IDs where available, actor/role, HELP/IM_OK/denial/
     ACK/RESOLVE or observed assistance, physical action time, host/device receipt and
     owner application time, prompt intent/observable delivery/perception, gateway
     attempt/receipt and caregiver acknowledgment/disposition with clock bounds.
     Scenario-assigned assistance need is explicitly SIMULATED, not clinical truth.
4. Independent review and adjudication:
   - Preserve immutable raw observer marks/video/notes first. Two reviewers independently
     annotate every physical event/boundary and complete exposure intervals, blinded to
     detector scores/predicted labels and each other's labels; mask the classifier UI in
     physical-truth review. Interaction review necessarily sees independently recorded
     prompts/actions/receipt evidence, but never uses predicted fall/aftermath as truth.
     Disclose that visibility, reviewer role, staging participation and nonindependence;
     live observer marks are not final labels.
   - Compare class/action/interval differences and boundary discrepancies. Proposed>100ms
     boundary difference or any class/exposure/action disagreement requires a third
     adjudicator against raw evidence. Keep original reviews, adjudicated bounds/reason
     and unresolved disagreements; no forced majority assignment without visible evidence.
   - QC dispositions: REVIEWED, REVIEWED_WITH_UNCERTAINTY, UNKNOWN_TRUTH,
     RIGHT_CENSORED_ENDPOINT or EXCLUDED_PROVENANCE. Capture QC is a separate axis.
     No fall-event exclusion merely because sensor/model evidence is unavailable.
5. Matching, exposure and censored outcomes:
   - Keep nominal §5.7 fixed-D1 matching/tie-breaks for comparable primary reports.
     Flag boundary-uncertain matches; additionally report definite/possible one-to-one
     match bounds using [start_hi−0.3,impact_lo+1.0) and
     [start_lo−0.3,impact_hi+1.0), respectively: definite requires the full decision-time
     uncertainty interval inside the conservative interval; possible requires overlap
     with the permissive interval. Empty conservative intervals have no definite match.
     Apply the same chronological one-to-one/tie-break algorithm separately to each
     bound, retaining the same event denominator. No favorable rounding/window expansion
     or margin-specific event-scoring policy.
   - Reviewed physical events stay in the all-event denominator through capture loss.
     If event existence is reviewed but timing is unavailable, list unresolved timed
     matches, conservative misses and bounds; exact timed recall/latency is unavailable,
     not a smaller favorable denominator. UNKNOWN event existence stays explicit in
     the inventory, never manufactured FALL or NON_FALL from detector output.
   - `H_negative` is the sum of reviewed continuous NON_FALL duration/3600, including
     sensor-invalid periods; `H_negative_valid` intersects it with the stated engine
     stage's valid coverage. Report FALL/UNKNOWN physical exposure and sensor-unavailable
     duration separately. Unknown observation cannot count as verified negative hours.
     Review the entire monitoring timeline, not only alarms; this prevents verification bias.
   - Session end right-censors pending confirmation/dispatch/receipt/ACK/resolution;
     save endpoint status, observed follow-up and required deadline. Report completed/
     failed/censored counts separately; no invented response or padding to180s. Live
     unresolved incidents persist independently of recorder stop (§5.8).
6. Freeze and acceptance artifacts:
   - Store `truth_protocol.json`, `clock_alignment.json`, immutable raw/reviewer/adjudicated
     event/interval/action records and `truth_qc.json` with SHA-256s, revision lineage,
     reviewers/adjudicator IDs, discrepancies, coverage totals and exclusion/censor reasons.
     Seal labels independently of model scores; training/runtime never reads held-out truth.
   - Validate interval partitioning, IDs/clock bounds/contact order, review completeness,
     consent and whole-group ownership. A pilot must pass these checks before B2–B8 main
     collection. Revisions never overwrite raw labels: new hashes/version and documented
     correction; opening reserved labels for correction does not authorize tuning on them.
   - A10 references these hashes; A11/A12 uses them for denominators/uncertainty; R4/PF6
     requires signed review/QC. Missing truth, alignment, independence or follow-up blocks
     the corresponding claim. Safety stops and real assistance always override the script.

### Fase C — Setelah data baru terkumpul

1. After B6/B9 identity/truth QC and A10 ownership, repeat supported DEVELOPMENT
   comparisons and publish interim A5 with session/subject feasibility. Do not open
   reserved groups to choose pipelines, margins, thresholds or grace periods.
2. Tables3–7 comparisons/specifications are complete; experiments remain NOT_RUN.
   Apply §5.6/A10 ownership and §5.7/A11 streaming/metric contracts before planned
   campaigns; C7 below supplies separately authorized hardware/live verification.
   Post-fall lifecycle design is §5.8/D17/A12/B8/B9; C8 is its separate device/interaction
   validation track, not an automatic extension of classifier replay or deployment.
3. Ubah firmware (window, fitur, model) hanya jika hasil offline jelas lebih
   baik: preflight docs → log `docs/agent-changes.md` → trailer `Docs:` →
   replay atau uji perangkat.
4. Jika D8 terpilih: tambahkan normalisasi per frame dan smoothing kausal di
   `activity_classifier_task` sebelum history amplitudo, plus invalidasi gap
   waktu (D9). Parity diuji dengan rekaman yang sama.
5. Uji ulang lantai noise kausal (D10) di rekaman kontinu B5.
6. Select/refit final artifacts using DEVELOPMENT only, complete host-C parity and
   authorized C7/C8 device/resource gates, then freeze exact build/model/policy hashes
   BEFORE untouched reserved offline/live confirmation. The artifact used for final
   testing is the same artifact reported afterward; do not refit using reserved data.
   Match the whole-group session/day/subject/environment claim and B9 truth support.
   Failed confirmation needs a new development revision and new untouched groups.

#### C7 — Actual-ESP replay harness and untouched live acceptance

- After separate authorization, implement §5.7's isolated bounded streaming adapter,
  instrumented virtual-clock fixtures and actual-clock1× replay on ESP32-WROOM-32.
- Preserve production queues/task/load and verify app/model identity; measure capture,
  transport, timing, Motion, state and instrumentation completeness before ranking.
- Execute R3-V/R3-P and reserved R4 only after offline readiness/preflight; firmware
  testing is not approval to deploy or overwrite the active generated artifact.
- Completion per §5.7.9; all new hardware/replay/live results NOT_RUN. Unsupported
  clock/Motion/FSM restore claims remain blocked or explicitly narrowed.

#### C8 — Authorized post-fall lifecycle firmware and interaction pilot

- After A12 core parity AND C7 adapter/identity/R3-V/R3-P readiness (not all of C7 R4)
  and separate approval, implement §5.8 PF4–PF6. B8/B9 truth/QC gates PF6 live outcomes:
  timestamped observations, bounded independent owner/deadlines, committed incident/outbox
  restore, diagnostic schema, incident-scoped controls and fake/test-gateway results.
- Default OFF/SHADOW_ONLY; preserve source classifier queue/voter/Motion/model and
  named matched B6 workload; report HTTP/TCP profile scope separately with one shared
  model. Real audible/tactile controls/gateway/recipients require
  explicit scope and usability/security/privacy review; no emergency-service rollout.
- Use H13–H24 at R3-V/R3-P; measure aggregate4KiB/CPU/stack/queue/timer/storage constraints,
  capture/trace loss, prompt delivery, command races and ACK vs resolution. Browser-verify
  any implemented UI; R4 outcome claims require B8/B9 reviewed untouched whole-group
  truth/clock/exposure QC. C7/C8 may share the final R4 campaign only after both device gates.
- Completion per §5.8.15; no firmware/build/flash/test/messages are performed by this plan
  update. Missing truth/usable prompt/durability/resource evidence remains a blocker.

---

## 7. Katalog preprocessing dan protokol uji (A6)

Goal: evaluate the bounded preprocessing catalog below under matched controls;
this does not enumerate every conceivable method or guarantee every member fits
ESP32-WROOM-32. Freeze §7.4 before execution and document changes in §9. Table4
and Table5 retain their own fixed contracts and selection ownership; A6 shortlists
selected from historical outer results remain exploratory in later combinations.

### 7.1 Data yang tersedia untuk uji offline

Terverifikasi dari 183 berkas `*.frames.csv` (55.744 frame):

| Field | Nilai di semua frame |
|---|---|
| `sig_mode` | 1 (HT) |
| `raw_len` / `valid_len` | 256 / 214 |
| `lltf_len` / `ht_ltf_len` / `stbc_ht_ltf_len` | 102 (51 pasangan) / 112 (56 pasangan) / 0 |
| `stbc` / `first_word_invalid` | 0 / true |
| `agc_gain`, `fft_gain` | 0 (T6) |

- **HT-LTF ikut terekam** di `valid_b64` → bisa diuji offline tanpa rekam
  ulang. Firmware sekarang hanya memakai LLTF.
- `rssi`, `noise_floor`, `host_receive_monotonic_ns`, `rx_ctrl_timestamp_us`
  tersedia per frame.
- Fase I/Q mentah tersedia (int8), jadi fase tersanitasi bisa diuji.

Kelas penerapan:

| Kelas | Arti |
|---|---|
| **F** | Preliminary causal/compact candidate using current data; actual cost/parity unverified |
| **F\*** | Preliminary causal candidate requiring additional firmware input (e.g. HT-LTF); mapping/cost/parity unverified |
| **R** | Requires changed acquisition/calibration protocol and new recordings |
| **O** | Initially offline-only/noncausal or cost-unverified comparator; cannot become a firmware choice without a new causal implementation and measured gates |

Jika kandidat **O** jauh lebih baik dari kandidat **F** terbaik, itu tanda ada
informasi yang hilang di versi kausal → cari padanan kausalnya.

### 7.2 Katalog kandidat

Urutan tahap pipeline tetap P1 → P11. Dalam satu tahap dipilih satu opsi;
`Px.0` = kondisi sekarang (baseline).

#### P1 — Validasi frame

| ID | Metode | Kelas | Parameter uji |
|---|---|---|---|
| P1.0 | Gate layout sekarang | F | — |
| P1.1 | Buang frame dengan RSSI menyimpang dari median kausal 30 frame | F | ambang 6 / 10 dB |
| P1.2 | Buang frame dengan skala amplitudo melonjak (rasio `mean(A)` terhadap median kausal) | F | di luar 0,67–1,5 / 0,8–1,25 |
| P1.3 | Buang frame duplikat (`seq`/`rx_seq` sama) | F | cek dulu apakah ada |

#### P2 — Sumber LTF

| ID | Metode | Kelas | Catatan |
|---|---|---|---|
| P2.0 | LLTF 51 subcarrier | F | sekarang |
| P2.1 | HT-LTF 56 subcarrier | F\* | config default sudah `htltf_en = true` |
| P2.2 | Rata-rata LLTF + HT-LTF di subcarrier yang sama (padanan offline `ltf_merge_en`) | F\* | |
| P2.3 | `ltf_merge_en = true` dari driver | R | |

Sebelum P2.1/P2.2: urutan dan indeks subcarrier HT-LTF diverifikasi dari
dokumentasi CSI ESP-IDF v5.5.3 dan `esp_radar.c`, bukan ditebak.

#### P3 — Representasi per subcarrier

| ID | Metode | Kelas | Catatan |
|---|---|---|---|
| P3.0 | Amplitudo `hypot(I, Q)` | F | sekarang |
| P3.1 | Daya \|H\|² | F | |
| P3.2 | Log-amplitudo (dB) | F | |
| P3.3 | Fase tersanitasi: unwrap lintas subcarrier, buang tren linear (offset + slope) | F | fase ESP32 punya offset acak per paket; uji apakah tersisa informasi |
| P3.4 | Amplitudo + fase tersanitasi (dua aliran, 32 fitur) | F | mengubah jumlah fitur → dicatat juga di Tabel 4 |

#### P4 — Normalisasi skala per frame

| ID | Metode | Kelas |
|---|---|---|
| P4.0 | Tidak ada | F |
| P4.1 | `A / mean(A)` (V3) | F |
| P4.2 | `A / ‖A‖₂` | F |
| P4.3 | `A / median(A)` | F |
| P4.4 | `log A − mean(log A)` (rata-rata geometrik) | F |
| P4.5 | Skala dari RSSI: `A · 10^(−RSSI/20)` (padanan kasar RSS scaling TCS-Fall) | F |
| P4.6 | `manu_scale = true` + `shift` tetap dari driver | R |

#### P5 — Seleksi / bobot subcarrier

| ID | Metode | Kelas | Parameter uji |
|---|---|---|---|
| P5.0 | Semua subcarrier | F | — |
| P5.1 | Buang indeks 45–50 (paling bising, T7) | F | — |
| P5.2 | Buang k subcarrier paling bising di window diam, di-fit per fold | F | k = 4 / 8 |
| P5.3 | Bobot `1/σ_diam` per subcarrier, di-fit per fold | F | — |

#### P6 — Outlier

| ID | Metode | Kelas | Parameter uji |
|---|---|---|---|
| P6.0 | Tidak ada | F | — |
| P6.1 | Hampel kausal (window ke belakang) | F | w = 5, 3σ |
| P6.2 | Hampel kausal longgar | F | w = 7, 4σ |
| P6.3 | Clip per subcarrier di P1/P99 data latih, di-fit per fold | F | — |

Catatan: V1 di T8 belum dipastikan kausal → diuji ulang sebagai P6.1.

#### P7 — Smoothing temporal

| ID | Metode | Kelas | Parameter uji |
|---|---|---|---|
| P7.0 | Tidak ada | F | — |
| P7.1 | Rata-rata kausal (V2) | F | 3 frame |
| P7.2 | Rata-rata kausal | F | 5 frame |
| P7.3 | EMA | F | α = 0,5 / 0,3 |
| P7.4 | Median kausal | F | 3 / 5 frame |
| P7.5 | Butterworth low-pass kausal orde 2 (biquad) | F | fc = 3 / 5 / 8 Hz |
| P7.6 | Butterworth zero-phase (`filtfilt`) | O | fc = 5 Hz |
| P7.7 | Savitzky–Golay terpusat | O | w = 7, orde 2 |
| P7.8 | Gaussian terpusat | O | σ = 1 / 2 frame |
| P7.9 | DWT denoising per window (db4, soft threshold) | O | level 2 / 3 |

Filter IIR (P7.3, P7.5) mengasumsikan sampling teratur; frekuensi cutoff
dihitung dari median ~29 Hz dan interaksinya dengan gap dibaca bersama P9.
P7.9 dipindah ke F hanya jika biaya per window terukur di perangkat masih
masuk anggaran G4.

#### P8 — Baseline / lantai noise

| ID | Metode | Kelas | Parameter uji |
|---|---|---|---|
| P8.0 | Tidak ada | F | — |
| P8.1 | High-pass: `A − EMA lambat` (mirip V5) | F | τ = 2 / 5 / 10 s |
| P8.2 | Lantai noise kausal P20 (V8/V9) | F | 30 window |
| P8.3 | Baseline per take 0,5–2,5 s (V4) | O | — |

Di data sekarang hanya skrining. Penilaian final di rekaman kontinu B5 (D10).

#### P9 — Waktu dan gap

| ID | Metode | Kelas | Parameter uji |
|---|---|---|---|
| P9.0 | Window per jumlah frame, tanpa cek gap | F | — |
| P9.1 | Invalidasi window bergap | F | gap > 0,2 / 0,3 / 0,5 / 1,0 s |
| P9.2 | Reset history saat gap (setara reset firmware saat queue drop) | F | gap > 0,5 / 1,0 s |
| P9.3 | Interpolasi linear ke grid 30 Hz | F | — |
| P9.4 | Zero-order hold ke grid 30 Hz | F | — |

Durasi window dalam detik diuji terpisah di A4.

#### P10 — Reduksi dimensi

| ID | Metode | Kelas | Parameter uji |
|---|---|---|---|
| P10.0 | 16 band rata-rata (sekarang) | F | — |
| P10.1 | PCA di-fit per fold, proyeksi tetap per frame, fitur delta per komponen | F | k = 3 / 5 / 8 |
| P10.2 | PCA dihitung ulang per window (ala Damodaran) | O | k = 3 |

#### P11 — Standardisasi fitur

| ID | Metode | Kelas |
|---|---|---|
| P11.0 | z-score di-fit per fold (sekarang) | F |
| P11.1 | Robust: median / IQR per fold | F |
| P11.2 | z-score per sesi dari periode kalibrasi diam saat deploy | R (uji di B5) |

Catalog inventory:11 stages/59 nonbaseline options including parameter variants;
56 are potential offline branches, not ready-to-run implementations. A10/A11 and
branch-specific A4/A7/operator tests must pass first. R options P2.3/P4.6/P11.2 wait
for authorized new acquisition/calibration under B6/B9 and separately reserved groups.

### 7.3 Protokol uji

#### Prasyarat

1. Freeze/test primary A2 eligibility, complete A10 input/group/inner/outer/reserved
   manifests and audit A1 scheme support BEFORE any fitting. A13 alternatives stay separate.
2. Complete A11 R0 capture/clock/loss audit and tested R1 full-stream/stage/episode/coverage
   metrics before screening. Missing Motion blocks gated metrics, not raw diagnostics.
   Require A7 for gap-policy branches and A4 for time-window branches only. R2 host-C
   parity and C7 device measurements gate deployment finalists, not every screening row.
   Freeze/hash metadata, frames, labels, acquisition identity and exclusions in reports.
3. Modul preprocessing di `fall_detection/` (mis. `preprocess.py`):
   konfigurasi per tahap (mis. `p4=mean,p7=ma3`), satu fungsi per opsi, unit
   test per opsi. Opsi kelas F wajib kausal (test: output frame t tidak
   berubah jika frame > t diubah).
4. Seed dijadikan parameter (`RANDOM_SEED` di `classifier_models.py` dan
   pembagian fold).
5. Ukur waktu satu `fit_classifier` (Python murni, SGD 500 epoch). Jika
   terlalu lambat untuk ratusan fit, buat port numpy yang dibuktikan identik
   dengan implementasi asli (test: bobot sama dalam toleransi). sklearn tidak
   dipakai untuk angka keputusan.
6. Cache label-independent raw transforms by input/config hash only; learned
   features require training-membership/fold/source/environment hashes too. Never
   reuse a scaler/PCA/mask/bin/quiet threshold fitted on another partition.

#### Skema evaluasi (sama untuk semua kandidat)

| Kode | Skema | Isi | Metrik |
|---|---|---|---|
| E1 | Proposed five-fold original-take/verified-lineage OOF |209 manual-first candidates; unknown identities eligible; inner take support pending | Window/event metrics pooled and per-profile; not session-independent |
| E2a | Hold out11-04 | train79F/65N; test0F/65N primary takes | Negative-take alarms;20 additional incomplete FALL takes separately any-alarm only |
| E2b | Hold out11-14 | train79F/73N; test0F/57N | Negative-take alarms; FALL recall NA |
| E2c | Hold out11-07 | train39F/130N; test40F/0N | Annotated-event recall/latency; no negative-take alarm rate; old blocker obsolete |
| E2d | Hold out11-19 | train40F/122N; test39F/8N | Annotated events and negative-take alarms by profile;2 incomplete falls separate; joint TCP/day shift |
| E3 | Day probe | Take-grouped quiet-window Linear SVM | Raw/balanced accuracy, training-fold majority-day baseline, confusion matrix, per-day/activity counts; diagnostic only; no fixed0.333 target, selection or tie-breaking |
| E4 | Biaya | operasi per frame, RAM state, tambahan latensi (frame) | dari kode; finalis diukur di perangkat |
| E5 | Parity | fitur Python vs C pada rekaman yang sama | selisih absolut maksimum |

- Replay complete held-out recordings, including unlabeled intervals: startup/reset
  immediately adopts raw class; subsequent FALL entry2/3, release3 NON_FALL. Do not
  reset at label boundaries. Separate raw/voted/Motion-gated outputs, episodes and
  coverage per §5.4.4/§5.5.8/§5.7; absent synchronized telemetry means unavailable
  gated metrics. Distinguish production versus proposed resets, nominal/actual clocks,
  host replay versus device replay/live evidence, and capture versus queue loss.
- §5.6.7 is the count audit, not a split allocation. E2c is now count-feasible;
  actual phase-window/quality/calibration gates remain. Incomplete FALL supplies
  no primary fitting frames, and any-alarm diagnostics never become timed event recall.
- Unified E2a includes TCP11-19 training; the historical one-FALL-day description
  no longer applies. Day/stimulus/activity remain confounded. E2d coincides with
  TCP-family holdout; do not count the same partition twice as independent evidence.
- Preserve the7 channel11 walking takes; report their stratum. A with/without
  sensitivity is proposed only after approval, not a present exclusion.
- No per-profile classifier/scaler/threshold: evaluate the same shared model with
  profile-specific denominators. Tests keep natural composition; absent cells are NA.
- E2 fixed controls or take-inner selection require the explicit §8.1 choice;
  three day-independent inner folds are unsupported, with no silent fallback.
- 5 seed per konfigurasi; dilaporkan median dan rentang min–maks.

#### Tahapan

| Tahap | Isi | Yang dikunci |
|---|---|---|
| 1. Skrining satu variabel | Setiap opsi F, F\*, O dibanding baseline (semua tahap lain `.0`) | window 24/12, `linear-svm`, label A2; keep 16-delta except explicitly schema-changing representation branches (§5.4) |
| 2. Kombinasi | Maks. 2 opsi terbaik per tahap yang lolos Tahap 1; forward selection mengikuti urutan pipeline, tahap baru ditambah hanya jika "lebih baik nyata" (§7.4). V2+V3 (P7.1 + P4.1) selalu diuji eksplisit | sama |
| 3. Window interaction | After A4/A7 operator tests, repeat at most3 development-shortlisted pipelines at1/2/3s; choose only in grouped inner training, report outer scores without selecting | Features/model/primary A2 labels; same A10 groups and A11 metrics |
| 4. Finalists | R2 host production-C parity for matched F0 and at most2 C-supported finalists; after authorization/preflight C7 R3-V/R3-P measures costs/timing; unsupported C operators stay blocked | Frozen development artifacts; no reserved-test refitting |
| 5. Confirmation | Complete B6 identity/B9 truth QC and freeze finalists before opening reserved B groups; same-axis whole session/subject tests and B5 continuous FA/hour; R acquisition variants need separately authorized matched sessions and untouched groups | No tuning on confirmation; R4 live/device evidence distinct from offline replay |

Stage1–4 choices remain provisional because of T1. The isolated C7 replay/profiling
harness may be authorized after R2 readiness to perform Stage4 device verification;
candidate behavior changes require the offline/parity gates. Neither authorizes
release. Final decisions wait for Stage5 untouched confirmation. A failed confirmation
returns to DEVELOPMENT and requires new reserved groups, not tuning on the old test.

Conditional unified screening workload:56 configurations ×9 fits
(5 E1 +4 E2) ×5 seeds=2,520 fits, excluding baseline/E3. This assumes approval
and support for all four E2 diagnostics, not executed work or readiness; actual rows depend
on A10/A11 and branch-specific A4/A7/schema gates. Inner selection, A13 and R2/device
verification add separately inventoried work; representation changes need §5.4 support.

### 7.4 Penilaian

These are provisional A6 criteria, not universal model-selection rules. Table4
uses §5.4 and Table5 uses §5.5, including nested training ownership. Preserve old
proxy results; append separate current-snapshot evidence. Historical selection
and confidence intervals cannot establish unseen-session generalization.

Readiness is staged: Stage1–3 screening may carry G3/G4 as NOT_VERIFIED until R2/C7
finalist checks; that is not a pass or permission to deploy. State every gate per row.
Historical E1/E2-driven forward selection is exploratory only. Confirmatory selection
replays the bounded candidate/combination/window search inside A10 grouped inner folds;
outer scores, E3 and reserved B groups are reporting-only. If inner folds/objectives lack
class/group support, keep selection BLOCKED or declare the narrower exploratory claim
before results, not a silently substituted outer-test winner.

#### Gerbang (wajib lolos semua, gagal = gugur)

| Kode | Syarat | Sifat angka |
|---|---|---|
| G1 | Kelas F atau F\* (O hanya pembanding; R menunggu Tahap 5) | — |
| G2 | Supported E2a any-alarm fall-take recall loses at most1 take vs baseline (median seed); show count/denominator and annotated E1/E2c/E2d metrics separately | Proposed diagnostic criterion, not timed event recall or an outer-test selector; current E2c blocker removed |
| G3 | Each feature/score abs(C-Python)<=1e-5+1e-4*abs(Python), plus threshold/class/state/episode checks (§5.5.9); quantized variants use their separate reference | Proposed gate; skipped checks do not pass |
| G4 | Additional peak live RAM<=4KiB; incremental complete-pipeline CPU<=2.9ms/frame amortized; decision P99<=50ms; event coverage>=95%; no incremental queue loss | Proposed targets, not measured; report absolute resources and concurrent-load profile |

#### Metrik utama (urutan prioritas)

1. Negative takes with>=1 prediction episode: E2a/E2b/E2d have65/57/8 candidates
   (130 total), reported per fold/profile and pooled, with count/proportion/unavailability.
   E2c negative-take rate is NA. No continuous FA/hour or notification claim from short takes.
2. Any-alarm diagnostics:20 incomplete FALL in E2a and2 in E2d, separately denominated.
   Annotated E1 and E2c/E2d event recall remains separate with fixed D1 scoring and
   actual coverage; no invented timing for incomplete takes or pooling distinct metrics.
3. **Macro-F1 E1.**

Secondary ranking/tie-breakers: FALL-window precision, annotated-event latency,
seed variability, E4 cost and fewer active stages. E3 raw/balanced day accuracy,
majority baseline/confusion/per-day/activity counts are diagnostics ONLY, never
selection or tie-breakers; imbalance invalidates a fixed raw-accuracy chance target.

#### Aturan "lebih baik nyata"

Suatu kandidat dianggap lebih baik dari pembandingnya hanya jika:

1. Selisih metrik utama lebih besar dari rentang min–maks pembanding antar-seed,
   **dan**
2. Diagnostic false-alarm improvement is consistent across supported E2a/E2b/E2d
   negative-take tests while recall satisfies G2; annotated E2c/E2d misses are reported
   separately and cannot be hidden by pooling, **and**
3. CI 95% bootstrap per take (1.000 resample) untuk laju alarm palsu / macro-F1
   tidak melewati nol pada selisihnya.

Uji McNemar exact per take (alarm ya/tidak) dilaporkan sebagai indikasi saja,
karena take dalam satu hari tidak independen. Jika syarat tidak terpenuhi,
lack of a detected difference is **not proof of equivalence**. Retain the
simpler candidate provisionally and confirm on new independently held-out sessions.

#### Keluaran

- `reports/preprocessing_ablation/<timestamp>/`:
  - `config.json`: snapshot dataset, seed, kriteria §7.4 apa adanya saat
    uji dijalankan.
  - `results.csv`: satu baris per konfigurasi × skema × seed.
  - `alarms_per_take.csv`: alarm per take untuk McNemar/bootstrap dan
    breakdown per aktivitas.
  - `summary.md`: tabel peringkat.
- Preserve historical T8 proxy data. Append new results with snapshot/policy/
  algorithm hashes; update D8–D11 only from identified new evidence and log in §9.

Template tabel peringkat:

| Configuration | Class | G1 | G2 | G3 | G4 | Negative-take alarms E2a/E2b/E2d +pooled/profile counts | Incomplete-fall any-alarm E2a/E2d | Annotated event recall E2c/E2d | Macro-F1 E1 | E3 diagnostic only | Annotated latency | Cost |
|---|---|---|---|---|---|---|---|---|---|---|---|---|

---

## 8. Pertanyaan terbuka

### 8.1 Approval checkpoint: outstanding decisions and recommended next scope

Already decided by the user: ONE unified HTTP/TCP dataset/model pipeline;
acquisition_profile retained; original take is the base unit; unknown identities
are preserved and do not automatically block eligibility; investigate alignment
without direct timestamp copying; no manifest/training/ablation before approval.
These decisions do not need to be reopened.

| Outstanding choice | Recommendation / reason | Current status |
|---|---|---|
| Primary-label candidate pool and smoke | Retain manual-first D1 and existing TEST01/SMOKE01 training exclusion:209 candidates, all232 inventoried. Unknown IDs remain eligible; incomplete labels and smoke are independent reasons | AWAITING_APPROVAL; no policy/metadata edits |
| Evaluation protocol | Take-based E1 as primary development; E2a–E2d secondary fixed-control diagnostics. If inner selection is requested for E2, explicitly approve take-inner scope, never call it day-independent | AWAITING_APPROVAL; no assignments; five outer/three inner take folds only count-plausible |
| Identity-exclusive claims | Defer subject/session claims until provenance supports them; preserve reused raw session strings and UNKNOWN values. User-supplied contemporaneous provenance can support a versioned correction, never guessing | PROVENANCE_UNRESOLVED; not a global eligibility blocker |
| Historical profile completeness | Approve versioned acquisition_profile sidecar/overlay with known fields and explicit UNKNOWN/INACTIVE evidence; do not reconstruct missing TCP settings from current source | AWAITING_APPROVAL for metadata implementation; family/day/channel reporting possible already |
| A14 validation and verification | Development-only study completed (§5.2.2); next review proposals and define acceptable error/coverage using intended use and independent evidence before tuning. Measured observer errors are not acceptance tolerances | DEVELOPMENT_STUDY_COMPLETE; fold-owned calibration, review, tolerances and independent evidence unresolved |
| Allowed assisted-label use | Proposals only, excluded from primary truth/training. Any weak-label training is a separately approved branch; signal review cannot make it manual ground truth | 20 AUTO_PROPOSED /2 ABSTAINED sidecars generated; training use NOT_APPROVED |
| Channel and sparse-stratum sensitivity | Retain7 channel11 takes and sparse TCP negatives in the base inventory; report strata. Approve any exclusion/with-without study separately, not from favorable scores | NO_EXCLUSION_APPLIED; sensitivity NOT_RUN |
| Next authorized work | The requested automatic-annotation study is complete. Review/verification, A2/A10/A11 detector preparation, future fits and new crossed-profile collection need their own explicit scope | ANNOTATION_STUDY_COMPLETE; remaining execution at APPROVAL_GATE |

No split can remove the observed TCP/day confounding or manufacture independent
subject/session provenance. The209 count is not a guarantee that every W24/time-window
configuration, calibration fold or nested scheme will remain eligible. New uninspected
confirmation data are required for an untouched claim, not a random holdout of the
already analyzed232 takes.

### 8.2 Longer-term research and deployment questions

- Berapa delay reaksi observer terhadap kejadian sebenarnya? (butuh video, B3)
- Which predeclared annotation margins improve development-only A13 sensitivity
  under fixed D1 scoring and observer uncertainty? Primary A2 remains−0.3s/+1.0s;
  outer/reserved results cannot select the margins.
- Which separate aftermath features/thresholds generalize across B8 sessions without
  turning scene quiet/movement into a victim-specific recovery or unconsciousness claim?
- Which proposed §5.8 confirmation/grace/countdown policy reduces false alarm burden
  without new true-fall rejection, unacceptable response delay or hidden unavailability?
- Can the aggregate owner/queue/stack/journal/diagnostic costs satisfy the shared4KiB
  budget under each declared HTTP/TCP profile load, and what is the measured uncommitted power-loss window?
- Which accessible local HELP/OK interface and authorized gateway/recipient workflow
  supports intended users? Browser/serial/LED availability is not a safety-alarm guarantee.
- Berapa banyak subjek dan sesi minimum yang realistis untuk dikumpulkan?
- Apakah 7 take walking di channel 11 perlu dikeluarkan dari evaluasi?
- Kenapa normalisasi per frame menaikkan akurasi menebak hari (0,717 →
  0,850) padahal alarm palsu lintas hari turun?
- Apakah subcarrier tepi (indeks 45–50) sebaiknya dibuang atau diberi bobot
  lebih kecil? (Tabel 4)
- Apakah `manu_scale = true` dengan shift tetap memberi skala lebih stabil
  daripada normalisasi per frame? Perlu cek dokumentasi ESP-IDF v5.5.3 dan uji
  perangkat.
- Apakah HT-LTF (56 subcarrier, sudah terekam) lebih stabil daripada LLTF?
  (P2.1–P2.2)
- Apakah fase satu antena setelah sanitasi masih membawa informasi gerak?
  (P3.3)
- What current flash/heap/stack/queue headroom remains under the full concurrent
  workload? Historical maps do not answer the live budget question (§5.5.10).
- Which conditional temporal/operator families pass verified C export and event
  coverage, and is there enough class-preserving data for nested calibration?
- Do weighted/novelty/quantized or combined pipelines reduce new-session false
  alarms without losing fall-subtype recall? All outcomes remain NOT_RUN.
- Are confirmation hours/subjects sufficient for the intended operating-point
  uncertainty? Proposed minimum collection is not a deployment safety guarantee.
- Which independence claim is supported by the available mixed groups: new take,
  session, day, user or environment? Confirm through A10, not the train/test ratio.
- How many additional development days/subjects remain necessary for three
  same-axis inner folds after reserving final-test groups (§5.6.5)?
- Which recordings have callback-complete CSI and alignable Motion rather than host
  timing/throttle proxies? R0 must audit this before claiming ESP-equivalent replay.
- Can the bounded adapter meet proposed5ms/P99 and20ms/max delivery-error targets
  under actual concurrent load, without ingress/diagnostic loss (§5.7.6)?
- What current app/model actually executes on the board, and which reset/clock mode
  does its build implement? Source inspection is not flash identity evidence.

---

## 9. Log hasil dan perubahan rencana

Historical review-fix traceability (document corrections, not completed experiments;
its HTTP-only and old split assumptions are superseded by the2026-11-20 entry):

| Reviewed issue | Integrated contract / execution owner |
|---|---|
| Missing D1 margin sensitivity | D1, frozen §5.4.1/A2, separate A13 and A5 reporting; fixed event-scoring interval |
| A6 missing/out-of-order dependencies | §6 RDEP0–RDEP8, A6/A8/A9/A10/A11 and §7.3/§7.4 staged readiness |
| First-intent cap vs stage2 contradiction | §5.8.3–§5.8.5/§5.8.7/§5.8.10/§5.8.12–§5.8.13; immutable separate anchors and ACK/restore tests |
| Undefined reviewed/verified truth | B9 taxonomy/schema/clock/review/adjudication/QC/exposure/censoring; A10/A11, B3/B5/B8 and R4/PF3/PF6 gates |
| E2a incorrectly called event recall | §5.6.3/§5.7.7, A3/A5, §7.3/G2/priorities/result template; historical counts retained |
| Fixed E3 accuracy target/ranking | T8 qualification, §5.4.4 and §7.3/§7.4; raw/balanced/majority/confusion/support, diagnostic only |
| Incomplete acquisition identity | B6 exact http_cloudflare GET bytes=65536 and canonical full-profile hash; B9/A10/R4 identity links |

| Tanggal | Perubahan |
|---|---|
| 2026-11-18 | Rencana awal dari perbandingan Tabel 1–2 dan analisis dataset (T1–T5, D1–D7, Fase A–C) |
| 2026-11-18 | Tabel 3 (preprocessing): T6–T8, D8–D11, §5.3, tugas A6–A7, Fase C 4–5 |
| 2026-11-18 | §7 baru: katalog 11 tahap preprocessing (59 opsi), protokol uji 5 tahap, gerbang dan kriteria penilaian. D11 direvisi (penolakan tanpa uji dicabut), D8 jadi hipotesis, A6 diperluas. Temuan: HT-LTF 56 subcarrier ada di semua frame |
| 2026-11-18 | Table 4 comparison: verified exact 16-delta formula and storage counts (T9/T10), literature reconciliation and feature configurations F0–F15 (§5.4), D12/D13 and A8. No new experiment run. Corrected E2c cue-label exception, pooled recall, and claims of sole false-alarm cause/equivalence; expanded features await controlled tests. |
| 2026-11-18 | Expanded Table4 testing specification §5.4.1–§5.4.6: F0–F27 with formulas/parameter variants, causal calibration and phase gates, fixed tensor shapes, implementation/test prerequisites, seeds/folds/replay/metrics, staged fit inventory, selection/resource guards, future CLI and result states. Updated A8/A1; no new script, training, firmware change, or measured result. |
| 2026-11-18 | Added Table5 lifecycle specification §5.5.1–§5.5.11, T11/D14/A9: bounded25 model families,15 training-strategy IDs, F/P representation reuse and four sequence inputs, controlled combinations, imbalance, nested split/calibration ownership, full event/window replay, float/quantized Python-C parity, live hardware profiling and untouched-session confirmation. Preserved Table4's unweighted baseline and historical T8; reconciled three label policies, voter startup, cost/parity wording and applicability labels. All new experiments NOT_RUN; only this plan edited, no implementation/install/training/build/flash/commit. |
| 2026-11-18 | Added Table6 recommendations §5.6.1–§5.6.6/D15/A10: literature uncertainty, current deterministic take grouping/fold-local scaling, missing-ID skips and undefined metrics, layered independence claims, original-group manifests, nested learned-state ownership, blocked folds and group-count feasibility, untouched whole-axis confirmation. Corrected A1 causal interpretation and skip behavior; aligned Table5 minimum-data caveats/status/FaseC. Preserved Table4 contract and old results. Documentation only; all new split tests/experiments NOT_RUN, no code/training/build/flash/commit. |
| 2026-11-19 | Added comprehensive Table7 §5.7.1–§5.7.9/D16/A11/C7: primary-source NEWR/CWR definitions, complete causal CSI streams, production vs proposed state/reset behavior, host-C/device virtual and paced/live fidelity tiers, capture/Motion/clock completeness, bounded adapter and queue semantics, actual timing/identity/concurrent-load profiles, episode/coverage/uncertainty contracts, scenario matrix and artifacts/status gates. Corrected A3 take-vs-event wording, aligned shared roadmap/metrics and half-open D1. ESP-IDF v5.5.3 Timer/FreeRTOS documentation checked. Only this existing plan changed; all new implementation/tests/experiments NOT_RUN, no code/install/training/build/flash/commit. |
| 2026-11-19 | Added post-fall lifecycle §5.8.1–§5.8.16/D17/A12/B8/C8: literature/source transfer limits and AL0–AL8 comparisons, explicit incident/aftermath/quality/notification axes and transitions, evidence-qualified confirmation, proposed bounded clocks/grace/escalation, user command/cancellation/ACK semantics, recovery/near-fall/dropout/re-fall/overload/power-fault handling, isolated pure-C/owner/queue integration, durable outbox/clock epochs, telemetry, H13–H24, event/assistance/receipt/FA-hour/latency/resource metrics, safe long-POST data and staged non-emergency rollout. Reconciled POST and prediction-episode terminology; preserved legacy model/voter/gate and selected HTTP65536/pause0/reuse-off acquisition. Prior research carried forward; csi-pose/Apple/smartphone and official v5.5.3 Timer/NVS checked. Only this living plan edited; numbers are proposed, all implementation/experiments NOT_RUN or explicitly blocked; no code/install/training/build/flash/notification/commit. |
| 2026-11-19 | Applied all seven review corrections in this existing plan: D1/A13 predeclared training-owned margin sensitivity with unchanged primary event scoring; A10/A11 R0/R1 readiness and conditional A4/A7/R2/device gates; dependency-based §6/§7/PF order; first-stage60s cap distinct from immutable first-intent+60s stage2 deadline, with HELP/ACK arbitration, restore/attempt budgets and H15/H17–H21 fixtures; B9 operational taxonomy/clock/independent review/adjudication/uncertainty/censoring/full-exposure QC; E2a any-alarm fall-take terminology; imbalance-aware diagnostic-only E3; full hashed B6 http_cloudflare request/radio/CSI/build/recorder identity. Clarified continuous reset boundaries, per-stage states, manual-help/denial dispositions, metric formulas/denominators and development-refit before untouched acceptance. Historical measurements/log entries and legacy controls preserved; new thresholds/tolerances are proposals, all implementation/tests/campaigns remain NOT_RUN/blocked. Documentation consistency checked; no runtime code, acquisition experiment, training/build/flash/notification or commit. |
| 2026-11-20 | Integrated the user's six decisions: unified232 takes (183 HTTP/49 TCP,101F/131N),79 complete/22 incomplete fall annotations, provisional manual-first209 pool including65 unknown-ID negatives. D5/D15/D18 preserve raw identities and take-based ownership; B6 specifies unified mode-specific acquisition_profile provenance with UNKNOWN/INACTIVE fields, no transport-specific models. Added §5.2.1/A14 time-aware correlation/DTW/consensus investigation, donor ownership, masked-label confidence validation, preserved manual marks and independent verification; no inferred label becomes manual truth. §5.6.7 recomputes day/profile feasibility, removes obsolete E2c no-training-FALL blocker, adds E2d and flags day/profile/class/channel confounding and unsupported three-inner-day selection. Reconciled A/B/C dependencies, §7 metrics/workload estimates, acquisition workload scope and §8.1 explicit approval choices. Sources: current raw metadata/frame audit, phase trainer/policy, earlier exploratory CSVs, official SciPy correlation and tslearn DTW documentation. Historical measurements/logs retained as historical. This request changed only the existing plan; read-only audit/design complete, implementation/manifests/annotation generation/training/ablations NOT_RUN or AWAITING_USER_APPROVAL; no recording edits, runtime code/build/flash/notification or commit. |
| 2026-11-20 | Subsequent request to run automatic annotations: completed a quarantined offline NCC/constrained-DTW study (§5.2.2),632 masked-observer diagnostic rows and22 immutable sidecars (20 proposals,2 host-gap abstentions). Preserved all467 source files and the partial5.229s manual start. Added annotation CLI/tests, passed63 focused tests including saved-output verification, and logged decisions/evidence in docs/agent-changes.md. Updated current authorization, A14 and §8.1; no confidence calibration, independent truth verification, training-label promotion, detector splits/manifests, classifier training/ablations, firmware/build/flash or commit. |
