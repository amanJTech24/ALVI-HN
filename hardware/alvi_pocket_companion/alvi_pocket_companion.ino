// ============================================================
// ALVI Pocket Companion / ALVI Mini Cognitive Lab
// Firmware for ESP32 DevKit V1 + 1.8" ST7735 SPI TFT
// ============================================================
#include <Arduino.h>
#include <SPI.h>

#if __has_include("config.h")
#include "config.h"
#else
#include "config.example.h"
#endif

#include "pins.h"
#include "display_ui.h"
#include "buttons.h"
#include "timmy.h"
#include "memory_game.h"
#include "reaction_game.h"
#include "reminders.h"
#include "storage.h"
#include "protocol.h"
#include "usb_sync.h"
#include "wifi_sync.h"

// Application screen states
enum AppScreen {
    SCREEN_BOOT_LOGO,
    SCREEN_BOOT_WELCOME,
    SCREEN_MAIN_MENU,
    SCREEN_TIMMY_MOOD,
    SCREEN_MOOD_FEEDBACK,
    SCREEN_MEMORY_GAME,
    SCREEN_REACTION_GAME,
    SCREEN_VOICE_CHECKIN,
    SCREEN_DAILY_REMINDER,
    SCREEN_DEVICE_SYNC,
    SCREEN_NEUROPEN,
    SCREEN_NEUROPEN_ACTIVE,
    SCREEN_NEUROPEN_DONE,
    SCREEN_REMINDER_ALERT
};

static AppScreen _currentScreen = SCREEN_BOOT_LOGO;
static uint32_t  _bootTimer     = 0;
static char      _sessionId[32] = "sess_hw_default";
static char      _neuropenSessionId[37] = "";
static uint32_t  _neuropenStartTime     = 0;
static uint32_t  _neuropenLastElapsedSec = 0xFFFFFFFF;

// Main menu configuration
static const uint8_t MENU_COUNT = 7;
static const char* MENU_ITEMS[MENU_COUNT] = {
    "1. Timmy / Mood",
    "2. Memory Game",
    "3. Reaction Test",
    "4. Voice Check-in",
    "5. Daily Reminder",
    "6. Device Sync",
    "7. NeuroPen"
};
static uint8_t _menuSelected = 0;
static uint8_t _menuScroll   = 0;

// Mood options (6 user-selected moods)
static const uint8_t MOOD_COUNT = 6;
static const char* MOOD_NAMES[MOOD_COUNT] = {
    "Happy", "Calm", "Tired", "Sad", "Anxious", "Okay"
};
static const TimmyMood MOOD_ENUMS[MOOD_COUNT] = {
    MOOD_HAPPY, MOOD_CALM, MOOD_TIRED, MOOD_SAD, MOOD_ANXIOUS, MOOD_OKAY
};
static const char* MOOD_MESSAGES[MOOD_COUNT] = {
    "Glad to see your smile!",
    "Peaceful moments help.",
    "Rest is brain medicine.",
    "I'm right here with you.",
    "Take a gentle breath.",
    "Steady and strong."
};
static uint8_t  _moodSelected = 0;
static uint32_t _feedbackTimer = 0;

// LED & status blink
static uint32_t _ledTimer = 0;

// Helper forward declarations
static void drawMainMenu();
static void drawMoodScreen();
static void drawVoiceCheckin();
static void drawReminderScreen();
static void drawSyncScreen();
static void drawNeuroPenReadyScreen();
static void drawNeuroPenActiveScreen(uint32_t elapsed_sec);
static void updateNeuroPenTimer(uint32_t elapsed_sec);
static void drawNeuroPenResultScreen(uint32_t duration_ms, bool completed);
static void drawReminderAlert();

