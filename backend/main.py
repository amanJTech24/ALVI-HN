"""
ALVI Backend API
FastAPI server for the ALVI Alzheimer's Voice-Screening Platform.
Integrated with the Phase 4 ML acoustic feature extraction and inference pipeline.
"""

import logging
from pathlib import Path
import tempfile
from typing import Any, Dict

from fastapi import FastAPI, File, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware

from backend.ml.audio_preprocessing import AudioPreprocessingError
from backend.ml.predict_voice import (
    ModelPredictionError,
    get_prediction_service,
)
from backend.routes.comparison import router as comparison_router
from backend.routes.games import router as games_router
from backend.routes.insights import insights_router
from backend.routes.learning_path import router as learning_router
from backend.routes.hardware import hardware_router
from backend.routes.neuropen import neuropen_router
from backend.routes.patterns import patterns_router
from backend.routes.story import router as story_router

logger = logging.getLogger("alvi.backend")

app = FastAPI(
    title="ALVI Alzheimer's Voice-Screening API",
    description=(
        "Backend API for the ALVI voice screening and cognitive pattern monitoring platform. "
        "Provides acoustic feature extraction, narrative recall NLP, MindPlay cognitive game analytics, "
        "case comparison, personalized cognitive learning path practice, longitudinal pattern exploration, "
        "and Gemma 4 AI personalized cognitive insights."
    ),
    version="1.7.0",
)

# Enable CORS for cross-origin access from frontend deployment and localhost
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register sub-routers
app.include_router(story_router)
app.include_router(games_router)
app.include_router(comparison_router)
app.include_router(learning_router)
app.include_router(patterns_router)
app.include_router(insights_router)
app.include_router(hardware_router)
app.include_router(neuropen_router)

MAX_UPLOAD_SIZE_BYTES = 25 * 1024 * 1024  # 25 MB max audio upload
SUPPORTED_EXTENSIONS = {".wav", ".webm", ".mp3", ".ogg", ".m4a", ".flac"}


@app.get("/")
def root() -> Dict[str, Any]:
    """Root endpoint providing service status, documentation, and active ML model info."""
    svc = None
    try:
        svc = get_prediction_service()
        model_name = svc.metadata.get("selected_model_name", "Random_Forest")
        model_version = svc.model_version
    except Exception:
        model_name = "Not Loaded"
        model_version = "None"

    return {
        "name": "ALVI API",
        "status": "online",
        "health_check": "/health",
        "ml_inference_endpoint": "/api/voice/analyze",
        "story_evaluation_endpoint": "/api/story/evaluate",
        "story_catalog_endpoint": "/api/story/stories",
        "games_catalog_endpoint": "/api/games/catalog",
        "games_submit_endpoint": "/api/games/submit",
        "cases_compare_endpoint": "/api/cases/compare",
        "cases_reference_endpoint": "/api/cases/reference-stats",
        "learning_catalog_endpoint": "/api/learning/catalog",
        "learning_recommend_endpoint": "/api/learning/recommend",
        "learning_progress_endpoint": "/api/learning/progress",
        "patterns_metrics_endpoint": "/api/patterns/metrics",
        "patterns_analyze_endpoint": "/api/patterns/analyze",
        "insights_status_endpoint": "/api/insights/status",
        "insights_generate_endpoint": "/api/insights/generate",
        "insights_chat_endpoint": "/api/insights/chat",
        "hardware_status_endpoint": "/api/hardware/status",
        "docs_url": "/docs",
        "ml_model": {
            "name": model_name,
            "version": model_version,
            "feature_count": 79,
            "inference_mode": "exploratory_research_benchmark",
        },
        "disclaimer": (
            "ALVI is an exploratory cognitive pattern screening prototype. "
            "It does NOT provide clinical diagnoses or validated medical risk predictions."
        ),
    }


@app.get("/health")
def health() -> Dict[str, str]:
    """Health check endpoint required by Render and frontend connectivity monitors."""
    return {"status": "healthy"}


@app.post("/analyze")
async def analyze_voice_receipt(file: UploadFile = File(...)) -> Dict[str, Any]:
    """
    Receipt endpoint maintained for baseline connectivity and backward compatibility.
    Acknowledges receipt of voice uploads without triggering heavy ML inference.
    """
    if not file or not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="No audio file uploaded."
        )

    content = await file.read()
    file_size = len(content)

    if file_size == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded audio file is empty."
        )

    return {
        "status": "received",
        "filename": file.filename,
        "content_type": file.content_type,
        "size_bytes": file_size,
        "message": "Audio file received successfully by ALVI backend.",
        "ml_endpoint_available": "/api/voice/analyze",
        "disclaimer": (
            "ALVI is an early cognitive pattern screening prototype and not a diagnostic device. "
            "Automated machine learning risk prediction has not been clinically validated or deployed."
        ),
    }


@app.post("/api/voice/analyze")
async def analyze_voice_ml(file: UploadFile = File(...)) -> Dict[str, Any]:
    """
    Full acoustic analysis and research-label prediction endpoint:
    1. Validates audio upload format and file size.
    2. Decodes, downmixes to mono, and resamples to 16 kHz.
    3. Extracts all 79 acoustic and prosodic features.
    4. Executes inference using the serialized Random Forest pipeline.
    5. Returns genuine physical measurements and research prediction.
    6. Safely cleans up temporary audio files.
    """
    if not file or not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="No audio file uploaded."
        )

    # 1. Inspect file extension
    ext = Path(file.filename).suffix.lower()
    if not ext:
        ext = ".webm"

    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=(
                f"Unsupported audio format '{ext}'. Supported formats: "
                f"{', '.join(sorted(SUPPORTED_EXTENSIONS))}"
            ),
        )

    # 2. Read audio payload and enforce size boundaries
    content = await file.read()
    file_size = len(content)

    if file_size == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded audio file is empty."
        )

    if file_size > MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Audio file exceeds maximum allowable size of {MAX_UPLOAD_SIZE_BYTES // (1024*1024)} MB.",
        )

    # 3. Write content to temporary file for acoustic signal decoding
    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp_file:
        tmp_path = Path(tmp_file.name)
        tmp_file.write(content)

    # 4. Execute preprocessing, feature extraction, and ML inference
    try:
        svc = get_prediction_service()
        result = svc.predict_from_audio_file(tmp_path)

        # Attach upload metadata
        result["filename"] = file.filename
        result["content_type"] = file.content_type
        result["size_bytes"] = file_size

        return result

    except AudioPreprocessingError as pre_err:
        logger.warning("Audio preprocessing rejected upload %s: %s", file.filename, pre_err.message)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Audio validation failure: {pre_err.message}",
        )
    except ModelPredictionError as pred_err:
        logger.error("Model prediction failure on %s: %s", file.filename, pred_err.message)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Inference failure: {pred_err.message}",
        )
    except Exception as unk_err:
        logger.exception("Unexpected exception analyzing voice recording %s", file.filename)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected server error during voice screening: {str(unk_err)}",
        )
    finally:
        # Guarantee removal of temporary file
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except Exception as rm_err:
                logger.warning("Failed deleting temporary audio file %s: %s", tmp_path, rm_err)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
