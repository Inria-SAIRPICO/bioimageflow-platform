# Multiple napari environments implementation handoff

## Purpose

This document is the continuation checkpoint for the multiple napari environments feature.
It records the accepted product contract, integrated implementation, preserved work in progress, known blockers, validation evidence, and the recommended continuation plan.
It does not replace the normative specifications.
Read `PLATFORM_CONTEXT.md`, `platform_specs_napari_environments.md`, the affected v1/v2 sections, and the BioImageFlow library viewer requirements documentation before changing the implementation.

Snapshot date: 2026-09-15.

## Source-of-truth branches and worktrees

The platform integration branch is `feature/napari-environments` in `.worktrees/napari-environments`.
Its clean checkpoint is `c17b863c196e72a6954a0687a6cdac2368e37c59`.
It was forked from platform commit `b10fe936334d1377ceb1690ab81b9f488c3c5b5d`.
Platform `main` was observed at `1e692ed02289d16760d8c2e131bb1b9b53e9c791` when this handoff was written, so later integration with current `main` remains required.

The BioImageFlow library integration branch is `feature/napari-viewer-contract` in `/Users/amasson/Travail/bioimageflow/.worktrees/napari-viewer-contract`.
Its clean checkpoint is `c0a854c` based on library `main` commit `659acda`.

Neither feature branch has been merged into `main`.
Do not implement the continuation directly on either repository's `main` branch.
Do not share virtual environments, frontend dependencies, runtime state, build output, or `.bioimageflow` directories between worktrees.

## Accepted product contract

- Users manage multiple named napari environments because plugin sets may be mutually incompatible.
- Names are user-facing labels and are useful even though portable workflows never refer to those names or local environment IDs.
- An environment is either attached external state or platform-managed state.
- External Conda and virtual environments may be registered, probed, renamed, located, launched, and forgotten, but the platform does not mutate their packages.
- Platform-managed environments may be created from strict recipes, copied before package changes, inspected, launched, cancelled or retried during setup, and deleted only when ownership is proven.
- The default managed recipe uses Python 3.12 from Conda and installs napari 0.9.1, PyQt6, and requested plugins from PyPI.
- The older smoke recipe uses napari 0.6.6 and PyQt5.
- Tool developers declare portable viewer requirements on outputs, including required or recommended Python distributions with PEP 440 constraints, an optional napari constraint, and an optional reader identifier.
- Compatibility means only that required installed Python distributions satisfy their declared constraints.
- Compatibility does not depend on npe1/npe2 manifest discovery, plugin enabled state, or proof that a reader will successfully open a particular artifact.
- Reader identifiers remain explicit launch instructions, and actual reader failures are reported after dispatch.
- A workflow archive contains portable viewer requirements and never contains local environment IDs, paths, credentials, or user-defined environment names.
- Workflow import and passive readiness checks report missing requirements without installing or launching anything implicitly.
- One exclusive, toggleable favorite environment may be stored for each structural output identity.
- That favorite applies to every row and all future results for the same structural output.
- There are no row-level favorites, row exceptions, or favorite-scope selectors.
- Choosing an environment from the output menu is a one-time launch and does not persist a preference.
- Selecting an empty star sets or replaces the favorite, and selecting the filled star unsets it.
- Ordered filename rules use first-match semantics.
- Extension entries are GUI shorthand normalized to glob patterns, while advanced users may enter complete glob patterns.
- Resolution considers the structural-output favorite, author requirements, filename rules, the global default, compatibility, availability, and deterministic fallback in the order defined by the specification.
- The output control is a split button whose primary action uses the effective environment and whose menu shows all environments, compatibility status, one-time launch actions, the exclusive favorite toggle, setup, and management actions.

## Implemented library scope

Library commit `c0a854c` adds the portable contract required by the platform.

