# BioImageFlow GUI Platform — General TDD Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers-extended-cc:subagent-driven-development (recommended) or superpowers-extended-cc:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the BioImageFlow GUI platform — a Vue SPA frontend + FastAPI backend that wraps the BioImageFlow library with a visual node-based workflow editor.

**Architecture:** Client-server model. The frontend (Vue + Vue Flow + Dockview + PrimeVue) owns the graph state and sends it to the backend (FastAPI) for validation and execution. The backend is a thin adapter between the frontend and the existing `bioimageflow` library. Communication uses REST + WebSocket.

**Tech Stack:**
- **Frontend:** Vue 3, TypeScript, Vue Flow, Dockview, PrimeVue, Pinia, Vite, Vitest, Playwright
- **Backend:** Python 3.12, FastAPI, uvicorn, Pydantic, pytest, httpx (test client)
- **Package management:** uv (Python), bun (JS/TS)
- **Monorepo layout:** `frontend/` and `backend/` at project root

---

## Component Breakdown

The platform is split into the following independent components, each with its own specific TDD plan. Components are listed in dependency order — earlier components are prerequisites for later ones.

### Phase 1: Foundation

| # | Component | Description | Specific Plan | Plan Status |
|---|-----------|-------------|---------------|-------------|
| 1 | **Project Scaffolding** | Monorepo setup, build configs, CI, dev server, linting, type generation from OpenAPI | `2026-04-01-scaffolding.md` | Written |
| 2 | **Backend Core** | FastAPI app shell, Pydantic models (GraphState, NodeState, Edge, NodeStatus, ValidationResult, GraphValidationError), health endpoint, CORS, error response format | `2026-04-01-backend-core.md` | Written |
| 3 | **Pinia Stores** | Non-graph state stores: tool registry, execution status, settings, UI state | `2026-04-01-pinia-stores.md` | Written |

**Parallelization:** Components 2 and 3 are independent of each other (both depend only on 1). Two agents can work on Backend Core and Pinia Stores simultaneously once Scaffolding is complete.

### Phase 2: Core Editor

| # | Component | Description | Specific Plan | Plan Status |
|---|-----------|-------------|---------------|-------------|
| 4 | **Tools Panel** | Left sidebar — tool/package table, search, drag-to-canvas, version management, env controls | `2026-04-01-tools-panel.md` | Written |
| 5 | **Canvas (Node Programming Interface)** | Central DAG editor — nodes, edges, pins, selection, copy/paste, undo/redo, canvas controls, status reconciliation | `2026-04-01-canvas.md` | Written |
| 6 | **Node Panel** | Right sidebar — parameter editing, output fields, resource config, node logs, action bar | `2026-04-01-node-panel.md` | Pending |

**Parallelization:** Components 4 and 5 are independent (both depend on Pinia Stores). Two agents can work on Tools Panel and Canvas simultaneously. Node Panel (6) must wait for Canvas (5). **Note:** Canvas (5) depends on `toolRegistryStore` which is defined in Tools Panel plan Task 11. This task must be completed before Canvas work can begin, or the store definition must be extracted and completed as part of Pinia Stores (3).

### Phase 3: Validation & Execution

| # | Component | Description | Specific Plan | Plan Status |
|---|-----------|-------------|---------------|-------------|
| 7 | **Graph Validation Pipeline** | Backend PUT /graph, PATCH /graph/nodes/{id}/parameters, cycle detection, type compatibility, parameter validation, cache status, debounce/cancel on frontend | `2026-04-01-graph-validation.md` | Pending |
| 8 | **Execution System** | POST /execution/run|stop|clear, GET /execution/status, execution banner, graph locking, progress tracking, error recovery | `2026-04-01-execution.md` | Pending |
| 9 | **WebSocket Layer** | /ws connection, server->client messages (progress, node_state, log, execution_complete, tool_reload, package_install, environment_status, ack), client->server (subscribe_logs), reconnection with backoff | `2026-04-01-websocket.md` | Pending |

**Parallelization:** Graph Validation (7) and WebSocket Layer (9) are independent and can be developed in parallel by two agents, provided WebSocket message interfaces are locked before work begins. Execution System (8) depends on Graph Validation (7) completing first. WebSocket (9) depends only on Backend Core (2), so it can start as soon as Phase 1 is done — it does not need to wait for Phase 2.

### Phase 4: Data & Viewing

