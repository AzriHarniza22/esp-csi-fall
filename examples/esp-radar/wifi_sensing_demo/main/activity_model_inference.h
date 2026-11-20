#pragma once

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "activity_model_data.h"

uint8_t activity_model_lltf_pair_count(bool int8_samples,
                                       bool first_word_invalid,
                                       uint16_t lltf_bytes);

bool activity_model_lltf_compatible(bool int8_samples,
                                    bool first_word_invalid,
                                    uint16_t lltf_bytes);

bool activity_model_ltf_segments_valid(bool is_non_ht,
                                       bool is_ht,
                                       bool stbc,
                                       uint16_t valid_len,
                                       uint16_t lltf_len,
                                       uint16_t ht_ltf_len,
                                       uint16_t stbc_ht_ltf_len);

bool activity_model_should_reset_history(bool queue_reset, bool frame_valid);

bool activity_model_iq_to_amplitude(
    const int8_t *samples,
    size_t pair_count,
    float amplitudes[ACTIVITY_MODEL_SUBCARRIERS]);

void activity_model_extract_features(const float *amplitude_history,
                                     size_t oldest_frame,
                                     float features[ACTIVITY_MODEL_FEATURE_COUNT]);

bool activity_model_standardize_features(
    const float features[ACTIVITY_MODEL_FEATURE_COUNT],
    float normalized[ACTIVITY_MODEL_FEATURE_COUNT]);

bool activity_model_linear_scores(
    const float features[ACTIVITY_MODEL_FEATURE_COUNT],
    float scores[ACTIVITY_MODEL_CLASS_COUNT]);

size_t activity_model_argmax(const float scores[ACTIVITY_MODEL_CLASS_COUNT]);
