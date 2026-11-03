# ESP Wi-Fi 感知 [[English]](./README.md)

### 概述

`esp_wifi_sensing` 是基于 CSI 数据的 Wi-Fi 感知状态机组件，用于在 ESP 设备上实现运动触发、人体存在检测和交互联动。组件内部基于 `esp-radar` 输出的运动特征，提供多通道管理、去抖、动态基线、事件回调和路由器 ping 驱动采样等能力。

### 功能特性

- **多通道 FSM**：一个句柄可同时管理多个 peer/BSSID 检测通道。
- **运动检测**：基于动态基线，内置平滑、自适应噪声估计、滞回和 ACTIVE 保持窗口，降低误触发。
- **人体存在检测**：基于 `waveform_wander` 特征的通道级存在检测。
- **现场标定**：内置训练流程，学习现场相关的 wander / jitter 阈值并为存在检测提供阈值。
- **简化调参**：运动灵敏度和存在灵敏度以独立参数暴露。
- **事件回调**：支持注册 ACTIVE / INACTIVE 事件回调，便于驱动灯效、上报或业务联动。
- **链路保活**：可通过内部 ping 维持 CSI 采样链路，适合路由器交互场景。
- **诊断接口**：支持读取状态机状态、通道配置以及运动 / 存在 / 训练诊断数据，便于调试和可视化。

### 支持的芯片

- ESP32
- ESP32-S2
- ESP32-S3
- ESP32-C3
- ESP32-C5
- ESP32-C6
- ESP32-C61

### 依赖要求

- ESP-IDF >= 5.4
- `esp-radar` >= 0.3.3

### 核心数据类型

#### `esp_wifi_sensing_fsm_handle_t`

不透明 FSM 句柄。一个句柄可管理多个感知通道，每个通道由一个 peer MAC 地址标识。

#### `esp_wifi_sensing_fsm_state_t`

对外暴露的通道状态：

- `ESP_WIFI_SENSING_FSM_STATE_INACTIVE`
- `ESP_WIFI_SENSING_FSM_STATE_DEBOUNCE`
- `ESP_WIFI_SENSING_FSM_STATE_ACTIVE`

#### `esp_wifi_sensing_fsm_event_t`

事件回调使用的事件类型：

- `ESP_WIFI_SENSING_FSM_EVENT_INACTIVE`
- `ESP_WIFI_SENSING_FSM_EVENT_ACTIVE`

#### `esp_wifi_sensing_fsm_config_t`

全局 FSM 配置，包含最大通道数、原始样本缓冲区大小、轮询周期、内部 ping 频率和默认通道配置。

#### `esp_wifi_sensing_fsm_channel_config_t`

通道级简化配置：

- `sensitivity`：运动检测灵敏度，推荐范围为 `(0, 1]`，越大越灵敏；修改该值会重新学习运动基线。
- `presence_sensitivity`：存在检测灵敏度，范围 `[0, 1]`，越大越灵敏；与运动 `sensitivity` 相互独立，修改它不会重置运动基线。
- `active_jitter_min`：进入或保持 ACTIVE 所需的最小原始 jitter，设为 `0` 表示关闭该保护。
- `active_filter_ms`：进入 ACTIVE 后的最小保持时间。

#### `esp_wifi_sensing_fsm_channel_diag_t`

通道运行态诊断信息，包括：

- 运动相关：最近一次 `jitter_value`、平滑值、进入/退出绝对门限、过程状态和初始化阶段。
- 存在相关：最近一次 `wander_value`、`presence_ready`、`presence_wander_average`、`presence_someone_threshold` 和 `presence_someone_status`。
- 训练相关：缓存的 `train_wander_threshold` / `train_jitter_threshold`、`train_thresholds_valid`、`train_status`、`train_last_action`、模板样本/背景计数以及最近用于判决的 `train_last_basis_wander`。

带 `scaled` 的字段主要用于调试和可视化。

#### `esp_wifi_sensing_fsm_train_status_t` / `esp_wifi_sensing_fsm_train_action_t`

用于外部观察训练状态和最近一次训练决策的公共枚举，便于在 UI 中展示训练进度，具体枚举值见头文件。

### 默认配置宏

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

### 推荐使用流程

