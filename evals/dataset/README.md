# Evaluation Dataset Layer

This folder contains only the dataset layer for evaluating the five numbered mock scenarios.

It does not include runners, scoring code, or report generation yet.

## Files

- `schema.json`
  JSON Schema for the dataset structure.
- `mock_scenarios_starter.json`
  Starter dataset with one canonical root-cause test case per numbered mock scenario.

## Scope

The starter dataset is grounded in the current repo implementation:

- Scenario data: `src/scenarios/__init__.py`
- Deterministic mock root-cause answers: `app.py` in `_build_mock_root_cause_result`

The legacy scenario `scenario_legacy_mock` is intentionally excluded from this starter set.

## Field Guide

- `test_id`
  Stable unique id for the eval case.
- `scenario_id`
  One of the five numbered mock scenarios.
- `user_query`
  The prompt you expect to send during evaluation.
- `expected_root_cause_label`
  Your canonical grading label for the main cause.
- `expected_team`
  The responsible team id, usually `ci-team`, `release-team`, or `cloudops-team`.
- `expected_service`
  The affected workload or service-like concept.
  For config or allocation issues, this can be a control-plane label such as `resource-tagging`.
- `reference_answer`
  A concise gold answer to compare against model output.
- `expected_tool_trajectory`
  Expected tool order for the canonical answer path.
  For the current deterministic root-cause path, this is usually `["pipeline_tool", "cost_api_tool"]`.
- `notes`
  Free-form provenance, caveats, or manual review guidance.

## Placeholder Convention

If you add new cases and cannot infer a ground-truth field from the repo, use this exact placeholder:

`MANUAL_REVIEW_REQUIRED`

When you use that placeholder, explain what is missing in `notes`.

## Recommended Next Edits

- Add more than one query per scenario once you decide your evaluation prompt set.
- Freeze your label taxonomy before building runners.
- Keep `reference_answer` short and factual so later grading logic can compare evidence cleanly.
