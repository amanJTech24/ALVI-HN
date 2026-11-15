# ALVI Pocket Companion — Wiring & Physical Assembly Guide

**Project:** ALVI — Alzheimer's Voice & Cognitive Intelligence  
**Component:** ALVI Pocket Companion / ALVI Mini Cognitive Lab (Phase 12)  
**Target Board:** DOIT ESP32 DevKit V1 (30-pin)  
**Display:** 1.8-inch 128×160 SPI TFT (ST7735 driver)

---

## 1. Bill of Materials (BOM)

| Item | Component | Specification | Quantity | Notes |
|:---:|:---|:---|:---:|:---|
| 1 | Microcontroller | ESP32 DevKit V1 (30-pin, CP2102/CH340 USB) | 1 | 2.4 GHz Wi-Fi + BLE, dual-core Tensilica LX6 |
| 2 | Display | 1.8" SPI TFT LCD (128×160, ST7735) | 1 | Red PCB / Black Tab or Blue PCB variant |
| 3 | Tactile Buttons | 6×6×5mm 4-pin momentary push buttons | 4 | BACK, UP, DOWN, SELECT |
| 4 | Resistor | 220Ω, 1/4W (carbon/metal film) | 1 | Current limiting for Status LED |
| 5 | Status LED | 3mm or 5mm Purple / Blue LED | 1 | Visual heartbeat / status indicator |
| 6 | Buzzer (Optional)| 5V/3.3V Active Piezo Buzzer | 1 | Acoustic alerts for reminders |
| 7 | Breadboard | 400-point or 830-point solderless breadboard | 1 | For prototyping before cardboard mounting |
| 8 | Jumper Wires | Male-to-Male & Male-to-Female dupont wires | ~20 | Flexible stranded jumper wires |
| 9 | USB Cable | Micro-USB to USB-A data cable | 1 | **Must support data lines**, not power-only |
| 10 | Cardboard | Reinforced double-wall corrugated cardboard | 2 panels | 24 cm × 18 cm each (see Assembly section) |
| 11 | Hinge Tape | Heavy-duty bookbinding cloth tape or duct tape | 1 roll | For spine hinge of the folio enclosure |
| 12 | Paper Pad | A5 or 15×20cm unruled notepad | 1 | For NeuroPen physical drawing pad |
| 13 | Binder Clips | 19mm or 25mm foldback clips | 2 | Secure the notepad to the lower panel |

---

## 2. Complete GPIO Pin Mapping Table

> [!CAUTION]
> **FLASH PINS PROHIBITED:** Never connect any buttons, display pins, or sensors to **GPIO6, GPIO7, GPIO8, GPIO9, GPIO10, or GPIO11**. These pins are internally connected to the integrated SPI flash memory. Using them will crash the ESP32 or prevent booting.

| Function | Pin Name | ESP32 GPIO | Electrical Mode | Wire Color Suggestion | Destination on Component |
|:---|:---:|:---:|:---:|:---:|:---|
| **TFT SPI SCK** | SCL / SCK | **GPIO 18** | Output (VSPI CLK) | Yellow | Pin `SCK` / `SCL` on TFT |
| **TFT SPI MOSI** | SDA / MOSI | **GPIO 23** | Output (VSPI MOSI) | Blue | Pin `SDA` / `MOSI` on TFT |
| **TFT Chip Select** | CS | **GPIO 21** | Output (Active LOW) | Orange | Pin `CS` on TFT |
| **TFT Data/Command** | DC / A0 | **GPIO 16** | Output (Logic High/Low) | White | Pin `DC` / `A0` on TFT |
| **TFT Reset** | RES / RST | **GPIO 17** | Output (Active LOW) | Green | Pin `RES` / `RST` on TFT |
| **TFT VCC** | VCC | **3.3V / VIN** | Power Supply | Red | Pin `VCC` on TFT *(See Voltage Warning)* |
| **TFT Ground** | GND | **GND** | Ground Reference | Black | Pin `GND` on TFT |
| **TFT Backlight** | BL / LED | **3.3V** | Power (Backlight) | Red / Orange | Pin `BL` / `LED` on TFT |
| **Button: BACK** | BTN_BACK | **GPIO 25** | `INPUT_PULLUP` | Brown | One leg to GPIO25, opposite leg to GND |
| **Button: UP** | BTN_UP | **GPIO 26** | `INPUT_PULLUP` | White | One leg to GPIO26, opposite leg to GND |
| **Button: DOWN** | BTN_DOWN | **GPIO 27** | `INPUT_PULLUP` | Gray | One leg to GPIO27, opposite leg to GND |
| **Button: SELECT** | BTN_SELECT | **GPIO 32** | `INPUT_PULLUP` | Purple | One leg to GPIO32, opposite leg to GND |
| **Status LED** | LED_PIN | **GPIO 22** | Output (via 220Ω) | Violet | Anode (+) to 220Ω to GPIO22; Cathode (-) to GND |
| **Active Buzzer** | BUZZER | **GPIO 33** | Output (Optional) | Brown | Anode (+) to GPIO33; Cathode (-) to GND |

---

## 3. Electrical & Voltage Warnings

