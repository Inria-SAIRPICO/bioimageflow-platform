---
orphan: true
---

# Platform testing implementation plan

Test and strengthen the platform by exercising its main GUI features, fixing demonstrated bugs, and delivering a complete, systematic suite for every implemented feature within the campaign scope.
A finished user journey with correct visible results and durable state is the unit of progress.
Priorities determine execution order, never permission to omit lower-priority features from final coverage.
The authoritative validation commands and completion requirements remain in [Test lanes](../testing.md).

## Scope and current product contract

Cover implemented desktop and webapp behavior from v1/v2 and applicable later implemented specification changes, following the authority order in `PLATFORM_CONTEXT.md`.
Exclude parallel scheduling, HPC, Parsl, managed remote execution, and distributed engines from campaign certification.
Record these exclusions explicitly; neither existing out-of-scope regression tests nor future v3 proposals expand campaign scope.
Keep Direct for ordinary DataFrame-only workflows and use real local Wetlands workers sequentially with one worker when worker behavior is being certified.
Distinguish mocked orchestration, Direct computation, and actual worker execution; worker claims require process identity, exact results, generated files, and cleanup.

The owner-approved catalog contract is single-click to open/toggle the bottom tool-information panel and double-click to add exactly one node to the active canvas.
Drag-and-drop remains a separate creation gesture; secondary row actions must not trigger inspection or creation accidentally.
Use this contract in all fixtures and acceptance criteria; historical ISSUE-003 single-click creation evidence describes an earlier interaction.

Preserve assertions and product intent when repairing tests or code.
Do not weaken expectations, hide skips or warnings, invent graph conversions, or introduce compatibility shims to obtain a pass.
Update affected code, tests, fixtures, specifications, and documentation together when behavior changes.

## Orchestrator, delegation, and context discipline

The main agent must be **GPT-5.6 Sol with high reasoning**, acting primarily as an orchestrator.
Ordinary implementation workers use **GPT-5.6 Sol with medium reasoning**; bounded specialist investigations use **GPT-6 Astra with high reasoning**.
These are requested runtime settings; editing this plan does not change the currently selected model.
Use [Restart instructions](platform-test-start.md) to start the requested orchestrator and verify the client settings.

The orchestrator owns the global feature map, priority and dependency decisions, task assignment, review, integration, validation reuse, and accurate reporting.
Workers own detailed source investigation, fixture design, implementation, focused tests, and their worktree completion checks.
The orchestrator may make small integration/documentation edits and inspect relevant code to review a result; it should not duplicate an entire worker investigation.

Keep the orchestrator's working context to the current objective, a short feature-status table, active tasks, open decisions, and the next three runnable tasks.
Read the active checkpoint, relevant inventory rows, and changed code as needed; retrieve historical evidence only when a decision depends on it.
Workers receive fresh bounded packets with `fork_turns="none"`, explicit model/reasoning, a worktree path, feature/issue IDs, current contract, owned paths, acceptance criteria, dependencies, required checks, and escalation conditions.
Worker handoffs should normally fit in about 30 lines: outcome, bug/cause, commit, changed files, exact commands/results/durations/exclusions, unresolved concerns, and evidence paths.
Keep raw logs, traces, and exploratory transcripts in ignored task artifacts; return only phase summaries and relevant failure excerpts to the orchestrator.
Do not repeatedly request unchanged status or ingest complete passing test output.
While a worker runs, review another independent feature's coverage or prepare the next bounded task; use completion notifications and concise milestone updates.
For a remote CI, validation, or publication run, record its URL and exact source revision, then poll only for meaningful state changes while continuing independent work.
Do not repeatedly ingest complete job payloads when the run status and first failing step are sufficient.

