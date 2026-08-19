# Manage Workflows

> **Available in:** Desktop and browser. Exporting results directly to a local folder is desktop-only.

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

Choose **Workflow → Export**, or click **Export workflow** in **Workflows**.

| Export choice | Use it for |
|---|---|
| **Workflow only** | Share or back up the workflow and its workflow-local tools without results. |
| **Latest results** | Copy the latest successful result of each node. These files can come from different runs. |
| **Workflow with results** | Keep the workflow and the outputs from one successful run together. |
| **Export latest results to folder** | Write the latest successful node results to a new local folder on desktop. |

Exporting a workflow saves its current changes first.
A results-only export does not change the workflow.

Choose **Workflow → Import** to add a workflow archive.
If its name already exists, enter another name.
After import, BioImageFlow shows missing tools and offers compatible versions already installed on your system.

A **Workflow with results** bundle is not directly importable.
Extract it and import the `.bioimageflow.zip` file inside its `workflow/` folder.

## Find output files

Select a saved workflow and click **Open latest outputs** on desktop.
This view is convenient for inspection but is not a portable backup.
Use an export choice when files must remain valid after being moved.

See [Run Workflows and Inspect Results](run-and-results.md) for tables, images, logs, and run-specific results.

## Delete safely

Deleting a workflow removes its saved definition, workflow-local tools, and managed output caches after confirmation.
Export important work first.

When deleting a non-empty folder, BioImageFlow lets you delete its contents, move them to the parent folder, or cancel.
These actions cannot be undone from the canvas.
