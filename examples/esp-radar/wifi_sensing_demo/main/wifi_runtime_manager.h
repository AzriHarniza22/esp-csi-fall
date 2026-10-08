/*
 * SPDX-FileCopyrightText: 2026 Espressif Systems (Shanghai) CO LTD
 *
 * SPDX-License-Identifier: Apache-2.0
 */
#pragma once

#include <stdbool.h>
#include <stdint.h>

#include "esp_err.h"
#include "esp_event.h"
#include "esp_netif.h"
#include "esp_wifi.h"

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief Connection phase reported to the browser monitor and the status LED.
 *
 * The names are part of the Web Serial protocol, so they must stay stable.
 */
typedef enum {
    WIFI_RUNTIME_STATE_BOOTING = 0,   /**< Stack coming up, Wi-Fi not started yet. */
    WIFI_RUNTIME_STATE_CONFIGURING,   /**< A new SSID/password is being applied. */
    WIFI_RUNTIME_STATE_DISCONNECTING, /**< Waiting for the disconnect event to complete. */
    WIFI_RUNTIME_STATE_CONNECTING,    /**< Association attempt in flight. */
    WIFI_RUNTIME_STATE_CONNECTED,     /**< Associated with the AP, IP not yet assigned. */
    WIFI_RUNTIME_STATE_GOT_IP,        /**< IP acquired, sensing may start. */
    WIFI_RUNTIME_STATE_FAILED,        /**< Association failed, see the last reason. */
    WIFI_RUNTIME_STATE_DISCONNECTED,  /**< Idle, no association attempt in flight. */
} wifi_runtime_state_t;

/**
 * @brief Snapshot of the current association, safe to read from any task.
 */
typedef struct {
    wifi_runtime_state_t state; /**< Current phase. */
    bool connected;            /**< True while associated with an AP. */
    bool has_ip;               /**< True once an IP address was assigned. */
    uint8_t reason;            /**< Last `wifi_event_sta_disconnected_t.reason`, 0 when unknown. */
    uint8_t bssid[6];          /**< AP BSSID, all zeros when not associated. */
    uint8_t ssid[33];          /**< AP SSID without the NUL terminator excluded. */
    uint8_t ssid_len;          /**< Length of `ssid`. */
    uint8_t channel;           /**< Primary channel of the AP, 0 when not associated. */
    int8_t rssi;               /**< Last known RSSI in dBm. */
    char ip[16];               /**< Dotted-quad IPv4 address, empty when unavailable. */
} wifi_runtime_info_t;

/**
 * @brief Human-readable name for a connection phase, matching the Web Serial protocol.
 */
const char *wifi_runtime_state_name(wifi_runtime_state_t state);

/**
 * @brief Human-readable name for an `esp_wifi` disconnect reason code.
 */
const char *wifi_runtime_reason_name(uint8_t reason);

/**
 * @brief Bring up the STA interface and connect using the saved credentials.
 *
 * The credentials are the ones written by wifi_runtime_manager_set_credentials()
 * when any exist, otherwise the Kconfig default.
 *
 * This replaces `example_connect()`: it registers the single reconnect owner used
 * for the whole runtime, so no other module may call `esp_wifi_connect()`.
 *
 * @return
 *      - ESP_OK: Wi-Fi is associated and an IP was acquired
 *      - ESP_ERR_TIMEOUT: The attempt did not reach GOT_IP within the boot budget
 *      - Other: Propagated from the ESP-IDF Wi-Fi calls
 */
esp_err_t wifi_runtime_manager_init(void);

/**
 * @brief Replace the station credentials and reconnect exactly once.
 *
 * The sequence is ordered so that a reconnect can never race the reconfiguration:
 * stop auto-reconnect, disconnect and wait for the event, drop any inherited
 * BSSID/channel lock, apply the new config, then issue a single connect.
 *
 * @param ssid Null-terminated SSID, at most 32 bytes.
 * @param password Null-terminated password, at most 64 bytes. May be NULL or empty for open networks.
 * @param[out] info Receives the resulting state, including the failure reason when the attempt fails.
 * @return
 *      - ESP_OK: The new AP is associated and an IP was acquired
 *      - ESP_ERR_INVALID_ARG: `ssid` is empty or too long, or `password` is too long
 *      - ESP_ERR_TIMEOUT: Associated but no IP within the connect budget
 *      - Other: Propagated from the ESP-IDF Wi-Fi calls
 */
esp_err_t wifi_runtime_manager_set_credentials(const char *ssid, const char *password, wifi_runtime_info_t *info);

/**
 * @brief Disconnect on purpose and keep auto-reconnect suppressed.
 */
esp_err_t wifi_runtime_manager_disconnect(void);

/**
 * @brief Reconnect using the credentials currently stored in the driver.
 */
esp_err_t wifi_runtime_manager_reconnect(void);

/**
 * @brief Retry the connect attempt when no association ever succeeded.
 *
 * Unlike wifi_runtime_manager_reconnect() this does not disconnect first, so it
 * also works on a device that has never been associated (a boot against an SSID
 * that is out of range). Callers own the retry schedule.
 *
 * @return Result of the single attempt.
 */
esp_err_t wifi_runtime_manager_retry_connect(void);

/**
 * @brief Copy the current connection snapshot.
 *
 * @param[out] info Destination, ignored when NULL.
 */
void wifi_runtime_manager_get_info(wifi_runtime_info_t *info);

/**
 * @brief Register a callback invoked on every connection phase change.
 *
 * The callback runs in the event-loop task, so it must stay short and must not
 * block. Pass NULL to clear the callback.
 *
 * @param cb Callback, or NULL to unregister.
 * @param ctx Opaque pointer forwarded to the callback.
 */
void wifi_runtime_manager_set_state_callback(void (*cb)(wifi_runtime_state_t state, const wifi_runtime_info_t *info, void *ctx),
                                              void *ctx);

#ifdef __cplusplus
}
#endif
