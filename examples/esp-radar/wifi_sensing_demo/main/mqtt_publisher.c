/*
 * SPDX-FileCopyrightText: 2026
 *
 * See mqtt_publisher.h for why this is publish-only.
 */
#include "mqtt_publisher.h"
#include "ht_stimulus.h"
#include "uplink_watchdog.h"
#include "web_serial_monitor.h"

#include <inttypes.h>
#include <string.h>

#include "esp_event.h"
#include "esp_log.h"
#include "esp_mac.h"
#include "esp_wifi.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
#include "freertos/queue.h"
#include "freertos/task.h"
#include "mqtt_client.h"
#include "mqtt5_client.h"
#include "nvs.h"
#include "nvs_flash.h"

static const char *TAG = "mqtt_pub";

/*
 * EMQX Cloud Serverless hands out a per-deployment root that chains up to
 * DigiCert Global Root G2. Verifying against the leaf would break when EMQX
 * rotates the intermediate; verifying against this public root keeps the
 * firmware working across that rotation, which is why EMQX expires the served
 * certificate years out.
 */
static const char *s_ca_cert =
    "-----BEGIN CERTIFICATE-----\n"
    "MIIDjjCCAnagAwIBAgIQAzrx5qcRqaC7KGSxHQn65TANBgkqhkiG9w0BAQsFADBh\n"
    "MQswCQYDVQQGEwJVUzEVMBMGA1UEChMMRGlnaUNlcnQgSW5jMRkwFwYDVQQLExB3\n"
    "d3cuZGlnaWNlcnQuY29tMSAwHgYDVQQDExdEaWdpQ2VydCBHbG9iYWwgUm9vdCBH\n"
    "MjAeFw0xMzA4MDExMjAwMDBaFw0zODAxMTUxMjAwMDBaMGExCzAJBgNVBAYTAlVT\n"
    "MRUwEwYDVQQKEwxEaWdpQ2VydCBJbmMxGTAXBgNVBAsTEHd3dy5kaWdpY2VydC5j\n"
    "b20xIDAeBgNVBAMTF0RpZ2lDZXJ0IEdsb2JhbCBSb290IEcyMIIBIjANBgkqhkiG\n"
    "9w0BAQEFAAOCAQ8AMIIBCgKCAQEAuzfNNNx7a8myaJCtSnX/RrohCgiN9RlUyfuI\n"
    "2/Ou8jqJkTx65qsGGmvPrC3oXgkkRLpimn7Wo6h+4FR1IAWsULecYxpsMNzaHxmx\n"
    "1x7e/dfgy5SDN67sH0NO3Xss0r0upS/kqbitOtSZpLYl6ZtrAGCSYP9PIUkY92eQ\n"
    "q2EGnI/yuum06ZIya7XzV+hdG82MHauVBJVJ8zUtluNJbd134/tJS7SsVQepj5Wz\n"
    "tCO7TG1F8PapspUwtP1MVYwnSlcUfIKdzXOS0xZKBgyMUNGPHgm+F6HmIcr9g+UQ\n"
    "vIOlCsRnKPZzFBQ9RnbDhxSJITRNrw9FDKZJobq7nMWxM4MphQIDAQABo0IwQDAP\n"
    "BgNVHRMBAf8EBTADAQH/MA4GA1UdDwEB/wQEAwIBhjAdBgNVHQ4EFgQUTiJUIBiV\n"
    "5uNu5g/6+rkS7QYXjzkwDQYJKoZIhvcNAQELBQADggEBAGBnKJRvDkhj6zHd6mcY\n"
    "1Yl9PMWLSn/pvtsrF9+wX3N3KjITOYFnQoQj8kVnNeyIv/iPsGEMNKSuIEyExtv4\n"
    "NeF22d+mQrvHRAiGfzZ0JFrabA0UWTW98kndth/Jsw1HKj2ZL7tcu7XUIOGZX1NG\n"
    "Fdtom/DzMNU+MeKNhJ7jitralj41E6Vf8PlwUHBHQRFXGU7Aj64GxJUTFy8bJZ91\n"
    "8rGOmaFvE7FBcf6IKshPECBV1/MUReXgRPTqh5Uykw7+U0b6LJ3/iyK5S9kJRaTe\n"
    "pLiaWN0bfVKfjllDiIGknibVb63dDcY3fe0Dkhvld1927jyNxF1WW6LZZm6zNTfl\n"
    "MrY=\n"
    "-----END CERTIFICATE-----\n";

#define MQTT_NVS_NAMESPACE "mqttcfg"
#define MQTT_NVS_MAX_LEN    96
#define MQTT_RESP_TOPIC_MAX_LEN  72
#define MQTT_CORRELATION_MAX_LEN 16
#define MQTT_STATUS_PERIOD_MS 15000

/*
 * How long the send buffer may stay backed up before the connection is
 * declared dead. Comfortably longer than the time it takes to drain a normal
 * backlog, so healthy operation never trips it.
 */
#define MQTT_OUTBOX_STUCK_MS 45000

/*
 * Send-buffer size above which the backlog counts as a dead connection rather
 * than normal in-flight traffic. Measured: a healthy unit sits under 1 KB, a
 * stalled one parks between 4 and 7 KB and stays there.
 */
#define MQTT_OUTBOX_DEAD_BYTES 4000

/*
 * End-to-end liveness probe.
 *
 * The send-buffer check above only catches the failure when it is busy enough
 * to pile up. Measured on this unit, publishing slowly leaves the buffer
 * small while nothing still reaches the broker, so the buffer alone is not
 * proof of life.
 *
 * A QoS 1 publish is used because the broker has to acknowledge it. If the
 * unit's data is genuinely arriving, the acknowledgement clears the message
 * back out of the buffer; if it is not, the message sits there waiting to be
 * retransmitted. That turns "are my publishes reaching the broker" into
 * something the unit can answer for itself, with no help from the network.
 */
#define MQTT_LIVENESS_PERIOD_MS  15000
#define MQTT_LIVENESS_TIMEOUT_MS  25000

/*
 * MQTT keepalive on this unit is deliberately short. The stock setting waits
 * roughly half a keepalive interval plus a network timeout before it admits a
 * session is dead, which is over thirty seconds of silence; measured on this
 * link a control round trip that landed in that window took seventeen.
 * Fifteen seconds notices sooner, and the probes above usually catch it first.
 */

/*
 * Shortest gap between two connection rebuilds. The fault this guards against
 * can outlive a rebuild, and rebuilding in a tight loop would leave the unit
 * offline continuously instead of recovering on and off.
 */
