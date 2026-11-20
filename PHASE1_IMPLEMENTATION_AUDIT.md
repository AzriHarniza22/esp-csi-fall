# Phase 1 implementation audit

## 1. Ringkasan status

Audit ini read-only dan membandingkan source kerja dengan commit dasar
`8f43df5`. Tidak ada build ulang, flash, capture hardware, training, atau
perubahan dataset.

**Keputusan: Tahap 2 belum boleh dimulai.** Fondasi sequence dan queue sudah
terkompilasi pada target komponen, tetapi kontrak replay dan accounting belum
benar. Ada masalah wajib diperbaiki sebelum menambahkan exporter atau
checkpoint.

## 2. Temuan

| Area | Status | Kesimpulan |
|---|---|---|
| Raw feature dan FIFO dasar | INCOMPLETE | Nilai dan urutan dasar tetap, tetapi accounting dequeue salah. |
| Sequence correlation | FAIL | `fsm_seq` dibuat saat enqueue, bukan saat processing aktual. |
| Window correlation | FAIL | Hanya `last_frame_seq` tersedia; first/last/count/gap tidak tersedia. |
| Feature status | INCOMPLETE | Zero diberi label ambigu, tetapi invalid window dan compute failure digabung. |
| Diagnostic queue | FAIL | Overflow hanya dihitung; capture tidak menjadi invalid secara persisten. |
| Lifecycle accounting | FAIL | START mereset counter historis; STOP/reset/remove tidak direkonsiliasi. |
| Header integration | INCOMPLETE | Source target terkompilasi, tetapi public struct/config layout berubah tanpa versioning. |
| Full build attribution | INCOMPLETE | Error jelas berada di source unchanged, tetapi baseline build terpisah belum dijalankan. |
| Detector source equivalence | FAIL | Jalur nilai detector sama, tetapi callback tambahan mengubah timing dan ada bug counter. |

## 3. Sequence semantics

- `frame_seq` dibuat oleh `peer->csi_seq++` pada jalur CSI filtering dan
  disimpan di ring CSI. Feature kemudian mengambil
  `seq_id[buff_index.end]` sebagai `radar_info.frame_seq`
  (`esp-radar/src/esp_radar.c:1813-1821`).
- `feature_seq` dibuat oleh `peer->feature_seq++` sebelum perhitungan feature
  (`esp-radar/src/esp_radar.c:1816-1818`). Nilai ini disalin ke
  `hms_raw_item_t`, sehingga tetap sama pada record enqueue, dequeue, dan
  process (`esp_wifi_sensing.c:105-114, 1276-1289, 2048-2065`).
- `fsm_seq` dibuat dengan `++fsm->fsm_seq` saat item dimasukkan ke ring
  (`esp_wifi_sensing.c:1284`). Nilai yang sama diteruskan ke dequeue dan
  process. Jadi **bukan** urutan processing aktual; item yang tertunda atau
  diproses batch tetap memiliki nomor enqueue.
- `record_seq` dibuat oleh `hms_diag_emit_locked()` untuk setiap stage
  (`esp_wifi_sensing.c:269-306`). Satu sample menghasilkan beberapa record,
  dan counter di-reset oleh `diag_start()` (`esp_wifi_sensing.c:1711-1729`).
  Ini adalah urutan record queue, bukan identitas sample.

Kesimpulan: `feature_seq` dapat dikorelasikan sampai dequeue, tetapi chain
belum memenuhi definisi `fsm_seq` desain dan tidak memiliki lifecycle/epoch
untuk membedakan capture yang berbeda.

## 4. Window correlation

`wifi_radar_info_t` hanya menyimpan `frame_seq` yang didokumentasikan sebagai
frame terakhir window (`esp-radar/include/esp_radar.h:110-118`). Source radar
memang memiliki `buff_index.begin`, `buff_index.end`, dan `buff_index.window`,
serta ring `seq_id`, tetapi metadata tersebut tidak diteruskan ke
`wifi_radar_info_t` (`esp-radar/src/esp_radar.c:1862-1867`).

Akibatnya tidak dapat diverifikasi dari diagnostic record:

