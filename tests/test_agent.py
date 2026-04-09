"""Unit tests for CloudCostAgent query input construction."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


pytest.importorskip("langchain_groq")

from src.agent import CloudCostAgent  # noqa: E402


def test_query_prepends_scenario_context_to_input():
    agent = CloudCostAgent()
    agent._agent_executor = MagicMock()
    agent._agent_executor.invoke.return_value = {
        "output": "done",
        "intermediate_steps": [],
    }

    result = agent.query(
        "Why did costs spike?",
        chat_history=None,
        scenario_context="Active investigation scenario: scenario_3_autoscaler",
    )

    invoke_input = agent._agent_executor.invoke.call_args[0][0]
    assert invoke_input["input"] == (
        "Active investigation scenario: scenario_3_autoscaler\n\nWhy did costs spike?"
    )
    assert invoke_input["chat_history"] == []
    assert result["question"] == "Why did costs spike?"


def test_query_uses_plain_question_when_no_scenario_context():
    agent = CloudCostAgent()
    agent._agent_executor = MagicMock()
    agent._agent_executor.invoke.return_value = {
        "output": "plain",
        "intermediate_steps": [],
    }

    agent.query("List the top resources.", chat_history=[])

    invoke_input = agent._agent_executor.invoke.call_args[0][0]
    assert invoke_input["input"] == "List the top resources."
    assert invoke_input["chat_history"] == []


def test_query_forwards_chat_history_and_extracts_tools_used():
    agent = CloudCostAgent()
    agent._agent_executor = MagicMock()
    agent._agent_executor.invoke.return_value = {
        "output": "investigation",
        "intermediate_steps": [
            (SimpleNamespace(tool="cost_api_tool"), "cost output"),
            (SimpleNamespace(tool="pipeline_tool"), "pipeline output"),
            (SimpleNamespace(tool="cost_api_tool"), "cost output 2"),
        ],
    }
    chat_history = [MagicMock(), MagicMock()]

    result = agent.query("Explain the spike.", chat_history=chat_history, scenario_context="")

    invoke_input = agent._agent_executor.invoke.call_args[0][0]
    assert invoke_input["chat_history"] is chat_history
    assert set(result["tools_used"]) == {"cost_api_tool", "pipeline_tool"}
