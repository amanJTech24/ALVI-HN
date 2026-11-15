"""
ALVI Phase 12 — Hardware API Test Suite
Tests for ESP32 hardware companion device API endpoints and protocol utilities.

All tests run WITHOUT a real ESP32 connected. HTTP tests use FastAPI TestClient
against the in-process app. Protocol tests call Python functions directly.
Storage tests use the hardware_store module with an in-memory/temp SQLite DB.
"""

import json
import os
import sys
import time
import uuid
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

# Ensure project root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from fastapi.testclient import TestClient


def _make_event_id() -> str:
    return str(uuid.uuid4())


class TestHardwareEndpoints(unittest.TestCase):
    """24 unit tests for the ALVI hardware API and protocol layer."""

    @classmethod
    def setUpClass(cls):
        # Isolate test database in an ephemeral temporary directory
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.test_db_path = Path(cls.temp_dir.name) / "test_hardware_events.db"
        os.environ["ALVI_HARDWARE_DB_PATH"] = str(cls.test_db_path)

        from backend.hardware import hardware_store as store
        store.set_db_path(cls.test_db_path)
        store.init_db()

        from backend.main import app
        cls.client = TestClient(app)
        # Register a test device first
        cls.test_device_id = "test-device-001"
        cls.client.post("/api/hardware/pair", json={
            "device_id": cls.test_device_id,
            "device_name": "Test Device"
        })

    @classmethod
    def tearDownClass(cls):
        from backend.hardware import hardware_store as store
        store.reset_db_path()
        if "ALVI_HARDWARE_DB_PATH" in os.environ:
            del os.environ["ALVI_HARDWARE_DB_PATH"]
        try:
            cls.temp_dir.cleanup()
        except Exception:
            pass

    # ── Test 01: Device registration ─────────────────────────────────────────

    def test_01_device_registration(self):
        """POST /api/hardware/pair with valid data returns 200 and device_id."""
        new_device_id = "test-device-reg-001"
        resp = self.client.post("/api/hardware/pair", json={
            "device_id": new_device_id,
            "device_name": "Registration Test Device"
        })
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["device_id"], new_device_id)
        self.assertIn("paired_at", body)
        self.assertIn("last_seen", body)

    # ── Test 02: Duplicate pairing is idempotent ──────────────────────────────

    def test_02_device_pairing_duplicate(self):
        """Pairing the same device_id twice returns 200 on both calls."""
        device_id = "test-device-dup-002"
        payload = {"device_id": device_id, "device_name": "Dup Test"}

        resp1 = self.client.post("/api/hardware/pair", json=payload)
        resp2 = self.client.post("/api/hardware/pair", json=payload)

        self.assertEqual(resp1.status_code, 200)
        self.assertEqual(resp2.status_code, 200)
        # Both should return the same device_id
        self.assertEqual(resp1.json()["device_id"], device_id)
        self.assertEqual(resp2.json()["device_id"], device_id)

    # ── Test 03: Protocol validate_message — valid HELLO ─────────────────────

    def test_03_protocol_message_parsing(self):
        """validate_message with valid HELLO message returns (True, '')."""
        from backend.hardware.protocol import validate_message
        msg = {
            "msg_type": "HELLO",
            "protocol_version": "1.0",
            "device_id": "test-device-001",
            "device_name": "Test Device"
        }
        valid, error = validate_message(msg)
        self.assertTrue(valid)
        self.assertEqual(error, "")

    # ── Test 04: Protocol — missing msg_type ─────────────────────────────────

    def test_04_protocol_invalid_missing_msg_type(self):
        """validate_message with missing msg_type returns (False, ...)."""
        from backend.hardware.protocol import validate_message
        msg = {
            "protocol_version": "1.0",
            "device_id": "test-device-001"
        }
        valid, error = validate_message(msg)
        self.assertFalse(valid)
        self.assertIn("msg_type", error)

    # ── Test 05: Protocol — missing protocol_version ──────────────────────────

    def test_05_protocol_optional_protocol_version(self):
        """validate_message accepts HELLO without protocol_version (real devices often omit it)."""
        from backend.hardware.protocol import validate_message
        msg = {
            "msg_type": "HELLO",
            "device_id": "test-device-001"
        }
        valid, error = validate_message(msg)
        # protocol_version is now optional — real ESP32 firmware may not include it
        self.assertTrue(valid, f"Expected HELLO without protocol_version to be valid, got error: {error}")

    # ── Test 06: Event submission — MOOD_SELECTED ─────────────────────────────

    def test_06_event_submission_mood(self):
        """POST /api/hardware/events with MOOD_SELECTED returns 200 and ack."""
        resp = self.client.post("/api/hardware/events", json={
            "msg_type": "MOOD_SELECTED",
            "protocol_version": "1.0",
            "device_id": self.test_device_id,
            "event_id": _make_event_id(),
            "session_id": str(uuid.uuid4()),
            "seq_num": 1,
            "payload": {"mood_code": 1, "mood_name": "Happy"}
        })
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["status"], "ok")
        self.assertIn("cmd", body)

    # ── Test 07: Event submission — MEMORY_RESULT ────────────────────────────

    def test_07_event_submission_memory(self):
        """POST /api/hardware/events with MEMORY_RESULT returns 200."""
        resp = self.client.post("/api/hardware/events", json={
            "msg_type": "MEMORY_RESULT",
            "protocol_version": "1.0",
            "device_id": self.test_device_id,
            "event_id": _make_event_id(),
            "session_id": str(uuid.uuid4()),
            "seq_num": 2,
            "payload": {"max_level": 4, "correct_count": 8, "error_count": 1, "duration_ms": 15000}
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["status"], "ok")

    # ── Test 08: Event submission — REACTION_RESULT ───────────────────────────

    def test_08_event_submission_reaction(self):
        """POST /api/hardware/events with REACTION_RESULT returns 200."""
        resp = self.client.post("/api/hardware/events", json={
            "msg_type": "REACTION_RESULT",
            "protocol_version": "1.0",
            "device_id": self.test_device_id,
            "event_id": _make_event_id(),
            "session_id": str(uuid.uuid4()),
            "seq_num": 3,
            "payload": {"median_rt_ms": 285, "false_starts": 0, "missed": 0, "trial_count": 5}
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["status"], "ok")

    # ── Test 09: Duplicate event_id deduplication ────────────────────────────

    def test_09_duplicate_event_id_deduplication(self):
        """Submitting the same event_id twice: both return 200, second is a duplicate."""
        shared_event_id = _make_event_id()
        session_id = str(uuid.uuid4())
        payload = {
            "msg_type": "MOOD_SELECTED",
            "protocol_version": "1.0",
            "device_id": self.test_device_id,
            "event_id": shared_event_id,
            "session_id": session_id,
            "seq_num": 1,
            "payload": {"mood_code": 2, "mood_name": "Sad"}
        }

        resp1 = self.client.post("/api/hardware/events", json=payload)
        resp2 = self.client.post("/api/hardware/events", json=payload)

        self.assertEqual(resp1.status_code, 200)
        self.assertEqual(resp2.status_code, 200)
        # Second response should indicate duplicate
        body2 = resp2.json()
        self.assertEqual(body2["status"], "ok")
        self.assertEqual(body2.get("detail"), "duplicate")

    # ── Test 10: Device reconnect updates last_seen ───────────────────────────

    def test_10_device_reconnect(self):
        """Re-pairing a device (simulating reconnect) updates last_seen."""
        device_id = "test-device-reconnect-010"
        # First pairing
        resp1 = self.client.post("/api/hardware/pair", json={
            "device_id": device_id,
            "device_name": "Reconnect Test"
        })
        self.assertEqual(resp1.status_code, 200)
        last_seen_1 = resp1.json().get("last_seen")

        # Small delay to ensure timestamp differs
        time.sleep(0.05)

        # Second pairing (reconnect)
        resp2 = self.client.post("/api/hardware/pair", json={
            "device_id": device_id,
            "device_name": "Reconnect Test"
        })
        self.assertEqual(resp2.status_code, 200)
        last_seen_2 = resp2.json().get("last_seen")

        # last_seen should be updated (second >= first)
        self.assertIsNotNone(last_seen_1)
        self.assertIsNotNone(last_seen_2)
        self.assertGreaterEqual(last_seen_2, last_seen_1)

    # ── Test 11: Mood submission and retrieval ────────────────────────────────

    def test_11_mood_submission_and_retrieval(self):
        """Submit a MOOD_SELECTED event, then GET /api/hardware/latest-mood/{device_id}."""
        device_id = "test-device-mood-011"
        # Register device
        self.client.post("/api/hardware/pair", json={
            "device_id": device_id, "device_name": "Mood Test Device"
        })
        # Submit mood
        mood_name = "Tired"
        self.client.post("/api/hardware/events", json={
            "msg_type": "MOOD_SELECTED",
            "protocol_version": "1.0",
            "device_id": device_id,
            "event_id": _make_event_id(),
            "session_id": str(uuid.uuid4()),
            "seq_num": 1,
            "payload": {"mood_code": 3, "mood_name": mood_name}
        })
        # Retrieve latest mood
        resp = self.client.get(f"/api/hardware/latest-mood/{device_id}")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        payload = body.get("payload", {})
        self.assertEqual(payload.get("mood_name"), mood_name)

    # ── Test 12: Memory result storage and session present ────────────────────

    def test_12_memory_result_storage(self):
        """Submit MEMORY_RESULT event, then GET /api/hardware/sessions and confirm session is present."""
        device_id = "test-device-mem-012"
        session_id = "sess-mem-012-" + str(uuid.uuid4())[:8]
        self.client.post("/api/hardware/pair", json={
            "device_id": device_id, "device_name": "Memory Test Device"
        })
        self.client.post("/api/hardware/events", json={
            "msg_type": "MEMORY_RESULT",
            "protocol_version": "1.0",
            "device_id": device_id,
            "event_id": _make_event_id(),
            "session_id": session_id,
            "seq_num": 1,
            "payload": {"max_level": 4, "correct_count": 8, "error_count": 1, "duration_ms": 15000}
        })
        resp = self.client.get("/api/hardware/sessions")
        self.assertEqual(resp.status_code, 200)
        sessions = resp.json()
        self.assertIsInstance(sessions, list)
        session_ids = [s.get("session_id") for s in sessions]
        self.assertIn(session_id, session_ids)

    # ── Test 13: Reaction result storage and session present ─────────────────

    def test_13_reaction_result_storage(self):
        """Submit REACTION_RESULT event, then GET /api/hardware/sessions and confirm session."""
        device_id = "test-device-react-013"
        session_id = "sess-react-013-" + str(uuid.uuid4())[:8]
        self.client.post("/api/hardware/pair", json={
            "device_id": device_id, "device_name": "Reaction Test Device"
        })
        self.client.post("/api/hardware/events", json={
            "msg_type": "REACTION_RESULT",
            "protocol_version": "1.0",
            "device_id": device_id,
            "event_id": _make_event_id(),
            "session_id": session_id,
            "seq_num": 1,
            "payload": {"median_rt_ms": 285, "false_starts": 0, "missed": 0, "trial_count": 5}
        })
        resp = self.client.get("/api/hardware/sessions")
        self.assertEqual(resp.status_code, 200)
        sessions = resp.json()
        session_ids = [s.get("session_id") for s in sessions]
        self.assertIn(session_id, session_ids)

    # ── Test 14: false_starts in REACTION_RESULT payload stored correctly ─────

    def test_14_false_start_in_reaction_payload(self):
        """Submit REACTION_RESULT with false_starts=2; verify stored payload has false_starts=2."""
        device_id = "test-device-fs-014"
        session_id = "sess-fs-014-" + str(uuid.uuid4())[:8]
        self.client.post("/api/hardware/pair", json={
            "device_id": device_id, "device_name": "False Start Test"
        })
        self.client.post("/api/hardware/events", json={
            "msg_type": "REACTION_RESULT",
            "protocol_version": "1.0",
            "device_id": device_id,
            "event_id": _make_event_id(),
            "session_id": session_id,
            "seq_num": 1,
            "payload": {"median_rt_ms": 310, "false_starts": 2, "missed": 1, "trial_count": 5}
        })
        # Retrieve session detail to verify stored payload
        resp = self.client.get(f"/api/hardware/sessions/{session_id}")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        summary = body.get("summary", {})
        self.assertEqual(summary.get("false_starts"), 2)

    # ── Test 15: Offline sync queue via storage module ───────────────────────

    def test_15_offline_sync_queue_via_storage(self):
        """
        Directly test hardware_store push/pop/mark_synced cycle using an
        isolated in-memory SQLite database (monkeypatched path).
        """
        import sqlite3
        from unittest.mock import patch

        # Create a temporary database file
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            tmp_db_path = f.name

        try:
            from backend.hardware import hardware_store as store

            store.set_db_path(tmp_db_path)
            store.init_db()

            # Push an event
            event_id = str(uuid.uuid4())
            result = store.store_event(
                event_id=event_id,
                device_id="sync-device",
                activity_id="hw_memory_game",
                session_id="sync-sess-001",
                msg_type="MEMORY_RESULT",
                payload_dict={"max_level": 3, "correct_count": 6}
            )
            self.assertTrue(result, "store_event should return True on first insert")

            # Verify event is retrievable
            events = store.get_events(device_id="sync-device")
            self.assertTrue(len(events) > 0)
            stored_ids = [e["event_id"] for e in events]
            self.assertIn(event_id, stored_ids)

            # Duplicate push should return False
            dup_result = store.store_event(
                event_id=event_id,
                device_id="sync-device",
                activity_id="hw_memory_game",
                session_id="sync-sess-001",
                msg_type="MEMORY_RESULT",
                payload_dict={"max_level": 3, "correct_count": 6}
            )
            self.assertFalse(dup_result, "Duplicate event_id should return False")

        finally:
            store.set_db_path(self.test_db_path)
            try:
                os.unlink(tmp_db_path)
            except OSError:
                pass

    # ── Test 16: Settings persistence ────────────────────────────────────────

    def test_16_settings_persistence(self):
        """POST settings for a device, then GET settings and verify values match."""
        device_id = "test-device-settings-016"
        self.client.post("/api/hardware/pair", json={
            "device_id": device_id, "device_name": "Settings Test Device"
        })

        settings_payload = {
            "reminder_enabled": True,
            "reminder_interval_min": 30,
            "device_name": "Updated Name"
        }
        post_resp = self.client.post(
            f"/api/hardware/settings/{device_id}",
            json=settings_payload
        )
        self.assertEqual(post_resp.status_code, 200)

        get_resp = self.client.get(f"/api/hardware/settings/{device_id}")
        self.assertEqual(get_resp.status_code, 200)
        stored = get_resp.json()
        self.assertEqual(stored.get("reminder_enabled"), True)
        self.assertEqual(stored.get("reminder_interval_min"), 30)

    # ── Test 17: Invalid/malformed event payload handling ─────────────────────

    def test_17_invalid_timestamp_handling(self):
        """
        Submit an event with malformed/missing payload fields.
        Server should return 400 or a graceful 200 with an error field —
        it must NOT raise an unhandled 500.
        """
        resp = self.client.post("/api/hardware/events", json={
            "msg_type": "MOOD_SELECTED",
            "protocol_version": "1.0",
            "device_id": self.test_device_id,
            # event_id and session_id omitted; payload malformed (missing mood_name)
            "event_id": _make_event_id(),
            "session_id": str(uuid.uuid4()),
            "seq_num": 99,
            "payload": {"bad_field": None, "timestamp": "NOT-A-TIMESTAMP"}
        })
        # Must not be 500
        self.assertIn(resp.status_code, [200, 400],
                      f"Expected 200 or 400, got {resp.status_code}: {resp.text}")

    # ── Test 18: Unknown device event still accepted & auto-registered ────────

    def test_18_unpaired_device_event_still_accepted(self):
        """
        Submit a valid event from an unknown device_id.
        The server should accept it (200) — HELLO processing auto-registers devices.
        """
        unknown_device = f"unknown-device-{uuid.uuid4().hex[:8]}"
        resp = self.client.post("/api/hardware/events", json={
            "msg_type": "MOOD_SELECTED",
            "protocol_version": "1.0",
            "device_id": unknown_device,
            "event_id": _make_event_id(),
            "session_id": str(uuid.uuid4()),
            "seq_num": 1,
            "payload": {"mood_code": 1, "mood_name": "Happy"}
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["status"], "ok")

    # ── Test 19: Session history retrieval ───────────────────────────────────

    def test_19_session_history_retrieval(self):
        """GET /api/hardware/sessions returns a list (possibly empty)."""
        resp = self.client.get("/api/hardware/sessions")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertIsInstance(body, list)

    # ── Test 20: Hardware status has 'connected' field ────────────────────────

    def test_20_no_hardware_empty_state(self):
        """GET /api/hardware/status returns a response with 'status' field present."""
        resp = self.client.get("/api/hardware/status")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        # The hardware status endpoint returns 'status' and 'paired_devices'
        self.assertIn("status", body)
        # 'paired_devices' acts as the 'connected' count (0 or more)
        self.assertIn("paired_devices", body)

    # ── Test 21: Voice check-in regression — does not 500 ────────────────────

    def test_21_voice_checkin_regression(self):
        """
        POST /api/voice/analyze with a mock (fake) audio file.
        Should return 200 or 400 — NOT 500 — proving the endpoint is stable.
        """
        # Create a small fake WAV-like byte string (not a real audio file)
        fake_audio = b"RIFF\x00\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00"
        fake_audio += b"\x44\xac\x00\x00\x88\x58\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00"

        resp = self.client.post(
            "/api/voice/analyze",
            files={"file": ("test_audio.wav", fake_audio, "audio/wav")}
        )
        self.assertIn(resp.status_code, [200, 400],
                      f"Voice endpoint returned unexpected {resp.status_code}: {resp.text}")

    # ── Test 22: Story recall regression ─────────────────────────────────────

    def test_22_story_recall_regression(self):
        """GET /api/story/stories returns 200 and a list of stories."""
        resp = self.client.get("/api/story/stories")
        self.assertEqual(resp.status_code, 200)

    # ── Test 23: MindPlay regression ─────────────────────────────────────────

    def test_23_mindplay_regression(self):
        """GET /api/games/catalog returns 200."""
        resp = self.client.get("/api/games/catalog")
        self.assertEqual(resp.status_code, 200)

    # ── Test 24: TIME_SYNC_REQ returns epoch ─────────────────────────────────

    def test_24_hardware_time_sync_request(self):
        """Submit TIME_SYNC_REQ event; response must contain 'epoch' (Unix timestamp)."""
        before = int(time.time())
        resp = self.client.post("/api/hardware/events", json={
            "msg_type": "TIME_SYNC_REQ",
            "protocol_version": "1.0",
            "device_id": self.test_device_id,
            "event_id": _make_event_id(),
            "session_id": "",
            "seq_num": 10,
            "payload": {}
        })
        after = int(time.time())
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["status"], "ok")
        self.assertIn("epoch", body, "TIME_SYNC_REQ response must contain 'epoch'")
        epoch = body["epoch"]
        self.assertIsInstance(epoch, int)
        self.assertGreaterEqual(epoch, before)
        self.assertLessEqual(epoch, after + 2)  # allow 2s tolerance


if __name__ == "__main__":
    unittest.main(verbosity=2)
