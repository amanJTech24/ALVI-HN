"""
ALVI Semantic Matching & NLP Utility Module
Provides lightweight, explainable semantic similarity, paraphrase recognition,
entity matching, and negation/contradiction detection without requiring heavy external downloads.
"""

from dataclasses import dataclass
import re
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


NEGATION_TOKENS: Set[str] = {
    "no", "not", "n't", "never", "without", "none", "hardly",
    "scarcely", "barely", "didn't", "wasn't", "couldn't",
    "wouldn't", "hadn't", "doesn't", "isn't", "aren't",
    "neither", "nor", "cannot", "cant", "dont"
}

NUMBER_WORD_MAP: Dict[str, str] = {
    "one": "1", "two": "2", "three": "3", "four": "4",
    "five": "5", "six": "6", "seven": "7", "eight": "8",
    "nine": "9", "ten": "10"
}


@dataclass
class MatchResult:
    unit_id: str
    label: str
    is_matched: bool
    match_type: str  # "exact", "paraphrase", "partial", "negated", "unmatched"
    similarity: float
    matched_text: Optional[str]
    char_position: Optional[int]
    is_negated: bool
    explanation: str


def normalize_text(text: str) -> str:
    """Normalize text by lowercasing, expanding number words, and cleaning whitespace."""
    if not text:
        return ""
    cleaned = text.lower()
    # Normalize punctuation spacing
    cleaned = re.sub(r"[^\w\s\']", " ", cleaned)
    # Replace word numbers with digits
    tokens = cleaned.split()
    normalized_tokens = [NUMBER_WORD_MAP.get(t, t) for t in tokens]
    return " ".join(normalized_tokens)


def split_into_clauses(text: str) -> List[Tuple[str, int]]:
    """
    Split text into sentence/clause segments while tracking character offsets.
    Returns list of (clause_text, start_char_index).
    """
    if not text:
        return []
    # Split on periods, commas, semicolons, and conjunctions
    pattern = re.compile(r"([^\.\,\;\!\?\n]+)")
    clauses: List[Tuple[str, int]] = []
    for match in pattern.finditer(text):
        clause_str = match.group(1).strip()
        if clause_str:
            clauses.append((clause_str, match.start(1)))
    if not clauses:
        clauses.append((text.strip(), 0))
    return clauses


def is_phrase_negated(text: str, match_start: int, window_tokens: int = 4) -> bool:
    """
    Determine if a matched phrase is in the scope of a preceding negation modifier.
    Inspects up to `window_tokens` immediately preceding the match position.
    """
    if match_start <= 0:
        return False
    preceding_text = text[:match_start].lower()
    # Look at the last few tokens before the match
    tokens = re.findall(r"[\w\']+", preceding_text)
    window = tokens[-window_tokens:] if len(tokens) >= window_tokens else tokens
    return any(tok in NEGATION_TOKENS for tok in window)


