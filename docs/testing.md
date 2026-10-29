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

The backend lock resolves published `bioimageflow[parsl,psij]==0.9.6`, Core 0.5.1 and Wetlands 2.6.1 from the registry; ordinary tests and CI do not require a sibling source checkout.
Installing the explicit scheduler dependency groups preserves the packaged capability and does not certify excluded distributed features.
Explicit source investigations use a separate owned interpreter and record their library revision, as described in [Local Development](developer/local-development.md#use-local-bioimageflow-source); they do not certify published compatibility.
Reuse a checkout's prepared environments while its lockfiles, dependency metadata and installation options remain compatible; resync the affected environment when installation requirements change.
Keep dependencies and build/runtime state separate between worktrees, and keep browser runtime roots and certification stores disposable even when dependency installation is reused.

Every `scripts/test` lane forces `PYTHON_KEYRING_BACKEND=keyring.backends.fail.Keyring` before launching subprocesses, overriding an inherited native backend so automated checks cannot discover or prompt for the personal Keychain.
Credential-dependent tests inject memory providers explicitly; owned live integration can install a process-local RAM provider while replacement workers fail closed.
This test guard does not change production credential behavior, and native credential integration remains outside automated acceptance.

## Feature suites

Every test command defaults to the **local** suite, including direct Pytest, Vitest, and Playwright invocations.
The local suite covers the application, Direct and Wetlands execution, local scheduling, persistence, and engine-neutral execution state and results.
The **distributed** suite covers managed cluster profiles, remote submission and preflight, distributed run observation, retry, and remote cleanup.
Distributed tests are optional and run only when explicitly selected.

```bash
scripts/test check all                          # Required local checks
scripts/test --suite distributed focus backend # Optional distributed backend tests
scripts/test --suite distributed focus unit    # Optional distributed frontend tests
scripts/test --suite distributed focus e2e --project=firefox
scripts/test distributed                        # Distributed backend, units, and both browsers
scripts/test --suite all full                    # Both feature suites plus external certification
```

`--suite local|distributed|all` precedes the command and applies to feature-test phases.
`BIOIMAGEFLOW_TEST_SUITE` supplies the same selection to native runners; Pytest also accepts its own `--suite` option.
Misspelled suite names fail rather than broadening the selection.
File, title, browser, critical-test, and marker filters narrow the selected feature suite.
A test excluded by the feature suite cannot be enabled by a title filter; choose `distributed` or `all` first.
The `distributed` convenience command always selects distributed features regardless of the inherited suite.
Shared logging-order checks always run their local infrastructure controls, and `certification` always selects common-tools compatibility independently of the feature suite.
`full` accepts `local` or `all`; use `distributed` for distributed-only validation without external package setup.

Backend tests declare `pytest.mark.distributed`, frontend unit tests use `distributedTest(...)`, and browser tests declare the native `@distributed` tag.
These declarations are the feature classification authority; no duplicate list of test names or campaign exclusion inventory is maintained.
Vitest applies selection before suite hooks and callbacks, while Pytest and Playwright deselect the other feature suite during collection.
Collection/list output establishes selection, not successful execution.
Historical campaign receipts retain the old command names as evidence for their original revision; current work uses the commands above.

Feature suites and external compatibility are independent dimensions.
Selecting distributed features does not enable external package/service tests, and common-tools certification does not certify distributed execution.

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

The noncritical `thumbnail-real.spec.ts` journey prepares its own 8×8 TIFF and installs the published common-tools version from `scripts/ci/test_versions.env` without dependencies into that isolated runtime's tool store.
It needs no manually prepared input or package installation and runs in the ordinary complete Chromium and Firefox collections, including CI; cold package and thumbnail-reader provisioning require network access.
The test restores the original E2E Files catalog before Run and checks that the explicitly bound result retains Path semantics despite the catalog's contradictory string declaration.
After the cold TIFF journey, the same isolated managed-reader test checks automatic RGB PNG/JPEG, middle-plane OME-TIFF and directory-backed OME-Zarr previews without thumbnail API warming.
An optional `BIOIMAGEFLOW_THUMBNAIL_TIFF` can supply an already prepared matching TIFF inside the same runtime for an owned recovery attempt; it is validated and never overwritten.

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
- Selected-suite backend tests that are not marked `integration`, `serial`, `slow`, or `external`.
- Selected-suite frontend tests in the Node Vitest project.

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

`check backend` runs backend lint, every non-external backend test in the selected feature suite, and the logging-order certification.
`check frontend` runs frontend lint, type checking, the selected feature suite in every Vitest project, and the production build.
`check campaign` verifies dashboard/inventory consistency and active campaign local links offline; it does not replace Sphinx for documentation structure or the final certification.
`check docs` includes `check campaign`, then runs Sphinx with warnings treated as failures.
Run `check campaign` once for a consolidated campaign-documentation task, not after each row or sentence edit.
Run `check docs` when moving/renaming campaign files, changing documentation navigation/extensions, at a substantial documentation milestone, and at final certification; do not repeat it for routine campaign status edits.
`check browser-smoke` runs only Chromium tests tagged `@critical`, while `check browser` runs the selected feature suite in Chromium.
`check cross-browser-smoke` runs critical Chromium and Firefox tests in isolated parallel processes.
`check browser-firefox` runs the selected feature suite in Firefox.
`check browser-all` runs the selected feature suite in Chromium and Firefox in isolated parallel processes without coverage or external certification.
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
It runs the selected feature suite across backend tests (including external tests), all frontend unit projects, branch coverage, the production build, the logging-order regression, and Chromium and Firefox.
Distributed features remain opt-in even in `full`; use `scripts/test --suite all full` to include them.
Before starting the tests it installs the pinned published `bioimageflow-common-tools` package into a fresh temporary tool store.
The command fails if installation or external certification cannot run, so a successful full result never hides deselected external tests.
Chromium and Firefox run against separate temporary roots and servers in parallel.
Each browser server keeps Vite's generated dependency cache in its own temporary root, so parallel optimization cannot replace another server's cached modules.
Local browser lanes stop after the first failure by default.
`full` subsumes the selected-suite backend/frontend product checks, both browser projects, and common-tools certification; it does not run `check docs` or native/manual acceptance.
Run documentation acceptance separately when required rather than stacking already-covered product lanes before `full`.

If a late full-suite phase fails, fix and stress the exact failure first.
Successful earlier phases remain valid when subsequent edits cannot affect them; run only the scoped checks invalidated by those edits rather than restarting the full lane automatically.
Record the source revision, command, duration, and result so this reuse is explicit.
Justify reuse with unchanged relevant source, fixtures, dependencies/editable library, generated artifacts, and runtime assumptions; retain the original failed command and every skipped or unrun case alongside the newer phase results.

Coverage artifacts are written to `backend/.pytest_cache/coverage.xml`, `backend/.pytest_cache/htmlcov/`, and `frontend/test-results/coverage/`.
The transient Coverage.py database is stored under `backend/.pytest_cache/` and removed on success or failure, so the suite does not leave `backend/.coverage` behind.

The desktop suite remains headless and mocks pywebview, so even a successful full lane does not certify a packaged native window or operating-system dialogs.
The ordinary E2E server declares the environment-lifecycle tools and observation routes without an opt-in flag, because their browser tests belong to the normal collection.
Only an explicit lifecycle preparation request provisions those fixture environments and checks that their SDK distributions are published packages; server startup does not provision them.
Its cleanup stops only the two environments that fixture owns, preserving unrelated journeys' manager and shared-array lifetimes in the same browser server.
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

`distributed` is a feature marker rather than an execution-cost marker.
Keep engine-neutral, local scheduling, Direct, and Wetlands cases unmarked even when they share a file with remote cases.
Use per-case markers in mixed files; module-wide markers are appropriate only when every case tests distributed features.

## CI workflows

| Workflow | Trigger | Feature suite | Purpose |
| --- | --- | --- | --- |
| **CI** (`ci.yml`) | Push to `main`, pull request | Local | Path-selected backend/frontend quality, documentation, Chromium, and critical Firefox checks; aggregated by **Required CI**. |
| **Weekly validation** (`weekly.yml`) | Monday at 04:00 UTC, or manual dispatch | Local | Backend/frontend branch coverage, production build, complete Chromium/Firefox local collections, and separate published common-tools compatibility. |
| **Distributed tests** (`distributed.yml`) | Manual dispatch only | Distributed | Independent backend, frontend unit, Chromium, and Firefox checks; not a dependency of required CI or weekly validation. |

The optional distributed workflow can fail without changing the result of either local workflow.
Run it from Actions → Distributed tests → Run workflow, or with `gh workflow run distributed.yml --ref <branch>`.
A green local workflow certifies only its selected local checks, not distributed functionality.

PR changes outside `backend/`, `frontend/`, `docs/`, and `README.md` select all five local jobs, including changes to test infrastructure and root instructions.
Frontend changes, backend runtime changes, and browser fixtures select critical Firefox coverage.
Documentation PRs retain their Sphinx check.

Weekly backend coverage excludes `external`; its common-tools job runs only the published package certification.
Real-worker fixtures, documentation acceptance, and native/manual acceptance remain separate gates unless explicitly run through their documented commands.
The published common-tools version has one source of truth in `scripts/ci/test_versions.env`, shared by local and CI runners.
All workflows install the published backend dependencies from the lockfile and require no sibling library checkout.
