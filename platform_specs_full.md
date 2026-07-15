# BioImageFlow GUI Specifications

## 1. Overview

The BioImageFlow GUI is a web application for building, executing, and inspecting bioimage analysis workflows visually. It wraps the BioImageFlow library (see `specs.md`) with a node-based editor, parameter panels, data viewers, and execution controls.

**Architecture:** The GUI follows a client-server model. The backend is a Python server (FastAPI) that wraps the BioImageFlow library and exposes a REST + WebSocket API. The frontend is a Vue SPA that communicates with the backend exclusively through this API.

**Deployment modes:**
- **Desktop:** Packaged with pywebview (or similar), giving access to native file dialogs.
- **Web app:** Served remotely; file access is handled via a dataset browser with upload support.

**Multi-user:** The MVP is single-user. The session system is deferred to a future version — it can be added as a middleware layer without breaking the API.

**Language:** English only (no i18n for now).

**Target devices:** The GUI is designed for desktop and laptop computers with standard screen sizes (1280px+ width). Tablets, mobile devices, and narrow browser windows are not supported. The Dockview layout assumes sufficient screen real estate for multiple panels.

**Accessibility:** Minimal accessibility features are provided: keyboard-navigable menus, focus indicators on interactive elements, and ARIA labels on buttons and panels. The DAG canvas is inherently visual and is not designed for screen reader use.

**Browser tab title:** `"BioImageFlow — {workflow_display_name}"`. With unsaved changes: `"BioImageFlow — {workflow_display_name} *"`.

---

## 2. Backend

### 2.1 Technology Stack

- **Framework:** FastAPI (async, OpenAPI docs auto-generated)
- **WebSocket:** For real-time progress, logs, and node state updates
- **Process model:** Single server process; BioImageFlow workflow execution runs in a background thread/task (via `asyncio.to_thread` or a dedicated executor) to keep the API responsive.
- **CORS:** In webapp mode, the server configures CORS middleware to allow requests from the frontend's origin. The allowed origins list is configurable at deployment time. In desktop mode, CORS is permissive (localhost only).
- **Rate limiting (webapp mode):** The `PUT /graph` endpoint is rate-limited server-side (e.g., 10 requests/second) to prevent abuse. Request body size is capped (default: 5MB). Validation computation has a timeout (default: 10 seconds) — if exceeded, the server returns HTTP 504.

### 2.2 Architecture: Full-State Sync

The frontend owns the graph state (nodes, edges, positions, parameters). The backend is a **thin adapter** between the frontend and the BioImageFlow library. It is stateless *between requests* for graph editing (no `last_valid_workflow` cache — each request is self-contained), but holds **transient execution state** during workflow runs (the running `Workflow` object, DataFrames, intermediate results). This distinction matters for error recovery: a server restart during execution loses the running workflow, but the graph state (owned by the frontend) is unaffected. The frontend sends the full graph as JSON on every meaningful change; the backend reconstructs the `Workflow` from it, validates it, and returns errors.

**Server state is minimal:**

| State | Description |
|-------|-------------|
| `tool_registry: dict[str, type[BaseTool]]` | Discovered tools indexed by class name (the unique tool identifier) |
| `workflow_name: str | None` | Currently open workflow name |
| `execution_task: Task | None` | Handle to the currently running execution (for cancellation) |
| `napari_launcher: NapariLauncher | None` | Manages the Napari process (lazily created) |

There is no `last_valid_workflow` cache — the server rebuilds the Workflow from the graph on every `PUT /graph` and `POST /execution/run`. Each request is self-contained.

