---
orphan: true
---

# Test lanes

The root test runner gives humans, agents, and CI one vocabulary for focused feedback, ordinary completion checks, and comprehensive certification.
Run `scripts/test help` from any directory in the checkout to see the available commands.

For native desktop, external-application, coding-agent, and human-judgment checks that remain outside these automated lanes, use the [Manual Platform Testing](developer/manual-testing.md) guide and its reusable `scripts/manual-qa` fixtures.

The [Platform confidence campaign](developer/platform-test-plan.md) sequences current-code readiness and systematic feature work using these existing lanes.
Its [current checkpoint](developer/platform-test-current.md) links scoped execution evidence and the active task; it does not redefine command scopes.
Read only the relevant task/specification sections and direct receipts; the [historical progress log](developer/platform-test-progress.md) is optional exact-look-up evidence, not required resume reading or a detailed append target.

## Install test dependencies

The runner does not install the repository's normal development dependencies.
Prepare both environments once per checkout:

```bash
cd backend
uv sync --group dev --frozen
cd ../frontend
bun install --frozen-lockfile
```

The backend lock resolves published `bioimageflow[parsl,psij]==0.9.2`, Core 0.5 and Wetlands 2.6.1 from the registry; ordinary tests and CI do not require a sibling source checkout.
Installing the explicit scheduler dependency groups preserves the packaged capability and does not certify excluded distributed features.
Explicit source investigations use a separate owned interpreter and record their library revision, as described in [Local Development](developer/local-development.md#use-local-bioimageflow-source); they do not certify published compatibility.
Reuse a checkout's prepared environments while its lockfiles, dependency metadata and installation options remain compatible; resync the affected environment when installation requirements change.
Keep dependencies and build/runtime state separate between worktrees, and keep browser runtime roots and certification stores disposable even when dependency installation is reused.

## Focused tests while editing

Map changed files to their owning service/session, callers, persistence and event consumers, and public library boundary before choosing selectors; `focus related` alone cannot establish that impact map.
Tools whose executable source is admitted by the library belong in ordinary imported fixture packages such as `backend/platform_test_tools`, separate from pytest test modules; pytest assertion rewriting must not become their admitted source authority.
Temporary installed-package fixtures need real distribution metadata and a complete RECORD computed from their current files; refresh that authority after intentional source edits.
Portable-workflow and immutable-record fixtures use the current public graph and result-relation contracts.
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
scripts/test check campaign
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
| Campaign checkpoint, issues, evidence, inventories, or dashboard only | `check campaign` |
| Other documentation or campaign navigation/structure | `check docs` |
| Backend/frontend API, schemas, dependencies, or runtime behavior | `check app` |
| Browser interaction, layout, or persistence | `check frontend` and `check browser` |
| Localized cross-browser behavior | `check frontend` and `check cross-browser-smoke` |
| Broad browser or E2E infrastructure | `check frontend` and `check browser-all` |
| Broad architecture or test-runner changes | `check all` |

`check backend` runs backend lint, every non-external backend test, and the logging-order certification.
`check frontend` runs frontend lint, type checking, every Vitest project, and the production build.
`check campaign` verifies dashboard/inventory consistency and active campaign local links offline; it does not replace Sphinx for documentation structure or the final certification.
`check docs` includes `check campaign`, then runs Sphinx with warnings treated as failures.
Run `check campaign` once for a consolidated campaign-documentation task, not after each row or sentence edit.
Run `check docs` when moving/renaming campaign files, changing documentation navigation/extensions, at a substantial documentation milestone, and at final certification; do not repeat it for routine campaign status edits.
`check browser-smoke` runs only Chromium tests tagged `@critical`, while `check browser` runs the complete Chromium project.
`check cross-browser-smoke` runs critical Chromium and Firefox tests in isolated parallel processes.
`check browser-firefox` runs the complete Firefox project.
`check browser-all` runs the complete Chromium and Firefox projects in isolated parallel processes without coverage or external certification.
`check app` runs the backend and frontend checks in parallel and follows them with the critical Chromium smoke.
`check all`, and the compatibility alias `check`, run the previous complete deterministic lane with the full Chromium project.
Both include the quick product phases, so do not stack `quick` immediately before them; neither includes Firefox, external certification, or documentation.
Scoped product checks use isolated test fixtures rather than developer runtime tool stores; cold dependency setup can still require network access.
`check campaign` is offline, while `check docs` resolves its Sphinx environment with `uv --with-requirements` and can require network when the cache is cold.

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
`full` subsumes the backend/frontend product checks, both browser projects, and common-tools certification; it does not run `check docs` or native/manual acceptance.
Run documentation acceptance separately when required rather than stacking already-covered product lanes before `full`.

If a late full-suite phase fails, fix and stress the exact failure first.
Successful earlier phases remain valid when subsequent edits cannot affect them; run only the scoped checks invalidated by those edits rather than restarting the full lane automatically.
Record the source revision, command, duration, and result so this reuse is explicit.
Justify reuse with unchanged relevant source, fixtures, dependencies/editable library, generated artifacts, and runtime assumptions; retain the original failed command and every skipped or unrun case alongside the newer phase results.

Coverage artifacts are written to `backend/.pytest_cache/coverage.xml`, `backend/.pytest_cache/htmlcov/`, and `frontend/test-results/coverage/`.
The transient Coverage.py database is stored under `backend/.pytest_cache/` and removed on success or failure, so the suite does not leave `backend/.coverage` behind.

The desktop suite remains headless and mocks pywebview, so even a successful full lane does not certify a packaged native window or operating-system dialogs.
That boundary requires a future platform-specific smoke or manual release check and is not silently represented as automated coverage.

The eight current external tests certify one integration package rather than representing eight general tool-package unit tests.
They cover graph schemas and registry discovery against the actual published package surface.
The additional real Wetlands worker fixture is marked `external`, `integration`, `serial`, and `slow` because it changes process-wide manager state and creating its isolated worker environment can download dependencies.
It runs in `full`, and can be selected explicitly with `scripts/test focus backend tests/test_integration/test_platform_fixture_contracts.py --run-external`.
It verifies actual worker process identity, transformed values, and output files; a DataFrame-only graph selecting Direct is not worker certification.
The stale-generation fixture in `tests/test_integration/test_stale_processing_environment.py` uses the same `external`, `integration`, `serial`, and `slow` boundaries and is selected with `scripts/test focus backend tests/test_integration/test_stale_processing_environment.py::test_real_stale_generation_failure_retry_and_fresh_process_reuse --run-external`.
It exercises whole-workflow computation through the platform preparation adapter with a genuine owned stale recipe, actual Pixi installation failure and retry, retired worker cleanup, fresh creation, unrelated/unmanaged isolation, and warm plus fresh-orchestrator-process generation reuse.
That restart assertion covers orchestration and worker reuse, not a packaged native desktop restart.
Other package installation and discovery behavior remains covered by repository-owned fixtures in the deterministic lane.
Additional published tool packages should receive an external lane only when the platform declares a compatibility contract with them; test count alone is not a reason to duplicate this certification.

## External certification by itself

```bash
scripts/test certification
```

This command installs the version declared in `scripts/ci/test_versions.env` from the package index into a new empty store, then runs tests marked both `external` and `common_tools` with `--run-external`.
It does not run the separate real Wetlands worker fixtures.
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

The local-platform campaign uses per-test markers or annotations together with the exact checked-in manifest at `tests/campaign-local-scope.json`.
Run each complete audited selection directly with `scripts/test focus backend --campaign-local`, `scripts/test focus unit --campaign-local`, or `scripts/test focus e2e --campaign-local`.
The browser selector defaults to Chromium; `--list`, `--project=chromium`, and `--project=firefox` are the only additional campaign arguments, and both project flags may be passed when both browser engines are required.
Frontend-unit and browser campaign selectors reject test-file, title, line, and grep filters up front because a partial collection cannot prove that every manifest identity is still present.
Collection fails if an annotation or manifest entry is missing, duplicated, stale, or uses a reason outside `parallel-scheduling`, `parsl`, `managed-remote`, and `distributed-engine`.
These are intentionally separate scope selectors; a repository-wide campaign command remains unavailable until their combined orchestration and evidence reporting are validated.

## CI mapping

Pull-request jobs run the selected deterministic backend, frontend, documentation, and Chromium portions in separate GitHub-hosted runners so they can execute in parallel.
Frontend changes, backend runtime changes, E2E fixtures, and shared test infrastructure also select a critical Firefox smoke job.
The current path selector treats changes outside `backend/`, `frontend/`, `docs/`, and `README.md` as shared and selects all five PR jobs; this includes root instructions such as `AGENTS.md` and `PLATFORM_CONTEXT.md`.
Routine documentation PRs still select the Sphinx job; the local campaign-status schedule does not change CI selection or demonstrate CI savings.
Scheduled and manually dispatched certification splits backend coverage and external certification, frontend coverage and build, Chromium, and Firefox into independent jobs with a final required aggregator.
Its backend job excludes `external`, and its external job runs common-tools certification only, so the separate real-worker fixtures and Sphinx still need explicit acceptance evidence.
Independent jobs can overlap; actual elapsed cost also includes dependency setup and runner queue time, and no measured savings are claimed here.
The published common-tools version has one source of truth in `scripts/ci/test_versions.env`, shared by local and CI runners.
