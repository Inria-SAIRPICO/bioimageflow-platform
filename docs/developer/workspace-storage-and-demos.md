---
orphan: true
---

# Workspace, Storage, and Demos

This page documents the filesystem and lifecycle rules maintained by the platform.
For user-facing actions, see [Settings, Storage, and Integrations](../user/preferences.md), [Manage Workflows](../user/manage-workflows.md), and [Run Workflows and Inspect Results](../user/run-and-results.md).

## Workspace layout

The desktop application has one active BioImageFlow workspace.
Its default location is `~/BioImageFlow/workspace/`, and the user can select another directory in **Edit → Preferences... → Storage**.

```text
workspace/
  .bioimageflow/
    executions/
      retry_plans/
      cleanup_plans/
    execution_exports/
  workflows/
    <workflow-id>/
      workflow.json
      tools/
      results/
```

Workflow IDs are paths relative to `workspace/workflows/`, such as `segmentation/nuclei` or `My Project/quality_control`.
Folder segments can contain spaces.

Each workflow derives its runtime storage from `<workflow-directory>/results`; this path is not stored as an editable workflow setting.
Moving or deleting a workflow carries or removes its results.
Duplicating a workflow copies the reusable definition and workflow-local tools but starts without the source workflow's results.
Stateless graph services use `<workspace>/.bioimageflow/runtime`.

Managed execution snapshots and their retry or cleanup journals use `<workspace>/.bioimageflow/executions`.
Verified managed result bundles use the deterministic `<workspace>/.bioimageflow/execution_exports/<execution-id>` destination and can be reused after restart or confirmed remote cleanup.
Switching workspaces changes the managed history and storage roots used for new executions, while an execution already loaded or created remains bound to its original workspace for active polling, journals, and result writes.

## Workflow folders and nested sources

The **Workflows** panel presents the directory hierarchy as folders and workflows sorted alphabetically within each folder.
Users can create, rename, move, and delete folders or workflows.
Deleting a non-empty folder asks whether to delete its children, move them to the parent, or cancel.

Dragging a saved workflow onto the canvas embeds an executable snapshot with source provenance.
The same recursive editor is used for workflow nodes created by dragging a saved workflow or grouping existing nodes.
BioImageFlow prevents direct and indirect self-containment.

The workflow-local `tools/` directory owns custom tool source that must travel with the workflow archive.
Reusable tools belong in separately versioned tool packages instead.
The embedded editor opens a generated multi-root VS Code workspace containing the writable BioImageFlow workspace and the read-only installed tool store.

## Latest output view and exports

Each workflow publishes a file-manager-friendly view of the latest successful assets beneath its result storage.
The projection selects the latest successful result independently for each node, so selected, failed, cancelled, or overlapping executions can leave it containing outputs from different runs.
It is not a snapshot of one complete workflow execution.

The platform uses symbolic links for this disposable view when possible and portable `*.bioimageflow-link.json` pointer files otherwise.
**Preferences... → Storage → Latest output view** reports the effective mode.
The **Open latest outputs** action opens this per-workflow directory.

Exports create independent copies when portability matters:

- **Workflow only** contains the reusable workflow and its local tools.
- **Latest results** copies the latest successful result of each node.
- **Workflow with results** combines the workflow with copied outputs and provenance from one successful run.
- **Export latest results to folder** writes copied latest results to a chosen destination.

A workflow-and-results bundle is an export artifact, not a directly importable workflow archive.
The workflow archive inside its `workflow/` directory can be imported separately.

## Execution cache actions

**Retry Failed Execution** reuses successful cached work and preserves the original execution target set.
**Invalidate Failed Nodes and Retry...** clears cache selection for failed nodes and their downstream work before retrying.
**Recompute Workflow...** invalidates all enabled nodes before a complete run.

Invalidation changes which retained records can be selected for reuse.
It does not immediately delete those records or reclaim their disk space.

## Bundled demos

When BioImageFlow creates a workspace root that did not previously exist, it installs **Fish Analysis** and **Parameters Space Exploration** under `Demo/`.
An existing workspace root is not seeded merely because it is empty.

The **Storage** preferences report whether the recognized demos are installed and provide **Install demos** and **Remove demos** actions.
Removing demos preserves unrelated workflows under `Demo/`.
Switching to another existing workspace does not copy demos into it automatically.

The maintained Python examples are exported to bundled workflow definitions with:

```bash
scripts/export_demo_workflows.py --bioimageflow-source /path/to/bioimageflow
```

This maintainer command explicitly consumes a BioImageFlow source checkout.
Ordinary platform development and CI use registry packages instead.
The demos download their public inputs into workflow-managed run assets, do not depend on repository-local datasets, and retain normal missing-package diagnostics without installing tool packages automatically.
