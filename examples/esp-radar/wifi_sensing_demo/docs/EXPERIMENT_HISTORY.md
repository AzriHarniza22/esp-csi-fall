# Experiment History — ESP32 Wi-Fi CSI Fall Detection

Dokumen ini merangkum **seluruh** rangkaian eksperimen stimulus CSI yang pernah dijalankan di
repo ini, dari investigasi awal (Oktober 2026) sampai kampanye benchmark protokol final
(November 2026) dan panel kontrol Web Serial. Tujuannya: setelah artefak eksperimen
(`reports/**`, fork percobaan, log, grafik) dibersihkan, **riwayat + temuan tetap dapat dibaca
pada satu file koheren** tanpa membuka puluhan laporan lama.

Ditulis sebagai hasil cleanup repository (mandat `docs/cleanup.md`). Bukan ringkasan diff;
ini dokumentasi teknis. Klaim diberi label:

- **TERBUKTI** — didukung pengukuran langsung dengan gerbang validasi.
- **TERAMATI** — terlihat pada pengujian, belum cukup untuk generalisasi.
- **TIDAK KONKLUSIF** — bukti tidak memadai / terkondangi.
- **DITOLAK** — tidak memenuhi kriteria atau terbukti tidak layak.
- **BELUM DIUJI** — belum ada validasi.
- **REKOMENDASI** — keputusan teknis berdasarkan bukti tersedia.

---

## 1. Tujuan Eksperimen

Penelitian inti: **deteksi jatuh berbasis Wi-Fi CSI** pada satu board ESP32-WROOM-32 yang
menjalankan firmware `wifi_sensing_demo` (esp-radar + FSM motion/fall + activity classifier +
HMS/Web Serial Monitor + recorder dataset).

Seluruh rangkaian eksperimen stimulus ini adalah **pekerjaan pendukung akuisisi**, bukan algoritma.
Masalah yang ingin dijawab:

1. Stimulus jaringan apa yang memaksa AP memancarkan cukup banyak frame data HT agar **tap CSI
   esp-radar terisi terus-menerus** pada topologi satu-ESP32 + satu-router?
2. Berapa **FPS CSI** yang realistis, dan bagaimana definisinya (counter mana yang dihitung)?
3. Apakah akuisisi pipeline siap untuk mengumpulkan dataset fall-detection, dan **feature
   extractor** perlu sadar-timestamp?

Yang **bukan** tujuan: mengubah format raw CSI, mengubah algoritma fall detection, mengubah
konfigurasi router, atau menjadikan laptop sebagai pemancar stimulus.

---

## 2. Arsitektur Sistem dan Lingkungan Eksperimen

- **Board:** ESP32-WROOM-32 (D0WD-V3 rev **v3.1**), crystal 40 MHz. MAC STA `44:1d:64:fa:57:b8`
  (IP 192.168.1.10). Konsol via CH340 di `/dev/ttyUSB0` @ 921600 baud.
- **Toolchain:** ESP-IDF **v5.5.3** (`/home/azri/.espressif/v5.5.3/esp-idf`), target `esp32`
  classic. Komponen: `esp_wifi_sensing 0.1.1~3`, `esp-radar 0.3.4` (**LOCKED** — `esp_radar.c`
  sha `5a4aaabc…` tidak boleh disentuh).
- **Router/AP:** SSID `kos mutiara ` (trailing space), BSSID `f8:73:1a:59:23:f4`, **kanal 1
  (2412 MHz), BW20/HT20**, gateway 192.168.1.1, WPA2. Konfigurasi router **tidak diubah** sepanjang
  kampanye (dilarang oleh mandat).
- **AP asing (interferer):** `d4:53:2a:61:a2:c1` — sumber co-channel `_plus`; ini variabel pengganggu
  utama (lihat §6). Catatan kanal: eksperimen `experiment_20261031` mencatat AP di **kanal 11**;
  seluruh kampanye berikutnya di **kanal 1** — lingkungan berpindah, angkanya jangan dicampur.
- **Arsitektur stimulus:** firmware menghasilkan traffic sendiri (HTTP Cloudflare download, TCP
  connect→close ke gateway, DNS query, ICMP ping). Laptop **bukan** pemancar.
