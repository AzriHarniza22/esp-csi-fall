#include "activity_motion_gate.h"

bool activity_motion_gate_apply(
    size_t model_class,
    size_t class_count,
    size_t fall_class,
    size_t non_fall_class,
    uint32_t smooth_scaled,
    activity_motion_gate_result_t *result)
{
    if (!result || class_count != 2 || fall_class >= class_count ||
            non_fall_class >= class_count || fall_class == non_fall_class ||
            model_class >= class_count) {
        return false;
    }

    result->output_class = model_class;
    result->amplitude_vetoed = false;
    result->confident_fall = false;

    if (model_class == fall_class &&
            smooth_scaled < ACTIVITY_MOTION_FALL_VETO_THRESHOLD) {
        result->output_class = non_fall_class;
        result->amplitude_vetoed = true;
    }
    result->confident_fall =
        result->output_class == fall_class &&
        smooth_scaled > ACTIVITY_MOTION_CONFIDENT_FALL_THRESHOLD;
    return true;
}
