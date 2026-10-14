/*
 * Uplink watchdog: restart the unit when the internet path dies for good.
 *
 * The symptom this exists for was measured, not guessed. After about 77 minutes
 * of uptime the board kept its Wi-Fi association and its IP, the router stopped
 * answering, and every MQTT reconnect came back "Failed to open a new
 * connection". The normal reconnect loop never recovered from that, while a
 * power cycle always did, within a couple of seconds.
 *
 * Two things keep this from becoming a reboot loop, which would be far worse
 * than the fault it fixes:
 *
 *  - Only a board that is associated and holds an IP is judged, so a reboot is
 *    never triggered simply because the access point is off.
 *  - Restarts are budgeted in RTC memory and the budget is only refunded after
 *    a sustained healthy stretch. If restarts stop helping, the watchdog stops
 *    restarting and the unit simply keeps retrying, which is no worse than the
 *    behaviour before this existed.
 */
#include "uplink_watchdog.h"

#include "mqtt_publisher.h"
#include "wifi_runtime_manager.h"

#include <string.h>

/*
 * How many times to re-associate with the access point before spending a full
 * restart on the same fault. Re-associating costs a second or two; a restart
 * costs the whole boot sequence, so it is the fallback, not the first move.
 */
#define UPLINK_WIFI_RECONNECT_TRIES 3

#include "esp_log.h"
#include "esp_netif.h"
#include "esp_attr.h"
#include "esp_system.h"
#include "esp_timer.h"
#include "esp_wifi.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "lwip/netdb.h"
#include "nvs.h"
#include "lwip/sockets.h"

#include <inttypes.h>
#include <stdlib.h>
#include <stdio.h>

static const char *TAG = "uplink_watchdog";

/*
 * The restart budget lives in NVS, not in RTC memory.
 *
 * RTC_DATA_ATTR was tried first and measured: on this board it came back zero
 * after esp_restart(), so the budget never accumulated and a unit parked behind
 * a black-holed network rebooted forever. NVS is one flash write on an event
 * that is already minutes apart, so it costs nothing and it is dependable.
 */
#define UPLINK_NVS_NAMESPACE "sysstat"
#define UPLINK_NVS_KEY       "uplink_reboots"

static uint8_t s_reboot_count;
static int s_reconnect_tries = 0;

static uint8_t reboot_count_load(void)
{
    nvs_handle_t h;
    if (nvs_open(UPLINK_NVS_NAMESPACE, NVS_READWRITE, &h) != ESP_OK) {
        return 0;
    }
    uint8_t v = 0;
    if (nvs_get_u8(h, UPLINK_NVS_KEY, &v) != ESP_OK) {
        v = 0;
    }
    nvs_close(h);
    return v;
}

static void reboot_count_store(uint8_t v)
{
    nvs_handle_t h;
    if (nvs_open(UPLINK_NVS_NAMESPACE, NVS_READWRITE, &h) != ESP_OK) {
        ESP_LOGW(TAG, "cannot open %s to record the restart", UPLINK_NVS_NAMESPACE);
        return;
    }
    esp_err_t err = nvs_set_u8(h, UPLINK_NVS_KEY, v);
    if (err == ESP_OK) {
        err = nvs_commit(h);
    }
    nvs_close(h);
    if (err != ESP_OK) {
        ESP_LOGW(TAG, "restart not recorded: %s", esp_err_to_name(err));
    }
}

static volatile bool s_failing;
static volatile uint32_t s_failure_seconds;

/* Copied from the caller so the task probes whatever broker is configured,
 * including one that was set at runtime through HMSCMD MQTT_CONFIG. */
static char s_host[128];
static uint16_t s_port;

/**
 * @brief Try to open a TCP connection to the broker.
 *
 * A real connect is used rather than a ping because that is the operation that
 * was failing, and because ICMP is frequently dropped on the way out.
 */
