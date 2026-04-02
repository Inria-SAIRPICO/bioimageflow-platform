# Project Scaffolding — TDD Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers-extended-cc:subagent-driven-development (recommended) or superpowers-extended-cc:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Set up the monorepo structure with a Vue 3 frontend and FastAPI backend, including build configs, dev servers, linting, testing infrastructure, and OpenAPI-to-TypeScript type generation.

**Architecture:** Two top-level directories (`frontend/`, `backend/`) at the project root alongside the existing `bioimageflow/` library. The backend is a Python package managed by uv. The frontend is a Vite-based Vue 3 + TypeScript SPA managed by bun. A type generation script produces TypeScript interfaces from the backend's OpenAPI schema, ensuring a single source of truth for API types.

**Tech Stack:**
- **Frontend:** Vue 3, TypeScript, Vite, Vitest, Playwright, PrimeVue, Vue Flow, Dockview, Pinia, bun
- **Backend:** Python 3.12, FastAPI, uvicorn, Pydantic v2, pytest, anyio, httpx, uv
- **Type generation:** openapi-typescript

**User Verification:** NO

---

## File Structure

```
bioimageflow-platform/
├── frontend/
│   ├── package.json
│   ├── tsconfig.json
│   ├── tsconfig.app.json
│   ├── tsconfig.node.json
│   ├── vite.config.ts
│   ├── vitest.config.ts
│   ├── playwright.config.ts
│   ├── env.d.ts
│   ├── index.html
│   ├── .eslintrc.cjs
│   ├── src/
│   │   ├── main.ts
│   │   ├── App.vue
│   │   ├── api/
│   │   │   ├── client.ts
│   │   │   └── types.ts          # Generated — do not edit
│   │   ├── stores/
│   │   ├── components/
│   │   ├── composables/
│   │   └── utils/
│   ├── tests/
│   │   ├── unit/
│   │   └── e2e/
│   └── scripts/
│       └── generate-types.sh
├── backend/
│   ├── pyproject.toml
│   ├── src/
│   │   └── bioimageflow_server/
│   │       ├── __init__.py
│   │       ├── __main__.py
│   │       ├── app.py
│   │       ├── models/
│   │       │   └── __init__.py
│   │       ├── routers/
│   │       │   └── __init__.py
│   │       ├── services/
│   │       │   └── __init__.py
│   │       └── ws/
│   │           └── __init__.py
│   └── tests/
│       ├── conftest.py
│       ├── test_models/
│       ├── test_routers/
│       └── test_services/
├── bioimageflow/               # Existing library — do not touch
├── specs.md
└── gui_specs_v1.md
```

---

### Task 1: Backend Python Package Setup

**Files to create:** `backend/pyproject.toml`, `backend/src/bioimageflow_server/__init__.py`, `backend/src/bioimageflow_server/__main__.py`, plus empty `__init__.py` in `models/`, `routers/`, `services/`, `ws/` sub-packages.

- [ ] **Step 1: Create pyproject.toml**

Standard `[project]` section with `name = "bioimageflow-server"`, `version = "0.1.0"`, `requires-python = ">=3.12"`.

Dependencies:
- `fastapi>=0.115`
- `uvicorn[standard]>=0.34`
- `pydantic>=2.0`
- `websockets>=15.0` (spec requires `/ws` endpoint)
- `python-multipart>=0.0.20` (spec requires file upload for dataset/workflow import)
- `watchdog>=6.0` (spec requires file watching for hot-reload)

Dev dependencies (`[project.optional-dependencies] dev`): `pytest>=8.0`, `anyio[trio]>=4.0`, `httpx>=0.27`, `ruff>=0.9`.

Note: rate limiting library is not needed yet — add when webapp mode is implemented.

Build system: `hatchling`. The correct hatch config for src layout is `packages = ["src/bioimageflow_server"]` under `[tool.hatch.build.targets.wheel]`.

