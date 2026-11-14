"""
ALVI Pattern Explorer Automated Test Suite — backend/tests/test_patterns.py

Verifies longitudinal pattern analytics, history normalization, time-series trend calculation,
data integrity constraints, deduplication, practice completion tracking, FastAPI endpoints,
and zero regressions across all prior modules.
"""

from datetime import datetime, timezone
import io
import math
import unittest

from fastapi.testclient import TestClient

from backend.main import app
from backend.services.history_normalization import HistoryNormalizer, get_history_normalizer
from backend.services.pattern_analytics import PatternAnalyticsService, get_pattern_analytics_service
from backend.services.practice_progress import get_practice_progress_tracker
from backend.services.trend_statistics import TrendStatistics, get_trend_statistics


class TestHistoryNormalization(unittest.TestCase):
    """Tests for HistoryNormalizer sanitization, deduplication, and bounds checking."""

    def setUp(self):
        self.normalizer = get_history_normalizer()

    def test_01_empty_history(self):
        """Empty session and practice arrays return empty normalized lists without error."""
        valid_sess, excluded_sess = self.normalizer.normalize_sessions([])
        self.assertEqual(len(valid_sess), 0)
        self.assertEqual(len(excluded_sess), 0)

        valid_prac, excluded_prac = self.normalizer.normalize_practice_records([])
        self.assertEqual(len(valid_prac), 0)
        self.assertEqual(len(excluded_prac), 0)

    def test_02_single_valid_session(self):
        """Single valid session normalizes correctly with canonical timestamps and ID."""
        raw = [{
            "sessionId": "sess-alpha",
            "startedAt": "2026-10-10T14:30:00Z",
            "voice": {"completed": True, "durationSeconds": 24.5, "features": {"mean_f0": 160.5, "rms": 0.08}},
            "story": {"completed": True, "score_percent": 85.0},
            "mindplay": {"completed": True, "ch1_score": 2, "ch3_reactionMs": 1850.0}
        }]
        valid, excluded = self.normalizer.normalize_sessions(raw)
        self.assertEqual(len(valid), 1)
        self.assertEqual(len(excluded), 0)
        self.assertEqual(valid[0]["session_id"], "sess-alpha")
        self.assertEqual(valid[0]["date"], "2026-10-10")
        self.assertEqual(valid[0]["voice"]["metrics"]["f0_mean_hz"], 160.5)
        self.assertEqual(valid[0]["story"]["score_percent"], 85.0)
        self.assertEqual(valid[0]["mindplay"]["ch3_reaction_ms"], 1850.0)

    def test_03_out_of_order_timestamps(self):
        """Sessions submitted in reverse or jumbled order are sorted chronologically."""
        raw = [
            {"sessionId": "sess-3", "startedAt": "2026-11-01T10:00:00Z", "story": {"score_percent": 90.0}},
            {"sessionId": "sess-1", "startedAt": "2026-09-01T10:00:00Z", "story": {"score_percent": 70.0}},
            {"sessionId": "sess-2", "startedAt": "2026-10-01T10:00:00Z", "story": {"score_percent": 80.0}}
        ]
        valid, _ = self.normalizer.normalize_sessions(raw)
        self.assertEqual(len(valid), 3)
        self.assertEqual(valid[0]["session_id"], "sess-1")
        self.assertEqual(valid[1]["session_id"], "sess-2")
        self.assertEqual(valid[2]["session_id"], "sess-3")

    def test_04_duplicate_session_records(self):
        """Identical session IDs and timestamp collisions are deduplicated."""
        raw = [
            {"sessionId": "sess-dupe", "startedAt": "2026-10-01T12:00:00Z", "voice": {"completed": True}},
            {"sessionId": "sess-dupe", "startedAt": "2026-10-01T12:00:00Z", "voice": {"completed": True}},
            {"sessionId": "sess-another", "startedAt": "2026-10-01T12:00:00Z", "voice": {"completed": True}},
            {"sessionId": "sess-unique", "startedAt": "2026-10-02T12:00:00Z", "voice": {"completed": True}}
        ]
        valid, excluded = self.normalizer.normalize_sessions(raw)
        self.assertEqual(len(valid), 2)
        self.assertEqual(len(excluded), 2)
        self.assertEqual(valid[0]["session_id"], "sess-dupe")
        self.assertEqual(valid[1]["session_id"], "sess-unique")

    def test_05_missing_metrics_preserved_as_none(self):
        """Uncompleted or unmeasured tasks retain metrics as None rather than zero-filling."""
        raw = [{
            "sessionId": "sess-partial",
            "startedAt": "2026-10-10T10:00:00Z",
            "voice": {"completed": False},  # voice unmeasured
            "story": {"completed": True, "score_percent": 60.0},
            "mindplay": {"completed": False}
        }]
        valid, _ = self.normalizer.normalize_sessions(raw)
        self.assertEqual(len(valid), 1)
        self.assertIsNone(valid[0]["voice"]["metrics"]["f0_mean_hz"])
        self.assertIsNone(valid[0]["mindplay"]["ch3_reaction_ms"])
        self.assertEqual(valid[0]["story"]["score_percent"], 60.0)

    def test_06_invalid_timestamps_excluded(self):
        """Malformed, garbage, or unparseable timestamps are safely excluded."""
        raw = [
            {"sessionId": "sess-bad-1", "startedAt": "not-a-timestamp", "voice": {"completed": True}},
            {"sessionId": "sess-bad-2", "startedAt": None, "voice": {"completed": True}},
            {"sessionId": "sess-good", "startedAt": "2026-10-10T10:00:00Z", "voice": {"completed": True}}
        ]
        valid, excluded = self.normalizer.normalize_sessions(raw)
        self.assertEqual(len(valid), 1)
        self.assertEqual(len(excluded), 2)
        self.assertEqual(valid[0]["session_id"], "sess-good")

    def test_07_nan_and_infinity_values_rejected(self):
        """Non-numeric NaN and Infinity floats are clamped or converted to None."""
        raw = [{
            "sessionId": "sess-nan",
            "startedAt": "2026-10-10T10:00:00Z",
            "voice": {"completed": True, "features": {"mean_f0": float("nan"), "rms": float("inf")}},
            "story": {"completed": True, "score_percent": float("nan")},
            "mindplay": {"completed": True, "ch3_reactionMs": float("inf")}
        }]
        valid, _ = self.normalizer.normalize_sessions(raw)
        self.assertEqual(len(valid), 1)
        self.assertIsNone(valid[0]["voice"]["metrics"]["f0_mean_hz"])
        self.assertIsNone(valid[0]["voice"]["metrics"]["rms_energy"])
        self.assertIsNone(valid[0]["story"]["score_percent"])
        self.assertIsNone(valid[0]["mindplay"]["ch3_reaction_ms"])

    def test_08_negative_or_impossible_reaction_times(self):
        """Negative or non-physiological latencies (<150ms or >30000ms) are rejected."""
        raw = [{
            "sessionId": "sess-rx",
            "startedAt": "2026-10-10T10:00:00Z",
            "mindplay": {"completed": True, "ch3_reactionMs": -500.0}
        }]
        valid, _ = self.normalizer.normalize_sessions(raw)
        self.assertEqual(len(valid), 1)
        self.assertIsNone(valid[0]["mindplay"]["ch3_reaction_ms"])

        raw_fast = [{
            "sessionId": "sess-rx-fast",
            "startedAt": "2026-10-10T10:00:00Z",
            "mindplay": {"completed": True, "ch3_reactionMs": 40.0}  # impossible human motor reaction
        }]
        valid_fast, _ = self.normalizer.normalize_sessions(raw_fast)
        self.assertIsNone(valid_fast[0]["mindplay"]["ch3_reaction_ms"])

    def test_09_synthetic_demo_records_segregated(self):
        """Records marked with is_demo=True or is_sample=True are excluded from genuine history."""
        raw = [
            {"sessionId": "sess-demo", "startedAt": "2026-10-10T10:00:00Z", "is_demo": True},
            {"sessionId": "sess-sample", "startedAt": "2026-10-11T10:00:00Z", "is_sample": True},
            {"sessionId": "sess-real", "startedAt": "2026-10-12T10:00:00Z"}
        ]
        valid, excluded = self.normalizer.normalize_sessions(raw, include_demo=False)
        self.assertEqual(len(valid), 1)
        self.assertEqual(len(excluded), 2)
        self.assertEqual(valid[0]["session_id"], "sess-real")

    def test_10_practice_records_initiated_vs_completed(self):
        """Task 9 verification: Initiated-only practice records are excluded from completed progress."""
        raw_prac = [
            {"practice_id": "p1", "exercise_id": "ex_narrative", "status": "completed", "score": 90.0, "timestamp": "2026-10-01T10:00:00Z"},
            {"practice_id": "p2", "exercise_id": "ex_narrative", "status": "initiated", "completed": False, "timestamp": "2026-10-02T10:00:00Z"},
            {"practice_id": "p3", "exercise_id": "ex_dual_feature", "is_demo": True, "status": "completed", "timestamp": "2026-10-03T10:00:00Z"}
        ]
        valid, excluded = self.normalizer.normalize_practice_records(raw_prac, include_demo=False)
        self.assertEqual(len(valid), 1)
        self.assertEqual(valid[0]["practice_id"], "p1")
        self.assertEqual(len(excluded), 2)


