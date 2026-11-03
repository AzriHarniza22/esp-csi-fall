/*
 * SPDX-FileCopyrightText: 2026 Espressif Systems (Shanghai) CO LTD
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/*
 * CSI-callback PHY probe.
 *
 * OBSERVATION BOUNDARY (read this first): this module is attached to
 * web_serial_monitor_csi_callback(), i.e. the ESP-IDF/esp-radar *CSI* path.
 * It therefore accounts ONLY for frames that already reached the CSI callback
 * — that is, frames that produced CSI after esp-radar peer selection + LTF
 * rebuild. It is NOT a promiscuous RX sniffer and cannot see:
 *   - frames rejected before the CSI callback (e.g. a starved AP whose frames
 *     never yield CSI),
 *   - management/control frames that never produce CSI,
 *   - the full over-the-air frame population.
 * The promiscuous-path characterisation lives entirely in esp-radar's own
 * "csi_preproc" accounting (locked component). Do NOT present this probe as
 * complete downlink instrumentation; it measures the CSI-eligible subset.
 *
 * In particular, an absent AP source in these counters proves only that no
 * AP frame reached the CSI callback — NOT that the AP uses CCK, a particular
 * PHY mode, or is silent on the wire. Absence here is not PHY evidence.
 *
 * Enabled only via "HMSCMD PHYPROBE on|off|get" (default OFF). Report is a
 * periodic ESP_LOGW from the monitor task (never per frame), kept separate
 * from the serial JSON stream so recording/protocol schemas are unchanged.
 */

#include <inttypes.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "freertos/FreeRTOS.h"

#include "esp_log.h"
#include "esp_mac.h"
#include "esp_timer.h"
#include "esp_wifi.h"

#include "csi_phy_probe.h"

static const char *TAG = "csi_phy_probe";

/* Bounded storage only: every histogram has a fixed number of bins and the
 * per-source-MAC table has a fixed slot count, so memory is constant regardless
 * of traffic. Records that fall outside a bin are counted, not expanded. */
#define CSI_PHY_PROBE_SRC_SLOTS   8
#define CSI_PHY_PROBE_RSSI_BUCKETS 20   /* (rssi + 100) / 5  => -100..-3 dBm in 5 dB steps */
#define CSI_PHY_PROBE_RATE_BINS   16    /* non-HT rate code is 5 bits (0..15) */
#define CSI_PHY_PROBE_MCS_BINS    8     /* ESP32 classic HT: MCS 0..7 single stream */
#define CSI_PHY_PROBE_SIG_BINS    3     /* NON_HT / HT / HE */
#define CSI_PHY_PROBE_FMT_BINS    4
#define CSI_PHY_PROBE_CHAN_BINS   16

typedef struct {
    uint8_t  mac[6];
    uint32_t cnt;
    uint8_t  sig;          /* last observed sig_mode */
    uint8_t  bw;           /* last observed cwb */
    bool     is_ap;
} csi_phy_probe_src_t;

typedef struct {
    int64_t  window_start_us;
    uint32_t total;
    /* Category (mutually exclusive, priority: from_ap > to_self > other).
     * Source MAC here is info->mac, the CSI-frame source, not a wire address. */
    uint32_t cat_from_ap;
    uint32_t cat_to_self;
    uint32_t cat_other;
    /* Frame type from the 802.11 header, best effort (NULL hdr => unknown). */
    uint32_t ft_mgmt;
    uint32_t ft_ctrl;
    uint32_t ft_data;
    uint32_t ft_unknown;
    uint32_t bc_mc;        /* data frames whose addr1 is broadcast/multicast */
    /* PHY distributions (of CSI-callback frames only). */
    uint32_t sig[CSI_PHY_PROBE_SIG_BINS];
    uint32_t fmt[CSI_PHY_PROBE_FMT_BINS];
    uint32_t bw[2];
    uint32_t stbc[2];
    uint32_t agg[2];
    uint32_t sech[4];      /* secondary channel: 0 none / 1 above / 2 below */
    uint32_t rate[CSI_PHY_PROBE_RATE_BINS];
    uint32_t mcs[CSI_PHY_PROBE_MCS_BINS];
    uint32_t mcs_overflow;
    uint32_t rate_overflow;
    uint32_t rssi[CSI_PHY_PROBE_RSSI_BUCKETS];
    uint32_t chan[CSI_PHY_PROBE_CHAN_BINS];
    uint32_t first_invalid;
    uint32_t payload_min;
    uint32_t payload_max;
    uint64_t payload_sum;
    uint32_t payload_n;
    /* Per-source MAC table. */
    csi_phy_probe_src_t src[CSI_PHY_PROBE_SRC_SLOTS];
    int      src_n;
    uint32_t src_overflow;
} csi_phy_probe_win_t;

