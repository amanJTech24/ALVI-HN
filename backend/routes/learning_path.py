"""
ALVI Learning Path API Routes — backend/routes/learning_path.py
FastAPI router providing personalized cognitive practice recommendations,
exercise catalog lookup, and practice progress analytics.

Endpoints:
- GET /api/learning/catalog — Returns the structured catalog of practice exercises.
- POST /api/learning/recommend — Generates deterministic, explainable practice recommendations based on ALVI task results.
- POST /api/learning/progress — Analyzes practice completions, personal bests, and intra-individual trends.
"""

import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from backend.services.learning_recommendations import get_learning_recommendation_engine
from backend.services.practice_progress import get_practice_progress_tracker

logger = logging.getLogger("alvi.routes.learning")

router = APIRouter(
    prefix="/api/learning",
    tags=["Cognitive Learning Path & Practice Engine"],
)


class RecommendationRequest(BaseModel):
    current_session: Optional[Dict[str, Any]] = Field(
        default=None,
        description="The active check-in session dictionary containing voice, story, and/or mindplay objects.",
    )
    history_sessions: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="Optional list of previous completed check-in sessions.",
    )
    practice_history: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="Optional list of previous completed practice activity records.",
    )


class ProgressRequest(BaseModel):
    practice_records: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="List of practice activity attempt records logged in the client browser.",
    )


@router.get("/catalog")
def get_catalog() -> Dict[str, Any]:
    """
    Returns the complete catalog of practice activities with instructions,
    targeted skills, supported signals, and estimated durations.
    """
    try:
        engine = get_learning_recommendation_engine()
        return engine.get_catalog()
    except Exception as e:
        logger.error("Failed to retrieve exercise catalog: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve exercise catalog: {str(e)}",
        )


@router.post("/recommend")
def get_recommendations(request: RecommendationRequest) -> Dict[str, Any]:
    """
    Generates personalized cognitive practice recommendations from actual assessment measurements.
    Returns starter path for new users or targeted practice drills for evaluated tasks.
    """
    try:
        engine = get_learning_recommendation_engine()
        result = engine.recommend(
            current_session=request.current_session,
            history_sessions=request.history_sessions,
            practice_history=request.practice_history,
        )
        return result
    except Exception as e:
        logger.error("Failed to generate recommendations: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate practice recommendations: {str(e)}",
        )


@router.post("/progress")
def track_progress(request: ProgressRequest) -> Dict[str, Any]:
    """
    Analyzes practice activity completion records, personal bests, and practice consistency.
    Returns honest empty state if no practice records exist.
    """
    try:
        tracker = get_practice_progress_tracker()
        result = tracker.analyze_progress(request.practice_records)
        return result
    except Exception as e:
        logger.error("Failed to analyze practice progress: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to analyze practice progress: {str(e)}",
        )

