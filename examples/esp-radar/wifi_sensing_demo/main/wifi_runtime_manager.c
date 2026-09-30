/*
 * SPDX-FileCopyrightText: 2026 Espressif Systems (Shanghai) CO LTD
 *
 * SPDX-License-Identifier: Apache-2.0
 */
#include <string.h>

#include <stdio.h>

#include "freertos/FreeRTOS.h"
#include "freertos/event_groups.h"
#include "freertos/semphr.h"
#include "freertos/task.h"

#include "esp_mac.h"

#include "esp_event.h"
#include "esp_log.h"
#include "esp_netif.h"
#include "esp_timer.h"
#include "esp_wifi.h"

#include "sdkconfig.h"

#include "wifi_runtime_manager.h"

static const char *TAG = "wifi_runtime";

#define WIFI_RUNTIME_BIT_CONNECTED    BIT0
#define WIFI_RUNTIME_BIT_DISCONNECTED BIT1
#define WIFI_RUNTIME_BIT_GOT_IP       BIT2

#define WIFI_RUNTIME_BOOT_TIMEOUT_MS   30000
#define WIFI_RUNTIME_CONNECT_TIMEOUT_MS 15000
#define WIFI_RUNTIME_DISCONNECT_TIMEOUT_MS 5000
#define WIFI_RUNTIME_MAX_RETRY         5
#define WIFI_RUNTIME_RETRY_BASE_MS     1000
#define WIFI_RUNTIME_RETRY_MAX_MS      8000
/* esp_wifi_set_config() fails with ESP_ERR_WIFI_STATE while the STA is still connecting. */
#define WIFI_RUNTIME_SET_CONFIG_RETRY  5
#define WIFI_RUNTIME_SET_CONFIG_RETRY_MS 200
/* Both STA fields are fixed NUL-terminated arrays, so the usable payload is one byte less. */
#define WIFI_RUNTIME_MAX_SSID_LEN      32
#define WIFI_RUNTIME_MAX_PASSPHRASE_LEN 64

typedef void (*wifi_runtime_state_cb_t)(wifi_runtime_state_t state, const wifi_runtime_info_t *info, void *ctx);

static struct {
    bool initialized;
    SemaphoreHandle_t lock;
    EventGroupHandle_t events;
    esp_netif_t *sta_netif;
    esp_timer_handle_t retry_timer;

    wifi_runtime_info_t info;
    /* Suppresses the reconnect path for the duration of a deliberate reconfiguration. */
    bool intentional_disconnect;
    /* A disconnect we did not ask for still deserves a bounded number of retries. */
    bool auto_reconnect_enabled;
    int retry_count;

    wifi_runtime_state_cb_t state_cb;
    void *state_cb_ctx;
} s_mgr;

static void lock(void)
{
    if (s_mgr.lock) {
        xSemaphoreTake(s_mgr.lock, portMAX_DELAY);
    }
}

static void unlock(void)
{
    if (s_mgr.lock) {
        xSemaphoreGive(s_mgr.lock);
    }
}

static void publish_state_locked(wifi_runtime_state_t state)
{
    s_mgr.info.state = state;
    s_mgr.info.connected = (state == WIFI_RUNTIME_STATE_CONNECTED || state == WIFI_RUNTIME_STATE_GOT_IP);
    s_mgr.info.has_ip = (state == WIFI_RUNTIME_STATE_GOT_IP);

    ESP_LOGI(TAG, "state=%s reason=%s", wifi_runtime_state_name(state),
             wifi_runtime_reason_name(s_mgr.info.reason));

    if (s_mgr.state_cb) {
        s_mgr.state_cb(state, &s_mgr.info, s_mgr.state_cb_ctx);
    }
}

