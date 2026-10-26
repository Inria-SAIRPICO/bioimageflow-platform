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
Detaching that provenance refuses while an editor at or below the target is open, using its exact canvas/workflow or private-session owner and node identity rather than a source name or global node ID.
After that editor closes, Detach changes only provenance and preserves the embedded graph, bindings and independent source workflow.

### Three persistence contexts

Do not conflate the following states:

1. A saved root workflow is persisted as a `WorkflowDocument` in the workflow directory's `workflow.json`.
   The envelope contains the canonical graph, workspace metadata, artifact hash, optional Python-authoring provenance, and owned local-source identifiers.
2. An open root canvas edits a durable workflow draft under that workflow directory.
   Draft writes use expected-revision compare-and-swap, record their writer, validate the accepted graph, and track whether the draft differs from the saved artifact.
   The canonical root persistence resource separately tracks local semantic changes and pending draft writes; an accepted external graph may remain dirty against the saved artifact and continue receiving newer revisions while only recovery persistence is pending.
   Same-graph validation preserves that origin, Keep my canvas preserves local ownership, and explicit external resolution or clean accepted Save clears it; a remounted dirty frontend draft remains conservatively protected because its earlier semantic origin cannot be recovered from writer metadata.
   Revision-zero synthesis captures one saved graph/hash/metadata snapshot per existing mutation-lock phase; captures expire as current saved authority at lock release and later phases and requests recheck current saved/draft authority, generation and storage.
   Each projected GET attempt reuses one public compilation outside the mutation lock and at most one plan under the final authority/Clear fence, without retaining compilation or metadata across requests.
   Synthesized responses adopt complete definition diagnostics and resolved schemas; persisted accepted drafts retain their non-cache diagnostic/schema authority, and execution authority helpers remain strictly validated.
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
Catalog and format discovery walk workspace folders freshly and stop at workflow.json boundaries, without traversing workflow-owned results or sources; one catalog operation reuses its own path snapshot.
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
Dynamic output-schema inspection carries its originating root workflow identity, including for nested canvases, and resolves owned sources in that workflow’s directory.
Unavailable compilation returns an unresolved schema rather than dereferencing a missing workflow; named inspection rechecks workflow identity and storage before publishing its result.
An incompatible runtime recipe retains its node-attributed validation error without attempting cache planning for that refused graph.

Frontend graph and workflow-draft routes/response types are generated from backend OpenAPI into `frontend/src/api/types.ts`.
The draft client's remaining handwritten response/conflict shapes are transitional debt and do not supersede the generated-only authority.
When an API model changes, update the backend model and schema first, regenerate the frontend types, and adapt consumers instead of introducing handwritten compatibility copies.

### Tools and sources

