# BioImageFlow Platform Development Context

This is the required orientation for agents developing the BioImageFlow Platform.
Read it once per agent session before changing platform code, then read the task-relevant normative sources identified below.

This file is a navigation aid and architectural summary, not a new specification or a substitute for source code, tests, or the normative documents.
It deliberately lives at the repository root and is not part of the public Sphinx documentation.

## What the platform is

BioImageFlow Platform is a visual application for creating, editing, executing, and inspecting bioimage-analysis workflows.
It presents workflows as node graphs while delegating tool definitions, workflow construction, execution semantics, caching, and portable workflow formats to the BioImageFlow library.

The product has three main layers:

1. The Vue frontend owns the interactive presentation of canvases, panels, editors, execution state, and user actions.
2. The FastAPI backend owns validation, persistence, workflow lifecycle, tool discovery, translation, execution coordination, results, external integrations, and security boundaries.
3. The BioImageFlow library owns the portable tool and workflow model and the execution contracts used by the backend.

The frontend communicates with the backend through the versioned REST and WebSocket APIs.
It must not reproduce backend validation or library behavior as an independent authority.
The backend should use public BioImageFlow APIs and should not depend on private library storage or implementation details.

The application supports desktop and webapp deployment modes.
Desktop mode is packaged with pywebview and may use trusted local capabilities such as native file dialogs and editor integration.
Webapp mode uses managed server-side datasets and restricts capabilities that would expose or execute against arbitrary server paths.
Desktop result images may also be opened in the platform-managed Napari environment or a user-installed Fiji application configured through Settings; Fiji launch requests resolve workflow result identities on the backend and are unavailable in webapp mode.
The existence of both modes does not make every proposal in `platform_specs_v3.md` implemented.

## The core mental model

### One recursive graph

`GraphState` is the single editable workflow definition at every depth.
A root workflow and a workflow embedded as a node use the same recursive graph schema, validation rules, canvas model, interface model, and execution translation.

Every graph has required identity and presentation fields, nodes, edges, a workflow interface, and workflow configuration.
There are two explicit node variants:

- A tool node identifies a BioImageFlow tool invocation and owns parameter values, resource overrides, output templates, layout, enabled state, and collapsed state.
- A workflow node embeds another complete `GraphState`, owns bindings from the parent into the embedded interface, and may retain provenance pointing to a saved workspace workflow.

There are two explicit edge variants:

- A column edge connects one named output to a field input or stable workflow input ID.
- A DataFrame edge connects a complete DataFrame to a positional tool input or stable named workflow input ID.

Workflow interface ports have stable immutable IDs and editable display names.
The Nodes panel publishes positional DataFrame inputs independently of tool parameters through **Published DataFrame inputs → Publish DataFrame input**.
Each publication reserves the next free positional slot; connected and published slots compact together on removal without changing surviving public IDs.
Existing child workflow DataFrame ports can also be published through the enclosing workflow interface.
Edges and bindings use the stable IDs, never display labels.
Renaming a port must therefore preserve connections, while removing or incompatibly changing a connected port requires explicit destructive-effect handling.
Canvas mutations must preserve interface referential integrity in the same graph snapshot: deleting nodes also removes outputs sourced from them and removes their input targets, dropping any input that has no surviving target.

An embedded graph is the workflow node's execution authority.
Its optional saved-workflow source is provenance only: changing, moving, or deleting the saved source must not silently mutate the embedded copy.

### Three persistence contexts

Do not conflate the following states:

1. A saved root workflow is persisted as a `WorkflowDocument` in the workflow directory's `workflow.json`.
   The envelope contains the canonical graph, workspace metadata, artifact hash, optional Python-authoring provenance, and owned local-source identifiers.
2. An open root canvas edits a durable workflow draft under that workflow directory.
   Draft writes use expected-revision compare-and-swap, record their writer, validate the accepted graph, and track whether the draft differs from the saved artifact.
3. An open nested canvas edits a private durable nested snapshot.
   It has its own session identity, ownership chain, revision compare-and-swap, and validation result, and it changes its parent workflow node only when explicitly applied.

Saving a root canvas promotes the accepted root graph to the saved workflow.
Saving a nested canvas applies the accepted snapshot to its parent node.
Closing or replacing dirty state must use the appropriate confirmation and conflict behavior.