Pytest config: `testpaths = ["tests"]`, `asyncio_mode = "auto"`.
Ruff config: `line-length = 100`, `target-version = "py312"`.

- [ ] **Step 2: Create `__init__.py`** with module docstring.

- [ ] **Step 3: Create `__main__.py`**

Entrypoint for `python -m bioimageflow_server`. Defines `main()` that calls `uvicorn.run()` with factory mode pointing to `bioimageflow_server.app:create_app`, host `127.0.0.1`, port `8000`, reload enabled.

- [ ] **Step 4: Create empty `__init__.py` in sub-packages** (`models`, `routers`, `services`, `ws`).

- [ ] **Step 5: Install and verify**

Run `cd backend && uv sync --all-extras`, then verify `uv run python -c "import bioimageflow_server; print('OK')"` prints `OK`.

- [ ] **Step 6: Commit** — `feat(backend): scaffold Python package structure`

---

### Task 2: Backend — Minimal FastAPI App with Health Endpoint

**Files to create:** `backend/src/bioimageflow_server/app.py`, `backend/src/bioimageflow_server/routers/health.py`, `backend/tests/conftest.py`, `backend/tests/test_routers/test_health.py`, plus `__init__.py` in `tests/`, `test_routers/`, `test_models/`, `test_services/`.

- [ ] **Step 1: Write failing test for health endpoint**

Test: `GET /api/v1/health` returns 200 with `{"status": "ok", "version": "..."}`. Use `httpx.AsyncClient` with `ASGITransport` against `create_app()`.

- [ ] **Step 2: Create conftest.py**

Provide `anyio_backend` fixture returning `"asyncio"`.

- [ ] **Step 3: Run test — should fail** with `ModuleNotFoundError` for `app`.

- [ ] **Step 4: Implement app.py and health router**

`routers/health.py`: Single `GET /health` endpoint returning status and version.

`app.py`: `create_app(settings=None)` factory. **Architectural note:** `create_app()` should accept a config/settings object (e.g. a Pydantic `Settings` class) rather than growing individual parameters. Many future plans will add dependencies (database, cache, auth), and a single settings object keeps the signature stable. For now, accept an optional settings parameter with sensible defaults.

The factory should:
- Create `FastAPI` instance with title and version
- Configure CORS middleware (desktop mode allows `localhost:5173`)
- Include the health router under `/api/v1` prefix
- Return the app

- [ ] **Step 5: Run test — should pass.**

- [ ] **Step 6: Commit** — `feat(backend): add FastAPI app factory with health endpoint`

---

### Task 3: Backend — Error Response Format

**Files to create:** `backend/src/bioimageflow_server/models/errors.py`, `backend/tests/test_models/test_errors.py`, `backend/tests/test_routers/test_error_handler.py`. Modify `app.py`.

- [ ] **Step 1: Write failing tests**

Test `ErrorResponse` model: verify fields `error`, `detail`, `field` (optional). Two cases: with and without `field`.

Test HTTP exception handler: register a test route that raises `HTTPException(404)`, verify response is `{"error": "not_found", "detail": "..."}`.

Test validation error handler: `POST` with invalid body, verify 422 response uses `{"error": "validation_error", "detail": "..."}` format instead of FastAPI's default.

- [ ] **Step 2: Run tests — should fail.**

- [ ] **Step 3: Implement**

`models/errors.py`: Pydantic `ErrorResponse` model with `error: str`, `detail: str`, `field: str | None = None`.

In `app.py`: add exception handlers for `HTTPException` and `RequestValidationError`. Map HTTP status codes to error strings (400 -> `bad_request`, 404 -> `not_found`, 422 -> `validation_error`, etc.). Matches spec error format.

- [ ] **Step 4: Run tests — should pass.**

- [ ] **Step 5: Commit** — `feat(backend): add consistent error response format with exception handlers`

---

### Task 4: Frontend — Vite + Vue 3 + TypeScript Scaffold

