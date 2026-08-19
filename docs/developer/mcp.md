# How MCP Connects Coding Agents

BioImageFlow uses the Model Context Protocol (MCP) to let a local coding client work with the workflow active in the running desktop application.
For the end-user procedure, see [Edit Workflows with a Coding Agent](../user/coding-agent.md).

## Connection flow

1. BioImageFlow writes active-workflow state and project-scoped client configuration into the selected workspace.
2. Codex, OpenCode, Claude Code, or another compatible client reads its project configuration from that workspace.
3. The client starts the local BioImageFlow MCP server over standard input and output.
4. The MCP server communicates with the running BioImageFlow application.
5. Accepted workflow changes appear back on the canvas for the user to review and save.

Through this connection, a client can inspect, edit, validate, and run the active workflow.
The BioImageFlow application must remain running.

## Generated workspace files

BioImageFlow writes `.codex/config.toml` for Codex, `opencode.json` for OpenCode, and `.mcp.json` for Claude Code and generic compatible clients.
It also writes workspace-level instructions in `AGENTS.md` and active connection state under `.bioimageflow/`.

These files keep each client connected to the BioImageFlow environment and workspace that created them.
They are generated context, not an alternative workflow-editing interface.

## Operational contract

Exact tool sequences, request payloads, edit conflict handling, and recovery rules belong in the operational contract read by maintainers and coding agents.
They are not reproduced in the public guide.

The repository contract remains in `docs/agents/`.
The generated workspace copy is under `.bioimageflow/platform-source/docs/agents/`, and the workspace root `AGENTS.md` provides the entry point for the active session.

Maintain these files with the implementation whenever the MCP interface changes.
Do not add the detailed contract to a public Sphinx toctree.
