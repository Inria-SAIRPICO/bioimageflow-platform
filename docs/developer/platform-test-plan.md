---
orphan: true
---

# Platform testing implementation plan

Test and strengthen the platform by exercising its main GUI features, fixing demonstrated bugs, and delivering a complete, systematic suite for every implemented feature within the campaign scope.
A finished user journey with correct visible results and durable state is the unit of progress.
Priorities determine execution order, never permission to omit lower-priority features from final coverage.
The authoritative validation commands and completion requirements remain in [Test lanes](../testing.md).

## Scope and current product contract

Cover implemented desktop and webapp behavior from v1/v2 and applicable later implemented specification changes, following the authority order in `PLATFORM_CONTEXT.md`.
Exclude parallel scheduling, HPC, Parsl, managed remote execution, and distributed engines from campaign certification.
Record these exclusions explicitly; neither existing out-of-scope regression tests nor future v3 proposals expand campaign scope.
Keep Direct for ordinary DataFrame-only workflows and use real local Wetlands workers sequentially with one worker when worker behavior is being certified.
Distinguish mocked orchestration, Direct computation, and actual worker execution; worker claims require process identity, exact results, generated files, and cleanup.

The owner-approved catalog contract is single-click to open/toggle the bottom tool-information panel and double-click to add exactly one node to the active canvas.
Drag-and-drop remains a separate creation gesture; secondary row actions must not trigger inspection or creation accidentally.
Use this contract in all fixtures and acceptance criteria; historical ISSUE-003 single-click creation evidence describes an earlier interaction.

Preserve assertions and product intent when repairing tests or code.
Do not weaken expectations, hide skips or warnings, invent graph conversions, or introduce compatibility shims to obtain a pass.
Update affected code, tests, fixtures, specifications, and documentation together when behavior changes.

## Orchestrator, delegation, and context discipline

The main agent must be **GPT-5.6 Sol with high reasoning**, acting primarily as an orchestrator.
Ordinary implementation workers use **GPT-5.6 Sol with medium reasoning**; bounded specialist investigations use **GPT-6 Astra with high reasoning**.
These are requested runtime settings; editing this plan does not change the currently selected model.
Use [Restart instructions](platform-test-start.md) to start the requested orchestrator and verify the client settings.

The orchestrator owns the global feature map, priority and dependency decisions, task assignment, review, integration, validation reuse, and accurate reporting.
Workers own detailed source investigation, fixture design, implementation, focused tests, and their worktree completion checks.
The orchestrator may make small integration/documentation edits and inspect relevant code to review a result; it should not duplicate an entire worker investigation.

Keep the orchestrator's working context to the current objective, a short feature-status table, active tasks, open decisions, and the next three runnable tasks.
Read the active checkpoint, relevant inventory rows, and changed code as needed; retrieve historical evidence only when a decision depends on it.
Workers receive fresh bounded packets with `fork_turns="none"`, explicit model/reasoning, a worktree path, feature/issue IDs, current contract, owned paths, acceptance criteria, dependencies, required checks, and escalation conditions.
Worker handoffs should normally fit in about 30 lines: outcome, bug/cause, commit, changed files, exact commands/results/durations/exclusions, unresolved concerns, and evidence paths.
Keep raw logs, traces, and exploratory transcripts in ignored task artifacts; return only phase summaries and relevant failure excerpts to the orchestrator.
Do not repeatedly request unchanged status or ingest complete passing test output.
While a worker runs, review another independent feature's coverage or prepare the next bounded task; use completion notifications and concise milestone updates.

Use up to two independent ordinary workers, leaving a slot for Astra.
Parallel writable tasks require separate worktrees under `.worktrees/<task_name>` with independent dependencies and runtime state as required by `AGENTS.md`.
Give each task one coherent feature or issue and explicit write ownership; do not split tightly coupled fixes merely to occupy agents.
Read-only investigations may share the primary checkout.
A blocked feature does not block independent work unless its fixture, contract, or safety issue affects them too.

### Commit and integration boundaries