Use at most two independent ordinary workers concurrently, including while a specialist review is pending; reserve the remaining agent slot for Astra or urgent integration review.
Do not fill a free slot merely to maximize parallelism, and do not start two browser-heavy completion lanes at once when their shared machine resources could make failures ambiguous.
Parallel writable tasks require separate worktrees under `.worktrees/<task_name>` with independent dependencies and runtime state as required by `AGENTS.md`.
Give each task one coherent user journey or issue, the related `ID.cell` obligations it may close, explicit write ownership, and a completion-check choice from `docs/testing.md`.
Prefer one representative success plus its immediate refusal/recovery and identity assertions in an existing journey when that closes related cells without turning the test into a long multi-feature chain.
Do not split tightly coupled fixes into one-cell assignments merely to occupy agents; do not add duplicate browser journeys when strengthening an existing one supplies the missing evidence.
Read-only investigations may share the primary checkout.
A blocked feature does not block independent work unless its fixture, contract, or safety issue affects them too.

### Commit and integration boundaries

Commit each coherent validated issue or feature immediately when resolved, together with its tests and relevant inventory/specification updates.
Do not start another writable task in that checkout until the previous completed task is committed.
Workers review and commit only their own task changes on their branches; the orchestrator reviews the commit, integrates it, and records the resulting revision and evidence.
Shared progress/issue records belong to the orchestrator; integrate their updates at the same task boundary and commit them promptly if they cannot be included in the implementation commit.
At that boundary, update the inventory, dashboard, evidence, and short checkpoint together, run `scripts/test check campaign` once on the consolidated campaign-documentation diff, and commit the documentation with or immediately after the feature commit.
Run `scripts/test check docs` for a documentation structure/navigation change, a substantial documentation milestone, and final certification; its Sphinx build is not needed for every status or inventory update.
Use the dashboard verifier for interim count checks; avoid separate administrative ownership, status, and worktree-archival commits when one resolved-batch record suffices.
An interruption, open defect, remote milestone, or new owner decision still requires an immediate durable record rather than waiting for unrelated work.
Do not accumulate resolved independent issues, stage another worker's files, or include temporary plans and raw logs in commits.
An unfinished failing reproduction remains explicitly unfinished; preserve its owner, worktree, selector, and evidence before interruption without claiming a passing fix.
After integration, move the clean completed worktree to trash with `mv`, prune its registration, and delete only its integrated branch, following `AGENTS.md`.
Preserve unrelated user worktrees and changes.

## Tiered GUI-first priority queue

Completed dependency releases, fixture repairs, and audited scope selection are retained prerequisites, not tasks to restart.
Use the current checkpoint to select the first unfinished item below.
Finish every runnable basic/common item before assigning an important extension, and finish important extensions before assigning advanced, native, or external edge cases.
Do not let an easily available specialist fixture or manual environment displace a higher-tier GUI gap.
Interrupt this order only for a reproduced security, data-loss, corruption, or wrong-result defect; record its reachable user impact and return to the highest unfinished tier after the repair.

| Tier | Scheduling rule | Included work |
| --- | --- | --- |
| 1A — Basic/common readiness | Mandatory first. The Basic-Use Readiness Gate may be evaluated when this exact subset is closed. | The stable-ID/cell matrix below: ordinary workspace lifecycle, catalog/canvas construction and edits, durable Save/Save As/delete/recovery, Direct Run and result inspection, plus immediate loss, wrong-result, and wrong-identity boundaries. |
| 1B — Important primary-GUI extensions | If the owner continues after the gate, close this tier before non-primary work. | Every remaining dashboard row marked `Primary GUI: yes`, including broader clipboard/shortcut variants, grouping and recursive editing, real-worker failure/cancellation, cache lifecycle, richer result combination/export, and their applicable scenario boundaries. Thus `Primary GUI` remains the broader Tier 1 campaign scope, not the gate denominator. |
| 2 — Important extensions | Start only after Tier 1B is closed. | Common but non-primary user features recorded as P1 or equivalent in the dashboard, including layout/settings, datasets, catalog administration, package/custom-tool management, source operations, authoring/editor controls, diagnostics, and other non-primary GUI workflows. |
| 3 — Advanced/external boundaries | Start only after Tier 2 is closed, except for a time-bound external appointment that does not consume a higher-tier worker. | P2 specialist behavior, native desktop dialogs and packaging, real external editors/viewers/credential stores, application crash/restart, uncommon integration and permission boundaries, and final manual/external acceptance. |
| Final systematic closure | Mandatory for a complete campaign claim, whether performed continuously or resumed after a pause. | Every remaining applicable obligation in all tiers, denominator reconciliation, complete deterministic and external certification, and owner disposition of manual limitations. |

