/*
 * SPDX-FileCopyrightText: 2026 Espressif Systems (Shanghai) CO LTD
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <inttypes.h>
#include <math.h>
#include <stdlib.h>
#include <string.h>

#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
#include "freertos/task.h"

#include "esp_check.h"
#include "esp_log.h"
#include "esp_mac.h"
#include "esp_netif.h"
#include "esp_timer.h"

#include "lwip/inet.h"
#include "ping/ping_sock.h"

#include "esp_radar.h"
#include "esp_wifi_sensing.h"

static const char *TAG = "esp_wifi_sensing_fsm";

#define HMS_GOLD_SPEEDUP_FACTOR 8.0f /* Gold-baseline speed scale: uniformly boosts gold rise/fall response. */
#define HMS_SCALE_FACTOR   1000U   /* Internal fixed-point scale: convert float features to integers with 3 decimal digits. */
#define HMS_MAX_BATCH      8    /* Max samples consumed per channel in one handle_events call, to keep polling short. */

#define HMS_DIAG_LOG_PERIOD_MS   2000U   /* Runtime diagnostic log period: emit a summary every 2 seconds. */
#define HMS_PRESENCE_HISTORY_LEN   25U   /* Presence-detection history window length. */
#define HMS_PRESENCE_MIN_SAMPLES    5U   /* Minimum valid samples before presence detection is ready. */
#define HMS_PRESENCE_TRIM_PERCENT 0.5f   /* Trimmed-mean ratio for presence: drop the larger side, then average. */
#define HMS_PRESENCE_GAIN_MIN      1.0f
#define HMS_PRESENCE_GAIN_MAX      30.0f
/* Ratios used to expand the simplified config into the older fine-grained runtime parameters. */
#define HMS_NOISE_NEGATIVE_RATIO      (0.70f / 0.30f) /* Negative noise-band expansion derived from noise_band. */
#define HMS_HYSTERESIS_ACTIVE_RATIO   (0.08f / 0.28f) /* Extra active-state hysteresis derived from hysteresis. */
#define HMS_GOLD_BASELINE_RATIO       (0.001f / 0.02f) /* Gold-baseline follow ratio derived from the baseline coefficient. */
#define HMS_NOISE_RELEASE_RATIO       (0.03f / 0.18f) /* Noise-envelope release speed derived from noise_adapt. */
#define HMS_NOISE_GAIN_EXIT_RATIO     (0.08f / 0.18f) /* Exit-state noise gain used in inactive/exit compensation. */
#define HMS_BASELINE_CLAMP_RATIO      (0.35f / 0.18f) /* Baseline clamp: max baseline offset relative to noise. */
#define HMS_DEBOUNCE_INACTIVE_RATIO   2U /* Inactive debounce multiplier applied to the base confirm count. */
#define HMS_HYSTERESIS_DEFAULT        0.28f /* Default hysteresis used for enter/exit threshold gap. */
#define HMS_NOISE_ADAPT_DEFAULT       0.18f /* Default noise-adapt coefficient for envelope updates. */
#define HMS_NOISE_BAND_DEFAULT        0.30f /* Default noise band around the baseline. */
#define HMS_DEBOUNCE_COUNT_DEFAULT    2U /* Default consecutive hits required before a state change. */
#define HMS_SENSITIVITY_DEFAULT       0.50f /* Default sensitivity used to scale thresholds and trigger strength. */
#define HMS_SMOOTH_COEF_MIN           0.06f /* Minimum smoothing coefficient so low dynamics still update. */
#define HMS_SMOOTH_COEF_MAX           0.38f /* Maximum smoothing coefficient so high dynamics do not overshoot. */
#define HMS_BASELINE_COEF_FIXED       0.020f /* Fixed baseline update coefficient for slow environmental drift. */
#define HMS_THRESHOLD_RATIO_MIN       0.20f /* Minimum detection-threshold ratio to avoid false triggers. */
#define HMS_THRESHOLD_RATIO_MAX       0.90f /* Maximum detection-threshold ratio to avoid missed detections. */
#define HMS_BASELINE_AVG_WINDOW_MS    2000U /* Initial averaging window used to estimate the startup baseline. */
#define HMS_BASELINE_AVG_WINDOW_US    ((int64_t)HMS_BASELINE_AVG_WINDOW_MS * 1000LL) /* Baseline averaging window in microseconds. */
#define HMS_BASELINE_AVG_MIN_PACKETS  50U /* Minimum packets required after the window elapses before init completes. */

#define HMS_RESET_COVER_DEFAULT       50U /* Dual-baseline recovery window after reset, in samples. */
#define HMS_CALIBRATION_TIMES_DEFAULT 6U /* Default calibration rounds before the init stage becomes stable. */

#define HMS_CHECK(a, str, ret_val)                                \
    if (!(a)) {                                                   \
        ESP_LOGE(TAG, "%s(%d): %s", __FUNCTION__, __LINE__, str); \
        return (ret_val);                                         \
    }

typedef struct {
    /* Event callback */
    esp_wifi_sensing_fsm_event_cb_t cb;
    /* User context passed back to the callback */
    void *user_data;
} hms_cb_info_t;

typedef struct {
    float smooth_coef;
    float baseline_coef;
    float noise_p;
    float noise_n;
    float threshold_p;
    float hysteresis_active;
    float hysteresis_inactive;
    float active_jitter_min;
    float gold_baseline_coef;
    float noise_attack_coef;
    float noise_release_coef;
    float noise_threshold_gain_enter;
    float noise_threshold_gain_exit;
    float baseline_clamp_gain;
    uint32_t debounce_active;
    uint32_t debounce_inactive;
    uint32_t reset_cover;
    uint32_t reset_calibration;
    uint32_t calibration_times;
    uint32_t active_filter_ms;
} hms_channel_runtime_config_t;

typedef struct {
    /* Whether this channel slot is in use */
    bool used;
    /* Peer MAC that identifies one sensing channel */
    uint8_t peer_mac[6];
    /* Radar peer handle */
    esp_radar_handle_t peer_handle;

    /* Public simplified channel config */
    esp_wifi_sensing_fsm_channel_config_t user_cfg;
    /* Expanded fine-grained runtime config */
    hms_channel_runtime_config_t cfg;
    /* Raw-feature ring buffer */
    uint32_t *raw_buf;
    uint32_t raw_read_index;
    uint32_t raw_write_index;
    uint32_t raw_count;

    /* Current sample after scaling */
    uint32_t raw_processing;
    /* Smoothed value after scaling */
    uint32_t smooth_scaled;
    /* Working baseline after scaling */
    uint32_t baseline_scaled;
    /* Slow gold baseline after scaling; the long-term center */
    uint32_t gold_baseline_scaled;
    /* Current noise-level estimate after scaling; used to raise thresholds */
    uint32_t noise_level_scaled;
    /* Baseline initialization stage */
    esp_wifi_sensing_fsm_init_stage_t init_stage;
    /* Stable-sample counter during initialization */
    uint32_t init_counter;
    /* Accumulated average used while initializing or resetting the baseline */
    uint64_t init_avg_sum;
    uint32_t init_avg_count;
    int64_t init_avg_start_us;
    /* Shared debounce counter for ACTIVE / INACTIVE */
    uint32_t debounce_counter;
    /* Consecutive out-of-noise hits that can trigger a baseline reset */
    uint32_t reset_counter;
    /* Background-stable counter: how long samples look like background */
    uint32_t gold_stable_counter;
    /* Previous diff sign; used to clear debounce on direction flip */
    int32_t last_diff;

    float jitter_value;
    float wander_value;
    float train_wander_thr;
    float train_jitter_thr;
    bool train_thresholds_valid;
    float presence_wander_history[HMS_PRESENCE_HISTORY_LEN];
    uint32_t presence_total_samples;
    uint32_t presence_write_index;
    float presence_wander_average;
    float presence_someone_threshold;
    bool presence_ready;
    bool presence_someone_status;
    int32_t diff_scaled;
    int32_t enter_threshold;
    int32_t exit_threshold;

    /* Deadline of the ACTIVE hold window, in microseconds */
    int64_t active_hold_until_us;
    /* Last emitted event */
    esp_wifi_sensing_fsm_event_t last_event;

    /* Internal process state (PROC_*) */
    uint8_t process_state;
} esp_wifi_sensing_fsm_channel_t;

typedef struct {
    /* Global configuration */
    esp_wifi_sensing_fsm_config_t config;
    /* Channel slots: reserved up front, allocated on add_channel */
    esp_wifi_sensing_fsm_channel_t **channels;
    /* Shared mutex used by the callback, task, and public APIs */
    SemaphoreHandle_t mutex;
    /* Background polling task */
    TaskHandle_t task;
    bool task_should_exit;
    /* Whether sample consumption and FSM updates are enabled */
    bool is_running;

    /* Radar / ping runtime state */
    bool radar_started;
    bool radar_amplitude_log_enabled;
    esp_ping_handle_t ping_handle;
    esp_ip4_addr_t ping_gw;
    uint32_t ping_frequency_hz;
    uint32_t ping_success_count;
    uint32_t ping_timeout_count;
    uint32_t radar_cb_count;
    uint32_t radar_drop_lock_count;
    uint32_t radar_drop_no_channel_count;
    uint32_t radar_overwrite_count;
    uint32_t radar_processed_count;
    uint32_t diag_prev_ping_success_count;
    uint32_t diag_prev_ping_timeout_count;
    uint32_t diag_prev_radar_cb_count;
    uint32_t diag_prev_radar_drop_lock_count;
    uint32_t diag_prev_radar_drop_no_channel_count;
    uint32_t diag_prev_radar_overwrite_count;
    uint32_t diag_prev_radar_processed_count;
    int64_t diag_last_log_us;

    hms_cb_info_t *cb_info[ESP_WIFI_SENSING_FSM_EVENT_MAX];
    size_t cb_size[ESP_WIFI_SENSING_FSM_EVENT_MAX];
} esp_wifi_sensing_fsm_t;

/*
 * Channel process_state:
 *
 *  (1) PROC_IDLE
 *       └─ After diff > active_enter_threshold for debounce_active hits
 *          -> enter PROC_ACTIVE and emit ACTIVE
 *
 *  (2) PROC_ACTIVE
 *       └─ Stay ACTIVE until active_filter_ms expires
 *       └─ After diff < inactive_exit_threshold for debounce_inactive hits
 *          -> return to PROC_IDLE and emit INACTIVE
 *
 *  Notes:
 *  - diff = smooth_scaled - baseline_scaled
 *  - active_enter_threshold = threshold_p * baseline * (1 + hysteresis_active)
 *  - inactive_exit_threshold = threshold_p * baseline * (1 - hysteresis_inactive)
 *  - PROC_DEBOUNCE_ACTIVE / PROC_DEBOUNCE_INACTIVE accumulate consecutive hits
 *    so a single spike cannot trigger a transition.
 */
enum {
    /* Idle: no confirmed active signal */
    PROC_IDLE = 0,
    /* Debouncing idle -> active until debounce_active is reached */
    PROC_DEBOUNCE_ACTIVE,
    /* Active: waiting for a confirmed exit */
    PROC_ACTIVE,
    /* Debouncing active -> idle until debounce_inactive is reached */
    PROC_DEBOUNCE_INACTIVE,
};

static esp_wifi_sensing_fsm_t *s_active_fsm = NULL;
static void hms_emit_event(esp_wifi_sensing_fsm_t *fsm,
                           esp_wifi_sensing_fsm_channel_t *ch,
                           esp_wifi_sensing_fsm_event_t event,
                           uint32_t data);
static void hms_reset_channel_state(esp_wifi_sensing_fsm_t *fsm,
                                    esp_wifi_sensing_fsm_channel_t *ch,
                                    bool emit_inactive);
