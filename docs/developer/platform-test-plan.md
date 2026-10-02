---
orphan: true
---

# Platform confidence campaign — 2026-09-30

Establish confidence in the platform people use today by reviewing architecture and tests together, repairing demonstrated defects and validated structural weaknesses, then completing systematic coverage of implemented in-scope behavior.
This campaign was prepared from the previous campaign's results; execution started after the user requested it on 2026-09-30.
M1 complete agreed-scope review is accepted; the dated M1 retrospective and first bounded M2 queue in the [checkpoint](platform-test-progress.md) now govern diagnosis and repair release.
The complete-review hold below describes the gate while it was open; its closure does not authorize every candidate repair, resume held I1/T1 automatically, or release systematic coverage expansion.
The checkpoint records actual readiness outcomes separately from historical coverage.
The [checkpoint](platform-test-progress.md) owns the current baseline, queue, and status; [start](platform-test-start.md) is the fresh-session execution prompt.
The [previous plan](archive/platform-test-plan-before-2026-09-30.md) and its historical 73-cell gate remain audit records, not this campaign's starting certification.

## What changes from the previous campaign

Start with the actual platform and installed library state before trusting old fixtures or branches.
Retain the four completed ordinary user journeys and accepted repairs, then examine the architecture and test suites before tackling the remaining flows.
Do not equate passing tests with sound architecture or a file-reading count with understanding the system.
Track the user outcome, available assertions, and executed evidence separately: a test body or a worker's proposed `V` is not a passing run.
Keep the existing stable feature inventory for systematic closure, while using a short outcome queue for daily work instead of treating five cells per feature as five separate tasks.
Reuse valid historical evidence explicitly and retain successful unchanged validation phases; do not restart completed releases or whole suites to chase an unrelated intermittent failure.

## Scope and authorities

Follow `AGENTS.md`, `PLATFORM_CONTEXT.md`, the implemented v1/v2 and applicable later specifications, and [Test lanes](../testing.md).
Cover implemented desktop and webapp behavior, including their different permission and persistence contracts.
Parallel scheduling, HPC, Parsl, managed remote execution, distributed engines, and future v3 proposals remain excluded from campaign execution.
Their tracked human-written source, tests and specifications remain included in the complete codebase review.
Keep Direct execution and real local Wetlands execution with one sequential worker; selecting a worker engine is not proof that a worker ran.
Preserve existing out-of-scope regression tests and specification contracts; campaign exclusions do not authorize deleting delivered parallel, HPC, Parsl, or managed remote/distributed capabilities.
The catalog contract remains single-click to toggle bottom tool information, double-click to create exactly one node, and drag as an independent creation gesture.

## First action: establish one reproducible baseline

Before application assertions or writable repair assignment, reconcile specification authority with actual current code and record the reviewed documentation revisions in the checkpoint.
Use the bounded specification-coherence revision as a docs baseline, then distinguish stale descriptions from implementation defects and unresolved future product choices rather than silently choosing code as the authority.
Keep canonical recursive GraphState, CAS drafts/private snapshots, stable source/result identities, worker requirements/floors/caps, dataset deletion CAS, local/managed execution ownership, portable viewer metadata, and native-certification boundaries intact.
Documentation review and a passing docs check earn no application, browser, worker, or native coverage credit.

Record these items together in the checkpoint:

- Platform SHA and dirty files; installed BioImageFlow/Core/Wetlands versions and source locations; editable library SHA and dirty state; relevant lockfile/dependency differences.
- Registered worktrees, their branches/SHAs, dirty state, actual active owners/processes, and disposition: preserve, read-only candidate for salvage, or integrated and safe to retire.
- A bounded change scan from inventory audit `15c5cc7` to the selected baseline, mapping changed controls/contracts to stable inventory IDs, missing obligations, and historical evidence invalidated by those changes.
- Reviewed platform/library specification revisions, preserved contract boundaries, and known doc-versus-code debts with an owner, scope, and distinguishing acceptance before any dependent assertion or repair.
  The current known debts include generated-type consumption in the handwritten draft wrapper, absent-installation Napari default-recipe creation, and exact uploaded-original-filename metadata fidelity; none is closed by documentation reconciliation.
  The library specification also records permissive runtime image-validation adapter implementation debt; use its own normative owner rather than copying that contract into campaign notes.
  Future v3 storage roots/migration, summary join policy, read-only-store installation strategy, and security deployment choices remain separate owner decisions.