- `bioimageflow-core` defines strict `ViewerSpec`, napari requirements, normalized package names, required and recommended distributions, version specifiers, and optional reader instructions without importing napari.
- Processing and DataFrame tools may annotate outputs with viewer requirements.
- Recursive workflow serialization carries viewer metadata through nested and published outputs.
- Canonical workflow documents use schema version 2, while schema-version-1 inputs are explicitly normalized.
- Viewer metadata participates in the normalized portable graph and artifact hash.
- Workflow archives include a derived requirements manifest without local environment references.
- Retained run-node output metadata records the effective viewer declarations alongside immutable result identities.
- Public library APIs expose retained viewer metadata to the platform without requiring access to private storage internals.
- Viewer metadata is provenance and viewing behavior, not a processing dependency or cache-key input beyond its presence in the canonical workflow definition.

The library package versions remain `bioimageflow==0.7.2` and `bioimageflow-core==0.3.1` on this branch.
A release/versioning decision is therefore still required before the platform can consume the new APIs through its frozen production lock.

## Implemented platform backend scope

The platform branch contains the following integrated backend work.

- A settings-backed, revisioned registry stores named environments, ownership, immutable launch context, inventory, state, and managed-recipe identity.
- External Conda and virtual environments can be registered through typed desktop-only APIs.
- Inventory probes run in bounded subprocesses and use `importlib.metadata` distribution metadata rather than importing napari or discovering plugin manifests.
- The former singleton napari environment can be adopted into the registry.
- UUID-keyed launcher processes and locks permit independent environment lifecycle and concurrent viewers.
- Registered launch arguments are frozen and dispatched according to the persisted interpreter, Conda, or managed strategy.
- Each environment receives an isolated napari settings file.
- Open commands carry an optional explicit reader and acknowledge only after the Qt-thread operation completes.
- Ambiguous open outcomes are not replayed automatically.
- Lifecycle events and WebSocket state are attributed to the environment ID rather than a singleton `napari` key.
- A dedicated launch route starts an empty viewer without issuing an empty open request.
- Managed creation, copy, retry, cancellation, restart reconciliation, and ownership-proven removal use public Wetlands operations where available.
- Managed recipes install only Python through Conda and install napari, Qt, and requested distributions from PyPI.
- Ordered filename rules, extension shortcuts, the global default, rule previews, and catch-all validation are exposed through typed APIs.
- Graph schema-v2 migration covers saved workflow documents, durable root drafts, nested snapshots, normalized hashes, and forward-recoverable migration state.
- Result APIs expose immutable run, node, result, and record identity needed to address an exact retained artifact.
- The resolver evaluates package-only compatibility for exact results and portable manifests.
- The resolver returns the exact server-derived persistent preference key so the frontend does not reconstruct it.
- A separate revisioned `viewer-preferences.json` store owns exclusive structural-output favorites.
- Favorite lifecycle is coordinated with workflow move, delete, identity generation, and nested-session apply behavior.
- Passive readiness evaluates portable output requirements, groups identical normalized requirement sets, preserves unknown or incomplete declarations, and can prefill managed setup without side effects.
- Desktop-only mode gates protect local filesystem and process operations from webapp deployment.

The legacy open, status, and shutdown routes without an environment ID remain temporarily available for compatibility.

## Implemented platform frontend and documentation scope

Platform commits `6111f84`, `9a1e904`, `0fe9974`, and `c17b863` add the integrated frontend and documentation increments.

- Image Viewers settings provides environment listing, registration, probing, locating, renaming, forgetting, and empty launch.
- Managed environment controls cover default, legacy, and advanced creation, operation polling, deduplication, progress, retry, cancellation, copying, and deletion.
- Settings exposes the global default and ordered file-opening rules with extension shortcuts, advanced glob patterns, reordering, previews, and a catch-all warning.
- Installing unverified requested packages requires explicit confirmation.
- Workflow import readiness is non-blocking and can prefill environment creation from a normalized requirement group.
- The passive readiness report displays per-output coverage and setup state and refreshes on relevant workflow, environment, and tool lifecycle events.
- The readiness UI explicitly says that plugin active/enabled state is unavailable instead of inferring it.
- Direct and merged result tables propagate exact result identity to image cells.
- The output split button resolves and opens the effective environment.
- The chooser lists compatible, incompatible, unknown, and unavailable candidates with package-only explanations.
- The chooser supports one-time environment selection, replace-layers dispatch, explicit try-anyway behavior, environment management, and requirement-prefilled setup.
- The chooser implements one exclusive toggleable favorite for the structural output across all rows.
- Generated OpenAPI frontend types were updated for schema-v2 graphs and the new napari APIs.
- User guidance, the napari feature specification, affected v1/v2 contracts, and `PLATFORM_CONTEXT.md` describe the implemented behavior and remaining certification limit.

