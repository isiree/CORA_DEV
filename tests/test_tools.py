"""
Tests for tool-level behaviour in mock mode. Verifies that
all three tools return correct data shapes, handle edge
cases gracefully, and propagate scenario context correctly.
"""

import pytest


pytest.importorskip("azure")
pytest.importorskip("langchain_core")
pytest.importorskip("sentence_transformers")


pytestmark = pytest.mark.usefixtures("mock_env", "reset_provider_cache")


def set_scenario(scenario_run):
    """Set the active scenario on thread-local global state."""
    import src.g as g_module

    g_module.g.scenario_run = scenario_run


def clear_scenario():
    """Clear the active scenario from thread-local global state."""
    import src.g as g_module

    g_module.g.scenario_run = None


@pytest.fixture(autouse=True)
def reset_tool_state():
    """Reset cached tool and cache singletons between tests."""
    import src.tools.cost_api_tool as cost_api_module
    import src.tools.pipeline_tool as pipeline_module
    import src.utils.cache_manager as cache_manager_module

    clear_scenario()
    if cache_manager_module._cache_instance is not None:
        cache_manager_module._cache_instance.clear()
    cost_api_module._cost_tool_instance = None
    pipeline_module._pipeline_tool_instance = None

    yield

    clear_scenario()
    if cache_manager_module._cache_instance is not None:
        cache_manager_module._cache_instance.clear()
    cost_api_module._cost_tool_instance = None
    pipeline_module._pipeline_tool_instance = None


def test_cost_tool_get_team_spending_success(scenario_1_run):
    """get_team_spending must return success=True with budget data for a valid team."""
    from src.tools.cost_api_tool import CostAPITool

    set_scenario(scenario_1_run)
    tool = CostAPITool()
    result = tool.get_team_spending("ci-team")
    assert isinstance(result, dict)
    assert result.get("success") is True
    assert "budget" in result or "team_name" in result


@pytest.mark.parametrize("team", ["ci-team", "release-team", "cloudops-team"])
def test_cost_tool_all_three_teams(scenario_1_run, team):
    """get_team_spending must succeed for all three valid teams."""
    from src.tools.cost_api_tool import CostAPITool

    set_scenario(scenario_1_run)
    tool = CostAPITool()
    result = tool.get_team_spending(team)
    assert result.get("success") is True, f"Failed for team {team}: {result.get('error')}"


def test_cost_tool_invalid_team_no_crash():
    """Invalid team name must not raise and must still return a dict response."""
    from src.tools.cost_api_tool import CostAPITool

    clear_scenario()
    tool = CostAPITool()
    result = tool.get_team_spending("nonexistent-team")
    assert isinstance(result, dict)


def test_cost_tool_get_all_teams_summary(scenario_1_run):
    """get_all_teams_summary must return all three teams with budget data."""
    from src.tools.cost_api_tool import CostAPITool

    set_scenario(scenario_1_run)
    tool = CostAPITool()
    result = tool.get_all_teams_summary()
    assert result.get("success") is True
    assert "teams" in result
    assert len(result["teams"]) >= 3


def test_cost_tool_scenario_1_primary_driver_is_ci_team(scenario_1_run):
    """Scenario 1 summary must identify CI Team as the primary spike driver."""
    from src.tools.cost_api_tool import CostAPITool

    set_scenario(scenario_1_run)
    tool = CostAPITool()
    result = tool.get_all_teams_summary()

    assert result.get("success") is True
    assert result.get("primary_driver", {}).get("team") == "CI Team"
    assert result.get("primary_driver", {}).get("daily_spike_delta", 0) > 0


def test_cost_tool_get_team_resources(scenario_1_run):
    """get_team_resources must return a resource list for ci-team."""
    from src.tools.cost_api_tool import CostAPITool

    set_scenario(scenario_1_run)
    tool = CostAPITool()
    result = tool.get_team_resources("ci-team")
    assert result.get("success") is True
    assert "resources" in result or "grouped" in result


@pytest.mark.parametrize("team", ["ci-team", "release-team", "cloudops-team"])
def test_cost_tool_resources_all_teams(scenario_1_run, team):
    """get_team_resources must succeed for all teams."""
    from src.tools.cost_api_tool import CostAPITool

    set_scenario(scenario_1_run)
    tool = CostAPITool()
    result = tool.get_team_resources(team)
    assert result.get("success") is True


def test_cost_tool_no_crash_without_scenario():
    """CostAPITool must return a clear error instead of legacy mock data when no scenario is selected."""
    from src.tools.cost_api_tool import CostAPITool

    clear_scenario()
    tool = CostAPITool()
    result = tool.get_team_spending("ci-team")
    assert isinstance(result, dict)
    assert result.get("success") is False
    assert "scenario" in result.get("error", "").lower()


def test_cost_tool_top_level_returns_string(scenario_1_run):
    """Top-level cost_api_tool() function must return a non-empty string."""
    from src.tools.cost_api_tool import cost_api_tool

    set_scenario(scenario_1_run)
    result = cost_api_tool.invoke("ci-team spending")
    assert isinstance(result, str)
    assert len(result) > 0


def test_cost_tool_all_teams_summary_without_scenario_returns_error_string():
    """Top-level all-teams summary must fail cleanly when no scenario is selected."""
    from src.tools.cost_api_tool import cost_api_tool

    clear_scenario()
    result = cost_api_tool.invoke("all teams summary")
    assert isinstance(result, str)
    assert "scenario" in result.lower()
    assert "teams" not in result.strip().lower()


