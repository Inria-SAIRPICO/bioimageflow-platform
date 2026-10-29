# BioImageFlow Platform Specifications — v1 (MVP)

Read the [BioImageFlow library specification](bioimageflow/docs/source/specs.md) first for the underlying workflow and tool contracts.

> **Status: normative current base.** This document defines the implemented single-user platform baseline. [v2](platform_specs_v2.md) contains cumulative, implemented additions. [v3](platform_specs_v3.md) is a future webapp and multi-user proposal, not a description of current behavior.

This is the desktop-oriented MVP specification for the BioImageFlow GUI. It covers the core feature set needed for a fully functional single-user application, including the plain-browser development runtime described below.

---

## 1. Overview

The BioImageFlow GUI is a desktop application for building, executing, and inspecting bioimage analysis workflows visually. It wraps the [BioImageFlow library](bioimageflow/docs/source/specs.md) with a node-based editor, parameter panels, data viewers, and execution controls.

**Architecture:** The GUI follows a client-server model. The backend is a Python server (FastAPI) that wraps the BioImageFlow library and exposes a REST + WebSocket API. The frontend is a Vue SPA that communicates with the backend exclusively through this API. The application is packaged with pywebview, giving access to native file dialogs.

**Desktop vs. browser runtime detection.** The same frontend bundle runs in two environments:

- **Inside pywebview (desktop).** The frontend detects this at runtime by checking for `window.pywebview` (injected by pywebview into the page). Path selection uses the native OS file dialogs exposed via `window.pywebview.api` (`select_file`, `select_files`, `select_folder`, `save_file`). Drag-and-dropped files are treated as local filesystem paths — the user's machine and the server share the same filesystem.
- **In a plain browser.** When `window.pywebview` is absent (e.g., the user pointed a browser at the FastAPI server for testing, or this is the basis for a future webapp deployment), the server's filesystem is not directly accessible from the client. Path selection instead activates the docked **Datasets panel** in transient single-file picker mode (Section 3.14), where the user can upload files and select managed datasets. Drag-and-drop queues uploads in that panel.

Dataset management endpoints (Section 2.4.10) are available in both environments — they are the only way for a non-pywebview client to get bytes onto the server. In pywebview mode they are unused by the standard flows but still reachable.

**Collaboration:** The MVP is single-user. Multi-user authentication, collaborative editing, and CRDT merge semantics are deferred. Current revision checks detect stale writes but do not merge concurrent edits.

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
- **Dependencies:** Published registry SDK/Core/provider versions are locked in `backend/uv.lock`; the platform requests BioImageFlow's `parsl` and `psij` dependency groups for its packaged target-integration surface.
- **Development fixtures:** Executable seeded tools are packaged separately from server routes and bundled workflow scripts, retaining ordinary finite primary-source admission when development routes are enabled.

### 2.2 Architecture: Draft-Backed Full-State Sync

Each frontend canvas owns its immediate graph snapshot, canvas identity, workflow or nested-snapshot identity, revision state, and synchronization resources. For a root workflow canvas, the backend live draft is the durable source of truth for the current editable graph. The backend remains the validation and execution authority. `workflow.json` is the saved/exportable artifact; it is updated only by explicit save/promotion flows.

Normal root-canvas synchronization sends complete graph snapshots to `PUT /workflow-drafts/{id}` with revision CAS. The accepted draft response is the ordinary persistence and validation authority: it returns the accepted graph, draft revision, validation errors, and derived node statuses together. Nested canvases use their private snapshot endpoint instead. `PUT /graph` remains a request-local, stateless compatibility and transient-validation endpoint; it does not persist a graph or select an active canvas.

