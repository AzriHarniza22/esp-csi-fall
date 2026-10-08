/*
 * SPDX-FileCopyrightText: 2026 Espressif Systems (Shanghai) CO LTD
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <stdio.h>
#include <inttypes.h>
#include <string.h>

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/event_groups.h"
#include "nvs_flash.h"
#include "esp_err.h"
#include "esp_log.h"
#include "esp_mac.h"
#include "esp_wifi.h"
#include "esp_now.h"
#include "esp_netif.h"
#include "esp_event.h"

#include "esp_wifi_sensing.h"
#include "esp_radar.h"

#include "led_control.h"
#include "web_serial_monitor.h"
#include "wifi_runtime_manager.h"
#include "ht_stimulus.h"

static const char *TAG = "wifi_sensing_demo";
static esp_wifi_sensing_fsm_handle_t s_hms = NULL;
static uint8_t s_mac_ap[6] = {0};

/*
 * The demo monitors three channels:
 * 1. The connected AP BSSID.
 * 2. A fixed CSI sender peer.
 * 3. A second fixed peer used as an extra reference channel.
 */
static const uint8_t CONFIG_CSI_SEND_MAC[]   = {0x1a, 0x00, 0x00, 0x00, 0x00, 0x00};
static const uint8_t CONFIG_CSI_SEND_MAC_2[] = {0x1a, 0x00, 0x00, 0x00, 0x00, 0x01};

static void espnow_recv_cb(const esp_now_recv_info_t *recv_info, const uint8_t *data, int data_len)
{
    if (!recv_info || !data || data_len <= 0) {
        return;
    }

    if (memcmp(recv_info->src_addr, CONFIG_CSI_SEND_MAC_2, 6) != 0) {
        /* Keep the console focused on the dedicated CSI sender. */
        return;
    }

    if (data_len >= (int)sizeof(uint32_t)) {
        uint32_t cnt = 0;
        memcpy(&cnt, data, sizeof(cnt));
        ESP_LOGD(TAG, "ESPNOW RX <- " MACSTR " len=%d cnt=%" PRIu32, MAC2STR(recv_info->src_addr), data_len, cnt);
    } else {
        ESP_LOGD(TAG, "ESPNOW RX <- " MACSTR " len=%d", MAC2STR(recv_info->src_addr), data_len);
    }
}

static void espnow_rx_init(void)
{
    esp_err_t err = esp_now_init();
    if (err == ESP_ERR_ESPNOW_EXIST) {
        err = ESP_OK;
    }
    ESP_ERROR_CHECK(err);

    /*
     * The current sender keeps ESPNOW encryption disabled.
     * Setting a PMK here is optional and harmless for the receiver path.
     */
    ESP_ERROR_CHECK(esp_now_set_pmk((uint8_t *)"pmk1234567890123"));
    ESP_ERROR_CHECK(esp_now_register_recv_cb(espnow_recv_cb));

    /*
     * Adding a broadcast peer is not strictly required for RX, but it makes the
     * setup more tolerant across targets and console workflows.
     */
    if (!esp_now_is_peer_exist((const uint8_t[6]) {
    0xff, 0xff, 0xff, 0xff, 0xff, 0xff
})) {
        esp_now_peer_info_t peer = {0};
        memcpy(peer.peer_addr, (const uint8_t[6]) {
            0xff, 0xff, 0xff, 0xff, 0xff, 0xff
        }, 6);
        peer.channel = 0; /* Follow the current STA channel from the connected AP. */
        peer.encrypt = false;
        peer.ifidx = WIFI_IF_STA;
        ESP_ERROR_CHECK(esp_now_add_peer(&peer));
    }
}

static const char *channel_name(const uint8_t mac[6])
{
    if (memcmp(mac, s_mac_ap, 6) == 0) {
        return "AP";
    }
    if (memcmp(mac, CONFIG_CSI_SEND_MAC, 6) == 0) {
        return "MAC_1";
    }
    if (memcmp(mac, CONFIG_CSI_SEND_MAC_2, 6) == 0) {
        return "MAC_2";
    }
    return "?";
}

