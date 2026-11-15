"""
ALVI Hardware Store — SQLite-backed persistence for hardware events, devices, sessions, and settings.
Database file: hardware_events.db in project root.
"""
import json
import sqlite3
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Database path: project root / hardware_events.db
_DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent.parent / "hardware_events.db"
_override_db_path: Optional[Path] = None


def get_db_path() -> Path:
    """Return active database path, honoring test overrides or environment variables."""
    if _override_db_path is not None:
        return _override_db_path
    if "ALVI_HARDWARE_DB_PATH" in os.environ:
        return Path(os.environ["ALVI_HARDWARE_DB_PATH"])
    return _DEFAULT_DB_PATH


def set_db_path(path: Path | str):
    """Override database path (used by automated tests to ensure complete isolation)."""
    global _override_db_path
    _override_db_path = Path(path)


def reset_db_path():
    """Reset database path back to default."""
    global _override_db_path
    _override_db_path = None


# Backward-compatible attribute for modules referencing _DB_PATH
class _DBPathProxy:
    def __fspath__(self):
        return str(get_db_path())
    def __str__(self):
        return str(get_db_path())
    @property
    def parent(self):
        return get_db_path().parent

_DB_PATH = _DBPathProxy()


@contextmanager
def _get_conn():
    conn = sqlite3.connect(str(get_db_path()))
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    """Create all hardware tables if they don't already exist."""
    with _get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS hw_devices (
                device_id TEXT PRIMARY KEY,
                device_name TEXT,
                paired_at TEXT,
                last_seen TEXT
            );

            CREATE TABLE IF NOT EXISTS hw_events (
                event_id TEXT PRIMARY KEY,
                device_id TEXT,
                activity_id TEXT,
                session_id TEXT,
                msg_type TEXT,
                payload TEXT,
                received_at TEXT,
                synced INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS hw_sessions (
                session_id TEXT PRIMARY KEY,
                device_id TEXT,
                activity_id TEXT,
                started_at TEXT,
                ended_at TEXT,
                summary TEXT
            );

            CREATE TABLE IF NOT EXISTS hw_settings (
                device_id TEXT PRIMARY KEY,
                settings TEXT
            );

            CREATE TABLE IF NOT EXISTS neuropen_assessments (
                assessment_id TEXT PRIMARY KEY,
                session_id TEXT,
                device_id TEXT,
                created_at TEXT,
                image_path TEXT,
                annotated_image_path TEXT,
                video_path TEXT,
                duration_sec REAL,
                clock_detected INTEGER,
                circle_detected INTEGER,
                circle_score REAL,
                hands_detected INTEGER,
                estimated_time TEXT,
                is_11_10_approx INTEGER,
                digits_detected_count INTEGER,
                video_motion_summary TEXT,
                quality_warnings TEXT,
                digit_note TEXT,
                raw_metrics TEXT
            );
        """)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Devices ──────────────────────────────────────────────────────────────────

def register_device(device_id: str, device_name: str) -> dict:
    """Register a new device or update an existing one; returns device row."""
    now = _now_iso()
    with _get_conn() as conn:
        existing = conn.execute(
            "SELECT * FROM hw_devices WHERE device_id = ?", (device_id,)
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE hw_devices SET device_name = ?, last_seen = ? WHERE device_id = ?",
                (device_name, now, device_id),
            )
            paired_at = existing["paired_at"]
        else:
            paired_at = now
            conn.execute(
                "INSERT INTO hw_devices (device_id, device_name, paired_at, last_seen) VALUES (?, ?, ?, ?)",
                (device_id, device_name, paired_at, now),
            )
    return {
        "device_id": device_id,
        "device_name": device_name,
        "paired_at": paired_at,
        "last_seen": now,
    }


def get_device(device_id: str) -> Optional[dict]:
    """Return device dict or None if not found."""
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM hw_devices WHERE device_id = ?", (device_id,)
        ).fetchone()
    return dict(row) if row else None


def update_device_seen(device_id: str):
    """Touch last_seen timestamp for a device."""
    now = _now_iso()
    with _get_conn() as conn:
        conn.execute(
            "UPDATE hw_devices SET last_seen = ? WHERE device_id = ?",
            (now, device_id),
        )


# ── Events ────────────────────────────────────────────────────────────────────

def store_event(
    event_id: str,
    device_id: str,
    activity_id: str,
    session_id: str,
    msg_type: str,
    payload_dict: dict,
) -> bool:
    """
    Insert a hardware event. Returns False if event_id already exists (duplicate),
    True on successful insert.
    """
    received_at = _now_iso()
    payload_json = json.dumps(payload_dict)
    try:
        with _get_conn() as conn:
            conn.execute(
                """INSERT INTO hw_events
                   (event_id, device_id, activity_id, session_id, msg_type, payload, received_at, synced)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 0)""",
                (event_id, device_id, activity_id, session_id, msg_type, payload_json, received_at),
            )
        return True
    except sqlite3.IntegrityError:
        return False  # duplicate event_id


def get_events(device_id: Optional[str] = None, limit: int = 50) -> list[dict]:
    """Return up to `limit` events, optionally filtered by device_id, newest first."""
    with _get_conn() as conn:
        if device_id:
            rows = conn.execute(
                "SELECT * FROM hw_events WHERE device_id = ? ORDER BY received_at DESC LIMIT ?",
                (device_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM hw_events ORDER BY received_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
    result = []
    for row in rows:
        d = dict(row)
        try:
            d["payload"] = json.loads(d["payload"]) if d["payload"] else {}
        except (json.JSONDecodeError, TypeError):
            d["payload"] = {}
        result.append(d)
    return result


def get_latest_event_by_type(device_id: str, msg_type: str) -> Optional[dict]:
    """Return the most recent event for a given device and message type."""
    with _get_conn() as conn:
        row = conn.execute(
            """SELECT * FROM hw_events
               WHERE device_id = ? AND msg_type = ?
               ORDER BY received_at DESC LIMIT 1""",
            (device_id, msg_type),
        ).fetchone()
    if not row:
        return None
    d = dict(row)
    try:
        d["payload"] = json.loads(d["payload"]) if d["payload"] else {}
    except (json.JSONDecodeError, TypeError):
        d["payload"] = {}
    return d


# ── Sessions ──────────────────────────────────────────────────────────────────

def get_sessions(device_id: Optional[str] = None, limit: int = 20) -> list[dict]:
    """Return up to `limit` sessions, optionally filtered by device_id, newest first."""
    with _get_conn() as conn:
        if device_id:
            rows = conn.execute(
                "SELECT * FROM hw_sessions WHERE device_id = ? ORDER BY started_at DESC LIMIT ?",
                (device_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM hw_sessions ORDER BY started_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
    result = []
    for row in rows:
        d = dict(row)
        try:
            d["summary"] = json.loads(d["summary"]) if d["summary"] else {}
        except (json.JSONDecodeError, TypeError):
            d["summary"] = {}
        result.append(d)
    return result


def get_session(session_id: str) -> Optional[dict]:
    """Return a single session dict or None."""
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM hw_sessions WHERE session_id = ?", (session_id,)
        ).fetchone()
    if not row:
        return None
    d = dict(row)
    try:
        d["summary"] = json.loads(d["summary"]) if d["summary"] else {}
    except (json.JSONDecodeError, TypeError):
        d["summary"] = {}
    return d


def upsert_session(session_id: str, device_id: str, activity_id: str, summary_dict: dict):
    """Insert or update a session record."""
    now = _now_iso()
    summary_json = json.dumps(summary_dict)
    with _get_conn() as conn:
        existing = conn.execute(
            "SELECT session_id FROM hw_sessions WHERE session_id = ?", (session_id,)
        ).fetchone()
        if existing:
            conn.execute(
                """UPDATE hw_sessions
                   SET device_id = ?, activity_id = ?, ended_at = ?, summary = ?
                   WHERE session_id = ?""",
                (device_id, activity_id, now, summary_json, session_id),
            )
        else:
            conn.execute(
                """INSERT INTO hw_sessions
                   (session_id, device_id, activity_id, started_at, ended_at, summary)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (session_id, device_id, activity_id, now, now, summary_json),
            )


