#include "activity_classifier.h"

#include <inttypes.h>
#include <math.h>
#include <stdbool.h>
#include <stdint.h>
#include <string.h>

#include "activity_model_data.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/task.h"
#include "web_serial_monitor.h"

#define ACTIVITY_QUEUE_DEPTH 4
#define ACTIVITY_TASK_STACK_SIZE 4096
#define ACTIVITY_TASK_PRIORITY 3

static const char *TAG = "activity_classifier";

/* Diagnostic reason codes for the flag-bound LLTF layout gate (DATA_CONTRACT §1). */
#define LAYOUT_DIAG_NONE 0
#define LAYOUT_DIAG_UNSUPPORTED_DATA_TYPE 1
#define LAYOUT_DIAG_UNSUPPORTED_BANDWIDTH 2
#define LAYOUT_DIAG_SECONDARY_CHANNEL 3
#define LAYOUT_DIAG_FIRST_WORD_FLAG_LEN_MISMATCH 4
#define LAYOUT_DIAG_UNKNOWN_LLTF_LENGTH 5
#define LAYOUT_DIAG_SIGNAL_MODE 6
#define LAYOUT_DIAG_SEGMENT_SUM 7
#define LAYOUT_DIAG_MODEL_WIDTH_MISMATCH 8
#define LAYOUT_DIAG_MODEL_REASON_BASE 100

typedef struct {
    bool valid;       /* layout satisfies the DATA_CONTRACT §1 length<->flag binding */
    bool model_compat;/* valid AND its LLTF width equals the loaded model width */
    uint8_t pairs;    /* complex pairs decoded from the LLTF segment */
    int reason;       /* LAYOUT_DIAG_* code, or >= MODEL_REASON_BASE for width mismatch */
} csi_layout_verdict_t;

typedef struct {
    uint16_t valid_len;
    uint16_t valid_lltf_len;
    uint8_t data_type;
    uint8_t signal_mode;
    uint8_t bandwidth;
    uint8_t stbc;
    uint8_t secondary_channel;
    bool supported_layout;
    bool reset_history;
    uint8_t lltf_pairs;
    bool model_compat;
    int8_t samples[ACTIVITY_MODEL_LLTF_BYTES];
} activity_frame_t;

static QueueHandle_t s_frame_queue;
static uint32_t s_queue_drops;
static uint32_t s_frames_processed;
static bool s_reset_on_next_frame;
static portMUX_TYPE s_stats_mux = portMUX_INITIALIZER_UNLOCKED;
static float s_amplitude_history[ACTIVITY_MODEL_WINDOW_FRAMES][ACTIVITY_MODEL_SUBCARRIERS];
static int s_last_layout_reason = -1;
static uint32_t s_layout_reason_count;
static uint32_t s_model_width_mismatch_count;

static void count_queue_drop(void)
{
    taskENTER_CRITICAL(&s_stats_mux);
    s_queue_drops++;
    taskEXIT_CRITICAL(&s_stats_mux);
}

/*
 * Classify a frame's LLTF layout against DATA_CONTRACT §1: length and
 * first_word_invalid are bound 1-to-1 (Layout A 102 B / 51 pairs <=> flag true;
 * Layout B 104 B / 52 pairs <=> flag false). The gate is bound to the flag, not
 * to the loaded model width, so any other length/flag combination is an
 * explicit error rather than a silent pass. Model-width compatibility is a
 * separate concern reported back to the caller for diagnostics.
 */
