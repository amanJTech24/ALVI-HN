"""
ALVI MindPlay Cognitive Games Analytics & Regression Test Suite
Validates:
1. Game catalog retrieval (GET /api/games/catalog)
2. Perfect game performance (100% composite score)
3. Partial game performance
4. Incorrect / zero responses
5. Empty / abandoned game sessions
6. Invalid sequence inputs handling
7. Reaction latency variations (sub-physiological, optimal, prolonged)
8. Weighting formula mathematical fidelity (35% Ch1, 35% Ch2, 30% Ch3)
9. Personal history trajectory analytics (baseline, delta, variability)
10. Insufficient history handling (< 2 sessions)
11. Pydantic boundary validation
12. Phase 5 Voice Check-in preservation
13. Phase 6 Story Recall preservation
"""

import io
import unittest
from fastapi.testclient import TestClient

from backend.main import app


class TestMindPlayGames(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    # ── 1. Catalog Endpoint ───────────────────────────────────────────────────
    def test_01_games_catalog(self):
        """GET /api/games/catalog returns metadata for all 3 challenges."""
        response = self.client.get("/api/games/catalog")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get("status"), "success")
        challenges = data.get("challenges", {})
        self.assertIn("ch1_remember", challenges)
        self.assertIn("ch2_sequence", challenges)
        self.assertIn("ch3_find", challenges)
        self.assertEqual(challenges["ch1_remember"]["total_targets"], 2)
        self.assertEqual(challenges["ch2_sequence"]["total_events"], 5)
        self.assertEqual(challenges["ch3_find"]["target_item"], "umbrella")

    # ── 2. Perfect Game Performance ───────────────────────────────────────────
    def test_02_perfect_game_performance(self):
        """All 3 challenges completed with target selections and prompt latency."""
        payload = {
            "session_id": "test_session_perfect",
            "ch1_selected": ["umbrella", "apples"],
            "ch2_sequence": [1, 2, 3, 4, 5],
            "ch3_selected": "umbrella",
            "ch3_reaction_ms": 1850.0,
            "total_time_seconds": 16.4
        }
        response = self.client.post("/api/games/submit", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]

        self.assertEqual(data["composite_score"], 100.0)
        self.assertEqual(data["performance_band"], "High Performance")
        self.assertEqual(data["perfect_tasks_count"], 3)
        self.assertEqual(data["summary_card"]["recall_accuracy"], "2/2")
        self.assertEqual(data["summary_card"]["sequence_status"], "Correct")
        self.assertIn("disclaimer", data)

    # ── 3. Partial Performance ────────────────────────────────────────────────
    def test_03_partial_performance(self):
        """1 target in Ch1, 1 inversion in Ch2, correct target in Ch3."""
        payload = {
            "ch1_selected": ["umbrella"],  # 1 of 2 targets (50% for Ch1)
            "ch2_sequence": [1, 3, 2, 4, 5],  # 1 inversion out of 10 pairs (90% for Ch2)
            "ch3_selected": "umbrella",
            "ch3_reaction_ms": 2500.0,  # ~95% for Ch3
            "total_time_seconds": 22.0
        }
        response = self.client.post("/api/games/submit", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]

        # Expected: 0.35*50 + 0.35*90 + 0.30*95 = 17.5 + 31.5 + 28.5 = 77.5
        self.assertGreaterEqual(data["composite_score"], 65.0)
        self.assertLess(data["composite_score"], 85.0)
        self.assertEqual(data["performance_band"], "Moderate Performance")

    # ── 4. Incorrect Responses & Distractor Penalties ──────────────────────────
    def test_04_incorrect_responses(self):
        """Distractors selected in Ch1, reversed order in Ch2, wrong card in Ch3."""
        payload = {
            "ch1_selected": ["bicycle", "books"],  # Only distractors (-1 penalty -> 0 points)
            "ch2_sequence": [5, 4, 3, 2, 1],  # 10 inversions (0% sequence score)
            "ch3_selected": "raincoat",  # Distractor (0% find score)
            "ch3_reaction_ms": 3200.0,
            "total_time_seconds": 35.0
        }
        response = self.client.post("/api/games/submit", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]

        self.assertEqual(data["composite_score"], 0.0)
        self.assertEqual(data["performance_band"], "Low / Incomplete Performance")
        self.assertEqual(data["perfect_tasks_count"], 0)

    # ── 5. Empty / Abandoned Session ──────────────────────────────────────────
    def test_05_empty_abandoned_session(self):
        """Unanswered challenges evaluate safely without crashes."""
        payload = {
            "ch1_selected": [],
            "ch2_sequence": [],
            "ch3_selected": None,
            "ch3_reaction_ms": None,
            "total_time_seconds": 5.0
        }
        response = self.client.post("/api/games/submit", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]

        self.assertEqual(data["composite_score"], 0.0)
        self.assertEqual(data["challenges"]["ch1_remember"]["accuracy_pct"], 0.0)
        self.assertEqual(data["challenges"]["ch2_sequence"]["accuracy_pct"], 0.0)
        self.assertEqual(data["challenges"]["ch3_find"]["accuracy_pct"], 0.0)

    # ── 6. Invalid Sequence Input Handling ────────────────────────────────────
    def test_06_invalid_sequence_handling(self):
        """Malformed sequence items handled gracefully."""
        payload = {
            "ch1_selected": ["umbrella", "apples"],
            "ch2_sequence": [1, 2, "invalid_id", 99],
            "ch3_selected": "umbrella",
            "ch3_reaction_ms": 2000.0
        }
        response = self.client.post("/api/games/submit", json=payload)
        self.assertEqual(response.status_code, 200)
        ch2 = response.json()["data"]["challenges"]["ch2_sequence"]
        self.assertFalse(ch2["is_correct"])
        self.assertEqual(ch2["score"], 0.0)

    # ── 7. Reaction Latency Variations ────────────────────────────────────────
    def test_07_reaction_time_variations(self):
        """Evaluates sub-physiological, optimal, and prolonged latencies."""
        # Sub-physiological (< 150 ms)
        res_anticipatory = self.client.post("/api/games/submit", json={
            "ch1_selected": ["umbrella", "apples"],
            "ch2_sequence": [1, 2, 3, 4, 5],
            "ch3_selected": "umbrella",
            "ch3_reaction_ms": 50.0  # Impractically fast
        }).json()["data"]["challenges"]["ch3_find"]
        self.assertEqual(res_anticipatory["latency_band"], "Anticipatory / Sub-physiological")

        # Optimal (< 2200 ms)
        res_optimal = self.client.post("/api/games/submit", json={
            "ch1_selected": ["umbrella", "apples"],
            "ch2_sequence": [1, 2, 3, 4, 5],
            "ch3_selected": "umbrella",
            "ch3_reaction_ms": 1600.0
        }).json()["data"]["challenges"]["ch3_find"]
        self.assertEqual(res_optimal["latency_band"], "Optimal / Prompt")
        self.assertEqual(res_optimal["latency_score"], 100.0)

        # Prolonged (> 15000 ms)
        res_prolonged = self.client.post("/api/games/submit", json={
            "ch1_selected": ["umbrella", "apples"],
            "ch2_sequence": [1, 2, 3, 4, 5],
            "ch3_selected": "umbrella",
            "ch3_reaction_ms": 18000.0
        }).json()["data"]["challenges"]["ch3_find"]
        self.assertEqual(res_prolonged["latency_band"], "Prolonged Search")
        self.assertEqual(res_prolonged["latency_score"], 10.0)

    # ── 8. Mathematical Weighting Fidelity ────────────────────────────────────
    def test_08_weighting_formula(self):
        """Verifies exact 35% / 35% / 30% contribution."""
        # Only Ch1 correct: composite should be exactly 35.0
        res1 = self.client.post("/api/games/submit", json={
            "ch1_selected": ["umbrella", "apples"],
            "ch2_sequence": [5, 4, 3, 2, 1],
            "ch3_selected": "raincoat"
        }).json()["data"]
        self.assertEqual(res1["composite_score"], 35.0)

        # Only Ch2 correct: composite should be exactly 35.0
        res2 = self.client.post("/api/games/submit", json={
            "ch1_selected": [],
            "ch2_sequence": [1, 2, 3, 4, 5],
            "ch3_selected": "raincoat"
        }).json()["data"]
        self.assertEqual(res2["composite_score"], 35.0)

    # ── 9. Longitudinal History Analytics (Multi-Session) ─────────────────────
    def test_09_multi_session_history_analytics(self):
        """POST /api/games/analyze-history computes baseline, delta, and variance."""
        sessions = [
            {"composite_score": 75.0, "total_time_seconds": 28.0, "ch3_reaction_ms": 3200.0},
            {"composite_score": 85.0, "total_time_seconds": 24.0, "ch3_reaction_ms": 2800.0},
            {"composite_score": 90.0, "total_time_seconds": 20.0, "ch3_reaction_ms": 2400.0}
        ]
        response = self.client.post("/api/games/analyze-history", json={"sessions": sessions})
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]

        self.assertTrue(data["has_baseline"])
        self.assertEqual(data["sessions_evaluated"], 3)
        self.assertEqual(data["personal_baseline"]["mean_score"], 83.3)
        self.assertEqual(data["personal_baseline"]["best_score"], 90.0)
        self.assertEqual(data["trajectory"]["score_delta"], 15.0)  # 90 - 75
        self.assertEqual(data["trajectory"]["label"], "Upward / Practice Effect")

    # ── 10. Insufficient History Handling ─────────────────────────────────────
    def test_10_insufficient_history(self):
        """Single session returns insufficient_history status without fake trends."""
        sessions = [{"composite_score": 85.0, "total_time_seconds": 22.0}]
        response = self.client.post("/api/games/analyze-history", json={"sessions": sessions})
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertFalse(data["has_baseline"])
        self.assertEqual(data["status"], "insufficient_history")
        self.assertIn("At least 2", data["message"])

    # ── 11. Request Validation (Extreme Values) ───────────────────────────────
    def test_11_request_validation(self):
        """Pydantic rejects negative or extreme out-of-bound inputs."""
        # Negative reaction time should be rejected by Pydantic ge=0.0
        response = self.client.post("/api/games/submit", json={
            "ch1_selected": ["umbrella"],
            "ch2_sequence": [1, 2, 3, 4, 5],
            "ch3_reaction_ms": -500.0
        })
        self.assertEqual(response.status_code, 422)

    # ── 12. Phase 5 Voice Check-in Regression ─────────────────────────────────
    def test_12_regression_voice_endpoints(self):
        """Verify Voice Check-in endpoints continue to function."""
        # /health
        h = self.client.get("/health")
        self.assertEqual(h.status_code, 200)
        self.assertEqual(h.json(), {"status": "healthy"})

        # / root
        r = self.client.get("/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("games_submit_endpoint", r.json())
        self.assertIn("ml_inference_endpoint", r.json())

        # /analyze receipt
        payload = {"file": ("test.wav", io.BytesIO(b"RIFFsampleWAVEfmt "), "audio/wav")}
        res = self.client.post("/analyze", files=payload)
        self.assertEqual(res.status_code, 200)

    # ── 13. Phase 6 Story Recall Regression ───────────────────────────────────
    def test_13_regression_story_recall_endpoints(self):
        """Verify Story Recall endpoints continue to function."""
        stories = self.client.get("/api/story/stories")
        self.assertEqual(stories.status_code, 200)
        self.assertGreaterEqual(stories.json()["count"], 2)

        # Story evaluation
        eval_res = self.client.post("/api/story/evaluate", json={
            "story_id": "aarav_story_v1",
            "transcript": "Aarav walked in the rain with his blue umbrella to the market."
        })
        self.assertEqual(eval_res.status_code, 200)
        self.assertEqual(eval_res.json()["status"], "success")


if __name__ == "__main__":
    unittest.main()
