---
orphan: true
---

# Platform confidence campaign evidence

Started 2026-09-30; current executed results are recorded below, separately from historical coverage.
Documentation validation for preparing this campaign does not establish any product readiness outcome.
The [checkpoint](platform-test-progress.md) owns baseline and queue; the [plan](platform-test-plan.md) owns acceptance and evidence rules.

The [previous active evidence](archive/platform-test-evidence-before-2026-09-30.md) preserves the September increments and their red/interrupted lanes, exact revisions, and limitations.
The older [Tier 1A–1B evidence archive](archive/platform-test-evidence-through-tier-1b.md) retains preceding runs and release history.
Consult only the historical entry needed to audit a claim; do not repeat completed releases or checks without an invalidating change.

## New execution records

For each completed batch record:

- Outcome and inventory IDs; evidence type and exact asserted boundary.
- Command/selector/browser, tested revision or named diff, integrated revision, and dependency baseline.
- Result and duration; retries, skips, deselections, excluded scope, failures, and unrun cases.
- Artifact path or durable concise failure excerpt; any reused phase's original revision and why it remains applicable.

Separate available test code, passing focused execution, scoped completion, and native/external certification.
Workers' planned commands and prospective status edits receive no evidence credit.

## Wave 1 execution — 2026-09-30

Source: platform `29733fafb7a27ccc749db0b78490e2bada35edd8` plus named J1/J3 readiness assertion diff, SHA-256 `f3309b087fe644144af690b87521c22630835937117a6b050d6888c18388d044` over the two test-file diffs.
Dependency baseline: clean editable sibling library `dff04e3eb7c15ded7984aa6b0befa44febe4cb37`, BioImageFlow 0.8.6/Core 0.4.1, registry Wetlands 2.4.2, Python 3.13.2, Bun 1.4.2; existing prepared checkout dependencies reused, no installation/download setup recorded for these runs.
All commands use `scripts/test focus e2e`, fresh disposable local backend/frontend runtime roots and allocated ports, one Playwright worker, no configured local retries, and fail-fast after the first failure.
Evidence type is **real GUI + backend** with actual Direct computation and exact accepted graph/result observations; it supplies no Wetlands-worker, native viewer or published-package certification.
No broad completion check or integrated repair claim is supplied by these initial focused runs.

| Outcome | Exact command after `scripts/test focus e2e` | Result and time | Assertions/artifacts |
| --- | --- | --- | --- |
| J1 | `tests/e2e/canvas-interactions.spec.ts --grep 'builds, runs, inspects, saves, and reopens a real workflow through the GUI' --project=chromium --project=firefox --trace=on --output=test-results/campaign-j1` | 2/2 passed, lane 49 s / elapsed 49.24 s; Chromium 9.9 s, Firefox 9.4 s | Catalog gestures, draft graph, captured execution backend `direct` and workflow/draft identity, exact displayed rows, Save/Open equality. Both `frontend/test-results/campaign-j1/*/trace.zip` retained. |
| J2 | `tests/e2e/canvas-interactions.spec.ts --grep 'recovers a real Direct failure without publishing a partial result' --project=chromium --project=firefox --output=test-results/campaign-j2` | 2/2 passed, lane 23 s / elapsed 23.20 s; Chromium 5.8 s, Firefox 9.3 s | Deliberate Controlled Direct failure, no partial target, exact retained upstream data, GUI correction and distinct successful run, accepted identities/reload. Expected fixture error log is not a failing test. |
| J3 initial | `tests/e2e/nested-execution.spec.ts --grep 'opened nested canvases inspect the results of their own instance' --project=chromium --project=firefox --output=test-results/campaign-j3 --trace=retain-on-failure` | Chromium failed, Firefox did not run; lane 19 s / elapsed 19.30 s | Distinct sibling sources expose reload/activation failure after reopened internal node selection: expected two columns, saw one body cell. `frontend/test-results/campaign-j3/*/trace.zip` and error context retained. |
| J3 exact reproduction | `tests/e2e/nested-execution.spec.ts --grep 'opened nested canvases inspect the results of their own instance' --project=chromium --output=test-results/campaign-j3-reproduce --trace=on` | 1/1 failed, lane 18 s / elapsed 17.40 s | Same reopened-instance path loses its second visible cell. `frontend/test-results/campaign-j3-reproduce/*/trace.zip` retained; correct second-instance rows and immutable identity are returned by the backend, while visible canvas/selection reverts to root public output. Cause is under bounded diagnosis, not attributed to the historical intermittent issues. |
| J4 | `tests/e2e/everyday-node-editing.spec.ts --grep 'quarantines a corrupt selected record through GUI Clear and reruns exact rows' --project=chromium --project=firefox --output=test-results/campaign-j4 --trace=retain-on-failure` | 2/2 passed, lane 27 s / elapsed 26.83 s; Chromium 6.7 s, Firefox 11.9 s | Real selected-record corruption, typed refusal and failed badge, no stale/partial fallback, GUI Clear exact quarantine bytes, downstream/sibling statuses, exact rerun rows, unchanged graph/revision and retained healthy history bytes. |

