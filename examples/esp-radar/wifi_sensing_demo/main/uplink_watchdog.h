/**
 * @file uplink_watchdog.h
 * @brief Restarts the unit when the internet path stops working for good.
 *
 * The Wi-Fi stack keeps reporting a healthy association while the route to the
 * outside world is dead. On this board that state was reached after roughly an
 * hour of uptime: the router stopped answering, every MQTT reconnect failed
 * with "Failed to open a new connection", and the existing reconnect loop never
 * recovered it. A power cycle always did. So the unit is restarted when the
 * path has been unusable for long enough that waiting longer is pointless.
 */
#ifndef UPLINK_WATCHDOG_H
#define UPLINK_WATCHDOG_H

#include <stdbool.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief Start the uplink watchdog task.
 *
 * @param host Broker hostname to probe. Connectivity to this name is what the
 *              remote dashboard actually depends on.
 * @param port Broker TCP port to probe.
 */
void uplink_watchdog_start(const char *host, uint16_t port);

/**
 * @brief Whether the watchdog is currently considering a restart.
 *
 * Exposed so the dashboard can tell "the unit is fine, the path is not" apart
 * from "the unit is gone".
 */
bool uplink_watchdog_is_failing(void);

/** @brief Seconds the path has been continuously unusable, 0 when healthy. */
uint32_t uplink_watchdog_failure_seconds(void);

/** @brief Number of watchdog restarts since the last healthy period. */
uint8_t uplink_watchdog_reboot_count(void);

#ifdef __cplusplus
}
#endif

#endif /* UPLINK_WATCHDOG_H */