BioImageFlow distinguishes processing tools, which process rows and can write templated outputs, from DataFrame tools, which create or transform DataFrames.
DataFrameTool parameter fields accept constants, including constant-valued published workflow inputs; their metadata reports no column pin.
Complete upstream DataFrames connect positionally, and the library rejects column or node-shorthand bindings to DataFrameTool parameters, including through recursive workflow interfaces.
Tool annotation introspection resolves postponed and inherited annotations while preserving GUI and image metadata, so registry schemas and execution validation describe the same declared types.
Tool metadata describes tool type, inputs, outputs, parameters, packages, versions, resources, row-consumption semantics, and capabilities.
Output metadata preserves each field's required and nullable facts from the library schema.
Tool-store scanning and explicit package lifecycle operations admit package/version selectors through the library, ignore unsupported directory names including private installer staging, and keep genuine selected-installation failures visible without replacing their original diagnostics with cleanup errors.
Installed tools use an admitted generation selected by the exact canonical store root, package and version; installation metadata, selected controller dependency compatibility, source content and installed inherited owners are captured once and reused while that selection remains immutable.
The normal dependency manifest and lock select published BioImageFlow 0.9.6/Core 0.5.1 with this workflow-loading lifecycle.
See [Workflow Loading Performance](docs/developer/workflow-loading.md) for the admission lifetime, fixture isolation and cold/warm measurement protocol.
Repeated workflow compilation and planning reuse those installed facts rather than walking host distributions, RECORD files or installed sources again.
Editable and workflow-owned sources retain fresh capture for each operation, independently of watcher delivery; invocation declarations, parameters, inputs, runtime readiness and selected result-record integrity remain current checks.
Portable CPU/GPU/memory/GPU-memory resources are worker requirements with author-declared floors, while maximum concurrency is a submission cap; actual capacity, allocation, and enforcement are backend/site-owned and resources do not affect cache identity.
Missing or null resource fields inherit the declaration; the resource form enables Reset all only for explicit overrides, including numeric zero subject to normal validation.
The registry describes catalog tools; validation returns node-scoped metadata from the actual compiled class for source-bound and explicitly bound portable tools, without replacing same-named registry entries.
Saved-workflow dependency diagnostics capture exact owned source bytes without changing the canonical graph or compiling it; explicit flat workflow-local module bindings resolve their contained file before catalog lookup, and present invalid source stays available to Open for repair.
Saved-workflow dependency diagnostics resolve that same carried executable identity through the public class loader without compiling, planning or provisioning; an unavailable explicit binding cannot borrow a same-named catalog entry.
Canvas hydration uses node-addressed metadata from the same accepted graph and root workflow or nested session before reconciling input/template presentation; unavailable metadata cannot erase authored parameters or output templates.
Pending validation or a global compilation failure may retain the bound node’s prior captured presentation metadata, without borrowing a same-named catalog class or treating that metadata as execution authority.
Installed bindings retain their package/version and read-only provenance; owned sources retain their editable custom provenance.
Custom-tool hot reload supplements native filesystem events with content checks limited to registered editable source directories, so missed editor-save events cannot leave metadata stale.
Successful editable code-only reloads also notify canvases for validation and cache-status refresh; failed edits retain prior presentation metadata for repair without authorizing execution of stale code.
Installed file events, including staging writes, do not trigger automatic reload.
Controlled package refresh retires the old generation before admitting a replacement through the public loader; it preserves installed RECORD members, including pip-generated bytecode, and a failed replacement remains unavailable rather than restoring retired classes.
All affected generations are preflighted together before uninstall or an actual store-root transition; active admitted operations refuse retirement without changing files or registry state.
Uninstall reserves retired package/version namespaces through physical removal and registry update, so concurrent workflow reads cannot re-admit the still-present directory.
Selecting the same global store for another workspace does not retire its generations, and replacing controller dependencies requires a process restart.
Every processing tool declares `row_consumption` as `mapped` for independently consumed rows or `collective` for a batch that may combine aligned rows; DataFrame tools expose `null`.
The canvas derives column-edge strands reactively from the target tool metadata and does not persist this presentation state in the graph.
Do not infer structural names from UI labels or filenames.

Installed package tools are versioned dependencies resolved through the tool store.
Package uninstall uses the exact optional query version and contained stored directory identity, independently of successful imports or registry membership; it rejects unsafe selectors, links below the configured root and observed root/package/version substitutions before removal or failed-trash fallback.
An omitted version selects the whole package, while an empty explicit version is invalid; successful selected removal preserves other packages/versions and does not own Wetlands environments.
Retirement follows path admission and precedes physical removal; supported versions are selected from the stored directories even when catalog discovery failed, while safe unsupported legacy names remain removable without SDK admission.
Install and uninstall explicitly publish registry diffs without depending on filesystem events, and a selected package that cannot be indexed fails installation with its original load detail.
A carried module/class/package/version binding takes precedence over a same-named catalog entry during translation and compilation; only explicit version rebind changes that dependency.
Explicit package references remain package requirements even when the catalog has a same-named custom tool, while module/class-only references are local references without an invented package requirement.
The platform app environment supplies `pip` for tool-store package installation; versioned and source-import paths install only the selected tool distribution through the app interpreter, using the already installed compatible controller dependencies.
Processing recipes provision their worker dependencies through Wetlands at execution preparation, independently of tool-store installation.
Workflow-local tools are editable source files owned by a workflow and travel with its exports.
Custom-tool usage reports traverse saved recursive graphs, distinguish tool and workflow nodes, and return each affected workspace-relative workflow ID once.
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
Catalog search derives a reactive index from names, display names, tags, categories and documentation words, splitting identifier word boundaries before normalization.
It preserves all-token exact partial matching and stable catalog order, and permits one conservative whole-word edit for otherwise unmatched tokens of 4–64 characters without new wire metadata or stored search state.
The Manage Tools inventory is independent of the catalog search query, and its tool information and actions expose each declared managed environment's location and explicit create/recreate operation.
Tool metadata resolves all declared environment locations from one fresh public inventory per request, off the event loop, without provisioning or retaining that inventory between requests.
Validation returns source-specific node metadata without registering imported classes in the global tool catalog.