const char *wifi_runtime_state_name(wifi_runtime_state_t state)
{
    switch (state) {
    case WIFI_RUNTIME_STATE_BOOTING:
        return "BOOTING";
    case WIFI_RUNTIME_STATE_CONFIGURING:
        return "CONFIGURING";
    case WIFI_RUNTIME_STATE_DISCONNECTING:
        return "DISCONNECTING";
    case WIFI_RUNTIME_STATE_CONNECTING:
        return "CONNECTING";
    case WIFI_RUNTIME_STATE_CONNECTED:
        return "CONNECTED";
    case WIFI_RUNTIME_STATE_GOT_IP:
        return "GOT_IP";
    case WIFI_RUNTIME_STATE_FAILED:
        return "FAILED";
    case WIFI_RUNTIME_STATE_DISCONNECTED:
        return "DISCONNECTED";
    default:
        return "UNKNOWN";
    }
}

const char *wifi_runtime_reason_name(uint8_t reason)
{
    switch (reason) {
    case 0:
        return "NONE";
    case WIFI_REASON_UNSPECIFIED:
        return "UNSPECIFIED";
    case WIFI_REASON_AUTH_EXPIRE:
        return "AUTH_EXPIRE";
    case WIFI_REASON_AUTH_LEAVE:
        return "AUTH_LEAVE";
    case WIFI_REASON_DISASSOC_DUE_TO_INACTIVITY:
        return "INACTIVITY";
    case WIFI_REASON_ASSOC_TOOMANY:
        return "ASSOC_TOOMANY";
    case WIFI_REASON_CLASS2_FRAME_FROM_NONAUTH_STA:
        return "CLASS2_FRAME";
    case WIFI_REASON_CLASS3_FRAME_FROM_NONASSOC_STA:
        return "CLASS3_FRAME";
    case WIFI_REASON_ASSOC_LEAVE:
        return "ASSOC_LEAVE";
    case WIFI_REASON_ASSOC_NOT_AUTHED:
        return "ASSOC_NOT_AUTHED";
    case WIFI_REASON_DISASSOC_PWRCAP_BAD:
        return "PWRCAP_BAD";
    case WIFI_REASON_DISASSOC_SUPCHAN_BAD:
        return "SUPCHAN_BAD";
    case WIFI_REASON_BSS_TRANSITION_DISASSOC:
        return "BSS_TRANSITION";
    case WIFI_REASON_IE_INVALID:
        return "IE_INVALID";
    case WIFI_REASON_MIC_FAILURE:
        return "MIC_FAILURE";
    case WIFI_REASON_4WAY_HANDSHAKE_TIMEOUT:
        return "HANDSHAKE_TIMEOUT";
    case WIFI_REASON_GROUP_KEY_UPDATE_TIMEOUT:
        return "GROUP_KEY_TIMEOUT";
    case WIFI_REASON_IE_IN_4WAY_DIFFERS:
        return "IE_IN_4WAY_DIFFERS";
    case WIFI_REASON_GROUP_CIPHER_INVALID:
        return "GROUP_CIPHER_INVALID";
    case WIFI_REASON_PAIRWISE_CIPHER_INVALID:
        return "PAIRWISE_CIPHER_INVALID";
    case WIFI_REASON_AKMP_INVALID:
        return "AKMP_INVALID";
    case WIFI_REASON_UNSUPP_RSN_IE_VERSION:
        return "UNSUPP_RSN_IE_VERSION";
    case WIFI_REASON_INVALID_RSN_IE_CAP:
        return "INVALID_RSN_IE_CAP";
    case WIFI_REASON_TDLS_PEER_UNREACHABLE:
        return "TDLS_PEER_UNREACHABLE";
    case WIFI_REASON_TDLS_UNSPECIFIED:
        return "TDLS_UNSPECIFIED";
    case WIFI_REASON_SSP_REQUESTED_DISASSOC:
        return "SSP_REQUESTED_DISASSOC";
    case WIFI_REASON_BAD_CIPHER_OR_AKM:
        return "BAD_CIPHER_OR_AKM";
    case WIFI_REASON_NOT_AUTHORIZED_THIS_LOCATION:
        return "NOT_AUTHORIZED_LOCATION";
    case WIFI_REASON_SERVICE_CHANGE_PERCLUDES_TS:
        return "SERVICE_CHANGE_TS";
    case WIFI_REASON_NOT_ENOUGH_BANDWIDTH:
        return "NOT_ENOUGH_BANDWIDTH";
    case WIFI_REASON_MISSING_ACKS:
        return "MISSING_ACKS";
    case WIFI_REASON_EXCEEDED_TXOP:
        return "EXCEEDED_TXOP";
    case WIFI_REASON_STA_LEAVING:
        return "STA_LEAVING";
    case WIFI_REASON_END_BA:
        return "END_BA";
    case WIFI_REASON_UNKNOWN_BA:
        return "UNKNOWN_BA";
    case WIFI_REASON_INVALID_FT_ACTION_FRAME_COUNT:
        return "INVALID_FT_ACTION_COUNT";
    case WIFI_REASON_INVALID_PMKID:
        return "INVALID_PMKID";
    case WIFI_REASON_INVALID_MDE:
        return "INVALID_MDE";
    case WIFI_REASON_INVALID_FTE:
        return "INVALID_FTE";
    case WIFI_REASON_802_1X_AUTH_FAILED:
        return "AUTH_FAIL_8021X";
    case WIFI_REASON_CIPHER_SUITE_REJECTED:
        return "CIPHER_REJECTED";
    case WIFI_REASON_NO_SSP_ROAMING_AGREEMENT:
        return "NO_SSP_ROAMING";
    case WIFI_REASON_UNSPECIFIED_QOS:
        return "UNSPECIFIED_QOS";
    case WIFI_REASON_TIMEOUT:
        return "TIMEOUT";
    case WIFI_REASON_PEER_INITIATED:
        return "PEER_INITIATED";
    case WIFI_REASON_AP_INITIATED:
        return "AP_INITIATED";
    case WIFI_REASON_TRANSMISSION_LINK_ESTABLISH_FAILED:
        return "LINK_ESTABLISH_FAILED";
    case WIFI_REASON_ALTERATIVE_CHANNEL_OCCUPIED:
        return "ALT_CHANNEL_OCCUPIED";
    case WIFI_REASON_BEACON_TIMEOUT:
        return "BEACON_TIMEOUT";
    case WIFI_REASON_NO_AP_FOUND:
        return "NO_AP_FOUND";
    case WIFI_REASON_AUTH_FAIL:
        return "AUTH_FAIL";
    case WIFI_REASON_ASSOC_FAIL:
        return "ASSOC_FAIL";
    case WIFI_REASON_HANDSHAKE_TIMEOUT:
        return "HANDSHAKE_TIMEOUT";
    case WIFI_REASON_CONNECTION_FAIL:
        return "CONNECTION_FAIL";
    case WIFI_REASON_AP_TSF_RESET:
        return "AP_TSF_RESET";
    case WIFI_REASON_ROAMING:
        return "ROAMING";
    case WIFI_REASON_SA_QUERY_TIMEOUT:
        return "SA_QUERY_TIMEOUT";
    case WIFI_REASON_ASSOC_COMEBACK_TIME_TOO_LONG:
        return "ASSOC_COMEBACK_TOO_LONG";
    case WIFI_REASON_NO_AP_FOUND_W_COMPATIBLE_SECURITY:
        return "NO_AP_FOUND_SECURITY";
    case WIFI_REASON_NO_AP_FOUND_IN_AUTHMODE_THRESHOLD:
        return "NO_AP_FOUND_AUTHMODE";
    case WIFI_REASON_NO_AP_FOUND_IN_RSSI_THRESHOLD:
        return "NO_AP_FOUND_RSSI";
    default:
        return "UNKNOWN";
    }
}

