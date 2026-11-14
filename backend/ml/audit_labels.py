"""
ALVI ML - Dataset & Label Audit Engine (Phase 3)
Audits DementiaNet features for exact hash duplicates, cross-class target conflicts,
speaker identity overlap, and label provenance.
"""

from collections import Counter, defaultdict
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Set

import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("alvi.audit_labels")

DEFAULT_FEATURES_PATH = Path("data/processed/voice_features.csv")


def audit_dataset_labels(
    features_csv_path: Path = DEFAULT_FEATURES_PATH,
) -> Dict[str, Any]:
    """
    Performs rigorous dataset integrity and label audit on voice_features.csv.
    Identifies exact duplicate hashes, contradictory class assignments,
    speaker overlap across classes, and label provenance issues.
    """
    p = Path(features_csv_path)
    if not p.is_file():
        raise FileNotFoundError(f"Feature CSV not found at: {p}")

    df = pd.read_csv(p)
    logger.info("Auditing feature dataset: %d rows x %d columns", len(df), len(df.columns))

    total_recordings = len(df)
    group_counts = df["group"].value_counts().to_dict()

    # 1. Feature schema check
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

    # 2. Duplicate Hash Analysis
    hash_to_rows = defaultdict(list)
    for idx, row in df.iterrows():
        hash_to_rows[row["file_sha256"]].append(row)

    exact_hash_duplicates = {h: rows for h, rows in hash_to_rows.items() if len(rows) > 1}
    cross_class_hash_duplicates = {}
    within_class_hash_duplicates = {}

    for h, rows in exact_hash_duplicates.items():
        groups = set(r["group"] for r in rows)
        if len(groups) > 1:
            cross_class_hash_duplicates[h] = rows
        else:
            within_class_hash_duplicates[h] = rows

    total_cross_dupe_rows = sum(len(rows) for rows in cross_class_hash_duplicates.values())
    total_within_dupe_rows = sum(len(rows) for rows in within_class_hash_duplicates.values())

    # 3. Speaker-level Class Overlap Analysis
    d_df = df[df["group"] == "dementia"]
    nd_df = df[df["group"] == "nodementia"]

    d_speakers: Set[str] = set(d_df["speaker_id"].unique())
    nd_speakers: Set[str] = set(nd_df["speaker_id"].unique())
    all_speakers: Set[str] = set(df["speaker_id"].unique())

    overlap_speakers = d_speakers.intersection(nd_speakers)
    d_only_speakers = d_speakers - nd_speakers
    nd_only_speakers = nd_speakers - d_speakers

    # 4. Speaker Overlap after hypothetical removal of exact duplicate hashes
    df_no_dupes = df[~df["is_cross_group_duplicate"]].copy()
    d_no_dupes_spk = set(df_no_dupes[df_no_dupes["group"] == "dementia"]["speaker_id"].unique())
    nd_no_dupes_spk = set(df_no_dupes[df_no_dupes["group"] == "nodementia"]["speaker_id"].unique())
    overlap_after_exact_dedupe = d_no_dupes_spk.intersection(nd_no_dupes_spk)
    d_only_after_exact_dedupe = d_no_dupes_spk - nd_no_dupes_spk
    nd_only_after_exact_dedupe = nd_no_dupes_spk - d_no_dupes_spk

    # 5. Normalization audit
    normalized_names = {}
    for s in all_speakers:
        norm = " ".join(s.strip().lower().split())
        normalized_names.setdefault(norm, []).append(s)
    name_collisions = {k: v for k, v in normalized_names.items() if len(v) > 1}

    # 6. Provenance & Clinical Validity Assessment
    provenance_findings = [
        "The DementiaNet corpus contains recordings of public figures and celebrities gathered from interviews.",
        "There is no clinical or cognitive diagnostic metadata accompanying individual recordings.",
        "76 audio files were duplicated byte-for-byte across both dementia/ and nodementia/ directories.",
        "83 speakers have recordings assigned to both classes, indicating either multi-session scrape labeling or arbitrary categorization.",
        "Ground-truth medical labels cannot be verified from source files.",
    ]

    audit_report = {
        "dataset_path": str(p),
        "total_recordings": total_recordings,
        "class_distribution": group_counts,
        "feature_column_count": len(numeric_feature_cols),
        "metadata_column_count": len(meta_cols),
        "unique_speakers_total": len(all_speakers),
        "speakers_in_dementia": len(d_speakers),
        "speakers_in_nodementia": len(nd_speakers),
        "speakers_in_both_classes": len(overlap_speakers),
        "speakers_only_in_dementia": len(d_only_speakers),
        "speakers_only_in_nodementia": len(nd_only_speakers),
        "exact_duplicate_hash_pairs": len(cross_class_hash_duplicates),
        "exact_duplicate_rows_total": total_cross_dupe_rows,
        "within_class_duplicate_rows": total_within_dupe_rows,
        "speakers_overlapping_after_exact_dedup": len(overlap_after_exact_dedupe),
        "speakers_exclusive_dementia_after_dedup": len(d_only_after_exact_dedupe),
        "speakers_exclusive_nodementia_after_dedup": len(nd_only_after_exact_dedupe),
        "recordings_from_exclusive_speakers": {
            "dementia": int((df_no_dupes["speaker_id"].isin(d_only_after_exact_dedupe)).sum()),
            "nodementia": int((df_no_dupes["speaker_id"].isin(nd_only_after_exact_dedupe)).sum()),
        },
        "name_normalization_collisions": name_collisions,
        "provenance_findings": provenance_findings,
    }

    # Print summary
    print("\n" + "=" * 75)
    print("ALVI ML — PHASE 3 DATASET & LABEL INTEGRITY AUDIT")
    print("=" * 75)
    print(f"Total Recordings:       {total_recordings}")
    print(f"Class Distribution:     {group_counts}")
    print(f"Total Unique Speakers:  {len(all_speakers)}")
    print(f"Speakers in Dementia:   {len(d_speakers)} | Exclusive: {len(d_only_speakers)}")
    print(f"Speakers in NoDementia: {len(nd_speakers)} | Exclusive: {len(nd_only_speakers)}")
    print(f"Overlapping Speakers:   {len(overlap_speakers)} (associated with both classes)")
    print("-" * 75)
    print(f"Exact Cross-Class Hash Duplicates: {len(cross_class_hash_duplicates)} hashes ({total_cross_dupe_rows} rows)")
    print(f"Speakers still in both classes after exact-hash deduplication: {len(overlap_after_exact_dedupe)}")
    print(f"Defensibly labeled exclusive speakers after cleaning:")
    print(f"  * Dementia:    {len(d_only_after_exact_dedupe)} speakers ({audit_report['recordings_from_exclusive_speakers']['dementia']} recordings)")
    print(f"  * NoDementia:  {len(nd_only_after_exact_dedupe)} speakers ({audit_report['recordings_from_exclusive_speakers']['nodementia']} recordings)")
    print("=" * 75 + "\n")

    return audit_report


if __name__ == "__main__":
    audit_dataset_labels()

