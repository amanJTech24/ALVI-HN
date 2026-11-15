"""
Entry point: python -m backend.hardware.bridge_service [--port COM8] [--baud 115200]
Auto-detects ESP32 CP210x/CH340 when port is omitted or 'auto'.
"""
import argparse
import logging
import sys
import serial.tools.list_ports as lp
from backend.hardware.serial_bridge import SerialBridge


def detect_esp32_port() -> str | None:
    """Scan for CP210x, CH340, or ESP32 USB-to-UART bridge."""
    for p in lp.comports():
        desc = (p.description or "").lower()
        hwid = (p.hwid or "").lower()
        if "cp210" in desc or "cp210" in hwid or "10c4:ea60" in hwid:
            return p.device
        if "ch340" in desc or "ch341" in desc or "1a86:7523" in hwid:
            return p.device
        if "esp32" in desc or "uart" in desc:
            return p.device
    ports = list(lp.comports())
    return ports[0].device if ports else None


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    p = argparse.ArgumentParser(description="ALVI Hardware Serial Bridge")
    p.add_argument("--port", default="auto", help="Serial port, e.g. COM8 or /dev/ttyUSB0 (default: auto)")
    p.add_argument("--baud", type=int, default=115200)
    p.add_argument("--backend", default="http://127.0.0.1:8765", help="Backend URL")
    p.add_argument("--list-ports", action="store_true", help="List available serial ports and exit")
    p.add_argument("--debug", action="store_true", help="Enable verbose debug logging")
    args = p.parse_args()

    if getattr(args, "debug", False):
        logging.getLogger().setLevel(logging.DEBUG)

    if args.list_ports:
        print("Available serial ports:")
        for pt in lp.comports():
            print(f"  {pt.device}: {pt.description} [{pt.hwid}]")
        return

    port = args.port
    if port == "auto" or not port:
        port = detect_esp32_port()
        if not port:
            logging.error("No serial ports detected. Connect ESP32 via USB and re-run.")
            sys.exit(1)
        logging.info(f"Auto-detected hardware port: {port}")

    bridge = SerialBridge(port, args.baud, args.backend, debug=getattr(args, "debug", False))
    logging.info(f"Starting bridge on {port} @ {args.baud} baud → {args.backend}")
    try:
        bridge.run()
    except KeyboardInterrupt:
        bridge.stop()
        logging.info("Bridge stopped.")


if __name__ == "__main__":
    main()