**Files to create:** `frontend/package.json`, `frontend/vite.config.ts`, `frontend/tsconfig.json`, `frontend/tsconfig.app.json`, `frontend/tsconfig.node.json`, `frontend/env.d.ts`, `frontend/index.html`, `frontend/src/main.ts`, `frontend/src/App.vue`.

- [ ] **Step 1: Create package.json**

Standard Vite+Vue project. Scripts: `dev`, `build`, `preview`, `test:unit`, `test:unit:watch`, `test:e2e`, `lint`, `generate-types`, `type-check`.

Dependencies: `vue ^3.5`, `vue-router ^4.5`, `pinia ^3.0`, `@vue-flow/core ^1.41`, `@vue-flow/minimap ^1.5`, `@vue-flow/controls ^1.1`, `primevue ^4.3`, `primeicons ^7.0`, `dockview-vue ^4.3`, `axios 1.14.0`.

Dev dependencies: `@vitejs/plugin-vue`, `vite`, `vitest`, `@vue/test-utils`, `vue-tsc`, `typescript`, `jsdom`, `playwright`, `@playwright/test`, `openapi-typescript`, `eslint`, `@vue/eslint-config-typescript`.

- [ ] **Step 2: Create vite.config.ts**

Vue plugin, `@` alias to `./src`, dev server on port 5173, proxy `/api` to `http://127.0.0.1:8000` and `/ws` to `ws://127.0.0.1:8000`.

- [ ] **Step 3: Create tsconfig files**

Solution-style `tsconfig.json` referencing `tsconfig.app.json` and `tsconfig.node.json`. App config: ESNext target/module, bundler resolution, strict, `@/*` path alias, `vitest/globals` types. Node config: covers `vite.config.ts`, `vitest.config.ts`, `playwright.config.ts`.

- [ ] **Step 4: Create env.d.ts** — Vite client type reference.

- [ ] **Step 5: Create index.html** — Standard SPA shell with `<div id="app">` and module script pointing to `/src/main.ts`.

- [ ] **Step 6: Create main.ts and App.vue**

`main.ts`: Create Vue app, install Pinia and PrimeVue, mount to `#app`.

`App.vue`: Minimal template with `<div id="bioimageflow-app">` containing "BioImageFlow" text. Full-viewport CSS reset on `html, body, #app, #bioimageflow-app`.

- [ ] **Step 7: Install and verify** — `bun install` then `bun run build` succeeds.

- [ ] **Step 8: Commit** — `feat(frontend): scaffold Vite + Vue 3 + TypeScript project`

---

### Task 5: Frontend — Vitest Configuration

**Files to create:** `frontend/vitest.config.ts`, `frontend/tests/unit/smoke.test.ts`.

- [ ] **Step 1: Create vitest.config.ts**

Vue plugin, `@` alias, jsdom environment, globals enabled, test includes `tests/unit/**/*.test.ts` and `src/**/__tests__/*.test.ts`.

- [ ] **Step 2: Write smoke test** — Verify vitest runs. A single trivial assertion is fine.

- [ ] **Step 3: Run** — `bun run test:unit` passes.

- [ ] **Step 4: Commit** — `feat(frontend): add Vitest configuration with smoke test`

---

### Task 6: Frontend — Playwright Configuration

**Files to create:** `frontend/playwright.config.ts`, `frontend/tests/e2e/smoke.spec.ts`.

- [ ] **Step 1: Create Playwright config**

Test dir `./tests/e2e`, fully parallel, base URL `http://127.0.0.1:5173`, trace on first retry, web server command `bun run dev`.

- [ ] **Step 2: Write E2E smoke test**

Test: navigate to `/`, verify `#bioimageflow-app` is visible and page contains "BioImageFlow" text.

- [ ] **Step 3: Install Playwright browsers** — `bunx playwright install --with-deps chromium`.

- [ ] **Step 4: Commit** — `feat(frontend): add Playwright E2E configuration with smoke test`

