---
orphan: true
---

# Platform Architecture

BioImageFlow Platform wraps the BioImageFlow workflow library with a desktop editor and an application server.
This page gives contributors the system-level context that is too detailed for the project README.

## Runtime components

- The Python backend exposes REST and WebSocket APIs for tool discovery, workflow editing, graph validation, execution, and progress updates.
- The TypeScript frontend owns immediate canvas interaction state and communicates with the backend through those APIs.
- The desktop entry point starts the backend, serves the built frontend or connects to Vite during development, opens the application in a native pywebview window, and provides native file dialogs.
- The BioImageFlow library validates and executes accepted workflow definitions, while Wetlands manages isolated tool environments and external processes.

The component-specific references are the [backend README](https://github.com/Inria-SAIRPICO/bioimageflow-platform/blob/main/backend/README.md) and [frontend README](https://github.com/Inria-SAIRPICO/bioimageflow-platform/blob/main/frontend/README.md).

## Workflow editing and persistence

Each root canvas persists its editable recursive graph through a revisioned backend workflow draft.
That draft is shared by Save, Run, and the MCP integration so they operate on the same accepted workflow state.

A workflow can also appear as a node inside another workflow.
Nested canvas changes remain private to that editor until the user explicitly applies them to the parent workflow.
The saved `workflow.json` is the portable workflow document, while request-local graph validation does not replace the active draft.
Execution state remains transient and is recorded separately from the editable workflow.

The normative recursive graph and provenance rules are in [platform_specs_v2.md](https://github.com/Inria-SAIRPICO/bioimageflow-platform/blob/main/platform_specs_v2.md).
The generated workspace contract for coding agents remains in `docs/agents/` and the workspace-root `AGENTS.md`; the public overview is [How MCP Connects Coding Agents](mcp.md).

## Source layout

```text
bioimageflow-platform/
  backend/       Python API, services, desktop entry point, and packaging
  frontend/      TypeScript application and workflow editor
  docs/          User, developer, and agent documentation
  scripts/       Test, demo export, icon, and maintenance commands
  signing/       Signing pipeline integration
```

## Related architecture references

- [Workspace, Storage, and Demos](workspace-storage-and-demos.md) describes application-owned files and result views.
- [Managed distributed execution runtime wiring](../distributed_execution_runtime_wiring.md) describes the public cluster boundary, durable attachment, structured observation, retry, result retrieval, and cleanup.
- [Platform specifications v1](https://github.com/Inria-SAIRPICO/bioimageflow-platform/blob/main/platform_specs_v1.md) define the implemented application base.
- [Platform specifications v3](https://github.com/Inria-SAIRPICO/bioimageflow-platform/blob/main/platform_specs_v3.md) are a future proposal and do not describe current behavior unless explicitly inherited from v1 or v2.
