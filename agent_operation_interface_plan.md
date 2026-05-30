# Agent Operation Interface Plan

## Decision

Keep the full-DAG workflow draft API as the canonical source-of-truth contract
and escape hatch. Add a small backend-owned operation interface for semantic
workflow edits, then expose that interface through a thin MCP server.

This avoids moving graph mutation semantics into MCP/client code while keeping
the current full-graph draft model intact. The operation interface must reuse
the same draft service behavior: latest draft read, `expected_revision`,
execution lock checks, validation, atomic draft write, dirty tracking, and
frontend draft-change notification.

## Strategy-Agent Conclusion

Three read-only strategy agents reviewed the API shape:

- One favored MCP/client first over adding command endpoints immediately.
- One favored backend operation endpoints first, with MCP only as a convenience
  layer.
- One recommended the middle path: full-DAG remains canonical, but semantic
  graph edits should become backend-owned before MCP becomes the main agent
  interface.

The plan follows the middle path. MCP alone would speed up prompts, but it
would still duplicate graph-edit rules outside the platform. A bounded backend
operation layer gives agents a simple interface without replacing the existing
draft API or forcing a frontend rewrite.

## Non-Goals

- Do not replace `GET/PUT /workflow-drafts/{workflow_id}`.
- Do not commandize every canvas change or every graph field.
- Do not rewrite frontend canvas editing around request-per-edit round trips.
- Do not build automatic merge, CRDTs, or multi-user collaboration.
- Do not support nested sub-workflow mutation in the first pass.
- Do not make MCP the only way agents can edit workflows.
- Do not build a CLI unless MCP plus raw HTTP fallback still leaves agents
  struggling. A CLI is useful, but not necessary for the core architecture.
- Do not add a large operation DSL before real usage proves it is needed.

## Target Architecture

The layers should be:

1. Backend draft source of truth:
   `GET/PUT /workflow-drafts/{workflow_id}` remains the canonical graph state
   contract.
2. Backend operation service:
   pure, tested graph mutations such as create node, delete node, rename node,
   update params, connect, disconnect, move, enable, and disable.
3. Backend operation API:
   a narrow REST surface that applies one operation or a small batch against the
   current draft and writes the resulting full graph through the existing draft
   service.
4. MCP server:
   thin tool layer over the operation API. It discovers the active workflow from
   `.bioimageflow/agent-state.json` and returns compact structured results.
5. Agent docs:
   prefer MCP when available, operation REST next, raw full-DAG editing only as
   a diagnostic fallback.
6. Deferred CLI fallback:
   optional and out of scope for the required path. Reconsider only after MCP
   and operation REST have been tested in real agent sessions.

## Operation API Shape

Avoid nested routes under `/{workflow_id:path}` because path capture can make
subroutes ambiguous. Prefer a sibling router:

```text
POST /api/v1/workflow-draft-operations/{workflow_id:path}
```

Phase 0 calibration confirmed this should be the endpoint path. The existing
draft router is mounted at `/api/v1/workflow-drafts/{workflow_id:path}` and is
already path-capturing, so operation routes must not be nested below it.

Request:

```json
{
  "expected_revision": 12,
  "updated_by": "agent",
  "validate": true,
  "operations": [
    {
      "type": "create_node",
      "node_id": "blur_1",
      "tool_name": "GaussianBlur",
      "name": "Blur",
      "position": [240, 160],
      "parameters": {}
    }
  ]
}
```

Response returns the normal `WorkflowDraftResponse` in the first pass. Do not
add operation summaries until real MCP/agent usage shows they are needed. Error
responses should stay machine-readable:
`409 draft_revision_conflict`, `423 workflow_locked`, `404 workflow_not_found`,
`422 operation_validation_error`.

Allow a small batch from the start because it keeps agent edits concise without
creating a broad DSL. The batch must be non-empty, capped at 10 operations, and
atomic: if any operation fails, no draft is written and no draft-change event is
published. Operation validation errors should include the failing operation
index and a stable error code. Phase 0 confirmed the cap stays 10.

Initial create-node requests require an explicit `node_id`. Backend id
generation remains deferred. Connect operations accept optional `edge_id`;
when omitted, the backend operation transform generates deterministic edge ids
matching frontend conventions:
`e-{source_node}-{source_output}-{target_node}-{target_input}` for column-ref
edges and `e-{source_node}-__dataframe_out-{target_node}-__positional_{index}`
for positional edges.

Initial operation set:

- `create_node`
- `delete_node`
- `rename_node`
- `update_node_parameters`
- `set_node_enabled`
- `move_node`
- `connect_column_ref`
- `connect_positional`
- `delete_edge`

Defer published inputs/outputs, sub-workflow addressing, bulk layout, automatic
node id generation beyond simple optional backend defaults, and schema-driven
parameter coercion.

Parameter updates are shallow patches in the first pass: supplied keys are set,
unspecified parameter keys are preserved, and parameter deletion is deferred
unless existing code already has a clear convention for it. Edge replacement
semantics should match the current graph rules: a column-ref connection replaces
any existing edge for the same `target_node` plus `target_input`; a positional
connection replaces any existing edge for the same `target_node` plus
`positional_index`.

## Alternating Phases

Each phase updates this plan before the next code phase starts. Each code phase
uses TDD, a dedicated worktree, and a dedicated review agent. Parallel agents
may run when write scopes are independent.

### Phase 0: Plan Calibration

Goal: keep the plan small and aligned with the real codebase.

Work:

- Review current draft service, graph models, router shape, and docs.
- Confirm endpoint path choice and first operation set.
- Update this plan and `progress_log_agent_operation_interface.md`.

Exit criteria:

- Reviewed plan is accepted as bounded. Completed on 2026-05-29.
- No implementation starts from stale assumptions. Phase 0 confirmed:
  operation names are unchanged; create-node requires explicit `node_id`;
  batches are non-empty and capped at 10; the operation response is
  `WorkflowDraftResponse`; and the operation endpoint is
  `/api/v1/workflow-draft-operations/{workflow_id:path}`.

### Phase 1: Backend Operation Models And Pure Transform Service

Goal: implement graph mutation semantics without HTTP or MCP concerns.

TDD:

- Add tests for operation model validation.
- Add tests for pure graph transforms:
  create, delete with edge cleanup, rename, params update, enable/disable,
  move, column-ref connect replacement, positional connect replacement, delete
  edge.
- Add negative tests for duplicate node id, missing node, missing edge, invalid
  self-conflict, empty/oversized batches, operation-indexed errors, and
  preserving published inputs/outputs except for explicit operations that are
  allowed to touch them in a future phase.

Implementation:

- Add operation request/response models.
- Add a service module for pure graph operation application.
- Keep it independent of FastAPI and MCP.
- Keep transform output as a full `GraphState`, so the REST layer can write
  through the existing draft service without a second persistence path.

Review:

- Backend review agent checks operation semantics, type models, edge cleanup,
  and test coverage.

Exit criteria:

- Focused backend tests pass. Completed on 2026-05-30 for the pure transform
  and model layer.
- Plan updated with any operation shape changes learned from tests. Phase 1
  made connect-operation `edge_id` optional with deterministic backend defaults.

### Phase 2: Backend Operation API

Goal: expose operation application through REST while preserving draft behavior.

TDD:

- Router tests for successful operation writes.
- Tests for `expected_revision`, validation, lock handling, missing workflow,
  operation validation errors, dirty tracking, and WebSocket draft-change
  publication.
- Tests that full-DAG `GET/PUT` behavior remains unchanged.

Implementation:

- Add a sibling router such as `/workflow-draft-operations/{workflow_id:path}`.
- Read the latest draft without refreshing agent state, apply operations, then
  write through the existing draft service only after operation validation
  succeeds.
- Return `WorkflowDraftResponse`.
- Reuse or extract the existing draft-router helpers for execution locks,
  conflict responses, API base URL handling, and draft-change publication
  instead of forking that behavior into a second route.
- Avoid calling any draft read path that rewrites agent state before operation
  validation has succeeded. Failed operation batches must not refresh
  `.bioimageflow/agent-state.json`.
- Validate all operation HTTP bodies through `WorkflowDraftOperationsRequest`
  so the non-empty and max-10 batch constraints are enforced before the pure
  transform service runs.

Review:

- Backend review agent checks route conflicts, source-of-truth preservation,
  error consistency, and no duplicate write path.

Exit criteria:

- Backend operation API passes tests.
- Existing draft API tests still pass.
- A failed operation batch leaves the draft revision, draft file, dirty state,
  agent state, and WebSocket publication count unchanged.
- Plan updated before MCP work.

### Phase 3: MCP Server

Goal: expose backend-owned graph edits through MCP while routing read,
validation, and execution helpers to existing REST endpoints.

TDD:

- Tests for tool schema generation or registration.
- Tests that MCP graph-editing tools call the operation API and do not mutate
  graphs locally.
