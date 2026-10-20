/*
 * SPDX-FileCopyrightText: 2026 Espressif Systems (Shanghai) CO LTD
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"
#include "esp_http_client.h"

#include "ht_stimulus.h"

#if CONFIG_ESP_WIFI_SENSING_HT_STIMULUS_ENABLE
#define HT_STIMULUS_URL_DEFAULT    CONFIG_ESP_WIFI_SENSING_HT_STIMULUS_URL
#define HT_STIMULUS_BURST_DEFAULT  CONFIG_ESP_WIFI_SENSING_HT_STIMULUS_BURST
#define HT_STIMULUS_PAUSE_DEFAULT  CONFIG_ESP_WIFI_SENSING_HT_STIMULUS_PAUSE_MS
#define HT_STIMULUS_RETRY_DEFAULT  CONFIG_ESP_WIFI_SENSING_HT_STIMULUS_RETRY_MS
#else
/* The Kconfig options below ENABLE disappear when the feature is off, so keep
 * the same bounds as literals and the module stays buildable either way. */
#define HT_STIMULUS_URL_DEFAULT    "http://speed.cloudflare.com/__down?bytes=200000"
#define HT_STIMULUS_BURST_DEFAULT  500000
#define HT_STIMULUS_PAUSE_DEFAULT  1000
#define HT_STIMULUS_RETRY_DEFAULT  1000
#endif

/* Same envelope as the Kconfig ranges, enforced again at runtime because the
 * values now arrive over the serial command channel instead of Kconfig. */
#define HT_STIMULUS_BURST_MIN      100000
#define HT_STIMULUS_BURST_MAX      20000000
#define HT_STIMULUS_PAUSE_MAX      5000

#define HT_STIMULUS_READ_CHUNK     4096
#define HT_STIMULUS_TASK_STACK     6144
#define HT_STIMULUS_TASK_PRIO      3
#define HT_STIMULUS_TIMEOUT_MS     15000
#define HT_STIMULUS_URL_LEN        192

/* Read by the task, written by ht_stimulus_set_config(). Kept volatile because
 * the command handler and the stimulus task run in different tasks. */
static volatile bool     s_running;
static volatile bool     s_stop_requested;
/* The requested state, which is not the same as s_running: a stop only takes
 * effect once the task leaves its current burst or pause, so reading the state
 * straight after a stop would briefly claim the stimulus is still on. */
static volatile bool     s_enabled;
static volatile uint32_t s_burst_bytes  = HT_STIMULUS_BURST_DEFAULT;
static volatile uint32_t s_pause_ms     = HT_STIMULUS_PAUSE_DEFAULT;

static const char *TAG = "ht_stimulus";

/*
 * The endpoint must be asked for the same number of bytes the burst will read:
 * requesting more only makes the ESP close mid-transfer and reset the TCP
 * connection while data is still in flight. Everything after '?' is rebuilt so
 * the two can never drift apart when the burst is retuned at runtime.
 */
static void ht_stimulus_build_url(char *out, size_t out_len, uint32_t burst_bytes)
{
    const char *base = HT_STIMULUS_URL_DEFAULT;
    const char *query = strchr(base, '?');
    size_t prefix_len = query ? (size_t)(query - base) : strlen(base);

    snprintf(out, out_len, "%.*s?bytes=%" PRIu32,
             (int)prefix_len, base, burst_bytes);
}

#if CONFIG_ESP_WIFI_SENSING_HT_STIMULUS_ENABLE

