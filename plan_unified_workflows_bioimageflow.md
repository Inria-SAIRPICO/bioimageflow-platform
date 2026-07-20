# BioImageFlow Unified Workflows: Library Implementation Session

## How To Use This Plan

This is the first of two implementation plans.

Run this plan in the BioImageFlow library repository at `/Users/amasson/Travail/bioimageflow`, not through the platform repository's `bioimageflow` symlink.

Complete and commit the library work before starting `plan_unified_workflows_platform.md` in the platform repository.

The library repository may have unrelated local changes when the session starts.

Preserve them, do not stage them, and use one worktree under `/Users/amasson/Travail/bioimageflow/.worktrees/unified-workflows` if isolation is useful.

If a library worktree is used, integrate its completed branch into the library's primary checkout before the platform session so the platform repository's required `bioimageflow` source link resolves to the finished contract; inspect and preserve unrelated primary-checkout changes before merging, and stop for user direction if they conflict.

Do not implement platform changes from this session.

The temporary cross-repository integration gap is intentional: the library must finish with a clean new contract even though the existing platform will not consume it until the second plan is executed.

Start this session only after recording the library repository base commit and the focused baseline results.

If unrelated changes prevent an isolated branch/worktree or make the required final merge ambiguous, stop before editing and ask for direction.

The session stops after the completed library branch is integrated into the primary library checkout, all library gates pass there, and the handoff described below is reported; it must not continue into opportunistic platform fixes.

## Product Decision

There is one workflow concept.

A workflow is represented by `Workflow` at every nesting level.

Calling a `Workflow` creates a `WorkflowNode` in its parent.

"Nested workflow" describes where a workflow is used; it is not a second definition type or API family.

Python workflow modules export a `build_workflow` factory that returns a fresh `Workflow`.

JSON and Python are definition sources that materialize the same `Workflow` object and the same recursive wire format.

There is no backward-compatibility requirement because the library has no users yet.

Do not add deprecated aliases, legacy loaders, schema migrations, warning periods, compatibility flags, or dual serialization.

Temporary coexistence of old and new code is allowed between implementation commits on the branch only.

The final library tree and public package must contain no old composite-workflow type, module, config language, registry path, tests, examples, or documentation.

## Required Final Public API

### Programmatic Definition

The intended authoring form is:

```python
from bioimageflow import Workflow


def build_workflow(
    *,
    storage_path: str = "./bif_data",
    engine: str = "wetlands",
    wetlands_config: dict | None = None,
) -> Workflow:
    workflow = Workflow(
        name="segment_and_measure",
        display_name="Segment and Measure",
        storage_path=storage_path,
        engine=engine,
        wetlands_config=wetlands_config,
    )

    with workflow:
        image = workflow.input("image", ImagePath, id="input-image")
        diameter = workflow.input(
            "diameter",
            float,
            default=30.0,
            id="input-diameter",
        )

        masks = Segment()(input_image=image, diameter=diameter, name="segment")
        measurements = Measure()(
            image=image,
            mask=masks["mask"],
            name="measure",
        )

        workflow.output("mask", masks["mask"], id="output-mask")
        workflow.output("area", measurements["area"], id="output-area")

    return workflow
```

The required public surface is:

- `Workflow(name="workflow", display_name=None, ...)` carries definition metadata in addition to root execution configuration; `display_name` defaults to `name`, while reusable factories set both deliberately.
- `Workflow.input(name, annotation=None, *, kind="field", default=MISSING, id=None)` returns a symbolic workflow-input reference owned by that workflow.
- `Workflow.output(name, source, *, id=None)` publishes an internal node column.
- An editor-oriented method may expose an existing node field as a workflow input, but it must create the same canonical interface model as `Workflow.input`.
- `Workflow.__call__(*, name=None, **bindings)` returns a `WorkflowNode` and registers it with the active parent workflow.
- `Workflow.compute(..., inputs={...})` supplies root workflow inputs using the same validation and binding semantics as a nested invocation.
- `Workflow.from_python(path_or_module)` explicitly executes the trusted module's exact `build_workflow` symbol once and requires it to return a `Workflow`.
- `Workflow.from_dict`, `Workflow.load`, `Workflow.to_dict`, and `Workflow.export` read and write only the new recursive format.
- `WorkflowNode` is exported from `bioimageflow` and is the only public composite node type.

The public Python API resolves workflow inputs and outputs by their unique names.

