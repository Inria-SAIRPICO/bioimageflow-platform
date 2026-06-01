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

- Continue with the agent capability completion track only if a later request
  asks for fully featured agent capabilities beyond the completed operation
  interface.

## 2026-06-01: Agent Capability Completion Planning

### Planned

- Extend the completed agent operation interface into the remaining
  fully-featured agent capability items:
  live MCP smoke testing, richer MCP discovery, better MCP validation feedback,
  MCP client configuration, broader operation coverage, real usage hardening,
  and conflict/end-to-end UX validation.
- Keep the full-DAG draft API canonical and backend semantic operations as the
  owner of graph mutation semantics.
- Preserve the existing frontend editing model and do not add a CLI unless a
  future plan update provides concrete evidence.

### Implemented

- Added an `Agent Capability Completion Track` to
  `agent_operation_interface_plan.md` with Phases 5-12.
- Closed stale prior subagent sessions so this run can use fresh GPT-5.5 high
  calibration/review agents.
- Started Phase 5 calibration with independent explorers for:
  MCP smoke/validation/hardening, MCP tool discovery, and MCP config plus
  frontend/e2e conflict validation.

### Learned

- The previous operation-interface phases are complete and should not be
  rewritten.
- The current repo already has separate agent feature plan documents for the
  backend-draft/frontend-conflict work; this track should build on those tests
  instead of replacing the frontend model.
- Existing dirty files unrelated to this track are present:
  `agents_feature_plan.md`, `agents_feature_review_progress.md`,
  `platform_specs_v1.md`, `backend_draft_source_of_truth_plan.md`, and
  `environments.log`. They must not be reverted or folded into this work unless
  explicitly requested.

### Plan Changes

- Added Phase 5 calibration before coding so the 1-7 track starts from current
  code.
- Split implementation into bounded phases:
  MCP smoke, discovery, validation feedback, client configuration, broader
  operations, hardening, and end-to-end conflict validation.
- Kept broader operations evidence-gated to avoid adding a broad operation DSL or
  nested sub-workflow mutation by default.

### Next Implementation Iteration

- Finish Phase 5 calibration from the fresh explorer reports.
- Update the plan/log again with concrete Phase 6 test scope.
- Create a dedicated worktree for Phase 6 and write failing MCP smoke tests
  before implementation.

## 2026-06-01: Phase 5 Capability Calibration

### Planned

- Calibrate the remaining agent-capability work before coding.
- Use independent GPT-5.5 high explorers for MCP smoke/validation/hardening,
  tool discovery, and MCP client configuration plus frontend/e2e UX validation.
- Keep the next implementation phase small enough for TDD and review.

### Implemented

- Inspected `bioimageflow_server.agent_mcp`, its focused tests, tool registry
  models/router, generated agent workspace instructions, docs, and frontend
  remote-draft/conflict tests.
- Received read-only explorer reports for:
  - MCP live smoke, validation feedback, and hardening;
  - richer MCP tool discovery;
  - MCP client configuration and frontend conflict/e2e validation.

### Learned

- Current MCP tests use `httpx.MockTransport` and fake `FastMCP`; they do not
  prove the shipped gateway path against a real ASGI app or generated
  `agent-state.json`.
- MCP graph-edit tools already delegate to the backend operation API, while
  validation/run/stop call existing REST endpoints. That layering must not
  change.
- `validate_workflow` currently returns only `valid` and `error_count`; operation
  success compresses validation to `validation_valid`. Agents need backend
  validation errors preserved in compact MCP results.
- Operation 422 payloads already contain useful backend fields, but MCP should
  promote `operation_index`, `code`, and `detail` into a self-correctable result.
- MCP request handling lacks explicit structured handling for missing/malformed
  agent state, connection errors, timeouts, malformed backend JSON, and
  unexpected successful non-JSON responses.
- `GET /tools` already exposes rich `ToolMetadata`: package/version,
  `tool_type`, `accepts_upstream`, `dynamic_outputs`, `dataframe_output`,
  `documentation`, tags/categories, inputs, outputs, environment, source kind,
  and editability. Current MCP `list_tools` drops most of it and reads a
  non-existent `description` field.
- Generated docs say to use `bioimageflow-mcp`, but do not yet give enough MCP
  client configuration detail: run from workspace root or set
  `BIOIMAGEFLOW_AGENT_STATE`, command, cwd, and env.
- Frontend remote draft behavior has good unit/component coverage, including
  auto-apply, conflict banner, apply, keep, copy, and guardrails. The missing
  evidence is a real backend/WebSocket/browser e2e path.
- `backend/tests/test_services/test_agent_workspace_context.py` is stale against
  MCP-first docs and currently has a failing assertion according to the docs
  explorer.

### Plan Changes

- Phase 6 will include the first small implementation slice:
  live-ish MCP smoke plus MCP feedback/hardening that is required for the smoke
  to be actionable.
