/*
 * SPDX-FileCopyrightText: 2026 Espressif Systems (Shanghai) CO LTD
 *
 * SPDX-License-Identifier: Apache-2.0
 */
#pragma once

#include <stdbool.h>
#include <stdint.h>

#include "esp_err.h"

#ifdef __cplusplus
extern "C" {
#endif

/*
 * TCP gateway stimulus (the validated "A3" engine from the tcp_csi_optimization
 * campaign). It opens a small set of non-blocking TCP connections to the current
 * default gateway and closes them right away (connect -> close). Each handshake
 * makes the AP emit a full HT downlink frame, which is what the CSI pipeline on
 * this target actually decodes. This is a LAN-only stimulus: unlike the HTTP
 * Cloudflare burst it needs no WAN, and unlike the router ping (legacy frames,
 * no CSI) it produces HT payload frames.
 *
 * It is only a traffic generator: CSI acquisition, feature extraction and the
 * motion FSM are unchanged and keep using the wifi_sensing_demo pipeline.
 */

/**
 * @brief Runtime settings of the TCP gateway stimulus.
 *
 * Mirrors the A3 baseline: non-blocking, concurrency 4, 10 ms between rounds,
 * connect -> close, gateway port 80 with a fallback to port 53, 50 ms timeout.
 *
 * Resolution note for runtime tuning: with CONFIG_FREERTOS_HZ=100 the poll()
 * timeout is rounded up to whole ticks plus one (components/lwip/port/freertos/
 * sys_arch.c), so 10, 5 and 1 ms all wait ~20 ms, and interval_ms is quantised
 * to 10 ms as well. Values are accepted as requested; only multiples of the
 * 10 ms tick change behaviour.
 */
typedef struct {
    uint32_t concurrency;  /**< Outstanding connections per round (1..8). */
    uint32_t interval_ms;  /**< Quiet gap between rounds, in milliseconds (1..5000). */
    uint16_t port;         /**< Primary TCP port (A3 baseline: 80). */
    uint16_t port_alt;     /**< Fallback TCP port on failure (A3 baseline: 53). */
    uint32_t timeout_ms;   /**< poll()/connect timeout per round (0..5000; 0 = do not wait). */
} tcp_stimulus_config_t;

/**
 * @brief Measured TCP stimulus counters, accumulated by the stimulus task.
 *
 * Written only by the task; read via tcp_stimulus_get_stats(). Reset when a
 * take's stimulus is applied so the numbers stay scoped to that take.
 */
typedef struct {
    uint32_t rounds;       /**< tcp_round() cycles attempted while running. */
    uint32_t connect_ok;   /**< Connections that completed the handshake. */
    uint32_t connect_fail; /**< socket()/connect()/poll() failures. */
    uint32_t port_flips;   /**< Times the active port switched (sticky failover). */
    uint16_t active_port;  /**< Port used by the current round. */
} tcp_stimulus_stats_t;

/**
 * @brief Start the TCP gateway stimulus.
 *
 * Safe to call repeatedly: if the task is already running it returns ESP_OK
 * without creating a second one. The task reads the gateway from the STA
 * interface every round, so it must only be started once an IP is available
 * (apply_stimulus_mode runs it on link-up).
 *
 * @return ESP_OK when the task is running or already running, ESP_ERR_NO_MEM
 *         when the task could not be created.
 */
esp_err_t tcp_stimulus_start(void);

/**
 * @brief Stop the TCP gateway stimulus.
 *
 * Signals the task to wind down; it closes every socket it holds before exiting.
 * Safe to call when it was never started or has already stopped.
 */
void tcp_stimulus_stop(void);

/**
 * @brief Report whether the stimulus task is currently running.
 */
bool tcp_stimulus_is_running(void);

/**
 * @brief Apply runtime settings.
 *
 * Only validates and stores; start/stop is owned by apply_stimulus_mode, exactly
 * like the HTTP stimulus. A rejected command leaves the previous settings intact.
 *
 * Safe to call while the stimulus task is running: the task reads these values
 * at the start of every round, so new settings take effect from the next round
 * without touching the task's lifetime (a task must not be destroyed while it is
 * waiting inside poll()/select()).
 */
esp_err_t tcp_stimulus_set_config(const tcp_stimulus_config_t *cfg);

/**
 * @brief Read back the runtime settings.
 */
esp_err_t tcp_stimulus_get_config(tcp_stimulus_config_t *cfg);

/**
 * @brief Read the stimulus counters accumulated since the last reset.
 */
esp_err_t tcp_stimulus_get_stats(tcp_stimulus_stats_t *stats);

/**
 * @brief Zero the stimulus counters (called when a take's stimulus is applied).
 */
void tcp_stimulus_reset_stats(void);

#ifdef __cplusplus
}
#endif
