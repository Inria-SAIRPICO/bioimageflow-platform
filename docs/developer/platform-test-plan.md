---
orphan: true
---

# Platform confidence campaign — 2026-09-30

Establish confidence in the platform people use today, repair demonstrated defects, then complete systematic coverage of implemented in-scope behavior.
This is a new campaign prepared from the previous campaign's results; execution has not started.
The [checkpoint](platform-test-progress.md) owns the current baseline, queue, and status; [start](platform-test-start.md) is the fresh-session execution prompt.
The [previous plan](archive/platform-test-plan-before-2026-09-30.md) and its historical 73-cell gate remain audit records, not this campaign's starting certification.

## What changes from the previous campaign

Start with the actual platform and installed library state before trusting old fixtures or branches.
Demonstrate four ordinary user journeys on the current baseline, then tackle the known unfinished high-risk flows in small independent tests.
Track the user outcome, available assertions, and executed evidence separately: a test body or a worker's proposed `V` is not a passing run.
Keep the existing stable feature inventory for systematic closure, while using a short outcome queue for daily work instead of treating five cells per feature as five separate tasks.
Reuse valid historical evidence explicitly and retain successful unchanged validation phases; do not restart completed releases or whole suites to chase an unrelated intermittent failure.

## Scope and authorities

Follow `AGENTS.md`, `PLATFORM_CONTEXT.md`, the implemented v1/v2 and applicable later specifications, and [Test lanes](../testing.md).
Cover implemented desktop and webapp behavior, including their different permission and persistence contracts.
Parallel scheduling, HPC, Parsl, managed remote execution, distributed engines, and future v3 proposals remain excluded.
Keep Direct execution and real local Wetlands execution with one sequential worker; selecting a worker engine is not proof that a worker ran.
Preserve existing out-of-scope regression tests; campaign exclusions do not authorize deleting them.
The catalog contract remains single-click to toggle bottom tool information, double-click to create exactly one node, and drag as an independent creation gesture.

## First action: establish one reproducible baseline

Before scenarios or writable task assignment, record these items together in the checkpoint:

- Platform SHA and dirty files; installed BioImageFlow/Core/Wetlands versions and source locations; editable library SHA and dirty state; relevant lockfile/dependency differences.
- Registered worktrees, their branches/SHAs, dirty state, actual active owners/processes, and disposition: preserve, read-only candidate for salvage, or integrated and safe to retire.
- A bounded change scan from inventory audit `15c5cc7` to the selected baseline, mapping changed controls/contracts to stable inventory IDs, missing obligations, and historical evidence invalidated by those changes.

Do not trust a stale branch's API fields, dependency pins, or documentation status.
In particular, removed fingerprint fields and changed dependency/result contracts require comparison with current code before using the unfinished Napari and stale-environment work.
Keep their original worktrees untouched while inspecting; port only reviewed relevant changes to a clean task branch if needed.
Do not merge a dirty worktree wholesale, silently reset it, or delete abandoned work.
A new task worktree has its own dependencies, runtime state, and build output under `.worktrees/<task_name>`.
The baseline is ready when the next tasks have current contracts, runnable fixtures, explicit ownership, and no unresolved dependency mismatch affecting their assertions.
Record a missing prerequisite with its recovery action and continue independent work.

## Wave 1: current-code readiness

The readiness gate is four fixed user outcomes, each exercised through the real GUI/backend in Chromium and Firefox on one reconciled integrated baseline.
These are existing tests to inspect and run, not new coverage claims or a request to duplicate them.
Use the title rather than a historical line number and confirm it still exists before execution.