- **Arsitektur CSI acquisition:** esp-radar mendaftarkan promiscuous RX callback → peer-selection
  (filter BSSID target) → **callback CSI** (`esp_radar_csi_rx_cb`) → counter `csi_frame_count` →
  stream HMS (`sample`, `csi`, `stimulus` telemetry) ke host lewat UART.
- **Alur data ESP32 → host:** UART 921600. **Plafon link terukur ≈ 63 fps CSI-saja, ≈ 45 fps
  dengan stream HUD** (`csi` 1446 B/terukur). Ini langit-langit keras di jalur HMS.
- **Batasan:** `CONFIG_FREERTOS_HZ=100` ⇒ tick **10 ms** membatasi presisi pacing (mitigasi clamp
  diterapkan Phase C/E). HMS bersifat metadata-only: **amplitudo 52 subcarrier tidak dikirim ke
  host**, jadi heatmap magnitude & validasi per-subcarrier tidak tersedia lewat jalur ini.

---

## 3. Riwayat Metode Stimulus

### 3.1 HTTP Cloudflare (download burst)
- **Mekanisme:** firmware menarik object berukuran tertentu dari `speed.cloudflare.com`; downlink AP
  ke STA berupa rangkaian frame **data HT teragregasi** (plen ~214, `sig=1`, `rate=11`, mcs2–6).
- **Hasil:** **TERBUKTI** kelas terbaik. Mempertahankan device-cb **32–36 Hz** dan **tahan
  interferensi** co-channel. 14/14 leg A-B-A VALID; akuntansi tertutup (`emitted−1+dropped==Δseq`);
  heap akhir ~115–133 kB; tanpa crash/watchdog.
- **Status akhir: DIPILIH** sebagai stimulus standar.

### 3.2 TCP gateway (connect→close)
- **Mekanisme:** non-blocking TCP connect→close ke gateway, parameterized
  (concurrency/interval/timeout/port), diforward via build-define `TCP_*`.
- **Optimasi (`tcp_csi_optimization`):** kandidat A3 (**conc=4, interval=10 ms, timeout=50 ms, port
  80→53, exchange=connect→close**) dipilih — **bukan** karena fps tertinggi (plateau ~165–175 pada
  fork standalone, link/AP-bound), melainkan karena **PHY sehat (MCS 6/7), tanpa dependensi layanan,
  bekerja di kedua state radio bistabil**. ~2.7 CSI/transaksi, ~60 transaksi/s.
- **Integrasi ke `wifi_sensing_demo`:** modul `main/tcp_stimulus.c/.h`; switchable live lewat
  `SET_STIMULUS_MODE tcp_gateway` + `SET_TCP_STIMULUS <conc> <int_ms> <to_ms>`; bug **TCP
  stop/start race diperbaiki** (masih di source utama — dipertahankan).
- **Verdict kampanye (`csi_stimulus_benchmark`):** pada jalur HMS terintegrasi, TCP ≈ HTTP di
  window tenang; angka "TCP unggul 35.8 vs 25.2" adalah efek denominator; **live parameter sweep
  menunjukkan TCP tidak bisa di-tune ke lebih banyak CSI** karena offer-rate bukan limiter.
- **Status: DIPERTAHANKAN di firmware** (fitur aktif, didukung panel Web), **bukan** stimulus
  rekomendasi utama. **TIDAK KONKLUSIF** vs HTTP pada throughput.

### 3.3 DNS UDP query
- **Mekanisme:** query DNS kecil ke router/resolver; bergantung proxy DNS router.
- **Hasil:** device_cb ~**29 Hz**, lebih rendah & kurang teratur dari HTTP; `no_peer` tertinggi
  (karena jendela radio ramai, bukan DNS-nya sendiri). **Cadangan LAN-only**, bukan peningkatan.
- **Status: DIPERTAHANKAN di firmware** (fallback), **DITOLAK** sebagai kandidat utama.