- Phase 7 richer discovery will preserve existing registry metadata and add only
  mechanical creation hints derived from `ToolMetadata`.
- Phase 9 client configuration will be client-agnostic first: command, cwd, and
  `BIOIMAGEFLOW_AGENT_STATE`, with client-specific snippets only if they remain
  low-churn.
- Phase 12 e2e UX validation will target existing conflict behavior instead of
  changing the frontend editing model.

### Next Implementation Iteration

- In a dedicated Phase 6 worktree, write failing MCP tests for:
  - ASGI-backed gateway smoke across active workflow, create-node, validate, run,
    and stop;
  - validation errors preserved in MCP results;
  - operation validation fields promoted for agent self-correction;
  - missing state, backend connection/timeout, and malformed JSON responses as
    structured errors.
- Implement the smallest `agent_mcp.py` changes needed to pass those tests.
- Run focused MCP/router tests and ruff, then use a dedicated review agent before
  integration.

## 2026-06-01: Phase 6 MCP Smoke And Hardening

### Planned

- Add live-ish MCP smoke coverage that exercises registered MCP tools against a
  real ASGI app and generated `agent-state.json`.
- Preserve backend-owned graph mutation semantics.
- Preserve useful validation and operation error detail in MCP responses.
- Harden common MCP runtime failures into compact structured results.

### Implemented

- Added an ASGI-backed smoke test that creates a workflow through the app, reads
  generated agent state, creates a node through the registered MCP `create_node`
  tool, validates through MCP, and calls MCP run/stop tools with a fake execution
  manager.
- Preserved backend validation errors in `validate_workflow` MCP results.
- Preserved operation-response validation errors in successful graph-edit MCP
  results when the draft is invalid.
- Promoted backend `operation_validation_error` fields to top-level MCP result
  fields: `operation_index`, `code`, and `detail`.
- Added structured MCP errors for missing agent state, malformed agent state,
  backend connection failures, backend timeouts, malformed backend JSON, and run
  REST failures.

### Learned

- A gateway-only ASGI smoke is not enough: it can miss `create_mcp_server`
  registration regressions. The reviewed smoke now calls the registered tool
  functions from a fake `FastMCP` server while still using the real ASGI app and
  backend REST routes.
- Pydantic wraps malformed JSON agent-state failures as `ValidationError`, so the
  hardening path should treat `ValidationError` as invalid agent state.
- `run_workflow` needed the same `_is_error` guard as validation and stop so
  backend REST errors are not wrapped as successful MCP results.

### Plan Changes

- Marked Phase 6 complete in `agent_operation_interface_plan.md`.
- Phase 7 should now focus on richer MCP discovery, especially preserving
  existing `ToolMetadata` fields and mechanical creation hints.

### Validation

- `UV_CACHE_DIR=/private/tmp/uv-cache uv run --extra dev python -m pytest
  tests/test_services/test_agent_mcp.py tests/test_routers/test_workflow_draft_operations.py`
  passed: 42 tests.
- `UV_CACHE_DIR=/private/tmp/uv-cache uv run ruff check
  src/bioimageflow_server/agent_mcp.py tests/test_services/test_agent_mcp.py`
  passed.

### Review Notes

- Initial review found one blocking issue: the smoke test used the gateway
  directly and did not prove MCP tool registration. The test was changed to use
  `create_mcp_server(..., mcp_factory=_FakeFastMCP)` and invoke registered tools.
- Review also requested malformed agent-state coverage; added.
- Follow-up review found no remaining blockers.

### Next Implementation Iteration

- Before Phase 7 coding, update this plan/log with the exact MCP discovery
  response shape and tests based on existing `ToolMetadata`.

## 2026-06-01: Phase 7 Planning Update

### Planned

- Improve MCP `list_tools` so agents can create useful nodes from discovery
  metadata.
- Reuse existing `ToolMetadata` returned by `GET /tools`; do not introduce a
  second schema or graph-construction engine.

### Learned

- `GET /tools` already exposes the relevant metadata:
  package/version, `tool_type`, upstream flags, documentation, tags/categories,
  inputs, outputs, environment, source kind, and editability.
- Current MCP `list_tools` drops most of that metadata and reads a non-existent
  `description` field, which usually returns `null`.
- Frontend creation defaults are mechanical: parameter defaults come from
  `tool.inputs[*].default`; required unconnected inputs are required inputs that
  are not connectable by default; connectable inputs come from input
  `connectable`; output template defaults can be derived from outputs that carry
  string defaults.

### Plan Changes

- Phase 7 response shape is now concrete in
  `agent_operation_interface_plan.md`.
- The first implementation will stay inside MCP response shaping and tests. It
  will not add REST endpoints, graph mutation semantics, schema coercion, or
  client-side validation rules.

### Next Implementation Iteration

