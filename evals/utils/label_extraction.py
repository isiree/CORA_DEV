from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Dict, List, Tuple

from evals.common import MANUAL_REVIEW_PLACEHOLDER


@dataclass
class LabelPrediction:
    label: str
    confidence: float
    matched_signals: list[str]
    score_breakdown: dict[str, int]
    extraction_notes: str

    def to_dict(self) -> dict:
        return asdict(self)


_LABEL_CATALOG: Dict[str, List[Tuple[str, int]]] = {
    "failed_cleanup_orphaned_resources": [
        ("destroy-loadtest", 4),
        ("terraform-destroy", 4),
        ("state lock", 4),
        ("failed cleanup", 3),
        ("left running", 2),
        ("load-test", 2),
        ("orphaned", 1),
    ],
    "tagging_regression_misattribution": [
        ("team=legacy", 4),
        ("unallocated", 3),
        ("misattributed", 3),
        ("mistag", 3),
        ("tagging", 2),
        ("missing team tags", 2),
        ("deploy-release-prod", 2),
    ],
    "autoscaler_no_scale_down": [
        ("update-web-autoscaler", 4),
        ("autoscaler", 3),
        ("web-frontend-asg", 3),
        ("no scale-down", 3),
        ("never scaled back down", 3),
        ("12 instances", 2),
        ("scale-down", 1),
    ],
    "forgotten_poc_environment": [
        ("deploy-poc-analytics", 4),
        ("proof-of-concept", 3),
        ("forgotten", 3),
        ("poc-analytics", 3),
        ("abandoned", 2),
        ("dashboard poc", 1),
    ],
    "application_misconfiguration_over_scaling": [
        ("deploy-release-api", 4),
        ("max_workers=500", 4),
        ("retry storm", 3),
        ("application configuration", 3),
        ("release-api", 2),
        ("pod surge", 2),
        ("pods", 1),
    ],
}


def _normalize(text: str) -> str:
    return " ".join(str(text or "").lower().split())


def extract_root_cause_label(answer_text: str) -> LabelPrediction:
    """
    Extract a canonical RCA label from the final answer text.

    Assumptions:
    - Extraction is answer-only; it does not inspect scenario_id or expected labels.
    - The best label is the one with the highest weighted signal score.
    - Ties or zero-signal cases are treated as ambiguous.
    """
    normalized = _normalize(answer_text)
    score_breakdown: dict[str, int] = {}
    matched_by_label: dict[str, list[str]] = {}

    for label, signals in _LABEL_CATALOG.items():
        score = 0
        matched_signals: list[str] = []
        for signal, weight in signals:
            if signal in normalized:
                score += weight
                matched_signals.append(signal)
        score_breakdown[label] = score
        matched_by_label[label] = matched_signals

    best_score = max(score_breakdown.values()) if score_breakdown else 0
    if best_score <= 0:
        return LabelPrediction(
            label=MANUAL_REVIEW_PLACEHOLDER,
            confidence=0.0,
            matched_signals=[],
            score_breakdown=score_breakdown,
            extraction_notes="No label-specific RCA signals were found in the final answer.",
        )

    best_labels = [label for label, score in score_breakdown.items() if score == best_score]
    if len(best_labels) > 1:
        return LabelPrediction(
            label=MANUAL_REVIEW_PLACEHOLDER,
            confidence=0.0,
            matched_signals=[],
            score_breakdown=score_breakdown,
            extraction_notes=(
                "Multiple labels reached the same top score: "
                + ", ".join(sorted(best_labels))
            ),
        )

    chosen_label = best_labels[0]
    total_possible = sum(weight for _, weight in _LABEL_CATALOG[chosen_label])
    confidence = round(best_score / total_possible, 4) if total_possible else 0.0
    return LabelPrediction(
        label=chosen_label,
        confidence=confidence,
        matched_signals=matched_by_label[chosen_label],
        score_breakdown=score_breakdown,
        extraction_notes="Label selected by highest weighted signal score.",
    )
