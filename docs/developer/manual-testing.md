# Manual Platform Testing

Use this guide after the automated checks have passed to exercise the behaviors that need a real desktop application, operating-system integration, an external coding agent, or human judgment.

The lightweight plan is appropriate for an ordinary release candidate or a focused confidence check.
The complete plan is the release-level human acceptance pass.
Distributed execution and application or launcher updates are intentionally excluded for now.

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

- `workspace/`: six saved workflows under `QA/` or at the workflow root, including deterministic DataFrame-level transform and nesting examples;
- `inputs/qa-gradient.tif` and `inputs/qa-table.csv`;
- `imports/`: valid collision and nested-workflow archives, a workflow-with-results bundle, and a deliberately corrupt archive;
- `packages/qa-manual-tools.zip`: a trusted local test package;
- `exports/`: an empty destination outside the workspace for copied exports;
- `evidence/`: a place for screenshots, notes, and exported logs.

Verify fixtures only before testing because normal test actions modify the workspace.
Never use `verify` as a post-test correctness check.

Launch the application build being tested and choose the generated `workspace/` under **Edit → Preferences... → Storage → Browse...**.
Restart the application after switching if custom tools do not appear immediately.

Record the following before testing:

| Field | Value |
| --- | --- |
| Git revision or release | |
| Application mode and version | |
| Operating system | |
| Browser or desktop shell | |
| QA root | |
| Automated command and result | |
| Tester and date | |

Use these result values consistently:

- **PASS**: observed behavior matches every stated expectation.
- **FAIL**: behavior differs; record exact steps, visible errors, logs, and evidence paths.
- **BLOCKED**: an external dependency, credential, application, or environment is unavailable.
- **N/A**: the check does not apply to the tested deployment or operating system.

Do not mark a blocked check as passed.

## Lightweight test plan

Allow approximately 25–35 minutes on the primary supported operating system.
Start only after `scripts/test check app` passes on the same revision.

### L1. Desktop startup and workspace

1. Launch the packaged desktop application.
2. Open **Preferences → Storage**, use **Browse...**, and select the generated `workspace/` directory.
3. Confirm **Workflows** shows `QA Reference Workflow`, `QA Nested Child`, `QA Nested Parent`, `QA Controlled Failure`, `QA Python Authoring`, and `QA Import Collision`.
4. Quit and reopen the application.
5. Confirm the selected workspace and workflow list persist.

Pass when startup and shutdown are clean, the native chooser works, and reopening does not create or remove workflows.

### L2. Edit, save, and execute

1. Open `QA Reference Workflow`.
2. Confirm it contains **QA Numbers** connected from its DataFrame output header to positional DataFrame input 1 on **QA Increment**, rather than a `number` column connection.
3. Move and rename **QA Increment**.
4. Disable it, undo, redo, and leave it enabled.
5. Save, close, and reopen the workflow.
6. Confirm the name, position, enabled state, and connection persisted.
7. Run the workflow.
8. Confirm both nodes complete and Node Data contains three rows with incremented values `2`, `3`, and `4`.
9. Inspect the Execution and Logger panels and confirm the run and node names are understandable.

Pass when editing and persistence are exact, the run succeeds, and the results match the deterministic values.

### L3. Nested workflow

1. Open `QA Nested Parent` and confirm the complete **QA Numbers** DataFrame is connected to the thick-bordered nested node's **Numbers DataFrame** header input.
2. Open the nested node and confirm **Numbers DataFrame** targets positional DataFrame input 1 on the internal **QA Increment** node.
3. Rename the internal **QA Increment** node and save the nested tab.
4. Return to the parent and confirm it is dirty.
5. Save the parent, close it, and reopen it.
6. Confirm the nested rename persisted while the separate saved `QA Nested Child` source retained its original internal name.
7. Run the parent and confirm the nested result values are `2`, `3`, and `4`.

Pass when nested edits apply only to the embedded copy and execute through the root workflow.

### L4. Import and export

1. Export `QA Reference Workflow` using **Workflow only**.
2. Import the exported archive under a new name.
3. Confirm nodes, connection, interface output, description, and local tools remain usable.
4. Import `imports/qa-nested-parent.bioimageflow.zip` as `qa_nested_parent_imported`, confirm its parent and nested child use DataFrame-level connections, and run it to obtain `2`, `3`, and `4`.
5. Import `imports/qa_import_collision.bioimageflow.zip`.
6. When the name collision appears, use `qa_import_collision_copy` and confirm both workflows exist.
7. Attempt to import `imports/corrupt-workflow.bioimageflow.zip` and confirm a clear error appears without creating a workflow.
8. Attempt to import `imports/qa-workflow-and-results.zip` and confirm BioImageFlow explains that the bundle is not directly importable.

