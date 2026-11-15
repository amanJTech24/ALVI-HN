// usb_sync.cpp — USB Serial sync manager
// Dispatches incoming commands and manages retry queue via storage.h
#include "usb_sync.h"
#include "protocol.h"
#include "storage.h"
#include "reminders.h"
#include "display_ui.h"
#include <Preferences.h>
#include <ArduinoJson.h>
#include <Arduino.h>

#define MAX_USB_RETRIES      3
#define CONNECTED_TIMEOUT_MS 30000UL
#define RETRY_INTERVAL_MS     5000UL  // attempt one retry every 5 s

static uint32_t _last_ack_ms    = 0;
static bool     _ever_connected = false;
static uint32_t _last_retry_ms  = 0;

// Paired device ID stored in NVS
static Preferences _pair_prefs;
static char        _paired_device_id[32] = "";

static void _load_paired_device() {
    _pair_prefs.begin("usb_sync", true);
    _pair_prefs.getString("paired_did", _paired_device_id, sizeof(_paired_device_id));
    _pair_prefs.end();
}

static void _save_paired_device(const char* did) {
    strlcpy(_paired_device_id, did, sizeof(_paired_device_id));
    _pair_prefs.begin("usb_sync", false);
    _pair_prefs.putString("paired_did", did);
    _pair_prefs.end();
}

// ─── Init ───────────────────────────────────────────────────────────────────
void usb_sync_init() {
    _load_paired_device();
    _last_retry_ms = millis();
}

// ─── Queue helper ────────────────────────────────────────────────────────────
void usb_sync_queue_event(const char* msg_type, const char* session_id,
                          const char* activity_id, const char* payload_json) {
    StoredEvent ev;
    memset(&ev, 0, sizeof(ev));
    storage_gen_uuid(ev.event_id, sizeof(ev.event_id));
    strlcpy(ev.activity_id, activity_id,  sizeof(ev.activity_id));
    strlcpy(ev.session_id,  session_id,   sizeof(ev.session_id));
    strlcpy(ev.payload,     payload_json, sizeof(ev.payload));
    ev.sync_state   = 0;
    ev.timestamp_ms = millis();
    ev.retry_count  = 0;
    storage_push(ev);
}

// ─── Connected check ─────────────────────────────────────────────────────────
bool usb_sync_connected() {
    if (!_ever_connected) return false;
    return (millis() - _last_ack_ms) < CONNECTED_TIMEOUT_MS;
}

// ─── Incoming command dispatch ───────────────────────────────────────────────
static void _dispatch(JsonDocument& doc) {
    const char* cmd = doc["msg_type"] | "";

    if (strcmp(cmd, CMD_SYNC_ACK) == 0) {
        // Mark specific event synced
        const char* eid = doc["event_id"] | "";
        if (eid[0]) storage_mark_synced(eid);
        _last_ack_ms    = millis();
        _ever_connected = true;

    } else if (strcmp(cmd, CMD_TIME_SYNC) == 0) {
        uint32_t epoch = doc["payload"]["epoch_seconds"] | 0UL;
        if (epoch > 0) {
            reminders_set_clock(epoch);
        }
        _last_ack_ms    = millis();
        _ever_connected = true;

    } else if (strcmp(cmd, CMD_PAIR_REQUEST) == 0) {
        const char* did = doc["device_id"] | "";
        if (did[0]) {
            _save_paired_device(did);
            // Acknowledge pairing on display briefly
            display_ui_clear(COLOR_BLACK);
            display_ui_draw_text_centered("Paired!", 70, COLOR_GREEN, FONT_LARGE);
            delay(1500);
            display_ui_clear(COLOR_BLACK);
        }

    } else if (strcmp(cmd, CMD_VOICE_RESULT) == 0) {
        // Show transcription result on screen
        const char* text = doc["payload"]["transcript"] | "(no text)";
        display_ui_clear(COLOR_BLACK);
        display_ui_draw_text_centered("Voice:", 20, COLOR_CYAN, FONT_MEDIUM);
        display_ui_draw_text_wrapped(text, 4, 50, COLOR_WHITE, FONT_SMALL, 150);
    }
}

// ─── Update (call in loop()) ─────────────────────────────────────────────────
void usb_sync_update() {
    // 1. Read incoming commands
    StaticJsonDocument<512> in_doc;
    while (protocol_read_command(in_doc)) {
        _dispatch(in_doc);
        in_doc.clear();
    }

    // 2. Retry pending events at interval when connected
    if (!usb_sync_connected()) return;

    uint32_t now_ms = millis();
    if (now_ms - _last_retry_ms < RETRY_INTERVAL_MS) return;
    _last_retry_ms = now_ms;

    StoredEvent ev;
    if (storage_pop_pending(ev)) {
        if (ev.retry_count >= MAX_USB_RETRIES) {
            storage_mark_failed(ev.event_id);
            return;
        }

        // Re-send based on activity type stored in payload JSON
        // The payload is already a serialised JSON string; wrap it in protocol frame.
        // We reconstruct a minimal JSON envelope and send it raw.
        StaticJsonDocument<768> out_doc;
        out_doc["msg_type"]         = ev.activity_id; // activity_id used as msg_type
        out_doc["protocol_version"] = PROTO_VERSION;
        out_doc["event_id"]         = ev.event_id;
        out_doc["session_id"]       = ev.session_id;
        out_doc["timestamp_ms"]     = ev.timestamp_ms;
        out_doc["retry"]            = ev.retry_count + 1;

        // Embed payload (already JSON string)
        StaticJsonDocument<512> pl_doc;
        if (deserializeJson(pl_doc, ev.payload) == DeserializationError::Ok) {
            out_doc["payload"] = pl_doc.as<JsonObject>();
        } else {
            out_doc["payload"] = ev.payload; // fallback: raw string
        }

        protocol_send_raw(out_doc);

        // Bump retry count in storage
        storage_mark_failed(ev.event_id); // increments retry; if still < 3 stays pending
    }
}