Workflow IDs are workspace-relative paths and carry identity generations.
Saving an agent draft as a copy duplicates the captured graph together with its recursively referenced owned sources and editable local tools in one staged backend operation, without promoting or replacing the original draft.
Operations that wait, move, rename, delete, duplicate, save, or apply must remain bound to the captured identity so that a delayed response cannot mutate a newly created workflow that happens to reuse the same path.

The artifact hash is a deterministic identity for canonical recursive graph content and referenced owned sources.
Do not add timestamps, runtime state, workspace paths, source labels, or Python-authoring provenance to that hash without changing the explicit contract.

### Validation, compilation, and library translation

The backend Pydantic models in `backend/src/bioimageflow_server/models/graph.py` define the strict platform graph wire shape.
Recursive structural validation, semantic validation, compilation, and translation are backend responsibilities shared by draft writes, nested snapshots, execution, import/export, cache operations, and stateless graph requests.

The platform graph is translated and compiled into BioImageFlow objects in memory.
There is no second editable child-graph language and no separately persisted library workflow document that can become another authority.

Validation must cover the whole recursive graph, including unique identities, endpoint compatibility, tool availability, interfaces, local-source ownership, containment cycles, bindings, and the selected execution context.
Errors should retain scoped node paths so a failure inside an embedded workflow remains attributable to its actual internal node.

Frontend graph types are generated from backend OpenAPI into `frontend/src/api/types.ts`.
When an API model changes, update the backend model and schema first, regenerate the frontend types, and adapt consumers instead of introducing handwritten compatibility copies.

### Tools and sources

BioImageFlow distinguishes processing tools, which process rows and can write templated outputs, from DataFrame tools, which create or transform DataFrames.
Tool metadata describes tool type, inputs, outputs, parameters, packages, versions, resources, row-consumption semantics, and capabilities.
The registry describes catalog tools; validation returns node-scoped metadata from the actual compiled class for source-bound tools, without replacing same-named registry entries.
Custom-tool hot reload supplements native filesystem events with content checks limited to registered editable source directories, so missed editor-save events cannot leave metadata stale.
Successful code-only reloads also notify canvases for validation and cache-status refresh; failed edits retain the previous usable registry entries.
Every processing tool declares `row_consumption` as `mapped` for independently consumed rows or `collective` for a batch that may combine aligned rows; DataFrame tools expose `null`.
The canvas derives column-edge strands reactively from the target tool metadata and does not persist this presentation state in the graph.
Do not infer structural names from UI labels or filenames.

Installed package tools are versioned dependencies resolved through the tool store.
Workflow-local tools are editable source files owned by a workflow and travel with its exports.
Import unpacks custom sources into `tools/<source-id>/`, where `module.json` contains identity and module-layout metadata and ordinary files contain the executable code.
An explicit import rename sets both the destination workflow ID and the root graph's visible and definition names (using the destination leaf), while preserving embedded workflow names.
There is no opened-bundle execution mode or persisted JSON source-text fallback.
Opening a saved workflow with missing owned-source files reports `workflow_source_missing` (HTTP 409), with workflow-relative file and recovery details; older JSON source records are identified but are not automatically converted.
Compilation and export capture current file bytes and assign content-derived runtime module identities, independently of watcher delivery, so package helper imports cannot reuse older code.
Source-bound nodes use the worker-capable engine without inferring their class from the global catalog.
Invalid edits prevent the affected workflow from executing with silently retained code.
Node script opening addresses an accepted root draft or nested session by workflow generation, revision, and node ID; it resolves the same source binding used for execution.
Opening a local source in a nested editor first forks that source into the private session; applying the session carries the binding to the parent.
Recursive embedding, copying, import, export, and source update must preserve all required local sources without registry shadowing when same-named sources have different content.
Canvas embedding prepares a destination-owned copy of the source graph and files on the backend before inserting the returned graph; it must not insert another workflow's source identifiers directly.

The embedded code editor uses a platform-generated multi-root VS Code workspace with the active BioImageFlow workspace first and the installed tool store second.
Embedded editor startup remains a single locked launch operation, while side-effect-free status probes expose its current preparation, extension-installation, process-start, readiness, or failure phase to the Code Editor panel.
Startup reuses a matching code-server environment and installed extensions; a digest in the managed environment tracks bundled integration updates across platform restarts.
Progress messages describe actual checks and missing or changed extension installations.
Editor lifecycle records use the streamed BioImageFlow logger so users can inspect setup details without the Logger panel opening automatically.
The workspace root remains the integrated-terminal working directory, installed package sources are read-only in that editor, and focusing either a workflow-local or package tool must not replace the editor project.
Configured external editors retain their command-defined project behavior.
Newly created tools use the same tool-opening route: return the managed workspace URL as soon as code-server responds, then focus the source after the workbench loads and activates the opener extension.
The Nodes panel opens the selected tool script through the node-addressed editor route after the canvas persistence barrier and deployment checks.
Tool catalog rows and newly created tools use the separate catalog tool-opening route; catalog names never override an explicitly bound node source.
Validation returns source-specific node metadata without registering imported classes in the global tool catalog.

