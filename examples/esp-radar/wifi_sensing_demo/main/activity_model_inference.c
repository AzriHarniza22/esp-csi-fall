#include "activity_model_inference.h"

#include <math.h>
#include <stdint.h>

#if ACTIVITY_MODEL_ALGORITHM != ACTIVITY_MODEL_ALGORITHM_LINEAR_SVM
#error "activity_model_inference requires a linear model"
#endif

#define CSI_LAYOUT_52_PAIR_BYTES 104

uint8_t activity_model_lltf_pair_count(bool int8_samples,
                                       bool first_word_invalid,
                                       uint16_t lltf_bytes)
{
    if (!int8_samples) {
        return 0;
    }
    if (first_word_invalid == (ACTIVITY_MODEL_FIRST_WORD_INVALID != 0) &&
        lltf_bytes == ACTIVITY_MODEL_LLTF_BYTES) {
        return ACTIVITY_MODEL_SUBCARRIERS;
    }
    if (!first_word_invalid && lltf_bytes == CSI_LAYOUT_52_PAIR_BYTES) {
        return 52;
    }
    return 0;
}

bool activity_model_lltf_compatible(bool int8_samples,
                                    bool first_word_invalid,
                                    uint16_t lltf_bytes)
{
    return activity_model_lltf_pair_count(
               int8_samples, first_word_invalid, lltf_bytes) ==
           ACTIVITY_MODEL_SUBCARRIERS;
}

bool activity_model_ltf_segments_valid(bool is_non_ht,
                                       bool is_ht,
                                       bool stbc,
                                       uint16_t valid_len,
                                       uint16_t lltf_len,
                                       uint16_t ht_ltf_len,
                                       uint16_t stbc_ht_ltf_len)
{
    if (is_non_ht) {
        return !is_ht && !stbc && valid_len == lltf_len &&
               ht_ltf_len == 0 && stbc_ht_ltf_len == 0;
    }
    if (is_ht) {
        const uint32_t expected = (uint32_t)lltf_len + ht_ltf_len +
                                  stbc_ht_ltf_len;
        if (stbc) {
            return valid_len == expected;
        }
        return stbc_ht_ltf_len == 0 &&
               valid_len == (uint32_t)lltf_len + ht_ltf_len;
    }
    return false;
}

bool activity_model_should_reset_history(bool queue_reset, bool frame_valid)
{
    return queue_reset || !frame_valid;
}

bool activity_model_iq_to_amplitude(
    const int8_t *samples,
    size_t pair_count,
    float amplitudes[ACTIVITY_MODEL_SUBCARRIERS])
{
    if (!samples || !amplitudes || pair_count != ACTIVITY_MODEL_SUBCARRIERS) {
        return false;
    }
    for (size_t pair = 0; pair < ACTIVITY_MODEL_SUBCARRIERS; ++pair) {
        amplitudes[pair] = hypotf((float)samples[pair * 2],
                                  (float)samples[pair * 2 + 1]);
    }
    return true;
}

void activity_model_extract_features(const float *amplitude_history,
                                     size_t oldest_frame,
                                     float features[ACTIVITY_MODEL_FEATURE_COUNT])
{
    float band_delta[ACTIVITY_MODEL_FEATURE_COUNT] = {0};
    uint16_t band_counts[ACTIVITY_MODEL_FEATURE_COUNT] = {0};
    oldest_frame %= ACTIVITY_MODEL_WINDOW_FRAMES;

    for (size_t frame = 1; frame < ACTIVITY_MODEL_WINDOW_FRAMES; ++frame) {
        const size_t previous =
            (oldest_frame + frame - 1) % ACTIVITY_MODEL_WINDOW_FRAMES;
        const size_t current =
            (oldest_frame + frame) % ACTIVITY_MODEL_WINDOW_FRAMES;
        for (size_t subcarrier = 0;
             subcarrier < ACTIVITY_MODEL_SUBCARRIERS;
             ++subcarrier) {
            const size_t band =
                subcarrier * ACTIVITY_MODEL_FEATURE_COUNT /
                ACTIVITY_MODEL_SUBCARRIERS;
            const float before = amplitude_history[
                previous * ACTIVITY_MODEL_SUBCARRIERS + subcarrier];
            const float after = amplitude_history[
                current * ACTIVITY_MODEL_SUBCARRIERS + subcarrier];
            band_delta[band] += fabsf(after - before);
            band_counts[band]++;
        }
    }

    for (size_t band = 0; band < ACTIVITY_MODEL_FEATURE_COUNT; ++band) {
        features[band] = log1pf(band_delta[band] / (float)band_counts[band]);
    }
}

bool activity_model_standardize_features(
    const float features[ACTIVITY_MODEL_FEATURE_COUNT],
    float normalized[ACTIVITY_MODEL_FEATURE_COUNT])
{
    for (size_t feature = 0; feature < ACTIVITY_MODEL_FEATURE_COUNT; ++feature) {
        if (!isfinite(features[feature])) {
            return false;
        }
        normalized[feature] =
            (features[feature] - activity_model_means[feature]) /
            activity_model_scales[feature];
        if (!isfinite(normalized[feature])) {
            return false;
        }
    }
    return true;
}

bool activity_model_linear_scores(
    const float features[ACTIVITY_MODEL_FEATURE_COUNT],
    float scores[ACTIVITY_MODEL_CLASS_COUNT])
{
    float normalized[ACTIVITY_MODEL_FEATURE_COUNT];
    if (!activity_model_standardize_features(features, normalized)) {
        return false;
    }

    for (size_t class_index = 0;
         class_index < ACTIVITY_MODEL_CLASS_COUNT;
         ++class_index) {
        float score = activity_model_biases[class_index];
        for (size_t feature = 0; feature < ACTIVITY_MODEL_FEATURE_COUNT; ++feature) {
            score += activity_model_weights[class_index][feature] *
                     normalized[feature];
        }
        if (!isfinite(score)) {
            return false;
        }
        scores[class_index] = score;
    }
    return true;
}

size_t activity_model_argmax(const float scores[ACTIVITY_MODEL_CLASS_COUNT])
{
    size_t best = 0;
    if (!isfinite(scores[0])) {
        return SIZE_MAX;
    }
    for (size_t class_index = 1;
         class_index < ACTIVITY_MODEL_CLASS_COUNT;
         ++class_index) {
        if (!isfinite(scores[class_index])) {
            return SIZE_MAX;
        }
        if (scores[class_index] > scores[best]) {
            best = class_index;
        }
    }
    return best;
}
