# BioImageFlow Platform Specification v2

This document is normative for the implemented v2 platform.
It extends the interaction and workspace foundations in [`platform_specs_v1.md`](platform_specs_v1.md) with recursive workflows, durable editing, explicit provenance, and trusted Python authoring.

## 1. One Recursive Workflow Model

A workflow has the same meaning at the workspace root and when used as a node inside another workflow.
Every workflow is represented by a recursive `GraphState`, has an explicit interface, and may contain tool nodes and workflow nodes.

Root and nested editors use the same canvas, node model, edge model, validation rules, and interface controls.
They differ only in persistence context: a root canvas owns a workspace draft, while a nested canvas owns a private durable editor snapshot that is explicitly applied to its parent node.

The platform does not use a sentinel tool, a second child graph language, duplicated interface arrays, or a derived persisted library document.

## 2. Canonical Graph Document

`GraphState` is the single editable and persisted workflow definition:

```json
{
  "schema_version": 2,
  "name": "measure_cells",
  "display_name": "Measure cells",
  "nodes": [],
  "edges": [],
  "interface": {"inputs": [], "outputs": []},
  "config": {
    "engine": "wetlands",
    "execution": "parallel"
  }
}
```

`schema_version`, `name`, `display_name`, `interface`, and `config` are required at every depth.
The graph owns layout, collapsed state, enabled state, parameter values, resource overrides, and output templates exactly once.
Processing-tool resources are typed portable per-node overrides for CPU, GPU, memory, GPU memory, and maximum concurrency.
They describe worker requirements rather than guaranteed limits, inherit the tool declaration when absent, and do not affect cache identity.
`GraphState.config.execution` owns sequential or parallel scheduling; application settings only choose the default for a new workflow.
Execution target profiles and durable remote-run state never enter `GraphState`.

The workspace `workflow.json` is a `WorkflowDocument` envelope containing a platform document version, the canonical graph, workspace metadata, the artifact hash, optional Python authoring provenance, and owned workflow-local source identifiers.
Runtime translation to the BioImageFlow library happens in memory from the accepted graph snapshot.
Canonical platform output is schema version 2 at every recursive depth.
Schema-version-1 input is accepted only through explicit recursive normalization that adds no viewer declarations; schema-v1 input carrying schema-v2 viewer fields and every unknown field are rejected instead of dropped.
Portable output schemas use the strict library-owned `ViewerSpec` wire, tool/workflow nodes may carry output-keyed `viewer_additions`, and public workflow outputs may carry a `viewer_addition`.

## 3. Node Types

Nodes use an explicit discriminator.
A tool node has `type: "tool"`, a tool identity, parameters, resources, output templates, position, and GUI state.

A workflow node has `type: "workflow"`, an embedded canonical `GraphState`, parent-instance bindings, optional workspace source provenance, position, and GUI state:

```json
{
  "type": "workflow",
  "id": "segment_and_measure",
  "name": "Segment and measure",
  "position": [420, 180],
  "enabled": true,
  "collapsed": false,
  "workflow": {
    "schema_version": 2,
    "name": "segment_and_measure",
    "display_name": "Segment and measure",
    "nodes": [],
    "edges": [],
    "interface": {"inputs": [], "outputs": []},
    "config": {
      "engine": "wetlands",
      "execution": "parallel"
    }
  },
  "bindings": {},
  "source": null
}
```

The embedded graph is execution authority; optional `source` data is provenance only.
Workflow nodes use a thick border and derive all visible pins from `workflow.interface`.
Double-clicking a workflow node or selecting **Open workflow** opens its graph in a nested editor tab.

## 4. Edges And Endpoint Handles

Edges are discriminated as `column` or `dataframe`.
A column edge connects one named output field to one named tool input or stable workflow input ID.
A DataFrame edge connects a whole DataFrame to either a positional input or a named DataFrame input.
DataFrameTool keyword parameters accept constants, not column edges or node shorthand, and their serialized input metadata reports `connectable="never"`.
Published field ports may supply constant values to these parameters; a column binding through a workflow field port is rejected when its ultimate target is a DataFrameTool parameter.