void wifi_runtime_manager_set_state_callback(wifi_runtime_state_cb_t cb, void *ctx)
{
    lock();
    s_mgr.state_cb = cb;
    s_mgr.state_cb_ctx = ctx;
    unlock();
}

void wifi_runtime_manager_get_info(wifi_runtime_info_t *info)
{
    if (!info) {
        return;
    }

    lock();
    *info = s_mgr.info;
    unlock();
}

static int32_t retry_backoff_ms(int attempt)
{
    int32_t delay = WIFI_RUNTIME_RETRY_BASE_MS << (attempt > 3 ? 3 : attempt);
    return (delay > WIFI_RUNTIME_RETRY_MAX_MS) ? WIFI_RUNTIME_RETRY_MAX_MS : delay;
}

static void schedule_retry_locked(void);

static void retry_timer_fired(void *arg)
{
    (void)arg;

    lock();
    s_mgr.auto_reconnect_enabled = true;
    bool should_connect = (s_mgr.info.state == WIFI_RUNTIME_STATE_DISCONNECTED) &&
                          !s_mgr.intentional_disconnect;
    if (should_connect) {
        s_mgr.info.reason = 0;
        publish_state_locked(WIFI_RUNTIME_STATE_CONNECTING);
    }
    unlock();

    if (!should_connect) {
        return;
    }

    esp_err_t err = esp_wifi_connect();
    if (err != ESP_OK) {
        /*
         * A synchronous failure produces no STA_DISCONNECTED event, so the retry
         * chain would stop here with the GUI stuck on CONNECTING. Re-arm the timer
         * instead, which re-evaluates the state on the next tick.
         */
        ESP_LOGW(TAG, "retry connect failed: %s", esp_err_to_name(err));
        lock();
        /*
         * Mirror the normal drop path: park in DISCONNECTED (never CONNECTING, or
         * retry_timer_fired's own guard would refuse to reconnect) and re-arm.
         */
        s_mgr.info.connected = false;
        s_mgr.info.has_ip = false;
        publish_state_locked(WIFI_RUNTIME_STATE_DISCONNECTED);
        schedule_retry_locked();
        unlock();
    }
}

