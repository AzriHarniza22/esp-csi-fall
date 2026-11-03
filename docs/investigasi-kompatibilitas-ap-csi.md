# Investigasi — Kompatibilitas AP dan CSI ESP32 Classic

Tanggal: 2026-11-02. Firmware: P1 (`2679aec7…`, tetap terpasang). ESP-IDF v5.5.3.

## Ringkasan satu paragraf

ESP32 **menerima** frame dari AP `f8:73:1a:59:23:f4` di lapisan jaringan (ICMP
Echo Reply masuk, ping gateway `ping_reply_hz=10.00 ping_to=0`), dan radio
**mengamati** channel itu di jalur promiscuous (`promisc=1`, `promis` 52–83
frame/2 s). Namun mesin CSI **tidak lagi menghasilkan callback untuk frame yang
bersumber dari AP**. Semua CSI callback yang terjadi dalam kondisi sekarang
berasal dari **uplink perangkat lain ke AP** (STA `48:45:20:ee:be:b1` dan
`d4:53:2a:61:a2:c1` dengan `dmac=f8:73:1a:59:23:f4`), bukan dari AP sebagai
sumber. Karena sumbernya bukan AP, `esp_radar_select_peer` menolak semuanya
(`no_peer`), `okmac` tetap `00:00:00:00:00:00`, dan tidak ada frame yang
di-queue. Ini bukan regresi image (rollback dan P1 identik), bukan kegagalan
asosiasi, dan bukan kegagalan penerimaan radio secara umum.

Kerangka empat lapisan yang dipakai dokumen ini:

| Lapisan | Pertanyaan | Status sekarang | Bukti |
|---|---|---|---|
| 1. Stack | Frame AP diterima Wi-Fi/network stack? | **YA** | ICMP reply 95/110 @5 Hz; `ping_reply_hz=10.00` |
| 2. Promiscuous RX | Frame teramati monitor/promiscuous? | **YA** (frame channel, mayorotas management) | `wifi state: … promisc=1`; `promis=52–83`, `promist{m=50–60 d=2–23}` |
| 3. CSI callback | Frame **dari AP** membangkitkan callback CSI? | **TIDAK** | `srcs{…}` hanya berisi STA lain; `okmac=00:00` |
| 4. Filter esp-radar | Frame lolos seleksi peer? | **TIDAK** (karena tidak ada src=AP) | `no_peer=rx`, `queued=0`, peers[0]=AP |

Kegagalan berpindah ke **batas lapisan 2→3 khusus arah downlink AP**.

---

## 1. Fakta konfigurasi AP

### 1.1 Baseline yang bekerja (recording lama)

Dari `recordings/walking/20261031T012305Z_walking_001.meta.json`:

- `ap_mac = f8:73:1a:59:23:f4`, ssid `kos mutiara `.
- **`wifi.channel = 11`**, `secondary_channel = null` (implikasi 20 MHz).
- `recording.frames = 304`, `complete = true`, `dropped_on_device = 0`.
- `quality.sampling_intervals_ms.mean_ms = 32.941`, median 24.236 → efektif ~30 Hz.
- `quality.first_word_invalid_frames = 304` (100 %) — lihat §3.6, ini kuirk
  hardware klasik ESP32 yang **jinak**, bukan penyebab.
- IP device saat itu `192.168.1.41`; `csi_period_ms = 0` (unthrottled).

Rekaman `empty_room` juga ~305 frame (field `wifi.channel` kosong pada format
meta lama, jadi tidak dipakai sebagai sumber channel).

### 1.2 Kondisi sekarang (diagnosis A/B, 2026-11-01)

- AP `kos mutiara` `f8:73:1a:59:23:f4` berpindah ke **channel 1 (2412 MHz)**,
  **HT20 (20 MHz)** per diagnosis host sebelumnya (`reports/prioritas1_smoke/`).
- Ada **radio kedua pada kanal yang sama**: `kos mutiara _plus`
  `d4:53:2a:61:a2:c1`, channel 1, WPA1/WPA2. Ini sumber STA uplink yang
  muncul di `srcs{}`.
- Device Espressif lain yang sangat kuat ikut teroverhear:
  `48:45:20:ee:be:b1` dengan **rssi −20 dBm**, `dmac=f8:73:1a:59:23:f4`
  (baris `csi_cb window` `ab_p1_final_20261101T154901Z.log`). Ini perangkat
  **lain** dari board ini (`ip neigh` memetakan 192.168.1.10 → `44:1d:64:fa:57:b8`).
- Device terasosiasi (state `GOT_IP`), ip `192.168.1.10`, bssid `f8:73:1a:59:23:f4`.

### 1.3 Perbedaan utama dengan eksperimen lama

| Aspek | Baseline (bekerja) | Sekarang (starved) |
|---|---|---|
| Kanal AP | 11 | 1 |
| Bandwidth | 20 MHz (HT20) | 20 MHz (HT20) — sama |
| BSSID | `f8:73:1a:59:23:f4` | sama |
| Radio kedua sekanal | tidak tercatat | `kos mutiara _plus` @ ch1 |
| Transmitter tetangga kuat | tidak tercatat | `48:45:20:ee:be:b1` @ −20 dBm |
| CSI sumber=AP | ya (`okmac=f8:73…`, queued>0) | **tidak pernah** (`okmac=00:00`) |
| Frame/recording | ~304 / 10 s | 0 |

Perubahan paling mencolok antara "bekerja" dan "starved" adalah **kanal AP
pindah 11 → 1**, dan lingkungan co-channel bertambah (radio kedua + satu STA
Espressif sangat dekat). Bandwidth tetap 20 MHz, BSSID sama, asosiasi hidup.

> **Catatan verifikasi hari ini (2026-11-02):** scan aktif `iw dev wlan0 scan`
> ditolak (`Operation not permitted`, perlu root) dan `nmcli --rescan auto` tidak
> menampilkan `kos mutiara` karena host saat ini terasosiasi ke AP lain
> (`Ini kan my`, `e2:0a:68:1d:b5:16`, channel 11 — lihat `/tmp/iw_scan.txt`).
> Karena batasan melarang reset/flash, kondisi kanal AP **dari sisi device** tidak
> diukur ulang hari ini; §1.2 memakai observasi A/B terakhir (2026-11-01) dan
> ditandai sebagai "tercatat", bukan "diverifikasi hari ini".

---

## 2. Analisis PHY dan kelayakan frame (frame eligibility)

Sumber otoritatif: `esp_wifi_types_native.h` ESP-IDF v5.5.3 (struct
`wifi_pkt_rx_ctrl_t` dan `wifi_csi_info_t`). Kutipan field (nomor baris file):

- L41 `sig_mode: 2` — *"0: non HT(11bg) packet; 1: HT(11n) packet; 3: VHT(11ac)"*.
- L39 `rate: 5` — *"PHY rate encoding … **Only valid for non HT(11bg) packet**"*.
- L43 `mcs: 7` — modulasi hanya berarti bila HT(11n).
- L52 `stbc: 2` — 0 non-STBC, 1 STBC.
- L62 `secondary_channel: 4` — 0 none, 1 above, 2 below (menandai 40 MHz).
- L123 `first_word_invalid` — *"first four bytes of the CSI data is invalid …
  due to **hardware limitation**"*.
- L97–100 konfigurasi sumber CSI: `lltf_en` (legacy long training field),
  `htltf…`, `stbc_htltf2_en` (STBC HT-LTF), `ltf_merge_en` (rata-rata LLTF+HT-LTF).

Implikasi yang **didukung source**:

1. **CSI dihitung dari field training OFDM (LLTF / HT-LTF).** Hanya PPDU berbasis
   OFDM yang memuat training field ini. Frame **802.11b DSSS/CCK** tidak memiliki
   LLTF OFDM, sehingga **tidak dapat** menghasilkan CSI. Ini dasar teknis dari
   watchdog bawaan proyek (`web_serial_monitor.c:72–81`: "When the AP rate-control
   drops our link to legacy CCK rates no OFDM frames arrive and the driver never
   produces CSI").
2. **`sig_mode` memformat payload CSI.** `activity_classifier.c:49–75`
   (`has_supported_lltf_layout`) menerima hanya `cwb == 20MHZ` dan
   `secondary_channel == NONE`, lalu menuntut tata letak byte yang cocok untuk
   NON_HT (LLTF saja) atau HT (LLTF+HT-LTF, +STBC-HT-LTF bila STBC). Frame 40 MHz
   atau dengan secondary channel, atau STBC yang tidak cocok, **gagal layout**
   (log `esp_radar.c:895` "value fail … secondary_channel … stbc").
3. **Agregasi (A-MPDU).** CSI adalah properti **per-PPDU** (satu estimate dari
   LTF di awal PPDU), bukan per subframe. Counter `phy{agg=…}` mengonfirmasi
   banyak CSI callback membawa agregat. Ini memengaruhi laju frame efektif, bukan
   kelayakan dasar.
4. **Keterbatasan driver klasik.** `first_word_invalid` dan `rate` "only valid
   non-HT" menandai bahwa jalur ESP32 classic punya korral bentuk data CSI yang
   berbeda dari ESP32-S3/C5. Baseline menunjukkan **100 % frame** ber-
   `first_word_invalid=true`, dan tetap `complete=true` — jadi quirk ini bukan
   sumber kegagalan.

Klaim eksplisit yang **TIDAK** dibuat dokumen ini (karena belum ada bukti
per-frame dari AP): bahwa satu tipe frame (mis. "semua downlink kini CCK")
adalah penyebab tunggal. Yang terbukti hanya "frame bersumber AP tidak
menghasilkan callback" (pernyataan sisi **CSI**). Sisi promiscuous **sebagian**
mengukur — `DL(fromAP)` mencatat `sig_mode`/`rate`/`rssi` untuk **frame data
yang Address 1-nya = MAC STA ini** (lihat §3.3, §8.6 A2, §8.8), **bukan** frame
yang teratribusi ke BSSID AP; ToDS/FromDS tidak dibaca sehingga **arah** frame
tidak tertentu, dan `UL(toAP)` — yang predikatnya menguji **Address 2 = TA**
terhadap MAC kita — **bukan** bukti uplink lengkap (nilai 0 pada 424/424 window,
penyebabnya belum diketahui, §8.3). Kode `rate` belum terpetakan,
jadi semua ini belum bisa mengubah H1 menjadi fakta.

Data PHY dari frame yang **memang** menghasilkan CSI callback (bukti positif):

| Log | `phy{agg ht legacy}` | `sig{0/1/2/3}` | `rate hist` |
|---|---|---|---|
| `ab_oldfw` (rollback) | agg=4 ht=4 legacy=0 | sig1=4 | {11=4} |
| `ab_p1_final` (P1) | agg=10 ht=15 legacy=24 | sig0=24 sig1=15 | {8=5 11=15 12=19} |

Artinya mesin CSI **hidup** dan berhasil mem-produce CSI untuk uplink HT (sig1)
dan non-HT (sig0) dari perangkat tetangga — tetapi nol untuk sumber AP. Jadi
"ESP32 tidak bisa CSI sama sekali" **salah**; yang benar "ESP32 tidak memperoleh
CSI dari AP pada kondisi ini".

> **Koreksi Ronde 2 (konsistensi)**: kalimat sebelumnya menafsirkan `rate`
> 8/11/12 sebagai "laju OFDM 11g". Penafsiran itu **tidak didukung dokumen** dan
> ditarik: field `rate` hanya 5 bit dan v5.5.3 menyebutnya "PHY rate encoding …
> only valid for non HT(11bg) packet" tanpa tabel pemetaan, jadi 8/11/12 **tidak
> bisa** dipetakan ke Mbps maupun ke CCK-vs-OFDM (§8.7/§8.8). Perhatikan juga
> `rate{11=…}` muncul pada window yang seluruhnya `sig1` (HT) — di mana field ini
> memang tidak bermakna. Yang tetap sah disimpulkan dari tabel: **ada** frame
> non-HT dan HT yang menghasilkan CSI dari sumber selain AP.

---

## 3. Analisis promiscuous RX vs CSI callback

### 3.1 Lapisan-lapisan dan tempat pengukurannya

- **Promiscuous/monitor** diukur oleh task preproc (`esp_radar.c:1324–1392`,
  tag `csi_preproc`): `promis`, `promist{m,c,d}` (management/control/data),
  `psig{0,1,2}` (sig_mode frame yang tertangkap monitor), dan status
  `esp_wifi_get_ps` / `esp_wifi_get_promiscuous` (`wifi state:`).
- **Callback CSI** diukur oleh `esp_radar_csi_rx_cb` (`esp_radar.c:901–1000`,
  tag `esp_radar_csi_rx_cb`, diregistrasi lewat `esp_wifi_set_csi_rx_cb`,
  L575): `rx`, `no_peer`, `filtered`, `queued`, `srcs{MAC(n)}`, `okmac`,
  `phy{agg,ht,legacy,sig2}`.
- **Seleksi peer / filter** terjadi di `esp_radar_select_peer` (L703–754):
  peer harus cocok `info->mac` (exact) atau wildcard. `peers[0]` = AP.

### 3.2 Yang dibandingkan (window 2 s)

GOOD (pre-flash, `raw_pre_flash_20261101T143203Z.log`):
```
promis=83  promist{m=60 c=0 d=23}  psig{0=83}      -> monitor hidup
csi_cb: rx=9 no_peer=9 okmac=f8:73:1a:59:23:f4      -> AP PERNAH jadi sumber (okmac terisi)
```
STARVED (P1, `ab_p1_final_20261101T154901Z.log`):
```
promis=52  promist{m=50 c=0 d=2}  psig{0=52}        -> monitor tetap hidup (mayoritas mgmt/beacon)
csi_cb: rx=39 no_peer=39 srcs{48:45:20:ee:be:b1} okmac=00:00:00:00:00:00  -> nol src=AP
```

Perbedaan bukan pada "radio buta" — **monitor tetap menangkap frame** (52–83/2 s)
dan **callback CSI tetap terjadi** (rx 4–39) — melainkan pada **siapa sumbernya**:
pada kondisi starved tidak satu pun callback berasal dari AP, padahal AP terdaftar
benar sebagai `peers[0]`.

### 3.3 Metadata promiscuous yang tersedia vs dibutuhkan

Field yang tersedia di `wifi_csi_info_t`/`rx_ctrl` **sudah cukup** untuk membedakan
empat lapisan, **kecuali** untuk arah downlink AP:

- MAC sumber/tujuan (`mac`, `dmac`): tersedia, dipakai `srcs{}`/`okmac`.
- Tipe/protokol frame (`sig_mode`): tersedia (0/1/3).
- `secondary_channel`, `stbc`, `mcs`, `rate`, `rssi`: tersedia.
- Sequence & panjang (`payload_len`, `len`, `seq_id`): tersedia.
- Channel & RSSI: tersedia (`rx_ctrl.channel`, `rssi`).
- **Format per-PPDU arah downlink AP**: *sebagian teramati* di jalur promiscuous,
  **tidak** teramati di jalur CSI (tidak ada callback AP untuk di-intip).
  Counter `DL(fromAP)`/`UL(toAP)` di preproc (`esp_radar.c:1363`) **dikoreksi
  [TERUKUR] pada koreksi Ronde 2**: klaim lama "membaca 0 pada SEMUA log" **keliru**.
  Dari 424 baris `DL(fromAP)` di `reports/` (grep, tanpa filtering): **209 window
  non-zero**, 215 window nol. Yang konsisten nol adalah **`UL(toAP)`** (0 baris
  non-zero) — dan itu **bukan** bukti "tidak ada uplink". Predikatnya menguji
  **Address 2 = TA** terhadap MAC kita (`pl+10`..`15`, `esp_radar.c:627`), slot
  yang memang berisi MAC STA pada frame uplink BSS infrastruktur — jadi predikat
  itu **sah**, dan nolnya adalah **pengamatan yang penyebabnya belum diketahui**
  (§8.3), bukan konsekuensi struktur. `DL(fromAP)` **bukan** counter mati — tetapi
  tetap punya batas interpretasi yang keras (§8.3: hanya frame **data** dengan
  **`Address1 == s_my_mac`** di `pl+4`..`9`, ToDS/FromDS tidak diperiksa, dipecah
  per `sig_mode` bukan per BSSID), dan ia **tidak** menjawab pertanyaan
  "frame dari AP dalam format apa" untuk frame yang Address 1-nya bukan
  MAC STA ini.
  Rincian per-file: **§8.8**. Kesimpulan lama bahwa "arah downlink tidak dapat
  dipakai sebagai bukti negatif" **dipertahankan hanya untuk sisi CSI**, bukan
  untuk sisi promiscuous.

### 3.4 Konsekuensi untuk lapisan 4

`esp_radar_select_peer` hanya mengeset `okmac` bila `info->mac` = peer. Karena
`srcs{}` tidak pernah memuat AP, `select_peer` selalu mengembalikan `no_peer`,
`filtered`/`queued` = 0. Jadi lapisan 4 bukan penyebab independen; ia hanya
memperkuat lapisan 3 (tidak ada masukan ber-sumber-AP).

### 3.5 Rancangan instrumentasi tambahan — **DITERAPKAN Ronde 2 (lihat §8.2/§8.3)**

> Status berubah: ronde 2 memasang instrumentasi PHY. **Opsi B (callback
> promiscuous kedua) DITOLAK** — slot promiscuous tunggal sudah dimiliki
> `esp-radar` LOCKED (dipasang satu kali di `esp_radar_csi_init()`, lihat §8.3);
> menambah callback sendiri akan menimpa akuntansi `csi_preproc` yang justru
> dipakai sebagai pembanding. Yang dipasang adalah varian **Opsi A** (hook CSI
> `main/`), dengan catatan cakupan di §8.3. Detail di **§8.2 Rancangan
> instrumentasi PHY downlink**.

Untuk menutup satu-satunya celah (distribusi PHY arah downlink AP) **tanpa**
menyentuh patch `esp-radar` LOCKED, opsi terkecil:

- **Opsi A (non-invasif, di `main/`)**: pada `web_serial_monitor_csi_callback`
  (yang menerima `wifi_csi_filtered_info_t` **setelah** peer lolos) tambahkan
  penghitung `sig_mode`/`rate`/`stbc`/`secondary_channel` **per arah** (bandingkan
  `info->mac` vs `info->dmac` dengan MAC AP). Tidak mengubah algoritma, tidak
  mengubah filter. Tapi ini **hanya** melihat frame yang lolos — tidak membantu
  bila tidak ada src=AP sama sekali. **Inilah yang dipasang ronde 2** sebagai
  `main/csi_phy_probe.c`, dengan batas observasi pada butir pertama di atas menjadi
  **bagian tetap dari namanya**, bukan cacat yang bisa diperbaiki dengan penamaan.
- **Opsi B (diajukan sebelum koreksi — DITOLAK, lihat §8.3)**: pasang callback
  promiscuous **sendiri** di `main/` yang
  mencatat `rx_ctrl` (sig_mode/rate/stbc/secondary) untuk **setiap** frame dengan
  `addr2 == AP` (downlink) di lapisan 2, **sebelum** gerbang CSI. Ini membuktikan
  apakah downlink AP hadir dalam format OFDM/HT (layak CSI) atau CCK (tidak layak).
  Ditolak karena slot promiscuous tunggal sudah dimiliki esp-radar LOCKED (§8.3);
  karakterisasi promiscuous karenanya tetap menjadi milik log `csi_preproc`.

### 3.6 Catatan `first_word_invalid`

Baseline 304/304 `first_word_invalid=true` namun valid & `complete` — kuirk
hardware klasik yang sudah ditangani hilir (kata pertama dibuang). Tidak terkait
starved; disebut agar tidak disalahtafsir sebagai kerusakan payload.

---

## 4. Penyebab error Ping profile

### 4.1 Gejala

`E ping_sock: esp_ping_get_profile(412): unmatched data size for profile 5`
muncul berulang. Pada window P1 60 s (`ab_p1_final_20261101T154901Z.log`):
**671 dari 671** baris `ping_sock` adalah "unmatched data size for **profile 5**"
— tidak ada profile lain. Frekuensi ≈ ping-success rate (10 Hz → ±600).

### 4.2 Pemetaan enum (0-based, `ping_sock.h:94–104`)

`SEQNO=0 TOS=1 TTL=2 REQUEST=3 REPLY=4 **IPADDR=5** SIZE=6 TIMEGAP=7 DURATION=8`.
Profil 5 = `ESP_PING_PROF_IPADDR`.

### 4.3 Ukuran yang diharapkan vs dikirim

Di `ping_sock.c` (`esp_ping_get_profile`):
```
case ESP_PING_PROF_IPADDR:
    from = &ep->recv_addr;  copy_size = sizeof(ep->recv_addr);   // recv_addr: ip_addr_t
...
ESP_GOTO_ON_FALSE(size >= copy_size, ESP_ERR_INVALID_SIZE, ..., "unmatched data size for profile %d", profile);
```
`ep->recv_addr` bertipe **`ip_addr_t`**. Dengan `CONFIG_LWIP_IPV4=y` **dan**
`CONFIG_LWIP_IPV6=y` (sdkconfig:1568–1569), `ip_addr_t` = struct `{ u8_t type;
union { ip6_addr_t ip6 /*u32[4]=16B*/; ip4_addr_t ip4; } u_addr; }` →
`sizeof(ip_addr_t) = 20` (union 16 + type + align; minimal ≥16).

Pemanggil salah — `esp_wifi_sensing/src/esp_wifi_sensing.c:833`:
```c
esp_ping_get_profile(hdl, ESP_PING_PROF_IPADDR, &ev.ip4_addr, sizeof(ev.ip4_addr));
```
`ev.ip4_addr` adalah **`uint32_t`** (`esp_wifi_sensing.h:174`) → `sizeof = 4`.
Ukuran yang diharapkan ≥16, yang dikirim 4 → `4 >= 16` **false** → `ESP_ERR_INVALID_SIZE`.
Inilah penyebab tunggal. Dipicu pada **setiap** ping-success callback → spam serial.

Pemanggil profil lain **benar** (cocok uint32_t vs uint32_t): SIZE→`uint32_t size`
(L829, `recv_len` uint32_t), TIMEGAP→`uint32_t timegap` (L830,
`elapsed_time_ms` uint32_t), REQUEST/REPLY/DURATION semuanya uint32_t. Hanya IPADDR
yang salah. Karena itu hanya "profile 5" yang muncul.

### 4.4 Perbaikan minimal — **DITERAPKAN Ronde 2 (lihat §8.1)**

Ambil ke `ip_addr_t` sungguhan lalu ekstrak IPv4-nya, sehingga buffer cukup besar:
```c
ip_addr_t addr;
if (esp_ping_get_profile(hdl, ESP_PING_PROF_IPADDR, &addr, sizeof(addr)) == ESP_OK &&
        IP_IS_V4_VAL(addr)) {
    ev.ip4_addr = ip4_addr_get_u32(ip_2_ip4(&addr));   /* network-order IPv4 */
} else {
    ev.ip4_addr = 0;                                    /* unavailable, bukan 0.0.0.0 sah */
}
```
Catatan desain:
- Mengubah **hanya** pemanggil di `esp_wifi_sensing.c` (bukan interval/timeout ping,
  bukan algoritma sensing, bukan `esp-radar`).
- `sizeof(ev.ip4_addr)` diganti `sizeof(addr)` agar `size >= copy_size` lolos.
- Membedakan "IP tidak tersedia" dari IPv4 nyata dengan flag hasil, selaras
  pembedaan unavailable-vs-nol yang dipakai metadata.
- Verifikasi yang diusulkan: rebuild, `grep` log harus 0 "unmatched data size",
  dan ping tetap `ping_reply_hz` normal; uji unit host untuk konversi IPv4.

Dampak bila tidak diperbaiki: bukan kerusakan ping (ping tetap jalan), melainkan
**polusi stream serial ±10 baris/s** yang menggeser buffer `rawSerialLines` dan
mengotori recording — relevan dengan §5.

---

## 5. Hipotesis yang masih terbuka

Dipisahkan dari fakta. Semua butuh §6 untuk memutuskan.

- **H1 — Laju downlink AP turun ke 802.11b CCK (tidak layak CSI).** Didukung
  hipotesis bawaan firmware (`web_serial_monitor.c:72–81`) dan oleh laju uplink
  tetangga yang seluruhnya OFDM/HT. Status **dikoreksi [TERUKUR]** (lihat §8.8):
  alasan lama penolakan — "`DL(fromAP)` selalu 0, instrumentasi tak terhubung" —
  **keliru**; counter itu terisi pada banyak window. Re-analisis artefak log yang
  ada menunjukkan downlink-ke-diri pada kanal 1 **selalu** tercatat `sig0`
  (non-HT) dan **nol pada `sig1` (HT)** di semua file era itu, sedangkan log
  2026-10-31 (kanal 11, BSSID sama) memperlihatkan `sig1>0` pada 8 window.
  Ini **memperkuat** H1/H2 tetapi **belum membuktikannya**: `sig_mode=0` mencakup
  11b **dan** 11g (§8.4); pemisahnya adalah kode `rate`, dan kode `rate` yang
  tercatat (5, 6, 11) **tidak bisa** dipetakan ke Mbps maupun CCK-vs-OFDM dari
  dokumen yang ditemukan — field-nya 5 bit ("PHY rate encoding",
  `esp_wifi_types_native.h:38`) sehingga bit7 (flag OFDM) pada nilai RATE 802.11
  terpotong. `DL(fromAP)` juga hanya menghitung frame **data ber-Address 1 =
  MAC STA ini** — tanpa atribusi BSSID dan tanpa pemeriksaan ToDS/FromDS, jadi
  bukan klasifikasi arah yang tertentu — dan data lama ini
  **retrospektif/tidak terkontrol** (hari, posisi,
  beban trafik, dan firmware berbeda). **Unggul, kini dengan indikasi promiscuous,
  tetap belum terbukti — E1 tetap diperlukan.**
- **H2 — Efek pindah kanal 11→1 + co-channel.** Kanal 1 kini berbagi dengan radio
  `_plus` dan STA Espressif kuat (−20 dBm). Bisa membuat AP menyetir link ke laju
  robust (mendukung H1) atau mengubah dwelling RX. Korelasi kuat
  (pindah kanal bersamaan dengan starved) tapi kausalitas belum diisolasi.
- **H3 — Format 40 MHz / STBC / A-MPDU pada downlink.** Akan tertolak
  `has_supported_lltf_layout`. Belum terukur arah AP.
- **H4 — Asimetri jalur RX: CSI hanya menempel pada frame yang di-overhear
  promiscuous (uplink orang lain), tidak pada unicast downlink ke STA asosiated
  pada kondisi ini.** Konsisten dengan data (srcs hanya uplink), tapi perlu §6.
- **DITOLAK:** regresi image P1 (rollback & P1 identik, §A/B), kegagalan asosiasi,
  kegagalan alokasi diagnostics (semua `barrier_ok/tx_drained=true`), dan "radio
  tidak menerima frame" (ping masuk).

---

## 6. Rekomendasi eksperimen berikutnya (minimal, belum dijalankan)

**Eksperimen E1 — isolasi kanal/bandwidth (paling murah, paling menentukan).**

- Firmware: P1 tetap (tanpa flash/rollback).
- Konfigurasi CSI, power save, promiscuous: **identik** dengan hari ini.
- Stimulus: `icmp_ping` 10 Hz (bawaan device), sama seperti baseline.
- Ruang kosong/statis; **tanpa** aktivitas manusia.
- Satu variabel: **kanal AP**. Ukur dua arm bolak-balik:
  - arm-11: kembalikan router ke **channel 11 / 20 MHz** (kondisi baseline),
  - arm-1: biarkan **channel 1** (kondisi starved).
- Metrik utama per arm — **dipisah per domain, lihat §8.6**:
  1. **Domain A (promiscuous, tag `csi_preproc`, window 2 s)**: `promist{m/c/d}` +
     `psig{0/1/2}` (agregat, tanpa atribusi BSSID; `c` selalu 0 — control frame
     tidak diserahkan driver, §8.2) dan `DL(fromAP) sig{}`/`rate{}`/
     `rssi{}` (frame **data** dengan **Address 1 = MAC STA ini**) — **bukan**
     tabel src-MAC, karena sisi promiscuous tidak punya tabel source-MAC (§8.2);
  2. **Domain B (CSI callback)**: `csi_ap_frame_count` (frame dari AP), `queued`,
     `srcs{…}`/`okmac` (esp-radar, window 2 s), dan tabel `csi_src` `csi_phy_probe`
     (window 1 s);
  3. ~~histogram dari callback promiscuous sendiri (§3.5 Opsi B)~~ — **DITOLAK**
     (§8.3): slot promiscuous dimiliki esp-radar LOCKED. Distribusi PHY downlink
     diambil dari kolom Domain A, bukan dari probe `main/`.
- Keputusan:
  - Downlink-ke-diri (A2, = frame data ber-Address 1 = MAC kita) **kembali**
    tercatat `sig1` (HT) di arm-11 dan hilang di
    arm-1 → kanal/co-channel (H2) pemicu; **pertahankan router di channel 11/20
    MHz** untuk seluruh eksperimen korelasi. (Re-analisis §8.8 sudah menunjukkan
    pola ini secara retrospektif, tetapi tidak terkontrol.)
  - Bila histogram `DL(fromAP)` pada arm-1 didominasi `sig0` **dan** kode `rate`
    sudah terpetakan ke laju CCK → H1 (rate-control AP); solusinya forcing rate
    OFDM di AP atau AP uji lain. Selama `rate` belum terpetakan, `sig0` **belum**
    membuktikan CCK (§8.7).
  - Bila downlink-ke-diri **tak pernah** muncul bahkan di arm-11 dengan ping
    berjalan → **bukan** bukti tunggal "masalah sniffer": `DL=0` punya banyak
    sebab alternatif (§8.3/§8.7 — tidak ada frame data yang Address 1-nya MAC
    kita di window itu, filter driver, `sig_mode>=3`, `s_my_mac` basi, reset tanpa
    krit-sek). Periksa `promist{d}`/`psig{}` dan `ping_ok` lebih dulu sebagai
    pembanding, lalu pakai AP uji kedua yang diketahui kompatibel sebagai kontrol.
    Yang **tidak** boleh disimpulkan dari `DL=0`: "AP tidak mengirim", "AP memakai
    format tertentu", atau (dari `UL=0`) "STA tidak mengirim uplink".

**AP uji lain**: disetujui hanya bila E1 arm-11 gagal memulihkan downlink HT (A2),
atau bila mengubah router produksi tidak diperkenankan. Rekomendasi: siapkan satu
AP 2.4 GHz terkontrol (channel 11/20, WPA2, HT20) sebagai ground truth.

**Pra-syarat**: perbaikan §4.4 (error profile 5) disetujui & diterapkan lebih
dahulu agar stream serial bersih selama eksperimen korelasi (mengurangi risiko
queue overflow karena spam `ping_sock`).

---

## 7. Batasan yang dipatuhi ronde ini

Tidak flash/rollback, tidak reset ESP32, tidak mengubah CSI config/power save/
promiscuous/patch `esp-radar` LOCKED, tidak ada recording baru, tidak ada HTTP
eksperimen, tidak ada Ping 50/100 Hz, tidak ada Eksperimen B, tidak mengubah
router. Tidak ada perubahan kode: §4.4 dan §3.5 adalah **rancangan** menunggu
persetujuan. Artefak sumber yang dikutip:
`esp_wifi_types_native.h`, `ping_sock.h`, `ping_sock.c`, `esp_wifi_sensing.c`,
`esp_wifi_sensing.h`, `esp_radar.c`, `activity_classifier.c`, `web_serial_monitor.c`,
`recordings/walking/*.meta.json`, `reports/prioritas1_smoke/ab_*.log`,
`raw_pre_flash_*.log`, `sdkconfig`, `/tmp/iw_scan.txt`.

> **Catatan Ronde 2**: batasan ronde 1 di atas tetap benar untuk ronde 1. Ronde 2
> (persetujuan eksplisit user) **menerapkan** §4.4 dan varian §3.5 Opsi A sebagai
> kode, tetap tanpa flash/reset/recording/router-change dan tanpa menyentuh
> `esp-radar` LOCKED. Lihat §8 untuk detail implementasi, verifikasi, dan
> keterbatasan bukti ronde 2.
---

## 8. Ronde 2 — Implementasi diagnostik & verifikasi (persetujuan user 2026-11-02)

Ronde ini **menerapkan** dua hal yang sebelumnya hanya rancangan (§4.4, §3.5
Opsi A) dan **menyusun protokol E1 tanpa menjalankannya**. Tidak ada flash,
reset, recording baru, perubahan router, HTTP stimulus, Ping 50/100 Hz, atau
perubahan `esp-radar` LOCKED. Penanda klaim dipakai konsisten:

- **[FAKTA-DOK]** — persis dari dokumentasi resmi (dikutip + nomor baris).
- **[FAKTA-SRC]** — dari kode sumber pada versi terpasang (IDF v5.5.3 / file repo).
- **[TERUKUR]** — dari log/output build/tests ronde ini.
- **[HIPOTESIS]** — belum terbukti.

### 8.1 Perbaikan Ping profile

**File**: `esp_wifi_sensing/src/esp_wifi_sensing.c` (vendored, **tidak** LOCKED).

Bug (lihat §4.3): `[FAKTA-SRC]` pemanggilan lama
`esp_ping_get_profile(hdl, ESP_PING_PROF_IPADDR, &ev.ip4_addr, sizeof(ev.ip4_addr))`
mengirim buffer `uint32_t` (4 B). `[FAKTA-DOK]` `ping_sock.c:392–394` menetapkan
`copy_size = sizeof(ep->recv_addr)` dengan `recv_addr` bertipe `ip_addr_t`
(ping_sock.c:46), dan `:412` menolak `size < copy_size` dengan
`ESP_ERR_INVALID_SIZE` → "unmatched data size for profile 5". Konfigurasi
dual-stack `[FAKTA-SRC]` (`CONFIG_LWIP_IPV4=y` **dan** `CONFIG_LWIP_IPV6=y`,
sdkconfig:1568–1569) membuat `sizeof(ip_addr_t)` = 20 B. `[TERUKUR]` 671/671
error (laporan §4.1).

Perbaikan yang diterapkan — helper bertipe benar + guard waktu-kompilasi:
```c
static void hms_ping_read_reply_ip4(esp_ping_handle_t hdl, uint32_t *out_ip4)
{
    ip_addr_t reply_addr;
    static_assert(sizeof(reply_addr) >= sizeof(ip_addr_t),
                  "ESP_PING_PROF_IPADDR buffer must be at least sizeof(ip_addr_t)");
    *out_ip4 = 0;
    memset(&reply_addr, 0, sizeof(reply_addr));
    if (esp_ping_get_profile(hdl, ESP_PING_PROF_IPADDR, &reply_addr, sizeof(reply_addr)) != ESP_OK)
        return;
    if (IP_IS_V4_VAL(reply_addr))
        *out_ip4 = ip4_addr_get_u32(ip_2_ip4(&reply_addr));   /* network-order IPv4 */
}
```

Pemenuhan butir user:
1. Tipe buffer = kontrak API (`ip_addr_t`). ✔
2. Ukuran yang benar (`sizeof(ip_addr_t)`). ✔
3. Cek tipe (`IP_IS_V4_VAL`) **sebelum** ekstrak IPv4. ✔
4. Tanpa cast tak-aman — hanya macro lwip `ip_2_ip4`/`ip4_addr_get_u32`. ✔
5. Kompat IPv4/IPv6: reply IPv6/unset → `ip4_addr = 0` (bukan IPv4 sah). ✔
6. **Evaluasi keperluan profil IPADDR**: `[FAKTA-SRC]` field `ev.ip4_addr`
   mengalir ke monitor tetapi **tidak punya kolom** pada rekaman ping serial, dan
   target ping selalu = gateway (`hms_ping_start` memakai `fsm->ping_gw`,
   `esp_wifi_sensing.c:900–901`). Artinya nilai IPADDR **redundan** — bisa
   diperoleh dari gateway. Keputusannya: **profil tetap dibaca dengan benar**
   (bukan dihapus) agar field diagnostik valid tanpa menyentuh struktur event
   atau konsumen `main/`; penghapusan total ditunda karena mengubah kontrak
   publik komponen dan tidak dibutuhkan untuk memperbaiki error. ✔
7. Guard buffer: `static_assert(sizeof(reply_addr) >= sizeof(ip_addr_t))` membuat
   kesalahan ukuran terdeteksi saat build, bukan runtime. ✔
8. Interval/timeout/payload/FSM **tidak** berubah — hanya pembacaan profil. ✔
9. Konfigurasi CSI **tidak** berubah. ✔

Verifikasi: `[TERUKUR]` build lolos (`BUILD_EXIT=0`), nol warning pada file ini.
Runtime (0 "unmatched data size") **belum** diverifikasi karena itu butuh flash —
ditunda ke persetujuan terpisah.

### 8.2 CSI callback PHY probe (dikoreksi dari "instrumentasi PHY downlink")

> **Koreksi Ronde 2**: modul ini **bukan** instrumen downlink lengkap. Ia hanya
> mengamat **subset frame yang layak-CSI** — yaitu frame yang sudah mencapai
> `web_serial_monitor_csi_callback()` setelah seleksi-peer + rekonstruksi LTF oleh
> esp-radar. Ia **bukan** sniffer promiscuous dan **tidak** melihat frame yang
> ditolak sebelum callback. Nama file/simbol diubah dari `phy_probe` →
> `csi_phy_probe` agar batas observasi terlihat dari namanya; token perintah
> `HMSCMD PHYPROBE` dipertahankan sebagai alias.

**Modul**: `main/csi_phy_probe.c` / `main/csi_phy_probe.h`, di-registrasi di
`main/CMakeLists.txt`. Diaktifkan hanya lewat `HMSCMD PHYPROBE on|off|get`
(default **OFF**), jadi nol overhead di jalur normal.

**Dua domain statistik yang harus dipisah — jangan disamakan:**

| Domain | Pemilik | Yang diamati | Di mana (window) |
|---|---|---|---|
| **Promiscuous RX** | `esp-radar` (LOCKED) | Frame yang **diserahkan driver** pada konfigurasi filter saat ini — yaitu **data + management saja**; **control frame tidak pernah diterima** callback (filter default). **Sebelum** gerbang CSI, jadi termasuk frame yang **tidak** menghasilkan CSI | Tag `csi_preproc`: `promis=`, `promist{m/c/d}`, `psig{0/1/2}`, `data sig0/sig1 rate{} mcs{}`, `OURS …`, `DL(fromAP)`/`UL(toAP)`/`rssi{}`, `wifi state:` (2 s) |
| **CSI callback** | `esp-radar` (`esp_radar_csi_rx_cb`) + `main/` (`csi_phy_probe`) | Hanya frame yang **lolos** ke callback CSI | Tag `esp_radar_csi_rx_cb` "csi_cb window: … srcs{…} okmac=…" (2 s) **dan** tag `csi_phy_probe` baris `csi_cb scope` + `csi_src` (1 s) |

**Pembedaan yang mudah salah:** sisi **promiscuous tidak punya tabel
source-MAC** — `esp_radar_promis_cb` (`esp_radar.c:595–641`) hanya mengisi
` s_promis_type`/`s_promis_sig`/`s_pd_rate`/`s_pd_mcs`/`s_dl_*`/`s_ul_*`/`s_me_*`.
Tabel src-MAC (`srcs{…}` / `s_src_mac`, `esp_radar.c:643+`) dan tabel `csi_src`
probe keduanya berada di **domain CSI** — jadi keduanya tidak bisa dipakai
sebagai bukti "AP ada/tidak di udara".

**Kolom `c` pada `promist{m/c/d}` tidak pernah berisi control frame [TERUKUR].**
`esp-radar` tidak memanggil `esp_wifi_set_promiscuous_filter()` maupun
`_ctrl_filter()` sama sekali, jadi filter bawaan yang berlaku. `[FAKTA-DOK]` IDF
v5.5.3 `docs/en/api-guides/wifi.rst:2700`: "By default, it will filter all
802.11 **data and management** frames to the application. If you want to filter
the 802.11 **control** frames, the filter parameter … should include
`WIFI_PROMIS_FILTER_MASK_CTRL` type …" — dalam kata-kata dokumen, kata "filter"
berarti **diserahkan ke aplikasi**, dan control frame butuh opt-in. Sejalan:
`esp_wifi.h:935` ("default filter is to filter all packets **except**
WIFI_PKT_MISC") dan `esp_wifi.h:960` ("default filter is to filter **none**
control packet"). Cross-check artefak: **422 baris terukur** `promist{…}` di
`reports/` semuanya membaca `c=0`; dua sisanya adalah format string mentah
(`m=%lu c=%lu d=%lu`) yang tertangkap dari file `.bin`, bukan pengukuran. Tidak
ada satu pun `c>0`.
Jadi `promist{m/c/d}` **bukan** cacah "mgmt+ctrl+data di udara", melainkan cacah
frame yang **diserahkan ke callback** — dan ACK/RTS/CTS/BlockAck tidak termasuk.

Probe `main/` **tidak** dapat menentukan karakteristik PHY frame AP yang tidak
sampai ke callback. Untuk pertanyaan "apakah AP mengirim frame dan dalam format
apa" sumbernya adalah kolom **Promiscuous RX** di atas (milik esp-radar), dengan
catatan `DL(fromAP)` (§8.3/§3.3).

Titik pasang probe: `web_serial_monitor_csi_callback()`, dipanggil tepat setelah
`csi_ap_frame_count` dan sebelum gerbang throttle stream, sehingga **setiap**
frame yang menghasilkan CSI tercatat, tak hanya yang dikirim.

Yang dipantau per frame (histogram berbatas tetap, bukan log per-frame):
- **Kategori arah** (saling-lepas, prioritas): `from_ap` (`src==peers[0].mac`) /
  `to_self` (`dmac==MAC STA sendiri`, di-cache sekali via `esp_wifi_get_mac`) /
  `other`. Sumber = `info->mac` (sumber frame CSI), bukan alamat udara bebas.
- **Frame type/subtype** (best-effort) dari `info->info->hdr` bila terisi;
  `mgmt/ctrl/data/unknown`, plus counter `bc_mc` (addr1 group-address). Bila
  `hdr==NULL` → `unknown`.
- **PHY**: `sig_mode`, `rx_format`, `bandwidth (cwb)`, `stbc`, `aggregation`,
  `secondary_channel`, `rate[16]`, `mcs[8]`, `channel[16]`, `rssi` bucket 5 dB,
  `first_word_invalid`, `payload_len` (min/max/avg).
- **Histogram per source-MAC × PHY mode**: tabel tetap 8 slot; setiap slot
  menyimpan MAC, jumlah, `sig_mode` & `bandwidth` terakhir, dan flag `is_ap`.
  Kehabisan slot → ganti slot terjarang + counter `src_overflow` (granularitas
  yang hilang tetap terlihat).
- `rx_seq` (sequence control 802.11) tersedia di `[FAKTA-SRC]`
  `esp_wifi_types_native.h:129` tetapi **tidak** di-histogram (12-bit, memutar →
  tidak bermakna sebagai distribusi); dipakai untuk konfirmasi kehadiran stream.

Pelaporan: **task terpisah**, `csi_phy_probe_report()` dipanggil dari
`web_serial_monitor_task` pada kadens status yang sudah ada
(`STIMULUS_STATUS_PERIOD_MS = 1000 ms`), lewat `ESP_LOGW` (tag `csi_phy_probe`),
**bukan** stream JSON — jadi tidak mengubah protokol serial/skema rekaman.
Window di-reset tiap laporan → interval pengamatan eksplisit (`win=<ms>` dicetak;
baris pertama diberi tanda `csi_cb scope` untuk menegaskan cakupannya).

Race: `csi_phy_probe_record` jalan di task preproc esp-radar (satu-writer);
`csi_phy_probe_report` jalan di task monitor. Kontras ditengahi `portMUX`; report
menyalin+reset snapshot dalam krit-sek singkat, memformat **setelah** keluar.
Callback tetap murah (hanya increment) — sesuai `[FAKTA-DOK]` wifi.rst:2853
("do not do lengthy operations in the callback function ... post ... to a queue").


### 8.3 Kepemilikan callback promiscuous RX

Pemetaan sebelum memasang apa pun (butir "Penting"):

- `[FAKTA-SRC]` Callback promiscuous dipasang **sekali** di
  `esp_radar_csi_init()` (`esp_radar.c:2021–2023`: baca MAC sendiri →
  `esp_wifi_set_promiscuous(true)` → `esp_wifi_set_promiscuous_rx_cb(esp_radar_promis_cb)`). **Koreksi Ronde 3 [FAKTA-SRC]**: klaim lama bahwa
  `esp_radar_csi_keepalive()` me-*re-assert* callback setiap ≥4000 ms **keliru**.
  Fungsi itu ada (`:558–577`) tetapi **dead code / tidak aktif pada build ini**:
  handle timer-nya (`s_csi_keepalive`, `:511`) tidak pernah dibuat lewat
  `esp_timer_create()`, dan referensinya di `esp_radar.c:2030` hanya
  `(void)esp_radar_csi_keepalive;` (statement tanpa efek). Konfirmasi tidak
  langsung dari artefak: kolom `tog=`/`tgf=` pada baris `csi_preproc` **0 di
  semua 424 window**, yaitu counter yang hanya naik kalau timer itu menyala.
- `[FAKTA-SRC]` Yang berjalan tiap window adalah `esp_radar_csi_reassert()`
  (`:579–592`, dipanggil `:1388`): **hanya** `set_csi_config` + `set_csi(true)`.
  Jangan samakan pemasangan callback promiscuous (satu kali, `:2023`) dengan
  re-assert CSI (periodik, `:579`) — keduanya berbeda dan yang kedua tidak
  menyentuh `promiscuous_rx_cb` sama sekali.
- `[FAKTA-SRC]` `esp_radar_promis_cb` (`:595–641`) mengisi histogram internal
  (`s_promis_type`, `s_promis_sig`, `s_pd_rate`/`s_pd_mcs`, `s_dl_sig`/`s_dl_rate`/
  `s_dl_rssi`, `s_ul_sig`, `s_me_sig`/`s_me_rate`) yang di-flush oleh
  `csi_preprocessing_task` (`:1336–1367`) tiap ≥2 s. **Tidak ada** pencacah
  per-source-MAC di sisi promiscuous — `srcs{…}` (`:924`) berasal dari jalur CSI.

**Pemetaan byte header 802.11 pada `pkt->payload`** (`pl` di `esp_radar.c:612`),
dengan `pl` = byte pertama header 802.11:

| Byte | Field 802.11 | Catatan |
|---|---|---|
| `pl + 0`..`1` | Frame Control (LE) | `fc = pl[0] \| (pl[1] << 8)` (`:613`) |
| `pl + 2`..`3` | Duration/ID | tidak dipakai kode |
| `pl + 4`..`9` | **Address 1** (RA) | diuji predicate `DL` (`:615`) |
| `pl + 10`..`15` | **Address 2** (TA) | diuji predicate `UL` (`:627`) |
| `pl + 16`..`21` | **Address 3** (BSSID) | **tidak** diuji kode mana pun |
| `pl + 22`..`23` | Sequence Control | tidak dipakai di sisi promiscuous |
| `pl + 24`..`29` | Address 4 | hanya pada format empat alamat (WDS/mesh) |

> **Koreksi Ronde 4**: tabel versi ronde 3 menempatkan Address 2 di `+6`,
> Address 3 di `+10`, Address 4 di `+16`. Itu **keliru** — tiga alamat itu 6
> byte masing dan dimulai di `+4`, jadi slotnya `+4/+10/+16`, bukan `+4/+6/+10`.
> Kesalahan itu mengubah seluruh interpretasi `UL(toAP)` (lihat di bawah).

Istilah **"downlink-ke-diri"** yang dipakai dokumen ini (§5, §6, §8.6, §8.8)
adalah singkatan untuk kondisi `DL`: frame **data** dengan **Address 1 = MAC
STA ini**. Ia bukan sinonim "frame dari BSSID AP" dan tidak memuat klaim arah.

Dasar pemetaan: IEEE 802.11-2012 Figure 8-30 / slide 15–16 IEEE 802.11 Tutorial
— FC(2), Duration/ID(2), Addr1(6), Addr2(6), Addr3(6), Seq Ctrl(2), Addr4(6).
Bukti internal yang cocok presisi dengannya:
`ruview/firmware/esp32-csi-node/main/csi_collector.c:903–904` menulis
"FC (2) | Duration (2) | Addr1 (6) | Addr2 (6) | Addr3 (6) | SeqCtl (2) = 24
bytes" lalu menempati `ndp_frame[4]` untuk Addr1 dan `ndp_frame[16]` untuk Addr3
(`:917–922`) — buffer 24 B itu dipakai sebagai frame FC-first
(`esp_wifi_80211_tx(..., ndp_frame, 24, false)`), sehingga byte 0 = FC dan
addr2 = `10`..`15`. Di sisi RX: `esp_wifi_types_native.h:112` mendeskripsikan
`payload[0]` sebagai "Data or management payload. Length … described by
`rx_ctrl.sig_len`" (bukan buffer ber-prefix status), dan contoh resmi IDF
`examples/network/simple_sniffer/main/cmd_sniffer.c:146 + :263` menyerahkan
`pkt->payload` apa adanya ke pcap dengan `PCAP_LINK_TYPE_802_11` — hanya sah
bila byte 0 adalah Frame Control.

Kesimpulan kepemilikan: **slot promiscuous dimiliki esp-radar (LOCKED)** dan
diisi **satu kali** saat `csi_init`. Memasang callback kedua di `main/` akan
(a) aktif terus tanpa pernah dipasang-ulang oleh esp-radar (karena keepalive-nya
mati — jadi tidak "ditimpa setiap 4 s" seperti dugaan lama), dan (b) menghapus
akuntansi `csi_preproc` yang justru dibutuhkan E1 sebagai pembanding. **Opsi B
(§3.5) karena itu tetap ditolak**, hanya dengan alasan yang dikoreksi.

Yang dipakai ronde ini: hook **CSI** `main/` yang sudah ada (Opsi A). Ini **tidak**
bersaing dengan slot promiscuous. Konsekuensi cakupan (§8.7): frame yang
**tidak** menghasilkan callback CSI (kasus starved) tidak terlihat dari sini;
sumber satu-satunya untuk frame itu tetap log `csi_preproc` esp-radar.

Peringatan interpretasi `[FAKTA-SRC]` (§3.3). Dua counter arah itu **mendefinisikan
dirinya sendiri secara literal**, dan label `fromAP`/`toAP` pada log adalah
**label, bukan klaim arah**:

- `DL(fromAP)` = jumlah frame **data** (type Data pada `rx_ctrl` **dan** FC
  `version==0 && type==2`, `:604/:614`) dengan **`Address1 == s_my_mac`**
  (`pl+4`..`9`, `:615`). Secara literal: "MPDU data yang Address 1/RA-nya adalah
  MAC STA ini" — frame **ditujukan kepada** STA, **bukan** identifikasi BSSID
  sumber.
- `UL(toAP)` = jumlah frame **data** dengan **`Address2 == s_my_mac`**
  (`pl+10`..`15`, `:627`). **Koreksi Ronde 4**: ronde 3 menyebut slot ini
  "Address 3 = BSSID" dan menyimpulkan predikatnya "mustahil terpenuhi / salah
  alamat". Itu **keliru** akibat tabel offset yang salah. Address 2 adalah TA,
  dan pada frame **uplink** BSS infrastruktur (ToDS=1, FromDS=0) Address 2 memang
  MAC STA — jadi predikat ini **sah secara struktural** dan bisa terpenuhi.
  Address 3 (BSSID) ada di `pl+16`..`21` dan **tidak** pernah dibaca kode.
  `OURS` (`:630`) = konjungsi (OR) kedua tes tersebut.
- Karena **To DS/From DS tidak pernah diperiksa** (`:614` hanya menguji version +
  type), kedua counter **bukan** klasifikasi arah yang definitif:
  - `DL > 0` ⇒ ada frame data dengan **Address 1 = MAC STA**. Tidak membuktikan
    frame itu dari BSSID AP target (peer ESP-NOW/ad-hoc, relai WDS, atau frame
    non-infrastructure bisa cocok), dan tidak membuktikan arah downlink.
  - `UL > 0` ⇒ ada frame data dengan **Address 2 = MAC STA**. Tidak membuktikan
    tujuan uplink adalah AP tertentu (di ad-hoc/WDS Address 2 = source-Addr), dan
    tidak membuktikan arah uplink.
  - Keduanya **belum** membuktikan atribusi per-BSSID.
- **`UL(toAP) == 0` bukan bukti tidak ada uplink yang dikirim STA ini.** Yang
  diukur adalah "tidak ada frame data ber-Address 2 = MAC STA pada window itu".
  Apakah TX milik STA sendiri **terlihat** pada promiscuous RX callback di ESP32
  classic **belum dibuktikan** di proyek ini, dan penyebab `UL = 0` pada 424/424
  window **tidak dapat ditetapkan** dari artefak yang ada: ini tetap
  **[TIDAK DIKETAHUI]**. Kandidat yang **belum diuji** (tidak boleh dikutip
  sebagai penjelasan): tidak diputarkannya frame TX ke callback RX pada target
  ini, atau uplink STA tidak lolos gerbang `:604/:614`. Memutuskannya butuh
  eksperimen TX terkontrol + pembacaan `UL`, bukan pembacaan kode saja.
- **Koreksi [TERUKUR]** atas klaim Ronde 2 bahwa `DL` 0 pada semua log: lihat
  §8.8. Yang benar: `DL` **mengikuti trafik** (window sunyi → 0, window aktif →
  terisi), jadi nol **tidak** boleh dibaca sebagai "AP diam". Observasi
  pendukung: `OURS == DL` pada **387 dari 391** window berpasangan (4 sisanya
  beda tepat 1) — karena `OURS = DL ∪ UL`, ini berarti kontribusi `UL` nol pada
  hampir semua window; itu **pengamatan**, bukan kesimpulan bahwa predikatnya salah.

### 8.4 Identifikasi PHY dan frame type (fakta vs hipotesis)

[FAKTA-DOK] IDF v5.5.3 `docs/en/api-guides/wifi.rst`:
- `:2717` CSI = "channel frequency responses of sub-carriers ... estimated when
  packets are received"; ada **tiga** field: **LLTF**, **HT-LTF**, **STBC-HT-LTF**,
  dipilih menurut tipe paket. Tidak ada field CSI untuk paket tanpa LTF OFDM.
- `:2768` "Except for the IEEE 802.11g mode, all other modes have two LTF
  sequences (LLTF + HT/VHT/HE-LTF)."
- `:2804` `rx_channel_estimate_info_vld==1` ⇒ CSI valid, selain itu invalid.
- `:2853` callback CSI jalan di Wi-Fi task; **STA terhubung hanya menerima paket
  dari AP**, disarankan **sniffer/promiscuous** untuk CSI lebih banyak.

[FAKTA-SRC] `esp_wifi_types_native.h` (ESP32 classic, non-HE):
- `:39` `sig_mode`: 0 = non-HT (11b/g), 1 = HT (11n), 3 = VHT (11ac).
- `:38` `rate`: "Only valid for non HT(11bg) packet" → **rate tidak bermakna
  untuk frame HT**; gunakan `mcs`.
- `:44` `mcs` 0..76; `:45` `cwb` 0=20 MHz/1=40 MHz; `:63` `stbc` (2 bit);
  `:60` `aggregation` (1 bit: 0 MPDU/1 AMPDU).
- `:66–67` `channel` (primary, 4 bit), `secondary_channel` (0 none/1 above/2 below).

**Koreksi salah-tafsir (butir user):** `[FAKTA-SRC]` `sig_mode` adalah **mode
modulasi PHY**, BUKAN tipe frame MAC. `sig_mode=0 (legacy/non-HT)` mencakup
11b **dan** 11g dan **tidak** berarti beacon/management. Frame management
(beacon/assoc) punya tipe MAC sendiri di header (terpisah dari `sig_mode`) dan
dapat dikirim pada PHY OFDM maupun CCK. Karena itu `csi_phy_probe` memisahkan
kategori **frame-type** (dari `hdr`) dan **sig_mode** (dari `rx_ctrl`) dan tidak
menyimpulkan yang satu dari yang lain.

Pembedaan kelayakan CSI:
- OFDM preamble (11a/g LLTF; 11n HT-LTF) ⇒ **ada** sub-carrier response. [FAKTA-DOK]
- 802.11b **DSSS/CCK** tidak memakai sub-carrier OFDM/LLTF ⇒ tidak ada baris CSI
  untuk CCK di tabel dok. [FAKTA-DOK: *tabel tidak mendefinisikan field untuk CCK*].
  Kesimpulan "CCK → nol CSI" adalah **inferensi dari fakta di atas**, dilacak
  sebagai **[HIPOTESIS H1]** sampai histogram **promiscuous** `csi_preproc`
  memberi bukti distribusi per-frame pada AP sungguhan. Catatan: `csi_phy_probe`
  **tidak** bisa membuktikan H1 karena ia hanya melihat frame yang sudah
  layak-CSI — frame CCK yang tidak menghasilkan CSI justru tidak muncul di sana.

### 8.5 Hasil tests dan build [TERUKUR]

- **Node tests**: `csi_recorder.test.js` (semua PASS, exit 0) dan
  `diag_session.test.js` (semua PASS, exit 0). Mencakup verifikasi serial-protocol
  (firmware diag line → ping diterima; fallback wire → csi_diag), **skema frames.csv
  tepat 32 kolom**, dan **meta = tepat dua file**.
- **Python server tests**: `python -m unittest test_csi_recorder_server` → **13 OK**,
  termasuk `test_post_writes_exactly_two_files` dan `test_frames_header_is_32_columns`.
- **Build ESP32 classic** (`idf.py build`, `CONFIG_IDF_TARGET="esp32"`):
  `BUILD_EXIT=0`; **0 warning** pada seluruh log (satu warning
  `-Wtype-limits` pada `aggregation < 2` — field 1-bit — telah diperbaiki).
- **`esp-radar` LOCKED tidak berubah oleh ronde ini**: `git status` pada
  `esp-radar/` bersih (nol edit sesi ini). **Ketidakcocokan checksum dicatat apa
  adanya**: hash `src/esp_radar.c` di disk (`5a4aaabc…`) **tidak cocok** dengan
  `CHECKSUMS.json` (`4d414bf2…`). Ini adalah **kondisi pre-existing yang belum
  direkonsiliasi** (instrumen `csi_preproc`/DL-UL/keepalive yang sudah ter-commit
  sebelum sesi ini), **bukan** perubahan ronde ini. **Tidak diklaim cocok**;
  rekonsiliasinya (regenerate `CHECKSUMS.json` atau pulihkan sumber upstream)
  adalah keputusan terpisah dan **belum** dilakukan.
- **HTTP Cloudflare tidak berubah**: tidak ada kode stimulus-HTTP yang disentuh.
- **Skema rekaman**: tetap 32 kolom, dua file (lihat hasil Node/Python di atas).

### 8.6 Protokol E1 (dijalankan sebagian — lihat §8.6.1: arm-1 terkontrol selesai, arm-11 terblokir)

Tujuan: mengisolasi efek kanal AP terhadap kelayakan CSI downlink (menguji
H1/H2/H4). **Menunggu persetujuan terpisah** untuk flash + jalankan.

| Parameter | Arm 1 | Arm 2 |
|---|---|---|
| Firmware | P1 | P1 |
| Kanal AP | 1 | 11 |
| Bandwidth | 20 MHz | 20 MHz |
| Ping | 10 Hz | 10 Hz |
| Konfigurasi CSI | identik | identik |
| Posisi ESP32 | sama | sama |
| Durasi | 40 s | 40 s |

**Pencatatan konfigurasi aktual router (bukan hanya yang diinginkan)** — wajib
diisi sebelum eksekusi, dari sumber terukur, bukan asumsi:
- `[TERUKUR]` dari sisi AP: `iw`/UI router → channel, bandwidth, dan **mode**
  (b/g/n, min data rate), serta daftar rate yang diizinkan.
- `[TERUKUR]` dari sisi STA: distribusi PHY **promiscuous** tag `csi_preproc`
  esp-radar — `promis=`/`promist{m/c/d}`/`psig{0/1/2}` (agregat, tanpa atribusi
  BSSID; `c` selalu 0 karena control frame tidak diserahkan driver, §8.2) dan
  `DL(fromAP) sig{}`/`rate{}`/`rssi{}` (frame **data** dengan **Address 1 = MAC
  STA ini**, bukan identifikasi BSSID AP) — ditambah scan (`/tmp/iw_scan.txt`
  gaya ronde 1). **Catatan:**
  channel/secondary/bandwidth per-frame **tidak** dicatat sisi promiscuous ini
  (lihat A3). `csi_phy_probe` **melengkapi** dengan sisi CSI-callback, tetapi
  bukan sumber untuk pertanyaan "frame AP di udara".
- Konfigurasi *diinginkan* vs *efektif* ditulis berdampingan; bila beda, catat
  selisihnya eksplisit (mis. AP "HT20" tapi menyetir unicast ke CCK).

**Metrik diukur per domain — dua hal berbeda, jangan disamakan:**

*Domain A — Promiscuous RX (milik `esp-radar` LOCKED, tag `csi_preproc`, window 2 s):*
- A1. Kehadiran frame di udara, **tanpa atribusi BSSID**: `promis=` (total),
  `promist{m/c/d}` (tipe), `psig{0/1/2}` (sig_mode semua pengirim campur aduk).
  **Koreksi Ronde 3:** slot `c` **tidak** mengamati control frame — pada
  konfigurasi ini driver hanya menyerahkan data + management (§8.2), jadi `c`
  konstan 0 dan tidak boleh dibaca sebagai "tidak ada ACK/RTS di kanal".
  Yang tersisa membuktikan "ada trafik mgmt/data di kanal", **bukan** "frame ini
  dari AP target".
- A2. Frame **data yang Address 1 RA-nya = MAC STA ini** (labelnya `fromAP`,
  tetapi itu **bukan** identifikasi frame dari BSSID AP target): `DL(fromAP)
  sig0/sig1/sig2` + `rate{}` + `rssi{}`, serta `OURS`/`UL(toAP)`.
  `UL(toAP)` adalah indikator kecocokan **Address 2 / TA** (`pl+10`..`15`) dengan
  MAC kita — **bukan** bukti uplink lengkap dan **bukan** tujuan AP tertentu,
  karena ToDS/FromDS tidak dibaca (§8.3). Ini proxy paling dekat untuk downlink
  AP pada STA yang asosiated,
  dengan batas: hanya frame data, ToDS/FromDS **tidak** diperiksa sehingga arah
  frame tidak tertentu, hanya `rate<16` / `mcs<8` yang ter-histogram, dan
  **bukan** atribusi per-BSSID. **Koreksi [TERUKUR]**: klaim "terbaca 0 bahkan
  pada baseline" **keliru** (§8.8) — ia terisi pada window bertrafik; nol berarti
  "tidak ada frame data ber-Address 1 = MAC kita di window itu", bukan "AP diam".
- A3. Yang **tidak** ada di Domain A: control frame (tidak diserahkan driver),
  channel/secondary/bandwidth per frame, tabel source-MAC, dan subtype/sequence
  mgmt. Pertanyaan "kanal berapa" dijawab dari sisi AP (`iw`/UI router) atau
  scan, bukan dari `csi_preproc`.

*Domain B — CSI callback (window 1 s `csi_phy_probe` di `main/`; window 2 s
`esp_radar_csi_rx_cb` di esp-radar):*
- B1. Frame yang **berhasil mencapai** jalur CSI: `cat_from_ap`, `csi_ap_frame_count`,
  `queued`, dan tabel sumber-MAC — `srcs{…}`/`okmac` (esp-radar) dan `csi_src`
  (probe). Kedua tabel src-MAC ada di **sisi CSI**, jadi absennya AP di sana bukan
  bukti bahwa AP tidak mengirim.
- B2. Distribusi PHY **dari** frame layak-CSI (sig_mode, bandwidth, stbc,
  aggregation, rate|non-HT, mcs|HT, channel, secondary_channel, rssi).
- B3. Ping reply & timeout (`ping_reply_hz`, timeout count).

`csi_phy_probe` adalah **instrumen sisi-CSI**, bukan pengganti Domain A. Menyebut
nya "instrumentasi downlink lengkap" adalah **keliru** — ia buta terhadap frame
AP yang tidak lolos ke callback.

**Perbandingan adil**:
- Satu variabel (kanal). Semua lain identik; urutan arm dirotasi (1→11→1) bila
  waktu memungkinkan untuk mengendalikan drift AP/rate-control.
- Posisi ESP32, orientasi antena, beban kanal tetangga, dan firmware dikunci;
  catat sumber interferensi co-channel yang berubah antar arm.
- Analisis **dua tahap, tidak dicampur**:
  1. Bandingkan **Domain A antar-arm**: apakah trafik tampak di promiscuous
     (`promist{d}`, `psig{}`) dan apakah frame **data ber-Address 1 = MAC kita**
     muncul (`DL(fromAP)` A2) beserta distribusi `sig`/`rate`-nya. Batas yang
     harus ditulis di hasil nanti: A tidak melakukan atribusi per-BSSID **dan**
     tidak memeriksa ToDS/FromDS, sehingga "frame AP" di sini berarti "frame data
     yang Address 1-nya adalah MAC STA ini" — bukan frame yang terbukti berasal
     dari BSSID AP, dan bukan klasifikasi arah yang tertentu.
  2. Baru kemudian bandingkan **Domain B terhadap A** dalam arm yang sama: rasio
     (window `DL(fromAP)` non-nol) : (callback CSI sumber-AP). Karena lebar window
     berbeda (2 s vs 1 s), normalisasi ke laju per-detik sebelum membandingkan.
- Keputusan (mengikuti §6):
  - A2 non-nol **dan** B (`cat_from_ap`/`srcs{}`) terisi pada arm-11, keduanya
    hilang pada arm-1 → kanal/co-channel (H2) pemicu.
  - A2 menunjuk downlink didominasi `sig0` (non-HT) sementara arm-11 menunjuk
    `sig1` (HT) → konsisten dengan rate-control AP turun ke laju robust (H1).
    **Ini belum membuktikan CCK** selama kode `rate` belum dipetakan (§8.8):
    `sig0` = 11b **atau** 11g. **Bukti H1 harus berasal dari Domain A, bukan dari
    absennya AP di B.**
  - Hadir di A tetapi tidak pernah di B (kedua arm) → asimetri jalur RX / filter
    peer (H4); perlu AP kontrol kedua.
- **Tidak** menyimpulkan penyebab sebelum data per-frame Domain A ada; absennya AP
  di `csi_phy_probe` **tidak** membuktikan AP memakai CCK atau PHY tertentu.

### 8.6.1 Hasil E1 [TERUKUR] (2026-11-02, P1 terpasang, tanpa flash ulang)

Bukti mentah + laporan gabungan: `reports/e1/20261102T070723Z/` (`arm1_channel1_raw.log`,
`ap_side_scan_kosmutiara.txt`, `arm11_prereq_blocker.txt`, `closure_state.log`, `REPORT.md`).

**Status arm:**

- **arm-1 (kanal 1 / 20 MHz) — EKSEKUSI PENUH, terkontrol.** Kanal dikonfirmasi dua sisi: beacon radio
  host `f8:73:1a:59:23:f4` = channel 1 / 2412 MHz / HT20 (130 Mbit/s) dan `WIFI_INFO` perangkat =
  channel 1, BW20 (PRE & POST; rssi −55→−61). Stimulus `icmp_ping` gateway 10 Hz; window 40 s.
  - **Domain A (`csi_preproc`, window 2 s):** 25 window, 23 non-zero (2 nol = pra-stimulus).
    `DL(fromAP)` total **464** → ternormalisasi **9.3 frame/s**; **sig0=464, sig1=0, sig2=0**
    (100% non-HT, `rate{5}` dominan); `UL(toAP)=0` semua window.
  - **Domain B (CSI callback):** `csi_phy_probe` (window 1 s) 40 report, `cat ap` total **702** →
    **17.6 AP-frame/s**, **seluruhnya sig1 (HT)**, MCS5–7, bw0/20 MHz, stbc1, agg1;
    `srcs{f8:73:1a:59:23:f4(…)}`, `okmac` AP, `csi_ap_frame_count` kumulatif ~907. `to_self=0`.
  - **Ping:** `ping_reply_hz` 10.00→12.50, `ping_to` 0→1, error profile-5 = **0**, reconnect/watchdog = **0**,
    `E(`/Guru = **0**.
- **arm-11 (kanal 11) — TIDAK DIEKSEKUSI, prasyarat tak terpenuhi.** Saat dicek ulang (07:29Z) router
  **masih channel 1**; `iw`/`iwconfig` tidak terpasang, host hanya klien WiFi, tidak ada kredensial admin
  `192.168.1.1`, dan tidak ada BSSID 2.4 GHz pada channel 11 (co-channel `_plus` juga di ch1). Instruksi
  melarang agent mengubah router, dan §6 l.417–419 menggolongkan perubahan router produksi sebagai kasus
  tepi. **Tidak** dibuat arm-11 palsu (channel 1 tidak dilabeli ulang); variabel lain tidak diubah.

**Perbandingan kanal 1 vs 11 (TIDAK terkontrol).** Satu-satunya rekaman kanal 11 adalah artefak lama
§8.8 (`probe_20261031T163333Z.log`, ch11/BW20): Domain A 31 window, 5 nol, `sig0>0` 19, **`sig1>0` 8/31**
(maks 73 HT/window). arm-1 E1: `sig1>0` **0/25**. **Perbedaan ini BUKAN hasil E1 terkontrol** — hari,
posisi, trafik, dan firmware berbeda; jumlah window ping ≠ window `csi_preproc` di file itu. Domain B pada
kanal 11 tidak punya rekaman E1, jadi rasio B:A antar-kanal tidak dapat dihitung.

**Fakta / inferensi / hipotesis:**

- Fakta (terkontrol): pada kanal 1 kini, `DL(fromAP)` Domain A hadir tetapi 100% `sig0`; Domain B **tidak
  starved** (AP frame HT berlimpah lolos callback); `UL=0`; ping ~10 Hz; 0 reconnect. Prasyarat arm-11 tak terpenuhi.
- Inferensi (didukung, satu arm): Domain A dan Domain B mengklasifikasi populasi frame berbeda pada kanal
  sama (A: `sig0` untuk downlink-ke-diri; B: `sig1` HT untuk frame AP yang lolos callback) — konsisten
  perintah §8.6 agar keduanya tidak disamakan.
- Hipotesis (terbuka): H1/H2/H4 **belum diputus**. `sig1` kanal-11 (8/31) vs kanal-1 (0/25) hanya indikasi
  dari data tak-terkontrol, bukan bukti "kanal memengaruhi frame AP ke CSI callback". `sig0` **bukan** CCK
  (`rate` belum terpetakan §8.7); `UL=0` tetap [TIDAK DIKETAHUI].

**Konsekuensi untuk rencana.** Untuk menutup E1 seperti didesain, jalankan pada **AP uji terkontrol kedua**
(2.4 GHz, channel 11/20, WPA2, HT20) **atau** dengan akses admin router kos mutiara untuk memindah kanal
(1→11→1). Catatan observasi: kondisi "starved" yang mendasari §6 **tidak** teramati lagi pada kanal 1 hari
ini (Domain B menerima AP HT), tapi penyebab perubahan (trafik/waktu/interferensi) tidak diisolasi.

### 8.7 Keterbatasan bukti

- **Cakupan `csi_phy_probe` = pasca-seleksi-esp-radar.** Ia melihat hanya frame yang
  **sudah** menghasilkan callback CSI. Frame AP yang ditolak sebelum `main/`
  (kasus starved) **tidak** tertangkap di sini; karena itu **absennya AP pada
  counter `csi_phy_probe` bukan bukti tentang PHY AP** (CCK/OFDM/HT) — hanya bukti
  bahwa tidak ada frame AP yang mencapai callback. Satu-satunya sumbernya untuk
  frame di udara tetap log `csi_preproc` esp-radar. Mengisi celah ini penuh
  (per-BSSID + subtype + seq dari
  header untuk frame **non**-CSI) memerlukan perubahan pada `esp-radar` LOCKED →
  **butuh persetujuan terpisah**, belum dikerjakan.
- **Frame type/subtype & BSSID-header best-effort.** Tergantung `info->info->hdr`
  terisi; bila tidak, tercatat `unknown` (bukan ditebak).
- **Panjang frame MAC 802.11** tidak tersedia di jalur CSI (hanya
  `payload_len`/panjang CSI). Yang dilaporkan sebagai `payload` adalah panjang
  payload paket, bukan panjang bingkai di udara.
- **Runtime ping-fix belum diverifikasi.** Build lolos & logika sesuai kontrak
  dok, tetapi "0 unmatched data size" hanya bisa dipastikan setelah flash.
- **`DL(fromAP)` punya batas interpretasi, tapi bukan counter mati** — lihat §8.8
  untuk koreksi klaim ronde 2. Batasnya: hanya frame **data** (control frame tidak
  pernah diserahkan driver, mgmt tidak dihitung di sini), hanya **Address 1
  (`pl+4`..`9`) = `s_my_mac`** — bukan identifikasi frame dari BSSID AP target —
  ToDS dan FromDS tidak diperiksa sehingga **arah frame tidak tertentu**, tidak
  ada atribusi per-BSSID, hanya `rate<16`/`mcs<8` yang ter-histogram, dan nol pada
  window tanpa trafik cocok.
- **`UL(toAP)` bukan bukti uplink lengkap.** Predikatnya membandingkan
  **Address 2 / TA (`pl+10`..`15`)** dengan MAC kita — slot yang memang berisi
  MAC STA pada frame uplink BSS infrastruktur, jadi predikat ini **sah** dan
  bisa terpenuhi (**Koreksi Ronde 4**: ronde 3 salah menyebutnya Address 3/BSSID
  lalu menyimpulkan "mustahil terpenuhi"; penyebab itu adalah tabel offset yang
  keliru, bukan kode). Yang terukur: 0 pada seluruh artefak (424/424 window).
  **`UL == 0` tidak boleh dibaca sebagai "STA tidak mengirim uplink"**, dan
  penyebab nol itu **belum diketahui**: belum dibuktikan apakah TX milik STA
  sendiri muncul pada promiscuous RX callback di ESP32 classic. Menetapkannya
  butuh eksperimen TX terkontrol, bukan perubahan kode — dan mengubah kode berarti
  menyentuh `esp-radar` LOCKED → **butuh persetujuan terpisah**.
- **Kode `rate` belum terpetakan.** Nilai yang muncul di log adalah 5, 6, 11.
  Field-nya 5 bit dan dokumen v5.5.3 hanya menyebutnya "PHY rate encoding … only
  valid for non HT(11bg) packet" tanpa tabel; bit7 (flag OFDM) pada nilai RATE
  802.11 hilang karena pemotongan bit. **Tidak ada** pemetaan Mbps / CCK-vs-OFDM
  yang bisa dinyatakan sebagai fakta → `sig0` tidak boleh dibaca sebagai CCK.
  Memetakannya butuh TX terkontrol pada rate diketahui (eksperimen baru, butuh
  persetujuan).
- **Angka-angka ini bukan hasil pengukuran E1.** E1 belum dijalankan; semua
  distribusi PHY pada AP masih hipotesis (H1/H2/H4) sampai histogram
  **Domain A** (`csi_preproc` esp-radar) memberi sampel per-frame pada AP target;
  `csi_phy_probe` hanya melengkapi sisi CSI-callback dan tidak bisa menutup
  Domain A.
- **Sumber yang dikutip** (versi terpasang): IDF v5.5.3
  `components/lwip/apps/ping/ping_sock.c`, `components/lwip/lwip/src/include/
  lwip/ip_addr.h`, `components/esp_wifi/include/local/esp_wifi_types_native.h`,
  `docs/en/api-guides/wifi.rst`; repo `esp_wifi_sensing/src/esp_wifi_sensing.c`,
  `esp-radar/src/esp_radar.c` (dibaca-saja), `esp-radar/include/esp_radar.h`,
  `main/web_serial_monitor.c`, `main/csi_phy_probe.c`. Tidak memakai MCP esp-idf v6.0.

### 8.8 Koreksi klaim "`DL(fromAP)` selalu 0" — re-analisis artefak log [TERUKUR]

Koreksi Ronde 2 ini **hanya membaca ulang log yang sudah ada** (grep); tidak ada
flash, reset, perubahan router, E1, atau recording baru.

Klaim §3.3/§8.3/§8.7 ronde 2 — "`DL(fromAP)` membaca 0 pada SEMUA log, termasuk
baseline yang bekerja, artinya instrumentasi arah ini tidak terhubung ke jalur RX
asosiated-STA" — **keliru**. Perhitungan pada `reports/` (semua file yang memuat
baris ini, termasuk yang bertanda biner karena timestamp):

| Ukuran | Nilai |
|---|---|
| Baris `DL(fromAP)` | 424 |
| Baris dengan `sig0=0 sig1=0 sig2=0` | 215 |
| Baris non-zero | **209** |
| Baris dengan `sig0>0` | 193 |
| Baris dengan `sig1>0` (HT) | 16 |
| Baris `UL(toAP)` non-zero | **0** (lihat catatan predikat di bawah) |

Per-file (kanal dibaca dari log itu sendiri; BSSID sama `f8:73:1a:59:23:f4`):

| File | Kanal | window | nol | `sig0>0` | `sig1>0` |
|---|---|---|---|---|---|
| `stimulus_comparison/…/probe_20261031T163333Z.log` | 11 (BW20) | 31 | 5 | 19 | **8** |
| `prioritas1_smoke/ab_oldfw_20261101T153729Z.log` | 1 | 55 | 5 | 50 | 0 |
| `prioritas1_smoke/ab_oldfw_stream_ping_20261101T154135Z.log` | 1 | 39 | 3 | 36 | 0 |
| `prioritas1_smoke/ab_oldfw_stream_on_20261101T154022Z.log` | 1 | 36 | 36 | 0 | 0 |
| `prioritas1_smoke/ab_oldfw_aptraf_20261101T154514Z.log` | 1 | 32 | 3 | 29 | 0 |
| `prioritas1_smoke/ab_p1_final_20261101T154901Z.log` | 1 | 40 | 5 | 35 | 0 |
| `prioritas1_smoke/boot_p1_*`, `raw_probe_144159/144340`, `eksperimen_A/raw_restore_boot` | (tak tercatat) | 20/22/28/28/15 | semua | 0 | 0 |

Yang bisa disimpulkan dari tabel, dan yang tidak:

- **Bisa**: counter **tidak** mati — ia terhubung ke jalur RX dan mengikuti
  trafik data yang Address 1-nya = MAC STA ini (balasan ping turun ke
  perangkat ini). Bukti kuantitatif (join berbasis timestamp, file
  `ab_oldfw_stream_ping`, kanal 1, ping 10 Hz): dari 39 window, **36** punya
  `ping_ok>0` **dan** `sig0>0`, dengan **0** ketidaksinkronan dua arah
  (`ping_ok>0` tapi `sig0=0`: 0; `sig0>0` tapi `ping_ok=0`: 0). Rata-rata
  `sig0 = 19.9` per window vs rata-rata `ping_ok = 18.2` — yaitu ±1 balasannya
  per detik selama window 2 s, sesuai. Pembandingnya, `ab_oldfw_stream_on`
  (kanal 1, **tanpa** stimulus ping) = 36/36 window nol. Jadi nol = "tidak ada
  frame data ber-Address 1 = MAC STA ini di window itu", bukan "AP diam" dan
  bukan "instrumentasi rusak".
  Catatan: window dengan `ping_ok=0` pada file ping ada 3 (sebelum stimulus
  mulai), jadi angka 36/39 bukan 39/39.
- **Bisa**: satu-satunya counter arah yang 0 pada semua log adalah `UL(toAP)`.
  Predikatnya menguji **Address 2 / TA** (`pl+10`..`15`, `esp_radar.c:627`)
  terhadap MAC kita — **slot yang benar** untuk uplink BSS infrastruktur
  (ToDS=1, FromDS=0: Addr1=BSSID, Addr2=STA), jadi predikat ini **sah** dan bisa
  terpenuhi. **Koreksi Ronde 4**: ronde 3 menulis nolnya "sudah terpredict dari
  predikatnya karena ia menguji Address 3/BSSID" — itu akibat tabel offset yang
  keliru dan **tidak** berlaku. Yang benar: `UL=0` pada 424/424 window adalah
  **pengamatan yang penyebabnya belum diketahui**; belum dibuktikan apakah TX
  milik STA sendiri terlihat pada promiscuous RX callback di ESP32 classic.
  Tabel ini karenanya **tidak** memberi informasi tentang ada/tidaknya uplink,
  dan **tidak** mendukung klaim "uplink tidak terjadi" maupun klaim penyebab
  tertentu untuk nol.
  Observasi pendukung: `OURS == DL` pada 387/391 window berpasangan (4 sisanya
  selisih 1) — kontribusi `UL` nol pada hampir semua window; `OURS = DL ∪ UL`.
- **Indikasi (belum bukti)**: satu-satunya file yang memperlihatkan `sig1` (HT)
  pada downlink-ke-diri adalah log kanal 11 — 8/31 window, maksimum 73 frame HT
  per window (2 s). Semua file kanal 1: **0** window `sig1>0` (mis. `ab_p1_final` 0/40,
  `ab_oldfw_stream_ping` 0/39) dan downlink-ke-diri yang sama tercatat di `sig0`
  dengan `rate{5=…}` (juga 6 dan 11). Konsisten dengan H1/H2, **tetapi**
  perbandingan ini **tidak terkontrol**: berbeda hari, posisi, beban trafik, dan
  firmware; pada log 10-31 jumlah window ping (23) bahkan tidak sama dengan
  jumlah window `csi_preproc` (31), jadi fase window-nya tidak sepadan. E1
  (§8.6) tetap diperlukan untuk membandingkan arm-11 vs arm-1 pada kondisi sama.
- **Tidak bisa**: menyebut `sig0` sebagai CCK. Pemisah 11b/11g adalah kode
  `rate`, dan kode itu **belum terpetakan** (§8.7). Menyimpulkan "AP memakai CCK"
  dari tabel ini adalah langkah yang tidak didukung bukti.
- Perintah yang dipakai (dapat diulang, hanya membaca artefak):
  `grep -rah "DL(fromAP)" reports | … | wc -l` dan varian `sig0=[1-9]` /
  `sig1=[1-9]`; per-file: `grep -ac` atas tiga pola yang sama.
