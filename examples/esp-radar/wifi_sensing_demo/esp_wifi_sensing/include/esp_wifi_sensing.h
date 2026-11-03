/*
 * SPDX-FileCopyrightText: 2026 Espressif Systems (Shanghai) CO LTD
 *
 * SPDX-License-Identifier: Apache-2.0
 */
#pragma once

#include <stdbool.h>
#include <stdint.h>
#include "sdkconfig.h"
#include "esp_err.h"

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief Opaque handle of a Wi-Fi sensing FSM instance.
 *
 * One handle manages a group of sensing channels, where each channel is
 * identified by a peer MAC address.
 */
typedef void *esp_wifi_sensing_fsm_handle_t;

/**
 * @brief Public sensing state reported for a channel.
 */
typedef enum {
    ESP_WIFI_SENSING_FSM_STATE_INACTIVE = 0, /**< No motion is currently confirmed. */
    ESP_WIFI_SENSING_FSM_STATE_ACTIVE,       /**< Motion is confirmed and the channel is active. */
    ESP_WIFI_SENSING_FSM_STATE_DEBOUNCE,     /**< The FSM is evaluating a possible state transition. */
} esp_wifi_sensing_fsm_state_t;

/**
 * @brief Control commands for the sensing FSM.
 */
typedef enum {
    ESP_WIFI_SENSING_FSM_CTRL_START = 0,       /**< Start processing and reinitialize all channel baselines. */
    ESP_WIFI_SENSING_FSM_CTRL_STOP,            /**< Stop processing while keeping the handle and channels allocated. */
    ESP_WIFI_SENSING_FSM_CTRL_RESET_BASELINE,  /**< Relearn the background baseline for all channels. */
} esp_wifi_sensing_fsm_ctrl_t;

/**
 * @brief Events emitted when a channel changes activity state.
 */
typedef enum {
    ESP_WIFI_SENSING_FSM_EVENT_INACTIVE = 0, /**< The channel returns to inactive. */
    ESP_WIFI_SENSING_FSM_EVENT_ACTIVE,       /**< The channel enters active state. */
    ESP_WIFI_SENSING_FSM_EVENT_MAX,          /**< Internal upper bound. */
} esp_wifi_sensing_fsm_event_t;

/**
 * @brief Internal processing state exposed for diagnostics.
 *
 * This enum is intended for logging, visualization, and tuning. Application
 * logic should usually rely on `esp_wifi_sensing_fsm_state_t` instead.
 */
typedef enum {
    ESP_WIFI_SENSING_FSM_PROCESS_IDLE = 0,             /**< Stable inactive state. */
    ESP_WIFI_SENSING_FSM_PROCESS_DEBOUNCE_ACTIVE,      /**< Debouncing before entering active. */
    ESP_WIFI_SENSING_FSM_PROCESS_ACTIVE,               /**< Stable active state. */
    ESP_WIFI_SENSING_FSM_PROCESS_DEBOUNCE_INACTIVE,    /**< Debouncing before returning inactive. */
} esp_wifi_sensing_fsm_process_state_t;

/**
 * @brief Baseline initialization stage exposed for diagnostics.
 */
typedef enum {
    ESP_WIFI_SENSING_FSM_INIT_STAGE_START = 0,      /**< Initial averaging is in progress. */
    ESP_WIFI_SENSING_FSM_INIT_STAGE_GOLD_FOUND,     /**< The initial center is found and is being verified. */
    ESP_WIFI_SENSING_FSM_INIT_STAGE_STABLE,         /**< Baseline learning is complete and detection is stable. */
} esp_wifi_sensing_fsm_init_stage_t;

/**
 * @brief Public radar-training status exposed for diagnostics.
 */
typedef enum {
    ESP_WIFI_SENSING_FSM_TRAIN_STATUS_NONE = 0,      /**< Training is idle or cleared. */
    ESP_WIFI_SENSING_FSM_TRAIN_STATUS_PROGRESS,      /**< Training is in progress. */
    ESP_WIFI_SENSING_FSM_TRAIN_STATUS_COMPLETE,      /**< Training completed and thresholds are ready. */
} esp_wifi_sensing_fsm_train_status_t;

/**
 * @brief Latest training decision exposed for diagnostics.
 */