static portMUX_TYPE s_probe_mux = portMUX_INITIALIZER_UNLOCKED;
static volatile bool s_probe_enabled;
static csi_phy_probe_win_t s_win;
static uint8_t s_self_mac[6];
static bool s_have_self_mac;

static void csi_phy_probe_reset_window(int64_t now_us)
{
    memset(&s_win, 0, sizeof(s_win));
    s_win.window_start_us = now_us;
    s_win.payload_min = 0xFFFFFFFFu;
}

void csi_phy_probe_set_enabled(bool enable)
{
    if (enable == s_probe_enabled) {
        return;
    }
    s_probe_enabled = enable;
    if (enable) {
        /* Cache our own STA MAC once so destination classification is cheap. */
        s_have_self_mac = (esp_wifi_get_mac(WIFI_IF_STA, s_self_mac) == ESP_OK);
        portENTER_CRITICAL(&s_probe_mux);
        csi_phy_probe_reset_window(esp_timer_get_time());
        portEXIT_CRITICAL(&s_probe_mux);
        ESP_LOGW(TAG, "CSI-callback probe enabled (self mac %s, window resets every report)",
                 s_have_self_mac ? MACSTR : "unknown");
    } else {
        ESP_LOGW(TAG, "disabled");
    }
}

bool csi_phy_probe_is_enabled(void)
{
    return s_probe_enabled;
}

static void csi_phy_probe_track_src(const uint8_t mac[6], uint8_t sig, uint8_t bw, bool is_ap)
{
    csi_phy_probe_src_t *slot = NULL;
    csi_phy_probe_src_t *least = NULL;
    for (int i = 0; i < CSI_PHY_PROBE_SRC_SLOTS; i++) {
        csi_phy_probe_src_t *c = &s_win.src[i];
        if (c->cnt == 0) {
            slot = c;
            break;
        }
        if (memcmp(c->mac, mac, 6) == 0) {
            slot = c;
            break;
        }
        if (!least || c->cnt < least->cnt) {
            least = c;
        }
    }
    if (!slot) {
        /* Table full: replace the least-frequent slot so dominant sources stay.
         * Overflow is recorded so the report flags lost granularity. */
        slot = least;
        s_win.src_overflow++;
    }
    memcpy(slot->mac, mac, 6);
    slot->cnt++;
    slot->sig = sig;
    slot->bw = bw;
    slot->is_ap = is_ap;
}