static void schedule_retry_locked(void)
{
    if (s_mgr.retry_count >= WIFI_RUNTIME_MAX_RETRY) {
        ESP_LOGW(TAG, "giving up after %d retries", s_mgr.retry_count);
        s_mgr.auto_reconnect_enabled = false;
        publish_state_locked(WIFI_RUNTIME_STATE_FAILED);
        return;
    }

    int32_t delay = retry_backoff_ms(s_mgr.retry_count);
    s_mgr.retry_count++;
    s_mgr.auto_reconnect_enabled = false;

    if (esp_timer_start_once(s_mgr.retry_timer, delay * 1000LL) != ESP_OK) {
        ESP_LOGE(TAG, "failed to arm reconnect timer");
        publish_state_locked(WIFI_RUNTIME_STATE_FAILED);
    }
}

static void handle_connected(wifi_event_sta_connected_t *event)
{
    lock();
    xEventGroupClearBits(s_mgr.events, WIFI_RUNTIME_BIT_DISCONNECTED);
    xEventGroupSetBits(s_mgr.events, WIFI_RUNTIME_BIT_CONNECTED);

    s_mgr.retry_count = 0;
    s_mgr.info.reason = 0;
    if (event) {
        s_mgr.info.channel = event->channel;
        memcpy(s_mgr.info.bssid, event->bssid, sizeof(s_mgr.info.bssid));
        size_t len = (event->ssid_len < sizeof(s_mgr.info.ssid)) ? event->ssid_len : sizeof(s_mgr.info.ssid);
        memcpy(s_mgr.info.ssid, event->ssid, len);
        s_mgr.info.ssid_len = (uint8_t)len;
    }

    publish_state_locked(WIFI_RUNTIME_STATE_CONNECTED);
    unlock();
}

