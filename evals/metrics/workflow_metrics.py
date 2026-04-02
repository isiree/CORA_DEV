from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable

from evals.utils.label_extraction import extract_root_cause_label


_TOKEN_RE = re.compile(r"[a-z0-9]+")
_ANCHOR_RE = re.compile(r"[A-Za-z0-9_=\-/]+")
_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "because",
    "by",
    "for",
    "from",
    "has",
    "have",
    "in",
    "is",
    "it",
    "main",
    "of",
    "on",
    "or",
    "reason",
    "that",
    "the",
    "their",
    "this",
    "to",
    "was",
    "what",
    "which",
    "while",
    "why",
    "with",
}
_UNCERTAINTY_SIGNALS = (
    "not directly stated",
    "more information",
    "unfortunately",
    "do not contain specific information",
    "do not specifically mention",
    "i may be able",
    "would be required",
)


def _safe_mean(values: Iterable[float]) -> float:
    values = list(values)
    if not values:
        return 0.0
    return sum(values) / len(values)


def _tokenize(text: str) -> list[str]:
    return [token for token in _TOKEN_RE.findall(str(text or "").lower()) if token not in _STOPWORDS]


def _token_f1(prediction: str, reference: str) -> dict[str, float]:
    pred_tokens = _tokenize(prediction)
    ref_tokens = _tokenize(reference)
    if not pred_tokens or not ref_tokens:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0}

    pred_counts = Counter(pred_tokens)
    ref_counts = Counter(ref_tokens)
    overlap = sum(min(pred_counts[token], ref_counts[token]) for token in pred_counts)
    precision = overlap / len(pred_tokens) if pred_tokens else 0.0
    recall = overlap / len(ref_tokens) if ref_tokens else 0.0
    f1 = 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)
    return {
        "precision": round(precision, 6),
        "recall": round(recall, 6),
        "f1": round(f1, 6),
    }


def _normalize_label(text: str) -> str:
    return str(text or "").strip().lower().replace("-", " ")


def _mentions_expected_team(answer: str, team_id: str) -> bool:
    normalized_answer = _normalize_label(answer)
    team_variants = {
        _normalize_label(team_id),
        _normalize_label(team_id.replace("-", " ")),
        _normalize_label(team_id.replace("-", "")),
    }
    pretty = team_id.replace("-", " ").title()
    team_variants.add(_normalize_label(pretty))
    if team_id == "ci-team":
        team_variants.add("ci team")
    return any(variant and variant in normalized_answer for variant in team_variants)


def _mentions_expected_service(answer: str, expected_service: str) -> float:
    answer_tokens = set(_tokenize(answer))
    service_tokens = set(_tokenize(expected_service))
    if not service_tokens:
        return 0.0
    overlap = len(answer_tokens & service_tokens)
    return round(overlap / len(service_tokens), 6)


def _extract_reference_anchors(reference: str) -> list[str]:
    anchors: list[str] = []
    for raw in _ANCHOR_RE.findall(str(reference or "")):
        token = raw.strip(".,:;()[]{}'\"")
        lowered = token.lower()
        if len(token) < 4:
            continue
        if token.isalpha() and lowered in _STOPWORDS:
            continue
        if "-" in token or "_" in token or "=" in token or any(ch.isdigit() for ch in token):
            anchors.append(lowered)
    seen: set[str] = set()
    ordered: list[str] = []
    for anchor in anchors:
        if anchor not in seen:
            seen.add(anchor)
            ordered.append(anchor)
    return ordered


def _evidence_score(answer: str, reference: str) -> float:
    anchors = _extract_reference_anchors(reference)
    if not anchors:
        return 0.0
    normalized_answer = str(answer or "").lower()
    matched = sum(1 for anchor in anchors if anchor in normalized_answer)
    target = min(3, len(anchors))
    return round(min(1.0, matched / target), 6)


