#pragma once
// reminders.h — Daily Reminders with Preferences persistence
#include <Arduino.h>

struct ReminderSettings {
    bool     enabled;
    uint8_t  interval_min;   // 0=use wall clock
    uint8_t  hour;           // wall-clock hour (0-23), only valid if synced
    uint8_t  minute;         // wall-clock minute
    bool     clock_synced;   // true if TIME_SYNC received from backend
};

void reminders_init();
void reminders_load();
void reminders_save();
void reminders_set_clock(uint32_t epoch_seconds);
void reminders_update();     // non-blocking, call in loop
bool reminders_is_due();
void reminders_dismiss();
void reminders_snooze(uint8_t minutes);
void reminders_show_settings_menu();
const ReminderSettings& reminders_get_settings();
void reminders_set_enabled(bool en);
void reminders_set_interval(uint8_t minutes);
