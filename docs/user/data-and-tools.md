# Find and Manage Tools

The **Tools** panel lists the analysis steps available to a workflow.
Each installed package can provide several tools and one or more versions.

## Find a tool

1. Enter a name or technique in **Search tools...**.
2. Expand a matching category.
3. Open the tool information and read its inputs, outputs, and documentation.
4. Drag the tool onto the canvas or use its add action.

An available tool may still need an environment to be prepared before its first run.

## Choose package versions

Click **Manage tools** at the top of **Tools**.
The dialog lists known packages, available and installed versions, the tools in each version, and environment status.

Use a version's row action to install, select, or uninstall it.
A workflow uses one selected version of each package.
If changing the selection affects existing nodes, BioImageFlow asks before updating their outputs.

## Prepare environments

The environment status shows whether a package environment is stopped, being created, running, ready, failed, or unavailable.
Use the power action to start or stop an environment.
Environment controls are unavailable during workflow execution.

If a run cannot use an environment, follow the recovery dialog to restart or rebuild it, wait until it is ready, and retry the workflow.

```{note}
Installing a package or preparing its environment can download dependencies and take several minutes.
```

## Resolve missing tools

Imported and shared workflows can refer to packages or versions not installed on your system.
BioImageFlow keeps those nodes visible and marks the missing tools, but it blocks execution until you resolve them.

- Click **Install all missing packages** to install every requested version.
- Open **Manage tools** to install versions one at a time.
- Use **Use installed alternatives...** only when the versions already installed are acceptable replacements.

Review replacements carefully because a different package version can change workflow behavior or outputs.

## Install a package from another source

Use **Install tool package** at the bottom of **Manage tools**.
Enter a supported GitHub or GitLab package URL, or select a `.zip` package archive, then click **Install**.

```{warning}
Tool packages contain executable code.
Install a package only when you trust its source and maintainer.
```

To write analysis code yourself, see [Create Custom Tools](create-custom-tools.md).