static void on_motion_event(esp_wifi_sensing_fsm_handle_t handle,
                            const uint8_t peer_mac[6],
                            esp_wifi_sensing_fsm_event_t event,
                            uint32_t data,
                            void *usr_data)
{
    (void)handle;
    (void)usr_data;
    const char *name = channel_name(peer_mac);
    bool is_ap_channel = (memcmp(peer_mac, s_mac_ap, 6) == 0);
    if (event == ESP_WIFI_SENSING_FSM_EVENT_ACTIVE) {
        if (is_ap_channel) {
            led_notify_ap_active();
        }
        ESP_LOGI(TAG, "[%s] ACTIVE peer=" MACSTR " data=%" PRIu32,
                 name, MAC2STR(peer_mac), data);
    } else if (event == ESP_WIFI_SENSING_FSM_EVENT_INACTIVE) {
        if (is_ap_channel) {
            led_notify_ap_inactive();
        }
        ESP_LOGI(TAG, "[%s] INACTIVE peer=" MACSTR,
                 name, MAC2STR(peer_mac));
    }
}

/*
 * Owned exclusively by sensing_task. The manager state callback must not touch
 * these: it runs inside the manager mutex on the event-loop task, and sharing
 * them without synchronisation races on the 6-byte BSSID copy.
 */
static bool s_sensing_started = false;
static bool s_ping_running = false;

/*
 * The event-loop task runs on a small stack (CONFIG_ESP_SYSTEM_EVENT_TASK_SIZE,
 * 2304 bytes by default), so the GOT_IP callback must not bring up espnow/FSM
 * directly. A single bit hands the work to sensing_task, which owns a 6 KiB stack.
 */
#define SENSING_EVT_WIFI_STATE BIT0

static EventGroupHandle_t s_sensing_events = NULL;

static void sensing_request(EventBits_t bits)
{
    if (!s_sensing_events) {
        return;
    }
    xEventGroupSetBits(s_sensing_events, bits);
}

static void sensing_start_ping(void)
{
    if (!s_hms || s_ping_running) {
        return;
    }

    esp_err_t err = esp_wifi_sensing_fsm_ping_router_start(s_hms);
    if (err == ESP_OK) {
        s_ping_running = true;
        ESP_LOGI(TAG, "router ping started");
    } else if (err == ESP_ERR_INVALID_STATE) {
        ESP_LOGW(TAG, "router ping start failed: Wi-Fi STA not connected or no gateway");
    } else {
        ESP_LOGE(TAG, "router ping start failed: %s", esp_err_to_name(err));
    }
}

static void sensing_stop_ping(void)
{
    if (!s_hms || !s_ping_running) {
        return;
    }

    (void)esp_wifi_sensing_fsm_ping_router_stop(s_hms);
    s_ping_running = false;
    ESP_LOGI(TAG, "router ping stopped");

#if CONFIG_ESP_WIFI_SENSING_HT_STIMULUS_ENABLE
    ht_stimulus_stop();
#endif
}

