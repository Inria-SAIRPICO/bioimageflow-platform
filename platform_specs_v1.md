# BioImageFlow Platform Specifications — v1 (MVP)

The library specs are at /Users/amasson/Travail/bioimageflow-platform/bioimageflow/docs/source/specs.md . Make sure you read this first.

This is the desktop-only MVP specification for the BioImageFlow GUI. It covers the core feature set needed for a fully functional single-user desktop application. For the comprehensive reference including webapp mode, sub-workflows, and planned future features, see `platform_specs_full.md`.

---

## 1. Overview

The BioImageFlow GUI is a desktop application for building, executing, and inspecting bioimage analysis workflows visually. It wraps the BioImageFlow library (see `specs.md`) with a node-based editor, parameter panels, data viewers, and execution controls.

**Architecture:** The GUI follows a client-server model. The backend is a Python server (FastAPI) that wraps the BioImageFlow library and exposes a REST + WebSocket API. The frontend is a Vue SPA that communicates with the backend exclusively through this API. The application is packaged with pywebview, giving access to native file dialogs.

**Desktop vs. browser runtime detection.** The same frontend bundle runs in two environments:

- **Inside pywebview (desktop).** The frontend detects this at runtime by checking for `window.pywebview` (injected by pywebview into the page). Path selection uses the native OS file dialogs exposed via `window.pywebview.api` (`select_file`, `select_files`, `select_folder`, `save_file`). Drag-and-dropped files are treated as local filesystem paths — the user's machine and the server share the same filesystem.
- **In a plain browser.** When `window.pywebview` is absent (e.g., the user pointed a browser at the FastAPI server for testing, or this is the basis for a future webapp deployment), the server's filesystem is not directly accessible from the client. Path selection instead uses the **Dataset Browser modal** (Section 3.14), which lets the user upload files to the server and select from previously uploaded datasets. Drag-and-drop opens the same modal in upload mode.

Dataset management endpoints (Section 2.4.10) are available in both environments — they are the only way for a non-pywebview client to get bytes onto the server. In pywebview mode they are unused by the standard flows but still reachable.

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

### 2.2 Architecture: Full-State Sync

The frontend owns the graph state (nodes, edges, positions, parameters). The backend is a **thin adapter** between the frontend and the BioImageFlow library. It is stateless *between requests* for graph editing (no `last_valid_workflow` cache — each request is self-contained), but holds **transient execution state** during workflow runs (the running `Workflow` object, DataFrames, intermediate results). This distinction matters for error recovery: a server restart during execution loses the running workflow, but the graph state (owned by the frontend) is unaffected. The frontend sends the full graph as JSON on every meaningful change; the backend reconstructs the `Workflow` from it, validates it, and returns errors.

**Server state is minimal:**

| State | Description |
|-------|-------------|
| `tool_registry: dict[str, type[BaseTool]]` | Discovered tools indexed by class name (the unique tool identifier) |
| `workflow_id: str | None` | Currently open workflow identifier, relative to the user's workspace workflows tree |
| `execution_task: Task | None` | Handle to the currently running execution (for cancellation) |
| `napari_launcher: NapariLauncher | None` | Manages the Napari process (lazily created) |

There is no `last_valid_workflow` cache — the server rebuilds the Workflow from the graph on every `PUT /graph` and `POST /execution/run`. Each request is self-contained.

