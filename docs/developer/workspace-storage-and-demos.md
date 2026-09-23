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
    backups/
      workflow-format/
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

Workflow-format startup handling is scan-only unless a previously confirmed migration journal needs forward completion.
The preview covers saved workflow documents, root drafts, and nested snapshots and derives its plan ID from their source and target content.
Confirmation creates and synchronizes exact source-byte backups beneath `<workspace>/.bioimageflow/backups/workflow-format/<plan-id>/` before atomically replacing any authority.
Deferred workflows stay out of the editable tree; unrelated current workflows remain available.

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
Import materializes archive sources in `tools/<source-id>/` as regular Python files and assets, with `module.json` containing only identity and module-layout metadata.
Working source IDs bind nodes independently of class names; separate workflow owners can therefore use different implementations of the same class.
Source text is never executed from persisted JSON bundles.
Compilation and export capture current file contents into the library's portable source representation, using content-derived runtime identities to prevent stale Python package imports.
The former `.bioimageflow/dependencies/*/source.json` representation is unsupported; reimport its workflow archive or manually convert single-file records as described in [Troubleshooting](../user/troubleshooting.md#an-existing-workflow-cannot-open-because-custom-tool-files-are-missing) to create the current layout.
Opening an existing workflow whose referenced source manifest or Python file is missing returns HTTP 409 with `workflow_source_missing`, naming the source and missing workflow-relative file and identifying an older source record when one exists.
An absent workflow still returns HTTP 404.
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
When the selected record is corrupt, diagnostic planning reports `cache_corrupt` without making the draft unavailable, while execution remains strict.
Clearing that node removes `current.json` and moves a safely identified damaged record from `records/` into the result key's `quarantine/` directory before recomputation.

## Bundled demos

When BioImageFlow creates a workspace root that did not previously exist, it installs **Fish Analysis** and **Parameters Space Exploration** under `Demo/`.
An existing workspace root is not seeded merely because it is empty.

The **Storage** preferences report whether the recognized demos are installed and provide **Install demos** and **Remove demos** actions.
Removing demos preserves unrelated workflows under `Demo/`.
Switching to another existing workspace does not copy demos into it automatically.

The runtime bundle is version 3, and every root and recursively embedded graph is canonical schema v2.
New Fish Analysis installations give the FOLS2 and CSF1R embedded instances distinct display names; existing installed demos remain unchanged.
The maintained Python examples are exported to bundled workflow definitions with:

```bash
scripts/export_demo_workflows.py --bioimageflow-source /path/to/bioimageflow
```

This maintainer command explicitly consumes a BioImageFlow source checkout.
Generation fails if any graph in the bundle is not recursively schema v2.
Because portable BioImageFlow definitions have no GUI coordinates, export assigns the same deterministic dependency-layered platform layout recursively before calculating each demo's artifact hash.
Ordinary platform development and CI use registry packages instead.
The demos download their public inputs into workflow-managed run assets, do not depend on repository-local datasets, and retain normal missing-package diagnostics without installing tool packages automatically.
An installed demo with matching bundled provenance is never replaced because the application version or bundle version changed, including on restart and explicit install calls; only missing canonical demos are installed.