Pass when portable content survives the round trip and both invalid artifacts fail safely.

### L5. Custom tool and coding agent

1. In a disposable copy of `QA Reference Workflow`, create a DataFrame Tool named `QaManualEdit`.
2. Open its source in the configured editor, change its display name, save, and confirm hot reload updates the tool list.
3. Connect a supported coding client from the QA workspace.
4. Ask it to inspect and explain the active workflow without changing it.
5. Confirm it identifies the exact active workflow and accurately describes both nodes and their connection.
6. Ask it to rename one node, move it, validate the workflow, and not save it.
7. Confirm the changes appear live, the workflow remains dirty, and the agent does not edit `workflow.json` directly.
8. Review and save the change yourself.

Pass when source reload works, agent changes synchronize visibly, validation succeeds, and saving remains under human control.

### L6. Native actions and visual check

1. Use **Reveal** for the workspace, one workflow, and the latest outputs of the successful reference run.
2. Start **Export latest results to folder**, select the generated `exports/` directory, and confirm copied files appear outside the workspace.
3. Start another folder export and cancel the native chooser; confirm no error or partial destination remains.
4. Pan, zoom, connect or reconnect nodes, resize panels, and change Light, Dark, and System themes.
5. Confirm labels, dialogs, validation messages, and graph connections remain readable.

Pass when native actions target the expected paths and the interface remains usable without clipping or ambiguous feedback.

Record an overall lightweight result only when L1–L6 each have a result and every failure has evidence.

## Complete test plan

Allow several hours on the primary operating system and a shorter native smoke on every additional supported operating system.
Run `scripts/test full` and `scripts/test check docs` on the exact revision before beginning.
Prepare a fresh QA root rather than reusing the lightweight session.

### C1. Application shell, settings, and storage

- Launch, quit, restart, and confirm clean shutdown with no orphaned application process.
- Show and hide every panel from **View**, move panels, create tab groups, resize them, and confirm layout persistence after restart.
- Exercise Light, Dark, and System themes and inspect the canvas, dialogs, tables, banners, tooltips, disabled states, and error history.
- Test every documented keyboard shortcut against the active root and nested canvas, including Save, undo, redo, copy, paste, select all, delete, fit, synchronization finish, Preferences, and context-menu Escape.
- Change Node Data page size and confirm it affects newly opened tables.
- Switch to another empty existing workspace and confirm demos are not silently copied.
- Test **Install demos** and **Remove demos**, confirming unrelated workflows under `Demo/` survive.
- Use **Retest** for the latest-output view and record whether the filesystem selects links or portable pointer files.
- Configure an embedded editor and an external editor command, open a workflow-local source, and confirm the workspace root and selected file are correct.
- Configure a valid Fiji installation when available; test invalid, missing, and corrected locations.

### C2. Datasets and local input paths

- Upload the generated TIFF and CSV, create nested dataset folders, rename and move files and folders, select several items, move them together, and delete disposable copies.
- Confirm search, hierarchical selection, and snapshots remain correct after reload.
- Cancel an active upload or dropped-file operation and confirm no partial managed file remains.
- Drag one file, several files, one folder, several folders, and a mixed selection from the operating-system file manager to the canvas.
- Confirm a single folder becomes a Directory source and mixed drops use the documented immediate-file behavior.
- Exercise Files-node **Select files** and **Select folder** and confirm choosing one source clears the other.
- Rename or remove a referenced local file and confirm validation reports the unusable path without damaging the workflow.

### C3. Workflow and folder lifecycle

- Create workflows at the root and inside folders with names containing spaces, Unicode display names, and descriptions.
- Open through double-click, Enter, the toolbar, and **Workflow → Open**.
- Edit the display name without moving the workflow, then rename or drag the workflow to move its identity.
- Test alphabetical sorting and workflow-tree search.
- Test Save, Save As, Duplicate, and confirm Duplicate excludes unsaved edits and prior results while retaining saved local tools.
- For dirty close, test Cancel, Discard, and Save independently and reopen after each choice.
- Reload with accepted unsaved changes and confirm recovery behavior without confusing the draft with the saved artifact.
- Delete a non-active workflow, the active workflow, and the last workflow; confirm tabs and reload state remain correct.
- Delete an empty folder, then test Cancel, move children up, and delete children for non-empty folders.
- Confirm moves, duplicates, deletes, and delayed operations never mutate a newly created workflow that reuses an old path.

### C4. Graph editing and validation

