from __future__ import annotations

from typing import Iterable


def _safe_divide(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator


def build_confusion_matrix(
    expected_labels: Iterable[str],
    predicted_labels: Iterable[str],
) -> dict:
    expected = list(expected_labels)
    predicted = list(predicted_labels)
    labels = sorted(set(expected) | set(predicted))
    index = {label: idx for idx, label in enumerate(labels)}
    matrix = [[0 for _ in labels] for _ in labels]

    for actual, guess in zip(expected, predicted):
        matrix[index[actual]][index[guess]] += 1

    return {
        "labels": labels,
        "matrix": matrix,
    }


def compute_classification_metrics(records: list[dict]) -> dict:
    expected = [record["expected_root_cause_label"] for record in records]
    predicted = [record["predicted_root_cause_label"] for record in records]

    confusion = build_confusion_matrix(expected, predicted)
    labels = confusion["labels"]
    matrix = confusion["matrix"]
    total_cases = len(records)
    correct = sum(
        1
        for actual, guess in zip(expected, predicted)
        if actual == guess
    )

    per_label: dict[str, dict] = {}
    macro_precision = 0.0
    macro_recall = 0.0
    macro_f1 = 0.0

    for idx, label in enumerate(labels):
        tp = matrix[idx][idx]
        fp = sum(matrix[row][idx] for row in range(len(labels)) if row != idx)
        fn = sum(matrix[idx][col] for col in range(len(labels)) if col != idx)
        support = sum(matrix[idx])

        precision = _safe_divide(tp, tp + fp)
        recall = _safe_divide(tp, tp + fn)
        f1 = _safe_divide(2 * precision * recall, precision + recall)

        per_label[label] = {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "support": support,
            "tp": tp,
            "fp": fp,
            "fn": fn,
        }
        macro_precision += precision
        macro_recall += recall
        macro_f1 += f1

    label_count = len(labels) if labels else 1
    return {
        "case_count": total_cases,
        "accuracy": round(_safe_divide(correct, total_cases), 4),
        "precision": round(macro_precision / label_count, 4),
        "recall": round(macro_recall / label_count, 4),
        "f1": round(macro_f1 / label_count, 4),
        "metric_convention": {
            "precision": "macro",
            "recall": "macro",
            "f1": "macro",
        },
        "per_label": per_label,
        "confusion_matrix": confusion,
    }


def confusion_matrix_csv_rows(confusion_matrix: dict) -> list[list[str]]:
    labels = confusion_matrix["labels"]
    matrix = confusion_matrix["matrix"]
    rows: list[list[str]] = [["actual\\predicted", *labels]]

    for label, row in zip(labels, matrix):
        rows.append([label, *[str(value) for value in row]])

    return rows
