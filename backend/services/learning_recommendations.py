"""
ALVI Learning Recommendations Service — backend/services/learning_recommendations.py
Deterministic, rule-based recommendation engine for personalized cognitive practice activities.

Maps actual user performance measurements from completed ALVI tasks
(Voice Check-in, Story Recall, MindPlay) to targeted practice activities.

GOVERNANCE & CLINICAL DISCLAIMERS:
- Transparent and rule-based: Explains exact reasons and metrics for each recommendation.
- Non-diagnostic: Practice activities are cognitive exercises for memory, attention, sequencing,
  and verbal fluency. They are NOT medical treatment or clinically validated therapy.
- Honest missing data handling: Displays a transparent starter path for new users without claiming
  fabricated personal observations.
"""

from functools import lru_cache
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger("alvi.learning_recommendations")

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
EXERCISE_CATALOG_PATH = PROJECT_ROOT / "backend" / "data" / "exercise_catalog.json"


@lru_cache(maxsize=1)
def load_exercise_catalog() -> Dict[str, Any]:
    """Loads and caches the structured exercise catalog."""
    if not EXERCISE_CATALOG_PATH.exists():
        logger.error("Exercise catalog not found at %s", EXERCISE_CATALOG_PATH)
        return {"version": "0.0.0", "exercises": []}
    try:
        with open(EXERCISE_CATALOG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error("Failed to parse exercise catalog at %s: %s", EXERCISE_CATALOG_PATH, e)
        return {"version": "0.0.0", "exercises": []}


class LearningRecommendationEngine:
    """Evaluates multi-modal assessment measurements and generates practice recommendations."""

    def __init__(self, catalog: Optional[Dict[str, Any]] = None):
        self.catalog_data = catalog or load_exercise_catalog()
        self.catalog_map = {
            ex["exercise_id"]: ex for ex in self.catalog_data.get("exercises", [])
        }

    def get_catalog(self) -> Dict[str, Any]:
        """Returns the exercise catalog dictionary."""
        return self.catalog_data

    def recommend(
        self,
        current_session: Optional[Dict[str, Any]] = None,
        history_sessions: Optional[List[Dict[str, Any]]] = None,
        practice_history: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Generates deterministic, explainable recommendations based on real ALVI task results.

        Args:
            current_session: Active check-in session dictionary (voice, story, mindplay).
            history_sessions: List of prior check-in sessions.
            practice_history: List of prior practice completions.

        Returns:
            Dict containing recommended exercises, explanations, supporting metrics, and starter flags.
        """
        session = current_session or {}
        past_sessions = history_sessions or []
        past_practice = practice_history or []

        voice = session.get("voice") or {}
        story = session.get("story") or {}
        mindplay = session.get("mindplay") or {}

        # 1. Detect which assessment modules were actually completed
        has_voice = bool(voice.get("completed")) and (float(voice.get("durationSeconds") or (voice.get("features") or {}).get("duration") or 0.0) > 0)
        has_story = bool(story.get("completed")) and (story.get("score_percent") is not None or bool(story.get("recalled_facts")))
        has_mindplay = bool(mindplay.get("completed")) or bool(mindplay.get("ch1_selected") or mindplay.get("ch3_reactionMs") or mindplay.get("ch3_reaction_ms"))

        completed_tasks = []
        if has_voice:
            completed_tasks.append("voice")
        if has_story:
            completed_tasks.append("story")
        if has_mindplay:
            completed_tasks.append("mindplay")

        # 2. Case: New user with NO completed assessments
        if len(completed_tasks) == 0:
            return self._build_starter_path(past_practice)

        # 3. Case: User has completed assessments — Evaluate opportunities
        recommendations = []
        opportunities_detected = []

        # Opportunity A: Story Recall Fact Retention
        if has_story:
            story_score = float(story.get("score_percent") or 0.0)
            recalled_facts = story.get("recalled_facts") or []
            missed_facts = story.get("missed_facts") or []
            total_facts = len(recalled_facts) + len(missed_facts) if (recalled_facts or missed_facts) else 8

            if story_score < 75.0 or len(missed_facts) >= 2:
                ex = self.catalog_map.get("ex_narrative_retell_foundations")
                if ex:
                    metric_str = f"{story_score}% accuracy ({len(recalled_facts)} of {total_facts} anchors recalled)"
                    reason_str = (
                        f"Story Recall achieved {story_score}% anchor retention with {len(missed_facts)} omitted details. "
                        "Listening and retelling practice strengthens episodic memory retrieval."
                    )
                    recommendations.append(
                        self._create_recommendation(
                            ex=ex,
                            priority=1,
                            priority_label="High Priority",
                            supporting_metric=metric_str,
                            reason=reason_str,
                            opportunity="Narrative Information Recall",
                        )
                    )
                    opportunities_detected.append("Story Recall anchor completeness")

        # Opportunity B: MindPlay Chronological Sequencing (Challenge 2)
        if has_mindplay:
            ch2_correct = bool(mindplay.get("ch2_correct"))
            if not ch2_correct:
                ex = self.catalog_map.get("ex_temporal_chronology_builder")
                if ex:
                    recommendations.append(
                        self._create_recommendation(
                            ex=ex,
                            priority=1,
                            priority_label="High Priority",
                            supporting_metric="Sequence transposed / inverted",
                            reason=(
                                "MindPlay Challenge 2 detected event order transpositions. "
                                "Chronological reordering exercises reinforce executive sequencing and temporal working memory."
                            ),
                            opportunity="Chronological Event Organization",
                        )
                    )
                    opportunities_detected.append("Event chronology sequencing")

        # Opportunity C: MindPlay Dual Feature Memory Binding (Challenge 1)
        if has_mindplay:
            ch1_score = int(mindplay.get("ch1_score") or (2 if mindplay.get("ch1_correct") else 0))
            ch1_correct = bool(mindplay.get("ch1_correct") or ch1_score == 2)
            if not ch1_correct or ch1_score < 2:
                ex = self.catalog_map.get("ex_dual_feature_binding")
                if ex:
                    recommendations.append(
                        self._create_recommendation(
                            ex=ex,
                            priority=1,
                            priority_label="High Priority",
                            supporting_metric=f"{ch1_score}/2 targets identified",
                            reason=(
                                f"MindPlay Challenge 1 identified {ch1_score} of 2 targets. "
                                "Dual-feature memory binding practice helps distinguish target narrative items from plausible distractor lures."
                            ),
                            opportunity="Visual-Verbal Feature Binding",
                        )
                    )
                    opportunities_detected.append("Dual-feature item memory")

        # Opportunity D: MindPlay Visual Search & Reaction Latency (Challenge 3)
        if has_mindplay:
            ch3_latency = mindplay.get("ch3_reactionMs")
            if ch3_latency is None:
                ch3_latency = mindplay.get("ch3_reaction_ms")
            ch3_correct = bool(mindplay.get("ch3_correct"))

            if (ch3_latency is not None and float(ch3_latency) > 3500.0) or (not ch3_correct):
                ex = self.catalog_map.get("ex_visual_search_agility")
                if ex:
                    lat_str = f"{round(float(ch3_latency))} ms latency" if ch3_latency is not None else "Target missed"
                    recommendations.append(
                        self._create_recommendation(
                            ex=ex,
                            priority=2,
                            priority_label="Medium Priority",
                            supporting_metric=lat_str,
                            reason=(
                                f"Visual search latency was {round(float(ch3_latency))} ms. "
                                "Target discrimination drills encourage focused visual scanning and prompt motor selection."
                                if ch3_latency is not None
                                else "Visual search challenge was missed. Practicing target scanning sharpens selective visual attention."
                            ),
                            opportunity="Visual Attention & Reaction Latency",
                        )
                    )
                    opportunities_detected.append("Visual search latency")

        # Opportunity E: Voice Check-in Hesitation Dynamics
        if has_voice:
            voice_features = voice.get("features") or {}
            pause_ratio = float(voice_features.get("low_energy_frame_ratio") or voice_features.get("pause_ratio") or 0.0)
            pause_count = int(voice_features.get("low_energy_interval_count") or voice_features.get("pause_count") or 0)
            dur = float(voice.get("durationSeconds") or voice_features.get("duration") or 0.0)

            if pause_ratio > 0.28 or pause_count >= 8 or (dur > 0 and dur < 15.0):
                ex = self.catalog_map.get("ex_spontaneous_speech_description")
                if ex:
                    recommendations.append(
                        self._create_recommendation(
                            ex=ex,
                            priority=2,
                            priority_label="Medium Priority",
                            supporting_metric=f"{round(pause_ratio * 100, 1)}% pause proxy ({pause_count} intervals)",
                            reason=(
                                f"Speech sample exhibited {round(pause_ratio * 100, 1)}% low-energy pauses. "
                                "Gentle descriptive picture narration builds continuous, relaxed verbal pacing without time pressure."
                            ),
                            opportunity="Spontaneous Verbal Fluency",
                        )
                    )
                    opportunities_detected.append("Speech fluency & pacing")

        # Opportunity F: High Performance / Routine Maintenance
        if len(recommendations) == 0:
            # User performed strongly across all evaluated tasks
            ex_review = self.catalog_map.get("ex_full_trio_review")
            ex_search = self.catalog_map.get("ex_visual_search_agility")
            ex_story = self.catalog_map.get("ex_narrative_retell_foundations")

            if ex_review:
                recommendations.append(
                    self._create_recommendation(
                        ex=ex_review,
                        priority=3,
                        priority_label="Maintenance Practice",
                        supporting_metric="Strong scores across all completed tasks",
                        reason=(
                            "All recent check-in activities showed robust performance. "
                            "Continuing routine check-ins helps preserve healthy cognitive agility and update your longitudinal baseline."
                        ),
                        opportunity="Longitudinal Maintenance",
                    )
                )
            if ex_story:
                recommendations.append(
                    self._create_recommendation(
                        ex=ex_story,
                        priority=3,
                        priority_label="Enrichment Practice",
                        supporting_metric="Preserved anchor recall",
                        reason="Narrative storytelling practice sustains episodic memory precision.",
                        opportunity="Narrative Enrichment",
                    )
                )
            if ex_search:
                recommendations.append(
                    self._create_recommendation(
                        ex=ex_search,
                        priority=3,
                        priority_label="Speed Challenge",
                        supporting_metric="Prompt search responses",
                        reason="Visual target discrimination practice maintains rapid processing speed.",
                        opportunity="Visual Agility",
                    )
                )

        # 4. History Rotation Adjustment:
        # If the top exercise was completed in the very last practice attempt, move it slightly down to ensure variety
        if len(past_practice) > 0 and len(recommendations) > 1:
            last_practiced_id = past_practice[-1].get("exercise_id")
            if recommendations[0]["exercise_id"] == last_practiced_id:
                # Rotate first exercise to index 1
                recommendations.insert(1, recommendations.pop(0))

        # Build practice order list
        suggested_order = [r["exercise_id"] for r in recommendations]

        return {
            "status": "success",
            "is_starter_path": False,
            "tasks_evaluated_count": len(completed_tasks),
            "completed_tasks": completed_tasks,
            "opportunities_identified": opportunities_detected,
            "recommended_exercises": recommendations,
            "suggested_practice_order": suggested_order,
            "total_recommendations": len(recommendations),
            "governance": {
                "recommendation_method": "Deterministic Rule-Based Behavioral Mapping (v1.0)",
                "clinical_notice": (
                    "ALVI practice recommendations are designed for cognitive stimulation and skill engagement. "
                    "They are NOT medical treatment, clinical rehabilitation, or a cure for neurodegenerative disease."
                ),
            },
        }

    def _build_starter_path(self, past_practice: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Builds a beginner-friendly starter practice path for users with no completed assessments."""
        starter_ids = [
            "ex_spontaneous_speech_description",
            "ex_narrative_retell_foundations",
            "ex_dual_feature_binding",
        ]
        starter_recs = []
        for idx, ex_id in enumerate(starter_ids):
            ex = self.catalog_map.get(ex_id)
            if ex:
                starter_recs.append(
                    self._create_recommendation(
                        ex=ex,
                        priority=idx + 1,
                        priority_label="Starter Activity",
                        supporting_metric="Initial setup / No prior check-in recorded",
                        reason=f"Recommended starter exercise to introduce you to {ex['skill_practiced'].lower()}.",
                        opportunity="Introductory Cognitive Practice",
                    )
                )

        return {
            "status": "success",
            "is_starter_path": True,
            "tasks_evaluated_count": 0,
            "completed_tasks": [],
            "opportunities_identified": ["Initial baseline establishment"],
            "recommended_exercises": starter_recs,
            "suggested_practice_order": [r["exercise_id"] for r in starter_recs],
            "total_recommendations": len(starter_recs),
            "starter_path_note": (
                "Welcome to ALVI! No prior check-in results were found. "
                "This starter practice plan introduces descriptive speech, story recall, and memory binding. "
                "Complete a full check-in anytime to personalize your practice recommendations."
            ),
            "governance": {
                "recommendation_method": "Default Starter Curriculum (v1.0)",
                "clinical_notice": (
                    "ALVI practice activities are experimental cognitive stimulation exercises. "
                    "They do NOT provide medical treatment or clinical diagnosis."
                ),
            },
        }

    def _create_recommendation(
        self,
        ex: Dict[str, Any],
        priority: int,
        priority_label: str,
        supporting_metric: str,
        reason: str,
        opportunity: str,
    ) -> Dict[str, Any]:
        """Formats an exercise definition into a concrete recommendation item."""
        return {
            "exercise_id": ex["exercise_id"],
            "display_name": ex["display_name"],
            "skill_practiced": ex["skill_practiced"],
            "category": ex["category"],
            "difficulty": ex["difficulty"],
            "estimated_duration": ex["estimated_duration"],
            "estimated_duration_seconds": ex["estimated_duration_seconds"],
            "target_activity_url": ex["route"],
            "target_activity": ex["target_activity"],
            "instructions": ex["instructions"],
            "priority": priority,
            "priority_label": priority_label,
            "opportunity_targeted": opportunity,
            "supporting_metric": supporting_metric,
            "recommendation_reason": reason,
        }


# Global singleton instance
_engine_instance: Optional[LearningRecommendationEngine] = None


def get_learning_recommendation_engine() -> LearningRecommendationEngine:
    """Retrieve singleton LearningRecommendationEngine."""
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = LearningRecommendationEngine()
    return _engine_instance

