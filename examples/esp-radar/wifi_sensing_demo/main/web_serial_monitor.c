/*
 * SPDX-FileCopyrightText: 2026 Espressif Systems (Shanghai) CO LTD
 *
 * SPDX-License-Identifier: Apache-2.0
 */
#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <stdarg.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <unistd.h>

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/semphr.h"

#if CONFIG_SOC_USB_SERIAL_JTAG_SUPPORTED
#include "driver/usb_serial_jtag.h"
#endif
#include "esp_check.h"
#include "esp_log.h"
#include "esp_mac.h"
#include "esp_netif.h"
#include "esp_timer.h"
#include "esp_wifi.h"
#include "mbedtls/base64.h"
#include "sdkconfig.h"

#include "web_serial_monitor.h"
#include "wifi_runtime_manager.h"

#define WEB_SERIAL_PREFIX            "HMS:"
#define WEB_SERIAL_COMMAND_PREFIX    "HMSCMD "
#define WEB_SERIAL_TASK_STACK_SIZE   6144
#define WEB_SERIAL_TASK_PRIORITY     4
#define WEB_SERIAL_LINE_BUF_SIZE     512
/*
 * A full sample line with three MAC strings and the FSM's float fields reaches
 * roughly 900 bytes, so 1 KiB left no margin and truncation produced invalid JSON.
 */
#define WEB_SERIAL_TX_BUF_SIZE       2048
#define WEB_SERIAL_RX_POLL_BUF_SIZE  64
#define WEB_SERIAL_DEFAULT_PERIOD_MS 50
#define WEB_SERIAL_CSI_DEFAULT_PERIOD_MS 100
#define WEB_SERIAL_CSI_MAX_RAW_LEN 512
#define WEB_SERIAL_CSI_MAX_ENCODED_LEN (((WEB_SERIAL_CSI_MAX_RAW_LEN + 2) / 3) * 4 + 1)

static const char *TAG = "web_serial_monitor";

/*
 * This module exposes a tiny line-oriented JSON protocol over the serial
 * console so the browser UI can observe and tune the sensing FSM without any
 * additional transport layer.
 */
typedef struct {
    bool initialized;
    /* Sensing is bound lazily: the monitor runs before Wi-Fi so boot states are visible. */
    bool sensing_ready;
    bool stream_enabled;
    esp_wifi_sensing_fsm_handle_t fsm;
    web_serial_monitor_peer_t peers[WEB_SERIAL_MONITOR_MAX_PEERS];
    size_t peer_num;
    uint32_t stream_period_ms;
    bool csi_stream_enabled;
    uint32_t csi_stream_period_ms;
    int64_t csi_last_emit_us;
    uint32_t csi_dropped_count;
    /* A reconfiguration is in flight, so the GUI must keep its buttons disabled. */
    bool wifi_busy;
    /* Messages dropped because they exceeded WEB_SERIAL_TX_BUF_SIZE. */
    uint32_t truncated_msg_count;
    TaskHandle_t task;
#if CONFIG_SOC_USB_SERIAL_JTAG_SUPPORTED
    bool usb_driver_owned;
#endif
} web_serial_monitor_ctx_t;

static web_serial_monitor_ctx_t s_ctx = {0};

static void handle_command(char *line);
static void send_ack(const char *cmd, bool ok, const char *detail);
static void send_wifi_result(const char *cmd, esp_err_t err, const wifi_runtime_info_t *info);
static void send_wifi_info(void);
static void send_hello(void);
static void send_all_configs(void);

static int hex_value(char ch)
{
    if (ch >= '0' && ch <= '9') {
        return ch - '0';
    }
    if (ch >= 'a' && ch <= 'f') {
        return ch - 'a' + 10;
    }
    if (ch >= 'A' && ch <= 'F') {
        return ch - 'A' + 10;
    }
    return -1;
}

static esp_err_t decode_hex_string(const char *encoded, uint8_t *decoded, size_t decoded_size, size_t *decoded_len)
{
    if (!encoded || !decoded || !decoded_len) {
        return ESP_ERR_INVALID_ARG;
    }

    size_t encoded_len = strlen(encoded);
    if ((encoded_len % 2) != 0 || encoded_len / 2 >= decoded_size) {
        return ESP_ERR_INVALID_SIZE;
    }

    for (size_t i = 0; i < encoded_len / 2; i++) {
        int high = hex_value(encoded[i * 2]);
        int low = hex_value(encoded[i * 2 + 1]);
        if (high < 0 || low < 0) {
            return ESP_ERR_INVALID_ARG;
        }
        decoded[i] = (uint8_t)((high << 4) | low);
    }
    *decoded_len = encoded_len / 2;
    decoded[*decoded_len] = '\0';
    return ESP_OK;
}

