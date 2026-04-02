# Pinia Stores — TDD Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers-extended-cc:subagent-driven-development (recommended) or superpowers-extended-cc:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the non-graph Pinia stores that manage application state shared across components: execution status, settings, and UI state. Vue Flow owns graph state — these stores handle everything else.

**Architecture:** Each store is a Pinia composable store (`defineStore` with setup syntax). Stores fetch data from the backend API and expose reactive state + actions. Tool registry store is defined in the Tools Panel plan — not duplicated here.

**Tech Stack:** Vue 3, TypeScript, Pinia, Vitest, bun

**User Verification:** NO

**Prerequisites:** Frontend scaffold complete, API client (`@/api/client`) available, TypeScript types (`@/api/types`) available.

> **Note — datasets store:** The spec (Section 3.1) says Pinia manages "settings, tool registry, execution status, datasets." A datasets store will be needed for webapp mode but is deferred to the Dataset Browser plan (component 18).

---

## File Structure

```
frontend/src/stores/
├── toolRegistry.ts          # Defined in Tools Panel plan — not duplicated here
├── execution.ts             # Execution state (running/idle, progress, last result)
├── settings.ts              # App settings from GET /settings
└── ui.ts                    # UI-only state (selected nodes, panel visibility, etc.)

frontend/tests/unit/stores/
├── toolRegistry.test.ts     # Defined in Tools Panel plan
├── execution.test.ts
├── settings.test.ts
└── ui.test.ts
```

---

### Task 1: Execution Store

**Files:**
- Create: `frontend/src/stores/execution.ts`
- Test: `frontend/tests/unit/stores/execution.test.ts`

- [ ] **Step 1: Write failing tests**

Mock `@/api/client` (api.get, api.post). Tests to write:

- **starts idle with no result** — initial state is "idle", isRunning false, lastResult null, progress null
- **fetchStatus populates state from server** — mock GET `/api/v1/execution/status` returning `{state: "running", last_result: null, progress: {node_id, row, total_rows}}`. Assert store state, isRunning, and progress update accordingly.
- **run sends POST and sets state to running** — call `store.run(graph)`, assert POST to `/api/v1/execution/run` with `{graph, nodes: undefined}`, state becomes "running"
- **run with specific nodes passes node list** — call `store.run(graph, ["seg_1", "stats_1"])`, assert nodes array in POST body
- **stop sends POST /execution/stop** — set state to running, call stop, assert POST sent
- **clear sends POST /execution/clear with node IDs** — assert POST to `/api/v1/execution/clear` with `{nodes: ["seg_1"]}`, verify response returned
- **applyProgress updates progress state** — call applyProgress with `{node_id, row, total_rows}`, verify progress ref updated
- **applyExecutionComplete updates state to idle** — set state to running, call applyExecutionComplete with `{success, errors, node_statuses}`. Assert state becomes idle, isRunning false, lastResult populated, progress cleared.
- **run rejects when already running** — set state to running, assert `store.run(...)` rejects with "already running"
- **fetchStatus handles API errors gracefully** — mock api.get to reject with a network error. Assert store sets an error state and does not throw unhandled.
- **run handles API errors gracefully** — mock api.post to reject with 500. Assert state reverts to idle and error is captured.

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && bun run vitest run tests/unit/stores/execution.test.ts`
Expected: FAIL with module not found

- [ ] **Step 3: Implement execution store**

Create `frontend/src/stores/execution.ts` using `defineStore("execution", () => {...})` setup syntax.

**Reactive state:** `state` (ref, "running" | "idle"), `lastResult` (ref, ExecutionResult | null), `progress` (ref, ProgressInfo | null), `error` (ref, string | null).

**Computed:** `isRunning` derived from state === "running".

**Actions:**
- `fetchStatus()` — GET `/api/v1/execution/status`, populate state/lastResult/progress. Wrap in try/catch, set error on failure.
- `run(graph: GraphState, nodes?: string[])` — guard against already running (throw). Set running, clear lastResult/progress, POST `/api/v1/execution/run`. On failure, revert to idle, set error.
- `stop()` — POST `/api/v1/execution/stop`
- `clear(nodeIds: string[])` — POST `/api/v1/execution/clear` with `{nodes}`, return response data
- `applyProgress(p: ProgressInfo)` — update progress ref (called from WebSocket handler)
- `applyExecutionComplete(payload)` — set idle, clear progress, populate lastResult

Import types `GraphState`, `NodeStatus`, `ExecutionResult`, `ProgressInfo` from `@/api/types`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && bun run vitest run tests/unit/stores/execution.test.ts`
Expected: PASS

