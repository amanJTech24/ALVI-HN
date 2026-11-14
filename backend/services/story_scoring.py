"""
ALVI Story Recall Scoring Service
Evaluates story recall transcripts against authoritative story keys.
Computes:
1. Fact Completeness (Key Information Units)
2. Paraphrase & Negation Resolution
3. Chronological Event Sequence Accuracy (Inversion Scoring)
4. Semantic Similarity (Global TF-IDF Cosine Similarity)
5. Missing Detail and Intrusion / Confabulation Detection
6. Weighted Composite Performance Score (Explainable & Non-Diagnostic)
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from backend.services.semantic_matching import (
    MatchResult,
    SemanticMatcher,
    normalize_text,
)

STORY_BANK_PATH = Path(__file__).resolve().parent.parent / "data" / "story_bank.json"

CLINICAL_DISCLAIMER = (
    "This score is an experimental NLP task performance metric measuring verbal recall completeness, "
    "semantic similarity, and chronological sequencing against a standard narrative. "
    "It is strictly for research and experimental tracking, NOT a clinical diagnosis of Alzheimer's disease, "
    "dementia, or any neurological condition."
)


class StoryBank:
    """Loads and caches stories from backend/data/story_bank.json."""

    def __init__(self, file_path: Path = STORY_BANK_PATH) -> None:
        self.file_path = file_path
        self._cache: Dict[str, Any] = {}
        self.load()

    def load(self) -> None:
        if not self.file_path.exists():
            raise FileNotFoundError(f"Story bank file not found: {self.file_path}")
        with open(self.file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            self._cache = data.get("stories", {})

    def list_stories(self) -> List[Dict[str, Any]]:
        """Return catalog of available stories without answer keys."""
        catalog = []
        for sid, sdata in self._cache.items():
            catalog.append({
                "id": sid,
                "title": sdata.get("title", sid),
                "difficulty": sdata.get("difficulty", "standard"),
                "word_count": sdata.get("word_count", len(sdata.get("text", "").split())),
                "total_units": len(sdata.get("information_units", []))
            })
        return catalog

    def get_story(self, story_id: str) -> Optional[Dict[str, Any]]:
        return self._cache.get(story_id)


# Global singleton instance
_story_bank = StoryBank()


def get_story_bank() -> StoryBank:
    return _story_bank


class StoryScoringService:
    """
    NLP Scoring Engine for Narrative Retell Assessments.
    """

    def __init__(self, matcher: Optional[SemanticMatcher] = None) -> None:
        self.matcher = matcher or SemanticMatcher()
        self.bank = get_story_bank()

    def score_recall(
        self,
        story_id: str,
        transcript: str,
        input_mode: str = "speech",
        timing_seconds: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Execute full NLP scoring evaluation for a retell transcript.
        """
        story = self.bank.get_story(story_id)
        if not story:
            raise KeyError(f"Story with ID '{story_id}' not found in story bank.")

        raw_transcript = transcript.strip() if transcript else ""
        norm_transcript = normalize_text(raw_transcript)
        story_text = story.get("text", "")
        information_units = story.get("information_units", [])
        expected_seq = story.get("expected_sequence", [u["id"] for u in information_units])
        known_intrusions = story.get("known_intrusions", [])

        # ── 1. Evaluate Information Units (Completeness) ──────────────────────
        unit_evaluations: List[Dict[str, Any]] = []
        matched_units: List[MatchResult] = []
        recalled_labels: List[str] = []
        missed_labels: List[str] = []

        total_points = 0.0
        max_points = float(len(information_units))

        for unit in information_units:
            match_res = self.matcher.match_information_unit(raw_transcript, unit)
            
            # Points assignment
            points = 0.0
            if match_res.is_matched and not match_res.is_negated:
                if match_res.match_type in ("exact", "paraphrase"):
                    points = 1.0
                elif match_res.match_type == "partial":
                    points = 0.5
                recalled_labels.append(unit["label"])
                matched_units.append(match_res)
            else:
                missed_labels.append(unit["label"])

            total_points += points

            unit_evaluations.append({
                "id": unit["id"],
                "label": unit["label"],
                "category": unit.get("category", "general"),
                "is_matched": match_res.is_matched,
                "match_type": match_res.match_type,
                "points_awarded": points,
                "max_points": 1.0,
                "similarity": round(match_res.similarity, 3),
                "matched_text": match_res.matched_text,
                "char_position": match_res.char_position,
                "is_negated": match_res.is_negated,
                "explanation": match_res.explanation
            })

        completeness_pct = (total_points / max_points * 100.0) if max_points > 0 else 0.0
        completeness_pct = round(max(0.0, min(100.0, completeness_pct)), 1)

        # ── 2. Global Semantic Similarity ─────────────────────────────────────
        global_semantic_sim = self.matcher.calculate_string_similarity(raw_transcript, story_text)
        semantic_pct = round(global_semantic_sim * 100.0, 1)

        # ── 3. Chronological Sequence Accuracy ────────────────────────────────
        # Only evaluate order for matched units that have an identified character position
        ordered_matched = [
            m for m in matched_units
            if m.char_position is not None and m.unit_id in expected_seq
        ]

        inversions_count = 0
        total_pairs = 0
        observed_order_labels: List[str] = []

        if len(ordered_matched) <= 1:
            # If 0 or 1 item recalled, no sequence error can occur; match completeness or 100
            sequence_pct = 100.0 if len(ordered_matched) == 1 else completeness_pct
            for m in ordered_matched:
                observed_order_labels.append(m.label)
        else:
            # Sort by character position in transcript to see participant's recall order
            observed_sorted = sorted(ordered_matched, key=lambda m: m.char_position or 0)
            observed_order_labels = [m.label for m in observed_sorted]
            observed_ids = [m.unit_id for m in observed_sorted]

            # Calculate inversion count relative to expected chronology tiers
            sequence_tiers = story.get("sequence_tiers")
            if sequence_tiers:
                expected_index_map = sequence_tiers
            else:
                expected_index_map = {uid: idx for idx, uid in enumerate(expected_seq)}

            k = len(observed_ids)
            evaluable_pairs = 0

            for i in range(k):
                for j in range(i + 1, k):
                    id_i = observed_ids[i]
                    id_j = observed_ids[j]
                    tier_i = expected_index_map.get(id_i, 0)
                    tier_j = expected_index_map.get(id_j, 0)
                    if tier_i != tier_j:
                        evaluable_pairs += 1
                        if tier_i > tier_j:
                            inversions_count += 1

            inversion_ratio = (inversions_count / evaluable_pairs) if evaluable_pairs > 0 else 0.0
            sequence_pct = max(0.0, (1.0 - inversion_ratio) * 100.0)

        sequence_pct = round(sequence_pct, 1)

        # ── 4. Intrusion & Confabulation Detection ────────────────────────────
        detected_intrusions: List[Dict[str, str]] = []
        transcript_words = set(norm_transcript.split())

        for intrusion in known_intrusions:
            norm_intr = normalize_text(intrusion)
            # Check single word or multiword phrase
            if " " in norm_intr:
                if norm_intr in norm_transcript:
                    detected_intrusions.append({
                        "concept": intrusion,
                        "type": "unsupported_narrative_intrusion",
                        "note": f"Word or concept '{intrusion}' was mentioned but did not occur in the original story."
                    })
            else:
                if norm_intr in transcript_words:
                    detected_intrusions.append({
                        "concept": intrusion,
                        "type": "unsupported_narrative_intrusion",
                        "note": f"Word '{intrusion}' was mentioned but did not occur in the original story."
                    })

        intrusion_penalty = len(detected_intrusions) * 5.0

        # ── 5. Composite Performance Score ────────────────────────────────────
        # Weighted: 60% Completeness, 25% Semantic, 15% Sequence - Intrusions
        weighted_raw = (
            (0.60 * completeness_pct) +
            (0.25 * semantic_pct) +
            (0.15 * sequence_pct) -
            intrusion_penalty
        )
        composite_score = round(max(0.0, min(100.0, weighted_raw)), 1)

        # Performance Tier classification
        if composite_score >= 85.0:
            performance_band = "High Recall"
            band_description = "Excellent memory retention; accurately recalled nearly all core narrative units in proper temporal sequence."
        elif composite_score >= 65.0:
            performance_band = "Moderate Recall"
            band_description = "Good memory retention; recalled the central narrative theme with minor detail omissions or mild sequencing drift."
        elif composite_score >= 40.0:
            performance_band = "Mild Recall Difficulty"
            band_description = "Partial recall; several key elements or temporal milestones were omitted or fragmented."
        else:
            performance_band = "Low Recall / Incomplete"
            band_description = "Limited recall; minimal facts retained from the original story."

        # Word count stats
        transcript_words_list = raw_transcript.split()
        word_count = len(transcript_words_list)
        story_word_count = story.get("word_count", len(story_text.split()))

        return {
            "story_id": story_id,
            "story_title": story.get("title", story_id),
            "input_mode": input_mode,
            "transcript": raw_transcript,
            "word_count": word_count,
            "target_word_count": story_word_count,
            "timing_seconds": timing_seconds,
            "composite_score": composite_score,
            "performance_band": performance_band,
            "band_description": band_description,
            "metrics": {
                "completeness_score": completeness_pct,
                "semantic_similarity_score": semantic_pct,
                "sequence_accuracy_score": sequence_pct,
                "points_awarded": total_points,
                "max_possible_points": max_points,
                "recalled_units_count": len(recalled_labels),
                "total_units_count": len(information_units),
                "sequence_inversions": inversions_count,
                "intrusions_count": len(detected_intrusions),
                "intrusion_penalty": intrusion_penalty
            },
            "information_units_detail": unit_evaluations,
            "recalled_units": recalled_labels,
            "missed_units": missed_labels,
            "observed_sequence": observed_order_labels,
            "intrusions_detected": detected_intrusions,
            "disclaimer": CLINICAL_DISCLAIMER
        }
