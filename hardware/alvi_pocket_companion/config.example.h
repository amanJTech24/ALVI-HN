#pragma once
// ============================================================
// ALVI Pocket Companion — Configuration Template
// COPY this file to config.h and fill in your values.
// NEVER commit config.h to version control.
// ============================================================

// WiFi credentials (optional — leave empty for USB-only mode)
#define WIFI_SSID     ""
#define WIFI_PASSWORD ""

// Backend address — use your LAN IP (not 127.0.0.1) when using WiFi
// Example: "http://192.168.1.100:8765"
#define BACKEND_URL   "http://192.168.1.100:8765"

// Device identity
#define DEVICE_ID     "alvi-hw-001"
#define DEVICE_NAME   "ALVI Pocket Companion"

// Serial configuration
#define SERIAL_BAUD   115200

// TFT display variant — uncomment the correct one for your module
// Most common black-tab 1.8" modules use INITR_BLACKTAB
#define TFT_INIT_TYPE  INITR_BLACKTAB
// #define TFT_INIT_TYPE  INITR_GREENTAB
// #define TFT_INIT_TYPE  INITR_144GREENTAB

// Reminder defaults
#define DEFAULT_REMINDER_INTERVAL_MIN  60   // minutes
#define DEFAULT_REMINDER_ENABLED       true