- [ ] **Step 5: Commit**

Stage `frontend/src/stores/execution.ts` and `frontend/tests/unit/stores/execution.test.ts`. Commit message: `feat(frontend): add execution Pinia store`

---

### Task 2: Settings Store

**Files:**
- Create: `frontend/src/stores/settings.ts`
- Test: `frontend/tests/unit/stores/settings.test.ts`

- [ ] **Step 1: Write failing tests**

Mock `@/api/client` (api.get, api.patch). Tests to write:

- **starts with null settings** — settings null, isLoaded false
- **fetchSettings loads from server** — mock GET `/api/v1/settings` returning a full settings object. Assert store.settings populated, isLoaded true.
- **isDesktop returns true for desktop mode** — fetch settings with `deployment_mode: "desktop"`, assert isDesktop true, isWebapp false
- **isWebapp returns true for webapp mode** — same pattern with "webapp"
- **updateSettings sends PATCH and updates local state** — fetch first, then call `updateSettings({external_editor: "code {file_path}"})`. Assert PATCH to `/api/v1/settings`, local state updated from response.
- **deploymentMode is accessible before settings load** — before fetch, isDesktop and isWebapp both false (no crash)
- **fetchSettings handles API errors gracefully** — mock api.get to reject with network error. Assert error state set, no unhandled throw. "Test that fetchSettings gracefully handles API errors (sets error state, doesn't crash)."
- **updateSettings handles API errors gracefully** — mock api.patch to reject with 500. Assert settings unchanged, error captured.

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && bun run vitest run tests/unit/stores/settings.test.ts`
Expected: FAIL with module not found

- [ ] **Step 3: Implement settings store**

Create `frontend/src/stores/settings.ts` using `defineStore("settings", () => {...})`.

**Reactive state:** `settings` (ref, Settings | null), `error` (ref, string | null).

**Computed:** `isLoaded`, `isDesktop`, `isWebapp`.

**Actions:**
- `fetchSettings()` — GET `/api/v1/settings`, set settings ref. Try/catch, set error on failure.
- `updateSettings(partial: Partial<Settings>)` — PATCH `/api/v1/settings`, update settings from response. Try/catch, set error on failure.

Import `Settings` from `@/api/types`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && bun run vitest run tests/unit/stores/settings.test.ts`
Expected: PASS

- [ ] **Step 5: Commit**

Stage `frontend/src/stores/settings.ts` and `frontend/tests/unit/stores/settings.test.ts`. Commit message: `feat(frontend): add settings Pinia store`

---

### Task 3: UI State Store

**Files:**
- Create: `frontend/src/stores/ui.ts`
- Test: `frontend/tests/unit/stores/ui.test.ts`

- [ ] **Step 1: Write failing tests**

No API mock needed — this is a pure client-side store. Tests to write:

- **starts with no selection** — selectedNodeIds empty, hasSelection false, isSingleSelection false, isMultiSelection false
- **setSelectedNodes updates selection** — set two IDs, assert hasSelection true, isMultiSelection true
- **clearSelection clears all** — set a node, clear, assert empty
- **single selection is detected** — set one ID, isSingleSelection true, isMultiSelection false
- **tracks active workflow name** — starts null, setActiveWorkflow updates it
- **tracks unsaved changes** — starts false, markDirty sets true, markClean resets
- **tracks execution lock state** — starts false, setExecutionLocked toggles
- **tracks panel visibility** — default: tools, nodePanel, dataTable, logger all true
- **togglePanel flips visibility** — toggle tools off then on
- **browser tab title reflects workflow name** — "BioImageFlow -- My Pipeline"
- **browser tab title shows asterisk for unsaved changes** — "BioImageFlow -- My Pipeline *"
- **browser tab title with no workflow** — just "BioImageFlow"

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && bun run vitest run tests/unit/stores/ui.test.ts`
Expected: FAIL with module not found

- [ ] **Step 3: Implement UI store**

Create `frontend/src/stores/ui.ts` using `defineStore("ui", () => {...})`.

**Reactive state:** `selectedNodeIds` (ref string[]), `activeWorkflowName` (ref string | null), `hasUnsavedChanges` (ref boolean), `isExecutionLocked` (ref boolean), `panels` (reactive object with boolean flags: tools, nodePanel, dataTable, logger — all default true).

**Computed:** `hasSelection`, `isSingleSelection`, `isMultiSelection` (derived from selectedNodeIds length). `tabTitle` — "BioImageFlow" base, append " -- {name}" if workflow set, append " *" if dirty.

**Actions:** `setSelectedNodes(ids)`, `clearSelection()`, `setActiveWorkflow(name)`, `markDirty()`, `markClean()`, `setExecutionLocked(locked)`, `togglePanel(panel)`.

No API imports needed.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && bun run vitest run tests/unit/stores/ui.test.ts`
Expected: PASS