static void handle_disconnected(wifi_event_sta_disconnected_t *event)
{
    lock();
    xEventGroupClearBits(s_mgr.events, WIFI_RUNTIME_BIT_CONNECTED);
    xEventGroupClearBits(s_mgr.events, WIFI_RUNTIME_BIT_GOT_IP);
    xEventGroupSetBits(s_mgr.events, WIFI_RUNTIME_BIT_DISCONNECTED);

    s_mgr.info.has_ip = false;
    s_mgr.info.channel = 0;
    memset(s_mgr.info.bssid, 0, sizeof(s_mgr.info.bssid));
    memset(s_mgr.info.ssid, 0, sizeof(s_mgr.info.ssid));
    s_mgr.info.ssid_len = 0;
    s_mgr.info.ip[0] = '\0';
    s_mgr.info.reason = event ? event->reason : 0;

    /* A failed association is reported as such; only a drop after GOT_IP is a plain disconnect. */
    bool wants_retry = s_mgr.auto_reconnect_enabled && !s_mgr.intentional_disconnect &&
                       (s_mgr.info.state == WIFI_RUNTIME_STATE_CONNECTED ||
                        s_mgr.info.state == WIFI_RUNTIME_STATE_CONNECTING);
    s_mgr.intentional_disconnect = false;

    if (wants_retry) {
        ESP_LOGI(TAG, "link lost (%s), reconnecting", wifi_runtime_reason_name(s_mgr.info.reason));
        publish_state_locked(WIFI_RUNTIME_STATE_DISCONNECTED);
        schedule_retry_locked();
    } else {
        publish_state_locked(WIFI_RUNTIME_STATE_FAILED);
    }
    unlock();
}

static void handle_got_ip(ip_event_got_ip_t *event)
{
    lock();
    xEventGroupSetBits(s_mgr.events, WIFI_RUNTIME_BIT_GOT_IP);

    s_mgr.retry_count = 0;
    s_mgr.info.reason = 0;
    if (event) {
        snprintf(s_mgr.info.ip, sizeof(s_mgr.info.ip), IPSTR, IP2STR(&event->ip_info.ip));
    }

    wifi_ap_record_t ap_info = {0};
    if (esp_wifi_sta_get_ap_info(&ap_info) == ESP_OK) {
        s_mgr.info.rssi = ap_info.rssi;
        s_mgr.info.channel = ap_info.primary;
        memcpy(s_mgr.info.bssid, ap_info.bssid, sizeof(s_mgr.info.bssid));
        /* The record is fixed 32 bytes, so the SSID length comes from the trailing NUL. */
        size_t len = strnlen((const char *)ap_info.ssid, sizeof(ap_info.ssid));
        memcpy(s_mgr.info.ssid, ap_info.ssid, len);
        s_mgr.info.ssid_len = (uint8_t)len;
    }

    ESP_LOGI(TAG, "got ip %s bssid=" MACSTR " ch=%u rssi=%d",
             s_mgr.info.ip, MAC2STR(s_mgr.info.bssid), s_mgr.info.channel, s_mgr.info.rssi);
    publish_state_locked(WIFI_RUNTIME_STATE_GOT_IP);
    unlock();
}

static void wifi_event_handler(void *arg, esp_event_base_t event_base, int32_t event_id, void *event_data)
{
    (void)arg;

    if (event_base == WIFI_EVENT) {
        if (event_id == WIFI_EVENT_STA_CONNECTED) {
            handle_connected((wifi_event_sta_connected_t *)event_data);
        } else if (event_id == WIFI_EVENT_STA_DISCONNECTED) {
            handle_disconnected((wifi_event_sta_disconnected_t *)event_data);
        }
    } else if (event_base == IP_EVENT && event_id == IP_EVENT_STA_GOT_IP) {
        handle_got_ip((ip_event_got_ip_t *)event_data);
    }
}

/* Drops any association left over from the previous AP so the scan is not pinned to it. */
static void clear_stale_association_locked(void)
{
    wifi_config_t current = {0};
    if (esp_wifi_get_config(WIFI_IF_STA, &current) != ESP_OK) {
        return;
    }

    current.sta.bssid_set = false;
    current.sta.channel = 0;
    current.sta.scan_method = WIFI_ALL_CHANNEL_SCAN;
    current.sta.sort_method = WIFI_CONNECT_AP_BY_SIGNAL;
    (void)esp_wifi_set_config(WIFI_IF_STA, &current);
}