### 3.4 ICMP Ping (router gateway)
- **Mekanisme:** `esp_ping` ke gateway pada N Hz.
- **Hasil:** **DITOLAK secara struktural.** Balasan ping IP-layer tiba (`ping_reply_hz` 50/100
  terukur), tapi **0 frame target** masuk callback CSI — reply = **satu frame kecil** yang gugur di
  tahap peer-selection esp-radar. Terkonfirmasi konsisten: eksperimen HTTP-vs-ping awal
  (2026-10-31, ap_frames_delta=0
  di 50 & 100 Hz), `official_baseline` (ping 100 Hz 1B, 5 CSI/300 s), `csi_stimulus_benchmark` Phase D.
  **Bukan soal laju** — bahkan official-parity 100 Hz tetap nol. Perbaikannya butuh mengubah
  ukuran/sumber frame AP, di luar kendali firmware pemancar.
- **Catatan bug historis:** error `unmatched data size for profile 5` (ping) **diperbaiki** — 0 error
  terverifikasi di perangkat (`p1_runtime_smoke`). Perbaikan tetap di source.
- **Status: DIPERTAHANKAN sebagai mode (warisan), tidak direkomendasikan untuk akuisisi CSI.**

### 3.5 NTP UDP
- **Hasil:** **DITOLAK via eliminasi struktural** (Phase F). Router tidak serve NTP; respons 48 B UDP
  = satu frame kecil, rezim identik ICMP (nol CSI). Upper-bound ~15 fps. **Tidak diimplementasi**;
  dihentikan sesuai mandat.

### 3.6 Null Data Frame + ACK (`console_test` bawaan)
- **Mekanisme:** `WIFI_CSI_SEND_NULL_DATA_ENABLE=1`, TX null-data ~100 Hz ke router.
- **Hasil:** **NEGATIF TERBUKTI** — **0 frame CSI/60 s**. Filter null-data esp-radar hanya menerima
  `payload_len == 14` (format ESP-NOW/null-data **antar dua ESP32**); router menghasilkan ACK
  (body ~0 B) dan data unicast 94–1421 B — tak satu pun == 14. Ditambah `esp_wifi_set_promiscuous(false)`
  saat GOT_IP di jalur ESPNOW ⇒ ACK router tidak muncul. Dengan SATU ESP32 + router, jalur null-data
  tidak punya sumber frame payload-14.
- **Keputusan:** hasil negatif, tidak ditindaklanjuti (butuh 2 ESP32). Fork `console_test_nulldata/`
  adalah eksperimen sekali-pakai.

### 3.7 Tabel perbandingan metode

| Metode | device-cb FPS (tipikal) | Kelaziman/interferensi | Stabilitas record | Status |
|---|---:|---|---|---|
| **HTTP Cloudflare** | **32–36** | Tahan interferensi; paling teratur | 14/14 VALID | **DIPILIH (REKOMENDASI)** |
| TCP gateway (A3) | ~30–36 (setara HTTP tenang) | OK | Stabil, heap recover | Dipertahankan; TIDAK KONKLUSIF vs HTTP |
| DNS UDP | ~29 | Kurang teratur | Stabil, laju rendah | Fallback LAN-only |
| ICMP ping | **0** | — | 0 CSI frame | DITOLAK (struktural) |
| NTP UDP | **0** (est. ≤15) | — | — | DITOLAK; tak diimplementasi |
| Null-data + ACK | **0** | — | — | NEGATIF (butuh 2 board) |

Angka berasal dari kampanye berbeda; **jangan diperlakukan satu-variabel antar-baris.** Yang
apple-to-apple hanya HTTP/DNS/ICMP/NTP/TCP di `csi_stimulus_benchmark` (fork & firmware sama,
satu variabel per leg).

---

## 4. Hasil Optimasi Stimulus

- **Baseline HTTP:** `http_cloudflare 200000 pause=100`. device-cb 36,1–36,2 (blok tenang).
- **HTTP 64 KB:** `http_cloudflare 65536 pause=0`. **setara** 200 KB di blok tenang (36,0–36,5).
  Knee naik monoton 21→35 fps lalu **plateau**; tidak ada peningkatan nyata di atas ~64 KB.
- **HTTP keep-alive:** **DITOLAK**. Angka tertinggi kampanye E6=38,1 tidak bereproduksi (A-B-A:
  25,6/5,6/34,9) dan membawa **kegagalan tingkat-aplikasi**: gap CSI **10 475 ms**, `fw_reported=0`,
  requests stall. p95 104 ms, satu window membentang **19,5 s**. **JANGAN dipakai.**
