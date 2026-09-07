# Reuse and Nest Workflows

A workflow can appear as one node inside another workflow.
Use this to group a readable section of a large analysis or reuse a saved workflow.

## Create a nested workflow

Choose one method:

- Select canvas nodes, right-click the selection, and choose **Group into workflow**.
- Drag a saved workflow from **Workflows** onto another workflow's canvas.

Grouping replaces the selection with one workflow node and preserves its connections.
Dragging a saved workflow copies its saved graph, public inputs and outputs, and workflow-local tools into the parent.

BioImageFlow prevents a workflow from containing itself, directly or through other workflows.

## Define its connections

A thick border identifies a workflow node.
Its handles come from the inputs and outputs exposed inside it.

1. Double-click the workflow node to open its graph.
2. Select an internal tool.
3. In **Nodes**, use **Publish DataFrame input** under **Published DataFrame inputs** to receive a whole upstream table, **Expose as workflow input** on a parameter, or **Expose as workflow output** on a result.
4. Give the exposed port a clear name.
5. Save the nested tab into its parent.

Renaming an exposed port keeps compatible parent connections.
Removing or changing a connected port asks for confirmation before removing an incompatible connection.

For a DataFrame Tool that accepts upstream tables, each click on **Publish DataFrame input** publishes another positional input.
Give each publication a clear name; **DataFrame 1**, **DataFrame 2**, and so on indicate the table order passed to the tool.
Publish only as many tables as the tool's implementation supports.
These inputs are separate from the tool's scalar parameters: do not declare a parameter merely to carry a column from an upstream table.
Use **Unpublish** to remove a public input; remaining table positions shift together while their public IDs and names stay stable.
You can also select a child workflow node and publish one of its unconnected DataFrame inputs through the enclosing workflow.

## Edit nested content

Double-click a workflow node, or right-click it and choose **Open workflow**.
BioImageFlow opens its graph in a nested editor tab.

![A workflow node and its internal graph open in a nested editor tab.](images/nested-workflow.png)

Choose **Workflow → Save** or press Ctrl/Cmd+S to apply the nested edits to the parent node.
You cannot run a nested tab directly; save it and run the root workflow.

If the parent changed while the nested tab was open, BioImageFlow refuses an outdated apply.
Review the latest parent before choosing whether to keep your changes or use the latest nested content.

## Update a reused workflow

A workflow dragged from **Workflows** remembers which saved workflow it came from.
Editing the nested copy does not edit that saved source.

Right-click the workflow node to use:

- **Open source workflow** to open the saved source in its own tab;
- **Update from source** to preview and apply its latest saved content;
- **Detach from source** to keep the nested content without its source link.

Save or close any nested editor at the update location before using **Update from source**.
BioImageFlow does not silently change embedded copies when their saved source is edited, moved, or deleted.
