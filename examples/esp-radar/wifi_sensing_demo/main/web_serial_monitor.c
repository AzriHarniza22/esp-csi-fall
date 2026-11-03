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
#include "freertos/queue.h"

#if CONFIG_SOC_USB_SERIAL_JTAG_SUPPORTED
#include "driver/usb_serial_jtag.h"
#endif
#include "esp_check.h"
#include "esp_log.h"
#include "esp_mac.h"
#include "esp_netif.h"
#include "esp_system.h"
#include "esp_random.h"
#include "esp_timer.h"
#include "esp_wifi.h"
#include "mbedtls/base64.h"
#include "sdkconfig.h"

#include "ht_stimulus.h"
#include "tcp_stimulus.h"
#include "dns_stimulus.h"
#include "web_serial_monitor.h"
#include "activity_classifier.h"
#include "wifi_runtime_manager.h"
#include "csi_phy_probe.h"

#define WEB_SERIAL_PREFIX            "HMS:"
#define WEB_SERIAL_COMMAND_PREFIX    "HMSCMD "
#define WEB_SERIAL_TASK_STACK_SIZE   6144
#define WEB_SERIAL_TASK_PRIORITY     4
#define WEB_SERIAL_LINE_BUF_SIZE     512
/*
 * A full sample line with three MAC strings and the FSM's float fields reaches
 * roughly 900 bytes, so 1 KiB left no margin and truncation produced invalid JSON.
 * CSI lines carry two base64 payloads (raw + valid). The ESP-IDF Wi-Fi CSI guide
 * (v5.5.3, api-guides/wifi.rst) documents up to 612 raw bytes for
 * HT/40 MHz/STBC frames, so both payloads plus the per-frame metadata must fit:
 * 2 * 816 base64 chars + metadata leaves room in 4 KiB.
 */
#define WEB_SERIAL_TX_BUF_SIZE       4096
#define WEB_SERIAL_RX_POLL_BUF_SIZE  64
#define WEB_SERIAL_DEFAULT_PERIOD_MS 50
#define WEB_SERIAL_CSI_DEFAULT_PERIOD_MS 100
#define WEB_SERIAL_CSI_MAX_RAW_LEN 612
#define WEB_SERIAL_CSI_MAX_ENCODED_LEN (((WEB_SERIAL_CSI_MAX_RAW_LEN + 2) / 3) * 4 + 1)

/*
 * Period 0 is a demo-serial extension: emit every CSI callback. It is not an
 * esp_wifi / esp-radar API. Live charts still use 20..1000 ms.
 */
#define WEB_SERIAL_CSI_MIN_PERIOD_MS 20
#define WEB_SERIAL_CSI_MAX_PERIOD_MS 1000

/* How often the stimulus state is pushed so the panel shows a live CSI frame
 * rate and a live "last frame" age without the user having to refresh. */
#define STIMULUS_STATUS_PERIOD_MS 1000

/* When the AP rate-control drops our link to legacy CCK rates no OFDM frames
 * arrive and the driver never produces CSI, leaving the radar graph flat. The
 * watchdog forces a reconnect (which nudges the AP back to OFDM) whenever the
 * link is up but no CSI has been seen for a while. */
#define CSI_WD_CHECK_PERIOD_MS 1000
/* Six seconds was short enough that a quiet AP looked like a dead link. The
 * stimulus normally produces ~85 Hz, so a genuinely stalled link stays silent
 * far longer than this before it is worth a reconnect. */
#define CSI_WD_STALE_MS 20000U
#define CSI_WD_MIN_INTERVAL_MS 30000U
#define CSI_WD_TASK_STACK 4096U

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
    int64_t csi_last_rx_us;
    /*
     * CSI frame rate, derived from csi_frame_count in the monitor task. The
     * counter is only incremented inside the Wi-Fi callback, never read there,
     * so the callback stays a single increment. csi_rate_hz_x10 carries tenths
     * of a hertz to keep the JSON free of floating point.
     */
    uint32_t csi_frame_count;
    uint32_t csi_rate_hz_x10;
    /*
     * CSI callbacks whose source MAC matches the tracked AP peer (§6C). The
     * raw csi_frame_count covers every filtered frame; this isolates the AP
     * channel so a stimulus that only moves other peers stays visible.
     */
    uint32_t csi_ap_frame_count;
    int64_t csi_rate_last_us;
    int64_t csi_wd_last_reconnect_us;
    bool csi_wd_enabled;
    bool csi_wd_reconnecting;
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
static void send_stimulus_state(void);
static void handle_set_stimulus(char *args);

/*
 * Traffic stimulus selection for the HTTP-vs-Ping comparison experiment. Only
 * one source may run at a time (§5, §16 mutual exclusion), so a mode switch
 * always stops the other before starting the requested one. The mode is stored
 * even when sensing is not ready yet: the recorder selects it over the serial
 * channel, and it is applied the moment the link is up.
 */
typedef enum {
    STIM_MODE_OFF = 0,   /**< No deliberate stimulus; natural AP traffic only. */
    STIM_MODE_HTTP,      /**< HTTP Cloudflare bursts (ht_stimulus), FSM ping off. */
    STIM_MODE_PING,      /**< FSM router ping at ping_hz, HTTP task off. */
    STIM_MODE_TCP,       /**< TCP connect->close to the gateway (tcp_stimulus), HTTP+ping off. */
    STIM_MODE_DNS,       /**< UDP DNS queries to the DHCP-configured resolver (dns_stimulus), others off. */
} stim_mode_t;

static struct {
    stim_mode_t mode;
    uint32_t ping_hz;
    int64_t switched_at_us;
} s_stimulus = {
    .mode = STIM_MODE_OFF,
    .ping_hz = CONFIG_ESP_WIFI_SENSING_PING_FREQUENCY_HZ,
    .switched_at_us = 0,
};

static const char *stim_mode_name(stim_mode_t mode);
static void apply_stimulus_mode(const char *reason);
static void handle_set_stimulus_mode(char *args);

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
/* CSI base64 lives here, not on the radar callback stack (that stack already
 * overflowed when a 2 KiB line buffer was local). */
static char s_csi_b64_raw[WEB_SERIAL_CSI_MAX_ENCODED_LEN];
static char s_csi_b64_valid[WEB_SERIAL_CSI_MAX_ENCODED_LEN];

/* ------------------------------------------------------------------ *
 * Ping/CSI diagnostic instrumentation (Prioritas 1, §17/§18).
 *
 * One MPSC FreeRTOS queue carries ping success/timeout events and CSI
 * diagnostic (throttle-dropped) events to a dedicated drain task, which is the
 * sole consumer. Frames stay on the existing direct-write path (2). The STOP
 * barrier must quiesce BOTH paths before emitting the final ACK.
 *
 * Concurrency model (ESP-IDF 5.5.3, single-core ESP32, producers in task
 * context — evidenced by the 50 ms s_tx_lock timeout already used from the CSI
 * callback, so these are NOT ISRs):
 *   - s_epoch_mux (portMUX spinlock) guards admission + drain flags ONLY.
 *   - No queue API is ever called while holding s_epoch_mux (uxQueueMessages-
 *     Waiting/xQueueReceive take their own xQueueLock — queue.c:2312).
 *   - s_epoch_mux is always released before s_tx_lock is taken (no inversion).
 * ------------------------------------------------------------------ */

/* Diagnostic event types on the shared queue. */
#define DIAG_EVT_PING 1
#define DIAG_EVT_CSI  2

/* csi_diag drop_reason enum (§18.3 extended by the post-implementation review).
 * 0 = throttle-dropped callback (the original csi_diag purpose). 1..4 mark a
 * minimal metadata fallback for a direct-write frame failure, so the callback
 * is represented on the diagnostic timeline instead of vanishing. The drain
 * path (§ below) deliberately keeps emitting these fallbacks: they are ≤160 B
 * versus the ±1.44 kB frame they replace, the send is non-blocking, and a
 * full queue shows up in diag_queue_overflow — congestion can never cascade. */
#define DIAG_CSI_DROP_THROTTLE 0
#define DIAG_CSI_DROP_TX_LOCK_TIMEOUT 1
#define DIAG_CSI_DROP_OVERSIZED 2
#define DIAG_CSI_DROP_BASE64_FAIL 3
#define DIAG_CSI_DROP_UART_WRITE_FAIL 4

/* Queue capacity and drain-task sizing (§17.5/§18.7). Measured on the xtensa
 * ESP32 ABI: sizeof(diag_item_t)=56 B, so N=256 storage = 14336 B (~14 KB) plus
 * the StaticQueue_t overhead. */
#define DIAG_QUEUE_LEN 256
#define DIAG_DRAIN_TASK_STACK 4096
#define DIAG_DRAIN_TASK_PRIORITY 5
/* Barrier wait budget (§18.10 [estimate] ±500 ms, bounded by the ±2000 ms
 * browser finalization timeout). */
#define DIAG_BARRIER_TIMEOUT_MS 500

typedef struct {
    uint8_t type;
    uint32_t epoch;
    uint32_t diag_seq;
    int64_t ts_us;
    union {
        struct {
            uint32_t timegap_ms;
            uint32_t ip4;
            uint32_t transmitted;
            uint32_t received;
            uint16_t seqno;
            uint16_t recv_size;
            uint8_t ttl;
            uint8_t success;
        } ping;
        struct {
            uint8_t mac[6];
            uint8_t dmac[6];
            uint32_t cb;
            uint32_t seq_id;      /* firmware frame seq_id of the failed direct write */
            uint16_t rx_seq;
            uint16_t payload_len;
            int8_t rssi;
            uint8_t sig_mode;
            uint8_t mcs;
            uint8_t bandwidth;
            uint8_t stbc;
            uint8_t drop_reason;  /* DIAG_CSI_DROP_* (0 = throttle, §18.3) */
        } csi;
    } u;
} diag_item_t;

/* Admission / barrier shared state, guarded by s_epoch_mux. */
static portMUX_TYPE s_epoch_mux = portMUX_INITIALIZER_UNLOCKED;
static volatile bool s_closing = false;
static volatile uint32_t s_take_epoch = 0;
static volatile uint32_t s_inflight = 0;
static volatile uint32_t s_drain_inflight = 0;
static volatile bool s_drain_saw_empty = false;
static volatile bool s_flush_requested = false;
static volatile uint32_t s_flush_generation = 0;
static volatile uint32_t s_drain_acked_generation = 0;
/* Lifecycle gate (post-implementation review §1): a take must be opened by
 * TAKE_BEGIN and closed by TAKE_END before the next TAKE_BEGIN; the flag is
 * cleared by a completed TAKE_END (even an unconfirmed one — admission is
 * already closed there, so no producer can add new items). */
