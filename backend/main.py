"""
ALVI Backend API
FastAPI server for the ALVI Alzheimer's Voice-Screening Platform.
Designed for deployment on Render.
"""

from typing import Any, Dict
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="ALVI Alzheimer's Voice-Screening API",
    description="Backend API for the ALVI voice screening and cognitive pattern monitoring platform.",
    version="1.0.0",
)

# Enable CORS for cross-origin access from frontend deployment and localhost
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root() -> Dict[str, Any]:
    """Root endpoint providing service status and navigation."""
    return {
        "name": "ALVI API",
        "status": "online",
        "health_check": "/health",
        "docs_url": "/docs",
        "message": "ALVI voice-screening platform backend is active.",
        "disclaimer": "ALVI supports cognitive pattern monitoring and is not a diagnostic tool.",
    }


@app.get("/health")
def health() -> Dict[str, str]:
    """Health check endpoint required by Render and frontend connectivity checks."""
    return {"status": "healthy"}


@app.post("/analyze")
async def analyze_voice(file: UploadFile = File(...)) -> Dict[str, Any]:
    """
    Receives an audio recording file (e.g., WebM, WAV) for voice screening processing.
    Note: Real-time diagnostic ML inference is not connected in this prototype.
    """
    if not file:
        raise HTTPException(status_code=400, detail="No audio file uploaded.")

    content = await file.read()
    file_size = len(content)

    if file_size == 0:
        raise HTTPException(status_code=400, detail="Uploaded audio file is empty.")

    return {
        "status": "received",
        "filename": file.filename,
        "content_type": file.content_type,
        "size_bytes": file_size,
        "message": "Audio file received successfully by ALVI backend.",
        "inference_status": "mock_placeholder",
        "disclaimer": (
            "ALVI is an early cognitive pattern screening prototype and not a diagnostic device. "
            "Automated machine learning risk prediction has not been clinically validated or deployed."
        ),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