static void hms_reset_presence_state(esp_wifi_sensing_fsm_channel_t *ch);

static esp_wifi_sensing_fsm_channel_config_t hms_get_default_channel_config(void)
{
    return (esp_wifi_sensing_fsm_channel_config_t)DEFAULT_ESP_WIFI_SENSING_FSM_CHANNEL_CONFIG();
}

static uint32_t hms_get_default_confirm_count(void)
{
#if defined(CONFIG_ESP_WIFI_SENSING_CONFIRM_COUNT)
    uint32_t confirm_count = CONFIG_ESP_WIFI_SENSING_CONFIRM_COUNT;
#else
    uint32_t confirm_count = HMS_DEBOUNCE_COUNT_DEFAULT;
#endif
    if (confirm_count < 1U) {
        return 1U;
    }
    if (confirm_count > 15U) {
        return 15U;
    }
    return confirm_count;
}

static uint32_t hms_get_default_ping_frequency_hz(void)
{
    uint32_t frequency_hz = (uint32_t)ESP_WIFI_SENSING_PING_FREQUENCY_HZ_DEFAULT;
    return (frequency_hz > 0U) ? frequency_hz : 1U;
}

static uint32_t hms_get_reset_calibration(uint32_t reset_cover)
{
    uint32_t reset_calibration = reset_cover / 5U;
    return (reset_calibration > 0) ? reset_calibration : 1U;
}

static float hms_lerp(float low, float high, float ratio)
{
    return low + ((high - low) * ratio);
}

static float hms_presence_gain_from_unit(float u)
{
    if (u < 0.0f) {
        u = 0.0f;
    } else if (u > 1.0f) {
        u = 1.0f;
    }
    return HMS_PRESENCE_GAIN_MIN + u * (HMS_PRESENCE_GAIN_MAX - HMS_PRESENCE_GAIN_MIN);
}

static void hms_normalize_channel_config(esp_wifi_sensing_fsm_channel_config_t *cfg)
{
    if (!cfg) {
        return;
    }

    const esp_wifi_sensing_fsm_channel_config_t def = hms_get_default_channel_config();
    if (cfg->sensitivity <= 0.0f || cfg->sensitivity > 1.0f) {
        cfg->sensitivity = def.sensitivity;
    }
    if (cfg->active_jitter_min < 0.0f) {
        cfg->active_jitter_min = def.active_jitter_min;
    }
    if (cfg->presence_sensitivity < 0.0f || cfg->presence_sensitivity > 1.0f) {
        cfg->presence_sensitivity = def.presence_sensitivity;
    }
}

static void hms_expand_channel_config(const esp_wifi_sensing_fsm_channel_config_t *cfg,
                                      hms_channel_runtime_config_t *runtime_cfg)
{
    if (!cfg || !runtime_cfg) {
        return;
    }

    float sensitivity = cfg->sensitivity;
    runtime_cfg->smooth_coef = hms_lerp(HMS_SMOOTH_COEF_MIN, HMS_SMOOTH_COEF_MAX, sensitivity);
    runtime_cfg->baseline_coef = HMS_BASELINE_COEF_FIXED;
    runtime_cfg->noise_p = HMS_NOISE_BAND_DEFAULT;
    runtime_cfg->noise_n = HMS_NOISE_BAND_DEFAULT * HMS_NOISE_NEGATIVE_RATIO;
    runtime_cfg->threshold_p = hms_lerp(HMS_THRESHOLD_RATIO_MAX, HMS_THRESHOLD_RATIO_MIN, sensitivity);
    runtime_cfg->hysteresis_active = HMS_HYSTERESIS_DEFAULT * HMS_HYSTERESIS_ACTIVE_RATIO;
    runtime_cfg->hysteresis_inactive = HMS_HYSTERESIS_DEFAULT;
    runtime_cfg->active_jitter_min = cfg->active_jitter_min;
    runtime_cfg->gold_baseline_coef = runtime_cfg->baseline_coef * HMS_GOLD_BASELINE_RATIO;
    runtime_cfg->noise_attack_coef = HMS_NOISE_ADAPT_DEFAULT;
    runtime_cfg->noise_release_coef = HMS_NOISE_ADAPT_DEFAULT * HMS_NOISE_RELEASE_RATIO;
    runtime_cfg->noise_threshold_gain_enter = HMS_NOISE_ADAPT_DEFAULT;
    runtime_cfg->noise_threshold_gain_exit = HMS_NOISE_ADAPT_DEFAULT * HMS_NOISE_GAIN_EXIT_RATIO;
    runtime_cfg->baseline_clamp_gain = HMS_NOISE_ADAPT_DEFAULT * HMS_BASELINE_CLAMP_RATIO;
    runtime_cfg->debounce_active = hms_get_default_confirm_count();
    runtime_cfg->debounce_inactive = runtime_cfg->debounce_active * HMS_DEBOUNCE_INACTIVE_RATIO;
    runtime_cfg->reset_cover = HMS_RESET_COVER_DEFAULT;
    runtime_cfg->reset_calibration = hms_get_reset_calibration(HMS_RESET_COVER_DEFAULT);
    runtime_cfg->calibration_times = HMS_CALIBRATION_TIMES_DEFAULT;
    runtime_cfg->active_filter_ms = cfg->active_filter_ms;
}

static int32_t hms_clamp_i32(int32_t value, int32_t low, int32_t high)
{
    if (value < low) {
        return low;
    }
    if (value > high) {
        return high;
    }
    return value;
}

static uint32_t hms_apply_iir_u32(uint32_t current, uint32_t target, float coef)
{
    if (coef <= 0.0f) {
        return current;
    }

    int32_t diff = (int32_t)target - (int32_t)current;
    if (diff == 0) {
        return current;
    }

    int32_t step = (int32_t)(diff * coef);
    if (step == 0) {
        step = (diff > 0) ? 1 : -1;
    }

    int32_t updated = (int32_t)current + step;
    return (updated > 0) ? (uint32_t)updated : 0;
}

static uint32_t hms_apply_center_step(uint32_t current, int32_t limited_error, float coef)
{
    if (coef <= 0.0f || limited_error == 0) {
        return current;
    }

    int32_t step = (int32_t)(limited_error * coef);
    if (step == 0) {
        step = (limited_error > 0) ? 1 : -1;
    }

    int32_t updated = (int32_t)current + step;
    return (updated > 0) ? (uint32_t)updated : 0;
}

static void hms_update_gold_baseline(esp_wifi_sensing_fsm_channel_t *ch,
                                     uint32_t target,
                                     float gold_coef)
{
    if (!ch) {
        return;
    }

    if (target == 0 || gold_coef <= 0.0f) {
        return;
    }

    float effective_gold_coef = gold_coef * HMS_GOLD_SPEEDUP_FACTOR;
    if (effective_gold_coef > 1.0f) {
        effective_gold_coef = 1.0f;
    }

    ch->gold_baseline_scaled = hms_apply_iir_u32(ch->gold_baseline_scaled, target, effective_gold_coef);
}

static void hms_update_noise_level(esp_wifi_sensing_fsm_channel_t *ch, uint32_t residual_scaled)
{
    if (!ch) {
        return;
    }

    float coef = (residual_scaled >= ch->noise_level_scaled) ?
                 ch->cfg.noise_attack_coef : ch->cfg.noise_release_coef;
    ch->noise_level_scaled = hms_apply_iir_u32(ch->noise_level_scaled, residual_scaled, coef);
}

static uint32_t hms_encode_waveform_jitter(float jitter_value)
{
    if (jitter_value <= 0.0f) {
        return 0;
    }

    float log_feature = log1pf(jitter_value * 1000.0f);
    if (log_feature <= 0.0f) {
        return 0;
    }

    float scaled_feature = log_feature * (float)HMS_SCALE_FACTOR;
    if (scaled_feature >= (float)(UINT32_MAX / HMS_SCALE_FACTOR)) {
        return UINT32_MAX / HMS_SCALE_FACTOR;
    }

    return (uint32_t)(scaled_feature + 0.5f);
}

static uint32_t hms_get_runtime_reference(const esp_wifi_sensing_fsm_channel_t *ch)
{
    if (!ch) {
        return HMS_SCALE_FACTOR;
    }

    uint32_t reference = HMS_SCALE_FACTOR;
    if (ch->baseline_scaled > reference) {
        reference = ch->baseline_scaled;
    }
    if (ch->gold_baseline_scaled > reference) {
        reference = ch->gold_baseline_scaled;
    }
    return reference;
}

static bool hms_within_noise_band(int32_t diff, uint32_t reference, float noise_p, float noise_n)
{
    if (reference == 0) {
        return diff == 0;
    }
    if (diff >= 0) {
        return diff <= (int32_t)(noise_p * reference);
    }
    return abs(diff) <= (int32_t)(noise_n * reference);
}

static bool hms_is_runtime_center_collapsed(const esp_wifi_sensing_fsm_channel_t *ch)
{
    if (!ch || ch->init_stage != ESP_WIFI_SENSING_FSM_INIT_STAGE_STABLE) {
        return false;
    }

    if (ch->baseline_scaled > HMS_SCALE_FACTOR || ch->gold_baseline_scaled > HMS_SCALE_FACTOR) {
        return false;
    }

    return ch->smooth_scaled > (8U * HMS_SCALE_FACTOR);
}

static void hms_seed_runtime_center(esp_wifi_sensing_fsm_channel_t *ch, uint32_t seed)
{
    if (!ch || seed == 0) {
        return;
    }

    ch->gold_baseline_scaled = seed;
    ch->baseline_scaled = seed;
    ch->smooth_scaled = seed;
    ch->noise_level_scaled = 0;
    ch->diff_scaled = 0;
    ch->enter_threshold = 0;
    ch->exit_threshold = 0;
    ch->init_counter = 0;
    ch->init_avg_sum = 0;
    ch->init_avg_count = 0;
    ch->init_avg_start_us = 0;
    ch->gold_stable_counter = 0;
    ch->reset_counter = 0;
    ch->init_stage = ESP_WIFI_SENSING_FSM_INIT_STAGE_STABLE;
}

static bool hms_recover_invalid_runtime_baseline(esp_wifi_sensing_fsm_t *fsm, esp_wifi_sensing_fsm_channel_t *ch)
{
    if (!fsm || !ch) {
        return false;
    }

    if (!hms_is_runtime_center_collapsed(ch)) {
        return false;
    }

    if (++ch->reset_counter < ch->cfg.reset_cover) {
        return false;
    }

    uint32_t seed = ch->smooth_scaled;
    hms_reset_channel_state(fsm, ch, true);
    hms_seed_runtime_center(ch, seed);
    ESP_LOGW(TAG, "recover collapsed runtime center: mac=" MACSTR " seed=%" PRIu32,
             MAC2STR(ch->peer_mac), seed);
    return true;
}

static void hms_reset_channel_state(esp_wifi_sensing_fsm_t *fsm, esp_wifi_sensing_fsm_channel_t *ch, bool emit_inactive)
{
    if (!fsm || !ch) {
        return;
    }

    if (emit_inactive && (ch->process_state == PROC_ACTIVE || ch->process_state == PROC_DEBOUNCE_INACTIVE)) {
        hms_emit_event(fsm, ch, ESP_WIFI_SENSING_FSM_EVENT_INACTIVE, ch->smooth_scaled / HMS_SCALE_FACTOR);
    }
    ch->process_state = PROC_IDLE;
    ch->debounce_counter = 0;
    ch->reset_counter = 0;
    ch->gold_stable_counter = 0;
    ch->last_diff = 0;
    ch->active_hold_until_us = 0;
}

