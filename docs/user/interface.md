# Interface Tour

The workflow canvas is the center of BioImageFlow.
Panels around it let you find tools and workflows, edit the selected node, inspect results, and follow execution.

![The main BioImageFlow workspace, showing the Tools panel, workflow canvas, Nodes panel, Node Data, Logger, and run controls.](images/interface-overview.png)

## Menus and run controls

- **Workflow** creates, opens, saves, imports, exports, and deletes workflows. It also contains **Build from Python source**.
- **Edit** contains undo, redo, clipboard actions, selection, and **Preferences...**.
- **Execution** runs the workflow or selected nodes, retries work, recomputes results, and stops the active run.
- **View** shows or hides panels.
- **Help** opens application information.

The active workflow name appears on the right of the menu bar.
Use the pencil to change its display name.
The error indicator opens error history, the theme button selects the appearance, and **Run Workflow** starts execution or opens additional run actions.
**Run Selected** is directly available beside it and becomes enabled when selected nodes can be run.

## Canvas and tabs

Each open workflow has a canvas tab.
Double-click a workflow node to open its contents in another tab.
The active tab determines what **Nodes**, **Node Data**, Save, undo, redo, and clipboard actions affect.
After a run, opening a workflow node also shows that instance's internal node statuses; select an internal node to inspect its intermediate results in **Node Data**.

On the canvas you can:

- drag nodes and connect their handles;
- drag empty space to pan and use the mouse wheel to zoom;
- Shift-click to select several nodes;
- right-click a node for actions such as rename, disable, group, open source, and delete;
- use the canvas controls to zoom and fit the graph.

Opening a workflow centers its nodes and fits them in view without zooming above 100%.
You can zoom out to 5% to view larger workflows.

A thick border identifies a workflow nested inside another workflow.

## Panels

### Tools

Search and browse tools by category.
Drag a tool onto the canvas or use its add action.
Selecting a tool node on the canvas reveals and highlights its tool in this list, expanding its category and clearing a search if needed.
Click **Manage tools** for package versions and environments, or **Create Tool** for workflow-local Python code.

### Workflows

Browse saved workflows and folders.
Use the toolbar to create, save, duplicate, import, export, edit, or delete items.
Drag a saved workflow onto the canvas to reuse it inside the active workflow.

### Nodes

Select one canvas node to edit its name, enabled state, parameters, resources, input pins, public workflow ports, output paths, and node logs.

Use **Open tool script** to open the selected tool’s source in the embedded or configured external editor when source access is available.

### Node Data

Inspect completed tables, filter rows, preview images, and use path or viewer actions.

### Execution and Logger

**Execution** shows current and previous runs and the status of each node.
**Logger** filters application, workflow, tool, and managed-environment setup messages by severity, run, node, or text. Pixi setup output appears here for workflow tools, managed tool environments, Napari, thumbnails, and the embedded code editor.
Drag across log rows to select and copy part of the output with your normal keyboard shortcut, or choose **Copy logs** to copy all entries currently shown by the level, node, and search filters.
The copied text includes each entry's displayed time, level, node when present, and full message, including line breaks.
**Copy logs** is disabled when the filtered view is empty and shows whether copying succeeded.

### Code Editor

Open custom or installed tool source in the embedded or configured external editor.
Custom source stays with its workflow when the workflow is exported.
The embedded editor keeps the writable BioImageFlow workspace and read-only installed tool packages together as separate Explorer roots, so opening a package tool does not replace the workspace or close its terminals.
The first launch may take several minutes while BioImageFlow downloads and prepares code-server and installs editor extensions.
The Code Editor panel reports the current setup or startup phase with an activity bar, extension step count, and elapsed time; use **Open Logger** for installation details or failure diagnostics.

## Rearrange your workspace

Resize panels, move them, place them in tab groups, or reopen them from **View**.
Use the theme control beside **Run Workflow** to choose **Light**, **Dark**, or **System**.
