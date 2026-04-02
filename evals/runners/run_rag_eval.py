from __future__ import annotations

import argparse
import csv
import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from evals.adapters import HistoricalRAGEvalAdapter
from evals.common import (
    DEFAULT_DATASET_PATH,
    DEFAULT_RAG_METRICS_JSON,
    DEFAULT_RAG_PREDICTIONS_CSV,
    DEFAULT_RAG_PREDICTIONS_JSON,
)
from evals.metrics.rag_fallback_metrics import aggregate_scores, score_record


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
        "expected_root_cause_label",
        "expected_team",
        "expected_service",
        "retrieved_context_count",
        "retrieved_sources",
        "context_precision",
        "context_recall",
        "faithfulness",
        "answer_relevancy",
        "reference_answer",
        "eval_response",
        "final_output",
        "notes",
    ]

    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for record in records:
            flat = dict(record)
            flat["retrieved_sources"] = " | ".join(record.get("retrieved_sources", []))
            flat.pop("retrieved_contexts", None)
            writer.writerow(flat)


def _build_record(case: dict[str, Any], rag_result: Any) -> dict[str, Any]:
    return {
        "test_id": case["test_id"],
        "scenario_id": case["scenario_id"],
        "user_query": case["user_query"],
        "expected_root_cause_label": case["expected_root_cause_label"],
        "expected_team": case["expected_team"],
        "expected_service": case["expected_service"],
        "reference_answer": case["reference_answer"],
        "retrieved_context_count": len(rag_result.retrieved_contexts),
        "retrieved_contexts": rag_result.retrieved_contexts,
        "retrieved_sources": rag_result.retrieved_sources,
        "final_output": rag_result.final_output,
        "eval_response": rag_result.eval_response,
        "notes": case.get("notes", ""),
    }


def _compute_means(scores: list[dict[str, Any]]) -> dict[str, float]:
    if not scores:
        return {}

    metric_names = scores[0].keys()
    means: dict[str, float] = {}
    for metric_name in metric_names:
        values = [float(row[metric_name]) for row in scores if not math.isnan(float(row[metric_name]))]
        means[metric_name] = round(sum(values) / len(values), 6) if values else 0.0
    return means


def _run_ragas(records: list[dict[str, Any]]) -> dict[str, Any]:
    from ragas import evaluate
    from ragas.dataset_schema import EvaluationDataset
    from ragas.metrics import (
        answer_relevancy,
        context_precision,
        context_recall,
        faithfulness,
    )
    from langchain_community.embeddings import HuggingFaceEmbeddings
    from langchain_groq import ChatGroq

    # These defaults make the sentence-transformers path more stable on CPU-only machines.
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

    rows = [
        {
            "user_input": record["user_query"],
            "retrieved_contexts": record["retrieved_contexts"],
            "response": record["eval_response"],
            "reference": record["reference_answer"],
        }
        for record in records
    ]

    dataset = EvaluationDataset.from_list(rows)
    llm = ChatGroq(
        model=os.getenv("LLM_MODEL", "llama-3.3-70b-versatile"),
        temperature=0,
    )
    answer_relevancy_metric = answer_relevancy
    if hasattr(answer_relevancy_metric, "strictness"):
        answer_relevancy_metric.strictness = 1

    embeddings = HuggingFaceEmbeddings(
        model_name=os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2"),
        cache_folder="models",
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
        show_progress=False,
    )

    result = evaluate(
        dataset=dataset,
        metrics=[
            context_precision,
            context_recall,
            faithfulness,
            answer_relevancy_metric,
        ],
        llm=llm,
        embeddings=embeddings,
        raise_exceptions=False,
        show_progress=False,
    )

    return {
        "mode": "ragas",
        "backend": {
            "ragas_version": __import__("ragas").__version__,
            "llm_model": os.getenv("LLM_MODEL", "llama-3.3-70b-versatile"),
            "embedding_model": os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2"),
        },
        "per_row_scores": result.scores,
        "aggregate_scores": _compute_means(result.scores),
    }


