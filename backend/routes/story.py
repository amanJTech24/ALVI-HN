"""
ALVI Story Recall NLP Routes
Provides endpoints for:
- Story catalog retrieval
- Individual story details
- NLP evaluation of participant narrative recall transcripts
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from backend.services.story_scoring import (
    StoryScoringService,
    get_story_bank,
)

logger = logging.getLogger("alvi.story_recall")

router = APIRouter(prefix="/api/story", tags=["Story Recall NLP"])

# Shared scoring service instance
_scoring_service: Optional[StoryScoringService] = None


def get_scoring_service() -> StoryScoringService:
    global _scoring_service
    if _scoring_service is None:
        _scoring_service = StoryScoringService()
    return _scoring_service


class StoryEvaluationRequest(BaseModel):
    story_id: str = Field(
        default="aarav_story_v1",
        description="Authoritative story identifier from the story bank."
    )
    transcript: str = Field(
        ...,
        description="The participant's spoken or typed narrative recall transcript.",
        min_length=1
    )
    input_mode: str = Field(
        default="speech",
        description="Input acquisition mode: 'speech' or 'typed'."
    )
    timing_seconds: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="Duration of recall attempt in seconds."
    )


@router.get("/stories")
def list_available_stories() -> Dict[str, Any]:
    """
    Retrieve the catalog of standard cognitive recall stories.
    """
    bank = get_story_bank()
    stories = bank.list_stories()
    return {
        "status": "success",
        "count": len(stories),
        "stories": stories
    }


@router.get("/{story_id}")
def get_story_details(story_id: str) -> Dict[str, Any]:
    """
    Retrieve stimulus text and metadata for a specific story.
    Omits internal grading keys/synonyms.
    """
    bank = get_story_bank()
    story = bank.get_story(story_id)
    if not story:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Story with ID '{story_id}' not found in story bank."
        )

    return {
        "id": story["id"],
        "title": story.get("title", story["id"]),
        "difficulty": story.get("difficulty", "standard"),
        "text": story.get("text", ""),
        "word_count": story.get("word_count", len(story.get("text", "").split())),
        "total_units": len(story.get("information_units", []))
    }


@router.post("/evaluate")
def evaluate_story_recall(payload: StoryEvaluationRequest) -> Dict[str, Any]:
    """
    Evaluate participant story recall transcript using explainable NLP:
    1. Key Information Unit completeness scoring (exact, paraphrase, partial, missing)
    2. Paraphrase & synonym recognition with negation scope detection
    3. Chronological event sequence accuracy (inversion counting)
    4. Global narrative semantic similarity (TF-IDF cosine similarity)
    5. Narrative intrusion / confabulation detection
    6. Explainable composite cognitive task performance score
    """
    clean_transcript = payload.transcript.strip()
    if not clean_transcript:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Transcript cannot be empty or contain only whitespace."
        )

    try:
        service = get_scoring_service()
        result = service.score_recall(
            story_id=payload.story_id,
            transcript=clean_transcript,
            input_mode=payload.input_mode,
            timing_seconds=payload.timing_seconds
        )
        return {
            "status": "success",
            "data": result
        }

    except KeyError as key_err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(key_err)
        )
    except Exception as exc:
        logger.exception("Error evaluating story recall: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Story recall evaluation error: {str(exc)}"
        )

