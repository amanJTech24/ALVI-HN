"""
ALVI Machine Learning Subsystem - Audio Processing, Feature Extraction & Baseline Models
"""

from .feature_config import FeatureConfig, DEFAULT_CONFIG
from .audio_preprocessing import (
    load_and_preprocess_audio,
    AudioPreprocessingError,
    PreprocessedAudio,
)
from .clean_dataset import clean_feature_dataset
from .audit_labels import audit_dataset_labels
from .model_config import ModelConfig, DEFAULT_MODEL_CONFIG
from .train_voice import train_and_evaluate_all_models
from .evaluate_voice import compute_classification_metrics

__all__ = [
    "FeatureConfig",
    "DEFAULT_CONFIG",
    "load_and_preprocess_audio",
    "AudioPreprocessingError",
    "PreprocessedAudio",
    "clean_feature_dataset",
    "audit_dataset_labels",
    "ModelConfig",
    "DEFAULT_MODEL_CONFIG",
    "train_and_evaluate_all_models",
    "compute_classification_metrics",
]
