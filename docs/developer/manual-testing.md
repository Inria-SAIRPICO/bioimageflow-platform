# Manual Platform Testing

Use this guide after the automated checks have passed to exercise behaviors that need a real desktop application, operating-system integration, an external coding agent, or human judgment.

The lightweight plan targets the packaged desktop application and is appropriate for an ordinary release candidate or a focused confidence check.
The complete plan is the release-level human acceptance pass, with a separate browser session for managed datasets.
Distributed execution and application or launcher updates are intentionally excluded for now.

Bold text identifies visible labels or icon tooltips.
Open preferences through **Edit → Preferences...**, and reopen hidden panels through **View**; that menu calls the tool and workflow panels **Tools Panel** and **Workflows Panel**.
“File manager” means Finder on macOS, Explorer on Windows, or the desktop file browser on Linux; a reveal action may select the target in its parent folder rather than open the target folder.
Use **Local** in the execution-target selector for all runs in this guide.
Wait for canvas synchronization before Save or Run; Ctrl/Cmd+Enter finishes pending synchronization.

Keep the supplied workflows available for later groups.
For destructive experiments, select the saved fixture in **Workflows**, click **Duplicate workflow**, and open the new copy before editing it.
If that duplicate's name already exists, open a clean fixture and use **Workflow → Save As** with a unique **Name**, then click **Save copy**.
Record the copy's name in the evidence.
Creating a tool adds it to the Tools list; it does not add a node until you click the tool row or drag it onto the canvas.

## Prepare a disposable QA environment

Install the pinned development dependencies first:

```bash
cd backend
uv sync --group dev --frozen
cd ../frontend
bun install --frozen-lockfile
cd ..
```

Choose an absolute path outside the repository and your normal BioImageFlow workspace, then prepare and verify it:

```bash
scripts/manual-qa prepare --root /absolute/path/bioimageflow-manual-qa
scripts/manual-qa verify --root /absolute/path/bioimageflow-manual-qa
```

The command refuses relative paths, paths overlapping the repository, the home or filesystem root itself and their ancestors, non-empty unmarked directories, and modified fixture roots.
Running `prepare` again without changing the generated files is safe and reports that the root is already prepared.

The root contains:

- `workspace/`: the workspace root, with six saved workflows in `workspace/workflows/`, under `QA/` or at the workflow-tree root;
- `inputs/qa-gradient.tif` and `inputs/qa-table.csv`;
- `imports/`: valid collision and nested-workflow archives, a workflow-with-results bundle, and a deliberately corrupt archive;
- `packages/qa-manual-tools.zip`: a trusted local test package;
- `exports/`: an empty destination outside the workspace for copied exports;
- `evidence/`: a place for screenshots, notes, and exported logs.

Verify fixtures only before testing because normal test actions modify the workspace.
Never use `verify` as a post-test correctness check.

Launch the application build being tested and choose the generated `workspace/` under **Edit → Preferences... → Storage → Browse...**.
Expand **QA** in **Workflows** to see its five fixtures; **QA Import Collision** is at the tree root.
The reference workflow lives at `workspace/workflows/QA/Reference Workflow/`.
Its node titles are `QaNumbers` and `QaIncrement`; their tool display names in **Tools** are **QA Numbers** and **QA Increment**.
The failure fixture contains `QaNumbers` and `QaFail`, and the parent fixture contains `QaNumbers` and `Nested Child`.
Restart the application after switching if custom tools do not appear immediately, and record if a restart was needed.

For the complete plan, also prepare disposable input copies, a folder containing both immediate files and a nested subfolder, and a sufficiently large file to keep an upload active long enough to cancel.
The generated 32 × 32 TIFF and three-row workflows are too small for reliable cancellation, pagination, or long-content checks.
Use disposable custom tools to prepare those cases, and record any extra source or input used.

Record the following before testing:

| Field | Value |
| --- | --- |
| Git revision or release | |
| Application mode and version | |
| Operating system | |
| Browser or desktop shell | |
| QA root | |
| Automated command, result, duration, and revision | |
| Tester and date | |

Use these result values consistently:

- **PASS**: observed behavior matches every stated expectation.
- **FAIL**: behavior differs; record exact steps, visible errors, logs, and evidence paths.
- **BLOCKED**: an external dependency, credential, application, or environment is unavailable.
- **N/A**: the check does not apply to the tested deployment or operating system.

Do not mark a blocked check as passed.
Record individual exceptions within a group rather than hiding them in a group-level PASS.

## Lightweight test plan

Allow approximately 25–35 minutes on the primary supported operating system, excluding dependency and editor/client setup.
Start only after `scripts/test check app` passes on the same revision.

