"""
ALVI MindPlay Personalized Analytics Service
Provides longitudinal and comparative statistical tracking across multiple
completed MindPlay sessions for a single participant:
- Personal baseline calculations
- Accuracy & latency trajectory tracking
- Performance consistency & variance analysis (Coefficient of Variation)
- Safe handling of single or insufficient session histories
"""

import math
from typing import Any, Dict, List, Optional


class MindPlayAnalyticsService:
    """
    Computes statistical and trajectory analytics across historical MindPlay sessions.
    """

    MIN_SESSIONS_REQUIRED = 2

    def analyze_history(self, sessions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Evaluate a sequence of completed MindPlay sessions.
        """
        if not sessions or len(sessions) < self.MIN_SESSIONS_REQUIRED:
            count = len(sessions) if sessions else 0
            return {
                "status": "insufficient_history",
                "sessions_evaluated": count,
                "message": (
                    f"Not enough sessions to establish a personal cognitive baseline. "
                    f"At least {self.MIN_SESSIONS_REQUIRED} completed check-ins are required "
                    f"({count} currently recorded)."
                ),
                "has_baseline": False,
                "baseline_score": None,
                "metrics_trajectory": None
            }

        # Extract numeric series
        composite_scores: List[float] = []
        completion_times: List[float] = []
        reaction_times: List[float] = []
        ch1_scores: List[float] = []
        ch2_inversions: List[int] = []

        valid_sessions: List[Dict[str, Any]] = []

        for s in sessions:
            # Check for composite score directly or in nested metrics
            comp = s.get("composite_score")
            if comp is None and "metrics" in s:
                comp = s["metrics"].get("composite_score")
            if comp is not None:
                try:
                    composite_scores.append(float(comp))
                    valid_sessions.append(s)
                except (ValueError, TypeError):
                    continue

            # Time
            t_sec = s.get("total_time_seconds")
            if t_sec is not None:
                try:
                    completion_times.append(float(t_sec))
                except (ValueError, TypeError):
                    pass

            # Reaction time
            rt = s.get("ch3_reactionMs") or s.get("ch3_reaction_ms")
            if rt is None and "challenges" in s:
                rt = s["challenges"].get("ch3_find", {}).get("reaction_time_ms")
            if rt is not None:
                try:
                    reaction_times.append(float(rt))
                except (ValueError, TypeError):
                    pass

            # Ch1 score
            sc1 = s.get("ch1_score")
            if sc1 is None and "challenges" in s:
                sc1 = s["challenges"].get("ch1_remember", {}).get("ch1_score")
            if sc1 is not None:
                try:
                    ch1_scores.append(float(sc1))
                except (ValueError, TypeError):
                    pass

            # Ch2 inversions
            inv = s.get("ch2_inversions")
            if inv is None and "challenges" in s:
                inv = s["challenges"].get("ch2_sequence", {}).get("inversions_count")
            if inv is not None:
                try:
                    ch2_inversions.append(int(inv))
                except (ValueError, TypeError):
                    pass

        if len(composite_scores) < self.MIN_SESSIONS_REQUIRED:
            return {
                "status": "insufficient_history",
                "sessions_evaluated": len(composite_scores),
                "message": "Fewer than 2 valid scored sessions available for trajectory analytics.",
                "has_baseline": False,
                "baseline_score": None
            }

        # ── 1. Central Tendency & Dispersion ──────────────────────────────────
        n = len(composite_scores)
        mean_score = sum(composite_scores) / n
        best_score = max(composite_scores)
        worst_score = min(composite_scores)
        recent_score = composite_scores[-1]
        first_score = composite_scores[0]

        # Standard Deviation
        variance = sum((x - mean_score) ** 2 for x in composite_scores) / n
        std_dev = math.sqrt(variance)

        # Coefficient of Variation (CV) %
        cv_pct = (std_dev / mean_score * 100.0) if mean_score > 0 else 0.0

        if cv_pct < 8.0:
            consistency_label = "Highly Consistent"
            consistency_desc = "Cognitive task performance shows minimal variance across attempts."
        elif cv_pct < 20.0:
            consistency_label = "Moderate Consistency"
            consistency_desc = "Normal behavioral fluctuations observed between assessment sessions."
        else:
            consistency_label = "High Variability"
            consistency_desc = "Noticeable fluctuations across attempts (common with fatigue or distraction)."

        # ── 2. Performance Delta (Recent vs First / Baseline) ─────────────────
        score_delta = recent_score - first_score
        pct_change = ((recent_score - first_score) / first_score * 100.0) if first_score > 0 else 0.0

        if score_delta >= 5.0:
            trajectory_label = "Upward / Practice Effect"
            trajectory_desc = "Performance improved relative to initial assessment, indicating intact task learning."
        elif score_delta <= -10.0:
            trajectory_label = "Downward Drift"
            trajectory_desc = "Recent score dropped below initial baseline (monitor in subsequent sessions)."
        else:
            trajectory_label = "Stable Baseline"
            trajectory_desc = "Performance remains within stable bounds of personal cognitive baseline."

        # ── 3. Completion Time & Latency Trends ───────────────────────────────
        mean_time_sec = (sum(completion_times) / len(completion_times)) if completion_times else None
        time_delta_sec = (completion_times[-1] - completion_times[0]) if len(completion_times) >= 2 else None

        mean_reaction_ms = (sum(reaction_times) / len(reaction_times)) if reaction_times else None
        reaction_delta_ms = (reaction_times[-1] - reaction_times[0]) if len(reaction_times) >= 2 else None

        return {
            "status": "success",
            "sessions_evaluated": n,
            "has_baseline": True,
            "personal_baseline": {
                "mean_score": round(mean_score, 1),
                "best_score": round(best_score, 1),
                "worst_score": round(worst_score, 1),
                "recent_score": round(recent_score, 1),
                "standard_deviation": round(std_dev, 2),
                "coefficient_of_variation_pct": round(cv_pct, 1),
                "consistency_label": consistency_label,
                "consistency_description": consistency_desc
            },
            "trajectory": {
                "score_delta": round(score_delta, 1),
                "percent_change": round(pct_change, 1),
                "label": trajectory_label,
                "description": trajectory_desc
            },
            "subtask_averages": {
                "mean_completion_time_sec": round(mean_time_sec, 1) if mean_time_sec is not None else None,
                "completion_time_delta_sec": round(time_delta_sec, 1) if time_delta_sec is not None else None,
                "mean_reaction_time_ms": round(mean_reaction_ms, 1) if mean_reaction_ms is not None else None,
                "reaction_time_delta_ms": round(reaction_delta_ms, 1) if reaction_delta_ms is not None else None
            },
            "disclaimer": (
                "Personal cognitive analytics reflect within-subject task performance variability. "
                "Fluctuations may arise from circadian rhythm, fatigue, distraction, or interface familiarity. "
                "These metrics do NOT represent diagnostic clinical indicators."
            )
        }

