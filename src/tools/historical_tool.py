"""
Historical Tool - RAG-based document search for policies and governance.

Searches through ABC Company's indexed documents (PDF, Markdown, text, DOCX)
including:
- Team subscriptions and budget allocations
- Cost governance policies
- FinOps frameworks
- Multicloud strategies
- AI automation best practices
"""

import os
import re
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv
from langchain_core.tools import tool
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq

from ..g import g
from ..scenarios import ScenarioRun
from ..utils.rag_retriever import get_retriever

load_dotenv()


class HistoricalTool:
    """
    Tool for searching historical documents and policies.
    Uses RAG with ChromaDB for semantic search.
    """

    _ROOT_CAUSE_RE = re.compile(
        r"\b(root cause|main reason|cost spike|unallocated cost|why did|what caused)\b",
        re.IGNORECASE,
    )
    _KNOWLEDGE_DOC_RE = re.compile(r"data/knowledge/doc\d+\.md$", re.IGNORECASE)
    _GENERIC_SOURCE_RE = re.compile(
        r"(cloud-finops-collaborative-real-time-cloud-financial-management|team_subscriptions\.pdf)",
        re.IGNORECASE,
    )
    _TITLE_CAUSE_MAP = {
        "Failed Terraform Destroy Jobs & Orphaned Resources": "failed cleanup of test or POC resources after a destroy job failure",
        "Cost Attribution Issues Due to Missing or Incorrect Tags": "a tagging regression that pushed real team spend into the unallocated bucket",
        "Autoscaler Not Scaling Down & Cost Impact": "an autoscaler configuration issue that scaled up but did not scale back down",
        "Avoiding Idle Cost from Forgotten Test/POC Environments": "a forgotten or abandoned test/POC environment left running after the work was finished",
        "Investigating Cost Spikes Caused by Application Behaviour": "an application configuration or behavior issue that triggered over-scaling, retries, or excess workload activity",
    }
    _SOURCE_CAUSE_MAP = {
        "data/knowledge/doc1.md": "failed cleanup of test or POC resources after a destroy job failure",
        "data/knowledge/doc2.md": "a tagging regression that pushed real team spend into the unallocated bucket",
        "data/knowledge/doc3.md": "an autoscaler configuration issue that scaled up but did not scale back down",
        "data/knowledge/doc4.md": "a forgotten or abandoned test/POC environment left running after the work was finished",
        "data/knowledge/doc5.md": "an application configuration or behavior issue that triggered over-scaling, retries, or excess workload activity",
    }
    _SOURCE_HINTS = {
        "data/knowledge/doc1.md": ("destroy", "cleanup", "terraform", "state lock", "orphan", "loadtest"),
        "data/knowledge/doc2.md": ("unallocated", "tag", "tagging", "team=legacy", "ownership", "misattributed"),
        "data/knowledge/doc3.md": ("autoscaler", "scale-down", "hpa", "instance count", "asg", "web-frontend"),
        "data/knowledge/doc4.md": ("poc", "proof-of-concept", "idle", "utilization", "analytics", "expires"),
        "data/knowledge/doc5.md": ("max_workers", "retry", "pod", "application", "workers", "release-api"),
    }

    def __init__(self, llm: Optional[ChatGroq] = None):
        self.retriever = get_retriever()
        self.llm = llm if llm is not None else ChatGroq(
            model=os.getenv("LLM_MODEL", "llama-3.3-70b-versatile"),
            temperature=0
        )

        self.summarization_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a retrieval-grounded assistant summarizing historical runbooks and governance documents.
You may receive both active scenario facts and retrieved historical guidance.

Rules:
- Treat scenario facts as the current investigation evidence.
- Treat retrieved documents as historical patterns and guidance that help label and explain the scenario.
- If scenario facts clearly align with a historical pattern, state the closest matching cause directly.
- Prefer exact, concrete evidence over generic background.
- Do not fill space with broad FinOps advice unless it directly supports the answer.
- Include specific details like numbers, team names, configuration values, deployment ids, and policy details when present.
- Always cite the source document for each finding.

Format your response as:
- Direct answer or closest supported pattern match (Source: document_name.ext)
- Scenario evidence that supports the match (Source: document_name.ext)
- Supporting evidence (Source: document_name.ext)
- Missing evidence, if needed (Source: document_name.ext)"""),
            ("human", """Query: {query}