static volatile bool s_diag_take_open = false;

/* diag_seq + high-water marks (§18.13). Reset per boot, not per epoch. */
static uint32_t s_diag_seq_assigned = 0;
static volatile uint32_t s_diag_seq_assigned_max = 0;
static volatile uint32_t s_diag_seq_enqueued_max = 0;
static volatile uint32_t s_diag_seq_emitted_max = 0;
static uint32_t s_boot_id = 0;

/* Transport/producer counters (§18.12), reported in the STOP ACK. */
static volatile uint32_t s_diag_queue_overflow_count = 0;
static volatile uint32_t s_serial_tx_lock_timeout_count = 0;
static volatile uint32_t s_serial_short_write_count = 0;
static volatile uint32_t s_csi_throttle_drop_count = 0;
static volatile uint32_t s_frame_tx_drop_count = 0;
static volatile uint32_t s_csi_callback_count = 0;
static volatile uint32_t s_csi_event_persisted_count = 0;
static volatile uint32_t s_ping_event_persisted_count = 0;
/* Final-audit §1 staged accounting: an enqueued item whose serial write failed
 * (write_line returns 0: oversized / tx-lock timeout / short write). Counts
 * TX failure ONLY — enqueue failures are in diag_queue_overflow and host-side
 * receipt gaps are counted there, so no event is counted at two stages. */
static volatile uint32_t s_diag_emit_failed_count = 0;

/* Why diagnostics degraded at init (final-audit §2); NULL when enabled. */
static const char *s_diag_disable_reason = NULL;

static QueueHandle_t s_diag_queue = NULL;
static SemaphoreHandle_t s_drain_idle_sem = NULL;
static TaskHandle_t s_drain_task = NULL;
static int64_t s_take_start_ts_us = 0;

/*
 * write_line_locked() is the core: build + fwrite + fflush, assuming the
 * caller already holds s_tx_lock. Exposed so the STOP barrier can emit its ACK
 * without re-entering write_line() (which would recursively take the
 * non-recursive s_tx_lock and deadlock — §18.11 finding).
 */
static int write_line_locked(const char *fmt, ...);
static int write_line_core(const char *fmt, va_list args);
static int emit_diag_item(const diag_item_t *it);
static void drain_task(void *arg);
static bool diag_admit_and_enqueue(diag_item_t *it);
static void emit_csi_diag(const wifi_csi_filtered_info_t *info, uint32_t cb, int64_t ts_us);
static void emit_csi_frame_fallback(const wifi_csi_filtered_info_t *info, uint32_t cb,
                                    int64_t ts_us, uint8_t drop_reason);
static void fill_csi_diag_item(diag_item_t *it, const wifi_csi_filtered_info_t *info,
                               uint32_t cb, int64_t ts_us, uint8_t drop_reason);

/*
 * Formats one message into the shared s_tx_line buffer and writes it. The
 * caller MUST already hold s_tx_lock. Returns the number of bytes written
 * (0 on oversize drop or short write, both counted).
 */
static int write_line_core(const char *fmt, va_list args)
{
    char *line = s_tx_line;
    line[0] = '\0';

    /* Prefix structured messages so ordinary ESP logs can coexist on the same port. */
    int prefix_len = snprintf(line, WEB_SERIAL_TX_BUF_SIZE, "%s", WEB_SERIAL_PREFIX);
    if (prefix_len <= 0 || prefix_len >= WEB_SERIAL_TX_BUF_SIZE) {
        return 0;
    }

    int body_len = vsnprintf(line + prefix_len, WEB_SERIAL_TX_BUF_SIZE - prefix_len, fmt, args);
    if (body_len < 0) {
        return 0;
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
        return 0;
    }

    size_t written = fwrite(line, 1, (size_t)total_len, stdout);
    int flush_result = fflush(stdout);
    if ((int)written < total_len) {
        /* §18.12 B2: fwrite accepted fewer bytes than the line (host stall). */
        s_serial_short_write_count++;
        return (int)written;
    }
    /* Final-audit §3: a complete fwrite only fills the stdio buffer. If fflush
     * reports EOF the line did NOT reach the wire, so it is reported as a
     * failed write (0) rather than a success the caller would confirm on. */
    if (flush_result != 0) {
        s_serial_short_write_count++;
        return 0;
    }
    return (int)written;
}

static int write_line(const char *fmt, ...)
{
    if (!s_tx_line || !s_tx_lock) {
        return 0;
    }

    if (xSemaphoreTake(s_tx_lock, pdMS_TO_TICKS(50)) != pdTRUE) {
        /* §18.12 B0: previously silent; now counted so transport loss is measurable. */
        s_serial_tx_lock_timeout_count++;
        return 0;
    }

    va_list args;
    va_start(args, fmt);
    int result = write_line_core(fmt, args);
    va_end(args);

    xSemaphoreGive(s_tx_lock);
    return result;
}

static int write_line_locked(const char *fmt, ...)
{
    if (!s_tx_line) {
        return 0;
    }
    va_list args;
    va_start(args, fmt);
    int result = write_line_core(fmt, args);
    va_end(args);
    return result;
}

static bool json_escape_string(const char *source, char *destination, size_t capacity)
{
    static const char hex[] = "0123456789abcdef";
    size_t output = 0;

    if (!source || !destination || capacity == 0) {
        return false;
    }

    while (*source) {
        const unsigned char value = (unsigned char)*source++;
        if (value == '"' || value == '\\') {
            if (output + 2 >= capacity) {
                return false;
            }
            destination[output++] = '\\';
            destination[output++] = (char)value;
        } else if (value < 0x20) {
            if (output + 6 >= capacity) {
                return false;
            }
            destination[output++] = '\\';
            destination[output++] = 'u';
            destination[output++] = '0';
            destination[output++] = '0';
            destination[output++] = hex[value >> 4];
            destination[output++] = hex[value & 0x0f];
        } else {
            if (output + 1 >= capacity) {
                return false;
            }
            destination[output++] = (char)value;
        }
    }

    destination[output] = '\0';
    return true;
}

void web_serial_monitor_publish_activity(const char *label, float score,
                                         const char *runner_up_label,
                                         float runner_up_score)
{
    char escaped_label[96];
    char escaped_runner_up[96];

    if (!isfinite(score) || !isfinite(runner_up_score) ||
            !json_escape_string(label, escaped_label, sizeof(escaped_label)) ||
            !json_escape_string(runner_up_label, escaped_runner_up, sizeof(escaped_runner_up))) {
        ESP_LOGW(TAG, "Skipping activity result with invalid label or score");
        return;
    }

    (void)write_line(
        "{\"type\":\"activity\",\"class\":\"%s\",\"score\":%.3f,"
        "\"runner_up\":\"%s\",\"runner_up_score\":%.3f,"
        "\"confidence_available\":false}\n",
        escaped_label, (double)score, escaped_runner_up, (double)runner_up_score);
}

