# BioImageFlow Platform

Build, run, and inspect bioimage-analysis workflows in a visual application.
Use the desktop application with local files, or use BioImageFlow in a browser with managed Datasets.

![A BioImageFlow workflow open on the canvas, with tools, workflow tabs, node data, and execution controls visible.](user/images/interface-overview.png)

## Start here

### [Install and run a demo](user/index.md)

Install the launcher, open **Fish Analysis**, run it, and inspect its images, tables, logs, and files.

### [Build your own workflow](user/build-workflows.md)

Add tools to the canvas, connect them, choose input data, and expose the outputs you need.

## What you can do

### [Build workflows visually or from trusted Python](user/build-workflows.md)

Assemble tools on the canvas for everyday work, or let a trusted technical collaborator [define a workflow in Python](user/advanced-authoring.md) on desktop.

### [Use isolated, versioned tools or create your own](user/data-and-tools.md)

Choose tool-package versions, prepare their environments, and create [workflow-local or reusable custom tools](user/create-custom-tools.md).

### [Edit workflows with a coding agent](user/coding-agent.md)

Connect Codex, OpenCode, or Claude Code to the desktop application through MCP, then review changes on the canvas before saving.

### [Work with local files or managed Datasets](user/choose-input-data.md)

Choose files and folders directly on desktop, or [upload and organize managed files](user/browser-datasets.md) in the browser.

### [Run locally, in parallel, or on distributed targets](user/run-and-results.md)

Run a complete workflow or selected nodes on your computer, then move advanced work to [configured distributed targets](user/distributed-execution.md).

### [Inspect tables, images, logs, and output files](user/run-and-results.md)

Follow execution on the canvas and examine each node's data, image previews, log messages, and output paths.

### [Save, share, and export workflows and results](user/manage-workflows.md)

Make copies, organize workflow folders, export a reusable workflow, or bundle one successful run with its results.

### [Install and update through the launcher](user/index.md)

The launcher installs a verified release, prepares an isolated application environment, and keeps the application up to date.

```{toctree}
:maxdepth: 1
:caption: Getting Started
:hidden:

user/index
user/interface
```

```{toctree}
:maxdepth: 1
:caption: Workflows
:hidden:

user/build-workflows
user/manage-workflows
user/coding-agent
```

```{toctree}
:maxdepth: 1
:caption: Tools
:hidden:

user/data-and-tools
user/create-custom-tools
```

```{toctree}
:maxdepth: 1
:caption: Data
:hidden:

user/choose-input-data
user/browser-datasets
```

```{toctree}
:maxdepth: 1
:caption: Run and Results
:hidden:

user/run-and-results
```

```{toctree}
:maxdepth: 1
:caption: Settings and Help
:hidden:

user/preferences
user/troubleshooting
user/keyboard-shortcuts
```

```{toctree}
:maxdepth: 1
:caption: Advanced
:hidden:

user/nested-workflows
user/distributed-execution
user/advanced-authoring
```

```{toctree}
:maxdepth: 2
:caption: Developers
:hidden:

developer/index
```