void csi_phy_probe_record(const wifi_csi_filtered_info_t *info, int64_t ts_us,
                          const uint8_t ap_mac[6])
{
    (void)ts_us;
    if (!s_probe_enabled || !info) {
        return;
    }

    const esp_radar_rx_ctrl_info_t *rx = &info->rx_ctrl_info;
    const wifi_csi_info_t *drv = info->info;

    bool is_ap = (ap_mac && memcmp(info->mac, ap_mac, 6) == 0);

    /* Best-effort frame type from the 802.11 header. The driver keeps `info->info`
     * alive for the callback duration (see web_serial_monitor.c header comment),
     * but `hdr` is only populated when CSI header capture is enabled, so guard it. */
    uint8_t ftype = 0xFF;
    bool bc_mc = false;
    if (drv && drv->hdr) {
        uint16_t fc = (uint16_t)drv->hdr[0] | ((uint16_t)drv->hdr[1] << 8);
        ftype = (uint8_t)((fc >> 2) & 0x3);
        /* addr1 (destination) bit0 set => group address (broadcast/multicast). */
        bc_mc = (drv->hdr[4] & 0x01) != 0;
    }

    portENTER_CRITICAL(&s_probe_mux);
    s_win.total++;

    if (is_ap) {
        s_win.cat_from_ap++;
    } else if (s_have_self_mac && memcmp(info->dmac, s_self_mac, 6) == 0) {
        s_win.cat_to_self++;
    } else {
        s_win.cat_other++;
    }

    switch (ftype) {
    case 0: s_win.ft_mgmt++; break;
    case 1: s_win.ft_ctrl++; break;
    case 2: s_win.ft_data++; if (bc_mc) { s_win.bc_mc++; } break;
    default: s_win.ft_unknown++; break;
    }

    if ((unsigned)rx->signal_mode < CSI_PHY_PROBE_SIG_BINS) {
        s_win.sig[rx->signal_mode]++;
    }
    if ((unsigned)rx->rx_format < CSI_PHY_PROBE_FMT_BINS) {
        s_win.fmt[rx->rx_format]++;
    }
    if (rx->cwb < 2) {
        s_win.bw[rx->cwb]++;
    }
    if (rx->stbc < 2) {
        s_win.stbc[rx->stbc]++;
    } else {
        s_win.stbc[1]++;
    }
    if (rx->secondary_channel < 4) {
        s_win.sech[rx->secondary_channel]++;
    }
    if (rx->rate < CSI_PHY_PROBE_RATE_BINS) {
        s_win.rate[rx->rate]++;
    } else {
        s_win.rate_overflow++;
    }
    if (rx->mcs < CSI_PHY_PROBE_MCS_BINS) {
        s_win.mcs[rx->mcs]++;
    } else {
        s_win.mcs_overflow++;
    }
    if (rx->channel < CSI_PHY_PROBE_CHAN_BINS) {
        s_win.chan[rx->channel]++;
    }
    {
        int ri = (rx->rssi + 100) / 5;
        if (ri < 0) { ri = 0; }
        if (ri >= CSI_PHY_PROBE_RSSI_BUCKETS) { ri = CSI_PHY_PROBE_RSSI_BUCKETS - 1; }
        s_win.rssi[ri]++;
    }

    if (drv) {
        /* aggregation is a 1-bit field: value is inherently 0 (MPDU) or 1 (AMPDU). */
        s_win.agg[drv->rx_ctrl.aggregation ? 1 : 0]++;
        if (drv->first_word_invalid) {
            s_win.first_invalid++;
        }
        if (drv->payload_len > 0) {
            if (drv->payload_len < s_win.payload_min) { s_win.payload_min = drv->payload_len; }
            if (drv->payload_len > s_win.payload_max) { s_win.payload_max = drv->payload_len; }
            s_win.payload_sum += drv->payload_len;
            s_win.payload_n++;
        }
    }

    csi_phy_probe_track_src(info->mac, rx->signal_mode, rx->cwb, is_ap);
    portEXIT_CRITICAL(&s_probe_mux);
}

/* Render up to `bins` counters as "i:n" pairs, skipping zeros, into `out`. */
static void csi_phy_probe_hist(char *out, size_t out_sz, const char *prefix,
                               const uint32_t *bins, int n)
{
    size_t off = 0;
    bool any = false;
    for (int i = 0; i < n; i++) {
        if (bins[i] == 0) {
            continue;
        }
        any = true;
        int w = snprintf(out + off, out_sz - off, "%s%s%u=%lu", off ? " " : "",
                         prefix, (unsigned)i, (unsigned long)bins[i]);
        if (w < 0 || (size_t)w >= out_sz - off) {
            break;
        }
        off += (size_t)w;
    }
    if (!any) {
        snprintf(out, out_sz, "-");
    }
}

