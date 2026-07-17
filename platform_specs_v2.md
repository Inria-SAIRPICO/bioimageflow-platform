# BioImageFlow Platform Specifications — v2

Read the [BioImageFlow library specification](bioimageflow/docs/source/specs.md) for the underlying workflow and tool contracts.

> **Status: normative implemented additions.** This document builds cumulatively on the [v1 current base](platform_specs_v1.md) and defines features implemented by the current platform. [v3](platform_specs_v3.md) remains a future proposal.

All endpoints listed below use the `/api/v1/` prefix. The architecture, technology stack, and draft-backed full-state synchronization model remain as specified in v1.

---

## 1. Sub-Workflow Support

Sub-workflows allow grouping a set of nodes into a single reusable unit. The BioImageFlow library provides [sub-workflow support](bioimageflow/docs/source/specs.md#14-sub-workflows). The GUI adds visual creation, editing, rendering, and execution of sub-workflows.

### 1.1 Creating a Sub-Workflow

#### From Selection

1. The user selects a group of nodes on the canvas.
2. Right-click context menu: "Create sub-workflow."
3. The selected nodes are wrapped into a `SubWorkflowNode`:
   - **Inputs auto-detection:** Edges entering the selection from outside become sub-workflow input pins. Each edge creates its own pin, even if the same `(source_node, source_output)` pair feeds multiple internal nodes. This allows the user to rewire inputs independently after creation.
   - **Outputs auto-detection:** Edges leaving the selection to outside become sub-workflow output pins.
   - If the selected nodes have no external connections, the sub-workflow is valid as a **detached branch** with no inputs/outputs. It can be executed independently from the rest of the graph.
4. The user can fine-tune the sub-workflow's interface using the **Publish toggle** (see Section 1.5): any internal input parameter with a connectable pin (`connectable != "never"`) can be promoted to the workflow interface, making it configurable on the outer node when this workflow is used as a sub-workflow.
5. This operation is **undoable** as a single undo step. Undoing restores all internal nodes, edges, and positions to the canvas and removes the SubWorkflowNode.

#### From Workflows Panel

Saved workflows can be dragged from anywhere on the workflow row in the
Workflows panel onto the canvas. Dropping a workflow creates a SubWorkflowNode;
the dragged workflow becomes the sub-workflow's internal DAG. The same row drag
also participates in the workspace tree drag/drop; there is no separate drag
handle with different behavior. The platform rejects drops that would make a
workflow contain itself directly or indirectly, including dropping the active
workflow into its own canvas, dropping a workflow whose nested graph already
contains the active workflow, or dropping an ancestor workflow inside one of its
sub-workflow editor tabs.

The Workflows panel uses the v1 workspace tree semantics: folder and workflow
ids are slash-separated workspace-relative paths whose individual segments may
contain spaces, underscores, and hyphens. Creating a workflow while a folder is
selected places the new workflow in that folder. Dragging workflows or folders
onto a folder moves the corresponding workflow or full folder subtree. Only
directories containing `workflow.json` are listed as workflows.

Workflow ids are derived from these directory paths. Display metadata does not change identity. Moving a workflow or folder changes each affected id, and every existing moved draft is preflight-validated before its embedded `workflow_id` is atomically updated to the new route. A workflow without a draft remains without one. The retained-snapshot inventory must also be fully readable before the first filesystem rename. A successful identity move rewrites the durable root ownership of every retained nested-snapshot tree while preserving each private session UUID, accepted graph, revision, validation result, and update timestamp. If nonfatal startup cleanup was skipped, the move applies the same deterministic canonical-collision winner and losing-tree cleanup used by reconciliation. Mounted root and nested canvas identities are immutable, so the frontend rejects any affected rename, move, or promotion before the request until all workflow and sub-workflow tabs presenting those routes are closed. Confirmed workflow deletion instead captures the selected durable identity generation and any mounted canvas-session registration, binds its lifecycle gate to that exact target, and supplies the generation as an atomic backend precondition. A stale dialog cannot delete a remounted or recreated same-ID workflow. The frontend keeps the captured root and nested canvases mounted until the backend succeeds, then closes those exact canvases and activates the most recently active remaining root. If no root remains, it opens an existing workflow in stable tree order or shows a non-persistent New/Open empty state. A pre-commit delete failure leaves every target mounted; a local cleanup failure after committed server deletion closes the stale dialog and is reported as a cleanup warning. Local or remote deletion cannot be redirected by later tab activation or a delayed same-ID response. A workspace-durable identity-generation ledger retains deletion and move tombstones across backend restarts, so transient reconnects preserve unchanged dirty canvases while a true delete/recreate causes canonical disposal and fresh reload.

The platform asks the BioImageFlow library to build and validate the
sub-workflow. Recursive containment is rejected by the library validation layer;
the platform surfaces that validation error in the GUI. A workflow cannot
contain itself directly or indirectly (for example, A contains B while B
contains A).

**Default derivation:** Connectable source-node inputs are published as sub-workflow Inputs, and all terminal node output columns are published as sub-workflow Outputs. The user can then adjust visibility using the Publish toggle on each connectable input and output field.

### 1.2 Rendering

- **SubWorkflowNode** is displayed with a **thick border** (vs. thin for tool nodes), visually distinguishing it from regular nodes.
- Sub-workflow **Inputs** appear as input pins on the left side.
- Sub-workflow **Outputs** appear as output pins on the right side.

### 1.3 Editing

- **Double-click** a SubWorkflowNode to open its internal DAG in a **new tab** (same behavior as opening a workflow from the Workflows Panel).
- The tab title shows the sub-workflow node name (e.g., `segment_and_measure_1`).
- The user can edit internal nodes, parameters, and connections within this tab.
- The editor session carries the parent SubWorkflowNode's published interface (`published_inputs` and `published_outputs`) alongside the internal DAG. Internal node panels use this shared session state for Publish toggles, so publishing/unpublishing a field changes the outer node interface, not only the nested graph.
- A sub-workflow tab uses the same canvas and side panels as a normal workflow tab. It does not add a special Apply/Close toolbar; saving uses the normal save command for the active tab.
- **Save semantics:** Changes to the sub-workflow's internal DAG are applied to the parent on explicit save (Ctrl+S within the sub-workflow tab or the normal Save command while that tab is active). The parent workflow does not see intermediate edits. Closing the tab with unsaved changes shows a confirmation dialog: "Discard unsaved changes to sub-workflow '{name}'?"
- Saving a sub-workflow tab applies both the internal DAG and the published interface to the parent node. Publishing-only changes mark the tab dirty. If a published pin is renamed, existing parent edges targeting the same internal field/output are moved to the new handle. If a pin is unpublished, parent edges and stale parent-level parameter values for that pin are removed.
- Opening a sub-workflow resolves or creates a private durable snapshot before the editor mounts. A saved root owner is normalized by the server to its canonical encoded `workflow:<id>` canvas ID, canonical workflow ID, and current durable workflow identity generation; deeper snapshots are owned by their stable parent snapshot session UUID. A client-supplied root alias or generation is never trusted as storage authority.
- Every nested edit replaces one complete `GraphState`, including its published interface, through revision-checked background persistence. The parent graph remains unchanged until explicit Save.
- Save first flushes all queued edits, then applies the exact graph and published interface accepted by the snapshot API only to the addressed parent canvas as one undo transition. The nested session becomes clean only after that parent acknowledges the apply.
- Parent apply is conditional on the parent's nested graph and published interface still matching the baseline captured when the editor opened or last saved. Unrelated parent edits are preserved, but a missing parent or independently changed nested graph/interface rejects the apply without a parent history transition and leaves the durable nested session dirty.
- A confirmed discard flushes the latest private edit and deletes the snapshot with its accepted revision before local state is dropped. A canceled discard retains the session, and a process restart recovers the last accepted private snapshot.
- Startup reconciliation retains complete snapshot trees whose root workflow and generation still exist, and removes interrupted temporary files, malformed records, ownership cycles, missing parents, confirmed-missing workflows, deleted-generation leftovers, workflow-less root sessions, and every descendant of an invalid owner. A transiently unreadable workflow authority preserves its retained tree unchanged for a later reconciliation. If legacy aliases project multiple roots onto the same canonical workflow owner and parent node, the most recently updated accepted snapshot wins deterministically and every losing snapshot tree is removed. A generation-less legacy root is backfilled only when it can still be proven to belong to an unmoved initial identity (generation 0 or 1), including normalization during a move if startup cleanup was skipped; ambiguous legacy state is discarded instead of being inherited by a recreated identity.
- Closing the sub-workflow tab returns focus to the parent workflow tab.

### 1.4 Execution and Caching

Per the library spec:

- The engine **flattens** the sub-workflow into constituent internal nodes at execution time. Internal nodes get scoped names (e.g., `segment_and_measure_1/cellpose_segmenter_1`).
- **Caching is per-internal-node**, not per-sub-workflow. Each internal node has its own cache entry.
- Each sub-workflow instance has its own parameter values (stored on the parent-level node).

**Execution locking:** During execution, all open tabs are locked identically. Sub-workflow tabs are locked the same as the parent workflow tab — no graph mutations allowed.

### 1.5 Publish Toggle on Parameters

Each connectable input row in the Node Panel ([v1 Section 3.5.3](platform_specs_v1.md#353-input-parameters)) includes a **Publish toggle** — a two-state button (+ icon). The toggle is shown for normal workflow tabs and sub-workflow tabs because any workflow may later be dragged into another workflow and become a SubWorkflowNode. Inputs with `connectable = "never"` do not show a Publish toggle and cannot be exposed as published input pins.

| Element | Description |
|---------|-------------|
| **Publish toggle** | Two-state button (+ icon). When active, this connectable input becomes part of the current workflow's published input interface. If the workflow is used as a SubWorkflowNode, it appears as an input pin on the outer node. |
| **Published name** | Text field (shown only when published). Sets the name of the corresponding input pin. Defaults to `{node_name}.{parameter_name}`. Must be unique among published inputs and outputs in the active workflow. |

When an input is published:
- It appears as an input pin on the SubWorkflowNode in the parent workflow.
- The parent workflow can set its value directly or connect an edge to it.
- The value set on the SubWorkflowNode overrides the internal node's default.
- The BioImageFlow library config represents this as a declared sub-workflow input plus an internal node binding of `{"from_input": "<published_name>"}`. The platform sends the derived config to the library validator and surfaces library errors.

### 1.6 Publish Toggle on Outputs

Each output field in the Node Panel ([v1 Section 3.5.4](platform_specs_v1.md#354-output-fields)) includes a **Publish toggle** (+ icon). Published outputs become sub-workflow Outputs, visible as output pins on the parent SubWorkflowNode.

**Default behavior:** Terminal node outputs are published by default when a sub-workflow is created. Non-terminal node outputs are unpublished by default.

When an output is published:
- It appears as an output pin on the SubWorkflowNode in the parent workflow.
- Other nodes in the parent workflow can connect edges to it.
- The published name defaults to `{node_name}.{output_field}` and can be customized.
- The BioImageFlow library config represents this as a declared sub-workflow output plus an `output_mapping` entry from the published name to the internal node output. The library validates missing mappings, undeclared mappings, and invalid interface references.

### 1.7 Nesting

Sub-workflows may contain other sub-workflows. Double-clicking a nested sub-workflow opens another tab. The engine flattens recursively at execution time.

### 1.8 Schema Changes

The root `GraphState` carries `published_inputs` and `published_outputs` in addition to `nodes` and `edges`. This gives every saved workflow the same published interface model as a SubWorkflowNode. SubWorkflowNodes are regular `NodeState` entries with sentinel `tool_name: "__sub_workflow__"`; `source_workflow_name` carries the path-derived ID when the nested graph came from a saved workflow. The sub-workflow's internal DAG is stored as a nested `GraphState`; the parent node also stores a snapshot of the nested graph's published interface for rendering pins and validating connections:

```json
{
  "nodes": [
    {
      "id": "segment_and_measure_1",
      "name": "Segment and Measure 1",
      "tool_name": "__sub_workflow__",
      "source_workflow_name": "segment_and_measure",
      "position": [400, 300],
      "parameters": {},
      "sub_workflow": {
        "nodes": [],
        "edges": [],
        "published_inputs": [],
        "published_outputs": []
      },
      "published_inputs": [],
      "published_outputs": []
    }
  ],
  "edges": [],
  "published_inputs": [],
  "published_outputs": []
}
```

Opening a saved workflow or a SubWorkflowNode creates or activates a named canvas tab. Each mounted canvas owns its graph snapshot, root-workflow or private-snapshot identity, revision state, synchronization coordinator, undo history, and derived status projection. The Node Panel, selected nodes, validation, and execution controls resolve through the active canvas tab, and switching tabs updates the workflow title shown in the top bar. There is no separate sub-workflow-only editor toolbar.

Startup uses a temporary non-canvas loading placeholder only while it resolves a saved workflow. The resolved initial root is created through the same canonical `workflow:<id>` panel path, canvas-session registration, parameters, persistence, activation, placement, close guard, and disposal behavior as every later root workflow. Reopening any root activates that one existing canonical tab, and closing all roots leaves a non-persistent empty state rather than a special canvas identity.

**Validation:** Validated root draft writes and private nested-snapshot writes call the BioImageFlow library's recursive sub-workflow validator and surface scoped errors. The stateless `PUT /graph` compatibility/transient-validation endpoint invokes the same validator without persisting graph state. Errors within a sub-workflow reference the scoped node path, for example `"node": "segment_and_measure_1/cellpose_segmenter_1"`.

Graph compilation, recursive validation, output-schema resolution, Run preparation, and cache-clear planning execute through the backend's bounded graph worker rather than occupying the application event loop.

Revisioned root-draft and private-snapshot mutations retain an immutable graph snapshot, capture the expected revision and durable workflow identity generation, release their mutation lock for validation, then reacquire the lock and recheck the captured authority before committing atomically. Root reset also rechecks the saved-artifact hash, nested snapshots recheck root storage context and open-session uniqueness, and stale validation results are discarded, retried against a changed non-conflicting context, or returned as revision conflicts instead of overwriting newer state.

Draft, semantic-operation, nested-snapshot, and transient graph-validation requests hold one execution-manager idle lease across their complete asynchronous prepare/validate/commit sequence, so an admitted edit finishes before Run and a Run already preparing or running rejects later edits. The lease does not present editing as execution startup.

Run reports an explicit `starting` status with its pending execution identity, without attaching prior execution results, until its exact graph has compiled, validated, and passed a single final workflow generation, storage-context, draft-revision, and exact-draft-graph authority recheck. Cache Clear is serialized with Run, validates outside workflow locks, and performs cache invalidation only while the captured identity generation and storage context remain current.

Every execution-related log carries the same immutable `execution_id`, `workflow_id`, and `draft_revision` as its progress and terminal events, including BioImageFlow and Wetlands worker-thread output captured during that run. Non-execution tool, environment, thumbnail, and platform logs remain contextless and global. The global Logger Panel retains both kinds, while a Node Panel execution-output view matches the owning workflow plus the exact or descendant-scoped node ID and narrows to the retained execution identity when that canvas owns one; identical node IDs in another workflow or execution cannot appear in that view or suppress its failure record.

### 1.9 Integration with v1 Features

- **Undo/redo:** Creating a sub-workflow from selection is a single undo step. Undoing restores all internal nodes, edges, and canvas positions, and removes the SubWorkflowNode.
- **Copy/paste:** SubWorkflowNodes can be copied and pasted like regular nodes. The entire internal DAG is included in the clipboard payload.
- **Execution banner:** During execution, the progress bar includes flattened internal nodes. The banner shows the scoped node name (e.g., `segment_and_measure_1/cellpose_segmenter_1`).
- **Data Table:** Selecting a SubWorkflowNode shows the published outputs in the Data Table.
- **Logger Panel:** Logs from internal nodes are prefixed with the scoped name.

---

## 2. Code Editor Panel

An embedded VS Code instance served by code-server, providing a full development environment for editing tool source code without leaving the application.

### 2.1 Overview

The Code Editor Panel is a Dockview panel containing an iframe that loads code-server. code-server is installed and configured locally automatically. The panel provides a complete VS Code editing experience (syntax highlighting, IntelliSense, terminal, extensions) within the BioImageFlow GUI.

### 2.2 Backend

#### `GET /editor/status`

Returns the current state of code-server and its URL.

Optional query parameter:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `launch` | `bool` | `false` | When `true`, the backend may start the embedded code-server before returning status. Used when the Code Editor Panel is opened directly from the menu. |

**Response:**

```json
{
  "available": true,
  "url": "http://127.0.0.1:32344",
  "version": "4.106.2",
  "control_available": true,
  "launch_attempted": false,
  "error_code": null,
  "error_detail": null
}
```

If code-server is not installed or not running:

```json
{
  "available": false,
  "url": null,
  "version": null,
  "control_available": false,
  "launch_attempted": false,
  "error_code": null,
  "error_detail": null
}
```

#### `POST /editor/open`

Opens a file or folder in the code editor.

**Request body:**

```json
{
  "path": "/path/to/tool/source"
}
```

**Behavior:**
1. If the user has configured an **external editor command** in Settings (e.g., `code {workspace_path} --goto {file_path}`), the backend launches that command with placeholders substituted.
2. Otherwise, if code-server is available, the backend instructs code-server to open the path.
3. If neither is available, the endpoint returns the normal `EditorOpenResponse` with `opened: false` and `method: "clipboard"`. The frontend copies `path` to the clipboard and shows the response message.

```json
{
  "opened": false,
  "method": "clipboard",
  "url": null,
  "path": "/path/to/tool/source",
  "project_path": null,
  "message": "Path copied - open in your local editor.",
  "error_code": null,
  "error_detail": null
}
```

#### `POST /editor/open-tool`

Opens the editor project that owns a tool source file and focuses that source file.

**Request body:**

```json
{
  "tool_name": "CellposeSegmenter",
  "workflow_id": "segmentation/nuclei"
}
```

`workflow_id` is optional for package tools and required when resolving custom workflow tools.
The endpoint returns the standard editor-open response; `path` is the focused tool source file:

```json
{
  "opened": true,
  "method": "embedded",
  "url": "http://127.0.0.1:32344/?folder=%2FUsers%2Falice%2FBioImageFlow%2Fworkspace",
  "path": "/Users/alice/BioImageFlow/workspace/workflows/segmentation/nuclei/tools/cellpose_segmenter.py",
  "project_path": "/Users/alice/BioImageFlow/workspace",
  "message": null,
  "error_code": null,
  "error_detail": null
}
```

**Behavior:**
1. If the tool is a custom workflow tool, the editor project path is the current user's workspace folder and the focused file points under `workspace/workflows/<id>/tools/`.
2. If the tool comes from an installed package, the editor project path is the installed tool-store root when the package source lives under that store; otherwise it falls back to the source file's parent directory.
3. For embedded code-server, the response URL selects only the project folder. The frontend loads that folder and focuses the response `path` through the opener endpoint without adding a `file` query parameter to the folder URL.
4. External editor commands receive `{workspace_path}` as the editor project folder and `{file_path}` as the focused source file, for example `code {workspace_path} --goto {file_path}`.

### 2.3 Frontend

**Implementation:** An iframe loading the code-server URL obtained from `GET /editor/status`.

**Panel behavior:**
- The Code Editor Panel is a tab in the Dockview layout. It can be docked, resized, and collapsed like any other panel.
- On first use, the panel checks `GET /editor/status?launch=true`. If code-server is available, the iframe loads. If not, the panel shows a message: "code-server is not available. Configure an external editor in Settings."
- Opening a tool's source script (from the Tools Panel "Open in editor" button)
  sends `POST /editor/open-tool` and activates the Code Editor Panel. Custom
  workflow tools open the user's workspace project; installed package tools open
  the installed tool-store project and focus the package source file.

**Interactions with tool development:**
- Editing tool source code in the Code Editor triggers the existing **tool hot-reload** mechanism ([v1 Section 2.7](platform_specs_v1.md#27-tool-hot-reload)). Changes are detected by the file watcher, and affected nodes are updated automatically.

### 2.4 Settings Changes

The Settings Panel ([v1 Section 3.12](platform_specs_v1.md#312-settings-panel)) includes a Code Editor section:

| Field | Widget | Description |
|-------|--------|-------------|
| **External editor command** | Text input | Command template for opening files in an external editor. Placeholder: `code {workspace_path} --goto {file_path}`. `{workspace_path}` is the editor project folder (the current workspace for custom tools, the installed tool store for package tools) and `{file_path}` is the focused file. |
| **Enable unsafe webapp features** | File-only boolean | Debug switch for local webapp-mode development. Default `false`. Exposed by `GET /settings`, rejected by `PATCH /settings`. |

`enable_unsafe_webapp_features` only affects `deployment_mode === "webapp"`. With the default `false` value, local source-editing actions are disabled: tool creation, rename, and delete are hidden in the frontend and rejected by the backend, and tool source-opening controls are hidden in the frontend. Setting it to `true` re-enables local debugging actions that can modify or open server-side code: creating tools, renaming custom tools, deleting custom tools, and opening tool source paths in the code editor. This setting is unsafe for hosted or multi-user deployments and must be changed only in the settings file or server-side configuration, never from the GUI.

**Editor resolution order:**
1. If an external editor command is configured and non-empty, use it (launch the command).
2. If code-server is available (`GET /editor/status` returns `available: true`), use the embedded code-server iframe.
3. If neither is available, copy the path to the clipboard with a toast notification.

### 2.5 Integration with v1 Features

- **Tools Panel:** The "Open in editor" button on each tool row sends `POST /editor/open-tool` and activates the Code Editor Panel.
- **Data Table:** Path cells (non-image) have an "Open" button that sends `POST /editor/open` for CSV, JSON, and tabular data files.
- **Tool hot-reload:** Edits made in the Code Editor Panel trigger the same hot-reload pipeline as edits made in any external editor (file watcher based).

---

## 3. Cross-Workflow Copy/Paste

Extends the v1 copy/paste feature to support pasting nodes across different workflows with automatic package version resolution and parameter re-validation.

### 3.1 Clipboard Format

The clipboard payload is self-contained and includes all information needed to reconstruct the copied nodes in any workflow:

```json
{
  "bioimageflow_clipboard": true,
  "clipboard_version": 2,
  "source_workflow_name": "segmentation/nuclei",
  "created_at": "2026-07-16T12:00:00.000Z",
  "nodes": [
    {
      "id": "cellpose_segmenter_1",
      "name": "Cellpose Segmenter 1",
      "tool_name": "CellposeSegmenter",
      "position": [350, 200],
      "parameters": {"diameter": 30.0, "model_type": "cyto2"},
      "resources": {},
      "output_templates": {},
      "enabled": true,
      "collapsed": false,
      "tool_package": "bioimageflow-cellpose",
      "tool_package_version": "1.2.0"
    }
  ],
  "edges": []
}
```

`clipboard_version` is required and current serialization emits version 2 together with `source_workflow_name` and `created_at`. `tool_package` and `tool_package_version` are included when registry metadata is available so version mismatches can be detected on paste.

### 3.2 Paste Behavior Within the Same Workflow

Same as v1: pasted nodes get new unique IDs and names. Internal edges between pasted nodes are preserved with remapped node IDs. Edges connecting to nodes outside the selection are dropped.

### 3.3 Paste Behavior Across Workflows

When pasting into a different workflow, the following resolution steps occur:

1. **Tool resolution:** Each pasted node's `tool_name` is looked up in the current tool store. If the tool is not found, the paste is aborted for that node and a toast warns: "Tool '{name}' not found — install the package first."

2. **Package version resolution:** If the pasted node's `tool_package_version` differs from the version active in the target workflow:
   - Parameters are validated against the **current** tool schema (the version active in the target workflow).
   - Compatible values are kept.
   - Incompatible or removed fields are set to their defaults.
   - A warning toast is shown: "Pasted node was from {package} {version}, but this workflow uses {other_version}. Some parameters were reset to defaults."

3. **Parameter re-validation:** Even if versions match, parameters are validated against the current schema. Invalid values (e.g., out-of-range numbers, removed enum options) are reset to defaults with a warning.

4. **Node ID and name generation:** New unique IDs and names are generated using the same logic as node creation (tool class name converted to snake_case with numeric suffix).

5. **Edge re-mapping:** Internal edges between pasted nodes are preserved with remapped node IDs. External edges are dropped.

### 3.4 Error Handling

| Scenario | Behavior |
|----------|----------|
| Tool not installed | Toast: "Tool '{name}' not found — install the package first." Node is not pasted. |
| Version mismatch, parameters compatible | Node is pasted. Toast: "Pasted node was from {package} {version}, but this workflow uses {other_version}." |
| Version mismatch, some parameters incompatible | Node is pasted with defaults for incompatible fields. Toast includes: "Some parameters were reset to defaults." |
| All tools missing | Toast: "No tools found for the pasted nodes. Install the required packages first." Paste is fully aborted. |

### 3.5 Integration with v1 Features

- **Undo/redo:** Cross-workflow paste is undoable as a single step, same as within-workflow paste.
- **Validation:** After paste, the frontend synchronously publishes the updated full graph through the owning registered canvas coordinator. A root canvas uses a validated draft write and a nested canvas uses a validated private-snapshot write; stateless `PUT /graph` remains available only for explicit request-local compatibility or transient validation and is not a hidden graph authority.
- **SubWorkflowNodes:** Cross-workflow copy/paste of SubWorkflowNodes includes the full internal DAG in the clipboard payload.

---

## 4. Export/Import Workflows

Allows exporting workflows to portable library archives and importing them
back, enabling workflow sharing between users and machines.

The platform is a thin GUI adapter here: it delegates export and import to the
BioImageFlow library API and must not reimplement the archive format. The
library-defined archive contains the workflow JSON and any project-local custom
tool bundle needed by that workflow. In the platform, GUI-created custom tools
are stored under `workspace/workflows/<id>/tools/` and exported without
embedding the absolute workspace path. The platform may add or restore GUI metadata only through
documented extension points in the library workflow document.

### 4.1 Backend

#### `POST /workflows/{id}/export`

Exports the workflow identified by workspace-relative id by calling the
BioImageFlow library export API.

**Response:** The response is the library archive as a browser download
(`Content-Disposition: attachment; filename="{slug}.bioimageflow.zip"`). The
archive structure is defined by the library and includes the workflow JSON plus
the project-local custom tool bundle used by the workflow.

**Error responses:**

| Code | Condition |
|------|-----------|
| 404 | Workflow not found |

#### `POST /workflows/import`

Imports a workflow by calling the BioImageFlow library import/load API.

**Request:** Multipart form upload with the `.bioimageflow.zip` file.

**Behavior:**
1. The server passes the upload to the BioImageFlow library import/load API.
2. If a workflow with the same path-derived name already exists, the server returns **409 Conflict** with a `suggested_name` alternative (e.g., `"segmentation/my_workflow_2"`). A caller may retry with the multipart `name_override` field.
3. The server checks required packages and tools against the tool store. The response uses the same `missing_packages` and `missing_tools` models as workflow loading in [v1 Section 2.4.2](platform_specs_v1.md#242-workflow-management).
4. On success, the imported workflow is saved as
   `workspace/workflows/<id>/workflow.json`. Any bundled custom tools are
   restored under that workflow directory's `tools/` folder with collision-safe
   names if needed.

**Response (HTTP 201):**

```json
{
  "info": {
    "id": "segmentation/my_workflow",
    "name": "my_workflow",
    "folder": "segmentation",
    "display_name": "My Workflow",
    "path": "/Users/alice/BioImageFlow/workspace/workflows/segmentation/my_workflow/workflow.json",
    "last_modified": "2026-07-16T12:00:00+00:00",
    "description": null,
    "storage_path": "/Users/alice/bioimageflow_data/workflows/segmentation/my_workflow",
    "workspace_path": "/Users/alice/BioImageFlow/workspace",
    "output_path": "/Users/alice/bioimageflow_data/workflows/segmentation/my_workflow"
  },
  "missing_packages": [
    {
      "package_name": "bioimageflow-stardist",
      "required_version": "0.9.0",
      "installed_versions": [],
      "affected_nodes": ["stardist_1"]
    }
  ],
  "missing_tools": [
    {
      "node_id": "stardist_1",
      "tool_name": "StarDist",
      "package_name": "bioimageflow-stardist",
      "required_version": "0.9.0",
      "installed_versions": []
    }
  ]
}
```

If either dependency array is non-empty, the frontend shows the same dependency dialog used by workflow loading. It lists required versions, installed alternatives, affected nodes, and missing tools; when an installed alternative exists, **Use installed versions** rebinds the imported workflow. Installation remains a separate Tools Panel action.

**Response (conflict):**

```json
{
  "error": "conflict",
  "detail": "Workflow 'segmentation/my_workflow' already exists",
  "suggested_name": "segmentation/my_workflow_2"
}
```

**Error responses:**

| Code | Condition |
|------|-----------|
| 409 | Workflow id conflict |
| 415 | Uploaded filename does not end in `.zip` (normally `.bioimageflow.zip`) |
| 422 | Invalid archive payload or invalid workflow structure |
| 423 | Workflow mutation is locked during execution |

### 4.2 Frontend — Workflows Panel Actions

The Workflows Panel ([v1 Section 3.8](platform_specs_v1.md#38-workflows-panel)) includes Export and Import actions:

- **Export:** Available in the Workflow menu and as a button in the Workflows Panel. Calls `POST /workflows/{id}/export` and triggers a browser file download of the `.bioimageflow.zip` archive.
- **Import:** Available in the Workflow menu and as a button in the Workflows Panel. Opens the browser's native file picker filtered to `.bioimageflow.zip` files. On file selection, uploads via `POST /workflows/import`. On success, the imported workflow appears in the workflow tree and can be opened. On id conflict, a dialog offers to rename or cancel.

### 4.3 Integration with v1 Features

- **Workflow loading:** The import endpoint reuses the same missing-package resolution flow as `GET /workflows/{id}` (v1).
- **Sub-workflows:** Exported workflows include all sub-workflow internal DAGs through the library export format. Sub-workflows are self-contained within the export.
- **Tool versions:** The `required_packages` field in the export enables the target machine to install exactly the right package versions.

---

## 5. Tool Creation and Management

Provides endpoints and UI for creating, deleting, and renaming custom tools directly from the GUI.

### 5.1 Backend

Custom-tool routes are scoped by the optional `workflow_name=<id>` query parameter. The current frontend supplies its active root workflow ID so the service resolves `workspace/workflows/<id>/tools/`; a request without a resolvable workflow context returns 400.

#### `POST /tools`

Creates a new tool from a template.

**Request body:**

```json
{
  "name": "MyNewTool",
  "tool_type": "ProcessingTool"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `name` | `str` | Tool class name (CamelCase). Must be unique across all loaded tools. |
| `tool_type` | `"ProcessingTool" \| "DataFrameTool"` | Determines which template to use. |

**Behavior:**
1. The server validates the name (must be a valid Python class name, must not conflict with existing tools).
2. A tool file is created at `workspace/workflows/<current_workflow>/tools/{snake_case_name}.py` using the appropriate template (see Section 5.4).
3. Custom tools in this workflow directory are auto-discovered by the server.
4. The response returns only after the source is registered. The frontend then refreshes the registry and opens the returned source path through `POST /editor/open`.

**Response (HTTP 201):**

```json
{
  "name": "MyNewTool",
  "tool_type": "ProcessingTool",
  "path": "/path/to/workflow/tools/my_new_tool.py",
  "source_kind": "custom",
  "editable": true
}
```

**Error responses:**

| Code | Condition |
|------|-----------|
| 400 | No workflow context is available |
| 409 | Tool name already exists |
| 422 | Invalid class name or tool type |
| 403 | Webapp mode (tool creation disabled for security) |

**Webapp restriction:** This endpoint returns 403 in webapp mode unless the file-only `enable_unsafe_webapp_features` debug flag is enabled.

#### `DELETE /tools/{tool_name}`

Deletes a custom tool.

**Behavior:**
1. The server checks if the tool is used in any saved workflows.
2. If used, the response includes a warning with the list of affected workflows.
3. The tool file is deleted from disk.
4. The tool is removed from the registry and the Tools Panel.

**Response (success with warning):**

```json
{
  "deleted": true,
  "warning": "Tool is referenced by saved workflows.",
  "affected_workflows": ["my_workflow", "test_pipeline"]
}
```

**Error responses:**

| Code | Condition |
|------|-----------|
| 400 | Target is not a workflow-local custom tool or no workflow context is available |
| 403 | Webapp mode with unsafe source editing disabled |
| 404 | Tool not found |

#### `PATCH /tools/{tool_name}`

Renames a custom tool.

**Request body:**

```json
{
  "new_name": "MyRenamedTool"
}
```

**Behavior:**
1. The server validates the new name (same rules as `POST /tools`).
2. The tool file is renamed on disk.
3. The class name inside the file is updated.
4. The tool registry is updated.
5. After the endpoint succeeds, the frontend emits a rename event and mounted canvases reconcile nodes that reference the old tool name.

**Response (success):**

```json
{
  "old_name": "MyNewTool",
  "new_name": "MyRenamedTool",
  "path": "/path/to/workflow/tools/my_renamed_tool.py"
}
```

**Error responses:**

| Code | Condition |
|------|-----------|
| 400 | Target is not a workflow-local custom tool or no workflow context is available |
| 403 | Webapp mode with unsafe source editing disabled |
| 404 | Tool not found |
| 409 | New name conflicts with existing tool |
| 422 | Invalid new class name |

### 5.2 Frontend — Tools Panel

The Tools Panel ([v1 Section 3.4](platform_specs_v1.md#34-tools-panel-left-sidebar)) includes a **Create Tool** button at the bottom of the panel.

**Create Tool button behavior:**
1. Opens a modal dialog with:
   - **Name field:** Text input for a user-facing tool name. The frontend derives and displays the Python class name, for example `my custom tool` -> `MyCustomTool`, then validates the derived class name in real time (valid Python identifier, starts uppercase, no conflicts).
   - **Tool type dropdown:** `ProcessingTool` (default) or `DataFrameTool`.
   - **Cancel / Create buttons.**
2. On "Create": sends `POST /tools` with the derived class name and tool type.
3. On success: the new tool appears in the Tools Panel, and its source file is opened in the Code Editor Panel.

**Delete and rename:** Available via right-click context menu on custom workflow tool rows in the Tools Panel. Package-installed tools cannot be deleted or renamed (context menu items are hidden).

**Manage Tools custom package install:** The Manage Tools dialog includes an inline footer below the package TreeTable labelled **Install tool package**. It is not a table-row action, search field, or separate modal, because unknown package sources cannot be listed before installation. The footer contains, in one line where width allows: a GitHub/GitLab repository URL text field, an **or** label, a **Select .zip archive** button, and an **Install** button. Selecting an archive clears the URL and typing a URL clears the selected archive. The backend validates that the source is a BioImageFlow tool package, installs it into the user's tool package store, indexes its available versions, and shows it as a normal package row with install/uninstall and "Set current" controls. Repository installs use `POST /tools/packages/import-url`; zip installs use `POST /tools/packages/import-archive`. Failed validation reports missing package metadata, invalid tool classes, or dependency-resolution errors without modifying the active package store.

### 5.3 Custom Tool Discovery

GUI-created custom tools are placed in `workspace/workflows/<id>/tools/`. The
server discovers custom tools for saved workflows and refreshes the custom-tool
registry when workflow-local files are edited. Custom tools appear in the Tools
Panel alongside package-installed tools, distinguished by a "Custom" badge. In
the Manage Tools dialog, the synthetic package row is labelled **Custom workflow
tools** and does not show package-version install controls.

### 5.4 Tool Templates

#### ProcessingTool Template

```python
"""Custom ProcessingTool: My Tool."""

from pathlib import Path
from typing import Annotated, Any

from bioimageflow_core import (
    Arguments,
    Category,
    Connectable,
    GENERAL_ENV,
    GUIMeta,
    IOModel,
    ImageSpec,
    Layout,
    ProcessingTool,
    Semantic,
    Template,
)


class MyTool(ProcessingTool):
    """Processing tool that operates on individual rows."""

    display_name = "My Tool"
    documentation = "Describe what this custom processing tool does."
    category = Category.IMAGE_PROCESSING
    tags = ["custom"]
    environment = GENERAL_ENV

    class Inputs(IOModel):
        input_image: Annotated[
            Path,
            ImageSpec(
                semantics={Semantic.INTENSITY},
                layouts={Layout.PLANAR, Layout.PLANAR_CHANNEL},
            ),
            GUIMeta(
                display_name="Input image",
                description="Image to process.",
                connectable=Connectable.BY_DEFAULT,
            ),
        ]

    class Outputs(IOModel):
        output_image: Annotated[
            Path,
            ImageSpec(semantics={Semantic.INTENSITY}),
            GUIMeta(
                display_name="Output image",
                description="Processed output image.",
            ),
        ] = Template("{input_image.stem}_out{ext}")

    def process_row(self, arguments: Arguments, *, context: Any = None) -> "Outputs":
        import shutil

        input_path = Path(arguments.input_image)
        output_path = Path(arguments.output_image)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Replace this pass-through copy with your processing code.
        shutil.copyfile(input_path, output_path)
        return self.Outputs(output_image=output_path)
```

The scaffold uses the library's current `Annotated[Path, ImageSpec(...), GUIMeta(...)]` image-field contract directly.

#### DataFrameTool Template

```python
"""Custom DataFrameTool: My Transform."""

from typing import Annotated, Any

from bioimageflow import DataFrameTool, Passthrough
from bioimageflow_core import Category, Connectable, GUIMeta, IOModel


class MyTransform(DataFrameTool):
    """DataFrame tool that transforms an entire dataframe."""

    display_name = "My Transform"
    documentation = "Describe what this custom dataframe transform does."
    category = Category.UTILITIES
    tags = ["custom"]

    class Inputs(IOModel):
        column_name: Annotated[str, GUIMeta(
            display_name="Column name",
            description="Optional column name used by your transform.",
            connectable=Connectable.NEVER,
        )] = ""

    class Outputs(Passthrough):
        pass

    def transform(self, df: Any, arguments: Any) -> Any:
        result = df.copy()

        # Modify result here. Passthrough outputs preserve upstream columns.
        return result
```

The template class name is dynamically replaced with the user-provided name
(converted to appropriate casing). ProcessingTool output path defaults must use
`Template(...)`; raw string or `Path` defaults are rejected by the library for
path-typed outputs.

### 5.5 Integration with v1 Features

- **Tool hot-reload:** Newly created tools are immediately watched by the file watcher. Edits trigger hot-reload as with any other tool.
- **Code Editor Panel:** After creation, the tool source is automatically opened in the Code Editor Panel for immediate editing.
- **Tools Panel:** Custom tools appear in the panel with a "Custom" badge and support drag-and-drop onto the canvas.
- **Webapp mode security:** `POST /tools`, `DELETE /tools/{tool_name}`, and `PATCH /tools/{tool_name}` are disabled in webapp mode (403 Forbidden), and source-opening controls are hidden, unless `enable_unsafe_webapp_features === true`. The "Create Tool" button is hidden when `deployment_mode === "webapp"` and the unsafe debug flag is false.

### 5.6 Path Picker Metadata

`GUIMeta` adds an optional `path_picker` hint for path-typed inputs with values `"file"`, `"folder"`, or `"both"`.
The library's canonical input schema serializes this as `path_picker: "file" | "folder" | "both" | null`, and the platform passes it through unchanged in `GET /tools`.
The hint controls Node Panel picker actions only and does not validate the runtime filesystem value.
Missing or `null` metadata remains backward-compatible: image path types use file selection and a plain `Path` allows both files and folders.

The common-tools `Files.Inputs.path` field declares `path_picker="folder"` because it scans a directory.
In desktop mode the Node Panel therefore shows only the **Select folder** action for that field.
In browser mode server-folder browsing is unsupported, so folder-only fields keep manual text entry without a picker button; `"both"` fields retain the Dataset Browser file action.

---

## 6. Consolidated Data Table Views

### 6.1 Source Resolution and Upstream Depth

The Data Table Panel shows one consolidated table when the selected DataFrame outputs have an obvious lossless alignment.
Every explicitly selected output is an **anchor**, and every output added only by upstream traversal is **context**.
Rows belonging to anchors must never be silently discarded.
Context rows that are unrelated to the anchor rows may be omitted.

The panel provides an integer **Upstream levels** spinbox with minimum `0`, default `0`, and a maximum equal to the greatest reachable upstream distance from the current selection.
The frontend follows incoming column-reference and positional edges through the active workflow graph, includes all branches up to the requested depth, deduplicates outputs, and orders them deterministically from upstream to downstream.
The value is local UI state for each open workflow editor, is discarded when that editor context is released, and is not persisted in the workflow or sent as a canvas/session identifier.

For `A > B > C > D`, selecting only `D` with depth `2` sends `B` and `C` as context and `D` as the anchor.
Selecting `A`, `B`, and `C` makes all three outputs anchors even when the depth is `0`.
If explicitly selected anchors belong to independent connected components, the frontend skips consolidation and immediately displays the stacked fallback.

Published sub-workflow outputs are resolved by the frontend to scoped internal node IDs.
Only published columns are requested, and their published names are supplied as presentation aliases.

### 6.2 Obvious Merge Rules

The frontend owns graph traversal and sends an explicit ordered source list.
The backend owns record loading, index alignment, column construction, sorting, and pagination.
The query API therefore needs a workflow identifier but no canvas identifier, editor session, snapshot session, graph, or revision.

Before loading data, the backend resolves the latest immutable result record for every source.
It then loads those exact records so one response cannot mix record generations when `latest` pointers change during the request.

A consolidation is obvious when every source has unique stringified indices and each output row can be aligned using either an exact index or one unambiguous nearest ancestor in the `::` lineage.
The backend uses the BioImageFlow core lineage parser so execution and display interpret exploded indices identically.
Parent values are repeated for descendant rows, and the finest selected anchor supplies the candidate output index.

Every row from every anchor must be represented by that candidate index, and every candidate row must resolve against every anchor.
This makes exact-index transforms and parent-to-child explosions mergeable while forcing filtered, aggregated, reindexed, duplicated, or divergent selected results to fall back when their alignment would hide selected data.
Extra rows from context sources do not have to appear.

When all requested sources are empty, the backend returns a merged empty table with its columns.
Mixed empty and non-empty anchors fall back, and an empty anchor with non-empty context also falls back.

Columns remain in source order and original DataFrame column order.
If two columns have the same aliased display name, both are retained and qualified with their source label.
The API uses opaque unique column IDs for values and sorting rather than using display labels as identifiers.
No columns are coalesced implicitly.

The complete merged projection is constructed and sorted with a stable sort before pagination.
Every returned row records the original absolute row position for every source, allowing image thumbnails, Napari, Avivator, reveal, and copy actions to address the original node result.

The platform does not offer outer, inner, left, Cartesian, aggregation, or other user-selectable join strategies in this panel.
Users who need a semantic join must add an explicit DataFrame tool to the workflow.

### 6.3 Automatic Stacked Fallback

Expected merge incompatibilities return HTTP 200 with `mode: "stacked"`, a stable reason code, and a user-facing explanation.
Reasons include non-unique indices, anchor rows that would be lost, incompatible lineage, and incompatible empty results.
The frontend displays an information banner and then renders the existing per-source DataFrames vertically, including their individual pagination and CSV controls.
The existing five-table display limit remains active in stacked mode.

Invalid source IDs, missing outputs, unknown columns, invalid sorting fields, and storage failures remain request errors rather than merge fallbacks.
HTTP 409 while immutable result data is still being published uses the existing bounded retry behavior and keeps any previous projection visible until a current response arrives.
An obsolete query response must not replace a newer selection, depth, sort, page, workflow, or editor-context request.

### 6.4 Query and CSV Contracts

`POST /api/v1/data-table/query` accepts a frontend-resolved source list and view state:

```json
{
  "workflow_id": "segmentation/nuclei",
  "sources": [
    {
      "node_id": "files_1",
      "role": "context",
      "label": "Input files",
      "tool_name": "Files",
      "columns": null,
      "column_aliases": {}
    },
    {
      "node_id": "measure_1",
      "role": "anchor",
      "label": "Measure",
      "tool_name": "MeasureObjects",
      "columns": ["area"],
      "column_aliases": {"area": "published_area"}
    }
  ],
  "page": 0,
  "page_size": 50,
  "sort_by": null,
  "sort_order": "asc"
}
```

At least one source must be an anchor, and `node_id` values must be unique within a request.
`columns: null` selects every column, while a list selects and orders only those columns.

A merged response has this shape:

```json
{
  "mode": "merged",
  "sources": [],
  "columns": [
    {
      "id": "s0:path",
      "label": "path",
      "type": "Path",
      "source_node_id": "files_1",
      "source_column": "path"
    }
  ],
  "rows": [
    {
      "index": "image_001::object_2",
      "values": {"s0:path": "/data/image_001.tif"},
      "source_rows": {"files_1": 0, "measure_1": 12}
    }
  ],
  "total_rows": 1,
  "page": 0,
  "page_size": 50
}
```

A stacked response has `mode: "stacked"`, echoes the resolved sources, and provides `reason` and `message` fields.

`POST /api/v1/data-table/csv` accepts the same workflow, sources, and sorting fields without pagination.
It uses the same consolidation service and streams the complete sorted projection as CSV.
If consolidation is not possible, it returns HTTP 409 and the frontend retains the individual CSV actions shown by stacked mode.

### 6.5 Image-Valued Plain Paths

Typed `ImageFile`, `ImageShared`, and `MaskPath` columns retain their existing image behavior independently of filename suffix.
For an ordinary `Path` column, image behavior is determined per cell and never inferred for an ordinary `str` column.

The recognized case-insensitive suffixes are `.tif`, `.tiff`, `.ome.tif`, `.ome.tiff`, `.png`, `.jpg`, `.jpeg`, `.czi`, `.lsm`, and `.nd2`.
A matching plain `Path` cell displays the thumbnail with its pending or unavailable state and shows the existing Napari, Avivator, reveal, and copy actions.
A non-matching `Path` cell shows the path, reveal, and copy actions without issuing a thumbnail request.

This feature uses the filename heuristic only.
It does not add a dynamic `Files` output type, persist a resolved result schema, or infer an image type from DataFrame contents.

---

## 7. Updated API Endpoint Summary

New and modified endpoints introduced in v2:

| # | Method | Endpoint | Description | When Used |
|---|--------|----------|-------------|-----------|
| 1 | `POST` | `/api/v1/tools` | Create a new tool from template | "Create Tool" button in Tools Panel |
| 2 | `DELETE` | `/api/v1/tools/{tool_name}` | Delete a custom tool | Context menu on custom tool in Tools Panel |
| 3 | `PATCH` | `/api/v1/tools/{tool_name}` | Rename a custom tool | Context menu on custom tool in Tools Panel |
| 4 | `POST` | `/api/v1/workflows/{id}/export` | Export workflow to library archive | "Export" in Workflows Panel menu |
| 5 | `POST` | `/api/v1/workflows/import` | Import workflow from library archive | "Import" in Workflows Panel menu |
| 6 | `POST` | `/api/v1/editor/open` | Open file/folder in code editor | "Open" from Data Table path cells |
| 7 | `POST` | `/api/v1/editor/open-tool` | Open workspace project and focus a tool file | "Open in editor" from Tools Panel or node source links |
| 8 | `GET` | `/api/v1/editor/status` | Check code-server availability and URL | Code Editor Panel initialization |
| 9 | `POST` | `/api/v1/nested-workflow-snapshots/open` | Resolve or create one private nested editor snapshot | Before a sub-workflow editor mounts |
| 10 | `GET` | `/api/v1/nested-workflow-snapshots/{session_id}` | Read an accepted private nested snapshot | Recovery and diagnostics |
| 11 | `PUT` | `/api/v1/nested-workflow-snapshots/{session_id}` | Replace the complete nested graph with revision CAS and validation | Background nested editing persistence |
| 12 | `DELETE` | `/api/v1/nested-workflow-snapshots/{session_id}` | Delete a private snapshot with revision CAS | Confirmed close or discard |
| 13 | `POST` | `/api/v1/data-table/query` | Return a paginated merged Data Table projection or an automatic stacked fallback | Selection, upstream depth, sorting, or pagination changes |
| 14 | `POST` | `/api/v1/data-table/csv` | Download the complete sorted merged projection as CSV | CSV action in merged mode |

**Modified endpoints (behavioral changes only, same URL/method):**

| Endpoint | Change |
|----------|--------|
| `PUT /api/v1/workflow-drafts/{id}` | Root-canvas full-graph persistence also returns recursive validation and derived statuses for the accepted draft revision. |
| `PUT /api/v1/graph` | Stateless compatibility/transient validation invokes the BioImageFlow library recursive sub-workflow validator without retaining an active graph. Errors reference scoped node paths. |
| `GET /api/v1/settings` | Response includes `external_editor` and `enable_unsafe_webapp_features` fields for code editor fallback and webapp debugging. |
| `PATCH /api/v1/settings` | Accepts `external_editor` field updates. Rejects `enable_unsafe_webapp_features`; that flag is file-only. |

---

## 8. Updated Keyboard Shortcuts

No new keyboard shortcuts are introduced in v2. All existing shortcuts from v1 apply unchanged:

- **Ctrl+C / Ctrl+V** now supports cross-workflow clipboard payloads (behavioral change, same keys).
- **Ctrl+S** within a sub-workflow tab saves changes to the parent workflow.

The right-click context menu gains a new entry for selected nodes: "Create sub-workflow". No keyboard shortcut or current shortcut-assignment UI is provided for this action; customizable shortcut UI remains a future v3 proposal.
