# Multiple napari environments implementation handoff

## Purpose

This document is the continuation checkpoint for the multiple napari environments feature.
It records the accepted product contract, the integrated implementation, the released library dependency, independent review outcomes, validation evidence, and the work that still remains.
It does not replace the normative specifications.
Read `PLATFORM_CONTEXT.md`, `platform_specs_napari_environments.md`, the affected v1/v2 sections, and the BioImageFlow library viewer requirements documentation before changing the implementation.

Snapshot date: 2026-09-16, second checkpoint.
The first checkpoint recorded the integrated feature before library release, before reconciliation with platform `main`, and before independent review; all three have since happened, and the exact-result metadata follow-up it preserved uncommitted is now committed and integrated.

## Source-of-truth branches and worktrees

The platform integration branch is `feature/napari-environments` in `.worktrees/napari-environments`, checked out at commit `2865cf9`.
It is reconciled with platform `main` through two clean merges: `532db4d` merged `main` `1e692ed`, and `8dc6f7c` merged `main` `58520b5`, which is the platform `main` revision at this checkpoint.
Platform `main` is untouched.
Do not implement further work directly on platform `main`.

The BioImageFlow library work is released.
The library branch `feature/napari-viewer-contract` (worktree `/Users/amasson/Travail/bioimageflow/.worktrees/napari-viewer-contract`, clean checkpoint `c0a854c`, release commit `4943915`) was merged into library `main` as `c467f501d5a5ba99dfb2d6f147109011806ec860` and published; see the release section.
Library `main` now carries the viewer contract.
Do not share virtual environments, frontend dependencies, runtime state, build output, or `.bioimageflow` directories between worktrees.

## Accepted product contract

Unchanged from the first checkpoint and still authoritative.

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
- Setting a new incompatible persistent favorite is disallowed under the normal requirements contract, enforced by the backend, not only by the frontend.
- Ordered filename rules use first-match semantics.
- Extension entries are GUI shorthand normalized to glob patterns, while advanced users may enter complete glob patterns.
- Resolution considers the structural-output favorite, author requirements, filename rules, the global default, compatibility, availability, and deterministic fallback in the order defined by the specification.
- The output control is a split button whose primary action uses the effective environment and whose menu shows all environments, compatibility status, one-time launch actions, the exclusive favorite toggle, setup, and management actions.

## Library release

The portable viewer contract is published and consumed through the frozen platform lock.

- `bioimageflow-core` `0.3.1` to `0.4.0`: new public worker-safe viewer API (`ViewerSpec`, `NapariRequirement`, `PackageRequirement`, and the `coerce_viewer_spec`, `extract_viewer_spec`, `merge_viewer_specs` helpers) plus a new `packaging` runtime dependency.
- `bioimageflow` `0.7.2` to `0.8.0`: public viewing requirements API, viewer metadata in node and workflow serialization, canonical schema version 2 with explicit v1 normalization, viewer metadata in the normalized portable graph and artifact hash, a derived requirements manifest in workflow archives, and retained run-node viewer metadata. Its core range moved to `>=0.4.0,<0.5`.
- Eight tool packages received compatibility-range-only patch bumps so that `bioimageflow` `0.8.0` and the published tool packages remain jointly installable: `bioimageflow-common-tools`, `bioimageflow-io-tools`, `bioimageflow-measurement-tools`, `bioimageflow-restoration-tools`, `bioimageflow-sairpico-tools`, and `bioimageflow-spot-tools` to `0.2.1`; `bioimageflow-segmentation-tools` and `bioimageflow-tracking-tools` to `0.3.1`. Their core floor stayed at `>=0.3.0` while the ceiling widened to `<0.5`.
- `bioimageflow-phasor-tools` was deliberately not released; it has never been published, and the release policy routes unpublished projects to a separate bootstrap path.
- Release authority: the library release policy in `docs/source/reference/releasing.md`, and publication through `.github/workflows/release.yml` with PyPI trusted publishing.
- Execution record: release commit `4943915`; pull request `Inria-SAIRPICO/bioimageflow#1`; merge commit `c467f501d5a5ba99dfb2d6f147109011806ec860`, whose tree is identical to the release commit; ten annotated tags pushed at that commit and verified to peel to it; publish workflow run `34980256529` on `main` with `mode=publish`, successful with no environment approval required.
- Independent verification: every released version answers `https://pypi.org/pypi/<project>/<version>/json`, wheel and sdist names match the locally built artifacts, the published metadata reports `bioimageflow-core>=0.4.0,<0.5` for `bioimageflow` `0.8.0` and `>=0.3.0,<0.5` for the tool packages, and a fresh resolution installs the nine downstream packages together with `bioimageflow-core==0.4.0`.