static void hms_enter_init_stage(esp_wifi_sensing_fsm_channel_t *ch,
                                 esp_wifi_sensing_fsm_init_stage_t stage,
                                 bool clear_gold_baseline)
{
    if (!ch) {
        return;
    }

    ch->init_stage = stage;
    ch->init_counter = 0;
    ch->init_avg_sum = 0;
    ch->init_avg_count = 0;
    ch->init_avg_start_us = 0;
    ch->debounce_counter = 0;
    ch->reset_counter = 0;
    ch->gold_stable_counter = 0;
    ch->last_diff = 0;
    ch->process_state = PROC_IDLE;
    ch->active_hold_until_us = 0;
    if (stage == ESP_WIFI_SENSING_FSM_INIT_STAGE_START) {
        ch->baseline_scaled = 0;
        ch->smooth_scaled = 0;
        ch->noise_level_scaled = 0;
        ch->diff_scaled = 0;
        ch->enter_threshold = 0;
        ch->exit_threshold = 0;
        if (clear_gold_baseline) {
            ch->gold_baseline_scaled = 0;
        }
    }
    hms_reset_presence_state(ch);
}

static const char *hms_process_state_to_name(uint8_t state)
{
    switch (state) {
    case PROC_IDLE:
        return "IDLE";
    case PROC_DEBOUNCE_ACTIVE:
        return "DEBOUNCE_ACTIVE";
    case PROC_ACTIVE:
        return "ACTIVE";
    case PROC_DEBOUNCE_INACTIVE:
        return "DEBOUNCE_INACTIVE";
    default:
        return "UNKNOWN";
    }
}

static void hms_log_state_change(const esp_wifi_sensing_fsm_t *fsm,
                                 const esp_wifi_sensing_fsm_channel_t *ch,
                                 uint8_t prev_state,
                                 const char *reason,
                                 int32_t diff,
                                 int32_t enter_threshold,
                                 int32_t exit_threshold,
                                 uint32_t prev_debounce,
                                 int64_t now_us)
{
    if (!fsm || !ch || prev_state == ch->process_state) {
        return;
    }

    int64_t hold_left_us = (ch->active_hold_until_us > now_us) ? (ch->active_hold_until_us - now_us) : 0;
    ESP_LOGD(TAG,
             "state change: mac=" MACSTR " %s->%s reason=%s diff=%" PRId32
             " raw=%" PRIu32 " smooth=%" PRIu32 " baseline=%" PRIu32 " gold=%" PRIu32 " noise=%" PRIu32
             " enter_th=%" PRId32 " exit_th=%" PRId32
             " debounce=%" PRIu32 "->%" PRIu32 " hold_left_ms=%" PRId64,
             MAC2STR(ch->peer_mac),
             hms_process_state_to_name(prev_state),
             hms_process_state_to_name(ch->process_state),
             reason ? reason : "-",
             diff,
             ch->raw_processing,
             ch->smooth_scaled,
             ch->baseline_scaled,
             ch->gold_baseline_scaled,
             ch->noise_level_scaled,
             enter_threshold,
             exit_threshold,
             prev_debounce,
             ch->debounce_counter,
             hold_left_us / 1000);
}

static esp_wifi_sensing_fsm_channel_t *hms_get_channel(esp_wifi_sensing_fsm_t *fsm, const uint8_t peer_mac[6])
{
    /* Linear channel lookup: the channel count is typically small */
    if (!fsm || !peer_mac) {
        return NULL;
    }
    for (uint32_t i = 0; i < fsm->config.max_channel_num; i++) {
        esp_wifi_sensing_fsm_channel_t *ch = fsm->channels[i];
        if (ch && ch->used && memcmp(ch->peer_mac, peer_mac, 6) == 0) {
            return ch;
        }
    }
    return NULL;
}

static esp_wifi_sensing_fsm_train_status_t hms_map_train_status(esp_radar_train_status_t status)
{
    switch (status) {
    case ESP_RADAR_TRAIN_STATUS_PROGRESS:
        return ESP_WIFI_SENSING_FSM_TRAIN_STATUS_PROGRESS;
    case ESP_RADAR_TRAIN_STATUS_COMPLETE:
        return ESP_WIFI_SENSING_FSM_TRAIN_STATUS_COMPLETE;
    case ESP_RADAR_TRAIN_STATUS_NONE:
    default:
        return ESP_WIFI_SENSING_FSM_TRAIN_STATUS_NONE;
    }
}

static esp_wifi_sensing_fsm_train_action_t hms_map_train_action(esp_radar_train_action_t action)
{
    switch (action) {
    case ESP_RADAR_TRAIN_ACTION_WAIT_BUFFER:
        return ESP_WIFI_SENSING_FSM_TRAIN_ACTION_WAIT_BUFFER;
    case ESP_RADAR_TRAIN_ACTION_DISCARD_OUTLIER:
        return ESP_WIFI_SENSING_FSM_TRAIN_ACTION_DISCARD_OUTLIER;
    case ESP_RADAR_TRAIN_ACTION_COLLECT_SAMPLE:
        return ESP_WIFI_SENSING_FSM_TRAIN_ACTION_COLLECT_SAMPLE;
    case ESP_RADAR_TRAIN_ACTION_ACCUMULATE_BACKGROUND:
        return ESP_WIFI_SENSING_FSM_TRAIN_ACTION_ACCUMULATE_BACKGROUND;
    case ESP_RADAR_TRAIN_ACTION_IDLE:
    default:
        return ESP_WIFI_SENSING_FSM_TRAIN_ACTION_IDLE;
    }
}

static int hms_cmp_float_asc(const void *lhs, const void *rhs)
{
    float a = *(const float *)lhs;
    float b = *(const float *)rhs;
    if (a > b) {
        return 1;
    }
    if (a < b) {
        return -1;
    }
    return 0;
}

static float hms_average_float_array(const float *values, size_t len)
{
    if (!values || len == 0) {
        return 0.0f;
    }
    float sum = 0.0f;
    for (size_t i = 0; i < len; i++) {
        sum += values[i];
    }
    return sum / (float)len;
}

static float hms_trimmean(const float *values, size_t len, float percent)
{
    if (!values || len == 0) {
        return 0.0f;
    }
    float tmp[HMS_PRESENCE_HISTORY_LEN] = {0};
    size_t copy_len = (len > HMS_PRESENCE_HISTORY_LEN) ? HMS_PRESENCE_HISTORY_LEN : len;
    memcpy(tmp, values, copy_len * sizeof(float));
    qsort(tmp, copy_len, sizeof(float), hms_cmp_float_asc);
    size_t take_len = (size_t)((float)copy_len * (1.0f - percent) + 0.5f);
    if (take_len == 0) {
        take_len = 1;
    }
    if (take_len > copy_len) {
        take_len = copy_len;
    }
    return hms_average_float_array(tmp, take_len);
}

static void hms_reset_presence_state(esp_wifi_sensing_fsm_channel_t *ch)
{
    if (!ch) {
        return;
    }
    memset(ch->presence_wander_history, 0, sizeof(ch->presence_wander_history));
    ch->presence_total_samples = 0;
    ch->presence_write_index = 0;
    ch->presence_wander_average = 0.0f;
    ch->presence_someone_threshold = 0.0f;
    ch->presence_ready = false;
    ch->presence_someone_status = false;
}

static void hms_update_presence_state(esp_wifi_sensing_fsm_channel_t *ch)
{
    if (!ch) {
        return;
    }

    ch->presence_wander_history[ch->presence_write_index % HMS_PRESENCE_HISTORY_LEN] = ch->wander_value;
    ch->presence_write_index = (ch->presence_write_index + 1) % HMS_PRESENCE_HISTORY_LEN;
    ch->presence_total_samples++;
    ch->presence_ready = (ch->presence_total_samples >= HMS_PRESENCE_MIN_SAMPLES);

    if (ch->presence_ready) {
        ch->presence_wander_average = hms_trimmean(ch->presence_wander_history,
                                                   HMS_PRESENCE_HISTORY_LEN,
                                                   HMS_PRESENCE_TRIM_PERCENT);
    } else {
        ch->presence_wander_average = 0.0f;
    }

    const float gain = hms_presence_gain_from_unit(ch->user_cfg.presence_sensitivity);

    if (ch->train_thresholds_valid) {
        ch->presence_someone_threshold = ch->train_wander_thr / gain;
    } else {
        ch->presence_someone_threshold = 0.0f;
    }

    ch->presence_someone_status = ch->presence_ready &&
                                  ch->train_thresholds_valid &&
                                  ((ch->presence_wander_average * gain) > ch->train_wander_thr);
}

static void hms_emit_event(esp_wifi_sensing_fsm_t *fsm, esp_wifi_sensing_fsm_channel_t *ch, esp_wifi_sensing_fsm_event_t event, uint32_t data)
{
    /* Emit state changes as events so the application stays decoupled */
    if (!fsm || !ch || event >= ESP_WIFI_SENSING_FSM_EVENT_MAX) {
        return;
    }
    ch->last_event = event;

    if (!fsm->cb_info[event]) {
        return;
    }
    for (size_t i = 0; i < fsm->cb_size[event]; i++) {
        fsm->cb_info[event][i].cb((esp_wifi_sensing_fsm_handle_t)fsm, ch->peer_mac, event, data, fsm->cb_info[event][i].user_data);
    }
}

static esp_err_t hms_ping_get_gateway(esp_wifi_sensing_fsm_t *fsm, esp_ip4_addr_t *out_gw)
{
    /* Resolve the STA gateway once, then reuse the cached address */
    HMS_CHECK(fsm && out_gw, "invalid args", ESP_ERR_INVALID_ARG);

    if (fsm->ping_gw.addr != 0) {
        *out_gw = fsm->ping_gw;
        ESP_LOGI(TAG, "use cached gateway: " IPSTR, IP2STR(&fsm->ping_gw));
        return ESP_OK;
    }

    esp_netif_t *netif = esp_netif_get_handle_from_ifkey("WIFI_STA_DEF");
    ESP_RETURN_ON_FALSE(netif, ESP_ERR_INVALID_STATE, TAG, "WiFi STA netif not ready");

    esp_netif_ip_info_t ip_info = {0};
    ESP_RETURN_ON_FALSE(esp_netif_get_ip_info(netif, &ip_info) == ESP_OK, ESP_ERR_INVALID_STATE, TAG, "WiFi STA ip_info not ready");
    ESP_RETURN_ON_FALSE(ip_info.gw.addr != 0, ESP_ERR_INVALID_STATE, TAG, "WiFi STA has no valid gateway");

    fsm->ping_gw = ip_info.gw;
    *out_gw = fsm->ping_gw;
    ESP_LOGI(TAG, "gateway resolved: " IPSTR, IP2STR(&fsm->ping_gw));
    return ESP_OK;
}

static void hms_ping_on_success(esp_ping_handle_t hdl, void *args)
{
    (void)hdl;
    esp_wifi_sensing_fsm_t *fsm = (esp_wifi_sensing_fsm_t *)args;
    if (fsm) {
        fsm->ping_success_count++;
    }
}

static void hms_ping_on_timeout(esp_ping_handle_t hdl, void *args)
{
    esp_wifi_sensing_fsm_t *fsm = (esp_wifi_sensing_fsm_t *)args;
    uint16_t seqno = 0;
    esp_ping_get_profile(hdl, ESP_PING_PROF_SEQNO, &seqno, sizeof(seqno));
    if (fsm) {
        fsm->ping_timeout_count++;
    }
    ESP_LOGW(TAG, "ping timeout: seq=%u", seqno);
}

