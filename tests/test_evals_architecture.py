from unittest.mock import MagicMock, patch

import pytest

import app as app_module
from evals.adapters.workflow_pipeline import WorkflowEvalAdapter
from evals.runners import run_rca_eval


pytestmark = pytest.mark.usefixtures("mock_env")


def test_workflow_eval_adapter_uses_agent_only_path():
    case = {
        "test_id": "case-1",
        "scenario_id": "scenario_1_vm_destroy",
        "user_query": "What is the main reason for the CI Team cost spike in Scenario 1?",
    }

    mock_agent = MagicMock()

    with patch.object(app_module, "_get_agent", return_value=mock_agent), patch.object(
        app_module,
        "_invoke_agent_query",
        return_value={
            "answer": "Agent answer",
            "tools_used": ["cost_api_tool", "pipeline_tool"],
            "intermediate_steps": [],
        },
    ) as invoke_mock, patch.object(
        app_module,
        "_fallback_classify_query_intent",
        return_value="ROOT_CAUSE",
    ), patch.object(
        app_module,
        "_try_handle_mock_scenario_query",
        side_effect=AssertionError("Deterministic workflow path should not be used by eval adapter"),
    ):
        result = WorkflowEvalAdapter(team_filter="All Teams").run_case(case)

    assert result.execution_mode == "agent_only"
    assert result.detected_intent == "GENERAL"
    assert result.classifier_preview == "ROOT_CAUSE"
    assert result.final_output == "Agent answer"
    assert set(result.tools_used) == {"cost_api_tool", "pipeline_tool"}
    invoke_mock.assert_called_once()


def test_rca_runner_uses_workflow_adapter_output_for_label_extraction():
    case = {
        "test_id": "case-2",
        "scenario_id": "scenario_1_vm_destroy",
        "user_query": "What is the main reason for the CI Team cost spike in Scenario 1?",
        "expected_root_cause_label": "failed_cleanup_orphaned_resources",
        "expected_team": "ci-team",
        "expected_service": "load-test environment",
        "reference_answer": "Reference",
        "expected_tool_trajectory": ["pipeline_tool", "cost_api_tool"],
        "notes": "",
    }

    fake_result = MagicMock(
        final_output="destroy-loadtest failed because terraform-destroy hit a state lock and left the load-test environment running.",
        tools_used=["pipeline_tool", "cost_api_tool"],
        sources=["scenario_1_vm_destroy mock pipeline data"],
        detected_intent="ROOT_CAUSE",
        classifier_preview="ROOT_CAUSE",
        execution_mode="agent_only",
    )

    with patch.object(run_rca_eval.WorkflowEvalAdapter, "run_case", return_value=fake_result):
        record = run_rca_eval._run_case(case)

    assert record["execution_mode"] == "agent_only"
    assert record["predicted_root_cause_label"] == "failed_cleanup_orphaned_resources"
    assert record["observed_tools_used"] == ["pipeline_tool", "cost_api_tool"]
