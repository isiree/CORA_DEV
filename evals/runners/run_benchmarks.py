from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from evals.adapters import HistoricalRAGEvalAdapter, WorkflowEvalAdapter
from evals.adapters.benchmark_variants import (
    KeywordRAGEvalBaselineAdapter,
    MinimalToolPathWorkflowAdapter,
    NoRAGWorkflowEvalAdapter,
)
from evals.common import (
    DEFAULT_BENCHMARK_RESULTS_CSV,
    DEFAULT_BENCHMARK_RESULTS_JSON,
    DEFAULT_BENCHMARK_RESULTS_MD,
    DEFAULT_DATASET_PATH,
)
from evals.metrics.rag_fallback_metrics import aggregate_scores as aggregate_rag_scores
from evals.metrics.rag_fallback_metrics import score_record as score_rag_record
from evals.metrics.workflow_metrics import _token_f1, aggregate_workflow_scores, score_workflow_record
from evals.utils.tabular_exports import write_csv_rows, write_markdown_table

# Keep benchmarks on the fixed mock data path.
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


def _workflow_variant_rows(name: str, adapter: Any, cases: list[dict[str, Any]], notes: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    records = []
    for case in cases:
        result = adapter.run_case(case)
        record = {
            "test_id": case["test_id"],
            "scenario_id": case["scenario_id"],
            "user_query": case["user_query"],
            "reference_answer": case["reference_answer"],
            "expected_root_cause_label": case["expected_root_cause_label"],
            "expected_team": case["expected_team"],
            "expected_service": case["expected_service"],
            "expected_tool_trajectory": case["expected_tool_trajectory"],
            "observed_tool_trajectory": [step.get("tool") for step in result.steps if step.get("tool")] or result.tools_used,
            "observed_tools_used": result.tools_used,
            "final_output": result.final_output,
            "execution_mode": result.execution_mode,
        }
        record.update(score_workflow_record(record))
        records.append(record)

    aggregate = aggregate_workflow_scores(records)
    row = {
        "benchmark_family": "workflow",
        "variant": name,
        "cases": len(records),
        "response_match_f1": aggregate["response_match_f1"],
        "rubric_score": aggregate["rubric_score"],
        "tool_trajectory_score": aggregate["tool_trajectory_score"],
        "tool_exact_match_rate": aggregate["tool_trajectory_exact_match_rate"],
        "context_precision": "",
        "context_recall": "",
        "faithfulness": "",
        "answer_relevancy": "",
        "notes": notes,
    }
    return row, records


def _rag_variant_rows(name: str, adapter: Any, cases: list[dict[str, Any]], notes: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    records = []
    metric_rows = []
    for case in cases:
        result = adapter.run_case(case)
        record = {
            "test_id": case["test_id"],
            "scenario_id": case["scenario_id"],
            "user_query": case["user_query"],
            "reference_answer": case["reference_answer"],
            "retrieved_contexts": result.retrieved_contexts,
            "retrieved_sources": result.retrieved_sources,
            "eval_response": result.eval_response,
            "final_output": result.final_output,
        }
        rag_scores = score_rag_record(record)
        metric_rows.append(rag_scores)
        answer_match = _token_f1(result.eval_response, case["reference_answer"])
        record.update(rag_scores)
        record["response_match_f1"] = round(answer_match["f1"], 6)
        records.append(record)

    rag_aggregate = aggregate_rag_scores(metric_rows) if metric_rows else {
        "context_precision": 0.0,
        "context_recall": 0.0,
        "faithfulness": 0.0,
        "answer_relevancy": 0.0,
    }
    response_match = round(sum(record["response_match_f1"] for record in records) / len(records), 6) if records else 0.0
    row = {
        "benchmark_family": "rag_component",
        "variant": name,
        "cases": len(records),
        "response_match_f1": response_match,
        "rubric_score": "",
        "tool_trajectory_score": "",
        "tool_exact_match_rate": "",
        "context_precision": rag_aggregate["context_precision"],
        "context_recall": rag_aggregate["context_recall"],
        "faithfulness": rag_aggregate["faithfulness"],
        "answer_relevancy": rag_aggregate["answer_relevancy"],
        "notes": notes,
    }
    return row, records


def main() -> None:
    dataset = _load_dataset(DEFAULT_DATASET_PATH)
    cases = dataset.get("cases", [])

    benchmark_rows = []
    detail_records: dict[str, list[dict[str, Any]]] = {}

    row, details = _workflow_variant_rows(
        "full_system",
        WorkflowEvalAdapter(team_filter="All Teams"),
        cases,
        "Current end-to-end mock workflow in app.py.",
    )
    benchmark_rows.append(row)
    detail_records["full_system"] = details

    row, details = _workflow_variant_rows(
        "system_without_rag",
        NoRAGWorkflowEvalAdapter(team_filter="All Teams"),
        cases,
        "Same agent workflow with historical_tool conceptually removed; on the current fixed root-cause dataset it usually remains close to the full system because these prompts are mostly cost/pipeline investigations.",
    )
    benchmark_rows.append(row)
    detail_records["system_without_rag"] = details

    row, details = _workflow_variant_rows(
        "minimal_tool_path",
        MinimalToolPathWorkflowAdapter(team_filter="All Teams"),
        cases,
        "Pipeline-first minimal baseline using only the earliest available tool step.",
    )
    benchmark_rows.append(row)
    detail_records["minimal_tool_path"] = details

    row, details = _rag_variant_rows(
        "semantic_rag_current",
        HistoricalRAGEvalAdapter(top_k=3, summarize=True),
        cases,
        "Current semantic retrieval plus summary generation path, scored with the local RAG fallback metrics for benchmark comparability.",
    )
    benchmark_rows.append(row)
    detail_records["semantic_rag_current"] = details

    row, details = _rag_variant_rows(
        "keyword_rag_baseline",
        KeywordRAGEvalBaselineAdapter(top_k=3),
        cases,
        "Simple keyword-overlap retrieval baseline over local markdown knowledge docs.",
    )
    benchmark_rows.append(row)
    detail_records["keyword_rag_baseline"] = details

    payload = {
        "generated_at": _utc_now(),
        "dataset_id": dataset.get("dataset_id"),
        "dataset_version": dataset.get("version"),
        "dataset_path": str(DEFAULT_DATASET_PATH.relative_to(Path.cwd())),
        "rows": benchmark_rows,
        "details": detail_records,
    }

    _write_json(DEFAULT_BENCHMARK_RESULTS_JSON, payload)
    write_csv_rows(DEFAULT_BENCHMARK_RESULTS_CSV, benchmark_rows)
    write_markdown_table(DEFAULT_BENCHMARK_RESULTS_MD, benchmark_rows)

    print(f"Wrote benchmark JSON: {DEFAULT_BENCHMARK_RESULTS_JSON}")
    print(f"Wrote benchmark CSV: {DEFAULT_BENCHMARK_RESULTS_CSV}")
    print(f"Wrote benchmark Markdown: {DEFAULT_BENCHMARK_RESULTS_MD}")


if __name__ == "__main__":
    main()
