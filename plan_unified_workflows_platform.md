# BioImageFlow Unified Workflows: Platform Implementation Session

## How To Use This Plan

This is the second of two implementation plans.

Run it in `/Users/amasson/Travail/bioimageflow-platform` only after `plan_unified_workflows_bioimageflow.md` has been completed and committed in `/Users/amasson/Travail/bioimageflow`.

At the start of the session, record the finished library commit and read its final public API, recursive wire format, and validation contract directly from the library source and documentation.

Do not reintroduce an adapter in either repository if the platform exposes an integration mismatch.

Fix the platform to consume the new library contract directly.

The platform repository may have unrelated local changes when the session starts.

Preserve them and use one worktree under `.worktrees/unified-workflows-platform` if isolation is useful.

When creating a worktree, recreate the ignored source links exactly as required by `AGENTS.md`, and point its `bioimageflow` link at the completed library checkout.

Before running the prescribed link command, verify that the platform primary checkout's `bioimageflow` link resolves to the completed library commit recorded in the handoff.

Start implementation only after the library handoff identifies committed normative API/wire/archive documentation and golden fixtures and the linked checkout passes the handoff smoke tests.

If the platform needs behavior, fields, identifiers, or source-transfer semantics absent from that contract, stop the platform session and return to a focused library change and new library commit first.

Do not infer a private contract, inspect library internals from platform code, or add a translator workaround for a missing library capability.

The platform session stops only after the final clean-tree and cross-repository gates pass, all task commits are integrated as intended, and the paired library/platform commit hashes are reported; it must not modify the completed library checkout in place.

## Product Decision

The platform edits, stores, validates, nests, and executes one recursive workflow document.

A root canvas and a nested canvas edit the same `GraphState` shape and the same workflow interface model.

A workflow used inside another workflow is represented by a discriminated workflow node, not by a sentinel tool or a second graph/config language.

Python-authored and JSON-authored workflows materialize to the same recursive library `Workflow` and the same platform `GraphState` semantics.

There is no backward-compatibility requirement.

Do not add old-document migration, deprecated fields, compatibility aliases, fallback parsers, legacy API routes, warning periods, dual writes, or tolerant sentinel detection.

Replace all checked-in fixtures and tests with the clean new schema.

Temporary coexistence between implementation commits is allowed only inside the branch.

The final platform tree must look as if it had been designed for recursive workflows from the beginning.

## Required Final Platform Model

### Graph And Node Types

Replace the permissive single `NodeState` model with a discriminated union.

The conceptual shape is:

```python
class ToolNodeState(BaseModel):
    type: Literal["tool"]
    id: str
    name: str
    tool_name: str
    parameters: dict[str, Any]
    # normal layout, resources, templates, enabled, and collapsed fields


class WorkflowNodeState(BaseModel):
    type: Literal["workflow"]
    id: str
    name: str
    workflow: GraphState
    bindings: dict[str, SerializedConstant]
    source: WorkspaceWorkflowSource | None
    # normal layout, enabled, and collapsed fields


NodeState = Annotated[
    ToolNodeState | WorkflowNodeState,
    Discriminator("type"),
]


class GraphState(BaseModel):
    schema_version: Literal[1]
    name: str
    display_name: str
    nodes: list[NodeState]
    edges: list[Edge]
    interface: WorkflowInterface
    config: WorkflowConfig
```

The root workspace path remains the workspace artifact identity and is not overloaded into `GraphState.name`.

`GraphState.display_name` is the sole editable workflow display label; root list/detail responses project it rather than storing a competing copy in workspace metadata.

Workspace metadata is limited to workspace concerns such as description, storage policy, identity generation, and authoring provenance.

Moving a workspace artifact changes its path identity and source-provenance references but does not silently rewrite the self-contained definition name; duplication assigns a new definition name explicitly as part of the atomic duplicate operation.

`GraphState.name`, `display_name`, interface, and definition configuration are part of the self-contained workflow definition at every depth; a nested graph must not depend on its parent node or workspace record to reconstruct the library workflow.