The earlier waves remain useful evidence and ordering history: ISSUE-005, the main create/run journey, everyday editing, nested workflows, and execution/results are completed batches only to the extent recorded in the dashboard and evidence file.
Within Tier 1, take the highest-reach unfinished normal GUI path first, then its immediate loss/wrong-result/refusal/recovery boundaries, before less frequent variants of the same feature.
Rank the next batches by ordinary user frequency and the impact of an incorrect result, lost work, or wrong identity; use the dashboard's remaining cells to choose the batch, not a convenient isolated test or a raw test-count target.
The three detailed inventories remain the feature backlog; this tier table classifies scheduling and does not replace or shorten them.

Build small independent journeys around these batches instead of one long test whose early failure hides later features.
Each family needs a representative successful user path before expanding its unusual scenarios, except when a known high-impact failure must be fixed first.
Reuse existing adequate journeys and strengthen missing assertions; do not recreate coverage merely to add test counts.
Limit runner/manifest work to enabling a required check, correcting a proven selection defect, or supplying missing final evidence.
A new combined campaign command is optional; the existing audited selectors can support final certification without another infrastructure project.

## Basic-Use Readiness Gate

The **Basic-Use Readiness Gate** is an optional owner decision point between Tier 1A and the remaining campaign.
It can authorize a pause or early stop of active campaign work, but it never means the systematic campaign is complete and never removes a Tier 1B, Tier 2, Tier 3, manual, external, or final-certification obligation.
The orchestrator may present this decision only after all requirements below pass on one reconciled current revision.

### Exact basic-use scope

The gate deliberately uses a smaller fixed subset than the broader `Primary GUI` denominator.
It proves that an ordinary user can create and edit a simple workflow, preserve its identity and work, execute it through Direct, and inspect exact results; grouping, recursive workflows, real-worker lifecycle, result bundles, native applications, and specialist authoring remain explicit later obligations.

The following stable IDs and required scenario cells are the auditable gate denominator.
`S`, `R`, `F`, `P`, and `B` retain the dashboard meanings; omitted cells remain campaign obligations but do not block this gate.

| Basic workflow | Stable ID and required cells |
| --- | --- |
| Reach an empty workspace, create/open/switch/delete the intended workflow, and never mutate or recreate the wrong identity | `GUI-SHL-002`: S, P; `WF-LIF-002`: S, P, B; `WF-LIF-003`: S, P, B; `WF-LIF-010`: S, F, P, B |
| Inspect a catalog tool; add, connect/disconnect, configure, rename, select/enable, delete, and undo/redo through visible controls | `GUI-EDT-001`: S, R, P, B; `GUI-EDT-003`: S, P; `GUI-EDT-004`: S, P, B; `GUI-EDT-006`: S, R, F, P, B; `GUI-EDT-007`: S, R, P, B; `GUI-EDT-008`: S, P, B; `GUI-EDT-009`: S, R, F, P, B; `GUI-EDT-010`: S, R, F, P |
| Save/reopen the accepted graph and recover, cancel, keep, or discard ordinary dirty/conflicting state without loss | `WF-LIF-004`: S, R, F, P, B; `WF-LIF-011`: S, R, F, P, B; `WF-LIF-012`: S, R, F, P, B; `WF-LIF-014`: S, R, P, B |
| Run the accepted simple graph through Direct, refusing invalid or mismatched accepted input, with exact durable result identity | `RT-EXE-001`: S, R, P; `RT-EXE-004`: S, R, P, B |
| Inspect exact table results and a representative bioimage/file result through the ordinary browser GUI | `RT-RES-001`: S, P, B; `RT-RES-007`: S, B |

