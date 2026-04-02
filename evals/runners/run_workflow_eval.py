from __future__ import annotations

import csv
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from evals.adapters import WorkflowEvalAdapter
from evals.common import (
    DEFAULT_DATASET_PATH,
    DEFAULT_WORKFLOW_METRICS_JSON,
    DEFAULT_WORKFLOW_PREDICTIONS_CSV,
    DEFAULT_WORKFLOW_PREDICTIONS_JSON,
)
from evals.metrics.workflow_metrics import aggregate_workflow_scores, score_workflow_record

# Keep the workflow eval on the current mock investigation path.
os.environ["USE_LIVE_DATA"] = "false"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_dataset(dataset_path: Path) -> dict[str, Any]:
    with dataset_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: Path, payload: dict | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=True)


def _write_predictions_csv(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "test_id",
        "scenario_id",
        "user_query",
        "detected_intent",
        "classifier_preview",
        "execution_mode",
        "expected_root_cause_label",
        "predicted_root_cause_label",
        "root_cause_match",
        "expected_tool_trajectory",
        "observed_tool_trajectory",
        "observed_tools_used",
        "tool_trajectory_exact_match",
        "tool_trajectory_score",
        "response_match_f1",
        "rubric_score",
        "reference_answer",
        "final_output",
        "observed_sources",
        "notes",
    ]

    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for record in records:
            flat = dict(record)
            flat["expected_tool_trajectory"] = " | ".join(record.get("expected_tool_trajectory", []))
            flat["observed_tool_trajectory"] = " | ".join(record.get("observed_tool_trajectory", []))
            flat["observed_tools_used"] = " | ".join(record.get("observed_tools_used", []))
            flat["observed_sources"] = " | ".join(record.get("observed_sources", []))
            flat.pop("steps", None)
            flat.pop("rubric_breakdown", None)
            writer.writerow(flat)


def _build_record(case: dict[str, Any], workflow_result: Any) -> dict[str, Any]:
    return {
        "test_id": case["test_id"],
        "scenario_id": case["scenario_id"],
        "user_query": case["user_query"],
        "reference_answer": case["reference_answer"],
        "expected_root_cause_label": case["expected_root_cause_label"],
        "expected_team": case["expected_team"],
        "expected_service": case["expected_service"],
        "expected_tool_trajectory": case["expected_tool_trajectory"],
        "detected_intent": workflow_result.detected_intent,
        "classifier_preview": workflow_result.classifier_preview,
        "execution_mode": workflow_result.execution_mode,
        "final_output": workflow_result.final_output,
        "observed_tool_trajectory": [step.get("tool") for step in workflow_result.steps if step.get("tool")] or workflow_result.tools_used,
        "observed_tools_used": workflow_result.tools_used,
        "observed_sources": workflow_result.sources,
        "steps": workflow_result.steps,
        "notes": case.get("notes", ""),
    }


def main() -> None:
    dataset_path = DEFAULT_DATASET_PATH
    dataset = _load_dataset(dataset_path)
    cases = dataset.get("cases", [])

    adapter = WorkflowEvalAdapter(team_filter="All Teams")
    records = [_build_record(case, adapter.run_case(case)) for case in cases]

    for record in records:
        record.update(score_workflow_record(record))

    aggregate = aggregate_workflow_scores(records)
    metrics_payload = {
        "generated_at": _utc_now(),
        "dataset_id": dataset.get("dataset_id"),
        "dataset_version": dataset.get("version"),
        "dataset_path": str(dataset_path.relative_to(Path.cwd())),
        "evaluation_component": "full_mock_workflow",
        "metrics": aggregate,
        "backend": {
            "evaluator": "local_structured",
            "adk_supported": False,
            "adk_gap_reason": (
                "The current app is a custom HTTP server plus LangChain/Groq agent with deterministic mock branches, "
                "not a Google ADK agent runtime. There is no google.adk dependency, ADK session model, or ADK-native tool trace stream to plug into directly."
            ),
            "adk_todo": [
                "Wrap the workflow in an ADK-native agent/session abstraction instead of the current custom app.py dispatch path.",
                "Emit tool calls and intermediate events in ADK's trace/evaluation format rather than only app-local steps/tool lists.",
                "Add the google.adk dependency and map the current mock scenario execution path into ADK runner inputs and outputs.",
            ],
        },
        "assumptions": [
            "This runner follows the same end-to-end mock workflow as app.py: classify query, try deterministic mock handling, then fall back to the live agent only if needed.",
            "For the fixed dataset, the prompts are single-turn root-cause questions, so the current workflow normally resolves through the deterministic mock branch.",
            "Response match is measured with local token-overlap F1 against reference_answer.",
            "Rubric score is a local structured score based on root-cause correctness, team grounding, service grounding, evidence grounding, and clarity.",
            "Tool trajectory score combines tool-set overlap and order preservation against expected_tool_trajectory.",
        ],
    }

    predictions_payload = {
        "generated_at": _utc_now(),
        "dataset_id": dataset.get("dataset_id"),
        "dataset_version": dataset.get("version"),
        "evaluation_component": "full_mock_workflow",
        "records": records,
    }

    _write_json(DEFAULT_WORKFLOW_PREDICTIONS_JSON, predictions_payload)
    _write_predictions_csv(DEFAULT_WORKFLOW_PREDICTIONS_CSV, records)
    _write_json(DEFAULT_WORKFLOW_METRICS_JSON, metrics_payload)

    print(f"Wrote predictions JSON: {DEFAULT_WORKFLOW_PREDICTIONS_JSON}")
    print(f"Wrote predictions CSV: {DEFAULT_WORKFLOW_PREDICTIONS_CSV}")
    print(f"Wrote metrics JSON: {DEFAULT_WORKFLOW_METRICS_JSON}")
    print(
        "Summary: "
        f"response_match_f1={aggregate['response_match_f1']:.4f}, "
        f"rubric_score={aggregate['rubric_score']:.4f}, "
        f"tool_trajectory_score={aggregate['tool_trajectory_score']:.4f}, "
        f"tool_exact_match_rate={aggregate['tool_trajectory_exact_match_rate']:.4f}"
    )


if __name__ == "__main__":
    main()
