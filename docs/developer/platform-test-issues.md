---
orphan: true
---

# Platform test campaign issues

Use the [campaign escalation protocol](platform-test-plan.md).
Statuses: `open`, `sol-investigating`, `astra-review`, `safe-to-fix`, `needs-owner`, `externally-blocked`, `resolved`, or `not-a-defect`.
Record the actual specialist model/reasoning and disposition; an unassigned queue entry is not completed Astra review.
Owner decisions and product intent take precedence over an agent's proposed fix.

## ISSUE-001 — Source-update preview and replaced workflow identity

Status: resolved after GPT-6 Astra/high `safe-to-fix` assessment and bounded Sol/medium repair.
At platform `353b425` with BioImageFlow 0.7.1, core 0.3.1, and Wetlands 2.4.1, a disposable supported-lifecycle reproduction showed an old generation-1 preview successfully mutating an exactly recreated generation-3 destination whose original and recreated artifact hashes were both `sha256:9256f7d81e082034f47aa62edbd9892a3687f944782dc4c49e3fcee66da25061`.
No existing lifecycle invalidation removed prepared tokens, and Apply captured only the current generation after the preview boundary.
The specialist found v2 §§10 and 12, v1 §2.4.2, and `PLATFORM_CONTEXT.md` decisive: the delayed operation must conflict without mutation, and a private captured-generation comparison inside the existing mutation lock is sufficient.

The repair stores the destination generation for both source-refresh and Python-rebuild previews, captures it atomically with the destination document, and compares it inside Apply's mutation lock before reads, staging, or writes.
It raises the existing `WorkflowSourceConflict`, preserving HTTP 409 and leaving artifact hashing and public schemas unchanged.
Regressions prove exact same-artifact recreation rejection with unchanged graph, hash, generation, and owned files, plus lifecycle serialization during preview.
Focused source tests passed and `scripts/test check backend` passed in 82s at `6d42c05` plus the settled backend diff: 1,577 deterministic tests passed, 9 deselected, and 7 logging-order tests passed; external package certification was intentionally not run by this lane.
The fix commit is discoverable with `git log -1 -- backend/src/bioimageflow_server/services/workflow_sources.py`.
Workspace switching and source-workflow recreation were not reproduced and are not claimed as resolved defects.

## ISSUE-002 — Logging specification versus contextual-log tests

Status: resolved as a stale specification row; no product behavior changed.
At `fcb4408`, the v1 WebSocket log-event table around line 910 describes logs as intentionally unscoped without execution/canvas context.
The audit reported deliberate contextual execution-log behavior in the logging bridge and `frontend/tests/e2e/error-handling.spec.ts`, while environment logs remain global.
Commit `a8d9533` intentionally introduced that behavior together with the v2 §1.8 normative requirement, typed WebSocket validation, source-time provenance safeguards, frontend filtering, and regression coverage.
The older v1 §2.5 table row was therefore stale and has been aligned with the established contract: execution-attributed BioImageFlow and Wetlands records carry the complete immutable execution context, while non-execution tool, environment, thumbnail, and platform logs omit it.
Affected files: `platform_specs_v1.md`, `PLATFORM_CONTEXT.md`, and the runtime coverage inventory.
Validation: `scripts/test check docs` passed in 2s at `353b425` plus the ISSUE-002 documentation diff; an initial sandboxed attempt was externally blocked fetching `furo` and is not counted as a test failure.
The resolution commit is discoverable with `git log -1 -- docs/developer/platform-test-issues.md`.

## ISSUE-003 — Tools Panel row click did not create a node

Status: resolved after GPT-6 Astra/high `safe-to-fix` assessment and bounded Sol/medium repair.
At `87fe704`, the named `SeedNumbers` browser journey clicked the rendered catalog row but observed zero nodes.
Static and reproduced evidence showed `ToolsPanel.vue` emitted `add-tool`, while its raw Dockview registration had no listener and Vue component events do not bubble.
V1 §§3.3.1 and 3.4 explicitly require click creation, and the existing state-free active-canvas command facade already owns synchronous root/nested routing, viewport projection, execution locks, undo, and persistence.

The repair calls `addToolNode(toolName)` once through that facade and retains the existing local event contract; App, canvas sessions, APIs, and backend remain unchanged.
Unit regressions cover a real rendered row, non-creating secondary actions, active nested/root routing, missing ownership, and disposed resources.
Distinct real click and drag journeys assert named metadata/schema, unchanged first-click viewport, exact pins/panel content, accepted persistence, and requested drag position in Chromium and Firefox.
The focused unit files passed 96 tests in 6s; Chromium click/drag passed in 15s/16s and Firefox in 14s/17s.
Frontend lint, all 1,260 unit tests, and build passed in the completion run; its only failure was new test-mock type declarations, whose exact type-check passed after correction.
The Chromium completion run passed both changed journeys before later failing from independent ISSUE-004 mutation contention.
The fix commit is discoverable with `git log -1 -- frontend/src/components/panels/ToolsPanel.vue`.

## ISSUE-004 — Ordinary mutation contention reported as execution lock

Status: `safe-to-fix`; Sol/medium implementation active.
Two Chromium completion runs passed 54 or 55 preceding cases, then the child-port workflow-interface save received HTTP 423 claiming execution was in progress; the exact case passed in a fresh runtime.
GPT-6 Astra/high disproved an execution lifecycle leak and reproduced the exact 423 with no execution ever started by holding an ordinary draft validation while issuing Save.
`ExecutionManager.is_running` includes the ordinary idle-mutation reservation even while status is `idle` with no execution identity, and Save immediately rejects that aggregate flag.
The established repair boundary is to queue ordinary Save behind an admitted mutation while retaining Run exclusion during mutations and mutation rejection during actual starting/running execution.
No arbitrary browser wait, forced unlock, or early execution ownership release is authorized.
Implementation, deterministic regressions, documentation clarification, and completion evidence are pending.

## New issue record template

Use a stable ISSUE-NNN heading with status, task/dependency scope, source revision and packages, observed versus expected behavior, authoritative references, exact reproduction/selector/browser, evidence paths, attempted changes, and unresolved question.
Add specialist model/reasoning, disposition and rationale, owner decision if needed, implementation/test/specification files, completion evidence, commit, and resume condition.
For resolved issues, retain the decision and commit references without carrying full logs into the master checkpoint.
