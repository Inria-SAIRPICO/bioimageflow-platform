---
orphan: true
---

# Restart the platform test campaign

Start a fresh session in this repository with **GPT-5.6 Sol**, reasoning **high**, as the orchestrator.
The requested specialist is **GPT-6 Astra**, reasoning **high**; ordinary workers use Sol/medium.
Model selection is a runtime setting, not an effect of reading this file.
The current runtime exposes these model identifiers for delegated agents; if a new runtime does not, report the configuration blocker instead of substituting silently.

The installed Codex CLI supports `--model` and `--config`; from the repository root, this starts a new master rather than resuming the old conversation:

```bash
codex --model gpt-5.6-sol -c 'model_reasoning_effort="high"' \
  'Read docs/developer/platform-test-start.md and execute its restart prompt.'
```

For the app, select the model and reasoning level in the session controls before sending the prompt below.
The command and controls request these settings; confirm the actual selected model in the client.
The `model` and `model_reasoning_effort` settings are described in the [official OpenAI configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference).
This documentation change does not launch a new campaign session or alter global Codex settings.

## Restart prompt

```text
Execute the BioImageFlow Platform testing campaign in this repository.
Use GPT-5.6 Sol with high reasoning as the main orchestrator and GPT-5.6 Sol with medium reasoning for focused ordinary workers.
The objective is to test and strengthen the platform, fix demonstrated bugs, and systematically cover all implemented in-scope features.
Use the plan's strict tiers and resume the highest-priority runnable obligation in the current tier; the Basic-Use Gate is already passed.
Do not assign a lower tier while a higher-tier runnable obligation remains; priority changes execution order, never the final coverage requirements.
Keep the orchestrator context focused on the feature-status table, current decisions, active ownership, and next three tasks.
Delegate detailed investigation, implementation, and focused validation in bounded packets; consume concise outcomes and failure excerpts, not full logs or worker transcripts.
Keep routine, bounded defects with Sol when intent and the repair boundary are clear.
For conflicting contracts, identity/data-loss risk, semantic redesign, unclear library behavior, or a failed bounded repair, delegate one focused decision packet to GPT-6 Astra with high reasoning and an identity/concurrency/persistence/rollback invariant checklist.
Request another specialist pass only for materially changed safety invariants or an unresolved concrete concern.
If Astra returns needs-owner on a shared-foundation issue, stop dependent work, record the issue, and ask me one concrete question; otherwise implement the established repair and continue independent work.

Read AGENTS.md and PLATFORM_CONTEXT.md, then docs/developer/platform-test-progress.md, docs/developer/platform-test-plan.md, and the open entries in docs/developer/platform-test-issues.md.
Read only the relevant coverage inventory and specifications for each assigned task.
Inspect git status/log and reconcile the checkpoint with actual files and installed library versions.
Do not assume historical workers still exist or temporary logs are available.
Do not repeat completed library releases, audits, or successful checks unless changes invalidate their evidence.

Continue from the first runnable action in the progress file after reconciling actual Git and worker state; do not treat historical issue examples in this prompt as an active queue.
Use the current catalog contract: single-click opens/toggles bottom tool information, double-click adds exactly one node, and drag is a separate creation gesture.
Prioritize remaining Primary-GUI journeys by ordinary use and risk of lost work, wrong identity, or wrong results before non-primary important extensions or specialist boundaries.
Preserve complete inventory obligations for negative, boundary, deployment, integration, native, and external cases after the basic paths.
Use disposable state for reproduction; do not change test expectations to manufacture a pass.
Keep writes disjoint and use at most two ordinary workers alongside the master, leaving a slot for Astra or urgent integration review; do not fill the slot merely to maximize parallelism.
When more than one agent may write in parallel, give each agent a dedicated worktree under `.worktrees/<task_name>`; never let parallel agents share one writable checkout.
Pass fresh, bounded task packets with explicit model/reasoning overrides rather than full-history forks; give each worker one coherent user journey, related dashboard `ID.cell` targets, owned paths, and the scoped completion check.
Strengthen an adequate existing browser journey to cover related refusal/recovery and identity cells before adding a near-duplicate test; avoid one long test whose early failure hides separate features.
Allow independent main-feature work while a bounded issue is investigated; freeze only dependent work unless the issue affects shared foundations.

Exclude parallel scheduling, HPC, Parsl, managed remote execution, and distributed engines from platform certification.
Keep Direct and test real Wetlands workers sequentially with one worker.
Run exact Chromium and Firefox selectors for a changed GUI journey, then use the smallest applicable `scripts/test` completion lane documented in `docs/testing.md`.
For localized browser test-only changes, do not add a complete browser-project run solely for reassurance; browser implementation/persistence changes, broad infrastructure changes, major GUI milestones, and final certification retain their documented broader checks.
Do not overlap browser-heavy completion lanes when shared machine resources could make failures ambiguous.
After a late failure, reproduce the exact failing selector/project and retain successful unchanged phases; rerun only invalidated checks.
Limit broad browser acceptance to one attempt per substantial milestone unless I explicitly request another or a later broad browser/E2E change requires it; do not repeatedly restart the full project to chase unrelated or nonreproduced failures.
Keep Tier 1B obligation closure separate from broad-lane certification: record a red/interrupted lane and its issue honestly, validate repairs with exact selectors and scoped checks, and reserve another broad attempt for the next planned milestone or final certification.
Use audited per-case exclusions.
Reuse existing scope selectors; do not build more runner infrastructure without a concrete testing need.
Make clean changes without backward-compatibility shims; update affected specifications, documentation, fixtures, and tests.
Commit each coherent validated task as soon as its issue or bounded task is resolved, including its durable progress update, without staging unrelated files.
Consolidate that task's inventory, dashboard, evidence, and checkpoint edits; run `scripts/test check docs` once for the batch and commit the documentation with or immediately after its product/test commit.
Use the dashboard verifier for interim counts instead of repeated full documentation builds; avoid separate administrative ownership and worktree-archival commits when the task-boundary record suffices.
Record an interruption, open defect, remote milestone, or owner decision immediately even when no feature is complete.
Do not begin another writable task in that checkout until the completed task is committed; keep restart points clean so the campaign can be interrupted safely.
Maintain the progress file, issue decisions, and feature inventories so another fresh session can continue without this conversation.
Keep completed validation history in platform-test-evidence.md and keep the active checkpoint short and internally consistent.
Use the established stable-ID dashboard to report verified applicable obligations over the total, separately for the whole campaign and primary GUI coverage; do not use raw test counts as completion percentages.
After remote CI, validation, publication, or dependency-availability milestones, update and commit the durable checkpoint/evidence before starting unrelated writable work; after interruption, reconcile the remote state before repeating an operation.
At each major GUI-wave boundary, run one representative primary Playwright journey headed when a visible display is available, otherwise retain trace/video/screenshots and record that no window was shown.
Before treating a specialist finding as P1 or release-blocking, prove its reachable platform entry path and user impact; keep artificial, unexposed dependency states as follow-ups without weakening reachable safety findings.
The fixed 73-cell Basic-Use Gate passed on the evaluated revision recorded in the progress file, and the owner chose to continue with Tier 1B.
Preserve that evidence; reevaluate the gate only if later relevant changes invalidate it, following the plan's exact matrix and current-revision requirements.
An owner-approved early pause leaves the systematic campaign incomplete and requires a durable risk/backlog checkpoint; do not infer such a decision from a status question.
Do not claim completion until every in-scope feature has verified applicable scenarios, all primary GUI journeys pass Chromium and Firefox, bugs are resolved, and external/manual obligations are completed or explicitly accepted by the owner as limitations.
Answer status questions briefly and continue the active campaign unless I explicitly pause it or change the objective.
Proceed until the campaign is complete or an escalation genuinely requires my decision.
```
