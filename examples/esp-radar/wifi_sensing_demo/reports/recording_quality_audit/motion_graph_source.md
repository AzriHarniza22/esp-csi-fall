# Motion Graph — Sumber Data dan Alur Rendering

## Ringkasan

Motion Graph pada halaman web hasil recording **bukan** dihitung dari payload CSI
(`valid_b64` / `raw_b64`). Graph dibentuk dari **telemetri firmware** yang sudah
dipre-proses oleh esp_wifi_sensing di ESP32 dan disimpan ke `meta.json` saat
recording berlangsung.

---

## 1. File dan Fungsi yang Relevan

| File | Fungsi | Peran |
|---|---|---|
| `tools/web_serial_monitor.html` | `drawMotionGraph(samples)` | Render tiga kurva + state strip |
| `tools/web_serial_monitor.html` | `drawMotionStateTimeline(samples)` | Render strip hijau/merah |
| `tools/web_serial_monitor.html` | `drawLineChart(canvas, series, fmt, times, key)` | Engine chart umum |
| `tools/web_serial_monitor.html` | `showRecordingVisualization(recording, "motion")` | Load data dari meta.json, panggil draw |
| `tools/csi_recorder.js` | `makeMotionSample(message)` | Validasi & normalisasi satu sample |
| `esp_wifi_sensing/src/esp_wifi_sensing.c` | `hms_process_csi_sample()` | Hitung `smooth_scaled` (firmware) |
| `esp_wifi_sensing/src/esp_wifi_sensing.c` | `esp_wifi_sensing_fsm_get_diag()` | Susun struct diag → `smooth_scaled`, `enter_level_scaled`, `exit_level_scaled` |
| `managed_components/.../web_serial_monitor.c` | `write_sample_line()` | Serialize diag → JSON serial stream |

---

## 2. Alur Data End-to-End

```
CSI payload dari router
        │
        ▼ (firmware)
esp_radar → amplitude per subcarrier = hypot(imag, real)
        │
        ▼ (firmware · esp_wifi_sensing)
First-order exponential smoothing:
  diff = raw - smooth_scaled
  coef = smooth_coef  (×2 jika diff < 0, capped at 1.0)
  smooth_scaled += diff * coef          ← nilai yang diplot
        │
        ▼ (firmware · esp_wifi_sensing)
Threshold computation:
  enter_level_scaled = baseline_scaled + enter_threshold
  exit_level_scaled  = baseline_scaled + exit_threshold
        │
        ▼ (firmware · web_serial_monitor.c)
JSON serial line: {"type":"sample","ts_ms":...,"smooth_scaled":...,"enter_level_scaled":...,"exit_level_scaled":...,"motion_status":...}
        │
        ▼ (browser saat recording)
CsiRecorder.makeMotionSample() — validasi + simpan ke csiRecorder.motionSamples[]
        │
        ▼ (saat take selesai)
Disimpan ke meta.json → events.motion_samples[]
        │
        ▼ (browser saat review)
showRecordingVisualization() → baca meta.json → drawMotionGraph(samples)
```

---

## 3. Formula Rendering (Browser)

### Y-axis — Transformasi satu-satunya:
```javascript
smooth_scaled      / 1000  → kurva hijau  (#7bffb6)
enter_level_scaled / 1000  → kurva oranye (#ffb454), threshold masuk aktif
exit_level_scaled  / 1000  → kurva merah  (#ff6b81), threshold keluar aktif
```
Pembagian `/1000` adalah satu-satunya transformasi browser. Nilai asli adalah
integer firmware (milli-unit internal). Tidak ada smoothing, interpolasi,
resampling, atau normalisasi tambahan di browser.

### X-axis — Time:
```javascript
tFirst = samples[0].ts_ms
tLast  = samples[N-1].ts_ms
position = (sample.ts_ms - tFirst) / (tLast - tFirst)   // 0..1
```
Sumbu X menampilkan offset dari sampel terakhir ke awal, label: `-10.0s … 0.0s`.
Tidak ada resampling; spasi X proporsional langsung ke `ts_ms`.

