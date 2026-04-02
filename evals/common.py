from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
EVALS_ROOT = REPO_ROOT / "evals"
DATASET_ROOT = EVALS_ROOT / "dataset"
OUTPUTS_ROOT = EVALS_ROOT / "outputs"

DEFAULT_DATASET_PATH = DATASET_ROOT / "mock_scenarios_starter.json"
DEFAULT_PREDICTIONS_JSON = OUTPUTS_ROOT / "rca_eval_predictions.json"
DEFAULT_PREDICTIONS_CSV = OUTPUTS_ROOT / "rca_eval_predictions.csv"
DEFAULT_METRICS_JSON = OUTPUTS_ROOT / "rca_eval_metrics.json"
DEFAULT_CONFUSION_CSV = OUTPUTS_ROOT / "rca_eval_confusion_matrix.csv"

DEFAULT_RAG_PREDICTIONS_JSON = OUTPUTS_ROOT / "rag_eval_predictions.json"
DEFAULT_RAG_PREDICTIONS_CSV = OUTPUTS_ROOT / "rag_eval_predictions.csv"
DEFAULT_RAG_METRICS_JSON = OUTPUTS_ROOT / "rag_eval_metrics.json"
DEFAULT_WORKFLOW_PREDICTIONS_JSON = OUTPUTS_ROOT / "workflow_eval_predictions.json"
DEFAULT_WORKFLOW_PREDICTIONS_CSV = OUTPUTS_ROOT / "workflow_eval_predictions.csv"
DEFAULT_WORKFLOW_METRICS_JSON = OUTPUTS_ROOT / "workflow_eval_metrics.json"
DEFAULT_BENCHMARK_RESULTS_JSON = OUTPUTS_ROOT / "benchmarking_results.json"
DEFAULT_BENCHMARK_RESULTS_CSV = OUTPUTS_ROOT / "benchmarking_results.csv"
DEFAULT_BENCHMARK_RESULTS_MD = OUTPUTS_ROOT / "benchmarking_results.md"
DEFAULT_THESIS_ROOT_CAUSE_CSV = OUTPUTS_ROOT / "root_cause_results.csv"
DEFAULT_THESIS_ROOT_CAUSE_MD = OUTPUTS_ROOT / "root_cause_results.md"
DEFAULT_THESIS_RAG_CSV = OUTPUTS_ROOT / "rag_results.csv"
DEFAULT_THESIS_RAG_MD = OUTPUTS_ROOT / "rag_results.md"
DEFAULT_THESIS_WORKFLOW_CSV = OUTPUTS_ROOT / "workflow_results.csv"
DEFAULT_THESIS_WORKFLOW_MD = OUTPUTS_ROOT / "workflow_results.md"

MANUAL_REVIEW_PLACEHOLDER = "MANUAL_REVIEW_REQUIRED"
