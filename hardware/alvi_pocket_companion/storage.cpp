// storage.cpp — Offline NVS event queue
#include "storage.h"
#include <Preferences.h>
#include <ArduinoJson.h>
#include <esp_random.h>
#include <Arduino.h>

// ─── NVS layout ─────────────────────────────────────────────────────────────
// Namespace: "storage"
// Key "count"   : uint8_t  — number of used slots (0..STORAGE_MAX_EVENTS)
// Key "evt_N"   : String   — compact JSON of StoredEvent for slot N
static const char* NVS_NS = "storage";

static Preferences _prefs;

// ─── UUID v4 generator ───────────────────────────────────────────────────────
void storage_gen_uuid(char* out, size_t len) {
    // RFC-4122 UUID v4: xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx
    if (len < 37) return;
    uint32_t r[4];
    r[0] = esp_random();
    r[1] = esp_random();
    r[2] = esp_random();
    r[3] = esp_random();

    // Set version 4 and variant bits
    uint8_t* b = (uint8_t*)r;
    b[6] = (b[6] & 0x0F) | 0x40;   // version 4
    b[8] = (b[8] & 0x3F) | 0x80;   // variant 10xx

    snprintf(out, len,
        "%02x%02x%02x%02x-%02x%02x-%02x%02x-%02x%02x-%02x%02x%02x%02x%02x%02x",
        b[0],  b[1],  b[2],  b[3],
        b[4],  b[5],  b[6],  b[7],
        b[8],  b[9],  b[10], b[11],
        b[12], b[13], b[14], b[15]);
}

// ─── Slot helpers ────────────────────────────────────────────────────────────
static String _slot_key(uint8_t n) {
    char k[12];
    snprintf(k, sizeof(k), "evt_%d", n);
    return String(k);
}

static bool _load_slot(uint8_t n, StoredEvent& ev) {
    _prefs.begin(NVS_NS, true);
    String raw = _prefs.getString(_slot_key(n).c_str(), "");
    _prefs.end();
    if (raw.isEmpty()) return false;

    StaticJsonDocument<768> doc;
    if (deserializeJson(doc, raw) != DeserializationError::Ok) return false;

    strlcpy(ev.event_id,    doc["eid"]  | "", sizeof(ev.event_id));
    strlcpy(ev.device_id,   doc["did"]  | "", sizeof(ev.device_id));
    strlcpy(ev.activity_id, doc["aid"]  | "", sizeof(ev.activity_id));
    strlcpy(ev.session_id,  doc["sid"]  | "", sizeof(ev.session_id));
    strlcpy(ev.payload,     doc["pl"]   | "", sizeof(ev.payload));
    ev.sync_state    = doc["ss"]  | 0;
    ev.timestamp_ms  = doc["ts"]  | 0UL;
    ev.retry_count   = doc["rc"]  | 0;
    return true;
}

static bool _save_slot(uint8_t n, const StoredEvent& ev) {
    StaticJsonDocument<768> doc;
    doc["eid"] = ev.event_id;
    doc["did"] = ev.device_id;
    doc["aid"] = ev.activity_id;
    doc["sid"] = ev.session_id;
    doc["pl"]  = ev.payload;
    doc["ss"]  = ev.sync_state;
    doc["ts"]  = ev.timestamp_ms;
    doc["rc"]  = ev.retry_count;

    char buf[768];
    size_t n2 = serializeJson(doc, buf, sizeof(buf));
    if (n2 == 0) return false;

    _prefs.begin(NVS_NS, false);
    bool ok = _prefs.putString(_slot_key(n).c_str(), buf);
    _prefs.end();
    return ok;
}

static void _clear_slot(uint8_t n) {
    _prefs.begin(NVS_NS, false);
    _prefs.remove(_slot_key(n).c_str());
    _prefs.end();
}

// ─── Public API ─────────────────────────────────────────────────────────────
void storage_init() {
    // No explicit initialisation needed; NVS is opened per-operation.
    // Clear slots that are corrupted on first boot.
    // (Intentionally lightweight.)
}

bool storage_push(const StoredEvent& ev) {
    // Find a free slot (empty or synced)
    for (uint8_t i = 0; i < STORAGE_MAX_EVENTS; i++) {
        StoredEvent tmp;
        bool exists = _load_slot(i, tmp);
        if (!exists || tmp.sync_state == 1) { // empty or already synced
            return _save_slot(i, ev);
        }
    }
    return false; // queue full
}

bool storage_pop_pending(StoredEvent& out) {
    for (uint8_t i = 0; i < STORAGE_MAX_EVENTS; i++) {
        if (_load_slot(i, out) && out.sync_state == 0) {
            return true;
        }
    }
    return false;
}

void storage_mark_synced(const char* event_id) {
    for (uint8_t i = 0; i < STORAGE_MAX_EVENTS; i++) {
        StoredEvent ev;
        if (_load_slot(i, ev) && strcmp(ev.event_id, event_id) == 0) {
            ev.sync_state = 1;
            _save_slot(i, ev);
            return;
        }
    }
}

void storage_mark_failed(const char* event_id) {
    for (uint8_t i = 0; i < STORAGE_MAX_EVENTS; i++) {
        StoredEvent ev;
        if (_load_slot(i, ev) && strcmp(ev.event_id, event_id) == 0) {
            ev.retry_count++;
            if (ev.retry_count >= 3) {
                ev.sync_state = 2; // permanently failed
            }
            _save_slot(i, ev);
            return;
        }
    }
}

uint8_t storage_pending_count() {
    uint8_t cnt = 0;
    for (uint8_t i = 0; i < STORAGE_MAX_EVENTS; i++) {
        StoredEvent ev;
        if (_load_slot(i, ev) && ev.sync_state == 0) cnt++;
    }
    return cnt;
}

void storage_clear_synced() {
    for (uint8_t i = 0; i < STORAGE_MAX_EVENTS; i++) {
        StoredEvent ev;
        if (_load_slot(i, ev) && ev.sync_state == 1) {
            _clear_slot(i);
        }
    }
}