void setup() {
    // 1. Hardware pin modes
    pinMode(STATUS_LED, OUTPUT);
    digitalWrite(STATUS_LED, HIGH); // LED on during boot

#ifdef BUZZER_PIN
    pinMode(BUZZER_PIN, OUTPUT);
    digitalWrite(BUZZER_PIN, LOW);
#endif

    // 2. Subsystems
    buttons_init();
    display_init(TFT_INIT_TYPE);
    protocol_init(SERIAL_BAUD);
    storage_init();
    reminders_init();
    usb_sync_init();
    wifi_sync_init();

    // 3. Mini Timmy
    timmy_init(&display_get_tft());

    // 4. Initial boot screen
    display_clear(C_BG);
    display_title("ALVI", C_ACCENT);
    display_subtitle("Mini Cognitive Lab", C_WHITE);
    display_hline(36, C_ACCENT);
    display_centered_text(55, "Pocket Companion", C_LGRAY, 1);
    display_centered_text(75, "v1.0 (Phase 12)", C_TEAL, 1);
    display_progress_bar(14, 110, 100, 8, 100, C_ACCENT);
    display_status_bar("Initializing...", C_ACCENT);

    // Announce device to USB host
    protocol_send_hello(DEVICE_ID, DEVICE_NAME);

    _bootTimer = millis();
    _currentScreen = SCREEN_BOOT_LOGO;
    digitalWrite(STATUS_LED, LOW);
}

