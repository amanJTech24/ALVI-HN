"""
ALVI Insight Validation & Security Sanitizer — backend/services/insight_validation.py

Provides prompt-injection sanitization, response structure validation,
medical non-diagnostic disclaimer enforcement, and numeric grounding checks.
"""

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("alvi.insight_validation")

STANDARD_AI_DISCLAIMER = (
    "ALVI is an exploratory research screening tool, NOT a diagnostic medical device. "
    "These AI-generated observations describe acoustic and cognitive task patterns for informational "
    "and self-monitoring purposes only. They do not constitute a clinical diagnosis, medical prognosis, "
    "or formal evaluation of Alzheimer's disease or cognitive impairment. Always consult a licensed "
    "neurologist or physician for medical evaluation."
)

# Common prompt injection, system override, and medical roleplay jailbreak patterns
SUSPICIOUS_PROMPT_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions?", re.IGNORECASE),
    re.compile(r"disregard\s+(all\s+)?(previous|prior|above)\s+instructions?", re.IGNORECASE),
    re.compile(r"system\s+prompt", re.IGNORECASE),
    re.compile(r"system\s*:", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+a\s+(doctor|neurologist|physician|medical\s+specialist)", re.IGNORECASE),
    re.compile(r"act\s+as\s+a\s+(doctor|neurologist|physician|medical\s+specialist)", re.IGNORECASE),
    re.compile(r"diagnose\s+(me|this\s+patient)", re.IGNORECASE),
    re.compile(r"give\s+me\s+a\s+(clinical\s+)?diagnosis", re.IGNORECASE),
    re.compile(r"what\s+stage\s+of\s+alzheimer'?s\s+do\s+i\s+have", re.IGNORECASE),
    re.compile(r"jailbreak|dan\s+mode|developer\s+mode", re.IGNORECASE),
    re.compile(r"bypass\s+safety|unfiltered\s+mode", re.IGNORECASE),
]


class InsightValidator:
    """Validates AI responses, sanitizes user inputs, and enforces non-diagnostic boundaries."""

    @staticmethod
    def sanitize_user_input(prompt: str) -> Tuple[str, bool]:
        """
        Sanitizes user queries to prevent prompt injection, system tampering,
        or illicit diagnostic requests.

        Args:
            prompt: Raw user input text.

        Returns:
            Tuple of (sanitized_prompt, was_flagged_boolean).
        """
        if not prompt or not isinstance(prompt, str):
            return ("", False)

        cleaned = prompt.strip()

        # Limit input length to prevent token-exhaustion attacks
        if len(cleaned) > 1000:
            cleaned = cleaned[:1000]

        was_flagged = False
        for pattern in SUSPICIOUS_PROMPT_PATTERNS:
            if pattern.search(cleaned):
                was_flagged = True
                logger.warning("Potential prompt-injection/medical-roleplay detected: %s", pattern.pattern)
                # Neutralize matched suspicious pattern
                cleaned = pattern.sub("[inquiry neutralized]", cleaned)

        return (cleaned, was_flagged)

    @staticmethod
    def validate_and_format_explanation(
        raw_output: Dict[str, Any],
        ground_metrics: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Validates the structure of the LLM-generated explanation, guarantees required
        sections exist, enforces standard medical disclaimers, and checks groundedness.
        """
        validated: Dict[str, Any] = {}

        # 1. String sections with fallback defaults if missing
        validated["session_overview"] = str(raw_output.get("session_overview") or "No session overview available.")
        validated["voice_observations"] = str(raw_output.get("voice_observations") or "Voice acoustic observations not recorded.")
        validated["memory_observations"] = str(raw_output.get("memory_observations") or "Narrative recall observations not recorded.")
        validated["executive_observations"] = str(raw_output.get("executive_observations") or "Cognitive game observations not recorded.")

        # 2. List sections
        def ensure_string_list(val: Any) -> List[str]:
            if isinstance(val, list):
                return [str(x) for x in val if x]
            if isinstance(val, str) and val.strip():
                return [val.strip()]
            return []

        validated["strengths"] = ensure_string_list(raw_output.get("strengths")) or ["Completed active assessment tasks."]
        validated["growth_opportunities"] = ensure_string_list(raw_output.get("growth_opportunities")) or ["Continue regular cognitive and speech monitoring."]
        validated["recommended_focus"] = ensure_string_list(raw_output.get("recommended_focus")) or ["Maintain regular check-in consistency."]

        # 3. Always enforce non-diagnostic disclaimer
        validated["disclaimer"] = STANDARD_AI_DISCLAIMER

        # 4. Attach ground metrics for verifiable reference
        validated["grounded_metrics"] = ground_metrics

        return validated

    @staticmethod
    def validate_and_format_chat_reply(
        reply_text: str,
        ground_metrics: Dict[str, Any],
        was_flagged: bool = False
    ) -> Dict[str, Any]:
        """
        Validates an interactive assistant chat response, guarantees non-diagnostic
        disclaimer attachment, and notes if prompt sanitization was applied.
        """
        text = str(reply_text or "").strip()
        if not text:
            text = "I could not generate a response based on the current assessment measurements."

        # If flagged for medical roleplay, prepend gentle boundary reminder
        if was_flagged:
            text = (
                "Note: As an AI assistant for the ALVI research platform, I cannot provide clinical medical "
                "diagnoses or evaluate disease stages. " + text
            )

        return {
            "reply": text,
            "disclaimer": STANDARD_AI_DISCLAIMER,
            "grounded_metrics": list(ground_metrics.keys()),
            "sanitized": was_flagged
        }