void csi_phy_probe_report(int64_t now_us)
{
    if (!s_probe_enabled) {
        return;
    }

    csi_phy_probe_win_t snap;
    portENTER_CRITICAL(&s_probe_mux);
    memcpy(&snap, &s_win, sizeof(snap));
    csi_phy_probe_reset_window(now_us);
    portEXIT_CRITICAL(&s_probe_mux);

    int64_t elapsed_us = now_us - snap.window_start_us;
    uint32_t elapsed_ms = elapsed_us > 0 ? (uint32_t)(elapsed_us / 1000) : 0;

    static char sigb[96], fmtb[96], bwb[48], stbcb[48], aggb[48], sechb[64];
    static char rateb[160], mcsb[128], rssib[224], chanb[128];
    csi_phy_probe_hist(sigb, sizeof(sigb), "sig", snap.sig, CSI_PHY_PROBE_SIG_BINS);
    csi_phy_probe_hist(fmtb, sizeof(fmtb), "fmt", snap.fmt, CSI_PHY_PROBE_FMT_BINS);
    csi_phy_probe_hist(bwb, sizeof(bwb), "bw", snap.bw, 2);
    csi_phy_probe_hist(stbcb, sizeof(stbcb), "stbc", snap.stbc, 2);
    csi_phy_probe_hist(aggb, sizeof(aggb), "agg", snap.agg, 2);
    csi_phy_probe_hist(sechb, sizeof(sechb), "sec", snap.sech, 4);
    csi_phy_probe_hist(rateb, sizeof(rateb), "r", snap.rate, CSI_PHY_PROBE_RATE_BINS);
    csi_phy_probe_hist(mcsb, sizeof(mcsb), "mcs", snap.mcs, CSI_PHY_PROBE_MCS_BINS);
    csi_phy_probe_hist(rssib, sizeof(rssib), "dbm-", snap.rssi, CSI_PHY_PROBE_RSSI_BUCKETS);
    csi_phy_probe_hist(chanb, sizeof(chanb), "ch", snap.chan, CSI_PHY_PROBE_CHAN_BINS);

    ESP_LOGW(TAG, "csi_cb scope win=%lums total=%lu | cat ap=%lu to_self=%lu other=%lu | ftype mgmt=%lu ctrl=%lu data=%lu unknown=%lu bc/mc=%lu",
             (unsigned long)elapsed_ms, (unsigned long)snap.total,
             (unsigned long)snap.cat_from_ap, (unsigned long)snap.cat_to_self,
             (unsigned long)snap.cat_other, (unsigned long)snap.ft_mgmt,
             (unsigned long)snap.ft_ctrl, (unsigned long)snap.ft_data,
             (unsigned long)snap.ft_unknown, (unsigned long)snap.bc_mc);
    ESP_LOGW(TAG, "PHY sig{%s} fmt{%s} bw{%s} stbc{%s} agg{%s} sec{%s}",
             sigb, fmtb, bwb, stbcb, aggb, sechb);
    ESP_LOGW(TAG, "PHY rate{%s} mcs{%s}(ovf=%lu,rateovf=%lu) chan{%s} first_inv=%lu",
             rateb, mcsb, (unsigned long)snap.mcs_overflow,
             (unsigned long)snap.rate_overflow, chanb, (unsigned long)snap.first_invalid);
    ESP_LOGW(TAG, "payload n=%lu min=%lu max=%lu avg=%lu",
             (unsigned long)snap.payload_n,
             (unsigned long)(snap.payload_n ? snap.payload_min : 0),
             (unsigned long)snap.payload_max,
             (unsigned long)(snap.payload_n ? (uint32_t)(snap.payload_sum / snap.payload_n) : 0));

    for (int i = 0; i < CSI_PHY_PROBE_SRC_SLOTS; i++) {
        if (snap.src[i].cnt == 0) {
            continue;
        }
        ESP_LOGW(TAG, "csi_src " MACSTR " cnt=%lu sig=%u bw=%u %s",
                 MAC2STR(snap.src[i].mac), (unsigned long)snap.src[i].cnt,
                 (unsigned)snap.src[i].sig, (unsigned)snap.src[i].bw,
                 snap.src[i].is_ap ? "AP" : "");
    }
    if (snap.src_overflow) {
        ESP_LOGW(TAG, "src table full: %lu replacement(s) (distinct MAC > %d)",
                 (unsigned long)snap.src_overflow, CSI_PHY_PROBE_SRC_SLOTS);
    }
}