Trusted `workflow.py` files are authoring inputs only.
Building from Python materializes a canonical graph and its allowed source bundle; running, nesting, copying, reopening, and exporting use the materialized graph and do not import the authoring source.

### Execution and results

Individual and merged Node Data tables share bounded content-aware column sizing and visible independent resize handles.
They measure only visible, font-ready content and persist deliberate user widths by workflow/table and column identity, never automatic DOM measurements; **Reset column widths** restores content sizing.

Execution operates on one exact accepted graph or draft snapshot.
Graph mutation is locked where required while an attached execution owns the mutable platform context.
Do not rebuild an ad hoc partial graph for Run Selected; the selected structural boundary and its enabled completion dependencies are resolved by the normal recursive compiler.

Recursive graphs compile to scoped jobs while workflow nodes project aggregate descendant status.
Caching and result attribution remain per internal tool node, and failures preserve their scoped path through nested workflow boundaries.

The platform has an engine-neutral execution model with execution targets, preflight, retained run identities, job snapshots, history, cancellation, and reconnection capabilities.
Local execution preserves Direct and Wetlands through the existing local path.
Managed remote execution delegates deployment, validation, Parsl orchestration, scheduler submission, attachment, progress, diagnostics, cancellation, retry, result transfer, and cleanup to the public `bioimageflow.cluster` API.
Execution targets and retained run state are platform-owned and must not be persisted in portable `GraphState`.
Workflow scheduling policy remains part of `GraphState`, while a selected execution target is run intent or application preference.

Managed remote profiles select one trusted Python script whose top level defines `cluster = RemoteCluster(...)`.
Profiles persist non-secret identity, name, enabled state, script path, observed digest, cluster host, and normalized root; target listing uses those observations and capabilities without executing the script, while profile validation, describe, and submission load the trusted code.
A managed run separately persists its own host/root attachment tuple, durable run ID, progress cursor, and deterministic result-bundle path so restart attachment does not need the original script and a verified local result remains usable after remote cleanup.
Strict profile descriptions, path and cleanup reports, run observations, and execution diagnostics expose typed sanitized allowlists rather than retaining unknown library report fields or arbitrary exception strings.
The platform does not retain attached-Parsl, submitted-local, low-level SSH transport, cluster-agent, importable factory, staging-root, or manual remote-directory workflows.
The public capability report and structured diagnostics determine UI state, and managed runs do not expose logs.
Retry recovery is attach-first and may replay only the exact persisted public retry plan after definitive child absence.
Managed execution registries, retry and cleanup journals, and downloaded result bundles are workspace-scoped; switching workspaces changes listings and new-run storage but does not redirect an already bound active execution's writes.
After version-1 profiles are dropped, an invalid or disabled default target is durably repaired to Local without disturbing a valid enabled version-2 default.

Each saved workflow owns runtime storage at `<workflow-directory>/results`.
The `outputs/latest` view is a disposable per-node projection and may combine the latest successful outputs from different runs.
A workflow-and-results bundle instead pins one successful run.
These artifacts have different import, export, mutation, and availability semantics and must not be treated as interchangeable archives.

### APIs, events, and agent control

Platform HTTP endpoints use the `/api/v1/` prefix.
Routers should remain thin transport boundaries over models and services, with stable structured errors for expected failures.
WebSocket events carry logs, execution progress, status, and workspace changes that the frontend uses for live projection and recovery.

The MCP server in `backend/src/bioimageflow_server/agent_mcp.py` is a separate control surface for agents operating the active user workspace.
The material under `docs/agents/` documents that workflow-operation contract; it is not the development architecture guide.
Platform development agents may edit repository source normally, but should not use direct saved-workflow JSON edits as a substitute for MCP when a task is about operating an active workflow.

## State and ownership invariants

Preserve these invariants unless an approved specification change explicitly replaces them:

- One canonical recursive `GraphState` represents editable workflow content at every depth.
- Each fact has one owner; avoid parallel persisted representations and duplicated frontend/backend authorities.
- Stable IDs, not labels or positions, connect nodes, edges, ports, drafts, snapshots, runs, and results.
- Root drafts and nested snapshots use revision compare-and-swap; conflicts must not partially apply.
- Operations with destructive or cross-resource effects use preview, captured identity, exact confirmation, recheck, staging, and atomic commit where the specifications require them.
- Backend validation and mutation locking are authoritative; frontend checks improve interaction but are not security or consistency barriers.
- Embedded workflow content is independent from saved-source provenance unless the user explicitly performs an update.
- Workflow-local source ownership is preserved recursively and same-named different-content sources can coexist.
- Runtime translation uses public BioImageFlow contracts and does not create a second persisted workflow authority.
- OpenAPI is the source of frontend API types.
- Desktop-only filesystem and execution capabilities remain gated from ordinary webapp mode.
- Path resolution, archive extraction, uploads, editor launches, and trusted Python authoring must reject traversal, symlink escape, and unintended server-path access.
- Mutation, publication, export, execution, and result reads operate on explicitly identified accepted snapshots.
- Expected operational failures return stable, actionable error categories and leave durable state coherent.

## Repository map

### Backend

- `backend/src/bioimageflow_server/app.py` constructs the FastAPI application, wires service instances and dependency overrides, registers routers and WebSockets, and serves the built frontend in packaged mode.
- `backend/src/bioimageflow_server/models/` contains strict API and persistence models.
- `backend/src/bioimageflow_server/routers/` contains REST transport handlers grouped by domain.
- `backend/src/bioimageflow_server/services/` contains graph validation and compilation, persistence coordinators, workflow lifecycle, tools and packages, execution, exports, results, datasets, and integrations.
- `backend/src/bioimageflow_server/ws/` contains WebSocket connection and logging infrastructure.
- `backend/src/bioimageflow_server/desktop.py` owns the pywebview desktop entry point.
- `backend/src/bioimageflow_server/agent_mcp.py` exposes controlled workspace operations to MCP clients.
- `backend/tests/` mirrors backend models, routers, services, integration boundaries, and application behavior.

For graph changes, begin with the graph models and the validator/compiler/translator services rather than patching one router in isolation.
For persistence changes, identify every coordinator participating in saved workflows, drafts, nested snapshots, identity generations, moves, source ownership, and execution locking.

### Frontend

- `frontend/src/api/` contains the HTTP clients and generated OpenAPI types.
- `frontend/src/stores/` contains Pinia state for workflows, drafts, tools, settings, execution, results, datasets, and UI state.
- `frontend/src/sessions/` contains canvas identity, graph synchronization, root-draft persistence, nested-snapshot persistence, recovery, and status projection coordinators.
- `frontend/src/components/canvas/` renders graph nodes, pins, edges, menus, and persistence feedback.
- `frontend/src/components/panels/` renders tools, node configuration, workflow trees, data, logs, settings, datasets, and execution inspection.
- `frontend/src/components/execution/` contains run, target, retry, remote-input, recovery, and execution-banner interactions.
- `frontend/src/utils/` contains graph operations and codecs such as grouping, clipboard handling, endpoint handles, output templates, and selection logic.
- `frontend/src/App.vue` integrates the application shell, docks, menus, canvas lifecycle, and top-level actions.
- Unit tests live beside or near their source; browser tests live under `frontend/tests/e2e/`.

Canvas views support zoom down to 5%; initial framing centers and fits nodes without exceeding 100%, and SVG grid identities are independent of encoded workflow paths.
Run Selected remains directly visible in the execution toolbar.

For a canvas change, trace ownership through the relevant session coordinator and store before changing component-local state.
For an API change, trace the backend model and service, router, generated type, API client, store/session consumer, UI, and tests as one contract.

### Other important areas

- `scripts/test` is the authoritative validation entry point.
- `docs/testing.md` defines focused, quick, scoped completion, browser, full, and certification lanes.
- `docs/user/` is public user documentation and should describe released user-facing behavior without exposing this internal orientation file.
- `backend/src/bioimageflow_server/data/demo_workflows/` contains bundled deterministic workflow artifacts.
- `bioimageflow/` may be a local library checkout or link used to inspect the library source and specification; the installed dependency remains the runtime authority selected by the lockfile.
- `external/wetlands-src` is an optional source-browsing link and must not become a package or runtime dependency.