Invocation keyword keys and `compute(inputs=...)` mapping keys are interface names; serialization resolves them to stable IDs.

The reserved invocation keyword `name` assigns the parent node's stable structural name, so workflow interfaces must reject `name` as an input name.

Stable port IDs are wire/editor identities and remain unchanged when a display name is edited.

`WorkflowNode["mask"]` therefore resolves the output name to its stable port ID before constructing the internal column reference.

`Workflow.input(..., kind="field")` may be bound only to named processing-tool fields or named field inputs on a contained `WorkflowNode`.

`Workflow.input(..., kind="dataframe")` may be bound only as a positional input to a `DataFrameTool` or to a DataFrame input on a contained `WorkflowNode`.

Passing the same symbolic input reference to multiple compatible targets records fan-out in the interface; it does not create an executable proxy node.

Reject a symbolic input reference used outside its owning workflow, a kind/target mismatch, and a target that already has an internal data edge.

At root execution, field inputs receive ordinary values and DataFrame inputs receive complete DataFrames.

At nested invocation, field inputs receive constants or `ColumnRef` values and DataFrame inputs receive an upstream `Node`/workflow result as a whole.

While building a parent definition, either kind may instead receive a compatible symbolic input reference owned by that active parent; this records the nested workflow input as another target of the parent's interface input.

Do not introduce a second public `WorkflowDefinition` abstraction during this task.

Factories solve shared mutable definition state by returning a fresh `Workflow`; a separate immutable definition class is not required for the first clean implementation.

Do not introduce a workflow-as-tool registry or decorator in this task.

Python workflow factories are discovered by the exact `build_workflow` module convention or imported normally, while `ToolRegistry` remains exclusively about executable tools.

### Factory Contract

Every workflow-definition Python module in the repository must export the exact symbol `build_workflow`.

For this requirement, a workflow-definition module is any shipped or documented Python module whose purpose is to provide a reusable or runnable workflow, including top-level examples, reusable children below an example, and any package-owned workflow module or resource exposed to users.

Test-only helpers that merely construct an inline graph for one test are not workflow-definition modules, but tests, documentation, and launch scripts must not advertise another factory name or a module-level shared `Workflow` as the user-facing convention.

Each `build_workflow` must:

- be callable with no required arguments;
- return only a `Workflow`, never `(Workflow, Node)` or another tuple;
- create and return a fresh object on every call;
- build deterministically without executing tools or calling `compute()`;
- express runtime-varying data and ordinary parameters through `Workflow.input`, not required factory arguments;
- use stable explicit workflow, node, input-port, and output-port identifiers where the API supports them;
- define meaningful workflow outputs rather than returning a terminal node separately.

Optional factory arguments may configure root-only execution settings such as storage path, engine, or Wetlands configuration.

Definition-time arguments that structurally change the graph are allowed only when necessary and must have deterministic defaults.

They are not workflow invocation inputs.

`Workflow.from_python` is an explicit trusted-code loader, not a portable runtime dependency.

It imports a module or file, calls `build_workflow` exactly once, validates that the result is a standalone `Workflow` with no active execution, and returns the materialized definition.

For a file-based source, each call must load the entry module and its local imports in a fresh import context rather than reusing stale `sys.modules` entries from a previous materialization.

A second call after either `workflow.py` or an imported local helper changes must therefore materialize the changed definition; a configured local module used for platform authoring must first be resolved to this file-based behavior, while ordinary installed-package imports may retain normal Python import semantics.

The materialized graph and recursively collected custom-source table must come from one coherent captured set of source bytes, not from files reread at different times during loading or export.

Export serializes that materialized graph and never requires the factory to run again.

### Calling And Snapshot Semantics

Calling a workflow must:

1. Validate the supplied bindings against the workflow interface.
2. Capture a deep, independent structural snapshot of the child definition for the new `WorkflowNode`.
3. Keep bindings and enabled state independent for each invocation.
4. Register only the `WorkflowNode` in the parent workflow's immediate node map.
5. Preserve the contained workflow for inspection through `workflow_node.workflow`.
6. Avoid executing Python factories or rebuilding the graph during planning or execution.

Calling a workflow requires an active, distinct parent `Workflow`; outside a parent construction context, callers use `compute(inputs=...)` instead of creating an orphan `WorkflowNode`.

Mutating the original `Workflow` after a call must not silently mutate existing parent nodes.

