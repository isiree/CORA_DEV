"""
Tests that mock mode is a complete firewall against all
live infrastructure. These are the highest-priority tests
in the suite — any failure here means a live service was
reached during a mock mode operation, which is a critical
bug.
"""

from unittest.mock import MagicMock

import pytest


pytestmark = pytest.mark.usefixtures("mock_env", "reset_provider_cache")


def set_scenario(scenario_run):
    import src.g as g_module

    g_module.g.scenario_run = scenario_run


def clear_scenario():
    import src.g as g_module

    g_module.g.scenario_run = None


@pytest.fixture(autouse=True)
def _scenario_context(scenario_1_run):
    set_scenario(scenario_1_run)
    yield
    clear_scenario()


def test_no_azure_credentials_accessed_in_mock_mode(monkeypatch, scenario_1_run):
    """Azure credential classes must never be instantiated in mock mode — any instantiation means Fix 2 regressed."""
    pytest.importorskip("azure")
    azure_identity = pytest.importorskip("azure.identity")

    monkeypatch.setattr(
        azure_identity,
        "DefaultAzureCredential",
        MagicMock(side_effect=Exception("Credentials accessed in mock mode")),
    )
    monkeypatch.setattr(
        azure_identity,
        "ClientSecretCredential",
        MagicMock(side_effect=Exception("Credentials accessed in mock mode")),
        raising=False,
    )

    set_scenario(scenario_1_run)

    from src.tools.cost_api_tool import CostAPITool

    tool = CostAPITool()
    result = tool.get_team_spending("ci-team")
    assert result["success"] is True


def test_no_azure_http_calls_in_mock_mode(monkeypatch, scenario_1_run):
    """No HTTP calls should reach Azure endpoints in mock mode — cost data must come from mock provider."""
    pytest.importorskip("azure")

    original_get = __import__("requests").sessions.Session.get

    def guarded_get(self, url, *args, **kwargs):
        lowered = str(url).lower()
        if "azure" in lowered or "management.azure" in lowered:
            raise AssertionError("HTTP call made in mock mode")
        return original_get(self, url, *args, **kwargs)

    monkeypatch.setattr("requests.Session.get", guarded_get)

    set_scenario(scenario_1_run)

    from src.tools.cost_api_tool import CostAPITool

    tool = CostAPITool()
    result = tool.get_all_teams_summary()
    assert result["success"] is True


def test_no_gitlab_http_calls_deployment_history_in_mock(monkeypatch, scenario_1_run, mock_groq):
    """Pipeline deployment history must never call GitLab in mock mode — this was the original bug found in manual UI testing."""
    pytest.importorskip("azure")

    original_get = __import__("requests").sessions.Session.get

    def guarded_get(self, url, *args, **kwargs):
        if "gitlab" in str(url).lower():
            raise AssertionError("GitLab HTTP call in mock mode")
        return original_get(self, url, *args, **kwargs)

    monkeypatch.setattr("requests.Session.get", guarded_get)

    set_scenario(scenario_1_run)

    from src.tools.pipeline_tool import PipelineTool

    tool = PipelineTool()
    result = tool.get_deployment_history("ci-team")
    assert result["success"] is True


def test_no_gitlab_http_calls_cost_impact_in_mock(monkeypatch, scenario_1_run, mock_groq):
    """Cost impact analysis must not call GitLab in mock mode — this was the specific 401 error seen in the UI for ci-team queries."""
    pytest.importorskip("azure")

    original_get = __import__("requests").sessions.Session.get

    def guarded_get(self, url, *args, **kwargs):
        if "gitlab" in str(url).lower():
            raise AssertionError("GitLab HTTP call in mock mode")
        return original_get(self, url, *args, **kwargs)

    monkeypatch.setattr("requests.Session.get", guarded_get)

    set_scenario(scenario_1_run)

    from src.tools.pipeline_tool import PipelineTool

    tool = PipelineTool()
    result = tool.analyze_cost_impact("ci-team")
    assert result["success"] is True


def test_cost_provider_is_mock_instance_in_mock_mode():
    """Provider factory must return MockCostDataProvider in mock mode, never AzureCostDataProvider."""
    pytest.importorskip("azure")

    from src.providers import get_cost_provider
    from src.providers.mock_cost_provider import MockCostDataProvider

    provider = get_cost_provider()
    assert isinstance(provider, MockCostDataProvider)


