// reaction_game.cpp — Reaction Time Test implementation
// Activity ID: "hw_reaction_test"
#include "reaction_game.h"
#include "display_ui.h"
#include "buttons.h"
#include "pins.h"
#include <esp_timer.h>
#include <Arduino.h>

// ─── State machine ──────────────────────────────────────────────────────────
enum RxState {
    RX_IDLE,
    RX_COUNTDOWN,
    RX_WAITING,
    RX_SHOW_STIMULUS,
    RX_MEASURING,
    RX_FEEDBACK,
    RX_DONE
};

static RxState       _state           = RX_IDLE;
static ReactionResult _result;
static uint8_t       _valid_trials    = 0;   // trials with valid RT recorded
static uint32_t      _state_enter_ms  = 0;
static int64_t       _stimulus_us     = 0;   // time of stimulus (esp_timer µs)
static uint32_t      _wait_delay_ms   = 0;   // random wait duration
static uint8_t       _countdown_val   = 3;
static uint32_t      _game_start_ms   = 0;
static uint16_t      _valid_rt[REACTION_TRIALS];  // growing sorted list

// ─── Helpers ────────────────────────────────────────────────────────────────
static void _insert_sorted(uint16_t* arr, uint8_t count, uint16_t val) {
    // Insert val into arr[0..count-1] keeping ascending order.
    // arr must have space for count+1.
    int i = (int)count - 1;
    while (i >= 0 && arr[i] > val) {
        arr[i + 1] = arr[i];
        i--;
    }
    arr[i + 1] = val;
}

static uint16_t _compute_median(uint16_t* sorted, uint8_t count) {
    if (count == 0) return 0;
    if (count % 2 == 1) return sorted[count / 2];
    return (uint16_t)(((uint32_t)sorted[count / 2 - 1] + sorted[count / 2]) / 2);
}

static void _enter_state(RxState s) {
    _state          = s;
    _state_enter_ms = millis();
}

static void _start_trial() {
    // Random wait 1500–4000 ms
    _wait_delay_ms = 1500 + (esp_random() % 2501);
    _enter_state(RX_WAITING);

    display_ui_clear(COLOR_RED);
    display_ui_draw_text_centered("WAIT...", 60, COLOR_WHITE, FONT_LARGE);
    display_ui_draw_text_centered(
        (String("Trial ") + (_valid_trials + 1) + "/" + REACTION_TRIALS).c_str(),
        20, COLOR_WHITE, FONT_SMALL);
}

// ─── Public API ─────────────────────────────────────────────────────────────
void reaction_game_init() {
    reaction_game_reset();
}

void reaction_game_reset() {
    _state          = RX_IDLE;
    _valid_trials   = 0;
    _state_enter_ms = 0;
    _stimulus_us    = 0;
    _wait_delay_ms  = 0;
    _countdown_val  = 3;
    _game_start_ms  = 0;
    memset(&_result, 0, sizeof(_result));
    memset(_valid_rt, 0, sizeof(_valid_rt));
}

void reaction_game_start(const char* session_id) {
    reaction_game_reset();
    strlcpy(_result.session_id, session_id, sizeof(_result.session_id));
    _game_start_ms = millis();
    _countdown_val = 3;
    _enter_state(RX_COUNTDOWN);

    display_ui_clear(COLOR_BLACK);
    display_ui_draw_text_centered("Reaction Test", 30, COLOR_CYAN, FONT_LARGE);
    display_ui_draw_text_centered("Get Ready!", 70, COLOR_WHITE, FONT_MEDIUM);
    display_ui_draw_text_centered("3", 100, COLOR_YELLOW, FONT_XLARGE);
}