void loop() {
    uint32_t now = millis();

    // Status LED heartbeat (blink every 2 seconds)
    if (now - _ledTimer > 2000) {
        _ledTimer = now;
        digitalWrite(STATUS_LED, HIGH);
        delayMicroseconds(10000);
        digitalWrite(STATUS_LED, LOW);
    }

    // Background sync managers
    usb_sync_update();
    wifi_sync_update();
    reminders_update();

    // Check reminder due (if not already handling it)
    if (reminders_is_due() && _currentScreen != SCREEN_REMINDER_ALERT) {
        _currentScreen = SCREEN_REMINDER_ALERT;
        drawReminderAlert();
        return;
    }

    // Read debounced buttons
    ButtonEvent ev = buttons_read();

    switch (_currentScreen) {
        case SCREEN_BOOT_LOGO:
            if (now - _bootTimer > 1800 || ev.type != PRESS_NONE) {
                _currentScreen = SCREEN_BOOT_WELCOME;
                display_clear(C_BG);
                display_centered_text(10, "Hello!", C_ACCENT, 2);
                timmy_set_mood(MOOD_WELCOME);
                timmy_draw_full();
                display_centered_text(130, "I am Mini Timmy", C_WHITE, 1);
                _bootTimer = now;
            }
            break;

        case SCREEN_BOOT_WELCOME:
            timmy_update();
            if (now - _bootTimer > 2000 || ev.type != PRESS_NONE) {
                _currentScreen = SCREEN_MAIN_MENU;
                drawMainMenu();
            }
            break;

        case SCREEN_MAIN_MENU:
            if (ev.type == PRESS_SHORT) {
                if (ev.btn == BTN_ID_UP) {
                    if (_menuSelected > 0) _menuSelected--;
                    else _menuSelected = MENU_COUNT - 1;
                    if (_menuSelected < _menuScroll) _menuScroll = _menuSelected;
                    if (_menuSelected >= _menuScroll + 5) _menuScroll = _menuSelected - 4;
                    drawMainMenu();
                } else if (ev.btn == BTN_ID_DOWN) {
                    if (_menuSelected < MENU_COUNT - 1) _menuSelected++;
                    else _menuSelected = 0;
                    if (_menuSelected >= _menuScroll + 5) _menuScroll = _menuSelected - 4;
                    if (_menuSelected < _menuScroll) _menuScroll = _menuSelected;
                    drawMainMenu();
                } else if (ev.btn == BTN_ID_SELECT) {
                    // Navigate to chosen screen
                    switch (_menuSelected) {
                        case 0:
                            _currentScreen = SCREEN_TIMMY_MOOD;
                            drawMoodScreen();
                            break;
                        case 1:
                            _currentScreen = SCREEN_MEMORY_GAME;
                            memory_game_start(_sessionId);
                            break;
                        case 2:
                            _currentScreen = SCREEN_REACTION_GAME;
                            reaction_game_start(_sessionId);
                            break;
                        case 3:
                            _currentScreen = SCREEN_VOICE_CHECKIN;
                            drawVoiceCheckin();
                            break;
                        case 4:
                            _currentScreen = SCREEN_DAILY_REMINDER;
                            drawReminderScreen();
                            break;
                        case 5:
                            _currentScreen = SCREEN_DEVICE_SYNC;
                            drawSyncScreen();
                            break;
                        case 6:
                            _currentScreen = SCREEN_NEUROPEN;
                            drawNeuroPenReadyScreen();
                            break;
                    }
                }
            }
            break;

        case SCREEN_TIMMY_MOOD:
            timmy_update();
            if (ev.type == PRESS_SHORT) {
                if (ev.btn == BTN_ID_BACK) {
                    _currentScreen = SCREEN_MAIN_MENU;
                    drawMainMenu();
                } else if (ev.btn == BTN_ID_UP) {
                    if (_moodSelected > 0) _moodSelected--;
                    else _moodSelected = MOOD_COUNT - 1;
                    drawMoodScreen();
                } else if (ev.btn == BTN_ID_DOWN) {
                    if (_moodSelected < MOOD_COUNT - 1) _moodSelected++;
                    else _moodSelected = 0;
                    drawMoodScreen();
                } else if (ev.btn == BTN_ID_SELECT) {
                    // Record mood choice
                    char evUuid[37];
                    storage_gen_uuid(evUuid, sizeof(evUuid));

                    char payload[128];
                    snprintf(payload, sizeof(payload),
                             "{\"mood_code\":%u,\"mood_name\":\"%s\"}",
                             _moodSelected + 1, MOOD_NAMES[_moodSelected]);

                    usb_sync_queue_event("MOOD_SELECTED", _sessionId, "hw_mood", payload);
                    protocol_send_mood(_sessionId, evUuid, _moodSelected + 1, MOOD_NAMES[_moodSelected]);

                    // Show feedback
                    _currentScreen = SCREEN_MOOD_FEEDBACK;
                    _feedbackTimer = now;
                    display_clear(C_BG);
                    display_title("Mood Logged", C_GREEN);
                    display_hline(28, C_ACCENT);
                    timmy_set_mood(MOOD_ENUMS[_moodSelected]);
                    timmy_draw_full();
                    display_centered_text(125, MOOD_NAMES[_moodSelected], C_YELLOW, 2);
                    display_centered_text(145, MOOD_MESSAGES[_moodSelected], C_WHITE, 1);
                }
            }
            break;

        case SCREEN_MOOD_FEEDBACK:
            timmy_update();
            if (now - _feedbackTimer > 2500 || ev.type != PRESS_NONE) {
                _currentScreen = SCREEN_MAIN_MENU;
                drawMainMenu();
            }
            break;

        case SCREEN_MEMORY_GAME:
            memory_game_update();
            if (memory_game_done()) {
                const MemoryResult& res = memory_game_result();
                char evUuid[37];
                storage_gen_uuid(evUuid, sizeof(evUuid));

                char payload[192];
                snprintf(payload, sizeof(payload),
                         "{\"max_level\":%u,\"correct_count\":%u,\"error_count\":%u,\"duration_ms\":%u,\"completed\":%s}",
                         res.max_level, res.correct_count, res.error_count,
                         (unsigned)res.duration_ms, res.completed ? "true" : "false");

                usb_sync_queue_event("MEMORY_RESULT", _sessionId, "hw_memory_seq", payload);
                protocol_send_memory_result(_sessionId, evUuid, res.max_level,
                                           res.correct_count, res.error_count, res.duration_ms);

                display_clear(C_BG);
                display_title("Game Over", C_WHITE);
                display_hline(26, C_ACCENT);
                char buf[32];
                snprintf(buf, sizeof(buf), "Max Level: %u", res.max_level);
                display_centered_text(50, buf, C_GREEN, 2);
                snprintf(buf, sizeof(buf), "Correct: %u | Errors: %u", res.correct_count, res.error_count);
                display_centered_text(80, buf, C_LGRAY, 1);
                display_centered_text(110, "Result Queued!", C_TEAL, 1);
                display_status_bar("Press any key", C_ACCENT);
                delay(1200);

                // Wait for press
                while (buttons_read().type == PRESS_NONE) { delay(20); }
                memory_game_reset();
                _currentScreen = SCREEN_MAIN_MENU;
                drawMainMenu();
            }
            break;

        case SCREEN_REACTION_GAME:
            reaction_game_update();
            if (reaction_game_done()) {
                const ReactionResult& res = reaction_game_result();
                char evUuid[37];
                storage_gen_uuid(evUuid, sizeof(evUuid));

                char payload[192];
                snprintf(payload, sizeof(payload),
                         "{\"median_rt_ms\":%u,\"false_starts\":%u,\"missed\":%u,\"trial_count\":%u,\"duration_ms\":%u,\"completed\":%s}",
                         res.median_rt_ms, res.false_starts, res.missed, res.trial_count,
                         (unsigned)res.duration_ms, res.completed ? "true" : "false");

                usb_sync_queue_event("REACTION_RESULT", _sessionId, "hw_reaction_test", payload);
                protocol_send_reaction_result(_sessionId, evUuid, res.median_rt_ms,
                                             res.false_starts, res.missed, res.trial_count);

                display_clear(C_BG);
                display_title("Reaction Test", C_WHITE);
                display_hline(26, C_ACCENT);
                char buf[32];
                snprintf(buf, sizeof(buf), "Median: %u ms", res.median_rt_ms);
                display_centered_text(50, buf, C_YELLOW, 2);
                snprintf(buf, sizeof(buf), "Trials: %u | False: %u", res.trial_count, res.false_starts);
                display_centered_text(80, buf, C_LGRAY, 1);
                display_centered_text(110, "Result Queued!", C_TEAL, 1);
                display_status_bar("Press any key", C_ACCENT);
                delay(1200);

                while (buttons_read().type == PRESS_NONE) { delay(20); }
                reaction_game_reset();
                _currentScreen = SCREEN_MAIN_MENU;
                drawMainMenu();
            }
            break;

        case SCREEN_VOICE_CHECKIN:
            if (ev.type == PRESS_SHORT && ev.btn == BTN_ID_BACK) {
                _currentScreen = SCREEN_MAIN_MENU;
                drawMainMenu();
            }
            break;

        case SCREEN_DAILY_REMINDER:
            if (ev.type == PRESS_SHORT) {
                if (ev.btn == BTN_ID_BACK) {
                    reminders_save();
                    _currentScreen = SCREEN_MAIN_MENU;
                    drawMainMenu();
                } else if (ev.btn == BTN_ID_SELECT) {
                    // Toggle enable
                    const ReminderSettings& s = reminders_get_settings();
                    reminders_set_enabled(!s.enabled);
                    drawReminderScreen();
                } else if (ev.btn == BTN_ID_UP) {
                    const ReminderSettings& s = reminders_get_settings();
                    reminders_set_interval(min(240, s.interval_min + 15));
                    drawReminderScreen();
                } else if (ev.btn == BTN_ID_DOWN) {
                    const ReminderSettings& s = reminders_get_settings();
                    reminders_set_interval(max(15, s.interval_min - 15));
                    drawReminderScreen();
                }
            }
            break;

        case SCREEN_DEVICE_SYNC:
            if (ev.type == PRESS_SHORT) {
                if (ev.btn == BTN_ID_BACK) {
                    _currentScreen = SCREEN_MAIN_MENU;
                    drawMainMenu();
                } else if (ev.btn == BTN_ID_SELECT) {
                    // Force hello handshake & status
                    protocol_send_hello(DEVICE_ID, DEVICE_NAME);
                    protocol_send_status(100, wifi_sync_connected(), storage_pending_count());
                    drawSyncScreen();
                }
            }
            break;

        case SCREEN_NEUROPEN:
            if (ev.type == PRESS_SHORT) {
                if (ev.btn == BTN_ID_BACK) {
                    _currentScreen = SCREEN_MAIN_MENU;
                    drawMainMenu();
                } else if (ev.btn == BTN_ID_SELECT) {
                    storage_gen_uuid(_neuropenSessionId, sizeof(_neuropenSessionId));
                    char evUuid[37];
                    storage_gen_uuid(evUuid, sizeof(evUuid));

                    _neuropenStartTime = millis();
                    _neuropenLastElapsedSec = 0;

                    char payload[160];
                    snprintf(payload, sizeof(payload),
                             "{\"task\":\"clock_drawing\",\"target_time\":\"11:10\",\"status\":\"started\"}");
                    usb_sync_queue_event("NEUROPEN_START", _neuropenSessionId, "hw_neuropen", payload);
                    protocol_send_neuropen_start(_neuropenSessionId, evUuid, "clock_drawing", "11:10");

                    _currentScreen = SCREEN_NEUROPEN_ACTIVE;
                    drawNeuroPenActiveScreen(0);
                }
            }
            break;

        case SCREEN_NEUROPEN_ACTIVE:
            {
                uint32_t elapsed_sec = (millis() - _neuropenStartTime) / 1000;
                if (elapsed_sec != _neuropenLastElapsedSec) {
                    _neuropenLastElapsedSec = elapsed_sec;
                    updateNeuroPenTimer(elapsed_sec);
                }
            }

            if (ev.type == PRESS_SHORT) {
                if (ev.btn == BTN_ID_SELECT) {
                    uint32_t dur_ms = millis() - _neuropenStartTime;
                    char evUuid[37];
                    storage_gen_uuid(evUuid, sizeof(evUuid));

                    char payload[192];
                    snprintf(payload, sizeof(payload),
                             "{\"task\":\"clock_drawing\",\"target_time\":\"11:10\",\"duration_ms\":%u,\"duration_sec\":%u,\"status\":\"completed\"}",
                             (unsigned)dur_ms, (unsigned)(dur_ms / 1000));
                    usb_sync_queue_event("NEUROPEN_FINISH", _neuropenSessionId, "hw_neuropen", payload);
                    protocol_send_neuropen_finish(_neuropenSessionId, evUuid, dur_ms, "clock_drawing", "completed");

                    _currentScreen = SCREEN_NEUROPEN_DONE;
                    drawNeuroPenResultScreen(dur_ms, true);
                } else if (ev.btn == BTN_ID_BACK) {
                    uint32_t dur_ms = millis() - _neuropenStartTime;
                    char evUuid[37];
                    storage_gen_uuid(evUuid, sizeof(evUuid));

                    char payload[192];
                    snprintf(payload, sizeof(payload),
                             "{\"task\":\"clock_drawing\",\"target_time\":\"11:10\",\"duration_ms\":%u,\"duration_sec\":%u,\"status\":\"cancelled\"}",
                             (unsigned)dur_ms, (unsigned)(dur_ms / 1000));
                    usb_sync_queue_event("NEUROPEN_FINISH", _neuropenSessionId, "hw_neuropen", payload);
                    protocol_send_neuropen_finish(_neuropenSessionId, evUuid, dur_ms, "clock_drawing", "cancelled");

                    _currentScreen = SCREEN_NEUROPEN_DONE;
                    drawNeuroPenResultScreen(dur_ms, false);
                }
            }
            break;

        case SCREEN_NEUROPEN_DONE:
            if (ev.type != PRESS_NONE) {
                _currentScreen = SCREEN_MAIN_MENU;
                drawMainMenu();
            }
            break;

        case SCREEN_REMINDER_ALERT:
            if (ev.type == PRESS_SHORT) {
                if (ev.btn == BTN_ID_BACK) {
                    reminders_dismiss();
                    _currentScreen = SCREEN_MAIN_MENU;
                    drawMainMenu();
                } else if (ev.btn == BTN_ID_SELECT) {
                    reminders_snooze(10);
                    _currentScreen = SCREEN_MAIN_MENU;
                    drawMainMenu();
                }
            }
            break;
    }
}