typedef enum {
    ESP_WIFI_SENSING_FSM_TRAIN_ACTION_IDLE = 0,              /**< No recent training action. */
    ESP_WIFI_SENSING_FSM_TRAIN_ACTION_WAIT_BUFFER,           /**< Waiting for enough history before making a decision. */
    ESP_WIFI_SENSING_FSM_TRAIN_ACTION_DISCARD_OUTLIER,       /**< Current point was discarded as an outlier. */
    ESP_WIFI_SENSING_FSM_TRAIN_ACTION_COLLECT_SAMPLE,        /**< Current step collected a new template sample. */
    ESP_WIFI_SENSING_FSM_TRAIN_ACTION_ACCUMULATE_BACKGROUND, /**< Current step accumulated normal background statistics. */
} esp_wifi_sensing_fsm_train_action_t;

/**
 * @brief Per-channel diagnostic snapshot.
 *
 * The scaled fields are implementation-oriented values that are useful for
 * debugging or visualization. They are not part of the simplified tuning API.
 */
typedef struct {
    float jitter_value;                               /**< Latest raw `waveform_jitter` value. */
    uint32_t smooth_scaled;                           /**< Current smoothed feature value in internal scaled units. */
    uint32_t enter_level_scaled;                      /**< Absolute enter-active threshold in internal scaled units. */
    uint32_t exit_level_scaled;                       /**< Absolute exit-active threshold in internal scaled units. */
    esp_wifi_sensing_fsm_process_state_t state;       /**< Current internal process state. */
    esp_wifi_sensing_fsm_init_stage_t init_stage;     /**< Current baseline initialization stage. */
    float wander_value;                               /**< Latest raw `waveform_wander` (presence-related) from esp-radar. */
    float train_wander_threshold;                     /**< Mean background wander from train_stop (same scale as `waveform_wander`). */
    float train_jitter_threshold;                     /**< Reference jitter from train_stop (same scale as `waveform_jitter`). */
    bool train_thresholds_valid;                      /**< True if train stop has produced valid thresholds for this channel. */
    esp_wifi_sensing_fsm_train_status_t train_status; /**< Current radar-training status. */
    esp_wifi_sensing_fsm_train_action_t train_last_action; /**< Latest radar-training decision. */
    uint32_t train_sample_count;                      /**< Number of template samples collected during training. */
    uint32_t train_background_count;                  /**< Number of background points accumulated for threshold averaging. */
    float train_background_avg;                       /**< Mean background wander accumulated so far. */
    float train_last_basis_wander;                    /**< Previous wander value used for collect/accumulate decision. */
    bool presence_ready;                              /**< True when the per-channel presence window has enough samples. */
    float presence_wander_average;                    /**< Per-channel wander average computed with a trimmed mean. */
    float presence_someone_threshold;                 /**< Per-channel someone threshold derived from train wander threshold. */
    bool presence_someone_status;                     /**< Per-channel presence result derived from wander-based detection. */
} esp_wifi_sensing_fsm_channel_diag_t;

/**
 * @brief Simplified tuning parameters for a sensing channel.
 */
typedef struct {
    float sensitivity;         /**< Motion detection sensitivity, recommended `(0, 1]`; larger values are more sensitive. */
    float presence_sensitivity; /**< Presence detection sensitivity in `[0, 1]`; larger values are more sensitive. Independent of motion detection sensitivity. */
    float active_jitter_min;   /**< Minimum raw `jitter_value` required to stay active. Set to `0` to disable this guard. */
    uint32_t active_filter_ms; /**< Minimum hold time after entering active, in milliseconds. */
} esp_wifi_sensing_fsm_channel_config_t;

/**
 * @brief Global configuration used when creating the sensing FSM.
 */
typedef struct {
    uint32_t max_channel_num;                              /**< Maximum number of sensing channels managed by one handle. */
    uint32_t raw_buf_size;                                 /**< Buffered sample count per channel. Oldest samples are overwritten when full. */
    uint32_t polling_interval;                             /**< Background processing period, in milliseconds. */
    uint32_t ping_frequency_hz;                            /**< Internal router ping frequency, in hertz, when ping-assisted sampling is used. */
    esp_wifi_sensing_fsm_channel_config_t default_channel_config; /**< Default channel config applied by `esp_wifi_sensing_fsm_add_channel()`. */
    void *user_data;                                       /**< Reserved user pointer for application-owned context. */
} esp_wifi_sensing_fsm_config_t;

/**
 * @brief Callback invoked when a channel emits an ACTIVE or INACTIVE event.
 *
 * @param handle    FSM handle that emitted the event.
 * @param peer_mac  MAC address of the channel that changed state.
 * @param event     Event type.
 * @param data      Event payload. Currently this is the smoothed feature value
 *                  converted back from internal scaled units.
 * @param user_data User pointer passed when registering the callback.
 */