static void handle_wifi_config_hex(char *args)
{
    char *saveptr = NULL;
    char *ssid_hex = strtok_r(args, " ", &saveptr);
    char *password_hex = strtok_r(NULL, " ", &saveptr);
    uint8_t ssid[33] = {0};
    uint8_t password[65] = {0};
    size_t ssid_len = 0;
    size_t password_len = 0;

    if (!ssid_hex ||
        decode_hex_string(ssid_hex, ssid, sizeof(ssid), &ssid_len) != ESP_OK ||
        ssid_len == 0 || ssid_len > 32) {
        send_ack("WIFI_CONFIG", false, "invalid hex ssid");
        return;
    }

    /* An omitted password is valid and means an open network. */
    if (password_hex) {
        if (decode_hex_string(password_hex, password, sizeof(password), &password_len) != ESP_OK ||
            password_len > 64) {
            send_ack("WIFI_CONFIG", false, "invalid hex password");
            return;
        }
    }

    if (s_ctx.wifi_busy) {
        send_ack("WIFI_CONFIG", false, "another wifi operation is in progress");
        return;
    }
    s_ctx.wifi_busy = true;

    /* The manager owns the disconnect/reconnect ordering; this only supplies credentials. */
    wifi_runtime_info_t info = {0};
    esp_err_t err = wifi_runtime_manager_set_credentials((const char *)ssid,
                                                         password_len ? (const char *)password : NULL,
                                                         &info);

    s_ctx.wifi_busy = false;

    if (err != ESP_OK) {
        send_wifi_result("WIFI_CONFIG", err, &info);
        return;
    }
    send_wifi_result("WIFI_CONFIG", ESP_OK, &info);
}

static esp_err_t configure_stdin_nonblocking(void)
{
    int fd = fileno(stdin);
    if (fd < 0) {
        ESP_LOGE(TAG, "failed to get stdin fd");
        return ESP_FAIL;
    }

    int flags = fcntl(fd, F_GETFL, 0);
    if (flags < 0) {
        ESP_LOGE(TAG, "failed to get stdin flags: errno=%d", errno);
        return ESP_FAIL;
    }

    if ((flags & O_NONBLOCK) != 0) {
        return ESP_OK;
    }

    if (fcntl(fd, F_SETFL, flags | O_NONBLOCK) < 0) {
        ESP_LOGE(TAG, "failed to set stdin nonblocking: errno=%d", errno);
        return ESP_FAIL;
    }

    return ESP_OK;
}

#if CONFIG_SOC_USB_SERIAL_JTAG_SUPPORTED
static esp_err_t configure_usb_serial_jtag_input(void)
{
    if (usb_serial_jtag_is_driver_installed()) {
        return ESP_OK;
    }

    usb_serial_jtag_driver_config_t usb_cfg = USB_SERIAL_JTAG_DRIVER_CONFIG_DEFAULT();
    usb_cfg.rx_buffer_size = 512;
    usb_cfg.tx_buffer_size = 256;
    esp_err_t err = usb_serial_jtag_driver_install(&usb_cfg);
    if (err == ESP_OK) {
        s_ctx.usb_driver_owned = true;
    }
    return err;
}
#endif

static void process_rx_bytes(char *line_buf, size_t *line_len, const uint8_t *rx_buf, size_t read_len)
{
    if (!line_buf || !line_len || !rx_buf || read_len == 0) {
        return;
    }

    /* Commands are newline-delimited so both terminals and browsers can share the same protocol. */
    for (size_t i = 0; i < read_len; i++) {
        char ch = (char)rx_buf[i];
        if (ch == '\r') {
            continue;
        }
        if (ch == '\n') {
            line_buf[*line_len] = '\0';
            handle_command(line_buf);
            *line_len = 0;
            continue;
        }
        if (*line_len < (WEB_SERIAL_LINE_BUF_SIZE - 1)) {
            line_buf[(*line_len)++] = ch;
        } else {
            *line_len = 0;
        }
    }
}

static const char *state_name(esp_wifi_sensing_fsm_process_state_t state)
{
    switch (state) {
    case ESP_WIFI_SENSING_FSM_PROCESS_IDLE:
        return "IDLE";
    case ESP_WIFI_SENSING_FSM_PROCESS_DEBOUNCE_ACTIVE:
        return "DEBOUNCE_ACTIVE";
    case ESP_WIFI_SENSING_FSM_PROCESS_ACTIVE:
        return "ACTIVE";
    case ESP_WIFI_SENSING_FSM_PROCESS_DEBOUNCE_INACTIVE:
        return "DEBOUNCE_INACTIVE";
    default:
        return "UNKNOWN";
    }
}

static const char *init_stage_name(esp_wifi_sensing_fsm_init_stage_t stage)
{
    switch (stage) {
    case ESP_WIFI_SENSING_FSM_INIT_STAGE_START:
        return "START";
    case ESP_WIFI_SENSING_FSM_INIT_STAGE_GOLD_FOUND:
        return "GOLD_FOUND";
    case ESP_WIFI_SENSING_FSM_INIT_STAGE_STABLE:
        return "STABLE";
    default:
        return "UNKNOWN";
    }
}

static const char *train_status_name(esp_wifi_sensing_fsm_train_status_t status)
{
    switch (status) {
    case ESP_WIFI_SENSING_FSM_TRAIN_STATUS_NONE:
        return "NONE";
    case ESP_WIFI_SENSING_FSM_TRAIN_STATUS_PROGRESS:
        return "PROGRESS";
    case ESP_WIFI_SENSING_FSM_TRAIN_STATUS_COMPLETE:
        return "COMPLETE";
    default:
        return "UNKNOWN";
    }
}