The frontend uses a versioned endpoint-handle codec.
Handles distinguish DataFrame output, tool input, tool output, DataFrame position, named DataFrame input, workflow input ID, and workflow output ID.
Display labels are never structural endpoint identities.

## 5. Workflow Interfaces

Every graph has one `WorkflowInterface` with `inputs` and `outputs`.
Each port has an immutable `id` and an editable `name`.

Workflow inputs are either field inputs with one or more internal targets or DataFrame inputs with one or more internal targets.
Workflow outputs map a stable port ID to an internal node and output.

The Node Panel uses **Expose as workflow input**, **Expose as workflow output**, **Workflow input name**, and **Workflow output name**.
For a `DataFrameTool` with `accepts_upstream=true`, the Nodes panel has a separate **Published DataFrame inputs** section with **Publish DataFrame input**.
Each click directly publishes the next unoccupied positional DataFrame slot, with no separate add-input step and no UI-imposed maximum.
Each row contains an editable **Workflow input name**, its one-based target label (for example, **DataFrame 1**), and **Unpublish**.
Publications reserve slots alongside internal DataFrame connections; the canvas shows those slots plus the next free slot and prevents an internal edge from also targeting a published slot.
Removing a publication or an internal connection compacts the remaining positional targets and edges together without changing surviving public port IDs or names.
Source tools that do not accept upstream DataFrames do not offer positional publication.
For a selected workflow node, the same section can publish each unconnected child DataFrame port through the enclosing interface, targeting the child's stable port ID rather than inventing positional inputs on the workflow node.
These actions use the ordinary graph mutation lock, undo/redo, draft persistence, and nested-save reconciliation paths.
Renaming a port changes its label while preserving its ID and parent connections.
Removing or changing a connected port requires explicit confirmation and atomically removes affected bindings and edges.

## 6. Creating And Reusing Workflows

### 6.1 Group Into Workflow

**Group into workflow** replaces the selected nodes with one workflow node in a single undo transition.
The operation moves selected nodes and internal edges into an embedded graph, converts each incoming column or DataFrame edge into an independent workflow input, converts outgoing column edges into workflow outputs, and rewires parent edges through stable port IDs.
Selections with no interface remain valid, and detached or otherwise unexposed internal branches are preserved.

### 6.2 Saved Workflow Drag And Drop

Dragging a saved workflow from the Workflows panel embeds its exact saved graph and all required workflow-local tool sources.
The node records workspace provenance with the saved workflow ID and artifact hash.
`POST /api/v1/workflows/{destination}/prepare-embedding` captures the source graph and saved files under source/destination identity locks, checks the destination generation and containment, and materializes fresh destination-owned source identities before returning the insertable graph.
The canvas then inserts that graph through its normal draft persistence flow; the preparation operation does not modify the destination graph.
Preparation only adds fresh, unreferenced files, so it does not take an execution mutation lease; the eventual graph insertion remains execution-guarded.

Workflow-local sources are ordinary editable files in destination-owned `tools/<source-id>/` directories.
Each directory contains a `module.json` identity/layout manifest, with no executable source text, and the original Python files and package assets.
Source identifiers bind nodes to working directories and remain stable across source saves; they are not mutable content hashes.
Package tools remain versioned package dependencies.
Same-named local tools with different content must coexist without registry shadowing.
Hot reload observes editable source directories and triggers canvas validation even for implementation-only changes.
Validation includes `node_tools`, keyed by scoped node identity, so an imported node's schemas come from its bound source rather than a same-named catalog entry.
Invalid edits remain visible on disk and invalidate execution; keeping previous catalog metadata must never cause Run to execute old code.

Portable archives are transport artifacts only.
Import validates and unpacks all custom source files, stages the ordinary workspace document and files together, and publishes the workflow directory only after preparation succeeds.
When import receives an explicit `name_override`, it uses the destination path as the workspace ID and its leaf name as both root graph `name` and `display_name`, before calculating the artifact hash and persisting the document.
Imports without an override preserve the archive's graph names, and renaming an import does not rename embedded workflows or alter the existing workflow that caused a collision.
There is no special opened-bundle workflow mode and no reader or migration for the previous `.bioimageflow/dependencies/*/source.json` storage layout.
Previously imported workflows using that layout must be imported again from their portable archives.
Export captures the current editable files, including package helpers and assets, and packages them through the public library archive API.

