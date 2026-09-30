---
orphan: true
---

Historical record superseded by the [new campaign](../platform-test-plan.md) on 2026-09-30.
Its next actions and execution instructions are retained for audit only.

# Platform test campaign evidence

The completed Tier 1A–1B runs, revisions, durations, limitations, and release history are retained in the [dated evidence archive](../archive/platform-test-evidence-through-tier-1b.md).
Do not read that archive during an ordinary restart; use the [current checkpoint](../platform-test-progress.md), [dashboard](../platform-test-dashboard.md), and only the feature's relevant inventory row.
Open the archive only to audit a specific historical claim or invalidated check.

Append concise evidence for the current task here: exact command and selector, source revision, outcome and duration, skips or unrun cases, and any limitation.
At the next major milestone, move completed entries to a dated archive and leave this file short.

## Current-code inventory reconciliation — 2026-09-24

A read-only change scan through `15c5cc7` found ten newly tracked in-scope obligations: overall execution progress/setup, confirmed workflow-format migration, Image Viewers settings, Napari result chooser/favorites, Manage Tools environment controls, imported-graph layout, corrupt-cache recovery, stale processing-environment rebuild, Logger copying, and previously omitted import-viewing guidance.
The prior 241/456 overall and 219/219 primary-GUI counts described historical evidence; the expanded dashboard is 241/500 overall and 219/224 primary GUI, with no current-revision application or browser certificate implied.
`scripts/test check campaign` passed on the campaign-documentation diff; no product regression or new feature assertion was run for this inventory reconciliation.

## RT-EXE-016 real-worker progress increment — integrated `3fb04d1`

Task commits `6a3c5df` and `3fb04d1` add opt-in task progress to the held-worker fixture, exact metadata/default/direct-call regressions, and live/retained banner assertions in the existing cancellation GUI journey.
At patch-equivalent task revision, exact Chromium cancellation passed in 39s and Firefox in 38s; the unchanged default-consumer failure/rerun Chromium selector passed in 33s; `scripts/test focus backend tests/test_integration/test_held_worker_fixture.py` passed 3/3 in 2s with localhost access, and targeted Ruff passed.
`scripts/test check frontend` passed in 26s with 1,313 units plus lint/type/build; `scripts/test check cross-browser-smoke` passed 18/18 Chromium and 18/18 Firefox in 112s; `scripts/test check campaign` passed in under 1s at 244/500 overall and 222/224 primary GUI.
An earlier `scripts/test check backend` attempt on intermediate task content ended red in 135s: 1,792 passed, one obsolete fixture metadata assertion failed, two tests could not bind localhost in the restricted sandbox, and nine external tests were deselected. The corrected exact fixture selection passed with local sockets permitted; the full backend lane was not repeated, so it is not claimed as passed.
Sol/high planning and independent Astra/high review approved the opt-in fixture contract; no production refactor was needed. RT-EXE-016.F/P/B are verified; setup-phase and selected/cached plan success plus visible stale-event refusal remain S/R gaps. No full suite or external certification ran.

## Current-revision nested-result and image-viewer spot checks — `9c4a435`

`scripts/test focus e2e tests/e2e/nested-execution.spec.ts:414 --project=chromium` passed 1/1 in 18s, and the same exact selector in Firefox passed 1/1 in 35s.
`scripts/test focus e2e tests/e2e/avivator.spec.ts --project=chromium --grep 'opens a converted OME-TIFF image inside the Dockview panel'` passed 1/1 in 21s, and its Firefox counterpart passed 1/1 in 27s.
All four runs used the current source revision, had no retries or skips, and used local-server access; they recheck WF-REC-012 and RT-RES-007 GUI success/identity paths, not every historical boundary or a complete browser lane.

## Current local execution selector rechecks — `71b82da`

`scripts/test focus backend tests/test_integration/test_real_execution.py::test_execution_manager_runs_real_dataframe_workflow_and_updates_cache` passed 1/1 in 44s, and `::test_api_runs_real_dataframe_workflow_and_reuses_cache` passed 1/1 in 5s.
`scripts/test focus backend tests/test_services/test_graph_builder.py::test_built_workflow_uses_wetlands` passed 1/1 in 6s.
`scripts/test focus backend tests/test_routers/test_execution_router.py -k 'run_selected_uses_accepted_draft_graph or run_rejects_stale_draft_before_execution_side_effects'` passed 2/2 in 6s, with 45 unrelated tests deselected by the exact selection.
These source-current selectors check Direct computation/cache, automatic worker routing, and accepted-draft/stale-revision boundaries; the real-worker GUI/PID and cancellation evidence is separately recorded at `6a3c5df`, and no broad backend or browser lane was run for this read-only revalidation.

## RT-EXE-016 progress and setup closure — integrated `0be3417` and `dfdb727`

