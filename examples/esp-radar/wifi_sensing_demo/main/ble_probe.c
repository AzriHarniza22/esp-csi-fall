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
 * The first question turned out to be answerable: a Samsung Note 20 Ultra sees
 * the advertisement and completes a connection while the radar runs, so the
 * Android advisory does not apply here. That made the next question worth
 * asking, which is how much throughput actually survives the shared radio.
 *
 * So this now carries a bare GATT service - a control characteristic the phone
 * can write ASCII commands to, and a data characteristic it can subscribe to -
 * and nothing else. No radar data is sent over it yet on purpose. Espressif
 * rates Wi-Fi sniffer RX alongside a connected BLE link as C1 and splits the
 * radio 50/50 between them, so the number that decides whether a BLE transport
 * is viable here is throughput and what it costs the radar. Building the real
 * protocol on top before measuring would be building on an assumption.
 *
 * Each notification starts with a 32-bit sequence number so the phone can spot
 * gaps directly, and is filled with a repeating pattern so a whole packet can
 * be told from a truncated one.
 *
 * The advertising interval is left at the default. Nothing is gained from a
 * fast one, and a busy radio makes the coexistence harder for no benefit.
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
#include "host/ble_gatt.h"
#include "host/ble_hs_mbuf.h"
#include "os/os_mbuf.h"

#include "ble_probe.h"

static const char *TAG = "ble_probe";

#define PROBE_DEVICE_NAME "ESP-RADAR"

/*
 * The unit has one job in this stage: push bytes at the phone as fast as the
 * shared radio allows, and say how many actually left. Espressif's coexistence
 * table rates Wi-Fi sniffer RX alongside a connected BLE link as C1, and the
 * coexistence policy splits the radio 50/50 between them once both are up. So
 * neither number is a property of the Bluetooth stack on its own - what has to
 * be measured is how much throughput survives while the radar is running, and
 * what that costs the radar.
 */
#define THRPT_SVC_UUID16        0x0001
#define THRPT_CHR_CTRL_UUID16   0x0002
#define THRPT_CHR_DATA_UUID16   0x0003

#define THRPT_UUID_DECLARE(uuid16)                            \
    ((const ble_uuid_t *) (&(ble_uuid128_t) BLE_UUID128_INIT(   \
        0xf1, 0x0e, 0x2c, 0x74, 0x9a, 0x0b, 0x4d, 0x88,          \
        0x91, 0x27, 0x3a, 0x55, uuid16, uuid16 >> 8, 0x00, 0x00  \
    )))

#define CTRL_RX_MAX 24
#define DEFAULT_PAYLOAD 253    /* ATT_MTU - 3; the real cap is negotiated at runtime */
#define STACK_DATA_MAX 512
#define NOTIFY_IN_FLIGHT 4

static uint8_t s_own_addr_type;
static int s_adv_started;
static ble_gap_event_fn *s_gap_cb;
static uint16_t s_data_handle;
static uint16_t s_conn_handle;
static bool s_notify_on;
static uint16_t s_mtu = 23;   /* the minimum until the phone negotiates */

/* Written by the notify task and read by the GAP callback, and by both from
 * two different tasks, so every field goes through s_lock. */
static struct {
    SemaphoreHandle_t lock;
    uint32_t queued;       /* handed to the stack */
    uint32_t transmitted;  /* confirmed gone by BLE_GAP_EVENT_NOTIFY_TX */
    uint32_t failed;       /* NOTIFY_TX reported an error */
    uint32_t stalled;      /* stack had no buffer room left */
    uint32_t last_seq;     /* sequence number assigned to the next packet */
    SemaphoreHandle_t room; /* one token per packet still in flight */
    int last_rc;           /* most recent notify return code, for diagnosis */
    uint16_t payload;
    uint16_t interval_ms;  /* 0 means as fast as possible */
    bool running;
    uint8_t payload_buf[STACK_DATA_MAX];
} s_m;


