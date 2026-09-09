---
orphan: true
---

# Platform testing implementation plan

Certify every implemented platform feature within the scope below, improve the existing tests, and maintain a dedicated browser acceptance suite.
This is an implementation plan, not evidence that certification has passed.
The authoritative commands and completion requirements are in [Test lanes](../testing.md).

## Scope and execution rules

Cover desktop and webapp behavior implemented in the current v1/v2 specifications, including recursive workflows and their library contracts.
Exclude parallel scheduling, HPC, Parsl, managed remote execution, and distributed engines from this campaign.
Preserve Direct execution for focused tests and ordinary DataFrame-only workflows.
Exercise real local Wetlands workers sequentially with an explicit single-worker limit, and verify process identity, exact results, generated files, and cleanup.
Tests must distinguish serialized configuration, mocked orchestration, Direct execution, and actual worker execution in their assertions and coverage claims.

Use the Sol → Astra → owner escalation protocol below when unexpected behavior has an unclear cause or repair.
This replaces the earlier rule that sent every ambiguous finding directly to the owner.
Do not alter expected results, weaken assertions, suppress warnings, invent workflow conversions, or change library semantics to obtain a pass.
Do not implement a speculative repair while the issue is under review.
For example, Generate supplies its complete DataFrame to a downstream positional DataFrame input; an output-column pin is not interchangeable with that input.
Implement contract-established or owner-approved fixes cleanly and update affected code, tests, fixtures, workflows, tools, specifications, and documentation together without backward-compatibility shims.

## Coordination and commits

The master agent owns scope, dependency order, the feature inventory, validation evidence, integration, and communication with the owner.
The master and ordinary implementation/review workers use `gpt-5.6-sol` with `medium` reasoning.
A specialist uses `gpt-6-astra` with `high` reasoning only for escalations.
Assign independent agents bounded ownership of backend feature families, frontend feature families, browser journeys, and any necessary library work.
Keep write ownership disjoint, pass exact file paths and contract expectations, and request concise findings rather than duplicating every investigation in the master's context.
Whenever multiple agents may write in parallel, create a dedicated worktree under `.worktrees/<task_name>` for each writable task and keep its dependencies, runtime state, and commit isolated as required by `AGENTS.md`.
Agents may share the primary checkout only for read-only investigations; a task that becomes writable must move to its own worktree before editing.
An agent reports an ambiguous defect immediately so the master can freeze affected work and send a focused escalation.
Use at most two ordinary workers alongside the master by default, leaving a fourth slot available for Astra; use fewer when tasks overlap.

Commit each coherent, independently validated change as soon as it is ready.
Treat resolution of an issue or bounded task as an immediate commit boundary: update its durable records, validate it, commit it, and restore a clean task checkout before starting the next writable task.
Separate dependency updates, library releases, platform behavior fixes, fixture corrections, browser fixes, and testing infrastructure when their dependencies allow it.
Review the staged diff and leave unrelated changes and temporary notes unstaged.
Do not delay a finished independent commit merely because another issue remains open, or commit an unfinished runner profile as working infrastructure.

## Autonomous execution and escalation

Sol may fix a routine defect without asking when the intended behavior is explicit in the specifications or an existing owner decision, the cause is understood, the change is bounded, and meaningful regression assertions can be written without changing that intent.
A failing test alone does not justify changing production behavior or its expected result.
Reproduce the exact failure and inspect the relevant contract before editing; do not repeatedly guess at fixes.
Escalate immediately for conflicting specifications, unintuitive library contracts, unclear fixture validity, identity/data-loss risks, or a repair that would require inventing semantics.
Also escalate after one unsuccessful bounded repair attempt if the remaining cause is unclear; this is a cost-control default, not permission for the first attempt to be speculative.

The master records an issue ID in [Campaign issues](platform-test-issues.md), freezes dependent edits and tests, and spawns one Astra specialist with a fresh context and a compact issue packet.
Unrelated work may continue only when the master can establish independence; freeze the whole campaign if the suspect fixture, contract, or state is shared widely.
Astra may inspect source/specifications and run a bounded reproduction in a disposable workspace without asking the owner first.
Astra returns one of these explicit dispositions:

- `safe-to-fix`: established intended behavior, reproduced cause or decisive code evidence, bounded implementation instructions, affected specifications, and required regressions; Sol implements and validates autonomously.
- `not-a-defect`: evidence that the behavior is correct and the test/audit assumption was wrong; Sol corrects the test or inventory only when the proper contract is established.
- `needs-owner`: unresolved design intent, contradictory specifications, questionable test oracle, unsafe workaround, or remaining uncertainty about a safe contract-preserving repair after bounded investigation; the master pauses the entire campaign and asks the owner one concrete question with the evidence, options, and recommendation.