typedef void (*esp_wifi_sensing_fsm_event_cb_t)(esp_wifi_sensing_fsm_handle_t handle,
                                                const uint8_t peer_mac[6],
                                                esp_wifi_sensing_fsm_event_t event,
                                                uint32_t data,
                                                void *user_data);

#define ESP_WIFI_SENSING_ACTIVE_FILTER_MS_DEFAULT CONFIG_ESP_WIFI_SENSING_ACTIVE_FILTER_MS
#define ESP_WIFI_SENSING_DEFAULT_SENSITIVITY ((float)CONFIG_ESP_WIFI_SENSING_DEFAULT_SENSITIVITY / 1000.0f)
#define ESP_WIFI_SENSING_DEFAULT_PRESENCE_SENSITIVITY ((float)CONFIG_ESP_WIFI_SENSING_DEFAULT_PRESENCE_SENSITIVITY / 1000.0f)
#define ESP_WIFI_SENSING_DEFAULT_ACTIVE_JITTER_MIN ((float)CONFIG_ESP_WIFI_SENSING_DEFAULT_ACTIVE_JITTER_MIN / 1000.0f)
#define ESP_WIFI_SENSING_PING_FREQUENCY_HZ_DEFAULT CONFIG_ESP_WIFI_SENSING_PING_FREQUENCY_HZ

/**
 * @brief Default per-channel sensing configuration.
 *
 * The defaults provide a balanced starting point for typical motion-triggered
 * applications.
 */
#define DEFAULT_ESP_WIFI_SENSING_FSM_CHANNEL_CONFIG() \
{ \
    .sensitivity = ESP_WIFI_SENSING_DEFAULT_SENSITIVITY, \
    .presence_sensitivity = ESP_WIFI_SENSING_DEFAULT_PRESENCE_SENSITIVITY, \
    .active_jitter_min = ESP_WIFI_SENSING_DEFAULT_ACTIVE_JITTER_MIN, \
    .active_filter_ms = ESP_WIFI_SENSING_ACTIVE_FILTER_MS_DEFAULT, \
}

/**
 * @brief Default global sensing configuration.
 *
 * This macro initializes a handle for up to 16 channels, uses a 20 ms
 * processing interval, and applies `DEFAULT_ESP_WIFI_SENSING_FSM_CHANNEL_CONFIG()`
 * to newly added channels.
 */
#define DEFAULT_ESP_WIFI_SENSING_FSM_CONFIG() \
{ \
    .max_channel_num = 16, \
    .raw_buf_size = 20, \
    .polling_interval = 20, \
    .ping_frequency_hz = ESP_WIFI_SENSING_PING_FREQUENCY_HZ_DEFAULT, \
    .default_channel_config = DEFAULT_ESP_WIFI_SENSING_FSM_CHANNEL_CONFIG(), \
    .user_data = NULL, \
}

/**
 * @brief Create a sensing FSM instance.
 *
 * The created handle owns the background task, channel table, and the internal
 * radar integration used by this component. Only one FSM instance is supported
 * at a time.
 *
 * Typical flow:
 * 1. Call this function.
 * 2. Add one or more channels with `esp_wifi_sensing_fsm_add_channel()`.
 * 3. Optionally register event callbacks and adjust channel configuration.
 * 4. Start detection with `esp_wifi_sensing_fsm_control(..., ESP_WIFI_SENSING_FSM_CTRL_START, ...)`.
 *
 * @param config   Pointer to the global configuration.
 * @param handle   Output handle.
 * @return
 *      - ESP_OK: Success
 *      - ESP_ERR_INVALID_ARG: `config` or `handle` is invalid, or configuration values are invalid
 *      - ESP_ERR_INVALID_STATE: An FSM instance already exists
 *      - ESP_ERR_NO_MEM: Memory allocation failed
 *      - Other error codes propagated from the underlying radar initialization
 */
esp_err_t esp_wifi_sensing_fsm_create(const esp_wifi_sensing_fsm_config_t *config, esp_wifi_sensing_fsm_handle_t *handle);

/**
 * @brief Delete a sensing FSM instance and release all resources.
 *
 * This function stops the background task, stops router ping if active, and
 * destroys all registered channels and callbacks.
 *
 * @param handle FSM handle returned by `esp_wifi_sensing_fsm_create()`.
 * @return
 *      - ESP_OK: Success
 *      - ESP_ERR_INVALID_ARG: `handle` is invalid
 */
