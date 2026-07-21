# Test lanes

The root test runner gives humans, agents, and CI one vocabulary for focused feedback, ordinary completion checks, and comprehensive certification.
Run `scripts/test help` from any directory in the checkout to see the available commands.

## Install test dependencies

The runner does not install the repository's normal development dependencies.
Prepare both environments once per checkout:

```bash
cd backend
uv sync --extra dev --frozen
cd ../frontend
bun install --frozen-lockfile
```

Local development uses the sibling source checkouts linked into the repository.
CI instead checks out the exact full commit SHAs configured in `.github/workflows/ci.yml` before it installs the backend environment.

## Focused tests while editing

Use the narrowest native selector that exercises the code being changed:

```bash
# Backend file, exact test, expression, or previous failures
scripts/test focus backend tests/test_services/test_dataset_store.py
scripts/test focus backend tests/test_services/test_dataset_store.py::test_name
scripts/test focus backend -k "dataset and delete"
scripts/test focus backend --lf

# Frontend unit file, test name, or tests related to a source file
scripts/test focus unit src/stores/__tests__/workflow.test.ts
scripts/test focus unit src/stores/__tests__/workflow.test.ts -t "deletes workflow"
scripts/test focus related frontend/src/stores/workflow.ts

# Browser spec, source line, test name, or previous failures
scripts/test focus e2e tests/e2e/execution.spec.ts
scripts/test focus e2e tests/e2e/execution.spec.ts:111
scripts/test focus e2e --grep "executes a source tool"
scripts/test focus e2e --last-failed
```

The backend and frontend arguments after the focus target are forwarded to Pytest, Vitest, or Playwright.
Related-test selection is advisory because dynamic imports and runtime wiring are not always visible to static dependency analysis.
Focused browser runs use Chromium, a fresh temporary runtime root, and automatically selected local ports unless the caller explicitly sets the corresponding `BIOIMAGEFLOW_E2E_*` variables.

## Quick coding checkpoint

```bash
scripts/test quick
```

The quick lane runs independent phases in parallel:

- Ruff and ESLint.
- TypeScript type checking.
- Backend tests that are not marked `integration`, `serial`, `slow`, or `external`.
- Frontend tests in the Node Vitest project.

It deliberately omits browsers, coverage instrumentation, external packages, and tests that cross application or process-global boundaries.
Use it frequently during an implementation, but do not treat it as completion validation.

## Deterministic completion check

```bash
scripts/test check
```

The check lane runs all repository-owned backend and frontend tests, lint, type checking, the production frontend build, the logging-order regression, and the complete Chromium suite.
It excludes only tests marked `external`, and reports that exclusion explicitly at the end.
It does not require network access or inspect packages from a developer's runtime tool store.

## Comprehensive end-of-iteration suite

```bash
scripts/test full
```

Use the full lane after large plans, before releases, and when changes affect package loading or cross-browser behavior.
It runs all backend tests in one invocation with no marker exclusion, all frontend unit projects, branch coverage, the production build, the logging-order regression, and the complete Chromium and Firefox suites.
Before starting the tests it installs the pinned published `bioimageflow-common-tools` package into a fresh temporary tool store.
The command fails if installation or external certification cannot run, so a successful full result never hides deselected external tests.

Coverage artifacts are written to `backend/.pytest_cache/coverage.xml`, `backend/.pytest_cache/htmlcov/`, and `frontend/test-results/coverage/`.

The desktop suite remains headless and mocks pywebview, so even a successful full lane does not certify a packaged native window or operating-system dialogs.
That boundary requires a future platform-specific smoke or manual release check and is not silently represented as automated coverage.

The eight current external tests certify one integration package rather than representing eight general tool-package unit tests.
They cover graph schemas and registry discovery against the actual published package surface.
Other package installation and discovery behavior remains covered by repository-owned fixtures in the deterministic lane.
Additional published tool packages should receive an external lane only when the platform declares a compatibility contract with them; test count alone is not a reason to duplicate this certification.

## External certification by itself

```bash
scripts/test certification
```

This command installs the version declared in `scripts/ci/test_versions.env` from the package index into a new empty store, then runs only tests marked `external` with `--run-external`.
The installer places only the tool package in that store; runtime dependencies remain owned by the pinned backend environment so they cannot shadow the platform's editable source dependencies.
It requires network access and an existing `backend/.venv`.
The temporary store is deleted when the command exits.

## Test categories

Backend markers describe execution requirements rather than product ownership:

- `integration`: multiple real components or an application/filesystem/execution boundary.
- `serial`: process-global state or ordering-sensitive behavior.
- `slow`: measured runtime that is unsuitable for the quick loop.
- `external`: a published package or other separately installed compatibility surface.
- `common_tools`: the descriptive package-specific subset of `external`; `external` remains the opt-in guard.

Pytest marker validation is strict, so misspelled or unregistered categories fail collection.
The external marker is the lane selector; `common_tools` identifies which external dependency supplies those cases.

## Exact CI source bootstrap

The full runner intentionally does not rewrite local sibling source checkouts.
To reproduce CI from a fresh checkout without existing sibling paths, first use the exact revisions from `.github/workflows/ci.yml`:

```bash
export BIOIMAGEFLOW_SOURCE_REVISION=30473f203fd6dee81b476f20c0b2566675da44aa
export LAUNCHER_SOURCE_REVISION=54c38b5e404bac9f3db5203ac29fa75b2b7c5df3
export WETLANDS_SOURCE_REVISION=d0780c44a15c894cb69bed83562e864cc62c6288
bash scripts/ci/bootstrap_backend_sources.sh
```

The bootstrap script reuses only clean repositories already at the requested commit and refuses to replace any other existing path.
Use a fresh checkout when exact CI reproduction would conflict with development links.

## CI mapping

Pull-request jobs run the deterministic backend, frontend, documentation, and Chromium portions in separate GitHub-hosted runners so they can execute in parallel.
The scheduled and manually dispatched `Full certification` job uses `scripts/test full` and therefore adds branch coverage, Firefox, and fresh package-index certification.
The published common-tools version has one source of truth in `scripts/ci/test_versions.env`, shared by local and CI runners.
