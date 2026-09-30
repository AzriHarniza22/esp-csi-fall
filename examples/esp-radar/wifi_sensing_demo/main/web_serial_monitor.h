/*
 * SPDX-FileCopyrightText: 2026 Espressif Systems (Shanghai) CO LTD
 *
 * SPDX-License-Identifier: Apache-2.0
 */
#pragma once

#include <stddef.h>
#include <stdint.h>

#include "esp_err.h"
#include "esp_radar.h"
#include "esp_wifi_sensing.h"

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief Maximum number of peers supported by the demo's browser monitor.
 */
#define WEB_SERIAL_MONITOR_MAX_PEERS 8

/**
 * @brief Peer entry exported to the browser monitor.
 */
typedef struct {
    const char *name; /**< Human-readable peer name shown by the UI. */
    uint8_t mac[6];   /**< Peer MAC address bound to the sensing channel. */
} web_serial_monitor_peer_t;

/**
 * @brief Configuration passed to `web_serial_monitor_init()`.
 */
typedef struct {
    esp_wifi_sensing_fsm_handle_t fsm;           /**< Sensing FSM instance to inspect and control. */
    const web_serial_monitor_peer_t *peers;      /**< Peer table visible to the UI. */
    size_t peer_num;                             /**< Number of valid entries in `peers`. */
    uint32_t stream_period_ms;                   /**< Streaming period in milliseconds. Set `0` to use the default. */
} web_serial_monitor_config_t;

/**
 * @brief Optional CSI callback passed to the sensing component.
 *
 * The callback is idle until the browser requests the CSI stream.
 */
void web_serial_monitor_csi_callback(void *ctx, const wifi_csi_filtered_info_t *info);

/**
 * @brief Start the serial transport and command loop without a sensing FSM.
 *
 * Called before Wi-Fi so the browser already observes `BOOTING`, `CONNECTING`,
 * and `GOT_IP` while the manager is still connecting. Sensing commands are
 * rejected with an ack until `web_serial_monitor_attach_sensing()` supplies the
 * FSM handle and peer table.
 *
 * @return
 *      - ESP_OK: Success
 *      - ESP_ERR_INVALID_STATE: Already initialized
 *      - ESP_FAIL: Failed to create the background task or configure inputs
 */
esp_err_t web_serial_monitor_init(void);

/**
 * @brief Publish the current Wi-Fi state to the browser.
 *
 * The transport does not observe the runtime manager directly, so the owner must
 * call this on every phase change. Without it the browser keeps the last state it
 * saw at boot and its buttons stay disabled after a manual reconnect.
 */
void web_serial_monitor_notify_wifi_state(void);

/**
 * @brief Bind the sensing FSM and peer table once Wi-Fi is ready.
 *
 * Called from the Wi-Fi GOT_IP path. Publishes `hello` and the per-channel
 * configuration so the browser can populate its UI without a reconnect.
 *
 * @param config Browser-monitor configuration.
 * @return
 *      - ESP_OK: Success
 *      - ESP_ERR_INVALID_ARG: `config` is invalid
 *      - ESP_ERR_INVALID_STATE: The transport was not started or is already bound
 */
esp_err_t web_serial_monitor_attach_sensing(const web_serial_monitor_config_t *config);

#ifdef __cplusplus
}
#endif