static csi_layout_verdict_t classify_csi_layout(const wifi_csi_filtered_info_t *info)
{
    csi_layout_verdict_t verdict = {0};
    const esp_radar_rx_ctrl_info_t *rx = &info->rx_ctrl_info;
    const bool first_word_invalid = info->info ? info->info->first_word_invalid : false;
    uint8_t pairs = 0;

    if (info->data_type != WIFI_CSI_DATA_TYPE_INT8) {
        verdict.reason = LAYOUT_DIAG_UNSUPPORTED_DATA_TYPE;
        return verdict;
    }
    if (rx->cwb != WIFI_CHANNEL_BANDWIDTH_20MHZ) {
        verdict.reason = LAYOUT_DIAG_UNSUPPORTED_BANDWIDTH;
        return verdict;
    }
    if (rx->secondary_channel != WIFI_SECOND_CHAN_NONE) {
        verdict.reason = LAYOUT_DIAG_SECONDARY_CHANNEL;
        return verdict;
    }

    verdict.valid = true;
    if (first_word_invalid) {
        if (info->valid_lltf_len != 102) {
            verdict.valid = false;
            verdict.reason = LAYOUT_DIAG_FIRST_WORD_FLAG_LEN_MISMATCH;
            return verdict;
        }
        pairs = 51;
    } else if (info->valid_lltf_len == ACTIVITY_MODEL_LLTF_BYTES) {
        pairs = ACTIVITY_MODEL_SUBCARRIERS;
    } else if (info->valid_lltf_len == 104) {
        pairs = 52;
    } else {
        verdict.valid = false;
        verdict.reason = LAYOUT_DIAG_UNKNOWN_LLTF_LENGTH;
        return verdict;
    }
    verdict.pairs = pairs;

    if (rx->signal_mode == WIFI_SIGNAL_MODE_NON_HT) {
        if (rx->stbc ||
                info->valid_len != info->valid_lltf_len ||
                info->valid_ht_ltf_len != 0 ||
                info->valid_stbc_ht_ltf_len != 0) {
            verdict.valid = false;
            verdict.reason = LAYOUT_DIAG_SIGNAL_MODE;
        }
    } else if (rx->signal_mode == WIFI_SIGNAL_MODE_HT) {
        const uint32_t expected = (uint32_t)info->valid_lltf_len +
                                  info->valid_ht_ltf_len + info->valid_stbc_ht_ltf_len;
        if (rx->stbc) {
            if (info->valid_len != expected) {
                verdict.valid = false;
                verdict.reason = LAYOUT_DIAG_SIGNAL_MODE;
            }
        } else if (info->valid_stbc_ht_ltf_len != 0 ||
                   info->valid_len != expected) {
            verdict.valid = false;
            verdict.reason = LAYOUT_DIAG_SIGNAL_MODE;
        }
    } else {
        verdict.valid = false;
        verdict.reason = LAYOUT_DIAG_SIGNAL_MODE;
    }

    if (!verdict.valid) {
        return verdict;
    }

    verdict.model_compat = (pairs == ACTIVITY_MODEL_SUBCARRIERS);
    if (!verdict.model_compat) {
        verdict.reason = LAYOUT_DIAG_MODEL_REASON_BASE + (int)pairs;
    }
    return verdict;
}

/*
 * Emit a throttled diagnostic so a rejected layout is visible without flooding
 * the CSI callback: the first occurrence of each reason is logged immediately,
 * repeats are summarized every 100 frames. Contract violations (valid=false)
 * and valid-but-mismatched-width frames are distinguished.
 */
static void log_layout_reject(const char *source, const wifi_csi_filtered_info_t *info,
                              const csi_layout_verdict_t *verdict)
{
    const bool first_word_invalid = info->info ? info->info->first_word_invalid : false;
    int reason_key = verdict->reason;
    if (!verdict->valid) {
        reason_key += 1000;
    }
    if (reason_key != s_last_layout_reason) {
        s_last_layout_reason = reason_key;
        s_layout_reason_count = 0;
    }
    s_layout_reason_count++;
    if (s_layout_reason_count != 1 && (s_layout_reason_count % 100) != 0) {
        return;
    }

    if (verdict->valid) {
        ESP_LOGW(TAG,
                 "%s: layout valid but incompatible with loaded model: lltf_len=%u "
                 "first_word_invalid=%s pairs=%u model_pairs=%u reason=width_mismatch count=%" PRIu32,
                 source, (unsigned)info->valid_lltf_len,
                 first_word_invalid ? "true" : "false",
                 (unsigned)verdict->pairs, (unsigned)ACTIVITY_MODEL_SUBCARRIERS,
                 (uint32_t)s_model_width_mismatch_count);
        s_model_width_mismatch_count++;
        return;
    }
    ESP_LOGW(TAG,
             "%s: rejected unknown CSI layout: lltf_len=%u first_word_invalid=%s reason=%d count=%" PRIu32,
             source, (unsigned)info->valid_lltf_len,
             first_word_invalid ? "true" : "false", verdict->reason,
             (uint32_t)s_layout_reason_count);
}

