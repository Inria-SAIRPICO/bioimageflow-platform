# BioImageFlow Platform

A desktop application for building, executing, and inspecting bioimage analysis workflows visually. It wraps the [BioImageFlow](https://github.com/Inria-SAIRPICO/bioimageflow) library with a node-based editor, parameter panels, data viewers, and execution controls.

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

Each root canvas persists its editable recursive `GraphState` through a revisioned backend workflow draft, which is the durable authority shared with Save, Run, and agents. The same graph can appear as a workflow node inside another graph; nested canvases persist private revisioned snapshots until explicit parent apply. `workflow.json` is the explicitly saved canonical platform document, while `PUT /graph` provides request-local validation without retaining editor state. The backend also holds transient execution state during workflow runs.

## Workspace Model

Each user has one active BioImageFlow workspace. Desktop mode defaults to `~/BioImageFlow/workspace/` and can select another path in Settings; proposed webapp deployments derive it from an admin-managed workspaces root as `<workspaces_root>/<user_id>/workspace/`.

```text
workspace/
  workflows/                          Saved workflow tree and folders
    <workflow-id>/tools/              Custom tools owned by one workflow
```

Execution outputs use the configured output-data folder, which defaults to `~/bioimageflow_data/`, and are scoped by workflow ID. Dataset uploads use the configured dataset root or `<BIOIMAGEFLOW_HOME>/datasets/`; neither is owned by `workspace/data` or `workspace/outputs` in the current implementation.

For each workflow, the file-browser-friendly output projection is `outputs/latest/<node>/<asset-relative-path>` beneath that workflow's storage directory.
The `latest` projection means the latest successful result independently for each node, so it can contain results from different executions after selected, failed, cancelled, or overlapping runs; it is not a single workflow-run snapshot.
The canonical cache and run views remain unchanged.

Preferences → Storage controls how this disposable projection is published.
Automatic mode uses symbolic links when the output filesystem permits them and otherwise uses portable `*.bioimageflow-link.json` pointer files with a warning.
Pointer files require no link permission but are not directly openable as images, symbolic links may require Windows Developer Mode or link privileges, and copying is an explicit option that can use roughly twice the asset space.
The workflow panel's Open latest outputs action opens this per-workflow directory directly in desktop mode.

The Run Workflow split button offers Run Selected, Retry Failed Execution, Invalidate Failed Nodes and Retry, and Recompute Workflow.
Retry reuses successful cached work and the original execution target set.
Invalidating a failed retry clears the failed nodes and their downstream cache selections atomically before retrying, while Recompute invalidates every enabled node before a full run.
Invalidation changes cache selection but does not delete retained records or immediately reclaim disk space.

When the application initializes a workflow root that did not previously exist, it installs the bundled **Fish Analysis** and **Parameters Space Exploration** workflows under `Demo/`. Existing workflow roots, including existing empty roots, are not seeded. The Storage tab in Settings reports their derived status and provides explicit **Install demos** and **Remove demos** actions. Removing demos never removes unrelated workflows from the `Demo` folder, and changing to another existing workspace does not copy demos into it automatically.

The two demo definitions are generated from the maintained Python examples by `scripts/export_demo_workflows.py --bioimageflow-source /path/to/bioimageflow`. This maintainer command explicitly consumes a BioImageFlow source checkout; normal platform development and CI use only registry packages. The demos download public input images into workflow-managed run assets, do not depend on repository-local data, and retain ordinary missing-package diagnostics without installing packages automatically.

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
a button that opens the workflow folder in the system file browser. Dragging a saved workflow onto the canvas embeds an executable snapshot with explicit source provenance, and any workflow may be grouped or opened recursively using the same interface model. Custom tools are created in the current workflow's `tools/` folder so a workflow
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
- The [BioImageFlow library](https://github.com/Inria-SAIRPICO/bioimageflow) cloned alongside this repo (symlinked as `bioimageflow/`)

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
uv sync --no-dev --extra desktop
uv run --no-dev --extra desktop bioimageflow-gui
```

A native window opens at `http://127.0.0.1:8000` showing the SPA served from `frontend/dist/`. Pywebview's developer tools stay disabled in this production mode. Closing the window shuts the server down cleanly.

## Quick Start — Browser (development)

Keep the frontend's hot-module-replacement while iterating on UI code.

**1. Backend** (first terminal):

```bash
cd backend
uv sync --group dev
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

Get hot reload and pywebview's developer tools inside the native window.

```bash
# terminal 1 -- frontend dev server
cd frontend && bun run dev

# terminal 2 -- desktop window pointing at Vite
cd backend
uv sync --group dev --extra desktop
uv run python -m bioimageflow_server --desktop --dev
```

Use `--log-config /path/to/logging.yaml` with `python -m bioimageflow_server` when you need deployment-specific logging levels or handlers.

The `--dev` flag makes the pywebview window load `http://localhost:5173` and open its developer tools while the FastAPI backend runs on port 8000; API calls reach the backend through Vite's proxy.
The repository's VS Code **Desktop** launch profile selects this same development mode.

## Testing

Use the root test runner for the same focused, quick, deterministic, and comprehensive lanes used by agents and CI:

```bash
scripts/test focus backend tests/test_services/test_dataset_store.py
scripts/test focus unit src/stores/__tests__/workflow.test.ts
scripts/test focus e2e --project=firefox tests/e2e/hot-reload.spec.ts
scripts/test quick
scripts/test check
scripts/test check cross-browser-smoke
scripts/test full
```

Use focused tests during editing, `quick` for coding checkpoints, the smallest scoped `check` before completing an ordinary change, and `full` only for complete certification after large iterations or before releases.
Playwright manages isolated backend and frontend servers.
See [`docs/testing.md`](docs/testing.md) for exact lane contents, dependency setup, selectors, coverage, Firefox, source bootstrap, and external common-tools certification.

## Packaging releases

BioImageFlow Platform is distributed with [`wetlands-launcher`](https://github.com/arthursw/launcher).
The [`wetlands-launcher` packaging guide](https://github.com/arthursw/launcher/blob/main/docs/packaging.md) is the comprehensive reference for one-time signing setup and generic command behavior.
This section is the BioImageFlow-specific release checklist.

The exact static version in `backend/pyproject.toml` is the release tag.
Do not add a `v` prefix: version `0.1.19` produces Git tag `0.1.19`, release asset names containing `0.1.19`, and no `v0.1.19` alias.
The `RELEASE_TAG` shell variable below is only used to make filenames readable in this checklist; Launcher commands independently infer and verify the same value from `pyproject.toml`.

### 1. Prepare and validate the release commit

Set `[project].version` in `backend/pyproject.toml`, then regenerate the lockfile:

```bash
export RELEASE_TAG="0.1.19"

cd backend
uv lock
uv sync --group dev --frozen
cd ..
```

Commit every intended source, version, lockfile, configuration, and submodule change before releasing.
If the version bump is the only uncommitted release preparation, commit it with:

```bash
git add backend/pyproject.toml backend/uv.lock
git commit -m "Prepare release ${RELEASE_TAG}"
```

Run the release-level validation on that exact commit:

```bash
scripts/test full
git status --short --untracked-files=no
```

The tracked worktree and index must be clean.
If validation requires a fix, commit the fix and rerun the full lane.
Push the validated release commit to `main` before creating its tag:

```bash
git push origin main
```

### 2. Rebuild launchers only when the launcher changed

Every release publishes a new application archive.
Rebuild, sign, and upload platform launcher packages only when the launcher executable or its bundled inputs changed, including a `wetlands-launcher` upgrade, `application.yml`, icons, PyInstaller inputs, or signing behavior.
For an app-only release, skip this phase and phase 5; existing launcher downloads remain valid and will install the new application update.

When a rebuild is required, check out the same clean release commit on every target operating system and build from `backend/`:

```bash
export RELEASE_TAG="0.1.19"

cd backend
uv sync --group dev --frozen
uv run --with pyinstaller launcher build
uv run launcher build package
cd ..
```

PyInstaller must be installed in the same `uv run` environment as Launcher.
Icons are generated with `scripts/generate_desktop_icons`.
The generator keeps the Windows and Linux launcher artwork full-size and creates an inset `backend/packaging/launcher/app.icns` for the macOS launcher bundle.
Standard packages are named from the inferred release tag, for example:

```text
backend/dist/BioImageFlow-launcher-0.1.19-macos-arm64.zip
backend/dist/BioImageFlow-launcher-0.1.19-windows-x64.zip
```

Do not upload unsigned macOS or Windows packages publicly.
Submit each of them to the Inria signing pipeline from the [`signing/`](signing/README.md) submodule.
The helper waits for signing and, on macOS, notarization, then downloads the verified result to `signing/signed/`:

```bash
cd signing
export GITLAB_TOKEN="<token>"

# or on Windows PowerShell:
# $env:GITLAB_TOKEN="<token>"

uv run python scripts/submit_launcher.py \
  --file "../backend/dist/BioImageFlow-launcher-${RELEASE_TAG}-macos-arm64.zip" \
  --project-id "474" \
  --ref main \
  --platform macos
cd ..
```

Use `--platform windows` and the `windows-x64` ZIP on Windows.
The helper infers the exact release tag from the standard package filename and rejects a platform or explicit-tag mismatch.
Linux launcher packages bypass the Inria operating-system signing pipeline.

### 3. Create the Git tag and GitHub release

Authenticate once with `gh auth login`.
From `backend/`, create the raw version tag at the current commit, push it, and create the provider release:

```bash
cd backend
uv run launcher release create \
  --tag \
  --push \
  --notes-text "<release notes>"
```

For longer notes, replace `--notes-text` with `--notes ../RELEASE_NOTES.md`.
Create the provider release only once.

### 4. Publish the signed application update

Still from `backend/`, create the application archive while the inferred release tag resolves to `HEAD`, then sign, verify, and upload it:

```bash
uv run launcher release archive
uv run launcher release sign
uv run launcher release verify
uv run launcher release upload
```

The upload publishes the versioned application ZIP together with `launcher-manifest.yml` and `launcher-manifest.yml.sig`.
These three assets are mandatory for every release.

### 5. Upload rebuilt launcher packages

Skip this phase for an app-only release.
When launchers were rebuilt, gather the signed packages in one checkout when practical and upload each one from `backend/`:

```bash
uv run launcher build upload \
  --asset "../signing/signed/BioImageFlow-launcher-${RELEASE_TAG}-macos-arm64.zip"
```

The command infers the tag and platform from project metadata and the package filename, uploads the exact asset, and updates `packaging/launcher/distribution.yml` after success.
If platforms upload from separate machines, commit and push `distribution.yml` after each upload and pull that commit before the next upload so entries are not overwritten.

After every platform package is recorded, update the existing release notes once:

```bash
uv run launcher release update-notes \
  --notes-text "<release notes>"
```

Commit the final distribution metadata:

```bash
cd ..
git add backend/packaging/launcher/distribution.yml
git commit -m "Record ${RELEASE_TAG} launcher downloads"
git push origin main
```

### 6. Verify the published release

Open the release and inspect its tag and assets:

```bash
gh release view "${RELEASE_TAG}" --web
```

Confirm that:

- the release tag is exactly `${RELEASE_TAG}`, without `v`;
- the application ZIP, `launcher-manifest.yml`, and `launcher-manifest.yml.sig` are present;
- every rebuilt launcher ZIP has the expected platform suffix and is linked from the release notes;
- the final `distribution.yml` change is committed and pushed;
- an existing installed launcher can discover, verify, install, and start the new application release;
- every newly rebuilt launcher starts successfully on a clean target system.

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

Published documentation is available at <https://bioimageflow-platform.readthedocs.io/latest/>.
Start with the [User Guide](https://bioimageflow-platform.readthedocs.io/latest/user/) to download the launcher, build and run workflows, inspect results, and configure the desktop application.
The documentation source is in `docs/` and can be built locally with the same warnings-as-errors policy used by CI and Read the Docs:

```bash
uv venv
uv pip install -r docs/requirements.txt
.venv/bin/sphinx-build -W --keep-going docs docs/_build/html
```

The versioned specifications are cumulative and have distinct status:

- [`platform_specs_v1.md`](platform_specs_v1.md) — normative current base.
- [`platform_specs_v2.md`](platform_specs_v2.md) — normative recursive workflow, interface, provenance, and editor specification.
- [`platform_specs_v3.md`](platform_specs_v3.md) — future webapp and multi-user proposal; it is not an implemented contract.
- [`bioimageflow/docs/source/specs.md`](bioimageflow/docs/source/specs.md) — BioImageFlow library specification.

There is intentionally no separate comprehensive platform specification; current requirements live in v1/v2 and future proposals live in v3.

## Todo

- Handle .DS_Store; make error messages more clear