## Integrated platform commit sequence

The commits after platform base `b10fe936` are listed oldest first.

```text
a82c056 docs: finalize napari environment specification
91a5bfb Implement napari environment registry foundation
dd92ede Clarify napari favorite preference storage
74326f6 Implement per-environment napari lifecycle
d97d68d Implement viewer provenance and resolution contracts
75669cd Isolate napari lifespan migration test
8fbf145 Add managed napari operation contracts
ff8b77a Complete viewer migration and favorite lifecycle
fb47db3 Implement managed napari lifecycle
38aba49 Tighten viewer backend type contracts
2c19e2d Expose resolved viewer preference identity
9b07144 Add passive napari viewing readiness
28b17f0 Add explicit empty viewer launch
6111f84 Add napari environment preferences UI
9a1e904 Add napari result environment chooser
0fe9974 Add passive viewing requirements report
c17b863 Document napari environment workflows
```

## Preserved uncommitted exact-result metadata follow-up

The worktree `.worktrees/napari-output-chooser` on branch `task/napari-output-chooser` is intentionally dirty at base commit `a19aea6`.
Do not discard, reset, rebase, or remove this worktree before reviewing and preserving its changes.

This follow-up fixes the main known functional defect at `c17b863`.
The current integrated frontend can decide specialized non-image napari action visibility from mutable current resolved-output metadata rather than metadata captured with the exact retained result.
The follow-up makes direct and merged table responses carry the viewer declaration captured with the exact result and an explicit `captured` or `legacy_unpinned` status.

Its uncommitted files are:

```text
backend/src/bioimageflow_server/models/data_table.py
backend/src/bioimageflow_server/models/nodes.py
backend/src/bioimageflow_server/routers/nodes.py
backend/src/bioimageflow_server/services/data_table_projection.py
backend/src/bioimageflow_server/services/result_store.py
backend/tests/test_routers/test_nodes.py
backend/tests/test_services/test_data_table_projection.py
frontend/src/api/types.ts
frontend/src/components/panels/ImageCell.vue
frontend/src/components/panels/MergedDataTable.vue
frontend/src/components/panels/NodeDataTable.vue
frontend/src/components/panels/__tests__/ImageCell.test.ts
frontend/src/stores/dataTable.ts
frontend/tests/e2e/napari-output-chooser.spec.ts
platform_specs_napari_environments.md
platform_specs_v2.md
```

The diff contained 221 added and 39 removed lines when this handoff was written.
It has not been validated or committed.

## Other worker worktree state

The `.worktrees/napari-frontend` worktree is at task commit `9bcd384` and remains dirty.
Its committed Settings and readiness changes are already integrated as `6111f84` and `0fe9974`.
Its remaining unstaged chooser, canvas, data-table, fixture, and E2E changes overlap an earlier abandoned implementation and are not the integration authority.
Inspect them before discarding the worktree, but do not merge them wholesale over the dedicated `NapariOutputChooser.vue` implementation.

The other napari task worktrees were clean when this handoff was written:

```text
.worktrees/napari-env-registry
.worktrees/napari-launcher
.worktrees/napari-managed
.worktrees/napari-readiness
.worktrees/napari-resolver
.worktrees/napari-spec
```

The detached `.worktrees/napari-review` worktree was at platform commit `28b17f0` and is not the current integration authority.

## Dependency and release blocker

The platform production dependency still declares `bioimageflow[cluster]==0.7.2` and `bioimageflow-core>=0.3.1,<0.4` in `backend/pyproject.toml`.
The frozen `backend/uv.lock` therefore installs published BioImageFlow 0.7.2 and core 0.3.1, which do not contain `ViewerSpec` and the new schema/viewer APIs.
Consequently, an authoritative `scripts/test` backend or browser lane cannot collect the feature branch from the frozen lock.

