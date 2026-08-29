# Developer Guide

BioImageFlow contributors should begin with the [project README](https://github.com/Inria-SAIRPICO/bioimageflow-platform#readme) for local setup and repository structure.

Use these focused references when needed:

- [Platform Architecture](architecture.md) describes the application components and workflow editing model.
- [Local Development](local-development.md) collects alternate run modes, logging, local core development, and editable tool packages.
- [Workspace, Storage, and Demos](workspace-storage-and-demos.md) documents platform-owned files, output views, exports, and bundled workflow maintenance.
- [Release Process](releases.md) is the application and launcher release checklist.
- [Testing](../testing.md) explains the repository-owned test lanes and focused selectors.
- [Manual Platform Testing](manual-testing.md) provides reusable fixtures plus lightweight and complete human acceptance plans.
- [Managed distributed execution runtime wiring](../distributed_execution_runtime_wiring.md) describes how the application connects trusted profiles, submission, durable attachment, structured progress, results, and cleanup.
- [How MCP Connects Coding Agents](mcp.md) explains the public architecture of the desktop coding-agent integration.

Detailed MCP operations are intentionally kept with the source and generated workspaces rather than published as end-user pages.

```{toctree}
:maxdepth: 1
:hidden:

mcp
manual-testing
```
