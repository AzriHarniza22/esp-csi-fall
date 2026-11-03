# ESP Wi-Fi Sensing [[中文]](./README_cn.md)

### Overview

`esp_wifi_sensing` is a Wi-Fi sensing FSM component built on CSI data. It is designed for motion-triggered interaction, human presence detection, and interaction integration on ESP devices. Internally it consumes motion features from `esp-radar` and provides multi-channel management, debounce, dynamic baseline tracking, event callbacks, and router-ping-driven sampling.

### Features

- **Multi-channel FSM**: One handle can manage multiple peer/BSSID sensing channels at the same time.
- **Motion detection**: Based on a dynamic baseline with built-in smoothing, adaptive noise estimation, hysteresis, and an ACTIVE hold window to reduce false triggers.
- **Human presence detection**: Per-channel presence detection based on the `waveform_wander` feature.
- **On-site calibration**: Built-in training workflow that learns site-specific wander / jitter thresholds and feeds them into presence detection.
- **Simplified tuning**: Motion sensitivity and presence sensitivity are exposed as independent parameters.
- **Event callbacks**: Register ACTIVE / INACTIVE callbacks for lighting, telemetry, or product logic.
- **Link keep-alive**: Keeps the CSI sampling path active via an internal ping, suitable for router-based scenarios.
- **Diagnostics**: Read FSM state, channel configuration, and motion / presence / training diagnostics for tuning and visualization.

### Supported Chips

- ESP32
- ESP32-S2
- ESP32-S3
- ESP32-C3
- ESP32-C5
- ESP32-C6
- ESP32-C61

### Requirements

- ESP-IDF >= 5.4
- `esp-radar` >= 0.3.3

### Core Data Types

#### `esp_wifi_sensing_fsm_handle_t`

Opaque FSM handle. One handle manages multiple sensing channels, and each channel is identified by a peer MAC address.

#### `esp_wifi_sensing_fsm_state_t`

Public channel state exposed to applications:

- `ESP_WIFI_SENSING_FSM_STATE_INACTIVE`
- `ESP_WIFI_SENSING_FSM_STATE_DEBOUNCE`
- `ESP_WIFI_SENSING_FSM_STATE_ACTIVE`

#### `esp_wifi_sensing_fsm_event_t`

Event type used by callbacks:

- `ESP_WIFI_SENSING_FSM_EVENT_INACTIVE`
- `ESP_WIFI_SENSING_FSM_EVENT_ACTIVE`

#### `esp_wifi_sensing_fsm_config_t`

Global FSM configuration, including maximum channel count, raw sample buffer size, polling interval, internal ping frequency, and the default per-channel configuration.

#### `esp_wifi_sensing_fsm_channel_config_t`

Simplified per-channel configuration:

- `sensitivity`: Motion detection sensitivity, recommended range `(0, 1]`. Larger values are more sensitive. Changing this value relearns the motion baseline.
- `presence_sensitivity`: Presence detection sensitivity in `[0, 1]`. Larger values are more sensitive. Independent from motion `sensitivity`; updating it does not reset the motion baseline.
- `active_jitter_min`: Minimum raw jitter required to enter or stay in ACTIVE. Set `0` to disable this guard.
- `active_filter_ms`: Minimum hold time after entering ACTIVE.

#### `esp_wifi_sensing_fsm_channel_diag_t`

Per-channel runtime diagnostics, including:

- Motion: latest `jitter_value`, smoothed value, absolute enter/exit thresholds, process state, and initialization stage.
- Presence: latest `wander_value`, `presence_ready`, `presence_wander_average`, `presence_someone_threshold`, and `presence_someone_status`.
- Training: cached `train_wander_threshold` / `train_jitter_threshold`, `train_thresholds_valid`, `train_status`, `train_last_action`, template-sample / background counters, and the last `train_last_basis_wander` used for the decision.

Fields with the `scaled` suffix are mainly intended for debugging and visualization.

#### `esp_wifi_sensing_fsm_train_status_t` / `esp_wifi_sensing_fsm_train_action_t`

Public enums that let external code observe the training status and the latest training decision, useful for surfacing training progress in UIs. See the header file for the exact enumerators.

### Default Macros

```c
#define DEFAULT_ESP_WIFI_SENSING_FSM_CHANNEL_CONFIG() \
{ \
    .sensitivity = ESP_WIFI_SENSING_DEFAULT_SENSITIVITY, \
    .presence_sensitivity = ESP_WIFI_SENSING_DEFAULT_PRESENCE_SENSITIVITY, \
    .active_jitter_min = ESP_WIFI_SENSING_DEFAULT_ACTIVE_JITTER_MIN, \
    .active_filter_ms = ESP_WIFI_SENSING_ACTIVE_FILTER_MS_DEFAULT, \
}

#define DEFAULT_ESP_WIFI_SENSING_FSM_CONFIG() \
{ \
    .max_channel_num = 16, \
    .raw_buf_size = 20, \
    .polling_interval = 20, \
    .ping_frequency_hz = ESP_WIFI_SENSING_PING_FREQUENCY_HZ_DEFAULT, \
    .default_channel_config = DEFAULT_ESP_WIFI_SENSING_FSM_CHANNEL_CONFIG(), \
    .user_data = NULL, \
}
```