- [ ] **Step 5: Commit**

Stage `frontend/src/stores/ui.ts` and `frontend/tests/unit/stores/ui.test.ts`. Commit message: `feat(frontend): add UI state Pinia store`

---

### Task 4: Add Types to Frontend Types

**Files:**
- Modify: `frontend/src/api/types.ts`
- Test: `frontend/tests/unit/stores/settings-types.test.ts`

> **Important:** Before adding types, check if they already exist in the scaffolding plan's placeholder types.ts. Only add what's missing. Do not duplicate.

- [ ] **Step 1: Write failing test that imports types**

Write a test that imports `Settings`, `OMEROInstance`, `ProgressInfo`, `ExecutionResult`, `ExecutionStatus` from `@/api/types` and validates their structure with simple object assignments. This ensures the types exist and are exported.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && bun run vitest run tests/unit/stores/settings-types.test.ts`
Expected: FAIL if any type is missing from types.ts

- [ ] **Step 3: Add missing types to types.ts**

Check what already exists in `frontend/src/api/types.ts`. Only add what is missing from:

- `OMEROInstance` — host (string), port (number, optional), username (string), name (string | null, optional)
- `Settings` — deployment_mode ("desktop" | "webapp"), output_data_folder (string), plus optional fields: external_editor, napari_env_path, omero_instances, tool_store_path, update_mode, execution_engine ("sequential" | "parsl"), cache_max_executions, cache_max_age, keyboard_shortcuts, dev_mode
- `ProgressInfo` — node_id (string), row (number), total_rows (number)
- `ExecutionResult` — success (boolean), errors (unknown[]), node_statuses (Record<string, NodeStatus>)
- `ExecutionStatus` — state ("running" | "idle"), last_result (ExecutionResult | null), progress (ProgressInfo | null)

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && bun run vitest run tests/unit/stores/settings-types.test.ts`
Expected: PASS

- [ ] **Step 5: Commit**

Stage `frontend/src/api/types.ts` and `frontend/tests/unit/stores/settings-types.test.ts`. Commit message: `feat(frontend): ensure Settings and execution types in API types`

---

### Task 5: Verify All Stores Work Together

**Files:**
- Test: `frontend/tests/unit/stores/integration.test.ts`

- [ ] **Step 1: Write integration test**

Mock `@/api/client`. Tests to write:

- **execution lock propagates to UI store** — set execution state to running, set UI executionLocked true. Assert both stores reflect expected state. (Verifies stores coexist without conflict.)
- **all stores can coexist in the same Pinia instance** — instantiate all three stores (execution, settings, ui) in one Pinia. Assert each has correct initial state.
- **workflow name in UI store drives tab title** — set workflow name, verify tabTitle. Mark dirty, verify asterisk appended.

- [ ] **Step 2: Run integration test**

Run: `cd frontend && bun run vitest run tests/unit/stores/integration.test.ts`
Expected: PASS

- [ ] **Step 3: Run all store tests together**

Run: `cd frontend && bun run vitest run tests/unit/stores/`
Expected: All tests pass.

- [ ] **Step 4: Commit**

Stage `frontend/tests/unit/stores/integration.test.ts`. Commit message: `test(frontend): add stores integration test`

---

### Task 6: Integration Test — Stores E2E Verification

**Files:** Create `frontend/tests/e2e/stores-integration.spec.ts`

**Prerequisites:** Backend running with health endpoint. Frontend running with Pinia installed.

**What to test (Playwright):**
- Navigate to `/`
- Execute JavaScript in the browser to access the Vue app instance and verify Pinia is installed (`document.querySelector('#app').__vue_app__.config.globalProperties.$pinia`)
- Verify no console errors from store initialization
- Verify no unexpected failed network requests (no 404s or 500s on API calls)

**Verify:** `cd frontend && bun run test:e2e -- --grep "stores"` passes

- [ ] Write Playwright test
- [ ] Run test — should pass
- [ ] Commit — `test(frontend): add stores E2E integration test`
