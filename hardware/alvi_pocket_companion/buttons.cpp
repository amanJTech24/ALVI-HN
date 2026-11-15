// buttons.cpp — Debounce + short/long press detection
#include "buttons.h"

#define DEBOUNCE_MS   30
#define LONG_PRESS_MS 700

struct BtnState {
    uint8_t pin;
    ButtonId id;
    bool     lastRaw;
    bool     stable;
    uint32_t lastChangeMs;
    uint32_t pressStartMs;
    bool     fired;      // long press already emitted
};

static BtnState _btns[4];
static const uint8_t _PINS[4] = {BTN_BACK, BTN_UP, BTN_DOWN, BTN_SELECT};
static const ButtonId _IDS[4]  = {BTN_ID_BACK, BTN_ID_UP, BTN_ID_DOWN, BTN_ID_SELECT};

void buttons_init() {
    for (int i = 0; i < 4; i++) {
        _btns[i] = {_PINS[i], _IDS[i], HIGH, HIGH, 0, 0, false};
        pinMode(_PINS[i], INPUT_PULLUP);
    }
}

static ButtonEvent _checkBtn(BtnState &b) {
    bool raw = (digitalRead(b.pin) == LOW); // LOW = pressed (INPUT_PULLUP)
    uint32_t now = millis();
    ButtonEvent ev = {BTN_ID_NONE, PRESS_NONE};

    if (raw != b.lastRaw) {
        b.lastChangeMs = now;
        b.lastRaw = raw;
    }

    bool debounced = (now - b.lastChangeMs >= DEBOUNCE_MS);
    if (!debounced) return ev;

    bool wasStable = b.stable;
    b.stable = raw;

    if (b.stable && !wasStable) {
        // press started
        b.pressStartMs = now;
        b.fired = false;
    } else if (!b.stable && wasStable && !b.fired) {
        // released without long press emit → short press
        ev = {b.id, PRESS_SHORT};
        return ev;
    }

    // Long press while held
    if (b.stable && !b.fired && (now - b.pressStartMs >= LONG_PRESS_MS)) {
        b.fired = true;
        ev = {b.id, PRESS_LONG};
    }
    return ev;
}

ButtonEvent buttons_read() {
    for (int i = 0; i < 4; i++) {
        ButtonEvent ev = _checkBtn(_btns[i]);
        if (ev.btn != BTN_ID_NONE) return ev;
    }
    return {BTN_ID_NONE, PRESS_NONE};
}

bool button_held(ButtonId id) {
    for (int i = 0; i < 4; i++) {
        if (_btns[i].id == id) return _btns[i].stable;
    }
    return false;
}

static ButtonEvent _cachedEvent = {BTN_ID_NONE, PRESS_NONE};

void buttons_update() {
    _cachedEvent = buttons_read();
}

bool button_just_pressed(ButtonId id) {
    if (_cachedEvent.btn == id && _cachedEvent.type != PRESS_NONE) {
        _cachedEvent.btn = BTN_ID_NONE;
        return true;
    }
    ButtonEvent ev = buttons_read();
    if (ev.btn == id && ev.type != PRESS_NONE) {
        return true;
    }
    return false;
}

bool button_long_pressed(ButtonId id) {
    if (_cachedEvent.btn == id && _cachedEvent.type == PRESS_LONG) {
        _cachedEvent.btn = BTN_ID_NONE;
        return true;
    }
    ButtonEvent ev = buttons_read();
    if (ev.btn == id && ev.type == PRESS_LONG) {
        return true;
    }
    return false;
}

