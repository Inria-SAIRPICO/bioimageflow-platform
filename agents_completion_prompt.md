# Prompt: Complete The BioImageFlow Agent Feature Plan

You are the master coding agent for finishing `agents_feature_plan.md`.

## Non-Negotiable Operating Rules

1. Work in a dedicated git worktree/branch created for this task. Keep the original worktree clean except for the worktree metadata.
2. Optimize context length for every agent, including the master:
   - Put durable facts in repo files, not chat.
   - Each sub-agent receives only the files/sections and exact task it needs.
   - Prefer `rg`, targeted `sed`, and test output summaries over broad file dumps.
   - Review agents receive the plan plus the milestone diff/status, not the full conversation.
3. Use TDD:
   - For every behavioral change, write or update focused failing tests first.
   - Implement the smallest production change that passes those tests.
   - Run targeted tests after each slice and broader regression tests at each milestone boundary.
4. Use parallel agents where useful:
   - Explorers answer bounded codebase questions.
   - Workers may implement disjoint file sets only when merge risk is low.
   - Review agents must be neutral and dedicated to plan/code review.
5. After each milestone:
   - Commit the milestone.
   - Ask a dedicated review agent to compare implementation reality against `agents_feature_plan.md`.
   - Update `agents_feature_plan.md` and `agents_feature_review_progress.md` to remove drift.
   - Commit the plan update separately or amend only if no code changed after the review.
6. Keep code quality high:
   - Reuse existing services, routers, stores, and test patterns.
   - Do not introduce speculative abstractions.
   - Preserve manual-save semantics unless the plan explicitly changes them.
   - Use structured Pydantic/TypeScript models instead of ad hoc dictionaries where contracts cross API boundaries.
7. Verification gates:
   - Backend: targeted pytest for changed routers/services, then `uv run ruff check src tests`.
   - Frontend: targeted Vitest for changed stores/components, then `bun run type-check` and `bun run lint`.
   - If a test cannot run, document why in the plan progress file.

## Current Reality

Milestone 1 is implemented:

- `GET`/`PUT /api/v1/workflow-drafts/{workflow_id:path}`.
- Workflow-local atomic `.bioimageflow/draft.json`.
- Workspace-root `.bioimageflow/agent-state.json`, `AGENTS.md`, and `CLAUDE.md`.
- Frontend `useWorkflowDraftStore` and draft autosave.
- Save/run/export/editor-open freshness checks.

Known deferrals:

- No `bioimageflow-agent` CLI yet.
- No structured `PATCH /workflow-drafts/{workflow_id:path}` mutation endpoint yet.
- No typed `draft_updated` WebSocket event yet.
- No frontend remote draft reconciliation UX yet.
- No draft promote/revert endpoints yet.

## Milestone Execution Order

### Milestone 2A: Read-Only Agent CLI

Goal: agents can reliably inspect platform/workflow state from VS Code terminal.

Implement:

- `bioimageflow-agent status`
- `bioimageflow-agent current-workflow`
- `bioimageflow-agent get-graph`
- `bioimageflow-agent validate`
- `bioimageflow-agent list-tools`
- `bioimageflow-agent tool-schema <tool_name>`

Requirements:

- Discover workspace-root `.bioimageflow/agent-state.json`.
- Verify health URL and backend boot/session id when available.
- Re-read `GET /workflow-drafts/{workflow_id}` before graph-dependent commands.
- Print JSON by default for graph/schema/status commands.
- Exit non-zero with clear stderr on stale/missing agent-state or unreachable backend.

### Milestone 2B: Structured Draft Mutation API And Writable CLI

Goal: agents mutate workflows through validated platform operations.

Implement:

- `PATCH /api/v1/workflow-drafts/{workflow_id:path}`
- Pydantic discriminated union operation models.
- Operations:
  - `add_node`
  - `delete_node`
  - `rename_node`
  - `set_param`
  - `unset_param`
  - `set_enabled`
  - `set_output_template`
  - `connect_column`
  - `connect_positional`
  - `delete_edge`
  - `move_node`
- `schema_refresh_node_ids` response field.
- Writable CLI commands:
  - `add-node`
  - `delete-node`
  - `rename-node`
  - `set-param`
  - `connect-column`
  - `connect-positional`
  - `save` only after draft promotion exists.

Requirements:

- Use optimistic `expected_revision`.
- Use per-workflow lock for read/compare/mutate/write.
- Validate with isolated draft validation.
- Emit machine-readable conflict/lock/operation errors.
- Do not mutate inside sub-workflows in the MVP.
- Do not enable CLI `save` until promote endpoint exists.

### Milestone 2C: Typed Draft WebSocket Invalidation

Goal: open frontends learn immediately when agents change drafts.

Implement:

- Backend `DraftUpdatedMessage` model.
- `ConnectionManager` broadcast/publish method.
- Draft service emits `draft_updated` for PUT/PATCH/promote/revert.
- Frontend websocket dispatch calls `useWorkflowDraftStore().handleDraftUpdated`.
- Store records `remoteAvailableRevision`, `lastWriter`, and `dirty_against_saved`.
- Save/run/export guards block when remote draft is newer than applied draft.

### Milestone 3: Frontend Reconciliation UX

Goal: frontend can safely apply or reject remote agent edits.

Implement:

- Auto-apply remote draft when no local pending edit/write and not executing.
- Non-modal conflict banner/dialog when local edits are pending.
- Actions:
  - Apply Remote
  - Keep Mine
  - Review JSON
- Tests for safe auto-apply and conflict state.

### Milestone 4: Draft Promotion/Revert And Save/Run Integration

Goal: saved workflow and execution semantics are draft-aware.

Implement:

- `POST /workflow-drafts/{workflow_id:path}/promote`
- `POST /workflow-drafts/{workflow_id:path}/revert`
- Save uses promote endpoint.
- CLI `save` uses promote endpoint.
- Export prompts or blocks on dirty draft.
- Run flushes/checks draft and executes the current frontend-applied graph.

### Milestone 5: Polish And Docs

Goal: user-facing agent support is discoverable and documented.

Implement:

- UI entry points for opening workspace/current workflow in VS Code or embedded editor for agent use.
- Clear `AGENTS.md` and `CLAUDE.md` instructions with examples.
- Troubleshooting messages for stale agent-state, conflicts, locked execution, unavailable backend.
- Update `platform_specs_v1.md` and plan docs to match final behavior.

## Review Loop After Each Milestone

After milestone implementation and tests:

1. Commit code.
2. Spawn a dedicated review agent with:
   - Current `agents_feature_plan.md`.
   - `git show --stat` and a short milestone summary.
   - Exact question: “Find plan drift, missing tests, or implementation gaps. Do not edit files.”
3. Apply only useful, reality-grounding changes to the plan/progress docs.
4. Commit plan/progress update.

## Completion Criteria

The task is complete only when:

- All milestones above are implemented or explicitly re-scoped in the plan with a concrete reason.
- Tests and lint/type checks pass.
- `agents_feature_plan.md` describes current reality, not aspiration.
- `agents_feature_review_progress.md` records every milestone review and plan correction.
- Final answer lists commits, verification, remaining risks, and whether more review iterations seem useful.