/* ------------------------------------------------------------------ *
 * Control characteristic: ASCII commands, so nRF Connect can drive this
 * without any app being written.
 *
 *   GO          push notifications as fast as the radio allows
 *   STOP        stop
 *   RATE <ms>   one notification every <ms> milliseconds
 *   SIZE <n>    payload of <n> bytes, clamped to the negotiated MTU
 * ------------------------------------------------------------------ */

static int thrpt_ctrl_access(uint16_t conn_handle, uint16_t attr_handle,
                             struct ble_gatt_access_ctxt *ctxt, void *arg)
{
    (void)conn_handle; (void)attr_handle; (void)arg;

    if (ctxt->op == BLE_GATT_ACCESS_OP_READ_CHR) {
        char reply[CTRL_RX_MAX];
        int rc = -1;
        xSemaphoreTake(s_m.lock, portMAX_DELAY);
        if (s_m.running) {
            rc = snprintf(reply, sizeof reply, "RUN %u %u",
                          (unsigned)s_m.payload, (unsigned)s_m.interval_ms);
        } else {
            rc = snprintf(reply, sizeof reply, "IDLE %u %u",
                          (unsigned)s_m.payload, (unsigned)s_m.interval_ms);
        }
        xSemaphoreGive(s_m.lock);
        return rc < 0 ? BLE_ATT_ERR_INSUFFICIENT_RES : os_mbuf_append(ctxt->om, reply, rc);
    }

    uint8_t cmd[CTRL_RX_MAX];
    uint16_t len = OS_MBUF_PKTLEN(ctxt->om);
    if (len == 0 || len > CTRL_RX_MAX) {
        return BLE_ATT_ERR_INSUFFICIENT_RES;
    }
    uint16_t out_len = 0;
    if (ble_hs_mbuf_to_flat(ctxt->om, cmd, sizeof cmd, &out_len) != 0) {
        return BLE_ATT_ERR_INSUFFICIENT_RES;
    }
    cmd[len] = '\0';

    ESP_LOGI(TAG, "command: \"%s\"", (char *)cmd);

    if (strcmp((char *)cmd, "GO") == 0) {
        xSemaphoreTake(s_m.lock, portMAX_DELAY);
        s_m.running = true;
        xSemaphoreGive(s_m.lock);
        return 0;
    }
    if (strcmp((char *)cmd, "STOP") == 0) {
        xSemaphoreTake(s_m.lock, portMAX_DELAY);
        s_m.running = false;
        xSemaphoreGive(s_m.lock);
        return 0;
    }

    unsigned value = 0;
    if (sscanf((char *)cmd, "RATE %u", &value) == 1 || sscanf((char *)cmd, "SIZE %u", &value) == 1) {
        xSemaphoreTake(s_m.lock, portMAX_DELAY);
        if (cmd[0] == 'R') {
            s_m.interval_ms = (uint16_t)value;
        } else {
            /* A payload larger than the negotiated ATT MTU would be split by
             * the stack and no longer measure one packet per notification. */
            uint16_t cap = (uint16_t)(s_mtu - 3);
            s_m.payload = (uint16_t)(value > cap ? cap : (value > STACK_DATA_MAX ? STACK_DATA_MAX : value));
        }
        ESP_LOGI(TAG, "now: %u byte payload, %u ms interval", (unsigned)s_m.payload, (unsigned)s_m.interval_ms);
        xSemaphoreGive(s_m.lock);
        return 0;
    }

    ESP_LOGW(TAG, "unrecognised command");
    return BLE_ATT_ERR_UNLIKELY;
}

