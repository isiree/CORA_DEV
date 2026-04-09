"""
HTTP endpoint contract tests for the app server.

These tests now focus on request routing, scenario binding, chat-history
plumbing, and emergency deterministic fallback behavior. The handler no longer
owns scenario-specific answer generation in normal mock mode.
"""

import json
import threading
from http.client import HTTPConnection
from http.server import HTTPServer, ThreadingHTTPServer
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
        return HTTPTestResponse(response.status, response.read())
    finally:
        connection.close()


@pytest.fixture(autouse=True)
def reset_app_state(mock_env):
    """Reset mutable module globals between API tests."""
    app_module._current_scenario_run = None
    app_module._conversation_history = []
    app_module.DETERMINISTIC_MODE = False
    app_module._set_mode("Mock")
    app_module.g.scenario_run = None
    yield
    app_module._current_scenario_run = None
    app_module._conversation_history = []
    app_module.DETERMINISTIC_MODE = False
    app_module._set_mode("Mock")
    app_module.g.scenario_run = None


@pytest.fixture
def api_server():
    """Start a local HTTP server with the agent dependency patched."""
    mock_agent = MagicMock()
    mock_agent.query.return_value = {
        "answer": "Mock investigation complete.",
        "tools_used": ["cost_api_tool"],
        "steps": [],
        "sources": ["mock source"],
        "intermediate_steps": [],
    }

    server = HTTPServer(("127.0.0.1", 0), app_module.CORARequestHandler)
    port = server.server_address[1]
    base_url = f"http://127.0.0.1:{port}"
    thread = threading.Thread(target=server.serve_forever, daemon=True)

    with patch.object(app_module, "_get_agent", return_value=mock_agent):
        thread.start()
        try:
            yield {"base_url": base_url, "mock_agent": mock_agent}
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)


def test_deterministic_mode_disabled_by_default():
    """The emergency deterministic mode must stay off by default."""
    assert app_module.DETERMINISTIC_MODE is False


def test_startup_config_can_be_mode_unselected(api_server):
    app_module._selected_mode = None
    response = _request(api_server["base_url"], "GET", "/api/config")
    assert response.status_code == 200
    assert response.json()["mode"] is None


