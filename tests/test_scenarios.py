"""
Tests for scenario data integrity. Verifies that all five
scenario builders produce internally consistent data that
the agent can reason about without contradictions.
"""

from datetime import datetime

import pytest

from src.scenarios import (
    SCENARIO_IDS,
    ScenarioRun,
    _build_scenario_1_vm_destroy as scenario_1_vm_destroy,
    _build_scenario_2_tagging as scenario_2_tagging,
    _build_scenario_3_autoscaler as scenario_3_autoscaler,
    _build_scenario_4_forgotten_poc as scenario_4_forgotten_poc,
    _build_scenario_5_app_misconfig as scenario_5_app_misconfig,
    _build_scenario_legacy_mock as scenario_legacy_mock,
)


SCENARIO_BUILDERS = [
    scenario_1_vm_destroy,
    scenario_2_tagging,
    scenario_3_autoscaler,
    scenario_4_forgotten_poc,
    scenario_5_app_misconfig,
    scenario_legacy_mock,
]

PRIMARY_SCENARIO_EXPECTATIONS = {
    scenario_1_vm_destroy: {
        "team_id": "ci-team",
        "pipeline": "destroy-loadtest",
        "resources": {"res-loadtest-1", "res-loadtest-2"},
    },
    scenario_2_tagging: {
        "team_id": "release-team",
        "pipeline": "deploy-release-prod",
        "resources": {"res-db-prod", "res-api-1"},
    },
    scenario_3_autoscaler: {
        "team_id": "release-team",
        "pipeline": "update-web-autoscaler",
        "resources": {"web-frontend-asg", "res-web-frontend"},
    },
    scenario_4_forgotten_poc: {
        "team_id": "cloudops-team",
        "pipeline": "deploy-poc-analytics",
        "resources": {"poc-analytics-vm-1", "poc-analytics-db"},
    },
    scenario_5_app_misconfig: {
        "team_id": "release-team",
        "pipeline": "deploy-release-api",
        "resources": {"release-api", "rel-api-pods"},
    },
}


@pytest.mark.parametrize("scenario_builder", SCENARIO_BUILDERS)
def test_scenario_build_returns_scenario_run(scenario_builder):
    """Each builder must return a ScenarioRun instance."""
    result = scenario_builder()
    assert isinstance(result, ScenarioRun)


def test_all_scenario_ids_defined():
    """SCENARIO_IDS must contain exactly 6 entries."""
    assert len(SCENARIO_IDS) == 6
    assert all(isinstance(scenario_id, str) and len(scenario_id) > 0 for scenario_id in SCENARIO_IDS)


@pytest.mark.parametrize("scenario_builder", SCENARIO_BUILDERS)
def test_scenario_run_has_required_fields(scenario_builder):
    """ScenarioRun must have non-null scenario_id, cost_data, and pipeline_data."""
    run = scenario_builder()
    assert run.scenario_id is not None
    assert len(run.scenario_id) > 0
    assert run.cost_data is not None
    assert isinstance(run.cost_data, dict)
    assert run.pipeline_data is not None
    assert isinstance(run.pipeline_data, dict)


@pytest.mark.parametrize("scenario_builder", SCENARIO_BUILDERS)
def test_scenario_cost_data_has_teams(scenario_builder):
    """cost_data must contain a non-empty teams list."""
    run = scenario_builder()
    assert "teams" in run.cost_data
    assert isinstance(run.cost_data["teams"], list)
    assert len(run.cost_data["teams"]) >= 1


@pytest.mark.parametrize("scenario_builder", SCENARIO_BUILDERS)
def test_scenario_each_team_has_required_fields(scenario_builder):
    """Each team entry in cost_data must have team_id, daily_costs, and resources."""
    run = scenario_builder()
    for team in run.cost_data["teams"]:
        assert "team_id" in team
        assert team["team_id"] is not None
        assert "daily_costs" in team
        assert isinstance(team["daily_costs"], list)
        assert "resources" in team
        assert isinstance(team["resources"], list)


@pytest.mark.parametrize("scenario_builder", SCENARIO_BUILDERS)
def test_scenario_daily_costs_are_numeric(scenario_builder):
    """All daily cost values must be numeric and non-negative."""
    run = scenario_builder()
    for team in run.cost_data["teams"]:
        for day in team["daily_costs"]:
            assert isinstance(day["total_cost"], (int, float))
            assert day["total_cost"] >= 0


@pytest.mark.parametrize("scenario_builder", SCENARIO_BUILDERS)
def test_scenario_pipeline_data_has_pipelines(scenario_builder):
    """pipeline_data must contain a pipelines list."""
    run = scenario_builder()
    assert "pipelines" in run.pipeline_data
    assert isinstance(run.pipeline_data["pipelines"], list)


@pytest.mark.parametrize("scenario_builder", SCENARIO_BUILDERS)
def test_scenario_pipeline_entries_have_required_fields(scenario_builder):
    """Each pipeline entry must have pipeline_id, team_id, and status."""
    run = scenario_builder()
    for pipeline in run.pipeline_data["pipelines"]:
        assert pipeline.get("pipeline_id") is not None
        assert pipeline.get("team_id") is not None
        assert pipeline.get("status") is not None


