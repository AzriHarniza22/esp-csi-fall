/*
 * SPDX-FileCopyrightText: 2026 Espressif Systems (Shanghai) CO LTD
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

#include <sys/poll.h>
#include <lwip/sockets.h>

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_err.h"
#include "esp_log.h"
#include "esp_netif.h"

#include "tcp_stimulus.h"

/* A3 baseline (tcp_csi_optimization campaign, 2026-11-02): non-blocking poll,
 * concurrency 4, 10 ms interval, connect -> close, port 80 fallback 53,
 * 50 ms timeout. Reproduced here from the validated working copy in
 * examples/get-started/csi_recv_router_promisc_on rather than rewritten. */
#define TCP_STIMULUS_TASK_STACK   4096
#define TCP_STIMULUS_TASK_PRIO    4
#define TCP_STIMULUS_MAX_CONC     8      /* bound for the fixed poll arrays */
#define TCP_STIMULUS_CONC_DEFAULT 4
#define TCP_STIMULUS_INT_DEFAULT  10
#define TCP_STIMULUS_PORT_DEFAULT 80
#define TCP_STIMULUS_PORT_ALT     53
#define TCP_STIMULUS_TIMEOUT_DFLT 50
#define TCP_STIMULUS_RETRY_MS     100    /* pause when the gateway has no IP yet */

/* Requested vs actual state, same two-flag pattern as ht_stimulus: a stop only
 * takes effect once the task leaves its current round, so is_running reflects
 * the real task, not the just-issued command.
 *
 * s_mux serialises the stop/exit handshake between the stimulus task and start/stop
 * calls. apply_stimulus_mode() always stops before it starts, so a tcp -> tcp
 * re-apply (a repeated SET_STIMULUS_MODE, or the panel's Apply button) runs while
 * the old task is still alive: without this lock the sequence "stop requested ->
 * start sees s_running true and skips -> task notices the stop and exits" leaves
 * the mode set to tcp with nothing generating traffic. */
static portMUX_TYPE s_mux = portMUX_INITIALIZER_UNLOCKED;
static volatile bool     s_running;
static volatile bool     s_stop_requested;

static volatile uint32_t s_concurrency = TCP_STIMULUS_CONC_DEFAULT;
static volatile uint32_t s_interval_ms = TCP_STIMULUS_INT_DEFAULT;
static volatile uint16_t s_port        = TCP_STIMULUS_PORT_DEFAULT;
static volatile uint16_t s_port_alt    = TCP_STIMULUS_PORT_ALT;
static volatile uint32_t s_timeout_ms  = TCP_STIMULUS_TIMEOUT_DFLT;

/* Active port index; flipped (sticky) when a whole round fails, exactly as A3. */
static volatile int      s_port_idx;

static tcp_stimulus_stats_t s_stats;

static const char *TAG = "tcp_stimulus";

static uint16_t tcp_active_port(void)
{
    return (s_port_idx == 0) ? s_port : s_port_alt;
}

/* Resolve the gateway IPv4 from the STA interface that is currently up. Returns
 * false when no IP has been obtained yet, so the caller can back off instead of
 * connecting to 0.0.0.0 in a tight loop. */
static bool tcp_make_addr(struct sockaddr_in *sa)
{
    memset(sa, 0, sizeof(*sa));
    esp_netif_t *sta = esp_netif_get_handle_from_ifkey("WIFI_STA_DEF");
    esp_netif_ip_info_t ip = {0};
    if (!sta || esp_netif_get_ip_info(sta, &ip) != ESP_OK || ip.gw.addr == 0) {
        return false;
    }
    sa->sin_family = AF_INET;
    sa->sin_addr.s_addr = ip.gw.addr;
    sa->sin_port = htons(tcp_active_port());
    return true;
}

static void tcp_flip_port(void)
{
    s_port_idx = 1 - s_port_idx;
    s_stats.port_flips++;
}

