from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from src.g import bind_shared_scenario_run
from src.scenarios import build_scenario_run
from src.tools.historical_tool import HistoricalTool


_SOURCES_BLOCK_RE = re.compile(r"\n+Sources:\s*\n(?:-\s+.+\n?)*\s*$", re.IGNORECASE)


@dataclass
class RAGCaseResult:
    test_id: str
    scenario_id: str
    user_input: str
    reference: str
    final_output: str
    eval_response: str
    retrieved_contexts: list[str]
    retrieved_sources: list[str]
    raw_results: list[dict[str, Any]]


def _strip_sources_block(text: str) -> str:
    cleaned = _SOURCES_BLOCK_RE.sub("", str(text or "")).strip()
    return cleaned or str(text or "").strip()


def _render_source_label(result: dict[str, Any]) -> str:
    source = str(result.get("source") or "Unknown").strip()
    page = result.get("page", "N/A")
    if page in (None, "", "N/A"):
        return source
    return f"{source}#page={page}"


def _fallback_response(results: list[dict[str, Any]]) -> str:
    if not results:
        return "No relevant documents found."

    lines = []
    for result in results:
        source = _render_source_label(result)
        content = str(result.get("content") or "").strip()
        preview = content[:400] + ("..." if len(content) > 400 else "")
        lines.append(f"- {preview} (Source: {source})")
    return "\n".join(lines)


class HistoricalRAGEvalAdapter:
    """
    Thin adapter that exposes the existing historical RAG path in a RAGAS-friendly shape.
    """

    def __init__(
        self,
        tool: HistoricalTool | None = None,
        top_k: int = 3,
        summarize: bool = True,
    ) -> None:
        self.tool = tool or HistoricalTool()
        self.top_k = top_k
        self.summarize = summarize

    def run_case(self, case: dict[str, Any]) -> RAGCaseResult:
        query = case["user_query"]
        scenario_run = build_scenario_run(case["scenario_id"])
        with bind_shared_scenario_run(scenario_run):
            result = self.tool.search(query, top_k=self.top_k, summarize=self.summarize)
        raw_results = list(result.get("results") or [])

        final_output = str(result.get("summary") or _fallback_response(raw_results)).strip()
        eval_response = _strip_sources_block(final_output)
        retrieved_contexts = [str(item.get("content") or "").strip() for item in raw_results]
        retrieved_sources = [_render_source_label(item) for item in raw_results]

        return RAGCaseResult(
            test_id=case["test_id"],
            scenario_id=case["scenario_id"],
            user_input=query,
            reference=case["reference_answer"],
            final_output=final_output,
            eval_response=eval_response,
            retrieved_contexts=retrieved_contexts,
            retrieved_sources=retrieved_sources,
            raw_results=raw_results,
        )
