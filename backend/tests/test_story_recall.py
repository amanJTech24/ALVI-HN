"""
ALVI Story Recall NLP & Regression Test Suite
Validates:
1. Story catalog & details endpoints
2. Perfect narrative recall
3. Paraphrase & synonym recognition
4. Partial narrative recall
5. Contradiction and negation filtering
6. Chronological event sequence & inversion penalty
7. Unrelated confabulations and narrative intrusions
8. Input validation (empty transcript, invalid story ID)
9. Phase 5 Voice Check-in regression preservation (/health, /, /analyze, /api/voice/analyze)
"""

import io
import unittest
from fastapi.testclient import TestClient

from backend.main import app


class TestStoryRecallNLP(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    # ── 1. Story Catalog & Detail Retrieval ────────────────────────────────────
    def test_01_story_catalog(self):
        """GET /api/story/stories returns standard story catalog."""
        response = self.client.get("/api/story/stories")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get("status"), "success")
        self.assertGreaterEqual(data.get("count", 0), 2)
        story_ids = [s["id"] for s in data["stories"]]
        self.assertIn("aarav_story_v1", story_ids)
        self.assertIn("ravi_market_v1", story_ids)

    def test_02_story_details(self):
        """GET /api/story/aarav_story_v1 returns stimulus text and metadata."""
        response = self.client.get("/api/story/aarav_story_v1")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["id"], "aarav_story_v1")
        self.assertIn("Aarav", data["title"])
        self.assertEqual(data["word_count"], 38)
        self.assertEqual(data["total_units"], 8)
        self.assertTrue(len(data["text"]) > 20)

    def test_03_story_not_found(self):
        """GET /api/story/{nonexistent} returns 404."""
        response = self.client.get("/api/story/nonexistent_story_999")
        self.assertEqual(response.status_code, 404)

    # ── 2. Perfect Story Recall ───────────────────────────────────────────────
    def test_04_perfect_recall(self):
        """Authoritative text achieves 100% completeness and sequence accuracy."""
        perfect_text = (
            "One rainy morning, Aarav left his home carrying a blue umbrella. "
            "He walked to the local market and bought three red apples. "
            "On his way back, he met his friend Meera and gave her one apple before returning home."
        )
        response = self.client.post(
            "/api/story/evaluate",
            json={"story_id": "aarav_story_v1", "transcript": perfect_text}
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body.get("status"), "success")
        data = body["data"]

        # Completeness & units
        self.assertEqual(data["metrics"]["completeness_score"], 100.0)
        self.assertEqual(data["metrics"]["recalled_units_count"], 8)
        self.assertEqual(data["metrics"]["sequence_accuracy_score"], 100.0)
        self.assertEqual(data["metrics"]["sequence_inversions"], 0)
        self.assertEqual(data["performance_band"], "High Recall")
        self.assertGreaterEqual(data["composite_score"], 85.0)
        self.assertIn("disclaimer", data)

    # ── 3. Paraphrased Recall ──────────────────────────────────────────────────
    def test_05_paraphrased_recall(self):
        """Paraphrases and synonyms are matched without penalty."""
        paraphrase_text = (
            "A young boy went outside during a rainy morning holding an umbrella. "
            "He went to the shop and purchased 3 apples. "
            "He bumped into his friend Mira, handed her an apple, and walked back home."
        )
        response = self.client.post(
            "/api/story/evaluate",
            json={"story_id": "aarav_story_v1", "transcript": paraphrase_text}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]

        self.assertGreaterEqual(data["metrics"]["completeness_score"], 85.0)
        self.assertIn(data["performance_band"], ["High Recall", "Moderate Recall"])
        self.assertGreaterEqual(data["composite_score"], 70.0)

    # ── 4. Partial Recall ──────────────────────────────────────────────────────
    def test_06_partial_recall(self):
        """Recalling only first portion yields partial score."""
        partial_text = "Aarav walked outside in the rain with his blue umbrella."
        response = self.client.post(
            "/api/story/evaluate",
            json={"story_id": "aarav_story_v1", "transcript": partial_text}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]

        # Only 3 facts recalled (Aarav, rain, umbrella)
        self.assertLessEqual(data["metrics"]["recalled_units_count"], 4)
        self.assertLessEqual(data["metrics"]["completeness_score"], 50.0)
        self.assertIn(data["performance_band"], ["Mild Recall Difficulty", "Low Recall / Incomplete"])

    # ── 5. Unrelated Narrative & Intrusions ───────────────────────────────────
    def test_07_unrelated_and_intrusions(self):
        """Unrelated speech with known intrusions triggers penalties."""
        intrusive_text = (
            "I rode a bicycle and drove a car to the hospital because the doctor called. "
            "Then someone stole my money and called the police."
        )
        response = self.client.post(
            "/api/story/evaluate",
            json={"story_id": "aarav_story_v1", "transcript": intrusive_text}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]

        # Zero key facts recalled
        self.assertEqual(data["metrics"]["recalled_units_count"], 0)
        self.assertEqual(data["metrics"]["completeness_score"], 0.0)
        # Intrusions detected
        self.assertGreaterEqual(data["metrics"]["intrusions_count"], 2)
        intrusions = [i["concept"] for i in data["intrusions_detected"]]
        self.assertTrue(any(c in intrusions for c in ["bicycle", "car", "hospital", "doctor", "police"]))
        self.assertEqual(data["performance_band"], "Low Recall / Incomplete")
        self.assertLessEqual(data["composite_score"], 20.0)

    # ── 6. Explicit Negations / Contradictions ────────────────────────────────
    def test_08_negation_filtering(self):
        """Negated information units are disqualified from recall credit."""
        negated_text = (
            "Aarav was not carrying an umbrella. He didn't go to any market, "
            "and he never gave an apple to anyone."
        )
        response = self.client.post(
            "/api/story/evaluate",
            json={"story_id": "aarav_story_v1", "transcript": negated_text}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]

        # Umbrella, market, and gave_apple must not be awarded
        for unit in data["information_units_detail"]:
            if unit["id"] in ("iu_umbrella", "iu_market", "iu_gave_apple"):
                self.assertFalse(
                    unit["is_matched"] and not unit["is_negated"],
                    f"Negated unit {unit['id']} should not be credited."
                )

    # ── 7. Scrambled Event Chronology ─────────────────────────────────────────
    def test_09_scrambled_chronology(self):
        """Events retold in reversed sequence incur temporal inversion penalty."""
        reversed_text = (
            "Aarav returned home. Before that, he gave Meera an apple and met her. "
            "Earlier he bought three apples at the market, walking with a blue umbrella in the rain."
        )
        response = self.client.post(
            "/api/story/evaluate",
            json={"story_id": "aarav_story_v1", "transcript": reversed_text}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]

        # High completeness, but sequence score reduced due to inversions
        self.assertGreater(data["metrics"]["sequence_inversions"], 0)
        self.assertLess(data["metrics"]["sequence_accuracy_score"], 100.0)

    # ── 8. Input Validation ───────────────────────────────────────────────────
    def test_10_empty_transcript_validation(self):
        """Empty transcript returns HTTP 400."""
        response = self.client.post(
            "/api/story/evaluate",
            json={"story_id": "aarav_story_v1", "transcript": "   "}
        )
        self.assertEqual(response.status_code, 400)

    def test_11_invalid_story_id(self):
        """Invalid story ID returns HTTP 404."""
        response = self.client.post(
            "/api/story/evaluate",
            json={"story_id": "unknown_story_id", "transcript": "Aarav walked home."}
        )
        self.assertEqual(response.status_code, 404)

    # ── 9. Phase 5 Voice Check-in Regression Tests ─────────────────────────────
    def test_12_regression_health_endpoint(self):
        """Verify GET /health remains functional."""
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "healthy"})

    def test_13_regression_root_endpoint(self):
        """Verify GET / returns ML metadata and status."""
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get("status"), "online")
        self.assertIn("ml_inference_endpoint", data)
        self.assertIn("story_evaluation_endpoint", data)

    def test_14_regression_voice_analyze_receipt(self):
        """Verify POST /analyze receipt endpoint still works."""
        file_payload = {"file": ("test_sample.wav", io.BytesIO(b"RIFFdummydataWAVEfmt "), "audio/wav")}
        response = self.client.post("/analyze", files=file_payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json().get("status"), "received")

    def test_15_regression_voice_ml_invalid_format(self):
        """Verify POST /api/voice/analyze validates extensions cleanly."""
        file_payload = {"file": ("bad_file.txt", io.BytesIO(b"Hello world"), "text/plain")}
        response = self.client.post("/api/voice/analyze", files=file_payload)
        self.assertEqual(response.status_code, 415)


if __name__ == "__main__":
    unittest.main()

