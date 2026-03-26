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