static void sensing_start(const uint8_t *ap_bssid)
{
    if (s_sensing_started) {
        return;
    }
    s_sensing_started = true;

    espnow_rx_init();

    /*
     * Follow the public component workflow:
     * 1. Resolve the peers used by this demo.
     * 2. Create one FSM handle.
     * 3. Add one channel per peer.
     * 4. Register ACTIVE / INACTIVE callbacks.
     * 5. Start the FSM and optionally enable router-ping-assisted sampling.
     *
     * The AP BSSID comes from the manager snapshot taken on GOT_IP, which has
     * already read the AP record, so no second lookup can fail here.
     */
    memcpy(s_mac_ap, ap_bssid, sizeof(s_mac_ap));
    ESP_LOGI(TAG, "peer mac (AP BSSID): " MACSTR, MAC2STR(ap_bssid));
    ESP_LOGI(TAG, "peer mac 1 (CONFIG_CSI_SEND_MAC): " MACSTR, MAC2STR(CONFIG_CSI_SEND_MAC));
    ESP_LOGI(TAG, "peer mac 2 (CONFIG_CSI_SEND_MAC_2): " MACSTR, MAC2STR(CONFIG_CSI_SEND_MAC_2));

    esp_wifi_sensing_fsm_config_t cfg = DEFAULT_ESP_WIFI_SENSING_FSM_CONFIG();
    cfg.max_channel_num = 3;

    ESP_ERROR_CHECK(esp_wifi_sensing_fsm_create(&cfg, &s_hms));

    /* The demo monitors the connected AP plus two fixed reference peers. */
    ESP_ERROR_CHECK(esp_wifi_sensing_fsm_add_channel(s_hms, ap_bssid));
    ESP_ERROR_CHECK(esp_wifi_sensing_fsm_add_channel(s_hms, CONFIG_CSI_SEND_MAC));
    ESP_ERROR_CHECK(esp_wifi_sensing_fsm_add_channel(s_hms, CONFIG_CSI_SEND_MAC_2));

    /* Register the same callback for both state transitions to keep logging symmetric. */
    ESP_ERROR_CHECK(esp_wifi_sensing_fsm_register_event_cb(s_hms, ESP_WIFI_SENSING_FSM_EVENT_ACTIVE, on_motion_event, NULL));
    ESP_ERROR_CHECK(esp_wifi_sensing_fsm_register_event_cb(s_hms, ESP_WIFI_SENSING_FSM_EVENT_INACTIVE, on_motion_event, NULL));
    ESP_ERROR_CHECK(esp_wifi_sensing_fsm_control(s_hms, ESP_WIFI_SENSING_FSM_CTRL_START, NULL));

    esp_radar_config_t radar_cfg = {0};
    ESP_ERROR_CHECK(esp_radar_get_config(&radar_cfg));
    radar_cfg.csi_config.csi_filtered_cb = web_serial_monitor_csi_callback;
    radar_cfg.csi_config.csi_filtered_cb_ctx = NULL;

    /*
     * esp_wifi_sensing hardcodes csi_recv_interval=20 ms, which assumes a CSI
     * frame every ~20 ms. The AP in practice delivers the tracked peer at about
     * 10 frames/s, so the real gap is ~118 ms (median), 191 ms (p90), 560 ms
     * (p99). With that mismatch every window was discarded by
     * csi_window_update() on "Timestamp delta out of range" (320 clears in
     * 120 s, all of them above the strict limit), so waveform_jitter stopped
     * updating and the Web Serial motion graph held one value for seconds at a
     * time.
     *
     * csi_recv_interval only sizes handle_window/buff_size (it does not throttle
     * reception), and csi_window_update() only flushes a window when it holds at
     * least handle_window/3 frames. So the interval has to describe the frames
     * that actually arrive, and csi_handle_time has to be wide enough that
     * csi_handle_time/2 (the strict timestamp limit) clears the observed gaps.
     */
    radar_cfg.csi_config.csi_recv_interval = 100;
    radar_cfg.dec_config.csi_handle_time   = 800;

    /*
     * The outlier filter soft-updates frames whose subcarriers deviate from the
     * previous three, which adds latency to every frame that trips it. The
     * official esp-csi console_test example disables it as well
     * (outliers_threshold = 0) and relies on the window filter instead.
     */
    radar_cfg.dec_config.outliers_threshold = 0;

    ESP_ERROR_CHECK(esp_radar_change_config(&radar_cfg));

    /* esp_wifi_sensing forces esp_radar's tags to WARN, which hides every
     * window/flush diagnostic. Restore INFO so starved windows are visible. */
    esp_radar_set_log_output(true, ESP_LOG_INFO);

    ESP_LOGI(TAG,
             "default config: motion_detection_sensitivity=%.3f active_jitter_min=%.3f hold=%" PRIu32 "ms confirm=%d ping=%" PRIu32 "Hz",
             cfg.default_channel_config.sensitivity,
             cfg.default_channel_config.active_jitter_min,
             cfg.default_channel_config.active_filter_ms,
             CONFIG_ESP_WIFI_SENSING_CONFIRM_COUNT,
             cfg.ping_frequency_hz);

    sensing_start_ping();

#if CONFIG_ESP_WIFI_SENSING_HT_STIMULUS_ENABLE
    /*
     * The router ping alone is not enough to keep the graph moving. Measured on
     * an 11n AP at -60 dBm with the stimulus off, the graph froze for up to 6 s
     * at a time (35-53% of samples held one value) and only 5.3 detection
     * windows were produced per 45 s. With the default 200 KB / 100 ms burst the
     * link carries 6x more HT frames and produces 18.4 windows per 45 s.
     *
     * `SET_STIMULUS off` on the web UI turns it off at runtime.
     */
    ESP_ERROR_CHECK(ht_stimulus_start());
#endif

#if CONFIG_ESP_WIFI_SENSING_WEB_SERIAL_ENABLE
    /* Web UI also maps esp-radar train (TRAIN_START/STOP/REMOVE) and streams wander / train thresholds. */
    /* Export the same three demo channels to the browser monitor UI. */
    web_serial_monitor_peer_t serial_peers[] = {
        { .name = "AP" },
        { .name = "MAC_1" },
        { .name = "MAC_2" },
    };
    memcpy(serial_peers[0].mac, s_mac_ap, sizeof(s_mac_ap));
    memcpy(serial_peers[1].mac, CONFIG_CSI_SEND_MAC, sizeof(serial_peers[1].mac));
    memcpy(serial_peers[2].mac, CONFIG_CSI_SEND_MAC_2, sizeof(serial_peers[2].mac));
    web_serial_monitor_config_t serial_cfg = {
        .fsm = s_hms,
        .peers = serial_peers,
        .peer_num = sizeof(serial_peers) / sizeof(serial_peers[0]),
        .stream_period_ms = CONFIG_ESP_WIFI_SENSING_WEB_SERIAL_STREAM_PERIOD_MS,
    };
    web_serial_monitor_attach_sensing(&serial_cfg);
#endif
}

