# Test lanes

Run the local development commands from a checkout with the repository's sibling source links in place.
Those links use whichever sibling revisions are currently checked out, while CI bootstraps exact source revisions before installing the backend environment.

## Exact CI source bootstrap

CI does not use arbitrary local sibling revisions.
It checks out the full commit SHAs configured in `.gitlab-ci.yml` so required jobs are reproducible.

From a fresh checkout without existing sibling source paths or worktree source links, reproduce that bootstrap with:

```bash
export BIOIMAGEFLOW_SOURCE_REVISION=30473f203fd6dee81b476f20c0b2566675da44aa
export LAUNCHER_SOURCE_REVISION=54c38b5e404bac9f3db5203ac29fa75b2b7c5df3
export WETLANDS_SOURCE_REVISION=d0780c44a15c894cb69bed83562e864cc62c6288
bash scripts/ci/bootstrap_backend_sources.sh
```

The bootstrap script reuses only clean repositories already at the requested commit and refuses to replace any other existing path.
Keep using the repository's documented source links for ordinary development, and use a fresh checkout when exact CI source reproduction would conflict with those links.

## Required backend checks

```bash
cd backend
uv sync --extra dev --frozen
uv run --frozen ruff check .
uv run --frozen pytest -m "not common_tools"
uv run --frozen pytest \
  tests/test_logging_config.py \
  tests/test_ws/test_handler.py::test_publish_without_loop_drops_silently \
  tests/test_ws/test_handler.py::test_publish_logs_future_exceptions \
  tests/test_ws/test_logging_bridge.py::test_attach_to_bioimageflow_logger \
  -q
```

The first pytest invocation is deterministic and does not inspect an installed common-tools package.
The second invocation is an order regression for process-global logging configuration and log capture.

## Required frontend checks

```bash
cd frontend
bun install --frozen-lockfile
bun run lint
bun run type-check
bun run test:unit
bun run test:e2e -- --project=chromium
```

Playwright starts and stops the isolated backend and frontend servers declared in `playwright.config.ts`.
Set `BIOIMAGEFLOW_E2E_ROOT` only when a run needs a caller-managed persistent fixture directory.

## Optional browser certification

Firefox runs on the scheduled or manual CI lane and can be reproduced locally with:

```bash
cd frontend
bun run test:e2e -- --project=firefox
```

## External common-tools certification

The live package-index lane is intentionally separate from required deterministic tests.
It installs a pinned published package into an empty tool store and requires an explicit pytest option:

```bash
cd backend
uv sync --extra dev --frozen
cd ..
export BIOIMAGEFLOW_COMMON_TOOLS_VERSION=0.1.5
export BIOIMAGEFLOW_TOOL_STORE=/tmp/bioimageflow-common-tools-certification/tool_packages
bash scripts/ci/install_common_tools_from_index.sh
cd backend
uv run --frozen pytest --run-common-tools -m common_tools
```

The installer requires the backend virtual environment at `backend/.venv`, so run `uv sync` before invoking it.
Use a new empty `BIOIMAGEFLOW_TOOL_STORE` for every certification run.
With `--run-common-tools`, a missing store, import, package load, or expected class fails certification instead of being skipped.
An external failure does not replace or invalidate the repository-owned fixture coverage in the required backend lane.