The backend rejects direct or transitive containment cycles on embed, paste, import, duplicate, source update, save, and move.
Frontend cycle checks are advisory only.

### 6.3 Clipboard

Copying a workflow node includes the complete recursive graph.
Pasting preserves all child interface IDs while assigning new parent node and edge IDs.
Cross-workflow paste stages required local sources atomically in the destination workspace.

## 7. Nested Editing Sessions

Opening a workflow node resolves or creates a private durable snapshot before mounting its editor.
A root-owned snapshot is bound to the canonical workflow ID, root canvas identity, and workflow identity generation.
A deeper snapshot is owned by its parent snapshot session UUID.

The nested editor uses the standard canvas and panels.
Edits remain private until Save explicitly applies the accepted snapshot to the parent workflow node.
Closing a dirty nested tab requires discard confirmation.
Closing a nested tab whose durable snapshot still owns an open descendant is refused until the descendant closes; a failed snapshot deletion keeps the tab and private state available for an explicit retry and shows the failure reason.
Opening a custom node source in a nested editor creates and binds a private editable copy of that source under a new identity, using the snapshot revision guard.
All references to that source within the private graph share the copy; other workflow instances retain their existing files.
Reopening the source returns the same working file, and applying the graph preserves its new source binding.

Saving preserves compatible parent bindings and edges by stable port ID.
Removed or incompatible connected ports require confirmation.
If the parent node changed or disappeared since the editor opened, apply reports a conflict and changes nothing.
During execution, root and nested editors are mutation-locked uniformly.
If a node context-menu Delete or Group action is invoked while execution owns the canvas, the graph and history remain unchanged and the editor reports the lock visibly.
Outside execution, ordinary root, draft, and nested mutations serialize through the same execution-admission gate: an admitted mutation blocks Run, concurrent mutations wait, and only an actually starting or running execution rejects a mutation as locked.

## 8. Validation And Translation

All accepted root drafts, nested snapshots, execution requests, cache operations, import, and export use the same recursive graph translator and library compiler.

Validation covers recursive graph structure, discriminator correctness, unique node/edge/interface IDs, field and DataFrame interface targets, binding and edge compatibility, recursive tool availability, workflow-local source ownership, workspace containment, source-update preconditions, and execution mutation locking.
It also validates ProcessingTool-only resource overrides, tool-declared resource floors, concurrency caps, exact execution intent, target availability, and invocation-only remote path choices.
Errors use scoped paths such as `segment_and_measure/cellpose_segmenter`.

Full Run rejects every diagnostic from complete-graph compilation. Run Selected derives its requested root nodes and transitive upstream root nodes from the accepted graph edges and ignores only diagnostics whose scoped node path proves ownership by an unrelated root node. Descendant diagnostics within a selected or upstream workflow boundary, global or unattributable diagnostics, unknown or unresolved requested targets, and a missing compiled workflow remain blocking.

The stateless graph endpoint validates the same canonical graph shape but does not retain editor state.

## 9. Execution And Status

Execution compiles the accepted recursive graph to one flat plan.
Attached progress callbacks are fenced to the active running execution context; a delayed event from an earlier run cannot change a later run's status or emitted progress.
Internal nodes receive scoped structural IDs.
Caching remains per internal tool node, and logs, progress, validation, cache clearing, and output lookup retain scoped paths.
Clearing selected outputs updates the matching workflow's retained live node-status snapshot without changing the completed run's historical result; a reconnect therefore preserves the cleared and downstream out-of-date presentation.
An authoritative root-draft GET also recomputes cache-derived statuses for its accepted graph against the workflow's current storage, so a backend restart does not revive pre-Clear badges from persisted validation. This is a response-only projection: it does not change draft graph/revision or other durable metadata. A `pending_upstream` node is `out_of_date` only if its latest output remains published, and `unexecuted` otherwise. The accepted draft, workflow identity generation, and storage path are fenced against Clear and concurrent workflow mutations before the final plan and latest-output read.
Each compilation captures current source bytes before loading the library workflow, without waiting for filesystem notifications.
Source-bound nodes select the worker-capable engine without consulting a same-named global catalog class.
The captured library payload assigns content-derived source-module identities, including helper and asset contents, to isolate Python imports between source versions.
An execution retains its captured code while later source saves affect subsequent runs.