// ── Screen Rendering Implementations ────────────────────────────────────────

static void drawMainMenu() {
    display_clear(C_BG);
    display_title("ALVI Pocket", C_WHITE);
    display_hline(24, C_ACCENT);
    display_menu(MENU_ITEMS, MENU_COUNT, _menuSelected, _menuScroll);
    display_status_bar("UP/DN=Nav  SEL=Go", C_ACCENT);
}

static void drawMoodScreen() {
    display_clear(C_BG);
    display_title("Mood Check", C_WHITE);
    display_hline(20, C_ACCENT);

    // Mini Timmy preview of selected mood
    timmy_set_mood(MOOD_ENUMS[_moodSelected]);
    timmy_draw_full();

    // Mood selection pill
    char buf[24];
    snprintf(buf, sizeof(buf), "< %s >", MOOD_NAMES[_moodSelected]);
    display_centered_text(120, buf, C_YELLOW, 2);
    display_status_bar("UP/DN=Pick  SEL=Save", C_ACCENT);
}

static void drawVoiceCheckin() {
    display_clear(C_BG);
    display_title("Voice Check", C_WHITE);
    display_hline(22, C_ACCENT);

    display_centered_text(32, "Use Laptop Mic", C_YELLOW, 1);
    display_centered_text(48, "ESP32 has no audio hw", C_LGRAY, 1);

    display_badge(14, 68, usb_sync_connected() ? "USB: CONNECTED" : "USB: WAITING",
                  usb_sync_connected() ? C_GREEN : C_GRAY, C_BLACK);

    display_text(8, 92, "1. Open browser at:", C_WHITE, 1);
    display_text(16, 104, "http://localhost:5500", C_TEAL, 1);
    display_text(8, 118, "2. Click Voice Check-in", C_WHITE, 1);
    display_text(8, 130, "3. Speak for 10 sec", C_WHITE, 1);

    display_status_bar("BACK=Return to Menu", C_ACCENT);
}

