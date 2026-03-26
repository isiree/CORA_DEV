"""
HTTP endpoint contract tests. Verifies that every route
in app.py returns the correct status code and response
shape. Uses a real HTTP server on a random port to test
the full request/response cycle.
"""

import json
import threading
from http.server import HTTPServer
from http.client import HTTPConnection
from unittest.mock import MagicMock, patch
from urllib.parse import urlparse

import pytest

import app as app_module


pytestmark = pytest.mark.usefixtures("mock_env")


class HTTPTestResponse:
    """Small helper wrapper for HTTP test responses."""

    def __init__(self, status_code, body):
        self.status_code = status_code
        self._body = body

    def json(self):
        """Decode the response body as JSON."""
        if not self._body:
            return {}
        return json.loads(self._body.decode("utf-8"))


def _request(base_url, method, path, payload=None, headers=None):
    """Issue a request against the local test server."""
    parsed = urlparse(base_url)
    request_headers = dict(headers or {})
    body = None

    if isinstance(payload, dict):
        body = json.dumps(payload).encode("utf-8")
        request_headers.setdefault("Content-Type", "application/json")
    elif isinstance(payload, str):
        body = payload.encode("utf-8")
    elif isinstance(payload, bytes):
        body = payload

    connection = HTTPConnection(parsed.hostname, parsed.port, timeout=5)
    try:
        connection.request(method, path, body=body, headers=request_headers)
        response = connection.getresponse()
        body = response.read()
        return HTTPTestResponse(response.status, body)
    finally:
        connection.close()


@pytest.fixture(scope="module")
def api_server():
    """Start a local HTTP server with the agent dependency patched."""
    mock_agent = MagicMock()
    mock_agent.query.return_value = {
        "answer": "Mock investigation complete.",
        "tools_used": ["cost_api_tool"],
        "steps": [],
        "sources": ["MOCK LIVE"],
        "intermediate_steps": [],
    }

    server = HTTPServer(("127.0.0.1", 0), app_module.CORARequestHandler)
    port = server.server_address[1]
    base_url = f"http://127.0.0.1:{port}"
    thread = threading.Thread(target=server.serve_forever, daemon=True)

    with patch.object(app_module, "_get_agent", return_value=mock_agent):
        app_module._current_scenario_run = None
        thread.start()
        try:
            yield base_url
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
            app_module._current_scenario_run = None


@pytest.fixture(autouse=True)
def reset_app_state(mock_env):
    """Reset mutable app-level state between API tests."""
    app_module._current_scenario_run = None
    app_module._set_mode("Mock")
    app_module.g.scenario_run = None
    yield
    app_module._current_scenario_run = None
    app_module._set_mode("Mock")
    app_module.g.scenario_run = None


