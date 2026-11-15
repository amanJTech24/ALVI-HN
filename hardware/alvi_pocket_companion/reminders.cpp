// reminders.cpp — Daily Reminders with NVS persistence
#include "reminders.h"
#include "display_ui.h"
#include "buttons.h"
#include "pins.h"
#include <Preferences.h>
#include <Arduino.h>

// ─── NVS namespace ──────────────────────────────────────────────────────────
static const char* NVS_NS       = "reminders";
static const char* KEY_ENABLED  = "enabled";
static const char* KEY_INTERVAL = "interval";
static const char* KEY_HOUR     = "hour";
static const char* KEY_MINUTE   = "minute";

// ─── State ──────────────────────────────────────────────────────────────────
static ReminderSettings _settings;
static Preferences      _prefs;

// Clock state
static uint32_t _epoch_base_s   = 0;    // epoch at last sync
static uint32_t _epoch_base_ms  = 0;    // millis() at last sync
static bool     _due            = false;

// Countdown / wall-clock scheduling
static uint32_t _last_trigger_ms   = 0; // millis() of last trigger (interval mode)
static uint32_t _snooze_until_ms   = 0; // millis() snooze deadline
static bool     _snooze_active     = false;

// ─── Internal helpers ────────────────────────────────────────────────────────
static uint32_t _now_epoch_s() {
    if (!_settings.clock_synced) return 0;
    return _epoch_base_s + (millis() - _epoch_base_ms) / 1000;
}

static void _beep_notification() {
    // 3 short beeps on GPIO33 (active-low or active-high buzzer)
    for (int i = 0; i < 3; i++) {
        digitalWrite(PIN_BUZZER, HIGH);
        delay(100);
        digitalWrite(PIN_BUZZER, LOW);
        delay(100);
    }
}

static void _show_reminder_screen() {
    display_ui_clear(COLOR_TEAL);
    display_ui_draw_text_centered("⏰", 30, COLOR_WHITE, FONT_XLARGE);
    display_ui_draw_text_centered("Time for a break!", 70, COLOR_WHITE, FONT_LARGE);
    display_ui_draw_text_centered("SELECT=snooze  BACK=dismiss", 120, COLOR_WHITE, FONT_SMALL);
}

// ─── Public API ─────────────────────────────────────────────────────────────
void reminders_init() {
    pinMode(PIN_BUZZER, OUTPUT);
    digitalWrite(PIN_BUZZER, LOW);
    reminders_load();
    _last_trigger_ms = millis();
}

void reminders_load() {
    _prefs.begin(NVS_NS, true); // read-only
    _settings.enabled      = _prefs.getBool(KEY_ENABLED,  true);
    _settings.interval_min = _prefs.getUChar(KEY_INTERVAL, 60);
    _settings.hour         = _prefs.getUChar(KEY_HOUR,     9);
    _settings.minute       = _prefs.getUChar(KEY_MINUTE,   0);
    _prefs.end();
    _settings.clock_synced = false; // must be re-synced after power-cycle
}

void reminders_save() {
    _prefs.begin(NVS_NS, false); // read-write
    _prefs.putBool(KEY_ENABLED,   _settings.enabled);
    _prefs.putUChar(KEY_INTERVAL, _settings.interval_min);
    _prefs.putUChar(KEY_HOUR,     _settings.hour);
    _prefs.putUChar(KEY_MINUTE,   _settings.minute);
    _prefs.end();
}

void reminders_set_clock(uint32_t epoch_seconds) {
    _epoch_base_s          = epoch_seconds;
    _epoch_base_ms         = millis();
    _settings.clock_synced = true;
}