Do not solve this with a permanent local path dependency or by claiming editable-install results as a frozen-lock pass.
Choose library release versions according to the BioImageFlow release policy, update both library packages consistently, publish only with explicit release authority, then update the platform dependency constraints and frozen lock to those released artifacts.
Until publication is authorized and completed, editable local installation may be used only for diagnostic cross-repository testing and must be reported as such.

## Validation evidence

### BioImageFlow library at `c0a854c`

| Command or check | Result | Duration |
| --- | --- | --- |
| `uv run pytest` | 2,306 passed, 37 skipped, 12 warnings | 103.78s |
| Focused viewer, archive, and retained-result tests | 79 passed | 18.76s |
| `uv run ruff check .` | Passed | Not retained |
| `uv run pyright` | 0 errors and 0 warnings | Not retained |
| File-size and import-boundary guardrails | Passed | Not retained |
| `uv run sphinx-build -W --keep-going docs/source docs/_build/html` | Passed | Not retained |

### Platform backend

| Revision and command | Result | Duration |
| --- | --- | --- |
| Backend feature revision through `28b17f0`, authoritative `scripts/test focus backend ...` | Failed during collection because the frozen published library lacks the new viewer APIs | 2s |
| Backend feature revision through `28b17f0`, relevant direct pytest families after diagnostic editable installation of the library feature | 148 passed | 3.31s |

The editable-library result is useful implementation evidence but is not an authoritative frozen-lock platform completion check.

### Platform frontend and docs

| Revision and command | Result | Duration |
| --- | --- | --- |
| Integrated primary `9a1e904`, `bun run type-check` | Passed | Not retained |
| Integrated primary `9a1e904`, focused chooser/component/store tests | 120 passed | 7.81s test time, 9s wrapper |
| Chooser worker `a19aea6`, focused Chromium E2E with all napari endpoints intercepted | 1 passed | Approximately 7s |
| Chooser worker `a19aea6`, frontend completion check | Lint, typecheck, 1,302 tests, and production build passed | Not retained |
| Readiness worker `9bcd384`, focused tests | 102 passed | 7s |
| Readiness worker `9bcd384`, `scripts/test check frontend` | Lint, typecheck, 1,319 tests, and production build passed | 17s |
| Browser lane | 3 passed, 1 failed, 80 not run; failure occurred before chooser coverage because published BioImageFlow 0.7.2 rejects schema-v2 export | Not retained |
| Integrated primary `c17b863`, `scripts/test check docs` | Passed after the initial sandbox dependency-access failure was rerun with approved access | 1s successful run; 3s blocked run |

No clean-primary full frontend completion check was run after `0fe9974` was integrated.
The exact-result metadata follow-up has not been validated.
Native desktop behavior remains an explicit manual certification obligation.

## Recommended continuation orchestration

Use one GPT-5.6 Sol high master agent to retain the global contract, integration sequence, dependency boundary, and validation record.
Keep the four-agent concurrency limit.
Give at most two GPT-5.6 Sol medium workers bounded implementation or test tasks in separate worktrees.
Reserve the remaining slot for a GPT-6 Astra high architecture/reliability review after the implementation and frozen dependency integration are coherent.
The master should integrate commits, resolve conflicts, run clean checks, update this handoff/specification status, and make all completion claims.

Suggested task split:

1. Assign one worker to preserve and finish the dirty `.worktrees/napari-output-chooser` exact-result metadata follow-up.
2. Assign a second worker to audit library versioning/release requirements and prepare the platform dependency/lock update without publishing anything unless explicitly authorized.
3. Have the master review and integrate the exact-result metadata commit into `feature/napari-environments`.
4. After released library artifacts exist, update the platform dependency pins and frozen lock and validate from a clean isolated environment.
5. Reconcile `feature/napari-environments` with the current platform `main`, preserving unrelated campaign work and resolving schema-v2/frontend conflicts deliberately.
6. Run focused backend and frontend tests for any conflict resolution, then the clean scoped checks required by `docs/testing.md`.
7. Run the chooser E2E with intercepted viewer endpoints before any broader browser lane.
8. Ask the GPT-6 Astra high reviewer to inspect portability, schema migration, result identity, preference lifecycle, concurrency, security/mode gates, package compatibility semantics, and frontend/backend contract alignment.
9. Resolve every material reviewer finding and rerun the affected focused checks.
10. Run `scripts/test check app`, `scripts/test check docs`, and finally `scripts/test full` because this is a large cross-stack, schema, package-loading, and external-compatibility change.
11. Record exact commands, results, durations, revisions, skips, and external/manual limits in the final handoff.
12. Commit only feature changes, leave both `main` branches untouched until review, and clean merged worktrees only after their branches are actually merged.

## Detailed continuation steps

### 1. Resume the exact-result metadata follow-up

- Start in `.worktrees/napari-output-chooser` without changing its base or cleaning its working tree.
- Review every existing diff against `a19aea6` and against current integration `c17b863` before editing.
- Preserve the retained-result contract: viewer metadata comes from the exact immutable result identity, not the current graph or latest row offset.
- Ensure legacy results without captured metadata are explicitly reported as `legacy_unpinned` and never presented as authoritatively captured.
- Ensure explicit viewer declarations can expose the napari action for non-thumbnail path, directory, points, or tracks outputs.
- Regenerate OpenAPI types from the backend model rather than maintaining handwritten copies.
- Run exact backend tests, exact frontend tests, and the intercepted chooser E2E.
- Commit the coherent follow-up on `task/napari-output-chooser`, then cherry-pick or otherwise integrate only that commit into `feature/napari-environments`.

### 2. Resolve library consumption

- Review BioImageFlow release/versioning instructions in the library repository.
- Select compatible new versions for `bioimageflow` and `bioimageflow-core`; do not reuse the already published 0.7.2/0.3.1 versions.
- Update library metadata, changelog/release documentation, and locks as required by that repository.
- Re-run the full library suite and documentation checks after version changes.
- Publish only if the user explicitly authorizes a release.
- Once artifacts are available from the production package source, update platform `backend/pyproject.toml` and `backend/uv.lock` and verify that a fresh `uv sync --frozen` installs them.

### 3. Integrate current platform main

- Record the new `main` revision and compare it with merge base `b10fe936`.
- Preserve unrelated test-campaign changes.
- Pay particular attention to generated OpenAPI types, graph schema construction sites, data-table models, result identity, Settings, ImageCell, workflow import/export, and test fixtures.
- Do not resolve schema-version conflicts by accepting version 1 or by adding silent fallback behavior.
- Re-run the exact affected tests after each conflict cluster before broader checks.

### 4. Final verification

- Verify named external and managed registry CRUD, probe bounds, mode gates, and revision conflicts.
- Verify independent per-environment launch state and WebSocket attribution without relying on a singleton pending flag.
- Verify ordered first-match filename rules, extension normalization, advanced globs, catch-all warnings, and preview behavior.
- Verify resolution precedence and package-only compatibility for compatible, incompatible, unknown, unavailable, and try-anyway cases.
- Verify one exclusive toggleable favorite per structural output identity across all rows and future results.
- Verify favorite remapping on workflow moves, clearing on deletion, identity-generation isolation, and nested-session apply semantics.
- Verify workflow export/import portability, no local environment references, missing requirement warnings, and setup prefill.
- Verify exact retained-result identity and captured viewer metadata for direct and merged tables, including legacy unpinned results.
- Verify webapp rejection for local environment, filesystem, process, and viewer-launch operations.
- Verify managed creation/copy/removal ownership, cancellation, restart reconciliation, and package validation.
- Verify user documentation and all affected specifications match the final implementation.
- Complete native desktop checks separately and report any unsupported platform matrix honestly.

## Completion definition

The feature is not complete merely because mocked backend tests or headless frontend tests pass.
Completion requires the exact-result metadata fix, released library consumption through the frozen platform lock, clean cross-stack checks on the reconciled platform branch, independent architecture review, documentation consistency, and an explicit record of native/manual certification status.
