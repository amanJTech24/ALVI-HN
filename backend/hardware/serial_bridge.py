"""
ALVI Serial Bridge — reads JSON events from ESP32 USB serial, POSTs to backend.

Improvements over v1:
- Accepts standalone-sketch format (type/message_type) AND project format (msg_type)
- Logs every received message type for diagnostics
- Retry queue (bounded) — failed backend POSTs are retried on next successful connection
- Returns ACK with both 'cmd' AND 'type'/'message_type' fields (standalone expects 'type')
- Heartbeat tracking (last_rx timestamp)
- Reconnect loop with backoff

Run as:
    python -m backend.hardware.bridge_service --port COM8 --baud 115200
    python -m backend.hardware.bridge_service --port COM8 --baud 115200 --debug
"""
import serial
import json
import time
import requests
import threading
import argparse
import logging
from collections import deque
from datetime import datetime

RETRY_QUEUE_MAX = 50     # Match ESP32 NVS queue size
BACKEND_TIMEOUT = 5      # seconds
RECONNECT_DELAY = 3      # seconds


class SerialBridge:
    def __init__(self, port: str, baud: int = 115200,
                 backend_url: str = "http://127.0.0.1:8765",
                 debug: bool = False):
        self.port = port
        self.baud = baud
        self.backend_url = backend_url
        self.debug = debug
        self.ser = None
        self.connected = False
        self._stop = threading.Event()
        self._logger = logging.getLogger("serial_bridge")
        # Retry queue for failed backend POSTs
        self._retry_queue: deque[dict] = deque(maxlen=RETRY_QUEUE_MAX)
        # Diagnostics
        self.last_rx: datetime | None = None
        self.last_msg_type: str = ""
        self.last_event_id: str = ""
        self.error_count: int = 0
        self.success_count: int = 0

    # ------------------------------------------------------------------ #
    # Connection                                                           #
    # ------------------------------------------------------------------ #

    def connect(self) -> bool:
        """Try to open serial port. Returns True on success."""
        try:
            self.ser = serial.Serial(self.port, self.baud, timeout=1)
            self.connected = True
            self._logger.info(f"[BRIDGE] Connected to {self.port} @ {self.baud} baud")
            return True
        except Exception as e:
            self._logger.warning(f"[BRIDGE] Cannot open {self.port}: {e}")
            self.connected = False
            return False

    def disconnect(self):
        if self.ser and self.ser.is_open:
            self.ser.close()
        self.connected = False

    def send_command(self, cmd_dict: dict):
        """Send JSON command to device."""
        if self.ser and self.ser.is_open:
            line = json.dumps(cmd_dict) + "\n"
            try:
                self.ser.write(line.encode())
                if self.debug:
                    self._logger.debug(f"[BRIDGE TX] {line.strip()}")
            except Exception as e:
                self._logger.warning(f"[BRIDGE] Serial write failed: {e}")

    # ------------------------------------------------------------------ #
    # Message processing                                                   #
    # ------------------------------------------------------------------ #

    def _extract_msg_type(self, msg: dict) -> str:
        """Return effective message type regardless of field name used."""
        return msg.get("msg_type") or msg.get("type") or msg.get("message_type") or "UNKNOWN"

    def _post_to_backend(self, msg: dict) -> bool:
        """
        POST one message to the backend.
        On success: send ACK to ESP32.
        On failure: add to retry queue.
        Returns True if stored successfully.
        """
        mt = self._extract_msg_type(msg)
        try:
            resp = requests.post(
                f"{self.backend_url}/api/hardware/events",
                json=msg, timeout=BACKEND_TIMEOUT
            )
            if resp.status_code == 200:
                ack = resp.json()
                self.success_count += 1
                self.last_event_id = ack.get("event_id", "")
                if self.debug:
                    self._logger.debug(f"[BRIDGE RX OK] type={mt} ack={ack}")
                # Send ACK — enrich with 'type'/'message_type' so standalone sketch recognises it
                if "cmd" in ack or "type" in ack:
                    cmd_val = ack.get("type") or ack.get("cmd") or "SYNC_ACK"
                    ack.setdefault("type", cmd_val)
                    ack.setdefault("message_type", cmd_val)
                    self.send_command(ack)
                return True
            else:
                detail = ""
                try:
                    detail = resp.json().get("detail", resp.text[:120])
                except Exception:
                    detail = resp.text[:120]
                self._logger.warning(
                    f"[BRIDGE] Backend {resp.status_code} for type={mt}: {detail}"
                )
                self.error_count += 1
                return False
        except Exception as e:
            self._logger.error(f"[BRIDGE] Backend unreachable (type={mt}): {e}")
            self.error_count += 1
            return False

    def _process_line(self, line: str):
        """Parse and forward one JSON line to backend."""
        line = line.strip()
        if not line:
            return
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            self._logger.warning(f"[BRIDGE] Non-JSON line: {line[:80]}")
            return

        self.last_rx = datetime.utcnow()
        mt = self._extract_msg_type(msg)
        self.last_msg_type = mt
        self._logger.info(f"[BRIDGE RX] type={mt} device={msg.get('device_id','?')} event={msg.get('event_id','?')}")

        # Drain retry queue first (oldest events first) now we have connectivity
        self._drain_retry_queue()

        # Post this message
        if not self._post_to_backend(msg):
            if len(self._retry_queue) < RETRY_QUEUE_MAX:
                self._retry_queue.appendleft(msg)   # Keep ordering: append to left = latest at left
                self._logger.info(f"[BRIDGE] Queued for retry (queue size: {len(self._retry_queue)})")

    def _drain_retry_queue(self):
        """Attempt to re-post queued messages. Stop on first failure to preserve order."""
        while self._retry_queue:
            msg = self._retry_queue[-1]   # Oldest first (rightmost)
            mt = self._extract_msg_type(msg)
            self._logger.info(f"[BRIDGE] Retrying queued event type={mt}")
            if self._post_to_backend(msg):
                self._retry_queue.pop()
            else:
                break   # Will retry next time

    # ------------------------------------------------------------------ #
    # Main loop                                                            #
    # ------------------------------------------------------------------ #

    def run(self):
        """Main loop — reconnects on port loss."""
        while not self._stop.is_set():
            if not self.connected:
                if not self.connect():
                    time.sleep(RECONNECT_DELAY)
                    continue
            try:
                raw = self.ser.readline()
                if raw:
                    self._process_line(raw.decode("utf-8", errors="replace"))
            except serial.SerialException as e:
                self._logger.warning(f"[BRIDGE] Serial error: {e} — reconnecting…")
                self.disconnect()
            except Exception as e:
                self._logger.error(f"[BRIDGE] Unexpected error: {e}")

    def stop(self):
        self._stop.set()
        self.disconnect()