The captured `workflow_node.workflow` is the editable definition of that particular invocation, so deliberate edits to it do not affect the factory result or sibling invocations.

Snapshotting copies graph structure, interface definitions, constants, output templates, enabled state, definition metadata, and tool-class references without copying cancellation flags, callbacks, run views, validation caches, execution engines, or other live runtime state.

Nested root-only configuration may round-trip as definition metadata, but the root execution context always overrides it.

## Canonical Recursive Model

### Workflow Interface

Store the public interface once on the workflow definition.

Every port has an immutable ID and editable name.

The minimum model is:

```json
{
  "interface": {
    "inputs": [
      {
        "id": "input-image",
        "name": "image",
        "kind": "field",
        "schema": {"type": "ImageFile"},
        "targets": [
          {
            "node": "segment",
            "port": {"kind": "field", "name": "input_image"}
          }
        ]
      },
      {
        "id": "input-table",
        "name": "table",
        "kind": "dataframe",
        "targets": [
          {
            "node": "merge",
            "port": {"kind": "positional", "index": 0}
          }
        ]
      }
    ],
    "outputs": [
      {
        "id": "output-mask",
        "name": "mask",
        "schema": {"type": "ImageFile"},
        "source": {"node": "segment", "column": "mask"}
      }
    ]
  }
}
```

Required invariants:

- Port IDs are unique and stable within one workflow interface.
- Port names are unique across inputs and outputs.
- A field input requires a field annotation/schema; a DataFrame input uses `kind="dataframe"` and may carry an optional whole-table schema without pretending to be a named tool field.
- A field input accepts a constant or column binding.
- A DataFrame input accepts a complete upstream DataFrame and targets a positional DataFrame-tool port.
- The interface stores serialized defaults by input port ID; invocation bindings do not mutate those defaults.
- One workflow input may target multiple mutually compatible internal ports.
- One internal port may not be targeted by multiple workflow inputs.
- An interface target on an internal tool uses the tool field name or positional index; a target on an internal `WorkflowNode` uses that child's stable input port ID.
- A workflow input target may retain a local constant or tool default as fallback, but not an internal data edge that would be silently shadowed.
- Binding resolution is explicit invocation/root input, interface default, local constant or tool default, then `missing_input`.
- Output schemas are derived and validated with the normal library type machinery; do not rebuild schemas through a restricted hard-coded type map.
- An output source belongs to the same workflow and names one real output column of an internal tool or one stable output port ID of an internal `WorkflowNode`.
- Automatically generated port IDs are opaque and collision-free; Python-authored reusable workflows use explicit IDs so refactors preserve parent connections.

### Wire Format

Require a single new schema version and one recursive node representation.

Because this is a clean first version rather than a migration target, start the new format at `schema_version: 1`:

```json
{
  "schema_version": 1,
  "name": "parent",
  "display_name": "Parent",
  "interface": {"inputs": [], "outputs": []},
  "nodes": [
    {
      "name": "segment_and_measure_1",
      "type": "workflow",
      "workflow": {
        "schema_version": 1,
        "name": "segment_and_measure",
        "display_name": "Segment and Measure",
        "interface": {"inputs": [], "outputs": []},
        "nodes": [],
        "edges": [],
        "config": {}
      },
      "bindings": {}
    }
  ],
  "edges": [],
  "config": {}
}
```

Normal tool nodes keep their existing tool identity, package identity, constants, output templates, enabled state, and edge representation where those remain clean.

Workflow `name` is the definition's stable identity, while workflow `display_name` is presentation metadata and is not used in references.

Each contained node's `name` remains its stable unique structural identity and cache-path segment; per-node canvas labels are platform GUI metadata and are not part of the standalone library graph contract.

Structural node names must be non-empty and must not contain `/`, which is reserved as the unambiguous scoped-path separator.

`WorkflowNode.bindings` contains constant bindings only, keyed by stable child-input port ID and encoded through the library's normal constant envelope.

For example, a constant invocation value is represented as `"bindings": {"input-diameter": {"kind": "constant", "value": 25.0}}` when the contained interface declares `input-diameter`.

An incoming edge and a constant binding for the same workflow input are mutually exclusive.

Use two explicit edge variants:

```json
{
  "type": "column",
  "id": "edge-image",
  "source_node": "files",
  "source_output": "path",
  "target_node": "segment_and_measure_1",
  "target_input": "input-image"
}
```

For a tool target, `target_input` is the tool field name; for a workflow target, it is the stable workflow-input port ID.