Trusted `workflow.py` files are authoring inputs only.
Building from Python materializes a canonical graph and its allowed source bundle; running, nesting, copying, reopening, and exporting use the materialized graph and do not import the authoring source.
Python preview retains runtime-source records from the strictly validated library archive independently of its viewing metadata, and Apply stages those captured records with the graph without rerunning the factory.
Accepting the materialized root graph also updates that canvas's presentation label from the accepted graph without changing its workspace workflow ID.

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
Result conflicts distinguish transient result_pending from rejected result_unavailable; individual and consolidated tables retry only explicitly pending publication, and display permanent failures immediately without polling.
Unsupported retained cache formats keep their files intact and report the validation cause with regeneration guidance rather than claiming that waiting will make them readable.
Individual and merged modern Node Data responses take column types and image viewers from the captured result's public producer declaration, using the same admitted DataFrame and immutable record rather than a same-named catalog tool or another result read.
Missing or explicitly dynamic producer output declarations use value inference; malformed retained declarations are unavailable, while unpinned legacy results keep their existing catalog behavior.
They measure only visible, font-ready content and persist deliberate user widths by workflow/table and column identity, never automatic DOM measurements; **Reset column widths** restores content sizing.
The browser image-viewer action checks its selected result's offsets through the same-origin backend API before opening the external Avivator iframe, so an unavailable conversion is reported locally and the unchanged action can retry without opening a broken panel.
Node-image, thumbnail, and Reveal requests resolve relative owned image paths against the immutable record captured for that request through the library's public asset API; absolute external image paths keep their declared location, and legacy unpinned results retain their existing lookup rules.
Thumbnail setup and per-fingerprint renders are service-owned shared jobs: request cancellation and repeated selections cannot cancel or duplicate them, and shutdown joins submissions and startup before closing the pool.
Thumbnail replies distinguish pending, ready, failed and unavailable states; cold setup stays pending until a real terminal outcome, shows a preparation notice only during actual environment mutation, and publishes PNGs atomically.
After the initial three-second progress wait, cells use bounded 20-second completion waits with a short fixed retry gap; retained-result I/O runs off the event loop, and latest DataFrame reads reuse their admitted run-node relation only within that read.
BioIO retains format/reader ownership and lazily computes the middle T/Z preview with channels and RGB(A) samples; versioned cache keys cover file metadata and directory-store descendants, including OME-Zarr chunk changes, with fingerprint walks and cache reads kept off the event loop.
Visible cells coalesce in-flight requests, cancel only their own interest, and revalidate row-addressed URLs rather than using stale browser responses; the server owns the fingerprinted disk cache.

Local execution and cache clearing load one exact accepted root draft by workflow ID and revision after the canvas freshness barrier.
Progress callbacks retain that run's immutable identity and are ignored after it stops owning the active running context.
The execution banner's single overall bar uses the run's retained scoped executable leaf-node plan, including cached and selected dependencies, rather than the active canvas node count. Its text distinguishes completed nodes, current row position or completed rows, and per-row task progress; a successful run reaches 100%.
Graph mutation is locked where required while an attached execution owns the mutable platform context.
Context-menu Delete and Group refusals during that lock leave the canvas graph and history unchanged and visibly explain the lock.
Ordinary accepted graph mutations serialize through the same admission gate: a mutation reservation blocks Run, concurrent mutations wait their turn, and an actually starting/running execution or terminal shutdown refuses new admission.
Run Selected first compiles the complete accepted graph, derives requested root nodes and their transitive upstream roots from its edges, and ignores only diagnostics proven by their scoped node paths to belong to unrelated roots.
Selected and upstream workflow boundaries own their descendant diagnostics, while global or unattributable diagnostics, unknown or unresolved targets, and a missing compiled workflow remain blocking.
Only when proven-unrelated construction diagnostics would otherwise leave a non-executable diagnostic workflow does the same public compiler materialize an honest selected/upstream root projection, preserving nested boundaries, configuration, relevant edges and interface identities.
Every diagnostic from that second compile blocks execution, and accepted draft authority is checked again before dispatch; clean selected graphs retain one compilation.