esp_err_t esp_wifi_sensing_fsm_delete(esp_wifi_sensing_fsm_handle_t handle);

/**
 * @brief Add a sensing channel for a peer MAC address.
 *
 * Each channel maintains its own baseline, state, and diagnostics. The newly
 * added channel inherits `default_channel_config` from the handle config.
 *
 * @param handle    FSM handle.
 * @param peer_mac  Peer MAC address that identifies the channel.
 * @return
 *      - ESP_OK: Success
 *      - ESP_ERR_INVALID_ARG: Invalid arguments
 *      - ESP_ERR_INVALID_STATE: The channel already exists
 *      - ESP_ERR_NO_MEM: No free channel slot or memory allocation failed
 *      - Other error codes propagated from `esp_radar_new_peer()`
 */
esp_err_t esp_wifi_sensing_fsm_add_channel(esp_wifi_sensing_fsm_handle_t handle, const uint8_t peer_mac[6]);

/**
 * @brief Remove a sensing channel.
 *
 * @param handle    FSM handle.
 * @param peer_mac  Peer MAC address of the channel to remove.
 * @return
 *      - ESP_OK: Success
 *      - ESP_ERR_INVALID_ARG: Invalid arguments
 *      - ESP_ERR_NOT_FOUND: The channel does not exist
 */
esp_err_t esp_wifi_sensing_fsm_remove_channel(esp_wifi_sensing_fsm_handle_t handle, const uint8_t peer_mac[6]);

/**
 * @brief Push a feature sample into a channel manually.
 *
 * This API is mainly intended for advanced integration. When the built-in
 * radar path is used, the component feeds samples automatically and applications
 * usually do not need to call this function.
 *
 * @param handle    FSM handle.
 * @param peer_mac  Peer MAC address of the target channel.
 * @param raw_data  Feature value to enqueue for processing.
 * @return
 *      - ESP_OK: Success
 *      - ESP_ERR_INVALID_ARG: Invalid arguments
 *      - ESP_ERR_NOT_FOUND: The channel does not exist
 */
esp_err_t esp_wifi_sensing_fsm_update_data(esp_wifi_sensing_fsm_handle_t handle, const uint8_t peer_mac[6], uint32_t raw_data);

/**
 * @brief Get the current public state of a channel.
 *
 * @param handle    FSM handle.
 * @param peer_mac  Peer MAC address of the channel.
 * @param state     Output state.
 * @return
 *      - ESP_OK: Success
 *      - ESP_ERR_INVALID_ARG: Invalid arguments
 *      - ESP_ERR_NOT_FOUND: The channel does not exist
 */
esp_err_t esp_wifi_sensing_fsm_get_state(esp_wifi_sensing_fsm_handle_t handle, const uint8_t peer_mac[6], esp_wifi_sensing_fsm_state_t *state);

/**
 * @brief Get diagnostic information for a channel.
 *
 * @param handle    FSM handle.
 * @param peer_mac  Peer MAC address of the channel.
 * @param diag      Output diagnostic snapshot.
 * @return
 *      - ESP_OK: Success
 *      - ESP_ERR_INVALID_ARG: Invalid arguments
 *      - ESP_ERR_NOT_FOUND: The channel does not exist
 */
esp_err_t esp_wifi_sensing_fsm_get_channel_diag(esp_wifi_sensing_fsm_handle_t handle, const uint8_t peer_mac[6], esp_wifi_sensing_fsm_channel_diag_t *diag);

/**
 * @brief Start esp-radar calibration / training for a channel peer.
 *
 * Collects background statistics used by `esp_radar_train_stop_ex()` to derive wander (presence)
 * and jitter (motion) thresholds. Keep the environment static while training.
 *
 * @param handle    FSM handle.
 * @param peer_mac  Peer MAC address of the channel.
 * @return
 *      - ESP_OK: Success
 *      - ESP_ERR_INVALID_ARG: Invalid arguments
 *      - ESP_ERR_NOT_FOUND: Channel does not exist or has no radar peer
 *      - Other codes propagated from esp-radar
 */
esp_err_t esp_wifi_sensing_fsm_train_start(esp_wifi_sensing_fsm_handle_t handle, const uint8_t peer_mac[6]);