Do not trust a stale branch's API fields, dependency pins, or documentation status.
In particular, removed fingerprint fields and changed dependency/result contracts require comparison with current code before using the unfinished Napari and stale-environment work.
Keep their original worktrees untouched while inspecting; port only reviewed relevant changes to a clean task branch if needed.
Do not merge a dirty worktree wholesale, silently reset it, or delete abandoned work.
A new task worktree has its own dependencies, runtime state, and build output under `.worktrees/<task_name>`.
Reuse its installed dependencies while lockfiles, editable dependency metadata, and installation options remain compatible; resync only affected environments when installation requirements change, without sharing them between worktrees.
Retain fresh disposable browser runtime roots and external certification stores; dependency reuse must not reuse a prior test's workspace or result state.
The baseline is ready when the next tasks have reviewed current contracts, runnable fixtures, explicit ownership, and no unresolved dependency mismatch or contract decision affecting their assertions.
Record the integrated documentation and application/dependency revisions actually used; dated prior observations stay historical and must not be relabelled as a current baseline.
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
The preparation-time J1 backend and J3 distinguishable-sibling assertion gaps were corrected in the accepted readiness work; the complete source review confirms the current assertions.
Retain their recorded revision-specific results and inspect the current bodies before any affected rerun; do not add duplicate tests or replay readiness solely because those historical gaps appeared in this plan.

Pass the gate only with 4/4 outcomes, both browser results for each, no retries/skips masking failure, exact command/revision/duration records, and no known reachable unresolved security, data-loss, wrong-identity, or wrong-result defect affecting these paths.
If a repair changes the baseline, rerun affected outcomes and explicitly justify reuse of unaffected results using source, fixture, dependency, and environment equivalence; do not manufacture a same-SHA run claim.
An existing test must be extended only where a current contract is demonstrably missing from its assertions.
At this boundary inspect a representative trace/screenshots, or run one representative journey headed when a display is available; record what was actually observed.
Report gate readiness separately from whole-campaign progress and continue into Wave 2 automatically when execution has been requested.
The gate is a modest readiness signal, not a release certificate or completion of all primary-GUI obligations.

## Reconnaissance gate: architecture and tests together

The independent GPT-6.1 Sol Ultra retrospective on 2026-10-01 found real product gains but no completed whole-system architecture or suite-redundancy audit.
Its installed-Wetlands force-Recreate contradiction and the earlier Run preparation bypass demonstrate why public dependency boundaries must be traced before adding coverage.
Insert this gate at the current checkpoint; do not undo accepted fixes or reexecute readiness merely because the sequence changes.
The user's subsequent clarification requires a meticulous whole-codebase and test-suite review before further repairs or campaign execution.
The earlier inventory and selective reconnaissance did not complete M1; priority diagnostic tests and implementation plans are now held with I1/T1.

Inventory all tracked first-party platform and library/Core implementation, tests, runner/configuration and specification files at named revisions.
Classify generated files, bundled assets, fixtures and excluded execution families explicitly rather than treating every file as an independent coding task.
Review Wetlands' relevant public contracts and installed implementation, recording differences from its source checkout; this is a targeted dependency review, not certification of the entire dependency.
Every inventoried file has a subsystem owner and a truthful depth: inventory-only, read, traced through callers/consumers, or deeply reviewed against an invariant.
Record complete-review status separately: pending, reviewed, or classified with a justified generated/asset boundary.
Earlier excerpt/invariant review does not establish a complete-file review.
Inventory-only and static reading earn no application coverage credit.
Use a compact file ledger and record unreviewed areas; do not claim exhaustive analysis from a representative sample.

Assign ordinary agents by subsystem, with the orchestrator owning shared records and a reserved specialist synthesizing cross-subsystem findings:

| Review family | Responsibilities and boundaries |
| --- | --- |
| Graph and workflow ownership | Canvas commands, root drafts, private snapshots, recovery, identity generations, CAS, recursive interfaces, generated API types and library graph contracts |
| Tools and portable sources | Registry versus compiled classes, source ownership, archive/import/export, package installation, hot reload, Python authoring and editor boundaries |
| Execution and environments | Admission, cancellation and physical completion, startup/Run/manual mutation, declared recipes, real workers and platform → BioImageFlow → Wetlands public capabilities |
| Results and scientific data | Cache/provenance, immutable results, images/adapters/transports, viewer requirements and real scientific tool integration boundaries |
| Deployment and persistence | Datasets, settings/workspace, containment and permissions, desktop/webapp differences, REST/WebSocket/MCP and external integration ownership |
| Test architecture and cost | Fixture authorities, assertion oracles, selection/markers, shared helpers, real versus intercepted paths, repeated setup, artifact retention and comparable timing evidence |

Trace sensitive paths from user gesture or API through validation, ownership, persistence and public dependency calls.
Look for redundant authorities, duplicated business rules, private dependency coupling, inconsistent error/recovery semantics and tests whose assertions do not distinguish their stated outcomes.
Treat complexity or repetition as a candidate to investigate, not proof that a rewrite or deletion is needed.
For each finding record the source/contract, demonstrated defect or unproved risk, consequence, existing distinguishing selectors, repair/retain/deepen/defer decision and owner.
Preserve the recursive GraphState, CAS, stable identities, immutable result and deployment contracts; excluded distributed implementations and tests remain intact.

Review every human-authored implementation, test, script/configuration and specification file in the platform and library checkout, including scientific packages and statically reviewed execution families excluded from later campaign execution.
Review the entire Wetlands source checkout and compare installed contracts where the platform/library consumes them.
Read complete files in manageable dependency-ordered batches, then trace callers, ownership/lifetime, error and concurrency paths, persistence, public contracts, test fixtures and distinguishing assertions.
Inspect generated code, lockfiles, fixtures and assets through their actual producer/consumer and boundary requirements; classification requires a specific rationale and cannot excuse an inconvenient human-written file.
Include all held I1/T1 and diagnostic task files at captured content hashes; unrelated historical worktrees remain outside the current source baseline.
Record every identified defect, risk, redundancy, maintainability issue, test-oracle weakness and specification inconsistency in the findings register, with severity, precise source, causal reasoning, existing tests, uncertainty and a proposed future action.
A no-finding file needs a specific review rationale; reading/search telemetry alone is not evidence of review quality.

Do not implement fixes, add or execute diagnostic/product/browser/external tests, install dependencies or resume campaign coverage while this review gate is open.
Documentation-only integrity validation may run to preserve coherent review deliverables; it supplies no application evidence.
Use serial review batches and durable checkpoints without an arbitrary one-or-two-day completion deadline.
The gate closes only when every baseline file is reviewed or explicitly classified, there are zero pending/unmatched/content-hash-mismatched human-written inputs, cross-subsystem findings are synthesized, and independent review accepts the method, a representative evidence sample and the prioritized backlog.
Review changed source again when its recorded hash changes; keep earlier partial inspection and red diagnostics as historical evidence.
Completion means the agreed source scope was meticulously reviewed, not that every possible bug was discovered or behavior was certified.
The specialist checks completeness, interactions and evidence quality rather than duplicating every file read.

I1/T1 remain isolated at their preserved checkpoints during reconnaissance.
After complete review and synthesis, finish I1's applicable completion checks without relabelling its composite or deferred phases as a passing original lane.
T1 must resolve force-Recreate through a supported public capability; do not delete environment directories, mutate private state, invent recipe nonces or silently narrow the essential feature to stale-only replacement.
Independent T1 ownership/admission repairs may be split only when they form a reviewed coherent change with their own required validation and explicit remaining lifecycle gap.
Recheck E1 consumers affected by shared helper or lifecycle changes; retain only equivalent unchanged evidence.

## Wave 2: finish the risky user flows