The backend retains workflow and draft files, private nested snapshots, agent workspace context, and execution state separately from request-local graph validation.
A server restart loses an attached local running workflow, while root drafts and accepted nested snapshots remain recoverable; durable managed remote runs follow the separate registry and attachment contract in [distributed execution Sections 6–7](platform_specs_distributed_execution.md#6-submission-and-identity).

**Server state is minimal:**

| State | Description |
|-------|-------------|
| `tool_registry: dict[str, type[BaseTool]]` | Discovered tools indexed by class name (the unique tool identifier) |
| `agent workspace context` | The active workflow id and draft revision written for external agents; this context does not select graph meaning for validation, persistence, or execution requests |
| `execution_task: Task | None` | Handle to the currently running execution (for cancellation) |
| `napari_launcher: NapariLauncher or NapariLauncherPool | None` | Manages the legacy process and UUID-keyed registered-environment processes (lazily created) |

There is no `last_valid_workflow` cache and no authoritative backend editor session. Validation of root edits persists an accepted draft, and Run and Clear load that exact draft by workflow ID and revision before compiling it. Run Selected compiles the complete accepted graph, then derives the requested root node IDs plus their transitive upstream root IDs from its edges. A diagnostic is ignored only when its scoped node path proves that it belongs to a root node outside this selected execution scope; diagnostics owned by a selected or upstream workflow boundary, including descendant paths, remain blocking, as do global or otherwise unattributable diagnostics.
If selected execution ignores proven-unrelated diagnostics, it then publicly compiles and validates the selected-plus-upstream root projection, preserving configuration, scoped identities, complete nested workflow boundaries, and relevant interface ports and edges; every projection diagnostic remains blocking, and accepted draft authority is rechecked after compilation before execution.
Clean selected graphs reuse their complete-graph compilation.

**Key design points:**
- **Backend draft source of truth.** Open workflow state is persisted as a backend draft under the workflow directory. Frontend memory and IndexedDB are fallback/local interaction state, not the authoritative saved draft.
- **Canvas-scoped ownership.** Every registered canvas owns its graph snapshot, identity, revision, persistence coordinator, and derived status projection. Active-canvas facades only route commands to that ownership boundary.
- **Structured server-side graph editing for agents.** Normal canvas editing still sends full graph state. Agents use validated draft operations instead of hand-editing workflow JSON.
- **Undo/redo is purely client-side.** The frontend maintains its own undo stack (snapshots of the graph state). No server round-trip needed. See [Section 4.6](#46-undoredo) for details.
- **Validation is authoritative on the server.** The frontend may do lightweight client-side checks (cycle detection, basic type checks) for instant UX feedback, but the server is the final authority before execution.
- **Vue Flow maintains the interactive graph client-side.** This approach keeps editing responsive while the backend draft provides durable state for agents, save, run, and export.
- **Attached local execution locks graph editing.** Local runs exclude graph mutations while starting or running and permit read-only inspection.
  Durable managed remote runs own immutable submissions and permit later editing under [distributed execution Section 10](platform_specs_distributed_execution.md#10-execution-panel-and-target-selection).

**Compatibility and deferred architecture:** Frontend active-session facades retain a zero-registered-canvas compatibility mode for older callers and tests; normal multi-canvas operation always resolves an explicit registered canvas. Canvas synchronization uses revision CAS and explicit execution context, not CRDTs or graph-content digests. Generalized multi-file filesystem transactions are deferred; individual JSON persistence and targeted identity repairs remain atomic.

### 2.3 Tool Discovery and the Tool Store

The server uses the BioImageFlow **tool store** (`~/.bioimageflow/tool_packages/`) to discover and load versioned tool packages. At startup, the server loads all installed package versions via `load_versioned_package()` and builds the tool registry.

The desktop application runtime uses Python 3.12 through 3.14. BioImageFlow Core 0.5.x resolves lazily evaluated class annotations on Python 3.14 so installed tools retain their input and output schemas.

Tools are indexed by **class name** (the unique tool identifier; `BaseTool.display_name` is the human-readable label) and organized by `tags`. The tool store directory can be overridden via the `BIOIMAGEFLOW_TOOL_STORE` environment variable.
Store scanning and explicit package lifecycle operations use the library's public installation-selector admission to ignore unrelated directories and private installer staging before loading or unloading a version.
Supported selectors with invalid or incomplete installations remain visible with their original load diagnostic; secondary unload failures do not replace that diagnostic.

Installed code is held as an immutable admitted generation selected by canonical tool-store root, package name and version.
Its first admission captures installation metadata, selected controller dependency compatibility, source content and installed inherited implementation owners; subsequent loads and plans reuse those facts without repeating distribution inventories, installation-record walks or installed-source checks.
Editable and workflow-local sources retain fresh capture for each operation, while parameters, bindings, runtime readiness and selected immutable result records retain their normal checks.
Generation counters and store paths govern selection and lifetime, not scientific cache identity.
The normal platform dependency manifest and lock select published BioImageFlow 0.9.5/Core 0.5.1 with this lifecycle integration.

Installed file edits do not trigger hot reload or change the admitted generation.
A controlled refresh or uninstall must retire the exact selected generation before replacement or removal, and a real store-root change preflights all affected published selections together, including packages loaded only through carried workflow bindings.
If an admitted operation still owns any affected generation, the operation refuses before changing files or registry state; it does not cancel the execution.
A retired class cannot authorize a new operation, and a failed replacement does not restore retired code.
Selecting the same global store again leaves its generations intact; changing installed controller dependencies requires a process restart.

**BioImageFlow state paths:** The platform must resolve BioImageFlow-owned state paths through `bioimageflow.paths` (`packages/bioimageflow/bioimageflow/paths.py`). Unless explicitly overridden, the BioImageFlow home is `~/.bioimageflow`, the tool store is `~/.bioimageflow/tool_packages`, and the Wetlands instance path is `~/.bioimageflow/wetlands`. Supported overrides are:

| Variable | Effect |
|----------|--------|
| `BIOIMAGEFLOW_HOME` | Changes the base directory for BioImageFlow state (`tool_packages`, `wetlands`, settings, etc.) unless a more specific variable is set. |
| `BIOIMAGEFLOW_TOOL_STORE` | Overrides only the tool store path. |
| `BIOIMAGEFLOW_WETLANDS` | Overrides only the Wetlands instance path. |

The default settings file is `<BIOIMAGEFLOW_HOME>/settings.json`, and a new settings document derives its tool-store default from `bioimageflow.paths.get_tool_store_path()`.
An explicit `BIOIMAGEFLOW_HOME` also places the default desktop workspace at `<BIOIMAGEFLOW_HOME>/workspace`; an explicitly selected workspace still wins.
Without that override, the desktop workspace remains `~/BioImageFlow/workspace`.
Launcher runtime roots contain application sources and their interpreter environments, independently of this user profile: reinstalling or replacing a launcher runtime does not reset settings, tools, or workflows.
The health endpoint reports installed distribution metadata when available, otherwise the static version from the platform's own source-archive `backend/pyproject.toml`; an unpackaged or unreadable project falls back to `0.0.0-dev`.

The platform must not rely on Wetlands' own `EnvironmentManager()` default for BioImageFlow-managed environments. Plain Wetlands defaults its root to cwd-relative `./wetlands`; this can happen if a service calls Wetlands directly or calls `bioimageflow.env_manager.get_shared_environment_manager()` before BioImageFlow has configured it. Because Wetlands uses a process-wide shared manager, the first initialization in the process fixes the Wetlands path for later callers. Tool execution, manual tool environment controls, Napari, thumbnails, and embedded code-server must therefore all use the same BioImageFlow-resolved Wetlands root.

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
| `GET` | `/tools/{tool_name}/usage` | Return affected saved workflow IDs, including references in recursively embedded workflows |
| `GET` | `/tools/packages` | List all packages (installed and known). Returns installed versions, available versions, tools per version, and environment status. This is the single source of truth for the Tools Panel — no need to cross-reference with `GET /tools`. |
| `POST` | `/tools/packages/refresh` | Refresh the known and installed package catalog from its configured package-index sources. |
| `POST` | `/tools/packages/{package_name}/install` | Install a package version into the tool store (body: `{version?: str}`) |
| `DELETE` | `/tools/packages/{package_name}` | Uninstall the exact stored version selected by optional `?version=X`; omission removes the selected package's versions |
| `POST` | `/tools/environments/{env_name}/start` | Start a tool's Wetlands environment |
| `POST` | `/tools/environments/{env_name}/stop` | Stop a tool's Wetlands environment |
| `POST` | `/tools/environments/{env_name}/recreate` | Create or replace a tool's managed Wetlands environment |

Custom-tool usage inspects tool nodes at every graph depth without reading tool-only fields from workflow nodes.
It resolves and returns workspace-relative workflow IDs, including folder segments, and lists each affected workflow once.

**Package uninstall ownership:** Package and explicit version selectors must be exact safe stored path components; an empty explicit version is invalid, not an all-versions request.
Uninstall admits only the selected physical directory below the configured tool-store root, without importing its code or requiring registry membership, distribution metadata, or version normalization.
A configuration-level root symlink is supported; package/version symlinks, non-directory entries, traversal and unsafe selectors return HTTP 400 `bad_request`, while a safe absent selection returns 404.
Path admission precedes generation retirement, hot-reload suppression and registry changes; the captured root, package ancestor and selected directory identities are checked again at physical removal and before any failed-trash fallback.
Supported version selectors are derived from the selected stored directories rather than successful metadata imports, and all affected loaded generations are preflighted atomically before retirement.
An active-operation refusal leaves the directory and registry unchanged; safe legacy directory names unsupported by the loader remain removable without importing them.
After retirement, selected package/version namespaces remain reserved through offloaded physical removal and registry update; a concurrent carried workflow read cannot re-admit the still-present directory.
The reservation releases after removal or failure, and any recovery re-admission occurs only after release.
Fallback must not remove a missing or substituted target; successful removal forgets only the exact selected package/version and explicitly publishes removals or the remaining active version's metadata without relying on watcher events.
A failed physical removal can re-admit only the unchanged owned selection and restores its prior active-version choice only after that re-admission succeeds.
It never restores retired class objects or imports a substituted or partially removed target, and recovery preserves the original removal error.
Other versions/packages and managed worker environments remain independent.
These checks serialize the service's cooperating operations and refuse observed ownership changes; they do not promise an atomic filesystem transaction against arbitrary external writers, rollback after physical removal, or cancellation-safe settlement of offloaded physical removal.

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
| `path_picker` | `"file" \| "folder" \| "both" \| null` | From `GUIMeta.path_picker`; controls picker actions for path-typed inputs without adding runtime validation. |
| `choices` | `string[] \| null` | Populated for `Literal[...]` and `Enum` fields. |
| `image_spec` | `object \| null` | `{semantics, layouts, dtypes, formats}` each as `string[]`, populated for `ImageFile` / `ImageShared` fields. |

Per-field `OutputFieldSchema`:

| Key | Type | Notes |
|-----|------|-------|
| `type` | `string` | Display name. |
| `type_spec` | `object` | The library's finite semantic annotation descriptor, independent of the display label (for example `{"kind": "Path"}`). |
| `required` | `boolean` | `true` when no class-level output default is declared. |
| `nullable` | `boolean` | `true` when the output annotation admits `None`; independent of `required`. |
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
| `dataframe_output` | `boolean` | `true` means the node exposes its full output DataFrame via the `bif:v1:dataframe-output` header pin. This is `true` for both `ProcessingTool` and `DataFrameTool` nodes in the current library. |
| `row_consumption` | `"mapped" \| "collective" \| null` | Required metadata describing column-edge row semantics. Processing tools use `mapped` when rows are independent and `collective` when one batch operation may combine aligned rows. DataFrame tools use `null`. |
| `environment.path` | `string` | Platform-resolved absolute managed environment location, added to a declared environment for local display and management. It is not portable tool-definition state. |

`GET /tools` resolves declared environment names against one fresh public managed-environment inventory per request, including expected paths for environments not yet created.
This filesystem work runs off the server event loop, does not provision or start workers, does not mutate registry metadata, and retains no inventory across requests.

**The `"any"` type.** The library reserves `"any"` (see [library Section 2.4](bioimageflow/docs/source/specs.md#24-type-compatibility)) for columns whose runtime type is not known until execution. `Generate(column_name="x", values=[...])` produces `{x: {type: "any", ...}}` regardless of the values' Python type, because static introspection cannot infer it. GUIs must treat `"any"` as compatible with **any** consumer input type at edge creation. See §3.3.3 for the pin rendering and edge-validity rules.

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
  "row_consumption": "mapped",
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
    "mask": {"type": "ImageFile", "type_spec": {"kind": "Path"}, "default": "{input_image.stem}_mask{ext}", "required": false, "nullable": false, "template": "{input_image.stem}_mask{ext}", "image_spec": {"semantics": ["label"], "layouts": ["YX"], "dtypes": [], "formats": []}},
    "cell_count": {"type": "int", "type_spec": {"kind": "int"}, "default": null, "required": true, "nullable": false, "image_spec": null}
  },
  "environment": {
    "name": "cellpose",
    "dependencies": {"conda": ["cellpose==4.0.8"], "pip": []},
    "allow_flexible_versions": false,
    "path": "/home/user/.bioimageflow/wetlands/environments/cellpose"
  }
}
```

**Endpoint roles:** `GET /tools` returns tool-level metadata (inputs schema, outputs, environment) for graph construction and the Node Panel. `GET /tools/packages` returns package-level metadata (installed/available versions, environment status) for the Tools Panel tool list and Manage Tools dialog. The data intentionally overlaps (both include package name and version) for convenience — the frontend uses `GET /tools/packages` to populate the Tools Panel, and `GET /tools` to resolve tool schemas when building nodes.

Tool environment metadata preserves the declared recipe's name, detached dependency projection and `allow_flexible_versions` flag, so reconstructing a recipe does not turn an explicitly flexible requirement into an exact-only requirement.

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

**Package installation:** The platform app environment includes `pip` as a runtime dependency because both versioned package installation through BioImageFlow and URL/archive source imports run the app interpreter's `python -m pip install --no-deps --target <dir>` to populate the tool store.
The platform supplies compatible controller dependencies; ProcessingTool worker dependencies remain in their declared execution environments.
The selected package is explicitly indexed before installation reports success, and a load failure returns HTTP 400 with its original detail; an unrelated pending editable-source failure does not fail a successful selected installation.
Re-indexing an already admitted unchanged version reuses its generation rather than retiring code held by a running operation.
This operation is separate from Wetlands worker environment provisioning. During installation, the Tools Panel shows a spinning icon on the package row. Installation progress and errors are streamed to the Logger Panel. Installation can be interrupted via a stop button. **Package installations are serialized** — only one installation runs at a time. If the user requests a second installation while one is in progress, it is queued and a toast informs: "Installation queued — waiting for {package_name} to finish."

**Execution during installation:** If a required package is currently being installed, the "Run" button is disabled with a tooltip: "Waiting for package installation to complete." Execution is blocked until all required packages are fully installed.

**Environment lifecycle:** Environments are automatically started by Wetlands when a workflow is executed. Before first use, BioImageFlow compares the requested recipe with Wetlands-managed state. Before managed Processing identity and cache lookup, a run-scoped adapter uses public `admit_runtime` with the engine's operation-owned admission dictionary; an authorized stale BioImageFlow-owned processing recipe is physically retired and replaced, a matching ready environment is reused, and a missing environment is created without starting scientific workers. The platform never implements this by deleting directories or editing `pixi.toml`. Existing user-managed, external, Napari, adopted, thumbnail, and code-server environments remain under their lifecycle owners and are not replaced by processing execution. After application startup, an already-existing stale `bioimageflow-general` environment is refreshed in the background, but a missing one is not proactively created. The Start/Stop buttons allow manual control (e.g., pre-warming an environment, or freeing resources), and the labeled Create/recreate button is the explicit user-authorized force-rebuild action. Environment status is shown via button color and label (stopped/creating/updating/ready/running); ready content does not imply a running worker pool. Environment controls are disabled during execution or another operation on the same environment.
Every platform-owned Wetlands provisioning path subscribes to its public operation events before waiting for the environment and streams setup stages and sanitized Pixi stdout/stderr lines to the Logger panel. During local workflow execution, those entries retain their execution and node attribution; replacement publishes `updating` and retains “Updating execution environment” for the affected node. A node-associated setup message is retained independently of numeric progress and shown in the Execution panel until tool execution begins. A tool may constrain `bioimageflow-core` only compatibly with the platform's exact runtime dependency; an explicit divergent requirement is reported as `environment_incompatible` during graph validation and is never silently replaced with another core version.
Workflow execution passes a run-scoped observer to the engine through the public environment-manager API; the process-wide shared manager keeps its original methods across successive runs.
The observer prepares runtime content before the scientific key and cache lookup during whole-workflow and stepwise execution; a cache hit starts no scientific pool.
Each public SDK preparation call supplies its explicit executable `scoped_node_path`, captured with the immutable run context; environment names, shared receipts and the last started node never establish attribution.
A retained waiting job can show its setup message before scientific start without a fabricated start timestamp or numeric progress.
Late observations cannot mutate a newer run, explicit public failure diagnostics own node details, and unscoped exceptions remain run-level.
Unsuccessful completion settles all known running node and retained job presentations without inventing a culprit or node traceback, preserving their recorded progress and explicit completed, failed and disabled states; logical settlement does not claim physical worker termination.
Admission reports ready when no pool is running and preserves running for an already-live owned pool, so warm cache-only reuse cannot hide its Stop control.
Dispatch revalidates and forwards the exact admitted runtime receipt and worker grant, without replacing or reprovisioning a generation already used for cache admission.
Automatic Run admission and background `bioimageflow-general` refresh share a platform service guard across fresh inspection and conditional replacement; processing submission separately fences the held receipt under that same guard, so a later generation cannot receive a task identified against the earlier generation.
The guard is released after admission or submission returns and never waits for scientific task completion.
Manual Start, Stop and Create/recreate require the exact declared environment name; tool and package names are not mutation aliases.
After acquiring the shared processing preparation guard, every matching tool declaration must reconstruct the same complete `EnvironmentSpec`, including dependencies and flexible-version policy; the current protected owner is checked under that guard, and unknown names or conflicting recipes are refused before manager access, lifecycle logs, status publication or catalog changes.
All three operations refuse environments owned by another platform lifecycle; Create/recreate uses public `recreate` once, forwards separate removal/provision events, and retains failed physical pool-close ownership for retry.
Manual lifecycle requests hold the execution manager's exclusive idle admission through the complete service operation and its final status publication; starting or running execution and terminal shutdown refuse admission with HTTP 423.
Request cancellation, including repeated task cancellation, does not release that admission while offloaded physical work remains active; after completion the original cancellation is preserved, an operation failure remains observable, and later explicit retry can acquire the idle gate.
Unknown or conflicting declared recipes return HTTP 422, protected lifecycle ownership returns HTTP 403, and unavailable controls return HTTP 503 rather than reporting an operation that did not occur.
Normal development launch profiles explicitly use the installed published core. Separately named `(local core)` profiles set `BIOIMAGEFLOW_CORE_SOURCE` to the sibling source project, expose that same package to the platform process through `PYTHONPATH`, and use a repository-local `BIOIMAGEFLOW_WETLANDS` root. An invalid source is a configuration error, and local-core recipes never share lifecycle state with the normal Wetlands root.

#### 2.4.1b Error Response Format

Ordinary HTTP errors and request-body validation failures use the normalized response shape below. Endpoints with revision conflicts or other domain-specific failure contracts may return their documented typed body instead.

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
| 400 | Bad Request | Semantically invalid request or rejected path |
| 404 | Not Found | Unknown node ID, unknown tool name, unknown workflow |
| 409 | Conflict | Workflow name already exists, execution already running |
| 422 | Validation Error | Invalid JSON/request schema, missing required fields, parameter type mismatch, or rejected graph |
| 423 | Locked | Graph mutation attempted while an execution is starting or running |

#### 2.4.2 Workflow Management

Every user has exactly one active BioImageFlow workspace. In desktop mode this is a user-editable filesystem path stored in Settings and defaults to `~/BioImageFlow/workspace/`. The current workspace authority is the workflow tree:

```text
workspace/
  workflows/                          # saved workflow tree
    <workflow-id>/
      workflow.json
      tools/                           # custom tools owned by this workflow
      results/                         # BioImageFlow runtime storage
```

In webapp mode the workspace root is administrator-managed; the generic settings route and direct workspace route both refuse client retargeting, while a persisted administrator root becomes authoritative after settings load.

`GET /workspace` reports the workspace, workflow, and reserved tool roots. Each named workflow owns its runtime data under `<workflow-directory>/results`, so moving or deleting the workflow naturally carries or removes its results. Dataset uploads use the configured dataset root or `<workspace>/datasets`.

Saved workflows are organized under `workspace/workflows/` as folders. Each workflow is a directory that contains `workflow.json` and optional workflow-local files such as `tools/`.

Workflow identifiers are derived from their slash-separated directory paths relative to `workspace/workflows/`, for example `segmentation/nuclei`; they are not independent metadata. `WorkflowInfo.name` remains the required compatibility field and `WorkflowInfo.id` is an optional preferred path-derived identity, so clients fall back to `name` when `id` is absent. `WorkflowInfo.identity_generation` is a non-negative, workspace-durable incarnation counter that advances before an identity is created, deleted, duplicated into, imported into, or moved. The atomic workspace ledger retains tombstones for removed and moved-away IDs, so clients compare generations across WebSocket reconnects and backend restarts and replace a mounted presentation only when that durable generation actually changes. Each folder or workflow path segment may contain letters, numbers, spaces, underscores, and hyphens. Empty segments, path traversal, and leading/trailing whitespace are rejected.

Opening an existing saved workflow with a missing referenced custom-source manifest or Python file returns HTTP 409 with `workflow_source_missing`, rather than reporting that the workflow does not exist.
The detail names the source identity and missing workflow-relative file, identifies an older `.bioimageflow/dependencies/<source-id>/source.json` record when present, and provides recovery guidance.
Opening an absent workflow retains HTTP 404.

An explicit `name_override` on workflow archive import sets the destination workflow ID to the override and the root graph's `name` and `display_name` to its leaf name, so the import rename dialog changes the name shown in the tree and canvas tabs.
Without an override, import preserves the archive's graph names; nested workflow names are preserved in either case.

Renaming or moving a workflow or containing folder changes every affected path-derived workflow id. If an affected workflow already has a draft, the backend validates it before the move and atomically rewrites only its embedded `workflow_id` after the move; workflows without drafts do not gain one. A defensive draft read repairs a valid legacy identity mismatch to the requested route without discarding unknown JSON fields.

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/workspace` | Return current workspace path, workflows root, tools root, deployment mode, and whether the workspace path is admin-managed/read-only. |
| `PATCH` | `/workspace` | Desktop-only in-memory workspace path change. Body: `{workspace_path: str}`. The current endpoint does not create or migrate directories. |
| `GET` | `/workflows/tree` | Return the folder/workflow tree rooted at `workspace/workflows/`. |
| `POST` | `/workflows/folders` | Create a folder under `workspace/workflows/` (body: `{path: str}`). |
| `PATCH` | `/workflows/folders/{path}` | Rename or move a workflow folder (body: `{new_path: str}`). |
| `DELETE` | `/workflows/folders/{path}` | Delete a folder. Body: `{policy: "empty" \| "delete_children" \| "move_children_up"}`. `empty` rejects non-empty folders with **409 Conflict**. |
| `GET` | `/workflows` | Compatibility flat list of saved workflows. New callers should use `/workflows/tree`. |
| `GET` | `/workflows/format-status` | Scan saved workflows, root drafts, and nested snapshots without writing them; return pending/error notices and a content-derived `pending_plan_id`. |
| `POST` | `/workflows/format-migrations/apply` | Confirm and apply the exact previewed format plan. A changed source makes the plan stale and returns HTTP 409. |
| `POST` | `/workflows` | Create a new workflow (body: `{name: str, display_name?: str, description?: str}`). Returns **409 Conflict** if a workflow with the same path-derived name already exists, with a suggested alternative. |
| `GET` | `/workflows/{id}` | Load a workflow (returns full graph JSON including GUI state). |
| `PUT` | `/workflows/{id}` | Save workflow from the current graph/draft path. UI save flows flush/promote the backend draft first. Always succeeds even if graph validation errors exist. |
| `DELETE` | `/workflows/{id}` | Delete a workflow directory, including its workflow-local results, and its retained nested snapshots. An optional `expected_identity_generation` query parameter atomically rejects a stale same-ID confirmation with **409 Conflict** before mutation. Returns `{deleted: true, identity_generation}` for the removed incarnation. |
| `PATCH` | `/workflows/{id}` | Update or duplicate a workflow (body: `{action: "update" \| "duplicate", display_name?: str, description?: str, new_name?: str, folder?: str, new_id?: str}`). Rename and move are update operations. Duplication starts without runtime results. |
| `POST` | `/workflows/{id}/rebind-versions` | Rebind package references to currently active installed versions and return the refreshed workflow plus remaining dependency issues. |
| `POST` | `/workflows/{id}/activate` | Publish the external active-workflow context and return the workflow; this does not select graph meaning for validation or execution. |

Startup only scans for unconfirmed workflow-format updates and forward-completes a transaction whose confirmed journal already exists.
Pending workflows are omitted from the editable tree, and direct saved-workflow or draft access returns HTTP 409 with `workflow_format_update_required`; current unrelated workflows remain usable.
The frontend initially offers **Update workflows** and **Not now**, and a deferred warning retains **Review updates**.
Confirmation rechecks the content-derived plan, preserves every original byte under `<workspace>/.bioimageflow/backups/workflow-format/<plan-id>/...`, synchronizes all backups before replacing any authority, and updates saved workflows, root drafts, and nested snapshots through one forward-recoverable journal.
The result lists every exact backup path; a stale plan or a migration error does not claim that an update or backup succeeded.

Draft endpoints keep unsaved workflow state available to the frontend and terminal agents without overwriting `workflow.json` on every edit. Workflow ids use the same slash-separated path rules as workflow endpoints.
`PATCH /workflows/{id}` with `action: "duplicate"` optionally accepts `graph` to copy a captured draft instead of the saved graph, and `expected_identity_generation` to reject a recreated source identity.
The backend copies all sources referenced by that graph plus editable local tools, stages the complete destination, and publishes it atomically without copying runtime results or mutating the original draft.
The conflict action **Save agent version as copy** uses this operation; it does not create an empty workflow followed by a graph-only save.
The optional `graph` field is rejected for `action: "update"`.

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/workflow-drafts/{id}` | Return the live draft, or synthesize clean revision `0` from `workflow.json` when no draft exists. |
| `PUT` | `/workflow-drafts/{id}` | Replace and validate the live draft using a complete graph and `expected_revision`; returns the accepted graph, incremented revision, validation result, and derived node statuses; rejects stale revisions and execution locks. |
| `POST` | `/workflow-draft-operations/{id}` | Apply 1–10 validated structured operations for agents using `{expected_revision, operations, updated_by?, validate?}`. |


**Workflow loading — missing dependencies:** When loading a workflow that references unavailable package versions or tool classes, the server returns `missing_packages` and `missing_tools` arrays. Available explicitly bound module/class/package/version identities are resolved through the public class loader independently of catalog discovery; unavailable explicit bindings remain missing even beside a same-named catalog class. The frontend dialog lists required versions, installed alternatives, affected nodes, and missing tools. When at least one alternative package version is installed, **Use installed versions** calls the workflow rebind endpoint; the current dialog does not install missing packages.

**Workflow results storage:** The backend derives every named workflow's BioImageFlow storage root as `<workflow-directory>/results` and passes that absolute path explicitly at runtime. The path is not persisted in graph configuration or workflow metadata. Stateless graph services use the private workspace-local fallback `<workspace>/.bioimageflow/runtime`.

#### 2.4.3 Graph Schema and Validation

##### Graph JSON Schema (Pydantic Models)

The full-state sync payload is the canonical recursive `GraphState` defined in [v2 Sections 2–5](platform_specs_v2.md#2-canonical-graph-document).
The strict wire shape is maintained in [`models/graph.py`](backend/src/bioimageflow_server/models/graph.py) and exposed through backend OpenAPI; this section is an overview rather than a second schema transcription.
Every graph carries its schema version, definition and display names, explicit interface, configuration, nodes, and edges at every recursive depth.
Layout, collapsed/enabled state, parameters, resource overrides, and output templates belong directly to that graph.

Nodes are discriminated as tool invocations or embedded workflows.
Tool nodes retain explicit module/class, package/version, and workflow-local source bindings when present; a catalog name must not replace a bound source or qualified tool identity.
Workflow nodes own an embedded graph and bindings keyed by stable child interface IDs; saved-workflow provenance is not execution authority.
Runtime translation to the library's portable form occurs in memory from the accepted graph, without persisting another editable representation.

Edges are discriminated as `column` or `dataframe`:

- A column edge connects a named output to a tool field or stable workflow field-input ID.
- A DataFrame edge connects a complete DataFrame to exactly one positional tool target or stable named workflow DataFrame-input ID.

DataFrameTool keyword parameters are constant-only and never expose column input pins, irrespective of an individual field's GUI metadata.
Published field ports may supply constants to those parameters, while a column-valued binding through a recursive interface is rejected at its ultimate DataFrameTool target.
Tool schemas resolve postponed and inherited Python annotations while retaining `Annotated` GUI/image metadata; validation and serialization use the same declarations.
The versioned endpoint-handle codec distinguishes structural endpoint kinds and IDs from display labels, as specified in [v2 Section 4](platform_specs_v2.md#4-edges-and-endpoint-handles).

**Structural identities:** A node's immutable `id` identifies API, edge, and WebSocket references; its editable `name` is a presentation label.
The frontend generates readable node IDs from tool class names with uniqueness suffixes, but renaming a label never changes its ID.
Node, edge, and interface IDs must be unique in their owning graph and valid for their structural role.
Edge IDs are unique frontend-generated strings; no particular UUID or nanoid generator is required.
Published positional DataFrame targets and internal DataFrame edges reserve one shared sequence of slots and compact together when removed, preserving surviving public port IDs and names ([v2 Section 5](platform_specs_v2.md#5-workflow-interfaces)).
Strict backend validation checks that accepted graph rather than silently normalizing edges alone.

**Derived status:** `NodeStatus` is separate from `NodeState` and is never saved as graph definition content.
It carries the structural node identity, status/cache assessment, optional failure detail and traceback, and available result/record identity.
The same backend status schema is used by accepted draft/snapshot validation, request-local graph validation, execution, Clear, and WebSocket events; frontend projection remains scoped to the owning canvas and execution context.

**Frontend API types:** Backend OpenAPI is the sole intended source of frontend API types, including recursive graph and workflow-draft routes and responses already generated in `frontend/src/api/types.ts`.
The handwritten draft response/conflict shapes in `frontend/src/api/workflowDrafts.ts` remain transitional implementation debt; they must consume the generated contract rather than become a second authority.

##### Graph Validation Endpoint

| Method | Endpoint | Description |
|--------|----------|-------------|
| `PUT` | `/graph` | Submit the complete graph state for request-local validation. Returns validation and cache status derived only from that request snapshot. |

Normal root canvases do not use this endpoint as their persistence authority; they use the validated `PUT /workflow-drafts/{id}` response. Nested canvases use validated private snapshot writes. `PUT /graph` is retained for explicit request-local compatibility and transient validation, and it never stores an active graph for a later request.

**Request body:** A complete canonical recursive `GraphState`; use the shape in [v2 Section 2](platform_specs_v2.md#2-canonical-graph-document) and the generated OpenAPI models.

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
2. Recursively translates the accepted graph in memory to BioImageFlow objects, preserving explicit tool/source identities, stable interface bindings, and column/complete-DataFrame edge semantics
3. Runs validation (cycle detection, type compatibility, parameter validation via Pydantic). Disabled nodes are skipped during validation.
4. Projects cache status through the library's public `plan()` API using result keys and exact selected upstream immutable record references; diagnostic logical signatures are not reusable cache identities
5. Returns the `ValidationResult` with per-node status

Cache projection is diagnostic rather than all-or-nothing.
If one selected immutable record is corrupt, planning reports that node as failed with a `cache_corrupt` validation error and continues projecting the rest of the graph, so the draft remains readable and saveable.
Normal cache reads and execution remain strict and reject the corrupt branch.

**Validation timing and debouncing:** Each canvas publishes a complete immutable graph snapshot to its own synchronization coordinator. A root canvas queues validated draft persistence, while a nested canvas queues a validated private-snapshot replacement. The transport is debounced so newer snapshots supersede older pending work without sharing state between canvases.

Parameter edit commands first update the owning canvas graph, synchronously publish that complete graph snapshot, mark the edited node provisionally `unexecuted`, and mark existing status projections provisional. Draft or nested-snapshot persistence then runs through the canvas coordinator. `NodeState` itself never receives these provisional or derived status fields.

During the debounce window, the frontend shows provisional client-side status with a subtle visual indicator to signal "unconfirmed." A newer edit supersedes an older pending snapshot, and stale responses cannot replace the owning canvas's newer graph or revision.

**Ctrl+Enter** triggers immediate validation without waiting for the debounce.

All validation transports use complete graph payloads. The server does not infer graph meaning from request history or from another canvas.

#### 2.4.4 Node Data (Outputs)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/nodes/{node_id}/data` | Get the output DataFrame as JSON (paginated: `?page=0&page_size=50`) |
| `GET` | `/nodes/{node_id}/data/csv` | Download output DataFrame as CSV |
| `GET` | `/nodes/{node_id}/thumbnail` | Get image thumbnail (`?row=0&col=mask&size=128`) |

**Data response:**
```json
{
  "columns": ["mask", "cell_count"],
  "index": ["img_001", "img_002"],
  "rows": [
    {"mask": "/path/to/mask1.tif", "cell_count": 42},
    {"mask": "/path/to/mask2.tif", "cell_count": 17}
  ],
  "absolute_rows": [0, 1],
  "total_rows": 250,
  "page": 0,
  "page_size": 50,
  "column_types": {"mask": "ImageFile", "cell_count": "int"}
}
```

For a modern retained result, Node Data and CSV first validate the latest link schema and relative target, require its resolved view to be the canonical directory for the captured run and node, then validate the result key, record, and manifest through the library's exact-record path; a damaged selected record or provenance returns HTTP 409 and never falls back to a stale raw file or companion CSV. A latest view with absent `result.json` remains eligible for the legacy unpinned reader, so that deliberate compatibility path does not provide modern provenance guarantees. Pagination and viewer metadata use the captured identity, and a later integrity failure is also reported as unavailable rather than serving rows from another selection.
Individual and merged modern tables derive column types and viewer declarations from the same request-local producer snapshot already admitted for that exact retained record, without an additional storage read.
Modern thumbnail, image/offset and Reveal requests carry the displayed `ResultArtifactIdentity` as JSON in the `result_identity` query parameter; individual filtered CSV carries it in the request body.
An explicitly selected result is validated through the exact retained-record reader and never falls back to latest when unavailable; omitted identity preserves the unpinned latest-selection API.
Fiji actions likewise carry the displayed identity through their existing typed request.
Node Data query/CSV and image file work runs through FastAPI's bounded worker thread boundary rather than blocking the async server event loop.
Concrete carried output declarations remain authoritative for empty and all-null columns and never borrow a same-named current catalog schema; missing or dynamic declarations and columns not declared by a passthrough model use DataFrame type inference without catalog substitution.
A malformed present output descriptor or mismatched carried metadata identity returns HTTP 409.
Legacy unpinned tables retain their existing current-tool declaration and DataFrame inference behavior without modern producer-provenance guarantees.

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
| `POST` | `/execution/run` | Run an accepted root draft (body: `{workflow_id: str, draft_revision: int, nodes?: [str], mode?: str, retry_of_execution_id?: str}`). The backend loads the graph identified by the required workflow ID and revision. |
| `POST` | `/execution/stop` | Stop the current execution |
| `POST` | `/execution/clear` | Clear outputs for specified nodes (body: `{workflow_id: str, draft_revision: int, nodes: [str]}`). The server loads and validates that accepted draft in its workflow storage context before invalidating cache. `cache_corrupt` diagnostics are permitted only when owned by the requested roots. Clear removes the current selection, quarantines a safely identified corrupt immutable record, and returns freshly projected `NodeStatus` for the cleared nodes and all downstream dependents. On other validation failures, the response includes the complete node-scoped `errors` list and the confirmation dialog displays it so the user can inspect and copy each cause. |

After a successful Clear, the retained live execution-status snapshot for that same workflow reflects the cleared and downstream statuses, including on browser reconnection. The historical `last_result` remains the result of the completed run and is not rewritten by Clear.
On a subsequent authoritative `GET /workflow-drafts/{id}`, cache-derived node statuses and `cache_corrupt` diagnostics are projected from the current accepted graph and workflow storage, including after backend restart. The response retains accepted non-cache diagnostics, replaces cache diagnostics only for nodes examined by the fresh plan, and derives `valid` from the response errors; a node unavailable to fresh planning retains its accepted cache diagnostic and failed status. The persisted draft validation, graph, revision, writer, timestamp, saved baseline, and historical execution result are not rewritten by this read. An enabled downstream node whose library plan is `pending_upstream` projects `out_of_date` if it retains a latest output, or `unexecuted` if it has none; disabled and other planned statuses retain their ordinary semantics. Compilation occurs outside the workflow mutation lock; the accepted draft, identity generation, and storage path are rechecked before planning and latest-output lookup under the same lock used by Clear's commit, retrying if authority changes.
Each stable projection attempt reuses one public compilation for definition validation and cache projection, with at most one plan after that authority fence; no compilation or metadata authority is retained across requests.
A synthesized revision-zero response adopts the complete validation result, including definition diagnostics and resolved tool schemas, while a persisted draft preserves its accepted non-cache diagnostic/schema authority.
| `GET` | `/execution/status` | Get full execution state (see response schema below) |

The `run` endpoint loads the named accepted root draft; it does not infer graph meaning from an editor session or a previously submitted request. Full Run and Run Selected compile that complete graph. Full Run rejects every validation diagnostic. Run Selected derives the requested root node IDs plus all transitive upstream root IDs from the accepted graph edges and filters out only diagnostics whose scoped node path proves ownership by an unrelated root node. A selected or upstream workflow node owns all of its descendant diagnostic paths for this purpose. An empty target list, any unknown requested root ID, any requested target unresolved in the partial compiled workflow, a missing compiled workflow, and every global or unattributable diagnostic reject the request; mixed valid and invalid target lists never degrade to an untargeted run.
A diagnostic library workflow is never passed to compute after unrelated errors were ignored: the accepted dependency closure receives a fresh public compilation, every resulting error is refused, and draft authority is rechecked before dispatch.

Normal root-canvas runs address the accepted draft revision:

```json
{
  "workflow_id": "segmentation/nuclei",
  "draft_revision": 12,
  "nodes": null
}
```

The backend rejects a stale revision with `draft_revision_conflict` and compiles the backend-loaded accepted graph. A request without `draft_revision` or with an inline graph fails request validation.

Every accepted Run creates an immutable execution context `{execution_id, workflow_id, draft_revision}`. The `202` response returns that context plus the fixed `planned_node_ids` and `planned_node_names`, `GET /execution/status` retains it with the current or last accepted execution, and progress, node-state, status-snapshot, and completion messages carry it. The attached local execution lock remains global: only one local execution may run in the process, even when several canvases are open. Durable managed remote submission and editing follow [distributed execution Section 10](platform_specs_distributed_execution.md#10-execution-panel-and-target-selection).
An attached progress callback may update state and publish messages only while its captured execution context is the active running context; late events from a completed or superseded run are discarded.
Ordinary accepted workflow and draft mutations serialize through the execution-admission gate instead of reporting one another as running execution: a mutation already holding the gate blocks Run, a concurrent mutation waits, and an actually starting or running execution rejects the mutation with HTTP 423.

A second `POST /execution/run` while one is already running returns HTTP 409 Conflict.

**Error recovery:** Successfully completed nodes retain their output and cache after a failed or stopped execution. Only the failed node (and its unexecuted descendants) need re-running. The user can fix parameters and re-run specific nodes via the `nodes` parameter.

**Stop behavior:** When execution is stopped, the currently running node's partial output is discarded and its status is set to "unexecuted". It must be re-executed from scratch. Nodes that completed before the stop retain their output and cache.

**Execution status response (`GET /execution/status`):**

```json
{
  "state": "idle",
  "execution_id": "4af78551-23af-4f07-b41f-a18d857d8197",
  "workflow_id": "segmentation/nuclei",
  "draft_revision": 12,
  "last_result": {
    "success": true,
    "errors": [],
    "node_statuses": {
      "cellpose_segmenter_1": {"node_id": "cellpose_segmenter_1", "status": "executed", "cached": true}
    }
  },
  "progress": null,
  "planned_node_ids": ["cellpose_segmenter_1"],
  "planned_node_names": {"cellpose_segmenter_1": "Cellpose segmenter"},
  "node_statuses": {
    "cellpose_segmenter_1": {"node_id": "cellpose_segmenter_1", "status": "executed", "cached": true}
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `state` | `"starting" \| "running" \| "idle"` | Whether an execution is starting, in progress, or idle |
| `last_result` | `ExecutionResult \| null` | Final result of the last execution (same result fields as `execution_complete`). Persists after execution ends and is cleared only when the next Run has been accepted after compilation. `null` if no execution has run since server start. |
| `progress` | `ProgressInfo \| null` | Latest running-node progress: `{node_id, status, row, total_rows, task_current, task_maximum, result_key?, record_id?}`. Row fields retain the library's zero-based row index and total row count; `row_progress` task units remain separate from `row_complete` row completion. |
| `planned_node_ids` | `list[str]` | Immutable scoped executable tool-node paths in this run's target and dependency closure, excluding disabled nodes and aggregate workflow boundaries. Cached nodes remain in the plan. |
| `planned_node_names` | `dict[str, str]` | Display names keyed by the planned scoped tool-node paths. |
| `node_statuses` | `dict[str, NodeStatus]` | Current or final statuses for the retained execution context |
| `execution_id` | `str \| null` | Unique accepted execution identity |
| `workflow_id` | `str \| null` | Path-derived workflow identity compiled for that execution |
| `draft_revision` | `int \| null` | Accepted root draft revision for the retained execution; null only before any run has been accepted |

The frontend derives each canvas's visible status projection from its local provisional state, accepted validation result, and only those execution payloads whose server wire context `{execution_id, workflow_id, draft_revision}` matches the locally captured originating canvas. Canvas ID is frontend-local correlation and is not a WebSocket field. These statuses are never persisted into `NodeState`. `GET /execution/status` remains available for explicit status inspection and recovery callers, including external agents, without making request history a source of graph meaning. Normal WebSocket registration and reconnection recovery uses the contextual `status_snapshot` sent by the backend.

#### 2.4.6 Settings

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/settings` | Get all settings (returns `Settings` model) |
| `PATCH` | `/settings` | Update editable preferences (partial update; deployment-policy and typed-registry fields have separate authorities) |

**Settings schema:**

```python
class OMEROInstance(BaseModel):
    name: str | None = None
    host: str
    port: int = 4064
    username: str

class Settings(BaseModel):
    deployment_mode: Literal["desktop", "webapp"]
    external_editor: str | None = None              # e.g., "code {workspace_path} --goto {file_path}"
    fiji_path: str | None = None                    # selected Fiji.app installation directory
    napari_registry_revision: int = 0
    napari_environments: list[NapariEnvironment] = []
    napari_default_environment_id: UUID | None = None
    napari_filename_rules: list[NapariFilenameRule] = []
    napari_environment_operations: list[NapariEnvironmentOperation] = []
    napari_suppressed_legacy_roots: list[str] = []
    omero_instances: list[OMEROInstance] = []
    tool_store_path: str = Field(default_factory=lambda: str(get_tool_store_path()))
    update_mode: Literal["auto", "manual"] | str = "auto"
    new_workflow_execution: Literal["sequential", "parallel"] = "sequential"
    node_data_page_size: Literal[25, 50, 100, 250, 500] = 250
    keyboard_shortcuts: dict[str, str] = {}
    enable_unsafe_webapp_features: bool = False
    datasets_root: str | None = None
    max_upload_size: int = 2 * 1024**3
    workspace_path: str | None = None
    workspaces_root: str | None = None
```

Deployment mode is configured by the application process, captured when the application is constructed, and cannot be changed by a settings file or API preference update.
Settings load and reads expose that effective mode; accepted writes persist it.
Mode normalization preserves the settings object identity and other live preferences; accepted preference updates retain their existing snapshot replacement semantics.
Loading a valid conflicting file keeps unrelated values and does not require a mode-only rewrite; existing schema migrations retain their documented write behavior.
An injected SettingsStore must have the same configured mode as the application; a mismatch is refused before runtime setup, including when the store has not loaded yet.
Generic settings updates containing `deployment_mode` in either mode or `workspaces_root` in webapp mode are refused with HTTP 403 and `error: settings_policy_read_only`, `field` and a fixed deployment-configuration detail, even if the submitted value echoes the current value.
The settings owner refuses the whole update before candidate validation, credential access or JSON replacement; it does not silently apply other submitted fields.
A webapp administrator root may come from explicit deployment configuration or the trusted settings file loaded at startup; request-time workspace, workflow and dataset resolution preserves that authority rather than accepting generic client retargeting.
Explicit deployment roots retain precedence, desktop workspace editing and ordinary live preferences remain supported, and this policy does not change new-workflow scheduling seeds or file-only unsafe-webapp debugging.

`GET /settings` returns the same fields, replaces each OMERO entry with an `OMEROInstanceResponse` carrying `password_stored: bool`, and adds `resolved_tool_store_path`. An OMERO entry submitted to `PATCH /settings` may include a transient `password`; the password is stored in the operating-system keyring and never returned or written to the settings JSON file.

Before any attempted password write, the settings owner validates all planned writes and captures one original string-or-absent value for every distinct planned write key.
Submitted writes retain their order: an omitted or null password requests no write, while an explicit empty string is a stored value.
On a known failure before settings JSON replacement, it attempts to restore every distinct attempted key once in reverse first-attempt order, including a setter that changed its value before raising or synchronously interrupted the operation.
Original strings, including empty strings, are restored exactly; only an originally absent credential is deleted.
Restoration continues after individual provider failures, preserves the original failure, and reports failed restorations using only a fixed warning and integer count, without credential identities, values or restoration exception text/tracebacks.
This is best-effort compensation within one settings operation, not an atomic settings/keyring transaction or protection against other credential writers; restoration can fail, and accepted replacement, later acknowledgement faults and process termination have no rollback guarantee.
Known pre-replacement failures preserve the previous in-memory settings and exact settings JSON bytes, independently of whether the credential provider permits full restoration.

Settings schema version 3 persists the Phase B napari environment registry and ordered filename rules while preserving Fiji. The settings store reads the former `execution_engine` preference from existing files when `new_workflow_execution` is absent; the live model, API, and new writes use only `new_workflow_execution`.
When a user forgets an adopted legacy napari installation, settings also retain its canonical root as an opt-out from automatic startup adoption.
The generic `PATCH /settings` route returns these fields but rejects direct napari registry or durable-operation mutation; revision-checked typed routes own environment registration, rename/locate/forget, managed create/copy/retry/removal, operation polling/cancellation, default selection, probe, rule creation/reordering, and first-match preview.
Every registry mutation carries and increments `napari_registry_revision` so stale clients cannot overwrite another window's changes.

`enable_unsafe_webapp_features` is a file-only debug switch for local testing of webapp mode. It is ignored in desktop mode. In webapp mode, the default `false` value keeps local source-editing features disabled; setting it to `true` re-enables actions that can modify or open server-side code, such as creating, renaming, deleting, and opening custom tool scripts. The Settings API must expose the value in `GET /settings` but reject attempts to change it through `PATCH /settings`.

#### 2.4.7 File System Helpers

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/fs/reveal` | Open a path in the system file browser |

In pywebview mode, path selection uses native file dialogs — no server-side browse endpoint is needed. In plain-browser mode, path selection activates the Datasets panel single-file picker backed by the catalog endpoints in Section 2.4.10.

#### 2.4.8 Image Viewer Integration

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/nodes/{node_id}/image` | Serve an image-valued output cell; query parameters are `row`, `col`, optional `workflow_name`, and optional `format=ome-tiff`. |
| `GET` | `/nodes/{node_id}/image/{filename}` | Serve the same image with a stable response filename for Avivator-compatible range and offset requests. |
| `POST` | `/napari/open` | Open image(s) in Napari (body: `{paths: [str], clear_layers: bool, environment_id?: UUID, reader_id?: str}`) |
| `POST` | `/napari/launch` | Start one registered environment without dispatching an artifact-open command |
| `GET` | `/napari/status` | Check legacy Napari status, or one registered environment with `environment_id` |
| `POST` | `/napari/shutdown` | Stop the legacy viewer, or one registered environment with `environment_id` |
| `POST` | `/napari/environments/managed` | Start creation of a new managed generation |
| `POST` | `/napari/environments/{environment_id}/copy` | Start an independent recipe-based managed copy |
| `POST` | `/napari/environments/{environment_id}/retry` | Retry a failed/cancelled managed setup when appropriate |
| `GET` | `/napari/environments/{environment_id}/operations/{operation_id}` | Poll one durable managed mutation |
| `POST` | `/napari/environments/{environment_id}/operations/{operation_id}/cancel` | Request public Wetlands operation cancellation |
| `DELETE` | `/napari/environments/managed/{environment_id}` | Stop its viewer and delete a proven platform-owned generation |
| `POST` | `/napari/viewing-readiness` | Passively evaluate a portable viewing-requirement manifest against registered environment inventories |
| `POST` | `/fiji/open` | Open one workflow result image in the configured Fiji installation (body: `{node_id, row, col, workflow_name?}`) |

The Phase B registry foundation also exposes typed desktop-only routes under `/napari/environments` and `/napari/environment-settings`.
They manage external Conda/venv registrations, adopt an existing managed `napari` Wetlands installation without provisioning, probe installed Python distribution metadata in the target interpreter, and persist ordered filename rules.
Desktop startup with a pristine Napari registry and no existing installation registers a metadata-only setup-needed default recipe without acquiring an environment manager or probing.
Its card offers explicit Setup with the same UUID through retry, disables Refresh before installation, and permits metadata-only Forget while it has no installed generation or active operation; the incremented registry revision prevents bootstrap from recreating it.
Webapp mode rejects all of these local operations.
The desktop-only passive viewing-readiness route accepts the manifest returned by workflow import directly and uses the same package-only candidate evaluator as retained-artifact resolution.
It does not reread a workflow, probe or mutate environments, launch a viewer, or execute archive content; its response retains structural output identities, unknown reasons, candidates, effective environments, normalized requirement groups, honest managed-setup prefill, and covered/not-covered/unknown summary counts.
Phase C extends `/napari/open`, `/napari/status`, and `/napari/shutdown` with optional registered environment IDs while preserving their no-ID compatibility behavior.
Managed creation provisions an immutable UUID-addressed Wetlands name with `replace_existing=False` and an `EnvironmentSpec` containing only Python 3.12 through Conda plus napari, Qt, and requested distributions through PyPI.
The persisted recipe retains a PEP 440 Python constraint, but the Wetlands boundary receives the equivalent Pixi/Conda `3.12.*` version specifier; Windows provisioning messages and structured output tails preserve Pixi's UTF-8 diagnostics.
Each operation is persisted before provisioning/removal and has typed state, progress, message, and error fields; startup recovers published ready generations but never represents interrupted progress as live.
Managed removal verifies the public Wetlands name, project path, and generation, stops only the addressed launcher, and retains recoverable `removing` intent until registry and local-reference cleanup complete.

The node-image endpoints resolve the requested result inside the explicit workflow storage context. For a captured result identity, record-relative image values resolve through that exact immutable record's declared assets; absolute external paths retain their declared location. Legacy unpinned results retain record-directory and workflow-storage-relative lookup. Existing image files are served with their inferred media type. `format=ome-tiff` preserves an existing OME-TIFF or converts a readable 2D, 3D, or 4D image into a bounded temporary OME-TIFF cache keyed by source path, modification time, and size. Missing results, cells, files, and unsupported conversions return explicit HTTP errors instead of silently selecting another workflow's data.

The backend uses an authenticated `multiprocessing.connection` Client/Listener channel to a helper running napari's Qt loop. The no-ID compatibility path lazily provisions the legacy Wetlands `napari` environment. An explicit registered ID instead uses that environment's persisted argv prefix without provisioning or package mutation, owns an independent process/lock/configuration file, and may pass `reader_id` separately as napari's `plugin=` argument. Success is returned only after the Qt-thread operation completes. A timeout or disconnect after dispatch reports an unknown outcome, invalidates the channel, and never replays the open automatically.

Fiji is a desktop-only, user-owned integration. BioImageFlow stores the selected `Fiji.app` installation directory, resolves the appropriate current or legacy launcher for the host platform, and passes the workflow-resolved image path as a separate process argument. BioImageFlow does not install, update, supervise, or shut down Fiji. The Fiji endpoint is forbidden in webapp mode and never accepts an arbitrary client-supplied filesystem path.

#### 2.4.9 Code Editor

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/editor/status` | Probe or launch embedded code-server; `workspace=true` with `launch=true` opens the managed multi-root workspace |
| `POST` | `/editor/open` | Open a file/folder in the user's external editor |
| `POST` | `/editor/open-tool` | Open the appropriate editor project and focus a tool source file |

The user specifies an external editor command in Settings (Section 3.12.1). The command may use `{workspace_path}` for the project folder and `{file_path}` for the focused file. For VS Code the recommended command is `code {workspace_path} --goto {file_path}`. If no external editor is configured, BioImageFlow uses embedded code-server when available and otherwise copies the relevant path to the clipboard with a toast.

`/editor/open-tool` is used by catalog tool rows and newly created tools.
Node source links use `/editor/open-node`, addressing the exact accepted node by workflow generation, draft or nested-session revision, and node identity.
Bound workflow-local sources are resolved directly from that binding, never from another same-named tool or a filename guessed from the class name.
A configured external editor retains the project selection: a workflow-local custom tool uses the current workspace, while an installed package tool uses the installed tool-store root when available and otherwise the source file's parent directory.
Newly created tools also use `/editor/open-tool`, with their tool name and workflow identity.
The embedded response returns the managed workspace URL without waiting for the opener extension; the panel loads the workbench first and then requests file focus, allowing the extension to activate without a circular startup wait.

Embedded code-server instead uses the generated project `<workspace>/.bioimageflow/BioImageFlow.code-workspace`. This multi-root workspace contains the active BioImageFlow workspace as `Workspace` and the installed tool store as `Installed Tool Packages`; the workspace is first, is the integrated-terminal working directory, and the tool-store tree is marked read-only through VS Code workspace settings. Both custom and package tool opens retain this project and focus only the selected source, so switching tool kinds must not reload the workbench or terminate its terminals. For an otherwise admitted installation, source navigation preserves a lexical tool-store symlink path when one can be identified so the file remains navigable under the package root. `EditorOpenResponse.project_path` identifies the generated `.code-workspace` file for these embedded opens.

Plain status probes remain side-effect free. `GET /editor/status?launch=true&workspace=true` lazily creates or refreshes the generated file atomically and returns a code-server URL with the encoded `workspace` query parameter. Generation failure returns an embedded-editor diagnostic without replacing an existing valid file. Changing the active BioImageFlow workspace changes the generated project and may reload the workbench; selecting another tool within the same active workspace does not.

`EditorStatus` also exposes the current embedded launch phase (`idle`, `preparing`, `installing_extensions`, `starting`, `waiting`, `ready`, or `failed`), a short message, launch start time, and optional current/total extension-installation steps. The launch request remains synchronous and protected by the existing launch lock; concurrent plain status probes report this shared snapshot without starting another launch. During launch, the Code Editor panel polls that side-effect-free status, shows an indeterminate progress bar, phase text, extension step count when available, and elapsed time after five seconds. An **Open Logger** action activates the existing Logger panel, where embedded-editor lifecycle records are streamed as ordinary framework logs. The Logger never opens automatically.
Startup reuses a matching managed code-server environment and checks the installed extension list before installing anything.
The editor runtime itself comes from the pinned upstream code-server release bundle for the host platform: environment provisioning downloads that bundle inside the managed environment, verifies its pinned SHA-256 before unpacking, and unpacked-bundle launches do not depend on a Conda build of code-server for the host. Windows ARM64 hosts use the upstream x64 Windows bundle, which they run through the system x64 emulation that also carries their x64 Pixi environments, because upstream publishes no native Windows ARM64 build; a host without that emulation reports the editor as unavailable instead of downloading an unrunnable bundle.
Failed managed-environment provisioning reports the failing step, command, exit code, and bounded redacted output tails in the launch message and embedded-editor diagnostic instead of an opaque exit summary.
Only missing extensions are installed; the bundled BioImageFlow integration is updated when its content digest changes or it is absent.
A successful integration installation records its digest in the managed environment, so reuse survives platform restarts.
Preparation messages describe environment, runtime-download, and extension checks; extension progress counts only the installations actually being performed.

#### 2.4.10 Dataset Management

Dataset management owns managed server-side files and a logical SQLite catalog of files and folders.
The docked Datasets panel and its transient single-file picker are specified in Section 3.14; [v2 Section 16](platform_specs_v2.md#16-files-source-selection) owns Files-source integration.
The endpoints remain available in both deployment modes, although ordinary desktop inputs use local filesystem references.

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/datasets` | List managed file records |
| `POST` | `/datasets/upload` | Upload multipart `files`, optionally into `folder_id` |
| `PATCH` | `/datasets/{dataset_id}` | Change `display_name` or logical `folder_id` |
| `DELETE` | `/datasets/{dataset_id}` | Compatibility single-file deletion |
| `GET` | `/datasets/folders` | List logical folders |
| `POST` | `/datasets/folders` | Create a named folder under optional `parent_id` |
| `PATCH` | `/datasets/folders/{folder_id}` | Rename or move a logical folder |
| `POST` | `/datasets/actions/resolve` | Resolve selected file/folder IDs to ordered file records |
| `POST` | `/datasets/actions/delete-preview` | Preview recursive selection counts and catalog revision |
| `POST` | `/datasets/actions/delete` | Confirm recursive deletion with `expected_revision` |

**Storage and catalog identity:** Physical uploads live directly under `{datasets_root}` as `{timestamp}_{sanitized_filename}.{ext}`, with collision disambiguation.
The root defaults to `<workspace>/datasets`, follows the active workspace, and may be overridden by deployment configuration; it is not a per-workflow setting.
The timestamp is compact UTC upload time, for example `20260421T143022`.
A file's `dataset_id` is a URL-safe base64 identity derived from its stored filename; a logical folder has its own stable ID.
Logical rename/move changes display names or catalog parent references without moving physical bytes or changing a file's ID or server path.
Folders are catalog groups, never server filesystem directories that can populate a Directory parameter.
Names are nonempty, exclude traversal/path separators and NUL, and must be unique among sibling files and folders ignoring case.
Folder moves reject self/descendant containment and invalid destination identities.

File records contain `id`, `original_filename`, `display_name`, `folder_id`, absolute server `path`, byte `size`, UTC `upload_date`, and informational `content_type`.
Folder records contain `id`, `name`, optional `parent_id`, and `created_at`.
The exact API shapes are defined in [`models/datasets.py`](backend/src/bioimageflow_server/models/datasets.py) and OpenAPI.
Selecting a file writes its server `path` into the addressed path parameter, never its display label or logical folder name.

**Selection resolution:** `{dataset_ids, folder_ids}` includes all descendants of each selected folder and deduplicates overlapping selections.
The backend resolves it to file records ordered by logical folder path, display name, and stable ID, with missing identities refused.
Canvas Files-source actions use those explicit paths and preserve the one-edit replacement contract in v2 Section 16.

**Deletion:** Preview returns `revision`, `dataset_count`, and `folder_count` for the recursive selection.
Confirmation submits the selected IDs and that `expected_revision`; any intervening catalog change returns HTTP 409 `catalog_conflict` before deletion.
The catalog writer transaction is acquired before revision, selection, sibling-name and publication decisions across cooperating store instances.
The response identifies deleted file/folder IDs and per-file errors.
Successful files are removed from storage and catalog, while failed files remain and prevent their containing folders from being deleted as empty.
The client refreshes the catalog and shows actionable partial failures rather than claiming the whole selection was deleted.
The compatibility `DELETE /datasets/{dataset_id}` returns 204 on success or 404 if absent; panel recursive deletion uses preview/confirmation instead.
Compatibility deletion requires the exact catalog ID and matching stored filename under a catalog writer transaction; an encoded contained filename or alternate encoding alone never authorizes deletion.
Unknown identities leave managed siblings, unrecognized files, and the catalog unchanged, while outside-root identities retain the 400 `path_traversal` refusal.
Containment inspection resolves links, but deletion unlinks only the selected catalog-owned entry, never a link's destination.
The writer transaction serializes cooperating catalog mutations; filesystem unlink and SQLite commit are not an atomic transaction, and commit failure cannot restore already removed bytes.
Deletion does not rewrite existing workflow parameters or invalidate prior computation records; a later run that needs a deleted input reports its absence.

**Uploads:** Multipart requests may contain multiple `files` parts and return `{uploaded: [...], errors: [{filename, error, detail}]}`.
Each successful record has the file fields above, and per-file failures do not conceal successful files in the same request.
Streaming writes use an exclusive unrecognized staging entry, handle short writes completely and refuse zero progress; listing and legacy reconciliation cannot publish incomplete uploads.
After successful close, a short writer transaction admits the destination folder, chooses a filename absent from both lexical storage entries and catalog reservations, and publishes complete bytes with their record and revision.
No streaming await holds the writer transaction; multi-query selection/preview reads use a consistent catalog snapshot.
Ordinary storage publication failures report per-file `storage_error`; multipart-close cleanup errors are logged without discarding already accepted file outcomes, while cancellation and programming faults remain distinct.
Cleanup removes an uncommitted published file only while its writer ownership remains held; a successful or ambiguous commit never authorizes subsequent file deletion.
Interrupted publication may leave complete unacknowledged legacy bytes that reconciliation recovers without the original logical folder metadata; this is not filesystem/SQLite atomic rollback or power-loss durability.
The cooperating-writer boundary does not guarantee atomic no-clobber against arbitrary external filesystem replacement.
The panel sends one file per request for per-file progress, cancel, and explicit retry.

**Upload validation:**

- **Filename safety:** Strip submitted directory components using both separator styles, reject NUL and empty/traversal basenames, protect Windows reserved stems, and preserve safe UTF-8 characters and spaces.
  Bound the final stored name to 255 bytes with room for the timestamp and collision suffix, truncating without splitting a UTF-8 character and preserving the extension where a valid bounded name is possible.
  The submitted original filename must remain metadata, separate from editable display naming and the safe stored basename.
  Current implementation derives `original_filename` from the sanitized basename, so exact original-name fidelity remains a documented implementation gap rather than a relaxed requirement.
- **File size limit:** The deployment default is **2 GB per file**.
  A running mid-stream byte counter enforces the authoritative cap, removes partial writes, and returns `file_too_large` in `errors[]`.
  `Content-Length` is only a coarse request guard: a declared body exceeding `max_upload_size * MAX_FILES_PER_REQUEST` (currently 32) receives HTTP 413 before body parsing, while a valid multi-file body may exceed one file's cap.
- **Containment:** Resolve every final upload/delete target and verify containment within the resolved dataset root; sanitization alone is not an authority.
  Reject traversal and symlink escape with an actionable `path_traversal` failure rather than accessing another server path.
- **Content type:** Informational, inferred from the extension; no content-type enforcement is promised.

The implemented baseline is single-user: managed catalogs are shared by canvases and browser windows in the active workspace.
Authentication and per-user dataset scoping remain the future [v3 proposal](platform_specs_v3.md#3-dataset-management--multi-user-extensions).

### 2.5 WebSocket API

A single WebSocket connection at `/ws` provides real-time updates. Messages are JSON with a `type` field. No authentication is required (server binds to localhost only).

**Server-to-client messages:**

| Type | Payload | Description |
|------|---------|-------------|
| `progress` | `{node_id, status, row, total_rows, task_current?, task_maximum?, timestamp, execution_id, workflow_id, result_key?, record_id?, draft_revision}` | Progress for one accepted execution context; row index/count and sub-row task units remain distinct |
| `node_state` | `{node_id, status, cached, execution_id, workflow_id, error?, traceback?, result_key?, record_id?, draft_revision}` | Node state change for one accepted execution context; status fields use the shared `NodeStatus` schema |
| `log` | `{level, message, node_id?, timestamp, execution_id?, workflow_id?, draft_revision?}` | BioImageFlow and Wetlands records attributable to an execution carry that execution's immutable context; non-execution tool, environment, thumbnail, and platform logs omit it and remain global |
| `execution_complete` | `{success, node_statuses: dict[str, NodeStatus], planned_node_ids, planned_node_names, execution_id, workflow_id, errors?: [...], draft_revision}` | Workflow execution finished with final statuses and the fixed executable plan for one accepted execution context |
| `status_snapshot` | `{state, last_result?, progress?, node_statuses, planned_node_ids, planned_node_names, execution_id?, workflow_id?, draft_revision?}` | Current or retained execution state and its fixed executable plan sent on connection and used for context-aware recovery |
| `workflow_draft_changed` | `{workflow_id, draft_revision, updated_by, updated_at, dirty_against_saved}` | A successful draft mutation for one path-derived workflow id |
| `tool_reload` | `{tool_name, tool_metadata}` | An editable tool reloaded or a controlled package operation updated its registry metadata. Includes the full updated tool schema. |
| `tool_removed` | `{tool_name}` | A previously registered tool source was removed or no longer loads. |
| `system_error` | `{code, detail, timestamp}` | A non-request system failure that belongs in the global error history. |
| `package_install` | `{package_name, status, detail?}` | Package installation progress (installing/complete/failed) |
| `environment_status` | `{env_name: str, status: "stopped" | "creating" | "updating" | "ready" | "running" | "failed"}` | Environment state change; ready content is separate from worker startup, and canceled manual requests still publish their physical operation's final state |
| `workflow_tree_changed` | `{action, workflow_id?, identity_generation?}` | Workflow or folder catalog mutation; clients refresh the workflow tree. Identity-specific mutations include the current workspace-durable generation so delayed events cannot target a newer same-ID incarnation, including after backend restart. |
| `active_workflow_changed` | `{workflow_id, updated_by}` | External active-workflow context changed; clients refresh matching workflow state without treating it as graph authority. |
| `ack` | `{ref: str}` | Acknowledges a client-to-server message (ref = the client's `message_id`) |

Progress, node-state, and completion messages always carry `execution_id`, `workflow_id`, and `draft_revision`. Execution-attributed log messages carry the same three fields together, while global log messages omit all three. An idle `status_snapshot` may omit execution context before any execution has been accepted.

`workflow_tree_changed` and `active_workflow_changed` are current runtime compatibility notifications emitted by the connection manager, but they are not yet members of the backend's typed `ServerMessage` union or generated frontend API types. Consumers must narrow them by their literal `type` until that schema gap is closed.

There is no `workflow_saved` WebSocket event in the MVP contract. Save/export flows reconcile through the draft and workflow REST APIs instead of relying on a separate save notification.

The frontend retains `workflow_draft_changed` notices by `workflow_id` instead of projecting every notice onto the active canvas. A matching root canvas without local semantic edits or pending draft writes auto-loads and applies the newer draft, including a strictly newer notice received during an earlier fetch or install. Accepted external graphs may remain dirty against the saved artifact, and recovery-only pending writes do not create a local conflict. A matching canvas with local semantic edits or pending draft writes keeps its graph and presents conflict resolution; inactive workflows retain their notice until tracked. Nested canvases do not auto-apply root-draft notices.

**Client-to-server messages:**

All client-to-server messages include an optional `message_id: str` field. When present, the server responds with an `ack` message (`{type: "ack", ref: "<message_id>"}`) once the request has been processed. This lets the frontend know when a state change (e.g., log subscription switch) has taken effect, avoiding races where stale messages from the previous state are mixed with new ones.

| Type | Payload | Description |
|------|---------|-------------|
| `subscribe_logs` | `{message_id?, node_id?: str, level?: str}` | Filter log stream. After the `ack`, all subsequent `log` messages match the new filter. |

**Reconnection strategy:** On WebSocket disconnect, the frontend uses exponential backoff (1s, 2s, 4s, 8s, max 30s) to reconnect. On reconnection, the frontend:
1. Receives a contextual `status_snapshot` from the backend immediately after WebSocket registration. The frontend projects the retained execution state only onto the matching canvas and accepted draft revision.
2. Fetches `GET /tools` to detect registry changes from controlled package operations, editable-source reloads or a server restart.
3. Re-sends `subscribe_logs` with the previous filter (the subscription is server-side state tied to the WebSocket connection and is lost on disconnect). The frontend stores the last subscription filter locally.

This ensures the frontend can reconstruct the correct state even if `node_state` messages were missed during disconnection. Log messages missed during disconnection are lost (logs are ephemeral; persistent logs are written to disk by the backend).

**WebSocket error messages:** If a client-to-server message has an invalid payload, the server responds with an error message instead of `ack`: `{type: "error", ref?: str, code: str, detail: str}`. When `ref` is set, it correlates to the client's `message_id`.

### 2.6 Thumbnail Generation

The server generates thumbnails on demand for image files referenced in output DataFrames. Thumbnail and Reveal actions use the same captured-record asset resolution as the node-image endpoints, so an owned asset is read from its immutable record and an absolute external path remains external. Thumbnails are cached under the workspace runtime directory.

- **Readers:** BioIO and the plugins installed in the managed thumbnail environment own format support, including TIFF/OME-TIFF, PNG, JPEG and directory-backed OME-Zarr; the platform does not replace BioIO with a TIFF-only decoding path.
- **Preview:** Select the middle time point and Z plane through BioIO's lazy array API before computing pixels, preserving channels and RGB(A) samples; readers with selective I/O may skip unused planes, while some formats still require whole-image decoding internally.
- **Size:** 128x128 pixels (configurable via query param)
- **Cache key:** SHA-256 of renderer version, absolute source path, nanosecond modification time, byte length, and requested size; directory stores additionally include descendant names, modification times and lengths so nested chunk changes invalidate the preview without hashing all pixel bytes.

ThumbnailManager reserves one service-owned job per fingerprint before environment setup or worker submission can yield.
All outstanding images share one startup operation and one bounded two-worker pool; matching ready Wetlands content is reused, and only its public provisioning operation owns replacement of a stale thumbnail recipe.
The response wait includes setup and is bounded independently of the shared job lifetime; abandoning a request or selecting another node does not cancel or resubmit shared work.
The PNG endpoint accepts a bounded `wait` of 0–20 seconds, defaulting to three seconds so initial installation progress becomes visible promptly.
Subsequent frontend requests wait up to 20 seconds on the same job and wake on completion; a fixed 250 ms inter-request delay avoids growing retry gaps after pixels are ready.
Thumbnail result and owned-asset resolution, directory fingerprint walks and cache reads run off the server event loop; latest DataFrame reads reuse their already-validated run-node relation within that operation, without caching it across requests or bypassing library record validation.
After setup, recheck the cache before worker submission, publish completed PNGs atomically, and discard a render if its source fingerprint changed during the job.
Shutdown stops admission, cancels the owned provisioning operation and render tasks, joins in-flight thread submissions and startup, and closes the resulting pool.
Terminal failures are memoized in bounded process-local state, while successful thumbnails remain in the disk cache.

The PNG endpoint returns X-Thumbnail-Status=pending|ready|failed|unavailable and X-Thumbnail-Environment=idle|starting|installing|ready|failed.
A ready header always accompanies rendered PNG bytes, including when generation completes at the response boundary.
Row-addressed responses use no-store because their URL does not encode the source fingerprint; the backend retains its disk cache.
Concurrent visible cells share one request and polling chain for the same inspection, captured result, source node/row/column and requested size; only their own display interest is canceled when they leave.
Successful PNG Blobs are reused within that accepted inspection, bounded to 128 cached entries and 32 MiB; cell-owned object URLs are revoked on departure independently of shared bytes.
This reuse is an inspection snapshot, not a claim that external files are immutable: explicit Refresh, accepted replacement results and owner/workspace replacement start a new inspection even when retained result IDs are unchanged.
Paging and mode changes retain the inspection; each new inspection revalidates sources through the server's fingerprinted cache.
No subscriber means no further polling; an already-issued wait and the backend-owned setup/render may finish, but cannot restart abandoned polling or update another inspection.
A pending job uses bounded completion waits without converting slow active setup into an unavailable result after a fixed retry count; terminal responses stop polling.
During actual environment mutation, Node Data shows a persistent preparation notice explaining that first-time setup may take several minutes; warm startup alone does not flash this notice.
The real TIFF browser acceptance must finish automatically after cold setup, without warming the endpoint through a separate API loop or reopening the workflow to repair an exhausted UI budget.
The managed-reader browser acceptance also checks RGB PNG/JPEG, middle-plane OME-TIFF and directory-backed OME-Zarr output automatically through Node Data.

### 2.7 Tool Hot-Reload

The backend watches editable custom and workflow-owned source directories for file changes (via `watchdog`, supplemented by limited content polling).
Installed package source files are read-only selections and their filesystem events do not authorize reload.
For an editable custom tool change:

1. Backend re-scans the changed tool module and updates the tool registry
2. Backend sends `tool_reload` WebSocket message with the full updated tool metadata (same format as `GET /tools` response)
3. Frontend updates the tool registry in Pinia and all nodes using the reloaded tool:
   - Input schema is updated (new/removed fields, changed types)
   - Parameters are re-validated against the new schema; incompatible values are flagged
   - Edges are re-validated; incompatible edges (removed output field, changed type) are flagged with a validation error
   - A temporary dismissable "tool updated" badge appears on affected nodes (small refresh icon, click to dismiss)
   - Executed nodes transition to "Out-of-date" (cache invalidated by code change)

Editable-source changes are applied automatically — no manual reload action required from the user.
Imported custom tools are unpacked as editable workspace files, and node source links open those exact files.
Run captures saved source bytes before compilation, independently of watcher timing; invalid edits block execution instead of using previous code.
Workflow-owned source changes emit `tool_source_changed` with affected tool names for canvas revalidation, without overwriting global catalog metadata.
Workflow-local source changes are detected through native file events and a periodic content check of registered editable tool directories, without scanning workflow results or datasets.
Reload reads current source bytes even for same-size saves with unchanged timestamps, and reload operations are serialized.
Each custom source is reloaded as a unit, including added, renamed, and removed classes; malformed edits report `tool_reload_failed` while preserving previous presentation metadata for repair and unrelated registry entries, without authorizing stale code for execution.
Implementation-only edits emit `tool_reload` even when the metadata is unchanged, and canvases retain this notification through field-focus deferral and execution locks.
An explicit installed-package refresh uses the generation lifecycle in Section 2.3, preserves an unaffected active version's class bindings and displayed metadata, and admits replacement bytes through the public library loader.
It preserves declared RECORD members, including pip-generated bytecode, rather than deleting installed cache files.
A failed replacement is reported as unavailable instead of restoring the retired class or module.

**Hot-reload during editing:** If the user is editing a parameter field (field has focus) when a `tool_reload` message arrives, the update is buffered until the field loses focus (blur event). This prevents data loss from mid-edit schema changes. If the field being edited was removed in the new schema, a warning toast is shown after blur: "Field '{name}' was removed by the tool update."

**Scientific identity:** Admitted executable source and ready runtime content always participate in cache identity through the library's public contracts; there is no development-mode setting or API argument.

**Tool reloads during execution:** Editable-source saves affect future compilations while an admitted execution retains its captured source.
Installed-generation retirement is refused while an admitted operation owns that generation; Python class references alone are not execution admission.
After retirement, a retained class reference cannot start a new operation and must be resolved through a freshly compiled workflow.

**Registry events during package installation:** The installer suppresses editable-source broadcasts while its operation is in progress and explicitly indexes the selected published package before returning.
It emits the selected tool metadata differences directly, without relying on installed-file or private staging events, then processes unrelated pending editable changes separately.
Uninstall likewise publishes selected removals or fallback-version metadata explicitly.
Refreshing package-index availability metadata does not authorize reloading installed code.

### 2.8 Startup and Shutdown

**Startup sequence:**
1. Load settings from configuration file
2. Scan tool store and load versioned packages to build tool registry
3. Start FastAPI server
4. Open pywebview window pointing to the server URL

**Shutdown sequence:**
1. Close new Run admission under the execution preparation gate, then request cancellation and await the accepted task with a bounded deadline; a timeout retains its task and cleanup owners, and later close calls may retry cleanup without reopening admission.
2. Stop background processing refresh and call public `shutdown_all` only on the already-created processing manager, retaining failed pools and grants for retry; terminate every running Napari viewer through the per-environment launcher pool (`NapariLauncher.shutdown_all`).
3. After copying durable projections and installing result bundles through public `WorkflowExecutionContext.export_result_bundle`, archive the verified bundle without hydrating an unused return, then close the supplied execution engine and release only that run's exact result groups; warm external pools may still retain physical grants.
   Retain every application-owned controller scope and failed cleanup owner, and retry its explicit close after worker grants have physically retired.
   Wait for local mapped readers to drain before deleting owned backing files; if the shutdown deadline expires or cleanup fails, report the exact scope as pending or failed and retain its backing rather than claim successful cleanup.
   Do not force-close live NumPy views, delete another owner’s files or perform global prefix-based shared-memory cleanup.
4. Save any pending settings changes
5. Stop FastAPI server

Unsaved workflow changes are not auto-saved to `workflow.json` on shutdown. Pending frontend edits are flushed to the backend draft when possible, and IndexedDB remains a local fallback for frontend/server failures.

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
|   Node Data   |  Logger  |  (tabbed bottom panel)    |
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
| Source DataFrameTool (`accepts_upstream: false`, e.g. `Files`, `Generate`) | None | `bif:v1:dataframe-output` |
| Merge / transform DataFrameTool (`accepts_upstream: true`, e.g. `CrossJoin`, `FilterRows`) | Positional (`bif:v1:dataframe-position:0`, `bif:v1:dataframe-position:1`, ..., auto-grow) | `bif:v1:dataframe-output` |
| ProcessingTool | None | `bif:v1:dataframe-output` |

**Node creation:**
- Drag a tool from the Tools Panel onto the canvas
- Or double-click a tool in the Tools Panel (creates the node at a default position)
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

**Node status reconciliation:** Status is a derived canvas projection and is never stored in `NodeState`. Client-side status is provisional for immediate feedback, while accepted validation and matching execution context are authoritative. The reconciliation rules are:

- **At rest (no execution):** A root canvas displays status from its last accepted validated draft response; a nested canvas uses its last accepted snapshot validation. During pending persistence, provisional statuses remain visible with a slightly desaturated treatment.
- **On a parameter command:** The owning canvas synchronously publishes the updated graph, projects the edited node as provisional `unexecuted`, and keeps other known statuses provisional until validation accepts the new snapshot.
- **During and after execution:** Contextual progress, `node_state`, status snapshots, and completion statuses override validation only for the root canvas whose workflow and accepted draft revision match that execution. Other canvases retain their own validation projection.

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

- **Positional edges** (`DataFrameEdge`): Connect a node's header DataFrame output pin (`bif:v1:dataframe-output`) to a DataFrameTool's header positional input pin (`bif:v1:dataframe-position:<index>`). Represent whole-DataFrame flow (upstream arguments to `merge_dataframes`). Rendered as **solid, neutral gray (#7A7A80), thicker (2.5px)** bezier curves with a small table badge, anchored on header-region pins.
- **Column reference edges** (`ColumnEdge`): Connect a body output pin (column name) to a body input pin (field name). Represent `ColumnRef` bindings for `ProcessingTool` inputs. A mapped target renders three parallel type-colored strands, while a collective target renders three strands that converge into one at the target. Workflow targets and missing or unknown tool metadata retain one standard strand.

**Cross-region rejection:** Header pins can only connect to header pins; body pins can only connect to body pins. Dragging a header output to a body input (or vice versa) is rejected client-side.

**Edge creation:**
- Drag from an output pin to an input pin (or vice versa).
- The frontend performs lightweight client-side validation (cycle detection, basic type check, cross-region rejection) for instant feedback.
- Invalid connections show a visual rejection (red flash + tooltip with reason).
- After creation, the full graph is queued through the owning canvas's validated draft or nested-snapshot persistence path. Request-local `PUT /graph` remains the compatibility fallback when no scoped canvas exists.

**Edge deletion:**
- Select an edge and press Delete.
- Or drag a connected input pin away to the empty canvas (disconnect).

**Edge visuals:**
- Edges are drawn as curved lines (bezier curves).
- Positional edges: solid, neutral gray (#7A7A80), 2.5px stroke width, with a table badge at the midpoint.
- Mapped column reference edges: three parallel solid, type-colored 2px strands, with the tooltip "Rows are processed independently."
- Collective column reference edges: three solid, type-colored 2px strands that converge into one at the target, with the tooltip "Rows are processed together."
- Workflow-input targets and targets with missing or unknown tool metadata: one standard solid, type-colored 2px strand.
- Selected edges are highlighted.

#### 3.3.3 Pins

Pins are the connection points on nodes. They are divided into two visual categories corresponding to the two edge types:

**Header pins (DataFrame-level)**

Header pins appear in the node header region and carry whole-DataFrame connections (positional edges).

- **Visual style:** Square (~14px), neutral gray fill (#7A7A80), distinct from the `"any"` wildcard color (#B0A060) and from body type-colored pins.
- **DataFrame output pin** (`bif:v1:dataframe-output`, right side): Present on nodes whose tool metadata has `dataframe_output === true` (currently all `ProcessingTool` and `DataFrameTool` nodes). Represents the node's full output DataFrame.
- **Positional input pins** (`bif:v1:dataframe-position:0`, `bif:v1:dataframe-position:1`, ..., left side): Present on DataFrameTool nodes with `accepts_upstream === true`. Numbered "1", "2", etc. A new pin appears dynamically when the last available pin is connected. **Auto-compact behavior:** when a positional edge is disconnected, higher-numbered pins shift down to fill the gap.
- Source-only DataFrameTools (`accepts_upstream === false`, e.g. `Files`, `Generate`) render no positional input pins. Edge-creation onto a positional handle of such a tool is rejected client-side. The backend additionally rejects any graph containing such an edge with a `source_tool_upstream` validation error.
- ProcessingTool nodes have no header input pins, but do have the `bif:v1:dataframe-output` header output pin so their full result DataFrame can feed a downstream `DataFrameTool` such as an aggregator.

**Body pins (column-level / field-level)**

Body pins appear in the node body region and carry per-column or per-field connections (column reference edges).

- **Visual style:** Round (~10px), type-colored (matching the data type color palette).
- **Output pins** (right side): One per output field or resolved column. Label shows the field/column name. Tooltip shows the type.
- **Input pins** (left side): Only for inputs where `connectable` is `"by_default"` or `"not_by_default"` (i.e. not `"never"`; declared by the tool author via `GUIMeta`). Fields without `GUIMeta` default to `"not_by_default"`. When a connectable input is connected, the corresponding parameter field in the Node Panel shows the source (e.g., `"cellpose_segmenter_1.mask"`) and the input widget is hidden.

For tools with `dynamic_outputs === true`, the body output pin set is computed by `POST /graph/nodes/{node_id}/output_schema` and refetched whenever a parameter on the node changes, or whenever a parameter on any upstream node with `dynamic_outputs === true` changes (the change is propagated downstream along positional edges). While the schema is unresolvable (`resolved: false`), the canvas renders a single placeholder pin styled with a dashed outline and disabled drag-out. Columns with `type: "any"` use a neutral wildcard pin color (#B0A060) and bypass type-compatibility checks at edge creation.

#### 3.3.4 Canvas Controls

- **Pan:** Middle-click drag, or scroll wheel + Shift
- **Zoom:** Scroll wheel, or pinch gesture; minimum zoom is 5% to support large workflows.
- **Fit view:** Button or shortcut to fit all nodes in view
- **Initial workflow view:** Center all nodes and fit them within the canvas, capped at 100% zoom so small workflows retain their normal node size.
- **Background:** Each canvas has a subtle dot grid that follows its viewport and uses a unique SVG-safe pattern identity independent of encoded workflow paths.
- **Initial empty canvas:** Adding the first node to a new empty workflow must not change the current viewport or zoom.
- **Undo/Redo:** Ctrl+Z / Ctrl+Shift+Z (client-side, instant). See [Section 4.6](#46-undoredo).

### 3.4 Tools Panel (Left Sidebar)

Displays the available tools in a two-tier layout: a minimalist tool list for everyday use, and a full management dialog for package/version administration.

**Panel layout (top to bottom):**

1. **Search bar** (with margins): Fuzzy search filtering by name, tags, categories, and keywords. This is not simple substring matching — it uses fuzzy matching so that partial or approximate terms still surface relevant results.
Search uses the current catalog name, display name, tags, categories and documentation words, with CamelCase/acronym identifier boundaries split before case normalization.
Every query token must match, and results retain the catalog order.
Exact partial matches are accepted directly; an otherwise unmatched token of 4–64 characters may match a whole indexed word with one insertion, deletion, substitution or adjacent transposition.
Short tokens and tokens longer than 64 characters retain exact partial matching only; the computed search index updates with catalog metadata and adds no separate persistent search authority.

2. **Tool list:** A flat, scrollable list of tools. Each row contains:

   | Element | Description |
   |---------|-------------|
   | **Tool display_name** | Primary label. A single click toggles that tool's documentation panel at the bottom of the Tools panel; a double-click creates a node at a default canvas position; the row is also draggable onto the canvas. |
   | **Env status dot** | Colored indicator for the tool's environment state: stopped (gray), creating or updating (yellow), running (green). |
   | **Category label** | Shown below the tool name. |
   | **Tags labels** | Shown below the tool name, next to category. |

   **Important:** Environments are per-tool, not per-package. Each tool row shows its own environment indicator and start/stop toggle, even if multiple tools share the same underlying environment.

Selecting a single tool node reveals its corresponding row in the Tools panel: expand its category, clear a search only if it hides the tool, scroll the row into view, and highlight it while selected.
Multi-selection, workflow-node selection, and clearing selection remove the highlight.
Only one catalog documentation panel is open at a time; clicking its active row again or its close action hides it.
Catalog secondary actions do not toggle documentation or create a node.

3. **"Manage tools" button** in the panel header: Opens a PrimeVue **Dialog** (modal) containing the full tool management interface (see below).

4. **"Create tool" button** at the bottom of the panel (with margins): Opens the tool creation workflow.

**Manage Tools Dialog:**

The dialog presents a hierarchical **TreeTable** with package rows (parents) and tool rows (children).
Its contents are independent of the Tools panel search field; opening the dialog always shows the complete package and tool inventory.

**Package rows (parent):**

| Element | Description |
|---------|-------------|
| **Package name** | The package identifier |
| **Categories** | Package-level categories |
| **Tags** | Package-level tags |
| **Version dropdown** | Lists all known versions (installed and available). Each version entry has an **Install/Uninstall toggle** — install button for uninstalled versions, uninstall button for installed ones. Shows spinning icon during installation. Installation can be interrupted (stop button). Custom workflow tools do not show package-version controls. |
| **"Use in workflow" button** | Sets the selected version as the active version for the current workflow. Only available for installed versions. When clicked, if the workflow already uses a different version of this package, a confirmation dialog is shown: "Changing {package} from {old_version} to {new_version} will mark {N} nodes as out-of-date. Their cached results will need re-execution. Continue?" |

Multiple versions of the same package can be installed simultaneously. Each workflow uses **one version per package**, selected via the "Use in workflow" button.
Portable nodes retain their explicit module/class/package/version binding through translation and compilation even when a same-named catalog tool has another active version or class kind.
Only explicit version rebind changes that package dependency; module/class-only references do not become package dependencies through catalog-name matching.

Below the TreeTable, the dialog includes an inline footer explicitly labelled **Install tool package**. The footer has one line of controls: a GitHub/GitLab repository URL text field, an **or** label, a **Select .zip archive** file picker, and an **Install** button. This footer installs unknown package sources that are not yet listed in the table; it must not be represented as a row-level action, search flow, or secondary modal. URL and archive inputs are mutually exclusive. In locked-down webapp mode this arbitrary package-source footer is hidden and the backend rejects it; approved package rows may still be installed through their version controls.

**Tool rows (children):**

| Element | Description |
|---------|-------------|
| **Tool name** | The tool's display name |
| **Info button** | Show detailed documentation and the managed environment location when the tool declares an environment |
| **Env status indicator** | Colored dot: stopped (gray) / creating (yellow) / running (green) |
| **Start/Stop toggle** | Start or stop the tool's Wetlands environment |
| **Create / recreate environment** | Labeled action that creates a missing environment or intentionally force-rebuilds the existing managed processing environment from the tool's declared recipe; all controls sharing that environment show the same busy state |

Each tool row shows the indicator and controls for its declared environment; tools sharing one environment share its lifecycle and busy state.
Manual controls serialize with other idle mutations and block Run until physical completion, including when the initiating request is canceled; an admitted Run or application shutdown refuses the manual operation without changing its environment.

### 3.5 Node Panel (Right Sidebar)

Title: Nodes.

Displays details and parameters for the currently selected node(s).

**Multi-selection:** When multiple nodes are selected, the Node Panel shows only bulk actions: Enable/Disable all, Delete all, Clear all. No parameter editing. Node Data shows the outputs of all selected nodes.

**Dynamic outputs source context:** Requests from a saved root or nested canvas carry the root workflow name alongside the graph so local tools resolve from their owning directory; downstream refreshes keep that same captured context.
A failed build, including a missing compiled workflow, returns an unresolved schema without an HTTP 500; an absent named workflow remains a 404.

**Dynamic outputs refresh:** When an input field changes on a node whose tool has `dynamic_outputs === true`, a debounced (200ms) call to `POST /graph/nodes/{node_id}/output_schema` refreshes the node's resolved output pins. The refresh also propagates downstream along positional edges to any visited node with `dynamic_outputs === true`.

**Single-node layout (top to bottom):**

#### 3.5.1 Header Section

- **Node name** (editable inline field). This is the human-readable display name (`NodeState.name`) — allows spaces and special characters. Must be unique within the workflow. The `NodeState.id` (URL-safe, used in API and edges) is auto-generated from the name on creation and remains stable when the name is renamed. Validated on blur — if duplicate, a red inline error is shown and the previous name is preserved until a valid name is entered.
- **Tool name** (read-only), with an **Open tool script** button that opens the selected node's executable source through the configured editor after the active canvas persistence barrier and identity/revision checks.
The button follows the same deployment-mode restrictions as source opening in Tools and is unavailable for workflow nodes.
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

DataFrame publication is separate from parameter editing.
For a DataFrame Tool that accepts upstream DataFrames, **Published DataFrame inputs → Publish DataFrame input** publishes successive positional inputs directly, each with an editable workflow input name, target position, and **Unpublish** action.
The number of published DataFrames is not limited by the tool's declared `Inputs` fields.
The recursive interface and positional compaction rules are defined in v2 Section 5.

Each input field from the tool's `Inputs` is rendered as a parameter row. Fields are grouped by category (if the tool defines categories via `GUIMeta.group`; otherwise all in one group).
Selected workflow nodes use the same parameter rows and value editors for their exposed field inputs, addressed by stable interface input ID.
The public interface owns the field name, schema and typed default; optional editor hints come from matching accepted target metadata, recursively through nested interfaces, and are retained across multiple targets only when they agree.
Unavailable hints leave a type-appropriate editor without creating an execution-blocking error or substituting another explicitly bound tool's metadata.
Connected rows remain visible with their source and disable value, Reset and None actions; connection display takes precedence over a retained null or local value.
Workflow Reset removes the instance override and displays the public default when present, otherwise an inherited/unset state without choosing one target's local default.
Explicit null remains distinct from an absent override.

**Each parameter row contains:**

| Element | Description |
|---------|-------------|
| **Pin toggle button** | Icon-only button placed **before** the label, only rendered when `connectable != "never"`. Two states with explicit tooltips: a two-arrows icon ("Add input pin") when the pin is hidden, a cross icon ("Remove input pin") when the pin is visible. Clicking toggles whether the canvas node shows an input pin for this field. `GUIMeta.connectable` (three-state: `"never" \| "not_by_default" \| "by_default"`) decides whether the button appears; the button itself decides whether the pin is shown. Current behaviour is to treat both `"not_by_default"` and `"by_default"` identically (pin visible) — a richer UX that hides pins by default for `"not_by_default"` fields is a separate plan. |
| **Label** | Field name (human-readable) |
| **Default button** | Resets a tool parameter to its declared default; for a workflow field, removes the instance binding and restores inheritance. |
| **None toggle** | Two-state button (only shown when `nullable` is `true` on the field schema). When active, the value is `None` and the input field is hidden. Independent of `required`: a required-and-nullable field still gets the toggle so the user can explicitly choose `None` as a valid value. |
| **Input field** | The actual value editor (hidden when connected or None). Type depends on the field annotation (see below). |
| **Help text** | Description from field metadata, shown with the parameter. |

**Input field types:**

| Field Type | Widget | GUIMeta influence |
|------------|--------|-------------------|
| `str` | Text input | -- |
| `int` | Number input (spinner) | `min`, `max`, `step` from GUIMeta |
| `float` | Number input or slider | `min`, `max`, `step` from GUIMeta. If all three are set, render as slider. |
| `bool` | Checkbox | -- |
| `Enum` or `Literal[...]` | Dropdown | -- |
| `Path` with `path_picker: "file"` | Text input + "Select File" button | In pywebview: native file dialog. In browser: Datasets panel single-file picker (Section 3.14). |
| `Path` with `path_picker: "folder"` | Text input + "Select Folder" button | In pywebview: native folder dialog. In browser: folder selection is not offered — the button is hidden and only manual text entry or drag-and-drop is available. |
| `Path` with `path_picker: "both"` | Text input + separate "Select File" and "Select Folder" buttons | In pywebview both native actions are shown. In browser only the Datasets panel file action is shown; folder paths can still be entered manually. |
| `Path` without `path_picker` | Backward-compatible generic path widget | Behaves as `"both"`; older tool schemas remain usable. |
| `ImageFile` | Text input + "Select File" button (filtered by format spec) | Same desktop/browser behavior as `Path` with `path_picker: "file"`. File-type filters apply to both the native dialog and the Datasets panel picker filter. |
| `ImageShared` | *Connection-only* (no manual input widget). Shows "Connect to upstream node" placeholder when unconnected. Unconnected required `ImageShared` fields produce a `missing_connection` validation error on the node. | Always `connectable != "never"`, not user-editable. |
| `tuple`, `list` | Inline list editor | -- |

When a connectable input is **connected** (pin has an edge), the input field is replaced by a read-only label showing the source: `"segmenter_1.mask"`.
Its pin remains visible and its hide action is disabled with an explanation until the edge is disconnected.
Workflow-field pin visibility follows the same transient presentation policy as ordinary pins; visibility changes do not change the workflow interface, bindings or edges.
Publication is a separate action: fields that accept constants may be exposed through a workflow interface even when they cannot accept a column connection.
Parameter focus, local parse errors and delayed file-picker results belong to the exact canvas registration, selected node and field; replacing that owner or locking mutation withdraws delayed edits.

#### 3.5.4 Output Fields

Each output field from `Outputs` is displayed with editable path templates for path-typed outputs **on `ProcessingTool` nodes only**:

- **Label:** Field name
- **Type badge:** Visual indicator of the type (ImageFile, int, etc.)
- **Path template editor:** *Only for `ProcessingTool` nodes.* For path-typed outputs (`Path`, `ImageFile`), a text input showing the current output path template (e.g., `{input_image.stem}_mask_{row_index}.png`). The user can edit this to customize output file naming. The template syntax follows the [library's output templating engine](bioimageflow/docs/source/specs.md#71-output-templating-engine). Available template variables are shown in a dropdown/autocomplete. Custom templates are stored in `NodeState.output_templates` (a dedicated dict, separate from `parameters`, to avoid mixing user-facing parameters with internal metadata). If a field has no entry in `output_templates`, the tool's default template is used.
- **Non-path outputs** (int, float, str, etc.) are shown read-only.
- **`DataFrameTool` outputs are column declarations, not file paths.** When `Outputs` is declared on a `DataFrameTool` (either explicit `IOModel` columns or a `Passthrough` marker), each field describes a column produced by the source/transform DataFrame, not a file written to disk. No path-template editor is shown — even for fields typed as `Path`/`ImageFile` — and `NodeState.output_templates` is not initialized for these nodes. Output templating is a `ProcessingTool`-only concept; [library Section 3.5](bioimageflow/docs/source/specs.md#35-dataframetool) defines `DataFrameTool` as returning DataFrames directly. The tool's `tool_type` field on `ToolMetadata` is the gate.

#### 3.5.4b Resource Configuration

For `ProcessingTool` nodes, the Node Panel includes a collapsible **Resources** section below the output fields. This section allows the user to configure execution resources for the node.

**Display:**

| Field | Widget | Description |
|-------|--------|-------------|
| **CPU** | Number spinner (min: 1) | Required CPU capacity |
| **GPU** | Number spinner (min: 0) | Required GPU capacity |
| **GPU Memory** | Text input (e.g., "8GB") | Minimum GPU memory required |
| **Memory** | Text input (e.g., "16GB") | Minimum worker memory required |
| **Max Concurrent** | Number spinner (min: 0) | Cap on active row tasks; 0 is unlimited only when the declaration permits it |

**Defaults:** Fields are pre-filled from the tool's `ResourceSpec` declaration (the tool author's minimum requirements). If the tool has no `ResourceSpec`, fields use the library defaults (1 CPU, 0 GPU, no declared memory requirement, unlimited concurrency).

**Semantics:** CPU, GPU, memory, and GPU-memory values are worker requirements used to select workers or request backend capacity, with the tool author's declaration as a minimum floor.
The GUI assists entry and backend/library validation enforces those floors against the actual materialized class, including for portable and source-bound nodes.
A same-named catalog class cannot reject or reinterpret bound overrides; actual DataFrame overrides are refused during validation and before publishing a portable archive.
Users may raise capacity requirements, but a nonzero maximum-concurrency override may only lower an existing nonzero declared cap; zero cannot remove that cap.
Actual available capacity, allocation, and enforcement belong to the execution backend or deployment site, so these portable requirements do not promise OS memory limits or a guaranteed allocation.
Requirements do not affect cache identity, and sequential/parallel scheduling remains workflow configuration ([v2 Sections 2 and 8](platform_specs_v2.md#2-canonical-graph-document)).

**Storage:** Resource overrides are stored in `NodeState.resources` — a dedicated dict separate from `parameters` to avoid namespace pollution. Keys are `cpu`, `gpu`, `gpu_memory`, `memory`, `max_concurrent`. The backend uses these to construct a `ResourceSpec` for the engine. If `resources` is empty, the tool's declared `ResourceSpec` is used as-is.
Missing or null resource fields inherit the declaration; **Reset all** clears explicit overrides and is disabled when none are present, including a canonical object whose fields are all null.
A numeric zero remains an explicit override and is subject to the declaration's normal validation.

**GPU badge:** Nodes requiring GPU (either from tool declaration or user override) show a small GPU badge (GPU icon) on the node header in the canvas.

#### 3.5.5 Node Output Section

A collapsible section at the bottom of the Node Panel that displays execution output scoped to the selected node.

- **Logs:** The frontend maintains a per-node log buffer in memory (from WebSocket `log` messages with `node_id` field). When a node is selected, this section shows only that node's logs — a filtered view of the same data as the Logger Panel.
- **Error display:** For failed nodes, the error message and traceback are displayed prominently at the top of this section with a red background. The `node_state` WebSocket message for failed nodes includes `error` and `traceback` fields (see `NodeStatus` model in Section 2.4.3).
- **Level filter buttons:** DEBUG / INFO / WARNING / ERROR, defaulting to INFO+.
- Logs are kept in memory for the duration of the session and cleared on new execution.

#### 3.5.6 Documentation

A collapsible section at the bottom of the Node Panel that shows the tool's documentation (from `tool.documentation`). **Open by default** so users see the docs without extra interaction. The toggle is a chevron icon rendered **before** the "Documentation" label (right-pointing when collapsed, down-pointing when expanded).

### 3.6 Node Data (Bottom Panel, Tab 1)

The "No output data for node" message is an informational empty state, styled blue in individual and consolidated tables.
HTTP 409 result conflicts use the existing ErrorResponse envelope with error=result_pending for transient publication and error=result_unavailable for rejected identity, metadata, format or record validation.
Individual and consolidated tables use bounded retries only for result_pending; permanent and unclassified conflicts stop loading and show their diagnostic immediately, without automatic polling.
Unsupported saved cache formats retain their files and explain that compatible output must be regenerated; opening a table never rewrites or discards those results.

Displays the output DataFrames of selected nodes in a tabular view.

**Behavior:**
- When one or more nodes are selected, the table shows their outputs.
- When no nodes are selected, the table shows the terminal node(s) outputs.
- If selected nodes have no output yet, a placeholder message is shown.
- **Disabled nodes:** If a disabled node was previously executed, Node Data shows its cached data with a dimmed appearance and a banner: "This node is disabled." If a disabled node has no cached data, the standard placeholder is shown. When no nodes are selected and all terminal nodes are disabled, the placeholder reads: "All terminal nodes are disabled."

**Layout — vertical flex column:**

The panel header, column headers, and paginator remain outside the vertically scrolling row viewport.
The row viewport consumes the remaining panel height so navigation remains visible even when the docked panel is short.

When multiple nodes are selected, their DataFrames are displayed in a **vertical flex column layout** (stacked vertically, not in separate tabs). Each DataFrame has a header showing the node name and its own independently visible pagination controls. Each stacked card is bounded by the available panel viewport, and its rows scroll internally before the outer panel moves to the next card.

**Display limit:** When more than 5 nodes are selected, only the first 5 DataFrames are shown, with a "Show all ({N})" toggle to display the rest.

**Single node selected:** Show that node's output DataFrame only.

Focusing an already visible Node Data dock preserves its projection and the active cell gesture; revealing the dock after it was hidden refreshes the projection.

**Table features:**
- **Column types:** Columns are annotated with their type. Image columns show special rendering.
- **Column sizing:** Individual and merged tables initially size columns from the displayed header, reserved sort/filter controls, and a bounded sample of up to 50 loaded rows; image/path cells receive a stable preview/action allowance rather than waiting for thumbnails. Automatic widths are bounded to 120–480 CSS pixels and measured only after fonts are ready and the table is visible. Narrow tables do not stretch to fill the panel; wide tables scroll horizontally. Paging, sorting, filtering, panel resizing, and thumbnail loading do not continually resize established columns. Header text truncates with a full-text tooltip while sort/filter controls remain accessible.
- **Manual column sizing:** Every header has a visible, theme-aware separator and a wider drag target. Dragging changes only that column within 120–1200 CSS pixels; focused separators also support Left/Right in 10-pixel steps. Double-click or Enter auto-sizes the column to current content. **Reset column widths** clears manual overrides for that table and recalculates automatic widths; there are no separate Fit or Auto modes. Only completed user resizes are persisted, scoped to workflow, table/source identities, and column ID/type; canceled gestures and hidden DOM measurements are never saved. Legacy automatic width snapshots are ignored.
- **Browsing mode:** Preferences → Display chooses Paginated (the default) or Continuous scrolling for Node Data; there is no second table-local mode toggle.
- **Virtual rows:** Both modes mount only a visible row window with a small buffer in individual, merged and stacked tables; hidden docks/cards do not initiate image work. Image and ordinary text/path rows retain their own bounded geometry, and scrolling uses source row identities independently of virtual positions. Width sampling uses actual loaded rows, never a total-length placeholder collection.
- **Pagination:** Large DataFrames are paginated server-side. The application default is 250 rows and the user may choose 25, 50, 100, 250, or 500 in Preferences → Display. Each table may temporarily choose another page size.
- **Continuous scrolling:** The same table viewport requests bounded server-side blocks near its visible range, deduplicates in-flight blocks, limits concurrent reads and evicts distant row payloads. Scrolling upward reloads evicted blocks against the same captured source identities; unloaded placeholders expose no artifact actions. Permanent result errors require an explicit retry or refresh and never loop automatically. Older unpinned results remain paginated with an explanation rather than claiming exact continuous snapshots.
- **Snapshot and refresh:** A captured source vector may legitimately contain results from different runs; every source identity stays fixed across additional blocks. Sorting/filtering and changing browsing mode preserve the selected results and reset the viewport/window. Refresh and accepted execution updates replace the inspection atomically; late prior responses cannot append to the new window. Mode changes do not execute or modify the graph.
- **Direct navigation:** The paginator provides first, previous, next, and last controls; a 1-based page input applied on Enter or blur; total pages; the visible row range; and filtered and unfiltered totals. Page input is clamped to the valid range.
- **Sorting:** A column header cycles visibly through unsorted, ascending, descending, and unsorted. Sorting is server-side and resets pagination to the first page.
- **Filtering:** Column-header popovers provide type-appropriate text, numeric, boolean, and empty-value operators. Filters combine with AND semantics, run server-side before sorting and pagination, appear as removable chips, and are applied to CSV export.
- **Image cells:** For columns typed as `ImageFile` or `ImageShared`:
  - Reserve a 96×96 thumbnail area, but request `/nodes/{node_id}/thumbnail?row=0&col=mask` only after the row intersects the visible table viewport.
  - **Open in Napari** button: Opens in Napari (`POST /napari/open`). Ctrl+Click clears existing layers.
  - **Open in Fiji** button: Opens the selected result image in the user-configured Fiji installation (`POST /fiji/open`). Before configuration, the same action opens Preferences → Image Viewers.
  - **Reveal in file browser** button.
- **Scalar cells:** Show the value directly.
- **Path cells (non-image):** Preserve left-to-right path order while right-aligning and truncating from the beginning so the filename and final directories remain visible. The full path remains available through its tooltip, inspector, and copy action. Show the filename with two buttons:
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
- **Selection and copying:** Users can drag to select text across log rows and copy the native selection with the platform keyboard shortcut. **Copy logs** copies every entry currently shown by the level, node, and search filters in display order without changing stored logs or filters. The plain-text output has one record per entry with the displayed timestamp, full level, node label when present, and complete message; embedded message newlines are preserved. The button is disabled when no entries are visible and reports clipboard success or failure.

### 3.8 Workflows Panel

Concurrent startup consumers share a workflow-tree HTTP request only while it is pending under the same catalog authority and structural generation.
Successful metadata/catalog writes and deliberate post-mutation, workspace, migration or reconnect refreshes invalidate that pending authority; a completed response is never a persistent catalog cache.
Tree and flat-list endpoints retain separate response contracts, bounded stale retries and request-owned loading/error state, so an older response or finalizer cannot undo accepted metadata or clear a newer refresh.
Backend catalog and format discovery use a fresh folder walk that stops at each workflow.json boundary before inspecting workflow-owned results, sources or private state.
One operation may reuse its own discovered paths for format checks and tree assembly; the next operation sees current filesystem content without a persistent catalog cache.

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
      tools/
    segmentation/
      nuclei/
        workflow.json
        tools/
```

Each `workflow.json` stores a `WorkflowDocument` envelope containing the canonical recursive graph, workspace metadata, artifact hash, optional Python-authoring provenance, and owned local-source IDs.
Layout and GUI node state belong directly to that graph; library translation happens in memory.
Custom tools created from the platform GUI live under `workspace/workflows/<workflow_id>/tools/`, and exported workflow archives carry the owned source files they use.
A workflow directory may contain other local files, but these directories are not shown as user folders in the Workflows panel.

Only directories containing `workflow.json` are platform workflows. Stray JSON
files under `workspace/workflows/` are ordinary files and are not listed,
opened, or treated as workflow id collisions.

**Panel layout:**

- **Toolbar:** New workflow, New folder, Save, Duplicate, Import, Export, Edit selected item, Delete selected item. Editing a selected workflow changes its display name; editing a selected folder renames that folder.
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

An explicit workflow or folder selection owns the panel details and actions against passive metadata updates and late automatic startup loading or activation.
A later deliberate Open, accepted Create, Save As, Duplicate or Import presentation, or actual root/nested canvas activation follows that workflow, including same-name activation.
Startup initializes selection only when no newer Browse or deliberate presentation owns it; ordinary Save, dependency refresh, rebind and structural metadata remapping do not acquire presentation intent.

Clicking a row selects it. Double-clicking a workflow, pressing Enter on a selected workflow, or using the Open action opens it in a root canvas tab or activates the existing tab already presenting that workflow. Dragging from anywhere on a workflow row onto a folder moves the workflow within the tree, and dragging that same row onto the canvas creates a workflow node containing an executable snapshot. Drops that would make a workflow contain itself directly or indirectly are rejected. Dragging a folder onto another folder moves the full folder subtree, including child folders and workflows.

**Actions:**
- **New workflow:** Opens a creation dialog for a free-form display name and an optional multiline description. The panel derives and previews the filesystem id, and a selected tree folder supplies the parent folder. The current panel does not expose editable workflow id or path fields; explicit ids and paths remain API capabilities. On id conflict, the server suggests an alternative while retaining the entered display name; editing that name clears the suggestion and derives a new id.
- **New folder:** Creates a folder under the selected folder or the tree root.
- **Open workflow:** Opens the selected saved workflow in its canonical `workflow:<id>` root canvas tab or activates that existing tab. Startup resolution uses this same creation, persistence, activation, placement, and close lifecycle after its temporary non-canvas loading placeholder resolves.
  An accepted named Open supersedes pending startup presentation before loading begins; late startup reads cannot mount or reactivate a competing root, change the selected workflow, clear its dirty state, or replace its accepted draft projection.
  The winning Open retains newer recovery for its own workflow with the durable draft revision as its CAS base; unrelated recovery remains separate, and a deliberate later Open still activates an existing root tab.
- **Edit workflow:** The current panel edits a workflow's display name and description. These metadata updates preserve the path-derived workflow `id`. Dragging a workflow row to a folder is the current panel control for moving it; the resulting path and `id` change together, and any existing embedded draft identity follows that route. Editable slug and path-id fields remain API capabilities rather than current panel controls.
- **Save:** Saves current workflow state including GUI state (Ctrl+S). The frontend flushes the current graph to the backend draft, verifies the draft revision, then saves/promotes that draft through the workflow save path. Saving always succeeds regardless of validation errors. Uses atomic writes (write to a temporary file, then rename) to prevent corruption on crashes or disk-full errors.
- **Save as / Duplicate:** Save the current draft under a new id; duplicate saved workflows without copying stale unsaved state unless the current draft is explicitly saved as the new workflow.
- **Import / Export:** Uses the BioImageFlow library import/export API. The
  platform does not reimplement the library archive format. Export saves/promotes
  a dirty draft first so the archive matches the current editable graph.
  After an imported or explicitly opened saved workflow is accepted in its root canvas, desktop mode presents persistent, dismissible viewing guidance for unmet requirements, unknown metadata, and check failures without blocking Run or installing anything.
  Pending-only checks remain silent so a covered result never flashes a temporary banner.
  Saved inspection uses the normal graph compiler and source/store authority, without planning, provisioning or execution; unresolved metadata preserves its loading diagnostics.
  The summary separates unknown tool/output metadata from known viewer requirements needing setup, and Manage/attach environments is available only when a known viewer requirement group needs attention.
  Readiness requests and all report, error, toast, and setup-prefill effects belong to the latest presentation intent, exact canvas registration, active owning workflow, and its local and durable server identity generations; superseded or refused presentations cannot overwrite the accepted workflow's guidance.
- **Delete:** Delete with confirmation bound to the selected workflow identity generation and, when mounted, its exact canvas-session registration. The frontend and backend both reject a confirmation if that target was removed, remounted, or replaced by a newer same-ID incarnation while the dialog or a freshness flush was pending. The backend serializes deletion with saved workflow, draft, move, and retained-snapshot mutations, then removes the workflow directory, its draft metadata, retained nested snapshots, and configured workflow output/cache directory. The frontend keeps an open target mounted and lifecycle-gated until server success, then closes that exact root and its nested canvases, clears their local recovery and presentation state, and activates the most recently active remaining root tab. If no root tab remains, it opens an existing saved workflow in stable tree order; if no workflow exists, it shows a non-persistent New/Open empty state. A pre-commit failure leaves the target mounted. If local recovery cleanup fails after server deletion has committed, the deleted target stays closed and the UI reports a cleanup warning instead of offering a stale retry. A remote deletion follows the same convergence path, and server identity generations prevent a delayed event or response from deleting or reopening a newer same-ID incarnation. Folder deletion uses the platform dialog system. For non-empty folders, the dialog offers three choices: delete all child workflows/folders, move direct children up to the deleted folder's parent, or cancel.

### 3.9 Execution Panel (Menu / Toolbar)

**Buttons:**
- **Run Workflow**: Execute all enabled nodes that are Unexecuted or Out-of-date. Shows a confirmation dialog: "The following out-of-date nodes will be re-executed, replacing their previous outputs: [list]. Continue?" Pending validation or draft persistence is a command barrier rather than a disabled state: Run flushes the owning canvas, checks draft revision freshness, waits for accepted validation, and then submits the workflow ID and accepted revision. If validation fails after the flush, execution is aborted and a toast is shown: "Validation errors found — fix them before running."
- **Run Selected:** Always visible as a separate toolbar button, disabled when no nodes are selected or execution is unavailable; it does not require opening the Run dropdown. Run only the currently selected nodes (and all their out-of-date or unexecuted dependencies). Sends `POST /execution/run` with `nodes` set to the selected stable node IDs. Also available via right-click context menu on selected nodes. Same debounce-flush behavior as Run Workflow.
- **Stop:** Cancel the current execution. Visible only during execution.

**During attached local execution — Non-Modal Execution Banner:**

Instead of a blocking modal, the GUI shows a **persistent execution banner** at the top of the canvas. The user can inspect completed nodes, view Node Data, and browse the Logger Panel while execution is in progress. Graph **mutations** are locked (node/edge creation, deletion, parameter changes, drag-to-reorder), but read-only inspection is allowed.

- **Banner content:** "Executing workflow..." and one progress bar for completed or cached executable tool nodes out of the fixed run plan. Text identifies the completed count, a currently running node, and its actual row position or completed row count when available; separate task progress is identified as task progress rather than rows. The count uses the accepted run identity and does not change when the user switches canvases. Parallel nodes can run at once, so the count says "nodes complete" rather than implying one sequential current-node ordinal. The bar shows 100% on successful completion and keeps the achieved partial count on failure or stop. **Stop** remains available in the execution controls.
- **Canvas overlay:** Running nodes show a pulsing blue border. Completed nodes turn green in real-time.
- **Locked interactions during execution:** Adding/removing nodes or edges, changing parameters, enable/disable toggle, clear outputs, save workflow, undo/redo. These actions are grayed out with a tooltip: "Locked during execution."
- **Allowed interactions during execution:** Selecting nodes, viewing the Node Panel (read-only), browsing Node Data (completed nodes show their output), scrolling the Logger Panel, panning/zooming the canvas, opening images in Napari.
- **Stop button:** Cancels execution. The banner updates to "Execution stopped" and disappears after 3 seconds (or on click).
- **On completion:** The banner shows "Execution complete" (green) or "Execution failed" (red, with error summary) and disappears after 5 seconds (or on click). On failure, the failed node is auto-selected so its error is visible in the Node Panel.
- **Safety guarantee:** Since all graph mutations are locked, the running workflow cannot be affected by user actions. The server also rejects graph validation, draft mutations, workflow mutations, and cache clearing while an execution is starting or running with HTTP 423 Locked. Ordinary admitted mutations serialize with one another and exclude Run; they are not themselves reported as a running execution.

### 3.10 Image Viewer

Image-valued Node Data cells expose both the managed desktop viewer and a browser viewer action.

**Avivator:** The browser action checks the selected cell's workflow-scoped OME-TIFF offsets response through the same-origin backend API before opening the external Avivator application in a Dockview iframe using the absolute node-image URL with `format=ome-tiff`. A failed or malformed offsets response leaves the action available, shows an error, and opens no panel; clicking the action again retries the backend read. An in-flight read cannot open a different cell if its result identity changes before completion. The panel can be activated, closed, or moved into a separate window. This current integration does not provide the embedded Viv component or OME-Zarr static-tree serving proposed by v3.

**Napari:** The backend uses a legacy `NapariLauncher` plus a registered-environment launcher pool that:

1. Preserves lazy Wetlands provisioning only for the no-ID compatibility path
2. Launches external explicit registrations directly from their frozen argv prefix, while recipe-created managed registrations use the public Wetlands managed-environment `spawn` API; adopted legacy Wetlands 1 workspaces may fall back to their persisted interpreter
3. Gives every registered environment a UUID-scoped `NAPARI_CONFIG` settings YAML file and verifies napari resolved that public configuration path before viewer startup
4. Communicates through authenticated local IPC and acknowledges opens only after their Qt-thread viewer operation completes
5. Reports reader failures as typed open errors and ambiguous post-dispatch completion as unknown without replay
6. Coordinates independently locked managed create/copy/retry/remove operations without replacing a working generation in place

**Interactions:**
- **Open in Napari:** The primary action resolves the exact retained cell and uses the compatible environment selected by structural-output favorite, first matching filename rule, global default, then another qualifying environment.
- **Choose environment:** The adjacent menu lists every compatible, incompatible, unknown, or unavailable registered environment with its backend explanation; choosing a runnable row opens once without changing preferences.
- **Favorite:** One keyboard-accessible exclusive star per structural output identity applies across rows and future results; choosing the filled star removes it, and favorite mutations never launch a viewer.
- **Clear layers, then open:** Explicitly clears layers only in the chosen environment before opening.
- Changing a selected artifact withdraws its previous resolved actions until the replacement resolves; deferred chooser work cannot combine the replacement artifact or preference key with the previous environment or reader, and cannot dispatch after its chooser is disposed.
- An already dispatched open or favorite remains bound to its original capture; late completion cannot retarget or replay that action or overwrite a replacement chooser.
- Napari is launched lazily on first use, while **Launch empty viewer** starts or focuses one addressed environment without dispatching an empty open request.

**Fiji:** Fiji is installed separately by the user. In desktop mode, the Node Data image-cell action sends the selected node, row, column, and workflow context to `POST /fiji/open`; the backend resolves the authoritative result path and launches the configured Fiji installation with that image. If Fiji is not configured, the action opens Preferences → Image Viewers. If the saved installation has moved or become invalid, the action returns to configuration mode. Fiji controls reuse of an existing Fiji process.

### 3.11 Error Handling

Three levels of error display:

**Validation errors:** Inline red border on the affected parameter field + tooltip with the error message. For invalid edges: visual rejection (red flash) + toast notification with reason.

**Execution errors:** Failed nodes turn red. The Node Panel's Output section (Section 3.5.5) shows the error message and traceback. The error is also logged in the Logger Panel. The GUI shows: "Node failed on row {N} of {total}. All results for this node were discarded. Fix the issue and re-run."

**System errors:** A global error indicator (icon in the top bar). The indicator is visible whenever one or more errors have occurred. Clicking it opens a sliding panel showing the error history. Each error entry includes timestamp, type, and message, and can be dismissed individually (cross button). Auto-dismiss for transient WebSocket reconnections.

All user-facing error surfaces preserve specific backend error detail ahead of generic HTTP-client status text, render structured validation locations in readable form, and keep their text selectable for copying even inside canvas, draggable panel, toast, and dialog regions.

### 3.12 Settings Panel

A dedicated panel or modal for application configuration. Settings are persisted as a JSON file at `~/.bioimageflow/settings.json`. Defaults are applied for any missing keys.

#### 3.12.1 External Editor Settings

- **External editor command:** Text field with `code {workspace_path} --goto {file_path}` as the recommended VS Code command.
  `{workspace_path}` identifies the editor project and `{file_path}` the focused file according to Section 2.4.9.
  If empty, the embedded managed multi-root code-server project is used when available, with clipboard/toast fallback if unavailable.

#### 3.12.2 Image Viewers

- **Napari environments:** Lists named external Conda/virtual environments and platform-managed generations with detected interpreter, napari, Qt, inventory, probe, launcher, and setup state.
- **Environment actions:** Register or locate an external installation; create, retry, cancel, or remove a managed generation; refresh inventory; rename; forget; or launch that addressed environment empty. Recipe-based copy remains an API operation but is not offered in Settings.
- **Selection preferences:** Chooses one global default and manages revision-checked, first-match filename rules with extension shortcuts, ordering, and catch-all diagnostics. An optional reader plugin ID selects a reader for matching files; package requirements remain separate.
- **Viewing readiness:** The workflow guidance passively evaluates imported or explicitly opened saved requirements and offers captured setup from one normalized requirement group without installing or launching anything; Settings does not show a per-output readiness report.
  Passive refresh preserves edited or submitting creation forms; explicit selection transfers only one captured set, and late creation completion or failure cannot consume a newer same-ID prefill or overwrite a newer transferred form.
  A constrained napari set displays its constraint and requires an explicit advanced exact-version choice instead of reusing an unrelated prior or default recipe; coverage is determined from the installed inventory.
- **Missing installations and inventory drift:** Missing external registrations offer Locate followed by a fresh probe.
  Replacing an interpreter at the recorded path or changing packages uses inventory Refresh; compatibility reflects observed Python/napari/Qt/distribution metadata rather than a persisted executable fingerprint.
  Adopted legacy entries can be forgotten durably and re-added as external installations.
- **Fiji installation:** Editable directory field with Browse and Clear actions. The selected directory must be a usable `Fiji.app` installation for the current desktop platform before it is saved.
- **Download Fiji:** Links to the official Fiji downloads page. Fiji installation and updates remain the user's responsibility.
- The section and Fiji result action are hidden in webapp mode.

#### 3.12.3 Execution

- **Execution backend:** Read-only summary of the effective backend (`Automatic`, `Wetlands`, or `Direct`) when supplied by the runtime settings contract.
- **Scheduling:** Read-only summary of `Sequential` or `Parallel` for new workflows. This setting is copied into the new workflow's `config.execution`; changing it does not alter existing workflows.

#### 3.12.4 Display

- **Node Data browsing mode:** Paginated or Continuous scrolling, initially Paginated, applied to existing and new root/nested inspections. Changing it preserves selection, upstream levels, sort/filter and the selected results, while resetting the row viewport to the beginning.
- **Node Data rows per page:** Select 25, 50, 100, 250, or 500 as the default for newly inspected tables. The initial default is 250, and a table-local page-size change does not rewrite this preference.
  This preference applies to paginated mode; continuous fetch-block size is an internal bounded implementation choice.

#### 3.12.5 Storage

- **Workspace path:** read-only display with a native Change action in desktop pywebview mode. The GUI persists the selected path through `PATCH /settings`; workspace-derived workflow, draft and result stores follow that setting without migrating existing content. Explicitly configured store roots retain their own authority. The separate `PATCH /workspace` endpoint changes its active path override in memory and does not migrate or create directories.
- **Latest output view:** Shows the effective symbolic-link or portable-pointer publication mode, any warning, and a Retest action.
  Named workflow results remain under `<workflow-directory>/results`, with per-node latest publication distinct from a pinned successful-run bundle ([v2 Section 12](platform_specs_v2.md#12-persistence-drafts-and-lifecycle)); this is not a configurable output-folder control.
- **Tool store path:** read-only resolved path display (default: `~/.bioimageflow/tool_packages/`, with environment overrides applied).

#### 3.12.6 OMERO

OMERO data access is supplied by dedicated tool packages; the platform UI manages credentials but does not browse or broker OMERO data itself.

The OMERO tab lists named server instances with host, port, username, password status, and Add, Save, Duplicate, and Remove actions. The display name defaults to `{host}:{username}` and must be unique. Passwords are submitted only when explicitly saved, stored through the operating-system keyring under service `bioimageflow-omero` and username `{host}:{port}:{username}`, omitted from settings JSON, and represented by `password_stored` in API responses. Named instances with the same normalized host, port and username share one credential; the last explicitly submitted password wins.
Removing an instance asks for confirmation and deletes that shared credential only when no retained instance still references it.

### 3.13 Drag and Drop (File Import)

Users can drag and drop files (images, CSVs, etc.) onto the application window.

- **In pywebview mode.** The drop event exposes local filesystem paths. Dropping files creates a "Files" DataFrameTool source node on the canvas, pre-configured with the dropped paths.
- **In browser mode.** The drop event exposes `File` objects rather than server paths; it activates the Datasets panel and queues the dropped files for upload.
  Successfully uploaded managed datasets can then populate a Files source through the panel actions and [v2 Section 16](platform_specs_v2.md#16-files-source-selection).

### 3.14 Datasets Panel

The docked **Datasets** panel is the normal managed-file browser in webapp mode and is absent from the desktop dock and View menu.
It owns catalog browsing and upload presentation, while the backend catalog in Section 2.4.10 owns file/folder identity and mutations.

The panel provides:

- **Search:** Filters file display/original names and logical folder paths, retaining matching ancestors and expanding matching paths.
- **Tree:** Logical folders and managed files with hierarchical checkboxes, full/partial selection states, and **Unselect all**.
  Folder selection includes its descendants, and deselecting a descendant clears the ancestor's complete-selection state.
- **Editing:** Add folder, rename one selected file/folder, and drag selected entries to another logical folder or the root.
  Moves reject containment cycles and name conflicts and refresh the catalog after success or failure.
- **Upload files:** Uses the browser file picker or dropped files, queues one request per file, shows per-file and batch progress, and offers cancel, retry for failed/cancelled entries, dismiss error, and clear completed actions.
  The frontend may reject files over the cached cap plus 10% headroom; the streamed backend cap remains authoritative.
- **Delete:** Previews the selected recursive file/folder counts and submits only after explicit confirmation with that catalog revision.
  A stale revision is refused as `catalog_conflict`; partial file failures remain actionable and undeleted descendants keep their folders.
- **Canvas actions:** **Create Files node**, **Set files on “node name”** for one selected Files node, and dataset-tree drag to the canvas use selected managed paths.
  Files-source behavior and one-edit replacement of Directory/Files are defined in [v2 Section 16](platform_specs_v2.md#16-files-source-selection).

The selection summary has its own footer row, with actions below it that wrap with visible spacing in narrow panels.
Execution mutation locks disable applicable editing and canvas actions.
Upload failures display the backend's per-file detail and offer explicit retry; a network failure is not proof that no file was stored.

**Transient single-file picker:** An ordinary browser **Select File** action activates this same panel with the calling parameter and optional file-type filters.
Folders remain visible for navigation but cannot be chosen as filesystem directories, and exactly one matching file can be selected.
**Use file** writes that file's authoritative server path to the calling parameter; **Cancel** changes no parameter.
Completion or cancellation restores the panel's previous normal multi-selection.
The Files source's **Select in Datasets panel** action instead uses normal multi-selection and does not enter this picker mode.

---

## 4. Data Flow and State Synchronization

### 4.1 Principle

For a root workflow canvas, the **backend draft is the durable source of truth** for the current editable graph. The frontend canvas remains the owner of immediate interaction state and of the exact graph snapshot being queued. Every canvas has a stable canvas identity and owns its graph snapshot, workflow or nested-snapshot identity, semantic revision, accepted persistence revision, synchronization coordinator, undo history, and status projection.

1. A user command edits only its owning canvas and synchronously publishes one complete graph snapshot.
2. Parameter commands also project the target node as provisional `unexecuted` before any asynchronous persistence starts.
3. A root canvas debounces validated full-graph `PUT /workflow-drafts/{id}` writes with `expected_revision`; a nested canvas debounces revision-CAS snapshot writes.
4. The accepted response updates only that canvas's graph, validation, and accepted draft or snapshot revision.
5. Save, save-as, new workflow creation, Run, and export cross the owning root canvas's freshness barrier. Editor path and tool launches cross that same barrier for an active root canvas or flush the active private snapshot and wait for acceptance for an active nested canvas. Every production graph owner is a registered canvas session; state-free menu and editor shell adapters only delegate to that active registered session.
6. Run submits the workflow ID and accepted draft revision after the canvas freshness barrier. Full Run and Run Selected both compile the complete backend-loaded graph. Run Selected derives its selected-plus-upstream root scope from that graph's edges and filters only diagnostics proven to belong to unrelated root branches. Only when such diagnostics were ignored, it publicly compiles the selected-plus-upstream execution projection and rechecks accepted draft authority; clean graphs need no second compilation.
7. During attached local execution, graph mutations are globally locked; contextual progress and state updates arrive by WebSocket and are projected only onto the matching canvas. Durable managed remote editing follows [distributed execution Section 10](platform_specs_distributed_execution.md#10-execution-panel-and-target-selection).
8. Draft-change notices are retained by workflow id. Each canonical root persistence resource distinguishes local semantic origin and draft-only pending writes from saved-artifact dirty presentation and recovery-only persistence. Matching canvases without local semantic edits or pending draft writes auto-apply newer external revisions. Same-graph validation preserves the admitted origin; Keep my canvas retains local ownership, while explicit external resolution and clean accepted Save clear it. A remounted dirty frontend draft is conservatively protected because durable writer metadata cannot recover its earlier semantic origin.

`workflow.json` is a saved artifact, not the live editing source.
Save promotes the accepted graph into its `WorkflowDocument` envelope; portable export translates that captured graph in memory through the public library API.

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
       validation |
        cache miss v
           +------+------+
           | Out-of-date |
           |  (orange)   |
           +-------------+
```

**Disabled node semantics** (aligned with [library Section 4.6a](bioimageflow/docs/source/specs.md#46a-enabling-and-disabling-nodes)):

- **Disabled nodes are not executed.** No cache lookup, no computation, no side effects.
- **Implicit skip propagation.** Any enabled node whose upstream includes a disabled node is skipped during execution. These nodes remain displayed as "unexecuted" — no special visual encoding is needed.
- **Graph structure is preserved.** Disabling does not alter edges, bindings, or registration. Re-enabling restores the original wiring.
- **Cache is unaffected.** The `enabled` flag is not part of result-key material. Re-enabling a node can reuse a valid selected record when its computation inputs and selected upstream record references are unchanged.
- **Serialization:** Canonical platform graphs persist each node's `enabled` state directly; an omitted value defaults to `true` on input. Portable library exports include `"enabled": false` for disabled nodes and omit the default `true` value.

**Out-of-date detection:** Out-of-date status is server-authoritative and projects the accepted graph's library plan, including exact selected upstream record provenance ([library Section 6.5](bioimageflow/docs/source/specs.md#65-pre-execution-planning)).
The accepted draft or nested-snapshot validation response (or direct `/graph` compatibility response) returns that projection; diagnostic logical signatures must not substitute for result keys and selected record IDs.
The frontend does not maintain `last_execution_params` for out-of-date detection.
A parameter command immediately projects its target as provisional `unexecuted`; the accepted validation may then classify it as `out_of_date` when a prior selection or retained latest output establishes stale work.

An accepted `cache_corrupt` diagnostic with a failed node status takes badge precedence over a matching retained execution status when execution is idle, including an aggregate workflow node whose failed status is caused by a corrupt descendant. Semantic edit feedback and active execution progress keep their precedence; ordinary terminal execution statuses remain tied to their exact workflow and accepted draft revision. After Clear removes the diagnostic, refreshed cache and execution statuses restore the cleared and downstream badges without changing the graph or historical run.

### 4.3 Auto-Save and Startup Recovery

The frontend auto-saves meaningful graph changes to the backend workflow draft (debounced at 500ms). IndexedDB remains a fallback for cases where the backend is unavailable, the browser crashes before a draft write completes, or a local recovery path is needed.

**Startup recovery flow:**

```
App starts
  |
  +--> GET /api/v1/tools (populate tool panel)
  |
  +--> Connect WebSocket /ws
  |
  +--> Load the valid last-opened workflow, otherwise the first existing workflow in stable order
  |
  +--> GET /api/v1/workflow-drafts/{id}
  |
  +--> If backend draft exists or is synthesized:
  |      Record its revision and validation/status projection
  |      Prefer a newer IndexedDB recovery snapshot for the same existing workflow,
  |      keeping the accepted draft revision as the compare-and-swap base
  |      Otherwise load the accepted draft graph; clear obsolete or older recovery
  |      Show the unsaved indicator for a recovered graph or dirty accepted draft
  |
  +--> If backend draft load fails but IndexedDB recovery exists:
  |      Load IndexedDB recovery state and schedule a draft save when the backend is available
  |
  +--> If no saved workflow exists, show a non-persistent New/Open empty state
  |
  +--> Application ready
```

**Unsaved state indicator:** The workflow title in the menu bar shows `"My Workflow *"` when the backend draft differs from the saved workflow. The asterisk disappears after save/promotion.

Closing a clean root canvas closes it immediately. Closing a dirty root canvas presents **Save**, **Discard**, and **Cancel**, bound to the initiating canonical canvas even if activation changes while the action is pending. Save uses the exact-snapshot ordinary save path and closes only if no newer edit remains. Discard fences older draft and recovery writes, CAS-resets the accepted backend draft to the saved `workflow.json` graph, resets the initiating canvas state, and then closes; a conflict or failure leaves the tab open. Cancel changes nothing. Nested-snapshot close and discard remain separate and never reset a root draft.

Manual save (Ctrl+S) flushes pending frontend edits to the backend draft, checks revision freshness, and saves/promotes the draft to `workflow.json`.

### 4.4 Mapping GUI to Library

| GUI Concept | Library Concept |
|-------------|----------------|
| `ColumnEdge` (output pin to input pin) | `ColumnRef` (keyword arg) |
| `DataFrameEdge` (node to DataFrameTool positional pin) | Positional argument in `DataFrameTool.__call__` |
| Parameter value in Node Panel | Constant keyword argument |
| Pin visibility on a node | ProcessingTool input pins follow `GUIMeta.connectable`; DataFrameTool parameters never expose column input pins. |
| "Run" button | `workflow.compute(node)` |
| Node position, collapsed state | Platform presentation state owned directly by canonical `GraphState`; omitted from portable library graphs |
| Explicit package/version or local-source node binding | Qualified tool/source identity preserved through library translation |

### 4.5 Workflow Persistence

A saved `workflow.json` is the strict `WorkflowDocument` envelope defined in [`models/workflow.py`](backend/src/bioimageflow_server/models/workflow.py), containing `platform_document_version`, `graph`, `metadata`, `authoring_source`, `owned_source_ids`, and `artifact_hash`.
Its `graph` is the sole recursive editable definition, including layout and node presentation state; there is no separate persisted `workflow` payload or `gui` graph.
Saved-workflow dependency inspection captures workflow-local source bindings from their exact owned files without changing the saved graph or compiling the workflow.
An explicit flat `tools.<module>` binding resolves the contained workflow-relative module before catalog lookup; missing files retain the typed source-missing refusal, while syntax-invalid bytes remain available for editing and are rejected by validation.
Root draft revision-CAS, private nested-snapshot revision-CAS, explicit promotion/apply, identity generations, source ownership, and workflow-owned runtime results follow [v2 Sections 2, 7, and 12](platform_specs_v2.md#2-canonical-graph-document).
Detaching saved-workflow provenance follows the exact editor-owner fence in [v2 Section 10](platform_specs_v2.md#10-saved-source-provenance): an open editor at or below the target prevents mutation, and successful Detach preserves the embedded graph and bindings.
The library workflow is compiled from the accepted graph in memory for validation, execution, and portable export.
Default serialization preserves accepted root and nested engine/scheduling configuration without loading carried bound packages; compilation derives the root engine from enabled recursive actual capabilities and materializes once without installing missing packages.
Validation supplies actual bound-node schemas in `node_tools`, retaining installed package/version and read-only provenance separately from editable owned sources.
The canvas consumes those schemas only for their matching accepted graph and root workflow or nested session; unavailable metadata preserves authored parameters/templates and cannot substitute a same-named catalog class.
Pending or globally failed compilation can retain that bound node’s prior presentation metadata, while actual execution remains governed by current validation.

Panel layout preferences (which panels are open, sizes) are stored in **user-level settings** (not per-workflow).

### 4.6 Undo/Redo

Undo/redo is purely client-side. The frontend maintains an undo stack of graph state snapshots.

- **Undoable operations:** Node add/remove, edge add/remove, parameter changes, node position changes. All are pure client-side graph state changes. Removing nodes prunes connected edges and every workflow-interface reference to those nodes in the same undoable snapshot; shared workflow inputs retain only their surviving targets and disappear when no target remains.
- **Not undoable:** Execution, clear outputs, save, tool installation. These have server-side effects that can't be reversed by restoring client state. The frontend shows a confirmation dialog for destructive operations (Clear already does, per Section 3.5.2).
- **Granularity:** Each user action is one undo step. A parameter change is captured on blur/Enter (not per keystroke). Moving multiple selected nodes is one step.
- **Stack size:** 100 steps (configurable). Oldest entries are dropped.
- **On workflow load:** Undo history is cleared (no mixing undo stacks across workflows).

---

## 5. Edge Cases and Error Scenarios

### 5.1 Tool Not Found

A workflow references a tool that is no longer installed (package uninstalled, or workflow shared from another machine).

The node is rendered with a red "Tool not found" badge and cannot be executed until the tool becomes available. Dependency details and any available version-rebind action are presented by the workflow dependency dialog; the current node UI does not install a package directly.

### 5.2 Missing Package Version

A workflow requires a tool package version that is not in the tool store (e.g., workflow saved with `bioimageflow-cellpose==1.2.0` but only `1.3.0` is installed).

On load, the server reports missing package versions and tool classes in the workflow response. The dependency dialog displays required and installed versions plus affected nodes. **Use installed versions** is enabled when package alternatives exist; it calls `POST /workflows/{id}/rebind-versions`, updates the saved workflow references, and marks affected nodes for revalidation. Installing an absent required version remains a separate Tools Panel action.

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

This table summarizes the primary frontend and agent routes. The generated OpenAPI document is the complete current HTTP surface.

| # | Method | Endpoint | When used |
|---|--------|----------|-----------|
| 1 | `GET` | `/api/v1/tools` | Startup; after package install/uninstall |
| 2 | `GET` | `/api/v1/tools/{tool_name}/source` | "Open in editor" button in Tools Panel |
| 3 | `GET` | `/api/v1/tools/packages` | Startup; Tools Panel tool list and Manage Tools dialog |
| 3a | `POST` | `/api/v1/tools/packages/refresh` | Refresh package-index metadata for known and installed packages |
| 4 | `POST` | `/api/v1/tools/packages/{name}/install` | Row-level version install button in Manage Tools dialog |
| 5 | `DELETE` | `/api/v1/tools/packages/{name}` | Row-level uninstall button in Manage Tools dialog |
| 5a | `POST` | `/api/v1/tools/packages/import-url` | Inline **Install tool package** footer; GitHub/GitLab URL source |
| 5b | `POST` | `/api/v1/tools/packages/import-archive` | Inline **Install tool package** footer; `.zip` archive source |
| 6 | `POST` | `/api/v1/tools/environments/{name}/start` | Start env toggle in Tools Panel / Manage Tools dialog; pre-warming |
| 7 | `POST` | `/api/v1/tools/environments/{name}/stop` | Stop env toggle in Tools Panel / Manage Tools dialog; freeing resources |
| 7a | `POST` | `/api/v1/tools/environments/{name}/recreate` | Create/recreate action in the Manage Tools dialog |
| 8 | `GET` | `/api/v1/workspace` | Startup; Settings storage section |
| 9 | `PATCH` | `/api/v1/workspace` | Explicit in-memory desktop workspace path change |
| 10 | `GET` | `/api/v1/workflows/tree` | Workflows panel tree |
| 11 | `POST` | `/api/v1/workflows/folders` | Create folder in Workflows panel |
| 12 | `PATCH` | `/api/v1/workflows/folders/{path}` | Rename or move folder |
| 13 | `DELETE` | `/api/v1/workflows/folders/{path}` | Delete empty folder, recursively delete children, or move children up |
| 14 | `GET` | `/api/v1/workflows` | Compatibility flat workflow list |
| 15 | `POST` | `/api/v1/workflows` | "New workflow" menu; startup if no existing workflow |
| 16 | `GET` | `/api/v1/workflows/{id}` | Opening a saved workflow |
| 17 | `PUT` | `/api/v1/workflows/{id}` | Ctrl+S save after draft flush/promotion; "Save" menu |
| 18 | `DELETE` | `/api/v1/workflows/{id}` | "Delete workflow" menu |
| 19 | `PATCH` | `/api/v1/workflows/{id}` | Update, rename/move, or duplicate workflow |
| 19a | `POST` | `/api/v1/workflows/{id}/rebind-versions` | Use currently active installed package versions and refresh dependency metadata |
| 19b | `POST` | `/api/v1/workflows/{id}/activate` | Update external active-workflow context without selecting graph authority |
| 20 | `GET` | `/api/v1/workflow-drafts/{id}` | Workflow open/startup draft load; agent graph inspection |
| 21 | `PUT` | `/api/v1/workflow-drafts/{id}` | Per-root-canvas full-graph persistence and validation with `expected_revision` |
| 22 | `POST` | `/api/v1/workflow-draft-operations/{id}` | Structured validated draft operations for agents |
| 23 | `PUT` | `/api/v1/graph` | Stateless request-local compatibility or transient graph validation; normal root canvases use validated draft writes |
| 23a | `POST` | `/api/v1/graph/nodes/{node_id}/output_schema` | Request-local dynamic output-schema resolution from a complete graph |
| 24 | `GET` | `/api/v1/nodes/{node_id}/data` | Compatibility query for a node output in Node Data |
| 24a | `POST` | `/api/v1/nodes/{node_id}/data/query` | Filtered, sorted, paginated Node Data query |
| 25 | `GET`/`POST` | `/api/v1/nodes/{node_id}/data/csv` | Unfiltered compatibility download or filtered Node Data CSV export |
| 26 | `GET` | `/api/v1/nodes/{node_id}/thumbnail` | Viewport-triggered image thumbnails in Node Data cells |
| 26a | `GET` | `/api/v1/nodes/{node_id}/image` | Serve an image-valued result cell, optionally converted to OME-TIFF |
| 26b | `GET` | `/api/v1/nodes/{node_id}/image/{filename}` | Serve the same image with an Avivator-compatible response filename |
| 26c | `POST` | `/api/v1/nodes/{node_id}/reveal` | Reveal the image-valued result cell in the system file browser |
| 28 | `POST` | `/api/v1/execution/run` | "Run Workflow" / "Run Selected" buttons after draft freshness check |
| 29 | `POST` | `/api/v1/execution/stop` | "Stop" button in execution banner |
| 30 | `POST` | `/api/v1/execution/clear` | "Clear" button in Node Panel |
| 31 | `GET` | `/api/v1/execution/status` | Explicit execution status inspection and recovery; WebSocket registration sends `status_snapshot` automatically |
| 32 | `GET` | `/api/v1/settings` | Opening Settings panel; startup |
| 33 | `PATCH` | `/api/v1/settings` | Live preferences and persisted desktop workspace selection |
| 34 | `POST` | `/api/v1/fs/reveal` | "Open output folder" or "Reveal in file browser" |
| 35 | `POST` | `/api/v1/napari/open` | "Open in Napari" button in Node Data |
| 36 | `GET` | `/api/v1/napari/status` | Checking Napari availability |
| 36a | `POST` | `/api/v1/napari/environments/managed` | Start managed napari environment creation |
| 36b | `POST` | `/api/v1/napari/environments/{id}/copy` | Start an independent modified managed copy |
| 36c | `POST` | `/api/v1/napari/environments/{id}/retry` | Retry eligible managed setup |
| 36d | `GET`/`POST` | `/api/v1/napari/environments/{id}/operations/{operation_id}` | Poll or cancel a managed mutation (cancel adds `/cancel`) |
| 36e | `DELETE` | `/api/v1/napari/environments/managed/{id}` | Remove a proven owned managed generation |
| 36f | `POST` | `/api/v1/napari/viewing-readiness` | Passive desktop-only compatibility report for a portable viewing-requirement manifest |
| 37 | `POST` | `/api/v1/fiji/open` | "Open in Fiji" button in Node Data |
| 37 | `POST` | `/api/v1/editor/open` | "Open" from Node Data path cells after the active canvas persistence barrier |
| 38 | `POST` | `/api/v1/editor/open-tool` | "Open in editor" for catalog tools and newly created tools after the active canvas persistence barrier |
| 39 | `GET` | `/api/v1/health` | Health check |
| 40 | `GET` | `/api/v1/datasets` | Datasets panel and transient file picker; list managed files |
| 41 | `POST` | `/api/v1/datasets/upload` | Datasets panel upload queue and browser file drops |
| 42 | `DELETE` | `/api/v1/datasets/{dataset_id}` | Compatibility single-file deletion |
| 42a | `GET`/`POST`/`PATCH` | `/api/v1/datasets/folders[/{folder_id}]` | List/create/rename/move logical folders (Section 2.4.10) |
| 42b | `PATCH` | `/api/v1/datasets/{dataset_id}` | Change display name or logical folder |
| 42c | `POST` | `/api/v1/datasets/actions/resolve` | Resolve a managed selection to ordered files |
| 42d | `POST` | `/api/v1/datasets/actions/delete-preview` / `/delete` | Preview and revision-confirm recursive deletion |

---

## 8. Security

The server binds to `localhost` only. No authentication is required. The application runs as a desktop process with the same permissions as the user.
