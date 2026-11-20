#include "activity_prediction_stability.h"

#include <string.h>

void activity_prediction_stability_reset(
    activity_prediction_stability_t *state)
{
    if (state) {
        memset(state, 0, sizeof(*state));
    }
}

bool activity_prediction_stability_update(
    activity_prediction_stability_t *state,
    size_t raw_class,
    size_t class_count,
    size_t fall_class,
    size_t non_fall_class,
    size_t *stable_class)
{
    if (!state || !stable_class || class_count != 2 ||
        fall_class >= class_count || non_fall_class >= class_count ||
        fall_class == non_fall_class || raw_class >= class_count) {
        return false;
    }

    if (!state->initialized) {
        state->stable_class = raw_class;
        state->initialized = true;
    }

    state->history[state->next_history_index] = raw_class;
    state->next_history_index =
        (state->next_history_index + 1) % ACTIVITY_PREDICTION_HISTORY_LENGTH;
    if (state->history_count < ACTIVITY_PREDICTION_HISTORY_LENGTH) {
        state->history_count++;
    }

    if (state->stable_class == non_fall_class) {
        size_t fall_votes = 0;
        for (size_t index = 0; index < state->history_count; ++index) {
            fall_votes += state->history[index] == fall_class;
        }
        if (fall_votes >= ACTIVITY_PREDICTION_FALL_VOTES_REQUIRED) {
            state->stable_class = fall_class;
            state->consecutive_non_fall = 0;
        }
    } else if (raw_class == non_fall_class) {
        if (state->consecutive_non_fall < ACTIVITY_PREDICTION_NON_FALL_RELEASE_COUNT) {
            state->consecutive_non_fall++;
        }
        if (state->consecutive_non_fall >= ACTIVITY_PREDICTION_NON_FALL_RELEASE_COUNT) {
            state->stable_class = non_fall_class;
            state->consecutive_non_fall = 0;
        }
    } else {
        state->consecutive_non_fall = 0;
    }

    *stable_class = state->stable_class;
    return true;
}
