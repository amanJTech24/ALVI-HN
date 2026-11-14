"""
ALVI ML - Voice Prediction Service (Phase 4)
Loads the serialized Scikit-learn model pipeline, validates input feature schemas,
executes inference, and returns structured non-diagnostic research predictions.
"""

from dataclasses import dataclass
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import joblib
import numpy as np
import pandas as pd

from .audio_preprocessing import (
    AudioPreprocessingError,
    PreprocessedAudio,
    load_and_preprocess_audio,
)
from .extract_features import extract_recording_features
from .feature_config import DEFAULT_CONFIG, FeatureConfig
from .model_config import DEFAULT_MODEL_CONFIG, ModelConfig

logger = logging.getLogger("alvi.predict_voice")


class ModelPredictionError(Exception):
    """Raised when model inference or feature validation fails."""

    def __init__(self, message: str, error_type: str = "InferenceError"):
        super().__init__(message)
        self.error_type = error_type
        self.message = message


class VoicePredictionService:
    """
    Thread-safe prediction service for ALVI voice screening ML pipeline.
    Caches model pipeline and feature schema in memory.
    """

    def __init__(
        self,
        model_path: Path = DEFAULT_MODEL_CONFIG.best_model_path,
        metadata_path: Path = DEFAULT_MODEL_CONFIG.metadata_json_path,
        feature_config: FeatureConfig = DEFAULT_CONFIG,
    ):
        self.model_path = Path(model_path)
        self.metadata_path = Path(metadata_path)
        self.feature_config = feature_config

        self.model = None
        self.metadata: Dict[str, Any] = {}
        self.feature_schema: List[str] = []
        self.label_mapping: Dict[int, str] = {}
        self.model_version: str = "unknown"

        self._load_model()

    def _load_model(self) -> None:
        """Loads model binary and metadata schema from disk."""
        if not self.model_path.is_file():
            raise ModelPredictionError(
                f"Model artifact not found at: {self.model_path}",
                error_type="ModelNotFound",
            )
        if not self.metadata_path.is_file():
            raise ModelPredictionError(
                f"Model metadata not found at: {self.metadata_path}",
                error_type="MetadataNotFound",
            )

        try:
            self.model = joblib.load(self.model_path)
            with open(self.metadata_path, "r", encoding="utf-8") as f:
                self.metadata = json.load(f)

            self.feature_schema = self.metadata.get("feature_schema", [])
            raw_labels = self.metadata.get("class_label_mapping", {"0": "nodementia", "1": "dementia"})
            self.label_mapping = {int(k): v for k, v in raw_labels.items()}
            self.model_version = self.metadata.get("model_version", "1.0.0-experimental")

            logger.info(
                "Loaded voice prediction model (%s, %d features, version: %s)",
                self.metadata.get("selected_model_name", "Unknown"),
                len(self.feature_schema),
                self.model_version,
            )
        except Exception as err:
            raise ModelPredictionError(
                f"Failed to load model pipeline: {err}", error_type="ModelLoadError"
            )

    def validate_features(self, features: Dict[str, float]) -> np.ndarray:
        """
        Validates feature dictionary against the exact training schema:
        1. Checks for missing required acoustic features.
        2. Filters out any extraneous metadata, identifiers, or labels.
        3. Checks for NaN or infinite values.
        4. Returns 2D numpy array with features in exact training order.
        """
        missing_features = [feat for feat in self.feature_schema if feat not in features]
        if missing_features:
            raise ModelPredictionError(
                f"Input missing {len(missing_features)} required features: {missing_features[:5]}...",
                error_type="MissingFeatures",
            )

        ordered_values = []
        for feat in self.feature_schema:
            val = features[feat]
            if val is None or np.isnan(val) or np.isinf(val):
                raise ModelPredictionError(
                    f"Feature '{feat}' contains invalid value: {val}",
                    error_type="InvalidFeatureValue",
                )
            ordered_values.append(float(val))

        return np.array([ordered_values], dtype=np.float32)

    def predict_from_features(self, features: Dict[str, float]) -> Dict[str, Any]:
        """
        Executes model inference on a validated feature dictionary.
        Returns structured research-label predictions.
        """
        X = self.validate_features(features)

        try:
            pred_id = int(self.model.predict(X)[0])
            pred_label = self.label_mapping.get(pred_id, str(pred_id))

            # Raw model vote fraction / score
            if hasattr(self.model, "predict_proba"):
                probs = self.model.predict_proba(X)[0]
                raw_score = float(probs[1]) if len(probs) > 1 else float(probs[0])
            else:
                raw_score = 1.0 if pred_id == 1 else 0.0

            return {
                "predicted_class_id": pred_id,
                "predicted_label": pred_label,
                "raw_model_score": round(raw_score, 4),
                "model_version": self.model_version,
                "is_calibrated_probability": False,
                "score_interpretation": (
                    "Raw ensemble tree vote fraction for research annotation 'dementia'. "
                    "This is an uncalibrated heuristic score, NOT a clinical diagnostic probability."
                ),
                "disclaimer": (
                    "ALVI is an exploratory cognitive pattern screening prototype. "
                    "This output is NOT a medical diagnosis, does NOT assess clinical Alzheimer's risk, "
                    "and has NOT been clinically validated."
                ),
            }
        except Exception as err:
            raise ModelPredictionError(
                f"Inference execution failed: {err}", error_type="InferenceFailure"
            )

    def predict_from_audio_file(
        self, file_path: Path, config: Optional[FeatureConfig] = None
    ) -> Dict[str, Any]:
        """
        Complete end-to-end pipeline from audio file to feature extraction and inference.
        Supports WAV, WebM, MP3, etc.
        """
        cfg = config or self.feature_config

        # 1. Preprocess audio
        pre = load_and_preprocess_audio(file_path, config=cfg)

        # 2. Extract acoustic features
        numeric_feats = extract_recording_features(pre, config=cfg)

        # 3. Model inference
        prediction_result = self.predict_from_features(numeric_feats)

        # 4. Compile response with acoustic summary
        audio_summary = {
            "duration_seconds": round(pre.metadata.get("resampled_duration_seconds", 0.0), 2),
            "sample_rate_hz": pre.sr,
            "peak_amplitude": round(pre.metadata.get("peak_amplitude", 0.0), 4),
            "is_clipped": pre.metadata.get("is_clipped", False),
            "voiced_f0_mean_hz": round(numeric_feats.get("f0_mean", 0.0), 1),
            "voiced_ratio": round(numeric_feats.get("f0_voiced_ratio", 0.0), 3),
            "rms_energy_mean": round(numeric_feats.get("rms_mean", 0.0), 4),
            "spectral_centroid_hz": round(numeric_feats.get("spectral_centroid_mean", 0.0), 1),
            "low_energy_interval_count": int(numeric_feats.get("low_energy_interval_count", 0)),
        }

        return {
            "status": "success",
            "audio_summary": audio_summary,
            "acoustic_features_extracted_count": len(numeric_feats),
            "acoustic_features": numeric_feats,
            "research_prediction": prediction_result,
        }


# Singleton service instance
_service_instance: Optional[VoicePredictionService] = None


def get_prediction_service() -> VoicePredictionService:
    """Returns singleton instance of VoicePredictionService."""
    global _service_instance
    if _service_instance is None:
        _service_instance = VoicePredictionService()
    return _service_instance

