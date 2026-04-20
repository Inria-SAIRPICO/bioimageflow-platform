# BioImageFlow Server

FastAPI backend for the BioImageFlow platform. Wraps the BioImageFlow library and exposes a REST + WebSocket API for tool discovery, graph validation, workflow execution, and real-time progress streaming. Also ships a **pywebview desktop entrypoint** that opens the Vue SPA in a native OS window.

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
  services/
    tool_registry.py  Tool discovery and registry
    package_installer.py  Tool package installation
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
uv run uvicorn bioimageflow_server.app:create_app --factory --host 127.0.0.1 --port 8000 --reload

# Or via the module entrypoint (add --dev for --reload)
uv run python -m bioimageflow_server --host 127.0.0.1 --port 8000 --dev
```

OpenAPI docs: <http://localhost:8000/docs>.

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

### How it fits together

`desktop.py` starts uvicorn in a background daemon thread, waits for `server.started`, then opens a pywebview window. When the window closes, a shutdown sequence stops the execution (placeholder), cleans up shared memory (placeholder), saves settings (placeholder), and signals uvicorn to exit.

The pywebview JS bridge (`DesktopApi`) exposes native file/folder pickers, a save dialog, a `reveal_path` call, and a `set_title` call to the frontend as `window.pywebview.api.*`. See `frontend/src/utils/nativeDialogs.ts` for the typed wrappers.

## Testing

```bash
uv run pytest                             # All tests
uv run pytest tests/test_desktop.py       # Desktop + DesktopApi + shutdown
uv run pytest tests/test_routers          # Router tests only
```

Desktop tests mock `webview`, `uvicorn`, and `threading.Thread`, so they run headlessly without opening any window.

## API Overview

All endpoints are prefixed with `/api/v1/`.

| Method   | Endpoint                            | Description                                 |
|----------|-------------------------------------|---------------------------------------------|
| `GET`    | `/health`                           | Health check                                |
| `GET`    | `/tools`                            | List all discovered tools                   |
| `GET`    | `/tools/{name}/source`              | Get tool source directory                   |
| `GET`    | `/tools/packages`                   | List all packages with versions             |
| `POST`   | `/tools/packages/{name}/install`    | Install a package version                   |
| `DELETE` | `/tools/packages/{name}`            | Uninstall a package version                 |
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