void web_serial_monitor_csi_callback(void *ctx, const wifi_csi_filtered_info_t *info)
{
    /*
     * Sample the monotonic clock before any other work so cb_ts_us is as close
     * to the callback entry as possible; it must not drift with payload size.
     */
    const int64_t cb_ts_us = esp_timer_get_time();

    (void)ctx;
    if (!info || !s_ctx.initialized || !s_ctx.sensing_ready ||
            !info->raw_data || info->raw_len == 0) {
        return;
    }

    s_ctx.csi_last_rx_us = cb_ts_us;
    s_ctx.csi_frame_count++;
    s_csi_callback_count++;
    if (s_ctx.peer_num > 0 && memcmp(info->mac, s_ctx.peers[0].mac, 6) == 0) {
        s_ctx.csi_ap_frame_count++;
    }

    /* CSI-callback PHY probe: bounded accounting of frames that REACHED the CSI
     * path (post esp-radar peer selection). No-op unless enabled; cheap when on.
     * This is NOT a promiscuous sniffer and cannot see AP frames rejected before
     * the CSI callback — promiscuous-path data comes from esp-radar's own
     * "csi_preproc" accounting. Report is emitted from the monitor task. */
    csi_phy_probe_record(info, cb_ts_us, s_ctx.peer_num > 0 ? s_ctx.peers[0].mac : NULL);

    activity_classifier_enqueue(info);

    if (!s_ctx.csi_stream_enabled) {
        return;
    }

    int64_t now_us = cb_ts_us;
    if (s_ctx.csi_stream_period_ms > 0 &&
            s_ctx.csi_last_emit_us > 0 &&
            now_us - s_ctx.csi_last_emit_us < (int64_t)s_ctx.csi_stream_period_ms * 1000LL) {
        /*
         * §17.4/§18.3: a throttle-dropped callback is represented on the
         * diagnostic timeline as a minimal csi_diag event (no raw payload). It
         * is disjoint from frames.csv (§18.4). Existing csi_dropped_count stays
         * incremented so the frames.csv `dropped` column is unchanged; the split
         * counter feeds the §18.14 identity.
         */
        s_ctx.csi_dropped_count++;
        s_csi_throttle_drop_count++;
        emit_csi_diag(info, s_csi_callback_count, cb_ts_us);
        return;
    }
    if (info->raw_len > WEB_SERIAL_CSI_MAX_RAW_LEN) {
        s_ctx.csi_dropped_count++;
        s_frame_tx_drop_count++;
        emit_csi_frame_fallback(info, s_csi_callback_count, cb_ts_us, DIAG_CSI_DROP_OVERSIZED);
        return;
    }
    uint8_t frame_fail = 0;
    if (!s_tx_line || !s_tx_lock ||
            xSemaphoreTake(s_tx_lock, pdMS_TO_TICKS(50)) != pdTRUE) {
        s_ctx.csi_dropped_count++;
        s_frame_tx_drop_count++;
        frame_fail = DIAG_CSI_DROP_TX_LOCK_TIMEOUT;
    }

    size_t encoded_raw_len = 0;
    if (frame_fail == 0 &&
            mbedtls_base64_encode((unsigned char *)s_csi_b64_raw, sizeof(s_csi_b64_raw) - 1,
                                  &encoded_raw_len, (const unsigned char *)info->raw_data,
                                  info->raw_len) != 0) {
        s_ctx.csi_dropped_count++;
        s_frame_tx_drop_count++;
        frame_fail = DIAG_CSI_DROP_BASE64_FAIL;
    }
    if (frame_fail == 0) {
        s_csi_b64_raw[encoded_raw_len] = '\0';
    }

    uint8_t uart_short = 0;
    if (frame_fail == 0) {
        uint16_t valid_len = info->valid_len;
        s_csi_b64_valid[0] = '\0';
        if (valid_len > 0 && valid_len <= WEB_SERIAL_CSI_MAX_RAW_LEN) {
            size_t encoded_valid_len = 0;
            if (mbedtls_base64_encode((unsigned char *)s_csi_b64_valid, sizeof(s_csi_b64_valid) - 1,
                                      &encoded_valid_len, (const unsigned char *)info->valid_data,
                                      valid_len) != 0) {
                s_csi_b64_valid[0] = '\0';
                valid_len = 0;
            } else {
                s_csi_b64_valid[encoded_valid_len] = '\0';
            }
        } else {
            valid_len = 0;
        }

        const esp_radar_rx_ctrl_info_t *rx = &info->rx_ctrl_info;
        /*
         * esp_radar keeps the driver's wifi_csi_info_t alive for the duration of
         * the callback (esp_radar.c assigns filtered_info->info = info), so
         * first_word_invalid and the 802.11 rx_seq can be forwarded verbatim.
         */
        const wifi_csi_info_t *drv = info->info;
        /* §18.10: a forwarded frame carries the active device epoch (0 when outside
         * a take or mid-closing) so the browser can gate/dedupe by epoch. Read under
         * s_epoch_mux, released before s_tx_lock (already held here) — no inversion,
         * and no queue API touched. Frames are path (2), so they carry eq/bid but no
         * diag_seq (§18.13 scope). */
        portENTER_CRITICAL(&s_epoch_mux);
        const uint32_t frame_eq = s_closing ? 0U : s_take_epoch;
        portEXIT_CRITICAL(&s_epoch_mux);
        int prefix_len = snprintf(s_tx_line, WEB_SERIAL_TX_BUF_SIZE, "%s", WEB_SERIAL_PREFIX);
        int body_len = 0;
        if (prefix_len > 0 && prefix_len < WEB_SERIAL_TX_BUF_SIZE) {
            body_len = snprintf(
                s_tx_line + prefix_len, WEB_SERIAL_TX_BUF_SIZE - prefix_len,
                "{\"type\":\"csi\",\"eq\":%" PRIu32 ",\"bid\":%" PRIu32 ",\"seq\":%" PRIu32 ",\"mac\":\"" MACSTR "\",\"rssi\":%d,"
                "\"raw_len\":%u,\"valid_len\":%u,\"data_type\":%d,\"dropped\":%" PRIu32 ","
                "\"ts_us\":%" PRId64 ",\"rate\":%u,\"sig_mode\":%d,\"mcs\":%u,\"bandwidth\":%u,"
                "\"stbc\":%u,\"noise_floor\":%d,\"channel\":%u,\"secondary_channel\":%u,"
                "\"local_timestamp\":%" PRIu32 ",\"agc_gain\":%u,\"fft_gain\":%d,"
                "\"dmac\":\"" MACSTR "\",\"first_word_invalid\":%s,\"rx_seq\":%u,"
                "\"lltf_len\":%u,\"ht_ltf_len\":%u,\"stbc_ht_ltf_len\":%u,"
                "\"rx_gain_compensation\":%.6f,"
                "\"data\":\"%s\",\"valid\":\"%s\"}\n",
                frame_eq, s_boot_id, info->seq_id, MAC2STR(info->mac), rx->rssi, info->raw_len, valid_len,
                (int)info->data_type, s_ctx.csi_dropped_count, now_us,
                (unsigned)rx->rate, (int)rx->signal_mode, (unsigned)rx->mcs, (unsigned)rx->cwb,
                (unsigned)rx->stbc, (int)rx->noise_floor, (unsigned)rx->channel,
                (unsigned)rx->secondary_channel, rx->timestamp, (unsigned)rx->agc_gain,
                (int)rx->fft_gain, MAC2STR(info->dmac),
                (drv && drv->first_word_invalid) ? "true" : "false",
                drv ? (unsigned)drv->rx_seq : 0U,
                (unsigned)info->valid_lltf_len, (unsigned)info->valid_ht_ltf_len,
                (unsigned)info->valid_stbc_ht_ltf_len,
                (double)info->rx_gain_compensation, s_csi_b64_raw, s_csi_b64_valid);
        }
        int total_len = prefix_len + body_len;
        if (prefix_len <= 0 || body_len < 0 || total_len >= WEB_SERIAL_TX_BUF_SIZE) {
            s_ctx.truncated_msg_count++;
            s_ctx.csi_dropped_count++;
            s_frame_tx_drop_count++;
            frame_fail = DIAG_CSI_DROP_OVERSIZED;
        } else {
            s_ctx.csi_last_emit_us = now_us;
            size_t written = fwrite(s_tx_line, 1, total_len, stdout);
            fflush(stdout);
            if (written < (size_t)total_len) {
                /* Non-driver UART mode: fwrite returns the requested count even when the
                 * HW FIFO drops bytes, but a genuine short write means the transport
                 * failed — mirror it as a fallback with the write-failure reason. */
                s_serial_short_write_count++;
                s_ctx.csi_dropped_count++;
                s_frame_tx_drop_count++;
                uart_short = 1;
            }
        }
        xSemaphoreGive(s_tx_lock);
    }

    /* Fallback enqueue runs strictly OUTSIDE s_tx_lock (no queue API under the
     * writer lock) and is non-blocking. A successfully-sent frame never reaches
     * this call, so frames.csv and csi_diag stay disjoint. */
    if (frame_fail != 0) {
        emit_csi_frame_fallback(info, s_csi_callback_count, cb_ts_us, frame_fail);
    } else if (uart_short) {
        emit_csi_frame_fallback(info, s_csi_callback_count, cb_ts_us, DIAG_CSI_DROP_UART_WRITE_FAIL);
    }
}

static void csi_watchdog_task(void *arg)
{
    (void)arg;
    esp_err_t err = wifi_runtime_manager_reconnect();
    ESP_LOGW(TAG, "csi watchdog: reconnect finished (err=%s)", esp_err_to_name(err));
    s_ctx.csi_wd_reconnecting = false;
    vTaskDelete(NULL);
}

