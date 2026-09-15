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

Choose **Workflow → Export**, or click **Export workflow** in **Workflows**.

| Export choice | Use it for |
|---|---|
| **Workflow only** | Share or back up the workflow and its workflow-local tools without results. |
| **Latest results** | Copy the latest successful result of each node. These files can come from different runs. |
| **Workflow with results** | Keep the workflow and the outputs from one successful run together. |
| **Export latest results to folder** | Write the latest successful node results to a new local folder. |

Exporting a workflow saves its current changes first.
A results-only export does not change the workflow.

Choose **Workflow → Import** to add a workflow archive.
BioImageFlow unpacks it into an ordinary editable workspace workflow, including its custom Python tools.
You do not need to unzip a workflow archive yourself.
The imported workflow owns its files independently of the archive and other imported copies.
If its name already exists, enter another name.
The name entered in **Rename imported workflow** becomes the imported workflow's visible name in the Workflows panel and canvas tab and is retained when you reopen it.
The existing workflow keeps its name and contents.
After import, BioImageFlow shows missing tools and offers compatible versions already installed on your system.
It also checks the archive's portable viewing requirements against registered Napari environments without installing packages or opening the archive's code.
An uncovered or unknown viewer requirement does not prevent importing or running the workflow.
Use the reported requirement groups to prefill one or more managed environment recipes, then review the proposed packages before starting setup.
Select a tool node and click **Open tool script** to edit the code that node uses.
Saving the script affects the next run; exporting the workflow includes the edited code.

A **Workflow with results** bundle is not directly importable.
Extract it and import the `.bioimageflow.zip` file inside its `workflow/` folder.

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
