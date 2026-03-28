"""
HTTP endpoint contract tests. Verifies that every route
in app.py returns the correct status code and response
shape. Uses a real HTTP server on a random port to test
the full request/response cycle.
"""

import json
import threading
from http.server import HTTPServer, ThreadingHTTPServer
from http.client import HTTPConnection
from unittest.mock import MagicMock, patch
from urllib.parse import urlparse

from langchain_core.messages import AIMessage, HumanMessage
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


def test_post_query_scenario_1_remediation_question_is_deterministic():
    """Scenario 1 remediation follow-ups must stay on the deterministic mock path."""
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
                    "prompt": "what remediation is recommended to fix this issue in the ci team ?",
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
    assert "destroy-loadtest" in body["answer"]
    assert "res-loadtest" in body["answer"]
    assert "state lock" in body["answer"].lower() or "force-unlock" in body["answer"].lower()


def test_post_query_scenario_1_remedy_situation_question_is_deterministic():
    """Natural phrasing like 'how to remedy this situation' must stay on the deterministic mock path."""
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
                    "prompt": "how to remedy this situation",
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
    assert "destroy-loadtest" in body["answer"]
    assert "res-loadtest" in body["answer"]


def test_post_query_scenario_1_root_cause_question_is_deterministic():
    """Scenario 1 root-cause follow-ups must not drop to generic budget guidance."""
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
                    "prompt": "what is the main reason behind this cost spike in the ci team ?",
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
    assert "destroy-loadtest" in body["answer"]
    assert "state lock" in body["answer"].lower()
    assert "$1,850" not in body["answer"]


def test_post_query_scenario_1_prevention_question_is_deterministic():
    """Prevention follow-ups about avoiding Terraform state-lock issues must stay deterministic."""
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
                    "prompt": "what can we do in the ci team to avoid a state lock issue in terraform again",
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
    assert "state lock" in body["answer"].lower() or "force-unlock" in body["answer"].lower()
    assert "destroy-loadtest" in body["answer"]


def test_post_query_scenario_2_ownership_question_is_deterministic():
    """Ownership/misattribution wording in Scenario 2 must stay on the deterministic mock path."""
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
                    "prompt": "is the cost increase owned by a team or is it unallocated/misattributed?",
                    "team_filter": "All Teams",
                    "scenario_id": "scenario_2_tagging",
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
    assert "Release Team" in body["answer"]
    assert "unallocated" in body["answer"].lower()
    assert "deploy-release-prod" in body["answer"]
    assert "$2,650" not in body["answer"]
    assert "10.4%" not in body["answer"]


def test_post_query_includes_detected_intent_metadata_for_mock_query():
    """Mock responses should report the detected intent for demo transparency."""
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
                    "prompt": "Which team is responsible for the cost spike?",
                    "team_filter": "All Teams",
                    "scenario_id": "scenario_3_autoscaler",
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
    assert body["detected_intent"] == "RESPONSIBILITY"


def test_post_query_scenario_3_singular_resource_followup_is_deterministic():
    """Singular follow-up wording like 'this resource' should stay on the scenario resource path."""
    mock_agent = MagicMock()
    mock_agent.query.side_effect = AssertionError("Agent fallback should not be used for deterministic mock resource follow-ups")

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
                    "prompt": "mention what this resource is",
                    "team_filter": "All Teams",
                    "scenario_id": "scenario_3_autoscaler",
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
    assert "web-frontend-asg" in body["answer"]
    assert "user-service" in body["answer"]