- Create a dedicated Phase 7 worktree.
- Add failing MCP tests for:
  - preserving `ToolMetadata` fields in `list_tools`;
  - using `documentation` rather than missing `description`;
  - deriving `creation.default_parameters`,
    `creation.required_unconnected_inputs`, `creation.connectable_inputs`, and
    `creation.default_output_templates`.
- Implement the smallest MCP `list_tools` shaping changes, validate, review, and
  integrate.

## 2026-06-01: Phase 7 Rich MCP Tool Discovery

### Planned

- Preserve useful `ToolMetadata` through MCP `list_tools`.
- Add mechanical creation hints that help an agent build a valid
  `create_node` request without inventing graph semantics.

### Implemented

- Replaced the minimal MCP tool projection with metadata preserving:
  `name`, `display_name`, `documentation`, `package`, `package_version`,
  `tool_type`, `accepts_upstream`, `dynamic_outputs`, `dataframe_output`,
  `tags`, `categories`, `inputs`, `outputs`, `environment`, `source_kind`, and
  `editable`.
- Added `creation` hints:
  `default_parameters`, `required_unconnected_inputs`, `connectable_inputs`, and
  `default_output_templates`.
- Added tests for preserving documentation instead of the non-existent
  `description` field, preserving passthrough outputs, deriving path output
  templates, preserving environment metadata, and including defaulted
  `not_by_default` inputs in defaults.

### Learned

- Frontend node creation copies defaults from all inputs with non-`None`
  defaults, not only inputs with `connectable: "never"`.
- `not_by_default` inputs are still connectable and should remain in
  `connectable_inputs`; agents can decide whether to wire them from the field's
  own `connectable` value.
- `environment` is part of `ToolMetadata` and should be preserved by the MCP
  projection.

### Plan Changes

- Marked Phase 7 complete in `agent_operation_interface_plan.md`.
- Response bloat remains a residual risk for large registries; defer a
  `get_tool`/search helper until real payload size evidence requires it.

### Validation

- `UV_CACHE_DIR=/private/tmp/uv-cache uv run --extra dev python -m pytest
  tests/test_services/test_agent_mcp.py tests/test_routers/test_workflow_draft_operations.py`
  passed: 46 tests.
- `UV_CACHE_DIR=/private/tmp/uv-cache uv run ruff check
  src/bioimageflow_server/agent_mcp.py tests/test_services/test_agent_mcp.py`
  passed.

### Review Notes

- Initial review found two blocking metadata-fidelity issues: defaulted
  `not_by_default` inputs were omitted from defaults, and `environment` was
  dropped.
- Both were fixed with tests. Follow-up review found no remaining blockers.

### Next Implementation Iteration

- Before Phase 8/9 coding, update the plan/log with whether validation-feedback
  work is already satisfied by Phase 6 and whether the next best phase is MCP
  client configuration.

## 2026-06-01: Phase 8 Scope Resolution

### Planned

- Reconcile Phase 8 validation-feedback goals with the Phase 6 hardening work
  before starting more code.

### Learned

- Phase 6 already implemented the core Phase 8 requirements:
  backend validation errors are preserved in `validate_workflow`, operation
  result validation errors are exposed on successful graph-edit results, and
  backend `operation_validation_error` fields are promoted to top-level MCP
  fields.
- Additional repair hints would require either registry-specific inference or
  backend validator changes. That is out of scope for the MCP thin-layer rule
  until real usage shows a concrete missing hint.

### Plan Changes

- Marked Phase 8 complete via Phase 6 implementation in
  `agent_operation_interface_plan.md`.
- The next implementation phase is Phase 9 MCP client configuration.

### Next Implementation Iteration

- Before Phase 9 coding, update docs/workspace-context tests for concrete MCP
  client setup: command, cwd/workspace root, and `BIOIMAGEFLOW_AGENT_STATE`.

## 2026-06-01: Phase 9 MCP Client Configuration

### Planned

- Make MCP client setup concrete in generated workspace context and docs.
- Keep the setup client-agnostic and avoid adding a CLI.

### Implemented

- Added `mcp_client_config` to generated `.bioimageflow/agent-state.json` with:
  command `bioimageflow-mcp`, workspace `cwd`, and
  `BIOIMAGEFLOW_AGENT_STATE` pointing at the generated state file.
- Added an MCP client setup section to generated workspace `AGENTS.md`.
- Added MCP client setup guidance to `docs/agents/README.md`,
  `docs/agents/api-reference.md`, and `docs/agents/workflow-editing.md`.
- Updated tests to assert generated instructions, generated state, and each
  static doc expose command/cwd/env setup details.

### Learned

- The current MCP implementation already supports this setup model:
  `BIOIMAGEFLOW_AGENT_STATE` takes precedence, then the server falls back to
  `$cwd/.bioimageflow/agent-state.json`.
- Tests should check each static doc independently; concatenated docs can hide a
  missing setup section in one file.

### Plan Changes

- Marked Phase 9 complete in `agent_operation_interface_plan.md`.
- Kept client-specific configuration examples deferred. The generic command/cwd
  and env shape is stable and lower churn.

