# Test quality audit

Date: 2026-07-20

Scope: `platform_specs_v2.md`, the backend Pytest suite, the frontend Vitest suite, the Playwright suite, test configuration, and CI test lanes.

## Executive summary

The project has a large and generally serious automated test suite, with especially strong coverage of workflow identity and recovery, draft and nested-snapshot concurrency, consolidated data-table projection, editor resolution, and frontend race handling.
The main problem is not a lack of tests in aggregate; it is that test effort is unevenly allocated.
Some safety-critical internals have deep coverage, while several central v2 user journeys have no real integration test, frontend coverage is not measured at all, the browser suite contains API-only and framework-wiring checks, and a few tests lock in behavior that contradicts the normative specification.

The highest-value improvement is to replace shallow and duplicated checks with a small number of real vertical feature tests: recursive sub-workflow execution and caching, archive export/import round trips, nested editor save/discard, cross-workflow paste, custom-tool lifecycle, and consolidated data-table behavior.
Coverage should become an enforced signal, but percentage targets should be introduced only after gaps are classified; raw line coverage must not become a reason to preserve trivial serialization and framework tests.

## Pre-cleanup measured baseline

The measurements below were taken from the working checkout on 2026-07-20.

| Lane | Inventory and result | Measured time | Coverage status |
|---|---:|---:|---|
| Backend Pytest, excluding external `common_tools` certification | 1,499 collected, 1,489 passed, 10 deselected | 95.46 seconds with coverage instrumentation | 88.72% line coverage, displayed as 89%; 10,868 statements and 1,226 missed |
| Frontend Vitest | 103 files, 1,479 tests passed | About 21 seconds for a normal non-verbose run | Not configured or enforced |
| Chromium Playwright | 19 spec files, 52 tests passed, no skips | 1.2 minutes reported by Playwright, 75.34 seconds wall time | No application-code coverage collection |
| Firefox Playwright | Same full suite, scheduled or manual | Not rerun for this audit | No application-code coverage collection |
| External common-tools certification | Separate opt-in lane | Not run | Intentionally outside deterministic coverage |

The backend source contains about 23,853 Python lines and its tests contain about 36,426 lines.
The frontend source contains about 34,851 TypeScript/Vue lines, its Vitest tests contain about 39,707 lines, and its Playwright tests contain about 2,799 lines.
Test volume therefore already exceeds production-code volume, which reinforces that future work should optimize signal rather than simply add more cases.

The backend run emitted 241 warnings, dominated by unclosed SQLite connection `ResourceWarning`s in dataset-related tests.
The cleanup iteration fixed the connection lifecycle and configured Pytest to fail on future `ResourceWarning`s.

## Small cleanup implemented

The small cleanup iteration removed or consolidated the following tests because they did not exercise a distinct project contract:

