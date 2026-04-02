from __future__ import annotations

import math
import re
from collections.abc import Iterable


_TOKEN_RE = re.compile(r"[a-z0-9]+")
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")
_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "did",
    "for",
    "from",
    "how",
    "in",
    "is",
    "it",
    "main",
    "of",
    "on",
    "or",
    "that",
    "the",
    "their",
    "this",
    "to",
    "was",
    "what",
    "when",
    "which",
    "why",
    "with",
}


def _tokens(text: str) -> set[str]:
    values = {
        token
        for token in _TOKEN_RE.findall(str(text or "").lower())
        if token not in _STOPWORDS and len(token) > 1
    }
    return values


def _sentences(text: str) -> list[str]:
    chunks = [part.strip() for part in _SENTENCE_RE.split(str(text or "").strip())]
    return [chunk for chunk in chunks if chunk]


def _safe_mean(values: Iterable[float]) -> float:
    values = list(values)
    if not values:
        return math.nan
    return sum(values) / len(values)


def _overlap_ratio(lhs: str, rhs: str) -> float:
    left = _tokens(lhs)
    right = _tokens(rhs)
    if not left or not right:
        return 0.0
    return len(left & right) / max(1, len(left))


def score_record(record: dict) -> dict[str, float]:
    user_input = record.get("user_input") or record.get("user_query", "")
    response = record.get("eval_response") or record.get("final_output", "")
    reference = record.get("reference_answer", "")
    retrieved_contexts = list(record.get("retrieved_contexts") or [])

    answer_relevancy = _overlap_ratio(user_input, response)

    response_sentences = _sentences(response) or [response]
    faithfulness_votes = []
    for sentence in response_sentences:
        support = max((_overlap_ratio(sentence, context) for context in retrieved_contexts), default=0.0)
        faithfulness_votes.append(1.0 if support >= 0.35 else support)
    faithfulness = _safe_mean(faithfulness_votes)

    context_precision_votes = []
    for context in retrieved_contexts:
        usefulness = max(_overlap_ratio(reference, context), _overlap_ratio(response, context))
        context_precision_votes.append(1.0 if usefulness >= 0.2 else usefulness)
    context_precision = _safe_mean(context_precision_votes)

    reference_sentences = _sentences(reference) or [reference]
    context_recall_votes = []
    for sentence in reference_sentences:
        support = max((_overlap_ratio(sentence, context) for context in retrieved_contexts), default=0.0)
        context_recall_votes.append(1.0 if support >= 0.35 else support)
    context_recall = _safe_mean(context_recall_votes)

    return {
        "answer_relevancy": 0.0 if math.isnan(answer_relevancy) else round(answer_relevancy, 6),
        "faithfulness": 0.0 if math.isnan(faithfulness) else round(faithfulness, 6),
        "context_precision": 0.0 if math.isnan(context_precision) else round(context_precision, 6),
        "context_recall": 0.0 if math.isnan(context_recall) else round(context_recall, 6),
    }


def aggregate_scores(scores: list[dict[str, float]]) -> dict[str, float]:
    if not scores:
        return {
            "answer_relevancy": 0.0,
            "faithfulness": 0.0,
            "context_precision": 0.0,
            "context_recall": 0.0,
        }

    metric_names = scores[0].keys()
    return {
        metric_name: round(_safe_mean(row[metric_name] for row in scores), 6)
        for metric_name in metric_names
    }
