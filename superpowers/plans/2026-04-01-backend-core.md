# Backend Core — TDD Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers-extended-cc:subagent-driven-development (recommended) or superpowers-extended-cc:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement all core Pydantic models that define the API contract between frontend and backend. These models drive OpenAPI schema generation which in turn generates frontend TypeScript types.

**Architecture:** All models live in `backend/src/bioimageflow_server/models/`. Pydantic v2 with strict typing. Edge type uses a discriminated union on the `type` field. Models are tested for serialization round-trips, default values, and validation constraints.

**Tech Stack:** Python 3.12, Pydantic v2, pytest

**User Verification:** NO

**Prerequisites:** Project scaffolding complete (Task 1 of scaffolding plan). `backend/` package installable with `uv sync`.

**Cross-plan dependency:** Task 5 imports `ErrorResponse` from `models/errors.py`, which is created by the scaffolding plan. The scaffolding plan must be complete before Task 5 can run.

---

## File Structure

```
backend/src/bioimageflow_server/models/
├── __init__.py          # Re-exports all models
├── graph.py             # NodeState, ColumnRefEdge, PositionalEdge, Edge, GraphState
├── validation.py        # NodeStatus, GraphValidationError, ValidationResult
├── execution.py         # ExecutionRequest, ProgressInfo, ExecutionResult, ExecutionStatus
├── workflow.py          # WorkflowCreate, WorkflowInfo, WorkflowUpdate, WorkflowFile
├── settings.py          # OMEROInstance, Settings
├── tools.py             # ToolMetadata, PackageInfo (already planned in tools-panel plan)
├── errors.py            # ErrorResponse (already planned in scaffolding plan)

backend/tests/test_models/
├── __init__.py
├── test_graph.py
├── test_validation.py
├── test_execution.py
├── test_workflow.py
├── test_settings.py
```

---

### Task 1: Graph Models — NodeState + Edge union + GraphState

**Files:**
- Create: `backend/src/bioimageflow_server/models/graph.py`
- Create: `backend/tests/test_models/test_graph.py`

**Models to implement:** Fields match gui_specs_v1.md Section 2.4.3 schema definitions exactly.

**NodeState** — a node in the graph, sent by frontend, saved to disk:

| Field | Type | Default |
|-------|------|---------|
| `id` | `str` | required |
| `name` | `str` | required |
| `tool_name` | `str` | required |
| `position` | `tuple[float, float]` | required |
| `parameters` | `dict[str, Any]` | required |
| `resources` | `dict[str, Any]` | `{}` |
| `output_templates` | `dict[str, str]` | `{}` |
| `enabled` | `bool` | `True` |
| `collapsed` | `bool` | `False` |

**ColumnRefEdge** — binds an output column to an input field (ProcessingTool keyword binding):
- `type: Literal["column_ref"]` (discriminator), `id`, `source_node`, `target_node`, `source_output`, `target_input` — all `str`, all required.

**PositionalEdge** — connects a node as positional upstream to a DataFrameTool:
- `type: Literal["positional"]` (discriminator), `id`, `source_node`, `target_node` — all `str`, all required. `positional_index: int` required.

**Edge** — discriminated union on `type` field using `Annotated[..., Discriminator("type")]`. This eliminates invalid states and produces clean TypeScript types from OpenAPI (see spec Section 2.4.3 rationale).

**GraphState** — `nodes: list[NodeState]`, `edges: list[Edge]`.

**Tests** (`test_graph.py`):
- [ ] Test NodeState with all fields populated, verify values
- [ ] Test NodeState defaults (resources, output_templates, enabled, collapsed)
- [ ] Test NodeState requires `id` (missing field raises ValidationError)
- [ ] Test NodeState dict and JSON round-trip serialization
- [ ] Test ColumnRefEdge construction and `type == "column_ref"`
- [ ] Test PositionalEdge construction and `type == "positional"`
- [ ] Test Edge discriminated union dispatches to correct type from dict
- [ ] Test Edge discriminated union rejects unknown `type` values
- [ ] Test Edge JSON round-trip preserves type discriminator
- [ ] Test GraphState with empty nodes/edges
- [ ] Test GraphState with mixed edge types (both ColumnRef and Positional)
- [ ] Test GraphState JSON round-trip preserves edge types through discriminated union

**TDD cycle:** Write all tests first, verify they fail (ImportError), implement models, verify all pass, commit.

---

### Task 2: Validation Models — NodeStatus + GraphValidationError + ValidationResult

**Files:**
- Create: `backend/src/bioimageflow_server/models/validation.py`
- Create: `backend/tests/test_models/test_validation.py`

**Models to implement:** Fields match gui_specs_v1.md Section 2.4.3 schema definitions.