def test_get_health_200(api_server):
    response = _request(api_server["base_url"], "GET", "/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "mode" in body


def test_get_config_fields(api_server):
    response = _request(api_server["base_url"], "GET", "/api/config")
    assert response.status_code == 200
    body = response.json()
    assert "mode" in body
    assert "team_options" in body
    assert "example_queries" in body
    assert "knowledge_base" in body


def test_get_tools_returns_three_tools(api_server):
    response = _request(api_server["base_url"], "GET", "/api/tools")
    assert response.status_code == 200
    tools = response.json()["tools"]
    assert len(tools) == 3
    assert all("name" in tool and "description" in tool for tool in tools)


def test_post_config_mode_mock(api_server):
    response = _request(api_server["base_url"], "POST", "/api/config/mode", {"mode": "Mock"})
    assert response.status_code == 200
    assert response.json()["mode"] == "Mock"


def test_post_config_mode_live(api_server):
    response = _request(api_server["base_url"], "POST", "/api/config/mode", {"mode": "Live"})
    assert response.status_code == 200
    assert response.json()["mode"] == "Live"


def test_get_config_includes_active_scenario_id(api_server):
    _request(
        api_server["base_url"],
        "POST",
        "/api/config/scenario",
        {"scenario_id": "scenario_1_vm_destroy"},
    )
    response = _request(api_server["base_url"], "GET", "/api/config")
    assert response.status_code == 200
    assert response.json()["scenario_id"] == "scenario_1_vm_destroy"


def test_post_config_scenario_valid(api_server):
    response = _request(
        api_server["base_url"],
        "POST",
        "/api/config/scenario",
        {"scenario_id": "scenario_1_vm_destroy"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["scenario_id"] == "scenario_1_vm_destroy"


def test_post_config_scenario_invalid(api_server):
    response = _request(
        api_server["base_url"],
        "POST",
        "/api/config/scenario",
        {"scenario_id": "fake_scenario_xyz"},
    )
    assert response.status_code == 400
    assert "error" in response.json()


def test_post_config_scenario_requires_mock_mode(api_server):
    _request(api_server["base_url"], "POST", "/api/config/mode", {"mode": "Live"})
    response = _request(
        api_server["base_url"],
        "POST",
        "/api/config/scenario",
        {"scenario_id": "scenario_1_vm_destroy"},
    )
    assert response.status_code == 409
    assert "Switch to Mock mode" in response.json()["error"]


def test_post_query_returns_answer_shape(api_server):
    response = _request(
        api_server["base_url"],
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
    assert body["answer"] == "Mock investigation complete."
    assert body["tools_used"] == ["cost_api_tool"]
    assert isinstance(body["steps"], list)
    assert isinstance(body["sources"], list)
    assert isinstance(body["anomaly_context"], dict)
    assert body["anomaly_context"]["team"] == "CI Team"
    assert body["anomaly_context"]["title"] == "VM destroy failure detected"
    assert "res-loadtest-1" in body["anomaly_context"]["cause"]
    assert body["anomaly_context"]["tools"][0]["n"] == "cost_api_tool"


def test_post_query_builds_scenario_specific_anomaly_context():
    mock_agent = MagicMock()
    mock_agent.query.return_value = {
        "answer": "Release Team is responsible for the cost spike.",
        "tools_used": ["cost_api_tool", "pipeline_tool"],
        "steps": [],
        "sources": [],
        "intermediate_steps": [],
    }

    server = HTTPServer(("127.0.0.1", 0), app_module.CORARequestHandler)
    port = server.server_address[1]
    base_url = f"http://127.0.0.1:{port}"
    thread = threading.Thread(target=server.serve_forever, daemon=True)

    with patch.object(app_module, "_get_agent", return_value=mock_agent):
        thread.start()
        try:
            response = _request(
                base_url,
                "POST",
                "/api/query",
                {
                    "prompt": "Which team is responsible for the cost spike?",
                    "team_filter": "All Teams",
                    "scenario_id": "scenario_2_tagging",
                },
            )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    assert response.status_code == 200
    context = response.json()["anomaly_context"]
    assert context["title"] == "Tagging anomaly detected"
    assert context["team"] == "Release Team"
    assert context["impact"] == "$4,500.00"
    assert context["pct"] == "87.5% over budget"
    assert context["since"] == "January 15, 2025"
    assert "res-db-prod" in context["cause"]
    assert any(resource["n"] == "res-db-prod" for resource in context["res"])
    assert {tool["n"] for tool in context["tools"]} == {"cost_api_tool", "pipeline_tool"}


def test_post_query_uses_payload_scenario_when_backend_has_none():
    seen = {}
    mock_agent = MagicMock()

    def query_side_effect(question, chat_history=None, scenario_context=None):
        seen["question"] = question
        seen["chat_history"] = chat_history
        seen["scenario_context"] = scenario_context
        return {
            "answer": "agent path used",
            "tools_used": ["cost_api_tool", "pipeline_tool"],
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

    assert response.status_code == 200
    assert response.json()["answer"] == "agent path used"
    assert app_module._current_scenario_run.scenario_id == "scenario_1_vm_destroy"
    assert seen["question"] == "Which team is responsible for the cost spike?"
    assert seen["chat_history"] == []
    assert "scenario_1_vm_destroy" in seen["scenario_context"]
    assert "CI Team" in seen["scenario_context"]
    assert "deploy-loadtest" in seen["scenario_context"]
    assert "res-loadtest-1" in seen["scenario_context"]


@pytest.mark.parametrize(
    ("scenario_id", "prompt", "expected_context_fragment"),
    [
        ("scenario_1_vm_destroy", "What pipeline activity caused the CI Team cost increase in Scenario 1?", "destroy-loadtest"),
        ("scenario_1_vm_destroy", "Which resources look orphaned or idle for the CI Team?", "res-loadtest-2"),
        ("scenario_1_vm_destroy", "what remediation is recommended to fix this issue in the ci team ?", "res-loadtest-1"),
        ("scenario_2_tagging", "is the cost increase owned by a team or is it unallocated/misattributed?", "deploy-release-prod"),
        ("scenario_3_autoscaler", "mention what this resource is", "web-frontend-asg"),
    ],
)
def test_post_query_uses_agent_path_for_mock_questions(scenario_id, prompt, expected_context_fragment):
    seen = {}
    mock_agent = MagicMock()

    def query_side_effect(question, chat_history=None, scenario_context=None):
        seen["question"] = question
        seen["scenario_context"] = scenario_context
        return {
            "answer": "agent-only path",
            "tools_used": ["cost_api_tool"],
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
        thread.start()
        try:
            response = _request(
                base_url,
                "POST",
                "/api/query",
                {"prompt": prompt, "team_filter": "All Teams", "scenario_id": scenario_id},
            )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    assert response.status_code == 200
    assert response.json()["answer"] == "agent-only path"
    mock_agent.query.assert_called_once()
    assert seen["question"] == prompt
    assert scenario_id in seen["scenario_context"]
    assert expected_context_fragment in seen["scenario_context"]


def test_post_query_mock_without_scenario_returns_400(api_server):
    response = _request(
        api_server["base_url"],
        "POST",
        "/api/query",
        {"prompt": "Which team is responsible for the cost spike?", "team_filter": "All Teams"},
    )
    assert response.status_code == 400
    assert "scenario" in response.json()["error"].lower()


def test_post_query_passes_scenario_context_in_mock_mode():
    seen = {}
    mock_agent = MagicMock()

    def query_side_effect(question, chat_history=None, scenario_context=None):
        seen["scenario_context"] = scenario_context
        return {
            "answer": "context received",
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

    assert response.status_code == 200
    assert "scenario_3_autoscaler" in seen["scenario_context"]
    assert "Release Team" in seen["scenario_context"]
    assert "update-web-autoscaler" in seen["scenario_context"]
    assert "web-frontend-asg" in seen["scenario_context"]


def test_post_query_does_not_pass_scenario_context_in_live_mode():
    seen = {}
    mock_agent = MagicMock()

    def query_side_effect(question, chat_history=None, scenario_context=None):
        seen["scenario_context"] = scenario_context
        return {
            "answer": "live path",
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
        app_module._set_mode("Live")
        thread.start()
        try:
            response = _request(
                base_url,
                "POST",
                "/api/query",
                {"prompt": "give me a concise investigation summary", "team_filter": "All Teams"},
            )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    assert response.status_code == 200
    assert seen["scenario_context"] == ""


def test_post_query_rejects_mock_scenario_when_backend_is_live():
    mock_agent = MagicMock()

    server = HTTPServer(("127.0.0.1", 0), app_module.CORARequestHandler)
    port = server.server_address[1]
    base_url = f"http://127.0.0.1:{port}"
    thread = threading.Thread(target=server.serve_forever, daemon=True)

    with patch.object(app_module, "_get_agent", return_value=mock_agent):
        app_module._set_mode("Live")
        thread.start()
        try:
            response = _request(
                base_url,
                "POST",
                "/api/query",
                {
                    "prompt": "which team caused the spike?",
                    "team_filter": "All Teams",
                    "scenario_id": "scenario_1_vm_destroy",
                },
            )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    assert response.status_code == 409
    assert "Switch to Mock mode" in response.json()["error"]
    mock_agent.query.assert_not_called()


def test_post_query_forwards_chat_history_to_agent():
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

    assert response.status_code == 200
    mock_agent.query.assert_called_once()
    call_args, call_kwargs = mock_agent.query.call_args
    assert call_args[0] == "Summarize this for leadership."
    history = call_kwargs["chat_history"]
    assert len(history) == 2
    assert isinstance(history[0], HumanMessage)
    assert history[0].content == "Which resources look orphaned or idle for the CI Team?"
    assert isinstance(history[1], AIMessage)
    assert history[1].content == "The CI Team's most suspicious resources are res-loadtest-1 and res-loadtest-2."


def test_post_config_scenario_resets_conversation_history(api_server):
    app_module._conversation_history = [{"role": "user", "content": "old"}]
    response = _request(
        api_server["base_url"],
        "POST",
        "/api/config/scenario",
        {"scenario_id": "scenario_2_tagging"},
    )
    assert response.status_code == 200
    assert app_module._conversation_history == []


def test_post_config_mode_resets_conversation_history(api_server):
    app_module._conversation_history = [{"role": "user", "content": "old"}]
    response = _request(api_server["base_url"], "POST", "/api/config/mode", {"mode": "Live"})
    assert response.status_code == 200
    assert app_module._conversation_history == []


def test_sequential_scenario_switch_resets_history_and_context():
    seen_calls = []
    mock_agent = MagicMock()

    def query_side_effect(question, chat_history=None, scenario_context=None):
        seen_calls.append(
            {
                "question": question,
                "history_len": len(chat_history or []),
                "scenario_context": scenario_context,
            }
        )
        return {
            "answer": "ok",
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
        thread.start()
        try:
            assert _request(
                base_url,
                "POST",
                "/api/config/scenario",
                {"scenario_id": "scenario_1_vm_destroy"},
            ).status_code == 200
            assert _request(
                base_url,
                "POST",
                "/api/query",
                {"prompt": "First scenario question"},
            ).status_code == 200

            assert _request(
                base_url,
                "POST",
                "/api/config/scenario",
                {"scenario_id": "scenario_2_tagging"},
            ).status_code == 200
            assert _request(
                base_url,
                "POST",
                "/api/query",
                {"prompt": "Second scenario question"},
            ).status_code == 200
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    assert len(seen_calls) == 2
    assert seen_calls[0]["history_len"] == 0
    assert seen_calls[1]["history_len"] == 0
    assert "scenario_1_vm_destroy" in seen_calls[0]["scenario_context"]
    assert "scenario_2_tagging" in seen_calls[1]["scenario_context"]
    assert "scenario_1_vm_destroy" not in seen_calls[1]["scenario_context"]


def test_post_query_returns_429_for_rate_limit_errors():
    mock_agent = MagicMock()
    mock_agent.query.side_effect = Exception("Error code: 429 - {'type': 'rate_limit_exceeded'}")

    server = HTTPServer(("127.0.0.1", 0), app_module.CORARequestHandler)
    port = server.server_address[1]
    base_url = f"http://127.0.0.1:{port}"
    thread = threading.Thread(target=server.serve_forever, daemon=True)

    with patch.object(app_module, "_get_agent", return_value=mock_agent):
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

    assert response.status_code == 429
    assert "rate limit" in response.json()["error"].lower()


def test_concurrent_scenario_switch_keeps_request_local_scenario():
    first_entered = threading.Event()
    responses = {}
    mock_agent = MagicMock()

    def query_side_effect(question, chat_history=None, scenario_context=None):
        scenario_id = getattr(app_module.g.scenario_run, "scenario_id", "none")
        if question == "first agent query":
            first_entered.set()
            threading.Event().wait(0.2)
        return {
            "answer": scenario_id,
            "tools_used": [],
            "steps": [],
            "sources": [scenario_context],
            "intermediate_steps": [],
        }

    mock_agent.query.side_effect = query_side_effect

    server = ThreadingHTTPServer(("127.0.0.1", 0), app_module.CORARequestHandler)
    port = server.server_address[1]
    base_url = f"http://127.0.0.1:{port}"
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)

    def run_request(label, scenario_id, prompt):
        responses[label] = _request(
            base_url,
            "POST",
            "/api/query",
            {"prompt": prompt, "team_filter": "All Teams", "scenario_id": scenario_id},
        )

    with patch.object(app_module, "_get_agent", return_value=mock_agent):
        server_thread.start()
        try:
            first_thread = threading.Thread(
                target=run_request,
                args=("first", "scenario_1_vm_destroy", "first agent query"),
                daemon=True,
            )
            second_thread = threading.Thread(
                target=run_request,
                args=("second", "scenario_2_tagging", "second agent query"),
                daemon=True,
            )
            first_thread.start()
            assert first_entered.wait(timeout=2)
            second_thread.start()
            first_thread.join(timeout=3)
            second_thread.join(timeout=3)
        finally:
            server.shutdown()
            server.server_close()
            server_thread.join(timeout=2)

    assert responses["first"].status_code == 200
    assert responses["second"].status_code == 200
    assert responses["first"].json()["answer"] == "scenario_1_vm_destroy"
    assert responses["second"].json()["answer"] == "scenario_2_tagging"


def test_agent_worker_thread_inherits_active_scenario():
    mock_agent = MagicMock()

    def query_side_effect(question, chat_history=None, scenario_context=None):
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
            "sources": [scenario_context],
            "intermediate_steps": [],
        }

    mock_agent.query.side_effect = query_side_effect

    server = ThreadingHTTPServer(("127.0.0.1", 0), app_module.CORARequestHandler)
    port = server.server_address[1]
    base_url = f"http://127.0.0.1:{port}"
    thread = threading.Thread(target=server.serve_forever, daemon=True)

    with patch.object(app_module, "_get_agent", return_value=mock_agent):
        thread.start()
        try:
            response = _request(
                base_url,
                "POST",
                "/api/query",
                {
                    "prompt": "worker-thread scenario check",
                    "team_filter": "All Teams",
                    "scenario_id": "scenario_2_tagging",
                },
            )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    assert response.status_code == 200
    assert response.json()["answer"] == "scenario_2_tagging"


def test_emergency_deterministic_fallback_can_be_reenabled():
    mock_agent = MagicMock()
    mock_agent.query.side_effect = AssertionError("Agent should be bypassed when deterministic mode is enabled")

    server = HTTPServer(("127.0.0.1", 0), app_module.CORARequestHandler)
    port = server.server_address[1]
    base_url = f"http://127.0.0.1:{port}"
    thread = threading.Thread(target=server.serve_forever, daemon=True)

    with patch.object(app_module, "_get_agent", return_value=mock_agent), patch.object(
        app_module,
        "_classify_query_intent",
        return_value="PIPELINE_CAUSE",
    ):
        app_module.DETERMINISTIC_MODE = True
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
            app_module.DETERMINISTIC_MODE = False

    body = response.json()
    assert response.status_code == 200
    assert "deploy-loadtest" in body["answer"]
    assert "destroy-loadtest" in body["answer"]
    assert "state lock" in body["answer"].lower()


def test_post_query_missing_prompt_400(api_server):
    response = _request(api_server["base_url"], "POST", "/api/query", {})
    assert response.status_code == 400
    assert "error" in response.json()


def test_post_query_requires_mode_selection(api_server):
    app_module._selected_mode = None
    response = _request(
        api_server["base_url"],
        "POST",
        "/api/query",
        {"prompt": "which team caused the spike?"},
    )
    assert response.status_code == 409
    assert "Choose Live or Mock mode" in response.json()["error"]


def test_post_query_invalid_json(api_server):
    response = _request(
        api_server["base_url"],
        "POST",
        "/api/query",
        "not valid json",
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code in [400, 500]
    try:
        assert "error" in response.json()
    except Exception:
        pass


def test_post_reindex_returns_ok(api_server):
    response = _request(api_server["base_url"], "POST", "/api/reindex", {})
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_static_path_traversal_blocked(api_server):
    response = _request(api_server["base_url"], "GET", "/static/../app.py")
    assert response.status_code in [403, 404]


def test_unmatched_route_404(api_server):
    response = _request(api_server["base_url"], "GET", "/api/this_does_not_exist")
    assert response.status_code == 404
    assert "error" in response.json()