static esp_err_t wait_for_bit(EventBits_t bit, uint32_t timeout_ms)
{
    EventBits_t bits = xEventGroupWaitBits(s_mgr.events, bit, pdFALSE, pdFALSE,
                                           pdMS_TO_TICKS(timeout_ms));
    return (bits & bit) ? ESP_OK : ESP_ERR_TIMEOUT;
}

/* One association attempt, ending either in GOT_IP or in a reported reason code. */
static esp_err_t connect_once(uint32_t timeout_ms, wifi_runtime_info_t *info)
{
    lock();
    s_mgr.retry_count = 0;
    s_mgr.auto_reconnect_enabled = false;
    s_mgr.info.reason = 0;
    xEventGroupClearBits(s_mgr.events, WIFI_RUNTIME_BIT_GOT_IP);
    publish_state_locked(WIFI_RUNTIME_STATE_CONNECTING);
    unlock();

    esp_err_t err = esp_wifi_connect();
    if (err != ESP_OK) {
        lock();
        publish_state_locked(WIFI_RUNTIME_STATE_FAILED);
        if (info) {
            *info = s_mgr.info;
        }
        unlock();
        return err;
    }

    err = wait_for_bit(WIFI_RUNTIME_BIT_GOT_IP, timeout_ms);

    lock();
    s_mgr.auto_reconnect_enabled = (err == ESP_OK);
    if (info) {
        *info = s_mgr.info;
    }
    unlock();
    return err;
}

static esp_err_t disconnect_and_wait(void)
{
    /*
     * A reconnect scheduled by a previous link loss would fire in the middle of a
     * manual reconfiguration and fight it for the STA config, so cancel it first.
     */
    esp_timer_stop(s_mgr.retry_timer);

    lock();
    s_mgr.retry_count = 0;
    s_mgr.intentional_disconnect = true;
    s_mgr.auto_reconnect_enabled = false;
    xEventGroupClearBits(s_mgr.events, WIFI_RUNTIME_BIT_DISCONNECTED);
    publish_state_locked(WIFI_RUNTIME_STATE_DISCONNECTING);
    unlock();

    esp_err_t err = esp_wifi_disconnect();
    if (err != ESP_OK) {
        lock();
        s_mgr.info.connected = false;
        s_mgr.info.has_ip = false;
        publish_state_locked(WIFI_RUNTIME_STATE_FAILED);
        unlock();
        return err;
    }

    err = wait_for_bit(WIFI_RUNTIME_BIT_DISCONNECTED, WIFI_RUNTIME_DISCONNECT_TIMEOUT_MS);
    if (err != ESP_OK) {
        /*
         * The DISCONNECTED event was lost, usually because the association was
         * already tearing down when the command arrived. Report a terminal state
         * anyway: staying in DISCONNECTING would leave the browser buttons locked
         * forever. intentional_disconnect stays set so a later link drop does not
         * silently undo a manual disconnect.
         */
        lock();
        s_mgr.info.connected = false;
        s_mgr.info.has_ip = false;
        publish_state_locked(WIFI_RUNTIME_STATE_DISCONNECTED);
        unlock();
    }
    return err;
}