**NodeStatus** — server-computed status for a node (returned by validation and WebSocket `node_state` messages):

| Field | Type | Default |
|-------|------|---------|
| `node_id` | `str` | required |
| `status` | `Literal["unexecuted", "executed", "out_of_date", "disabled", "running", "failed"]` | required |
| `cached` | `bool` | required |
| `error` | `str \| None` | `None` |
| `traceback` | `str \| None` | `None` |

Design note: NodeStatus is intentionally separate from NodeState — NodeState flows frontend-to-backend, NodeStatus flows backend-to-frontend (see spec Section 2.4.3 "NodeStatus separation").

**GraphValidationError** — a single validation error:

| Field | Type | Default |
|-------|------|---------|
| `type` | `Literal["cycle_detected", "type_incompatible", "parameter_invalid", "missing_tool", "missing_connection", "missing_package", "invalid_node_id", "invalid_edge_id"]` | required |
| `detail` | `str` | required |
| `node` | `str \| None` | `None` |
| `edge_id` | `str \| None` | `None` |
| `field` | `str \| None` | `None` |

**ValidationResult** — response from `PUT /graph`:

| Field | Type | Default |
|-------|------|---------|
| `valid` | `bool` | required |
| `node_statuses` | `dict[str, NodeStatus]` | `{}` |
| `errors` | `list[GraphValidationError]` | `[]` |

**Tests** (`test_validation.py`):
- [ ] Test NodeStatus minimal (error and traceback default to None)
- [ ] Test NodeStatus with failed status including error and traceback
- [ ] Test NodeStatus accepts all 6 valid status strings
- [ ] Test NodeStatus rejects invalid status strings (e.g., "bogus")
- [ ] Test GraphValidationError with all fields and with minimal fields (optional fields None)
- [ ] Test GraphValidationError accepts all 8 valid error types
- [ ] Test GraphValidationError rejects invalid type strings
- [ ] Test ValidationResult with valid=True and populated node_statuses
- [ ] Test ValidationResult with valid=False and errors list
- [ ] Test ValidationResult defaults (empty node_statuses and errors)
- [ ] Test ValidationResult JSON round-trip with nested NodeStatus and errors

**TDD cycle:** Write all tests first, verify they fail, implement models, verify all pass, commit.

---

### Task 3: Execution Models — ExecutionRequest + ProgressInfo + ExecutionResult + ExecutionStatus

**Files:**
- Create: `backend/src/bioimageflow_server/models/execution.py`
- Create: `backend/tests/test_models/test_execution.py`

**Models to implement:** Matches gui_specs_v1.md Section 2.4.5 execution status response and endpoint descriptions.

**ExecutionRequest** — body for `POST /execution/run`:
- `graph: dict[str, Any]` — GraphState as dict (validated separately when building Workflow)
- `nodes: list[str] | None = None` — specific nodes to run, or None for all enabled unexecuted/out-of-date

**ProgressInfo** — current execution progress (matches spec Section 2.4.5 `progress` field):
- `node_id: str`, `row: int`, `total_rows: int` — all required

**ExecutionResult** — final result of execution (also used in `execution_complete` WebSocket message):
- `success: bool` required, `errors: list[dict[str, Any]] = []`, `node_statuses: dict[str, NodeStatus] = {}`
- Imports NodeStatus from validation module

**ExecutionStatus** — response from `GET /execution/status`:
- `state: Literal["running", "idle"]` required
- `last_result: ExecutionResult | None = None`
- `progress: ProgressInfo | None = None`

**Tests** (`test_execution.py`):
- [ ] Test ExecutionRequest full run (nodes=None means run all)
- [ ] Test ExecutionRequest selective run (specific node IDs)
- [ ] Test ProgressInfo construction
- [ ] Test ExecutionResult success (empty errors default)
- [ ] Test ExecutionResult failure with errors and failed NodeStatus
- [ ] Test ExecutionStatus idle and running states
- [ ] Test ExecutionStatus rejects invalid state strings (e.g., "paused")
- [ ] Test ExecutionStatus JSON round-trip with nested ExecutionResult and ProgressInfo

**TDD cycle:** Write all tests first, verify they fail, implement models, verify all pass, commit.

---

### Task 4: Workflow + Settings Models

**Files:**
- Create: `backend/src/bioimageflow_server/models/workflow.py`
- Create: `backend/src/bioimageflow_server/models/settings.py`
- Create: `backend/tests/test_models/test_workflow.py`
- Create: `backend/tests/test_models/test_settings.py`

#### Workflow Models

Matches gui_specs_v1.md Section 2.4.2 endpoint descriptions.

**WorkflowCreate** — body for `POST /workflows`:
- `name: str` required, `display_name: str | None = None`, `description: str | None = None`, `storage_path: str | None = None`