This matrix contains 73 required cells at the current stable-ID baseline.
The required `R`, `F`, and `B` cells are limited to ordinary invalid-value refusal/recovery, destructive-action cancellation, stable graph/result identity, accepted-revision safety, and isolation from the wrong workflow or canvas.
Broader Run Selected recovery, viewer error handling, and enablement recovery remain owned by Tier 1B; they are not silently counted in this gate.
If reconciliation splits or aliases one of these rows, update this matrix explicitly in the same commit and preserve the equivalent user outcome; do not silently expand or shrink it through a dashboard label change.
The detailed inventories remain authoritative for selectors and assertions, while the dashboard remains authoritative for each cell's credited state and evidence revision.
The gate passes only when all 73 required cells are `V` on the evaluated revision; `G`, `I`, `B`, or `U` in this matrix is a failed gate.

Recompute the gate at every evaluation rather than carrying its prior percentage forward.
First run `python3 scripts/verify-platform-test-dashboard.py` on the evaluated revision, then look up each `ID.cell` named above in the verified dashboard and tally `V`, `G`, `I`, `B`, and `U`.
Record `V / 73` and `100 × V / 73`, followed by every non-`V` cell as `ID.cell=state`, grouped into runnable gaps (`G`), active work (`I`), external blockers (`B`), and unassessed work (`U`).
A required cell unexpectedly changed to `N`, or a row split/alias, invalidates the fixed denominator until this matrix and rationale are reviewed in the same commit.

### Blockers, reachability, and acceptable limitations

A current-revision finding blocks the gate when a supported basic-use GUI path can reach it from ordinary prerequisites and it has either of these effects:

- critical impact: security or permission escape, data loss/corruption, wrong workflow/result identity, wrong scientific result, or mutation of an unrelated workflow;
- high impact: a gate workflow cannot complete or recover through its specified controls, has no reasonable in-product workaround, or fails deterministically or repeatedly in a required gate check.

The finding record must include the supported deployment, visible entry steps, deterministic fixture or preconditions, affected user outcome, exact selector or manual procedure, and source revision.
An artificial dependency state that the platform neither installs nor exposes does not block the gate unless it demonstrates a safety failure against state produced by a supported path.
Moderate degradation with a safe in-product workaround and cosmetic, performance, or convenience defects do not block the gate only when their affected dashboard cells are outside the gate scope; record them in the durable backlog instead of weakening an assertion.

The gate may leave Tier 1B, Tier 2, and Tier 3 work incomplete, including grouping/recursive workflows, real-worker lifecycle, richer exports, package and custom-tool administration, uncommon source/authoring flows, native dialogs, packaged-window behavior, real editor/viewer/credential-store interaction, application crash/restart, and other manual/external boundaries.
Unavailable visible-display infrastructure may use the artifact-backed headed-confidence alternative below.
Scope exclusions already named in this plan remain exclusions, not limitations and not passing evidence.
No skip, deselection, unresolved flake, reachable data/wrong-result/loss defect, or missing required gate cell is an acceptable gate limitation.

### Current-revision evidence and owner decision

Evaluate a single clean integrated revision after reconciling all completed feature branches, inventories, and the dashboard.
Historical browser evidence remains useful for diagnosis but cannot by itself pass the gate on a later revision.
Record one source SHA and run, without intervening product changes:

- `scripts/test check backend`, `scripts/test check frontend`, and `scripts/test check docs`;
- every exact browser selector and required deployment variant credited to the 73 required cells in Chromium and Firefox, using the source inventories to avoid substituting a neighboring test; a same-revision `scripts/test check browser-all` pass may supply the browser evidence when its complete collection contains all of those selectors;
- any gate-scope manual procedure that cannot be represented in those lanes, if dashboard applicability explicitly requires it.

Do not make an unrelated Tier 1B, Tier 2, or Tier 3 browser failure a hidden gate requirement by demanding a broader lane when the exact gate selection is sufficient.
A broad current-revision lane is welcome evidence, but if it fails outside the gate matrix, record that risk in the backlog and still evaluate the gate selectors independently.

At least one representative create/edit/connect/run/inspect/save/reopen journey must also pass headed in Chromium on that same revision when a visible display is available.
Record the selector and observation as confidence only; assertions remain authoritative.
If no visible display is available, retain trace/video/screenshots from the same current-revision journey, record that no window was shown, and treat this as an acceptable confidence limitation rather than a passed headed run.