- `frontend/tests/unit/smoke.test.ts` asserted only that `1 + 1` equals `2`.
- `frontend/tests/unit/stores/integration.test.ts` checked that Pinia stores can coexist and repeated state assertions already owned by the individual store suites.
- `frontend/tests/unit/stores/settings-types.test.ts` made runtime identity assertions on typed literals; `bun run type-check` is the test of those compile-time contracts.
- `frontend/tests/e2e/smoke.spec.ts` was a strict subset of the retained backend-connected `full-stack-smoke.spec.ts` and `app-shell.spec.ts`.
- `frontend/tests/e2e/stores-integration.spec.ts` inspected Vue/Pinia internals rather than a user-visible feature; every maintained browser flow already proves that the app and stores initialize.
- `frontend/tests/e2e/graph-validation.spec.ts` drove `fetch` directly and duplicated `backend/tests/test_routers/test_graph.py`, including empty-graph validation and removal of the parameter PATCH endpoint; it never exercised GUI validation behavior.
- The API-only “Tools Panel fetches tools from backend successfully” case in `frontend/tests/e2e/workflow-creation.spec.ts` asserted the response shape of `/tools`, not panel behavior.
- The standalone “newly created canonical workflow canvas is visible” case in `frontend/tests/e2e/execution.spec.ts` duplicated setup and weaker assertions already present in real execution and workflow CRUD flows.
- The font-family and PrimeIcons implementation checks in `frontend/tests/e2e/workflow-creation.spec.ts` did not protect a platform feature or stable visual contract.
- `frontend/tests/manual/chrome_devtools_harness.py` was outside every documented and CI lane, depended on an external CLI and fragile Vue internals, and duplicated maintained Playwright coverage.
- The 5,000-row `LoggerPanel` render test cost about 1.93 seconds while the logger store already owns the capped-buffer contract; a future virtualization test should use a bounded performance assertion rather than requiring 5,000 DOM rows.
- `backend/tests/test_models/test_imports.py` was redundant with collection, type checking, and consuming tests that import the public models.
- The private default-installer construction assertion in `backend/tests/test_app_config_wiring.py` was redundant with the retained observable install-endpoint test.
- The two `AppConfig.static_dir` getter/default assertions in `backend/tests/test_static_serving.py` duplicated the retained tests of actual fallback and asset serving.
- Importability, callability, signature, and positive-constant assertions were removed from `backend/tests/test_desktop.py`; the retained tests exercise observable desktop behavior and the exact execution-stop timeout contract.
- Two tools-router environment start/stop cases were removed because they duplicated the retained fake-service delegation tests and could race a real Pixi installation.
- The exact four-item assertion in `NodeContextMenu.test.ts` was removed while each menu action remains covered independently.
- Six serial canvas browser cases were consolidated into one feature flow that proves tool discovery, draft persistence, selection, pins, and the Node Panel without repeating workflow setup.

Immediately after that cleanup, Pytest collected 1,484 tests with 1,474 selected in the required lane, Vitest ran 1,465 tests in 100 files, and Playwright ran 37 tests in 16 spec files.
That historical validation completed with 1,474 backend tests passing in 43.16 seconds, 1,465 frontend unit tests passing in 22.15 seconds, and all 37 Chromium tests passing in 52.9 seconds; later feature commits have increased the live inventory.
The retained `full-stack-smoke.spec.ts` is the one browser smoke because it proves app rendering, the Vite proxy, backend health, and absence of console errors in one flow.

No tests were added, and sub-workflow tests were deliberately left unchanged because that feature area is expected to change soon.
Further deletion candidates need coverage-assisted mutation or fault-seeding evidence before removal.

## What is already strong

### Workflow durability and concurrency

The strongest area is the identity-generation, move-journal, draft, nested-snapshot, and mutation-serialization logic.
`backend/tests/test_services/test_workflow_move_recovery.py`, `test_workflow_folder_move_recovery.py`, `test_workflow_move_recovery_service.py`, `test_workflow_generation_ledger.py`, and `test_workflow_mutation_serialization.py` cover failure boundaries and restart behavior that would be difficult to validate manually.
Frontend race behavior is also unusually well covered in `frontend/tests/e2e/critical-operation-races.spec.ts`, session coordinator tests, `CanvasView.test.ts`, `AppShell.test.ts`, and `MenuBar.test.ts`.
These tests are valuable even when detailed because they protect data-loss and stale-response hazards.

### Consolidated data tables

`backend/tests/test_services/test_data_table_projection.py` and `backend/tests/test_routers/test_data_table.py` cover lineage alignment, anchor preservation, context omission, duplicate/divergent fallback, empty-result rules, column qualification, stable sorting, pagination, and CSV contracts.
Frontend traversal and request-order behavior are covered in `frontend/src/utils/__tests__/dataTableSources.test.ts`, `frontend/src/stores/__tests__/dataTable.test.ts`, and `frontend/src/components/panels/__tests__/DataTablePanel.test.ts`.
This is good layered coverage: pure algorithm tests, HTTP contract tests, and presentation/store tests have distinct responsibilities.

### Editor, datasets, and execution races

Editor resolution has substantial backend service/router and frontend API/component coverage, including external, embedded, and clipboard fallback paths.
Dataset catalog fundamentals have strong service/router coverage and one relevant real-backend browser flow.
Execution identity, stale-event rejection, save/run races, and workflow-specific log scoping have broad unit and browser regression coverage.

### Browser-test architecture

