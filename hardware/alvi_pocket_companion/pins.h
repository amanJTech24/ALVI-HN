#pragma once
// ============================================================
// ALVI Pocket Companion — Pin Definitions
// Board: DOIT ESP32 DevKit V1
// ============================================================
// CAUTION: GPIO6-11 are connected to internal flash — NEVER USE

// TFT Display (1.8" ST7735, 128x160, SPI/VSPI)
#define TFT_SCK    18   // VSPI CLK
#define TFT_MOSI   23   // VSPI MOSI
#define TFT_CS     21   // Chip Select
#define TFT_DC     16   // Data/Command
#define TFT_RST    17   // Reset

// Push buttons (INPUT_PULLUP, active LOW when pressed, connect to GND)
#define BTN_BACK    25
#define BTN_UP      26
#define BTN_DOWN    27
#define BTN_SELECT  32

// Status LED (220Ω resistor to GND)
#define STATUS_LED  22

// Optional active buzzer (driven HIGH for sound)
#define BUZZER_PIN  33
#define PIN_BUZZER  BUZZER_PIN

// Memory game color buttons (reuse main buttons, colors are on-screen)
// Colors: RED=1, GREEN=2, BLUE=3, YELLOW=4
#define COLOR_RED    1
#define COLOR_GREEN  2
#define COLOR_BLUE   3
#define COLOR_YELLOW 4