Selecting a workflow node for Run Selected targets that workflow boundary and schedules its enabled internal completion dependencies.
The platform does not prune or rebuild a partial graph before compilation.
Run Selected compiles the same complete accepted graph as full Run; only its post-compilation diagnostic acceptance is limited to the selected-plus-upstream root scope. It never turns an empty, unknown, unresolved, or mixed target list into an untargeted computation.

A workflow node projects aggregate status from its descendants while preserving the failing or cancelled scoped path.
Detached internal failures still make the workflow node fail and block its downstream consumers.

The target selector beside Run offers the built-in **Local** target and available managed remote profiles.
Local execution preserves Direct and Wetlands behavior.
The current platform compiler selects Direct for ordinary DataFrame-only graphs and Wetlands for enabled ProcessingTools, source-bound tools, or recursive graphs requiring those capabilities.
DataFrameTools run in the orchestrator with either backend; worker acceptance requires executing an actual ProcessingTool and checking its process identity and outputs.
Managed remote execution uses the public `bioimageflow.cluster.RemoteCluster` lifecycle and follows `describe cluster → build workflow → submit → save run ID → reconnect → download result`.
Changing the target is application state and never changes the workflow graph.

The Execution panel is the engine-neutral authority for current and retained runs.
An `ExecutionSnapshot` identifies the workflow and accepted draft, target, engine and scheduling policy, normalized and backend states, timestamps, job counts, backend allocation when available, scoped job snapshots, structured diagnostics, action availability, retry relationships, result state, and a monotonically increasing revision.
Direct, Wetlands, and managed remote runs use the same snapshot presentation.
Each job is one compiled scoped node attempt; a scheduler allocation or Parsl worker task is not presented as a workflow job.

Managed runs are monitored only through public snapshots, sequence-based progress, and structured diagnostics.
They do not expose a managed-run log action.
Cancellation, retry planning and start, result download, and cleanup delegate to the public run or cluster methods, and UI availability is derived from capability and diagnostic reports.
Public run observations are projected through a strict known-field allowlist before persistence, and structured public diagnostics replace arbitrary exception text wherever the library supplies them.

A managed run persists the durable run ID plus host, cluster root, and progress sequence so restart attachment does not require the original workflow or trusted configuration files.
It also persists the deterministic workspace-owned result-bundle path so a verified local result can be reused after restart or remote cleanup.
Retry recovery persists the exact public retry plan and planned child ID, attempts child attachment first, and repeats `start_retry()` only after the public API definitively reports that the child is absent.

## 10. Saved-Source Provenance

Workspace provenance has exactly this shape:

```json
{
  "kind": "workspace",
  "workflow_id": "analysis/segment",
  "artifact_hash": "sha256:..."
}
```

Editing an embedded workflow changes only that snapshot.
Changing or deleting the saved source never mutates or breaks an existing parent automatically.

When provenance exists, the context menu offers **Open source workflow**, **Update from source**, and **Detach from source**.

Update uses a preview/apply protocol.
Preview captures the destination identity, target workflow-node path, parent and source artifact hashes, incompatible or removed stable ports, affected edges and bindings, and workflow-local source changes.
Apply requires the immutable token and exact destructive-effect confirmation, rechecks every captured value under the mutation gate, stages sources, and commits atomically.
A conflict changes nothing.

An open editor at or below the replacement target blocks update or detach until it is applied or discarded.
Workspace moves update provenance IDs atomically without changing embedded content or artifact hashes.

The artifact hash is a deterministic digest of canonical recursive graph content and referenced owned sources.
It excludes timestamps, workspace paths, runtime state, provenance labels, and Python authoring provenance.
Layout is included because it is part of the editable embedded snapshot.