Representative visual check: J1 Chromium's final screencast frame was inspected from the actual trace; it shows Local execution, complete 2/2 banner, the Seed/Increment canvas, Node Data headers and saved-workflow feedback.
The screenshot is not substituted for the test's exact row or durable graph assertions.
J3's trace actions preserve the ordinary Workflows row double-click/Open, root/nested tab transitions, internal node and Node Data clicks; retained responses distinguish root public-column projection from the full scoped child projection.
The error-context page snapshot follows fixture cleanup and must not be misread as the pre-cleanup failure UI; the trace contains that earlier UI.
Readiness is 3/4, with no retries/skips among the passing journeys; the initial J3 Firefox case is explicitly unrun and the failed commands remain red.
No inventory denominator/status credit is changed yet; prior coverage percentages remain historical pending obligation-level reconciliation.

## N1 independent backend preparation

`/usr/bin/time -p scripts/test focus backend tests/test_services/test_viewer_preferences.py` passed 3/3 tests in 0.11 s pytest / 2 s lane / 2.47 s elapsed on platform `29733fa` plus the unchanged J1/J3 readiness assertion diff above, library `dff04e3` and the same installed dependency baseline.
It exercised durable workspace identity/favorites, structural move/delete/session identity, and forward-recoverable environment-forget journaling; no skips or retries were reported.
This lower-level real persistence evidence is independent of the pending frontend J3 repair and does not establish the N1 GUI scenarios or native launch.

## J3 repair diagnosis and focused validation

The three-pass dedicated plan review converged with no additional material change in pass 3.
Temporary review artifacts are `/private/tmp/bioimageflow-j3-activation-plan.md` and `/private/tmp/bioimageflow-j3-activation-review.md`; they are working artifacts and are not committed.
Temporary event probes were removed before repaired validation.
The instrumented diagnostic command used the exact J3 Chromium selector, `--output=test-results/campaign-j3-events --trace=on`: 1/1 passed, lane 17 s / elapsed 16.94 s; it observed both loaders but did not reproduce the late child steal.
The same selector with a temporary gate on the second real draft response and `--output=test-results/campaign-j3-events-controlled --trace=on` failed 1/1, lane 32 s / elapsed 32.09 s.
It captured explicit Open start at 445.2 ms, startup mount at 924.0 ms, child activation at 1458.8 ms, delayed explicit apply at 1547.3 ms and root reactivation at 1548.8 ms; Node Data then showed only the parent public column.
This supplies event-level causal evidence for ISSUE-018, while preserving the actual workflow row/child gestures and real backend payloads; the response gate changes timing only and is not final journey evidence.
Both traces are retained under their named `frontend/test-results` directories.

