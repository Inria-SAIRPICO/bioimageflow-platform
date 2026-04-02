# Tools Panel — TDD Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers-extended-cc:subagent-driven-development (recommended) or superpowers-extended-cc:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Tools Panel (left sidebar) -- a searchable, hierarchical table of tool packages and tools that supports drag-to-canvas, version management, environment controls, and tool creation.

**Architecture:** The Tools Panel is a Vue component backed by a Pinia `toolRegistryStore` that caches data from two backend endpoints: `GET /tools` (tool-level metadata for graph construction) and `GET /tools/packages` (package-level metadata for the table). The panel uses PrimeVue's TreeTable for the hierarchical package->tool display. Drag-and-drop uses the HTML5 Drag API, emitting a custom event that the Canvas consumes.

**Tech Stack:** Vue 3, TypeScript, PrimeVue (TreeTable, InputText, Button, Dialog), Pinia, Vitest (unit), Playwright (E2E)

**Prerequisites:** Project scaffolding complete, backend core models defined, Pinia stores skeleton exists.

**User Verification:** NO

**Parallelization:** Backend tasks (1-9) and frontend tasks (10-15) can run in parallel once the API contract (models + endpoint signatures) is locked after Task 1. Lock the contract early and share the TypeScript types via `frontend/src/api/types.ts`.

---

## `create_app()` Design

`create_app(config: AppConfig)` where `AppConfig` is a dataclass holding `tool_registry`, `workflow_root`, `deployment_mode`, `package_installer`, and future services. This prevents the function signature from growing with every plan. Tests create `AppConfig` with overrides for only the fields they need; all others use sensible defaults (empty registry, `Path.cwd()`, `"desktop"` mode).

---

## API Contract (gui_specs_v1.md Section 2.4.1)

All endpoints are prefixed with `/api/v1`.

| Method | Path | Description | Gate |
|--------|------|-------------|------|
| GET | `/tools` | List all tool metadata | -- |
| POST | `/tools` | Create tool from template | desktop only |
| DELETE | `/tools/{tool_name}` | Delete a user tool file | desktop only |
| PATCH | `/tools/{tool_name}` | Rename a user tool file | desktop only |
| GET | `/tools/{tool_name}/source` | Get source file path for a tool | -- |
| GET | `/tools/packages` | List all packages with versions and env status | -- |
| POST | `/tools/packages/{package_name}/install` | Install a package version via uv | -- |
| DELETE | `/tools/packages/{package_name}` | Uninstall a package (with optional `?version=` query param) | -- |
| POST | `/tools/environments/{env_name}/start` | Start a conda/pixi environment | -- |
| POST | `/tools/environments/{env_name}/stop` | Stop a running environment | -- |

---

## File Structure

```
backend/
  src/bioimageflow_server/
    models/tools.py          # ToolMetadata, PackageInfo, ToolCreate, ToolRename, AppConfig
    routers/tools.py         # All /tools/* endpoints
    services/
      tool_registry.py       # In-memory registry of tools and packages
      package_installer.py   # Package install/uninstall via uv
  tests/
    test_models/test_tools.py
    test_routers/test_tools.py
    test_services/test_tool_registry.py

frontend/
  src/
    stores/toolRegistry.ts
    components/panels/ToolsPanel.vue
    components/panels/CreateToolDialog.vue
    components/panels/__tests__/ToolsPanel.test.ts
    components/panels/__tests__/CreateToolDialog.test.ts
    api/types.ts             # ToolMetadata, PackageInfo TS interfaces
  tests/
    unit/stores/toolRegistry.test.ts
```

---

## PrimeVue TreeTable Testing Note

TreeTable hierarchical rendering is difficult to unit test reliably with jsdom because TreeTable relies on DOM measurements and internal PrimeVue state. **Recommendation:** Focus unit tests on the Pinia store logic (filtering, tree node computation, version row building). Defer visual TreeTable rendering verification (expand/collapse, row rendering) to E2E tests with Playwright where a real browser is available.

---

## Backend Tasks

### Task 1: Tool Metadata Pydantic Models

**Files:** Create `models/tools.py`, test in `test_models/test_tools.py`

Define these Pydantic models:
- `InputFieldSchema` -- fields: `type` (str), `connectable` (bool, default True), `default` (Any, None), `description` (str), `min`/`max`/`step` (optional float), `group` (optional str)
- `OutputFieldSchema` -- fields: `type` (str)
- `ToolMetadata` -- fields: `name`, `display_name`, `package`, `package_version`, `tool_type` (str), `documentation` (str, default ""), `tags` (list[str], default []), `categories` (list[str], default []), `inputs` (dict[str, InputFieldSchema]), `outputs` (dict[str, OutputFieldSchema]), `environment` (dict | None)

