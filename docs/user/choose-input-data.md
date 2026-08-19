# Choose Input Data

Use a **Files** node when a workflow needs a set of files or one input directory.
Add **Files** from **Tools**, then select the node to configure it in **Nodes**.

## Choose files or a folder

Use one source on the **Files** node:

- **Select files** fills an ordered list of individual local files.
- **Select folder** fills one **Directory** source.

Choosing one source clears the other.
BioImageFlow refers to these local paths in place; it does not copy them into the workspace.

You can also drag local files or folders onto the canvas.
A single folder becomes the **Directory** source.
A drop with several folders, or a mixture of files and folders, adds the immediate files to the explicit file list.

## Connect data to tools

Connect the **Files** output to a compatible tool input.
If a downstream tool expects one path rather than a table, expose or connect the specific field shown by that tool.

Before running, check the selected paths and any file filters in **Nodes**.
If BioImageFlow reports a missing or invalid path, choose the file or folder again instead of typing a path from another computer.
