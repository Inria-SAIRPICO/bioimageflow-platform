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
The objective is to test and strengthen the platform, fix demonstrated bugs, and systematically cover all implemented in-scope features, with main GUI journeys first.
Priority changes execution order, never the final coverage requirements.
Keep the orchestrator context focused on the feature-status table, current decisions, active ownership, and next three tasks.
Delegate detailed investigation, implementation, and focused validation in bounded packets; consume concise outcomes and failure excerpts, not full logs or worker transcripts.
For an issue that is difficult, unsafe, or unclear, delegate a bounded investigation to GPT-6 Astra with high reasoning.
If Astra still cannot establish the intended contract and a safe repair, stop the whole campaign, record the issue, and ask me one concrete question.
Otherwise implement and validate the established repair autonomously.

Read AGENTS.md and PLATFORM_CONTEXT.md, then docs/developer/platform-test-progress.md, docs/developer/platform-test-plan.md, and the open entries in docs/developer/platform-test-issues.md.
Read only the relevant coverage inventory and specifications for each assigned task.
Inspect git status/log and reconcile the checkpoint with actual files and installed library versions.
Do not assume historical workers still exist or temporary logs are available.
Do not repeat completed library releases, audits, or successful checks unless changes invalidate their evidence.

Continue from the first runnable action in the progress file after reconciling actual Git and worker state.
ISSUE-005 has a preserved Run Selected reproduction awaiting contract assessment; ISSUE-001 and the scope-selection foundations are already resolved.
Use the current catalog contract: single-click opens/toggles bottom tool information, double-click adds exactly one node, and drag is a separate creation gesture.
Prioritize the main create/edit/connect/run/inspect/save/reopen journey, then everyday editing, nested workflows, failure/cancellation/recovery, and remaining features.
Preserve complete inventory obligations for negative, boundary, deployment, and integration cases after the main paths.
Use disposable state for reproduction; do not change test expectations to manufacture a pass.
Keep writes disjoint and use at most two ordinary workers alongside the master, leaving a slot for Astra.
When more than one agent may write in parallel, give each agent a dedicated worktree under `.worktrees/<task_name>`; never let parallel agents share one writable checkout.
Pass fresh, bounded task packets with explicit model/reasoning overrides rather than full-history forks.
Allow independent main-feature work while a bounded issue is investigated; freeze only dependent work unless the issue affects shared foundations.

Exclude parallel scheduling, HPC, Parsl, managed remote execution, and distributed engines from platform certification.
Keep Direct and test real Wetlands workers sequentially with one worker.
Comprehensive Chromium/Firefox GUI acceptance is opt-in after large changes, not part of every development edit.
Use scripts/test and its documented focused/completion gates with audited per-case exclusions.
Reuse valid unchanged phase results and existing scope selectors; do not build more runner infrastructure without a concrete testing need.
Make clean changes without backward-compatibility shims; update affected specifications, documentation, fixtures, and tests.
Commit each coherent validated task as soon as its issue or bounded task is resolved, including its durable progress update, without staging unrelated files.
Do not begin another writable task in that checkout until the completed task is committed; keep restart points clean so the campaign can be interrupted safely.
Maintain the progress file, issue decisions, and feature inventories so another fresh session can continue without this conversation.
Keep completed validation history in platform-test-evidence.md and keep the active checkpoint short and internally consistent.
Before Wave 6, normalize the inventories into a stable-ID dashboard and report verified applicable obligations over the total, separately for the whole campaign and primary GUI coverage; do not use raw test counts as completion percentages.
After remote CI, validation, publication, or dependency-availability milestones, update and commit the durable checkpoint/evidence before starting unrelated writable work; after interruption, reconcile the remote state before repeating an operation.
At each major GUI-wave boundary, run one representative primary Playwright journey headed when a visible display is available, otherwise retain trace/video/screenshots and record that no window was shown.
Before treating a specialist finding as P1 or release-blocking, prove its reachable platform entry path and user impact; keep artificial, unexposed dependency states as follow-ups without weakening reachable safety findings.
Do not claim completion until every in-scope feature has verified applicable scenarios, all primary GUI journeys pass Chromium and Firefox, bugs are resolved, and external/manual obligations are completed or explicitly accepted by the owner as limitations.
Answer status questions briefly and continue the active campaign unless I explicitly pause it or change the objective.
Proceed until the campaign is complete or an escalation genuinely requires my decision.
```