static void hms_ping_on_end(esp_ping_handle_t hdl, void *args)
{
    (void)args;
    uint32_t transmitted = 0;
    uint32_t received = 0;
    uint32_t total_time_ms = 0;
    esp_ping_get_profile(hdl, ESP_PING_PROF_REQUEST, &transmitted, sizeof(transmitted));
    esp_ping_get_profile(hdl, ESP_PING_PROF_REPLY, &received, sizeof(received));
    esp_ping_get_profile(hdl, ESP_PING_PROF_DURATION, &total_time_ms, sizeof(total_time_ms));
    ESP_LOGI(TAG, "ping session end: tx=%" PRIu32 " rx=%" PRIu32 " loss=%" PRIu32 "%% duration=%" PRIu32 " ms",
             transmitted, received, (transmitted == 0) ? 0 : ((transmitted - received) * 100U) / transmitted, total_time_ms);
}

static esp_err_t hms_ping_start(esp_wifi_sensing_fsm_t *fsm, uint32_t frequency_hz, esp_ip4_addr_t gw)
{
    /* Keep the link active with continuous ping so CSI samples stay continuous */
    HMS_CHECK(fsm, "invalid fsm", ESP_ERR_INVALID_ARG);
    HMS_CHECK(frequency_hz > 0, "invalid ping frequency", ESP_ERR_INVALID_ARG);
    if (fsm->ping_handle) {
        ESP_LOGW(TAG, "ping session already started, skip start");
        return ESP_OK;
    }

    esp_ping_config_t ping_config = ESP_PING_DEFAULT_CONFIG();
    ping_config.count = 0;
    ping_config.interval_ms = 1000U / frequency_hz;
    if (ping_config.interval_ms == 0) {
        ping_config.interval_ms = 1;
    }
    ping_config.task_stack_size = 3072;
    ping_config.data_size = 1;
    ping_config.target_addr.u_addr.ip4.addr = ip4_addr_get_u32(&gw);
    ping_config.target_addr.type = ESP_IPADDR_TYPE_V4;

    esp_ping_callbacks_t cbs = {
        .on_ping_success = hms_ping_on_success,
        .on_ping_timeout = hms_ping_on_timeout,
        .on_ping_end = hms_ping_on_end,
        .cb_args = fsm,
    };
    ESP_LOGI(TAG, "start ping session: target=" IPSTR ", hz=%" PRIu32 ", interval=%" PRIu32 " ms",
             IP2STR(&gw), frequency_hz, ping_config.interval_ms);
    ESP_RETURN_ON_ERROR(esp_ping_new_session(&ping_config, &cbs, &fsm->ping_handle), TAG, "esp_ping_new_session failed");
    esp_err_t err = esp_ping_start(fsm->ping_handle);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "esp_ping_start failed: %s", esp_err_to_name(err));
        esp_ping_delete_session(fsm->ping_handle);
        fsm->ping_handle = NULL;
        return err;
    }
    ESP_LOGI(TAG, "ping session started");
    return ESP_OK;
}

static esp_err_t hms_ping_stop(esp_wifi_sensing_fsm_t *fsm)
{
    HMS_CHECK(fsm, "invalid fsm", ESP_ERR_INVALID_ARG);
    if (!fsm->ping_handle) {
        ESP_LOGW(TAG, "ping session not started, skip stop");
        return ESP_OK;
    }
    ESP_LOGI(TAG, "stop ping session");
    esp_ping_stop(fsm->ping_handle);
    esp_ping_delete_session(fsm->ping_handle);
    fsm->ping_handle = NULL;
    ESP_LOGI(TAG, "ping session stopped");
    return ESP_OK;
}

static void hms_preprocess_channel(esp_wifi_sensing_fsm_t *fsm, esp_wifi_sensing_fsm_channel_t *ch, uint32_t raw)
{
    /* 1) Scale the raw value so later float coefficients do not lose precision */
    if (raw > (UINT32_MAX / HMS_SCALE_FACTOR)) {
        raw = UINT32_MAX / HMS_SCALE_FACTOR;
    }
    raw *= HMS_SCALE_FACTOR;
    ch->raw_processing = raw;

    if (ch->init_stage == ESP_WIFI_SENSING_FSM_INIT_STAGE_START) {
        int64_t now_us = esp_timer_get_time();
        if (ch->init_avg_start_us == 0) {
            ch->init_avg_start_us = now_us;
        }
        ch->init_avg_sum += raw;
        ch->init_avg_count++;
        ch->init_counter = ch->init_avg_count;

        if (((now_us - ch->init_avg_start_us) >= HMS_BASELINE_AVG_WINDOW_US) &&
                (ch->init_avg_count >= HMS_BASELINE_AVG_MIN_PACKETS)) {
            uint32_t avg_raw = (ch->init_avg_count > 0) ? (uint32_t)(ch->init_avg_sum / ch->init_avg_count) : raw;
            uint32_t avg_count = ch->init_avg_count;
            ch->gold_baseline_scaled = avg_raw;
            ch->baseline_scaled = avg_raw;
            ch->smooth_scaled = avg_raw;
            ch->noise_level_scaled = 0;
            ch->init_counter = 0;
            ch->init_avg_sum = 0;
            ch->init_avg_count = 0;
            ch->init_avg_start_us = 0;
            ch->reset_counter = 0;
            ch->gold_stable_counter = 0;
            ch->init_stage = ESP_WIFI_SENSING_FSM_INIT_STAGE_GOLD_FOUND;
            ESP_LOGI(TAG, "baseline averaged: mac=" MACSTR " baseline=%" PRIu32 " samples=%" PRIu32 " window=%" PRIu32 "ms min_packets=%" PRIu32,
                     MAC2STR(ch->peer_mac), ch->baseline_scaled, avg_count,
                     HMS_BASELINE_AVG_WINDOW_MS, HMS_BASELINE_AVG_MIN_PACKETS);
        }
        return;
    }

    /* 2) First-order smoothing to suppress high-frequency jitter */
    int32_t diff_raw_smooth = (int32_t)raw - (int32_t)ch->smooth_scaled;
    float smooth_coef = ch->cfg.smooth_coef;
    if (diff_raw_smooth < 0) {
        smooth_coef *= 2.0f;
        if (smooth_coef > 1.0f) {
            smooth_coef = 1.0f;
        }
    }
    ch->smooth_scaled = (uint32_t)((int32_t)ch->smooth_scaled + (int32_t)(diff_raw_smooth * smooth_coef));

    int32_t diff_smooth_baseline = (int32_t)ch->smooth_scaled - (int32_t)ch->baseline_scaled;
    if (ch->init_stage == ESP_WIFI_SENSING_FSM_INIT_STAGE_GOLD_FOUND) {
        if (!hms_within_noise_band(diff_smooth_baseline,
                                   hms_get_runtime_reference(ch),
                                   ch->cfg.noise_p,
                                   ch->cfg.noise_n)) {
            if (ch->cfg.reset_calibration && ++ch->reset_counter >= ch->cfg.reset_calibration) {
                hms_reset_channel_state(fsm, ch, true);
                hms_enter_init_stage(ch, ESP_WIFI_SENSING_FSM_INIT_STAGE_START, false);
            }
        } else {
            ch->reset_counter = 0;
            ch->init_stage = ESP_WIFI_SENSING_FSM_INIT_STAGE_STABLE;
        }
        return;
    }

    bool center_collapsed = hms_is_runtime_center_collapsed(ch);
    if (center_collapsed) {
        if (hms_recover_invalid_runtime_baseline(fsm, ch)) {
            return;
        }
    } else {
        ch->reset_counter = 0;
    }

    /* 3) Continuously update noise, working center, and long-term center independently */
    uint32_t center_reference = hms_get_runtime_reference(ch);
    bool background_like = hms_within_noise_band(diff_smooth_baseline,
                                                 center_reference,
                                                 ch->cfg.noise_p,
                                                 ch->cfg.noise_n);
    uint32_t residual_scaled = (uint32_t)abs(diff_smooth_baseline);
    hms_update_noise_level(ch, residual_scaled);

    if (background_like) {
        ch->gold_stable_counter++;
    } else {
        ch->gold_stable_counter = 0;
    }

    int32_t positive_limit = (int32_t)(center_reference * ch->cfg.noise_p);
    int32_t negative_limit = (int32_t)(center_reference * ch->cfg.noise_n);
    int32_t noise_limit = (int32_t)(ch->noise_level_scaled * ch->cfg.baseline_clamp_gain);
    if (noise_limit < (int32_t)HMS_SCALE_FACTOR) {
        noise_limit = HMS_SCALE_FACTOR;
    }
    if (positive_limit < noise_limit) {
        positive_limit = noise_limit;
    }
    if (negative_limit < noise_limit) {
        negative_limit = noise_limit;
    }

    int32_t limited_center_error = hms_clamp_i32(diff_smooth_baseline, -negative_limit, positive_limit);
    float baseline_runtime_coef = background_like ? ch->cfg.baseline_coef : (ch->cfg.baseline_coef * 0.25f);
    ch->baseline_scaled = hms_apply_center_step(ch->baseline_scaled, limited_center_error, baseline_runtime_coef);

    float gold_runtime_coef = background_like ? ch->cfg.gold_baseline_coef : (ch->cfg.gold_baseline_coef * 0.25f);
    hms_update_gold_baseline(ch, ch->baseline_scaled, gold_runtime_coef);
}

