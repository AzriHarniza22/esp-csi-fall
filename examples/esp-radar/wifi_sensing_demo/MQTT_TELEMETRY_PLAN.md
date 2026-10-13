# MQTT 5.0 Telemetry & Remote Control Plan

Status: siap dieksekusi
Target: `examples/esp-radar/wifi_sensing_demo`
Branch: `wifi-sensing-web-serial`

## 1. Tujuan

Membuat ESP32 benar-benar **standalone** — hanya butuh colok power, tanpa laptop —
sambil tetap bisa dimonitor dan dikontrol dari smartphone (Samsung Note 20 Ultra)
dari mana pun, melalui internet.

```
┌─ ESP32 (colok power 5V, tanpa laptop) ───────────────────┐
│                                                          │
│  radar / CSI pipeline  ← TIDAK BERUBAH                  │
│         │                                                │
│         ▼                                                │
│  sensing_task ──sample──► ring buffer                    │
│                                │                         │
│                                ▼                         │
│  mqtt_task (prio 5, stack 4 KB)                          │
│    ├─ publish telemetry  radar/esp32/peer/<n>  QoS 0     │
│    ├─ publish status     radar/esp32/status      QoS 1   │
│    ├─ LWT → broker auto-publish saat putus tak wajar    │
│    ├─ subscribe cmd      radar/esp32/cmd          QoS 1 │
│    └─ publish ack        radar/esp32/ack          QoS 1 │
│                                │                         │
│  csi watchdog (sudah ada, timer 1 s)                    │
└────────────────────┬─────────────────────────────────────┘
                     │ mqtts://…:8883 (TLS, CA diverifikasi)
                     ▼
        EMQX Cloud Serverless  (region asia-southeast1)
                     │ wss://…:8084
                     ▼
        Dashboard di HP (mqtt.js)   ← tidak butuh laptop
```

Prinsip pemisahan: **radar tidak tahu MQTT ada, MQTT tidak tahu radar ada.**
Keduanya hanya berbagi ring buffer.

## 2. Keputusan yang sudah diambil

| # | Keputusan | Konsekuensi |
|---|---|---|
| 1 | Kredensial ESP32 = kredensial dashboard (`esp32`/`esp32`) | Siapa pun yang punya halaman bisa mengirim perintah juga |
| 2 | Kontrol dari HP **wajib** (bukan hanya telemetry) | Fase 2 jadi inti, bukan pelengkap |
| 3 | Kredensial tidak dirotasi (untuk tes) | Tetap disimpan di NVS agar bisa diganti tanpa rebuild |
| 4 | MQTT **5.0** | Pakai `message_expiry_interval` dan `will_delay_interval` |
| — | `WIFI_CONFIG_HEX` **masuk** whitelist | Perangkat bisa diambil alih dari jarak jauh; dimitigasi flag + log |
| — | Prefix topik tetap `radar/esp32` | — |

## 3. Riset: sumber dan temuan

### 3.1 Dokumentasi resmi Espressif

**ESP-MQTT Programming Guide**

- `session.last_will.{topic,msg,qos,retain}` — broker memublikasikan LWT saat
  client memutus koneksi tanpa mengirim DISCONNECT. Ini mekanisme **standar**
  untuk deteksi offline.
- `esp_mqtt_client_publish()` — "might block for several seconds, either due to
  network timeout (10s) or if publishing payloads longer than internal buffer".
  Karena itu publish harus dipanggil dari task khusus, bukan dari task monitor.
- `esp_mqtt_client_enqueue()` — varian non-blocking, pengiriman terjadi di
  mqtt-task.
- QoS 0 dikirim sekali saja; QoS 1/2 di-retransmit sampai ACK diterima.

**ESP-FAQ (MQTT)**

- Keepalive default **120 s**.
- Auto-reconnect default **ON** (`network.disable_auto_reconnect = false`).
- "You only need to care about the memory in this handle" — Wi-Fi putus tidak
  perlu release/re-init MQTT; auto-reconnect menanganinya.
- Rekomendasi: jangan publish atau retry MQTT saat link layer down.
- `esp_mqtt_client_disconnect()` eksplisit agar LWT tidak terkirim pada shut-down
  yang bersih.

**ESP-TechPedia (MQTT)**

