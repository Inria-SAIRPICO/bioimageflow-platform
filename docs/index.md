# BioImageFlow Platform

BioImageFlow is a desktop application for building, running, and inspecting bioimage-analysis workflows.

![A BioImageFlow workflow open on the canvas, with tools, workflow tabs, node data, and execution controls visible.](user/images/interface-overview.png)

## Get started

- **[Install and run a demo](user/index.md).** Install BioImageFlow, open the bundled **Fish Analysis** demo, run it, and inspect its images, tables, logs, and output files.
- **[Build your own workflow](user/build-workflows.md).** Add tools to the canvas, connect them, select local input data, and expose the outputs you need.

## Features

- **[Build workflows visually or from trusted Python](user/build-workflows.md).** Assemble tools on the canvas, [reuse workflows inside other workflows](user/nested-workflows.md), or let a trusted technical collaborator [define a workflow in Python](user/advanced-authoring.md).
- **[Use isolated, versioned tools or create your own](user/data-and-tools.md).** Choose package versions, prepare their environments, and create [workflow-local or reusable custom tools](user/create-custom-tools.md).
- **[Edit workflows with a coding agent](user/coding-agent.md).** Connect Codex, OpenCode, or Claude Code through MCP, then review changes on the canvas before saving.
- **[Choose local input data](user/choose-input-data.md).** Select files and folders with system pickers, or drag them directly onto the canvas.
- **[Run locally, in parallel, or on distributed targets](user/run-and-results.md).** Run a complete workflow or selected nodes on your computer, or submit advanced work to a [configured distributed target](user/distributed-execution.md).
- **[Inspect tables, images, logs, and output files](user/run-and-results.md).** Follow execution on the canvas and examine each node's data, image previews, messages, and output paths.
- **[Save, organize, share, and export your work](user/manage-workflows.md).** Copy workflows, arrange them in folders, export reusable workflow archives, or bundle one successful run with its results.
- **[Install and update through the launcher](user/index.md).** The launcher prepares an isolated application environment and selects verified BioImageFlow releases; [settings](user/preferences.md) cover storage and integrations.

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
