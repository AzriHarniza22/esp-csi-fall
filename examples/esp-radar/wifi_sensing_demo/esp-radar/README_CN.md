# esp-radar 组件

[![Component Registry](https://components.espressif.com/components/espressif/esp-radar/badge.svg)](https://components.espressif.com/components/espressif/esp-radar)

- [用户指南](https://github.com/espressif/esp-csi/tree/master/README.md)
- [English README](./README.md)

Wi-Fi CSI（Channel State Information，信道状态信息）是从 Wi-Fi 数据包中提取出的细粒度信道信息。`esp-radar` 提供了基于 ESP-CSI 数据的人体存在检测和运动检测核心算法及示例。

## v0.3.3 更新亮点

- 新增多 `peer` CSI 接收与分发能力，现在可以按源 MAC 地址分别处理 CSI 数据包。
- 新增基于 `peer` 的 API：`esp_radar_new_peer()` 和 `esp_radar_del_peer()`，用于注册和注销 CSI `peer`。
- 新增扩展雷达回调 `wifi_radar_cb_ex_t`，可在上报雷达结果的同时返回对应 `peer` 的 MAC 地址。
- 每个 `peer` 都维护独立的运行时状态，包括缓冲区和训练/标定数据。
- 默认保留原有单 `peer` 行为。如果不注册额外 `peer`，`filter_mac` / `filter_dmac` 以及旧回调路径仍按原有方式工作。

## 依赖要求

- ESP-IDF `>= 5.4`
- 支持目标芯片：`esp32`、`esp32s2`、`esp32s3`、`esp32c3`、`esp32c5`、`esp32c6`、`esp32c61`

## 添加组件到工程

使用组件管理器命令 `add-dependency` 将 `esp-radar` 添加到工程依赖中。在 `CMake` 阶段会自动下载组件。

```bash
idf.py add-dependency "espressif/esp-radar^0.3.2"
```

## 示例

使用组件管理器命令 `create-project-from-example` 基于示例模板创建工程。

```bash
idf.py create-project-from-example "espressif/esp-radar=*:console_test"
```

随后示例会被下载到当前目录，你可以直接进入工程进行编译和烧录。

你也可以使用同样的命令下载其他示例，或者直接浏览仓库中的示例：

- [connect_rainmaker](https://github.com/espressif/esp-csi/tree/master/examples/esp-radar/connect_rainmaker)：为 ESP RainMaker 添加 Wi-Fi CSI 功能
- [console_test](https://github.com/espressif/esp-csi/tree/master/examples/esp-radar/console_test)：提供 Wi-Fi CSI 数据显示、采集和分析的测试平台
- [wifi_sensing_demo](https://github.com/espressif/esp-csi/tree/master/examples/esp-radar/wifi_sensing_demo)：基于 `esp_wifi_sensing` 组件的 Wi-Fi 感知演示，包含运动 / 人体存在检测、现场训练标定、LED 状态反馈，以及浏览器端 Web Serial 监控页面

## 多 `peer` CSI 用法

`v0.3.3` 为需要同时接收多个源 MAC 的应用引入了多 `peer` 工作流。

1. 像以往一样先通过 `esp_radar_init()` 初始化 `esp-radar`。
2. 如果需要知道每条雷达结果来自哪个 `peer`，请注册 `dec_config.wifi_radar_cb_ex`。
3. 针对每个源 MAC 调用 `esp_radar_new_peer()` 创建对应的 `peer` 句柄。
4. 如果需要针对不同 `peer` 分别做标定，可使用 `esp_radar_train_start_ex()` / `esp_radar_train_stop_ex()`。
5. 删除 `peer` 前，必须先停止雷达，再调用 `esp_radar_del_peer()`。

```c
static void radar_cb_ex(void *ctx, const uint8_t mac[6], const wifi_radar_info_t *info)
{
    ESP_LOGI("esp-radar", MACSTR ", wander=%0.3f, jitter=%0.3f",
             MAC2STR(mac), info->waveform_wander, info->waveform_jitter);
}

void app_main(void)
{
    const uint8_t peer_mac[6] = {0x24, 0x6F, 0x28, 0x00, 0x00, 0x01};
    esp_radar_handle_t peer = NULL;
    esp_radar_config_t radar_config = ESP_RADAR_CONFIG_DEFAULT();

    radar_config.dec_config.wifi_radar_cb_ex = radar_cb_ex;

    ESP_ERROR_CHECK(esp_radar_init(&radar_config));
    ESP_ERROR_CHECK(esp_radar_new_peer(peer_mac, &peer));
    ESP_ERROR_CHECK(esp_radar_start());

    ESP_ERROR_CHECK(esp_radar_train_start_ex(peer));
    /* 在这里采集参考数据 */
    ESP_ERROR_CHECK(esp_radar_train_stop_ex(peer, NULL, NULL));

    ESP_ERROR_CHECK(esp_radar_stop());
    ESP_ERROR_CHECK(esp_radar_del_peer(peer));
    ESP_ERROR_CHECK(esp_radar_deinit());
}
```

### 说明

- 所有 `peer` 共享由 `esp_radar_init()` 设置的全局雷达配置。
- 每个 `peer` 在内部维护独立的运行时状态。
- 可以注册 `FF:FF:FF:FF:FF:FF` 作为通配 `peer`，但精确匹配的 `peer` 优先级更高。
- 如果仍然使用旧的单 `peer` 流程，现有的 `wifi_radar_cb`、`filter_mac` 和 `filter_dmac` 行为不会变化。

## 常见问题

Q1. 使用包管理器时遇到下面的问题：

```text
  HINT: Please check manifest file of the following component(s): main

  ERROR: Because project depends on esp-radar (2.*) which doesn't match any
  versions, version solving failed.
```

A1. 如果是通过该命令下载的示例，请将示例工程 `main/idf_component.yml` 中的 `override_path` 行注释掉。

Q2. 使用包管理器时遇到下面的问题：

```text
Executing action: create-project-from-example
CMakeLists.txt not found in project directory /home/username
```

A2. 这通常是因为组件管理器版本较旧。请在 ESP-IDF 环境中执行 `pip install -U idf-component-manager` 后再重试。