Recursive graphs compile to scoped jobs while workflow nodes project aggregate descendant status in validation and retained execution completion.
Caching and result attribution remain per internal tool node, and failures preserve their scoped path through nested workflow boundaries.
An opened nested canvas maps its local node IDs through its durable owner chain to the root execution's scoped IDs for status, progress, and Node Data; private edits use the nested editor's validation until applied.
Every platform-owned Wetlands provisioning path forwards public environment-operation events, including sanitized Pixi output, to the Logger panel. Local workflow execution passes a run-scoped environment observer to the public engine API, keeping the shared Wetlands manager's methods unchanged while attributing provisioning to the correct execution and node. Retained job snapshots carry a setup message independently of numeric row progress, so the Execution panel distinguishes environment installation from tool execution.
Published BioImageFlow 0.9.4 supplies the explicit executable `scoped_node_path` for each preparation call; the platform captures that scope with immutable run context rather than inferring it from environment names, shared receipts or the last started node.
Setup can appear on a waiting job before scientific start without inventing a start timestamp or numeric progress; late observations cannot mutate a newer run.
Explicit public failure diagnostics own node details, while unscoped exceptions remain run-level; unsuccessful completion settles known running presentations without assigning a culprit and preserves explicit completed, failed and disabled states.
The run observer forwards public preparation, provision and removal events during runtime admission before scientific identity and cache lookup.
Admission emits ready status when no pool is running and preserves an already-live pool status; it never starts a pool itself.
A warm cache hit does not start new scientific work or hide the controls needed to retire an existing pool.
The tool environment service supplies the same reentrant preparation guard to Run, manual lifecycle operations and its background default-general refresh, coordinating authorized admission and exact receipt/grant handoff without holding the guard for scientific task completion.
Manual Start, Stop and Create/recreate resolve the exact declared environment name, all matching complete recipes and its current lifecycle owner after acquiring that guard; aliases, conflicting declarations and protected owners refuse before manager, progress or catalog effects.
The execution manager holds exclusive idle admission through the full manual service operation and its final status publication, including physical settlement after repeated task or scope cancellation; active execution or terminal shutdown returns 423, owner refusal 403, invalid or unknown declarations 422, and unavailable controls 503.
A canceled request preserves its original cancellation after the owned operation settles, retains an operational failure as observable, and allows an explicit later retry without replaying the original action.
BioImageFlow compares requested processing recipes with Wetlands-managed state before use. Stale platform-owned processing environments are closed and replaced lazily through Wetlands, while an already-existing stale `bioimageflow-general` environment is refreshed in the background after startup. User-managed, external, Napari, adopted, thumbnail, and code-server environments remain under their own lifecycle owners. An explicit tool requirement that cannot use the platform's exact `bioimageflow-core` runtime is a graph validation error.
The campaign library now admits Wetlands2.6 ready-runtime content before managed Processing keys and cache lookup, with one content admission per augmented recipe and operation and separate generation/recipe/lock fences.
Published and PyPI-verified Wetlands2.6.1 captures complete installed authority: a uniquely anchored installed Conda manifest governs transformed Conda packages; other distributions require raw complete RECORD, and missing retained members refuse ready publication.
Published BioImageFlow 0.9.2 exposes preparation/provision/removal observers and explicit stale replacement through public `admit_runtime`, so an authorized consumer can prepare before identity/cache lookup without starting workers.
Metadata-only admission performs no writes or worker starts; a held receipt is revalidated and cannot authorize another recipe or stale replacement during dispatch.
The platform adapter forwards this public admission/receipt/grant boundary; dispatch relies on the public manager's atomic generation fence and cannot provision or replace an already admitted generation.
Execution copies durable output projections and installs a verified bundle through public `WorkflowExecutionContext.export_result_bundle` before closing its engine and releasing its exact captured result groups.
Bundle-only export returns the installed Path and does not hydrate a second array result; archive and retained download verification use that same durable destination.
Failed persistence, engine, group or controller cleanup retains the original owner for retry and preserves an existing scientific primary error while attempting independent cleanup.
Application close terminates new execution admission, settles active execution and environment refresh, retires only an already-created shared processing manager, then retries retained controller scopes after physical grants drain.
A warm application-owned pool can retain physical grants until retirement; per-run completion does not certify per-run zero physical resources.
Its configured-backend planning reports unavailable ready authority as PENDING_RUNTIME without managed provisioning, worker startup or content probes; metadata-only planning preserves record/asset integrity reads without array hydration or controller array-owner allocation. Ready warm hits do not start a scientific pool.
Column-bound planning and computation normalize omitted defaults to the same effective scientific constants, preserving existing compute keys and exact selected records while retaining bound-column, value and container distinctions.
The campaign library admits the finite selected primary Python package and inherited constructor/row/batch owners before runtime preparation and cache lookup.
Installed owners follow their immutable admitted generation; editable owners retain operation-local capture, and controlled retirement prevents new operations from using retired classes.
Canonical worker tasks retain the same admitted source bytes through scientific callbacks, including lazy imports; Direct retains its actual callback authority.
Direct Processing scientific identity captures both effective row and batch callbacks independently of its selected execution callback map; all source-bound Direct tools pair admitted source bytes with actual supported inherited/runtime callback evidence.
Published BioImageFlow 0.9.2 keeps exact declared output-class authority separate from its detached validation facade, allowing original global Outputs returns while retaining strict captured field/value validation.
Direct dispatch refuses finite nominal declaration/default drift before callbacks; cached captured records and arbitrary callback-global or concurrent external mutation guarantees remain separate boundaries.
Its source/normal-wheel controls, independent review, ordinary exact-source CI and actual PyPI verification pass; platform cross-stack adoption is committed at `1ca0d1f` through the scoped phase assembly in the current checkpoint.
The subsequent actual returned-array control exposed a root-boundary export-route scope mismatch in published 0.9.1.
Published and independently PyPI-verified BioImageFlow 0.9.2 now preserves synthetic root versus real nested provider routes, shares one verified installation path between materialized and bundle-only export, and retains SDK-created hydration-root disposal authority in exact result groups until physical drainage or retry.
Caller-created memory owners remain under their own lifecycle; same-root live groups cannot be revoked by disposing a sibling.
Published BioImageFlow 0.9.3 shares imperative and portable workflow output source resolution: absent/null output schemas retain known source type and image semantics through recursive interfaces, while explicit carried schemas remain authoritative and unresolved dynamic outputs stay unknown.
The finite construction-only controls execute no scientific callbacks; this patch leaves the accepted root-route, bundle transaction and memory-owner boundaries unchanged.
For the 0.9.2 repair, reviewed source is `7c329948`, normally merged as exact-tree `d7bc53dc`; ordinary exact-source CI passed fourteen jobs with one expected dispatch-only skip, and its single publisher plus both actual public archives match the reviewed source and tested candidate.
The platform uses the nonhydrating bundle seam.
Its actual published-registry array control passes independently: copied uint16 pixels and the verified ZIP remain correct after selected worker retirement, exact compute resources move from a truthful pending grant to all-zero public status, and an unrelated owner remains intact.
That finite result does not certify viewer guidance, forced environment mutation, distributed execution or native acceptance.
Campaign DataFrame merges now receive their actual positional working inputs without implicit parent-row coercion, with one execution-contract epoch change preventing reuse of earlier wrong records; column-pin and published-output alignment remain distinct mechanisms.
The finite actual managed lifetime proof now joins successful result discard, truthful quota refusal and explicit selected idle-pool retirement: physical grants drain while a retained read-only view and independent owner stay valid, then the identical controller allocation fits and final resources reach zero.
This proves the existing explicit retirement contract; automatic pressure scheduling remains optional and no scientific quota retry is introduced.
Cold publication by either tool family now reuses already sealed SharedArray references only for the admitted selected own candidate, preserving canonical stored frame/manifest/address and exact asset mapping; conflicting winners and mutable inputs keep exact hydration.
Shared-array mapping synchronizes buffered state on the same admitted descriptor before native cursor transitions and cleans only a newly created mapping on handoff failure while preserving the primary error.
The measured managed publication point uses two physical backings per result instead of four, while quota, view and retirement controls remain intact; this is a backing-residency saving, not an end-to-end speed claim.
Campaign source now also preserves absent-only native file publication, explicit child PATH and cleanup-primary ownership, with finite TIFF/OME unit/axis and harmonic-aware Phasor numerical controls.
The subsequent finite adapter source gate preserves used model/content stamps and singleton spatial dimensions, admits pinned Nagini geometry before publication, validates captured LapTrack object association and preserves Atlas preparation/reference ownership.
Its independent controls use fake model/native transport and do not certify learned-model runtimes or current platform adoption.
The numerical proof uses an exclusively owned local pinned science interpreter; the separately retained early Core candidate is not relabeled as current source, and managed recipe/OS certification remains separate.
These reviewed library changes are published as Core 0.5.0, BioImageFlow 0.9.0 and eight base-tool releases after ordinary exact-main CI and canonical same-wheel Linux/Windows Python 3.9/3.12 capability gates.
Actual PyPI wheel/sdist hashes and source bytes match the admitted release cohort, including the canonical Core wheel.
Wetlands 2.6.1 is also published and verified; platform dependency/API adoption, actual returned-array export/lifetime, T1 deterministic/real-provider/force-GUI and scoped client recovery/reopen, and I1 two-browser imported-viewer guidance are accepted with the distinct evidence limits in the current checkpoint.
Published common-tools 0.2.2 discovery/schema certification passes on normal BioImageFlow 0.9.3, Core 0.5.0 and Wetlands 2.6.1 (eight selected cases); actual worker/science, supported OMERO, native desktop and final audited campaign certification remain separate gates.
Arbitrary trusted Python state/dependency closure, whole merged-input provenance, external filesystem tampering and automatic pressure scheduling are explicit accepted boundaries; the campaign milestone and named remaining tasks remain open; the [current checkpoint](docs/developer/platform-test-current.md) holds source-bound proof and the remaining queue.
The backend dependency manifest resolves published `bioimageflow[parsl,psij]==0.9.6`, Core 0.5.1 and Wetlands 2.6.1 or newer from the registry; ordinary development and CI do not require a sibling source checkout.
The explicit scheduler groups replace a dependency-free `cluster` selection; installed package availability does not certify excluded distributed features.
The Python debug launch profiles use that backend environment.
Explicit `(local core)` profiles opt into the sibling `bioimageflow-core` project through `BIOIMAGEFLOW_CORE_SOURCE` and `PYTHONPATH`, and isolate their Wetlands state under the repository's ignored `.bioimageflow` directory.
Source investigations use an explicitly owned environment and do not supply published compatibility evidence.

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
Changing the persisted desktop workspace path retargets workspace-derived stores without migrating existing files; an explicitly configured store root retains its own authority.
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
Workspace agent setup creates its optional read-only platform source reference as a depth-one clone, including for a local development checkout by using Git's regular transport rather than its local object-copy optimization.
The reference remains separate from running application code, and clone failure remains nonfatal.
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
- Scientific tool fixtures use ordinary imported packages outside pytest-rewritten modules, so test-runner instrumentation cannot become their admitted executable authority.
- Executable development seed tools live in the finite ordinary `bioimageflow_dev_tools` package, separate from HTTP wiring and bundled workflow scripts; the server wheel includes both source packages without broadening library primary admission.
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
- [Current campaign checkpoint](docs/developer/platform-test-current.md) owns the active source revision, accepted outcomes, remaining gates and direct validation receipts.
- [Campaign start](docs/developer/platform-test-start.md) resumes from that checkpoint and the task-relevant specification/source; the historical progress diary is optional lookup evidence, never required restart context.
- [Specification intent](docs/developer/library-specification-intent-review.md), [test quality](docs/developer/library-test-quality-review.md) and [causal architecture review](docs/developer/library-causal-architecture-review.md) retain the accepted library findings and finite dispositions.
- [Platform architecture audit](docs/developer/platform-test-architecture-audit.md) and [supplemental review](docs/developer/platform-supplemental-architecture-review.md) retain source coverage, cross-layer ownership and qualified candidates; their ledgers are evidence rather than application certification.
- The current candidate's Task4/Result4 portable declaration and row/group contexts are checked before science and controller publication; normal Processing returns require a pinned selected record, while explicit public Storage/launcher transient workspaces remain separate.
- Canonical records preserve finite container kind, ordered primitive keys, exact scalar dtype/bytes, precision, nonfinite values and signed zero; Path/native/SharedArray leaves require exact manifest role/cell authority before hydration.
  Collective consumed-row groups and record relation/domain metadata preserve association independently of positional DataFrame merging and Processing column-pin alignment.