> [!WARNING]
> **TFT Display Voltage Compatibility:**
> - Most common 1.8-inch ST7735 boards have an onboard 3.3V low-dropout regulator (LDO marked `662K` or `XC6206`). These modules can accept 5V (`VIN`) or 3.3V into `VCC`.
> - **Signal logic levels are 3.3V.** Since the ESP32 DevKit V1 outputs 3.3V CMOS logic on all GPIO pins, **no level shifters are required**.
> - If your TFT module lacks an onboard regulator and is labeled `VCC: 3.3V ONLY`, connect `VCC` **strictly to the ESP32 3.3V pin**, never to 5V/VIN!
> - Connect the Backlight pin (`BL` or `LED`) to 3.3V through a 10Ω–47Ω resistor if it lacks an onboard resistor. Most modules already include a series surface-mount resistor and can connect directly to 3.3V.

---

## 4. Step-by-Step Breadboard Prototyping

### Step 1: Seat the ESP32
1. Position the 30-pin ESP32 DevKit V1 across the center trough of the breadboard so each row of pins occupies its own isolated rail.
2. Ensure the micro-USB connector faces toward the outer edge of the board for easy cable connection.

### Step 2: Wire the Power & Ground Rails
1. Connect the ESP32 `GND` pin to the breadboard blue negative (`-`) rail.
2. Connect the ESP32 `3.3V` pin to the breadboard red positive (`+`) rail.

### Step 3: Wire the 1.8" SPI TFT Display
1. `GND` → Breadboard Ground rail
2. `VCC` → Breadboard 3.3V rail (or `VIN` if module requires 5V)
3. `SCK` / `SCL` → ESP32 **GPIO 18**
4. `SDA` / `MOSI` → ESP32 **GPIO 23**
5. `RES` / `RST` → ESP32 **GPIO 17**
6. `DC` / `A0` → ESP32 **GPIO 16**
7. `CS` → ESP32 **GPIO 21**
8. `BL` / `LED` → Breadboard 3.3V rail

### Step 4: Wire the 4 Tactile Buttons
Each button connects between its designated GPIO and ground. Internal pull-up resistors (`INPUT_PULLUP`) maintain logic HIGH when unpressed; pressing connects the pin to GND (active LOW).
1. Place 4 tactile buttons in a vertical or diamond arrangement:
   - **Top button (UP):** Pin 1 to **GPIO 26**, diagonally opposite pin to GND rail.
   - **Bottom button (DOWN):** Pin 1 to **GPIO 27**, diagonally opposite pin to GND rail.
   - **Left button (BACK):** Pin 1 to **GPIO 25**, diagonally opposite pin to GND rail.
   - **Right button (SELECT):** Pin 1 to **GPIO 32**, diagonally opposite pin to GND rail.

### Step 5: Wire the Status LED & Buzzer
1. Connect a 220Ω resistor from ESP32 **GPIO 22** to an unused breadboard row.
2. Connect the longer lead (Anode, +) of the Status LED to the resistor.
3. Connect the shorter lead (Cathode, -) of the LED to the Ground rail.
4. *(Optional)* Connect the buzzer positive (+) lead to **GPIO 33**, and the negative (-) lead to Ground.

---

## 5. Foldable Cardboard Enclosure Assembly

The ALVI Pocket Companion enclosure is designed as a portable, two-panel notebook-style folio that integrates the digital cognitive screen with the physical NeuroPen drawing pad.

```
       ┌────────────────────────┐
       │   ALVI Pocket Folio    │
       ├────────────────────────┤
       │   UPPER PANEL (24×18cm)│
       │  ┌──────────────────┐  │
       │  │  1.8" TFT Window │  │
       │  └──────────────────┘  │
       │     [UP]               │
       │ [BACK]  [SELECT]       │
       │    [DOWN]    ● LED     │
       ├════════════════════════┤ <── Fabric-tape Spine Hinge
       │   LOWER PANEL (24×18cm)│
       │  ┌──────────────────┐  │
       │  │ NeuroPen Drawing │  │
       │  │ Pad (Paper & Pen)│  │
       │  │                  │  │
       │  └──────────────────┘  │
       │    [== Binder Clip ==] │
       └────────────────────────┘
```

### Construction Steps:
1. **Prepare Panels:** Cut two rectangular panels (24 cm wide × 18 cm high) from 2mm–3mm rigid corrugated cardboard or dense foam-core board.
2. **Spine Hinge:** Align the two panels side-by-side with a 3mm gap. Apply heavy-duty fabric tape or bookbinding tape along the entire seam on both the front and back to create a flexible, durable hinge.
3. **Screen Cutout:** On the upper panel (left or top), trace the active viewing window of the 1.8" TFT (approx. 29 mm × 35 mm). Cut out the rectangular opening cleanly with a craft knife.
4. **Button Holes:** Measure and punch four 7mm circular holes arranged for ergonomic thumb access:
   - Left: BACK
   - Up: UP
   - Down: DOWN
   - Right: SELECT
5. **LED & Sound Holes:** Punch a 3mm hole for the Status LED and three pinhole perforations over the buzzer location.
6. **Component Mounting:** Secure the breadboard and TFT module to the inner face of the upper panel using non-conductive double-sided foam mounting tape. Ensure the TFT glass aligns with the cutout.
7. **USB Cable Routing:** Notch a 10mm slot on the outer edge of the upper panel to allow the micro-USB cable to route cleanly to the ESP32 without straining the connector.
8. **Electrical Insulation:** Apply electrical tape or kapton tape over any exposed metal contacts before securing the outer cover.
9. **Attach Lower Paper Pad:** Mount the unruled paper notepad to the lower panel using two metal binder clips. This serves as the physical canvas for the **NeuroPen** clock-drawing and shape-copying tasks.
10. **Finishing:** Decorate the exterior folio with ALVI purple (`#a81f` / `#7c3aed`) and white accents, labeling the buttons and display clearly.