# ── Settings ──────────────────────────────────────────────────────────────────

def get_settings(device_id: str) -> dict:
    """Return settings dict for a device; returns {} if not found."""
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT settings FROM hw_settings WHERE device_id = ?", (device_id,)
        ).fetchone()
    if not row or not row["settings"]:
        return {}
    try:
        return json.loads(row["settings"])
    except (json.JSONDecodeError, TypeError):
        return {}


def save_settings(device_id: str, settings_dict: dict):
    """Insert or update settings for a device."""
    settings_json = json.dumps(settings_dict)
    with _get_conn() as conn:
        conn.execute(
            """INSERT INTO hw_settings (device_id, settings) VALUES (?, ?)
               ON CONFLICT(device_id) DO UPDATE SET settings = excluded.settings""",
            (device_id, settings_json),
        )


# ── NeuroPen Assessments ──────────────────────────────────────────────────────

def save_neuropen_assessment(
    assessment_id: str,
    session_id: str,
    device_id: str,
    image_path: Optional[str] = None,
    annotated_image_path: Optional[str] = None,
    video_path: Optional[str] = None,
    duration_sec: float = 0.0,
    clock_detected: bool = False,
    circle_detected: bool = False,
    circle_score: float = 0.0,
    hands_detected: int = 0,
    estimated_time: str = "Unable to determine",
    is_11_10_approx: Optional[bool] = None,
    digits_detected_count: int = 0,
    video_motion_summary: Optional[dict] = None,
    quality_warnings: Optional[list] = None,
    digit_note: Optional[str] = None,
    raw_metrics: Optional[dict] = None,
) -> dict:
    """Persist a completed NeuroPen Clock Drawing Assessment."""
    now = _now_iso()
    vm_json = json.dumps(video_motion_summary or {})
    qw_json = json.dumps(quality_warnings or [])
    raw_json = json.dumps(raw_metrics or {})
    is_11_10_val = 1 if is_11_10_approx is True else (0 if is_11_10_approx is False else None)

    with _get_conn() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO neuropen_assessments (
                assessment_id, session_id, device_id, created_at,
                image_path, annotated_image_path, video_path, duration_sec,
                clock_detected, circle_detected, circle_score,
                hands_detected, estimated_time, is_11_10_approx,
                digits_detected_count, video_motion_summary, quality_warnings,
                digit_note, raw_metrics
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                assessment_id, session_id, device_id, now,
                image_path, annotated_image_path, video_path, duration_sec,
                1 if clock_detected else 0, 1 if circle_detected else 0, circle_score,
                hands_detected, estimated_time, is_11_10_val,
                digits_detected_count, vm_json, qw_json,
                digit_note, raw_json
            ),
        )
    return {
        "assessment_id": assessment_id,
        "session_id": session_id,
        "device_id": device_id,
        "created_at": now,
        "duration_sec": duration_sec,
        "clock_detected": clock_detected,
        "circle_detected": circle_detected,
        "circle_score": circle_score,
        "hands_detected": hands_detected,
        "estimated_time": estimated_time,
        "is_11_10_approx": is_11_10_approx,
        "digits_detected_count": digits_detected_count,
        "quality_warnings": quality_warnings or [],
        "digit_note": digit_note,
        "annotated_image_path": annotated_image_path,
        "image_path": image_path,
        "video_path": video_path,
    }


