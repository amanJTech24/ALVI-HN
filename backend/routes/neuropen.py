"""
ALVI NeuroPen API Router — FastAPI endpoints for Clock Drawing Test assessment.

Endpoints:
  POST /api/neuropen/sessions            — Create a new NeuroPen session
  POST /api/neuropen/sessions/{id}/image — Upload clock photo (JPG/PNG)
  POST /api/neuropen/sessions/{id}/video — Upload drawing video (MP4/WebM)
  POST /api/neuropen/sessions/{id}/analyze — Run computer-vision analysis
  GET  /api/neuropen/sessions            — List all assessments
  GET  /api/neuropen/sessions/{id}       — Single assessment detail
"""
import uuid
import json
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from backend.hardware import hardware_store as store

neuropen_router = APIRouter(prefix="/api/neuropen", tags=["neuropen"])

# File storage root (relative to project root)
UPLOAD_ROOT = Path("data/neuropen_uploads")
UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
ALLOWED_VIDEO_TYPES = {"video/mp4", "video/webm", "video/quicktime"}
MAX_IMAGE_BYTES = 10 * 1024 * 1024    # 10 MB
MAX_VIDEO_BYTES = 100 * 1024 * 1024   # 100 MB


# ── Pydantic models ──────────────────────────────────────────────────────────

class NeuropenSessionCreate(BaseModel):
    device_id: Optional[str] = None
    notes: Optional[str] = None


# ── Helpers ──────────────────────────────────────────────────────────────────

def _session_dir(session_id: str) -> Path:
    d = UPLOAD_ROOT / session_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def _save_upload(session_id: str, upload: UploadFile, prefix: str, allowed: set, max_size: int) -> str:
    ct = upload.content_type or ""
    if ct not in allowed:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type: {ct}. Allowed: {', '.join(sorted(allowed))}"
        )
    dest_dir = _session_dir(session_id)
    ext = Path(upload.filename or "file").suffix or ".bin"
    filename = f"{prefix}{ext}"
    dest = dest_dir / filename

    size = 0
    with dest.open("wb") as f:
        while True:
            chunk = upload.file.read(1024 * 64)
            if not chunk:
                break
            size += len(chunk)
            if size > max_size:
                dest.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=413,
                    detail=f"File too large. Max size: {max_size // (1024*1024)} MB"
                )
            f.write(chunk)

    return str(dest)


def _get_session_state(session_id: str) -> dict:
    """
    Get current assessment state from the store.
    Returns empty dict if not found.
    """
    result = store.get_neuropen_assessment(session_id=session_id)
    return result or {}


# ── Endpoints ────────────────────────────────────────────────────────────────

@neuropen_router.post("/sessions", status_code=201)
def create_session(body: NeuropenSessionCreate):
    """Create a new NeuroPen Clock Drawing Test session."""
    session_id = str(uuid.uuid4())
    assessment_id = str(uuid.uuid4())
    store.save_neuropen_assessment(
        assessment_id=assessment_id,
        session_id=session_id,
        device_id=body.device_id or "",
    )
    return {
        "session_id": session_id,
        "assessment_id": assessment_id,
        "status": "pending",
    }


@neuropen_router.post("/sessions/{session_id}/image")
async def upload_image(session_id: str, file: UploadFile = File(...)):
    """
    Upload a photo of the completed clock drawing (JPG/PNG/WebP, max 10 MB).

    Transfer your phone photo to the laptop via USB cable or local network,
    then use this endpoint to submit it for analysis.
    """
    current = _get_session_state(session_id)
    if not current:
        raise HTTPException(status_code=404, detail="NeuroPen session not found. Create one first.")

    path = _save_upload(session_id, file, "clock_drawing", ALLOWED_IMAGE_TYPES, MAX_IMAGE_BYTES)

    store.save_neuropen_assessment(
        assessment_id=current.get("assessment_id", str(uuid.uuid4())),
        session_id=session_id,
        device_id=current.get("device_id", ""),
        image_path=path,
        video_path=current.get("video_path"),
        duration_sec=current.get("duration_sec", 0.0),
    )
    return {"session_id": session_id, "status": "image_uploaded", "image_path": path}


@neuropen_router.post("/sessions/{session_id}/video")
async def upload_video(session_id: str, file: UploadFile = File(...)):
    """
    Upload a video of the clock drawing process (MP4/WebM, max 100 MB).

    Workflow for phone recording:
    1. Record the clock drawing on your phone camera.
    2. Connect phone via USB OR use local Wi-Fi file sharing.
    3. Upload the video file using this endpoint.
    """
    current = _get_session_state(session_id)
    if not current:
        raise HTTPException(status_code=404, detail="NeuroPen session not found.")

    path = _save_upload(session_id, file, "drawing_video", ALLOWED_VIDEO_TYPES, MAX_VIDEO_BYTES)

    store.save_neuropen_assessment(
        assessment_id=current.get("assessment_id", str(uuid.uuid4())),
        session_id=session_id,
        device_id=current.get("device_id", ""),
        image_path=current.get("image_path"),
        video_path=path,
        duration_sec=current.get("duration_sec", 0.0),
    )
    return {"session_id": session_id, "status": "video_uploaded", "video_path": path}


@neuropen_router.post("/sessions/{session_id}/analyze")
def analyze_session(session_id: str):
    """
    Run computer-vision analysis on the uploaded clock image.
    Requires a prior image upload for this session.
    """
    current = _get_session_state(session_id)
    if not current:
        raise HTTPException(status_code=404, detail="NeuroPen session not found.")

    image_path = current.get("image_path")
    if not image_path or not Path(image_path).exists():
        raise HTTPException(
            status_code=422,
            detail="No clock image found for this session. Upload an image first."
        )

    try:
        from backend.services.neuropen_cv import analyze_clock_image
        result = analyze_clock_image(image_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"CV analysis failed: {e}")

    # Persist analysis results using the full structured store signature
    store.save_neuropen_assessment(
        assessment_id=current.get("assessment_id", str(uuid.uuid4())),
        session_id=session_id,
        device_id=current.get("device_id", ""),
        image_path=image_path,
        annotated_image_path=result.get("annotated_image_path"),
        video_path=current.get("video_path"),
        duration_sec=current.get("duration_sec", 0.0),
        clock_detected=result.get("clock_detected", False),
        circle_detected=result.get("circle_detected", False),
        circle_score=result.get("circle_score", 0.0),
        hands_detected=result.get("hands_detected", 0),
        estimated_time=result.get("estimated_time", "Unable to determine"),
        is_11_10_approx=result.get("is_11_10_approx"),
        digits_detected_count=result.get("digits_detected_count", 0),
        video_motion_summary=result.get("video_motion_summary"),
        quality_warnings=result.get("quality_warnings"),
        digit_note=result.get("digit_note"),
        raw_metrics=result,
    )

    return {
        "session_id": session_id,
        "assessment_id": current.get("assessment_id"),
        "status": "analyzed",
        "result": result,
    }


@neuropen_router.get("/sessions")
def list_sessions(device_id: Optional[str] = None, limit: int = 20):
    """List NeuroPen assessments, optionally filtered by device_id."""
    return store.get_neuropen_assessments(device_id=device_id, limit=limit)


@neuropen_router.get("/sessions/{session_id}")
def get_session(session_id: str):
    """Get detailed info for a single NeuroPen assessment."""
    assessment = store.get_neuropen_assessment(session_id=session_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="NeuroPen session not found")
    return assessment
