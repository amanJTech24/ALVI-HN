"""
ALVI ML - Model Training & Evaluation Configuration (Phase 3)
Defines feature schema, model architectures, hyperparameter grids,
reproducibility seeds, and artifact paths.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List


@dataclass(frozen=True)
class ModelConfig:
    """Configuration for participant-independent ML training and evaluation."""

    # Paths
    clean_features_path: Path = Path("data/processed/voice_features_clean.csv")
    models_dir: Path = Path("backend/ml/models")
    best_model_path: Path = Path("backend/ml/models/voice_model.joblib")
    metadata_json_path: Path = Path("backend/ml/models/model_metadata.json")
    figures_dir: Path = Path("backend/ml/models/figures")

    # Target & Grouping
    target_column: str = "group"
    group_column: str = "speaker_id"
    positive_class: str = "dementia"
    negative_class: str = "nodementia"

    # Columns excluded from feature inputs
    metadata_columns: List[str] = field(
        default_factory=lambda: [
            "file_path",
            "filename",
            "group",
            "speaker_id",
            "file_sha256",
            "is_cross_group_duplicate",
            "is_clipped",
            "original_sr",
            "original_channels",
            "original_duration_seconds",
            "resampled_duration_seconds",
        ]
    )

    # Evaluation & Splitting
    test_size: float = 0.20  # 20% of independent speakers reserved for held-out test
    n_splits_cv: int = 5  # 5-fold cross-validation on training speakers
    random_state: int = 42  # Seed for reproducible splits and training

    # Hyperparameter grids for GridSearchCV with GroupKFold
    logreg_param_grid: Dict[str, Any] = field(
        default_factory=lambda: {
            "classifier__C": [0.01, 0.1, 1.0, 5.0, 10.0],
            "classifier__solver": ["lbfgs"],
            "classifier__max_iter": [1000],
            "classifier__class_weight": ["balanced"],
        }
    )

    rf_param_grid: Dict[str, Any] = field(
        default_factory=lambda: {
            "classifier__n_estimators": [50, 100],
            "classifier__max_depth": [3, 5, None],
            "classifier__min_samples_split": [2, 5],
            "classifier__class_weight": ["balanced"],
        }
    )

    svm_param_grid: Dict[str, Any] = field(
        default_factory=lambda: {
            "classifier__C": [0.1, 1.0, 10.0],
            "classifier__kernel": ["rbf", "linear"],
            "classifier__gamma": ["scale", "auto"],
            "classifier__class_weight": ["balanced"],
            "classifier__probability": [True],
        }
    )


DEFAULT_MODEL_CONFIG = ModelConfig()