- Native values capture independent accepted bytes and mutable SharedArrays receive independent sealed backings; numeric NPY2 views retain explicit controller scope ownership.
  Exact result-group discard releases only its leases; readers and physical worker grants must drain before backing reclamation, and compute/GC never implicitly closes a whole owner or retires an idle pool.
- Selected package installation uses owned staging, METADATA/RECORD/import-member admission and exclusive publication; selected controller dependency compatibility and installed owners are admitted once for the held generation, while editable source evidence stays operation-local.
  Controlled refresh, removal and store-root changes retire generations only after admitted operations release them; arbitrary external installed-file mutation is outside that contract, and workers never inherit the controller dependency-store path.
  EnvironmentSpec captures a detached recipe and returns fresh ordinary projections, with exact/flexible Pip and finite Conda grammar admission.
- Execution setup/science failure preserves the primary error, uses captured run-directory authority for persistence, and reports truthful pending cleanup.
  Frozen observer events run outside scheduler locks; logical outcome, registered persistence retry and physical engine/pool close are distinct responsibilities.
- Workflow archives and output trees are staged before exclusive publication; persistent archive imports load from the final root and refuse occupied targets.
  Explicit output-tree replacement binds initial destination identity, preserves late independent owners and reports recoverable backups or committed installation with pending cleanup; JSON/ZIP replacement follows successful write/close.
