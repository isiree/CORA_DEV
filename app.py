"""
React UI backend for CORA (Cloud Optimization & Resource Advisor).

Uses only Python standard library HTTP serving to avoid introducing new
runtime dependencies while preserving existing backend agent functionality.
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import re
from typing import Any, Optional
from urllib.parse import urlparse

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage

from src.scenarios import ScenarioRun, build_scenario_run, SCENARIO_IDS
from src.g import g

ROOT_DIR = Path(__file__).parent.resolve()
TEMPLATES_DIR = ROOT_DIR / "templates"
STATIC_DIR = ROOT_DIR / "static"

_AGENT_LOCK = threading.Lock()
_AGENT_INSTANCE: Any = None
_current_scenario_run: Optional[ScenarioRun] = None

TEAM_OPTIONS = ["All Teams", "ci-team", "release-team", "cloudops-team"]
EXAMPLE_QUERIES = [
    "What is the Release Team's monthly budget?",
    "Is anyone over budget this month?",
    "Why did costs spike last week?",
    "List CI team resources",
    "Recent infrastructure changes for cloudops-team",
]

TOOL_INFO_FALLBACK = [
    {
        "name": "historical_tool",
        "description": "Search governance documents for policies, budgets, and team information.",
    },
    {
        "name": "cost_api_tool",
        "description": "Get current spending, budget status, and cost/resource breakdown.",
    },
    {
        "name": "pipeline_tool",
        "description": "Analyze deployment history, infrastructure changes, and cost impact.",
    },
]

TEAM_LABELS = {
    "ci-team": "CI Team",
    "release-team": "Release Team",
    "cloudops-team": "CloudOps Team",
}


def _get_mode() -> str:
    return "Live" if os.getenv("USE_LIVE_DATA", "false").lower() == "true" else "Mock"


def _reset_providers() -> None:
    """Reset provider and tool singletons to enforce mode changes."""
    try:
        import src.providers
        import src.tools.cost_api_tool
        import src.tools.pipeline_tool

        if hasattr(src.providers, "_cost_provider_instance"):
            src.providers._cost_provider_instance = None

        if hasattr(src.tools.cost_api_tool, "_cost_tool_instance"):
            src.tools.cost_api_tool._cost_tool_instance = None

        if hasattr(src.tools.pipeline_tool, "_pipeline_tool_instance"):
            src.tools.pipeline_tool._pipeline_tool_instance = None
    except Exception:
        pass


def _reset_runtime_state() -> None:
    """Reset cached runtime state when mode or scenario changes."""
    _reset_providers()
    try:
        from src.utils.cache_manager import get_cache

        get_cache().clear()
    except Exception:
        pass


def _reset_agent() -> None:
    global _AGENT_INSTANCE
    with _AGENT_LOCK:
        _AGENT_INSTANCE = None


def _set_mode(new_mode: str) -> str:
    normalized = "Live" if str(new_mode).lower() == "live" else "Mock"
    os.environ["USE_LIVE_DATA"] = "true" if normalized == "Live" else "false"
    _reset_runtime_state()
    _reset_agent()
    # Reset scenario on mode change
    global _current_scenario_run
    _current_scenario_run = None
    return normalized


def _get_agent() -> Any:
    global _AGENT_INSTANCE
    with _AGENT_LOCK:
        if _AGENT_INSTANCE is None:
            # Lazy import so the UI server can start even if heavy LLM deps are slow.
            from src.agent import CloudCostAgent

            _AGENT_INSTANCE = CloudCostAgent(verbose=False)
        return _AGENT_INSTANCE


def _serialize_steps(intermediate_steps: list[Any]) -> list[dict[str, Any]]:
    serialized: list[dict[str, Any]] = []

    steps: list[Any] = intermediate_steps[:5] if isinstance(intermediate_steps, list) else []
    for idx, step in enumerate(steps, start=1):
        try:
            action, observation = step
        except Exception:
            continue

        tool_name = getattr(action, "tool", "Unknown")
        tool_input = getattr(action, "tool_input", {})
        obs_text = str(observation)
        obs_preview = str(obs_text)[:800] + ("... [truncated]" if len(str(obs_text)) > 800 else "")
        sources = _extract_sources(obs_text)

        serialized.append(
            {
                "number": idx,
                "tool": tool_name,
                "query": str(tool_input),
                "result_preview": obs_preview,
                "sources": sources,
            }
        )

    return serialized


def _extract_sources(text: str) -> list[str]:
    if not text:
        return []

    sources: list[str] = []

    # Matches "(Source: something)" or "Source: something"
    for match in re.findall(r"Source:\s*([^\)\n]+)", text, flags=re.IGNORECASE):
        sources.append(match.strip())

    # Matches "[path/to/doc]" lines used in fallback formatting
    for match in re.findall(r"^\[([^\]]+)]", text, flags=re.MULTILINE):
        sources.append(match.strip())

    # Matches "- source" lines under a "Sources:" block
    for match in re.findall(r"^-\s+(.+)$", text, flags=re.MULTILINE):
        sources.append(match.strip())

    # De-dupe while preserving order
    seen = set()
    unique = []
    for s in sources:
        if s and s not in seen:
            seen.add(s)
            unique.append(s)

    return unique


def _json_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=True).encode("utf-8")


def _guess_content_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".css":
        return "text/css; charset=utf-8"
    if suffix == ".js":
        return "application/javascript; charset=utf-8"
    if suffix == ".html":
        return "text/html; charset=utf-8"
    return "application/octet-stream"


def _normalize_team_name(team_name: str) -> str:
    return str(team_name).strip().lower().replace(" ", "-").replace("_", "-")


def _team_label(team_id: str) -> str:
    return TEAM_LABELS.get(team_id, team_id.replace("-", " ").title())


def _extract_team_from_query(prompt: str, team_filter: str = "") -> Optional[str]:
    normalized_filter = _normalize_team_name(team_filter)
    if normalized_filter in TEAM_LABELS:
        return normalized_filter

    prompt_lower = prompt.lower()
    for team_id in TEAM_LABELS:
        variants = {team_id, team_id.replace("-", " "), team_id.replace("-", "_"), _team_label(team_id).lower()}
        if any(variant in prompt_lower for variant in variants):
            return team_id
    return None


def _scenario_team_data(scenario_run: ScenarioRun, team_id: str) -> Optional[dict[str, Any]]:
    return next((team for team in scenario_run.cost_data.get("teams", []) if team.get("team_id") == team_id), None)


def _scenario_team_spike_stats(scenario_run: ScenarioRun, team_id: str) -> dict[str, float]:
    team = _scenario_team_data(scenario_run, team_id) or {}
    daily_costs = team.get("daily_costs", [])
    total = sum(float(day.get("total_cost", 0)) for day in daily_costs)
    baseline = daily_costs[: min(7, len(daily_costs))]
    recent = daily_costs[-7:] if daily_costs else []
    baseline_avg = sum(float(day.get("total_cost", 0)) for day in baseline) / len(baseline) if baseline else 0.0
    recent_avg = sum(float(day.get("total_cost", 0)) for day in recent) / len(recent) if recent else 0.0
    return {
        "total": total,
        "baseline_avg": baseline_avg,
        "recent_avg": recent_avg,
        "delta": recent_avg - baseline_avg,
    }


def _format_currency(amount: float) -> str:
    return f"${amount:,.2f}"


def _format_date(date_value: str) -> str:
    if not date_value:
        return "Unknown date"
    cleaned = str(date_value).replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(cleaned).strftime("%B %d, %Y").replace(" 0", " ")
    except ValueError:
        try:
            return datetime.strptime(str(date_value), "%Y-%m-%d").strftime("%B %d, %Y").replace(" 0", " ")
        except ValueError:
            return str(date_value)


def _scenario_team_pipelines(scenario_run: ScenarioRun, team_id: str) -> list[dict[str, Any]]:
    pipelines = [p for p in scenario_run.pipeline_data.get("pipelines", []) if p.get("team_id") == team_id]
    return sorted(pipelines, key=lambda item: item.get("started_at", item.get("created_at", "")))


def _scenario_failed_cleanup_events(scenario_run: ScenarioRun, team_id: str) -> list[dict[str, str]]:
    events: list[dict[str, str]] = []
    for pipeline in _scenario_team_pipelines(scenario_run, team_id):
        for job in pipeline.get("jobs", []):
            job_name = str(job.get("name", "")).lower()
            if job.get("status") == "failed" and any(keyword in job_name for keyword in ("destroy", "cleanup")):
                events.append(
                    {
                        "pipeline_name": pipeline.get("name", pipeline.get("pipeline_id", "unknown")),
                        "date": _format_date(pipeline.get("started_at", "")),
                        "error": job.get("log_excerpt", "No error excerpt available."),
                    }
                )
    return events


def _mock_step(number: int, tool: str, query: str, result_preview: str, sources: list[str]) -> dict[str, Any]:
    return {
        "number": number,
        "tool": tool,
        "query": query,
        "result_preview": result_preview,
        "sources": sources,
    }


def _mock_query_result(answer: str, tools_used: list[str], sources: list[str], steps: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "answer": answer,
        "tools_used": tools_used,
        "steps": steps,
        "sources": sources,
    }


def _build_mock_responsibility_result(scenario_run: ScenarioRun) -> dict[str, Any]:
    scenario_id = scenario_run.scenario_id
    source_cost = [f"{scenario_id} mock cost data"]
    source_pipeline = [f"{scenario_id} mock pipeline data"]

    if scenario_id == "scenario_1_vm_destroy":
        stats = _scenario_team_spike_stats(scenario_run, "ci-team")
        failures = _scenario_failed_cleanup_events(scenario_run, "ci-team")
        failure_dates = ", ".join(event["date"] for event in failures)
        answer = (
            f"The CI Team is responsible for the Scenario 1 cost spike. Its daily spend rises from "
            f"{_format_currency(stats['baseline_avg'])}/day before January 10, 2025 to "
            f"{_format_currency(stats['recent_avg'])}/day afterward. The key evidence is the "
            f"`deploy-loadtest` environment deployment followed by failed `destroy-loadtest` runs on "
            f"{failure_dates}. Those failed `terraform-destroy` jobs hit `Error acquiring the state lock`, "
            f"so the load-test resources were left running."
        )
        steps = [
            _mock_step(1, "cost_api_tool", "all teams summary", "Primary driver: CI Team based on scenario cost spike.", source_cost),
            _mock_step(2, "pipeline_tool", "ci-team cost impact", "Failed destroy-loadtest pipelines left load-test resources running.", source_pipeline),
        ]
        return _mock_query_result(answer, ["cost_api_tool", "pipeline_tool"], source_cost + source_pipeline, steps)

    if scenario_id == "scenario_2_tagging":
        answer = (
            "The Release Team is the team behind the Scenario 2 increase, but the spend appears as "
            "unallocated because the release deployment introduced bad tagging. `deploy-release-prod` on "
            "January 14, 2025 updated tags incorrectly, leaving one resource tagged `team=legacy` and another "
            "missing team tags entirely."
        )
        steps = [
            _mock_step(1, "cost_api_tool", "subscription ownership review", "Unallocated spend increases sharply after January 15, 2025.", source_cost),
            _mock_step(2, "pipeline_tool", "release-team deployment review", "deploy-release-prod introduced the tagging error.", source_pipeline),
        ]
        return _mock_query_result(answer, ["cost_api_tool", "pipeline_tool"], source_cost + source_pipeline, steps)

    if scenario_id == "scenario_3_autoscaler":
        answer = (
            "The Release Team is responsible for the Scenario 3 spike. Release spend jumps on January 10, 2025 "
            "and stays elevated because the web frontend autoscaler scaled out and never scaled back down."
        )
        steps = [
            _mock_step(1, "cost_api_tool", "all teams summary", "Release Team has the sustained post-January 10 spike.", source_cost),
            _mock_step(2, "pipeline_tool", "release-team deployment review", "Autoscaler config change preceded the sustained scale-out.", source_pipeline),
        ]
        return _mock_query_result(answer, ["cost_api_tool", "pipeline_tool"], source_cost + source_pipeline, steps)

    if scenario_id == "scenario_4_forgotten_poc":
        answer = (
            "The CloudOps Team is responsible for the Scenario 4 spike. The root cause is a forgotten `poc-analytics` "
            "environment that stayed up after January 14, 2025. The `poc-dashboard` pipeline is a decoy because it was "
            "destroyed successfully."
        )
        steps = [
            _mock_step(1, "cost_api_tool", "all teams summary", "CloudOps Team has the post-January 15 increase.", source_cost),
            _mock_step(2, "pipeline_tool", "cloudops-team deployment review", "deploy-poc-analytics remained active while destroy-poc-dashboard succeeded.", source_pipeline),
        ]
        return _mock_query_result(answer, ["cost_api_tool", "pipeline_tool"], source_cost + source_pipeline, steps)

    if scenario_id == "scenario_5_app_misconfig":
        answer = (
            "The Release Team is responsible for the Scenario 5 spike. The increase follows the January 19, 2025 "
            "`deploy-release-api` rollout, where the app config set `MAX_WORKERS=500`. That drove a pod-count surge, "
            "so this is an application misconfiguration rather than a CloudOps infrastructure change."
        )
        steps = [
            _mock_step(1, "cost_api_tool", "all teams summary", "Release Team spikes after January 20, 2025.", source_cost),
            _mock_step(2, "pipeline_tool", "release-team deployment review", "deploy-release-api changed application behavior and drove excess scaling.", source_pipeline),
        ]
        return _mock_query_result(answer, ["cost_api_tool", "pipeline_tool"], source_cost + source_pipeline, steps)

    answer = (
        "The Legacy Mock scenario uses the original hard-coded dataset, where the Release Team has the highest mock "
        "spend. Use the numbered scenarios for deterministic root-cause investigations."
    )
    steps = [_mock_step(1, "cost_api_tool", "legacy all teams summary", "Legacy mock data points to Release Team.", source_cost)]
    return _mock_query_result(answer, ["cost_api_tool"], source_cost, steps)


def _build_mock_pipeline_result(scenario_run: ScenarioRun, team_id: Optional[str]) -> dict[str, Any]:
    scenario_id = scenario_run.scenario_id
    team_id = team_id or "ci-team"
    source_pipeline = [f"{scenario_id} mock pipeline data"]
    source_cost = [f"{scenario_id} mock cost data"]

    if scenario_id == "scenario_1_vm_destroy":
        answer = (
            "The cost increase is driven by the CI Team's load-test lifecycle, not generic deployment volume. "
            "`deploy-loadtest` created the environment on January 9, 2025. Then `destroy-loadtest` failed on "
            "January 10, 11, and 12, 2025. The failed job is `terraform-destroy`, and the log excerpt says "
            "`Error acquiring the state lock`. `deploy-feature-x` is only a decoy unit-test failure and is not the cost driver."
        )
        steps = [
            _mock_step(1, "pipeline_tool", "ci-team deployment history", "deploy-loadtest was followed by repeated destroy-loadtest failures.", source_pipeline),
            _mock_step(2, "cost_api_tool", "ci-team spend trend", "CI spend rises immediately after the failed cleanup sequence.", source_cost),
        ]
        return _mock_query_result(answer, ["pipeline_tool", "cost_api_tool"], source_pipeline + source_cost, steps)

    if scenario_id == "scenario_2_tagging":
        answer = (
            "The key pipeline activity is `deploy-release-prod` on January 14, 2025. Its logs show `Updating tags... team=legacy`, "
            "which matches the mistagged Release Team resources and explains why the new spend shows up as unallocated."
        )
        steps = [_mock_step(1, "pipeline_tool", "release-team deployment history", "deploy-release-prod introduced the bad tags.", source_pipeline)]
        return _mock_query_result(answer, ["pipeline_tool"], source_pipeline, steps)

    if scenario_id == "scenario_3_autoscaler":
        answer = (
            "The pivotal activity is `update-web-autoscaler` on January 9, 2025. The rollout changed autoscaler behavior, "
            "and the `web-frontend-asg` resource then scaled from 4 to 12 instances on January 10 without any recorded scale-down."
        )
        steps = [_mock_step(1, "pipeline_tool", "release-team deployment history", "Autoscaler update preceded the sustained scale-out.", source_pipeline)]
        return _mock_query_result(answer, ["pipeline_tool"], source_pipeline, steps)

    if scenario_id == "scenario_4_forgotten_poc":
        answer = (
            "The relevant pipeline is `deploy-poc-analytics` on January 14, 2025. It created the forgotten POC environment that stayed running. "
            "`deploy-poc-dashboard` and `destroy-poc-dashboard` are decoys because the dashboard environment was torn down successfully."
        )
        steps = [_mock_step(1, "pipeline_tool", "cloudops-team deployment history", "deploy-poc-analytics remained active while the dashboard POC was cleaned up.", source_pipeline)]
        return _mock_query_result(answer, ["pipeline_tool"], source_pipeline, steps)

    if scenario_id == "scenario_5_app_misconfig":
        answer = (
            "The important rollout is `deploy-release-api` on January 19, 2025. Its deployment log includes `Config update: MAX_WORKERS=500`, "
            "which lines up with the later pod-count jump and retry storm in the application metrics."
        )
        steps = [_mock_step(1, "pipeline_tool", "release-team deployment history", "deploy-release-api changed runtime behavior and drove scale-out.", source_pipeline)]
        return _mock_query_result(answer, ["pipeline_tool"], source_pipeline, steps)

    answer = (
        f"The { _team_label(team_id) } Legacy Mock pipelines are generic hard-coded examples rather than scenario-specific root-cause evidence."
    )
    steps = [_mock_step(1, "pipeline_tool", f"{team_id} deployment history", "Legacy mock pipeline data only.", source_pipeline)]
    return _mock_query_result(answer, ["pipeline_tool"], source_pipeline, steps)


def _build_mock_resource_result(scenario_run: ScenarioRun, team_id: Optional[str]) -> dict[str, Any]:
    from src.providers.mock_cost_provider import MockCostDataProvider

    scenario_id = scenario_run.scenario_id
    team_id = team_id or "ci-team"
    provider = MockCostDataProvider()
    source_cost = [f"{scenario_id} mock resource data"]

    if scenario_id == "scenario_1_vm_destroy" and team_id == "ci-team":
        resource_result = provider.get_team_resources("ci-team")
        orphaned = resource_result.get("orphaned_resources", [])
        idle = resource_result.get("idle_resources", [])
        orphaned_line = ""
        if orphaned:
            top = orphaned[0]
            orphaned_line = (
                f"`{top['resource_id']}` is explicitly orphaned: {top['resource_type']}, "
                f"{top['days_idle']} idle days, about {_format_currency(top['monthly_cost'])}/month, "
                f"reason: {top['reason_orphaned']}"
            )
        idle_line = ""
        if len(idle) > 1:
            next_idle = idle[1]
            idle_line = (
                f" `{next_idle['resource_id']}` also looks idle: {next_idle['resource_type']}, "
                f"{next_idle['days_idle']} idle days, about {_format_currency(next_idle['monthly_cost'])}/month."
            )
        util = resource_result.get("resource_utilization", {})
        answer = (
            f"The CI Team's most suspicious resources are the leftover load-test VMs. {orphaned_line}{idle_line} "
            f"Scenario utilization is also very low at {util.get('average_cpu_percent', 0)}% CPU and "
            f"{util.get('average_memory_percent', 0)}% memory, which supports the orphaned/idle diagnosis."
        )
        steps = [_mock_step(1, "cost_api_tool", "ci-team resource discovery", "res-loadtest-1 and res-loadtest-2 stand out as idle/orphaned load-test VMs.", source_cost)]
        return _mock_query_result(answer, ["cost_api_tool"], source_cost, steps)

    if scenario_id == "scenario_2_tagging":
        answer = (
            "Scenario 2 is primarily a tagging and ownership problem rather than an idle-resource problem. The critical Release Team resources are "
            "`res-db-prod`, which is tagged `team=legacy`, and `res-api-1`, which is missing team tags altogether."
        )
        steps = [_mock_step(1, "cost_api_tool", "release-team resource review", "Mistagged and untagged Release Team resources explain the unallocated spend.", source_cost)]
        return _mock_query_result(answer, ["cost_api_tool"], source_cost, steps)

    if scenario_id == "scenario_3_autoscaler":
        answer = (
            "The main problematic resource is `web-frontend-asg` / `res-web-frontend`. Its metrics show instance count rising from 4 to 12 on "
            "January 10, 2025 with no scale-down events logged. `user-service` is not the root cause because it scaled back down correctly."
        )
        steps = [_mock_step(1, "cost_api_tool", "release-team resource review", "web-frontend-asg stayed scaled out; user-service recovered.", source_cost)]
        return _mock_query_result(answer, ["cost_api_tool"], source_cost, steps)

    if scenario_id == "scenario_4_forgotten_poc":
        answer = (
            "The forgotten POC resources are `poc-analytics-vm-1` and `poc-analytics-db`. The VM metrics show CPU utilization near 0% after "
            "January 15, 2025, which is exactly the kind of abandoned footprint the scenario is meant to surface."
        )
        steps = [_mock_step(1, "cost_api_tool", "cloudops-team resource review", "poc-analytics resources remained active with negligible utilization.", source_cost)]
        return _mock_query_result(answer, ["cost_api_tool"], source_cost, steps)

    if scenario_id == "scenario_5_app_misconfig":
        answer = (
            "The key resource signal is the Release Team's `release-api` / `rel-api-pods` deployment. Its metrics show pod count jumping from 5 to 50 "
            "on January 19, 2025 with repeated `failed to process message, retrying` logs. That is over-scaling from app behavior, not an orphaned resource."
        )
        steps = [_mock_step(1, "cost_api_tool", "release-team resource review", "release-api pod count jump explains the excess spend.", source_cost)]
        return _mock_query_result(answer, ["cost_api_tool"], source_cost, steps)

    answer = f"No scenario-specific orphaned or idle resource summary is defined for {scenario_id}."
    steps = [_mock_step(1, "cost_api_tool", f"{team_id} resource review", "No scenario-specific resource summary available.", source_cost)]
    return _mock_query_result(answer, ["cost_api_tool"], source_cost, steps)


def _build_mock_root_cause_result(scenario_run: ScenarioRun, team_id: Optional[str]) -> dict[str, Any]:
    scenario_id = scenario_run.scenario_id
    source_cost = [f"{scenario_id} mock cost data"]
    source_pipeline = [f"{scenario_id} mock pipeline data"]

    if scenario_id == "scenario_1_vm_destroy":
        stats = _scenario_team_spike_stats(scenario_run, "ci-team")
        answer = (
            "The main reason for the CI Team cost spike is failed cleanup of the load-test environment. "
            "`deploy-loadtest` created the environment on January 9, 2025, but `destroy-loadtest` failed on "
            "January 10, 11, and 12 because `terraform-destroy` hit `Error acquiring the state lock`. "
            f"That left the load-test VMs running and pushed daily spend from {_format_currency(stats['baseline_avg'])}/day "
            f"to {_format_currency(stats['recent_avg'])}/day."
        )
        steps = [
            _mock_step(1, "pipeline_tool", "ci-team root cause review", "Repeated destroy-loadtest failures left the environment running.", source_pipeline),
            _mock_step(2, "cost_api_tool", "ci-team spend delta", "CI spend increases immediately after the failed cleanup attempts.", source_cost),
        ]
        return _mock_query_result(answer, ["pipeline_tool", "cost_api_tool"], source_pipeline + source_cost, steps)

    if scenario_id == "scenario_2_tagging":
        answer = (
            "The main reason is a tagging regression, not new organic usage. `deploy-release-prod` on January 14, 2025 "
            "updated tags incorrectly, including `team=legacy`, so Release Team spend was misattributed into the unallocated bucket."
        )
        steps = [
            _mock_step(1, "pipeline_tool", "release-team root cause review", "deploy-release-prod introduced incorrect team tags.", source_pipeline),
            _mock_step(2, "cost_api_tool", "unallocated spend trend", "Unallocated spend jumps immediately after the tagging change.", source_cost),
        ]
        return _mock_query_result(answer, ["pipeline_tool", "cost_api_tool"], source_pipeline + source_cost, steps)

    if scenario_id == "scenario_3_autoscaler":
        answer = (
            "The main reason is a bad autoscaler configuration change. `update-web-autoscaler` on January 9, 2025 "
            "was followed by `web-frontend-asg` scaling from 4 to 12 instances on January 10 with no scale-down, creating sustained excess compute cost."
        )
        steps = [
            _mock_step(1, "pipeline_tool", "release-team root cause review", "Autoscaler update preceded the permanent scale-out.", source_pipeline),
            _mock_step(2, "cost_api_tool", "release-team compute trend", "Release compute spend stays elevated after the scale-out.", source_cost),
        ]
        return _mock_query_result(answer, ["pipeline_tool", "cost_api_tool"], source_pipeline + source_cost, steps)

    if scenario_id == "scenario_4_forgotten_poc":
        answer = (
            "The main reason is a forgotten proof-of-concept environment. `deploy-poc-analytics` created resources that remained active after January 14, 2025, "
            "while the dashboard POC was actually destroyed successfully. The spike comes from abandoned analytics resources, not the decoy dashboard workflow."
        )
        steps = [
            _mock_step(1, "pipeline_tool", "cloudops-team root cause review", "deploy-poc-analytics remained active after the POC should have ended.", source_pipeline),
            _mock_step(2, "cost_api_tool", "cloudops-team idle footprint", "POC analytics resources show negligible utilization but continued spend.", source_cost),
        ]
        return _mock_query_result(answer, ["pipeline_tool", "cost_api_tool"], source_pipeline + source_cost, steps)

    if scenario_id == "scenario_5_app_misconfig":
        answer = (
            "The main reason is an application configuration mistake in `deploy-release-api`. The January 19, 2025 rollout set `MAX_WORKERS=500`, "
            "which triggered a pod-count surge and retry storm. This is an app-driven scaling problem rather than an orphaned infrastructure issue."
        )
        steps = [
            _mock_step(1, "pipeline_tool", "release-team root cause review", "deploy-release-api changed runtime behavior and triggered excess scaling.", source_pipeline),
            _mock_step(2, "cost_api_tool", "release-team pod scaling review", "Release API pod count and compute spend jump after the config rollout.", source_cost),
        ]
        return _mock_query_result(answer, ["pipeline_tool", "cost_api_tool"], source_pipeline + source_cost, steps)

    answer = f"No scenario-specific root cause summary is defined for {scenario_id}."
    steps = [_mock_step(1, "cost_api_tool", f"{team_id or 'all-teams'} root cause review", "No scenario-specific root cause summary available.", source_cost)]
    return _mock_query_result(answer, ["cost_api_tool"], source_cost, steps)


def _build_mock_remediation_result(scenario_run: ScenarioRun, team_id: Optional[str]) -> dict[str, Any]:
    scenario_id = scenario_run.scenario_id
    team_id = team_id or "ci-team"
    source_cost = [f"{scenario_id} mock cost data"]
    source_pipeline = [f"{scenario_id} mock pipeline data"]

    if scenario_id == "scenario_1_vm_destroy":
        answer = (
            "Recommended remediation for the CI Team is to clear the Terraform state lock, rerun `destroy-loadtest`, and manually decommission any leftover "
            "`res-loadtest-*` VMs that remain. To prevent recurrence, add destroy-job retry/force-unlock handling and alert when load-test resources survive after a failed cleanup pipeline."
        )
        steps = [
            _mock_step(1, "pipeline_tool", "ci-team remediation review", "Failed destroy-loadtest jobs point to Terraform state-lock handling as the first fix.", source_pipeline),
            _mock_step(2, "cost_api_tool", "ci-team leftover resource cleanup", "res-loadtest-1 and res-loadtest-2 are the immediate cost-saving cleanup targets.", source_cost),
        ]
        return _mock_query_result(answer, ["pipeline_tool", "cost_api_tool"], source_pipeline + source_cost, steps)

    if scenario_id == "scenario_2_tagging":
        answer = (
            "Recommended remediation is to correct the bad team tags on the affected Release Team resources, backfill missing ownership metadata, and add tag validation in the IaC pipeline so "
            "`team=legacy`-style regressions are blocked before deployment. A short-term ownership review should also reassign the currently unallocated spend."
        )
        steps = [
            _mock_step(1, "pipeline_tool", "release-team remediation review", "deploy-release-prod needs tag validation and change controls.", source_pipeline),
            _mock_step(2, "cost_api_tool", "unallocated spend reassignment", "Mistagged resources should be reattributed to restore accurate cost ownership.", source_cost),
        ]
        return _mock_query_result(answer, ["pipeline_tool", "cost_api_tool"], source_pipeline + source_cost, steps)

    if scenario_id == "scenario_3_autoscaler":
        answer = (
            "Recommended remediation is to roll back or correct the autoscaler thresholds, force a scale-in of the excess `web-frontend-asg` instances, and add monitoring for scale-out without matching scale-down events. "
            "That addresses both the immediate compute overrun and the detection gap."
        )
        steps = [
            _mock_step(1, "pipeline_tool", "release-team remediation review", "Autoscaler config should be rolled back or corrected first.", source_pipeline),
            _mock_step(2, "cost_api_tool", "release-team excess instance review", "Scaled-out frontend instances are the immediate savings target.", source_cost),
        ]
        return _mock_query_result(answer, ["pipeline_tool", "cost_api_tool"], source_pipeline + source_cost, steps)

    if scenario_id == "scenario_4_forgotten_poc":
        answer = (
            "Recommended remediation is to shut down and delete the forgotten `poc-analytics` resources, add expiration tags and owner metadata to all POC environments, and enforce automatic cleanup or review for non-production workloads after the expected end date."
        )
        steps = [
            _mock_step(1, "pipeline_tool", "cloudops-team remediation review", "POC lifecycle controls are missing for deploy-poc-analytics.", source_pipeline),
            _mock_step(2, "cost_api_tool", "cloudops-team abandoned POC cleanup", "Idle analytics resources are the immediate cleanup target.", source_cost),
        ]
        return _mock_query_result(answer, ["pipeline_tool", "cost_api_tool"], source_pipeline + source_cost, steps)

    if scenario_id == "scenario_5_app_misconfig":
        answer = (
            "Recommended remediation is to revert the bad `MAX_WORKERS=500` configuration, scale the `release-api` workload back to normal pod levels, and add deployment guardrails that flag extreme worker-count changes before rollout. "
            "Application retry behavior should also be reviewed so bad config cannot amplify compute usage this quickly."
        )
        steps = [
            _mock_step(1, "pipeline_tool", "release-team remediation review", "The release-api configuration change should be rolled back immediately.", source_pipeline),
            _mock_step(2, "cost_api_tool", "release-team pod right-sizing", "Excess release-api pods are the direct cost-remediation target.", source_cost),
        ]
        return _mock_query_result(answer, ["pipeline_tool", "cost_api_tool"], source_pipeline + source_cost, steps)

    answer = f"No scenario-specific remediation summary is defined for {scenario_id}."
    steps = [_mock_step(1, "cost_api_tool", f"{team_id} remediation review", "No scenario-specific remediation summary available.", source_cost)]
    return _mock_query_result(answer, ["cost_api_tool"], source_cost, steps)


def _deserialize_chat_history(raw_history: Any) -> list[Any]:
    if not isinstance(raw_history, list):
        return []

    chat_history: list[Any] = []
    for item in raw_history:
        if not isinstance(item, dict):
            continue

        role = str(item.get("role", "")).strip().lower()
        content = str(item.get("content", "")).strip()
        if not content:
            continue

        if role == "user":
            chat_history.append(HumanMessage(content=content))
        elif role == "assistant":
            chat_history.append(AIMessage(content=content))

    return chat_history


def _try_handle_mock_scenario_query(prompt: str, team_filter: str, scenario_run: Optional[ScenarioRun]) -> Optional[dict[str, Any]]:
    if scenario_run is None:
        return None

    query_lower = prompt.lower()
    team_id = _extract_team_from_query(prompt, team_filter)
    remediation_keywords = ("remediation", "fix", "resolve", "recommended action", "recommended remediation", "how do we fix", "how should", "what should we do")
    root_cause_keywords = ("root cause", "main reason", "reason behind", "what caused", "why did this happen", "why is this happening", "why did this issue")

    if any(keyword in query_lower for keyword in ("orphaned", "idle resource", "idle resources", "which resources", "what resources")):
        return _build_mock_resource_result(scenario_run, team_id)

    if (
        any(phrase in query_lower for phrase in ("which team", "who is responsible"))
        and any(keyword in query_lower for keyword in ("cost spike", "spike", "cost increase", "increase"))
    ):
        return _build_mock_responsibility_result(scenario_run)

    if "pipeline" in query_lower and any(keyword in query_lower for keyword in ("cause", "caused", "why", "activity")):
        return _build_mock_pipeline_result(scenario_run, team_id)

    if any(keyword in query_lower for keyword in root_cause_keywords) or (
        ("why" in query_lower or "cause" in query_lower)
        and any(keyword in query_lower for keyword in ("cost spike", "spike", "cost increase", "increase", "issue"))
    ):
        return _build_mock_root_cause_result(scenario_run, team_id)

    if any(keyword in query_lower for keyword in remediation_keywords) and any(
        keyword in query_lower for keyword in ("issue", "spike", "cost", "problem")
    ):
        return _build_mock_remediation_result(scenario_run, team_id)

    return None


class CORARequestHandler(BaseHTTPRequestHandler):
    server_version = "CORAHTTP/1.0"

    def do_GET(self) -> None:
        route = urlparse(self.path).path

        if route == "/api/health":
            self._send_json(HTTPStatus.OK, {"status": "ok", "mode": _get_mode()})
            return

        if route == "/api/config":
            self._send_json(
                HTTPStatus.OK,
                {
                    "mode": _get_mode(),
                    "team_options": TEAM_OPTIONS,
                    "example_queries": EXAMPLE_QUERIES,
                    "knowledge_base": {
                        "document_count": None,
                        "chunk_count": None,
                        "last_updated": None,
                    },
                },
            )
            return

        if route == "/api/tools":
            # Keep this endpoint fast and independent of LLM provider imports.
            self._send_json(HTTPStatus.OK, {"tools": TOOL_INFO_FALLBACK})
            return

        if route == "/":
            self._send_file(TEMPLATES_DIR / "index.html")
            return

        if route.startswith("/static/"):
            relative = route.removeprefix("/static/")
            safe_path = (STATIC_DIR / relative).resolve()
            if not str(safe_path).startswith(str(STATIC_DIR.resolve())):
                self._send_json(HTTPStatus.FORBIDDEN, {"error": "Forbidden"})
                return
            self._send_file(safe_path)
            return

        self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})

    def do_POST(self) -> None:
        global _current_scenario_run

        route = urlparse(self.path).path
        payload = self._read_json_body()

        if route == "/api/config/mode":
            mode = _set_mode((payload or {}).get("mode", "Mock"))
            self._send_json(HTTPStatus.OK, {"mode": mode})
            return

        if route == "/api/config/scenario":
            payload = payload or {}
            scenario_id = payload.get("scenario_id")
            if not scenario_id or scenario_id not in SCENARIO_IDS:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": f"Invalid scenario_id. Must be one of: {', '.join(SCENARIO_IDS)}"})
                return
            
            _current_scenario_run = build_scenario_run(scenario_id)
            _reset_runtime_state()
            self._send_json(HTTPStatus.OK, {"status": "ok", "scenario_id": scenario_id})
            return

        if route == "/api/query":
            payload = payload or {}
            prompt = str(payload.get("prompt", "")).strip()
            team_filter = str(payload.get("team_filter", "All Teams"))
            scenario_id = str(payload.get("scenario_id", "")).strip()
            chat_history = _deserialize_chat_history(payload.get("chat_history"))
            
            if _get_mode() == "Mock":
                if scenario_id and scenario_id in SCENARIO_IDS:
                    if _current_scenario_run is None or _current_scenario_run.scenario_id != scenario_id:
                        _current_scenario_run = build_scenario_run(scenario_id)
                g.scenario_run = _current_scenario_run
            else:
                g.scenario_run = None

            if not prompt:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "Prompt is required."})
                return

            if _get_mode() == "Mock" and _current_scenario_run is None:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "Select a mock scenario before starting an investigation."})
                return

            full_query = f"For {team_filter}: {prompt}" if team_filter != "All Teams" else prompt

            try:
                direct_result = None
                if _get_mode() == "Mock":
                    direct_result = _try_handle_mock_scenario_query(prompt, team_filter, _current_scenario_run)

                if direct_result is not None:
                    self._send_json(
                        HTTPStatus.OK,
                        {
                            "full_query": full_query,
                            "answer": direct_result.get("answer", ""),
                            "tools_used": direct_result.get("tools_used", []),
                            "steps": direct_result.get("steps", []),
                            "sources": direct_result.get("sources", []),
                        },
                    )
                    return

                agent = _get_agent()
                result = agent.query(full_query, chat_history=chat_history or None)
                steps = _serialize_steps(result.get("intermediate_steps", []))
                source_set = []
                seen_sources = set()
                for s in _extract_sources(result.get("answer", "")):
                    if s not in seen_sources:
                        seen_sources.add(s)
                        source_set.append(s)
                for step in steps:
                    for s in step.get("sources", []):
                        if s not in seen_sources:
                            seen_sources.add(s)
                            source_set.append(s)
                self._send_json(
                    HTTPStatus.OK,
                    {
                        "full_query": full_query,
                        "answer": result.get("answer", ""),
                        "tools_used": result.get("tools_used", []),
                        "steps": steps,
                        "sources": source_set,
                    },
                )
            except Exception as exc:
                self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": f"Investigation failed: {exc}"})
            return

        if route == "/api/reindex":
            try:
                self._send_json(HTTPStatus.OK, {"status": "ok", "message": "Index refreshed"})
            except Exception as exc:
                self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": f"Reindex failed: {exc}"})
            return

        self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})

    def _read_json_body(self) -> dict[str, Any] | None:
        raw_length = self.headers.get("Content-Length")
        if not raw_length:
            return None

        try:
            length = int(raw_length)
        except (TypeError, ValueError):
            return None

        if length <= 0:
            return None

        body = self.rfile.read(length)
        try:
            return json.loads(body.decode("utf-8"))
        except Exception:
            return None

    def _send_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        body = _json_bytes(payload)
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, file_path: Path) -> None:
        if not file_path.exists() or not file_path.is_file():
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})
            return

        body = file_path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", _guess_content_type(file_path))
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


def run(host: str = "0.0.0.0", port: int = 8501) -> None:
    server = ThreadingHTTPServer((host, port), CORARequestHandler)
    print(f"CORA UI running at http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    run()