- **pause_ms:** **TERBUKTI** pause>0 menurunkan fps (35,8→31,7→28,9→23,7) & menambah gap ⇒
  **pause=0 lebih dipilih**.
- **TCP optimization:** A3 (conc=4/int=10/to=50/80→53) dibekukan; **live sweep membuktikan TCP tidak
  bisa di-tune melampaui plafon** (offer-rate bukan limiter).
- **Hasil yang dikoreksi akibat interferensi:** klaim lama "**64 KB unggul konsistensi peer**"
  **DICABUT** — itu mis-atribusi interferensi AP asing, bukan keunggulan protokol. Lihat §6.
- **Konfigurasi kerja final (REKOMENDASI):**
  ```text
  mode                 = http_cloudflare
  burst_bytes          = 65536      # 200000 setara; 64KB = preferensi airtime, bukan laju
  pause_ms             = 0          # pause>0 menurunkan laju & menambah gap
  keep_alive           = off        # keep-alive membawa stall 10 s — JANGAN
  csi_stream_period_ms = 0          # throttle emisi minimal; recall: throttle mengubah laju callback
  ```
  Butuh internet (DNS + route `speed.cloudflare.com`). Fallback LAN-only: DNS ke router (~29 fps).

---

## 5. Measurement Audit

- **Enam FPS didefinisikan terpisah, tidak pernah digabung:** `device_cb`, `emitted`, `host-received`,
  `browser`, `firmware_reported` (window 1 s), `rx entry callback`. Angka historis (32,6 / 1,98 / 9,86 /
  35–47 / ~160) memakai **penyebut berbeda** sehingga tidak dapat dibandingkan langsung.
- **~160 Hz mustahil sebagai angka host** pada 921600 baud — plafon ≈ 63 fps (csi-saja), ≈ 45 fps
  (dengan HUD). **TERBUKTI.**
- **9,86 fps lama** = bug jendela harness v1 (dihitung pada 9,867 s, bukan 15 s). **TERBUKTI** bug.
- **Back-pressure emisi:** **TERBUKTI** mengubah laju callback hilir driver — hanya dengan mengubah
  throttle emisi 0→100 ms, `rx` di entry callback naik **34,89 → 88,73 Hz**. Inilah alasan `SET_CSI_PERIOD 0`
  (throttle minimal) dipakai saat akuisisi.
- **Beban link bersama:** stream HUD `sample` (747 B/baris ~47/s) memakai sepertiga link ⇒ fps 35,5→29,6,
  utilisasi uart 57→85%. **TERBUKTI.**
- **Identitas akuntansi:** `emitted − 1 + dropped == Δseq`, `seq_gap=0`, `dropped=0` menutup jalur HMS
  tanpa sequence-ID baru (10/10 + 14/14 leg). **TERBUKTI.**
- **Serial capture & arm-verification:** protokol capture diverifikasi lewat read-back SHA (lihat §9).
- **Race condition:** TCP stop/start race ditemukan & diperbaiki di source utama. **TERBUKTI** (fix aktif).
- **Bug label metrik streak:** angka "14 s empty streak" adalah salah label (dihitung pada cabang
  detik-**berisi**; longest *filled* streak = 14 s); streak kosong sebenarnya 5 s. fps/coverage tetap benar.

---

## 6. Wi-Fi Interference

**Temuan metodologis terbesar kampanye.**

- **Perangkat asing teridentifikasi:** `d4:53:2a:61:a2:c1` (co-channel `_plus`).
- **`no_peer` ≠ indikator kualitas stimulus.** `no_peer` (dan sebagian variasi laju) disebabkan
  **AP asing** itu, bukan stimulus. Korelasi langsung `foreign%` vs `no_peer` diverifikasi lewat
  `check_no_peer_source.py`. **TERBUKTI.**
- **Mekanisme:** esp_radar peer-selection menolak frame dari sumber asing ⇒ window tercatat `no_peer`;
  saat blok AP asing ramai, laju HTTP turun dan `no_peer` naik — **meniru** perbedaan antar-protokol.