**WorkflowInfo** — workflow list item returned by `GET /workflows`:
- `name: str`, `display_name: str`, `path: str`, `last_modified: str` — all required. `description: str | None = None`

**WorkflowUpdate** — body for `PATCH /workflows/{name}`:
- `action: Literal["update", "duplicate"]` required
- `display_name: str | None = None`, `description: str | None = None`, `new_name: str | None = None`, `storage_path: str | None = None`

**WorkflowFile** — the persistence format for saved workflows (matches gui_specs_v1.md Section 4.5). Contains both the library export data and GUI-specific state (node positions, collapsed state). This model is used by `PUT /workflows/{name}` (save) and `GET /workflows/{name}` (load):
- `workflow: dict[str, Any]` — library export format (includes tool_package + tool_package_version per node)
- `gui: dict[str, Any]` — GUI state (node positions, collapsed flags, keyed by node ID)

#### Settings Models

Matches gui_specs_v1.md Section 2.4.6 settings schema exactly.

**OMEROInstance**:

| Field | Type | Default |
|-------|------|---------|
| `name` | `str \| None` | `None` |
| `host` | `str` | required |
| `port` | `int` | `4064` |
| `username` | `str` | required |

**Settings**:

| Field | Type | Default |
|-------|------|---------|
| `deployment_mode` | `Literal["desktop", "webapp"]` | required |
| `external_editor` | `str \| None` | `None` |
| `napari_env_path` | `str \| None` | `None` |
| `omero_instances` | `list[OMEROInstance]` | `[]` |
| `output_data_folder` | `str` | required |
| `tool_store_path` | `str` | `"~/.bioimageflow/tool_packages/"` |
| `update_mode` | `Literal["auto", "manual"] \| str` | `"auto"` |
| `execution_engine` | `Literal["sequential", "parsl"]` | `"sequential"` |
| `cache_max_executions` | `int \| None` | `None` |
| `cache_max_age` | `str \| None` | `None` |
| `keyboard_shortcuts` | `dict[str, str]` | `{}` |
| `dev_mode` | `bool` | `True` |

Non-obvious choice: `update_mode` uses `Literal["auto", "manual"] | str` to allow both known modes and arbitrary version strings (e.g., `"1.5.0"`). The Literal values are checked first by Pydantic's union logic, but any string is accepted as a pinned version.

**Workflow Tests** (`test_workflow.py`):
- [ ] Test WorkflowCreate minimal (only name) and full (all fields)
- [ ] Test WorkflowInfo construction and optional description
- [ ] Test WorkflowUpdate with "update" and "duplicate" actions
- [ ] Test WorkflowUpdate rejects invalid action strings
- [ ] Test WorkflowFile round-trip with workflow and gui dicts

**Settings Tests** (`test_settings.py`):
- [ ] Test OMEROInstance with all fields and with defaults (name=None, port=4064)
- [ ] Test Settings full construction and defaults for all optional fields
- [ ] Test Settings rejects invalid deployment_mode (e.g., "cloud")
- [ ] Test Settings rejects invalid execution_engine (e.g., "spark")
- [ ] Test Settings with OMERO instances list
- [ ] Test Settings JSON round-trip including keyboard_shortcuts
- [ ] Test Settings accepts both Literal values ("auto") and arbitrary strings ("1.5.0") for update_mode

**TDD cycle:** Write all tests first, verify they fail, implement models, verify all pass, commit.

---

### Task 5: Re-exports + Verification

**Files:**
- Modify: `backend/src/bioimageflow_server/models/__init__.py`
- Create: `backend/tests/test_models/test_imports.py`

**Dependency:** Requires the scaffolding plan to be complete (`ErrorResponse` in `models/errors.py`).

Populate `__init__.py` with re-exports of all models from all submodules (graph, validation, execution, workflow, settings, errors). Define `__all__` listing every exported name alphabetically.

**Re-exported names:** `ColumnRefEdge`, `ErrorResponse`, `ExecutionRequest`, `ExecutionResult`, `ExecutionStatus`, `GraphState`, `GraphValidationError`, `NodeState`, `NodeStatus`, `OMEROInstance`, `PositionalEdge`, `ProgressInfo`, `Settings`, `ValidationResult`, `WorkflowCreate`, `WorkflowFile`, `WorkflowInfo`, `WorkflowUpdate`

**Tests** (`test_imports.py`):
- [ ] Test all models are importable from `bioimageflow_server.models` (single import statement)
- [ ] Verify class names match expected values

**Verification:**
- [ ] Run full test suite: `cd backend && uv run pytest tests/test_models/ -v`
- [ ] All tests from Tasks 1-4 plus import test must pass

**TDD cycle:** Write import test first, verify it fails, implement __init__.py, run ALL model tests, commit.