esp_err_t wifi_runtime_manager_init(void)
{
    if (s_mgr.initialized) {
        return ESP_ERR_INVALID_STATE;
    }

    s_mgr.lock = xSemaphoreCreateMutex();
    if (!s_mgr.lock) {
        return ESP_ERR_NO_MEM;
    }
    s_mgr.events = xEventGroupCreate();
    if (!s_mgr.events) {
        return ESP_ERR_NO_MEM;
    }

    s_mgr.info.reason = 0;
    s_mgr.info.state = WIFI_RUNTIME_STATE_BOOTING;
    s_mgr.info.rssi = 0;
    s_mgr.auto_reconnect_enabled = true;

    esp_timer_create_args_t timer_args = {
        .callback = retry_timer_fired,
        .name = "wifi_retry",
    };
    if (esp_timer_create(&timer_args, &s_mgr.retry_timer) != ESP_OK) {
        return ESP_FAIL;
    }

    wifi_init_config_t init_cfg = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&init_cfg));

    esp_netif_inherent_config_t netif_cfg = ESP_NETIF_INHERENT_DEFAULT_WIFI_STA();
    s_mgr.sta_netif = esp_netif_create_wifi(WIFI_IF_STA, &netif_cfg);
    if (!s_mgr.sta_netif) {
        return ESP_FAIL;
    }
    esp_wifi_set_default_wifi_sta_handlers();

    /* RAM-only storage keeps credentials out of flash; boot always uses the Kconfig values. */
    ESP_ERROR_CHECK(esp_wifi_set_storage(WIFI_STORAGE_RAM));
    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
    ESP_ERROR_CHECK(esp_wifi_start());

    /*
     * Storage is RAM-only, so the Kconfig credentials must be applied explicitly
     * before the first connect. Without this the driver starts with an empty SSID
     * and the boot attempt fails with NO_AP_FOUND.
     */
    {
        /*
         * Follow the official example pattern: a zero-initialised config with
         * designated initialisers, so unused bytes stay zero. The STA ssid and
         * password fields are fixed arrays with no length member and the driver
         * derives the length from the trailing NUL.
         */
        wifi_config_t boot_cfg = {
            .sta = {
                .scan_method = WIFI_ALL_CHANNEL_SCAN,
                .sort_method = WIFI_CONNECT_AP_BY_SIGNAL,
                .threshold = {
                    .authmode = (CONFIG_EXAMPLE_WIFI_PASSWORD[0] != '\0')
                                    ? WIFI_AUTH_WPA2_PSK
                                    : WIFI_AUTH_OPEN,
                },
            },
        };
        strlcpy((char *)boot_cfg.sta.ssid, CONFIG_EXAMPLE_WIFI_SSID, sizeof(boot_cfg.sta.ssid));
        strlcpy((char *)boot_cfg.sta.password, CONFIG_EXAMPLE_WIFI_PASSWORD, sizeof(boot_cfg.sta.password));

        esp_err_t cfg_err = esp_wifi_set_config(WIFI_IF_STA, &boot_cfg);
        if (cfg_err != ESP_OK) {
            ESP_LOGE(TAG, "failed to apply boot credentials: %s", esp_err_to_name(cfg_err));
            return cfg_err;
        }
        ESP_LOGI(TAG, "boot credentials applied (ssid=\"%s\", auth=%d)",
                 boot_cfg.sta.ssid, (int)boot_cfg.sta.threshold.authmode);
    }

    ESP_ERROR_CHECK(esp_event_handler_register(WIFI_EVENT, WIFI_EVENT_STA_CONNECTED, wifi_event_handler, NULL));
    ESP_ERROR_CHECK(esp_event_handler_register(WIFI_EVENT, WIFI_EVENT_STA_DISCONNECTED, wifi_event_handler, NULL));
    ESP_ERROR_CHECK(esp_event_handler_register(IP_EVENT, IP_EVENT_STA_GOT_IP, wifi_event_handler, NULL));

    /* Disable power save so the CSI sampling cadence stays stable across reconnects. */
    ESP_ERROR_CHECK(esp_wifi_set_ps(WIFI_PS_NONE));

    s_mgr.initialized = true;
    return connect_once(WIFI_RUNTIME_BOOT_TIMEOUT_MS, NULL);
}