**Tests to write:**
- [ ] Full ToolMetadata construction with all fields populated; assert nested field access (e.g., `inputs["diameter"].min`)
- [ ] ToolMetadata with only required fields; verify defaults (`documentation=""`, `tags=[]`, `environment=None`)
- [ ] InputFieldSchema `connectable` defaults to True
- [ ] Run tests, confirm failure (module not found), implement, confirm pass
- [ ] Commit

---

### Task 2: PackageInfo and Request/Response Models

**Files:** Append to `models/tools.py`, test in `test_models/test_tools.py`

Define:
- `PackageInfo` -- fields: `name` (str), `installed_versions` (list[str], default []), `available_versions` (list[str], default []), `tools` (dict[str, list[str]], default {}), `environment_status` (str, default "stopped"; values: "stopped" | "creating" | "running")
- `ToolCreate` -- fields: `name` (str), `tool_type` (Literal["ProcessingTool", "DataFrameTool"])
- `ToolRename` -- fields: `new_name` (str)
- `AppConfig` dataclass -- fields: `tool_registry` (ToolRegistryService | None), `workflow_root` (Path | None), `deployment_mode` (str, default "desktop"), `package_installer` (PackageInstallerService | None)

**Tests to write:**
- [ ] PackageInfo full construction; assert `tools["1.2.0"]` returns tool list
- [ ] PackageInfo defaults; assert `environment_status == "stopped"`
- [ ] Commit

---

### Task 3: Tool Registry Service

**Files:** Create `services/tool_registry.py`, test in `test_services/test_tool_registry.py`

`ToolRegistryService` -- an in-memory dict-backed registry with these methods:
- `register_tool(class_name: str, metadata: ToolMetadata) -> None`
- `get_tool(class_name: str) -> ToolMetadata | None`
- `list_tools() -> list[ToolMetadata]`
- `register_package(name: str, info: PackageInfo) -> None`
- `get_package(name: str) -> PackageInfo | None`
- `list_packages() -> list[PackageInfo]`

**Tests to write:**
- [ ] Empty registry returns empty lists and None for lookups
- [ ] Register a tool, then get it by name; assert equality
- [ ] Register 3 tools, list_tools returns all 3
- [ ] Same pattern for packages
- [ ] Commit

---

### Task 4: GET /tools Endpoint

**Files:** Create `routers/tools.py`, modify `app.py` to accept `AppConfig` and register router, test in `test_routers/test_tools.py`

Router at prefix `/tools` with tag `"tools"`. Uses FastAPI `Depends()` for `get_tool_registry` (stub that raises NotImplementedError; overridden by `app.dependency_overrides`).

`GET /tools` -> returns `list[ToolMetadata]` from `registry.list_tools()`.

Wire into `create_app(config: AppConfig)` which sets up dependency overrides from config fields.

**Tests to write:**
- [ ] GET /tools with one registered tool returns 200, list of length 1, correct name/display_name
- [ ] GET /tools with empty registry returns 200 and `[]`
- [ ] Commit

---

### Task 5: GET /tools/packages Endpoint

**Files:** Modify `routers/tools.py`, test in `test_routers/test_tools.py`

`GET /tools/packages` -> returns `list[PackageInfo]` from `registry.list_packages()`.

**Tests to write:**
- [ ] GET /tools/packages with one registered package returns 200, correct structure including nested `tools` dict
- [ ] GET /tools/packages with empty registry returns 200 and `[]`
- [ ] Commit

---

### Task 6: POST /tools (Create Tool from Template)

**Files:** Modify `routers/tools.py`, test in `test_routers/test_tools.py`

`POST /tools` accepts `ToolCreate` body. Generates a Python file from a template (ProcessingTool or DataFrameTool) in `{workflow_root}/tools/{snake_name}.py`. Returns 201 with `{name, tool_type, path}`. Returns 403 in webapp mode.

Helpers needed: `_name_to_snake(name)` (CamelCase -> snake_case), `_name_to_display(name)` (CamelCase -> "Camel Case"). Templates should include the standard bioimageflow imports, class skeleton, and required methods (`process_row` for ProcessingTool, `transform` for DataFrameTool).

**Tests to write:**
- [ ] POST with ProcessingTool type returns 201; verify file exists at `tmp_path/tools/my_new_tool.py`; file contains `class MyNewTool(ProcessingTool):` and `def process_row`
- [ ] POST with DataFrameTool type returns 201; file contains `class MyTransform(DataFrameTool):` and `def transform`
- [ ] POST in webapp mode returns 403
- [ ] POST with duplicate tool name (file already exists) returns 409 Conflict
- [ ] Commit

---

### Task 7: DELETE /tools/{tool_name} and PATCH /tools/{tool_name}

**Files:** Modify `routers/tools.py`, test in `test_routers/test_tools.py`