The independently reviewed implementation guards App startup at accepted named Open, preserves deliberate later existing-root activation, and uses that same App predicate for late saved-load presentation updates.
A speculative startup draft read does not track/acknowledge the active draft facade; the eventual accepted root canvas owns its draft application.
Explicit Open uses the existing recovery freshness rules for its own workflow, retaining the accepted draft revision as CAS base and keeping unrelated recovery separate.
Impact map: MenuBar accepted named Open → App startup/panel activation owner → startup/root-presentation loader → workflow presentation and draft facade consumers → root/nested selection, dirty state, result scope and recovery.
No backend, wire schema, dependency, result cache/storage or library execution implementation changed.
The repair updates v1 Section 3.8, v2 Section 13 and `PLATFORM_CONTEXT.md` for this lifecycle invariant.

Focused unit history is retained without presenting red commands as passes:

- Initial App/MenuBar/startup/root-presentation/registry focus: 95/95 passed, elapsed 8.67 s, before the additional late-store probes.
- Root-presentation probe: 1 failed / 3 passed, elapsed 1.02 s; delayed saved loading reset global current from `other` to `race`. This required the guarded startup store option.
- Five-file focus during adaptation: 2 failed / 96 passed, elapsed 11.36 s; failures were stale mock expectations and a misplaced new test observer, both corrected in test code.
- Exact MenuBar/startup files after those corrections: 82/82 passed, elapsed 7.84 s.
- App/MenuBar/startup/root-presentation/registry plus workflow-store focus: 158/158 passed, elapsed 8.26 s.
- Root-presentation final preservation/diagnostic tests: 5/5 passed, elapsed 1.49 s; after typed fixture metadata correction the exact file passed again, elapsed 0.98 s.

Repaired production/E2E diff SHA-256 is `6c6481a636be650e0ed87c8c43816674252615fddb4c6c92ad04e8a9b82b1bae` over `git diff -- frontend/src frontend/tests/e2e ':!frontend/src/**/__tests__/*'` on parent `29733fa`; full frontend source/test diff after the typed fixture correction is `7c39c19c2eb976688edfed0b2f8e354d7406f41f5870c1050878615330e17beb`.
Library/dependency/runtime baseline remains the Wave 1 baseline.

| Command after `scripts/test focus e2e` | Result | Duration |
| --- | --- | --- |
| Exact J3 selector, `--project=chromium --output=test-results/campaign-j3-fixed --trace=retain-on-failure` | 1/1 passed | lane 12 s / elapsed 12.24 s |
| Exact J3 selector, `--project=chromium --repeat-each=5 --output=test-results/campaign-j3-race-chromium --trace=retain-on-failure` | 5/5 passed | lane 34 s / elapsed 34.65 s |
| Exact J3 selector, `--project=firefox --output=test-results/campaign-j3-firefox --trace=retain-on-failure` | 1/1 passed | lane 18 s / elapsed 17.32 s |
| Exact J3 selector, `--project=firefox --repeat-each=5 --output=test-results/campaign-j3-race-firefox --trace=retain-on-failure` | 5/5 passed | lane 60 s / elapsed 59.70 s |

The repaired exact journey asserts distinct sibling/public and unpublished intermediate rows, then preserves the second internal result's immutable identity, visible nested editor and selected internal node after reload.
No browser retry/skip occurred; the five repetitions are deliberate stress for the reproduced timing defect.

`/usr/bin/time -p scripts/test check frontend` remained red at lane 23 s / elapsed 23.55 s: lint passed (9 s), all 134 Vitest files/1330 tests passed (23 s), production build passed (4 s), but type-check failed (7 s) because the new deferred saved-file fixture omitted required `artifact_hash`.
The fixture gained only that metadata field; production source, build inputs, browser fixtures, dependencies and all other unit files remained unchanged.
Instead of repeating unchanged passing phases, the exact affected unit file passed 5/5 (0.98 s), `/usr/bin/time -p bun run type-check` passed (4.84 s), and `/usr/bin/time -p bun run lint` passed (4.58 s), both from `frontend/`.
These are explicit repaired native subphases of the authoritative runner's failed completion command, forming composite frontend acceptance; the original command is not relabeled green.
Build retains its existing >500 kB chunk warning; no tests were skipped or deselected in the unit completion phase.
Browser/docs completion and integration are still pending.

