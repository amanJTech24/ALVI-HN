"""
ALVI ML - Audio Feature Extraction Engine
Extracts acoustic and prosodic features from speech recordings using Librosa and NumPy.
Outputs feature records containing MFCCs, deltas, pitch (F0), RMS energy,
spectral descriptors, acoustic activity proxies, and HNR proxies.
"""

import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import logging
from pathlib import Path
import sys
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

import librosa
import numpy as np
import pandas as pd

from .audio_preprocessing import (
    AudioPreprocessingError,
    PreprocessedAudio,
    load_and_preprocess_audio,
)
from .feature_config import DEFAULT_CONFIG, FeatureConfig

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("alvi.extract_features")


def compute_file_sha256(file_path: Path) -> str:
    """Computes SHA-256 hash of audio file contents for duplicate detection."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def extract_recording_features(
    pre: PreprocessedAudio, config: FeatureConfig = DEFAULT_CONFIG
) -> Dict[str, float]:
    """
    Extracts acoustic features from preprocessed 1D mono audio waveform (16 kHz).
    Returns flat dictionary of numeric features.
    """
    y = pre.y
    sr = pre.sr
    features: Dict[str, float] = {}

    # ─────────────────────────────────────────────────────────────
    # A. MFCC Features (1-13) + First-Order Deltas
    # ─────────────────────────────────────────────────────────────
    mfcc = librosa.feature.mfcc(
        y=y,
        sr=sr,
        n_mfcc=config.n_mfcc,
        n_fft=config.n_fft,
        hop_length=config.hop_length,
    )
    for i in range(config.n_mfcc):
        coeff_num = i + 1
        features[f"mfcc_{coeff_num}_mean"] = float(np.mean(mfcc[i]))
        features[f"mfcc_{coeff_num}_std"] = float(np.std(mfcc[i]))

    # First-order deltas (delta width=9 or min frames)
    if mfcc.shape[1] >= 9:
        mfcc_delta = librosa.feature.delta(mfcc, order=1)
        for i in range(config.n_mfcc):
            coeff_num = i + 1
            features[f"mfcc_delta_{coeff_num}_mean"] = float(np.mean(mfcc_delta[i]))
            features[f"mfcc_delta_{coeff_num}_std"] = float(np.std(mfcc_delta[i]))
    else:
        for i in range(config.n_mfcc):
            coeff_num = i + 1
            features[f"mfcc_delta_{coeff_num}_mean"] = 0.0
            features[f"mfcc_delta_{coeff_num}_std"] = 0.0

    # ─────────────────────────────────────────────────────────────
    # B. Zero-Crossing Rate (ZCR)
    # ─────────────────────────────────────────────────────────────
    zcr = librosa.feature.zero_crossing_rate(
        y=y, frame_length=config.n_fft, hop_length=config.hop_length
    )[0]
    features["zcr_mean"] = float(np.mean(zcr))
    features["zcr_std"] = float(np.std(zcr))

    # ─────────────────────────────────────────────────────────────
    # C. Pitch and Fundamental Frequency (F0) via YIN
    # ─────────────────────────────────────────────────────────────
    try:
        f0 = librosa.yin(
            y,
            fmin=config.fmin,
            fmax=config.fmax,
            sr=sr,
            frame_length=config.pitch_frame_length,
            hop_length=config.pitch_hop_length,
        )
        rms_pitch = librosa.feature.rms(
            y=y,
            frame_length=config.pitch_frame_length,
            hop_length=config.pitch_hop_length,
        )[0]

        max_pitch_rms = float(np.max(rms_pitch)) if len(rms_pitch) > 0 else 0.0
        pitch_energy_thresh = max_pitch_rms * config.f0_energy_threshold_ratio

        # Voiced frames: within valid speech F0 range and having audible energy
        voiced_mask = (
            (f0 > (config.fmin + 0.5))
            & (f0 < (config.fmax - 5.0))
            & (rms_pitch >= pitch_energy_thresh)
        )
        total_pitch_frames = len(f0)
        voiced_frames_count = int(np.sum(voiced_mask))

        if total_pitch_frames > 0:
            features["f0_voiced_ratio"] = float(voiced_frames_count / total_pitch_frames)
        else:
            features["f0_voiced_ratio"] = 0.0

        if voiced_frames_count > 0:
            voiced_f0 = f0[voiced_mask]
            features["f0_mean"] = float(np.mean(voiced_f0))
            features["f0_std"] = float(np.std(voiced_f0)) if voiced_frames_count > 1 else 0.0
            features["f0_min"] = float(np.min(voiced_f0))
            features["f0_max"] = float(np.max(voiced_f0))
        else:
            # Unvoiced fallback
            features["f0_mean"] = 0.0
            features["f0_std"] = 0.0
            features["f0_min"] = 0.0
            features["f0_max"] = 0.0
    except Exception as pitch_err:
        logger.warning("Pitch estimation fallback triggered: %s", pitch_err)
        features["f0_voiced_ratio"] = 0.0
        features["f0_mean"] = 0.0
        features["f0_std"] = 0.0
        features["f0_min"] = 0.0
        features["f0_max"] = 0.0

    # ─────────────────────────────────────────────────────────────
    # D. RMS Energy
    # ─────────────────────────────────────────────────────────────
    rms = librosa.feature.rms(
        y=y, frame_length=config.n_fft, hop_length=config.hop_length
    )[0]
    features["rms_mean"] = float(np.mean(rms))
    features["rms_std"] = float(np.std(rms))
    features["rms_min"] = float(np.min(rms))
    features["rms_max"] = float(np.max(rms))

    # ─────────────────────────────────────────────────────────────
    # E. Spectral Features
    # ─────────────────────────────────────────────────────────────
    sc = librosa.feature.spectral_centroid(
        y=y, sr=sr, n_fft=config.n_fft, hop_length=config.hop_length
    )[0]
    features["spectral_centroid_mean"] = float(np.mean(sc))
    features["spectral_centroid_std"] = float(np.std(sc))

    sb = librosa.feature.spectral_bandwidth(
        y=y, sr=sr, n_fft=config.n_fft, hop_length=config.hop_length
    )[0]
    features["spectral_bandwidth_mean"] = float(np.mean(sb))
    features["spectral_bandwidth_std"] = float(np.std(sb))

    s_roll = librosa.feature.spectral_rolloff(
        y=y, sr=sr, n_fft=config.n_fft, hop_length=config.hop_length, roll_percent=0.85
    )[0]
    features["spectral_rolloff_mean"] = float(np.mean(s_roll))
    features["spectral_rolloff_std"] = float(np.std(s_roll))

    s_flat = librosa.feature.spectral_flatness(
        y=y, n_fft=config.n_fft, hop_length=config.hop_length
    )[0]
    features["spectral_flatness_mean"] = float(np.mean(s_flat))
    features["spectral_flatness_std"] = float(np.std(s_flat))

    # ─────────────────────────────────────────────────────────────
    # F. Temporal & Activity Features (Acoustic Proxies)
    # ─────────────────────────────────────────────────────────────
    duration_sec = float(len(y) / sr)
    features["duration_seconds"] = duration_sec

    # Active energy threshold: 10% of 95th percentile RMS
    p95_rms = float(np.percentile(rms, 95)) if len(rms) > 0 else 0.0
    active_thresh = max(p95_rms * config.activity_threshold_ratio, 1e-4)
    is_active = rms >= active_thresh

    frame_duration_sec = float(config.hop_length / sr)
    active_duration = float(np.sum(is_active) * frame_duration_sec)
    features["active_duration_seconds"] = active_duration
    features["low_energy_frame_ratio"] = float(np.mean(~is_active)) if len(rms) > 0 else 0.0

    # Contiguous low-energy intervals
    low_energy_intervals = []
    current_interval_len = 0
    for flag in (~is_active):
        if flag:
            current_interval_len += 1
        else:
            if current_interval_len > 0:
                interval_dur = current_interval_len * frame_duration_sec
                if interval_dur >= config.min_interval_duration_seconds:
                    low_energy_intervals.append(interval_dur)
                current_interval_len = 0
    if current_interval_len > 0:
        interval_dur = current_interval_len * frame_duration_sec
        if interval_dur >= config.min_interval_duration_seconds:
            low_energy_intervals.append(interval_dur)

    features["low_energy_interval_count"] = float(len(low_energy_intervals))
    features["low_energy_interval_mean_duration"] = (
        float(np.mean(low_energy_intervals)) if low_energy_intervals else 0.0
    )

    # ─────────────────────────────────────────────────────────────
    # G. Optional Advanced Features: HNR Proxy & Spectral Contrast
    # ─────────────────────────────────────────────────────────────
    try:
        y_harm, y_perc = librosa.effects.hpss(y)
        harm_pow = float(np.sum(y_harm**2))
        perc_pow = float(np.sum(y_perc**2))
        hnr_proxy = float(10.0 * np.log10((harm_pow + 1e-10) / (perc_pow + 1e-10)))
        features["hnr_proxy_db"] = hnr_proxy
    except Exception:
        features["hnr_proxy_db"] = 0.0

    try:
        contrast = librosa.feature.spectral_contrast(
            y=y, sr=sr, n_fft=config.n_fft, hop_length=config.hop_length
        )
        features["spectral_contrast_mean"] = float(np.mean(contrast))
        features["spectral_contrast_std"] = float(np.std(contrast))
    except Exception:
        features["spectral_contrast_mean"] = 0.0
        features["spectral_contrast_std"] = 0.0

    return features


def process_single_file(
    item: Dict[str, Any], config: FeatureConfig
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """
    Worker function to process one audio file.
    Returns (feature_row_or_none, error_row_or_none).
    """
    file_path = Path(item["file_path"])
    group = item["group"]
    speaker_id = item["speaker_id"]

    try:
        pre = load_and_preprocess_audio(file_path, config=config)
        numeric_feats = extract_recording_features(pre, config=config)

        row = {
            "file_path": item["relative_path"],
            "filename": item["filename"],
            "group": group,
            "speaker_id": speaker_id,
            "file_sha256": item["file_sha256"],
            "is_cross_group_duplicate": item["is_cross_group_duplicate"],
            "is_clipped": pre.metadata.get("is_clipped", False),
            "original_sr": pre.metadata.get("original_sr", 0),
            "original_channels": pre.metadata.get("original_channels", 0),
            "original_duration_seconds": pre.metadata.get("original_duration_seconds", 0.0),
            "resampled_duration_seconds": pre.metadata.get("resampled_duration_seconds", 0.0),
        }
        row.update(numeric_feats)
        return row, None

    except AudioPreprocessingError as pre_err:
        return None, {
            "file_path": item["relative_path"],
            "filename": item["filename"],
            "group": group,
            "error_type": pre_err.error_type,
            "error_message": pre_err.message,
        }
    except Exception as unk_err:
        return None, {
            "file_path": item["relative_path"],
            "filename": item["filename"],
            "group": group,
            "error_type": "UnexpectedExtractionError",
            "error_message": str(unk_err),
        }


def scan_dataset_files(
    data_dir: Path,
) -> Tuple[List[Dict[str, Any]], Dict[str, List[Dict[str, Any]]]]:
    """
    Scans data directory recursively for supported audio formats.
    Records relative path, group label, speaker ID, and SHA-256 hash.
    Detects cross-group duplicates.
    """
    supported_extensions = {".wav", ".mp3", ".m4a", ".mp4", ".flac", ".ogg"}
    discovered_files: List[Dict[str, Any]] = []
    hash_map: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    groups = ["dementia", "nodementia"]
    for group in groups:
        group_path = data_dir / group
        if not group_path.is_dir():
            logger.warning("Group directory not found: %s", group_path)
            continue

        for p in sorted(group_path.rglob("*")):
            if p.is_file() and p.suffix.lower() in supported_extensions:
                rel_parts = p.relative_to(group_path).parts
                if len(rel_parts) > 1:
                    speaker_id = rel_parts[0]
                else:
                    speaker_id = "unknown"

                file_hash = compute_file_sha256(p)
                entry = {
                    "file_path": str(p),
                    "relative_path": p.relative_to(data_dir).as_posix(),
                    "filename": p.name,
                    "group": group,
                    "speaker_id": speaker_id,
                    "file_sha256": file_hash,
                    "extension": p.suffix.lower(),
                }
                discovered_files.append(entry)
                hash_map[file_hash].append(entry)

    # Flag cross-group duplicates
    for f in discovered_files:
        matching_entries = hash_map[f["file_sha256"]]
        groups_present = set(e["group"] for e in matching_entries)
        f["is_cross_group_duplicate"] = bool(len(groups_present) > 1)
        f["duplicate_instance_count"] = len(matching_entries)

    return discovered_files, hash_map


def process_dataset(
    data_dir: Path = DEFAULT_CONFIG.default_data_dir,
    output_dir: Path = DEFAULT_CONFIG.default_output_dir,
    limit_per_group: Optional[int] = None,
    workers: int = 4,
    config: FeatureConfig = DEFAULT_CONFIG,
) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, Any]]:
    """
    Executes full feature extraction pipeline on the dataset with multi-worker parallelism:
    1. Scans dataset and flags duplicates.
    2. Applies per-group limit if specified.
    3. Streams each audio file through preprocessing and feature extraction.
    4. Aggregates results and logs errors.
    5. Saves voice_features.csv, extraction_errors.csv, and extraction_summary.json.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Scanning dataset in: %s", data_dir)
    discovered_files, hash_map = scan_dataset_files(data_dir)
    logger.info("Discovered %d audio files across dataset.", len(discovered_files))

    if limit_per_group is not None and limit_per_group > 0:
        logger.info("Applying limit of %d recordings per group.", limit_per_group)
        group_counts: Dict[str, int] = defaultdict(int)
        filtered_files = []
        for f in discovered_files:
            g = f["group"]
            if group_counts[g] < limit_per_group:
                filtered_files.append(f)
                group_counts[g] += 1
        processing_list = filtered_files
    else:
        processing_list = discovered_files

    total_to_process = len(processing_list)
    logger.info("Processing %d audio recordings with %d worker threads...", total_to_process, workers)

    feature_rows: List[Dict[str, Any]] = []
    error_rows: List[Dict[str, Any]] = []

    start_time = time.time()
    processed_count = 0
    lock = threading.Lock()

    if workers > 1:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(process_single_file, item, config): item
                for item in processing_list
            }
            for fut in as_completed(futures):
                item = futures[fut]
                feat, err = fut.result()
                with lock:
                    processed_count += 1
                    if feat is not None:
                        feature_rows.append(feat)
                    if err is not None:
                        error_rows.append(err)

                    if (
                        processed_count % 10 == 0
                        or processed_count == total_to_process
                        or processed_count <= 5
                    ):
                        elapsed = time.time() - start_time
                        logger.info(
                            "[%d/%d] Finished %s (%s) [Elapsed: %.1fs, Active Success: %d, Errors: %d]",
                            processed_count,
                            total_to_process,
                            item["filename"],
                            item["group"],
                            elapsed,
                            len(feature_rows),
                            len(error_rows),
                        )
    else:
        # Serial fallback
        for idx, item in enumerate(processing_list, 1):
            feat, err = process_single_file(item, config)
            if feat is not None:
                feature_rows.append(feat)
            if err is not None:
                error_rows.append(err)
            if idx % 10 == 0 or idx == total_to_process or idx <= 5:
                elapsed = time.time() - start_time
                logger.info(
                    "[%d/%d] Finished %s (%s) [Elapsed: %.1fs, Active Success: %d, Errors: %d]",
                    idx,
                    total_to_process,
                    item["filename"],
                    item["group"],
                    elapsed,
                    len(feature_rows),
                    len(error_rows),
                )

    total_time = time.time() - start_time
    logger.info("Feature extraction completed in %.2f seconds.", total_time)

    # Sort feature rows consistently by group and file_path
    feature_rows.sort(key=lambda x: (x.get("group", ""), x.get("file_path", "")))

    df_features = pd.DataFrame(feature_rows)
    if len(error_rows) == 0:
        df_errors = pd.DataFrame(
            columns=["file_path", "filename", "group", "error_type", "error_message"]
        )
    else:
        df_errors = pd.DataFrame(error_rows)

    features_csv_path = output_dir / config.features_csv_name
    errors_csv_path = output_dir / config.errors_csv_name
    summary_json_path = output_dir / config.summary_json_name

    df_features.to_csv(features_csv_path, index=False)
    df_errors.to_csv(errors_csv_path, index=False)
    logger.info("Saved feature dataset to: %s", features_csv_path)
    logger.info("Saved error log to: %s", errors_csv_path)

    cross_group_duplicate_count = sum(
        1 for f in feature_rows if f.get("is_cross_group_duplicate", False)
    )
    group_counts_dict = Counter(r["group"] for r in feature_rows)
    speaker_counts_dict = Counter(r["speaker_id"] for r in feature_rows)
    unknown_speaker_count = speaker_counts_dict.get("unknown", 0)
    known_speaker_count = len(speaker_counts_dict) - (1 if "unknown" in speaker_counts_dict else 0)

    feature_col_names = [
        c
        for c in df_features.columns
        if c
        not in [
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
    ]

    summary = {
        "dataset_directory": str(data_dir),
        "output_directory": str(output_dir),
        "total_files_discovered": len(discovered_files),
        "total_files_processed_in_run": len(processing_list),
        "successful_extractions": len(df_features),
        "failed_extractions": len(df_errors),
        "group_wise_counts": dict(group_counts_dict),
        "cross_group_duplicate_count": cross_group_duplicate_count,
        "unique_speakers_identified": known_speaker_count,
        "unknown_speakers_count": unknown_speaker_count,
        "total_feature_columns": len(df_features.columns),
        "acoustic_feature_columns_count": len(feature_col_names),
        "acoustic_feature_names": feature_col_names,
        "processing_duration_seconds": round(total_time, 2),
        "processing_config": {
            "target_sr": config.target_sr,
            "mono": config.mono,
            "n_mfcc": config.n_mfcc,
            "fmin": config.fmin,
            "fmax": config.fmax,
            "min_duration_seconds": config.min_duration_seconds,
            "normalize_peak": config.normalize_peak,
            "workers": workers,
        },
        "warnings": [
            "76 identical SHA-256 hash pairs exist across dementia and nodementia directories in DementiaNet.",
            "Cross-group duplicates have conflicting ground-truth targets and must be deduplicated in Phase 3.",
            "Energy-based silence measurements are acoustic proxies, not clinical speech-pause ground truth.",
            "Labels represent exploratory research annotations and are not clinically verified medical diagnoses.",
        ],
    }

    with open(summary_json_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    logger.info("Saved summary report to: %s", summary_json_path)

    return df_features, df_errors, summary


def main():
    parser = argparse.ArgumentParser(description="ALVI Acoustic Feature Extraction Engine")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=DEFAULT_CONFIG.default_data_dir,
        help="Path to DementiaNet data directory containing dementia/ and nodementia/ subfolders.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_CONFIG.default_output_dir,
        help="Path to directory where extracted CSV and JSON files will be stored.",
    )
    parser.add_argument(
        "--limit-per-group",
        type=int,
        default=None,
        help="Optional maximum number of recordings to process per research group (for testing).",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Number of parallel worker threads for feature extraction (default: 4).",
    )
    args = parser.parse_args()

    process_dataset(
        data_dir=args.data_dir,
        output_dir=args.output_dir,
        limit_per_group=args.limit_per_group,
        workers=args.workers,
    )


if __name__ == "__main__":
    main()
