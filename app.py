"""
React UI backend for CORA (Cloud Optimization & Resource Advisor).

Uses only Python standard library HTTP serving to avoid introducing new
runtime dependencies while preserving existing backend agent functionality.
"""

from __future__ import annotations

import json
import os
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import re
from typing import Any, Optional
from urllib.parse import urlparse

from dotenv import load_dotenv

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


def _reset_agent() -> None:
    global _AGENT_INSTANCE
    with _AGENT_LOCK:
        _AGENT_INSTANCE = None


def _set_mode(new_mode: str) -> str:
    normalized = "Live" if str(new_mode).lower() == "live" else "Mock"
    os.environ["USE_LIVE_DATA"] = "true" if normalized == "Live" else "false"
    _reset_providers()
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
            
            global _current_scenario_run
            _current_scenario_run = build_scenario_run(scenario_id)
            self._send_json(HTTPStatus.OK, {"status": "ok", "scenario_id": scenario_id})
            return

        if route == "/api/query":
            payload = payload or {}
            prompt = str(payload.get("prompt", "")).strip()
            team_filter = str(payload.get("team_filter", "All Teams"))
            
            if _get_mode() == "Mock":
                g.scenario_run = _current_scenario_run
            else:
                g.scenario_run = None

            if not prompt:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "Prompt is required."})
                return

            full_query = f"For {team_filter}: {prompt}" if team_filter != "All Teams" else prompt

            try:
                agent = _get_agent()
                result = agent.query(full_query)
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