static void drawReminderScreen() {
    display_clear(C_BG);
    display_title("Reminders", C_WHITE);
    display_hline(22, C_ACCENT);

    const ReminderSettings& s = reminders_get_settings();

    char buf[32];
    snprintf(buf, sizeof(buf), "Status: %s", s.enabled ? "ENABLED" : "DISABLED");
    display_text(10, 36, buf, s.enabled ? C_GREEN : C_RED, 1);

    snprintf(buf, sizeof(buf), "Interval: %u min", s.interval_min);
    display_text(10, 56, buf, C_WHITE, 1);

    display_text(10, 76, s.clock_synced ? "Clock: Synced (LAN)" : "Clock: Relative countdown",
                 s.clock_synced ? C_TEAL : C_LGRAY, 1);

    display_text(10, 100, "SEL  : Toggle On/Off", C_LGRAY, 1);
    display_text(10, 114, "UP/DN: Adjust min", C_LGRAY, 1);
    display_text(10, 128, "BACK : Save & Exit", C_LGRAY, 1);

    display_status_bar("Daily Practice Alert", C_ACCENT);
}

static void drawSyncScreen() {
    display_clear(C_BG);
    display_title("Device Sync", C_WHITE);
    display_hline(22, C_ACCENT);

    display_text(10, 32, "Device: " DEVICE_ID, C_WHITE, 1);

    char buf[32];
    snprintf(buf, sizeof(buf), "USB: %s", usb_sync_connected() ? "ONLINE" : "WAITING");
    display_text(10, 50, buf, usb_sync_connected() ? C_GREEN : C_GRAY, 1);

    snprintf(buf, sizeof(buf), "WiFi: %s", wifi_sync_connected() ? "CONNECTED" : "OFFLINE");
    display_text(10, 68, buf, wifi_sync_connected() ? C_GREEN : C_GRAY, 1);

    snprintf(buf, sizeof(buf), "Pending Queue: %u", storage_pending_count());
    display_text(10, 86, buf, storage_pending_count() > 0 ? C_YELLOW : C_TEAL, 1);

    display_text(10, 110, "SEL = Ping / Sync now", C_LGRAY, 1);
    display_text(10, 124, "BACK = Main menu", C_LGRAY, 1);

    display_status_bar("115200 Baud JSON", C_ACCENT);
}