#define MQTT_RECOVERY_MIN_MS 60000
#define MQTT_QUEUE_LEN      32
#define MQTT_MAX_PEERS      3

/* One queued sample per peer; the dashboard cares about the newest. */
typedef struct {
    char name[16];
    uint8_t mac[6];
    float jitter;
    float wander;
    bool motion;
    bool presence_ready;
} mqtt_sample_t;

/* Per-peer publish slot, so a rate limit never silences a quiet peer. */
typedef struct {
    char name[16];
    uint8_t mac[6];
    bool seen;
    bool dirty;
    bool has_signal;      /* ever produced a non-zero reading */
    uint32_t last_publish_ms;
    mqtt_sample_t newest;
    /*
     * What was last put on the wire, kept so a sample that says exactly what
     * the previous one said can be recognised and skipped.
     */
    mqtt_sample_t published;
    bool has_published;
} mqtt_peer_slot_t;

static esp_mqtt_client_handle_t s_client = NULL;

/*
 * At file scope so the status snapshot can name the peers it describes. The
 * device address of a peer never changes, so carrying it in every reading was
 * paying for the same seventeen characters several times a second.
 */
static mqtt_peer_slot_t s_slots[MQTT_MAX_PEERS];

/*
 * Shortest gap between two readings for the same peer.
 *
 * Telemetry used to go out on a fixed interval whether or not anything had
 * moved. Measured on this unit that was overwhelmingly wasted: a hundred and
 * forty four readings in a row carried only eleven distinct values. Reading a
 * chart does not need the same number told to it repeatedly, so a reading is
 * now sent when it differs from the last one sent.
 *
 * The floor stays because jitter wanders by very small amounts, and a value
 * that moves only in its last digits is not worth a message.
 */
#define MQTT_PUBLISH_MIN_MS 500
static volatile bool s_connected = false;
static volatile bool s_resubscribe = false;
static volatile bool s_state_pending = false;
/*
 * Send-buffer bookkeeping for the stall check in mqtt_task.
 */
static int s_outbox_last_bytes = 0;
static uint32_t s_outbox_stuck_ms = 0;
static uint32_t s_liveness_sent_ms = 0;
static uint32_t s_liveness_ok_ms = 0;
static int s_liveness_base_bytes = 0;
static bool s_liveness_pending = false;
static uint32_t s_recovery_ms = 0;
static QueueHandle_t s_queue = NULL;
static char s_prefix[MQTT_NVS_MAX_LEN] = CONFIG_ESP_WIFI_SENSING_MQTT_TOPIC_PREFIX;
/*
 * A queued reply. It carries the response topic and correlation data from the
 * command so the MQTT 5 Request/Response handshake can be completed, and falls
 * back to the shared ack topic when the sender did not ask for one.
 */
typedef struct {
    char text[256];
    char response_topic[MQTT_RESP_TOPIC_MAX_LEN];
    uint8_t correlation[MQTT_CORRELATION_MAX_LEN];
    uint8_t correlation_len;
} mqtt_ack_t;

static QueueHandle_t s_ack_queue = NULL;

static char s_client_id[40] = CONFIG_ESP_WIFI_SENSING_MQTT_CLIENT_ID;
static char s_password[MQTT_NVS_MAX_LEN] = CONFIG_ESP_WIFI_SENSING_MQTT_PASSWORD;

static void publish_status(bool online);
static void mqtt_client_create(void);
static void mqtt_exec_enqueue(const void *data, int len,
                              const char *response_topic, int response_topic_len,
                              const void *correlation, uint8_t correlation_len);
static const char *response_topic_is_allowed(const char *topic, int topic_len);

/* ---------------------------------------------------------------- NVS ----- */

static void nvs_store_str(nvs_handle_t h, const char *key, const char *value)
{
    if (value && *value) {
        nvs_set_str(h, key, value);
    }
}

static void nvs_load_str(nvs_handle_t h, const char *key, char *out, size_t out_len)
{
    size_t len = out_len;
    if (nvs_get_str(h, key, out, &len) != ESP_OK) {
        out[0] = '\0';
    }
}

/*
 * Load the saved broker settings, seeding NVS from Kconfig the first time. The
 * Kconfig values stay as a fallback rather than being written back on every
 * boot, so HMSCMD MQTT_CONFIG survives a reflash.
 */
/*
 * The password is deliberately kept out of mqtt_settings_t so that it never
 * reaches a reporting call such as HMSCMD MQTT_STATUS. It is read on its own
 * here, only to hand straight to the client config.
 */
static void load_password(char *out, size_t len)
{
    nvs_handle_t h;
    if (nvs_open(MQTT_NVS_NAMESPACE, NVS_READONLY, &h) != ESP_OK) {
        snprintf(out, len, "%s", CONFIG_ESP_WIFI_SENSING_MQTT_PASSWORD);
        return;
    }
    nvs_load_str(h, "pass", out, len);
    nvs_close(h);
    if (out[0] == '\0') {
        snprintf(out, len, "%s", CONFIG_ESP_WIFI_SENSING_MQTT_PASSWORD);
    }
}

static void load_settings(void)
{
    nvs_handle_t h;
    bool seeded = false;
    if (nvs_open(MQTT_NVS_NAMESPACE, NVS_READWRITE, &h) != ESP_OK) {
        return;
    }
    char tmp[MQTT_NVS_MAX_LEN];

    nvs_load_str(h, "host", tmp, sizeof(tmp));
    if (tmp[0] == '\0') {
        nvs_store_str(h, "host", CONFIG_ESP_WIFI_SENSING_MQTT_BROKER);
        seeded = true;
    }
    nvs_load_str(h, "user", tmp, sizeof(tmp));
    if (tmp[0] == '\0') {
        nvs_store_str(h, "user", CONFIG_ESP_WIFI_SENSING_MQTT_USERNAME);
        seeded = true;
    }
    nvs_load_str(h, "pass", tmp, sizeof(tmp));
    if (tmp[0] == '\0') {
        nvs_store_str(h, "pass", CONFIG_ESP_WIFI_SENSING_MQTT_PASSWORD);
        seeded = true;
    }
    nvs_load_str(h, "prefix", tmp, sizeof(tmp));
    if (tmp[0] == '\0') {
        nvs_store_str(h, "prefix", CONFIG_ESP_WIFI_SENSING_MQTT_TOPIC_PREFIX);
        seeded = true;
    }
    int32_t port = 0;
    if (nvs_get_i32(h, "port", &port) != ESP_OK) {
        nvs_set_i32(h, "port", CONFIG_ESP_WIFI_SENSING_MQTT_PORT);
    }
    nvs_commit(h);
    nvs_close(h);
    if (seeded) {
        ESP_LOGI(TAG, "seeded broker settings from Kconfig");
    }
}