## 11. Python Authoring

A workflow directory may contain a trusted `workflow.py` authoring source.
It must export `build_workflow`, which is invoked exactly once and must return a standalone BioImageFlow `Workflow`.

Python is an authoring input, never a persisted execution model.
The build operation materializes the returned workflow into the same canonical `GraphState`, validates it, stages its documented runtime-source bundle, and saves only after preview and confirmation.

The GUI exposes **Build from Python source** in trusted desktop mode.
The request never accepts an arbitrary path or module string.
The backend resolves only the addressed workflow's allowed authoring source, rejects path or symlink escapes, and disables the operation in ordinary webapp mode.

The authoring hash covers a canonical manifest of all allowed Python files under the authoring root, including imported local helpers.
Preview captures immutable bytes and apply conflicts if the live manifest changed.
Each build uses a fresh import context.

Run, nest, copy, reopen, and export operations use only the materialized graph and never import the Python authoring source.

## 12. Persistence, Drafts, And Lifecycle

Opening an existing workflow with a missing owned-source manifest or Python file returns HTTP 409 with the stable code `workflow_source_missing` and actionable workflow-relative file details.
When an older `.bioimageflow/dependencies/<source-id>/source.json` record exists, the message identifies the unsupported layout and directs the user to reimport an archive or manually convert the records; opening does not perform conversion.
HTTP 404 remains reserved for an absent workflow on this read path.

Root drafts use revision compare-and-swap, a saved-artifact baseline, validation, dirty state, and writer metadata.
Nested snapshots use their own revision compare-and-swap and ownership chain.
Save and Run operate on exact accepted snapshots.
Remote draft changes are resolved explicitly before destructive or execution operations.
**Save agent version as copy** preserves the fetched agent graph and all recursively referenced workflow-local sources, including sources absent from the saved baseline.
It copies editable `tools/` files, excludes results and draft/runtime state, and leaves both the original saved workflow and its current draft unchanged.
The destination becomes visible only after its graph and sources are prepared successfully; failures do not leave an empty workflow.
The copy request carries the captured source identity generation to reject a deleted and recreated source.

Workflow identities are path-derived and carry durable identity generations.
Move, rename, delete, duplicate, and save operations bind to captured identities so delayed responses cannot mutate a recreated same-ID workflow.
Moves update drafts, retained snapshots, and provenance references atomically.

The platform keeps an atomic, revisioned execution registry under the active workspace, separate from graphs and cache storage.
The registry is an index and presentation cache rather than authority for managed run state.
It stores only non-secret profile attribution, accepted snapshot identity, durable run identity, managed attachment tuple, progress cursor, retry and cleanup journals, managed result-bundle identity, allowlisted observation fields, and normalized presentation state.
Listings, startup recovery, and new runs use the current workspace; an already loaded or created execution remains bound to its original workspace for registry, journal, poller, and result writes after a workspace switch.
On restart, managed entries attach through `RemoteCluster(host=..., root=...).attach(run_id)` and converge from public run observations without importing the original cluster script or resubmitting.
For a succeeded run with a verified retained archive, result access uses the local bundle before attempting remote attachment.

Every named workflow derives its BioImageFlow runtime storage as `<workflow-directory>/results`.
This path is not configurable or persisted in `GraphState` or workspace metadata.
Moving and deleting a workflow naturally carry or remove its results, while duplication copies only the reusable workflow definition and workflow-local tools.

Every direct or merged result-table response pins each displayed source to the library's public `(run_id, node_key, result_key, record_id)` identity captured before the page or projection is built.
For each displayed structural column, the same response carries the viewer declaration captured by that exact retained identity; a captured `null` declaration is distinct from legacy unpinned metadata whose viewer status is explicitly unknown.
Pagination and selected-cell viewer requests reuse that exact identity and never resolve `latest` again; displayed row offsets select only a cell within the pinned artifact and never participate in preference identity.
Legacy retained views without valid provenance remain readable as explicitly unpinned tables, but they cannot use exact selected-cell viewer resolution.
Effective viewer requirements for retained output come from that run-node result's stored viewer metadata, including cache hits, rather than from a mutable current tool schema.