The initial N1/E1 queue has already produced accepted repairs.
Before finishing I1/T1 or expanding Wave 3, use the accepted reconnaissance gate and dated M2 queue to resolve each packet's remaining contract, source and validation prerequisites rather than blindly resuming the old test queue.
A demonstrated loss/wrong-result or permission defect takes precedence and independent work may continue when one item is externally blocked.

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
After reconnaissance and the prioritized repairs, select remaining runnable rows by user frequency and loss/wrong-result risk; check existing assertions before adding tests.
Cover all of these families before final closure:

- Workspace/startup, settings, layouts, tabs, and deployment-specific controls.
- Workflow lifecycle, recovery/conflicts, import/export, recursive interfaces, private edits, provenance, and source ownership.
- Catalog/canvas editing, clipboard/history/focus, tools/packages, hot reload, Python authoring, and editor lifecycle.
- Local execution, selected dependencies, progress/logs, cancellation/retry, cache/results, tables/images, and result exports/bundles.
- Datasets, implemented OMERO controls, REST/WebSocket/MCP boundaries, real native dialogs/viewers/editors, and process crash/restart.

At each wave boundary compare implemented specification sections and visible controls/routes against the inventory so an omitted feature cannot disappear from final coverage.
Inspect external prerequisites without launching native applications; execute desktop tests only at the very end, after automated and external acceptance, as the user requested.
Headless checks cannot certify native dialogs, viewer launch, editor interaction or desktop restart.
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
Use the runner's phase and total timings to record cold versus warm setup, dependency/provisioning setup time when separately observed, executed lane count, and why a repeat was needed; parallel wall time and summed phase time are different measurements.
Compare equivalent commands and prerequisites before claiming savings; the schedule is an efficiency hypothesis until measured, and cost goals never reduce required coverage or hide a failure.
Use the labels **mocked client**, **real API/storage**, **real GUI + backend**, **real sequential worker**, and **native/manual** where needed to delimit claims.
API-seeded prerequisites are allowed, but an API/store mutation cannot certify that action's GUI path; mocked execution cannot certify computation or worker lifecycle.
Use exact expected values and captured identities rather than assertions that merely copy implementation output.
Workers return proposed obligation credits; only the orchestrator updates shared inventory/dashboard/checkpoint after checking actual commands and assertions.
Never promote status from a planned command or prospective worker documentation.
Record interruptions, blockers, and owner decisions immediately; consolidate ordinary completed-batch administration into one update and commit.

## Suite and specification improvement

Review tests alongside their production owners, comparing contract, entry point, expected result and failure condition before declaring duplication.
Prefer extending a missing local distinction in an existing case; keep separate tests when they protect different boundaries or one earlier failure would conceal another outcome.
Remove or merge only proven redundant assertions with retained contract coverage; preserve meaningful component, storage, GUI and actual-worker layers.
Correct misleading test titles and fixture/marker boundaries when demonstrated, without building tests that merely mirror marker implementation.

Establish comparable costs from retained timings first, then collect only missing measurements needed for an optimization decision.
Distinguish cold/warm dependency setup, collection/fixture time, execution/waits, repeated work, wall time and summed parallel phases.
Report the before/after scope, revision and prerequisites for each accepted optimization; no global speedup or redundancy removal is established yet.
Avoid predictable sandbox failures by requesting known socket/network/system access on the first applicable command; confirm exact selectors exist before execution.
Preserve failure artifacts before runtime cleanup or pytest retention can remove them, and capture first-attempt browser traces for unexplained ordering failures when the fixture supports it.
Do not create new runner infrastructure without a demonstrated need.

Review platform and library specifications at the same boundaries as code.
Keep requirements in their owning normative document and use context as navigation; remove repeated descriptions only when no essential requirement, rationale or explicit gap is lost.
Update all affected specifications and PLATFORM_CONTEXT with behavioral or architectural repairs.
Keep the checkpoint focused on current state/decisions and put detailed completed evidence in its owning record/archive rather than repeating the full narrative.

## Milestones and retrospectives