- Tests for active workflow discovery from `.bioimageflow/agent-state.json`.
- Tests for compact structured success and error results.

Implementation:

- Add an MCP server package/module with tools:
  `get_active_workflow`, `list_tools`, `create_node`, `delete_node`,
  `rename_node`, `update_node_parameters`, `connect_nodes`, `delete_edge`,
  `validate_workflow`, `run_workflow`, `stop_execution`.
- MCP should be a thin transport layer over REST. Graph-editing tools call the
  operation API; read-only, validation, run, and stop tools call the existing
  REST endpoints and must not add separate graph mutation semantics.
- Include generated MCP config or clear startup docs if automatic registration
  is not reliable yet.

Review:

- MCP review agent checks that graph semantics remain backend-owned and that
  tool names/descriptions are simple enough for agents.

Exit criteria:

- A capable agent can add a node through one MCP tool call.
- Plan updated before docs integration.

### Phase 4: Documentation And Workspace Integration

Goal: make the fastest path obvious to future agents.

TDD:

- Tests for generated `AGENTS.md` content.
- Tests for generated state/config fields if new ones are added.

Implementation:

- Update root generated `AGENTS.md`:
  MCP first, operation REST second, raw full-DAG HTTP fallback.
- Update `docs/agents/`.
- Refresh live workspace context.
- Keep platform-source read-only warning.

Review:

- Fresh review agent reads docs as an agent with no prior platform knowledge.

Exit criteria:

- Future agents can identify the preferred tool path in under a minute.
- Raw full-DAG editing is clearly marked as fallback.

### Deferred Phase: CLI Fallback

Reconsider only after MCP and operation REST are implemented and tested in real
agent sessions.

Build it later if local/simple models still need a shell-oriented interface or
if MCP setup proves unreliable. If added, the CLI must be a thin wrapper over
the operation API, not a graph mutation implementation.

## Parallelization

Use parallel agents only for disjoint write scopes:

- Backend models/transform service and docs planning can be reviewed in
  parallel.
- MCP and docs can be prepared in parallel after the operation API contract is
  stable, but MCP should not invent graph semantics.
- CLI work is deferred and should not run in parallel with the core path unless
  a later plan update explicitly brings it back into scope.

Each coding agent works in a dedicated worktree and reports changed files,
tests run, and residual risks. Each implementation is reviewed by a separate
high-effort review agent before integration.

## Quality Bar

- The backend remains the owner of graph mutation semantics.
- Full-DAG draft API remains available and tested.
- Operation tests cover both success and destructive edge cleanup.
- Frontend sync/conflict behavior does not regress.
- Agent tools reduce the “add node” path to one operation-level command/tool
  call.
- Errors are machine-readable and concise enough for agents to self-correct.
- The required implementation path stays small: backend operation transforms,
  backend operation REST, MCP, and docs. CLI remains optional.

## Open Questions

- Should the initial batch cap stay at 10, or should Phase 0 adjust it after
  reviewing typical agent edits?
- Phase 0 decision: backend should require agent-provided node ids in the first
  pass. Optional backend id generation is deferred because explicit ids make
  tests, retries, and follow-up agent references clearer.
- Which MCP Python package should be used, and is it already acceptable as a
  backend dependency?

## New Session Handoff Prompt

Use this prompt to start the implementation session:

```text
Implement the BioImageFlow agent operation interface from
agent_operation_interface_plan.md, starting with Phase 0 and Phase 1 only.

Constraints:
- Defer CLI entirely unless a later plan update with new evidence brings it
  back into scope.
- Do not rewrite the frontend editing model, build a broad operation DSL, add
  automatic merge/CRDT behavior, or mutate nested sub-workflows.
- Keep full-DAG workflow drafts as the canonical source of truth.
- Put graph mutation semantics in backend operation models and pure transforms,
  then expose them through a REST operation API and a thin MCP layer in later
  phases.
- Follow TDD: write/update tests before implementation.
- Use a dedicated worktree for coding work, review agents for each phase, and
  parallel agents only for independent write scopes.
- Before each new implementation iteration, update this plan and
  progress_log_agent_operation_interface.md with what was learned.

Expected first iteration:
1. Review the current draft service, graph models, router wiring, and existing
   tests.
2. Confirm operation names, request/response model shape, batch cap, and
   agent-provided node id policy.
3. Update this plan/log if the real codebase changes any assumption.
4. Implement Phase 1 backend operation models and pure graph transforms with
   focused tests.
```
