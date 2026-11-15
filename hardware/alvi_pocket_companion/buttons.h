#pragma once
// ============================================================
// buttons.h — 4-Button Debounce & Press Detection
// ============================================================
#include <Arduino.h>
#include "pins.h"

enum ButtonId { BTN_ID_NONE=0, BTN_ID_BACK=1, BTN_ID_UP=2, BTN_ID_DOWN=3, BTN_ID_SELECT=4 };
enum PressType { PRESS_NONE=0, PRESS_SHORT=1, PRESS_LONG=2 };

struct ButtonEvent {
    ButtonId btn;
    PressType type;
};

void     buttons_init();
ButtonEvent buttons_read();   // call every loop iteration, returns event or NONE
bool     button_held(ButtonId id); // true while physically pressed
void     buttons_update();
bool     button_just_pressed(ButtonId id);
bool     button_long_pressed(ButtonId id);

