# Test lanes

The root test runner gives humans, agents, and CI one vocabulary for focused feedback, ordinary completion checks, and comprehensive certification.
Run `scripts/test help` from any directory in the checkout to see the available commands.

## Install test dependencies

The runner does not install the repository's normal development dependencies.
Prepare both environments once per checkout:

```bash
cd backend
uv sync --group dev --frozen
cd ../frontend
bun install --frozen-lockfile
```

Local development and CI both install the published dependency versions recorded in `backend/uv.lock`.

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
scripts/test focus e2e --project=firefox tests/e2e/hot-reload.spec.ts
scripts/test focus e2e --grep "executes a source tool"
scripts/test focus e2e --last-failed
```

The backend and frontend arguments after the focus target are forwarded to Pytest, Vitest, or Playwright.
Related-test selection is advisory because dynamic imports and runtime wiring are not always visible to static dependency analysis.
Focused browser runs use Chromium unless one or more Playwright `--project` options are provided.
Explicit project options are honored exactly, so `--project=firefox` does not also launch Chromium.
Focused runs use a fresh temporary runtime root, automatically selected local ports unless the caller explicitly sets the corresponding `BIOIMAGEFLOW_E2E_*` variables, and `--max-failures=1` unless the caller supplies another limit.

For a failing browser test, first reproduce its exact selector and project.
After a change, run it once, then use `--repeat-each=5` only when validating a timing or race fix.
Do not start a complete browser lane while the focused test still fails.

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
Use it at intermediate checkpoints when development will continue, but do not treat it as completion validation.
Do not run it immediately before a completion check that already includes the same phases.

## Scoped completion checks

```bash
scripts/test check backend
scripts/test check frontend
scripts/test check docs
scripts/test check browser-smoke
scripts/test check cross-browser-smoke
scripts/test check browser
scripts/test check browser-firefox
scripts/test check browser-all
scripts/test check app
scripts/test check all
```

Use the smallest scope that covers the changed surface:

| Change surface | Required completion check |
| --- | --- |
| Backend implementation or tests | `check backend` |
| Frontend logic or unit tests | `check frontend` |
| Documentation only | `check docs` |
| Backend/frontend API, schemas, dependencies, or runtime behavior | `check app` |
| Browser interaction, layout, or persistence | `check frontend` and `check browser` |
| Localized cross-browser behavior | `check frontend` and `check cross-browser-smoke` |
| Broad browser or E2E infrastructure | `check frontend` and `check browser-all` |
| Broad architecture or test-runner changes | `check all` |

`check backend` runs backend lint, every non-external backend test, and the logging-order certification.
`check frontend` runs frontend lint, type checking, every Vitest project, and the production build.
`check docs` runs Sphinx with warnings treated as failures.
`check browser-smoke` runs only Chromium tests tagged `@critical`, while `check browser` runs the complete Chromium project.
`check cross-browser-smoke` runs critical Chromium and Firefox tests in isolated parallel processes.
`check browser-firefox` runs the complete Firefox project.
`check browser-all` runs the complete Chromium and Firefox projects in isolated parallel processes without coverage or external certification.
`check app` runs the backend and frontend checks in parallel and follows them with the critical Chromium smoke.
`check all`, and the compatibility alias `check`, run the previous complete deterministic lane with the full Chromium project.
All scoped checks avoid network access and developer runtime tool stores unless their description explicitly says otherwise.

## Comprehensive end-of-iteration suite

```bash
scripts/test full
```

Use the full lane after large plans, before releases, for package-loading or external-compatibility changes, when explicitly requested, or when complete local certification is otherwise required.
Use the scoped cross-browser lanes for ordinary browser fixes.
It runs all backend tests in one invocation with no marker exclusion, all frontend unit projects, branch coverage, the production build, the logging-order regression, and the complete Chromium and Firefox suites.
Before starting the tests it installs the pinned published `bioimageflow-common-tools` package into a fresh temporary tool store.
The command fails if installation or external certification cannot run, so a successful full result never hides deselected external tests.
Chromium and Firefox run against separate temporary roots and servers in parallel.
Local browser lanes stop after the first failure by default.

If a late full-suite phase fails, fix and stress the exact failure first.
Successful earlier phases remain valid when subsequent edits cannot affect them; run only the scoped checks invalidated by those edits rather than restarting the full lane automatically.
Record the source revision, command, duration, and result so this reuse is explicit.

Coverage artifacts are written to `backend/.pytest_cache/coverage.xml`, `backend/.pytest_cache/htmlcov/`, and `frontend/test-results/coverage/`.
The transient Coverage.py database is stored under `backend/.pytest_cache/` and removed on success or failure, so the suite does not leave `backend/.coverage` behind.

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

## CI mapping

Pull-request jobs run the selected deterministic backend, frontend, documentation, and Chromium portions in separate GitHub-hosted runners so they can execute in parallel.
Frontend changes, backend runtime changes, E2E fixtures, and shared test infrastructure also select a critical Firefox smoke job.
Scheduled and manually dispatched certification splits backend coverage and external certification, frontend coverage and build, Chromium, and Firefox into independent jobs with a final required aggregator.
This preserves the complete certification surface while making its wall time the longest component rather than the sum of every component.
The published common-tools version has one source of truth in `scripts/ci/test_versions.env`, shared by local and CI runners.