The final exact setup selector, `scripts/test focus e2e --project=chromium --project=firefox --grep 'Execution panel shows local setup text' tests/e2e/execution.spec.ts`, passed 2/2 in 38s at task source `18aa760`.
The selected-branch Chromium selector passed 1/1 in 91s; the held-worker and earlier setup selection passed 2/2 in 59s in Chromium, and three focused Firefox cases passed 3/3 in 81s. The first controlled-setup Chromium attempt failed because the panel remained workflow-scoped; selecting Workspace fixed that in the exact selector, and the later detail-refresh version passed both browsers.
`scripts/test check frontend` passed lint, types, build, and 1,313 units in 23s. `scripts/test check cross-browser-smoke` passed 18/18 Chromium and 18/18 Firefox in 146s before the final setup-only test adjustment; no broad browser or full suite was run after that adjustment.
The setup test uses a typed local retained-run response to verify the Execution panel's installation message without a numeric bar and its detail-refresh transition to 33%; it does not install a real environment. The injected WebSocket events prove visible refusal of stale or malformed execution context while a real worker is held, then delivery of a valid same-context event; arbitrary invalid numeric progress is not claimed.
The focused selectors had no retries or skips. Unrelated tests were outside those selections, and external certification was not run. `scripts/test check campaign` was initially red only from the intentionally unedited aggregate tally, then passed after integration reconciliation.

## Headed primary GUI journey — `b41e41d`

`scripts/test focus e2e tests/e2e/canvas-interactions.spec.ts --project=chromium --headed --grep 'builds, runs, inspects, saves, and reopens a real workflow through the GUI'` passed 1/1 in 23s on the integrated source revision, with no retries or skips.
It exercised the representative primary create/edit/run/inspect/save/reopen journey in a headed Chromium process; a separate human visual observation of the window was not recorded. Other browser cases were outside this exact selection, and no full browser lane was run.

## WF-LIF-015 confirmed workflow-format migration — integrated `2ce96a0`

At task revision `181186f`, `scripts/test focus e2e tests/e2e/workflow-format-migration.spec.ts --project=chromium` passed 1/1 in 20s and the Firefox counterpart passed 1/1 in 18s. The GUI defers an old saved workflow without changing its bytes, opens an unaffected current workflow, confirms the exact plan, checks the visible saved-document backup and original bytes, and opens/reloads the migrated workflow.
`scripts/test focus backend tests/test_services/test_schema_v2_migration.py` passed 4/4 in 4s before the final private-edit fixture refinement. After that refinement, `scripts/test focus backend tests/test_services/test_schema_v2_migration.py::test_migrates_recursive_saved_clean_dirty_and_nested_snapshot_truth` passed 1/1 in 19s, and Ruff lint/format passed. The backend evidence covers real root→child→grandchild saved/draft/private-snapshot migration, exact per-authority backups, identity/hash preservation after service reconstruction, stale-plan refusal, and multi-authority interrupted forward recovery.
`scripts/test check frontend` passed in 26s with 1,313 units, lint, types, and build; `scripts/test check cross-browser-smoke` passed 18/18 Chromium and 18/18 Firefox in 126s. `scripts/test check backend` passed before the final fixture refinement in 193s: 1,796 selected deterministic tests plus 7/7 logging-order certification, with nine external tests deselected. The directly affected selector and static checks passed after the refinement; the broad backend lane was not repeated.
Focused GUI selectors had no retries or skips. The GUI proof covers the saved document; draft/private-snapshot, interruption, and service restart are backend-level evidence, not an operating-system crash or packaged desktop restart. No full suite or external certification ran.

## GUI-EDT-014 recursive imported layout — integrated `38ac552`

At task revision `22ac5e5`, `scripts/test focus backend tests/test_services/test_graph_translator.py -k 'library_import_layout or library_layout_handles'` passed 2/2 in 3s, with 17 unrelated tests deselected. `scripts/test focus e2e --project=chromium tests/e2e/imported-graph-layout.spec.ts` passed 1/1 in 12s and its Firefox counterpart passed 1/1 in 17s after the final test edit. The browser journey imports a real portable archive twice, verifies exact recursive positions, visible nonoverlap and edges, moves a root node, then saves/reloads without reflow or sibling mutation.
`scripts/test check frontend` passed 1,313 units plus lint/types/build in 25s. `scripts/test check backend` remained red after 199s: 1,795 passed, two unrelated held-worker tests failed because sandboxed `socket.create_server(('127.0.0.1', 0))` raised `PermissionError`, and nine external cases were deselected. The exact two failed selectors then passed with local-server permission in 2s, with one unrelated case deselected; the whole backend lane was not repeated.
`scripts/test check browser` remained red after 47s: eight Chromium cases passed, then `canvas-interactions.spec.ts:342` failed because the expected `canvas-persistence-issue` message was absent after 5s while the active workflow title was dirty; 103 cases did not run. `scripts/test focus e2e --project=chromium tests/e2e/canvas-interactions.spec.ts:342` passed 1/1 in 56s on exact reproduction. No API response breadcrumb was captured by the failed run, so no product cause is established. The broad browser lane was not repeated; an initial attempted run was interrupted during server startup before tests (4s). No full suite or external certification ran.