### Validation

- `UV_CACHE_DIR=/private/tmp/uv-cache uv run --extra dev python -m pytest
  tests/test_services/test_agent_workspace_context.py
  tests/test_routers/test_workflow_drafts.py tests/test_services/test_agent_mcp.py`
  passed: 48 tests.
- `UV_CACHE_DIR=/private/tmp/uv-cache uv run ruff check
  src/bioimageflow_server/services/workflow_draft.py
  src/bioimageflow_server/services/agent_workspace_context.py
  tests/test_services/test_agent_workspace_context.py
  tests/test_routers/test_workflow_drafts.py`
  passed.

### Review Notes

- Dedicated review found no blocking issues and confirmed no accidental CLI
  scope.
- Review suggested tightening static doc assertions so each file is checked
  independently; fixed before commit.

### Next Implementation Iteration

- Before Phase 10 coding, update the plan/log with evidence for which broader
  operations are worth adding now. If evidence remains insufficient, explicitly
  defer Phase 10 rather than inventing a broad operation DSL.

## 2026-06-01: Phase 10 Planning Update

### Planned

- Broaden agent operation coverage without adding speculative backend mutation
  semantics.

### Learned

- The backend operation layer already implements `set_node_enabled` and
  `move_node`, but MCP currently does not expose them.
- Those operations are in the original backend semantic set, require no new graph
  semantics, and are useful for agents that need to disable a step or arrange a
  readable canvas.
- There is not yet enough evidence to add parameter deletion, published
  input/output mutation, backend node-id generation, or bulk layout operations.

### Plan Changes

- Phase 10 first slice is limited to adding thin MCP tools for existing backend
  operations: `set_node_enabled` and `move_node`.
- New backend operation semantics remain deferred.

### Next Implementation Iteration

- Create a dedicated Phase 10 worktree.
- Add failing MCP tests for registered `set_node_enabled` and `move_node` tools
  delegating to `/workflow-draft-operations/{workflow_id}` with the expected
  operation payloads.
- Implement only the MCP wrappers and keep backend operation semantics unchanged.

## 2026-06-01: Phase 10 Broader MCP Operation Coverage

### Planned

- Broaden MCP graph-edit coverage only for operations already owned by the
  backend operation API.
- Avoid new backend mutation semantics.

### Implemented

- Added MCP gateway methods and registered MCP tools:
  `set_node_enabled` and `move_node`.
- Both tools call `_apply_operations` and delegate to
  `/workflow-draft-operations/{workflow_id}` with the existing backend operation
  payloads.
- Updated generated workspace guidance and workflow-editing docs to list the new
  MCP tools.
- Added tests for direct gateway delegation, registered tool forwarding, tool
  registration, and generated instruction coverage.

### Learned

- Registered-tool coverage matters for MCP phases; gateway-only tests do not
  catch parameter forwarding regressions in `create_mcp_server`.
- This slice closed a real coverage gap without adding parameter deletion,
  backend node-id generation, published input/output operations, bulk layout, or
  nested sub-workflow mutation.

### Plan Changes

- Marked the Phase 10 first slice complete in
  `agent_operation_interface_plan.md`.
- Left new backend operation semantics deferred until real usage provides
  evidence.

### Validation

- `UV_CACHE_DIR=/private/tmp/uv-cache uv run --extra dev python -m pytest
  tests/test_services/test_agent_mcp.py tests/test_routers/test_workflow_draft_operations.py
  tests/test_routers/test_workflow_drafts.py`
  passed: 59 tests.
- `UV_CACHE_DIR=/private/tmp/uv-cache uv run ruff check
  src/bioimageflow_server/agent_mcp.py
  src/bioimageflow_server/services/agent_workspace_context.py
  tests/test_services/test_agent_mcp.py tests/test_routers/test_workflow_drafts.py`
  passed.

### Review Notes

- Initial review found the need for registered-tool tests and updated docs. Both
  were fixed.
- Follow-up review found no remaining blockers.

### Next Implementation Iteration

- Phase 11 hardening is mostly satisfied by Phase 6. Before more code, update the
  plan/log to decide whether any hardening gaps remain or whether to move to
  Phase 12 end-to-end UX validation.

## 2026-06-01: Phase 11 Scope Resolution

### Planned

- Decide whether more real-usage hardening is needed after the Phase 6 MCP
  smoke/error work.

### Learned

- Phase 6 already covers the evidenced MCP hardening gaps from calibration:
  missing and malformed agent state, unavailable backend, timeout, malformed
  backend response, draft-fetch failure, run failure, operation validation error,
  and backend validation errors.
- Additional health/status tooling could be useful later, but current docs and
  generated state already include `health_url`, `api_base_url`, and
  `mcp_client_config`.

### Plan Changes

- Marked Phase 11 complete via Phase 6 implementation in
  `agent_operation_interface_plan.md`.