`DELETE /tools/{tool_name}` -- deletes `{workflow_root}/tools/{tool_name}.py`. Returns 200 or 404 if not found.

`PATCH /tools/{tool_name}` -- accepts `ToolRename` body, renames the file. Returns 200 or 404 if source not found.

**Tests to write:**
- [ ] DELETE existing tool file returns 200, file no longer exists
- [ ] DELETE nonexistent tool returns 404
- [ ] PATCH renames file from `old_tool.py` to `new_tool.py`; old gone, new exists
- [ ] PATCH nonexistent tool returns 404
- [ ] Commit

---

### Task 8: Package Install/Uninstall Endpoints

**Files:** Create `services/package_installer.py`, modify `routers/tools.py`, test in `test_routers/test_tools.py`

`PackageInstallerService` -- stub service with async methods:
- `install(package_name: str, version: str | None) -> PackageInfo` (TODO: actual `uv pip install`)
- `uninstall(package_name: str, version: str | None) -> dict` (TODO: actual uninstall)

Endpoints:
- `POST /tools/packages/{package_name}/install` -- accepts `{"version": "1.2.0"}`, delegates to installer
- `DELETE /tools/packages/{package_name}` -- accepts optional `?version=` query param, delegates to installer

Wire `get_package_installer` dependency from `AppConfig`.

**Tests to write (mock the installer):**
- [ ] POST install calls `installer.install()` with correct args, returns 200
- [ ] DELETE uninstall calls `installer.uninstall()`, returns 200
- [ ] POST install with network error (mock raises) returns 502 with error message
- [ ] POST install with package not found (mock raises PackageNotFoundError) returns 404
- [ ] Commit

---

### Task 9: Environment Start/Stop Endpoints + GET /tools/{tool_name}/source

**Files:** Modify `routers/tools.py`, test in `test_routers/test_tools.py`

Endpoints:
- `POST /tools/environments/{env_name}/start` -- returns `{"env_name": ..., "status": "creating"}` (stub; TODO: integrate with Wetlands EnvironmentManager)
- `POST /tools/environments/{env_name}/stop` -- returns `{"env_name": ..., "status": "stopped"}`
- `GET /tools/{tool_name}/source` -- looks up tool in registry, returns `{"tool_name": ..., "path": ...}` or 404

**Tests to write:**
- [ ] POST start returns 200, status is "creating"
- [ ] POST stop returns 200, status is "stopped"
- [ ] POST start for nonexistent env -- decide behavior (currently returns 200 stub; note that real integration will need error handling)
- [ ] GET source for registered tool returns 200 with path
- [ ] GET source for unknown tool returns 404
- [ ] Commit

---

## Frontend Tasks

### Task 10: TypeScript Interfaces

**Files:** Update `frontend/src/api/types.ts`

Define TS interfaces matching the backend models: `InputFieldSchema`, `OutputFieldSchema`, `ToolMetadata`, `PackageInfo`. These are the shared contract.

- [ ] Write interfaces, no tests needed (pure types)
- [ ] Commit

---

### Task 11: Tool Registry Pinia Store

**Files:** Create `frontend/src/stores/toolRegistry.ts`, test in `frontend/tests/unit/stores/toolRegistry.test.ts`

Store using `defineStore` (composition API style) with:
- State: `tools: ToolMetadata[]`, `packages: PackageInfo[]`
- Actions: `fetchTools()` (GET /tools), `fetchPackages()` (GET /tools/packages)
- Getters: `getToolByName(name) -> ToolMetadata | undefined`, `searchTools(query) -> ToolMetadata[]` (filters by name, display_name, tags, categories; case-insensitive; empty query returns all)

**Tests to write (mock API client):**
- [ ] Store starts with empty tools and packages
- [ ] `fetchTools` populates tools from mocked GET response
- [ ] `fetchPackages` populates packages from mocked GET response
- [ ] `getToolByName` returns correct tool or undefined
- [ ] `searchTools` filters by name substring, tag match, category match; empty query returns all
- [ ] `searchTools` is case-insensitive
- [ ] Commit

---

### Task 12: ToolsPanel Component

**Files:** Create `frontend/src/components/panels/ToolsPanel.vue`, test in `__tests__/ToolsPanel.test.ts`

Component structure:
- Search input (`data-testid="tool-search"`) bound to a `searchQuery` ref
- Computed `treeNodes` that groups `searchTools(query)` results by package, producing TreeTable-compatible node structure (package rows with tool children)
- PrimeVue TreeTable rendering the tree with columns: Name (expander), Categories, Tags
- Tool rows are draggable (`draggable="true"`, sets `application/bioimageflow-tool` drag data) and clickable (emits `add-tool` event)
- "Create Tool" button (`data-testid="create-tool-btn"`) emits `create-tool` event

