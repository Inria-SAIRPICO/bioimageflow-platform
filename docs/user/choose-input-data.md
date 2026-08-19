# Choose Input Data

> **Available in:** Desktop and browser. Desktop uses local paths; browser uses managed files from **Datasets**.

Use a **Files** node when a workflow needs a set of files or one input directory.
Add **Files** from **Tools**, then select the node to configure it in **Nodes**.

## Choose local files on desktop

Use one source on the **Files** node:

- **Select files** fills an ordered list of individual local files.
- **Select folder** fills one **Directory** source.

Choosing one source clears the other.
BioImageFlow refers to these local paths in place; it does not upload or copy them.

You can also drag local files or folders onto the desktop canvas.
A single folder becomes the **Directory** source.
A drop with several folders, or a mixture of files and folders, adds the immediate files to the explicit file list.

## Choose managed files in the browser

The browser does not use desktop file or folder pickers for workflow inputs.
Select uploaded items in **Datasets**, then click **Create Files node** or **Set files on “node name”**.

Managed folders expand to an ordered list of managed files.
They never become a filesystem **Directory** value.

Continue with [Manage Browser Datasets](browser-datasets.md) for upload, folders, selection, and drag-and-drop.

## Connect data to tools

Connect the **Files** output to a compatible tool input.
If a downstream tool expects one path rather than a table, expose or connect the specific field shown by that tool.

Before running, check the selected paths and any file filters in **Nodes**.
If BioImageFlow reports a missing or invalid path, correct the source for your current mode instead of typing a path from another computer.
