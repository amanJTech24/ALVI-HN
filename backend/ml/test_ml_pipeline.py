"""
ALVI ML - Unit & Pipeline Integrity Tests (Phase 3)
Verifies cleaned feature matrix, zero speaker leakage, model loading,
prediction schema compliance, and metadata consistency.
"""

import json
from pathlib import Path
import unittest

import joblib
import numpy as np
import pandas as pd

from .model_config import DEFAULT_MODEL_CONFIG


class TestALVIPipeline(unittest.TestCase):
    """Test suite validating data cleaning, speaker isolation, and model artifact integrity."""

    def setUp(self):
        self.clean_csv_path = Path("data/processed/voice_features_clean.csv")
        self.report_json_path = Path("data/processed/data_cleaning_report.json")
        self.excluded_csv_path = Path("data/processed/excluded_records.csv")
        self.model_path = DEFAULT_MODEL_CONFIG.best_model_path
        self.metadata_path = DEFAULT_MODEL_CONFIG.metadata_json_path

    def test_01_clean_dataset_exists_and_valid(self):
        """Verifies cleaned CSV exists, has exactly 100 rows and 90 columns, and 0 nulls."""
        self.assertTrue(self.clean_csv_path.is_file(), f"Missing: {self.clean_csv_path}")
        df = pd.read_csv(self.clean_csv_path)
        self.assertEqual(len(df), 100, f"Expected 100 rows, found {len(df)}")
        self.assertEqual(len(df.columns), 90, f"Expected 90 columns, found {len(df.columns)}")
        self.assertEqual(df.isnull().sum().sum(), 0, "Clean dataset contains unexpected nulls")

    def test_02_zero_hash_duplicates_in_clean_data(self):
        """Verifies zero duplicate SHA-256 hashes remain in clean dataset."""
        df = pd.read_csv(self.clean_csv_path)
        dupes = df["file_sha256"].duplicated().sum()
        self.assertEqual(dupes, 0, f"Found {dupes} duplicate hashes in clean dataset")

    def test_03_zero_speaker_leakage_between_classes(self):
        """Verifies zero speaker overlap exists between dementia and nodementia in clean data."""
        df = pd.read_csv(self.clean_csv_path)
        d_speakers = set(df[df["group"] == "dementia"]["speaker_id"])
        nd_speakers = set(df[df["group"] == "nodementia"]["speaker_id"])
        overlap = d_speakers.intersection(nd_speakers)
        self.assertEqual(
            len(overlap), 0, f"Critical leakage! Speakers in both classes: {overlap}"
        )
        self.assertEqual(len(d_speakers), 39, "Expected 39 dementia speakers")
        self.assertEqual(len(nd_speakers), 41, "Expected 41 nodementia speakers")
        self.assertEqual(df["speaker_id"].nunique(), 80, "Expected 80 unique speakers")

    def test_04_saved_model_loads_and_predicts(self):
        """Verifies saved model artifact can be loaded and executes inference on feature schema."""
        self.assertTrue(self.model_path.is_file(), f"Missing model: {self.model_path}")
        model = joblib.load(self.model_path)
        self.assertTrue(hasattr(model, "predict"), "Model object has no predict method")

        # Load clean features to get valid input schema
        df = pd.read_csv(self.clean_csv_path)
        feature_cols = [
            c for c in df.columns if c not in DEFAULT_MODEL_CONFIG.metadata_columns
        ]
        self.assertEqual(len(feature_cols), 79, "Expected 79 numeric acoustic features")

        # Test single sample prediction
        sample = df[feature_cols].iloc[[0]].values
        pred = model.predict(sample)
        self.assertIn(int(pred[0]), [0, 1], "Prediction should be binary 0 or 1")

        if hasattr(model, "predict_proba"):
            probs = model.predict_proba(sample)[0]
            self.assertEqual(len(probs), 2, "Probabilities should have 2 classes")
            self.assertAlmostEqual(float(np.sum(probs)), 1.0, places=5)

    def test_05_metadata_json_matches_model_schema(self):
        """Verifies model_metadata.json exists and accurately records 79 feature names."""
        self.assertTrue(self.metadata_path.is_file(), f"Missing metadata: {self.metadata_path}")
        with open(self.metadata_path, "r", encoding="utf-8") as f:
            meta = json.load(f)

        self.assertEqual(meta["feature_count"], 79)
        self.assertEqual(len(meta["feature_schema"]), 79)
        self.assertIn("Random_Forest", meta["selected_model_name"])
        self.assertEqual(meta["split_information"]["speaker_overlap_count"], 0)


if __name__ == "__main__":
    unittest.main()