/*
 * The browser switched APs. Rebind the AP channel to the new BSSID,
 * relearn the baseline, then bring the router ping back on the new link.
 */
static void sensing_rebind_ap(const uint8_t *bssid)
{
    if (!s_hms || !s_sensing_started) {
        return;
    }

    if (memcmp(s_mac_ap, bssid, sizeof(s_mac_ap)) == 0) {
        /* Same AP: the channel binding is still valid, only the ping needs reviving. */
        sensing_start_ping();
#if CONFIG_ESP_WIFI_SENSING_HT_STIMULUS_ENABLE
        /* sensing_stop_ping() stops the stimulus too, and a reconnect tears the
         * association down, so without this the graph never recovers on its own
         * after a link drop. */
        ht_stimulus_start();
#endif
        return;
    }

    (void)esp_wifi_sensing_fsm_remove_channel(s_hms, s_mac_ap);
    memcpy(s_mac_ap, bssid, sizeof(s_mac_ap));
    ESP_ERROR_CHECK(esp_wifi_sensing_fsm_add_channel(s_hms, s_mac_ap));
    ESP_ERROR_CHECK(esp_wifi_sensing_fsm_control(s_hms, ESP_WIFI_SENSING_FSM_CTRL_RESET_BASELINE, NULL));

#if CONFIG_ESP_WIFI_SENSING_WEB_SERIAL_ENABLE
    /* The monitor owns a copy of the peer table, so it must follow the new BSSID
     * or every sample lookup for the AP channel fails and the motion chart freezes. */
    (void)web_serial_monitor_update_peer_mac("AP", s_mac_ap);
#endif

    sensing_start_ping();
#if CONFIG_ESP_WIFI_SENSING_HT_STIMULUS_ENABLE
    ht_stimulus_start();
#endif
    ESP_LOGI(TAG, "rebound AP channel to " MACSTR, MAC2STR(s_mac_ap));
}

/*
 * Owns all sensing bring-up so it never runs on the event-loop task stack.
 */
static void sensing_task(void *arg)
{
    (void)arg;

    while (1) {
        EventBits_t bits = xEventGroupWaitBits(s_sensing_events, SENSING_EVT_WIFI_STATE,
                                               pdFALSE, pdFALSE, portMAX_DELAY);
        if (bits == 0) {
            continue;
        }

        /*
         * Clear before doing the work: a state change arriving mid-work re-sets
         * the bit and is handled on the next iteration. Leaving it set would make
         * this wait return immediately forever and spin the task into the WDT.
         */
        xEventGroupClearBits(s_sensing_events, bits);

        /* The snapshot is copied under the manager lock, so no flag sharing is needed. */
        wifi_runtime_info_t info = {0};
        wifi_runtime_manager_get_info(&info);

#if CONFIG_ESP_WIFI_SENSING_WEB_SERIAL_ENABLE
        /* Publish the new phase so the browser can unlock its buttons. */
        web_serial_monitor_notify_wifi_state();
#endif

        switch (info.state) {
        case WIFI_RUNTIME_STATE_GOT_IP:
            if (!s_sensing_started) {
                sensing_start(info.bssid);
            } else {
                sensing_rebind_ap(info.bssid);
            }
            break;

        case WIFI_RUNTIME_STATE_CONFIGURING:
        case WIFI_RUNTIME_STATE_DISCONNECTING:
        case WIFI_RUNTIME_STATE_DISCONNECTED:
        case WIFI_RUNTIME_STATE_FAILED:
            /*
             * The AP channel is about to move, or is already gone, so the ping
             * schedule is stale. Stopping it here also keeps this (blocking) call
             * off the event-loop stack and out of the manager mutex.
             */
            sensing_stop_ping();
            break;

        default:
            break;
        }
    }
}

