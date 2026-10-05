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
Portable BioImageFlow graphs intentionally carry no canvas coordinates, so their first platform materialization derives a deterministic recursive left-to-right layered layout from dependencies.
Once materialized, positions belong to the canonical graph and imports, execution, reopening, and ordinary edits never reflow that persisted user layout.

Every graph has required identity and presentation fields, nodes, edges, a workflow interface, and workflow configuration.
There are two explicit node variants:

- A tool node identifies a BioImageFlow tool invocation and owns parameter values, resource overrides, output templates, layout, enabled state, and collapsed state.
- A workflow node embeds another complete `GraphState`, owns bindings from the parent into the embedded interface, and may retain provenance pointing to a saved workspace workflow.

There are two explicit edge variants:

- A column edge connects one named output to a field input or stable workflow input ID.
- A DataFrame edge connects a complete DataFrame to a positional tool input or stable named workflow input ID.

Workflow interface ports have stable immutable IDs and editable display names.
The Nodes panel edits unconnected field bindings on selected workflow nodes by stable child input ID.
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
   Revision-zero synthesis captures one saved graph/hash/metadata snapshot per existing mutation-lock phase; captures expire as current saved authority at lock release and later phases and requests recheck current saved/draft authority, generation and storage.
   After an interrupted draft write, a newer browser recovery snapshot may temporarily supply the startup canvas graph; it is reconciled through the accepted draft's revision compare-and-swap rather than becoming another backend authority.
   An accepted named Open supersedes pending startup presentation and its late presentation writes; the winning Open retains newer same-workflow recovery and the accepted draft CAS base, while nested inspection and unrelated recovery remain scoped to their owners.
   The Workflows panel owns explicit row/folder browsing independently of loaded metadata; late automatic startup preserves it, and deliberate presentation or canvas activation retakes selection through synchronously consumed immutable intent.
   Ordinary Save, dependency refresh, rebind and structural metadata remapping remain passive; canonical automatic activation retains its exact target-bound cause.
   Workflow-tree startup consumers share only an in-flight read under the same catalog authority and structural generation; accepted same-ID metadata writes and explicit post-mutation/workspace/migration/reconnect refreshes invalidate that authority.
   Flat-list and tree requests keep separate response contracts and owned loading/error lifetimes, with at most one stale retry per caller and no resolved-response cache.
3. An open nested canvas edits a private durable nested snapshot.
   It has its own session identity, ownership chain, revision compare-and-swap, and validation result, and it changes its parent workflow node only when explicitly applied.

Saving a root canvas promotes the accepted root graph to the saved workflow.
Saving a nested canvas applies the accepted snapshot to its parent node.
Closing or replacing dirty state must use the appropriate confirmation and conflict behavior.
Nested tabs close in descendant-first order: a refused or failed durable snapshot deletion leaves the editor recoverable with a visible reason, and never silently discards child sessions.

Older saved workflows, root drafts, and nested snapshots are discovered by a write-free format scan.
They remain byte-for-byte unchanged and unavailable until the user confirms the content-derived plan; current unrelated workflows remain usable.
Confirmation first synchronizes exact backups under `<workspace>/.bioimageflow/backups/workflow-format/<plan-id>/`, then replaces all planned authorities through one forward-recoverable journal whose already-confirmed work is completed after restart.

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

Frontend graph and workflow-draft routes/response types are generated from backend OpenAPI into `frontend/src/api/types.ts`.
The draft client's remaining handwritten response/conflict shapes are transitional debt and do not supersede the generated-only authority.
When an API model changes, update the backend model and schema first, regenerate the frontend types, and adapt consumers instead of introducing handwritten compatibility copies.

### Tools and sources

BioImageFlow distinguishes processing tools, which process rows and can write templated outputs, from DataFrame tools, which create or transform DataFrames.
DataFrameTool parameter fields accept constants, including constant-valued published workflow inputs; their metadata reports no column pin.
Complete upstream DataFrames connect positionally, and the library rejects column or node-shorthand bindings to DataFrameTool parameters, including through recursive workflow interfaces.
Tool annotation introspection resolves postponed and inherited annotations while preserving GUI and image metadata, so registry schemas and execution validation describe the same declared types.
Tool metadata describes tool type, inputs, outputs, parameters, packages, versions, resources, row-consumption semantics, and capabilities.
Portable CPU/GPU/memory/GPU-memory resources are worker requirements with author-declared floors, while maximum concurrency is a submission cap; actual capacity, allocation, and enforcement are backend/site-owned and resources do not affect cache identity.
The registry describes catalog tools; validation returns node-scoped metadata from the actual compiled class for source-bound and explicitly bound portable tools, without replacing same-named registry entries.
Installed bindings retain their package/version and read-only provenance; owned sources retain their editable custom provenance.
Custom-tool hot reload supplements native filesystem events with content checks limited to registered editable source directories, so missed editor-save events cannot leave metadata stale.
Successful code-only reloads also notify canvases for validation and cache-status refresh; failed edits retain the previous usable registry entries.
Every processing tool declares `row_consumption` as `mapped` for independently consumed rows or `collective` for a batch that may combine aligned rows; DataFrame tools expose `null`.
The canvas derives column-edge strands reactively from the target tool metadata and does not persist this presentation state in the graph.
Do not infer structural names from UI labels or filenames.

