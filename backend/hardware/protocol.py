"""
ALVI Hardware Protocol — Python mirror of firmware JSON protocol spec.

Accepts both standalone sketch format (type/message_type fields) and
the original project format (msg_type). Both paths are normalized.
"""
from datetime import datetime
from enum import Enum
from typing import Optional

PROTOCOL_VERSION = "1.0"

# 6 authoritative mood states supported by Mini Timmy firmware
VALID_MOOD_NAMES = {"Happy", "Calm", "Tired", "Sad", "Anxious", "Okay"}
VALID_MOOD_CODES = {1, 2, 3, 4, 5, 6}

# Authoritative activity identifiers
ACTIVITY_HW_MOOD = "hw_mood"
ACTIVITY_HW_MEMORY = "hw_memory_seq"
ACTIVITY_HW_REACTION = "hw_reaction_test"
ACTIVITY_HW_NEUROPEN = "hw_neuropen"
ACTIVITY_HW_REMINDER = "hw_reminder"
ACTIVITY_HW_VOICE_STATUS = "hw_voice_status"

# Alias sets — standalone sketch uses these; we normalise them to canonical IDs
ACTIVITY_HW_MOOD_ALIASES = {"hw_mood", "hw_timmy_mood"}
ACTIVITY_HW_NEUROPEN_ALIASES = {"hw_neuropen", "hw_neuropen_clock"}

MSG_TYPE_TO_ACTIVITY = {
    # Modular-firmware naming
    "MOOD_SELECTED": ACTIVITY_HW_MOOD,
    "MEMORY_RESULT": ACTIVITY_HW_MEMORY,
    "REACTION_RESULT": ACTIVITY_HW_REACTION,
    "NEUROPEN_START": ACTIVITY_HW_NEUROPEN,
    "NEUROPEN_FINISH": ACTIVITY_HW_NEUROPEN,
    "REMINDER_EVENT": ACTIVITY_HW_REMINDER,
    "VOICE_STATUS": ACTIVITY_HW_VOICE_STATUS,
    # Standalone-sketch naming (ALVI_Pocket_NeuroPen.ino)
    "NEUROPEN_STARTED": ACTIVITY_HW_NEUROPEN,
    "NEUROPEN_FINISHED": ACTIVITY_HW_NEUROPEN,
    "NEUROPEN_CANCELLED": ACTIVITY_HW_NEUROPEN,
}


class MsgType(str, Enum):
    HELLO = "HELLO"
    DEVICE_STATUS = "DEVICE_STATUS"
    MOOD_SELECTED = "MOOD_SELECTED"
    MEMORY_RESULT = "MEMORY_RESULT"
    REACTION_RESULT = "REACTION_RESULT"
    NEUROPEN_START = "NEUROPEN_START"
    NEUROPEN_FINISH = "NEUROPEN_FINISH"
    # Standalone-sketch variants
    NEUROPEN_STARTED = "NEUROPEN_STARTED"
    NEUROPEN_FINISHED = "NEUROPEN_FINISHED"
    NEUROPEN_CANCELLED = "NEUROPEN_CANCELLED"
    REMINDER_EVENT = "REMINDER_EVENT"
    TIME_SYNC_REQ = "TIME_SYNC_REQ"
    VOICE_STATUS = "VOICE_STATUS"
    ERROR = "ERROR"


class CmdType(str, Enum):
    TIME_SYNC = "TIME_SYNC"
    SYNC_ACK = "SYNC_ACK"
    HELLO_ACK = "HELLO_ACK"
    DEVICE_ACK = "DEVICE_ACK"
    PAIR_REQUEST = "PAIR_REQUEST"
    VOICE_RESULT = "VOICE_RESULT"


REQUIRED_FIELDS = {
    # HELLO: device_name is optional (standalone sketch omits it)
    MsgType.HELLO: ["device_id"],
    MsgType.MOOD_SELECTED: ["session_id", "event_id", "payload"],
    MsgType.MEMORY_RESULT: ["session_id", "event_id", "payload"],
    MsgType.REACTION_RESULT: ["session_id", "event_id", "payload"],
    MsgType.NEUROPEN_START: ["session_id", "event_id", "payload"],
    MsgType.NEUROPEN_FINISH: ["session_id", "event_id", "payload"],
    MsgType.NEUROPEN_STARTED: ["session_id", "event_id", "payload"],
    MsgType.NEUROPEN_FINISHED: ["session_id", "event_id", "payload"],
    MsgType.NEUROPEN_CANCELLED: ["session_id", "event_id"],
}