- Struktur konfigurasi: broker → verification → credentials → session
  (clean session, heartbeat, **will message** untuk abnormal monitoring).

**Espressif DevCon — Networking Best Practices**

- MQTT tetap mencoba reconnect walau link layer down, karena pustaka ini tidak
  mengetahui event driver. Rekomendasi: hanya bekerja saat link up.

### 3.2 Forum dan issue GitHub

**esp-mqtt issue #133** — task publish yang tetap berjalan saat disconnect
membuat **reconnect macet**. Penyelesainya: hentikan dulu task publish saat
`MQTT_EVENT_DISCONNECTED` diterima.

**esp-idf issue #11330** — keepalive terlalu kecil (`= 2`) memicu
`No PING_RESP, disconnected` berulang. Saran Espressif: **minimal 30 s**; keepalive
5 s masih mendeteksi disconnect dalam 7,5 detik, sedangkan nilai besar mengurangi
beban jaringan.

**MQTT.js README** — "The only protocol supported in browsers is MQTT over
WebSockets, so you must use `ws://` or `wss://`". Dashboard **wajib** WSS.
`protocolVersion: 5` didukung, dengan `resubscribe: true` sebagai default.

### 3.3 Panduan EMQX (operator broker yang dipakai)

- **QoS 0 untuk telemetri, QoS 1 untuk perintah**.
- Payload **kurang dari 1 KB**.
- Reconnect **Wi-Fi dan MQTT ditangani terpisah**.
- Jangan melakukan alokasi memori besar di dalam callback.
- EMQX Cloud Serverless: MQTT TLS **8883**, WebSocket TLS **8084**; port polos
  1883/8083 **tidak didukung**.
- Session expiry: default 2 jam untuk MQTT v3; untuk **MQTT v5** ditentukan oleh
  client lewat `session_expiry_interval`.

### 3.4 API MQTT 5 yang tersedia (IDF 5.5.3)

```c
esp_mqtt5_connection_property_config_t {
    uint32_t session_expiry_interval;   // dipakai
    uint32_t will_delay_interval;       // dipakai
    uint32_t message_expiry_interval;   // dipakai
    uint16_t topic_alias_maximum;
    mqtt5_user_property_handle_t user_property;
    /* ... */
};

esp_mqtt5_client_set_connect_property(client, &prop);
esp_mqtt5_client_set_publish_property(client, &prop);  // message_expiry_interval per publish
esp_mqtt5_client_set_disconnect_property(client, &prop);
```

## 4. Analisis gap: apa yang salah di implementasi sekarang

| # | Cacat | Dampak | Prioritas |
|---|---|---|---|
| 1 | **Tidak ada LWT** | Mati listrik atau crash membuat dashboard tetap menampilkan `online` selamanya. Heartbeat **tidak menolong** karena membutuhkan perangkat tetap hidup | Tinggi |
| 2 | `esp_mqtt_client_publish()` dipanggil dari task monitor | Dokumentasi menyebut bisa **block 10 detik**, sehingga handler HMSCMD dan csi watchdog ikut stall | Tinggi |
| 3 | Publish terikat pada `send_channel_sample()` | Klik **STOP_STREAM** di GUI membuat MQTT ikut mati | Tinggi |
| 4 | `MQTT_PUBLISH_MS` tidak pernah dipakai | Sekitar 6,6 pesan/detik atau **86 MB/hari**; kuota 1 GB habis dalam ~11 hari | Sedang |
| 5 | Tidak ada `client_id` | Pakai default `ESP32_<chipid>`; sulit dipetakan ke MAC, tidak bisa dipakai untuk ACL | Sedang |
| 6 | Credential ada di Kconfig defaults (ter-commit) | Secret bocor ke repo | Tinggi |
| 7 | Tidak ada subscribe, cmd, maupun ack | Tidak ada kontrol dari HP | Rencana |
| 8 | Tidak ada `esp_mqtt_client_disconnect()` saat shutdown bersih | LWT terkirim padahal shut-down normal | Rencana |

## 5. Topik dan QoS