### L1. Desktop startup and workspace

1. Launch the packaged desktop application.
2. Open **Edit → Preferences... → Storage**, use **Browse...** next to **Workspace path**, and select the generated `workspace/` directory.
3. Expand **QA** in **Workflows** and confirm `QA Reference Workflow`, `QA Nested Child`, `QA Nested Parent`, `QA Controlled Failure`, and `QA Python Authoring` are present, with `QA Import Collision` at the tree root.
4. Quit and reopen the application.
5. Confirm the selected workspace and workflow list persist.

Pass when startup and shutdown are clean, the native chooser works, and reopening does not create or remove workflows.

### L2. Edit, save, and execute

1. In **Workflows**, double-click `QA Reference Workflow`.
2. Confirm `QaNumbers` sends its whole **DataFrame** through the header connection to the positional input labelled **1** on `QaIncrement`.
3. Move `QaIncrement`, then right-click it and choose **Rename**; use `QA Increment edited`.
4. Right-click it and choose **Disable**, use **Edit → Undo**, then **Edit → Redo**, and finally right-click it and choose **Enable**.
5. Choose **Workflow → Save**, close its canvas tab, and reopen the workflow.
6. Confirm the name, position, enabled state, and connection persisted.
7. Click **Run Workflow**.
8. Confirm both nodes complete, select `QA Increment edited`, and open **View → Node Data**; its `number_plus_one` column must contain `2`, `3`, and `4`.
9. Open **View → Execution** and **View → Logger** and confirm the run and node names are understandable.

Pass when editing and persistence are exact, the run succeeds, and the results match the deterministic values.

### L3. Nested workflow

1. Open `QA Nested Parent` and confirm `QaNumbers` sends its whole DataFrame to the **Numbers DataFrame** header input on the thick-bordered `Nested Child` node.
2. Double-click `Nested Child`, select its `QaIncrement` node, and inspect **Nodes → Parameters → Published DataFrame inputs**; **Numbers DataFrame** must target **DataFrame 1**.
3. Rename the internal `QaIncrement` node and choose **Workflow → Save** while the nested tab is active.
4. Return to the parent tab and confirm it is dirty.
5. Save the parent, close its nested and root tabs, and reopen it.
6. Reopen `Nested Child` and confirm the nested rename persisted; separately open saved `QA Nested Child` and confirm its node is still named `QaIncrement`.
7. Activate the parent tab, click **Run Workflow**, select `Nested Child`, and confirm **Node Data** shows `2`, `3`, and `4` in **Incremented number**.

Pass when nested edits apply only to the embedded copy and execute through the root workflow.

### L4. Import and export

1. Activate the root tab for `QA Reference Workflow`, choose **Workflow → Export**, and click **Workflow only**.
2. Choose **Workflow → Import** and select the downloaded archive.
   If **Rename imported workflow** appears, enter an unused **Name** and click **Import**; otherwise the import uses the archive's name.
   Identify the new entry before opening it; its display name may match the original.
3. Confirm the nodes, connection, **Incremented number** output, description, and local tools survive the round trip; run the imported workflow and compare its results with L2.
4. Use **Workflow → Import** for `imports/qa-nested-parent.bioimageflow.zip`; if prompted for a collision name, use `qa_nested_parent_imported`.
   Inspect the parent's whole-DataFrame connection and the child's published **Numbers DataFrame** input, then run the imported parent and inspect its nested output for `2`, `3`, and `4`.
5. Import `imports/qa_import_collision.bioimageflow.zip`.
6. In **Rename imported workflow**, enter `qa_import_collision_copy` in **Name**, click **Import**, and confirm both workflow entries exist.
7. Attempt to import `imports/corrupt-workflow.bioimageflow.zip` and confirm a clear error appears without creating a workflow.
8. Attempt to import `imports/qa-workflow-and-results.zip` and confirm BioImageFlow explains that the bundle is not directly importable.

Pass when portable content survives the round trip and both invalid artifacts fail safely.

### L5. Custom tool and coding agent

1. Open a disposable copy of `QA Reference Workflow`, then click **Create Tool** in **Tools**, enter `QaManualEdit` in **Name**, select **DataFrame Tool** in **Type**, and click **Create**.
2. Creation opens its source in the configured editor; **Open tool script** beside its Tools entry reopens it.
   Change the Python class's `display_name` string, save the source file in the editor, and confirm the Tools entry updates.
   Leave the tool off the canvas so the reference graph still has two nodes.