After all gate-scope cells and checks pass, commit a durable gate checkpoint before asking the owner whether to **continue now through Tiers 1B, 2, and 3** or **pause/stop now with the systematic campaign incomplete**.
Do not infer the decision from a request for status, and do not stop early on the orchestrator's initiative.
If the gate fails, continue the highest-priority Tier 1 repair or report a genuine owner blocker; an early-stop choice is not yet available.

An early-stop checkpoint must record the evaluated SHA, clean/integration state, commands/results/durations and any retries or exclusions, headed or artifact evidence, reachable blocker audit, dashboard denominator revision, overall and primary-GUI verified/applicable percentages, blocked/unassessed counts, and the first three resumable backlog actions.
It must list outstanding Tier 1B, Tier 2, Tier 3, manual/external, limitation, and risk categories by links to their owning inventories rather than duplicate their rows.
Label the state **basic-use gate passed; systematic campaign paused/incomplete** and preserve the final certification gate unchanged.

## Complete and systematic feature coverage

Priority is separate from coverage status: every in-scope feature remains mandatory.
Maintain stable feature IDs in the existing [GUI](coverage-gui.md), [Workflow](coverage-workflows.md), and [Runtime](coverage-runtime.md) inventories; assign IDs as rows are reconciled and use them in worker packets and handoffs.
Each row records authority, actual implementation, user outcome, priority, applicable scenarios, exact selectors, required levels, deployment/browser variants, owner/status, and evidence revision.
Use explicit states: `unassessed`, `gap`, `in-progress`, `blocked`, `verified`, or `out-of-scope`.
For each applicable scenario, record the assertion or gap; record a reason for any `not-applicable` decision.
Historical inspection or a passing mock is not proof of an untested real integration.

The inventories must cover at least these families, expanding them when specification or UI inspection finds more implemented features:

| Feature family | Mandatory coverage dimensions |
| --- | --- |
| Startup, modes, workspace, and layout | Empty/nonempty startup, workspace switching, restore/reopen, tabs/docks/panels, settings load/save/reset, persisted layout/preferences, desktop versus webapp availability. |
| Workflow lifecycle | Create/open/save/save-as, draft recovery/discard/conflict, rename/move/folders, duplicate/delete, import/export, independent graph/source copies, identity-safe lifecycle changes. |
| Catalog and canvas editing | Search/filter/information, single/double-click/drag behavior, metadata/pins, node/edge types, connect/reconnect/disconnect, parameter control types/defaults/reset, rename, selection, collapse/enable, clipboard, undo/redo, shortcuts/focus, pan/zoom/fit, validation feedback. |
| Recursive workflows and sources | Group/embed, interfaces/bindings/stable IDs, private nested edits, apply/discard/reopen, parent conflicts and destructive confirmation, provenance/detach/update, recursive owned-source transport. |
| Tools, packages, and authoring | Package discovery/version/install/uninstall/error paths, custom creation/rename/delete, valid/invalid hot reload and recovery, catalog versus bound source opening, editor lifecycle, Python preview/apply/cancel, materialized graph reopen. |
| Local execution | Real Direct and sequential worker paths, accepted snapshot/Run Selected, enablement/dependencies, progress/status/log attribution, mutation lock, failure/cancel/retry, cached versus recomputed output, reconnect and recovery. |
| Results and data | Exact table values, columns/row lineage, merged/stacked results, selection/navigation, pagination/width preferences, images/thumbnails/viewers, output templates/files, exports/bundles and readiness/error states. |
| Datasets and integrations | Upload/select/organize/move/delete/download, partial failure and path boundaries, implemented OMERO controls, filesystem dialogs, editor/viewer actions and actual external capabilities. |
| Cross-cutting contracts | REST/schema validation, WebSocket delivery/reconnect, error history and navigation, MCP operations to accepted draft/GUI, ownership and persistence, permissions/path safety, native packaging and crash/restart boundaries. |