| Milestone | Required outcome |
| --- | --- |
| M0 — Retained baseline | Reviewed specifications, accepted Wave 1/N1/E1 and preserved I1/T1; historical percentages remain separate from current certification |
| M1 — Complete codebase review | Every human-authored platform/library/Wetlands source and test file reviewed, generated/assets explicitly classified, held WIP inspected, all identified findings recorded, cross-boundary synthesis and independent completeness review; no static-review coverage credit |
| M2 — Priority repairs and optimization | Validated coherent repairs, resolved or explicitly blocked dependency contracts, measured suite changes and consistent specifications |
| M3 — Systematic implemented coverage | Reconciled inventories and missing real assertions across all in-scope families, with low-risk work following the architectural findings |
| M4 — Automated and external certification | Complete audited local selections plus required lint/types/build/logging/docs, published compatibility and real-worker/scientific-boundary results |
| M5 — Final desktop acceptance | Actual native outcomes at the end, named remaining limitations and clean committed task changes |

Hold a strategic retrospective after M1, after several coherent repair batches or a major architectural integration, before systematic coverage expansion and before final certification.
Combine adjacent triggers into one review; do not conduct a retrospective after every edit, test or file.
An ordinary retrospective is a bounded 30–60 minute review of what was learned, duplicated/moved authorities, invalidated evidence, observed cost and changed priorities.
Record only consequential decisions and queue changes in the checkpoint.
Trigger an exceptional targeted review for a contradictory public dependency contract, new ownership/permission bypass, recurring unexplained failure or repeated fixture/permission rework; independent work continues where safe.
Use independent high-reasoning review for unresolved high-impact decisions, retaining the ordinary two-worker and specialist arrangement.
The campaign is a learning and repair process, not a percentage-filling exercise.

### October 2 repair-wave decision

Close the bounded first wave A/D1/B/D2/C: executable/resource authority, exact dataset deletion/publication, confined uninstall and the imported-layout fixture correction.
Keep the demonstrated startup-versus-Browse selection ownership defect in a separate next repair packet; preserve its RED regression independently and exclude it from first-wave commits.
Complete that packet before the urgent populated-credential rollback, configured deployment-policy admission, public force-Recreate and physical-lifetime packets; resolve or explicitly block those architectural priorities before M3 coverage expansion.
Force-Recreate remains a public ownership/contract seam to reconcile in the correct repository, not an assumed Wetlands defect.

Accept each task through its reviewed impact map and smallest applicable completion scope.
For this first wave, independently inspect the retained backend/frontend/logging/external and current fixture phases plus all 18 critical Chromium cases, with exact source, dependency, fixture and runtime equivalence.
Record this as scoped phase assembly; the original full invocation, browser failures and remaining broad-browser gaps stay open and cannot become a monolithic app/full PASS.
After a selection product change, rerun its exact causal/original failures and affected frontend completion, then both-browser completion unless per-case independence justifies narrower reuse; unchanged backend/external phases need no automatic repeat.
Keep documentation checks at coherent increments and native desktop acceptance at final M5.

