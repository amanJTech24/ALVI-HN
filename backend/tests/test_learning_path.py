"""
Unit and Integration Tests for Phase 9: ALVI Cognitive Learning Path & Personalized Practice Engine.
Covers:
- Exercise catalog structure and schema validation.
- LearningRecommendationEngine starter path vs targeted recommendation rules.
- Specific opportunity triggers (Story recall, MindPlay sequence, MindPlay binding, Visual latency, Voice hesitation).
- High performance maintenance recommendations.
- Practice history rotation and adaptation.
- PracticeProgressTracker progress calculations and honest empty states.
- FastAPI endpoints: GET /api/learning/catalog, POST /api/learning/recommend, POST /api/learning/progress.
- Root endpoint verification.
"""

import unittest
from typing import Any, Dict

from fastapi.testclient import TestClient
from backend.main import app
from backend.services.learning_recommendations import (
    LearningRecommendationEngine,
    get_learning_recommendation_engine,
)
from backend.services.practice_progress import (
    PracticeProgressTracker,
    get_practice_progress_tracker,
)


class TestLearningRecommendationService(unittest.TestCase):
    """Unit tests for LearningRecommendationEngine and PracticeProgressTracker."""

    def setUp(self):
        self.engine = get_learning_recommendation_engine()
        self.tracker = get_practice_progress_tracker()

    def test_01_catalog_structure_and_schema(self):
        """Verify exercise catalog contains all 6 required practice activities."""
        catalog = self.engine.get_catalog()
        self.assertEqual(catalog["version"], "1.0.0")
        self.assertIn("exercises", catalog)
        exercises = catalog["exercises"]
        self.assertGreaterEqual(len(exercises), 6)

        required_ids = [
            "ex_narrative_retell_foundations",
            "ex_temporal_chronology_builder",
            "ex_dual_feature_binding",
            "ex_visual_search_agility",
            "ex_spontaneous_speech_description",
            "ex_full_trio_review",
        ]
        catalog_ids = [ex["exercise_id"] for ex in exercises]
        for req_id in required_ids:
            self.assertIn(req_id, catalog_ids, f"Missing required exercise: {req_id}")

        for ex in exercises:
            self.assertIn("display_name", ex)
            self.assertIn("skill_practiced", ex)
            self.assertIn("difficulty", ex)
            self.assertIn("estimated_duration", ex)
            self.assertIn("route", ex)
            self.assertTrue(ex["route"].endswith(".html"))

    def test_02_new_user_starter_path(self):
        """Verify new users with no completed assessments receive transparent starter path."""
        res = self.engine.recommend(current_session={})
        self.assertTrue(res["is_starter_path"])
        self.assertEqual(res["tasks_evaluated_count"], 0)
        self.assertIn("starter_path_note", res)
        self.assertIn("No prior check-in results were found", res["starter_path_note"])
        self.assertEqual(len(res["recommended_exercises"]), 3)

        # Starter exercises should cover voice, story, and mindplay
        starter_ids = [r["exercise_id"] for r in res["recommended_exercises"]]
        self.assertIn("ex_spontaneous_speech_description", starter_ids)
        self.assertIn("ex_narrative_retell_foundations", starter_ids)
        self.assertIn("ex_dual_feature_binding", starter_ids)

    def test_03_story_recall_only_input(self):
        """Verify recommendations when only Story Recall was administered."""
        session = {
            "story": {
                "completed": True,
                "score_percent": 50.0,
                "recalled_facts": ["aarav", "umbrella"],
                "missed_facts": ["rain", "market", "apples", "meera"],
            }
        }
        res = self.engine.recommend(current_session=session)
        self.assertFalse(res["is_starter_path"])
        self.assertEqual(res["tasks_evaluated_count"], 1)
        self.assertIn("story", res["completed_tasks"])
        self.assertGreaterEqual(len(res["recommended_exercises"]), 1)
        top_ex = res["recommended_exercises"][0]
        self.assertEqual(top_ex["exercise_id"], "ex_narrative_retell_foundations")
        self.assertEqual(top_ex["priority"], 1)
        self.assertIn("50.0% accuracy", top_ex["supporting_metric"])

    def test_04_mindplay_only_sequence_deficit(self):
        """Verify MindPlay with sequencing inversion triggers chronology practice."""
        session = {
            "mindplay": {
                "completed": True,
                "ch1_correct": True,
                "ch1_score": 2,
                "ch2_correct": False,
                "ch3_correct": True,
                "ch3_reactionMs": 1800.0,
            }
        }
        res = self.engine.recommend(current_session=session)
        self.assertFalse(res["is_starter_path"])
        self.assertEqual(res["tasks_evaluated_count"], 1)
        seq_recs = [r for r in res["recommended_exercises"] if r["exercise_id"] == "ex_temporal_chronology_builder"]
        self.assertEqual(len(seq_recs), 1)
        self.assertEqual(seq_recs[0]["priority"], 1)
        self.assertIn("transposed", seq_recs[0]["supporting_metric"].lower())

    def test_05_mindplay_only_dual_binding_deficit(self):
        """Verify MindPlay with dual binding error triggers association practice."""
        session = {
            "mindplay": {
                "completed": True,
                "ch1_correct": False,
                "ch1_score": 1,
                "ch2_correct": True,
                "ch3_correct": True,
                "ch3_reactionMs": 1900.0,
            }
        }
        res = self.engine.recommend(current_session=session)
        bind_recs = [r for r in res["recommended_exercises"] if r["exercise_id"] == "ex_dual_feature_binding"]
        self.assertEqual(len(bind_recs), 1)
        self.assertIn("1/2", bind_recs[0]["supporting_metric"])

    def test_06_mindplay_visual_latency_deficit(self):
        """Verify slow reaction latency triggers visual search practice."""
        session = {
            "mindplay": {
                "completed": True,
                "ch1_correct": True,
                "ch1_score": 2,
                "ch2_correct": True,
                "ch3_correct": True,
                "ch3_reactionMs": 4200.0,
            }
        }
        res = self.engine.recommend(current_session=session)
        lat_recs = [r for r in res["recommended_exercises"] if r["exercise_id"] == "ex_visual_search_agility"]
        self.assertEqual(len(lat_recs), 1)
        self.assertIn("4200", lat_recs[0]["supporting_metric"])

    def test_07_voice_checkin_hesitation_deficit(self):
        """Verify elevated low-energy pauses in speech triggers descriptive scene narration."""
        session = {
            "voice": {
                "completed": True,
                "durationSeconds": 20.0,
                "features": {
                    "low_energy_frame_ratio": 0.35,
                    "low_energy_interval_count": 9,
                },
            }
        }
        res = self.engine.recommend(current_session=session)
        voice_recs = [r for r in res["recommended_exercises"] if r["exercise_id"] == "ex_spontaneous_speech_description"]
        self.assertEqual(len(voice_recs), 1)
        self.assertIn("35.0%", voice_recs[0]["supporting_metric"])

    def test_08_all_assessments_high_performance_maintenance(self):
        """Verify all assessments completed with high scores recommends maintenance drills."""
        session = {
            "voice": {
                "completed": True,
                "durationSeconds": 24.0,
                "features": {
                    "low_energy_frame_ratio": 0.16,
                    "low_energy_interval_count": 4,
                },
            },
            "story": {
                "completed": True,
                "score_percent": 100.0,
                "recalled_facts": ["aarav", "rain", "umbrella", "market", "apples", "meera", "gave_apple", "home"],
                "missed_facts": [],
            },
            "mindplay": {
                "completed": True,
                "ch1_correct": True,
                "ch1_score": 2,
                "ch2_correct": True,
                "ch3_correct": True,
                "ch3_reactionMs": 1900.0,
            },
        }
        res = self.engine.recommend(current_session=session)
        self.assertFalse(res["is_starter_path"])
        self.assertEqual(res["tasks_evaluated_count"], 3)
        rec_ids = [r["exercise_id"] for r in res["recommended_exercises"]]
        self.assertIn("ex_full_trio_review", rec_ids)

    def test_09_practice_history_rotation_avoids_immediate_repetition(self):
        """Verify engine rotates top recommendation if user just practiced that exact activity."""
        session = {
            "story": {"completed": True, "score_percent": 40.0, "missed_facts": ["a", "b", "c"]},
            "mindplay": {"completed": True, "ch2_correct": False},
        }
        # Without practice history, story retell is first
        recs_clean = self.engine.recommend(current_session=session)
        self.assertEqual(recs_clean["recommended_exercises"][0]["exercise_id"], "ex_narrative_retell_foundations")

        # With practice history indicating story retell was just practiced, it rotates
        practice_history = [{"exercise_id": "ex_narrative_retell_foundations", "timestamp": "2026-11-13T10:00:00Z"}]
        recs_rotated = self.engine.recommend(current_session=session, practice_history=practice_history)
        self.assertNotEqual(recs_rotated["recommended_exercises"][0]["exercise_id"], "ex_narrative_retell_foundations")

    def test_10_invalid_and_edge_case_inputs(self):
        """Verify engine gracefully handles None, empty, and malformed inputs."""
        res1 = self.engine.recommend(None)
        self.assertTrue(res1["is_starter_path"])

        res2 = self.engine.recommend({"voice": None, "story": {}, "mindplay": None})
        self.assertTrue(res2["is_starter_path"])

        res3 = self.engine.recommend({"story": {"completed": True, "score_percent": -15.0}})
        self.assertFalse(res3["is_starter_path"])

    def test_11_practice_progress_empty_state(self):
        """Verify practice progress returns honest empty state when records are empty."""
        prog = self.tracker.analyze_progress([])
        self.assertFalse(prog["has_practice_history"])
        self.assertEqual(prog["total_activities_completed"], 0)
        self.assertIn("No practice activities completed yet", prog["message"])

        prog_none = self.tracker.analyze_progress(None)
        self.assertFalse(prog_none["has_practice_history"])

    def test_12_practice_progress_tracking_metrics(self):
        """Verify practice progress accurately computes completion count, personal bests, and dates."""
        records = [
            {
                "exercise_id": "ex_narrative_retell_foundations",
                "completed": True,
                "score": 62.5,
                "duration_seconds": 120.0,
                "timestamp": "2026-11-10T09:00:00Z",
            },
            {
                "exercise_id": "ex_narrative_retell_foundations",
                "completed": True,
                "score": 87.5,
                "duration_seconds": 140.0,
                "timestamp": "2026-11-12T09:00:00Z",
            },
            {
                "exercise_id": "ex_visual_search_agility",
                "completed": True,
                "score": 95.0,
                "duration_seconds": 45.0,
                "timestamp": "2026-11-12T09:10:00Z",
            },
        ]
        prog = self.tracker.analyze_progress(records)
        self.assertTrue(prog["has_practice_history"])
        self.assertEqual(prog["total_activities_completed"], 3)
        self.assertEqual(prog["unique_exercises_count"], 2)
        self.assertAlmostEqual(prog["total_practice_duration_seconds"], 305.0)

        # Personal bests
        self.assertEqual(prog["personal_bests"]["ex_narrative_retell_foundations"], 87.5)
        self.assertEqual(prog["personal_bests"]["ex_visual_search_agility"], 95.0)

        # Consistency
        self.assertEqual(prog["consistency"]["days_active_count"], 2)
        self.assertEqual(prog["consistency"]["consistency_label"], "Regular Practice")

        # Scientific disclaimer
        self.assertIn("familiarity effects", prog["scientific_notice"])


