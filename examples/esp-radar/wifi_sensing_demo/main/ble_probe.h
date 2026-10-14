/*
 * BLE advertising probe - see ble_probe.c for what this is for and why it is
 * deliberately no more than an advertisement.
 */

#ifndef BLE_PROBE_H
#define BLE_PROBE_H

#include <stdbool.h>

/**
 * @brief Start the NimBLE host and begin advertising.
 *
 * Safe to call only when Bluetooth is enabled in the build; otherwise this
 * compiles to nothing. Blocking is not an option here - it returns as soon as
 * the host is running and advertising starts from the sync callback.
 */
void ble_probe_start(void);

/** @brief Whether the probe is currently advertising. */
bool ble_probe_is_advertising(void);

#endif /* BLE_PROBE_H */