static const char *train_action_name(esp_wifi_sensing_fsm_train_action_t action)
{
    switch (action) {
    case ESP_WIFI_SENSING_FSM_TRAIN_ACTION_IDLE:
        return "IDLE";
    case ESP_WIFI_SENSING_FSM_TRAIN_ACTION_WAIT_BUFFER:
        return "WAIT_BUFFER";
    case ESP_WIFI_SENSING_FSM_TRAIN_ACTION_DISCARD_OUTLIER:
        return "DISCARD_OUTLIER";
    case ESP_WIFI_SENSING_FSM_TRAIN_ACTION_COLLECT_SAMPLE:
        return "COLLECT_SAMPLE";
    case ESP_WIFI_SENSING_FSM_TRAIN_ACTION_ACCUMULATE_BACKGROUND:
        return "ACCUMULATE_BACKGROUND";
    default:
        return "UNKNOWN";
    }
}

static const web_serial_monitor_peer_t *find_peer_by_name_or_mac(const char *token)
{
    if (!token) {
        return NULL;
    }

    for (size_t i = 0; i < s_ctx.peer_num; i++) {
        const web_serial_monitor_peer_t *peer = &s_ctx.peers[i];
        if (strcmp(token, peer->name) == 0) {
            return peer;
        }

        char mac_str[18] = {0};
        snprintf(mac_str, sizeof(mac_str), MACSTR, MAC2STR(peer->mac));
        if (strcasecmp(token, mac_str) == 0) {
            return peer;
        }
    }

    return NULL;
}

/*
 * The line buffer must not live on a caller's stack: this runs from the 4 KiB
 * monitor task and from the esp_radar CSI callback, and a 2 KiB stack buffer
 * overflowed both. It is heap-allocated once and guarded so concurrent
 * fwrite() calls cannot interleave two messages into one line.
 */
static char *s_tx_line = NULL;
static SemaphoreHandle_t s_tx_lock = NULL;

static int write_line(const char *fmt, ...)
{
    if (!s_tx_line || !s_tx_lock) {
        return 0;
    }

    if (xSemaphoreTake(s_tx_lock, pdMS_TO_TICKS(50)) != pdTRUE) {
        return 0;
    }

    int result = 0;
    char *line = s_tx_line;
    line[0] = '\0';

    /* Prefix structured messages so ordinary ESP logs can coexist on the same port. */
    int prefix_len = snprintf(line, WEB_SERIAL_TX_BUF_SIZE, "%s", WEB_SERIAL_PREFIX);
    if (prefix_len <= 0 || prefix_len >= WEB_SERIAL_TX_BUF_SIZE) {
        goto done;
    }

    va_list args;
    va_start(args, fmt);
    int body_len = vsnprintf(line + prefix_len, WEB_SERIAL_TX_BUF_SIZE - prefix_len, fmt, args);
    va_end(args);
    if (body_len < 0) {
        goto done;
    }

    int total_len = prefix_len + body_len;
    if (total_len >= WEB_SERIAL_TX_BUF_SIZE) {
        /*
         * Truncating would emit invalid JSON and desync the browser parser, so the
         * message is dropped and counted instead.
         */
        s_ctx.truncated_msg_count++;
        ESP_LOGW(TAG, "dropped oversized message: need=%d capacity=%d",
                 total_len, WEB_SERIAL_TX_BUF_SIZE);
        goto done;
    }

    result = (int)fwrite(line, 1, total_len, stdout);
    fflush(stdout);

done:
    xSemaphoreGive(s_tx_lock);
    return result;
}

void web_serial_monitor_csi_callback(void *ctx, const wifi_csi_filtered_info_t *info)
{
    (void)ctx;
    if (!info || !s_ctx.initialized || !s_ctx.sensing_ready ||
            !s_ctx.csi_stream_enabled || !info->raw_data || info->raw_len == 0) {
        return;
    }

    int64_t now_us = esp_timer_get_time();
    if (s_ctx.csi_last_emit_us > 0 &&
        now_us - s_ctx.csi_last_emit_us < (int64_t)s_ctx.csi_stream_period_ms * 1000LL) {
        s_ctx.csi_dropped_count++;
        return;
    }
    if (info->raw_len > WEB_SERIAL_CSI_MAX_RAW_LEN) {
        s_ctx.csi_dropped_count++;
        return;
    }

    char encoded[WEB_SERIAL_CSI_MAX_ENCODED_LEN] = {0};
    size_t encoded_len = 0;
    if (mbedtls_base64_encode((unsigned char *)encoded, sizeof(encoded) - 1, &encoded_len,
                              (const unsigned char *)info->raw_data, info->raw_len) != 0) {
        s_ctx.csi_dropped_count++;
        return;
    }
    encoded[encoded_len] = '\0';
    s_ctx.csi_last_emit_us = now_us;
    (void)write_line(
        "{\"type\":\"csi\",\"seq\":%" PRIu32 ",\"mac\":\"" MACSTR "\",\"rssi\":%d,\"raw_len\":%u,\"data_type\":%d,\"dropped\":%" PRIu32 ",\"data\":\"%s\"}\n",
        info->seq_id, MAC2STR(info->mac), info->rx_ctrl_info.rssi, info->raw_len,
        (int)info->data_type, s_ctx.csi_dropped_count, encoded);
}

static void send_error(const char *message)
{
    if (!message) {
        return;
    }
    (void)write_line("{\"type\":\"error\",\"message\":\"%s\"}\n", message);
}

static void send_ack(const char *cmd, bool ok, const char *detail)
{
    (void)write_line("{\"type\":\"ack\",\"cmd\":\"%s\",\"ok\":%s,\"detail\":\"%s\"}\n",
                     cmd ? cmd : "",
                     ok ? "true" : "false",
                     detail ? detail : "");
}

