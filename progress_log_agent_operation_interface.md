# Progress Log: Agent Operation Interface

## 2026-05-29: Initial Planning

### Planned

- Revisit whether agent editing should use the current full-DAG draft API, a
  high-level MCP wrapper, backend command endpoints, or some combination.
- Keep the plan bounded and split into alternating plan/code phases.
- Apply the global workflow rules: high-effort agents, dedicated worktrees for
  coding, TDD, review agents, and plan updates between implementation phases.

### Implemented

- Spawned three high-effort strategy agents with distinct perspectives:
  backend/source-of-truth, agent usability/tooling, and frontend/product
  architecture.
- Created `agent_operation_interface_plan.md`.

### Learned

- Full-DAG draft replacement remains a good canonical source-of-truth contract.
- MCP alone would improve prompts but would put graph mutation semantics in the
  wrong layer.
- A narrow backend operation service/API can keep semantics centralized while
  preserving the full-DAG draft escape hatch.
- The plan must avoid a frontend rewrite, automatic merge, CRDTs, nested
  sub-workflow mutation, and a large operation DSL.

### Plan Changes

- Chose the middle path: backend operation layer first, with a thin tool
  transport afterward. Later planning below supersedes any CLI-first ordering.
- Explicitly made each implementation phase update the plan before the next
  code phase starts.

### Next Implementation Iteration

- Before coding, run a dedicated review-agent pass over
  `agent_operation_interface_plan.md`.
- Integrate only useful bounded improvements from that review.

## 2026-05-29: Review Agent Iteration 1

### Findings

- The plan was directionally correct and aligned with the existing full-DAG
  draft source of truth.
- The highest-risk gap was ambiguity around operation batching: allowing a
  batch is useful for agents, but only if it is capped, non-empty, and atomic.
- The backend API phase needed an explicit guard against duplicating draft write
  behavior that already exists in the current draft router/service.
- Parameter patch and edge replacement semantics needed to be concrete enough
  for TDD before implementation.
- CLI documentation tests need to change only when the CLI path becomes real,
  because current generated agent instructions intentionally do not mention a
  `bioimageflow-agent` command.

### Edits Made

- Added small-batch constraints: non-empty, maximum 10 operations, atomic write,
  operation-indexed validation errors, and no draft-change event on failure.
- Renamed the planned column connection operation to `connect_column_ref` to
  match the graph edge model.
- Clarified first-pass parameter updates as shallow patches that preserve
  unspecified keys and defer deletion semantics.
- Clarified edge replacement semantics for column-ref and positional
  connections.
- Added Phase 1 tests for empty/oversized batches and operation-indexed errors.
- Added Phase 2 acceptance criteria that failed batches leave revision, draft
  file, dirty state, agent state, and WebSocket publication count unchanged.
- Added an implementation note to reuse or extract existing draft-router
  behavior rather than forking lock/conflict/publication handling.
- Added a CLI regression-test note so generated `AGENTS.md` expectations are
  updated only if the CLI is actually documented in a later phase.
- Replaced the now-stale one-operation-versus-batch open question with a
  narrower question about whether the batch cap should remain 10.

### Meaningful

Yes. The edits materially reduce ambiguity and scope drift while keeping the
plan compact.

### Deferred Ideas

- Deciding whether Phase 1 should require agent-provided node ids or include a
  backend id-generation helper.
- Choosing the MCP Python package and dependency strategy.
- Adding parameter deletion, schema-driven coercion, sub-workflow addressing,
  published input/output mutation, or automatic merge behavior.

### Next Implementation Iteration

- Phase 0 should confirm the final operation model names and whether node id
  generation stays deferred before any coding starts.

## 2026-05-29: Scope Tightening Before Handoff Prompt

### Planned

- Reassess whether a CLI is necessary.
- Update the plan so a new session can execute autonomously without expanding
  scope.
- Review the revised plan before producing the handoff prompt.

### Implemented

- Deferred the CLI from the required path.
- Made the required path backend operation transforms, backend operation REST,
  MCP, and docs.
- Chose explicit agent-provided node ids for the first pass and deferred
  backend id generation.

### Learned

- The CLI is useful but not necessary for the core architecture.
- Adding a CLI now would add another interface to document and test without
  solving the main bottleneck better than MCP plus operation REST.

### Plan Changes

- Phase 3 is now MCP, not CLI.
- Documentation now says MCP first, operation REST second, raw full-DAG HTTP as
  diagnostic fallback.
- CLI is a deferred phase to revisit only after real MCP/operation usage.

### Next Implementation Iteration

- Have a fresh review agent check that the revised plan remains bounded and
  execution-ready.

## 2026-05-29: Review Agent Iteration 2

### Findings

- The active plan was mostly bounded and already deferred the CLI in non-goals,
  quality bar, and the deferred phase.
- The target architecture still listed CLI before MCP, which could mislead a
  new session into treating CLI as part of the required execution path.
- One Phase 2 exit criterion still said "before CLI/MCP work" after the CLI had
  been deferred.
- Phase 3 said MCP tools call the operation API, but the tool list also includes
  validation and execution controls that should call existing REST endpoints.
- The plan was actionable but lacked a self-contained prompt for the next
  implementation session.

### Edits Made

- Reordered target architecture so MCP and docs are the required path and CLI
  is explicitly a deferred fallback.
- Updated Phase 2 to say the plan must be updated before MCP work, with no CLI
  implication.
- Clarified that MCP graph-editing tools call the operation API, while
  read-only, validation, run, and stop tools call existing REST endpoints.
- Added a bounded new-session handoff prompt covering Phase 0/Phase 1, TDD,
  dedicated worktrees, review agents, parallel-agent limits, plan-update loops,
  and explicit out-of-scope items.
