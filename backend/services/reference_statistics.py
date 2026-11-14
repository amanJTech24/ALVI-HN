"""
ALVI Reference Statistics Service — backend/services/reference_statistics.py
Computes and serves empirical, non-clinical acoustic reference distributions derived
from the cleaned DementiaNet research feature dataset (data/processed/voice_features_clean.csv).

PROVENANCE & CLINICAL DISCLAIMERS:
- Data Source: Cleaned DementiaNet audio features (100 recordings across 80 unique speakers).
- Nature of Corpus: Public broadcast interview speech, NOT clinically verified Alzheimer's patients.
- Clinical Limitation: This reference distribution is strictly exploratory and non-diagnostic.
  It does NOT establish medical normative standards, diagnostic cutoffs, or disease probabilities.
"""

from functools import lru_cache
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd

logger = logging.getLogger("alvi.reference_statistics")

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CLEAN_CSV_PATH = PROJECT_ROOT / "data" / "processed" / "voice_features_clean.csv"
EXTRACTION_SUMMARY_PATH = PROJECT_ROOT / "data" / "processed" / "extraction_summary.json"
MODEL_METADATA_PATH = PROJECT_ROOT / "backend" / "ml" / "models" / "model_metadata.json"

# Key acoustic metrics exposed for empirical case comparison
REFERENCE_METRICS = [
    {
        "key": "voice.f0_mean",
        "column": "f0_mean",
        "name": "Estimated Pitch (Voiced F0 Mean)",
        "unit": "Hz",
        "domain": "acoustic_prosody",
        "higher_atypical": False,
        "description": "Mean fundamental frequency of voiced speech frames.",
    },
    {
        "key": "voice.pause_ratio",
        "column": "low_energy_frame_ratio",
        "name": "Low-Energy Pause Ratio (Acoustic Proxy)",
        "unit": "ratio",
        "domain": "acoustic_hesitation",
        "higher_atypical": True,
        "description": "Proportion of audio frames falling below energy silence threshold.",
    },
    {
        "key": "voice.zcr",
        "column": "zcr_mean",
        "name": "Zero-Crossing Rate (ZCR Mean)",
        "unit": "",
        "domain": "acoustic_articulation",
        "higher_atypical": False,
        "description": "Rate at which audio signal changes sign; proxy for unvoiced/fricative speech components.",
    },
    {
        "key": "voice.rms",
        "column": "rms_mean",
        "name": "Speech RMS Energy Amplitude",
        "unit": "",
        "domain": "acoustic_intensity",
        "higher_atypical": False,
        "description": "Root-mean-square amplitude representing speech vocal energy stability.",
    },
    {
        "key": "voice.spectral_centroid",
        "column": "spectral_centroid_mean",
        "name": "Spectral Centroid Mean",
        "unit": "Hz",
        "domain": "acoustic_timbre",
        "higher_atypical": False,
        "description": "Center of mass of spectrum; proxy for speech brightness and formant distribution.",
    },
    {
        "key": "voice.duration",
        "column": "active_duration_seconds",
        "name": "Active Speech Duration",
        "unit": "s",
        "domain": "speech_duration",
        "higher_atypical": False,
        "description": "Total duration of voice-active speech segments excluding trailing silence.",
    },
    {
        "key": "voice.pause_count",
        "column": "low_energy_interval_count",
        "name": "Low-Energy Pause Intervals",
        "unit": "intervals",
        "domain": "acoustic_hesitation",
        "higher_atypical": True,
        "description": "Total count of discrete low-energy silence/hesitation intervals detected.",
    },
]


def _compute_metric_stats(series: pd.Series) -> Dict[str, float]:
    """Calculate descriptive distribution summary for a pandas numeric Series."""
    clean = series.dropna().astype(float)
    if len(clean) == 0:
        return {
            "count": 0,
            "mean": 0.0,
            "std": 0.0,
            "median": 0.0,
            "q1": 0.0,
            "q3": 0.0,
            "iqr": 0.0,
            "min": 0.0,
            "max": 0.0,
        }

    q1 = float(np.percentile(clean, 25))
    q3 = float(np.percentile(clean, 75))
    return {
        "count": int(len(clean)),
        "mean": round(float(clean.mean()), 4),
        "std": round(float(clean.std(ddof=1) if len(clean) > 1 else 0.0), 4),
        "median": round(float(clean.median()), 4),
        "q1": round(q1, 4),
        "q3": round(q3, 4),
        "iqr": round(q3 - q1, 4),
        "min": round(float(clean.min()), 4),
        "max": round(float(clean.max()), 4),
    }


