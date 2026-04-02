# Evaluation Usage

This folder now contains two evaluation runners built on the same fixed mock-scenario dataset:

- RCA evaluation for deterministic root-cause labeling
- RAG evaluation for the historical document retrieval + answer synthesis path
- Workflow evaluation for the full mock investigation path in `app.py`

## RCA Runner

From the repo root:

```bash
.venv/bin/python -m evals.runners.run_rca_eval
```

If your shell already resolves the project interpreter, this also works:

```bash
python -m evals.runners.run_rca_eval
```

### RCA Outputs

The RCA runner writes these files under `evals/outputs/`:

- `rca_eval_predictions.json`
- `rca_eval_predictions.csv`
- `rca_eval_metrics.json`
- `rca_eval_confusion_matrix.csv`

### RCA Assumption

For the five numbered mock scenarios, the RCA runner evaluates the canonical deterministic mock root-cause function in `app.py`.

It does not stand up the full LangChain fallback agent, because that is not the primary RCA path for these mock cases today.

### RCA Label Extraction

Predicted RCA labels are extracted from the final answer text only.

The extraction logic uses weighted keyword signals for each canonical label:

- `failed_cleanup_orphaned_resources`
- `tagging_regression_misattribution`
- `autoscaler_no_scale_down`
- `forgotten_poc_environment`
- `application_misconfiguration_over_scaling`

If no label wins clearly, the extractor returns `MANUAL_REVIEW_REQUIRED`.

### RCA Metrics Convention

- Accuracy: standard exact-match accuracy
- Precision: macro average
- Recall: macro average
- F1-score: macro average

Confusion matrix rows are actual labels and columns are predicted labels.

## RAG Runner

The RAG runner reuses the same `evals/dataset/mock_scenarios_starter.json` file and evaluates the current `historical_tool` pipeline:

1. retrieve top-k chunks from Chroma
2. synthesize a final answer from those chunks
3. score the retrieved contexts and answer against the dataset's `reference_answer`

### Optional RAG Eval Dependencies

The RAG runner prefers direct RAGAS scoring. Install the extra packages first if they are not already present:

```bash
uv pip install --python .venv/bin/python -r evals/requirements-rag.txt
```

### Run RAG Eval

Direct RAGAS scoring:

```bash
KMP_DUPLICATE_LIB_OK=TRUE OMP_NUM_THREADS=1 .venv/bin/python -m evals.runners.run_rag_eval --mode ragas
```

Auto mode, which falls back to a local approximation if RAGAS or the judge model cannot initialize:

```bash
KMP_DUPLICATE_LIB_OK=TRUE OMP_NUM_THREADS=1 .venv/bin/python -m evals.runners.run_rag_eval --mode auto
```

Local-only fallback scoring:

```bash
.venv/bin/python -m evals.runners.run_rag_eval --mode local
```

Optional knobs:

- `--top-k 5` to score more retrieved chunks per query
- `--dataset path/to/file.json` to point at a different fixed eval set

### RAG Outputs

The RAG runner writes these files under `evals/outputs/`:

- `rag_eval_predictions.json`
- `rag_eval_predictions.csv`
- `rag_eval_metrics.json`

### RAG Metrics

When RAGAS is available, the runner scores:

- `context_precision`
- `context_recall`
- `faithfulness`
- `answer_relevancy`

If RAGAS cannot run, the runner writes the same output files using a local heuristic fallback and records the reason in `rag_eval_metrics.json`.

## Workflow Runner

The workflow runner evaluates the full mock investigation path for each fixed dataset case:

1. classify the user query
2. run the current mock workflow dispatch in `app.py`
3. capture the final answer, tool usage, and step trajectory
4. score response match, rubric quality, and tool trajectory

### Run Workflow Eval

From the repo root:

```bash
.venv/bin/python -m evals.runners.run_workflow_eval
```

### Workflow Outputs

The workflow runner writes these files under `evals/outputs/`:

- `workflow_eval_predictions.json`
- `workflow_eval_predictions.csv`
- `workflow_eval_metrics.json`

### Workflow Metrics

The current workflow evaluator is local and structured rather than ADK-backed. It reports:

- `response_match_f1`
- `rubric_score`
- `tool_trajectory_score`
- `tool_trajectory_exact_match_rate`

Per-case outputs also include:

- detected intent
- execution mode (`mock_direct` vs `fallback_agent`)
- predicted root-cause label
- rubric breakdown
- observed tool steps and sources

### Why This Is Not ADK Yet

Google ADK integration is not straightforward in the current repo because:

- there is no `google.adk` dependency or ADK-native runtime in the project
- the app uses a custom HTTP handler plus LangChain/Groq agent objects, not ADK sessions and runners
- tool traces are exposed only as app-local `steps`/`tools_used`, not as ADK evaluation events

For full ADK support, the workflow would need an ADK-native agent wrapper, ADK-compatible trace emission, and an evaluator wired against that runtime instead of the current custom `app.py` dispatch path.

## Run Everything

To refresh RCA, RAG, workflow, benchmarking, and thesis-ready tables in one command:

```bash
.venv/bin/python -m evals.runners.run_all_evals --rag-mode auto
```

## Workflow Runner

The workflow runner evaluates the end-to-end app workflow for each fixed eval case:

1. classify the query
2. run the same mock/direct or fallback-agent dispatch path used by `app.py`
3. score the final answer against the dataset reference answer
4. score the observed tool trajectory against `expected_tool_trajectory`

### Run Workflow Eval

From the repo root:

```bash
.venv/bin/python -m evals.runners.run_workflow_eval
```

### Workflow Outputs

The workflow runner writes these files under `evals/outputs/`:

- `workflow_eval_predictions.json`
- `workflow_eval_predictions.csv`
- `workflow_eval_metrics.json`

### Workflow Scores

The local structured evaluator records:

- `response_match_f1`
- `rubric_score`
- `tool_trajectory_score`
- `tool_trajectory_exact_match_rate`

Per-case outputs also include:

- detected intent
- execution mode (`mock_direct` or `fallback_agent`)
- predicted root-cause label extracted from the final response
- rubric breakdown
- observed tools, steps, and sources

### Why This Is Not ADK-Native Yet

Google ADK integration is not straightforward in the current repo because:

- the app uses a custom HTTP workflow in `app.py`, not an ADK runtime
- the main agent is a LangChain/Groq agent, not a Google ADK agent
- the current workflow exposes app-local `steps` and `tools_used`, but not ADK-native evaluation traces or session artifacts
- `google.adk` is not currently a project dependency

To support full ADK evaluation later, the repo would need:

- an ADK-native wrapper around the current workflow or a migrated agent runtime
- structured ADK trace/event emission for tool calls and intermediate reasoning steps
- dataset-to-ADK input/output mapping for the mock scenario harness