| Outcome | Existing browser selector under `frontend/tests/e2e/` | Required observation | Inventory anchors |
| --- | --- | --- | --- |
| J1 — Build, run, inspect, save, reopen | `canvas-interactions.spec.ts`, `builds, runs, inspects, saves, and reopens a real workflow through the GUI` | Actual catalog/canvas actions produce the intended accepted graph, exact result, and durable reopened workflow; confirm the execution record says `direct` before claiming Direct coverage. | GUI-EDT-001, WF-LIF-004, RT-EXE-004, RT-RES-001 |
| J2 — Recover a failed run | `canvas-interactions.spec.ts`, `recovers a real Direct failure without publishing a partial result` | Visible failure exposes no partial result; GUI correction and rerun produce the exact expected data. | RT-EXE-008 |
| J3 — Inspect the intended nested instance | `nested-execution.spec.ts`, `opened nested canvases inspect the results of their own instance` | Scoped requests and visible tables must identify the selected nested instance; give sibling instances distinguishable expected results before claiming wrong-instance display is excluded. | WF-REC-012 |
| J4 — Recover corrupt cache safely | `everyday-node-editing.spec.ts`, `quarantines a corrupt selected record through GUI Clear and reruns exact rows` | Corrupt result is refused, Clear repairs the selected state, rerun yields exact rows, and healthy sibling/history state stays coherent. | RT-EXE-017 |

For example, run J1 with `scripts/test focus e2e tests/e2e/canvas-interactions.spec.ts --grep 'builds, runs, inspects, saves, and reopens a real workflow through the GUI' --project=chromium --project=firefox`.
Playwright matches the full title including any parent `describe` block and appended test tags, so do not anchor the bare title to the end when a tag follows it; confirm that exactly the intended case was selected in each project.
Use the same command shape for J2–J4, with their own file/title.
Inspect assertions before execution; the current J1 test does not assert the selected backend, and J3's siblings currently produce identical rows despite its scoped-request checks.
Strengthen only these missing assertions if the current code still has those gaps; a passing test cannot credit an observation it does not distinguish.

Pass the gate only with 4/4 outcomes, both browser results for each, no retries/skips masking failure, exact command/revision/duration records, and no known reachable unresolved security, data-loss, wrong-identity, or wrong-result defect affecting these paths.
If a repair changes the baseline, rerun affected outcomes and explicitly justify reuse of unaffected results using source, fixture, dependency, and environment equivalence; do not manufacture a same-SHA run claim.
An existing test must be extended only where a current contract is demonstrably missing from its assertions.
At this boundary inspect a representative trace/screenshots, or run one representative journey headed when a display is available; record what was actually observed.
Report gate readiness separately from whole-campaign progress and continue into Wave 2 automatically when execution has been requested.
The gate is a modest readiness signal, not a release certificate or completion of all primary-GUI obligations.

## Wave 2: finish the risky user flows

After Wave 1, take this initial queue in order; a demonstrated loss/wrong-result defect takes precedence and independent work may continue when one item is externally blocked.

| Batch | Concrete acceptance and test boundaries | Completion evidence |
| --- | --- | --- |
| N1 — Napari chooser and favorite (RT-RES-012) | Compare the dirty candidate against current main. Make separate scenarios for ordinary selection/launch, exclusive favorite and reload, inactive-dock/scroll geometry, and failure/retry/stale-result refusal. Assert captured result/output/environment identity and no duplicate launch or unintended favorite mutation. | Exact relevant Chromium/Firefox selectors; lower-level real resolver/favorite persistence assertions; required scoped check. Intercepted resolve/open/favorite APIs prove client contract only; native launch remains RT-RES-011. |
| E1 — Stale local processing environment (RT-EXE-018) | Compare the dirty candidate with the current dependency contract. A real GUI Run replaces a stale owned processing generation once, executes a real worker, and yields exact files/data. Separately cover incompatible core refusal, failed replacement/retry, later run/restart reuse, and fresh/unrelated/external environment isolation. | Real worker PID, generation and cleanup evidence plus visible progress/error/recovery. Controlled setup fixtures alone cannot close real provisioning or restart claims. |
| I1 — Import viewing guidance (WF-SRC-011) | Import real viewer requirements, show output-specific missing/unknown guidance, and run despite absent viewers without implicit installation. Separately exercise readiness failure/retry and sibling-import identity. | GUI success in both browsers plus real readiness/manifest contract checks; unavailable native viewer does not prevent testing import guidance. |
| T1 — Manage Tools environments (GUI-AUT-008) | Open a tool's declared environments, create/recreate only the selected owned environment, reopen its state, and recover a failure. Check forbidden deployment/ownership actions without changing another environment. | Visible control assertions, real lifecycle evidence where claimed, and independent webapp/API permission checks. |