/**
 * @brief Stop esp-radar training and read calculated thresholds for a channel peer.
 *
 * On success, thresholds are cached on the channel for later diagnostics (`train_*` fields in
 * `esp_wifi_sensing_fsm_channel_diag_t`).
 *
 * @param handle             FSM handle.
 * @param peer_mac           Peer MAC address of the channel.
 * @param wander_threshold   Optional output mean background wander (`esp_radar_motion_dec` scale). Pass NULL to ignore.
 * @param jitter_threshold   Optional output reference jitter (`esp_radar_motion_dec` scale). Pass NULL to ignore.
 * @return
 *      - ESP_OK: Success
 *      - ESP_ERR_INVALID_ARG: Invalid arguments
 *      - ESP_ERR_NOT_FOUND: Channel does not exist
 *      - ESP_ERR_NOT_SUPPORTED / ESP_ERR_INVALID_STATE: Propagated from esp-radar when training data is missing
 */
esp_err_t esp_wifi_sensing_fsm_train_stop(esp_wifi_sensing_fsm_handle_t handle, const uint8_t peer_mac[6],
                                          float *wander_threshold, float *jitter_threshold);

/**
 * @brief Clear esp-radar calibration data for a channel peer.
 *
 * @param handle    FSM handle.
 * @param peer_mac  Peer MAC address of the channel.
 * @return
 *      - ESP_OK: Success
 *      - ESP_ERR_INVALID_ARG: Invalid arguments
 *      - ESP_ERR_NOT_FOUND: Channel does not exist
 */
esp_err_t esp_wifi_sensing_fsm_train_remove(esp_wifi_sensing_fsm_handle_t handle, const uint8_t peer_mac[6]);

/**
 * @brief Update the runtime configuration of a channel.
 *
 * If motion detection sensitivity changes, the channel relearns its baseline.
 * Changing presence detection sensitivity only updates presence state and does not reset the motion baseline.
 *
 * @param handle    FSM handle.
 * @param peer_mac  Peer MAC address of the channel.
 * @param config    New channel configuration.
 * @return
 *      - ESP_OK: Success
 *      - ESP_ERR_INVALID_ARG: Invalid arguments
 *      - ESP_ERR_NOT_FOUND: The channel does not exist
 */
esp_err_t esp_wifi_sensing_fsm_set_channel_config(esp_wifi_sensing_fsm_handle_t handle, const uint8_t peer_mac[6], const esp_wifi_sensing_fsm_channel_config_t *config);

/**
 * @brief Read the current runtime configuration of a channel.
 *
 * @param handle    FSM handle.
 * @param peer_mac  Peer MAC address of the channel.
 * @param config    Output channel configuration.
 * @return
 *      - ESP_OK: Success
 *      - ESP_ERR_INVALID_ARG: Invalid arguments
 *      - ESP_ERR_NOT_FOUND: The channel does not exist
 */
esp_err_t esp_wifi_sensing_fsm_get_channel_config(esp_wifi_sensing_fsm_handle_t handle, const uint8_t peer_mac[6], esp_wifi_sensing_fsm_channel_config_t *config);

/**
 * @brief Update the internal router ping frequency.
 *
 * If ping-assisted sampling is already running, the ping session is restarted
 * with the new frequency.
 *
 * @param handle        FSM handle.
 * @param frequency_hz  New ping frequency in hertz. Must be greater than 0.
 * @return
 *      - ESP_OK: Success
 *      - ESP_ERR_INVALID_ARG: Invalid arguments
 *      - Other error codes propagated from ping session restart when ping is active
 */
esp_err_t esp_wifi_sensing_fsm_set_ping_frequency_hz(esp_wifi_sensing_fsm_handle_t handle, uint32_t frequency_hz);

/**
 * @brief Get the configured internal router ping frequency.
 *
 * @param handle        FSM handle.
 * @param frequency_hz  Output ping frequency in hertz.
 * @return
 *      - ESP_OK: Success
 *      - ESP_ERR_INVALID_ARG: Invalid arguments
 */
esp_err_t esp_wifi_sensing_fsm_get_ping_frequency_hz(esp_wifi_sensing_fsm_handle_t handle, uint32_t *frequency_hz);

/**
 * @brief Enable or disable amplitude log compression in the underlying radar decoder.
 *
 * The setting is applied immediately when the radar backend is already running.
 *
 * @param handle   FSM handle.
 * @param enabled  `true` to enable amplitude log compression, `false` to disable it.
 * @return
 *      - ESP_OK: Success
 *      - ESP_ERR_INVALID_ARG: `handle` is invalid
 *      - Other error codes propagated from radar runtime reconfiguration
 */
