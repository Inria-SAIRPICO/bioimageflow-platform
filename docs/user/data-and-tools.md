# Manage Data and Tools

BioImageFlow separates managed input data from analysis tools.
The **Datasets** panel organizes files that workflows can consume, while the **Tools** panel manages the executable steps available to workflows.

## Upload and organize datasets

Click **Upload files** in the Datasets panel and choose one or more files.
Each upload shows progress and can be cancelled while active, retried after failure, or dismissed after completion.
Use **Clear completed** to remove finished upload notifications without deleting uploaded files.

The dataset tree supports folders, rename, deletion, search, and drag-and-drop moves.
Use the checkboxes to select several files or folders.
Selecting a folder includes its descendants; clearing one child leaves the parent visibly partially selected.

Before deletion, BioImageFlow previews the managed items that will be removed and identifies changed data if the dataset tree was updated elsewhere.

## Put datasets into a workflow

After selecting data, use one of these actions:

- **Create Files node** adds a Files node to the active canvas with the selected files resolved in tree order.
- **Set files on “node name”** replaces the files on the selected compatible Files node.
- dragging files or folders from the dataset tree onto the canvas creates or updates a compatible input flow.

Dropping local files anywhere on the application uploads them into managed dataset storage and selects them in the Datasets panel.
After the upload completes, click **Create Files node** or drag the new dataset entry onto the canvas.

## Browse and add tools

The Tools panel groups tools by their primary category.
Search uses tool names and metadata, and matching categories expand automatically.
Use the information action to read the tool's documentation before adding it.

Drag a tool onto the canvas or use its add action.
An available tool can still need an environment to be prepared before its first execution.

## Install and select package versions

Open **Manage Tools** to see known and installed packages, their versions, the tools each version provides, and environment states.

For a known package, open its version list and use the row action to install, select, or uninstall a version.
A workflow selects one version per package.
Changing that selection can make existing nodes out of date, and BioImageFlow asks before rebuilding their outputs.

For a package that is not in the known list, use the **Install tool package** footer.
Enter a supported GitHub or GitLab package URL, or select a `.zip` package archive, then click **Install**.
Package-source installation is a trusted desktop action: install code only from a source you trust.

## Manage tool environments

The environment badge reports states such as stopped, creating, running, ready, failed, or unavailable.
Use the power action to start or stop a tool environment.
Environment controls are disabled while workflow execution is active.

If an execution cannot use an environment, BioImageFlow opens an environment recovery dialog.
Choose the offered restart or rebuild action and wait for recovery before retrying the workflow.

## Resolve missing dependencies

A workflow can refer to a tool package or version that is not installed locally.
BioImageFlow keeps the workflow structure visible, marks missing tools, and blocks execution until the dependency is resolved.

Use **Install all missing packages** in the dependency dialog to install every requested version, or use Manage Tools to install versions individually.
When every missing dependency has an installed alternative, **Use installed alternatives…** can rebind the workflow after confirmation.
After importing a workflow, use the rebind action only when the locally available tools are the intended replacements.

## Create workflow-local tools

Workflow-local tools travel with their owning workflow archive and are appropriate for analysis code specific to that workflow.
Use a packaged tool when the same implementation should be shared and versioned across many workflows.

To create a local tool:

1. save or open the workflow that will own the source;
2. click **Create Tool** in the Tools panel;
3. enter a name and choose **Processing Tool** or **DataFrame Tool**;
4. click **Create**;
5. complete the generated Python source in the embedded or configured external editor.

The dialog converts a readable name into a valid Python class name and prevents collisions with existing tools.
When a saved source file changes, hot reload refreshes the tool metadata and marks affected nodes out of date when necessary.

Manage Tools also provides actions to open, rename, or delete editable workflow-local tools.
Deletion identifies saved workflows that reference the tool and requires confirmation.