def test_get_cost_provider_never_calls_is_available_in_mock(monkeypatch):
    """is_available() on the live Azure provider must never be called in mock mode — calling it triggers Azure credential acquisition (Fix 2)."""
    pytest.importorskip("azure")

    import src.providers as providers_module

    azure_provider_mock = MagicMock()
    azure_provider_mock.is_available.side_effect = AssertionError(
        "is_available called in mock mode"
    )
    monkeypatch.setattr(providers_module, "AzureCostDataProvider", MagicMock(return_value=azure_provider_mock))

    from src.providers import get_cost_provider
    from src.providers.mock_cost_provider import MockCostDataProvider

    result = get_cost_provider()
    assert isinstance(result, MockCostDataProvider)


def test_idle_resources_returns_data_not_error_in_mock(scenario_1_run):
    """Resource discovery methods must return mock data in mock mode — the original bug returned an error because mock provider lacked these methods."""
    pytest.importorskip("azure")

    set_scenario(scenario_1_run)

    from src.tools.cost_api_tool import CostAPITool

    tool = CostAPITool()
    result = tool.get_team_resources("ci-team")
    assert isinstance(result, dict)
    assert result.get("success") is True
    assert "resources" in result or "grouped" in result


def test_idle_resources_all_teams_no_error_in_mock(scenario_1_run):
    """Resource discovery must work for all three teams in mock mode without returning error responses."""
    pytest.importorskip("azure")

    set_scenario(scenario_1_run)

    from src.tools.cost_api_tool import CostAPITool

    tool = CostAPITool()
    for team in ["ci-team", "release-team", "cloudops-team"]:
        result = tool.get_team_resources(team)
        assert isinstance(result, dict)
        assert result.get("success") is True, (
            f"get_team_resources failed for {team}: "
            f"{result.get('error')}"
        )


def test_error_messages_no_azure_mention_in_mock_mode():
    """Error messages in mock mode must not mention Azure infrastructure — users should never see live-mode error text during a mock session."""
    pytest.importorskip("azure")

    from src.tools.cost_api_tool import CostAPITool

    tool = CostAPITool()
    result = tool.get_team_spending("nonexistent-team-xyz")
    if not result.get("success"):
        error = result.get("error", "")
        assert "azure.com" not in error.lower()
        assert "management.azure" not in error.lower()
        assert "credentials" not in error.lower()
        assert "subscription" not in error.lower()


def test_error_messages_no_gitlab_mention_in_mock_mode(mock_groq):
    """Error messages in mock mode must not mention GitLab — users should never see live API error text."""
    pytest.importorskip("azure")

    from src.tools.pipeline_tool import PipelineTool

    tool = PipelineTool()
    result = tool.get_deployment_history("")
    if not result.get("success"):
        error = result.get("error", "")
        assert "gitlab.com" not in error.lower()
        assert "401" not in error
        assert "unauthorized" not in error.lower()
        assert "private-token" not in error.lower()


def test_no_crash_when_scenario_run_is_none_cost_tool():
    """CostAPITool must fail cleanly when g.scenario_run is None — no implicit legacy fallback."""
    pytest.importorskip("azure")

    clear_scenario()

    from src.tools.cost_api_tool import CostAPITool

    tool = CostAPITool()
    result = tool.get_team_spending("ci-team")
    assert isinstance(result, dict)
    assert result.get("success") is False
    assert "scenario" in result.get("error", "").lower()


def test_no_crash_when_scenario_run_is_none_pipeline_tool(mock_groq):
    """PipelineTool must fail cleanly when g.scenario_run is None — no implicit legacy fallback."""
    pytest.importorskip("azure")

    clear_scenario()

    from src.tools.pipeline_tool import PipelineTool

    tool = PipelineTool()
    result = tool.get_deployment_history("ci-team")
    assert isinstance(result, dict)
    assert result.get("success") is False
    assert "scenario" in result.get("error", "").lower()


def test_pipeline_result_tagged_as_mock(scenario_1_run, mock_groq):
    """Pipeline tool results in mock mode must include a mode indicator showing data is simulated, not live."""
    pytest.importorskip("azure")

    set_scenario(scenario_1_run)

    from src.tools.pipeline_tool import PipelineTool

    tool = PipelineTool()
    result = tool.get_deployment_history("ci-team")
    mode = result.get("mode", "")
    assert "mock" in mode.lower() or "MOCK" in str(result)


def test_scenario_context_reaches_cost_tool(scenario_1_run):
    """Scenario data set in g.scenario_run must reach the mock cost provider — verifies the g object thread-local propagation works correctly."""
    pytest.importorskip("azure")

    from src.tools.cost_api_tool import CostAPITool

    set_scenario(scenario_1_run)
    tool = CostAPITool()
    result = tool.get_team_spending("ci-team")
    assert result["success"] is True

    set_scenario(None)
    result2 = tool.get_team_spending("ci-team")
    assert isinstance(result2, dict)
    assert result2.get("success") is False
