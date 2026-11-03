/*
 * SPDX-FileCopyrightText: 2026 Espressif Systems (Shanghai) CO LTD
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <errno.h>
#include <inttypes.h>
#include <stdio.h>
#include <string.h>

#include <sys/poll.h>
#include <sys/socket.h>

#include <lwip/sockets.h>

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_err.h"
#include "esp_log.h"
#include "esp_netif.h"
#include "esp_random.h"
#include "esp_timer.h"

#include "dns_stimulus.h"

/* Task lifecycle follows tcp_stimulus.c (mux handshake around stop/start), not
 * ht_stimulus.c, whose start-after-stop early-return is a documented defect in
 * the campaign's measurement_audit.md (§A7). */
#define DNS_STIMULUS_TASK_STACK   4096
#define DNS_STIMULUS_TASK_PRIO    4
#define DNS_STIMULUS_INTERVAL_DEFAULT 100
#define DNS_STIMULUS_INTERVAL_MIN     10   /* 100 queries/s screening ceiling (§6.2) */
#define DNS_STIMULUS_INTERVAL_MAX  5000
#define DNS_STIMULUS_TIMEOUT_DEFAULT  500
#define DNS_STIMULUS_TIMEOUT_MAX     5000
#define DNS_STIMULUS_RETRY_MS         200  /* backoff while DHCP has not given a DNS server */
#define DNS_STIMULUS_RESP_MAX        1024  /* a gateway answer for one A record is ~90-130 B */

static portMUX_TYPE s_mux = portMUX_INITIALIZER_UNLOCKED;
static volatile bool     s_running;
static volatile bool     s_stop_requested;
static volatile uint32_t s_interval_ms = DNS_STIMULUS_INTERVAL_DEFAULT;
static volatile uint32_t s_timeout_ms  = DNS_STIMULUS_TIMEOUT_DEFAULT;

static dns_stimulus_stats_t s_stats;

static const char *TAG = "dns_stimulus";

bool dns_stimulus_server_ip(char *out, size_t out_len)
{
    esp_netif_t *sta = esp_netif_get_handle_from_ifkey("WIFI_STA_DEF");
    if (!sta || !out || out_len == 0) {
        return false;
    }
    esp_netif_dns_info_t dns = {0};
    if (esp_netif_get_dns_info(sta, ESP_NETIF_DNS_MAIN, &dns) != ESP_OK ||
        !IP_IS_V4(&dns.ip) || ip4_addr_get_u32(&dns.ip.u_addr.ip4) == 0) {
        if (esp_netif_get_dns_info(sta, ESP_NETIF_DNS_BACKUP, &dns) != ESP_OK ||
            !IP_IS_V4(&dns.ip) || ip4_addr_get_u32(&dns.ip.u_addr.ip4) == 0) {
            return false;
        }
    }
    snprintf(out, out_len, IPSTR, IP2STR(&dns.ip.u_addr.ip4));
    return true;
}

static bool dns_server_sockaddr(struct sockaddr_in *sa)
{
    esp_netif_t *sta = esp_netif_get_handle_from_ifkey("WIFI_STA_DEF");
    if (!sta) {
        return false;
    }
    esp_netif_dns_info_t dns = {0};
    if (esp_netif_get_dns_info(sta, ESP_NETIF_DNS_MAIN, &dns) != ESP_OK ||
        !IP_IS_V4(&dns.ip) || ip4_addr_get_u32(&dns.ip.u_addr.ip4) == 0) {
        if (esp_netif_get_dns_info(sta, ESP_NETIF_DNS_BACKUP, &dns) != ESP_OK ||
            !IP_IS_V4(&dns.ip) || ip4_addr_get_u32(&dns.ip.u_addr.ip4) == 0) {
            return false;
        }
    }
    memset(sa, 0, sizeof(*sa));
    sa->sin_family = AF_INET;
    sa->sin_addr.s_addr = ip4_addr_get_u32(&dns.ip.u_addr.ip4);
    sa->sin_port = htons(53); /* DNS_SERVER_PORT, lwip/prot/dns.h */
    return true;
}

/* RFC1035 §4.1.1/§4.1.2 standard query, hand-built so every transaction is
 * counted, timed and byte-sized on its own (getaddrinfo would hide all three
 * and cache). Layout mirrors struct dns_hdr in lwip/prot/dns.h. */