A merely slow implementation or unavailable external dependency is not evidence of flawed intent.
Record unavailable services or credentials as `externally-blocked` with the exact recovery action; do not ask the owner to invent semantics to bypass an environmental block.
Astra is not permission to redesign the platform or silently choose among conflicting product contracts.
If Astra remains uncertain, it must return `needs-owner`; do not launch repeated higher-cost reviews to avoid asking.
A missing required model or escalation capability is a configuration blocker: report it rather than silently substituting another model or claiming review happened.
Owner decisions are recorded verbatim or faithfully summarized with scope in the issue record before resuming.
The currently unconfirmed source-update identity issue is queued for Astra under this protocol; no repair has been approved or executed by this documentation change.

### Focused delegation

Use explicit `model` and `reasoning_effort` arguments when the runtime exposes them.
For the current collaboration interface, use `fork_turns="none"` with these overrides and supply a self-contained task; a full-history fork inherits the parent's model and cannot change it.
Ordinary worker settings are `model="gpt-5.6-sol", reasoning_effort="medium"`; escalation settings are `model="gpt-6-astra", reasoning_effort="high"`.
Do not make the worker reread the entire conversation or all inventories.

Every worker packet contains the task/issue ID, objective, relevant file/specification paths, acceptance criteria, owned write paths, dependency constraints, exact focused checks, and escalation rules.
An Astra packet additionally contains observed versus expected behavior, exact selector/browser/revision/package versions, minimal reproduction or explicitly unconfirmed hypothesis, evidence paths, attempted changes, and the unresolved decision.
Ask for concise findings and a disposition, not a transcript.
The master owns shared progress/issue records, staging, commits, and completion checks; workers return file lists, evidence, and status without staging another worker's work.
Release idle workers or reuse them only for closely related bounded work; do not create agents for trivial edits or redundant audits.

### Durable state and restart

[Campaign progress](platform-test-progress.md) is the authoritative live checkpoint, [Campaign issues](platform-test-issues.md) owns escalation decisions, and the three linked coverage inventories own feature-to-test evidence.
These are requested project deliverables and should be committed; raw traces, large logs, scratch plans, and transient agent notes are not.
Update progress after each coherent task, escalation, commit, and before ending or replacing a session.
Record task status, owner and write paths, source revision, exact validation commands/results/durations/exclusions, commit IDs, and the next concrete action.
A completed code task needs its required validation and commit; a read-only audit must remain labeled inspected, not passed.
For a checkpoint's own commit, use `git log -1 -- <checkpoint-path>` rather than recursively editing its own hash into the file.

Keep the checkpoint short: active work, unresolved issues, completed milestone references, and the next queue.
Keep closed issues as concise decisions with commit references; do not carry obsolete investigation transcripts into each restart.
Before a restart, stop or hand off all workers, record dirty-file ownership and running processes, and preserve necessary evidence in stable ignored artifact paths with reconstruction steps.
Temporary `/private/tmp` logs are historical conveniences, not restart dependencies.
A new master reads [Restart instructions](platform-test-start.md), reconciles Git and the checkpoint, and resumes the first runnable task without replaying finished releases or baseline tests.
A prompt cannot change the current master model; select Sol/medium when starting the new session and verify the runtime settings rather than claiming the prose configured them.

## 1. Complete the library and dependency gate

The dedicated library agent reviews and validates the three approved contracts: reject column bindings to DataFrameTool constant parameters, resolve postponed annotations with metadata and inheritance intact, and retain Direct while testing real sequential workers separately.
It commits the completed library fixes with their specifications and regression tests, prepares the appropriate package version bumps and release notes, and follows the library's documented release process.
Publishing the necessary library release is authorized for this task; use the configured GitHub and package-publishing workflow, and report missing credentials or failed release checks rather than claiming publication.
Library publication must satisfy that repository's required CI, including existing worker-backend checks; owner-approved repairs to those release checks do not expand the platform campaign's execution scope.
Record the library commit, release tag, package versions, workflow result, and package-index availability.

Commit the finished Wetlands 2.4.1 dependency update independently once its targeted cleanup regression is verified.
After the patched BioImageFlow packages are published, update the platform constraints and lockfile, synchronize from the package index, and verify imported package versions and locations.
Rerun the contract and worker regressions against the published packages without an editable-install override before committing the platform dependency integration.
Keep local-source validation explicitly labeled until that gate passes.

## 2. Resolve the GUI test startup race

Preserve the failing Generate browser test, browser project, trace or screenshot, backend logs, accepted workflow identity, and draft revision.
Give the owner manual steps and identify which setup is test-only, especially seeded workflows and API changes made before navigation.
Trace inspection identified that the test begins its mouse drag before the canvas mounts.
The later “No workflow is open” screenshot is misleading because cleanup has already deleted the workflow; it is not evidence of an application restoration failure.
Fix test readiness by waiting for both the specific workflow title and its mounted canvas before dragging, and preserve failure evidence before cleanup.
Keep the application unchanged unless subsequent evidence demonstrates a separate product defect.
The owner has authorized investigation; route further ambiguous product decisions through Astra before implementing them.