Commit each coherent validated issue or feature immediately when resolved, together with its tests and relevant inventory/specification updates.
Do not start another writable task in that checkout until the previous completed task is committed.
Workers review and commit only their own task changes on their branches; the orchestrator reviews the commit, integrates it, and records the resulting revision and evidence.
Shared progress/issue records belong to the orchestrator; integrate their updates at the same task boundary and commit them promptly if they cannot be included in the implementation commit.
Do not accumulate resolved independent issues, stage another worker's files, or include temporary plans and raw logs in commits.
An unfinished failing reproduction remains explicitly unfinished; preserve its owner, worktree, selector, and evidence before interruption without claiming a passing fix.
After integration, move the clean completed worktree to trash with `mv`, prune its registration, and delete only its integrated branch, following `AGENTS.md`.
Preserve unrelated user worktrees and changes.

## GUI-first priority queue

Completed dependency releases, fixture repairs, and audited scope selection are retained prerequisites, not tasks to restart.
Use the current checkpoint to select the first unfinished item below.
Default to a main GUI journey over additional testing infrastructure or speculative rare cases.
Interrupt that order for a reproduced data-loss, security, wrong-result, or core-feature blocker; record why its impact justifies the interruption.

| Order | Feature batch | Required observable outcome |
| --- | --- | --- |
| 1 | Resolve the already reproduced Run Selected issue (ISSUE-005) | Selected valid work and its required upstream nodes execute with exact output; an unrelated invalid branch does not incorrectly block the specified selected execution. Establish the contract and add a focused backend regression plus browser journey. |
| 2 | Main workflow journey | Create/open a workflow, inspect tool information, add tools by double-click/drag, connect compatible pins, edit parameters, run real computation, inspect exact GUI results, save, and reopen the same graph. |
| 3 | Everyday editing and persistence | Select/multiselect, rename, reconnect/disconnect, enable/disable, copy/paste, delete, undo/redo, keyboard actions, save/discard/recovery, and workflow switching preserve the correct graph and active context. |
| 4 | Nested workflows | Group/embed, publish/connect stable ports, edit privately, apply/save, discard, reopen, and execute nested work while preserving parent connections and source ownership. |
| 5 | Execution and results lifecycle | Run/Run Selected, progress, actual failure, cancellation, correction/rerun, cache reuse/clear, result tables/images/files, and output export show correct state and data. |
| 6 | Remaining user features | Complete workflow/file management, settings/layout, datasets, catalog search, package/custom-tool management, source updates, editor/Python authoring, viewers, errors/logging, and agent control. |
| 7 | Systematic gap closure and final certification | Close every remaining in-scope inventory obligation, including negative/boundary and deployment/integration cases, then certify the complete suite and manual boundaries. |

Build small independent journeys around these batches instead of one long test whose early failure hides later features.
Each family needs a representative successful user path before expanding its unusual scenarios, except when a known high-impact failure must be fixed first.
Reuse existing adequate journeys and strengthen missing assertions; do not recreate coverage merely to add test counts.
Limit runner/manifest work to enabling a required check, correcting a proven selection defect, or supplying missing final evidence.
A new combined campaign command is optional; the existing audited selectors can support final certification without another infrastructure project.

## Complete and systematic feature coverage

Priority is separate from coverage status: every in-scope feature remains mandatory.
Maintain stable feature IDs in the existing [GUI](coverage-gui.md), [Workflow](coverage-workflows.md), and [Runtime](coverage-runtime.md) inventories; assign IDs as rows are reconciled and use them in worker packets and handoffs.
Each row records authority, actual implementation, user outcome, priority, applicable scenarios, exact selectors, required levels, deployment/browser variants, owner/status, and evidence revision.
Use explicit states: `unassessed`, `gap`, `in-progress`, `blocked`, `verified`, or `out-of-scope`.
For each applicable scenario, record the assertion or gap; record a reason for any `not-applicable` decision.
Historical inspection or a passing mock is not proof of an untested real integration.

The inventories must cover at least these families, expanding them when specification or UI inspection finds more implemented features:

| Feature family | Mandatory coverage dimensions |
| --- | --- |
| Startup, modes, workspace, and layout | Empty/nonempty startup, workspace switching, restore/reopen, tabs/docks/panels, settings load/save/reset, persisted layout/preferences, desktop versus webapp availability. |
| Workflow lifecycle | Create/open/save/save-as, draft recovery/discard/conflict, rename/move/folders, duplicate/delete, import/export, independent graph/source copies, identity-safe lifecycle changes. |
| Catalog and canvas editing | Search/filter/information, single/double-click/drag behavior, metadata/pins, node/edge types, connect/reconnect/disconnect, parameter control types/defaults/reset, rename, selection, collapse/enable, clipboard, undo/redo, shortcuts/focus, pan/zoom/fit, validation feedback. |
| Recursive workflows and sources | Group/embed, interfaces/bindings/stable IDs, private nested edits, apply/discard/reopen, parent conflicts and destructive confirmation, provenance/detach/update, recursive owned-source transport. |
| Tools, packages, and authoring | Package discovery/version/install/uninstall/error paths, custom creation/rename/delete, valid/invalid hot reload and recovery, catalog versus bound source opening, editor lifecycle, Python preview/apply/cancel, materialized graph reopen. |
| Local execution | Real Direct and sequential worker paths, accepted snapshot/Run Selected, enablement/dependencies, progress/status/log attribution, mutation lock, failure/cancel/retry, cached versus recomputed output, reconnect and recovery. |
| Results and data | Exact table values, columns/row lineage, merged/stacked results, selection/navigation, pagination/width preferences, images/thumbnails/viewers, output templates/files, exports/bundles and readiness/error states. |
| Datasets and integrations | Upload/select/organize/move/delete/download, partial failure and path boundaries, implemented OMERO controls, filesystem dialogs, editor/viewer actions and actual external capabilities. |
| Cross-cutting contracts | REST/schema validation, WebSocket delivery/reconnect, error history and navigation, MCP operations to accepted draft/GUI, ownership and persistence, permissions/path safety, native packaging and crash/restart boundaries. |

For every feature assess: normal success; invalid input/refused action; cancel/failure/recovery; persistence/reload; and applicable identity, concurrency, ownership, and permission boundaries.
Choose meaningful representative cases and lower-level tests for larger state spaces instead of requiring every possible Cartesian combination.
Every user-visible in-scope action needs behavioral UI evidence on its supported surface, plus lower-level assertions for the important contracts it depends on.
Every primary GUI journey must pass in Chromium and Firefox at final acceptance.
Test desktop/webapp differences explicitly rather than assuming one browser project proves both deployment modes.
Assign genuine native/external boundaries reproducible manual or integration acceptance steps; mocks certify only the controlled boundary.

At the end of each feature batch, reconcile its rows against actual assertions.
At the end of each priority wave, scan implemented specification sections and visible menus/panels/routes for features absent from the inventories.
Final closure requires that this reconciliation covers all implemented in-scope features, not merely the initial shortlist.

## Per-feature testing and repair loop

1. Pick the highest-priority runnable feature and inspect its contract, current implementation, and existing assertions.
2. Prepare a realistic small fixture with known tool metadata, required parameters, compatible bindings, expected data, and intended validation state; anticipate ordinary dialogs before a browser run.
3. Exercise actual UI controls through the real frontend/backend and assert visible results plus accepted/persisted state.
4. If it fails, preserve the exact selector/browser/revision, first relevant error, trace, and state before cleanup; distinguish fixture, product, environment, and specification failures.
5. Fix a demonstrated defect with a small regression at the lowest useful layer, then prove the affected UI outcome.
6. Run the required focused and completion checks, update the feature evidence, commit immediately, and integrate.

API setup is acceptable for a prerequisite not being certified in that test; verify the exact opened workflow and accepted graph before interaction.
Do not claim GUI creation/editing coverage when the operation under test was performed through an API, internal store, handler call, or direct file edit.
Do not claim real execution from an intercepted Run request, nor readable image/result correctness from placeholder bytes.
Use exact expected data, independent file/output oracles where appropriate, and state-based readiness; avoid arbitrary sleeps and snapshots that merely echo current implementation.

Use `scripts/test focus` without campaign-wide selection flags for exact failing selectors.
After a fix, run the exact test once; use `--repeat-each=5` only for a suspected timing/race defect.
Run the applicable completion lane from `docs/testing.md` before declaring the batch complete.
Reuse successful unchanged phases after a late failure and state their source revision; rerun only checks invalidated by subsequent edits.
Do not stack quick, scoped, and full checks when the later scheduled command subsumes the earlier work.
Run comprehensive browser acceptance at substantial milestones and final certification, not after every edit.

## Autonomous repair and escalation