def _clarity_score(answer: str) -> float:
    normalized_answer = str(answer or "").lower()
    return 0.0 if any(signal in normalized_answer for signal in _UNCERTAINTY_SIGNALS) else 1.0


def _lcs_length(lhs: list[str], rhs: list[str]) -> int:
    if not lhs or not rhs:
        return 0
    dp = [0] * (len(rhs) + 1)
    for left in lhs:
        prev = 0
        for idx, right in enumerate(rhs, start=1):
            current = dp[idx]
            if left == right:
                dp[idx] = prev + 1
            else:
                dp[idx] = max(dp[idx], dp[idx - 1])
            prev = current
    return dp[-1]


def _tool_metrics(expected: list[str], observed: list[str]) -> dict[str, float | bool]:
    expected = list(expected or [])
    observed = list(observed or [])
    expected_counter = Counter(expected)
    observed_counter = Counter(observed)
    overlap = sum(min(expected_counter[token], observed_counter[token]) for token in expected_counter)
    precision = overlap / len(observed) if observed else 0.0
    recall = overlap / len(expected) if expected else 0.0
    f1 = 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)
    order_score = _lcs_length(expected, observed) / len(expected) if expected else 0.0
    exact_match = expected == observed
    trajectory_score = (f1 + order_score) / 2 if expected else 0.0
    return {
        "tool_precision": round(precision, 6),
        "tool_recall": round(recall, 6),
        "tool_f1": round(f1, 6),
        "tool_order_score": round(order_score, 6),
        "tool_trajectory_score": round(trajectory_score, 6),
        "tool_trajectory_exact_match": exact_match,
    }


def score_workflow_record(record: dict) -> dict:
    answer = record.get("final_output", "")
    reference = record.get("reference_answer", "")
    response_match = _token_f1(answer, reference)
    prediction = extract_root_cause_label(answer)
    cause_correct = prediction.label == record.get("expected_root_cause_label")
    team_score = 1.0 if _mentions_expected_team(answer, record.get("expected_team", "")) else 0.0
    service_score = _mentions_expected_service(answer, record.get("expected_service", ""))
    evidence_score = _evidence_score(answer, reference)
    clarity_score = _clarity_score(answer)
    rubric_components = {
        "cause_correctness": 1.0 if cause_correct else 0.0,
        "team_grounding": round(team_score, 6),
        "service_grounding": round(service_score, 6),
        "evidence_grounding": round(evidence_score, 6),
        "clarity_confidence": round(clarity_score, 6),
    }
    rubric_score = round(_safe_mean(rubric_components.values()), 6)
    tool_scores = _tool_metrics(
        list(record.get("expected_tool_trajectory", [])),
        list(record.get("observed_tool_trajectory", [])) or list(record.get("observed_tools_used", [])),
    )
    return {
        "response_match_precision": response_match["precision"],
        "response_match_recall": response_match["recall"],
        "response_match_f1": response_match["f1"],
        "predicted_root_cause_label": prediction.label,
        "root_cause_match": cause_correct,
        "rubric_score": rubric_score,
        "rubric_breakdown": rubric_components,
        **tool_scores,
    }


def aggregate_workflow_scores(records: list[dict]) -> dict[str, float]:
    if not records:
        return {
            "response_match_f1": 0.0,
            "rubric_score": 0.0,
            "tool_trajectory_score": 0.0,
            "tool_trajectory_exact_match_rate": 0.0,
        }

    return {
        "response_match_f1": round(_safe_mean(float(record["response_match_f1"]) for record in records), 6),
        "rubric_score": round(_safe_mean(float(record["rubric_score"]) for record in records), 6),
        "tool_trajectory_score": round(_safe_mean(float(record["tool_trajectory_score"]) for record in records), 6),
        "tool_trajectory_exact_match_rate": round(
            _safe_mean(1.0 if record["tool_trajectory_exact_match"] else 0.0 for record in records),
            6,
        ),
    }
