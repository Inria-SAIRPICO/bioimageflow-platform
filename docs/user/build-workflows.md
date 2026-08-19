# Build a Workflow

> **Available in:** Desktop and browser. Input-data selection differs by mode; see [Choose Input Data](choose-input-data.md).

A workflow connects analysis tools on a canvas.
Each node performs one task, and each edge sends data to another node.

## Create and save

1. Choose **Workflow → New**, or click **New workflow** in **Workflows**.
2. Enter a workflow name, display name, and optional description.
3. Add and connect nodes.
4. Choose **Workflow → Save** or press Ctrl/Cmd+S.

An asterisk in the workflow tab means that the canvas contains unsaved changes.
BioImageFlow keeps accepted canvas changes available for recovery, but it updates the saved workflow only when you use **Save**.

## Add a tool

1. Search in **Tools**.
2. Read the tool information to confirm its purpose and inputs.
3. Drag it onto the canvas or use its add action.
4. Select the new node to edit it in **Nodes**.

Double-click the displayed node name to rename that step without changing the tool it uses.
Disable a node when you want to keep it on the canvas without running it.

If the tool you need is missing, see [Find and Manage Tools](data-and-tools.md).

## Configure inputs

The **Parameters** section uses controls suited to each input, such as text fields, number fields, choices, checkboxes, and paths.

- **Reset to default** restores the value defined by the tool.
- **Set to null** passes no value when the input permits it.
- **Add input pin** makes the parameter connectable on the node.
- **Expose as workflow input** makes the value available to a parent workflow.

Use a **Files** node for a group of input files or one source directory.
Desktop users can use local pickers or drag local items onto the canvas.
Browser users select managed files in **Datasets**.

## Connect nodes

Drag from an output handle to a compatible input handle.
A field connection sends one named output into one input.
A DataFrame connection sends a whole table.

BioImageFlow prevents obvious cycles and validates every connection before saving or running.

![A selected tool node with parameter controls and connections to other workflow steps.](images/node-editing.png)

## Choose outputs

The **Outputs** section lists what the selected tool produces.
Use **Expose as workflow output** when a parent workflow should receive that value.
Give each public output a clear name.

For file outputs, enter a relative path that describes the result, such as `segmentation/masks.tif`.
Keep output paths distinct when one tool writes several files.

## Group related steps

Select one or more nodes, right-click the selection, and choose **Group into workflow**.
The grouped steps become one workflow node, and their outside connections become workflow inputs and outputs.

See [Reuse and Nest Workflows](nested-workflows.md) to edit and reuse the group.

## Fix validation problems

Workflow-wide problems appear above the canvas.
Node and parameter problems also appear on the affected item.
Select the named node, correct its field or connection, and wait for synchronization to finish before saving or running.

A path such as `segment_and_measure/cellpose_segmenter` points through a nested workflow.
Open each named workflow node until you reach the affected tool.