- Viewer wire metadata is strict and detached; example downloads, metrics and previews use captured identities, and release tooling admits all artifact pairs before any upload.
  Core `py.typed` support is backed by the actual normal wheel/source-distribution marker proof, independently of source-only declarations.
  The candidate Parquet publisher avoids whole-file Python allocation; representative measurements and unchanged ownership controls belong to the checkpoint, not an unqualified speed claim.

### Campaign state and next adoption boundary

The selected local-library Phase 3 milestone is technically accepted, with source selectors, normal artifact/cohort checks, actual WorkerPool results and Core OS/Python floor receipts qualified separately in the checkpoint.
Its finite MAIN and SECONDARY obligations are complete within that scope; arbitrary trusted Python/dependency closure, external filesystem tampering, conservative merged-input provenance and automatic quota scheduling remain explicit limitations.
These accepted library contracts do not prove platform T1/I1, published tool compatibility or desktop acceptance.
The backend's actual lock selects normal published `bioimageflow[parsl,psij]==0.9.6`, Core 0.5.1 and Wetlands 2.6.1; the coherent prior platform source adoption removes retired `dev_mode` and `get_source_hash` callers without aliases or parallel formats and is committed at `1ca0d1f` through scoped phase assembly.
The subsequent 0.9.2 pin and bundle-only export adoption has its own exact export/tamper, mapped local completion and actual returned-array acceptance, with causally unchanged frontend/schema/browser phases retained; prior failed invocations remain failed and no monolithic app/full success is inferred.
The v1 application-owned scope release contract requires physical reader/grant drain and truthful pending/error reporting at that adoption boundary.