static bool dns_make_query(uint8_t *buf, size_t cap, uint16_t id, size_t *out_len)
{
    const char *name = DNS_STIMULUS_QUERY_NAME;
    size_t name_len = strlen(name);
    /* 12 header + name with length prefixes + terminating 0 + qtype + qclass */
    size_t need = 12 + name_len + 2 + 4;
    if (cap < need) {
        return false;
    }
    memset(buf, 0, need);
    buf[0] = (uint8_t)(id >> 8);
    buf[1] = (uint8_t)(id & 0xff);
    buf[2] = 0x01; /* flags1: recursion desired */
    buf[3] = 0x00; /* flags2: opcode QUERY, no response bits set in a query */
    buf[5] = 0x01; /* QDCOUNT = 1 */
    size_t o = 12;
    const char *p = name;
    while (*p) {
        const char *dot = strchr(p, '.');
        size_t lbl = dot ? (size_t)(dot - p) : strlen(p);
        if (lbl > 63) {
            return false;
        }
        buf[o++] = (uint8_t)lbl;
        memcpy(buf + o, p, lbl);
        o += lbl;
        p += lbl + (dot ? 1 : 0);
    }
    buf[o++] = 0x00;          /* label terminator */
    buf[o++] = 0x00; buf[o++] = 0x01; /* QTYPE  = A (DNS_RRTYPE_A) */
    buf[o++] = 0x00; buf[o++] = 0x01; /* QCLASS = IN (DNS_RRCLASS_IN) */
    *out_len = o;
    return true;
}

/* Validate what came back: response bit, our transaction id, NOERROR, at least
 * one answer, and the source is the server we asked (§6.2 "validate DNS
 * response"). Anything else counts responses_bad, never responses_ok. */
static bool dns_validate_response(const uint8_t *resp, size_t len, uint16_t id)
{
    if (len < 12) {
        return false;
    }
    uint16_t rid = ((uint16_t)resp[0] << 8) | resp[1];
    bool qr = (resp[2] & 0x80) != 0;
    uint8_t opcode = (resp[2] >> 3) & 0x0f;
    uint8_t rcode = resp[3] & 0x0f;
    uint16_t ancount = ((uint16_t)resp[6] << 8) | resp[7];
    return rid == id && qr && opcode == 0 && rcode == 0 && ancount >= 1;
}

static void dns_round(void)
{
    struct sockaddr_in sa;
    if (!dns_server_sockaddr(&sa)) {
        s_stats.errors++;
        vTaskDelay(pdMS_TO_TICKS(DNS_STIMULUS_RETRY_MS));
        return;
    }

    uint8_t query[128];
    size_t qlen = 0;
    uint16_t id = (uint16_t)(esp_random() & 0xffff);
    if (!dns_make_query(query, sizeof(query), id, &qlen)) {
        s_stats.errors++;
        return;
    }

    int s = socket(AF_INET, SOCK_DGRAM, 0);
    if (s < 0) {
        s_stats.errors++;
        return;
    }
    int64_t t0 = esp_timer_get_time();
    ssize_t sent = sendto(s, query, qlen, 0, (struct sockaddr *)&sa, sizeof(sa));
    if (sent != (ssize_t)qlen) {
        s_stats.errors++;
        close(s);
        return;
    }
    s_stats.queries_sent++;

    int32_t elapsed_ms = (int32_t)((esp_timer_get_time() - t0) / 1000);
    int32_t remaining_ms = (int32_t)s_timeout_ms - elapsed_ms;
    if (remaining_ms < 0) {
        remaining_ms = 0;
    }
    struct pollfd pfd = { .fd = s, .events = POLLIN, .revents = 0 };
    int pr = poll(&pfd, 1, remaining_ms);
    if (pr == 0) {
        s_stats.timeouts++;
        close(s);
        return;
    }
    if (pr < 0) {
        s_stats.errors++;
        close(s);
        return;
    }

    uint8_t resp[DNS_STIMULUS_RESP_MAX];
    struct sockaddr_in from;
    socklen_t flen = sizeof(from);
    ssize_t n = recvfrom(s, resp, sizeof(resp), 0, (struct sockaddr *)&from, &flen);
    uint32_t lat_us = (uint32_t)(esp_timer_get_time() - t0);
    if (n >= 12) {
        s_stats.bytes_received += (uint64_t)n;
    }
    bool from_server = (from.sin_addr.s_addr == sa.sin_addr.s_addr);
    if (n >= 12 && from_server && dns_validate_response(resp, (size_t)n, id)) {
        s_stats.responses_ok++;
        s_stats.latency_us_last = lat_us;
        if (s_stats.latency_us_min == 0 || lat_us < s_stats.latency_us_min) {
            s_stats.latency_us_min = lat_us;
        }
        if (lat_us > s_stats.latency_us_max) {
            s_stats.latency_us_max = lat_us;
        }
    } else {
        s_stats.responses_bad++;
    }
    close(s);
}

