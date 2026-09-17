# Settings, Storage, and Integrations

Choose **Edit → Preferences...**.
On macOS, Cmd+, also opens the dialog; use Ctrl+, on Windows or Linux.

Changes are saved as you make them.
If a change fails, BioImageFlow keeps the previous value and shows an error.

## External Editor

Enter the command used to open workflow-local source files.
Include `{file_path}` where the selected file path belongs, for example `code {file_path}`.
Leave it empty to use the embedded editor when available.

The embedded editor shows two roots: **Workspace** for workflows and custom tools, and **Installed Tool Packages** for shared versioned packages.
Installed package files are read-only because an update or reinstall may replace them.
New terminals start in **Workspace**, and opening either kind of tool keeps the same editor project and existing terminal sessions.

A configured external editor continues to use its command-defined project folder.
The workspace root used by external editors is also used by the [coding-agent walkthrough](coding-agent.md).

## Image Viewers

Desktop mode can keep several named Napari environments side by side.
Use **Add existing** to register a Conda environment or virtual environment without changing its packages, or **Create environment** to let BioImageFlow create an isolated managed environment.
Each entry shows its detected Python, Napari, Qt, and installed-distribution inventory.
Use **Refresh** after changing packages outside BioImageFlow, and **Launch empty viewer** when you want to start or focus that environment without opening an image.

Choose a global default for outputs that have no more-specific preference.
Optional file-opening rules match the complete file or directory name from top to bottom; the first match wins.
The **Extension** shortcut turns values such as `.ome.tif` into `*.ome.tif`, while **Filename pattern** accepts `*`, `?`, and bracket character classes.
Use the filename test before saving or reordering a broad rule.
An environment preference never overrides a tool output's required packages, and a reader ID is attempted only for opens selected by that rule.

Managed environment creation uses an isolated recipe.
The default recipe installs Python 3.12, Napari 0.9.1, and PyQt6; the legacy recipe installs Napari 0.6.6 and PyQt5.
Creating a modified copy leaves the original installation unchanged.
Setup, retry, cancellation, and removal progress appears with the affected environment.

The viewing requirements report compares every declared output requirement in the saved workflow with the current registered inventories.
It is informational: unknown or uncovered requirements do not block editing or running, and checking them does not install packages or launch Napari.
When requirements are uncovered, use a setup action on one requirement group to prefill a separate managed environment recipe.

Fiji is installed separately from BioImageFlow.
[Download Fiji](https://imagej.net/software/fiji/downloads), unpack it, then choose the `Fiji.app` folder in **Preferences → Image Viewers**.
In Node Data, use the Fiji button beside Napari to open an image; before setup, the same button takes you to the Fiji setting.

## Execution

Choose the default execution target and how new workflows schedule independent nodes.
**Local** preserves workstation execution through Direct and Wetlands.
In desktop mode, a managed remote profile stores a name and the path to one trusted Python script whose top level defines `cluster = RemoteCluster(...)`.
Saving the profile records its observed digest and non-secret host/root observations.
Use **Describe cluster** to show its destination, scheduler request, connection observation, capabilities, and structured diagnostics.
Opening the target list does not execute the trusted script; saving, describing, and submitting do.
Download the reusable Slurm example to start with `cluster.py`, `parsl.py`, and optional `setup.sh` files that keep genuine site facts together.
In webapp mode, managed profiles are provisioned out of band and appear read-only.
If a saved default names a removed, disabled, or obsolete profile, BioImageFlow repairs the setting to **Local** the next time profiles load.

See [Managed Cluster Execution](distributed-execution.md) before selecting or trusting a cluster script.

## Display

Set **Node Data rows per page** for newly opened result tables.
You can temporarily choose another page size in an individual table.

## Storage

### Workspace path

The workspace contains saved workflows and their workflow-local tools.
Click **Reveal** to open the displayed location, or click **Browse...** to switch to another workspace.

Changing the workspace does not move workflows from the previous location.
Local workflow runtime results remain in each workflow's `results` folder.
Managed run history, retry and cleanup journals, and verified downloaded result bundles remain under the workspace's private `.bioimageflow` directory.
Already running managed executions keep writing to the workspace where they started, while the selected workspace owns new runs and the history currently shown.

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
