# BioImageFlow Platform

A desktop application for building, executing, and inspecting bioimage analysis workflows visually. It wraps the [BioImageFlow](https://github.com/your-org/bioimageflow) library with a node-based editor, parameter panels, data viewers, and execution controls.

## Architecture

```
bioimageflow-platform/
  backend/          Python FastAPI server + pywebview desktop entrypoint
  frontend/         Vue 3 SPA with node-based workflow editor
  bioimageflow/     Symlink to the BioImageFlow library
  docs/             Specs and implementation plans
```

The platform follows a **client-server model**:

- The **backend** is a Python server (FastAPI) that exposes a REST + WebSocket API. It handles tool discovery, graph validation, workflow execution, and real-time progress streaming.
- The **frontend** is a Vue SPA that owns the graph state (nodes, edges, positions, parameters) and communicates with the backend exclusively through the API.
- The backend also ships a **pywebview entrypoint** that opens the SPA in a native OS window, exposes native file dialogs to the frontend, and manages the full application lifecycle.

The frontend owns all graph state. The backend is stateless between requests for graph editing -- each request sends the full graph as JSON. The backend holds only transient execution state during workflow runs.

## Prerequisites

- **Python** >= 3.12
- **Node.js** >= 20 (or [Bun](https://bun.sh/))
- **uv** (Python package manager)
- The [BioImageFlow library](https://github.com/your-org/bioimageflow) cloned alongside this repo (symlinked as `bioimageflow/`)

## Quick Start — Desktop (production)

Run the app as a native desktop window with a single command. See [`backend/README.md`](backend/README.md#desktop-mode) for details.

**1. Build the frontend** (once, or after any frontend change):

```bash
cd frontend
bun install
bun run build
```

**2. Install the backend** with the `desktop` extra and launch:

```bash
cd backend
uv sync --extra desktop
uv run bioimageflow-gui
```

A native window opens at `http://127.0.0.1:8000` showing the SPA served from `frontend/dist/`. Closing the window shuts the server down cleanly.

## Quick Start — Browser (development)

Keep the frontend's hot-module-replacement while iterating on UI code.

**1. Backend** (first terminal):

```bash
cd backend
uv sync --extra dev
uv run uvicorn bioimageflow_server.app:create_app --factory --host 127.0.0.1 --port 8000 --reload
```

**2. Frontend** (second terminal):

```bash
cd frontend
bun install
bun run dev
```

Open <http://localhost:5173>. Vite proxies `/api` and `/ws` to the backend on port 8000.

## Quick Start — Desktop + HMR (development)

Get hot reload inside the native window.

```bash
# terminal 1 -- frontend dev server
cd frontend && bun run dev

# terminal 2 -- desktop window pointing at Vite
cd backend
uv sync --extra desktop --extra dev
uv run python -m bioimageflow_server --desktop --dev
```

The pywebview window loads `http://localhost:5173` while the FastAPI backend runs on port 8000; API calls reach the backend through Vite's proxy.

## Testing

```bash
# Backend
cd backend && uv run pytest

# Frontend unit tests
cd frontend && bun run test:unit

# Frontend E2E tests (requires both backend and frontend running)
cd frontend && bun run test:e2e
```

## Documentation

- `specs.md` -- BioImageFlow library specifications
- `platform_specs_v1.md` -- MVP platform specifications
- `docs/superpowers/specs/` -- Design specs for individual components
- `docs/superpowers/plans/` -- Implementation plans (including `2026-04-10-pywebview-desktop.md`)