static void hms_process_channel_state(esp_wifi_sensing_fsm_t *fsm, esp_wifi_sensing_fsm_channel_t *ch)
{
    /*
     * Core state-transition logic:
     * - Input: current smooth/baseline, configured thresholds, debounce history
     * - Output: updated process_state, plus ACTIVE / INACTIVE events on boundary crossings
     *
     * Decision order:
     * 1) Compute diff
     * 2) Compute enter / exit thresholds
     * 3) Follow the active or inactive path for the current state
     * 4) Commit the transition after debounce is satisfied
     */
    /* diff = smoothed value - baseline; every later decision uses this */
    int32_t diff = (int32_t)ch->smooth_scaled - (int32_t)ch->baseline_scaled;
    uint8_t prev_state = ch->process_state;
    uint32_t prev_debounce = ch->debounce_counter;
    const char *transition_reason = NULL;

    if ((ch->last_diff > 0) != (diff > 0)) {
        /* Reset debounce when the signal direction flips so hits do not accumulate across signs */
        ch->debounce_counter = 0;
    }
    ch->last_diff = diff;

    const int64_t now_us = esp_timer_get_time();
    /* active_filter_ms is the minimum ACTIVE hold window, to avoid flapping on brief drops */
    const int64_t hold_us = (ch->cfg.active_filter_ms > 0) ? ((int64_t)ch->cfg.active_filter_ms * 1000LL) : 0;
    uint32_t threshold_reference = hms_get_runtime_reference(ch);
    int32_t enter_threshold = (int32_t)(ch->cfg.threshold_p * threshold_reference * (1.0f + ch->cfg.hysteresis_active)) +
                              (int32_t)(ch->noise_level_scaled * ch->cfg.noise_threshold_gain_enter);
    int32_t exit_threshold = (int32_t)(ch->cfg.threshold_p * threshold_reference * (1.0f - ch->cfg.hysteresis_inactive)) +
                             (int32_t)(ch->noise_level_scaled * ch->cfg.noise_threshold_gain_exit);
    ch->diff_scaled = diff;
    ch->enter_threshold = enter_threshold;
    ch->exit_threshold = exit_threshold;

    if (ch->init_stage != ESP_WIFI_SENSING_FSM_INIT_STAGE_STABLE) {
        ch->debounce_counter = 0;
        ch->last_diff = 0;
        return;
    }

    bool jitter_below_active_min = (ch->cfg.active_jitter_min > 0.0f) && (ch->jitter_value < ch->cfg.active_jitter_min);
    if (jitter_below_active_min) {
        if (ch->process_state == PROC_ACTIVE || ch->process_state == PROC_DEBOUNCE_INACTIVE) {
            hms_reset_channel_state(fsm, ch, true);
            transition_reason = "force_inactive_low_jitter";
        } else {
            ch->debounce_counter = 0;
            if (ch->process_state == PROC_DEBOUNCE_ACTIVE) {
                ch->process_state = PROC_IDLE;
                transition_reason = "active_blocked_low_jitter";
            }
        }
        ch->last_diff = 0;
        hms_log_state_change(fsm, ch, prev_state, transition_reason, diff,
                             enter_threshold, exit_threshold, prev_debounce, now_us);
        return;
    }

    if (ch->process_state == PROC_IDLE || ch->process_state == PROC_DEBOUNCE_ACTIVE) {
        /*
         * [Path A] IDLE / DEBOUNCE_ACTIVE
         * Goal: decide whether to enter ACTIVE
         *
         * Enter condition:
         * diff > threshold_p * baseline * (1 + hysteresis_active)
         *
         * Behavior:
         * - On hit: increment debounce and stay in PROC_DEBOUNCE_ACTIVE
         * - After debounce_active hits: enter PROC_ACTIVE and emit ACTIVE
         * - On miss: clear debounce (hits must be consecutive)
         */
        if (diff > enter_threshold) {
            ch->debounce_counter++;
            ch->process_state = PROC_DEBOUNCE_ACTIVE;
            transition_reason = "enter_active_debounce";
            if (ch->debounce_counter >= ch->cfg.debounce_active) {
                ch->debounce_counter = 0;
                ch->process_state = PROC_ACTIVE;
                ch->active_hold_until_us = now_us + hold_us;
                transition_reason = "active_confirmed";
                /* Convert the event payload back to the original scale */
                hms_emit_event(fsm, ch, ESP_WIFI_SENSING_FSM_EVENT_ACTIVE, ch->smooth_scaled / HMS_SCALE_FACTOR);
            }
        } else {
            ch->debounce_counter = 0;
            if (ch->process_state == PROC_DEBOUNCE_ACTIVE) {
                ch->process_state = PROC_IDLE;
                transition_reason = "active_debounce_cancelled";
            }
        }
    } else if (ch->process_state == PROC_ACTIVE || ch->process_state == PROC_DEBOUNCE_INACTIVE) {
        /*
         * [Path B] ACTIVE / DEBOUNCE_INACTIVE
         * Goal: decide whether to leave ACTIVE
         *
         * Step 1: hold window
         * - If now < active_hold_until_us, return (exit is blocked)
         *
         * Step 2: exit condition:
         * diff < threshold_p * baseline * (1 - hysteresis_inactive)
         *
         * Behavior:
         * - On hit: increment debounce and stay in PROC_DEBOUNCE_INACTIVE
         * - After debounce_inactive hits: enter PROC_IDLE and emit INACTIVE
         * - On miss: remain ACTIVE, refresh the hold deadline, and clear debounce
         */
        /* Do not leave ACTIVE while the hold window is still open */
        if (hold_us > 0 && now_us < ch->active_hold_until_us) {
            return;
        }
        /* Start inactive debounce after the exit threshold (with hysteresis) is crossed */
        if (diff < exit_threshold) {
            ch->debounce_counter++;
            ch->process_state = PROC_DEBOUNCE_INACTIVE;
            transition_reason = "enter_inactive_debounce";
            if (ch->debounce_counter >= ch->cfg.debounce_inactive) {
                ch->debounce_counter = 0;
                ch->process_state = PROC_IDLE;
                transition_reason = "inactive_confirmed";
                hms_emit_event(fsm, ch, ESP_WIFI_SENSING_FSM_EVENT_INACTIVE, ch->smooth_scaled / HMS_SCALE_FACTOR);
            }
        } else {
            /* Extend the hold only when the signal is strong enough to re-enter, so noise cannot keep ACTIVE alive. */
            if (hold_us > 0 && diff > enter_threshold) {
                ch->active_hold_until_us = now_us + hold_us;
            }
            ch->debounce_counter = 0;
            if (ch->process_state == PROC_DEBOUNCE_INACTIVE) {
                ch->process_state = PROC_ACTIVE;
                transition_reason = "inactive_debounce_cancelled";
            }
        }
    }

    hms_log_state_change(fsm, ch, prev_state, transition_reason, diff,
                         enter_threshold, exit_threshold, prev_debounce, now_us);
}

static void radar_cb_ex(void *ctx, const uint8_t mac[6], const wifi_radar_info_t *info)
{
    /* Radar decode callback: enqueue samples only; the task owns state decisions */
    esp_wifi_sensing_fsm_t *fsm = (esp_wifi_sensing_fsm_t *)ctx;
    if (!fsm || !mac || !info) {
        return;
    }
    if (xSemaphoreTake(fsm->mutex, 0) != pdTRUE) {
        /* Never block in the callback; drop the sample if the lock is busy */
        fsm->radar_drop_lock_count++;
        return;
    }
    fsm->radar_cb_count++;
    esp_wifi_sensing_fsm_channel_t *ch = hms_get_channel(fsm, mac);
    if (!ch || !ch->raw_buf) {
        fsm->radar_drop_no_channel_count++;
        xSemaphoreGive(fsm->mutex);
        return;
    }

    /* Compress the dynamic range with log1p, then quantize so low-amplitude background keeps resolution */
    float raw_jitter_value = info->waveform_jitter;
    ch->jitter_value = raw_jitter_value;
    ch->wander_value = info->waveform_wander;
    hms_update_presence_state(ch);
    uint32_t raw_feature = hms_encode_waveform_jitter(raw_jitter_value);

    /* Push into the ring buffer; overwrite the oldest sample when full */
    if (ch->raw_count >= fsm->config.raw_buf_size) {
        fsm->radar_overwrite_count++;
        ch->raw_read_index = (ch->raw_read_index + 1) % fsm->config.raw_buf_size;
        ch->raw_count--;
    }
    ch->raw_buf[ch->raw_write_index] = raw_feature;
    ch->raw_write_index = (ch->raw_write_index + 1) % fsm->config.raw_buf_size;
    ch->raw_count++;
    ESP_LOGD(TAG, "radar sample: mac=" MACSTR " jitter=%.3f raw=%" PRIu32 " queue=%" PRIu32,
             MAC2STR(mac), raw_jitter_value, raw_feature, ch->raw_count);

    xSemaphoreGive(fsm->mutex);
}

static esp_err_t hms_radar_apply_runtime_config_locked(esp_wifi_sensing_fsm_t *fsm)
{
    HMS_CHECK(fsm, "invalid fsm", ESP_ERR_INVALID_ARG);
    esp_radar_config_t radar_config = ESP_RADAR_CONFIG_DEFAULT();
    ESP_RETURN_ON_ERROR(esp_radar_get_config(&radar_config), TAG, "esp_radar_get_config failed");
    if (radar_config.dec_config.amplitude_log_enabled == fsm->radar_amplitude_log_enabled) {
        return ESP_OK;
    }
    radar_config.dec_config.amplitude_log_enabled = fsm->radar_amplitude_log_enabled;
    ESP_RETURN_ON_ERROR(esp_radar_change_config(&radar_config), TAG, "esp_radar_change_config failed");
    return ESP_OK;
}

static esp_err_t hms_radar_start(esp_wifi_sensing_fsm_t *fsm)
{
    /* Initialize CSI and radar decode, then attach the extended callback */
    if (fsm->radar_started) {
        return ESP_OK;
    }
    esp_radar_set_log_output(true, ESP_LOG_WARN);

    esp_radar_csi_config_t csi_config = ESP_RADAR_CSI_CONFIG_DEFAULT();
    csi_config.csi_recv_interval = 20;

    esp_radar_dec_config_t dec_config = ESP_RADAR_DEC_CONFIG_DEFAULT();
    dec_config.wifi_radar_cb = NULL;
    dec_config.wifi_radar_cb_ctx = NULL;
    dec_config.wifi_radar_cb_ex = radar_cb_ex;
    dec_config.wifi_radar_cb_ex_ctx = fsm;
    dec_config.ltf_type = RADAR_LTF_TYPE_LLTF;
    dec_config.amplitude_log_enabled = fsm->radar_amplitude_log_enabled;

    ESP_RETURN_ON_ERROR(esp_radar_csi_init(&csi_config), TAG, "esp_radar_csi_init failed");
    ESP_RETURN_ON_ERROR(esp_radar_dec_init(&dec_config), TAG, "esp_radar_dec_init failed");
    ESP_RETURN_ON_ERROR(esp_radar_start(), TAG, "esp_radar_start failed");

    fsm->radar_started = true;
    ESP_LOGI(TAG, "radar started: csi_interval=%u ltf_type=%d", csi_config.csi_recv_interval, dec_config.ltf_type);
    return ESP_OK;
}

static void hms_radar_stop(esp_wifi_sensing_fsm_t *fsm)
{
    if (!fsm || !fsm->radar_started) {
        return;
    }
    (void)hms_ping_stop(fsm);
    esp_radar_stop();
    esp_radar_deinit();
    fsm->radar_started = false;
}

static void hms_task_entry(void *arg)
{
    /* Background polling task: consume samples and advance the FSM periodically */
    esp_wifi_sensing_fsm_t *fsm = (esp_wifi_sensing_fsm_t *)arg;
    while (!fsm->task_should_exit) {
        if (fsm->is_running) {
            (void)esp_wifi_sensing_fsm_handle_events((esp_wifi_sensing_fsm_handle_t)fsm);
            int64_t now_us = esp_timer_get_time();
            if (fsm->diag_last_log_us == 0) {
                fsm->diag_last_log_us = now_us;
            } else if ((now_us - fsm->diag_last_log_us) >= ((int64_t)HMS_DIAG_LOG_PERIOD_MS * 1000LL)) {
                uint32_t queued_total = 0;
                uint32_t used_channels = 0;
                int64_t diag_elapsed_us = now_us - fsm->diag_last_log_us;
                xSemaphoreTake(fsm->mutex, portMAX_DELAY);
                for (uint32_t i = 0; i < fsm->config.max_channel_num; i++) {
                    esp_wifi_sensing_fsm_channel_t *ch = fsm->channels[i];
                    if (!ch || !ch->used) {
                        continue;
                    }
                    used_channels++;
                    queued_total += ch->raw_count;
                }
                uint32_t ping_ok = fsm->ping_success_count;
                uint32_t ping_to = fsm->ping_timeout_count;
                uint32_t radar_cb = fsm->radar_cb_count;
                uint32_t radar_drop_lock = fsm->radar_drop_lock_count;
                uint32_t radar_drop_no_channel = fsm->radar_drop_no_channel_count;
                uint32_t radar_ovw = fsm->radar_overwrite_count;
                uint32_t radar_proc = fsm->radar_processed_count;
                xSemaphoreGive(fsm->mutex);

                uint32_t d_ping_ok = ping_ok - fsm->diag_prev_ping_success_count;
                uint32_t d_ping_to = ping_to - fsm->diag_prev_ping_timeout_count;
                uint32_t d_radar_cb = radar_cb - fsm->diag_prev_radar_cb_count;
                uint32_t d_radar_drop_lock = radar_drop_lock - fsm->diag_prev_radar_drop_lock_count;
                uint32_t d_radar_drop_no_channel = radar_drop_no_channel - fsm->diag_prev_radar_drop_no_channel_count;
                uint32_t d_radar_ovw = radar_ovw - fsm->diag_prev_radar_overwrite_count;
                uint32_t d_radar_proc = radar_proc - fsm->diag_prev_radar_processed_count;
                float ping_reply_hz = (diag_elapsed_us > 0) ? ((float)d_ping_ok * 1000000.0f / (float)diag_elapsed_us) : 0.0f;

                fsm->diag_prev_ping_success_count = ping_ok;
                fsm->diag_prev_ping_timeout_count = ping_to;
                fsm->diag_prev_radar_cb_count = radar_cb;
                fsm->diag_prev_radar_drop_lock_count = radar_drop_lock;
                fsm->diag_prev_radar_drop_no_channel_count = radar_drop_no_channel;
                fsm->diag_prev_radar_overwrite_count = radar_ovw;
                fsm->diag_prev_radar_processed_count = radar_proc;
                fsm->diag_last_log_us = now_us;

                if (d_radar_cb == 0) {
                    ESP_LOGW(TAG, "diag(%ums): radar idle? channels=%" PRIu32 " queue=%" PRIu32 " ping_ok=%" PRIu32 " ping_to=%" PRIu32 " ping_reply_hz=%.2f",
                             HMS_DIAG_LOG_PERIOD_MS, used_channels, queued_total, d_ping_ok, d_ping_to, ping_reply_hz);
                } else {
                    ESP_LOGD(TAG, "diag(%ums): radar_cb=%" PRIu32 " proc=%" PRIu32 " queue=%" PRIu32 " drop_lock=%" PRIu32 " drop_no_ch=%" PRIu32 " ovw=%" PRIu32 " ping_ok=%" PRIu32 " ping_to=%" PRIu32 " ping_reply_hz=%.2f",
                             HMS_DIAG_LOG_PERIOD_MS, d_radar_cb, d_radar_proc, queued_total, d_radar_drop_lock, d_radar_drop_no_channel, d_radar_ovw, d_ping_ok, d_ping_to, ping_reply_hz);
                }
            }
        }
        vTaskDelay(pdMS_TO_TICKS(fsm->config.polling_interval));
    }
    fsm->task = NULL;
    vTaskDelete(NULL);
}