void activity_classifier_enqueue(const wifi_csi_filtered_info_t *info)
{
    if (!s_frame_queue || !info) {
        return;
    }

    activity_frame_t frame = {
        .valid_len = info->valid_len,
        .valid_lltf_len = info->valid_lltf_len,
        .data_type = (uint8_t)info->data_type,
        .signal_mode = (uint8_t)info->rx_ctrl_info.signal_mode,
        .bandwidth = info->rx_ctrl_info.cwb,
        .stbc = info->rx_ctrl_info.stbc,
        .secondary_channel = info->rx_ctrl_info.secondary_channel,
        .reset_history = s_reset_on_next_frame,
    };
    csi_layout_verdict_t verdict = classify_csi_layout(info);
    frame.supported_layout = verdict.valid && verdict.model_compat;
    frame.model_compat = verdict.model_compat;
    frame.lltf_pairs = verdict.pairs;

    if (!frame.supported_layout) {
        log_layout_reject("enqueue", info, &verdict);
    }

    if (frame.supported_layout) {
        const size_t bytes = (size_t)frame.lltf_pairs * 2u;
        if (bytes <= sizeof(frame.samples)) {
            memcpy(frame.samples, info->valid_data, bytes);
        }
    }

    if (xQueueSend(s_frame_queue, &frame, 0) != pdTRUE) {
        s_reset_on_next_frame = true;
        count_queue_drop();
    } else {
        s_reset_on_next_frame = false;
    }
}

static bool frame_to_amplitude(const activity_frame_t *frame, float *amplitudes)
{
    if (!frame->supported_layout ||
            frame->data_type != WIFI_CSI_DATA_TYPE_INT8 ||
            frame->lltf_pairs == 0) {
        return false;
    }

    for (uint8_t i = 0; i < frame->lltf_pairs; ++i) {
        const float real = frame->samples[i * 2];
        const float imag = frame->samples[i * 2 + 1];
        amplitudes[i] = hypotf(real, imag);
    }
    return true;
}

static void extract_window_features(float features[ACTIVITY_MODEL_FEATURE_COUNT])
{
    float band_delta[ACTIVITY_MODEL_FEATURE_COUNT] = {0};
    uint16_t band_counts[ACTIVITY_MODEL_FEATURE_COUNT] = {0};
    const size_t oldest = s_frames_processed % ACTIVITY_MODEL_WINDOW_FRAMES;

    for (size_t frame = 1; frame < ACTIVITY_MODEL_WINDOW_FRAMES; ++frame) {
        const size_t previous_index =
            (oldest + frame - 1) % ACTIVITY_MODEL_WINDOW_FRAMES;
        const size_t current_index =
            (oldest + frame) % ACTIVITY_MODEL_WINDOW_FRAMES;
        for (size_t subcarrier = 0; subcarrier < ACTIVITY_MODEL_SUBCARRIERS; ++subcarrier) {
            const size_t band =
                subcarrier * ACTIVITY_MODEL_FEATURE_COUNT / ACTIVITY_MODEL_SUBCARRIERS;
            band_delta[band] += fabsf(
                s_amplitude_history[current_index][subcarrier] -
                s_amplitude_history[previous_index][subcarrier]);
            band_counts[band]++;
        }
    }

    for (size_t band = 0; band < ACTIVITY_MODEL_FEATURE_COUNT; ++band) {
        const float mean_delta = band_delta[band] / (float)band_counts[band];
        features[band] = log1pf(mean_delta);
    }
}