def _run_local_fallback(records: list[dict[str, Any]], reason: str) -> dict[str, Any]:
    per_row_scores = [score_record(record) for record in records]
    return {
        "mode": "local_fallback",
        "backend": {
            "reason": reason,
            "todo": "Install and configure RAGAS-compatible judge dependencies if you want LLM-graded metrics instead of the local approximation.",
        },
        "per_row_scores": per_row_scores,
        "aggregate_scores": aggregate_scores(per_row_scores),
    }


def _score_records(records: list[dict[str, Any]], mode: str) -> dict[str, Any]:
    if mode == "local":
        return _run_local_fallback(records, "Requested local-only mode.")

    try:
        return _run_ragas(records)
    except Exception as exc:  # pragma: no cover - this is an environment fallback path.
        if mode == "ragas":
            raise
        return _run_local_fallback(records, f"RAGAS evaluation failed: {type(exc).__name__}: {exc}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run RAG evaluation for the historical document pipeline.")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=DEFAULT_DATASET_PATH,
        help="Path to the fixed evaluation dataset JSON.",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=3,
        help="Number of retrieved chunks to evaluate per query.",
    )
    parser.add_argument(
        "--mode",
        choices=["auto", "ragas", "local"],
        default="auto",
        help="Use direct RAGAS scoring, force local fallback scoring, or try RAGAS then fall back locally.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    dataset_path = args.dataset
    dataset = _load_dataset(dataset_path)
    cases = dataset.get("cases", [])

    adapter = HistoricalRAGEvalAdapter(top_k=args.top_k, summarize=True)
    records = [_build_record(case, adapter.run_case(case)) for case in cases]

    scoring = _score_records(records, args.mode)
    per_row_scores = scoring["per_row_scores"]
    for record, row_scores in zip(records, per_row_scores):
        record.update(row_scores)

    metrics_payload = {
        "generated_at": _utc_now(),
        "dataset_id": dataset.get("dataset_id"),
        "dataset_version": dataset.get("version"),
        "dataset_path": str(dataset_path.relative_to(Path.cwd())),
        "evaluation_component": "historical_tool",
        "scoring_mode": scoring["mode"],
        "top_k": args.top_k,
        "metrics": scoring["aggregate_scores"],
        "backend": scoring["backend"],
        "assumptions": [
            "This runner evaluates the current historical_tool RAG path: retrieve top-k chunks, then summarize them into a final answer.",
            "The fixed RCA dataset is reused as-is; reference_answer is used as the gold reference for RAG evaluation.",
            "The eval_response field strips the trailing Sources block from the final tool output before scoring to avoid grading citation boilerplate.",
        ],
    }

    predictions_payload = {
        "generated_at": _utc_now(),
        "dataset_id": dataset.get("dataset_id"),
        "dataset_version": dataset.get("version"),
        "evaluation_component": "historical_tool",
        "scoring_mode": scoring["mode"],
        "records": records,
    }

    _write_json(DEFAULT_RAG_PREDICTIONS_JSON, predictions_payload)
    _write_predictions_csv(DEFAULT_RAG_PREDICTIONS_CSV, records)
    _write_json(DEFAULT_RAG_METRICS_JSON, metrics_payload)

    print(f"Wrote predictions JSON: {DEFAULT_RAG_PREDICTIONS_JSON}")
    print(f"Wrote predictions CSV: {DEFAULT_RAG_PREDICTIONS_CSV}")
    print(f"Wrote metrics JSON: {DEFAULT_RAG_METRICS_JSON}")
    print(
        "Summary: "
        f"context_precision={metrics_payload['metrics'].get('context_precision', 0.0):.4f}, "
        f"context_recall={metrics_payload['metrics'].get('context_recall', 0.0):.4f}, "
        f"faithfulness={metrics_payload['metrics'].get('faithfulness', 0.0):.4f}, "
        f"answer_relevancy={metrics_payload['metrics'].get('answer_relevancy', 0.0):.4f}, "
        f"mode={scoring['mode']}"
    )


if __name__ == "__main__":
    main()
