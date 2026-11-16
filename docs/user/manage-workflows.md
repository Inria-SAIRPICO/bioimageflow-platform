# Manage Workflows

Use **Workflows** to organize, copy, import, export, and delete saved workflows.

## Organize workflows

Select a folder before clicking **New workflow** to create the workflow there.
Use **New folder** to add another level.
The search field filters the tree.

A workflow name such as `Segmentation/Nuclei` determines its folder location.
Its display name is the readable title shown in BioImageFlow.
Changing the display name does not move the workflow.

Drag a workflow or folder onto another folder to move it.
Use **Edit selected item** to rename a folder or edit a workflow's display name.

## Open and save

Double-click a workflow, press Enter while it is selected, click **Open workflow**, or choose **Workflow → Open**.

Choose **Workflow → Save** to save the active workflow.
When a nested workflow tab is active, **Save** applies those edits to its parent node.

When closing a tab with unsaved changes, choose:

- **Save** to keep the changes;
- **Discard** to return to the last saved workflow;
- **Cancel** to keep editing.

## Make a copy

Choose **Workflow → Save As** to create a new saved workflow from the active canvas.
Use **Duplicate workflow** in **Workflows** to copy an existing saved workflow and its local tools.
Duplication does not include unsaved canvas changes.

## Import or export

### Export a workflow or its results

Choose **Workflow → Export**, or click **Export workflow** in **Workflows**.

| Export choice | What the download contains |
|---|---|
| **Workflow only** | An importable workflow archive, including its custom tools, without results. |
| **Workflow with results from the latest successful run** | The workflow archive plus copied results and provenance from one successful run. |
| **Latest result from each node** | Each node's most recent successful result. These may come from different runs, for example after running only selected nodes. |
| **Results from the latest successful run** | Copied results and provenance from one successful run, without the workflow. |

All four choices download ZIP archives.
On desktop, **Latest result from each node → folder** copies the same per-node results directly into a new child folder at a location you choose.

Exports containing a workflow save its current changes first.
Results-only exports leave the workflow unchanged.
“Latest successful run” means the most recent run that succeeded, which may have run only selected nodes; it does not promise that every node was executed.
If you need results for the whole workflow, complete **Run Workflow** before exporting.
The workflow included in a bundle is the current saved version, so edits made since that run are also included.

### Import a workflow

1. Choose **Workflow → Import** and select a workflow archive (`.bioimageflow.zip`).
   BioImageFlow extracts the workflow and its custom tools into your workspace for you.
2. If the name already exists, enter another name in **Rename imported workflow**.
   The new name appears in **Workflows** and the canvas tab; the existing workflow stays unchanged.
3. Resolve any missing tool packages using the offered installation or compatible-version choices.
   See [Resolve missing tools](data-and-tools.md#resolve-missing-tools).

The imported copy owns its files independently: you can edit it without changing the archive or another imported copy.
To edit a custom tool, select its node and click **Open tool script** in **Nodes**.
The next run uses your saved code, and future workflow exports include it.

```{note}
A workflow-and-results bundle contains the importable archive inside its `workflow/` folder.
Extract the bundle first, then import that `.bioimageflow.zip` file.
Results-only downloads cannot be imported as workflows.
```

### Viewer guidance after import

BioImageFlow checks whether your registered Napari environments can open the workflow's declared image outputs.
Missing or unknown viewer requirements do not prevent importing or running the workflow.
If setup is offered, use a reported requirement group to prefill an environment recipe, review its packages, and start setup when ready.
Nothing is installed by this check.
See [Image viewers](preferences.md#image-viewers) for details.

## Workspace and workflow files

Your **workspace** is the folder containing your saved analyses.
Its default location is `~/BioImageFlow/workspace/`.
Find or change it in **Edit → Preferences... → Storage**; **Reveal** opens it in your file browser.
Changing the workspace selects another folder; it does not move files from the old one.

```text
workspace/
  AGENTS.md                   Instructions for coding agents
  .bioimageflow/              Editor, agent, and recovery metadata
  workflows/
    My Project/              A folder shown in the Workflows panel
      Nuclei/                One workflow
        workflow.json        Saved graph, parameters, and layout
        tools/               Custom Python tools owned by this workflow
        .bioimageflow/       Recoverable drafts and nested editing state
        results/             Run records and cached results
          outputs/
            latest/          Convenient view of each node's latest outputs
```

The **Workflows** panel follows the folders beneath `workflows/`.
Saving updates `workflow.json`; custom tool code lives in `tools/` and is included in workflow exports.
Moving a workflow in the panel carries its tools and results with it.
Duplicating copies its definition and custom tools, but starts without results.

Installed tool packages and their execution environments are shared across workflows and stored separately from this folder; see [installation locations](index.md#install-the-desktop-application).
Back up the workspace to preserve your saved analyses and local tools, and back up original input datasets stored elsewhere too.
Use an export for portable result copies: the `latest/` view can contain links to managed files rather than independent copies.

## Find output files

Select a saved workflow and click **Open latest outputs**.
This view is convenient for inspection but is not a portable backup.
Use an export choice when files must remain valid after being moved.

See [Run Workflows and Inspect Results](run-and-results.md) for tables, images, logs, and run-specific results.

## Delete safely

Deleting a workflow removes its saved definition, workflow-local tools, and managed output caches after confirmation.
Export important work first.

When deleting a non-empty folder, BioImageFlow lets you delete its contents, move them to the parent folder, or cancel.
These actions cannot be undone from the canvas.
