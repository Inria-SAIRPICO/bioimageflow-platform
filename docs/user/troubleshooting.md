# Troubleshooting

Start with the message shown by BioImageFlow.
Validation banners, save messages, notifications, **Execution**, and error history usually identify the workflow, node, field, or environment that needs attention.
Error text is selectable, so copy the complete detail—including any validation field location—when reporting a problem.

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
If its environment is stopped or failed, use the power action to start it or the labeled **Create / recreate** action in **Manage tools** to rebuild it.
If the environment is updating, wait for the managed replacement to finish and inspect the Logger panel if it fails.

Do not choose another version unless you intend to change the workflow dependency and review affected nodes.
See [Find and Manage Tools](data-and-tools.md#resolve-missing-tools).

## The workflow has validation errors

Select the node named by the banner or error entry.
Correct its missing parameter, invalid path, incompatible connection, or unavailable tool.

For a path such as `outer_workflow/inner_workflow/tool`, open each workflow node in order.
A cycle error means one workflow would contain itself; change how the workflows are grouped or reused.

## A workflow format update is waiting

BioImageFlow previews older workflow files without changing them.
Choose **Not now** to leave every affected saved workflow, draft, and nested editing snapshot untouched; those workflows remain unavailable, but current workflows continue working.

Use **Review updates** in the Workflows warning when you are ready, then choose **Update workflows**.
BioImageFlow verifies that the previewed files did not change, preserves their exact bytes under `<workspace>/.bioimageflow/backups/workflow-format/<plan-id>/`, and shows every backup path after the update.
If the preview became stale, review it again instead of overwriting newer edits.
An interrupted confirmed update completes forward on restart from its journal and backups.

## An existing workflow cannot open because custom-tool files are missing

The message identifies the missing file relative to the workflow's folder.
If it also identifies an older source record under `.bioimageflow/dependencies/<source-id>/source.json`, the workflow was saved with the former custom-tool storage layout.
The current platform requires editable files under `tools/<source-id>/` and does not automatically convert those older records.

If you have the original `.bioimageflow.zip` archive, choose **Workflow → Import** and use a new workflow name when prompted about a collision.
The import creates the current tool-file layout.
It restores the archive's saved definition; edits and results made since that export remain in the old workflow.
Keep the old workflow until you have checked the imported copy.

For single-file tools, you can instead convert the old records manually while preserving the existing workflow, drafts, and results:

1. Quit BioImageFlow and back up the complete workflow folder, including its hidden `.bioimageflow` directory.
2. For each `.bioimageflow/dependencies/<source-id>/source.json`, inspect its `id`, `module`, `filename`, `source`, and `source_hash` fields.
   These instructions apply to single-file records; if a record contains `root_package` or `files`, reimport its archive instead.
3. Create `tools/<source-id>/` within the workflow folder.
   If that destination already contains files, preserve them and use an archive or backup to resolve the conflict instead of overwriting edits.
4. Decode the JSON `source` string and save its exact text as UTF-8 in `tools/<source-id>/<filename>`.
   JSON escapes such as `\n` must become actual newlines; do not copy the quoted JSON string directly into the Python file.
5. In the same directory, create `module.json` by copying the record's metadata and removing `source` and `source_hash`.
   Preserve `id`, `module`, and `filename` exactly.
6. Repeat for every referenced source, including sources used by nested workflows, then restart BioImageFlow and reopen the workflow.

For example, a record with `id: "owned_custom"`, `module: "custom"`, and `filename: "custom.py"` becomes:

```text
tools/owned_custom/
  module.json
  custom.py
```

Its `module.json` contains:

```json
{"id": "owned_custom", "module": "custom", "filename": "custom.py"}
```

Keep `workflow.json`, drafts, results, and the old source records unchanged.
If no older record exists, restore the missing files from a backup or reimport an archive that contains them.

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

## A node reports a corrupt cache

A `cache_corrupt` error means the selected cached record failed an integrity check.
The workflow draft remains available for editing and saving, but BioImageFlow blocks execution through the affected branch so it cannot reuse damaged data.

Open the affected node's menu and choose **Clear cached outputs**.
BioImageFlow removes the current cache selection, moves a safely identified damaged immutable record into the cache quarantine area for diagnosis, and refreshes the node and downstream statuses.
The cleared node becomes unexecuted and can be recomputed normally.

## A managed cluster action failed

Open **Execution** and use the structured category and next action rather than looking for a managed-run log.
An `ssh-*` category means the site could not be reached and is normally retryable, `run-not-found` means the exact retained remote identity is absent, and submission uncertainty means BioImageFlow must reconnect to the same identity rather than allocate another run.
Scheduler rejection, retry conflicts, result conflicts, and cleanup-plan conflicts require correcting or confirming the reported condition before repeating the action.

The diagnostic may include sanitized run, attempt, or allocation identities that your site administrator can use for investigation.
BioImageFlow does not expose unknown remote observation fields, raw exception strings, credentials, or managed logs.

If you switched workspaces, switch back to the workspace where the run was created to see its retained history and verified downloaded result.
Confirmed remote cleanup does not remove a verified local archive that was already downloaded into that workspace.

## A viewer is unavailable

For Napari, open **Preferences → Image Viewers** and inspect the selected environment's state and package inventory.
Use **Refresh** after external package changes, **Retry** for an eligible failed managed setup, or **Locate** when a registered installation moved.
If the result chooser reports unmet requirements, select another compatible environment or create an isolated environment from the offered requirement group.
An explicit reader can still reject a file after package compatibility passes; inspect the launch error and correct the reader or rule instead of repeatedly opening other environments.
For Avivator, confirm that the image format is supported and the application can reach the external viewer.
Use the action that reveals the image in the system file manager as a fallback.

See [Keyboard Shortcuts](keyboard-shortcuts.md) for canvas and save shortcuts.