esp_err_t mqtt_publisher_get_settings(mqtt_settings_t *out)
{
    nvs_handle_t h;
    if (!out) {
        return ESP_ERR_INVALID_ARG;
    }
    memset(out, 0, sizeof(*out));
    if (nvs_open(MQTT_NVS_NAMESPACE, NVS_READONLY, &h) != ESP_OK) {
        return ESP_FAIL;
    }
    nvs_load_str(h, "host", out->host, sizeof(out->host));
    nvs_load_str(h, "user", out->user, sizeof(out->user));
    nvs_load_str(h, "prefix", out->prefix, sizeof(out->prefix));
    int32_t port = 0;
    nvs_get_i32(h, "port", &port);
    out->port = port;
    nvs_close(h);
    return ESP_OK;
}

esp_err_t mqtt_publisher_set_settings(const char *host, int port, const char *user,
                                      const char *pass, const char *prefix)
{
    nvs_handle_t h;
    if (!host || !*host || port <= 0 || port > 65535) {
        return ESP_ERR_INVALID_ARG;
    }
    if (nvs_open(MQTT_NVS_NAMESPACE, NVS_READWRITE, &h) != ESP_OK) {
        return ESP_FAIL;
    }
    nvs_store_str(h, "host", host);
    nvs_set_i32(h, "port", port);
    nvs_store_str(h, "user", user);
    nvs_store_str(h, "pass", pass);
    nvs_store_str(h, "prefix", prefix);
    esp_err_t err = nvs_commit(h);
    nvs_close(h);
    if (err != ESP_OK) {
        return err;
    }
    /* Reconnect so the change takes effect without a reboot. */
    mqtt_client_create();
    return ESP_OK;
}

/* --------------------------------------------------------------- client --- */

static void mqtt_event_handler(void *arg, esp_event_base_t base, int32_t event_id,
                               void *event_data)
{
    (void)arg;
    (void)base;
    (void)event_data;

    switch (event_id) {
    case MQTT_EVENT_CONNECTED:
        s_connected = true;
        ESP_LOGI(TAG, "connected");
        /*
         * The subscribe itself is done from mqtt_task on the connect edge, not
         * from here: this callback runs inside the MQTT task, and issuing a
         * client call from it is exactly what used to break the session.
         */
        s_resubscribe = true;
        s_outbox_last_bytes = 0;
        s_outbox_stuck_ms = (uint32_t)(esp_timer_get_time() / 1000ULL);
        s_liveness_sent_ms = s_outbox_stuck_ms;
        s_liveness_ok_ms = s_outbox_stuck_ms;
        s_liveness_pending = false;
        break;
    case MQTT_EVENT_DATA: {
        const esp_mqtt_event_t *event = (const esp_mqtt_event_t *)event_data;
        int len = event->topic_len ? event->topic_len : (int)strlen(event->topic);
        char cmd_topic[MQTT_NVS_MAX_LEN + 8];
        snprintf(cmd_topic, sizeof(cmd_topic), "%s/cmd", s_prefix);
        if (len == (int)strlen(cmd_topic) &&
            strncmp(event->topic, cmd_topic, (size_t)len) == 0 &&
            event->data_len > 0) {
            const char *resp = NULL;
            int resp_len = 0;
            const void *corr = NULL;
            uint8_t corr_len = 0;

            /*
             * MQTT 5 Request/Response. Only meaningful for a publisher that set
             * the properties; the older fixed ack topic still works for anyone
             * who does not.
             */
            if (event->property) {
                resp = response_topic_is_allowed(event->property->response_topic,
                                                 event->property->response_topic_len);
                if (resp) {
                    resp_len = event->property->response_topic_len;
                    corr = event->property->correlation_data;
                    corr_len = event->property->correlation_data_len;
                }
            }
            if (event->property && event->property->response_topic &&
                event->property->response_topic_len > 0 && !resp) {
                ESP_LOGW(TAG, "src=mqtt rejected response topic outside our namespace");
            }
            mqtt_exec_enqueue(event->data, event->data_len, resp, resp_len, corr, corr_len);
        }
        break;
    }
    case MQTT_EVENT_DISCONNECTED:
        s_connected = false;
        ESP_LOGW(TAG, "disconnected");
        /*
         * Acks that were in flight are lost with the session. The retained copy
         * of the last ack survives on the broker, so the dashboard can still
         * read it; nothing is resent to a session that no longer exists.
         */
        break;
    case MQTT_EVENT_ERROR:
        /* A TLS or auth failure otherwise repeats forever with only this line. */
        s_connected = false;
        ESP_LOGW(TAG, "mqtt error");
        break;
    default:
        break;
    }
}

