"""
ALVI Longitudinal Pattern Analytics Service — backend/services/pattern_analytics.py

Orchestrates multi-session longitudinal analytics across Voice Acoustics, Story Recall Memory,
MindPlay Game Telemetry, and Learning Path Practice Engagement.

STRICT RESEARCH & SAFETY GOVERNANCE:
1. Metric Integrity: Measurements are computed from genuine recorded observations with explicit units.
2. Separate Visual Axes: Latency (ms), accuracy (%), pitch (Hz), and energy are strictly separated.
3. Task Familiarity Notice: Cautions users that gains on repeated recall or game tasks reflect procedural
   familiarity effects (test-retest practice) and NOT clinical Alzheimer's reversal or recovery.
4. Non-Diagnostic Policy: Disclaims clinical diagnosis, disease probability calculation, or progression scores.
"""

from typing import Any, Dict, List, Optional
from backend.services.history_normalization import get_history_normalizer
from backend.services.trend_statistics import get_trend_statistics


class PatternAnalyticsService:
    """Provides high-level multi-modal longitudinal pattern analysis across ALVI sessions."""

    def __init__(self):
        self.normalizer = get_history_normalizer()
        self.trend_calculator = get_trend_statistics()

    def get_available_metrics_catalog(self) -> Dict[str, Any]:
        """Returns catalog of trackable metrics, units, ranges, and analytical constraints."""
        return {
            "version": "1.6.0",
            "service_name": "ALVI Longitudinal Pattern Explorer",
            "governance": {
                "clinical_policy": (
                    "ALVI Pattern Explorer provides observational longitudinal trend tracking for self-monitoring "
                    "and research insight. It does NOT diagnose Alzheimer's disease, evaluate clinical progression, "
                    "or calculate medical deterioration probabilities."
                ),
                "familiarity_effect_warning": (
                    "Repeated performance on cognitive games and story recall tasks is subject to test-retest "
                    "learning and task familiarity. Upward trajectories reflect procedural practice, not cognitive restoration."
                ),
                "acoustic_variance_notice": (
                    "Microphone hardware, ambient background noise, speech tempo, and user fatigue naturally cause "
                    "acoustic measurements to fluctuate between recordings without implying neurological change."
                )
            },
            "metric_domains": {
                "voice": {
                    "display_name": "Voice Check-in Acoustics",
                    "description": "Physical acoustic properties extracted from spontaneous vocal recordings.",
                    "metrics": [
                        {
                            "id": "f0_mean_hz",
                            "display_name": "Mean Fundamental Frequency (F0)",
                            "unit": "Hz",
                            "description": "Acoustic pitch center of voiced speech frames.",
                            "typical_human_range": "85 Hz – 260 Hz",
                            "chart_type": "line",
                            "y_axis_label": "Pitch (Hz)"
                        },
                        {
                            "id": "rms_energy",
                            "display_name": "RMS Signal Energy",
                            "unit": "RMS (0–1)",
                            "description": "Root-mean-square amplitude representing vocal loudness and breath support.",
                            "typical_human_range": "0.01 – 0.35",
                            "chart_type": "line",
                            "y_axis_label": "RMS Amplitude"
                        },
                        {
                            "id": "zero_crossing_rate",
                            "display_name": "Zero-Crossing Rate (ZCR)",
                            "unit": "Rate (0–1)",
                            "description": "Frequency of signal sign changes, capturing spectral noisiness.",
                            "typical_human_range": "0.02 – 0.25",
                            "chart_type": "line",
                            "y_axis_label": "ZCR"
                        },
                        {
                            "id": "low_energy_frame_ratio",
                            "display_name": "Low-Energy Frame Ratio (Pause Proxy)",
                            "unit": "Ratio (0–1)",
                            "description": "Proportion of audio frames with energy below pause threshold.",
                            "typical_human_range": "0.10 – 0.45",
                            "chart_type": "line",
                            "y_axis_label": "Frame Ratio"
                        },
                        {
                            "id": "spectral_centroid_hz",
                            "display_name": "Spectral Centroid",
                            "unit": "Hz",
                            "description": "Center of mass of the audio spectrum (spectral brightness).",
                            "typical_human_range": "500 Hz – 3500 Hz",
                            "chart_type": "line",
                            "y_axis_label": "Frequency (Hz)"
                        },
                        {
                            "id": "duration_seconds",
                            "display_name": "Recording Duration",
                            "unit": "Seconds",
                            "description": "Total length of vocal sample recorded.",
                            "typical_human_range": "10s – 60s",
                            "chart_type": "line",
                            "y_axis_label": "Duration (s)"
                        }
                    ]
                },
                "story": {
                    "display_name": "Story Recall Memory",
                    "description": "Episodic detail retention and chronological sequence accuracy.",
                    "metrics": [
                        {
                            "id": "score_percent",
                            "display_name": "Information Unit Completeness",
                            "unit": "%",
                            "description": "Percentage of core narrative anchor elements successfully recalled.",
                            "typical_human_range": "0% – 100%",
                            "chart_type": "line",
                            "y_axis_label": "Recall Accuracy (%)"
                        },
                        {
                            "id": "recalled_facts_count",
                            "display_name": "Recalled Anchor Count",
                            "unit": "Units",
                            "description": "Number of core factual milestones correctly articulated.",
                            "typical_human_range": "0 – 8",
                            "chart_type": "bar",
                            "y_axis_label": "Anchors Recalled"
                        },
                        {
                            "id": "missed_facts_count",
                            "display_name": "Missed Anchor Count",
                            "unit": "Units",
                            "description": "Number of core narrative anchor elements omitted.",
                            "typical_human_range": "0 – 8",
                            "chart_type": "bar",
                            "y_axis_label": "Anchors Missed"
                        },
                        {
                            "id": "chronological_inversions",
                            "display_name": "Chronological Inversions",
                            "unit": "Count",
                            "description": "Number of narrative milestone pairs recalled out of original sequence.",
                            "typical_human_range": "0 – 4",
                            "chart_type": "bar",
                            "y_axis_label": "Inversion Count"
                        }
                    ]
                },
                "mindplay": {
                    "display_name": "MindPlay Cognitive Telemetry",
                    "description": "Working memory, executive sequencing, and visual processing reaction times.",
                    "metrics": [
                        {
                            "id": "composite_accuracy_percent",
                            "display_name": "Overall Challenge Accuracy",
                            "unit": "%",
                            "description": "Cumulative score across Remember, Sequence, and Find challenges.",
                            "typical_human_range": "0% – 100%",
                            "chart_type": "line",
                            "y_axis_label": "Accuracy (%)"
                        },
                        {
                            "id": "ch1_score",
                            "display_name": "Dual-Feature Binding Score",
                            "unit": "pts (0–2)",
                            "description": "Correct target associations identified in Challenge 1.",
                            "typical_human_range": "0 – 2",
                            "chart_type": "bar",
                            "y_axis_label": "Score (pts)"
                        },
                        {
                            "id": "ch3_reaction_ms",
                            "display_name": "Visual Search Reaction Latency",
                            "unit": "ms",
                            "description": "Measured millisecond latency to identify visual search target (Ch 3).",
                            "typical_human_range": "500 ms – 15000 ms",
                            "chart_type": "line",
                            "y_axis_label": "Reaction Time (ms)"
                        },
                        {
                            "id": "total_time_seconds",
                            "display_name": "Total MindPlay Duration",
                            "unit": "Seconds",
                            "description": "Total elapsed seconds to complete all MindPlay challenges.",
                            "typical_human_range": "30s – 300s",
                            "chart_type": "line",
                            "y_axis_label": "Total Time (s)"
                        }
                    ]
                },
                "practice": {
                    "display_name": "Learning Path Practice",
                    "description": "Longitudinal drill completions and engagement frequency.",
                    "metrics": [
                        {
                            "id": "total_completed_count",
                            "display_name": "Completed Practice Drills",
                            "unit": "Drills",
                            "description": "Number of finished practice sessions.",
                            "chart_type": "bar",
                            "y_axis_label": "Completed Drills"
                        },
                        {
                            "id": "unique_exercises_count",
                            "display_name": "Unique Exercises Tried",
                            "unit": "Drills (0–6)",
                            "description": "Distinct exercise modalities practiced.",
                            "chart_type": "bar",
                            "y_axis_label": "Unique Drills"
                        },
                        {
                            "id": "cumulative_practice_minutes",
                            "display_name": "Total Practice Time",
                            "unit": "Minutes",
                            "description": "Cumulative minutes invested in practice exercises.",
                            "chart_type": "line",
                            "y_axis_label": "Minutes"
                        }
                    ]
                }
            }
        }

    def analyze_patterns(
        self,
        raw_sessions: Optional[List[Dict[str, Any]]],
        raw_practices: Optional[List[Dict[str, Any]]] = None,
        filter_options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Executes complete multi-modal pattern analysis across historical sessions and practice logs.

        Args:
            raw_sessions: List of raw session dictionaries.
            raw_practices: List of raw practice dictionaries.
            filter_options: Optional filters:
                            - "domain": "all" | "voice" | "story" | "mindplay" | "practice"
                            - "start_date": "YYYY-MM-DD"
                            - "end_date": "YYYY-MM-DD"
                            - "include_demo": bool (default False)

        Returns:
            Dict containing normalized time-series, statistics, comparisons, and governance notes.
        """
        filters = filter_options or {}
        include_demo = bool(filters.get("include_demo", False))

        # 1. Normalize sessions & practices
        valid_sessions, excluded_sessions = self.normalizer.normalize_sessions(raw_sessions, include_demo=include_demo)
        valid_practices, excluded_practices = self.normalizer.normalize_practice_records(raw_practices, include_demo=include_demo)

        # 2. Apply Date Range Filters if specified
        start_date = filters.get("start_date")
        end_date = filters.get("end_date")

        if start_date:
            valid_sessions = [s for s in valid_sessions if s["date"] >= start_date]
            valid_practices = [p for p in valid_practices if p["date"] >= start_date]
        if end_date:
            valid_sessions = [s for s in valid_sessions if s["date"] <= end_date]
            valid_practices = [p for p in valid_practices if p["date"] <= end_date]

        total_sessions_analyzed = len(valid_sessions)

        # 3. Extract time-series for Voice Metrics
        voice_f0_pts, voice_rms_pts, voice_zcr_pts = [], [], []
        voice_pause_pts, voice_centroid_pts, voice_dur_pts = [], [], []

        # 4. Extract time-series for Story Recall Metrics
        story_score_pts, story_recalled_pts, story_missed_pts, story_inversions_pts = [], [], [], []

        # 5. Extract time-series for MindPlay Metrics
        mindplay_acc_pts, mindplay_ch1_pts, mindplay_reaction_pts, mindplay_time_pts = [], [], [], []

        # Version & Compatibility Tracking
        story_ids_seen = set()
        scoring_versions_seen = set()
        game_difficulties_seen = set()

        for s in valid_sessions:
            meta = {
                "session_id": s["session_id"],
                "timestamp": s["timestamp"],
                "timestamp_epoch": s["timestamp_epoch"],
                "date": s["date"]
            }

            # Voice
            v_m = s["voice"].get("metrics", {})
            if s["voice"].get("completed"):
                if v_m.get("f0_mean_hz") is not None:
                    voice_f0_pts.append({**meta, "value": v_m["f0_mean_hz"]})
                if v_m.get("rms_energy") is not None:
                    voice_rms_pts.append({**meta, "value": v_m["rms_energy"]})
                if v_m.get("zero_crossing_rate") is not None:
                    voice_zcr_pts.append({**meta, "value": v_m["zero_crossing_rate"]})
                if v_m.get("low_energy_frame_ratio") is not None:
                    voice_pause_pts.append({**meta, "value": v_m["low_energy_frame_ratio"]})
                if v_m.get("spectral_centroid_hz") is not None:
                    voice_centroid_pts.append({**meta, "value": v_m["spectral_centroid_hz"]})
                if v_m.get("duration_seconds") is not None:
                    voice_dur_pts.append({**meta, "value": v_m["duration_seconds"]})

            # Story Recall
            st = s["story"]
            if st.get("completed"):
                story_ids_seen.add(st.get("story_id"))
                scoring_versions_seen.add(st.get("scoring_version"))
                if st.get("score_percent") is not None:
                    story_score_pts.append({**meta, "value": st["score_percent"]})
                story_recalled_pts.append({**meta, "value": st.get("recalled_facts_count", 0)})
                story_missed_pts.append({**meta, "value": st.get("missed_facts_count", 0)})
                story_inversions_pts.append({**meta, "value": st.get("chronological_inversions", 0)})

            # MindPlay
            mp = s["mindplay"]
            if mp.get("difficulty"):
                game_difficulties_seen.add(mp.get("difficulty"))
            if mp.get("completed") or mp.get("ch1_score") is not None:
                if mp.get("composite_accuracy_percent") is not None:
                    mindplay_acc_pts.append({**meta, "value": mp["composite_accuracy_percent"]})
                if mp.get("ch1_score") is not None:
                    mindplay_ch1_pts.append({**meta, "value": mp["ch1_score"]})
                if mp.get("ch3_reaction_ms") is not None:
                    mindplay_reaction_pts.append({**meta, "value": mp["ch3_reaction_ms"]})
                if mp.get("total_time_seconds") is not None:
                    mindplay_time_pts.append({**meta, "value": mp["total_time_seconds"]})

        # 6. Compute Trend Statistics per Metric
        analyzed_metrics: Dict[str, Dict[str, Any]] = {
            "voice": {
                "f0_mean_hz": self.trend_calculator.compute_metric_series(voice_f0_pts, "Mean Fundamental Frequency", "Hz"),
                "rms_energy": self.trend_calculator.compute_metric_series(voice_rms_pts, "RMS Signal Energy", "RMS"),
                "zero_crossing_rate": self.trend_calculator.compute_metric_series(voice_zcr_pts, "Zero-Crossing Rate", "Rate"),
                "low_energy_frame_ratio": self.trend_calculator.compute_metric_series(voice_pause_pts, "Low-Energy Frame Ratio", "Ratio"),
                "spectral_centroid_hz": self.trend_calculator.compute_metric_series(voice_centroid_pts, "Spectral Centroid", "Hz"),
                "duration_seconds": self.trend_calculator.compute_metric_series(voice_dur_pts, "Recording Duration", "s"),
            },
            "story": {
                "score_percent": self.trend_calculator.compute_metric_series(story_score_pts, "Recall Completeness", "%"),
                "recalled_facts_count": self.trend_calculator.compute_metric_series(story_recalled_pts, "Recalled Anchors", "units"),
                "missed_facts_count": self.trend_calculator.compute_metric_series(story_missed_pts, "Missed Anchors", "units"),
                "chronological_inversions": self.trend_calculator.compute_metric_series(story_inversions_pts, "Chronological Inversions", "count"),
            },
            "mindplay": {
                "composite_accuracy_percent": self.trend_calculator.compute_metric_series(mindplay_acc_pts, "Composite Accuracy", "%"),
                "ch1_score": self.trend_calculator.compute_metric_series(mindplay_ch1_pts, "Feature Binding Score", "pts"),
                "ch3_reaction_ms": self.trend_calculator.compute_metric_series(mindplay_reaction_pts, "Visual Search Reaction Latency", "ms"),
                "total_time_seconds": self.trend_calculator.compute_metric_series(mindplay_time_pts, "Total Challenge Time", "s"),
            }
        }

        # 7. Analyze Practice Engagement
        practice_summary = self._summarize_practice_engagement(valid_practices)

        # 8. Pairwise Recent vs Previous Session Comparison
        recent_vs_previous = self._compute_recent_session_comparison(valid_sessions)

        # 9. Multi-Modal Overview Timeline Labels
        timeline_labels = [s["date"] for s in valid_sessions]

        # 10. Compatibility Warnings
        compatibility_notes = []
        if len(story_ids_seen) > 1:
            compatibility_notes.append(
                f"Story Recall sessions evaluated different narrative texts ({', '.join(story_ids_seen)}). "
                "Different stories possess distinct lexical complexity; compare with caution."
            )
        if len(game_difficulties_seen) > 1:
            compatibility_notes.append(
                f"MindPlay sessions evaluated different game difficulty levels ({', '.join(game_difficulties_seen)})."
            )

        # 11. History Threshold Status
        history_threshold_status = "no_history"
        if total_sessions_analyzed == 1:
            history_threshold_status = "single_baseline"
        elif total_sessions_analyzed == 2:
            history_threshold_status = "pairwise_comparison"
        elif total_sessions_analyzed >= 3:
            history_threshold_status = "longitudinal_trend_available"

        return {
            "status": "success",
            "version": "1.6.0",
            "history_summary": {
                "total_sessions_received": len(raw_sessions or []),
                "valid_sessions_analyzed": total_sessions_analyzed,
                "excluded_sessions_count": len(excluded_sessions),
                "excluded_sessions": excluded_sessions,
                "history_threshold_status": history_threshold_status,
                "timeline_labels": timeline_labels,
                "date_range": {
                    "earliest": valid_sessions[0]["date"] if valid_sessions else None,
                    "latest": valid_sessions[-1]["date"] if valid_sessions else None,
                }
            },
            "metrics_domains": analyzed_metrics,
            "recent_vs_previous_comparison": recent_vs_previous,
            "practice_engagement": practice_summary,
            "compatibility_notes": compatibility_notes,
            "governance": {
                "scientific_notice": (
                    "Longitudinal changes in speech acoustics, story recall accuracy, or game reaction times "
                    "are influenced by recording hardware, environment, user wakefulness, and task familiarity. "
                    "They do NOT provide diagnostic certainty or indicate Alzheimer's disease progression or reversal."
                ),
                "practice_effects_disclaimer": (
                    "Performance gains upon repeated exposure to identical or similar cognitive tasks indicate "
                    "procedural familiarity and test-retest learning, not neurological restoration."
                )
            }
        }

    def _compute_recent_session_comparison(
        self,
        valid_sessions: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """Computes direct delta between the two most recent check-in sessions."""
        if len(valid_sessions) < 2:
            return None

        prev = valid_sessions[-2]
        curr = valid_sessions[-1]

        deltas: Dict[str, Any] = {}

        # Voice pause ratio
        curr_pause = curr["voice"]["metrics"].get("low_energy_frame_ratio")
        prev_pause = prev["voice"]["metrics"].get("low_energy_frame_ratio")
        if curr_pause is not None and prev_pause is not None:
            deltas["voice_pause_ratio"] = {
                "previous": round(prev_pause, 3),
                "current": round(curr_pause, 3),
                "delta": round(curr_pause - prev_pause, 3),
                "unit": "ratio"
            }

        # Story recall completeness
        curr_story = curr["story"].get("score_percent")
        prev_story = prev["story"].get("score_percent")
        if curr_story is not None and prev_story is not None:
            deltas["story_recall_percent"] = {
                "previous": round(prev_story, 1),
                "current": round(curr_story, 1),
                "delta": round(curr_story - prev_story, 1),
                "unit": "%"
            }

        # MindPlay composite accuracy
        curr_acc = curr["mindplay"].get("composite_accuracy_percent")
        prev_acc = prev["mindplay"].get("composite_accuracy_percent")
        if curr_acc is not None and prev_acc is not None:
            deltas["mindplay_accuracy_percent"] = {
                "previous": round(prev_acc, 1),
                "current": round(curr_acc, 1),
                "delta": round(curr_acc - prev_acc, 1),
                "unit": "%"
            }

        # MindPlay latency
        curr_rx = curr["mindplay"].get("ch3_reaction_ms")
        prev_rx = prev["mindplay"].get("ch3_reaction_ms")
        if curr_rx is not None and prev_rx is not None:
            deltas["mindplay_latency_ms"] = {
                "previous": round(prev_rx, 1),
                "current": round(curr_rx, 1),
                "delta": round(curr_rx - prev_rx, 1),
                "unit": "ms"
            }

        return {
            "previous_session_id": prev["session_id"],
            "previous_session_date": prev["date"],
            "current_session_id": curr["session_id"],
            "current_session_date": curr["date"],
            "metrics_deltas": deltas
        }

    def _summarize_practice_engagement(
        self,
        valid_practices: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Summarizes longitudinal practice drill activity."""
        total_completed = len(valid_practices)
        if total_completed == 0:
            return {
                "total_completed": 0,
                "unique_exercises_count": 0,
                "active_practice_days": 0,
                "total_practice_minutes": 0.0,
                "practice_consistency_label": "No Practice Recorded",
                "personal_bests": {},
                "cumulative_series": []
            }

        unique_drills = set(p["exercise_id"] for p in valid_practices)
        unique_dates = set(p["date"] for p in valid_practices)
        total_seconds = sum(float(p.get("duration_seconds") or 180.0) for p in valid_practices)

        # Personal bests per exercise
        personal_bests: Dict[str, Dict[str, Any]] = {}
        cumulative_mins = 0.0
        cumulative_series = []

        for p in valid_practices:
            ex_id = p["exercise_id"]
            title = p["exercise_title"]
            score = p.get("score")
            dur = float(p.get("duration_seconds") or 180.0)
            cumulative_mins += (dur / 60.0)

            cumulative_series.append({
                "date": p["date"],
                "exercise_id": ex_id,
                "exercise_title": title,
                "cumulative_minutes": round(cumulative_mins, 1)
            })

            if ex_id not in personal_bests:
                personal_bests[ex_id] = {
                    "exercise_title": title,
                    "completions": 0,
                    "best_score": score,
                    "total_seconds": 0.0,
                    "last_completed": p["timestamp"]
                }
            personal_bests[ex_id]["completions"] += 1
            personal_bests[ex_id]["total_seconds"] += dur
            personal_bests[ex_id]["last_completed"] = p["timestamp"]
            if score is not None:
                if personal_bests[ex_id]["best_score"] is None or score > personal_bests[ex_id]["best_score"]:
                    personal_bests[ex_id]["best_score"] = score

        # Consistency labeling
        label = "Starting Out"
        if total_completed >= 10 and len(unique_dates) >= 5:
            label = "Consistent Daily Routine"
        elif total_completed >= 4 and len(unique_dates) >= 2:
            label = "Active Regular Habit"
        elif total_completed >= 1:
            label = "Initial Practice Started"

        return {
            "total_completed": total_completed,
            "unique_exercises_count": len(unique_drills),
            "active_practice_days": len(unique_dates),
            "total_practice_minutes": round(total_seconds / 60.0, 1),
            "practice_consistency_label": label,
            "personal_bests": personal_bests,
            "cumulative_series": cumulative_series
        }


# Global singleton
_pattern_service = PatternAnalyticsService()


def get_pattern_analytics_service() -> PatternAnalyticsService:
    """Retrieve singleton PatternAnalyticsService."""
    return _pattern_service
