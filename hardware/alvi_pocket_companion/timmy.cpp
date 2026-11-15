// timmy.cpp — Mini Timmy animated companion
#include "timmy.h"
#include "display_ui.h"
#include <Arduino.h>

// Timmy center position on screen
#define T_CX    64
#define T_CY    80
#define T_RX    30    // face horizontal radius
#define T_RY    24    // face vertical radius
#define T_EY    70    // eye Y center
#define T_EL    52    // left eye X
#define T_ER    76    // right eye X
#define T_ER_   10    // eye outer radius
#define T_EP    4     // pupil radius
#define T_MX    64    // mouth center X
#define T_MY    90    // mouth Y

static Adafruit_ST7735* _tft = nullptr;
static TimmyMood _mood      = MOOD_IDLE;
static bool      _blinking  = false;
static uint32_t  _blinkTime = 0;
static uint32_t  _nextBlink = 0;
static int8_t    _glanceX   = 0;   // pupil offset
static uint32_t  _nextGlance = 0;
static bool      _needRedraw = true;

static uint16_t _faceColor()  { return C_WHITE; }
static uint16_t _outlineColor(){ return C_ACCENT; }

static void _drawEye(int16_t cx, int16_t cy, bool closed, int8_t gx) {
    // Eye socket
    _tft->fillCircle(cx, cy, T_ER_, C_WHITE);
    _tft->drawCircle(cx, cy, T_ER_, C_ACCENT);

    if (closed || _blinking) {
        // Closed: draw line
        _tft->drawFastHLine(cx - T_ER_, cy, T_ER_*2, C_ACCENT);
        _tft->drawFastHLine(cx - T_ER_, cy+1, T_ER_*2, C_ACCENT);
        return;
    }

    // Pupil with glance offset
    int16_t px = cx + gx;
    _tft->fillCircle(px, cy, T_EP, C_BLACK);
    // Highlight
    _tft->fillCircle(px + 1, cy - 1, 1, C_WHITE);
}

static void _drawMouth(TimmyMood mood) {
    // Erase old mouth
    _tft->fillRect(T_MX-18, T_MY-6, 36, 16, C_WHITE);

    switch (mood) {
        case MOOD_HAPPY:
        case MOOD_WELCOME:
            // Big smile — arc simulation via filled arcs
            for (int8_t i = -14; i <= 14; i++) {
                int16_t y = T_MY + (i*i)/20;
                _tft->drawPixel(T_MX + i, y, C_ACCENT);
                _tft->drawPixel(T_MX + i, y+1, C_ACCENT);
            }
            break;
        case MOOD_SAD:
            // Frown
            for (int8_t i = -14; i <= 14; i++) {
                int16_t y = T_MY + 8 - (i*i)/20;
                _tft->drawPixel(T_MX + i, y, C_ACCENT);
                _tft->drawPixel(T_MX + i, y+1, C_ACCENT);
            }
            break;
        case MOOD_CALM:
        case MOOD_IDLE:
            // Straight line
            _tft->drawFastHLine(T_MX-10, T_MY+4, 20, C_ACCENT);
            _tft->drawFastHLine(T_MX-10, T_MY+5, 20, C_ACCENT);
            break;
        case MOOD_TIRED:
            // Small downward curve
            for (int8_t i = -8; i <= 8; i++) {
                int16_t y = T_MY + 5 - (i*i)/20;
                _tft->drawPixel(T_MX + i, y, C_ACCENT);
            }
            break;
        case MOOD_ANXIOUS:
            // Wavy
            for (int8_t i = -12; i <= 12; i++) {
                int16_t y = T_MY + 4 + (int16_t)(2.0f * sin(i * 0.6f));
                _tft->drawPixel(T_MX + i, y, C_ACCENT);
                _tft->drawPixel(T_MX + i, y+1, C_ACCENT);
            }
            break;
        case MOOD_OKAY:
            // Slight smile
            for (int8_t i = -10; i <= 10; i++) {
                int16_t y = T_MY + 4 + (i*i)/40;
                _tft->drawPixel(T_MX + i, y, C_ACCENT);
            }
            break;
        default:
            _tft->drawFastHLine(T_MX-8, T_MY+4, 16, C_ACCENT);
    }
}