### Reconciled readiness recheck

`/usr/bin/time -p scripts/test focus e2e tests/e2e/canvas-interactions.spec.ts tests/e2e/everyday-node-editing.spec.ts --grep 'builds, runs, inspects, saves, and reopens a real workflow through the GUI|recovers a real Direct failure without publishing a partial result|quarantines a corrupt selected record through GUI Clear and reruns exact rows' --project=chromium --project=firefox --output=test-results/campaign-j124-integrated --trace=retain-on-failure` passed 6/6, lane 61 s / elapsed 60.87 s.
This rechecks J1, J2 and J4 because the Open/startup presentation repair invalidated reuse of their earlier GUI outcomes; the deliberately failed Direct fixture remains expected behavior within the passing recovery test.
Source is parent `29733fa` plus the repaired production/E2E diff above; the typed unit-fixture correction is browser-independent, and editable dependencies, generated artifacts and disposable runtime assumptions are unchanged.
Together with the exact J3 passes and five repetitions per browser, all four focused readiness journeys now pass in Chromium and Firefox without retries/skips.
This is a 4/4 focused gate; final scoped completion, implementation review and commit are still pending.

### Delegated packet ownership

The user pointed out that root had retained too much implementation/testing work despite the plan's orchestrator/worker division.
Root corrected execution allocation without redesigning the campaign: N1 worker owns fresh branch/worktree `campaign/n1-current` / `.worktrees/campaign-n1-current`; E1 owns `campaign/e1-current` / `.worktrees/campaign-e1-current`, both created from `29733fa`.
They received bounded contracts, impact maps, independent setup requirements, task-only commits, evidence boundaries, review triggers and runtime ownership rules; root owns main readiness, integration and shared records, with one reserved specialist reviewing J3.
The source-only `.worktrees/bioimageflow` link points to the clean sibling library; environments, build output and runtime stores are prepared per worktree.
Independent lower-level work proceeds concurrently; browser-heavy lanes are granted sequentially, and E1's disposable backend provisioning is separately authorized without sharing runtime state.
No packet completion or passing credit follows from delegation alone.

### Wave 1 scoped completion

`/usr/bin/time -p scripts/test check cross-browser-smoke` passed 18/18 critical Chromium and 18/18 critical Firefox tests, lane 122 s / elapsed 122.82 s (Chromium phase 83 s, Firefox 122 s) on the repaired production/E2E diff above.
The two projects ran in independent fresh disposable roots as the scoped runner defines; no browser retry/skip was reported.
This unfiltered completion lane also exercised an existing managed-execution critical case outside the local campaign obligation scope; that broader test execution does not expand the campaign's accepted feature denominator.
It is a critical smoke, not the full browser projects or full suite.
A reserved independent implementation reviewer found no material blocking issue; this is read-only source/spec review, not a separately executed test or native certification.
ISSUE-018 is archived with its bounded resolution; ISSUE-013/014/017 remain open.
`/usr/bin/time -p env UV_OFFLINE=1 scripts/test check docs` passed, lane 3 s / elapsed 2.91 s on the same repaired application source plus the Wave 1 campaign/specification record; dashboard consistency (500 applicable cells, historical 266 verified), 49 active links and Sphinx 9.1.0 warnings-as-errors passed.
These documentary counts remain historical; no native/worker or whole-campaign acceptance is inferred.
The following status-only acceptance record does not change application/specification behavior or documentation navigation.
The task-only main commit will be the integrated baseline sent to workers.