## Platform dependency boundary

The blocker recorded in the first checkpoint is resolved.

- `backend/pyproject.toml` pins `bioimageflow-core>=0.4.0,<0.5` and `bioimageflow[cluster]==0.8.0`.
- `backend/uv.lock` was relocked and resolves the published artifacts; it no longer installs the pre-viewer `0.7.2`/`0.3.1`.
- `scripts/ci/test_versions.env` pins `BIOIMAGEFLOW_COMMON_TOOLS_VERSION=0.2.1`, because `0.2.0` declares `bioimageflow-core<0.4` and cannot coexist with `bioimageflow` `0.8.0`.
- A clean isolated environment created with `uv sync --frozen --group dev` under a separate project environment installs `bioimageflow` `0.8.0` and `bioimageflow-core` `0.4.0`, from which `bioimageflow_core.ViewerSpec` imports successfully. No editable or path dependency is used anywhere in the frozen lane.
- The library worktree's diagnostic editable installation recorded in the first checkpoint has been removed from the platform environment and is not part of any completion evidence.

Ownership note: the release policy publishes from library `main` and requires the release commit to be there, so the library feature branch was merged to library `main` for the release. That is a release action, not an implementation route; further library implementation should still not be done directly on `main`.

Repository maintenance finding, outside this feature: library `main` branch protection still requires status contexts named `Fast tests (Python 3.10)`, `Fast tests (Python 3.11)`, and `Fast tests (Python 3.12)`, which the current `ci.yml` no longer produces, so pull requests report a permanently blocked merge state. The release merged with an administrator override. The protection rule should be updated to the contexts the workflow now emits.

## Implemented scope

The implemented library, backend, and frontend scope recorded in the first checkpoint is unchanged and remains accurate for commit `c17b863` and its ancestors; this document does not repeat that inventory.
The commits after the first checkpoint add or change the following.

- Retained viewer metadata is pinned to the exact result identity for direct and merged tables: each displayed structural column carries the viewer declaration captured with that exact retained result, with an explicit `captured` or `legacy_unpinned` status, and the frontend never substitutes mutable current graph or tool metadata for specialized action visibility.
- Viewer conversion from the library type to the platform wire model has one authority, `ViewerSpec.from_library`, used by the resolver, the pages router, and the projection service.
- The incompatible-favorite rule is enforced by the backend favorite toggle and set endpoints, with one shared compatibility evaluator extracted from the resolver.
- The feature specification describes delivered behaviour instead of a proposal.

Two defects that only the complete browser lane could expose were found and fixed after the first full-lane run.

- Saving a workflow whose interface output schema carried an explicit `null` viewer declaration was rejected with `422`. `OutputFieldSchema` gained `viewer: ViewerSpec | None`, so tool output metadata carries `"viewer": null`, and the canvas copied that field verbatim into the exposed output's schema; the new `WorkflowOutput.validate_schema_viewer` then treated the present key as a declaration and refused the null. An explicit null is not a declaration: `36d12f7` makes the validator erase the key on ingress so that `{"viewer": null}` and an absent key produce one serialized graph and one artifact hash, while a non-null value is still validated strictly against the library type.
- Even after the save was accepted, the unsaved-changes marker never cleared. The canvas document and the API wire document disagreed on optional viewer fields: the API carried `viewer_addition: null` on interface outputs and `viewer_additions: {}` on nodes, the canvas document omitted them, and an exposed output schema re-introduced `viewer: null`. The save coordinator then saw a phantom newer edit, kept the canvas dirty, and never reached the clean state. `887e326` makes the canvas serialize the same optional fields and stops an exposed output schema from copying an absent viewer declaration, so client and server agree on one spelling of the document.