esp_err_t esp_wifi_sensing_fsm_create(const esp_wifi_sensing_fsm_config_t *config, esp_wifi_sensing_fsm_handle_t *handle)
{
    /* Create order: validate args -> allocate -> start radar -> create the task */
    HMS_CHECK(config && handle, "invalid args", ESP_ERR_INVALID_ARG);
    HMS_CHECK(config->max_channel_num > 0, "invalid max_channel_num", ESP_ERR_INVALID_ARG);
    HMS_CHECK(config->raw_buf_size > 0, "invalid raw_buf_size", ESP_ERR_INVALID_ARG);
    HMS_CHECK(config->polling_interval > 0, "invalid polling_interval", ESP_ERR_INVALID_ARG);
    if (s_active_fsm) {
        return ESP_ERR_INVALID_STATE;
    }

    esp_wifi_sensing_fsm_t *fsm = calloc(1, sizeof(esp_wifi_sensing_fsm_t));
    HMS_CHECK(fsm, "alloc fsm failed", ESP_ERR_NO_MEM);
    fsm->config = *config;
    hms_normalize_channel_config(&fsm->config.default_channel_config);
    fsm->ping_frequency_hz = (config->ping_frequency_hz > 0) ? config->ping_frequency_hz : hms_get_default_ping_frequency_hz();
    fsm->config.ping_frequency_hz = fsm->ping_frequency_hz;
    fsm->radar_amplitude_log_enabled = true;

    fsm->channels = calloc(config->max_channel_num, sizeof(esp_wifi_sensing_fsm_channel_t *));
    if (!fsm->channels) {
        free(fsm);
        return ESP_ERR_NO_MEM;
    }

    fsm->mutex = xSemaphoreCreateMutex();
    if (!fsm->mutex) {
        free(fsm->channels);
        free(fsm);
        return ESP_ERR_NO_MEM;
    }

    esp_err_t err = hms_radar_start(fsm);
    if (err != ESP_OK) {
        vSemaphoreDelete(fsm->mutex);
        free(fsm->channels);
        free(fsm);
        return err;
    }

    BaseType_t ok = xTaskCreate(hms_task_entry, "esp_wifi_sensing_fsm", 4096, fsm, 5, &fsm->task);
    if (ok != pdPASS) {
        hms_radar_stop(fsm);
        vSemaphoreDelete(fsm->mutex);
        free(fsm->channels);
        free(fsm);
        return ESP_FAIL;
    }

    fsm->is_running = false;
    s_active_fsm = fsm;
    *handle = (esp_wifi_sensing_fsm_handle_t)fsm;
    return ESP_OK;
}

esp_err_t esp_wifi_sensing_fsm_delete(esp_wifi_sensing_fsm_handle_t handle)
{
    /* Tear down in reverse of create so peripherals and memory are fully released */
    HMS_CHECK(handle, "invalid handle", ESP_ERR_INVALID_ARG);
    esp_wifi_sensing_fsm_t *fsm = (esp_wifi_sensing_fsm_t *)handle;

    if (fsm->task) {
        fsm->task_should_exit = true;
        vTaskDelay(pdMS_TO_TICKS(20));
        if (fsm->task) {
            vTaskDelete(fsm->task);
            fsm->task = NULL;
        }
    }

    hms_radar_stop(fsm);

    for (uint32_t i = 0; i < fsm->config.max_channel_num; i++) {
        esp_wifi_sensing_fsm_channel_t *ch = fsm->channels[i];
        if (!ch) {
            continue;
        }
        /* hms_radar_stop() already deinitializes radar and frees all peer handles. */
        ch->peer_handle = NULL;
        free(ch->raw_buf);
        free(ch);
        fsm->channels[i] = NULL;
    }
    for (int i = 0; i < ESP_WIFI_SENSING_FSM_EVENT_MAX; i++) {
        free(fsm->cb_info[i]);
    }

    if (fsm->mutex) {
        vSemaphoreDelete(fsm->mutex);
    }
    free(fsm->channels);
    if (s_active_fsm == fsm) {
        s_active_fsm = NULL;
    }
    free(fsm);
    return ESP_OK;
}

esp_err_t esp_wifi_sensing_fsm_add_channel(esp_wifi_sensing_fsm_handle_t handle, const uint8_t peer_mac[6])
{
    /* Add a peer channel: allocate the ring buffer and register the radar peer */
    HMS_CHECK(handle && peer_mac, "invalid args", ESP_ERR_INVALID_ARG);
    esp_wifi_sensing_fsm_t *fsm = (esp_wifi_sensing_fsm_t *)handle;
    xSemaphoreTake(fsm->mutex, portMAX_DELAY);

    if (hms_get_channel(fsm, peer_mac) != NULL) {
        xSemaphoreGive(fsm->mutex);
        return ESP_ERR_INVALID_STATE;
    }

    uint32_t idx = UINT32_MAX;
    for (uint32_t i = 0; i < fsm->config.max_channel_num; i++) {
        if (!fsm->channels[i]) {
            idx = i;
            break;
        }
    }
    if (idx == UINT32_MAX) {
        xSemaphoreGive(fsm->mutex);
        return ESP_ERR_NO_MEM;
    }

    esp_wifi_sensing_fsm_channel_t *ch = calloc(1, sizeof(*ch));
    if (!ch) {
        xSemaphoreGive(fsm->mutex);
        return ESP_ERR_NO_MEM;
    }
    ch->raw_buf = calloc(fsm->config.raw_buf_size, sizeof(uint32_t));
    if (!ch->raw_buf) {
        free(ch);
        xSemaphoreGive(fsm->mutex);
        return ESP_ERR_NO_MEM;
    }
    ch->user_cfg = fsm->config.default_channel_config;
    hms_expand_channel_config(&ch->user_cfg, &ch->cfg);
    ch->used = true;
    hms_enter_init_stage(ch, ESP_WIFI_SENSING_FSM_INIT_STAGE_START, true);
    memcpy(ch->peer_mac, peer_mac, 6);

    esp_err_t err = esp_radar_new_peer(peer_mac, &ch->peer_handle);
    if (err != ESP_OK) {
        free(ch->raw_buf);
        free(ch);
        xSemaphoreGive(fsm->mutex);
        return err;
    }
    fsm->channels[idx] = ch;

    xSemaphoreGive(fsm->mutex);
    return ESP_OK;
}

esp_err_t esp_wifi_sensing_fsm_remove_channel(esp_wifi_sensing_fsm_handle_t handle, const uint8_t peer_mac[6])
{
    /* Remove the radar peer first, then free the local channel state */
    HMS_CHECK(handle && peer_mac, "invalid args", ESP_ERR_INVALID_ARG);
    esp_wifi_sensing_fsm_t *fsm = (esp_wifi_sensing_fsm_t *)handle;
    xSemaphoreTake(fsm->mutex, portMAX_DELAY);
    esp_wifi_sensing_fsm_channel_t *ch = hms_get_channel(fsm, peer_mac);
    if (!ch) {
        xSemaphoreGive(fsm->mutex);
        return ESP_ERR_NOT_FOUND;
    }
    if (ch->peer_handle) {
        esp_radar_stop();
        (void)esp_radar_del_peer(ch->peer_handle);
        ch->peer_handle = NULL;
        esp_radar_start();
    }
    free(ch->raw_buf);
    for (uint32_t i = 0; i < fsm->config.max_channel_num; i++) {
        if (fsm->channels[i] == ch) {
            fsm->channels[i] = NULL;
            break;
        }
    }
    free(ch);
    xSemaphoreGive(fsm->mutex);
    return ESP_OK;
}

esp_err_t esp_wifi_sensing_fsm_update_data(esp_wifi_sensing_fsm_handle_t handle, const uint8_t peer_mac[6], uint32_t raw_data)
{
    /* Manual feed API: enqueue the same way as the radar callback */
    HMS_CHECK(handle && peer_mac, "invalid args", ESP_ERR_INVALID_ARG);
    esp_wifi_sensing_fsm_t *fsm = (esp_wifi_sensing_fsm_t *)handle;
    xSemaphoreTake(fsm->mutex, portMAX_DELAY);
    esp_wifi_sensing_fsm_channel_t *ch = hms_get_channel(fsm, peer_mac);
    if (!ch) {
        xSemaphoreGive(fsm->mutex);
        return ESP_ERR_NOT_FOUND;
    }
    if (ch->raw_count >= fsm->config.raw_buf_size) {
        ch->raw_read_index = (ch->raw_read_index + 1) % fsm->config.raw_buf_size;
        ch->raw_count--;
    }
    ch->raw_buf[ch->raw_write_index] = raw_data;
    ch->raw_write_index = (ch->raw_write_index + 1) % fsm->config.raw_buf_size;
    ch->raw_count++;
    xSemaphoreGive(fsm->mutex);
    return ESP_OK;
}

esp_err_t esp_wifi_sensing_fsm_get_state(esp_wifi_sensing_fsm_handle_t handle, const uint8_t peer_mac[6], esp_wifi_sensing_fsm_state_t *state)
{
    /* Public state is only INACTIVE / DEBOUNCE / ACTIVE */
    HMS_CHECK(handle && peer_mac && state, "invalid args", ESP_ERR_INVALID_ARG);
    esp_wifi_sensing_fsm_t *fsm = (esp_wifi_sensing_fsm_t *)handle;
    xSemaphoreTake(fsm->mutex, portMAX_DELAY);
    esp_wifi_sensing_fsm_channel_t *ch = hms_get_channel(fsm, peer_mac);
    if (!ch) {
        xSemaphoreGive(fsm->mutex);
        return ESP_ERR_NOT_FOUND;
    }
    if (ch->debounce_counter > 0) {
        *state = ESP_WIFI_SENSING_FSM_STATE_DEBOUNCE;
    } else if (ch->process_state == PROC_ACTIVE) {
        *state = ESP_WIFI_SENSING_FSM_STATE_ACTIVE;
    } else {
        *state = ESP_WIFI_SENSING_FSM_STATE_INACTIVE;
    }
    xSemaphoreGive(fsm->mutex);
    return ESP_OK;
}

