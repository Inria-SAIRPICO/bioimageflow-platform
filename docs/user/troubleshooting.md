# Troubleshooting

Start with the message shown by BioImageFlow.
Validation banners, save messages, notifications, **Execution**, and error history usually identify the workflow, node, field, or environment that needs attention.

## The launcher does not start BioImageFlow

1. Confirm that the computer can reach GitHub and its release-download hosts.
2. Keep the launcher open and inspect its progress and log.
3. Retry after a temporary network failure.
4. Use the launcher's reinstall action if it reports a damaged local environment.
5. Download a new launcher only when release notes require it or the launcher itself is damaged.

A corporate proxy or certificate policy can block release and environment downloads.
Use the proxy dialog offered by the launcher or ask your administrator for the correct HTTPS proxy and certificate settings.

## Run Workflow is unavailable

Check that:

- the active canvas belongs to a saved root workflow;
- no save, validation, start, stop, or other run is in progress;
- the active tab is not a nested editor;
- every required tool and package version is installed;
- the workflow has no validation errors.

Save a new workflow before its first run.
For nested content, save the nested tab into its parent and run the root workflow.

## A tool or environment is missing

Open **Manage tools**, locate the requested package version, and install it.
If its environment is stopped or failed, use the environment action or recovery dialog to restart or rebuild it.

Do not choose another version unless you intend to change the workflow dependency and review affected nodes.
See [Find and Manage Tools](data-and-tools.md#resolve-missing-tools).

## The workflow has validation errors

Select the node named by the banner or error entry.
Correct its missing parameter, invalid path, incompatible connection, or unavailable tool.

For a path such as `outer_workflow/inner_workflow/tool`, open each workflow node in order.
A cycle error means one workflow would contain itself; change how the workflows are grouped or reused.

## Changes could not be saved

A red save message means the canvas changes are still visible but synchronization failed.
Correct the connection or server problem, then click **Retry**.

If BioImageFlow reports that the workflow changed elsewhere, review both versions before choosing **Apply agent changes**, **Keep my canvas**, or **Save agent version as copy**.
For a nested workflow, choose **Keep my changes** or **Use latest snapshot** only after checking which edits you need.

When a coding agent caused the conflict, ask it to re-read the active workflow before proposing another change.
Never edit workflow JSON or `.bioimageflow/platform-source` to bypass the conflict.

## Outputs are missing or unexpected

The latest-output view chooses the latest successful result independently for each node.
After partial, failed, cancelled, or overlapping runs, it can contain files from different runs.

Check the selected nodes, node status, **Execution**, and **Node Data**.
Use **Workflow with results** when every copied output must come from one successful run.

If pointer files appear, open **Edit → Preferences... → Storage** and read **Latest output view**.
Use an export when you need ordinary file copies.

## A viewer is unavailable

For Napari, wait for the first-time environment preparation, retry, and inspect application logs for a launch error.
For Avivator, confirm that the image format is supported and the application can reach the external viewer.
Use the action that reveals the image in the system file manager as a fallback.

See [Keyboard Shortcuts](keyboard-shortcuts.md) for canvas and save shortcuts.
