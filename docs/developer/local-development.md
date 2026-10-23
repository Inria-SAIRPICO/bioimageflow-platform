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

## Installed tools and editable sources

Installed tool packages are read-only selections while the backend process holds their admitted generations.
Editing a Python file in the tool store does not trigger automatic reload, and repeated workflow opens reuse the admitted package metadata and executable identity.
Use workflow-owned or custom editable tool sources for ordinary tool development; their current bytes are captured for compilation even if a watcher event was missed.
A malformed editable save stays available for repair and cannot make Run execute the previous code.

A controlled package refresh or uninstall retires the selected installed generation before admitting replacement code or removing files.
An active admitted operation blocks retirement and leaves files and registry state unchanged; finish that operation before retrying.
During physical uninstall, a concurrent workflow open reports the selected tool as unavailable rather than re-admitting code from the directory being removed.
Changing installed controller dependencies requires a backend restart.
The Tools Panel's package-index Refresh updates release availability, not installed executable code.
Tool-store installation uses `--no-deps`: declarations and DataFrame tools import compatible dependencies already supplied by the controller environment, while ProcessingTool recipes provision worker dependencies separately during execution preparation.

The generation lifecycle changes are being validated with unreleased BioImageFlow 0.9.5/Core 0.5.1 candidates in isolated environments.
The normal manifest and lock still select the published packages described below; candidate validation must not modify the ordinary backend environment.
The [workflow loading guide](workflow-loading.md) describes the benchmark and the remaining per-operation checks.

## Use local BioImageFlow source

The backend's `pyproject.toml` and `uv.lock` resolve published `bioimageflow[parsl,psij]==0.9.4`, Core 0.5 and Wetlands 2.6.1 from the registry.
A sibling library checkout is optional and is not required by ordinary development or CI.
Sync and validate the normal published environment with:

```bash
cd backend
uv sync --group dev --locked
cd ..
scripts/test focus backend tests/test_integration/test_platform_fixture_contracts.py
scripts/test focus e2e tests/e2e/canvas-interactions.spec.ts --grep 'new dynamic tools connect cleanly'
```

For an explicit source investigation, use a separate owned interpreter or worktree and install the selected sibling orchestrator/Core projects there.
Record both repository revisions and distinguish that source evidence from the published package environment.
Do not add editable source paths to the normal lock or reuse a source-modified interpreter for published compatibility certification.

Wetlands tool environments install `bioimageflow-core` separately from the backend environment.
They use the selected published version by default so controller and runtime environments describe the same supported Core release.
The normal **Desktop**, **Backend**, and **Backend-worktree** VS Code launch profiles explicitly clear local-core worker settings and use the locked published orchestrator and Core.

For regular `bioimageflow-core` development, clone the BioImageFlow library alongside this repository and choose **Desktop (local core)** or **Backend (local core)** in VS Code.
These profiles add the sibling core package to the platform process's `PYTHONPATH`, pass its project directory to BioImageFlow through `BIOIMAGEFLOW_CORE_SOURCE`, and set `BIOIMAGEFLOW_WETLANDS` to the ignored `.bioimageflow/wetlands-local-core` directory.
The platform process and Wetlands workers therefore use the same source checkout without modifying `backend/.venv`, and switching back to a normal profile does not rebuild the normal Wetlands environments.

The equivalent command is:

```bash
cd backend
PYTHONPATH=../../bioimageflow/packages/bioimageflow-core \
BIOIMAGEFLOW_CORE_SOURCE=../../bioimageflow/packages/bioimageflow-core \
BIOIMAGEFLOW_WETLANDS=../.bioimageflow/wetlands-local-core \
  uv run python -m bioimageflow_server --desktop --dev
```

BioImageFlow validates that the configured directory exists, declares the `bioimageflow-core` project and a valid version in `pyproject.toml`, and contains the `bioimageflow_core` package.
An invalid explicit source fails clearly and never falls back to the published wheel.
On the next processing use, an existing BioImageFlow-owned Wetlands environment whose stored recipe no longer matches is replaced through Wetlands after its pool is closed. The platform also refreshes an already-existing stale `bioimageflow-general` environment in the background after startup. It does not rewrite external, adopted, Napari, thumbnail, or code-server environments.

## Develop a tool package

Use the package repository's isolated editable environment and native tests while changing package code.
For platform integration, install a complete versioned artifact through the package installer and use the controlled uninstall/install or restart boundary when replacing that selection.
A bare source-directory link in the tool store is not a complete installation: it lacks the providing distribution metadata and RECORD required at admission.
Use custom or workflow-owned tool sources when edits must appear immediately in an open platform workflow.