- The next implementation phase is Phase 12 conflict/end-to-end UX validation.

### Next Implementation Iteration

- Calibrate existing frontend e2e harness, then add the smallest reliable e2e
  validation for backend operation edits reaching the canvas through the existing
  draft/WebSocket path.

## 2026-06-01: Phase 12 Planning Update

### Planned

- Add end-to-end evidence for the missing integration path between the backend
  operation API, draft WebSocket publication, and the active browser canvas.
- Keep Phase 12 focused unless the e2e test exposes a real frontend sync
  regression.

### Learned

- Existing frontend unit/component tests already cover WebSocket draft dispatch,
  clean-canvas auto-apply, local-conflict banners, apply/keep/copy conflict
  actions, and stale-draft guards for save/run/export style critical actions.
- Existing Playwright tests cover workflow opening and graph persistence, but
  not an agent/backend draft operation reaching a live canvas through WebSocket.
- The Playwright backend exposes `/api/v1/dev/seed`, so the new e2e test can
  create a deterministic tool node without relying on external packages.

### Plan Changes

- Phase 12 first slice is one browser-realistic test: open a seeded workflow,
  call `/api/v1/workflow-draft-operations/{workflow_id}` with `create_node`,
  and assert the node appears on the active canvas without a conflict banner or
  reload.
- Broader conflict-action e2e coverage remains deferred unless this slice shows
  a real gap, because those actions already have focused component coverage.

### Next Implementation Iteration

- Create a dedicated Phase 12 worktree.
- Write the failing Playwright test first.
- Patch only regressions found by that test, then run the single chromium e2e
  spec and targeted frontend checks as available.

## 2026-06-01: Phase 12 End-To-End UX Validation

### Planned

- Add a browser-realistic e2e test for an agent/backend draft operation reaching
  the active canvas through the existing WebSocket draft-sync path.
- Keep production code unchanged unless the test exposed a regression.

### Implemented

- Added `frontend/tests/e2e/agent-draft-sync.spec.ts`.
- The test seeds deterministic dev tools, creates an empty workflow, opens it in
  the browser, calls
  `/api/v1/workflow-draft-operations/{workflow_id}` with `create_node`, and
  asserts the node appears on the active canvas without a
  `.workflow-draft-conflict` banner.
- After review, tightened the test to instrument browser WebSocket messages,
  wait for the post-reload WebSocket connection, assert receipt of the
  `workflow_draft_changed` message for the agent edit, and assert no main-frame
  navigation occurs after the operation.

### Learned

- The existing backend operation API, draft publication, WebSocket dispatch, and
  clean-canvas auto-apply path work together end to end.
- No frontend editing-model changes were needed.
- The worktree needed its own frontend dependency install; `TMPDIR=/private/tmp`
  was required for Bun in the sandbox, and the Playwright run used alternate
  ports because the default frontend port was already occupied.

### Plan Changes

- Marked the first Phase 12 e2e slice complete in
  `agent_operation_interface_plan.md`.
- Broader conflict-action e2e remains deferred because focused component tests
  already cover those behaviors and this e2e slice closed the missing
  integration evidence.

### Validation

- `env TMPDIR=/private/tmp UV_CACHE_DIR=/private/tmp/uv-cache
  BIOIMAGEFLOW_E2E_FRONTEND_PORT=5174 BIOIMAGEFLOW_E2E_BACKEND_PORT=8001
  bun run test:e2e -- --project=chromium agent-draft-sync.spec.ts` passed: 1
  test.
- `env TMPDIR=/private/tmp bunx eslint
  tests/e2e/agent-draft-sync.spec.ts` passed.

### Review Notes

- Initial review found a validation-evidence blocker: the first test version
  could have passed after a reload and did not directly observe the WebSocket
  draft event.
- Fixed by adding WebSocket message instrumentation and a no-navigation
  assertion after the operation.
- Follow-up review found no remaining blockers.

### Next Implementation Iteration

- Integrate the reviewed Phase 12 work into main.
- Run final focused status/validation checks and close the capability completion
  track unless new failures appear.

## 2026-06-01: Post-Phase-12 Scope Expansion Planning

### Planned

- Add a concrete future phase for agent tool authoring docs and validation.
- Add explicit future phases for three remaining graph-capability gaps:
  published workflow interface operations, bulk layout, and scoped nested
  sub-workflow mutation.

### Learned

- Workflow-local tool authoring is already partly supported by existing APIs and
  file watching: agents can create custom tools, resolve editable source paths,
  edit Python files, rename/delete custom tools, and rely on tool hot reload
  events.
- The main gap for tool authoring is documentation plus validation that the
  documented path remains accurate and agent-visible.
- Published input/output edits, bulk layout, and nested sub-workflow mutation
  should be separate semantic-operation phases. Combining them into a generic
  patch language would undermine the backend-owned operation model.

### Plan Changes