1. 调用 `esp_wifi_sensing_fsm_create()` 创建 FSM。
2. 通过 `esp_wifi_sensing_fsm_add_channel()` 添加一个或多个通道。
3. 按需注册事件回调，并调整通道参数（运动 `sensitivity`、`presence_sensitivity`、`active_jitter_min`、`active_filter_ms`）。
4. （推荐）每次现场部署执行一次训练：保持环境静止，调用 `esp_wifi_sensing_fsm_train_start()` 采集足够背景样本后调用 `esp_wifi_sensing_fsm_train_stop()` 获取 wander / jitter 阈值。阈值会缓存到通道并参与存在检测判决。
5. 调用 `esp_wifi_sensing_fsm_control(..., ESP_WIFI_SENSING_FSM_CTRL_START, NULL)` 启动检测。
6. 在基于路由器的 CSI 场景中，可选调用 `esp_wifi_sensing_fsm_ping_router_start()` 保持采样链路活跃。
7. 运行中按需读取状态和诊断信息，结束时停止并删除 FSM。

### API 参考

#### 生命周期管理

```c
esp_err_t esp_wifi_sensing_fsm_create(const esp_wifi_sensing_fsm_config_t *config,
                                      esp_wifi_sensing_fsm_handle_t *handle);
esp_err_t esp_wifi_sensing_fsm_delete(esp_wifi_sensing_fsm_handle_t handle);
```

用于创建和销毁感知状态机句柄。当前实现只支持同时存在一个活动 FSM 实例。

#### 通道管理

```c
esp_err_t esp_wifi_sensing_fsm_add_channel(esp_wifi_sensing_fsm_handle_t handle,
                                           const uint8_t peer_mac[6]);
esp_err_t esp_wifi_sensing_fsm_remove_channel(esp_wifi_sensing_fsm_handle_t handle,
                                              const uint8_t peer_mac[6]);
```

用于为指定 peer MAC/BSSID 增删检测通道。每个通道维护各自的基线、运行状态和诊断数据。

#### 数据写入与状态读取

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

用于写入特征数据，并读取当前通道状态和诊断信息。

- `esp_wifi_sensing_fsm_update_data()` 属于高级接口，用于手动注入特征值。
- 使用组件内建的 radar 集成路径时，样本会自动写入，应用通常无需主动调用该函数。

#### 运行时配置与事件

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

用于运行时调参、控制底层 radar 解码器的 amplitude-log 压缩，以及注册 ACTIVE / INACTIVE 事件回调。

- 修改运动 `sensitivity` 后，通道会重新学习基线。
- 修改 `presence_sensitivity` 只影响存在检测判决，不会重置运动检测基线。
- 同一个事件支持注册多个回调。

#### 训练 / 标定

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

从状态机驱动底层 `esp_radar` 标定，并把得到的 wander / jitter 阈值缓存到通道用于存在检测。

- 训练期间请保持现场环境静止。
- `esp_wifi_sensing_fsm_train_stop()` 返回的 wander / jitter 阈值取值范围为 `[0, 1]`，越小越稳定。
- 缓存的阈值可通过 `esp_wifi_sensing_fsm_channel_diag_t::train_wander_threshold` / `train_jitter_threshold` 读取。

#### 控制与内部处理

```c
esp_err_t esp_wifi_sensing_fsm_control(esp_wifi_sensing_fsm_handle_t handle,
                                       esp_wifi_sensing_fsm_ctrl_t ctrl,
                                       void *ctrl_param);
esp_err_t esp_wifi_sensing_fsm_handle_events(esp_wifi_sensing_fsm_handle_t handle);
```

用于启动、停止、重置基线和主动推进事件处理。

- `ctrl_param` 预留，传 `NULL` 即可。
- 组件内部已经按 `polling_interval` 运行后台任务，通常不需要手动调用 `esp_wifi_sensing_fsm_handle_events()`。

#### Ping 驱动采样

```c
esp_err_t esp_wifi_sensing_fsm_set_ping_frequency_hz(esp_wifi_sensing_fsm_handle_t handle,
                                                     uint32_t frequency_hz);
esp_err_t esp_wifi_sensing_fsm_get_ping_frequency_hz(esp_wifi_sensing_fsm_handle_t handle,
                                                     uint32_t *frequency_hz);
esp_err_t esp_wifi_sensing_fsm_ping_router_start(esp_wifi_sensing_fsm_handle_t handle);
esp_err_t esp_wifi_sensing_fsm_ping_router_stop(esp_wifi_sensing_fsm_handle_t handle);
```

用于配置或启停内部路由器 ping，以驱动 CSI 数据持续产生。

- `esp_wifi_sensing_fsm_ping_router_start()` 会自动解析 STA 网关并启动持续 ping 会话。
- 仅在你的部署方式依赖路由器流量维持 CSI 样本连续输出时使用。

### 使用示例

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

    /* ... 运行应用逻辑 ... */

    ESP_ERROR_CHECK(esp_wifi_sensing_fsm_ping_router_stop(handle));
    ESP_ERROR_CHECK(esp_wifi_sensing_fsm_delete(handle));
}
```

更完整的演示可参考组件内的 `test_apps`。