static const struct ble_gatt_svc_def s_svcs[] = {
    {
        .type = BLE_GATT_SVC_TYPE_PRIMARY,
        .uuid = THRPT_UUID_DECLARE(THRPT_SVC_UUID16),
        .characteristics = (struct ble_gatt_chr_def[]) {
            {
                .uuid = THRPT_UUID_DECLARE(THRPT_CHR_CTRL_UUID16),
                .access_cb = thrpt_ctrl_access,
                .flags = BLE_GATT_CHR_F_READ | BLE_GATT_CHR_F_WRITE,
            },
            {
                .uuid = THRPT_UUID_DECLARE(THRPT_CHR_DATA_UUID16),
                .access_cb = thrpt_ctrl_access,
                .val_handle = &s_data_handle,
                .flags = BLE_GATT_CHR_F_NOTIFY | BLE_GATT_CHR_F_READ,
            },
            { 0 },
        },
    },
    { 0 },
};

/* ------------------------------------------------------------------ *
 * The notify pump. Runs whether or not it is subscribed, so the one
 * second report stays meaningful either way.
 * ------------------------------------------------------------------ */

static void thrpt_fill_and_send(void)
{
    uint16_t payload;
    uint32_t seq;
    xSemaphoreTake(s_m.lock, portMAX_DELAY);
    payload = s_m.payload;
    seq = ++s_m.last_seq;
    xSemaphoreGive(s_m.lock);

    /* Sequence number first, so the phone can see gaps directly, then a
     * repeating pattern so it can tell a whole packet from a truncated one. */
    s_m.payload_buf[0] = (uint8_t)(seq >> 24);
    s_m.payload_buf[1] = (uint8_t)(seq >> 16);
    s_m.payload_buf[2] = (uint8_t)(seq >> 8);
    s_m.payload_buf[3] = (uint8_t)(seq);
    for (uint16_t i = 4; i < payload; i++) {
        s_m.payload_buf[i] = (uint8_t)i;
    }

    struct os_mbuf *om = ble_hs_mbuf_from_flat(s_m.payload_buf, payload);
    if (om == NULL) {
        xSemaphoreTake(s_m.lock, portMAX_DELAY);
        s_m.stalled++;
        xSemaphoreGive(s_m.lock);
        return;
    }

    /* The stack takes ownership of om whatever happens, so there is no free
     * path to add here. */
    int rc = ble_gatts_notify_custom(s_conn_handle, s_data_handle, om);
    xSemaphoreTake(s_m.lock, portMAX_DELAY);
    s_m.last_rc = rc;
    if (rc == 0) {
        s_m.queued++;
    } else {
        /* 6 is BLE_HS_ENOMEM: the 24 ACL buffers are all in flight. That is
         * backpressure, not an error - it is the radio being full. */
        s_m.stalled++;
    }
    xSemaphoreGive(s_m.lock);
}

static void thrpt_task(void *arg)
{
    (void)arg;
    TickType_t last = xTaskGetTickCount();

    while (1) {
        bool running, subscribed;
        uint16_t interval;
        xSemaphoreTake(s_m.lock, portMAX_DELAY);
        running = s_m.running;
        subscribed = s_notify_on;
        interval = s_m.interval_ms;
        xSemaphoreGive(s_m.lock);

        if (running && subscribed) {
            /*
             * Wait for a free slot rather than spinning.
             *
             * There are only 24 ACL buffers, and a token is taken per packet
             * and returned when the controller reports the notification gone.
             * Spinning instead produced a pump that lost roughly 99% of its
             * packets and pegged the CPU while doing it - the numbers looked
             * like a slow radio when the real fault was unbounded queueing.
             */
            if (xSemaphoreTake(s_m.room, pdMS_TO_TICKS(1000)) != pdTRUE) {
                /* No completion in a second: the link is stuck, not busy. */
                xSemaphoreTake(s_m.lock, portMAX_DELAY);
                s_m.stalled++;
                xSemaphoreGive(s_m.lock);
            } else {
                thrpt_fill_and_send();
            }
        } else if (interval == 0) {
            vTaskDelay(pdMS_TO_TICKS(50));
        } else {
            vTaskDelay(pdMS_TO_TICKS(interval));
        }

        TickType_t now = xTaskGetTickCount();
        if (now - last >= pdMS_TO_TICKS(1000)) {
            uint32_t queued, tx, failed, stalled;
            int rc_seen;
            xSemaphoreTake(s_m.lock, portMAX_DELAY);
            queued = s_m.queued; tx = s_m.transmitted; failed = s_m.failed;
            stalled = s_m.stalled; rc_seen = s_m.last_rc;
            xSemaphoreGive(s_m.lock);

            ESP_LOGI(TAG,
                     "mtu=%u payload=%u | queued %u/s, tx %u/s (%.1f KB/s) | stalled %u, failed %u, last rc=%d | heap %u",
                     (unsigned)s_mtu, (unsigned)s_m.payload,
                     (unsigned)queued, (unsigned)tx, (tx * (float)s_m.payload) / 1024.0f,
                     (unsigned)stalled, (unsigned)failed, rc_seen,
                     (unsigned)esp_get_free_heap_size());

            xSemaphoreTake(s_m.lock, portMAX_DELAY);
            s_m.queued = 0; s_m.transmitted = 0; s_m.failed = 0; s_m.stalled = 0;
            xSemaphoreGive(s_m.lock);
            last = now;
        }
    }
}

