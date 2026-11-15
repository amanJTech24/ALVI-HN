#pragma once
// storage.h — Offline event queue using Preferences (NVS)
// Max 50 events per queue, never store per-frame events
#include <Arduino.h>

#define STORAGE_MAX_EVENTS  50
#define STORAGE_MAX_PAYLOAD 384

struct StoredEvent {
    char    event_id[37];       // UUID v4
    char    device_id[32];
    char    activity_id[32];
    char    session_id[32];
    char    payload[STORAGE_MAX_PAYLOAD];
    uint8_t sync_state;         // 0=pending, 1=synced, 2=failed
    uint32_t timestamp_ms;
    uint8_t retry_count;
};

void     storage_init();
bool     storage_push(const StoredEvent& ev);     // returns false if queue full
bool     storage_pop_pending(StoredEvent& out);   // oldest pending event
void     storage_mark_synced(const char* event_id);
void     storage_mark_failed(const char* event_id);
uint8_t  storage_pending_count();
void     storage_gen_uuid(char* out, size_t len); // fills out with UUID v4
void     storage_clear_synced();
