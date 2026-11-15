#pragma once
// wifi_sync.h — WiFi HTTP sync to backend
#include <Arduino.h>

void wifi_sync_init();       // read creds from Preferences, connect if set
void wifi_sync_update();     // process send queue non-blocking
bool wifi_sync_connected();
void wifi_sync_queue_event(const char* endpoint, const char* json_body);
void wifi_sync_set_credentials(const char* ssid, const char* password,
                               const char* backend_url);
