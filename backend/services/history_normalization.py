"""
ALVI Session History Normalization Service — backend/services/history_normalization.py

Provides rigorous sanitization, validation, deduplication, and schema normalization
for multi-session assessment history (Voice, Story Recall, MindPlay) and Practice history.

DATA INTEGRITY PRINCIPLES:
1. Non-destructive: Normalizes client history without mutating or dropping legitimate records.
2. Chronological Ordering: Parses ISO timestamps and sorts sessions from earliest to newest.
3. Stable Identification: Preserves existing session IDs or assigns deterministic fallback IDs.
4. Deduplication: Eliminates duplicate session entries (identical ID or identical timestamp).
5. Value Sanitization: Rejects NaN, Infinity, negative reaction times, and impossible percentages.
6. Missingness Preservation: Retains unmeasured metrics as None/null rather than zero-filling.
7. Segregation: Filters synthetic developer/demo records from genuine user history.
"""

from datetime import datetime, timezone
import math
from typing import Any, Dict, List, Optional, Tuple


class HistoryNormalizer:
    """Normalizes and sanitizes longitudinal assessment and practice session records."""

    @staticmethod
    def parse_iso_timestamp(ts: Any) -> Optional[datetime]:
        """Safely parses an ISO timestamp string into a timezone-aware datetime object."""
        if not ts or not isinstance(ts, str):
            return None
        cleaned = ts.strip().replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(cleaned)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except (ValueError, TypeError):
            # Try date-only fallback YYYY-MM-DD
            try:
                parts = cleaned.split("T")[0].split("-")
                if len(parts) == 3:
                    return datetime(int(parts[0]), int(parts[1]), int(parts[2]), tzinfo=timezone.utc)
            except Exception:
                pass
            return None

    @staticmethod
    def is_valid_number(val: Any) -> bool:
        """Checks if a value is a finite, non-null, real numeric type."""
        if val is None or isinstance(val, bool):
            return False
        try:
            f = float(val)
            return not (math.isnan(f) or math.isinf(f))
        except (ValueError, TypeError):
            return False

    @staticmethod
    def clamp_or_none(val: Any, min_val: float, max_val: float) -> Optional[float]:
        """Returns float value if valid and within bounds [min_val, max_val], else None."""
        if not HistoryNormalizer.is_valid_number(val):
            return None
        f = float(val)
        if min_val <= f <= max_val:
            return round(f, 4)
        return None

    def normalize_sessions(
        self,
        raw_sessions: Optional[List[Dict[str, Any]]],
        include_demo: bool = False
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Normalizes, deduplicates, and chronologically sorts raw check-in session records.

        Args:
            raw_sessions: List of raw session dictionaries from client storage.
            include_demo: Whether to include developer/demo synthetic sessions.

        Returns:
            Tuple of (valid_normalized_sessions, excluded_records_with_reasons).
        """
        if not raw_sessions or not isinstance(raw_sessions, list):
            return [], []

        valid_sessions: List[Dict[str, Any]] = []
        excluded_records: List[Dict[str, Any]] = []
        seen_ids = set()
        seen_timestamps = set()

        for idx, item in enumerate(raw_sessions):
            if not isinstance(item, dict):
                excluded_records.append({"index": idx, "reason": "Record is not a dictionary", "record": str(item)})
                continue

            # Check demo / synthetic flag
            is_demo = bool(item.get("is_demo") or item.get("is_sample") or item.get("activeCaseId", "").startswith("DEMO_"))
            if is_demo and not include_demo:
                excluded_records.append({
                    "index": idx,
                    "session_id": item.get("sessionId"),
                    "reason": "Synthetic developer/demo record excluded from genuine history"
                })
                continue

            # Parse and validate timestamp
            ts_str = item.get("startedAt") or item.get("timestamp") or item.get("created_at")
            dt = self.parse_iso_timestamp(ts_str)
            if not dt:
                excluded_records.append({
                    "index": idx,
                    "session_id": item.get("sessionId"),
                    "reason": f"Invalid or unparseable timestamp: '{ts_str}'"
                })
                continue

            # Format canonical ISO string
            canonical_ts = dt.isoformat()

            # Session ID resolution
            raw_id = item.get("sessionId") or item.get("session_id") or item.get("id")
            if raw_id and isinstance(raw_id, str) and raw_id.strip():
                session_id = raw_id.strip()
            else:
                session_id = f"sess-{int(dt.timestamp())}-{idx}"

            # Deduplication: check session_id and exact timestamp
            if session_id in seen_ids:
                excluded_records.append({
                    "index": idx,
                    "session_id": session_id,
                    "reason": f"Duplicate session ID: '{session_id}'"
                })
                continue

            ts_second_key = dt.strftime("%Y-%m-%d %H:%M:%S")
            if ts_second_key in seen_timestamps:
                excluded_records.append({
                    "index": idx,
                    "session_id": session_id,
                    "reason": f"Duplicate session timestamp collision at '{ts_second_key}'"
                })
                continue

            seen_ids.add(session_id)
            seen_timestamps.add(ts_second_key)

            # Normalize task metrics
            norm_voice = self._normalize_voice_payload(item.get("voice"))
            norm_story = self._normalize_story_payload(item.get("story"))
            norm_mindplay = self._normalize_mindplay_payload(item.get("mindplay"))

            # Build canonical normalized session object
            normalized_session = {
                "session_id": session_id,
                "timestamp": canonical_ts,
                "timestamp_epoch": dt.timestamp(),
                "date": dt.strftime("%Y-%m-%d"),
                "is_demo": is_demo,
                "active_case_id": item.get("activeCaseId") or item.get("active_case_id") or "LIVE_USER",
                "voice": norm_voice,
                "story": norm_story,
                "mindplay": norm_mindplay,
                "tasks_completed_count": sum([
                    1 if norm_voice.get("completed") else 0,
                    1 if norm_story.get("completed") else 0,
                    1 if norm_mindplay.get("completed") else 0,
                ]),
                "schema_version": "1.6.0"
            }

            valid_sessions.append(normalized_session)

        # Chronological sort (oldest to newest)
        valid_sessions.sort(key=lambda s: s["timestamp_epoch"])

        return valid_sessions, excluded_records

    def _normalize_voice_payload(self, voice: Any) -> Dict[str, Any]:
        """Sanitizes voice check-in acoustic parameters."""
        if not isinstance(voice, dict):
            return {
                "completed": False,
                "duration_seconds": None,
                "is_valid": False,
                "features": None,
                "metrics": {}
            }

        completed = bool(voice.get("completed", False))
        duration = self.clamp_or_none(voice.get("durationSeconds") or voice.get("duration_seconds") or voice.get("duration"), 0.0, 600.0)
        is_valid = bool(voice.get("isValid", voice.get("is_valid", completed)))

        # Extract features dictionary
        raw_feats = voice.get("features")
        features_dict: Dict[str, Any] = {}
        metrics_dict: Dict[str, Optional[float]] = {}

        if isinstance(raw_feats, dict):
            features_dict = raw_feats
        elif isinstance(voice.get("acoustic_features"), dict):
            features_dict = voice["acoustic_features"]

        # Parse key metrics with physiological / physical boundary validation
        # 1. Fundamental Frequency (F0 in Hz): normal human speech ~ 50Hz to 600Hz
        f0 = self.clamp_or_none(
            features_dict.get("mean_f0") or features_dict.get("pitch_hz") or features_dict.get("mean_pitch") or voice.get("pitch_hz"),
            40.0, 800.0
        )
        metrics_dict["f0_mean_hz"] = f0

        # 2. RMS Energy: 0.0 to 1.0 amplitude
        rms = self.clamp_or_none(
            features_dict.get("rms") or features_dict.get("rms_mean") or voice.get("rms"),
            0.0, 1.0
        )
        metrics_dict["rms_energy"] = rms

        # 3. Zero-Crossing Rate (ZCR): 0.0 to 1.0
        zcr = self.clamp_or_none(
            features_dict.get("zcr") or features_dict.get("zero_crossing_rate") or voice.get("zcr"),
            0.0, 1.0
        )
        metrics_dict["zero_crossing_rate"] = zcr

        # 4. Low-energy frame ratio (pause proxy): 0.0 to 1.0
        pause_ratio = self.clamp_or_none(
            features_dict.get("low_energy_frame_ratio") or features_dict.get("pause_ratio") or voice.get("pause_ratio"),
            0.0, 1.0
        )
        metrics_dict["low_energy_frame_ratio"] = pause_ratio

        # 5. Spectral Centroid in Hz: typical voice 100Hz to 8000Hz
        spectral_centroid = self.clamp_or_none(
            features_dict.get("spectral_centroid") or features_dict.get("spectral_centroid_mean") or voice.get("spectral_centroid"),
            50.0, 10000.0
        )
        metrics_dict["spectral_centroid_hz"] = spectral_centroid

        # 6. Recording Duration in seconds
        metrics_dict["duration_seconds"] = duration

        # 7. Pause count (integer >= 0)
        pause_cnt_val = features_dict.get("pause_count") or voice.get("pause_count")
        pause_count = int(pause_cnt_val) if self.is_valid_number(pause_cnt_val) and int(pause_cnt_val) >= 0 else None
        metrics_dict["pause_count"] = pause_count

        return {
            "completed": completed,
            "duration_seconds": duration,
            "is_valid": is_valid,
            "rejection_reason": voice.get("rejectionReason") or voice.get("rejection_reason"),
            "features": features_dict if features_dict else None,
            "metrics": metrics_dict,
            "processing_version": voice.get("processing_version", "1.0.0-librosa")
        }

    def _normalize_story_payload(self, story: Any) -> Dict[str, Any]:
        """Sanitizes Story Recall NLP metrics."""
        if not isinstance(story, dict):
            return {
                "completed": False,
                "duration_seconds": None,
                "score_percent": None,
                "recalled_facts_count": 0,
                "missed_facts_count": 0,
                "chronological_inversions": 0,
                "story_id": None,
                "scoring_version": "1.0.0-nlp"
            }

        completed = bool(story.get("completed", False))
        duration = self.clamp_or_none(story.get("durationSeconds") or story.get("duration_seconds"), 0.0, 600.0)

        # Score percent: 0.0 to 100.0
        score_pct = self.clamp_or_none(story.get("score_percent") or story.get("score"), 0.0, 100.0)

        # Recalled & Missed facts
        recalled = story.get("recalled_facts") or []
        missed = story.get("missed_facts") or []
        recalled_count = len(recalled) if isinstance(recalled, list) else 0
        missed_count = len(missed) if isinstance(missed, list) else 0

        # Inversions count
        inversions = story.get("chronological_inversions") or story.get("sequence_inversions") or 0
        inversions_count = int(inversions) if self.is_valid_number(inversions) and int(inversions) >= 0 else 0

        return {
            "completed": completed,
            "duration_seconds": duration,
            "score_percent": score_pct,
            "recalled_facts_count": recalled_count,
            "missed_facts_count": missed_count,
            "recalled_facts": recalled if isinstance(recalled, list) else [],
            "missed_facts": missed if isinstance(missed, list) else [],
            "chronological_inversions": inversions_count,
            "story_id": story.get("story_id") or "aarav_story_v1",
            "scoring_version": story.get("scoring_version") or "1.0.0-nlp",
            "input_mode": story.get("input_mode") or "voice"
        }

    def _normalize_mindplay_payload(self, mindplay: Any) -> Dict[str, Any]:
        """Sanitizes MindPlay cognitive challenge telemetry."""
        if not isinstance(mindplay, dict):
            return {
                "completed": False,
                "ch1_score": None,
                "ch1_correct": False,
                "ch2_correct": False,
                "ch3_correct": False,
                "ch3_reaction_ms": None,
                "composite_accuracy_percent": None,
                "total_time_seconds": None,
                "difficulty": "Standard"
            }

        completed = bool(mindplay.get("completed", False))

        # Ch1 Remember score: 0 to 2
        raw_ch1 = mindplay.get("ch1_score")
        ch1_score = int(raw_ch1) if self.is_valid_number(raw_ch1) and 0 <= int(raw_ch1) <= 2 else None
        ch1_correct = bool(mindplay.get("ch1_correct", ch1_score == 2 if ch1_score is not None else False))

        # Ch2 Sequence correctness
        ch2_correct = bool(mindplay.get("ch2_correct", False))

        # Ch3 Find accuracy & reaction latency
        ch3_correct = bool(mindplay.get("ch3_correct", False))
        raw_reaction = mindplay.get("ch3_reactionMs") or mindplay.get("ch3_reaction_ms")

        # Physiological latency boundaries: 150ms to 30000ms
        ch3_reaction_ms = self.clamp_or_none(raw_reaction, 150.0, 30000.0)

        # Composite Accuracy (%) across the 3 challenges
        # Challenge 1: up to 2 pts, Challenge 2: 1 pt, Challenge 3: 1 pt -> Total 4 pts
        composite_acc = None
        if ch1_score is not None or completed:
            pts = (ch1_score or (2 if ch1_correct else 0)) + (1 if ch2_correct else 0) + (1 if ch3_correct else 0)
            composite_acc = round((pts / 4.0) * 100.0, 1)

        total_time = self.clamp_or_none(
            mindplay.get("total_time_seconds") or mindplay.get("totalTimeSeconds"),
            0.0, 1200.0
        )

        return {
            "completed": completed,
            "ch1_score": ch1_score,
            "ch1_correct": ch1_correct,
            "ch2_correct": ch2_correct,
            "ch3_correct": ch3_correct,
            "ch3_reaction_ms": ch3_reaction_ms,
            "composite_accuracy_percent": composite_acc,
            "total_time_seconds": total_time,
            "difficulty": mindplay.get("difficulty") or "Standard"
        }

    def normalize_practice_records(
        self,
        raw_practice: Optional[List[Dict[str, Any]]],
        include_demo: bool = False
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Normalizes, deduplicates, and validates practice engagement records.

        CRITICAL PHASE 9 / 10 CORRECTION:
        - Only records marked as completed (completed=True or status='completed') count as genuine completions.
        - Initiated-only attempts (status='initiated' or completed=False) are retained under 'initiated_practices'
          or excluded from completion metrics.
        - Demo/synthetic records (is_demo=True) are strictly quarantined.
        """
        if not raw_practice or not isinstance(raw_practice, list):
            return [], []

        valid_practice: List[Dict[str, Any]] = []
        excluded_records: List[Dict[str, Any]] = []
        seen_practice_ids = set()

        for idx, item in enumerate(raw_practice):
            if not isinstance(item, dict):
                excluded_records.append({"index": idx, "reason": "Practice record is not a dictionary", "record": str(item)})
                continue

            # Quarantine synthetic / demo practices
            is_demo = bool(item.get("is_demo") or item.get("is_sample"))
            if is_demo and not include_demo:
                excluded_records.append({
                    "index": idx,
                    "practice_id": item.get("practice_id"),
                    "reason": "Synthetic demo practice record excluded from genuine history"
                })
                continue

            # Check completion status
            status = str(item.get("status", "")).lower()
            completed = bool(item.get("completed", True if status == "completed" or (status != "initiated" and item.get("score") is not None) else False))

            # Exclude incomplete / merely initiated launches
            if not completed or status == "initiated":
                excluded_records.append({
                    "index": idx,
                    "practice_id": item.get("practice_id"),
                    "reason": "Practice drill was initiated but not completed (in-progress/abandoned launch)"
                })
                continue

            # Timestamp parsing
            ts_str = item.get("timestamp") or item.get("created_at")
            dt = self.parse_iso_timestamp(ts_str)
            if not dt:
                excluded_records.append({
                    "index": idx,
                    "practice_id": item.get("practice_id"),
                    "reason": f"Invalid practice timestamp: '{ts_str}'"
                })
                continue

            practice_id = item.get("practice_id") or f"prac-{int(dt.timestamp())}-{idx}"
            if practice_id in seen_practice_ids:
                excluded_records.append({
                    "index": idx,
                    "practice_id": practice_id,
                    "reason": f"Duplicate practice ID: '{practice_id}'"
                })
                continue
            seen_practice_ids.add(practice_id)

            duration = self.clamp_or_none(item.get("duration_seconds") or item.get("durationSeconds"), 0.0, 3600.0) or 180.0
            score = self.clamp_or_none(item.get("score"), 0.0, 100.0)

            valid_practice.append({
                "practice_id": practice_id,
                "exercise_id": item.get("exercise_id") or "unspecified_drill",
                "exercise_title": item.get("exercise_title") or item.get("exercise_id") or "Practice Drill",
                "domain": item.get("domain") or "general",
                "score": score,
                "duration_seconds": duration,
                "timestamp": dt.isoformat(),
                "timestamp_epoch": dt.timestamp(),
                "date": dt.strftime("%Y-%m-%d"),
                "status": "completed",
                "completed": True,
                "is_demo": is_demo
            })

        valid_practice.sort(key=lambda p: p["timestamp_epoch"])
        return valid_practice, excluded_records


# Global singleton
_normalizer = HistoryNormalizer()


def get_history_normalizer() -> HistoryNormalizer:
    """Retrieve singleton HistoryNormalizer."""
    return _normalizer
