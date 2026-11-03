/*
 * SPDX-FileCopyrightText: 2026 Espressif Systems (Shanghai) CO LTD
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#pragma once

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "esp_err.h"

#ifdef __cplusplus
extern "C" {
#endif

/* One fixed query name for every transaction: the campaign screens pacing and
 * response size, not resolution breadth, and the mandate (§6.2) forbids
 * spraying random domains. */
#define DNS_STIMULUS_QUERY_NAME "speed.cloudflare.com"

typedef struct {
    uint32_t interval_ms;   /* gap between transactions; 10 ms == 100 qps ceiling */
    uint32_t timeout_ms;    /* receive wait per transaction */
} dns_stimulus_config_t;

typedef struct {
    uint32_t rounds;
    uint32_t queries_sent;
    uint32_t responses_ok;    /* matching id, QR set, rcode 0, >=1 answer, right source */
    uint32_t responses_bad;   /* received but mismatched or malformed */
    uint32_t timeouts;
    uint32_t errors;          /* socket/send failures and "no DNS server yet" backoffs */
    uint64_t bytes_received;
    uint32_t latency_us_last;
    uint32_t latency_us_min;  /* 0 until the first ok response */
    uint32_t latency_us_max;
} dns_stimulus_stats_t;

esp_err_t dns_stimulus_start(void);
void dns_stimulus_stop(void);
bool dns_stimulus_is_running(void);
esp_err_t dns_stimulus_set_config(const dns_stimulus_config_t *cfg);
esp_err_t dns_stimulus_get_config(dns_stimulus_config_t *cfg);
esp_err_t dns_stimulus_get_stats(dns_stimulus_stats_t *stats);
void dns_stimulus_reset_stats(void);

/* IPv4 of the DNS server the task actually queries - MAIN, else BACKUP, exactly
 * what DHCP handed the STA interface. Telemetry reports this instead of any
 * hardcoded address (mandat §6.1). Returns false when none is configured yet. */
bool dns_stimulus_server_ip(char *out, size_t out_len);

#ifdef __cplusplus
}
#endif
