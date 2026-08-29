# BioImageFlow Platform

BioImageFlow Platform is a desktop application for building, running, and inspecting bioimage-analysis workflows visually.
It combines the [BioImageFlow](https://github.com/Inria-SAIRPICO/bioimageflow) workflow library with a node-based editor, versioned analysis tools, data viewers, and local or distributed execution.

![A BioImageFlow workflow open on the canvas, with tools, workflow tabs, node data, and execution controls visible.](docs/user/images/interface-overview.png)

## Install BioImageFlow

Download the launcher for your operating system from the [BioImageFlow releases](https://github.com/Inria-SAIRPICO/bioimageflow-platform/releases).
The launcher installs a verified application release and prepares its isolated environment.

Follow [Getting Started](https://bioimageflow-platform.readthedocs.io/latest/user/) to install BioImageFlow, run the bundled **Fish Analysis** demo, and inspect its results.

## Documentation

The complete documentation is published at <https://bioimageflow-platform.readthedocs.io/latest/>.

- [Getting Started](https://bioimageflow-platform.readthedocs.io/latest/user/) covers installation and the first workflow run.
- [Interface Tour](https://bioimageflow-platform.readthedocs.io/latest/user/interface.html) introduces the canvas, panels, menus, and run controls.
- [Build a Workflow](https://bioimageflow-platform.readthedocs.io/latest/user/build-workflows.html) explains the main editing workflow.
- [Developer Guide](https://bioimageflow-platform.readthedocs.io/latest/developer/) collects contributor and maintainer references.

## Development

### Requirements

- Python 3.12 or newer
- [uv](https://docs.astral.sh/uv/)
- [Bun](https://bun.sh/) or Node.js 20 or newer

### Repository layout

```text
bioimageflow-platform/
  backend/       Python server and desktop entry point
  frontend/      TypeScript application and workflow editor
  docs/          User and developer documentation
  scripts/       Test, packaging, and maintenance commands
```

### Start the desktop application with hot reload

Install the frontend and backend development dependencies once:

```bash
cd frontend
bun install

cd ../backend
uv sync --group dev --extra desktop
```

Then start the frontend and desktop application in separate terminals from the repository root:

```bash
cd frontend
bun run dev
```

```bash
cd backend
uv run python -m bioimageflow_server --desktop --dev
```

The desktop window loads the Vite development server at <http://localhost:5173> and sends API requests to the backend at <http://127.0.0.1:8000>.
See [Local Development](docs/developer/local-development.md) for production-mode builds, browser-based frontend development, logging, local BioImageFlow source, and editable tool packages.

## Testing

Use `scripts/test` as the repository test entry point.
Run focused tests while editing, then the smallest scoped check that covers the completed change:

```bash
scripts/test focus backend tests/test_services/test_demo_workflows.py
scripts/test focus unit src/stores/__tests__/workflow.test.ts
scripts/test quick
scripts/test check app
```

See [Test Lanes](docs/testing.md) for selectors, lane contents, browser coverage, and external package certification.

## Build the documentation

Build once with warnings treated as errors:

```bash
uv run --no-project --with-requirements docs/requirements.txt -- \
  sphinx-build -W --keep-going docs docs/_build/html
```

For a local server that rebuilds and reloads when documentation changes:

```bash
uv run --no-project --with-requirements docs/requirements.txt -- \
  sphinx-autobuild docs docs/_build/html
```

Open <http://127.0.0.1:8000/> and press <kbd>Ctrl</kbd>+<kbd>C</kbd> to stop the server.

## Contributor references

- [Platform Architecture](docs/developer/architecture.md) describes the backend, frontend, desktop shell, and workflow editing model.
- [Managed Distributed Execution](docs/user/distributed-execution.md) explains trusted cluster profiles, workspace-scoped durable reconnection, verified retained result download, and cleanup.
- [Workspace, Storage, and Demos](docs/developer/workspace-storage-and-demos.md) documents filesystem ownership, latest-output views, exports, and bundled workflow maintenance.
- [Release Process](docs/developer/releases.md) is the application and launcher release checklist.
- [Backend README](backend/README.md) covers the server, desktop entry point, API, and Python package.
- [Frontend README](frontend/README.md) covers the editor application, build commands, and frontend structure.
- [Platform specifications](platform_specs_v1.md) define the implemented base; [recursive workflow behavior](platform_specs_v2.md) and [managed distributed execution](platform_specs_distributed_execution.md) extend it, while [v3](platform_specs_v3.md) is a future proposal.
