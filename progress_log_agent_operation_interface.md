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

## 2026-05-30: Phase 2 Planning Update

### Planned

- Expose the Phase 1 transform service through a sibling backend operation API.
- Preserve the current full-DAG draft API behavior and tests.
- Keep failed operation batches atomic across draft file, revision, dirty state,
  agent state, and WebSocket publication.

### Learned

- Existing draft writes already centralize revision checks, validation, dirty
  tracking, agent-state refresh, and draft-file persistence in
  `WorkflowDraftService.put_draft`.
- Existing draft reads refresh `.bioimageflow/agent-state.json`, so the
  operation route needs a read path that does not refresh agent state before a
  semantic operation batch has passed validation.
- Phase 1 request models enforce non-empty and max-10 batches; the router must
  use those models directly.

### Plan Changes

- Phase 2 will add or expose a no-agent-context draft read path for operation
  validation.
- Phase 2 will extract/reuse router helpers for execution lock, conflict
  response, API base URL, and draft-change publication.
- Phase 2 will keep operation validation errors machine-readable as
  `operation_validation_error` with `operation_index`, `code`, and `detail`.

### Next Implementation Iteration

- Add router tests first for success, conflict, lock, missing workflow,
  operation validation failure, failed-batch atomicity, dirty state,
  draft-change publication, and unchanged full-DAG draft API behavior.
- Implement the sibling operation router and app wiring.
- Run a dedicated Phase 2 review agent before commit.

## 2026-05-30: Phase 2 Backend Operation API

### Planned

- Add a sibling `POST /api/v1/workflow-draft-operations/{workflow_id:path}`
  route.
- Apply semantic operations against the latest draft, then write through the
  existing draft service.
- Preserve existing full-DAG draft API behavior.
- Keep failed semantic batches from writing drafts, refreshing agent state, or
  publishing frontend events.

### Implemented

- Added `WorkflowDraftService.get_draft_snapshot()` for draft reads that do not
  refresh `.bioimageflow/agent-state.json`.
- Extracted reusable draft-router helpers for conflict responses and
  draft-change publication.
- Added `bioimageflow_server.routers.workflow_draft_operations`.
- Wired the operation router into `create_app` with the same draft service,
  execution manager, and connection manager dependencies as the full-DAG draft
  router.
- Added router tests for successful batches, nested workflow IDs, stale
  revision conflicts, execution lock, missing workflow, semantic validation
  errors, failed-batch atomicity, request-model batch validation, and unchanged
  full-DAG draft API behavior.

### Learned

- The no-agent-context draft snapshot method keeps failed semantic batches
  atomic without weakening the existing full-DAG `GET /workflow-drafts` behavior.
- Reusing the existing draft service for writes preserved validation, dirty
  tracking, revision increments, agent-state refresh, and draft-file
  persistence without a second write path.
- The operation route must be included before the path-capturing draft router,
  even though the routes are siblings, to keep future route additions safer.

### Plan Changes

- Marked Phase 2 exit criteria as complete.
- Confirmed the operation route returns `WorkflowDraftResponse` and semantic
  errors use `operation_validation_error` with operation index and code.

### Validation

- `env UV_CACHE_DIR=/private/tmp/uv-cache uv run --extra dev python -m pytest
  tests/test_routers/test_workflow_draft_operations.py
  tests/test_routers/test_workflow_drafts.py
  tests/test_models/test_workflow_draft_operations.py
  tests/test_services/test_workflow_draft_operations.py`
  passed: 35 tests after the review follow-up.
- `env UV_CACHE_DIR=/private/tmp/uv-cache uv run ruff check
  src/bioimageflow_server/app.py
  src/bioimageflow_server/routers/workflow_drafts.py
  src/bioimageflow_server/routers/workflow_draft_operations.py
  src/bioimageflow_server/services/workflow_draft.py
  src/bioimageflow_server/models/workflow_draft_operations.py
  tests/test_routers/test_workflow_draft_operations.py`
  passed.

### Next Implementation Iteration

- Run a dedicated Phase 2 review agent. Completed: no blocking findings.
- Fix review findings, then commit Phase 2. Added the suggested regression test
  that a semantic failure preserves an existing draft file byte-for-byte.
- Before Phase 3 coding, update the plan/log with MCP package/dependency and
  thin-transport implementation decisions.

## 2026-05-30: Phase 3 Planning Update

### Planned

- Choose the MCP Python package and thin-transport strategy before coding.
- Keep backend operation REST as the only owner of graph mutation semantics.
- Make node creation possible with one MCP tool call.

### Learned

- The official Model Context Protocol Python SDK provides a `FastMCP` server API
  and is the appropriate dependency for this backend.
- A one-call `create_node` MCP workflow requires the tool to fetch the active
  draft revision automatically when the caller omits `expected_revision`.

### Plan Changes

- Phase 3 will use the official `mcp` Python package.
- Graph-editing MCP tools will call
  `/workflow-draft-operations/{workflow_id}` only.
- Read, validation, run, and stop MCP tools will call existing REST endpoints.

### Next Implementation Iteration

- Add MCP tests first for state discovery, tool registration, operation API
  delegation, validation/run/stop REST delegation, and compact results.
- Implement the MCP module without local graph mutation semantics.
- Run a dedicated Phase 3 review agent before commit.

## 2026-05-30: Phase 3 MCP Server

### Planned

- Add an MCP module with tools for active workflow discovery, tool listing,
  graph edits, validation, run, and stop.