- `first_frame_seq`;
- `last_frame_seq` secara eksplisit selain satu nilai `frame_seq`;
- jumlah frame pembentuk window;
- frame gap atau timestamp gap;
- frame yang terhapus/terlewati oleh ring CSI.

Satu `frame_seq` tidak cukup untuk exact replay sebuah window. Ini adalah
blocker wajib.

## 5. Ring buffer dan detector equivalence

Perbandingan baseline (`esp_wifi_sensing.c:1860-1868`) dengan implementasi:

- FIFO read index, write index, count, wrap-around, full condition, dan
  overwrite oldest tetap sama; hanya payload berubah dari `uint32_t` menjadi
  `hms_raw_item_t`.
- `item.raw_feature` diproses langsung oleh
  `hms_preprocess_channel()` (`esp_wifi_sensing.c:2058`), sehingga transformasi
  `log1p` dan nilai input detector tidak berubah secara source-level.
- `HMS_MAX_BATCH` tetap membatasi batch dequeue.
- START/STOP/RESET_BASELINE tetap menjalankan lifecycle detector lama, dan
  fungsi reset tidak mengosongkan ring raw (`esp_wifi_sensing.c:628-674,
  1975-2031`). Pending item dapat tetap diproses setelah STOP/START, seperti
  perilaku dasar.
- Channel removal tetap membebaskan raw ring dan channel
  (`esp_wifi_sensing.c:1594-1624`), tetapi pending item tidak dihitung sebagai
  discard diagnostik.

**Bug accounting wajib:** `fsm_drop_count++` berada di jalur dequeue
(`esp_wifi_sensing.c:2051-2054`). Itu menghitung setiap item yang berhasil
diambil, bukan hanya item yang dibuang. Counter tidak dapat dipakai untuk
persamaan drop/overwrite.

Perubahan callback menambah callback feature sebelum callback FSM biasa
(`esp-radar/src/esp_radar.c:1870-1875`). Callback itu mencoba mutex
non-blocking dan melakukan atomic counter; ini tidak mengubah rumus detector,
tetapi mengubah timing callback dan contention. Kesetaraan runtime belum dapat
dinyatakan tanpa pengukuran.

## 6. Feature status

Status yang tersedia:

- `COMPUTE_FAILED` digunakan saat `csi_detection_compute_motion_dec()` gagal
  (`esp-radar/src/esp_radar.c:1827-1834`).
- `COMPUTED_ZERO_AMBIGUOUS` digunakan saat API prebuilt
  `compute_jitter()` mengembalikan `0.0` (`esp-radar/src/esp_radar.c:1838-1843`).
  Ini tidak mengklaim zero valid atau insufficient data.
- `COMPUTED` digunakan untuk jitter non-zero.

Namun status `COMPUTE_FAILED` mencakup kegagalan window/input sebelum
`compute_jitter()` dipanggil. Tidak ada status terpisah untuk invalid window,
insufficient input, atau kegagalan internal dependency. Percobaan yang tidak
mencapai loop detection karena buffer/peer belum siap juga tidak dihitung.
Dengan kontrak dependency float-only, pemisahan lebih rinci tidak dapat
dibuat tanpa metadata tambahan dari radar source atau dependency.

## 7. Diagnostic queue

Queue dibuat fixed-size 64 record dan `xQueueSend(..., 0)` digunakan sehingga
producer tidak blocking (`esp_wifi_sensing.c:269-306, create path`). `diag_read()`
menggunakan `xQueueReceive(..., 0)`, yang secara internal aman terhadap operasi
queue producer/consumer bersamaan (`esp_wifi_sensing.c:1736-1741`).

Masalah:

1. Saat queue penuh, `diag_drop_count` bertambah, tetapi tidak ada
   `capture_invalid` atau alasan invalid yang persisten. Capture overflow dapat
   terlihat seperti capture valid dengan record lebih sedikit.
2. `diag_start()` melakukan `xQueueReset()` dan mereset counter tanpa
   menghitung record yang dibuang (`esp_wifi_sensing.c:1717-1729`).