For a tool source, `source_output` is its column name; for a workflow source, it is the stable workflow-output port ID.

```json
{
  "type": "dataframe",
  "id": "edge-table",
  "source_node": "child_workflow",
  "target_node": "merge",
  "target_position": 0
}
```

A DataFrame edge targets exactly one of `target_position` for a `DataFrameTool` or `target_input` for a DataFrame-kind workflow input.

A workflow node used as a DataFrame source supplies the DataFrame assembled from its published outputs.

Replace the ambiguous positional-edge sentinel with an explicit DataFrame edge/target model capable of addressing either a tool positional index or a stable workflow DataFrame input ID.

Do not accept old unversioned dictionaries or old composite node records.

Reject unknown node/edge variants and malformed endpoint combinations rather than guessing from optional keys.

Portable archive export collects source modules recursively, deduplicates them once in the archive envelope, and lets nested tool records reference those module IDs without embedding a source registry in each child graph.

Custom-module identity is the explicit serialized module ID plus content, not the tool class name alone; recursive archives must support two nested sources that export the same class name from different module IDs without one shadowing the other.

The graph dictionary and the portable archive envelope are distinct public contracts.

The final library documentation and golden fixtures must specify the archive-level source table, how graph tool records refer to its module IDs, how file-based `Workflow.from_python` resolves imports, and which public loader/exporter APIs preserve those references.

Consumers must be able to materialize a Python factory and obtain the graph plus all recursively required custom sources through those library APIs without inspecting tool classes or crawling the factory's source tree themselves.

Update all repository fixtures and exported workflow samples to the new required shape.

## Validation And Compilation

### Recursive Validation

`Workflow.validate()` must recursively validate:

- workflow definition metadata and node-name identity uniqueness;
- interface ID and name uniqueness;
- interface target and source existence;
- interface schema compatibility;
- missing workflow-node bindings;
- illegal extra bindings;
- field versus DataFrame binding kind;
- graph cycles at every level;
- recursive object containment;
- normal tool bindings, constants, types, environments, and output mappings;
- error paths using the complete workflow-node path.

A standalone definition with required public inputs is structurally valid before values are supplied; `compute(inputs=...)` validates root values, while normal `Workflow.__call__` validates that every required child input is satisfied by an edge, constant, symbolic parent input, or fallback.

The library must reject a Python object graph that directly or indirectly contains the same `Workflow` definition on its active containment path.

Validation traverses contained definitions with an object-identity recursion stack, not a global visited set, so two independent invocations of the same source definition are valid while recursive containment is not.

`from_dict(..., validate_only=True, partial=True)` may still materialize an incomplete editor graph and return structured errors, but it must parse only the new schema and must not normalize old records.

### Flat Execution Plan

Introduce one recursive compilation phase used by validation-dependent planning, execution, cache invalidation, and `compute_steps`.

The compiler produces an internal execution representation containing flattened executable tool nodes, scoped paths, data dependencies, completion-only dependencies, workflow-boundary input providers, workflow-boundary output providers, and aggregate workflow-node metadata.

Boundary providers are compiler/runtime records, not serialized nodes, public tools, proxy nodes, or cache-owning execution steps.

Compilation must:

1. Expand every `WorkflowNode` recursively.
2. Substitute workflow input bindings at their declared internal targets.
3. Assign immutable scoped node paths without mutating stored node names.
4. Include all internal nodes, not only nodes reachable from published outputs.
5. Record all enabled terminal nodes inside each invocation as completion dependencies of that workflow boundary.
6. Resolve every published output to its internal source and assemble the boundary DataFrame through the normal index-alignment rules.
7. Route a parent column consumer through the selected published-output provider and a parent DataFrame consumer through the assembled boundary provider.
8. Ensure every consumer or explicit target of a workflow boundary waits for all of that invocation's completion dependencies, including unpublished and detached branches.
9. Use the root workflow's storage, engine, output-view, cancellation, progress, and environment-manager context.
10. Ignore nested root-only runtime configuration.
11. Preserve per-internal-node cache entries under scoped paths.
12. Derive aggregate workflow-node planning/status entries without creating an aggregate cache record.

The assembled boundary DataFrame exposes current workflow-output names as its column labels, while parent column edges continue to resolve their stable output port IDs to the underlying values.

Renaming an output therefore preserves column-edge connectivity but intentionally changes the label seen by whole-DataFrame consumers and root callers.