For every feature assess: normal success; invalid input/refused action; cancel/failure/recovery; persistence/reload; and applicable identity, concurrency, ownership, and permission boundaries.
Choose meaningful representative cases and lower-level tests for larger state spaces instead of requiring every possible Cartesian combination.
Every user-visible in-scope action needs behavioral UI evidence on its supported surface, plus lower-level assertions for the important contracts it depends on.
Every primary GUI journey must pass in Chromium and Firefox at final acceptance.
Test desktop/webapp differences explicitly rather than assuming one browser project proves both deployment modes.
Assign genuine native/external boundaries reproducible manual or integration acceptance steps; mocks certify only the controlled boundary.

At the end of each feature batch, reconcile its rows against actual assertions.
At the end of each priority wave, scan implemented specification sections and visible menus/panels/routes for features absent from the inventories.
Final closure requires that this reconciliation covers all implemented in-scope features, not merely the initial shortlist.

### Coverage dashboard and completion denominator

Before Wave 6 expands into the remaining feature families, normalize each inventory into an auditable dashboard.
The canonical normalized denominator is the [platform test obligation dashboard](platform-test-dashboard.md); the three detailed inventories retain its selector, assertion, manual-procedure, and gap evidence.
Every implemented user action or contract must have a stable feature ID and explicit fields for priority, supported surface, applicable scenario obligations, selectors or manual procedure, browser/deployment variants, status, and evidence revision.
Scenario obligations are normal success, invalid or refused action, cancellation/failure/recovery, persistence/reload, and applicable identity/concurrency/ownership/permission boundaries; mark a dimension `not-applicable` only with a short reason.

Campaign completion percentages must use this dashboard rather than subjective estimates or raw test counts.
Report both `verified applicable obligations / total applicable obligations` and the same ratio for primary GUI obligations, with blocked and unassessed counts shown separately.
A dashboard count is provisional until all five dimensions of every inventory row have been reconciled to a concrete source-row scenario contract or a justified `not-applicable` reason and the checked-in dashboard verifier passes.
Remove the provisional label only after that complete reconciliation; a partial example audit must not be reported as the canonical denominator.
A feature row is `verified` only when every applicable obligation has exact evidence; a partially covered row remains `in-progress` or `gap`.
Reconcile the denominator whenever implementation or specification discovery adds or removes an in-scope feature, and record the revision that changed it.
Do not begin final certification while any inventory row lacks a stable ID, an applicability decision, or a status.

## Per-feature testing and repair loop

1. Pick the highest-priority runnable feature and inspect its contract, current implementation, and existing assertions.
2. Prepare a realistic small fixture with known tool metadata, required parameters, compatible bindings, expected data, and intended validation state; anticipate ordinary dialogs before a browser run.
3. Exercise actual UI controls through the real frontend/backend and assert visible results plus accepted/persisted state.
4. If it fails, preserve the exact selector/browser/revision, first relevant error, trace, and state before cleanup; distinguish fixture, product, environment, and specification failures.
5. Fix a demonstrated defect with a small regression at the lowest useful layer, then prove the affected UI outcome.
6. Run the required focused and completion checks, update the feature evidence, commit immediately, and integrate.

API setup is acceptable for a prerequisite not being certified in that test; verify the exact opened workflow and accepted graph before interaction.
Do not claim GUI creation/editing coverage when the operation under test was performed through an API, internal store, handler call, or direct file edit.
Do not claim real execution from an intercepted Run request, nor readable image/result correctness from placeholder bytes.
Use exact expected data, independent file/output oracles where appropriate, and state-based readiness; avoid arbitrary sleeps and snapshots that merely echo current implementation.

### Visible browser confidence checkpoints

Playwright remains authoritative in headless mode for repeatable automated browser evidence.
At the end of each major GUI wave, also run one representative primary journey with `--headed` when a visible display is available, so the owner can observe the actual browser interaction.
Record the selector, browser, revision, and outcome as a confidence checkpoint, but do not substitute visual observation for assertions or count it as separate feature coverage.
If a visible display is unavailable, retain a Playwright trace, video, or screenshots for that representative journey and record the limitation; do not claim that a browser window was shown.