def test_post_query_passes_scenario_context_to_fallback_agent_in_mock_mode():
    """Fallback mock-mode agent calls should receive structured scenario context."""
    seen = {}
    mock_agent = MagicMock()

    def query_side_effect(question, chat_history=None, scenario_context=None):
        seen["scenario_context"] = scenario_context
        return {
            "answer": "fallback answer",
            "tools_used": [],
            "steps": [],
            "sources": [],
            "intermediate_steps": [],
        }

    mock_agent.query.side_effect = query_side_effect

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
                    "prompt": "give me a concise investigation summary",
                    "team_filter": "All Teams",
                    "scenario_id": "scenario_3_autoscaler",
                },
            )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
            app_module._current_scenario_run = None
            app_module.g.scenario_run = None

    assert response.status_code == 200
    scenario_context = seen["scenario_context"]
    assert "scenario_3_autoscaler" in scenario_context
    assert "Release Team" in scenario_context
    assert "update-web-autoscaler" in scenario_context
    assert "web-frontend-asg" in scenario_context


def test_post_query_does_not_pass_scenario_context_in_live_mode():
    """Live-mode fallback agent calls should not receive mock scenario context."""
    seen = {}
    mock_agent = MagicMock()

    def query_side_effect(question, chat_history=None, scenario_context=None):
        seen["scenario_context"] = scenario_context
        return {
            "answer": "live fallback answer",
            "tools_used": [],
            "steps": [],
            "sources": [],
            "intermediate_steps": [],
        }

    mock_agent.query.side_effect = query_side_effect

    server = HTTPServer(("127.0.0.1", 0), app_module.CORARequestHandler)
    port = server.server_address[1]
    base_url = f"http://127.0.0.1:{port}"
    thread = threading.Thread(target=server.serve_forever, daemon=True)

    with patch.object(app_module, "_get_agent", return_value=mock_agent):
        app_module._current_scenario_run = None
        app_module._set_mode("Live")
        app_module.g.scenario_run = None
        thread.start()
        try:
            response = _request(
                base_url,
                "POST",
                "/api/query",
                {
                    "prompt": "give me a concise investigation summary",
                    "team_filter": "All Teams",
                },
            )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
            app_module._current_scenario_run = None
            app_module._set_mode("Mock")
            app_module.g.scenario_run = None

    assert response.status_code == 200
    assert seen["scenario_context"] in (None, "")


def test_post_query_forwards_chat_history_to_agent():
    """Fallback agent queries must receive prior conversation history for follow-up context."""
    mock_agent = MagicMock()
    mock_agent.query.return_value = {
        "answer": "Leadership summary.",
        "tools_used": ["historical_tool"],
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
                    "prompt": "Summarize this for leadership.",
                    "team_filter": "All Teams",
                    "scenario_id": "scenario_1_vm_destroy",
                    "chat_history": [
                        {"role": "user", "content": "Which resources look orphaned or idle for the CI Team?"},
                        {"role": "assistant", "content": "The CI Team's most suspicious resources are res-loadtest-1 and res-loadtest-2."},
                    ],
                },
            )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
            app_module._current_scenario_run = None
            app_module.g.scenario_run = None

    assert response.status_code == 200
    mock_agent.query.assert_called_once()
    call_args, call_kwargs = mock_agent.query.call_args
    assert call_args[0] == "Summarize this for leadership."
    assert "chat_history" in call_kwargs
    history = call_kwargs["chat_history"]
    assert len(history) == 2
    assert isinstance(history[0], HumanMessage)
    assert history[0].content == "Which resources look orphaned or idle for the CI Team?"
    assert isinstance(history[1], AIMessage)
    assert history[1].content == "The CI Team's most suspicious resources are res-loadtest-1 and res-loadtest-2."


def test_post_query_returns_429_for_rate_limit_errors():
    """Provider/model rate-limit errors should surface as a clean 429 instead of a generic 500."""
    mock_agent = MagicMock()
    mock_agent.query.side_effect = Exception("Error code: 429 - {'type': 'rate_limit_exceeded'}")

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
                    "prompt": "Summarize this for leadership.",
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
    assert response.status_code == 429
    assert "rate limit" in body["error"].lower()


