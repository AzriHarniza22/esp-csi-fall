/*
 * SPDX-FileCopyrightText: 2026
 *
 * Publishes radar peer samples to an MQTT broker over TLS so a browser
 * dashboard can read them from any phone. The device stays standalone: nothing
 * between the ESP32 and the browser but the broker.
 *
 * This is deliberately publish-only for now. Publishing does not make the radar
 * work. CSI only exists for OFDM/HT frames, so the AP has to keep sending them,
 * which is what the HT stimulus is for. On an AP that pins the station to
 * 2 Mbps CCK the stream here stays flat no matter what the broker reports.
 */
#pragma once

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "esp_wifi_sensing.h"

#ifdef __cplusplus
extern "C" {
#endif

#define MQTT_SETTINGS_STR_LEN 96

typedef struct {
    char name[16];
    uint8_t mac[6];
} mqtt_publisher_peer_t;

/** @brief Broker settings as currently stored in NVS. The password is never returned. */
typedef struct {
    char host[MQTT_SETTINGS_STR_LEN];
    char user[MQTT_SETTINGS_STR_LEN];
    char prefix[MQTT_SETTINGS_STR_LEN];
    int port;
} mqtt_settings_t;

/**
 * @brief Bring the MQTT client up and start the publishing task.
 *
 * Returns once the client object exists, not once it is connected; the client
 * keeps retrying on its own and @ref mqtt_publisher_is_connected reports the
 * live state. NVS is seeded from Kconfig on first boot.
 */
esp_err_t mqtt_publisher_init(esp_wifi_sensing_fsm_handle_t fsm,
                              const mqtt_publisher_peer_t *peers, size_t peer_num);

/**
 * @brief Queue one peer sample for publishing.
 *
 * Non-blocking: the sample goes on a ring and the MQTT task drains it, because
 * esp_mqtt_client_publish() can block for the network timeout. Safe to call
 * before @ref mqtt_publisher_init; the call is ignored until then. Values are
 * dropped while the client is disconnected rather than queued, since stale
 * radar values are worse than a gap in the chart.
 */
void mqtt_publisher_publish(const char *name, const uint8_t mac[6],
                            const esp_wifi_sensing_fsm_channel_diag_t *diag,
                            esp_wifi_sensing_fsm_state_t motion_state);

/** @brief Read the broker settings stored in NVS. */
esp_err_t mqtt_publisher_get_settings(mqtt_settings_t *out);

/** @brief Store broker settings in NVS and reconnect with them. */
esp_err_t mqtt_publisher_set_settings(const char *host, int port, const char *user,
                                      const char *pass, const char *prefix);

bool mqtt_publisher_is_connected(void);

#ifdef __cplusplus
}
#endif