@pytest.mark.parametrize("scenario_builder", SCENARIO_BUILDERS)
def test_scenario_timestamps_ordered(scenario_builder):
    """Pipeline finished_at must be greater than or equal to started_at."""
    run = scenario_builder()
    for pipeline in run.pipeline_data["pipelines"]:
        started = pipeline.get("started_at")
        finished = pipeline.get("finished_at")
        if started and finished:
            started_at = datetime.fromisoformat(started.replace("Z", "+00:00"))
            finished_at = datetime.fromisoformat(finished.replace("Z", "+00:00"))
            assert finished_at >= started_at, (
                f"Pipeline {pipeline['pipeline_id']} finishes before it starts"
            )


def test_scenario_1_has_failed_destroy_job():
    """Scenario 1 must include a failed destroy or cleanup job for the root cause."""
    run = scenario_1_vm_destroy()
    all_jobs = [
        job
        for pipeline in run.pipeline_data["pipelines"]
        for job in pipeline.get("jobs", [])
    ]
    failed_destroy = [
        job
        for job in all_jobs
        if job.get("status") == "failed"
        and any(keyword in job.get("name", "").lower() for keyword in ("destroy", "cleanup"))
    ]
    assert len(failed_destroy) >= 1, (
        "Scenario 1 must have a failed destroy/cleanup job as the causal root of the cost spike"
    )


def test_scenario_3_has_vmss_or_autoscaler_resource():
    """Scenario 3 must include a VMSS or autoscaler-related resource in cost data."""
    run = scenario_3_autoscaler()
    all_resources = [
        resource
        for team in run.cost_data["teams"]
        for resource in team.get("resources", [])
    ]
    autoscaler_resources = [
        resource
        for resource in all_resources
        if any(
            keyword in (resource.get("name", "") + resource.get("type", "")).lower()
            for keyword in ("vmss", "autoscal", "scaleset")
        )
    ]
    assert len(autoscaler_resources) >= 1


@pytest.mark.parametrize(
    ("scenario_builder", "expected"),
    list(PRIMARY_SCENARIO_EXPECTATIONS.items()),
)
def test_primary_team_has_required_agent_evidence_fields(scenario_builder, expected):
    """Primary teams in the five numbered scenarios must expose explicit anomaly metadata for the agent."""
    run = scenario_builder()
    team = next(team for team in run.cost_data["teams"] if team["team_id"] == expected["team_id"])

    assert team["anomaly_detected"] is True
    assert isinstance(team["anomaly_description"], str) and team["anomaly_description"]
    assert isinstance(team["cost_spike_date"], str) and team["cost_spike_date"]
    assert isinstance(team["top_resources"], list)
    assert len(team["top_resources"]) >= 2

    resource_names = {resource["name"] for resource in team["top_resources"]}
    assert expected["resources"].issubset(resource_names)
    for resource in team["top_resources"]:
        assert {"name", "type", "cost", "utilisation"} <= resource.keys()


@pytest.mark.parametrize(
    ("scenario_builder", "expected"),
    list(PRIMARY_SCENARIO_EXPECTATIONS.items()),
)
def test_primary_team_has_near_zero_utilisation_resource(scenario_builder, expected):
    """Each numbered scenario must include at least one near-idle resource for resource follow-up questions."""
    run = scenario_builder()
    team = next(team for team in run.cost_data["teams"] if team["team_id"] == expected["team_id"])
    assert any(float(resource["utilisation"]) <= 5.0 for resource in team["top_resources"])


@pytest.mark.parametrize(
    ("scenario_builder", "expected"),
    list(PRIMARY_SCENARIO_EXPECTATIONS.items()),
)
def test_primary_team_pipeline_contains_expected_causal_event(scenario_builder, expected):
    """Each numbered scenario must include the expected causal pipeline on the primary team."""
    run = scenario_builder()
    pipelines = [
        pipeline
        for pipeline in run.pipeline_data["pipelines"]
        if pipeline["team_id"] == expected["team_id"]
    ]
    assert any(pipeline["name"] == expected["pipeline"] for pipeline in pipelines)


@pytest.mark.parametrize(
    ("scenario_builder", "expected"),
    list(PRIMARY_SCENARIO_EXPECTATIONS.items()),
)
def test_primary_team_pipeline_has_failed_or_suspicious_job_before_spike(scenario_builder, expected):
    """Each numbered scenario must include failed or suspicious job evidence before the spike date."""
    run = scenario_builder()
    team = next(team for team in run.cost_data["teams"] if team["team_id"] == expected["team_id"])
    spike_date = datetime.fromisoformat(f"{team['cost_spike_date']}T00:00:00+00:00")

    suspicious_pipelines = []
    for pipeline in run.pipeline_data["pipelines"]:
        if pipeline["team_id"] != expected["team_id"]:
            continue
        started_at = datetime.fromisoformat(pipeline["started_at"].replace("Z", "+00:00"))
        if started_at > spike_date:
            continue
        jobs = pipeline.get("jobs", [])
        if any(job.get("status") in {"failed", "warning"} or job.get("log_excerpt") for job in jobs):
            suspicious_pipelines.append((pipeline, jobs))

    assert suspicious_pipelines
    assert any(
        any(isinstance(job.get("name"), str) and job["name"] for job in jobs)
        and any(isinstance(job.get("log_excerpt", ""), str) and job.get("log_excerpt") for job in jobs)
        for _, jobs in suspicious_pipelines
    )