static void send_runtime_config(void)
{
    bool enabled = false;
    if (!s_ctx.sensing_ready) {
        (void)write_line("{\"type\":\"runtime\",\"amplitude_log_enabled\":false,\"sensing_ready\":false}\n");
        return;
    }
    if (esp_wifi_sensing_fsm_get_amplitude_log_enabled(s_ctx.fsm, &enabled) != ESP_OK) {
        return;
    }
    (void)write_line("{\"type\":\"runtime\",\"amplitude_log_enabled\":%s,\"sensing_ready\":true}\n",
                     enabled ? "true" : "false");
}

/* Escapes the bytes of an SSID so control characters cannot break the JSON line. */
static void ssid_to_json(const uint8_t *ssid, uint8_t ssid_len, char *out, size_t out_size)
{
    size_t used = 0;
    for (uint8_t i = 0; i < ssid_len && (used + 7) < out_size; i++) {
        uint8_t ch = ssid[i];
        if (ch == '"' || ch == '\\') {
            used += (size_t)snprintf(out + used, out_size - used, "\\%c", ch);
        } else if (ch < 0x20 || ch == 0x7f) {
            used += (size_t)snprintf(out + used, out_size - used, "\\u%04x", ch);
        } else {
            out[used++] = (char)ch;
        }
    }
    out[used] = '\0';
}

void web_serial_monitor_notify_wifi_state(void)
{
    if (!s_ctx.initialized) {
        return;
    }
    send_wifi_info();
}

static void send_wifi_info(void)
{
    wifi_runtime_info_t info = {0};
    wifi_runtime_manager_get_info(&info);

    char ssid_json[96] = {0};
    ssid_to_json(info.ssid, info.ssid_len, ssid_json, sizeof(ssid_json));

    (void)write_line(
        "{\"type\":\"wifi\",\"state\":\"%s\",\"connected\":%s,\"has_ip\":%s,"
        "\"bssid\":\"" MACSTR "\",\"ssid\":\"%s\",\"channel\":%u,\"rssi\":%d,\"ip\":\"%s\","
        "\"reason\":%u,\"reason_name\":\"%s\"}\n",
        wifi_runtime_state_name(info.state),
        info.connected ? "true" : "false",
        info.has_ip ? "true" : "false",
        MAC2STR(info.bssid),
        ssid_json,
        info.channel,
        info.rssi,
        info.ip,
        info.reason,
        wifi_runtime_reason_name(info.reason));
}

/* Reports the terminal result of a Wi-Fi command together with the reason code. */
static void send_wifi_result(const char *cmd, esp_err_t err, const wifi_runtime_info_t *info)
{
    wifi_runtime_info_t snapshot = {0};
    if (info) {
        snapshot = *info;
    } else {
        wifi_runtime_manager_get_info(&snapshot);
    }

    char ssid_json[96] = {0};
    ssid_to_json(snapshot.ssid, snapshot.ssid_len, ssid_json, sizeof(ssid_json));

    if (err != ESP_OK) {
        (void)write_line(
            "{\"type\":\"wifi_result\",\"cmd\":\"%s\",\"ok\":false,\"detail\":\"%s\","
            "\"state\":\"%s\",\"reason\":%u,\"reason_name\":\"%s\"}\n",
            cmd ? cmd : "",
            esp_err_to_name(err),
            wifi_runtime_state_name(snapshot.state),
            snapshot.reason,
            wifi_runtime_reason_name(snapshot.reason));
    } else {
        (void)write_line(
            "{\"type\":\"wifi_result\",\"cmd\":\"%s\",\"ok\":true,\"state\":\"%s\","
            "\"bssid\":\"" MACSTR "\",\"ssid\":\"%s\",\"channel\":%u,\"rssi\":%d,\"ip\":\"%s\"}\n",
            cmd ? cmd : "",
            wifi_runtime_state_name(snapshot.state),
            MAC2STR(snapshot.bssid),
            ssid_json,
            snapshot.channel,
            snapshot.rssi,
            snapshot.ip);
    }
}

static void send_hello(void)
{
    char peers_json[256] = {0};
    size_t used = 0;
    for (size_t i = 0; i < s_ctx.peer_num; i++) {
        char item[48] = {0};
        snprintf(item, sizeof(item), "%s\"%s\"", (i == 0) ? "" : ",", s_ctx.peers[i].name);
        size_t item_len = strlen(item);
        if ((used + item_len + 1) >= sizeof(peers_json)) {
            break;
        }
        memcpy(peers_json + used, item, item_len);
        used += item_len;
        peers_json[used] = '\0';
    }

    bool enabled = false;
    if (s_ctx.sensing_ready) {
        (void)esp_wifi_sensing_fsm_get_amplitude_log_enabled(s_ctx.fsm, &enabled);
    }
    /* Send enough metadata for the web page to populate its initial UI state. */
    (void)write_line(
        "{\"type\":\"hello\",\"transport\":\"stdio\",\"target\":\"%s\",\"stream_period_ms\":%" PRIu32 ",\"amplitude_log_enabled\":%s,\"csi_stream_enabled\":%s,\"csi_stream_period_ms\":%" PRIu32 ",\"sensing_ready\":%s,\"peers\":[%s]}\n",
        CONFIG_IDF_TARGET,
        s_ctx.stream_period_ms,
        enabled ? "true" : "false",
        s_ctx.csi_stream_enabled ? "true" : "false",
        s_ctx.csi_stream_period_ms,
        s_ctx.sensing_ready ? "true" : "false",
        peers_json);
}