N1 is a small set of independent scenarios, not one expanded test that launches, favorites, changes docks, scrolls, fails, retries, and changes results in a single chain.
Reuse fixtures and existing tests where adequate; isolate only behaviors whose earlier failure would hide a different outcome.
Keep native Qt and real installation as separately scheduled obligations with explicit prerequisites, not implicit credits for a mocked browser journey.
ISSUE-013 retains its exact focused probe investigation; ISSUE-014/017 and earlier one-off selection failures remain open observations, not proven product causes.
On recurrence capture the real gesture/Open command, request/response, workflow generation/revision, active tab, execution lock, and event order before changing the test or product.
A failed focused reproduction is actionable; an isolated pass does not close an intermittent issue or make its original lane green.

## Wave 3: systematic extensions and real integrations

The [GUI](coverage-gui.md), [workflow](coverage-workflows.md), and [runtime](coverage-runtime.md) inventories retain every implemented in-scope obligation, including negative, recovery, persistence, permission, native, and external cases.
After Wave 2 select remaining runnable rows by user frequency and loss/wrong-result risk; check existing assertions before adding tests.
Cover all of these families before final closure:

- Workspace/startup, settings, layouts, tabs, and deployment-specific controls.
- Workflow lifecycle, recovery/conflicts, import/export, recursive interfaces, private edits, provenance, and source ownership.
- Catalog/canvas editing, clipboard/history/focus, tools/packages, hot reload, Python authoring, and editor lifecycle.
- Local execution, selected dependencies, progress/logs, cancellation/retry, cache/results, tables/images, and result exports/bundles.
- Datasets, implemented OMERO controls, REST/WebSocket/MCP boundaries, real native dialogs/viewers/editors, and process crash/restart.

At each wave boundary compare implemented specification sections and visible controls/routes against the inventory so an omitted feature cannot disappear from final coverage.
Schedule external/native prerequisites early enough to expose blockers while independent automated work continues.
Use [Manual Platform Testing](manual-testing.md) for native/external procedures and disposable fixtures.

## Evidence and coverage without unnecessary overhead

Keep three distinct facts: the inventory's required scenario, a located test/manual procedure capable of asserting it, and a dated executed result that actually did so.
The [dashboard](platform-test-dashboard.md) retains the stable denominator: 500 applicable obligations, including 224 primary-GUI obligations, at preparation time.
Its historical 266/500 and 224/224 counts are not new-campaign progress or current certification.
Do not reset valid historical evidence merely because a new campaign starts; assess affected rows during baseline reconciliation and retain unaffected evidence only with an explicit applicability rationale.
Mark invalidated/uncertain cells as gaps or unassessed in inventory and dashboard together, retaining the old evidence link.
Change the denominator only for a documented scope/applicability discovery, with the old/new totals and rationale; never shrink it to improve completion.
Report current campaign gate outcomes and completed batches first; report a dashboard percentage as current only after its evidence applicability is reconciled, otherwise label it historical.

For one coherent completed batch, the orchestrator records command/selector/project, tested SHA or named diff, integrated SHA, dependency baseline, duration, result, retries/skips/deselections/unrun cases, evidence type, and artifact location in [evidence](platform-test-evidence.md).
Use the labels **mocked client**, **real API/storage**, **real GUI + backend**, **real sequential worker**, and **native/manual** where needed to delimit claims.
API-seeded prerequisites are allowed, but an API/store mutation cannot certify that action's GUI path; mocked execution cannot certify computation or worker lifecycle.
Use exact expected values and captured identities rather than assertions that merely copy implementation output.
Workers return proposed obligation credits; only the orchestrator updates shared inventory/dashboard/checkpoint after checking actual commands and assertions.
Never promote status from a planned command or prospective worker documentation.
Record interruptions, blockers, and owner decisions immediately; consolidate ordinary completed-batch administration into one update and commit.