def test_concurrent_scenario_switch_keeps_request_local_scenario():
    """Concurrent fallback requests must still answer with their own scenario ids."""
    first_entered = threading.Event()

    mock_agent = MagicMock()

    def query_side_effect(question, chat_history=None):
        scenario_id = getattr(app_module.g.scenario_run, "scenario_id", "none")
        if question == "first fallback query":
            first_entered.set()
            threading.Event().wait(0.2)
            scenario_id = getattr(app_module.g.scenario_run, "scenario_id", "none")
            return {
                "answer": scenario_id,
                "tools_used": [],
                "steps": [],
                "sources": [],
                "intermediate_steps": [],
            }

        if question == "second fallback query":
            return {
                "answer": scenario_id,
                "tools_used": [],
                "steps": [],
                "sources": [],
                "intermediate_steps": [],
            }

        raise AssertionError(f"Unexpected prompt: {question}")

    mock_agent.query.side_effect = query_side_effect

    server = ThreadingHTTPServer(("127.0.0.1", 0), app_module.CORARequestHandler)
    port = server.server_address[1]
    base_url = f"http://127.0.0.1:{port}"
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)

    responses = {}

    def run_request(label, scenario_id, prompt):
        responses[label] = _request(
            base_url,
            "POST",
            "/api/query",
            {
                "prompt": prompt,
                "team_filter": "All Teams",
                "scenario_id": scenario_id,
            },
        )

    with patch.object(app_module, "_get_agent", return_value=mock_agent):
        app_module._current_scenario_run = None
        app_module._set_mode("Mock")
        app_module.g.scenario_run = None
        server_thread.start()
        try:
            first_thread = threading.Thread(
                target=run_request,
                args=("first", "scenario_1_vm_destroy", "first fallback query"),
                daemon=True,
            )
            second_thread = threading.Thread(
                target=run_request,
                args=("second", "scenario_2_tagging", "second fallback query"),
                daemon=True,
            )

            first_thread.start()
            assert first_entered.wait(timeout=2), "First request never reached the agent"
            second_thread.start()

            first_thread.join(timeout=3)
            second_thread.join(timeout=3)
        finally:
            server.shutdown()
            server.server_close()
            server_thread.join(timeout=2)
            app_module._current_scenario_run = None
            app_module.g.scenario_run = None

    assert responses["first"].status_code == 200
    assert responses["second"].status_code == 200
    assert responses["first"].json()["answer"] == "scenario_1_vm_destroy"
    assert responses["second"].json()["answer"] == "scenario_2_tagging"


def test_fallback_agent_worker_thread_inherits_active_scenario():
    """Fallback agent tool work running on another thread must still see the request scenario."""
    mock_agent = MagicMock()

    def query_side_effect(question, chat_history=None):
        seen = {}

        def worker():
            seen["scenario_id"] = getattr(app_module.g.scenario_run, "scenario_id", "none")

        worker_thread = threading.Thread(target=worker, daemon=True)
        worker_thread.start()
        worker_thread.join(timeout=2)
        return {
            "answer": seen.get("scenario_id", "missing"),
            "tools_used": [],
            "steps": [],
            "sources": [],
            "intermediate_steps": [],
        }

    mock_agent.query.side_effect = query_side_effect

    server = ThreadingHTTPServer(("127.0.0.1", 0), app_module.CORARequestHandler)
    port = server.server_address[1]
    base_url = f"http://127.0.0.1:{port}"
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)

    with patch.object(app_module, "_get_agent", return_value=mock_agent):
        app_module._current_scenario_run = None
        app_module._set_mode("Mock")
        app_module.g.scenario_run = None
        server_thread.start()
        try:
            response = _request(
                base_url,
                "POST",
                "/api/query",
                {
                    "prompt": "fallback worker-thread scenario check",
                    "team_filter": "All Teams",
                    "scenario_id": "scenario_2_tagging",
                },
            )
        finally:
            server.shutdown()
            server.server_close()
            server_thread.join(timeout=2)
            app_module._current_scenario_run = None
            app_module.g.scenario_run = None

    assert response.status_code == 200
    assert response.json()["answer"] == "scenario_2_tagging"


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