The parent workflow-node `id` maps to the library node's structural `name`.

The parent workflow-node `name` is platform-owned canvas display metadata: translation to the library does not use it as identity, and import from a standalone library graph initializes it deterministically from the contained workflow's `display_name` or structural name when no platform document supplies it.

Do not silently substitute a parent node ID for missing child definition metadata during translation.

Implement the recursive Pydantic model with forward references followed by an explicit model rebuild, `extra="forbid"` on every wire model, and explicit discriminator mappings for both nodes and edges.

Add a backend OpenAPI schema test that resolves the recursive `$ref` graph and asserts that generated TypeScript exposes `ToolNodeState | WorkflowNodeState` and the edge union without `any`, an optional-child-field fallback, or a lost discriminator.

`WorkflowNodeState.workflow.interface` is the only source of truth for the child node's pins.

Do not copy the child interface onto its parent node.

Use immutable interface port IDs for edge handles and binding keys, and editable names for labels.

`WorkflowNodeState.bindings` stores only the library's typed serialized constant envelopes keyed by child-input port ID; incoming edges are represented only in the parent graph's edge list, and the two forms are mutually exclusive for one input.

Do not leave `bindings` as an unconstrained `dict[str, Any]` in the implemented schema: reject unknown port IDs, column-reference values, and malformed constant envelopes during model/service validation.

### Interface And Edges

Mirror the finished library contract exactly instead of inventing a platform-only mapping language.

The platform model must support:

- field inputs that accept constants or column-reference edges;
- DataFrame inputs that target positional DataFrame-tool ports;
- one interface input targeting one or more compatible internal ports;
- published column outputs;
- stable port IDs across display-name edits;
- interface defaults and internal tool defaults according to the library's precedence rules;
- explicit DataFrame edges capable of targeting either a tool positional index or a workflow DataFrame input ID.

Use the library's explicit `column` and `dataframe` edge variants.

For a workflow-node endpoint, `target_input` and `source_output` are stable interface port IDs rather than editable labels.

For a tool-node endpoint, they remain tool field/output names, while a DataFrame tool target uses `target_position`.

Do not encode workflow identity through `tool_name`.

Do not infer node type by inspecting optional child fields.

Frontend handle identity must be typed and collision-free.

Use a single encoder/decoder for handles such as `out:column:<tool-output-or-port-id>`, `out:dataframe`, `in:field:<tool-field-or-port-id>`, `in:dataframe:<port-id>`, and `in:position:<index>`; do not concatenate editable labels or infer endpoint kind from a bare string.

Connection, reconnection, deletion, clipboard, grouping, and schema-resolution code must all use that endpoint codec.

New platform-created interface IDs are opaque UUIDs generated once at the mutation boundary and then retained; grouping creates one independent input per incoming edge by default, while an explicit interface edit may add further compatible targets to an existing input for fan-out.

Deleting one target from a fan-out input does not delete the port unless it was the final target; deleting or changing the kind of the port follows the connected-port confirmation rules.

### Source Provenance

Dragging a saved workflow onto a canvas embeds an executable snapshot and records optional provenance:

```json
{
  "source": {
    "kind": "workspace",
    "workflow_id": "segmentation/nuclei",
    "artifact_hash": "sha256:..."
  }
}
```

The embedded workflow is execution authority.

Source provenance is used only to open the source, detect a changed saved artifact, update explicitly, and enforce containment rules.

`WorkspaceWorkflowSource` contains exactly the workspace workflow ID and the source artifact hash.

Python authoring provenance belongs to the saved root workflow document, not to `WorkflowNodeState.source`; dragging a Python-authored saved workflow still produces ordinary workspace provenance on the embedded node.

Required behavior:

- editing a nested instance changes only the embedded snapshot;
- changing or deleting its saved source does not silently mutate or break the parent;
- source changes may produce an "Update available" state;
- "Update from source" validates and replaces the embedded snapshot atomically;
- retained interface port IDs preserve compatible parent edges and bindings;
- removing connected ports requires confirmation and removes the affected parent state only after confirmation;
- workflow/folder moves update stored source IDs through the existing atomic move path;
- source metadata does not participate in execution or cache identity beyond the embedded content it identifies.