static void _drawEyebrows(TimmyMood mood) {
    // Clear eyebrow area
    _tft->fillRect(T_EL-14, T_EY-18, 60, 6, C_WHITE);

    switch (mood) {
        case MOOD_ANXIOUS:
            // Worried brows (angled inward)
            _tft->drawLine(T_EL-10, T_EY-15, T_EL+6, T_EY-12, C_ACCENT);
            _tft->drawLine(T_ER-6,  T_EY-12, T_ER+10, T_EY-15, C_ACCENT);
            break;
        case MOOD_SAD:
            _tft->drawLine(T_EL-8, T_EY-12, T_EL+8, T_EY-16, C_ACCENT);
            _tft->drawLine(T_ER-8, T_EY-16, T_ER+8, T_EY-12, C_ACCENT);
            break;
        case MOOD_HAPPY:
        case MOOD_WELCOME:
            _tft->drawLine(T_EL-10, T_EY-16, T_EL+8, T_EY-14, C_ACCENT);
            _tft->drawLine(T_ER-8,  T_EY-14, T_ER+10, T_EY-16, C_ACCENT);
            break;
        default:
            _tft->drawFastHLine(T_EL-8, T_EY-14, 16, C_ACCENT);
            _tft->drawFastHLine(T_ER-8, T_EY-14, 16, C_ACCENT);
            break;
    }
}

void timmy_init(Adafruit_ST7735* tft) {
    _tft = tft;
    _nextBlink  = millis() + random(3000, 6000);
    _nextGlance = millis() + random(5000, 10000);
}

void timmy_set_mood(TimmyMood mood) {
    if (_mood != mood) { _mood = mood; _needRedraw = true; }
}

void timmy_draw_full() {
    if (!_tft) return;
    // Face background
    _tft->fillEllipse(T_CX, T_CY, T_RX, T_RY, C_WHITE);
    _tft->drawEllipse(T_CX, T_CY, T_RX, T_RY, _outlineColor());
    _tft->drawEllipse(T_CX, T_CY, T_RX+1, T_RY+1, _outlineColor());

    _drawEyebrows(_mood);
    _drawEye(T_EL, T_EY, false, _glanceX);
    _drawEye(T_ER, T_EY, false, _glanceX);
    _drawMouth(_mood);
    _needRedraw = false;
}

void timmy_clear_area() {
    if (!_tft) return;
    _tft->fillRect(T_CX-T_RX-4, T_CY-T_RY-20, (T_RX+4)*2, (T_RY+20)*2+20, C_BG);
}

void timmy_update() {
    if (!_tft) return;
    uint32_t now = millis();

    if (_needRedraw) { timmy_draw_full(); }

    // Blink
    if (!_blinking && now >= _nextBlink) {
        _blinking  = true;
        _blinkTime = now;
        // Draw closed eyes
        _tft->fillCircle(T_EL, T_EY, T_ER_, C_WHITE);
        _tft->drawCircle(T_EL, T_EY, T_ER_, C_ACCENT);
        _tft->fillRect(T_EL-T_ER_, T_EY-1, T_ER_*2, 4, C_ACCENT);
        _tft->fillCircle(T_ER, T_EY, T_ER_, C_WHITE);
        _tft->drawCircle(T_ER, T_EY, T_ER_, C_ACCENT);
        _tft->fillRect(T_ER-T_ER_, T_EY-1, T_ER_*2, 4, C_ACCENT);
    }
    if (_blinking && now - _blinkTime >= 150) {
        _blinking   = false;
        _nextBlink  = now + random(3000, 6000);
        _needRedraw = true;
    }

    // Glance
    if (!_blinking && now >= _nextGlance) {
        static int8_t glances[] = {-3, 0, 3, 0};
        static uint8_t gi = 0;
        gi = (gi+1) % 4;
        _glanceX    = glances[gi];
        _nextGlance = now + random(4000, 9000);
        _needRedraw = true;
    }
}

const char* timmy_mood_name(TimmyMood mood) {
    switch (mood) {
        case MOOD_HAPPY:   return "Happy";
        case MOOD_CALM:    return "Calm";
        case MOOD_TIRED:   return "Tired";
        case MOOD_SAD:     return "Sad";
        case MOOD_ANXIOUS: return "Anxious";
        case MOOD_OKAY:    return "Okay";
        case MOOD_WELCOME: return "Welcome";
        default:           return "Idle";
    }
}