Sol workers may repair routine, bounded defects autonomously when the intended behavior is explicit, the cause is reproduced or decisive, and regressions preserve the contract.
Use Astra/high for conflicting specifications, unclear library semantics or fixture validity, identity/data-loss risk, a proposed semantic redesign, or one unsuccessful bounded repair whose cause remains unclear.
A production failure alone does not require specialist escalation if those conditions are absent.

The orchestrator records an issue and freezes dependent changes, then sends one bounded fresh-context investigation to Astra.
Only describe an issue as `astra-review` after a specialist is actually assigned; otherwise it is `open` with a queued next action.
Astra returns `safe-to-fix` with contract/cause/repair/regressions, `not-a-defect` with supporting evidence, or `needs-owner` with one concrete unresolved decision.
For `safe-to-fix`, Sol implements and validates; for `not-a-defect`, correct the test/inventory without inventing new behavior.
If Astra cannot establish a safe contract and returns `needs-owner`, pause the campaign and ask the owner one concrete question with the evidence.
Independent features may continue while a bounded specialist investigation runs unless the concern affects shared foundations.
Record unavailable services/credentials as `externally-blocked` with recovery steps; neither slowness nor infrastructure failure establishes a product defect.
Missing required model capability is a configuration blocker; never silently substitute or claim a review occurred.

## Final certification and completion gate

Use the existing per-case audited selectors in `docs/testing.md` and `tests/campaign-local-scope.json`.
Frontend-unit/browser campaign selectors require complete collections; use ordinary focused commands for individual cases.
Audit exact exclusions and ensure newly added tests are selected; collection-only output proves selection, not successful execution.
Scope exclusions must not drop local assertions from mixed tests; split such tests when necessary.
Preserve out-of-scope tests in the normal regression suite.

Final certification must cover the complete in-scope backend and frontend suites, every in-scope Chromium and Firefox journey, backend logging-order checks, lint/type checks/build/docs, published common-tools compatibility, and real sequential-worker acceptance.
Use `scripts/test` with documented commands; record the actual scoped commands when an unmodified broad lane would include excluded campaign features.
External package and worker checks must actually run for their respective certification claims, using the published locked dependencies and independent runtime state.
Retain completed release evidence; reopen library release work only for a new necessary library fix, following its documented release/CI requirements.
The existing release authorization and library-required CI do not expand platform campaign scope.

The orchestrator must verify all of the following before claiming completion:

- Every implemented in-scope feature has inventory rows and all applicable scenarios are verified, with justified test levels and exact evidence.
- Every primary GUI journey passes on both browsers, with correct data and persistence; no primary action is represented only by rendering or mocks.
- Demonstrated bugs are resolved and committed with regressions; no unresolved in-scope defect or silently skipped/flaky test is counted as passing.
- Collected/selected/excluded/skipped/failed counts reconcile for every suite; each exclusion has its explicit scope reason.
- Manual/native/external obligations have recorded outcomes using [Manual Platform Testing](manual-testing.md); any unavailable obligation remains blocked.
- Every completion record identifies command, revision or diff, duration, results, retries/exclusions, packages, and limitations; the relevant integrated revision is validated.
- Task worktrees are integrated/cleaned up, shared records agree, and the checkout is clean apart from explicitly identified unrelated user work.

If a required manual or external check remains unavailable, report automated coverage achieved and the outstanding obligation; the campaign is incomplete unless the owner explicitly accepts the limitation.
Owner-accepted limitations remain visible as limitations, never reclassified as passed tests.
Test counts, line coverage, or completion of only the high-priority wave do not establish comprehensive coverage.

## Durable state and restart

[Campaign progress](platform-test-progress.md) owns the short current objective, prioritized feature summary, active ownership/worktrees, open decisions, and next three actions.
[Campaign issues](platform-test-issues.md) owns defect decisions, the coverage inventories own detailed feature obligations, and [Campaign evidence](platform-test-evidence.md) retains completed validation and release history.
Keep each fact in its owning record and link to it; remove obsolete next actions when a task is integrated.
Record historical product contracts as historical, including superseded catalog single-click creation.
Update durable records at every completed task, escalation, and interruption; do not create administrative commits solely for unchanged status.
Status questions steer the ongoing campaign: answer briefly, then continue unless the user asks to pause or change the objective.
Before restart, preserve unfinished work/evidence and reconcile actual Git/worker/process state; never rely on a prior conversation or temporary logs to identify the next task.
