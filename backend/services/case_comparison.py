"""
ALVI Case Comparison Service — backend/services/case_comparison.py
Multi-modal cognitive performance synthesis and comparison engine.

Supports Three Distinct Comparison Modes:
- Mode A (Current Session Performance): Synthesizes completed assessment modules
  (Voice Check-in acoustic features, Story Recall NLP completeness & sequence,
  MindPlay cognitive game challenges), identifying missing/uncollected modules.
- Mode B (Personal Longitudinal History): Evaluates within-subject changes across
  repeated sessions (delta scores, reaction latency changes, baseline tracking),
  returning an honest empty state when fewer than 2 sessions exist.
- Mode C (Research Reference Comparison): Compares user acoustic features against
  empirical distributions from the cleaned DementiaNet corpus (100 recordings,
  80 speakers) with transparent non-clinical disclosures.

NO CLINICAL DIAGNOSTIC PREDICTIONS OR ALZHEIMER'S PROBABILITIES ARE FABRICATED.
"""

import logging
from typing import Any, Dict, List, Optional, Union
from backend.services.reference_statistics import (
    ReferenceStatisticsService,
    get_reference_statistics_service,
)

logger = logging.getLogger("alvi.case_comparison")


class CaseComparisonEngine:
    """Multi-modal case comparison and longitudinal tracking engine."""

    def __init__(self, ref_service: Optional[ReferenceStatisticsService] = None):
        self.ref_service = ref_service or get_reference_statistics_service()

    def compare(
        self,
        current_session: Dict[str, Any],
        history_sessions: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Executes unified case comparison across all three evaluation modes.

        Args:
            current_session: The active session payload (voice, story, mindplay).
            history_sessions: Optional list of previous session records for within-subject tracking.

        Returns:
            Dict containing mode_a_synthesis, mode_b_history, mode_c_reference, and metadata.
        """
        history_list = history_sessions or []

        mode_a = self.synthesize_current_session(current_session)
        mode_b = self.compare_personal_history(current_session, history_list)
        mode_c = self.compare_research_reference(current_session)

        return {
            "status": "success",
            "session_id": current_session.get("sessionId", "session_unassigned"),
            "timestamp": current_session.get("startedAt", ""),
            "mode_a_current_performance": mode_a,
            "mode_b_personal_history": mode_b,
            "mode_c_research_reference": mode_c,
            "governance": {
                "system": "ALVI Cognitive Performance & Case Comparison Engine",
                "version": "1.4.0",
                "clinical_notice": (
                    "ALVI provides multi-modal observational cognitive pattern monitoring. "
                    "All metrics are descriptive empirical measurements and do NOT constitute "
                    "a clinical diagnosis, medical risk percentage, or disease probability."
                ),
            },
        }

    # ─────────────────────────────────────────────────────────────────────────
    # MODE A: Current Session Multi-Modal Performance Synthesis
    # ─────────────────────────────────────────────────────────────────────────
    def synthesize_current_session(self, session: Dict[str, Any]) -> Dict[str, Any]:
        """Synthesize and validate completed vs uncollected assessment modules."""
        voice = session.get("voice") or {}
        story = session.get("story") or {}
        mindplay = session.get("mindplay") or {}

        # 1. Voice Check-in Evaluation
        voice_completed = bool(voice.get("completed"))
        voice_features = voice.get("features") or {}
        voice_summary = voice.get("audio_summary") or {}
        voice_pred = voice.get("research_prediction") or (
            voice.get("backend_result", {}).get("research_prediction") if isinstance(voice.get("backend_result"), dict) else None
        )

        voice_dur = float(
            voice.get("durationSeconds")
            or voice_summary.get("duration_seconds")
            or voice_features.get("duration_seconds")
            or voice_features.get("duration")
            or 0.0
        )
        has_valid_voice = voice_completed and (voice.get("isValid", True) is not False) and (voice_dur > 0)

        voice_synthesized = {
            "completed": voice_completed,
            "is_valid": voice.get("isValid", True) if voice_completed else False,
            "rejection_reason": voice.get("rejectionReason") if not voice.get("isValid", True) else None,
            "duration_seconds": round(voice_dur, 2),
            "measurements": {
                "f0_mean_hz": (
                    round(float(voice_summary.get("voiced_f0_mean_hz")), 2)
                    if voice_summary.get("voiced_f0_mean_hz") is not None
                    else (round(float(voice_features.get("f0_mean")), 2) if voice_features.get("f0_mean") is not None else None)
                ),
                "rms_amplitude": (
                    round(float(voice_summary.get("rms_energy_mean")), 4)
                    if voice_summary.get("rms_energy_mean") is not None
                    else (round(float(voice_features.get("rms_mean")), 4) if voice_features.get("rms_mean") is not None else (
                        round(float(voice_features.get("rms")), 4) if voice_features.get("rms") is not None else None
                    ))
                ),
                "zcr": (
                    round(float(voice_features.get("zcr_mean")), 4)
                    if voice_features.get("zcr_mean") is not None
                    else (round(float(voice_features.get("zcr")), 4) if voice_features.get("zcr") is not None else None)
                ),
                "low_energy_pause_ratio": (
                    round(float(voice_features.get("low_energy_frame_ratio")), 4)
                    if voice_features.get("low_energy_frame_ratio") is not None
                    else (round(float(voice_features.get("pause_ratio")), 4) if voice_features.get("pause_ratio") is not None else None)
                ),
                "low_energy_pause_count": (
                    int(voice_features.get("low_energy_interval_count"))
                    if voice_features.get("low_energy_interval_count") is not None
                    else (int(voice_features.get("pause_count")) if voice_features.get("pause_count") is not None else None)
                ),
                "spectral_centroid_hz": (
                    round(float(voice_summary.get("spectral_centroid_hz")), 1)
                    if voice_summary.get("spectral_centroid_hz") is not None
                    else (round(float(voice_features.get("spectral_centroid_mean")), 1) if voice_features.get("spectral_centroid_mean") is not None else (
                        round(float(voice_features.get("spectral_centroid")), 1) if voice_features.get("spectral_centroid") is not None else None
                    ))
                ),
            },
            "research_prediction": voice_pred,
        }

        # 2. Story Recall Evaluation
        story_completed = bool(story.get("completed"))
        recalled_facts = story.get("recalled_facts") or []
        missed_facts = story.get("missed_facts") or []
        story_score = float(story.get("score_percent") or 0.0)

        story_synthesized = {
            "completed": story_completed,
            "input_mode": story.get("input_mode", "voice"),
            "timing_seconds": round(float(story.get("durationSeconds") or story.get("timing_seconds") or 0.0), 2),
            "recalled_facts_count": len(recalled_facts),
            "target_facts_total": len(recalled_facts) + len(missed_facts) if (recalled_facts or missed_facts) else 8,
            "recalled_facts": recalled_facts,
            "missed_facts": missed_facts,
            "score_percent": round(story_score, 1),
            "has_transcript": bool(story.get("transcript") or story.get("recalled_text")),
        }

        # 3. MindPlay Cognitive Game Evaluation
        mindplay_completed = bool(mindplay.get("completed"))
        mp_synthesized = None
        if mindplay_completed or bool(mindplay.get("ch1_selected") or mindplay.get("ch3_reactionMs") or mindplay.get("ch3_reaction_ms")):
            ch1_score = int(mindplay.get("ch1_score") or (2 if mindplay.get("ch1_correct") else 0))
            ch1_correct = bool(mindplay.get("ch1_correct") or (ch1_score == 2))
            ch2_correct = bool(mindplay.get("ch2_correct"))
            ch3_correct = bool(mindplay.get("ch3_correct"))
            ch3_latency = mindplay.get("ch3_reactionMs")
            if ch3_latency is None:
                ch3_latency = mindplay.get("ch3_reaction_ms")
            ch3_latency_ms = round(float(ch3_latency), 1) if ch3_latency is not None else None

            correct_challenges_count = sum([ch1_correct, ch2_correct, ch3_correct])

            mp_synthesized = {
                "completed": True,
                "challenges_correct_count": correct_challenges_count,
                "challenges_total": 3,
                "total_time_seconds": round(float(mindplay.get("total_time_seconds") or 0.0), 1),
                "challenge_details": {
                    "ch1_dual_binding": {
                        "name": "Shape & Color Dual Binding",
                        "score": ch1_score,
                        "max_score": 2,
                        "is_correct": ch1_correct,
                        "selected_items": mindplay.get("ch1_selected") or [],
                    },
                    "ch2_chronology_sequence": {
                        "name": "Narrative Chronology Sequencing",
                        "is_correct": ch2_correct,
                        "status": "Correct Order" if ch2_correct else "Order Inverted / Transposed",
                    },
                    "ch3_visual_search": {
                        "name": "Visual Target Discrimination",
                        "is_correct": ch3_correct,
                        "reaction_time_ms": ch3_latency_ms,
                    },
                },
            }

        # 4. Overall Protocol Summary
        available_tasks = []
        if has_valid_voice:
            available_tasks.append("voice")
        if story_completed:
            available_tasks.append("story")
        if mp_synthesized is not None and mp_synthesized["completed"]:
            available_tasks.append("mindplay")

        missing_tasks = [t for t in ["voice", "story", "mindplay"] if t not in available_tasks]

        completion_status = "uncollected"
        if len(available_tasks) == 3:
            completion_status = "complete"
        elif len(available_tasks) > 0:
            completion_status = "partial"

        # Domain Level Status Summaries
        domain_summaries = {
            "acoustic_prosodic_domain": {
                "collected": has_valid_voice,
                "summary": (
                    f"Acoustic features extracted ({voice_synthesized['duration_seconds']}s audio)."
                    if has_valid_voice
                    else "Voice check-in was uncollected or rejected."
                ),
            },
            "episodic_memory_domain": {
                "collected": story_completed,
                "summary": (
                    f"Story recall achieved {story_synthesized['score_percent']}% retention ({story_synthesized['recalled_facts_count']} facts)."
                    if story_completed
                    else "Story recall was not administered in this session."
                ),
            },
            "executive_function_domain": {
                "collected": mp_synthesized is not None,
                "summary": (
                    f"MindPlay completed {mp_synthesized['challenges_correct_count']}/3 challenges correctly."
                    if mp_synthesized is not None
                    else "MindPlay executive games were not administered in this session."
                ),
            },
        }

        return {
            "completion_status": completion_status,
            "tasks_completed_count": len(available_tasks),
            "tasks_total": 3,
            "available_tasks": available_tasks,
            "missing_tasks": missing_tasks,
            "missing_tasks_note": (
                f"Missing tasks: {', '.join(missing_tasks)}. Complete all 3 activities for full multi-modal evaluation."
                if missing_tasks
                else "All 3 assessment modules completed."
            ),
            "voice": voice_synthesized,
            "story": story_synthesized,
            "mindplay": mp_synthesized,
            "domain_summaries": domain_summaries,
        }

    # ─────────────────────────────────────────────────────────────────────────
    # MODE B: Personal Longitudinal History Comparison
    # ─────────────────────────────────────────────────────────────────────────
    def compare_personal_history(
        self,
        current_session: Dict[str, Any],
        history_sessions: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Calculates within-subject longitudinal changes across repeated sessions.
        Returns an honest empty state when fewer than 2 total sessions are available.
        """
        # Valid historical sessions
        valid_history = [s for s in history_sessions if isinstance(s, dict)]
        total_session_count = len(valid_history) + 1  # history + current session

        if len(valid_history) < 1:
            return {
                "has_sufficient_history": False,
                "total_sessions_recorded": total_session_count,
                "minimum_required_sessions": 2,
                "message": (
                    "Personal longitudinal comparison requires at least 2 completed sessions. "
                    "Current session represents your initial baseline. Complete future check-ins "
                    "to monitor intra-individual trajectories over time."
                ),
                "metric_trajectories": {},
                "summary_delta": None,
            }

        # Compare current session with the most recent prior session and baseline (oldest)
        prior_session = valid_history[-1]
        baseline_session = valid_history[0]

        # Helper to compute numeric delta
        def _compute_delta(curr_val: Optional[Union[int, float]], prev_val: Optional[Union[int, float]], unit: str = "") -> Optional[Dict[str, Any]]:
            if curr_val is None or prev_val is None:
                return None
            c = float(curr_val)
            p = float(prev_val)
            abs_delta = round(c - p, 3)
            pct_delta = round(((c - p) / p * 100), 1) if p != 0 else 0.0

            # Neutral descriptive trajectory
            if abs(pct_delta) < 5.0:
                direction = "stable"
            elif pct_delta > 0:
                direction = "increased"
            else:
                direction = "decreased"

            return {
                "current_value": round(c, 3),
                "prior_value": round(p, 3),
                "absolute_delta": abs_delta,
                "percent_change": pct_delta,
                "unit": unit,
                "trajectory": direction,
            }

        # Extract values
        curr_story_score = (current_session.get("story") or {}).get("score_percent")
        prev_story_score = (prior_session.get("story") or {}).get("score_percent")

        curr_mp = current_session.get("mindplay") or {}
        prev_mp = prior_session.get("mindplay") or {}
        curr_latency = curr_mp.get("ch3_reactionMs") or curr_mp.get("ch3_reaction_ms")
        prev_latency = prev_mp.get("ch3_reactionMs") or prev_mp.get("ch3_reaction_ms")

        curr_voice = (current_session.get("voice") or {}).get("features") or {}
        prev_voice = (prior_session.get("voice") or {}).get("features") or {}
        curr_f0 = curr_voice.get("f0_mean")
        prev_f0 = prev_voice.get("f0_mean")
        curr_pause = curr_voice.get("low_energy_frame_ratio") or curr_voice.get("pause_ratio")
        prev_pause = prev_voice.get("low_energy_frame_ratio") or prev_voice.get("pause_ratio")
        curr_rms = curr_voice.get("rms_mean") or curr_voice.get("rms")
        prev_rms = prev_voice.get("rms_mean") or prev_voice.get("rms")

        trajectories = {
            "story_recall_accuracy": _compute_delta(curr_story_score, prev_story_score, "%"),
            "visual_search_latency": _compute_delta(curr_latency, prev_latency, "ms"),
            "voice_pitch_f0": _compute_delta(curr_f0, prev_f0, "Hz"),
            "voice_pause_ratio": _compute_delta(curr_pause, prev_pause, "ratio"),
            "voice_rms_energy": _compute_delta(curr_rms, prev_rms, ""),
        }

        # Clean null trajectories
        active_trajectories = {k: v for k, v in trajectories.items() if v is not None}

        return {
            "has_sufficient_history": True,
            "total_sessions_recorded": total_session_count,
            "prior_session_id": prior_session.get("sessionId"),
            "prior_session_date": prior_session.get("startedAt"),
            "baseline_session_id": baseline_session.get("sessionId"),
            "metric_trajectories": active_trajectories,
            "summary_delta": {
                "active_metric_count": len(active_trajectories),
                "interpretation": (
                    "Within-subject longitudinal comparison computed relative to preceding check-in. "
                    "Variations reflect normal day-to-day fluctuation or pacing shifts."
                ),
            },
        }

    # ─────────────────────────────────────────────────────────────────────────
    # MODE C: Research Reference Benchmark Comparison
    # ─────────────────────────────────────────────────────────────────────────
    def compare_research_reference(self, session: Dict[str, Any]) -> Dict[str, Any]:
        """
        Compares participant acoustic measurements against descriptive reference distributions
        derived from the cleaned DementiaNet corpus.
        """
        ref_data = self.ref_service.get_reference_statistics()
        ref_metrics = ref_data.get("acoustic_reference_metrics", {})
        provenance = ref_data.get("provenance", {})

        voice = session.get("voice") or {}
        features = voice.get("features") or {}
        summary = voice.get("audio_summary") or {}

        dur = float(
            voice.get("durationSeconds")
            or summary.get("duration_seconds")
            or features.get("duration_seconds")
            or features.get("duration")
            or 0.0
        )
        rms = summary.get("rms_energy_mean") if summary.get("rms_energy_mean") is not None else (
            features.get("rms_mean") if features.get("rms_mean") is not None else features.get("rms")
        )
        zcr = features.get("zcr_mean") if features.get("zcr_mean") is not None else features.get("zcr")
        pause_ratio = features.get("low_energy_frame_ratio") if features.get("low_energy_frame_ratio") is not None else features.get("pause_ratio")
        pause_count = features.get("low_energy_interval_count") if features.get("low_energy_interval_count") is not None else features.get("pause_count")
        centroid = summary.get("spectral_centroid_hz") if summary.get("spectral_centroid_hz") is not None else (
            features.get("spectral_centroid_mean") if features.get("spectral_centroid_mean") is not None else features.get("spectral_centroid")
        )
        f0_mean = summary.get("voiced_f0_mean_hz") if summary.get("voiced_f0_mean_hz") is not None else features.get("f0_mean")

        # Map current values to reference metric keys
        value_map = {
            "voice.f0_mean": float(f0_mean) if f0_mean is not None else None,
            "voice.pause_ratio": float(pause_ratio) if pause_ratio is not None else None,
            "voice.zcr": float(zcr) if zcr is not None else None,
            "voice.rms": float(rms) if rms is not None else None,
            "voice.spectral_centroid": float(centroid) if centroid is not None else None,
            "voice.duration": float(dur) if dur > 0 else None,
            "voice.pause_count": float(pause_count) if pause_count is not None else None,
        }

        benchmarks: List[Dict[str, Any]] = []

        for ref_key, user_val in value_map.items():
            ref_info = ref_metrics.get(ref_key)
            if not ref_info:
                continue

            dist = ref_info["distribution"]
            metric_name = ref_info["name"]
            unit = ref_info["unit"]
            q1 = dist.get("q1", 0.0)
            median = dist.get("median", 0.0)
            q3 = dist.get("q3", 0.0)
            min_val = dist.get("min", 0.0)
            max_val = dist.get("max", 0.0)

            if user_val is not None:
                in_iqr = q1 <= user_val <= q3
                in_range = min_val <= user_val <= max_val

                if in_iqr:
                    status_badge = "Within Reference IQR"
                    status_class = "within_iqr"
                elif in_range:
                    status_badge = "Within Cohort Range"
                    status_class = "within_range"
                else:
                    status_badge = "Variation from Cohort"
                    status_class = "variation"

                # % of median calculation
                percent_of_median = round((user_val / median * 100), 1) if median != 0 else 100.0
            else:
                status_badge = "Uncollected / Missing"
                status_class = "uncollected"
                percent_of_median = None

            benchmarks.append({
                "metric_key": ref_key,
                "name": metric_name,
                "unit": unit,
                "user_value": round(user_val, 4) if user_val is not None else None,
                "reference_median": median,
                "reference_q1": q1,
                "reference_q3": q3,
                "reference_min": min_val,
                "reference_max": max_val,
                "percent_of_median": percent_of_median,
                "status_badge": status_badge,
                "status_class": status_class,
                "description": ref_info.get("description", ""),
            })

        return {
            "status": "success",
            "provenance": provenance,
            "benchmarks": benchmarks,
            "disclosure": (
                "Empirical reference comparison derived from 100 cleaned DementiaNet interview recordings. "
                "This serves as an acoustic descriptive benchmark and does NOT represent clinical "
                "diagnostic criteria or disease probability."
            ),
        }


# Global singleton instance
_engine_instance: Optional[CaseComparisonEngine] = None


def get_case_comparison_engine() -> CaseComparisonEngine:
    """Retrieve singleton CaseComparisonEngine instance."""
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = CaseComparisonEngine()
    return _engine_instance

