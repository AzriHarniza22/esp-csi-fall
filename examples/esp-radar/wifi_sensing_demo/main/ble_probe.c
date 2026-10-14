/*
 * BLE advertising probe.
 *
 * This exists to answer one question before anything else is built on top of it:
 * can a phone actually see this unit?
 *
 * That is not a formality. Espressif publishes an advisory that Wi-Fi in HT40
 * mode breaks the Bluetooth LE configuration badly enough that some Android
 * phones never receive the advertising PDU at all. This unit runs HT40 - the
 * radar measured it carrying only high throughput frames - so if that advisory
 * applies here, no amount of GATT service or a client application will help.
 * Finding that out with thirty lines of advertising is a far better outcome
 * than finding it out after building the transport.
 *
 * So this deliberately does the least that can answer the question:
 *
 *   - advertising only, no GATT server and no characteristics
 *   - a name, so it can be identified in a scan
 *   - logging of the radio state before and after Bluetooth starts, because
 *     whether the stack fits in the heap the radar leaves is the other thing
 *     that could rule this out, and that is worth knowing at the same time
 *
 * The advertising interval is the default rather than something fast. There is
 * nothing to gain from a short one here - the question is whether the phone can
 * see it at all - and a busy radio makes the coexistence harder for no benefit.
 */

#include "esp_log.h"
#include "esp_heap_caps.h"
#include "esp_system.h"
#include "nimble/nimble_port.h"
#include "nimble/nimble_port_freertos.h"
#include "host/ble_hs.h"
#include "host/util/util.h"
#include "services/gap/ble_svc_gap.h"
#include "host/ble_gap.h"

#include "ble_probe.h"

static const char *TAG = "ble_probe";

#define PROBE_DEVICE_NAME "ESP-RADAR"
#define PROBE_ADV_DATA_MAX 29   /* the short, legacy advertising packet limit */

static uint8_t s_own_addr_type;
static int s_adv_started;
static ble_gap_event_fn *s_gap_cb;

static int probe_on_gap_event(struct ble_gap_event *event, void *arg)
{
    (void)arg;
    switch (event->type) {
    case BLE_GAP_EVENT_CONNECT:
        ESP_LOGI(TAG, "a client connected (status %d, handle %u)",
                 event->connect.status, event->connect.conn_handle);
        break;
    case BLE_GAP_EVENT_DISCONNECT:
        ESP_LOGI(TAG, "client disconnected (reason 0x%02x)", event->disconnect.reason);
        s_adv_started = 0;
        break;
    case BLE_GAP_EVENT_ADV_COMPLETE:
        ESP_LOGD(TAG, "advertising complete, reason 0x%02x", event->adv_complete.reason);
        break;
    default:
        break;
    }
    return 0;
}

static void probe_on_sync(void)
{
    struct ble_hs_adv_fields fields;
    struct ble_gap_adv_params adv_params;
    int rc;

    rc = ble_hs_id_infer_auto(0, &s_own_addr_type);
    if (rc != 0) {
        ESP_LOGE(TAG, "no usable Bluetooth address: rc=%d", rc);
        return;
    }

    uint8_t addr[6] = {0};
    rc = ble_hs_id_copy_addr(s_own_addr_type, addr, NULL);
    if (rc == 0) {
        ESP_LOGI(TAG, "advertising address %02x:%02x:%02x:%02x:%02x:%02x (type %d)",
                 addr[0], addr[1], addr[2], addr[3], addr[4], addr[5], s_own_addr_type);
    }

    rc = ble_svc_gap_device_name_set(PROBE_DEVICE_NAME);
    if (rc != 0) {
        ESP_LOGE(TAG, "could not set the name: rc=%d", rc);
        return;
    }

    /*
     * Flags and name only. No service UUID and no GATT server - the question
     * here is whether the phone can see the advertisement at all, and every
     * extra field is another thing that could stop that happening.
     *
     * General discoverable so a scanner lists it without asking for a
     * specific service, and BR/EDR unsupported because Bluetooth Classic is
     * switched off in this build.
     */
    memset(&fields, 0, sizeof fields);
    fields.flags = BLE_HS_ADV_F_DISC_GEN | BLE_HS_ADV_F_BREDR_UNSUP;
    const char *name = ble_svc_gap_device_name();
    fields.name = (uint8_t *)name;
    fields.name_len = (uint8_t)strlen(name);
    fields.name_is_complete = 1;

    rc = ble_gap_adv_set_fields(&fields);
    if (rc != 0) {
        ESP_LOGE(TAG, "could not build the advertisement: rc=%d", rc);
        return;
    }

    /*
     * Undirected connectable, not a beacon.
     *
     * A non-connectable beacon does not need to be connectable to be seen, but
     * the next stage needs a connection and a scan that succeeds against a
     * beacon proves less than a scan that can actually attach. Connectable
     * advertising costs one extra byte and makes this a fair rehearsal.
     */
    memset(&adv_params, 0, sizeof adv_params);
    adv_params.conn_mode = BLE_GAP_CONN_MODE_UND;
    adv_params.disc_mode = BLE_GAP_DISC_MODE_GEN;

    rc = ble_gap_adv_start(s_own_addr_type, NULL, BLE_HS_FOREVER,
                           &adv_params, s_gap_cb, NULL);
    if (rc != 0) {
        ESP_LOGE(TAG, "could not start advertising: rc=%d", rc);
        return;
    }

    s_adv_started = 1;
    ESP_LOGI(TAG, "advertising as \"%s\" - scan for it from the phone", name);
}

static void probe_host_task(void *param)
{
    (void)param;
    nimble_port_run();
    nimble_port_freertos_deinit();
}

void ble_probe_start(void)
{
    ESP_LOGI(TAG, "heap before Bluetooth: %u bytes free, %u largest block",
             (unsigned)esp_get_free_heap_size(),
             (unsigned)heap_caps_get_largest_free_block(MALLOC_CAP_INTERNAL));

    s_gap_cb = probe_on_gap_event;
    ble_hs_cfg.sync_cb = probe_on_sync;
    /*
     * No store callback: nothing here persists across a reset, and the unit has
     * no reason to carry Bluetooth state in NVS where Wi-Fi keeps its own.
     */
    ble_hs_cfg.store_status_cb = ble_store_util_status_rr;

    if (nimble_port_init() != 0) {
        ESP_LOGE(TAG, "the Bluetooth host stack would not start");
        return;
    }

    /*
     * NimBLE carries the host protocol; the sync callback tells it when the
     * controller is ready and advertising may begin.
     */
    nimble_port_freertos_init(probe_host_task);
}

bool ble_probe_is_advertising(void)
{
    return s_adv_started;
}