### Recommended Workflow

1. Create the FSM with `esp_wifi_sensing_fsm_create()`.
2. Add one or more channels with `esp_wifi_sensing_fsm_add_channel()`.
3. Optionally register event callbacks and tune channel parameters (motion `sensitivity`, `presence_sensitivity`, `active_jitter_min`, `active_filter_ms`).
4. (Recommended) Run the training once per on-site deployment: keep the environment static, call `esp_wifi_sensing_fsm_train_start()`, collect enough background samples, then call `esp_wifi_sensing_fsm_train_stop()` to obtain the wander / jitter thresholds. The thresholds are cached on the channel and feed the presence decision.
5. Start detection with `esp_wifi_sensing_fsm_control(..., ESP_WIFI_SENSING_FSM_CTRL_START, NULL)`.
6. In router-based CSI scenarios, optionally call `esp_wifi_sensing_fsm_ping_router_start()` to keep the sampling path alive.
7. Read state and diagnostics as needed while running, then stop and delete the FSM when done.

### API Reference

#### Lifecycle

```c
esp_err_t esp_wifi_sensing_fsm_create(const esp_wifi_sensing_fsm_config_t *config,
                                      esp_wifi_sensing_fsm_handle_t *handle);
esp_err_t esp_wifi_sensing_fsm_delete(esp_wifi_sensing_fsm_handle_t handle);
```

Creates and destroys the sensing FSM handle. The current implementation supports only one active FSM instance at a time.

#### Channel Management

```c
esp_err_t esp_wifi_sensing_fsm_add_channel(esp_wifi_sensing_fsm_handle_t handle,
                                           const uint8_t peer_mac[6]);
esp_err_t esp_wifi_sensing_fsm_remove_channel(esp_wifi_sensing_fsm_handle_t handle,
                                              const uint8_t peer_mac[6]);
```

Adds or removes sensing channels bound to a peer MAC/BSSID. Each channel maintains its own baseline, runtime state, and diagnostics.

#### Data Feed and State Query

```c
esp_err_t esp_wifi_sensing_fsm_update_data(esp_wifi_sensing_fsm_handle_t handle,
                                           const uint8_t peer_mac[6],
                                           uint32_t raw_data);
esp_err_t esp_wifi_sensing_fsm_get_state(esp_wifi_sensing_fsm_handle_t handle,
                                         const uint8_t peer_mac[6],
                                         esp_wifi_sensing_fsm_state_t *state);
esp_err_t esp_wifi_sensing_fsm_get_channel_diag(esp_wifi_sensing_fsm_handle_t handle,
                                                const uint8_t peer_mac[6],
                                                esp_wifi_sensing_fsm_channel_diag_t *diag);
```

Feeds feature data into the FSM and reads the current channel state and diagnostics.

- `esp_wifi_sensing_fsm_update_data()` is an advanced API for manual feature injection.
- With the built-in radar integration path, samples are fed automatically and applications normally do not need to call it.

#### Runtime Configuration and Events

```c
esp_err_t esp_wifi_sensing_fsm_set_channel_config(esp_wifi_sensing_fsm_handle_t handle,
                                                  const uint8_t peer_mac[6],
                                                  const esp_wifi_sensing_fsm_channel_config_t *config);
esp_err_t esp_wifi_sensing_fsm_get_channel_config(esp_wifi_sensing_fsm_handle_t handle,
                                                  const uint8_t peer_mac[6],
                                                  esp_wifi_sensing_fsm_channel_config_t *config);
esp_err_t esp_wifi_sensing_fsm_set_amplitude_log_enabled(esp_wifi_sensing_fsm_handle_t handle,
                                                         bool enabled);
esp_err_t esp_wifi_sensing_fsm_get_amplitude_log_enabled(esp_wifi_sensing_fsm_handle_t handle,
                                                         bool *enabled);
esp_err_t esp_wifi_sensing_fsm_register_event_cb(esp_wifi_sensing_fsm_handle_t handle,
                                                 esp_wifi_sensing_fsm_event_t event,
                                                 esp_wifi_sensing_fsm_event_cb_t cb,
                                                 void *user_data);
esp_err_t esp_wifi_sensing_fsm_unregister_event_cb(esp_wifi_sensing_fsm_handle_t handle,
                                                   esp_wifi_sensing_fsm_event_t event);
```