static void drawNeuroPenReadyScreen() {
    display_clear(C_BG);
    display_title("ALVI NEUROPEN", C_WHITE);
    display_hline(22, C_ACCENT);

    display_centered_text(34, "Draw a clock", C_YELLOW, 2);
    display_centered_text(58, "Time: 11:10", C_TEAL, 2);
    display_centered_text(84, "Pen & paper ready?", C_LGRAY, 1);

    display_badge(10, 106, "SELECT: START", C_GREEN, C_BLACK);
    display_badge(10, 126, "BACK: MENU", C_GRAY, C_WHITE);
    display_status_bar("Clock Drawing Test", C_ACCENT);
}

static void drawNeuroPenActiveScreen(uint32_t elapsed_sec) {
    display_clear(C_BG);
    display_title("ALVI NEUROPEN", C_WHITE);
    display_hline(22, C_ACCENT);

    display_centered_text(32, "Draw on paper", C_YELLOW, 2);
    display_centered_text(54, "Target: 11:10", C_WHITE, 1);

    char buf[32];
    snprintf(buf, sizeof(buf), "Elapsed: %us", (unsigned)elapsed_sec);
    display_centered_text(74, buf, C_TEAL, 2);

    display_badge(10, 106, "SELECT: FINISH", C_GREEN, C_BLACK);
    display_badge(10, 126, "BACK: CANCEL", C_RED, C_WHITE);
    display_status_bar("Timer Running...", C_ACCENT);
}

