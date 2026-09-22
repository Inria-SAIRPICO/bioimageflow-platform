---
orphan: true
---

# Local Development

The project [README](https://github.com/Inria-SAIRPICO/bioimageflow-platform#readme) contains the shortest setup for desktop development with hot reload.
This page collects the alternative run modes and cross-repository workflows used by contributors.

## Install dependencies

The backend requires Python 3.12 or newer and uv.
The frontend requires Bun or Node.js 20 or newer.

```bash
cd frontend
bun install

cd ../backend
uv sync --group dev --extra desktop
```

## Run a production-style desktop build

Build the frontend after every frontend change that should appear in production mode:

```bash
cd frontend
bun run build

cd ../backend
uv sync --no-dev --extra desktop
uv run --no-dev --extra desktop bioimageflow-gui
```

The native window opens at <http://127.0.0.1:8000> and serves `frontend/dist/` with pywebview developer tools disabled.
Closing the window shuts down the server.

## Run the frontend in a browser

Use this mode when a native desktop window is not needed during frontend development.

Start the backend in one terminal:

```bash
cd backend
uv sync --group dev
uv run python -m bioimageflow_server --host 127.0.0.1 --port 8000 --dev
```

Start Vite in another terminal:

```bash
cd frontend
bun install
bun run dev
```

Open <http://localhost:5173>.
Vite proxies `/api` and `/ws` to `BIOIMAGEFLOW_BACKEND_PORT`, which defaults to `8000`.

To use a different backend port:

```bash
cd backend
uv run uvicorn bioimageflow_server.app:create_app --factory \
  --host 127.0.0.1 --port 8008
```

```bash
cd frontend
BIOIMAGEFLOW_BACKEND_PORT=8008 bun run dev
```

## Run the desktop application with hot reload

Start Vite and the desktop entry point in separate terminals:

```bash
cd frontend
bun run dev
```

```bash
cd backend
uv sync --group dev --extra desktop
uv run python -m bioimageflow_server --desktop --dev
```

The desktop window loads the Vite server and enables pywebview developer tools.
The repository's VS Code **Desktop** launch profile uses this mode and starts Vite through its background pre-launch task.

## Configure logging

The module entry point and desktop mode use the packaged `bioimageflow_server/logging.yaml` by default.
Pass another file when a deployment or debugging session needs different levels or handlers:

```bash
cd backend
uv run python -m bioimageflow_server --log-config /path/to/logging.yaml
uv run python -m bioimageflow_server --desktop --log-config /path/to/logging.yaml
```

Raw Uvicorn does not load the packaged application logging configuration automatically:

```bash
cd backend
uv run uvicorn bioimageflow_server.app:create_app --factory \
  --host 127.0.0.1 --port 8000 \
  --reload --reload-dir src \
  --log-config src/bioimageflow_server/logging.yaml
```

## Use local BioImageFlow source in workers

When validating unpublished changes to the sibling BioImageFlow library, first install its orchestrator and core into this checkout's backend environment:

```bash
cd backend
uv pip install --python .venv/bin/python --no-deps \
  --editable ../../bioimageflow/packages/bioimageflow-core \
  --editable ../../bioimageflow/packages/bioimageflow
cd ..
UV_NO_SYNC=1 scripts/test focus backend tests/test_integration/test_platform_fixture_contracts.py
UV_NO_SYNC=1 scripts/test focus e2e tests/e2e/canvas-interactions.spec.ts --grep 'new dynamic tools connect cleanly'
```

`UV_NO_SYNC=1` keeps nested `uv run` calls, including the Playwright backend server, from replacing those editable sources with the published lockfile versions.
Record both repository revisions with test evidence; this validates local source, not a published package release.
Restore the ordinary published environment with `cd backend && uv sync --group dev --frozen` when local-library validation is finished.

Wetlands tool environments install `bioimageflow-core` separately from the backend environment.
They use a pinned published version by default so user and runtime environments remain reproducible.

For cross-repository development, clone the BioImageFlow library alongside this repository and set `BIOIMAGEFLOW_USE_LOCAL_CORE=1` before starting the backend:

```bash
cd backend
BIOIMAGEFLOW_USE_LOCAL_CORE=1 \
  uv run python -m bioimageflow_server --desktop --dev
```

The VS Code launch profiles set this variable automatically.
On the next processing use, an existing BioImageFlow-owned Wetlands environment whose stored recipe no longer matches is replaced through Wetlands after its pool is closed. The platform also refreshes an already-existing stale `bioimageflow-general` environment in the background after startup. It does not rewrite external, adopted, Napari, thumbnail, or code-server environments.

## Use an editable tool package

Create a versioned tool-store directory and link the package source into it:

```bash
mkdir -p ~/.bioimageflow/tool_packages/bioimageflow_common_tools/0.1.6

ln -sfn \
  /path/to/bioimageflow-common-tools/bioimageflow_common_tools \
  ~/.bioimageflow/tool_packages/bioimageflow_common_tools/0.1.6/bioimageflow_common_tools
```

Restart the backend after creating or changing the link.

For normal use, install versioned packages through **Manage tools** rather than linking source directories.