3. Capture stop aman terhadap producer yang memakai mutex, tetapi
   `diag_capture_enabled` dibaca task tanpa mutex pada
   `esp_wifi_sensing.c:1358-1361`; ini adalah shared state tanpa mekanisme
   sinkronisasi yang konsisten.
4. Batas 60 detik diperiksa oleh task dan oleh `hms_diag_emit_locked()`, jadi
   admission umumnya berhenti setelah elapsed time tercapai. Akan tetapi
   status selesai/timeout tidak diekspor dan tidak ada penanda bahwa capture
   terpotong.
5. Tidak ada exporter, sehingga queue memang bounded tetapi belum menyediakan
   data replay ke host.

## 8. Lifecycle accounting

START mereset `feature_*`, `fsm_*`, radar, dan diagnostic interval counters
(`esp_wifi_sensing.c:1975-2007`). Ini menghapus sejarah counter sebelumnya tanpa
event/epoch record. STOP hanya mengubah `is_running`; pending raw items tidak
didiscard dan tidak dicatat (`esp_wifi_sensing.c:2013-2015`). RESET_BASELINE
mereset state detector tetapi tidak mencatat reset, flush, atau queue boundary
(`esp_wifi_sensing.c:2016-2028`). Remove membebaskan pending ring tanpa
accounting.

Karena itu accounting berikut belum dapat direkonsiliasi secara historis:

```text
feature_attempts
  = computed_nonzero + computed_zero_ambiguous + compute_failed

fsm_enqueues
  = fsm_dequeues + fsm_drops + pending
```

Persamaan kedua gagal karena `fsm_drop_count` saat ini menghitung dequeue.
Selain itu reset, STOP discard, remove discard, queue reset, dan diagnostic
queue drop tidak memiliki event/counter lifecycle yang persisten.

## 9. Header integration dan full build

Public `wifi_radar_info_t` dan `esp_radar_dec_config_t` diperluas dengan field
dan callback (`esp-radar/include/esp_radar.h:110-124, 348-350`). Semua source
lokal target berhasil dikompilasi sebelumnya, tetapi perubahan layout dapat
memengaruhi consumer binary atau positional initializer di luar source yang
diaudit. Initializer default sudah diperbarui, namun tidak ada ABI/version
guard.

Full build log yang tersedia menunjukkan error di
`main/web_serial_monitor.c:1099-1115` untuk
`esp_wifi_sensing_ping_event_t`/field-field ping dan
`main/web_serial_monitor.c:2680` untuk
`esp_wifi_sensing_fsm_register_ping_event_cb()`.
Source `web_serial_monitor.c` tidak berubah dari commit dasar
(`git diff HEAD -- .../main/web_serial_monitor.c` kosong), dan header Tahap 1
tidak mendefinisikan simbol ping tersebut. Ini adalah bukti kuat bahwa error
tidak berasal dari perubahan sequence/diagnostic header.

Namun, karena batasan audit melarang build ulang, **baseline full build
terpisah belum terbukti secara empiris pada sesi ini**. Status yang tepat
adalah INCOMPLETE, bukan klaim pasti pre-existing. Pembuktian final memerlukan
build baseline di worktree/commit sementara tanpa mengubah worktree pengguna.

## 10. Masalah wajib diperbaiki

1. Pindahkan pemberian `fsm_seq` ke titik processing aktual; pertahankan
   sequence enqueue terpisah bila diperlukan.
2. Hapus increment `fsm_drop_count` dari dequeue dan tambahkan counter/drop
   event yang tepat untuk overwrite, STOP, reset/flush, remove, dan queue
   discard.
3. Tambahkan metadata window: first/last frame sequence, frame count, dan
   gap/invalid-window status.
4. Tambahkan status capture invalid yang persisten; queue overflow, queue
   reset, export loss, dan lifecycle discard harus membuat capture tidak valid.
5. Tambahkan lifecycle/epoch records dan jangan mereset accounting historis
   tanpa menyimpan boundary.
6. Pisahkan invalid window, insufficient data, dan compute failure sejauh yang
   benar-benar dapat dibuktikan oleh source/API; jangan mengarang status
   internal prebuilt library.
