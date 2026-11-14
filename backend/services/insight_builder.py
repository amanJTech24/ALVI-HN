"""
ALVI Insight Context Builder — backend/services/insight_builder.py

Extracts genuine, grounded measurements from active sessions, longitudinal history,
and learning recommendations to form prompt contexts for Gemma 4 LLM inference.
Also provides a deterministic rule-based fallback when external AI is unavailable.
"""

import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from backend.services.history_normalization import HistoryNormalizer
from backend.services.insight_validation import STANDARD_AI_DISCLAIMER

logger = logging.getLogger("alvi.insight_builder")


class InsightContextBuilder:
    """Extracts genuine measurements and builds structured prompt contexts."""

    def __init__(self):
        self.normalizer = HistoryNormalizer()

    def extract_ground_metrics(
        self,
        current_session: Optional[Dict[str, Any]],
        history_sessions: Optional[List[Dict[str, Any]]] = None,
        practice_history: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Extracts verified numeric and categorical metrics from the active session
        and historical sessions. Only authentic, present metrics are extracted.
        """
        metrics: Dict[str, Any] = {}
        curr = current_session or {}

        # ── 1. Voice Acoustic Metrics ──────────────────────────────────────────
        voice = curr.get("voice") or {}
        if voice.get("completed") or voice.get("features") or voice.get("audio_summary"):
            feats = voice.get("features") or voice.get("acoustic_features") or {}
            audio_sum = voice.get("audio_summary") or {}
            pred = voice.get("research_prediction") or {}

            v_metrics: Dict[str, Any] = {}
            if "durationSeconds" in voice or "duration_seconds" in audio_sum:
                v_metrics["duration_seconds"] = round(float(voice.get("durationSeconds") or audio_sum.get("duration_seconds", 0)), 1)
            if "mean_f0" in feats or "pitch_hz" in feats:
                v_metrics["pitch_f0_hz"] = round(float(feats.get("mean_f0") or feats.get("pitch_hz", 0)), 1)
            if "rms" in feats or "rms_energy" in feats:
                v_metrics["rms_energy"] = round(float(feats.get("rms") or feats.get("rms_energy", 0)), 4)
            if "zcr" in feats or "zero_crossing_rate" in feats:
                v_metrics["zero_crossing_rate"] = round(float(feats.get("zcr") or feats.get("zero_crossing_rate", 0)), 4)
            if "low_energy_frame_ratio" in feats or "pause_ratio" in feats:
                v_metrics["pause_ratio"] = round(float(feats.get("low_energy_frame_ratio") or feats.get("pause_ratio", 0)), 3)
            if "pause_count" in feats:
                v_metrics["pause_count"] = int(feats.get("pause_count", 0))
            if "predicted_label" in pred:
                v_metrics["research_label"] = str(pred.get("predicted_label"))
            if "probability" in pred:
                v_metrics["research_probability"] = round(float(pred.get("probability", 0)), 3)

            if v_metrics:
                metrics["voice"] = v_metrics

        # ── 2. Story Recall NLP Metrics ─────────────────────────────────────────
        story = curr.get("story") or {}
        if story.get("completed") or story.get("score_percent") is not None or story.get("composite_score") is not None:
            s_metrics: Dict[str, Any] = {}
            score = story.get("score_percent") if story.get("score_percent") is not None else story.get("composite_score")
            if score is not None:
                s_metrics["recall_score_percent"] = round(float(score), 1)
            if story.get("performance_band"):
                s_metrics["performance_band"] = str(story.get("performance_band"))
            if story.get("recalled_facts") is not None:
                recalled = story.get("recalled_facts")
                s_metrics["recalled_facts_count"] = len(recalled) if isinstance(recalled, list) else int(recalled)
            if story.get("missed_facts") is not None:
                missed = story.get("missed_facts")
                s_metrics["missed_facts_count"] = len(missed) if isinstance(missed, list) else int(missed)
            if story.get("intrusions_detected") is not None:
                intrusions = story.get("intrusions_detected")
                s_metrics["intrusions_count"] = len(intrusions) if isinstance(intrusions, list) else int(intrusions)
            if story.get("input_mode"):
                s_metrics["input_mode"] = str(story.get("input_mode"))

            metrics["story"] = s_metrics

        # ── 3. MindPlay Cognitive Game Metrics ───────────────────────────────────
        mindplay = curr.get("mindplay") or {}
        if mindplay.get("completed") or mindplay.get("composite_score") is not None:
            m_metrics: Dict[str, Any] = {}
            if mindplay.get("composite_score") is not None:
                m_metrics["composite_score"] = round(float(mindplay.get("composite_score")), 1)
            if mindplay.get("performance_band"):
                m_metrics["performance_band"] = str(mindplay.get("performance_band"))
            if mindplay.get("ch1_score") is not None:
                m_metrics["dual_feature_memory_score"] = int(mindplay.get("ch1_score"))
            if mindplay.get("ch2_correct") is not None:
                m_metrics["temporal_sequencing_correct"] = bool(mindplay.get("ch2_correct"))
            if mindplay.get("ch3_reactionMs") is not None or mindplay.get("ch3_reaction_ms") is not None:
                m_metrics["visual_search_latency_ms"] = round(float(mindplay.get("ch3_reactionMs") or mindplay.get("ch3_reaction_ms")), 1)
            if mindplay.get("ch3_correct") is not None:
                m_metrics["visual_search_correct"] = bool(mindplay.get("ch3_correct"))

            metrics["mindplay"] = m_metrics

        # ── 4. Longitudinal History Summary ─────────────────────────────────────
        if history_sessions and len(history_sessions) > 0:
            valid_sessions, _ = self.normalizer.normalize_sessions(history_sessions, include_demo=False)
            metrics["longitudinal"] = {
                "total_valid_prior_sessions": len(valid_sessions),
                "earliest_date": valid_sessions[0]["date"] if valid_sessions else None,
                "latest_date": valid_sessions[-1]["date"] if valid_sessions else None
            }

        # ── 5. Practice History Summary ─────────────────────────────────────────
        if practice_history and len(practice_history) > 0:
            valid_prac, _ = self.normalizer.normalize_practice_records(practice_history, include_demo=False)
            completed_prac = [p for p in valid_prac if p.get("completed")]
            metrics["practice"] = {
                "completed_practice_activities": len(completed_prac),
                "total_recorded_attempts": len(valid_prac)
            }

        return metrics

    def build_prompt_context(
        self,
        current_session: Optional[Dict[str, Any]],
        history_sessions: Optional[List[Dict[str, Any]]] = None,
        practice_history: Optional[List[Dict[str, Any]]] = None,
        learning_recommendations: Optional[Dict[str, Any]] = None
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Builds the grounded system prompt and JSON schema instructions for Gemma 4.

        Returns:
            Tuple of (formatted_prompt_string, ground_metrics_dict).
        """
        ground_metrics = self.extract_ground_metrics(current_session, history_sessions, practice_history)

        # Build context summary text
        metrics_json_str = json.dumps(ground_metrics, indent=2)
        rec_json_str = json.dumps(learning_recommendations or {}, indent=2)

        prompt = f"""You are the ALVI Cognitive Intelligence Explanation Engine, powered by Gemma 4.
Your purpose is to provide clear, compassionate, and scientifically grounded explanations of acoustic
voice features, narrative recall performance, and cognitive game measurements collected during an ALVI check-in.

STRICT MEDICAL BOUNDARIES & COMPLIANCE RULES:
1. NON-DIAGNOSTIC: ALVI is an exploratory research screening prototype, NOT a medical device. You must NEVER give a medical diagnosis, predict Alzheimer's disease progression, assign dementia stages, or imply definitive cognitive impairment.
2. GROUNDEDNESS: Refer ONLY to the measurements provided in the GROUNDED METRICS section below. Do NOT hallucinate scores, baseline comparisons, or tasks that were not completed.
3. OBJECTIVITY: Explain what specific measurements mean in neutral, educational terms (e.g., pause ratio reflects acoustic vocal pacing, information units reflect episodic story recall completeness, reaction time reflects visual discrimination latency).
4. OUTPUT FORMAT: You must return a SINGLE, valid JSON object with EXACTLY the keys specified below. Do not wrap in markdown code blocks if possible, or use standard ```json ``` formatting.

REQUIRED JSON SCHEMA:
{{
  "session_overview": "A concise 2-3 sentence summary of the active check-in session and what tasks were performed.",
  "voice_observations": "An objective explanation of acoustic measurements (pitch, vocal energy, pause ratio, speaking pacing) based on real numbers.",
  "memory_observations": "An objective summary of episodic story recall completeness, recalled vs missed facts, and information units.",
  "executive_observations": "An objective summary of MindPlay challenges (paired association, chronological sequencing, visual search reaction latency).",
  "strengths": [
    "Specific observed cognitive or vocal strength with grounded metric",
    "Another observed strength"
  ],
  "growth_opportunities": [
    "Specific area where additional practice or monitoring is warranted",
    "Another growth opportunity"
  ],
  "recommended_focus": [
    "Targeted cognitive practice domain or exercise",
    "Recommended check-in pacing"
  ]
}}

=== GROUNDED METRICS ===
{metrics_json_str}

=== LEARNING RECOMMENDATIONS CONTEXT ===
{rec_json_str}
"""
        return prompt, ground_metrics

    def build_chat_prompt(
        self,
        question: str,
        ground_metrics: Dict[str, Any],
        chat_history: Optional[List[Dict[str, str]]] = None
    ) -> str:
        """
        Builds prompt for interactive Q&A grounded in the user's authentic measurements.
        """
        history_text = ""
        if chat_history:
            for turn in chat_history[-6:]:  # Keep recent 3 turns
                role = turn.get("role", "user").capitalize()
                content = turn.get("content", "")
                history_text += f"{role}: {content}\n"

        prompt = f"""You are the ALVI Cognitive Assistant, powered by Gemma 4.
Answer the user's question directly, empathetically, and educationally.

STRICT COMPLIANCE RULES:
1. Never provide a clinical medical diagnosis or say the user has Alzheimer's disease or dementia.
2. Ground all answers in the user's authentic session measurements provided below.
3. If asked for medical advice or diagnostic staging, clearly clarify that ALVI is a research screening tool and suggest consulting a healthcare professional.
4. Keep answers concise, clear, and informative (2-4 paragraphs).

=== USER GROUNDED METRICS ===
{json.dumps(ground_metrics, indent=2)}

=== CONVERSATION HISTORY ===
{history_text}
User: {question}
Assistant:"""
        return prompt

    def generate_deterministic_fallback(
        self,
        ground_metrics: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generates a deterministic, rule-based explanation when external AI is unavailable.
        Uses real metrics to provide high-quality, transparent observations.
        """
        voice = ground_metrics.get("voice", {})
        story = ground_metrics.get("story", {})
        mindplay = ground_metrics.get("mindplay", {})
        longitudinal = ground_metrics.get("longitudinal", {})

        # Overview
        tasks = []
        if voice: tasks.append("Acoustic Voice Check-in")
        if story: tasks.append("Narrative Story Recall")
        if mindplay: tasks.append("MindPlay Cognitive Challenges")
        task_list_str = ", ".join(tasks) if tasks else "general assessment"

        overview = (
            f"This session recorded performance across {task_list_str}. "
            "Measurements were gathered using ALVI's research-grade acoustic and NLP analytics."
        )

        # Voice observations
        if voice:
            pause_pct = f"{round(voice.get('pause_ratio', 0) * 100, 1)}%" if 'pause_ratio' in voice else "standard"
            duration = f"{voice.get('duration_seconds')}s" if 'duration_seconds' in voice else "recorded duration"
            pitch = f"{voice.get('pitch_f0_hz')} Hz" if 'pitch_f0_hz' in voice else "normal pitch"
            voice_obs = (
                f"Speech analysis recorded an audio duration of {duration} with mean fundamental frequency (F0) of {pitch}. "
                f"Low-energy acoustic pauses accounted for {pause_pct} of speech frames."
            )
        else:
            voice_obs = "Voice check-in was not completed in this session."

        # Memory observations
        if story:
            score = story.get("recall_score_percent", "N/A")
            recalled = story.get("recalled_facts_count", "N/A")
            missed = story.get("missed_facts_count", "N/A")
            band = story.get("performance_band", "Completed")
            mem_obs = (
                f"Narrative recall achieved a composite score of {score}% ({band} band). "
                f"The response successfully retrieved {recalled} core story anchor units, with {missed} omitted units."
            )
        else:
            mem_obs = "Story Recall was not completed in this session."

        # Executive observations
        if mindplay:
            score = mindplay.get("composite_score", "N/A")
            band = mindplay.get("performance_band", "Completed")
            latency = f"{mindplay.get('visual_search_latency_ms')} ms" if 'visual_search_latency_ms' in mindplay else "N/A"
            exec_obs = (
                f"MindPlay cognitive challenges scored {score}% ({band} band). "
                f"Visual search discrimination recorded an average reaction latency of {latency}."
            )
        else:
            exec_obs = "MindPlay challenges were not completed in this session."

        # Strengths & Growth
        strengths = []
        if story and story.get("recall_score_percent", 0) >= 70:
            strengths.append(f"Strong narrative memory retention ({story.get('recall_score_percent')}% anchor retrieval).")
        if mindplay and mindplay.get("temporal_sequencing_correct"):
            strengths.append("Accurate chronological event sequencing in MindPlay.")
        if voice and voice.get("pause_ratio", 1.0) < 0.25:
            strengths.append("Continuous, fluid vocal pacing with low pause overhead.")
        if not strengths:
            strengths.append("Successful completion of cognitive check-in tasks.")

        growth = []
        if story and story.get("missed_facts_count", 0) > 2:
            growth.append(f"Episodic anchor detail retention ({story.get('missed_facts_count')} missed narrative units).")
        if mindplay and mindplay.get("visual_search_latency_ms", 0) > 3000:
            growth.append("Visual target discrimination response latency under timed distraction.")
        if voice and voice.get("pause_ratio", 0) > 0.30:
            growth.append("Descriptive speech continuity and pause interval reduction.")
        if not growth:
            growth.append("Maintain consistent longitudinal check-ins to track baseline stability.")

        focus = [
            "Practice narrative retell drills to reinforce episodic detail anchoring.",
            "Complete scheduled weekly check-ins to establish long-term trend baselines."
        ]

        return {
            "session_overview": overview,
            "voice_observations": voice_obs,
            "memory_observations": mem_obs,
            "executive_observations": exec_obs,
            "strengths": strengths,
            "growth_opportunities": growth,
            "recommended_focus": focus,
            "disclaimer": STANDARD_AI_DISCLAIMER,
            "grounded_metrics": ground_metrics,
            "fallback_mode": True
        }