| Topik | Arah | QoS | Retain | Isi |
|---|---|---|---|---|
| `radar/esp32/status` | ESP32 ke broker | 1 | ya | `online`, `ts`, uptime, fw |
| `radar/esp32/peer/AP` | ESP32 ke broker | 0 | tidak | `jitter`, `wander`, `motion`, `presence` |
| `radar/esp32/peer/MAC_1` | ESP32 ke broker | 0 | tidak | idem |
| `radar/esp32/peer/MAC_2` | ESP32 ke broker | 0 | tidak | idem |
| `radar/esp32/cmd` | HP ke ESP32 | 1 | tidak | baris `HMSCMD ...` |
| `radar/esp32/ack` | ESP32 ke HP | 1 | tidak | hasil perintah |

LWT diarahkan ke `radar/esp32/status` dengan payload `{"online":false}`.
Dashboard subscribe wildcard `radar/esp32/peer/+` (1 dari 10 subscription yang
diizinkan EMQX free tier).

Payload telemetri (sekitar 160 byte, jauh di bawah batas 1 KB):

```json
{"peer":"AP","mac":"f8:73:1a:59:23:f4","jitter":0.00271,"wander":0.0,
 "motion":false,"motion_state":0,"presence_ready":true,"ts_ms":258455}
```

## 6. Fase implementasi

### Fase 1 — Konfigurasi dan credential (NVS)

**`Kconfig.projbuild`**