7. Sinkronkan akses capture state dan tetapkan kontrak concurrency
   start/stop/read.

## 11. Masalah yang dapat ditunda

- Serial/chunk exporter dan format host dapat ditambahkan setelah kontrak
  record/window/lifecycle diperbaiki.
- ABI/version guard untuk public header dapat ditambahkan sebelum API dipakai
  consumer eksternal, selama seluruh build source lokal tetap konsisten.
- Pengukuran runtime callback overhead, mutex contention, queue rate, dan
  detector transition equivalence memerlukan hardware atau replay dan bukan
  bagian audit read-only ini.

## 12. Rekomendasi tahap berikutnya

Jangan mulai Tahap 2. Lakukan corrective patch kecil untuk sequence,
window-membership, invalidation, dan lifecycle accounting terlebih dahulu.
Setelah itu:

1. compile kedua komponen;
2. buktikan baseline/full-build comparison secara terpisah;
3. jalankan static accounting tests untuk enqueue/dequeue/overflow/reset;
4. baru desain exporter berdasarkan record yang sudah memiliki validitas
   capture yang dapat dipercaya.

## 13. Status corrective patch

Corrective patch sudah diterapkan pada source override, tetapi belum di-commit.
Target komponen `esp-radar` dan `esp_wifi_sensing` berhasil dibuild dengan
ESP-IDF v5.5.3; tidak ada flash, training, capture hardware, atau build ulang
full application.

| Area | Status setelah patch | Bukti dan batasan |
|---|---|---|
| Sequence semantics | PASS source-level | `feature_seq` dibawa dari radar ke raw item; `fsm_seq` baru diberikan setelah dequeue sebelum processing; `record_seq` diberikan saat record dibuat. |
| Window metadata | PASS source-level | `first/last_frame_seq`, count, timestamp awal/akhir/span, dan sequence-gap count disalin dari `csi_data_buff_index_t`; timestamp gap tidak diklaim sebagai frame loss. |
| FIFO semantics | PASS source-level | Payload ring menjadi struct tanpa mengubah index/count/full/overwrite algorithm; `raw_feature` tetap diproses langsung. Runtime equivalence belum dibuktikan tanpa hardware/replay. |
| Diagnostic overflow | PASS source-level | Overflow menambah `diag_drop_count` dan menetapkan `INVALID_OVERFLOW` persisten sampai capture berikutnya; record lama tidak ditimpa oleh queue. |
| FSM accounting | PASS source-level | Attempt, enqueue, dequeue, processed, overwrite, dan channel-remove discard memiliki penghitung terpisah; dequeue normal tidak menambah counter drop. |
| Lifecycle accounting | INCOMPLETE | START/STOP/RESET_BASELINE/channel-remove memiliki lifecycle sequence dan record saat capture aktif. STOP/reset tidak membuang ring untuk mempertahankan perilaku lama, sehingga discard counter tetap nol bila tidak ada flush aktual. |
| Feature validity | INCOMPLETE | Compute failure dan zero ambiguous dicatat tanpa mengarang status internal dependency; API prebuilt tetap tidak membedakan insufficient data dari zero valid. |
| Full build | INCOMPLETE | Build target komponen lulus. Full build tetap memiliki error `main/web_serial_monitor.c` yang belum dibuktikan terhadap baseline secara terpisah. |

Persamaan source-level yang sekarang dapat diaudit per channel adalah:

```text
fsm_enqueued
  = fsm_dequeued
  + pending_raw_items
  + fsm_queue_overwritten
  + fsm_queue_discarded_on_stop
  + fsm_queue_discarded_on_reset
  + fsm_queue_discarded_on_channel_remove
```

Dengan implementasi saat ini, overwrite terjadi saat ring penuh dan discard
STOP/reset tidak dilakukan oleh lifecycle lama; nilai aktual harus diambil dari
counter dan `raw_count` pada saat capture. `fsm_processed +
fsm_processing_failed` harus sama dengan `fsm_dequeued`; fungsi processing
belum memiliki jalur error terpisah sehingga `fsm_processing_failed` tetap nol.