Updates runtime tuning, controls amplitude-log compression in the underlying radar decoder, and registers ACTIVE / INACTIVE event callbacks.

- Changing motion `sensitivity` causes the channel baseline to be relearned.
- Changing `presence_sensitivity` only affects the presence decision and does not reset the motion baseline.
- Multiple callbacks can be registered for the same event.

#### Training / Calibration

```c
esp_err_t esp_wifi_sensing_fsm_train_start(esp_wifi_sensing_fsm_handle_t handle,
                                           const uint8_t peer_mac[6]);
esp_err_t esp_wifi_sensing_fsm_train_stop(esp_wifi_sensing_fsm_handle_t handle,
                                          const uint8_t peer_mac[6],
                                          float *wander_threshold,
                                          float *jitter_threshold);
esp_err_t esp_wifi_sensing_fsm_train_remove(esp_wifi_sensing_fsm_handle_t handle,
                                            const uint8_t peer_mac[6]);
```

Drives the underlying `esp_radar` calibration from the FSM and caches the resulting wander / jitter thresholds on the channel for presence detection.

- Keep the environment static while training.
- The wander / jitter thresholds returned by `esp_wifi_sensing_fsm_train_stop()` are in the range `[0, 1]`; smaller means more stable.
- The cached thresholds can be read through `esp_wifi_sensing_fsm_channel_diag_t::train_wander_threshold` / `train_jitter_threshold`.

#### Control and Processing

```c
esp_err_t esp_wifi_sensing_fsm_control(esp_wifi_sensing_fsm_handle_t handle,
                                       esp_wifi_sensing_fsm_ctrl_t ctrl,
                                       void *ctrl_param);
esp_err_t esp_wifi_sensing_fsm_handle_events(esp_wifi_sensing_fsm_handle_t handle);
```

Starts, stops, resets the baseline, and manually advances event processing.

- `ctrl_param` is reserved; pass `NULL`.
- The component already runs a background task based on `polling_interval`, so `esp_wifi_sensing_fsm_handle_events()` usually does not need to be called manually.

#### Ping-driven Sampling

```c
esp_err_t esp_wifi_sensing_fsm_set_ping_frequency_hz(esp_wifi_sensing_fsm_handle_t handle,
                                                     uint32_t frequency_hz);
esp_err_t esp_wifi_sensing_fsm_get_ping_frequency_hz(esp_wifi_sensing_fsm_handle_t handle,
                                                     uint32_t *frequency_hz);
esp_err_t esp_wifi_sensing_fsm_ping_router_start(esp_wifi_sensing_fsm_handle_t handle);
esp_err_t esp_wifi_sensing_fsm_ping_router_stop(esp_wifi_sensing_fsm_handle_t handle);
```

Configures or starts/stops the internal router ping to keep CSI data flowing.

- `esp_wifi_sensing_fsm_ping_router_start()` automatically resolves the STA gateway and starts a continuous ping session.
- Use only when your deployment relies on router traffic to keep CSI samples flowing.

### Usage Example

```c
static void motion_cb(esp_wifi_sensing_fsm_handle_t handle,
                      const uint8_t peer_mac[6],
                      esp_wifi_sensing_fsm_event_t event,
                      uint32_t data,
                      void *user_data)
{
    (void)handle;
    (void)peer_mac;
    (void)user_data;
    printf("event=%d data=%lu\n", event, (unsigned long)data);
}

void sensing_example(const uint8_t peer_mac[6])
{
    esp_wifi_sensing_fsm_handle_t handle = NULL;
    esp_wifi_sensing_fsm_config_t config = DEFAULT_ESP_WIFI_SENSING_FSM_CONFIG();

    ESP_ERROR_CHECK(esp_wifi_sensing_fsm_create(&config, &handle));
    ESP_ERROR_CHECK(esp_wifi_sensing_fsm_add_channel(handle, peer_mac));
    ESP_ERROR_CHECK(esp_wifi_sensing_fsm_register_event_cb(handle,
                                                           ESP_WIFI_SENSING_FSM_EVENT_ACTIVE,
                                                           motion_cb,
                                                           NULL));
    ESP_ERROR_CHECK(esp_wifi_sensing_fsm_control(handle, ESP_WIFI_SENSING_FSM_CTRL_START, NULL));
    ESP_ERROR_CHECK(esp_wifi_sensing_fsm_ping_router_start(handle));

    /* ... run application logic ... */

    ESP_ERROR_CHECK(esp_wifi_sensing_fsm_ping_router_stop(handle));
    ESP_ERROR_CHECK(esp_wifi_sensing_fsm_delete(handle));
}
```

For a more complete demo, see `test_apps` in this component.
