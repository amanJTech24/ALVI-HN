// protocol.cpp — USB Serial JSON Protocol
#include "protocol.h"
#include <Arduino.h>

// Static sequence number (declared here; extern in protocol.h would conflict)
static uint32_t _seq_num = 0;

// Device ID shared across send functions — set by protocol_send_hello
static char _device_id[32] = "ALVI_DEVICE";

// ─── Init ───────────────────────────────────────────────────────────────────
void protocol_init(uint32_t baud) {
    Serial.begin(baud);
    // Brief settle
    delay(50);
}

// ─── Internal: build base fields ────────────────────────────────────────────
static void _base(JsonDocument& doc, const char* msg_type,
                  const char* session_id = nullptr,
                  const char* event_id   = nullptr) {
    doc["msg_type"]         = msg_type;
    doc["protocol_version"] = PROTO_VERSION;
    doc["device_id"]        = _device_id;
    doc["seq_num"]          = _seq_num++;
    if (session_id && session_id[0]) doc["session_id"] = session_id;
    if (event_id   && event_id[0])   doc["event_id"]   = event_id;
}

// ─── Send raw ───────────────────────────────────────────────────────────────
void protocol_send_raw(const JsonDocument& doc) {
    serializeJson(doc, Serial);
    Serial.println();
}

// ─── Outgoing messages ───────────────────────────────────────────────────────
void protocol_send_hello(const char* device_id, const char* device_name) {
    strlcpy(_device_id, device_id, sizeof(_device_id));

    StaticJsonDocument<256> doc;
    _base(doc, MSG_HELLO);
    doc["device_name"]  = device_name;
    doc["firmware_ver"] = PROTO_VERSION;
    protocol_send_raw(doc);
}

void protocol_send_mood(const char* session_id, const char* event_id,
                        uint8_t mood_code, const char* mood_name) {
    StaticJsonDocument<256> doc;
    _base(doc, MSG_MOOD_SELECTED, session_id, event_id);
    doc["activity_id"] = "hw_mood";
    JsonObject pl  = doc.createNestedObject("payload");
    pl["activity_id"] = "hw_mood";
    pl["mood_code"] = mood_code;
    pl["mood_name"] = mood_name;
    protocol_send_raw(doc);
}

void protocol_send_memory_result(const char* session_id, const char* event_id,
                                 uint8_t max_level, uint8_t correct,
                                 uint8_t errors, uint32_t dur_ms) {
    StaticJsonDocument<256> doc;
    _base(doc, MSG_MEMORY_RESULT, session_id, event_id);
    doc["activity_id"] = "hw_memory_seq";
    JsonObject pl    = doc.createNestedObject("payload");
    pl["activity_id"] = "hw_memory_seq";
    pl["max_level"]  = max_level;
    pl["correct"]    = correct;
    pl["errors"]     = errors;
    pl["duration_ms"]= dur_ms;
    protocol_send_raw(doc);
}

void protocol_send_reaction_result(const char* session_id, const char* event_id,
                                   uint16_t median_rt, uint8_t false_starts,
                                   uint8_t missed, uint8_t trial_count) {
    StaticJsonDocument<256> doc;
    _base(doc, MSG_REACTION_RESULT, session_id, event_id);
    doc["activity_id"] = "hw_reaction_test";
    JsonObject pl        = doc.createNestedObject("payload");
    pl["activity_id"]   = "hw_reaction_test";
    pl["median_rt_ms"]   = median_rt;
    pl["false_starts"]   = false_starts;
    pl["missed"]         = missed;
    pl["trial_count"]    = trial_count;
    protocol_send_raw(doc);
}

void protocol_send_neuropen_start(const char* session_id, const char* event_id,
                                  const char* task_name, const char* target_time) {
    StaticJsonDocument<256> doc;
    _base(doc, MSG_NEUROPEN_START, session_id, event_id);
    doc["activity_id"] = "hw_neuropen";
    JsonObject pl = doc.createNestedObject("payload");
    pl["activity_id"] = "hw_neuropen";
    pl["task"] = task_name ? task_name : "clock_drawing";
    pl["target_time"] = target_time ? target_time : "11:10";
    pl["status"] = "started";
    protocol_send_raw(doc);
}

void protocol_send_neuropen_finish(const char* session_id, const char* event_id,
                                   uint32_t duration_ms, const char* task_name,
                                   const char* status) {
    StaticJsonDocument<256> doc;
    _base(doc, MSG_NEUROPEN_FINISH, session_id, event_id);
    doc["activity_id"] = "hw_neuropen";
    JsonObject pl = doc.createNestedObject("payload");
    pl["activity_id"] = "hw_neuropen";
    pl["task"] = task_name ? task_name : "clock_drawing";
    pl["target_time"] = "11:10";
    pl["duration_ms"] = duration_ms;
    pl["duration_sec"] = (uint32_t)(duration_ms / 1000);
    pl["status"] = status ? status : "completed";
    protocol_send_raw(doc);
}

void protocol_send_status(uint8_t battery_pct, bool wifi_ok, uint8_t pending_events) {
    StaticJsonDocument<192> doc;
    _base(doc, MSG_DEVICE_STATUS);
    JsonObject pl         = doc.createNestedObject("payload");
    pl["battery_pct"]     = battery_pct;
    pl["wifi_ok"]         = wifi_ok;
    pl["pending_events"]  = pending_events;
    pl["uptime_ms"]       = millis();
    protocol_send_raw(doc);
}

void protocol_send_error(const char* code, const char* message) {
    StaticJsonDocument<192> doc;
    _base(doc, MSG_ERROR);
    JsonObject pl  = doc.createNestedObject("payload");
    pl["code"]     = code;
    pl["message"]  = message;
    protocol_send_raw(doc);
}

// ─── Incoming command reader ─────────────────────────────────────────────────
// Accumulates bytes until '\n', then parses JSON.
bool protocol_read_command(JsonDocument& doc) {
    static char _rx_buf[512];
    static uint16_t _rx_len = 0;

    while (Serial.available()) {
        char c = (char)Serial.read();
        if (c == '\n' || c == '\r') {
            if (_rx_len == 0) continue; // skip blank lines
            _rx_buf[_rx_len] = '\0';
            _rx_len = 0;

            DeserializationError err = deserializeJson(doc, _rx_buf);
            if (err == DeserializationError::Ok) return true;
            // malformed — discard and continue
        } else {
            if (_rx_len < sizeof(_rx_buf) - 1) {
                _rx_buf[_rx_len++] = c;
            } else {
                // Buffer overflow — reset
                _rx_len = 0;
            }
        }
    }
    return false;
}