static bool probe_tcp(const char *host, uint16_t port)
{
    char service[8];
    snprintf(service, sizeof(service), "%u", (unsigned)port);

    struct addrinfo hints = {
        .ai_family = AF_UNSPEC,
        .ai_socktype = SOCK_STREAM,
    };
    struct addrinfo *res = NULL;
    if (getaddrinfo(host, service, &hints, &res) != 0 || !res) {
        return false;
    }

    bool ok = false;
    for (struct addrinfo *ai = res; ai && !ok; ai = ai->ai_next) {
        int fd = socket(ai->ai_family, ai->ai_socktype, ai->ai_protocol);
        if (fd < 0) {
            continue;
        }
        struct timeval tv = {
            .tv_sec = CONFIG_ESP_WIFI_SENSING_UPLINK_PROBE_TIMEOUT_S,
            .tv_usec = 0,
        };
        setsockopt(fd, SOL_SOCKET, SO_SNDTIMEO, &tv, sizeof(tv));
        setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv));
        if (connect(fd, ai->ai_addr, ai->ai_addrlen) == 0) {
            ok = true;
        }
        close(fd);
    }
    freeaddrinfo(res);
    return ok;
}

/** @brief True when the station is associated and has a routable address. */
static bool link_is_up(void)
{
    wifi_ap_record_t ap;
    if (esp_wifi_sta_get_ap_info(&ap) != ESP_OK) {
        return false;
    }
    esp_netif_ip_info_t ip;
    esp_netif_t *netif = esp_netif_get_default_netif();
    if (!netif || esp_netif_get_ip_info(netif, &ip) != ESP_OK) {
        return false;
    }
    return ip.ip.addr != 0;
}

/**
 * @brief Whether the access point this unit was told to use is still nearby.
 *
 * This is what separates "the router is gone" from "this board fell off the
 * router". Both look identical from the inside: no association, no address. The
 * difference was worth chasing because the observed failure was the second one.
 * The board was dropped with reason INACTIVITY while the access point was still
 * up and still in range, and the reconnect loop never picked it back up. A
 * restart did.
 *
 * A restart cannot help when the access point is genuinely absent, so that case
 * must be told apart or the watchdog would reboot forever against a router
 * somebody switched off.
 */
static bool access_point_is_in_range(void)
{
    wifi_scan_config_t scan = {
        .show_hidden = false,
    };
    if (esp_wifi_scan_start(&scan, true) != ESP_OK) {
        return false;
    }
    uint16_t found = 0;
    esp_wifi_scan_get_ap_num(&found);

    /* Prefer the network this unit was actually configured for. */
    wifi_runtime_info_t info;
    wifi_runtime_manager_get_info(&info);
    char want[33] = {0};
    if (info.ssid_len) {
        memcpy(want, info.ssid, info.ssid_len);
    }

    bool present = false;
    if (found > 0) {
        wifi_ap_record_t *records = calloc(found, sizeof(wifi_ap_record_t));
        if (records) {
            uint16_t got = found;
            if (esp_wifi_scan_get_ap_records(&got, records) == ESP_OK) {
                for (uint16_t i = 0; i < got && !present; i++) {
                    if (want[0] && strcmp((const char *)records[i].ssid, want) == 0) {
                        present = true;
                    }
                }
            }
            free(records);
        }
        if (!present && !want[0]) {
            /* No SSID on record yet, so any network means the area is fine. */
            present = true;
        }
    }
    esp_wifi_scan_stop();
    return present;
}