- `MQTT_USERNAME` dan `MQTT_PASSWORD` tetap ada **hanya sebagai fallback boot
  pertama** (tetap `esp32`/`esp32` sesuai keputusan #3), dengan help text yang
  menyatakan credential disimpan di NVS setelah di-override.
- Tambah `MQTT_ALLOW_RECONFIG` (bool, default `y`) untuk mengaktifkan atau
  menonaktifkan `WIFI_CONFIG_HEX` dari MQTT.
- Tambah `MQTT_KEEPALIVE_S` (default 45) dan `MQTT_CLIENT_ID` (default dari MAC).

**`mqtt_publisher.c` — penyimpanan NVS** (mengikuti pola `wifi_runtime_manager.c:554-590`)

```
namespace "mqttcfg" : host, port, user, pass, prefix
```

- Dibaca saat boot; bila kosong dipakai nilai Kconfig, lalu ditulis ke NVS
  (self-heal).
- Perintah baru di `web_serial_monitor.c`:
  - `HMSCMD MQTT_CONFIG <host> <port> <user> <pass> <prefix>` — tulis NVS lalu
    reconnect.
  - `HMSCMD MQTT_STATUS` — balas `{host, port, user, prefix, connected,
    allow_reconfig}` tanpa mengirim password.

**Konfigurasi MQTT 5.0**

```c
.session.protocol_ver  = MQTT_PROTOCOL_V_5,
.session.keepalive     = CONFIG_..._KEEPALIVE_S, /* 45 */
.credentials.client_id = "radar-44:1d:64:fa:57:b8",   /* MAC-based, stabil */
.session.last_will     = {
    .topic  = "radar/esp32/status",
    .msg    = "{\"online\":false}",
    .qos    = 1,
    .retain = true,
},
.broker.verification.certificate = s_ca_cert,   /* DigiCert Global Root G2 */
```

```c
esp_mqtt5_client_set_connect_property(client, &(esp_mqtt5_connection_property_config_t){
    .session_expiry_interval = 300,   /* antrean pesan offline 5 menit */
    .will_delay_interval     = 5,     /* reconnect < 5 s tidak memunculkan "offline" palsu */
    .message_expiry_interval = 300,
});

esp_mqtt5_client_set_publish_property(client, &(esp_mqtt5_publish_property_config_t){
    .message_expiry_interval = 60,    /* data lebih tua dari 60 s dianggap basi */
});
```

**Verifikasi Fase 1**

- `HMSCMD MQTT_CONFIG ...` lalu `MQTT_STATUS` menampilkan konfigurasi tersimpan.
- Setelah reboot, `MQTT_STATUS` menunjukkan NVS terbaca, bukan fallback lagi.
- Log `mqtt_pub: connected to ...:8883` muncul maksimal 5 detik setelah GOT_IP.

### Fase 2 — Kontrol dari HP (inti)

**`web_serial_monitor.c`**

1. Ekspor `handle_command` (saat ini `static` di baris 848) menjadi
   `web_serial_monitor_handle_remote(const char *line, char *ack, size_t ack_len)`.
2. Tambah **capture mode** di `write_line()` (baris 356, corong tunggal untuk
   semua output `HMS:`). Saat aktif, baris ack disalin ke buffer dan tidak
   dikirim ke serial. Dengan begitu semua respons `send_ack()` yang sudah ada
   otomatis ikut tertangkap.

**`mqtt_publisher.c`**

3. Subscribe `radar/esp32/cmd` QoS 1 pada `MQTT_EVENT_CONNECTED` (re-subscribe
   otomatis tiap reconnect, jangan mengandalkan sesi broker).
4. Validasi sebelum dieksekusi:
   - prefix `HMSCMD ` wajib, payload lain ditolak
   - panjang maksimal 128 byte
   - tolak karakter kontrol (`\r`, `\n`, `\0`)
   - rate limit 1 perintah per 500 ms dengan burst 3
5. Pipeline perintah, dijalankan di `mqtt_exec_task` dan bukan di mqtt-task:

```
cmd topic → validasi → antrean mqtt_exec → web_serial_monitor_handle_remote(...)
 │
 ack ke radar/esp32/ack (QoS 1)
```

6. **Whitelist perintah** (sesuai keputusan, `WIFI_CONFIG_HEX` termasuk):

```
SET_STIMULUS, GET_STIMULUS, AUTO_RECONNECT,
GET_CFG, SET_CFG, WIFI_INFO, WIFI_CONFIG_HEX,
WIFI_DISCONNECT, WIFI_RECONNECT, FSM_START, FSM_STOP,
RESET_BASELINE, TRAIN_START, TRAIN_STOP, MQTT_STATUS
```

   `WIFI_CONFIG_HEX` hanya diizinkan bila `MQTT_ALLOW_RECONFIG = y`; selain itu
   ditolak dengan ack eksplisit.

7. Semua perintah dari MQTT dicatat di log dengan sumber `mqtt` untuk audit.

**Verifikasi Fase 2**

| Uji | Cara | Lolos bila |
|---|---|---|
| Kontrol dasar | publish `HMSCMD SET_STIMULUS off` ke `cmd` | burst berhenti, `ack` diterima |
| Reconfig | publish `HMSCMD WIFI_CONFIG_HEX <hex>` | AP berubah, `ack` sukses |
| Security | publish payload tanpa `HMSCMD ` | ditolak dan tercatat di log |
| Rate limit | 10 perintah beruntun | 7 ditolak |
| Reject | `MQTT_ALLOW_RECONFIG = n` lalu `WIFI_CONFIG_HEX` | ditolak, perintah lain tetap jalan |

### Fase 3 — Dekoupling dan task sendiri

**`mqtt_publisher.c`**

1. **`mqtt_task`** (stack 4 KB, prio 5) menangani seluruh publish dan pengiriman
   ack. Tidak pernah publish dari task monitor.
2. **Ring buffer** task-safe (FreeRTOS queue) antara sensing dan `mqtt_task`.
   `mqtt_publisher_publish()` menjadi fire-and-forget, hanya mengisi ring lalu
   langsung kembali.
3. `mqtt_publisher_tick()` dipindah ke `mqtt_task`, tidak lagi dipanggil per-peer
   dari `send_channel_sample()`.
4. **Rate limit publish** memakai `MQTT_PUBLISH_MS` (default 1000 ms), sehingga
   kuota 1 GB bertahan lebih dari satu tahun (sekarang sekitar 11 hari).
5. `esp_mqtt_client_disconnect()` pada shutdown bersih agar LWT tidak terkirim.

**`web_serial_monitor.c`**

6. Hapus pemanggilan `mqtt_publisher_publish()` dan `mqtt_publisher_tick()` dari
   `send_channel_sample()`, ganti dengan pemanggilan yang mengisi ring buffer.

**`app_main.c`**

7. Inisialisasi publisher **setelah** sensing dan stimulus siap, bukan di dalam
   `attach_sensing`.

**Verifikasi Fase 3**

| Uji | Cara | Lolos bila |
|---|---|---|
| Coupling | klik **STOP_STREAM** di GUI | MQTT tetap jalan |
| Blocking | publish saat Wi-Fi lambat | handler HMSCMD dan watchdog tetap responsif |
| Heap | monitor `heap` saat publish | turun kurang dari 2 KB |
| Kuota | 1 jam capture | kurang dari 300 KB |

### Fase 4 — Dashboard (`tools/mqtt_dashboard.html`)

1. `protocolVersion: 5`, `clean: true`, `resubscribe: true`.
2. Properties `messageExpiryInterval: 60000`. Data lebih tua dari 60 detik
   dianggap basi dan tidak digambar ulang.
3. **Fallback** ke `protocolVersion: 4` bila connect MQTT 5 gagal, karena jalur
   browser harus lewat WSS.
4. Panel kontrol, semua lewat topic `cmd` dengan tampilan `ack`:
   - toggle stimulus, toggle auto-reconnect, start/stop FSM
   - reconnect Wi-Fi, ganti SSID (form hex) — ditampilkan sesuai
     `MQTT_ALLOW_RECONFIG`
5. Status badge dengan tiga kondisi:
   - `online` — heartbeat atau LWT diterima kurang dari 20 detik
   - `offline` — LWT `{"online":false}`
   - `no data > 20s` — masih terhubung ke broker tetapi radar tidak publish,
     yang biasanya berarti rate AP turun ke CCK, bukan masalah MQTT
6. Pratinjau respons `ack` untuk lima perintah terakhir.
7. Optimasi mobile: safe-area, tema light/dark, chart ringkas dua menit.

**Verifikasi Fase 4**

- Dari Note 20 Ultra semua tombol bekerja dan status berubah saat ESP32 dicabut.
- Dashboard dibuka dari jaringan lain (mode seluler) tetap connect.

### Fase 5 — Commit setelah stabil

Commit dilakukan setelah keempat fase lulus verifikasi, pada branch
`wifi-sensing-web-serial`. Pesan commit mencakup akar masalah graf beku serta
penambahan telemetri MQTT 5.0.

## 7. Pengujian end-to-end

| Uji | Cara | Lolos bila |
|---|---|---|
| LWT | cabut daya ESP32 | dashboard berubah ke `offline` maksimal 90 detik |
| will_delay | putus Wi-Fi 3 detik | dashboard tidak berkedip ke offline |
| MQTT 5 | mqtt.js | connect dengan `protocolVersion: 5` |
| Kontrol | publish `SET_STIMULUS off` | burst berhenti dan ada ack |
| Security | publish tanpa `HMSCMD ` | ditolak dan tercatat |
| Rate limit | 10 perintah beruntun | 7 ditolak |
| Coupling | STOP_STREAM | MQTT tetap jalan |
| Kuota | 1 jam capture | kurang dari 300 KB |
| Stabilitas | 4 jam | reconnect bersih, data kontinyu |

## 8. Risiko yang diakui

1. **`WIFI_CONFIG_HEX` terbuka** karena kredensial ESP32 sama dengan kredensial
   dashboard. Siapa pun yang punya halaman bisa mengambil alih SSID perangkat.
   Mitigasi: flag `MQTT_ALLOW_RECONFIG`, ack eksplisit, dan log audit.
2. **Kredensial terlihat di HTML.** MQTT dari browser berarti user dan password
   ada di source halaman. Untuk demo ke client, matikan flag di atas atau
   credential terpisah.
3. **Dashboard butuh internet**, berbeda dari mode USB. Ini trade-off dari
   kebutuhan "dari mana pun".
4. **ESP32 tetap butuh router** untuk sensing. Terbukti: tanpa link AP tidak ada
   CSI sehingga graf datar.
5. **Link Wi-Fi bisa drop**, terbukti di `kos mutiara` dengan RSSI turun dari
   -58 lalu hilang. Mitigasi yang sudah ada: retry tanpa batas, watchdog
   reconnect, dan stimulus.

## 9. Referensi

- ESP-MQTT Programming Guide — LWT, blocking pada publish/enqueue, keepalive
- ESP-FAQ MQTT — reconnection, disconnect handling, keepalive
- ESP-TechPedia — struktur konfigurasi client
- Espressif DevCon — handling disconnect dan link-layer awareness
- esp-mqtt issue #133 — task publish versus reconnect
- esp-idf issue #11330 — keepalive terlalu kecil
- MQTT.js README — browser hanya mendukung WSS, `protocolVersion: 5`
- Panduan ESP32 dari EMQX — pembagian QoS, payload di bawah 1 KB, reconnect terpisah
- EMQX Cloud docs — port 8883/8084 dan session expiry