3. Follow [Prepare the workspace and choose a coding client](../user/coding-agent.md) to start a supported client from the generated workspace root, with the disposable reference copy active in BioImageFlow.
4. Ask it to use the BioImageFlow MCP server to inspect and explain the active workflow without changing it.
5. Confirm it identifies the exact active workflow and accurately describes both nodes and their connection.
6. Ask it to rename one node, move it, validate the workflow, and not save it.
7. Confirm the changes appear live, the workflow remains dirty, and the agent does not edit `workflow.json` directly.
8. Review and choose **Workflow → Save** yourself.

Pass when source reload works, agent changes synchronize visibly, validation succeeds, and saving remains under human control.

### L6. Native actions and visual check

1. Open **Edit → Preferences... → Storage**, click **Reveal** next to **Workspace path**, and confirm the file manager reveals the generated `workspace/` folder.
2. Select the original `QA Reference Workflow` in **Workflows**, click **Open latest outputs** beside **Latest outputs** in its details, and confirm the file manager reveals `workspace/workflows/QA/Reference Workflow/results/outputs/latest`.
   Inspect the latest successful per-node outputs; this view can combine different runs and is not an independent backup.
3. With that workflow's root tab active, choose **Workflow → Export → Export latest results to folder**, select the generated `exports/` directory as the parent, and wait for **Latest results exported**.
   Click **Show in folder** and inspect the reported child directory: it must contain copied files outside the workspace.
4. Click **Export latest results to folder** again and cancel the native chooser; confirm no error or new partial export appears and the previous export remains intact.
5. On a disposable workflow, pan by dragging empty canvas space, zoom with the mouse wheel, disconnect and reconnect the DataFrame edge, and resize panels.
   Use the theme button beside the run controls to choose **Light**, **Dark**, and **System**.
6. Confirm labels, dialogs, validation messages, and graph connections remain readable.

Pass when native actions target the expected paths and the interface remains usable without clipping or ambiguous feedback.

Record an overall lightweight result only when L1–L6 each have a result and every failure has evidence.

## Complete test plan

Allow several hours on the primary operating system and a shorter native smoke on every additional supported operating system.
Run `scripts/test full` and `scripts/test check docs` on the exact revision before beginning.
Prepare a fresh QA root rather than reusing the lightweight session.
Groups refer to the original fixture names; use disposable copies for changes that later groups must not inherit.
C4 may use tools prepared in C6, and C1's table checks may use the larger results prepared in C8.

### C1. Application shell, settings, and storage

- Launch, quit, restart, and confirm clean shutdown with no orphaned application process.
- Show and hide every available panel from **View**, move panels, create tab groups, resize them, and confirm layout persistence after restart.
- Use the theme button beside the run controls to select **Light**, **Dark**, and **System**; inspect the canvas, dialogs, tables, banners, tooltips, disabled states, and the menu-bar **Error history** / **Errors (n)** indicator.
- Exercise each shortcut in [Keyboard Shortcuts](../user/keyboard-shortcuts.md) with the root canvas active, then with a nested canvas active; move focus out of text fields first.
  For Escape, open a node context menu before pressing the key.
- In **Edit → Preferences... → Display**, change **Node Data rows per page** and confirm the value is used in a newly opened result table with enough rows to paginate.
- In **Storage**, use **Browse...** to switch to a separately prepared empty existing workspace, confirm demos are not silently copied, then switch back to the generated QA workspace.
- In **Storage → Example workflows**, test **Install demos** and **Remove demos**; create an unrelated disposable workflow under `Demo/` first and confirm it survives removal.
- In **Storage → Latest output view**, click **Retest** and record the reported symbolic-link or portable-pointer-file mode and any warning.
- In **External Editor**, leave the command empty to test the embedded editor, then test an installed external editor with a command such as `code {file_path}`.
  Use **Open tool script** in **Tools** or **Nodes**; confirm the embedded editor has **Workspace** and **Installed Tool Packages** roots and focuses the selected source, while the external editor follows its configured command.
- In **Image Viewers**, select a valid Fiji installation with **Browse…**, use **Clear**, and test invalid and corrected paths; confirm actionable validation feedback.

### C2. Local input paths and browser datasets

In the packaged desktop application:

- On a disposable workflow, drag one file, several files, one folder, several folders, and a mixed selection from the file manager to the canvas.
- Confirm each drop creates one **Files** node without uploading or copying the source files.
  Select it in **Nodes → Parameters**: a single folder fills **Directory**; compound drops fill **Files**, expanding each folder's immediate files without recursively including subfolders.
- On a Files node, use **Select files** for **Files** and **Select folder** for **Directory**; confirm choosing one clears the other, and cancelling either chooser preserves both values.
- Rename or remove a disposable referenced local file in the file manager, run or validate the workflow, and confirm the unusable path produces an actionable error without damaging the graph.
  Restore the file before continuing.