Per-output napari favorites are local state in the separate atomic `viewer-preferences.json` authority described by `platform_specs_napari_environments.md`.
They use a durable workspace UUID plus workflow generation, structural node path, and output key; they never enter graph/archive bytes, execution dependencies, or cache identity.
The workflow move journal advances through artifact, nested-snapshot, and preference rewrite phases before deletion, and preference remapping uses the journaled destination generation.
Stateless graph services use the private workspace fallback `<workspace>/.bioimageflow/runtime`.

The platform publishes a disposable, human-facing view at `<workflow-directory>/results/outputs/latest`.
This view resolves the latest successful result independently for each node and may therefore combine outputs from different workflow runs.
It uses symbolic links when the workflow filesystem supports them and otherwise falls back to portable BioImageFlow pointer files.
Copying is not a publication preference because `latest` is a lightweight projection rather than an independent backup.
Preferences reports the effective publication mode and warning, if any, but does not expose a mode selector.

Workflow export uses one dialog with these platform-owned choices:

- **Workflow only** saves an unsaved addressed root workflow when necessary and downloads the BioImageFlow recursive workflow archive, including owned workflow-local sources but no results.
- **Latest results** downloads materialized copies of the current per-node latest projection; its files may come from different runs.
- **Workflow with results** saves when necessary and downloads a platform results bundle containing the workflow archive plus copied outputs and provenance from exactly one pinned latest successful run.
- **Export latest results to folder** is desktop-only and materializes the current per-node latest projection as ordinary files in a generated child directory of the selected parent.

Results-only exports do not save or mutate the workflow definition and remain available while graph mutation is locked.
Workflow-containing exports use the normal save and mutation barriers.
An empty latest projection or absent successful run is reported as unavailable rather than producing an empty archive.

The desktop folder export writes `.bioimageflow-output-export.json` with schema `bioimageflow.platform.output-export.v1`.
Replacement is allowed only for a directory carrying a valid marker for the same workflow.
Materialization and marker creation complete in a sibling staging directory before an atomic install, and a failed replacement restores the previous marked export.
The selected parent directory and unrelated existing directories are never replaced.

The workflow-and-results bundle writes the top-level manifest `bioimageflow-results-bundle.json` with schema `bioimageflow-results-bundle/v1`.
The manifest identifies the workflow, nested workflow archive and its SHA-256 digest, pinned successful run ID, and copied run-results path.
It is a self-contained export artifact, not a portable workflow archive, and workflow import rejects it with an explicit unsupported-media response.
Only the nested workflow archive inside the bundle is importable.

A workspace-document backup, when provided, remains a separate platform artifact and is not accepted as a BioImageFlow workflow archive.

### Bundled demo workflows

The application loads demo bundle version 2, whose root graph and every recursively embedded graph use canonical schema version 2.
The versioned platform templates are generated deterministically from the maintained Python examples for **Fish Analysis** and **Parameters Space Exploration**, and generation fails if any bundled graph is not recursively schema v2.
The examples are self-contained definitions that download their public input data into workflow-managed run assets and do not reference repository-local datasets.

Initialization installs both templates under `Demo/` only when the active workflow root did not exist before initialization.
An existing workflow root is not seeded merely because it is empty, and a workspace change applies the same new-root rule.
No launcher post-install hook, user-home marker, or demo-folder filesystem watcher participates in this decision.

Demo status is derived from each canonical path and `metadata.bundled_template` identity.
A matching template identity is installed regardless of its recorded bundle version and is never overwritten by restart, application upgrade, bundle version change, or an explicit install call; an absent identity is missing; an occupied canonical path without matching provenance is a conflict.
Moving or renaming a demo detaches it from canonical status, so a later install may create a fresh copy at the canonical path.

Settings exposes explicit install and remove actions.
Install is idempotent, installs only missing templates, refuses canonical conflicts, and remains locked during execution.
Remove deletes only recognized canonical demo workflows through the normal generation-aware deletion coordinator, preserves unrelated `Demo` children, and removes the folder only if it is empty.
Missing tool packages are reported through the ordinary dependency UI and are never installed implicitly.

