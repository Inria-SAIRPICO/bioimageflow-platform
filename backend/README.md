# BioImageFlow Server

FastAPI backend for the BioImageFlow platform. It persists one canonical recursive workflow graph model, translates accepted snapshots to the BioImageFlow library for validation and execution, and exposes REST and WebSocket APIs for editing, provenance updates, trusted Python materialization, execution, and real-time progress. It also ships a **pywebview desktop entrypoint** that opens the Vue SPA in a native OS window.

## Tech Stack

- **FastAPI** with async support
- **Pydantic** v2 for request/response models
- **WebSockets** for real-time execution updates
- **pywebview** for the native desktop window (optional extra)
- **uv** for dependency management
- **Python** >= 3.12

## Project Structure

```
src/bioimageflow_server/
  app.py              Application factory (also mounts frontend/dist/ in desktop mode)
  __main__.py         CLI entry: `python -m bioimageflow_server [--desktop] [--dev]`
  desktop.py          pywebview entrypoint + DesktopApi JS bridge + shutdown lifecycle
  routers/
    health.py         GET /api/v1/health
    tools.py          Tool registry and package management endpoints
    dev.py            Development-only endpoints
    filesystem.py     POST /api/v1/fs/reveal (file-browser reveal)
    graph.py          Graph validation endpoints
    workflows.py      Workflow CRUD and workspace tree endpoints
  services/
    tool_registry.py  Tool discovery and registry
    package_installer.py  Tool package installation
    workflow_store.py Workspace workflow persistence
    workspace.py      Workspace path resolution and workspace roots
  models/             Pydantic models (errors, graph, tools, settings, ...)
  ws/                 WebSocket handlers
```

## Setup

```bash
uv sync                          # Core dependencies
uv sync --extra dev              # + pytest, ruff, httpx
uv sync --extra desktop          # + pywebview (required for --desktop / bioimageflow-gui)
uv sync --extra dev --extra desktop   # Both
```

## Running

### Headless / browser mode

Best for backend development or when running the frontend separately via Vite.

```bash
# Dev server with auto-reload
uv run python -m bioimageflow_server --host 127.0.0.1 --port 8000 --dev

# Raw Uvicorn is also supported; pass the packaged logging config explicitly
uv run uvicorn bioimageflow_server.app:create_app --factory --host 127.0.0.1 --port 8000 --reload --reload-dir src --log-config src/bioimageflow_server/logging.yaml
```

OpenAPI docs: <http://localhost:8000/docs>.

### Local BioImageFlow core in Wetlands workers

Wetlands creates separate Python environments for tools, so a backend running from the editable checkout can still dispatch workers that import the published `bioimageflow-core` wheel.
For source development across `bioimageflow-core` and tool packages, launch the backend with:

```bash
BIOIMAGEFLOW_USE_LOCAL_CORE=1 uv run python -m bioimageflow_server --host 127.0.0.1 --port 8000 --dev
```

The VS Code launch profiles already set `BIOIMAGEFLOW_USE_LOCAL_CORE=1`.
Normal CLI and desktop commands omit it by default so released/runtime sessions keep pinned, reproducible worker dependencies.
After changing this flag, recreate any already-created Wetlands workspaces that still pin the wheel under `~/.bioimageflow/wetlands/pixi/workspaces/`.

### Logging

The `python -m bioimageflow_server` entrypoint and desktop mode use the packaged `bioimageflow_server/logging.yaml` config by default.
That config shows INFO logs for `bioimageflow_server`, `bioimageflow`, and `wetlands`, keeps third-party root logs at WARNING, and preserves Uvicorn access logs.

Override it for deployments or local debugging with:

```bash
uv run python -m bioimageflow_server --log-config /path/to/logging.yaml
uv run python -m bioimageflow_server --desktop --log-config /path/to/logging.yaml
```

If you launch raw Uvicorn directly, pass `--log-config src/bioimageflow_server/logging.yaml` or your own config path; raw Uvicorn does not automatically use the packaged config.

### Desktop mode

Opens a native pywebview window around the SPA. Requires `uv sync --extra desktop`.

**Production** (uses the pre-built frontend in `../frontend/dist/`):

```bash
# Build the frontend first
cd ../frontend && bun install && bun run build && cd -

# Then launch the native app -- the console script is the simplest entry point
uv run bioimageflow-gui

# Or via the module entrypoint, which accepts --host / --port overrides
uv run python -m bioimageflow_server --desktop --port 8765
```