Quit the desktop application before starting the backend and browser session described in [Run the frontend in a browser](local-development.md#run-the-frontend-in-a-browser).
Confirm **Storage → Workspace path** still identifies the QA workspace, open a disposable workflow, and open **View → Datasets Panel**.
Record this subsection as **N/A** for a desktop-only signoff; if browser coverage is required but unavailable, record **BLOCKED**.

- Click **Upload files**, select copies of the generated TIFF and CSV, and wait for completion.
- Use **Add folder**, **Rename**, checkbox selection, and drag-and-drop within the tree to create nested folders and move individual and multiple items.
  Use **Delete**, review **Delete selected datasets**, cancel once, then confirm deletion of disposable copies.
- Use **Search files and folders** and folder checkboxes, verifying full and partial selection states.
  Select a folder and click **Create Files node**; add another dataset to that folder afterward and confirm the existing Files node retains its original resolved file list.
  Save the workflow, reload, and confirm the dataset tree and Files parameters persist; selection itself need not persist.
- Upload the prepared large disposable file, click its **Cancel** or **Cancel uploads** while it is active, and confirm no completed dataset or partial managed file remains for the cancelled upload.
  Files that completed before cancellation remain valid.
- Select a Files node and use **Select in Datasets panel**, choose dataset checkboxes, then click **Set files on “…”**, which names the selected node.
  For an individual path picker, use **Use file** or **Cancel**.

Stop the browser-session servers and return to the packaged desktop application for the remaining groups.

### C3. Workflow and folder lifecycle

- Use **Workflow → New** at the root and **New workflow** after selecting a folder in **Workflows**.
  Enter **Name** and **Description**; test names with spaces and Unicode alongside Latin letters or numbers, and inspect the generated **ID** below the name.
  The form has one name field, and names that cannot generate an ID must show validation feedback.
- Open through double-click, Enter with a workflow selected, **Open workflow** in the selected workflow details, and **Workflow → Open**.
- Click **Edit selected item** for a workflow and change its display name; confirm its directory does not move.
  Use **Edit workflow description** in the details to change the description.
  Drag the workflow into another folder to change its path; selecting a folder and using **Edit selected item** opens **Rename folder**.
- Test alphabetical sorting and **Search workflows...**.
- Test **Workflow → Save**, **Workflow → Save As → Save copy**, and **Duplicate workflow** in **Workflows**.
  Make an unsaved change before copying: Save As must include it, while Duplicate must use the saved graph and local tools and exclude prior results.
- Close a dirty root tab using its tab close control; test **Cancel**, **Discard**, and **Save** in **Save changes before closing?** on separate edits.
  Cancel keeps the tab open; reopen after Discard or Save and check the corresponding saved content.
  For a dirty nested tab, test cancelling and accepting its native discard confirmation; use **Workflow → Save** beforehand when testing application to the parent.
- Reload with synchronized unsaved changes and confirm recovery preserves the draft and dirty indicator without treating it as the saved artifact.
- Use **Delete selected item** for a non-active disposable workflow and **Workflow → Delete** for an active one; review the named deletion dialog and follow its confirmation instruction.
  In a separate scratch workspace, delete the last workflow and confirm tabs and reload state remain correct, then return to the QA workspace.
- Use **Delete selected item** for an empty folder, then test **Cancel**, **Move children up**, and **Delete all** in **Delete folder** on separate non-empty disposable folders.
- Leave a deletion confirmation open, cancel it, switch workflow tabs, and open deletion again; check that each dialog names the intended workflow.
  Delayed-response races involving deletion and recreation at the same path require automated lifecycle tests; an ordinary manual delete does not certify those races.

### C4. Graph editing and validation

- In **Tools**, click a Processing Tool row and drag a DataFrame Tool row onto the canvas; test the reverse as well.
  Add **Files** through its Tools row and through a local file drop.
  Use C6 first if the required tool types are not installed.
- Rename, move, collapse, enable, disable, and multi-select nodes; copy/paste selected nodes, and delete/undo/redo nodes and connections.
  Node actions such as Rename and Disable do not apply to edges.
- Select a tool in **Nodes → Parameters** and exercise text, integer, float, Boolean, choice, nullable, file, folder, list, and connectable controls supplied by its schema.
  The numeric reference fixtures do not provide all control types; use suitable installed tools or extend a disposable custom tool and record its source.
- Use **Reset to default** and **Set to null** on parameters that offer them; test **Set value (currently null)** to restore a value.
- Use **Add input pin** / **Remove input pin**, **Expose as workflow input** / **Remove workflow input**, and **Expose as workflow output** / **Remove workflow output** where available.
  Edit **Workflow input name** and **Workflow output name**, and configure distinct file-output templates on a Processing Tool with multiple outputs.
- In **Nodes → Resources** for a Processing Tool, enter values in the **Override** fields for **CPU cores**, **GPUs**, **Memory**, **GPU memory**, and **Maximum concurrent jobs**.
  Test valid values and invalid values the controls allow you to enter; confirm control limits or validation prevent invalid values from being used, and exercise **Reset all**.
- Connect compatible field and DataFrame edges and confirm incompatible connections and cycles are rejected.
  Feed a DataFrame Tool through its positional header input; its declared scalar inputs are constant parameters and must not carry an upstream column.
- Confirm workflow-wide validation appears above the canvas and node or field problems identify the affected item.
  Follow a nested path by double-clicking each named workflow node; do not assume every validation message is a clickable navigation link.
- Save and reload, then compare every node, edge, parameter, interface port, position, resource, output template, and enabled state.

### C5. Nested workflows and provenance

- Recreate `QA Nested Child` under a new name: add **QA Increment** from **Tools**, select its node, and in **Nodes → Parameters → Published DataFrame inputs** click **Publish DataFrame input**.
  Set **Workflow input name** to `Numbers DataFrame`, expose `number_plus_one` with **Expose as workflow output**, set **Workflow output name** to `Incremented number`, and save.
- Create a new parent workflow, add **QA Numbers**, drag the newly saved child from **Workflows** onto the canvas, and connect the source's whole **DataFrame** output to **Numbers DataFrame**.
  Run the parent, select the child node, and compare **Incremented number** with `2`, `3`, and `4`.
- On a disposable copy, use **Publish DataFrame input** several times, edit the names, click **Unpublish** on the middle row, undo/redo, and save/reload.
  Confirm surviving names and connections remain intact and **DataFrame 1**, **DataFrame 2**, etc. compact together; stable IDs can be checked in a read-only inspection of the exported workflow.
- On an unconnected embedded child, use **Nodes → Parameters → Published DataFrame inputs → Publish DataFrame input: Numbers DataFrame**.
  Confirm the parent publication targets that child port and prevents an internal edge from also connecting to it.
- Confirm source DataFrame Tools such as **QA Numbers** have no **Publish DataFrame input** action, and publication controls are disabled while execution locks editing.
- Select one tool node and then several connected tool nodes in separate trials; right-click and choose **Group into workflow**.
  Confirm connections across the group boundary become workflow interface ports.
- Drag saved `QA Nested Child` into a new parent and confirm its saved graph, interface, source provenance, and local tools are copied.
  Edit the embedded copy and confirm the saved source does not change.
- Rename a public port in a nested editor, save to the parent, and confirm compatible parent edges survive.
- Close the nested editor, right-click the embedded node, and choose **Open source workflow**.
  In the source, remove a port connected by the parent, then save; return to the parent and choose **Update from source**.
  Review the native replacement confirmation, cancel once and confirm the parent is unchanged, then repeat and accept; confirm affected connections are removed together with the replaced interface.
- On another copy, test **Detach from source** from the embedded node's context menu; confirm the embedded graph remains intact and the three source actions disappear.
- Move and delete a disposable saved source and confirm the embedded snapshot remains unchanged and executable.
- Try dragging a saved workflow into itself, then try embedding a parent inside its saved child; confirm direct and indirect containment cycles are rejected.
- Open a nested editor and edit it, return to the parent and change the same workflow node, then attempt **Workflow → Save** from the nested tab.
  If the parent change invalidates the snapshot, confirm a conflict leaves the parent intact; changing an unrelated parent node is not necessarily a conflict.
- Confirm run actions are disabled while a nested tab is active; run from the root and inspect nested job paths, errors, logs, and results under that root execution.

### C6. Tools, packages, and environments

- Use **Search tools...** for names and tags and browse category groups; click **Tool information** for documentation.
  Inspect package/version information in **Manage tools**, and input, output, resource, and execution information in **Nodes** after adding a node.
- Click **Manage tools** in **Tools**; in the **Install tool package** area, click **Select .zip archive**, choose `packages/qa-manual-tools.zip`, then click **Install**.
  Close the dialog, add **QA Packaged Numbers** to a disposable workflow, run it, select it, and verify `1`, `2`, and `3` in **Node Data**.
- Reinstall the same archive and confirm the outcome is clear and does not create duplicate package/version entries.
- Use the environment status/action icon beside a tool that offers it to start and stop its environment; confirm it is disabled during a sufficiently long execution.
  The package fixture is a DataFrame source, so use a Processing Tool if it has no environment action.
- In **Manage Tools**, expand a package's version list and click **Set current** on another installed version.
  Review **Change Package Version**, test **Cancel**, then **Set current**; the confirmation applies to every node from that package.
  The generated package supplies only one version, so prepare another trusted version or record this case as **BLOCKED**.
- Export a workflow using **QA Packaged Numbers**, use **Uninstall** on the package's version row, and re-import the workflow to create the missing-package case.
  Inspect **Workflow dependencies**; the missing node must remain visible and execution must be blocked.
  **Use installed alternatives…** requires a suitable installed version; reinstall the local package through **Select .zip archive** and **Install** to recover.
- Use **Create Tool** for one **Processing Tool** and one **DataFrame Tool**, review their generated source, save edits, and confirm hot reload.
  Add the Processing Tool with a valid input image; connect **QA Numbers** to the DataFrame Tool's positional input before running its generated pass-through implementation.
- Execute a custom tool, then change its implementation or execution-relevant schema and save the source.
  Confirm hot reload updates validation/cache status; when **Rebuild nodes before running?** appears on Run, test **Cancel**, then **Continue** and check fresh results.
  A display-name-only change need not invalidate cached computation.
- Use **Rename tool** beside each custom tool; confirm its nodes and source paths follow safely.
- Click **Delete tool** while saved disposable workflows reference it, inspect **Delete Custom Tool** and its affected-workflow list, then choose **Cancel**.
  Remove and save those dependencies before confirming **Delete**; the warning is not a promise that deletion is prohibited.
- Duplicate, nest, export, and import workflows using local tools and confirm their source remains usable.
- Review custom and imported source before execution and confirm no credentials are stored in it.

If installing the local package is blocked by build-environment downloads, record **BLOCKED** with the installer output; do not substitute an arbitrary untrusted package.

### C7. Python authoring

- Open `QA Python Authoring`, use the workspace **Reveal** action and your editor to review `workspace/workflows/QA/Python Authoring/workflow.py`, and save the current canvas with **Workflow → Save**.
- Choose **Workflow → Build from Python source**, inspect the native replacement summary, and cancel once.
- Repeat and accept; verify the graph is saved with display name `QA Python Built`.
  This fixture deliberately builds an empty graph, so an empty canvas is expected.
- Add a node to the generated canvas and save; reopen, run with valid inputs, duplicate, nest, and export it, confirming those actions preserve the materialized graph instead of rebuilding the empty Python definition.
- Back up this disposable fixture's `workflow.py` outside its workflow directory, introduce a syntax error, and choose **Workflow → Build from Python source**.
  Confirm the failure leaves the accepted graph unchanged, then restore the source.
- Replace this fixture's `workflow.py` temporarily with a symbolic link to the backed-up file outside its workflow directory and repeat the build; confirm rejection, then restore the regular source file.
  This checks the authoring-source path boundary; ordinary imports of installed Python packages are supported.

### C8. Execution, cache, logs, and results

- Open `QA Reference Workflow`, use **Run Workflow**, then select `QaIncrement` and use **Run Selected**; confirm required upstream work is available, with cached work reused when valid.
- Prepare a disposable custom tool with a delay long enough to click **Stop** while it runs; use **Execution → Stop** and wait for the final cancelled state.
  Record which jobs completed before cancellation; if the whole run finishes before Stop is accepted, increase the delay and repeat.
- Run `QA Controlled Failure` and confirm `QaNumbers` first supplies its complete DataFrame, then `QaFail` reports `Intentional manual QA failure`.
  Inspect the canvas error, menu-bar error history, **Logger**, and the failed job's diagnostic in **Execution**.
  Confirm the detail is preserved and the same event is not duplicated within error history; Logger may also contain lifecycle messages and a traceback.
- Select error text in canvas banners, notifications, dialogs, and error history, copy it, and confirm specific server details and validation field locations are preserved instead of only a generic HTTP status.
- In a disposable copy of `QA Reference Workflow`, delete `QaIncrement` and confirm **Incremented number** is removed from the workflow outputs with it.
  Undo once and confirm the node and output return together, redo the deletion, then move `QaNumbers` and save successfully without a queued validation error.
  Inspect public outputs on the restored node or in a read-only exported workflow; there is no separate workflow-interface panel.
- Return to the failed `QA Controlled Failure` run and use **Execution → Retry Failed Execution**; confirm successful upstream work is reused and the original target set is retained.
- Use **Execution → Invalidate Failed Nodes and Retry…**, review any confirmation, and verify failed/downstream work is recomputed without deleting retained run records.
- In a disposable copy of `QA Controlled Failure`, create a DataFrame Tool named `QaRecovered` and keep its generated pass-through `transform` implementation.
  Delete `QaFail`, add the new tool, connect `QaNumbers` to its positional header input, save, run, and confirm success without editing the original failure tool's source.
- On a successful disposable workflow, disable one node, use **Execution → Recompute Workflow…**, and confirm enabled work reruns while the disabled node remains untouched.
- In **View → Execution**, use **Workflow** and **Workspace** scopes, select current and earlier runs in the history, and inspect job status, progress, and duration.
  Select a job to inspect its scoped nested path and use **Canvas** and **Logs**; confirm cancellation feedback is understandable.
- Select one and several completed nodes in **Node Data**, vary **Upstream levels**, use a column's filter icon (for example, **Filter number**) followed by **Apply**, and test pagination/page size with a larger result.
  Compatible results combine automatically; unrelated or incompatible projections fall back to separate tables with an explanation, rather than a manual combined/separate switch.
  To exercise that fallback, prepare two source results with incompatible row indices, run both, and select them together.
  Two independent sources with identical indices may still combine.
- In combined and separate tables, use results with long headers, narrow numeric columns, paths, and thumbnails; sort/filter controls must never overlap text.
  Check visible resize separators in light and dark themes, drag and keyboard resizing, double-click/Enter auto-sizing, and **Reset column widths**.
  Confirm narrow panels scroll horizontally, neighboring columns do not resize, and manual widths survive reload without leaking into another workflow.
  Hide **Node Data** while loading results, reopen it, and verify the column widths remain usable; use automated table-sizing tests for the underlying hidden-measurement persistence invariant.
- Confirm `number` contains `1`, `2`, and `3`, and `number_plus_one` contains `2`, `3`, and `4` in the reference results.
- In a disposable workflow, click **Create Tool** in **Tools**, create `QaImageCopy` with **Type → Processing Tool**, and retain its generated pass-through implementation.
  Add its Tools entry to the canvas, set **Input image** to the generated `inputs/qa-gradient.tif` with **Select file**, run, and select the node to inspect its output thumbnail in **Node Data**.
- Beside the output image, test **Reveal in file browser**, **Copy path**, **Open in Napari**, and **Open in Fiji**.
  Before Fiji is configured, that action is **Configure Fiji** and must open its preference section.
  Test **Open in Avivator** with an image that viewer supports; record unavailable viewers or unsupported fixture coverage as **BLOCKED** rather than passing an untested launch.
- Confirm viewer failures provide useful feedback, can be retried after correcting the configuration or input, and do not corrupt execution results.

### C9. Import, export, and output portability

- Choose **Workflow → Export → Workflow only**, import the archive with **Workflow → Import**, resolve a name collision if prompted, and compare graph, interfaces, nested content, metadata, and local source.
- On a disposable workflow with two independent branches, complete a run, change one branch and use **Run Selected**, then make that branch fail on another attempt.
  Choose **Workflow → Export → Latest results** and confirm it contains each node's latest successful output, including successful values from different runs; these runs occur sequentially, not concurrently.
- Choose **Workflow → Export → Workflow with results**, unzip it, and inspect `bioimageflow-results-bundle.json`.
  Confirm `results.run_id` identifies one successful run and `results.path` identifies its copied outputs; compute the SHA-256 of the nested archive at `workflow.archive` and compare it with `workflow.sha256`.
  This is the archive file's checksum, not a graph artifact hash.
- Attempt direct import of that bundle and confirm rejection, then extract and import the archive under `workflow/`.
- Choose **Export latest results to folder**, select `exports/` as the parent, and use **Show in folder** to inspect the reported child directory and `.bioimageflow-output-export.json` marker.
  Confirm output files are independent regular copies.
  Export the same workflow to the same parent again, cancel the native replacement confirmation, and verify the previous export is intact; repeat and accept replacement.
- In the folder chooser, select the workspace, a workflow directory, its results directory, the home folder, and the filesystem root in separate attempts; confirm rejection without an export.
  Native choosers may resolve symlinks or prevent selecting missing paths and regular files; use automated export tests for those raw-path rejection cases.
- Import the provided collision, nested, corrupt, and result-bundle fixtures and check the outcomes described in L4.
- Test spaces and Unicode in **Rename imported workflow → Name** when a collision occurs, and edit the imported display name separately with **Edit selected item**.
  A first import without a collision does not offer a rename form.
- Select the workflow in **Workflows** and click **Open latest outputs**; compare its per-node results with the mixed-run export and the single-run bundle.
  Check the per-node explanation under **Latest outputs** and the storage/export explanatory text; do not expect a separate backup warning dialog.
- Delete a disposable source workflow and verify its previously exported copied artifacts remain usable.

### C10. Coding-agent integration

- Use **Edit → Preferences... → Storage → Reveal**, open the workspace folder in VS Code, and show hidden files.
  Confirm `.codex/config.toml`, `opencode.json`, `.mcp.json`, `AGENTS.md`, and `.bioimageflow/agent-state.json` are present; keep BioImageFlow running with the intended saved workflow active.
- Follow [Choose a coding client](../user/coding-agent.md#choose-a-coding-client) to start one supported client from the workspace root.
- Ask it to inspect the active workflow through BioImageFlow MCP without changes and judge the accuracy and scientific usefulness of its explanation.
- Ask it to list and describe tools before adding a node, then create, configure, connect, rename, move, enable, disable, and remove disposable nodes.
- Expose and remove workflow inputs and outputs and confirm stable IDs preserve compatible connections.
- Create, duplicate, rename, activate, and delete disposable workflows; confirm exact deletion confirmation and active-workflow protection.
- Validate, run fully, run selected nodes, poll status, and stop a sufficiently long execution.
- Edit the canvas while the agent works and confirm stale revision rejection and re-read behavior when the agent submits against the older revision.
- If simultaneous edits produce the canvas/agent conflict banner, exercise **Apply agent changes**, **Keep my canvas**, and **Save agent version as copy** on separate conflicts.
  These controls appear only for a conflict, not for every agent edit; record an untriggered race case as untested and retain the automated conflict-test evidence.
- Ask for import, export, Save, package installation, retry, and recompute; confirm the agent explains unsupported MCP operations and returns control rather than editing saved files or calling hidden APIs.
- Review every agent-authored graph before saving and record whether its proposal is scientifically sensible separately from protocol correctness.

### C11. OMERO and operating-system integrations

- Open **Edit → Preferences... → OMERO**, click **Add instance**, fill **Name**, **Host**, **Port**, **Username**, and **Password**, then click that card's **Save**.
  Test **Duplicate** with a new unique name and password, edit/save, and **Remove** with its confirmation.
  Test duplicate names, missing fields, password replacement, and the Port control's `1–65535` bounds.
- After saving, confirm the password input is cleared and the card reports **Stored**; reopening preferences must not retrieve the saved secret into the field.
  The eye control can reveal a password currently being typed, so use disposable credentials and omit them from screenshots.
  Verify saved secrets are absent from settings, workflow files, logs, and exports; credential-store behavior is also covered by automated integration tests.
- With a disposable real OMERO account and a supporting tool package, choose the saved connection in that tool and run it; there is no standalone OMERO login/test button in Preferences.
  Otherwise record the live portion as **BLOCKED**.
- Test native single-file and multi-file selection from **Nodes**, folder selection from **Directory**, workspace selection from **Storage → Browse...**, and export-parent selection from **Export latest results to folder**, including cancellation of each chooser.
- Repeat physical filesystem drag-and-drop, the workspace **Reveal** and workflow **Open latest outputs** actions, result **Copy path**, external links, and **Open tool script** with the external editor configured.
- Test **Open in Napari** startup, reuse, failure recovery, and application shutdown.
- Test **Configure Fiji** / **Open in Fiji** with missing, invalid, and corrected configuration.
- Confirm application focus, menu conventions, keyboard behavior, window title, and shutdown are appropriate for the operating system.

### C12. Cross-platform signoff and cleanup

- On each additional supported operating system, repeat startup/shutdown, workspace selection, one physical drop, Save/reopen, one local execution, one export/import, one coding-agent synchronization, one native Reveal, and one viewer launch.
- Record **PASS**, **FAIL**, **BLOCKED**, or **N/A** for every C1–C12 group, with evidence for failures, blockers, and any untested cases.
- Preserve a failing QA root until diagnosis is complete.
- Before cleanup, stop executions and coding clients, close editors using the QA root, and switch BioImageFlow back to your normal workspace or quit it.
- After a successful session or after evidence is copied elsewhere, remove the generated root with:

```bash
scripts/manual-qa clean --root /absolute/path/bioimageflow-manual-qa
```

The cleanup command must refuse any directory without the exact generator marker.
The separately prepared scratch workspace and browser-session data require their own cleanup.

The complete acceptance result is PASS only when all required automated commands pass, every applicable manual group passes, and the release owner explicitly accepts any external blocker or untested case.