**Key design points:**
- **No server-side graph editing logic.** The backend does not have add-node/remove-edge endpoints. It receives the full graph state and either accepts or rejects it.
- **Undo/redo is purely client-side.** The frontend maintains its own undo stack (snapshots of the graph state). No server round-trip needed. See [Section 4.6](#46-undoredo) for details.
- **Large workflow warning:** If the graph exceeds a threshold (e.g., 50 nodes), the frontend shows a persistent info banner: "Your workflow has {N} nodes. Consider splitting it into sub-workflows for better organization." The threshold is configurable.
- **Validation is authoritative on the server.** The frontend may do lightweight client-side checks (cycle detection, basic type checks) for instant UX feedback, but the server is the final authority before execution.
- **Vue Flow already maintains the graph client-side.** This approach aligns naturally with Vue Flow's data model rather than fighting it.
- **Graph editing is locked during execution.** While a workflow is running, the frontend disables all graph mutations (node/edge creation, deletion, parameter changes). The user can only view data and logs. This avoids race conditions between the running workflow and user edits.

### 2.3 Tool Discovery and the Tool Store

The server uses the BioImageFlow **tool store** (`~/.bioimageflow/tool_packages/`) to discover and load versioned tool packages. At startup, the server loads all installed package versions via `load_versioned_package()` and builds the tool registry.

Tools are indexed by **class name** (the unique tool identifier; `BaseTool.display_name` is the human-readable label) and organized by `tags`. The tool store directory can be overridden via the `BIOIMAGEFLOW_TOOL_STORE` environment variable.

**BioImageFlow state paths:** The platform must resolve BioImageFlow-owned state paths through `bioimageflow.paths` (`packages/bioimageflow/bioimageflow/paths.py`). Unless explicitly overridden, the BioImageFlow home is `~/.bioimageflow`, the tool store is `~/.bioimageflow/tool_packages`, and the Wetlands instance path is `~/.bioimageflow/wetlands`. Supported overrides are:

| Variable | Effect |
|----------|--------|
| `BIOIMAGEFLOW_HOME` | Changes the base directory for BioImageFlow state (`tool_packages`, `wetlands`, settings, etc.) unless a more specific variable is set. |
| `BIOIMAGEFLOW_TOOL_STORE` | Overrides only the tool store path. |
| `BIOIMAGEFLOW_WETLANDS` | Overrides only the Wetlands instance path. |

The platform must not rely on Wetlands' own `EnvironmentManager()` default for BioImageFlow-managed environments. Plain Wetlands defaults `wetlands_instance_path` to cwd-relative `./wetlands`; this can happen if a service calls Wetlands directly (or calls `bioimageflow.env_manager.get_shared_environment_manager()` before BioImageFlow has configured it) instead of going through `bioimageflow.paths.get_wetlands_path()` / `WetlandsEnvManager`. Because Wetlands uses a process-wide shared manager, the first initialization in the process fixes the Wetlands path for later callers. Tool execution, manual tool environment controls, Napari, thumbnails, and embedded code-server must therefore all use the same BioImageFlow-resolved Wetlands path, unless the user explicitly configured a custom environment path for that feature.

**Version management:** Version is a property of the package, not of individual nodes. Multiple versions of the same package can be installed simultaneously in the tool store. The Tools Panel (Section 3.4) shows installed packages with a version list allowing the user to install, uninstall, or select the active version for the current workflow. A workflow uses **one version per package**. Changing the active package version for a workflow marks all nodes using tools from that package as Out-of-date (with a confirmation dialog).

### 2.4 REST API

All endpoints are prefixed with `/api/v1/`. The version prefix allows future breaking changes to be introduced under `/api/v2/` without disrupting existing clients. No backward compatibility guarantees are made between major API versions. The frontend and backend are versioned together — they must use the same API version.

**Health check:** `GET /api/v1/health` returns `{"status": "ok", "version": "<bioimageflow_version>"}`. Used for monitoring in webapp mode (reverse proxy, container orchestration).

#### 2.4.1 Tool Registry

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/tools` | List all discovered tools with metadata |
| `POST` | `/tools` | Create a new tool from template (body: `{name, tool_type: "ProcessingTool" | "DataFrameTool"}`). The tool file is created in the current workflow's `tools/` directory (`workflow_root/tools/{name}.py`). Custom tools in this directory are auto-discovered by the server. Desktop mode only — disabled in webapp mode (see Section 8.3). |
| `DELETE` | `/tools/{tool_name}` | Delete a tool. Returns warning if used in workflows |
| `PATCH` | `/tools/{tool_name}` | Rename a tool (body: `{new_name: str}`) |
| `GET` | `/tools/{tool_name}/source` | Get the tool's source directory path |
| `GET` | `/tools/packages` | List all packages (installed and known). Returns installed versions, available versions, tools per version, and environment status. This is the single source of truth for the Tools Panel — no need to cross-reference with `GET /tools`. |
| `POST` | `/tools/packages/{package_name}/install` | Install a package version into the tool store (body: `{version?: str}`) |
| `DELETE` | `/tools/packages/{package_name}` | Uninstall a package version from the tool store (body: `{version?: str}`) |
| `POST` | `/tools/environments/{env_name}/start` | Start a tool's Wetlands environment |
| `POST` | `/tools/environments/{env_name}/stop` | Stop a tool's Wetlands environment |

**Tool metadata response (from `GET /tools`):**

The backend uses the library's canonical serializers
(`serialize_input_schema`, `serialize_output_schema`, and
`serialize_tool_metadata`) for tool schemas. These serializers read
`ImageSpec` and `GUIMeta` annotations from `Inputs`/`Outputs` fields.

```json
{
  "name": "CellposeSegmenter",
  "display_name": "Cellpose Segmenter",
  "package": "bioimageflow-cellpose",
  "package_version": "1.2.0",
  "tool_type": "ProcessingTool",
  "accepts_upstream": true,
  "dynamic_outputs": false,
  "documentation": "Segment cells using Cellpose models.",
  "tags": ["segmentation", "deep-learning"],
  "categories": ["segmentation"],
  "inputs": {
    "input_image": {
      "type": "ImagePath",
      "required": true,
      "nullable": false,
      "connectable": "by_default",
      "default": null,
      "display_name": "Input image",
      "description": "Input intensity image",
      "group": null,
      "min": null,
      "max": null,
      "step": null,
      "choices": null,
      "image_spec": {"semantics": ["intensity"], "layouts": ["YX", "CYX"], "dtypes": [], "formats": []}
    },
    "diameter": {
      "type": "float",
      "required": false,
      "nullable": false,
      "connectable": "not_by_default",
      "default": 30.0,
      "display_name": "Cell diameter",
      "description": "Expected cell diameter in pixels",
      "group": "general",
      "min": 1.0,
      "max": 500.0,
      "step": 0.5,
      "choices": null,
      "image_spec": null
    },
    "model_type": {
      "type": "str",
      "required": false,
      "nullable": false,
      "connectable": "never",
      "default": "cyto2",
      "display_name": "Model",
      "description": "Cellpose model to use",
      "group": null,
      "min": null,
      "max": null,
      "step": null,
      "choices": ["cyto", "cyto2", "nuclei"],
      "image_spec": null
    }
  },
  "outputs": {
    "mask": {"type": "ImagePath", "default": "{input_image.stem}_mask{ext}", "template": "{input_image.stem}_mask{ext}", "image_spec": {"semantics": ["label"], "layouts": ["YX"], "dtypes": [], "formats": []}},
    "cell_count": {"type": "int", "default": null, "image_spec": null}
  },
  "environment": {"python": "3.11", "conda": ["cellpose"], "pip": []}
}
```

The `connectable`, `display_name`, `description`, `min`, `max`, `step`, and
`group` fields come from `GUIMeta` annotations. Fields without `GUIMeta`
default to `connectable: "not_by_default"`.

**Endpoint roles:** `GET /tools` returns tool-level metadata (inputs schema, outputs, environment) for graph construction and the Node Panel. `GET /tools/packages` returns package-level metadata (installed/available versions, environment status) for the Tools Panel table. The data intentionally overlaps (both include package name and version) for convenience — the frontend uses `GET /tools/packages` to populate the Tools Panel, and `GET /tools` to resolve tool schemas when building nodes.

**Example tool definition with GUIMeta:**
```python
from typing import Annotated, Any, Literal

from bioimageflow_core import (
    Arguments,
    Connectable,
    GUIMeta,
    IOModel,
    ImagePath,
    Layout,
    ProcessingTool,
    Semantic,
    Template,
)

class CellposeSegmenter(ProcessingTool):
    display_name = "Cellpose Segmenter"
    environment = cellpose_env

    class Inputs(IOModel):
        input_image: Annotated[
            ImagePath(
                semantics={Semantic.INTENSITY},
                layouts={Layout.PLANAR, Layout.PLANAR_CHANNEL},
            ),
            GUIMeta(
                display_name="Input image",
                description="Input intensity image.",
                connectable=Connectable.BY_DEFAULT,
            ),
        ]
        diameter: Annotated[
            float,
            GUIMeta(min=1.0, max=500.0, step=0.5, group="general"),
        ] = 30.0
        model_type: Annotated[
            Literal["cyto", "cyto2", "nuclei"],
            GUIMeta(connectable=Connectable.NEVER),
        ] = "cyto2"

    class Outputs(IOModel):
        mask: Annotated[
            ImagePath(semantics={Semantic.LABEL}, layouts={Layout.PLANAR}),
            GUIMeta(display_name="Segmentation mask"),
        ] = Template("{input_image.stem}_mask{ext}")
        cell_count: int

    def process_row(self, arguments: Arguments, *, context: Any = None) -> Outputs:
        ...
```

**Package list response (from `GET /tools/packages`):**
```json
[
  {
    "name": "bioimageflow-cellpose",
    "installed_versions": ["1.1.0", "1.2.0"],
    "available_versions": ["1.0.0", "1.1.0", "1.2.0", "1.3.0-rc1"],
    "tools": {"1.2.0": ["CellposeSegmenter", "CellposeTrain"]},
    "environment_status": "running"
  },
  {
    "name": "bioimageflow-stardist",
    "installed_versions": [],
    "available_versions": ["0.8.0", "0.9.0"],
    "tools": {},
    "environment_status": "stopped"
  }
]
```

**Package installation:** Packages are installed into the tool store via `uv pip install --target <dir>`. During installation, the Tools Panel shows a spinning icon on the package row. Installation progress and errors are streamed to the Logger Panel. Installation can be interrupted via a stop button. **Package installations are serialized** — only one installation runs at a time. If the user requests a second installation while one is in progress, it is queued and a toast informs: "Installation queued — waiting for {package_name} to finish."

**Execution during installation:** If a required package is currently being installed, the "Run" button is disabled with a tooltip: "Waiting for package installation to complete." Execution is blocked until all required packages are fully installed.

**Environment lifecycle:** Environments are automatically started by Wetlands when a workflow is executed. The Start/Stop buttons allow manual control (e.g., pre-warming an environment, or freeing resources). Environment status is shown via button color and label (stopped/creating/running). Environments cannot be stopped during execution.

#### 2.4.1b Error Response Format

All API endpoints use a consistent error response format:

```json
{
  "error": "short_error_code",
  "detail": "Human-readable error message",
  "field": "optional_field_name"
}
```

**Common HTTP status codes:**

| Code | Meaning | Example |
|------|---------|---------|
| 400 | Bad Request | Invalid JSON body, missing required fields |
| 404 | Not Found | Unknown node ID, unknown tool name, unknown workflow |
| 409 | Conflict | Workflow name already exists, execution already running |
| 422 | Validation Error | Parameter type mismatch, graph validation failure |
| 423 | Locked | Graph mutation attempted during execution |
| 403 | Forbidden | Desktop-only endpoint called in webapp mode |
| 501 | Not Implemented | `POST /fs/reveal` in webapp mode |

#### 2.4.2 Workflow Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/workflows` | List saved workflows (name, display_name, description, path, last modified) |
| `POST` | `/workflows` | Create a new workflow (body: `{name: str, display_name?: str, description?: str, storage_path?: str}`). Returns **409 Conflict** if a workflow with the same name already exists, with a suggested alternative name (e.g., `"My_Workflow_2"`). The `name` is the filesystem/API identifier: alphanumeric characters, underscores, and hyphens only. The `display_name` is the free-form human-readable label (allows spaces, special characters). If `display_name` is omitted, it defaults to `name`. The `description` is an optional free-form text describing the workflow's purpose. |
| `GET` | `/workflows/{name}` | Load a workflow (returns full graph JSON including GUI state) |
| `PUT` | `/workflows/{name}` | Save workflow (body: full graph JSON). Always succeeds (saves even if graph has validation errors). |
| `DELETE` | `/workflows/{name}` | Delete a workflow |
| `PATCH` | `/workflows/{name}` | Update workflow metadata or duplicate (body: `{action: "update" | "duplicate", display_name?: str, description?: str, new_name?: str, storage_path?: str}`) |
| `POST` | `/workflows/{name}/export` | Export workflow to downloadable JSON file |
| `POST` | `/workflows/import` | Import workflow from uploaded JSON file |

**Workflow loading — missing package resolution:** When loading a workflow that requires tool packages or versions not in the tool store (based on the `tool_package` and `tool_package_version` fields in the serialized nodes), the server returns a `missing_packages` field in the response. The frontend shows a dialog: "This workflow requires packages not installed: [list with versions]. Install them?" with an "Install All" button.

#### 2.4.3 Graph Schema and Validation

##### Graph JSON Schema (Pydantic Models)

The full-state sync architecture has a single graph payload as its central contract. This schema is formally defined as Pydantic models in the backend, which serve as both validation and documentation. FastAPI auto-generates OpenAPI schemas from these models. The frontend generates TypeScript types from the OpenAPI spec using `openapi-typescript`.

**Edge model — discriminated union:**

The graph has two kinds of edges, each with a distinct purpose:

- **`ColumnRefEdge`**: Binds a specific output column of one node to a specific input field of another. Used for `ProcessingTool` keyword bindings.
- **`PositionalEdge`**: Connects a node as a positional upstream argument to a `DataFrameTool`. The `positional_index` determines order in `merge_dataframes(dfs)`.

These are modeled as a **discriminated union** (discriminator: `type` field) rather than a single model with optional fields. This eliminates invalid states (e.g., `source_output` set simultaneously with `positional_index`), produces cleaner TypeScript types from OpenAPI, and makes each edge self-documenting.

**NodeStatus separation:**

`NodeStatus` is intentionally **not** a property of `NodeState`. The separation reflects the data flow direction:

- **`NodeState`** flows **frontend → backend**: the user's graph definition (what to build). Saved to disk.
- **`NodeStatus`** flows **backend → frontend**: the server's assessment (cache state, validity). Computed, never saved.

Merging them would mean the frontend sends back stale server-computed values, and the backend would need to ignore its own fields.

**Schema definition:**

```python
from pydantic import BaseModel, Discriminator, Tag
from typing import Any, Annotated, Literal

class NodeState(BaseModel):
    """A node in the graph. Sent by the frontend, saved to disk."""
    id: str                              # Unique node identifier (URL-safe, e.g., "cellpose_segmenter_1")
    name: str                            # Human-readable display name (may contain spaces, e.g., "Cellpose Segmenter 1")
    tool_name: str                       # Tool class name (e.g., "CellposeSegmenter")
    position: tuple[float, float]        # Canvas position (x, y)
    parameters: dict[str, Any]           # Constant input values (non-connected fields)
    resources: dict[str, Any] = {}       # Resource overrides (cpu, gpu, gpu_memory, memory, max_concurrent)
    output_templates: dict[str, str] = {} # Custom output path templates (field_name → template string)
    enabled: bool = True
    collapsed: bool = False

class ColumnRefEdge(BaseModel):
    """Binds an output column to an input field (ProcessingTool keyword binding)."""
    type: Literal["column_ref"] = "column_ref"
    id: str                              # Unique edge ID
    source_node: str                     # Upstream node ID
    target_node: str                     # Downstream node ID
    source_output: str                   # Output field name on source node
    target_input: str                    # Input field name on target node

class PositionalEdge(BaseModel):
    """Connects a node as positional upstream to a DataFrameTool."""
    type: Literal["positional"] = "positional"
    id: str                              # Unique edge ID
    source_node: str                     # Upstream node ID
    target_node: str                     # Downstream node ID
    positional_index: int                # Position in merge_dataframes(dfs) list

Edge = Annotated[
    Annotated[ColumnRefEdge, Tag("column_ref")]
    | Annotated[PositionalEdge, Tag("positional")],
    Discriminator("type"),
]

class GraphState(BaseModel):
    """Full graph state sent by the frontend on every structural change."""
    nodes: list[NodeState]
    edges: list[Edge]

class NodeStatus(BaseModel):
    """Server-computed status for a node. Returned by validation and WebSocket."""
    node_id: str                         # Matches NodeState.id
    status: Literal["unexecuted", "executed", "out_of_date", "disabled", "running", "failed"]
    cached: bool
    error: str | None = None             # Error message (only for status="failed")
    traceback: str | None = None         # Full traceback string (only for status="failed")

class GraphValidationError(BaseModel):
    """A single validation error."""
    type: Literal[
        "cycle_detected",
        "type_incompatible",
        "parameter_invalid",
        "missing_tool",
        "missing_connection",
        "missing_package",
        "invalid_node_id",
        "invalid_edge_id",
    ]
    detail: str
    node: str | None = None
    edge_id: str | None = None
    field: str | None = None

class ValidationResult(BaseModel):
    """Response from PUT /graph."""
    valid: bool
    node_statuses: dict[str, NodeStatus] = {}
    errors: list[GraphValidationError] = []
```

**Node `id` vs `name`:** The `id` is the URL-safe, unique, special-character-free identifier used in API endpoints (e.g., `/nodes/{id}/data`) and edge references (`source_node`, `target_node`). The `name` is the human-readable display name shown on the canvas and in the Node Panel. The `id` is auto-generated from the tool's **class name** by converting CamelCase to snake_case and appending a numeric suffix for uniqueness (e.g., class `CellposeSegmenter` → id `"cellpose_segmenter_1"`). The `id` is stable once assigned — renaming the `name` does not change the `id`. All API endpoints and WebSocket messages use `id` (not `name`). The `name` is used only in UI display contexts.

**Node ID validation:** The backend validates node ID uniqueness and format in `PUT /graph`. Duplicate or malformed IDs produce a `GraphValidationError` of type `"invalid_node_id"`.

**Edge IDs:** Edge IDs (`ColumnRefEdge.id`, `PositionalEdge.id`) are frontend-generated UUIDs (or nanoid). The backend validates uniqueness; duplicate or missing edge IDs produce a `GraphValidationError` of type `"invalid_edge_id"`.

**Positional index normalization:** The backend normalizes `positional_index` values on `PositionalEdge`s: it sorts by `positional_index` and reassigns `0..N-1`. This makes the frontend resilient to gaps after edge disconnection.

Note: `NodeStatus` is used both in the `PUT /graph` response and in WebSocket `node_state` messages — the same schema for both, avoiding the inconsistency of having `status` vs `ui_status` in different contexts.

Note: `NodeState` does not include `tool_version`. The `tool_package` and `tool_package_version` are stored in the library's serialization format (per node), not in the GUI's graph state. The server resolves tool versions from the tool store when building the Workflow.

**Compatibility with the library serialization format:**

The backend translation layer maps between the GUI schema and the library's `workflow.export()` format:
- Library edges with `column: "__positional__"` map to `PositionalEdge`
- Library edges with `column: "field_name"` map to `ColumnRefEdge`
- Library `nodes[].constants` maps to `NodeState.parameters`
- Library `nodes[].tool_module` + `tool_class` are resolved from `NodeState.tool_name` via the tool registry
- Library `nodes[].tool_package` + `tool_package_version` are resolved from the tool registry (based on the current workflow's selected package versions)

##### Graph Validation Endpoint

| Method | Endpoint | Description |
|--------|----------|-------------|
| `PUT` | `/graph` | Submit the complete graph state for request-local validation. Returns validation and cache status derived only from that request snapshot. |

**Request body — example `GraphState`:**

```json
{
  "nodes": [
    {
      "id": "cellpose_segmenter_1",
      "name": "Cellpose Segmenter 1",
      "tool_name": "CellposeSegmenter",
      "position": [350, 200],
      "parameters": {
        "diameter": 30.0,
        "model_type": "cyto2"
      },
      "enabled": true,
      "collapsed": false
    }
  ],
  "edges": [
    {
      "type": "column_ref",
      "id": "edge_1",
      "source_node": "file_lister_1",
      "source_output": "path",
      "target_node": "cellpose_segmenter_1",
      "target_input": "input_image"
    },
    {
      "type": "positional",
      "id": "edge_2",
      "source_node": "file_lister_1",
      "target_node": "inner_join_1",
      "positional_index": 0
    }
  ]
}
```

**Response (success):**
```json
{
  "valid": true,
  "node_statuses": {
    "cellpose_segmenter_1": {"node_id": "cellpose_segmenter_1", "status": "unexecuted", "cached": false},
    "file_lister_1": {"node_id": "file_lister_1", "status": "executed", "cached": true}
  }
}
```

**Response (validation errors):**
```json
{
  "valid": false,
  "errors": [
    {
      "type": "cycle_detected",
      "detail": "Cycle: segmenter_1 -> stats_1 -> ... -> segmenter_1",
      "node": "segmenter_1"
    },
    {
      "type": "type_incompatible",
      "detail": "Output 'mask' (label) is not compatible with input 'input_image' (intensity)",
      "edge_id": "edge_3"
    },
    {
      "type": "parameter_invalid",
      "detail": "diameter must be > 0",
      "node": "cellpose_segmenter_1",
      "field": "diameter"
    }
  ]
}
```

The backend:
1. Parses the `GraphState`
2. Reconstructs a BioImageFlow `Workflow` object (translates `ColumnRefEdge` to `ColumnRef` bindings, `PositionalEdge` to positional args, resolves tool classes from the tool store)
3. Runs validation (cycle detection, type compatibility, parameter validation via Pydantic). Disabled nodes are skipped during validation.
4. Checks cache status for each node (compares current parameters + upstream signature against stored hashes)
5. Returns the `ValidationResult` with per-node status

**Validation timing and debouncing:** The frontend sends `PUT /graph` on structural changes (add/remove node, add/remove edge, parameter change confirmed by blur or Enter). Cosmetic-only changes (node position, collapsed state) do not trigger validation.

Changes are **debounced**: the frontend accumulates changes and sends `PUT /graph` after **300ms of inactivity**. During the debounce window, the frontend shows provisional client-side status with a subtle visual indicator (slightly desaturated colors) to signal "unconfirmed." If an edit occurs while a validation request is in flight, the in-flight request is cancelled and a new one is sent after the debounce window.

**Ctrl+Enter** triggers immediate validation without waiting for the debounce.

Parameter changes use the same full-state `PUT /graph` contract as structural changes. The server does not retain an active graph between requests, so validation meaning never depends on request history.

#### 2.4.4 Node Data (Outputs)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/nodes/{node_id}/data` | Get the output DataFrame as JSON (paginated: `?page=0&page_size=50`) |
| `GET` | `/nodes/{node_id}/data/csv` | Download output DataFrame as CSV |
| `GET` | `/nodes/{node_id}/thumbnail` | Get image thumbnail (`?row=0&col=mask&size=128`) |
| `GET` | `/nodes/{node_id}/status` | Get execution status + cache info |
| `POST` | `/nodes/summary` | Compute summary DataFrame (body: `{node_ids: [str], page?: int, page_size?: int}`). Returns an outer join on index of the specified nodes' DataFrames, paginated. Returns error with `reason` if summary is not possible (no common index lineage, column name conflict). |

**Data response:**
```json
{
  "columns": ["mask", "cell_count"],
  "index": ["img_001", "img_002"],
  "rows": [
    {"mask": "/path/to/mask1.tif", "cell_count": 42},
    {"mask": "/path/to/mask2.tif", "cell_count": 17}
  ],
  "total_rows": 250,
  "page": 0,
  "page_size": 50,
  "column_types": {"mask": "ImagePath", "cell_count": "int"}
}
```

#### 2.4.4b Image Viewer Endpoint (Webapp Mode)

In webapp mode, the Viv viewer needs access to full image data. The following endpoint serves images in formats compatible with Viv:

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/nodes/{node_id}/image` | Serve a full image file. Query params: `row` (row index, required), `col` (output column name, required), `format` (optional, see below). |

**Response behavior:**

The server reads the image file referenced by the specified row and column in the node's output DataFrame. The response depends on the source format and the `format` query parameter:

| Source Format | Default Response | Notes |
|---------------|-----------------|-------|
| OME-TIFF | Served as-is (`image/tiff`) | Viv loads OME-TIFF natively with metadata (channels, resolution levels) |
| OME-Zarr | Redirects to a static file tree URL | The server serves the Zarr directory as static files under `/nodes/{node_id}/zarr/{row}/{col}/`. Viv loads the `.zattrs` and chunk files directly. |
| Standard TIFF | Served as-is (`image/tiff`) | Viv handles standard multi-page TIFFs |
| PNG/JPEG | Served as-is (`image/png` or `image/jpeg`) | Simple 2D images |
| NIfTI (`.nii`, `.nii.gz`) | Served as-is (`application/gzip` or `application/octet-stream`) | Frontend uses a NIfTI loader for Viv |
| `SharedArray` (in-memory) | Converted to OME-TIFF on-the-fly and served | Includes shape/dtype metadata in OME-TIFF headers |

**`format` query parameter:** When set to `ome-tiff`, forces conversion to OME-TIFF regardless of source format. Useful for formats that Viv cannot load natively.

**Caching:** Responses include `ETag` headers based on `SHA256(file_path + file_mtime)`. Viv's HTTP loader respects conditional requests (`If-None-Match`), avoiding redundant transfers.

**Desktop mode:** This endpoint is available but rarely used (Napari is the primary viewer). It can serve as a fallback for in-browser preview.

#### 2.4.5 Execution

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/execution/run` | Submit graph + run (body: `{graph: {...}, nodes?: [str]}`) |
| `POST` | `/execution/stop` | Stop the current execution |
| `POST` | `/execution/clear` | Clear outputs for specified nodes (body: `{graph: GraphState, nodes: [str], workflow_name: str}`). `workflow_name` is required. The server compiles the submitted graph in that workflow's storage context and rejects build errors before invalidating cache. Returns updated `NodeStatus` for the cleared nodes and all downstream dependents. |
| `GET` | `/execution/status` | Get full execution state (see response schema below) |

The `run` endpoint accepts the full graph (same `GraphState` format as `PUT /graph`). This ensures the executed workflow always matches what the user sees. The backend validates, builds the Workflow, and executes. If `nodes` is provided, those nodes and all their out-of-date or unexecuted dependencies are re-executed — stale cached results are never used. If `nodes` is omitted, all enabled unexecuted/out-of-date nodes are executed.

A second `POST /execution/run` while one is already running returns HTTP 409 Conflict.

**Error recovery:** Successfully completed nodes retain their output and cache after a failed or stopped execution. Only the failed node (and its unexecuted descendants) need re-running. The user can fix parameters and re-run specific nodes via the `nodes` parameter.

**Stop behavior:** When execution is stopped, the currently running node's partial output is discarded and its status is set to "unexecuted". It must be re-executed from scratch. Nodes that completed before the stop retain their output and cache.

**Execution status response (`GET /execution/status`):**

```json
{
  "state": "idle",
  "last_result": {
    "success": true,
    "errors": [],
    "node_statuses": {
      "cellpose_segmenter_1": {"node_id": "cellpose_segmenter_1", "status": "executed", "cached": true}
    }
  },
  "progress": null
}
```

| Field | Type | Description |
|-------|------|-------------|
| `state` | `"running" \| "idle"` | Whether an execution is in progress |
| `last_result` | `ExecutionResult \| null` | Final result of the last execution (same schema as `execution_complete` WebSocket message). Persists after execution ends, cleared on the next `POST /execution/run`. `null` if no execution has run since server start. |
| `progress` | `ProgressInfo \| null` | Current progress (only when `state` is `"running"`): `{node_id, row, total_rows}` |

This ensures that if the frontend misses the `execution_complete` WebSocket message (e.g., during a brief disconnection), it can recover the final state via this endpoint on reconnect.

#### 2.4.6 Settings

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/settings` | Get all settings (returns `Settings` model) |
| `PATCH` | `/settings` | Update settings (partial update, same `Settings` fields) |

**Settings schema:**

```python
class OMEROInstance(BaseModel):
    name: str | None = None              # Display name (defaults to "host:username")
    host: str
    port: int = 4064
    username: str
    # Password is stored via Python keyring, not in this model

class Settings(BaseModel):
    deployment_mode: Literal["desktop", "webapp"]  # Read-only, set at server startup
    external_editor: str | None = None              # e.g., "code {file_path}"
    napari_env_path: str | None = None              # Custom Napari Conda env path (desktop only)
    omero_instances: list[OMEROInstance] = []
    output_data_folder: str                         # Workflow output storage path
    tool_store_path: str = "~/.bioimageflow/tool_packages/"
    update_mode: Literal["auto", "manual"] | str = "auto"  # Version or "auto"
    execution_engine: Literal["sequential", "parsl"] = "sequential"
    cache_max_executions: int | None = None         # Max cached executions per node (None = unlimited)
    cache_max_age: str | None = None                # Max cache age (e.g., "30d", None = unlimited)
    keyboard_shortcuts: dict[str, str] = {}         # Action → key binding overrides
    dev_mode: bool = True                           # Always true in GUI mode (cache invalidation on code change)
```

#### 2.4.7 File System Helpers

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/fs/reveal` | Open a path in the system file browser (desktop mode only) |

In **desktop mode**, path selection uses native file dialogs via pywebview. No server-side browse endpoint is needed.

In **webapp mode**, path selection uses the Dataset Browser (see Section 3.14). The `/fs/reveal` endpoint returns **501 Not Implemented**. The frontend hides "Reveal in file browser" buttons when `deployment_mode === "webapp"` (from `GET /settings`).

#### 2.4.8 Dataset Management (Webapp Mode)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/datasets` | List available datasets for the current user |
| `POST` | `/datasets/upload` | Upload a dataset (multipart) |
| `DELETE` | `/datasets/{dataset_id}` | Delete a dataset |

Datasets are stored on the server in a dedicated folder, organized by user: `datasets/{user_id}/{timestamp}_{filename}.{ext}`. Each user can only see and use their own datasets. No quota system for now.

#### 2.4.9 Image Viewer Integration

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/napari/open` | Open image(s) in Napari (body: `{paths: [str], clear_layers: bool}`). Desktop mode only. |
| `GET` | `/napari/status` | Check if Napari is running. Desktop mode only. |

**Desktop mode:** The backend manages Napari via `NapariLauncher` (using Wetlands). Napari runs in an isolated Conda environment (`napari` + `pyqt`) with its own Qt event loop. Communication uses `multiprocessing.connection` (Client/Listener pattern on localhost). The backend launches Napari lazily on the first `/napari/open` call and reconnects automatically if the process dies.

**Webapp mode:** The frontend uses [Viv](https://github.com/hms-dbmi/viv) as an in-browser image viewer instead of Napari. Viv supports OME-TIFF, OME-Zarr, and other bioimage formats with pan/zoom/contrast controls. The "Open in Napari" button is replaced with "View image" which opens an in-browser Viv viewer. No server-side endpoints needed for Viv.

#### 2.4.10 Code Editor

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/editor/open` | Open a file/folder in the code editor (body: `{path: str}`). In webapp mode, the path is validated to be within the tool store or workflow directories; paths outside allowed roots are rejected (403 Forbidden). |
| `GET` | `/editor/status` | Check if code-server is running and get its URL |

**code-server** is the default embedded editor — it is installed and configured locally automatically. The user can optionally specify an external editor command (e.g., `code` for VS Code) in Settings (Section 3.13.1) to open files in their own editor. If code-server is unavailable and no external editor is configured, "Open in editor" copies the path to clipboard with a toast: "Path copied — open in your local editor."

### 2.5 WebSocket API

A single WebSocket connection at `/ws` provides real-time updates. Messages are JSON with a `type` field.

**Authentication (webapp mode):** The WebSocket connection must include the session token as a query parameter (`/ws?token=<token>`). The server rejects unauthenticated connections with a close frame. In desktop mode, no authentication is required.

**Server-to-client messages:**

| Type | Payload | Description |
|------|---------|-------------|
| `progress` | `{node_id, status, row, total_rows, timestamp}` | Maps directly to BioImageFlow's `ProgressEvent` |
| `node_state` | `{node_id, status, cached, error?, traceback?}` | Node state change. Uses the same `NodeStatus` schema as `PUT /graph` response. |
| `log` | `{level, message, node_id?, timestamp}` | Log message (from BioImageFlow logger and worker forwarding) |
| `execution_complete` | `{success, errors?: [...], node_statuses: dict[str, NodeStatus]}` | Workflow execution finished. Includes final per-node statuses (same schema as `PUT /graph` response), eliminating the need for a post-execution `PUT /graph` just to refresh statuses. |
| `tool_reload` | `{tool_name, tool_metadata}` | A tool's source changed (file watcher). Includes full updated tool schema. |
| `package_install` | `{package_name, status, detail?}` | Package installation progress (installing/complete/failed) |
| `environment_status` | `{env_name: str, status: "stopped" | "creating" | "running"}` | Environment state change (asynchronous creation, manual start/stop) |
| `ack` | `{ref: str}` | Acknowledges a client-to-server message (ref = the client's `message_id`) |

**Client-to-server messages:**

All client-to-server messages include an optional `message_id: str` field. When present, the server responds with an `ack` message (`{type: "ack", ref: "<message_id>"}`) once the request has been processed. This lets the frontend know when a state change (e.g., log subscription switch) has taken effect, avoiding races where stale messages from the previous state are mixed with new ones.

| Type | Payload | Description |
|------|---------|-------------|
| `subscribe_logs` | `{message_id?, node_id?: str, level?: str}` | Filter log stream. After the `ack`, all subsequent `log` messages match the new filter. |

**Reconnection strategy:** On WebSocket disconnect, the frontend uses exponential backoff (1s, 2s, 4s, 8s, max 30s) to reconnect. On reconnection, the frontend:
1. Fetches `GET /execution/status` to resynchronize the full execution state, including per-node statuses (the response uses the same `NodeStatus` schema as WebSocket `node_state` messages, including `error` and `traceback` for failed nodes).
2. Fetches `GET /tools` to detect tool registry changes (e.g., if the tool store was modified during the disconnection or a server restart).
3. Re-sends `subscribe_logs` with the previous filter (the subscription is server-side state tied to the WebSocket connection and is lost on disconnect). The frontend stores the last subscription filter locally.

This ensures the frontend can reconstruct the correct state even if `node_state` messages were missed during disconnection. Log messages missed during disconnection are lost (logs are ephemeral; persistent logs are written to disk by the backend).

**WebSocket error messages:** If a client-to-server message has an invalid payload, the server responds with an error message instead of `ack`: `{type: "error", ref?: str, code: str, detail: str}`. When `ref` is set, it correlates to the client's `message_id`.

**Future improvement — message sequencing:** The current WebSocket protocol does not guarantee message ordering or provide backpressure. For a future version, adding a monotonic sequence number to all server-to-client messages would allow the frontend to discard stale messages received after a reconnection resync, and to detect missed messages.

### 2.6 Thumbnail Generation

The server generates thumbnails on demand for image files referenced in output DataFrames. Thumbnails are cached on disk in the workflow's storage directory.

- **Supported formats:** TIFF, PNG, JPEG, NIfTI (max-projection for 3D)
- **Size:** 128x128 pixels (configurable via query param)
- **Cache key:** `SHA256(file_path + file_mtime)` -- invalidates when the file changes

### 2.7 Tool Hot-Reload

The backend watches tool source directories for file changes (via `watchdog`). On change:

1. Backend re-scans the changed tool module and updates the tool registry
2. Backend sends `tool_reload` WebSocket message with the full updated tool metadata (same format as `GET /tools` response)
3. Frontend updates the tool registry in Pinia and all nodes using the reloaded tool:
   - Input schema is updated (new/removed fields, changed types)
   - Parameters are re-validated against the new schema; incompatible values are flagged
   - Edges are re-validated; incompatible edges (removed output field, changed type) are flagged with a validation error
   - A temporary dismissable "tool updated" badge appears on affected nodes (small refresh icon, click to dismiss)
   - Executed nodes transition to "Out-of-date" (cache invalidated by code change)

Changes are applied automatically — no manual reload action required from the user.

**Hot-reload during editing:** If the user is editing a parameter field (field has focus) when a `tool_reload` message arrives, the update is buffered until the field loses focus (blur event). This prevents data loss from mid-edit schema changes. If the field being edited was removed in the new schema, a warning toast is shown after blur: "Field '{name}' was removed by the tool update."

**Development mode:** The GUI always runs with `dev_mode=True` (cache invalidation on tool code change). There is no toggle — this is the appropriate default for an interactive GUI where users iterate on tool code.

**Tool reloads during execution** affect only future executions. The currently running Workflow uses the tool code that was loaded when execution started. This is the natural behavior of Python object references — the Workflow holds references to the tool classes loaded at build time.

**Hot-reload during package installation:** The file watcher is suppressed while a package is being installed (files are written sequentially during installation, which would trigger spurious reload events). Once installation completes, a single batch `tool_reload` event is emitted for all tools in the installed package.

### 2.8 Startup and Shutdown

**Startup sequence:**
1. Load settings from configuration file
2. Scan tool store and load versioned packages to build tool registry
3. Start FastAPI server
4. (Desktop mode) Open pywebview window pointing to the server URL

**Shutdown sequence:**
1. If execution is running, send stop signal and wait (with timeout)
2. Terminate Napari process if running (via `NapariLauncher`)
3. Clean up shared memory segments (`bioimageflow clean-shm`)
4. Save any pending settings changes
5. Stop FastAPI server

Unsaved workflow changes are not auto-saved to disk on shutdown. The frontend auto-saves to `localStorage` (see Section 4.3), so the user can recover their work on next startup.

---

## 3. Frontend

### 3.1 Technology Stack

- **Framework:** Vue SPA
- **DAG Editor:** Vue Flow
- **Layout:** Dockview (dockable, resizable panels)
- **UI Components:** PrimeVue
- **State management:** Vue Flow owns graph state (nodes, edges). Pinia for non-graph state (settings, tool registry, execution status, datasets). Graph state is not duplicated in Pinia.

### 3.2 Layout

The application uses a Dockview-based multi-panel layout. Panels are resizable, dockable, and can be collapsed.

```
+------------------------------------------------------+
| Menu bar (Workflow / Edit / Execution / View / Help) |
+----------+----------------------------+--------------+
|          |                            |              |
|  Tools   |   Node Programming         |   Node       |
|  Panel   |   Interface (canvas)       |   Panel      |
|          |                            |  (params)    |
|          |                            |              |
+----------+----------------------------+--------------+
|                                                      |
|   Data Table  |  Logger  |  (tabbed bottom panel)    |
|                                                      |
+------------------------------------------------------+
```

### 3.3 Node Programming Interface (Canvas)

The central canvas where users build the DAG visually.

#### 3.3.1 Nodes

A node represents an instance of a tool in the workflow. Each node displays:

- **Header:** Tool name (or custom node name) + tool icon/category badge
- **Input pins:** One pin per connectable input field (left side)
- **Output pins:** One pin per output field (right side)
- **Status indicator:** Color-coded border or badge

**Node creation:**
- Drag a tool from the Tools Panel onto the canvas
- Or click a tool in the Tools Panel (creates the node at a default position)
- The frontend assigns a unique node name (e.g., `cellpose_segmenter_1`)

**Node states and visual encoding:**

| State | Color | Condition |
|-------|-------|-----------|
| Disabled | Gray (40% opacity) | Manually disabled by user |
| Unexecuted | Blue | No output data exists (newly created or cleared) |
| Executed | Green | Has output data matching current parameters |
| Out-of-date | Orange | Parameters changed since last execution, or upstream changed |
| Running | Blue (pulsing) | Currently being executed |
| Failed | Red | Last execution failed |

Disabled nodes are rendered at reduced opacity. Nodes downstream of a disabled node remain in their current status (typically "unexecuted") — no special visual treatment is needed since the disabled ancestor is visible in the graph.

**Node status reconciliation:** Client-side status is **provisional** (for instant feedback based on local parameter comparison). Server-side status is **authoritative**. The reconciliation rules are:

- **At rest (no execution):** The frontend displays server status from the last `PUT /graph` response. If a `PUT /graph` request is in flight (during the debounce window), the frontend shows its own provisional status with slightly desaturated colors to signal "unconfirmed."
- **During execution:** WebSocket `node_state` messages override the last known status. These are authoritative during execution.
- **After execution:** The frontend sends `PUT /graph` to get fresh status (cache hits may have changed). This replaces all provisional states.

**Node interactions:**
- **Select:** Click a node. Shift+click toggles selection. Click on empty canvas clears selection.
- **Box select:** Drag a selection rectangle on the canvas. Shift+drag adds to selection.
- **Move:** Drag selected node(s).
- **Delete:** Press Delete key with node(s) selected. Confirms if nodes have output data.
- **Copy/Paste:** Ctrl+C / Ctrl+V. Copies selected nodes and edges between them. Pasted nodes get new unique IDs and names (same name generation logic as node creation). Internal edges between pasted nodes are preserved with their `source_node` and `target_node` fields remapped to the new node IDs. Edges connecting to nodes outside the selection are dropped. **Cross-workflow copy/paste** is supported: the clipboard format is self-contained (includes tool names, parameters, internal edges, `tool_package`, and `tool_package_version`). When pasting into a different workflow, tools are resolved from the tool store by name. If the pasted node's package version differs from the target workflow's version, parameters are validated against the current tool schema: compatible values are kept, incompatible or removed fields are set to defaults, and a warning toast is shown: "Pasted node was from {package} {version}, but this workflow uses {other_version}. Some parameters were reset to defaults." If a required tool is not installed, a toast warns: "Tool '{name}' not found — install the package first." and the paste is aborted for that node.
- **Collapse/Expand:** Double-click header or toggle in Node Panel. Collapsed nodes show only the header bar with pins.
- **Enable/Disable:** Right-click context menu or toggle in Node Panel header.
- **Create sub-workflow:** Select multiple nodes → right-click → "Create sub-workflow." See [Section 6](#6-sub-workflow-support).

#### 3.3.2 Edges

Edges represent data flow between nodes. There are two kinds of edges (see [Section 2.4.3](#243-graph-schema-and-validation)):

- **Column reference edges** (`ColumnRefEdge`): Connect a specific output pin to a specific input pin. Represent `ColumnRef` bindings for `ProcessingTool` inputs.
- **Positional edges** (`PositionalEdge`): Connect a node to a `DataFrameTool`'s positional input pin. Represent upstream arguments to `merge_dataframes`.

**Edge creation:**
- Drag from an output pin to an input pin (or vice versa).
- The frontend performs lightweight client-side validation (cycle detection, basic type check) for instant feedback.
- Invalid connections show a visual rejection (red flash + tooltip with reason).
- After creation, the full graph is sent to `PUT /graph` for authoritative server validation.

**Edge deletion:**
- Select an edge and press Delete.
- Or drag a connected input pin away to the empty canvas (disconnect).

**Edge visuals:**
- Edges are drawn as curved lines (bezier curves).
- Edge color matches the data type (e.g., ImagePath = blue, scalar = gray).
- Selected edges are highlighted.

#### 3.3.3 Pins

Input and output pins are the connection points on nodes.

- **Output pins** (right side): One per field in `Outputs`. Label shows the field name. Tooltip shows the type.
- **Input pins** (left side): Only for inputs where `connectable` is `"by_default"` or `"not_by_default"` (declared by the tool author via `GUIMeta`). Fields without `GUIMeta` default to `"not_by_default"`. When a connectable input is connected, the corresponding parameter field in the Node Panel shows the source (e.g., `"cellpose_segmenter_1.mask"`) and the input widget is hidden.

For **DataFrameTool** nodes: positional upstream connections appear as numbered input pins ("1", "2", ...) on the left side. A new pin appears dynamically when the last available pin is connected. **Auto-compact behavior:** when a positional edge is disconnected, higher-numbered pins shift down to fill the gap (e.g., removing pin 1 causes pin 2 to become pin 1). Positional pin order can be changed by disconnecting and reconnecting edges in the desired order.

#### 3.3.4 Canvas Controls

- **Pan:** Middle-click drag, or scroll wheel + Shift
- **Zoom:** Scroll wheel, or pinch gesture
- **Fit view:** Button or shortcut to fit all nodes in view
- **Minimap:** Optional overview in corner
- **Undo/Redo:** Ctrl+Z / Ctrl+Shift+Z (client-side, instant). See [Section 4.6](#46-undoredo).

### 3.4 Tools Panel (Left Sidebar)

Displays the available tools in a PrimeVue table.

**Layout (top to bottom):**
1. **Search bar:** Fuzzy search filtering by name, tags, categories, and keywords.
2. **Tool table:** A hierarchical table where Python packages are parent rows and individual tools are children.

**Columns:**

| Column | Content |
|--------|---------|
| **Package / Name** | Package name on parent row, tool name on child rows |
| **Categories** | Tool categories |
| **Tags** | Tool tags |
| **Versions** | Package versions (on parent row). Expandable version list (see below). |
| **Actions** | Icon buttons (see below) |

**Version management (on package parent row):**

Expanding the package row reveals a **version list** showing all known versions (installed and available). Each version row contains:

| Element | Description |
|---------|-------------|
| **Version number** | e.g., "1.2.0" |
| **Install/Uninstall toggle** | Install button for uninstalled versions, Uninstall button for installed versions. Shows spinning icon during installation. Installation can be interrupted (stop button). |
| **Use in workflow** button | Sets this version as the active version for the current workflow. Only available for installed versions. When clicked, if the workflow already uses a different version of this package, a confirmation dialog is shown: "Changing {package} from {old_version} to {new_version} will mark {N} nodes as out-of-date. Their cached results will need re-execution. Continue?" |
| **Active indicator** | Checkmark icon shown on the version currently used by the active workflow |

Multiple versions of the same package can be installed simultaneously. Each workflow uses **one version per package**, selected via the "Use in workflow" button.

**Action buttons:**

| Button | Scope | Description |
|--------|-------|-------------|
| **Info** | Tool or package | Show detailed documentation (modal or expandable row) |
| **Open in editor** | Tool | Open the tool's source in the code editor |
| **Start/Stop env** | Package | Start or stop the Wetlands environment. Button color/label reflects state: stopped (gray) / creating (yellow) / running (green). |

3. **Create Tool button:** At the bottom. Opens a modal with:
   - Name field
   - Tool type dropdown: ProcessingTool (default) or DataFrameTool
   - Cancel / Create buttons
   - On create: generates tool from standard template, opens in code editor

**Tool templates:**

ProcessingTool template:
```python
from pathlib import Path
from typing import Annotated, Any

from bioimageflow_core import (
    Arguments,
    Category,
    Connectable,
    GENERAL_ENV,
    GUIMeta,
    IOModel,
    ImagePath,
    Layout,
    ProcessingTool,
    Semantic,
    Template,
)

class MyTool(ProcessingTool):
    display_name = "My Tool"
    documentation = "Description of what this tool does."
    category = Category.IMAGE_PROCESSING
    tags = ["custom"]
    environment = GENERAL_ENV

    class Inputs(IOModel):
        input_image: Annotated[
            ImagePath(
                semantics={Semantic.INTENSITY},
                layouts={Layout.PLANAR, Layout.PLANAR_CHANNEL},
            ),
            GUIMeta(
                display_name="Input image",
                description="Image to process.",
                connectable=Connectable.BY_DEFAULT,
            ),
        ]
        # Example scalar parameter:
        # threshold: Annotated[float, GUIMeta(min=0.0, max=1.0, step=0.01)] = 0.5

    class Outputs(IOModel):
        output_image: Annotated[
            ImagePath(semantics={Semantic.INTENSITY}),
            GUIMeta(
                display_name="Output image",
                description="Processed output image.",
            ),
        ] = Template("{input_image.stem}_out{ext}")

    def process_row(self, arguments: Arguments, *, context: Any = None) -> Outputs:
        import shutil

        input_path = Path(arguments.input_image)
        output_path = Path(arguments.output_image)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Replace this pass-through copy with your processing code.
        shutil.copyfile(input_path, output_path)
        return self.Outputs(output_image=output_path)
```

The common-tools package often spells image fields as
`Annotated[Path, ImageSpec(...), GUIMeta(...)]`. The platform scaffold uses the
shorter equivalent `Annotated[ImagePath(...), GUIMeta(...)]`: `ImagePath(...)`
is a convenience factory for `Annotated[Path, ImageSpec(...)]`, and the current
library serializers flatten nested `Annotated` metadata correctly.

DataFrameTool template:
```python
from typing import Annotated, Any

from bioimageflow import DataFrameTool, Passthrough
from bioimageflow_core import Category, Connectable, GUIMeta, IOModel

class MyTransform(DataFrameTool):
    display_name = "My Transform"
    documentation = "Description of what this transform does."
    category = Category.UTILITIES
    tags = ["custom"]

    class Inputs(IOModel):
        column_name: Annotated[str, GUIMeta(
            display_name="Column name",
            description="Optional column name used by your transform.",
            connectable=Connectable.NEVER,
        )] = ""

    class Outputs(Passthrough):
        pass  # Use Passthrough to preserve input columns, or IOModel for explicit schema

    def transform(self, df: Any, arguments: Any) -> Any:
        result = df.copy()
        # Transform the DataFrame here.
        return result
```

**Drag and drop:** Tools can be dragged from the table onto the canvas to create nodes.

### 3.5 Node Panel (Right Sidebar)

Displays details and parameters for the currently selected node(s).

**Multi-selection:** When multiple nodes are selected, the Node Panel shows only bulk actions: Enable/Disable all, Delete all, Clear all. No parameter editing. The Data Table shows the outputs of all selected nodes.

**Single-node layout (top to bottom):**

#### 3.5.1 Header Section

- **Node name** (editable inline field). This is the human-readable display name (`NodeState.name`) — allows spaces and special characters. Must be unique within the workflow. The `NodeState.id` (URL-safe, used in API and edges) is auto-generated from the name on creation and remains stable when the name is renamed. Validated on blur — if duplicate, a red inline error is shown and the previous name is preserved until a valid name is entered.
- **Tool name** (read-only, links to source)
- **Package + version** (read-only, e.g., "bioimageflow-cellpose 1.2.0")
- **Enable/Disable** toggle button
- **Documentation** (collapsible help text from `tool.documentation`)

#### 3.5.2 Action Bar

- **Run** button: Execute this node (and its unexecuted dependencies)
- **Clear** button: Set to Unexecuted, remove output data
- **Stop** button: Visible only while the node is executing
- **Restore parameters** button: Reset all parameters to their values at last execution. **Disabled** with tooltip "No previous execution" when the node has never been executed. If the tool schema changed since the last execution (fields added, removed, or type changed), restored values are applied only for fields that still exist and are type-compatible; incompatible or removed fields are left at their current values, and a toast warns: "Some parameters could not be restored due to schema changes."
- **Open output folder** button: Reveal in system file browser (desktop mode only)

#### 3.5.3 Input Parameters

Each input field from the tool's `Inputs` is rendered as a parameter row. Fields are grouped by category (if the tool defines categories via `GUIMeta.group`; otherwise all in one group).

**Each parameter row contains:**

| Element | Description |
|---------|-------------|
| **Label** | Field name (human-readable) |
| **Default button** | Resets the field to its default value |
| **None toggle** | Two-state button (only shown if the field is `Optional`). When active, the value is `None` and the input field is hidden. |
| **Input field** | The actual value editor (hidden when connected or None). Type depends on the field annotation (see below). |
| **Help text** | Collapsible description from field metadata |
| **Publish toggle** | Two-state button (+ icon). Makes this parameter an input of the sub-workflow when this node is inside a sub-workflow. See [Section 6](#6-sub-workflow-support). |
| **Published name** | Text field for the published parameter name (shown only when published). |

**Input field types:**

| Field Type | Widget | GUIMeta influence |
|------------|--------|-------------------|
| `str` | Text input | -- |
| `int` | Number input (spinner) | `min`, `max`, `step` from GUIMeta |
| `float` | Number input or slider | `min`, `max`, `step` from GUIMeta. If all three are set, render as slider. |
| `bool` | Checkbox | -- |
| `Enum` or `Literal[...]` | Dropdown | -- |
| `Path` (file) | Text input + "Select File" button | Desktop: native dialog. Webapp: opens Dataset Browser. |
| `Path` (directory) | Text input + "Select Folder" button | Desktop: native dialog. Webapp: opens Dataset Browser. |
| `ImagePath` | Text input + "Select File" button (filtered by format spec) | Same as Path |
| `ImageShared` | *Connection-only* (no manual input widget). Shows "Connect to upstream node" placeholder when unconnected. Unconnected required `ImageShared` fields produce a `missing_connection` validation error on the node. | Always connectable, not user-editable. |
| `tuple`, `list` | Inline list editor | -- |

When a connectable input is **connected** (pin has an edge), the input field is replaced by a read-only label showing the source: `"segmenter_1.mask"`.

#### 3.5.4 Output Fields

Each output field from `Outputs` is displayed with editable path templates for path-typed outputs **on `ProcessingTool` nodes only**:

- **Label:** Field name
- **Type badge:** Visual indicator of the type (ImagePath, int, etc.)
- **Path template editor:** *Only for `ProcessingTool` nodes.* For path-typed outputs (`Path`, `ImagePath`, `MaskPath`), a text input showing the current output path template (e.g., `{input_image.stem}_mask{ext}`). The user can edit this to customize output file naming. The template syntax follows the library's output templating engine. Available variables include `node_name`, `row_index`, `timestamp`, `{input_field.stem}`, `{input_field.name}`, `{input_field.ext}`, `{input_field.exts}`, and `{column:name}`. Custom templates are stored in `NodeState.output_templates` (a dedicated dict, separate from `parameters`, to avoid mixing user-facing parameters with internal metadata). If a field has no entry in `output_templates`, the tool's `Template(...)` default is used; otherwise the library's built-in default is used.
- **Non-path outputs** (int, float, str, etc.) are shown read-only.
- **`DataFrameTool` outputs are column declarations, not file paths.** No path-template editor is shown for DataFrameTool outputs, even when a declared column is typed as `Path`/`ImagePath`.
- **Publish toggle** (+ icon): When this node is inside a sub-workflow, each output field has a publish toggle. Published outputs become sub-workflow Outputs (visible as output pins on the parent SubWorkflowNode). By default, terminal node outputs are published.

#### 3.5.4b Resource Configuration

For `ProcessingTool` nodes, the Node Panel includes a collapsible **Resources** section below the output fields. This section allows the user to configure execution resources for the node.

**Display:**

| Field | Widget | Description |
|-------|--------|-------------|
| **CPU** | Number spinner (min: 1) | Number of CPUs to allocate |
| **GPU** | Number spinner (min: 0) | Number of GPUs to allocate |
| **GPU Memory** | Text input (e.g., "8GB") | Minimum GPU memory required |
| **Memory** | Text input (e.g., "16GB") | Memory limit |
| **Max Concurrent** | Number spinner (min: 0, 0=unlimited) | Maximum parallel rows |

**Defaults:** Fields are pre-filled from the tool's `ResourceSpec` declaration (the tool author's minimum requirements). If the tool has no `ResourceSpec`, all fields default to the library defaults (1 CPU, 0 GPU, no memory limit, unlimited concurrency).

**Semantics:** The values in this section are the **execution allocation** — what the engine will actually use when running the node. The tool author's `ResourceSpec` serves as the **minimum floor**: the GUI prevents the user from setting values below the tool's declared minimums (e.g., if the tool declares `gpu=1`, the user cannot set GPU to 0). The user can increase resources above the minimum (e.g., allocate 2 GPUs instead of the tool's required 1).

**Storage:** Resource overrides are stored in `NodeState.resources` — a dedicated dict separate from `parameters` to avoid namespace pollution. Keys are `cpu`, `gpu`, `gpu_memory`, `memory`, `max_concurrent`. The backend uses these to construct a `ResourceSpec` for the engine. If `resources` is empty, the tool's declared `ResourceSpec` is used as-is.

**GPU badge:** Nodes requiring GPU (either from tool declaration or user override) show a small GPU badge (GPU icon) on the node header in the canvas.

#### 3.5.5 Node Output Section

A collapsible section at the bottom of the Node Panel that displays execution output scoped to the selected node.

- **Logs:** The frontend maintains a per-node log buffer in memory (from WebSocket `log` messages with `node_name` field). When a node is selected, this section shows only that node's logs — a filtered view of the same data as the Logger Panel.
- **Error display:** For failed nodes, the error message and traceback are displayed prominently at the top of this section with a red background. The `node_state` WebSocket message for failed nodes includes `error` and `traceback` fields (see `NodeStatus` model in Section 2.4.3).
- **Level filter buttons:** DEBUG / INFO / WARNING / ERROR, defaulting to INFO+.
- Logs are kept in memory for the duration of the session and cleared on new execution.

### 3.6 Data Table (Bottom Panel, Tab 1)

Displays the output DataFrames of selected nodes in a tabular view.

**Behavior:**
- When one or more nodes are selected, the table shows their outputs.
- When no nodes are selected, the table shows the terminal node(s) outputs.
- If selected nodes have no output yet, a placeholder message is shown.
- **Disabled nodes:** If a disabled node was previously executed, the Data Table shows its cached data with a dimmed appearance and a banner: "This node is disabled." If a disabled node has no cached data, the standard placeholder is shown. When no nodes are selected and all terminal nodes are disabled, the placeholder reads: "All terminal nodes are disabled."

**Layout — vertical flex column:**

When multiple nodes are selected, their DataFrames are displayed in a **vertical flex column layout** (stacked vertically, not in separate tabs). Each DataFrame has a header showing the node name and its own independent pagination controls (page selector, page size). The user can scroll through all DataFrames in a single view for quick comparison.

**Summary DataFrame:** When possible, a **Summary DataFrame** is displayed at the top, above the individual DataFrames. This summary is an **outer join on index** of all selected contiguous nodes' DataFrames. NaN values fill gaps where indices don't match. Column headers include a tooltip with the originating node name. The summary join is computed **server-side** via `POST /api/v1/nodes/summary` (see below) to handle large DataFrames correctly with pagination.

- **When summary is shown:** The summary is attempted whenever all selected nodes share a **common index lineage** — i.e., all selected nodes' indices are derived from the same root index (possibly through explosions). This is more permissive than requiring a strict linear chain: selecting a parent node and its two children (a fork) produces a valid summary.
- **When summary is not shown:** If selected nodes have no common index lineage (e.g., two independent source branches), or if duplicate column names exist across DataFrames, the summary is omitted. The server returns an error with a reason, and the frontend shows a subtle message: "Summary unavailable — no common index lineage" or "Summary unavailable — column name conflict."

**Display limit:** When more than 5 nodes are selected, only the first 5 DataFrames are shown, with a "Show all ({N})" toggle to display the rest.

**Single node selected:** Show that node's output DataFrame only. No summary needed.

**Table features:**
- **Column types:** Columns are annotated with their type. Image columns show special rendering.
- **Pagination:** Large DataFrames are paginated (server-side, via `/nodes/{node_id}/data?page=0&page_size=50`).
- **Sorting:** Click column header to sort.
- **Image cells:** For columns typed as `ImagePath` or `ImageShared`:
  - Show a thumbnail (loaded lazily from `/nodes/{node_id}/thumbnail?row=0&col=mask`)
  - **View image** button: Desktop mode opens in Napari (`POST /napari/open`). Ctrl+Click clears existing layers. Webapp mode opens in Viv (in-browser).
  - **Reveal in file browser** button (desktop mode only).
- **Scalar cells:** Show the value directly.
- **Path cells (non-image):** Show the filename with two buttons:
  - **Open** button: Opens in the code editor (for CSV, JSON, tabular data).
  - **Reveal in file browser** button (desktop mode only).

### 3.7 Logger Panel (Bottom Panel, Tab 2)

Displays real-time logs streamed via WebSocket.

**Features:**
- **Level filter:** Buttons to toggle DEBUG / INFO / WARNING / ERROR visibility
- **Node filter:** Filter logs by node name (dropdown or auto-filter when nodes are selected)
- **Search:** Text search within logs
- **Auto-scroll:** Follows new messages (toggleable)
- **Timestamps:** Shown in local time
- **Log entries include:** timestamp, level, node name (if applicable), message
- **Color coding:** DEBUG=gray, INFO=default, WARNING=yellow, ERROR=red

### 3.8 Workflow Panel (Menu / Toolbar)

Accessed via the menu bar or a dedicated toolbar area.

**Actions:**
- **New workflow:** Opens a creation dialog with fields: display name (free-form), name (auto-generated from display name, editable, restricted to `[a-zA-Z0-9_-]`), description (optional, multiline), and storage path. On name conflict, the server suggests an alternative.
- **Open workflow:** Shows list of saved workflows (display name, description, last modified). Opening a new workflow closes the current one (with save prompt).
- **Edit workflow:** Each workflow in the list has an **Edit** button that opens an "Edit workflow" dialog to modify the display name, description, and storage path. The `name` (filesystem identifier) cannot be changed after creation.
- **Drag to canvas:** Workflows listed in the panel can be **dragged onto the canvas** to create a SubWorkflowNode (see Section 6.1).
- **Save:** Saves current workflow state including GUI state (Ctrl+S). The full graph JSON (with positions, collapsed state, etc.) is sent to `PUT /workflows/{name}`. Saving always succeeds regardless of validation errors. Uses atomic writes (write to a temporary file, then rename) to prevent corruption on crashes or disk-full errors.
- **Save as / Duplicate:** Save under a new name
- **Export:** Export to JSON (downloads file)
- **Import:** Import from JSON file
- **Delete:** Delete with confirmation. Deletes the workflow file, all cached output data in the storage directory, and clears the auto-saved IndexedDB state for this workflow.

### 3.9 Execution Panel (Menu / Toolbar)

**Buttons:**
- **Run Workflow**: Execute all enabled nodes that are Unexecuted or Out-of-date. Shows a confirmation dialog: "The following out-of-date nodes will be re-executed, replacing their previous outputs: [list]. Continue?" **Disabled** when a validation request is pending or the debounce timer is active. If clicked during the debounce window, the frontend flushes the debounce (sends `PUT /graph` immediately), waits for the validation response, and only then proceeds with execution. If validation fails after the flush, execution is aborted and a toast is shown: "Validation errors found — fix them before running."
- **Run Selected:** Run only the currently selected nodes (and all their out-of-date or unexecuted dependencies). Sends `POST /execution/run` with `nodes` set to the selected node names. Also available via right-click context menu on selected nodes. Same debounce-flush behavior as Run Workflow.
- **Stop:** Cancel the current execution. Visible only during execution.

**During execution — Non-Modal Execution Banner:**

Instead of a blocking modal, the GUI shows a **persistent execution banner** at the top of the canvas. The user can inspect completed nodes, view the Data Table, and browse the Logger Panel while execution is in progress. Graph **mutations** are locked (node/edge creation, deletion, parameter changes, drag-to-reorder), but read-only inspection is allowed.

- **Banner content:** "Executing workflow..." + overall progress bar (nodes completed / total) + current node name + row progress bar + **Stop** button.
- **Canvas overlay:** Running nodes show a pulsing blue border. Completed nodes turn green in real-time.
- **Locked interactions during execution:** Adding/removing nodes or edges, changing parameters, enable/disable toggle, clear outputs, save workflow, undo/redo. These actions are grayed out with a tooltip: "Locked during execution." **This applies to all open tabs** — sub-workflow tabs are locked identically to the parent workflow tab.
- **Allowed interactions during execution:** Selecting nodes, viewing the Node Panel (read-only), browsing the Data Table (completed nodes show their output), scrolling the Logger Panel, panning/zooming the canvas, opening images in Napari/Viv.
- **Stop button:** Cancels execution. The banner updates to "Execution stopped" and disappears after 3 seconds (or on click).
- **On completion:** The banner shows "Execution complete" (green) or "Execution failed" (red, with error summary) and disappears after 5 seconds (or on click). On failure, the failed node is auto-selected so its error is visible in the Node Panel.
- **Safety guarantee:** Since all graph mutations are locked, the running workflow cannot be affected by user actions. The server also rejects graph validation and cache clearing during execution with HTTP 423 Locked.

### 3.10 Code Editor Panel

An embedded VS Code instance served by code-server (installed and configured locally automatically).

**Implementation:** An iframe loading the code-server URL. The URL is obtained from `GET /editor/status`.

**Interactions:**
- Opening a tool's source folder (from Tools Panel) sends `POST /editor/open` with the folder path.
- The backend either opens the path in code-server or in the user's configured external editor (see Settings).

### 3.11 Image Viewer

**Desktop mode — Napari:**

Napari is managed by the backend via Wetlands (isolated Conda environment). The backend uses a `NapariLauncher` that:

1. Creates or reuses a Conda environment with `napari` and `pyqt` via Wetlands
2. Launches a `napari_manager.py` script in that environment
3. Communicates via `multiprocessing.connection` (Client/Listener on localhost)
4. Auto-reconnects if Napari crashes or is closed by the user

**Interactions:**
- **Open in Napari:** Triggered from Data Table image cells. Sends `POST /napari/open {paths, clear_layers: false}`.
- **Replace in Napari (Ctrl+Click):** Same endpoint with `clear_layers: true`.
- Napari is launched lazily on first use.

**Webapp mode — Viv:**

The frontend uses [Viv](https://github.com/hms-dbmi/viv) for in-browser image viewing. Viv supports OME-TIFF, OME-Zarr, and common bioimage formats with pan/zoom/contrast controls and 3D orthogonal projections. Images are loaded from the server via `GET /nodes/{node_id}/image?row=N&col=field` (see Section 2.4.4b). For OME-Zarr data, Viv loads directly from the static file tree served at `/nodes/{node_id}/zarr/{row}/{col}/`.

### 3.12 Error Handling

Three levels of error display:

**Validation errors:** Inline red border on the affected parameter field + tooltip with the error message. For invalid edges: visual rejection (red flash) + toast notification with reason.

**Execution errors:** Failed nodes turn red. The Node Panel's Output section (Section 3.5.5) shows the error message and traceback. The error is also logged in the Logger Panel. The GUI shows: "Node failed on row {N} of {total}. All results for this node were discarded. Fix the issue and re-run."

**System errors:** A global error indicator (icon in the top bar). The indicator is visible whenever one or more errors have occurred. Clicking it opens a sliding panel showing the error history. Each error entry includes timestamp, type, and message, and can be dismissed individually (cross button). Auto-dismiss for transient WebSocket reconnections.

### 3.13 Settings Panel

A dedicated panel or modal for application configuration. Settings are persisted as a JSON file at `~/.bioimageflow/settings.json`. Defaults are applied for any missing keys.

#### 3.13.1 Code Editor Settings

- **External editor command:** Text field. Placeholder: `code {file_path}`. The `{file_path}` token is replaced with the actual path. If empty, the built-in code-server editor is used.

#### 3.13.2 Napari Settings

- **Napari environment path:** Path to an existing Napari Conda environment. If set, BioImageFlow uses this instead of creating one via Wetlands. Desktop mode only.

#### 3.13.3 OMERO Settings

OMERO integration is provided through dedicated tools (ProcessingTools with OMERO dependencies in their environment), not through core GUI features. The GUI only provides credential management here. The OMERO tools handle downloading and uploading (not browsing).

- **Instance list:** Add/remove/duplicate OMERO server configurations.
- Per instance:
  - Name (optional, defaults to `host:username`)
  - Host
  - Port (number)
  - Username
  - Password (stored via Python keyring, not sent/stored in plaintext via API)

#### 3.13.4 Update Settings

- **Version dropdown:** Choose which BioImageFlow version to use, or "auto-update" (default). Choices are refreshed at startup and when opening settings.

#### 3.13.5 Storage

- **Output data folder** path display + "Reveal in file browser" button (desktop mode only)
- **Tool store path** display (default: `~/.bioimageflow/tool_packages/`)
- **Wetlands path** display (default: `~/.bioimageflow/wetlands/`, resolved by `bioimageflow.paths.get_wetlands_path()`)

#### 3.13.6 Keyboard Shortcuts

Shortcuts are customizable. The settings panel shows a table of all shortcuts with editable key bindings.

### 3.14 Dataset Browser (Webapp Mode Only)

A **modal dialog** for managing and selecting datasets when running as a web application. Not shown in desktop mode (which uses native file dialogs).

**Modal layout (opened when user clicks "Select File"/"Select Folder" on a Path parameter):**
- **Title bar:** "Select dataset for: {parameter_name}"
- **Dataset table:** Lists all datasets for the current user. Columns: filename, size, upload date. Single-selection. Search/filter bar at top.
- **Upload button:** Opens the browser's native file picker. Uploaded files appear in the table with a progress bar. Supports multi-file selection.
- **Action buttons:** "Cancel" / "Select" (disabled until a row is selected). "Select" sets the dataset's server-side path as the parameter value and closes the modal.
- **Delete button:** Remove a dataset from the server.

### 3.15 Drag and Drop (File Import)

Users can drag and drop files (images, CSVs, etc.) onto the application window.

**Desktop mode:** Dropping files creates a "Files" DataFrameTool source node on the canvas, pre-configured to list the dropped file paths. The paths are local filesystem paths.

**Webapp mode:** Dropping files:
1. Opens the Dataset Browser modal
2. Automatically starts uploading the dropped files
3. Once upload completes, the user selects the uploaded dataset
4. A "Files" source node is created with the server-side paths

File size limit: configurable, default 2GB. Upload progress is shown per file. On timeout or failure, an error toast is shown with a retry option.

---

## 4. Data Flow and State Synchronization

### 4.1 Principle

The **frontend is the source of truth** for the graph state (nodes, edges, positions, parameters). The **server is the authority** for validation and execution. The workflow is:

1. User edits the graph in the frontend (instant, no round-trip)
2. Frontend debounces changes (300ms) then sends the full graph to `PUT /graph` for validation (cancelled and re-sent on new edits)
3. Server returns validation errors + per-node status (executed, cached, out-of-date)
4. Frontend updates node visual states accordingly
5. On "Run", the frontend sends the graph to `POST /execution/run`; the server validates, builds the Workflow, and executes
6. During execution, the Execution Banner is shown; graph mutations are locked; progress and state updates arrive via WebSocket
7. On execution complete, the banner auto-dismisses; the frontend sends `PUT /graph` to refresh all node statuses

### 4.2 Node State Transitions

```
                    +-----------+
           create   |           |  disable
       +----------->| Unexecuted|----------+
       |            |  (blue)   |          |
       |            +-----+-----+          v
       |                  |           +---------+
       |              run |           | Disabled|
       |                  v           |  (gray) |
       |           +------+------+    +---------+
  clear|           |   Running   |         ^
       |           | (blue pulse)|         |
       |           +------+------+    enable|
       |                  |           (restore
       |          +-------+-------+   previous
       |          |               |   state)
       |          v               v
       |   +------+------+ +-----+-----+
       +---+  Executed   | |   Failed  |
           |  (green)    | |   (red)   |
           +------+------+ +-----------+
                  |
          change  |
          params  v
           +------+------+
           | Out-of-date |
           |  (orange)   |
           +-------------+
```

**Disabled node semantics** (aligned with bioimageflow library Section 4.6):

- **Disabled nodes are not executed.** No cache lookup, no computation, no side effects.
- **Implicit skip propagation.** Any enabled node whose upstream includes a disabled node is skipped during execution. These nodes remain displayed as "unexecuted" — no special visual encoding is needed.
- **Graph structure is preserved.** Disabling does not alter edges, bindings, or registration. Re-enabling restores the original wiring.
- **Cache is unaffected.** The `enabled` flag is NOT part of the signature hash. Re-enabling a node with unchanged parameters hits existing cache.
- **Serialization:** The `enabled` flag is persisted in the workflow JSON (`"enabled": false` when disabled, omitted when enabled).

**Out-of-date detection:** Out-of-date status is **server-authoritative**. The server determines whether a node is out-of-date by comparing the current parameters and upstream signature hashes against cached results (via `PUT /graph` response). The frontend does not maintain `last_execution_params` for out-of-date detection. When the user modifies parameters, the node status is shown as "unconfirmed" (desaturated) until the next `PUT /graph` response arrives.

### 4.3 Auto-Save and Startup Recovery

The frontend auto-saves the current graph state to **IndexedDB** on every modification (debounced at 500ms). IndexedDB is used instead of `localStorage` to avoid the ~5–10MB size limit and to support large workflows with many nodes. This protects against browser crashes, accidental tab closure, or server failures.

**Startup recovery flow:**

```
App starts
  |
  +--> GET /api/v1/tools (populate tool panel)
  |
  +--> Connect WebSocket /ws
  |
  +--> Check IndexedDB for auto-saved graph state
  |
  +--> If auto-save exists:
  |      Load graph from IndexedDB automatically (no confirmation dialog)
  |      Show dot/asterisk (*) beside workflow title to indicate unsaved changes
  |      The user can revert to the last server-saved version via Ctrl+Z (undo) or the Edit > Undo menu
  |      Send PUT /api/v1/graph for validation
  |
  +--> If no auto-save:
  |      If a "last opened" workflow name is saved in user settings:
  |        Load it via GET /api/v1/workflows/{name}
  |      Else:
  |        Create new empty workflow (POST /api/v1/workflows with default name)
  |
  +--> Application ready
```

**Unsaved state indicator:** The workflow title in the menu bar shows `"My Workflow *"` when the current graph differs from the last saved version. The asterisk disappears on `Ctrl+S` (save). Closing a workflow with unsaved changes shows a confirmation: "Discard unsaved changes?"

Manual save (Ctrl+S) persists to a real file on the server via `PUT /workflows/{name}`.

**Tab-level locking:** The frontend uses a `BroadcastChannel` (or `localStorage`-based lock) to prevent multiple browser tabs from editing the same workflow simultaneously. When a tab detects that another tab is already editing the same workflow, it opens in **read-only mode** with a banner: "This workflow is open in another tab. Close that tab to edit here."

### 4.4 Mapping GUI to Library

| GUI Concept | Library Concept |
|-------------|----------------|
| `ColumnRefEdge` (output pin to input pin) | `ColumnRef` (keyword arg) |
| `PositionalEdge` (node to DataFrameTool positional pin) | Positional argument in `DataFrameTool.__call__` |
| Parameter value in Node Panel | Constant keyword argument |
| Pin visibility on a node | Determined by `GUIMeta.connectable` field metadata (set by tool author) |
| "Run" button | `workflow.compute(node)` |
| Node position, collapsed state | GUI-only state (stored in workflow file under `gui` section) |
| Package version in Tools Panel | `tool_package_version` in library serialization format |

### 4.5 Workflow Persistence

The workflow file (JSON) contains both the library workflow data and GUI-specific state:

```json
{
  "workflow": { "...library export format (includes tool_package + tool_package_version per node)..." },
  "gui": {
    "nodes": {
      "cellpose_segmenter_1": {
        "position": [350, 200],
        "collapsed": false
      }
    }
  }
}
```

Panel layout preferences (which panels are open, sizes) are stored in **user-level settings** (not per-workflow).

### 4.6 Undo/Redo

Undo/redo is purely client-side. The frontend maintains an undo stack of graph state snapshots.

- **Undoable operations:** Node add/remove, edge add/remove, parameter changes, node position changes, sub-workflow creation (restores all internal nodes, edges, and positions to the canvas). All are pure client-side graph state changes.
- **Not undoable:** Execution, clear outputs, save, tool installation. These have server-side effects that can't be reversed by restoring client state. The frontend shows a confirmation dialog for destructive operations (Clear already does, per Section 3.5.2).
- **Granularity:** Each user action is one undo step. A parameter change is captured on blur/Enter (not per keystroke). Moving multiple selected nodes is one step.
- **Stack size:** 100 steps (configurable). Oldest entries are dropped.
- **On workflow load:** Undo history is cleared (no mixing undo stacks across workflows).

---

## 5. Edge Cases and Error Scenarios

### 5.1 Tool Not Found

A workflow references a tool that is no longer installed (package uninstalled, or workflow imported from another machine).

The node is rendered with a red "Tool not found" badge. The Node Panel shows the tool name and a "Install package" button (if the package is known in the tool store registry). The node cannot be executed until the tool is available.

### 5.2 Missing Package Version

A workflow requires a tool package version that is not in the tool store (e.g., workflow saved with `bioimageflow-cellpose==1.2.0` but only `1.3.0` is installed).

On load, the server reports missing packages in the load response. The frontend shows a dialog: "This workflow requires packages not installed: [list]. Install them?" Options:
- **Install required versions:** Installs the exact versions into the tool store.
- **Use installed versions:** Updates the workflow to use the versions currently in the tool store. All affected nodes are marked Out-of-date.

---

## 6. Sub-Workflow Support

Sub-workflows are fully supported by the BioImageFlow library (see `specs.md` Section 14). The GUI provides visual creation and editing of sub-workflows.

### 6.1 Creating a Sub-Workflow

**From selection:**

1. The user selects a group of nodes on the canvas.
2. Right-click → "Create sub-workflow."
3. The selected nodes are wrapped into a `SubWorkflowNode`:
   - **Inputs auto-detection:** Edges entering the selection from outside become sub-workflow input pins. Each edge creates its own pin, even if the same `(source_node, source_output)` pair feeds multiple internal nodes. This allows the user to rewire inputs independently after creation.
   - **Outputs auto-detection:** Edges leaving the selection to outside become sub-workflow output pins.
   - If the selected nodes have no external connections, the sub-workflow is valid as a **detached branch** with no inputs/outputs. It can be executed independently from the rest of the graph.
4. The user can fine-tune the sub-workflow's interface using the **publish toggle** (Section 3.5.3): any internal parameter can be promoted to the sub-workflow's Inputs, making it configurable on the outer node.
5. This operation is **undoable** as a single undo step. Undoing restores all internal nodes, edges, and positions to the canvas and removes the SubWorkflowNode.

**From Workflow Panel:** Saved workflows can be **dragged from the Workflow Panel** onto the canvas, creating a SubWorkflowNode. The dragged workflow becomes the sub-workflow's internal DAG. **Default derivation:** All source node constant parameters are published as sub-workflow Inputs, and all terminal node output columns are published as sub-workflow Outputs. The user can then adjust visibility using the publish toggle on each parameter and output field.

### 6.2 Rendering

- **SubWorkflowNode** is displayed with a **thick border** (vs. thin for tool nodes).
- Sub-workflow **Inputs** appear as input pins on the left.
- Sub-workflow **Outputs** appear as output pins on the right.

### 6.3 Editing

- **Double-click** a SubWorkflowNode to open its internal DAG in a **new tab** (the same behavior as opening a workflow from the Workflow Panel).
- The tab title shows the sub-workflow node name (e.g., `segment_and_measure_1`).
- The user can edit internal nodes, parameters, and connections within this tab.
- **Save semantics:** Changes to the sub-workflow's internal DAG are applied to the parent on explicit save (Ctrl+S within the sub-workflow tab). The parent workflow does not see intermediate edits. Closing the tab with unsaved changes shows a confirmation dialog: "Discard unsaved changes to sub-workflow '{name}'?"
- Closing the sub-workflow tab returns focus to the parent workflow tab.

### 6.4 Execution and Caching

Per the library spec:
- The engine **flattens** the sub-workflow into constituent internal nodes at execution time. Internal nodes get scoped names (e.g., `segment_and_measure_1/cellpose_segmenter_1`).
- **Caching is per-internal-node**, not per-sub-workflow.
- Each sub-workflow instance has its own parameter values (stored on the parent-level node).

### 6.5 Nesting

Sub-workflows may contain other sub-workflows. Double-clicking a nested sub-workflow opens another tab. The engine flattens recursively at execution time.

---

## 7. Keyboard Shortcuts

All shortcuts are customizable via Settings (Section 3.13.6).

**Defaults:**

| Shortcut | Action |
|----------|--------|
| `Delete` / `Backspace` | Delete selected nodes/edges |
| `Ctrl+Z` | Undo (client-side) |
| `Ctrl+Shift+Z` | Redo (client-side) |
| `Ctrl+C` | Copy selected nodes (+internal edges) |
| `Ctrl+V` | Paste |
| `Ctrl+A` | Select all nodes |
| `Ctrl+S` | Save workflow |
| `Ctrl+Enter` | Validate immediately (skip debounce) |
| `Ctrl+F` | Focus tool search bar |
| `Space` (hold) | Pan mode |
| `F` | Fit all nodes in view |
| `Escape` | Deselect all / cancel current action |

---

## 8. API Endpoint Summary

| # | Method | Endpoint | When used |
|---|--------|----------|-----------|
| 1 | `GET` | `/api/v1/tools` | Startup; after package install/uninstall |
| 2 | `POST` | `/api/v1/tools` | "Create Tool" button in Tools Panel |
| 3 | `DELETE` | `/api/v1/tools/{tool_name}` | Delete button on user-created tool |
| 4 | `PATCH` | `/api/v1/tools/{tool_name}` | Rename a user-created tool |
| 5 | `GET` | `/api/v1/tools/{tool_name}/source` | "Open in editor" button in Tools Panel |
| 6 | `GET` | `/api/v1/tools/packages` | Startup; Tools Panel package list |
| 7 | `POST` | `/api/v1/tools/packages/{name}/install` | Install button in Tools Panel; version change |
| 8 | `DELETE` | `/api/v1/tools/packages/{name}` | Uninstall button in Tools Panel |
| 9 | `POST` | `/api/v1/tools/environments/{name}/start` | Start env button in Tools Panel; pre-warming |
| 10 | `POST` | `/api/v1/tools/environments/{name}/stop` | Stop env button in Tools Panel; freeing resources |
| 11 | `GET` | `/api/v1/workflows` | Startup; "Open workflow" menu |
| 12 | `POST` | `/api/v1/workflows` | "New workflow" menu; startup (if no existing workflow) |
| 13 | `GET` | `/api/v1/workflows/{name}` | Opening a saved workflow |
| 14 | `PUT` | `/api/v1/workflows/{name}` | Ctrl+S save; "Save" menu |
| 15 | `DELETE` | `/api/v1/workflows/{name}` | "Delete workflow" menu |
| 16 | `PATCH` | `/api/v1/workflows/{name}` | Rename or duplicate workflow |
| 17 | `POST` | `/api/v1/workflows/{name}/export` | "Export" menu (download JSON) |
| 18 | `POST` | `/api/v1/workflows/import` | "Import" menu (upload JSON) |
| 19 | `PUT` | `/api/v1/graph` | On all meaningful graph changes (debounced 300ms) |
| 20 | `GET` | `/api/v1/nodes/{node_id}/data` | Selecting a node to view its output in Data Table |
| 21 | `GET` | `/api/v1/nodes/{node_id}/data/csv` | "Download CSV" button in Data Table |
| 22 | `GET` | `/api/v1/nodes/{node_id}/thumbnail` | Lazy-loading image thumbnails in Data Table cells |
| 23 | `GET` | `/api/v1/nodes/{node_id}/status` | WebSocket reconnection (resync node states) |
| 24 | `POST` | `/api/v1/execution/run` | "Run Workflow" / "Run Selected" buttons |
| 25 | `POST` | `/api/v1/execution/stop` | "Stop" button in execution banner |
| 26 | `POST` | `/api/v1/execution/clear` | "Clear" button in Node Panel |
| 27 | `GET` | `/api/v1/execution/status` | WebSocket reconnection (resync execution state) |
| 28 | `GET` | `/api/v1/settings` | Opening Settings panel; startup (deployment mode) |
| 29 | `PATCH` | `/api/v1/settings` | Changing any setting |
| 30 | `POST` | `/api/v1/fs/reveal` | "Open output folder" or "Reveal in file browser" (desktop only) |
| 31 | `GET` | `/api/v1/datasets` | Opening Dataset Browser modal (webapp mode) |
| 32 | `POST` | `/api/v1/datasets/upload` | Upload button in Dataset Browser modal (webapp mode) |
| 33 | `DELETE` | `/api/v1/datasets/{id}` | Delete button in Dataset Browser modal (webapp mode) |
| 34 | `POST` | `/api/v1/napari/open` | "Open in Napari" button in Data Table (desktop only) |
| 35 | `GET` | `/api/v1/napari/status` | Checking Napari availability (desktop only) |
| 36 | `POST` | `/api/v1/editor/open` | "Open in editor" from Tools Panel or Data Table |
| 37 | `GET` | `/api/v1/editor/status` | Checking code-server availability for embedded editor |
| 38 | `GET` | `/api/v1/health` | Health check (monitoring, reverse proxy) |
| 39 | `POST` | `/api/v1/nodes/summary` | Summary DataFrame for multi-node selection |
| 40 | `GET` | `/api/v1/nodes/{node_id}/image` | Full image file for Viv viewer |

Total: 40 endpoints.

---

## 9. Security

### 9.1 Authentication

- **Desktop mode:** No authentication required. The server binds to `localhost` only.
- **Webapp mode:** All API endpoints require a session token or API key (passed as `Authorization: Bearer <token>` header). The authentication mechanism is a simple shared secret configured at deployment time. Multi-user authentication is deferred to a future version.

### 9.2 Desktop-Only Endpoints

The following endpoints are **disabled in webapp mode** (return HTTP 403 Forbidden):

- `POST /fs/reveal` — filesystem access
- `POST /napari/open` — launches a desktop process
- `GET /napari/status`

### 9.3 Tool Creation and Editing (Webapp Mode)

In **webapp mode**, the following are disabled to prevent remote code execution:

- `POST /tools` — tool creation is disabled
- `POST /editor/open` — source editing is disabled
- Tool hot-reload (Section 2.7) is disabled

Tool packages can still be installed from the **known packages list** (see Section 9.5) via the Tools Panel. Only packages on this pre-defined list are available for installation — users cannot install arbitrary PyPI packages. ProcessingTools are sandboxed by Wetlands; DataFrameTools from known packages run in the main process.

### 9.4 Dataset Upload Validation

The `POST /datasets/upload` endpoint (webapp mode) enforces:

- **Filename sanitization:** Path separators are stripped, filenames are limited to 255 characters, only alphanumeric characters, hyphens, underscores, and dots are allowed. The original filename is stored as metadata but the file is saved under a sanitized name.
- **File size limit:** Configurable, default 2GB per file.
- **Path traversal prevention:** Uploaded files are always stored in the dedicated datasets directory. The server resolves the final path and verifies it is within the allowed directory before writing.

### 9.5 Available Package Versions

Tool packages are published on **PyPI**. The server queries PyPI's JSON API (`https://pypi.org/pypi/{package_name}/json`) to retrieve available versions. The response's `releases` field lists all published versions. The server caches this response for 1 hour per package. The list of known BioImageFlow tool packages is maintained in a configuration file (`~/.bioimageflow/known_packages.txt`) that is updated at startup from a central registry URL. **Registry requirements:** The URL must use HTTPS. The request has a 5-second timeout. If the registry is unavailable, the server falls back gracefully to the bundled default list.

---

## 10. Future Work: Webapp Sandboxing and Multi-User

### 10.1 The DataFrameTool Security Problem

In the current architecture, `DataFrameTool` runs in the **main server process** (the same process that hosts FastAPI, manages the Workflow, and holds all state). This is by design — DataFrameTools need full pandas access and benefit from zero-overhead DataFrame manipulation. However, in webapp mode, this means any DataFrameTool code (including from installed PyPI packages) has unrestricted access to the server's filesystem, network, and memory.

Sandboxing ProcessingTools is straightforward (Wetlands already isolates them in separate processes). Sandboxing DataFrameTools is harder because their core abstraction — "I transform DataFrames in the main process" — is inherently incompatible with process-level isolation.

Three approaches were evaluated:

| Approach | Description | Spec Impact | Drawbacks |
|----------|-------------|-------------|-----------|
| **Per-user container** | Each user's entire BioImageFlow server runs in a rootless Podman container | None (operational only) | Higher resource usage per user |
| **DataFrameTool in worker** | Move DataFrameTools to sandboxed workers (like ProcessingTools) | Major — redesigns a core abstraction | DataFrame serialization overhead, blurs tool type distinction |
| **Hybrid trust model** | Sandbox only user-created DataFrameTools, trust installed packages | Moderate — two execution paths | Complexity, "trusted" is a judgment call |

### 10.2 Recommended Architecture: Per-User Containers

The recommended approach for webapp mode is to run each user's BioImageFlow server inside a **rootless Podman container**. This provides full isolation without changing the library architecture.

```
                    ┌─────────────────────────────────┐
                    │        Launcher Service          │
                    │  (auth, container orchestration) │
                    └──────────┬──────────────────────┘
                               │
                    ┌──────────▼──────────────────────┐
                    │       Reverse Proxy (nginx)      │
                    │   routes /api/user_token → container
                    └──┬───────────┬──────────────────┘
                       │           │
          ┌────────────▼──┐  ┌────▼─────────────┐
          │ Podman (user1) │  │ Podman (user2)   │
          │                │  │                  │
          │ FastAPI server │  │ FastAPI server   │
          │ bioimageflow   │  │ bioimageflow     │
          │ DataFrameTools │  │ DataFrameTools   │
          │   ├─ Wetlands  │  │   ├─ Wetlands    │
          │   │  workers   │  │   │  workers     │
          │   └─ Napari    │  │   └─ Napari      │
          └────────────────┘  └──────────────────┘
```

**Why this approach:**

1. **Zero library spec changes.** DataFrameTool keeps its "main process" semantics. ProcessingTool keeps its Wetlands isolation. The sandboxing is purely operational.

2. **The DataFrameTool design is architecturally correct.** Merge/filter/aggregate operations are fundamentally DataFrame-level and benefit from running in-process with full pandas access. Forcing them into workers would add serialization overhead and blur the clean separation between "per-row processing in isolated env" (ProcessingTool) and "holistic DataFrame manipulation" (DataFrameTool).

3. **Standard pattern.** Per-user containers is the established approach for multi-tenant compute platforms (JupyterHub, Google Colab, Gitpod). Proven and well-understood.

4. **Solves multi-user.** Each container is a user session with its own filesystem namespace, tool store, and workflow state.

### 10.3 Launcher Service

A new lightweight service (`bioimageflow-launcher`) manages user containers:

**Responsibilities:**
- **Authentication:** Validates user credentials (OAuth, LDAP, or simple token-based).
- **Container lifecycle:** Spins up a rootless Podman container on first request, reuses it for subsequent requests, stops it after an idle timeout (configurable, default 30 minutes).
- **Reverse proxy:** Routes HTTP and WebSocket traffic to the correct container based on the user's session token.
- **Resource limits:** Configures per-container CPU, memory, and GPU limits via Podman `--cpus`, `--memory`, `--device` flags.
- **Data volumes:** Mounts the user's dataset directory and workflow directory into the container. The tool store (`~/.bioimageflow/tool_packages/`) can be shared read-only across all containers to avoid duplication.

**Container image:** A pre-built image containing Python, `bioimageflow`, `bioimageflow-core`, pandas, and code-server. Tool packages are mounted from the shared tool store. Wetlands environments are created inside the container.

**Startup latency:** ~2–5 seconds for container creation (cached image). Subsequent requests within the same session hit the existing container instantly.

**GPU support:** Podman supports GPU passthrough via `--device nvidia.com/gpu=all` (requires `nvidia-container-toolkit`). The launcher can allocate specific GPUs to containers based on resource requests.

### 10.4 Impact on Current Specs

| Component | Change Required |
|-----------|----------------|
| `bioimageflow-core` | None |
| `bioimageflow` (library) | None |
| GUI backend (FastAPI) | None (runs inside the container as-is) |
| GUI frontend | Minimal — authentication flow (login page, token management) |
| Deployment | New: launcher service, Podman configuration, container image build |
| Settings | New: launcher config (idle timeout, resource limits, auth provider) |

### 10.5 Desktop Mode

Desktop mode is unaffected. No containers, no launcher, no authentication. The FastAPI server runs directly on the user's machine, bound to `localhost`. This is the current architecture and remains unchanged.

---

## 11. Future Enhancements

### 11.1 Step-by-Step Execution

The library provides `compute_steps()` for step-by-step execution with per-node control (prepare, execute). A future "Step" execution mode could execute one node at a time, pausing between nodes for intermediate inspection. This enables richer debugging without changing the current `compute()` flow.