def test_get_health_200(api_server):
    """GET /api/health must return 200 with status ok."""
    response = _request(api_server, "GET", "/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "mode" in body


def test_get_config_fields(api_server):
    """GET /api/config must return the required config fields."""
    response = _request(api_server, "GET", "/api/config")
    assert response.status_code == 200
    body = response.json()
    assert "mode" in body
    assert "team_options" in body
    assert isinstance(body["team_options"], list)
    assert "example_queries" in body
    assert "knowledge_base" in body


def test_get_tools_returns_three_tools(api_server):
    """GET /api/tools must return exactly three tool definitions."""
    response = _request(api_server, "GET", "/api/tools")
    assert response.status_code == 200
    tools = response.json()["tools"]
    assert len(tools) == 3
    for tool in tools:
        assert "name" in tool
        assert "description" in tool


def test_post_config_mode_mock(api_server):
    """POST /api/config/mode with Mock must switch mode and confirm it."""
    response = _request(api_server, "POST", "/api/config/mode", {"mode": "Mock"})
    assert response.status_code == 200
    assert response.json()["mode"] == "Mock"


def test_post_config_mode_live(api_server):
    """POST /api/config/mode with Live must switch mode and confirm it."""
    response = _request(api_server, "POST", "/api/config/mode", {"mode": "Live"})
    assert response.status_code == 200
    assert response.json()["mode"] == "Live"


def test_post_config_scenario_valid(api_server):
    """Valid scenario_id must return 200 with status ok."""
    response = _request(
        api_server,
        "POST",
        "/api/config/scenario",
        {"scenario_id": "scenario_1_vm_destroy"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["scenario_id"] == "scenario_1_vm_destroy"


def test_post_config_scenario_invalid(api_server):
    """Invalid scenario_id must return 400 with an error payload."""
    response = _request(
        api_server,
        "POST",
        "/api/config/scenario",
        {"scenario_id": "fake_scenario_xyz"},
    )
    assert response.status_code == 400
    assert "error" in response.json()


def test_post_query_returns_answer(api_server):
    """POST /api/query must return answer, tools_used, steps, and sources."""
    response = _request(
        api_server,
        "POST",
        "/api/query",
        {
            "prompt": "Why has ci-team spend increased?",
            "team_filter": "ci-team",
            "scenario_id": "scenario_1_vm_destroy",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert "answer" in body
    assert isinstance(body["answer"], str)
    assert len(body["answer"]) > 0
    assert "tools_used" in body
    assert "steps" in body
    assert "sources" in body


def test_post_query_uses_payload_scenario_when_backend_has_none():
    """POST /api/query must activate the payload scenario in mock mode even before scenario config is posted."""
    mock_agent = MagicMock()
    mock_agent.query.side_effect = lambda prompt: {
        "answer": "agent fallback used",
        "tools_used": ["cost_api_tool"],
        "steps": [],
        "sources": [],
        "intermediate_steps": [],
    }

    server = HTTPServer(("127.0.0.1", 0), app_module.CORARequestHandler)
    port = server.server_address[1]
    base_url = f"http://127.0.0.1:{port}"
    thread = threading.Thread(target=server.serve_forever, daemon=True)

    with patch.object(app_module, "_get_agent", return_value=mock_agent):
        app_module._current_scenario_run = None
        app_module._set_mode("Mock")
        app_module.g.scenario_run = None
        thread.start()
        try:
            response = _request(
                base_url,
                "POST",
                "/api/query",
                {
                    "prompt": "Which team is responsible for the cost spike?",
                    "team_filter": "All Teams",
                    "scenario_id": "scenario_1_vm_destroy",
                },
            )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
            app_module._current_scenario_run = None
            app_module.g.scenario_run = None

    assert response.status_code == 200
    assert "CI Team" in response.json()["answer"]
    assert "destroy-loadtest" in response.json()["answer"]


def test_post_query_mock_without_scenario_returns_400(api_server):
    """Mock investigations must not silently fall back to legacy data when no scenario is selected."""
    response = _request(
        api_server,
        "POST",
        "/api/query",
        {"prompt": "Which team is responsible for the cost spike?", "team_filter": "All Teams"},
    )
    assert response.status_code == 400
    assert "scenario" in response.json()["error"].lower()


def test_post_query_scenario_1_pipeline_question_is_deterministic():
    """Scenario 1 pipeline-cause questions must return the destroy failure root cause, not legacy budget text."""
    mock_agent = MagicMock()
    mock_agent.query.side_effect = AssertionError("Agent fallback should not be used for deterministic mock queries")

    server = HTTPServer(("127.0.0.1", 0), app_module.CORARequestHandler)
    port = server.server_address[1]
    base_url = f"http://127.0.0.1:{port}"
    thread = threading.Thread(target=server.serve_forever, daemon=True)

    with patch.object(app_module, "_get_agent", return_value=mock_agent):
        app_module._current_scenario_run = None
        app_module._set_mode("Mock")
        app_module.g.scenario_run = None
        thread.start()
        try:
            response = _request(
                base_url,
                "POST",
                "/api/query",
                {
                    "prompt": "What pipeline activity caused the CI Team cost increase in Scenario 1?",
                    "team_filter": "All Teams",
                    "scenario_id": "scenario_1_vm_destroy",
                },
            )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
            app_module._current_scenario_run = None
            app_module.g.scenario_run = None

    body = response.json()
    assert response.status_code == 200
    assert "deploy-loadtest" in body["answer"]
    assert "destroy-loadtest" in body["answer"]
    assert "state lock" in body["answer"].lower()
    assert "$1,850" not in body["answer"]


def test_post_query_scenario_1_resource_question_returns_resources():
    """Scenario 1 orphaned-resource questions must return concrete resource ids, not generic budget advice."""
    mock_agent = MagicMock()
    mock_agent.query.side_effect = AssertionError("Agent fallback should not be used for deterministic mock queries")

    server = HTTPServer(("127.0.0.1", 0), app_module.CORARequestHandler)
    port = server.server_address[1]
    base_url = f"http://127.0.0.1:{port}"
    thread = threading.Thread(target=server.serve_forever, daemon=True)

    with patch.object(app_module, "_get_agent", return_value=mock_agent):
        app_module._current_scenario_run = None
        app_module._set_mode("Mock")
        app_module.g.scenario_run = None
        thread.start()
        try:
            response = _request(
                base_url,
                "POST",
                "/api/query",
                {
                    "prompt": "Which resources look orphaned or idle for the CI Team?",
                    "team_filter": "All Teams",
                    "scenario_id": "scenario_1_vm_destroy",
                },
            )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
            app_module._current_scenario_run = None
            app_module.g.scenario_run = None

    body = response.json()
    assert response.status_code == 200
    assert "res-loadtest-1" in body["answer"]
    assert "res-loadtest-2" in body["answer"]
    assert "orphaned" in body["answer"].lower() or "idle" in body["answer"].lower()


def test_post_query_missing_prompt_400(api_server):
    """Missing prompt field must return 400 with an error message."""
    response = _request(api_server, "POST", "/api/query", {})
    assert response.status_code == 400
    assert "error" in response.json()


def test_post_query_invalid_json(api_server):
    """Invalid JSON body must not crash the server."""
    response = _request(
        api_server,
        "POST",
        "/api/query",
        "not valid json",
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code in [400, 500]
    try:
        body = response.json()
        assert "error" in body
    except Exception:
        pass


def test_post_reindex_returns_ok(api_server):
    """POST /api/reindex must return 200 with status ok."""
    response = _request(api_server, "POST", "/api/reindex", {})
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_static_path_traversal_blocked(api_server):
    """Path traversal attempts must be blocked with 403 or 404."""
    response = _request(api_server, "GET", "/static/../app.py")
    assert response.status_code in [403, 404]


def test_unmatched_route_404(api_server):
    """Unmatched routes must return 404 with an error payload."""
    response = _request(api_server, "GET", "/api/this_does_not_exist")
    assert response.status_code == 404
    assert "error" in response.json()