static void send_channel_config(const web_serial_monitor_peer_t *peer)
{
    if (!peer || !s_ctx.sensing_ready) {
        return;
    }

    esp_wifi_sensing_fsm_channel_config_t cfg = {0};
    if (esp_wifi_sensing_fsm_get_channel_config(s_ctx.fsm, peer->mac, &cfg) != ESP_OK) {
        return;
    }

    (void)write_line(
        "{\"type\":\"config\",\"peer\":\"%s\",\"mac\":\"" MACSTR "\",\"sensitivity\":%.6f,"
        "\"presence_sensitivity\":%.6f,"
        "\"active_jitter_min\":%.6f,"
        "\"active_filter_ms\":%" PRIu32 "}\n",
        peer->name,
        MAC2STR(peer->mac),
        cfg.sensitivity,
        cfg.presence_sensitivity,
        cfg.active_jitter_min,
        cfg.active_filter_ms);
}

static void send_all_configs(void)
{
    for (size_t i = 0; i < s_ctx.peer_num; i++) {
        send_channel_config(&s_ctx.peers[i]);
    }
}

static void send_channel_sample(const web_serial_monitor_peer_t *peer)
{
    if (!peer || !s_ctx.sensing_ready) {
        return;
    }

    esp_wifi_sensing_fsm_channel_diag_t diag = {0};
    if (esp_wifi_sensing_fsm_get_channel_diag(s_ctx.fsm, peer->mac, &diag) != ESP_OK) {
        return;
    }
    esp_wifi_sensing_fsm_state_t motion_state = ESP_WIFI_SENSING_FSM_STATE_INACTIVE;
    if (esp_wifi_sensing_fsm_get_state(s_ctx.fsm, peer->mac, &motion_state) != ESP_OK) {
        return;
    }

    /* Ship only the minimum public diagnostics required by the browser UI. */
    (void)write_line(
        "{\"type\":\"sample\",\"ts_ms\":%" PRIu64 ",\"peer\":\"%s\",\"mac\":\"" MACSTR "\","
        "\"motion_status\":%s,\"motion_state\":%d,"
        "\"jitter_value\":%.6f,"
        "\"wander_value\":%.6f,"
        "\"presence_ready\":%s,\"presence_wander_average\":%.6f,\"presence_someone_threshold\":%.6f,\"presence_someone_status\":%s,"
        "\"train_wander_threshold\":%.6f,\"train_jitter_threshold\":%.6f,\"train_thresholds_valid\":%s,"
        "\"train_status\":%d,\"train_status_name\":\"%s\",\"train_last_action\":%d,\"train_last_action_name\":\"%s\","
        "\"train_sample_count\":%" PRIu32 ",\"train_background_count\":%" PRIu32 ","
        "\"train_background_avg\":%.6f,\"train_last_basis_wander\":%.6f,"
        "\"smooth_scaled\":%" PRIu32 ",\"enter_level_scaled\":%" PRIu32 ",\"exit_level_scaled\":%" PRIu32 ","
        "\"state\":%d,\"state_name\":\"%s\",\"init_stage\":%d,\"init_stage_name\":\"%s\"}\n",
        (uint64_t)(esp_timer_get_time() / 1000ULL),
        peer->name,
        MAC2STR(peer->mac),
        (motion_state == ESP_WIFI_SENSING_FSM_STATE_ACTIVE) ? "true" : "false",
        (int)motion_state,
        diag.jitter_value,
        diag.wander_value,
        diag.presence_ready ? "true" : "false",
        diag.presence_wander_average,
        diag.presence_someone_threshold,
        diag.presence_someone_status ? "true" : "false",
        diag.train_wander_threshold,
        diag.train_jitter_threshold,
        diag.train_thresholds_valid ? "true" : "false",
        (int)diag.train_status,
        train_status_name(diag.train_status),
        (int)diag.train_last_action,
        train_action_name(diag.train_last_action),
        diag.train_sample_count,
        diag.train_background_count,
        diag.train_background_avg,
        diag.train_last_basis_wander,
        diag.smooth_scaled,
        diag.enter_level_scaled,
        diag.exit_level_scaled,
        (int)diag.state,
        state_name(diag.state),
        (int)diag.init_stage,
        init_stage_name(diag.init_stage));
}

static void apply_cfg_value(esp_wifi_sensing_fsm_channel_config_t *cfg, const char *key, const char *value)
{
    if (!cfg || !key || !value) {
        return;
    }

    if (strcmp(key, "motion_sensitivity") == 0) {
        cfg->sensitivity = strtof(value, NULL);
    } else if (strcmp(key, "presence_sensitivity") == 0) {
        cfg->presence_sensitivity = strtof(value, NULL);
    } else if (strcmp(key, "active_jitter_min") == 0) {
        cfg->active_jitter_min = strtof(value, NULL);
    } else if (strcmp(key, "active_filter_ms") == 0) {
        cfg->active_filter_ms = (uint32_t)strtoul(value, NULL, 10);
    }
}