void reaction_game_update() {
    uint32_t now_ms = millis();

    // ── Global: BTN_BACK long-press exits ────────────────────────────────
    if (_state != RX_IDLE && _state != RX_DONE) {
        if (button_long_pressed(BTN_ID_BACK)) {
            _result.completed    = false;
            _result.duration_ms  = now_ms - _game_start_ms;
            _result.trial_count  = _valid_trials;
            _enter_state(RX_DONE);

            display_ui_clear(COLOR_BLACK);
            display_ui_draw_text_centered("Cancelled", 70, COLOR_RED, FONT_LARGE);
            return;
        }
    }

    switch (_state) {

    // ── COUNTDOWN ────────────────────────────────────────────────────────
    case RX_COUNTDOWN: {
        if (now_ms - _state_enter_ms >= 1000) {
            _state_enter_ms = now_ms;
            if (_countdown_val > 1) {
                _countdown_val--;
                display_ui_clear(COLOR_BLACK);
                display_ui_draw_text_centered("Get Ready!", 40, COLOR_WHITE, FONT_MEDIUM);
                char buf[4];
                snprintf(buf, sizeof(buf), "%d", _countdown_val);
                display_ui_draw_text_centered(buf, 80, COLOR_YELLOW, FONT_XLARGE);
            } else {
                _start_trial();
            }
        }
        break;
    }

    // ── WAITING (red screen – do NOT press) ──────────────────────────────
    case RX_WAITING: {
        // False-start detection
        if (button_just_pressed(BTN_ID_SELECT)) {
            _result.false_starts++;
            display_ui_clear(COLOR_RED);
            display_ui_draw_text_centered("Too Early!", 55, COLOR_WHITE, FONT_LARGE);
            display_ui_draw_text_centered("Wait for YELLOW", 90, COLOR_WHITE, FONT_SMALL);
            delay(800);   // brief penalty pause (blocking OK – game context)
            _start_trial();
            return;
        }
        // Show stimulus when delay elapsed
        if (now_ms - _state_enter_ms >= _wait_delay_ms) {
            _stimulus_us = esp_timer_get_time();
            _enter_state(RX_SHOW_STIMULUS);

            display_ui_clear(COLOR_YELLOW);
            display_ui_draw_text_centered("PRESS!", 70, COLOR_BLACK, FONT_XLARGE);
        }
        break;
    }

    // ── SHOW_STIMULUS — just a visual frame; immediately move to MEASURING
    case RX_SHOW_STIMULUS: {
        _enter_state(RX_MEASURING);
        break;
    }

    // ── MEASURING ────────────────────────────────────────────────────────
    case RX_MEASURING: {
        // Missed: 2000ms timeout
        if (now_ms - _state_enter_ms >= 2000) {
            _result.missed++;
            _enter_state(RX_FEEDBACK);
            display_ui_clear(COLOR_BLACK);
            display_ui_draw_text_centered("Too Slow!", 55, COLOR_RED, FONT_LARGE);
            display_ui_draw_text_centered("(missed)", 90, COLOR_GRAY, FONT_SMALL);
            return;
        }
        // Button press → measure RT
        if (button_just_pressed(BTN_ID_SELECT)) {
            int64_t now_us = esp_timer_get_time();
            uint32_t rt_us = (uint32_t)(now_us - _stimulus_us);
            uint16_t rt_ms = (uint16_t)(rt_us / 1000);

            if (rt_ms < MIN_VALID_RT_MS) {
                // Treated as false start (anticipation)
                _result.false_starts++;
                _enter_state(RX_FEEDBACK);
                display_ui_clear(COLOR_BLACK);
                display_ui_draw_text_centered("Too Fast!", 50, COLOR_ORANGE, FONT_LARGE);
                display_ui_draw_text_centered("(anticipation)", 85, COLOR_GRAY, FONT_SMALL);
            } else {
                // Record valid RT
                _result.rt_ms[_valid_trials] = rt_ms;
                _insert_sorted(_valid_rt, _valid_trials, rt_ms);
                _valid_trials++;

                _enter_state(RX_FEEDBACK);
                char buf[32];
                snprintf(buf, sizeof(buf), "%u ms", rt_ms);
                display_ui_clear(COLOR_BLACK);
                display_ui_draw_text_centered("Your time:", 45, COLOR_WHITE, FONT_MEDIUM);
                display_ui_draw_text_centered(buf, 75, COLOR_GREEN, FONT_XLARGE);
            }
        }
        break;
    }

    // ── FEEDBACK — show result for 1200ms then advance ───────────────────
    case RX_FEEDBACK: {
        if (now_ms - _state_enter_ms >= 1200) {
            if (_valid_trials >= REACTION_TRIALS) {
                // All valid trials complete
                _result.trial_count  = _valid_trials;
                _result.median_rt_ms = _compute_median(_valid_rt, _valid_trials);
                _result.duration_ms  = now_ms - _game_start_ms;
                _result.completed    = true;
                _enter_state(RX_DONE);

                // Final summary screen
                display_ui_clear(COLOR_BLACK);
                display_ui_draw_text_centered("Done!", 20, COLOR_CYAN, FONT_LARGE);
                char med_buf[32];
                snprintf(med_buf, sizeof(med_buf), "Median: %u ms", _result.median_rt_ms);
                display_ui_draw_text_centered(med_buf, 60, COLOR_YELLOW, FONT_MEDIUM);
                char fs_buf[32];
                snprintf(fs_buf, sizeof(fs_buf), "False starts: %d", _result.false_starts);
                display_ui_draw_text_centered(fs_buf, 95, COLOR_WHITE, FONT_SMALL);
                char mi_buf[32];
                snprintf(mi_buf, sizeof(mi_buf), "Missed: %d", _result.missed);
                display_ui_draw_text_centered(mi_buf, 115, COLOR_WHITE, FONT_SMALL);
            } else {
                _start_trial();
            }
        }
        break;
    }

    case RX_IDLE:
    case RX_DONE:
    default:
        break;
    }
}

bool reaction_game_done() {
    return _state == RX_DONE;
}

const ReactionResult& reaction_game_result() {
    return _result;
}
