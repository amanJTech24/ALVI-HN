#pragma once
// ============================================================
// timmy.h — Mini Timmy Animated Companion
// Oval face, blinking eyes, 6 mood expressions
// Non-blocking animation using millis()
// ============================================================
#include <Adafruit_GFX.h>
#include <Adafruit_ST7735.h>

enum TimmyMood {
    MOOD_IDLE    = 0,
    MOOD_HAPPY   = 1,
    MOOD_CALM    = 2,
    MOOD_TIRED   = 3,
    MOOD_SAD     = 4,
    MOOD_ANXIOUS = 5,
    MOOD_OKAY    = 6,
    MOOD_WELCOME = 7
};

void timmy_init(Adafruit_ST7735* tft);
void timmy_set_mood(TimmyMood mood);
void timmy_update();         // call every loop() — non-blocking
void timmy_draw_full();      // force full redraw
void timmy_clear_area();     // erase Timmy from screen
const char* timmy_mood_name(TimmyMood mood);