#if ACTIVITY_MODEL_ALGORITHM == ACTIVITY_MODEL_ALGORITHM_DECISION_TREE || \
    ACTIVITY_MODEL_ALGORITHM == ACTIVITY_MODEL_ALGORITHM_RANDOM_FOREST
static int predict_tree(int16_t root, const float *normalized)
{
    int16_t node_index = root;
    for (size_t step = 0; step < ACTIVITY_MODEL_NODE_COUNT; ++step) {
        if (node_index < 0 || node_index >= ACTIVITY_MODEL_NODE_COUNT) {
            return -1;
        }
        const activity_model_node_t *node = &activity_model_nodes[node_index];
        if (node->feature < 0) {
            return node->prediction;
        }
        node_index = normalized[node->feature] <= node->threshold
                         ? node->left
                         : node->right;
    }
    return -1;
}
#endif

static void classify_window(void)
{
    float features[ACTIVITY_MODEL_FEATURE_COUNT];
    float normalized[ACTIVITY_MODEL_FEATURE_COUNT];
    float scores[ACTIVITY_MODEL_CLASS_COUNT] = {0};
    size_t best_class = 0;
    size_t second_class = 0;

    extract_window_features(features);
#if ACTIVITY_MODEL_ALGORITHM == ACTIVITY_MODEL_ALGORITHM_NEAREST_CENTROID
    for (size_t feature_index = 0; feature_index < ACTIVITY_MODEL_FEATURE_COUNT; ++feature_index) {
        normalized[feature_index] =
            (features[feature_index] - activity_model_means[feature_index]) /
            activity_model_scales[feature_index];
    }
    for (size_t class_index = 0; class_index < ACTIVITY_MODEL_CLASS_COUNT; ++class_index) {
        float distance = 0.0f;
        for (size_t feature_index = 0; feature_index < ACTIVITY_MODEL_FEATURE_COUNT; ++feature_index) {
            const float delta =
                normalized[feature_index] - activity_model_centroids[class_index][feature_index];
            distance += delta * delta;
        }
        scores[class_index] = -distance;
    }
#elif ACTIVITY_MODEL_ALGORITHM == ACTIVITY_MODEL_ALGORITHM_LOGISTIC_REGRESSION || \
    ACTIVITY_MODEL_ALGORITHM == ACTIVITY_MODEL_ALGORITHM_LINEAR_SVM
    for (size_t feature_index = 0; feature_index < ACTIVITY_MODEL_FEATURE_COUNT; ++feature_index) {
        normalized[feature_index] =
            (features[feature_index] - activity_model_means[feature_index]) /
            activity_model_scales[feature_index];
    }
    for (size_t class_index = 0; class_index < ACTIVITY_MODEL_CLASS_COUNT; ++class_index) {
        scores[class_index] = activity_model_biases[class_index];
        for (size_t feature_index = 0; feature_index < ACTIVITY_MODEL_FEATURE_COUNT; ++feature_index) {
            scores[class_index] += activity_model_weights[class_index][feature_index] *
                                   normalized[feature_index];
        }
    }
#elif ACTIVITY_MODEL_ALGORITHM == ACTIVITY_MODEL_ALGORITHM_DECISION_TREE
    for (size_t feature_index = 0; feature_index < ACTIVITY_MODEL_FEATURE_COUNT; ++feature_index) {
        normalized[feature_index] =
            (features[feature_index] - activity_model_means[feature_index]) /
            activity_model_scales[feature_index];
    }
    const int prediction = predict_tree(activity_model_tree_roots[0], normalized);
    if (prediction < 0 || prediction >= ACTIVITY_MODEL_CLASS_COUNT) {
        ESP_LOGE(TAG, "Generated decision tree contains an invalid prediction");
        return;
    }
    scores[prediction] = 1.0f;
#elif ACTIVITY_MODEL_ALGORITHM == ACTIVITY_MODEL_ALGORITHM_RANDOM_FOREST
    for (size_t feature_index = 0; feature_index < ACTIVITY_MODEL_FEATURE_COUNT; ++feature_index) {
        normalized[feature_index] =
            (features[feature_index] - activity_model_means[feature_index]) /
            activity_model_scales[feature_index];
    }
    for (size_t tree = 0; tree < ACTIVITY_MODEL_TREE_COUNT; ++tree) {
        const int prediction = predict_tree(activity_model_tree_roots[tree], normalized);
        if (prediction < 0 || prediction >= ACTIVITY_MODEL_CLASS_COUNT) {
            ESP_LOGE(TAG, "Generated random forest contains an invalid prediction");
            return;
        }
        scores[prediction] += 1.0f;
    }
#else
#error "Unsupported generated activity model algorithm"
#endif

    float best_score = -INFINITY;
    float second_score = -INFINITY;
    for (size_t class_index = 0; class_index < ACTIVITY_MODEL_CLASS_COUNT; ++class_index) {
        if (scores[class_index] > best_score) {
            second_score = best_score;
            second_class = best_class;
            best_score = scores[class_index];
            best_class = class_index;
        } else if (scores[class_index] > second_score) {
            second_score = scores[class_index];
            second_class = class_index;
        }
    }

    uint32_t queue_drops;
    taskENTER_CRITICAL(&s_stats_mux);
    queue_drops = s_queue_drops;
    taskEXIT_CRITICAL(&s_stats_mux);
    web_serial_monitor_publish_activity(
        activity_model_labels[best_class], best_score,
        activity_model_labels[second_class], second_score);
    ESP_LOGI(TAG, "DEMO only: algorithm=%s class=%s score=%.3f runner_up=%s score=%.3f frames=%" PRIu32 " queue_drops=%" PRIu32,
             ACTIVITY_MODEL_NAME, activity_model_labels[best_class], (double)best_score,
             activity_model_labels[second_class], (double)second_score,
             s_frames_processed, queue_drops);
}