Installed package tools are versioned dependencies resolved through the tool store.
Package uninstall uses the exact optional query version and contained stored directory identity, independently of successful imports or registry membership; it rejects unsafe selectors, links below the configured root and observed root/package/version substitutions before removal or failed-trash fallback.
An omitted version selects the whole package, while an empty explicit version is invalid; successful selected removal preserves other packages/versions and does not own Wetlands environments.
A carried module/class/package/version binding takes precedence over a same-named catalog entry during translation and compilation; only explicit version rebind changes that dependency.
Explicit package references remain package requirements even when the catalog has a same-named custom tool, while module/class-only references are local references without an invented package requirement.
The platform app environment supplies `pip` for tool-store package installation; the current BioImageFlow library and platform source-import path invoke the app interpreter's `python -m pip`, independently of Wetlands worker environments.
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
Environment provisioning downloads the pinned upstream code-server release bundle for the host platform and verifies its pinned SHA-256 before unpacking, so the embedded editor does not depend on a host Conda build; Windows ARM64 hosts run the upstream x64 bundle under x64 emulation because upstream publishes no native Windows ARM64 build, and provisioning failures surface the failing step, command, exit code, and redacted output tails instead of an opaque exit summary.
Progress messages describe actual checks and missing or changed extension installations.
Editor lifecycle records use the streamed BioImageFlow logger so users can inspect setup details without the Logger panel opening automatically.
The workspace root remains the integrated-terminal working directory, installed package sources are read-only in that editor, and focusing either a workflow-local or package tool must not replace the editor project.
Configured external editors retain their command-defined project behavior.
Newly created tools use the same tool-opening route: return the managed workspace URL as soon as code-server responds, then focus the source after the workbench loads and activates the opener extension.
The Nodes panel opens the selected tool script through the node-addressed editor route after the canvas persistence barrier and deployment checks.
Tool catalog rows and newly created tools use the separate catalog tool-opening route; catalog names never override an explicitly bound node source.
In the main tool catalog, single-click toggles the bottom documentation panel and double-click creates a node through the active-canvas command facade; catalog secondary actions remain isolated from both row gestures.
The Manage Tools inventory is independent of the catalog search query, and its tool information and actions expose each declared managed environment's location and explicit create/recreate operation.
Validation returns source-specific node metadata without registering imported classes in the global tool catalog.

Trusted `workflow.py` files are authoring inputs only.
Building from Python materializes a canonical graph and its allowed source bundle; running, nesting, copying, reopening, and exporting use the materialized graph and do not import the authoring source.

### Managed datasets

The implemented dataset catalog and docked panel have their normative home in v1 Sections 2.4.10 and 3.14; v2 Section 16 owns Files-source integration.
Managed bytes default to `<workspace>/datasets`, while logical folders and display names live in a SQLite catalog and do not change physical paths or file IDs.
Uploads stream into exclusive unrecognized staging, then publish complete bytes and their catalog record under a short cooperating-writer transaction; name, revision and selection decisions acquire that writer before inspection.
Short writes complete before publication, interrupted staging is cleaned by its owner, and accepted/ambiguous commits retain complete bytes; recovery may import unacknowledged complete legacy files without their original logical metadata.
Per-file storage failures preserve earlier successes, and multipart cleanup cannot roll back accepted bytes; snapshot reads remain separate from writer admission and no power-loss or arbitrary external-writer atomicity is promised.
Selection resolution expands folder descendants into explicit ordered file records; recursive deletion requires a preview and catalog-revision confirmation, with actionable partial failures.
Ordinary browser path parameters use the panel's transient single-file picker, and Files sources use normal multi-selection; desktop inputs use native/local filesystem paths.
Resolve-and-containment checks remain authoritative for uploads and deletion.
Compatibility single-file deletion additionally requires the exact catalog ID and matching stored filename under a writer transaction; encoded filenames alone cannot select unmanaged files or the catalog.
It checks resolved containment and unlinks only the selected lexical entry, preserving a contained symlink's destination; filesystem deletion and catalog commit have no atomic rollback guarantee.
Exact submitted-original-filename metadata fidelity remains a known store implementation gap, distinct from safe stored naming.

### Execution and results

Individual and merged Node Data tables share bounded content-aware column sizing and visible independent resize handles.
Modern Node Data and CSV validate the latest link schema and contained relative target, require the canonical run/node view named by its provenance, and verify the retained result identity and immutable record before serving rows; corrupt provenance or Parquet produces a typed unavailable response, and only views with absent `result.json` use the deliberately unpinned legacy path.
They measure only visible, font-ready content and persist deliberate user widths by workflow/table and column identity, never automatic DOM measurements; **Reset column widths** restores content sizing.
The browser image-viewer action checks its selected result's offsets through the same-origin backend API before opening the external Avivator iframe, so an unavailable conversion is reported locally and the unchanged action can retry without opening a broken panel.
Node-image, thumbnail, and Reveal requests resolve relative owned image paths against the immutable record captured for that request through the library's public asset API; absolute external image paths keep their declared location, and legacy unpinned results retain their existing lookup rules.

