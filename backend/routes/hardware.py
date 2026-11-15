"""
ALVI Hardware API Router — FastAPI endpoints for ESP32 hardware companion device.

Accepts both standalone-sketch format (type/message_type) and project format (msg_type).
"""
import time
from typing import Optional, Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, model_validator

from backend.hardware.hardware_service import HardwareService
from backend.hardware import hardware_store as store
from backend.hardware.protocol import normalize_msg_type

hardware_router = APIRouter(prefix="/api/hardware", tags=["hardware"])

# Initialise DB and service at module load
store.init_db()
hardware_service = HardwareService()


# ── Pydantic Models ────────────────────────────────────────────────────────────

class PairRequest(BaseModel):
    device_id: str
    device_name: str = "ALVI Pocket Companion"


class EventRequest(BaseModel):
    """
    Accepts both standalone-sketch format (type/message_type) and
    project format (msg_type).  At least one of msg_type/type/message_type
    must be present; the validator normalises to msg_type for downstream code.
    """
    # Project format
    msg_type: Optional[str] = None
    # Standalone-sketch format
    type: Optional[str] = None
    message_type: Optional[str] = None
    # Shared optional fields
    protocol_version: str = "1.0"
    device_id: str = ""
    event_id: str = ""
    session_id: str = ""
    activity_id: Optional[str] = None
    assessment_id: Optional[str] = None
    seq_num: int = 0
    payload: Any = {}

    @model_validator(mode="before")
    @classmethod
    def normalise_msg_type(cls, values):
        # Accept type/message_type as aliases for msg_type
        mt = values.get("msg_type") or values.get("type") or values.get("message_type")
        if not mt:
            raise ValueError("missing msg_type / type / message_type")
        values["msg_type"] = mt
        return values


class SettingsUpdate(BaseModel):
    reminder_enabled: Optional[bool] = None
    reminder_interval_min: Optional[int] = None
    device_name: Optional[str] = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@hardware_router.get("/status")
def get_hardware_status():
    """Return connection status, latest paired device, last_seen."""
    return hardware_service.get_status()


@hardware_router.get("/diagnostics")
def get_diagnostics():
    """Development diagnostics: service state, latest events, pipeline info."""
    return hardware_service.get_diagnostics()


@hardware_router.post("/pair")
def pair_device(req: PairRequest):
    """Register or update a hardware device pairing."""
    return hardware_service.pair_device(req.device_id, req.device_name)


@hardware_router.post("/events")
async def receive_event(request: Request):
    """
    Receive a hardware event from the ESP32 serial bridge.

    Accepts raw JSON body directly (bypasses strict Pydantic schema) so that
    the standalone sketch's extra fields (type, message_type, assessment_id,
    etc.) are forwarded verbatim to the service layer, which normalises them.

    Idempotent by event_id.  Returns TIME_SYNC cmd on TIME_SYNC_REQ,
    HELLO_ACK on HELLO, SYNC_ACK on other successful events.
    """
    try:
        msg = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Request body must be valid JSON")

    if not isinstance(msg, dict):
        raise HTTPException(status_code=400, detail="JSON body must be an object")

    result = hardware_service.process_event(msg)
    if result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result.get("detail", "Bad event"))
    return result


@hardware_router.get("/sessions")
def list_sessions(device_id: Optional[str] = None, limit: int = 20):
    """List recent hardware sessions, optionally filtered by device_id."""
    return hardware_service.get_recent_sessions(device_id=device_id, limit=limit)


@hardware_router.get("/sessions/{session_id}")
def get_session(session_id: str):
    """Get detailed info for a single session."""
    detail = hardware_service.get_session_detail(session_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Session not found")
    return detail


@hardware_router.get("/settings/{device_id}")
def get_settings(device_id: str):
    """Get settings for a device."""
    return hardware_service.get_device_settings(device_id)


@hardware_router.post("/settings/{device_id}")
def update_settings(device_id: str, body: SettingsUpdate):
    """Update settings for a device."""
    updates = body.model_dump(exclude_none=True)
    return hardware_service.update_device_settings(device_id, updates)


@hardware_router.get("/latest-mood/{device_id}")
def latest_mood(device_id: str):
    """Return the latest MOOD_SELECTED event for a device."""
    result = hardware_service.get_latest_mood(device_id)
    if result is None:
        raise HTTPException(status_code=404, detail="No mood event found for device")
    return result