Data dependencies determine values and downstream cache signatures.

Completion-only dependencies enforce full-workflow execution but do not make an unrelated detached branch part of a downstream value signature.

Changing a detached branch therefore invalidates and reruns that branch without needlessly invalidating consumers of an unchanged published output.

Completion dependencies must still be planned and cache-checked when a downstream consumer of the workflow boundary is itself a cache hit.

A workflow boundary succeeds only after every enabled completion dependency has succeeded or produced a valid cache hit.

If any completion dependency fails or is cancelled, the boundary exposes the corresponding aggregate failure or cancellation, downstream consumers of that boundary do not run, and the root or explicitly targeted compute call reports the existing error with the failing scoped path.

A workflow with no public outputs is valid.

Executing it must still execute all enabled internal terminal branches and return a canonical zero-row, zero-column DataFrame for the workflow boundary.

Disabling a `WorkflowNode` disables its entire contained subtree and applies the normal downstream skipped-node propagation; no contained tool is planned as executable while the boundary is disabled.

At root level, `Workflow.compute(inputs=...)` with no explicit targets uses the same boundary semantics: it executes all enabled terminal branches and returns the DataFrame assembled from published outputs, or an empty DataFrame when there are no outputs.

Explicit tool-node targets retain the normal direct target-result behavior.

An explicit `WorkflowNode` target executes all enabled terminal/completion dependencies in that invocation and returns its assembled published-output DataFrame, or the canonical empty DataFrame when it has no outputs.

Hosts pass target nodes or scoped structural paths to the compiled workflow; they must not need to flatten or prune the serialized graph themselves.

Calling `compute()` without targets on an interface-free ad hoc workflow no longer guesses a terminal result; tests and examples that require a tool result must either expose it with `Workflow.output` or pass the tool node explicitly.

`compute_steps()` yields only real executable tool steps, using scoped paths such as `outer/inner/tool`; it does not yield a fake boundary execution step.

`plan()` includes scoped executable entries and an aggregate non-cache-owning entry for each `WorkflowNode` so hosts can render hierarchy and aggregate status.

Invalidation and cache clearing accept a workflow-node path to affect its full contained subtree and an internal scoped path to target that node; cascading follows dependencies across workflow boundaries in both directions as appropriate.

Remove proxy source nodes, separate composite execution paths, and temporary mutation of internal node names.

## Library-To-Platform Handoff Contract

The library implementation session owns every execution and serialization decision needed by the platform.

Before handoff, commit normative library documentation and golden test fixtures that cover:

- exact public signatures and return types for `Workflow`, `WorkflowNode`, interface construction, invocation, root inputs, loading, and export;
- the complete strict recursive graph grammar, including every node, edge, interface, constant, config, package, and custom-module field;
- the separate portable archive envelope and collision-safe custom-source identity rules;
- structural-name and scoped-path rules;
- validation error structure and full nested-path representation;
- planning, target, progress, cancellation, cache-clear, and invalidation identifiers consumed by hosts, plus the exact aggregate-status reduction and failure/cancellation propagation rules;
- root-versus-nested runtime-configuration precedence;
- file-based Python materialization freshness and the guarantee that the graph and recursive custom-source table come from one captured source snapshot;
- one minimal recursive JSON graph fixture and one archive fixture containing nested custom tools, including a same-class-name collision case.

The golden graph fixture must round-trip byte-for-byte after canonical JSON normalization through the final library APIs.

The fixtures and their tests are part of the supported contract, not temporary implementation notes.

The library session's final report must give the integrated commit hash, the paths of these normative documents and fixtures, the exact verification results, and any deliberately unsupported operation.

If a required platform behavior cannot be expressed by this committed contract, the library session is not complete.

## Implementation Sequence

### Step 0: Baseline And Worktree

- Inspect `git status`, preserve all unrelated changes, and record focused baseline test results.
- Create one branch/worktree if needed; do not work through the platform symlink.
- Read `README.md`, `docs/source/specs.md`, the workflow, node, engine, session, validation, serialization, registry, tool-loader, examples, and existing composite-workflow tests before editing.
- Use repository search to build an exact removal inventory before the first commit.
- Classify every shipped or documented workflow-definition module, including package-owned reusable workflows, before changing factory APIs; record that inventory in a test parameterization or another maintained repository manifest rather than an agent-only note.

### Step 1: Definition, Interface, And Recursive Wire Model