- Add Processing Tool, DataFrame Tool, and Files nodes by click, drag, and file drop.
- Rename, move, collapse, enable, disable, multi-select, copy, paste, delete, undo, and redo nodes and edges.
- Exercise text, integer, float, Boolean, choice, nullable, file, folder, list, and connectable controls where available.
- Reset a parameter to its default and set a nullable parameter to null.
- Add and remove input pins, expose workflow inputs and outputs, rename public ports, and configure distinct output templates.
- Apply valid resource overrides and confirm invalid minimum, grammar, or concurrency values are rejected.
- Connect compatible field and DataFrame edges and confirm incompatible connections and cycles are rejected. In particular, feed a `DataFrameTool` through its positional header input; its declared scalar `Inputs` are constant parameters and must not be used to carry an upstream column.
- Confirm node, field, global, and nested-path validation messages navigate to the correct item.
- Save and reload, then compare every node, edge, parameter, interface port, position, resource, output template, and enabled state.

### C5. Nested workflows and provenance

- Group one node and several connected nodes, confirming outside connections become stable workflow interface ports.
- Drag `QA Nested Child` into a new parent and confirm its saved graph, interface, source provenance, and local tools are copied.
- Edit an embedded copy and confirm the saved source does not change.
- Rename a public port and confirm compatible parent edges survive.
- Remove or incompatibly change a connected port and test Cancel and Confirm in the destructive-effect dialog.
- Change the saved source and test **Open source workflow**, **Update from source** preview/apply, and **Detach from source**.
- Move and delete the saved source and confirm the embedded snapshot remains unchanged and executable.
- Attempt direct and indirect self-containment and confirm both are rejected.
- Open a nested editor, change the parent elsewhere, and confirm stale apply is rejected without partial mutation.
- Confirm nested tabs cannot run directly and nested execution, cache, logs, errors, and results remain attributed under the root path.

### C6. Tools, packages, and environments

- Search tools by name, tag, and category and inspect documentation, package, version, type, inputs, outputs, resources, and capabilities.
- Install `packages/qa-manual-tools.zip` through **Install tool package**, add **QA Packaged Numbers**, run it, and verify rows `1`, `2`, and `3`.
- Re-import the same package/version and confirm the documented no-op or conflict behavior is clear.
- Start and stop its environment where controls apply and confirm environment controls are unavailable during execution.
- Select another installed version of a disposable package and review the affected-node confirmation before applying.
- Export a workflow using **QA Packaged Numbers**, uninstall the package, and re-import the workflow to create the missing-package case.
- Confirm the missing node remains visible, execution is blocked, and installed alternatives are offered only when compatible.
- Reinstall the package and confirm the workflow becomes valid again.
- Create one Processing Tool and one DataFrame Tool, complete their generated source, save, and confirm hot reload.
- Change tool metadata and confirm existing nodes are marked out of date and can be rebuilt.
- Rename each custom tool and confirm nodes and source paths follow safely.
- Attempt deletion while saved workflows use the tool, inspect the affected-workflow warning, then remove dependencies and delete it.
- Duplicate, nest, export, and import workflows using local tools and confirm their source remains usable.
- Review custom and imported source before execution and confirm no credentials are stored in it.

If installing the local package is blocked by build-environment downloads, record **BLOCKED** with the installer output; do not substitute an arbitrary untrusted package.

### C7. Python authoring

- Open `QA Python Authoring`, review `workflow.py`, and save the current canvas.
- Choose **Build from Python source**, inspect the replacement summary, and cancel once.
- Repeat and confirm; verify the graph is rebuilt, validated, saved, and titled `QA Python Built`.
- Change the generated canvas and confirm opening, running, copying, nesting, and exporting do not re-import `workflow.py`.
- Introduce a syntax error in a disposable copy, confirm a clear build failure leaves the accepted graph unchanged, then restore the source.
- Attempt a symlink or import escaping the workflow directory and confirm it is rejected.

### C8. Execution, cache, logs, and results

- Run `QA Reference Workflow` completely and by selected target, confirming required dependencies run.
- Stop a running disposable workflow and wait for the final cancelled state.
- Run `QA Controlled Failure` and confirm **QA Numbers** first supplies its complete DataFrame, then the exact `Intentional manual QA failure` node error appears once in the canvas, error history, Logger, and Execution panels.
- Select error text in canvas banners, notifications, dialogs, and error history, copy it, and confirm specific server detail and validation field locations are preserved instead of only a generic HTTP status.
- In a disposable copy of `QA Reference Workflow`, delete **QA Increment** and confirm **Incremented number** is removed from the workflow outputs with it. Undo once and confirm the node and output return together, redo the deletion, then move another node and save successfully without a queued 422 error.
- Retry the failed execution and confirm successful upstream work is reused and the original target set is retained.
- Use **Invalidate Failed Nodes and Retry** and verify failed/downstream selection is recomputed without deleting retained records.
- Fix the controlled failure in a disposable copy, rerun, and confirm success.
- Use **Recompute Workflow** and confirm every enabled node runs while disabled nodes remain untouched.
- Inspect current and previous executions, nested node hierarchy, progress, duration, logs, node status, and cancellation feedback.
- Select one and several completed nodes, inspect combined and separate tables, filter columns, paginate, and change page size.
- Confirm the deterministic reference values are `1–3` and `2–4` as appropriate.
- Create an image-producing pass-through tool using `qa-gradient.tif`, run it, and inspect the thumbnail and path actions.
- Reveal and copy a result path, open the image in Napari and Fiji when installed, and open a supported image in Avivator.
- Confirm viewer failures remain retryable and do not corrupt execution results.

