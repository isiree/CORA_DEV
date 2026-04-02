from __future__ import annotations

import csv
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from evals.common import (
    DEFAULT_CONFUSION_CSV,
    DEFAULT_DATASET_PATH,
    DEFAULT_METRICS_JSON,
    DEFAULT_PREDICTIONS_CSV,
    DEFAULT_PREDICTIONS_JSON,
    OUTPUTS_ROOT,
)
from evals.metrics.rca_metrics import (
    compute_classification_metrics,
    confusion_matrix_csv_rows,
)
from evals.utils.label_extraction import extract_root_cause_label

# Keep the runner on the current mock RCA path.
os.environ["USE_LIVE_DATA"] = "false"

import app as app_module
from src.scenarios import build_scenario_run


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_dataset(dataset_path: Path) -> dict:
    with dataset_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _run_case(case: dict) -> dict:
    prompt = case["user_query"]
    scenario_run = build_scenario_run(case["scenario_id"])
    team_id = app_module._extract_team_from_query(prompt, "All Teams")

    # This is an RCA-only runner, so we evaluate the canonical root-cause
    # branch directly and record the fallback classifier result as context.
    classifier_intent_preview = app_module._fallback_classify_query_intent(prompt)
    detected_intent = "ROOT_CAUSE"
    result = app_module._build_mock_root_cause_result(scenario_run, team_id)

    final_output = result.get("answer", "")
    prediction = extract_root_cause_label(final_output)

    return {
        "test_id": case["test_id"],
        "scenario_id": case["scenario_id"],
        "user_query": case["user_query"],
        "expected_root_cause_label": case["expected_root_cause_label"],
        "predicted_root_cause_label": prediction.label,
        "label_match": prediction.label == case["expected_root_cause_label"],
        "expected_team": case["expected_team"],
        "expected_service": case["expected_service"],
        "reference_answer": case["reference_answer"],
        "final_output": final_output,
        "expected_tool_trajectory": case["expected_tool_trajectory"],
        "observed_tools_used": result.get("tools_used", []),
        "observed_sources": result.get("sources", []),
        "detected_intent": detected_intent,
        "classifier_intent_preview": classifier_intent_preview,
        "extraction_confidence": prediction.confidence,
        "matched_signals": prediction.matched_signals,
        "score_breakdown": prediction.score_breakdown,
        "extraction_notes": prediction.extraction_notes,
        "notes": case.get("notes", ""),
    }


def _write_json(path: Path, payload: dict | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=True)


def _write_predictions_csv(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "test_id",
        "scenario_id",
        "user_query",
        "expected_root_cause_label",
        "predicted_root_cause_label",
        "label_match",
        "expected_team",
        "expected_service",
        "detected_intent",
        "classifier_intent_preview",
        "extraction_confidence",
        "matched_signals",
        "expected_tool_trajectory",
        "observed_tools_used",
        "observed_sources",
        "reference_answer",
        "final_output",
        "extraction_notes",
        "notes",
    ]

    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for record in records:
            flat = dict(record)
            flat["matched_signals"] = " | ".join(record.get("matched_signals", []))
            flat["expected_tool_trajectory"] = " | ".join(record.get("expected_tool_trajectory", []))
            flat["observed_tools_used"] = " | ".join(record.get("observed_tools_used", []))
            flat["observed_sources"] = " | ".join(record.get("observed_sources", []))
            flat.pop("score_breakdown", None)
            writer.writerow(flat)


def _write_confusion_csv(path: Path, confusion_matrix: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = confusion_matrix_csv_rows(confusion_matrix)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerows(rows)


def main() -> None:
    dataset_path = DEFAULT_DATASET_PATH
    dataset = _load_dataset(dataset_path)
    cases = dataset.get("cases", [])
    records = [_run_case(case) for case in cases]

    metrics = compute_classification_metrics(records)
    metrics_payload = {
        "generated_at": _utc_now(),
        "dataset_id": dataset.get("dataset_id"),
        "dataset_version": dataset.get("version"),
        "dataset_path": str(dataset_path.relative_to(Path.cwd())),
        "assumptions": [
            "This runner evaluates the canonical deterministic mock root-cause function in app.py for the five numbered scenarios.",
            "Predicted RCA labels are extracted from final answer text only.",
            "Precision, recall, and F1 are macro-averaged across observed labels.",
        ],
        **metrics,
    }

    predictions_payload = {
        "generated_at": _utc_now(),
        "dataset_id": dataset.get("dataset_id"),
        "dataset_version": dataset.get("version"),
        "records": records,
    }

    _write_json(DEFAULT_PREDICTIONS_JSON, predictions_payload)
    _write_predictions_csv(DEFAULT_PREDICTIONS_CSV, records)
    _write_json(DEFAULT_METRICS_JSON, metrics_payload)
    _write_confusion_csv(DEFAULT_CONFUSION_CSV, metrics["confusion_matrix"])

    print(f"Wrote predictions JSON: {DEFAULT_PREDICTIONS_JSON}")
    print(f"Wrote predictions CSV: {DEFAULT_PREDICTIONS_CSV}")
    print(f"Wrote metrics JSON: {DEFAULT_METRICS_JSON}")
    print(f"Wrote confusion CSV: {DEFAULT_CONFUSION_CSV}")
    print(
        "Summary: "
        f"accuracy={metrics['accuracy']:.4f}, "
        f"precision={metrics['precision']:.4f}, "
        f"recall={metrics['recall']:.4f}, "
        f"f1={metrics['f1']:.4f}"
    )


if __name__ == "__main__":
    main()