Use `scripts/test focus` without campaign-wide selection flags for exact failing selectors.
After a fix, run the exact test once; use `--repeat-each=5` only for a suspected timing/race defect.
Follow a strict test ladder: reproduce the exact failure, fix and rerun that selector, then run the next previously unrun check in the smallest applicable completion lane.
If that next check fails, stop there and focus on its exact failure; do not restart the lane from the beginning merely because an earlier case was repaired.
Carry forward passing phase results only while their source, fixtures, dependencies, and relevant environment remain unchanged; if a later edit invalidates a phase, rerun that phase before claiming completion.
Run the applicable completion lane from `docs/testing.md` before declaring the batch complete.
For a localized test-only cross-browser assertion, run its exact Chromium and Firefox selectors, then the documented localized cross-browser completion check; for a browser interaction or persistence implementation change, honor the documented browser completion lane.
Do not add a complete browser-project run to a passing localized batch solely for reassurance; reserve broad browser acceptance for substantial GUI milestones, browser/E2E infrastructure changes, and final certification.
Budget **one broad browser-lane attempt per substantial milestone** unless the owner explicitly requests another or a later broad browser/E2E change itself requires that lane under `docs/testing.md`; a failed attempt is an honest milestone limitation, not an automatic instruction to run the entire lane again.
When a broad lane fails late, stop broad reruns for that milestone, retain its unchanged successful cases and phase results, reproduce the exact failed selector in its browser, and run only the smallest checks invalidated by a demonstrated fix.
After a localized test or product repair, use the exact affected browser selectors and the documented scoped completion check; do not restart a full Chromium/Firefox project merely to turn an unrelated prior red result green.
Revisit broad acceptance at the next scheduled milestone or final certification, or when the changed surface genuinely requires a new broad lane; record the prior red lane, its source revision, first failure, unrun count, and whether any focused reproduction passed.
Completing all Tier 1B primary-GUI obligation cells is a coverage result distinct from a passing broad browser lane; a red or interrupted broad lane must remain visible as a certification limitation and owned issue, not erase valid cell evidence or be described as a pass.
Do not stack quick, scoped, and full checks when the later scheduled command subsumes the earlier work.
Run comprehensive browser acceptance at substantial milestones and final certification, not after every edit or every late-suite flake.

## Autonomous repair and escalation

Sol workers may repair routine, bounded defects autonomously when the intended behavior is explicit, the cause is reproduced or decisive, and regressions preserve the contract.
Use Astra/high for conflicting specifications, unclear library semantics or fixture validity, identity/data-loss risk, a proposed semantic redesign, or one unsuccessful bounded repair whose cause remains unclear.
A production failure alone does not require specialist escalation if those conditions are absent.
Before escalation, a Sol worker should capture the smallest reachable reproduction, authoritative contract, likely ownership boundary, and failed bounded attempts; a routine local event-wiring or assertion defect with clear intent stays with Sol.
For a risky change, send Astra one bounded decision packet with an explicit invariant checklist covering identity, concurrency, persistence, rollback, and affected user-visible outcomes.
Request another Astra pass only when the implementation materially changes those invariants or a concrete unresolved safety concern remains; record each pass and its disposition in the issue or evidence record.

Before classifying a finding as release-blocking or P1, record the exact reachable platform entry path, credible trigger, affected user outcome, and smallest reproduction.
An artificial dependency state that platform code neither installs nor exposes is a dependency follow-up unless it demonstrates a reachable safety or correctness failure.
Limit the resulting claim to the tested boundary; reachability review must not dismiss a reproduced data-loss, security, wrong-result, or writer-lifecycle risk.

The orchestrator records an issue and freezes dependent changes, then sends one bounded fresh-context investigation to Astra.
Only describe an issue as `astra-review` after a specialist is actually assigned; otherwise it is `open` with a queued next action.
Astra returns `safe-to-fix` with contract/cause/repair/regressions, `not-a-defect` with supporting evidence, or `needs-owner` with one concrete unresolved decision.
For `safe-to-fix`, Sol implements and validates; for `not-a-defect`, correct the test/inventory without inventing new behavior.
If Astra cannot establish a safe contract and returns `needs-owner`, pause the campaign and ask the owner one concrete question with the evidence.
Independent features may continue while a bounded specialist investigation runs unless the concern affects shared foundations.
Record unavailable services/credentials as `externally-blocked` with recovery steps; neither slowness nor infrastructure failure establishes a product defect.
Missing required model capability is a configuration blocker; never silently substitute or claim a review occurred.