/*
 * Runs in the event-loop task on every phase change. Sensing is armed on GOT_IP
 * so the FSM never samples a link that has no gateway yet. Only flags and
 * notifications happen here; the heavy work is deferred to sensing_task.
 */
static void on_wifi_runtime_state(wifi_runtime_state_t state, const wifi_runtime_info_t *info, void *ctx)
{
    (void)info;
    (void)ctx;
    led_set_wifi_connected(state == WIFI_RUNTIME_STATE_CONNECTED || state == WIFI_RUNTIME_STATE_GOT_IP);

    /*
     * This runs inside the manager mutex on the event-loop task, so it must stay
     * O(1): no sensing calls, no shared flags. The sensing task reads the state
     * snapshot itself once the bit is set.
     */
    sensing_request(SENSING_EVT_WIFI_STATE);
}

void app_main(void)
{
    /* Standard ESP-IDF bring-up, then hand Wi-Fi ownership to the runtime manager. */
    ESP_ERROR_CHECK(nvs_flash_init());
    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    ESP_ERROR_CHECK(led_init());
    led_set_wifi_connected(false);

#if CONFIG_ESP_WIFI_SENSING_WEB_SERIAL_ENABLE
    /*
     * Start the console transport before Wi-Fi so BOOTING and CONNECTING are
     * already visible in the browser. Sensing is attached later from GOT_IP.
     */
    web_serial_monitor_init();
#endif

    /*
     * Sensing bring-up runs on its own task. The event-loop task has a 2 KiB
     * stack and cannot absorb the espnow/FSM call chain.
     */
    s_sensing_events = xEventGroupCreate();
    ESP_ERROR_CHECK(s_sensing_events ? ESP_OK : ESP_ERR_NO_MEM);
    BaseType_t sensing_ok = xTaskCreate(sensing_task,
                                        "sensing",
                                        6144,
                                        NULL,
                                        5,
                                        NULL);
    ESP_ERROR_CHECK(sensing_ok == pdPASS ? ESP_OK : ESP_ERR_NO_MEM);

    /*
     * The manager is the only owner of connect/reconnect for the whole runtime.
     * Sensing is armed from the GOT_IP callback, never before the link is usable.
     */
    wifi_runtime_manager_set_state_callback(on_wifi_runtime_state, NULL);
    esp_err_t connect_err = wifi_runtime_manager_init();
    if (connect_err != ESP_OK) {
        wifi_runtime_info_t boot_info = {0};
        wifi_runtime_manager_get_info(&boot_info);
        ESP_LOGE(TAG, "initial connect failed: %s (%s)",
                 esp_err_to_name(connect_err), wifi_runtime_reason_name(boot_info.reason));
    }

    /*
     * The SSID can be changed from the browser at any time, so booting against a
     * network that is merely out of range is an ordinary state rather than a
     * fault. Keep backing off and retrying until the saved network answers
     * again: without this the only cure for a stale SSID would be a reflash.
     */
    uint32_t retry_backoff_ms = 5000;
    while (connect_err != ESP_OK) {
        vTaskDelay(pdMS_TO_TICKS(retry_backoff_ms));

        wifi_runtime_info_t retry_info = {0};
        wifi_runtime_manager_get_info(&retry_info);
        if (retry_info.has_ip) {
            break;
        }

        connect_err = wifi_runtime_manager_retry_connect();
        if (connect_err != ESP_OK) {
            retry_backoff_ms = (retry_backoff_ms < 30000) ? retry_backoff_ms * 2 : 30000;
            ESP_LOGW(TAG, "connect retry failed: %s, next attempt in %u ms",
                     esp_err_to_name(connect_err), (unsigned)retry_backoff_ms);
        }
    }

    while (1) {
        vTaskDelay(pdMS_TO_TICKS(1000));
    }
}