static int probe_start_advertising(void);

static int probe_on_gap_event(struct ble_gap_event *event, void *arg)
{
    (void)arg;
    switch (event->type) {
    case BLE_GAP_EVENT_CONNECT:
        ESP_LOGI(TAG, "client connected (status %d, handle %u)",
                 event->connect.status, event->connect.conn_handle);
        if (event->connect.status == 0) {
            s_conn_handle = event->connect.conn_handle;
        }
        break;
    case BLE_GAP_EVENT_DISCONNECT:
        ESP_LOGI(TAG, "client disconnected (reason 0x%02x)", event->disconnect.reason);
        s_adv_started = 0;
        s_notify_on = false;
        s_conn_handle = 0;
        xSemaphoreTake(s_m.lock, portMAX_DELAY);
        s_m.running = false;
        xSemaphoreGive(s_m.lock);
        if (probe_start_advertising() == 0) {
            ESP_LOGI(TAG, "advertising again");
        }
        break;
    case BLE_GAP_EVENT_SUBSCRIBE:
        if (event->subscribe.attr_handle == s_data_handle) {
            s_notify_on = event->subscribe.cur_notify;
            ESP_LOGI(TAG, "notifications %s", s_notify_on ? "on" : "off");
        }
        break;
    case BLE_GAP_EVENT_MTU:
        s_mtu = event->mtu.value;
        ESP_LOGI(TAG, "negotiated MTU %u, so %u usable bytes per notification",
                 (unsigned)s_mtu, (unsigned)(s_mtu - 3));
        xSemaphoreTake(s_m.lock, portMAX_DELAY);
        if (s_m.payload > s_mtu - 3) {
            s_m.payload = s_mtu - 3;
        }
        xSemaphoreGive(s_m.lock);
        break;
    case BLE_GAP_EVENT_NOTIFY_TX:
        /*
         * This is the only place a notification is known to have actually
         * left, rather than merely been queued. BLE_HS_EDONE is reported for
         * indications and is not an error, but this service only notifies.
         */
        if (event->notify_tx.attr_handle == s_data_handle) {
            xSemaphoreTake(s_m.lock, portMAX_DELAY);
            if (event->notify_tx.status == 0) {
                s_m.transmitted++;
            } else {
                s_m.failed++;
            }
            xSemaphoreGive(s_m.lock);
            /* The buffer is free again whether or not the send worked. */
            xSemaphoreGive(s_m.room);
        }
        break;
    case BLE_GAP_EVENT_ADV_COMPLETE:
        ESP_LOGD(TAG, "advertising complete, reason 0x%02x", event->adv_complete.reason);
        break;
    default:
        break;
    }
    return 0;
}


