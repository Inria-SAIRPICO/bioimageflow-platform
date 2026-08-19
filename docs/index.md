# BioImageFlow Platform

BioImageFlow is a desktop application for building, running, and inspecting bioimage-analysis workflows.

![A BioImageFlow workflow open on the canvas, with tools, workflow tabs, node data, and execution controls visible.](user/images/interface-overview.png)

## Get started

New users can follow [Getting Started](user/index.md) to install BioImageFlow, open the bundled **Fish Analysis** demo, run it, and inspect its images, tables, logs, and output files.
When you are ready to create an analysis, [Build a Workflow](user/build-workflows.md) explains how to add tools, connect them, select local input data, and expose outputs.

## Build and manage workflows

Build workflows visually on the canvas, or let a trusted technical collaborator [define a workflow in Python](user/advanced-authoring.md).
Use [Find and Manage Tools](user/data-and-tools.md) to choose package versions and prepare their environments, and [Create Custom Tools](user/create-custom-tools.md) when an analysis needs its own Python code.

Saved workflows can be copied, organized, imported, and exported from the **Workflows** panel.
[Manage Workflows](user/manage-workflows.md) covers those tasks, while [Reuse and Nest Workflows](user/nested-workflows.md) shows how to group related steps or reuse one workflow inside another.

## Run and inspect analyses

[Choose Input Data](user/choose-input-data.md) explains how to select local files and folders or drag them onto the canvas.
[Run Workflows and Inspect Results](user/run-and-results.md) covers complete and partial runs, execution status, logs, tables, image previews, and output paths.

For larger workloads, BioImageFlow can schedule independent nodes in parallel or submit work to a [configured distributed target](user/distributed-execution.md).
Results can be exported on their own or bundled with the workflow that produced them.

## Configure and extend BioImageFlow

[Settings, Storage, and Integrations](user/preferences.md) explains the workspace, tool store, external editor, OMERO connections, execution targets, and launcher updates.
You can also connect a trusted coding client and [edit the active workflow through MCP](user/coding-agent.md), with every proposed change visible for review in BioImageFlow.

Use [Troubleshooting](user/troubleshooting.md) when the launcher, a tool environment, validation, saving, execution, or a viewer needs attention.
The [Keyboard Shortcuts](user/keyboard-shortcuts.md) page lists the main canvas and workflow commands.

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