GUI/e2e tests do exist and many are relevant.
Playwright starts the real Vue application and a real FastAPI application configured through `backend/tests/e2e_app.py`, with isolated storage and deterministic tool fixtures.
The most valuable current specs are `critical-operation-races.spec.ts`, `workflow-crud.spec.ts`, `workflow-publishing.spec.ts`, `execution.spec.ts`, `graph-persistence.spec.ts`, `agent-draft-sync.spec.ts`, `datasets-panel.spec.ts`, `hot-reload.spec.ts`, `error-handling.spec.ts`, and `avivator.spec.ts`.
There is no real pywebview/native desktop GUI lane; `backend/tests/test_desktop.py` is a headless mock suite and cannot catch JavaScript bridge, native dialog, window, or packaged-process integration defects.

## Coverage assessment

### Backend

The measured 89% line coverage is a good baseline, but CI neither records nor enforces it and branch coverage is not enabled.
Line coverage alone overstates confidence in code with complex recovery branches, exception boundaries, and concurrency interleavings.

The lowest-covered production boundaries were `routers/workspace.py` at 64.29%, `routers/graph.py` at 69.09%, `routers/datasets.py` at 71.54%, `routers/data_table.py` at 72.97%, `services/thumbnail_manager.py` at 75.32%, and `routers/nested_workflow_snapshots.py` at 77.11%.
`routers/workspace.py` has no router test file.
The output-schema cases in `test_routers/test_graph.py` all depend on the external `common_tools` marker and are deselected from the required lane, leaving a live editor endpoint without deterministic required coverage.

Add `pytest-cov` to the development dependencies and run coverage in the required backend lane using source and branch coverage.
Start with a repository threshold just below the measured baseline, for example 87–88%, then ratchet it upward only when meaningful gaps are closed.
Apply stricter expectations to pure decision-heavy modules and avoid forcing defensive platform-specific branches to be covered with artificial tests.
Publish an HTML or XML report as a CI artifact so missed lines can be reviewed rather than reduced to one percentage.

The important backend gaps are behavioral, even where neighboring lines are covered:

- No real sub-workflow execution proves recursive flattening, scoped internal node names, per-internal-node cache reuse, progress, or log attribution.
- Archive tests use fake adapters or monkeypatched library APIs; there is no real export→import round trip with nested graphs and workflow-local custom tools.
- Graph output-schema resolution needs repository-owned dynamic-output fixtures so unknown-node, retry, invalid-graph, and serialization branches run without the package-index certification lane.
- Webapp security explicitly tests creation rejection but does not symmetrically prove that custom-tool rename and delete are rejected.
- `GET /tools` lacks a precise integration assertion for non-null `path_picker` pass-through.
- Platform integration does not prove the common `Files` tool’s mutual exclusion, ordering, pattern, and recursion behavior.

### Frontend

Frontend source coverage is unknown.
There is no coverage provider dependency, test script, Vitest coverage configuration, CI artifact, or threshold.

Add `@vitest/coverage-v8`, collect statements/branches/functions/lines for production `src` files, exclude generated API types and test utilities, and establish the first threshold only after inspecting the report.
A reasonable initial policy is to prevent total coverage from decreasing and to require stronger coverage for pure utilities, stores, and session coordinators than for thin Vue wrappers.
Use branch coverage for clipboard schema reconciliation, workflow deletion fencing, execution event acceptance, nested persistence, and data-table state transitions.

Likely frontend gaps visible without instrumentation include `CanvasTab.vue`, `CanvasPlaceholder.vue`, `MergedDataTable.vue`, `NodeDataTable.vue`, `PathCell.vue`, `DeleteWorkflowDialog.vue`, `MissingPackageDialog.vue`, `workflowDeletion.ts`, `graphDocument.ts`, `canvasLifecycle.ts`, `executionSelection.ts`, and several panel sections that have no direct test file.
Some are exercised indirectly, so they should be classified from an actual coverage report before adding tests.
Particularly important static gaps are `MissingPackageDialog.vue`, canonical equality in `graphDocument.ts`, encoded canvas IDs in `canvasPanels.ts`, and selected-run closure/error filtering in `executionSelection.ts`.

### Coverage quality controls

