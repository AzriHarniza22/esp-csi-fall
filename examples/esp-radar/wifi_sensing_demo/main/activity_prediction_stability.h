#pragma once

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define ACTIVITY_PREDICTION_HISTORY_LENGTH 3
#define ACTIVITY_PREDICTION_FALL_VOTES_REQUIRED 2
#define ACTIVITY_PREDICTION_NON_FALL_RELEASE_COUNT 3

typedef struct {
    size_t history[ACTIVITY_PREDICTION_HISTORY_LENGTH];
    size_t stable_class;
    uint8_t history_count;
    uint8_t next_history_index;
    uint8_t consecutive_non_fall;
    bool initialized;
} activity_prediction_stability_t;

void activity_prediction_stability_reset(
    activity_prediction_stability_t *state);

bool activity_prediction_stability_update(
    activity_prediction_stability_t *state,
    size_t raw_class,
    size_t class_count,
    size_t fall_class,
    size_t non_fall_class,
    size_t *stable_class);