static void mqtt_client_create(void)
{
    mqtt_settings_t cfg = {0};
    if (mqtt_publisher_get_settings(&cfg) != ESP_OK || cfg.host[0] == '\0') {
        return;
    }

    if (s_client) {
        esp_mqtt_client_stop(s_client);
        esp_mqtt_client_destroy(s_client);
        s_client = NULL;
    }
    snprintf(s_prefix, sizeof(s_prefix), "%s", cfg.prefix[0] ? cfg.prefix : "radar/esp32");

    uint8_t mac[6] = {0};
    esp_read_mac(mac, ESP_MAC_WIFI_STA);
    snprintf(s_client_id, sizeof(s_client_id), "%s-%02x%02x%02x",
             CONFIG_ESP_WIFI_SENSING_MQTT_CLIENT_ID, mac[3], mac[4], mac[5]);

    load_password(s_password, sizeof(s_password));

    char uri[160];
    snprintf(uri, sizeof(uri), "mqtts://%s:%d", cfg.host, cfg.port);

    /*
     * The will topic must outlive the client, so it is built here rather than on
     * a stack inside the event handler.
     */
    static char will_topic[MQTT_NVS_MAX_LEN + 16];
    static char will_msg[64];
    snprintf(will_topic, sizeof(will_topic), "%s/status", s_prefix);
    snprintf(will_msg, sizeof(will_msg), "{\"online\":false,\"target\":\"%s\"}",
             CONFIG_IDF_TARGET);

    const esp_mqtt_client_config_t mqtt_cfg = {
        .broker.address.uri = uri,
        .broker.verification.certificate = s_ca_cert,
        .credentials.username = cfg.user,
        .credentials.authentication.password = s_password,
        .credentials.client_id = s_client_id,
        .session.keepalive = CONFIG_ESP_WIFI_SENSING_MQTT_KEEPALIVE_S,
        .session.protocol_ver = MQTT_PROTOCOL_V_5,
        .session.last_will = {
            .topic = will_topic,
            .msg = will_msg,
            .qos = 1,
            .retain = true,
        },
        .network.timeout_ms = 10000,
    };

    s_client = esp_mqtt_client_init(&mqtt_cfg);
    if (!s_client) {
        ESP_LOGE(TAG, "client init failed");
        return;
    }
    esp_mqtt_client_register_event(s_client, MQTT_EVENT_ANY, mqtt_event_handler, NULL);

    /*
     * MQTT 5 properties. will_delay keeps a brief Wi-Fi drop from publishing a
     * misleading offline; session_expiry is what makes the broker hold QoS 1
     * commands while the device is away.
     */
    /*
     * maximum_packet_size must be set explicitly. MQTT 5 reads it as "the
     * largest packet the client will accept", and 0 means none, so leaving it
     * zero makes the broker close the session the moment CONNACK is sent.
     * The radar payloads are ~200 bytes; 1024 leaves room for the ACK echoes.
     * receive_maximum likewise has to be non-zero or no publish is allowed.
     */
    /*
     * MQTT 5 session properties. will_delay keeps a brief Wi-Fi drop from
     * publishing a misleading offline, and the session expiry interval is what
     * makes the broker hold QoS 1 commands while the device is away.
     *
     * maximum_packet_size must be non-zero: MQTT 5 reads it as "largest packet
     * the client will accept", and 0 means none, so a zero value makes the
     * broker close the session right after CONNACK. The radar payloads are
     * ~200 bytes, so 1024 leaves room for the echoed ACKs. receive_maximum has
     * the same all-or-nothing reading and must also be non-zero.
     */
    esp_mqtt5_client_set_connect_property(s_client, &(esp_mqtt5_connection_property_config_t){
        .session_expiry_interval = CONFIG_ESP_WIFI_SENSING_MQTT_SESSION_EXPIRY_S,
        .receive_maximum = 8,
        .maximum_packet_size = 1024,
        .will_delay_interval = CONFIG_ESP_WIFI_SENSING_MQTT_WILL_DELAY_S,
        .message_expiry_interval = CONFIG_ESP_WIFI_SENSING_MQTT_SESSION_EXPIRY_S,
    });
    esp_err_t err = esp_mqtt_client_start(s_client);
    if (err != ESP_OK) {
        ESP_LOGW(TAG, "start failed: %s", esp_err_to_name(err));
    }
}

/* -------------------------------------------------------------- publish --- */

/*
 * The status topic carries the whole authoritative state, not just a heartbeat.
 *
 * This is what the dashboard treats as truth. It matters because the command
 * ack on radar/esp32/ack turned out to be unreliable: the packet reaches the
 * outbox but the broker does not always answer, so a dashboard that waits for
 * the ack would leave its buttons spinning. Confirming against a state
 * snapshot that is published after every command works regardless, and it also
 * repairs the UI whenever a message is missed.
 */
static void publish_status(bool online)
{
    if (!s_client) {
        return;
    }
    char topic[MQTT_NVS_MAX_LEN + 16];
    char payload[512];

    ht_stimulus_config_t stim = {0};
    (void)ht_stimulus_get_config(&stim);
    wifi_ap_record_t ap = {0};
    esp_wifi_sta_get_ap_info(&ap);

    /*
     * The addresses of the peers being reported on.
     *
     * They used to travel inside every reading. A MAC does not change while a
     * peer is tracked, so a dashboard that wants it can read it once from here
     * and label its charts from that, instead of being handed the same
     * seventeen characters several times a second to throw away.
     */
    /* name in quotes plus a MAC in quotes, plus separator and slack */
    char peers[MQTT_MAX_PEERS * 40];
    size_t pn = 0;
    peers[0] = '\0';
    for (size_t i = 0; i < MQTT_MAX_PEERS; i++) {
        if (!s_slots[i].seen) {
            continue;
        }
        int w = snprintf(peers + pn, sizeof(peers) - pn, "%s\"%s\":\"" MACSTR "\"",
                         pn ? "," : "", s_slots[i].name, MAC2STR(s_slots[i].mac));
        if (w < 0 || (size_t)w >= sizeof(peers) - pn) {
            break;
        }
        pn += (size_t)w;
    }

    snprintf(topic, sizeof(topic), "%s/status", s_prefix);
    snprintf(payload, sizeof(payload),
             "{\"peer\":\"status\",\"online\":%s,\"target\":\"%s\","
             "\"stimulus\":{\"enabled\":%s,\"burst_bytes\":%lu,\"pause_ms\":%lu},"
             "\"allow_reconfig\":%s,\"uplink_failing\":%s,"
             "\"uplink_down_s\":%lu,\"restarts\":%u,\"outbox\":%d,"
             "\"rssi\":%d,\"bssid\":\"" MACSTR "\",\"channel\":%u,"
             "\"peers\":{%s},\"ts_ms\":%" PRIu64 "}",
             online ? "true" : "false", CONFIG_IDF_TARGET,
             stim.enabled ? "true" : "false", (unsigned long)stim.burst_bytes, (unsigned long)stim.pause_ms,
             CONFIG_ESP_WIFI_SENSING_MQTT_ALLOW_RECONFIG ? "true" : "false",
             /*
              * The board can be perfectly alive while the path to the broker is
              * not, which looks identical to "offline" from the outside. These
              * three fields let the dashboard say which of the two it is.
              */
             uplink_watchdog_is_failing() ? "true" : "false",
             (unsigned long)uplink_watchdog_failure_seconds(),
             (unsigned)uplink_watchdog_reboot_count(),
             esp_mqtt_client_get_outbox_size(s_client),
             ap.rssi, MAC2STR(ap.bssid), ap.primary, peers,
             (uint64_t)(esp_timer_get_time() / 1000ULL));
    /*
     * QoS 0, retained. The retain is what carries the durability here: a
     * dashboard that connects later still reads the current state immediately.
     * QoS 1 was measured to sit unretransmitted in the client outbox whenever
     * PUBACK was slow on a marginal Wi-Fi link, which on this unit was often,
     * so a QoS 1 heartbeat quietly stopped arriving. QoS 0 goes out on the same
     * path as the telemetry that never drops.
     */
    esp_mqtt_client_enqueue(s_client, topic, payload, 0, 0, 0, true);
}

