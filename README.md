# BioImageFlow Platform

A desktop application for building, executing, and inspecting bioimage analysis workflows visually. It wraps the [BioImageFlow](https://gitlab.inria.fr/sairpico/bioimageflow) library with a node-based editor, parameter panels, data viewers, and execution controls.

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
- The **frontend** is a Vue SPA whose mounted canvases own immediate graph interaction state (nodes, edges, positions, parameters) and communicate with the backend exclusively through the API.
- The backend also ships a **pywebview entrypoint** that opens the SPA in a native OS window, exposes native file dialogs to the frontend, and manages the full application lifecycle.

Each root canvas persists its editable graph through a revisioned backend workflow draft, which is the durable authority shared with Save, Run, and agents. Nested canvases persist private revisioned snapshots until explicit parent apply. `workflow.json` is the explicitly saved artifact, and `PUT /graph` remains only stateless compatibility or transient validation. The backend also holds transient execution state during workflow runs.

## Workspace Model

Each user has one active BioImageFlow workspace. Desktop mode defaults to `~/BioImageFlow/workspace/` and can select another path in Settings; proposed webapp deployments derive it from an admin-managed workspaces root as `<workspaces_root>/<user_id>/workspace/`.

```text
workspace/
  workflows/                          Saved workflow tree and folders
    <workflow-id>/tools/              Custom tools owned by one workflow
```

Execution outputs use the configured output-data folder, which defaults to `~/bioimageflow_data/`, and are scoped by workflow ID. Dataset uploads use the configured dataset root or `<BIOIMAGEFLOW_HOME>/datasets/`; neither is owned by `workspace/data` or `workspace/outputs` in the current implementation.

Workflow ids are paths relative to `workspace/workflows/`, such as
`segmentation/nuclei` or `My Project/quality_control`. Folder path segments can
contain spaces. Each workflow is stored as
`workspace/workflows/<id>/workflow.json`. The Workflows panel shows a PrimeVue
folder tree where users can create, rename, delete, and drag folders or
workflows. Items are sorted alphabetically inside each folder, and a workflow row
can be dragged either to another folder or to the canvas, except when that would
make a workflow contain itself directly or indirectly. Deleting a non-empty
folder asks whether to delete children, move them up, or cancel. Creating a
workflow while a folder is selected places it in that folder and the creation
dialog includes an optional description field. The workflow detail panel shows
the description with an edit action, the workflow id, output storage path, and
a button that opens the workflow folder in the system file browser. Custom tools are created in the current workflow's `tools/` folder so a workflow
archive carries the custom tool sources it uses. Tool source opening keeps VS
Code or code-server rooted at the workspace project and focuses the selected
tool file. Reusable tools shared across workflows should be distributed as tool
packages; the Manage Tools dialog installs known packages from table rows and
unknown GitHub/GitLab or `.zip` package sources from the inline **Install tool
package** footer below the table.

## Prerequisites

- **Python** >= 3.12
- **Node.js** >= 20 (or [Bun](https://bun.sh/))
- **uv** (Python package manager)
- The [BioImageFlow library](https://gitlab.inria.fr/sairpico/bioimageflow) cloned alongside this repo (symlinked as `bioimageflow/`)

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
uv run python -m bioimageflow_server --host 127.0.0.1 --port 8000 --dev
```

**2. Frontend** (second terminal):

```bash
cd frontend
bun install
bun run dev
```

You can use `BIOIMAGEFLOW_BACKEND_PORT` to overwrite the port: `BIOIMAGEFLOW_BACKEND_PORT=8008 bun run dev` 
(when server is run with `uv run uvicorn bioimageflow_server.app:create_app --factory --host 127.0.0.1 --port 8008`)

Open <http://localhost:5173>. Vite proxies `/api` and `/ws` to `BIOIMAGEFLOW_BACKEND_PORT`, defaulting to port 8000.

The module entrypoint uses the packaged backend logging config by default, so application INFO logs are visible during development. To run raw Uvicorn instead, pass the same config explicitly:

```bash
cd backend
uv run uvicorn bioimageflow_server.app:create_app --factory --host 127.0.0.1 --port 8000 --reload --reload-dir src --log-config src/bioimageflow_server/logging.yaml
```

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

Use `--log-config /path/to/logging.yaml` with `python -m bioimageflow_server` when you need deployment-specific logging levels or handlers.

The pywebview window loads `http://localhost:5173` while the FastAPI backend runs on port 8000; API calls reach the backend through Vite's proxy.

## Testing

Use the root test runner for the same focused, quick, deterministic, and comprehensive lanes used by agents and CI:

```bash
scripts/test focus backend tests/test_services/test_dataset_store.py
scripts/test focus unit src/stores/__tests__/workflow.test.ts
scripts/test quick
scripts/test check
scripts/test full
```

Use focused tests during editing, `quick` for frequent coding checkpoints, `check` before completing an ordinary change, and `full` after large iterations or before releases.
Playwright manages isolated backend and frontend servers.
See [`docs/testing.md`](docs/testing.md) for exact lane contents, dependency setup, selectors, coverage, Firefox, source bootstrap, and external common-tools certification.

## Development

### Use the local core package in Wetlands workers

Wetlands tool environments install `bioimageflow-core` separately from the backend Python environment.
By default they inject the pinned published package version for reproducible user/runtime environments.
For local source development, set `BIOIMAGEFLOW_USE_LOCAL_CORE=1` before launching the backend so new Wetlands tool environments install the editable local `bioimageflow-core` checkout instead.
The VS Code launch profiles in `.vscode/launch.json` set this variable automatically.

Existing Wetlands envs are not rewritten when this flag changes.

### Install tool packages in editable mode

Create a symlink of the tool package:

```
mkdir -p ~/.bioimageflow/tool_packages/bioimageflow_common_tools/0.1.6

ln -sfn \
  /path/to/bioimageflow-common-tools/bioimageflow_common_tools \
  ~/.bioimageflow/tool_packages/bioimageflow_common_tools/0.1.6/bioimageflow_common_tools

```

Then restart the backend.

## Documentation

The versioned specifications are cumulative and have distinct status:

- [`platform_specs_v1.md`](platform_specs_v1.md) — normative current base.
- [`platform_specs_v2.md`](platform_specs_v2.md) — normative implemented additions, including sub-workflows and editor integration.
- [`platform_specs_v3.md`](platform_specs_v3.md) — future webapp and multi-user proposal; it is not an implemented contract.
- [`bioimageflow/docs/source/specs.md`](bioimageflow/docs/source/specs.md) — BioImageFlow library specification.

There is intentionally no separate comprehensive platform specification; current requirements live in v1/v2 and future proposals live in v3.

## Todo

- Handle .DS_Store; make error messages more clear
