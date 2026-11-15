#pragma once
// usb_sync.h — USB Serial sync manager
#include <Arduino.h>
#include <ArduinoJson.h>

void usb_sync_init();
void usb_sync_update();     // process incoming commands, retry pending events
bool usb_sync_connected();  // true if SYNC_ACK received recently (within 30s)
void usb_sync_queue_event(const char* msg_type, const char* session_id,
                          const char* activity_id, const char* payload_json);