static void uplink_watchdog_task(void *arg)
{
    (void)arg;
    const uint32_t period_ms = CONFIG_ESP_WIFI_SENSING_UPLINK_PROBE_PERIOD_MS;
    const uint32_t fail_after_s = CONFIG_ESP_WIFI_SENSING_UPLINK_FAIL_AFTER_S;
    const uint32_t healthy_for_s = CONFIG_ESP_WIFI_SENSING_UPLINK_HEALTHY_FOR_S;

    uint32_t failing_s = 0;
    uint32_t healthy_s = 0;
    bool warned = false;
    uint32_t link_down_reports = 0;
    uint32_t reports = 0;
    int64_t last_us = esp_timer_get_time();

    while (true) {
        vTaskDelay(pdMS_TO_TICKS(period_ms));

        /*
         * Every accounting step uses real elapsed time, never the nominal
         * period. A probe against a black hole takes far longer than the
         * configured interval, so counting the nominal period made the
         * watchdog run in slow motion exactly when the link was worst, which is
         * the opposite of what it is for.
         */
        int64_t now_us = esp_timer_get_time();
        /* esp_timer_get_time() counts microseconds, so a second is 1e6 of them. */
        uint32_t elapsed_s = (uint32_t)((now_us - last_us) / 1000000);
        if (elapsed_s == 0) {
            elapsed_s = 1;   /* never report a zero step */
        }
        last_us = now_us;

if (!link_is_up()) {
            healthy_s = 0;
            if (++link_down_reports % 10 == 1) {
                ESP_LOGW(TAG, "station has no address (report %u), scanning for the access point",
                         link_down_reports);
            }

            /*
             * The counter is only cleared once the access point is genuinely
             * gone. Clearing it here, before deciding which case this is, meant
             * the timer was reset on every pass and could never reach the
             * threshold, so the restart below was unreachable in exactly the
             * situation it exists for.
             */
            if (!access_point_is_in_range()) {
                failing_s = 0;
                s_failing = false;
                s_failure_seconds = 0;
                ESP_LOGD(TAG, "access point not in range, leaving the reconnect loop to it");
                continue;
            }
            ESP_LOGW(TAG, "access point is in range but this board has no address");
            failing_s += elapsed_s;
            s_failing = true;
            s_failure_seconds = failing_s;
            if (failing_s < fail_after_s) {
                continue;
            }
            /*
             * The access point is right there and this board is simply not
             * associated with it. That is a radio problem, not a fault anywhere
             * else on the unit, and re-associating fixes it in a second or two.
             *
             * Restarting the whole board takes far longer and throws away every
             * bit of state just to repeat a step the Wi-Fi driver already knows
             * how to do. So the cheap recovery goes first, and a restart is only
             * spent once reconnecting has itself stopped helping.
             */
            if (++s_reconnect_tries <= UPLINK_WIFI_RECONNECT_TRIES) {
                ESP_LOGW(TAG, "unassociated %" PRIu32 " s, re-associating with the "
                              "access point (try %d of %d)",
                         failing_s, s_reconnect_tries, UPLINK_WIFI_RECONNECT_TRIES);
                esp_err_t err = wifi_runtime_manager_reconnect();
                ESP_LOGW(TAG, "re-associate returned %s", esp_err_to_name(err));
                failing_s = 0;
                continue;
            }
            ESP_LOGW(TAG, "re-associating did not help, falling back to a restart");
            s_reconnect_tries = 0;
            if (s_reboot_count >= CONFIG_ESP_WIFI_SENSING_UPLINK_MAX_REBOOTS) {
                ESP_LOGW(TAG, "unassociated %" PRIu32 " s with the access point in range, "
                              "%u restarts already tried; not restarting again",
                         failing_s, s_reboot_count);
                failing_s = 0;
                continue;
            }
            ESP_LOGE(TAG, "unassociated %" PRIu32 " s although the access point is in "
                          "range, restarting (attempt %u of %d)",
                     failing_s, s_reboot_count + 1,
                     CONFIG_ESP_WIFI_SENSING_UPLINK_MAX_REBOOTS);
            s_reconnect_tries = 0;
            s_reboot_count++;
            reboot_count_store(s_reboot_count);
            fflush(stdout);
            vTaskDelay(pdMS_TO_TICKS(100));
            esp_restart();
            continue;
        }
        s_reconnect_tries = 0;

        /*
         * The endpoint is re-read each cycle so a broker changed at runtime with
         * HMSCMD MQTT_CONFIG is watched too, not just the built-in default.
         */
        mqtt_settings_t cfg;
        if (mqtt_publisher_get_settings(&cfg) == ESP_OK && cfg.host[0]) {
            snprintf(s_host, sizeof(s_host), "%s", cfg.host);
            s_port = (uint16_t)cfg.port;
        }

        bool reachable = probe_tcp(s_host, s_port);
        if (++reports % 5 == 0) {
            ESP_LOGI(TAG, "probe %u of %s:%u -> %s (failing %" PRIu32 " s)",
                     reports, s_host, s_port,
                     reachable ? "reachable" : "unreachable", failing_s);
        }

        if (reachable) {
            if (failing_s > 0) {
                ESP_LOGI(TAG, "uplink recovered after %" PRIu32 " s", failing_s);
            }
            failing_s = 0;
            s_failing = false;
            s_failure_seconds = 0;
            warned = false;

            healthy_s += elapsed_s;
            if (healthy_s >= healthy_for_s && s_reboot_count > 0) {
                /* The path held up long enough to refund the restart budget. */
                ESP_LOGI(TAG, "uplink stable for %" PRIu32 " s, clearing restart budget", healthy_s);
                s_reboot_count = 0;
                reboot_count_store(0);
            }
            continue;
        }

        failing_s += elapsed_s;
        s_failing = true;
        s_failure_seconds = failing_s;

        if (!warned) {
            ESP_LOGW(TAG, "broker unreachable although Wi-Fi is up; watching");
            warned = true;
        }
        if (failing_s < fail_after_s) {
            continue;
        }

        if (s_reboot_count >= CONFIG_ESP_WIFI_SENSING_UPLINK_MAX_REBOOTS) {
            /*
             * Restarting has already been tried and did not help, so the fault
             * is upstream of this board. Keep retrying quietly instead.
             */
            ESP_LOGW(TAG, "uplink down %" PRIu32 " s and %u restarts already tried; not restarting again",
                     failing_s, s_reboot_count);
            failing_s = 0;   /* re-arm so the warning is not printed every cycle */
            continue;
        }

        ESP_LOGE(TAG, "uplink down %" PRIu32 " s, restarting (attempt %u of %d)",
                 failing_s, s_reboot_count + 1, CONFIG_ESP_WIFI_SENSING_UPLINK_MAX_REBOOTS);
        s_reboot_count++;
        reboot_count_store(s_reboot_count);
        fflush(stdout);
        vTaskDelay(pdMS_TO_TICKS(100));
        esp_restart();
    }
}

