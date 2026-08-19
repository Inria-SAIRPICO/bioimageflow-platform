# Edit Workflows with a Coding Agent

> **Available in:** Desktop only.

BioImageFlow can connect a coding agent to the workflow open in the desktop application.
Through MCP, the agent can inspect, modify, validate, and run that workflow while changes remain visible in BioImageFlow.

## Prepare the workspace

1. Open the workflow you want to work on.
2. Choose **Workflow → Save**.
3. Choose **Edit → Preferences...** and open **Storage**.
4. Next to **Workspace path**, click **Reveal**.
5. Open that workspace folder in [Visual Studio Code](https://code.visualstudio.com/docs/getstarted/overview).
6. In VS Code, choose **Terminal → New Terminal** and confirm that the terminal starts at the workspace root.

Keep BioImageFlow running and keep the intended workflow active.
The local MCP server communicates with the running application.

## Choose a coding client

Install and start one supported client by following its current official documentation:

- [Codex CLI](https://developers.openai.com/codex/cli)
- [OpenCode](https://opencode.ai/docs/)
- [Claude Code](https://code.claude.com/docs/en/quickstart)

Start the client from the VS Code terminal at the workspace root.
BioImageFlow has already written the project configuration that client needs:

| Client | Generated configuration |
|---|---|
| Codex | `.codex/config.toml` |
| OpenCode | `opencode.json` |
| Claude Code | `.mcp.json` |

You do not need to copy an MCP command or edit these generated files.

```{warning}
Coding agents and tool packages can execute code and can modify or run workflows.
Install them only from sources you trust, keep an original saved workflow, and review every change before saving.
```

## Inspect before changing

Use this as the first prompt:

> Use the BioImageFlow MCP server to inspect the active workflow. Explain what it does and propose one improvement, but do not change anything yet.

Check that the agent names the workflow you opened and that its explanation matches the canvas.
Discuss the proposed change before authorizing it.

## Apply and review a change

When the proposal is acceptable, give an explicit second instruction, for example:

> Apply the approved change through the BioImageFlow MCP server. Validate the active workflow afterward, summarize exactly what changed, and do not save the workflow for me.

Then:

1. Watch the change appear on the BioImageFlow canvas.
2. Read any validation banner and ask the agent to correct remaining errors through MCP.
3. Inspect renamed nodes, parameters, connections, and outputs in **Nodes**.
4. Run the workflow only when you are ready to execute its tools.
5. Choose **Workflow → Save** in BioImageFlow after the review.

## Handle an outdated change

If you edit the canvas or switch workflows while the agent is working, BioImageFlow can reject a change based on the older state.
Ask the agent to re-read the active workflow, explain what changed, and ask before trying again.

Never work around a rejected change by editing `workflow.json` or anything under `.bioimageflow/platform-source`.
Those files are not a safe route to the running workflow.

If BioImageFlow shows both a canvas version and an agent version, review the named workflow before choosing **Apply agent changes**, **Keep my canvas**, or **Save agent version as copy**.

For a non-operational explanation of the connection, see [How MCP Connects Coding Agents](../developer/mcp.md).
