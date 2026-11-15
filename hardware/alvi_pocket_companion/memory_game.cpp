// memory_game.cpp — 4-color memory sequence game
#include "memory_game.h"
#include "display_ui.h"
#include "buttons.h"
#include "pins.h"
#include <Arduino.h>

// Colors: 1=RED, 2=GREEN, 3=BLUE, 4=YELLOW
static const uint16_t COLOR_MAP[5] = {0, C_RED, C_GREEN, C_BLUE, C_YELLOW};
static const char* COLOR_NAMES[5]  = {"", "RED", "GRN", "BLU", "YLW"};

enum MemState {
    MS_IDLE, MS_SHOWING, MS_WAITING_INPUT,
    MS_FEEDBACK, MS_LEVEL_UP, MS_FAIL, MS_WIN, MS_DONE
};

static MemState     _state = MS_IDLE;
static MemoryResult _result;
static uint8_t  _seq[20];
static uint8_t  _seqLen   = 0;
static uint8_t  _showIdx  = 0;
static uint8_t  _inputIdx = 0;
static uint32_t _stateMs  = 0;
static uint32_t _startMs  = 0;
static bool     _done     = false;
static uint8_t  _flashColor = 0;

static void _tft_drawColorBtn(uint8_t idx, uint8_t highlight);

static void _drawBoard(uint8_t highlight=0) {
    // 2x2 color buttons
    _tft_drawColorBtn(0,  highlight);  // RED    top-left
    _tft_drawColorBtn(1,  highlight);  // GREEN  top-right
    _tft_drawColorBtn(2,  highlight);  // BLUE   bot-left
    _tft_drawColorBtn(3,  highlight);  // YELLOW bot-right
}

static void _tft_drawColorBtn(uint8_t idx, uint8_t highlight) {
    static const int16_t xs[4] = {4,  68, 4,  68};
    static const int16_t ys[4] = {40, 40, 90, 90};
    uint8_t colorId = idx + 1;
    uint16_t col = (highlight == colorId) ? C_WHITE : COLOR_MAP[colorId];
    display_get_tft().fillRoundRect(xs[idx], ys[idx], 56, 42, 6, col);
    display_get_tft().drawRoundRect(xs[idx], ys[idx], 56, 42, 6, C_WHITE);
    display_get_tft().setTextSize(1);
    display_get_tft().setTextColor(C_BLACK);
    display_get_tft().setCursor(xs[idx]+20, ys[idx]+18);
    display_get_tft().print(COLOR_NAMES[colorId]);
}

static void _genSeq() {
    _seqLen++;
    if (_seqLen > 20) _seqLen = 20;
    _seq[_seqLen-1] = random(1, 5);
}

void memory_game_init() {
    _state = MS_IDLE;
    _done  = false;
}

void memory_game_start(const char* sid) {
    memset(&_result, 0, sizeof(_result));
    strncpy(_result.session_id, sid, 31);
    _seqLen  = 0;
    _inputIdx = 0;
    _result.correct_count = 0;
    _result.error_count   = 0;
    _done     = false;
    _startMs  = millis();

    // Clear screen, show title
    display_clear();
    display_centered_text(2, "Memory Game", C_WHITE, 1);
    display_hline(16, C_ACCENT);
    display_centered_text(18, "Watch & repeat!", C_LGRAY, 1);

    _genSeq();
    _showIdx = 0;
    _state   = MS_SHOWING;
    _stateMs = millis();
}

void memory_game_update() {
    if (_state == MS_IDLE || _state == MS_DONE) return;

    uint32_t now = millis();

    switch (_state) {
        case MS_SHOWING: {
            if (now - _stateMs < 500) return;
            _stateMs = now;
            if (_showIdx < _seqLen) {
                uint8_t c = _seq[_showIdx];
                _result.sequence_shown[_showIdx] = c;
                _drawBoard(c);
                delay(400);
                _drawBoard(0);
                _showIdx++;
            } else {
                // All shown — wait for input
                _inputIdx = 0;
                _state = MS_WAITING_INPUT;
                display_text(10, 136, "Your turn!  ", C_YELLOW, 1);
            }
            break;
        }

        case MS_WAITING_INPUT: {
            ButtonEvent ev = buttons_read();
            uint8_t pressed = 0;
            if (ev.type == PRESS_SHORT) {
                if (ev.btn == BTN_ID_SELECT) pressed = 1; // navigate to pick color
                if (ev.btn == BTN_ID_UP)     pressed = 2;
                if (ev.btn == BTN_ID_DOWN)   pressed = 3;
                if (ev.btn == BTN_ID_BACK)   pressed = 4;
            }
            if (ev.btn == BTN_ID_BACK && ev.type == PRESS_LONG) {
                // Exit game
                _result.completed = false;
                _result.duration_ms = millis() - _startMs;
                _result.seq_len = _seqLen;
                _state = MS_DONE; _done = true;
                return;
            }
            if (pressed == 0) return;

            _result.user_responses[_inputIdx] = pressed;
            _drawBoard(pressed);
            delay(150);
            _drawBoard(0);

            if (pressed == _seq[_inputIdx]) {
                _result.correct_count++;
                _inputIdx++;
                if (_inputIdx == _seqLen) {
                    // Level complete
                    _result.max_level = _seqLen;
                    if (_seqLen >= 20) {
                        _state = MS_WIN; _stateMs = now;
                    } else {
                        _state = MS_LEVEL_UP; _stateMs = now;
                    }
                }
            } else {
                _result.error_count++;
                _state = MS_FAIL; _stateMs = now;
            }
            break;
        }

        case MS_LEVEL_UP:
            if (now - _stateMs < 800) {
                display_centered_text(136, "Level up! +1", C_GREEN, 1);
                return;
            }
            _genSeq();
            _showIdx = 0;
            _state   = MS_SHOWING;
            _stateMs = now;
            display_clear();
            display_centered_text(2, "Memory Game", C_WHITE, 1);
            display_hline(16, C_ACCENT);
            {char buf[16]; snprintf(buf,16,"Level %d",_seqLen); display_text(10,18,buf,C_TEAL,1);}
            break;

        case MS_FAIL:
            if (now - _stateMs < 1200) {
                display_centered_text(136, "Wrong! Game over", C_RED, 1);
                return;
            }
            _result.completed = true;
            _result.duration_ms = millis() - _startMs;
            _result.seq_len = _seqLen;
            _state = MS_DONE; _done = true;
            break;

        case MS_WIN:
            if (now - _stateMs < 1500) {
                display_centered_text(70, "You win!", C_GREEN, 2);
                return;
            }
            _result.completed = true;
            _result.duration_ms = millis() - _startMs;
            _result.seq_len = _seqLen;
            _state = MS_DONE; _done = true;
            break;

        default: break;
    }
}

bool memory_game_done() { return _done; }
const MemoryResult& memory_game_result() { return _result; }
void memory_game_reset() { _state = MS_IDLE; _done = false; }