static void updateNeuroPenTimer(uint32_t elapsed_sec) {
    display_badge(10, 72, "                ", C_BG, C_BG);
    char buf[32];
    snprintf(buf, sizeof(buf), "Elapsed: %us", (unsigned)elapsed_sec);
    display_centered_text(74, buf, C_TEAL, 2);
}

static void drawNeuroPenResultScreen(uint32_t duration_ms, bool completed) {
    display_clear(C_BG);
    display_title("ALVI NEUROPEN", C_WHITE);
    display_hline(22, C_ACCENT);

    if (completed) {
        display_centered_text(32, "FINISHED!", C_GREEN, 2);
        char buf[32];
        snprintf(buf, sizeof(buf), "Time: %.1fs", (float)duration_ms / 1000.0f);
        display_centered_text(58, buf, C_YELLOW, 2);
        display_centered_text(84, "Result Queued!", C_TEAL, 1);
        display_centered_text(102, "Upload photo/video", C_WHITE, 1);
        display_centered_text(116, "on ALVI website", C_LGRAY, 1);
    } else {
        display_centered_text(36, "CANCELLED", C_RED, 2);
        display_centered_text(66, "Session stopped", C_LGRAY, 1);
        display_centered_text(90, "No result saved", C_WHITE, 1);
    }

    display_status_bar("Press any button", C_ACCENT);
}

static void drawReminderAlert() {
    display_clear(C_RED);
    display_centered_text(14, "PRACTICE TIME!", C_WHITE, 2);
    display_centered_text(45, "Daily Mind Exercise", C_YELLOW, 1);
    display_centered_text(65, "A quick check-in", C_WHITE, 1);
    display_centered_text(80, "keeps neurons sharp!", C_WHITE, 1);

    display_badge(10, 108, "SEL: Snooze 10m", C_WHITE, C_BLACK);
    display_badge(10, 126, "BACK: Dismiss", C_WHITE, C_BLACK);
    display_status_bar("ALVI Reminder", C_WHITE);

#ifdef BUZZER_PIN
    // 3 short alert beeps
    for (int i = 0; i < 3; i++) {
        digitalWrite(BUZZER_PIN, HIGH);
        delay(80);
        digitalWrite(BUZZER_PIN, LOW);
        delay(80);
    }
#endif
}