- **Dampak pada perbandingan:** klaim awal "64 KB/keep-alive/DNS unggul" banyak yang **tercemar**
  interferensi. **Bracket A-B-A biasa tidak melindungi** dari interferensi yang berubah dalam skala menit.
- **Solusi metodologi:** gunakan **blok punggung-ke-punggung dalam satu jendela radio** (back-to-back
  dalam block tenang) alih-alih bracket berjauhan. Insiden malam 2026-11-02 (eksperimen D/E tidak
  dapat dinilai karena AP mendadak senyap padahal ping 100%) menegaskan hal ini.
- **Cara membaca benchmark berikutnya:** pantau & dokumentasikan `foreign%` per sesi; pilih jendela
  tenang atau terima varians; jangan klaim keunggulan protokol tanpa kontrol interferensi.

---

## 7. CSI Acquisition & Temporal Characteristics

- **Plafon laju:** ~**36 fps device_cb** (HTTP/DNS/TCP tenang). **Target engineering §12 (≥ 50
  frame/0,5 s; p95 ≤ 15 ms) TIDAK tercapai** oleh kandidat mana pun (maks ~22 frame/0,5 s, p95 ~53 ms).
- **Interval HTTP (64/200 KB):** median ~**17,5 ms**, p95 ~**53 ms**, **tanpa bucket kosong**;
  CV window-24 ~**10%**. DNS p95 sedikit lebih rendah (47 ms) tapi median interval lebih panjang
  (31,8 ms, laju lebih rendah). Keep-alive terburuk (p95 104 ms, CV 34–146%, satu window 19,5 s).
- **Window-24 frame-indexed ≈ 0,62 s**, bukan 0,5 s. **Jam host ≈ jam perangkat** (durasi window
  identik dari `rel_ms` dan `ts_us`) ⇒ jitter berasal dari **sumber akuisisi radio**, bukan skew jam.
- **Rekomendasi timestamp-aware (Q12, TERBUKTI perlu):** extractor `fall_detection/dataset_io.py`
  saat ini **frame-indexed** (window 24 / stride 12) ⇒ satu window = rentang waktu bervariasi.
  **Satu timestamp perangkat/frame (`ts_us`) cukup.** Jalur turunan berbasis-duration (kumpulkan
  sampai ≥ 0,5 s, atau resample ke grid 20 Hz via `ts_us`, atau fitur berbobot-Δt) disimpan
  **terpisah, tanpa menimpa raw, tanpa resample diam-diam.** Extractor frame-indexed dipertahankan
  sebagai baseline (mandat: jangan ubah extractor sebelum acquisition selesai).
- **Keterbatasan:** amplitudo per-subcarrier & browser-FPS tidak terekam di jalur HMS.

---

## 8. Recording dan Dataset

- **Format:** recorder dua-file v3 (`tools/csi_recorder.js` + `tools/csi_recorder_server.py`).
  Tiap take = folder berlabel-sanitasi berisi `*.csi_data.csv` (header cocok esp-radar `CSI_DATA`),
  `*.iq.csv` (satu baris/frame, kolom I/Q per subcarrier), `*.meta.json` (label, countdown, duration,
  batch ID, gap antar-take, jumlah frame, completeness, `motion_samples` telemetri motion-detector ESP).
- **Integritas raw CSI:** timestamp + sequence number dipertahankan; counter & akuntansi diverifikasi §5.
- **First-word-invalid:** masalah `first_word_invalid` telah diperbaiki **di sumber (clamp)**, bukan
  trim `valid_data` yang telah dikompaksi (keputusan tercatat; fix tetap di source).
- **Validasi:** take dihasilkan builder nyata dari stream HMS dan diterima validator server (HTTP 200).
  `stim_ping` dengan 0 CSI ditolak dengan benar.
- **Dataset penelitian vs rekaman eksperimen:** seluruh take **sudah di-purge pada 2026-11-03**
  atas permintaan user (dataset akan dikumpulkan ulang dari nol). Yang dipertahankan hanya
  `recordings/README.md` (format) + `.gitkeep`. Klasifikasi saat masih ada, untuk panduan rekaman
  berikutnya:
  - aktivitas (`empty_room`, `walking`, label `non_fall`) = kandidat **dataset** → kumpulkan lagi.
  - `stim_http`, `stim_off`, `stim_tcp`, `tcp_stimulus` = validasi stimulus (bukan dataset).
  - `tcp_motion` = dulu ambigu ("motion") — saat rekaman ulang, beri label aktivitas yang jelas.