### Keputusan tahap

Tahap 2 **belum boleh dimulai**. Corrective patch memperbaiki blocker sequence,
window metadata, overflow, dan counter pada level source, tetapi full build
aplikasi belum lulus dan runtime equivalence, queue contention, serta
rekonsiliasi hardware belum diuji. Selain itu, exact end-to-end replay tetap
terbatas oleh dependency motion decoder prebuilt.

## 14. Final corrective patch

Patch final diterapkan pada source override dan dibuild tanpa flash, training,
capture hardware, atau perubahan dataset.

| Area | Status final | Bukti |
|---|---|---|
| Capture identity | PASS source-level | Setiap record membawa `boot_id`, `capture_id`, dan `record_seq`; `capture_id` naik setiap capture baru dan `record_seq` boleh reset per capture. |
| Final capture status | PASS source-level | Status operasi membedakan stopped-complete, stopped-pending, duration-complete, overflow, dan data-loss; integrity disimpan terpisah. |
| Queue preservation | PASS source-level | `diag_start()` menolak start saat capture aktif atau queue masih berisi record; tidak lagi memakai `xQueueReset()`. |
| Automatic reset lifecycle | PASS source-level | `hms_reset_channel_state()` menghasilkan satu lifecycle record per reset dengan channel, reason, state sebelum/sesudah, pending count, sequence, dan timestamp. |
| Enqueue accounting | PASS source-level | Callback delivery dihitung terpisah dari `fsm_enqueue_attempted`; lock/no-channel tidak masuk attempted; rejected dipisahkan. |
| Individual overwrite disposition | PASS source-level | Item tertua disalin sebelum index maju, direkam dengan feature/raw value, lifecycle sequence, dan discard reason; overflow record gagal menginvalidasi capture. |
| Target component build | PASS | `esp-radar` dan `esp_wifi_sensing` target tersedia/lulus pada build ESP-IDF v5.5.3. |
| Full application build | INCOMPLETE | Baseline pembanding belum dijalankan; error API ping tetap tidak boleh disebut pre-existing. |

Accounting final:

```text
radar_callback_delivered =
    radar_drop_lock_count
  + radar_drop_no_channel_count
  + radar_callback_with_channel

fsm_enqueue_attempted =
    fsm_enqueued
  + fsm_enqueue_rejected

fsm_enqueued =
    fsm_dequeued
  + pending_raw_items
  + fsm_queue_overwritten
  + fsm_queue_discarded_on_stop
  + fsm_queue_discarded_on_reset
  + fsm_queue_discarded_on_channel_remove
```

`radar_cb_count` sekarang merepresentasikan callback yang diterima dengan
argument valid, sedangkan lock failure dan no-channel dicatat terpisah.
Overwrite tetap mempertahankan kebijakan ring lama; patch hanya menambahkan
disposition record dan invalidasi integritas capture.

### Keputusan final

Tahap 1 **lulus secara source-level dan target-component build**, tetapi belum
tersertifikasi runtime. Tahap 2 masih **ditahan** sampai full-build baseline
dibuktikan, serta FIFO, capture separation, lifecycle, dan counter diuji pada
hardware atau harness yang sesuai. Kesetaraan end-to-end juga tetap dibatasi
dependency motion decoder prebuilt.

## 15. Tahap 2 checkpoint dan state instrumentation

Tahap 2 menambahkan API checkpoint berbasis caller-provided buffer dan field
state sebelum/sesudah pada diagnostic record. Snapshot memakai mutex FSM yang
sama, tidak memicu START/RESET_BASELINE, tidak menghapus ring, tidak
mengalokasikan memori, dan tidak melakukan serial I/O.

Status source-level:

- **PASS:** checkpoint header memuat version, boot/capture identity, lifecycle
  sequence, batch sequence, required size, dan monotonic timestamp.
- **PASS:** setiap channel aktif menyimpan seluruh state mutable detector,
  runtime configuration, presence/training state, ring capacity/index/count,
  dan pending items.
- **PASS:** pending items disalin dari `raw_read_index` dalam logical dequeue
  order, termasuk feature/raw value, enqueue timestamp, dan lifecycle sequence.
