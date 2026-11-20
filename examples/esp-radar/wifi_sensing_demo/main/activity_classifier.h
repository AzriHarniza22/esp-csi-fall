/*
 * Experimental offline-trained CSI activity classifier.
 */
#pragma once

#include "esp_err.h"
#include "esp_radar.h"

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

esp_err_t activity_classifier_init(void);
void activity_classifier_enqueue(const wifi_csi_filtered_info_t *info);
void activity_classifier_note_motion_sample(
    const uint8_t peer_mac[6],
    int64_t timestamp_us,
    uint32_t smooth_scaled);

#ifdef __cplusplus
}
#endif
