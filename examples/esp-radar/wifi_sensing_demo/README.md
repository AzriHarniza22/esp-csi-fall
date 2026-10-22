# ESP Wi-Fi Sensing Demo

This directory contains a self-contained ESP-IDF demo used to exercise the
`esp_wifi_sensing` component in a realistic bring-up flow.

The example combines:

- Wi-Fi STA connection and sensing FSM startup
- Three monitored channels: the connected AP plus two fixed peer MAC addresses
- A status LED policy for quick visual feedback
- A lightweight serial protocol that can be consumed by the browser-based Web
  Serial monitor in `tools/web_serial_monitor.html`

The example follows the same public workflow recommended by the component:

1. Create the FSM with `esp_wifi_sensing_fsm_create()`.
2. Add the AP channel and two extra peer channels.
3. Register ACTIVE / INACTIVE callbacks.
4. Start the FSM with `esp_wifi_sensing_fsm_control(..., ESP_WIFI_SENSING_FSM_CTRL_START, NULL)`.
5. Optionally keep CSI traffic flowing with `esp_wifi_sensing_fsm_ping_router_start()`.

## Directory Layout

- `main/app_main.c`: example entry point and sensing FSM wiring
- `main/led_control.*`: LED backend and state mapping
- `main/web_serial_monitor.*`: line-oriented serial protocol for diagnostics and runtime tuning
- `tools/web_serial_monitor.html`: browser UI for charts, live diagnostics, and configuration

## Build and Run

Open the `wifi_sensing_demo` directory as an ESP-IDF project, then build and
flash it in the usual way:

```bash
idf.py set-target <chip>
idf.py flash monitor
```

The example uses `protocol_examples_common` for Wi-Fi provisioning, so configure
your Wi-Fi credentials before flashing if your local workflow requires it.

## Web Serial Monitor

When `CONFIG_ESP_WIFI_SENSING_WEB_SERIAL_ENABLE=y`, the firmware emits
line-delimited JSON messages prefixed with `HMS:` and accepts commands prefixed
with `HMSCMD `. This allows ordinary ESP logs and structured diagnostics to
share the same serial port.

The browser UI currently focuses on the minimum public diagnostics exported by
the component: `jitter_value`, `smooth_scaled`, `enter_level_scaled`,
`exit_level_scaled`, `state`, and `init_stage`.

The serial monitor also exposes the main runtime controls used by the demo:

- `HMSCMD HELLO`
- `HMSCMD START_STREAM`
- `HMSCMD STOP_STREAM`
- `HMSCMD FSM_START`
- `HMSCMD FSM_STOP`
- `HMSCMD RESET_BASELINE`
- `HMSCMD GET_CFG ALL`
- `HMSCMD GET_CFG <peer>`
- `HMSCMD GET_RUNTIME`
- `HMSCMD SET_AMPLITUDE_LOG on`
- `HMSCMD SET_AMPLITUDE_LOG off`
- `HMSCMD SET_CFG <peer> motion_sensitivity=<float> active_jitter_min=<float> active_filter_ms=<ms>`
- `HMSCMD WIFI_CONFIG_HEX <ssid_hex> <password_hex>`
- `HMSCMD WIFI_DISCONNECT`
- `HMSCMD WIFI_INFO`
- `HMSCMD START_CSI_STREAM`
- `HMSCMD STOP_CSI_STREAM`
- `HMSCMD SET_CSI_PERIOD <0 or 20..1000>` (`0` emits every CSI callback; this is a demo-serial extension, not an ESP-IDF API)

Here `<peer>` can be either the demo name (`AP`, `MAC_1`, `MAC_2`) or the peer
MAC string.

To use the browser monitor:

1. Build and run the firmware.
2. Open `tools/web_serial_monitor.html` in a Chromium-based browser.
3. Connect to the board through Web Serial.
4. Inspect live channel diagnostics or update channel parameters from the page.

If the browser blocks `file://` access for Web Serial, or you want to save CSI
dataset takes under `recordings/`, serve the tools directory with the recorder
server (not `python -m http.server`, which cannot accept uploads):

```bash
cd tools
python3 csi_recorder_server.py
```

Then open `http://127.0.0.1:8000/web_serial_monitor.html`.

The browser monitor includes a Wi-Fi Configuration panel for runtime-only
connection changes. The password is sent as UTF-8 hex over the command channel,
cleared from the form after submission, and is not printed in device logs.

The Raw CSI panel is disabled by default to keep low-spec computers responsive.
Start it explicitly when needed, choose a period of 20-1000 ms, and select
amplitude, real, or imaginary display. Each selected subcarrier is drawn as an
individual curve over the bounded CSI history, matching the `console_test`
visualization model. Step `5` is the low-cost view used by `console_test`; step
`1` draws every available subcarrier (for example, all 52 LLTF subcarriers).
CSI frames are sent as base64 with a sequence number, source MAC, RSSI, raw
length, filtered `valid` payload, `rx_ctrl` radio fields, device `ts_us`, data
type, and dropped-frame counter.

The CSI Recorder panel follows the `console_test` collect window: label, countdown,
duration, and optional repeat count. Each take writes `*.csi_data.csv` (official
`CSI_DATA` header), `*.iq.csv` (I/Q per subcarrier), and `*.meta.json` under
`recordings/<label>/`. The Recordings panel lists, deletes, heatmaps, and
plots those files. Its amplitude heatmap puts recorded frames on the x-axis and
subcarriers on the y-axis, with color showing `|I+jQ|`; the color scale clips
the 2nd and 98th percentiles to keep outlier frames from hiding typical
variation. On this hardware, HT stimulus usually has to be running or the take
is marked incomplete.

## Demo Behavior

- The AP BSSID channel is treated as the primary channel for LED feedback.
- The LED blinks while Wi-Fi is disconnected.
- When the AP channel becomes ACTIVE, the LED turns fully on.
- When the AP channel returns to INACTIVE, the LED fades out.
- The two fixed peer channels remain visible in logs and the browser monitor as
  extra sensing references.