Local execution and cache clearing load one exact accepted root draft by workflow ID and revision after the canvas freshness barrier.
Progress callbacks retain that run's immutable identity and are ignored after it stops owning the active running context.
The execution banner's single overall bar uses the run's retained scoped executable leaf-node plan, including cached and selected dependencies, rather than the active canvas node count. Its text distinguishes completed nodes, current row position or completed rows, and per-row task progress; a successful run reaches 100%.
Graph mutation is locked where required while an attached execution owns the mutable platform context.
Context-menu Delete and Group refusals during that lock leave the canvas graph and history unchanged and visibly explain the lock.
Ordinary accepted graph mutations serialize through the same admission gate: a mutation reservation blocks Run, concurrent mutations wait their turn, and only an actually starting or running execution makes a mutation fail as execution-locked.
Do not rebuild an ad hoc partial graph for Run Selected; compile the complete accepted graph, derive requested root nodes and their transitive upstream roots from its edges, and ignore only diagnostics proven by their scoped node paths to belong to unrelated roots. Selected and upstream workflow boundaries own their descendant diagnostics, while global or unattributable diagnostics, unknown or unresolved targets, and a missing compiled workflow remain blocking. The selected structural boundary and its enabled completion dependencies are resolved by the normal recursive compiler.

Recursive graphs compile to scoped jobs while workflow nodes project aggregate descendant status in validation and retained execution completion.
Caching and result attribution remain per internal tool node, and failures preserve their scoped path through nested workflow boundaries.
An opened nested canvas maps its local node IDs through its durable owner chain to the root execution's scoped IDs for status, progress, and Node Data; private edits use the nested editor's validation until applied.
Every platform-owned Wetlands provisioning path forwards public environment-operation events, including sanitized Pixi output, to the Logger panel. Local workflow execution passes a run-scoped environment observer to the public engine API, keeping the shared Wetlands manager's methods unchanged while attributing provisioning to the correct execution and node. Retained job snapshots carry a setup message independently of numeric row progress, so the Execution panel distinguishes environment installation from tool execution.
The observer prepares processing environments at task submission for whole-workflow execution as well as explicitly prepared steps, so ordinary Run cannot bypass stale-generation authorization or setup observation.
The tool environment service supplies the same reentrant preparation guard to Run and its background default-general refresh, coordinating fresh inspection and conditional replacement through task submission without holding the guard for task completion.
BioImageFlow compares requested processing recipes with Wetlands-managed state before use. Stale platform-owned processing environments are closed and replaced lazily through Wetlands, while an already-existing stale `bioimageflow-general` environment is refreshed in the background after startup. User-managed, external, Napari, adopted, thumbnail, and code-server environments remain under their own lifecycle owners. An explicit tool requirement that cannot use the platform's exact `bioimageflow-core` runtime is a graph validation error.
The backend uv lock currently resolves the sibling BioImageFlow orchestrator and core as editable source packages for local development; the Python debug launch profiles use that backend environment. Explicit `(local core)` profiles also select and import the sibling `bioimageflow-core` project through `BIOIMAGEFLOW_CORE_SOURCE` and `PYTHONPATH`, and isolate their Wetlands state under the repository's ignored `.bioimageflow` directory.

The platform has an engine-neutral execution model with execution targets, preflight, retained run identities, job snapshots, history, cancellation, and reconnection capabilities.
Local execution preserves Direct and Wetlands through the existing local path.
Default library serialization preserves accepted root and child engine/scheduling configuration without loading carried packages.
Compilation derives one root engine from enabled recursive actual bound capabilities, selects Direct for ordinary DataFrame-only graphs and Wetlands for processing or owned-source nodes, and materializes once without installing packages; the graph's engine field is not proof that a worker ran.
Resources are checked against the actual materialized class, including a scoped refusal of DataFrame overrides during validation and refusal before publishing a portable archive.
DataFrameTool execution stays in the orchestrator in either case, while platform worker acceptance tests use a real ProcessingTool and verify process identity and outputs.
Direct remains useful for focused library tests and does not certify worker serialization, isolation, or lifecycle behavior.
Managed remote execution delegates deployment, validation, Parsl orchestration, scheduler submission, attachment, progress, diagnostics, cancellation, retry, result transfer, and cleanup to the public `bioimageflow.cluster` API.
Execution targets and retained run state are platform-owned and must not be persisted in portable `GraphState`.
Workflow scheduling policy remains part of `GraphState`; the application scheduling preference seeds newly created workflows and does not override an accepted graph at execution time. A selected execution target is run intent or application preference.

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
Clearing selected root-workflow nodes operates on an accepted draft, invalidates their cache/status, and removes only those nodes' disposable latest pointers and materializations without mutating the graph; nested-canvas result clearing requires its own scoped ownership path and is not exposed through the root-only control.
The matching retained execution-status snapshot tracks a successful Clear across browser reloads, while the completed run's historical result remains unchanged.
On an authoritative root-draft GET, the backend recomputes cache statuses and `cache_corrupt` diagnostics from the accepted graph and current workflow storage without rewriting the persisted draft or its revision; it preserves accepted non-cache diagnostics and cache diagnostics for nodes unavailable to fresh planning. A dependent waiting on cleared upstream work is out of date only when it retains a latest output, otherwise it is unexecuted.
The read fences the accepted draft, workflow generation, and storage path against concurrent draft mutation, Clear, and workflow replacement, and performs the final plan and latest-output lookup under the same workflow mutation lock as Clear.
A corrupt selected cache record projects the affected node as failed with `cache_corrupt` while leaving the draft readable and saveable; execution remains strict and rejects that branch.
When execution is idle, that accepted failed status takes badge precedence over a matching retained execution status for the affected node or a failed aggregate workflow ancestor; semantic edits, active progress, and ordinary terminal execution status keep their existing precedence.
Clearing the affected node removes its current selection, quarantines a safely identified corrupt immutable record, and refreshes the cleared and downstream status projection.
A workflow-and-results bundle instead pins one successful run.
These artifacts have different import, export, mutation, and availability semantics and must not be treated as interchangeable archives.

