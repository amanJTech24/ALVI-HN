"""
ALVI Case Comparison API Routes — backend/routes/comparison.py
FastAPI router providing multi-modal case comparison and descriptive research reference stats.
Endpoints:
- GET /api/cases/reference-stats: Empirical reference distributions derived from DementiaNet cleaned corpus.
- POST /api/cases/compare: Unified comparison engine evaluating Mode A (current), Mode B (history), and Mode C (reference).
"""

import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from backend.services.case_comparison import get_case_comparison_engine
from backend.services.reference_statistics import get_reference_statistics_service

logger = logging.getLogger("alvi.routes.comparison")

router = APIRouter(
    prefix="/api/cases",
    tags=["Case Comparison & Cognitive Analytics"],
)


class CaseComparisonRequest(BaseModel):
    current_session: Dict[str, Any] = Field(
        ...,
        description="The active check-in session dictionary containing voice, story, and/or mindplay objects.",
    )
    history_sessions: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="Optional list of previous completed check-in sessions for within-subject longitudinal tracking.",
    )


class ReferenceStatsResponse(BaseModel):
    status: str
    provenance: Dict[str, Any]
    acoustic_reference_metrics: Dict[str, Any]
    by_group_acoustic_breakdown: Optional[Dict[str, Any]] = None
    cognitive_task_standards: Optional[Dict[str, Any]] = None


@router.get("/reference-stats")
def get_reference_statistics() -> Dict[str, Any]:
    """
    Returns empirical descriptive reference statistics derived from the cleaned DementiaNet dataset.
    Covers acoustic distributions (median, IQR, min, max) for 100 recordings across 80 unique speakers.
    Includes explicit provenance and non-diagnostic disclaimers.
    """
    try:
        service = get_reference_statistics_service()
        stats = service.get_reference_statistics()
        return stats
    except Exception as e:
        logger.error("Failed to retrieve reference statistics: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate reference statistics: {str(e)}",
        )


@router.post("/compare")
def compare_cases(request: CaseComparisonRequest) -> Dict[str, Any]:
    """
    Performs multi-modal case comparison across three evaluation modes:
    - Mode A: Current Session Performance Synthesis (voice, story, mindplay completeness).
    - Mode B: Personal Longitudinal History Tracking (within-subject changes, honest empty state if < 2 sessions).
    - Mode C: Research Reference Benchmark (empirical comparison against DementiaNet acoustic distributions).

    Does NOT generate clinical Alzheimer's diagnostic percentages or risk probabilities.
    """
    if not isinstance(request.current_session, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid request: 'current_session' must be a valid dictionary.",
        )

    try:
        engine = get_case_comparison_engine()
        result = engine.compare(
            current_session=request.current_session,
            history_sessions=request.history_sessions or [],
        )
        return result
    except Exception as e:
        logger.error("Error executing case comparison: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Case comparison processing failed: {str(e)}",
        )