A retained ID is compatible only when its input/output direction, field-versus-DataFrame kind, and completed-library schema compatibility still accept the existing edge or constant; same ID with an incompatible contract is reported in the destructive preview rather than trusted blindly.

Define the artifact hash as a deterministic digest of the canonical saved recursive graph plus the recursively required workflow-local tool-source bundle.

Exclude workspace path, timestamps, revisions, runtime storage/output state, and source-provenance labels from that digest.

Canonical hashing must recursively elide every workflow-node `source` object and root authoring-provenance field before encoding the graph; otherwise moving a source or detaching provenance would contradict the rule that provenance does not affect artifact or cache identity.

Include layout because it is part of the embedded editable snapshot; canonicalize JSON before hashing so update availability does not fluctuate because of key order.

Containment validation uses workspace source identities only as a mutation-time dependency graph; execution never dereferences them.

On embed, paste, source update, save, import, duplicate, and move, reject a direct or transitive provenance dependency back to the destination workflow and report the complete source/node path.

Validate against the exact saved source artifact/hash captured for the mutation, not against a later reread.

### Python Authoring Sources

A Python `workflow.py` is an optional trusted authoring source, not a second persisted or executable workflow model.

The backend must provide an explicit trusted "build from Python source" operation for a configured local module or file; the GUI exposes it as "Build from Python source" or "Rebuild from Python source" in trusted desktop mode only.

Do not accept an arbitrary filesystem path or module string from an ordinary request.

The backend resolves an authoring-source identifier through a configured allowlist or a `workflow.py` under the addressed workflow directory, rejects symlink/path escapes, and disables the operation in webapp mode unless the existing unsafe-feature gate is explicitly enabled.

That action must:

1. Execute the module's exact `build_workflow` factory once through the completed library API.
2. Require a returned standalone `Workflow` and surface factory/import failures without changing the saved document.
3. Translate the materialized workflow into the canonical editable `GraphState`, assigning deterministic default layout and GUI state when the Python definition contains none.
4. Validate and save the replacement graph atomically only after user confirmation when graphical or draft edits would be overwritten.
5. Record optional authoring provenance containing the module/file identity, exact factory symbol, and source hash.

Rebuild uses the same preview/apply CAS protocol as source refresh, including a summary of overwritten graph/interface state and owned custom-tool changes.

The authoring source hash covers a canonical manifest of the resolved entry module and all allowlisted local Python files under its configured authoring root, excluding caches, generated runtime state, and the materialized `workflow.json`; do not claim change detection from hashing only the entry file while ignoring imported local helpers.

Preview must capture an immutable copy of that manifest, and materialization, recursive runtime-source collection, and the recorded authoring hash must all use those exact captured bytes.

Apply must conflict without saving if the live allowlisted manifest no longer has the captured hash; rebuilding after an entry-file or local-helper edit must use a fresh import context and must not reuse module state from an earlier build.

Run, nest, copy, export, and reopen operations use the materialized graph and must never import the Python source.

Do not execute arbitrary uploaded or downloaded Python as part of ordinary workflow import.

A workflow dragged from the saved-workflow panel still records workspace snapshot provenance; its saved document may separately remember that it was authored from Python.

### Workflow-Local Tool Ownership

Embedding only a graph is not a complete snapshot when the source workflow uses files from its own `tools/` directory.

The destination root workflow must own immutable copies of all recursively required workflow-local tool sources before an embedded workflow can be considered independent of its source.

Store embedded copies in a destination-owned, content-addressed dependency area distinct from the editable root `tools/` directory, rewrite the materialized tool references to collision-safe module identities, and load them through the normal tool resolver.

Two copies with identical content may deduplicate; two same-named tools with different content must coexist without registry shadowing.

