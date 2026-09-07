# Run Workflows and Inspect Results

BioImageFlow validates the active saved workflow before every run.
You can run the whole workflow, run selected nodes, or retry failed work.

## Choose what to run

Use the arrow beside **Run Workflow** or open **Execution**:

- **Run Workflow** runs every enabled step that is needed.
- **Run Selected** runs selected nodes and the dependencies they need.
- **Retry Failed Execution** repeats the targets from the failed run and reuses successful work.
- **Invalidate Failed Nodes and Retry...** forces failed nodes and their downstream work to run again.
- **Recompute Workflow...** forces every enabled node to run again.
- **Stop** requests cancellation of the active run.

If a tool changed after a node was added, BioImageFlow lists the out-of-date nodes and asks whether to rebuild them before running.

## Follow execution

The execution banner reports overall progress.
Nodes show states such as waiting, running, completed, reused, failed, or cancelled.
Editing is locked during a run, but you can still select nodes, read logs, and inspect earlier data.

Open **View → Execution** to see current and previous runs and the status of each node.
Nested workflow steps remain grouped under their workflow name.

Use **Stop** to cancel.
A running tool may need a short time to respond before execution fully stops.

For managed cluster targets, durable reconnection, retry, and result download, see [Managed Cluster Execution](distributed-execution.md).

## Read logs and errors

Open **Logger** to filter messages by severity, run, node, or text.
Node-specific messages also appear at the bottom of **Nodes**.

The error indicator near the theme control keeps execution, validation, connection, and application errors.
Open an entry for details or use **Go to node** when it is available.

## Inspect tables

1. Select one or more completed nodes.
2. Open **View → Node Data**.
3. Filter columns or change pages to inspect larger tables.

When selected nodes have compatible rows, BioImageFlow can combine their fields in one table.
Otherwise it shows separate tables.

Columns start at readable widths based on their headers and loaded values; wide tables scroll horizontally.
Drag a visible header separator to resize just that column, or double-click it to auto-size it.
You can also focus a separator with Tab and use Left/Right to resize or Enter to auto-size.
Manual widths are remembered for the workflow and table; **Reset column widths** restores automatic sizing using the current data.
Widths stay stable while changing pages or loading thumbnails, and hovering truncated header or text-cell content reveals the full text.

![Completed node results with an image preview and path actions in Node Data.](images/results-inspection.png)

## Inspect images and paths

Image paths can display preview thumbnails.
Path actions can reveal a file in the system file manager or copy its full path.

Use **Open in Napari** for local interactive image viewing.
Its first use can take longer while BioImageFlow prepares the viewer environment.
Use **Open in Avivator** for supported images when the application can reach that external web viewer.

## Export results

Select the workflow in **Workflows** and click **Open latest outputs** for a convenient file view.
“Latest” means the latest successful result of each node, so the folder can combine files from several runs.

Choose **Workflow → Export**, then:

- **Latest results** for independent copies with the same per-node latest behavior;
- **Workflow with results** for one successful run together with the workflow.

See [Manage Workflows](manage-workflows.md#import-or-export) for every sharing and export choice.