- **PASS:** process records memiliki batch ID/index/size dan state
  before/after untuk smooth, baseline, gold baseline, noise, diff, threshold,
  debounce, init stage, process state, serta transition reason.
- **PASS:** reset helper, START/STOP, explicit reset, automatic reset,
  low-jitter reset, runtime-center recovery, dan channel removal tetap tercatat
  melalui lifecycle records.
- **INCOMPLETE:** durasi critical section checkpoint dan contention belum
  diukur pada hardware; full application baseline build juga belum diverifikasi.

Tidak ada serial exporter atau Tahap 3 yang dimulai.

## 16. Tahap 3 diagnostic export

Tahap 3 sekarang tersedia secara source-level dan telah melewati build aplikasi
ESP-IDF v5.5.3. Firmware mengekspor checkpoint, record diagnostik, dan manifest
melalui chunk `HMS:` Base64 dengan CRC32 IEEE. Record hanya dihapus setelah ACK
yang cocok dengan `boot_id`, `capture_id`, `chunk_seq`, dan CRC. Browser memakai
writer Web Serial yang sudah ada untuk memvalidasi chunk dan mengirim
`HMSCMD DIAG_ACK`; host recorder menyediakan jalur stdin bounded dan menyimpan
chunk, manifest, laporan transfer, serta payload berurutan.

Status verifikasi:

- **PASS:** `idf.py build` menghasilkan `wifi_sensing_demo.bin` dengan
  ESP-IDF v5.5.3.
- **PASS:** protocol/recorder fixture lulus 10 pemeriksaan, termasuk manifest
  wajib dan validasi CRC/identity/duplicate/missing.
- **PASS:** JavaScript host dan browser syntax check lulus; `git diff --check`
  lulus.
- **INCOMPLETE:** tidak ada flash atau uji hardware, sehingga retry ACK,
  throughput serial, dan contention runtime belum terbukti.
- **LIMITATION:** payload checkpoint/record masih raw C layout ESP32; belum
  menjadi format portable lintas arsitektur.
- **NOTE:** hook ping event yang tidak dideklarasikan pada source override
  dihapus dari monitor agar aplikasi dapat dikompilasi. Counter ping tetap
  dipertahankan untuk kompatibilitas laporan, tetapi tidak dapat terisi tanpa
  API dependency tersebut.

Tahap 3 belum mengaktifkan serial exporter terpisah, tidak mengubah algoritma
detector, dan tidak mengubah `managed_components/`.

## 17. Post-implementation audit dan corrective patch Tahap 3

- **PASS:** record dan checkpoint tidak lagi dikirim sebagai raw C struct.
  Envelope versioned memakai magic, schema, record type, payload length, dan
  little-endian fixed-width fields. Float memakai IEEE-754 binary32 bit
  representation. Host decoder menolak length mismatch dan trailing bytes.
- **PASS:** setiap record diagnostic dikonversi field-by-field; checkpoint
  mencakup header, seluruh channel, dan pending item logical order.
- **PASS:** record hanya di-drop setelah ACK; chunk checkpoint dapat direkonstruksi
  sebelum decoding di host recorder.
- **PASS:** TAKE_BEGIN tetap membuka recording, memulai FSM diagnostics secara
  terpisah, dan mempertahankan field telemetry `diagnostics_enabled`. Dua test
  gagal sebelumnya adalah static pattern terlalu ketat terhadap whitespace dan
  field `fsm_diagnostics_enabled`; setelah diperbaiki, seluruh suite lulus.
- **INCOMPLETE:** ping per-reply tidak dapat dipulihkan dari source aktual
  karena `esp_wifi_sensing_ping_event_t` dan
  `esp_wifi_sensing_fsm_register_ping_event_cb` tidak tersedia pada public
  header/source override. Aggregate ping counters yang dipakai monitoring tetap
  tersedia dan tidak dihapus.
- **INCOMPLETE:** tidak ada hardware validation; bandwidth, ACK retry timing,
  heap pressure, dan checkpoint duration masih perlu diukur pada perangkat.
