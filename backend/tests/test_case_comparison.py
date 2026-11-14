"""
Unit & Integration Tests for Phase 8: ALVI Case Comparison & Cognitive Performance Analytics.
Tests:
- ReferenceStatisticsService empirical distributions, provenance, and fallbacks.
- CaseComparisonEngine Mode A (current multi-modal synthesis & missing module handling).
- CaseComparisonEngine Mode B (personal history tracking, empty state when < 2 sessions, delta calculations).
- CaseComparisonEngine Mode C (research reference benchmark against DementiaNet clean features).
- FastAPI endpoints: GET /api/cases/reference-stats, POST /api/cases/compare, GET /
"""

import unittest
from pathlib import Path
from typing import Any, Dict

from fastapi.testclient import TestClient
from backend.main import app
from backend.services.case_comparison import CaseComparisonEngine, get_case_comparison_engine
from backend.services.reference_statistics import (
    ReferenceStatisticsService,
    get_reference_statistics_service,
)


class TestCaseComparisonService(unittest.TestCase):
    """Unit tests for ReferenceStatisticsService and CaseComparisonEngine."""

    def setUp(self):
        self.ref_service = get_reference_statistics_service()
        self.engine = get_case_comparison_engine()

    def test_01_reference_statistics_structure_and_provenance(self):
        """Verify reference statistics load real data from DementiaNet clean CSV."""
        stats = self.ref_service.get_reference_statistics()
        self.assertEqual(stats["status"], "success")

        # Provenance verification
        prov = stats["provenance"]
        self.assertEqual(prov["total_recordings"], 100)
        self.assertEqual(prov["unique_speakers"], 80)
        self.assertEqual(prov["subgroup_distribution"]["dementia_labeled"], 53)
        self.assertEqual(prov["subgroup_distribution"]["nodementia_labeled"], 47)
        self.assertIn("NOT clinically verified", prov["nature_of_data"])
        self.assertIn("NOT establish clinical diagnostic thresholds", prov["clinical_disclaimer"])

        # Acoustic metrics verification
        metrics = stats["acoustic_reference_metrics"]
        required_keys = [
            "voice.f0_mean",
            "voice.pause_ratio",
            "voice.zcr",
            "voice.rms",
            "voice.spectral_centroid",
            "voice.duration",
            "voice.pause_count",
        ]
        for k in required_keys:
            self.assertIn(k, metrics, f"Missing metric key: {k}")
            dist = metrics[k]["distribution"]
            self.assertEqual(dist["count"], 100)
            self.assertGreater(dist["mean"], 0)
            self.assertGreater(dist["median"], 0)
            self.assertLessEqual(dist["q1"], dist["median"])
            self.assertLessEqual(dist["median"], dist["q3"])
            self.assertLessEqual(dist["min"], dist["max"])

    def test_02_reference_statistics_fallback(self):
        """Verify fallback behavior when CSV file path is missing."""
        dummy_service = ReferenceStatisticsService(clean_csv_path=Path("nonexistent_path/fake.csv"))
        fallback_stats = dummy_service.get_reference_statistics()
        self.assertEqual(fallback_stats["status"], "fallback")
        self.assertIn("voice.f0_mean", fallback_stats["acoustic_reference_metrics"])

    def test_03_mode_a_complete_three_task_session(self):
        """Mode A: Verify synthesis when all 3 activities are completed."""
        session = {
            "sessionId": "test-session-all-3",
            "startedAt": "2026-11-13T20:00:00Z",
            "voice": {
                "completed": True,
                "durationSeconds": 24.5,
                "isValid": True,
                "features": {
                    "f0_mean": 142.3,
                    "rms_mean": 0.058,
                    "zcr_mean": 0.082,
                    "low_energy_frame_ratio": 0.165,
                    "low_energy_interval_count": 5,
                    "spectral_centroid_mean": 1620.0,
                },
                "research_prediction": {
                    "predicted_label": "nodementia",
                    "raw_model_score": 0.42,
                    "model_version": "1.0.0-experimental",
                },
            },
            "story": {
                "completed": True,
                "durationSeconds": 35.0,
                "recalled_facts": ["aarav", "umbrella", "apples", "rain"],
                "missed_facts": ["park", "bench"],
                "score_percent": 66.7,
                "transcript": "Aarav walked in the rain with his umbrella and bought apples.",
            },
            "mindplay": {
                "completed": True,
                "ch1_selected": ["umbrella", "apples"],
                "ch1_correct": True,
                "ch1_score": 2,
                "ch2_correct": True,
                "ch3_correct": True,
                "ch3_reactionMs": 1950.0,
                "total_time_seconds": 38.0,
            },
        }

        result = self.engine.compare(session)
        mode_a = result["mode_a_current_performance"]

        self.assertEqual(mode_a["completion_status"], "complete")
        self.assertEqual(mode_a["tasks_completed_count"], 3)
        self.assertEqual(len(mode_a["missing_tasks"]), 0)
        self.assertIn("voice", mode_a["available_tasks"])
        self.assertIn("story", mode_a["available_tasks"])
        self.assertIn("mindplay", mode_a["available_tasks"])

        # Check domain summaries
        self.assertTrue(mode_a["domain_summaries"]["acoustic_prosodic_domain"]["collected"])
        self.assertTrue(mode_a["domain_summaries"]["episodic_memory_domain"]["collected"])
        self.assertTrue(mode_a["domain_summaries"]["executive_function_domain"]["collected"])

    def test_04_mode_a_partial_session_voice_only(self):
        """Mode A: Honest handling when only Voice Check-in was administered."""
        session = {
            "sessionId": "test-session-voice-only",
            "voice": {
                "completed": True,
                "durationSeconds": 18.0,
                "isValid": True,
                "features": {
                    "f0_mean": 135.0,
                    "rms_mean": 0.045,
                    "zcr_mean": 0.075,
                    "low_energy_frame_ratio": 0.20,
                    "low_energy_interval_count": 6,
                    "spectral_centroid_mean": 1450.0,
                },
            },
            "story": {"completed": False},
            "mindplay": {"completed": False},
        }

        result = self.engine.compare(session)
        mode_a = result["mode_a_current_performance"]

        self.assertEqual(mode_a["completion_status"], "partial")
        self.assertEqual(mode_a["tasks_completed_count"], 1)
        self.assertIn("story", mode_a["missing_tasks"])
        self.assertIn("mindplay", mode_a["missing_tasks"])
        self.assertIsNone(mode_a["mindplay"])
        self.assertFalse(mode_a["domain_summaries"]["episodic_memory_domain"]["collected"])
        self.assertFalse(mode_a["domain_summaries"]["executive_function_domain"]["collected"])

    def test_05_mode_a_empty_session(self):
        """Mode A: Completely blank/uncollected session."""
        session = {
            "sessionId": "blank-session",
            "voice": {"completed": False},
            "story": {"completed": False},
            "mindplay": {"completed": False},
        }
        result = self.engine.compare(session)
        mode_a = result["mode_a_current_performance"]

        self.assertEqual(mode_a["completion_status"], "uncollected")
        self.assertEqual(mode_a["tasks_completed_count"], 0)
        self.assertEqual(len(mode_a["missing_tasks"]), 3)

    def test_06_mode_b_empty_state_under_two_sessions(self):
        """Mode B: Returns honest empty state when fewer than 2 total sessions exist."""
        current = {"sessionId": "s-1", "story": {"score_percent": 80.0}}

        # 0 history sessions
        res_zero = self.engine.compare(current, history_sessions=[])
        mode_b = res_zero["mode_b_personal_history"]
        self.assertFalse(mode_b["has_sufficient_history"])
        self.assertEqual(mode_b["total_sessions_recorded"], 1)
        self.assertEqual(mode_b["minimum_required_sessions"], 2)
        self.assertIn("requires at least 2 completed sessions", mode_b["message"])

        # None history sessions
        res_none = self.engine.compare(current, history_sessions=None)
        self.assertFalse(res_none["mode_b_personal_history"]["has_sufficient_history"])

    def test_07_mode_b_trajectory_with_two_plus_sessions(self):
        """Mode B: Calculates delta, percent change, and neutral trajectory across sessions."""
        current = {
            "sessionId": "session-2",
            "story": {"score_percent": 87.5},
            "mindplay": {"ch3_reactionMs": 1800.0},
            "voice": {
                "features": {
                    "f0_mean": 140.0,
                    "low_energy_frame_ratio": 0.15,
                    "rms_mean": 0.060,
                }
            },
        }
        history = [
            {
                "sessionId": "session-1",
                "startedAt": "2026-11-10T10:00:00Z",
                "story": {"score_percent": 75.0},
                "mindplay": {"ch3_reactionMs": 2200.0},
                "voice": {
                    "features": {
                        "f0_mean": 136.0,
                        "low_energy_frame_ratio": 0.20,
                        "rms_mean": 0.050,
                    }
                },
            }
        ]

        result = self.engine.compare(current, history)
        mode_b = result["mode_b_personal_history"]

        self.assertTrue(mode_b["has_sufficient_history"])
        self.assertEqual(mode_b["total_sessions_recorded"], 2)
        self.assertEqual(mode_b["prior_session_id"], "session-1")

        trajectories = mode_b["metric_trajectories"]
        # Story: 87.5 - 75.0 = +12.5%
        self.assertIn("story_recall_accuracy", trajectories)
        self.assertAlmostEqual(trajectories["story_recall_accuracy"]["absolute_delta"], 12.5, places=1)
        self.assertEqual(trajectories["story_recall_accuracy"]["trajectory"], "increased")

        # Reaction latency: 1800 - 2200 = -400ms
        self.assertIn("visual_search_latency", trajectories)
        self.assertEqual(trajectories["visual_search_latency"]["absolute_delta"], -400.0)
        self.assertEqual(trajectories["visual_search_latency"]["trajectory"], "decreased")

        # Pause ratio: 0.15 - 0.20 = -0.05
        self.assertIn("voice_pause_ratio", trajectories)
        self.assertAlmostEqual(trajectories["voice_pause_ratio"]["absolute_delta"], -0.05, places=3)
        self.assertEqual(trajectories["voice_pause_ratio"]["trajectory"], "decreased")

    def test_08_mode_c_reference_benchmarks(self):
        """Mode C: Maps extracted acoustic features to empirical reference distributions."""
        session = {
            "voice": {
                "completed": True,
                "durationSeconds": 22.0,
                "features": {
                    "f0_mean": 135.5,  # Exactly at median
                    "rms_mean": 0.055,
                    "zcr_mean": 0.080,
                    "low_energy_frame_ratio": 0.16,
                    "spectral_centroid_mean": 1500.0,
                },
            }
        }

        result = self.engine.compare(session)
        mode_c = result["mode_c_research_reference"]

        self.assertEqual(mode_c["status"], "success")
        benchmarks = mode_c["benchmarks"]
        self.assertGreaterEqual(len(benchmarks), 5)

        # F0 benchmark should be classified as Within Reference IQR
        f0_bm = next((b for b in benchmarks if b["metric_key"] == "voice.f0_mean"), None)
        self.assertIsNotNone(f0_bm)
        self.assertAlmostEqual(f0_bm["user_value"], 135.5, places=1)
        self.assertEqual(f0_bm["status_badge"], "Within Reference IQR")
        self.assertAlmostEqual(f0_bm["percent_of_median"], 100.0, delta=2.0)

        # Missing metric should receive Uncollected / Missing
        uncollected_bm = next((b for b in benchmarks if b["metric_key"] == "voice.pause_count"), None)
        if uncollected_bm:
            self.assertEqual(uncollected_bm["status_badge"], "Uncollected / Missing")


