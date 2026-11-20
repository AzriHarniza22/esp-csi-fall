#pragma once

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define ACTIVITY_MOTION_FALL_VETO_THRESHOLD 3850000U
#define ACTIVITY_MOTION_CONFIDENT_FALL_THRESHOLD 5000000U

typedef struct {
    size_t output_class;
    bool amplitude_vetoed;
    bool confident_fall;
} activity_motion_gate_result_t;

bool activity_motion_gate_apply(
    size_t model_class,
    size_t class_count,
    size_t fall_class,
    size_t non_fall_class,
    uint32_t smooth_scaled,
    activity_motion_gate_result_t *result);