- Added Phase 13: Agent Tool Authoring Docs And Validation.
- Added Phase 14: Published Workflow Interface Operations.
- Added Phase 15: Bulk Layout Operation.
- Added Phase 16: Scoped Nested Sub-Workflow Mutation.
- Kept CLI fallback deferred.

### Next Implementation Iteration

- Start Phase 13 with calibration: inspect current custom-tool APIs, hot-reload
  tests, frontend WebSocket handling, generated workspace docs, and docs/agents.
- Update the plan/log again with exact Phase 13 test scope before coding.
- Use TDD, a dedicated worktree, and a dedicated review agent for Phase 13.

## 2026-06-01: Phase 13 Calibration

### Planned

- Calibrate workflow-local tool authoring before implementation.
- Identify whether Phase 13 is docs-only or needs validation/fixes around
  hot-reload and frontend updates.

### Learned

- Existing REST and service surfaces already support workflow-local custom tool
  creation, source lookup, rename, delete, usage lookup, and package-tool
  protections.
- Existing hot-reload tests cover generic package reload behavior, but not the
  real `ToolRegistryService + CustomToolService + ToolHotReloadService`
  workflow-local custom-tool path.
- `reload_custom_tool` appears to unregister a custom tool before re-registering
  it, so a syntax/import failure during reload may drop the last working
  metadata from the registry.
- Frontend WebSocket dispatch for `tool_reload`, `tool_removed`, and
  `system_error` exists, but focused unit coverage is thin compared with
  `workflow_draft_changed`.
- Agent docs do not yet explain the workflow-local tool authoring path.

### Plan Changes

- Phase 13 first slice includes:
  - docs and generated workspace instruction updates for workflow-local tool
    authoring;
  - backend real custom hot-reload tests for edit/delete/failure preservation;
  - a minimal backend fix if the failure preservation test confirms the bug;
  - focused frontend/store/WebSocket tests for tool reload/removal dispatch if
    practical in the same bounded slice.
- Broader UI/e2e coverage for canvas rename/delete handling remains optional
  unless the focused tests expose a regression.

### Next Implementation Iteration

- Create a dedicated Phase 13 worktree.
- Write failing backend custom hot-reload tests first, then doc/static tests.
- Implement the minimal fix and doc updates.
- Run focused backend/frontend checks and use a dedicated review agent before
  integrating.

## 2026-06-01: Phase 14-16 Calibration

### Planned

- Calibrate the future semantic operation phases before coding Phase 13, so the
  follow-on plan remains concrete.

### Learned

- Phase 14 should add four published interface operations:
  `set_published_input`, `delete_published_input`, `set_published_output`, and
  `delete_published_output`.
- Published interface `set_*` operations should upsert by stable internal target
  key, while `delete_*` operations should delete by external published name.
- Phase 15 should add `move_nodes` as absolute-position bulk layout. Existing
  `move_node` stays as a compatibility tool.
- Phase 16 should add explicit operation scope with `sub_workflow_path`; nested
  graphs can reuse ids, so flat node ids are unsafe.
- Phase 16 first slice should support scoped `move_node`/`move_nodes` only,
  avoiding create/delete/connect semantics until nested interface reconciliation
  is defined.

### Plan Changes

- Added concrete Phase 14 operation names, keys, and validation rules.
- Added concrete Phase 15 request shape and atomic preflight behavior.
- Narrowed Phase 16 first slice to scoped layout operations with an explicit
  `sub_workflow_path` scope model.

### Next Implementation Iteration

- Continue with Phase 13 implementation first.
- Before Phase 14 coding, update the plan/log again from Phase 13 learnings and
  create a dedicated Phase 14 worktree.

## 2026-06-01: Phase 13 Agent Tool Authoring Docs And Validation

### Planned

- Document the workflow-local tool authoring path for agents.
- Validate real custom-tool hot reload and frontend tool reload/removal handling.
- Fix only bugs exposed by the new tests.

### Implemented

- Added generated workspace instructions for workflow-local tool authoring:
  create scaffold, resolve source path, edit Python files, verify `tool_reload`,
  handle `tool_removed` and `tool_reload_failed`, and avoid
  `.bioimageflow/platform-source/`.
- Updated `docs/agents/README.md` and `docs/agents/workflow-editing.md` with
  workflow-local tool authoring guidance.
- Added real `ToolRegistryService + CustomToolService + ToolHotReloadService`
  tests for custom tool edit, delete, and reload failure.
- Fixed `reload_custom_tool` so a failed custom tool reload preserves the
  previous working metadata, source path, package entry, and class binding.
- Added frontend unit coverage for WebSocket `tool_reload` / `tool_removed`
  dispatch and tool registry package-membership updates.

### Learned

- The existing custom tool authoring API surface was sufficient; the largest
  actual bug was reload failure rollback for invalid custom Python edits.
- `TMPDIR=/private/tmp/` is required for Bun install/test commands in this
  worktree.