class TestCaseComparisonAPI(unittest.TestCase):
    """Integration tests for FastAPI comparison endpoints."""

    def setUp(self):
        self.client = TestClient(app)

    def test_09_api_root_exposes_comparison_endpoints(self):
        """Root endpoint lists comparison endpoints and updated version."""
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("cases_compare_endpoint", data)
        self.assertIn("cases_reference_endpoint", data)
        self.assertEqual(data["cases_compare_endpoint"], "/api/cases/compare")
        self.assertEqual(data["cases_reference_endpoint"], "/api/cases/reference-stats")

    def test_10_api_get_reference_stats(self):
        """GET /api/cases/reference-stats returns empirical reference dataset distributions."""
        res = self.client.get("/api/cases/reference-stats")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("provenance", data)
        self.assertIn("acoustic_reference_metrics", data)
        self.assertEqual(data["provenance"]["total_recordings"], 100)

    def test_11_api_post_compare_success(self):
        """POST /api/cases/compare executes comparison with valid current and history payload."""
        payload = {
            "current_session": {
                "sessionId": "api-test-curr",
                "voice": {
                    "completed": True,
                    "durationSeconds": 20.0,
                    "features": {
                        "f0_mean": 145.0,
                        "rms_mean": 0.052,
                        "zcr_mean": 0.078,
                        "low_energy_frame_ratio": 0.18,
                    },
                },
                "story": {
                    "completed": True,
                    "score_percent": 80.0,
                    "recalled_facts": ["aarav", "umbrella"],
                },
                "mindplay": {
                    "completed": True,
                    "ch1_correct": True,
                    "ch2_correct": True,
                    "ch3_correct": True,
                    "ch3_reactionMs": 2100.0,
                },
            },
            "history_sessions": [
                {
                    "sessionId": "api-test-hist-1",
                    "story": {"score_percent": 70.0},
                    "mindplay": {"ch3_reactionMs": 2400.0},
                }
            ],
        }

        res = self.client.post("/api/cases/compare", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["mode_a_current_performance"]["completion_status"], "complete")
        self.assertTrue(data["mode_b_personal_history"]["has_sufficient_history"])
        self.assertEqual(len(data["mode_c_research_reference"]["benchmarks"]), 7)

    def test_12_api_post_compare_empty_session_validation(self):
        """POST /api/cases/compare handles minimal/empty session dictionaries without error."""
        payload = {
            "current_session": {},
            "history_sessions": [],
        }
        res = self.client.post("/api/cases/compare", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["mode_a_current_performance"]["completion_status"], "uncollected")
        self.assertFalse(data["mode_b_personal_history"]["has_sufficient_history"])

    def test_13_api_post_compare_invalid_request(self):
        """POST /api/cases/compare returns 422 if current_session is missing."""
        res = self.client.post("/api/cases/compare", json={"history_sessions": []})
        self.assertEqual(res.status_code, 422)


if __name__ == "__main__":
    unittest.main()