/*
 * Owns every outgoing message. esp_mqtt_client_publish() can block for the
 * network timeout, so it must not run in the sensing or monitor task; the ring
 * is what decouples them.
 */
static void publish_peer_sample(const mqtt_sample_t *sample, bool has_signal)
{
    char topic[MQTT_NVS_MAX_LEN + 32];
    char payload[160];

    snprintf(topic, sizeof(topic), "%s/peer/%s", s_prefix, sample->name);

    /*
     * Short keys, and no device address.
     *
     * These go out several times a second for the life of the unit, and the
     * full spelling of every field was the bulk of the message: the same
     * reading was 159 bytes, of which more than half was the name of the
     * values and the MAC of a peer that can never change. Shortening the keys
     * and moving the address into the status snapshot cuts this to a little
     * over half its size, which matters on a link that is already struggling.
     *
     * p peer  j jitter  w wander  m motion  r presence ready  s has signal
     * t device uptime in ms
     */
    snprintf(payload, sizeof(payload),
             "{\"p\":\"%s\",\"j\":%.6f,\"w\":%.6f,\"m\":%s,\"r\":%s,"
             "\"s\":%s,\"t\":%" PRIu64 "}",
             sample->name,
             sample->jitter, sample->wander,
             sample->motion ? "true" : "false",
             sample->presence_ready ? "true" : "false",
             has_signal ? "true" : "false",
             (uint64_t)(esp_timer_get_time() / 1000ULL));

    /* store must be true even at QoS 0 or enqueue drops the message. */
    esp_mqtt_client_enqueue(s_client, topic, payload, 0, 0, 0, true);
}

/*
 * Rebuild the broker session once the unit has decided it is no longer getting
 * through. Rate limited, because the symptom can still be present immediately
 * after a rebuild, and an unlimited retry would turn a recovering unit into a
 * permanently reconnecting one.
 */
static void mqtt_recover(const char *why)
{
    uint32_t now = (uint32_t)(esp_timer_get_time() / 1000ULL);
    if ((int64_t)(now - s_recovery_ms) < MQTT_RECOVERY_MIN_MS) {
        return;
    }
    s_recovery_ms = now;
    ESP_LOGW(TAG, "%s, rebuilding connection", why);
    s_outbox_stuck_ms = now;
    s_liveness_sent_ms = now;
    s_liveness_ok_ms = now;
    s_liveness_pending = false;
    s_outbox_last_bytes = 0;
    mqtt_client_create();
}