| # | Component | Description | Specific Plan | Plan Status |
|---|-----------|-------------|---------------|-------------|
| 10 | **Data Table** | Bottom panel tab 1 — output DataFrames, pagination, sorting, image thumbnails, multi-node stacking | `2026-04-01-data-table.md` | Pending |
| 11 | **Logger Panel** | Bottom panel tab 2 — real-time logs, level/node filter, search, auto-scroll | `2026-04-01-logger-panel.md` | Pending |
| 12 | **Image Viewer** | Napari integration (NapariLauncher, /napari/* endpoints) | `2026-04-01-image-viewer.md` | Pending |

**Parallelization:** All three components (10, 11, 12) are independent of each other. Data Table and Logger Panel depend on Backend Core (2) — they are bottom panels that consume API data independently, not on Canvas. Image Viewer (12) depends on Execution (8) for result data. Up to three agents can work on these in parallel once their respective dependencies are met.

### Phase 5: Workflow Management & Settings

| # | Component | Description | Specific Plan | Plan Status |
|---|-----------|-------------|---------------|-------------|
| 13 | **Workflow CRUD** | /workflows endpoints, save/load, missing package resolution, auto-save to IndexedDB, startup recovery | `2026-04-01-workflow-crud.md` | Pending |
| 14 | **Settings Panel** | /settings endpoints, editor/Napari/execution/storage config | `2026-04-01-settings.md` | Pending |
| 15 | **Tool Hot-Reload** | File watcher (watchdog), tool_reload WS message, frontend schema update, parameter re-validation | `2026-04-01-hot-reload.md` | Pending |

**Parallelization:** All three components are independent. Workflow CRUD (13) depends on Backend Core (2). Settings Panel (14) depends on Backend Core (2) + Pinia Stores (3). Hot-Reload (15) depends on Backend Core (2) + WebSocket (9). Up to three agents can work in parallel.

### Phase 6: Polish

| # | Component | Description | Specific Plan | Plan Status |
|---|-----------|-------------|---------------|-------------|
| 16 | **Error Handling System** | 3-level errors (validation inline, execution in Node Panel, system in global indicator), error history panel | `2026-04-01-error-handling.md` | Pending |

**Parallelization:** Independent of other Phase 6 work. Depends on Execution (8) and Node Panel (6) being complete.

---

## Priority Order for Missing Plans

The following plans should be written next, in this order. Rationale is based on dependency criticality and risk.

1. **Graph Validation (7)** — Blocks Execution System, high complexity (cycle detection, type compatibility, parameter validation). Must be specified first.
2. **Execution System (8)** — Core feature of the platform. Depends on Graph Validation being defined.
3. **WebSocket Layer (9)** — Pervasive real-time feature that touches many components (logs, progress, hot-reload). Early specification prevents integration surprises.
4. **Node Panel (6)** — Needed immediately after Canvas. The parameter editing UX drives many backend contracts.
5. **Workflow CRUD (13)** — Gates save/load functionality. Without it, all work is ephemeral.
6. **Image Viewer (12)** — Napari integration via Wetlands requires careful design (IPC, process lifecycle).

---

## Cross-Cutting Concerns

These are not separate components but constraints applied across all plans:

- **Desktop-only MVP:** This plan covers the desktop-only MVP. Webapp mode (sessions, auth, dataset browser, code-server iframe, security middleware) is deferred to a future version.
- **Type generation:** Backend Pydantic models -> OpenAPI -> `openapi-typescript` -> frontend types. No hand-written duplicate types.
- **Testing strategy:**
  - Backend: pytest + httpx async test client. Unit tests for models/services, integration tests for endpoints.
  - Frontend: Vitest for component/store unit tests, Playwright for E2E flows.
  - Every feature is built TDD: failing test -> minimal implementation -> pass -> refactor -> commit.
- **State ownership:** Frontend owns graph state (Vue Flow). Backend owns validation/execution state. Never duplicate.
- **`create_app()` pattern:** The `create_app()` factory should accept an `AppConfig` object rather than individual parameters, since many components add service dependencies (execution engine, file watcher, WebSocket manager, etc.). A single config object keeps the factory signature stable as the platform grows.
- **Plan verbosity:** Plans should specify contracts (API shapes, store interfaces, message formats) and acceptance criteria (what tests must pass), not verbatim code. Agents are capable of writing correct implementation from specs + criteria. Keeping plans declarative makes them shorter, easier to review, and less likely to drift from the actual codebase.

---

## File Structure Overview

```
bioimageflow-platform/
├── frontend/
│   ├── package.json
│   ├── vite.config.ts
│   ├── vitest.config.ts
│   ├── playwright.config.ts
│   ├── tsconfig.json
│   ├── src/
│   │   ├── App.vue
│   │   ├── main.ts
│   │   ├── api/                    # API client (typed, generated from OpenAPI)
│   │   │   ├── client.ts           # Axios/fetch wrapper
│   │   │   └── types.ts            # Generated from OpenAPI (openapi-typescript)
│   │   ├── stores/                 # Pinia stores
│   │   │   ├── toolRegistry.ts     # Tool metadata cache
│   │   │   ├── execution.ts        # Execution state
│   │   │   ├── settings.ts         # App settings
│   │   │   └── ui.ts               # UI state (selected nodes, panel visibility)
│   │   ├── composables/            # Vue composables
│   │   │   ├── useGraphSync.ts     # Debounced PUT /graph, status reconciliation
│   │   │   ├── useWebSocket.ts     # WS connection, reconnection, message dispatch
│   │   │   ├── useUndoRedo.ts      # Client-side undo/redo stack
│   │   │   └── useAutoSave.ts      # IndexedDB auto-save
│   │   ├── components/
│   │   │   ├── canvas/             # Canvas (Vue Flow wrapper, custom nodes/edges)
│   │   │   │   ├── CanvasView.vue
│   │   │   │   ├── ToolNode.vue    # Custom node component
│   │   │   │   ├── InputPin.vue
│   │   │   │   ├── OutputPin.vue
│   │   │   │   └── EdgeRenderer.vue
│   │   │   ├── panels/
│   │   │   │   ├── ToolsPanel.vue
│   │   │   │   ├── NodePanel.vue
│   │   │   │   ├── DataTable.vue
│   │   │   │   ├── LoggerPanel.vue
│   │   │   │   └── SettingsPanel.vue
│   │   │   ├── execution/
│   │   │   │   └── ExecutionBanner.vue
│   │   │   ├── workflow/
│   │   │   │   ├── WorkflowMenu.vue
│   │   │   │   └── WorkflowDialog.vue
│   │   │   └── shared/             # Reusable UI atoms
│   │   │       ├── ParameterField.vue
│   │   │       └── StatusBadge.vue
│   │   └── utils/
│   │       ├── nodeIdGenerator.ts  # Name -> URL-safe ID
│   │       ├── typeColors.ts       # Edge/pin color by data type
│   │       └── clipboard.ts        # Copy/paste serialization
│   └── tests/
│       ├── unit/                   # Vitest unit tests (mirrors src/)
│       └── e2e/                    # Playwright E2E tests
├── backend/
│   ├── pyproject.toml
│   ├── src/
│   │   └── bioimageflow_server/
│   │       ├── __init__.py
│   │       ├── __main__.py         # uvicorn entrypoint
│   │       ├── app.py              # FastAPI app factory
│   │       ├── models/             # Pydantic models
│   │       │   ├── graph.py        # GraphState, NodeState, Edge, ValidationResult
│   │       │   ├── execution.py    # ExecutionResult, ProgressInfo
│   │       │   ├── tools.py        # ToolMetadata, PackageInfo
│   │       │   ├── workflow.py     # WorkflowCreate, WorkflowInfo
│   │       │   ├── settings.py     # Settings, OMEROInstance
│   │       │   └── validation.py   # GraphValidationError
│   │       ├── routers/            # FastAPI routers (one per domain)
│   │       │   ├── tools.py
│   │       │   ├── graph.py
│   │       │   ├── execution.py
│   │       │   ├── workflows.py
│   │       │   ├── nodes.py
│   │       │   ├── settings.py
│   │       │   ├── napari.py
│   │       │   ├── editor.py
│   │       │   ├── filesystem.py
│   │       │   └── health.py
│   │       ├── services/           # Business logic
│   │       │   ├── tool_registry.py
│   │       │   ├── graph_builder.py    # GraphState -> bioimageflow Workflow
│   │       │   ├── graph_validator.py
│   │       │   ├── execution.py
│   │       │   ├── workflow_store.py
│   │       │   ├── result_store.py
│   │       │   ├── thumbnail.py
│   │       │   ├── napari_launcher.py
│   │       │   └── package_installer.py
│   │       └── ws/
│   │           └── handler.py      # WebSocket handler
│   └── tests/
│       ├── conftest.py
│       ├── test_models/
│       ├── test_routers/
│       └── test_services/
└── superpowers/
    └── plans/
```

---

## Dependency Graph Between Components

```
Scaffolding (1)
    ├── Backend Core (2)
    │       ├── Graph Validation (7) ←── also needs Pinia Stores (3)
    │       │       └── Execution System (8)
    │       ├── WebSocket Layer (9) ←── can parallel with Execution (8) if interfaces locked
    │       ├── Workflow CRUD (13)
    │       ├── Data Table (10)
    │       ├── Logger Panel (11)
    │       └── Settings Panel (14) ←── also needs Pinia Stores (3)
    └── Pinia Stores (3)
            ├── Tools Panel (4)
            ├── Canvas (5) ←── also needs toolRegistryStore from Tools Panel (4) Task 11
            │       └── Node Panel (6)
            ├── Graph Validation (7) ←── also needs Backend Core (2)
            ├── Settings Panel (14) ←── also needs Backend Core (2)
            └── Error Handling (16)
```

Components sharing the same parent level can be developed in parallel. Each specific plan is self-contained and produces working, testable software independently. Where a component has two parents (e.g., Graph Validation needs both Backend Core and Pinia Stores), both must be complete before work begins.