Release prerequisites are successful ordinary exact-SHA CI, the finite affected science/native gates and actual canonical Core wheel floor acceptance.
Core publication must match the held reviewed wheel hash before any selected package upload; capability dispatches cannot substitute for ordinary release-qualifying CI.
The earlier ordinary CI exposed distributed failures, including a bridge mismatch as well as fixture failures.
The user requires distributed features to remain excluded and local/distributed CI gates to be separate.
The implemented partition retains successful ordinary exact-SHA local release authority with auditable exclusions; the separate visible distributed workflow preserves its coverage and failures without distributed production repairs or a release-predicate waiver.
Published and PyPI-verified Wetlands 2.6.1 is the current library provider prerequisite; library/Core/tool publication and platform adoption remain distinct gates.

After release, prioritize coherent platform pins/public APIs and T1/I1 through ready runtime, selected primary, key/Storage, actual worker, pinned result and physical cleanup.
Reconcile the current source and accepted priority repair queue before M3 coverage expansion; a historical finding title alone does not establish a remaining defect.
Reuse authoritative ordinary-source/compile fixtures and the existing normal-artifact capability driver; preserve exact selectors, no-skip effects, source/OS/artifact qualifications and unchanged successful phases.
Build and validate one publication set rather than routinely rebuilding in both validate and publish modes; a changed Core digest stops publication instead of being relabeled as the tested artifact.
The user authorizes continuation through the campaign END, subject to technical gates and explicit scope decisions; M3/M4 follow adoption and desktop M5 is LAST.

Campaign task worktrees have explicit ownership and retirement: preserve held/dirty/unmerged work, stop owned processes, retire only completed task-owned runtimes/caches, then move clean merged trees to Trash, prune and remove merged branches as AGENTS requires.
Cleanup measurements supply no product evidence, and protected/shared/user environments and metadata remain untouched.
Keep caller incarnation, accepted revision, catalog freshness, presentation intent and physical lifetime as separate authorities when choosing follow-up repairs.
Use one clean current design without backward-only aliases or duplicate authorities, preserving essential features, current data and recovery.
Inspect obvious repeated reads/hashes/copies and unnecessary dispatch on changed public paths, but measure a representative scope before claiming an optimization.

### Remaining repository areas