class ReferenceStatisticsService:
    """Provides research reference acoustic distribution benchmarks."""

    def __init__(self, clean_csv_path: Optional[Path] = None):
        self.csv_path = clean_csv_path or CLEAN_CSV_PATH
        self._cached_stats: Optional[Dict[str, Any]] = None

    def get_reference_statistics(self) -> Dict[str, Any]:
        """Load and return the complete descriptive reference statistics dictionary."""
        if self._cached_stats is not None:
            return self._cached_stats

        if not self.csv_path.exists():
            logger.warning("Cleaned voice features CSV not found at %s. Returning fallback baseline.", self.csv_path)
            return self._generate_fallback_statistics()

        try:
            df = pd.read_csv(self.csv_path)
            stats = self._build_statistics_from_df(df)
            self._cached_stats = stats
            return stats
        except Exception as e:
            logger.error("Error computing reference statistics from %s: %s", self.csv_path, e, exc_info=True)
            return self._generate_fallback_statistics()

    def _build_statistics_from_df(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Compute statistical breakdown across overall cohort and group subsets."""
        total_records = len(df)
        unique_speakers = int(df["speaker_id"].nunique()) if "speaker_id" in df.columns else total_records
        group_counts = df["group"].value_counts().to_dict() if "group" in df.columns else {}

        metrics_stats: Dict[str, Any] = {}
        by_group_stats: Dict[str, Dict[str, Any]] = {
            "dementia": {},
            "nodementia": {},
        }

        for item in REFERENCE_METRICS:
            col = item["column"]
            key = item["key"]
            if col in df.columns:
                overall_summary = _compute_metric_stats(df[col])
                metrics_stats[key] = {
                    "name": item["name"],
                    "unit": item["unit"],
                    "domain": item["domain"],
                    "higher_atypical": item["higher_atypical"],
                    "description": item["description"],
                    "distribution": overall_summary,
                }

                # Breakdown by group
                if "group" in df.columns:
                    for grp in ["dementia", "nodementia"]:
                        subset = df[df["group"] == grp][col] if grp in group_counts else pd.Series(dtype=float)
                        by_group_stats[grp][key] = _compute_metric_stats(subset)
            else:
                logger.warning("Column %s not found in clean feature CSV.", col)

        # Dataset metadata
        provenance = {
            "dataset_name": "DementiaNet Interview Corpus (Cleaned Research Subset)",
            "total_recordings": total_records,
            "unique_speakers": unique_speakers,
            "subgroup_distribution": {
                "dementia_labeled": group_counts.get("dementia", 0),
                "nodementia_labeled": group_counts.get("nodementia", 0),
            },
            "cleaning_protocol": (
                "Filtered 76 exact duplicate audio pairs (152 rows) and multi-class speaker overlap "
                "to ensure speaker-independent empirical baseline."
            ),
            "nature_of_data": (
                "Public broadcast interviews and speeches. NOT clinically verified Alzheimer's patients."
            ),
            "clinical_disclaimer": (
                "These empirical distributions represent acoustic speech features from public recordings. "
                "They do NOT establish clinical diagnostic thresholds, normative medical ranges, or "
                "Alzheimer's disease probability estimates."
            ),
        }

        # Cognitive task empirical standard targets (Story & MindPlay protocols)
        cognitive_task_standards = {
            "story.score_percent": {
                "name": "Story Recall Accuracy",
                "unit": "%",
                "domain": "episodic_memory",
                "task": "Aarav Story v1.0 (8 Core Information Units)",
                "expected_median": 87.5,
                "expected_q1": 75.0,
                "expected_q3": 100.0,
                "min": 0.0,
                "max": 100.0,
                "description": "Percentage of 8 core information units accurately recalled.",
            },
            "mindplay.dual_binding": {
                "name": "Dual Feature Binding",
                "unit": "targets",
                "domain": "working_memory",
                "task": "MindPlay Challenge 1",
                "max_score": 2,
                "expected_median": 2.0,
                "description": "Accurate simultaneous recall of target shape and color attributes.",
            },
            "mindplay.sequence_order": {
                "name": "Narrative Chronology Sequencing",
                "unit": "boolean",
                "domain": "executive_sequencing",
                "task": "MindPlay Challenge 2",
                "expected_norm": "0 Transposition Inversions",
                "description": "Chronological ordering accuracy of narrative story cards.",
            },
            "mindplay.ch3_reaction_ms": {
                "name": "Visual Search Latency",
                "unit": "ms",
                "domain": "executive_reaction",
                "task": "MindPlay Challenge 3 (Target Discrimination)",
                "expected_median": 2200.0,
                "expected_q1": 1500.0,
                "expected_q3": 3100.0,
                "min": 600.0,
                "max": 6500.0,
                "description": "Latency in milliseconds to locate and select target visual stimuli.",
            },
        }

        return {
            "status": "success",
            "provenance": provenance,
            "acoustic_reference_metrics": metrics_stats,
            "by_group_acoustic_breakdown": by_group_stats,
            "cognitive_task_standards": cognitive_task_standards,
        }

    def _generate_fallback_statistics(self) -> Dict[str, Any]:
        """Provides hardcoded fallback based on documented Phase 2/3 extraction metrics."""
        return {
            "status": "fallback",
            "provenance": {
                "dataset_name": "DementiaNet Baseline (Fallback Estimates)",
                "total_recordings": 100,
                "unique_speakers": 80,
                "nature_of_data": "Public interviews; non-clinical reference distribution.",
                "clinical_disclaimer": "Exploratory research data only. Not clinically diagnostic.",
            },
            "acoustic_reference_metrics": {
                "voice.f0_mean": {
                    "name": "Estimated Pitch (Voiced F0 Mean)",
                    "unit": "Hz",
                    "domain": "acoustic_prosody",
                    "distribution": {"median": 165.0, "q1": 138.0, "q3": 195.0, "min": 85.0, "max": 280.0, "mean": 168.0, "std": 38.0},
                },
                "voice.pause_ratio": {
                    "name": "Low-Energy Pause Ratio",
                    "unit": "ratio",
                    "domain": "acoustic_hesitation",
                    "distribution": {"median": 0.18, "q1": 0.12, "q3": 0.26, "min": 0.04, "max": 0.58, "mean": 0.20, "std": 0.11},
                },
                "voice.rms": {
                    "name": "Speech RMS Energy Amplitude",
                    "unit": "",
                    "domain": "acoustic_intensity",
                    "distribution": {"median": 0.062, "q1": 0.041, "q3": 0.088, "min": 0.015, "max": 0.170, "mean": 0.067, "std": 0.032},
                },
                "voice.zcr": {
                    "name": "Zero-Crossing Rate",
                    "unit": "",
                    "domain": "acoustic_articulation",
                    "distribution": {"median": 0.085, "q1": 0.065, "q3": 0.115, "min": 0.025, "max": 0.220, "mean": 0.092, "std": 0.038},
                },
                "voice.spectral_centroid": {
                    "name": "Spectral Centroid Mean",
                    "unit": "Hz",
                    "domain": "acoustic_timbre",
                    "distribution": {"median": 1540.0, "q1": 1320.0, "q3": 1820.0, "min": 950.0, "max": 2650.0, "mean": 1580.0, "std": 320.0},
                },
            },
            "cognitive_task_standards": {},
        }


# Global singleton instance
_ref_service_instance: Optional[ReferenceStatisticsService] = None


def get_reference_statistics_service() -> ReferenceStatisticsService:
    """Retrieve singleton ReferenceStatisticsService."""
    global _ref_service_instance
    if _ref_service_instance is None:
        _ref_service_instance = ReferenceStatisticsService()
    return _ref_service_instance

