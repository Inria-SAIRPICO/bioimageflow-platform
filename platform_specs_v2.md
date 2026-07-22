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
  "schema_version": 1,
  "name": "measure_cells",
  "display_name": "Measure cells",
  "nodes": [],
  "edges": [],
  "interface": {"inputs": [], "outputs": []},
  "config": {
    "storage_path": "./bif_data",
    "engine": "wetlands",
    "execution": "parallel"
  }
}
```

`schema_version`, `name`, `display_name`, `interface`, and `config` are required at every depth.
The graph owns layout, collapsed state, enabled state, parameter values, resource overrides, and output templates exactly once.

The workspace `workflow.json` is a `WorkflowDocument` envelope containing a platform document version, the canonical graph, workspace metadata, the artifact hash, optional Python authoring provenance, and owned workflow-local source identifiers.
Runtime translation to the BioImageFlow library happens in memory from the accepted graph snapshot.

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
    "schema_version": 1,
    "name": "segment_and_measure",
    "display_name": "Segment and measure",
    "nodes": [],
    "edges": [],
    "interface": {"inputs": [], "outputs": []},
    "config": {
      "storage_path": "./bif_data",
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

The frontend uses a versioned endpoint-handle codec.
Handles distinguish DataFrame output, tool input, tool output, DataFrame position, named DataFrame input, workflow input ID, and workflow output ID.
Display labels are never structural endpoint identities.

## 5. Workflow Interfaces

Every graph has one `WorkflowInterface` with `inputs` and `outputs`.
Each port has an immutable `id` and an editable `name`.

Workflow inputs are either field inputs with one or more internal targets or DataFrame inputs with one or more internal targets.
Workflow outputs map a stable port ID to an internal node and output.

The Node Panel uses **Expose as workflow input**, **Expose as workflow output**, **Workflow input name**, and **Workflow output name**.
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

Embedding copies workflow-local sources into destination-owned content-addressed storage.
Package tools remain versioned package dependencies.
Same-named local tools with different content must coexist without registry shadowing.

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

Saving preserves compatible parent bindings and edges by stable port ID.
Removed or incompatible connected ports require confirmation.
If the parent node changed or disappeared since the editor opened, apply reports a conflict and changes nothing.
During execution, root and nested editors are mutation-locked uniformly.

## 8. Validation And Translation

All accepted root drafts, nested snapshots, execution requests, cache operations, import, and export use the same recursive graph translator and library compiler.

Validation covers recursive graph structure, discriminator correctness, unique node/edge/interface IDs, field and DataFrame interface targets, binding and edge compatibility, recursive tool availability, workflow-local source ownership, workspace containment, source-update preconditions, and execution mutation locking.
Errors use scoped paths such as `segment_and_measure/cellpose_segmenter`.

The stateless graph endpoint validates the same canonical graph shape but does not retain editor state.

## 9. Execution And Status

Execution compiles the accepted recursive graph to one flat plan.
Internal nodes receive scoped structural IDs.
Caching remains per internal tool node, and logs, progress, validation, cache clearing, and output lookup retain scoped paths.

Selecting a workflow node for Run Selected targets that workflow boundary and schedules its enabled internal completion dependencies.
The platform does not prune or rebuild a partial graph before compilation.

A workflow node projects aggregate status from its descendants while preserving the failing or cancelled scoped path.
Detached internal failures still make the workflow node fail and block its downstream consumers.

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

Root drafts use revision compare-and-swap, a saved-artifact baseline, validation, dirty state, and writer metadata.
Nested snapshots use their own revision compare-and-swap and ownership chain.
Save and Run operate on exact accepted snapshots.
Remote draft changes are resolved explicitly before destructive or execution operations.

Workflow identities are path-derived and carry durable identity generations.
Move, rename, delete, duplicate, and save operations bind to captured identities so delayed responses cannot mutate a recreated same-ID workflow.
Moves update drafts, retained snapshots, and provenance references atomically.

Portable export/import uses the BioImageFlow library recursive archive format.
A workspace-document backup, when provided, is a separate platform artifact and is not accepted as a library workflow archive.

### Bundled demo workflows

The application bundle contains versioned platform templates generated deterministically from the maintained Python examples for **Fish Analysis** and **Parameters Space Exploration**.
The examples are self-contained definitions that download their public input data into workflow-managed run assets and do not reference repository-local datasets.

Initialization installs both templates under `Demo/` only when the active workflow root did not exist before initialization.
An existing workflow root is not seeded merely because it is empty, and a workspace change applies the same new-root rule.
No launcher post-install hook, user-home marker, or demo-folder filesystem watcher participates in this decision.

Demo status is derived from each canonical path and `metadata.bundled_template` identity.
A matching template identity is installed regardless of its recorded bundle version and is never overwritten automatically; an absent identity is missing; an occupied canonical path without matching provenance is a conflict.
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

Node Data is a read-only inspection surface during execution.
Thumbnail requests are initiated only when their rendered row enters the visible table viewport, and nested canvases use their own canvas-scoped Node Data query state.

## 14. API Surface

The v2 API includes canonical workflow lifecycle routes; root workflow-draft routes; nested workflow-snapshot routes; recursive validation, execution, output-schema, cache, package, and tool routes; source-update preview and apply routes; and trusted Python-source preview using the same apply route.

OpenAPI is the sole frontend API type source.
Generated discriminated graph, interface, edge, provenance, and source-operation types are consumed directly without handwritten compatibility aliases.

## 15. Keyboard And Context Actions

Ctrl/Cmd+S saves the active persistence context.
In a root tab it saves the workspace workflow; in a nested tab it applies the accepted nested snapshot to its parent.

The workflow-node context actions are **Open workflow**, source actions when provenance exists, Rename, Enable/Disable, and Delete.
The selection action is **Group into workflow**.