## RT-XCT-007 Logger selection and filtered copy — integrated `cd81d42`

At patch-equivalent task revision `d997815`, `scripts/test focus e2e --project=chromium --project=firefox tests/e2e/logger-panel.spec.ts --grep 'copies visibly filtered global and execution logs without changing attribution'` passed 2/2 in 105s, including isolated server startup. The exact row-selection selector with `--grep 'selects text across log rows and copies it with the keyboard'` passed 2/2 in 16s. The tests exercise visible filters, exact global/execution log order and clipboard text, retained execution/workflow/revision metadata, empty state, denied clipboard feedback, and native row selection. Chromium reads the real clipboard; Firefox captures its write because automated read permission is unavailable. Logs are deterministically seeded in the browser store; WebSocket provenance is separately owned.
`scripts/test check frontend` passed 1,313 units plus lint/types/build in 24s. `scripts/test check cross-browser-smoke` remained red after 157s: Firefox 18/18 passed; Chromium passed 12, failed unrelated `managed-execution.spec.ts:146` on a cleanup-history message, and did not run five remaining cases. `scripts/test focus e2e --project=chromium tests/e2e/managed-execution.spec.ts:146` then passed 1/1 in 14s. No Logger coupling or reproducible product cause is established, and the smoke lane was not repeated. Focused Logger selectors had no retries or skips; no full suite or external certification ran.

## GUI-SHL-009 Image Viewers settings — integrated `198e6f6`

At task revision `198e6f6`, `scripts/test focus backend tests/test_routers/test_napari_environments_router.py::test_settings_journey_persists_rules_and_recovers_failed_managed_setup` passed 1/1 in 54s. It registers two real venv paths, persists the default and ordered rules, refuses duplicate/ownership-invalid changes, injects a controlled managed-setup failure/retry, and verifies file-backed reopen and external forget without deleting its installation.
`scripts/test focus e2e --project=chromium tests/e2e/settings.spec.ts --grep 'Image Viewers saves an ordered desktop settings journey'` passed 1/1 in 13s; the Firefox counterpart passed 1/1 in 15s after correcting two new-test locator assumptions. The browser registry and failed manager are controlled; these assertions do not certify actual Wetlands provisioning or native Qt launch.
`scripts/test check frontend` passed lint/types/build and 1,313 units in 24s. `scripts/test check backend` stayed red after 176s: 1,797 passed, two unrelated held-worker tests failed on sandboxed localhost socket binding, and nine external tests were deselected. The exact two held-worker selectors passed with localhost permission in 3s; the broad backend lane was not repeated.
`scripts/test check browser` stopped after 291s with 65 Chromium cases passed, one unrelated `napari-output-chooser.spec.ts:28` Selected workflow details mismatch before Open was clicked, and 47 cases unrun. `scripts/test focus e2e --project=chromium tests/e2e/napari-output-chooser.spec.ts:28` passed 1/1 in 8s. This does not establish an ISSUE-017 activation recurrence; an Astra/high read-only review found only a pre-Open selection/details symptom and recommended event/API breadcrumbs on recurrence. The broad browser lane was not repeated; no full suite or external certification ran.

## RT-EXE-017 corrupt cache and strict result reads — integrated `e58b8f1`

The browser `quarantines a corrupt selected record through GUI Clear and reruns exact rows` selector in `everyday-node-editing.spec.ts` passed 1/1 in Chromium (15s) and Firefox (19s) at task revision `477f73a`. It corrupts a real selected record after a three-node run, observes the failed badge and accepted-draft diagnostic after reload, refuses Run and source Node Data/CSV without stale rows, clears and quarantines through the GUI, then reruns exact rows while preserving graph/revision, healthy sibling bytes, and retained run metadata.
Specialist planning plus independent high-reasoning review governed three product corrections: idle accepted `cache_corrupt` badge precedence over a retained success; response-only draft GET cache-diagnostic refresh with partial-plan protection; and strict modern result identity/integrity through ordinary and CSV reads, including canonical latest-link validation. Exact backend service/router and frontend projector selectors passed after each correction; the final post-link-guard backend selection passed 31/31 in 6s with Ruff and diff checks clean.
`scripts/test check app` passed in 241s before the final narrow canonical-link guard: 1,806 selected backend tests, 7/7 logging-order cases, 1,319 frontend units plus lint/types/build, and 18/18 critical Chromium cases. Nine external backend tests were deselected. The guard changed only result-link validation and exact affected selectors passed afterward; the broad app lane was not repeated, so the final commit does not claim a same-revision `check app` pass.
An attempted task-worktree `scripts/test check docs` stopped before Sphinx because the task inventory was V while the shared dashboard remained G. After integration and dashboard reconciliation, `scripts/test check campaign` passed in under 1s and `scripts/test check docs` passed dashboard, links, and Sphinx in 3s at `e58b8f1` plus the campaign-record diff. The true absent-provenance legacy path remains unpinned, path-race immunity is not claimed, and the browser evidence is same-process reload rather than one session across backend restart. No full suite or external certification ran.
