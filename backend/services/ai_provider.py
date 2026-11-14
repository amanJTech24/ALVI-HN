"""
ALVI AI Provider Interface & Factory — backend/services/ai_provider.py

Defines the abstract interface for AI explanation and insights providers,
and a factory function for instantiating the active provider.
"""

from abc import ABC, abstractmethod
import logging
import os
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv

# Ensure environment variables from .env are loaded
load_dotenv()

logger = logging.getLogger("alvi.ai_provider")


class AIServiceError(Exception):
    """Base exception for AI provider service errors."""
    pass


class AIServiceUnavailableError(AIServiceError):
    """Raised when the AI provider is unconfigured, unreachable, or rate-limited."""
    pass


class BaseAIProvider(ABC):
    """
    Abstract Base Class for AI Insights & Explanation Providers.
    Any LLM integration (e.g., Gemma 4 via Google GenAI) must implement this interface.
    """

    @abstractmethod
    def get_status(self) -> Dict[str, Any]:
        """
        Returns the operational status of the AI provider without leaking secrets.

        Returns:
            Dict containing:
                provider: str
                model: str
                configured: bool
                available: bool
                status_message: str
        """
        pass

    @abstractmethod
    def generate_explanation(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generates structured cognitive insights and explanations grounded strictly
        in the provided assessment measurements.

        Args:
            context: Dictionary containing structured user measurements,
                     history trends, and learning recommendations.

        Returns:
            Dict containing structured explanation sections:
                session_overview: str
                voice_observations: str
                memory_observations: str
                executive_observations: str
                strengths: List[str]
                growth_opportunities: List[str]
                recommended_focus: List[str]
                disclaimer: str
                grounded_metrics: Dict[str, Any]
        """
        pass

    @abstractmethod
    def chat_completion(
        self,
        question: str,
        context: Dict[str, Any],
        chat_history: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """
        Answers user questions in an interactive chat session grounded strictly in
        the session measurements, refusing medical diagnoses or ungrounded claims.

        Args:
            question: User inquiry string.
            context: Session context and measurements.
            chat_history: Optional list of previous role/content conversation turns.

        Returns:
            Dict containing:
                reply: str
                grounded_metrics: List[str]
                disclaimer: str
        """
        pass


_PROVIDER_INSTANCE: Optional[BaseAIProvider] = None


def get_ai_provider() -> BaseAIProvider:
    """
    Factory function returning the configured AI provider singleton.
    Defaults to GemmaAIProvider using Google GenAI SDK.
    """
    global _PROVIDER_INSTANCE
    if _PROVIDER_INSTANCE is None:
        provider_type = os.getenv("AI_PROVIDER", "gemma").lower().strip()
        if provider_type in ("gemma", "google", "gemini"):
            from backend.services.gemma_service import GemmaAIProvider
            _PROVIDER_INSTANCE = GemmaAIProvider()
        else:
            logger.warning("Unknown AI_PROVIDER '%s'. Defaulting to GemmaAIProvider.", provider_type)
            from backend.services.gemma_service import GemmaAIProvider
            _PROVIDER_INSTANCE = GemmaAIProvider()

    return _PROVIDER_INSTANCE


def reset_ai_provider_for_testing() -> None:
    """Resets the singleton instance for unit test isolation."""
    global _PROVIDER_INSTANCE
    _PROVIDER_INSTANCE = None

