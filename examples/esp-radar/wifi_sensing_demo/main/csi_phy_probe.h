/*
 * SPDX-FileCopyrightText: 2026 Espressif Systems (Shanghai) CO LTD
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/*
 * CSI-callback PHY probe (replaces the earlier generic "PHY downlink" framing).
 *
 * SCOPE — this probe observes ONLY the frames that reach the CSI callback.
 * It is attached to web_serial_monitor_csi_callback() (the esp-radar CSI path,
 * after peer selection + LTF rebuild). Consequently it measures the
 * CSI-ELIGIBLE SUBSET of received frames, NOT the whole promiscuous RX
 * population. It cannot characterise PHY of AP frames that never produced a
 * CSI callback (the starved-AP case): absence of a source MAC in these counters
 * is NOT evidence about the AP's PHY mode (CCK/OFDM/HT) or about whether the AP
 * is transmitting at all.
 *
 * The promiscuous-path characterisation (per-frame type/subtype, sig_mode
 * distribution, per-source-MAC counts over the air) is owned by the LOCKED
 * esp-radar component and surfaces in its "csi_preproc" ESP_LOG accounting.
 * This module complements — and must not be confused with or substituted for —
 * that promiscuous-side data.
 *
 * ESP32 classic has a SINGLE promiscuous RX slot owned by esp-radar, so this
 * probe deliberately does NOT install a second promiscuous callback (which
 * would clobber esp-radar). It reuses the existing CSI hook only.
 *
 * Coverage / limits of the CSI path (see docs/investigasi-kompatibilitas-ap-csi.md §8):
 *  - Available per frame: source/destination MAC, RSSI, rate, rx_format,
 *    signal_mode, mcs, cwb (bandwidth), stbc, channel, secondary_channel,
 *    aggregation, rx_seq, payload_len, first_word_invalid, best-effort frame
 *    type from hdr when populated.
 *  - NOT available here: a header-derived BSSID, reliable 802.11 subtype for
 *    frames without hdr, MAC frame air-length, and any frame that never
 *    reached the CSI callback.
 *
 * Bounded counters, updated cheaply under a short critical section; reported
 * periodically from the monitor task via ESP_LOGW (never per frame, never in
 * the serial JSON stream). Disabled by default (HMSCMD PHYPROBE on|off|get).
 */

#ifndef CSI_PHY_PROBE_H
#define CSI_PHY_PROBE_H

#include <stdbool.h>
#include <stdint.h>

#include "esp_radar.h"

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief Enable or disable CSI-callback frame accounting.
 *
 * Disabling also clears the current observation window.
 */
void csi_phy_probe_set_enabled(bool enable);

/** @brief Current enable state. */
bool csi_phy_probe_is_enabled(void);

/**
 * @brief Account one CSI-callback frame. Cheap; safe to call from the
 *        esp-radar CSI preprocessing task (Wi-Fi callback context).
 *
 * Only frames handed to the CSI callback are seen here.
 *
 * @param info   Filtered CSI frame passed to the monitor callback.
 * @param ts_us  esp_timer_get_time() sampled at callback entry (may be 0).
 * @param ap_mac Source MAC of the tracked AP peer, or NULL when unknown.
 */
void csi_phy_probe_record(const wifi_csi_filtered_info_t *info, int64_t ts_us,
                          const uint8_t ap_mac[6]);

/**
 * @brief Emit the periodic ESP_LOGW report and reset the window.
 *
 * Call from a task (not the Wi-Fi callback). No-op when disabled.
 *
 * @param now_us esp_timer_get_time() at report time.
 */
void csi_phy_probe_report(int64_t now_us);

#ifdef __cplusplus
}
#endif

#endif /* CSI_PHY_PROBE_H */