## Final certification and completion gate

Use the existing per-case audited selectors in `docs/testing.md` and `tests/campaign-local-scope.json`.
Frontend-unit/browser campaign selectors require complete collections; use ordinary focused commands for individual cases.
Audit exact exclusions and ensure newly added tests are selected; collection-only output proves selection, not successful execution.
Scope exclusions must not drop local assertions from mixed tests; split such tests when necessary.
Preserve out-of-scope tests in the normal regression suite.

Final certification must cover the complete in-scope backend and frontend suites, every in-scope Chromium and Firefox journey, backend logging-order checks, lint/type checks/build/docs, published common-tools compatibility, and real sequential-worker acceptance.
Use `scripts/test` with documented commands; record the actual scoped commands when an unmodified broad lane would include excluded campaign features.
External package and worker checks must actually run for their respective certification claims, using the published locked dependencies and independent runtime state.
Retain completed release evidence; reopen library release work only for a new necessary library fix, following its documented release/CI requirements.
The existing release authorization and library-required CI do not expand platform campaign scope.

The orchestrator must verify all of the following before claiming completion:

- Every implemented in-scope feature has inventory rows and all applicable scenarios are verified, with justified test levels and exact evidence.
- Every primary GUI journey passes on both browsers, with correct data and persistence; no primary action is represented only by rendering or mocks.
- Demonstrated bugs are resolved and committed with regressions; no unresolved in-scope defect or silently skipped/flaky test is counted as passing.
- Collected/selected/excluded/skipped/failed counts reconcile for every suite; each exclusion has its explicit scope reason.
- Manual/native/external obligations have recorded outcomes using [Manual Platform Testing](manual-testing.md); any unavailable obligation remains blocked.
- Every completion record identifies command, revision or diff, duration, results, retries/exclusions, packages, and limitations; the relevant integrated revision is validated.
- Task worktrees are integrated/cleaned up, shared records agree, and the checkout is clean apart from explicitly identified unrelated user work.

If a required manual or external check remains unavailable, report automated coverage achieved and the outstanding obligation; the campaign is incomplete unless the owner explicitly accepts the limitation.
Owner-accepted limitations remain visible as limitations, never reclassified as passed tests.
Test counts, line coverage, or completion of only the high-priority wave do not establish comprehensive coverage.

## Durable state and restart

[Campaign progress](platform-test-progress.md) owns the short current objective, prioritized feature summary, active ownership/worktrees, open decisions, and next three actions.
[Campaign issues](platform-test-issues.md) owns open defect decisions, the coverage inventories own detailed feature obligations, and [Campaign evidence](platform-test-evidence.md) owns concise current-task validation.
Completed checkpoint, issue, and validation history lives in the dated [progress](archive/platform-test-progress-through-tier-1b.md), [issue](archive/platform-test-issues-through-tier-1b.md), and [evidence](archive/platform-test-evidence-through-tier-1b.md) archives.
Ordinary restarts and worker packets must not load those archives; consult a specific archived entry only when a current claim, invalidated check, or decision needs an audit.
Keep each fact in its owning record and link to it; remove obsolete next actions when a task is integrated.
Record historical product contracts as historical, including superseded catalog single-click creation.
Update durable records at every completed task, escalation, and interruption; do not create administrative commits solely for unchanged status.
Remote milestones are completed task boundaries: after a required CI gate passes, a package is published, or a dependency becomes available, update the checkpoint and evidence and commit that durable state before starting another unrelated writable task.
After an interruption, reconcile remote workflow and package-index state before repeating or resuming release operations.
Status questions steer the ongoing campaign: answer briefly, then continue unless the user asks to pause or change the objective.
Before restart, preserve unfinished work/evidence and reconcile actual Git/worker/process state; never rely on a prior conversation or temporary logs to identify the next task.