/* One A3 round: open `conc` non-blocking connects in parallel, one poll(),
 * count the handshakes that complete, close every socket. connect -> close, so
 * a completed handshake is the whole exchange (no send/recv). */
static void tcp_round(void)
{
    struct sockaddr_in sa;
    if (!tcp_make_addr(&sa)) {
        s_stats.connect_fail++;
        vTaskDelay(pdMS_TO_TICKS(TCP_STIMULUS_RETRY_MS));
        return;
    }

    uint32_t conc = s_concurrency;
    if (conc < 1) {
        conc = 1;
    }
    if (conc > TCP_STIMULUS_MAX_CONC) {
        conc = TCP_STIMULUS_MAX_CONC;
    }

    int fd[TCP_STIMULUS_MAX_CONC];
    struct pollfd pfd[TCP_STIMULUS_MAX_CONC];
    int opened = 0;

    for (uint32_t i = 0; i < conc && !s_stop_requested; i++) {
        int s = socket(AF_INET, SOCK_STREAM, 0);
        if (s < 0) {
            s_stats.connect_fail++;
            continue;
        }
        int fl = fcntl(s, F_GETFL, 0);
        fcntl(s, F_SETFL, fl | O_NONBLOCK);
        int r = connect(s, (struct sockaddr *)&sa, sizeof(sa));
        if (r == 0 || errno == EINPROGRESS) {
            fd[opened] = s;
            pfd[opened].fd = s;
            pfd[opened].events = POLLOUT;
            pfd[opened].revents = 0;
            opened++;
        } else {
            s_stats.connect_fail++;
            close(s);
        }
    }

    if (opened == 0) {
        tcp_flip_port();
        return;
    }

    int pr = poll(pfd, opened, (int)s_timeout_ms);
    int any_ok = 0;
    for (int i = 0; i < opened; i++) {
        int err = 0;
        socklen_t el = sizeof(err);
        bool ready = (pr > 0) && (pfd[i].revents & POLLOUT);
        if (ready) {
            getsockopt(fd[i], SOL_SOCKET, SO_ERROR, &err, &el);
        }
        if (ready && err == 0) {
            s_stats.connect_ok++;
            any_ok++;
        } else {
            s_stats.connect_fail++;
        }
        close(fd[i]);
    }
    if (!any_ok) {
        tcp_flip_port();
    }
}

static void tcp_stimulus_task(void *arg)
{
    (void)arg;
    ESP_LOGI(TAG, "TCP stimulus started (conc=%" PRIu32 " interval=%" PRIu32 " ms ports=%" PRIu16 "/%" PRIu16 " timeout=%" PRIu32 " ms)",
             (uint32_t)s_concurrency, (uint32_t)s_interval_ms, (uint16_t)s_port, (uint16_t)s_port_alt, (uint32_t)s_timeout_ms);

    for (;;) {
        while (!s_stop_requested) {
            s_stats.rounds++;
            s_stats.active_port = tcp_active_port();
            tcp_round();
            /* Sleep in short slices so a stop is honoured within one slice. With
             * CONFIG_FREERTOS_HZ=100 a slice below one tick does not delay: the
             * real granularity of interval_ms is portTICK_PERIOD_MS. */
            uint32_t remaining = s_interval_ms;
            while (remaining > 0 && !s_stop_requested) {
                uint32_t slice = (remaining > 5) ? 5 : remaining;
                vTaskDelay(pdMS_TO_TICKS(slice));
                remaining -= slice;
            }
        }

        /* Re-check the request under the lock: a start() that ran during the round
         * above has cleared it, and this task must keep serving rather than exit.
         * A task must not be torn down around a pending poll()/select() wait, and
         * this path never destroys one while it is waiting. */
        portENTER_CRITICAL(&s_mux);
        if (s_stop_requested) {
            s_running = false;
        }
        portEXIT_CRITICAL(&s_mux);
        if (!s_running) {
            break;
        }
    }

    s_stats.active_port = tcp_active_port();
    ESP_LOGI(TAG, "TCP stimulus stopped (rounds=%" PRIu32 " ok=%" PRIu32 " fail=%" PRIu32 " flips=%" PRIu32 " port=%" PRIu16 ")",
             s_stats.rounds, s_stats.connect_ok, s_stats.connect_fail, s_stats.port_flips, s_stats.active_port);
    vTaskDelete(NULL);
}