class TestTrendStatisticsAndAnalytics(unittest.TestCase):
    """Tests for descriptive statistics, pairwise comparison, and longitudinal trends."""

    def setUp(self):
        self.trend_stats = get_trend_statistics()
        self.analytics_svc = get_pattern_analytics_service()

    def test_11_single_baseline_statistics(self):
        """n=1 returns comparison_mode='baseline_only' without slope or deltas."""
        series = [{"session_id": "s1", "date": "2026-10-01", "timestamp": "2026-10-01T10:00:00Z", "value": 80.0}]
        res = self.trend_stats.compute_metric_series(series, "Recall Completeness", "%")
        self.assertEqual(res["data_points_count"], 1)
        self.assertEqual(res["comparison_mode"], "baseline_only")
        self.assertEqual(res["baseline_value"], 80.0)
        self.assertEqual(res["latest_value"], 80.0)
        self.assertIsNone(res["trend_slope_per_session"])
        self.assertEqual(res["trend_direction"], "baseline_established")

    def test_12_pairwise_comparison_statistics(self):
        """n=2 returns pairwise comparison with absolute delta and percent change, but no trend line."""
        series = [
            {"session_id": "s1", "date": "2026-10-01", "timestamp": "2026-10-01T10:00:00Z", "value": 150.0},
            {"session_id": "s2", "date": "2026-10-15", "timestamp": "2026-10-15T10:00:00Z", "value": 165.0}
        ]
        res = self.trend_stats.compute_metric_series(series, "Pitch F0", "Hz")
        self.assertEqual(res["data_points_count"], 2)
        self.assertEqual(res["comparison_mode"], "pairwise_only")
        self.assertEqual(res["baseline_value"], 150.0)
        self.assertEqual(res["latest_value"], 165.0)
        self.assertEqual(res["absolute_change"], 15.0)
        self.assertEqual(res["percent_change"], 10.0)
        self.assertEqual(res["mean"], 157.5)
        self.assertIsNone(res["trend_slope_per_session"])

    def test_13_multi_session_longitudinal_trajectory(self):
        """n>=3 calculates ordinary least squares linear regression slope and trajectory direction."""
        series = [
            {"session_id": "s1", "date": "2026-10-01", "timestamp": "2026-10-01T10:00:00Z", "value": 70.0},
            {"session_id": "s2", "date": "2026-10-10", "timestamp": "2026-10-10T10:00:00Z", "value": 80.0},
            {"session_id": "s3", "date": "2026-10-20", "timestamp": "2026-10-20T10:00:00Z", "value": 90.0}
        ]
        res = self.trend_stats.compute_metric_series(series, "Recall", "%")
        self.assertEqual(res["data_points_count"], 3)
        self.assertEqual(res["comparison_mode"], "longitudinal_trend")
        self.assertEqual(res["baseline_value"], 70.0)
        self.assertEqual(res["latest_value"], 90.0)
        self.assertEqual(res["mean"], 80.0)
        self.assertEqual(res["median"], 80.0)
        self.assertEqual(res["trend_slope_per_session"], 10.0)
        self.assertEqual(res["trend_direction"], "increasing")

    def test_14_outlier_detection_with_sufficient_history(self):
        """Values > 2.5 std devs from personal mean are flagged as outliers when n >= 4."""
        series = [
            {"session_id": "s1", "date": "2026-10-01", "timestamp": "2026-10-01T10:00:00Z", "value": 150.0},
            {"session_id": "s2", "date": "2026-10-05", "timestamp": "2026-10-05T10:00:00Z", "value": 152.0},
            {"session_id": "s3", "date": "2026-10-10", "timestamp": "2026-10-10T10:00:00Z", "value": 149.0},
            {"session_id": "s4", "date": "2026-10-15", "timestamp": "2026-10-15T10:00:00Z", "value": 151.0},
            {"session_id": "s5", "date": "2026-10-20", "timestamp": "2026-10-20T10:00:00Z", "value": 450.0}  # extreme spike
        ]
        res = self.trend_stats.compute_metric_series(series, "F0", "Hz")
        self.assertEqual(res["data_points_count"], 5)
        self.assertEqual(len(res["outliers"]), 1)
        self.assertEqual(res["outliers"][0]["session_id"], "s5")

    def test_15_task_version_and_difficulty_compatibility_notes(self):
        """Compatibility notes are flagged when stories or difficulty levels differ."""
        raw_sessions = [
            {"sessionId": "s1", "startedAt": "2026-10-01T10:00:00Z", "story": {"completed": True, "story_id": "story_a", "score_percent": 80.0}, "mindplay": {"difficulty": "Standard"}},
            {"sessionId": "s2", "startedAt": "2026-10-10T10:00:00Z", "story": {"completed": True, "story_id": "story_b", "score_percent": 80.0}, "mindplay": {"difficulty": "Advanced"}}
        ]
        res = self.analytics_svc.analyze_patterns(raw_sessions)
        self.assertEqual(len(res["compatibility_notes"]), 2)
        self.assertTrue(any("Story Recall sessions evaluated different narrative texts" in note for note in res["compatibility_notes"]))
        self.assertTrue(any("MindPlay sessions evaluated different game difficulty levels" in note for note in res["compatibility_notes"]))

    def test_16_practice_progress_quarantines_demo_records(self):
        """PracticeProgressTracker accurately ignores demo and initiated records."""
        tracker = get_practice_progress_tracker()
        raw_practices = [
            {"exercise_id": "ex_narrative_retell_foundations", "status": "completed", "score": 90.0, "duration_seconds": 180},
            {"exercise_id": "ex_dual_feature_binding", "status": "initiated", "completed": False},
            {"exercise_id": "ex_temporal_chronology_builder", "is_demo": True, "status": "completed", "score": 95.0}
        ]
        res = tracker.analyze_progress(raw_practices)
        self.assertEqual(res["total_activities_completed"], 1)
        self.assertEqual(res["unique_exercises_count"], 1)