### APIs, events, and agent control

Platform HTTP endpoints use the `/api/v1/` prefix.
Routers should remain thin transport boundaries over models and services, with stable structured errors for expected failures.
WebSocket events carry logs, execution progress, status, and workspace changes that the frontend uses for live projection and recovery.
Execution-attributed BioImageFlow and Wetlands logs carry the immutable execution context used by progress and terminal events, while non-execution tool, environment, thumbnail, and platform logs remain contextless and global.

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
- OpenAPI is the sole normative source of frontend API types; remaining handwritten wrappers are implementation debt.
- Desktop-only filesystem and execution capabilities remain gated from ordinary webapp mode.
- Path resolution, archive extraction, uploads, editor launches, and trusted Python authoring must reject traversal, symlink escape, and unintended server-path access.
- Mutation, publication, export, execution, and result reads operate on explicitly identified accepted snapshots.
- Expected operational failures return stable, actionable error categories and leave durable state coherent.
- Deployment mode is captured process configuration: SettingsStore load/read/write and no-store live Settings reads expose that mode, and generic settings updates reject `deployment_mode` in both modes and `workspaces_root` in webapp mode before credential or JSON effects.
  App construction refuses an injected store with a conflicting configured mode before runtime setup; persisted administrator webapp roots remain available after authoritative settings load, while desktop workspace editing and ordinary live preferences remain supported.