- Removed the remaining confusing CLI-first wording from the initial planning
  log while preserving the historical decision path.

### Meaningful

Yes. The edits remove stale CLI ordering and improve the autonomy of the future
implementation prompt without expanding scope.

### Deferred Ideas

- Choosing the MCP package and dependency strategy.
- Deciding whether to expose operation summaries in addition to
  `WorkflowDraftResponse`.
- Revisiting CLI only after MCP plus operation REST have real usage evidence.

### Next Implementation Iteration

- Start Phase 0 calibration in a dedicated worktree, then implement only Phase 1
  backend operation models and pure transforms with tests.

## 2026-05-29: Phase 0 Calibration

### Planned

- Inspect the current draft service, graph models, router wiring, tests, and
  agent docs before implementation.
- Confirm operation names, request/response shape, batch cap, explicit node id
  policy, and endpoint path.
- Update the plan before starting Phase 1.

### Implemented

- Reviewed the existing workflow draft models and service.
- Reviewed the draft router and app wiring.
- Reviewed graph node/edge models, frontend graph conversion conventions, and
  generated agent workspace instructions.
- Updated `agent_operation_interface_plan.md` with the confirmed endpoint,
  response, batch cap, and explicit node id decisions.

### Learned

- The existing full-DAG draft API is `GET/PUT
  /api/v1/workflow-drafts/{workflow_id:path}` and returns
  `WorkflowDraftResponse`.
- Draft writes already own revision conflict detection, validation, dirty state,
  agent-state refresh, and WebSocket draft-change publication.
- `GraphState` already has the fields needed for Phase 1:
  `nodes`, `edges`, `published_inputs`, and `published_outputs`.
- `NodeState` includes `id`, `name`, `tool_name`, `position`, `parameters`,
  `resources`, `output_templates`, `enabled`, `collapsed`, and sub-workflow
  metadata that operation transforms must preserve unless explicitly changed.
- Column-ref and positional edge models already match the planned operation
  names.
- No MCP dependency is currently present in the backend dependency set.
- `get_draft()` refreshes `.bioimageflow/agent-state.json`, so Phase 2 must not
  use it before semantic operation validation if failed batches are required to
  leave agent state unchanged.

### Plan Changes

- Confirmed the operation endpoint as
  `/api/v1/workflow-draft-operations/{workflow_id:path}`.
- Confirmed Phase 1/2 response shape as the normal `WorkflowDraftResponse`
  without operation summaries.
- Confirmed non-empty operation batches capped at 10.
- Confirmed create-node requires agent-provided `node_id`; backend id
  generation remains deferred.
- Added a Phase 2 implementation note to avoid agent-state refreshes before a
  batch has passed operation validation.

### Next Implementation Iteration

- Implement Phase 1 backend operation models and pure transforms with tests in a
  dedicated worktree.
- Review Phase 1 with a dedicated review agent before integration.

## 2026-05-30: Phase 1 Backend Operation Models And Pure Transforms

### Planned

- Add backend operation request/model types and a pure graph transform service.
- Cover the initial operation set with TDD:
  create/delete/rename/params/enabled/move/connect/delete-edge.
- Keep implementation independent of FastAPI and MCP.
- Preserve unrelated graph and node fields.

### Implemented

- Added `bioimageflow_server.models.workflow_draft_operations`.
- Added `bioimageflow_server.services.workflow_draft_operations`.
- Added focused model and service tests for:
  create node, delete node with edge cleanup, rename, shallow parameter patch,
  enabled state, move, column-ref connect replacement, positional connect
  replacement, delete edge, duplicate node IDs, missing nodes/edges,
  self-connections, duplicate edge IDs, operation-indexed semantic errors,
  atomic failure behavior, and preservation of unrelated fields.

### Learned

- The plan needed an explicit edge ID policy for connect operations because
  `GraphState` requires edge IDs.
- Connect operations can stay agent-friendly by accepting optional `edge_id` and
  generating deterministic backend defaults when it is omitted.
- Registry-aware connection validity, such as whether a positional target can
  accept upstream DataFrame inputs, should remain graph-validator/API behavior
  rather than part of the pure transform service.

### Plan Changes

- Documented optional connect-operation `edge_id` with deterministic backend
  generation.
- Marked Phase 1 model/transform exit criteria as complete.

### Validation

- `env UV_CACHE_DIR=/private/tmp/uv-cache uv run --extra dev python -m pytest
  tests/test_models/test_workflow_draft_operations.py
  tests/test_services/test_workflow_draft_operations.py`
  passed: 19 tests.
- `env UV_CACHE_DIR=/private/tmp/uv-cache uv run --extra dev python -m pytest
  tests/test_models/test_workflow_draft_operations.py
  tests/test_services/test_workflow_draft_operations.py
  tests/test_models/test_graph.py`
  passed: 34 tests.
- `env UV_CACHE_DIR=/private/tmp/uv-cache uv run ruff check
  src/bioimageflow_server/models/workflow_draft_operations.py
  src/bioimageflow_server/services/workflow_draft_operations.py
  tests/test_models/test_workflow_draft_operations.py
  tests/test_services/test_workflow_draft_operations.py`
  passed.

### Next Implementation Iteration

- Run a dedicated Phase 1 review agent. Completed: no blocking findings.
- Fix review findings, then commit Phase 1.
- Before Phase 2 coding, update this plan/log with the reviewed API-router
  implementation plan.

### Review Notes

- Review found no blocking Phase 1 issues.
- Phase 2 must ensure HTTP entry points validate through
  `WorkflowDraftOperationsRequest`; the pure transform service intentionally
  assumes the request/model layer has enforced non-empty and maximum-10 batch
  constraints.