Both were reproduced deterministically on both browser engines and confirmed as feature-caused, not environmental.

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
61aa96b Document napari implementation handoff
1799397 Pin retained viewer metadata to the exact result identity
532db4d Merge branch 'main' into feature/napari-environments
4931b20 Consume the released viewer contract from the frozen lock
b7da7f4 Describe the delivered napari environments specification
3a79ded Enforce the incompatible favorite rule in the napari backend
5f1dcc2 Add the rendered viewer addition to the recursive copy e2e expectation
36d12f7 Give a workflow output without a viewer declaration one identity
887e326 Serialize the viewer fields the canvas graph document omits
78c6a1b Record the released, reviewed, and certified napari environment checkpoint
8dc6f7c Merge branch 'main' into feature/napari-environments
2865cf9 Assert node data table columns only after the panel settles
```

Platform `main` at this checkpoint is `58520b5`.

## Worktree disposition

- `.worktrees/napari-environments` is the integration authority and holds the branch checkpoint.
- `.worktrees/napari-output-chooser` on branch `task/napari-output-chooser` at commit `3577093` is now clean. Its commit was cherry-picked into the integration branch as `1799397`, so its content is integrated, but the branch itself was never merged. Keep the worktree until the integration branch is merged or the branch is explicitly disposed of.
- `.worktrees/napari-frontend` was audited: every remaining unstaged change is either already integrated or superseded by the dedicated `NapariOutputChooser.vue` authority, and no salvageable behaviour was identified. It can be discarded once the integration branch is merged.
- `.worktrees/napari-env-registry`, `.worktrees/napari-launcher`, `.worktrees/napari-managed`, `.worktrees/napari-readiness`, `.worktrees/napari-resolver`, and `.worktrees/napari-spec` were clean at the first checkpoint.
- The detached `.worktrees/napari-review` worktree is not an integration authority.
- The historical test-evidence documents under `docs/developer/platform-test-*.md` intentionally keep the library versions that were current when those runs happened; they are records, not live status, and must not be rewritten.

## Independent review outcomes

- Merge semantics audit of the reconciled branch: the schema-v2 mandate, result-identity pinning, and multi-environment UI authority survived the merge intact; the two flagged items (a schema-version-1 golden fixture and the legacy singleton compatibility paths) were adjudicated as intentional by design, and a third (the campaign manifest's own document `schema_version`) is a distinct field unrelated to the graph schema. No must-fix item.
- Architecture and reliability review of portability, schema migration, result identity, preference lifecycle, concurrency, package-compatibility semantics, and frontend/backend contract alignment: correct, with one medium finding that the backend favorite endpoint did not enforce the specification's incompatible-favorite rule. Fixed by `3a79ded`.
- Security and mode-gate review of desktop gating, path handling, process execution, managed-environment ownership, package installation, and credential leakage: no release-blocking finding. Three low-severity hardening items were recorded for the implemented desktop, single-user, same-account threat model.
  1. Managed-environment viewers started through Wetlands inherit the backend process's ambient environment, while external registered environments are started with an explicit whitelist. Third-party packages requested into a managed environment therefore receive ambient environment variables such as proxy or token settings.
  2. `GET /api/v1/settings` serves the registry roots, interpreter paths, launch argv, and distribution inventory without the desktop-only gate that the dedicated napari environment routes enforce.
  3. The local API accepts unauthenticated, origin-open requests, so a page the user visits could drive destructive managed-environment routes. This is inherited platform behaviour, not introduced by this feature.
- Documentation consistency audit: the feature specification and the handoff carried proposal framing and pre-release version claims, while the user documentation, `platform_specs_v1.md`, `platform_specs_v2.md`, and `PLATFORM_CONTEXT.md` were already accurate. Fixed by `b7da7f4`.

## Validation evidence

### BioImageFlow library at the release commit `4943915`

| Command or check | Result | Duration |
| --- | --- | --- |
| `uv run pytest` | 2,306 passed, 37 skipped, 12 warnings | 84.47s |
| `uv run ruff check .` | Passed | 0.12s |
| `uv run pyright` | 0 errors, 0 warnings | 7.89s |
| `uv run sphinx-build -W --keep-going docs/source docs/_build/html` | Succeeded | 35.68s |
| Metadata, release-tooling, tagging, artifact, and development-workflow tests | 83 passed | 7.79s |
| `scripts/check_file_sizes.py`, `scripts/check_import_boundaries.py` | Passed | <0.5s |
| `uv run python docs/generate_tool_package_docs.py --check` | Passed | 0.10s |
| `uv lock` | Resolved 127 packages, 11 workspace members reversioned | 0.39s |
| Release packaging and publication | Ten projects built, validated, and published; PyPI confirmed per project | Workflow duration recorded in run `34980256529` |

### Platform backend

| Revision and command | Result | Duration |
| --- | --- | --- |
| `532db4d`, focused feature families after the exact-result follow-up and the frozen-lock update | 168 passed | 7.96s |
| `3a79ded`, napari environments router, resolver, and readiness families | 18 passed | 1.31s |
| `3a79ded`, broad napari backend family including launcher and managed lifecycle | 149 passed | 3.74s |
| `5f1dcc2`, `scripts/test full`, backend with branch coverage and external common-tools `0.2.1` | 1,722 passed | 118s |
| `5f1dcc2`, logging-order certification phase | 7 passed | 2s |

The backend suite now runs against the published `bioimageflow` `0.8.0` and `bioimageflow-core` `0.4.0` through the frozen lock; the first checkpoint's blocker was that this was impossible before publication.

### Platform frontend

| Revision and command | Result | Duration |
| --- | --- | --- |
| `532db4d`, `scripts/test check frontend` | Lint, type check, 1,324 unit tests, and production build passed | 20s |
| `5f1dcc2`, `scripts/test full`, frontend unit tests with branch coverage | 134 files, 1,324 tests passed | 25s |
| `5f1dcc2`, frontend lint, type check, production build phases | Passed | 9s, 0s, 6s |
| `3a79ded`, `scripts/test focus e2e tests/e2e/napari-output-chooser.spec.ts` | Chromium and Firefox passed | 6.1s, 6.6s |
| `5f1dcc2`, `scripts/test focus e2e tests/e2e/agent-draft-sync.spec.ts` | Chromium 4 passed, Firefox 4 passed | 10.3s, 15.1s |

### Platform documentation

| Revision and command | Result | Duration |
| --- | --- | --- |
| `4931b20`, `scripts/test check docs` | Passed | 2s |
| `b7da7f4`, `scripts/test check docs` | Passed | 2s |

### Browser lane

Getting both browser projects to a complete green run took three attempts, and the two intermediate failures were real.

The first `scripts/test full`, on revision `532db4d`/`4931b20`, aborted both projects on `tests/e2e/agent-draft-sync.spec.ts`, a deep-equality mismatch caused by the feature's explicit `viewer_addition: null` in a copied embedded graph; `5f1dcc2` updated the stale expectation after establishing that the platform's wire convention is to render optional fields as explicit `null`.
The second run, on `5f1dcc2`, cleared that blocker and executed 76 of 85 Chromium tests and 48 of 85 Firefox tests before each project aborted at its first remaining failure, `tests/e2e/workflow-interface.spec.ts:308`. Isolated reproduction showed that failure to be deterministic on both engines and feature-caused: saving an interface output whose schema carried `"viewer": null` was rejected `422`, and behind it the canvas and API documents disagreed on their viewer-field spelling so the unsaved-changes marker never cleared. A separate Firefox `tests/e2e/hot-reload.spec.ts` failure was run six times in isolation without reproducing and did not recur, so it was recorded as load flakiness rather than a defect.
The third run, on `887e326` after `36d12f7` and `887e326`, completed both projects with no failures and no flakes.

| Revision and command | Result | Duration |
| --- | --- | --- |
| `887e326`, `scripts/test full`, Chromium project | 85 passed, 0 failed, 0 flaky, 0 not run | 277s |
| `887e326`, `scripts/test full`, Firefox project | 85 passed, 0 failed, 0 flaky, 0 not run | 414s |
| `887e326`, `scripts/test full`, whole lane | Exit 0, every phase passed | 645s |

### Complete lane on the final revision `887e326`

| Phase | Result | Duration |
| --- | --- | --- |
| Backend source import preflight | Passed | 2s |
| Install `bioimageflow-common-tools` `0.2.1` | Passed | 0s |
| Backend and frontend lint | Passed | 0s, 9s |
| Frontend type check and production build | Passed | 1s, 6s |
| Frontend unit tests with branch coverage | 134 files, 1,326 tests passed | 35s |
| Backend full tests with branch coverage | 1,724 passed, 0 failed | 218s |
| Backend logging-order certification | 7 passed | 11s |
| Chromium end-to-end | 85 passed | 277s |
| Firefox end-to-end | 85 passed | 414s |

### Post-merge state at `8dc6f7c`

After the second reconciliation, every phase of `scripts/test full` except the browser projects passes again on the merged revision: backend 1,732 passed, 134 frontend files and 1,327 tests, lint, type check, production build, and the logging-order certification. Both browser projects reported 89 passed, 1 flaky, and 0 did-not-run; the lane's non-zero exit came only from the CI-mode `failOnFlakyTests` setting, which counts a retried pass as a failure. No test failed.

Both flakes are inherited from platform `main` and are not this feature's.
- Chromium `nested-execution.spec.ts` asserted table headers with a single non-polling `evaluateAll` immediately after a request wait, so it could read the previous node's columns; the captured trace shows the response body carrying both expected columns, proving the product correct. The spec and that helper were authored on `main` (`fd96f8f`). `2865cf9` makes that one assertion await the settled panel state while keeping the exact expected header list and the deep equality; the formerly racing test then passed five consecutive runs under CI semantics. That commit is test-only and self-contained, so the platform test campaign can drop it if it prefers to own the fix.
- Firefox `everyday-node-editing.spec.ts` failed in its `beforeEach` because the application auto-opened a workflow created by an earlier spec in the same run. `frontend/playwright.config.ts` gives every test a fresh browser context, but one backend and one E2E root persist across the run and the pre-existing startup resolver reopens the last workflow. The same symptom appears in several `main`-authored specs, so it is a harness isolation artifact rather than a feature defect, and it is left to the platform test campaign.

This branch's own focused checks on the merged revision are the ones that matter for this feature: the two exact workflow-interface selectors pass on Chromium and Firefox, the formerly racing result-table test passes five consecutive runs, and the feature's own browser coverage (`napari-output-chooser.spec.ts`) passes on both projects.

## Remaining work

1. Complete native desktop certification. A packaged native window, operating-system dialogs, real napari launches against a real environment, and the cross-platform matrix remain outside every automated lane, including `scripts/test full`, which mocks pywebview. The earlier local attempt did not leave a reliable completion artifact and is not acceptance evidence. This obligation is manual and must be reported honestly rather than inferred from green lanes.
2. Decide whether to act on the three recorded low-severity security hardening items. None is release-blocking for the implemented desktop, single-user, same-account threat model.
3. Update library `main` branch protection so the required status contexts match the contexts `ci.yml` actually emits.
4. Merge or explicitly dispose of the remaining napari task worktrees after the integration branch itself is merged.
5. The two browser flakes recorded above are inherited from platform `main` and belong to the platform test campaign, not to this feature. This feature's verification scope is its own changed surface: the two workflow-interface selectors, the formerly racing result-table assertion, the chooser spec, and the focused backend and frontend families named in the validation evidence.

## Completion definition

The feature is not complete merely because mocked backend tests or headless frontend tests pass.
Completion requires the complete browser certification on both projects, native desktop certification by a human on a real machine, and no unresolved material review finding.
As of this checkpoint the implemented contract, the released library consumption through the frozen lock, the reconciled platform branch, the complete Chromium and Firefox certification at `887e326`, independent architecture and security review, and documentation consistency are all in place; the only outstanding obligation for this feature is native desktop certification, followed by the repository maintenance and hardening decisions listed above.
The merged revision `8dc6f7c` repeats every non-browser phase successfully and shows no feature failure in either browser project; the two flakes it does show are inherited from platform `main` and are owned by the platform test campaign.