Add focused failing tests first for:

- symbolic field and DataFrame workflow inputs;
- workflow outputs and interface validation;
- direct `Workflow` invocation;
- two independent instances of one workflow;
- recursive serialization and round-trip;
- nested validation paths and recursive containment rejection;
- explicit trusted `Workflow.from_python` loading of `build_workflow` exactly once, with serialization and invocation proving that the factory is not rerun;
- repeated file-based `Workflow.from_python` materialization after changing the entry file or an imported local helper, proving that no stale import state is reused and that the resulting graph and custom-source table describe the same source snapshot.

Implement the symbolic interface model, `WorkflowNode`, callable `Workflow`, independent snapshots, strict recursive format, recursive custom-source collection, and definition-time validation.

It is acceptable for the old implementation to remain temporarily during this step, but new tests must exercise only the new surface.

Run focused tests plus Ruff and Pyright before committing.

This commit may retain the old implementation internally, but every new public test and fixture introduced by the commit must pass and no changed library test may be knowingly red.

Suggested first commit: `Add recursive callable workflow definitions`.

### Step 2: Compile And Execute Recursive Workflows

Add focused failing tests first for:

- root `compute(inputs=...)` and published-result assembly;
- nested field and positional DataFrame inputs;
- a workflow result consumed as a whole DataFrame;
- published outputs assembled from multiple internal nodes with compatible and incompatible indexes;
- zero-output and unpublished detached terminal execution, including when a parent consumes only one published output;
- detached-branch failure and cancellation propagation through the aggregate workflow boundary, including blocking downstream consumers and reporting the failing scoped path;
- nested disabled nodes and disabled workflow nodes;
- scoped planning, progress, caching, cancellation, and invalidation without name mutation;
- cache signatures that exclude unrelated completion-only branches;
- nested engine/environment reuse and root runtime-context precedence;
- `compute_steps()` exposing scoped real tool steps and no boundary step;
- recursive archive round-trip with workflow-local custom sources, including two modules with the same tool class name but different module IDs/content.

Implement the compiler representation and make planning, execution, `compute_steps`, cancellation, run views, progress, cache lookup/publication, invalidation, output export, and environment handling consume it.

Delete proxy and special composite engine behavior once the new execution tests pass.

Run focused execution and cache suites plus Ruff and Pyright before committing.

At this commit boundary, every new recursive definition from Step 1 must execute through the new compiler; do not leave two selectable execution paths for the new wire format.

Suggested second commit: `Compile and execute recursive workflows`.

### Step 3: Switch Every Remaining Internal Consumer

Update:

- `WorkflowSession` editing and round-trip behavior;
- tool/package/custom-source collection across recursively nested workflows;
- tool registry behavior so it indexes tools only and does not present workflows as tool classes;
- package/version resolution inside nested workflows;
- planning, cache clearing, run views, progress events, environment mismatch checks, and output export;
- public exports in `bioimageflow/__init__.py`;
- wire-format and validation helpers;
- all tests that used the old API or schema.

Avoid adapters.

Internal consumers should move directly to `Workflow`, `WorkflowNode`, the canonical interface, and the recursive wire format.

Run all deterministic unit and integration tests before committing.

At this commit boundary, all internal and public consumers must use the new contract, even if old files and terminology remain only to be deleted in Step 4.

Suggested third commit: `Adopt unified workflows across the library`.

### Step 4: Examples, Documentation, And Complete Removal

Update every workflow-definition module under `example_workflows`.

At minimum this includes:

- `bbbc038_segmentation_benchmark/workflow.py`;
- `cell_counting_phenotyping/workflow.py`;
- `fish_analysis/workflow.py`;
- `live_cell_tracking/workflow.py`;
- `low_snr_restoration/workflow.py`;
- `parameter_space_exploration/workflow.py`;
- `sairpico_deconvolution/workflow.py`;
- every reusable child workflow module, including the marker-analysis workflow used by `fish_analysis`.

Rename `build_fish_workflow` and `build_parameter_space_workflow` to the exact `build_workflow` symbol.

Convert every factory return type from tuple to `Workflow`.

Convert required data arguments into workflow interface inputs where they are invocation-time values.

Update `main()` functions and tests to call the factory, provide root inputs, and execute the returned workflow.

Add a repository test that discovers every workflow-definition module and asserts that:

- `build_workflow` exists;
- it is callable with defaults;
- it returns a fresh `Workflow` on consecutive calls;
- it returns no tuple;
- the returned workflow validates structurally without executing tools.

Discovery must cover every `example_workflows/**/workflow.py`, every reusable child workflow module anywhere below `example_workflows`, and every package-owned workflow-definition module or workflow resource found in the maintained Step 0 inventory, not only the seven current top-level entry points.

For JSON workflow resources, add a companion documented Python module exporting `build_workflow` when that workflow is presented as a Python-usable example; do not create a Python wrapper solely for internal JSON fixtures.

Move the marker-analysis child currently implemented as a composite class into an ordinary workflow module exporting `build_workflow`; import that factory in `fish_analysis` and invoke its returned `Workflow` normally.

Rewrite the specifications, API reference, tutorials, concepts, GUI integrator documentation, package-authoring guidance, example-workflow pages, docstrings, and README material as a clean description of the new model.

Add the normative handoff documentation and golden recursive graph/archive fixtures described above, and test both factory discovery and fixture round-trips in the normal suite.

Delete old tutorial pages rather than leaving redirect or migration pages.

Delete old implementation modules and old tests rather than renaming them while preserving their abstractions.

Suggested final commit: `Remove the legacy composite workflow model`.

## Mandatory Removal Inventory

The final tracked library tree must not contain:

- the old public composite definition or node classes;
- `bioimageflow/sub_workflow.py`;
- the config-driven composite implementation or its restricted type map;
- proxy-input classes or proxy tools;
- old serialization keys, source-module keys, or nested config dictionaries;
- removed records and keys including `type: "sub_workflow"`, `sub_workflow_type`, `sub_workflow_class`, `sub_workflow_module`, `sub_workflow_package`, `sub_workflow_source_module`, `from_input`, and `output_mapping`;
- special engine branches for the removed node type;
- registry discovery of workflows as `ToolMetadata`;
- old tests such as `test_sub_workflow.py` and `test_config_sub_workflow.py` unless completely replaced and renamed around `WorkflowNode` behavior;
- old tutorial/reference files or toctree entries;
- old terminology in current specs, examples, docstrings, test names, comments, or error messages.

Use a final tracked-source search, including case and separator variants, and inspect every match rather than blindly deleting generated or unrelated content.

The final search should have no matches for the removed concept in tracked source.

At minimum, run equivalent case-insensitive tracked-file searches for `SubWorkflow`, `subworkflow`, `sub_workflow`, `sub-workflow`, and `sub workflow`, plus all removed wire keys listed above.

Add strict contract tests using generic unknown node/config variants and extra keys, an explicit public-export allowlist, and a registry assertion that workflow factories are never discovered as tools.

Do not keep fixtures or test literals for the removed format merely to prove their rejection; strict unknown/extra-field tests enforce the clean parser without leaving the old schema in the final tree.

Also inspect generated API/reference output, package manifests, example launch configuration, snapshots, and golden data; a clean source grep alone is not sufficient if generated or packaged artifacts still expose removed names or schemas.

Historical Git commits are outside this requirement.

## Verification

Run focused tests throughout, then run the documented broad library checks from the library repository:

```bash
uv run ruff check .
uv run pyright
uv run pytest
uv run python docs/generate_tool_package_docs.py
uv run sphinx-build -W --keep-going docs/source docs/_build/html
```

The public exports and package contents change in this task, so run the package artifact checks:

```bash
uv run pytest tests/unit/test_package_artifacts.py
uv build --all-packages --out-dir dist/packages
BIOIMAGEFLOW_PACKAGE_ARTIFACTS_DIR=dist/packages uv run pytest tests/unit/test_package_artifacts.py
```

Do not run opt-in external, complete, model-runtime, public-data, or Wetlands tiers unless the changed behavior requires them or the normal suite explicitly routes to them.

## Completion Criteria And Handoff

The library session is complete only when:

- the new API, recursive format, validation, planning, and execution semantics are implemented;
- every example workflow exports `build_workflow` and returns a fresh `Workflow`;
- all current library docs describe only the unified model;
- the complete removal inventory is satisfied;
- required checks pass;
- only task changes are committed in coherent implementation commits;
- every intermediate commit satisfies its stated focused gate, with any intentional cross-repository break limited to the unmodified platform repository;
- the integrated primary-checkout commit hash, normative contract/fixture paths, exact verification results, and deliberately unsupported operations are reported for the platform session.

Do not start platform implementation from this session.