- Keep MCP graph editing as a thin REST layer over the backend operation API.
- Allow a capable agent to create a node with one MCP tool call.

### Implemented

- Added `bioimageflow_server.agent_mcp`.
- Added the `mcp` package dependency and `bioimageflow-mcp` package script.
- Implemented `BioImageFlowMCPGateway` for agent-state discovery and REST
  calls.
- Registered MCP tools:
  `get_active_workflow`, `list_tools`, `create_node`, `delete_node`,
  `rename_node`, `update_node_parameters`, `connect_nodes`, `delete_edge`,
  `validate_workflow`, `run_workflow`, and `stop_execution`.
- Graph-editing MCP methods call
  `/workflow-draft-operations/{workflow_id}` only. Validation, run, and stop
  call existing REST endpoints.

### Learned

- The `create_node` MCP tool can satisfy the one-call requirement by fetching
  the current draft revision internally when the caller omits
  `expected_revision`.
- The MCP layer can return compact structured results without duplicating graph
  mutation semantics.

### Plan Changes

- Marked the MCP one-call node creation exit criterion complete.

### Validation

- `env UV_CACHE_DIR=/private/tmp/uv-cache uv run --extra dev python -m pytest
  tests/test_services/test_agent_mcp.py
  tests/test_routers/test_workflow_draft_operations.py
  tests/test_models/test_workflow_draft_operations.py
  tests/test_services/test_workflow_draft_operations.py`
  passed: 43 tests after review fixes.
- `env UV_CACHE_DIR=/private/tmp/uv-cache uv run ruff check
  src/bioimageflow_server/agent_mcp.py
  tests/test_services/test_agent_mcp.py`
  passed.
- `env UV_CACHE_DIR=/private/tmp/uv-cache uv run python -c "from
  bioimageflow_server.agent_mcp import create_mcp_server; server =
  create_mcp_server(); print(type(server).__name__)"`
  printed `FastMCP`.

### Next Implementation Iteration

- Run a dedicated Phase 3 review agent. Completed.
- Fix review findings, then commit Phase 3. Fixed compact error propagation
  for failed draft/validation/run paths and added MCP tool docstrings.
- Before Phase 4 coding, update the plan/log with docs and workspace-context
  integration details.

### Review Notes

- Review found no layering or scope issue.
- Review identified MCP error handling gaps where failed draft or validation
  REST calls could be masked or crash; tests now cover these paths.
- Review noted empty MCP tool descriptions; registered tools now have docstrings.

## 2026-05-30: Phase 4 Planning Update

### Planned

- Update generated workspace `AGENTS.md` and `docs/agents/`.
- Make MCP the first documented path, operation REST second, and raw full-DAG
  editing a diagnostic fallback.
- Keep platform-source read-only warnings.

### Learned

- The concrete MCP startup command is `bioimageflow-mcp`.
- The operation REST route is now stable:
  `POST /workflow-draft-operations/{workflow_id}`.
- Raw full-DAG draft replacement remains necessary as an escape hatch, but it
  should no longer be the main agent editing recipe.

### Plan Changes

- Phase 4 will update generated workspace instructions and docs to prefer MCP.
- Generated agent state can include MCP and operation endpoint hints without
  adding new mutable workflow data.

### Next Implementation Iteration

- Add/update tests for generated `AGENTS.md` and agent-state recommended
  commands.
- Update docs and workspace context text.
- Run a dedicated Phase 4 docs review agent before commit.

## 2026-05-30: Phase 4 Documentation And Workspace Integration

### Planned

- Update generated workspace instructions and docs to make MCP first, operation
  REST second, and raw full-DAG HTTP a diagnostic fallback.
- Add tests for generated state/config fields and generated `AGENTS.md`
  content.
- Preserve platform-source read-only warnings.

### Implemented

- Added `mcp_server_command` and `operation_api_url` runtime hints to generated
  `.bioimageflow/agent-state.json`.
- Updated generated workspace `AGENTS.md` instructions.
- Updated `docs/agents/README.md`, `api-reference.md`,
  `workflow-editing.md`, `execution.md`, and `troubleshooting.md`.
- Updated router tests to assert MCP-first ordering, operation REST endpoint
  hints, and fallback labeling.

### Learned

- Generated docs needed an explicit fallback label on raw graph editing because
  otherwise future agents could still skim directly to manual graph mutation.
- Examples should say `<latest draft_revision>` instead of literal `0` outside
  of executable shell snippets.

### Plan Changes

- Marked Phase 4 exit criteria complete.

### Validation

- `env UV_CACHE_DIR=/private/tmp/uv-cache uv run --extra dev python -m pytest
  tests/test_routers/test_workflow_drafts.py
  tests/test_routers/test_workflow_draft_operations.py
  tests/test_services/test_agent_mcp.py`
  passed: 31 tests.
- `env UV_CACHE_DIR=/private/tmp/uv-cache uv run ruff check
  src/bioimageflow_server/services/workflow_draft.py
  src/bioimageflow_server/services/agent_workspace_context.py
  tests/test_routers/test_workflow_drafts.py`
  passed.

### Review Notes

- Phase 4 review found no blocking issues.
- Review suggested labeling the generated raw graph section as fallback-only and
  avoiding literal `expected_revision: 0` examples; both were fixed before
  commit.

### Next Implementation Iteration

- No planned implementation phases remain in the agent operation interface
  plan.