## Repair, delegation, and validation

The executing session is the orchestrator and may use at most two ordinary workers, keeping one slot available for a specialist.
Workers receive a fresh bounded packet with current contract, one outcome, owned paths/worktree, inventory IDs, baseline/dependencies, acceptance conditions, exact checks, and escalation triggers.
Writable parallel work must use separate worktrees; shared campaign records belong to the orchestrator.
Commit only each task's validated changes, integrate after review, and retire only clean integrated task worktrees as `AGENTS.md` requires.
Leave unrelated files and unfinished worktrees intact.

Routine bounded repairs stay with the ordinary worker when cause and contract are clear, including mechanical updates to stale fixtures or renamed fields.
When a contract conflict remains unresolved after checking current code, tests, and specifications, or a refactor could alter identity, persistence, concurrency, or loss behavior, get one bounded high-reasoning diagnosis/plan and independent review before dependent implementation.
The plan identifies the authoritative contract, smallest correction, identity/concurrency/persistence/rollback invariants, and distinguishing tests; a concise no-refactor decision is sufficient when justified.
Use the same specialist path for unclear library semantics or high-impact identity/loss risk.
Do not repeat the specialist loop for unchanged reviewed invariants; if unavailable, record the missing review and continue independent work.
Escalate to the owner only for a concrete unresolved product/scope decision, with the supported entry path and user impact.

Use `scripts/test` and the completion table in [Test lanes](../testing.md), not an invented campaign runner.
Reproduce an exact failure in its exact browser before expanding; after a fix rerun it once, or five times only for a suspected timing/race defect.
Then run the smallest required scoped completion check for the actual changed surface; changed GUI journeys need exact Chromium and Firefox evidence.
Use `quick` only for intermediate coding feedback, never immediately before a completion check that subsumes it.
Do not overlap browser-heavy lanes; do not start a broad browser project while its exact failing selector remains red.
After late failure preserve successful unchanged phases, record the failed/unrun portion, and rerun only invalidated checks; a composite record must identify each phase's revision rather than call the original command passed.
Routine status edits use `check campaign` once per consolidated batch; navigation/structure changes and final documentation acceptance use `check docs`, which includes it.
No new runner infrastructure is planned; change it only for a demonstrated selection/validation need.

## Final acceptance

Use the existing audited `--campaign-local` selectors and `tests/campaign-local-scope.json` to cover complete in-scope backend, unit, Chromium, and Firefox collections.
Exact focused tests use ordinary selectors because campaign-wide selection cannot be combined with arbitrary grep/file filters.
Collect-only output establishes selection, not a pass; reconcile every selected, excluded, skipped, failed, and unrun case.
Also cover lint/types/build, logging-order certification, documentation, published common-tools compatibility (`scripts/test certification`), and real sequential-worker acceptance with the documented commands.
Choose comprehensive lanes only at final certification or when the change surface requires them; if a broad lane contains excluded behavior, report its broader scope or use the documented complete audited selections with the remaining checks recorded separately.
Record editable dependency SHAs as well as package versions; source-checkout results cannot silently become a published-package compatibility claim.
Do not repeat previously completed release/publication operations without a new required dependency fix.

Complete the campaign only when all implemented in-scope obligations have reconciled evidence, every primary GUI journey passes in Chromium and Firefox, demonstrated defects have a reviewed resolution, and native/external obligations have actual outcomes.
An unavailable obligation remains blocked; explicit owner acceptance may permit closure with a named limitation, never a fabricated pass or a removed denominator cell.
Readiness alone, raw test counts, and historical dashboard percentages cannot establish completion.
The final report gives exact validation revisions/results/durations and any retained limitations, with clean committed task changes and a restartable checkpoint.