static void activity_classifier_task(void *arg)
{
    (void)arg;
    activity_frame_t frame;
    float amplitudes[ACTIVITY_MODEL_SUBCARRIERS];

    for (;;) {
        if (xQueueReceive(s_frame_queue, &frame, portMAX_DELAY) != pdTRUE) {
            continue;
        }
        if (frame.reset_history) {
            s_frames_processed = 0;
        }
        if (!frame_to_amplitude(&frame, amplitudes)) {
            /* Layout diagnostics (length/flag/reason) are emitted once at the
             * enqueue gate; frames here are only unsupported or model-width
             * mismatches, so reset the window and drop without re-logging. */
            s_frames_processed = 0;
            continue;
        }

        const size_t write_index = s_frames_processed % ACTIVITY_MODEL_WINDOW_FRAMES;
        memcpy(s_amplitude_history[write_index], amplitudes, sizeof(amplitudes));
        s_frames_processed++;

        if (s_frames_processed >= ACTIVITY_MODEL_WINDOW_FRAMES &&
                (s_frames_processed - ACTIVITY_MODEL_WINDOW_FRAMES) %
                    ACTIVITY_MODEL_WINDOW_STRIDE == 0) {
            classify_window();
        }
    }
}

esp_err_t activity_classifier_init(void)
{
    if (s_frame_queue) {
        return ESP_ERR_INVALID_STATE;
    }

    s_frame_queue = xQueueCreate(ACTIVITY_QUEUE_DEPTH, sizeof(activity_frame_t));
    if (!s_frame_queue) {
        return ESP_ERR_NO_MEM;
    }

    if (xTaskCreate(activity_classifier_task, "csi_activity", ACTIVITY_TASK_STACK_SIZE,
                    NULL, ACTIVITY_TASK_PRIORITY, NULL) != pdPASS) {
        vQueueDelete(s_frame_queue);
        s_frame_queue = NULL;
        return ESP_ERR_NO_MEM;
    }

    ESP_LOGW(TAG,
             "Experimental %s model loaded: %u classes, %u LLTF complex samples",
             ACTIVITY_MODEL_NAME, ACTIVITY_MODEL_CLASS_COUNT, ACTIVITY_MODEL_SUBCARRIERS);
    return ESP_OK;
}
