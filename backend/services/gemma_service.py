"""
ALVI Gemma 4 AI Insights Service — backend/services/gemma_service.py

Implements hosted Gemma 4 AI explanations and chat completions via the official
Google GenAI SDK (google-genai). Features secure API key handling, retry logic with
exponential backoff, JSON extraction and schema validation, and groundedness enforcement.
"""

import json
import logging
import os
import re
import time
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv

from google import genai
from google.genai import types

from backend.services.ai_provider import (
    AIServiceError,
    AIServiceUnavailableError,
    BaseAIProvider,
)
from backend.services.insight_builder import InsightContextBuilder
from backend.services.insight_validation import (
    InsightValidator,
    STANDARD_AI_DISCLAIMER,
)

load_dotenv()
logger = logging.getLogger("alvi.gemma_service")

# Primary and alternative Gemma 4 models
DEFAULT_GEMMA_MODEL = "gemma-4-26b-a4b-it"
ALTERNATIVE_GEMMA_MODEL = "gemma-4-31b-it"


class GemmaAIProvider(BaseAIProvider):
    """
    Gemma 4 AI Provider connecting to Google's hosted Gemma models via Google GenAI SDK.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None
    ):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GEMMA_API_KEY")
        self.model_name = (
            model_name or
            os.getenv("AI_MODEL") or
            DEFAULT_GEMMA_MODEL
        ).strip()
        self.builder = InsightContextBuilder()
        self.validator = InsightValidator()

        self._client: Optional[genai.Client] = None
        if self.api_key and self.api_key.strip():
            try:
                self._client = genai.Client(api_key=self.api_key.strip())
            except Exception as e:
                logger.error("Failed to initialize Google GenAI Client: %s", e)
                self._client = None

    def is_configured(self) -> bool:
        """Returns True if a valid API key string is present."""
        return bool(self.api_key and len(self.api_key.strip()) > 5)

    def get_status(self) -> Dict[str, Any]:
        """Returns provider status without exposing the API key."""
        configured = self.is_configured()
        return {
            "provider": "gemma",
            "model": self.model_name,
            "configured": configured,
            "available": configured and (self._client is not None),
            "status_message": (
                "Gemma 4 AI Insights service is ready."
                if configured
                else "GEMINI_API_KEY is not configured in environment or .env file."
            )
        }

    def _execute_with_retry(self, fn, max_retries: int = 3, initial_delay: float = 1.0):
        """Executes a GenAI call with exponential backoff on transient errors."""
        last_err = None
        delay = initial_delay

        for attempt in range(1, max_retries + 1):
            try:
                return fn()
            except Exception as e:
                err_str = str(e).lower()
                last_err = e
                # Check for rate limit (429), quota, or transient server unavailable (503)
                is_transient = any(x in err_str for x in ["429", "rate", "resourceexhausted", "503", "unavailable", "timeout"])
                if is_transient and attempt < max_retries:
                    logger.warning("Transient error calling Gemma API (attempt %d/%d): %s. Retrying in %.1fs...", attempt, max_retries, e, delay)
                    time.sleep(delay)
                    delay *= 2.0
                else:
                    break

        raise last_err

    def generate_explanation(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generates structured cognitive insights grounded in the provided session context.
        """
        current_session = context.get("current_session") or context.get("session")
        history_sessions = context.get("history_sessions") or context.get("history")
        practice_history = context.get("practice_history")
        learning_recs = context.get("learning_recommendations")

        prompt, ground_metrics = self.builder.build_prompt_context(
            current_session=current_session,
            history_sessions=history_sessions,
            practice_history=practice_history,
            learning_recommendations=learning_recs
        )

        if not self.is_configured() or self._client is None:
            # Deterministic fallback when API key is missing
            logger.info("Gemma API key unconfigured. Returning grounded deterministic fallback explanation.")
            return self.builder.generate_deterministic_fallback(ground_metrics)

        try:
            def _call_model():
                return self._client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.2,
                        max_output_tokens=1500,
                    )
                )

            response = self._execute_with_retry(_call_model, max_retries=3)
            raw_text = response.text or ""

            parsed_json = self._extract_json(raw_text)
            if not parsed_json:
                logger.warning("Could not extract clean JSON from Gemma output. Using deterministic fallback.")
                return self.builder.generate_deterministic_fallback(ground_metrics)

            validated = self.validator.validate_and_format_explanation(parsed_json, ground_metrics)
            return validated

        except Exception as e:
            logger.error("Error generating Gemma AI explanation: %s", e)
            # Gracefully fall back to deterministic mode rather than crashing
            fallback = self.builder.generate_deterministic_fallback(ground_metrics)
            fallback["warning"] = f"Gemma API encountered an issue ({type(e).__name__}); showing rule-based analysis."
            return fallback

    def chat_completion(
        self,
        question: str,
        context: Dict[str, Any],
        chat_history: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """
        Answers user questions grounded in their assessment metrics.
        """
        sanitized_question, was_flagged = self.validator.sanitize_user_input(question)
        if not sanitized_question:
            return {
                "reply": "Please enter a valid question regarding your assessment results.",
                "disclaimer": STANDARD_AI_DISCLAIMER,
                "grounded_metrics": [],
                "sanitized": was_flagged
            }

        current_session = context.get("current_session") or context.get("session")
        history_sessions = context.get("history_sessions") or context.get("history")
        ground_metrics = self.builder.extract_ground_metrics(current_session, history_sessions)

        if not self.is_configured() or self._client is None:
            # Informative response when API key is missing
            return {
                "reply": (
                    "The Gemma 4 AI Assistant is currently in offline mode (GEMINI_API_KEY is not configured on the backend). "
                    "Based on your recorded session metrics, your tasks have been stored and analyzed deterministically."
                ),
                "disclaimer": STANDARD_AI_DISCLAIMER,
                "grounded_metrics": list(ground_metrics.keys()),
                "sanitized": was_flagged,
                "offline": True
            }

        prompt = self.builder.build_chat_prompt(
            question=sanitized_question,
            ground_metrics=ground_metrics,
            chat_history=chat_history
        )

        try:
            def _call_model():
                return self._client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.3,
                        max_output_tokens=800,
                    )
                )

            response = self._execute_with_retry(_call_model, max_retries=3)
            reply_text = response.text or ""
            return self.validator.validate_and_format_chat_reply(
                reply_text=reply_text,
                ground_metrics=ground_metrics,
                was_flagged=was_flagged
            )

        except Exception as e:
            logger.error("Error in Gemma AI chat completion: %s", e)
            return {
                "reply": f"Unable to reach Gemma 4 AI service ({type(e).__name__}). Please check your internet connection or backend API key.",
                "disclaimer": STANDARD_AI_DISCLAIMER,
                "grounded_metrics": list(ground_metrics.keys()),
                "sanitized": was_flagged,
                "error": True
            }

    @staticmethod
    def _extract_json(text: str) -> Optional[Dict[str, Any]]:
        """Extracts JSON object from LLM output, handling markdown blocks."""
        if not text:
            return None

        clean_text = text.strip()

        # Handle ```json ... ``` or ``` ... ``` code blocks
        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", clean_text, re.DOTALL)
        if json_match:
            clean_text = json_match.group(1).strip()
        else:
            # Fallback: look for first '{' and last '}'
            start = clean_text.find("{")
            end = clean_text.rfind("}")
            if start != -1 and end != -1 and end > start:
                clean_text = clean_text[start:end+1]

        try:
            return json.loads(clean_text)
        except json.JSONDecodeError:
            return None

