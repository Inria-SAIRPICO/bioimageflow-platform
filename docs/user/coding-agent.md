# Edit Workflows with a Coding Agent

BioImageFlow lets coding agents create and edit workflows from your instructions, with their changes shown in real time on the canvas.
Describe the analysis you want, then refine it through conversation or by editing the canvas yourself.
You can use Codex, Claude Code, oh-my-pi, or OpenCode.

## Open the code editor and terminal

1. Choose **View → Code Editor** in BioImageFlow.
   On first use, wait while the editor is downloaded and prepared.
2. In the editor's menu, choose **Terminal → New Terminal**.
   You can also open its Command Palette with F1 and run **Terminal: Create New Terminal**.
3. If asked which folder to use, select **Workspace**.
   The embedded editor starts terminals at your BioImageFlow workspace root, where the agent connection is already configured.

Keep BioImageFlow running while you use the agent.

```{note}
You can use your own Visual Studio Code installation instead.
Find **Workspace path** in **Edit → Preferences... → Storage**, open that folder in VS Code, and choose **Terminal → New Terminal** there.
Run the agent on the same computer as BioImageFlow, in this workspace folder.
```

## Install and start an agent

Choose one agent below.
Copy its installation command into the terminal and press Enter; you only need to install it once.
Then open a new terminal, enter its start command, and follow its sign-in instructions.
Your agent provider handles accounts, model access, and any usage charges.

### macOS and Linux

**Codex** — [official installation instructions](https://developers.openai.com/codex/cli):

```bash
curl -fsSL https://chatgpt.com/codex/install.sh | sh
```

Start it with `codex`.

**Claude Code** — [official installation instructions](https://code.claude.com/docs/en/setup):

```bash
curl -fsSL https://claude.ai/install.sh | bash
```

Start it with `claude`.

**oh-my-pi** — [official installation instructions](https://github.com/can1357/oh-my-pi#install):

```bash
curl -fsSL https://omp.sh/install | sh
```

Start it with `omp`.

### Windows (PowerShell)

Use a **PowerShell** terminal for these commands.
VS Code normally defaults to PowerShell on Windows, but your selected profile may be different.
Use the arrow beside the terminal's **+** button to choose PowerShell, or run **Terminal: Select Default Profile** from the Command Palette and open a new terminal.
See [VS Code terminal profiles](https://code.visualstudio.com/docs/terminal/profiles).

**Codex**:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://chatgpt.com/codex/install.ps1 | iex"
```

Start it with `codex`.

**Claude Code**:

```powershell
irm https://claude.ai/install.ps1 | iex
```

Start it with `claude`.

**oh-my-pi**:

```powershell
irm https://omp.sh/install.ps1 | iex
```

Start it with `omp`.

```{note}
These are the providers' convenience installers; check their official instructions above for current requirements, alternative installation methods, and troubleshooting.
If the start command is not found, follow the installer's PATH instructions and restart the terminal (or the editor if necessary).
For a Windows desktop BioImageFlow installation, use a native Windows agent terminal so the generated connection can use the same Python installation.

OpenCode is also configured automatically; follow its [installation guide](https://opencode.ai/docs/) and start `opencode` from the workspace terminal.
```

When the agent asks whether to trust this workspace or enable the **bioimageflow** connection, review and accept it to let the agent work with the application.
You do not need to configure the connection or mention it in every prompt.

## Create your first workflow

Try a request such as:

> Create a workflow called “Nuclei analysis” that reads TIFF images from `/path/to/my/images`, segments nuclei, and measures their area. Use available tools and ask me about any analysis choices you need.

Replace the example path with your image folder and describe your own analysis.
The agent can create the workflow, add tools, connect steps, and set parameters.
Watch the canvas update as it works, then select nodes to review the inputs, settings, and outputs.
Ask for changes in ordinary language:

> Change the segmentation threshold to 0.4 and add a summary of the measurements for each image.

When ready, click **Run Workflow**, inspect the results, and choose **Workflow → Save** to keep the workflow.
You can also ask the agent to run it and help interpret a failure.

## Edit an existing workflow

Open the workflow you want to change and make its canvas tab active.
Then describe the change, for example:

> Add a Gaussian blur before segmentation and keep the rest of this workflow unchanged.

Or ask the agent to duplicate a workflow before experimenting:

> Make a copy of Fish Analysis called “Fish Analysis experiment” and change the spot-detection settings in that copy.

If you and the agent edit the same workflow at the same time, BioImageFlow may ask you to choose between versions.
Review **Apply agent changes**, **Keep my canvas**, or **Save agent version as copy** before continuing.

## How the connection works

**MCP** means **Model Context Protocol**: a standard that lets an agent use actions supplied by another application.
BioImageFlow provides actions to discover available tools, create and organize workflows, edit nodes and connections, validate settings, and start or inspect a run.
The agent uses these actions to change the live workflow, and BioImageFlow updates the canvas automatically.
This is why you can describe an analysis without knowing the workflow file format or writing API calls.

BioImageFlow prepares the connection files in your workspace automatically:

| File | Purpose |
|---|---|
| `AGENTS.md` | Instructions for agents: how to discover tools, edit workflows, lay out nodes, and handle validation. |
| `.codex/config.toml` | Codex's BioImageFlow MCP connection. |
| `.mcp.json` | Claude Code's project MCP connection. |
| `.omp/mcp.json` | oh-my-pi's project MCP connection. |
| `opencode.json` | OpenCode's project MCP connection. |
| `.bioimageflow/mcp-client-config.json` | Shared connection configuration for other compatible clients. |
| `.bioimageflow/agent-state.json` | Current application connection and active-workflow information. |

You normally do not need to edit these generated files.
Clients that support `AGENTS.md` read these instructions from the workspace.
Current Claude Code versions can load it automatically when no `CLAUDE.md` takes precedence.
If Claude does not load it (for example with an older version or an existing `CLAUDE.md`), add this line to a `CLAUDE.md` at the workspace root:

```text
@AGENTS.md
```

This uses Claude Code's [instruction-file import](https://code.claude.com/docs/en/memory#import-additional-files).
It is separate from the automatically generated MCP connection.

If the agent cannot connect, check that BioImageFlow is running, the terminal is at the workspace root, and the client's project connection is enabled.
Restart the agent after switching workspaces or updating BioImageFlow so it reloads the generated configuration.
For more detail, see [How MCP Connects Coding Agents](../developer/mcp.md).