esp_err_t esp_wifi_sensing_fsm_get_channel_diag(esp_wifi_sensing_fsm_handle_t handle, const uint8_t peer_mac[6], esp_wifi_sensing_fsm_channel_diag_t *diag)
{
    HMS_CHECK(handle && peer_mac && diag, "invalid args", ESP_ERR_INVALID_ARG);
    esp_wifi_sensing_fsm_t *fsm = (esp_wifi_sensing_fsm_t *)handle;
    xSemaphoreTake(fsm->mutex, portMAX_DELAY);
    esp_wifi_sensing_fsm_channel_t *ch = hms_get_channel(fsm, peer_mac);
    if (!ch) {
        xSemaphoreGive(fsm->mutex);
        return ESP_ERR_NOT_FOUND;
    }

    uint64_t enter_level_scaled = (uint64_t)ch->baseline_scaled +
                                  (uint64_t)((ch->enter_threshold > 0) ? ch->enter_threshold : 0);
    uint64_t exit_level_scaled = (uint64_t)ch->baseline_scaled +
                                 (uint64_t)((ch->exit_threshold > 0) ? ch->exit_threshold : 0);
    esp_radar_train_diag_t train_diag = {0};
    bool train_diag_ok = (ch->peer_handle && esp_radar_train_get_diag_ex(ch->peer_handle, &train_diag) == ESP_OK);

    memset(diag, 0, sizeof(*diag));
    diag->jitter_value = ch->jitter_value;
    diag->smooth_scaled = ch->smooth_scaled;
    diag->enter_level_scaled = (enter_level_scaled > UINT32_MAX) ? UINT32_MAX : (uint32_t)enter_level_scaled;
    diag->exit_level_scaled = (exit_level_scaled > UINT32_MAX) ? UINT32_MAX : (uint32_t)exit_level_scaled;
    diag->state = (esp_wifi_sensing_fsm_process_state_t)ch->process_state;
    diag->init_stage = ch->init_stage;
    diag->wander_value = ch->wander_value;
    diag->train_wander_threshold = ch->train_wander_thr;
    diag->train_jitter_threshold = ch->train_jitter_thr;
    diag->train_thresholds_valid = ch->train_thresholds_valid;
    diag->train_status = train_diag_ok ? hms_map_train_status(train_diag.status) : ESP_WIFI_SENSING_FSM_TRAIN_STATUS_NONE;
    diag->train_last_action = train_diag_ok ? hms_map_train_action(train_diag.last_action) : ESP_WIFI_SENSING_FSM_TRAIN_ACTION_IDLE;
    diag->train_sample_count = train_diag_ok ? train_diag.template_sample_count : 0;
    diag->train_background_count = train_diag_ok ? train_diag.background_stats_count : 0;
    diag->train_background_avg = train_diag_ok ? train_diag.background_stats_avg : 0.0f;
    diag->train_last_basis_wander = train_diag_ok ? train_diag.last_basis_wander : 0.0f;
    diag->presence_ready = ch->presence_ready;
    diag->presence_wander_average = ch->presence_wander_average;
    diag->presence_someone_threshold = ch->presence_someone_threshold;
    diag->presence_someone_status = ch->presence_someone_status;
    xSemaphoreGive(fsm->mutex);
    return ESP_OK;
}

esp_err_t esp_wifi_sensing_fsm_set_channel_config(esp_wifi_sensing_fsm_handle_t handle, const uint8_t peer_mac[6], const esp_wifi_sensing_fsm_channel_config_t *config)
{
    HMS_CHECK(handle && peer_mac && config, "invalid args", ESP_ERR_INVALID_ARG);
    esp_wifi_sensing_fsm_t *fsm = (esp_wifi_sensing_fsm_t *)handle;
    xSemaphoreTake(fsm->mutex, portMAX_DELAY);
    esp_wifi_sensing_fsm_channel_t *ch = hms_get_channel(fsm, peer_mac);
    if (!ch) {
        xSemaphoreGive(fsm->mutex);
        return ESP_ERR_NOT_FOUND;
    }
    esp_wifi_sensing_fsm_channel_config_t prev_cfg = ch->user_cfg;
    esp_wifi_sensing_fsm_channel_config_t normalized = *config;
    hms_normalize_channel_config(&normalized);
    bool sensitivity_changed = fabsf(normalized.sensitivity - prev_cfg.sensitivity) > 0.000001f;
    bool presence_sens_changed = fabsf(normalized.presence_sensitivity - prev_cfg.presence_sensitivity) > 0.000001f;
    ch->user_cfg = normalized;
    hms_expand_channel_config(&ch->user_cfg, &ch->cfg);
    if (sensitivity_changed) {
        hms_reset_channel_state(fsm, ch, true);
        hms_enter_init_stage(ch, ESP_WIFI_SENSING_FSM_INIT_STAGE_START, true);
    } else if (presence_sens_changed) {
        const float gain = hms_presence_gain_from_unit(ch->user_cfg.presence_sensitivity);
        if (ch->train_thresholds_valid) {
            ch->presence_someone_threshold = ch->train_wander_thr / gain;
        } else {
            ch->presence_someone_threshold = 0.0f;
        }
        ch->presence_someone_status = ch->presence_ready && ch->train_thresholds_valid &&
                                      ((ch->presence_wander_average * gain) > ch->train_wander_thr);
    }
    xSemaphoreGive(fsm->mutex);
    return ESP_OK;
}

esp_err_t esp_wifi_sensing_fsm_set_amplitude_log_enabled(esp_wifi_sensing_fsm_handle_t handle, bool enabled)
{
    HMS_CHECK(handle, "invalid handle", ESP_ERR_INVALID_ARG);
    esp_wifi_sensing_fsm_t *fsm = (esp_wifi_sensing_fsm_t *)handle;
    xSemaphoreTake(fsm->mutex, portMAX_DELAY);
    bool prev_enabled = fsm->radar_amplitude_log_enabled;
    if (prev_enabled == enabled) {
        xSemaphoreGive(fsm->mutex);
        return ESP_OK;
    }
    fsm->radar_amplitude_log_enabled = enabled;
    esp_err_t err = ESP_OK;
    if (fsm->radar_started) {
        err = hms_radar_apply_runtime_config_locked(fsm);
        if (err != ESP_OK) {
            fsm->radar_amplitude_log_enabled = prev_enabled;
        }
    }
    xSemaphoreGive(fsm->mutex);
    if (err == ESP_OK) {
        ESP_LOGI(TAG, "radar amplitude_log_enabled=%d", enabled);
    }
    return err;
}

esp_err_t esp_wifi_sensing_fsm_get_amplitude_log_enabled(esp_wifi_sensing_fsm_handle_t handle, bool *enabled)
{
    HMS_CHECK(handle && enabled, "invalid args", ESP_ERR_INVALID_ARG);
    esp_wifi_sensing_fsm_t *fsm = (esp_wifi_sensing_fsm_t *)handle;
    xSemaphoreTake(fsm->mutex, portMAX_DELAY);
    *enabled = fsm->radar_amplitude_log_enabled;
    xSemaphoreGive(fsm->mutex);
    return ESP_OK;
}

esp_err_t esp_wifi_sensing_fsm_get_channel_config(esp_wifi_sensing_fsm_handle_t handle, const uint8_t peer_mac[6], esp_wifi_sensing_fsm_channel_config_t *config)
{
    HMS_CHECK(handle && peer_mac && config, "invalid args", ESP_ERR_INVALID_ARG);
    esp_wifi_sensing_fsm_t *fsm = (esp_wifi_sensing_fsm_t *)handle;
    xSemaphoreTake(fsm->mutex, portMAX_DELAY);
    esp_wifi_sensing_fsm_channel_t *ch = hms_get_channel(fsm, peer_mac);
    if (!ch) {
        xSemaphoreGive(fsm->mutex);
        return ESP_ERR_NOT_FOUND;
    }
    *config = ch->user_cfg;
    xSemaphoreGive(fsm->mutex);
    return ESP_OK;
}

esp_err_t esp_wifi_sensing_fsm_train_start(esp_wifi_sensing_fsm_handle_t handle, const uint8_t peer_mac[6])
{
    HMS_CHECK(handle && peer_mac, "invalid args", ESP_ERR_INVALID_ARG);
    esp_wifi_sensing_fsm_t *fsm = (esp_wifi_sensing_fsm_t *)handle;
    xSemaphoreTake(fsm->mutex, portMAX_DELAY);
    esp_wifi_sensing_fsm_channel_t *ch = hms_get_channel(fsm, peer_mac);
    esp_radar_handle_t peer_handle = (ch && ch->peer_handle) ? ch->peer_handle : NULL;
    xSemaphoreGive(fsm->mutex);
    if (!peer_handle) {
        return ESP_ERR_NOT_FOUND;
    }
    esp_err_t err = esp_radar_train_start_ex(peer_handle);
    if (err == ESP_OK) {
        xSemaphoreTake(fsm->mutex, portMAX_DELAY);
        ch = hms_get_channel(fsm, peer_mac);
        if (ch) {
            hms_reset_presence_state(ch);
        }
        xSemaphoreGive(fsm->mutex);
    }
    return err;
}

esp_err_t esp_wifi_sensing_fsm_train_stop(esp_wifi_sensing_fsm_handle_t handle, const uint8_t peer_mac[6],
                                          float *wander_threshold, float *jitter_threshold)
{
    HMS_CHECK(handle && peer_mac, "invalid args", ESP_ERR_INVALID_ARG);
    esp_wifi_sensing_fsm_t *fsm = (esp_wifi_sensing_fsm_t *)handle;
    xSemaphoreTake(fsm->mutex, portMAX_DELAY);
    esp_wifi_sensing_fsm_channel_t *ch = hms_get_channel(fsm, peer_mac);
    esp_radar_handle_t peer_handle = (ch && ch->peer_handle) ? ch->peer_handle : NULL;
    xSemaphoreGive(fsm->mutex);
    if (!peer_handle) {
        return ESP_ERR_NOT_FOUND;
    }

    float wander_out = 0.0f;
    float jitter_out = 0.0f;
    esp_err_t err = esp_radar_train_stop_ex(peer_handle, &wander_out, &jitter_out);

    xSemaphoreTake(fsm->mutex, portMAX_DELAY);
    ch = hms_get_channel(fsm, peer_mac);
    if (ch) {
        if (err == ESP_OK) {
            const float gain = hms_presence_gain_from_unit(ch->user_cfg.presence_sensitivity);
            ch->train_wander_thr = wander_out;
            ch->train_jitter_thr = jitter_out;
            ch->train_thresholds_valid = true;
            ch->presence_someone_threshold = wander_out / gain;
            ch->presence_someone_status = ch->presence_ready &&
                                          ((ch->presence_wander_average * gain) > wander_out);
        }
    }
    xSemaphoreGive(fsm->mutex);

    if (wander_threshold) {
        *wander_threshold = wander_out;
    }
    if (jitter_threshold) {
        *jitter_threshold = jitter_out;
    }
    return err;
}

esp_err_t esp_wifi_sensing_fsm_train_remove(esp_wifi_sensing_fsm_handle_t handle, const uint8_t peer_mac[6])
{
    HMS_CHECK(handle && peer_mac, "invalid args", ESP_ERR_INVALID_ARG);
    esp_wifi_sensing_fsm_t *fsm = (esp_wifi_sensing_fsm_t *)handle;
    xSemaphoreTake(fsm->mutex, portMAX_DELAY);
    esp_wifi_sensing_fsm_channel_t *ch = hms_get_channel(fsm, peer_mac);
    esp_radar_handle_t peer_handle = (ch && ch->peer_handle) ? ch->peer_handle : NULL;
    xSemaphoreGive(fsm->mutex);
    if (!peer_handle) {
        return ESP_ERR_NOT_FOUND;
    }

    esp_err_t err = esp_radar_train_remove_ex(peer_handle);

    xSemaphoreTake(fsm->mutex, portMAX_DELAY);
    ch = hms_get_channel(fsm, peer_mac);
    if (ch) {
        ch->train_thresholds_valid = false;
        ch->train_wander_thr = 0.0f;
        ch->train_jitter_thr = 0.0f;
        hms_reset_presence_state(ch);
    }
    xSemaphoreGive(fsm->mutex);
    return err;
}