- Broader UI/e2e coverage for canvas node rename/delete handling can remain a
  later hardening item; the focused Phase 13 path now protects platform-visible
  tool registry updates.

### Plan Changes

- Marked the first Phase 13 slice complete in
  `agent_operation_interface_plan.md`.
- Phase 14 remains next: published workflow interface semantic operations.

### Validation

- `UV_CACHE_DIR=/private/tmp/uv-cache uv run --extra dev python -m pytest
  tests/test_services/test_tool_hot_reload.py
  tests/test_services/test_agent_workspace_context.py` passed: 27 tests.
- `TMPDIR=/private/tmp/ TEMP=/private/tmp/ TMP=/private/tmp/ bun run test:unit
  -- src/composables/__tests__/useWebSocket.test.ts
  src/stores/__tests__/toolRegistry.test.ts` passed: 8 tests.
- `UV_CACHE_DIR=/private/tmp/uv-cache uv run ruff check
  src/bioimageflow_server/services/tool_registry.py
  src/bioimageflow_server/services/agent_workspace_context.py
  tests/test_services/test_tool_hot_reload.py
  tests/test_services/test_agent_workspace_context.py` passed.
- `TMPDIR=/private/tmp/ TEMP=/private/tmp/ TMP=/private/tmp/ bunx eslint
  src/composables/__tests__/useWebSocket.test.ts
  src/stores/__tests__/toolRegistry.test.ts` passed.

### Review Notes

- Dedicated Phase 13 review found no blockers.
- Review suggested a non-blocking test gap: assert failed custom-tool reload
  also preserves the prior class binding and `__custom__` package state. Added
  those assertions and reran focused validation.

### Next Implementation Iteration

- Run a dedicated Phase 13 review agent.
- Fix blockers if any, rerun focused checks, integrate, then update plan/log
  before Phase 14 coding.

## 2026-06-01: Phase 14 Planning Update

### Planned

- Start published workflow interface semantic operations after Phase 13.
- Keep the first implementation slice backend-owned and bounded.

### Learned

- Phase 13 did not change the graph operation API, so Phase 14 can proceed from
  the calibrated operation shapes.
- The pure operation transform does not have registry context today. First-slice
  validation should therefore focus on graph-local facts: node existence, stable
  target keys, non-empty/trimmed names, cross-list name uniqueness, delete
  selectors, and required schema for new pins.

### Plan Changes

- Phase 14 first slice will implement backend models, pure transforms, REST, MCP
  thin wrappers, and docs for:
  `set_published_input`, `delete_published_input`, `set_published_output`, and
  `delete_published_output`.
- Tool-metadata-aware input/output schema validation remains deferred until the
  operation layer receives registry context.

### Next Implementation Iteration

- Create a dedicated Phase 14 worktree.
- Write model and transform tests first, then REST and MCP tests.
- Implement the bounded operations and docs, run focused validation, review,
  and integrate before Phase 15.

## 2026-06-01: Phase 14 Published Workflow Interface Operations

### Planned

- Add backend-owned semantic operations for published workflow inputs and
  outputs.
- Keep the operation set bounded to four operations:
  `set_published_input`, `delete_published_input`, `set_published_output`, and
  `delete_published_output`.
- Expose MCP only as a thin wrapper over the operation API, then document MCP
  first and operation REST second.

### Implemented

- Added published interface operation models with trimmed, non-empty published
  names and non-empty internal target strings.
- Added pure transform support for set/delete published input/output operations.
  `set_*` upserts by stable internal target key and `delete_*` removes by
  published name.
- Added REST tests covering successful interface edits, atomic failure, no draft
  file write, unchanged agent state, and no WebSocket publication on failed
  batches.
- Added MCP gateway methods and registered MCP tools for the four operations.
- Updated generated workspace instructions and `docs/agents/workflow-editing.md`
  with published interface guidance.

### Learned

- The pure transform layer can validate node existence, blank target strings,
  duplicate published names, delete selectors, and required schema for new pins.
  It cannot yet validate target names against tool metadata because it has no
  registry context.
- REST can distinguish omitted nullable fields from explicit `null` through
  Pydantic `model_fields_set`. MCP needed explicit `set_schema` / `set_default`
  flags so agents can clear nullable fields while omission continues to mean
  preserve the existing value.

### Plan Changes

- Marked Phase 14 complete in `agent_operation_interface_plan.md`.
- Deferred tool-metadata-aware validation of `internal_field` and
  `internal_output` names until a later phase provides registry context.
- Phase 15 remains next: `move_nodes` as a bulk layout-only operation.

### Validation

- `UV_CACHE_DIR=/private/tmp/uv-cache uv run --extra dev python -m pytest
  tests/test_models/test_workflow_draft_operations.py
  tests/test_services/test_workflow_draft_operations.py
  tests/test_routers/test_workflow_draft_operations.py
  tests/test_services/test_agent_mcp.py
  tests/test_services/test_agent_workspace_context.py` passed: 91 tests.