## 13. Node Data Inspection

The v1 Data Table panel is named **Node Data** in v2 because it inspects the output DataFrames owned by selected nodes rather than arbitrary datasets.
For a workflow node, exposed outputs resolve recursively to their scoped internal data nodes while preserving workflow output aliases.
Related selected nodes and requested upstream context use the consolidated projection service when their stable indices have an obvious lossless alignment; otherwise their DataFrames remain vertically stacked with independent query state.

Filtering, sorting, pagination, totals, and CSV export operate on the same immutable result snapshot and scoped node identities.
Filtering precedes sorting and pagination, and CSV applies the same active filter and sort contract.
The default page size is the persisted user preference, initially 250, while infinite scrolling is not part of the platform interaction model.
Individual and merged tables share the column-sizing contract in v1 Section 3.6: bounded initial content sizing, stable widths across data-page updates, independent resizing through visible separators, and one **Reset column widths** action.
Width persistence stores only explicit user choices by workflow/table and stable column identity, not measured component-update snapshots.

Node Data is a read-only inspection surface during execution.
Thumbnail requests are initiated only when their rendered row enters the visible table viewport, and nested canvases use their own canvas-scoped Node Data query state.

## 14. API Surface

The v2 API includes canonical workflow lifecycle routes; root workflow-draft routes; nested workflow-snapshot routes; recursive validation, execution, output-schema, cache, package, and tool routes; source-update preview and apply routes; trusted Python-source preview using the same apply route; and explicit workflow and result exports.

Execution APIs include strict profile and target models, sanitized cluster and connection descriptions, typed remote path plans, exact run preflight without a root-input field, plural execution snapshots, reload of retained observations, ID-specific cancellation, persisted retry preview and confirmation, managed result download, and typed plan-based cleanup.
Managed profile records select a trusted desktop Python script whose top level defines `cluster = RemoteCluster(...)`; their persistence contains identity, revision, name, enabled state, script path, observed digest, and non-secret cluster host/root observations.
Target listing reads those saved observations and capability support without executing the selected scripts; script execution occurs only during profile validation, explicit describe, and submission.
Version-1 low-level Parsl and transport profiles are dropped without archive or conversion.
If the saved default target no longer names Local or an enabled current profile after that load, the setting is durably repaired to Local.

The export routes are:

- `POST /api/v1/workflows/{name}/export` for the portable workflow-only archive;
- `POST /api/v1/workflows/{name}/exports/latest-results` for the copied latest-results ZIP;
- `POST /api/v1/workflows/{name}/exports/latest-results-folder` for the desktop copied-folder export;
- `POST /api/v1/workflows/{name}/exports/workflow-run-bundle` for the workflow and pinned successful-run bundle.

Download routes complete their temporary materialization before returning a streamed file response and remove temporary state after the response.
The desktop folder route accepts an absolute existing parent directory and a replacement flag, derives the export child name itself, and is forbidden outside desktop mode.
Expected export failures use stable status categories for missing workflows, forbidden or unsafe destinations, existing destinations, unavailable results, invalid requests, and internal materialization failures.

OpenAPI is the sole frontend API type source.
Generated discriminated graph, interface, edge, provenance, and source-operation types are consumed directly without handwritten compatibility aliases.
`POST /api/v1/napari/viewing-readiness` accepts a `ViewingRequirementsManifest` directly, including the exact manifest returned after import, and returns the backend-authoritative desktop-only passive compatibility report without rereading workflow state.
The report preserves every structural output identity and declaration or unknown reason, shares registered-inventory candidate evaluation with retained-artifact resolution, and returns independent normalized requirement groups with managed-create prefill rather than unioning incompatible output needs.
`POST /api/v1/editor/open-node` identifies the workflow ID and identity generation, the accepted revision, the node ID, and an optional nested session UUID.
It resolves the addressed node's actual source and rejects stale or missing identities instead of falling back to the global registry for bound local sources.
Nested source preparation returns the updated accepted snapshot along with the editor response.