`bioimageflow-gui` binds `127.0.0.1:8000` by default. If that port is in use, the backend will fail to start and `start_desktop` raises a clear `RuntimeError`; switch to `python -m bioimageflow_server --desktop --port <other>`.

**Development** (Vite HMR inside the window):

```bash
# terminal 1
cd ../frontend && bun run dev

# terminal 2
uv run python -m bioimageflow_server --desktop --dev
```

With `--dev` the pywebview window points at `http://localhost:5173` (the Vite dev server) while FastAPI still runs on `127.0.0.1:8000` so `/api` calls work through Vite's proxy.

## Workspace Storage

The backend resolves platform-owned workflow files through one active workspace per user. Desktop mode defaults to `~/BioImageFlow/workspace/` unless overridden in Settings. A proposed webapp deployment provides a workspaces root and derives `<workspaces_root>/<user_id>/workspace/`.

```text
workspace/
  workflows/                          folders and workflow directories
    <workflow-id>/tools/              custom tools owned by one workflow
```

Workflow IDs are slash-separated paths relative to `workspace/workflows/`. Runtime execution paths passed to the BioImageFlow library are resolved below the configured output-data folder, by default `~/bioimageflow_data/workflows/<workflow-id>/`. Dataset uploads use the configured dataset root or `<BIOIMAGEFLOW_HOME>/datasets/`. `WorkspaceInfo` also reports reserved `tools_root` and `outputs_root` values, but those paths are not the current custom-tool or execution-output authorities.

### How it fits together

`desktop.py` starts uvicorn in a background daemon thread, waits for `server.started`, then opens a pywebview window. When the window closes, a shutdown sequence stops the execution (placeholder), cleans up shared memory (placeholder), saves settings (placeholder), and signals uvicorn to exit.

The pywebview JS bridge (`DesktopApi`) exposes native file/folder pickers, a save dialog, a `reveal_path` call, and a `set_title` call to the frontend as `window.pywebview.api.*`. See `frontend/src/utils/nativeDialogs.ts` for the typed wrappers.

## Testing

```bash
../scripts/test focus backend tests/test_desktop.py
../scripts/test focus backend tests/test_routers
../scripts/test quick
../scripts/test check
```

Desktop tests mock `webview`, `uvicorn`, and `threading.Thread`, so they run headlessly without opening any window.

External common-tools certification is intentionally separate and available through `../scripts/test certification`.
See [`../docs/testing.md`](../docs/testing.md) for focused selectors and the exact quick, check, full, browser, and external-certification lane contents.

## API Overview

All endpoints are prefixed with `/api/v1/`. This is a short orientation list; use the generated OpenAPI document for the complete current surface.

| Method   | Endpoint                            | Description                                 |
|----------|-------------------------------------|---------------------------------------------|
| `GET`    | `/health`                           | Health check                                |
| `GET`    | `/tools`                            | List all discovered tools                   |
| `GET`    | `/tools/{name}/source`              | Get tool source directory                   |
| `GET`    | `/tools/packages`                   | List all packages with versions             |
| `POST`   | `/tools/packages/{name}/install`    | Install a package version                   |
| `DELETE` | `/tools/packages/{name}`            | Uninstall a package version                 |
| `GET`    | `/workspace`                        | Current workspace roots and flags           |
| `PATCH`  | `/workspace`                        | Desktop workspace path change               |
| `GET`    | `/workflows/tree`                   | Nested workflow folder tree                 |
| `POST`   | `/workflows/{id}/source-update/preview` | Preview an explicit embedded-source refresh |
| `POST`   | `/workflows/{id}/python-source/preview` | Preview trusted `build_workflow` materialization |
| `POST`   | `/workflows/{id}/source-operations/apply` | Apply an immutable confirmed source operation |
| `POST`   | `/fs/reveal`                        | Open a path in the system file browser      |

## Linting

```bash
uv run ruff check .              # Lint
uv run ruff format .             # Format
```

## Packaging

```bash
uv build                         # Build wheel/sdist into dist/
uv pip install dist/bioimageflow_server-*.whl    # Install the built wheel
bioimageflow-gui                 # Launch the desktop app from the installed entry point
```

The `bioimageflow-gui` console script is declared in `pyproject.toml` and resolves to `bioimageflow_server.desktop:main_desktop`.