def normalize_msg_type(msg: dict) -> str:
    """
    Return the effective msg_type from any supported field name.

    Standalone sketch (ALVI_Pocket_NeuroPen.ino) sends both 'type' and
    'message_type' but NOT 'msg_type'.  The original project format uses
    'msg_type'.  We check in preference order and also mutate the dict so
    downstream code can rely on 'msg_type' being present.
    """
    mt = msg.get("msg_type") or msg.get("type") or msg.get("message_type") or ""
    if mt and "msg_type" not in msg:
        msg["msg_type"] = mt
    return mt


def normalize_activity_id(activity_id: str) -> str:
    """Map standalone-sketch activity aliases to canonical project IDs."""
    if activity_id in ACTIVITY_HW_MOOD_ALIASES:
        return ACTIVITY_HW_MOOD
    if activity_id in ACTIVITY_HW_NEUROPEN_ALIASES:
        return ACTIVITY_HW_NEUROPEN
    return activity_id


def _is_valid_timestamp(ts) -> bool:
    """Validate numeric epoch or ISO-8601 string timestamp."""
    if ts is None:
        return True
    if isinstance(ts, (int, float)):
        # Range check: between 2017 and 2050 (seconds or milliseconds)
        return (1_500_000_000 <= ts <= 2_550_000_000) or (1_500_000_000_000 <= ts <= 2_550_000_000_000)
    if isinstance(ts, str):
        try:
            datetime.fromisoformat(ts.replace("Z", "+00:00"))
            return True
        except Exception:
            return False
    return False


def validate_message(msg: dict) -> tuple[bool, str]:
    """
    Returns (valid, error_string).

    Normalises field names before validation so both standalone-sketch
    (type/message_type) and project-format (msg_type) messages pass.
    protocol_version is optional — many real devices omit it.
    """
    if not isinstance(msg, dict):
        return False, "message must be a JSON object"

    # Normalize field names — mutates msg so downstream code is consistent
    mt = normalize_msg_type(msg)
    if not mt:
        return False, "missing msg_type / type / message_type"

    # Validate required fields (use string key since MsgType may not match enum)
    try:
        mt_enum = MsgType(mt)
        required = REQUIRED_FIELDS.get(mt_enum, [])
    except ValueError:
        required = []

    for field in required:
        if field not in msg:
            return False, f"missing required field: {field}"

    # Timestamp validation if provided at top-level or in payload
    payload = msg.get("payload")
    if "timestamp" in msg and not _is_valid_timestamp(msg.get("timestamp")):
        return False, "invalid timestamp format"
    if isinstance(payload, dict) and "timestamp" in payload and not _is_valid_timestamp(payload.get("timestamp")):
        return False, "invalid timestamp format"

    # Mood-specific validation
    if mt in (MsgType.MOOD_SELECTED, "MOOD_SELECTED"):
        if not isinstance(payload, dict):
            return False, "payload must be a JSON object for MOOD_SELECTED"
        mood_code = payload.get("mood_code")
        mood_name = payload.get("mood_name")
        if mood_code is None and mood_name is None:
            return False, "missing mood_code or mood_name in payload"
        if mood_code is not None and mood_code not in VALID_MOOD_CODES:
            return False, f"unsupported mood code: {mood_code}. Valid codes are 1..6"
        if mood_name is not None:
            normalized_mood = str(mood_name).strip().title()
            if normalized_mood not in VALID_MOOD_NAMES:
                return False, f"unsupported mood value: '{mood_name}'. Valid moods are: {', '.join(sorted(VALID_MOOD_NAMES))}"

    return True, ""


def build_time_sync(epoch_seconds: int) -> dict:
    return {"cmd": CmdType.TIME_SYNC, "type": CmdType.TIME_SYNC, "message_type": CmdType.TIME_SYNC,
            "epoch": epoch_seconds, "protocol_version": PROTOCOL_VERSION}


def build_sync_ack(event_id: str) -> dict:
    """
    Build an ACK that is understood by both standalone sketch and modular firmware.
    Standalone sketch reads j["type"] or j["message_type"] in its ack handler.
    """
    return {
        "cmd": CmdType.SYNC_ACK,
        "type": CmdType.SYNC_ACK,
        "message_type": CmdType.SYNC_ACK,
        "event_id": event_id,
        "protocol_version": PROTOCOL_VERSION,
    }


def build_hello_ack(event_id: str) -> dict:
    """HELLO_ACK — also understood by standalone sketch (checks type/message_type)."""
    return {
        "cmd": CmdType.HELLO_ACK,
        "type": CmdType.HELLO_ACK,
        "message_type": CmdType.HELLO_ACK,
        "event_id": event_id,
        "protocol_version": PROTOCOL_VERSION,
    }
