/*
 * Experimental offline-trained CSI activity classifier.
 */
#pragma once

#include "esp_err.h"
#include "esp_radar.h"

#ifdef __cplusplus
extern "C" {
#endif

esp_err_t activity_classifier_init(void);
void activity_classifier_enqueue(const wifi_csi_filtered_info_t *info);

#ifdef __cplusplus
}
#endif