Do not use test count or line coverage as the deletion criterion.
For candidate redundant suites, temporarily remove or mutate the underlying behavior and check whether a higher-level test fails.
Targeted mutation testing is especially useful for `clipboard.ts`, `dataTableSources.ts`, graph validation/translation, workflow generation fencing, and execution event acceptance.
This will identify assertions that execute code without detecting wrong behavior.

## Specification v2 traceability and gaps

| Specification area | Current evidence | Most important missing proof | Priority |
|---|---|---|---:|
| §1.1 Sub-workflow creation | `subWorkflow.test.ts`, `CanvasView.test.ts`, `WorkflowsPanel.test.ts`, backend workflow move/recovery suites | Duplicate entering edges from the same source must create independent published pins; default interface derivation; create/undo/redo as one real transition | High |
| §1.2 Rendering | `ToolNode.test.ts` checks the class and pins | Browser or CSS assertion for the required thick-border distinction | Low |
| §1.3 Editing | Strong nested-session, persistence, parent-baseline, reconciliation, and close-guard coverage | Node double-click routing, focus return to parent, exact discard prompt, and a real nested edit→save/discard browser journey | High |
| §1.4, §1.7, §1.9 Execution, nesting, integration | Translator/validator and lock tests | Real recursive execution, scoped progress/log names, and per-internal-node cache behavior | Critical |
| §1.5–§1.6 Publishing | Strong `NodePanel`, `CanvasView`, `ToolNode`, graph-model, and translator coverage | Browser proof of publication-only dirty/save and parent-edge migration | Medium |
| §2 Code editor | Strong service/router/API/component tests | Browser flow with a controlled fake code-server; Data Table path-cell→`/editor/open` flow | Medium |
| §3 Cross-workflow copy/paste | Strong pure logic in `clipboard.test.ts` and basic canvas paste | Two-workflow browser flow, required warning toasts, and single-step undo | High |
| §4 Export/import | Router/store/menu wiring and fake adapter-boundary tests | Real library archive round trip with custom tools, nested DAG, path sanitization, collisions, and dependency reporting | Critical |
| §5.1–§5.5 Tool lifecycle | Strong backend custom-tool tests and frontend component tests | Real browser create→register→open→edit/hot-reload→rename/delete flow; PATCH/DELETE webapp rejection | High |
| §5.6 Path picker | Strong Node Panel and composable behavior | Backend pass-through contract and real common-tools `Files` semantics | Medium |
| §5.7 Datasets | Strong catalog service/router coverage and a useful upload browser flow | Retry/error persistence, hierarchy move rules, delete revision conflicts/failures, browser picker mode, and overlap deduplication | High |
| §6 Consolidated Data Table | Very strong pure/service/router/store/component coverage | One real browser projection with upstream depth, merged/stacked transition, CSV, and stale-response protection | High |
| §6.5 Image-valued paths | Strong suffix and cell-rendering unit coverage; separate Avivator flow | An end-user table-cell action flow is optional, not urgent | Low |

## Stale, contradictory, and redundant tests still requiring decisions

### Normative contradiction: custom-tool actions

Section 5.2 says rename and delete are right-click context-menu actions on custom tool rows.
`frontend/src/components/panels/__tests__/ToolsPanel.test.ts` instead asserts permanent main-list rename and delete buttons, and the component has no corresponding context-menu behavior.
This is not safe to “fix” by deleting a test alone: product behavior and the normative spec disagree.
Choose the intended interaction, update the implementation or specification, and keep tests only for the chosen contract.

### Likely low-value backend groups

Several model suites spend many separate tests on Pydantic construction, defaults, serialization, JSON serialization, round trips, enum values, importability, signatures, callability, and constants.
Examples include `backend/tests/test_models/test_errors.py`, portions of `test_models/test_execution.py`, `test_models/test_napari.py`, `test_models/test_ws.py`, and portions of the 1,151-line `test_desktop.py`.
Keep boundary validation, extra-field rejection, migrations, security checks, and wire-format contracts.
Consolidate basic framework behavior into parameterized contract cases and remove assertions such as “function exists”, “is callable”, or positive timeout constants unless they protect an actual regression.

Router and service duplication is justified when the router test checks HTTP translation and the service test checks domain behavior.
Remove router cases that reproduce every service permutation through mocked dependencies; retain status codes, request/response schemas, dependency wiring, and one representative success/failure per mapping.