class TestPatternExplorerAPI(unittest.TestCase):
    """Tests for FastAPI endpoints: GET /api/patterns/metrics and POST /api/patterns/analyze."""

    def setUp(self):
        self.client = TestClient(app)

    def test_17_api_get_metrics_catalog(self):
        """GET /api/patterns/metrics returns catalog of metrics, units, and governance notices."""
        resp = self.client.get("/api/patterns/metrics")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["version"], "1.6.0")
        self.assertIn("voice", data["metric_domains"])
        self.assertIn("story", data["metric_domains"])
        self.assertIn("mindplay", data["metric_domains"])
        self.assertIn("practice", data["metric_domains"])
        self.assertIn("clinical_policy", data["governance"])

    def test_18_api_post_analyze_empty_payload(self):
        """POST /api/patterns/analyze with empty lists returns valid empty-state response."""
        resp = self.client.post("/api/patterns/analyze", json={
            "session_history": [],
            "practice_history": []
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["history_summary"]["valid_sessions_analyzed"], 0)
        self.assertEqual(data["history_summary"]["history_threshold_status"], "no_history")

    def test_19_api_post_analyze_full_trajectory(self):
        """POST /api/patterns/analyze with 3 sessions computes complete multi-modal analysis."""
        sessions = [
            {
                "sessionId": "s-1",
                "startedAt": "2026-10-01T10:00:00Z",
                "voice": {"completed": True, "features": {"mean_f0": 150.0, "low_energy_frame_ratio": 0.22}},
                "story": {"completed": True, "score_percent": 75.0},
                "mindplay": {"completed": True, "ch3_reactionMs": 2200.0}
            },
            {
                "sessionId": "s-2",
                "startedAt": "2026-10-15T10:00:00Z",
                "voice": {"completed": True, "features": {"mean_f0": 152.0, "low_energy_frame_ratio": 0.20}},
                "story": {"completed": True, "score_percent": 80.0},
                "mindplay": {"completed": True, "ch3_reactionMs": 2000.0}
            },
            {
                "sessionId": "s-3",
                "startedAt": "2026-11-01T10:00:00Z",
                "voice": {"completed": True, "features": {"mean_f0": 154.0, "low_energy_frame_ratio": 0.18}},
                "story": {"completed": True, "score_percent": 85.0},
                "mindplay": {"completed": True, "ch3_reactionMs": 1800.0}
            }
        ]
        resp = self.client.post("/api/patterns/analyze", json={"session_history": sessions})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["history_summary"]["valid_sessions_analyzed"], 3)
        self.assertEqual(data["history_summary"]["history_threshold_status"], "longitudinal_trend_available")

        # Verify Story recall trend
        st_data = data["metrics_domains"]["story"]["score_percent"]
        self.assertEqual(st_data["mean"], 80.0)
        self.assertEqual(st_data["trend_direction"], "increasing")

        # Verify MindPlay latency
        mp_data = data["metrics_domains"]["mindplay"]["ch3_reaction_ms"]
        self.assertEqual(mp_data["latest_value"], 1800.0)
        self.assertEqual(mp_data["absolute_change"], -400.0)

        # Verify recent pairwise delta
        self.assertIsNotNone(data["recent_vs_previous_comparison"])
        self.assertEqual(data["recent_vs_previous_comparison"]["current_session_id"], "s-3")

    def test_20_api_root_exposes_pattern_endpoints(self):
        """GET / root endpoint advertises pattern metrics and analysis endpoints with v1.6.0."""
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["name"], "ALVI API")
        self.assertEqual(data["patterns_metrics_endpoint"], "/api/patterns/metrics")
        self.assertEqual(data["patterns_analyze_endpoint"], "/api/patterns/analyze")