/*
 * Start (or restart) advertising.
 *
 * Split out of the sync callback because NimBLE stops advertising the moment a
 * client attaches, and this unit is meant to be found by a phone - so it has to
 * come back up when that client leaves. Without this the unit advertises once
 * at boot and is then unreachable forever, which is exactly the kind of fault
 * that only shows up after someone actually tries to reconnect.
 */
static int probe_start_advertising(void)
{
    struct ble_hs_adv_fields fields;
    struct ble_gap_adv_params adv_params;
    int rc;

    memset(&fields, 0, sizeof fields);
    fields.flags = BLE_HS_ADV_F_DISC_GEN | BLE_HS_ADV_F_BREDR_UNSUP;
    const char *name = ble_svc_gap_device_name();
    fields.name = (uint8_t *)name;
    fields.name_len = (uint8_t)strlen(name);
    fields.name_is_complete = 1;

    rc = ble_gap_adv_set_fields(&fields);
    if (rc != 0) {
        ESP_LOGE(TAG, "could not build the advertisement: rc=%d", rc);
        return rc;
    }

    /*
     * Undirected connectable, not a beacon. A non-connectable beacon would
     * still be visible, but the next stage needs a connection, so this doubles
     * as a rehearsal for that.
     */
    memset(&adv_params, 0, sizeof adv_params);
    adv_params.conn_mode = BLE_GAP_CONN_MODE_UND;
    adv_params.disc_mode = BLE_GAP_DISC_MODE_GEN;

    rc = ble_gap_adv_start(s_own_addr_type, NULL, BLE_HS_FOREVER,
                           &adv_params, s_gap_cb, NULL);
    if (rc != 0) {
        ESP_LOGE(TAG, "could not start advertising: rc=%d", rc);
        return rc;
    }
    s_adv_started = 1;
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

    (void)adv_params;
    (void)fields;
    (void)name;
    rc = probe_start_advertising();
    if (rc != 0) {
        return;
    }

    s_adv_started = 1;
    ESP_LOGI(TAG, "service queued, data characteristic at ATT handle %u", s_data_handle);
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
    s_m.lock = xSemaphoreCreateMutex();
    /*
     * A small window rather than the full buffer count: enough to keep the
     * radio busy between completions, small enough that a stalled connection
     * is noticed in well under a second instead of after 24 packets.
     */
    s_m.room = xSemaphoreCreateCounting(NOTIFY_IN_FLIGHT, NOTIFY_IN_FLIGHT);
    s_m.payload = DEFAULT_PAYLOAD;

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
    /*
     * Services have to be queued before the host task starts running. The ATT
     * handles are assigned by ble_gatts_start(), which happens inside the host
     * startup, so registering from the sync callback would be too late and the
     * notify handle would stay 0.
     */
    /*
     * count_cfg then add_svcs, in that order, and both are required.
     *
     * count_cfg is what tells NimBLE how many ATT attributes and client
     * configurations the services need; add_svcs only queues the definitions.
     * Skipping count_cfg leaves those pools unsized, so ble_gatts_start() fails
     * during host startup and the unit resets in a loop. That is an assert
     * inside NimBLE rather than an error return, so it looks like a crash with
     * no usable cause.
     */
    int rc = ble_gatts_count_cfg(s_svcs);
    if (rc != 0) {
        ESP_LOGE(TAG, "could not size the service: rc=%d", rc);
        return;
    }

    rc = ble_gatts_add_svcs(s_svcs);
    if (rc != 0) {
        ESP_LOGE(TAG, "could not queue the service: rc=%d", rc);
        return;
    }

    nimble_port_freertos_init(probe_host_task);

    /*
     * The pump starts with the host. It does nothing until a phone subscribes
     * and sends GO, and it reports every second either way, which is what makes
     * an idle baseline comparable to a loaded one.
     */
    if (xTaskCreate(thrpt_task, "ble_thrpt", 4096, NULL, 4, NULL) != pdPASS) {
        ESP_LOGE(TAG, "could not start the throughput task");
        return;
    }
}

bool ble_probe_is_advertising(void)
{
    return s_adv_started;
}