def get_neuropen_assessments(limit: int = 20, device_id: Optional[str] = None) -> list[dict]:
    """Retrieve recent NeuroPen assessments, optionally filtered by device."""
    with _get_conn() as conn:
        if device_id:
            rows = conn.execute(
                """SELECT * FROM neuropen_assessments WHERE device_id = ?
                   ORDER BY created_at DESC LIMIT ?""",
                (device_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT * FROM neuropen_assessments ORDER BY created_at DESC LIMIT ?""",
                (limit,),
            ).fetchall()

    results = []
    for r in rows:
        d = dict(r)
        d["clock_detected"] = bool(d["clock_detected"])
        d["circle_detected"] = bool(d["circle_detected"])
        if d["is_11_10_approx"] is not None:
            d["is_11_10_approx"] = bool(d["is_11_10_approx"])
        try:
            d["video_motion_summary"] = json.loads(d["video_motion_summary"]) if d["video_motion_summary"] else {}
        except Exception:
            d["video_motion_summary"] = {}
        try:
            d["quality_warnings"] = json.loads(d["quality_warnings"]) if d["quality_warnings"] else []
        except Exception:
            d["quality_warnings"] = []
        try:
            d["raw_metrics"] = json.loads(d["raw_metrics"]) if d["raw_metrics"] else {}
        except Exception:
            d["raw_metrics"] = {}
        results.append(d)
    return results


def get_neuropen_assessment(assessment_id: Optional[str] = None, session_id: Optional[str] = None) -> Optional[dict]:
    """Retrieve single NeuroPen assessment by assessment_id or session_id."""
    with _get_conn() as conn:
        if assessment_id:
            row = conn.execute(
                "SELECT * FROM neuropen_assessments WHERE assessment_id = ?", (assessment_id,)
            ).fetchone()
        elif session_id:
            row = conn.execute(
                "SELECT * FROM neuropen_assessments WHERE session_id = ? ORDER BY created_at DESC LIMIT 1",
                (session_id,),
            ).fetchone()
        else:
            return None

    if not row:
        return None
    d = dict(row)
    d["clock_detected"] = bool(d["clock_detected"])
    d["circle_detected"] = bool(d["circle_detected"])
    if d["is_11_10_approx"] is not None:
        d["is_11_10_approx"] = bool(d["is_11_10_approx"])
    try:
        d["video_motion_summary"] = json.loads(d["video_motion_summary"]) if d["video_motion_summary"] else {}
    except Exception:
        d["video_motion_summary"] = {}
    try:
        d["quality_warnings"] = json.loads(d["quality_warnings"]) if d["quality_warnings"] else []
    except Exception:
        d["quality_warnings"] = []
    try:
        d["raw_metrics"] = json.loads(d["raw_metrics"]) if d["raw_metrics"] else {}
    except Exception:
        d["raw_metrics"] = {}
    return d
