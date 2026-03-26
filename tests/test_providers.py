"""
Tests for provider factory selection and mode detection.
Verifies that the correct provider is selected under every
environment variable combination, and that mock mode never
triggers live provider instantiation.
"""

from unittest.mock import MagicMock

import pytest


pytest.importorskip("azure")

from src.providers import (  # noqa: E402
    get_cost_provider,
    get_pipeline_provider,
    is_azure_live_mode,
    is_gitlab_live_mode,
    is_live_mode,
)
from src.providers.mock_cost_provider import MockCostDataProvider  # noqa: E402
from src.providers.mock_pipeline_provider import MockPipelineDataProvider  # noqa: E402


pytestmark = pytest.mark.usefixtures("mock_env", "reset_provider_cache")


def test_is_live_mode_false_when_use_live_data_not_set(monkeypatch):
    """is_live_mode must return False when USE_LIVE_DATA is not set."""
    monkeypatch.delenv("USE_LIVE_DATA", raising=False)
    assert is_live_mode() is False


@pytest.mark.parametrize("value", ["false", "FALSE", "False"])
def test_is_live_mode_false_when_set_to_false(monkeypatch, value):
    """is_live_mode must return False when USE_LIVE_DATA is explicitly false."""
    monkeypatch.setenv("USE_LIVE_DATA", value)
    assert is_live_mode() is False


def test_is_live_mode_true_when_set_to_true(monkeypatch):
    """is_live_mode must return True when USE_LIVE_DATA is set to true."""
    monkeypatch.setenv("USE_LIVE_DATA", "true")
    assert is_live_mode() is True


def test_is_azure_live_mode_false_without_subscription_id(monkeypatch):
    """Azure live mode requires AZURE_SUBSCRIPTION_ID and must otherwise stay disabled."""
    monkeypatch.setenv("USE_LIVE_DATA", "true")
    monkeypatch.delenv("AZURE_SUBSCRIPTION_ID", raising=False)
    assert is_azure_live_mode() is False


def test_is_azure_live_mode_false_without_credentials(monkeypatch):
    """Azure live mode requires SPN credentials or CLI auth and must otherwise stay disabled."""
    monkeypatch.setenv("USE_LIVE_DATA", "true")
    monkeypatch.setenv("AZURE_SUBSCRIPTION_ID", "sub-123")
    monkeypatch.setenv("AZURE_USE_CLI_AUTH", "false")
    monkeypatch.delenv("AZURE_TENANT_ID", raising=False)
    monkeypatch.delenv("AZURE_CLIENT_ID", raising=False)
    monkeypatch.delenv("AZURE_CLIENT_SECRET", raising=False)
    assert is_azure_live_mode() is False


def test_is_azure_live_mode_true_with_spn_credentials(monkeypatch):
    """Full SPN credentials must enable Azure live mode."""
    monkeypatch.setenv("USE_LIVE_DATA", "true")
    monkeypatch.setenv("AZURE_SUBSCRIPTION_ID", "sub-123")
    monkeypatch.setenv("AZURE_TENANT_ID", "tenant-123")
    monkeypatch.setenv("AZURE_CLIENT_ID", "client-123")
    monkeypatch.setenv("AZURE_CLIENT_SECRET", "secret-123")
    assert is_azure_live_mode() is True


def test_is_azure_live_mode_true_with_cli_auth(monkeypatch):
    """CLI auth must enable Azure live mode without SPN credentials."""
    monkeypatch.setenv("USE_LIVE_DATA", "true")
    monkeypatch.setenv("AZURE_SUBSCRIPTION_ID", "sub-123")
    monkeypatch.setenv("AZURE_USE_CLI_AUTH", "true")
    monkeypatch.delenv("AZURE_TENANT_ID", raising=False)
    monkeypatch.delenv("AZURE_CLIENT_ID", raising=False)
    monkeypatch.delenv("AZURE_CLIENT_SECRET", raising=False)
    assert is_azure_live_mode() is True


def test_is_gitlab_live_mode_false_without_token(monkeypatch):
    """GitLab live mode requires GITLAB_TOKEN and must otherwise stay disabled."""
    monkeypatch.setenv("USE_LIVE_DATA", "true")
    monkeypatch.delenv("GITLAB_TOKEN", raising=False)
    monkeypatch.delenv("GITLAB_PROJECT_ID", raising=False)
    assert is_gitlab_live_mode() is False


def test_is_gitlab_live_mode_true_with_token_and_project(monkeypatch):
    """GitLab token plus project ID must enable live pipeline mode."""
    monkeypatch.setenv("USE_LIVE_DATA", "true")
    monkeypatch.setenv("GITLAB_TOKEN", "x")
    monkeypatch.setenv("GITLAB_PROJECT_ID", "123")
    assert is_gitlab_live_mode() is True


def test_get_cost_provider_returns_mock_in_mock_mode():
    """Provider factory must return MockCostDataProvider when in mock mode."""
    result = get_cost_provider()
    assert isinstance(result, MockCostDataProvider)


def test_get_cost_provider_never_checks_azure_in_mock_mode(monkeypatch):
    """Azure provider is_available() must never run while the app is in mock mode."""
    import src.providers as providers_module

    azure_provider = MagicMock()
    azure_provider.is_available.side_effect = AssertionError("is_available called")
    monkeypatch.setattr(
        providers_module,
        "AzureCostDataProvider",
        MagicMock(return_value=azure_provider),
    )

    result = get_cost_provider()

    assert isinstance(result, MockCostDataProvider)


def test_get_cost_provider_returns_mock_when_azure_incomplete(monkeypatch):
    """Incomplete Azure configuration must fall back to the mock provider."""
    monkeypatch.setenv("USE_LIVE_DATA", "true")
    monkeypatch.delenv("AZURE_SUBSCRIPTION_ID", raising=False)
    result = get_cost_provider()
    assert isinstance(result, MockCostDataProvider)


def test_get_pipeline_provider_returns_mock_in_mock_mode():
    """Pipeline factory must return MockPipelineDataProvider when in mock mode."""
    result = get_pipeline_provider()
    assert isinstance(result, MockPipelineDataProvider)


def test_get_pipeline_provider_returns_mock_without_token(monkeypatch):
    """Missing GITLAB_TOKEN must force the mock pipeline provider."""
    monkeypatch.setenv("USE_LIVE_DATA", "true")
    monkeypatch.delenv("GITLAB_TOKEN", raising=False)
    result = get_pipeline_provider()
    assert isinstance(result, MockPipelineDataProvider)


def test_provider_cache_returns_same_instance():
    """Provider factory must cache and return the same cost provider instance."""
    provider_one = get_cost_provider()
    provider_two = get_cost_provider()
    assert provider_one is provider_two
