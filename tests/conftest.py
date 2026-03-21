import importlib
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def mock_env(monkeypatch):
    monkeypatch.setenv("USE_LIVE_DATA", "false")
    for var in [
        "AZURE_SUBSCRIPTION_ID",
        "AZURE_TENANT_ID",
        "AZURE_CLIENT_ID",
        "AZURE_CLIENT_SECRET",
        "GITLAB_TOKEN",
        "GITLAB_PROJECT_ID",
    ]:
        monkeypatch.delenv(var, raising=False)


@pytest.fixture
def live_env(monkeypatch):
    monkeypatch.setenv("USE_LIVE_DATA", "true")
    monkeypatch.setenv("AZURE_SUBSCRIPTION_ID", "test-sub-id")
    monkeypatch.setenv("AZURE_TENANT_ID", "test-tenant")
    monkeypatch.setenv("AZURE_CLIENT_ID", "test-client")
    monkeypatch.setenv("AZURE_CLIENT_SECRET", "test-secret")
    monkeypatch.setenv("GITLAB_TOKEN", "test-token")
    monkeypatch.setenv("GITLAB_PROJECT_ID", "12345")


@pytest.fixture
def scenario_1_run():
    from src.scenarios import ScenarioRun, _build_scenario_1_vm_destroy

    scenario = _build_scenario_1_vm_destroy()
    assert isinstance(scenario, ScenarioRun)
    return scenario


@pytest.fixture
def all_scenario_runs():
    from src.scenarios import SCENARIO_IDS, ScenarioRun, build_scenario_run

    scenarios = {scenario_id: build_scenario_run(scenario_id) for scenario_id in SCENARIO_IDS}
    assert all(isinstance(run, ScenarioRun) for run in scenarios.values())
    return scenarios


@pytest.fixture
def mock_groq(monkeypatch):
    pytest.importorskip("langchain_groq")

    mock_response = MagicMock(content="Mock LLM response for testing.")
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = mock_response
    mock_llm.return_value = mock_response

    monkeypatch.setattr("langchain_groq.ChatGroq", lambda *args, **kwargs: mock_llm)
    return mock_llm


@pytest.fixture
def mock_chroma(monkeypatch):
    chromadb = pytest.importorskip("chromadb")

    mock_collection = MagicMock()
    mock_collection.query.return_value = {
        "documents": [[]],
        "metadatas": [[]],
        "distances": [[]],
    }
    mock_collection.count.return_value = 0

    mock_client = MagicMock()
    mock_client.get_or_create_collection.return_value = mock_collection

    monkeypatch.setattr(chromadb, "PersistentClient", lambda *args, **kwargs: mock_client)
    monkeypatch.setattr(chromadb, "Client", lambda *args, **kwargs: mock_client)
    return mock_collection


@pytest.fixture
def reset_provider_cache():
    providers_module = importlib.import_module("src.providers")
    if hasattr(providers_module, "_cost_provider_instance"):
        providers_module._cost_provider_instance = None
    if hasattr(providers_module, "_pipeline_provider_instance"):
        providers_module._pipeline_provider_instance = None

    yield

    if hasattr(providers_module, "_cost_provider_instance"):
        providers_module._cost_provider_instance = None
    if hasattr(providers_module, "_pipeline_provider_instance"):
        providers_module._pipeline_provider_instance = None