class SemanticMatcher:
    """
    Hybrid Rule & Sublinear TF-IDF Semantic Matcher.
    Combines rule-based synonym mapping, negation scope resolution,
    and character/word n-gram cosine similarity.
    """

    def __init__(self) -> None:
        # Dual vectorizer: Character 3-5 ngrams for robust morphological matching
        # plus word 1-2 ngrams for phrase structure.
        self.vectorizer = TfidfVectorizer(
            analyzer="char_wb",
            ngram_range=(3, 5),
            sublinear_tf=True,
            norm="l2"
        )

    def calculate_string_similarity(self, s1: str, s2: str) -> float:
        """Calculate pairwise cosine similarity between two text snippets."""
        n1 = normalize_text(s1)
        n2 = normalize_text(s2)
        if not n1 or not n2:
            return 0.0
        if n1 == n2:
            return 1.0

        try:
            tfidf_mat = self.vectorizer.fit_transform([n1, n2])
            sim = float(cosine_similarity(tfidf_mat[0:1], tfidf_mat[1:2])[0][0])
            return max(0.0, min(1.0, sim))
        except Exception:
            return 0.0

    def match_information_unit(
        self,
        transcript: str,
        unit: Dict[str, Any]
    ) -> MatchResult:
        """
        Evaluate whether an information unit was recalled in the transcript.
        Checks:
        1. Negation: Disqualifies matches that are explicitly negated.
        2. Direct synonym/paraphrase match.
        3. Clause-level semantic cosine similarity.
        """
        norm_transcript = normalize_text(transcript)
        raw_transcript_lower = transcript.lower()

        unit_id = unit["id"]
        label = unit["label"]
        canonical = unit.get("canonical_text", label)
        accepted_synonyms = unit.get("accepted_synonyms", [])
        core_concepts = unit.get("core_concepts", [])

        if not norm_transcript.strip():
            return MatchResult(
                unit_id=unit_id,
                label=label,
                is_matched=False,
                match_type="unmatched",
                similarity=0.0,
                matched_text=None,
                char_position=None,
                is_negated=False,
                explanation="Response was empty."
            )

        # ── 1. Check for Accepted Paraphrases & Synonyms ────────────────────────
        best_match_phrase = None
        best_match_pos = None
        is_negated_match = False

        for syn in accepted_synonyms:
            norm_syn = normalize_text(syn)
            # Find in transcript using word boundary to avoid false substring matches
            pattern = re.compile(r"\b" + re.escape(norm_syn) + r"\b")
            m = pattern.search(norm_transcript)
            if m:
                pos = m.start()
                # Check negation scope
                if is_phrase_negated(norm_transcript, pos):
                    is_negated_match = True
                    continue  # Keep looking for non-negated mention

                best_match_phrase = syn
                best_match_pos = pos
                break

        if is_negated_match and best_match_phrase is None:
            return MatchResult(
                unit_id=unit_id,
                label=label,
                is_matched=False,
                match_type="negated",
                similarity=0.1,
                matched_text=None,
                char_position=None,
                is_negated=True,
                explanation=f"Concept '{label}' was explicitly negated or denied in response."
            )

        if best_match_phrase:
            # High-confidence exact or paraphrase match
            sim = self.calculate_string_similarity(best_match_phrase, canonical)
            sim_score = max(0.85, sim)
            return MatchResult(
                unit_id=unit_id,
                label=label,
                is_matched=True,
                match_type="exact" if sim_score >= 0.90 else "paraphrase",
                similarity=sim_score,
                matched_text=best_match_phrase,
                char_position=best_match_pos,
                is_negated=False,
                explanation=f"Matched accepted paraphrase: '{best_match_phrase}'."
            )

        # ── 2. Check Core Concept Overlap ──────────────────────────────────────
        # If all or majority of core concept keywords exist in text
        matched_concepts = []
        concept_positions = []
        for concept in core_concepts:
            norm_c = normalize_text(concept)
            pattern = re.compile(r"\b" + re.escape(norm_c) + r"\b")
            m = pattern.search(norm_transcript)
            if m:
                c_pos = m.start()
                if not is_phrase_negated(norm_transcript, c_pos):
                    matched_concepts.append(concept)
                    concept_positions.append(c_pos)

        if core_concepts and len(matched_concepts) == len(core_concepts):
            first_pos = min(concept_positions) if concept_positions else 0
            sim_score = self.calculate_string_similarity(transcript, canonical)
            return MatchResult(
                unit_id=unit_id,
                label=label,
                is_matched=True,
                match_type="paraphrase",
                similarity=max(0.75, sim_score),
                matched_text=", ".join(matched_concepts),
                char_position=first_pos,
                is_negated=False,
                explanation=f"All core concepts identified: {', '.join(matched_concepts)}."
            )

        # ── 3. Clause-Level Semantic Cosine Similarity ─────────────────────────
        clauses = split_into_clauses(transcript)
        best_clause_sim = 0.0
        best_clause_text = None
        best_clause_pos = None

        for clause, pos in clauses:
            clause_sim = self.calculate_string_similarity(clause, canonical)
            if clause_sim > best_clause_sim:
                best_clause_sim = clause_sim
                best_clause_text = clause
                best_clause_pos = pos

        # High threshold for purely embedding/ngram similarity
        if best_clause_sim >= 0.65:
            # Verify clause is not negated
            if is_phrase_negated(norm_transcript, best_clause_pos or 0):
                return MatchResult(
                    unit_id=unit_id,
                    label=label,
                    is_matched=False,
                    match_type="negated",
                    similarity=best_clause_sim,
                    matched_text=best_clause_text,
                    char_position=best_clause_pos,
                    is_negated=True,
                    explanation=f"Similar clause was negated in context."
                )

            return MatchResult(
                unit_id=unit_id,
                label=label,
                is_matched=True,
                match_type="paraphrase",
                similarity=best_clause_sim,
                matched_text=best_clause_text,
                char_position=best_clause_pos,
                is_negated=False,
                explanation=f"Semantic clause match with similarity {best_clause_sim:.2f}."
            )

        if best_clause_sim >= 0.45 or (core_concepts and len(matched_concepts) >= 1):
            return MatchResult(
                unit_id=unit_id,
                label=label,
                is_matched=True,
                match_type="partial",
                similarity=best_clause_sim if best_clause_sim > 0.4 else 0.50,
                matched_text=best_clause_text or (matched_concepts[0] if matched_concepts else None),
                char_position=best_clause_pos if best_clause_pos is not None else (concept_positions[0] if concept_positions else None),
                is_negated=False,
                explanation=f"Partial recall match (similarity: {max(best_clause_sim, 0.50):.2f})."
            )

        # No match found
        return MatchResult(
            unit_id=unit_id,
            label=label,
            is_matched=False,
            match_type="unmatched",
            similarity=best_clause_sim,
            matched_text=None,
            char_position=None,
            is_negated=False,
            explanation=f"Information unit was omitted or insufficient similarity ({best_clause_sim:.2f})."
        )