- SettingsStore owns secret-free settings JSON and synchronous OMERO credential compensation: every distinct planned password-write key is read before any attempted write, and known pre-replacement failures preserve settings while attempting exact restoration of attempted credentials.
  Restoration is best effort through the injected provider; cross-resource atomicity, later replacement/acknowledgement faults and process termination are outside this guarantee.

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
- [Current campaign checkpoint](docs/developer/platform-test-current.md) is the single authority for the current source revision, next accepted work, residual gates and direct validation proof. Read it and the task-relevant specification/source paths; historical repair summaries below and the old progress diary are lookup material only, never required restart context.
- The unadopted candidate validates supplied worker row/batch contexts against Task4 role and row identity before tool import. Normal Processing execution requires a pinned selected-record identity; explicit public Storage/launcher transient workspaces remain separate from ordinary graph execution.
- The unadopted library candidate now stages complete workflow archives and output trees before native exclusive publication; persistent archive imports refuse occupied destinations and load only from the stable final root. Completed JSON/ZIP files replace the requested file only after writing and close succeed. These are scoped local publication guarantees, with OS capability and library milestone gates retained by the current checkpoint.
- **Historical library review — October 4:** deep current BioImageFlow library/Core review uses source `2cd79a2`; publication, release merge/tag actions, platform dependency/T1 adoption and platform testing remain paused through acceptance of the completed scoped library milestone. [Specification intent S](docs/developer/library-specification-intent-review.md), owning documentation clarification `e0f41b1`, [Test quality T](docs/developer/library-test-quality-review.md) and [Causal architecture/global findings C](docs/developer/library-causal-architecture-review.md) are accepted, with current mechanisms, strong controls, essential intent gaps and unexecuted capabilities distinguished. S→T→C main→C secondary and the combined interface design are accepted; the first coherent capture/transaction/schema increment is source-accepted at `936c44003f759075a16629d290bb3a5a227fe194` (43 task paths), with detached root/explicit-target/steps admission, effective defaults/configuration and central declaration/schema authority. The bounded numerical/order/pinned-selection and loader-admission increment is accepted at `d6865b1206747655ac93b280c7a61866aee466f2` (32 task paths): exact column values and strings, ordered dependency recipes, one captured record/frame/manifest/address through planning/progress/export, and actual source-byte/module/root admission. It preserves ordinary caching; executable-content cache-key proof remains open, and neither frozen selection metadata nor the one current Core artifact worker witness certifies accepted-array immutability or the entire current library cohort. The collective/empty aggregate and measured common-path increment is accepted at `cb83afc969df97a2159120f9c0c43cfdc8524e13` (64 task paths): current task/result v3 carries explicit ordered consumed-row groups, record v2 retains authoritative relation/domain metadata, and three current packaged Core managed-worker cases preserve nonempty/empty auxiliary/mapped expansion semantics. Explicit tracking joins preserve image outputs with nullable track fields, and undeclared Path echoes preserve original inputs. Public 1,000-row workflow planning/cached reuse and bounded components show measured speed improvements within their stated scopes. The finite array-sealing/exact-group/manual-idle-retirement increment is committed at `b6f84cc499d7938602d51f2796d1f76406195828`: newly admitted mutable SharedArrays receive one independent read-only accepted backing with content identity, admitted tasks retain independent capabilities, and caller-captured result handles release exact groups. Default result/group discard is not strongly retained by the diagnostic last context; explicit idle pool retirement preserves physical barriers and failed-close retry. The finite executable-admission/cache-key increment is committed at `116a40015da048bf669aa2fb9412b03dc9977d8f` (34 task paths). Normal Direct identity now consumes retained primary callbacks and supported code/default/literal/helper facts; source-backed managed capture joins its captured bytes/origin before lookup, while Installed/Versioned retain explicitly qualified declared-installation authority. Captured semantic IO order/types/required-nullability/image/bounds and declared distribution/version tokens join the same key and provenance; obsolete `dev_mode` and `get_source_hash` APIs are removed without aliases. Future platform T1 callers must migrate those APIs when adopting the candidate; current installed platform pins and old APIs remain unchanged. At that source revision, ordinary managed declaration parity remained OPEN because task/result v3 had no controller schema attestation; installed/transitive worker byte closure remains open independently. Custom admitted bytes provide stronger source authority without sealing arbitrary post-load class/global state. Continue remaining MAIN obligations, including broader DataFrame sealing/quota/planning cleanup, before SECONDARY and milestone gates. Continue broader C07/C08 and remaining MAIN obligations before secondary effects/tooling/science and milestone validation; these increments do not close every candidate or the library milestone. Scientific identity consumes admitted executable origin; collective association, reference access and exact result/group ownership share task/result/assembly boundaries. Local Direct/managed WorkerPool and mixed launcher local result APIs remain essential; actual Parsl/Dask/remote/distributed implementation and capability tests stay excluded. Candidate-source capability-only CI may validate repaired milestone requirements while release/publication/platform actions stay paused; the exact source/CI task plan is coordinated separately. A file ledger supplements causal/oracle evidence, not certification: all 230 package-source paths have owned or feature-excluded dispositions, with full bodies and ranges distinguished, and all573 historical classifications stay frozen. Preserve current metadata/artifacts, held WIP and existing environments; use focused/subsumed checks, one upfront scope and one final review, no backward-only layers, cleanup after consumers and desktop-last. Every task packet must carry accepted intent, active wave, shared interface, owned paths, causal oracle, current baseline and local/distributed boundary. During library repairs, inspect obvious repeated reads/hashes/copies, row-wise pandas work and unnecessary dispatch along the changed public paths; preserve precision, association and ownership, measure representative before/after scopes for accepted optimizations and queue unmeasured candidates without claiming all opportunities are exhausted.
- The finite managed declaration attestation and operation-metadata increment is committed at 80444eb27c1833f05d6afd75ef5fe4b715059cf1 on `116a400` (31 task paths). Task/result v4 carries one shared Core portable declaration projection and the successful actual digest; loaded worker instances and Direct retained callbacks must match before the scientific method, and controller correlation rejects mismatches before accepting outputs/cache publication. The declaration contract epoch prevents reuse of prior unattested cache keys; local dynamic DataFrame/no-Outputs/Passthrough remains explicit. This closes represented declaration parity, not arbitrary initializer effects, custom validators, post-load mutation or installed/transitive dependency byte closure. Operation-owned distribution discovery shares one package map across import roots and refreshes version/absent facts on each new operation; exact selected-version roots stay independent. Next MAIN is owned staged install/readiness and canonical dependency-conflict admission, followed by remaining MAIN/SECONDARY and one library milestone; technical publication/platform gates remain paused until that milestone, and the campaign continues through M5.
- The finite staged-installation/readiness and selected dependency-authority increment is committed at f1bc2f90fc4579644337a571ce501f1548a8a45f on `80444eb` (20 task paths). Occupied incomplete/mismatched targets refuse before pip; fresh installs use private same-filesystem staging, pure METADATA/RECORD/import-member admission and native no-replace publication, with cleanup restricted to owned staging and primary failures preserved. Controller selected installations and managed runtime dependencies share one scoped Core admission/context with explicit authorities, caller-path restoration, metadata-backed membership and active requirement checks; managed workers never add the controller dependency store to their import path. Dependency facts join captured cache identity/provenance without claiming selected/environment bytes equal, and operation-owned metadata snapshots preserve live-module checks while avoiding repeated RECORD/METADATA parsing. The normal current SDK20 actual worker confirms compatible runtime NumPy versus a poisoned controller store and pre-method incompatible-requirement refusal, with exact current module bytes and physical cleanup. Next MAIN is native-array acceptance, execution-owned DataFrame inputs and exact namespace-acquisition rollback, followed by remaining MAIN/SECONDARY and one library milestone; the campaign continues through M5 and technical publication/platform gates remain paused until that milestone.
- The finite native-array/working-frame/acquisition increment is committed at c5c759ec0b9971febc99de580de5c26293c428cf on `f1bc2f9` (24 task paths). Plain native outputs and inputs capture independent immutable bytes once, preserve dtype/shape/values through explicit native NPY records and hydrate independent view metadata; C-contiguous accepted values reuse their bytes, while noncontiguous values normalize to C layout. Current Processing/DataFrame keys include one execution-contract epoch, invalidating earlier framework semantics without a cache-format migration. Direct and worker row callbacks publish before the next callback, batches once, with nonterminal snapshots separated from one final result group and physical grant drain. Execution supplies one owned mutable working DataFrame to the captured merge hook; native pixels and finite container leaves are independent, while sealed SharedArray descriptors retain their admitted owner/backing. Exclusive root/task acquisition failures roll back only newly created namespaces and preserve the primary error; nested lexical owner activation restores the outer owner and caller without implicit close. Next MAIN is bounded C09 run setup/outcome/reentrancy/shutdown evidence, with C01 finite record-container admission and C05 pointer/key joins queued; C08 quota/planning/global-grant and broader ownership residuals remain explicit. The campaign continues through remaining MAIN/SECONDARY, the accepted library milestone, technically gated publication/platform adoption and DesktopM5 last.
- The finite C09 failure-finalization increment is committed at b1c2a553d3b9ec879603b1322a5d8334e989c8dc on `c5c759ec` (28 owned physical paths, including one renamed test). Newly admitted execution contexts become logically failed on setup/scientific failure, while an exact run-directory acquisition ticket and detached attempt-directory authority restrict persistence retries to owned identities. Original scientific errors survive failed terminal writes, optional progress observers and strict engine-owned shutdown; rejected reuse preserves prior active/deferred/succeeded contexts. Observers receive frozen events outside scheduler locks and own concurrency safety; immutable diagnostic history and registered-persistence-only `cleanup_pending` remain separate from physical pool/grant retirement through explicit `engine.close()` retry. The accepted scoped source/owner/quality/docs checkpoint changes no SDK bytes and does not close the entire C09 family: transient Processing failure-persistence masking remains an explicit MAIN residual. Next MAIN is C01 finite-container record admission with one Core traversal/neutral portable-cell adapter, then the prepared C10 atomic-publication causes, C05 pointer/key and explicit C08 quota/planning/global-grant residuals; remaining MAIN/SECONDARY and one accepted library milestone still precede technically gated publication/platform adoption and DesktopM5 last.
- The finite C01 record-container increment is committed at d9a17b79600552b251a5103a52d73b0be1aa3ff7 on `b1c2a553` (15 task paths). One Core finite-container traversal with explicit leaf roles and one neutral portable-cell adapter preserve list/tuple kind, ordered primitive dictionary keys, exact scalar dtype/bytes, precision, nonfinite values and signed zero through canonical Parquet records. Nested Path/native/SharedArray leaves require exact manifest role/cell authority before hydration and use existing result-group leases rather than task locators; execution-owned working inputs protect pinned providers from custom merge mutation. Default task/result v4 is unchanged. Scoped public/record/default-worker checks and one normal SDK20 actual-child proof validate this finite increment, not the whole C01 family or packaged cohort/OS/support-floor milestone. Raw container constant/default key normalization remains an explicit next C01/C05 causal join, followed by prepared C10 atomic-publication causes and the transient C09 primary-error residual; C08 quota/planning/global-grant, other MAIN/SECONDARY and accepted milestone gates remain before publication/platform adoption and DesktopM5 last.
- The finite C01/C05 parameter-identity increment is committed at e2def49cbb3cf637001e59413933aa4c214c228b on `d9a17b79` (5 task paths). One selective computation-key projection uses the existing portable identity only for actual Processing constants/defaults and declared DataFrame parameter fields, preserving container kind, primitive dictionary-key types and exact scalar facts without rewriting runtime arguments. Binding/template/provenance/code descriptors and synthetic root-frame digests retain their structural authority; declared Enum choices retain primitive-value semantics. Three public wrong-record-reuse baselines recover, while equal omitted defaults and explicit values keep warm reuse. SDK/task4/record cell bytes are unchanged, so prior normal SDK22c0 and record proofs are retained without rebuild. Next MAIN is the prepared C10 no-replace/export-ZIP/public-return causal slice, followed by the transient C09 primary-error persistence residual and other explicit C05/C08/main/secondary gates; no whole C01 closure, milestone, publication/platform adoption or DesktopM5 certification is implied.
- `docs/developer/platform-test-start.md` starts or resumes the user-authorized campaign through the compact current checkpoint. Continue the accepted causal repair queue without restarting completed reviews or reloading the historical diary; retain unchanged successful phases and consult older evidence only for a named finding, path or source revision. The orchestrator owns the current checkpoint and task-bound validation proof; scoped subsystem work and independent review preserve their assigned source boundaries.
- The user explicitly authorizes continued execution until the END of the whole campaign: coherent source commits/checkpoints are progress boundaries, not stopping points or requests for renewed permission. After the accepted library milestone, continue technically gated publication, platform API/pin adoption and T1/I1, complete M3/M4, and execute desktop M5 last; standing release authorization remains valid and does not waive technical gates. Reuse stable existing worker/artifact drivers and content-bound recipe dependencies, group causally overlapping repairs, retain unchanged successful phases, and request a new design decision only for a genuinely unbounded ambiguity.
- Campaign repair packets trace owners, callers, storage/events, generated types and public library/dependency contracts to distinguishing tests and required completion scopes. M0–M5 define complete review, repair, coverage and certification milestones with low-frequency retrospectives; desktop execution belongs only to final M5. Preserve valid unchanged phases and measure setup/test costs without weakening coverage or claiming unmeasured CI savings.
- Campaign task worktrees have an explicit cleanup owner and retirement checkpoint: preserve actionable evidence and held/dirty/unmerged changes, verify no active process, remove only completed task-owned disposable dependency/runtime/build stores, then move clean merged source to Trash, prune and delete its merged branch as AGENTS requires. Record reclaimed versus trashed bytes and retain public lifecycle rules for managed/shared/adopted environments; authorized unused-tree housekeeping supplies no product evidence.
- `docs/developer/platform-test-architecture-audit.md` records the initial selective architecture/test synthesis and the completed agreed-scope M1 review with per-file status and content hashes; the findings register records all identified future actions. Repairs/tests remain held until every human-written platform/library/Wetlands input and held WIP file is reviewed, generated/assets are specifically classified, and independent completeness review accepts zero pending/unmatched/hash-mismatched entries. Inventoried or selectively inspected source is not complete review or application certification.
- `docs/developer/platform-supplemental-architecture-review.md` supplements M1 with detailed current task chains, module/dependency ownership, high-risk cross-layer source samples, suite/specification assessment and explicit dynamic unknowns before further repair selection. Its companion `platform-architecture-candidate-dispositions.tsv` preserves all 573 original qualified candidates, including current-versus-historical evidence and responsible owner/trigger; neither file certifies every candidate or replaces the frozen per-file ledger. Keep caller incarnation, accepted revision, catalog freshness, presentation intent and physical lifetime as separate authorities when selecting follow-up repairs.
  The accepted October 3 archive-containment and Core object-dtype repairs are owning source commits `d4ba925` and `86a84fd` in the isolated library tree, not updates to the platform’s installed `dff04e3`/Core 0.4.1/Wetlands 2.4.2 runtime.
  The October 3 user direction requires one clean coherent current platform/library/Core design without backward-only aliases, dual formats or compatibility layers, preserving essential features, current data/recovery and ownership.
  Source-cache identity is accepted at `063d81c` and the single-current typed worker contract at `8c1e668`; uniform shared-array lifetime is independently accepted at owning source commit `6551f0b`, but is not adopted by the platform.
  The current owning candidate uses numeric NPY2 files and zero-copy mapped views inside explicit controller scopes, with bound result references retaining ownership independently of temporary Workflow execution; ordinary exact-result-group discard releases its leases, while automatic compute/GC never requests whole-owner closure or idle worker-pool retirement. Group/read/task/grant ownership controls backing reclamation; arrays admitted by these APIs do not imply arbitrary DataFrame/native ndarray immutability.
  Explicit release remains pending until local readers and physically retired worker grants drain; decoding performs no attachment, and worker close cannot delete controller buffers.
  This is source-development context, not availability in the platform's installed `dff04e3`/Core 0.4.1/Wetlands 2.4.2 runtime: the owning source includes force integration/current cohort metadata from `2cd79a2`, the capture/schema increment at `936c440`, the bounded numeric/pinned/loader increment at `d6865b1` collective/record-admission increment at `cb83afc` and finite sealed-array/group increment at `b6f84cc499d7938602d51f2796d1f76406195828` plus admitted executable-key increment at `116a40015da048bf669aa2fb9412b03dc9977d8f`, but supported-OS/artifact/CI/publication and platform T1 remain separate gates paused behind the October 4 library phase.
  The inherited v1 Section 2.8 now specifies explicit application-owned scope release after physical worker-grant and reader drain, with truthful pending/error reporting; runtime adoption remains part of platform T1, not implemented by this documentation checkpoint.