- `UV_CACHE_DIR=/private/tmp/uv-cache uv run ruff check
  src/bioimageflow_server/models/workflow_draft_operations.py
  src/bioimageflow_server/services/workflow_draft_operations.py
  src/bioimageflow_server/agent_mcp.py
  src/bioimageflow_server/services/agent_workspace_context.py
  tests/test_models/test_workflow_draft_operations.py
  tests/test_services/test_workflow_draft_operations.py
  tests/test_routers/test_workflow_draft_operations.py
  tests/test_services/test_agent_mcp.py
  tests/test_services/test_agent_workspace_context.py` passed.

### Review Notes

- Dedicated Phase 14 review found no atomicity or backend-ownership blockers.
- Review flagged blank internal target strings and MCP explicit-null support.
  Both were fixed with regression tests, and the follow-up review found no
  remaining blockers in those patched areas.

### Next Implementation Iteration

- Before coding Phase 15, update the plan/log with Phase 14 learnings and use a
  dedicated Phase 15 worktree.
- Implement `move_nodes` with tests first, then review and integrate before
  Phase 16.

## 2026-06-01: Phase 15 Planning Update

### Planned

- Start the bulk layout operation phase after Phase 14 integration.
- Keep Phase 15 independent from nested sub-workflow scope; scoped layout is
  reserved for Phase 16.

### Learned

- Phase 14 added published interface operations without changing node layout
  models or existing `move_node` semantics.
- The operation API already supports atomic batches, so `move_nodes` should
  focus on preflight validation and preserving every non-position node field.

### Plan Changes

- Phase 15 will add a single new `move_nodes` operation with
  `moves: [{node_id, position}]`.
- The operation will reject empty move lists, duplicate node ids, missing nodes,
  and invalid coordinates before applying changes.
- MCP exposure will be added only as a thin wrapper after backend tests pass.

### Next Implementation Iteration

- Create a dedicated Phase 15 worktree.
- Write model/service/router/MCP tests first for `move_nodes`, verify they fail,
  implement, run focused validation, review, fix blockers, update plan/log, and
  commit.

## 2026-06-01: Phase 15 Bulk Layout Operation

### Planned

- Add a layout-only `move_nodes` operation for repositioning several root-graph
  nodes without replacing full workflow JSON.
- Keep `move_node` unchanged and expose MCP as a thin wrapper only after backend
  tests pass.

### Implemented

- Added `MoveNodeItem` and `MoveNodesOperation`.
- Added pure transform support that preflights duplicate move targets and
  missing nodes, then updates only node positions while preserving node order
  and all non-position graph data.
- Added model, transform, router, and MCP tests for success and atomic failure.
- Added MCP `move_nodes` gateway/tool registration that calls the backend
  operation API.
- Updated generated workspace instructions and `docs/agents/workflow-editing.md`
  to prefer `move_nodes` for bulk layout.

### Learned

- The existing operation API atomicity model covers `move_nodes` cleanly; failed
  layout batches are rejected before draft write or WebSocket publication.
- A single `move_nodes` operation can include many move items. This deliberately
  exceeds the existing operation-count batch cap because it is one bounded
  layout operation rather than a general graph patch.

### Plan Changes

- Marked Phase 15 complete in `agent_operation_interface_plan.md`.
- Phase 16 remains next: add explicit scope for nested sub-workflow layout only.

### Validation

- `UV_CACHE_DIR=/private/tmp/uv-cache uv run --extra dev python -m pytest
  tests/test_models/test_workflow_draft_operations.py
  tests/test_services/test_workflow_draft_operations.py
  tests/test_routers/test_workflow_draft_operations.py
  tests/test_services/test_agent_mcp.py
  tests/test_services/test_agent_workspace_context.py` passed: 102 tests.
- `UV_CACHE_DIR=/private/tmp/uv-cache uv run ruff check
  src/bioimageflow_server/models/workflow_draft_operations.py
  src/bioimageflow_server/services/workflow_draft_operations.py
  src/bioimageflow_server/agent_mcp.py
  src/bioimageflow_server/services/agent_workspace_context.py
  tests/test_models/test_workflow_draft_operations.py
  tests/test_services/test_workflow_draft_operations.py
  tests/test_routers/test_workflow_draft_operations.py
  tests/test_services/test_agent_mcp.py
  tests/test_services/test_agent_workspace_context.py` passed.

### Review Notes

- Dedicated Phase 15 review found no blockers.
- Residual review notes: no move-item max cap yet, duplicate move target
  atomicity is covered at pure transform level but not separately through HTTP,
  and MCP uses a generic `list[dict[str, Any]]` schema while backend validation
  owns correctness.

### Next Implementation Iteration

- Before coding Phase 16, update the plan/log with scoped layout details.
- Create a dedicated Phase 16 worktree.
- Write tests first for root default scope and explicit `sub_workflow_path`
  scoped `move_node` / `move_nodes`, then implement and review.
