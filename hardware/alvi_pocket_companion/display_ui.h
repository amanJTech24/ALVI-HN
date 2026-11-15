#pragma once
// ============================================================
// display_ui.h — TFT Wrapper & UI Helpers (128x160 ST7735)
// ============================================================
#include <Adafruit_GFX.h>
#include <Adafruit_ST7735.h>
#include "pins.h"

// Color palette (16-bit RGB565)
#define C_BLACK    0x0000
#define C_WHITE    0xFFFF
#define C_BG       0x0820   // dark navy
#define C_ACCENT   0xA81F   // purple
#define C_GREEN    0x07E0
#define C_RED      0xF800
#define C_YELLOW   0xFFE0
#define C_BLUE     0x001F
#define C_GRAY     0x7BEF
#define C_LGRAY    0xC618
#define C_TEAL     0x07FF
#define C_ORANGE   0xFC00

void display_init(uint8_t initType);
void display_clear(uint16_t color = C_BG);
void display_title(const char* text, uint16_t color = C_WHITE);
void display_subtitle(const char* text, uint16_t color = C_LGRAY);
void display_text(int16_t x, int16_t y, const char* text, uint16_t color = C_WHITE, uint8_t size = 1);
void display_hline(int16_t y, uint16_t color = C_ACCENT);
void display_status_bar(const char* label, uint16_t color = C_ACCENT);
void display_menu(const char** items, uint8_t count, uint8_t selected, uint8_t scrollOffset);
void display_progress_bar(int16_t x, int16_t y, int16_t w, int16_t h, uint8_t pct, uint16_t color);
void display_centered_text(int16_t y, const char* text, uint16_t color, uint8_t size);
void display_badge(int16_t x, int16_t y, const char* text, uint16_t bg, uint16_t fg);
Adafruit_ST7735& display_get_tft();

// Compatibility aliases for other modules
#define COLOR_BLACK   C_BLACK
#define COLOR_WHITE   C_WHITE
#define COLOR_CYAN    C_TEAL
#define COLOR_RED     C_RED
#define COLOR_GREEN   C_GREEN
#define COLOR_BLUE    C_BLUE
#define COLOR_YELLOW  C_YELLOW
#define COLOR_GRAY    C_GRAY
#define COLOR_ORANGE  C_ORANGE
#define COLOR_TEAL    C_TEAL

#define FONT_SMALL    1
#define FONT_MEDIUM   2
#define FONT_LARGE    2
#define FONT_XLARGE   3

inline void display_ui_clear(uint16_t color = C_BG) { display_clear(color); }
inline void display_ui_draw_text(const char* text, int16_t x, int16_t y, uint16_t color, uint8_t size = 1) {
    display_text(x, y, text, color, size);
}
inline void display_ui_draw_text_centered(const char* text, int16_t y, uint16_t color, uint8_t size = 1) {
    display_centered_text(y, text, color, size);
}
void display_ui_draw_text_wrapped(const char* text, int16_t x, int16_t y, uint16_t color, uint8_t size, int16_t max_w);