- `docs/user/` is public user documentation and should describe released user-facing behavior without exposing this internal orientation file.
- `backend/src/bioimageflow_server/data/demo_workflows/` contains bundled deterministic workflow artifacts.
- Fish Analysis gives its marker branches distinct internal node IDs and runs in parallel using the sibling editable BioImageFlow source, whose worker-thread scope propagation preserves nested result identities and Node Data views. Its summary groups mapped overlap rows by their immediate parent image row index.
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
5. `platform_specs_napari_environments.md` is the feature-specific implemented viewer/environment extension, with explicit remaining gaps and native certification obligations; it overrides v1/v2 in that scope.
6. `platform_specs_v3.md` is a future authenticated multi-user proposal building on existing deployment modes, not evidence that a feature is implemented or an override of current storage/results contracts.

[`platform_specs_napari_environments.md`](platform_specs_napari_environments.md) is the completed Phase A design and phased implementation authority for multiple napari environments: named local environments, portable output viewing requirements, one exclusive toggleable favorite per structural output identity across all rows and future results, filename rules with extension shortcuts, deterministic environment selection, and setup guidance.
Its package-compatibility contract uses installed Python distribution metadata and PEP 440 constraints independently of npe1/npe2 manifests, plugin discovery, and enabled flags; reader identifiers remain separate launch instructions and actual reader/plugin failures are launch-time outcomes.
Managed creation uses Python 3.12 from Conda and installs the remaining distributions from PyPI, with napari 0.9.1/PyQt6 as the default matrix and napari 0.6.6/PyQt5 as the older smoke matrix.
Its coordinated portable contract uses canonical recursive schema-v2 graphs, explicit schema-v1 normalization, strict viewer metadata, normalized artifact hashes, and a previewed, explicitly confirmed, byte-backed-up, forward-recoverable saved-document/root-draft/nested-snapshot migration.
Its Phase B backend foundation implements the settings-backed environment registry, explicit immutable launch/managed identity, package-only bounded probes, singleton adoption, revisioned desktop-only routes, and ordered filename rules.
Startup adoption still does not create the required setup-needed default recipe when no legacy installation exists; explicit managed creation does not close that known requirement gap.
Phase C implements UUID-keyed lazy launcher processes and locks, frozen registered-environment argv dispatch, public Wetlands generation-owned spawning for recipe-created managed entries with a narrow persisted-interpreter fallback for adopted legacy Wetlands 1 workspaces, per-environment napari settings files, optional explicit reader dispatch, Qt-completion acknowledgements, typed open failures, unknown-outcome no-replay semantics, and attributed lifecycle status/events.
Its dedicated environment launch route starts an empty viewer without dispatching `viewer.open([])`.
The managed installer backend implements strict default, legacy-smoke, and explicit advanced recipes, PyPI-only requested distribution validation, immutable create/copy generations, durable public-Wetlands operation progress/cancellation/restart reconciliation, metadata-only validation probes, and ownership-proven removal coordinated with per-environment launcher shutdown and an idempotent local-reference cleanup seam.
The legacy no-ID open/status/shutdown contract remains as a temporary desktop compatibility path; explicit launch IDs never provision or mutate registered environments.
Its Phase C backend implements immutable public result identities, retained per-result viewer metadata lookup, package-only compatibility resolution, archive/readiness reports without implicit installation, and a separate CAS favorite store integrated with environment forget and workflow identity move/delete recovery.
Portable viewing manifests can also be submitted directly to the desktop-only passive readiness endpoint before any result artifact exists; it shares the resolver's installed-distribution and PEP 440 candidate evaluator, preserves output identities and unknowns, and groups identical normalized requirements without implicitly unioning different outputs.
Resolve responses return the exact server-derived persistent output-preference key, including durable workspace identity, rather than requiring clients to infer it from existing favorites.
Nested favorite finalization derives its destination from the stored snapshot owner and remaps only after the accepted parent snapshot or current root draft embeds the exact child graph; unsaved roots cannot create durable favorites.
The frontend Image Viewers settings UI manages registered and managed environments, defaults, ordered filename rules, lifecycle operations, and empty launches. Passive viewing checks still guide workflow import and prefill managed setup, but the per-output readiness report is not shown in Settings. Forgetting an adopted legacy installation suppresses its automatic startup adoption; external entries can be located again, and package changes are checked through inventory refresh rather than executable-file identity.
Focusing an already visible Node Data dock preserves its projection and cell gestures; hidden-to-visible transitions refresh its projection.
Result tables use a backend-resolved exact-artifact split action for deterministic environment selection, one-shot overrides, replace-layers dispatch, and one exclusive toggleable favorite per structural output identity.
Chooser actions capture their retained artifact, structural output, environment, reader, and server-derived preference key; selection replacement withdraws stale actions, and deferred or disposed continuations cannot retarget a newer chooser or replay an issued operation.
Native desktop smoke certification for this feature remains incomplete and must not be inferred from mocked or headless checks.
Read it alongside the v1 viewer/settings sections and v2 output/import/export contracts when designing or implementing multiple napari environments; do not introduce row favorites, row exceptions, result-row preference storage or migration, or a favorite scope selector.

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
| Datasets, browser mode, authentication, security, or multi-user behavior | v1 Sections 2.4.10 and 3.14 plus v2 Section 16 for implemented datasets; consult v3 only for work explicitly targeting the proposal and distinguish inherited behavior from proposed behavior |
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