**Tests to write (focus on store logic, not TreeTable rendering):**
- [ ] Renders search input element
- [ ] Renders "Create Tool" button
- [ ] `treeNodes` computed groups tools by package correctly (test the computed, not the DOM)
- [ ] Search filtering: setting `searchQuery` to "cellpose" filters out non-matching tools in `treeNodes`
- [ ] Drag start sets correct dataTransfer data (if testable; otherwise defer to E2E)
- [ ] Click on tool row emits `add-tool` with tool name
- [ ] Commit

---

### Task 13: Create Tool Dialog

**Files:** Create `frontend/src/components/panels/CreateToolDialog.vue`, test in `__tests__/CreateToolDialog.test.ts`

Dialog with:
- Name input (`data-testid="tool-name-input"`)
- Tool type dropdown (`data-testid="tool-type-select"`) defaulting to "ProcessingTool"
- Create button calls `POST /api/v1/tools`, emits `created` event on success, closes dialog
- Cancel button emits `update:visible` to close

**Tests to write:**
- [ ] Renders name input and type dropdown
- [ ] Defaults tool type to "ProcessingTool"
- [ ] Create button calls POST /tools with correct payload
- [ ] Cancel emits `update:visible`
- [ ] Create button is disabled when name is empty
- [ ] Commit

---

### Task 14: Version Management UI

**Files:** Modify `ToolsPanel.vue`, test in `__tests__/ToolsPanel.test.ts`

Add to ToolsPanel:
- `getVersionRows(packageName) -> {version, installed}[]` -- merges `installed_versions` and `available_versions`, sorted, with an `installed` boolean flag
- `installVersion(packageName, version)` -- calls POST install endpoint, then refreshes packages
- `uninstallVersion(packageName, version)` -- calls DELETE endpoint, then refreshes packages
- Template: expandable version list inside package rows showing install/uninstall buttons per version

**Tests to write (on the computed/method logic):**
- [ ] `getVersionRows` merges installed and available, marks installed correctly
- [ ] `getVersionRows` for unknown package returns empty array
- [ ] `installVersion` calls correct API endpoint
- [ ] `uninstallVersion` calls correct API endpoint
- [ ] Commit

---

### Task 15: Environment Controls

**Files:** Modify `ToolsPanel.vue`, test in `__tests__/ToolsPanel.test.ts`

Add to package rows:
- Environment status badge (`data-testid="env-status-{name}"`) showing "stopped"/"creating"/"running"
- Toggle button (`data-testid="env-toggle-{name}"`) that calls start or stop endpoint based on current status, then refreshes packages

`toggleEnvironment(envName, currentStatus)` -- if running, POST stop; otherwise POST start.

**Tests to write:**
- [ ] Environment badge renders with correct status text
- [ ] Toggle calls start endpoint when status is "stopped"
- [ ] Toggle calls stop endpoint when status is "running"
- [ ] After toggle, `fetchPackages` is called to refresh state
- [ ] Commit

---

## Error Handling Tests (cross-cutting, add to relevant task test files)

These error scenarios should be covered in the router tests (Task 8 and Task 9 primarily):

- [ ] **Failed install** -- mock installer raises an exception; endpoint returns 502 with error detail
- [ ] **Package not found** -- mock installer raises `PackageNotFoundError`; endpoint returns 404
- [ ] **Network error during install** -- mock installer raises `ConnectionError`; endpoint returns 502
- [ ] **Duplicate tool name on POST /tools** -- tool file already exists at target path; endpoint returns 409 Conflict

Frontend store tests should also verify:
- [ ] `fetchTools` handles API error gracefully (sets error state or re-raises)
- [ ] `fetchPackages` handles API error gracefully

---

### Task 16: Integration Test — Tools Panel E2E

**Files:** Create `frontend/tests/e2e/tools-panel.spec.ts`

**Prerequisites:** Backend running with tool registry containing mock tools/packages. Frontend running.

**What to test (Playwright):**
- Navigate to `/`, verify the tools panel is visible
- Verify the tool search input exists (`data-testid="tool-search"`)
- Type "cellpose" in the search input, verify the tree filters to show only matching tools
- Clear the search, verify all tools reappear
- Verify a tool row is draggable: initiate drag on a tool row, verify `dataTransfer` is set (or that the drag visual appears)
- Click "Create Tool" button, verify the create tool dialog opens with name input and type selector
- Verify the "Create Tool" button is hidden when `deployment_mode === "webapp"` (if settings store is available with webapp mode)
- Verify no console errors throughout

**Verify:** `cd frontend && bun run test:e2e -- --grep "tools panel"` passes

- [ ] Write Playwright test with mock backend data
- [ ] Run test — should pass
- [ ] Commit — `test(frontend): add tools panel E2E integration test`
