# BioImageFlow REST Cookbook

This document summarizes the current stable REST surface for agents. It is documentation only and does not register tools or change runtime behavior.

## Draft workflow state

Agents should use draft APIs for current workflow state when stable draft endpoints exist in the active branch. In this branch, stable REST routes for workflow drafts are not present in the checked OpenAPI snapshot. For current editing state, follow the frontend graph serialization contract and validate with `PUT /api/v1/graph` before saving.

## Workflow CRUD

- `GET /api/v1/workflows`: list saved workflows.
- `POST /api/v1/workflows`: create a workflow.
- `GET /api/v1/workflows/{name}`: load saved workflow metadata, graph, and missing dependency data.
- `PUT /api/v1/workflows/{name}`: save a graph for the workflow.
- `PATCH /api/v1/workflows/{name}`: update workflow metadata or rename.
- `DELETE /api/v1/workflows/{name}`: delete workflow.
- `POST /api/v1/workflows/{name}/export`: export workflow archive.
- `POST /api/v1/workflows/import`: import JSON or zip workflow.
- `POST /api/v1/workflows/{name}/rebind-versions`: rebind package versions for a workflow.

## Graph Validation

- `PUT /api/v1/graph`: validate graph structure and node statuses. Send `{ "graph": <GraphState>, "workflow_name": "<name>" }` when validating in workflow context.
- `PATCH /api/v1/graph/nodes/{node_id}/parameters?tool_name=<tool>`: validate constant parameter updates only.
- `POST /api/v1/graph/nodes/{node_id}/output_schema`: resolve output columns for one node from a full graph.

## Workflow-Local Tools

- `GET /api/v1/tools`: list registered tools.
- `GET /api/v1/tools/packages`: list packages.
- `POST /api/v1/tools?workflow_name=<name>`: create a workflow-local custom tool.
- `GET /api/v1/tools/{tool_name}/source?workflow_name=<name>`: resolve source path and editability.
- `GET /api/v1/tools/{tool_name}/usage?workflow_name=<name>`: list saved workflows affected by a custom tool.
- `PATCH /api/v1/tools/{tool_name}?workflow_name=<name>`: rename a workflow-local custom tool.
- `DELETE /api/v1/tools/{tool_name}?workflow_name=<name>`: delete a workflow-local custom tool.

## Execution

- `GET /api/v1/execution/status`: fetch execution state, last result, progress, and node statuses.
- `POST /api/v1/execution/run`: run all or selected nodes with a graph and optional `workflow_name`.
- `POST /api/v1/execution/stop`: request stop.
- `POST /api/v1/execution/clear`: clear selected node caches for a graph and optional `workflow_name`.

## MCP tool inventory

Initial inventory, documentation/scaffold only. Do not call these names unless a real MCP server exposes them.

| Proposed tool | Purpose | Stable REST backing |
| --- | --- | --- |
| `bioimageflow.workflow.list` | List saved workflows | `GET /api/v1/workflows` |
| `bioimageflow.workflow.load` | Load saved workflow | `GET /api/v1/workflows/{name}` |
| `bioimageflow.workflow.current_draft` | Read current draft graph | Not stable in this branch |
| `bioimageflow.graph.validate` | Validate graph in workflow context | `PUT /api/v1/graph` |
| `bioimageflow.tool.create_local` | Create workflow-local tool | `POST /api/v1/tools?workflow_name=<name>` |
| `bioimageflow.tool.usage` | Check saved workflow references | `GET /api/v1/tools/{tool_name}/usage` |
| `bioimageflow.execution.status_snapshot` | Read execution state | `GET /api/v1/execution/status` |
| `bioimageflow.execution.run` | Start run | `POST /api/v1/execution/run` |
| `bioimageflow.execution.stop` | Stop run | `POST /api/v1/execution/stop` |
| `bioimageflow.execution.clear_cache` | Clear selected node caches | `POST /api/v1/execution/clear` |