esp_err_t esp_wifi_sensing_fsm_set_amplitude_log_enabled(esp_wifi_sensing_fsm_handle_t handle, bool enabled);

/**
 * @brief Get the current amplitude log compression setting.
 *
 * @param handle   FSM handle.
 * @param enabled  Output enable flag.
 * @return
 *      - ESP_OK: Success
 *      - ESP_ERR_INVALID_ARG: Invalid arguments
 */
esp_err_t esp_wifi_sensing_fsm_get_amplitude_log_enabled(esp_wifi_sensing_fsm_handle_t handle, bool *enabled);

/**
 * @brief Register a callback for an event type.
 *
 * Multiple callbacks can be registered for the same event. Callbacks are
 * invoked synchronously when the FSM emits the event.
 *
 * @param handle     FSM handle.
 * @param event      Event type to subscribe to.
 * @param cb         Callback function.
 * @param user_data  User pointer passed back to the callback.
 * @return
 *      - ESP_OK: Success
 *      - ESP_ERR_INVALID_ARG: Invalid arguments
 *      - ESP_ERR_NO_MEM: Callback storage allocation failed
 */
esp_err_t esp_wifi_sensing_fsm_register_event_cb(esp_wifi_sensing_fsm_handle_t handle, esp_wifi_sensing_fsm_event_t event, esp_wifi_sensing_fsm_event_cb_t cb, void *user_data);

/**
 * @brief Unregister all callbacks of an event type.
 *
 * @param handle  FSM handle.
 * @param event   Event type whose callbacks should be removed.
 * @return
 *      - ESP_OK: Success
 *      - ESP_ERR_INVALID_ARG: Invalid arguments
 */
esp_err_t esp_wifi_sensing_fsm_unregister_event_cb(esp_wifi_sensing_fsm_handle_t handle, esp_wifi_sensing_fsm_event_t event);

/**
 * @brief Control the sensing FSM runtime.
 *
 * `ESP_WIFI_SENSING_FSM_CTRL_START` starts processing and restarts baseline
 * learning for all existing channels. `ESP_WIFI_SENSING_FSM_CTRL_STOP` pauses
 * processing. `ESP_WIFI_SENSING_FSM_CTRL_RESET_BASELINE` relearns the baseline
 * without deleting channels.
 *
 * @param handle      FSM handle.
 * @param ctrl        Control command.
 * @param ctrl_param  Reserved for future use. Pass `NULL`.
 * @return
 *      - ESP_OK: Success
 *      - ESP_ERR_INVALID_ARG: Invalid handle or control command
 */
esp_err_t esp_wifi_sensing_fsm_control(esp_wifi_sensing_fsm_handle_t handle, esp_wifi_sensing_fsm_ctrl_t ctrl, void *ctrl_param);

/**
 * @brief Process queued samples immediately.
 *
 * The component already runs a background task based on `polling_interval`, so
 * applications normally do not need to call this function. It is exposed for
 * advanced integrations and explicit processing points.
 *
 * @param handle FSM handle.
 * @return
 *      - ESP_OK: Success
 *      - ESP_ERR_INVALID_ARG: `handle` is invalid
 *      - ESP_ERR_INVALID_STATE: The FSM is not started
 */
esp_err_t esp_wifi_sensing_fsm_handle_events(esp_wifi_sensing_fsm_handle_t handle);

/**
 * @brief Start internal router ping to keep the sampling path active.
 *
 * This is useful in router-based CSI scenarios where periodic traffic helps
 * maintain a continuous sensing stream. The function resolves the STA gateway
 * automatically and starts an endless ping session.
 *
 * @param handle FSM handle.
 * @return
 *      - ESP_OK: Success
 *      - ESP_ERR_INVALID_ARG: `handle` is invalid
 *      - ESP_ERR_INVALID_STATE: STA network interface or gateway is not ready
 *      - Other error codes propagated from the ping subsystem
 */
esp_err_t esp_wifi_sensing_fsm_ping_router_start(esp_wifi_sensing_fsm_handle_t handle);

/**
 * @brief Stop the internal router ping session.
 *
 * @param handle FSM handle.
 * @return
 *      - ESP_OK: Success
 *      - ESP_ERR_INVALID_ARG: `handle` is invalid
 */
esp_err_t esp_wifi_sensing_fsm_ping_router_stop(esp_wifi_sensing_fsm_handle_t handle);

#ifdef __cplusplus
}
#endif