Embed, paste across root workflows, duplicate, import, Python materialization, and source update must stage the graph and required source files together and publish them atomically.

A failed copy/import/validation leaves neither a graph mutation nor orphan dependency files.

Source deletion or later edits to its custom tools must not affect the embedded instance.

Garbage-collect an embedded source only after no saved graph, root draft, retained nested snapshot, clipboard/import transaction, or in-flight execution snapshot owned by that root can refer to it.

Installed package references remain versioned dependencies rather than copied source, and required package detection must recurse through every embedded workflow.

Library archive export collects the destination-owned embedded sources once at archive root and import restores and rewrites them without creating a source registry inside each nested workflow.

Python materialization and library archive import must ingest the completed library's documented graph-plus-source result as one unit.

The platform stages that returned source table into destination-owned content-addressed storage and rewrites module IDs through the documented library/platform translation boundary; it must not rediscover required runtime sources by introspecting returned tool classes or by treating the broader Python authoring-source hash manifest as the runtime dependency bundle.

Conversely, library archive export must be built from the accepted graph snapshot and exactly its referenced destination-owned source entries, then passed through the library's documented archive API.

## Backend Implementation

### Models And OpenAPI

- Replace graph node, interface, and edge Pydantic models with the final discriminated recursive schema.
- Rename request, response, operation, snapshot, and error models around workflows and nested workflows.
- Keep the existing nested-editor snapshot behavior where it remains sound, but use workflow terminology and the canonical child `GraphState` document.
- Regenerate OpenAPI-derived frontend types after the backend schema stabilizes.
- Do not retain compatibility aliases in generated or handwritten TypeScript.

### Translation And Library Boundary

`graph_state_to_lib_dict` must recursively translate every `GraphState` through the same code path.

Delete the special nested config generation path.

The final translator must:

- emit one recursive library workflow dictionary;
- map tool nodes normally;
- map workflow nodes to `type: "workflow"` with a nested workflow dictionary;
- map the canonical interface directly;
- preserve stable edge IDs and interface port IDs;
- represent DataFrame edges without rejecting nested positional inputs;
- resolve packages and custom tools recursively;
- pass the completed library's recursive validation errors through with exact node paths;
- never synthesize a restricted interface schema with a fallback string type.

`lib_dict_to_graph_state` must perform the inverse for all execution-relevant fields in the new format only; platform-only position, collapsed state, and other GUI metadata remain owned by `GraphState` and are not expected to appear in a standalone library export.

Definition configuration round-trips at every depth, while execution resolves storage, engine, output view, and environment policy from the root workspace/run context without mutating the accepted graph; nested root-only values are preserved as metadata and ignored by the library compiler exactly as specified by the finished library contract.

Remove class-based read-only child handling because Python factories materialize an ordinary editable workflow snapshot before reaching the platform.

Execution, planning, cache-clear, output-schema, and validation callers must all translate the same immutable accepted `GraphState` snapshot and invoke the library's recursive compiler.

Remove platform-side graph pruning or flattening that reconstructs a partial `GraphState`: selected Run sends target structural IDs, and selecting a `WorkflowNodeState` targets that workflow boundary so the library schedules all enabled internal terminal/completion dependencies.

No platform service may traverse only root `nodes` when collecting tool packages, missing tools, custom sources, output schemas, status paths, or cache-clear targets.

### Persistence, Drafts, And Export

- Replace the current persisted `graph`/derived `workflow`/duplicated `gui` triple with one workspace document carrying its own `platform_document_version`, the canonical recursive `GraphState`, workspace metadata, optional root Python-authoring provenance, and references to the destination-owned tool-source bundle; do not conflate the envelope version with the library-compatible `GraphState.schema_version`.
- Store layout, collapsed state, resource overrides, and output templates once in the recursive `GraphState`; do not persist a second GUI projection.
- Generate the library dictionary in memory from the exact accepted graph snapshot for validation, execution, and library-archive export; do not persist a derived library section in `workflow.json`.
- Compute the saved-artifact hash from the canonical definition and owned source bundle described above, and use that same hash for draft baselines, source provenance, update preconditions, and exact-snapshot Save/Run.
- Carry the interface inside every root or nested draft `GraphState`.
- Preserve revision CAS, identity-generation, saved-artifact hash, exact-snapshot Save/Run, and nested private-snapshot semantics.
- Keep the two export intentions explicit: portable execution export/import uses only the library's recursive archive format, while any workspace-document backup format carries the canonical platform document and GUI state but is not accepted as a library workflow.
- Collect required packages and custom workflow-local tools recursively.
- Replace all checked-in saved-workflow fixtures instead of teaching the store to load old documents.

