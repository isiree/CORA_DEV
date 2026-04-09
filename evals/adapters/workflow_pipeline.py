from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import app as app_module
from src.g import bind_shared_scenario_run
from src.scenarios import build_scenario_run


@dataclass
class WorkflowCaseResult:
    test_id: str
    scenario_id: str
    user_input: str
    full_query: str
    detected_intent: str
    execution_mode: str
    final_output: str
    tools_used: list[str]
    steps: list[dict[str, Any]]
    sources: list[str]
    classifier_preview: str


class WorkflowEvalAdapter:
    """
    Executes the current agent-only mock query workflow for a single-turn investigation.
    """

    def __init__(self, team_filter: str = "All Teams") -> None:
        self.team_filter = team_filter

    def run_case(self, case: dict[str, Any]) -> WorkflowCaseResult:
        prompt = case["user_query"]
        full_query = f"For {self.team_filter}: {prompt}" if self.team_filter != "All Teams" else prompt

        scenario_run = build_scenario_run(case["scenario_id"])
        app_module._set_mode("Mock")
        app_module.DETERMINISTIC_MODE = False
        app_module._current_scenario_run = scenario_run
        app_module._conversation_history = []
        app_module.g.scenario_run = scenario_run

        detected_intent = "GENERAL"
        classifier_preview = app_module._fallback_classify_query_intent(prompt)
        agent = app_module._get_agent()
        scenario_context = app_module._build_scenario_context(scenario_run)
        with app_module._AGENT_CONTEXT_LOCK:
            with bind_shared_scenario_run(scenario_run):
                result = app_module._invoke_agent_query(
                    agent,
                    full_query,
                    chat_history=None,
                    scenario_context=scenario_context,
                )

        steps = app_module._serialize_steps(result.get("intermediate_steps", []))
        source_set: list[str] = []
        seen_sources: set[str] = set()
        for source in app_module._extract_sources(result.get("answer", "")):
            if source not in seen_sources:
                seen_sources.add(source)
                source_set.append(source)
        for step in steps:
            for source in step.get("sources", []):
                if source not in seen_sources:
                    seen_sources.add(source)
                    source_set.append(source)

        return WorkflowCaseResult(
            test_id=case["test_id"],
            scenario_id=case["scenario_id"],
            user_input=prompt,
            full_query=full_query,
            detected_intent=detected_intent,
            execution_mode="agent_only",
            final_output=result.get("answer", ""),
            tools_used=list(result.get("tools_used", [])),
            steps=steps,
            sources=source_set,
            classifier_preview=classifier_preview,
        )
