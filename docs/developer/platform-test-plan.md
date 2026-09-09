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

If unexpected behavior has an unclear cause or repair, pause the entire campaign and report it to the owner with reproduction steps and preserved evidence.
Do not alter expected results, weaken assertions, suppress warnings, invent workflow conversions, or change library semantics to obtain a pass.
Resume the affected investigation or implementation only with the owner's direction.
For example, Generate supplies its complete DataFrame to a downstream positional DataFrame input; an output-column pin is not interchangeable with that input.
Implement approved fixes cleanly and update affected code, tests, fixtures, workflows, tools, specifications, and documentation together without backward-compatibility shims.

## Coordination and commits

The master agent owns scope, dependency order, the feature inventory, validation evidence, integration, and communication with the owner.
Assign independent agents bounded ownership of library release work, backend feature families, frontend feature families, and browser journeys as needed.
Keep write ownership disjoint, pass exact file paths and contract expectations, and request concise findings rather than duplicating every investigation in the master's context.
An agent reports an ambiguous defect immediately so the master can stop all dependent work.

Commit each coherent, independently validated change as soon as it is ready.
Separate dependency updates, library releases, platform behavior fixes, fixture corrections, browser fixes, and testing infrastructure when their dependencies allow it.
Review the staged diff and leave unrelated changes and temporary notes unstaged.
Do not delay a finished independent commit merely because another issue remains open, or commit an unfinished runner profile as working infrastructure.

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
The owner has authorized investigation; report any further ambiguous product decision before implementing it.

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