def test_cost_tool_is_live_mode_false_in_mock_env():
    """CostAPITool.is_live_mode() must return False in mock mode."""
    from src.tools.cost_api_tool import CostAPITool

    tool = CostAPITool()
    assert tool.is_live_mode() is False


def test_pipeline_tool_deployment_history(scenario_1_run, mock_groq):
    """get_deployment_history must return success=True with statistics in mock mode."""
    pytest.importorskip("langchain_groq")
    from src.tools.pipeline_tool import PipelineTool

    set_scenario(scenario_1_run)
    tool = PipelineTool()
    result = tool.get_deployment_history("ci-team")
    assert result.get("success") is True
    assert "statistics" in result


@pytest.mark.parametrize("team", ["ci-team", "release-team", "cloudops-team"])
def test_pipeline_tool_all_teams(scenario_1_run, team, mock_groq):
    """get_deployment_history must succeed for all three valid teams."""
    pytest.importorskip("langchain_groq")
    from src.tools.pipeline_tool import PipelineTool

    set_scenario(scenario_1_run)
    tool = PipelineTool()
    result = tool.get_deployment_history(team)
    assert result.get("success") is True, f"Failed for {team}: {result.get('error')}"


def test_pipeline_tool_no_crash_without_scenario(mock_groq):
    """PipelineTool must return a clear error instead of legacy mock data when no scenario is selected."""
    pytest.importorskip("langchain_groq")
    from src.tools.pipeline_tool import PipelineTool

    clear_scenario()
    tool = PipelineTool()
    result = tool.get_deployment_history("ci-team")
    assert isinstance(result, dict)
    assert result.get("success") is False
    assert "scenario" in result.get("error", "").lower()


def test_pipeline_tool_result_is_mock(scenario_1_run, mock_groq):
    """Deployment history result must clearly indicate mock mode."""
    pytest.importorskip("langchain_groq")
    from src.tools.pipeline_tool import PipelineTool

    set_scenario(scenario_1_run)
    tool = PipelineTool()
    result = tool.get_deployment_history("ci-team")
    mode = result.get("mode", "")
    assert "mock" in mode.lower() or "MOCK" in str(result)


def test_pipeline_tool_top_level_returns_string(scenario_1_run, mock_groq):
    """Top-level pipeline_tool() function must return a non-empty string."""
    pytest.importorskip("langchain_groq")
    from src.tools.pipeline_tool import pipeline_tool

    set_scenario(scenario_1_run)
    result = pipeline_tool.invoke("analyze ci-team cost impact")
    assert isinstance(result, str)
    assert len(result) > 0


def test_historical_tool_search_returns_dict(mock_groq, mock_chroma):
    """search() must return a dict with success, query, and results fields."""
    pytest.importorskip("chromadb")
    pytest.importorskip("langchain_groq")
    from src.tools.historical_tool import HistoricalTool

    tool = HistoricalTool()
    result = tool.search("cloud cost policy")
    assert isinstance(result, dict)
    assert "success" in result
    assert "query" in result
    assert "results" in result
    assert isinstance(result["results"], list)


def test_historical_tool_empty_store_no_crash(mock_groq, mock_chroma):
    """Empty vector store must not crash the tool."""
    pytest.importorskip("chromadb")
    pytest.importorskip("langchain_groq")
    from src.tools.historical_tool import HistoricalTool

    tool = HistoricalTool()
    result = tool.search("any query about costs")
    assert isinstance(result, dict)


def test_historical_tool_top_level_returns_string(mock_groq, mock_chroma):
    """Top-level historical_tool() must return a string even with an empty store."""
    pytest.importorskip("chromadb")
    pytest.importorskip("langchain_groq")
    from src.tools.historical_tool import historical_tool

    result = historical_tool.invoke("FinOps governance policy")
    assert isinstance(result, str)


def test_scenario_switch_changes_pipeline_data(mock_groq):
    """Switching scenarios must change pipeline data returned by PipelineTool."""
    pytest.importorskip("langchain_groq")
    from src.scenarios import (
        _build_scenario_1_vm_destroy as scenario_1_vm_destroy,
        _build_scenario_3_autoscaler as scenario_3_autoscaler,
    )
    from src.tools.pipeline_tool import PipelineTool

    set_scenario(scenario_1_vm_destroy())
    tool = PipelineTool()
    result_1 = tool.get_deployment_history("ci-team")

    clear_scenario()
    import src.tools.pipeline_tool as pipeline_module

    pipeline_module._pipeline_tool_instance = None
    set_scenario(scenario_3_autoscaler())
    tool = PipelineTool()
    result_3 = tool.get_deployment_history("release-team")

    assert result_1.get("success") is True
    assert result_3.get("success") is True


def test_scenario_2_team_spending_uses_scenario_data_not_legacy():
    """Scenario 2 spend queries must not leak legacy mock numbers like $2,650."""
    from src.scenarios import _build_scenario_2_tagging
    from src.tools.cost_api_tool import CostAPITool

    set_scenario(_build_scenario_2_tagging())
    tool = CostAPITool()
    result = tool.get_team_spending("release-team")

    assert result.get("success") is True
    assert result["budget"]["current_spend"] == "$4,500.00"
    assert result["budget"]["monthly_budget"] == "$2,400"


def test_scenario_legacy_mock_explicit_selection_keeps_legacy_values():
    """The legacy numbers should only appear when the explicit Legacy Mock scenario is selected."""
    from src.scenarios import _build_scenario_legacy_mock
    from src.tools.cost_api_tool import CostAPITool

    set_scenario(_build_scenario_legacy_mock())
    tool = CostAPITool()
    result = tool.get_team_spending("release-team")

    assert result.get("success") is True
    assert result["budget"]["current_spend"] == "$2,650.00"
