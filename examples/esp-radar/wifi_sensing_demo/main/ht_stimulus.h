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

/**
 * @brief Runtime settings of the AP HT-rate traffic stimulus.
 *
 * These are deliberately runtime values instead of build-time constants so the
 * web monitor can tune them live while watching how the radar responds.
 */
typedef struct {
    bool     enabled;      /**< Requested state; may differ from the task state for the short moment after a stop. */
    uint32_t burst_bytes;  /**< Download size of one burst, in bytes. */
    uint32_t pause_ms;     /**< Quiet gap between bursts, in milliseconds. */
} ht_stimulus_config_t;

/**
 * @brief Start the AP HT-rate traffic stimulus (opt-in fallback).
 *
 * CSI from the AP only flows while the AP transmits frames the ESP can decode
 * as HT. A router ping is not enough on its own: ping replies are legacy frames
 * and they yield no CSI on this hardware, which is why the official LLTF-only
 * `csi_recv_router` recipe leaves the channel flat here.
 *
 * This keeps an HTTP transfer running through the AP so the AP continuously
 * emits large HT frames captured through HT-LTF. The AP transmits those frames
 * and their source MAC is the AP BSSID, so the CSI still originates from the AP
 * only: no laptop, no extra peer and no loopback is involved.
 *
 * Cost: the stimulus runs entirely on this ESP but requires the AP to provide
 * internet access, and the bulk downlink traffic inflates latency for other
 * clients sharing the link. When the endpoint is unreachable the task just
 * retries after a delay instead of failing the demo.
 *
 * @return ESP_OK when the task is running or already running.
 */
esp_err_t ht_stimulus_start(void);

/**
 * @brief Stop the AP HT-rate traffic stimulus.
 *
 * Safe to call when the stimulus was never started or has already stopped.
 */
void ht_stimulus_stop(void);

/**
 * @brief Report whether the stimulus task is currently running.
 */
bool ht_stimulus_is_running(void);

/**
 * @brief Apply runtime settings.
 *
 * Passing @c enabled true starts the task and @c false stops it. The burst and
 * pause values take effect on the next cycle, so retuning while the stimulus
 * runs does not drop the task. The download URL is derived from
 * @c burst_bytes, which keeps the requested byte count and the endpoint's
 * `bytes=` argument in agreement; asking the endpoint for more than the burst
 * would only reset the TCP connection and waste the remainder.
 *
 * @param cfg  Settings to apply in full: @c burst_bytes and @c pause_ms are
 *             validated first and only written when every field is valid, so a
 *             rejected command leaves the previous settings untouched. Callers
 *             that only want to change one field should read the current
 *             configuration first and modify it.
 * @return ESP_ERR_INVALID_ARG when a value is out of range, ESP_ERR_NOT_SUPPORTED
 *         when the stimulus feature was compiled out.
 */
esp_err_t ht_stimulus_set_config(const ht_stimulus_config_t *cfg);

/**
 * @brief Read back the runtime settings and whether the task is running.
 *
 * @param cfg  Destination; may not be NULL.
 * @return ESP_OK on success.
 */
esp_err_t ht_stimulus_get_config(ht_stimulus_config_t *cfg);

#ifdef __cplusplus
}
#endif