static void dns_stimulus_task(void *arg)
{
    (void)arg;
    char server[16] = "?";
    (void)dns_stimulus_server_ip(server, sizeof(server));
    ESP_LOGI(TAG, "DNS stimulus started (interval=%" PRIu32 " ms, timeout=%" PRIu32 " ms, server=%s, name=%s)",
             (uint32_t)s_interval_ms, (uint32_t)s_timeout_ms, server, DNS_STIMULUS_QUERY_NAME);

    for (;;) {
        while (!s_stop_requested) {
            s_stats.rounds++;
            dns_round();
            /* Short slices so a stop is honoured quickly; real granularity of
             * interval_ms is portTICK_PERIOD_MS (same note as tcp_stimulus.c).
             * With CONFIG_FREERTOS_HZ=100 a 5 ms slice truncates to 0 ticks and
             * vTaskDelay(0) never sleeps - this collapsed pacing to ~37 qps at
             * interval=100 in the first C2 preflight. Clamp to >=1 tick and
             * debit the actual slept time. */
            uint32_t remaining = s_interval_ms;
            while (remaining > 0 && !s_stop_requested) {
                uint32_t slice = (remaining > 10) ? 10 : remaining;
                TickType_t ticks = pdMS_TO_TICKS(slice);
                if (ticks == 0) {
                    ticks = 1;
                }
                vTaskDelay(ticks);
                remaining -= (uint32_t)ticks * (uint32_t)portTICK_PERIOD_MS;
            }
        }

        portENTER_CRITICAL(&s_mux);
        if (s_stop_requested) {
            s_running = false;
        }
        portEXIT_CRITICAL(&s_mux);
        if (!s_running) {
            break;
        }
    }

    ESP_LOGI(TAG, "DNS stimulus stopped (queries=%" PRIu32 " ok=%" PRIu32 " bad=%" PRIu32 " timeouts=%" PRIu32 " errors=%" PRIu32 ")",
             s_stats.queries_sent, s_stats.responses_ok, s_stats.responses_bad,
             s_stats.timeouts, s_stats.errors);
    vTaskDelete(NULL);
}

esp_err_t dns_stimulus_start(void)
{
    portENTER_CRITICAL(&s_mux);
    if (s_running) {
        /* Cancel a pending stop instead of skipping the restart, so a
         * stop-then-start re-apply keeps the existing task serving. */
        s_stop_requested = false;
        portEXIT_CRITICAL(&s_mux);
        return ESP_OK;
    }
    s_running = true;
    s_stop_requested = false;
    portEXIT_CRITICAL(&s_mux);

    BaseType_t ok = xTaskCreate(dns_stimulus_task, "dns_stim",
                                DNS_STIMULUS_TASK_STACK, NULL,
                                DNS_STIMULUS_TASK_PRIO, NULL);
    if (ok != pdPASS) {
        portENTER_CRITICAL(&s_mux);
        s_running = false;
        portEXIT_CRITICAL(&s_mux);
        ESP_LOGE(TAG, "task create failed");
        return ESP_ERR_NO_MEM;
    }
    return ESP_OK;
}

void dns_stimulus_stop(void)
{
    portENTER_CRITICAL(&s_mux);
    if (s_running) {
        s_stop_requested = true;
    }
    portEXIT_CRITICAL(&s_mux);
}

bool dns_stimulus_is_running(void)
{
    return s_running;
}

esp_err_t dns_stimulus_set_config(const dns_stimulus_config_t *cfg)
{
    if (!cfg) {
        return ESP_ERR_INVALID_ARG;
    }
    /* Validate everything before touching anything: a rejected command must not
     * disturb a running stimulus. */
    if (cfg->interval_ms < DNS_STIMULUS_INTERVAL_MIN ||
        cfg->interval_ms > DNS_STIMULUS_INTERVAL_MAX) {
        return ESP_ERR_INVALID_ARG;
    }
    if (cfg->timeout_ms < 1 || cfg->timeout_ms > DNS_STIMULUS_TIMEOUT_MAX) {
        return ESP_ERR_INVALID_ARG;
    }
    s_interval_ms = cfg->interval_ms;
    s_timeout_ms = cfg->timeout_ms;
    return ESP_OK;
}

esp_err_t dns_stimulus_get_config(dns_stimulus_config_t *cfg)
{
    if (!cfg) {
        return ESP_ERR_INVALID_ARG;
    }
    cfg->interval_ms = s_interval_ms;
    cfg->timeout_ms = s_timeout_ms;
    return ESP_OK;
}

esp_err_t dns_stimulus_get_stats(dns_stimulus_stats_t *stats)
{
    if (!stats) {
        return ESP_ERR_INVALID_ARG;
    }
    *stats = s_stats;
    return ESP_OK;
}

void dns_stimulus_reset_stats(void)
{
    memset(&s_stats, 0, sizeof(s_stats));
}