### Y-axis range:
```javascript
min = 0 (hardcoded)
max = stickyRange(key, 0, Math.max(...values))   // decay per redraw, CHART_SCALE_DECAY=0.995
```

### State strip (canvas `recMotionState`):
```javascript
motion_status === true  → #24543e (hijau tua = ACTIVE)
motion_status === false → #58313a (merah tua = INACTIVE)
```
Lebar setiap segment proporsional ke selang waktu ke sampel berikutnya.

---

## 4. Sumber Data dalam meta.json

```
meta.json
  └─ events
       └─ motion_samples[]          ← primary (schema v3)
            ├─ ts_ms                : uint64, epoch ms dari esp_timer_get_time()/1000
            ├─ peer                 : string, MAC AP
            ├─ motion_status        : boolean
            ├─ smooth_scaled        : uint32, nilai smooth firmware (skala internal)
            ├─ enter_level_scaled   : uint32, baseline + enter_threshold
            └─ exit_level_scaled    : uint32, baseline + exit_threshold
  └─ motion_samples[]               ← fallback legacy (schema v1/v2)
```

Recording **tanpa `motion_samples`** (direkam sebelum telemetri ini ditambahkan)
menampilkan graph kosong. Semua 130 recording dalam dataset ini memiliki
`motion_samples` di `events`.

---

## 5. Apa yang TIDAK Digunakan Motion Graph

- `frames.csv` / `valid_b64` / `raw_b64` — tidak dibaca untuk motion graph
- Amplitude delta antar-frame CSI — tidak dihitung di browser untuk motion graph
- `callback_timestamp_us` / `rx_ctrl_timestamp_us` — tidak digunakan
- Subcarrier selection, `first_word_invalid`, `lltf_len` — tidak relevan

Motion graph adalah tampilan output **detector firmware**, bukan re-analysis CSI.

---

## 6. Formula Firmware (esp_wifi_sensing)

```c
/* Per CSI frame yang masuk */
int32_t diff_raw_smooth = (int32_t)raw - (int32_t)ch->smooth_scaled;
float smooth_coef = ch->cfg.smooth_coef;         // konfig sensitivity
if (diff_raw_smooth < 0) {
    smooth_coef *= 2.0f;                          // turun 2× lebih cepat
    if (smooth_coef > 1.0f) smooth_coef = 1.0f;
}
ch->smooth_scaled += (int32_t)(diff_raw_smooth * smooth_coef);

/* Threshold lines */
enter_level_scaled = baseline_scaled + enter_threshold;
exit_level_scaled  = baseline_scaled + exit_threshold;

/* motion_status (FSM) */
// ACTIVE  jika smooth_scaled > enter_level_scaled (setelah debounce)
// INACTIVE jika smooth_scaled < exit_level_scaled  (setelah debounce)
```

`raw` adalah nilai CSI yang diproses oleh `esp_radar_motion_dec_compute()` —
yaitu varian dari mean absolute deviation across subcarriers dalam sliding window,
bukan single-frame amplitude.

---

## 7. Implikasi untuk Analisis

1. `smooth_scaled` adalah output **after** exponential smoothing dengan
   `smooth_coef` yang bergantung pada sensitivity setting. Nilai ini sudah
   mengalami low-pass filtering firmware — bukan raw amplitude.
2. `enter_level_scaled` dan `exit_level_scaled` bergerak bersama `baseline_scaled`
   — baseline drift menggeser kedua threshold.
3. `motion_status` adalah output FSM dengan debounce — transisi tidak langsung
   mengikuti `smooth_scaled` melewati threshold.
4. Sampling rate motion_samples ≈ 60ms (∼17 Hz) berdasarkan interval `ts_ms`
   dalam data nyata, jauh lebih lambat dari CSI frame rate (~30–50 ms/frame).
5. Untuk recording Nov 4 (89 recording), audio speech synthesis gagal tetapi
   motion telemetry tetap berjalan normal.