- **Data recording (`*.csi_data.csv`, `*.iq.csv`, `*.meta.json`) di-gitignore** (`.gitignore`:
  `recordings/**/*.csv`, `recordings/**/*.meta.json`) — lokal saja, hanya README & struktur yang dilacak.

---

## 9. Bug dan Perbaikan yang Sudah Diterapkan

Semua perbaikan berikut **masih menjadi bagian program utama** dan **WAJIB dipertahankan**
(asal-usul "untuk eksperimen" tidak menggugahkan kebutuhan). Verifikasi di source sebelum cleanup.

| Masalah | Penyebab | Perbaikan | File/modul | Status |
|---|---|---|---|---|
| `unmatched data size for profile 5` (ping) | ukuran payload profil ping tak cocok | koreksi profil; 0 error terverifikasi perangkat | `main/ht_stimulus.c` (ping) | **AKTIF** |
| TCP stop/start race | task TCP dihentikan/dijalankan berurutan tanpa sinkron | perbaikan stop/start + handoff task | `main/tcp_stimulus.c` | **AKTIF** |
| `first_word_invalid` | kata pertama payload CSI | clamp di sumber, bukan trim valid_data | jalur parser CSI | **AKTIF** |
| Throttle emisi menekan laju callback | back-pressure emisi | `SET_CSI_PERIOD 0` saat akuisisi | `main/web_serial_monitor.c` (HMS) | **AKTIF** |
| Interleaving statistik/CSI di UART | tulis bersama tanpa antre | diag_queue/serial sinkron | `main/web_serial_monitor.c` | **AKTIF** |
| Parser command & ACK tanpa epoch | `send_ack` tak punya epoch | waiter ACK promise-based (Web) | `tools/web_serial_monitor.html` | **AKTIF** |
| Race harness FPS (jendela 9,867 s) | bug durasi jendela harness | definisi ulang enam FPS + window | tooling host | diperbaiki di tooling |

---

## 10. Eksperimen yang Gagal, Ditolak, atau Tidak Konklusif

- **Null-data + ACK → 0 CSI** (butuh 2 ESP32; filter `payload_len==14` = ESP-NOW). DITOLAK.
- **ICMP → 0 CSI** & **NTP → 0/tak kompetitif**: struktural (downlink AP satu frame kecil). DITOLAK.
- **keep-alive**: tidak >baseline, tidak aman kontinuitas (stall 10 s). DITOLAK.
- **Klaim "64 KB unggul konsistensi peer"**: **DICABUT** — mis-atribusi interferensi (§6).
- **Eksperimen D (`dump_ack_en=1`) & E (ping 200 Hz) malam 2026-11-02**: **tidak dapat dinilai** —
  lingkungan radio/AP berubah (ping 100% tapi CSI target runtuh ke 0–2/60 s). ACK jalur mati di
  perangkat ini (`ack=0, ackme=0`). Hasilnya **jangan** dipakai sebagai kesimpulan.
- **Parity throughput keep-alive vs baseline**, **DNS vs baseline**: **TIDAK KONKLUSIF** (butuh ≥3 leg
  terkontrol di jendela tenang).
- **Hipotesis BELUM DIUJI:** HTTPS/TLS, HTTP multi-koneksi terkontrol, chunked/streaming body,
  `foreign%` sebagai kovariat eksplisit dalam re-ranking.

---

## 11. Keputusan Teknis Saat Ini

- **Stimulus standar:** `http_cloudflare 65536 pause=0 keep_alive=off` + `csi_stream_period_ms=0`.
- **TCP:** modul aktif + support `SET_TCP_STIMULUS` live + Web panel; **bukan** rekomendasi utama.
- **DNS:** fallback LAN-only aktif. **ICMP/NTP:** mode warisan (ping tetap ada), tidak untuk akuisisi.
- **CSI period:** `SET_CSI_PERIOD 0` saat akuisisi; dipertahankan panel Web (guard vs OFF & vs
  rec-aktif).
