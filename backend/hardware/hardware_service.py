"""
ALVI Hardware Service — business logic layer for hardware device management.
Wraps hardware_store and protocol for use by FastAPI routes.
"""
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

from backend.hardware import hardware_store as store
from backend.hardware.protocol import (
    MsgType,
    CmdType,
    PROTOCOL_VERSION,
    validate_message,
    build_time_sync,
    build_sync_ack,
    build_hello_ack,
    normalize_activity_id,
    MSG_TYPE_TO_ACTIVITY,
)


class HardwareService:
    """Business logic for hardware device pairing, event processing, and session tracking."""

    def process_event(self, msg: dict) -> dict:
        """
        Validate, deduplicate, store, and return ack/response dict.

        Accepts both standalone-sketch format (type/message_type) and
        project format (msg_type).  validate_message() normalises the
        dict in-place before we read msg_type below.

        Returns {"status": "ok", "event_id": ..., "cmd": ...} or
                {"status": "error", "detail": ...}
        """
        valid, error = validate_message(msg)
        if not valid:
            return {"status": "error", "detail": error}

        # After validate_message(), msg["msg_type"] is guaranteed to be set
        msg_type = msg.get("msg_type", "")
        device_id = msg.get("device_id", "")
        event_id = msg.get("event_id") or str(uuid.uuid4())
        session_id = msg.get("session_id") or str(uuid.uuid4())
        payload = msg.get("payload", {})

        # Update device last-seen if we know the device
        if device_id:
            device = store.get_device(device_id)
            if device:
                store.update_device_seen(device_id)

        # Handle TIME_SYNC_REQ — respond with current epoch, no storage needed
        if msg_type in (MsgType.TIME_SYNC_REQ, "TIME_SYNC_REQ"):
            epoch = int(time.time())
            cmd = build_time_sync(epoch)
            return {"status": "ok", "event_id": event_id,
                    "cmd": cmd["cmd"], "type": cmd["cmd"], "message_type": cmd["cmd"],
                    "epoch": cmd["epoch"], "protocol_version": PROTOCOL_VERSION}

        # Handle HELLO — register/update device; return HELLO_ACK (standalone understands it)
        if msg_type in (MsgType.HELLO, "HELLO"):
            # device_name is optional — standalone sketch may omit it
            device_name = msg.get("device_name", "ALVI Pocket Companion")
            if device_id:
                store.register_device(device_id, device_name)
            ack = build_hello_ack(event_id)
            return {"status": "ok", "event_id": event_id,
                    "cmd": ack["cmd"], "type": ack["type"], "message_type": ack["message_type"],
                    "protocol_version": PROTOCOL_VERSION}

        # Determine authoritative activity_id
        activity_id = msg.get("activity_id") or ""
        if not activity_id and isinstance(payload, dict):
            activity_id = payload.get("activity_id") or ""
        if not activity_id:
            activity_id = MSG_TYPE_TO_ACTIVITY.get(str(msg_type), "hw_activity")

        # Normalise standalone-sketch aliases to canonical IDs
        activity_id = normalize_activity_id(activity_id)

        # Also store assessment_id if present (NeuroPen standalone sketch field)
        assessment_id = msg.get("assessment_id")
        if assessment_id and isinstance(payload, dict):
            payload["assessment_id"] = assessment_id

        if isinstance(payload, dict) and "activity_id" not in payload:
            payload["activity_id"] = activity_id

        # Deduplicate by event_id
        stored = store.store_event(
            event_id=event_id,
            device_id=device_id,
            activity_id=activity_id,
            session_id=session_id,
            msg_type=str(msg_type),
            payload_dict=payload if isinstance(payload, dict) else {},
        )
        if not stored:
            # Duplicate — still return ok (idempotent)
            ack = build_sync_ack(event_id)
            return {"status": "ok", "event_id": event_id,
                    "cmd": ack["cmd"], "type": ack["type"], "message_type": ack["message_type"],
                    "detail": "duplicate"}

        # Upsert session when session_id present
        if session_id:
            store.upsert_session(
                session_id=session_id,
                device_id=device_id,
                activity_id=activity_id,
                summary_dict=payload if isinstance(payload, dict) else {},
            )

        ack = build_sync_ack(event_id)
        return {
            "status": "ok",
            "event_id": event_id,
            "cmd": ack["cmd"],
            "type": ack["type"],
            "message_type": ack["message_type"],
            "protocol_version": PROTOCOL_VERSION,
        }

    def get_status(self) -> dict:
        """
        Return connection status, latest paired device, last_seen, and activity previews.
        Distinguishes API service availability ('service': 'online') from confirmed
        physical device connectivity ('connected': bool, 'status': 'connected'/'disconnected').
        """
        devices = []
        try:
            with store._get_conn() as conn:
                rows = conn.execute(
                    "SELECT * FROM hw_devices ORDER BY last_seen DESC LIMIT 10"
                ).fetchall()
                devices = [dict(r) for r in rows]
        except Exception:
            pass

        latest = devices[0] if devices else None

        # Physical connectivity check: seen within the last 60 seconds
        is_connected = False
        if latest and latest.get("last_seen"):
            try:
                last_seen_dt = datetime.fromisoformat(latest["last_seen"])
                now_dt = datetime.now(timezone.utc)
                diff = abs((now_dt - last_seen_dt).total_seconds())
                if diff <= 60:
                    is_connected = True
            except Exception:
                pass

        device_id = latest["device_id"] if latest else None
        latest_mood = self.get_latest_mood(device_id) if device_id else None
        latest_memory = self.get_latest_memory_result(device_id) if device_id else None
        latest_reaction = self.get_latest_reaction_result(device_id) if device_id else None

        return {
            "service": "online",
            "status": "connected" if is_connected else "disconnected",
            "connected": is_connected,
            "device": latest,
            "latest_device": latest,
            "paired_devices": len(devices),
            "last_seen": latest["last_seen"] if latest else None,
            "latest_mood": latest_mood,
            "latest_memory": latest_memory,
            "latest_reaction": latest_reaction,
        }

    def get_diagnostics(self) -> dict:
        """Return pipeline diagnostics for the /api/hardware/diagnostics endpoint."""
        status = self.get_status()
        events = store.get_events(limit=5)
        return {
            "service": "online",
            "device_status": status["status"],
            "connected": status["connected"],
            "paired_devices": status["paired_devices"],
            "last_seen": status["last_seen"],
            "latest_device": status.get("device"),
            "recent_events": events,
            "bridge_note": "Start serial bridge: python -m backend.hardware.bridge_service --port COM8 --baud 115200",
        }

    def pair_device(self, device_id: str, device_name: str) -> dict:
        """Register/update device, return device info."""
        return store.register_device(device_id, device_name)

    def get_recent_sessions(self, device_id: Optional[str] = None, limit: int = 20) -> list:
        return store.get_sessions(device_id=device_id, limit=limit)

    def get_session_detail(self, session_id: str) -> dict:
        session = store.get_session(session_id)
        if not session:
            return {}
        events = store.get_events(limit=100)
        session_events = [e for e in events if e.get("session_id") == session_id]
        session["events"] = session_events
        return session

    def get_device_settings(self, device_id: str) -> dict:
        return store.get_settings(device_id)

    def update_device_settings(self, device_id: str, settings: dict) -> dict:
        existing = store.get_settings(device_id)
        existing.update({k: v for k, v in settings.items() if v is not None})
        store.save_settings(device_id, existing)
        return existing

    def get_latest_mood(self, device_id: str) -> Optional[dict]:
        return store.get_latest_event_by_type(device_id, MsgType.MOOD_SELECTED)

    def get_latest_memory_result(self, device_id: str) -> Optional[dict]:
        return store.get_latest_event_by_type(device_id, MsgType.MEMORY_RESULT)

    def get_latest_reaction_result(self, device_id: str) -> Optional[dict]:
        return store.get_latest_event_by_type(device_id, MsgType.REACTION_RESULT)