There is no fallback that reconstructs `GraphState` from an obsolete persisted library section and no load-order choice between competing graph authorities.

### Validation And Containment

The backend is authoritative for:

- recursive library validation;
- interface target/source integrity;
- stable interface ID uniqueness;
- parent binding and edge compatibility;
- field versus DataFrame input kinds;
- exact scoped validation errors;
- direct and indirect workspace containment cycles through source provenance;
- update-from-source preconditions;
- no graph mutation during execution.

Frontend containment checks remain useful for immediate feedback but are not sufficient authority.

Implement source refresh as a revisioned semantic mutation rather than a frontend read/replace sequence.

The preview operation captures the parent draft revision, destination identity generation, workflow-node path, current embedded source hash, exact saved source artifact hash, removed/incompatible port IDs, affected bindings/edges, and required local-tool changes.

Apply accepts that exact preview token plus explicit confirmation of the listed destructive effects, reacquires the normal workflow/execution mutation gates, rechecks every captured value, stages owned tool sources, replaces the embedded graph, and commits one parent undo/revision transition atomically.

Any mismatch returns a conflict and changes nothing.

An open private editor snapshot for the target workflow node or any descendant makes refresh, detach, or replacement fail until that editor is explicitly applied or discarded; do not strand a durable nested session against a silently replaced baseline.

Workspace moves update provenance IDs in saved documents, accepted root drafts, and retained nested snapshots through the existing journaled all-or-nothing identity move, without changing embedded content or artifact hashes.

### Services And Agents

Update semantic workflow-draft operations and agent tools so they manipulate the canonical interface directly.

Required operations include:

- expose/update/delete workflow input;
- expose/update/delete workflow output;
- create/delete workflow node;
- connect column edge to workflow field input;
- connect DataFrame edge to workflow DataFrame input;
- address nested scopes through workflow-node paths;
- inspect source provenance and explicit source-update availability;
- preview/apply source update with revision/hash preconditions;
- detach workspace provenance without changing embedded content;
- build/rebuild a root graph from trusted Python authoring source with the same preview/apply and revision semantics.

Use stable interface port IDs for mutation identity.

Names are editable presentation fields, not handles.

Operation payloads use the discriminated node/edge models and a list of workflow-node IDs as the scope path.

They never accept a slash-parsed display path, editable port name as mutation identity, or an arbitrary raw nested graph replacement when a semantic interface/source operation is required.

Update `docs/agents` and MCP/API reference material accordingly.

## Frontend Implementation

### Canvas And Serialization

- Render `ToolNodeState` and `WorkflowNodeState` from their explicit discriminator.
- Replace sentinel detection and permissive field probing everywhere.
- Derive workflow-node pins solely from `node.workflow.interface`.
- Serialize root and nested canvases through one graph-document function.
- Update clipboard, copy/paste, cross-workflow reconciliation, undo/redo, graph synchronization, status projection, Data Table, logger filtering, and output inspection for recursive workflow nodes.
- Preserve the complete embedded workflow when copying or pasting a workflow node.
- Preserve interface port IDs within the copied child while generating new parent node and edge IDs where required.

### Grouping And Drag/Drop

Replace the selected-node grouping utility with "Group into workflow" behavior:

1. Move the selected nodes and internal edges into an anonymous embedded `GraphState`.
2. Convert every incoming column edge into an independent field workflow input by default.
3. Convert every incoming DataFrame edge into an independent DataFrame workflow input.
4. Convert outgoing edges into workflow outputs.
5. Rewire parent edges to stable interface port IDs.
6. Preserve zero-interface selections.
7. Preserve every internal branch, including unpublished and detached terminal branches.
8. Apply the operation as one undo transition.

Dragging a saved workflow row embeds its exact saved graph snapshot plus source ID and artifact hash.

The frontend may reject obvious cycles immediately, but the backend must revalidate.

### Editing Sessions

Root and nested tabs use the same canvas component and graph/interface editing behavior.

Retain private durable nested snapshots and explicit parent apply because those are persistence-context semantics, not a different workflow concept.

Rename stores, components, composables, events, panel IDs, test fixtures, CSS classes, and variables to workflow or nested-workflow terminology.

The final naming should include forms such as:

- `nestedWorkflowSessions`;
- `NestedWorkflowEditorPanel` or a generic `WorkflowEditorPanel`;
- `openNestedWorkflow` where location matters;
- `applyNestedWorkflowDraft` where parent application matters;
- `isWorkflowNode` for node-type checks.

Do not call a nested canvas a different kind of workflow.

### Interface UX

Replace the current publish language with workflow-interface language:

- "Expose as workflow input";
- "Expose as workflow output";
- "Workflow input name";
- "Workflow output name".

Renaming changes only the port name and keeps its immutable ID.

Renaming an output preserves connected column edges but intentionally changes that column's label in the workflow's assembled whole-DataFrame result; show this consequence when a DataFrame edge consumes the workflow node.

Unexposing a connected port requires confirmation and atomically removes its parent bindings/edges.

Workflow nodes retain the visually distinct thick border and double-click-to-open behavior.

Context-menu labels become:

- "Group into workflow" for a selection;
- "Open workflow" for a workflow node.

Add source actions where provenance exists:

- "Open source workflow";
- "Update from source";
- "Detach from source" if source provenance needs to be intentionally removed.

## Documentation And Specifications

Rewrite `platform_specs_v2.md` as the implemented clean specification rather than appending a migration section.

The final normative documentation must describe:

- one recursive workflow concept;
- root and nested persistence contexts;
- workflow interfaces and stable port IDs;
- tool nodes versus workflow nodes;
- grouping and saved-workflow embedding;
- snapshot provenance and explicit source updates;
- recursive validation and cycle rejection;
- flat execution, scoped paths, per-internal-node caching, and aggregate node status;
- Python `build_workflow` factories as an authoring source that materializes the same workflow model.

Update root, backend, and frontend READMEs plus agent documentation and API references.

Do not retain migration notes, removed schema examples, old screenshots, old endpoint terminology, or historical tutorial sections in current documentation.

## Implementation Sequence

### Step 0: Baseline And Library Contract

- Read both plans and the completed library implementation/docs.
- Record the library base and integrated commits, normative documentation/fixture paths, and verification results in the implementation handoff or first commit message.
- Inspect and preserve unrelated platform changes.
- Create one worktree if useful and recreate required source links.
- Run focused baseline commands to distinguish expected library-integration failures from unrelated failures.
- Build an exact tracked-file removal/rename inventory before editing.
- Run a platform-side contract smoke test against the linked library: load and canonical-round-trip the handoff's recursive graph fixture, import/export its custom-source archive fixture, invoke a Python `build_workflow` exactly once, and inspect nested validation/plan identifiers using only documented public APIs.
- Stop before product edits if the linked checkout hash differs, a golden fixture fails, or platform requirements would require an undocumented library field or private API.

### Step 1: Backend Schema And Recursive Translation

Add failing backend tests first for:

- strict recursive Pydantic parsing and OpenAPI discriminator/`$ref` generation;
- root/nested schema identity;
- stable interface IDs;
- recursive library translation and inverse translation;
- nested field and DataFrame inputs;
- zero-output workflow nodes;
- scoped library validation errors;
- canonical single-authority persistence with no derived library/GUI sections;
- recursive draft, save, selected workflow-node run, cache-clear, import, and export behavior without platform-side graph pruning.