class TestPriorPhaseRegressions(unittest.TestCase):
    """Regression checks verifying Phases 4, 6, 7, 8, and 9 remain fully operational."""

    def setUp(self):
        self.client = TestClient(app)

    def test_21_regression_voice_analyze(self):
        """Phase 4 & 5: POST /api/voice/analyze media type validation intact."""
        file_payload = {"file": ("test.txt", io.BytesIO(b"hello"), "text/plain")}
        resp = self.client.post("/api/voice/analyze", files=file_payload)
        self.assertEqual(resp.status_code, 415)

    def test_22_regression_story_catalog_and_eval(self):
        """Phase 6: GET /api/story/stories and POST /api/story/evaluate intact."""
        resp = self.client.get("/api/story/stories")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(len(resp.json()["stories"]) >= 1)

        eval_resp = self.client.post("/api/story/evaluate", json={
            "story_id": "aarav_story_v1",
            "transcript": "Aarav walked in the garden and saw a bird."
        })
        self.assertEqual(eval_resp.status_code, 200)
        self.assertIn("data", eval_resp.json())
        self.assertIn("composite_score", eval_resp.json()["data"])

    def test_23_regression_games_catalog_and_submit(self):
        """Phase 7: GET /api/games/catalog and POST /api/games/submit intact."""
        resp = self.client.get("/api/games/catalog")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("challenges", resp.json())

    def test_24_regression_cases_reference_and_compare(self):
        """Phase 8: GET /api/cases/reference-stats and POST /api/cases/compare intact."""
        ref_resp = self.client.get("/api/cases/reference-stats")
        self.assertEqual(ref_resp.status_code, 200)
        self.assertIn("acoustic_reference_metrics", ref_resp.json())

    def test_25_regression_learning_catalog_and_recommend(self):
        """Phase 9: GET /api/learning/catalog and POST /api/learning/recommend intact."""
        cat_resp = self.client.get("/api/learning/catalog")
        self.assertEqual(cat_resp.status_code, 200)
        self.assertEqual(len(cat_resp.json()["exercises"]), 6)

        rec_resp = self.client.post("/api/learning/recommend", json={})
        self.assertEqual(rec_resp.status_code, 200)
        self.assertTrue(rec_resp.json()["is_starter_path"])


if __name__ == "__main__":
    unittest.main()