static void handle_set_cfg(char *args)
{
    char *saveptr = NULL;
    char *peer_token = strtok_r(args, " ", &saveptr);
    if (!peer_token) {
        send_ack("SET_CFG", false, "missing peer");
        return;
    }

    const web_serial_monitor_peer_t *peer = find_peer_by_name_or_mac(peer_token);
    if (!peer) {
        send_ack("SET_CFG", false, "peer not found");
        return;
    }

    esp_wifi_sensing_fsm_channel_config_t cfg = {0};
    if (esp_wifi_sensing_fsm_get_channel_config(s_ctx.fsm, peer->mac, &cfg) != ESP_OK) {
        send_ack("SET_CFG", false, "get cfg failed");
        return;
    }

    char *token = NULL;
    while ((token = strtok_r(NULL, " ", &saveptr)) != NULL) {
        char *sep = strchr(token, '=');
        if (!sep) {
            continue;
        }
        *sep = '\0';
        apply_cfg_value(&cfg, token, sep + 1);
    }

    if (esp_wifi_sensing_fsm_set_channel_config(s_ctx.fsm, peer->mac, &cfg) != ESP_OK) {
        send_ack("SET_CFG", false, "set cfg failed");
        return;
    }

    send_ack("SET_CFG", true, peer->name);
    send_channel_config(peer);
}

static void handle_command(char *line)
{
    if (!line || strncmp(line, WEB_SERIAL_COMMAND_PREFIX, strlen(WEB_SERIAL_COMMAND_PREFIX)) != 0) {
        return;
    }

    /* The command grammar stays intentionally small to keep the demo debuggable from a plain terminal. */
    char *cmd = line + strlen(WEB_SERIAL_COMMAND_PREFIX);

    /*
     * Wi-Fi commands are always allowed, even before sensing is up, because the
     * browser may need to fix the AP before the FSM can ever start.
     */
    if (strncmp(cmd, "WIFI_", 5) == 0) {
        if (strcmp(cmd, "WIFI_INFO") == 0) {
            send_wifi_info();
            send_ack("WIFI_INFO", true, "wifi");
            return;
        }
        if (strncmp(cmd, "WIFI_CONFIG_HEX ", 16) == 0) {
            handle_wifi_config_hex(cmd + 16);
            return;
        }
        if (strcmp(cmd, "WIFI_DISCONNECT") == 0) {
            esp_err_t err = wifi_runtime_manager_disconnect();
            send_wifi_result("WIFI_DISCONNECT", err, NULL);
            return;
        }
        if (strcmp(cmd, "WIFI_RECONNECT") == 0) {
            esp_err_t err = wifi_runtime_manager_reconnect();
            send_wifi_result("WIFI_RECONNECT", err, NULL);
            return;
        }
    }

    if (!s_ctx.sensing_ready) {
        send_ack(cmd, false, "sensing not ready");
        return;
    }

    if (strcmp(cmd, "HELLO") == 0) {
        send_hello();
        send_runtime_config();
        send_all_configs();
        return;
    }

    if (strcmp(cmd, "START_STREAM") == 0) {
        s_ctx.stream_enabled = true;
        send_ack("START_STREAM", true, "stream enabled");
        return;
    }

    if (strcmp(cmd, "STOP_STREAM") == 0) {
        s_ctx.stream_enabled = false;
        send_ack("STOP_STREAM", true, "stream disabled");
        return;
    }

    if (strcmp(cmd, "START_CSI_STREAM") == 0) {
        s_ctx.csi_stream_enabled = true;
        s_ctx.csi_last_emit_us = 0;
        s_ctx.csi_dropped_count = 0;
        send_ack("START_CSI_STREAM", true, "csi stream enabled");
        return;
    }

    if (strcmp(cmd, "STOP_CSI_STREAM") == 0) {
        s_ctx.csi_stream_enabled = false;
        send_ack("STOP_CSI_STREAM", true, "csi stream disabled");
        return;
    }

    if (strncmp(cmd, "SET_CSI_PERIOD ", 15) == 0) {
        uint32_t period_ms = (uint32_t)strtoul(cmd + 15, NULL, 10);
        if (period_ms < 20 || period_ms > 1000) {
            send_ack("SET_CSI_PERIOD", false, "period must be 20..1000 ms");
            return;
        }
        s_ctx.csi_stream_period_ms = period_ms;
        send_ack("SET_CSI_PERIOD", true, "period updated");
        return;
    }

    if (strcmp(cmd, "FSM_START") == 0) {
        esp_err_t err = esp_wifi_sensing_fsm_control(s_ctx.fsm, ESP_WIFI_SENSING_FSM_CTRL_START, NULL);
        send_ack("FSM_START", err == ESP_OK, esp_err_to_name(err));
        return;
    }

    if (strcmp(cmd, "FSM_STOP") == 0) {
        esp_err_t err = esp_wifi_sensing_fsm_control(s_ctx.fsm, ESP_WIFI_SENSING_FSM_CTRL_STOP, NULL);
        send_ack("FSM_STOP", err == ESP_OK, esp_err_to_name(err));
        return;
    }

    if (strcmp(cmd, "RESET_BASELINE") == 0) {
        esp_err_t err = esp_wifi_sensing_fsm_control(s_ctx.fsm, ESP_WIFI_SENSING_FSM_CTRL_RESET_BASELINE, NULL);
        send_ack("RESET_BASELINE", err == ESP_OK, esp_err_to_name(err));
        return;
    }

    if (strncmp(cmd, "GET_CFG", 7) == 0) {
        char *arg = cmd + 7;
        while (*arg == ' ') {
            arg++;
        }
        if (*arg == '\0' || strcmp(arg, "ALL") == 0) {
            send_all_configs();
            send_ack("GET_CFG", true, "all");
            return;
        }

        const web_serial_monitor_peer_t *peer = find_peer_by_name_or_mac(arg);
        if (!peer) {
            send_ack("GET_CFG", false, "peer not found");
            return;
        }
        send_channel_config(peer);
        send_ack("GET_CFG", true, peer->name);
        return;
    }

    if (strcmp(cmd, "GET_RUNTIME") == 0) {
        send_runtime_config();
        send_ack("GET_RUNTIME", true, "runtime");
        return;
    }

    if (strncmp(cmd, "SET_AMPLITUDE_LOG ", 18) == 0) {
        const char *value = cmd + 18;
        bool enabled = false;
        if ((strcmp(value, "1") == 0) || (strcasecmp(value, "true") == 0) || (strcasecmp(value, "on") == 0)) {
            enabled = true;
        } else if ((strcmp(value, "0") == 0) || (strcasecmp(value, "false") == 0) || (strcasecmp(value, "off") == 0)) {
            enabled = false;
        } else {
            send_ack("SET_AMPLITUDE_LOG", false, "invalid value");
            return;
        }

        esp_err_t err = esp_wifi_sensing_fsm_set_amplitude_log_enabled(s_ctx.fsm, enabled);
        send_ack("SET_AMPLITUDE_LOG", err == ESP_OK, esp_err_to_name(err));
        if (err == ESP_OK) {
            send_runtime_config();
            send_hello();
        }
        return;
    }

    if (strncmp(cmd, "SET_CFG ", 8) == 0) {
        handle_set_cfg(cmd + 8);
        return;
    }

    if (strncmp(cmd, "TRAIN_START ", 12) == 0) {
        const char *arg = cmd + 12;
        while (*arg == ' ') {
            arg++;
        }
        const web_serial_monitor_peer_t *peer = find_peer_by_name_or_mac(arg);
        if (!peer) {
            send_ack("TRAIN_START", false, "peer not found");
            return;
        }
        esp_err_t err = esp_wifi_sensing_fsm_train_start(s_ctx.fsm, peer->mac);
        send_ack("TRAIN_START", err == ESP_OK, esp_err_to_name(err));
        return;
    }

    if (strncmp(cmd, "TRAIN_STOP ", 11) == 0) {
        const char *arg = cmd + 11;
        while (*arg == ' ') {
            arg++;
        }
        const web_serial_monitor_peer_t *peer = find_peer_by_name_or_mac(arg);
        if (!peer) {
            send_ack("TRAIN_STOP", false, "peer not found");
            return;
        }
        float wander_th = 0.0f;
        float jitter_th = 0.0f;
        esp_err_t err = esp_wifi_sensing_fsm_train_stop(s_ctx.fsm, peer->mac, &wander_th, &jitter_th);
        if (err == ESP_OK) {
            char detail[96] = {0};
            snprintf(detail, sizeof(detail), "%s wander=%.4f jitter=%.4f", peer->name, wander_th, jitter_th);
            send_ack("TRAIN_STOP", true, detail);
        } else {
            send_ack("TRAIN_STOP", false, esp_err_to_name(err));
        }
        return;
    }

    if (strncmp(cmd, "TRAIN_REMOVE ", 13) == 0) {
        const char *arg = cmd + 13;
        while (*arg == ' ') {
            arg++;
        }
        const web_serial_monitor_peer_t *peer = find_peer_by_name_or_mac(arg);
        if (!peer) {
            send_ack("TRAIN_REMOVE", false, "peer not found");
            return;
        }
        esp_err_t err = esp_wifi_sensing_fsm_train_remove(s_ctx.fsm, peer->mac);
        send_ack("TRAIN_REMOVE", err == ESP_OK, esp_err_to_name(err));
        return;
    }

    send_error("unknown command");
}