- `docs/user/` is public user documentation and should describe released user-facing behavior without exposing this internal orientation file.
- `backend/src/bioimageflow_server/data/demo_workflows/` contains bundle version 6 with deterministic workflow artifacts pinned to published Core 0.5-compatible common/I/O/spot tools 0.2.2 and segmentation tools 0.3.2.
  The exporter retains these explicit release pins independently of the example source checkout’s package versions.
- Fish Analysis gives its marker branches distinct internal node IDs and runs in parallel using the locked published BioImageFlow runtime, whose worker-thread scope propagation preserves nested result identities and Node Data views. Its summary groups mapped overlap rows by their immediate parent image row index.
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
Desktop startup adopts an existing singleton or atomically registers one setup-needed default recipe when the Napari registry is pristine; creating that declaration does not acquire an environment manager, probe, provision or launch.
Reconciliation acquires no environment manager when there are no nonterminal operations; interrupted operations retain their existing runtime recovery.
The default card offers explicit Setup through the existing retry operation with the same UUID; Refresh is unavailable before installation.
A never-installed setup-needed declaration can be forgotten through metadata and reference cleanup without removing or changing installed-environment files, and its registry revision prevents recreation on the next startup.
Phase C implements UUID-keyed lazy launcher processes and locks, frozen registered-environment argv dispatch, public Wetlands generation-owned spawning for recipe-created managed entries with a narrow persisted-interpreter fallback for adopted legacy Wetlands 1 workspaces, per-environment napari settings files, optional explicit reader dispatch, Qt-completion acknowledgements, typed open failures, unknown-outcome no-replay semantics, and attributed lifecycle status/events.
Its dedicated environment launch route starts an empty viewer without dispatching `viewer.open([])`.
The managed installer backend implements strict default, legacy-smoke, and explicit advanced recipes, PyPI-only requested distribution validation, immutable create/copy generations, durable public-Wetlands operation progress/cancellation/restart reconciliation, metadata-only validation probes, and ownership-proven removal coordinated with per-environment launcher shutdown and an idempotent local-reference cleanup seam.
The legacy no-ID open/status/shutdown contract remains as a temporary desktop compatibility path; explicit launch IDs never provision or mutate registered environments.
Its Phase C backend implements immutable public result identities, retained per-result viewer metadata lookup, package-only compatibility resolution, archive/readiness reports without implicit installation, and a separate CAS favorite store integrated with environment forget and workflow identity move/delete recovery.
Portable viewing manifests can also be submitted directly to the desktop-only passive readiness endpoint before any result artifact exists; it shares the resolver's installed-distribution and PEP 440 candidate evaluator, preserves output identities and unknowns, and groups identical normalized requirements without implicitly unioning different outputs.
Resolve responses return the exact server-derived persistent output-preference key, including durable workspace identity, rather than requiring clients to infer it from existing favorites.
Nested favorite finalization derives its destination from the stored snapshot owner and remaps only after the accepted parent snapshot or current root draft embeds the exact child graph; unsaved roots cannot create durable favorites.
The frontend Image Viewers settings UI manages registered and managed environments, defaults, ordered filename rules, lifecycle operations, and empty launches.
Workflow import and explicit saved Open present persistent output-specific missing/unknown viewing guidance outside Settings, without blocking Run or installing viewers.
Saved-workflow viewing inspection uses the normal request-local graph compiler, workflow-owned source capture and selected tool store; it never plans or executes a workflow to obtain viewer declarations.
Construction and missing-source diagnostics remain unknown metadata, including an empty diagnostic workflow returned with validation errors, and are never counted as evidence of missing viewer packages.
Unknown metadata remains visible with tool/source diagnostics; environment setup actions are offered only for known viewer requirement groups.
Pending-only viewing checks stay silent; successful covered reports never mount a transient guidance banner, while completed warnings and failures remain dismissible.
Guidance, readiness errors and setup suggestions belong to the accepted registered root canvas, its registration token, local/server workflow identity and current request intent; switching, closing or replacing that owner invalidates delayed responses and queued transfers.
Settings receives a copied requirement set through an explicit action; automatic prefills update only an untouched, idle creation form, and older setup completions cannot consume a newer owner's groups.
A constrained napari set displays its original version range and requires an explicit exact release in the advanced recipe; the default preset is not assumed compatible, and installed inventory remains the compatibility authority.
The per-output readiness report is not shown in Settings. Forgetting an adopted legacy installation suppresses its automatic startup adoption; external entries can be located again, and package changes are checked through inventory refresh rather than executable-file identity.
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
