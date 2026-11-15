#pragma once
// protocol.h — USB Serial JSON Protocol (115200 baud)
// Newline-terminated JSON messages
#include <Arduino.h>
#include <ArduinoJson.h>

#define PROTO_VERSION "1.0"

// Outgoing message types
#define MSG_HELLO           "HELLO"
#define MSG_DEVICE_STATUS   "DEVICE_STATUS"
#define MSG_MOOD_SELECTED   "MOOD_SELECTED"
#define MSG_MEMORY_RESULT   "MEMORY_RESULT"
#define MSG_REACTION_RESULT "REACTION_RESULT"
#define MSG_NEUROPEN_START  "NEUROPEN_START"
#define MSG_NEUROPEN_FINISH "NEUROPEN_FINISH"
#define MSG_REMINDER_EVENT  "REMINDER_EVENT"
#define MSG_TIME_SYNC_REQ   "TIME_SYNC_REQ"
#define MSG_VOICE_STATUS    "VOICE_STATUS"
#define MSG_ERROR           "ERROR"

// Incoming message types
#define CMD_TIME_SYNC    "TIME_SYNC"
#define CMD_SYNC_ACK     "SYNC_ACK"
#define CMD_PAIR_REQUEST "PAIR_REQUEST"
#define CMD_VOICE_RESULT "VOICE_RESULT"

void     protocol_init(uint32_t baud);
void     protocol_send_hello(const char* device_id, const char* device_name);
void     protocol_send_mood(const char* session_id, const char* event_id,
                            uint8_t mood_code, const char* mood_name);
void     protocol_send_memory_result(const char* session_id, const char* event_id,
                                     uint8_t max_level, uint8_t correct,
                                     uint8_t errors, uint32_t dur_ms);
void     protocol_send_reaction_result(const char* session_id, const char* event_id,
                                       uint16_t median_rt, uint8_t false_starts,
                                       uint8_t missed, uint8_t trial_count);
void     protocol_send_neuropen_start(const char* session_id, const char* event_id,
                                  const char* task_name, const char* target_time);
void     protocol_send_neuropen_finish(const char* session_id, const char* event_id,
                                   uint32_t duration_ms, const char* task_name,
                                   const char* status);
void     protocol_send_status(uint8_t battery_pct, bool wifi_ok, uint8_t pending_events);
void     protocol_send_error(const char* code, const char* message);
bool     protocol_read_command(JsonDocument& doc); // returns true if complete message received
void     protocol_send_raw(const JsonDocument& doc);