static void poll_rx_and_handle_commands(void)
{
    static char stdin_line_buf[WEB_SERIAL_LINE_BUF_SIZE] = {0};
    static size_t stdin_line_len = 0;
#if CONFIG_SOC_USB_SERIAL_JTAG_SUPPORTED
    static char usb_line_buf[WEB_SERIAL_LINE_BUF_SIZE] = {0};
    static size_t usb_line_len = 0;
#endif
    uint8_t rx_buf[WEB_SERIAL_RX_POLL_BUF_SIZE] = {0};

    /* Accept commands from both the standard console and USB Serial/JTAG when available. */
    ssize_t read_len = read(fileno(stdin), rx_buf, sizeof(rx_buf));
    if (read_len < 0) {
        if (errno != EAGAIN && errno != EWOULDBLOCK) {
            ESP_LOGD(TAG, "stdin read failed: errno=%d", errno);
        }
    } else if (read_len > 0) {
        process_rx_bytes(stdin_line_buf, &stdin_line_len, rx_buf, (size_t)read_len);
    }

#if CONFIG_SOC_USB_SERIAL_JTAG_SUPPORTED
    int usb_read_len = usb_serial_jtag_read_bytes(rx_buf, sizeof(rx_buf), 0);
    if (usb_read_len > 0) {
        process_rx_bytes(usb_line_buf, &usb_line_len, rx_buf, (size_t)usb_read_len);
    }
#endif
}

