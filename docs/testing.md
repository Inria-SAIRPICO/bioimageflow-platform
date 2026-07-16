# Test lanes

Run these commands from a checkout with the repository's sibling source links in place.
They are the same checks used by repository CI.

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
export BIOIMAGEFLOW_COMMON_TOOLS_VERSION=0.1.6
export BIOIMAGEFLOW_TOOL_STORE=/tmp/bioimageflow-common-tools-certification/tool_packages
bash scripts/ci/install_common_tools_from_index.sh
cd backend
uv run --frozen pytest --run-common-tools -m common_tools
```

Use a new empty `BIOIMAGEFLOW_TOOL_STORE` for every certification run.
An external failure does not replace or invalidate the repository-owned fixture coverage in the required backend lane.
