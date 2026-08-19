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

## Canvas and tabs

Each open workflow has a canvas tab.
Double-click a workflow node to open its contents in another tab.
The active tab determines what **Nodes**, **Node Data**, Save, undo, redo, and clipboard actions affect.

On the canvas you can:

- drag nodes and connect their handles;
- drag empty space to pan and use the mouse wheel to zoom;
- Shift-click to select several nodes;
- right-click a node for actions such as rename, disable, group, open source, and delete;
- use the canvas controls to zoom and fit the graph.

A thick border identifies a workflow nested inside another workflow.

## Panels

### Tools

Search and browse tools by category.
Drag a tool onto the canvas or use its add action.
Click **Manage tools** for package versions and environments, or **Create Tool** for workflow-local Python code.

### Workflows

Browse saved workflows and folders.
Use the toolbar to create, save, duplicate, import, export, edit, or delete items.
Drag a saved workflow onto the canvas to reuse it inside the active workflow.

### Nodes

Select one canvas node to edit its name, enabled state, parameters, resources, input pins, public workflow ports, output paths, and node logs.

### Node Data

Inspect completed tables, filter rows, preview images, and use path or viewer actions.

### Execution and Logger

**Execution** shows current and previous runs and the status of each node.
**Logger** filters application, workflow, and tool messages by severity, run, node, or text.

### Code Editor

Open workflow-local tool source in the embedded or configured external editor.
Custom source stays with its workflow when the workflow is exported.

## Rearrange your workspace

Resize panels, move them, place them in tab groups, or reopen them from **View**.
Use the theme control beside **Run Workflow** to choose **Light**, **Dark**, or **System**.
