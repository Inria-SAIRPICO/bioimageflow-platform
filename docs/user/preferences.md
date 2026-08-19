# Settings, Storage, and Integrations

Choose **Edit → Preferences...**.
On macOS, Cmd+, also opens the dialog; use Ctrl+, on Windows or Linux.

Changes are saved as you make them.
If a change fails, BioImageFlow keeps the previous value and shows an error.

## External Editor

Enter the command used to open workflow-local source files.
Include `{file_path}` where the selected file path belongs, for example `code {file_path}`.
Leave it empty to use the embedded editor when available.

BioImageFlow opens the editor at the workspace root and focuses the selected source file.
The same workspace root is used by the [coding-agent walkthrough](coding-agent.md).

## Execution

Choose the default execution target and how new workflows schedule independent nodes.
You can add and edit distributed profiles for configured remote systems.

See [Distributed Execution](distributed-execution.md) before adding a remote target or startup script.

## Display

Set **Node Data rows per page** for newly opened result tables.
You can temporarily choose another page size in an individual table.

## Storage

### Workspace path

The workspace contains saved workflows and their workflow-local tools.
Click **Reveal** to open the displayed location, or click **Browse...** to switch to another workspace.

Changing the workspace does not move workflows from the previous location.
Each workflow stores its managed execution results in its own `results` folder.

### Latest output view

**Latest output view** reports whether BioImageFlow can use symbolic links or must use portable pointer files.
Click **Retest** after changing filesystem permissions or mount settings.

This view is for convenient inspection, not backup.
Use **Workflow → Export** to make independent file copies.

### Tool store path

**Tool store path** shows where shared, versioned tool packages are installed.
The default is `~/.bioimageflow/tool_packages/`.

### Example workflows

Click **Install demos** to add missing bundled examples under **Demo** without overwriting other workflows.
Click **Remove demos** to remove only recognized bundled examples and their managed caches.

## OMERO

Add an OMERO connection with a display name, host, port, username, and password.
BioImageFlow stores the password in the operating system credential service and reports only whether one is stored.

Removing a connection also removes its stored credential after confirmation.
Tools that support OMERO let you choose one of these named connections in their own parameters.

## Launcher version and updates

The launcher log shows **Using version:** followed by the release it starts.
BioImageFlow's packaged launcher is configured to select the latest verified application release automatically; keep using the same launcher to receive application updates.

```{note}
Launcher behavior belongs to the installed launcher, not the **Preferences...** dialog.
Download a newer launcher only when the BioImageFlow release notes specifically require it.
```
