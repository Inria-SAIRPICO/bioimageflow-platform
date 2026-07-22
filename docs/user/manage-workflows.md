# Manage Workflows

The **Workflows** panel presents saved workflows as a folder tree under the active workspace.
Workflow IDs are path-based, so moving a workflow into a folder changes its ID while preserving its saved content and known references.

## Create folders and workflows

Select a folder before clicking **New workflow** to create the workflow inside it.
Use **New folder** to add another level to the tree.
Items are sorted alphabetically inside each folder, and the search field filters the visible tree.

A workflow has three user-facing identifiers:

- its workspace ID, such as `Segmentation/Nuclei`, determines its folder location;
- its display name is the readable title shown in the application;
- its optional description explains its purpose in the workflow detail area.

Editing the display name does not move the workflow.
Renaming or dragging the tree item changes its workspace path.

## Open and close workflows

Double-click a workflow row, press Enter on it, click **Open workflow** in its details, or choose **Workflow → Open**.
Each opened workflow gets a root canvas tab.

Closing a tab with unsaved changes offers three choices:

- **Save** promotes the accepted draft and closes the tab;
- **Discard** restores the last explicitly saved workflow and closes the tab;
- **Cancel** keeps the tab and its current draft open.

## Save, duplicate, and Save As

Use **Save** to promote the active root draft.
In a nested editor, the same command applies that editor's private snapshot to its parent node instead.

Use **Save As** to create a new saved workflow from the active graph.
Use **Duplicate workflow** in the Workflows panel to copy a saved workflow and its workflow-local tools without including unsaved draft edits.

## Move and rename

Drag a workflow or folder onto another folder to move it.
Use **Edit selected item** to change a folder name or the selected workflow's display name.
Workspace moves update open drafts and saved-workflow provenance references as one coordinated operation.

BioImageFlow rejects a move that would make a workflow contain itself directly or through another workflow.

## Delete

Deleting a workflow removes its saved definition, workflow-local tools, and server-managed output caches after confirmation.
If it is open with unsaved changes, the confirmation identifies that state.

When deleting a non-empty folder, choose whether to:

- delete the folder and all children;
- move its children to the parent folder;
- cancel without changing anything.

These actions cannot be undone from the canvas undo stack.
Export an important workflow first if you need a portable backup.

## Import and export

Choose **Workflow → Export** or click **Export workflow** in the panel to create a portable `.bioimageflow.zip` archive.
If the active workflow has unsaved changes, BioImageFlow asks to save before creating the archive.
The archive includes the recursive workflow and the workflow-local tool sources it owns.

Choose **Workflow → Import** to add a library workflow archive to the workspace.
If its suggested ID already exists, enter another name.
After import, BioImageFlow reports missing tool packages and offers to rebind dependencies that are available locally.

A platform workspace backup is not interchangeable with a portable workflow archive.
Use the export command when you want to move or share an individual workflow.

## Open workflow files and outputs

The selected workflow's detail area shows its ID and output storage path.
Use its folder action to reveal the workflow directory in the system file browser.
Use **Open latest outputs** to reveal the disposable per-node latest-output view for that workflow.
