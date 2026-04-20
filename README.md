# BioImageFlow Platform

A desktop application for building, executing, and inspecting bioimage analysis workflows visually. It wraps the [BioImageFlow](https://github.com/your-org/bioimageflow) library with a node-based editor, parameter panels, data viewers, and execution controls.

## Architecture

```
bioimageflow-platform/
  backend/          Python FastAPI server wrapping the BioImageFlow library
  frontend/         Vue 3 SPA with node-based workflow editor
  bioimageflow/     Symlink to the BioImageFlow library
  docs/             Specs and implementation plans
```

The platform follows a **client-server model**:

- The **backend** is a Python server (FastAPI) that exposes a REST + WebSocket API. It handles tool discovery, graph validation, workflow execution, and real-time progress streaming.
- The **frontend** is a Vue SPA that owns the graph state (nodes, edges, positions, parameters) and communicates with the backend exclusively through the API.
- In production, the application is packaged with pywebview for native desktop integration.

The frontend owns all graph state. The backend is stateless between requests for graph editing -- each request sends the full graph as JSON. The backend holds only transient execution state during workflow runs.

## Prerequisites

- **Python** >= 3.12
- **Node.js** >= 20 (or [Bun](https://bun.sh/))
- **uv** (Python package manager)
- The [BioImageFlow library](https://github.com/your-org/bioimageflow) cloned alongside this repo (symlinked as `bioimageflow/`)

## Quick Start

**1. Start the backend:**

```bash
cd backend
uv sync
uv run uvicorn bioimageflow_server.app:create_app --factory --host 127.0.0.1 --port 8000
```

**2. Start the frontend:**

```bash
cd frontend
bun install
bun run dev
```

The app is available at http://localhost:5173. The Vite dev server proxies `/api` and `/ws` requests to the backend at port 8000.

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
- `docs/superpowers/plans/` -- Implementation plans
