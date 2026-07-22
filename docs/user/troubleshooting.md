# Troubleshooting and Reference

Start with the message shown by BioImageFlow.
Validation banners, persistence messages, toasts, execution details, and the error history usually identify the workflow, node, field, or environment that needs attention.

## Launcher or startup problems

If the launcher cannot prepare or start BioImageFlow:

1. confirm that the computer can reach GitHub and its release-download hosts;
2. keep the launcher open and inspect its progress or log view;
3. retry after a transient network failure;
4. use the launcher's reinstall action if it reports a corrupted local environment;
5. download a new launcher only when the release notes publish a launcher update or the existing launcher itself is damaged.

A corporate proxy or custom certificate authority can prevent release and environment downloads.
Use the proxy dialog offered by the launcher or ask your system administrator for the correct HTTPS proxy and certificate settings.

## A workflow cannot run

The run action is unavailable when:

- no saved root workflow owns the active canvas;
- a lifecycle operation, draft validation, start, stop, or another execution is in progress;
- the active tab is a nested editor;
- required tools or package versions are missing;
- the accepted graph has validation errors.

Save a new workflow before its first run.
For nested content, save the nested tab into its parent and run the owning root workflow.

## Missing tools or failed environments

Open **Manage Tools**, locate the requested package version, and install it.
If the package is installed but its environment is stopped or failed, use the environment action or the recovery dialog to restart or rebuild it.
Tool and package downloads require network access.

Do not substitute another version unless you intend to change the workflow dependency and rebuild affected nodes.

## Validation errors

Select the node named by the banner, field error, or error-history entry.
Correct missing parameters, invalid paths, incompatible connections, duplicate identities, or unavailable tools, then wait for draft synchronization.

For a path such as `outer_workflow/inner_workflow/tool`, open each workflow node in order until you reach the named tool.

Containment-cycle errors mean the requested embed, paste, import, move, source update, or save would make a workflow contain itself recursively.
Reorganize the workflow relationship instead of retrying the same action.

## Changes could not be saved

A red persistence message means synchronization failed but the latest canvas changes remain locally visible.
Use **Retry** after correcting the underlying connection or server problem.

An amber conflict means the same draft or nested snapshot changed elsewhere.
Choose the action that matches your intent:

- **Keep my changes** retries from your local nested canvas;
- **Use latest snapshot** replaces local nested changes with the accepted remote snapshot;
- **Apply agent changes** accepts an external workflow edit;
- **Keep my canvas** preserves the current canvas version;
- **Save agent version as copy** preserves both root versions as separate workflows.

Review the named workflow and revision before choosing because conflict resolution can discard one version.

## An update from source is blocked

Save or discard any open editor at or below the workflow node you want to replace.
Then request **Update from source** again so BioImageFlow can create a fresh preview.

If the source or parent changed after the preview, the apply step intentionally changes nothing.
Review the new preview rather than repeating an old confirmation.

## Outputs are missing or surprising

The `latest` output view is assembled independently per node and is not one execution snapshot.
A selected, failed, cancelled, or cached run can therefore leave files from different successful executions in that view.

Check the active execution, selected nodes, node statuses, and Node Data before assuming that all files were produced together.
Under **Preferences → Storage**, inspect the effective latest-output mode and warning.
Pointer files are metadata and cannot be opened directly as images.

## A viewer action is unavailable

For Napari, configure a Python environment containing Napari under **Preferences → Napari** and retry after any launch failure.
For Avivator, confirm that the image format is supported and that the application can reach the external viewer service.
Use **Reveal in file browser** as a local fallback.

## Keyboard shortcuts

Shortcuts act on the active canvas unless noted otherwise.
Use Cmd in place of Ctrl on macOS.

| Shortcut | Action |
|---|---|
| Ctrl/Cmd+S | Save the active root workflow, or apply the active nested snapshot to its parent |
| Ctrl/Cmd+Z | Undo the latest active-canvas graph change |
| Ctrl/Cmd+Shift+Z | Redo the latest active-canvas graph change |
| Ctrl/Cmd+C | Copy selected nodes |
| Ctrl/Cmd+V | Paste nodes |
| Ctrl/Cmd+A | Select all nodes |
| Delete or Backspace | Delete selected nodes or edges |
| F | Fit the active graph in view |
| Ctrl/Cmd+Enter | Flush pending active-canvas synchronization |
| Cmd+, on macOS; Ctrl+, in the desktop app on Windows/Linux | Open Preferences |
| Escape | Close an open node context menu |

## Glossary

**Accepted draft**
: The latest graph revision stored by the backend for an open root workflow.

**Cache**
: Retained results that can let an unchanged node avoid repeated computation.

**Column edge**
: A connection carrying one named output field into one input.

**DataFrame edge**
: A connection carrying a complete table between nodes or workflow interfaces.

**Provenance**
: The optional record linking an embedded workflow snapshot to the saved workflow it came from.

**Workflow interface**
: The stable named inputs and outputs through which a workflow node connects to its parent graph.

**Workflow-local tool**
: Python tool source owned and exported by one saved workflow.