static esp_err_t configure_command_inputs(void)
{
    esp_err_t err = configure_stdin_nonblocking();
    if (err != ESP_OK) {
        return err;
    }

#if CONFIG_SOC_USB_SERIAL_JTAG_SUPPORTED
    err = configure_usb_serial_jtag_input();
    if (err != ESP_OK) {
        return err;
    }
#endif

    return ESP_OK;
}

static void cleanup_command_inputs(void)
{
#if CONFIG_SOC_USB_SERIAL_JTAG_SUPPORTED
    if (s_ctx.usb_driver_owned) {
        (void)usb_serial_jtag_driver_uninstall();
        s_ctx.usb_driver_owned = false;
    }
#endif
}

static const char *input_mode_name(void)
{
#if CONFIG_SOC_USB_SERIAL_JTAG_SUPPORTED
    return "stdio + usb_serial_jtag";
#else
    return "stdio";
#endif
}

static void web_serial_monitor_task(void *arg)
{
    (void)arg;
    int64_t last_stream_us = 0;

    /* Emit an initial snapshot so the browser can render immediately after connecting. */
    send_hello();
    send_runtime_config();
    send_wifi_info();
    send_all_configs();

    while (true) {
        poll_rx_and_handle_commands();

        int64_t now_us = esp_timer_get_time();
        if (s_ctx.stream_enabled && s_ctx.sensing_ready &&
                (last_stream_us == 0 || (now_us - last_stream_us) >= ((int64_t)s_ctx.stream_period_ms * 1000LL))) {
            last_stream_us = now_us;
            for (size_t i = 0; i < s_ctx.peer_num; i++) {
                send_channel_sample(&s_ctx.peers[i]);
            }
        }

        vTaskDelay(pdMS_TO_TICKS(10));
    }
}

esp_err_t web_serial_monitor_init(void)
{
    if (s_ctx.initialized) {
        return ESP_ERR_INVALID_STATE;
    }

    memset(&s_ctx, 0, sizeof(s_ctx));
    s_ctx.initialized = true;
    s_ctx.sensing_ready = false;
    s_ctx.stream_enabled = false;
    s_ctx.csi_stream_enabled = false;
    s_ctx.csi_stream_period_ms = WEB_SERIAL_CSI_DEFAULT_PERIOD_MS;
    s_ctx.stream_period_ms = WEB_SERIAL_DEFAULT_PERIOD_MS;

    s_tx_line = malloc(WEB_SERIAL_TX_BUF_SIZE);
    if (!s_tx_line) {
        memset(&s_ctx, 0, sizeof(s_ctx));
        return ESP_ERR_NO_MEM;
    }
    s_tx_lock = xSemaphoreCreateMutex();
    if (!s_tx_lock) {
        free(s_tx_line);
        s_tx_line = NULL;
        memset(&s_ctx, 0, sizeof(s_ctx));
        return ESP_ERR_NO_MEM;
    }

    esp_err_t err = configure_command_inputs();
    if (err != ESP_OK) {
        vSemaphoreDelete(s_tx_lock);
        s_tx_lock = NULL;
        free(s_tx_line);
        s_tx_line = NULL;
        memset(&s_ctx, 0, sizeof(s_ctx));
        return err;
    }

    BaseType_t ok = xTaskCreate(web_serial_monitor_task,
                                "web_serial_monitor",
                                WEB_SERIAL_TASK_STACK_SIZE,
                                NULL,
                                WEB_SERIAL_TASK_PRIORITY,
                                &s_ctx.task);
    if (ok != pdPASS) {
        cleanup_command_inputs();
        vSemaphoreDelete(s_tx_lock);
        s_tx_lock = NULL;
        free(s_tx_line);
        s_tx_line = NULL;
        memset(&s_ctx, 0, sizeof(s_ctx));
        return ESP_FAIL;
    }

    ESP_LOGI(TAG, "web serial monitor transport started, input=%s, output=stdio",
             input_mode_name());
    return ESP_OK;
}

esp_err_t web_serial_monitor_attach_sensing(const web_serial_monitor_config_t *config)
{
    if (!config || !config->fsm || !config->peers || config->peer_num == 0 ||
            config->peer_num > WEB_SERIAL_MONITOR_MAX_PEERS) {
        return ESP_ERR_INVALID_ARG;
    }
    if (!s_ctx.initialized) {
        return ESP_ERR_INVALID_STATE;
    }
    if (s_ctx.sensing_ready) {
        return ESP_ERR_INVALID_STATE;
    }

    s_ctx.fsm = config->fsm;
    s_ctx.peer_num = config->peer_num;
    s_ctx.stream_period_ms = (config->stream_period_ms > 0) ? config->stream_period_ms : WEB_SERIAL_DEFAULT_PERIOD_MS;
    memcpy(s_ctx.peers, config->peers, config->peer_num * sizeof(web_serial_monitor_peer_t));
    s_ctx.sensing_ready = true;
    s_ctx.stream_enabled = true;

    ESP_LOGI(TAG, "sensing attached, peers=%u, period=%" PRIu32 "ms",
             (unsigned)s_ctx.peer_num, s_ctx.stream_period_ms);

    /* Republish the full snapshot so the browser reflects the new AP without a reconnect. */
    send_hello();
    send_runtime_config();
    send_wifi_info();
    send_all_configs();
    return ESP_OK;
}