Implement the new models, strict OpenAPI schema, translator, canonical persistence, validation, workflow-store, execution, draft, snapshot, import, and export paths.

Delete old backend tests as their replacements become green.

Run backend Ruff and deterministic pytest before committing.

This commit must leave the backend and generated OpenAPI schema green against the pinned library contract.

The branch may have a recorded frontend compile failure caused solely by the deliberate API cut, but no backend test or generated-schema assertion changed in this step may be left red; do not present this commit as independently mergeable.

Suggested first commit: `Adopt the recursive workflow backend model`.

The frontend may be temporarily broken after this commit inside the feature branch.

### Step 2: Backend Provenance, Sources, And Semantic Operations

Add failing backend tests first for:

- recursive package and installed-tool requirement collection;
- backend-authoritative direct and transitive containment rejection on every mutation path;
- deterministic snapshot source hashes and update availability;
- source-refresh preview/apply conflicts, incompatible/removed-port confirmation, and rejection while a target/descendant private editor is open;
- destination-owned recursive local-tool snapshotting, rollback, deletion independence, garbage-collection safety, and same-class-name source collisions;
- move, duplicate, import, cross-root paste, retained-snapshot, and draft provenance/tool-bundle behavior;
- explicit trusted Python-factory materialization, atomic failure, and no factory execution during run or nesting;
- rebuild after entry-file and imported-local-helper changes, coherent graph/runtime-source/provenance hashes from the captured manifest, stale-import isolation, and a conflict when the manifest changes between preview and apply;
- path/allowlist and deployment-mode enforcement for Python materialization;
- stable-ID interface and nested-scope semantic/agent operations.

Implement the destination-owned dependency bundle, source provenance/update services, containment checks, Python materialization, move/recovery integration, and typed semantic/API/agent operations.

Run backend Ruff and deterministic pytest again before committing.

This commit must also pass focused graph-plus-source archive interoperability tests against the library handoff fixtures; Python materialization, archive import, and saved-workflow embedding must use the same destination-owned source-ingestion path.

Suggested second commit: `Add snapshot provenance and workflow sources`.

### Step 3: Frontend Schema, Canvas, And Sessions

Regenerate API types from the new OpenAPI schema without appending compatibility aliases.

Add or replace frontend unit tests for:

- explicit workflow-node rendering;
- canonical graph serialization;
- typed handle encoding/decoding and edge reconnection for every endpoint variant;
- interface editing by stable ID;
- fan-out target editing and final-target deletion behavior;
- grouping with column and DataFrame boundaries;
- zero-interface and detached branches;
- saved workflow drag/drop and source provenance;
- nested tab open/edit/save/discard/conflict behavior;
- clipboard and cross-workflow paste;
- source update reconciliation;
- source update conflict/destructive-effect confirmation and open-nested-editor gating;
- explicit Python-source rebuild confirmation and error handling if that action is exposed in the GUI;
- deletion, move, lifecycle, execution lock, status, logs, and Data Table behavior.

Rename the complete frontend surface and remove old detection helpers.

Run lint, type-check, and unit tests before committing.

At this boundary, regenerate types twice, require the second generation to be clean, and restore a green backend/frontend compile and deterministic unit-test state before proceeding to E2E cleanup.

Suggested third commit: `Adopt recursive workflows in the editor`.

### Step 4: End-To-End Behavior, Docs, And Removal

Replace E2E fixtures and scenarios with the new schema.

Cover at least:

- grouping selected tools into a workflow;
- opening and editing the nested workflow;
- exposing and renaming input/output ports without breaking parent edges;
- nesting a saved workflow snapshot;
- nested DataFrame input execution;
- source update behavior;
- direct and indirect containment rejection;
- recursive execution progress and cache status;
- aggregate workflow-node failure and cancellation projection, with detached internal failures blocking downstream consumers and retaining the failing scoped path;
- copy/paste and export/import of nested workflows.