### C9. Import, export, and output portability

- Export **Workflow only**, import it under another name, and compare graph, interfaces, nested content, metadata, and local source.
- Export **Latest results** after overlapping complete, selected, failed, and successful runs; confirm the copied files reflect the latest successful value independently per node.
- Export **Workflow with results**, inspect its manifest, confirm all outputs belong to one successful run, and verify the recorded workflow hash.
- Attempt direct import of that bundle and confirm rejection, then extract and import the archive under `workflow/`.
- Export latest results to the generated `exports/` directory, confirm independent regular files, test destination collision, Cancel, and authorized replacement.
- Confirm folder export rejects workspace, workflow, results, home, root, symlinked, missing, and non-directory destinations.
- Import the provided collision, nested, corrupt, and result-bundle fixtures and confirm the expected success, rename, or error behavior.
- Test spaces and Unicode in imported display names and collision overrides.
- Confirm **Open latest outputs** is clearly a disposable mixed-run view rather than a portable backup.
- Delete the source workflow and verify previously exported copied artifacts remain usable.

### C10. Coding-agent integration

- Reveal and open the QA workspace in VS Code and confirm `.codex/config.toml`, `opencode.json`, `.mcp.json`, `AGENTS.md`, and active connection state are present.
- Start one supported coding client from the workspace root.
- Ask it to inspect the active workflow without changes and judge the accuracy and scientific usefulness of its explanation.
- Ask it to list and describe tools before adding a node, then create, configure, connect, rename, move, enable, disable, and remove disposable nodes.
- Expose and remove workflow inputs and outputs and confirm stable IDs preserve compatible connections.
- Create, duplicate, rename, activate, and delete disposable workflows; confirm exact deletion confirmation and active-workflow protection.
- Validate, run fully, run selected nodes, poll status, and stop an execution.
- Edit the canvas while the agent works and confirm stale revision rejection and re-read behavior.
- Exercise **Apply agent changes**, **Keep my canvas**, and **Save agent version as copy** with separate disposable conflicts.
- Ask for import, export, Save, package installation, retry, and recompute; confirm the agent explains unsupported MCP operations and returns control rather than editing saved files or calling hidden APIs.
- Review every agent-authored graph before saving and record whether its proposal is scientifically sensible separately from protocol correctness.

### C11. OMERO and operating-system integrations

- Add, edit, duplicate, and remove OMERO records; test duplicate names, invalid ports, missing fields, password replacement, and removal confirmation.
- Confirm passwords use the operating-system credential service and are never displayed or written into settings, workflows, logs, screenshots, or exports.
- With a disposable real OMERO account, authenticate and exercise one supported tool; otherwise record the live portion as **BLOCKED**.
- Test native file, multi-file, folder, workspace, export-destination, and cancellation dialogs.
- Test physical filesystem drag-and-drop, Reveal actions, clipboard path copying, external links, and external editor focus.
- Test Napari startup, reuse, failure recovery, and application shutdown.
- Test valid and invalid Fiji configuration and image opening.
- Confirm application focus, menu conventions, keyboard behavior, window title, and shutdown are appropriate for the operating system.

### C12. Cross-platform signoff and cleanup

- On each additional supported operating system, repeat startup/shutdown, workspace selection, one physical drop, Save/reopen, one local execution, one export/import, one coding-agent synchronization, one native Reveal, and one viewer launch.
- Record **PASS**, **FAIL**, **BLOCKED**, or **N/A** for every C1–C12 group, with evidence for failures and blockers.
- Preserve a failing QA root until diagnosis is complete.
- After a successful session or after evidence is copied elsewhere, remove the generated root with:

```bash
scripts/manual-qa clean --root /absolute/path/bioimageflow-manual-qa
```

The cleanup command must refuse any directory without the exact generator marker.

The complete acceptance result is PASS only when all required automated commands pass, every applicable manual group passes, and every external blocker is explicitly accepted by the release owner.