static void mqtt_task(void *arg)
{
    (void)arg;
    mqtt_peer_slot_t *slots = s_slots;
    mqtt_sample_t sample;
    uint32_t last_status_ms = (uint32_t)(esp_timer_get_time() / 1000ULL);

    while (true) {
        if (xQueueReceive(s_queue, &sample, pdMS_TO_TICKS(500)) == pdTRUE) {
            mqtt_peer_slot_t *slot = NULL;
            for (size_t i = 0; i < MQTT_MAX_PEERS; i++) {
                if (slots[i].seen && strcmp(slots[i].name, sample.name) == 0) {
                    slot = &slots[i];
                    break;
                }
            }
            if (!slot) {
                for (size_t i = 0; i < MQTT_MAX_PEERS; i++) {
                    if (!slots[i].seen) {
                        slot = &slots[i];
                        slot->seen = true;
                        snprintf(slot->name, sizeof(slot->name), "%s", sample.name);
                        memcpy(slot->mac, sample.mac, sizeof(slot->mac));
                        break;
                    }
                }
            }
            /* An untracked peer still has to reach the dashboard, so fall back
             * to the first slot rather than dropping the sample. */
            if (!slot) {
                slot = &slots[0];
                snprintf(slot->name, sizeof(slot->name), "%s", sample.name);
                memcpy(slot->mac, sample.mac, sizeof(slot->mac));
            }
            if (sample.jitter != 0.0f || sample.wander != 0.0f || sample.motion) {
                slot->has_signal = true;
            }
            slot->newest = sample;
            slot->dirty = true;
        }

        /*
         * Telemetry goes out when it changes, not on a timer.
         *
         * A reading identical to the one already on the wire tells a chart
         * nothing, and sending it anyway is what filled the send buffer on a
         * link that could not always keep up. The floor below still applies so
         * that jitter drifting by its last digits does not become a message of
         * its own.
         *
         * Replies are drained first regardless, so a person waiting on a button
         * is never queued behind readings nobody is waiting for.
         */
        /*
         * Acks are QoS 0 and retained, and are queued with len=0 like the
         * telemetry and the status snapshot.
         *
         * Both of those are delivered reliably on this unit while the ack was
         * not, and the only remaining difference was passing an explicit length
         * here. Going through the same "let the client measure it" path as
         * every other publish is what puts acks on the reliable one.
         */
        if (s_client && s_connected) {
            mqtt_ack_t ack;
            while (xQueueReceive(s_ack_queue, &ack, 0) == pdTRUE) {
                char topic[MQTT_NVS_MAX_LEN + 8];
                /*
                 * A reply to one specific request must not be retained. Each
                 * requester gets its own response topic, so retaining would
                 * leave a copy of every command ever answered sitting on the
                 * broker forever. The shared ack topic keeps its retain, which
                 * is what makes a late-joining dashboard able to read the last
                 * answer.
                 */
                bool retain = true;
                if (ack.response_topic[0]) {
                    /*
                     * The sender named a response topic, so this is a
                     * Request/Response reply and it belongs there.
                     */
                    snprintf(topic, sizeof(topic), "%s", ack.response_topic);
                    retain = false;
                    esp_mqtt5_client_set_publish_property(
                        s_client,
                        &(esp_mqtt5_publish_property_config_t){
                            .correlation_data = (const char *)ack.correlation,
                            .correlation_data_len = ack.correlation_len,
                        });

                } else {
                    snprintf(topic, sizeof(topic), "%s/ack", s_prefix);
                }
                /*
                 * QoS 0 and retained, and are queued with len=0 like the
                 * telemetry and the status snapshot.
                 *
                 * Both of those are delivered reliably on this unit while the ack
                 * was not, and the only remaining difference was passing an
                 * explicit length here. Going through the same "let the client
                 * measure it" path as every other publish is what puts acks on
                 * the reliable one.
                 */
                if (esp_mqtt_client_enqueue(s_client, topic, ack.text, 0, 0, retain ? 1 : 0, true) < 0) {
                    ESP_LOGW(TAG, "ack enqueue failed");
                }
            }
        }

        if (s_client && s_connected) {
            uint32_t now_ms = (uint32_t)(esp_timer_get_time() / 1000ULL);
            for (size_t i = 0; i < MQTT_MAX_PEERS; i++) {
                mqtt_peer_slot_t *slot = &slots[i];
                if (!slot->seen || !slot->dirty) {
                    continue;
                }
                /*
                 * A peer with no signal at all is reported at a slow rate only.
                 *
                 * The configured MACs for the non-AP channels are placeholders
                 * and there is no traffic to measure on them, so publishing
                 * three values per second for them spent most of the unit's
                 * uplink on zeroes.
                 */
                uint32_t idle = slot->has_signal
                                    ? (uint32_t)CONFIG_ESP_WIFI_SENSING_MQTT_PUBLISH_MS
                                    : (uint32_t)CONFIG_ESP_WIFI_SENSING_MQTT_PUBLISH_MS * 10;
                uint32_t since = now_ms - slot->last_publish_ms;
                bool floor_ok = since >= MQTT_PUBLISH_MIN_MS;
                bool due = slot->has_signal ? since >= idle : since >= idle;

                if (floor_ok && due) {
                    bool same = slot->has_published &&
                                slot->published.jitter == slot->newest.jitter &&
                                slot->published.wander == slot->newest.wander &&
                                slot->published.motion == slot->newest.motion &&
                                slot->published.presence_ready == slot->newest.presence_ready;
                    /*
                     * Nothing moved, so nothing is sent. A peer with a signal
                     * still gets one reading per idle period regardless, which
                     * is what keeps a quiet room visible on the dashboard rather
                     * than looking identical to a dead unit.
                     */
                    if (!same || since >= idle * 2) {
                        publish_peer_sample(&slot->newest, slot->has_signal);
                        slot->published = slot->newest;
                        slot->has_published = true;
                        slot->last_publish_ms = now_ms;
                    } else {
                        slot->last_publish_ms = now_ms;
                    }
                }
                slot->dirty = false;
            }
        }

        /*
         * Resubscribe on every connect edge. Relying on the broker session to
         * restore the subscription means a broker restart silently leaves the
         * unit accepting no commands, which is the failure that matters here.
         */
        if (s_resubscribe && s_client && s_connected) {
            char topic[MQTT_NVS_MAX_LEN + 8];
            snprintf(topic, sizeof(topic), "%s/cmd", s_prefix);
            s_resubscribe = false;
            esp_mqtt_client_subscribe(s_client, topic, 1);
        }


        /*
         * A command just ran, so push the new state straight away instead of
         * making the dashboard wait out the heartbeat interval.
         */
        if (s_state_pending && s_connected) {
            s_state_pending = false;
            publish_status(true);
            last_status_ms = (uint32_t)(esp_timer_get_time() / 1000ULL);
        }

        uint32_t now_ms = (uint32_t)(esp_timer_get_time() / 1000ULL);
        if (now_ms - last_status_ms >= MQTT_STATUS_PERIOD_MS) {
            last_status_ms = now_ms;
            if (s_connected) {
                publish_status(true);
            }
        }

        /*
         * The broker connection can die without the unit ever being told.
         *
         * When the path is torn down silently there is no error to report, so
         * s_connected stays set, no disconnect event fires, and nothing retries.
         * Measured on this unit: a fresh session delivers for a couple of
         * minutes and then goes completely quiet while the network stays
         * provably healthy, and rebuilding the client puts it back. Two
         * independent checks cover the two shapes that failure takes.
         *
         * The first is volume: at a high publish rate the send buffer piles up
         * and stays several kilobytes above where a draining unit sits.
         *
         * The second is a QoS 1 probe, which the broker has to acknowledge. A
         * buffer that stays small proves nothing, so the probe is what says
         * whether the broker is actually receiving us at all.
         */
        if (s_client && s_connected) {
            int outbox = esp_mqtt_client_get_outbox_size(s_client);
            bool recovering = false;

            if (outbox < MQTT_OUTBOX_DEAD_BYTES) {
                s_outbox_stuck_ms = now_ms;
            }
            if (outbox >= MQTT_OUTBOX_DEAD_BYTES &&
                (now_ms - s_outbox_stuck_ms) >= MQTT_OUTBOX_STUCK_MS) {
                char why[64];
                snprintf(why, sizeof(why), "send buffer stuck at %d B", outbox);
                mqtt_recover(why);
                recovering = true;
            }

            /* A rebuild replaces the client, so nothing after it may touch the
             * old one or judge the new one by the old one's state. */
            if (!recovering) {
                if ((now_ms - s_liveness_sent_ms) >= MQTT_LIVENESS_PERIOD_MS) {
                    s_liveness_sent_ms = now_ms;
                    s_liveness_base_bytes = outbox;
                    char probe[MQTT_NVS_MAX_LEN + 8];
                    snprintf(probe, sizeof(probe), "%s/live", s_prefix);
                    if (esp_mqtt_client_enqueue(s_client, probe, "1", 1, 0, 0, true) == 0) {
                        s_liveness_pending = true;
                    }
                }
                if (s_liveness_pending &&
                    esp_mqtt_client_get_outbox_size(s_client) <= s_liveness_base_bytes) {
                    s_liveness_pending = false;
                    s_liveness_ok_ms = now_ms;
                }
                if (s_liveness_pending &&
                    (now_ms - s_liveness_ok_ms) >= MQTT_LIVENESS_TIMEOUT_MS) {
                    mqtt_recover("no broker acknowledgement");
                }
            }
        }
    }
}

/* ------------------------------------------------------------------ exec --- */

/*
 * A remote command can change the radio environment, so it is treated as an
 * untrusted input: fixed length, no control characters, a whitelist of command
 * verbs, and a rate limit. The whitelist is what stops a stray subscriber from
 * driving the device, and it is deliberately shorter than the full serial
 * grammar.
 */
#define MQTT_CMD_MAX_LEN 128
#define MQTT_CMD_QUEUE_LEN 8

/*
 * One command per 500 ms with a burst of 3. A phone pressing a button five
 * times should still get every tap through, but a looping script must not be
 * able to flood the unit.
 */
#define MQTT_CMD_MIN_INTERVAL_MS 500
#define MQTT_CMD_BURST           3

/*
 * A command carries the MQTT 5 Request/Response properties alongside its text.
 *
 * The response topic comes from whoever published the command, so it is only
 * honoured when it stays inside this unit's own namespace. Without that check a
 * stranger could talk the device into publishing its replies to any topic on the
 * broker.
 */
