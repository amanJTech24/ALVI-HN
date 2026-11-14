"""
ALVI Longitudinal Trend & Descriptive Statistics Service — backend/services/trend_statistics.py

Computes transparent descriptive statistics, pairwise deltas, and multi-session trend trajectories
for validated assessment measurements without black-box clinical modeling or unsupported inferences.

SCIENTIFIC & STATISTICAL GOVERNANCE:
1. Honest History Thresholds:
   - n = 0: No history available (empty state).
   - n = 1: Single baseline observation (no comparison or trend possible).
   - n = 2: Pairwise comparison only (absolute delta & percent change; no trend line).
   - n >= 3: Descriptive trajectory available (linear slope, dispersion, range).
2. Non-Diagnostic Policy: Changes over time are reported descriptively. No "Alzheimer's progression score",
   disease stage, or clinical deterioration probabilities are computed.
3. Unit Preservation: Calculations preserve physical units (Hz, ms, %, sec) and never combine disparate scales.
"""

import math
from typing import Any, Dict, List, Optional, Tuple


class TrendStatistics:
    """Calculates factual descriptive statistics and linear trajectory for a time series."""

    @staticmethod
    def compute_metric_series(
        values_with_meta: List[Dict[str, Any]],
        metric_name: str,
        unit: str,
        min_change_threshold_pct: float = 2.5
    ) -> Dict[str, Any]:
        """
        Computes descriptive statistics and trajectory for a single metric time series.

        Args:
            values_with_meta: List of dicts each containing:
                              {"timestamp": str, "timestamp_epoch": float, "date": str, "value": float, "session_id": str}
            metric_name: Name of metric (e.g. "f0_mean_hz").
            unit: Unit label (e.g. "Hz", "%", "ms").
            min_change_threshold_pct: Percentage change threshold to distinguish stable from increasing/decreasing.

        Returns:
            Dict of descriptive statistics, trajectory mode, and data points.
        """
        # Filter valid numeric points
        valid_points = [
            pt for pt in values_with_meta
            if pt.get("value") is not None and not math.isnan(float(pt["value"])) and not math.isinf(float(pt["value"]))
        ]

        n = len(valid_points)

        # Baseline empty state
        if n == 0:
            return {
                "metric_name": metric_name,
                "unit": unit,
                "data_points_count": 0,
                "comparison_mode": "no_data",
                "message": f"No valid recorded observations for {metric_name}.",
                "baseline_value": None,
                "latest_value": None,
                "absolute_change": None,
                "percent_change": None,
                "mean": None,
                "median": None,
                "min": None,
                "max": None,
                "std_dev": None,
                "trend_direction": "insufficient_data",
                "trend_slope_per_session": None,
                "outliers": [],
                "series": []
            }

        values = [float(pt["value"]) for pt in valid_points]
        first_val = round(values[0], 3)
        latest_val = round(values[-1], 3)
        abs_change = round(latest_val - first_val, 3)

        # Percent change
        pct_change = None
        if first_val != 0.0:
            pct_change = round(((latest_val - first_val) / abs(first_val)) * 100.0, 2)

        # Summary statistics
        mean_val = round(sum(values) / n, 3)
        sorted_vals = sorted(values)
        if n % 2 == 1:
            median_val = round(sorted_vals[n // 2], 3)
        else:
            median_val = round((sorted_vals[(n // 2) - 1] + sorted_vals[n // 2]) / 2.0, 3)

        min_val = round(min(values), 3)
        max_val = round(max(values), 3)

        # Sample standard deviation (ddof=1 when n >= 2)
        std_dev = None
        if n >= 2:
            variance = sum((x - mean_val) ** 2 for x in values) / (n - 1)
            std_dev = round(math.sqrt(variance), 3)

        # Trajectory Mode & Direction
        trend_direction = "stable"
        slope = None
        comparison_mode = "baseline_only"
        scientific_note = ""

        if n == 1:
            comparison_mode = "baseline_only"
            trend_direction = "baseline_established"
            scientific_note = "Single baseline observation. At least 2 sessions are required for comparison."

        elif n == 2:
            comparison_mode = "pairwise_only"
            if pct_change is not None:
                if pct_change > min_change_threshold_pct:
                    trend_direction = "higher"
                elif pct_change < -min_change_threshold_pct:
                    trend_direction = "lower"
                else:
                    trend_direction = "stable"
            scientific_note = (
                "Pairwise comparison between two sessions. "
                "Two points do NOT establish a statistical trend or indicate disease progression."
            )

        else:
            # n >= 3: Longitudinal trajectory
            comparison_mode = "longitudinal_trend"
            # Ordinary least squares linear regression over session indices (0, 1, 2, ..., n-1)
            x_vals = list(range(n))
            x_mean = (n - 1) / 2.0
            numerator = sum((x_vals[i] - x_mean) * (values[i] - mean_val) for i in range(n))
            denominator = sum((x_vals[i] - x_mean) ** 2 for i in range(n))

            if denominator > 0:
                slope = round(numerator / denominator, 4)

            # Classify direction
            # If slope is relative change > min_change_threshold_pct of mean per session
            normalized_slope_pct = (slope / mean_val * 100.0) if mean_val != 0.0 and slope is not None else 0.0
            if normalized_slope_pct > 1.5:
                trend_direction = "increasing"
            elif normalized_slope_pct < -1.5:
                trend_direction = "decreasing"
            else:
                trend_direction = "stable"

            scientific_note = (
                f"Descriptive trajectory across {n} observations. "
                "Repeated task performance is subject to practice effects, ambient environment, and recording variance. "
                "Trajectories are descriptive and do NOT represent clinical cognitive decline or recovery."
            )

        # Detect statistical outliers (> 1.7 std devs if n <= 5, > 2.0 if n > 5)
        outlier_indices = []
        if n >= 4 and std_dev and std_dev > 0:
            threshold = 1.7 if n <= 5 else 2.0
            for idx, val in enumerate(values):
                z_score = abs(val - mean_val) / std_dev
                if z_score >= threshold:
                    outlier_indices.append({
                        "index": idx,
                        "session_id": valid_points[idx].get("session_id"),
                        "date": valid_points[idx].get("date"),
                        "value": val,
                        "z_score": round(z_score, 2),
                        "reason": f"Value deviates > {threshold} standard deviations ({round(z_score, 1)}σ) from personal mean."
                    })

        return {
            "metric_name": metric_name,
            "unit": unit,
            "data_points_count": n,
            "comparison_mode": comparison_mode,
            "baseline_value": first_val,
            "latest_value": latest_val,
            "absolute_change": abs_change,
            "percent_change": pct_change,
            "mean": mean_val,
            "median": median_val,
            "min": min_val,
            "max": max_val,
            "std_dev": std_dev,
            "trend_direction": trend_direction,
            "trend_slope_per_session": slope,
            "scientific_note": scientific_note,
            "outliers": outlier_indices,
            "series": [
                {
                    "session_id": pt["session_id"],
                    "timestamp": pt["timestamp"],
                    "date": pt["date"],
                    "value": round(float(pt["value"]), 3)
                }
                for pt in valid_points
            ]
        }


# Global singleton
_trend_stats = TrendStatistics()


def get_trend_statistics() -> TrendStatistics:
    """Retrieve singleton TrendStatistics."""
    return _trend_stats