static void csi_watchdog_check(void *arg)
{
    (void)arg;
    if (!s_ctx.initialized || !s_ctx.csi_wd_enabled || s_ctx.csi_wd_reconnecting) {
        return;
    }
    wifi_runtime_info_t info;
    wifi_runtime_manager_get_info(&info);
    if (!info.connected || !info.has_ip) {
        return;
    }
    int64_t now_us = esp_timer_get_time();
    if (now_us - s_ctx.csi_wd_last_reconnect_us < (int64_t)CSI_WD_MIN_INTERVAL_MS * 1000LL) {
        return;
    }
    /*
     * The watchdog is for the case where CSI stops mid-session, so it must only
     * fire after CSI has actually been seen. A freshly associated link has no
     * frames yet, and treating that as stale made the unit force a reconnect
     * within seconds of getting an IP, then loop on every quiet AP.
     */
    if (s_ctx.csi_last_rx_us <= 0) {
        return;
    }
    int64_t age_us = now_us - s_ctx.csi_last_rx_us;
    if (age_us < (int64_t)CSI_WD_STALE_MS * 1000LL) {
        return;
    }
    ESP_LOGW(TAG, "csi watchdog: no CSI for %lld ms, forcing reconnect",
             (long long)(age_us / 1000));
    s_ctx.csi_wd_last_reconnect_us = now_us;
    s_ctx.csi_wd_reconnecting = true;
    if (xTaskCreate(csi_watchdog_task, "csi_wd", CSI_WD_TASK_STACK, NULL,
                    tskIDLE_PRIORITY + 5, NULL) != pdPASS) {
        s_ctx.csi_wd_reconnecting = false;
    }
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

/* ------------------------------------------------------------------ *
 * Diagnostic engine implementation.
 * ------------------------------------------------------------------ */

/* Wrap-safe high-water update for a monotonic uint32 counter. */
static inline bool seq_newer(uint32_t candidate, uint32_t current)
{
    return (int32_t)(candidate - current) > 0;
}

static void fmt_mac12(const uint8_t *m, char *out)
{
    for (int i = 0; i < 6; i++) {
        snprintf(out + i * 2, 3, "%02x", m[i]);
    }
    out[12] = '\0';
}

/*
 * Producer admission (§18.11 part I). The epoch check, diag_seq assignment and
 * in-flight registration happen in ONE s_epoch_mux critical section, so there
 * is no window in which STOP closes admission between the check and the
 * registration. Rejected (closing / no active take) producers never consume a
 * diag_seq, so they create no phantom gap; admitted producers that then fail
 * xQueueSend DO consume a number (that is the overflow/gap signal, §18.13).
 * Callers run in task context (Wi-Fi RX task and LWIP ping task), never ISR.
 */
static bool diag_admit_and_enqueue(diag_item_t *it)
{
    /* Final-audit §2: with diagnostics disabled the plumbing does not exist, so
     * producers must be invisible to the accounting — no diag_seq consumed, no
     * in-flight registered, and NO overflow counted (an enqueue attempt against
     * a NULL queue would otherwise report every CSI frame as a phantom loss). */
    if (s_diag_queue == NULL) {
        return false;
    }
    uint32_t epoch = 0;
    uint32_t ds = 0;
    portENTER_CRITICAL(&s_epoch_mux);
    if (!s_closing && s_take_epoch != 0) {
        epoch = s_take_epoch;
        ds = ++s_diag_seq_assigned;
        if (seq_newer(ds, s_diag_seq_assigned_max)) {
            s_diag_seq_assigned_max = ds;
        }
        ++s_inflight;
    }
    portEXIT_CRITICAL(&s_epoch_mux);

    if (epoch == 0) {
        return false;
    }
    it->epoch = epoch;
    it->diag_seq = ds;

    /* Queue API is called OUTSIDE s_epoch_mux (never nest with xQueueLock). */
    bool sent = (s_diag_queue && xQueueSend(s_diag_queue, it, 0) == pdTRUE);

    portENTER_CRITICAL(&s_epoch_mux);
    if (sent && seq_newer(ds, s_diag_seq_enqueued_max)) {
        s_diag_seq_enqueued_max = ds;
    }
    --s_inflight;
    portEXIT_CRITICAL(&s_epoch_mux);

    if (!sent) {
        s_diag_queue_overflow_count++;
    }
    return sent;
}

/* Formats one diagnostic record and writes it via the locked-free writer. */
static int emit_diag_item(const diag_item_t *it)
{
    if (it->type == DIAG_EVT_PING) {
        return write_line(
            "{\"type\":\"diag\",\"et\":\"ping\",\"bid\":%" PRIu32 ",\"e\":%" PRIu32 ",\"ds\":%" PRIu32
            ",\"ts\":%" PRId64 ",\"st\":%s,\"sn\":%" PRIu32 ",\"sv\":true,\"tg\":%" PRIu32
            ",\"ttl\":%" PRIu32 ",\"sz\":%" PRIu32 ",\"tx\":%" PRIu32 ",\"rx\":%" PRIu32 "}\n",
            s_boot_id, it->epoch, it->diag_seq, (int64_t)it->ts_us,
            it->u.ping.success ? "true" : "false",
            (uint32_t)it->u.ping.seqno, it->u.ping.timegap_ms,
            (uint32_t)it->u.ping.ttl, (uint32_t)it->u.ping.recv_size,
            it->u.ping.transmitted, it->u.ping.received);
    }
    char mac[13];
    char dmac[13];
    fmt_mac12(it->u.csi.mac, mac);
    fmt_mac12(it->u.csi.dmac, dmac);
    return write_line(
        "{\"type\":\"diag\",\"et\":\"csi\",\"bid\":%" PRIu32 ",\"e\":%" PRIu32 ",\"ds\":%" PRIu32
        ",\"ts\":%" PRId64 ",\"cb\":%" PRIu32 ",\"mac\":\"%s\",\"dm\":\"%s\",\"rq\":%" PRIu32
        ",\"sm\":%" PRIu32 ",\"mc\":%" PRIu32 ",\"rs\":%d,\"bw\":%" PRIu32 ",\"sb\":%" PRIu32
        ",\"pl\":%" PRIu32 ",\"sid\":%" PRIu32 ",\"dr\":%" PRIu32 "}\n",
        s_boot_id, it->epoch, it->diag_seq, (int64_t)it->ts_us, it->u.csi.cb,
        mac, dmac, (uint32_t)it->u.csi.rx_seq, (uint32_t)it->u.csi.sig_mode,
        (uint32_t)it->u.csi.mcs, (int)it->u.csi.rssi, (uint32_t)it->u.csi.bandwidth,
        (uint32_t)it->u.csi.stbc, (uint32_t)it->u.csi.payload_len,
        it->u.csi.seq_id, (uint32_t)it->u.csi.drop_reason);
}

/*
 * Sole-consumer drain with reserve-before-dequeue + consumer acknowledgement
 * (§18.11, verified against FreeRTOS queue.c:2312 in round 5). Because drain is
 * the only consumer, an observed "count > 0" can only grow, so the following
 * non-blocking xQueueReceive(...,0) is guaranteed to succeed; only the flag
 * transitions need s_epoch_mux, and no queue API runs inside it.
 */
static void drain_task(void *arg)
{
    (void)arg;
    diag_item_t it;
    for (;;) {
        if (s_diag_queue && uxQueueMessagesWaiting(s_diag_queue) > 0) {
            portENTER_CRITICAL(&s_epoch_mux);
            s_drain_inflight = 1;
            s_drain_saw_empty = false;
            portEXIT_CRITICAL(&s_epoch_mux);

            if (xQueueReceive(s_diag_queue, &it, 0) == pdTRUE) {
                /* Final-audit §1 stage 2: a failed serial write is counted as a
                 * TX failure here and nowhere else (the host cannot see the
                 * item either; the transport-gap term subtracts this counter). */
                if (emit_diag_item(&it) == 0) {
                    s_diag_emit_failed_count++;
                }
                portENTER_CRITICAL(&s_epoch_mux);
                if (seq_newer(it.diag_seq, s_diag_seq_emitted_max)) {
                    s_diag_seq_emitted_max = it.diag_seq;
                }
                portEXIT_CRITICAL(&s_epoch_mux);
            }

            portENTER_CRITICAL(&s_epoch_mux);
            s_drain_inflight = 0;
            portEXIT_CRITICAL(&s_epoch_mux);
        } else {
            bool ack = false;
            portENTER_CRITICAL(&s_epoch_mux);
            s_drain_saw_empty = true;
            if (s_flush_requested) {
                s_drain_acked_generation = s_flush_generation;
                ack = true;
            }
            portEXIT_CRITICAL(&s_epoch_mux);
            if (ack) {
                xSemaphoreGive(s_drain_idle_sem);
            }
            /* Short timeout keeps the final empty-check prompt even if STOP's
             * notify races past it. */
            ulTaskNotifyTake(pdTRUE, pdMS_TO_TICKS(10));
        }
    }
}

/* Per-reply ping hook invoked from the LWIP ping task (vendored component). */
static void web_serial_monitor_ping_event_cb(const esp_wifi_sensing_ping_event_t *ev, void *user_data)
{
    (void)user_data;
    if (!ev || !s_diag_queue) {
        return;
    }
    diag_item_t it = {0};
    it.type = DIAG_EVT_PING;
    it.ts_us = ev->ts_us;
    it.u.ping.success = ev->success ? 1 : 0;
    it.u.ping.seqno = ev->seqno;
    it.u.ping.timegap_ms = ev->timegap_ms;
    it.u.ping.ip4 = ev->ip4_addr;
    it.u.ping.ttl = ev->ttl;
    it.u.ping.recv_size = ev->recv_size;
    it.u.ping.transmitted = ev->transmitted;
    it.u.ping.received = ev->received;
    if (diag_admit_and_enqueue(&it)) {
        s_ping_event_persisted_count++;
    }
}

/* Shared minimal-metadata builder for csi_diag records (no raw payload). */
static void fill_csi_diag_item(diag_item_t *it, const wifi_csi_filtered_info_t *info,
                               uint32_t cb, int64_t ts_us, uint8_t drop_reason)
{
    const esp_radar_rx_ctrl_info_t *rx = &info->rx_ctrl_info;
    const wifi_csi_info_t *drv = info->info;
    it->type = DIAG_EVT_CSI;
    it->ts_us = ts_us;
    memcpy(it->u.csi.mac, info->mac, 6);
    memcpy(it->u.csi.dmac, info->dmac, 6);
    it->u.csi.cb = cb;
    it->u.csi.seq_id = info->seq_id;
    it->u.csi.rx_seq = drv ? (uint16_t)drv->rx_seq : 0U;
    it->u.csi.payload_len = drv ? (uint16_t)drv->payload_len : 0U;
    it->u.csi.rssi = (int8_t)rx->rssi;
    it->u.csi.sig_mode = (uint8_t)rx->signal_mode;
    it->u.csi.mcs = (uint8_t)rx->mcs;
    it->u.csi.bandwidth = (uint8_t)rx->cwb;
    it->u.csi.stbc = (uint8_t)rx->stbc;
    it->u.csi.drop_reason = drop_reason;
}

/* Builds and admits a minimal csi_diag record for a throttle-dropped callback. */
static void emit_csi_diag(const wifi_csi_filtered_info_t *info, uint32_t cb, int64_t ts_us)
{
    if (!s_diag_queue) {
        return;
    }
    diag_item_t it = {0};
    fill_csi_diag_item(&it, info, cb, ts_us, DIAG_CSI_DROP_THROTTLE);
    if (diag_admit_and_enqueue(&it)) {
        s_csi_event_persisted_count++;
    }
}

/*
 * Post-implementation review §2: a direct-write frame failure is mirrored as a
 * minimal csi_diag metadata record (drop_reason 1..4, NEVER any raw payload).
 * Non-blocking (xQueueSend timeout 0, outside every lock — callers release
 * s_tx_lock first); during UART congestion the fallback costs ≤160 B against
 * the ±1.44 kB frame it replaces, and a full queue only bumps
 * diag_queue_overflow, so this can never cascade an overload. Disjointness
 * holds: successfully-sent frames exist only in frames.csv; throttle drops and
 * direct-write failures share meta.events.csi_diag, distinguished by drop_reason.
 * All original counters (csi_dropped_count, frame_tx_drop) are unchanged.
 */
static void emit_csi_frame_fallback(const wifi_csi_filtered_info_t *info, uint32_t cb,
                                    int64_t ts_us, uint8_t drop_reason)
{
    if (!s_diag_queue) {
        return;
    }
    diag_item_t it = {0};
    fill_csi_diag_item(&it, info, cb, ts_us, drop_reason);
    if (diag_admit_and_enqueue(&it)) {
        s_csi_event_persisted_count++;
    }
}

/* ACK emitted while s_tx_lock is already held (STOP barrier), never re-takes it.
 * Returns bytes written (0 on oversize/short write) so the barrier can tell
 * whether the ACK itself reached the wire (final-audit §3). */
static int send_ack_locked(const char *json_body)
{
    return write_line_locked("%s\n", json_body);
}

/*
 * TAKE_BEGIN lifecycle gate (post-implementation review §1). A new take may
 * only open once the PREVIOUS session is truly quiescent. The old design ran
 * xQueueReset() unconditionally, which silently destroyed pending events when
 * the previous STOP had timed out (boundary_unconfirmed) or the drain was
 * still mid-item. New contract:
 *   - TAKE_BEGIN while the previous take is still open (no TAKE_END) → reject.
 *   - queue pending / producer inflight / drain inflight → bounded recovery
 *     (the drain task keeps emitting old-epoch items; the host epoch-gates
 *     them, and they are never counted into the new take) until quiescent.
 *   - recovery times out → reject with a reason + live snapshot; state is NOT
 *     mutated, so the caller may retry TAKE_BEGIN later.
 *   - xQueueReset() runs ONLY after quiescence is proven, so it can never
 *     discard in-flight events (it is then a belt-and-braces no-op).
 * The old epoch is never silently altered: rejection keeps the previous
 * session's state frozen; acceptance opens a brand-new epoch explicitly.
 */
static void handle_take_begin(uint32_t epoch)
{
    if (epoch == 0) {
        send_ack("TAKE_BEGIN", false, "epoch must be > 0");
        return;
    }
    if (s_diag_take_open) {
        portENTER_CRITICAL(&s_epoch_mux);
        uint32_t open_epoch = s_take_epoch;
        portEXIT_CRITICAL(&s_epoch_mux);
        char detail[96];
        snprintf(detail, sizeof(detail), "take_open:epoch=%" PRIu32 ";send TAKE_END first", open_epoch);
        send_ack("TAKE_BEGIN", false, detail);
        return;
    }

    /* Recovery window: wait for the previous session's pipeline to go idle.
     * Bounded by the same budget as the STOP barrier so a browser waiting
     * ±2000 ms for the START ACK always gets an explicit answer. Admission is
     * closed outside a take (s_closing / s_take_epoch==0), so no producer can
     * add new items while we poll. */
    int64_t deadline_us = esp_timer_get_time() + (int64_t)DIAG_BARRIER_TIMEOUT_MS * 1000;
    for (;;) {
        uint32_t pending = s_diag_queue ? (uint32_t)uxQueueMessagesWaiting(s_diag_queue) : 0U;
        portENTER_CRITICAL(&s_epoch_mux);
        uint32_t inflight = s_inflight;
        uint32_t drain_inflight = s_drain_inflight;
        portEXIT_CRITICAL(&s_epoch_mux);
        if (pending == 0 && inflight == 0 && drain_inflight == 0) {
            break;
        }
        if (esp_timer_get_time() >= deadline_us) {
            char detail[160];
            snprintf(detail, sizeof(detail),
                     "prev_not_quiescent:queue_pending=%" PRIu32 ";inflight=%" PRIu32
                     ";drain_inflight=%" PRIu32, pending, inflight, drain_inflight);
            send_ack("TAKE_BEGIN", false, detail);
            return;
        }
        vTaskDelay(pdMS_TO_TICKS(2));
    }

    /* Only now is discarding residue safe — the queue is provably empty. */
    if (s_diag_queue) {
        xQueueReset(s_diag_queue);
    }
    uint32_t gen;
    portENTER_CRITICAL(&s_epoch_mux);
    s_closing = false;
    s_take_epoch = epoch;
    s_inflight = 0;
    s_drain_inflight = 0;
    s_drain_saw_empty = false;
    s_flush_requested = false;
    s_drain_acked_generation = 0;
    s_diag_take_open = true;
    ++s_flush_generation;
    gen = s_flush_generation;
    portEXIT_CRITICAL(&s_epoch_mux);

    /* Reset per-take producer/transport counters (§18.12); diag_seq high-waters
     * stay monotonic per boot (wrap-safe) for gap accounting. */
    s_diag_queue_overflow_count = 0;
    s_serial_tx_lock_timeout_count = 0;
    s_serial_short_write_count = 0;
    s_csi_throttle_drop_count = 0;
    s_frame_tx_drop_count = 0;
    s_csi_event_persisted_count = 0;
    s_ping_event_persisted_count = 0;
    s_diag_emit_failed_count = 0;

    /* Final-audit §2: a degraded build still records CSI normally; the START
     * ACK says so explicitly with the init-time reason so the browser can
     * persist "diagnostics unavailable" instead of inferring empty == zero. */
    const bool diag_on = (s_diag_queue != NULL) && (s_drain_task != NULL);
    s_take_start_ts_us = esp_timer_get_time();
    if (diag_on) {
        (void)write_line(
            "{\"type\":\"ack\",\"cmd\":\"TAKE_BEGIN\",\"ok\":true,\"epoch\":%" PRIu32
            ",\"gen\":%" PRIu32 ",\"boot_id\":%" PRIu32 ",\"start_ts_us\":%" PRId64
            ",\"diagnostics_enabled\":true}\n",
            epoch, gen, s_boot_id, (int64_t)s_take_start_ts_us);
    } else {
        (void)write_line(
            "{\"type\":\"ack\",\"cmd\":\"TAKE_BEGIN\",\"ok\":true,\"epoch\":%" PRIu32
            ",\"gen\":%" PRIu32 ",\"boot_id\":%" PRIu32 ",\"start_ts_us\":%" PRId64
            ",\"diagnostics_enabled\":false,\"reason\":\"%s\"}\n",
            epoch, gen, s_boot_id, (int64_t)s_take_start_ts_us,
            s_diag_disable_reason ? s_diag_disable_reason : "unknown");
    }
}

/*
 * STOP barrier (§18.11 part II): quiesce BOTH transmission paths, then emit the
 * final ACK under a single s_tx_lock hold. Reports boundary_ok / tx_drained
 * truthfully; never claims browser receipt (§18.13 C/D are host-side).
 */
static void handle_take_end(uint32_t epoch)
{
    if (!s_diag_take_open) {
        /* No take was ever opened (or a duplicate TAKE_END after a completed
         * one). A second barrier run would bump nothing but could emit a
         * confusing confirmed ACK, so answer explicitly instead. */
        send_ack("TAKE_END", false, "no_open_take");
        return;
    }
    /* step 1: close admission under the same mux the producers use. */
    uint32_t inflight_at_close = 0;
    portENTER_CRITICAL(&s_epoch_mux);
    s_closing = true;
    inflight_at_close = s_inflight;
    portEXIT_CRITICAL(&s_epoch_mux);

    bool inflight_zero = false;
    bool drain_ok = false;
    int64_t deadline_us = esp_timer_get_time() + (int64_t)DIAG_BARRIER_TIMEOUT_MS * 1000;

    /* step 2: wait for accepted producers to finish enqueuing. */
    while (esp_timer_get_time() < deadline_us) {
        portENTER_CRITICAL(&s_epoch_mux);
        uint32_t n = s_inflight;
        portEXIT_CRITICAL(&s_epoch_mux);
        if (n == 0) {
            inflight_zero = true;
            break;
        }
        vTaskDelay(pdMS_TO_TICKS(1));
    }

    /* step 3: ask the drain for a final empty-check and wait for its ack.
     * Degraded mode (diagnostic plumbing failed to allocate at init): there is
     * no queue and no consumer, so MPSC quiescence is trivially true and the
     * barrier only has to guard the direct-write path (steps 4-5). */
    const bool diag_enabled = (s_diag_queue != NULL) && (s_drain_task != NULL);
    uint32_t gen;
    portENTER_CRITICAL(&s_epoch_mux);
    s_flush_requested = true;
    s_drain_saw_empty = false;
    gen = s_flush_generation;
    portEXIT_CRITICAL(&s_epoch_mux);
    if (diag_enabled) {
        xTaskNotifyGive(s_drain_task);   // wake for the final empty check
    }

    while (esp_timer_get_time() < deadline_us) {
        if (!diag_enabled) {
            drain_ok = true;
            break;
        }
        xSemaphoreTake(s_drain_idle_sem, pdMS_TO_TICKS(10));
        portENTER_CRITICAL(&s_epoch_mux);
        bool done = s_drain_saw_empty && s_drain_inflight == 0 && s_drain_acked_generation == gen;
        portEXIT_CRITICAL(&s_epoch_mux);
        if (done) {
            drain_ok = true;
            break;
        }
        xTaskNotifyGive(s_drain_task);
    }

    bool barrier_ok = inflight_zero && drain_ok;

    /* step 4: acquire the single writer lock (no active writer may interleave). */
    bool got_lock = (xSemaphoreTake(s_tx_lock, pdMS_TO_TICKS(50)) == pdTRUE);

    /* steps 5+7 (final-audit §3): fflush/stdio and fsync are checked
     * INDIVIDUALLY and feed `ok` directly — a confirmation may never be claimed
     * on an unchecked write. Observation about this IDF version: with
     * CONFIG_ESP_CONSOLE_UART=y, fd 1 is owned by the UART VFS and its
     * fsync hook (esp_driver_uart uart_fsync) calls
     * esp_rom_output_tx_wait_idle() and returns 0 unconditionally, so fsync
     * cannot report failure here today; the check is kept because that is the
     * documented UART-TX-idle wait and a future hook may return an error. The
     * failures that ARE observable in this build are fwrite short writes and
     * fflush EOF, both handled in write_line_core(). */
    int fflush_result = fflush(stdout);
    bool fsync_ok = (fsync(fileno(stdout)) == 0);
    bool tx_drained = (fflush_result == 0) && fsync_ok;

    int64_t end_ts_us = esp_timer_get_time();
    uint32_t queue_pending = s_diag_queue ? (uint32_t)uxQueueMessagesWaiting(s_diag_queue) : 0;
    uint32_t drain_inflight_final = s_drain_inflight;

    /* steps 6-7: ACK is the last physical record, written under the held lock,
     * then release once. send_ack_locked never re-takes s_tx_lock (no deadlock).
     * stop_ack_drained is true only when the ACK line itself provably reached
     * the wire (fwrite complete AND fsync OK after release) — the browser uses
     * it so a short-written/garbled ACK can never finalize a confirmed
     * boundary. Even then, device confirmation is NOT a claim of browser
     * receipt (§18.13: post-device loss is host-accounted). */
    bool stop_ack_drained = false;
    if (got_lock) {
        char body[896];
        snprintf(body, sizeof(body),
                 "{\"type\":\"ack\",\"cmd\":\"TAKE_END\",\"ok\":%s,\"epoch\":%" PRIu32
                 ",\"gen\":%" PRIu32 ",\"end_ts_us\":%" PRId64 ",\"boot_id\":%" PRIu32
                 ",\"diag_seq_assigned_max\":%" PRIu32 ",\"diag_seq_enqueued_max\":%" PRIu32
                 ",\"diag_seq_emitted_max\":%" PRIu32
                 ",\"counters\":{\"diag_queue_overflow\":%" PRIu32 ",\"serial_tx_lock_timeout\":%" PRIu32
                 ",\"truncated_msg\":%" PRIu32 ",\"serial_short_write\":%" PRIu32
                 ",\"csi_throttle_drop\":%" PRIu32 ",\"frame_tx_drop\":%" PRIu32
                 ",\"csi_callback\":%" PRIu32 ",\"csi_event_persisted\":%" PRIu32
                 ",\"ping_event_persisted\":%" PRIu32 ",\"diag_emit_failed\":%" PRIu32 "}"
                 ",\"queue_pending\":%" PRIu32 ",\"drain_inflight\":%" PRIu32
                 ",\"drain_saw_empty\":%s,\"inflight_at_close\":%" PRIu32
                 ",\"barrier_ok\":%s,\"tx_drained\":%s,\"diagnostics_enabled\":%s"
                 ",\"fflush_ok\":%s,\"fsync_ok\":%s}",
                 barrier_ok && tx_drained ? "true" : "false",
                 epoch, gen, (int64_t)end_ts_us, s_boot_id,
                 s_diag_seq_assigned_max, s_diag_seq_enqueued_max, s_diag_seq_emitted_max,
                 s_diag_queue_overflow_count, s_serial_tx_lock_timeout_count,
                 s_ctx.truncated_msg_count, s_serial_short_write_count,
                 s_csi_throttle_drop_count, s_frame_tx_drop_count,
                 s_csi_callback_count, s_csi_event_persisted_count, s_ping_event_persisted_count,
                 s_diag_emit_failed_count,
                 queue_pending, drain_inflight_final,
                 s_drain_saw_empty ? "true" : "false", inflight_at_close,
                 barrier_ok ? "true" : "false", tx_drained ? "true" : "false",
                 diag_enabled ? "true" : "false",
                 fflush_result == 0 ? "true" : "false", fsync_ok ? "true" : "false");
        int ack_written = send_ack_locked(body);
        xSemaphoreGive(s_tx_lock);
        /* ACK body wrote completely; then flush + fsync the whole line out to
         * the idle UART outside the lock (no writer races during this window:
         * admission is closed and this task owns the command stream). */
        if (ack_written > 0) {
            stop_ack_drained = (fflush(stdout) == 0) && (fsync(fileno(stdout)) == 0);
        }
    }
    if (!got_lock || !stop_ack_drained) {
        /* No ACK at all, or a short/failed ACK write: the boundary cannot be
         * confirmed and the browser finalizes as boundary_unconfirmed. */
        ESP_LOGW(TAG, "STOP ACK not confirmed: got_lock=%s ack_drained=%s",
                 got_lock ? "yes" : "no", stop_ack_drained ? "yes" : "no");
    }

    /* The take is closed regardless of barrier outcome: admission stays closed
     * (s_closing) until the next accepted TAKE_BEGIN, so no producer can add
     * items to this session anymore. The next TAKE_BEGIN still verifies
     * queue/drain quiescence before it opens a new epoch. */
    portENTER_CRITICAL(&s_epoch_mux);
    s_diag_take_open = false;
    portEXIT_CRITICAL(&s_epoch_mux);
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

/*
 * Reports the stimulus settings alongside the requested enable state: the task
 * may still be winding down after a stop, so the panel needs both numbers to
 * show what is configured and what is actually running.
 *
 * csi_hz_x10 and last_rx_age_ms are measured, not derived from the configured
 * burst. They are what tells the user whether the stimulus setting actually
 * produces CSI: a running task with a growing last_rx_age_ms means bursts are
 * failing and no frames arrive. last_rx_age_ms is -1 when no frame has ever
 * been seen.
 */
static void send_stimulus_state(void)
{
    ht_stimulus_config_t cfg = {0};
    (void)ht_stimulus_get_config(&cfg);

    ht_stimulus_stats_t stats = {0};
    (void)ht_stimulus_get_stats(&stats);

    tcp_stimulus_config_t tcfg = {0};
    (void)tcp_stimulus_get_config(&tcfg);
    tcp_stimulus_stats_t tstats = {0};
    (void)tcp_stimulus_get_stats(&tstats);

    dns_stimulus_config_t dcfg = {0};
    (void)dns_stimulus_get_config(&dcfg);
    dns_stimulus_stats_t dstats = {0};
    (void)dns_stimulus_get_stats(&dstats);
    char dns_server[16] = "";
    (void)dns_stimulus_server_ip(dns_server, sizeof(dns_server));

    int64_t last_rx_age_ms = -1;
    if (s_ctx.csi_last_rx_us > 0) {
        int64_t age_us = esp_timer_get_time() - s_ctx.csi_last_rx_us;
        last_rx_age_ms = (age_us > 0) ? (age_us / 1000) : 0;
    }

    /* Gateway IPv4, read from the STA interface so ping mode can report the
     * actual target rather than a guessed address. */
    char gw_ip[16] = "";
    esp_netif_t *sta = esp_netif_get_handle_from_ifkey("WIFI_STA_DEF");
    esp_netif_ip_info_t ipi = {0};
    if (sta && esp_netif_get_ip_info(sta, &ipi) == ESP_OK) {
        snprintf(gw_ip, sizeof(gw_ip), IPSTR, IP2STR(&ipi.gw));
    }

    double interval_ms = (s_stimulus.ping_hz > 0) ? (1000.0 / (double)s_stimulus.ping_hz) : 0.0;
    bool http_running = ht_stimulus_is_running();
    bool tcp_running = tcp_stimulus_is_running();
    bool dns_running = dns_stimulus_is_running();
    bool stim_running = http_running || tcp_running || dns_running || s_stimulus.mode == STIM_MODE_PING;

    /*
     * burst_bytes/pause_ms/running/enabled stay at the top level for backward
     * compatibility with the existing stimulus panel and completeness check,
     * while the nested http/ping objects carry the per-take experiment counters.
     */
    (void)write_line(
        "{\"type\":\"stimulus\",\"mode\":\"%s\",\"enabled\":%s,\"running\":%s,"
        "\"burst_bytes\":%" PRIu32 ",\"pause_ms\":%" PRIu32 ","
        "\"switched_at_us\":%lld,"
        "\"csi_hz_x10\":%" PRIu32 ",\"last_rx_age_ms\":%" PRId64 ",\"csi_ap_frame_count\":%" PRIu32 ","
        "\"http\":{\"burst_bytes\":%" PRIu32 ",\"pause_ms\":%" PRIu32 ",\"running\":%s,"
        "\"keep_alive\":%s,"
        "\"requests\":%" PRIu32 ",\"burst_success\":%" PRIu32 ",\"burst_failed\":%" PRIu32 ","
        "\"bytes_requested\":%" PRIu64 ",\"bytes_received\":%" PRIu64 ","
        "\"active_ms\":%" PRIu32 ",\"idle_ms\":%" PRIu32 ",\"errors\":%" PRIu32 "},"
        "\"ping\":{\"configured_frequency_hz\":%" PRIu32 ",\"configured_interval_ms\":%.1f,"
        "\"target_type\":\"default_gateway\",\"target_ip\":\"%s\","
        "\"ping_request_count\":null,\"ping_reply_count\":null,\"ping_timeout_count\":null,\"rtt_ms\":null,"
        "\"metrics_reason\":\"esp_wifi_sensing FSM ping does not surface esp_ping result callbacks; a second session is disallowed to avoid duplicate pings\"},"
        "\"tcp\":{\"configured_concurrency\":%" PRIu32 ",\"configured_interval_ms\":%" PRIu32 ","
        "\"configured_timeout_ms\":%" PRIu32 ",\"port\":%" PRIu16 ",\"port_alt\":%" PRIu16 ","
        "\"target_type\":\"default_gateway\",\"target_ip\":\"%s\",\"running\":%s,"
        "\"rounds\":%" PRIu32 ",\"connect_ok\":%" PRIu32 ",\"connect_fail\":%" PRIu32 ","
        "\"port_flips\":%" PRIu32 ",\"active_port\":%u},"
        "\"dns\":{\"server\":\"%s\",\"query_name\":\"" DNS_STIMULUS_QUERY_NAME "\","
        "\"configured_interval_ms\":%" PRIu32 ",\"configured_timeout_ms\":%" PRIu32 ","
        "\"running\":%s,\"rounds\":%" PRIu32 ",\"queries_sent\":%" PRIu32 ","
        "\"responses_ok\":%" PRIu32 ",\"responses_bad\":%" PRIu32 ",\"timeouts\":%" PRIu32 ","
        "\"errors\":%" PRIu32 ",\"bytes_received\":%" PRIu64 ","
        "\"latency_us_last\":%" PRIu32 ",\"latency_us_min\":%" PRIu32 ",\"latency_us_max\":%" PRIu32 "},"
        "\"free_heap\":%" PRIu32 "}\n",
        stim_mode_name(s_stimulus.mode),
        (s_stimulus.mode != STIM_MODE_OFF) ? "true" : "false",
        stim_running ? "true" : "false",
        cfg.burst_bytes, cfg.pause_ms,
        (long long)s_stimulus.switched_at_us,
        s_ctx.csi_rate_hz_x10, last_rx_age_ms, s_ctx.csi_ap_frame_count,
        cfg.burst_bytes, cfg.pause_ms, http_running ? "true" : "false",
        cfg.keep_alive ? "true" : "false",
        stats.requests, stats.burst_success, stats.burst_failed,
        stats.bytes_requested, stats.bytes_received,
        stats.active_ms, stats.idle_ms, stats.errors,
        s_stimulus.ping_hz, interval_ms, gw_ip,
        tcfg.concurrency, tcfg.interval_ms, tcfg.timeout_ms, tcfg.port, tcfg.port_alt,
        gw_ip, tcp_running ? "true" : "false",
        tstats.rounds, tstats.connect_ok, tstats.connect_fail, tstats.port_flips,
        (unsigned)tstats.active_port,
        dns_server,
        dcfg.interval_ms, dcfg.timeout_ms,
        dns_running ? "true" : "false",
        dstats.rounds, dstats.queries_sent, dstats.responses_ok,
        dstats.responses_bad, dstats.timeouts, dstats.errors,
        dstats.bytes_received,
        dstats.latency_us_last, dstats.latency_us_min, dstats.latency_us_max,
        esp_get_free_heap_size());
}

static const char *stim_mode_name(stim_mode_t mode)
{
    switch (mode) {
    case STIM_MODE_HTTP:
        return "http_cloudflare";
    case STIM_MODE_PING:
        return "icmp_ping_gateway";
    case STIM_MODE_TCP:
        return "tcp_gateway";
    case STIM_MODE_DNS:
        return "dns_query";
    case STIM_MODE_OFF:
    default:
        return "off";
    }
}

/*
 * The single choke point that guarantees mutual exclusion (§5, §16): it always
 * stops both sources first, then starts only the selected one. Ping needs the
 * FSM (sensing_ready); if it is requested early the mode is still stored and a
 * later link-up applies it. Counters are reset so a take's numbers are scoped
 * to that take.
 */
static void apply_stimulus_mode(const char *reason)
{
#if CONFIG_ESP_WIFI_SENSING_HT_STIMULUS_ENABLE
    ht_stimulus_stop();
#endif
    tcp_stimulus_stop();
    dns_stimulus_stop();
    if (s_ctx.sensing_ready && s_ctx.fsm) {
        (void)esp_wifi_sensing_fsm_ping_router_stop(s_ctx.fsm);
    }

    switch (s_stimulus.mode) {
    case STIM_MODE_HTTP:
#if CONFIG_ESP_WIFI_SENSING_HT_STIMULUS_ENABLE
        (void)ht_stimulus_start();
#endif
        break;
    case STIM_MODE_PING:
        if (s_ctx.sensing_ready && s_ctx.fsm) {
            (void)esp_wifi_sensing_fsm_set_ping_frequency_hz(s_ctx.fsm, s_stimulus.ping_hz);
            (void)esp_wifi_sensing_fsm_ping_router_start(s_ctx.fsm);
        }
        break;
    case STIM_MODE_TCP:
        (void)tcp_stimulus_start();
        break;
    case STIM_MODE_DNS:
        (void)dns_stimulus_start();
        break;
    case STIM_MODE_OFF:
    default:
        break;
    }

    s_stimulus.switched_at_us = esp_timer_get_time();
    ht_stimulus_reset_stats();
    tcp_stimulus_reset_stats();
    dns_stimulus_reset_stats();
    s_ctx.csi_ap_frame_count = 0;
    ESP_LOGI(TAG, "stimulus applied: mode=%s ping_hz=%lu (%s)",
             stim_mode_name(s_stimulus.mode), (unsigned long)s_stimulus.ping_hz, reason);
}

void web_serial_monitor_link_up_apply_stimulus(void)
{
    apply_stimulus_mode("link-up");
}

void web_serial_monitor_link_down_stop_stimulus(void)
{
#if CONFIG_ESP_WIFI_SENSING_HT_STIMULUS_ENABLE
    ht_stimulus_stop();
#endif
    tcp_stimulus_stop();
    dns_stimulus_stop();
    if (s_ctx.sensing_ready && s_ctx.fsm) {
        (void)esp_wifi_sensing_fsm_ping_router_stop(s_ctx.fsm);
    }
}

static void handle_set_stimulus_mode(char *args)
{
    char *saveptr = NULL;
    char *mode_tok = strtok_r(args, " ", &saveptr);
    if (!mode_tok) {
        send_ack("SET_STIMULUS_MODE", false,
                 "usage: SET_STIMULUS_MODE <http_cloudflare|icmp_ping|tcp_gateway|dns_query|off> [hz|burst pause|interval timeout]");
        return;
    }

    stim_mode_t prev = s_stimulus.mode;

    if (strcmp(mode_tok, "http_cloudflare") == 0 || strcmp(mode_tok, "http") == 0) {
        s_stimulus.mode = STIM_MODE_HTTP;
        char *burst = strtok_r(NULL, " ", &saveptr);
        char *pause = strtok_r(NULL, " ", &saveptr);
        char *ka_tok = strtok_r(NULL, " ", &saveptr);
        if (burst && pause) {
            ht_stimulus_config_t cfg = {0};
            if (ht_stimulus_get_config(&cfg) == ESP_OK) {
                cfg.burst_bytes = (uint32_t)strtoul(burst, NULL, 10);
                cfg.pause_ms = (uint32_t)strtoul(pause, NULL, 10);
                /* Explicit: absent ka_tok means off, not inherited. Without
                 * this, a previous keep-alive leg bleeds into subsequent legs
                 * that omit the flag. */
                cfg.keep_alive = (ka_tok && (strcmp(ka_tok, "on") == 0 || strcmp(ka_tok, "1") == 0));
                /* enabled=false so set_config only validates+stores; apply starts it. */
                cfg.enabled = false;
                if (ht_stimulus_set_config(&cfg) != ESP_OK) {
                    send_ack("SET_STIMULUS_MODE", false,
                             "burst must be 4000..20000000, pause 0..5000, ka on|off");
                    s_stimulus.mode = prev;
                    return;
                }
            }
        }
    } else if (strcmp(mode_tok, "icmp_ping") == 0 || strcmp(mode_tok, "ping") == 0) {
        char *hz = strtok_r(NULL, " ", &saveptr);
        uint32_t f = hz ? (uint32_t)strtoul(hz, NULL, 10) : s_stimulus.ping_hz;
        if (f == 0 || f > 1000) {
            send_ack("SET_STIMULUS_MODE", false, "ping hz must be 1..1000");
            return;
        }
        s_stimulus.ping_hz = f;
        s_stimulus.mode = STIM_MODE_PING;
    } else if (strcmp(mode_tok, "tcp_gateway") == 0 || strcmp(mode_tok, "tcp") == 0) {
        s_stimulus.mode = STIM_MODE_TCP;
    } else if (strcmp(mode_tok, "dns_query") == 0 || strcmp(mode_tok, "dns") == 0) {
        char *iv = strtok_r(NULL, " ", &saveptr);
        char *to = strtok_r(NULL, " ", &saveptr);
        if (iv) {
            dns_stimulus_config_t cfg = {0};
            if (dns_stimulus_get_config(&cfg) == ESP_OK) {
                cfg.interval_ms = (uint32_t)strtoul(iv, NULL, 10);
                if (to) {
                    cfg.timeout_ms = (uint32_t)strtoul(to, NULL, 10);
                }
                if (dns_stimulus_set_config(&cfg) != ESP_OK) {
                    send_ack("SET_STIMULUS_MODE", false,
                             "dns interval must be 10..5000 ms, timeout 1..5000 ms");
                    s_stimulus.mode = prev;
                    return;
                }
            }
        }
        s_stimulus.mode = STIM_MODE_DNS;
    } else if (strcmp(mode_tok, "off") == 0) {
        s_stimulus.mode = STIM_MODE_OFF;
    } else {
        send_ack("SET_STIMULUS_MODE", false, "mode must be http_cloudflare, icmp_ping, tcp_gateway, dns_query or off");
        return;
    }

    apply_stimulus_mode("command");
    send_stimulus_state();
    char detail[64];
    snprintf(detail, sizeof(detail), "%s -> %s", stim_mode_name(prev), stim_mode_name(s_stimulus.mode));
    send_ack("SET_STIMULUS_MODE", true, detail);
}

/*
 * Runtime tuning of the TCP gateway stimulus: SET_TCP_STIMULUS <concurrency>
 * <interval_ms> <timeout_ms>. Every token is optional, so a partial edit keeps
 * the current value for the rest; a bare SET_TCP_STIMULUS reads the live config
 * back (set_config re-accepts what get_config returned).
 *
 * This deliberately does NOT go through apply_stimulus_mode(). Re-applying the
 * mode while TCP is the active source would stop the task and then no-op the
 * restart: tcp_stimulus_stop() only raises the request flag, tcp_stimulus_start()
 * returns early while s_running is still true, and the flagged task then exits -
 * leaving the stimulus silently off. It would also be the wrong shape anyway: a
 * task must not be destroyed while it is waiting inside poll()/select()
 * (ESP-IDF v5.5.3 lwip.rst, "Thread-Safe Sockets"). Neither is needed, because
 * the task reads the volatile settings at the top of every round, so a new
 * config takes effect from the next round with the task untouched.
 */
static void handle_set_tcp_stimulus(char *args)
{
    tcp_stimulus_config_t cfg = {0};
    if (tcp_stimulus_get_config(&cfg) != ESP_OK) {
        send_ack("SET_TCP_STIMULUS", false, "get cfg failed");
        return;
    }

    char *saveptr = NULL;
    char *conc_tok = strtok_r(args, " ", &saveptr);
    char *int_tok = strtok_r(NULL, " ", &saveptr);
    char *timeout_tok = strtok_r(NULL, " ", &saveptr);

    if (conc_tok) {
        cfg.concurrency = (uint32_t)strtoul(conc_tok, NULL, 10);
    }
    if (int_tok) {
        cfg.interval_ms = (uint32_t)strtoul(int_tok, NULL, 10);
    }
    if (timeout_tok) {
        cfg.timeout_ms = (uint32_t)strtoul(timeout_tok, NULL, 10);
    }

    if (tcp_stimulus_set_config(&cfg) != ESP_OK) {
        send_ack("SET_TCP_STIMULUS", false,
                 "concurrency 1..8, interval 1..5000 ms, timeout 0..5000 ms");
        return;
    }

    send_stimulus_state();
    char detail[96];
    snprintf(detail, sizeof(detail), "conc=%" PRIu32 " interval=%" PRIu32 "ms timeout=%" PRIu32 "ms",
             cfg.concurrency, cfg.interval_ms, cfg.timeout_ms);
    send_ack("SET_TCP_STIMULUS", true, detail);
}

/*
 * Legacy HTTP-only knob, now routed through apply_stimulus_mode so it can never
 * start HTTP while ping is the selected mode. Turning it off only stops HTTP
 * when HTTP is the active mode; ping mode is controlled via SET_STIMULUS_MODE.
 */
static void handle_set_stimulus(char *args)
{
    ht_stimulus_config_t cfg = {0};
    if (ht_stimulus_get_config(&cfg) != ESP_OK) {
        send_ack("SET_STIMULUS", false, "get cfg failed");
        return;
    }

    char *saveptr = NULL;
    char *state = strtok_r(args, " ", &saveptr);
    if (!state) {
        send_ack("SET_STIMULUS", false, "usage: SET_STIMULUS <on|off> [burst_bytes] [pause_ms]");
        return;
    }

    bool on;
    if ((strcmp(state, "on") == 0) || (strcmp(state, "1") == 0) ||
        (strcasecmp(state, "true") == 0)) {
        on = true;
    } else if ((strcmp(state, "off") == 0) || (strcmp(state, "0") == 0) ||
               (strcasecmp(state, "false") == 0)) {
        on = false;
    } else {
        send_ack("SET_STIMULUS", false, "state must be on or off");
        return;
    }

    char *token = strtok_r(NULL, " ", &saveptr);
    if (token) {
        cfg.burst_bytes = (uint32_t)strtoul(token, NULL, 10);
    }
    token = strtok_r(NULL, " ", &saveptr);
    if (token) {
        cfg.pause_ms = (uint32_t)strtoul(token, NULL, 10);
    }
    /* Only validate/store here; apply_stimulus_mode owns start/stop. */
    cfg.enabled = false;

    esp_err_t err = ht_stimulus_set_config(&cfg);
    if (err != ESP_OK) {
        send_ack("SET_STIMULUS", false,
                 err == ESP_ERR_INVALID_ARG ? "burst must be 100000..20000000, pause 0..5000"
                                            : esp_err_to_name(err));
        return;
    }

    if (on) {
        s_stimulus.mode = STIM_MODE_HTTP;
    } else if (s_stimulus.mode == STIM_MODE_HTTP) {
        s_stimulus.mode = STIM_MODE_OFF;
    }

    apply_stimulus_mode("SET_STIMULUS");
    send_stimulus_state();
    send_ack("SET_STIMULUS", true, on ? "stimulus on" : "stimulus off");
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
        "{\"type\":\"hello\",\"transport\":\"stdio\",\"target\":\"%s\",\"stream_period_ms\":%" PRIu32 ",\"amplitude_log_enabled\":%s,\"csi_stream_enabled\":%s,\"csi_stream_period_ms\":%" PRIu32 ",\"sensing_ready\":%s,\"auto_reconnect\":%s,\"peers\":[%s]}\n",
        CONFIG_IDF_TARGET,
        s_ctx.stream_period_ms,
        enabled ? "true" : "false",
        s_ctx.csi_stream_enabled ? "true" : "false",
        s_ctx.csi_stream_period_ms,
        s_ctx.sensing_ready ? "true" : "false",
        s_ctx.csi_wd_enabled ? "true" : "false",
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
     * Recording-epoch commands (§18.10/§18.11). Handled at the transport level
     * (independent of the sensing FSM) because the diagnostic queue exists as
     * soon as the monitor task starts. TAKE_BEGIN opens the device-side epoch;
     * TAKE_END runs the two-path STOP barrier and emits the final ACK.
     */
    if (strncmp(cmd, "TAKE_BEGIN", 10) == 0) {
        char *arg = cmd + 10;
        while (*arg == ' ') {
            arg++;
        }
        uint32_t epoch = (uint32_t)strtoul(arg, NULL, 10);
        handle_take_begin(epoch);
        return;
    }
    if (strncmp(cmd, "TAKE_END", 8) == 0) {
        char *arg = cmd + 8;
        while (*arg == ' ') {
            arg++;
        }
        uint32_t epoch = (uint32_t)strtoul(arg, NULL, 10);
        handle_take_end(epoch);
        return;
    }

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

    if (strncmp(cmd, "AUTO_RECONNECT ", 15) == 0) {
        s_ctx.csi_wd_enabled = (strtol(cmd + 15, NULL, 10) != 0);
        send_ack("AUTO_RECONNECT", true, s_ctx.csi_wd_enabled ? "enabled" : "disabled");
        return;
    }

    /*
     * The stimulus only needs a network interface, not the sensing FSM, so it
     * is reachable before sensing is ready. That keeps the panel usable while
     * the channel is still flat and the FSM has not started yet.
     */
    if (strcmp(cmd, "GET_STIMULUS") == 0) {
        send_stimulus_state();
        send_ack("GET_STIMULUS", true, "stimulus");
        return;
    }

    if (strncmp(cmd, "SET_STIMULUS_MODE ", 18) == 0) {
        handle_set_stimulus_mode(cmd + 18);
        return;
    }

    /*
     * TCP tuning sits next to the other stimulus commands for the same reason:
     * it only needs the network interface, not the sensing FSM.
     */
    if (strncmp(cmd, "SET_TCP_STIMULUS ", 17) == 0 || strcmp(cmd, "SET_TCP_STIMULUS") == 0) {
        handle_set_tcp_stimulus(cmd + 16);
        return;
    }

    if (strncmp(cmd, "SET_STIMULUS ", 13) == 0 || strcmp(cmd, "SET_STIMULUS") == 0) {
        handle_set_stimulus(cmd + 12);
        return;
    }

    if (!s_ctx.sensing_ready) {
        send_ack(cmd, false, "sensing not ready");
        return;
    }

    if (strcmp(cmd, "HELLO") == 0) {
        send_hello();
        send_runtime_config();
        send_stimulus_state();
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
        if (period_ms != 0 &&
                (period_ms < WEB_SERIAL_CSI_MIN_PERIOD_MS ||
                 period_ms > WEB_SERIAL_CSI_MAX_PERIOD_MS)) {
            send_ack("SET_CSI_PERIOD", false, "period must be 0 or 20..1000 ms");
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

    if (strncmp(cmd, "PHYPROBE", 8) == 0) {
        const char *arg = cmd + 8;
        while (*arg == ' ') {
            arg++;
        }
        if (*arg == '\0' || strcasecmp(arg, "GET") == 0) {
            send_ack("PHYPROBE", true, csi_phy_probe_is_enabled() ? "on" : "off");
            return;
        }
        bool enable = false;
        if ((strcasecmp(arg, "on") == 0) || (strcmp(arg, "1") == 0)) {
            enable = true;
        } else if ((strcasecmp(arg, "off") == 0) || (strcmp(arg, "0") == 0)) {
            enable = false;
        } else {
            send_ack("PHYPROBE", false, "invalid value");
            return;
        }
        csi_phy_probe_set_enabled(enable);
        send_ack("PHYPROBE", true, enable ? "on" : "off");
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
    int64_t last_status_us = 0;
    uint32_t last_frame_count = 0;

    /* Emit an initial snapshot so the browser can render immediately after connecting. */
    send_hello();
    send_runtime_config();
    send_wifi_info();
    send_all_configs();
    /* Without this the stimulus panel stays on "-" until the user clicks Apply,
     * because the browser never asks for the stimulus state on connect. */
    send_stimulus_state();

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

        /*
         * Derive the CSI frame rate here rather than in the Wi-Fi callback: this
         * task already sleeps 10 ms, while the callback must stay cheap.
         */
        if (last_status_us == 0 || (now_us - last_status_us) >= (STIMULUS_STATUS_PERIOD_MS * 1000LL)) {
            if (last_status_us != 0) {
                uint32_t frames = s_ctx.csi_frame_count;
                int64_t elapsed_us = now_us - last_status_us;
                uint32_t elapsed_ms = (uint32_t)(elapsed_us / 1000);
                if (elapsed_ms > 0) {
                    s_ctx.csi_rate_hz_x10 = (uint32_t)(((uint64_t)(frames - last_frame_count) * 10000ULL) / elapsed_ms);
                }
            }
            last_frame_count = s_ctx.csi_frame_count;
            last_status_us = now_us;
            send_stimulus_state();
            /* CSI-callback probe report runs on this same 1 s cadence in a task
             * (never in the Wi-Fi callback). No-op unless PHYPROBE was enabled. */
            csi_phy_probe_report(now_us);
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
    s_ctx.csi_wd_enabled = true;

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

    /* Diagnostic MPSC plumbing (Prioritas 1). Queue storage comes from the heap;
     * N=256 x sizeof(diag_item_t)=56 B = 14336 B (~14 KB, measured on xtensa).
     * Post-implementation review §3: allocation failure here is NON-FATAL and
     * degrades to "diagnostics disabled" (s_diag_queue/s_drain_task stay NULL;
     * every producer path no-ops on the NULL queue and the STOP barrier skips
     * the MPSC step) rather than aborting the serial monitor, so a low-memory
     * boot can never take down the CSI/streaming path. A successful build does
     * NOT prove this allocation succeeds at runtime — the heap low-water is
     * only known on the device. */
    s_diag_queue = xQueueCreate(DIAG_QUEUE_LEN, sizeof(diag_item_t));
    s_drain_idle_sem = xSemaphoreCreateBinary();
    if (!s_diag_queue || !s_drain_idle_sem) {
        if (s_diag_queue) {
            vQueueDelete(s_diag_queue);
            s_diag_queue = NULL;
        }
        if (s_drain_idle_sem) {
            vSemaphoreDelete(s_drain_idle_sem);
            s_drain_idle_sem = NULL;
        }
        s_diag_disable_reason = !s_diag_queue ? "queue_alloc_failed" : "sem_alloc_failed";
        ESP_LOGE(TAG, "diagnostics disabled (%s): free heap=%" PRIu32,
                 s_diag_disable_reason, esp_get_free_heap_size());
    } else {
        /* Sole-consumer drain task (Prioritas 1). Same priority band as the
         * monitor so it is not starved, but it never blocks producers (queue
         * send is 0-tmo). Creation failure degrades the same way as the queue. */
        BaseType_t drain_ok = xTaskCreate(drain_task,
                                          "diag_drain",
                                          DIAG_DRAIN_TASK_STACK,
                                          NULL,
                                          DIAG_DRAIN_TASK_PRIORITY,
                                          &s_drain_task);
        if (drain_ok != pdPASS) {
            s_drain_task = NULL;
            vQueueDelete(s_diag_queue);
            s_diag_queue = NULL;
            vSemaphoreDelete(s_drain_idle_sem);
            s_drain_idle_sem = NULL;
            s_diag_disable_reason = "drain_task_create_failed";
            ESP_LOGE(TAG, "diagnostics disabled (%s)", s_diag_disable_reason);
        }
    }
    s_boot_id = esp_random();
    s_closing = false;
    s_take_epoch = 0;
    s_inflight = 0;
    s_drain_inflight = 0;
    s_drain_saw_empty = false;
    s_flush_requested = false;
    s_flush_generation = 0;
    s_drain_acked_generation = 0;
    s_diag_take_open = false;
    s_diag_seq_assigned = 0;
    s_diag_seq_assigned_max = 0;
    s_diag_seq_enqueued_max = 0;
    s_diag_seq_emitted_max = 0;

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

    ESP_LOGI(TAG, "web serial monitor transport started, input=%s, output=stdio, diag_queue=%u items x %u B (diagnostics %s)",
             input_mode_name(), (unsigned)DIAG_QUEUE_LEN, (unsigned)sizeof(diag_item_t),
             (s_diag_queue && s_drain_task) ? "enabled" : "DISABLED");

    esp_timer_handle_t csi_wd_timer = NULL;
    const esp_timer_create_args_t csi_wd_args = {
        .callback = csi_watchdog_check,
        .name = "csi_wd",
    };
    if (esp_timer_create(&csi_wd_args, &csi_wd_timer) == ESP_OK) {
        esp_timer_start_periodic(csi_wd_timer, CSI_WD_CHECK_PERIOD_MS * 1000ULL);
    }
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

    /* Prioritas 1: receive every ping success/timeout with per-reply seqno/ts.
     * Optional hook on the vendored component; harmless if ping is not started. */
    esp_err_t ping_cb_err = esp_wifi_sensing_fsm_register_ping_event_cb(
        config->fsm, web_serial_monitor_ping_event_cb, NULL);
    if (ping_cb_err != ESP_OK) {
        ESP_LOGW(TAG, "ping event cb registration failed: %s", esp_err_to_name(ping_cb_err));
    }

    ESP_LOGI(TAG, "sensing attached, peers=%u, period=%" PRIu32 "ms",
             (unsigned)s_ctx.peer_num, s_ctx.stream_period_ms);

    /* Republish the full snapshot so the browser reflects the new AP without a reconnect. */
    send_hello();
    send_runtime_config();
    send_wifi_info();
    send_all_configs();
    return ESP_OK;
}

esp_err_t web_serial_monitor_update_peer_mac(const char *name, const uint8_t *mac)
{
    if (!name || !mac) {
        return ESP_ERR_INVALID_ARG;
    }
    if (!s_ctx.initialized || !s_ctx.sensing_ready) {
        return ESP_ERR_INVALID_STATE;
    }

    for (size_t i = 0; i < s_ctx.peer_num; i++) {
        web_serial_monitor_peer_t *peer = &s_ctx.peers[i];
        if (strcmp(name, peer->name) != 0) {
            continue;
        }
        if (memcmp(peer->mac, mac, sizeof(peer->mac)) == 0) {
            return ESP_OK;
        }

        memcpy(peer->mac, mac, sizeof(peer->mac));
        ESP_LOGI(TAG, "monitor peer %s rebound to " MACSTR, name, MAC2STR(mac));

        /* Push the new MAC so GET_CFG/SET_CFG/TRAIN on this peer hit the FSM channel again. */
        send_channel_config(peer);
        return ESP_OK;
    }

    return ESP_ERR_NOT_FOUND;
}