typedef struct {
    char text[MQTT_CMD_MAX_LEN + 1];
    char response_topic[MQTT_RESP_TOPIC_MAX_LEN];
    uint8_t correlation[MQTT_CORRELATION_MAX_LEN];
    uint8_t correlation_len;
} mqtt_cmd_t;

static QueueHandle_t s_cmd_queue = NULL;


/* Verbs accepted from the network, matched on the token before any argument. */
static const char *const s_cmd_whitelist[] = {
    "SET_STIMULUS",  "GET_STIMULUS",  "AUTO_RECONNECT",
    "GET_CFG",       "SET_CFG",       "SET_CSI_PERIOD",
    "SET_AMPLITUDE_LOG",
    "WIFI_INFO",     "WIFI_CONFIG_HEX", "WIFI_CONFIG", "WIFI_DISCONNECT", "WIFI_RECONNECT",
    "FSM_START",     "FSM_STOP",      "RESET_BASELINE",
    "TRAIN_START",   "TRAIN_STOP",    "MQTT_STATUS",
    "START_STREAM",  "STOP_STREAM",   "HELLO",
};

/*
 * Acks are queued rather than published here.
 *
 * Only mqtt_task is allowed to call the client. The client keeps one outbound
 * message and one pending_msg_id, and make_publish() overwrites both, so a QoS 1
 * ack sent from this task while mqtt_task is publishing QoS 0 telemetry loses
 * its pending state and silently never reaches the broker.
 */
static void send_ack_line(const char *ack, const char *response_topic,
                          const void *correlation, uint8_t correlation_len);

static void send_ack_line(const char *ack, const char *response_topic,
                          const void *correlation, uint8_t correlation_len)
{
    if (!s_ack_queue) {
        return;
    }
    mqtt_ack_t item = {0};
    snprintf(item.text, sizeof(item.text), "%s", ack);
    if (response_topic && *response_topic) {
        snprintf(item.response_topic, sizeof(item.response_topic), "%s", response_topic);
    }
    if (correlation && correlation_len > 0 && correlation_len <= MQTT_CORRELATION_MAX_LEN) {
        memcpy(item.correlation, correlation, correlation_len);
        item.correlation_len = correlation_len;
    }
    /*
     * Where a reply is going is worth having in the log. A command that names a
     * response topic is answered there and nowhere else, so when a reply goes
     * missing this line is what says whether the unit chose the per-request
     * topic or fell back to the shared one.
     */
    ESP_LOGI(TAG, "reply -> %s%s%s",
             item.response_topic[0] ? item.response_topic : s_prefix,
             item.response_topic[0] ? "" : "/ack",
             item.correlation_len ? " (correlated)" : "");
    if (xQueueSend(s_ack_queue, &item, 0) != pdTRUE) {
        ESP_LOGW(TAG, "ack queue full, dropping");
    }
}

static void send_reject(const char *detail, const char *response_topic,
                        const void *correlation, uint8_t correlation_len)
{
    char ack[160];
    snprintf(ack, sizeof(ack),
             "{\"type\":\"ack\",\"cmd\":\"mqtt\",\"ok\":false,\"detail\":\"%s\"}", detail);
    send_ack_line(ack, response_topic, correlation, correlation_len);
}

/*
 * Returns the verb of an "HMSCMD <verb> ..." line, or NULL when the payload is
 * not acceptable at all.
 */
static const char *cmd_validate(const char *text, int len, char *why, size_t why_len)
{
    static const char prefix[] = "HMSCMD ";
    const size_t prefix_len = sizeof(prefix) - 1;

    if (len <= 0) {
        snprintf(why, why_len, "empty");
        return NULL;
    }
    /*
     * The prefix is checked before the length so the rejection names the actual
     * mistake. "REBOOT" is shorter than "HMSCMD " itself, so a length-first
     * check called it an empty payload, which sends the reader looking in the
     * wrong place entirely.
     */
    if (len < (int)prefix_len || strncmp(text, prefix, prefix_len) != 0) {
        snprintf(why, why_len, "missing HMSCMD prefix");
        return NULL;
    }
    if (len > MQTT_CMD_MAX_LEN) {
        snprintf(why, why_len, "too long");
        return NULL;
    }
    /*
     * Control characters would break the ack framing and can also smuggle a
     * second command past a naive line based check.
     */
    for (int i = 0; i < len; i++) {
        unsigned char c = (unsigned char)text[i];
        if (c < 0x20 || c == 0x7f) {
            snprintf(why, why_len, "control character");
            return NULL;
        }
    }
    const char *verb = text + prefix_len;
    const char *end = text + len;
    const char *verb_end = verb;
    while (verb_end < end && *verb_end != ' ') {
        verb_end++;
    }

    for (size_t i = 0; i < sizeof(s_cmd_whitelist) / sizeof(s_cmd_whitelist[0]); i++) {
        size_t n = strlen(s_cmd_whitelist[i]);
        if ((size_t)(verb_end - verb) == n && strncmp(verb, s_cmd_whitelist[i], n) == 0) {
            return verb;
        }
    }
    snprintf(why, why_len, "command not allowed");
    return NULL;
}

static void mqtt_exec_enqueue(const void *data, int len,
                              const char *response_topic, int response_topic_len,
                              const void *correlation, uint8_t correlation_len)
{
    if (!s_cmd_queue || len <= 0 || len > MQTT_CMD_MAX_LEN) {
        return;
    }
    mqtt_cmd_t cmd = {0};
    memcpy(cmd.text, data, (size_t)len);
    cmd.text[len] = '\0';
    if (correlation && correlation_len > 0 &&
        correlation_len <= MQTT_CORRELATION_MAX_LEN) {
        memcpy(cmd.correlation, correlation, correlation_len);
        cmd.correlation_len = correlation_len;
    }
    /*
     * MQTT 5 hands these strings over as a pointer into the raw packet together
     * with a length. They are not NUL terminated, so copying them as C strings
     * runs past the end and picks up the next property, which produced replies
     * addressed to a topic one byte off from the one the sender subscribed to.
     */
    if (response_topic && response_topic_len > 0 &&
        response_topic_len < MQTT_RESP_TOPIC_MAX_LEN) {
        memcpy(cmd.response_topic, response_topic, (size_t)response_topic_len);
        cmd.response_topic[response_topic_len] = '\0';
    }
    if (xQueueSend(s_cmd_queue, &cmd, 0) != pdTRUE) {
        ESP_LOGW(TAG, "cmd queue full, refusing");
        /*
         * Silence here is the worst possible answer.
         *
         * A command that is dropped without a reply looks exactly like a unit
         * that has gone away, and the dashboard retries it for the full window
         * before reporting failure. Saying "busy" turns an invisible drop into
         * an answer the sender can act on, which is the difference between a
         * momentary burst and a control panel that appears broken.
         */
        char line[MQTT_CMD_MAX_LEN + 64];
        snprintf(line, sizeof(line),
                 "{\"type\":\"ack\",\"cmd\":\"mqtt\",\"ok\":false,"
                 "\"detail\":\"busy, command queue full\"}");
        send_ack_line(line, response_topic, correlation, correlation_len);
    }
}

