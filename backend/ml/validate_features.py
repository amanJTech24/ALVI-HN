"""
ALVI ML - Feature Validation Engine
Validates the extracted feature dataset (voice_features.csv) for data integrity,
numerical stability (NaNs, Infs, near-constant columns), duplicate hashes,
implausible values, speaker overlap, and participant-independent training readiness.
"""

import argparse
import json
import logging
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pandas as pd

from .feature_config import DEFAULT_CONFIG

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("alvi.validate_features")


def validate_feature_dataset(
    features_csv_path: Path = DEFAULT_CONFIG.default_output_dir
    / DEFAULT_CONFIG.features_csv_name,
) -> Dict[str, Any]:
    """
    Performs comprehensive data quality and machine learning integrity checks on the feature CSV.
    Returns structured dictionary with findings and prints formatted validation report.
    """
    p = Path(features_csv_path)
    if not p.is_file():
        raise FileNotFoundError(f"Feature CSV not found at: {p}")

    df = pd.read_csv(p)
    logger.info("Loaded feature dataset: %d rows x %d columns", len(df), len(df.columns))

    results: Dict[str, Any] = {
        "features_csv_path": str(p),
        "total_rows": len(df),
        "total_columns": len(df.columns),
        "issues_found": [],
        "warnings": [],
    }

    # 1. Group Counts
    group_counts = df["group"].value_counts().to_dict() if "group" in df.columns else {}
    results["group_counts"] = group_counts

    # 2. Metadata vs Numeric Feature columns
    meta_cols = [
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
    numeric_feature_cols = [c for c in df.columns if c not in meta_cols]
    results["numeric_feature_count"] = len(numeric_feature_cols)

    # 3. Missing / Null / NaN values
    null_counts = df[numeric_feature_cols].isnull().sum()
    cols_with_nulls = null_counts[null_counts > 0].to_dict()
    results["columns_with_nulls"] = cols_with_nulls
    if cols_with_nulls:
        results["issues_found"].append(
            f"{len(cols_with_nulls)} feature columns contain null/NaN values: {cols_with_nulls}"
        )

    # 4. Infinite values check
    numeric_df = df[numeric_feature_cols].select_dtypes(include=[np.number])
    inf_counts = np.isinf(numeric_df).sum()
    cols_with_inf = inf_counts[inf_counts > 0].to_dict()
    results["columns_with_inf"] = cols_with_inf
    if cols_with_inf:
        results["issues_found"].append(
            f"{len(cols_with_inf)} feature columns contain infinite values: {cols_with_inf}"
        )

    # 5. Constant or Near-Constant Columns (variance < 1e-6 or unique values <= 1)
    near_constant_cols = []
    for col in numeric_df.columns:
        vals = numeric_df[col].dropna()
        if len(vals) > 0:
            var = float(np.var(vals))
            if var < 1e-6 or vals.nunique() <= 1:
                near_constant_cols.append({"column": col, "variance": var, "nunique": vals.nunique()})
    results["near_constant_columns"] = near_constant_cols
    if near_constant_cols:
        results["warnings"].append(
            f"{len(near_constant_cols)} columns are constant or near-constant (variance < 1e-6)."
        )

    # 6. Duplicate records check
    if "file_sha256" in df.columns:
        hash_dupes = df["file_sha256"].duplicated(keep=False).sum()
        results["duplicate_hash_rows_count"] = int(hash_dupes)
        if hash_dupes > 0:
            results["warnings"].append(
                f"{hash_dupes} rows have duplicate SHA-256 hashes across the dataset."
            )

    if "is_cross_group_duplicate" in df.columns:
        cross_dupes = int(df["is_cross_group_duplicate"].sum())
        results["cross_group_duplicate_count"] = cross_dupes
        if cross_dupes > 0:
            results["warnings"].append(
                f"{cross_dupes} rows are cross-group duplicates (identical file exists in both dementia and nodementia)."
            )

    # 7. Implausible Durations check (< 2s or > 600s)
    if "duration_seconds" in df.columns:
        implausible_short = df[df["duration_seconds"] < 2.0]
        implausible_long = df[df["duration_seconds"] > 600.0]
        results["implausible_short_count"] = len(implausible_short)
        results["implausible_long_count"] = len(implausible_long)
        if len(implausible_short) > 0 or len(implausible_long) > 0:
            results["issues_found"].append(
                f"Implausible durations found: {len(implausible_short)} < 2s, {len(implausible_long)} > 600s."
            )

    # 8. Extreme Pitch (F0) values check
    if "f0_mean" in df.columns:
        voiced_rows = df[df["f0_voiced_ratio"] > 0]
        extreme_low_f0 = voiced_rows[voiced_rows["f0_mean"] < 50.0]
        extreme_high_f0 = voiced_rows[voiced_rows["f0_mean"] > 500.0]
        results["extreme_low_f0_count"] = len(extreme_low_f0)
        results["extreme_high_f0_count"] = len(extreme_high_f0)
        if len(extreme_low_f0) > 0 or len(extreme_high_f0) > 0:
            results["warnings"].append(
                f"Extreme voiced F0 values detected: {len(extreme_low_f0)} < 50Hz, {len(extreme_high_f0)} > 500Hz."
            )

    # 9. Speaker Identification & Missing Identifiers
    if "speaker_id" in df.columns:
        unknown_speakers = (df["speaker_id"] == "unknown").sum()
        unique_speakers = df["speaker_id"].nunique()
        results["unknown_speaker_count"] = int(unknown_speakers)
        results["unique_speaker_count"] = int(unique_speakers)

        # Cross-class speaker overlap analysis
        d_speakers = set(df[df["group"] == "dementia"]["speaker_id"])
        nd_speakers = set(df[df["group"] == "nodementia"]["speaker_id"])
        speaker_overlap = d_speakers.intersection(nd_speakers)
        results["speakers_in_dementia"] = len(d_speakers)
        results["speakers_in_nodementia"] = len(nd_speakers)
        results["overlapping_speakers_count"] = len(speaker_overlap)
        if len(speaker_overlap) > 0:
            results["warnings"].append(
                f"Participant-independent risk: {len(speaker_overlap)} speakers appear in both dementia and nodementia classes!"
            )

    # 10. Recording quality flags (clipping, extreme low energy)
    if "is_clipped" in df.columns:
        clipped_count = int(df["is_clipped"].sum())
        results["clipped_recordings_count"] = clipped_count

    if "low_energy_frame_ratio" in df.columns:
        predominantly_silent = int((df["low_energy_frame_ratio"] > 0.85).sum())
        results["predominantly_silent_recordings_count"] = predominantly_silent

    # 11. Participant-Independent Training Readiness Assessment
    readiness_notes = []
    if results.get("cross_group_duplicate_count", 0) > 0:
        readiness_notes.append(
            "CRITICAL: Exact duplicate recordings with conflicting class labels MUST be pruned before training."
        )
    if results.get("overlapping_speakers_count", 0) > 0:
        readiness_notes.append(
            "CRITICAL: Standard random train-test splitting will cause severe identity leakage. "
            "Phase 3 must enforce GroupKFold by speaker_id after resolving cross-class speaker assignments."
        )
    if not results["issues_found"]:
        readiness_notes.append(
            "Numerical feature matrix is complete, non-empty, and free of NaNs/Infs."
        )

    results["training_readiness_assessment"] = readiness_notes

    # ─────────────────────────────────────────────────────────────
    # Console Report Generation
    # ─────────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("ALVI ML — ACOUSTIC FEATURE DATASET VALIDATION REPORT")
    print("=" * 70)
    print(f"Dataset Path: {p}")
    print(f"Total Rows:   {results['total_rows']}")
    print(f"Total Cols:   {results['total_columns']} (Metadata: {len(meta_cols)}, Numeric Features: {results['numeric_feature_count']})")
    print(f"Group Distribution: {results['group_counts']}")
    print("-" * 70)
    print("NUMERICAL INTEGRITY:")
    print(f"  Columns with Null/NaN:     {len(results['columns_with_nulls'])}")
    print(f"  Columns with Inf:          {len(results['columns_with_inf'])}")
    print(f"  Near-constant columns:     {len(results['near_constant_columns'])}")
    print(f"  Clipped recordings:        {results.get('clipped_recordings_count', 0)}")
    print(f"  Predominantly silent:      {results.get('predominantly_silent_recordings_count', 0)}")
    print("-" * 70)
    print("SPEAKER & LEAKAGE AUDIT:")
    print(f"  Unique Speakers:           {results.get('unique_speaker_count', 0)}")
    print(f"  Unknown Speakers:          {results.get('unknown_speaker_count', 0)}")
    print(f"  Overlapping Speakers:      {results.get('overlapping_speakers_count', 0)}")
    print(f"  Cross-Group Duplicates:    {results.get('cross_group_duplicate_count', 0)}")
    print("-" * 70)
    print("PARTICIPANT-INDEPENDENT TRAINING READINESS:")
    for note in readiness_notes:
        print(f"  * {note}")
    if results["warnings"]:
        print("-" * 70)
        print("WARNINGS & GOVERNANCE FLAGS:")
        for w in results["warnings"]:
            print(f"  [!] {w}")
    print("=" * 70 + "\n")

    return results


def main():
    parser = argparse.ArgumentParser(description="ALVI Feature Dataset Validation Engine")
    parser.add_argument(
        "--features-path",
        type=Path,
        default=DEFAULT_CONFIG.default_output_dir / DEFAULT_CONFIG.features_csv_name,
        help="Path to voice_features.csv",
    )
    args = parser.parse_args()
    validate_feature_dataset(args.features_path)


if __name__ == "__main__":
    main()