class TestLearningPathAPI(unittest.TestCase):
    """Integration tests for FastAPI learning path endpoints."""

    def setUp(self):
        self.client = TestClient(app)

    def test_13_api_root_exposes_learning_endpoints(self):
        """Root endpoint advertises learning path endpoints."""
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("learning_catalog_endpoint", data)
        self.assertIn("learning_recommend_endpoint", data)
        self.assertIn("learning_progress_endpoint", data)
        self.assertEqual(data["learning_catalog_endpoint"], "/api/learning/catalog")

    def test_14_api_get_catalog(self):
        """GET /api/learning/catalog returns valid structured catalog."""
        res = self.client.get("/api/learning/catalog")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["version"], "1.0.0")
        self.assertGreaterEqual(len(data["exercises"]), 6)

    def test_15_api_post_recommend_starter_path(self):
        """POST /api/learning/recommend returns starter path for empty payload."""
        payload = {"current_session": None, "history_sessions": None}
        res = self.client.post("/api/learning/recommend", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "success")
        self.assertTrue(data["is_starter_path"])
        self.assertEqual(len(data["recommended_exercises"]), 3)

    def test_16_api_post_recommend_with_active_session(self):
        """POST /api/learning/recommend evaluates active session and returns targeted exercises."""
        payload = {
            "current_session": {
                "sessionId": "test-session-p9",
                "story": {"completed": True, "score_percent": 60.0, "missed_facts": ["a", "b"]},
                "mindplay": {"completed": True, "ch2_correct": False},
            }
        }
        res = self.client.post("/api/learning/recommend", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "success")
        self.assertFalse(data["is_starter_path"])
        rec_ids = [r["exercise_id"] for r in data["recommended_exercises"]]
        self.assertIn("ex_narrative_retell_foundations", rec_ids)
        self.assertIn("ex_temporal_chronology_builder", rec_ids)

    def test_17_api_post_progress_empty_and_active(self):
        """POST /api/learning/progress handles empty and active practice logs."""
        # Empty
        res_empty = self.client.post("/api/learning/progress", json={"practice_records": []})
        self.assertEqual(res_empty.status_code, 200)
        self.assertFalse(res_empty.json()["has_practice_history"])

        # Active
        records = [
            {
                "exercise_id": "ex_narrative_retell_foundations",
                "completed": True,
                "score": 85.0,
                "duration_seconds": 130.0,
                "timestamp": "2026-11-13T12:00:00Z",
            }
        ]
        res_active = self.client.post("/api/learning/progress", json={"practice_records": records})
        self.assertEqual(res_active.status_code, 200)
        data = res_active.json()
        self.assertTrue(data["has_practice_history"])
        self.assertEqual(data["total_activities_completed"], 1)


if __name__ == "__main__":
    unittest.main()

