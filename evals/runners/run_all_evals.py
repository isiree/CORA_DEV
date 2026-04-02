from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def _run_step(step_name: str, module: str, extra_args: list[str] | None = None) -> None:
    cmd = [sys.executable, "-m", module]
    if extra_args:
        cmd.extend(extra_args)

    print(f"[evals] Running {step_name}: {' '.join(cmd)}")
    subprocess.run(
        cmd,
        cwd=str(REPO_ROOT),
        env=os.environ.copy(),
        check=True,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the full IMRAG evaluation suite end to end.")
    parser.add_argument(
        "--rag-mode",
        choices=["auto", "ragas", "local"],
        default="auto",
        help="Mode to pass through to the RAG evaluation runner.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    os.environ.setdefault("USE_LIVE_DATA", "false")
    os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
    os.environ.setdefault("OMP_NUM_THREADS", "1")

    _run_step("root-cause evaluation", "evals.runners.run_rca_eval")
    _run_step("RAG evaluation", "evals.runners.run_rag_eval", ["--mode", args.rag_mode])
    _run_step("workflow evaluation", "evals.runners.run_workflow_eval")
    _run_step("benchmarking", "evals.runners.run_benchmarks")
    _run_step("thesis exports", "evals.runners.export_thesis_results")

    print("[evals] All evaluation steps completed successfully.")


if __name__ == "__main__":
    main()
