"""
ALVI ML - FastAPI Integration & Endpoint Test Suite (Phase 4)
Automated verification of health checks, WAV & WebM uploads, ML feature extraction,
input validation, error handling, and temporary file lifecycle.
"""

import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from starlette.testclient import TestClient

from backend.main import app
from backend.ml.model_config import DEFAULT_MODEL_CONFIG


class TestFastAPIIntegration(unittest.TestCase):
    """End-to-end integration tests for FastAPI backend with ML inference pipeline."""

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.sample_wav_path = Path("data/dementianet/dementia/Al Pacino/AlPacino_1.wav")

        # Create a synthetic WebM test file using FFmpeg
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.sample_webm_path = Path(cls.temp_dir.name) / "synthetic_test.webm"
        wav_intermediate = Path(cls.temp_dir.name) / "temp_tone.wav"

        try:
            # 3 second 440 Hz tone
            subprocess.run(
                [
                    "ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=3",
                    "-ar", "16000", "-ac", "1", str(wav_intermediate),
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True,
            )
            subprocess.run(
                [
                    "ffmpeg", "-y", "-i", str(wav_intermediate),
                    "-c:a", "libopus", str(cls.sample_webm_path),
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True,
            )
            cls.webm_available = True
        except Exception:
            cls.webm_available = False

    @classmethod
    def tearDownClass(cls):
        cls.temp_dir.cleanup()

    def test_01_health_check(self):
        """Validates GET /health returns 200 OK and status healthy."""
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "healthy"})

    def test_02_root_endpoint(self):
        """Validates GET / returns 200 OK with model status and non-diagnostic disclaimer."""
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "online")
        self.assertIn("ml_model", data)
        self.assertEqual(data["ml_model"]["feature_count"], 79)
        self.assertIn("disclaimer", data)

    def test_03_legacy_analyze_receipt(self):
        """Validates existing POST /analyze endpoint still works for receipt acknowledgments."""
        with open(self.sample_wav_path, "rb") as f:
            file_bytes = f.read()

        response = self.client.post(
            "/analyze",
            files={"file": ("AlPacino_1.wav", io.BytesIO(file_bytes), "audio/wav")},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "received")
        self.assertIn("ml_endpoint_available", data)

    def test_04_valid_wav_upload_ml_endpoint(self):
        """Validates POST /api/voice/analyze on a real dataset WAV recording."""
        self.assertTrue(self.sample_wav_path.is_file(), f"Missing: {self.sample_wav_path}")
        with open(self.sample_wav_path, "rb") as f:
            file_bytes = f.read()

        response = self.client.post(
            "/api/voice/analyze",
            files={"file": ("AlPacino_1.wav", io.BytesIO(file_bytes), "audio/wav")},
        )
        self.assertEqual(response.status_code, 200, f"Error: {response.text}")
        data = response.json()

        self.assertEqual(data["status"], "success")
        self.assertEqual(data["filename"], "AlPacino_1.wav")
        self.assertEqual(data["acoustic_features_extracted_count"], 79)

        # Validate audio summary structure
        summary = data["audio_summary"]
        self.assertIn("duration_seconds", summary)
        self.assertIn("sample_rate_hz", summary)
        self.assertIn("voiced_f0_mean_hz", summary)
        self.assertIn("spectral_centroid_hz", summary)

        # Validate research prediction structure
        pred = data["research_prediction"]
        self.assertIn("predicted_class_id", pred)
        self.assertIn(pred["predicted_class_id"], [0, 1])
        self.assertIn(pred["predicted_label"], ["nodementia", "dementia"])
        self.assertIn("raw_model_score", pred)
        self.assertFalse(pred["is_calibrated_probability"])
        self.assertIn("disclaimer", pred)

    def test_05_valid_webm_upload_ml_endpoint(self):
        """Validates POST /api/voice/analyze on synthetic WebM audio (browser recording format)."""
        if not self.webm_available:
            self.skipTest("FFmpeg WebM generator not available in environment.")

        with open(self.sample_webm_path, "rb") as f:
            file_bytes = f.read()

        response = self.client.post(
            "/api/voice/analyze",
            files={"file": ("synthetic_test.webm", io.BytesIO(file_bytes), "audio/webm")},
        )
        self.assertEqual(response.status_code, 200, f"Error: {response.text}")
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["acoustic_features_extracted_count"], 79)
        self.assertGreaterEqual(data["audio_summary"]["duration_seconds"], 2.0)

    def test_06_empty_audio_upload_rejected(self):
        """Validates that empty audio uploads return 400 Bad Request."""
        response = self.client.post(
            "/api/voice/analyze",
            files={"file": ("empty.wav", io.BytesIO(b""), "audio/wav")},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("empty", response.json()["detail"].lower())

    def test_07_corrupted_audio_upload_rejected(self):
        """Validates that corrupt non-audio bytes return 400 Bad Request."""
        garbage_bytes = b"NOT_A_VALID_AUDIO_HEADER_DATA_1234567890" * 50
        response = self.client.post(
            "/api/voice/analyze",
            files={"file": ("corrupt.wav", io.BytesIO(garbage_bytes), "audio/wav")},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("validation failure", response.json()["detail"].lower())

    def test_08_oversized_audio_upload_rejected(self):
        """Validates that uploads exceeding 25 MB return 413 Payload Too Large."""
        oversized_bytes = b"0" * (26 * 1024 * 1024)  # 26 MB
        response = self.client.post(
            "/api/voice/analyze",
            files={"file": ("huge.wav", io.BytesIO(oversized_bytes), "audio/wav")},
        )
        self.assertEqual(response.status_code, 413)
        self.assertIn("exceeds maximum", response.json()["detail"].lower())

    def test_09_unsupported_format_rejected(self):
        """Validates that unsupported formats (e.g., .txt, .exe) return 415 Unsupported Media Type."""
        response = self.client.post(
            "/api/voice/analyze",
            files={"file": ("notes.txt", io.BytesIO(b"sample text"), "text/plain")},
        )
        self.assertEqual(response.status_code, 415)
        self.assertIn("unsupported audio format", response.json()["detail"].lower())

    def test_10_feature_schema_matches_model_metadata(self):
        """Validates that all 79 returned acoustic features match the saved metadata schema."""
        with open(self.sample_wav_path, "rb") as f:
            file_bytes = f.read()

        response = self.client.post(
            "/api/voice/analyze",
            files={"file": ("AlPacino_1.wav", io.BytesIO(file_bytes), "audio/wav")},
        )
        data = response.json()
        returned_features = list(data["acoustic_features"].keys())

        with open(DEFAULT_MODEL_CONFIG.metadata_json_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
        expected_schema = meta["feature_schema"]

        self.assertEqual(len(returned_features), len(expected_schema))
        self.assertEqual(set(returned_features), set(expected_schema))


if __name__ == "__main__":
    unittest.main()