Many backend tests use unconstrained `MagicMock` objects or assert private members in execution, data-table, desktop, and tool-registry code.
Prefer small Protocol/spec-set fakes and public observations such as API responses, files, status, or events; keep private-state assertions only when no observable seam exists.

### Likely low-value frontend groups

There are overlapping old/new locations for execution, tool registry, WebSocket, and MenuBar tests under both `frontend/tests/unit` and co-located `src/**/__tests__` directories.
The files are not exact duplicates, but ownership is fragmented and some behavior is asserted at multiple layers.
Merge by responsibility: protocol dispatch in one WebSocket suite, state transitions in one store suite, and visible behavior in component/browser suites.

The brittle exact menu-item count in `NodeContextMenu.test.ts` was removed during the small cleanup; the individual action assertions remain.

The Create Tool browser case currently proves only that a dialog opens and closes; it should be replaced by a real creation flow rather than expanded with more dialog-shape assertions.

`frontend/src/api/__tests__/editor.test.ts` is 871 lines and repeats many state permutations.
Keep URL/path encoding, resolution-order, persistence barriers, and failure behavior, but consolidate request-shape variants with table-driven tests.

## Speed and reliability improvements

### Backend

The autouse `isolated_bioimageflow_runtime` fixture still requests `tmp_path` and creates a home, tool store, and Wetlands directory for every deterministic test, including pure model tests.
A trial session-shared runtime was rejected because it allowed process state and network transports to leak across tests; future optimization must retain per-test mutation isolation while making provisioning lazy or opt-in.

The ordinary `client` fixture creates the full application for every router test.
Use module-scoped application/client fixtures for read-only contract groups and retain per-test application instances only where state or dependency overrides can leak.

The slowest measured tests were pending-move app lifecycle recovery at 5.72 seconds, snapshot cleanup failure at 5.41 seconds, catalog startup wiring at 2.36 seconds, and environment stop at 1.27 seconds; all remaining measured tests were below 0.7 seconds.
The two lifecycle tests took 6.62 and 4.22 seconds even without instrumentation because unrelated app startup clones the platform into each temporary agent workspace.
Stub the independently tested `ensure_agent_workspace_context` setup in move-recovery and snapshot-cleanup tests, retain one explicit clone integration case, and replace genuine timeout expiry with injected clocks/events or configurable short test timeouts.

Numerous backend tests poll with `asyncio.sleep(0.01)` or use fixed `time.sleep` calls, especially WebSocket logging, hot reload, editor, package installer, and execution tests.
Prefer explicit events, awaited task completion, or condition polling with an immediate first check.

Before cleanup, ordinary uninstrumented runs under the local macOS/Python 3.13 environment repeatedly exited with status 133 when consecutive application-lifespan tests ran, although those tests passed individually and the slower coverage-instrumented full run passed.
The cleanup disables unrelated hot reload in affected lifespan tests and stubs the separately tested agent-workspace setup in the global isolated-runtime fixture; the complete uninstrumented backend lane now passes without an interpreter abort.

Consider `pytest-xdist` only after marking process-global logging, module-import, file-watcher, and environment tests as serial.
Parallelizing everything blindly would make this suite less reliable; the safe service/model subset is the first candidate.

Dataset SQLite connections now commit or roll back explicitly and always close, and Pytest treats `ResourceWarning` as an error.
Pytest now rejects unregistered markers, distinguishes integration, serial, slow, and external requirements, and the root runner reports the slowest tests.

### Frontend unit tests

Vitest is now divided into Node, JSDOM, and JSDOM-with-IndexedDB projects.
The fast Node project covers verified pure utility, session, service, store, and API suites, while fake IndexedDB is installed only for the two files that require the shared implementation.

Very large files increase transform, collection, review, and failure-localization costs: `CanvasView.test.ts` is about 6,576 lines, `AppShell.test.ts` 2,251, `MenuBar.test.ts` 2,138, and `workflow.test.ts` 1,705.
Split them by contract area without duplicating the expensive mount/setup path, using shared fixture builders from `src/test-utils`.

