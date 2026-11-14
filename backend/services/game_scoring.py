"""
ALVI MindPlay Cognitive Game Scoring Service
Provides deterministic, explainable task performance scoring for:
1. Challenge 1: Remember (Associative Visual-Verbal Memory Binding)
2. Challenge 2: Sequence (Chronological Event Reordering / Working Memory)
3. Challenge 3: Find (Visual Target Discrimination & Search Latency)
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

CONFIG_PATH = Path(__file__).resolve().parent.parent / "data" / "game_config.json"


class GameConfigLoader:
    """Loads and caches MindPlay game rules from backend/data/game_config.json."""

    def __init__(self, path: Path = CONFIG_PATH) -> None:
        self.path = path
        self._config: Dict[str, Any] = {}
        self.load()

    def load(self) -> None:
        if not self.path.exists():
            raise FileNotFoundError(f"MindPlay configuration file missing: {self.path}")
        with open(self.path, "r", encoding="utf-8") as f:
            self._config = json.load(f)

    @property
    def config(self) -> Dict[str, Any]:
        return self._config

    def get_challenge(self, challenge_id: str) -> Optional[Dict[str, Any]]:
        return self._config.get("challenges", {}).get(challenge_id)


_config_loader = GameConfigLoader()


def get_game_config() -> Dict[str, Any]:
    return _config_loader.config


class MindPlayScoringService:
    """
    Evaluates empirical participant telemetry from MindPlay challenges.
    """

    def __init__(self, config_loader: Optional[GameConfigLoader] = None) -> None:
        self.loader = config_loader or _config_loader

    # ── Challenge 1: Remember ──────────────────────────────────────────────────
    def score_challenge_1(
        self,
        selected_items: List[str],
        interaction_time_ms: Optional[float] = None,
        toggle_count: Optional[int] = None
    ) -> Dict[str, Any]:
        cfg = self.loader.get_challenge("ch1_remember") or {}
        targets: Set[str] = set(cfg.get("target_items", ["umbrella", "apples"]))
        distractors: Set[str] = set(cfg.get("distractor_items", ["bicycle", "books"]))

        clean_selected = set(str(item).strip().lower() for item in selected_items)
        matched_targets = clean_selected & targets
        selected_distractors = clean_selected & distractors

        # 2 points max: +1.0 per correct target, -0.5 per distractor false alarm
        raw_points = len(matched_targets) * 1.0 - len(selected_distractors) * 0.5
        raw_points = max(0.0, min(2.0, raw_points))
        accuracy_pct = round((raw_points / 2.0) * 100.0, 1)

        is_correct = (len(matched_targets) == 2 and len(selected_distractors) == 0)
        ch1_score = len(matched_targets)

        # Performance qualitative description
        if is_correct:
            description = "Intact dual memory recognition (both target items correctly recalled)."
        elif len(matched_targets) == 1 and len(selected_distractors) == 0:
            description = "Partial memory recall (1 target recalled, 0 distractors selected)."
        elif len(selected_distractors) > 0:
            description = f"Associative interference ({len(selected_distractors)} distractor items selected)."
        else:
            description = "Target memory items omitted."

        return {
            "challenge_id": "ch1_remember",
            "name": cfg.get("name", "Challenge 1: Remember"),
            "cognitive_domain": cfg.get("cognitive_domain", "Episodic Visual-Verbal Memory"),
            "is_correct": is_correct,
            "ch1_score": ch1_score,
            "raw_points": raw_points,
            "max_points": 2.0,
            "accuracy_pct": accuracy_pct,
            "score": accuracy_pct,
            "selected_items": sorted(list(clean_selected)),
            "matched_targets": sorted(list(matched_targets)),
            "distractor_errors": sorted(list(selected_distractors)),
            "toggle_count": toggle_count,
            "timing_ms": interaction_time_ms,
            "description": description
        }

    # ── Challenge 2: Sequence ──────────────────────────────────────────────────
    def score_challenge_2(
        self,
        final_sequence: List[Any],
        move_count: Optional[int] = None,
        interaction_time_ms: Optional[float] = None
    ) -> Dict[str, Any]:
        cfg = self.loader.get_challenge("ch2_sequence") or {}
        target_order = cfg.get("target_order", [1, 2, 3, 4, 5])
        total_events = len(target_order)
        total_pairs = total_events * (total_events - 1) // 2  # 10 pairs for 5 events

        # Extract sequence of integer IDs
        observed_ids: List[int] = []
        for x in final_sequence:
            if isinstance(x, dict) and "id" in x:
                observed_ids.append(int(x["id"]))
            elif isinstance(x, dict) and "correctOrder" in x:
                observed_ids.append(int(x["correctOrder"]))
            else:
                try:
                    observed_ids.append(int(x))
                except (ValueError, TypeError):
                    pass

        # Handle incomplete or invalid input
        if len(observed_ids) != total_events or set(observed_ids) != set(target_order):
            return {
                "challenge_id": "ch2_sequence",
                "name": cfg.get("name", "Challenge 2: Sequence"),
                "cognitive_domain": cfg.get("cognitive_domain", "Working Memory & Executive Sequencing"),
                "is_correct": False,
                "inversions_count": total_pairs,
                "accuracy_pct": 0.0,
                "score": 0.0,
                "final_sequence": observed_ids,
                "move_count": move_count,
                "timing_ms": interaction_time_ms,
                "description": "Sequence was incomplete or invalid."
            }

        # Calculate pairwise inversions (Kendall tau distance)
        inversions = 0
        for i in range(total_events):
            for j in range(i + 1, total_events):
                if observed_ids[i] > observed_ids[j]:
                    inversions += 1

        inversion_ratio = inversions / total_pairs
        base_accuracy = max(0.0, (1.0 - inversion_ratio) * 100.0)
        is_correct = (inversions == 0)

        # Efficiency feedback
        if is_correct:
            description = "Intact chronological sequence (0 inversions, accurate temporal order)."
        elif inversions <= 2:
            description = f"Minor temporal transposition ({inversions} inversion(s) detected)."
        else:
            description = f"Fragmented temporal sequencing ({inversions} inversions detected)."

        return {
            "challenge_id": "ch2_sequence",
            "name": cfg.get("name", "Challenge 2: Sequence"),
            "cognitive_domain": cfg.get("cognitive_domain", "Working Memory & Executive Sequencing"),
            "is_correct": is_correct,
            "inversions_count": inversions,
            "total_pairs": total_pairs,
            "accuracy_pct": round(base_accuracy, 1),
            "score": round(base_accuracy, 1),
            "final_sequence": observed_ids,
            "move_count": move_count,
            "timing_ms": interaction_time_ms,
            "description": description
        }

    # ── Challenge 3: Find ──────────────────────────────────────────────────────
    def score_challenge_3(
        self,
        selected_item: Optional[str],
        reaction_time_ms: Optional[float] = None,
        interaction_time_ms: Optional[float] = None
    ) -> Dict[str, Any]:
        cfg = self.loader.get_challenge("ch3_find") or {}
        target = cfg.get("target_item", "umbrella")
        min_valid = cfg.get("min_valid_latency_ms", 150.0)
        optimal_ms = cfg.get("optimal_latency_ms", 2200.0)
        slow_ms = cfg.get("slow_latency_ms", 4800.0)

        clean_item = str(selected_item).strip().lower() if selected_item else None
        is_correct = (clean_item == target)

        # Reaction time validity and normalization
        valid_reaction = False
        latency_score = 0.0
        latency_band = "Uncollected"

        if reaction_time_ms is not None and reaction_time_ms >= min_valid:
            valid_reaction = True
            rt = float(reaction_time_ms)

            if rt <= optimal_ms:
                latency_score = 100.0
                latency_band = "Optimal / Prompt"
            elif rt <= slow_ms:
                # Linear drop from 100 to 60 between 2200ms and 4800ms
                fraction = (rt - optimal_ms) / (slow_ms - optimal_ms)
                latency_score = 100.0 - (fraction * 40.0)
                latency_band = "Normal Search Latency"
            elif rt <= 12000.0:
                # Linear drop from 60 to 20
                fraction = (rt - slow_ms) / (12000.0 - slow_ms)
                latency_score = max(20.0, 60.0 - (fraction * 40.0))
                latency_band = "Hesitant / Extended Search"
            else:
                latency_score = 10.0
                latency_band = "Prolonged Search"
        elif reaction_time_ms is not None and reaction_time_ms < min_valid:
            latency_band = "Anticipatory / Sub-physiological"
            latency_score = 30.0

        accuracy_score = 100.0 if is_correct else 0.0

        # Weighted: 70% target correctness, 30% latency efficiency if correct
        if is_correct:
            final_ch3_score = round((0.70 * accuracy_score) + (0.30 * latency_score), 1)
            description = f"Correct target identified ({latency_band})."
        else:
            final_ch3_score = 0.0
            description = "Incorrect target selected." if clean_item else "No item selected (skipped)."

        return {
            "challenge_id": "ch3_find",
            "name": cfg.get("name", "Challenge 3: Find"),
            "cognitive_domain": cfg.get("cognitive_domain", "Processing Speed & Sustained Attention"),
            "is_correct": is_correct,
            "selected_item": clean_item,
            "target_item": target,
            "reaction_time_ms": round(reaction_time_ms, 1) if reaction_time_ms is not None else None,
            "is_valid_reaction": valid_reaction,
            "latency_score": round(latency_score, 1),
            "latency_band": latency_band,
            "accuracy_pct": accuracy_score,
            "score": final_ch3_score,
            "timing_ms": interaction_time_ms,
            "description": description
        }

    # ── Full Session Evaluation ────────────────────────────────────────────────
    def score_session(
        self,
        ch1_selected: List[str],
        final_sequence: List[Any],
        ch3_selected: Optional[str],
        ch3_reaction_ms: Optional[float] = None,
        total_time_seconds: Optional[float] = None,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Calculates composite performance score across all three MindPlay challenges.
        """
        cfg = self.loader.config
        weights = cfg.get("composite_weights", {
            "ch1_remember": 0.35,
            "ch2_sequence": 0.35,
            "ch3_find": 0.30
        })

        res1 = self.score_challenge_1(ch1_selected)
        res2 = self.score_challenge_2(final_sequence)
        res3 = self.score_challenge_3(ch3_selected, reaction_time_ms=ch3_reaction_ms)

        w1 = weights.get("ch1_remember", 0.35)
        w2 = weights.get("ch2_sequence", 0.35)
        w3 = weights.get("ch3_find", 0.30)

        composite = (w1 * res1["score"]) + (w2 * res2["score"]) + (w3 * res3["score"])
        composite = round(max(0.0, min(100.0, composite)), 1)

        # Performance band
        bands = cfg.get("performance_bands", [])
        band_name = "Low / Incomplete Performance"
        band_desc = "Task responses were incomplete or fragmented."

        for b in bands:
            if composite >= b["min"]:
                band_name = b["band"]
                band_desc = b["description"]
                break

        # Count of completely correct tasks
        perfect_tasks = sum([1 for r in [res1, res2, res3] if r["is_correct"]])

        return {
            "session_id": session_id,
            "task_name": cfg.get("task_name", "MindPlay Tri-Challenge Cognitive Assessment"),
            "completed": True,
            "total_time_seconds": round(total_time_seconds, 1) if total_time_seconds is not None else None,
            "composite_score": composite,
            "performance_band": band_name,
            "band_description": band_desc,
            "perfect_tasks_count": perfect_tasks,
            "total_tasks_count": 3,
            "challenges": {
                "ch1_remember": res1,
                "ch2_sequence": res2,
                "ch3_find": res3
            },
            "summary_card": {
                "recall_accuracy": f"{res1['ch1_score']}/2",
                "sequence_status": "Correct" if res2["is_correct"] else "Incorrect",
                "reaction_latency": f"{Math_round_str(res3['reaction_time_ms'])}ms" if res3["reaction_time_ms"] else "—",
                "completion_time": f"{total_time_seconds}s" if total_time_seconds is not None else "—"
            },
            "disclaimer": cfg.get("disclaimer", "")
        }


def Math_round_str(val: Optional[float]) -> str:
    if val is None:
        return "—"
    return str(int(round(val)))