void reminders_update() {
    if (!_settings.enabled) return;
    if (_due) {
        // Waiting for user dismissal — handle buttons
        if (button_just_pressed(BTN_ID_BACK)) {
            reminders_dismiss();
        } else if (button_just_pressed(BTN_ID_SELECT)) {
            reminders_snooze(10);
        }
        return;
    }

    uint32_t now_ms = millis();

    // Snooze check
    if (_snooze_active) {
        if (now_ms < _snooze_until_ms) return; // still snoozing
        _snooze_active = false;
    }

    // ── Interval mode (millis-based countdown) ────────────────────────────
    if (_settings.interval_min > 0) {
        uint32_t interval_ms = (uint32_t)_settings.interval_min * 60000UL;
        if (now_ms - _last_trigger_ms >= interval_ms) {
            _due = true;
            _last_trigger_ms = now_ms;
            _beep_notification();
            _show_reminder_screen();
        }
        return;
    }

    // ── Wall-clock mode ───────────────────────────────────────────────────
    if (!_settings.clock_synced) {
        // Can't do wall-clock without sync; show warning once at boot if needed
        return;
    }

    uint32_t epoch = _now_epoch_s();
    // Seconds-within-day
    uint32_t day_sec = epoch % 86400UL;
    uint32_t target  = (uint32_t)_settings.hour * 3600UL + _settings.minute * 60UL;
    // Trigger within a 30-second window to avoid missing it
    if (day_sec >= target && day_sec < target + 30) {
        // Avoid re-triggering within same minute
        static uint32_t _last_wall_trigger_day = 0xFFFFFFFF;
        uint32_t today = epoch / 86400UL;
        if (today != _last_wall_trigger_day) {
            _last_wall_trigger_day = today;
            _due = true;
            _beep_notification();
            _show_reminder_screen();
        }
    }
}

bool reminders_is_due() {
    return _due;
}

void reminders_dismiss() {
    _due           = false;
    _snooze_active = false;
    display_ui_clear(COLOR_BLACK); // return to idle
}

void reminders_snooze(uint8_t minutes) {
    _due             = false;
    _snooze_active   = true;
    _snooze_until_ms = millis() + (uint32_t)minutes * 60000UL;
    display_ui_clear(COLOR_BLACK);
}

void reminders_show_settings_menu() {
    bool editing = true;
    uint8_t cursor = 0; // 0=enabled, 1=interval, 2=back

    auto _redraw = [&]() {
        display_ui_clear(COLOR_BLACK);
        display_ui_draw_text_centered("Reminder Settings", 10, COLOR_CYAN, FONT_MEDIUM);

        char buf[48];
        snprintf(buf, sizeof(buf), "[%c] Enabled", _settings.enabled ? 'X' : ' ');
        display_ui_draw_text(buf, 4, 40,
                             cursor == 0 ? COLOR_YELLOW : COLOR_WHITE, FONT_SMALL);

        if (_settings.interval_min == 0) {
            snprintf(buf, sizeof(buf), "Time: %02d:%02d (wall)", _settings.hour, _settings.minute);
        } else {
            snprintf(buf, sizeof(buf), "Every: %d min", _settings.interval_min);
        }
        display_ui_draw_text(buf, 4, 65,
                             cursor == 1 ? COLOR_YELLOW : COLOR_WHITE, FONT_SMALL);

        if (!_settings.clock_synced && _settings.interval_min == 0) {
            display_ui_draw_text("! Clock not synced", 4, 85, COLOR_RED, FONT_SMALL);
        }

        display_ui_draw_text("BACK=exit  SELECT=edit", 4, 110, COLOR_GRAY, FONT_SMALL);
    };

    _redraw();

    while (editing) {
        buttons_update();
        if (button_just_pressed(BTN_ID_UP)) {
            cursor = (cursor == 0) ? 2 : cursor - 1;
            _redraw();
        }
        if (button_just_pressed(BTN_ID_DOWN)) {
            cursor = (cursor >= 2) ? 0 : cursor + 1;
            _redraw();
        }
        if (button_just_pressed(BTN_ID_SELECT)) {
            switch (cursor) {
                case 0:
                    _settings.enabled = !_settings.enabled;
                    break;
                case 1:
                    // Cycle intervals: 10, 20, 30, 60, 90, 120 min, then 0 (wall)
                    {
                        const uint8_t steps[] = {10, 20, 30, 60, 90, 120, 0};
                        const uint8_t nsteps  = sizeof(steps);
                        uint8_t idx = 0;
                        for (uint8_t i = 0; i < nsteps; i++) {
                            if (steps[i] == _settings.interval_min) { idx = i; break; }
                        }
                        idx = (idx + 1) % nsteps;
                        _settings.interval_min = steps[idx];
                    }
                    break;
                case 2:
                    editing = false;
                    break;
            }
            _redraw();
        }
        if (button_just_pressed(BTN_ID_BACK)) {
            editing = false;
        }
        delay(20);
    }

    reminders_save();
    display_ui_clear(COLOR_BLACK);
}

const ReminderSettings& reminders_get_settings() {
    return _settings;
}

void reminders_set_enabled(bool en) {
    _settings.enabled = en;
    reminders_save();
}

void reminders_set_interval(uint8_t minutes) {
    _settings.interval_min = minutes;
    reminders_save();
}
