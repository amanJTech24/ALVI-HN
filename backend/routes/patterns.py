"""
ALVI Pattern Explorer API Routes — backend/routes/patterns.py

Exposes endpoints for longitudinal time-series analytics, descriptive statistics,
metric definitions, and multi-session comparisons.
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from backend.services.pattern_analytics import get_pattern_analytics_service

patterns_router = APIRouter(prefix="/api/patterns", tags=["Pattern Explorer"])


class PatternAnalysisRequest(BaseModel):
    session_history: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="List of raw check-in session dictionaries from client storage."
    )
    practice_history: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="Optional list of completed practice activity records."
    )
    filter_options: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional filtering options (e.g. start_date, end_date, include_demo)."
    )


@patterns_router.get("/metrics")
async def get_metrics_catalog() -> Dict[str, Any]:
    """
    Returns available longitudinal metrics across Voice, Story Recall, MindPlay,
    and Practice domains, along with measurement units, ranges, and analytical constraints.
    """
    try:
        service = get_pattern_analytics_service()
        return service.get_available_metrics_catalog()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load pattern metrics catalog: {str(e)}"
        )


@patterns_router.post("/analyze")
async def analyze_longitudinal_patterns(request: PatternAnalysisRequest) -> Dict[str, Any]:
    """
    Analyzes historical check-in sessions and practice engagement records.
    Normalizes data, computes time-series statistics, pairwise deltas, and multi-modal trajectories.
    """
    try:
        service = get_pattern_analytics_service()
        result = service.analyze_patterns(
            raw_sessions=request.session_history,
            raw_practices=request.practice_history,
            filter_options=request.filter_options
        )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Pattern analysis failed: {str(e)}"
        )