Rewrite specifications and all current documentation.

Delete old backend/frontend files and tests rather than retaining renamed wrappers around the removed architecture.

After implementation is complete, remove `plan_unified_workflows_bioimageflow.md` and `plan_unified_workflows_platform.md` in the final cleanup commit because they are migration-time plans and contain historical terminology that must not remain in the clean final tree.

Run all required platform validation before the final commit.

Suggested final commit: `Remove the legacy workflow composition model`.

## Mandatory Removal And Rename Inventory

The final tracked platform tree must not contain:

- sentinel workflow tool names;
- duplicated child interfaces on parent nodes;
- old child graph field names;
- old readonly class-based child state;
- special nested config translators;
- old published-interface models or fields;
- permissive node-type inference from optional fields;
- frontend stores, components, functions, events, tests, CSS classes, or fixtures named after the removed concept;
- backend services, models, tests, comments, error codes, or docstrings named after the removed concept;
- old context-menu and panel labels;
- old specification, README, agent-documentation, or API-reference terminology;
- compatibility aliases in generated API types;
- these two completed implementation-plan files.

The concrete forbidden schema/terminology set includes `SubWorkflow`, `subworkflow`, `sub_workflow`, `sub-workflow`, `sub workflow`, `__sub_workflow__`, `published_inputs`, `published_outputs`, `sub_workflow_readonly_reason`, the old `sub_workflow` child field, and every old library composite-config key from the library handoff inventory.

Use `git grep` for case, hyphen, underscore, and space variants of the removed terminology and inspect every match.

At minimum, search tracked handwritten and generated files case-insensitively for the concrete forbidden set above and every obsolete nested-config key identified in Step 0.

Add strict schema/API tests using generic unknown discriminators, fields, routes, operations, and persisted sections so permissive parsing cannot silently drop unsupported data.

Do not retain obsolete fixtures or literal old records solely as rejection tests; the final forbidden-term search and strict generic tests together are the clean-tree gate.

Verify the generated OpenAPI document, generated TypeScript, snapshots, fixtures, persisted sample workspaces, agent schemas, route tables, and built frontend strings; source-level renaming alone does not satisfy this gate.

The final tracked tree should have no matches.

Do not modify or delete unrelated untracked user files merely because a filesystem-wide search finds historical text in them.

Historical Git commits are outside this requirement.

## Verification

Run focused tests throughout, then run the repository's required checks.

Backend:

```bash
cd backend
uv run --frozen ruff check .
uv run --frozen pytest -m "not common_tools"
uv run --frozen pytest tests/test_logging_config.py tests/test_ws/test_handler.py::test_publish_without_loop_drops_silently tests/test_ws/test_handler.py::test_publish_logs_future_exceptions tests/test_ws/test_logging_bridge.py::test_attach_to_bioimageflow_logger -q
```

Frontend:

```bash
cd frontend
bun run generate-types
bun run lint
bun run type-check
bun run test:unit
bun run test:e2e -- --project=chromium
```

Run `bun run generate-types` against the backend from the same platform commit, review the generated diff, and assert a second generation is clean before the final frontend verification.

Run Firefox or external common-tools certification only if the changed behavior specifically requires those optional lanes or the normal checks expose a relevant failure.

## Completion Criteria

The platform session is complete only when:

- the backend and frontend consume the completed library contract directly;
- root and nested editors use one graph/interface model;
- nested DataFrame inputs work without a special translation language;
- saved workflow reuse is snapshot-based and source updates are explicit;
- backend containment validation is authoritative;
- all current specs and documentation describe only the clean unified architecture;
- every mandatory removal and rename is complete;
- both implementation plans have been removed from the final tree;
- all required backend, frontend, and Chromium checks pass;
- only task changes are committed in the four coherent implementation commits above;
- every commit satisfies its stated subsystem gate and the temporary backend/frontend cut is closed in Step 3;
- the final integrated library and platform commits, contract fixture paths, and cross-repository interoperability results are reported together.