---

### Task 7: Frontend — API Client

**Files to create:** `frontend/src/api/client.ts`, `frontend/tests/unit/api/client.test.ts`.

- [ ] **Step 1: Write failing test**

Test: the `api` export is an axios instance created via `axios.create()`, with standard HTTP methods available. Mock axios to verify `create` was called.

- [ ] **Step 2: Run test — should fail** with module not found.

- [ ] **Step 3: Implement**

`client.ts`: export `api` as an `axios.create()` instance with `Content-Type: application/json`. No explicit `baseURL` — Vite proxy handles `/api` in dev, same-origin works in production.

- [ ] **Step 4: Run test — should pass.**

- [ ] **Step 5: Commit** — `feat(frontend): add axios API client`

---

### Task 8: OpenAPI Type Generation Script

**Files to create:** `frontend/scripts/generate-types.sh`, `frontend/src/api/types.ts` (placeholder).

- [ ] **Step 1: Create generate-types.sh**

Bash script that fetches `http://127.0.0.1:8000/openapi.json`, pipes it through `bunx openapi-typescript` to generate `src/api/types.ts`. Prints helpful error if backend is unreachable. Make executable.

- [ ] **Step 2: Create placeholder types.ts**

Hand-written placeholder interfaces matching the spec until first generation. Include: `ToolMetadata`, `InputFieldSchema`, `OutputFieldSchema`, `PackageInfo`, `NodeState`, `Edge` (union of `ColumnRefEdge` | `PositionalEdge`), `GraphState`, `NodeStatus`, `GraphValidationError`, `ValidationResult`, `ErrorResponse`. These will be overwritten by the generation script once the backend has real endpoints.

- [ ] **Step 3: Verify** — `bun run type-check` has no errors related to `types.ts`.

- [ ] **Step 4: Commit** — `feat(frontend): add OpenAPI type generation script and placeholder types`

---

### Task 9: Backend — Verify Full Test Suite Runs

No new files. Verification only.

- [ ] **Step 1: Run all backend tests** — `cd backend && uv run pytest -v` — all pass.

- [ ] **Step 2: Run ruff linter** — `cd backend && uv run ruff check src/ tests/` — no errors.

- [ ] **Step 3: Run ruff formatter** — `cd backend && uv run ruff format --check src/ tests/` — all formatted. Fix and commit if needed.

- [ ] **Step 4: Commit formatting fixes if any** — `style(backend): apply ruff formatting`

---

### Task 10: Frontend — Verify Full Test Suite & Dev Server

No new files. Verification only.

- [ ] **Step 1: Run all frontend unit tests** — `bun run test:unit` — all pass.

- [ ] **Step 2: Run type-check** — `bun run type-check` — no errors.

- [ ] **Step 3: Verify dev server starts and serves HTML**

Start the Vite dev server in background, curl `http://127.0.0.1:5173/`, verify the response contains `<div id="app">`, then kill the server.

- [ ] **Step 4: Commit fixes if any** — `fix(frontend): resolve any startup issues`

---

### Task 11: Integration Test — Full Stack Smoke

**Files:** Create `frontend/tests/e2e/full-stack-smoke.spec.ts`

**Prerequisites:** Both backend and frontend must be running.

**What to test (Playwright):**
- Start backend (`uv run python -m bioimageflow_server`) and frontend (`bun run dev`) via Playwright's `webServer` config
- Navigate to `/`, verify `#bioimageflow-app` is visible with "BioImageFlow" text
- Fetch `/api/v1/health` via the Vite proxy (relative URL), verify response has `status: "ok"`
- Verify no console errors in the browser

**Verify:** `cd frontend && bun run test:e2e -- --grep "full stack"` passes

- [ ] Write Playwright test
- [ ] Configure Playwright webServer to start both backend and frontend (use a script or `concurrently`)
- [ ] Run test — should pass
- [ ] Commit — `test: add full-stack smoke E2E test`