Scenario Facts:
{scenario_facts}

Search Results:
{results}

Provide a concise, factual summary:""")
        ])

    def _is_root_cause_style_query(self, query: str) -> bool:
        return bool(self._ROOT_CAUSE_RE.search(str(query or "")))

    def _get_active_scenario_run(self) -> Optional[ScenarioRun]:
        scenario_run = getattr(g, "scenario_run", None)
        return scenario_run if isinstance(scenario_run, ScenarioRun) else None

    def _primary_team_id(self, scenario_run: ScenarioRun) -> Optional[str]:
        best_team = None
        best_delta = float("-inf")
        for team in scenario_run.cost_data.get("teams", []):
            daily = team.get("daily_costs", [])
            if not daily:
                continue
            values = [float(item.get("total_cost", 0.0) or 0.0) for item in daily]
            delta = max(values) - min(values)
            if delta > best_delta:
                best_delta = delta
                best_team = team.get("team_id")
        return best_team

    def _build_scenario_retrieval_hint(self, scenario_run: Optional[ScenarioRun]) -> str:
        if scenario_run is None:
            return ""

        lines = [f"active scenario {scenario_run.scenario_id}"]
        primary_team = self._primary_team_id(scenario_run)
        if primary_team:
            lines.append(f"primary affected team {primary_team}")

        unallocated = [float(item.get("total", 0.0) or 0.0) for item in scenario_run.cost_data.get("unallocated_cost", [])]
        if unallocated and (max(unallocated) - min(unallocated)) >= 100.0:
            lines.append("unallocated cost spike observed")

        for pipeline in scenario_run.pipeline_data.get("pipelines", [])[:4]:
            parts = [
                "pipeline",
                str(pipeline.get("name", "")),
                str(pipeline.get("status", "")),
                str(pipeline.get("started_at", ""))[:10],
            ]
            for job in pipeline.get("jobs", [])[:2]:
                parts.append(str(job.get("name", "")))
                parts.append(str(job.get("status", "")))
                log_excerpt = str(job.get("log_excerpt", "")).strip()
                if log_excerpt:
                    parts.append(log_excerpt)
            lines.append(" ".join(part for part in parts if part))

        primary_team_data = next(
            (team for team in scenario_run.cost_data.get("teams", []) if team.get("team_id") == primary_team),
            None,
        )
        resource_rows = (primary_team_data or {}).get("resources", [])
        for resource in resource_rows[:4]:
            tags = " ".join(f"{key}={value}" for key, value in sorted((resource.get("tags") or {}).items()))
            metrics = str(resource.get("metrics", "")).strip()
            parts = [
                "resource",
                str(resource.get("name", "")),
                str(resource.get("type", "")),
                tags,
                metrics,
            ]
            lines.append(" ".join(part for part in parts if part))

        return "\n".join(line.strip() for line in lines if line.strip())

    def _is_knowledge_doc_source(self, source: str) -> bool:
        return bool(self._KNOWLEDGE_DOC_RE.search(str(source or "")))

    def _source_sort_key(self, source: str) -> tuple[int, int]:
        source_text = str(source or "")
        return (
            0 if self._is_knowledge_doc_source(source_text) else 1,
            1 if self._GENERIC_SOURCE_RE.search(source_text) else 0,
        )

    def _prioritize_results(
        self,
        results: list[dict[str, Any]],
        query: str,
        scenario_hint: str,
        top_k: int,
    ) -> list[dict[str, Any]]:
        if not results:
            return []

        should_prefer_runbooks = self._is_root_cause_style_query(query) or bool(scenario_hint)
        if not should_prefer_runbooks:
            return results[:top_k]

        ranking_text = " ".join(part for part in [query, scenario_hint] if part)
        reranked = sorted(
            results,
            key=lambda row: (
                self._source_sort_key((row.get("metadata") or {}).get("source", "")),
                -(
                    self._text_overlap_score(ranking_text, row.get("content", ""))
                    + self._source_hint_bonus(str((row.get("metadata") or {}).get("source", "")), ranking_text)
                ),
                -float(row.get("hybrid_score", row.get("similarity", 0.0)) or 0.0),
                -float(row.get("keyword_score", 0.0) or 0.0),
                str((row.get("metadata") or {}).get("source", "")),
            ),
        )

        preferred = [row for row in reranked if self._is_knowledge_doc_source((row.get("metadata") or {}).get("source", ""))]
        if preferred:
            selected: list[dict[str, Any]] = []
            seen: set[tuple[str, str]] = set()
            for row in preferred:
                source = str((row.get("metadata") or {}).get("source", ""))
                page = "" if self._is_knowledge_doc_source(source) else str((row.get("metadata") or {}).get("page", ""))
                key = (source, page)
                if key in seen:
                    continue
                selected.append(row)
                seen.add(key)
                if len(selected) >= top_k:
                    break
            if len(selected) < top_k:
                for row in reranked:
                    source = str((row.get("metadata") or {}).get("source", ""))
                    page = "" if self._is_knowledge_doc_source(source) else str((row.get("metadata") or {}).get("page", ""))
                    key = (source, page)
                    if key in seen:
                        continue
                    selected.append(row)
                    seen.add(key)
                    if len(selected) >= top_k:
                        break
            return selected

        return reranked[:top_k]

    def _markdown_title(self, content: str) -> str:
        for line in str(content or "").splitlines():
            stripped = line.strip()
            if stripped.startswith("# "):
                return stripped[2:].strip()
        return "Historical guidance document"

    def _section_bullets(self, content: str, heading: str) -> list[str]:
        lines = str(content or "").splitlines()
        capture = False
        bullets: list[str] = []
        target = heading.strip().lower()
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("## "):
                capture = stripped[3:].strip().lower() == target
                continue
            if capture:
                if stripped.startswith("## "):
                    break
                if stripped.startswith("- "):
                    bullets.append(stripped[2:].strip())
        return bullets

    def _matching_bullets(self, bullets: list[str], reference_text: str, limit: int = 2) -> list[str]:
        tokens = {token for token in re.findall(r"[a-z0-9_=/-]+", str(reference_text or "").lower()) if len(token) > 2}
        scored = []
        for bullet in bullets:
            bullet_tokens = set(re.findall(r"[a-z0-9_=/-]+", bullet.lower()))
            overlap = len(tokens & bullet_tokens)
            scored.append((overlap, bullet))
        scored.sort(key=lambda item: (-item[0], item[1]))
        selected = [bullet for _, bullet in scored[:limit] if bullet]
        return selected or bullets[:limit]

    def _text_overlap_score(self, lhs: str, rhs: str) -> float:
        left = {token for token in re.findall(r"[a-z0-9_=/-]+", str(lhs or "").lower()) if len(token) > 2}
        right = {token for token in re.findall(r"[a-z0-9_=/-]+", str(rhs or "").lower()) if len(token) > 2}
        if not left or not right:
            return 0.0
        return len(left & right) / max(1, len(left))

    def _source_hint_bonus(self, source: str, ranking_text: str) -> float:
        hints = self._SOURCE_HINTS.get(str(source), ())
        if not hints:
            return 0.0
        lowered = str(ranking_text or "").lower()
        matches = sum(1 for hint in hints if hint in lowered)
        return min(matches * 0.2, 0.8)

    def _knowledge_doc_candidates(self, ranking_text: str, top_k: int) -> list[dict[str, Any]]:
        docs_root = Path("data/knowledge")
        candidates: list[dict[str, Any]] = []
        if not docs_root.exists():
            return candidates

        for path in sorted(docs_root.glob("doc*.md")):
            content = path.read_text(encoding="utf-8")
            score = self._text_overlap_score(ranking_text, content)
            if score <= 0.0:
                continue
            source = str(path)
            hybrid_score = score + 0.2 + self._source_hint_bonus(source, ranking_text)
            candidates.append(
                {
                    "content": content,
                    "metadata": {"source": source},
                    "similarity": round(score, 4),
                    "keyword_score": round(score, 4),
                    "hybrid_score": round(hybrid_score, 4),
                    "retrieval_strategy": "knowledge_keyword",
                }
            )

        candidates.sort(
            key=lambda row: (
                -float(row.get("hybrid_score", 0.0) or 0.0),
                str((row.get("metadata") or {}).get("source", "")),
            )
        )
        return candidates[:top_k]

    def _scenario_evidence_lines(self, scenario_run: ScenarioRun) -> list[str]:
        lines: list[str] = []
        for pipeline in scenario_run.pipeline_data.get("pipelines", [])[:3]:
            line = f"{pipeline.get('name', 'unknown pipeline')} {pipeline.get('status', 'unknown status')}"
            started_at = str(pipeline.get("started_at", "")).strip()
            if started_at:
                line += f" on {started_at[:10]}"
            for job in pipeline.get("jobs", [])[:2]:
                log_excerpt = str(job.get("log_excerpt", "")).strip()
                if log_excerpt:
                    line += f"; {job.get('name', 'job')} logged '{log_excerpt}'"
            lines.append(line)

        primary_team = self._primary_team_id(scenario_run)
        primary_team_data = next(
            (team for team in scenario_run.cost_data.get("teams", []) if team.get("team_id") == primary_team),
            None,
        )
        for resource in (primary_team_data or {}).get("resources", [])[:2]:
            metrics = str(resource.get("metrics", "")).strip()
            tags = ", ".join(f"{key}={value}" for key, value in sorted((resource.get("tags") or {}).items()))
            if metrics or tags:
                pieces = [str(resource.get("name", "unknown resource"))]
                if tags:
                    pieces.append(tags)
                if metrics:
                    pieces.append(metrics)
                lines.append("; ".join(pieces))
        return lines[:3]

    def _deterministic_pattern_summary(
        self,
        query: str,
        formatted_results: list[dict[str, Any]],
        scenario_run: Optional[ScenarioRun],
    ) -> Optional[str]:
        if not formatted_results:
            return None

        best = formatted_results[0]
        title = self._markdown_title(best.get("content", ""))
        source = best.get("source", "Unknown")
        cause = self._TITLE_CAUSE_MAP.get(title) or self._SOURCE_CAUSE_MAP.get(str(source), title.lower())
        reference_text = " ".join(
            part
            for part in [
                query,
                self._build_scenario_retrieval_hint(scenario_run),
                best.get("content", ""),
            ]
            if part
        )

        likely_causes = self._matching_bullets(self._section_bullets(best.get("content", ""), "Likely Causes"), reference_text, limit=2)
        when_to_use = self._matching_bullets(self._section_bullets(best.get("content", ""), "When to Use This"), reference_text, limit=1)
        scenario_evidence = self._scenario_evidence_lines(scenario_run) if scenario_run is not None else []
        generic_support = []
        if not likely_causes and not when_to_use:
            content_lines = [line.strip() for line in str(best.get("content", "")).splitlines() if line.strip()]
            generic_support = [line for line in content_lines[:4] if not line.startswith("#")][:1]

        lines = [f"- Closest historical match: {cause} (Source: {source})"]
        if scenario_evidence:
            lines.append(f"- Scenario evidence: {scenario_evidence[0]} (Source: {source})")
        if likely_causes:
            lines.append(f"- Supporting evidence: {likely_causes[0]} (Source: {source})")
        if when_to_use:
            lines.append(f"- Supporting evidence: {when_to_use[0]} (Source: {source})")
        if generic_support:
            lines.append(f"- Supporting evidence: {generic_support[0]} (Source: {source})")
        if len(scenario_evidence) > 1:
            lines.append(f"- Scenario evidence: {scenario_evidence[1]} (Source: {source})")
        return "\n".join(lines)

    def search(
        self,
        query: str,
        top_k: int = 3,
        summarize: bool = True
    ) -> dict:
        """
        Search documents and optionally summarize results.
        
        Args:
            query: Search query about policies, budgets, teams, etc.
            top_k: Number of documents to retrieve
            summarize: Whether to use LLM to summarize results
        
        Returns:
            Dictionary with raw results and optional summary
        """
        scenario_run = self._get_active_scenario_run()
        scenario_hint = self._build_scenario_retrieval_hint(scenario_run)
        search_query = query
        if scenario_hint:
            search_query = f"{query}\n\nScenario investigation facts:\n{scenario_hint}"

        should_use_runbook_boost = bool(scenario_hint or self._is_root_cause_style_query(query))
        retrieval_top_k = max(top_k * 3, top_k) if should_use_runbook_boost else top_k
        results = self.retriever.retrieve(search_query, top_k=retrieval_top_k)
        if should_use_runbook_boost:
            ranking_text = " ".join(part for part in [query, scenario_hint] if part)
            results.extend(self._knowledge_doc_candidates(ranking_text, top_k=retrieval_top_k))
        results = self._prioritize_results(results, query=query, scenario_hint=scenario_hint, top_k=top_k)
        
        if not results:
            return {
                "success": False,
                "message": "No relevant documents found for query.",
                "query": query,
                "results": [],
                "summary": None
            }
        
        # Format results for output
        formatted_results = []
        for i, r in enumerate(results, 1):
            formatted_results.append({
                "rank": i,
                "content": r["content"],
                "source": r["metadata"].get("source", "Unknown"),
                "page": r["metadata"].get("page", "N/A"),
                "similarity": r["similarity"],
                "keyword_score": r.get("keyword_score", 0.0),
                "hybrid_score": r.get("hybrid_score", r.get("similarity", 0.0)),
                "retrieval_strategy": r.get("retrieval_strategy", "dense"),
            })
        
        response = {
            "success": True,
            "query": query,
            "retrieval_query": search_query,
            "results": formatted_results,
            "summary": None
        }

        # Generate summary if requested
        if summarize:
            deterministic_summary = None
            if scenario_run is not None or self._is_root_cause_style_query(query):
                deterministic_summary = self._deterministic_pattern_summary(query, formatted_results, scenario_run)

            if deterministic_summary:
                sources = []
                seen = set()
                for r in formatted_results:
                    src = r.get("source")
                    if src and src not in seen:
                        seen.add(src)
                        sources.append(src)
                sources_block = "\n".join([f"- {s}" for s in sources]) if sources else "- Unknown"
                response["summary"] = f"{deterministic_summary}\n\nSources:\n{sources_block}"
            elif self.llm:
                results_text = "\n\n".join([
                    f"[Result {r['rank']}] (Source: {r['source']}, Strategy: {r['retrieval_strategy']}, Hybrid: {r['hybrid_score']}, Similarity: {r['similarity']}, Keyword: {r['keyword_score']})\n{r['content']}"
                    for r in formatted_results
                ])

                chain = self.summarization_prompt | self.llm
                summary_response = chain.invoke({
                    "query": query,
                    "scenario_facts": scenario_hint or "No active scenario facts available.",
                    "results": results_text
                })
                sources = []
                seen = set()
                for r in formatted_results:
                    src = r.get("source")
                    if src and src not in seen:
                        seen.add(src)
                        sources.append(src)
                sources_block = "\n".join([f"- {s}" for s in sources]) if sources else "- Unknown"
                response["summary"] = f"{summary_response.content.strip()}\n\nSources:\n{sources_block}"

        return response


# Create singleton instance
_historical_tool_instance: Optional[HistoricalTool] = None


def get_historical_tool() -> HistoricalTool:
    """Get or create global historical tool instance."""
    global _historical_tool_instance
    if _historical_tool_instance is None:
        _historical_tool_instance = HistoricalTool()
    return _historical_tool_instance


@tool
def historical_tool(query: str) -> str:
    """
    Search ABC Company's historical documents for policies, budgets, team information, and governance.
    
    Use this tool when you need information about:
    - Team budget allocations and spending limits
    - Cost governance policies and thresholds
    - Resource tagging requirements
    - FinOps maturity and practices
    - Multicloud strategy
    - AI/automation initiatives
    
    Args:
        query: Natural language query about company policies or historical data
    
    Returns:
        Summary of relevant information with source citations
    """
    tool_instance = get_historical_tool()
    result = tool_instance.search(query, top_k=3, summarize=True)
    
    if not result["success"]:
        return f"No relevant documents found for: {query}"
    
    # Return the summary for the agent
    if result["summary"]:
        return result["summary"]
    
    # Fallback to raw results if no summary
    output_parts = [f"Found {len(result['results'])} relevant documents:"]
    for r in result["results"]:
        output_parts.append(f"\n[{r['source']}] (Similarity: {r['similarity']})")
        output_parts.append(r["content"][:500] + "..." if len(r["content"]) > 500 else r["content"])
    
    return "\n".join(output_parts)