**Key design points:**
- **No server-side graph editing logic.** The backend does not have add-node/remove-edge endpoints. It receives the full graph state and either accepts or rejects it.
- **Undo/redo is purely client-side.** The frontend maintains its own undo stack (snapshots of the graph state). No server round-trip needed. See [Section 4.6](#46-undoredo) for details.
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

**Agent source context for Wetlands:** The platform and library dependencies should resolve Wetlands from the published `wetlands` package for reproducible installs and CI. It is possible to inspect Wetlands implementation code: use the source-browsing symlink `external/wetlands-src` when it exists. This symlink is context-only: it points to the local Wetlands source checkout and must not be used as a package source in `pyproject.toml`, `uv.lock`, or runtime import configuration. If the symlink is absent, inspect the installed package source with `python -c "import inspect, wetlands; print(inspect.getfile(wetlands))"`.

**Version management:** Version is a property of the package, not of individual nodes. Multiple versions of the same package can be installed simultaneously in the tool store. The Tools Panel (Section 3.4) shows installed packages with a version list allowing the user to install, uninstall, or select the active version for the current workflow. A workflow uses **one version per package**. Changing the active package version for a workflow marks all nodes using tools from that package as Out-of-date (with a confirmation dialog).

### 2.4 REST API

All endpoints are prefixed with `/api/v1/`. The version prefix allows future breaking changes to be introduced under `/api/v2/` without disrupting existing clients. No backward compatibility guarantees are made between major API versions. The frontend and backend are versioned together — they must use the same API version.

**Health check:** `GET /api/v1/health` returns `{"status": "ok", "version": "<bioimageflow_version>"}`.

#### 2.4.1 Tool Registry

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/tools` | List all discovered tools with metadata |
| `GET` | `/tools/{tool_name}/source` | Get the tool's source directory path |
| `GET` | `/tools/packages` | List all packages (installed and known). Returns installed versions, available versions, tools per version, and environment status. This is the single source of truth for the Tools Panel — no need to cross-reference with `GET /tools`. |
| `POST` | `/tools/packages/{package_name}/install` | Install a package version into the tool store (body: `{version?: str}`) |
| `DELETE` | `/tools/packages/{package_name}` | Uninstall a package version from the tool store (body: `{version?: str}`) |
| `POST` | `/tools/environments/{env_name}/start` | Start a tool's Wetlands environment |
| `POST` | `/tools/environments/{env_name}/stop` | Stop a tool's Wetlands environment |

**Tool metadata response (from `GET /tools`):**

The input/output schemas are the library's canonical wire format, produced by `bioimageflow.validation.serialize_input_schema` and `serialize_output_schema`. The platform does not transform them — see the library spec (§2.4 / §3.4) for the authoritative definition.

Per-field `InputFieldSchema`:

| Key | Type | Notes |
|-----|------|-------|
| `type` | `string` | Display name (e.g. `"float"`, `"int"`, `"str"`, `"bool"`, `"Path"`, `"ImageFile"`, `"ImageShared"`). |
| `required` | `boolean` | `true` when no class-level default is set on `Inputs`. |
| `nullable` | `boolean` | `true` when the type annotation admits `None` (i.e. `Optional[X]` or `X \| None`). Independent of `required`: a field can be required-and-nullable (user must pass *something*, and `None` counts) or non-required-and-non-nullable. GUIs use this to decide whether to expose a "set to null" affordance. |
| `connectable` | `"never" \| "not_by_default" \| "by_default"` | Three-state. `"never"` hides the pin; the other two mean the field can accept an upstream binding. |
| `default` | `any` | JSON-safe default (or `null` when `required: true`). |
| `display_name` | `string \| null` | From `GUIMeta.display_name`. |
| `description` | `string \| null` | From `GUIMeta.description`. |
| `group` | `string \| null` | From `GUIMeta.group`. |
| `min` / `max` / `step` | `number \| null` | From `GUIMeta`. |
| `choices` | `string[] \| null` | Populated for `Literal[...]` and `Enum` fields. |
| `image_spec` | `object \| null` | `{semantics, layouts, dtypes, formats}` each as `string[]`, populated for `ImageFile` / `ImageShared` fields. |

Per-field `OutputFieldSchema`:

| Key | Type | Notes |
|-----|------|-------|
| `type` | `string` | Display name. |
| `default` | `any` | Path-template string for `Path`-typed outputs (e.g. `"{input_image.stem}_mask{ext}"`), or `null`. |
| `template` | `string \| null` | Present when the output default was declared with `Template(...)`; same pattern as `default` for path-template defaults. |
| `image_spec` | `object \| null` | Same shape as on inputs. |

**Passthrough outputs (`DataFrameTool`):** when the tool's `Outputs` class subclasses `bioimageflow.Passthrough`, the `outputs` dict on `ToolMetadata` is the marker `{"_passthrough": true}` instead of a per-field dict — frontends render "inherits columns from upstream."

Per-tool `ToolMetadata` fields (beyond name, package, inputs/outputs):

| Key | Type | Notes |
|-----|------|-------|
| `tool_type` | `"ProcessingTool" \| "DataFrameTool"` | Discriminator for rendering and pin logic. |
| `accepts_upstream` | `boolean` | `false` means the tool refuses positional upstream DataFrame connections. The canvas hides positional input pins. |
| `dynamic_outputs` | `boolean` | `true` means the tool's output column set depends on inputs/upstream; the canvas refetches the resolved schema on input edits via `POST /graph/nodes/{node_id}/output_schema`. |
| `dataframe_output` | `boolean` | `true` means the node exposes its full output DataFrame via the `__dataframe_out` header pin. This is `true` for both `ProcessingTool` and `DataFrameTool` nodes in the current library. |

**The `"any"` type.** The library reserves `"any"` (per library `specs.md` §2.4) for columns whose runtime type is not known until execution. `Generate(column_name="x", values=[...])` produces `{x: {type: "any", ...}}` regardless of the values' Python type, because static introspection cannot infer it. GUIs must treat `"any"` as compatible with **any** consumer input type at edge creation. See §3.3.3 for the pin rendering and edge-validity rules.

```json
{
  "name": "CellposeSegmenter",
  "display_name": "Cellpose Segmenter",
  "package": "bioimageflow-cellpose",
  "package_version": "1.2.0",
  "tool_type": "ProcessingTool",
  "accepts_upstream": true,
  "dynamic_outputs": false,
  "dataframe_output": true,
  "documentation": "Segment cells using Cellpose models.",
  "tags": ["segmentation", "deep-learning"],
  "categories": ["segmentation"],
  "inputs": {
    "input_image": {
      "type": "ImageFile",
      "required": true,
      "nullable": false,
      "connectable": "by_default",
      "default": null,
      "display_name": "Input image",
      "description": "Input intensity image",
      "group": null,
      "min": null, "max": null, "step": null,
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
      "min": 1.0, "max": 500.0, "step": 0.5,
      "choices": null,
      "image_spec": null
    },
    "model_type": {
      "type": "str",
      "required": false,
      "nullable": false,
      "connectable": "not_by_default",
      "default": "cyto2",
      "display_name": "Model",
      "description": "Cellpose model to use",
      "group": null,
      "min": null, "max": null, "step": null,
      "choices": ["cyto", "cyto2", "nuclei"],
      "image_spec": null
    }
  },
  "outputs": {
    "mask": {"type": "ImageFile", "default": "{input_image.stem}_mask{ext}", "template": "{input_image.stem}_mask{ext}", "image_spec": {"semantics": ["label"], "layouts": ["YX"], "dtypes": [], "formats": []}},
    "cell_count": {"type": "int", "default": null, "image_spec": null}
  },
  "environment": {"python": "3.11", "conda": ["cellpose"], "pip": []}
}
```

**Endpoint roles:** `GET /tools` returns tool-level metadata (inputs schema, outputs, environment) for graph construction and the Node Panel. `GET /tools/packages` returns package-level metadata (installed/available versions, environment status) for the Tools Panel tool list and Manage Tools dialog. The data intentionally overlaps (both include package name and version) for convenience — the frontend uses `GET /tools/packages` to populate the Tools Panel, and `GET /tools` to resolve tool schemas when building nodes.

**Example tool definition with GUIMeta:**
```python
from pathlib import Path
from typing import Annotated, Any, Literal

from bioimageflow_core import (
    Arguments,
    Connectable,
    GUIMeta,
    IOModel,
    ImageSpec,
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
            Path,
            ImageSpec(
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
            Path,
            ImageSpec(semantics={Semantic.LABEL}, layouts={Layout.PLANAR}),
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

#### 2.4.2 Workflow Management

Every user has exactly one active BioImageFlow workspace. In desktop mode this
is a user-editable filesystem path stored in Settings. The default development
workspace is `<repo>/workspace/`; packaged desktop builds may choose an
OS-appropriate default such as `~/BioImageFlow/workspace/`. The workspace has
fixed child roots:

```text
workspace/
  workflows/     # saved workflow tree
  tools/         # workspace-owned custom tools
  data/          # user-managed local data
  outputs/       # workflow execution output and cache roots
```

Saved workflows are organized under `workspace/workflows/` as folders. Each
workflow is a directory that contains `workflow.json` and optional workflow-local
files such as `tools/`. Workflow identifiers are slash-separated paths relative
to `workspace/workflows/`, for example `segmentation/nuclei`. `name` remains in
the wire model as a compatibility alias for the leaf slug, but new APIs and
frontend state use `id`. Each folder or workflow path segment may contain
letters, numbers, spaces, underscores, and hyphens. Empty segments, path
traversal, and leading/trailing whitespace are rejected.

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/workspace` | Return current workspace path, workflows root, tools root, outputs root, deployment mode, and whether the workspace path is admin-managed/read-only. |
| `PATCH` | `/workspace` | Desktop-only workspace path change. Body: `{workspace_path: str}`. The backend creates missing child roots after validation. |
| `GET` | `/workflows/tree` | Return the folder/workflow tree rooted at `workspace/workflows/`. |
| `POST` | `/workflows/folders` | Create a folder under `workspace/workflows/` (body: `{path: str}`). |
| `PATCH` | `/workflows/folders/{path}` | Rename or move a workflow folder (body: `{new_path: str}`). |
| `DELETE` | `/workflows/folders/{path}` | Delete a folder. Body: `{policy: "empty" \| "delete_children" \| "move_children_up"}`. `empty` rejects non-empty folders with **409 Conflict**. |
| `GET` | `/workflows` | Compatibility flat list of saved workflows. New callers should use `/workflows/tree`. |
| `POST` | `/workflows` | Create a new workflow (body: `{id: str, display_name?: str, description?: str}`). Returns **409 Conflict** if a workflow with the same id already exists, with a suggested alternative id. |
| `GET` | `/workflows/{id}` | Load a workflow (returns full graph JSON including GUI state). |
| `PUT` | `/workflows/{id}` | Save workflow (body: full graph JSON). Always succeeds (saves even if graph has validation errors). |
| `DELETE` | `/workflows/{id}` | Delete a workflow file and its workspace-scoped output/cache directory. |
| `PATCH` | `/workflows/{id}` | Update workflow metadata, duplicate, rename, or move (body: `{action: "update" \| "duplicate" \| "move", display_name?: str, description?: str, new_id?: str}`). |

**Workflow loading — missing package resolution:** When loading a workflow that requires tool packages or versions not in the tool store (based on the `tool_package` and `tool_package_version` fields in the serialized nodes), the server returns a `missing_packages` field in the response. The frontend shows a dialog: "This workflow requires packages not installed: [list with versions]. Install them?" with an "Install All" button.

**Workflow storage path normalization:** The backend resolves each workflow's
runtime storage root to `workspace/outputs/<workflow_id>/` before handing a
graph to the BioImageFlow library. Workflow id separators are sanitized where
needed for filesystem safety. Relative paths must not reach tool execution as
CWD-sensitive paths. This is required because ProcessingTool wrappers may run
subprocesses with `cwd=context.work_dir` while passing framework-provided
input/output paths directly to the subprocess. Explicit per-workflow
`storage_path` metadata is preserved for export compatibility, but it is not the
primary organization control in the platform UI.

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
| `PUT` | `/graph` | Submit full graph state for validation. Returns validation result. |
| `PATCH` | `/graph/nodes/{id}/parameters` | Submit parameter-only change for a single node (body: `{parameters: {...}}`). Validates the patched node's parameters and recomputes **cache status** for the patched node and its transitive downstream (since their upstream signature hash changed). Does **not** re-check type compatibility downstream (parameter changes don't alter output schemas). Lighter than full `PUT /graph`. |

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

For **parameter-only changes** (no structural change to edges/nodes), the frontend may use the lighter `PATCH /graph/nodes/{id}/parameters` endpoint, which validates only the affected node and its downstream. This avoids full graph reconstruction for the most common edit operation.

#### 2.4.4 Node Data (Outputs)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/nodes/{node_id}/data` | Get the output DataFrame as JSON (paginated: `?page=0&page_size=50`) |
| `GET` | `/nodes/{node_id}/data/csv` | Download output DataFrame as CSV |
| `GET` | `/nodes/{node_id}/thumbnail` | Get image thumbnail (`?row=0&col=mask&size=128`) |
| `GET` | `/nodes/{node_id}/status` | Get execution status + cache info |

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
  "column_types": {"mask": "ImageFile", "cell_count": "int"}
}
```

#### 2.4.4b Node Output Schema Resolution

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/graph/nodes/{node_id}/output_schema` | Resolve the output column schema for a single node |

**Request body:** a full `GraphState` (same format as `PUT /graph`). The full graph is required because schema resolution may depend on upstream wiring (e.g. merge tools propagate columns from their upstreams).

**Response:** the library's `serialize_resolved_outputs(node)` wire shape verbatim. No `node_id` in the response body --- the URL carries it.

```json
{
  "resolved": true,
  "columns": {
    "sensitivity": {"type": "any", "default": null, "image_spec": null}
  }
}
```

Or when unresolvable (e.g. required kwargs like `JoinOnColumn.join_column` not yet set):

```json
{"resolved": false, "columns": {}}
```

**Error handling:**
- **404:** only when the `node_id` is not present in the request body's `nodes` list.
- **200 with `resolved: false`:** for all build/resolution failures (cycles, missing required kwargs, unknown tool). Input edits frequently produce transiently invalid graph states; the endpoint must respond cleanly so the GUI can keep polling.
- The `columns` dict may contain a passthrough marker (`{"_passthrough": true, ...extra}`) when the tool declares `class Outputs(Passthrough)` without enough information to expand. The frontend renders `extra` keys as concrete pins plus a single "(+ inherited columns)" placeholder.

#### 2.4.5 Execution

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/execution/run` | Submit graph + run (body: `{graph: {...}, nodes?: [str]}`) |
| `POST` | `/execution/stop` | Stop the current execution |
| `POST` | `/execution/clear` | Clear outputs for specified nodes (body: `{nodes: [str]}`). Returns updated `NodeStatus` for the cleared nodes and all their downstream dependents (cleared nodes become "unexecuted"; downstream nodes become "out-of-date"). |
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
class Settings(BaseModel):
    external_editor: str | None = None              # e.g., "code {workspace_path} --goto {file_path}"
    napari_env_path: str | None = None              # Custom Napari Conda env path
    workspace_path: str                             # Desktop user's BioImageFlow workspace path
    tool_store_path: str = "~/.bioimageflow/tool_packages/"
    execution_engine: Literal["sequential", "parsl"] = "sequential"
    cache_max_executions: int | None = None         # Max cached executions per node (None = unlimited)
    cache_max_age: str | None = None                # Max cache age (e.g., "30d", None = unlimited)
    dev_mode: bool = True                           # Always true in GUI mode (cache invalidation on code change)
    enable_unsafe_webapp_features: bool = False     # Debug-only; enables local source-editing actions in webapp mode
```

`enable_unsafe_webapp_features` is a file-only debug switch for local testing of webapp mode. It is ignored in desktop mode. In webapp mode, the default `false` value keeps local source-editing features disabled; setting it to `true` re-enables actions that can modify or open server-side code, such as creating, renaming, deleting, and opening custom tool scripts. The Settings API must expose the value in `GET /settings` but reject attempts to change it through `PATCH /settings`.

#### 2.4.7 File System Helpers

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/fs/reveal` | Open a path in the system file browser |

In pywebview mode, path selection uses native file dialogs — no server-side browse endpoint is needed. In plain-browser mode, path selection is handled by the Dataset Browser modal backed by the endpoints in Section 2.4.10.

#### 2.4.8 Image Viewer Integration

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/napari/open` | Open image(s) in Napari (body: `{paths: [str], clear_layers: bool}`) |
| `GET` | `/napari/status` | Check if Napari is running |

The backend manages Napari via `NapariLauncher` (using Wetlands). Napari runs in an isolated Conda environment (`napari` + `pyqt`) with its own Qt event loop. Communication uses `multiprocessing.connection` (Client/Listener pattern on localhost). The backend launches Napari lazily on the first `/napari/open` call and reconnects automatically if the process dies.

#### 2.4.9 Code Editor

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/editor/open` | Open a file/folder in the user's external editor |
| `POST` | `/editor/open-tool` | Open the user's workspace as the editor project and focus a tool source file |

The user specifies an external editor command in Settings (Section 3.13.1). The
command may use `{workspace_path}` for the project folder and `{file_path}` for
the focused file. For VS Code the recommended command is
`code {workspace_path} --goto {file_path}`. If no external editor is configured,
"Open in editor" copies the relevant path to clipboard with a toast.

`/editor/open-tool` is used by tool rows and node source links. The backend
always opens the current user's workspace folder as the editor project, then
focuses the selected tool file. This applies to workspace-owned custom tools and
installed package tools; package source is focused as a file, not opened as the
editor project.

#### 2.4.10 Dataset Management

Dataset management provides server-side file storage for clients that cannot access the server's filesystem directly (primarily plain-browser mode, but also useful for testing and for workflows that share inputs across machines). Datasets are uploaded via HTTP, stored under a dedicated server directory, and referenced by absolute path in node parameters.

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/datasets` | List available datasets |
| `POST` | `/datasets/upload` | Upload one or more datasets (multipart form data) |
| `DELETE` | `/datasets/{dataset_id}` | Delete a dataset |

**Dataset storage layout (v1, single-user):**

```
{datasets_root}/{timestamp}_{sanitized_filename}.{ext}
```

- `{datasets_root}` defaults to `workspace/data/datasets/` in desktop mode and
  is derived from the user's workspace. It is not configured per workflow.
- `{timestamp}` is the upload time in ISO 8601 compact format (e.g., `20260421T143022`).
- `{sanitized_filename}` is the original filename after sanitization (see below).

The `dataset_id` is a stable string derived from the stored filename (e.g., `d_20260421T143022_cells_tif`) and is URL-safe.

**`GET /datasets` response:**

```json
[
  {
    "id": "d_20260421T143022_cells_tif",
    "filename": "cells.tif",
    "original_filename": "cells.tif",
    "size": 52428800,
    "upload_date": "2026-04-21T14:30:22Z",
    "path": "/abs/path/to/datasets/20260421T143022_cells.tif",
    "content_type": "image/tiff"
  }
]
```

The `path` field is the absolute server-side path. This is the value that gets written into `NodeState.parameters` for Path-typed inputs when a dataset is selected.

**`POST /datasets/upload` request:** Multipart form data with one or more `files` parts. Multi-file upload is supported in a single request.

**`POST /datasets/upload` response:**

```json
{
  "uploaded": [
    {
      "id": "d_20260421T143022_cells_tif",
      "filename": "cells.tif",
      "path": "/abs/path/to/datasets/20260421T143022_cells.tif",
      "size": 52428800
    }
  ],
  "errors": [
    {"filename": "too_big.tif", "error": "file_too_large", "detail": "Exceeds 2GB limit"}
  ]
}
```

Per-file errors are returned in the `errors` array so that a partially successful multi-file upload still reports the successes.

**`DELETE /datasets/{dataset_id}` response:** HTTP 204 No Content on success. HTTP 404 Not Found if the dataset does not exist. Deleting a dataset does not invalidate any node that previously consumed it — the node simply fails on next execution with a "file not found" error.

**Upload validation:**

- **Filename sanitization.** Path separators (`/`, `\`) are stripped. Only alphanumerics, hyphens, underscores, and dots are kept; any other character is replaced with `_`. The extension is preserved. Names longer than 255 characters are truncated while preserving the extension. The original filename is retained in the `original_filename` metadata field.
- **File size limit.** Configurable per deployment, default **2 GB** per file. The authoritative per-file cap is enforced **mid-stream**: as each file in the multipart body is streamed to disk, a running byte counter aborts the upload (HTTP 413 for single-file requests, or a `file_too_large` entry in `errors[]` for multi-file requests) as soon as the cap is exceeded, and the partially-written file is `unlink`ed. `Content-Length` is additionally used as a coarse DoS guard: a request whose declared body size clearly exceeds `max_upload_size * MAX_FILES_PER_REQUEST` (e.g., 2 GB × 32 = 64 GB) is rejected up-front with HTTP 413, before any body is read. It is **not** used as a per-file cap, because a multi-file body legitimately contains multiple files plus multipart boundaries and form fields — a valid N-file upload can have a total size exceeding the per-file cap.
- **Path traversal prevention.** The server resolves the final storage path with `Path.resolve()` and verifies it starts with the configured `{datasets_root}`. Any escape attempt is rejected with HTTP 400 `{"error": "path_traversal", "detail": "Invalid filename"}`. This is defensive programming — sanitization already prevents path separators, but resolve-then-check is the authoritative gate.
- **Content type.** No enforcement in v1. The `content_type` field is informational, derived from the extension.

**Single-user note.** v1 is single-user (see Section 1), so datasets are shared across all sessions on the machine. Multi-user scoping (per-user directories, auth-based access control) is added in v3.

### 2.5 WebSocket API

A single WebSocket connection at `/ws` provides real-time updates. Messages are JSON with a `type` field. No authentication is required (server binds to localhost only).

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
4. Open pywebview window pointing to the server URL

**Shutdown sequence:**
1. If execution is running, send stop signal and wait (with timeout)
2. Terminate Napari process if running (via `NapariLauncher`)
3. Clean up shared memory segments (`bioimageflow clean-shm`)
4. Save any pending settings changes
5. Stop FastAPI server

Unsaved workflow changes are not auto-saved to disk on shutdown. The frontend auto-saves to `IndexedDB` (see Section 4.3), so the user can recover their work on next startup.

---

## 3. Frontend

### 3.1 Technology Stack

- **Framework:** Vue SPA
- **DAG Editor:** Vue Flow
- **Layout:** Dockview (dockable, resizable panels)
- **UI Components:** PrimeVue
- **Styling:** The entire styles of the app should be managed by a PrimeVue theme, and almost no custom CSS should be added concerning styles. Use PrimeVue CSS variables (e.g., `--p-surface-*`, `--p-text-color`, `--p-primary-color`) for any custom styling that is absolutely necessary.
- **State management:** Vue Flow owns graph state (nodes, edges). Pinia for non-graph state (settings, tool registry, execution status). Graph state is not duplicated in Pinia.

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

A node represents an instance of a tool in the workflow. The node template is divided into three regions:

- **Header:** Tool name, category badge, and **DataFrame-level pins** (header pins). DataFrameTool nodes render square header pins for positional DataFrame inputs (left, when `accepts_upstream === true`) and a single DataFrame output (right). ProcessingTool nodes render the DataFrame output pin only.
- **Body:** Per-column output pins and per-field input pins (body pins). Round, type-colored, matching the existing column/field semantics.
- **Footer:** Status indicator (color-coded dot), GPU badge, provisional indicator.

Per-tool-type header pin rules:

| Tool type | Header input pins | Header output pin |
|---|---|---|
| Source DataFrameTool (`accepts_upstream: false`, e.g. `Files`, `Generate`) | None | `__dataframe_out` |
| Merge / transform DataFrameTool (`accepts_upstream: true`, e.g. `CrossJoin`, `FilterRows`) | Positional (`__positional_0`, `__positional_1`, ..., auto-grow) | `__dataframe_out` |
| ProcessingTool | None | `__dataframe_out` |

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
- **Copy/Paste:** Ctrl+C / Ctrl+V. Copies selected nodes and edges between them. Pasted nodes get new unique IDs and names (same name generation logic as node creation). Internal edges between pasted nodes are preserved with their `source_node` and `target_node` fields remapped to the new node IDs. Edges connecting to nodes outside the selection are dropped. Parameters and internal edges are preserved.
- **Collapse/Expand:** Double-click header or toggle in Node Panel. Collapsed nodes show only the header bar with pins.
- **Enable/Disable:** Right-click context menu or toggle in Node Panel header.

#### 3.3.2 Edges

Edges represent data flow between nodes. There are two kinds of edges (see [Section 2.4.3](#243-graph-schema-and-validation)), each visually distinct:

- **Positional edges** (`PositionalEdge`): Connect a node's header DataFrame output pin (`__dataframe_out`) to a DataFrameTool's header positional input pin (`__positional_*`). Represent whole-DataFrame flow (upstream arguments to `merge_dataframes`). Rendered as **solid, neutral gray (#7A7A80), thicker (2.5px)** bezier curves anchored on header-region pins.
- **Column reference edges** (`ColumnRefEdge`): Connect a body output pin (column name) to a body input pin (field name). Represent `ColumnRef` bindings for `ProcessingTool` inputs. Rendered as **solid, type-colored, thinner (2px)** bezier curves anchored on body-region pins.

**Cross-region rejection:** Header pins can only connect to header pins; body pins can only connect to body pins. Dragging a header output to a body input (or vice versa) is rejected client-side.

**Edge creation:**
- Drag from an output pin to an input pin (or vice versa).
- The frontend performs lightweight client-side validation (cycle detection, basic type check, cross-region rejection) for instant feedback.
- Invalid connections show a visual rejection (red flash + tooltip with reason).
- After creation, the full graph is sent to `PUT /graph` for authoritative server validation.

**Edge deletion:**
- Select an edge and press Delete.
- Or drag a connected input pin away to the empty canvas (disconnect).

**Edge visuals:**
- Edges are drawn as curved lines (bezier curves).
- Positional edges: solid, neutral gray (#7A7A80), 2.5px stroke width.
- Column reference edges: solid, type-colored (e.g., ImageFile = blue, scalar = gray), 2px stroke width.
- Selected edges are highlighted.

#### 3.3.3 Pins

Pins are the connection points on nodes. They are divided into two visual categories corresponding to the two edge types:

**Header pins (DataFrame-level)**

Header pins appear in the node header region and carry whole-DataFrame connections (positional edges).

- **Visual style:** Square (~14px), neutral gray fill (#7A7A80), distinct from the `"any"` wildcard color (#B0A060) and from body type-colored pins.
- **DataFrame output pin** (`__dataframe_out`, right side): Present on nodes whose tool metadata has `dataframe_output === true` (currently all `ProcessingTool` and `DataFrameTool` nodes). Represents the node's full output DataFrame.
- **Positional input pins** (`__positional_0`, `__positional_1`, ..., left side): Present on DataFrameTool nodes with `accepts_upstream === true`. Numbered "1", "2", etc. A new pin appears dynamically when the last available pin is connected. **Auto-compact behavior:** when a positional edge is disconnected, higher-numbered pins shift down to fill the gap.
- Source-only DataFrameTools (`accepts_upstream === false`, e.g. `Files`, `Generate`) render no positional input pins. Edge-creation onto a positional handle of such a tool is rejected client-side. The backend additionally rejects any graph containing such an edge with a `source_tool_upstream` validation error.
- ProcessingTool nodes have no header input pins, but do have the `__dataframe_out` header output pin so their full result DataFrame can feed a downstream `DataFrameTool` such as an aggregator.

**Body pins (column-level / field-level)**

Body pins appear in the node body region and carry per-column or per-field connections (column reference edges).

- **Visual style:** Round (~10px), type-colored (matching the data type color palette).
- **Output pins** (right side): One per output field or resolved column. Label shows the field/column name. Tooltip shows the type.
- **Input pins** (left side): Only for inputs where `connectable` is `"by_default"` or `"not_by_default"` (i.e. not `"never"`; declared by the tool author via `GUIMeta`). Fields without `GUIMeta` default to `"not_by_default"`. When a connectable input is connected, the corresponding parameter field in the Node Panel shows the source (e.g., `"cellpose_segmenter_1.mask"`) and the input widget is hidden.

For tools with `dynamic_outputs === true`, the body output pin set is computed by `POST /graph/nodes/{node_id}/output_schema` and refetched whenever a parameter on the node changes, or whenever a parameter on any upstream node with `dynamic_outputs === true` changes (the change is propagated downstream along positional edges). While the schema is unresolvable (`resolved: false`), the canvas renders a single placeholder pin styled with a dashed outline and disabled drag-out. Columns with `type: "any"` use a neutral wildcard pin color (#B0A060) and bypass type-compatibility checks at edge creation.

#### 3.3.4 Canvas Controls

- **Pan:** Middle-click drag, or scroll wheel + Shift
- **Zoom:** Scroll wheel, or pinch gesture
- **Fit view:** Button or shortcut to fit all nodes in view
- **Initial empty canvas:** Adding the first node to a new empty workflow must not change the current viewport or zoom.
- **Undo/Redo:** Ctrl+Z / Ctrl+Shift+Z (client-side, instant). See [Section 4.6](#46-undoredo).

### 3.4 Tools Panel (Left Sidebar)

Displays the available tools in a two-tier layout: a minimalist tool list for everyday use, and a full management dialog for package/version administration.

**Panel layout (top to bottom):**

1. **Search bar** (with margins): Fuzzy search filtering by name, tags, categories, and keywords. This is not simple substring matching — it uses fuzzy matching so that partial or approximate terms still surface relevant results.

2. **Tool list:** A flat, scrollable list of tools. Each row contains:

   | Element | Description |
   |---------|-------------|
   | **Tool display_name** | Primary label. The row is **draggable** onto the canvas and **clickable** to create a node at a default position. |
   | **Info icon-button** | Opens detailed documentation for the tool (modal). |
   | **Env status dot** | Colored indicator for the tool's environment state: stopped (gray), creating (yellow), running (green). |
   | **Category label** | Shown below the tool name. |
   | **Tags labels** | Shown below the tool name, next to category. |

   **Important:** Environments are per-tool, not per-package. Each tool row shows its own environment indicator and start/stop toggle, even if multiple tools share the same underlying environment.

3. **"Manage tools" button** in the panel header: Opens a PrimeVue **Dialog** (modal) containing the full tool management interface (see below).

4. **"Create tool" button** at the bottom of the panel (with margins): Opens the tool creation workflow.

**Manage Tools Dialog:**

The dialog presents a hierarchical **TreeTable** with package rows (parents) and tool rows (children).

**Package rows (parent):**

| Element | Description |
|---------|-------------|
| **Package name** | The package identifier |
| **Categories** | Package-level categories |
| **Tags** | Package-level tags |
| **Version dropdown** | Lists all known versions (installed and available). Each version entry has an **Install/Uninstall toggle** — install button for uninstalled versions, uninstall button for installed ones. Shows spinning icon during installation. Installation can be interrupted (stop button). |
| **"Use in workflow" button** | Sets the selected version as the active version for the current workflow. Only available for installed versions. When clicked, if the workflow already uses a different version of this package, a confirmation dialog is shown: "Changing {package} from {old_version} to {new_version} will mark {N} nodes as out-of-date. Their cached results will need re-execution. Continue?" |

Multiple versions of the same package can be installed simultaneously. Each workflow uses **one version per package**, selected via the "Use in workflow" button.

**Tool rows (children):**

| Element | Description |
|---------|-------------|
| **Tool name** | The tool's display name |
| **Info button** | Show detailed documentation (modal) |
| **Env status indicator** | Colored dot: stopped (gray) / creating (yellow) / running (green) |
| **Start/Stop toggle** | Start or stop the tool's Wetlands environment |

**Important:** Environments are per-tool, not per-package. Each tool row in the TreeTable shows its own env indicator and start/stop toggle, even if multiple tools share the same underlying environment.

### 3.5 Node Panel (Right Sidebar)

Title: Nodes.

Displays details and parameters for the currently selected node(s).

**Multi-selection:** When multiple nodes are selected, the Node Panel shows only bulk actions: Enable/Disable all, Delete all, Clear all. No parameter editing. The Data Table shows the outputs of all selected nodes.

**Dynamic outputs refresh:** When an input field changes on a node whose tool has `dynamic_outputs === true`, a debounced (200ms) call to `POST /graph/nodes/{node_id}/output_schema` refreshes the node's resolved output pins. The refresh also propagates downstream along positional edges to any visited node with `dynamic_outputs === true`.

**Single-node layout (top to bottom):**

#### 3.5.1 Header Section

- **Node name** (editable inline field). This is the human-readable display name (`NodeState.name`) — allows spaces and special characters. Must be unique within the workflow. The `NodeState.id` (URL-safe, used in API and edges) is auto-generated from the name on creation and remains stable when the name is renamed. Validated on blur — if duplicate, a red inline error is shown and the previous name is preserved until a valid name is entered.
- **Tool name** (read-only, links to source)
- **Package + version** (read-only, e.g., "bioimageflow-cellpose 1.2.0")
- **Enable/Disable** toggle button

(Tool documentation lives at the bottom of the Node Panel — see §3.5.6.)

#### 3.5.2 Action Bar

- **Run** button: Execute this node (and its unexecuted dependencies)
- **Clear** button: Set to Unexecuted, remove output data
- **Stop** button: Visible only while the node is executing
- **Restore parameters** button: Reset all parameters to their values at last execution. **Disabled** with tooltip "No previous execution" when the node has never been executed. If the tool schema changed since the last execution (fields added, removed, or type changed), restored values are applied only for fields that still exist and are type-compatible; incompatible or removed fields are left at their current values, and a toast warns: "Some parameters could not be restored due to schema changes."
- **Open output folder** button: Reveal in system file browser

#### 3.5.3 Input Parameters

Each input field from the tool's `Inputs` is rendered as a parameter row. Fields are grouped by category (if the tool defines categories via `GUIMeta.group`; otherwise all in one group).

**Each parameter row contains:**

| Element | Description |
|---------|-------------|
| **Pin toggle button** | Icon-only button placed **before** the label, only rendered when `connectable != "never"`. Two states with explicit tooltips: a two-arrows icon ("Add input pin") when the pin is hidden, a cross icon ("Remove input pin") when the pin is visible. Clicking toggles whether the canvas node shows an input pin for this field. `GUIMeta.connectable` (three-state: `"never" \| "not_by_default" \| "by_default"`) decides whether the button appears; the button itself decides whether the pin is shown. Current behaviour is to treat both `"not_by_default"` and `"by_default"` identically (pin visible) — a richer UX that hides pins by default for `"not_by_default"` fields is a separate plan. |
| **Label** | Field name (human-readable) |
| **Default button** | Resets the field to its default value |
| **None toggle** | Two-state button (only shown when `nullable` is `true` on the field schema). When active, the value is `None` and the input field is hidden. Independent of `required`: a required-and-nullable field still gets the toggle so the user can explicitly choose `None` as a valid value. |
| **Input field** | The actual value editor (hidden when connected or None). Type depends on the field annotation (see below). |
| **Help text** | Collapsible description from field metadata |

**Input field types:**

| Field Type | Widget | GUIMeta influence |
|------------|--------|-------------------|
| `str` | Text input | -- |
| `int` | Number input (spinner) | `min`, `max`, `step` from GUIMeta |
| `float` | Number input or slider | `min`, `max`, `step` from GUIMeta. If all three are set, render as slider. |
| `bool` | Checkbox | -- |
| `Enum` or `Literal[...]` | Dropdown | -- |
| `Path` (file) | Text input + "Select File" button | In pywebview: native file dialog. In browser: Dataset Browser modal (Section 3.14). |
| `Path` (directory) | Text input + "Select Folder" button | In pywebview: native folder dialog. In browser: folder selection is not offered — the button is hidden and only manual text entry or drag-and-drop is available. |
| `ImageFile` | Text input + "Select File" button (filtered by format spec) | Same dual behavior as `Path` (file). File-type filter applies to both the native dialog and the Dataset Browser search filter. |
| `ImageShared` | *Connection-only* (no manual input widget). Shows "Connect to upstream node" placeholder when unconnected. Unconnected required `ImageShared` fields produce a `missing_connection` validation error on the node. | Always `connectable != "never"`, not user-editable. |
| `tuple`, `list` | Inline list editor | -- |

When a connectable input is **connected** (pin has an edge), the input field is replaced by a read-only label showing the source: `"segmenter_1.mask"`.

#### 3.5.4 Output Fields

Each output field from `Outputs` is displayed with editable path templates for path-typed outputs **on `ProcessingTool` nodes only**:

- **Label:** Field name
- **Type badge:** Visual indicator of the type (ImageFile, int, etc.)
- **Path template editor:** *Only for `ProcessingTool` nodes.* For path-typed outputs (`Path`, `ImageFile`), a text input showing the current output path template (e.g., `{input_image.stem}_mask_{row_index}.png`). The user can edit this to customize output file naming. The template syntax follows the library's output templating engine (see `specs.md` Section 7.1). Available template variables are shown in a dropdown/autocomplete. Custom templates are stored in `NodeState.output_templates` (a dedicated dict, separate from `parameters`, to avoid mixing user-facing parameters with internal metadata). If a field has no entry in `output_templates`, the tool's default template is used.
- **Non-path outputs** (int, float, str, etc.) are shown read-only.
- **`DataFrameTool` outputs are column declarations, not file paths.** When `Outputs` is declared on a `DataFrameTool` (either explicit `IOModel` columns or a `Passthrough` marker), each field describes a column produced by the source/transform DataFrame, not a file written to disk. No path-template editor is shown — even for fields typed as `Path`/`ImageFile` — and `NodeState.output_templates` is not initialized for these nodes. Output templating is a `ProcessingTool`-only concept (see `specs.md` Section 2080: *"DataFrameTool does not use output templating — it returns DataFrames directly."*). The tool's `tool_type` field on `ToolMetadata` is the gate.

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

#### 3.5.6 Documentation

A collapsible section at the bottom of the Node Panel that shows the tool's documentation (from `tool.documentation`). **Open by default** so users see the docs without extra interaction. The toggle is a chevron icon rendered **before** the "Documentation" label (right-pointing when collapsed, down-pointing when expanded).

### 3.6 Data Table (Bottom Panel, Tab 1)

Displays the output DataFrames of selected nodes in a tabular view.

**Behavior:**
- When one or more nodes are selected, the table shows their outputs.
- When no nodes are selected, the table shows the terminal node(s) outputs.
- If selected nodes have no output yet, a placeholder message is shown.
- **Disabled nodes:** If a disabled node was previously executed, the Data Table shows its cached data with a dimmed appearance and a banner: "This node is disabled." If a disabled node has no cached data, the standard placeholder is shown. When no nodes are selected and all terminal nodes are disabled, the placeholder reads: "All terminal nodes are disabled."

**Layout — vertical flex column:**

When multiple nodes are selected, their DataFrames are displayed in a **vertical flex column layout** (stacked vertically, not in separate tabs). Each DataFrame has a header showing the node name and its own independent pagination controls (page selector, page size). The user can scroll through all DataFrames in a single view for quick comparison.

**Display limit:** When more than 5 nodes are selected, only the first 5 DataFrames are shown, with a "Show all ({N})" toggle to display the rest.

**Single node selected:** Show that node's output DataFrame only.

**Table features:**
- **Column types:** Columns are annotated with their type. Image columns show special rendering.
- **Pagination:** Large DataFrames are paginated (server-side, via `/nodes/{node_id}/data?page=0&page_size=50`).
- **Sorting:** Click column header to sort.
- **Image cells:** For columns typed as `ImageFile` or `ImageShared`:
  - Show a thumbnail (loaded lazily from `/nodes/{node_id}/thumbnail?row=0&col=mask`)
  - **Open in Napari** button: Opens in Napari (`POST /napari/open`). Ctrl+Click clears existing layers.
  - **Reveal in file browser** button.
- **Scalar cells:** Show the value directly.
- **Path cells (non-image):** Show the filename with two buttons:
  - **Open** button: Opens in the external editor.
  - **Reveal in file browser** button.

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

### 3.8 Workflows Panel

The application has a persistent **Workflows** panel, analogous to the Tools
panel. The workflow menu may expose the same commands, but the panel is the
primary browsing and management surface.

**Workflow storage layout:**

Each user has one workspace, and saved workflows live under the workspace's
workflow tree:

```text
workspace/
  workflows/
    my_workflow/
      workflow.json
    segmentation/
      nuclei/
        workflow.json
        tools/
  tools/
```

Each `workflow.json` stores the platform document for the workflow, including
the library workflow payload, GUI state, and metadata. `workspace/tools/` stores
workspace-owned custom tools shared by workflows in that workspace. A workflow
directory can contain workflow-local files, but these directories are not shown
as user folders in the Workflows panel.

Only directories containing `workflow.json` are platform workflows. Stray JSON
files under `workspace/workflows/` are ordinary files and are not listed,
opened, or treated as workflow id collisions.

**Panel layout:**

- **Toolbar:** New workflow, New folder, Save, Duplicate, Import, Export,
  Rename selected item, Delete selected item.
- **Search:** Filters by workflow display name, id, and folder name while
  preserving matching ancestors.
- **Workflow tree:** Nested folders and workflows under `workspace/workflows/`.
  Workflow rows show display name and last modified time. Folder and workflow
  rows are sorted together alphabetically within each folder, not grouped by
  type. Folder and workflow rows are selectable drag/drop targets; selected item
  rename/delete actions live in the toolbar. The tree is a classic PrimeVue Tree
  component with folder expansion, selection, built-in drag/drop indicators, and
  node templates. Drop indicators overlay rows and must not shift other rows
  while dragging.
- **Selected workflow details:** Shows the selected workflow's description,
  workflow id, and output storage path. The description appears here, not in
  every list row, and has an edit button that opens a platform dialog. The
  detail section also has an action that opens the workflow folder in the
  system file browser. It does not show a separate workflow-file row because
  that duplicates the storage/path information.

Clicking a row selects it. Double-clicking a workflow, pressing Enter on a
selected workflow, or using the Open action opens it, subject to the unsaved
changes prompt. Dragging from anywhere on a workflow row onto a folder moves the
workflow within the tree, and dragging that same row onto the canvas creates a
SubWorkflowNode. Drops that would make a workflow contain itself directly or
indirectly are rejected. Dragging a folder onto another folder moves the full
folder subtree, including child folders and workflows.

**Actions:**
- **New workflow:** Opens a creation dialog with fields: display name
  (free-form), folder, id/slug (auto-generated from display name, editable, with
  slash-separated safe path segments), and description (optional, multiline). On
  id conflict, the server suggests an alternative. When a folder is selected in
  the tree, the dialog creates the workflow inside that folder by default.
- **New folder:** Creates a folder under the selected folder or the tree root.
- **Open workflow:** Opens the selected saved workflow. Opening a new workflow closes the current one (with save prompt).
- **Edit workflow:** Each workflow has an **Edit** action to modify display
  name, description, folder, or slug. Moving or renaming changes the workflow
  `id`; the frontend updates any current-workflow references atomically.
- **Save:** Saves current workflow state including GUI state (Ctrl+S). The full graph JSON (with positions, collapsed state, etc.) is sent to `PUT /workflows/{id}`. Saving always succeeds regardless of validation errors. Uses atomic writes (write to a temporary file, then rename) to prevent corruption on crashes or disk-full errors.
- **Save as / Duplicate:** Save under a new id.
- **Import / Export:** Uses the BioImageFlow library import/export API. The
  platform does not reimplement the library archive format.
- **Delete:** Delete with confirmation. Deletes the workflow file, its
  workspace-scoped output/cache directory, and the auto-saved IndexedDB state for
  this workflow. Folder deletion uses the platform dialog system. For non-empty
  folders, the dialog offers three choices: delete all child workflows/folders,
  move direct children up to the deleted folder's parent, or cancel.

### 3.9 Execution Panel (Menu / Toolbar)

**Buttons:**
- **Run Workflow**: Execute all enabled nodes that are Unexecuted or Out-of-date. Shows a confirmation dialog: "The following out-of-date nodes will be re-executed, replacing their previous outputs: [list]. Continue?" **Disabled** when a validation request is pending or the debounce timer is active. If clicked during the debounce window, the frontend flushes the debounce (sends `PUT /graph` immediately), waits for the validation response, and only then proceeds with execution. If validation fails after the flush, execution is aborted and a toast is shown: "Validation errors found — fix them before running."
- **Run Selected:** Run only the currently selected nodes (and all their out-of-date or unexecuted dependencies). Sends `POST /execution/run` with `nodes` set to the selected node names. Also available via right-click context menu on selected nodes. Same debounce-flush behavior as Run Workflow.
- **Stop:** Cancel the current execution. Visible only during execution.

**During execution — Non-Modal Execution Banner:**

Instead of a blocking modal, the GUI shows a **persistent execution banner** at the top of the canvas. The user can inspect completed nodes, view the Data Table, and browse the Logger Panel while execution is in progress. Graph **mutations** are locked (node/edge creation, deletion, parameter changes, drag-to-reorder), but read-only inspection is allowed.

- **Banner content:** "Executing workflow..." + overall progress bar (nodes completed / total) + current node name + row progress bar + **Stop** button.
- **Canvas overlay:** Running nodes show a pulsing blue border. Completed nodes turn green in real-time.
- **Locked interactions during execution:** Adding/removing nodes or edges, changing parameters, enable/disable toggle, clear outputs, save workflow, undo/redo. These actions are grayed out with a tooltip: "Locked during execution."
- **Allowed interactions during execution:** Selecting nodes, viewing the Node Panel (read-only), browsing the Data Table (completed nodes show their output), scrolling the Logger Panel, panning/zooming the canvas, opening images in Napari.
- **Stop button:** Cancels execution. The banner updates to "Execution stopped" and disappears after 3 seconds (or on click).
- **On completion:** The banner shows "Execution complete" (green) or "Execution failed" (red, with error summary) and disappears after 5 seconds (or on click). On failure, the failed node is auto-selected so its error is visible in the Node Panel.
- **Safety guarantee:** Since all graph mutations are locked, the running workflow cannot be affected by user actions. The server also rejects `PUT /graph` and `PATCH /graph/nodes/{id}/parameters` during execution (returns HTTP 423 Locked).

### 3.10 Image Viewer

Napari is managed by the backend via Wetlands (isolated Conda environment). The backend uses a `NapariLauncher` that:

1. Creates or reuses a Conda environment with `napari` and `pyqt` via Wetlands
2. Launches a `napari_manager.py` script in that environment
3. Communicates via `multiprocessing.connection` (Client/Listener on localhost)
4. Auto-reconnects if Napari crashes or is closed by the user

**Interactions:**
- **Open in Napari:** Triggered from Data Table image cells. Sends `POST /napari/open {paths, clear_layers: false}`.
- **Replace in Napari (Ctrl+Click):** Same endpoint with `clear_layers: true`.
- Napari is launched lazily on first use.

### 3.11 Error Handling

Three levels of error display:

**Validation errors:** Inline red border on the affected parameter field + tooltip with the error message. For invalid edges: visual rejection (red flash) + toast notification with reason.

**Execution errors:** Failed nodes turn red. The Node Panel's Output section (Section 3.5.5) shows the error message and traceback. The error is also logged in the Logger Panel. The GUI shows: "Node failed on row {N} of {total}. All results for this node were discarded. Fix the issue and re-run."

**System errors:** A global error indicator (icon in the top bar). The indicator is visible whenever one or more errors have occurred. Clicking it opens a sliding panel showing the error history. Each error entry includes timestamp, type, and message, and can be dismissed individually (cross button). Auto-dismiss for transient WebSocket reconnections.

### 3.12 Settings Panel

A dedicated panel or modal for application configuration. Settings are persisted as a JSON file at `~/.bioimageflow/settings.json`. Defaults are applied for any missing keys.

#### 3.12.1 External Editor Settings

- **External editor command:** Text field. Placeholder:
  `code {workspace_path} --goto {file_path}`. `{workspace_path}` is replaced
  with the current workspace folder and `{file_path}` with the focused file. If
  empty, "Open in editor" copies the relevant path to clipboard with a toast.

#### 3.12.2 Napari Settings

- **Napari environment path:** Path to an existing Napari Conda environment. If set, BioImageFlow uses this instead of creating one via Wetlands.

#### 3.12.3 Execution

- **Execution engine:** Dropdown to select `sequential` or `parsl`.
- **Cache max executions:** Number spinner (or empty for unlimited). Maximum cached executions per node.
- **Cache max age:** Text input (e.g., "30d", or empty for unlimited). Maximum cache age.

#### 3.12.4 Storage

- **Workspace path:** editable folder picker in desktop mode. Changing it
  switches the one active per-user workspace after confirmation. The backend
  creates `workflows/`, `tools/`, `data/`, and `outputs/` if missing.
- **Workflows root:** read-only display of `workspace/workflows/`.
- **Workspace tools root:** read-only display of `workspace/tools/`.
- **Outputs root:** read-only display of `workspace/outputs/`.
- **Tool store path** display (default: `~/.bioimageflow/tool_packages/`)
- **Wetlands path** display (default: `~/.bioimageflow/wetlands/`, resolved by `bioimageflow.paths.get_wetlands_path()`)

### 3.13 Drag and Drop (File Import)

Users can drag and drop files (images, CSVs, etc.) onto the application window.

- **In pywebview mode.** The drop event exposes local filesystem paths. Dropping files creates a "Files" DataFrameTool source node on the canvas, pre-configured with the dropped paths.
- **In browser mode.** The drop event exposes `File` objects, not filesystem paths. The frontend opens the Dataset Browser modal (Section 3.14) in upload mode, with the dropped files queued for upload. Once the user confirms, the server-side paths of the uploaded datasets are used to create the "Files" DataFrameTool source node.

### 3.14 Dataset Browser Modal

A PrimeVue **Dialog** that replaces native file/folder dialogs in browser mode. Shown when:

- The user clicks **Select File** on a Path parameter in the Node Panel (browser mode only; in pywebview mode the native dialog opens directly).
- The user drags and drops files onto the application window (browser mode only).
- A workflow is being imported or otherwise requires selecting server-side input paths.

**Modal layout:**

- **Title bar:** `"Select dataset for: {parameter_name}"` (or `"Upload datasets"` when opened in upload mode via drag-and-drop).
- **Search/filter bar:** Text input at the top, filters the dataset table by filename. The file-type filter from the calling Path parameter (e.g., `*.tif`) seeds this box.
- **Dataset table:** Single-selection, columns:

  | Column | Content |
  |--------|---------|
  | **Filename** | Original filename |
  | **Size** | Human-readable (e.g., "50 MB") |
  | **Upload date** | Formatted date/time |

  Clicking a row selects it.

- **Upload button.** Opens the browser's native `<input type="file">` picker (multi-file). Each selected file is dispatched as its **own POST** to `/datasets/upload` (one file per request), so axios's `onUploadProgress` gives genuine per-file progress and per-file error retry falls out for free. Uploaded files appear as pending rows in the table immediately with a per-row progress bar; on completion the bar is replaced with the final file size from the backend response. Files exceeding `serverCap * 1.1` (10% client-side headroom over the server's authoritative cap — avoids blocking legitimate uploads when the cap has been raised but the cached frontend hasn't reloaded) are rejected client-side before upload with a toast: `"File '{filename}' exceeds the {limit} size limit."`
- **Delete button.** Removes the selected dataset via `DELETE /datasets/{dataset_id}`. Confirmation dialog: `"Delete '{filename}'? This cannot be undone."` Disabled when no row is selected.
- **Footer actions:**
  - **Cancel.** Closes the modal without selecting.
  - **Select.** Writes the chosen dataset's `path` (server-side absolute path) into the calling parameter and closes the modal. Disabled until a row is selected.

**Drag-and-drop upload mode.** When the modal is opened by a file drop, the dropped files are auto-queued for upload and the **Select** button is pre-targeted at the first successfully uploaded file. On successful upload, the action bar adds a **"Create Files node"** button (in addition to Select) that creates the "Files" DataFrameTool source node on the canvas with the uploaded paths and closes the modal.

**Error handling.** Per-file upload errors from the server (`errors` array in the upload response) are shown inline on the corresponding row with a **Retry** button. Network failures show a toast with a Retry action.

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

The frontend auto-saves the current graph state to **IndexedDB** on every modification (debounced at 500ms). IndexedDB is used instead of `localStorage` to avoid the ~5-10MB size limit and to support large workflows with many nodes. This protects against browser crashes, accidental tab closure, or server failures.

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
  |      If a "last opened" workflow id is saved in user settings:
  |        Load it via GET /api/v1/workflows/{id}
  |      Else:
  |        Create new empty workflow (POST /api/v1/workflows with default name)
  |
  +--> Application ready
```

**Unsaved state indicator:** The workflow title in the menu bar shows `"My Workflow *"` when the current graph differs from the last saved version. The asterisk disappears on `Ctrl+S` (save). Closing a workflow with unsaved changes shows a confirmation: "Discard unsaved changes?"

Manual save (Ctrl+S) persists to a real file on the server via `PUT /workflows/{id}`.

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

- **Undoable operations:** Node add/remove, edge add/remove, parameter changes, node position changes. All are pure client-side graph state changes.
- **Not undoable:** Execution, clear outputs, save, tool installation. These have server-side effects that can't be reversed by restoring client state. The frontend shows a confirmation dialog for destructive operations (Clear already does, per Section 3.5.2).
- **Granularity:** Each user action is one undo step. A parameter change is captured on blur/Enter (not per keystroke). Moving multiple selected nodes is one step.
- **Stack size:** 100 steps (configurable). Oldest entries are dropped.
- **On workflow load:** Undo history is cleared (no mixing undo stacks across workflows).

---

## 5. Edge Cases and Error Scenarios

### 5.1 Tool Not Found

A workflow references a tool that is no longer installed (package uninstalled, or workflow shared from another machine).

The node is rendered with a red "Tool not found" badge. The Node Panel shows the tool name and a "Install package" button (if the package is known in the tool store registry). The node cannot be executed until the tool is available.

### 5.2 Missing Package Version

A workflow requires a tool package version that is not in the tool store (e.g., workflow saved with `bioimageflow-cellpose==1.2.0` but only `1.3.0` is installed).

On load, the server reports missing packages in the load response. The frontend shows a dialog: "This workflow requires packages not installed: [list]. Install them?" Options:
- **Install required versions:** Installs the exact versions into the tool store.
- **Use installed versions:** Updates the workflow to use the versions currently in the tool store. All affected nodes are marked Out-of-date.

---

## 6. Keyboard Shortcuts

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

## 7. API Endpoint Summary

| # | Method | Endpoint | When used |
|---|--------|----------|-----------|
| 1 | `GET` | `/api/v1/tools` | Startup; after package install/uninstall |
| 2 | `GET` | `/api/v1/tools/{tool_name}/source` | "Open in editor" button in Tools Panel |
| 3 | `GET` | `/api/v1/tools/packages` | Startup; Tools Panel tool list and Manage Tools dialog |
| 4 | `POST` | `/api/v1/tools/packages/{name}/install` | Install button in Manage Tools dialog; version change |
| 5 | `DELETE` | `/api/v1/tools/packages/{name}` | Uninstall button in Manage Tools dialog |
| 6 | `POST` | `/api/v1/tools/environments/{name}/start` | Start env toggle in Tools Panel / Manage Tools dialog; pre-warming |
| 7 | `POST` | `/api/v1/tools/environments/{name}/stop` | Stop env toggle in Tools Panel / Manage Tools dialog; freeing resources |
| 8 | `GET` | `/api/v1/workspace` | Startup; Settings storage section |
| 9 | `PATCH` | `/api/v1/workspace` | Desktop workspace path change |
| 10 | `GET` | `/api/v1/workflows/tree` | Workflows panel tree |
| 11 | `POST` | `/api/v1/workflows/folders` | Create folder in Workflows panel |
| 12 | `PATCH` | `/api/v1/workflows/folders/{path}` | Rename or move folder |
| 13 | `DELETE` | `/api/v1/workflows/folders/{path}` | Delete empty folder, recursively delete children, or move children up |
| 14 | `GET` | `/api/v1/workflows` | Compatibility flat workflow list |
| 15 | `POST` | `/api/v1/workflows` | "New workflow" menu; startup (if no existing workflow) |
| 16 | `GET` | `/api/v1/workflows/{id}` | Opening a saved workflow |
| 17 | `PUT` | `/api/v1/workflows/{id}` | Ctrl+S save; "Save" menu |
| 18 | `DELETE` | `/api/v1/workflows/{id}` | "Delete workflow" menu |
| 19 | `PATCH` | `/api/v1/workflows/{id}` | Update, rename/move, or duplicate workflow |
| 20 | `PUT` | `/api/v1/graph` | On structural changes (debounced 300ms) |
| 21 | `PATCH` | `/api/v1/graph/nodes/{id}/parameters` | On parameter-only changes (lighter validation) |
| 22 | `GET` | `/api/v1/nodes/{node_id}/data` | Selecting a node to view its output in Data Table |
| 23 | `GET` | `/api/v1/nodes/{node_id}/data/csv` | "Download CSV" button in Data Table |
| 24 | `GET` | `/api/v1/nodes/{node_id}/thumbnail` | Lazy-loading image thumbnails in Data Table cells |
| 25 | `GET` | `/api/v1/nodes/{node_id}/status` | WebSocket reconnection (resync node states) |
| 26 | `POST` | `/api/v1/execution/run` | "Run Workflow" / "Run Selected" buttons |
| 27 | `POST` | `/api/v1/execution/stop` | "Stop" button in execution banner |
| 28 | `POST` | `/api/v1/execution/clear` | "Clear" button in Node Panel |
| 29 | `GET` | `/api/v1/execution/status` | WebSocket reconnection (resync execution state) |
| 30 | `GET` | `/api/v1/settings` | Opening Settings panel; startup |
| 31 | `PATCH` | `/api/v1/settings` | Changing non-workspace settings |
| 32 | `POST` | `/api/v1/fs/reveal` | "Open output folder" or "Reveal in file browser" |
| 33 | `POST` | `/api/v1/napari/open` | "Open in Napari" button in Data Table |
| 34 | `GET` | `/api/v1/napari/status` | Checking Napari availability |
| 35 | `POST` | `/api/v1/editor/open` | "Open" from Data Table path cells |
| 36 | `POST` | `/api/v1/editor/open-tool` | "Open in editor" from Tools Panel or node source links |
| 37 | `GET` | `/api/v1/health` | Health check |
| 38 | `GET` | `/api/v1/datasets` | Dataset Browser modal — populate list (browser mode) |
| 39 | `POST` | `/api/v1/datasets/upload` | Dataset Browser modal — upload button; drag-and-drop in browser mode |
| 40 | `DELETE` | `/api/v1/datasets/{dataset_id}` | Dataset Browser modal — delete button |

Total: 40 endpoints.

---

## 8. Security

The server binds to `localhost` only. No authentication is required. The application runs as a desktop process with the same permissions as the user.