After an approved repair, run the exact failing Chromium test once.
Use five repetitions only if the diagnosis identifies a timing or race defect, then verify the same journey in Firefox and the smallest relevant browser completion scope.
Keep the real Generate metadata, complete DataFrame edge, accepted-draft validation, and exact output-row assertions in the test.

## 3. Build a feature-to-test inventory

Read the implemented specifications and inspect routes, services, stores, panels, commands, fixtures, and existing tests.
Create an inventory with one row per user-visible behavior or developer contract: specification reference, implementation owner, positive and negative cases, existing selectors, gaps, required test level, exclusions, and completion evidence.
Audit test bodies and fixtures rather than relying on filenames, test counts, or coverage percentages.

Cover these feature families:

- Startup, deployment modes, settings, workspace selection, application layout, and durable restoration.
- Workflow creation, save, draft recovery, rename, move, duplicate, delete, import/export, and identity conflicts.
- Canvas editing, pins and edge types, parameters, metadata, selection, clipboard, undo/redo, keyboard actions, and validation feedback.
- Nested workflows, published interfaces, draft isolation, application to parents, provenance, and recursive local-source ownership.
- Tool catalog, packages, editable sources, hot reload, Python authoring, and code-editor integration.
- Local execution, Run Selected, progress, failure reporting, cancellation, caching, results, tables, output templates, and result bundles.
- Datasets, filesystem boundaries, thumbnails and images, viewer integrations, WebSockets, logging, error history, and MCP operations.
- Desktop packaging and external integrations that require separate manual or release acceptance.

Classify each boundary as repository-owned deterministic testing, a real isolated local integration, explicit external certification, or human acceptance.
Record unavailable external services or unsupported environments as blocked, never as covered by mocks.

## 4. Refactor and fill gaps systematically

For each feature family, remove stale tests only when the behavior is obsolete or its intended replacement coverage is identified.
Replace permissive snapshots, silent skips, fabricated metadata, obsolete APIs, and unrealistic workflows with reviewed fixtures using current public contracts.
Share a fixture only when tests depend on the same semantics; keep expected values readable and independent of the implementation.
Add missing success, invalid-input, persistence, failure, and boundary cases at the lowest useful level, then add cross-layer journeys for behavior that isolated tests cannot prove.
Prioritize silent data corruption, incorrect bindings, workflow loss, ownership violations, and misleading execution status before cosmetic gaps.
Commit each completed family after its focused regressions and applicable scoped completion check pass.

## 5. Maintain the dedicated GUI acceptance suite

Use the existing Playwright suite with real frontend and backend processes in disposable workspaces.
Exercise complete user journeys across the inventory, including reopening state, nested workflows, actual graph connections, execution and exact data inspection, failures, settings, and tool editing.
Prefer visible UI actions; when backend setup is necessary, explicitly verify that the UI has opened the intended accepted workflow before interacting.
Use stable semantic selectors and state-based readiness assertions, and capture useful failure evidence.

Keep comprehensive Chromium and Firefox acceptance opt-in after large changes, before releases, and at the end of this campaign.
It must not run on every development edit; focused browser tests and a small critical smoke remain available for relevant changes.
First audit and implement explicit per-test scope selection so the campaign excludes managed-remote and parallel features without dropping unrelated coverage.
Validate selection by inspecting collected tests, including mixed files and parameterized cases, and fail if expected exclusions do not match.
Local-platform profile selection and per-case evidence tooling remain pending and must not be exposed as working commands until their selection behavior is validated.
Do not use broad name filters or project-level exclusion assumptions as evidence of complete local-platform coverage.

## 6. Certification and handoff

Use `scripts/test focus` during localized work, then the smallest applicable completion check documented in the test lanes.
For cross-stack dependencies and runtime changes, cover the `check app` phases with explicitly audited exclusions; record a scoped campaign result rather than claiming an unmodified lane passed when phases were selected separately.
After the large campaign, run comprehensive backend, frontend, and Chromium/Firefox acceptance within the approved scope, plus published-package and sequential-worker certification.
Do not broaden a browser run while its exact failing test is unresolved or rerun unchanged successful phases after an unrelated late failure.
Record every completion command, result, duration, source revision, installed library versions, and skipped, deselected, flaky, or externally blocked cases.

Use [Manual Platform Testing](manual-testing.md) for packaged desktop windows, operating-system dialogs, physical drag-and-drop, real editors/viewers, and other integrations that headless automation cannot certify.
Reconcile the completed inventory against all implemented in-scope features, update affected specifications and developer guidance, and remove superseded fixtures or instructions.
Conclude only with the actual coverage achieved, remaining blockers accepted by the owner, commit and release identities, and commands for routine checks and occasional complete GUI acceptance.
