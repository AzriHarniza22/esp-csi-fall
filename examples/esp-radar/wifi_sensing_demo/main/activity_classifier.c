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
    int8_t samples[ACTIVITY_MODEL_LLTF_BYTES];
} activity_frame_t;

static QueueHandle_t s_frame_queue;
static uint32_t s_queue_drops;
static uint32_t s_frames_processed;
static bool s_reset_on_next_frame;
static portMUX_TYPE s_stats_mux = portMUX_INITIALIZER_UNLOCKED;
static float s_amplitude_history[ACTIVITY_MODEL_WINDOW_FRAMES][ACTIVITY_MODEL_SUBCARRIERS];

static void count_queue_drop(void)
{
    taskENTER_CRITICAL(&s_stats_mux);
    s_queue_drops++;
    taskEXIT_CRITICAL(&s_stats_mux);
}

static bool has_supported_lltf_layout(const wifi_csi_filtered_info_t *info)
{
    const esp_radar_rx_ctrl_info_t *rx = &info->rx_ctrl_info;
    if (info->data_type != WIFI_CSI_DATA_TYPE_INT8 ||
            info->valid_lltf_len != ACTIVITY_MODEL_LLTF_BYTES ||
            rx->cwb != WIFI_CHANNEL_BANDWIDTH_20MHZ ||
            rx->secondary_channel != WIFI_SECOND_CHAN_NONE) {
        return false;
    }

    if (rx->signal_mode == WIFI_SIGNAL_MODE_NON_HT) {
        return !rx->stbc &&
               info->valid_len == info->valid_lltf_len &&
               info->valid_ht_ltf_len == 0 &&
               info->valid_stbc_ht_ltf_len == 0;
    }
    if (rx->signal_mode == WIFI_SIGNAL_MODE_HT) {
        if (rx->stbc) {
            return info->valid_len ==
                   info->valid_lltf_len + info->valid_ht_ltf_len +
                       info->valid_stbc_ht_ltf_len;
        }
        return info->valid_stbc_ht_ltf_len == 0 &&
               info->valid_len == info->valid_lltf_len + info->valid_ht_ltf_len;
    }
    return false;
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
        .supported_layout = has_supported_lltf_layout(info),
        .reset_history = s_reset_on_next_frame,
    };
    if (frame.supported_layout) {
        memcpy(frame.samples, info->valid_data, sizeof(frame.samples));
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
            frame->valid_lltf_len != ACTIVITY_MODEL_LLTF_BYTES) {
        return false;
    }

    for (size_t i = 0; i < ACTIVITY_MODEL_SUBCARRIERS; ++i) {
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
            s_frames_processed = 0;
            ESP_LOGW(TAG,
                     "Skipping CSI frame: type=%u mode=%u bandwidth=%u stbc=%u secondary=%u valid_len=%u lltf_len=%u",
                     frame.data_type, frame.signal_mode, frame.bandwidth,
                     frame.stbc, frame.secondary_channel, frame.valid_len,
                     frame.valid_lltf_len);
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