The first post-split run completed the current 100-file suite in 18.52 seconds, down from the earlier 22.15-second post-cleanup run, while the Node-only project completed in 4.32 seconds during isolated validation.
V8 coverage is now available only in the comprehensive lane; its first baseline measured 95.18% statements, 84.16% branches, and 84.89% functions without slowing the coding loop.

### Browser tests

Keep Chromium as the required feature browser.
Run only a tagged compatibility subset in scheduled Firefox: app startup, one canvas interaction, one upload, one WebSocket event, and one execution.
Run the full Firefox suite only when browser-specific changes or failure history justify it.

Playwright uses one worker and a shared persistent backend root, which avoids races but forces all feature tests to be serial and encourages state cleanup by convention.
Introduce fixtures that create and delete a workflow per test, eliminate `Date.now()`/random naming where a deterministic test ID is enough, and then shard independent spec groups across isolated server/root pairs.

The fixed `page.waitForTimeout(350)` in `logger-panel.spec.ts` has been replaced with an actual WebSocket log event and an observable filtered-row transition.
Keep the file-watcher timeout in `hot-reload.spec.ts` as a bounded integration timeout, but make timeout failures report watcher/backend state.

CI still retries browser failures twice, but Playwright now enables `failOnFlakyTests` in CI so a pass-on-retry remains a failing quality signal.
Quarantine any demonstrably flaky test with an owner and expiry rather than silently normalizing retries.

There are no screenshot assertions and no automated accessibility audit in the Playwright suite.
Do not create a large screenshot-baseline suite, but consider a few stable visual assertions for the sub-workflow border, canvas shell, and critical dialogs, plus an accessibility scan of the main shell and modal flows.

The browser lane still runs the Vite development server, but the deterministic check and comprehensive lane now run `bun run build` before browser certification.

## Recommended test lanes

### Required on every change

1. Backend lint and deterministic unit/service/router tests with branch coverage and warning enforcement.
2. Frontend lint, type-check, fast Node-environment unit tests, and JSDOM component tests with coverage.
3. Chromium critical feature journeys with retries treated as flaky failures.
4. A generated OpenAPI TypeScript check that fails when `frontend/src/api/types.ts` differs from the backend schema.

### Scheduled or change-triggered

1. Compact Firefox compatibility suite, with the full Firefox suite available manually.
2. External pinned common-tools certification, as already configured.
3. Real library archive round-trip certification.
4. Targeted mutation testing for graph, clipboard, execution, and persistence decision logic.
5. Longer recovery/fault-injection and filesystem-watcher tests if they become too slow for the required lane.

## Prioritized implementation plan

### P0: restore trust in signals

1. Completed in the small cleanup: fix and then fail on SQLite/resource warnings.
2. Coverage instrumentation and artifacts are complete; establish non-regression thresholds after the baselines stabilize.
3. Resolve the custom-tool context-menu specification contradiction.
4. Add a real recursive sub-workflow execution/cache/log test.
5. Add a real export→import archive round trip.

### P1: cover real v2 journeys

1. Add a nested sub-workflow edit→save and edit→discard browser flow.
2. Add a cross-workflow paste flow with missing-tool/version-reset warnings and one-step undo.
3. Replace the shallow Create Tool dialog E2E with create→registry→editor-open→hot-reload→rename/delete coverage.
4. Extend dataset E2E coverage to movement, recursive selection, revision-conflict delete, and browser picker mode.
5. Add one consolidated data-table E2E covering upstream depth, merged fallback, sorting, CSV, and image-path actions.

### P2: reduce runtime and maintenance cost

1. Completed: split Node, JSDOM, and IndexedDB Vitest environments and scope fake IndexedDB setup.
2. Scope backend runtime directories and application construction to tests that need them.
3. Remove fixed sleeps and introduce deterministic synchronization helpers.
4. Consolidate trivial model/framework tests and overlapping frontend ownership after mutation checks.
5. Isolate browser state per shard and parallelize only independent feature groups.

## Success criteria

The suite is in a healthier state when every normative v2 area has at least one test at the lowest useful layer, each critical user journey has one vertical test through real frontend/backend boundaries, backend and frontend branch coverage cannot regress silently, warnings fail the build, Chromium remains comfortably under one minute on CI hardware, the required unit lanes become materially faster, and no test exists solely to prove framework arithmetic, importability, or duplicate wiring.
