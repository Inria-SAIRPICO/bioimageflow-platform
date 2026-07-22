# User Guide

BioImageFlow is a desktop application for assembling, running, and inspecting bioimage-analysis workflows without writing orchestration code.
You build a workflow by placing tool nodes on a canvas, configuring their parameters, and connecting their inputs and outputs.

This guide is written for bioimage researchers.
It assumes that you understand your images and analysis methods, but it does not assume experience with graph editors or Python.

## Start here

- [Install and launch BioImageFlow](installation.md) if this is your first session.
- Follow the [quick start](quick-start.md) to run an example and inspect its results.
- Read the [interface tour](interface.md) when you want to understand the panels and controls.
- Use [Build a workflow](build-workflows.md) when creating an analysis of your own.

## Common tasks

- [Organize, import, export, and duplicate workflows](manage-workflows.md)
- [Group and reuse workflows inside other workflows](nested-workflows.md)
- [Run workflows and inspect tables, images, logs, and output files](run-and-results.md)
- [Upload datasets and manage analysis tools](data-and-tools.md)
- [Configure storage, viewers, editors, examples, and OMERO](preferences.md)
- [Build a saved workflow from trusted Python source](advanced-authoring.md)
- [Resolve common problems and look up keyboard shortcuts](troubleshooting.md)

```{toctree}
:maxdepth: 2
:hidden:

installation
quick-start
interface
build-workflows
manage-workflows
nested-workflows
run-and-results
data-and-tools
preferences
advanced-authoring
troubleshooting
```