- **Feature extraction:** **REKOMENDASI** jalur timestamp-aware (`ts_us`) sebagai turunan terpisah;
  extractor frame-indexed tetap baseline.
- **Recorder:** dua-file v3 aktif; `recordings/` sedang dikosongkan (purge 2026-11-03, akan direkam ulang).
- **Firmware aktif di perangkat (end-state `csi_stimulus_benchmark`):** build `0xf16a0` (988832 B,
  sha `d3b3b0a7…`); diverifikasi **non-destruktif** via `esptool read_flash` == `build/*.bin`.
  **P1 backup** `p1_flash_backup/p1_full_flash_4MB.bin` (sha `13e048af…`) **utuh & TIDAK dipulihkan.**
- **Panel Web Serial:** satu kotak "Wi-Fi Stimulus Control" (4 preset + blok Advanced collapsible);
  **UI-only, tanpa reflash** (lihat §12 untuk status validasi end-to-end yang masih menunggu perangkat).
- **Sudah selesai:** karakterisasi protokol, optimasi stimulus, audit pengukuran, integrasi TCP,
  konsolidasi dokumentasi.

---

## 12. Pekerjaan yang Masih Diperlukan

- **Validasi end-to-end panel Web (E2/E3):** uji 4 preset di ESP32 nyata + Brave nyata — **BELUM
  DIUJI** (tidak ada perangkat saat panel dibuat). Prosedur manual ada di laporan `web_stimulus_control`.
- **Ekstraksi fitur timestamp-aware:** implementasi jalur turunan berbasis-`ts_us` (masih rekomendasi).
- **Dataset fall-detection:** pengumpulan take jatuh/non-jatuh terkontrol pada HTTP 64 KB; monitor
  `foreign%` per sesi.
- **Keterbatasan yang belum teratasi:** interferensi `d4:53` tak bisa dihilangkan (satu router, dilarang
  ubah); plafon ~36 fps; amplitudo per-subcarrier tak lewat HMS.
- **Kosmetik (tidak diperbaiki, terdokumentasi):** baris "enabled" `csi_phy_probe` mencetak literal
  `%02x:…` (pakai `MACSTR` tanpa `MAC2STR`) — bug tampilan, tidak memengaruhi akuisisi.

---

## 13. Referensi Implementasi

Path source program utama yang relevan (bukan laporan eksperimen yang dihapus):

- `examples/esp-radar/wifi_sensing_demo/main/web_serial_monitor.c` — parser HMSCMD, `apply_stimulus_mode`
  (mutual-exclusion), `handle_set_stimulus_mode`, `handle_set_tcp_stimulus`, telemetri
  `send_stimulus_state` (`mode/running/csi_hz_x10/free_heap/http.*/tcp.configured_*/dns.*`), `send_ack`.
- `examples/esp-radar/wifi_sensing_demo/main/ht_stimulus.c/.h` — stimulus HTTP Cloudflare + ping.
- `examples/esp-radar/wifi_sensing_demo/main/tcp_stimulus.c/.h` — stimulus TCP non-blocking;
  default `TCP_STIMULUS_CONC_DEFAULT 4 / INT 10 / TO 50 / PORT 80→53`.
- `examples/esp-radar/wifi_sensing_demo/main/dns_stimulus.c/.h` — stimulus DNS query.
- `examples/esp-radar/wifi_sensing_demo/main/csi_phy_probe.c/.h` — probe CSI-callback (histogram sumber).
- `examples/esp-radar/wifi_sensing_demo/main/app_main.c` — bootstrap FSM, stimulus defaults OFF.
- `examples/esp-radar/wifi_sensing_demo/tools/web_serial_monitor.html` — panel "Wi-Fi Stimulus Control".
- `examples/esp-radar/wifi_sensing_demo/tools/csi_recorder.js` + `csi_recorder_server.py` — recorder dua-file v3.
- `fall_detection/dataset_io.py` + `train_activity_model.py` — extractor frame-indexed (baseline) & training.
- `examples/esp-radar/wifi_sensing_demo/recordings/README.md` — format dataset.