### 14.1 Platform-Owned Integration Settings

Application-wide integration settings are platform-owned and are not contributed by installed tool packages through schemas, HTML, Vue components, or other executable frontend extensions.
An integration that needs global configuration is added to the platform core with its storage, validation, secret handling, UI, tests, and compatibility behavior.

Managed remote profiles are platform-owned integration settings.
Desktop users select and explicitly trust a local configuration script, while webapp profiles are provisioned out of band and remain read-only without introducing a new administrator role.
SSH host, scheduler, project or account, queue, writable root, and optional Modules or Spack initialization remain genuine site facts in the selected script and reusable templates rather than duplicated platform form state.
Resolved secrets are never stored or returned.

OMERO remains a platform-owned integration consumed by dedicated tool packages.
The OMERO settings UI renders each named server instance as a separate responsive form card with individually labelled fields and card-local Save, Duplicate, and Remove actions.
Cards use multiple field columns when space permits, collapse to one column in narrow windows, and do not require horizontal scrolling to reach fields or actions.

Fiji is also a platform-owned desktop integration, but the Fiji application remains user-installed and user-managed. The platform stores and validates the selected installation directory, resolves result images from their workflow-scoped identities, and never exposes this local-launch capability in webapp mode.

Named napari environment registrations, managed recipes and operations, inventories, defaults, filename rules, and output favorites are likewise platform-owned local integration state.
They never enter recursive `GraphState`, artifact hashes, workflow archives, retained result snapshots, or processing dependency resolution.
Managed creation, copy, retry, cancellation, and deletion therefore do not acquire a workflow graph mutation lock; their own environment UUID and registry revision contracts prevent them from targeting a replaced local installation.

## 15. Keyboard And Context Actions

In the main Tools catalog, a single row click toggles the tool documentation panel, a double-click adds the tool to the active canvas at its default position, and drag-and-drop adds it at the requested position.
The catalog has no separate information button, and its script, rename, delete, and environment actions do not trigger either row interaction.

Ctrl/Cmd+S saves the active persistence context.
In a root tab it saves the workspace workflow; in a nested tab it applies the accepted nested snapshot to its parent.

The workflow-node context actions are **Open workflow**, source actions when provenance exists, Rename, Enable/Disable, and Delete.
The selection action is **Group into workflow**.

The Run toolbar includes an execution-target selector whose visible value applies to every run command.
**View → Execution** opens the retained run monitor.
Run actions address one execution ID for cancellation, retry, result download, retained-observation reload, and cleanup; managed retry confirmation always names its captured target and planned child run.

## 16. Files Source Selection

The Files source tool accepts either one filesystem Directory or an explicit ordered Files list.
Directory remains singular because its Glob pattern and Recursive settings describe one directory scan.
The two source parameters are mutually exclusive.

In desktop mode, Directory provides **Select folder** and Files provides **Select files**.
Selecting one source replaces its value and clears the other source in one graph edit.
Cancelling a native dialog changes nothing.
The Datasets panel is absent from the desktop dock and View menu because desktop inputs remain ordinary local filesystem references.
Dropped desktop files are neither uploaded nor copied.
Dropping local files or folders on the canvas creates a Files node at the drop position.
A single dropped folder populates Directory; a compound drop expands each folder's immediate files into the explicit ordered Files list so that list never contains invalid directory paths.

In webapp mode, the Files source controls provide one shared **Select in Datasets panel** action instead of native filesystem actions.
The action reveals and activates the Datasets panel without changing parameters or entering the single-file parameter picker.
Users may select managed files or multiple managed folders there; **Set files on “node name”** resolves the selection to an explicit ordered Files list and clears Directory in one graph edit.
Managed folders do not populate Directory because they are logical dataset groups rather than server filesystem paths.

The Datasets panel selection summary occupies its own footer row.
Footer actions appear below it with visible spacing and wrap without touching at narrow panel widths.
This section overrides the Files-source-specific browser folder behavior inherited from v1 Section 3.5.3; other path parameters retain the v1 picker behavior.