/**
 * @brief Accept a response topic only if it is inside this unit's own namespace.
 *
 * @return The topic when it is acceptable, otherwise NULL.
 */
static const char *response_topic_is_allowed(const char *topic, int topic_len)
{
    char expected[MQTT_RESP_TOPIC_MAX_LEN];
    int prefix_len = snprintf(expected, sizeof(expected), "%s/resp/", s_prefix);

    if (!topic || topic_len <= 0 || topic_len >= MQTT_RESP_TOPIC_MAX_LEN) {
        return NULL;
    }
    if (topic_len <= prefix_len ||
        strncmp(topic, expected, (size_t)prefix_len) != 0) {
        return NULL;
    }
    return topic;
}

static void mqtt_exec_task(void *arg)
{
    (void)arg;
    mqtt_cmd_t cmd;
    char why[48];
    char ack[256];
    uint32_t last_ms = 0;
    int burst = MQTT_CMD_BURST;

    for (;;) {
        if (xQueueReceive(s_cmd_queue, &cmd, portMAX_DELAY) != pdTRUE) {
            continue;
        }

        const char *verb = cmd_validate(cmd.text, (int)strlen(cmd.text), why, sizeof(why));
        if (!verb) {
            ESP_LOGW(TAG, "src=mqtt rejected: %s", why);
            s_state_pending = true;
            send_reject(why, cmd.response_topic, cmd.correlation, cmd.correlation_len);
            continue;
        }

        /*
         * Reconfiguring the access point is the one verb that can strand the
         * unit on a network it cannot reach the broker from, so it stays behind
         * its own build switch.
         */
        if ((strcmp(verb, "WIFI_CONFIG_HEX") == 0 ||
             strcmp(verb, "WIFI_CONFIG") == 0) &&
            !CONFIG_ESP_WIFI_SENSING_MQTT_ALLOW_RECONFIG) {
            ESP_LOGW(TAG, "src=mqtt rejected: %s disabled", verb);
            send_reject("reconfig disabled", cmd.response_topic, cmd.correlation,
                        cmd.correlation_len);
            continue;
        }

        uint32_t now = (uint32_t)(esp_timer_get_time() / 1000ULL);
        if (burst < MQTT_CMD_BURST) {
            burst++;
        } else if (now - last_ms < MQTT_CMD_MIN_INTERVAL_MS) {
            ESP_LOGW(TAG, "src=mqtt rejected: rate limit");
            send_reject("rate limited", cmd.response_topic, cmd.correlation,
                        cmd.correlation_len);
            continue;
        }
        last_ms = now;

        ESP_LOGI(TAG, "src=mqtt exec: %s", cmd.text);
        s_state_pending = true;
        if (web_serial_monitor_handle_remote(cmd.text, ack, sizeof(ack)) == ESP_OK) {
            ESP_LOGI(TAG, "src=mqtt ack: %s", ack);
        } else {
            ESP_LOGW(TAG, "src=mqtt produced no ack");
        }
        /*
         * The reply is queued rather than published straight away. The client
         * is still working through the command it just received when this runs,
         * and a publish issued in that window was measured to never reach the
         * broker, while the same message a moment later does. One tick is
         * enough to let the receive path finish.
         */
        vTaskDelay(pdMS_TO_TICKS(250));
        send_ack_line(ack, cmd.response_topic, cmd.correlation, cmd.correlation_len);
    }
}

/* ------------------------------------------------------------------ api ---- */

esp_err_t mqtt_publisher_init(esp_wifi_sensing_fsm_handle_t fsm,
                              const mqtt_publisher_peer_t *peers, size_t peer_num)
{
    (void)fsm;
    (void)peers;
    (void)peer_num;

    load_settings();
    s_queue = xQueueCreate(MQTT_QUEUE_LEN, sizeof(mqtt_sample_t));
    if (!s_queue) {
        return ESP_ERR_NO_MEM;
    }
    s_cmd_queue = xQueueCreate(MQTT_CMD_QUEUE_LEN, sizeof(mqtt_cmd_t));
    if (!s_cmd_queue) {
        return ESP_ERR_NO_MEM;
    }
    s_ack_queue = xQueueCreate(8, sizeof(mqtt_ack_t));
    if (!s_ack_queue) {
        return ESP_ERR_NO_MEM;
    }
    if (xTaskCreate(mqtt_task, "mqtt_task", 4096, NULL, 5, NULL) != pdPASS) {
        return ESP_ERR_NO_MEM;
    }
    /*
     * Commands run in their own task: the handler can block for as long as it
     * takes to change the AP, and doing that on the mqtt task would stall the
     * keepalive and get the session dropped.
     */
    if (xTaskCreate(mqtt_exec_task, "mqtt_exec", 5120, NULL, 4, NULL) != pdPASS) {
        return ESP_ERR_NO_MEM;
    }
    mqtt_client_create();
    return ESP_OK;
}

bool mqtt_publisher_is_connected(void)
{
    return s_connected;
}

void mqtt_publisher_publish(const char *name, const uint8_t mac[6],
                            const esp_wifi_sensing_fsm_channel_diag_t *diag,
                            esp_wifi_sensing_fsm_state_t motion_state)
{
    if (!name || !mac || !diag || !s_queue) {
        return;
    }
    mqtt_sample_t sample = {0};
    snprintf(sample.name, sizeof(sample.name), "%s", name);
    memcpy(sample.mac, mac, sizeof(sample.mac));
    sample.jitter = diag->jitter_value;
    sample.wander = diag->wander_value;
    sample.motion = motion_state == ESP_WIFI_SENSING_FSM_STATE_ACTIVE;
    sample.presence_ready = diag->presence_ready;

    /*
     * Never block the caller: if the queue is full the oldest sample is stale
     * by definition and the new one is the only one worth keeping.
     */
    if (xQueueSend(s_queue, &sample, 0) != pdTRUE) {
        mqtt_sample_t dropped;
        xQueueReceive(s_queue, &dropped, 0);
        xQueueSend(s_queue, &sample, 0);
    }
}