Use about 50% of the next repair wave's effort for owner/caller analysis and implementation, 30–35% for meaningful verification, and the remainder for specifications, integration and cleanup as a planning heuristic, not a measured quota.
Suite-wide optimization has not been measured.
After the architectural repairs, evaluate one separately measurable suite candidate, prioritizing reliable first-failure artifacts or deterministic fixture ownership; compare baseline/candidate cost and preserve distinct contracts, entry points and failure oracles before merging or removing tests.
Take one strategic checkpoint after the accepted repair wave or a material scope change, before M3 and before final certification; combine adjacent triggers instead of reviewing strategy after each test failure.
The [current checkpoint](platform-test-progress.md#october-2-strategic-checkpoint-and-first-wave-delivery) owns the active queue, completion evidence and remaining gates.

## Repair, delegation, and validation

The executing session is the orchestrator and may use at most two ordinary workers, keeping one slot available for a specialist.
Workers receive a fresh bounded packet with current contract, one outcome, owned paths/worktree, inventory IDs, baseline/dependencies, acceptance conditions, exact checks, and escalation triggers.
Include a short impact map: changed files → owning service/session and callers → storage/event/generated-type/library consumers → exact distinguishing selectors in each affected layer/browser → required completion scope.
Trace those consumers in code and tests rather than selecting only by file proximity; include negative, recovery, permission, and identity cases when the changed contract can affect them.
Writable parallel work must use separate worktrees; shared campaign records belong to the orchestrator.
Commit only each task's validated changes, integrate after review, and retire only clean integrated task worktrees as `AGENTS.md` requires.
Leave unrelated files and unfinished worktrees intact.


### Worktree and environment retirement

The orchestrator assigns a cleanup owner when each task worktree is created, and records its exclusive dependency/runtime/build directories plus any required failure evidence.
At task integration, require committed changes, clean tracked/untracked source state, merged HEAD, no active owner/process and preserved actionable evidence before retirement.
Release task-owned servers/workers through their normal owner and verify physical retirement before deleting their disposable files; a process stop request alone does not prove cleanup.
Remove only that completed task's rebuildable `.venv`, `node_modules`, build output and disposable test runtime/environment stores, preserving user data, credentials, adopted/shared environments and retained artifacts.
Bulk dependency deletion acquires the heavy-work token or runs outside timing-sensitive browser/subprocess validation; prior timing failures have no established causal attribution to cleanup.
Follow `AGENTS.md`: move the retired source tree to Trash with `mv`, run `git worktree prune`, then delete only the merged task branch.
Record paths, branch/HEAD, ownership/status checks, removed bytes, bytes merely moved to Trash and preserved evidence; moving files to Trash alone is not a disk-space reclamation claim.
Do not run a global cache purge or delete environments by private dependency paths; actual managed resources retain their public lifecycle/ownership rules.
Held, dirty or unmerged worktrees keep their source changes and explicit owner/disposition; reassess them at each major campaign checkpoint, with no age-only deletion policy.
Before beginning another milestone, reconcile registered worktrees and task-owned disposable stores against the active/held queue and complete any safe overdue retirement.
The user's authorized cleanup of completed unused trees may run during M1; it does not release repairs, diagnostics or application/native acceptance.

### Repair and verification

Routine bounded repairs stay with the ordinary worker when cause and contract are clear, including mechanical updates to stale fixtures or renamed fields.
When a contract conflict remains unresolved after checking current code, tests, and specifications, or a refactor could alter identity, persistence, concurrency, or loss behavior, get one bounded high-reasoning diagnosis/plan and independent review before dependent implementation.
The plan identifies the authoritative contract, smallest correction, identity/concurrency/persistence/rollback invariants, and distinguishing tests; a concise no-refactor decision is sufficient when justified.
Use the same specialist path for unclear library semantics or high-impact identity/loss risk.
Do not repeat the specialist loop for unchanged reviewed invariants; if unavailable, record the missing review and continue independent work.
Escalate to the owner only for a concrete unresolved product/scope decision, with the supported entry path and user impact.

Use `scripts/test` and the completion table in [Test lanes](../testing.md), not an invented campaign runner.
After each localized edit run its affected exact selectors; reproduce an exact failure in its exact browser before expanding, then rerun it once after a fix, or five times only for a suspected timing/race defect.
Run `quick` after a coherent coding increment when development will continue; omit it immediately before a completion check that subsumes it.
At feature/repair completion run the smallest required scoped check once before committing or integrating; changed GUI journeys also need exact Chromium and Firefox evidence.
Cross-stack API/schema/dependency/runtime changes require `check app`; broad architectural/test-infrastructure changes require `check all`, plus `check browser-all` when broad browser/E2E infrastructure is affected, as the lane table requires.
Do not overlap browser-heavy lanes; do not start a broad browser project while its exact failing selector remains red.
For lanes or exact controls that start local servers or browsers, select the execution context permitting localhost binding/browser launch on the first attempt; retain any denied original invocation separately from unchanged exact recovery.
After late failure preserve successful unchanged phases only with relevant source, fixture, dependency/editable-library, generated-artifact, and runtime equivalence; record the original red/interrupted command and all failed/skipped/unrun portions, then rerun only invalidated checks.
A composite record must identify each phase's revision and applicability rather than call the original command passed.
Routine status edits use `check campaign` once per consolidated batch before commit; navigation/structure changes, substantial documentation milestones, and final documentation acceptance use `check docs`, which includes it, without a separate preceding campaign check or Sphinx runs for each review draft.
No new runner infrastructure is planned; change it only for a demonstrated selection/validation need.

Use M0–M5 above to review the combined impact map and confirm affected shared journeys on the reconciled integrated baseline; run missing or invalidated journeys and retain equivalent passing feature and journey evidence instead of repeating checks solely because a milestone ended.
Use `full` after a completed large cross-stack plan, for package-loading/external-compatibility changes, or for final comprehensive certification when that broader scope is chosen; it includes product, external, coverage, and both-browser phases but documentation remains separate.
`check app` includes backend/frontend completion plus critical Chromium, and `check all` expands that browser scope to full Chromium; neither supplies Firefox or documentation evidence.

### Dependency PyPI releases with gh

Verified 2026-10-02 against BioImageFlow [`7c718a0` release workflow](https://github.com/Inria-SAIRPICO/bioimageflow/blob/7c718a094e2741d738b27fc52cb560b7e84722c6/.github/workflows/release.yml) and [release guide](https://github.com/Inria-SAIRPICO/bioimageflow/blob/7c718a094e2741d738b27fc52cb560b7e84722c6/docs/source/reference/releasing.md), and Wetlands [`3ee2ffe` release workflow](https://github.com/arthursw/wetlands/blob/3ee2ffe1da7b6f1cfe97a8d88e6de67797d031d1/.github/workflows/release.yml) and [release checklist](https://github.com/arthursw/wetlands/blob/3ee2ffe1da7b6f1cfe97a8d88e6de67797d031d1/RELEASING.md).
Before a needed release, reconcile upstream, commit the reviewed versions/dependency ranges/lockfile, and require successful `ci.yml` for the exact release SHA; Wetlands additionally requires the documented full checks and Linux/macOS/Windows real-Pixi acceptance.
Configured PyPI Trusted Publishers and GitHub `pypi` environments are prerequisites; neither repository's environment had required-reviewer rules at verification, so these are not approval-gated publication examples.

**BioImageFlow/Core:** From its clean release checkout, preview then push the same selected package set; append `bioimageflow-core` to both tag commands only when Core also needs a release.
The helper returns annotated `<package>-v<major>.<minor>.<patch>` tags matching each package version at one commit, including `bioimageflow-v…` and, when selected, `bioimageflow-core-v…`.
Use its exact `release_tags` string; the dispatch validates CI/dependencies/artifacts and publishes in dependency order (`validate` is an optional artifact-only mode, not a required extra run).

```sh
uv run --no-project --with packaging python scripts/release_set.py tag --dry-run bioimageflow
release_tags="$(uv run --no-project --with packaging python scripts/release_set.py tag --push origin bioimageflow | jq -r .release_tags)"
gh workflow run release.yml --repo Inria-SAIRPICO/bioimageflow --ref main -f release_tags="$release_tags" -f mode=publish
gh run list --repo Inria-SAIRPICO/bioimageflow --workflow release.yml --limit 5
gh run watch RUN_ID --repo Inria-SAIRPICO/bioimageflow --exit-status
```

**Wetlands:** Set `WETLANDS_TAG` to the already pushed `v<version>` tag on the reviewed commit; its version must equal both `[project].version` and `WORKER_RUNTIME_VERSION`.
Publishing this GitHub release triggers the validated-build/trusted-publishing workflow; tag pushes or draft releases alone do not.

```sh
gh release create "$WETLANDS_TAG" --repo arthursw/wetlands --verify-tag --title "Wetlands $WETLANDS_TAG" --generate-notes
gh run list --repo arthursw/wetlands --workflow release.yml --limit 5
gh run watch RUN_ID --repo arthursw/wetlands --exit-status
```

Replace `RUN_ID` with the matching run and confirm its success plus every exact package/version on PyPI before updating platform/worker Core pins and certifying published wheels.
Wetlands also supports `gh workflow run release.yml --repo arthursw/wetlands --ref main -f tag="$WETLANDS_TAG"` for an existing non-draft release; use this recovery route instead of creating a second release, check PyPI first, and never replace uploaded files.
Earlier local/manual publication instructions describe historical releases; the current Wetlands route is the workflow above.

## Final acceptance

Use the existing audited `--campaign-local` selectors and `tests/campaign-local-scope.json` to cover complete in-scope backend, unit, Chromium, and Firefox collections.
Exact focused tests use ordinary selectors because campaign-wide selection cannot be combined with arbitrary grep/file filters.
Collect-only output establishes selection, not a pass; reconcile every selected, excluded, skipped, failed, and unrun case.
Also cover lint/types/build, logging-order certification, documentation, published common-tools compatibility (`scripts/test certification`), and real sequential-worker acceptance with the documented commands.
Choose comprehensive lanes only at final certification or when the change surface requires them; if a broad lane contains excluded behavior, report its broader scope or use the documented complete audited selections with the remaining checks recorded separately.
Record editable dependency SHAs as well as package versions; source-checkout results cannot silently become a published-package compatibility claim.
Do not repeat previously completed release/publication operations without a new required dependency fix.

Complete the campaign only when all implemented in-scope obligations have reconciled evidence, every primary GUI journey passes in Chromium and Firefox, demonstrated defects have a reviewed resolution, and native/external obligations have actual outcomes.
Native application execution belongs to M5 after automated and external phases; prerequisite inventory and headless tests never supply its credit.
An unavailable obligation remains blocked; explicit owner acceptance may permit closure with a named limitation, never a fabricated pass or a removed denominator cell.
Readiness alone, raw test counts, and historical dashboard percentages cannot establish completion.
The final report gives exact validation revisions/results/durations and any retained limitations, with clean committed task changes and a restartable checkpoint.


### Next bounded force/lifetime packet after configured policy

The current policy checkpoint qualifies app-phase delivery separately from open full/browser/published/native certification.
The next library-owned force contract begins with preservation-first reconciliation of the observed four-ahead/two-behind histories and dirty held library/T1 inputs; do not reset, overwrite, import whole WIP trees or publish automatically.
The reviewed boundary is strict selected-owner close → public managed removal → provision with replacement false → start → cache publication, preserving False warm reuse, retry ownership on failed close and established best-effort stop.
Platform physical admission/cancellation and later published API pins/worker compatibility require their own aligned acceptance; conditional readiness is not implemented or released behavior.

## Measured platform performance repair queue — October 2

Use common-task request and accepted-graph/paint measurements alongside architecture review; test-command duration is not application latency.
The accepted first repair uses one saved `WorkflowFile` capture per existing locked draft-synthesis phase, preserving fresh unlocked-phase generation/saved/draft rechecks, full workspace migration admission, compilation, source freshness and agent context.
Then coalesce simultaneous workflow-tree requests without caching away later mutations or failed-request retries; request-local shared environment discovery and a single dataset-list reconciliation are smaller candidates to validate at their owning boundary.
For workflow-tree coalescing, prove two passive consumers share one pending request within the same endpoint/authority epoch; mutation or authoritative-event refresh must admit a fresh epoch, stale responses/finalizers cannot publish or clear newer ownership, and failure clears its own pending record for later retry while the existing bounded stale-generation retry remains and does not self-await.
Then verify two→one duplicate startup requests and accepted-graph latency with the same fixture before one proportionate frontend/browser completion; this work bound implies no twofold latency gain.
Folder/ancestry indexes, affected-node dynamic schema refresh and library/Core repeated preparation/codec work remain conditional source candidates until relevant task evidence establishes value and contract safety.
Use the same disposable cardinalities and cache assumptions for before/after investigation, report request multiplicity separately from user latency, and avoid absolute timing assertions in CI.
Develop with distinguishing functional regressions and owner checks, then one proportionate scoped completion/docs gate for the accepted repair wave; use app at cross-stack milestones; retain unmeasured cold provisioning, results/dense graphs and published/worker/native limits.
Do not create a benchmark subsystem, broaden frozen M1 inventory or rewrite the suite to obtain these measurements.

After this measured draft repair and its scoped backend/docs gate, resume the preservation-first library force-Recreate/lifetime packet before the separate workflow-tree singleflight repair; both preserve the published/worker/native certification boundaries.
