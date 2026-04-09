from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import app as app_module
from evals.adapters.rag_pipeline import RAGCaseResult
from evals.adapters.workflow_pipeline import WorkflowCaseResult, WorkflowEvalAdapter
from src.scenarios import build_scenario_run


@dataclass
class BenchmarkRunResult:
    variant: str
    family: str
    record: dict[str, Any]


class NoRAGWorkflowEvalAdapter(WorkflowEvalAdapter):
    """
    Benchmark variant that keeps the same app workflow but conceptually removes RAG.

    For the current fixed root-cause dataset, historical_tool usage is uncommon,
    so this variant is expected to remain close to the full system unless the
    dataset is expanded with policy/context-heavy prompts.
    """

    def run_case(self, case: dict[str, Any]) -> WorkflowCaseResult:
        result = super().run_case(case)
        result.execution_mode = f"{result.execution_mode}+no_rag"
        return result


class MinimalToolPathWorkflowAdapter:
    """
    Simplified baseline that answers root-cause questions using only the earliest
    pipeline-style evidence path instead of the full root-cause workflow.
    """

    def __init__(self, team_filter: str = "All Teams") -> None:
        self.team_filter = team_filter

    def run_case(self, case: dict[str, Any]) -> WorkflowCaseResult:
        prompt = case["user_query"]
        full_query = f"For {self.team_filter}: {prompt}" if self.team_filter != "All Teams" else prompt
        scenario_run = build_scenario_run(case["scenario_id"])
        detected_intent = app_module._fallback_classify_query_intent(prompt)
        team_id = app_module._extract_team_from_query(prompt, self.team_filter)
        result = app_module._build_mock_pipeline_result(scenario_run, team_id)
        steps = list(result.get("steps", []))
        first_step = steps[:1]
        first_tools = [step.get("tool") for step in first_step if step.get("tool")]
        first_sources = []
        seen: set[str] = set()
        for step in first_step:
            for source in step.get("sources", []):
                if source not in seen:
                    seen.add(source)
                    first_sources.append(source)
        return WorkflowCaseResult(
            test_id=case["test_id"],
            scenario_id=case["scenario_id"],
            user_input=prompt,
            full_query=full_query,
            detected_intent=detected_intent,
            execution_mode="minimal_tool_path",
            final_output=result.get("answer", ""),
            tools_used=first_tools or list(result.get("tools_used", []))[:1],
            steps=first_step,
            sources=first_sources or list(result.get("sources", []))[:1],
            classifier_preview=detected_intent,
        )


class KeywordRAGEvalBaselineAdapter:
    """
    Lightweight keyword-overlap retrieval baseline over the local markdown knowledge docs.
    """

    def __init__(self, top_k: int = 3, docs_root: str = "data/knowledge") -> None:
        self.top_k = top_k
        self.docs_root = Path(docs_root)
        self._docs = self._load_docs()

    def _load_docs(self) -> list[dict[str, str]]:
        docs: list[dict[str, str]] = []
        for path in sorted(self.docs_root.glob("*.md")):
            docs.append({"source": str(path), "content": path.read_text(encoding="utf-8")})
        return docs

    @staticmethod
    def _tokens(text: str) -> set[str]:
        return {token.lower() for token in str(text or "").replace("`", " ").split() if len(token) > 2}

    def _retrieve(self, query: str) -> list[dict[str, Any]]:
        query_tokens = self._tokens(query)
        scored = []
        for doc in self._docs:
            content = doc["content"]
            content_tokens = self._tokens(content)
            overlap = len(query_tokens & content_tokens)
            if overlap == 0:
                continue
            scored.append(
                {
                    "source": doc["source"],
                    "content": content,
                    "score": overlap,
                }
            )
        scored.sort(key=lambda item: (-item["score"], item["source"]))
        return scored[: self.top_k]

    def run_case(self, case: dict[str, Any]) -> RAGCaseResult:
        query = case["user_query"]
        rows = self._retrieve(query)
        retrieved_contexts = [row["content"] for row in rows]
        retrieved_sources = [row["source"] for row in rows]
        if rows:
            summary_lines = []
            for row in rows:
                preview = row["content"].strip().splitlines()
                preview_text = " ".join(preview[:4])[:450]
                summary_lines.append(f"- {preview_text} (Source: {row['source']})")
            final_output = "\n".join(summary_lines)
        else:
            final_output = "No relevant keyword-matching documents found."
        return RAGCaseResult(
            test_id=case["test_id"],
            scenario_id=case["scenario_id"],
            user_input=query,
            reference=case["reference_answer"],
            final_output=final_output,
            eval_response=final_output,
            retrieved_contexts=retrieved_contexts,
            retrieved_sources=retrieved_sources,
            raw_results=[
                {"content": row["content"], "source": row["source"], "score": row["score"]}
                for row in rows
            ],
        )