esp_err_t esp_wifi_sensing_fsm_register_event_cb(esp_wifi_sensing_fsm_handle_t handle, esp_wifi_sensing_fsm_event_t event, esp_wifi_sensing_fsm_event_cb_t cb, void *user_data)
{
    /* Multiple callbacks per event; grow the array as needed */
    HMS_CHECK(handle && cb, "invalid args", ESP_ERR_INVALID_ARG);
    HMS_CHECK(event < ESP_WIFI_SENSING_FSM_EVENT_MAX, "invalid event", ESP_ERR_INVALID_ARG);
    esp_wifi_sensing_fsm_t *fsm = (esp_wifi_sensing_fsm_t *)handle;
    xSemaphoreTake(fsm->mutex, portMAX_DELAY);
    size_t sz = fsm->cb_size[event];
    hms_cb_info_t *new_buf = realloc(fsm->cb_info[event], (sz + 1) * sizeof(hms_cb_info_t));
    if (!new_buf) {
        xSemaphoreGive(fsm->mutex);
        return ESP_ERR_NO_MEM;
    }
    fsm->cb_info[event] = new_buf;
    fsm->cb_info[event][sz].cb = cb;
    fsm->cb_info[event][sz].user_data = user_data;
    fsm->cb_size[event]++;
    xSemaphoreGive(fsm->mutex);
    return ESP_OK;
}

esp_err_t esp_wifi_sensing_fsm_unregister_event_cb(esp_wifi_sensing_fsm_handle_t handle, esp_wifi_sensing_fsm_event_t event)
{
    HMS_CHECK(handle, "invalid handle", ESP_ERR_INVALID_ARG);
    HMS_CHECK(event < ESP_WIFI_SENSING_FSM_EVENT_MAX, "invalid event", ESP_ERR_INVALID_ARG);
    esp_wifi_sensing_fsm_t *fsm = (esp_wifi_sensing_fsm_t *)handle;
    xSemaphoreTake(fsm->mutex, portMAX_DELAY);
    free(fsm->cb_info[event]);
    fsm->cb_info[event] = NULL;
    fsm->cb_size[event] = 0;
    xSemaphoreGive(fsm->mutex);
    return ESP_OK;
}

esp_err_t esp_wifi_sensing_fsm_control(esp_wifi_sensing_fsm_handle_t handle, esp_wifi_sensing_fsm_ctrl_t ctrl, void *ctrl_param)
{
    /* Control API for runtime state and baseline reset */
    (void)ctrl_param;
    HMS_CHECK(handle, "invalid handle", ESP_ERR_INVALID_ARG);
    esp_wifi_sensing_fsm_t *fsm = (esp_wifi_sensing_fsm_t *)handle;
    xSemaphoreTake(fsm->mutex, portMAX_DELAY);
    switch (ctrl) {
    case ESP_WIFI_SENSING_FSM_CTRL_START:
        /* Reset every channel decision state before start so leftover history cannot leak */
        for (uint32_t i = 0; i < fsm->config.max_channel_num; i++) {
            esp_wifi_sensing_fsm_channel_t *ch = fsm->channels[i];
            if (!ch || !ch->used) {
                continue;
            }
            hms_reset_channel_state(fsm, ch, true);
            hms_enter_init_stage(ch, ESP_WIFI_SENSING_FSM_INIT_STAGE_START, true);
            ch->raw_processing = 0;
            ch->diff_scaled = 0;
            ch->enter_threshold = 0;
            ch->exit_threshold = 0;
        }
        fsm->ping_success_count = 0;
        fsm->ping_timeout_count = 0;
        fsm->radar_cb_count = 0;
        fsm->radar_drop_lock_count = 0;
        fsm->radar_drop_no_channel_count = 0;
        fsm->radar_overwrite_count = 0;
        fsm->radar_processed_count = 0;
        fsm->diag_prev_ping_success_count = 0;
        fsm->diag_prev_ping_timeout_count = 0;
        fsm->diag_prev_radar_cb_count = 0;
        fsm->diag_prev_radar_drop_lock_count = 0;
        fsm->diag_prev_radar_drop_no_channel_count = 0;
        fsm->diag_prev_radar_overwrite_count = 0;
        fsm->diag_prev_radar_processed_count = 0;
        fsm->diag_last_log_us = 0;
        fsm->is_running = true;
        ESP_LOGI(TAG, "fsm start: channels=%" PRIu32 " poll=%" PRIu32 "ms", fsm->config.max_channel_num, fsm->config.polling_interval);
        break;
    case ESP_WIFI_SENSING_FSM_CTRL_STOP:
        fsm->is_running = false;
        break;
    case ESP_WIFI_SENSING_FSM_CTRL_RESET_BASELINE:
        /* Re-enter the averaging baseline procedure instead of seeding from an instantaneous sample */
        for (uint32_t i = 0; i < fsm->config.max_channel_num; i++) {
            esp_wifi_sensing_fsm_channel_t *ch = fsm->channels[i];
            if (!ch || !ch->used) {
                continue;
            }
            hms_reset_channel_state(fsm, ch, true);
            hms_enter_init_stage(ch, ESP_WIFI_SENSING_FSM_INIT_STAGE_START, true);
        }
        break;
    default:
        xSemaphoreGive(fsm->mutex);
        return ESP_ERR_INVALID_ARG;
    }
    xSemaphoreGive(fsm->mutex);
    return ESP_OK;
}

esp_err_t esp_wifi_sensing_fsm_handle_events(esp_wifi_sensing_fsm_handle_t handle)
{
    /* Core processing entry: dequeue raw samples, preprocess, then update the FSM */
    HMS_CHECK(handle, "invalid handle", ESP_ERR_INVALID_ARG);
    esp_wifi_sensing_fsm_t *fsm = (esp_wifi_sensing_fsm_t *)handle;
    if (!fsm->is_running) {
        return ESP_ERR_INVALID_STATE;
    }

    xSemaphoreTake(fsm->mutex, portMAX_DELAY);
    for (uint32_t i = 0; i < fsm->config.max_channel_num; i++) {
        esp_wifi_sensing_fsm_channel_t *ch = fsm->channels[i];
        if (!ch || !ch->used) {
            continue;
        }
        uint32_t batch = 0;
        while (ch->raw_count > 0 && batch < HMS_MAX_BATCH) {
            uint32_t raw_data = ch->raw_buf[ch->raw_read_index];
            ch->raw_read_index = (ch->raw_read_index + 1) % fsm->config.raw_buf_size;
            ch->raw_count--;
            hms_preprocess_channel(fsm, ch, raw_data);
            hms_process_channel_state(fsm, ch);
            fsm->radar_processed_count++;
            /* Cap this pass at HMS_MAX_BATCH samples */
            batch++;
        }
    }
    xSemaphoreGive(fsm->mutex);
    return ESP_OK;
}

esp_err_t esp_wifi_sensing_fsm_ping_router_start(esp_wifi_sensing_fsm_handle_t handle)
{
    HMS_CHECK(handle, "invalid handle", ESP_ERR_INVALID_ARG);
    esp_wifi_sensing_fsm_t *fsm = (esp_wifi_sensing_fsm_t *)handle;
    xSemaphoreTake(fsm->mutex, portMAX_DELAY);
    esp_ip4_addr_t gw = {0};
    esp_err_t err = hms_ping_get_gateway(fsm, &gw);
    if (err == ESP_OK) {
        err = hms_ping_start(fsm, fsm->ping_frequency_hz, gw);
    }
    xSemaphoreGive(fsm->mutex);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "ping_router_start failed: %s", esp_err_to_name(err));
    }
    return err;
}

esp_err_t esp_wifi_sensing_fsm_set_ping_frequency_hz(esp_wifi_sensing_fsm_handle_t handle, uint32_t frequency_hz)
{
    HMS_CHECK(handle, "invalid handle", ESP_ERR_INVALID_ARG);
    HMS_CHECK(frequency_hz > 0, "invalid ping frequency", ESP_ERR_INVALID_ARG);
    esp_wifi_sensing_fsm_t *fsm = (esp_wifi_sensing_fsm_t *)handle;

    xSemaphoreTake(fsm->mutex, portMAX_DELAY);
    uint32_t old_frequency_hz = fsm->ping_frequency_hz;
    if (old_frequency_hz == 0) {
        old_frequency_hz = 1;
    }
    if (old_frequency_hz == frequency_hz) {
        xSemaphoreGive(fsm->mutex);
        return ESP_OK;
    }

    bool ping_running = (fsm->ping_handle != NULL);
    esp_ip4_addr_t gw = {0};
    if (ping_running) {
        if (fsm->ping_gw.addr != 0) {
            gw = fsm->ping_gw;
        } else {
            esp_err_t gw_err = hms_ping_get_gateway(fsm, &gw);
            if (gw_err != ESP_OK) {
                xSemaphoreGive(fsm->mutex);
                return gw_err;
            }
        }
    }

    fsm->ping_frequency_hz = frequency_hz;
    fsm->config.ping_frequency_hz = frequency_hz;

    esp_err_t err = ESP_OK;
    if (ping_running) {
        err = hms_ping_stop(fsm);
        if (err == ESP_OK) {
            err = hms_ping_start(fsm, frequency_hz, gw);
        }
        if (err != ESP_OK) {
            fsm->ping_frequency_hz = old_frequency_hz;
            fsm->config.ping_frequency_hz = old_frequency_hz;
            if (!fsm->ping_handle) {
                esp_err_t rollback_err = hms_ping_start(fsm, old_frequency_hz, gw);
                if (rollback_err != ESP_OK) {
                    ESP_LOGE(TAG, "rollback ping session failed: %s", esp_err_to_name(rollback_err));
                }
            }
        }
    }
    xSemaphoreGive(fsm->mutex);

    if (err != ESP_OK) {
        ESP_LOGE(TAG, "set_ping_frequency_hz failed: %s", esp_err_to_name(err));
        return err;
    }

    ESP_LOGI(TAG, "ping frequency updated: %" PRIu32 " Hz", frequency_hz);
    return ESP_OK;
}

esp_err_t esp_wifi_sensing_fsm_get_ping_frequency_hz(esp_wifi_sensing_fsm_handle_t handle, uint32_t *frequency_hz)
{
    HMS_CHECK(handle && frequency_hz, "invalid args", ESP_ERR_INVALID_ARG);
    esp_wifi_sensing_fsm_t *fsm = (esp_wifi_sensing_fsm_t *)handle;
    xSemaphoreTake(fsm->mutex, portMAX_DELAY);
    *frequency_hz = fsm->ping_frequency_hz;
    xSemaphoreGive(fsm->mutex);
    return ESP_OK;
}

esp_err_t esp_wifi_sensing_fsm_ping_router_stop(esp_wifi_sensing_fsm_handle_t handle)
{
    HMS_CHECK(handle, "invalid handle", ESP_ERR_INVALID_ARG);
    esp_wifi_sensing_fsm_t *fsm = (esp_wifi_sensing_fsm_t *)handle;
    xSemaphoreTake(fsm->mutex, portMAX_DELAY);
    esp_err_t err = hms_ping_stop(fsm);
    xSemaphoreGive(fsm->mutex);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "ping_router_stop failed: %s", esp_err_to_name(err));
    }
    return err;
}
