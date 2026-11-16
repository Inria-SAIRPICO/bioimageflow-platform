# Find and Manage Tools

The **Tools** panel lists the analysis steps available to a workflow.
Each installed package can provide several tools and one or more versions.

## Find a tool

1. Enter a name or technique in **Search tools...**.
   Search covers tool names, tags, categories, and documentation keywords.
2. Expand a matching category.
3. Click a tool row to show its information at the bottom of the panel; click the row again to hide it.
4. Double-click the row to add the tool at the default canvas position, or drag it to a chosen position.

## Choose package versions

Click **Manage tools** at the top of **Tools**.
The dialog lists known packages, available and installed versions, the tools in each version, and environment status.

Use a version's row action to install, select, or uninstall it.
A workflow uses one selected version of each package.
If changing the selection affects existing nodes, BioImageFlow asks before updating their outputs.

## Tool environments

A tool package provides the code and descriptions you see in **Tools**.
A **tool environment** contains the software needed to execute processing tools: a Python interpreter, libraries, and any other programs declared by the tool.
Keeping these dependencies in isolated environments lets tools use different versions without changing your system Python or other applications.
**Wetlands**, BioImageFlow's environment manager, creates and runs these environments from recipes supplied by tool authors.
Tools with the same requirements can share an environment; this is separate from the version of the tool package selected in your workflow.
DataFrame tools operate on tables in the application's own process rather than a separate processing environment.

You can usually click **Run Workflow** and let BioImageFlow prepare missing environments as needed.
The first preparation requires internet access and may take several minutes to download dependencies.
Later runs reuse the installed environment.
Follow setup progress in **Execution** and detailed messages in **Logger**.

To prepare or inspect an environment yourself, open **Manage tools**:

- Check its status to see whether it needs setup, is being prepared, is ready, or has failed.
- Use **Create / recreate** to install a missing environment or rebuild it from the declared recipe after a setup problem.
- Use the power action to start or stop its running process.
  Stopping releases the process; it does not uninstall the environment, tool code, or workflow results.
- Select the tool to find its environment location in the tool information area.

Environment controls are unavailable while a workflow is executing.
If an application update changes the required execution recipe, BioImageFlow updates a managed environment on first use and reports **Updating execution environment**.
If setup fails, read **Logger** for the failed download or dependency, correct the cause, and retry **Create / recreate**.
A tool that declares an incompatible BioImageFlow Core version needs an updated tool definition or package version; recreating the same incompatible recipe will not fix it.

Napari uses separate viewer environments, configured under [Image viewers](preferences.md#image-viewers).

## Resolve missing tools

Imported and shared workflows can refer to packages or versions not installed on your system.
BioImageFlow keeps those nodes visible and marks the missing tools, but it blocks execution until you resolve them.

- Click **Install all missing packages** to install every requested version.
- Open **Manage tools** to install versions one at a time.
- Use **Use installed alternatives...** only when the versions already installed are acceptable replacements.
  Confirm the listed replacements, review the updated draft, then **Save** to keep the new dependency versions.

Review replacements carefully because a different package version can change workflow behavior or outputs.

## Install a package from another source

Use **Install tool package** at the bottom of **Manage tools**.
Enter a supported GitHub or GitLab package URL, or select a `.zip` package archive, then click **Install**.

```{warning}
Tool packages contain executable code.
Install a package only when you trust its source and maintainer.
```

To write analysis code yourself, see [Create Custom Tools](create-custom-tools.md).