esp_err_t tcp_stimulus_start(void)
{
    portENTER_CRITICAL(&s_mux);
    if (s_running) {
        /* Cancel a pending stop instead of skipping the restart, so that a
         * stop-then-start re-apply keeps the existing task running. */
        s_stop_requested = false;
        portEXIT_CRITICAL(&s_mux);
        return ESP_OK;
    }
    s_running = true;
    s_stop_requested = false;
    portEXIT_CRITICAL(&s_mux);

    BaseType_t ok = xTaskCreate(tcp_stimulus_task, "tcp_stim",
                                TCP_STIMULUS_TASK_STACK, NULL,
                                TCP_STIMULUS_TASK_PRIO, NULL);
    if (ok != pdPASS) {
        portENTER_CRITICAL(&s_mux);
        s_running = false;
        portEXIT_CRITICAL(&s_mux);
        ESP_LOGE(TAG, "task create failed");
        return ESP_ERR_NO_MEM;
    }
    return ESP_OK;
}

void tcp_stimulus_stop(void)
{
    portENTER_CRITICAL(&s_mux);
    if (s_running) {
        s_stop_requested = true;
    }
    portEXIT_CRITICAL(&s_mux);
}

bool tcp_stimulus_is_running(void)
{
    return s_running;
}

esp_err_t tcp_stimulus_set_config(const tcp_stimulus_config_t *cfg)
{
    if (!cfg) {
        return ESP_ERR_INVALID_ARG;
    }
    /* Validate everything before touching anything; a rejected command must not
     * disturb a running stimulus. */
    if (cfg->concurrency < 1 || cfg->concurrency > TCP_STIMULUS_MAX_CONC) {
        return ESP_ERR_INVALID_ARG;
    }
    if (cfg->interval_ms < 1 || cfg->interval_ms > 5000) {
        return ESP_ERR_INVALID_ARG;
    }
    /* timeout_ms == 0 is a real mode, not a mistake: lwip_poll() returns 0
     * immediately when the timeout is zero (components/lwip/lwip/src/api/
     * sockets.c), so a round becomes SYN-then-forget with no wait at all. */
    if (cfg->timeout_ms > 5000) {
        return ESP_ERR_INVALID_ARG;
    }
    if (cfg->port == 0 || cfg->port_alt == 0) {
        return ESP_ERR_INVALID_ARG;
    }

    s_concurrency = cfg->concurrency;
    s_interval_ms = cfg->interval_ms;
    s_port = cfg->port;
    s_port_alt = cfg->port_alt;
    s_timeout_ms = cfg->timeout_ms;
    return ESP_OK;
}

esp_err_t tcp_stimulus_get_config(tcp_stimulus_config_t *cfg)
{
    if (!cfg) {
        return ESP_ERR_INVALID_ARG;
    }
    cfg->concurrency = s_concurrency;
    cfg->interval_ms = s_interval_ms;
    cfg->port = s_port;
    cfg->port_alt = s_port_alt;
    cfg->timeout_ms = s_timeout_ms;
    return ESP_OK;
}

esp_err_t tcp_stimulus_get_stats(tcp_stimulus_stats_t *stats)
{
    if (!stats) {
        return ESP_ERR_INVALID_ARG;
    }
    *stats = s_stats;
    return ESP_OK;
}

void tcp_stimulus_reset_stats(void)
{
    memset(&s_stats, 0, sizeof(s_stats));
}
