// wifi_sync.cpp — WiFi HTTP sync to backend
// Credentials are NEVER hard-coded; always read from NVS Preferences.
#include "wifi_sync.h"
#include <WiFi.h>
#include <HTTPClient.h>
#include <Preferences.h>
#include <ArduinoJson.h>
#include <Arduino.h>

// ─── NVS namespace ──────────────────────────────────────────────────────────
static const char* NVS_NS       = "wifi_sync";
static const char* KEY_SSID     = "ssid";
static const char* KEY_PASS     = "password";
static const char* KEY_BACKEND  = "backend_url";

// ─── Send queue (up to 20 events, offline buffer) ───────────────────────────
#define WIFI_QUEUE_MAX 20
#define HTTP_TIMEOUT_MS 5000

struct _WifiQueueEntry {
    char endpoint[128];
    char body[512];
    bool used;
};

static _WifiQueueEntry _queue[WIFI_QUEUE_MAX];
static uint8_t         _queue_count = 0;

// ─── Credentials ─────────────────────────────────────────────────────────────
static char _ssid[64]        = "";
static char _password[64]    = "";
static char _backend_url[128]= "";

static Preferences _prefs;

static void _load_credentials() {
    _prefs.begin(NVS_NS, true);
    _prefs.getString(KEY_SSID,    _ssid,        sizeof(_ssid));
    _prefs.getString(KEY_PASS,    _password,    sizeof(_password));
    _prefs.getString(KEY_BACKEND, _backend_url, sizeof(_backend_url));
    _prefs.end();
}

static void _save_credentials() {
    _prefs.begin(NVS_NS, false);
    _prefs.putString(KEY_SSID,    _ssid);
    _prefs.putString(KEY_PASS,    _password);
    _prefs.putString(KEY_BACKEND, _backend_url);
    _prefs.end();
}

// ─── Queue helpers ───────────────────────────────────────────────────────────
static bool _enqueue(const char* endpoint, const char* body) {
    if (_queue_count >= WIFI_QUEUE_MAX) return false;
    for (int i = 0; i < WIFI_QUEUE_MAX; i++) {
        if (!_queue[i].used) {
            strlcpy(_queue[i].endpoint, endpoint, sizeof(_queue[i].endpoint));
            strlcpy(_queue[i].body,     body,     sizeof(_queue[i].body));
            _queue[i].used = true;
            _queue_count++;
            return true;
        }
    }
    return false;
}

static void _dequeue(int idx) {
    _queue[idx].used = false;
    _queue_count     = (_queue_count > 0) ? _queue_count - 1 : 0;
}

// ─── HTTP POST ───────────────────────────────────────────────────────────────
static bool _http_post(const char* url, const char* json_body) {
    HTTPClient http;
    http.begin(url);
    http.addHeader("Content-Type", "application/json");
    http.setTimeout(HTTP_TIMEOUT_MS);

    int code = http.POST((uint8_t*)json_body, strlen(json_body));
    http.end();

    return (code >= 200 && code < 300);
}

// ─── Drain offline queue ─────────────────────────────────────────────────────
static void _drain_queue() {
    if (!wifi_sync_connected()) return;
    if (_backend_url[0] == '\0') return;

    for (int i = 0; i < WIFI_QUEUE_MAX; i++) {
        if (!_queue[i].used) continue;

        // Build full URL
        char url[256];
        snprintf(url, sizeof(url), "%s%s", _backend_url, _queue[i].endpoint);

        if (_http_post(url, _queue[i].body)) {
            _dequeue(i);
        }
        // If failed, leave in queue for next update cycle
        // Add a small inter-request delay to avoid hammering
        delay(50);
    }
}

// ─── Public API ─────────────────────────────────────────────────────────────
void wifi_sync_init() {
    memset(_queue, 0, sizeof(_queue));
    _queue_count = 0;

    _load_credentials();

    if (_ssid[0] == '\0') return; // no credentials — stay offline

    WiFi.mode(WIFI_STA);
    WiFi.begin(_ssid, _password);

    // Non-blocking: connection completes in wifi_sync_update()
}

void wifi_sync_update() {
    // Reconnect if needed
    if (_ssid[0] != '\0' && WiFi.status() != WL_CONNECTED) {
        static uint32_t _last_reconnect = 0;
        if (millis() - _last_reconnect > 15000UL) {
            _last_reconnect = millis();
            WiFi.disconnect(true);
            delay(100);
            WiFi.begin(_ssid, _password);
        }
    }

    // Drain offline queue when online
    if (wifi_sync_connected()) {
        _drain_queue();
    }
}

bool wifi_sync_connected() {
    return (WiFi.status() == WL_CONNECTED);
}

void wifi_sync_queue_event(const char* endpoint, const char* json_body) {
    if (wifi_sync_connected() && _backend_url[0] != '\0') {
        // Online: try to send immediately
        char url[256];
        snprintf(url, sizeof(url), "%s%s", _backend_url, endpoint);
        if (_http_post(url, json_body)) return; // sent — done
    }
    // Offline or failed: buffer it
    _enqueue(endpoint, json_body);
}

void wifi_sync_set_credentials(const char* ssid, const char* password,
                               const char* backend_url) {
    strlcpy(_ssid,        ssid,        sizeof(_ssid));
    strlcpy(_password,    password,    sizeof(_password));
    strlcpy(_backend_url, backend_url, sizeof(_backend_url));
    _save_credentials();

    // Reconnect with new credentials
    WiFi.disconnect(true);
    delay(200);
    WiFi.begin(_ssid, _password);
}