static void ht_stimulus_task(void *arg)
{
    (void)arg;

    uint8_t *buf = malloc(HT_STIMULUS_READ_CHUNK);
    if (!buf) {
        ESP_LOGE(TAG, "no memory for read buffer");
        s_running = false;
        vTaskDelete(NULL);
        return;
    }

    ESP_LOGI(TAG, "HT stimulus started (burst=%" PRIu32 " B, pause=%" PRIu32 " ms)",
             (uint32_t)s_burst_bytes, (uint32_t)s_pause_ms);

    while (!s_stop_requested) {
        /* Re-read every cycle so SET_STIMULUS applies without a restart. */
        const uint32_t burst_bytes = s_burst_bytes;
        const uint32_t pause_ms = s_pause_ms;

        char url[HT_STIMULUS_URL_LEN];
        ht_stimulus_build_url(url, sizeof(url), burst_bytes);

        esp_http_client_config_t cfg = {
            .url = url,
            .method = HTTP_METHOD_GET,
            .timeout_ms = HT_STIMULUS_TIMEOUT_MS,
            .keep_alive_enable = true,
        };

        esp_http_client_handle_t client = esp_http_client_init(&cfg);
        if (!client) {
            ESP_LOGW(TAG, "client init failed, retry in %d ms", HT_STIMULUS_RETRY_DEFAULT);
            vTaskDelay(pdMS_TO_TICKS(HT_STIMULUS_RETRY_DEFAULT));
            continue;
        }

        esp_err_t err = esp_http_client_open(client, 0);
        if (err != ESP_OK) {
            ESP_LOGW(TAG, "burst open failed (%s), retry in %d ms",
                     esp_err_to_name(err), HT_STIMULUS_RETRY_DEFAULT);
            esp_http_client_cleanup(client);
            vTaskDelay(pdMS_TO_TICKS(HT_STIMULUS_RETRY_DEFAULT));
            continue;
        }

        (void)esp_http_client_fetch_headers(client);
        int status = esp_http_client_get_status_code(client);
        if (status != 200) {
            ESP_LOGW(TAG, "unexpected HTTP status %d, retry in %d ms",
                     status, HT_STIMULUS_RETRY_DEFAULT);
            esp_http_client_cleanup(client);
            vTaskDelay(pdMS_TO_TICKS(HT_STIMULUS_RETRY_DEFAULT));
            continue;
        }

        int total = 0;
        int short_read = 0;
        TickType_t read_start = xTaskGetTickCount();
        while (total < (int)burst_bytes && !s_stop_requested) {
            int n = esp_http_client_read(client, (char *)buf, HT_STIMULUS_READ_CHUNK);
            if (n <= 0) {
                short_read = n;
                break;
            }
            total += n;
        }
        uint32_t read_ms = (uint32_t)((xTaskGetTickCount() - read_start) * portTICK_PERIOD_MS);

        esp_http_client_close(client);
        esp_http_client_cleanup(client);

        /* CSI on this target only comes from HT payload frames, so a burst that
         * transfers nothing starves the radar pipeline and the motion graph
         * freezes. Keep that visible on the console instead of debug-only. */
        static uint32_t burst_ok;
        static uint32_t burst_short;
        static TickType_t last_status;
        if (total < (int)burst_bytes) {
            burst_short++;
            TickType_t now = xTaskGetTickCount();
            if (burst_short <= 5 || (now - last_status) >= pdMS_TO_TICKS(4000)) {
                last_status = now;
                ESP_LOGW(TAG, "burst short #%lu: %d/%" PRIu32 " bytes, read_ret=%d in %" PRIu32 " ms",
                         (unsigned long)burst_short, total, burst_bytes, short_read, read_ms);
            }
        } else {
            burst_ok++;
            ESP_LOGI(TAG, "burst ok #%lu: %d bytes in %" PRIu32 " ms (short_total=%lu)",
                     (unsigned long)burst_ok, total, read_ms, (unsigned long)burst_short);
        }
        ESP_LOGD(TAG, "burst done, %d bytes", total);

        /* Quiet gap so the AP goes idle again and the FSM has a stable window
         * to rebuild its baseline between bursts. */
        vTaskDelay(pdMS_TO_TICKS(pause_ms));
    }

    free(buf);
    ESP_LOGI(TAG, "HT stimulus stopped");
    s_running = false;
    vTaskDelete(NULL);
}

esp_err_t ht_stimulus_start(void)
{
    s_enabled = true;

    if (s_running) {
        return ESP_OK;
    }

    s_stop_requested = false;
    s_running = true;

    BaseType_t ok = xTaskCreate(ht_stimulus_task, "ht_stimulus",
                                HT_STIMULUS_TASK_STACK, NULL,
                                HT_STIMULUS_TASK_PRIO, NULL);
    if (ok != pdPASS) {
        s_running = false;
        ESP_LOGE(TAG, "task create failed");
        return ESP_ERR_NO_MEM;
    }
    return ESP_OK;
}

void ht_stimulus_stop(void)
{
    s_enabled = false;

    if (!s_running) {
        return;
    }
    s_stop_requested = true;
}

bool ht_stimulus_is_running(void)
{
    return s_running;
}

esp_err_t ht_stimulus_set_config(const ht_stimulus_config_t *cfg)
{
    if (!cfg) {
        return ESP_ERR_INVALID_ARG;
    }

    /* Validate everything before touching anything: a rejected command must
     * leave the previous settings completely intact. */
    if (cfg->burst_bytes < HT_STIMULUS_BURST_MIN ||
        cfg->burst_bytes > HT_STIMULUS_BURST_MAX) {
        return ESP_ERR_INVALID_ARG;
    }
    if (cfg->pause_ms > HT_STIMULUS_PAUSE_MAX) {
        return ESP_ERR_INVALID_ARG;
    }

    s_burst_bytes = cfg->burst_bytes;
    s_pause_ms = cfg->pause_ms;

    if (cfg->enabled) {
        return ht_stimulus_start();
    }

    ht_stimulus_stop();
    return ESP_OK;
}

esp_err_t ht_stimulus_get_config(ht_stimulus_config_t *cfg)
{
    if (!cfg) {
        return ESP_ERR_INVALID_ARG;
    }
    cfg->enabled = s_enabled;
    cfg->burst_bytes = s_burst_bytes;
    cfg->pause_ms = s_pause_ms;
    return ESP_OK;
}

#else /* feature compiled out */

static const ht_stimulus_config_t s_stub_config = {
    .enabled = false,
    .burst_bytes = HT_STIMULUS_BURST_DEFAULT,
    .pause_ms = HT_STIMULUS_PAUSE_DEFAULT,
};

esp_err_t ht_stimulus_start(void)
{
    return ESP_ERR_NOT_SUPPORTED;
}

void ht_stimulus_stop(void)
{
}

bool ht_stimulus_is_running(void)
{
    return false;
}

esp_err_t ht_stimulus_set_config(const ht_stimulus_config_t *cfg)
{
    (void)cfg;
    return ESP_ERR_NOT_SUPPORTED;
}

esp_err_t ht_stimulus_get_config(ht_stimulus_config_t *cfg)
{
    if (!cfg) {
        return ESP_ERR_INVALID_ARG;
    }
    *cfg = s_stub_config;
    return ESP_OK;
}

#endif /* CONFIG_ESP_WIFI_SENSING_HT_STIMULUS_ENABLE */
