# Preferences and Integrations

Open **Edit → Preferences…**.
On macOS, Cmd+, also opens Preferences; in the desktop application on Windows or Linux, use Ctrl+,.

Settings are saved as you change them.
If an update fails, BioImageFlow leaves the previous setting in effect and displays an error.

## External Editor

Set the command used to open workflow-local source files.
Include `{file_path}` where the selected source path should be inserted, for example `code {file_path}`.
Leave the field empty to use the embedded editor behavior when available.

Tool source opens with the editor rooted at the workspace project while focusing the selected file.

## Napari

Choose a Python environment that already contains Napari, or enter its path.
Leave the setting empty to disable the **Open in Napari** action in result tables.

BioImageFlow starts Napari lazily when you first open an image and reports launch progress above the workspace.
Closing BioImageFlow also shuts down the Napari process it manages.

## Execution

This tab summarizes the active execution backend and whether scheduling is sequential or parallel.
These values are derived from the current platform and workflow configuration and are read-only in Preferences.

## Display

Choose the default number of **Node Data rows per page** for newly inspected result tables.
Individual tables can temporarily select a different page size without changing this default.

## Storage

### Workspace

The workspace contains the saved workflow tree and workflow-local tools.
Use **Reveal** to open the current location in the file browser.
In desktop mode, **Browse…** switches to another workspace.

Changing the workspace does not move workflows from the previous location.
If the selected workflow root already exists, BioImageFlow does not add examples merely because the root is empty.

### Latest output view

Choose how the disposable `outputs/latest` projection is published:

- **Automatic** uses symbolic links when the filesystem supports them and falls back to pointer files with a warning.
- **Symbolic links** are directly openable but can require Developer Mode or link privileges on Windows.
- **Pointer files** use little extra space and need no link privilege, but image applications cannot open the JSON pointer files directly.
- **Copies** work with ordinary file applications but can use roughly twice the asset space.

The displayed effective mode tells you what BioImageFlow is currently using.
Click **Retest** after changing filesystem permissions or mount configuration.

### Output data folder

This folder contains workflow execution storage, caches, and published output views.
Use **Reveal** to inspect it or **Browse…** to choose a different folder.
Existing data is not moved when you change the setting.

### Tool store

The read-only path identifies the shared versioned tool-package store.
Its default is `~/.bioimageflow/tool_packages/`.

### Example workflows

The status shows how many recognized bundled examples occupy their canonical locations under `Demo/`.
Use **Install demos** to add missing examples without overwriting conflicts.
Use **Remove demos** to remove only recognized canonical examples and their server-managed caches; unrelated children in the Demo folder are preserved.

Renaming or moving an example detaches it from its canonical status, so a later install can create a fresh copy at the original location.

## OMERO

Add one row for each OMERO connection.
Provide an optional unique display name, host, port, username, and password, then use the row's save action.
BioImageFlow stores the password in the operating system's credential service and reports only whether a password is stored.

Duplicate a row when configuring a related account or endpoint.
Removing a row also deletes its stored credential after confirmation.

Workflow tools that support OMERO select these named instances through their own parameters or configuration.
