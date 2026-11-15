// display_ui.cpp — TFT display wrapper
#include "display_ui.h"

static Adafruit_ST7735 _tft = Adafruit_ST7735(TFT_CS, TFT_DC, TFT_RST);

void display_init(uint8_t initType) {
    _tft.initR(initType);
    _tft.setRotation(0);  // portrait
    _tft.fillScreen(C_BG);
}

void display_clear(uint16_t color) {
    _tft.fillScreen(color);
}

void display_title(const char* text, uint16_t color) {
    _tft.setTextSize(2);
    _tft.setTextColor(color);
    int16_t x = max(0, (128 - (int16_t)strlen(text)*12)/2);
    _tft.setCursor(x, 4);
    _tft.print(text);
}

void display_subtitle(const char* text, uint16_t color) {
    _tft.setTextSize(1);
    _tft.setTextColor(color);
    int16_t x = max(0, (128 - (int16_t)strlen(text)*6)/2);
    _tft.setCursor(x, 24);
    _tft.print(text);
}

void display_text(int16_t x, int16_t y, const char* text, uint16_t color, uint8_t size) {
    _tft.setTextSize(size);
    _tft.setTextColor(color);
    _tft.setCursor(x, y);
    _tft.print(text);
}

void display_hline(int16_t y, uint16_t color) {
    _tft.drawFastHLine(0, y, 128, color);
}

void display_status_bar(const char* label, uint16_t color) {
    _tft.fillRect(0, 150, 128, 10, color);
    _tft.setTextSize(1);
    _tft.setTextColor(C_BLACK);
    int16_t x = max(0, (128 - (int16_t)strlen(label)*6)/2);
    _tft.setCursor(x, 151);
    _tft.print(label);
}

void display_menu(const char** items, uint8_t count, uint8_t selected, uint8_t scrollOffset) {
    const uint8_t VISIBLE = 5;
    const int16_t ITEM_H  = 20;
    const int16_t START_Y = 36;

    for (uint8_t i = 0; i < VISIBLE && (i + scrollOffset) < count; i++) {
        uint8_t idx = i + scrollOffset;
        bool isSelected = (idx == selected);
        int16_t y = START_Y + i * ITEM_H;

        uint16_t bg = isSelected ? C_ACCENT : C_BG;
        uint16_t fg = isSelected ? C_WHITE  : C_LGRAY;
        _tft.fillRect(2, y, 124, ITEM_H - 2, bg);
        _tft.setTextSize(1);
        _tft.setTextColor(fg);
        _tft.setCursor(8, y + 6);
        if (isSelected) _tft.print("> ");
        _tft.print(items[idx]);
    }
    // Scroll indicator
    if (count > VISIBLE) {
        uint8_t barH = max((uint8_t)4, (uint8_t)(VISIBLE * ITEM_H * VISIBLE / count));
        uint8_t barY = START_Y + (scrollOffset * VISIBLE * ITEM_H / count);
        _tft.fillRect(124, START_Y, 4, VISIBLE*ITEM_H, C_GRAY);
        _tft.fillRect(124, barY, 4, barH, C_ACCENT);
    }
}

void display_progress_bar(int16_t x, int16_t y, int16_t w, int16_t h, uint8_t pct, uint16_t color) {
    _tft.drawRect(x, y, w, h, C_LGRAY);
    int16_t fill = (w-2) * pct / 100;
    if (fill > 0) _tft.fillRect(x+1, y+1, fill, h-2, color);
}

void display_centered_text(int16_t y, const char* text, uint16_t color, uint8_t size) {
    _tft.setTextSize(size);
    _tft.setTextColor(color);
    int16_t x = max(0, (128 - (int16_t)strlen(text)*6*size)/2);
    _tft.setCursor(x, y);
    _tft.print(text);
}

void display_badge(int16_t x, int16_t y, const char* text, uint16_t bg, uint16_t fg) {
    int16_t w = strlen(text)*6 + 4;
    _tft.fillRoundRect(x, y, w, 10, 3, bg);
    _tft.setTextSize(1);
    _tft.setTextColor(fg);
    _tft.setCursor(x+2, y+2);
    _tft.print(text);
}

Adafruit_ST7735& display_get_tft() { return _tft; }

void display_ui_draw_text_wrapped(const char* text, int16_t x, int16_t y, uint16_t color, uint8_t size, int16_t max_w) {
    _tft.setTextSize(size);
    _tft.setTextColor(color);
    _tft.setCursor(x, y);
    _tft.setTextWrap(true);
    _tft.print(text);
}

