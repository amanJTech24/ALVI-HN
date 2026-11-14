"""
ALVI Practice Progress Tracking Service — backend/services/practice_progress.py
Tracks genuine activity completions, personal bests, and intra-individual trends across practice sessions.

GOVERNANCE & SCIENTIFIC PRINCIPLES:
- Familiarity Effect: Clarifies that improvements on repeated practice activities reflect task familiarity
  and procedural learning, rather than generalized or clinically proven cognitive enhancement.
- Honest Empty State: Returns transparent zero/empty indicators when no practice sessions have been logged.
"""

from datetime import datetime
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("alvi.practice_progress")


class PracticeProgressTracker:
    """Calculates factual progress metrics from client practice records."""

    def analyze_progress(self, practice_records: Optional[List[Dict[str, Any]]]) -> Dict[str, Any]:
        """
        Analyzes logged practice records and returns completion statistics,
        personal bests, and practice consistency.

        Args:
            practice_records: List of practice attempt dictionaries.

        Returns:
            Dict containing progress analysis or an honest empty state.
        """
        records = practice_records or []
        valid_records = [r for r in records if isinstance(r, dict)]

        if len(valid_records) == 0:
            return {
                "status": "success",
                "has_practice_history": False,
                "total_activities_completed": 0,
                "unique_exercises_count": 0,
                "total_practice_duration_seconds": 0,
                "personal_bests": {},
                "exercise_breakdown": {},
                "recent_activity": None,
                "consistency": {
                    "days_active_count": 0,
                    "consistency_label": "No Practice Logged",
                },
                "message": (
                    "No practice activities completed yet. Select any recommended activity from your "
                    "Cognitive Learning Path to begin logging your practice journey."
                ),
                "scientific_notice": (
                    "Practice activities are for mental engagement and skill practice. "
                    "Performance changes on specific tasks reflect familiarity and practice effects."
                ),
            }

        # Analyze completed activities (Task 9: exclude initiated-only, abandoned, and synthetic demo records)
        completed_records = [
            r for r in valid_records
            if not r.get("is_demo")
            and not r.get("is_sample")
            and str(r.get("status", "")).lower() != "initiated"
            and (r.get("completed") is True or str(r.get("status", "")).lower() == "completed" or (r.get("completed", True) and r.get("score") is not None and str(r.get("status", "")).lower() != "initiated"))
        ]
        total_completed = len(completed_records)

        total_duration = sum([float(r.get("duration_seconds") or 0.0) for r in completed_records])

        # Exercise Breakdown & Personal Bests
        breakdown: Dict[str, Dict[str, Any]] = {}
        personal_bests: Dict[str, float] = {}
        unique_dates = set()

        for r in completed_records:
            ex_id = r.get("exercise_id", "unspecified_exercise")
            score = r.get("score")
            ts = r.get("timestamp", "")
            if ts:
                try:
                    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    unique_dates.add(dt.date())
                except Exception:
                    unique_dates.add(ts[:10])

            if ex_id not in breakdown:
                breakdown[ex_id] = {
                    "exercise_id": ex_id,
                    "completions_count": 0,
                    "scores": [],
                    "best_score": None,
                    "last_practiced_at": ts,
                }

            breakdown[ex_id]["completions_count"] += 1
            breakdown[ex_id]["last_practiced_at"] = ts

            if score is not None:
                s_val = float(score)
                breakdown[ex_id]["scores"].append(s_val)
                if breakdown[ex_id]["best_score"] is None or s_val > breakdown[ex_id]["best_score"]:
                    breakdown[ex_id]["best_score"] = s_val

        # Populate personal bests map
        for ex_id, data in breakdown.items():
            if data["best_score"] is not None:
                personal_bests[ex_id] = round(data["best_score"], 1)

        # Consistency labeling
        days_active = len(unique_dates)
        if days_active >= 5:
            consistency_label = "Dedicated Practice"
        elif days_active >= 2:
            consistency_label = "Regular Practice"
        elif days_active == 1:
            consistency_label = "Initial Practice Started"
        else:
            consistency_label = "Occasional"

        # Recent activity
        latest_record = valid_records[-1] if len(valid_records) > 0 else None

        return {
            "status": "success",
            "has_practice_history": True,
            "total_activities_completed": total_completed,
            "unique_exercises_count": len(breakdown),
            "total_practice_duration_seconds": round(total_duration, 1),
            "personal_bests": personal_bests,
            "exercise_breakdown": breakdown,
            "recent_activity": {
                "exercise_id": latest_record.get("exercise_id"),
                "timestamp": latest_record.get("timestamp"),
                "score": latest_record.get("score"),
                "duration_seconds": latest_record.get("duration_seconds"),
            } if latest_record else None,
            "consistency": {
                "days_active_count": days_active,
                "consistency_label": consistency_label,
            },
            "scientific_notice": (
                "Repeated practice on familiar tasks naturally shows procedural learning and familiarity effects. "
                "Task improvements indicate practice proficiency rather than general cognitive restoration."
            ),
        }


# Global singleton instance
_tracker_instance: Optional[PracticeProgressTracker] = None


def get_practice_progress_tracker() -> PracticeProgressTracker:
    """Retrieve singleton PracticeProgressTracker."""
    global _tracker_instance
    if _tracker_instance is None:
        _tracker_instance = PracticeProgressTracker()
    return _tracker_instance