## Specification authority and reading order

The specifications are intentionally separate because they belong to different products and maturity levels.
Do not combine them into a new manually maintained normative document.

Use this authority order:

1. `bioimageflow/docs/source/specs.md` is authoritative for BioImageFlow library contracts.
2. `platform_specs_v1.md` is the implemented platform baseline.
3. `platform_specs_v2.md` is a cumulative implemented platform delta and overrides v1 where it explicitly changes the same behavior.
4. `platform_specs_distributed_execution.md` is the implemented normative delta for managed distributed execution and overrides v2 where it explicitly changes the same behavior.
5. `platform_specs_v3.md` is a future webapp and multi-user proposal, not evidence that a feature is implemented.

Source and tests reveal actual implementation state but do not silently erase an explicit normative requirement.
When implementation and specification disagree, determine whether the code is defective or the specification has not been updated, then make the task leave them consistent.

Read this file first, then use the following routing table instead of loading every specification for every task:

| Task area | Required additional reading |
| --- | --- |
| Localized platform UI, panels, shortcuts, or desktop interaction | Relevant v1 frontend section, plus any v2 section that names or overrides the feature |
| Graph schema, nodes, edges, endpoint handles, interfaces, grouping, or clipboard | v2 Sections 1–8 and relevant v1 graph/canvas sections; library Sections 2–4 and 14 when portable contracts are involved |
| Root drafts, save, recovery, workflow lifecycle, move/rename/delete, or identity conflicts | v1 backend workflow/state sections and v2 Sections 7, 8, 10, and 12 |
| Nested workflows, provenance, source update, or recursive local sources | v2 Sections 1–12 and library Section 14 |
| Tool definitions, type compatibility, DataFrame semantics, resources, packages, or tool loading | Relevant library Sections 2–4, 7, and 10, plus v1 tool and node-panel sections and applicable v2 overrides |
| Execution, caching, cancellation, progress, or result storage | Relevant library Sections 4–7 and 10–13, v1 execution/data-flow sections, and v2 Sections 8, 9, 12, and 14 |
| Execution targets, profiles, preflight, retained runs, managed clusters, Parsl, PSI/J, or remote data | `platform_specs_distributed_execution.md`, the library remote-cluster specifications and how-to, relevant library execution sections, and the current execution models/services/tests |
| Import, export, latest outputs, result bundles, or Python authoring | v2 Sections 6, 8, and 10–14 plus library archive, file-management, and recursive-workflow sections |
| Datasets, browser mode, authentication, security, or multi-user behavior | Implemented v1/v2 sections first; consult v3 only for work explicitly targeting the proposal and distinguish inherited behavior from proposed behavior |
| MCP workspace operations or coding-agent user features | Root `AGENTS.md`, `docs/agents/`, `backend/src/bioimageflow_server/data/agent_workspace_instructions.md`, and the corresponding backend MCP/services tests |
| Broad cross-stack architecture or library compatibility | All of v1 and v2 plus relevant library sections; add the managed distributed specification or v3 proposal only when the task includes that scope |

Follow links into additional specification sections when the selected material explicitly makes them prerequisites.
For ambiguous behavior, search all specification documents for the concept and check for a later explicit override before implementing.

## How to approach a development task

1. Read this file once per agent session and reread it if it changes during the work.
2. Inspect `git status` and preserve unrelated user changes.
3. Classify the task by ownership boundaries and use the routing table to read the relevant specifications.
4. Trace the current behavior through models, services, transport, generated types, state/session ownership, UI, and tests as applicable.
5. State the invariant being changed or preserved before editing.
6. Implement the smallest coherent cross-layer change rather than adding compatibility state that creates another authority.
7. Run focused tests during implementation and the smallest applicable completion check from `docs/testing.md` before completion.
8. Update every affected specification document, not only the newest version, whenever the change modifies its behavior, architecture, contract, terminology, status, or acceptance criteria.
9. Update this file in the same task whenever the platform mental model, invariants, repository map, authority order, or reading guidance would otherwise become inaccurate or incomplete.
10. Keep internal development guidance out of the public Sphinx toctree unless a separate task explicitly turns some of it into user-facing documentation.

Specification updates are part of implementation, not optional cleanup.
Do not edit every specification mechanically when a change does not affect it, but do update all documents that make statements invalidated or superseded by the change.
