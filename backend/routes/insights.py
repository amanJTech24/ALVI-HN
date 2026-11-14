"""
ALVI Gemma 4 AI Insights API Routes — backend/routes/insights.py

Exposes endpoints for AI explanation generation, interactive question answering,
and service configuration/health status.
"""

import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from backend.services.ai_provider import (
    AIServiceError,
    AIServiceUnavailableError,
    get_ai_provider,
)

logger = logging.getLogger("alvi.insights_router")

insights_router = APIRouter(prefix="/api/insights", tags=["AI Insights"])


class InsightGenerateRequest(BaseModel):
    current_session: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Active check-in session containing voice, story, and mindplay results."
    )
    history_sessions: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="Historical check-in sessions for longitudinal trajectory grounding."
    )
    practice_history: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="Practice drill completions."
    )
    learning_recommendations: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Personalized learning path recommendations."
    )
    user_consent: bool = Field(
        default=False,
        description="Explicit user consent to transmit assessment metrics to external AI service."
    )


class InsightChatRequest(BaseModel):
    question: str = Field(
        ...,
        description="User's inquiry about their voice features, recall, or cognitive metrics."
    )
    current_session: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Active session measurements for grounding."
    )
    history_sessions: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="Historical sessions for trajectory context."
    )
    chat_history: Optional[List[Dict[str, str]]] = Field(
        default=None,
        description="Recent conversation turns (role/content)."
    )
    user_consent: bool = Field(
        default=False,
        description="Explicit user consent to chat with the AI assistant."
    )


@insights_router.get("/status")
def get_insights_status() -> Dict[str, Any]:
    """
    Returns the availability and configuration status of the Gemma 4 AI provider.
    Never reveals API keys or private credentials.
    """
    provider = get_ai_provider()
    status_info = provider.get_status()
    status_info["version"] = "1.7.0"
    return status_info


@insights_router.post("/generate")
def generate_insights(request: InsightGenerateRequest) -> Dict[str, Any]:
    """
    Generates structured AI insights grounded in authentic acoustic and cognitive measurements.
    Requires explicit user consent prior to external API processing.
    """
    if not request.user_consent:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User consent is required before assessment metrics can be processed for AI explanation."
        )

    try:
        provider = get_ai_provider()
        context = {
            "current_session": request.current_session,
            "history_sessions": request.history_sessions,
            "practice_history": request.practice_history,
            "learning_recommendations": request.learning_recommendations
        }
        return provider.generate_explanation(context)

    except AIServiceUnavailableError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e)
        )
    except Exception as e:
        logger.error("Failed to generate AI insights: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate AI insights: {str(e)}"
        )


@insights_router.post("/chat")
def chat_with_insights_assistant(request: InsightChatRequest) -> Dict[str, Any]:
    """
    Answers user questions regarding their assessment metrics using Gemma 4.
    Requires explicit user consent. Refuses diagnostic or ungrounded claims.
    """
    if not request.user_consent:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User consent is required before chatting with the AI assistant."
        )

    clean_question = (request.question or "").strip()
    if not clean_question:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Question cannot be empty."
        )

    try:
        provider = get_ai_provider()
        context = {
            "current_session": request.current_session,
            "history_sessions": request.history_sessions
        }
        return provider.chat_completion(
            question=clean_question,
            context=context,
            chat_history=request.chat_history
        )

    except Exception as e:
        logger.error("Failed to process AI chat query: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process chat inquiry: {str(e)}"
        )