void uplink_watchdog_start(const char *host, uint16_t port)
{
    if (!CONFIG_ESP_WIFI_SENSING_UPLINK_WATCHDOG_ENABLE) {
        return;
    }
    snprintf(s_host, sizeof(s_host), "%s",
             (host && *host) ? host : CONFIG_ESP_WIFI_SENSING_MQTT_BROKER);
    s_port = port ? port : CONFIG_ESP_WIFI_SENSING_MQTT_PORT;
    s_reboot_count = reboot_count_load();
    if (xTaskCreate(uplink_watchdog_task, "uplink_watchdog", 4096, NULL, 2, NULL) != pdPASS) {
        ESP_LOGW(TAG, "could not start, continuing without it");
        return;
    }
    ESP_LOGI(TAG, "watching the path to %s:%u every %d s, restart after %d s, budget %d, %u already used",
             s_host, s_port,
             CONFIG_ESP_WIFI_SENSING_UPLINK_PROBE_PERIOD_MS / 1000,
             CONFIG_ESP_WIFI_SENSING_UPLINK_FAIL_AFTER_S,
             CONFIG_ESP_WIFI_SENSING_UPLINK_MAX_REBOOTS, s_reboot_count);
}

bool uplink_watchdog_is_failing(void)
{
    return s_failing;
}

uint32_t uplink_watchdog_failure_seconds(void)
{
    return s_failure_seconds;
}

uint8_t uplink_watchdog_reboot_count(void)
{
    return s_reboot_count;
}