esp_err_t wifi_runtime_manager_set_credentials(const char *ssid, const char *password, wifi_runtime_info_t *info)
{
    if (!s_mgr.initialized) {
        return ESP_ERR_INVALID_STATE;
    }
    if (!ssid || ssid[0] == '\0') {
        return ESP_ERR_INVALID_ARG;
    }
    /*
     * wifi_sta_config_t has no ssid_len field (only the soft-AP config has one),
     * so the driver derives the SSID length from the trailing NUL. A 32-byte SSID
     * would fill the array with no terminator and be rejected or misread, so the
     * usable maximum through this API is 31 bytes even though 802.11 allows 32.
     */
    size_t ssid_len = strlen(ssid);
    if (ssid_len >= WIFI_RUNTIME_MAX_SSID_LEN) {
        return ESP_ERR_INVALID_ARG;
    }
    if (password && strlen(password) >= WIFI_RUNTIME_MAX_PASSPHRASE_LEN) {
        return ESP_ERR_INVALID_ARG;
    }

    lock();
    publish_state_locked(WIFI_RUNTIME_STATE_CONFIGURING);
    unlock();

    esp_err_t err = disconnect_and_wait();
    if (err != ESP_OK) {
        /*
         * A lost DISCONNECTED event leaves the STA possibly still associating, so
         * this can time out. That is not fatal: the state is already terminal and
         * esp_wifi_set_config() below retries on ESP_ERR_WIFI_STATE, so continuing
         * is what actually applies the requested credentials.
         */
        ESP_LOGW(TAG, "disconnect before reconfigure not confirmed: %s", esp_err_to_name(err));
    }

    lock();
    clear_stale_association_locked();

    wifi_config_t config = {0};
    err = esp_wifi_get_config(WIFI_IF_STA, &config);
    if (err != ESP_OK) {
        unlock();
        return err;
    }

    /*
     * Both fields must be cleared first. The previous config is read back with
     * esp_wifi_get_config(), so a shorter new password would otherwise leave
     * trailing bytes of the old one behind. IDF derives the length from the
     * trailing NUL, so the PMK would be computed from a corrupted string:
     * association succeeds but the 4-way handshake fails.
     */
    memset(config.sta.ssid, 0, sizeof(config.sta.ssid));
    memcpy(config.sta.ssid, ssid, ssid_len);
    memset(config.sta.password, 0, sizeof(config.sta.password));
    if (password) {
        memcpy(config.sta.password, password, strlen(password));
    }
    /*
     * threshold is carried over by esp_wifi_get_config(), so an explicit authmode
     * is required: without it a previous WPA2 threshold would reject an open AP,
     * and a stale WPA3 threshold would reject a WPA2 one.
     */
    config.sta.threshold.authmode = (config.sta.password[0] == '\0') ? WIFI_AUTH_OPEN
                                                                   : WIFI_AUTH_WPA2_PSK;

    /*
     * esp_wifi_set_config() returns ESP_ERR_WIFI_STATE while the STA is still
     * connecting, which is reachable when the DISCONNECTED event was lost. Give
     * the driver a few short retries instead of failing the whole reconfiguration.
     */
    for (int attempt = 0; attempt < WIFI_RUNTIME_SET_CONFIG_RETRY; attempt++) {
        err = esp_wifi_set_config(WIFI_IF_STA, &config);
        if (err == ESP_OK || err != ESP_ERR_WIFI_STATE) {
            break;
        }
        unlock();
        vTaskDelay(pdMS_TO_TICKS(WIFI_RUNTIME_SET_CONFIG_RETRY_MS));
        lock();
    }
    unlock();
    if (err != ESP_OK) {
        lock();
        publish_state_locked(WIFI_RUNTIME_STATE_FAILED);
        if (info) {
            *info = s_mgr.info;
        }
        unlock();
        return err;
    }

    return connect_once(WIFI_RUNTIME_CONNECT_TIMEOUT_MS, info);
}

esp_err_t wifi_runtime_manager_disconnect(void)
{
    if (!s_mgr.initialized) {
        return ESP_ERR_INVALID_STATE;
    }

    esp_err_t err = disconnect_and_wait();
    /*
     * intentional_disconnect is deliberately left set even on timeout: the user
     * asked to be disconnected, so a later link drop must not auto-reconnect.
     * An explicit reconnect or set_credentials clears it again.
     */
    if (err == ESP_OK) {
        lock();
        s_mgr.intentional_disconnect = true;
        unlock();
    }
    return err;
}

esp_err_t wifi_runtime_manager_reconnect(void)
{
    if (!s_mgr.initialized) {
        return ESP_ERR_INVALID_STATE;
    }

    disconnect_and_wait();

    lock();
    clear_stale_association_locked();
    unlock();

    return connect_once(WIFI_RUNTIME_CONNECT_TIMEOUT_MS, NULL);
}
