# ALVI Hardware Firmware

## Canonical Standalone Sketch — Arduino IDE (Recommended for Flashing)

**Location:** `hardware/ALVI_Pocket_NeuroPen/ALVI_Pocket_NeuroPen.ino`

This is the **authoritative single-file Arduino IDE sketch** uploaded by the user and physically running on the ESP32.

### Features
1. Mini Timmy animated emotional companion (1.8" TFT ST7735)
2. Six-option mood check-in (Buttons 1–6)
3. Offline memory-sequence game
4. Offline reaction-time test
5. NeuroPen Clock Drawing Test (phase-timed via millisecond timer)
6. Daily cognitive reminders
7. USB serial synchronization (JSON protocol over 115200 baud)
8. Wi-Fi optional (not required)

### Protocol (Standalone Sketch)
Messages are sent as single JSON lines over serial (115200 baud).

| Field | Value |
|-------|-------|
| `type` | Message type string (e.g. `HELLO`, `MOOD_SELECTED`) |
| `message_type` | Same as `type` (redundant field for compatibility) |
| `device_id` | MAC-based ID: `esp32-XXXX-XXXXXXXX` |
| `event_id` | Unique UUID per event |
| `session_id` | UUID per game/activity session |
| `payload` | Activity-specific JSON object |

> **Note:** The standalone sketch sends `type` + `message_type` but NOT `msg_type`.  
> The backend `protocol.py` normalizes all three field names.

### Message Types Sent
| type | Trigger |
|------|---------|
| `HELLO` | On boot |
| `MOOD_SELECTED` | Mood check-in complete |
| `MEMORY_RESULT` | Memory game complete |
| `REACTION_RESULT` | Reaction test complete |
| `NEUROPEN_STARTED` | Clock Drawing Test begun |
| `NEUROPEN_FINISHED` | Clock Drawing Test finished |
| `NEUROPEN_CANCELLED` | Clock Drawing Test cancelled |
| `TIME_SYNC_REQ` | Requests current epoch |

### Expected ACKs from Backend
| ACK `type` | Trigger |
|------------|---------|
| `HELLO_ACK` or `SYNC_ACK` | After HELLO |
| `SYNC_ACK` | After any event |
| `TIME_SYNC` | After TIME_SYNC_REQ |

---

## Modular Multi-File Firmware (Alternative)

**Location:** `hardware/alvi_pocket_companion/alvi_pocket_companion.ino`

A modular multi-file version built by the development team.  
Uses separate `.cpp`/`.h` modules for each feature.  
May not be flashed on the physical device — confirm before using.

---

## How to Flash

1. Open `hardware/ALVI_Pocket_NeuroPen/ALVI_Pocket_NeuroPen.ino` in **Arduino IDE**
2. Install libraries: `TFT_eSPI`, `ArduinoJson`, `Preferences`
3. Board: **ESP32 Dev Module**
4. Upload Speed: **115200**
5. Flash

---

## Running the Python Serial Bridge

```powershell
cd D:\ALVIHN\ALVI_new
.\.venv\Scripts\python.exe -m backend.hardware.bridge_service --port COM8 --baud 115200
# Or with verbose diagnostics:
.\.venv\Scripts\python.exe -m backend.hardware.bridge_service --port COM8 --baud 115200 --debug
# Auto-detect port:
.\.venv\Scripts\python.exe -m backend.hardware.bridge_service --baud 115200
```
