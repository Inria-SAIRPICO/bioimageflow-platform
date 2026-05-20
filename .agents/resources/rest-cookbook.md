# BioImageFlow REST Cookbook

This document summarizes the current stable REST surface for agents. It is documentation only and does not register tools or change runtime behavior.

## Draft workflow state

Agents should use workflow draft APIs for current unsaved workflow state. Drafts are in-memory, revisioned, and addressable. Mutating requests must include the caller's `base_revision`; stale revisions return `409`.

- `POST /api/v1/workflow-drafts`: create an anonymous draft from a `GraphState`.
- `GET /api/v1/workflow-drafts/{draft_id}`: read the current draft graph and revision.
- `PUT /api/v1/workflow-drafts/{draft_id}`: replace a draft graph with `{ graph, base_revision, client_seq }`.
- `PATCH /api/v1/workflow-drafts/{draft_id}/nodes/{node_id}/parameters`: patch constant parameters with `{ parameters, base_revision, client_seq }`.
- `POST /api/v1/workflow-drafts/{draft_id}/validate`: validate the draft snapshot.
- `POST /api/v1/workflow-drafts/{draft_id}/agent-proposals`: create a graph proposal against a draft revision.
- `POST /api/v1/workflow-drafts/{draft_id}/agent-proposals/{proposal_id}/apply`: apply a validated proposal.
- `POST /api/v1/workflow-drafts/{draft_id}/agent-proposals/{proposal_id}/reject`: reject a proposal.

The frontend root canvas uses stable addressed draft ids such as `workflow:<workflow_name-or-canvas>`. The first `PUT` with `base_revision: 0` creates that addressed draft.

Agents must carry the active draft id and revision through every bridge tool or REST mutation. Graph changes should be represented as draft proposals so the Agent Panel can preserve preview, reject, apply, and undo behavior.

## Agent Workspace Boundaries

- Agents must never edit platform source when authoring a workflow or tool for a user.
- Use the workflow-root workspace for generated scripts, workflow-local `tools/`, temporary inputs, and outputs.
- The platform reference is a copy and a read-only reference. Inspect it for examples and contracts, but do not patch or save workflow work there.
- Prefer Agent Panel bridge tools for workflow, graph, tool, package, execution, and undo actions. Use these REST routes as the backing contract when bridge tools are absent.

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

Execution is allowed when the user asks to run or verify a workflow and gives execution permission. Run the draft graph, include workflow context, and keep status visible through `GET /api/v1/execution/status` or WebSocket state.

## Packages

Request package install approval before installing missing packages or tools. Tell the user which node requires the package and whether the install will use the platform package action or an environment command.

## MCP tool inventory

Initial inventory, documentation/scaffold only. Do not call these names unless a real MCP server exposes them.

| Proposed tool | Purpose | Stable REST backing |
| --- | --- | --- |
| `bioimageflow.workflow.list` | List saved workflows | `GET /api/v1/workflows` |
| `bioimageflow.workflow.load` | Load saved workflow | `GET /api/v1/workflows/{name}` |
| `bioimageflow.workflow.current_draft` | Read current draft graph | `GET /api/v1/workflow-drafts/{draft_id}` |
| `bioimageflow.graph.validate` | Validate graph in workflow context | `PUT /api/v1/graph` |
| `bioimageflow.graph.propose` | Create a revisioned draft proposal | `POST /api/v1/workflow-drafts/{draft_id}/agent-proposals` |
| `bioimageflow.tool.create_local` | Create workflow-local tool | `POST /api/v1/tools?workflow_name=<name>` |
| `bioimageflow.tool.usage` | Check saved workflow references | `GET /api/v1/tools/{tool_name}/usage` |
| `bioimageflow.execution.status_snapshot` | Read execution state | `GET /api/v1/execution/status` |
| `bioimageflow.execution.run` | Start run | `POST /api/v1/execution/run` |
| `bioimageflow.execution.stop` | Stop run | `POST /api/v1/execution/stop` |
| `bioimageflow.execution.clear_cache` | Clear selected node caches | `POST /api/v1/execution/clear` |
| `bioimageflow.history.undo` | Undo the last applied agent graph edit | Agent Panel draft history |

## Scenario: Files > Atlas > Connected Components

For a novice `Files > Atlas > Connected Components` request:

1. Work only in the workflow-root workspace and inspect the copied platform reference as a read-only reference.
2. Read or create the active draft id and revision.
3. Use bridge tools, or `POST /api/v1/workflow-drafts/{draft_id}/agent-proposals`, to add a Files input or loader, Atlas processing node, and Connected Components node.
4. Connect outputs to inputs through the proposal flow; preserve existing ids, positions, resources, output templates, and published fields unless the request says otherwise.
5. Validate the draft with `POST /api/v1/workflow-drafts/{draft_id}/validate`.
6. Request package install approval for missing Atlas, segmentation, or connected-component dependencies before installation.
7. Ask for execution permission, then run the draft graph and report status. Leave undo available for applied edits.
